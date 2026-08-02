"""Immagine del dispositivo per la scheda di ricerca.

Usa l'API pubblica di Wikipedia (nessuna chiave richiesta): prima una ricerca
per trovare la voce più pertinente al modello, poi il suo estratto/riepilogo
per l'immagine in evidenza (di solito la foto del telefono nell'infobox).

Il risultato viene messo in cache su database (tabella `device_images`):
Streamlit riesegue lo script a ogni interazione, quindi senza cache la stessa
immagine verrebbe richiesta più volte durante la stessa sessione.
"""
from __future__ import annotations

import re

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import config as C
from . import storage

_WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
_WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# Termini che, se il titolo Wikipedia trovato li contiene, indicano una voce
# sbagliata (disambigua, categoria, ecc.) da scartare.
_BAD_TITLE_RE = re.compile(r"\b(disambiguation|category|list of)\b", re.IGNORECASE)


def _get(url: str, params: dict):
    return requests.get(
        url, params=params, timeout=C.HTTP_TIMEOUT,
        headers={"User-Agent": C.USER_AGENT, "Accept": "application/json"},
    )


def _search_title(query: str) -> str | None:
    try:
        response = _get(_WIKI_SEARCH_URL, {
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 3,
        })
    except Exception:
        return None
    if response.status_code != 200:
        return None
    try:
        results = response.json()["query"]["search"]
    except (ValueError, KeyError):
        return None
    for result in results:
        title = result.get("title", "")
        if title and not _BAD_TITLE_RE.search(title):
            return title
    return None


def _fetch_thumbnail(title: str) -> str | None:
    try:
        response = _get(_WIKI_SUMMARY_URL.format(title=title.replace(" ", "_")), {})
    except Exception:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    thumb = data.get("originalimage") or data.get("thumbnail")
    return thumb.get("source") if thumb else None


def find_device_image(query: str) -> str | None:
    """Ritorna l'URL di un'immagine per il modello, o None se non trovata.

    Usa sempre la cache su database prima di interrogare Wikipedia: una
    ricerca già fatta in passato non genera più traffico di rete.
    """
    query = (query or "").strip()
    if not query:
        return None

    cached = storage.get_cached_image(query)
    if cached is not None:
        return cached or None  # stringa vuota in cache = "cercato, non trovato"

    if requests is None:  # pragma: no cover
        return None

    title = _search_title(f"{query} smartphone")
    url = _fetch_thumbnail(title) if title else None
    storage.cache_image(query, url or "")
    return url
