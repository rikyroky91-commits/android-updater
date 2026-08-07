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

_memory_cache: dict[str, list[str]] | None = None
# Indice inverso nome commerciale -> codici tecnici, costruito su richiesta
# a partire da `_memory_cache` (vedi codes_for_name).
_reverse_cache: dict[str, list[str]] | None = None
_reverse_senza_suffisso: dict[str, list[str]] | None = None

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
    cached_hex = storage.get_meta(bytes_meta_key)
    if cached_hex and fetched_at:
        try:
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
        except ValueError:
            age_h = _REFRESH_HOURS + 1
        if age_h < _REFRESH_HOURS:
            _status[source_key] = f"da cache (aggiornata {age_h:.0f}h fa)"
            return bytes.fromhex(cached_hex)

    fresh = _download(url, source_key)
    if fresh:
        storage.set_meta(bytes_meta_key, fresh.hex())
        storage.set_meta(fetched_meta_key, datetime.now(timezone.utc).isoformat())
        return fresh
    if cached_hex:
        _status[source_key] += " — uso la cache precedente (non aggiornatissima)"
        return bytes.fromhex(cached_hex)
    _status[source_key] += " — nessuna cache precedente disponibile"
    return None


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
            _add_names(index, row.get("model") or "", row.get("model_name") or "")
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
            display = f"{brand} {marketing}".strip()
            if not display:
                continue
            _add_names(index, row.get("Device") or "", display)
            _add_names(index, row.get("Model") or "", display)
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
    """
    global _memory_cache
    _memory_cache = dict(indice)


def _build_index() -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for code, names in _build_mobilemodels_index().items():
        for name in names:
            _add_names(merged, code, name)
    for code, names in _build_google_play_index().items():
        for name in names:
            _add_names(merged, code, name)
    return merged


def resolve(code: str) -> list[str]:
    """Nomi commerciali noti per un codice modello (es. 'RMX3939' →
    ['realme C61 Global', 'realme C63', 'realme C65s', 'realme NARZO N63']),
    combinando entrambi i dataset. Lista vuota se il codice non è in nessuno
    dei due — probabilmente perché il testo passato non è affatto un codice
    tecnico, ma già un nome per esteso. Usa `status()` per sapere se i
    database si sono anche solo caricati.
    """
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = _build_index()
    return _memory_cache.get((code or "").strip().upper(), [])


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
    if _memory_cache is None:
        _memory_cache = _build_index()
    chiave = (prefisso or "").strip().upper()
    if not _RE_PREFISSO_UTILE.match(chiave):
        return []
    trovati = sorted(k for k in _memory_cache if k.startswith(chiave) and k != chiave)
    return trovati[:limite]


# Un prefisso utile ha una radice riconoscibile: `SM-A325`, `CPH264`,
# `RMX393`. Sotto questa soglia si pescherebbe nel mucchio.
_RE_PREFISSO_UTILE = re.compile(r"^(?:SM-[A-Z]\d{3}|[A-Z]{2,3}\d{3,4}|[A-Z]\d{3})[A-Z0-9]*$")


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
    senza_parentesi = re.sub(r"\([^)]*\)", " ", name or "")
    text = re.sub(r"[^a-z0-9+]+", " ", senza_parentesi.lower()).strip()
    for prefix in ("samsung ", "xiaomi ", "honor ", "huawei ", "motorola ",
                   "oneplus ", "oppo ", "realme ", "vivo ", "google "):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    text = re.sub(r"\b([a-z]{1,2})\s+(\d)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def codes_for_name(name: str) -> list[str]:
    """Indice INVERSO: codici tecnici noti per un nome commerciale
    (es. 'Galaxy S24 Ultra' → ['SM-S928B', 'SM-S928U', ...]).

    Serve per interrogare on-demand gli endpoint ufficiali che accettano
    solo il codice modello e non il nome commerciale — in particolare il
    controllo versione Samsung, che con questo indice funziona per
    qualunque modello presente nei dataset invece che solo per quelli di
    una tabella scritta a mano.
    """
    global _reverse_cache, _reverse_senza_suffisso, _memory_cache
    if _memory_cache is None:
        _memory_cache = _build_index()
    if _reverse_cache is None:
        reverse: dict[str, list[str]] = {}
        senza: dict[str, list[str]] = {}
        for code, names in _memory_cache.items():
            for candidate in names:
                key = _normalize_name(candidate)
                if not key:
                    continue
                bucket = reverse.setdefault(key, [])
                if code not in bucket:
                    bucket.append(code)
                ridotta = _senza_suffissi(key)
                if ridotta and ridotta != key:
                    bucket2 = senza.setdefault(ridotta, [])
                    if code not in bucket2:
                        bucket2.append(code)
        _reverse_cache = reverse
        _reverse_senza_suffisso = senza

    chiave = _normalize_name(name)
    trovati = _reverse_cache.get(chiave)
    if trovati:
        return trovati
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
        trovati = _reverse_cache.get(ridotta)
        if trovati:
            return trovati
    return (_reverse_senza_suffisso or {}).get(ridotta or chiave, [])


def reset_cache() -> None:
    """Usato dai test per forzare una nuova build dell'indice."""
    global _memory_cache, _reverse_cache, _reverse_senza_suffisso, _status
    _memory_cache = None
    _reverse_cache = None
    _reverse_senza_suffisso = None
    _status = {"mobilemodels": "non ancora caricato", "google_play": "non ancora caricato"}
