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

# Parole troppo generiche per contare come corrispondenza: da sole non
# dicono che il titolo trovato parla del telefono cercato.
_PAROLE_GENERICHE = {"smartphone", "phone", "mobile", "the", "and", "of"}


def _parole_significative(testo: str) -> set[str]:
    parole = re.findall(r"[a-z0-9]+", (testo or "").lower())
    return {p for p in parole if len(p) >= 3 and p not in _PAROLE_GENERICHE}


def _titolo_pertinente(query: str, title: str) -> bool:
    """Il titolo trovato deve condividere almeno una parola con la domanda.

    SENZA QUESTO CONTROLLO, UN CODICE O UN NOME CORTO PUÒ FAR RISPONDERE
    WIKIPEDIA CON UN TELEFONO DI UN'ALTRA MARCA. Misurato in produzione:
    cercando un realme C61, la ricerca su Wikipedia — «C61 smartphone» —
    ha risposto con la voce di un telefono Xiaomi, e la scheda ha mostrato
    il logo Xiaomi per un dispositivo che non lo è. Il docstring del
    modulo lo segnalava già come rischio noto («Wikipedia... risponde
    sempre qualcosa e proprio per questo può rispondere il telefono
    sbagliato»): qui si trasforma da rischio accettato a controllo vero.

    Il criterio è deliberatamente permissivo — basta UNA parola in comune
    di almeno tre lettere, non un confronto sulla marca — perché il nome
    con cui si cerca e il titolo Wikipedia raramente coincidono parola
    per parola (abbreviazioni, «Galaxy» davanti o no, ecc.): lo scopo non
    è un confronto esatto, è scartare un titolo che non ha NULLA a che
    fare con la domanda, che è il caso di un errore vero.

    ## LA SIGLA DEL MODELLO DEVE COMBACIARE (16/08/2026)

    «Una parola in comune» basta a fermare il telefono di un'altra marca,
    ma non quello della STESSA marca — ed è il caso più frequente, perché
    per vivo, Honor e realme la marca è dentro il nome. Misurato:

        «vivo V30» → Vivo V40          «vivo Y36» → Vivo X300 Pro
        «Moto G24» → Motorola Moto     (la pagina generica della serie)

    Tutti e tre passavano il controllo sulla parola «vivo» o «moto», e la
    scheda mostrava la foto di un altro telefono. È lo stesso difetto del
    logo Xiaomi descritto sopra, solo dentro la stessa marca — e più
    insidioso, perché una foto plausibile non insospettisce nessuno.

    Quando la domanda contiene una sigla di modello (una parola con
    dentro una cifra: «x100», «v30», «g24», «s24»), quella sigla deve
    esserci anche nel titolo. Non è una stretta generale: per i nomi
    senza cifre — «Nothing Phone», «Pixel Fold» — resta la regola
    permissiva di prima, che per loro funzionava già.

    Meglio nessuna foto che la foto sbagliata: una casella vuota si vede,
    un telefono sbagliato no.
    """
    parole_domanda = _parole_significative(query)
    if not parole_domanda:
        return True   # niente con cui confrontare: non si può scartare nulla
    parole_titolo = _parole_significative(title)

    sigle_domanda = {p for p in parole_domanda if any(c.isdigit() for c in p)}
    if sigle_domanda:
        return bool(sigle_domanda & parole_titolo)
    return bool(parole_domanda & parole_titolo)


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
    if title and not _titolo_pertinente(query, title):
        title = None   # trovato qualcosa, ma non ha a che fare con la domanda
    url = _fetch_thumbnail(title) if title else None
    storage.cache_image(query, url or "")
    return url
