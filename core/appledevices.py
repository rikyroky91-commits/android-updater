"""Mappatura dispositivi Apple: identificatore ↔ nome commerciale.

Apple identifica internamente i dispositivi con stringhe tipo `iPhone15,2`
(iPhone 14 Pro) o `iPad14,3`. L'endpoint ufficiale Apple usato come fonte
degli aggiornamenti (`gdmf.apple.com/v2/pmv`) elenca proprio questi
identificatori in `SupportedDevices`, non i nomi commerciali: senza una
mappatura, l'app mostrerebbe "iPhone15,2" a chi cerca "iPhone 14 Pro".

Fonte della mappatura: `api.ipsw.me/v4/devices`, che restituisce l'elenco
completo dei dispositivi Apple con `identifier` e `name`.

NOTA SUL RISPETTO DELLA FONTE: la documentazione di ipsw.me chiede
esplicitamente di non sovraccaricare l'API ("please use this API fairly...
rate limiting is in place"). Per questo la risposta viene messa in cache sul
database e riscaricata al massimo una volta ogni due settimane — l'elenco
dei dispositivi Apple cambia solo quando esce un modello nuovo, quindi una
cache lunga non costa nulla in accuratezza.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import config as C
from . import storage

DEVICES_URL = "https://api.ipsw.me/v4/devices"
_META_JSON_KEY = "apple_devices_json"
_META_FETCHED_KEY = "apple_devices_fetched_at"
_REFRESH_HOURS = 24 * 14  # l'elenco cambia solo con un modello nuovo

# identifier -> nome commerciale, e l'indice inverso
_by_identifier: dict[str, str] | None = None
_by_name: dict[str, list[str]] | None = None
_status = "non ancora caricato"

# Solo telefoni e tablet: l'app traccia dispositivi mobili, non orologi,
# TV o visori (che pure compaiono nell'elenco di ipsw.me).
_MOBILE_PREFIXES = ("iphone", "ipad", "ipod")


def status() -> str:
    return _status


def _download() -> str | None:
    global _status
    if requests is None:  # pragma: no cover
        _status = "libreria 'requests' non disponibile"
        return None
    try:
        response = requests.get(
            DEVICES_URL, timeout=C.HTTP_TIMEOUT + 15,
            headers={"User-Agent": C.USER_AGENT, "Accept": "application/json"},
        )
    except Exception as exc:
        _status = f"connessione fallita: {exc}"
        return None
    if response.status_code != 200:
        _status = f"HTTP {response.status_code}"
        return None
    if len(response.text) < 500:
        _status = f"risposta sospettosamente corta ({len(response.text)} byte)"
        return None
    _status = f"scaricato con successo ({len(response.text) // 1024} KB)"
    return response.text


def _cached_text() -> str | None:
    global _status
    fetched_at = storage.get_meta(_META_FETCHED_KEY)
    cached = storage.get_meta(_META_JSON_KEY)
    if cached and fetched_at:
        try:
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
        except ValueError:
            age_h = _REFRESH_HOURS + 1
        if age_h < _REFRESH_HOURS:
            _status = f"da cache (aggiornata {age_h:.0f}h fa)"
            return cached

    fresh = _download()
    if fresh:
        storage.set_meta(_META_JSON_KEY, fresh)
        storage.set_meta(_META_FETCHED_KEY, datetime.now(timezone.utc).isoformat())
        return fresh
    if cached:
        _status += " — uso la cache precedente"
        return cached
    _status += " — nessuna cache precedente disponibile"
    return None


def normalize_name(name: str) -> str:
    """Chiave di confronto tollerante per un nome Apple: minuscolo, senza
    punteggiatura, e senza le precisazioni di connettività fra parentesi
    ('iPad Air (WiFi)' e 'iPad Air (Cellular)' collassano su 'ipad air')."""
    text = re.sub(r"\([^)]*\)", " ", name or "")
    text = re.sub(r"[^a-z0-9+]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _build() -> None:
    global _by_identifier, _by_name, _status
    _by_identifier, _by_name = {}, {}
    text = _cached_text()
    if not text:
        return
    try:
        entries = json.loads(text)
    except ValueError as exc:
        _status = f"JSON scaricato ma non interpretabile: {exc}"
        return
    if not isinstance(entries, list):
        _status = "JSON valido ma di forma inattesa (attesa una lista)"
        return

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        identifier = str(entry.get("identifier") or "").strip()
        name = str(entry.get("name") or "").strip()
        if not identifier or not name:
            continue
        if not identifier.lower().startswith(_MOBILE_PREFIXES):
            continue
        _by_identifier[identifier] = name
        key = normalize_name(name)
        if key:
            bucket = _by_name.setdefault(key, [])
            if identifier not in bucket:
                bucket.append(identifier)
    _status += f" — {len(_by_identifier)} dispositivi mobili indicizzati"


def name_for(identifier: str) -> str | None:
    """'iPhone15,2' → 'iPhone 14 Pro'."""
    if _by_identifier is None:
        _build()
    return (_by_identifier or {}).get((identifier or "").strip())


def identifiers_for(name: str) -> list[str]:
    """'iPhone 14 Pro' → ['iPhone15,2'] (più voci se esistono varianti)."""
    if _by_name is None:
        _build()
    return (_by_name or {}).get(normalize_name(name), [])


def is_apple_identifier(text: str) -> bool:
    """True se il testo somiglia a un identificatore interno Apple."""
    return bool(re.fullmatch(r"(?:iPhone|iPad|iPod)\d+,\d+", (text or "").strip(), re.IGNORECASE))


def reset_cache() -> None:
    global _by_identifier, _by_name, _status
    _by_identifier = None
    _by_name = None
    _status = "non ancora caricato"
