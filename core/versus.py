"""Scheda tecnica per le marche che il catalogo GSMArena non copre.

## Perché esiste

`core/specs.py` dichiara il proprio perimetro in testa al file: il mirror
JSON di GSMArena contiene dieci cartelle di marca — Samsung, Motorola,
vivo, Nokia, Xiaomi, Oppo, Sony, Apple, OnePlus, Google — e **HONOR,
realme, Huawei e Nothing non ci sono**. Non è una supposizione: contando i
`details.json` dell'archivio scaricato il 2026-08-11 escono 4766 schede
divise fra quelle dieci marche e zero per le altre quattro.

La conseguenza si misurava sulla pagina di un dispositivo. Su otto modelli
realme e HONOR presi dai tracker veri (realme GT 7 Pro, realme C63,
realme 14 Pro+ 5G, realme GT 6, HONOR Magic7 Pro, HONOR 200, HONOR X8c,
HONOR 400 Pro) la scheda tecnica era assente **otto volte su otto**, e su
tre di quegli otto mancava anche il processore, perché l'unica fonte
rimasta era la tabella scritta a mano. Al loro posto l'interfaccia
mostrava la frase di `web/presenters.py` che si scusa per il buco di
copertura. Per i due brand che questo progetto segue con una fonte
ufficiale dedicata — la pagina AER di HONOR (26 modelli) e quella di
realme (6 modelli più 103 codici) — significava sapere a che Android sta
un telefono e non sapere che telefono è.

Questo modulo chiude quel buco, e **solo quello**: per le marche che
GSMArena copre non viene interrogato mai, perché il mirror è una fonte
migliore (si scarica in blocco, è indicizzata per codice modello e
distingue le varianti regionali).

## Che cos'è la fonte

versus.com pubblica, per ogni telefono, una tabella di 180-190
caratteristiche marcata così:

    <tr data-prop="chipset_name"><td class="f">Chipset name (SoC)</td>
                                 <td class="v">Qualcomm Snapdragon 8 Elite</td></tr>

L'attributo `data-prop` è la chiave che rende la pagina utilizzabile da un
programma: è **indipendente dalla lingua** (resta `chipset_name` sia in
italiano sia in inglese), mentre l'etichetta accanto è tradotta. Si legge
quello, non il testo.

Le righe sono raggruppate in capitoli (`<details class="chap"
id="chap-design">`), e i valori booleani non sono testo ma una classe:
`<span class="bool y">` / `<span class="bool n">`.

## Tre decisioni che non sono di gusto

1. **Si scarica la versione inglese** (`/en/`), non quella italiana, e non
   per preferenza linguistica: gli stessi valori escono come `1.024GB` e
   `5.850 mAh` in italiano e `1,024GB` e `5,850 mAh` in inglese. In
   italiano il punto è separatore delle migliaia, e un parser che lo legge
   come decimale trasforma un terabyte in un giga. In inglese il punto è
   sempre e solo il decimale. Le sezioni complete restano in inglese come
   quelle di GSMArena, che l'interfaccia mostra già così.

2. **Un nome che non combacia non vale una scheda.** È l'errore ricorrente
   di questo progetto — cercare «realme c63» e ricevere la scheda del C61 —
   e qui la ricerca di versus lo offre su un piatto: interrogandola con i
   26 nomi veri del tracker HONOR risponde «Honor 400 Smart 5G» a chi ha
   chiesto «HONOR 400», e con quelli realme risponde «Realme 14 Pro» a chi
   ha chiesto «realme 14 Pro+ 5G». Sono telefoni diversi con chip diversi.
   `risolvi` accetta solo la corrispondenza esatta della chiave compatta;
   il suffisso di connettività (4G/5G) si può togliere, ma **solo se resta
   un candidato solo** — la stessa identica regola che `specs.per_nome`
   applica già al catalogo GSMArena, e per lo stesso motivo: «Realme 13 4G»
   e «Realme 13 5G» sono due telefoni, e sceglierne uno è indovinare.

3. **Anche il buco si mette in cache.** Un modello che versus non ha —
   HONOR X6d 5G e i tablet della pagina AER, misurati — costerebbe due
   richieste HTTP a ogni apertura di pagina se il «non trovato» non venisse
   ricordato. Si ricorda, ma per meno tempo di una scheda trovata (una
   settimana contro trenta giorni): un telefono uscito ieri domani c'è.

Nessun dato di questo modulo entra in archivio come aggiornamento e
nessuno tocca `android_version`: versus è un catalogo di hardware, non una
fonte di firmware, e la versione Android che pubblica è quella di lancio.
Attribuire a un telefono una versione presa da qui sarebbe ripetere
l'errore di HONOR X8c descritto in `core/sources.py`. Per questo
`DATA_LOGIC_VERSION` non cambia.
"""
from __future__ import annotations

