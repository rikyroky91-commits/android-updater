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
# Il catalogo con le forme già normalizzate — vedi `_catalogo_indicizzato`.
_indice_normalizzato: list[tuple[str, str, str, str]] | None = None
_mappa_normalizzata: dict[str, str] | None = None


# Compilate qui e non a ogni chiamata: `re.sub` con il modello scritto come
# STRINGA rifà ogni volta la ricerca nella cache dei modelli compilati, e
# questa funzione viene chiamata decine di migliaia di volte per ogni tasto
# digitato. Misurato: 1,7 milioni di `re.sub` per venti suggerimenti.
_RE_NON_ALFANUM = re.compile(r"[^a-z0-9+]+")
_RE_SPAZI = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _RE_SPAZI.sub(" ", _RE_NON_ALFANUM.sub(" ", (text or "").lower())).strip()


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

    try:  # catalogo delle schede tecniche (v45)
        # LA FONTE PIÙ RICCA DI NOMI CHE ABBIAMO, e fino alla v45 questo
        # catalogo non la vedeva: 4766 nomi commerciali, cioè quasi il
        # listino intero di undici marche. Senza, il «forse cercavi…»
        # sapeva correggere solo i modelli già passati da una scansione o
        # presenti nei dataset dei codici — e proprio i modelli nuovi, che
        # sono quelli che si sbagliano a scrivere, non c'erano.
        #
        # Non forza il caricamento: se il catalogo non è ancora stato
        # scaricato si resta senza questi nomi, invece di far attendere un
        # download a chi sta scrivendo nella casella di ricerca.
        from . import specs

        for scheda in (specs._schede or ()):
            if scheda.get("nome"):
                nomi.add(str(scheda["nome"]))
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
    global _cache, _cache_at, _indice_normalizzato, _mappa_normalizzata
    scaduto = (time.monotonic() - _cache_at) > _CACHE_TTL_SECONDS
    if _cache is None or scaduto or force_refresh:
        _cache = _collect_names()
        _cache_at = time.monotonic()
        # Il catalogo è cambiato: quello che ne deriva non vale più.
        _indice_normalizzato = None
        _mappa_normalizzata = None
    return _cache


def _catalogo_indicizzato() -> list[tuple[str, str, str, str]]:
    """Ogni nome con la sua forma normalizzata, già pronta.

    ## Perché esiste

    `suggest()` confrontava la domanda con TUTTO il catalogo normalizzando
    ogni nome sul momento, e lo faceva a ogni carattere digitato: sono
    quarantaquattromila normalizzazioni per tasto, ognuna con due
    espressioni regolari, più uno `split()` per la ricerca per parola.
    Misurato: 120 ms a tasto, cioè un campo di ricerca che arranca dietro
    a chi scrive — e il lavoro era sempre lo stesso, rifatto da capo.

    La forma normalizzata di un nome non cambia finché non cambia il
    catalogo, e il catalogo si ricostruisce ogni cinque minuti al massimo.
    Si calcola lì, una volta, e si riusa.

    L'indice si lega a una LOCALE prima di restituirlo: `catalog()` può
    azzerarlo da un altro thread fra il controllo e l'uso, ed è lo stesso
    difetto già corretto in `core/modelcodes.py` e `core/imeicheck.py`.
    """
    global _indice_normalizzato
    nomi = catalog()           # può ricostruire e azzerare l'indice derivato
    indice = _indice_normalizzato
    if indice is None:
        indice = []
        for nome in nomi:
            normalizzato = _normalize(nome)
            # LO SPAZIO DAVANTI NON È UN VEZZO. Serve a cercare «una parola
            # che comincia per X» con una sola ricerca di sottostringa:
            # siccome la forma normalizzata separa le parole con un solo
            # spazio, l'inizio di una parola è sempre preceduto da uno
            # spazio, e « gal» dentro « galaxy s24» dice esattamente quello
            # che diceva `any(p.startswith("gal") for p in parole)` — ma lo
            # decide il C invece di un ciclo Python per ogni nome.
            indice.append((nome, normalizzato, " " + normalizzato,
                           normalizzato.replace(" ", "")))
        _indice_normalizzato = indice
    return indice


