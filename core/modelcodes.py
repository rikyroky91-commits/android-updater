"""Risoluzione codice modello → nome commerciale.

Perché serve: i codici tecnici interni (RMX3939, ANA-AL00, CPH2513...) non
compaiono quasi mai nei titoli delle notizie — i giornalisti scrivono
"Realme C63", non "RMX3939" — quindi cercarli alla lettera su Google News
non trova nulla anche quando il modello esiste ed è stato aggiornato di
recente. Questo modulo risolve il codice al nome commerciale prima che la
ricerca live parta, combinando DUE dataset pubblici indipendenti:

1. KHwang9883/MobileModels-csv — community, copre bene i brand cinesi/globali
   con le loro varianti regionali (colonne: model = codice, model_name = nome).
2. La lista ufficiale di Google dei dispositivi certificati Play Store
   (storage.googleapis.com/play_public/supported_devices.csv) — enorme
   (ogni dispositivo Android mai certificato), colonne: Retail Branding,
   Marketing Name, Device (nome in codice), Model (stringa modello).
   ATTENZIONE: questo file è codificato in UTF-16, non UTF-8 — va decodificato
   esplicitamente, altrimenti (esperienza già fatta con un bug simile sul BOM
   dell'altro CSV) il parsing fallisce silenziosamente senza errori evidenti.

I risultati delle due fonti vengono uniti: uno stesso codice può comparire
in una, nell'altra, o in entrambe con nomi leggermente diversi — meglio
mostrarli tutti che sceglierne uno arbitrariamente.

Un codice può risolvere a PIÙ nomi commerciali: lo stesso numero di modello
viene spesso riusato per varianti regionali diverse (es. RMX3939 = Realme
C61 Global, C63, C65s e NARZO N63 insieme).
"""
from __future__ import annotations

import csv
import os
import re
import io
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import config as C
from . import storage

_REFRESH_HOURS = 24 * 7  # dataset che cambiano raramente: un refresh a settimana basta
_DOWNLOAD_TIMEOUT = C.HTTP_TIMEOUT + 45  # sono file unici da diversi MB

MOBILEMODELS_URL = "https://raw.githubusercontent.com/KHwang9883/MobileModels-csv/refs/heads/main/models.csv"
GOOGLE_PLAY_URL = "https://storage.googleapis.com/play_public/supported_devices.csv"

CARTELLA_DATI = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FILE_OVERRIDE_NOMI = os.path.join(CARTELLA_DATI, "nomi_modello.csv")

_memory_cache: dict[str, list[str]] | None = None
# Indice inverso nome commerciale -> codici tecnici, costruito su richiesta
# a partire da `_memory_cache` (vedi codes_for_name).
_reverse_cache: dict[str, list[str]] | None = None
_reverse_senza_suffisso: dict[str, list[str]] | None = None
_reverse_compatto: dict[str, list[str]] | None = None
# Codice tecnico -> nome della marca COME LO SCRIVE IL DATASET.
#
# LA MARCA ERA GIÀ NEL FILE, e veniva buttata via. `brand_from_code` la
# deduceva da una manciata di espressioni regolari scritte a mano (`RMX`,
# `CPH`, `SM-`, `XT`…), quindi ogni famiglia non prevista finiva sotto
# «Altri brand»: `PCET00` (Oppo), `V2283A` (vivo), `CLT-L04` (Huawei),
# `G020E` (Pixel). E un brand sbagliato è un `device_key` diverso, cioè
# due schede per lo stesso telefono a seconda di come lo si cerca.
#
# Aggiungere una regex per ogni famiglia sarebbe una rincorsa senza fine.
# I dataset dichiarano la marca riga per riga: la si legge e basta.
_marca_di_codice: dict[str, str] | None = None

# Codice tecnico -> nome commerciale scelto A MANO, verificato — vedi
# `data/nomi_modello.csv` e `_indice_override_nomi()` più sotto. Risolve i
# codici con più nomi commerciali VERI (varianti regionali dello stesso
# hardware) dove l'algoritmo di `nome_canonico` sceglierebbe il nome più
# corto anche quando non è il più riconoscibile — vedi CPH2781 nel CSV.
_override_nomi: dict[str, str] | None = None

# Sigle di CONNETTIVITÀ, non di gamma. La distinzione è tutta qui: «5G» in
# «Galaxy A55 5G» non individua un telefono diverso da «Galaxy A55», mentre
# «Ultra», «Pro», «Plus» e «FE» sì. Togliere anche quelle unirebbe modelli
# distinti e restituirebbe il codice sbagliato — molto peggio di nessun
# codice, perché un dato falso non si nota.
_SUFFISSI_CONNETTIVITA = ("5g", "4g", "lte", "wifi", "wi fi", "ds", "dual sim")


def _senza_suffissi(chiave_normalizzata: str) -> str:
    """«galaxy a55 5g» → «galaxy a55». Lavora sulla chiave già normalizzata.

    Lo spazio va ripulito a ogni giro: senza, il risultato è «galaxy a55 »
    con lo spazio in coda, che non combacia con niente — il ripiego
    sembrava attivo e non trovava nulla lo stesso.
    """
    testo = (chiave_normalizzata or "").strip()
    cambiato = True
    while cambiato:
        cambiato = False
        for suffisso in _SUFFISSI_CONNETTIVITA:
            for forma in (suffisso, suffisso.replace(" ", "")):
                if len(testo) > len(forma) + 2 and testo.endswith(forma):
                    testo = testo[: -len(forma)].strip()
                    cambiato = True
    return " ".join(testo.split())

# Stato leggibile dell'ultimo caricamento di ciascuna fonte, per distinguere
# "database non raggiungibile" da "codice non presente" invece di un
# fallimento silenzioso indistinguibile (bug già preso una volta: il
# download riusciva ma il parsing falliva senza errori visibili).
_status = {"mobilemodels": "non ancora caricato", "google_play": "non ancora caricato"}


def status() -> str:
    """Diagnostica leggibile sull'ultimo tentativo di caricare entrambi i
    database dei codici modello. Usato dalla scheda Diagnostica e nei
    messaggi di errore della ricerca."""
    return f"MobileModels: {_status['mobilemodels']} | Google Play: {_status['google_play']}"


def _download(url: str, source_key: str) -> bytes | None:
    if requests is None:  # pragma: no cover
        _status[source_key] = "libreria 'requests' non disponibile"
        return None
    try:
        response = requests.get(url, timeout=_DOWNLOAD_TIMEOUT, headers={"User-Agent": C.USER_AGENT})
    except Exception as exc:
        _status[source_key] = f"connessione fallita: {exc}"
        return None
    if response.status_code != 200:
        _status[source_key] = f"HTTP {response.status_code}"
        return None
    if not response.content or len(response.content) < 1000:
        # Questi file sono sempre da diversi MB: una risposta minuscola
        # indica quasi certamente una pagina di errore, non i dati veri.
        _status[source_key] = f"risposta sospettosamente corta ({len(response.content)} byte)"
        return None
    _status[source_key] = f"scaricato con successo ({len(response.content) // 1024} KB)"
    return response.content


