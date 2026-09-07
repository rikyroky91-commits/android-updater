"""Utility comuni: gestione date/timezone, formattazione italiana, slug e hash.

Nessuna dipendenza esterna: questo modulo deve restare importabile (e testabile)
anche senza requests / feedparser installati.
"""
from __future__ import annotations

import hashlib
import html
import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timezone


# ------------------------------------------------------------------
# Date & orari (tutto internamente in UTC, ISO 8601 con offset)
# ------------------------------------------------------------------
def _aware(dt: datetime) -> datetime:
    """Rende un datetime timezone-aware in UTC (assume UTC se naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return utcnow().isoformat()


_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%d %b %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


def to_dt(value) -> datetime | None:
    """Converte in datetime UTC qualunque cosa somigli a una data.

    Accetta datetime, timestamp epoch (int/float), struct_time di feedparser
    e le stringhe più comuni restituite dai feed RSS / API.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, (tuple, list)) and len(value) >= 6:
        try:
            return _aware(datetime(*[int(x) for x in value[:6]]))
        except (TypeError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _aware(datetime.fromisoformat(text))
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return _aware(datetime.strptime(text, fmt))
        except ValueError:
            continue
    return None


def iso(value) -> str | None:
    """Normalizza qualunque data in stringa ISO UTC (o None)."""
    dt = to_dt(value)
    return dt.replace(microsecond=0).isoformat() if dt else None


def days_since(value) -> float | None:
    dt = to_dt(value)
    if dt is None:
        return None
    return (utcnow() - dt).total_seconds() / 86400.0


def fmt_dt(value, fmt: str = "%d/%m/%Y %H:%M") -> str:
    dt = to_dt(value)
    return dt.strftime(fmt) if dt else "—"


def fmt_date(value) -> str:
    return fmt_dt(value, "%d/%m/%Y")


def fmt_relative(value) -> str:
    """'3 ore fa', '2 giorni fa', ... in italiano."""
    dt = to_dt(value)
    if dt is None:
        return "mai"
    seconds = (utcnow() - dt).total_seconds()
    if seconds < 0:
        return fmt_dt(value)
    if seconds < 90:
        return "pochi istanti fa"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)} min fa"
    hours = minutes / 60
    if hours < 24:
        n = int(hours)
        return "1 ora fa" if n == 1 else f"{n} ore fa"
    days = hours / 24
    if days < 30:
        n = int(days)
        return "ieri" if n == 1 else f"{n} giorni fa"
    months = days / 30.44
    if months < 12:
        n = max(1, int(months))
        return "1 mese fa" if n == 1 else f"{n} mesi fa"
    years = days / 365.25
    n = max(1, int(years))
    return "1 anno fa" if n == 1 else f"{n} anni fa"


# ------------------------------------------------------------------
# Testo
# ------------------------------------------------------------------
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(text: str, maxlen: int = 70) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = _SLUG_RE.sub("-", text).strip("-")
    return text[:maxlen]


def short_hash(text: str, length: int = 10) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8")).hexdigest()[:length]


def clean_text(text: str) -> str:
    """Rimuove tag HTML residui, decodifica le entità e normalizza gli spazi.

    LE ENTITÀ SI DECODIFICANO TUTTE, non cinque scelte a mano. Qui c'era
    un elenco — `&amp;`, `&#8217;`, `&#8216;`, `&quot;`, `&nbsp;` — e
    bastava che una fonte ne usasse una sesta perché finisse a video così
    com'era. Visto il 16/08/2026 sulla pagina Novità appena fatta:
    «Samsung&#39;s decision to change...», dove `&#39;` è semplicemente un
    apostrofo che non era nell'elenco.

    `html.unescape` le conosce tutte ed è nella libreria standard. Si
    decodifica DOPO aver tolto i tag: così un `&lt;b&gt;` scritto nel
    testo resta testo invece di diventare un tag da rimuovere. Quello che
    esce di qui è testo puro, e i template lo re-inseriscono con
    l'autoescape di Jinja: nessuna via di ritorno verso l'HTML."""
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, limit: int = 120) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def memoria_mb() -> float | None:
    """Quanta RAM sta usando questo processo, adesso, in MB.

    ESISTE PERCHÉ IL DIFETTO ERA INVISIBILE. Il 31/08/2026 l'utente ha
    segnalato che il sito «crasha continuamente per saturamento della
    memoria», e non c'era un solo numero da guardare per capirlo: Render
    riavvia il contenitore e nel registro resta un avvio, non una causa.
    Un contatore che si legge da fuori trasforma «ogni tanto va giù» in
    «alle 14:32 era a 480 MB su 512».

    Si legge da `/proc/self/statm` (seconda colonna: pagine residenti),
    che è la stessa cosa che misura il limite di Render, senza dipendenze
    esterne. Fuori da Linux non esiste, e allora si risponde `None`: un
    numero mancante è meglio di un numero inventato.
    """
    try:
        with open("/proc/self/statm", encoding="ascii") as f:
            pagine = int(f.read().split()[1])
    except Exception:
        return None
    return round(pagine * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024), 1)