import html as H
import json
import re
import threading
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import config as C

RICERCA_URL = "https://versus.com/api/search"
SCHEDA_URL = "https://versus.com/en/{slug}"
# La ricerca pubblica il percorso dell'immagine senza host
# («/honor-magic-7-pro.front.variety.….jpg»): l'host è quello che la
# pagina stessa usa in `og:image`, verificato, non dedotto dal dominio.
IMMAGINI_BASE = "https://images.versus.io/objects"
FONTE_LABEL = "versus.com"

# Quanto vale un ricordo. Una scheda hardware non cambia mai dopo l'uscita
# del telefono; un «non trovato» invece scade, perché il catalogo cresce.
_TTL_TROVATA_ORE = 24 * 30
_TTL_MANCANTE_ORE = 24 * 7
_BLOB_CACHE = "versus_schede_json"

# Una pagina prodotto vera pesa 450-480 kB. Sotto questa soglia è una
# pagina di errore o un redirect, e provare a leggerne la tabella
# produrrebbe una scheda vuota indistinguibile da un modello senza dati.
_DIMENSIONE_MINIMA = 50_000

_lock = threading.RLock()
_cache: dict[str, dict] | None = None
_status = "non ancora interrogato"


# ======================================================================
# Le marche di competenza
# ======================================================================
# La marca del tracker NON basta a decidere: `C.OPPO` vale «Oppo / Realme /
# OnePlus», e di quei tre GSMArena copre i primi due. La discriminante è
# come si chiama il modello, non in che cassetto sta.
_MARCHE_SCOPERTE = (
    ("realme", "Realme"),
    ("narzo", "Realme"),      # realme vende il NARZO senza mai scrivere «realme»
    ("honor", "Honor"),
    ("huawei", "Huawei"),
    ("nothing", "Nothing"),
)


def marca_scoperta(*testi: str | None) -> str | None:
    """La marca da usare su versus, o None se il catalogo GSMArena la copre.

    Si guarda l'inizio del nome e non una parola qualsiasi dentro il testo:
    «Galaxy S24 confrontato con HONOR 200» parla di un Samsung.
    """
    for testo in testi:
        parole = re.sub(r"[^a-z0-9 ]+", " ", (testo or "").lower()).split()
        if not parole:
            continue
        for prefisso, marca in _MARCHE_SCOPERTE:
            if parole[0] == prefisso:
                return marca
    return None


# ======================================================================
# Chiavi di confronto fra nomi
# ======================================================================
# «HONOR Magic7 Pro» (come lo scrive la pagina AER) e «Honor Magic 7 Pro»
# (come lo scrive versus) sono lo stesso telefono: la chiave toglie gli
# spazi del tutto, cosa che `modelcodes._normalize_name` non fa perché lì
# servono a distinguere altro.
#
# Il «+» diventa «plus» perché le due fonti lo scrivono in modo diverso e
# in modo sistematico: realme pubblica «realme 13+», versus «Realme 13
# Plus 5G». Senza questa riga il modello non si troverebbe mai.
_RE_PARENTESI = re.compile(r"\(.*?\)")
_RE_NON_UTILE = re.compile(r"[^a-z0-9]+")
# «(256GB / 12GB RAM)», «128GB», «6GB RAM»: sono confezioni dello stesso
# telefono, non telefoni diversi. versus ne pubblica una pagina per taglio.
_RE_VARIANTE = re.compile(
    r"\s*(?:\(\s*\d+\s*[GT]B\s*(?:/\s*\d+\s*[GT]B\s*RAM\s*)?\)"
    r"|\b\d+\s*[GT]B(?:\s+RAM)?)\s*$", re.I)
# Suffisso di connettività: lo stesso elenco di `specs._SUFFISSI_CONNETTIVITA`.
_RE_CONNETTIVITA = re.compile(r"\s*\b(?:4G|5G|LTE)\b\s*$", re.I)


def chiave(nome: str) -> str:
    """«Honor Magic 7 Pro» e «HONOR Magic7 Pro» → `honormagic7pro`."""
    testo = _RE_PARENTESI.sub(" ", nome or "").lower().replace("+", " plus ")
    return _RE_NON_UTILE.sub("", testo)