def _cached_bytes(url: str, source_key: str, bytes_meta_key: str, fetched_meta_key: str) -> bytes | None:
    """Bytes grezzi da cache se abbastanza freschi, altrimenti riscaricati;
    se la rete non risponde ricade sulla cache anche se vecchia."""
    fetched_at = storage.get_meta(fetched_meta_key)
    in_cache = storage.get_blob(bytes_meta_key)
    if in_cache and fetched_at:
        try:
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
        except ValueError:
            age_h = _REFRESH_HOURS + 1
        if age_h < _REFRESH_HOURS:
            _status[source_key] = f"da cache (aggiornata {age_h:.0f}h fa)"
            return in_cache

    fresh = _download(url, source_key)
    if fresh:
        storage.set_blob(bytes_meta_key, fresh)
        storage.set_meta(fetched_meta_key, datetime.now(timezone.utc).isoformat())
        return fresh
    if in_cache:
        _status[source_key] += " — uso la cache precedente (non aggiornatissima)"
        return in_cache
    _status[source_key] += " — nessuna cache precedente disponibile"
    return None


def _nome_visualizzato(marca: str, commerciale: str) -> str:
    """«Retail Branding» + «Marketing Name», senza ripetere la marca.

    UNDICIMILA NOMI SBAGLIATI, E LI SCRIVEVAMO NOI. Il CSV di Google tiene
    la marca e il nome in due colonne, ma il nome spesso la contiene già:
    unirli sempre produceva «POCO POCO M4 Pro», «Nokia Nokia C32», «Honor
    HONOR Magic6» — 11 251 voci su questa forma.

    Non è un problema estetico. Il nome finisce nella chiave del
    dispositivo: chi cercava «POCO M4 Pro» e chi arrivava dal codice
    `FLEUR` — che risolve al nome duplicato — ottenevano due schede
    diverse per lo stesso telefono. Lo stesso difetto della v40, prodotto
    dal nostro modo di leggere il file invece che dalle grafie delle fonti.
    """
    marca = " ".join((marca or "").split())
    commerciale = " ".join((commerciale or "").split())
    if not commerciale:
        return marca
    if not marca:
        return commerciale
    # Il confronto è per PAROLE INTERE, non per prefisso: «Tecno» e
    # «TECNOPOP 5C» non sono una ripetizione — «TECNOPOP» è una gamma, e
    # togliere la marca lascerebbe un nome che il catalogo non usa.
    parole_marca = marca.lower().split()
    parole_nome = commerciale.lower().split()
    if parole_nome[:len(parole_marca)] == parole_marca:
        return commerciale
    return f"{marca} {commerciale}"


def _ricorda_marca(codice: str, marca: str) -> None:
    """Annota la marca dichiarata dal dataset per questo codice."""
    global _marca_di_codice
    codice = (codice or "").strip().upper()
    marca = (marca or "").strip()
    if not codice or not marca:
        return
    if _marca_di_codice is None:
        _marca_di_codice = {}
    _marca_di_codice.setdefault(codice, marca)


def marca_dichiarata(codice: str) -> str | None:
    """La marca che i dataset attribuiscono a questo codice, o None.

    Risponde solo per un codice ESATTO: su un testo qualsiasi tacere è
    l'unica risposta onesta, e chi chiama ha altri modi per dedurla.
    """
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = _build_index()
    return (_marca_di_codice or {}).get((codice or "").strip().upper())


def carica_override_nomi(testo: str) -> dict[str, str]:
    """Legge `data/nomi_modello.csv`: codice modello -> nome preferito.

    Stessa forma di `soc.carica_curato`: righe che iniziano con `#` sono
    commenti (il CSV standard non li prevede, ma qui servono a spiegare
    *perché* la tabella esiste, e quella spiegazione deve stare accanto ai
    dati). Esiste come funzione a sé — invece di leggere il file dentro
    `_indice_override_nomi()` — per poter essere collaudata con un testo
    in memoria, senza toccare il disco (stesso motivo di `carica_da` in
    `core/specs.py` e `core/aer_catalog.py`).
    """
    righe = [r for r in (testo or "").splitlines() if not r.lstrip().startswith("#")]
    indice: dict[str, str] = {}
    for riga in csv.DictReader(io.StringIO("\n".join(righe))):
        codice = (riga.get("codice") or "").strip().upper()
        nome = (riga.get("nome") or "").strip()
        if codice and nome:
            indice[codice] = nome
    return indice


def _indice_override_nomi() -> dict[str, str]:
    global _override_nomi
    if _override_nomi is None:
        try:
            with open(FILE_OVERRIDE_NOMI, encoding="utf-8-sig") as f:
                testo = f.read()
        except OSError:
            testo = ""
        _override_nomi = carica_override_nomi(testo)
    return _override_nomi


def nome_scelto_a_mano(codice: str) -> str | None:
    """Il nome deciso in `data/nomi_modello.csv` per questo codice, se c'è.

    Serve a chi deve distinguere due cose che `nome_canonico` restituisce
    allo stesso modo: una scelta AUTOMATICA fra i nomi noti — legittima,
    ma che una fonte strutturata può battere, perché conosce il mercato —
    e una riga scritta a mano dopo aver verificato, che invece non deve
    essere battuta da nessuno.

    Il caso che l'ha resa necessaria: RMX3997 è venduto come «C65 5G»,
    «NARZO N65» e «realme 12x 5G». Sono tutti nomi veri, e la fonte
    strutturata ne restituisce uno qualsiasi; in Europa serve l'ultimo,
    perché è quello sotto cui il telefono riceve gli aggiornamenti.
    Nessun automatismo può saperlo — la riga curata sì.
    """
    if not codice:
        return None
    return _indice_override_nomi().get(codice.strip().upper()) or None


def _add_names(index: dict[str, list[str]], code: str, name: str) -> None:
    code = code.strip().upper()
    name = name.strip()
    if not code or not name:
        return
    names = index.setdefault(code, [])
    if name not in names:
        names.append(name)


