"""Catalogo ufficiale Motorola: codice XT -> nome commerciale.

Il file Google Play e MobileModels non contengono molti codici Motorola
europei. Motorola pubblica invece una tabella di conformita' con il modello
esatto e una pagina di supporto per ogni riga. La tabella serve solo per
identificare il telefono: non viene mai usata per inventare una versione di
Android o un firmware.
"""
from __future__ import annotations

import csv
import html
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import config as C
from . import storage


URL = "https://en-us.support.motorola.com/app/answers/detail/a_id/178271/p/11066"
TTL_SECONDS = 24 * 3600
_BLOB = "motorola_model_catalog_html"
_META = "motorola_model_catalog_fetched_at"
_SEED = Path(__file__).resolve().parents[1] / "data" / "motorola_modelli.csv"

_ROW_RE = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>.*?\b(XT\d{4}(?:-\d{1,2})?)\b.*?</td>"
    r"\s*<td[^>]*>(.*?)</td>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_CODE_RE = re.compile(r"^XT\d{4}(?:-\d{1,2})?$", re.IGNORECASE)
_NAME_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_lock = threading.Lock()
_codes: dict[str, str] | None = None
_loaded_at: float | None = None
_status = "non ancora caricato"
_from_seed = False


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


def _catalogo_incluso() -> dict[str, str]:
    """Snapshot piccolo della tabella Motorola, disponibile senza rete.

    La build prova comunque a scaricare la tabella aggiornata e la salva nel
    database. Il file incluso copre pero' il caso importante in cui la rete
    del *build* di Render non risponde: la prima ricerca Motorola non deve
    degradare al solo nome del telefono ne' aspettare un worker di fondo.
    """
    try:
        with _SEED.open(encoding="utf-8", newline="") as handle:
            return {
                str(row.get("codice") or "").strip().upper():
                str(row.get("nome") or "").strip()
                for row in csv.DictReader(handle)
                if _CODE_RE.fullmatch(str(row.get("codice") or "").strip())
                and str(row.get("nome") or "").strip()
            }
    except OSError:
        return {}


def _download() -> bytes:
    request = urllib.request.Request(URL, headers={"User-Agent": C.USER_AGENT})
    with urllib.request.urlopen(request, timeout=C.HTTP_TIMEOUT + 20) as response:
        content = response.read()
    if len(content) < 5000 or not parse(content.decode("utf-8", "replace")):
        raise ValueError("tabella Motorola assente o incompleta")
    return content


def carica(forza: bool = False, rete: bool = True) -> dict[str, str]:
    """Mappa aggiornata, con cache compressa nel DB incluso nell'immagine.

    ``rete=False`` serve alle ricerche interattive: il database-seme creato
    durante la build è già sufficiente a risolvere i codici, mentre attendere
    il refresh del sito Motorola può consumare tutto il budget della pagina.
    Il preload e i refresh espliciti mantengono invece il comportamento di
    rete predefinito.
    """
    global _codes, _loaded_at, _status, _from_seed
    with _lock:
        if (_codes is not None and _loaded_at is not None and not forza
                and time.monotonic() - _loaded_at < TTL_SECONDS
                # Una risposta dal file incluso e' subito utilizzabile,
                # ma non deve impedire al preload dal completare il refresh
                # ufficiale quando la rete e' disponibile.
                and (not rete or not _from_seed)):
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

        content = cached if fresh or not rete else None
        source = "archivio" if content is not None else "rete"
        if content is None and not rete:
            # La richiesta interattiva non deve trasformarsi in un download
            # inatteso quando il database-seme non e' ancora disponibile.
            # Torna vuoto: il chiamante prosegue con le altre fonti nel suo
            # budget, mentre il preload/refresh esplicito puo' popolare la
            # cache in seguito.
            included = _catalogo_incluso()
            if included:
                _codes = included
                _loaded_at = time.monotonic()
                _from_seed = True
                _status = f"{len(included)} codici XT (copia inclusa)"
                return _codes
            _status = "archivio non disponibile"
            return _codes or {}

        if content is None:
            try:
                content = _download()
                storage.set_blob(_BLOB, content)
                storage.set_meta(_META, datetime.now(timezone.utc).isoformat())
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                content = cached
                source = "archivio precedente"
                if content is None:
                    included = _catalogo_incluso()
                    if included:
                        _codes = included
                        _loaded_at = time.monotonic()
                        _from_seed = True
                        _status = f"{len(included)} codici XT (copia inclusa; rete non raggiungibile)"
                        return _codes
                    _status = f"non raggiungibile: {exc}"
                    return _codes or {}

        parsed = parse(content.decode("utf-8", "replace"))
        if not parsed:
            _status = "risposta senza codici XT"
            return _codes or {}
        _codes = parsed
        _loaded_at = time.monotonic()
        _from_seed = False
        _status = f"{len(parsed)} codici XT ({source})"
        return _codes


def carica_da(rows: dict[str, str], etichetta: str = "elenco fornito") -> dict[str, str]:
    """Iniezione senza rete per i test."""
    global _codes, _loaded_at, _status, _from_seed
    with _lock:
        _codes = {str(code).upper(): str(name) for code, name in rows.items()
                  if _CODE_RE.fullmatch(str(code)) and str(name).strip()}
        _loaded_at = time.monotonic()
        _from_seed = False
        _status = f"{len(_codes)} codici XT ({etichetta})"
        return _codes


def name_for_code(code: str, rete: bool = True) -> str | None:
    return carica(rete=rete).get(str(code or "").strip().upper())


def _name_key(value: str) -> str:
    """Chiave prudente per il nome commerciale nella tabella Motorola.

    Il catalogo ufficiale alterna ``motorola moto g05`` e ``moto g05``;
    marca e spazi non devono decidere se la ricerca per nome riesce. Non si
    eliminano invece parole di gamma (``power``, ``5g``...) perche' quelle
    identificano modelli diversi.
    """
    words = [w.lower() for w in _NAME_WORD_RE.findall(value or "")]
    return " ".join(w for w in words if w not in {"motorola", "moto"})


def codes_for_name(name: str) -> list[str]:
    """Codici XT ufficiali per un nome commerciale esatto.

    E' l'inverso di :func:`name_for_code`: permette alla ricerca di partire
    da ``moto g05`` e interrogare un archivio firmware *per codice*, senza
    mantenere nel codice una lista manuale di modelli Motorola.
    """
    target = _name_key(name)
    if not target:
        return []
    return [code for code, display in carica(rete=False).items()
            if _name_key(display) == target]


def status() -> str:
    return _status


def reset_cache() -> None:
    global _codes, _loaded_at, _status, _from_seed
    with _lock:
        _codes = None
        _loaded_at = None
        _from_seed = False
        _status = "non ancora caricato"
