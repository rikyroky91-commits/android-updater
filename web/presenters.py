"""Dal core alle viste: un solo posto dove i dati diventano testo.

## Perché esiste questo file, e non è una formalità

Nella versione Streamlit la formattazione stava sparsa dentro il codice che
disegnava. Funzionava finché la pagina era una sola. Con un front end vero
le pagine sono sei, e la stessa riga «Galaxy S24 Ultra · Android 16 ·
aggiornato 2 giorni fa» compare in tre di quelle: se ognuna se la
costruisce per conto suo, prima o poi tre pagine dicono tre cose diverse
sullo stesso telefono — ed è già successo in questo progetto, con il chip.

Qui invece i template ricevono **dizionari già pronti**, e non contengono
una sola decisione. Un template che sa quando una data va scritta
«rilevato 3 giorni fa» invece che «10/08/2026» è codice, solo scritto in
un posto dove non si può collaudare.

Nulla in questo file tocca la rete o il database: prende quello che
`core` gli passa e lo rende leggibile. Per questo si collauda da solo.
"""
from __future__ import annotations

import re

from markupsafe import Markup, escape

from core import config as C
from core import soc, specs
from core.classify import qa_impact
from core.util import days_since, fmt_date, fmt_relative, truncate


# ======================================================================
# Stato di un dispositivo
# ======================================================================
# LE TRE PASTIGLIE DEL REDESIGN, con dentro il significato del progetto.
# Il disegno prevede «piena / neutra / contornata»; qui corrispondono a
# «aggiornato di recente / in linea / da guardare», che è la domanda vera
# di chi fa QA: su questo telefono devo rifare i test o no.
FRESCO = ("tag-accent", "Aggiornato")
LINEA = ("tag-neutral", "In linea")
VERIFICA = ("tag-outline", "Da verificare")
FERMO = ("tag-outline", "Fermo")
MAI = ("tag-outline", "Mai visto")


def stato_dispositivo(device: dict) -> dict:
    giorni = days_since(device.get("last_update_at"))
    if giorni is None:
        classe, etichetta = MAI
    elif giorni <= 7:
        classe, etichetta = FRESCO
    elif giorni <= C.FRESH_DAYS:
        classe, etichetta = LINEA
    elif giorni <= C.STALE_DAYS:
        classe, etichetta = VERIFICA
    else:
        classe, etichetta = FERMO
    return {"classe": classe, "etichetta": etichetta, "giorni": giorni}


def data_voce(item: dict, chiave_pubblicazione: str = "published",
              chiave_rilevazione: str = "first_seen") -> str:
    """Distingue la data di USCITA da quella di RILEVAZIONE.

    Alcune fonti — il controllo versione ufficiale Samsung, per dirne una —
    confermano la versione ma non pubblicano una data di rilascio. Scrivere
    lì la data della scansione significherebbe dire quando l'app ha
    guardato spacciandolo per quando l'aggiornamento è uscito.
    """
    if item.get(chiave_pubblicazione):
        return fmt_date(item[chiave_pubblicazione])
    return f"rilevato {fmt_relative(item.get(chiave_rilevazione))}"


def chip_di(riga: dict) -> "soc.Soc | None":
    """Il processore di una riga, provando le tracce dalla più precisa.

    Il codice modello se c'è, poi il numero di build (che per Samsung
    COMINCIA col codice modello: `A325F`XXSCDYB2), infine il nome
    commerciale. **Un solo punto per tutto il sito**, così tabella, scheda
    e ricerca non possono dare risposte diverse sullo stesso telefono —
    che è esattamente il difetto già trovato una volta.
    """
    return soc.per_modello(
        riga.get("model_code") or riga.get("build"),
        riga.get("model") or riga.get("device_model"),
    )