def _build_mobilemodels_index() -> dict[str, list[str]]:
    raw = _cached_bytes(
        MOBILEMODELS_URL, "mobilemodels", "modelcodes_mm_bytes", "modelcodes_mm_fetched_at"
    )
    if not raw:
        return {}
    # UTF-8 con BOM iniziale ("\ufeffmodel,dtype,..."): va tolto o il nome
    # della prima colonna letto da DictReader diventa "\ufeffmodel" invece
    # di "model", scartando ogni riga silenziosamente (bug già preso una volta).
    text = raw.decode("utf-8-sig", errors="replace")
    index: dict[str, list[str]] = {}
    try:
        for row in csv.DictReader(io.StringIO(text)):
            # QUI LA MARCA NON SI AGGIUNGE, ed è una scelta misurata.
            # Provato il contrario — usare `_nome_visualizzato` come fa il
            # parser di Google — la coerenza fra ricerca per nome e per
            # codice PEGGIORA (Xiaomi dall'83% al 49%): i due dataset
            # finiscono per dare nomi di lunghezza diversa per lo stesso
            # codice, e `resolve()` ne restituisce uno solo. Il prefisso di
            # marca si toglie invece nella CHIAVE, dove non distingue
            # niente (vedi `extract.radice_modello`).
            _add_names(index, row.get("model") or "", row.get("model_name") or "")
            _ricorda_marca(row.get("model") or "",
                           row.get("brand_title") or row.get("brand") or "")
    except csv.Error as exc:
        _status["mobilemodels"] = f"CSV scaricato ma non interpretabile: {exc}"
        return {}
    _status["mobilemodels"] += f" — {len(index)} codici indicizzati"
    return index


def _build_google_play_index() -> dict[str, list[str]]:
    raw = _cached_bytes(
        GOOGLE_PLAY_URL, "google_play", "modelcodes_gp_bytes", "modelcodes_gp_fetched_at"
    )
    if not raw:
        return {}
    # Questo file è UTF-16 (LE, con BOM), non UTF-8: decodificarlo come UTF-8
    # produce testo con un carattere ogni due sbagliato invece di un errore
    # esplicito — un fallimento silenzioso, esattamente il tipo di bug già
    # preso una volta col CSV precedente. "utf-16" (senza suffisso) rileva
    # da solo LE/BE dal BOM.
    try:
        text = raw.decode("utf-16")
    except UnicodeError:
        text = raw.decode("utf-8", errors="replace")
    index: dict[str, list[str]] = {}
    try:
        for row in csv.DictReader(io.StringIO(text)):
            brand = (row.get("Retail Branding") or "").strip()
            marketing = (row.get("Marketing Name") or "").strip()
            display = _nome_visualizzato(brand, marketing)
            if not display:
                continue
            _add_names(index, row.get("Device") or "", display)
            _add_names(index, row.get("Model") or "", display)
            _ricorda_marca(row.get("Device") or "", brand)
            _ricorda_marca(row.get("Model") or "", brand)
    except csv.Error as exc:
        _status["google_play"] = f"CSV scaricato ma non interpretabile: {exc}"
        return {}
    _status["google_play"] += f" — {len(index)} codici indicizzati"
    return index


def carica_indice(indice: dict[str, list[str]]) -> None:
    """Sostituisce l'indice in memoria con uno dato.

    Serve ai test: senza questo seme, ogni prova sulla risoluzione dei
    codici scaricherebbe i dataset veri, e la suite fallirebbe su una
    macchina senza rete — cosa che è puntualmente successa. Il progetto ha
    la regola che nessun test tocchi la rete, e senza un punto di innesto
    quella regola non è applicabile a questo modulo.

    SOSTITUIRE L'INDICE VUOL DIRE BUTTARE VIA TUTTO QUELLO CHE NE DERIVA.
    Qui si assegnava il solo `_memory_cache`, e gli indici costruiti a
    partire da lui — quello inverso (nome → codici), le sue due varianti
    e quello per cifre — restavano quelli di PRIMA. Chi chiamava
    `codes_for_name` continuava quindi a ricevere risposte del catalogo
    vecchio, mescolate a un `resolve` del catalogo nuovo: due cataloghi
    diversi consultati nella stessa frase.

    Il guasto misurato: `resolve_senza_ambiguita("SM-A325F")` tornava
    vuota. Il nome «Galaxy A32» era corretto e presente nell'indice
    appena caricato, ma l'indice inverso rimasto indietro lo dava a
    quattro codici, quindi risultava ambiguo e veniva scartato — e
    «SM-A325F» non arrivava più a «Galaxy A32». Restava nascosto perché
    l'indice inverso vero non veniva quasi mai costruito prima.
    """
    global _memory_cache, _reverse_cache, _reverse_senza_suffisso
    global _reverse_compatto, _per_cifre
    _memory_cache = dict(indice)
    _reverse_cache = None
    _reverse_senza_suffisso = None
    _reverse_compatto = None
    _per_cifre = None


def _build_index() -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for code, names in _build_mobilemodels_index().items():
        for name in names:
            _add_names(merged, code, name)
    for code, names in _build_google_play_index().items():
        for name in names:
            _add_names(merged, code, name)
    return merged


#: Un codice modello scritto con degli spazi in mezzo: una sigla di marca
#: (`CPH`, `XT`, `SM`, `RMX`) e dei numeri, separati da spazi che nel
#: codice vero non ci sono. NON deve riconoscere i nomi commerciali —
#: «Galaxy A54 5G» ha la stessa forma a occhio, e attaccarne le parole
#: produrrebbe una chiave che non esiste — per questo la sigla iniziale è
#: limitata a quattro lettere e il resto deve essere numerico.
_CODICE_CON_SPAZI = re.compile(
    r"^([A-Z]{1,4})\s+(\d{3,5})(?:\s+(\d{1,2}))?$")


def _varianti_senza_spazi(codice: str) -> list[str]:
    """Le forme compatte di un codice scritto con gli spazi.

    «CPH 2695» → «CPH2695»; «XT2553 1» → «XT25531» e «XT2553-1», perché
    le varianti Motorola si separano col trattino e chi le trascrive a
    mano ci mette uno spazio.
    """
    pezzi = _CODICE_CON_SPAZI.match((codice or "").strip().upper())
    if not pezzi:
        # «XT2553 1»: la sigla è già attaccata al numero, resta la coda.
        coda = re.fullmatch(r"^([A-Z]{1,4}\d{3,5})\s+(\d{1,2})$",
                            (codice or "").strip().upper())
        if not coda:
            return []
        return [f"{coda.group(1)}-{coda.group(2)}", f"{coda.group(1)}{coda.group(2)}"]
    marca, numero, variante = pezzi.groups()
    if not variante:
        return [f"{marca}{numero}"]
    return [f"{marca}{numero}-{variante}", f"{marca}{numero}{variante}"]