def memoria_picco_mb() -> float | None:
    """Il massimo di RAM toccato da questo processo dall'avvio.

    Il picco conta più del valore corrente: un OOM lo provoca l'istante
    peggiore, non la media. `VmHWM` è il numero che il kernel tiene per
    questo — «high water mark» — e non si può azzerare, il che è
    esattamente quello che serve per accorgersi di un picco già passato.
    """
    try:
        with open("/proc/self/status", encoding="ascii") as f:
            for riga in f:
                if riga.startswith("VmHWM:"):
                    return round(int(riga.split()[1]) / 1024, 1)
    except Exception:
        return None
    return None


def _peso_profondo(oggetto, visti: set | None = None) -> int:
    """Byte occupati da una struttura e da tutto ciò che contiene.

    `sys.getsizeof` guarda solo il contenitore: per un dizionario di
    liste di stringhe — la forma che in questo progetto è già costata
    112 MB una volta — risponde il 5% del vero. Qui si scende dentro, una
    volta sola per oggetto (gli identificatori già visti non si contano
    due volte, altrimenti le stringhe condivise gonfierebbero il totale).

    Non è gratis: su ottantamila voci costa qualche decimo di secondo. Per
    questo non sta in `/health`, che l'host interroga ogni minuto, ma
    dietro `?dettaglio=1`.
    """
    import sys

    visti = set() if visti is None else visti
    identificatore = id(oggetto)
    if identificatore in visti:
        return 0
    visti.add(identificatore)
    peso = sys.getsizeof(oggetto)
    # SI MISURA UNA FOTOGRAFIA, NON IL CATALOGO VIVO.
    #
    # I cataloghi si costruiscono in un thread di sottofondo, e questa
    # misura arriva da una richiesta web: percorrere un dizionario mentre
    # qualcun altro ci scrive dentro solleva «dictionary changed size
    # during iteration». Visto in produzione il 02/09/2026 — la riga degli
    # indici inversi tornava `null` proprio mentre venivano riempiti, e un
    # `null` in mezzo ai numeri sembra un guasto invece che una misura
    # arrivata un attimo troppo presto. `list(...)` copia i riferimenti,
    # non i contenuti: costa poco e toglie la corsa.
    if isinstance(oggetto, dict):
        for chiave, valore in list(oggetto.items()):
            peso += _peso_profondo(chiave, visti) + _peso_profondo(valore, visti)
    elif isinstance(oggetto, (list, tuple, set, frozenset)):
        for voce in list(oggetto):
            peso += _peso_profondo(voce, visti)
    return peso


