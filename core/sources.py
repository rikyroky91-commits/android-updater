"""Sorgenti dati.

Ogni sorgente espone una funzione `fetch()` che restituisce `(items, error)`:
un errore su una fonte non blocca mai le altre, viene solo registrato nello
stato fonti e mostrato nella diagnostica.

Le fonti sono ordinate per affidabilità decrescente:

* **structured** – dati ufficiali/strutturati (immagini OTA Pixel, tracker
  firmware Xiaomi): device, build e versione arrivano già separati, non serve
  interpretare linguaggio naturale.
* **curated** – feed dedicati agli aggiornamenti (SamMobile, HuaweiCentral,
  PiunikaWeb): filtro morbido.
* **noisy** – ricerche generiche su Google News: filtro rigido.

Le fonti extra si possono aggiungere senza toccare il codice, con la variabile
d'ambiente `EXTRA_FEEDS` (vedi in fondo al file).
"""
from __future__ import annotations

import gzip

import html
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Callable

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from . import aer_catalog
from . import config as C
from . import extract
from . import modelcodes
from . import motorola_catalog
from . import oplus_arb
from . import oppo_official
from . import storage
from . import telegram_tracker
from .util import clean_text, iso

try:  # dipendenze opzionali: il core resta importabile senza rete
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    import feedparser
except ImportError:  # pragma: no cover
    feedparser = None


# ======================================================================
# Modello dei dati grezzi
# ======================================================================
@dataclass
class RawItem:
    title: str
    link: str = ""
    published: str | None = None
    brand: str | None = None
    device: str | None = None          # modello, se la fonte lo fornisce già
    # Codice modello ESATTO a cui si riferisce questo dato, quando la fonte
    # lo conosce (`SM-S921B`, `CPH2737`). È la differenza fra «il Galaxy
    # S24» e «quel Galaxy S24»: due varianti dello stesso nome montano chip
    # diversi e ricevono build diverse, quindi senza il codice la risposta
    # sul chip non può che essere «una delle due».
    #
    # NON entra in `text`, di proposito: gli estrattori rileggono quel
    # testo, e un codice modello ha la forma di un numero di build.
    model_code: str | None = None
    version: str | None = None         # versione/etichetta fornita dalla fonte
    build: str | None = None
    android_version: int | None = None
    size_gb: float = 0.0
    size_info: str = ""
    summary: str = ""
    # Livello di fiducia dichiarato dalla fonte che ha prodotto l'item.
    # `None` significa «quello predefinito del chiamante».
    trust: str | None = None
    # Non confondere attendibilità e semantica: una fonte può essere
    # ufficiale e dire soltanto la versione di fabbrica. Solo CURRENT può
    # diventare la risposta «ultimo firmware stabile».
    firmware_kind: str | None = None

    @property
    def text(self) -> str:
        """Testo su cui girano estrazione e filtri."""
        parts = [self.title, self.version or "", self.build or "", self.summary]
        return " ".join(p for p in parts if p)


@dataclass
class Source:
    key: str
    label: str
    trust: str
    fetch: Callable[[], tuple[list[RawItem], str | None]]
    brand: str | None = None
    homepage: str = ""
    notes: str = ""
    # True solo per le ricerche generiche su Google News (fallback per i
    # brand senza fonte dedicata): a differenza di un feed editoriale come
    # 9to5Google o GSMArena, qui un articolo senza un modello riconosciuto
    # non è collegabile a nessun device, quindi va scartato a prescindere
    # dal punteggio testuale (vedi scan.normalize).
    is_web_search: bool = False
    # current / factory / support / beta / reported. Le fonti registrate
    # ricevono il valore dalla mappa sotto; questo campo serve alle ricerche
    # dirette, che hanno una semantica propria.
    firmware_kind: str = C.FW_REPORTED


# Una chiave sorgente non può descrivere da sola la qualità del dato.
# Questa mappa resta intenzionalmente piccola e verificabile: ciò che non è
# esplicitamente un firmware corrente è solo una segnalazione o metadato.
_FIRMWARE_KIND_BY_SOURCE = {
    "apple_devices": C.FW_CURRENT,
    "xiaomi_tracker": C.FW_CURRENT,
    "samsung_fus": C.FW_CURRENT,
    "motorola_lolinet": C.FW_CURRENT,
    "oppo_official": C.FW_CURRENT,
    "oplus_arb": C.FW_CURRENT,
    "oplus_telegram": C.FW_CURRENT,
    "pixel_ota": C.FW_BETA,
    "oppo_aer": C.FW_SUPPORT,
    "aer_catalog": C.FW_SUPPORT,
    "realme_aer": C.FW_FACTORY,
    "honor_aer": C.FW_FACTORY,
    "honor_security": C.FW_SUPPORT,
    "vivo_aer": C.FW_FACTORY,
}


def firmware_kind_for(source: Source) -> str:
    """Semantica effettiva del dato, senza promuovere i default a firmware."""
    return _FIRMWARE_KIND_BY_SOURCE.get(source.key, source.firmware_kind)


# ======================================================================
# Helper HTTP
# ======================================================================
def _headers() -> dict:
    return {"User-Agent": C.USER_AGENT, "Accept": "*/*"}


def http_get(url: str, timeout: int | None = None, headers: dict | None = None):
    """GET con gli header del progetto, sovrascrivibili per singola fonte.

    Il parametro `headers` esiste per l'endpoint FOTA di Samsung, che
    rifiuta gli User-Agent da browser: vedi `_fota_get`.
    """
    if requests is None:  # pragma: no cover
        raise RuntimeError("la libreria 'requests' non è installata")
    intestazioni = _headers()
    if headers:
        intestazioni.update(headers)
    return requests.get(url, timeout=timeout or C.HTTP_TIMEOUT, headers=intestazioni)


# Header che l'endpoint FOTA si aspetta. NON è un capriccio: è il client
# ufficiale Samsung (Kies) che quel server serve, e con uno User-Agent da
# browser risponde 403 o restituisce corpi che non si riescono a leggere.
#
# È LA RADICE DEL GUASTO SAMSUNG. Il controllo versione veniva chiamato
# con lo User-Agent generico del progetto: ogni region falliva in
# silenzio (`except: continue`) e la ricerca finiva per rispondere con
# una fonte di ripiego — la versione di fabbrica o una notizia vecchia.
# Da fuori sembrava che il modello non fosse coperto; in realtà non gli
# veniva mai chiesto niente.
FOTA_USER_AGENT = "Kies2.0_FUS"


def _fota_get(url: str, timeout: int | None = None) -> str | None:
    """Testo XML da `fota-cloud-dn`, o None se la region non risponde.

    Oltre allo User-Agent, gestisce la compressione: il server può
    restituire gzip senza dichiararlo negli header, e in quel caso
    `response.text` è un blocco binario in cui la ricerca del numero di
    build non trova nulla — un altro modo silenzioso di non funzionare.
    """
    try:
        response = http_get(url, timeout=timeout,
                            headers={"User-Agent": FOTA_USER_AGENT})
    except Exception:
        return None
    if getattr(response, "status_code", 0) != 200:
        return None

    testo = getattr(response, "text", "") or ""
    if "<" in testo:
        return testo

    # Nessun tag: probabile gzip non dichiarato.
    dati = getattr(response, "content", None)
    if not dati:
        return testo or None
    try:
        return gzip.decompress(dati).decode("utf-8", "replace")
    except Exception:
        return testo or None


def fetch_json(urls: list[str]) -> tuple[object | None, str | None]:
    """Prova più URL candidati e restituisce il primo JSON valido.

    Serve perché le fonti community cambiano branch o percorso senza preavviso:
    con una sola URL cablata, un rename del branch spegne la fonte.
    """
    last_error = "nessun URL candidato"
    for url in urls:
        try:
            response = http_get(url)
        except Exception as exc:
            last_error = f"{url} → connessione fallita: {exc}"
            continue
        if response.status_code != 200:
            last_error = f"{url} → HTTP {response.status_code}"
            continue
        try:
            return response.json(), None
        except ValueError:
            last_error = f"{url} → risposta non JSON: {response.text[:60]!r}"
    return None, last_error


def fetch_yaml(urls: list[str]) -> tuple[object | None, str | None]:
    """Come `fetch_json`, ma per fonti che pubblicano YAML invece di JSON."""
    if yaml is None:  # pragma: no cover
        return None, "la libreria 'pyyaml' non è installata"
    last_error = "nessun URL candidato"
    for url in urls:
        try:
            response = http_get(url, timeout=C.HTTP_TIMEOUT + 15)  # file grande
        except Exception as exc:
            last_error = f"{url} → connessione fallita: {exc}"
            continue
        if response.status_code != 200:
            last_error = f"{url} → HTTP {response.status_code}"
            continue
        try:
            return yaml.safe_load(response.text), None
        except yaml.YAMLError as exc:
            last_error = f"{url} → YAML non valido: {exc}"
    return None, last_error


def fetch_feed(urls: list[str], timeout: int | None = None):
    """Primo feed RSS/Atom che contiene almeno una voce.

    Il download passa da `requests` (già usato per le fonti JSON, con lo
    stesso timeout/header) invece che dal client HTTP interno di feedparser:
    su alcuni siti quest'ultimo fallisce la verifica TLS anche quando lo
    stesso URL scaricato con `requests` funziona senza problemi.
    """
    if feedparser is None:  # pragma: no cover
        return None, "la libreria 'feedparser' non è installata"
    last_error = "nessun URL candidato"
    for url in urls:
        try:
            response = http_get(url, timeout=timeout)
        except Exception as exc:
            last_error = f"{url} → connessione fallita: {exc}"
            continue
        if response.status_code != 200:
            last_error = f"{url} → HTTP {response.status_code}"
            continue
        parsed = feedparser.parse(response.content)
        if getattr(parsed, "entries", None):
            return parsed, None
        last_error = f"{url} → {getattr(parsed, 'bozo_exception', 'feed vuoto')}"
    return None, last_error