def resolve(code: str) -> list[str]:
    """Nomi commerciali noti per un codice modello (es. 'RMX3939' →
    ['realme C61 Global', 'realme C63', 'realme C65s', 'realme NARZO N63']),
    combinando entrambi i dataset. Lista vuota se il codice non è in nessuno
    dei due — probabilmente perché il testo passato non è affatto un codice
    tecnico, ma già un nome per esteso. Usa `status()` per sapere se i
    database si sono anche solo caricati.
    """
    global _memory_cache
    # L'INDICE SI LEGGE UNA VOLTA SOLA, IN UNA LOCALE.
    #
    # `if _memory_cache is None: ...` seguito da `_memory_cache.get(...)`
    # lascia in mezzo una finestra: un altro thread può azzerare la cache
    # fra il controllo e l'uso, e la riga dopo trova `None`. Non è teoria
    # — un ciclo di sforzo con thread paralleli l'ha fatto scattare:
    # «AttributeError: 'NoneType' object has no attribute 'get'», cioè un
    # 500 sulla pagina di chi stava cercando.
    #
    # Il rimedio non è un lucchetto: costruire l'indice due volte non fa
    # danno (si perde lavoro, non correttezza), mentre serializzare ogni
    # lettura di un indice usato da tutta l'applicazione sì. Basta legare
    # il dizionario a un nome LOCALE: da lì in poi nessuno può togliercelo
    # di sotto.
    indice = _memory_cache
    if indice is None:
        indice = _memory_cache = _build_index()
    codice = (code or "").strip().upper()
    nomi = indice.get(codice, [])
    # QUI NON SI NORMALIZZANO GLI SPAZI, DI PROPOSITO.
    #
    # Ci avevo messo un ripiego che risolveva anche «rmx 3939», e sembrava
    # innocuo. Non lo era: chi chiama questa funzione usa il codice che le
    # ha passato per costruire la descrizione del risultato, e trovando
    # una risposta sul testo grezzo si teneva quel testo — «codice rmx
    # 3939» invece di «codice RMX3939». Il compito di raddrizzare quello
    # che è stato digitato spetta all'ingresso della ricerca
    # (`web.main._codice_con_gli_spazi`), che sostituisce la domanda una
    # volta sola: da lì in poi tutti vedono la stessa forma, e nessuno
    # deve indovinare quale delle due sta guardando.
    #
    # `_varianti_senza_spazi` resta pubblica in questo modulo perché è lì
    # che sa di codici — la usa l'ingresso della ricerca.
    # Il catalogo di certificazioni Motorola e' la fonte primaria per i
    # codici XT europei che i due dataset generici non elencano. E' una
    # risposta di identita' soltanto: firmware e versione continuano a
    # provenire dalla fonte dedicata Motorola.
    if not nomi and re.fullmatch(r"XT\d{4}(?:-\d{1,2})?", codice):
        try:
            from . import motorola_catalog
            nome = motorola_catalog.name_for_code(codice)
            if nome:
                nomi = [nome]
        except Exception:
            pass
    if len(nomi) < 2:
        return nomi

    # IL NOME COMMERCIALE PRIMA DEL CODICE RIPETUTO.
    #
    # Ottomila nomi su 89 342 (l'8%) non sono nomi: sono il codice scritto
    # una seconda volta, perché il dataset non aveva altro da mettere in
    # quella colonna. Per 582 codici però il nome vero c'è — solo che
    # arriva DOPO, e chi legge prende il primo.
    #
    # L'effetto si vedeva su OPPO: cercando `CPH2385` si otteneva «OPPO
    # A57s», cercando «Oppo CPH2385» — che è il nome messo lì dal dataset —
    # si otteneva un dispositivo chiamato come un codice. Due schede per lo
    # stesso telefono, e una con un nome che nessuno riconoscerebbe.
    #
    # Non se ne butta via nessuno: chi non ha alternative tiene il suo.
    return sorted(nomi, key=lambda n: _e_il_codice(n, codice))


def resolve_senza_ambiguita(code: str) -> list[str]:
    """Come `resolve()`, ma **senza i nomi condivisi con un telefono diverso**.

    ## Il bug che questa funzione esiste per evitare

    Cercando «realme c63» il sito rispondeva con la scheda di «C61»: niente
    foto, niente CPU, aggiornamenti di un modello (RMX3930) diverso da
    quello cercato (RMX3939, che questo stesso progetto ha verificato a
    mano come "realme C63" — vedi `data/soc_modelli.csv`). La causa non è
    un dato inventato, è un nome AMBIGUO usato come se non lo fosse:

        resolve("RMX3939")   -> [..., "C61", "C63", ...]
        codes_for_name("C61") -> ["RMX3930", "RMX3933", "RMX3939"]

    Il dataset MobileModels (community, non verificato) assegna "C61" a
    TRE codici diversi. `forme_equivalenti()` prendeva ogni nome restituito
    da `resolve()` e lo usava come se identificasse senza ambiguità lo
    stesso identico telefono del codice di partenza — vero per "C63",
    "C65s", "NARZO N63" (che risolvono a un solo codice, proprio questo),
    falso per "C61" (che ne risolve a tre). Provando "C61" come forma
    equivalente di RMX3939, la ricerca trovava il piano ufficiale
    Android Enterprise Recommended del VERO C61 (RMX3930, fonte Google,
    non il dataset community) e lo presentava come se fosse la risposta
    alla domanda su RMX3939.

    ## Il punto 2, e perché la prima versione era troppo severa

    La prima versione teneva un nome solo se `codes_for_name(nome)`
    tornava **esattamente** `[code]` — un solo codice al mondo. Misurato
    sui dati veri, questo buttava via anche i casi INNOCUI: Samsung vende
    lo stesso «Galaxy A32» sotto tre codici regionali,

        resolve("SM-A325F") -> ["Galaxy A32"]
        resolve("SM-A325M") -> ["Galaxy A32"]
        resolve("SM-A325N") -> ["Galaxy A32"]
        codes_for_name("Galaxy A32") -> ["SM-A325F", "SM-A325M", "SM-A325N"]

    tre codici, stesso identico telefono — non un'ambiguità, è la normale
    variante di mercato. La versione precedente scartava "Galaxy A32" per
    tutti e tre, e una ricerca su «SM-A325F» smetteva di arrivare al nome
    commerciale. Misurato con un test che prova ogni grafia dello stesso
    telefono (`test_quattro_segnalazioni.py`), fallito appena introdotto.

    La differenza vera fra i due casi non è "quanti codici condividono
    questo nome", è "quei codici sono davvero lo stesso telefono". Un
    codice fratello che ha ESATTAMENTE lo stesso insieme di nomi (come i
    tre A325) è una variante regionale innocua. Un codice fratello con
    un insieme di nomi DIVERSO (RMX3933 risolve anche a "Note 60", "Note
    60s", "NARZO N61" — non solo "C61") sta usando quel nome come alias
    di un telefono che, per il resto della sua identità, è un altro
    dispositivo: lì il nome va scartato.

    Un nome resta valido come forma di ricerca solo se OGNI codice
    fratello che lo rivendica ha, complessivamente, lo stesso insieme di
    nomi di questo codice — altrimenti il nome punta a dispositivi con
    un'identità diversa e va scartato: è lo stesso principio "meglio
    saltare che indovinare" già applicato al catalogo specifiche. Il
    codice nudo non passa da questo filtro e resta sempre utilizzabile:
    è l'unica forma che il dataset non può rendere ambigua.
    """
    codice_pulito = code.strip().upper()
    nomi = resolve(code)
    proprio = set(nomi)
    risultato = []
    for nome in nomi:
        fratelli = [c for c in codes_for_name(nome) if c != codice_pulito]
        ambiguo = any(set(resolve(fratello)) != proprio for fratello in fratelli)
        if not ambiguo:
            risultato.append(nome)
    return risultato