def memoria_dei_cataloghi() -> dict:
    """Quanto pesa ogni catalogo tenuto in memoria, in MB.

    ESISTE PER NON TIRARE A INDOVINARE. Il 01/09/2026, con l'indice TAC
    già ridotto da 165 MB a 22, il servizio in produzione stava a 432 MB
    su 512 e continuava a salire: la causa non era più quella corretta, e
    senza un numero per catalogo l'unica strada era provare a caso.

    I nomi sono quelli che compaiono in Diagnostica, così una riga alta
    qui indica una riga di lì.
    """
    from core import aer_catalog, imeicheck, modelcodes, soc, specs

    strutture = {
        "indice TAC": getattr(imeicheck, "_memory_index", None),
        "codici modello": getattr(modelcodes, "_memory_cache", None),
        "codici, indici inversi": [
            getattr(modelcodes, "_reverse_cache", None),
            getattr(modelcodes, "_reverse_senza_suffisso", None),
            getattr(modelcodes, "_reverse_compatto", None),
            getattr(modelcodes, "_per_cifre", None),
            getattr(modelcodes, "_marca_di_codice", None),
        ],
        "schede tecniche": [getattr(specs, "_schede", None),
                            getattr(specs, "_per_codice", None),
                            getattr(specs, "_per_nome", None),
                            getattr(specs, "_curate_per_codice", None),
                            getattr(specs, "_curate_per_nome", None),
                            getattr(specs, "_honor_specs_cache", None)],
        "processori": [getattr(soc, "_dataset", None),
                       getattr(soc, "_curato", None),
                       getattr(soc, "_play", None)],
        "catalogo aziendale": [getattr(aer_catalog, "_dispositivi", None),
                               getattr(aer_catalog, "_per_nome", None),
                               getattr(aer_catalog, "_per_codice", None)],
    }
    def vuoto(struttura) -> bool:
        """Un catalogo non ancora caricato, che è diverso da uno leggero."""
        if struttura is None:
            return True
        if isinstance(struttura, list):
            return all(pezzo is None or not pezzo for pezzo in struttura)
        return not struttura

    pesi = {}
    for nome, struttura in strutture.items():
        # «NON CARICATO» E «PESA POCO» NON DEVONO LEGGERSI UGUALI. Un
        # catalogo ancora spento rispondeva `0.0`, cioè lo stesso numero di
        # uno caricato e minuscolo: chi legge conclude che quella riga non
        # costa niente, mentre il costo deve ancora arrivare. Visto in
        # produzione il 02/09/2026 su «codici modello», misurato mentre il
        # preriscaldamento non c'era ancora arrivato.
        if vuoto(struttura):
            pesi[nome] = "non ancora caricato"
            continue
        try:
            pesi[nome] = round(_peso_profondo(struttura) / (1024 * 1024), 1)
        except Exception:  # pragma: no cover - una misura non deve rompere nulla
            pesi[nome] = "in costruzione, riprova fra un minuto"
    return pesi



# ======================================================================
# L'ALLEGGERIMENTO AUTOMATICO: non aspettare la scansione per accorgersene
# ======================================================================
# Richiesto dall'utente il 04/09/2026, guardando `/health`: 423 MB usati e
# 457 di picco su 512. «Già a circa 450 MB usati fai un alleggerimento,
# perché secondo me non sono tutti cataloghi: al primo scaricamento sono
# molto meno.»
#
# L'osservazione è giusta e la spiegazione sta già in `libera_memoria` qui
# sotto: `gc.collect()` libera gli oggetti Python ma NON restituisce al
# sistema le arene che li contenevano, quindi ogni ciclo che alloca un po'
# più del precedente alza il pavimento e non lo riabbassa mai. Non è un
# catalogo che cresce: è il pavimento che sale.
#
# `libera_memoria()` c'era già ed è la cura giusta. Il difetto era CHI la
# chiamava: soltanto la scansione (ogni ora), il salvataggio (ogni mezz'ora)
# e un tasto in Diagnostica. Fra due scansioni ci stanno sessanta minuti di
# ricerche, e ogni ricerca è una manciata di richieste HTTP con il loro
# transito. Se il pavimento arriva a 500 in quell'ora, nessuno se ne
# accorge finché il contenitore non viene ucciso.
#
# Da qui in poi il controllo si fa a ogni richiesta servita. Costa la
# lettura di `/proc/self/statm` — un file piccolo, in memoria, niente disco
# — e sotto soglia finisce lì. Sopra soglia si interviene in due tempi:
#
#   1. `libera_memoria()`: restituisce il pavimento. Non perde niente.
#   2. se ancora sopra soglia, si buttano gli indici RICOSTRUIBILI —
#      quelli che si rifanno da soli dai byte già in archivio, senza
#      rete. Costa qualche decimo di secondo alla prossima ricerca che
#      ne ha bisogno, e vale la pena: un indice da rifare è un fastidio,
#      un processo ucciso a metà ricerca è una pagina bianca.
#
# LA SOGLIA È 450 SU 512 E NON PIÙ ALTA di proposito. Il picco misurato è
# 457, cioè il margine vero è già stato consumato una volta: intervenire a
# 480 vorrebbe dire intervenire dopo.
SOGLIA_ALLEGGERIMENTO_MB = 450.0
#: Sotto questo intervallo non si riprova. `malloc_trim` non è gratis e la
#: memoria non cambia in un secondo: senza questa pausa, una raffica di
#: richieste sopra soglia pagherebbe il trim a ognuna.
_PAUSA_ALLEGGERIMENTO_S = 30.0

