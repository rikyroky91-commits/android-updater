"""Android Enterprise Recommended — catalogo ufficiale, in JSON.

PERCHÉ ESISTE QUESTO MODULO. Oggi il progetto legge le pagine AER con
espressioni regolari, una per marca (Honor, realme, vivo, Oppo). Sono
quattro parser diversi sullo stesso dato, costruiti su HTML che nessuno
garantisce, e uno di loro (vivo) non è mai stato verificato sul sito vero.
È il tipo di codice che si rompe in silenzio.

La stessa pagina si serve da un'API JSON:

    GET https://androidenterprisepartners.withgoogle.com/_ah/spi/search/v1/devices
        ?is_archived=false&size=1000

Una richiesta, **706 dispositivi di 40+ marche**, campi tipizzati. Nessuna
chiave, nessuna firma, nessuno User-Agent particolare. Sostituisce quattro
scraper con un parser solo, e in più copre marche che oggi non hanno
nessuna fonte strutturata.

## COSA DÀ DAVVERO (e cosa no)

Dà, per ogni dispositivo:

* `models` — **i codici tecnici** (`CPH2791`, `RMX5057`, `SM-S938B`): è la
  cosa più preziosa, perché permette di *verificare* la corrispondenza
  codice ↔ nome invece di dedurla, che è esattamente il pregio per cui il
  documento di passaggio consegne teneva GSMArena;
* `smrDate` — **fino a quando il modello riceve patch di sicurezza**, e
  `smrUpdateFrequency` (mensile / trimestrale). Per un QA è un dato
  operativo che oggi non è da nessuna parte: dice se un device di test è
  ancora vivo o è fuori supporto;
* `osVersionSupported` — la versione Android **di lancio**;
* `imageUrls` — la foto ufficiale del modello.

NON dà la versione attuale. **Il campo `hardwareFeatures.os` sembra
prometterla e non la mantiene**: il Galaxy S21 FE vi risulta «Android 16»,
che non ha mai ricevuto, e 402 dispositivi su 706 riportano lo stesso
identico valore. È un campo dichiarativo compilato dal produttore, non una
rilevazione. Leggerlo come «versione attuale» sarebbe la ripetizione esatta
dell'errore già costato giorni con la «Future version» di HONOR — con
l'aggravante che qui sembra plausibile. `verifica_versione_attuale()` più
sotto esiste apposta per impedirlo, e c'è un test che lo blocca.

Quindi: questa è una fonte di **catalogo e finestra di supporto**, non di
versione. Le due cose vanno tenute separate, e dette in modo diverso
all'utente.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request

from . import config as C

ENDPOINT = (
    "https://androidenterprisepartners.withgoogle.com"
    "/_ah/spi/search/v1/devices?is_archived=false&size=1000"
)

SOURCE_KEY = "aer_catalog"
SOURCE_LABEL = "Android Enterprise Recommended (catalogo ufficiale)"

# Il catalogo cambia quando esce un modello nuovo: qualche volta al mese.
# Riscaricarlo a ogni scansione oraria sarebbe traffico sprecato.
TTL_SECONDS = 12 * 3600

# Marche AER → brand del tracker. Le marche non elencate restano C.OTHER,
# che è il comportamento giusto: il catalogo comprende anche produttori
# industriali (Zebra, Point Mobile, Bluebird) che l'app non traccia ma che
# non c'è motivo di scartare.
_BRAND_MAP = {
    "samsung": C.SAMSUNG,
    "google": C.PIXEL,
    "xiaomi": C.XIAOMI, "redmi": C.XIAOMI, "poco": C.XIAOMI,
    "honor": C.HUAWEI, "huawei": C.HUAWEI,
    "oppo": C.OPPO, "oneplus": C.OPPO, "realme": C.OPPO,
    "vivo": C.VIVO, "iqoo": C.VIVO, "motorola": C.VIVO,
}

_lock = threading.Lock()
_dispositivi: list[dict] | None = None
_per_nome: dict[str, dict] = {}
_per_codice: dict[str, dict] = {}
# `None` = mai scaricato. NON `0.0`: il valore è un istante di
# `time.monotonic()`, il cui zero è arbitrario (il boot della macchina, non
# un'epoca). Su un container appena avviato `monotonic()` vale una manciata
# di secondi, quindi `0.0` non significa «scaduto da sempre» ma «scaricato
# 94 secondi fa» — e la cache risultava fresca quando era vuota. L'errore
# era mascherato dal fatto che `_dispositivi is not None` faceva da guardia
# di fatto; si è visto solo quando un test ha provato a forzare la scadenza.
_scaricato_a: float | None = None
_status = "non ancora caricato"


def status() -> str:
    return _status


def reset_cache() -> None:
    global _dispositivi, _per_nome, _per_codice, _scaricato_a, _status
    with _lock:
        _dispositivi = None
        _per_nome = {}
        _per_codice = {}
        _scaricato_a = None
        _status = "non ancora caricato"


# ----------------------------------------------------------------------
# Normalizzazione
# ----------------------------------------------------------------------
_PARENTESI = re.compile(r"\([^)]*\)")
_MARCHE_IN_TESTA = re.compile(
    r"^\s*(?:oppo|oneplus|realme|samsung|google|xiaomi|redmi|poco|honor|huawei|"
    r"vivo|iqoo|motorola|moto|nothing|sony|asus|tcl|lenovo|sharp)\s+",
    re.IGNORECASE,
)


def normalize(nome: str) -> str:
    """Chiave di confronto CON la marca: niente punteggiatura, niente
    spazi. «OPPO Find X9 Pro» e «oppo findx9pro» collassano sulla stessa
    chiave."""
    testo = _PARENTESI.sub(" ", str(nome or ""))
    return re.sub(r"[^a-z0-9]+", "", testo.lower())


def normalize_short(nome: str) -> str:
    """Come sopra, ma SENZA la marca in testa: serve a far trovare
    «find x9 pro» a chi non scrive «OPPO».

    Questa forma è ambigua per costruzione — «OnePlus 12» e «Redmi 12» si
    riducono entrambi a `12` — e per questo l'indice che la usa scarta le
    chiavi contese invece di assegnarle al primo arrivato. Un abbinamento
    sbagliato è peggio di un modello non trovato: il secondo si vede, il
    primo produce un dato falso che sembra buono.
    """
    return normalize(_MARCHE_IN_TESTA.sub(" ", str(nome or "")))


def _codici(voce: dict) -> list[str]:
    """`"CPH2791, PLG110"` → `['CPH2791', 'PLG110']`.

    Il campo arriva come stringa separata da virgole, non come lista.
    """
    grezzo = voce.get("models")
    if isinstance(grezzo, list):
        pezzi = grezzo
    else:
        pezzi = str(grezzo or "").split(",")
    return [p.strip().upper() for p in pezzi if p and p.strip()]


def _nomi_alternativi(display_name: str) -> list[str]:
    """Una voce AER può descrivere più prodotti insieme:
    «OPPO Reno13 F 5G / Reno13 FS 5G», «OPPO A6 Pro 5G/F31».
    Vanno indicizzati tutti, altrimenti chi cerca il secondo nome non
    trova nulla pur essendo nel catalogo.
    """
    testa = _MARCHE_IN_TESTA.match(display_name or "")
    marca = testa.group(0).strip() if testa else ""
    pezzi = [p.strip() for p in re.split(r"\s*/\s*", str(display_name or "")) if p.strip()]
    nomi = []
    for indice, pezzo in enumerate(pezzi):
        nomi.append(pezzo)
        # Dal secondo in poi la marca non è ripetuta: «Reno13 FS 5G» va
        # indicizzato anche come «OPPO Reno13 FS 5G».
        if indice and marca and not _MARCHE_IN_TESTA.match(pezzo):
            nomi.append(f"{marca} {pezzo}")
    return nomi


# ----------------------------------------------------------------------
# Lettura di una voce
# ----------------------------------------------------------------------
_VUOTI = {"", "datanotprovided", "none", "null", "n/a"}


def _valore(grezzo) -> str | None:
    """L'API scrive `"dataNotProvided"` invece di omettere il campo: va
    trattato come assenza, o finirebbe scritto tale e quale in interfaccia."""
    testo = str(grezzo or "").strip()
    return None if testo.lower() in _VUOTI else testo


def _versione_di_lancio(voce: dict) -> int | None:
    """`"Android14"` → `14`. È la versione CON CUI IL MODELLO È USCITO,
    non quella attuale: chi la usa deve dirlo all'utente."""
    testo = _valore(voce.get("osVersionSupported"))
    if not testo:
        return None
    trovato = re.search(r"(\d{1,2})", testo)
    if not trovato:
        return None
    valore = int(trovato.group(1))
    return valore if 5 <= valore <= C.MAX_PLAUSIBLE_ANDROID else None