# ======================================================================
# Righe
# ======================================================================
def riga_dispositivo(device: dict, in_parco: bool = False) -> dict:
    chip = chip_di(device)
    stato = stato_dispositivo(device)
    return {
        "chiave": device.get("device_key", ""),
        "brand": device.get("brand", ""),
        "modello": device.get("model", ""),
        "cpu": chip.etichetta if chip else None,
        "cpu_nota": chip.nota if chip else None,
        "sistema": (f"Android {device['android_version']}"
                    if device.get("android_version")
                    else (device.get("os_version") or "")),
        "versione": device.get("os_version") or "",
        "build": device.get("build") or "",
        "patch": device.get("patch_level") or "",
        "aggiornato": fmt_relative(device.get("last_update_at")),
        "update_90g": device.get("updates_90d", 0),
        "stato": stato,
        "in_parco": bool(device.get("watched")) or in_parco,
        "impatto": qa_impact(device.get("severity", ""),
                             bool(device.get("watched"))),
        "link": device.get("link") or "",
    }


def riga_aggiornamento(item: dict) -> dict:
    return {
        "data": data_voce(item),
        "brand": item.get("brand", ""),
        "modello": item.get("device_model") or "—",
        "titolo": truncate(item.get("title", ""), 130),
        "severita": item.get("severity", ""),
        "colore": item.get("color", "#5c5a59"),
        "motivo": item.get("severity_reason", ""),
        "build": item.get("build") or "",
        "patch": item.get("patch_level") or "",
        "versione": item.get("os_version") or "",
        "fonte": item.get("source_label", ""),
        "fiducia": item.get("source_trust", ""),
        "link": item.get("link") or "",
    }


def stato_backup() -> dict:
    """Lo stato del salvataggio esterno (Gist o URL), per la scheda
    Diagnostica.

    Nato da una domanda dell'utente, dopo il fix che avvia un backup
    subito a ogni correzione a mano (`_backup_subito` in `web/main.py`):
    non c'era NESSUN modo di vedere da fuori se il backup fosse davvero
    configurato e funzionante — la pagina Diagnostica elencava fonti e
    cataloghi ma non diceva niente sul backup, che è esattamente
    l'informazione che serve per rispondere «la correzione che ho appena
    salvato sopravviverà al prossimo riavvio?».

    L'ultimo esito porta anche il tipo di operazione che lo ha generato.
    Un ripristino automatico fallito all'avvio non prova che Gist o URL
    siano configurati male: se il successivo ``Salva adesso`` riesce, il
    backup è utilizzabile. Solo il fallimento di un salvataggio viene quindi
    mostrato qui come errore di configurazione.
    """
    from core import backup

    configurato = backup.configurato()
    stato = backup.stato()
    operazione = stato.get("ultima_operazione")
    esito_ok = stato.get("ultima_operazione_ok")
    mai_tentato = (configurato and not operazione
                   and stato.get("ultimo_esito") == "non configurato")

    if not configurato:
        classe, etichetta = "tag-outline", "Non configurato"
    elif operazione == "salvataggio" and esito_ok is False:
        classe, etichetta = "tag-outline", "Errore"
    elif stato.get("ultimo_salvataggio"):
        classe, etichetta = "tag-accent", "Attivo"
    elif operazione == "ripristino" and esito_ok is True:
        classe, etichetta = "tag-accent", "Attivo"
    elif operazione == "ripristino" and esito_ok is False:
        classe, etichetta = "tag-neutral", "Configurato, verifica consigliata"
    elif operazione == "ripristino":
        classe, etichetta = "tag-neutral", "Configurato, pronto a salvare"
    elif mai_tentato:
        classe, etichetta = "tag-neutral", "Configurato, in attesa del primo salvataggio"
    else:
        # Stato di versioni precedenti, senza il tipo dell'operazione: il
        # motivo dell'errore non è deducibile con affidabilità.
        classe, etichetta = "tag-outline", "Errore"

    return {
        "classe": classe,
        "etichetta": etichetta,
        "dettaglio": ("nessun salvataggio o ripristino ancora in questa sessione"
                     if mai_tentato else (stato.get("ultimo_esito") or "—")),
        "ultimo_salvataggio": fmt_relative(stato.get("ultimo_salvataggio")),
        "ultimo_ripristino": fmt_relative(stato.get("ultimo_ripristino")),
    }


