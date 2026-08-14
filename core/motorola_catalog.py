"""Catalogo ufficiale Motorola: codice XT -> nome commerciale.

Il file Google Play e MobileModels non contengono molti codici Motorola
europei. Motorola pubblica invece una tabella di conformita' con il modello
esatto e una pagina di supporto per ogni riga. La tabella serve solo per
identificare il telefono: non viene mai usata per inventare una versione di
Android o un firmware.
"""
from __future__ import annotations

import html
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import config as C
from . import storage


URL = "https://en-us.support.motorola.com/app/answers/detail/a_id/178271/p/11066"
TTL_SECONDS = 24 * 3600
_BLOB = "motorola_model_catalog_html"
_META = "motorola_model_catalog_fetched_at"

_ROW_RE = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>.*?\b(XT\d{4}(?:-\d{1,2})?)\b.*?</td>"
    r"\s*<td[^>]*>(.*?)</td>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_CODE_RE = re.compile(r"^XT\d{4}(?:-\d{1,2})?$", re.IGNORECASE)

_lock = threading.Lock()
_codes: dict[str, str] | None = None
_loaded_at: float | None = None
_status = "non ancora caricato"


def _clean(value: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", value or "")).split())


def parse(page: str) -> dict[str, str]:
    """Estrae la tabella senza dipendere dagli ``span`` decorativi del sito."""
    rows: dict[str, str] = {}
    for match in _ROW_RE.finditer(page or ""):
        code = match.group(1).upper()
        name = _clean(match.group(2))
        if _CODE_RE.fullmatch(code) and name:
            rows.setdefault(code, name)
    return rows


def _download() -> bytes:
    request = urllib.request.Request(URL, headers={"User-Agent": C.USER_AGENT})
    with urllib.request.urlopen(request, timeout=C.HTTP_TIMEOUT + 20) as response:
        content = response.read()
    if len(content) < 5000 or not parse(content.decode("utf-8", "replace")):
        raise ValueError("tabella Motorola assente o incompleta")
    return content


def carica(forza: bool = False) -> dict[str, str]:
    """Mappa aggiornata, con cache compressa nel DB incluso nell'immagine."""
    global _codes, _loaded_at, _status
    with _lock:
        if (_codes is not None and _loaded_at is not None and not forza
                and time.monotonic() - _loaded_at < TTL_SECONDS):
            return _codes

        cached = storage.get_blob(_BLOB)
        fetched = storage.get_meta(_META)
        fresh = False
        if cached and fetched and not forza:
            try:
                fresh = ((datetime.now(timezone.utc) - datetime.fromisoformat(fetched)).total_seconds()
                         < TTL_SECONDS)
            except (TypeError, ValueError):
                pass

        content = cached if fresh else None
        source = "archivio" if fresh else "rete"
        if content is None:
            try:
                content = _download()
                storage.set_blob(_BLOB, content)
                storage.set_meta(_META, datetime.now(timezone.utc).isoformat())
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                content = cached
                source = "archivio precedente"
                if content is None:
                    _status = f"non raggiungibile: {exc}"
                    return _codes or {}

        parsed = parse(content.decode("utf-8", "replace"))
        if not parsed:
            _status = "risposta senza codici XT"
            return _codes or {}
        _codes = parsed
        _loaded_at = time.monotonic()
        _status = f"{len(parsed)} codici XT ({source})"
        return _codes


def carica_da(rows: dict[str, str], etichetta: str = "elenco fornito") -> dict[str, str]:
    """Iniezione senza rete per i test."""
    global _codes, _loaded_at, _status
    with _lock:
        _codes = {str(code).upper(): str(name) for code, name in rows.items()
                  if _CODE_RE.fullmatch(str(code)) and str(name).strip()}
        _loaded_at = time.monotonic()
        _status = f"{len(_codes)} codici XT ({etichetta})"
        return _codes


def name_for_code(code: str) -> str | None:
    return carica().get(str(code or "").strip().upper())


def status() -> str:
    return _status


def reset_cache() -> None:
    global _codes, _loaded_at, _status
    with _lock:
        _codes = None
        _loaded_at = None
        _status = "non ancora caricato"