def parse_device(voce: dict) -> dict | None:
    nome = str(voce.get("displayName") or "").strip()
    if not nome:
        return None
    marca_aer = str(voce.get("brand") or voce.get("manufacturer") or "").strip()
    hardware = voce.get("hardwareFeatures") or {}
    immagini = voce.get("imageUrls") or {}
    return {
        "device_model": nome,
        "brand": _BRAND_MAP.get(marca_aer.lower(), C.OTHER),
        "brand_aer": marca_aer,
        "model_codes": _codici(voce),
        "launch_android": _versione_di_lancio(voce),
        # Fine del supporto di sicurezza e cadenza: il dato operativo che
        # giustifica da solo l'esistenza di questa fonte.
        "security_until": (_valore(voce.get("smrDate")) or "")[:10] or None,
        "security_frequency": _valore(voce.get("smrUpdateFrequency")),
        "security_url": _valore(voce.get("smrUrl")),
        "image_url": _valore(immagini.get("main") or immagini.get("original")),
        "form_factor": _valore(hardware.get("formFactor")),
        "source": SOURCE_KEY,
        "source_label": SOURCE_LABEL,
        "source_trust": C.TRUST_STRUCTURED,
    }


def verifica_versione_attuale(voce: dict) -> None:
    """Non restituisce niente: esiste solo per essere citata.

    `hardwareFeatures.os` è l'unico campo di questa API che sembra dire la
    versione attuale. Non la dice (vedi il docstring del modulo). Questa
    funzione è il posto dove è scritto il perché, così chi in futuro cercherà
    «os» in questo file lo trova prima di usarlo.
    """
    raise NotImplementedError(
        "L'AER non pubblica la versione attuale. `hardwareFeatures.os` è "
        "dichiarativo: il Galaxy S21 FE vi risulta Android 16, che non ha mai "
        "ricevuto. Per la versione attuale servono le fonti per marca "
        "(Samsung FOTA, Apple, Pixel, Xiaomi, Motorola)."
    )