def senza_variante(nome: str) -> str:
    """Toglie il taglio di memoria dalla coda, anche ripetuto."""
    precedente = None
    testo = (nome or "").strip()
    while testo != precedente:
        precedente = testo
        testo = _RE_VARIANTE.sub("", testo).strip()
    return testo


def senza_connettivita(nome: str) -> str:
    return _RE_CONNETTIVITA.sub("", senza_variante(nome)).strip()


def con_marca(nome: str, marca: str) -> str:
    """«NARZO 70 5G» → «Realme NARZO 70 5G».

    Serve perché versus mette sempre la marca nel nome e le fonti
    ufficiali no: la pagina realme elenca il NARZO senza mai scrivere
    «realme», e senza questo la chiave non combacerebbe mai.
    """
    testo = " ".join((nome or "").split())
    if not testo:
        return marca
    if chiave(testo).startswith(chiave(marca)):
        return testo
    return f"{marca} {testo}"


# ======================================================================
# Rete
# ======================================================================
def _scarica(url: str, parametri: dict | None = None):
    """L'UNICA porta verso la rete di questo modulo.

    È una funzione sola e non tre chiamate sparse per la stessa ragione per
    cui `specs._scarica` e `soc._scarica_dataset` lo sono: `tests/
    test_niente_rete.py` blocca il socket e pretende che ogni fonte abbia
    un aggancio sostituibile. Una fonte con due porte d'ingresso è una
    fonte che quel test non riesce a fermare.
    """
    if requests is None:  # pragma: no cover
        return None
    try:
        risposta = requests.get(url, params=parametri, timeout=C.HTTP_TIMEOUT + 10,
                                headers={"User-Agent": C.USER_AGENT})
    except Exception:
        return None
    if getattr(risposta, "status_code", 0) != 200:
        return None
    return risposta


# ======================================================================
# Dal nome allo slug
# ======================================================================
def scegli_candidato(nome_completo: str, risultati: list[dict],
                     marca: str) -> dict | None:
    """Il risultato di ricerca che è DAVVERO quel telefono, o None.

    Separata dalla rete perché i test possano girare su una risposta vera
    registrata invece che su quello che il server risponde oggi.

    Due passaggi, il secondo più permissivo del primo ma mai ambiguo:

    1. la chiave compatta combacia — tolta la confezione (`128GB`) e le
       precisazioni fra parentesi, che non fanno un telefono diverso;
    2. combacia dopo aver tolto anche il suffisso 4G/5G, **e sopravvive un
       solo telefono**. Se ne sopravvivono due — «Realme 13 4G» e «Realme
       13 5G» per chi ha cercato «realme 13» — non si sceglie: sono due
       modelli con chip diversi e prenderne uno a caso è la radice del
       guasto che questo modulo ha il compito di non ripetere.
    """
    atteso = chiave(nome_completo)
    atteso_nudo = chiave(senza_connettivita(nome_completo))
    if not atteso:
        return None

    ammessi = []
    for riga in risultati or []:
        nome = (riga or {}).get("name") or ""
        if "phone" not in ((riga or {}).get("categories") or []):
            continue
        if not chiave(nome).startswith(chiave(marca)):
            continue
        ammessi.append(riga)

    def preferito(righe: list[dict]) -> dict:
        # A parità di telefono si prende la pagina del modello base invece
        # di quella di un taglio di memoria: la prima elenca il telefono,
        # la seconda una confezione.
        return sorted(righe, key=lambda r: (
            senza_variante(r.get("name") or "") != (r.get("name") or ""),
            len(r.get("name") or ""),
        ))[0]

    esatti = [r for r in ammessi
              if chiave(senza_variante(r.get("name") or "")) == atteso]
    if esatti:
        return preferito(esatti)

    nudi = [r for r in ammessi
            if chiave(senza_connettivita(r.get("name") or "")) == atteso_nudo]
    if not nudi:
        return None
    distinti = {chiave(senza_variante(r.get("name") or "")) for r in nudi}
    if len(distinti) != 1:
        return None
    return preferito(nudi)