def _entry_date(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return iso(tuple(value))
    for key in ("published", "updated", "date"):
        value = entry.get(key)
        if value:
            parsed = iso(value)
            if parsed:
                return parsed
    return None


def rss_items(urls: list[str], brand: str | None, size_info: str, limit: int | None = None,
              timeout: int | None = None):
    parsed, error = fetch_feed(urls, timeout=timeout)
    if parsed is None:
        return [], error
    items = []
    for entry in parsed.entries[: limit or C.MAX_ITEMS_PER_SOURCE]:
        title = clean_text(entry.get("title", ""))
        if not title:
            continue
        items.append(
            RawItem(
                title=title,
                link=entry.get("link", ""),
                published=_entry_date(entry),
                brand=brand,
                size_info=size_info,
                summary=clean_text(entry.get("summary", ""))[:400],
            )
        )
    return items, None


def _pick(data: dict, *keys, default=None):
    """Primo valore non vuoto fra chiavi alternative (schemi API instabili)."""
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return value
    return default


def _size_to_gb(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) / (1024 ** 3) if value > 10000 else float(value)
    match = re.search(r"([\d.,]+)\s*(GB|MB|G|M)\b", str(value), re.IGNORECASE)
    if not match:
        return 0.0
    number = float(match.group(1).replace(",", "."))
    return number if match.group(2).upper().startswith("G") else number / 1024


# ======================================================================
# 1. Xiaomi — MIUI/HyperOS Updates Tracker (YAML strutturato)
# ======================================================================
# Il progetto è passato da JSON a YAML (vedi il loro README: "Starting from
# V3 the script provides an all-in-one YAML file"). Lo schema di ogni voce è:
# android, branch, codename, date, link, md5, method, name, size, version.
XIAOMI_YAML_URLS = [
    "https://raw.githubusercontent.com/XiaomiFirmwareUpdater/miui-updates-tracker/master/data/latest.yml",
]
# Vecchi URL JSON: tenuti come ultimo tentativo nel caso il progetto torni
# indietro o pubblichi di nuovo un JSON in futuro.
XIAOMI_JSON_URLS = [
    "https://raw.githubusercontent.com/XiaomiFirmwareUpdater/miui-updates-tracker/main/data/latest.json",
]


# LA CACHE A TEMPO, non solo per lo storico Xiaomi qui sotto ma per tutte
# le fonti UFFICIALI interrogate «a comando» (Xiaomi, Honor, Vivo, Oppo
# AER): a differenza della scansione periodica, `_lookup_structured_for`
# le richiama a ogni singola ricerca, per rispondere anche su un modello
# che il giro periodico non ha ancora visto. Senza una cache qui, due
# ricerche diverse sullo STESSO brand — due modelli Xiaomi cercati a un
# minuto di distanza — riscaricano e rianalizzano l'intero catalogo due
# volte: per Xiaomi è lo storico COMPLETO dal 2015, migliaia di righe di
# YAML. `RICERCHE` (`web/cache.py`) evita di ripetere la STESSA ricerca,
# ma non aiuta quando cambia il modello e resta il brand — che è il caso
# comune. Su un host da 512 MB, dove l'applicazione è già stata riavviata
# d'ufficio per memoria (lo dice lo stesso `web/cache.py`), è la
# differenza fra reggere una raffica di ricerche e non reggerla.
class _CacheDiFonte:
    """Un solo valore, con scadenza. Non è keyed: qui il valore è sempre
    «l'intero catalogo di questa fonte», non una risposta per domanda."""

    # OGNI CACHE SI ISCRIVE DA SOLA, così `azzera_cache_fonti` non è un
    # elenco scritto a mano che invecchia alla prima fonte aggiunta.
    #
    # Il motivo è un errore ripetuto tre volte in due giorni: aggiungere
    # una cache a una fonte fa fallire i test che sostituiscono `http_get`
    # o che spengono la rete, perché quelli continuano a leggere il valore
    # lasciato da un test precedente — e falliscono affermando l'opposto di
    # ciò che verificano. È successo con Honor (che la cache ce l'aveva già
    # e nessuno l'azzerava), poi con realme e poi con Pixel appena gliene è
    # stata data una.
    _tutte: list = []

    def __init__(self, ttl_secondi: float) -> None:
        self.ttl = ttl_secondi
        self.valore = None
        self.scaricato_a: float | None = None
        _CacheDiFonte._tutte.append(self)
        # SERIALIZZA CHI SCARICA, non chi legge. Da quando le fonti si
        # scaldano in parallelo (`_scalda_fonti`), la stessa fonte può
        # essere chiesta insieme dal thread che scalda e dal giro di
        # ricerca: senza questo la scaricherebbero tutti e due, cioè il
        # doppio delle richieste proprio nel momento in cui si sta cercando
        # di farne meno. Chi arriva secondo aspetta il primo e trova la
        # cache già scritta.
        self._lock = threading.Lock()

    def fresca(self) -> bool:
        return (self.valore is not None and self.scaricato_a is not None
                and (time.monotonic() - self.scaricato_a) < self.ttl)

    def scrivi(self, valore) -> None:
        self.valore = valore
        self.scaricato_a = time.monotonic()

    def azzera(self) -> None:
        with self._lock:
            self.valore = None
            self.scaricato_a = None

    def ottieni(self, scarica, forza: bool = False):
        """Il valore in cache, scaricandolo se serve. **Una volta sola.**

        Raccoglie la regola che le sei fonti con cache ripetevano identica,
        compresa quella che conta di più e che è facile scordare: **un
        guasto non si mette in cache**. Tenerlo significherebbe rispondere
        «fonte irraggiungibile» per un'ora dopo un singolo errore di rete
        passeggero, quando il tentativo successivo sarebbe riuscito.
        """
        if self.fresca() and not forza:
            return self.valore
        with self._lock:
            # Ricontrollato DENTRO il lock: mentre si aspettava, chi stava
            # davanti può avere già scaricato.
            if self.fresca() and not forza:
                return self.valore
            valore = scarica()
            if valore[1] is None:
                self.scrivi(valore)
            return valore


# Il tracker Xiaomi pubblica più volte al giorno: 20 minuti, come il
# canale Telegram OPlus, tengono la risposta fresca senza riscaricare lo
# storico completo a ogni ricerca.
_XIAOMI_TTL_SECONDI = 20 * 60
_xiaomi_cache = _CacheDiFonte(_XIAOMI_TTL_SECONDI)


def azzera_cache_fonti() -> None:
    """Azzera **tutte** le cache di fonte, presenti e future.

    Da chiamare in ogni test che sostituisce `http_get` o che spegne la
    rete: una fonte che risponde dalla cache mentre la rete è giù sta
    dichiarando come fresco un dato che non lo è, e un test che la
    interroga in quello stato misura il test precedente, non il proprio.

    Le singole `reset_*_cache` restano per i test che vogliono azzerare una
    fonte sola senza toccare le altre.
    """
    # PRIMA si aspettano i riscaldamenti in volo, POI si azzera. Al
    # contrario, un thread partito prima riscriverebbe la cache subito dopo
    # averla svuotata — vedi `attendi_riscaldamenti`.
    attendi_riscaldamenti()
    for cache in _CacheDiFonte._tutte:
        cache.azzera()
    # LE DUE CACHE CHE NON SONO `_CacheDiFonte`. Il tracker ARB e il canale
    # Telegram tengono il proprio stato in variabili di modulo, scritte
    # prima che questa classe esistesse. Non elencarle qui rendeva la
    # funzione bugiarda proprio dove serve di più: con la rete spenta
    # `oplus_arb` continuava a rispondere con 53 voci lasciate da un test
    # precedente, e la scansione dichiarava quella fonte «OK».
    reset_arb_cache()
    reset_telegram_cache()
    reset_realme_firmware_cache()


def reset_xiaomi_cache() -> None:
    """Azzera la cache del catalogo Xiaomi (usata dai test)."""
    _xiaomi_cache.azzera()


def fetch_xiaomi(forza: bool = False) -> tuple[list[RawItem], str | None]:
    return _xiaomi_cache.ottieni(_fetch_xiaomi_scarica, forza)


def _fetch_xiaomi_scarica() -> tuple[list[RawItem], str | None]:
    data, error = fetch_yaml(XIAOMI_YAML_URLS)
    if not isinstance(data, list):
        data, json_error = fetch_json(XIAOMI_JSON_URLS)
        if not isinstance(data, list):
            return [], error or json_error or "nessuna fonte disponibile"

    # Il file pubblica lo storico COMPLETO di ogni codename dal 2015 a oggi
    # (migliaia di righe), non ordinato globalmente per data (ogni codename
    # è in ordine cronologico al suo interno, ma i codename sono intrecciati
    # in ordine di append, non di data). Tagliare le prime N righe come
    # arrivano dal file prende quindi uno spaccato quasi arbitrario — spesso
    # i device più vecchi in testa — invece delle build più recenti.
    # Si deduplica per device tenendo solo la release più recente di
    # ciascuno, poi si ordina per data: così un modello reale ma poco
    # aggiornato di recente (es. Redmi 12) resta comunque nel catalogo
    # invece di sparire perché tagliato fuori da un limite pensato per un
    # feed di notizie, non per un catalogo di ~1300 device distinti.
    latest_by_device: dict[str, dict] = {}
    for record in data:
        if not isinstance(record, dict):
            continue
        device = clean_text(_pick(record, "name", "device", "codename", default=""))
        if not device:
            continue
        published = iso(_pick(record, "date", "release_date", "updated"))
        current = latest_by_device.get(device)
        if current is None or (published or "") > (current.get("_published") or ""):
            record = dict(record)
            record["_published"] = published
            latest_by_device[device] = record

    ordered = sorted(latest_by_device.items(), key=lambda kv: kv[1].get("_published") or "", reverse=True)

    items = []
    for device, record in ordered[: C.XIAOMI_MAX_DEVICES]:
        version = clean_text(_pick(record, "version", "versionName", default=""))
        android = _pick(record, "android", "android_version")
        try:
            android_version = int(str(android).split(".")[0]) if android else None
        except ValueError:
            android_version = None
        size_gb = _size_to_gb(_pick(record, "size", "filesize"))
        branch = clean_text(_pick(record, "branch", "type", default="Stable"))
        method = clean_text(_pick(record, "method", default=""))
        size_label = f"{branch} {method}".strip() or "Stable ROM"
        items.append(
            RawItem(
                title=f"{device} — {branch} {version}".strip(),
                link=_pick(record, "download", "link", "url", default=""),
                published=record.get("_published"),
                brand=C.XIAOMI,
                device=device,
                version=version or None,
                build=version or None,
                android_version=android_version,
                size_gb=size_gb,
                size_info=size_label + (f" · {size_gb:.1f} GB" if size_gb else ""),
            )
        )
    return items, None


# ======================================================================
# 2. Google Pixel — pagina ufficiale delle immagini OTA
# ======================================================================
# ATTENZIONE MANUTENZIONE: la vecchia pagina unica developers.google.com/
# android/ota ora carica la tabella per-dispositivo via JavaScript lato
# client, quindi una richiesta HTTP semplice non vede più righe (Google ha
# ristrutturato il sito nel 2026). Le nuove pagine per singola release sono
# invece statiche, ma sono organizzate per versione/QPR (es. .../16/qpr2/
# download-ota) e il numero di versione va aggiornato quando Google rilascia
# una nuova major/QPR. La lista qui sotto va scorsa e ampliata di tanto in
# tanto con la versione più recente in testa.
PIXEL_OTA_URLS = [
    "https://developer.android.com/about/versions/17/download-ota",
    "https://developer.android.com/about/versions/16/qpr3/download-ota",
    "https://developer.android.com/about/versions/16/qpr2/download-ota",
    "https://developer.android.com/about/versions/16/download-ota",
    "https://developers.google.com/android/ota",  # tenuta come ultimo tentativo
]
_PIXEL_DEVICE_RE = re.compile(
    r"\bPixel\s+(?:10(?:\s+Pro(?:\s+(?:XL|Fold))?)?|9(?:a|\s+Pro(?:\s+(?:XL|Fold))?)?|"
    r"8(?:a|\s+Pro)?|7(?:a|\s+Pro)?|6(?:a|\s+Pro)?|Fold|Tablet)\b"
)
_PIXEL_FILENAME_RE = re.compile(r"\b[a-z][a-z0-9]+_beta-ota-([\w.]+?)-[0-9a-f]{6,}\.zip\b")
_PIXEL_RELEASE_DATE_RE = re.compile(
    r"Release date\**\s*[|:]\s*\**\s*([A-Za-z]+ \d{1,2},\s*\d{4})"
)
_PIXEL_PATCH_RE = re.compile(r"Security patch level\**\s*[|:]\s*\**\s*([\d-]{7,10})")
_PIXEL_VERSION_FROM_URL_RE = re.compile(r"/versions/(\d+)")


# LA FONTE PIÙ COSTOSA DELLA RICERCA, ED ERA L'UNICA «BASSO COSTO» SENZA
# CACHE. Misurato l'11/08/2026 con un cronometro su ogni fonte, a cache
# fredde: cercando «c63» — un realme, niente a che vedere con i Pixel —
# questa fonte da sola consumava **6,9 dei 12 secondi** di budget, in
# cinque chiamate. Cinque perché `lookup_model_structured` interroga ogni
# fonte con TUTTE le forme equivalenti della ricerca, e senza cache ognuna
# riscaricava le pagine di Android Developers da capo.
#
# È lo stesso difetto trovato sulla pagina realme il giorno prima, e ha lo
# stesso rimedio. Qui pesa di più per due motivi che si moltiplicano: le
# pagine sono grandi, e `PIXEL_OTA_URLS` ne prova fino a cinque in fila
# finché una non risponde con delle righe — quindi il caso peggiore è
# cinque forme × cinque pagine.
#
# Il TTL è lo stesso delle altre pagine ufficiali (un'ora, come
# `_AER_TTL_SECONDI`, che però è definito più sotto insieme alla fonte
# Honor): Google pubblica un'immagine OTA al massimo una volta al mese.
_PIXEL_TTL_SECONDI = 60 * 60
_pixel_ota_cache = _CacheDiFonte(_PIXEL_TTL_SECONDI)


def reset_pixel_ota_cache() -> None:
    """Azzera la cache delle immagini OTA Pixel (usata dai test)."""
    _pixel_ota_cache.azzera()


def fetch_pixel_ota(forza: bool = False) -> tuple[list[RawItem], str | None]:
    return _pixel_ota_cache.ottieni(_fetch_pixel_ota_scarica, forza)


def _fetch_pixel_ota_scarica() -> tuple[list[RawItem], str | None]:
    """Estrae, per ogni Pixel, l'ultima immagine OTA pubblicata su una delle
    pagine per-release di Android Developers (vedi nota di manutenzione sopra).

    Dispositivo e file vengono associati per **posizione** nella tabella
    (stesso ordine in cui compaiono), non tramite una mappa nome-in-codice →
    modello: così un nuovo codename mai visto prima (è già successo con
    Pixel 10) non rompe l'estrazione.
    """
    last_error = "nessun URL candidato"
    for url in PIXEL_OTA_URLS:
        try:
            response = http_get(url, timeout=C.HTTP_TIMEOUT + 10)
        except Exception as exc:
            last_error = f"{url} → connessione fallita: {exc}"
            continue
        if response.status_code != 200:
            last_error = f"{url} → HTTP {response.status_code}"
            continue

        html = response.text
        # findall con un solo gruppo di cattura ritorna solo il gruppo, non il
        # match intero: per i nomi dispositivo (nessun gruppo) basta findall.
        device_names = [f"Pixel {m}" if not m.startswith("Pixel") else m
                        for m in re.findall(_PIXEL_DEVICE_RE.pattern, html)]
        builds = [m.group(1) for m in _PIXEL_FILENAME_RE.finditer(html)]

        if not device_names or not builds:
            last_error = f"{url} → pagina raggiungibile ma nessuna riga dispositivo/build trovata"
            continue

        date_match = _PIXEL_RELEASE_DATE_RE.search(html)
        published = iso(date_match.group(1)) if date_match else None
        version_match = _PIXEL_VERSION_FROM_URL_RE.search(url)
        android_version = int(version_match.group(1)) if version_match else None

        # Le due liste dovrebbero avere la stessa lunghezza (una riga = un
        # dispositivo + un file); se non combaciano ci si ferma al più corto
        # invece di associare righe sbagliate.
        pairs = list(zip(device_names, builds))
        if not pairs:
            last_error = f"{url} → dispositivi e build non allineati"
            continue

        items = []
        seen = set()
        for device, build in pairs:
            if device in seen:  # "Pixel 6" può comparire più volte nel testo
                continue
            seen.add(device)
            items.append(
                RawItem(
                    # QUESTE PAGINE SERVONO IMMAGINI BETA, TUTTE. Verificato
                    # il 2026-08-03: `/versions/17/`, `/16/qpr3/` e `/16/`
                    # contengono solo file `*_beta-ota-*`, e la regex dei
                    # nomi file lo pretende pure. La pagina delle immagini
                    # stabili (developers.google.com/android/ota) è resa in
                    # JavaScript e a una richiesta semplice risponde con
                    # zero righe.
                    #
                    # Finché non si trova una fonte stabile, questa va detta
                    # per quello che è. Prima dichiarava «Pixel 9 Pro —
                    # Android 17», cioè un'anteprima spacciata per la
                    # versione del telefono: la parola «beta» nel titolo fa
                    # sì che il classificatore la marchi BETA, e quindi che
                    # resti fuori dalle notifiche automatiche.
                    title=f"{device} — immagine OTA beta · build {build}",
                    link=url,
                    published=published,
                    brand=C.PIXEL,
                    device=device,
                    # Niente `version`/`android_version`: sono la versione
                    # dell'ANTEPRIMA, non quella installata. Scriverla qui
                    # la farebbe diventare la versione del dispositivo nella
                    # vista per modello. Resta leggibile in `size_info`, che
                    # non passa dagli estrattori.
                    build=build,
                    firmware_kind=C.FW_BETA,
                    size_info=(
                        "Immagine OTA canale Beta"
                        + (f" · anteprima Android {android_version}" if android_version else "")
                    ),
                )
            )
        if items:
            return items, None
        last_error = f"{url} → nessun dispositivo estratto dopo la deduplica"
    return [], last_error


# ======================================================================
# 3. Oppo / OnePlus / realme — API news di OxygenUpdater (JSON vero)
# ======================================================================
OXYGEN_URLS = [
    "https://oxygenupdater.com/api/v2.7/news",
    "https://oxygenupdater.com/api/v2.6/news",
]


# ======================================================================
# 3b. Oppo / OnePlus / realme — API ufficiale OxygenUpdater (v2.10)
# ======================================================================
# ACCESSO — LEGGERE PRIMA DI TOCCARE QUESTA FONTE.
# L'endpoint filtra sullo User-Agent e risponde 403 a qualunque client che
# non si dichiari l'app OxygenUpdater (verificato: 403 con il nostro UA,
# 200 solo con "Oxygen_updater_*"). È un controllo d'accesso deliberato di
# chi gestisce il servizio, non un ostacolo tecnico da aggirare.
#
# Questo codice NON invia l'UA dell'app. Si identifica per quello che è
# (vedi OXYGEN_USER_AGENT in config.py), quindi finché i manutentori non
# mettono in whitelist quell'UA questa fonte risponde 403 e resta inattiva.
# È il comportamento voluto: l'integrazione è pronta, l'autorizzazione no.
#
# Per attivarla quando l'accordo sarà formalizzato: valorizzare la variabile
# d'ambiente OXYGEN_USER_AGENT con l'UA concordato. Nessuna modifica al
# codice. Se invece l'accesso venisse negato o revocato, la risposta giusta
# è disattivare la fonte (DISABLED_SOURCES=oppo_official), non cercare un
# modo per rientrare: niente rotazione di identità, niente evasione di
# rate limit.
#
# Cortesia verso un servizio comunitario gratuito: la copertura è una lista
# curata di modelli (non tutti i ~1600 del catalogo) e il parallelismo è
# tenuto basso di proposito. Sono ~30 richieste per giro orario: l'ordine di
# grandezza di pochi utenti dell'app, non di uno scraping.
#
# Rotte lette dal client open source (github.com/oxygen-updater/os-updater,
# apis/ServerApi.kt + build.gradle.kts per l'URL base):
#   devices/{filter}                              -> catalogo dispositivi
#   mostRecentUpdateData/{deviceId}/{methodId}    -> build corrente
# L'id del metodo è risultato uguale su tutti i device controllati
# (2 = "Stable (full)", 1 = "Stable (incremental)"), quindi non serve una
# chiamata per-device solo per scoprirlo.
OXYGEN_API_BASE = "https://oxygenupdater.com/api/v2.10"
OXYGEN_METHOD_FULL = 2
OXYGEN_METHOD_INCREMENTAL = 1

# Modelli recenti più diffusi, una regione ciascuno (gli id vengono dal
# catalogo `devices/enabled`). Per aggiungerne altri: interrogare quel
# catalogo e riportare qui la coppia (id, nome da mostrare).
OPPO_OFFICIAL_DEVICES: list[tuple[int, str]] = [
    (151, "OnePlus 13"),
    (155, "OnePlus 13R"),
    (227, "OnePlus 13s"),
    (128, "OnePlus 12"),
    (131, "OnePlus 12R"),
    (122, "OnePlus Open"),
    (525, "OnePlus Nord 5"),
    (575, "OnePlus Nord CE5"),
    (144, "OnePlus Nord 4"),
    (1342, "OPPO Find X9 Ultra"),
    (788, "OPPO Find X9 Pro"),
    (802, "OPPO Find X9"),
    (187, "OPPO Find X8 Pro"),
    (206, "OPPO Find X8"),
    (1336, "realme GT 8 Pro"),
    (1464, "realme GT 7"),
    (1561, "realme GT 7T"),
    (1042, "realme GT 7 Pro"),
    (1051, "realme GT 6"),
    (1063, "realme GT 6T"),
    (1369, "realme 14 Pro+"),
    (1463, "realme 14 Pro"),
    (1448, "realme 14T"),
    (1352, "realme 14"),
    (1531, "realme 14x"),
    (1591, "realme 13 Pro"),
    (1565, "realme 13+"),
    (1625, "realme 13"),
]

# La data di rilascio non ha un campo proprio nella risposta: compare come
# intestazione markdown nella descrizione ("##2026-07-24").
_OXYGEN_DATE_RE = re.compile(r"##(20\d{2}-\d{2}-\d{2})")


def _oxygen_get(path: str):
    if requests is None:  # pragma: no cover
        raise RuntimeError("la libreria 'requests' non è installata")
    return requests.get(
        f"{OXYGEN_API_BASE}/{path}",
        timeout=C.HTTP_TIMEOUT,
        headers={"User-Agent": C.OXYGEN_USER_AGENT, "Accept": "application/json"},
    )


def _oxygen_latest(device_id: int) -> dict | None:
    """Build più recente per un device: prima il pacchetto completo, poi
    l'incrementale per i device che pubblicano solo quello."""
    for method_id in (OXYGEN_METHOD_FULL, OXYGEN_METHOD_INCREMENTAL):
        try:
            response = _oxygen_get(f"mostRecentUpdateData/{device_id}/{method_id}")
        except Exception:
            continue
        if response.status_code != 200:
            continue
        try:
            data = response.json()
        except ValueError:
            continue
        if data and data.get("version_number"):
            return data
    return None


def fetch_oppo_official() -> tuple[list[RawItem], str | None]:
    """Versione firmware corrente per i principali Oppo/OnePlus/realme,
    da fonte ufficiale invece che dedotta da un titolo di notizia."""
    def _check(pair):
        device_id, display_name = pair
        try:
            return display_name, _oxygen_latest(device_id)
        except Exception:
            return display_name, None

    items = []
    # Parallelismo volutamente contenuto (vedi nota sulla cortesia sopra).
    with ThreadPoolExecutor(max_workers=6) as pool:
        for display_name, data in pool.map(_check, OPPO_OFFICIAL_DEVICES):
            if not data:
                continue
            version = clean_text(data.get("version_number") or "")
            date_match = _OXYGEN_DATE_RE.search(data.get("description") or "")
            size_gb = (data.get("download_size") or 0) / (1024 ** 3)
            items.append(
                RawItem(
                    title=f"{display_name} — {version}".strip(),
                    link=data.get("download_url") or "",
                    published=iso(date_match.group(1)) if date_match else None,
                    brand=C.OPPO,
                    device=display_name,
                    version=version or None,
                    build=version or None,
                    size_gb=size_gb,
                    size_info="OTA ufficiale" + (f" · {size_gb:.1f} GB" if size_gb else ""),
                    summary=clean_text((data.get("changelog") or "")[:400]),
                )
            )
    if not items:
        return [], f"nessun modello raggiungibile su {len(OPPO_OFFICIAL_DEVICES)} in elenco"
    return items, None


# ======================================================================
# Honor — piano ufficiale "Android Enterprise Recommended"
# ======================================================================
# Pagina statica (non JS), lista per modello: versione Android di partenza
# e impegno massimo di aggiornamento futuro con relativa scadenza. Non da'
# il build/patch esatto del mese (Honor non lo pubblica pubblicamente), ma
# e' un dato ufficiale diretto invece di dover sperare in una notizia.
HONOR_AER_URL = "https://www.honor.com/global/tech/security-update/"
_HONOR_ROW_RE = re.compile(
    r"(HONOR\s+[A-Za-z0-9 +\-]+?)\s*\n+\s*"
    r"\d{2}/\d{4}\s+at least[（(]([^）)]+)[）)]\s*\n+\s*"
    r"Shipped version:\s*(\d+)\s*\n+\s*"
    r"Future version:\s*([\d&]+)"
)


# Pagina ufficiale, non un feed di notizie: cambia raramente. Un'ora di
# cache è larga per la freschezza del dato e stretta abbastanza da non
# tenere per sempre un errore temporaneo — vedi `fetch_honor_aer` sotto,
# che non mette in cache gli errori.
_AER_TTL_SECONDI = 60 * 60
_honor_aer_cache = _CacheDiFonte(_AER_TTL_SECONDI)

# Il bollettino italiano è la fonte europea più ampia che HONOR pubblichi
# direttamente: non espone il numero di build, ma elenca i modelli ancora
# supportati e la loro cadenza di sicurezza. È complementare ad AER, che
# copre soltanto una parte dei modelli business e riporta l'Android iniziale.
HONOR_SECURITY_BULLETIN_URL = "https://www.honor.com/it/support/bulletin/"
_HONOR_SECURITY_SECTION_RE = re.compile(
    r'<p\b[^>]*class=["\']des-tit["\'][^>]*>(?P<title>.*?)</p>'
    r'(?P<models>.*?)(?=<p\b[^>]*class=["\']des-tit["\']|</div>)',
    re.IGNORECASE | re.DOTALL,
)
_HONOR_SECURITY_MODEL_LINE_RE = re.compile(
    r'<p\b[^>]*class=["\']des["\'][^>]*>(?P<line>.*?)</p>',
    re.IGNORECASE | re.DOTALL,
)
_honor_security_cache = _CacheDiFonte(_AER_TTL_SECONDI)


def _testo_html_breve(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def _parse_honor_security_bulletin(html_text: str) -> list[tuple[str, str]]:
    """Estrae ``(modello, cadenza)`` dal bollettino HONOR europeo.

    Il parser opera sulle sezioni (mensile/bimestrale/trimestrale), non su
    ogni token del documento: i bollettini mensili contengono gli stessi
    nomi e non devono diventare falsi dispositivi o duplicati.
    """
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for section in _HONOR_SECURITY_SECTION_RE.finditer(html_text or ""):
        title = _testo_html_breve(section.group("title")).lower()
        if "mensili" in title:
            cadence = "mensili"
        elif "bimestrali" in title:
            cadence = "bimestrali"
        elif "trimestrali" in title:
            cadence = "trimestrali"
        else:
            continue
        for line_match in _HONOR_SECURITY_MODEL_LINE_RE.finditer(section.group("models")):
            line = _testo_html_breve(line_match.group("line"))
            if ":" not in line:
                continue
            _series, names = line.split(":", 1)
            for raw_name in names.split(","):
                name = " ".join(raw_name.split())
                if not name or "honor" not in name.lower():
                    continue
                key = modelcodes._normalize_name(name)
                if key and key not in seen:
                    seen.add(key)
                    result.append((name, cadence))
    return result


def reset_honor_aer_cache() -> None:
    """Azzera la cache della pagina Honor AER (usata dai test)."""
    _honor_aer_cache.azzera()


def reset_honor_security_cache() -> None:
    """Azzera la cache del bollettino sicurezza HONOR (usata dai test)."""
    _honor_security_cache.azzera()


def fetch_honor_security_bulletin(forza: bool = False) -> tuple[list[RawItem], str | None]:
    return _honor_security_cache.ottieni(_fetch_honor_security_bulletin_scarica, forza)


def _fetch_honor_security_bulletin_scarica() -> tuple[list[RawItem], str | None]:
    try:
        response = http_get(HONOR_SECURITY_BULLETIN_URL)
    except Exception as exc:
        return [], f"connessione fallita: {exc}"
    if response.status_code != 200:
        return [], f"HTTP {response.status_code}"
    response.encoding = "utf-8"
    parsed = _parse_honor_security_bulletin(response.text)
    if not parsed:
        return [], "pagina raggiungibile ma nessuna riga dispositivo riconosciuta (formato cambiato?)"
    return [
        RawItem(
            title=f"{device} — aggiornamenti di sicurezza {cadence}",
            link=HONOR_SECURITY_BULLETIN_URL,
            brand=C.HUAWEI,
            device=device,
            size_info=(
                "Bollettino sicurezza ufficiale HONOR Italia — "
                f"cadenza {cadence}; il produttore non pubblica una build OTA per modello"
            ),
            trust=C.TRUST_STRUCTURED,
            firmware_kind=C.FW_SUPPORT,
        )
        for device, cadence in parsed
    ], None


def fetch_honor_aer(forza: bool = False) -> tuple[list[RawItem], str | None]:
    return _honor_aer_cache.ottieni(_fetch_honor_aer_scarica, forza)


def _fetch_honor_aer_scarica() -> tuple[list[RawItem], str | None]:
    try:
        response = http_get(HONOR_AER_URL)
    except Exception as exc:
        return [], f"connessione fallita: {exc}"
    if response.status_code != 200:
        return [], f"HTTP {response.status_code}"

    # La pagina non dichiara un charset nell'header Content-Type: senza
    # questo, `requests` la decodifica come ISO-8859-1 di default (fallback
    # HTTP standard quando manca l'informazione), storpiando le parentesi a
    # larghezza intera usate nella tabella ("（Global）") in caratteri che il
    # regex non riconosce più — sembra un cambio di formato della pagina, è
    # solo un encoding sbagliato. Il contenuto reale è UTF-8.
    response.encoding = "utf-8"
    text = re.sub(r"<[^>]+>", "\n", response.text)
    text = re.sub(r"[ \t]+", " ", text)

    items = []
    seen = set()
    for match in _HONOR_ROW_RE.finditer(text):
        device_raw, region, shipped, future = match.groups()
        device = " ".join(device_raw.split())
        if device in seen:
            continue
        seen.add(device)
        # ATTENZIONE ALLA SEMANTICA DI QUESTA PAGINA (errore già commesso):
        # "Shipped version: 15"      = la versione Android che il device HA
        # "Future version: 16 at least" = una PROMESSA di aggiornamento futuro
        # Usare la promessa come `android_version` fa dichiarare all'app una
        # versione che il telefono non ha ancora (es. HONOR X8c riportato ad
        # Android 16 quando è realmente su Android 15). La versione dichiarata
        # deve essere quella spedita; l'impegno futuro è solo contesto.
        shipped_version = int(shipped)
        future_top = max(int(v) for v in future.split("&"))
        items.append(
            RawItem(
                title=(
                    f"{device} — Android {shipped_version} di fabbrica; "
                    f"aggiornamenti garantiti almeno fino ad Android {future_top} ({region.strip()})"
                ),
                link=HONOR_AER_URL,
                brand=C.HUAWEI,
                device=device,
                android_version=shipped_version,
                size_info=(
                    "Piano ufficiale Honor Android Enterprise Recommended — "
                    f"versione di fabbrica; garantito fino ad Android {future_top}"
                ),
            )
        )
    if not items:
        return [], "pagina raggiungibile ma nessuna riga dispositivo riconosciuta (formato cambiato?)"
    return items, None


# ======================================================================
# Apple — firmware PER SINGOLO DISPOSITIVO (iOS / iPadOS)
# ======================================================================
# PERCHÉ QUESTO APPROCCIO, E NON L'ENDPOINT GLOBALE APPLE:
# la prima versione di questo supporto leggeva `gdmf.apple.com/v2/pmv`
# (l'endpoint ufficiale Apple che elenca le release disponibili con i
# dispositivi supportati) e da quella lista globale ricavava, per
# inversione, la versione di ciascun dispositivo. Quel disegno si è
# rivelato SBAGLIATO in produzione: attribuiva versioni impossibili a
# dispositivi vecchi (iPhone 8 e iPhone X mostrati con iOS 26, quando si
# fermano a iOS 16.7.x). La causa di fondo non era un dettaglio di parsing
# ma il disegno stesso: costruivo l'associazione dispositivo→versione a
# partire da una struttura che non avevo mai verificato su dati reali, e
# qualunque errore in quell'inversione produce silenziosamente numeri
# plausibili ma falsi.
#
# Qui l'associazione NON viene costruita: si interroga direttamente
# l'elenco dei firmware DI QUEL dispositivo (`/v4/device/{identificatore}`).
# Un iPhone 8 non può restituire iOS 26 perché quella versione non è nella
# sua lista: l'errore di attribuzione diventa impossibile per costruzione,
# non "improbabile perché il codice è scritto bene".
#
# In cambio si perde la copertura totale in un'unica richiesta: per la
# scansione periodica si interroga una lista curata di modelli (una
# richiesta ciascuno, con cache), mentre la ricerca a comando interroga
# esattamente il modello chiesto (una sola richiesta).
APPLE_DEVICE_API = "https://api.ipsw.me/v4/device/{identifier}"
_APPLE_FIRMWARE_TTL_HOURS = 12

# Modelli coperti dalla scansione periodica. Elenco volutamente contenuto:
# la documentazione di ipsw.me chiede di non sovraccaricare l'API, e ogni
# modello costa una richiesta. La ricerca a comando copre tutto il resto.
APPLE_TRACKED_DEVICES = [
    "iPhone18,1", "iPhone18,2", "iPhone18,3", "iPhone18,4",   # linea 17
    "iPhone17,1", "iPhone17,2", "iPhone17,3", "iPhone17,4",   # linea 16
    "iPhone16,1", "iPhone16,2", "iPhone15,4", "iPhone15,5",   # linea 15
    "iPhone15,2", "iPhone15,3", "iPhone14,7", "iPhone14,8",   # linea 14
    "iPhone14,2", "iPhone14,3",                                # linea 13 Pro
    "iPhone12,1", "iPhone10,3",                                # 11 / X
    "iPad14,3", "iPad13,16", "iPad14,1",                       # iPad Pro/Air/mini
]


def _apple_firmwares(identifier: str) -> tuple[list[dict], str | None]:
    """Elenco firmware di UN dispositivo, con cache su database.

    La cache (12h) serve anche a rispettare la richiesta esplicita di
    ipsw.me di non sovraccaricare l'API."""
    identifier = (identifier or "").strip()
    if not identifier:
        return [], "nessun identificatore"

    cache_key = f"apple_fw_{identifier}"
    fetched_key = f"apple_fw_at_{identifier}"
    cached = storage.get_meta(cache_key)
    fetched_at = storage.get_meta(fetched_key)
    if cached and fetched_at:
        try:
            from .util import to_dt
            age_h = (utcnow_for_apple() - to_dt(fetched_at)).total_seconds() / 3600
        except Exception:
            age_h = _APPLE_FIRMWARE_TTL_HOURS + 1
        if age_h < _APPLE_FIRMWARE_TTL_HOURS:
            return cached if isinstance(cached, list) else [], None

    url = APPLE_DEVICE_API.format(identifier=identifier)
    try:
        response = http_get(url, timeout=C.HTTP_TIMEOUT + 10)
    except Exception as exc:
        return [], f"{identifier} → connessione fallita: {exc}"
    if response.status_code == 404:
        return [], f"{identifier} → dispositivo non presente nella fonte"
    if response.status_code != 200:
        return [], f"{identifier} → HTTP {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        return [], f"{identifier} → risposta non JSON"
    if not isinstance(data, dict):
        return [], f"{identifier} → JSON di forma inattesa"

    firmwares = data.get("firmwares")
    if not isinstance(firmwares, list):
        return [], f"{identifier} → campo 'firmwares' assente (formato cambiato?)"

    pulito = []
    for fw in firmwares:
        if not isinstance(fw, dict):
            continue
        version = str(fw.get("version") or "").strip()
        if not version:
            continue
        pulito.append({
            "version": version,
            "build": str(fw.get("buildid") or "").strip() or None,
            "released": iso(fw.get("releasedate")),
            "signed": bool(fw.get("signed")),
            "name": str(data.get("name") or "").strip() or None,
        })
    storage.set_meta(cache_key, pulito)
    storage.set_meta(fetched_key, now_iso_for_apple())
    return pulito, None


def utcnow_for_apple():
    from .util import utcnow
    return utcnow()


def now_iso_for_apple():
    from .util import now_iso
    return now_iso()


def _apple_platform_for(identifier: str) -> str:
    return "iPadOS" if identifier.lower().startswith("ipad") else "iOS"


def _apple_item_for(identifier: str) -> tuple[RawItem | None, str | None]:
    """La versione più recente rilasciata PER QUEL dispositivo."""
    from . import appledevices

    firmwares, error = _apple_firmwares(identifier)
    if error or not firmwares:
        return None, error or f"{identifier} → nessun firmware elencato"

    piu_recente = max(firmwares, key=lambda f: _apple_version_key(f["version"]))
    nome = appledevices.name_for(identifier) or piu_recente.get("name") or identifier
    piattaforma = _apple_platform_for(identifier)
    build = piu_recente.get("build")
    etichetta_build = f" · build {build}" if build else ""
    return RawItem(
        title=f"{nome} — {piattaforma} {piu_recente['version']}{etichetta_build}",
        link=f"https://ipsw.me/{identifier}",
        published=piu_recente.get("released"),
        brand=C.APPLE,
        device=nome,
        version=f"{piattaforma} {piu_recente['version']}",
        build=build,
        android_version=None,  # non è Android: la versione sta in `version`
        size_info=f"Firmware del dispositivo ({identifier})",
    ), None


def fetch_apple() -> tuple[list[RawItem], str | None]:
    """Scansione periodica: una richiesta per ciascun modello seguito."""
    items = []
    errori = []
    for identifier in APPLE_TRACKED_DEVICES:
        try:
            item, error = _apple_item_for(identifier)
        except Exception as exc:
            errori.append(f"{identifier}: {exc}")
            continue
        if item:
            items.append(item)
        elif error:
            errori.append(error)
    if not items:
        return [], "; ".join(errori[:3]) or "nessun modello raggiungibile"
    return items, None


def _apple_version_key(version: str) -> tuple:
    """Ordina '18.1.1' > '18.1' > '9.0' numericamente, non alfabeticamente
    (in stringa '9' risulterebbe maggiore di '18')."""
    parts = []
    for chunk in re.split(r"[.\s]", str(version or "")):
        parts.append(int(chunk) if chunk.isdigit() else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


# ======================================================================
# realme — pagina ufficiale Android Enterprise Recommended
# ======================================================================
# Stessa impostazione della pagina Honor, e stesso identico tranello:
# la tabella riporta "Shipped version" (la versione che il telefono HA) e
# "Future version" (una PROMESSA di aggiornamento). Va usata la prima —
# usare la seconda ha già prodotto un errore reale con Honor, dichiarando
# per un X8c una versione che non aveva ancora.
#
# La stessa pagina contiene un secondo tesoro: l'elenco UFFICIALE dei
# codici modello con il nome commerciale (es. «realme C63/Narzo 63/C61
# （RMX3939）») e la cadenza degli aggiornamenti (mensile o trimestrale).
# È una mappatura di prima mano, più autorevole dei dataset community
# usati altrove.
# ======================================================================
# vivo / iQOO — pagina ufficiale Android Enterprise Recommended
# ======================================================================
# VERIFICATO SUL CONTENUTO REALE il 2026-08-02. La versione precedente di
# questo parser era dichiaratamente un'ipotesi — riusava lo schema AER
# generico di Honor e realme senza aver mai letto la pagina vivo — e stava
# in errore da giorni. La pagina è invece perfettamente raggiungibile: a non
# combaciare era il riconoscimento, per tre motivi che si vedono solo
# guardando l'HTML vero:
#
#   1. lo schema generico pretende che il nome cominci con «vivo» o «iQOO»,
#      mentre la tabella scrive soltanto «X300 Ultra», senza marca;
#   2. ogni cella è preceduta da `&nbsp;&nbsp;`, che resta nel testo perché
#      togliere i tag NON decodifica le entità;
#   3. qui si legge «Shipped version: Android 16», con la parola «Android»
#      davanti al numero, non «Shipped version: 15» come su Honor.
#
# È la stessa famiglia di errore già costata giorni con realme: una regex
# costruita su un formato immaginato invece che osservato. Il parser qui
# sotto legge la tabella per quello che è — righe e celle — e i suoi test
# girano sull'HTML vero registrato in tests/fixtures/vivo_aer.html.
VIVO_AER_URL = "https://www.vivo.com/en/security"

# Righe e celle della tabella AER. Si legge la STRUTTURA (una riga per
# modello, tre celle) invece di inseguire il testo con una regex sola: la
# tabella è marcata bene, e questo la rende insensibile a come sono scritti
# i contenuti — «Android 16» o «16», con o senza `&nbsp;`.
_VIVO_RIGA_RE = re.compile(r"<tr[^>]*class=\"table-content\"[^>]*>(.*?)</tr>", re.S | re.I)
_VIVO_CELLA_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
# «Shipped version: Android 16» oppure «Shipped version: 16».
_VIVO_SHIPPED_RE = re.compile(r"Shipped\s+version:\s*(?:Android\s*)?(\d{1,2})", re.I)
_VIVO_FINE_RE = re.compile(r"End\s+date:\s*([0-9]{1,2}/[0-9]{4})", re.I)
_VIVO_FREQUENZA_RE = re.compile(r"Frequency:\s*([^()\n]{1,40})", re.I)
# «V40 Lite(V2341)»: il codice va tolto dal nome — attaccato lo renderebbe
# un dispositivo diverso da «vivo V40 Lite» delle altre fonti — ma non
# buttato via, perché è il codice ufficiale del modello.
_VIVO_CODICE_RE = re.compile(r"\(\s*(V\d{4}[A-Z0-9]*)\s*\)", re.I)


def _testo_cella(html_cella: str) -> str:
    """Cella HTML → testo piano.

    `html.unescape` NON è opzionale: ogni cella comincia con `&nbsp;&nbsp;`,
    e senza decodificarle il nome del modello risulta «&nbsp;&nbsp;X300
    Ultra». È metà del motivo per cui il parser precedente non trovava mai
    niente.
    """
    testo = re.sub(r"<[^>]+>", " ", html_cella or "")
    return " ".join(html.unescape(testo).split())


def parse_vivo_aer(pagina: str) -> list[RawItem]:
    """Tabella AER di vivo → elenco di modelli.

    Separata dalla rete perché i test possano girare sull'HTML vero.
    """
    visti, items = set(), []
    for riga in _VIVO_RIGA_RE.findall(pagina or ""):
        celle = [_testo_cella(c) for c in _VIVO_CELLA_RE.findall(riga)]
        if len(celle) < 3:
            continue
        nome_grezzo, supporto, versioni = celle[0], celle[1], celle[2]

        shipped = _VIVO_SHIPPED_RE.search(versioni)
        if not shipped or not nome_grezzo:
            continue
        # Versione EFFETTIVA di fabbrica, mai la promessa futura: è l'errore
        # già commesso con Honor, dove un X8c su Android 15 veniva
        # dichiarato su Android 16. Qui la promessa non viene nemmeno letta.
        android = int(shipped.group(1))
        if not 5 <= android <= C.MAX_PLAUSIBLE_ANDROID:
            continue

        codice = _VIVO_CODICE_RE.search(nome_grezzo)
        nome = " ".join(_VIVO_CODICE_RE.sub(" ", nome_grezzo).split())
        # La tabella scrive «X300 Ultra» senza marca: senza il prefisso il
        # `device_key` non coinciderebbe con quello delle altre fonti, e lo
        # stesso telefono diventerebbe due dispositivi distinti.
        if not re.match(r"^\s*(?:vivo|iqoo)\b", nome, re.I):
            nome = f"vivo {nome}"

        chiave = modelcodes._normalize_name(nome)
        if not chiave or chiave in visti:
            continue
        visti.add(chiave)

        fine = _VIVO_FINE_RE.search(supporto)
        frequenza = _VIVO_FREQUENZA_RE.search(supporto)
        dettagli = ["Piano ufficiale vivo Android Enterprise Recommended"]
        if fine:
            dettagli.append(f"patch fino a {fine.group(1)}")
        if frequenza:
            dettagli.append(frequenza.group(1).strip().rstrip("."))
        if codice:
            dettagli.append(codice.group(1).upper())

        items.append(RawItem(
            title=f"{nome} — Android {android} di fabbrica"
                  + (f"; patch garantite fino a {fine.group(1)}" if fine else ""),
            link=VIVO_AER_URL,
            brand=C.VIVO,
            device=nome,
            android_version=android,
            size_info=" · ".join(dettagli),
        ))
    return items


_vivo_aer_cache = _CacheDiFonte(_AER_TTL_SECONDI)


def reset_vivo_aer_cache() -> None:
    """Azzera la cache della pagina Vivo AER (usata dai test)."""
    _vivo_aer_cache.azzera()


def fetch_vivo_aer(forza: bool = False) -> tuple[list[RawItem], str | None]:
    return _vivo_aer_cache.ottieni(_fetch_vivo_aer_scarica, forza)


def _fetch_vivo_aer_scarica() -> tuple[list[RawItem], str | None]:
    try:
        risposta = http_get(VIVO_AER_URL, timeout=C.HTTP_TIMEOUT + 10)
    except Exception as exc:
        return [], f"connessione fallita: {exc}"
    if risposta.status_code != 200:
        return [], f"HTTP {risposta.status_code}"

    items = parse_vivo_aer(risposta.text)
    if not items:
        return [], (
            "pagina raggiungibile ma nessuna riga della tabella «Android Enterprise "
            "Recommended Device List» è stata riconosciuta: probabile cambio di "
            "struttura della pagina"
        )
    return items, None


# ======================================================================
# Android Enterprise Recommended — catalogo ufficiale in JSON
# ======================================================================
# PERCHÉ COMPLEMENTARE E NON SOSTITUTIVA. L'idea iniziale era rimpiazzare
# con questa i quattro parser HTML (Honor, realme, vivo, Oppo). La misura
# dice di no, ed è il motivo per cui vale la pena misurare:
#
#   Honor   pagina 26 device, 26 con versione  →  JSON 24, solo 21
#   vivo    pagina 20 device, 20 con versione  →  JSON 19, solo 15
#   realme  pagina  6 device                   →  JSON 16, 15 con versione
#   Oppo    pagina 113 device, ZERO versioni   →  JSON 50, con codici
#
# Sostituire avrebbe tolto dati a Honor e vivo. Quello che questa fonte
# aggiunge davvero, e che nessun'altra dà:
#
#   * 1404 CODICI MODELLO verificati (CPH2791 → OPPO Find X9 Pro), che
#     permettono di confermare la corrispondenza invece di dedurla;
#   * la FINESTRA DI SUPPORTO di sicurezza per 706 dispositivi — per un QA
#     è il dato che dice se un device di test è ancora vivo;
#   * OnePlus, che oggi non ha nessuna fonte strutturata.
#
# NON dà la versione attuale, e il campo che sembra darla non è
# affidabile: vedi il docstring di core/aer_catalog.py.
_MARCHE_DA_TOGLIERE = re.compile(r"^\s*(?:samsung|google|motorola)\s+", re.IGNORECASE)
# Le tre marche per cui l'AER usa una forma DIVERSA da quella del resto del
# progetto: «Samsung Galaxy S25 Ultra» contro «Galaxy S25 Ultra» della fonte
# FOTA, «Google Pixel 10» contro «Pixel 10», «Motorola moto g14» contro
# «Moto G14». Solo per queste il nome va ricondotto, o lo stesso telefono
# finisce in archivio due volte con metà storia ciascuno.
_MARCHE_DA_RICONDURRE = {"samsung", "google", "motorola"}


def nome_aer_normalizzato(display_name: str, brand_aer: str = "") -> str:
    """Adegua il nome AER alle convenzioni già usate nel progetto.

    PERCHÉ NON SI APPLICA A TUTTI. La tentazione è passare ogni nome dal
    riconoscitore di `extract`, che allineerebbe tutto per costruzione.
    Provato, e peggiora: «HONOR 600e» diventa «Honor 600» — un altro
    telefono — e «realme 14 Pro 5G» perde il 5G. Il riconoscitore è tarato
    sui titoli delle notizie, non su un catalogo, e semplifica.

    Quindi si ricorre a lui solo per le tre marche dove serve davvero, e
    per tutte le altre il nome AER si tiene com'è: lì il prefisso È già la
    convenzione del progetto («OPPO A6x», «vivo X300 Ultra», «realme C61»).
    """
    nome = " ".join(str(display_name or "").split())
    if not nome:
        return ""
    if str(brand_aer or "").strip().lower() not in _MARCHE_DA_RICONDURRE:
        return nome
    _brand, modello = extract.extract_device(nome)
    if modello:
        return modello
    # Il riconoscitore non l'ha visto (un tablet, un modello troppo nuovo):
    # si toglie almeno la marca ripetuta, che è la differenza principale.
    return " ".join(_MARCHE_DA_TOGLIERE.sub(" ", nome).split())


def _item_da_aer(device: dict) -> RawItem | None:
    nome = nome_aer_normalizzato(device.get("device_model"), device.get("brand_aer"))
    if not nome:
        return None
    android = device.get("launch_android")
    dettagli = ["Android Enterprise Recommended"]
    if android:
        dettagli.append(f"Android {android} DI FABBRICA")
    if device.get("security_until"):
        dettagli.append(f"patch fino a {device['security_until']}")
    if device.get("security_frequency"):
        dettagli.append(device["security_frequency"])
    codici = device.get("model_codes") or []
    if codici:
        dettagli.append("/".join(codici[:3]))

    # IL TITOLO NON DEVE CONTENERE NÉ VERSIONI NÉ DATE, e la ragione non è
    # estetica: `RawItem.text` (titolo + versione + build + sommario) è il
    # testo che gli estrattori rileggono. Scriverci «Android 14 di
    # fabbrica» ricreava la `android_version` appena tolta dal campo, e
    # «patch fino a 2031-10-30» sarebbe diventato un livello di patch di
    # sicurezza datato 2031 — un dato falso, per giunta nel futuro.
    #
    # `size_info` invece NON entra in `text`: è il posto giusto per i
    # dettagli leggibili da una persona.
    return RawItem(
        title=f"{nome} — dispositivo certificato Android Enterprise Recommended",
        link=aer_catalog.ENDPOINT.split("?")[0],
        brand=device.get("brand"),
        device=nome,
        # Un solo codice, e solo se non è ambiguo: il catalogo ne elenca
        # più d'uno per le varianti regionali, e sceglierne uno a caso
        # sarebbe peggio che non dirne nessuno — è la stessa regola già
        # applicata al chip in `soc.carica_dataset_esterno`.
        model_code=codici[0] if len(codici) == 1 else None,
        # NIENTE `android_version`, ed è una decisione, non una svista.
        #
        # Questa fonte conosce solo la versione DI LANCIO. Dichiararla come
        # versione del dispositivo la rendeva un dato strutturato che
        # scavalcava le altre fonti: durante l'integrazione un «Moto G14 —
        # patch di luglio 2026», datato e attuale, è stato sostituito in
        # cronologia da un «Android 14» di fabbrica. Per un tracker degli
        # aggiornamenti è esattamente il contrario di quello che serve.
        #
        # La versione di lancio resta leggibile nel titolo e in `size_info`,
        # marcata come tale. Il valore di questa fonte è altrove: codici
        # modello, finestra di supporto, copertura di OnePlus.
        size_info=" · ".join(dettagli),
    )


def fetch_aer_catalog() -> tuple[list[RawItem], str | None]:
    dispositivi = aer_catalog.carica()
    if not dispositivi:
        return [], aer_catalog.status()
    items = [i for i in (_item_da_aer(d) for d in dispositivi) if i]
    return items, None


def _lookup_aer_catalog(model_name: str) -> list[RawItem]:
    """Ricerca per nome commerciale O per codice tecnico, indifferentemente."""
    device = aer_catalog.lookup(model_name)
    if not device:
        return []
    item = _item_da_aer(device)
    return [item] if item else []


def _lookup_pixel(model_name: str) -> list[RawItem]:
    """Ultima immagine OTA ufficiale per un Pixel.

    Mancava, e la mancanza era invisibile: la fonte Pixel esisteva ma solo
    nella scansione periodica, quindi cercare «Pixel 9 Pro» a comando dava
    la sola conferma che il dispositivo esiste — su una delle marche con la
    fonte ufficiale migliore del progetto.
    """
    tutti, errore = fetch_pixel_ota()
    if errore or not tutti:
        return []
    bersaglio = modelcodes._normalize_name(model_name)
    if not bersaglio:
        return []
    esatti = [i for i in tutti if modelcodes._normalize_name(i.device or "") == bersaglio]
    if esatti:
        return esatti[:1]
    # Confronto contenitivo, ma solo verso nomi PIÙ LUNGHI del cercato:
    # «Pixel 9» non deve restituire «Pixel 9 Pro XL», che è un altro
    # telefono, mentre chi scrive «pixel 9 pro» deve trovarlo comunque.
    parziali = [
        i for i in tutti
        if bersaglio in modelcodes._normalize_name(i.device or "")
    ]
    parziali.sort(key=lambda i: len(modelcodes._normalize_name(i.device or "")))
    return parziali[:1]


def _lookup_vivo(model_name: str) -> list[RawItem]:
    tutti, errore = fetch_vivo_aer()
    if errore or not tutti:
        return []
    bersaglio = modelcodes._normalize_name(model_name)
    if not bersaglio:
        return []
    esatti = [i for i in tutti if modelcodes._normalize_name(i.device or "") == bersaglio]
    if esatti:
        return esatti[:1]
    # Senza un nome esatto vince il PIÙ VICINO, non il primo del catalogo:
    # «SMART 8» non deve rispondere «SMART 10 HD» solo perché era elencato
    # prima. Stessa regola di `_lookup_xiaomi` e `_lookup_honor`.
    return _piu_vicini(
        [(i, modelcodes._normalize_name(i.device or "")) for i in tutti], bersaglio)


# ======================================================================
# Oppo — pagina ufficiale Android Enterprise Recommended
# ======================================================================
# A differenza di Honor e realme, questa pagina NON pubblica la versione
# Android per singolo dispositivo: dichiara solo la politica di supporto
# valida per tutti i modelli certificati ("aggiornamenti di sicurezza per
# 3 anni dalla data di uscita, almeno un passaggio di versione").
#
# Va quindi usata per quello che dice davvero: conferma che un modello
# esiste ufficialmente, ne dà il nome commerciale corretto e la finestra
# di supporto. Non se ne ricava una versione installata, e l'app non deve
# fingere il contrario — è lo stesso errore già commesso con Honor, dove
# una promessa di aggiornamento futuro era stata presa per versione attuale.
OPPO_AER_URL = "https://www.oppo.com/en/events/aerb2b/"

# Nomi dei modelli nell'elenco. Si escludono orologi, auricolari e router:
# questo è un tracker di telefoni e tablet.
#
# L'estrazione è volutamente TOLLERANTE, non esatta. La prima versione
# pretendeva che il nome iniziasse esattamente a inizio riga: bastava uno
# spazio di indentazione, o il nome ripetuto due volte come accade nelle
# voci di menu ("OPPO A6x OPPO A6x", dove la seconda copia è il testo
# alternativo dell'immagine), perché non riconoscesse più nulla. Era stata
# provata su un HTML scritto a mano, non su quello vero.
_OPPO_DEVICE_RE = re.compile(
    r"^\s*OPPO\s+((?!Watch|Enco|5G CPE|Community|Lock)[A-Za-z0-9][A-Za-z0-9 +]{0,28}?)\s*$",
    re.MULTILINE,
)
# Seconda via, indipendente dal testo: lo slug nell'indirizzo della scheda
# prodotto ("…/series-a/a6x/"). Regge anche se cambia l'impaginazione.
_OPPO_SLUG_RE = re.compile(
    r"/smartphones/series-[a-z]+/([a-z0-9][a-z0-9-]{1,28})/", re.IGNORECASE
)
OPPO_SUPPORT_POLICY = (
    "aggiornamenti di sicurezza per 3 anni dalla data di uscita, "
    "almeno un passaggio di versione Android"
)

# L'endpoint ``support.oppo.com/software-update`` continua a essere la
# fonte per le build legacy, ma il suo catalogo termina intorno al 2021/22.
# Per modelli moderni OPPO pubblica il piano di rollout ColorOS: non è una
# build installata, quindi questa fonte resta SUPPORT e non può mai essere
# presentata come "ultimo firmware". È però il modo ufficiale per dire se
# Android 16 è previsto per quel modello.
OPPO_COLOROS16_URL = "https://www.oppo.com/en/coloros16/"
_OPPO_COLOROS16_TTL_SECONDI = 12 * 60 * 60
_OPPO_COLOROS16_SEZIONE_RE = re.compile(
    r"ColorOS\s+16\s+Official\s+Version\s+Roll[\s-]*Out\s+Schedule"
    r"(?P<corpo>.*?)(?=ColorOS\s+15\b|$)",
    re.IGNORECASE | re.DOTALL,
)
_oppo_coloros16_cache = _CacheDiFonte(_OPPO_COLOROS16_TTL_SECONDI)


def reset_oppo_coloros16_cache() -> None:
    """Azzera la cache del piano ColorOS 16 (usata dai test)."""
    _oppo_coloros16_cache.azzera()


def fetch_oppo_coloros16(forza: bool = False) -> tuple[list[RawItem], str | None]:
    """Modelli nel piano ufficiale OPPO ColorOS 16 / Android 16.

    OPPO avverte che date, regione e operatore possono cambiare. Per questo
    le voci sono ``FW_SUPPORT`` e dichiarano il limite, pur mantenendo il
    dato Android utile alla diagnosi.
    """
    return _oppo_coloros16_cache.ottieni(_fetch_oppo_coloros16_scarica, forza)


def _fetch_oppo_coloros16_scarica() -> tuple[list[RawItem], str | None]:
    try:
        risposta = http_get(OPPO_COLOROS16_URL, timeout=C.HTTP_TIMEOUT + 10)
    except Exception as exc:
        return [], f"connessione fallita: {exc}"
    if risposta.status_code != 200:
        return [], f"HTTP {risposta.status_code}"

    testo = html.unescape(re.sub(r"<[^>]+>", "\n", risposta.text or ""))
    sezione = _OPPO_COLOROS16_SEZIONE_RE.search(testo)
    if not sezione:
        return [], "pagina raggiungibile ma calendario ColorOS 16 non riconosciuto (formato cambiato?)"

    visti: set[str] = set()
    items: list[RawItem] = []
    for riga in sezione.group("corpo").splitlines():
        nome = " ".join(riga.split())
        # Nella sezione del calendario le righe dispositivo iniziano tutte
        # con OPPO. Il controllo stretto evita falsi modelli dalle note
        # legali nel caso in cui OPPO cambi il markup.
        if not re.fullmatch(r"OPPO\s+[A-Za-z0-9][A-Za-z0-9 +.-]{1,64}", nome):
            continue
        chiave = modelcodes._normalize_name(nome)
        if not chiave or chiave in visti:
            continue
        visti.add(chiave)
        items.append(RawItem(
            title=f"{nome} — ColorOS 16 / Android 16 (piano ufficiale)",
            link=OPPO_COLOROS16_URL,
            brand=C.OPPO,
            device=nome,
            version="ColorOS 16",
            android_version=16,
            summary=(
                "Calendario ufficiale OPPO: date, regione e operatore possono "
                "variare; non prova la build installata."
            ),
            size_info="Piano ufficiale OPPO ColorOS 16",
            firmware_kind=C.FW_SUPPORT,
        ))
    if not items:
        return [], "pagina raggiungibile ma nessun modello ColorOS 16 riconosciuto (formato cambiato?)"
    return items, None


def _lookup_oppo_coloros16(model_name: str) -> list[RawItem]:
    """Trova il piano Android 16 anche partendo da un codice CPH."""
    tutti, errore = fetch_oppo_coloros16()
    if errore or not tutti:
        return []

    candidati = [model_name]
    for codice in _code_candidates(model_name):
        canonico = modelcodes.nome_canonico(codice)
        if canonico:
            candidati.append(canonico)
    for candidato in candidati:
        bersaglio = modelcodes._normalize_name(candidato)
        if not bersaglio:
            continue
        esatti = [i for i in tutti if modelcodes._normalize_name(i.device or "") == bersaglio]
        if esatti:
            return esatti[:1]
    return []


def _oppo_nome_da_slug(slug: str) -> str:
    """'a6x-5g' → 'OPPO A6x 5G'."""
    pezzi = []
    for pezzo in slug.split("-"):
        if pezzo.lower() in ("5g", "4g"):
            pezzi.append(pezzo.upper())
        elif re.fullmatch(r"[a-z]\d+[a-z]?", pezzo, re.IGNORECASE):
            # "a6x" → "A6x": lettera iniziale maiuscola, suffisso minuscolo
            pezzi.append(pezzo[0].upper() + pezzo[1:].lower())
        else:
            pezzi.append(pezzo.capitalize())
    return "OPPO " + " ".join(pezzi)


_oppo_aer_cache = _CacheDiFonte(_AER_TTL_SECONDI)


def reset_oppo_aer_cache() -> None:
    """Azzera la cache della pagina Oppo AER (usata dai test)."""
    _oppo_aer_cache.azzera()


def fetch_oppo_aer(forza: bool = False) -> tuple[list[RawItem], str | None]:
    return _oppo_aer_cache.ottieni(_fetch_oppo_aer_scarica, forza)


def _fetch_oppo_aer_scarica() -> tuple[list[RawItem], str | None]:
    try:
        response = http_get(OPPO_AER_URL, timeout=C.HTTP_TIMEOUT + 10)
    except Exception as exc:
        return [], f"connessione fallita: {exc}"
    if response.status_code != 200:
        return [], f"HTTP {response.status_code}"

    grezzo = response.text
    testo = re.sub(r"<[^>]+>", "\n", grezzo)
    testo = re.sub(r"[ \t]+", " ", testo)

    nomi = []
    for match in _OPPO_DEVICE_RE.finditer(testo):
        nome = " ".join(("OPPO " + match.group(1)).split())
        # Le voci di menu ripetono il nome due volte: si tiene la prima metà.
        parole = nome.split()
        meta = len(parole) // 2
        if meta and parole[:meta] == parole[meta:]:
            nome = " ".join(parole[:meta])
        nomi.append(nome)

    # Seconda via, indipendente dall'impaginazione.
    for slug in _OPPO_SLUG_RE.findall(grezzo):
        nomi.append(_oppo_nome_da_slug(slug))

    visti, items = set(), []
    for nome in nomi:
        chiave = modelcodes._normalize_name(nome)
        if not chiave or chiave in visti or len(chiave) < 2:
            continue
        visti.add(chiave)
        items.append(
            RawItem(
                title=(
                    f"{nome} — dispositivo Android Enterprise Recommended: "
                    f"{OPPO_SUPPORT_POLICY}"
                ),
                link=OPPO_AER_URL,
                brand=C.OPPO,
                device=nome,
                # Nessuna versione: la pagina non la pubblica per dispositivo,
                # e inventarla sarebbe peggio che non averla.
                android_version=None,
                size_info="Elenco ufficiale Oppo Android Enterprise Recommended",
            )
        )
    if not items:
        return [], "pagina raggiungibile ma nessun dispositivo riconosciuto (formato cambiato?)"
    return items, None


def _lookup_oppo(model_name: str) -> list[RawItem]:
    """Cerca un modello nell'elenco ufficiale Oppo."""
    tutti, error = fetch_oppo_aer()
    if error or not tutti:
        return []
    bersaglio = modelcodes._normalize_name(model_name)
    if not bersaglio:
        return []
    esatti = [i for i in tutti if modelcodes._normalize_name(i.device or "") == bersaglio]
    if esatti:
        return esatti[:1]
    # Senza un nome esatto vince il PIÙ VICINO, non il primo del catalogo:
    # «SMART 8» non deve rispondere «SMART 10 HD» solo perché era elencato
    # prima. Stessa regola di `_lookup_xiaomi` e `_lookup_honor`.
    return _piu_vicini(
        [(i, modelcodes._normalize_name(i.device or "")) for i in tutti], bersaglio)


def _lookup_oppo_support(model_name: str) -> list[RawItem]:
    """Versione firmware ufficiale dall'archivio di support.oppo.com.

    A differenza di `_lookup_oppo` (elenco AER), questa fonte dà la versione
    DAVVERO RILASCIATA, con data e changelog — non quella di fabbrica. Copre
    però solo i ~94 modelli per cui Oppo pubblica il firmware completo, cioè
    fino al 2021-2022: per tutti i modelli più recenti restituisce
    correttamente niente, e la ricerca prosegue sulle fonti successive.
    Vedi core/oppo_official.py per l'indagine completa.
    """
    dato, errore = oppo_official.fetch_oppo_official(
        model_name, timeout=C.SEARCH_HTTP_TIMEOUT)
    if errore or not dato:
        return []

    # NIENTE `size_gb`, ed è una scelta, non una dimenticanza: sono tutte
    # ROM complete da 3-4 GB, e passarle al semaforo renderebbe MAJOR anche
    # una patch di sicurezza. La severità resta all'euristica sul changelog.
    dimensione = f"{dato['size_mb'] / 1024:.1f} GB" if dato.get("size_mb") else ""
    pezzi = ["Firmware ufficiale Oppo"]
    if dimensione:
        pezzi.append(dimensione)
    if dato.get("versioni_archiviate", 0) > 1:
        pezzi.append(f"{dato['versioni_archiviate']} versioni in archivio")

    pubblicato = dato.get("published")
    return [RawItem(
        title=f"{dato['device_model']} — {dato['build']}",
        link=dato.get("link") or "",
        published=iso(pubblicato.replace(" ", "T", 1)) if pubblicato else None,
        brand=C.OPPO,
        device=dato["device_model"],
        build=dato["build"],
        # Il changelog serve agli estrattori per ricavare il livello di
        # patch di sicurezza: è richiesto in inglese apposta (vedi il
        # docstring di oppo_official).
        summary=dato.get("changelog", ""),
        size_info=" · ".join(pezzi),
    )]


# ======================================================================
# Oppo / OnePlus / realme moderni — canale Telegram di rollout
# ======================================================================
# Il buco che questa fonte chiude, e perché è accettabile tenerla:
# `_lookup_oppo_support` copre solo i ~94 modelli d'archivio fino al
# 2021-22; l'AER e il piano realme danno la versione DI FABBRICA; le news
# danno un titolo da interpretare. Per un Reno 15 o un OnePlus 13 uscito
# ieri non c'era nessun numero di build da nessuna parte — ed è
# esattamente la domanda che il QA fa.
#
# Il prezzo: è il canale di una persona, quindi TRUST_CURATED e mai
# STRUCTURED. Non deve poter sovrascrivere un dato ufficiale, e
# nell'interfaccia deve dire da dove viene.
TELEGRAM_OPLUS_URL = telegram_tracker.URL_CANALE

_telegram_cache: list[telegram_tracker.Rilascio] | None = None
_telegram_errore: str | None = None
# Sentinel «mai scaricato» = None, NON 0.0: lo zero di `time.monotonic()`
# è l'accensione della macchina, non un'epoca, e su un container appena
# avviato «0.0» significherebbe «scaricato pochi secondi fa». È l'errore
# n. 11 del passaggio di consegne, già pagato una volta in aer_catalog.
_telegram_scaricato_a: float | None = None
_TELEGRAM_TTL_SECONDI = 30 * 60


def _telegram_get(url: str, timeout: int | None = None):
    """Unico punto di rete di questa fonte, isolato apposta.

    Sta qui e non in `telegram_tracker` perché quel modulo deve restare
    puro: così i test lo esercitano sui messaggi registrati senza dover
    intercettare niente, e chi cerca gli agganci di rete ne trova uno
    solo, sostituibile, invece di un client nascosto in un altro file.
    """
    return http_get(url, timeout=timeout)


def _telegram_rilasci(forza: bool = False):
    """Rilasci confermati dal canale, con cache a tempo.

    Ritorna `(rilasci, errore)`. Una pagina che non contiene rilasci NON
    è un errore (il canale parla spesso d'altro); una pagina da cui non
    si estrae nessun messaggio sì, ed è il segnale che l'HTML di Telegram
    è cambiato.
    """
    global _telegram_cache, _telegram_errore, _telegram_scaricato_a

    fresca = (
        _telegram_cache is not None
        and _telegram_scaricato_a is not None
        and (time.monotonic() - _telegram_scaricato_a) < _TELEGRAM_TTL_SECONDI
    )
    if fresca and not forza:
        return _telegram_cache, _telegram_errore

    try:
        risposta = _telegram_get(TELEGRAM_OPLUS_URL)
    except Exception as exc:
        _telegram_cache, _telegram_errore = [], f"canale non raggiungibile: {exc}"
        _telegram_scaricato_a = time.monotonic()
        return _telegram_cache, _telegram_errore

    codice = getattr(risposta, "status_code", 0)
    if codice != 200:
        _telegram_cache, _telegram_errore = [], f"HTTP {codice} da {TELEGRAM_OPLUS_URL}"
        _telegram_scaricato_a = time.monotonic()
        return _telegram_cache, _telegram_errore

    rilasci, errore = telegram_tracker.rilasci_da_pagina(getattr(risposta, "text", "") or "")
    _telegram_cache, _telegram_errore = rilasci, errore
    _telegram_scaricato_a = time.monotonic()
    return _telegram_cache, _telegram_errore


def reset_telegram_cache() -> None:
    """Azzera la cache del canale (usata dai test e dal pulsante di
    ricarica in Diagnostica)."""
    global _telegram_cache, _telegram_errore, _telegram_scaricato_a
    _telegram_cache = None
    _telegram_errore = None
    _telegram_scaricato_a = None


def _nome_per_codice(codice: str | None) -> str | None:
    """Codice modello → nome commerciale, con le due tabelle già in casa.

    È il pezzo che rende utile questa fonte invece che curiosa: più della
    metà dei post confermati porta la build **senza il nome del telefono**
    (`Version : CPH2613_16.0.3.500` e basta). Il canale porta il firmware,
    il progetto ci mette l'identità — AER prima perché usa la grafia
    ufficiale, poi i dataset di `modelcodes`.
    """
    if not codice:
        return None
    try:
        nome = aer_catalog.name_for_code(codice)
        if nome:
            return nome
    except Exception:
        pass
    try:
        nomi = modelcodes.resolve(codice)
    except Exception:
        nomi = []
    return nomi[0] if nomi else None


def _item_da_rilascio(rilascio, nome_forzato: str | None = None) -> RawItem | None:
    """Da `Rilascio` a `RawItem`, o None se il telefono resta ignoto.

    **Un rilascio senza nome viene scartato nel giro periodico**, e non è
    uno spreco: un dispositivo chiamato «CPH2613» in archivio non si
    incontra con «OPPO A6x» delle altre fonti, quindi produrrebbe una
    scheda gemella con metà della storia — lo stesso danno descritto in
    INTEGRAZIONE-OPPO.md. Nella ricerca a comando il nome arriva invece
    da chi cerca, e allora l'item si costruisce lo stesso.
    """
    nome = nome_forzato or rilascio.device_name or _nome_per_codice(rilascio.model_code)
    if not nome:
        return None

    descrizione = ["Canale rollout OxygenOS/ColorOS (non ufficiale)"]
    if rilascio.model_code:
        descrizione.append(rilascio.model_code)
    if rilascio.region:
        descrizione.append(f"regione {rilascio.region}")
    if rilascio.canale_build:
        descrizione.append(rilascio.canale_build)

    skin = " ".join(p for p in (rilascio.skin, rilascio.skin_version) if p)
    titolo = f"{nome} — {rilascio.build}" + (f" ({skin})" if skin else "")

    return RawItem(
        title=titolo,
        link=rilascio.link,
        # La data del rilascio non c'è: il canale pubblica il livello di
        # patch, non il giorno di distribuzione. Lasciare `published`
        # vuoto è corretto — l'archivio userà la data di prima
        # rilevazione e la marcherà come stimata, invece di spacciare il
        # livello di patch per una data di uscita.
        published=None,
        brand=C.OPPO,
        device=nome,
        version=skin or None,
        build=rilascio.build,
        android_version=rilascio.android_version,
        # Il livello di patch viaggia nel testo perché è da lì che gli
        # estrattori lo leggono, come per l'archivio ufficiale Oppo.
        summary=(f"Security patch level: {rilascio.patch_level}. "
                 if rilascio.patch_level else "") + rilascio.changelog,
        size_info=" · ".join(descrizione),
        trust=C.TRUST_CURATED,
    )


# ======================================================================
# OnePlus / OPPO — tracker ARB (build correnti per regione)
# ======================================================================
# Perché sta PRIMA del canale Telegram nell'ordine dei lookup: entrambe
# sono fonti community, ma questa è generata da uno script che scarica i
# firmware veri e ne estrae i dati, mentre l'altra è la prosa di una
# persona. A parità di trust, vince il dato prodotto da una macchina.
#
# Copre OnePlus quasi per intero e una parte degli OPPO (Reno, Find N,
# Find X di qualche anno fa). NON copre la serie A di OPPO, né realme,
# né vivo: per quelli la risposta onesta resta «nessuna fonte».
ARB_README_URL = oplus_arb.URL_README

_arb_cache: list | None = None
_arb_errore: str | None = None
_arb_scaricato_a: float | None = None
_ARB_TTL_SECONDI = 6 * 60 * 60


def _arb_rilasci(forza: bool = False):
    """Build correnti dal tracker ARB, con cache a tempo."""
    global _arb_cache, _arb_errore, _arb_scaricato_a

    fresca = (
        _arb_cache is not None
        and _arb_scaricato_a is not None
        and (time.monotonic() - _arb_scaricato_a) < _ARB_TTL_SECONDI
    )
    if fresca and not forza:
        return _arb_cache, _arb_errore

    try:
        risposta = http_get(ARB_README_URL)
    except Exception as exc:
        _arb_cache, _arb_errore = [], f"tracker ARB non raggiungibile: {exc}"
        _arb_scaricato_a = time.monotonic()
        return _arb_cache, _arb_errore

    codice = getattr(risposta, "status_code", 0)
    if codice != 200:
        _arb_cache, _arb_errore = [], f"HTTP {codice} da {ARB_README_URL}"
        _arb_scaricato_a = time.monotonic()
        return _arb_cache, _arb_errore

    rilasci, errore = oplus_arb.rilasci_da_readme(getattr(risposta, "text", "") or "")
    _arb_cache, _arb_errore = rilasci, errore
    _arb_scaricato_a = time.monotonic()
    return _arb_cache, _arb_errore


def reset_arb_cache() -> None:
    global _arb_cache, _arb_errore, _arb_scaricato_a
    _arb_cache = None
    _arb_errore = None
    _arb_scaricato_a = None


def _chiave_versione(rilascio) -> tuple:
    """Ordina le build per anzianità. Le build di vecchio stile
    (`CPH2611_11_A.65`), che non espongono una versione numerica
    confrontabile, finiscono in fondo invece di essere scartate."""
    if not rilascio.skin_version:
        return (0,)
    try:
        return (1,) + tuple(int(p) for p in rilascio.skin_version.split("."))
    except ValueError:
        return (0,)


# QUALE REGIONE DIVENTA «IL» RISULTATO, quando la ricerca ne trova più di
# una per lo stesso telefono. Segnalato dall'utente: cercando un modello
# non deve comparire una variante a caso, ma la europea in priorità — lo
# stesso principio già applicato a Samsung (`_ORDINE_MERCATI_SAMSUNG`),
# qui esteso alla fonte che nomina esplicitamente «Europe»/«Global» come
# regione (vedi il docstring di `_lookup_oplus_arb`: OnePlus 13 è
# `CPH2653` in Europa e `CPH2649` in India, con build che non procedono di
# pari passo — prima di questo fix vinceva quella con la build più
# recente, non quella europea, ed è esattamente il "modello a caso"
# segnalato).
#
# «Global» subito dopo «Europe»: è la build che OnePlus/OPPO distribuisce
# fuori da un mercato specifico, quella più vicina a un dispositivo
# comprato in Europa quando non esiste una riga «Europe» dedicata.
_ORDINE_REGIONI_ARB = ("EUROPE", "GLOBAL")


def _rango_regione_arb(regione: str) -> int:
    chiave = (regione or "").strip().upper()
    try:
        return _ORDINE_REGIONI_ARB.index(chiave)
    except ValueError:
        # Regione non elencata (India, North America, China, ...): dopo
        # quelle note, in qualunque ordine avessero fra loro — build più
        # recente prima, come già era prima di questo fix.
        return len(_ORDINE_REGIONI_ARB)


def _arb_item(rilascio, con_regione: bool = True) -> RawItem:
    descrizione = ["Tracker ARB OnePlus/OPPO (non ufficiale)", rilascio.model_code]
    if con_regione and rilascio.region:
        descrizione.append(f"regione {rilascio.region}")
    if rilascio.canale_build:
        descrizione.append(rilascio.canale_build)
    if rilascio.arb_nota:
        descrizione.append(rilascio.arb_nota)

    titolo = f"{rilascio.device_name} — {rilascio.build}"
    if rilascio.region:
        titolo += f" [{rilascio.region}]"

    riepilogo = ""
    if rilascio.last_checked:
        # È la data in cui il TRACKER ha visto quella build, non quella in
        # cui OnePlus l'ha distribuita. Detta com'è, invece di essere
        # spacciata per data di rilascio.
        riepilogo = f"Build vista dal tracker il {rilascio.last_checked}."

    # Dal 14 in poi OPPO associa in modo esplicito il numero principale di
    # ColorOS a quello di Android (ColorOS 14 -> Android 14, 15 -> 15,
    # 16 -> 16). Non si indovinano le versioni precedenti né si ricava un
    # Android dalla sola build: il tracker espone già la versione ColorOS.
    android_da_coloros = _android_da_coloros(rilascio.skin_version)

    return RawItem(
        title=titolo,
        link=rilascio.link,
        published=None,
        brand=C.OPPO,
        device=rilascio.device_name,
        # Il README dichiara il codice esatto per regione (CPH2525EEA,
        # CPH2653, ...). Perderlo qui impediva la ricerca da IMEI/TAC.
        model_code=rilascio.model_code,
        version=rilascio.skin_version,
        build=rilascio.build,
        android_version=android_da_coloros,
        summary=riepilogo,
        size_info=" · ".join(p for p in descrizione if p),
        trust=C.TRUST_CURATED,
    )


def _android_da_coloros(versione: str | None) -> int | None:
    """Versione Android documentata per ColorOS 14, 15 e 16.

    La conversione resta volontariamente limitata alle tre associazioni
    pubblicate da OPPO. Un formato sconosciuto restituisce ``None`` invece
    di una versione Android soltanto plausibile.
    """
    match = re.match(r"^(14|15|16)(?:\.\d+){0,3}$", (versione or "").strip())
    return int(match.group(1)) if match else None


def fetch_oplus_arb() -> tuple[list[RawItem], str | None]:
    """Una voce per dispositivo, con la build più avanzata fra le regioni.

    Nel giro periodico si tiene un solo rilascio per telefono: l'archivio
    è indicizzato per dispositivo, quindi cinque regioni dello stesso
    OnePlus 13 si sovrascriverebbero a vicenda lasciando in memoria
    l'ultima arrivata invece della più significativa. Le altre regioni
    restano visibili nella ricerca a comando, dove servono davvero.
    """
    rilasci, errore = _arb_rilasci()
    if errore:
        return [], errore

    migliori: dict[str, object] = {}
    for rilascio in rilasci:
        attuale = migliori.get(rilascio.device_name)
        if attuale is None or _chiave_versione(rilascio) > _chiave_versione(attuale):
            migliori[rilascio.device_name] = rilascio
    return [_arb_item(r) for r in migliori.values()], None


def _lookup_oplus_arb(model_name: str) -> list[RawItem]:
    """Ricerca a comando: per codice modello o per nome commerciale.

    Restituisce PIÙ regioni quando esistono, perché è l'informazione che
    il tracker ha in più di chiunque altro: lo stesso OnePlus 13 è
    CPH2653 in Europa e CPH2649 in India, con build che non procedono di
    pari passo. Per un parco di test misto, sapere quale delle due si ha
    in mano è metà del lavoro.

    TUTTE le regioni trovate restano nel risultato — nessuna sparisce —
    ma **la prima è la europea**, quando c'è: `web/main.py::
    _cerca_davvero` mostra come risultato principale il primo elemento
    strutturato, quindi l'ordine qui decide quale variante regionale
    diventa «il» risultato di una ricerca generica. Prima di questo fix
    vinceva la build più recente qualunque fosse la regione — segnalato
    dall'utente come «mi spunta un modello a caso» — vedi
    `_rango_regione_arb`.
    """
    testo = (model_name or "").strip()
    if not testo:
        return []

    rilasci, errore = _arb_rilasci()
    if errore or not rilasci:
        return []

    codici = {c.upper() for c in _code_candidates(testo)}
    codici.update(c.upper() for c in modelcodes.codes_for_name(testo))
    atteso = extract.canonical_device(testo).lower()

    trovati = []
    for rilascio in rilasci:
        codice = rilascio.model_code.upper()
        # Confronto anche col codice base: chi cerca «CPH2525» deve
        # trovare la riga europea che si chiama «CPH2525EEA».
        base = re.match(r"^[A-Z]{2,4}\d{3,4}", codice)
        per_codice = codice in codici or (base and base.group(0) in codici)
        per_nome = (rilascio.device_name.lower() == atteso
                    or extract.canonical_device(rilascio.device_name).lower() == atteso)
        if per_codice or per_nome:
            trovati.append(rilascio)

    # Due passaggi, entrambi stabili: prima la build più recente decide
    # l'ordine ALL'INTERNO di ogni regione, poi la regione (Europa, poi
    # Global, poi le altre) decide l'ordine FRA le regioni — senza
    # scartare né mescolare a caso chi arriva dopo.
    trovati.sort(key=_chiave_versione, reverse=True)
    trovati.sort(key=lambda r: _rango_regione_arb(r.region))
    return [_arb_item(r) for r in trovati[:5]]


def fetch_oplus_telegram() -> tuple[list[RawItem], str | None]:
    """Build confermate di OnePlus/Oppo/realme dal canale di rollout."""
    rilasci, errore = _telegram_rilasci()
    if errore:
        return [], errore
    items = []
    for rilascio in rilasci:
        item = _item_da_rilascio(rilascio)
        if item is not None:
            items.append(item)
    return items, None


def _lookup_oplus_telegram(model_name: str) -> list[RawItem]:
    """Ricerca a comando nel canale, per nome commerciale o per codice.

    Cercare per codice funziona anche quando il post non nominava il
    telefono: chi digita «CPH2613» ottiene la sua build, ed è il caso in
    cui le altre fonti Oppo restituiscono solo «esiste, versione ignota».
    """
    testo = (model_name or "").strip()
    if not testo:
        return []

    rilasci, errore = _telegram_rilasci()
    if errore or not rilasci:
        return []

    codici_cercati = {c.upper() for c in _code_candidates(testo)}
    codici_cercati.update(c.upper() for c in modelcodes.codes_for_name(testo))
    atteso = extract.canonical_device(testo).lower()

    trovati = []
    for rilascio in rilasci:
        per_codice = bool(rilascio.model_code
                          and rilascio.model_code.upper() in codici_cercati)
        nome = rilascio.device_name or _nome_per_codice(rilascio.model_code)
        per_nome = bool(nome and (
            nome.lower() == atteso
            or extract.canonical_device(nome).lower() == atteso
        ))
        if per_codice or per_nome:
            item = _item_da_rilascio(rilascio, nome_forzato=nome or None)
            if item is not None:
                trovati.append(item)

    # Più rilasci per lo stesso telefono (regioni o mesi diversi): vince
    # il livello di patch più alto, non il primo incontrato.
    trovati.sort(key=lambda i: i.summary or "", reverse=True)
    return trovati[:3]


def fetch_coloros_news():
    """Notizie dedicate agli aggiornamenti ColorOS (Oppo e OnePlus).

    Per questi marchi non esiste una fonte che pubblichi la versione per
    singolo dispositivo: gli annunci di rilascio passano dai canali
    ufficiali e vengono ripresi dalle testate. Query brevi e separate,
    come per gli altri brand senza fonte strutturata.
    """
    queries = [
        "ColorOS update rollout",
        "ColorOS security patch",
        "Oppo ColorOS version",
        "OnePlus OxygenOS rollout",
    ]
    return _merge_news_queries(queries, C.OPPO, "Aggiornamenti ColorOS")


REALME_AER_URL = "https://www.realme.com/global/legal/AndroidSecurityAdvisories"

# realme non espone un catalogo OTA pubblico per i modelli recenti. Questo
# archivio tecnico non viene quindi mai trattato come fonte ufficiale o come
# risposta "ultimo OTA": serve a riportare una build osservabile, soltanto
# dopo che il codice RMX e' stato verificato nella pagina ufficiale realme.
#
# La ricerca per codice è preferita al tag: per RMX3939 il tag è incompleto e
# ometteva la C.16 Export, mentre le prime quattro pagine di ricerca contengono
# sia la C.14 GDPR sia la C.16. Le quattro piccole pagine sono richieste in
# parallelo, quindi non si scarica mai un catalogo globale né si supera il
# budget interattivo.
REALME_FIRMWARE_ARCHIVE_URL = (
    "https://support.halabtech.com/index.php?a=downloads&b=search&keyword={codice}&p_start={pagina}"
)
_REALME_FIRMWARE_RE = re.compile(
    r"\b(?P<codice>RMX\d{4}[A-Z]*)(?P<regione>GDPR|export)_"
    r"(?P<android>\d{2})_(?P<ramo>[A-Z])\.(?P<revisione>\d+)_"
    r"(?P<data>\d{14})",
    re.IGNORECASE,
)
# Dal 2025 l'indice contiene anche i pacchetti service nel nuovo formato.
# Sono gli stessi file RMX, ma non hanno più ``_15_C.14_`` nel nome:
#
#   RMX5011GDPR_11_16.0.3.500EX01_20260305010156.zip
#   RMX5011 16.0.3.500(EX01) [GDPR].zip
#
# Il primo non va confuso con il vecchio campo Android ``_15_``: ``_11_`` è
# parte del formato service. La versione Android certa è il primo numero
# della build 14.0/15.0/16.0, convenzione confermata dalle pagine prodotto
# realme (realme UI 6 = Android 15, realme UI 7 = Android 16). Limitare la
# deduzione a questi numeri evita di trasformare un'altra sigla in Android.
_REALME_FIRMWARE_MODERN_COMPACT_RE = re.compile(
    r"\b(?P<codice>(?:RMX|CPH)\d{4}[A-Z]*?)(?:\d{5})?(?P<regione>GDPR|export)_\d{2}_"
    r"(?P<versione>1[4-9](?:\.\d+){3})(?P<canale>[A-Z]{2}\d{2})"
    r"(?:_(?P<data>\d{14}))?(?:\.zip)?",
    re.IGNORECASE,
)
_REALME_FIRMWARE_MODERN_LABEL_RE = re.compile(
    r"\b(?P<codice>(?:RMX|CPH)\d{4}[A-Z]*?)\s+"
    r"(?P<versione>1[4-9](?:\.\d+){3})\((?P<canale>[A-Z]{2}\d{2})\)\s+"
    r"\[(?P<regione>GDPR|export)\](?:\.zip)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _PacchettoRealme:
    """Metadati del nome di un pacchetto realme, senza inventare un OTA.

    ``data`` è presente soltanto nei nomi che la espongono. Non viene
    sostituita dalla data di caricamento dell'archivio, che è un fatto
    diverso e può far sembrare più recente un file ripubblicato.
    """

    codice: str
    regione: str
    build: str
    android: int | None
    data: str | None
    filename: str
# Mai un catalogo intero in memoria: fino a 32 codici richiesti di recente,
# con al massimo due RawItem piccoli per codice (Europa e globale).
_REALME_FIRMWARE_TTL = 60 * 60
_REALME_FIRMWARE_SEARCH_PAGES = 4
_realme_firmware_cache: dict[str, tuple[float, list[RawItem]]] = {}
_realme_firmware_cache_lock = threading.Lock()

# ATTENZIONE AL FORMATO SU CUI SI LAVORA (errore già commesso):
# `_realme_page` sostituisce i tag HTML con un a capo, quindi il testo che
# arriva qui ha i campi separati da NEWLINE, non da pipe. La prima versione
# di questa regex cercava le pipe «|» perché era stata costruita sulla resa
# in markdown della pagina — quella che si vede con uno strumento di
# lettura web, non quella che riceve il codice. Risultato: pagina scaricata
# correttamente, zero righe riconosciute.
# Il separatore ammette ora entrambe le forme, così la regex regge sia
# l'HTML sia una eventuale resa tabellare.
_REALME_AER_RE = re.compile(
    r"(realme[^|\n]{0,60}?)[|\s]+Security update support end date:\s*(\d{1,2}/\d{4})"
    r"[|\s]+Shipped version:\s*Android\s*(\d{1,2})"
    r"[|\s]*Future version:\s*Android\s*(\d{1,2})",
    re.IGNORECASE,
)
# «realme C63/Narzo 63/C61（RMX3939）» — parentesi a larghezza piena e più
# codici separati da virgola ideografica.
_REALME_CODE_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 +/\.]*?)\s*[（(]\s*([A-Z]{3}\d{4}[^）)]*)\s*[）)]"
)
_REALME_MONTHLY_MARKER = "once a month"
_REALME_QUARTERLY_MARKER = "every quarter"