def riga_fonte(stato: dict) -> dict:
    degrado = stato.get("degrado")
    if not stato.get("ok"):
        classe, etichetta = "tag-outline", "Errore"
    elif degrado:
        classe, etichetta = "tag-neutral", "Impoverita"
    else:
        classe, etichetta = "tag-accent", "Attiva"
    dettaglio = stato.get("last_error") or (degrado or {}).get("messaggio") or (
        f"{stato.get('items_found', 0)} voci nell'ultima scansione")
    return {
        "nome": stato.get("label", ""),
        "classe": classe,
        "etichetta": etichetta,
        "voci": stato.get("items_found", 0),
        "dettaglio": truncate(dettaglio, 160),
        "controllata": fmt_relative(stato.get("checked_at")),
    }


# ======================================================================
# La marca, per i ripieghi che ne hanno bisogno
# ======================================================================
def marca_probabile(codice: str = "", nome: str = "", aer: dict | None = None) -> str | None:
    """La marca più affidabile che si riesce a determinare per un codice
    modello — o `None` se non si trova, mai una marca indovinata.

    UN SOLO PUNTO DI CALCOLO, usato sia per decidere se la scheda tecnica
    si può cercare su versus.com (`scheda_tecnica`, sotto) sia per proporre
    una forma col marchio nella correzione a mano del nome
    (`web/main.py::_opzioni_correzione`). Prima di essere una funzione a
    parte viveva solo dentro `scheda_tecnica`: separarla evita che le due
    domande — "che marca ha questo codice?" — trovino risposte diverse a
    seconda di chi la fa.

    Bug reale, segnalato dall'utente: cercando «RMX3933» (un codice) o
    «Note 60s» (il nome canonico di quel codice — vedi il docstring di
    `specs._ripiego_esterno`) la scheda tecnica spariva; cercando «realme
    Note 60» — la STESSA identica scheda, stesso codice, stesso telefono —
    appariva. La causa: `specs._ripiego_esterno` (il ripiego su versus.com
    per realme/HONOR/Huawei/Nothing) decide la marca dalla PRIMA PAROLA del
    nome che riceve, e «RMX3933»/«Note 60s» non la scrivono.

    **Primo tentativo — il catalogo AER**: la marca dichiarata dalla fonte
    ufficiale Google (`brand_aer`), non indovinata dal testo.

    **Secondo tentativo — segnalato di nuovo dall'utente**: RMX3933 non è
    nel catalogo AER (non tutti i modelli realme lo sono — è un programma
    Google a cui il produttore aderisce modello per modello), quindi il
    primo tentativo restava vuoto E la scheda restava assente per
    QUALSIASI forma del nome, non solo per quelle senza marca in testa. Il
    rimedio non inventa una marca: `modelcodes.resolve(codice)` è l'elenco
    dei nomi commerciali VERI di quel codice, e fra questi c'è quasi
    sempre una forma che la marca la dichiara (per RMX3933, «NARZO N61» —
    narzo è un sinonimo di realme che `versus.marca_scoperta` riconosce
    anche senza che la parola «realme» compaia da nessuna parte). Prendere
    la marca da lì invece che dal singolo `nome` corrente rende la scheda
    indipendente da QUALE dei nomi veri sia mostrato in quel momento —
    ed è anche il motivo per cui una correzione a mano del nome (vedi
    `web/main.py::_cerca_davvero`) non deve mai "rompere" la scheda.

    `aer`, opzionale: `scheda_tecnica` lo ha già cercato per la foto e le
    patch garantite, e passarlo qui evita di interrogare il catalogo AER
    due volte per la stessa chiamata. Chi non lo ha già (`web/main.py`,
    per la correzione a mano del nome) lo lascia calcolare qui.
    """
    if aer is None:
        from core import aer_catalog
        aer = aer_catalog.lookup(codice) or aer_catalog.lookup(nome)
    marca = (aer or {}).get("brand_aer") or None

    if not marca and codice:
        try:
            from core import modelcodes, versus
            marca = versus.marca_scoperta(*modelcodes.resolve(codice)) or None
        except ImportError:  # pragma: no cover - stessa difesa di specs.py
            pass

    return marca


# ======================================================================
# La scheda tecnica
# ======================================================================

