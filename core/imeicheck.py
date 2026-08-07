"""Identificazione marca/modello da IMEI (come fa imei.info), usando il TAC.

Il TAC (Type Allocation Code) sono le prime 8 cifre di un IMEI: identificano
il modello del dispositivo (non l'unità fisica), sono assegnate dalla GSMA e
sono informazione pubblica — cercarle in una tabella locale non contatta
nessun server e non richiede nessuna autenticazione.

Principio di privacy importante: l'IMEI passato a `identify()` NON viene mai
salvato su disco né loggato da nessuna parte in questo modulo. Solo il TAC
(derivato) viene usato per la ricerca; il chiamante (app.py) deve a sua volta
salvare nella cronologia solo il modello risolto, mai l'IMEI originale.

Uso deliberatamente NON incluso: questo modulo non contatta alcun server di
un produttore con l'IMEI. Identifica solo marca/modello da un dato pubblico
(il TAC); la ricerca dell'ultimo aggiornamento per quel modello passa poi
dalla normale pipeline di ricerca (Google News + fonti strutturate), non da
un controllo diretto sul dispositivo specifico.
"""
from __future__ import annotations

import re
import csv
import io
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

from . import config as C
from . import storage

TAC_DB_URL = "https://raw.githubusercontent.com/MoazEb/tac-database/main/tac_full.xlsx"

# SECONDA base dati, consultata solo per i TAC che la prima non ha.
#
# Nessun database TAC pubblico è completo: sono tutti alimentati dalla
# community e ognuno ha buchi diversi. Un IMEI valido che «non esiste»
# mentre altri siti lo riconoscono è quasi sempre un buco di copertura,
# non un IMEI sbagliato — quindi vale la pena chiedere a due fonti prima
# di dire di no.
#
# Osmocom è vecchia (i dati a monte si fermano intorno al 2014) e non
# aiuta sui modelli recenti, ma copre bene i TAC storici, che è
# esattamente dove la prima base dati è più debole.
TAC_DB_FALLBACK_URL = "http://tacdb.osmocom.org/export/tacdb.csv"
_META_FALLBACK_BYTES = "imei_tacdb2_bytes"
_META_FALLBACK_FETCHED = "imei_tacdb2_fetched_at"
_META_BYTES_KEY = "imei_tacdb_bytes"
_META_FETCHED_KEY = "imei_tacdb_fetched_at"
_REFRESH_HOURS = 24 * 14  # database molto stabile, un refresh ogni due settimane basta

_memory_index: dict[str, tuple[str, str]] | None = None  # tac -> (brand, specs)
_status = "non ancora caricato"


def status() -> str:
    return _status


def _download() -> bytes | None:
    global _status
    if requests is None:  # pragma: no cover
        _status = "libreria 'requests' non disponibile"
        return None
    try:
        response = requests.get(TAC_DB_URL, timeout=C.HTTP_TIMEOUT + 30, headers={"User-Agent": C.USER_AGENT})
    except Exception as exc:
        _status = f"connessione fallita: {exc}"
        return None
    if response.status_code != 200:
        _status = f"HTTP {response.status_code}"
        return None
    if len(response.content) < 10_000:
        _status = f"risposta sospettosamente corta ({len(response.content)} byte)"
        return None
    _status = f"scaricato con successo ({len(response.content) // 1024} KB)"
    return response.content


def _cached_bytes() -> bytes | None:
    fetched_at = storage.get_meta(_META_FETCHED_KEY)
    cached_hex = storage.get_meta(_META_BYTES_KEY)
    if cached_hex and fetched_at:
        try:
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
        except ValueError:
            age_h = _REFRESH_HOURS + 1
        if age_h < _REFRESH_HOURS:
            return bytes.fromhex(cached_hex)

    fresh = _download()
    if fresh:
        storage.set_meta(_META_BYTES_KEY, fresh.hex())
        storage.set_meta(_META_FETCHED_KEY, datetime.now(timezone.utc).isoformat())
        return fresh
    if cached_hex:
        return bytes.fromhex(cached_hex)
    return None


def _scarica_url(url: str, minimo: int = 10_000) -> bytes | None:
    """Scarica una base dati TAC senza toccare lo stato globale.

    A differenza di `_download`, non scrive in `_status`: questo serve alla
    fonte supplementare, il cui esito non deve mascherare la diagnosi della
    fonte principale — se la storica non risponde non è un guasto dell'app.
    """
    if requests is None:  # pragma: no cover
        return None
    try:
        response = requests.get(url, timeout=C.HTTP_TIMEOUT + 30,
                                headers={"User-Agent": C.USER_AGENT})
    except Exception:
        return None
    if response.status_code != 200 or len(response.content) < minimo:
        return None
    return response.content


