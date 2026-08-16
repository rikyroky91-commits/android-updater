"""Utility comuni: gestione date/timezone, formattazione italiana, slug e hash.

Nessuna dipendenza esterna: questo modulo deve restare importabile (e testabile)
anche senza requests / feedparser installati.
"""
from __future__ import annotations

import hashlib
import html
import re
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