def risolvi(nome: str, marca: str) -> dict | None:
    """Nome commerciale → il risultato di ricerca di versus, o None.

    Si interroga più volte perché le due fonti scrivono lo stesso telefono
    in modi che la ricerca testuale non riconcilia da sola: realme lo
    chiama «realme 13+», versus «Realme 13 Plus 5G», e la pagina ufficiale
    realme unisce i nomi regionali con una barra («realme 13 4G/12 4G»).
    Ogni tentativo passa comunque dal filtro di `scegli_candidato`: provare
    più chiavi allarga cosa si trova, non cosa si accetta.
    """
    completo = con_marca(nome, marca)
    tentativi = [completo]
    if "+" in completo:
        tentativi.append(completo.replace("+", " Plus"))
    if "/" in completo:
        tentativi.append(con_marca(completo.split("/")[0], marca))
    for tentativo in tentativi:
        risposta = _scarica(RICERCA_URL, {"q": tentativo})
        if risposta is None:
            continue
        try:
            risultati = risposta.json()
        except ValueError:
            continue
        if not isinstance(risultati, list):
            continue
        scelto = scegli_candidato(completo, risultati, marca)
        if scelto:
            return scelto
    return None


# ======================================================================
# Dalla pagina alla scheda
# ======================================================================
_RE_CAPITOLO = re.compile(
    r'<details[^>]*class="chap"[^>]*>(.*?)</details>', re.S | re.I)
_RE_TITOLO_CAPITOLO = re.compile(r'<span class="cname">(.*?)</span>', re.S | re.I)
_RE_RIGA = re.compile(
    r'<tr[^>]*data-prop="([^"]*)"[^>]*>\s*<td class="f">(.*?)</td>'
    r'\s*<td class="v">(.*?)</td>', re.S | re.I)
_RE_BOOL = re.compile(r'class="bool\s+([yn])\b', re.I)
_RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
_RE_OG_IMAGE = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.I)
# Il numero iniziale del titolo di capitolo («1. Design») è la posizione
# nella pagina, non parte del nome della sezione.
_RE_NUMERO_CAPITOLO = re.compile(r"^\s*\d+\.\s*")


def testo(frammento: str) -> str:
    """Frammento di HTML → testo piano, entità comprese."""
    ripulito = re.sub(r"<[^>]+>", " ", frammento or "")
    return " ".join(H.unescape(ripulito).split())


def valore(cella: str) -> str:
    """Il contenuto di `<td class="v">`, booleani compresi.

    Un booleano non è testo: è `<span class="bool y">`. Leggerlo con
    `testo()` renderebbe stringa vuota, e in interfaccia «ha l'NFC» e «non
    si sa se ha l'NFC» diventerebbero la stessa cosa.
    """
    piano = testo(cella)
    if piano:
        return piano
    trovato = _RE_BOOL.search(cella or "")
    if trovato:
        return "sì" if trovato.group(1).lower() == "y" else "no"
    return ""