def _cached_bytes_url(url: str, chiave_byte: str, chiave_data: str) -> bytes | None:
    """Come `_cached_bytes` ma per un URL qualsiasi."""
    fetched_at = storage.get_meta(chiave_data)
    cached_hex = storage.get_meta(chiave_byte)
    if cached_hex and fetched_at:
        try:
            eta = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
        except ValueError:
            eta = _REFRESH_HOURS + 1
        if eta < _REFRESH_HOURS:
            return bytes.fromhex(cached_hex)

    fresco = _scarica_url(url)
    if fresco:
        storage.set_meta(chiave_byte, fresco.hex())
        storage.set_meta(chiave_data, datetime.now(timezone.utc).isoformat())
        return fresco
    if cached_hex:
        return bytes.fromhex(cached_hex)
    return None


def _build_index() -> dict[str, tuple[str, str]]:
    global _status
    if openpyxl is None:  # pragma: no cover
        _status = "libreria 'openpyxl' non disponibile"
        return {}
    raw = _cached_bytes()
    if not raw:
        return {}

    index: dict[str, tuple[str, str]] = {}
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:
        _status = f"file scaricato ma non interpretabile: {exc}"
        return {}

    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            continue
        header_lower = [str(h).strip().lower() if h else "" for h in header]
        try:
            i_brand = header_lower.index("brand")
            i_tac = header_lower.index("tac")
            i_specs = header_lower.index("specs")
        except ValueError:
            continue  # foglio senza le colonne attese: si salta, non si blocca tutto
        for row in rows:
            if len(row) <= max(i_brand, i_tac, i_specs):
                continue
            tac = str(row[i_tac] or "").strip()
            brand = str(row[i_brand] or "").strip()
            specs = str(row[i_specs] or "").strip()
            if len(tac) == 8 and tac.isdigit() and brand:
                index[tac] = (brand, specs)
    workbook.close()

    prima = len(index)
    for tac, voce in _indice_fallback().items():
        index.setdefault(tac, voce)
    aggiunti = len(index) - prima

    if not index:
        _status = "file interpretato ma nessuna riga valida trovata (formato cambiato?)"
    else:
        _status += f" — {prima} codici TAC indicizzati"
        if aggiunti:
            _status += f" (+{aggiunti} dalla base dati storica)"
    return index


def _indice_fallback() -> dict[str, tuple[str, str]]:
    """TAC dalla base dati storica, in formato CSV.

    Fallisce in silenzio di proposito: è un supplemento, e se non è
    raggiungibile l'app deve continuare a funzionare con la prima base
    dati invece di non identificare più niente.
    """
    raw = _cached_bytes_url(TAC_DB_FALLBACK_URL, _META_FALLBACK_BYTES,
                            _META_FALLBACK_FETCHED)
    if not raw:
        return {}
    try:
        testo = raw.decode("utf-8", "replace")
    except Exception:
        return {}

    indice: dict[str, tuple[str, str]] = {}
    lettore = csv.reader(io.StringIO(testo))
    try:
        intestazione = [c.strip().lower() for c in next(lettore)]
    except StopIteration:
        return {}

    def colonna(*nomi):
        for nome in nomi:
            if nome in intestazione:
                return intestazione.index(nome)
        return None

    i_tac = colonna("tac")
    i_marca = colonna("manufacturer", "brand", "vendor")
    i_modello = colonna("model", "name", "device")
    if i_tac is None or i_marca is None:
        return {}

    for riga in lettore:
        if len(riga) <= max(i_tac, i_marca):
            continue
        tac = str(riga[i_tac] or "").strip()
        marca = str(riga[i_marca] or "").strip()
        modello = (str(riga[i_modello] or "").strip()
                   if i_modello is not None and i_modello < len(riga) else "")
        if len(tac) == 8 and tac.isdigit() and marca:
            indice[tac] = (marca, modello)
    return indice


# ======================================================================
# Terza via: interrogazione puntuale del SOLO TAC
# ======================================================================
# Perché serve. I database scaricabili gratuiti hanno buchi diversi e
# nessuno è completo: il TAC `35135531` è assente da entrambi quelli in
# uso, mentre i servizi commerciali lo identificano. Quei servizi però o
# bloccano l'accesso automatico (imei.info risponde con rilevamento bot) o
# lo vietano nei termini d'uso, quindi non sono una strada percorribile.
#
# HiCellTek offre un piano gratuito (100 interrogazioni al mese) e —
# differenza che qui conta più del prezzo — accetta il **solo TAC di 8
# cifre**, non l'IMEI completo. Il resto del numero, che è la parte che
# identifica il singolo telefono, non esce mai da questa macchina.
#
# È DISATTIVATA finché non c'è una chiave. Senza chiave l'app si comporta
# esattamente come prima: nessuna chiamata, nessun errore.
TAC_API_URL = "https://imei.hicelltek.com/api/v1/tac/lookup"