# LA PAGINA realme SI SCARICAVA A OGNI DOMANDA, E PIÙ VOLTE PER DOMANDA.
# Honor e vivo hanno una cache (`_honor_aer_cache`, `_vivo_aer_cache`),
# realme no: era rimasta l'unica delle tre pagine AER senza. Il conto
# misurato il 2026-08-11, con un cronometro sulle chiamate a `http_get`:
#
#   * `fetch_realme_aer()` scaricava la pagina DUE volte — una qui e una
#     dentro `realme_official_codes()`, che la richiede di nuovo per la
#     mappatura dei codici;
#   * `lookup_model_structured` interroga ogni fonte con TUTTE le forme
#     equivalenti della ricerca (per «c63» sono cinque), e ognuna rifaceva
#     il giro;
#   * risultato: la ricerca di «c63» durava **15,4 secondi** contro un
#     tetto di 12 (`C.SEARCH_BUDGET_SECONDS`). Il tempo finiva prima che
#     la fonte realme rispondesse, e chi cercava un realme C63 riceveva un
#     «POCO C61/Redmi A3 India» — l'unica fonte che aveva fatto in tempo.
#
# La cache sta sul TESTO della pagina e non sull'elenco di dispositivi,
# perché è il testo che serve a tutti e due i lettori: così `fetch_realme_aer`
# e `realme_official_codes` scaricano insieme una volta sola.
_realme_pagina_cache = _CacheDiFonte(_AER_TTL_SECONDI)