def _domanda_per_la_foto(marca: str, titolo: str) -> str:
    """La stringa con cui si cerca la foto del modello.

    IL DIFETTO, MISURATO IL 16/08/2026. Qui si scriveva
    `f"{marca} {titolo}"`, ma in questo progetto `brand` NON è una marca:
    è la sigla della FAMIGLIA di fonti a cui il telefono appartiene —
    «Vivo / iQOO / Motorola», «Xiaomi / Redmi / POCO», «Huawei / Honor»,
    «Oppo / Realme / OnePlus». La domanda che partiva era quindi

        «Vivo / iQOO / Motorola vivo X90 smartphone»

    e Wikipedia rispondeva **«Android (operating system)»**. Riguardava
    ogni telefono di una famiglia raggruppata, cioè quasi tutti: solo
    Samsung e Pixel hanno una sigla che è davvero una marca.

    La sigla di gruppo si riconosce dalla barra e si toglie: il nome del
    modello contiene già quasi sempre la marca vera («vivo X90», «HONOR
    Magic6 Pro»), e quando non la contiene una ricerca sul solo modello
    è comunque più precisa di una che nomina tre marche di cui due
    sbagliate.
    """
    marca = (marca or "").strip()
    titolo = (titolo or "").strip()
    if "/" in marca:
        return titolo
    return f"{marca} {titolo}".strip()


