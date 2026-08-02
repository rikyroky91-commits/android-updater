"""Suggerimenti di ricerca: completamento e tolleranza agli errori.

Il problema che risolve: per trovare un modello bisognava indovinarne il
nome esatto. Chi scrive «galaxi s24», «iphone 15pro» o «redmi note13» non
ottiene nulla, anche se il dispositivo è perfettamente noto all'app — ed è
il modo più comune di non trovare quello che si cerca.

I portali di settore risolvono questo con tre cose, riprese qui:
  1. completamento mentre si digita, da un catalogo di nomi noti;
  2. «forse cercavi…» quando la ricerca non dà risultati;
  3. disambiguazione, quando un termine corrisponde a più modelli.

Il catalogo dei nomi non richiede nuove fonti: si costruisce da ciò che
l'app già possiede — i dispositivi in archivio, i dataset dei codici
modello, l'elenco dispositivi Apple, i modelli ufficiali realme.

Nessuna dipendenza esterna: la somiglianza usa `difflib` della libreria
standard.
"""
from __future__ import annotations

import difflib
import re
import time

from . import config as C

_CACHE_TTL_SECONDS = 300  # il catalogo cambia solo quando arrivano nuovi dati
_cache: list[str] | None = None
_cache_at = 0.0


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+]+", " ", (text or "").lower())).strip()


def _collect_names() -> list[str]:
    """Nomi di dispositivo noti, da tutte le fonti già disponibili.

    Ogni raccolta è protetta: una fonte non ancora caricata (o rotta) deve
    ridurre la qualità dei suggerimenti, non impedirli del tutto.
    """
    nomi: set[str] = set()
    nomi_realme: set[str] = set()

    try:  # dispositivi già visti dalle scansioni
        from . import storage

        for device in storage.get_devices():
            if device.get("model"):
                nomi.add(str(device["model"]))
    except Exception:
        pass

    try:  # nomi commerciali dai dataset dei codici modello
        from . import modelcodes

        if modelcodes._memory_cache is None:
            modelcodes.resolve("")  # forza il caricamento una volta sola
        for elenco in (modelcodes._memory_cache or {}).values():
            nomi.update(elenco)
    except Exception:
        pass

    try:  # nomi ufficiali realme, scomposti nei singoli modelli regionali
        from . import sources

        # ATTENZIONE al nome della variabile del ciclo: chiamarla `nomi`
        # riassegnava l'insieme che sta accumulando tutto, e da lì in poi
        # `nomi` era l'ultima lista realme invece del catalogo. Le
        # `nomi.update(...)` successive sollevavano AttributeError, che i
        # `except Exception: pass` inghiottivano: il catalogo si riduceva a
        # un modello solo, senza un errore visibile da nessuna parte.
        for varianti, _codice in sources.realme_name_variants().values():
            nomi_realme.update(varianti)
        nomi.update(nomi_realme)
    except Exception:
        pass

    try:  # iPhone / iPad
        from . import appledevices

        if appledevices._by_identifier is None:
            appledevices.name_for("")  # forza il caricamento
        nomi.update((appledevices._by_identifier or {}).values())
    except Exception:
        pass

    puliti = set()
    for nome in nomi:
        nome = " ".join(str(nome or "").split())
        # Si scartano gli identificatori interni (iPhone16,1) e i codici
        # tecnici puri: come suggerimento non aiutano a scrivere il nome.
        if not nome or len(nome) < 3 or "," in nome:
            continue
        if re.fullmatch(r"[A-Z]{2,4}[- ]?\d{3,5}[A-Z]*", nome):
            continue
        puliti.add(nome)
    return sorted(puliti)


def catalog(force_refresh: bool = False) -> list[str]:
    global _cache, _cache_at
    scaduto = (time.monotonic() - _cache_at) > _CACHE_TTL_SECONDS
    if _cache is None or scaduto or force_refresh:
        _cache = _collect_names()
        _cache_at = time.monotonic()
    return _cache


def suggest(query: str, limit: int = 8) -> list[str]:
    """Completamenti per quello che si sta scrivendo, dal più pertinente.

    L'ordine conta: chi scrive «galaxy s24» vuole vedere prima «Galaxy S24»
    e «Galaxy S24 Ultra», non un modello che contiene quelle parole in mezzo
    ad altre.
    """
    bersaglio = _normalize(query)
    if len(bersaglio) < 2:
        return []

    inizia, parola, contiene = [], [], []
    for nome in catalog():
        normalizzato = _normalize(nome)
        if normalizzato.startswith(bersaglio):
            inizia.append(nome)
        elif any(p.startswith(bersaglio) for p in normalizzato.split()):
            parola.append(nome)
        elif bersaglio in normalizzato:
            contiene.append(nome)

    ordina = lambda gruppo: sorted(gruppo, key=lambda n: (len(n), n))  # noqa: E731
    risultato = ordina(inizia) + ordina(parola) + ordina(contiene)
    return risultato[:limit]


def did_you_mean(query: str, limit: int = 5, cutoff: float = 0.72) -> list[str]:
    """«Forse cercavi…»: nomi simili, per gli errori di battitura.

    Serve quando la ricerca non trova nulla: «galaxi s24» o «redmi note13»
    non corrispondono a nessun nome, ma sono a un carattere di distanza da
    uno valido. La soglia è volutamente alta: un suggerimento sbagliato
    manda fuori strada più di quanto un suggerimento mancato faccia danno.
    """
    bersaglio = _normalize(query)
    if len(bersaglio) < 3:
        return []

    nomi = catalog()
    indice = {_normalize(n): n for n in nomi}
    vicini = difflib.get_close_matches(bersaglio, list(indice), n=limit, cutoff=cutoff)
    proposte = [indice[v] for v in vicini]

    # Un errore su una parola sola (es. «galaxi» per «galaxy») spesso non
    # supera la soglia sull'intera frase: si ritenta parola per parola.
    if not proposte and " " in bersaglio:
        parole = bersaglio.split()
        vocabolario = {p for n in indice for p in n.split()}
        corrette = []
        for parola in parole:
            simili = difflib.get_close_matches(parola, list(vocabolario), n=1, cutoff=cutoff)
            corrette.append(simili[0] if simili else parola)
        ricostruita = " ".join(corrette)
        if ricostruita != bersaglio:
            proposte = suggest(ricostruita, limit=limit)
    return proposte


def brands_with_devices() -> dict[str, list[str]]:
    """Catalogo raggruppato per marca, per sfogliare senza dover scrivere.

    Molti portali offrono questa via d'ingresso proprio perché non tutti
    ricordano il nome esatto del proprio telefono.
    """
    try:
        from . import storage

        devices = storage.get_devices()
    except Exception:
        return {}

    per_brand: dict[str, list[str]] = {}
    for device in devices:
        brand = device.get("brand") or C.OTHER
        modello = device.get("model")
        if modello:
            per_brand.setdefault(brand, []).append(str(modello))
    return {b: sorted(set(m)) for b, m in sorted(per_brand.items())}


def reset_cache() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0