def _e_il_codice(nome: str, codice: str) -> bool:
    """True se questo «nome» è in realtà il codice ripetuto.

    Conta anche «Oppo CPH2385», cioè il codice con davanti la marca: è la
    forma più frequente, e guardando solo l'inizio della stringa sfuggiva
    tutta. Ciò che resta dopo aver tolto il codice deve però essere corto —
    una parola di marca, non un nome vero: «Galaxy A54 SM-A546B» resta un
    nome, perché senza il codice dice ancora «Galaxy A54».
    """
    n = re.sub(r"[^A-Za-z0-9]", "", nome or "").upper()
    c = re.sub(r"[^A-Za-z0-9]", "", codice or "").upper()
    if len(c) < 4 or not n:
        return False
    if n.startswith(c) or c.startswith(n):
        return True
    return c in n and len(n.replace(c, "", 1)) <= 8


#: Le parole di marca si tolgono prima di confrontare due nomi: le fonti
#: le aggiungono e le tolgono a piacere, e «OPPO Reno12 F» e «Reno12 F»
#: sono lo stesso telefono.
_PAROLE_DI_MARCA = {
    "oppo", "realme", "oneplus", "samsung", "xiaomi", "redmi", "poco",
    "vivo", "iqoo", "motorola", "moto", "honor", "huawei", "google",
    "nokia", "zte", "tecno", "infinix", "itel", "asus", "sony", "nothing",
}


def _radice_famiglia(nome: str) -> str:
    """La parte del nome che identifica il modello, senza marca né grafia.

    «OPPO Reno12 F 5G» → «reno12f5g». Serve a capire se due nomi dello
    stesso codice sono lo stesso telefono scritto in due modi o due
    telefoni diversi.
    """
    parole = [p for p in re.split(r"[^0-9A-Za-z]+", (nome or "").lower()) if p]
    utili = [p for p in parole if p not in _PAROLE_DI_MARCA]
    return "".join(utili or parole)