def reset_realme_aer_cache() -> None:
    """Azzera la cache della pagina realme AER (usata dai test)."""
    _realme_pagina_cache.azzera()


def reset_realme_firmware_cache() -> None:
    """Azzera le piccole risposte per codice dell'archivio tecnico realme.

    È separata dalla cache AER: la prima contiene l'elenco ufficiale dei
    codici, la seconda soltanto gli ultimi due nomi di pacchetto osservati.
    """
    with _realme_firmware_cache_lock:
        _realme_firmware_cache.clear()


def _realme_page() -> tuple[str | None, str | None]:
    return _realme_pagina_cache.ottieni(_realme_page_scarica)


def _realme_page_scarica() -> tuple[str | None, str | None]:
    try:
        response = http_get(REALME_AER_URL, timeout=C.HTTP_TIMEOUT + 10)
    except Exception as exc:
        return None, f"connessione fallita: {exc}"
    if response.status_code != 200:
        return None, f"HTTP {response.status_code}"
    testo = re.sub(r"<[^>]+>", "\n", response.text)
    return re.sub(r"[ \t]+", " ", testo), None


def realme_official_codes() -> dict[str, tuple[str, str]]:
    """Mappatura ufficiale codice → (nome commerciale, cadenza patch).

    Fonte di prima mano: è realme stessa a pubblicare questo elenco, quindi
    è più autorevole dei dataset community usati per gli altri brand.
    """
    testo, error = _realme_page()
    if not testo:
        return {}
    inizio_trimestrale = testo.lower().find(_REALME_QUARTERLY_MARKER)
    mappa: dict[str, tuple[str, str]] = {}
    for match in _REALME_CODE_RE.finditer(testo):
        nome = " ".join(match.group(1).split())
        if not nome.lower().startswith(("realme", "narzo", "note")):
            continue
        cadenza = ("trimestrale" if inizio_trimestrale != -1 and match.start() > inizio_trimestrale
                   else "mensile")
        for codice in re.split(r"[、,]", match.group(2)):
            codice = codice.strip().upper()
            if re.fullmatch(r"[A-Z]{3}\d{4}[A-Z]*", codice):
                mappa.setdefault(codice, (nome, cadenza))
    return mappa


def fetch_realme_aer() -> tuple[list[RawItem], str | None]:
    testo, error = _realme_page()
    if not testo:
        return [], error

    codici_per_nome: dict[str, list[str]] = {}
    for codice, (nome, _) in realme_official_codes().items():
        codici_per_nome.setdefault(nome.lower(), []).append(codice)

    items = []
    visti = set()
    for match in _REALME_AER_RE.finditer(testo):
        nome_raw, fine_supporto, shipped, future = match.groups()
        nome = " ".join(nome_raw.split())
        if nome in visti:
            continue
        visti.add(nome)
        codici = codici_per_nome.get(nome.lower(), [])
        etichetta_codici = f" ({', '.join(codici)})" if codici else ""
        items.append(
            RawItem(
                title=(
                    f"{nome}{etichetta_codici} — Android {shipped} di fabbrica; "
                    f"aggiornamenti garantiti almeno fino ad Android {future}, "
                    f"patch di sicurezza fino a {fine_supporto}"
                ),
                link=REALME_AER_URL,
                brand=C.OPPO,
                device=nome,
                # Versione EFFETTIVA di fabbrica, MAI la promessa futura
                # (vedi la nota in testa a questa sezione).
                android_version=int(shipped),
                size_info=(
                    "Piano ufficiale realme Android Enterprise Recommended — "
                    f"supporto sicurezza fino a {fine_supporto}"
                ),
            )
        )
    if not items:
        return [], "pagina raggiungibile ma nessuna riga dispositivo riconosciuta (formato cambiato?)"
    return items, None


def realme_name_variants() -> dict[str, tuple[list[str], str]]:
    """Ogni singolo nome commerciale → (nomi fratelli, codice).

    realme registra sotto un unico codice più nomi regionali dello stesso
    telefono, e li scrive uniti: «realme C63/Narzo 63/C61（RMX3939）». Chi
    cerca «realme C63» non trova nulla se si confronta solo con la stringa
    intera, e nemmeno nella tabella AER, dove quel modello compare con un
    altro dei suoi nomi (C61). Qui il nome composto viene scomposto nei
    singoli nomi, ciascuno collegato ai propri fratelli: così partendo da
    uno qualsiasi si arriva al dato pubblicato sotto un altro.
    """
    varianti: dict[str, tuple[list[str], str]] = {}
    for codice, (composto, _cadenza) in realme_official_codes().items():
        pezzi = [p.strip() for p in composto.split("/") if p.strip()]
        if not pezzi:
            continue
        prefisso = pezzi[0].split()[0] if pezzi[0].split() else ""
        nomi_completi = []
        for pezzo in pezzi:
            if prefisso and not pezzo.lower().startswith(prefisso.lower()):
                pezzo = f"{prefisso} {pezzo}"
            nomi_completi.append(pezzo)
        for nome in nomi_completi:
            chiave = modelcodes._normalize_name(nome)
            if chiave:
                varianti.setdefault(chiave, (nomi_completi, codice))
    return varianti


def _realme_nomi_ambigui() -> set[str]:
    """Nomi (normalizzati) che l'elenco ufficiale realme usa per PIÙ DI UN
    gruppo di dispositivi diversi — vedi il docstring di `_lookup_realme`
    per il bug reale che questo controllo esiste per evitare.

    `realme_official_codes()` è la mappatura AUTOREVOLE codice→gruppo, ma
    un gruppo composto («realme C63/Narzo 63/C61») e una voce a sé stante
    («realme C61», un ALTRO codice) possono condividere un pezzo di nome:
    la pagina ufficiale realme lo fa davvero, non è un'invenzione del
    dataset community.

    ## Non basta "più di un codice rivendica questo nome"

    realme raggruppa anche le varianti REGIONALI dello stesso telefono
    sotto più codici con lo STESSO gruppo di nomi, es. «realme 9i
    （RMX3491、RMX3492、RMX3493）»: tre codici, un solo nome, nessuna
    ambiguità reale — sono lo stesso telefono. Contare solo "quanti
    codici" (come una prima versione di questa funzione faceva)
    marcherebbe «realme 9i» come ambiguo e romperebbe la ricerca per quel
    nome, lo stesso errore misurato e corretto in
    `modelcodes.resolve_senza_ambiguita()` per il caso Samsung
    SM-A325F/M/N → «Galaxy A32».

    Un nome è ambiguo solo se i codici che lo rivendicano NON hanno tutti
    lo stesso gruppo completo di nomi — cioè se scomporre i loro gruppi
    ufficiali produce insiemi diversi. Quando è così, quel nome non
    identifica un telefono solo, e va tolto dai candidati di ricerca.
    """
    per_nome: dict[str, set[str]] = {}
    gruppo_per_codice: dict[str, frozenset[str]] = {}
    for codice, (composto, _cadenza) in realme_official_codes().items():
        pezzi = {modelcodes._normalize_name(p) for p in _realme_espandi(composto)}
        pezzi.discard("")
        gruppo_per_codice[codice] = frozenset(pezzi)
        for chiave in pezzi:
            per_nome.setdefault(chiave, set()).add(codice)
    return {
        nome for nome, codici in per_nome.items()
        if len({gruppo_per_codice[c] for c in codici}) > 1
    }


def _lookup_realme(model_name: str) -> list[RawItem]:
    """Ricerca a comando su realme, accettando il nome commerciale, uno dei
    nomi regionali alternativi, o il codice ufficiale.

    realme riusa uno stesso codice per più modelli regionali e li elenca
    come un unico nome composto separato da «/», mentre la tabella con le
    versioni ne riporta solo uno. Vanno quindi provati tutti i nomi del
    gruppo, altrimenti un modello legittimo non trova la propria riga —
    ECCETTO i nomi ambigui (`_realme_nomi_ambigui`), che restano esclusi
    anche da questo elenco: vedi il docstring lì sopra.
    """
    query = (model_name or "").strip()
    if not query:
        return []

    candidati = [query]
    codice_trovato = None

    # Partendo da un codice: si espande nei nomi del gruppo.
    codice = re.sub(r"\s+", "", query).upper()
    if re.fullmatch(r"[A-Z]{3}\d{4}[A-Z]*", codice):
        voce = realme_official_codes().get(codice)
        if voce:
            codice_trovato = codice
            candidati = _realme_espandi(voce[0]) + candidati

    # Partendo da uno dei nomi del gruppo: si recuperano i fratelli.
    if not codice_trovato:
        variante = realme_name_variants().get(modelcodes._normalize_name(query))
        if variante:
            fratelli, codice_trovato = variante
            candidati = fratelli + candidati

    # BUG REALE, segnalato dall'utente con uno screenshot: cercando
    # `RMX3939` (gruppo ufficiale «realme C63/Narzo 63/C61») la pagina
    # mostrava i dati di un telefono realme del tutto diverso, pubblicato
    # sotto lo stesso nome «realme C61» ma con un proprio codice a sé —
    # la stessa sigla «C61» compare DUE volte nella pagina ufficiale
    # realme, in due gruppi diversi. Un pezzo scomposto dal gruppo di
    # RMX3939 («realme C61») combaciava per errore con la riga A SÉ
    # STANTE dell'ALTRO codice, che quel nome lo usa davvero da solo.
    #
    # Non si tolgono TUTTI i nomi scomposti (romperebbe la ricerca per
    # nome che questa stessa funzione esiste per abilitare, es. cercare
    # «C63» e trovare il dato pubblicato sotto «C61» — caso comune, senza
    # conflitto), solo quelli che l'elenco ufficiale stesso associa a più
    # di un codice: quelli, e solo quelli, non identificano un telefono
    # solo.
    ambigui = _realme_nomi_ambigui()
    candidati = [c for c in candidati
                if modelcodes._normalize_name(c) not in ambigui]

    tutti, error = fetch_realme_aer()
    if error or not tutti:
        return []

    # IL CODICE, QUANDO NE HA UNO SCRITTO ADDOSSO, NON HA MAI QUESTA
    # AMBIGUITÀ — anche quando il nome sì. Una riga la cui etichetta cita
    # per davvero `codice_trovato` (perché `codici_per_nome`, dentro
    # `fetch_realme_aer()`, l'ha già abbinata con un confronto ESATTO
    # sull'intero gruppo ufficiale) è una prova più forte di qualunque
    # nome scomposto, ambiguo o no: si prova PRIMA di tutto il resto.
    if codice_trovato:
        per_codice = [
            i for i in tutti
            if re.search(rf"\b{re.escape(codice_trovato)}\b", i.title or "")
        ]
        if per_codice:
            return [_realme_etichetta(per_codice[0], query, codice_trovato)]

    for candidato in candidati:
        bersaglio = modelcodes._normalize_name(candidato)
        if not bersaglio:
            continue
        esatti = [i for i in tutti if modelcodes._normalize_name(i.device or "") == bersaglio]
        if esatti:
            return [_realme_etichetta(esatti[0], query, codice_trovato)]
    for candidato in candidati:
        bersaglio = modelcodes._normalize_name(candidato)
        parziali = [i for i in tutti if bersaglio and bersaglio in modelcodes._normalize_name(i.device or "")]
        if parziali:
            return [_realme_etichetta(parziali[0], query, codice_trovato)]
    return []


def _realme_espandi(composto: str) -> list[str]:
    pezzi = [p.strip() for p in composto.split("/") if p.strip()]
    if not pezzi:
        return []
    prefisso = pezzi[0].split()[0] if pezzi[0].split() else ""
    espansi = []
    for pezzo in pezzi:
        if prefisso and not pezzo.lower().startswith(prefisso.lower()):
            pezzo = f"{prefisso} {pezzo}"
        espansi.append(pezzo)
    return espansi


def _realme_codice_verificato(query: str) -> tuple[str, str] | None:
    """Restituisce `(codice, nome)` solo se realme lo dichiara ufficialmente.

    Il catalogo tecnico da solo non basta a collegare un file a un telefono:
    nomi come C61 sono riusati. Il codice RMX risolve quell'ambiguità; prima
    si controlla nella pagina di realme, poi si consulta l'archivio.
    """
    testo = (query or "").strip()
    if not testo:
        return None
    ufficiali = realme_official_codes()
    codice = re.sub(r"\s+", "", testo).upper()
    if codice in ufficiali:
        return codice, ufficiali[codice][0]
    variante = realme_name_variants().get(modelcodes._normalize_name(testo))
    if variante and variante[1] in ufficiali:
        codice = variante[1]
        return codice, ufficiali[codice][0]
    return None


def _realme_data_pacchetto(valore: str) -> str:
    """Data interna `AAAAMMGGhhmmss`, formattata senza fingere un rilascio."""
    if len(valore) != 14:
        return valore
    return f"{valore[6:8]}/{valore[4:6]}/{valore[:4]}"


def _android_da_build_realme(versione: str) -> int | None:
    """Major Android dichiarato implicitamente dalle build realme recenti.

    I nomi service moderni hanno una build come ``16.0.3.500(EX01)`` e un
    campo intermedio ``_11_`` che *non* è Android. Per i rami 14--19 il
    primo componente è invece quello della generazione Android/realme UI;
    al di fuori di quel formato non si indovina nulla.
    """
    primo = (versione or "").split(".", 1)[0]
    try:
        android = int(primo)
    except ValueError:
        return None
    return android if 14 <= android <= C.MAX_PLAUSIBLE_ANDROID else None


def _pacchetti_realme_da_testo(testo: str) -> list[_PacchettoRealme]:
    """Legge tutti i formati RMX usati dall'archivio tecnico.

    La funzione è separata dalla rete per poterla testare con i nomi reali
    di pacchetto: la regressione era nel parser, non nel download.
    """
    pacchetti: list[_PacchettoRealme] = []
    visti: set[tuple[str, str, str]] = set()

    def aggiungi(pacchetto: _PacchettoRealme) -> None:
        chiave = (pacchetto.codice, pacchetto.regione, pacchetto.filename)
        if chiave not in visti:
            visti.add(chiave)
            pacchetti.append(pacchetto)

    for match in _REALME_FIRMWARE_RE.finditer(testo):
        android = int(match.group("android"))
        filename = match.group(0) + ".zip"
        aggiungi(_PacchettoRealme(
            codice=match.group("codice").upper(),
            regione=match.group("regione").upper(),
            build=f"{match.group('ramo').upper()}.{match.group('revisione')}",
            android=android,
            data=match.group("data"),
            filename=filename,
        ))

    for parser in (_REALME_FIRMWARE_MODERN_COMPACT_RE,
                   _REALME_FIRMWARE_MODERN_LABEL_RE):
        for match in parser.finditer(testo):
            versione = match.group("versione")
            canale = match.group("canale").upper()
            raw = match.group(0)
            filename = raw if raw.lower().endswith(".zip") else raw + ".zip"
            aggiungi(_PacchettoRealme(
                codice=match.group("codice").upper(),
                regione=match.group("regione").upper(),
                build=f"{versione}({canale})",
                android=_android_da_build_realme(versione),
                data=match.groupdict().get("data"),
                filename=filename,
            ))
    return pacchetti


def _chiave_pacchetto_realme(pacchetto: _PacchettoRealme) -> tuple:
    """Ordine stabile dentro un ramo regionale, senza comparare GDPR/Export.

    Prima la major Android, poi (nei pacchetti moderni) i numeri della build
    e solo dopo la data interna. Così una 16.0.3 senza data nel titolo non
    viene scavalcata da una 16.0.2 più vecchia che esponeva un timestamp.
    """
    moderno = bool(re.match(r"^\d+\.", pacchetto.build))
    numeri = tuple(int(x) for x in re.findall(r"\d+", pacchetto.build))
    return (pacchetto.android or 0, moderno, numeri, pacchetto.data or "")


def _lookup_realme_firmware_archive(model_name: str,
                                    _verificato: tuple[str, str] | None = None,
                                    _nome_fonte: str = "realme",
                                    _verifica: str = "confermato da realme") -> list[RawItem]:
    """Build realme riportate da archivio tecnico, ordinate Europa → globale.

    La fonte non conosce lo stato OTA di uno specifico telefono e può
    ospitare copie non ufficiali: è dunque `CURATED` + `REPORTED`, mai
    `CURRENT`. Il codice, la regione e Android vengono letti dal *nome del
    pacchetto* (non dalla descrizione editoriale, che per RMX3939 riporta
    Android 16 nonostante il pacchetto dica chiaramente `_15_`).
    """
    trovato = _verificato or _realme_codice_verificato(model_name)
    if not trovato:
        return []
    codice, nome_composto = trovato
    ora = time.monotonic()
    with _realme_firmware_cache_lock:
        in_cache = _realme_firmware_cache.get(codice)
        if in_cache and ora - in_cache[0] < _REALME_FIRMWARE_TTL:
            return list(in_cache[1])

    # Una build per ramo regionale: il numero C.16 Export non e' comparabile
    # con C.14 GDPR. La data interna al pacchetto, non la data di caricamento
    # dell'archivio, indica quale sia la copia più recente nel singolo ramo.
    # GDPR e Export restano rami separati: la priorità europea è nell'ordine
    # di presentazione, non un confronto arbitrario fra le loro revisioni.
    per_regione: dict[str, _PacchettoRealme] = {}
    urls = [
        REALME_FIRMWARE_ARCHIVE_URL.format(codice=codice, pagina=pagina)
        for pagina in range(1, _REALME_FIRMWARE_SEARCH_PAGES + 1)
    ]

    def scarica(url: str) -> tuple[str, bool]:
        try:
            risposta = http_get(url, timeout=C.SEARCH_HTTP_TIMEOUT)
        except Exception:
            return "", False
        if getattr(risposta, "status_code", 0) != 200:
            return "", False
        return getattr(risposta, "text", "") or "", True

    # Quattro pagine da ~160 KB in quattro worker sono un picco sotto 1 MB;
    # il contenuto è interpretato subito e non entra nella cache. In serie,
    # invece, quattro timeout da 5 s basterebbero a svuotare il budget di 12 s.
    with ThreadPoolExecutor(max_workers=_REALME_FIRMWARE_SEARCH_PAGES) as pool:
        pagine = list(pool.map(scarica, urls))
    tutte_risposte_ok = all(ok for _testo, ok in pagine)
    for testo, _ok in pagine:
        for pacchetto in _pacchetti_realme_da_testo(testo):
            if pacchetto.codice != codice:
                continue
            regione = pacchetto.regione
            precedente = per_regione.get(regione)
            if (precedente is None
                    or _chiave_pacchetto_realme(pacchetto) > _chiave_pacchetto_realme(precedente)):
                per_regione[regione] = pacchetto

    # Il primo nome dell'elenco ufficiale è quello di mercato principale;
    # RMX3939 diventa quindi "realme C63", non il C61 ambiguo.
    # L'elenco ufficiale realme può avere più nomi regionali; il catalogo
    # codici OPPO invece consegna già il nome singolo da mostrare.
    espansi = _realme_espandi(nome_composto) if _nome_fonte == "realme" else []
    device = espansi[0] if espansi else nome_composto
    items: list[RawItem] = []
    for regione in ("GDPR", "EXPORT"):
        record = per_regione.get(regione)
        if not record:
            continue
        area = "Europa (GDPR)" if regione == "GDPR" else "Globale / Export"
        versione = f"Android {record.android}" if record.android else None
        dettaglio_data = (
            f"Data interna del pacchetto: {_realme_data_pacchetto(record.data)}."
            if record.data else
            "Nome pacchetto senza data interna: non viene inventata una data di rilascio."
        )
        items.append(RawItem(
            title=f"{device} — {record.filename}",
            link=REALME_FIRMWARE_ARCHIVE_URL.format(codice=codice, pagina=1),
            brand=C.OPPO,
            device=device,
            model_code=codice,
            version=versione,
            build=record.build,
            android_version=record.android,
            size_info=(
                f"Archivio tecnico {_nome_fonte} · {area} · build riportata, non OTA ufficiale"
            ),
            summary=f"Codice {codice} {_verifica}. {dettaglio_data}",
            trust=C.TRUST_CURATED,
            firmware_kind=C.FW_REPORTED,
        ))

    # Anche «nessuna build trovata» è un esito utile se tutte le pagine hanno
    # risposto: per le forme equivalenti dello stesso RMX evita di ripetere
    # quattro GET senza alcuna possibilità di ottenere un dato diverso. Un
    # guasto di rete, invece, NON entra in cache e sarà ritentato.
    if items or tutte_risposte_ok:
        with _realme_firmware_cache_lock:
            # Il limite impedisce che una raffica di codici diversi trasformi
            # una cache di comodità in memoria trattenuta sul piano da 512 MB.
            if len(_realme_firmware_cache) >= 32:
                _realme_firmware_cache.pop(next(iter(_realme_firmware_cache)))
            _realme_firmware_cache[codice] = (ora, list(items))
    return items


_OPPO_ARCHIVIO_CODE_RE = re.compile(r"^CPH\d{4}[A-Z]*$", re.IGNORECASE)


def _oppo_codice_archivio_verificato(query: str) -> tuple[str, str] | None:
    """Codice CPH e nome commerciale per l'archivio tecnico OPPO.

    A differenza di realme, OPPO non pubblica un elenco ufficiale codice →
    nome per i modelli moderni. Il codice viene quindi accettato solo se il
    catalogo modelli locale lo conosce; una ricerca per nome procede soltanto
    quando identifica un solo CPH. Questo evita che «OPPO A5» interroghi a
    caso una variante regionale o una generazione omonima.
    """
    testo = (query or "").strip()
    diretto = re.sub(r"\s+", "", testo).upper()
    if _OPPO_ARCHIVIO_CODE_RE.fullmatch(diretto):
        candidati = [diretto]
    else:
        try:
            candidati = [c.upper() for c in modelcodes.codes_for_name(testo)
                          if _OPPO_ARCHIVIO_CODE_RE.fullmatch(c.upper())]
        except Exception:
            return None
        candidati = list(dict.fromkeys(candidati))
        if len(candidati) != 1:
            return None

    codice = candidati[0]
    try:
        nomi = modelcodes.resolve(codice)
    except Exception:
        return None
    if not nomi:
        return None
    # La scheda AER ufficiale, quando c'è, è la migliore disambiguazione dei
    # rebrand regionali (CPH2639: A3 Pro/A3/A80). Fuori da AER, le serie F e
    # K sono in genere la denominazione India/Cina dello stesso CPH: per la
    # priorità europea si preferisce una denominazione OPPO A/Reno/Find.
    aer = aer_catalog.lookup(codice)
    nome_aer = (aer or {}).get("device_model", "").split("/")[0].strip()
    if nome_aer:
        nome = nome_aer
    else:
        opzioni = [n for n in nomi if n.lower().startswith("oppo ")]
        opzioni = opzioni or nomi
        opzioni = sorted(opzioni, key=lambda n: bool(re.search(r"\b[FK]\d", n, re.I)))
        nome = opzioni[0]
        # «A6 Pro» e «A6 Pro 5G» non sono due grafie intercambiabili: il
        # suffisso distingue proprio la variante radio. Se il catalogo
        # associa quel CPH anche al nome 5G, non lo si elimina scegliendo
        # meccanicamente la stringa più corta (CPH2781 è questo caso).
        base = re.sub(r"\s+5G$", "", nome, flags=re.I).strip()
        variante_5g = next((n for n in opzioni
                            if n.lower().endswith(" 5g")
                            and re.sub(r"\s+5G$", "", n, flags=re.I).strip().lower()
                            == base.lower()), None)
        if variante_5g:
            nome = variante_5g
    return codice, nome


def _lookup_oppo_firmware_archive(model_name: str) -> list[RawItem]:
    """Build CPH riportate dall'archivio tecnico, GDPR prima di Export.

    Ha la stessa semantica prudente della fonte realme: il file è una build
    osservabile, non la risposta dell'OTA del telefono, dunque non diventa
    mai un firmware ``CURRENT``. È tuttavia più utile dei soli piani di
    rollout per la serie OPPO A, che il tracker ARB non copre.
    """
    trovato = _oppo_codice_archivio_verificato(model_name)
    if not trovato:
        return []
    return _lookup_realme_firmware_archive(
        model_name,
        _verificato=trovato,
        _nome_fonte="OPPO",
        _verifica="associato al modello dal catalogo dispositivi",
    )


def _realme_etichetta(item: RawItem, richiesto: str, codice: str | None) -> RawItem:
    """Se il dato è pubblicato sotto un nome regionale diverso da quello
    cercato, va detto: nascondere la differenza farebbe sembrare che la
    fonte parli esattamente del modello richiesto."""
    richiesto_pulito = " ".join(richiesto.split())
    if modelcodes._normalize_name(richiesto_pulito) == modelcodes._normalize_name(item.device or ""):
        return item
    nota_codice = f", codice {codice}" if codice else ""
    return RawItem(
        title=(
            f"{richiesto_pulito} — stesso dispositivo di «{item.device}»"
            f"{nota_codice}: {item.title}"
        ),
        link=item.link,
        published=item.published,
        brand=item.brand,
        device=item.device,
        version=item.version,
        build=item.build,
        android_version=item.android_version,
        size_info=(
            f"{item.size_info} · dato pubblicato sotto il nome regionale «{item.device}»"
        ),
    )


def fetch_oxygen_updater() -> tuple[list[RawItem], str | None]:
    """ATTENZIONE MANUTENZIONE: l'app OxygenUpdater ha sostituito questa API
    "v2.x/news" (tutte le notizie in un colpo) con una nuova API che richiede
    un ID dispositivo e un ID metodo di aggiornamento per ogni chiamata
    (endpoint tipo `news/{deviceId}/{updateMethodId}`), su un host non
    documentato pubblicamente. Riscriverla richiederebbe prima enumerare
    tutti i dispositivi e i loro metodi con chiamate separate: rimandato,
    nel frattempo si prova comunque il vecchio endpoint (potrebbe tornare
    a funzionare) e si ricade sulla ricerca Google News se fallisce."""
    data, error = fetch_json(OXYGEN_URLS)
    if isinstance(data, dict):
        data = _pick(data, "data", "news", "items", default=[])
    if not isinstance(data, list):
        return fetch_oppo_news_fallback(error)

    items = []
    for record in data[: C.MAX_ITEMS_PER_SOURCE]:
        if not isinstance(record, dict):
            continue
        title = clean_text(
            _pick(record, "title", "english_title", "title_en", "dutch_title", default="")
        )
        if not title:
            continue
        subtitle = clean_text(_pick(record, "subtitle", "english_subtitle", "summary", default=""))
        news_id = _pick(record, "id", "news_id")
        link = _pick(record, "url", "link", default="")
        if not link and news_id:
            link = f"https://oxygenupdater.com/news/{news_id}"
        items.append(
            RawItem(
                title=title,
                link=link,
                published=iso(_pick(record, "date_published", "datetime", "published_at", "date")),
                brand=C.OPPO,
                summary=subtitle,
                size_info="OxygenOS / ColorOS",
            )
        )
    if items:
        return items, None
    return fetch_oppo_news_fallback("JSON valido ma nessuna voce utile")


def fetch_oppo_news_fallback(previous_error: str | None):
    """Ricerca Google News come ripiego mentre l'API OxygenUpdater resta da
    riscrivere (vedi nota in fetch_oxygen_updater)."""
    queries = [
        "OnePlus update Android",
        "OnePlus OxygenOS",
        "Oppo ColorOS update",
        "realme update Android",
    ]
    items, error = _merge_news_queries(queries, C.OPPO, "OTA news (ripiego)")
    if items:
        return items, None
    return [], f"API OxygenUpdater non disponibile ({previous_error}); ripiego news anch'esso senza risultati ({error})"


# ======================================================================
# 4-6. Feed curati
# ======================================================================
def fetch_samsung():
    return rss_items(
        [
            "https://www.sammobile.com/category/firmware-news/feed/",
            "https://www.sammobile.com/feed/",
        ],
        C.SAMSUNG,
        "Firmware / One UI",
    )