def scheda_tecnica(nome: str, codice: str = "", brand: str = "",
                   device: dict | None = None) -> dict:
    """Foto, hardware e supporto di un modello, pronti per il template.

    Funziona sia per un modello dell'archivio sia per uno appena cercato:
    a questa funzione basta un nome o un codice. È il motivo per cui la
    scheda «Dispositivi» non può più restare vuota davanti a una ricerca
    andata a buon fine.
    """
    from core import aer_catalog, images

    # Si guarda la scheda curata LOCale senza scaricare il catalogo bulk.
    # Per un IMEI appena riconosciuto questo e' il percorso caldo: basta per
    # Note 50/A16/A05s e non trasforma l'avvio in un picco di RAM. Se manca,
    # si conserva il flusso completo AER -> marca verificata -> ripiego.
    build = (device or {}).get("build") or None
    scheda = (specs._curata_per_codice(codice) if codice else None)
    if scheda is None and nome:
        scheda = specs._curata_per_nome(nome)
    # Le schede curate sono dati completi dentro l'immagine: per un TAC
    # appena riconosciuto non si deve prima attendere il catalogo AER remoto
    # soltanto per provare ad aggiungere una data di supporto. Il catalogo
    # resta il ripiego per le schede non curate e viene gia' preriscaldato.
    aer = None
    if not scheda:
        aer = aer_catalog.lookup(codice) or aer_catalog.lookup(nome)
        # La marca della fonte che ha appena risolto il modello e' piu'
        # precisa di un riscontro AER ottenuto cercando solo un nome corto.
        # Senza questa precedenza ``vivo X200 Pro`` prendeva il codice
        # Samsung SM-X200 (Tab A8): stessa sigla, telefono completamente
        # diverso. Il fallback AER resta utile quando la ricerca non sa la
        # marca, ma non puo' scavalcare un vincolo gia' verificato.
        marca_aer = brand or marca_probabile(codice, nome, aer=aer)
        scheda = specs.cerca(codice or None, nome or None, build, marca=marca_aer)
    else:
        marca_aer = scheda.marca
    chip = soc.per_modello(codice or (device or {}).get("build") or nome,
                           nome or (device or {}).get("model"), marca=marca_aer)

    marca = brand or (scheda.marca if scheda else "") or (device or {}).get("brand", "")
    titolo = (scheda.nome if scheda else nome) or nome

    # ORDINE DELLE FONTI PER LA FOTO, e conta. Prima il catalogo
    # specifiche (è la foto del modello esatto), poi quella ufficiale del
    # produttore nel catalogo aziendale Google, e solo per ultima
    # Wikipedia — che risponde sempre qualcosa e proprio per questo può
    # rispondere il telefono sbagliato.
    foto = (scheda.foto if scheda else None) or (aer or {}).get("image_url")
    if not foto:
        foto = images.find_device_image(_domanda_per_la_foto(marca, titolo))

    voci = []
    if scheda:
        voci = [
            ("Schermo", " · ".join(p for p in (scheda.display_tipo, scheda.display) if p)),
            ("Fotocamera", scheda.camera_post),
            ("Frontale", scheda.camera_front),
            ("Ricarica", scheda.ricarica),
            ("Corpo", " · ".join(p for p in (scheda.dimensioni, scheda.peso) if p)),
            ("Sistema di lancio", scheda.os_lancio),
        ]

    return {
        "trovata": scheda is not None,
        "titolo": titolo,
        "marca": marca,
        "codice": codice,
        "foto": foto,
        "rilascio": scheda.rilascio if scheda else None,
        "cpu": chip.etichetta if chip else None,
        "cpu_nota": chip.nota if chip else None,
        "cpu_fonte": chip.fonte if chip else None,
        "ram": scheda.ram_etichetta if scheda else None,
        "storage": scheda.storage_etichetta if scheda else None,
        "batteria": scheda.batteria if scheda else None,
        "voci": [(k, v) for k, v in voci if v],
        "sezioni": scheda.sezioni if scheda else {},
        "fonte": scheda.fonte if scheda else None,
        "patch_fino_a": fmt_date(aer["security_until"]) if (aer or {}).get(
            "security_until") else None,
        "patch_cadenza": (aer or {}).get("security_frequency"),
        # DETTO, NON TACIUTO. Una scheda vuota sembra un guasto; questa
        # frase dice che è un buco di copertura e quali marche non copre,
        # che per chi fa QA è un'informazione utile.
        #
        # DUE FRASI DIVERSE, NON UNA SOLA. Prima si diceva sempre "specifiche
        # non disponibili" quando mancava `scheda` (RAM/storage/fotocamera,
        # dal catalogo automatico degli 11 brand di `specs.py`) — ANCHE
        # quando `chip` (il processore, dalla tabella curata a mano) era
        # stato trovato. Per un modello HONOR/realme/Huawei/Nothing coperto
        # a mano la pagina mostrava la CPU giusta subito sopra una frase che
        # diceva "non disponibile per questo modello": sembrava una
        # contraddizione, non un buco di copertura parziale.
        #
        # DALLA v49 LA FRASE NON PUÒ PIÙ DIRE «HONOR e realme non ci sono»,
        # perché non è più vero: quelle schede arrivano da versus.com (vedi
        # `core/versus.py`). Resta un buco, ma è un altro — un modello che
        # nessuna delle due fonti ha, tipicamente un tablet o un'uscita
        # regionale — e dirlo con la frase vecchia manderebbe a cercare la
        # causa dalla parte sbagliata.
        "nota_copertura": (
            None if scheda else
            (
                "Scheda tecnica completa (RAM, storage, fotocamera) non "
                "disponibile per questo modello: il processore sopra viene "
                "dalla tabella verificata a mano del progetto. Le schede "
                "arrivano dal catalogo GSMArena e, per HONOR, realme, Huawei "
                "e Nothing, da versus.com; per HONOR si prova anche la pagina "
                "ufficiale italiana. Un modello assente da tutte è di solito "
                "un tablet o una variante venduta in un solo mercato."
                if chip else
                "Specifiche hardware non disponibili per questo modello. Le "
                "schede arrivano dal catalogo GSMArena (Samsung, Xiaomi, OPPO, "
                "OnePlus, vivo, Motorola, Google, Apple, Sony, Nokia), da "
                "versus.com per HONOR, realme, Huawei e Nothing e dalla pagina "
                "HONOR Italia quando disponibile: questo modello non è in nessuna fonte."
            )
        ),
    }