def nome_canonico(codice: str) -> str | None:
    """UN nome solo per un codice, scelto sempre allo stesso modo.

    **QUESTA È LA RADICE DI META' DEI DIFETTI DI QUESTE VERSIONI.**

    L'identità di un dispositivo la costruiamo dal NOME, ma le fonti
    identificano i telefoni per CODICE — e il 17% dei codici ha più di un
    nome. `CPH2423` è insieme «一加 10R», «OnePlus 10R» e «OnePlus 10R 5G»:
    lo stesso identico telefono, tre grafie, e con una chiave costruita sul
    nome diventava tre dispositivi.

    Ogni correzione fatta finora — le parole di marca, i nomi cinesi, le
    parentesi, la marca ripetuta, il confronto per parole intere — cercava
    di far collassare grafie diverse su una chiave sola. È una partita che
    non si vince: le grafie sono un dato della realtà, non un errore da
    normalizzare.

    Qui si fa il contrario: quando il codice è noto, **è il codice a
    decidere il nome**, sempre lo stesso, e tutte le strade che arrivano a
    quel telefono arrivano alla stessa identità.

    La scelta è deterministica e motivata, non arbitraria:
      1. mai un nome che è il codice ripetuto;
      2. mai un nome che il dataset condivide con un ALTRO codice, se ne
         esiste uno che non lo condivide — vedi sotto;
      3. alfabeto latino prima dei caratteri cinesi — l'app è in italiano e
         confronta con fonti occidentali;
      4. il più corto, che è la forma senza suffissi di mercato;
      5. a parità, l'ordine alfabetico, perché due esecuzioni diverse non
         devono dare due nomi diversi.

    ## Il punto 2, e perché è stato aggiunto

    Misurato in produzione: cercando «realme c63» (RMX3939, verificato a
    mano come "realme C63" in `data/soc_modelli.csv`) il nome scelto era
    «realme C61» — non sbagliato di per sé (il dataset registra anche
    questo come un nome di RMX3939), ma quel nome è REGISTRATO ALLO STESSO
    MODO anche per RMX3930, il vero C61 secondo Android Enterprise
    Recommended. Fra due nomi ugualmente validi per lo stesso codice, uno
    condiviso con un telefono diverso e uno no, scegliere quello condiviso
    è la scelta più confondibile delle due — e prima non c'era nessun
    motivo per preferire l'altro.

    ## Un caso limite scoperto dopo: un nome senza UNA lettera

    Segnalato dall'utente sul sito vero: un IMEI risolto a un realme 7
    (`RMX2151`) mostrava come nome solo «7». Non un difetto di questa
    funzione — «7» è per quel codice l'UNICO nome vero che
    `resolve()` conosce, quindi non c'è nulla fra cui scegliere — ma il
    dataset community (MobileModels) registra a volte il solo numero di
    gamma, senza marca, per come alcuni produttori compilano il campo
    `model_name`.

    **Perché non si prefissa la marca a ogni nome di quel dataset.** È
    già stato provato, ed è annotato in `_build_mobilemodels_index()`
    (vedi il suo commento): farlo per OGNI riga fa PEGGIORARE la
    coerenza fra ricerca per nome e per codice (misurato: Xiaomi
    dall'83% al 49%), perché i due dataset finiscono per dare nomi di
    lunghezza diversa per lo stesso codice e `resolve()` ne restituisce
    uno solo. Quella scelta resta: `resolve()` non cambia.

    **Cosa cambia invece, e perché è un caso diverso**: qui si ripara
    SOLO il risultato finale, e SOLO quando non ha una sola lettera — un
    nome così non identifica niente da solo, a differenza di «C61» o
    «Note 60», che restano tali e quali. La marca aggiunta non è
    indovinata: `marca_dichiarata()` legge la colonna che il dataset
    dedica proprio a questo (indipendente dal nome commerciale, quindi
    non soggetta alla stessa regressione), e `_nome_visualizzato()` è la
    stessa funzione già usata per il dataset Google — non una seconda
    euristica da tenere allineata alla prima.

    ## Un altro caso limite: due nomi ugualmente veri, nessuno sbagliato

    Segnalato dall'utente: `CPH2781` risolve a «OPPO F31» *e* «OPPO A6
    Pro» — non un errore del dataset, ma lo stesso hardware venduto con
    due nomi commerciali diversi in due mercati diversi (Cina la prima,
    Global/India/Medio Oriente la seconda — verificato con più fonti
    indipendenti, non assunto). Qui la regola 4 sceglie «F31» solo perché
    è più corto: un criterio che funziona bene quando un nome è solo un
    suffisso di mercato dell'altro («C61» vs «C61 Global»), ma qui sceglie
    fra due nomi commerciali del tutto distinti, e non ha nessun modo di
    sapere che per un'app usata in Italia il nome Global è quello
    riconoscibile.

    Non è un caso isolabile con una regola generale — è esattamente
    l'ambiguità per cui esiste la correzione a mano (vedi
    `web/main.py::_opzioni_correzione`) — ma chiedere a OGNI persona di
    correggerlo a mano, per SEMPRE, per un caso già verificato una volta,
    non è «alla radice»: è la stessa correzione ripetuta all'infinito.
    `data/nomi_modello.csv` è la via di mezzo: una tabella curata a mano,
    corta di proposito (stessa filosofia di `data/soc_modelli.csv`), che
    SCEGLIE fra nomi che il dataset conferma già — non ne inventa mai uno
    nuovo — e che viaggia col repository invece che nel database
    effimero, quindi sopravvive a un reset completo. Ha la precedenza su
    tutto il resto di questa funzione, ma si applica solo se il nome
    scritto lì è ancora fra quelli che `resolve()` restituisce: se il
    dataset a monte cambia, la riga smette di avere effetto invece di
    imporre un nome ormai sbagliato.
    """
    nomi = resolve(codice)
    if not nomi:
        return None
    codice_pulito = (codice or "").strip().upper()

    override = _indice_override_nomi().get(codice_pulito)
    if override and override in nomi:
        return override

    def rango(nome: str) -> tuple:
        ambiguo = codes_for_name(nome) != [codice_pulito]
        cinese = any("一" <= ch <= "鿿" for ch in nome)
        # L'ALFABETO VIENE PRIMA DELL'AMBIGUITA', non dopo.
        #
        # Misurato il 16/08/2026: `ASUS_AI2401_A` usciva come
        # «ROG 游戏手机 8» pur avendo «ROG Phone 8» nello stesso elenco.
        # Il nome cinese vinceva perche' era l'unico non condiviso con un
        # altro codice, e l'ambiguita' veniva valutata per prima.
        #
        # Fra i due criteri, questo e' il piu' forte: un nome condiviso
        # con una variante della stessa famiglia e' un fastidio, un nome
        # in ideogrammi su un'app in italiano non e' leggibile affatto.
        #
        # NON tocca il caso che ha motivato la regola dell'ambiguita'
        # (realme C61 contro C63): li' TUTTI i candidati sono latini,
        # quindi questo termine e' costante e l'ordine ricade
        # sull'ambiguita' esattamente come prima.
        # LA FAMIGLIA PIU' NUMEROSA VIENE PRIMA DELLA LUNGHEZZA.
        #
        # Segnalato dall'utente il 17/08/2026 su `CPH2637`: la pagina
        # diceva «OPPO F27», che è il nome indiano, mentre in Europa quel
        # telefono si chiama «OPPO Reno12 F» — e l'app lo sapeva, tanto da
        # elencarlo fra i gemelli appena sotto. Vinceva solo perché è più
        # corto, e la lunghezza non dice niente su quale nome sia quello
        # giusto qui.
        #
        # Il segnale sta nei dati che abbiamo già: dei cinque nomi noti
        # per quel codice, QUATTRO sono varianti di «Reno12 F» e uno solo
        # è «F27». Un nome di distribuzione larga viene registrato più
        # volte, in più forme, dai cataloghi; la variante di un mercato
        # singolo compare una volta sola. Non è conoscenza dei mercati —
        # che non abbiamo — è il peso dell'evidenza che abbiamo.
        #
        # Resta sotto ai due criteri più forti (il codice travestito da
        # nome, e gli ideogrammi) e sopra la lunghezza, che diventa il
        # criterio di parità dentro la famiglia vincente: fra «Reno12 F»,
        # «Reno12 F 5G» e «Reno12 F/FS 5G» continua a vincere il più
        # corto, che è quello che si legge meglio.
        # ...e passa DAVANTI all'ambiguità solo quando una famiglia domina.
        #
        # L'ambiguità è lì per un bug peggiore («realme C63» che rispondeva
        # «C61», due telefoni diversi), quindi non si scavalca alla
        # leggera. Ma quando quattro nomi su cinque dicono «Reno12 F» e
        # uno solo dice «F27», il dubbio non c'è: quel codice è un Reno12
        # F che in un mercato si chiama diversamente.
        #
        # La soglia (una famiglia di almeno tre nomi, e almeno doppia
        # della seconda) tiene fuori i casi incerti, che restano governati
        # dai criteri di prima: `RMX3939` ha due nomi «C63» contro uno per
        # ciascuno degli altri, ed è troppo poco per decidere così.
        domina = quanti_nella_famiglia(nome) == massimo_famiglia and famiglia_dominante
        return (_e_il_codice(nome, codice_pulito), cinese, not domina, ambiguo,
                len(nome), nome)

    def quanti_nella_famiglia(nome: str) -> int:
        """Quanti degli altri nomi di questo codice sono lo stesso modello.

        Il confronto ignora marca, spazi e maiuscole e guarda se un nome
        è il prefisso dell'altro: «Reno12 F» sta dentro «Reno12 F 5G» e
        «Reno12 FS», non dentro «F27».
        """
        mio = _radice_famiglia(nome)
        if not mio:
            return 1
        return sum(1 for altro in nomi
                   if (r := _radice_famiglia(altro))
                   and (r.startswith(mio) or mio.startswith(r)))

    conteggi = sorted((quanti_nella_famiglia(n) for n in nomi), reverse=True)
    massimo_famiglia = conteggi[0] if conteggi else 0
    secondo = next((c for c in conteggi if c < massimo_famiglia), 0)
    famiglia_dominante = massimo_famiglia >= 3 and massimo_famiglia >= 2 * max(1, secondo)

    scelto = sorted(nomi, key=rango)[0]
    if not any(ch.isalpha() for ch in scelto):
        marca = marca_dichiarata(codice_pulito)
        if marca:
            return _nome_visualizzato(marca, scelto)
    return scelto