def _chiave_api() -> str:
    try:
        import streamlit as st
        return (st.secrets.get("TAC_API_KEY", "") or "").strip()
    except Exception:
        return ""


def cerca_tac_online(tac: str) -> tuple[str, str] | None:
    """Marca e modello per un TAC, chiedendoli al servizio esterno.

    Ritorna None in ogni caso incerto: chiave assente, servizio non
    raggiungibile, risposta inattesa, TAC sconosciuto. Un servizio a
    pagamento che non risponde non deve mai diventare un dato inventato.
    """
    chiave = _chiave_api()
    if not chiave or requests is None:
        return None
    tac = "".join(c for c in (tac or "") if c.isdigit())[:8]
    if len(tac) != 8:
        return None

    try:
        risposta = requests.post(
            TAC_API_URL,
            json={"query": tac},
            headers={"X-Api-Key": chiave, "User-Agent": C.USER_AGENT},
            timeout=C.HTTP_TIMEOUT,
        )
    except Exception:
        return None
    if getattr(risposta, "status_code", 0) != 200:
        return None
    try:
        dati = risposta.json()
    except Exception:
        return None
    if not isinstance(dati, dict):
        return None

    corpo = dati.get("data") if isinstance(dati.get("data"), dict) else dati
    marca = str(corpo.get("manufacturer") or corpo.get("brand") or "").strip()
    modello = str(corpo.get("model") or "").strip()
    if not marca and not modello:
        return None
    return (marca or "Sconosciuto", modello)


def is_valid_imei(imei: str) -> bool:
    """Controllo Luhn standard sui 15 cifre di un IMEI (solo formato, non
    verifica se è realmente assegnato/attivo)."""
    digits = "".join(ch for ch in (imei or "") if ch.isdigit())
    if len(digits) != 15:
        return False
    total = 0
    for i, ch in enumerate(digits):
        n = int(ch)
        if i % 2 == 1:  # posizioni dispari (0-indexed): raddoppia, 2 cifre -> sommale
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def identify(imei: str) -> tuple[str, str] | None:
    """(brand, specs) dal TAC di un IMEI, o None se non identificabile.

    L'IMEI passato qui non viene salvato né loggato: si usano solo i primi
    8 caratteri (il TAC) per la ricerca nell'indice.
    """
    global _memory_index
    digits = "".join(ch for ch in (imei or "") if ch.isdigit())
    if len(digits) < 8:
        return None
    tac = digits[:8]

    if _memory_index is None:
        _memory_index = _build_index()
    trovato = _memory_index.get(tac)
    if trovato:
        return trovato

    # Solo adesso, e solo se configurato, si chiede fuori: le
    # interrogazioni gratuite sono cento al mese e vanno spese sui
    # codici che i database locali non hanno.
    esterno = cerca_tac_online(tac)
    if esterno:
        _memory_index[tac] = esterno
    return esterno


# Formati di codice modello riconosciuti, dal più specifico al più generico.
# Una singola regex generica non funziona: i produttori usano schemi molto
# diversi fra loro (SM-S928B, XT2347-1, RMX5313, 2312DRA50C…) e un pattern
# unico o non riconosce Samsung o spezza in due il suffisso di Motorola.
_CODE_PATTERNS = [
    re.compile(r"\bSM-[A-Z]\d{3}[A-Z]{0,3}\b"),        # Samsung: SM-S928B
    re.compile(r"\b[A-Z]{3}-[A-Z]{2}\w{1,4}\b"),        # Huawei/Honor: ABR-LX1
    re.compile(r"\bXT\d{4}(?:-\d{1,2})?\b"),            # Motorola: XT2347-1
    # Fino a 8 cifre: il database a volte concatena il codice con l'anno
    # ("RMX53132025" = RMX5313 + 2025), che viene poi separato più sotto.
    re.compile(r"\b(?:RMX|RMP|CPH|PJ[A-Z])\d{3,8}[A-Z]*\b"),  # realme/Oppo/OnePlus
    re.compile(r"\b\d{4,5}[A-Z]{2,4}\d{2,3}[A-Z]{0,2}\b"),    # Xiaomi: 2312DRA50C, 23053RN02A
    re.compile(r"\b[A-Z]{2,4}\d{3,5}[A-Z]{0,3}\b"),     # generico, per ultimo
]
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

# Codice e anno appiccicati senza separatore ("RMX53132025", "23053RN02A2023").
# Si separano solo se ciò che resta è lungo almeno cinque caratteri: così un
# codice che finisce legittimamente con quattro cifre (es. CPH2019) non viene
# spezzato, perché "CPH" da solo sarebbe troppo corto per essere un codice.
_GLUED_YEAR_RE = re.compile(r"\b([A-Z0-9][A-Z0-9-]{4,}?)((?:19|20)\d{2})\b")