def suggest(query: str, limit: int = 8) -> list[str]:
    """Completamenti per quello che si sta scrivendo, dal più pertinente.

    L'ordine conta: chi scrive «galaxy s24» vuole vedere prima «Galaxy S24»
    e «Galaxy S24 Ultra», non un modello che contiene quelle parole in mezzo
    ad altre.
    """
    bersaglio = _normalize(query)
    if len(bersaglio) < 2:
        return []

    inizia, parola, contiene, compatti = [], [], [], []
    a_inizio_parola = " " + bersaglio
    # LO SPAZIO FRA LA GAMMA E IL NUMERO NON DISTINGUE NIENTE, e qui non
    # veniva perdonato. Il catalogo scrive «OPPO Reno14» e «Mi 11», le
    # persone scrivono «oppo reno 14» e «mi11»: comunque sia scritto il
    # nome, l'altro modo non completava. Misurato: 9.620 nomi su 44.333
    # — il 22% del catalogo — sono esposti a questa ambiguità, in una
    # direzione o nell'altra, e fra loro ci sono Reno, Mi, Nord, Zenfone,
    # Galaxy, Find e moto.
    #
    # È lo stesso ripiego che `modelcodes.codes_for_name` applica già da
    # tempo, aggiunto proprio dopo una segnalazione su «oppo reno 14»: la
    # RICERCA quelle forme le trovava tutte, il COMPLETAMENTO no. Le due
    # metà dello stesso campo si comportavano al contrario, e il danno
    # peggiore non era il suggerimento mancato: mentre si digita non
    # compare niente, e si smette di scrivere prima di premere invio,
    # convinti che il modello non ci sia.
    #
    # STA IN FONDO, DOPO GLI ALTRI TRE, ed è la ragione per cui è sicuro:
    # attaccare le parole perde i confini fra loro, quindi è un confronto
    # più grossolano degli altri. Finché resta l'ultimo, nessun
    # suggerimento che oggi funziona cambia posto, e queste proposte
    # compaiono solo dove prima non c'era nulla.
    compattato = bersaglio.replace(" ", "")
    for nome, normalizzato, spaziato, senza_spazi in _catalogo_indicizzato():
        if normalizzato.startswith(bersaglio):
            inizia.append(nome)
        elif a_inizio_parola in spaziato:
            parola.append(nome)
        elif bersaglio in normalizzato:
            contiene.append(nome)
        elif compattato != bersaglio or " " in normalizzato:
            # si prova la forma attaccata solo se cambia qualcosa: o la
            # domanda aveva spazi, o ce li ha il nome.
            if compattato and compattato in senza_spazi:
                compatti.append(nome)

    ordina = lambda gruppo: sorted(gruppo, key=lambda n: (len(n), n))  # noqa: E731
    risultato = (ordina(inizia) + ordina(parola) + ordina(contiene)
                 + ordina(compatti))
    return risultato[:limit]


# ----------------------------------------------------------------------
# I codici tecnici: un catalogo a parte, e per un motivo
# ----------------------------------------------------------------------
# I codici sono esclusi dal catalogo dei NOMI apposta: come completamento
# non aiutano a scrivere «Galaxy S24», e in mezzo ai nomi commerciali
# renderebbero l'elenco illeggibile.
#
# Come bersaglio della correzione però servono eccome, perché è la forma
# che si sbaglia più facilmente: un codice non si ricorda, si copia — da
# un'etichetta, da una schermata, da un messaggio — e si copia male.
# `SMA075F` senza trattino, `SM-A075` troncato, uno zero al posto di una
# O: nessuno di questi trova niente oggi, e sono tutti a un carattere da
# un codice valido.
_cache_codici: list[str] | None = None
_cache_codici_at = 0.0

_RE_SEMBRA_CODICE = re.compile(r"^[a-z]{1,4}[\s-]?[a-z]?\d{2,5}[a-z0-9\s/-]*$", re.I)


def _collect_codes() -> list[str]:
    codici: set[str] = set()

    try:
        from . import specs

        for scheda in (specs._schede or ()):
            codici.update(scheda.get("codici") or ())
    except Exception:
        pass

    try:
        from . import modelcodes

        if modelcodes._memory_cache is None:
            modelcodes.resolve("")
        codici.update((modelcodes._memory_cache or {}).keys())
    except Exception:
        pass

    return sorted(c for c in (str(x or "").strip().upper() for x in codici)
                  if 4 <= len(c) <= 20)


def catalogo_codici(force_refresh: bool = False) -> list[str]:
    global _cache_codici, _cache_codici_at
    scaduto = (time.monotonic() - _cache_codici_at) > _CACHE_TTL_SECONDS
    if _cache_codici is None or scaduto or force_refresh:
        _cache_codici = _collect_codes()
        _cache_codici_at = time.monotonic()
    return _cache_codici


def sembra_un_codice(query: str) -> bool:
    """«SM-A075F» sì, «Galaxy A07» no.

    Serve a non sprecare una passata di somiglianza sui codici quando chi
    cerca ha scritto chiaramente un nome commerciale, e viceversa.
    """
    testo = " ".join(str(query or "").split())
    if not testo or " " in testo.strip() and len(testo.split()) > 2:
        return False
    return bool(_RE_SEMBRA_CODICE.match(testo))


