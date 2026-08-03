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

import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from . import aer_catalog
from . import config as C
from . import extract
from . import modelcodes
from . import oppo_official
from . import storage
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
    version: str | None = None         # versione/etichetta fornita dalla fonte
    build: str | None = None
    android_version: int | None = None
    size_gb: float = 0.0
    size_info: str = ""
    summary: str = ""

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


# ======================================================================
# Helper HTTP
# ======================================================================
def _headers() -> dict:
    return {"User-Agent": C.USER_AGENT, "Accept": "*/*"}


def http_get(url: str, timeout: int | None = None):
    if requests is None:  # pragma: no cover
        raise RuntimeError("la libreria 'requests' non è installata")
    return requests.get(url, timeout=timeout or C.HTTP_TIMEOUT, headers=_headers())


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


def fetch_xiaomi() -> tuple[list[RawItem], str | None]:
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


def fetch_pixel_ota() -> tuple[list[RawItem], str | None]:
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


def fetch_honor_aer() -> tuple[list[RawItem], str | None]:
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


def fetch_vivo_aer() -> tuple[list[RawItem], str | None]:
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
    if device.get("model_codes"):
        dettagli.append("/".join(device["model_codes"][:3]))

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
    return [i for i in tutti if bersaglio in modelcodes._normalize_name(i.device or "")][:3]


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


def fetch_oppo_aer() -> tuple[list[RawItem], str | None]:
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
    return [i for i in tutti if bersaglio in modelcodes._normalize_name(i.device or "")][:3]


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


def _realme_page() -> tuple[str | None, str | None]:
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