_lucchetto_memoria = threading.Lock()
_ultimo_tentativo = 0.0
_alleggerimenti = {
    "quanti": 0,
    "restituiti_mb": 0.0,
    "svuotamenti": 0,
    "ultimo": "",
    "quando": "",
}

#: Cache che il livello 2 può buttare, aggiunte da chi le possiede.
#: Serve perché la cache delle ricerche vive in `web/`, e questo modulo
#: non può importarlo — è la regola dichiarata in cima al file, e vale
#: anche quando romperla farebbe comodo.
_da_svuotare: list[tuple[str, object]] = []


def registra_da_svuotare(nome: str, funzione) -> None:
    """Dichiara una cache che l'alleggerimento può buttare via.

    Il contratto è stretto e va rispettato: la funzione deve poter essere
    chiamata in qualunque momento, e ciò che butta deve ricostruirsi da
    solo SENZA rete. Una cache che per tornare deve scaricare qualcosa non
    va registrata qui: la butteremmo proprio quando il processo sta male,
    per poi chiedergli anche un download.
    """
    if not any(n == nome for n, _ in _da_svuotare):
        _da_svuotare.append((nome, funzione))


def soglia_alleggerimento_mb() -> float:
    """La soglia, sovrascrivibile con `MEMORIA_SOGLIA_MB`.

    Si legge da `os.environ` invece che da `core.config` perché questo
    modulo non dipende da nient'altro (vedi il docstring in cima), e
    quella promessa vale più della comodità di una riga.
    """
    grezzo = (os.environ.get("MEMORIA_SOGLIA_MB") or "").strip()
    if not grezzo:
        return SOGLIA_ALLEGGERIMENTO_MB
    try:
        valore = float(grezzo)
    except ValueError:
        return SOGLIA_ALLEGGERIMENTO_MB
    # Zero (o meno) spegne l'alleggerimento automatico: serve ai test e a
    # chi gira su una macchina senza il limite dei 512 MB.
    return valore


def _svuota_ricostruibili() -> list[str]:
    """Butta gli indici che si rifanno da soli, e dice quali.

    NON C'È DENTRO NESSUN CATALOGO CHE PER TORNARE DEVE SCARICARE. Codici
    modello, schede tecniche, processori e catalogo aziendale pesano di
    più e sarebbero la scorciatoia ovvia, ma si ricostruiscono da un
    download: buttarli sotto pressione significa chiedere una connessione
    al processo che sta per essere ucciso. L'indice TAC e le schede di
    confronto invece si rifanno dai byte che stanno già in archivio.
    """
    svuotati: list[str] = []
    try:
        from . import imeicheck
        if getattr(imeicheck, "_memory_index", None):
            imeicheck.libera_indice()
            svuotati.append("indice TAC")
    except Exception:  # pragma: no cover - un alleggerimento non rompe nulla
        pass
    try:
        from . import versus
        if getattr(versus, "_cache", None):
            # Senza `anche_archivio`: si scorda il ricordo in memoria, non
            # quello su disco. Buttare anche quello vorrebbe dire
            # riscaricare le schede, cioè l'esatto contrario.
            versus.reset_cache()
            svuotati.append("schede di confronto")
    except Exception:  # pragma: no cover
        pass
    for nome, funzione in list(_da_svuotare):
        try:
            funzione()
            svuotati.append(nome)
        except Exception:  # pragma: no cover
            continue
    return svuotati