# Cifre di un codice -> codici che le contengono. Costruito su richiesta,
# come l'indice inverso dei nomi: serve solo quando una ricerca fallisce.
_per_cifre: dict[str, list[str]] | None = None


def codici_con_le_stesse_cifre(testo: str, limite: int = 5) -> list[str]:
    """Codici noti che hanno le STESSE CIFRE di quello cercato, con un
    prefisso diverso.

    E' l'errore che fa una persona: si ricorda il numero e sbaglia la
    sigla. Segnalato il 16/08/2026 — cercando «cph 3939» il sito
    rispondeva «niente trovato», mentre `RMX3939` (realme C63) e' nei
    cataloghi. Il suggeritore proponeva `CPH2399`, cioe' teneva il
    prefisso sbagliato e storpiava le cifre giuste: confronta le stringhe
    intere, e cosi' la parte che chi cerca ricorda MEGLIO conta meno di
    quella che ricorda peggio.

    Le cifre da sole non bastano a identificare un telefono, quindi
    questa e' una PROPOSTA, non una correzione automatica: chi cerca
    riconosce «realme C63» e capisce di aver sbagliato prefisso.
    """
    global _per_cifre, _memory_cache
    cifre = re.sub(r"[^0-9]", "", testo or "")
    if len(cifre) < 3:
        # Meno di tre cifre combaciano per caso con mezzo catalogo.
        return []
    indice = _memory_cache
    if indice is None:
        indice = _memory_cache = _build_index()
    if _per_cifre is None:
        mappa: dict[str, list[str]] = {}
        for codice in indice:
            solo_cifre = re.sub(r"[^0-9]", "", codice)
            if len(solo_cifre) >= 3:
                mappa.setdefault(solo_cifre, []).append(codice)
        _per_cifre = mappa
    scritto = re.sub(r"[^a-z0-9]", "", (testo or "").lower())
    return [c for c in _per_cifre.get(cifre, [])
            if re.sub(r"[^a-z0-9]", "", c.lower()) != scritto][:limite]


def codici_per_prefisso(prefisso: str, limite: int = 12) -> list[str]:
    """Codici completi che cominciano per `prefisso`.

    Serve per il CODICE INCOMPLETO, che è come le persone lo scrivono
    davvero: chi cerca «a325» intende il Galaxy A32, ma nel dataset non
    esiste `SM-A325` — esistono `SM-A325F`, `SM-A325M`, `SM-A325N`, perché
    l'ultima lettera indica il mercato. Senza questa espansione la ricerca
    non trovava nulla pur avendo il dato a un carattere di distanza.

    Il prefisso deve essere già abbastanza specifico (almeno una lettera e
    tre cifre): su un dataset da 68.000 voci un prefisso corto
    restituirebbe decine di modelli diversi, e la ricerca peggiorerebbe
    invece di migliorare.
    """
    global _memory_cache
    indice = _memory_cache
    if indice is None:
        indice = _memory_cache = _build_index()
    chiave = (prefisso or "").strip().upper()
    if not _RE_PREFISSO_UTILE.match(chiave):
        return []
    trovati = sorted(k for k in indice if k.startswith(chiave) and k != chiave)
    return trovati[:limite]


# Un prefisso utile ha una radice riconoscibile: `SM-A325`, `CPH264`,
# `RMX393`. Sotto questa soglia si pescherebbe nel mucchio.
_RE_PREFISSO_UTILE = re.compile(r"^(?:SM-[A-Z]\d{3}|[A-Z]{2,3}\d{3,4}|[A-Z]\d{3})[A-Z0-9]*$")


# FRA PARENTESI CI PUÒ ESSERE UNA PRECISAZIONE O IL MODELLO STESSO.
#
# La regola nata per «Oppo A6x (CPH2819)» — buttare via tutto ciò che sta
# fra parentesi — cancellava anche il numero di «Nothing Phone (2)», e con
# lui la differenza fra (1), (2), (3a) e (4b): **tutti i telefoni Nothing
# finivano sullo stesso modello**, e cercando «Phone (2)» si otteneva la
# scheda del Phone (1). Vale per CMF e per chiunque altro usi le parentesi
# come numero di gamma.
#
# La distinzione è la lunghezza, e non è un caso: un codice tecnico è lungo
# (`CPH2819`, `SM-A546B`), un numero di gamma è corto (`2`, `2a`, `3a`).
# Sotto i quattro caratteri quello che c'è fra parentesi È il modello.
_RE_PARENTESI_CODICE = re.compile(r"\(\s*[^)]{4,}\s*\)")