# ======================================================================
# Samsung — controllo versione ufficiale (endpoint FOTA, senza download)
# ======================================================================
# `fota-cloud-dn.ospserver.net` è l'endpoint che i telefoni Samsung stessi
# interrogano per sapere se c'è un aggiornamento: nessuna autenticazione,
# nessun nonce (a differenza del protocollo FUS usato per lo *scaricamento*
# vero e proprio, molto più complesso). Risponde con un XML tipo:
#   <latest o="14">S928BXXU5CYA1/S928BOXM5CYA1/S928BXXU5CYA1</latest>
# dove "o" è la versione Android e il primo segmento è la build PDA.
#
# Copertura MANUALE, verificata modello per modello (S21→S24, A-series
# recenti, Z Fold/Flip 5-6). Codici da Samsung/GSMArena/samsung-parts.net.
SAMSUNG_FUS_DEVICES: list[tuple[str, str]] = [
    ("SM-S928B", "Galaxy S24 Ultra"),
    ("SM-S926B", "Galaxy S24+"),
    ("SM-S921B", "Galaxy S24"),
    ("SM-S721B", "Galaxy S24 FE"),
    ("SM-S918B", "Galaxy S23 Ultra"),
    ("SM-S916B", "Galaxy S23+"),
    ("SM-S911B", "Galaxy S23"),
    ("SM-S711B", "Galaxy S23 FE"),
    ("SM-S908B", "Galaxy S22 Ultra"),
    ("SM-S906B", "Galaxy S22+"),
    ("SM-S901B", "Galaxy S22"),
    ("SM-G998B", "Galaxy S21 Ultra"),
    ("SM-G996B", "Galaxy S21+"),
    ("SM-G991B", "Galaxy S21"),
    ("SM-F956B", "Galaxy Z Fold6"),
    ("SM-F741B", "Galaxy Z Flip6"),
    ("SM-F946B", "Galaxy Z Fold5"),
    ("SM-A556B", "Galaxy A55"),
    ("SM-A546B", "Galaxy A54"),
    ("SM-A356B", "Galaxy A35"),
    ("SM-A346B", "Galaxy A34"),
    ("SM-A256B", "Galaxy A25"),
    ("SM-A156B", "Galaxy A15"),
    ("SM-A057F", "Galaxy A05s"),
]

# CSC (region code) da provare in ordine: ITV = Italia, poi Europa generica.
# Non tutti i modelli pubblicano un firmware per ogni CSC, da qui il fallback.
# Region (CSC) provate in sequenza sull'endpoint FOTA.
#
# ERANO QUATTRO, TUTTE EUROPEE — ed era il motivo per cui un modello come
# `SM-A075F`, venduto soprattutto in India e in Asia, non restituiva NULLA:
# non perché il firmware non esista, ma perché nessuna delle quattro region
# interrogate lo distribuisce. La ricerca sembrava rotta e invece stava
# guardando nel posto sbagliato.
#
# L'ordine è deliberato: prima le region multi-paese, che coprono di più con
# una richiesta sola, poi i mercati singoli grandi. La ricerca si ferma alla
# prima che risponde, quindi una lista più lunga non costa tempo quando il
# modello è europeo — costa solo quando altrimenti non si troverebbe niente.
SAMSUNG_CSC_CANDIDATES = [
    # Multi-paese europee
    "EUX", "EUY", "DBT", "ITV", "XEO", "BTU", "XEF", "PHE", "NEE",
    # India, il mercato che mancava del tutto
    "INS", "INU", "IND",
    # Nord America
    "XAA", "TMB", "ATT", "VZW", "XAC",
    # Asia-Pacifico, Medio Oriente, Africa, America Latina
    "XSG", "XSA", "THL", "XME", "XTC", "ZTO", "CHC", "SEK", "KOO",
]

_SAMSUNG_VERSION_XML_RE = re.compile(
    r'<latest(?:\s+o=["\'](\d+)["\'])?[^>]*>([^<]+)</latest>', re.IGNORECASE
)


# Anno e mese sono codificati nelle ULTIME TRE lettere del PDA Samsung:
# `A325FXXSCDYB2` → `YB2` = anno Y (2025), mese B (febbraio), revisione 2.
# Serve a confrontare due build fra loro, che è l'unico modo di sapere
# quale regione ha il firmware più recente.
_ANNI_PDA = "RSTUVWXYZ"          # R=2018 … Z=2026
_MESI_PDA = "ABCDEFGHIJKL"       # A=gennaio … L=dicembre


def _eta_build_samsung(pda: str) -> tuple[int, int, str]:
    """(anno, mese, revisione) da un PDA. (0, 0, '') se non decodificabile."""
    coda = (pda or "").strip().upper()[-3:]
    if len(coda) < 3:
        return (0, 0, "")
    anno, mese, revisione = coda[0], coda[1], coda[2]
    if anno not in _ANNI_PDA or mese not in _MESI_PDA:
        return (0, 0, "")
    return (_ANNI_PDA.index(anno), _MESI_PDA.index(mese), revisione)


# Regioni interrogate SEMPRE, e confrontate fra loro. Non è la lista intera:
# sono otto regioni scelte per coprire i mercati principali, perché ognuna
# costa una richiesta e la scansione periodica le paga per ogni modello.
SAMSUNG_CSC_PRIMARIE = ["EUX", "DBT", "ITV", "XEF", "BTU", "INS", "XAA", "XSG"]


def _samsung_fus_latest(model: str) -> tuple[str | None, str | None, str | None]:
    """Ritorna (build_pda, android_version, csc_usato): il firmware PIÙ
    RECENTE fra le regioni interrogate.

    NON la prima regione che risponde, ed è una correzione di sostanza.
    Alcune regioni restano ferme a un firmware vecchio mentre il modello ha
    ricevuto altro altrove: per `SM-A325F` la regione `EUX` — che era la
    prima della lista — dichiara **Android 11**, mentre tredici altre
    regioni danno **Android 13**. L'app riportava quindi Android 11 per un
    telefono aggiornato ad Android 13, e lo faceva con l'aria del dato
    ufficiale.

    Le regioni si interrogano in parallelo e si confronta il risultato:
    prima la versione di Android, poi la data codificata nel PDA. Se non si
    trova niente fra le primarie si allarga alle altre, perché un modello
    venduto in un solo mercato non deve sparire.
    """
    def _una(csc: str):
        url = f"https://fota-cloud-dn.ospserver.net/firmware/{csc}/{model}/version.xml"
        testo = _fota_get(url)
        if not testo:
            return None
        match = _SAMSUNG_VERSION_XML_RE.search(testo)
        if not match:
            return None
        android_version, versions = match.groups()
        pda = versions.split("/")[0].strip()
        if not pda:
            return None
        return pda, android_version, csc

    def _migliore(regioni):
        esiti = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            for esito in pool.map(_una, regioni):
                if esito:
                    esiti.append(esito)
        if not esiti:
            return None
        return max(esiti, key=lambda e: (int(e[1] or 0), _eta_build_samsung(e[0])))

    trovato = _migliore(SAMSUNG_CSC_PRIMARIE)
    if trovato:
        return trovato

    restanti = [c for c in SAMSUNG_CSC_CANDIDATES if c not in SAMSUNG_CSC_PRIMARIE]
    trovato = _migliore(restanti)
    if trovato:
        return trovato
    return None, None, None


# Tetto ai modelli aggiunti dal parco di test: una richiesta per modello, e
# la scansione gira ogni ora. Chi ne segue 200 sta usando lo strumento in un
# altro modo, e può interrogarli a comando dalla scheda Parco di test.
SAMSUNG_WATCHLIST_MAX = 40


def _samsung_da_controllare() -> list[tuple[str, str]]:
    """Modelli Samsung da interrogare nella scansione periodica.

    La tabella scritta a mano copre i modelli più diffusi, ma **i telefoni
    che contano davvero sono quelli nel parco di test**: se un device
    seguito non è in tabella, l'utente non riceve mai una notifica per esso
    — proprio lo scopo per cui l'ha aggiunto. Il controllo versione Samsung
    funziona per qualunque codice `SM-`, quindi qui si uniscono le due
    cose: la tabella di base più i modelli seguiti, risolti in codice
    tramite i dataset pubblici.
    """
    coppie: list[tuple[str, str]] = list(SAMSUNG_FUS_DEVICES)
    visti = {codice for codice, _nome in coppie}
    try:
        seguiti = storage.get_watchlist()
    except Exception:      # pragma: no cover - il DB può non essere pronto
        return coppie

    aggiunti = 0
    for voce in seguiti:
        if aggiunti >= SAMSUNG_WATCHLIST_MAX:
            break
        if voce.get("brand") != C.SAMSUNG:
            continue
        nome = voce.get("model") or ""
        for codice in modelcodes.codes_for_name(nome):
            if not _SAMSUNG_CODE_RE.match(codice) or codice in visti:
                continue
            visti.add(codice)
            coppie.append((codice, nome))
            aggiunti += 1
            break          # una variante regionale basta
    return coppie


def fetch_samsung_fus() -> tuple[list[RawItem], str | None]:
    """Ultima versione firmware nota per i modelli Samsung più diffusi,
    letta dall'endpoint di controllo versione ufficiale (non richiede
    autenticazione, a differenza del protocollo di download completo).

    Le richieste vanno in parallelo (thread pool): l'endpoint FOTA risponde
    anche in pochi decimi di secondo per modello, ma con ~20 modelli in
    sequenza il tempo si accumula inutilmente per query indipendenti fra
    loro — in parallelo la fonte impiega il tempo della richiesta più lenta,
    non la somma di tutte."""
    def _check(pair):
        model, display_name = pair
        try:
            pda, android_version, csc = _samsung_fus_latest(model)
        except Exception:
            pda = None
        return model, display_name, pda, android_version, csc

    items = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        for model, display_name, pda, android_version, csc in pool.map(
                _check, _samsung_da_controllare()):
            if not pda:
                continue
            items.append(
                RawItem(
                    title=f"Samsung {display_name} — build {pda} ({csc})",
                    link=f"https://fota-cloud-dn.ospserver.net/firmware/{csc}/{model}/version.xml",
                    brand=C.SAMSUNG,
                    device=f"Galaxy {display_name.replace('Galaxy ', '')}",
                    build=pda,
                    android_version=int(android_version) if android_version else None,
                    size_info="Controllo versione ufficiale (endpoint FOTA)",
                )
            )
    if not items:
        return [], f"nessun modello raggiungibile su {len(SAMSUNG_FUS_DEVICES)} in elenco"
    return items, None


def fetch_huawei():
    return rss_items(
        [
            "https://www.huaweicentral.com/category/updates/feed/",
            "https://www.huaweicentral.com/feed/",
        ],
        C.HUAWEI,
        "EMUI / HarmonyOS / MagicOS",
    )


def fetch_piunikaweb():
    # Rubrica multi-brand dedicata al tracciamento dei rollout: il brand viene
    # dedotto dal titolo in fase di normalizzazione.
    return rss_items(
        [
            "https://piunikaweb.com/category/software-updates/feed/",
            "https://piunikaweb.com/tag/software-update/feed/",
            "https://piunikaweb.com/feed/",
        ],
        None,
        "Software update tracker",
    )


def fetch_gsmarena():
    # Testata generalista molto piu' autorevole/attiva delle fonti minori
    # gia' in uso: copre tutti i brand insieme, il brand viene dedotto dal
    # titolo. Serve soprattutto a Realme/Oppo/Vivo/brand minori, che non
    # hanno una fonte ufficiale strutturata dedicata.
    return rss_items(["https://www.gsmarena.com/rss-news-reviews.php3"], None, "GSMArena")


def fetch_9to5google():
    # "/category/pixel/feed/" (usato in precedenza) risponde 200 ma il tag è
    # stato dismesso: serve un feed congelato al 2016-2017, quindi sembrava
    # funzionare mentre restituiva solo articoli vecchi di anni. Il tag
    # "pixel-feature-drop" è quello che 9to5Google usa davvero oggi per la
    # copertura dei rollout.
    return rss_items(["https://9to5google.com/tag/pixel-feature-drop/feed/"], C.PIXEL, "Pixel news")


# ======================================================================
# 7-8. Ricerche generiche (ultima risorsa per i brand senza fonte dedicata)
# ======================================================================
def _google_news(query: str, lang: str = "en-US", country: str = "US") -> str:
    from urllib.parse import quote

    return (
        f"https://news.google.com/rss/search?q={quote(query)}"
        f"&hl={lang}&gl={country}&ceid={country}:{lang.split('-')[0]}"
    )


def _merge_news_queries(queries: list[str], brand: str | None, size_info: str):
    """Esegue OGNI query separatamente (invece di un'unica query complessa
    con parentesi/OR/intitle: annidati) e unisce i risultati, deduplicando
    per titolo.

    Motivo: il parser di ricerca di Google News RSS non è documentato ed è
    noto per restituire silenziosamente ZERO risultati quando la query
    combina troppi operatori insieme (frasi tra virgolette + gruppi OR +
    intitle: nello stesso testo) — anche quando esistono notizie reali per
    l'argomento cercato con un termine più semplice. Query brevi e singole
    sono molto più affidabili con questo endpoint non ufficiale.
    """
    seen_titles: set[str] = set()
    merged: list[RawItem] = []
    last_error = None
    any_ok = False
    for query in queries:
        items, error = rss_items([_google_news(query)], brand, size_info)
        if error and not items:
            last_error = error
            continue
        any_ok = True
        for item in items:
            key = item.title.strip().lower()
            if key not in seen_titles:
                seen_titles.add(key)
                merged.append(item)
    if not any_ok and not merged:
        return [], last_error or "nessun risultato da nessuna delle query"
    return merged, None


def fetch_vivo_iqoo():
    queries = [
        "vivo update Android",
        "vivo security patch",
        "iQOO update Android",
        "iQOO OTA",
    ]
    return _merge_news_queries(queries, C.VIVO, "OTA news")


def fetch_motorola():
    # Le notizie su Motorola raramente usano le frasi "software update" o
    # "rollout": titoli tipici sono "Moto G85 gets the Android 15 update",
    # "Motorola Razr 50 receives September patch". Query brevi e separate
    # invece di un unico OR/intitle: complesso (il parser di Google News
    # RSS può restituire zero risultati con query troppo articolate anche
    # quando le notizie esistono davvero).
    queries = [
        "Motorola update Android",
        "Motorola security patch",
        "Moto G update",
        "Razr update Android",
    ]
    return _merge_news_queries(queries, C.VIVO, "OTA news")


# ======================================================================
# Motorola — firmware ufficiale via mirror comunitario lolinet.com
# ======================================================================
# lolinet.com ospita un mirror dei pacchetti firmware Motorola (verificati
# MD5-identici agli originali dalla community, vedi thread XDA); non è un
# endpoint Motorola diretto, ma a differenza delle notizie da' una build e
# una data certe invece di un titolo da interpretare.
#
# Copertura MANUALE: solo i modelli elencati qui sotto vengono controllati.
# Mappatura (anno, codename interno, nome commerciale) verificata da
# XDA "[Index] Motorola Devices by Codename & Model#" e dal database
# community KHwang9883/MobileModels. Copre le linee principali Razr/Edge/G
# dal 2022 al 2025: non e' un elenco completo di ogni variante regionale.
MOTOROLA_LOLINET_DEVICES: list[tuple[int, str, str]] = [
    (2022, "oneli", "Razr 2022"),
    (2022, "xpeng", "Edge S30"),
    (2022, "hiphic", "Edge X30"),
    (2022, "eqs", "X30 Pro"),
    (2022, "tundra", "S30 Pro"),
    (2022, "ibiza", "G50"),
    (2022, "cypfq", "G51"),
    (2022, "corfur", "G71"),
    (2023, "bronco", "ThinkPhone"),
    (2023, "cancun", "G14"),
    (2023, "cancunf", "G54 5G"),
    (2023, "devonf", "G73 5G"),
    (2023, "devonn", "G Power (2023)"),
    (2023, "fogos", "G34 5G"),
    (2023, "genevn", "G Stylus 5G (2023)"),
    (2023, "gnevan", "G Stylus (2023)"),
    (2023, "lynkco", "Razr 40"),
    (2023, "lyriq", "Edge 40"),
    (2023, "manaus", "Edge 40 Neo"),
    (2023, "penang", "G53 5G"),
    (2023, "penangf", "G13"),
    (2023, "pnangn", "G 5G (2023)"),
    (2023, "rtwo", "Edge 40 Pro"),
    (2023, "sabahl", "E13"),
    (2023, "zeekr", "Razr 40 Ultra"),
    # I nomi cinesi X50/S50 sono rebrand: in Europa questi codename sono
    # Edge 50 Ultra, Edge 50 Neo e moto g85. Mostrare il rebrand avrebbe
    # portato a scheda tecnica e firmware del mercato sbagliato.
    (2024, "ctwo", "Edge 50 Ultra"),
    (2024, "vienna", "Edge 50 Neo"),
    (2024, "malmo", "G85 5G"),
    (2024, "fogorow", "G24"),
    (2024, "aito", "Razr 50"),
    (2024, "arcfox", "Razr 50 Ultra"),
    (2024, "taipei", "G55"),
    (2024, "paros", "G75"),
    (2025, "scout", "Edge 60 Fusion"),
    (2025, "cybert", "Edge 60 Pro"),
    (2025, "leap", "Razr 60 Ultra"),
    # Nuovi codename con pacchetto RETEU verificato nel mirror e nome
    # verificato nella tabella ufficiale Motorola dei codici XT.
    (2025, "aito25", "Razr 60"),
    (2025, "bogota", "G56 5G"),
    (2025, "nice", "G86 5G"),
    (2025, "roadstr", "Edge 70"),
]

# Codici letti dai pacchetti del mirror, non dedotti dal nome. Questa piccola
# mappa rende immediata la ricerca per codice anche offline, mentre
# `motorola_catalog` amplia l'identificazione a tutti i codici XT pubblicati
# da Motorola. Ogni tupla e' (anno, codename, nome europeo).
MOTOROLA_LOLINET_CODES: dict[str, tuple[int, str, str]] = {
    "XT2309-2": (2023, "bronco", "ThinkPhone"),
    "XT2341-2": (2023, "cancun", "G14"),
    "XT2343-2": (2023, "cancunf", "G54 5G"),
    "XT2237-2": (2023, "devonf", "G73 5G"),
    "XT2363-3": (2023, "fogos", "G34 5G"),
    "XT2323-1": (2023, "lynkco", "Razr 40"),
    "XT2307-1": (2023, "manaus", "Edge 40 Neo"),
    "XT2331-2": (2023, "penangf", "G13"),
    "XT2335-2": (2023, "penang", "G53 5G"),
    "XT2301-4": (2023, "rtwo", "Edge 40 Pro"),
    "XT2345-3": (2023, "sabahl", "E13"),
    "XT2321-1": (2023, "zeekr", "Razr 40 Ultra"),
    "XT2401-1": (2024, "ctwo", "Edge 50 Ultra"),
    "XT2409-1": (2024, "vienna", "Edge 50 Neo"),
    "XT2423-3": (2024, "fogorow", "G24"),
    "XT2427-2": (2024, "malmo", "G85 5G"),
    "XT2453-1": (2024, "aito", "Razr 50"),
    "XT2451-3": (2024, "arcfox", "Razr 50 Ultra"),
    "XT2435-2": (2024, "taipei", "G55 5G"),
    "XT2437-3": (2024, "paros", "G75 5G"),
    "XT2503-4": (2025, "scout", "Edge 60 Fusion"),
    "XT2507-1": (2025, "cybert", "Edge 60 Pro"),
    "XT2551-6": (2025, "leap", "Razr 60 Ultra"),
    "XT2553-1": (2025, "aito25", "Razr 60"),
    "XT2529-2": (2025, "bogota", "G56 5G"),
    "XT2527-2": (2025, "nice", "G86 5G"),
    "XT2601-2": (2025, "roadstr", "Edge 70"),
}

# Non tutti i modelli pubblicano un pacchetto per ogni regione: si prova
# questa lista in ordine finché una cartella risponde con dei file.
_LOLINET_REGIONS = ["RETEU", "RETAIL", "RETGB", "RETUS", "RETBR"]

# Righe tipiche della tabella h5ai: un link a un file .zip seguito, poco
# dopo nello stesso HTML, dalla colonna data ("2025-10-16 23:10").
_LOLINET_FILE_RE = re.compile(
    r'href="([^"]+\.(?:xml\.zip|zip))"[^<]*<[^>]*>.*?(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})',
    re.S,
)
# Nome file tipico:
# XT2323-1_LYNKCO_RETEU_15_V1TVS35H.41-24-6-7_subsidy-DEFAULT_regulatory-...
_LOLINET_NAME_RE = re.compile(
    r"(XT[\w-]+)_[A-Z0-9]+_[A-Z0-9]+_(\d{1,2})_([^_/]+)_subsidy", re.I
)
_LOLINET_FASTBOOT_RE = re.compile(
    r"_(\d{1,2})_(?:SHIPPING_[^_]+_g-user-)?([A-Z][A-Z0-9.-]*\d[A-Z0-9.-]*)",
    re.I,
)


def _lolinet_metadata(filename: str, fallback_code: str | None = None):
    """Codice, Android e build sia dai pacchetti OTA sia dai fastboot."""
    match = _LOLINET_NAME_RE.search(filename or "")
    if match:
        return match.group(1).upper(), int(match.group(2)), match.group(3)
    match = _LOLINET_FASTBOOT_RE.search(filename or "")
    if match:
        return fallback_code, int(match.group(1)), match.group(2)
    return fallback_code, None, None


def _lolinet_latest(codename: str, year: int):
    """Ultimo file firmware per un codename, provando le region una a una.
    Ritorna (nome_file, url_completo, data_iso) oppure None se non trovato."""
    base = f"https://mirrors.lolinet.com/firmware/lenomola/{year}/{codename}/official"
    ripiego = None
    for region in _LOLINET_REGIONS:
        folder_url = f"{base}/{region}/"
        try:
            response = http_get(folder_url)
        except Exception:
            continue
        if response.status_code != 200:
            continue
        matches = _LOLINET_FILE_RE.findall(response.text)
        if not matches:
            continue
        # L'indice h5ai puo' contenere pacchetti di piu' mercati anche
        # dentro una cartella regionale. Prima si prendeva la data piu'
        # recente e un RETAPAC poteva prevalere su un RETEU. Qui si accetta
        # solo il tag della regione richiesta; se non esiste nessun tag, il
        # pacchetto resta disponibile esclusivamente come ripiego finale.
        regionali = [m for m in matches if f"_{region}_" in m[0].upper()]
        scelti = regionali or matches
        filename, date_str = max(scelti, key=lambda m: m[1])
        filename = filename.rsplit("/", 1)[-1]
        trovato = (filename, folder_url + filename, date_str)
        if regionali:
            return trovato
        if ripiego is None:
            ripiego = trovato
    return ripiego


def fetch_motorola_lolinet():
    """Ultima build ufficiale per i Motorola più recenti, letta direttamente
    dal mirror invece che dedotta da un titolo di notizia.

    ATTENZIONE PRESTAZIONI: mirrors.lolinet.com è lentissimo — anche una
    singola richiesta riuscita impiega ~15s (verificato). Con ~35 modelli e
    fino a 5 region da provare ciascuno, in sequenza lo scan intero poteva
    richiedere decine di minuti. Le richieste per modello sono indipendenti
    fra loro, quindi vanno in parallelo (thread pool): il tempo totale resta
    quello del modello più lento, non la somma di tutti."""
    def _check(triple):
        year, codename, model = triple
        try:
            found = _lolinet_latest(codename, year)
        except Exception:
            found = None
        return model, found

    items = []
    with ThreadPoolExecutor(max_workers=15) as pool:
        for model, found in pool.map(_check, MOTOROLA_LOLINET_DEVICES):
            if not found:
                continue
            filename, file_url, date_str = found
            model_code, android_version, build = _lolinet_metadata(filename)
            items.append(
                RawItem(
                    title=f"Motorola {model} — build {build or filename}",
                    link=file_url,
                    published=iso(date_str.replace(" ", "T", 1)),
                    brand=C.VIVO,
                    device=f"Motorola {model}",
                    model_code=model_code,
                    build=build,
                    android_version=android_version,
                    size_info="Firmware ufficiale (mirror lolinet.com)",
                )
            )
    if not items:
        return [], f"nessun modello raggiungibile su {len(MOTOROLA_LOLINET_DEVICES)} in elenco"
    # Non blocca la fonte se alcuni modelli mancano: possono non avere ancora
    # un pacchetto nella region provata, o il mirror li ha riorganizzati.
    return items, None


def fetch_minor_brands():
    queries = [
        "Nothing Phone update",
        "Umidigi update",
        "Doogee update",
        "Cubot update",
        "Blackview update",
        "Fairphone update",
    ]
    return _merge_news_queries(queries, C.OTHER, "Firmware release")


# ======================================================================
# Registro delle fonti
# ======================================================================
SOURCES: list[Source] = [
    Source("apple_devices", "Apple — firmware per dispositivo (iOS/iPadOS)", C.TRUST_STRUCTURED,
           fetch_apple, C.APPLE, "https://ipsw.me",
           "Versione, build e data di rilascio letti dalla lista firmware del singolo dispositivo."),
    Source("pixel_ota", "Google Pixel — immagini OTA (canale Beta)", C.TRUST_STRUCTURED,
           fetch_pixel_ota, C.PIXEL, "https://developers.google.com/android/ota",
           "Build ufficiali, ma del canale BETA: le pagine per-release servono "
           "solo file `*_beta-ota-*`. La pagina delle immagini stabili è resa in "
           "JavaScript e non è leggibile con una richiesta semplice — finché non "
           "si trova una fonte stabile, questi item restano marcati BETA e fuori "
           "dalle notifiche automatiche."),
    Source("xiaomi_tracker", "Xiaomi — MIUI/HyperOS Updates Tracker", C.TRUST_STRUCTURED,
           fetch_xiaomi, C.XIAOMI, "https://xiaomifirmwareupdater.com",
           "Dataset community aggiornato di continuo, per singolo codename."),
    # FONTE RITIRATA DALL'ELENCO PREDEFINITO (il codice resta, vedi
    # fetch_oppo_official). Il loro endpoint risponde solo a chi si dichiara
    # l'app OxygenUpdater: senza un accordo con i manutentori l'unico modo di
    # farla funzionare sarebbe impersonare la loro applicazione, cosa che
    # questo progetto non fa. Tenerla attiva significava mostrare un errore
    # rosso permanente in Diagnostica per una fonte che non potrà mai
    # riuscire — rumore che rende meno credibili gli errori veri.
    #
    # Per riattivarla se un giorno si ottiene un UA concordato:
    #   ENABLED_SOURCES="oppo_official"  (oltre a OXYGEN_USER_AGENT)
    Source("oppo_aer", "Oppo — elenco ufficiale Android Enterprise Recommended", C.TRUST_STRUCTURED,
           fetch_oppo_aer, C.OPPO, OPPO_AER_URL,
           "Modelli certificati e politica di supporto; non pubblica la versione per dispositivo."),
    Source("oplus_arb", "OnePlus/OPPO — tracker ARB (build per regione)",
           C.TRUST_CURATED, fetch_oplus_arb, C.OPPO, ARB_README_URL,
           "Build correnti per regione, estratte dai firmware veri da uno "
           "script automatico. NON ufficiale: progetto community nato per "
           "segnalare il rischio di anti-rollback. Copre OnePlus quasi per "
           "intero e parte degli OPPO; non copre la serie A, realme e vivo."),
    # FONTE RITIRATA DALL'ELENCO PREDEFINITO il 2026-08-11: il canale non
    # stava dando niente da sfruttare (0 voci in scansione, misurato in
    # Diagnostica) e nel frattempo costava comunque un giro di rete a ogni
    # scansione periodica E una richiesta in più a ogni ricerca live su un
    # modello Oppo/OnePlus/realme (vedi `RETIRED_SOURCES` più sotto e la
    # corrispondente `StructuredLookup` tolta da `_STRUCTURED_LOOKUPS_LIST`).
    # Il codice resta tutto (`fetch_oplus_telegram`, `_lookup_oplus_telegram`,
    # `core/telegram_tracker.py`): da riprendere quando il canale torna a
    # dare numeri di build reali, non da riscrivere da capo.
    #
    # Per riattivarla: ENABLED_SOURCES="oplus_telegram" e riportare la riga
    # `StructuredLookup(C.OPPO, _lookup_oplus_telegram, ...)` nell'elenco.
    Source("coloros_news", "Oppo/OnePlus — aggiornamenti ColorOS", C.TRUST_CURATED,
           fetch_coloros_news, C.OPPO, "https://news.google.com",
           "Annunci di rilascio ColorOS ripresi dalle testate."),
    Source("realme_aer", "realme — piano ufficiale Android Enterprise Recommended", C.TRUST_STRUCTURED,
           fetch_realme_aer, C.OPPO, REALME_AER_URL,
           "Versione di fabbrica, scadenza supporto sicurezza e codici modello ufficiali."),
    Source("oxygen_updater", "Oppo/OnePlus/realme — ricerca news", C.TRUST_CURATED,
           fetch_oxygen_updater, C.OPPO, "https://oxygenupdater.com",
           "Fonte attiva per questi brand: nessun endpoint ufficiale accessibile."),
    Source("samsung_fus", "Samsung — controllo versione ufficiale (FOTA)", C.TRUST_STRUCTURED,
           fetch_samsung_fus, C.SAMSUNG, "https://fota-cloud-dn.ospserver.net",
           "Copertura manuale dei modelli principali 2021-2024 (S/A/Z series)."),
    Source("sammobile", "Samsung — SamMobile Firmware News", C.TRUST_CURATED,
           fetch_samsung, C.SAMSUNG, "https://www.sammobile.com"),
    Source("huaweicentral", "Huawei/Honor — HuaweiCentral Updates", C.TRUST_CURATED,
           fetch_huawei, C.HUAWEI, "https://www.huaweicentral.com"),
    Source("honor_aer", "Honor — piano ufficiale Android Enterprise Recommended", C.TRUST_STRUCTURED,
           fetch_honor_aer, C.HUAWEI, HONOR_AER_URL,
           "Versione Android di partenza e impegno di aggiornamento futuro per modello."),
    Source("honor_security", "Honor — bollettino sicurezza ufficiale Italia", C.TRUST_STRUCTURED,
           fetch_honor_security_bulletin, C.HUAWEI, HONOR_SECURITY_BULLETIN_URL,
           "Modelli supportati e cadenza aggiornamenti: non pubblica il numero di build OTA."),
    Source("aer_catalog", "Multi-brand — Android Enterprise Recommended (catalogo)",
           C.TRUST_STRUCTURED, fetch_aer_catalog, None,
           "https://androidenterprisepartners.withgoogle.com/devices/",
           "706 dispositivi di 40+ marche in JSON: codici modello verificati, "
           "finestra di supporto e cadenza delle patch. Non pubblica la versione "
           "attuale. Unica fonte strutturata per OnePlus."),
    Source("piunikaweb", "Multi-brand — PiunikaWeb Software Updates", C.TRUST_CURATED,
           fetch_piunikaweb, None, "https://piunikaweb.com"),
    Source("gsmarena", "Multi-brand — GSMArena", C.TRUST_CURATED,
           fetch_gsmarena, None, "https://www.gsmarena.com"),
    Source("9to5google", "Google Pixel — 9to5Google", C.TRUST_NOISY,
           fetch_9to5google, C.PIXEL, "https://9to5google.com"),
    Source("vivo_aer", "vivo/iQOO — piano ufficiale Android Enterprise Recommended",
           C.TRUST_STRUCTURED, fetch_vivo_aer, C.VIVO, VIVO_AER_URL,
           "Tabella AER ufficiale: 20 modelli con versione di fabbrica, "
           "fine del supporto e cadenza delle patch. Verificata sul sito reale."),
    Source("news_vivo_iqoo", "vivo/iQOO — ricerca news", C.TRUST_NOISY,
           fetch_vivo_iqoo, C.VIVO, "https://news.google.com", is_web_search=True),
    Source("motorola_lolinet", "Motorola — firmware (mirror lolinet.com)", C.TRUST_STRUCTURED,
           fetch_motorola_lolinet, C.VIVO, "https://mirrors.lolinet.com/firmware/lenomola/",
           "Copertura manuale dei modelli principali 2022-2025 (Razr/Edge/G)."),
    Source("news_motorola", "Motorola — ricerca news", C.TRUST_NOISY,
           fetch_motorola, C.VIVO, "https://news.google.com", is_web_search=True),
    Source("news_minor", "Altri brand — ricerca news", C.TRUST_NOISY,
           fetch_minor_brands, C.OTHER, "https://news.google.com", is_web_search=True),
]