def codici_simili(query: str, limit: int = 5, cutoff: float = 0.72) -> list[str]:
    """Codici modello a un errore di distanza da quello scritto."""
    bersaglio = re.sub(r"[^A-Z0-9]", "", str(query or "").upper())
    if len(bersaglio) < 4:
        return []
    codici = catalogo_codici()
    # Il confronto avviene senza trattini né spazi da entrambe le parti:
    # `SMA075F` e `SM-A075F` devono risultare identici, non simili.
    indice: dict[str, str] = {}
    for codice in codici:
        indice.setdefault(re.sub(r"[^A-Z0-9]", "", codice), codice)
    if bersaglio in indice:
        return [indice[bersaglio]]

    # SI RIORDINA PER RADICE COMUNE, non solo per somiglianza.
    # `difflib` da solo, su `SM-A075G`, mette davanti `SM-A505G` e
    # `SM-A305G`: hanno lo stesso numero di caratteri in comune, quindi
    # per lui valgono uguale. Ma un codice si sbaglia quasi sempre in
    # coda — l'ultima lettera è la variante regionale, ed è quella che si
    # legge male da un'etichetta — mentre la radice `SM-A075` la si
    # trascrive giusta. Chi ha scritto `SM-A075G` cerca un A075, non un
    # A505: la lunghezza del prefisso in comune lo dice, la somiglianza
    # complessiva no.
    def radice_comune(codice: str) -> int:
        comune = 0
        for a, b in zip(bersaglio, codice):
            if a != b:
                break
            comune += 1
        return comune

    vicini = difflib.get_close_matches(bersaglio, list(indice),
                                       n=limit * 4, cutoff=cutoff)
    vicini.sort(key=lambda c: (-radice_comune(c),
                               -difflib.SequenceMatcher(None, bersaglio, c).ratio()))
    return [indice[v] for v in vicini[:limit]]


def _mappa_normalizzati() -> dict[str, str]:
    """Forma normalizzata -> nome originale, costruita una volta sola."""
    global _mappa_normalizzata
    indice = _catalogo_indicizzato()      # può azzerare quello che deriva da lui
    mappa = _mappa_normalizzata
    if mappa is None:
        mappa = {normalizzato: nome for nome, normalizzato, _sp, _co in indice}
        _mappa_normalizzata = mappa
    return mappa


def _candidati_per_lunghezza(indice, bersaglio: str, cutoff: float) -> list[str]:
    """Solo i nomi che possono ANCORA superare la soglia, per lunghezza.

    Non è un'approssimazione, è un'esclusione dimostrata. `difflib`
    calcola `2*M/T`, dove M sono i caratteri in comune e T la somma delle
    due lunghezze; siccome M non può superare la lunghezza della stringa
    più corta, il punteggio non può superare

        2 * min(la, lb) / (la + lb)

    Imporre che questo resti sopra la soglia dà una finestra di lunghezze
    fuori dalla quale il confronto è già perso in partenza: con la soglia
    predefinita, fra 0,56 e 1,78 volte la lunghezza di quello che si è
    scritto. Sono gli stessi limiti che `difflib` applica al suo interno
    con `real_quick_ratio`, ma pagati qui una volta per candidato invece
    che dopo aver costruito un oggetto di confronto per ognuno.

    Il risultato è identico per costruzione: si tolgono solo candidati
    che la soglia avrebbe comunque scartato.
    """
    lunghezza = len(bersaglio)
    if not lunghezza or cutoff <= 0:
        return list(indice)
    minima = lunghezza * cutoff / (2 - cutoff)
    massima = lunghezza * (2 - cutoff) / cutoff
    return [n for n in indice if minima <= len(n) <= massima]


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

    # I CODICI PRIMA, quando è un codice che si sta scrivendo. Un `SMA075F`
    # confrontato coi nomi commerciali non somiglia a niente, e la funzione
    # tornava a mani vuote su quello che è l'errore più frequente in
    # assoluto — perché un codice non si ricorda, si copia, e si copia male.
    if sembra_un_codice(query):
        vicini_codice = codici_simili(query, limit=limit, cutoff=cutoff)
        if vicini_codice:
            return vicini_codice

    indice = _mappa_normalizzati()
    vicini = difflib.get_close_matches(
        bersaglio, _candidati_per_lunghezza(indice, bersaglio, cutoff),
        n=limit, cutoff=cutoff)
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
    # E ANCHE QUELLO CHE DERIVA DAL CATALOGO. Azzerare la sorgente
    # lasciando in piedi l'indice normalizzato costruito da lei significa
    # rispondere con il catalogo vecchio a chi ha appena chiesto di
    # buttarlo: è lo stesso difetto già corretto in `core/modelcodes.py`,
    # dove `carica_indice` sostituiva l'indice e lasciava indietro quello
    # inverso.
    global _cache, _cache_at, _cache_codici, _cache_codici_at
    global _indice_normalizzato, _mappa_normalizzata
    _cache = None
    _cache_at = 0.0
    _cache_codici = None
    _cache_codici_at = 0.0
    _indice_normalizzato = None
    _mappa_normalizzata = None