def _normalize_name(name: str) -> str:
    """Chiave di confronto tollerante per un nome commerciale: minuscolo,
    senza punteggiatura, spazi normalizzati, senza prefisso di marca
    ('Samsung Galaxy S24 Ultra' e 'Galaxy S24 Ultra' devono combaciare).

    Unisce anche una sigla breve alle cifre che la seguono: «C 63» e «C63»
    sono lo stesso modello, e le persone scrivono in entrambi i modi. Il
    taglio a due lettere è voluto: unire anche parole più lunghe
    trasformerebbe «Note 13» in «Note13», che non corrisponde a nulla.
    Le precisazioni fra parentesi vengono scartate: «Oppo A6x (CPH2819)» e
    «OPPO A6x» sono lo stesso telefono. Serve anche come difesa verso i
    dati già in archivio, dove un nome decorato impediva ogni
    corrispondenza con il catalogo delle fonti ufficiali.
    """
    senza_parentesi = _RE_PARENTESI_CODICE.sub(" ", name or "")
    text = re.sub(r"[^a-z0-9+]+", " ", senza_parentesi.lower()).strip()
    for prefix in ("samsung ", "xiaomi ", "honor ", "huawei ", "motorola ",
                   "oneplus ", "oppo ", "realme ", "vivo ", "google "):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    text = re.sub(r"\b([a-z]{1,2})\s+(\d)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


# Le stesse marche che `_normalize_name` toglie dalla testa del nome.
_MARCHE_NOTE = ("samsung", "xiaomi", "honor", "huawei", "motorola",
                "oneplus", "oppo", "realme", "vivo", "google")


def _prima_la_marca_giusta(nome_cercato: str, codici: list[str]) -> list[str]:
    """Riordina i candidati mettendo davanti quelli della marca nominata
    nella richiesta.

    IL PROBLEMA, MISURATO IL 16/08/2026. `_normalize_name` toglie il
    prefisso della marca — cosa giusta e voluta, senza cui «Samsung
    Galaxy S24» e «Galaxy S24» sarebbero due telefoni diversi (vedi il suo
    docstring e `test_quattro_segnalazioni`). Ma per i marchi il cui nome
    commerciale è *marca + numero* non resta nient'altro: «Xiaomi 14» e
    «realme 14» diventano tutti e due la chiave «14», e finiscono nello
    stesso secchio dell'indice inverso.

    L'effetto era concreto: `codes_for_name("Xiaomi 14")` restituiva
    `RMX5075` come PRIMO candidato, che è un realme. Chi prende il primo
    codice — e i chiamanti fanno così — interrogava le fonti ufficiali
    per il telefono di un'altra marca. Un codice sbagliato è molto peggio
    di nessun codice, come dice il docstring di `codes_for_name` stesso.

    Non si toglie niente dall'elenco, si riordina soltanto: parecchie
    voci di catalogo non ripetono la marca dentro il nome («Galaxy S24»
    non contiene «Samsung»), e scartarle perderebbe codici buoni. Chi
    prende il primo ora prende quello giusto; chi li scorre tutti trova
    le stesse cose di prima.

    La correzione sta QUI e non in `_normalize_name` di proposito: quella
    è usata in una cinquantina di punti fra `sources.py` e `web/main.py`,
    e cambiarne il significato per risolvere un problema dell'indice
    inverso avrebbe spostato il rischio su tutto il resto del progetto.
    """
    testo = (nome_cercato or "").lower()
    marca = next((m for m in _MARCHE_NOTE if testo.startswith(m)), None)
    if not marca or not codici:
        return codici
    combacia, resto = [], []
    # Stessa cautela del resto del modulo: il globale si lega a una locale,
    # così fra il controllo e la lettura nessuno può azzerarlo.
    indice = _memory_cache or {}
    for codice in codici:
        nomi = " ".join(indice.get(codice, [])).lower()
        (combacia if marca in nomi else resto).append(codice)
    return combacia + resto if combacia else codici


def codes_for_name(name: str) -> list[str]:
    """Indice INVERSO: codici tecnici noti per un nome commerciale
    (es. 'Galaxy S24 Ultra' → ['SM-S928B', 'SM-S928U', ...]).

    Serve per interrogare on-demand gli endpoint ufficiali che accettano
    solo il codice modello e non il nome commerciale — in particolare il
    controllo versione Samsung, che con questo indice funziona per
    qualunque modello presente nei dataset invece che solo per quelli di
    una tabella scritta a mano.
    """
    global _reverse_cache, _reverse_senza_suffisso, _reverse_compatto, _memory_cache
    indice = _memory_cache
    if indice is None:
        indice = _memory_cache = _build_index()
    if _reverse_cache is None:
        reverse: dict[str, list[str]] = {}
        senza: dict[str, list[str]] = {}
        compatto: dict[str, list[str]] = {}
        for code, names in indice.items():
            for candidate in names:
                key = _normalize_name(candidate)
                if not key:
                    continue
                bucket = reverse.setdefault(key, [])
                if code not in bucket:
                    bucket.append(code)
                stretta = _compatta(key)
                if stretta:
                    bucket3 = compatto.setdefault(stretta, [])
                    if code not in bucket3:
                        bucket3.append(code)
                ridotta = _senza_suffissi(key)
                if ridotta and ridotta != key:
                    bucket2 = senza.setdefault(ridotta, [])
                    if code not in bucket2:
                        bucket2.append(code)
        _reverse_cache = reverse
        _reverse_senza_suffisso = senza
        _reverse_compatto = compatto

    # I TRE INDICI INVERSI SI LEGGONO IN LOCALI, come l'indice diretto:
    # da qui in giù se ne usano cinque volte, e ognuna era una finestra in
    # cui un azzeramento poteva lasciare `None` sotto un `.get`.
    diretto = _reverse_cache or {}
    compatti = _reverse_compatto or {}
    ridotti = _reverse_senza_suffisso or {}

    chiave = _normalize_name(name)
    trovati = diretto.get(chiave)
    if trovati:
        return _prima_la_marca_giusta(name, trovati)

    # LO SPAZIO FRA LA GAMMA E IL NUMERO NON DISTINGUE NIENTE.
    # Il catalogo scrive «OPPO Reno14», le persone scrivono «oppo reno 14»,
    # ed erano due telefoni diversi: cercando per nome non si arrivava a
    # nessun codice, quindi nessuna fonte ufficiale veniva interrogata,
    # mentre cercando «CPH2737» si otteneva la risposta. Stessa domanda,
    # stesso telefono, due esiti — e quello sbagliato toccava alla forma
    # più naturale.
    #
    # La regola in `_normalize_name` unisce solo sigle di UNA o DUE
    # lettere («C 63» → «c63») perché unire di più avrebbe rotto i nomi in
    # cui lo spazio conta. Qui non si sceglie: si prova anche la forma
    # tutta attaccata, come RIPIEGO, dopo il confronto esatto. Nessun nome
    # che oggi funziona cambia comportamento.
    stretta = _compatta(chiave)
    if stretta:
        trovati = compatti.get(stretta)
        if trovati:
            return _prima_la_marca_giusta(name, trovati)
    # RIPIEGO SUI SUFFISSI COMMERCIALI. Il catalogo scrive «Galaxy A55 5G»,
    # le persone cercano «Galaxy A55»: con il solo confronto esatto quel
    # modello non aveva NESSUN codice, e senza codice il controllo versione
    # Samsung — che è generico e funzionerebbe — non poteva partire. Su
    # sedici nomi comuni ne mancavano tre, tutti per questo motivo.
    #
    # Si tolgono solo le sigle di connettività, mai le sigle di gamma:
    # «Ultra», «Pro», «Plus», «FE» distinguono telefoni diversi e unirli
    # produrrebbe il codice sbagliato, che è molto peggio di nessun codice.
    ridotta = _senza_suffissi(chiave)
    if ridotta and ridotta != chiave:
        trovati = diretto.get(ridotta)
        if trovati:
            return _prima_la_marca_giusta(name, trovati)
        trovati = compatti.get(_compatta(ridotta))
        if trovati:
            return _prima_la_marca_giusta(name, trovati)
    return _prima_la_marca_giusta(
        name, ridotti.get(ridotta or chiave, []))


def _compatta(chiave: str) -> str:
    """Il nome senza spazi: «reno 14» e «reno14» danno la stessa chiave."""
    return re.sub(r"\s+", "", chiave or "")


def reset_cache() -> None:
    """Usato dai test per forzare una nuova build dell'indice."""
    global _memory_cache, _reverse_cache, _per_cifre, _reverse_senza_suffisso, _status
    global _reverse_compatto, _marca_di_codice
    _marca_di_codice = None
    _memory_cache = None
    _reverse_cache = None
    _reverse_senza_suffisso = None
    _reverse_compatto = None
    _per_cifre = None
    _status = {"mobilemodels": "non ancora caricato", "google_play": "non ancora caricato"}