def alleggerisci_se_serve(soglia_mb: float | None = None) -> dict:
    """Controlla la memoria e, se è oltre soglia, la riporta giù.

    Pensata per essere chiamata spessissimo — a ogni richiesta servita —
    quindi il caso normale (sotto soglia) deve costare quanto la lettura
    di un file di `/proc`, e costa quello.

    Ritorna sempre un dizionario che dice cosa è successo, così chi la
    chiama può scriverlo in un registro invece di sperare.
    """
    global _ultimo_tentativo

    prima = memoria_mb()
    if prima is None:
        return {"fatto": False, "motivo": "memoria non misurabile"}
    soglia = soglia_alleggerimento_mb() if soglia_mb is None else float(soglia_mb)
    if soglia <= 0:
        return {"fatto": False, "motivo": "alleggerimento spento", "mb": prima}
    if prima < soglia:
        return {"fatto": False, "mb": prima, "soglia": soglia}

    with _lucchetto_memoria:
        if time.monotonic() - _ultimo_tentativo < _PAUSA_ALLEGGERIMENTO_S:
            return {"fatto": False, "motivo": "appena fatto", "mb": prima}
        _ultimo_tentativo = time.monotonic()

    restituiti = libera_memoria()
    dopo = memoria_mb() or 0.0
    svuotati: list[str] = []
    # SECONDO TEMPO SOLO SE SERVE. Nel caso normale il pavimento scende e
    # gli indici restano dove sono: buttarli comunque significherebbe far
    # pagare a ogni ricerca successiva un problema che non c'è più.
    if dopo >= soglia:
        svuotati = _svuota_ricostruibili()
        restituiti += libera_memoria()
        dopo = memoria_mb() or 0.0

    _alleggerimenti["quanti"] += 1
    _alleggerimenti["restituiti_mb"] = round(
        _alleggerimenti["restituiti_mb"] + restituiti, 1)
    if svuotati:
        _alleggerimenti["svuotamenti"] += 1
    _alleggerimenti["ultimo"] = (
        f"{prima} → {dopo} MB, restituiti {round(restituiti, 1)}"
        + (f", svuotati: {', '.join(svuotati)}" if svuotati else ""))
    _alleggerimenti["quando"] = now_iso()
    return {"fatto": True, "prima": prima, "dopo": dopo,
            "restituiti_mb": round(restituiti, 1), "svuotati": svuotati,
            "soglia": soglia}


def stato_alleggerimento() -> dict:
    """Quante volte è servito e quanto ha reso: per Diagnostica e /health.

    Zero interventi con la memoria alta e zero interventi con la memoria
    bassa sono due situazioni opposte che senza questo contatore si
    leggono uguali.
    """
    stato = dict(_alleggerimenti)
    stato["soglia_mb"] = soglia_alleggerimento_mb()
    return stato


def libera_memoria() -> float:
    """Restituisce al sistema la memoria che Python ha smesso di usare.

    IL PROBLEMA CHE RISOLVE, MISURATO. Il 02/09/2026 l'utente segnala che
    «il sito crasha di notte anche quando nessuno lo usa»: di notte non ci
    sono visite, ma ci sono i lavori periodici — la scansione ogni ora e
    il salvataggio dell'archivio ogni mezz'ora. Provato qui con la stessa
    sequenza del salvataggio (database di 20 MB → gzip → base64 → corpo
    della richiesta):

        picco durante l'invio      43,6 MB
        dopo `del` e `gc.collect`  43,6 MB   ← non torna NIENTE
        dopo `malloc_trim(0)`      10,4 MB

    `gc.collect()` libera gli oggetti Python; non restituisce al sistema
    operativo le arene di memoria che li contenevano. Per il kernel — e
    quindi per il limite dei 512 MB di Render — quel processo continua a
    occupare 43 MB. Ogni ciclo che alloca un po' più del precedente alza
    il pavimento e non lo riabbassa mai: è la scala che porta all'OOM
    nella notte, ed è anche il motivo per cui `memoria_picco_mb` e
    `memoria_mb` sono sempre uguali.

    `malloc_trim` è la chiamata di glibc che quel pavimento lo riabbassa.
    Esiste solo lì: su un sistema che non ce l'ha (musl, macOS, Windows)
    questa funzione fa il `gc.collect()` e torna zero, senza rompere
    niente.

    Ritorna i MB effettivamente tornati al sistema, così chi la chiama può
    scriverlo in un registro invece di sperare.
    """
    import gc

    prima = memoria_mb() or 0.0
    gc.collect()
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        # Nessuna glibc: resta il `gc.collect()` qui sopra, che è comunque
        # la metà utile del lavoro.
        pass
    dopo = memoria_mb() or 0.0
    return round(max(0.0, prima - dopo), 1)