def _extra_sources() -> list[Source]:
    """Fonti aggiuntive definite a runtime, senza modificare il codice.

    Formato: EXTRA_FEEDS="url|Etichetta|brand|trust ;; url2|..."
    (brand e trust sono opzionali; trust ∈ structured|curated|noisy).
    """
    raw = C.env("EXTRA_FEEDS")
    if not raw:
        return []
    extra = []
    for index, chunk in enumerate(raw.split(";;")):
        parts = [p.strip() for p in chunk.split("|")]
        if not parts or not parts[0]:
            continue
        url = parts[0]
        label = parts[1] if len(parts) > 1 and parts[1] else url
        brand = parts[2] if len(parts) > 2 and parts[2] in C.BRANDS else None
        trust = parts[3] if len(parts) > 3 and parts[3] else C.TRUST_NOISY
        extra.append(
            Source(
                key=f"extra_{index}",
                label=f"Personalizzata — {label}",
                trust=trust,
                fetch=(lambda u=url, b=brand: rss_items([u], b, "Feed personalizzato")),
                brand=brand,
                homepage=url,
            )
        )
    return extra


# Fonti presenti nel codice ma NON attive per impostazione predefinita,
# perché non possono riuscire nell'ambiente normale (vedi il commento sulla
# fonte OxygenUpdater ufficiale). Si riattivano con ENABLED_SOURCES.
RETIRED_SOURCES = [
    Source("oppo_official", "Oppo/OnePlus/realme — versione ufficiale (OxygenUpdater)",
           C.TRUST_STRUCTURED, fetch_oppo_official, C.OPPO, "https://oxygenupdater.com",
           "Richiede un UA concordato con i manutentori (vedi OXYGEN_USER_AGENT)."),
    Source("oplus_telegram", "Oppo/OnePlus/realme — canale rollout OxygenOS/ColorOS",
           C.TRUST_CURATED, fetch_oplus_telegram, C.OPPO, TELEGRAM_OPLUS_URL,
           "Numeri di build reali per i modelli recenti, che nessuna fonte "
           "ufficiale di questi marchi pubblica. NON ufficiale: canale gestito "
           "da una persona. I post di versioni previste ('Upcoming', 'subject "
           "to change') vengono scartati. Ritirata l'11/08/2026: non stava "
           "dando risultati (0 voci in scansione) e costava comunque un giro "
           "di rete a ogni scansione e a ogni ricerca live Oppo/OnePlus."),
]


def all_sources() -> list[Source]:
    disabled = {s.strip() for s in C.env("DISABLED_SOURCES").split(",") if s.strip()}
    enabled_extra = {s.strip() for s in C.env("ENABLED_SOURCES").split(",") if s.strip()}
    riattivate = [s for s in RETIRED_SOURCES if s.key in enabled_extra]
    return [s for s in SOURCES + riattivate + _extra_sources() if s.key not in disabled]


# ======================================================================
# Ricerca live su un modello specifico (on-demand, non nel giro periodico)
# ======================================================================
# Un codice modello vero ha una forma distintiva: una sigla di marca seguita
# da un numero lungo (RMX3939, SM-S928B, ABR-LX1, 2312DRA50C). Una stringa
# corta e generica come «C61» NON è un codice: è il nome commerciale di un
# modello — e trattarla come codice la fa corrispondere per caso a
# dispositivi di marche del tutto diverse (Chainway C61, Oukitel C61), su
# cui la ricerca viene poi sprecata.
# Suffissi di variante che compaiono sulla scatola, nell'etichetta sotto la
# batteria e in «Info software», ma che NON fanno parte del codice usato
# dalle fonti firmware: `SM-A075F/DS` è il dual-SIM di `SM-A075F`, e
# l'endpoint FOTA conosce solo il secondo.
#
# Finché non venivano tolti, un utente che copiava il codice come lo vedeva
# scritto sul proprio telefono non trovava NIENTE: né il firmware, né il
# modello. Ed è la forma più naturale in cui copiarlo.
_RE_SUFFISSO_VARIANTE = re.compile(
    r"[/\s]+(?:DS|DSN|DUOS|D|N|ZA|ZT)\s*$", re.I)


def normalizza_codice_modello(testo: str) -> str:
    """Toglie spazi e suffissi di variante da un codice modello.

    `SM-A075F/DS` → `SM-A075F` · `SM-A075F DS` → `SM-A075F`

    L'ordine conta: il suffisso va tolto PRIMA di comprimere gli spazi.
    Al contrario, «SM-A075F DS» diventerebbe «SM-A075FDS», che ha ancora
    la forma di un codice valido — e quindi non verrebbe segnalato come
    errore, verrebbe solo cercato invano.
    """
    grezzo = (testo or "").strip().upper()
    precedente = None
    while grezzo != precedente:
        precedente = grezzo
        grezzo = _RE_SUFFISSO_VARIANTE.sub("", grezzo).strip()
    return re.sub(r"\s+", "", grezzo)


_MODEL_CODE_SHAPES = [
    re.compile(r"^SM-[A-Z]\d{3}[A-Z]{0,3}$", re.I),          # Samsung
    re.compile(r"^[A-Z]{3}-[A-Z]{2}\w{1,4}$", re.I),          # Huawei/Honor
    re.compile(r"^(?:iPhone|iPad|iPod)\d+,\d+$", re.I),       # Apple
    # RMX3939, CPH2625, XT2347 — con eventuale suffisso di variante (XT2323-1)
    re.compile(r"^[A-Z]{2,5}[-_]?\d{4,5}[A-Z0-9]{0,4}(?:-\d{1,2})?$", re.I),
    # Xiaomi moderno: il tratto alfabetico e quello numerico non hanno più
    # una lunghezza fissa. Sono reali sia `2306EPN60G` sia `23078PND5G`,
    # `2304FPN6DG`, `2406APNFAG` e `2410FPCC5G`; il vecchio vincolo di due
    # cifre dopo le lettere scartava tutti gli ultimi tre.
    re.compile(r"^\d{4,5}[A-Z]{2,6}\d{0,3}[A-Z]{0,3}$", re.I),
    # Xiaomi vecchio stile: solo cifre più il suffisso di regione (22101316UG)
    re.compile(r"^\d{7,9}[A-Z]{1,3}$", re.I),
    # Xiaomi stile classico, con la M davanti: M1910F4G (Mi Note 10),
    # M2007J20CG (Redmi Note 9 Pro), M2101K6G (POCO F3). Mancava del
    # tutto — nessuna delle forme sopra comincia con UNA lettera sola —
    # quindi questi codici non "avevano la forma di un codice" per
    # `looks_like_model_code`, e saltavano ogni instradamento che ne
    # dipende: la ricerca sul catalogo Xiaomi, i gemelli, la correzione
    # del nome. Restava solo `core/specs.py::cerca`, che prova il testo
    # SENZA validarne la forma — ed è per questo che la scheda tecnica
    # (foto, processore) trovava il telefono giusto mentre il resto
    # della pagina si comportava come se il codice non fosse mai stato
    # scritto: intestazione con la query grezza, nessuna correzione
    # possibile, nessun instradamento verso il tracker Xiaomi.
    re.compile(r"^M\d{4}[A-Z]\d{1,2}[A-Z]{0,3}$", re.I),
]


# Codice Samsung scritto SENZA il prefisso: `A325F`, `S928B`, `G991B`.
#
# È la forma in cui il codice compare nel numero di build (`A325FXXU2CVK1`),
# nei log, nelle discussioni tecniche e nei nomi dei firmware — quindi è
# quella che chi fa QA copia più spesso, molto più di `SM-A325F`.
#
# Finché non veniva riconosciuta, cercare «a325f» non attivava il controllo
# firmware Samsung: rispondeva un'altra fonte, con la versione **di
# fabbrica**. Su un Galaxy A32 significava vedere Android 11 (il lancio,
# 2021) su un telefono che intanto è arrivato ad Android 13. Non era un
# dato mancante — era un dato SBAGLIATO, che è molto peggio.
#
# Il vincolo sulle cifre è stretto (esattamente tre) apposta: allargarlo
# farebbe passare per codice Samsung qualunque parola con dei numeri.
_RE_SAMSUNG_SENZA_PREFISSO = re.compile(r"^([A-Z]\d{3}[A-Z]{0,3})$")


def espandi_codice_samsung(testo: str) -> str | None:
    """`A325F` → `SM-A325F`. None se non ha quella forma."""
    compatto = normalizza_codice_modello(testo)
    if compatto.startswith("SM-"):
        return None
    match = _RE_SAMSUNG_SENZA_PREFISSO.match(compatto)
    return f"SM-{match.group(1)}" if match else None


def looks_like_model_code(text: str) -> bool:
    """True solo se il testo ha la forma di un codice modello vero."""
    compatto = normalizza_codice_modello(text)
    if espandi_codice_samsung(compatto):
        return True
    return any(pattern.match(compatto) for pattern in _MODEL_CODE_SHAPES)


def _code_candidates(query: str) -> list[str]:
    """Varianti del testo digitato da provare contro il database di codici:
    così com'è e senza spazi (un utente può scrivere "rmx 3939" invece di
    "RMX3939").

    Solo le varianti che hanno davvero la FORMA di un codice vengono
    restituite: risolvere una sigla generica contro un database di 70.000
    codici trova sempre qualcosa, ma quasi mai la cosa giusta.
    """
    stripped = query.strip().upper()
    no_spaces = re.sub(r"\s+", "", stripped)
    # La forma senza suffisso di variante viene per PRIMA: è quella che
    # le fonti firmware conoscono. `SM-A075F/DS` è come l'utente lo
    # legge sul telefono, `SM-A075F` è come lo chiama l'endpoint FOTA.
    variants = []
    # La forma ESPANSA per prima: `a325f` va cercato come `SM-A325F`,
    # che e' l'unico nome che l'endpoint firmware Samsung conosce.
    espanso = espandi_codice_samsung(query)
    for v in (espanso, normalizza_codice_modello(query), stripped, no_spaces):
        if not v:
            continue
        if v and v not in variants and looks_like_model_code(v):
            variants.append(v)
    return variants


def _news_attempts(text: str) -> list[str]:
    """Dalla più mirata alla più larga, per un singolo testo di ricerca
    (nome commerciale o query originale). Query BREVI e SEMPLICI, non
    frasi tra virgolette con gruppi OR e intitle: annidati insieme: il
    parser di Google News RSS non è documentato ed è noto restituire
    silenziosamente zero risultati con query troppo articolate, anche
    quando esistono notizie reali sull'argomento (verificato: una ricerca
    generale trova notizie che la query complessa precedente non trovava)."""
    return [
        f"{text} update",
        f"{text} software update",
        f"{text} security patch",
        text,
    ]


# ======================================================================
# Ricerca ON-DEMAND sulle fonti ufficiali per un singolo modello
# ======================================================================
# Lacuna colmata qui: prima, le fonti STRUCTURED (Samsung FUS, Xiaomi,
# Honor AER, Motorola) venivano interrogate SOLO dal giro periodico, e solo
# per i modelli presenti in tabelle scritte a mano. Cercando un modello non
# ancora in archivio — cosa frequentissima, perché il database SQLite si
# azzera a ogni riavvio del container su Streamlit Cloud — restava solo la
# ricerca su notizie, che per definizione non garantisce un dato di
# firmware. Ora ogni ricerca interroga direttamente la fonte ufficiale del
# brand per QUEL modello, quando è possibile.
_SAMSUNG_CODE_RE = re.compile(r"^SM-[A-Z0-9]{4,}$", re.IGNORECASE)

# L'ULTIMA LETTERA DI UN CODICE SAMSUNG È IL MERCATO, e senza una regola la
# variante interrogata era quella che il dataset aveva messo per prima —
# cioè il caso. Cercando «samsung s24» rispondeva `SM-S9210` (Cina) e
# cercando `SM-S921B` rispondeva la build europea: stesso telefono, due
# risposte diverse, e la differenza non era spiegata da nessuna parte.
#
# Senza un mercato indicato, quello sensato è l'internazionale. Non è una
# risposta più «vera» delle altre — è una scelta dichiarata invece che
# casuale, e l'app mostra sempre quale variante ha interrogato.
#   B, F  internazionale / Europa      N   Corea
#   U, U1 Stati Uniti                  0   Cina
#   W     Canada                       Q   variante USA
_ORDINE_MERCATI_SAMSUNG = ("B", "F", "E", "U", "U1", "W", "N", "Q", "0")


def _rango_mercato_samsung(codice: str) -> int:
    suffisso = re.sub(r"^SM-[A-Z]\d{3,4}", "", (codice or "").upper())
    try:
        return _ORDINE_MERCATI_SAMSUNG.index(suffisso)
    except ValueError:
        # Suffisso non elencato (o assente): dopo quelli noti, ma prima di
        # niente — resta comunque un codice valido da provare.
        return len(_ORDINE_MERCATI_SAMSUNG)


def _nome_ufficiale(codice: str, ripiego: str) -> str:
    """Nome commerciale con le maiuscole giuste, preso dal dataset.

    Il testo digitato può essere in minuscolo o essere un codice: mostrarlo
    così com'è produce «galaxy s24 ultra» o «SM-S928B» al posto del nome
    vero. Quando il dataset conosce il codice, la forma corretta è già lì.
    """
    for nome in modelcodes.resolve(codice):
        return nome
    return " ".join((ripiego or "").split())


def _lookup_samsung(model_name: str) -> list[RawItem]:
    """Controllo versione ufficiale per un Samsung qualsiasi.

    Il codice modello (SM-xxxx) viene ricavato dall'indice inverso dei
    dataset pubblici: così la copertura non è più limitata ai ~23 modelli
    della tabella scritta a mano, ma vale per qualunque Samsung presente
    nei dataset.
    """
    # Il testo digitato può essere già un codice ("SM-S928B") o un nome
    # scritto in minuscolo: in entrambi i casi il nome da mostrare è quello
    # ufficiale del dataset, non la forma battuta a tastiera.
    normalizzato = espandi_codice_samsung(model_name) or normalizza_codice_modello(model_name)
    if _SAMSUNG_CODE_RE.match(normalizzato):
        codes = [normalizzato]
    else:
        # Ordine dichiarato, non ordine del dataset: vedi
        # `_ORDINE_MERCATI_SAMSUNG`. È ciò che rende la ricerca per nome
        # e quella per codice due strade verso la stessa risposta.
        codes = sorted(
            (c for c in modelcodes.codes_for_name(model_name) if _SAMSUNG_CODE_RE.match(c)),
            key=_rango_mercato_samsung,
        )
    items: list[RawItem] = []
    # Tetto di tempo: ogni codice prova più region in sequenza, quindi il
    # caso peggiore è codici × region × timeout. In una ricerca interattiva
    # va limitato, o la pagina resta in caricamento (vedi la nota analoga
    # in search_model_live).
    scadenza = time.monotonic() + C.SEARCH_BUDGET_SECONDS
    for code in codes[:4]:  # più varianti regionali: basta la prima che risponde
        if time.monotonic() >= scadenza:
            break
        try:
            pda, android_version, csc = _samsung_fus_latest(code)
        except Exception:
            continue
        if not pda:
            continue
        items.append(
            RawItem(
                title=f"{_nome_ufficiale(code, code)} ({code}) — build {pda} ({csc})",
                link=f"https://fota-cloud-dn.ospserver.net/firmware/{csc}/{code}/version.xml",
                brand=C.SAMSUNG,
                device=_nome_ufficiale(code, code),
                model_code=code,
                build=pda,
                android_version=int(android_version) if android_version else None,
                size_info=f"Controllo versione ufficiale (endpoint FOTA) · {code}",
            )
        )
        break
    return items


def _rango_mercato_xiaomi(item: RawItem) -> int:
    """Ordine delle ROM Xiaomi per una ricerca dal mercato europeo.

    Il tracker conserva la stessa release per tutte le regioni e la ordina
    per data, non per mercato. Una build Indonesia più nuova non deve però
    diventare il primo risultato per un codice globale/EEA: il suffisso
    ``EUXM`` (o l'etichetta EEA) identifica la variante europea. Globale è
    il secondo ripiego; le varianti nazionali restano disponibili dopo.
    """
    testo = " ".join((item.build or "", item.device or "", item.title or "")).upper()
    if "EUXM" in testo or re.search(r"\bEEA\b", testo):
        return 0
    if "MIXM" in testo or re.search(r"\bGLOBAL\b", testo):
        return 1
    if "RUXM" in testo or "TWXM" in testo:
        return 3
    if "INXM" in testo or "IDXM" in testo:
        return 4
    if "CNXM" in testo or re.search(r"\bCHINA\b", testo):
        return 5
    return 2


def _risultati_xiaomi_ordinati(items: list[RawItem], codice: str | None = None) -> list[RawItem]:
    """Deduplica e mette Europa/Globale davanti alle altre regioni."""
    visti: set[tuple[str, str, str]] = set()
    distinti: list[RawItem] = []
    for item in items:
        chiave = (item.device or "", item.build or "", item.link or "")
        if chiave in visti:
            continue
        visti.add(chiave)
        distinti.append(replace(item, model_code=codice) if codice else item)
    # Ordinamenti stabili in due passaggi: prima l'ultima data dentro ogni
    # regione, poi la priorità geografica. Un ``reverse=True`` sul tuple
    # invertirebbe anche Europa/Globale e ricreerebbe il difetto.
    distinti.sort(key=lambda item: item.published or "", reverse=True)
    distinti.sort(key=_rango_mercato_xiaomi)
    return distinti[:3]


# Nelle build Xiaomi le tre lettere subito prima del mercato sono il
# identificatore della stessa variante hardware: ``WNO`` in
# ``WNOEUXM``/``WNOMIXM``, per esempio, è sempre il Redmi Note 13 Pro+ 5G.
# Il nome nel tracker può invece contenere uno o più alias dopo ``/`` e non
# è quindi confrontabile letteralmente fra regioni. Usiamo la chiave soltanto
# *dopo* avere trovato il modello per nome: non trasforma mai una sigla di
# build in un riconoscimento autonomo.
_XIAOMI_BUILD_PRODUCT_RE = re.compile(
    r"\.([A-Z0-9]{3})(?:CN|EU|MI|IN|ID|RU|TW|TR|JP)XM(?:\b|$)", re.I
)


def _chiave_prodotto_xiaomi(item: RawItem) -> str | None:
    testo = " ".join((item.build or "", item.version or "")).upper()
    trovato = _XIAOMI_BUILD_PRODUCT_RE.search(testo)
    return trovato.group(1).upper() if trovato else None


_PAROLE_REGIONI_XIAOMI = frozenset((
    "eea", "global", "china", "india", "indonesia", "japan", "russia",
    "taiwan", "turkey", "europe", "european",
))


def _varianti_regionali_xiaomi(nomi: list[tuple[RawItem, str]], richiesto: str) -> list[RawItem]:
    """Trova «Xiaomi 14 EEA» senza confonderlo con 14T o 14 Ultra.

    La normalizzazione generale rimuove la marca, perciò «Xiaomi 14» si
    riduce a ``14`` e il normale ripiego lo scarta (due caratteri sono in
    genere troppo ambigui). Per un nome ricavato da un *codice esatto* si
    può invece confrontare le parole originali: dopo il nome sono ammesse
    esclusivamente etichette di regione, mai una variante di prodotto.
    """
    parole_richieste = re.findall(r"[a-z0-9]+", (richiesto or "").lower())
    if not parole_richieste:
        return []
    trovati: list[RawItem] = []
    for item, _nome_norm in nomi:
        parole = re.findall(r"[a-z0-9]+", (item.device or item.title or "").lower())
        larghezza = len(parole_richieste)
        for inizio in range(len(parole) - larghezza + 1):
            if parole[inizio:inizio + larghezza] != parole_richieste:
                continue
            resto = parole[inizio + larghezza:]
            if resto and all(parola in _PAROLE_REGIONI_XIAOMI for parola in resto):
                trovati.append(item)
            break
    return trovati


def _lookup_xiaomi(model_name: str) -> list[RawItem]:
    """Cerca il modello nel catalogo Xiaomi completo (già scaricato e in
    cache): copre qualunque device del tracker, non solo i più recenti.

    IL NOME ESATTO VIENE PRIMA DI QUELLO CHE LO CONTIENE. Con il solo
    confronto per sottostringa, cercare «Redmi Note 13» rispondeva «Redmi
    Note 13 Pro+ 5G Taiwan» — un telefono diverso, con un altro chip e un
    altro firmware — solo perché il catalogo lo elencava prima. È la stessa
    regola già applicata in `_lookup_pixel`: la sottostringa resta come
    ripiego, non come prima scelta.
    """
    all_items, error = fetch_xiaomi()
    if error or not all_items:
        return []
    codice = normalizza_codice_modello(model_name) if looks_like_model_code(model_name) else None
    # Il codice è l'identità più precisa: un nome commerciale può comparire
    # su più codici regionali, ma non è ambiguo *per il codice digitato*.
    # `expand_query` evita correttamente quegli alias generici per non
    # mescolare due RMX; qui invece li usiamo solo per interrogare il
    # catalogo Xiaomi con quel preciso codice e li restituiamo marcati.
    nomi_richiesti = modelcodes.resolve(codice) if codice else [model_name]
    if not nomi_richiesti:
        nomi_richiesti = [model_name]
    aghi = [modelcodes._normalize_name(nome) for nome in nomi_richiesti]
    aghi = [ago for ago in aghi if ago]
    if not aghi:
        return []
    nomi = [(item, modelcodes._normalize_name(item.device or item.title))
            for item in all_items]
    esatti = [item for item, nome in nomi if nome in aghi]
    if esatti:
        return _risultati_xiaomi_ordinati(esatti, codice)

    vicini: list[RawItem] = []
    for nome, ago in zip(nomi_richiesti, aghi):
        # Le righe che differiscono dal nome richiesto soltanto per il
        # mercato sono già un gruppo certo, anche se il nome è lungo. Non
        # limitarle alle sole query corte: una major release può cambiare il
        # token della build (es. WPA -> XPA) e non sarebbe quindi recuperata
        # dal raggruppamento per build qui sotto.
        vicini.extend(_varianti_regionali_xiaomi(nomi, nome))
        if len(ago) < _TERMINE_MINIMO:
            continue
        vicini.extend(_piu_vicini(nomi, ago))

    # `_piu_vicini` limita deliberatamente il ripiego a tre nomi. Per una
    # famiglia già riconosciuta questo non basta: le tre righe iniziali del
    # tracker possono essere Taiwan/India/Russia e l'EEA, pur esistente,
    # resterebbe esclusa prima dell'ordinamento per mercato. La chiave della
    # build riunisce qui soltanto le release della *stessa* variante hardware
    # trovata sopra, incluse quelle che nel nome hanno l'alias dopo ``/``.
    chiavi = {chiave for chiave in (_chiave_prodotto_xiaomi(item) for item in vicini)
              if chiave}
    if chiavi:
        vicini.extend(
            item for item in all_items
            if _chiave_prodotto_xiaomi(item) in chiavi
        )
    return _risultati_xiaomi_ordinati(vicini, codice)


def _lookup_honor(model_name: str) -> list[RawItem]:
    """Stessa regola di `_lookup_xiaomi`: prima il nome esatto, poi chi lo
    contiene. «HONOR 200» non deve rispondere «HONOR 200 Pro»."""
    all_items, error = fetch_honor_aer()
    if error or not all_items:
        return []
    needle = modelcodes._normalize_name(model_name)
    if not needle:
        return []
    nomi = [(item, modelcodes._normalize_name(item.device or "")) for item in all_items]
    esatti = [item for item, nome in nomi if nome == needle]
    if esatti:
        return esatti[:3]
    return _piu_vicini(nomi, needle)


def _lookup_honor_security(model_name: str) -> list[RawItem]:
    """Supporto HONOR ufficiale per i modelli non presenti nel solo AER."""
    all_items, error = fetch_honor_security_bulletin()
    if error or not all_items:
        return []
    needle = modelcodes._normalize_name(model_name)
    if not needle:
        return []
    nomi = [(item, modelcodes._normalize_name(item.device or "")) for item in all_items]
    esatti = [item for item, name in nomi if name == needle]
    if esatti:
        return esatti[:3]
    return _piu_vicini(nomi, needle)


# Sotto questa lunghezza il termine cercato non identifica un telefono.
# La normalizzazione toglie il prefisso della marca, quindi «xiaomi 14»
# diventa «14»: due caratteri che compaiono dentro mezzo catalogo.
_TERMINE_MINIMO = 3

# LE PAROLE CHE CAMBIANO TELEFONO, non solo il nome.
#
# «POCO X6» non ha una voce propria nel tracker Xiaomi: esiste solo in
# coppia con l'altro marchio con cui condivide l'hardware («Redmi Note 13
# Pro 5G / POCO X6 5G Global»), e quella coppia porta sempre PIÙ parole di
# «POCO X6 Pro 5G Indonesia» — che di parole in più ne aggiunge poche, ma
# una di quelle è «Pro»: un telefono diverso, con un altro chip, non una
# confezione regionale dello stesso modello. Contarle tutte allo stesso
# modo faceva vincere il Pro sul modello base solo perché il nome vero del
# base è più lungo — la stessa famiglia di difetto che questa funzione
# diceva già di correggere, riapparsa in un'altra forma.
#
# Non tutte le parole in più sono uguali: una sigla di rete o una zona
# («5G», «Global», «India») restano lo stesso telefono; un marcatore di
# gamma («Pro», «Ultra», «Neo») no. Il criterio guarda solo la parola
# SUBITO DOPO la corrispondenza — non quelle prima, che possono essere il
# nome con cui un altro marchio rivende lo stesso hardware — ed è quella
# a decidere se il nome trovato è ancora il telefono chiesto o già un
# altro modello della stessa famiglia.
_PAROLE_VARIANTE = frozenset((
    "pro", "pro+", "proplus", "ultra", "plus", "max", "max+",
    "lite", "se", "fe", "neo", "gt", "prime", "turbo", "power",
    "mini", "edge", "air", "fold", "flip",
))


def _piu_vicini(nomi: list[tuple], cercato: str) -> list[RawItem]:
    """Fra i nomi che contengono quello cercato, i più vicini per primi.

    «Redmi Note 13» non ha una voce esatta nel catalogo, che elenca solo
    varianti regionali. Prendere quelle nell'ordine del catalogo rispondeva
    «Redmi Note 13 Pro+ 5G Taiwan»: un telefono diverso, con un altro chip
    e un altro firmware, scelto dal caso. Il criterio è il numero di parole
    in più: meno se ne aggiungono, più il nome è vicino a quello chiesto —
    ma prima ancora si scarta chi aggiunge un marcatore di gamma appena
    dopo il nome cercato (vedi `_PAROLE_VARIANTE`), perché quello non è
    "lo stesso telefono con qualche parola in più": è un altro telefono.

    **IL CONFRONTO È PER PAROLE INTERE, NON PER CARATTERI.** «xiaomi 14»
    normalizzato diventa «14» — la marca esce dal confronto — e «14» è
    contenuto dentro «14t»: cercando lo Xiaomi 14 rispondeva **Xiaomi
    14T**, che è un altro telefono. Un modello sbagliato è la risposta
    peggiore che questa funzione possa dare, peggio di nessuna risposta.

    E sotto i tre caratteri non si risponde affatto: un termine così corto
    non identifica niente, e qualunque cosa si scelga è un caso.
    """
    if len(cercato) < _TERMINE_MINIMO:
        return []
    parole = cercato.split()
    n = len(parole)

    def dopo_la_corrispondenza(nome: str) -> str | None:
        """`None` se il nome non contiene la frase cercata; altrimenti la
        parola subito dopo, o stringa vuota se la corrispondenza è in
        fondo al nome (nessun rischio: non c'è nient'altro che la segua)."""
        candidate = nome.split()
        for i in range(len(candidate) - n + 1):
            if candidate[i:i + n] == parole:
                return candidate[i + n] if i + n < len(candidate) else ""
        return None

    trovati = []
    for item, nome in nomi:
        seguente = dopo_la_corrispondenza(nome)
        if seguente is None:
            continue
        trovati.append((item, nome, seguente in _PAROLE_VARIANTE))

    # SI PREFERISCE SEMPRE CHI NON CAMBIA FASCIA. Solo se nessun candidato
    # resta lo stesso telefono si torna a quelli che lo fanno — meglio un
    # nome vicino ma di un'altra gamma che nessuna risposta, e il nome
    # restituito lo dichiara comunque per quello che è («Pro», «Ultra»...
    # restano scritti nel risultato, non vengono nascosti).
    stesso_telefono = [(item, nome) for item, nome, altra_fascia in trovati
                       if not altra_fascia]
    scelta = stesso_telefono or [(item, nome) for item, nome, _ in trovati]
    scelta.sort(key=lambda coppia: len(coppia[1].split()))
    return [item for item, _ in scelta[:3]]


def _lookup_motorola(model_name: str) -> list[RawItem]:
    """Cerca fra i modelli Motorola coperti dal mirror. Qui la copertura
    resta quella della tabella manuale (il mirror è organizzato per nome in
    codice interno, non per nome commerciale)."""
    query_code = normalizza_codice_modello(model_name)
    target = MOTOROLA_LOLINET_CODES.get(query_code)
    if target:
        # Il codice e' stato letto da un pacchetto reale: questa via non
        # mescola mai firmware di varianti XT sorelle.
        year, codename, commercial = target
        try:
            found = _lolinet_latest(codename, year)
        except Exception:
            return []
        if not found:
            return []
        filename, file_url, date_str = found
        model_code, android_version, build = _lolinet_metadata(filename, query_code)
        return [RawItem(
            title=f"Motorola {commercial} - build {build or filename}",
            link=file_url,
            published=iso(date_str.replace(" ", "T", 1)),
            brand=C.VIVO,
            device=f"Motorola {commercial}",
            model_code=model_code,
            build=build,
            android_version=android_version,
            size_info="Firmware ufficiale (mirror lolinet.com)",
        )]

    needle = modelcodes._normalize_name(model_name)
    if not needle:
        return []
    for year, codename, commercial in MOTOROLA_LOLINET_DEVICES:
        if needle not in modelcodes._normalize_name(commercial):
            continue
        try:
            found = _lolinet_latest(codename, year)
        except Exception:
            return []
        if not found:
            return []
        filename, file_url, date_str = found
        name_match = _LOLINET_NAME_RE.search(filename)
        return [RawItem(
            title=f"Motorola {commercial} — build {name_match.group(3) if name_match else filename}",
            link=file_url,
            published=iso(date_str.replace(" ", "T", 1)),
            brand=C.VIVO,
            device=f"Motorola {commercial}",
            build=name_match.group(3) if name_match else None,
            android_version=int(name_match.group(2)) if name_match else None,
            size_info="Firmware ufficiale (mirror lolinet.com)",
        )]
    return []


def _lookup_apple(model_name: str) -> list[RawItem]:
    """Versione iOS/iPadOS di un iPhone/iPad specifico.

    Accetta sia il nome commerciale ('iPhone 15 Pro') sia l'identificatore
    interno ('iPhone16,1'). Il nome viene tradotto in identificatore e si
    interroga la lista firmware DI QUEL dispositivo: nessuna inferenza, e
    quindi nessuna possibilità di attribuire a un modello una versione che
    non gli appartiene (vedi la nota sul disegno precedente più sopra).

    Se il nome non è traducibile in un identificatore noto, si restituisce
    lista vuota: meglio dire "non lo so" che indovinare.
    """
    from . import appledevices

    query = (model_name or "").strip()
    if not query:
        return []

    if appledevices.is_apple_identifier(query):
        identificatori = [query]
    else:
        identificatori = appledevices.identifiers_for(query)

    items = []
    for identifier in identificatori[:3]:
        try:
            item, _ = _apple_item_for(identifier)
        except Exception:
            continue
        if item:
            items.append(item)
    return items