def leggi_pagina(pagina: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """La pagina di un prodotto → (valori per `data-prop`, sezioni).

    Due strutture dagli stessi dati e non una: `data-prop` è la chiave
    stabile con cui si riempiono i campi della scheda, i capitoli con le
    etichette tradotte sono quello che si mostra a chi guarda.
    """
    proprieta: dict[str, str] = {}
    sezioni: dict[str, dict[str, str]] = {}
    for corpo in _RE_CAPITOLO.findall(pagina or ""):
        trovato = _RE_TITOLO_CAPITOLO.search(corpo)
        titolo = _RE_NUMERO_CAPITOLO.sub("", testo(trovato.group(1)) if trovato else "")
        campi: dict[str, str] = {}
        for prop, etichetta, cella in _RE_RIGA.findall(corpo):
            letto = valore(cella)
            if not letto:
                continue
            proprieta.setdefault(prop, letto)
            campi[testo(etichetta)] = letto
        if titolo and campi:
            sezioni[titolo] = campi
    return proprieta, sezioni


_RE_NUMERO = re.compile(r"(\d+(?:\.\d+)?)")


def _numero(grezzo: str | None) -> float | None:
    """`"1,024GB"` → 1024.0. La virgola è separatore delle migliaia nella
    pagina inglese (vedi la nota in testa al file): va tolta prima di
    leggere il numero, non interpretata."""
    if not grezzo:
        return None
    trovato = _RE_NUMERO.search(str(grezzo).replace(",", ""))
    return float(trovato.group(1)) if trovato else None


def _gigabyte(grezzo: str | None) -> tuple[int, ...]:
    valore_letto = _numero(grezzo)
    if valore_letto is None or valore_letto <= 0:
        return ()
    # `\bTB\b` NON funziona qui: in «1TB» fra la cifra e la T non c'è
    # nessun confine di parola, e il taglio da un terabyte veniva letto
    # come un giga.
    if re.search(r"TB\b", grezzo or "", re.I):
        valore_letto *= 1024
    return (int(round(valore_letto)),)


def _zoom(grezzo: str | None) -> str | None:
    """«3x» → «zoom ottico 3x»; «0x» → niente.

    versus scrive `0x` quando lo zoom ottico non c'è. Riportarlo alla
    lettera mette «zoom ottico 0x» nella riga della fotocamera di ogni
    telefono economico: una caratteristica assente scritta come se fosse
    un dato.
    """
    if not grezzo or _numero(grezzo) in (None, 0):
        return None
    return f"zoom ottico {grezzo}"


def _unisci(*pezzi: str | None, separatore: str = " · ") -> str | None:
    presenti = [p.strip() for p in pezzi if p and p.strip()]
    return separatore.join(presenti) or None


def costruisci_scheda(nome_versus: str, pagina: str, marca_tracker: str,
                      foto: str | None = None) -> dict | None:
    """Pagina scaricata → la stessa forma che produce `specs.leggi_scheda`.

    Si riusa quella forma invece di inventarne una: l'interfaccia, il
    presenter e `soc._soc_da_specifiche` sanno già leggerla, e una seconda
    struttura per lo stesso dato vorrebbe dire due percorsi da tenere
    allineati per sempre.
    """
    proprieta, sezioni = leggi_pagina(pagina)
    if not proprieta:
        return None

    trovato = _RE_H1.search(pagina or "")
    # IL TAGLIO DI MEMORIA NON STA NEL NOME. Di alcuni modelli versus non
    # pubblica la pagina base ma solo quelle delle confezioni: di «Realme
    # 14 Pro» esistono solo `…-256gb-8gb-ram` e `…-256gb-12gb-ram`.
    # Tenendo il titolo come sta, la pagina del dispositivo si
    # intitolerebbe «Realme 14 Pro (256GB / 8GB RAM)» — un altro nome
    # rispetto a quello che usa il tracker, quindi in apparenza un altro
    # telefono. Il taglio non si perde: resta in `memoria`, dove è un dato
    # e non un'identità.
    nome = senza_variante(testo(trovato.group(1)) if trovato else nome_versus)
    if not nome:
        return None

    if not foto:
        immagine = _RE_OG_IMAGE.search(pagina or "")
        foto = immagine.group(1) if immagine else None

    archiviazione = proprieta.get("internal_storage")
    ram = proprieta.get("ram")
    dimensioni = _unisci(proprieta.get("height"), proprieta.get("width"),
                         proprieta.get("thickness"), separatore=" x ")

    return {
        "nome": nome,
        "marca": marca_tracker,
        "foto": foto,
        # versus non pubblica i codici modello: l'indice per codice resta
        # quello di GSMArena. Dichiararlo vuoto è corretto, riempirlo con
        # qualcosa di simile a un codice no.
        "codici": [],
        "rilascio": proprieta.get("release_date"),
        "chipset": proprieta.get("chipset_name"),
        "cpu": _unisci(proprieta.get("total_clock_speed"),
                       proprieta.get("cpu_threads")),
        "gpu": proprieta.get("gpu_name"),
        "ram_gb": list(_gigabyte(ram)),
        "storage_gb": list(_gigabyte(archiviazione)),
        "memoria": _unisci(archiviazione, f"{ram} RAM" if ram else None,
                           separatore=" "),
        "display": _unisci(proprieta.get("screen_size"),
                           proprieta.get("resolution")),
        "display_tipo": _unisci(proprieta.get("mobile_display_tech"),
                                proprieta.get("refresh_rate")),
        "batteria": proprieta.get("battery_power"),
        "ricarica": _unisci(proprieta.get("charging_speed"),
                            "ricarica wireless"
                            if proprieta.get("cable_less") == "sì" else None),
        # La fotocamera posteriore sta sotto `megapixels` — senza prefisso,
        # a differenza di `front_camera_megapixel`. Letto dalla pagina vera
        # del realme C63: leggere il nome che sembra simmetrico avrebbe
        # lasciato la riga «Fotocamera» con il solo zoom dentro.
        "camera_post": _unisci(proprieta.get("megapixels"),
                               _zoom(proprieta.get("optical_zoom"))),
        "camera_front": proprieta.get("front_camera_megapixel"),
        # «Sistema di lancio», come il campo omonimo di GSMArena: versus
        # pubblica la versione con cui il telefono è uscito, non quella che
        # ha oggi. Nessuna parte del progetto la usa come `android_version`.
        "os_lancio": proprieta.get("android_version"),
        "peso": proprieta.get("weight"),
        "dimensioni": f"{dimensioni} mm" if dimensioni else None,
        "sezioni_json": (json.dumps(sezioni, ensure_ascii=False,
                                    separators=(",", ":")) if sezioni else ""),
        "fonte": FONTE_LABEL,
    }


# ======================================================================
# Cache
# ======================================================================
def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scaduta(voce: dict) -> bool:
    try:
        eta = (datetime.now(timezone.utc)
               - datetime.fromisoformat(voce.get("quando") or "")).total_seconds() / 3600
    except ValueError:
        return True
    limite = _TTL_TROVATA_ORE if voce.get("riga") else _TTL_MANCANTE_ORE
    return eta >= limite


def _leggi_cache() -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache
    letta: dict[str, dict] = {}
    try:
        from . import storage
        grezzo = storage.get_blob(_BLOB_CACHE)
        if grezzo:
            caricata = json.loads(grezzo.decode("utf-8"))
            if isinstance(caricata, dict):
                letta = caricata
    except Exception:
        # Una cache illeggibile fa ripartire da zero: costa qualche
        # richiesta in più, non una pagina in meno.
        letta = {}
    _cache = letta
    return _cache


def _scrivi_cache() -> None:
    try:
        from . import storage
        storage.set_blob(_BLOB_CACHE,
                         json.dumps(_cache or {}, ensure_ascii=False).encode("utf-8"))
    except Exception:
        pass


def reset_cache(anche_archivio: bool = False) -> None:
    """Azzera il ricordo in memoria; con `anche_archivio` pure quello su disco.

    I due livelli sono separati perché servono a cose diverse: scordare la
    memoria basta per rileggere il blob, scordare anche il blob serve a
    ripartire davvero da zero — che è quello che vuole un test, dove una
    scheda lasciata lì dal caso precedente passerebbe per una scheda
    appena scaricata.
    """
    global _cache, _status
    with _lock:
        _cache = None
        _status = "non ancora interrogato"
        if anche_archivio:
            try:
                from . import storage
                storage.set_blob(_BLOB_CACHE, b"{}")
            except Exception:
                pass


def status() -> str:
    return _status


# ======================================================================
# La porta d'ingresso
# ======================================================================
def scheda_grezza(nome: str, marca_tracker: str = "") -> dict | None:
    """La scheda di un modello realme/HONOR/Huawei/Nothing, o None.

    Restituisce la stessa forma di `specs.leggi_scheda`, pronta per
    `specs._a_scheda`. Non solleva mai: una fonte esterna che non risponde
    deve togliere una sezione dalla pagina, non farla fallire.
    """
    global _status
    marca = marca_scoperta(nome)
    if not marca:
        return None

    chiave_cache = chiave(con_marca(nome, marca))
    if not chiave_cache:
        return None

    with _lock:
        cache = _leggi_cache()
        voce = cache.get(chiave_cache)
        if voce and not _scaduta(voce):
            _status = f"{len(cache)} modelli ricordati (da archivio)"
            return voce.get("riga")

    try:
        scelto = risolvi(nome, marca)
        riga = None
        if scelto:
            slug = (scelto.get("name_url") or "").strip("/")
            risposta = _scarica(SCHEDA_URL.format(slug=slug)) if slug else None
            pagina = getattr(risposta, "text", "") if risposta is not None else ""
            if len(pagina) >= _DIMENSIONE_MINIMA:
                immagine = scelto.get("image") or ""
                riga = costruisci_scheda(
                    scelto.get("name") or nome, pagina,
                    marca_tracker or C.OTHER,
                    foto=f"{IMMAGINI_BASE}{immagine}" if immagine else None,
                )
    except Exception as errore:  # pragma: no cover - rete imprevedibile
        _status = f"non disponibile: {errore}"
        return None

    with _lock:
        cache = _leggi_cache()
        cache[chiave_cache] = {"quando": _adesso(), "riga": riga}
        _scrivi_cache()
        trovate = sum(1 for v in cache.values() if v.get("riga"))
        _status = f"{trovate} schede su {len(cache)} modelli chiesti"
    return riga