# ======================================================================
# La nota libera di una riga del parco
# ======================================================================
# Un indirizzo intero dentro una tabella la sfonda in larghezza e non si
# legge comunque: quello che serve sapere, guardando la riga, è che una
# nota HA un collegamento, non quale. L'indirizzo resta nel `title`, che
# il browser mostra al passaggio del mouse, e ovviamente nel `href`.
_URL_NELLA_NOTA = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def nota_con_link(testo: str | None) -> Markup:
    """La nota come HTML: il testo scritto a mano, con gli indirizzi
    trasformati in un tasto «Link».

    QUESTA FUNZIONE COSTRUISCE HTML A MANO, quindi è l'unico punto del
    progetto dove l'autoescape di Jinja non lavora per noi: ogni pezzo di
    testo che arriva da fuori passa per `escape()` prima di essere
    concatenato. Una nota che contiene `<script>` deve leggersi come
    `<script>`, non eseguirsi — e la nota la scrive una persona collegata,
    ma «collegata» non vuol dire «di cui fidarsi ciecamente», e comunque
    un domani il parco potrebbe avere più utenti.

    Solo `http://` e `https://` diventano tasti: uno schema come
    `javascript:` in un `href` sarebbe codice che parte al click.
    """
    if not testo or not testo.strip():
        return Markup("")
    pezzi: list[str] = []
    ultimo = 0
    for trovato in _URL_NELLA_NOTA.finditer(testo):
        pezzi.append(str(escape(testo[ultimo:trovato.start()])))
        indirizzo = trovato.group(0)
        # Un punto o una parentesi finale quasi sempre appartengono alla
        # frase, non all'indirizzo: «vedi https://esempio.invalid/a.» non
        # deve produrre un link che finisce con il punto.
        coda = ""
        while indirizzo and indirizzo[-1] in ".,;:)]}":
            coda = indirizzo[-1] + coda
            indirizzo = indirizzo[:-1]
        if indirizzo:
            pezzi.append(
                f'<a class="tasto-link" href="{escape(indirizzo)}" '
                f'title="{escape(indirizzo)}" target="_blank" '
                f'rel="noopener noreferrer">Link</a>'
            )
        pezzi.append(str(escape(coda)))
        ultimo = trovato.end()
    pezzi.append(str(escape(testo[ultimo:])))
    return Markup("".join(pezzi))


# ======================================================================
# La pagina Novità — un feed, non una tabella
# ======================================================================
def voce_feed(item: dict) -> dict:
    """Una notizia di aggiornamento come la si legge in un lettore RSS.

    PERCHÉ NON UNA TABELLA. «Aggiornamenti» era una griglia di sette
    colonne: data, marca, modello, notizia, build, severità, fonte. Una
    tabella risponde bene a «confronta queste righe fra loro», che non è
    la domanda di chi apre la pagina — quella è «cosa è successo, e mi
    riguarda?». Per rispondere serve il TESTO della notizia, che la
    tabella non aveva spazio di mostrare e che infatti non mostrava.

    Il riassunto viene dalla fonte (vedi `summary` in `core/scan.py`), non
    è generato: riassumere a macchina una notizia che si può citare
    testualmente aggiunge un modo di sbagliare senza aggiungere niente.
    Per le righe più vecchie della colonna il campo è vuoto, e allora si
    ripiega su quello che il record sa già dire di sé.
    """
    riassunto = (item.get("summary") or "").strip()
    if not riassunto:
        # RIPIEGO PER LE RIGHE VECCHIE, e per le fonti strutturate che un
        # riassunto non ce l'hanno mai avuto: un controllo versione
        # ufficiale non pubblica un articolo, pubblica una build.
        riassunto = " · ".join(p for p in (
            item.get("size_info") or "",
            item.get("severity_reason") or "",
        ) if p)

    versione = " · ".join(p for p in (
        item.get("os_version") or "",
        f"build {item['build']}" if item.get("build") else "",
        f"patch {item['patch_level']}" if item.get("patch_level") else "",
    ) if p)

    return {
        "titolo": item.get("title", ""),
        "riassunto": truncate(riassunto, 320),
        "modello": item.get("device_model") or "",
        "brand": item.get("brand", ""),
        "versione": versione,
        "quando": data_voce(item),
        "fonte": item.get("source_label", ""),
        "severita": item.get("severity", ""),
        "colore": item.get("color", "#5c5a59"),
        "link": item.get("link") or "",
        "chiave": item.get("device_key") or "",
    }