def _lookup_realme(model_name: str) -> list[RawItem]:
    """Ricerca a comando su realme, accettando il nome commerciale, uno dei
    nomi regionali alternativi, o il codice ufficiale.

    realme riusa uno stesso codice per più modelli regionali e li elenca
    come un unico nome composto separato da «/», mentre la tabella con le
    versioni ne riporta solo uno. Vanno quindi provati tutti i nomi del
    gruppo, altrimenti un modello legittimo non trova la propria riga.
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

    tutti, error = fetch_realme_aer()
    if error or not tutti:
        return []

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
]

# CSC (region code) da provare in ordine: ITV = Italia, poi Europa generica.
# Non tutti i modelli pubblicano un firmware per ogni CSC, da qui il fallback.
SAMSUNG_CSC_CANDIDATES = ["ITV", "DBT", "EUX", "XEO"]

_SAMSUNG_VERSION_XML_RE = re.compile(
    r'<latest(?:\s+o=["\'](\d+)["\'])?[^>]*>([^<]+)</latest>', re.IGNORECASE
)


def _samsung_fus_latest(model: str) -> tuple[str | None, str | None, str | None]:
    """Ritorna (build_pda, android_version, csc_usato) per un modello, provando
    le region candidate in ordine finché una risponde con un dato valido."""
    for csc in SAMSUNG_CSC_CANDIDATES:
        url = f"https://fota-cloud-dn.ospserver.net/firmware/{csc}/{model}/version.xml"
        try:
            response = http_get(url)
        except Exception:
            continue
        if response.status_code != 200:
            continue
        match = _SAMSUNG_VERSION_XML_RE.search(response.text)
        if not match:
            continue
        android_version, versions = match.groups()
        pda = versions.split("/")[0].strip()
        if not pda:
            continue
        return pda, android_version, csc
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
    (2023, "cancunf", "G54"),
    (2023, "devonf", "G73"),
    (2023, "devonn", "G Power (2023)"),
    (2023, "fogos", "G34"),
    (2023, "genevn", "G Stylus 5G (2023)"),
    (2023, "gnevan", "G Stylus (2023)"),
    (2023, "lynkco", "Razr 40"),
    (2023, "lyriq", "Edge 40"),
    (2023, "manaus", "Edge 40 Neo"),
    (2023, "penang", "G53"),
    (2023, "penangf", "G13"),
    (2023, "pnangn", "G 5G (2023)"),
    (2023, "rtwo", "Edge 40 Pro"),
    (2023, "sabahl", "E13"),
    (2023, "zeekr", "Razr 40 Ultra"),
    (2024, "ctwo", "X50 Ultra"),
    (2024, "vienna", "S50"),
    (2024, "malmo", "S50 Neo"),
    (2024, "fogorow", "G24"),
    (2024, "aito", "Razr 50"),
    (2024, "arcfox", "Razr 50 Ultra"),
    (2024, "taipei", "G55"),
    (2024, "paros", "G75"),
    (2024, "scout", "Edge 60"),
    (2024, "cybert", "Edge 60 Pro"),
    (2025, "leap", "Razr 60 Ultra"),
]

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


def _lolinet_latest(codename: str, year: int):
    """Ultimo file firmware per un codename, provando le region una a una.
    Ritorna (nome_file, url_completo, data_iso) oppure None se non trovato."""
    base = f"https://mirrors.lolinet.com/firmware/lenomola/{year}/{codename}/official"
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
        filename, date_str = max(matches, key=lambda m: m[1])
        filename = filename.rsplit("/", 1)[-1]
        return filename, folder_url + filename, date_str
    return None


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
            name_match = _LOLINET_NAME_RE.search(filename)
            android_version = int(name_match.group(2)) if name_match else None
            build = name_match.group(3) if name_match else None
            items.append(
                RawItem(
                    title=f"Motorola {model} — build {build or filename}",
                    link=file_url,
                    published=iso(date_str.replace(" ", "T", 1)),
                    brand=C.VIVO,
                    device=f"Motorola {model}",
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
_MODEL_CODE_SHAPES = [
    re.compile(r"^SM-[A-Z]\d{3}[A-Z]{0,3}$", re.I),          # Samsung
    re.compile(r"^[A-Z]{3}-[A-Z]{2}\w{1,4}$", re.I),          # Huawei/Honor
    re.compile(r"^(?:iPhone|iPad|iPod)\d+,\d+$", re.I),       # Apple
    # RMX3939, CPH2625, XT2347 — con eventuale suffisso di variante (XT2323-1)
    re.compile(r"^[A-Z]{2,5}[-_]?\d{4,5}[A-Z0-9]{0,4}(?:-\d{1,2})?$", re.I),
    re.compile(r"^\d{4,5}[A-Z]{2,4}\d{2,3}[A-Z]{0,2}$", re.I),   # Xiaomi 2312DRA50C
    # Xiaomi vecchio stile: solo cifre più il suffisso di regione (22101316UG)
    re.compile(r"^\d{7,9}[A-Z]{1,3}$", re.I),
]


def looks_like_model_code(text: str) -> bool:
    """True solo se il testo ha la forma di un codice modello vero."""
    compatto = re.sub(r"\s+", "", (text or "")).strip()
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
    variants = []
    for v in (stripped, no_spaces):
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
    if _SAMSUNG_CODE_RE.match(re.sub(r"\s+", "", model_name)):
        codes = [re.sub(r"\s+", "", model_name).upper()]
    else:
        codes = [c for c in modelcodes.codes_for_name(model_name) if _SAMSUNG_CODE_RE.match(c)]
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
                title=f"{_nome_ufficiale(code, model_name)} ({code}) — build {pda} ({csc})",
                link=f"https://fota-cloud-dn.ospserver.net/firmware/{csc}/{code}/version.xml",
                brand=C.SAMSUNG,
                device=_nome_ufficiale(code, model_name),
                build=pda,
                android_version=int(android_version) if android_version else None,
                size_info="Controllo versione ufficiale (endpoint FOTA)",
            )
        )
        break
    return items


def _lookup_xiaomi(model_name: str) -> list[RawItem]:
    """Cerca il modello nel catalogo Xiaomi completo (già scaricato e in
    cache): copre qualunque device del tracker, non solo i più recenti."""
    all_items, error = fetch_xiaomi()
    if error or not all_items:
        return []
    needle = modelcodes._normalize_name(model_name)
    if not needle:
        return []
    return [
        item for item in all_items
        if needle and needle in modelcodes._normalize_name(item.device or item.title)
    ][:3]


def _lookup_honor(model_name: str) -> list[RawItem]:
    all_items, error = fetch_honor_aer()
    if error or not all_items:
        return []
    needle = modelcodes._normalize_name(model_name)
    if not needle:
        return []
    return [
        item for item in all_items
        if needle in modelcodes._normalize_name(item.device or "")
    ][:3]


def _lookup_motorola(model_name: str) -> list[RawItem]:
    """Cerca fra i modelli Motorola coperti dal mirror. Qui la copertura
    resta quella della tabella manuale (il mirror è organizzato per nome in
    codice interno, non per nome commerciale)."""
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


_STRUCTURED_LOOKUPS_LIST = [
    StructuredLookup(C.SAMSUNG, _lookup_samsung, "alto", "controllo versione Samsung"),
    StructuredLookup(C.APPLE, _lookup_apple, "alto", "firmware Apple per dispositivo"),
    StructuredLookup(C.VIVO, _lookup_motorola, "alto", "mirror firmware Motorola"),
    StructuredLookup(C.PIXEL, _lookup_pixel, "basso", "immagini OTA ufficiali Pixel",
                     fetch_pixel_ota),
    StructuredLookup(C.VIVO, _lookup_vivo, "basso", "piano ufficiale vivo", fetch_vivo_aer),
    StructuredLookup(C.XIAOMI, _lookup_xiaomi, "basso", "catalogo Xiaomi", fetch_xiaomi),
    StructuredLookup(C.HUAWEI, _lookup_honor, "basso", "piano ufficiale Honor", fetch_honor_aer),
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
    StructuredLookup(C.OPPO, _lookup_realme, "basso", "piano ufficiale realme", fetch_realme_aer),
    StructuredLookup(C.OPPO, _lookup_oppo, "basso", "elenco ufficiale Oppo", fetch_oppo_aer),
    # In fondo alle economiche, appena prima di GSMArena: le pagine
    # ufficiali di marca hanno la versione di fabbrica e vanno provate
    # prima. Questa risponde per QUALSIASI marca — comprese quelle senza
    # fonte dedicata, OnePlus in testa — e riconosce anche i codici
    # tecnici, che è il motivo più frequente di ricerca a vuoto.
    StructuredLookup(None, _lookup_aer_catalog, "basso",
                     "catalogo Android Enterprise Recommended", fetch_aer_catalog),
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


def brand_from_code(query: str) -> str | None:
    """Brand dedotto dal formato di un codice modello, o None."""
    testo = re.sub(r"\s+", "", (query or "")).upper()
    for pattern, brand in _CODE_BRAND_PATTERNS:
        if pattern.match(testo):
            return brand
    return None


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

    # Codice tecnico → nomi commerciali (RMX3939 → realme C63/…)
    for codice in _code_candidates(query):
        candidati.extend(modelcodes.resolve(codice))

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

    ordinati = _lookup_order(brand)
    if not ordinati:
        return [], "nessuna fonte ufficiale disponibile"

    # Ogni fonte riceve TUTTE le forme equivalenti della ricerca, non solo
    # il testo digitato: è ciò che rende uniforme il comportamento fra
    # marche diverse (vedi expand_query).
    forme = expand_query(model_name) or [model_name]

    scadenza = time.monotonic() + C.SEARCH_BUDGET_SECONDS
    tentate, fallite = [], []
    ripiego = None      # risultato che conferma il modello ma senza versione
    for voce in ordinati:
        if time.monotonic() >= scadenza:
            break
        tentate.append(voce.etichetta)
        for forma in forme:
            if time.monotonic() >= scadenza:
                break
            try:
                items = voce.funzione(forma)
            except Exception as exc:
                fallite.append(f"{voce.etichetta}: {exc}")
                break
            if not items:
                continue
            # SI SCEGLIE IL RISULTATO MIGLIORE, NON IL PRIMO.
            # Alcune fonti confermano che un modello esiste ma non ne
            # pubblicano la versione (l'elenco Oppo, per esempio).
            # Fermarsi al primo risultato significa accontentarsi di
            # «esiste» e non interrogare mai una fonte che avrebbe la
            # versione: è esattamente ciò che rendeva la ricerca inutile
            # per Oppo, pur essendo andata a buon fine.
            if _ha_versione(items[0]):
                return items, None
            if ripiego is None:
                ripiego = items
            break

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
    for candidate in _code_candidates(model_query):
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


def _gsmarena_page(url: str) -> str | None:
    try:
        response = http_get(url, timeout=C.SEARCH_HTTP_TIMEOUT + 4)
    except Exception:
        return None
    if response.status_code != 200:
        return None
    testo = re.sub(r"<[^>]+>", "\n", response.text)
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

    elenco = _gsmarena_page(GSMARENA_SEARCH_URL.format(query=quote(query)))
    if not elenco:
        return []

    # La pagina dei risultati è HTML: i link alle schede vanno cercati lì.
    try:
        risposta = http_get(GSMARENA_SEARCH_URL.format(query=quote(query)),
                            timeout=C.SEARCH_HTTP_TIMEOUT + 4)
        grezzo = risposta.text if risposta.status_code == 200 else ""
    except Exception:
        grezzo = ""
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