# ======================================================================
# Registro delle ricerche su fonte ufficiale
# ======================================================================
# PERCHÉ NON UNA MAPPA BRAND → FUNZIONE (com'era prima).
# Il difetto non era in una singola fonte ma nell'impianto: si deduceva un
# brand, si sceglieva UNA funzione e si accettava il suo esito come
# definitivo. Bastava che la deduzione fosse imprecisa — o che un
# contenitore raggruppasse più produttori — perché la ricerca fallisse
# senza appello. È il caso di «Oppo / Realme / OnePlus»: tre marchi
# diversi in un contenitore solo, con l'unica fonte disponibile che è
# quella realme. Ogni dispositivo Oppo e OnePlus era irraggiungibile per
# costruzione, e la stessa cosa sarebbe successa a ogni nuovo brand
# aggiunto a un contenitore condiviso.
#
# Ora il brand serve solo a stabilire l'ORDINE dei tentativi, non a
# escluderli: si prova la fonte più probabile per prima, poi le altre
# economiche, finché il tempo a disposizione lo consente. Aggiungere una
# fonte nuova la rende automaticamente raggiungibile da qualunque forma di
# ricerca, senza toccare la logica di ricerca.
#
# `costo` indica quante richieste di rete servono nel caso peggiore: le
# fonti costose si interrogano solo quando il brand corrisponde davvero,
# per non far pagare a ogni ricerca il prezzo di tutte le altre.
@dataclass
class StructuredLookup:
    brand: str
    funzione: Callable[[str], list]
    costo: str          # "basso" = una richiesta, "alto" = una per dispositivo
    etichetta: str
    # Funzione che scarica l'intera fonte. Serve alla diagnosi per
    # distinguere «modello assente da questa fonte» da «fonte
    # irraggiungibile»: la ricerca per modello restituisce solo gli item e
    # l'errore andrebbe altrimenti perduto.
    fetch: Callable[[], tuple] | None = None
    # Livello di fiducia. In coda ai campi di proposito: `fetch` è già
    # passato come quinto argomento POSIZIONALE in mezza dozzina di punti,
    # e infilare un campo prima di lui li avrebbe silenziosamente
    # riassegnati tutti — il tipo di rottura che i test non vedono perché
    # i tipi combaciano.
    #
    # Predefinito STRUCTURED perché fino a ieri qui c'erano solo fonti
    # ufficiali; da quando ce n'è una CURATED, il valore va dichiarato.
    trust: str = C.TRUST_STRUCTURED
    # Il dato attuale è la norma per questi lookup; le eccezioni (schede,
    # supporto e beta) sono dichiarate esplicitamente in elenco.
    firmware_kind: str = C.FW_CURRENT


_STRUCTURED_LOOKUPS_LIST = [
    StructuredLookup(C.SAMSUNG, _lookup_samsung, "alto", "controllo versione Samsung"),
    StructuredLookup(C.APPLE, _lookup_apple, "alto", "firmware Apple per dispositivo"),
    StructuredLookup(C.VIVO, _lookup_motorola, "alto", "mirror firmware Motorola"),
    StructuredLookup(C.PIXEL, _lookup_pixel, "basso", "immagini OTA ufficiali Pixel",
                     fetch_pixel_ota, firmware_kind=C.FW_BETA),
    StructuredLookup(C.VIVO, _lookup_vivo, "basso", "piano ufficiale vivo",
                     fetch_vivo_aer, firmware_kind=C.FW_FACTORY),
    StructuredLookup(C.XIAOMI, _lookup_xiaomi, "basso", "catalogo Xiaomi", fetch_xiaomi),
    StructuredLookup(C.HUAWEI, _lookup_honor, "basso", "piano ufficiale Honor",
                     fetch_honor_aer, firmware_kind=C.FW_FACTORY),
    StructuredLookup(C.HUAWEI, _lookup_honor_security, "basso",
                     "bollettino sicurezza ufficiale Honor Italia",
                     fetch_honor_security_bulletin, firmware_kind=C.FW_SUPPORT),
    # Prima delle due fonti Oppo che danno la versione di fabbrica: questa
    # dà quella davvero rilasciata.
    #
    # Costo "basso" anche se fa una richiesta per dispositivo, e la ragione
    # merita una riga: il catalogo dei modelli coperti sta in memoria, e un
    # nome che non c'è viene escluso SENZA toccare la rete. La richiesta si
    # paga solo quando il modello esiste davvero — cioè quando serve.
    # Marcarla "alto" la faceva entrare solo a brand già dedotto, e
    # «find x2» scritto senza «oppo» non trovava niente.
    StructuredLookup(C.OPPO, _lookup_oppo_support, "basso",
                     "archivio firmware ufficiale Oppo"),
    # SUBITO DOPO l'archivio ufficiale, e PRIMA delle due fonti che danno
    # la versione di fabbrica. L'ordine è la tesi di tutta l'aggiunta:
    #   1. se Oppo pubblica il firmware di quel modello, vince Oppo;
    #   2. altrimenti una build reale da un canale dichiaratamente non
    #      ufficiale vale più della versione con cui il telefono è uscito
    #      di fabbrica tre anni fa;
    #   3. e comunque il trust CURATED impedisce che sovrascriva un dato
    #      ufficiale già in archivio.
    StructuredLookup(C.OPPO, _lookup_oplus_arb, "basso",
                     "tracker ARB OnePlus/OPPO (non ufficiale)",
                     fetch_oplus_arb, trust=C.TRUST_CURATED),
    # Il piano ufficiale risponde alla domanda "Android 16 è previsto?",
    # ma viene dopo le build correnti: non deve nascondere un firmware reale
    # dell'archivio OPPO o del tracker ARB.
    StructuredLookup(C.OPPO, _lookup_oppo_coloros16, "basso",
                     "piano ufficiale OPPO ColorOS 16", fetch_oppo_coloros16,
                     firmware_kind=C.FW_SUPPORT),
    # La serie OPPO A moderna non è nel tracker ARB né nell'archivio
    # ufficiale legacy. I pacchetti CPH osservabili colmano quel buco ma
    # restano REPORTED, non un'asserzione sullo stato OTA del singolo telefono.
    StructuredLookup(C.OPPO, _lookup_oppo_firmware_archive, "basso",
                     "archivio tecnico OPPO (build per codice)",
                     trust=C.TRUST_CURATED, firmware_kind=C.FW_REPORTED),
    # Per realme recenti non esiste un endpoint OTA pubblico. L'archivio
    # tecnico è una fonte REPORTED (non CURRENT), protetta dal controllo del
    # codice sul sito realme e ordinata GDPR/Europa prima del ramo Export.
    StructuredLookup(C.OPPO, _lookup_realme_firmware_archive, "basso",
                     "archivio tecnico realme (build per codice)",
                     trust=C.TRUST_CURATED, firmware_kind=C.FW_REPORTED),
    # `oplus_telegram` tolta di qui l'11/08/2026 insieme al resto della
    # fonte — vedi il commento sopra `RETIRED_SOURCES` per il motivo e come
    # riportarla.
    StructuredLookup(C.OPPO, _lookup_realme, "basso", "piano ufficiale realme",
                     fetch_realme_aer, firmware_kind=C.FW_FACTORY),
    StructuredLookup(C.OPPO, _lookup_oppo, "basso", "elenco ufficiale Oppo",
                     fetch_oppo_aer, firmware_kind=C.FW_SUPPORT),
    # In fondo alle economiche, appena prima di GSMArena: le pagine
    # ufficiali di marca hanno la versione di fabbrica e vanno provate
    # prima. Questa risponde per QUALSIASI marca — comprese quelle senza
    # fonte dedicata, OnePlus in testa — e riconosce anche i codici
    # tecnici, che è il motivo più frequente di ricerca a vuoto.
    StructuredLookup(None, _lookup_aer_catalog, "basso",
                     "catalogo Android Enterprise Recommended", fetch_aer_catalog,
                     firmware_kind=C.FW_SUPPORT),
]

# Ripiego universale: vale per QUALSIASI marca, comprese quelle senza
# fonte ufficiale. Va provato per ultimo perché costa due richieste e dà
# la versione di fabbrica, non quella attuale — ma è meglio di niente, ed
# è l'unica cosa disponibile per Oppo, vivo, OnePlus e i brand minori.
def _gsmarena_lookup() -> StructuredLookup:
    # Costruita al momento dell'uso: la funzione è definita più in basso
    # nel file, e riferirla qui a livello di modulo darebbe NameError.
    return StructuredLookup(
        brand=None, funzione=_lookup_gsmarena, costo="medio",
        etichetta="scheda tecnica GSMArena",
        # GSMArena è una scheda di fabbrica, non l'ultimo OTA. La ricerca
        # la usa solo per identificazione e specifiche; non entra in
        # storage.get_devices né nel feed firmware.
        firmware_kind=C.FW_FACTORY,
    )

# Mantenuta per compatibilità con il codice esistente e i test.
_STRUCTURED_LOOKUPS = {v.brand: v.funzione for v in _STRUCTURED_LOOKUPS_LIST}


# Prefissi dei codici modello ufficiali, per dedurre il brand quando la
# ricerca è un codice tecnico puro: "RMX3939" non contiene la parola
# "realme", quindi senza questa tabella la ricerca per codice non riusciva
# a individuare la fonte ufficiale da interrogare.
_CODE_BRAND_PATTERNS = [
    (re.compile(r"^RMX\d{4}", re.I), C.OPPO),        # realme
    (re.compile(r"^RMP\d{4}", re.I), C.OPPO),        # realme Pad
    (re.compile(r"^CPH\d{4}", re.I), C.OPPO),        # Oppo / OnePlus
    (re.compile(r"^SM-[A-Z0-9]{4,}", re.I), C.SAMSUNG),
    (re.compile(r"^(?:iPhone|iPad|iPod)\d+,\d+", re.I), C.APPLE),
    (re.compile(r"^XT\d{4}", re.I), C.VIVO),         # Motorola
    # Huawei/Honor: ABR-LX1, ANA-AL00, ELS-NX9 — 3 lettere, trattino, poi
    # 2 lettere e da una a quattro cifre/lettere secondo la variante.
    (re.compile(r"^[A-Z]{3}-[A-Z]{2}\w{1,4}$", re.I), C.HUAWEI),
]


# ======================================================================
# Onestà sulla copertura
# ======================================================================
# A cosa serve. Una ricerca che restituisce il modello senza il firmware
# è vissuta come un guasto dell'app, non come un limite del produttore —
# ed è comprensibile, perché finora l'app non diceva la differenza. Il
# dato mancante resta mancante, ma sapere PERCHÉ manca è la differenza
# fra uno strumento che si può usare e uno di cui non ci si fida.
_NOTE_COPERTURA = {
    C.OPPO: (
        "OPPO, OnePlus e realme non pubblicano da nessuna parte la versione "
        "OTA corrente per modello: i portali ufficiali rispondono 403/404 e "
        "l'API OTA pretende l'impronta del dispositivo. Coperti con build "
        "riportata: pacchetti RMX e CPH moderni dell'archivio tecnico, "
        "l'archivio OPPO legacy e una copertura verificabile ma parziale "
        "(ARB) per OnePlus/OPPO. Fuori da questi casi l'app mostra "
        "identificazione e scheda tecnica, non una versione di fabbrica "
        "come firmware attuale."
    ),
    C.VIVO: (
        "vivo e iQOO pubblicano il piano di supporto ufficiale ma non la "
        "build per modello. Per Motorola la build reale c'è (mirror lolinet)."
    ),
    C.OTHER: (
        "Marca senza fonte dedicata: si può solo riportare quanto scrivono "
        "le testate, con l'incertezza che questo comporta."
    ),
}


def nota_copertura(brand: str | None) -> str | None:
    """Perché per questa marca può mancare il firmware. None se la marca
    ha una fonte che pubblica la versione attuale."""
    return _NOTE_COPERTURA.get(brand or "")


# Nome della marca come lo scrivono i dataset -> gruppo dell'applicazione.
#
# **IL DATASET È CINESE PRIMA CHE INGLESE.** MobileModels nasce in Cina e
# scrive le marche nella loro lingua: `SM-G9900` è di 三星, `DE2117` di
# 一加. Su 3577 nomi di marca distinti, sedici sono in caratteri cinesi e
# coprono da soli oltre quattromila codici — Samsung, Xiaomi, Huawei,
# Honor, OnePlus fra questi.
#
# Elencarli è possibile perché i produttori sono un insieme chiuso, a
# differenza dei formati dei codici che sono infiniti.
_GRUPPO_DI_MARCA = {
    "samsung": C.SAMSUNG, "三星": C.SAMSUNG,
    "apple": C.APPLE, "苹果": C.APPLE,
    "google": C.PIXEL, "谷歌": C.PIXEL,
    "xiaomi": C.XIAOMI, "redmi": C.XIAOMI, "poco": C.XIAOMI,
    "小米": C.XIAOMI, "红米": C.XIAOMI, "黑鲨": C.XIAOMI,
    "huawei": C.HUAWEI, "honor": C.HUAWEI,
    "华为": C.HUAWEI, "华为智选": C.HUAWEI, "荣耀": C.HUAWEI,
    "oppo": C.OPPO, "realme": C.OPPO, "oneplus": C.OPPO, "one plus": C.OPPO,
    "一加": C.OPPO, "真我": C.OPPO, "欧珀": C.OPPO,
    "vivo": C.VIVO, "iqoo": C.VIVO, "motorola": C.VIVO, "moto": C.VIVO,
    "维沃": C.VIVO, "摩托罗拉": C.VIVO,
    # Le marche che l'app raggruppa sotto «Altri brand» sono elencate una
    # per una, non dedotte per esclusione: dire «altri» a tutto ciò che non
    # si riconosce è ciò che aveva scavalcato le regole buone. Qui
    # «Altri brand» è una risposta, non un ripiego.
    "nothing": C.OTHER, "cmf": C.OTHER, "nokia": C.OTHER, "诺基亚": C.OTHER,
    "tecno": C.OTHER, "infinix": C.OTHER, "itel": C.OTHER,
    "asus": C.OTHER, "sony": C.OTHER, "fairphone": C.OTHER,
    "umidigi": C.OTHER, "doogee": C.OTHER, "cubot": C.OTHER,
    "blackview": C.OTHER, "ulefone": C.OTHER, "oukitel": C.OTHER,
}


def gruppo_di_marca(marca: str) -> str | None:
    """Da «OPPO», «vivo», «三星»… al gruppo usato dall'applicazione.

    **None quando la marca non è fra quelle raggruppate**, e la
    distinzione è tutto: rispondere «Altri brand» sembrava innocuo, ma
    questa funzione decide PRIMA delle regole sul formato del codice. Con
    3577 nomi di marca nei dataset, quasi tutti fuori elenco, un «Altri
    brand» qui cancellava il riconoscimento di `SM-…` come Samsung — che
    funzionava da sempre. Misurato: Samsung era sceso al 75% di coerenza
    fra ricerca per nome e per codice, Redmi al 13%.

    Tacere lascia decidere a chi viene dopo, che per Nokia o ZTE arriverà
    comunque ad «Altri brand» — ma passando dalle strade giuste.
    """
    testo = " ".join((marca or "").lower().split())
    if not testo:
        return None
    for nome, gruppo in _GRUPPO_DI_MARCA.items():
        if testo == nome or testo.startswith(nome + " "):
            return gruppo
    return None


def brand_from_code(query: str) -> str | None:
    """Brand di un codice modello, o None.

    **PRIMA IL DATO, POI L'INDOVINELLO.** I dataset dei codici dichiarano la
    marca riga per riga, e finora quel campo veniva buttato via: la marca si
    deduceva da una manciata di formati scritti a mano, quindi ogni famiglia
    non prevista — `PCET00` di Oppo, `V2283A` di vivo, `CLT-L04` di Huawei,
    `G020E` di un Pixel — finiva sotto «Altri brand». Non è un dettaglio di
    presentazione: il brand entra nella chiave del dispositivo, quindi lo
    stesso telefono cercato per nome e per codice diventava due schede.

    I formati restano, dopo, per i codici che nessun dataset conosce.
    """
    testo = re.sub(r"\s+", "", (query or "")).upper()
    # Alcuni codici hanno uno spazio dentro («TECNO W5006S»): si prova sia
    # la forma compattata sia quella scritta, o metà dataset non risponde.
    for forma in (testo, " ".join((query or "").upper().split())):
        try:
            dichiarata = modelcodes.marca_dichiarata(forma)
        except Exception:  # pragma: no cover - il dataset non deve mai bloccare
            dichiarata = None
        if dichiarata:
            gruppo = gruppo_di_marca(dichiarata)
            if gruppo:
                return gruppo

    if espandi_codice_samsung(query):
        return C.SAMSUNG
    for pattern, brand in _CODE_BRAND_PATTERNS:
        if pattern.match(testo):
            return brand
    return None


def _sottomarca_nominata(testo: str) -> str | None:
    """La sotto-marca scritta nel testo («oneplus», «realme», «poco»…).

    Serve perché `brand` in questo progetto è un GRUPPO, non un
    produttore: `C.OPPO` vale «Oppo / Realme / OnePlus» tutti insieme, e
    dentro un gruppo il nome del produttore distingue eccome — esistono
    sia un OPPO A5 sia un realme A5. L'elenco è quello che `extract` usa
    già per la stessa distinzione, non una seconda copia da tenere
    allineata.
    """
    parole = set(re.sub(r"[^a-z0-9 ]+", " ", (testo or "").lower()).split())
    if not parole:
        return None
    for sottomarche in extract._SOTTOMARCHE_DEL_GRUPPO.values():
        for sottomarca in sottomarche:
            if sottomarca in parole:
                return sottomarca
    return None


def _scarta_marca_sbagliata(items: list, marca_chiesta: str | None) -> list:
    """Toglie i risultati di una marca diversa da quella chiesta.

    Se la domanda non nomina nessun produttore non si scarta niente: è il
    caso ambiguo («a15»), dove più marche sono risposte legittime e
    l'applicazione le mostra tutte.

    ## Il gruppo non basta: serve anche la sotto-marca

    CASO REALE, e comparso solo dopo aver reso veloce la fonte realme.
    Cercando «OnePlus 12» la risposta era **«realme 12x 5G»**. Il filtro
    sul gruppo non poteva vederlo: OnePlus e realme stanno tutti e due in
    `C.OPPO`, quindi per lui erano la stessa marca. A far combaciare i due
    nomi è `_normalize_name`, che toglie il prefisso del produttore — «OnePlus
    12» diventa «12» — dopo di che la ricerca per somiglianza trova «12x 5G».

    Il difetto c'era da prima; a nasconderlo era la lentezza. Finché la
    pagina realme si riscaricava a ogni forma, quella fonte non faceva in
    tempo a rispondere e vinceva il tracker ARB, che il OnePlus 12 ce
    l'ha davvero. Sistemata la lentezza, la fonte sbagliata è arrivata
    prima — un buon promemoria che una fonte lenta può mascherare una
    fonte che risponde male.
    """
    if not marca_chiesta:
        return items
    tenuti = [i for i in items if not i.brand or i.brand == marca_chiesta]
    return tenuti


def _scarta_sottomarca_sbagliata(items: list, chiesto: str) -> list:
    """Dentro lo stesso gruppo, tiene solo chi non contraddice la domanda.

    Un risultato che non nomina nessun produttore non viene scartato: i
    cataloghi elencano parecchi modelli col solo nome commerciale («Nord
    CE 3 Lite»), e pretendere la marca lì butterebbe via risposte giuste.
    Si scarta solo chi ne nomina una **diversa** da quella chiesta.
    """
    voluta = _sottomarca_nominata(chiesto)
    if not voluta:
        return items
    return [
        i for i in items
        if (_sottomarca_nominata(i.device or "") or voluta) == voluta
    ]


def brand_from_known_device(query: str) -> str | None:
    """Brand dedotto dal fatto che il nome compare in un catalogo ufficiale.

    Serve per le ricerche senza marca: chi scrive «c63» o «x8c» indica un
    modello preciso, ma quel testo non contiene il nome del produttore e
    non ha il formato di un codice tecnico. Cercarlo nei cataloghi già
    scaricati dice a quale marca appartiene, e quindi quale fonte ufficiale
    interrogare.
    """
    chiave = modelcodes._normalize_name(query)
    if not chiave or len(chiave) < 2:
        return None
    try:
        if chiave in realme_name_variants():
            return C.OPPO
    except Exception:
        pass
    try:
        for codice in modelcodes.codes_for_name(query):
            brand = brand_from_code(codice)
            if brand:
                return brand
    except Exception:
        pass
    return None


# Marche che si scrivono davanti a una sigla nuda («samsung a32») e che
# vanno tolte prima di riconoscerla.
_RE_MARCA_DAVANTI = re.compile(
    r"^\s*(?:samsung|galaxy|oppo|realme|vivo|iqoo|honor|huawei|xiaomi|redmi|poco|"
    r"motorola|moto|oneplus|nothing)\s+", re.IGNORECASE)
# Sigla nuda: una lettera, due o tre cifre, eventuale suffisso corto.
_RE_SIGLA_CORTA = re.compile(r"^([A-Za-z])\s*(\d{2,3})\s*([A-Za-z]{0,2})$")
# Gamma sotto cui una sigla nuda va letta, PER MARCA. Cablare «Galaxy» per
# tutti era un errore attivo: «oppo a96» diventava «Galaxy A96», un
# telefono che non esiste, e la ricerca non poteva che fallire.
_GAMME_PER_SIGLA = {
    "samsung": "Galaxy", "galaxy": "Galaxy",
    "oppo": "OPPO",
    "realme": "realme",
    "vivo": "vivo", "iqoo": "iQOO",
    "honor": "HONOR",
    "huawei": "Huawei",
    "xiaomi": "Xiaomi", "redmi": "Redmi", "poco": "POCO",
    "oneplus": "OnePlus",
}
# Senza marca scritta, la sigla da sola non dice di chi sia: si provano le
# gamme che numerano davvero in questo modo. Un nome inesistente non trova
# nulla e non fa danno, mentre indovinarne una sola sbagliata fa fallire
# ricerche che avrebbero successo.
_GAMME_SENZA_MARCA = ["Galaxy", "OPPO", "realme", "vivo", "HONOR", "Redmi"]


def _nomi_da_sigla_corta(query: str) -> list[str]:
    """«a32» → «Galaxy A32». «samsung a32» → «Galaxy A32».

    Vale solo per la forma «lettera + 2-3 cifre», che è quella delle serie
    A/M/F Samsung. Non si inventa una gamma quando il testo non la implica:
    una sigla di quattro cifre è già un codice e passa da un'altra strada.
    """
    testo = " ".join(str(query or "").split())
    if not testo:
        return []
    # Se è già un codice valido non serve inventargli una gamma: «a325f»
    # produrrebbe un inesistente «Galaxy A325F», rumore che allunga la
    # ricerca senza aggiungere niente.
    if looks_like_model_code(testo):
        return []
    marca = ""
    match_marca = _RE_MARCA_DAVANTI.match(testo)
    if match_marca:
        marca = match_marca.group(0).strip().lower()
        testo = testo[match_marca.end():]

    match = _RE_SIGLA_CORTA.match(testo.strip())
    if not match:
        return []
    lettera, cifre, coda = match.groups()
    sigla = f"{lettera.upper()}{cifre}{coda.upper()}"

    # TRE CIFRE SONO GIÀ UN CODICE, non un nome commerciale: «a235» è la
    # radice di `SM-A235F`, non un «Galaxy A235» — che non esiste. Prima
    # veniva inventato quel nome, e per giunta al posto dell'espansione del
    # codice, che avrebbe funzionato: «samsung a235» non trovava nulla
    # mentre «a235» da solo sì.
    if len(cifre) == 3 and not coda:
        return []

    if marca:
        gamma = _GAMME_PER_SIGLA.get(marca)
        return [f"{gamma} {sigla}"] if gamma else []
    return [f"{g} {sigla}" for g in _GAMME_SENZA_MARCA]


# «note13» → «note 13», e «note 13» → «note13». Le lettere devono essere
# almeno due: separare `A32` in `A 32` produrrebbe una sigla che non
# esiste, e quella strada è già coperta da `_nomi_da_sigla_corta`.
_RE_LETTERA_CIFRA = re.compile(r"([A-Za-z]{2,})(\d)")
_RE_SPAZIO_CIFRA = re.compile(r"([A-Za-z]{2,})\s+(\d)")


def expand_query(query: str) -> list[str]:
    """Tutte le forme equivalenti con cui questo modello può essere indicato.

    QUESTA È LA CORREZIONE SISTEMICA. Prima ogni fonte espandeva la ricerca
    per conto proprio: realme risolveva i codici e i nomi regionali, Samsung
    e Honor no, Apple gestiva solo i propri identificatori. Ne seguiva che
    la stessa forma di scrittura funzionava con una marca e falliva con
    un'altra — ed è il motivo per cui correggere un caso ne rompeva un
    altro, all'infinito.

    Ora l'espansione avviene UNA VOLTA, qui, e ogni fonte riceve tutte le
    forme. Una fonte nuova eredita automaticamente la risoluzione dei
    codici, dei nomi regionali e degli identificatori, senza dover
    reimplementare nulla.
    """
    query = (query or "").strip()
    if not query:
        return []

    candidati = [query]

    # Il codice va cercato ANCHE senza la marca davanti: «samsung a235»
    # contiene il codice `a235`, ma con la parola «samsung» attaccata non ha
    # più la forma di un codice e non veniva riconosciuto. Risultato: la
    # stessa ricerca funzionava scritta «a235» e falliva scritta
    # «samsung a235», che è il modo più naturale di scriverla.
    testi_da_esaminare = [query]
    senza_marca = _RE_MARCA_DAVANTI.sub("", query).strip()
    if senza_marca and senza_marca != query:
        testi_da_esaminare.append(senza_marca)

    # Codice tecnico → nomi commerciali (RMX3939 → realme C63/…)
    #
    # `resolve_senza_ambiguita`, NON `resolve`, per lo stesso motivo già
    # documentato in `scan.py::forme_equivalenti`: il dataset community
    # riusa lo stesso nome («C61») per più codici diversi, e passarlo
    # com'è come FORMA A SÉ STANTE (non solo come candidato interno di una
    # singola fonte) faceva sì che ogni fonte strutturata venisse
    # interrogata anche per il nome ambiguo, riportando indietro il
    # firmware del telefono sbagliato — «RMX3939» tornava con i dati di
    # «RMX3930» perché entrambi condividono l'alias «C61», e questa
    # funzione lo aggiungeva a `forme` senza controllare l'ambiguità
    # (bug reale, segnalato dall'utente cercando «RMX3939» sul sito).
    # `nomi` (non filtrato) resta per capire se il codice è conosciuto
    # ALMENO in parte: un codice con soli alias ambigui non deve sembrare
    # sconosciuto e finire nel ramo «codice incompleto» qui sotto.
    for codice in dict.fromkeys(
            c for testo in testi_da_esaminare for c in _code_candidates(testo)):
        nomi = modelcodes.resolve(codice)
        candidati.extend(modelcodes.resolve_senza_ambiguita(codice))
        if nomi:
            continue
        # CODICE INCOMPLETO. Chi scrive «a325» intende il Galaxy A32, ma nel
        # dataset esistono solo `SM-A325F`, `SM-A325M`, `SM-A325N`: l'ultima
        # lettera è il mercato. Senza questo passaggio la ricerca falliva
        # avendo il dato a un carattere di distanza — ed è una delle forme
        # più comuni, perché il codice si legge sulla scatola senza la
        # lettera finale o si ricorda a metà.
        for completo in modelcodes.codici_per_prefisso(codice):
            candidati.append(completo)
            candidati.extend(modelcodes.resolve_senza_ambiguita(completo))

    # NOME CORTO SENZA GAMMA. «a32» e «samsung a32» sono il modo più
    # naturale di chiamare un Galaxy A32, e non venivano riconosciuti né
    # come codice (due cifre sono troppo poche) né come nome (il catalogo
    # lo chiama «Galaxy A32»). Si prova quindi la forma con la gamma
    # davanti, che è l'unica cosa che manca.
    for esteso in _nomi_da_sigla_corta(query):
        candidati.append(esteso)

    # LA MARCA AL POSTO DELLA GAMMA. «samsung s23 ultra» non arrivava a
    # nessun codice mentre «galaxy s23 ultra» sì: il catalogo scrive
    # «Galaxy S23 Ultra», e chi cerca scrive il nome della marca al posto
    # di quello della gamma — che è il modo più naturale di chiamarlo.
    #
    # `_nomi_da_sigla_corta` copre già questo, ma solo per la forma
    # «lettera + due cifre» («samsung a32»): appena c'è una parola in più
    # («ultra», «plus», «fe») non riconosce più niente, e sono proprio i
    # modelli di punta.
    marca_iniziale = _RE_MARCA_DAVANTI.match(query)
    if marca_iniziale:
        parola = marca_iniziale.group(0).strip().lower()
        gamma = _GAMME_PER_SIGLA.get(parola)
        resto = query[marca_iniziale.end():].strip()
        if gamma and resto and gamma.lower() != parola:
            candidati.append(f"{gamma} {resto}")

    # LO SPAZIO FRA LE LETTERE E LE CIFRE NON DISTINGUE NIENTE.
    #
    # Misurato interrogando il sito, non dedotto: «redmi note13» e
    # «pixel9» non trovavano nessun firmware, mentre «Redmi Note 13» e
    # «Pixel 9» lo trovavano. Lo stesso telefono, la stessa domanda, due
    # esiti — e quello muto tocca alla forma che si digita di fretta.
    #
    # Si aggiungono ENTRAMBE le forme, staccata e attaccata, perché
    # l'incoerenza va nei due versi: «moto g 14» deve arrivare a «Moto
    # G14» tanto quanto «redmi note13» deve arrivare a «Redmi Note 13».
    # Sono candidati in più, non sostituzioni: se la forma originale
    # risponde, risponde per prima e queste non vengono nemmeno provate.
    for testo in list(candidati):
        for variante in (_RE_LETTERA_CIFRA.sub(r"\1 \2", testo),
                         _RE_SPAZIO_CIFRA.sub(r"\1\2", testo)):
            variante = " ".join(variante.split())
            if variante and variante != testo:
                candidati.append(variante)

    # Nome regionale → nomi gemelli dello stesso dispositivo
    try:
        variante = realme_name_variants().get(modelcodes._normalize_name(query))
        if variante:
            candidati.extend(variante[0])
    except Exception:
        pass

    # Identificatore interno Apple → nome commerciale
    try:
        from . import appledevices

        if appledevices.is_apple_identifier(query):
            nome = appledevices.name_for(query)
            if nome:
                candidati.append(nome)
    except Exception:
        pass

    # Deduplica conservando l'ordine di preferenza
    visti, ordinati = set(), []
    for c in candidati:
        chiave = modelcodes._normalize_name(c)
        if c and chiave not in visti:
            visti.add(chiave)
            ordinati.append(c)
    return ordinati[:C.SEARCH_MAX_CANDIDATES + 2]