def _unglue_year(text: str) -> str:
    return _GLUED_YEAR_RE.sub(r"\1 \2", text or "")


def _split_code_and_year(text: str) -> tuple[str | None, str | None]:
    """Estrae (codice, anno) da una stringa, gestendo il caso in cui il
    database li concatena senza separatore.
    """
    text = _unglue_year(text)
    for pattern in _CODE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        codice = match.group(0)
        anno_match = _YEAR_RE.search(text.replace(codice, " "))
        return codice, (anno_match.group(1) if anno_match else None)
    anno_match = _YEAR_RE.search(text)
    return None, (anno_match.group(1) if anno_match else None)


def parse_specs(brand: str, specs: str) -> dict:
    """Scompone il campo descrittivo grezzo del database TAC in parti utili.

    Il dato di partenza è pensato per essere letto da una macchina, non da
    una persona: arriva in forme come
        "REALME NOTE 70, Realme Chongqing RMX53132025"
    dove il nome è ripetuto, tutto in maiuscolo, e il codice modello è
    attaccato all'anno senza separatore. Mostrarlo così com'è produce righe
    illeggibili come «REALME NOTE 70 (REALME NOTE 70, Realme Chongqing
    RMX53132025)».

    Ritorna un dizionario con: model (nome pulito), maker (produttore, se
    aggiunge informazione), code (codice modello), year (anno), raw.
    """
    grezzo = " ".join(str(specs or "").split())
    parti = [p.strip() for p in grezzo.split(",") if p.strip()]
    nome = parti[0] if parti else grezzo
    coda = " ".join(parti[1:]) if len(parti) > 1 else ""

    codice, anno = _split_code_and_year(coda or grezzo)

    # Produttore: la coda ripulita da codice e anno. Si scarta se ripete il
    # nome o il brand, per non mostrare due volte la stessa informazione.
    produttore = coda
    for pezzo in filter(None, [(codice or "") + (anno or ""), codice, anno]):
        produttore = produttore.replace(pezzo, " ")
    produttore = " ".join(produttore.replace("-", " ").split())
    if produttore and (
        _same_words(produttore, nome) or _same_words(produttore, brand)
        or len(produttore) < 3
    ):
        produttore = ""

    return {
        "model": _best_name(nome, codice),
        "maker": produttore or None,
        "code": codice,
        "year": anno,
        "raw": grezzo,
    }


def _best_name(nome_grezzo: str, codice: str | None) -> str:
    """Nome commerciale con le maiuscole giuste.

    Il database TAC fornisce i nomi TUTTI IN MAIUSCOLO ("HONOR X8C"), e la
    forma originale è persa: rimetterle a posto per euristica è un tiro a
    indovinare che sbaglia sulle convenzioni dei produttori (Honor scrive
    "X8c" minuscolo, Samsung "S24 FE" maiuscolo). Se però conosciamo il
    codice modello, il nome corretto è già disponibile nei dataset
    ufficiali: si usa quello, e si ricade sull'euristica solo se manca.
    """
    if codice:
        try:
            from . import modelcodes

            ufficiali = modelcodes.resolve(codice)
        except Exception:
            ufficiali = []
        for candidato in ufficiali:
            # Si accetta solo se descrive lo stesso dispositivo, per non
            # sostituire il nome con quello di un modello diverso.
            if _same_words(candidato, nome_grezzo):
                return " ".join(candidato.split())
    return prettify_model(nome_grezzo)


def _same_words(a: str, b: str) -> bool:
    normalizza = lambda t: set(re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).split())  # noqa: E731
    parole_a, parole_b = normalizza(a), normalizza(b)
    return bool(parole_a) and (parole_a <= parole_b or parole_b <= parole_a)


def prettify_model(name: str) -> str:
    """Rende leggibile un nome che il database fornisce in maiuscolo.

    Delega a `extract.canonical_device`, che conosce già le convenzioni dei
    produttori (realme minuscolo, iPhone con la i minuscola, POCO tutto
    maiuscolo…): senza questo un "REALME NOTE 70" resterebbe urlato.
    """
    from . import extract

    return extract.canonical_device(" ".join(str(name or "").split()))


def describe(brand: str, specs: str) -> str:
    """Riga leggibile per la scheda dispositivo: nome, e fra parentesi solo
    le informazioni che aggiungono qualcosa (codice, anno, produttore)."""
    parsed = parse_specs(brand, specs)
    extra = [x for x in (parsed["code"], parsed["year"], parsed["maker"]) if x]
    return f"{parsed['model']} ({', '.join(extra)})" if extra else parsed["model"]


def reset_cache() -> None:
    global _memory_index, _status
    _memory_index = None
    _status = "non ancora caricato"