# ----------------------------------------------------------------------
# Rete e indici
# ----------------------------------------------------------------------
def _scarica() -> list[dict]:
    richiesta = urllib.request.Request(
        ENDPOINT,
        headers={"User-Agent": C.USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(richiesta, timeout=C.HTTP_TIMEOUT + 30) as risposta:
        payload = json.loads(risposta.read().decode("utf-8", "replace"))
    voci = payload.get("items")
    if not isinstance(voci, list):
        raise ValueError("risposta in forma inattesa: manca 'items'")
    return voci


def _indicizza(voci: list[dict]) -> tuple[list[dict], dict, dict]:
    dispositivi, per_nome, per_codice = [], {}, {}
    corti: dict[str, dict] = {}
    contesi: set[str] = set()

    for voce in voci:
        letto = parse_device(voce)
        if not letto:
            continue
        dispositivi.append(letto)
        for alias in _nomi_alternativi(letto["device_model"]):
            per_nome.setdefault(normalize(alias), letto)
            breve = normalize_short(alias)
            if not breve or breve == normalize(alias):
                continue
            precedente = corti.get(breve)
            if precedente is not None and precedente is not letto:
                # Due modelli di marche diverse con lo stesso nome nudo
                # («OnePlus 12» e «Redmi 12» → `12`): la forma breve non
                # identifica più niente e va tolta del tutto.
                contesi.add(breve)
            else:
                corti[breve] = letto
        for codice in letto["model_codes"]:
            per_codice.setdefault(codice, letto)

    for chiave in contesi:
        corti.pop(chiave, None)
    # Le forme brevi non devono mai coprire un nome completo esistente.
    for chiave, letto in corti.items():
        per_nome.setdefault(chiave, letto)
    return dispositivi, per_nome, per_codice


def carica(forza: bool = False) -> list[dict]:
    global _dispositivi, _per_nome, _per_codice, _scaricato_a, _status
    with _lock:
        fresco = (
            _dispositivi is not None
            and _scaricato_a is not None
            and (time.monotonic() - _scaricato_a) < TTL_SECONDS
        )
        if fresco and not forza:
            return _dispositivi
        try:
            voci = _scarica()
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            _status = f"non raggiungibile: {exc}"
            # Meglio un catalogo vecchio che nessun catalogo: se c'era già
            # qualcosa in memoria lo si tiene, invece di azzerarlo.
            return _dispositivi or []
        _dispositivi, _per_nome, _per_codice = _indicizza(voci)
        _scaricato_a = time.monotonic()
        _status = f"{len(_dispositivi)} dispositivi, {len(_per_codice)} codici modello"
        return _dispositivi


def carica_da(voci: list[dict], etichetta: str = "elenco fornito") -> list[dict]:
    """Indicizza un elenco già in mano, **senza toccare la rete**.

    Esiste per due usi legittimi che prima non avevano un modo pulito di
    farsi: i test (che devono partire da una risposta registrata, non da
    quello che il server dice oggi) e un'eventuale copia locale del
    catalogo. Prima l'unica via era riassegnare `_scarica` e le variabili
    di modulo dall'esterno — cioè scrivere nei dettagli interni di un altro
    modulo, che è esattamente il genere di aggancio che si rompe in
    silenzio alla prima riorganizzazione.
    """
    global _dispositivi, _per_nome, _per_codice, _scaricato_a, _status
    with _lock:
        _dispositivi, _per_nome, _per_codice = _indicizza(list(voci))
        _scaricato_a = time.monotonic()
        _status = (f"{len(_dispositivi)} dispositivi, {len(_per_codice)} codici "
                   f"modello ({etichetta})")
        return _dispositivi


def lookup(testo: str) -> dict | None:
    """Cerca per codice tecnico o per nome commerciale, indifferentemente."""
    chiave = str(testo or "").strip()
    if not chiave:
        return None
    carica()
    trovato = _per_codice.get(chiave.upper())
    if trovato:
        return trovato
    return _per_nome.get(normalize(chiave))


def name_for_code(codice: str) -> str | None:
    """`CPH2791` → `OPPO Find X9 Pro`. Alimenta `modelcodes`/`suggest`."""
    voce = _per_codice.get(str(codice or "").strip().upper()) if _per_codice else None
    if voce is None:
        carica()
        voce = _per_codice.get(str(codice or "").strip().upper())
    return voce["device_model"] if voce else None


def all_devices() -> list[dict]:
    return list(carica())