def lookup_model_structured(model_name: str, brand: str | None = None):
    """Cerca il modello nelle fonti ufficiali, senza fermarsi alla prima.

    Ritorna `(items, note)`. `items` vuoto non è un errore: significa che
    nessuna fonte ufficiale conosce quel modello — resta la ricerca su
    notizie, che il chiamante esegue comunque.

    IMPIANTO (e perché è cambiato). Prima si deduceva un brand, si sceglieva
    UNA funzione e il suo esito era definitivo: una deduzione imprecisa, o un
    contenitore che raggruppa più produttori, condannava la ricerca senza
    appello. Ora il brand stabilisce solo l'ORDINE dei tentativi:
      1. la fonte del brand dedotto, se c'è;
      2. tutte le altre fonti economiche (una richiesta di rete ciascuna);
      3. le fonti costose (una richiesta per dispositivo) solo se il brand
         corrisponde, per non far pagare a ogni ricerca il prezzo di tutte.
    Il tutto entro un tetto di tempo, come la ricerca su notizie.
    """
    model_name = (model_name or "").strip()
    if not model_name:
        return [], "nessun modello indicato"

    brand = (
        brand
        or extract.detect_brand(model_name)
        or brand_from_code(model_name)
        or brand_from_known_device(model_name)
    )
    if not brand:
        # LA MARCA SI DEDUCE ANCHE DALLE FORME ESPANSE, non solo dal testo
        # digitato. «a32» non contiene nulla che riveli il produttore, ma si
        # espande in «Galaxy A32», che sì. Senza questo passaggio la fonte
        # Samsung — che è costosa e quindi entra solo a marca nota — non
        # veniva mai interrogata, e la ricerca finiva a vuoto pur avendo
        # riconosciuto il modello un attimo prima.
        for forma in expand_query(model_name):
            brand = (extract.detect_brand(forma)
                     or brand_from_code(forma)
                     or brand_from_known_device(forma))
            if brand:
                break

    # Le fonti che parlano di catalogo/supporto devono conservare la loro
    # semantica fino alla UI: il RawItem è il veicolo tra questo lookup e
    # `scan.normalize`.
    ordinati = _lookup_order(brand)
    if not ordinati:
        return [], "nessuna fonte ufficiale disponibile"

    # Con una sigla senza marca, dedurne UNA sola esclude le fonti costose
    # delle altre: per «a15» la marca dedotta era Oppo, e il controllo
    # versione Samsung — che avrebbe dato il Galaxy A15 su Android 16 — non
    # entrava nemmeno nell'elenco. Si uniscono quindi gli ordini di tutte le
    # marche implicate dalle forme espanse.
    if not looks_like_model_code(model_name) and not extract.detect_brand(model_name):
        viste = {id(v.funzione) for v in ordinati}
        for forma in expand_query(model_name):
            altra = extract.detect_brand(forma) or brand_from_known_device(forma)
            if not altra or altra == brand:
                continue
            for voce in _lookup_order(altra):
                if id(voce.funzione) not in viste:
                    viste.add(id(voce.funzione))
                    ordinati.append(voce)

    # Ogni fonte riceve TUTTE le forme equivalenti della ricerca, non solo
    # il testo digitato: è ciò che rende uniforme il comportamento fra
    # marche diverse (vedi expand_query).
    forme = expand_query(model_name) or [model_name]

    # QUANDO LA MARCA NON È SCRITTA, LA DOMANDA È AMBIGUA.
    # «a15» è insieme un OPPO A15 e un Galaxy A15, ed esistono entrambi. La
    # ricerca si ferma alla prima fonte che ha una versione, e l'ordine
    # delle fonti è per costo, non per pertinenza: rispondeva «OPPO A15,
    # patch 2022-04» senza mai interrogare Samsung, e senza dire che stava
    # scegliendo. Una risposta sola a una domanda con due risposte è
    # sbagliata anche quando è verificata.
    #
    # Con la marca scritta, o con un codice, l'ambiguità non c'è e ci si
    # ferma al primo risultato buono come prima.
    ambigua = not looks_like_model_code(model_name) and not extract.detect_brand(model_name)

    # LA MARCA SCRITTA NELLA DOMANDA È UN VINCOLO, non un suggerimento.
    #
    # Le fonti si confrontano su un nome NORMALIZZATO, e la
    # normalizzazione toglie il prefisso della marca perché «Samsung Galaxy
    # S24» e «Galaxy S24» sono lo stesso telefono. L'effetto collaterale è
    # che «OnePlus Pad Go» diventa «pad go», che è contenuto in «Redmi Pad
    # Go Russia»: il catalogo Xiaomi rispondeva a una domanda su OnePlus, e
    # rispondeva pure con una versione, quindi vinceva.
    #
    # Un modello di un'altra marca non è un risultato parziale: è la
    # risposta sbagliata. Se la domanda nomina un produttore, chi non è
    # quello viene scartato.
    marca_dichiarata_dalla_query = extract.detect_brand(model_name)

    scadenza = time.monotonic() + C.SEARCH_BUDGET_SECONDS
    tentate, fallite = [], []
    ripiego = None      # risultato che conferma il modello ma senza versione
    raccolti: list = []  # usato solo quando la ricerca è ambigua
    scaldate = False
    for posizione, voce in enumerate(ordinati):
        if time.monotonic() >= scadenza:
            break
        # I CATALOGHI FREDDI DELLE FONTI RIMANENTI PARTONO INSIEME, e solo
        # da qui in poi: dopo che la prima fonte — quella del brand dedotto,
        # cioè la più probabile — non ha risposto.
        #
        # Scaldarli già alla prima riga avrebbe fatto pagare a OGNI ricerca
        # il traffico di tutti i cataloghi, comprese quelle che rispondono
        # in mezzo secondo dalla prima fonte: misurato, «Galaxy S24 Ultra»
        # passava da 9 a 14 richieste di rete per un risultato che aveva
        # già. Su un host da 512 MB, dove il catalogo Xiaomi è lo storico
        # completo dal 2015, scaricarlo per rispondere a una domanda su un
        # Samsung è esattamente il genere di spreco che fa riavviare il
        # servizio per memoria.
        #
        # Chi arriva qui invece le fonti le interrogherà davvero tutte, e
        # allora tanto vale che le attese scorrano insieme. Vedi
        # `_scalda_fonti` per i numeri.
        if posizione and not scaldate:
            scaldate = True
            _scalda_fonti(ordinati[posizione:])
        tentate.append(voce.etichetta)
        for forma in forme:
            if time.monotonic() >= scadenza:
                break
            try:
                items = voce.funzione(forma)
            except Exception as exc:
                fallite.append(f"{voce.etichetta}: {exc}")
                break
            # LA MARCA VALE ANCHE SE LA SCRIVE L'ESPANSIONE, NON L'UTENTE.
            #
            # `expand_query` traduce «c63» nei nomi regionali con cui quel
            # telefono è pubblicato davvero, e uno di quelli è «realme C61»
            # — la marca c'è, scritta a chiare lettere, solo non l'ha
            # digitata l'utente. Il filtro guardava però la sola domanda
            # originale: essendo «c63» senza marca, non scartava niente, e
            # la forma «realme C61» finiva anche nel catalogo Xiaomi. Lì
            # `_normalize_name` toglie il prefisso della marca — è il suo
            # mestiere, «Samsung Galaxy S24» e «Galaxy S24» sono lo stesso
            # telefono — quindi «realme C61» diventa «c61» e combacia
            # ESATTAMENTE con «POCO C61/Redmi A3 India», che è un altro
            # telefono di un altro produttore.
            #
            # Misurato: cercando «c63» l'unico risultato era quel POCO.
            # Una forma che nomina un produttore è un vincolo tanto quanto
            # la domanda che lo nomina.
            marca_della_forma = (marca_dichiarata_dalla_query
                                 or extract.detect_brand(forma))
            items = _scarta_marca_sbagliata(items, marca_della_forma)
            # E dentro il gruppo, la sotto-marca: «OnePlus 12» non è un
            # realme anche se il progetto li tiene nello stesso cassetto.
            items = _scarta_sottomarca_sbagliata(items, forma)
            if not items:
                continue
            for item in items:
                if item.firmware_kind is None:
                    item.firmware_kind = voce.firmware_kind
            # SI SCEGLIE IL RISULTATO MIGLIORE, NON IL PRIMO.
            # Alcune fonti confermano che un modello esiste ma non ne
            # pubblicano la versione (l'elenco Oppo, per esempio).
            # Fermarsi al primo risultato significa accontentarsi di
            # «esiste» e non interrogare mai una fonte che avrebbe la
            # versione: è esattamente ciò che rendeva la ricerca inutile
            # per Oppo, pur essendo andata a buon fine.
            if (voce.firmware_kind in (C.FW_CURRENT, C.FW_REPORTED)
                    and _ha_versione(items[0])):
                if not ambigua:
                    return items, None
                raccolti.extend(items)
                break
            # Se un firmware corrente non c'è, una scheda di fabbrica più
            # ricca è comunque un'identità migliore del primo catalogo che
            # ha detto soltanto «esiste». Il chiamante conserva il suo
            # firmware_kind=FACTORY, quindi non la mostrerà come update.
            if ripiego is None or (
                    voce.firmware_kind == C.FW_FACTORY and _ha_versione(items[0])):
                ripiego = items
            break

    if raccolti:
        # Un dispositivo per nome: due fonti che descrivono lo stesso
        # telefono non devono comparire due volte, ma due telefoni diversi
        # sì — è tutto il punto.
        # La chiave NON passa da `_normalize_name`: quella toglie la marca,
        # e «OPPO A15» e «Galaxy A15» finivano sulla stessa chiave — cioè
        # esattamente i due telefoni che qui vanno tenuti distinti.
        visti, distinti = set(), []
        for voce in raccolti:
            chiave = " ".join((voce.device or "").lower().split())
            if chiave and chiave not in visti:
                visti.add(chiave)
                distinti.append(voce)
        return distinti, None

    # Nessuna fonte aveva la versione: si restituisce comunque quello che
    # si è trovato, ma il chiamante potrà dire che manca il firmware.
    if ripiego:
        return ripiego, None

    if fallite:
        return [], f"fonti ufficiali non raggiungibili — {'; '.join(fallite[:2])}"

    stato_fonte = _stato_fonte_per_brand(brand)
    if stato_fonte:
        return [], f"la fonte ufficiale di {brand} non sta rispondendo ({stato_fonte})"

    provate = ", ".join(tentate[:4]) or "nessuna"
    return [], f"nessuna fonte ufficiale conosce «{model_name}» (provate: {provate})"


def _ha_versione(item) -> bool:
    """True se questo risultato porta davvero un'informazione di firmware.

    Serve a distinguere «so che questo telefono esiste» da «so a che
    versione è»: sono due risposte molto diverse, e solo la seconda è
    quello che l'app deve cercare.
    """
    return bool(
        getattr(item, "android_version", None)
        or getattr(item, "version", None)
        or getattr(item, "build", None)
    )


def _lookup_order(brand: str | None) -> list:
    """Fonti da interrogare, dalla più probabile alla meno.

    Le fonti costose (una richiesta di rete per dispositivo: Samsung, Apple,
    Motorola) entrano nell'elenco SOLO se il brand corrisponde davvero.
    Interrogarle sempre significherebbe pagare decine di richieste per ogni
    ricerca, e far scadere il tempo prima di arrivare a quelle utili.
    """
    del_brand = [v for v in _STRUCTURED_LOOKUPS_LIST if v.brand == brand]
    economiche = [
        v for v in _STRUCTURED_LOOKUPS_LIST
        if v.costo == "basso" and v.brand != brand
    ]
    # GSMArena chiude la fila: copre qualunque modello, ma dà la versione
    # di fabbrica, quindi si preferiscono le fonti ufficiali quando ci sono.
    return del_brand + economiche + [_gsmarena_lookup()]


# Quale cache appartiene a quale `fetch`. Serve solo a NON dedicare un
# thread a una fonte già scaldata: `ottieni` la salterebbe comunque, quindi
# una fonte che non compare qui funziona lo stesso, paga solo un thread
# inutile. È una mappa e non un campo di `StructuredLookup` perché la
# stessa `fetch` è condivisa da più voci, e la cache è una sola.
_CACHE_PER_FETCH = {
    id(fetch_xiaomi): _xiaomi_cache,
    id(fetch_honor_aer): _honor_aer_cache,
    id(fetch_honor_security_bulletin): _honor_security_cache,
    id(fetch_vivo_aer): _vivo_aer_cache,
    id(fetch_oppo_aer): _oppo_aer_cache,
    id(fetch_pixel_ota): _pixel_ota_cache,
    id(fetch_realme_aer): _realme_pagina_cache,
}

# Quante fonti si scaldano insieme. Sono download indipendenti su host
# diversi, quindi il limite non è la banda ma il numero di thread che ha
# senso tenere su un host da 512 MB. Sei copre le fonti a basso costo
# esistenti senza lasciarne quasi mai fuori una.
_SCALDA_MAX_THREAD = 6
_scalda_pool: ThreadPoolExecutor | None = None
_scalda_lock = threading.Lock()
# I riscaldamenti ancora in volo. Servono a `attendi_riscaldamenti`, che è
# il modo per rendere questa parallelizzazione osservabile: un thread che
# scrive in cache DOPO che qualcuno l'ha azzerata è la definizione di
# fallimento a intermittenza.
_scalda_in_volo: set = set()


def _scalda_fonti(voci: list) -> None:
    """Avvia il download dei cataloghi ancora freddi, **senza aspettarli**.

    ## Il problema che risolve, misurato

    `lookup_model_structured` interroga le fonti in fila. Ogni fonte a
    basso costo scarica un catalogo intero la prima volta, e a cache fredde
    quei download si sommano: misurati l'11/08/2026 su una ricerca sola,
    archivio Oppo 3,5s + Xiaomi 2,2s + catalogo AER 1,3s + Pixel 1,1s +
    ARB 1,0s + vivo 1,0s. Sono **dieci secondi di attese indipendenti**
    messe in coda una dopo l'altra, dentro un budget di dodici — ed è il
    motivo per cui una ricerca a cache fredde scadeva prima di aver
    interrogato tutte le fonti, restituendo «nessuna fonte conosce questo
    modello» quando invece una l'avrebbe conosciuto.

    Su Render il caso freddo non è l'eccezione: l'archivio si azzera a ogni
    riavvio, quindi è la prima ricerca dopo ogni riavvio.

    ## Perché non si aspetta

    Aspettare che finiscano trasformerebbe ogni ricerca — anche quelle che
    oggi rispondono in mezzo secondo dalla prima fonte, come «HONOR 400» —
    nel costo della fonte più lenta. Qui invece i download partono e basta:
    il giro di ricerca prosegue identico, e quando arriva alla terza fonte
    trova il catalogo già scaricato da chi è partito prima. Chi risponde
    subito continua a rispondere subito, e i thread rimasti finiscono di
    scaldare la cache per la ricerca successiva.

    Non cambia MAI il risultato: scalda le stesse fonti che il giro
    interrogherebbe comunque, nello stesso ordine di preferenza. È solo il
    momento in cui si paga l'attesa a essere diverso.
    """
    global _scalda_pool
    da_scaldare = []
    for voce in voci:
        if voce.costo != "basso" or voce.fetch is None:
            continue
        # Una fonte già in cache non si tocca: `ottieni` la salterebbe
        # comunque, ma così non le si dedica nemmeno un thread.
        cache = _CACHE_PER_FETCH.get(id(voce.fetch))
        if cache is not None and cache.fresca():
            continue
        da_scaldare.append(voce.fetch)
    if not da_scaldare:
        return

    with _scalda_lock:
        if _scalda_pool is None:
            # `daemon` implicito: i thread di un ThreadPoolExecutor non
            # impediscono l'uscita del processo in Python 3.9+.
            _scalda_pool = ThreadPoolExecutor(
                max_workers=_SCALDA_MAX_THREAD,
                thread_name_prefix="scalda-fonte")
        pool = _scalda_pool

    def scalda(fetch):
        try:
            fetch()
        except Exception:
            # Un guasto qui non deve arrivare a chi cerca: la stessa fonte
            # verrà richiamata dal giro di ricerca, che l'errore lo sa
            # gestire e lo sa anche riferire in Diagnostica.
            pass
        finally:
            # Il pool resta vivo per i riscaldamenti successivi: una
            # connessione SQLite thread-local altrimenti rimarrebbe aperta
            # inutilmente per tutta la vita del processo (e trattiene sia
            # memoria sia il file del database dopo un cambio/deploy).
            storage.close_thread_connection()

    for fetch in da_scaldare:
        try:
            futuro = pool.submit(scalda, fetch)
        except RuntimeError:
            # Pool chiuso (spegnimento in corso): si prosegue in fila, che
            # è esattamente il comportamento di prima di questa funzione.
            return
        with _scalda_lock:
            _scalda_in_volo.add(futuro)
        futuro.add_done_callback(
            lambda f: _scalda_in_volo.discard(f))


def attendi_riscaldamenti(timeout: float = 30.0) -> None:
    """Aspetta che i riscaldamenti avviati finiscano.

    In produzione non serve a nessuno: i thread scaldano la cache per la
    ricerca dopo e chi ha cercato ha già la sua risposta. Serve a **rendere
    deterministico chi osserva la cache** — cioè i test, che l'azzerano e
    poi verificano che una fonte senza rete dichiari un guasto. Senza
    questa attesa un thread partito da un test precedente può scrivere in
    cache un valore fresco DOPO l'azzeramento, e il test successivo fallisce
    dicendo che una fonte risponde a rete spenta: vero, ma per colpa del
    test di prima.
    """
    with _scalda_lock:
        rimasti = list(_scalda_in_volo)
    for futuro in rimasti:
        try:
            futuro.result(timeout=timeout)
        except Exception:
            pass


def _stato_fonte_per_brand(brand: str | None) -> str | None:
    """Messaggio d'errore della fonte ufficiale di questo brand, se è in
    errore in questo momento. None se la fonte funziona."""
    if not brand:
        return None
    try:
        chiavi = {s.key for s in SOURCES if s.brand == brand and s.trust == C.TRUST_STRUCTURED}
        for riga in storage.get_source_status():
            if riga.get("source") in chiavi and not riga.get("ok"):
                return (riga.get("last_error") or "errore non specificato")[:120]
    except Exception:
        return None
    return None


def search_model_live(model_query: str):
    """Interroga Google News in questo momento per un modello preciso.

    A differenza delle fonti registrate in SOURCES (che girano ogni
    `SCAN_INTERVAL_MINUTES` su query generiche per brand), questa funzione
    cerca il nome esatto del modello scritto dall'utente, per rispondere
    subito a «qual è l'ultimo aggiornamento di questo telefono» anche se
    la scansione periodica non l'ha ancora intercettato.

    Nessun limite di tempo: Google News viene interrogato su tutta la sua
    cronologia, non solo sugli ultimi giorni. Le query sono volutamente
    BREVI e SEMPLICI (frase + una parola, niente virgolette/OR/intitle:
    combinati insieme): il parser di ricerca di Google News RSS non è
    documentato ed è noto restituire silenziosamente zero risultati con
    query troppo articolate, anche quando esistono notizie reali
    sull'argomento — è la causa più comune di "zero risultati", non che la
    notizia sia troppo vecchia o che manchi davvero.

    Prima di tutto questo, se il testo scritto è un codice modello tecnico
    noto (es. "RMX3939") invece di un nome commerciale, viene risolto al
    nome vero (es. "realme C63") tramite il database KHwang9883/MobileModels
    e SI CERCA QUELLO: un codice tecnico non compare quasi mai in un titolo
    di notizia, mentre il nome commerciale sì. Se il codice corrisponde a
    più varianti regionali, si provano tutte finché una trova qualcosa.

    Punto chiave sul risultato: il modello mostrato viene fissato al testo
    scritto dall'utente (o al nome commerciale risolto), non dedotto dal
    titolo della notizia. Così un modello di nicchia o vecchio di qualche
    anno, che nessun pattern regex conosce esplicitamente, diventa comunque
    un dispositivo tracciabile invece di sparire perché "non riconosciuto".
    """
    model_query = (model_query or "").strip()
    if not model_query:
        return [], "Scrivi il nome di un modello o un codice modello."

    # Il brand serve ad attribuire correttamente le notizie trovate: va
    # dedotto con tutti i mezzi disponibili, non solo dal testo. Un codice
    # tecnico non contiene il nome della marca, ma il suo formato sì.
    brand = (
        extract.detect_brand(model_query)
        or brand_from_code(model_query)
        or brand_from_known_device(model_query)
        or C.OTHER
    )

    resolved_names: list[str] = []
    resolved_code = None
    # SI CHIEDE AL DATASET PRIMA DI GIUDICARE DALLA FORMA.
    #
    # `_code_candidates` riconosce i codici da come SONO FATTI (`SM-…`,
    # `CPH…`, `RMX…`, `XT####`). Fuori da quelle famiglie non vede niente —
    # e fuori ci sono `PCET00` di Oppo, `CLT-L04` di Huawei, `V2283A` di
    # vivo, `XT920` di Motorola, `MKDA` di Nokia: tutti codici che il
    # dataset risolve al nome commerciale senza esitare.
    #
    # La conseguenza non era una ricerca a vuoto — era peggio: il codice
    # diventava il NOME del dispositivo, e nasceva una scheda «Pcet00»
    # separata da quella di «OPPO A9x», che è lo stesso telefono. Su un
    # campione casuale di 32 modelli questa era la causa singola più
    # frequente di divergenza fra ricerca per nome e ricerca per codice.
    #
    # Il filtro per forma resta DOPO, per i codici scritti dentro una frase
    # più lunga, dove chiedere al dataset l'intera frase non servirebbe.
    for candidate in [model_query] + list(_code_candidates(model_query)):
        names = modelcodes.resolve(candidate)
        if names:
            resolved_names, resolved_code = names, candidate
            break

    # Dal più preciso al più permissivo: ogni nome risolto prima della query
    # grezza, ci si ferma al primo che trova qualcosa.
    #
    # TETTO DI TEMPO: ogni tentativo è una richiesta di rete, e i nomi
    # risolti da un codice possono essere parecchi (RMX3939 ne risolve
    # quattro). Senza limite il caso peggiore è nomi × formulazioni ×
    # timeout, cioè diversi minuti: la pagina resta in caricamento e sembra
    # bloccata. Si prova finché c'è tempo, poi si risponde con quello che
    # si ha, dicendolo esplicitamente.
    search_texts = (resolved_names + [model_query])[:C.SEARCH_MAX_CANDIDATES]
    scadenza = time.monotonic() + C.SEARCH_BUDGET_SECONDS
    tempo_scaduto = False

    last_error = "nessun risultato"
    for text in search_texts:
        if time.monotonic() >= scadenza:
            tempo_scaduto = True
            break
        # Un nome risolto dal database codici (es. "HONOR X8c") è già
        # scritto correttamente dalla fonte: passarlo per l'euristica di
        # normalizzazione maiuscole rischia di rovinarlo (es. "X8c" diventa
        # "X8C", sbagliato — Honor scrive quel suffisso minuscolo). La
        # normalizzazione resta utile solo sul testo grezzo digitato a
        # mano dall'utente, quando non è avvenuta nessuna risoluzione.
        # IL NOME DEL MODELLO NON DEVE CONTENERE DECORAZIONI.
        # Prima qui si scriveva «Oppo A6x (CPH2819)», con il codice fra
        # parentesi. Sembra utile, ma quel nome diventa un dispositivo
        # DIVERSO da «OPPO A6x» delle fonti ufficiali: lo stesso telefono
        # si spezza in due voci, e soprattutto quel nome decorato finisce
        # poi usato come termine di ricerca nel catalogo, dove non
        # corrisponde a nulla. È così che una ricerca andata a buon fine
        # finiva per non mostrare alcun dispositivo.
        # Il codice resta visibile, ma nella descrizione, non nel nome.
        display_model = text if text in resolved_names else extract.canonical_device(text)
        # UN CODICE CHE NESSUN DATASET CONOSCE NON È UN NOME DI DISPOSITIVO.
        # Fissare il modello al testo digitato è ciò che rende tracciabile
        # un telefono di nicchia chiamato per nome — ma applicato a un
        # codice non risolto crea un dispositivo che si chiama «Xt2341-3»,
        # separato dal «Moto G14» che è lo stesso telefono. Meglio nessun
        # modello: le notizie restano, il dispositivo fantasma no.
        if looks_like_model_code(text) and text not in resolved_names:
            display_model = None
        nota_codice = f" · codice {resolved_code}" if (resolved_code and text in resolved_names) else ""
        for attempt_query in _news_attempts(text):
            if time.monotonic() >= scadenza:
                tempo_scaduto = True
                break
            items, error = rss_items(
                [_google_news(attempt_query)], brand, "Ricerca live",
                limit=25, timeout=C.SEARCH_HTTP_TIMEOUT,
            )
            if items:
                for item in items:
                    if display_model:
                        item.device = display_model
                    if nota_codice:
                        item.size_info = (item.size_info or "") + nota_codice
                return items, None
            if error:
                last_error = error
        if tempo_scaduto:
            break

    if tempo_scaduto:
        return [], (
            f"ricerca interrotta dopo {C.SEARCH_BUDGET_SECONDS}s senza risultati per "
            f"«{model_query}»: le fonti di notizie stanno rispondendo lentamente. "
            "Riprova fra poco — se il modello ha già dati in archivio li vedi comunque qui sotto."
        )

    hint = f" (risolto come codice modello: {', '.join(resolved_names)})" if resolved_names else ""
    codes_status = f" [database codici modello: {modelcodes.status()}]"
    return [], (
        f"nessuna notizia trovata per «{model_query}»{hint} in nessuna forma di "
        f"ricerca provata ({last_error}){codes_status}"
    )


def diagnose_query(query: str) -> dict:
    """Racconta passo per passo cosa succede cercando questo testo.

    Serve a rispondere alla domanda «perché non trova nulla» senza dover
    indovinare: mostra se il testo è stato riconosciuto come codice, in
    quali nomi è stato risolto, quali fonti sono state interrogate e cosa
    hanno risposto ciascuna. Finora ogni ipotesi sbagliata è costata un
    giro di correzioni a vuoto; questo la sostituisce con un fatto.
    """
    query = (query or "").strip()
    passi = {
        "query": query,
        "ha_forma_di_codice": looks_like_model_code(query),
        "candidati_codice": _code_candidates(query),
        "nomi_risolti": [],
        "brand_dedotto": None,
        "forme_provate": [],
        "fonti": [],
        "esito": None,
    }
    if not query:
        passi["esito"] = "nessun testo"
        return passi

    for codice in passi["candidati_codice"]:
        nomi = modelcodes.resolve(codice)
        if nomi:
            passi["nomi_risolti"].append({"codice": codice, "nomi": nomi})

    passi["brand_dedotto"] = (
        extract.detect_brand(query)
        or brand_from_code(query)
        or brand_from_known_device(query)
    )
    passi["forme_provate"] = expand_query(query)

    for voce in _lookup_order(passi["brand_dedotto"]):
        esito_fonte = {"fonte": voce.etichetta, "brand": voce.brand,
                       "trovati": 0, "errore": None}
        for forma in passi["forme_provate"]:
            try:
                trovati = voce.funzione(forma)
            except Exception as exc:
                esito_fonte["errore"] = str(exc)[:160]
                break
            if trovati:
                esito_fonte["trovati"] = len(trovati)
                esito_fonte["dispositivo"] = trovati[0].device
                esito_fonte["forma_vincente"] = forma
                break
        # Nessun risultato: si distingue «la fonte non conosce il modello»
        # da «la fonte non risponde», che richiedono azioni diverse.
        if not esito_fonte["trovati"] and not esito_fonte["errore"] and voce.fetch:
            try:
                _, errore_fonte = voce.fetch()
            except Exception as exc:
                errore_fonte = str(exc)[:160]
            if errore_fonte:
                esito_fonte["errore"] = errore_fonte[:160]
        passi["fonti"].append(esito_fonte)

    trovato = next((f for f in passi["fonti"] if f["trovati"]), None)
    if trovato:
        passi["esito"] = f"trovato da «{trovato['fonte']}» come «{trovato.get('dispositivo')}»"
    else:
        passi["esito"] = "nessuna fonte ufficiale ha riconosciuto questo modello"
    return passi


# ======================================================================
# GSMArena — versione di fabbrica per QUALSIASI modello
# ======================================================================
# È la risposta al problema di copertura, non l'ennesima fonte per un
# brand: GSMArena ha una scheda per ogni telefono mai prodotto, e ciascuna
# riporta la riga «OS: Android 15, ColorOS 15». Vale quindi per marche che
# non hanno alcuna fonte ufficiale interrogabile (Oppo, vivo, OnePlus,
# brand di nicchia) e anche per quelle future, senza aggiungere codice.
#
# Punto importante: la scheda contiene anche la riga «Models: CPH2819»,
# cioè il codice modello. La corrispondenza può quindi essere VERIFICATA
# sul codice invece che dedotta dal nome — molto più solido, ed è ciò che
# evita di attribuire a un telefono la versione di un altro.
#
# LIMITE DICHIARATO: è la versione **di fabbrica**, non quella installata
# oggi dopo gli aggiornamenti. L'app deve dirlo, non lasciarlo intendere.
GSMARENA_SEARCH_URL = "https://www.gsmarena.com/results.php3?sQuickSearch=yes&sName={query}"
GSMARENA_BASE = "https://www.gsmarena.com/"

_GSM_RESULT_RE = re.compile(r'href="([a-z0-9_()\-]+-\d+\.php)"', re.IGNORECASE)
_GSM_OS_RE = re.compile(r"\bOS\b\s*\n+\s*(Android[^\n]{0,70})", re.IGNORECASE)
_GSM_MODELS_RE = re.compile(r"^Models\s*\n+\s*([^\n]{1,120})", re.IGNORECASE | re.MULTILINE)
_GSM_NAME_RE = re.compile(r"^(.{2,60}?)\s*-\s*Full phone specifications", re.MULTILINE)
_GSM_RELEASED_RE = re.compile(r"Released\s+(\d{4},?\s+\w+\s+\d{1,2})", re.IGNORECASE)


def _gsmarena_html(url: str) -> str | None:
    """L'HTML COM'È. Serve a chi cerca i link delle schede, che i tag li
    vuole: `_gsmarena_page` qui sotto li toglie."""
    try:
        response = http_get(url, timeout=C.SEARCH_HTTP_TIMEOUT + 4)
    except Exception:
        return None
    if response.status_code != 200:
        return None
    return response.text


def _gsmarena_page(url: str) -> str | None:
    grezzo = _gsmarena_html(url)
    if grezzo is None:
        return None
    testo = re.sub(r"<[^>]+>", "\n", grezzo)
    return re.sub(r"[ \t]+", " ", testo)


def _gsmarena_specs(pagina: str) -> dict:
    """Estrae dalla scheda le informazioni che interessano."""
    os_match = _GSM_OS_RE.search(pagina)
    modelli_match = _GSM_MODELS_RE.search(pagina)
    nome_match = _GSM_NAME_RE.search(pagina)
    data_match = _GSM_RELEASED_RE.search(pagina)
    codici = []
    if modelli_match:
        codici = [
            c.strip().upper()
            for c in re.split(r"[,;/]", modelli_match.group(1))
            if 4 <= len(c.strip()) <= 20
        ]
    return {
        "os": os_match.group(1).strip() if os_match else None,
        "codici": codici,
        "nome": nome_match.group(1).strip() if nome_match else None,
        "uscita": data_match.group(1) if data_match else None,
    }


def _lookup_gsmarena(model_name: str) -> list[RawItem]:
    """Versione di fabbrica per un modello qualsiasi, da GSMArena.

    Due richieste: la ricerca e poi la scheda. Quando il testo cercato è un
    codice, la corrispondenza viene verificata sulla riga «Models» della
    scheda: è una prova, non una somiglianza di nomi.
    """
    from urllib.parse import quote

    query = (model_name or "").strip()
    if len(query) < 3:
        return []

    # UNA SOLA RICHIESTA PER LA PAGINA DEI RISULTATI, non due.
    #
    # Qui c'erano due `http_get` sullo STESSO identico URL, una dietro
    # l'altra: la prima passava da `_gsmarena_page`, che toglie i tag — e
    # quindi butta via proprio i link alle schede — e serviva solo come
    # guardia «la ricerca ha risposto qualcosa»; la seconda riscaricava la
    # stessa pagina per leggerne l'HTML vero.
    #
    # Il doppione si pagava per OGNI forma equivalente della ricerca:
    # misurato l'11/08/2026, per «c63» (cinque forme) erano dieci richieste
    # e 3,5 secondi, su una fonte che sta in fondo alla fila e che nella
    # maggior parte dei casi non risponderà. L'HTML grezzo basta a fare
    # tutte e due le cose.
    grezzo = _gsmarena_html(GSMARENA_SEARCH_URL.format(query=quote(query)))
    if not grezzo:
        return []

    percorsi = list(dict.fromkeys(_GSM_RESULT_RE.findall(grezzo)))[:3]
    if not percorsi:
        return []

    codice_cercato = re.sub(r"\s+", "", query).upper() if looks_like_model_code(query) else None
    bersaglio = modelcodes._normalize_name(query)

    for percorso in percorsi:
        pagina = _gsmarena_page(GSMARENA_BASE + percorso)
        if not pagina:
            continue
        dati = _gsmarena_specs(pagina)
        if not dati["os"]:
            continue

        # Verifica: se cerchiamo un codice, deve comparire fra i modelli.
        if codice_cercato:
            if codice_cercato not in dati["codici"]:
                continue
        elif dati["nome"] and bersaglio not in modelcodes._normalize_name(dati["nome"]):
            continue

        nome = dati["nome"] or query
        etichetta_codici = f" · codice {', '.join(dati['codici'][:3])}" if dati["codici"] else ""
        return [RawItem(
            title=(
                f"{nome} — uscito con {dati['os']}"
                + (f" (rilascio {dati['uscita']})" if dati["uscita"] else "")
            ),
            link=GSMARENA_BASE + percorso,
            published=iso(dati["uscita"]) if dati["uscita"] else None,
            brand=extract.detect_brand(nome) or C.OTHER,
            device=nome,
            version=dati["os"],
            size_info=(
                "Scheda tecnica GSMArena — versione DI FABBRICA, "
                "non quella installata oggi" + etichetta_codici
            ),
        )]
    return []
