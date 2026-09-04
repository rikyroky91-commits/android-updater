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
import gzip
import io
import json
import os
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

# `openpyxl` SI IMPORTA SOLO SE SERVE DAVVERO, e non serve quasi mai.
#
# Misurato il 31/08/2026 su questa immagine: importarlo costa **26 MB di
# RAM**, il 5% dei 512 MB del servizio, spesi a ogni avvio per una libreria
# che serve in un ramo di ripiego — il foglio di calcolo, che si legge
# soltanto se il CSV della base dati sparisse. Un caso mai capitato,
# pagato a ogni avvio.
def _openpyxl():
    """La libreria del foglio di calcolo, importata al primo uso."""
    try:
        import openpyxl
    except ImportError:  # pragma: no cover
        return None
    return openpyxl


from . import config as C
from . import storage

# LA STESSA BASE DATI, IN CSV INVECE CHE IN XLSX.
#
# Il repository pubblica entrambi i formati dallo stesso commit, quindi i
# dati sono identici — 248 359 TAC, misurati. Cambia quanto pesano in
# archivio: un `.xlsx` è già un archivio compresso, quindi dentro
# `tracker.db` occupava **13,5 MB** anche dopo la compressione, mentre il
# CSV scende a 2,6. E `tracker.db` viene caricato su un Gist ogni mezz'ora
# e committato ogni ora.
#
# In più toglie `openpyxl` dal percorso critico: una dipendenza in meno fra
# l'app e la sua capacità di riconoscere un telefono.
TAC_DB_URL = "https://raw.githubusercontent.com/MoazEb/tac-database/main/tac_full.csv"
# Stesso dato in formato foglio di calcolo. Resta come ripiego perché il
# codice per leggerlo esiste già ed è collaudato: se un giorno il CSV
# sparisse, l'app continuerebbe a riconoscere i telefoni.
TAC_DB_XLSX_URL = "https://raw.githubusercontent.com/MoazEb/tac-database/main/tac_full.xlsx"

# ALTRE BASI DATI, e perché sono più d'una.
#
# Nessun database TAC pubblico è completo: sono tutti alimentati dalla
# community e ognuno ha buchi diversi. Un IMEI valido che «non esiste»
# mentre altri siti lo riconoscono è quasi sempre un buco di copertura,
# non un IMEI sbagliato.
#
# Quanto aggiungono davvero, misurato il 2026-08-09 e non stimato:
#   MoazEb    248 359 TAC
#   IMEIDB     27 827 TAC, di cui  626 nuovi
#   Osmocom    22 524 TAC, di cui   97 nuovi
#                        ─────────────────
#   insieme   249 028 TAC  (+0,27 %)
#
# È poco, ed è un dato utile di per sé: aggiungere basi dati gratuite non
# chiude il buco. Per questo il confronto con i siti esterni è SEMPRE
# disponibile, non solo quando la ricerca fallisce.
TAC_DB_FALLBACK_URL = "http://tacdb.osmocom.org/export/tacdb.csv"
TAC_DB_IMEIDB_URL = "https://raw.githubusercontent.com/VTSTech/IMEIDB/master/imeidb.csv"
_META_FALLBACK_BYTES = "imei_tacdb2_bytes"
_META_FALLBACK_FETCHED = "imei_tacdb2_fetched_at"
_META_IMEIDB_BYTES = "imei_imeidb_bytes"
_META_IMEIDB_FETCHED = "imei_imeidb_fetched_at"
_META_BYTES_KEY = "imei_tacdb_bytes"
_META_FETCHED_KEY = "imei_tacdb_fetched_at"
_META_XLSX_BYTES = "imei_tacdb_xlsx_bytes"
_META_XLSX_FETCHED = "imei_tacdb_xlsx_fetched_at"
_REFRESH_HOURS = 24 * 14  # database molto stabile, un refresh ogni due settimane basta

# Etichette delle fonti, in ordine di precedenza. L'ordine È la regola: chi
# viene prima vince quando due fonti dicono cose diverse sullo stesso TAC.
FONTE_UTENTE = "inserito da te"
FONTE_CURATA = "verificato a mano"
FONTE_PRINCIPALE = "MoazEb/tac-database"
FONTE_IMEIDB = "VTSTech/IMEIDB"
FONTE_OSMOCOM = "Osmocom TAC db"
FONTE_ESTERNA = "servizio esterno"

# tac -> [(fonte, marca, specs), ...] in ordine di precedenza.
#
# Prima era `tac -> (marca, specs)`: le fonti venivano fuse e il
# disaccordo spariva. Ma è proprio il disaccordo il dato che serve — «lo
# stesso IMEI dà un modello su un sito e un altro modello su un altro» è
# la ragione per cui esiste il confronto. Conservare l'elenco costa memoria
# solo per i TAC che più fonti conoscono.
#
# In archivio ogni TAC tiene le sue risposte in UNA stringa sola: le tre
# parti di una risposta separate da `_CAMPO`, le risposte fra loro da
# `_VOCE`. Sono i due caratteri di controllo che ASCII dedica esattamente a
# questo (0x1F «unit separator», 0x1E «record separator») e non compaiono
# in nessun catalogo di telefoni. Il perché sta nel commento sopra
# `_flusso_di_testo`: la forma «dizionario di liste di tuple» costava 45
# volte il testo che conteneva.
_CAMPO = "\x1f"
_VOCE = "\x1e"
_memory_index: dict[str, str] | None = None
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
    in_cache = storage.get_blob(_META_BYTES_KEY)
    if in_cache and fetched_at:
        try:
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
        except ValueError:
            age_h = _REFRESH_HOURS + 1
        if age_h < _REFRESH_HOURS:
            return in_cache

    fresh = _download()
    if fresh:
        storage.set_blob(_META_BYTES_KEY, fresh)
        storage.set_meta(_META_FETCHED_KEY, datetime.now(timezone.utc).isoformat())
        return fresh
    if in_cache:
        return in_cache
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


def _cached_bytes_url(url: str, chiave_byte: str, chiave_data: str,
                      minimo: int = 10_000) -> bytes | None:
    """Come `_cached_bytes` ma per un URL qualsiasi."""
    fetched_at = storage.get_meta(chiave_data)
    in_cache = storage.get_blob(chiave_byte)
    if in_cache and fetched_at:
        try:
            eta = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
        except ValueError:
            eta = _REFRESH_HOURS + 1
        if eta < _REFRESH_HOURS:
            return in_cache

    fresco = _scarica_url(url, minimo)
    if fresco:
        storage.set_blob(chiave_byte, fresco)
        storage.set_meta(chiave_data, datetime.now(timezone.utc).isoformat())
        return fresco
    if in_cache:
        return in_cache
    return None


CARTELLA_DATI = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FILE_TAC_CURATO = os.path.join(CARTELLA_DATI, "tac_modelli.csv")


def carica_tac_curati(testo: str) -> dict[str, tuple[str, str]]:
    """TAC verificati a mano. Le righe che iniziano con `#` sono commenti."""
    righe = [r for r in (testo or "").splitlines() if not r.lstrip().startswith("#")]
    indice: dict[str, tuple[str, str]] = {}
    for riga in csv.DictReader(io.StringIO("\n".join(righe))):
        tac = _tac_normalizzato(riga.get("tac"))
        marca = (riga.get("marca") or "").strip()
        modello = (riga.get("modello") or "").strip()
        if tac and (marca or modello):
            indice[tac] = (marca or "Sconosciuto", modello)
    return indice


# ======================================================================
# TAC inseriti dall'utente dentro l'app
# ======================================================================
# Perché non basta il CSV. Il file nel repository è la forma definitiva —
# sopravvive ai riavvii e si porta dietro la cronologia — ma richiede di
# uscire dall'app, aprire un editor e ricaricare il progetto. Chi sta
# controllando un telefono in quel momento non lo fa, e il dato si perde.
#
# Quindi: si salva subito nell'archivio, dove vale immediatamente, e
# l'app mostra comunque la riga da incollare nel CSV per renderlo
# permanente. Le due strade non si escludono, si completano.
_META_TAC_UTENTE = "imei_tac_inseriti"
#: Le risposte già pagate al servizio esterno. Tenute SEPARATE da quelle
#: inserite a mano: le prime sono un acquisto, le seconde una verifica di
#: una persona, e mescolarle farebbe sparire la differenza proprio nella
#: tabella che il sito mostra per dire da dove viene una risposta.
_META_TAC_ESTERNI = "imei_tac_esterni"
#: I TAC che il servizio esterno ha dichiarato di NON conoscere.
#:
#: Serve a due cose diverse, e nessuna delle due è un dettaglio.
#: La prima e' il denaro: senza questa memoria un TAC ignoto veniva
#: richiesto — e pagato — a ogni singola visita, e il piano gratuito e'
#: di cento interrogazioni al mese. La seconda e' la rotellina: la pagina
#: decide di aspettare («cerco fuori») guardando se la risposta e' gia'
#: in casa, e una risposta negativa che non viene conservata non e' mai
#: in casa — quindi la pagina aspettava, ricaricava, aspettava di nuovo,
#: all'infinito. Segnalato dall'utente il 26/08/2026 con l'IMEI del TAC
#: 35286149, che nessun database — locale o esterno — conosce.
#:
#: A differenza di una risposta positiva, questa SCADE: un TAC assente
#: oggi puo' essere aggiunto al database del fornitore fra un mese
#: (succede di continuo con i modelli appena usciti). Un no per sempre
#: renderebbe l'app cieca proprio sui telefoni nuovi, che sono quelli
#: che interessano.
_META_TAC_ASSENTI = "imei_tac_assenti"
#: Per quanto tempo si crede a un «non lo conosco» prima di richiederlo.
GIORNI_VALIDITA_TAC_ASSENTE = 30

# I siti dove verificare un TAC a mano. Nessuno di questi viene
# interrogato dall'app: bloccano l'accesso automatico o lo vietano nei
# termini d'uso. Consultarli di persona è invece del tutto lecito, ed è
# esattamente ciò che questi collegamenti permettono.
#
# Sono più d'uno di proposito: hanno cataloghi diversi, e un TAC assente
# da uno si trova spesso nell'altro. Il primo non richiede nemmeno
# registrazione.
SITI_VERIFICA_TAC = [
    ("imei.info", "https://www.imei.info/it/?imei={imei}",
     "catalogo ampio; IMEI gia' precompilato"),
    ("HiCellTek", "https://hicelltek.com/en/tac-lookup/",
     "catalogo TAC; l'IMEI viene copiato prima di aprire il sito"),
    ("IMEIpro", "https://www.imeipro.info/",
     "controllo blacklist; l'IMEI viene copiato prima di aprire il sito"),
    ("IMEI Check", "https://imeicheck.com/imei-check",
     "identita', blacklist e SIM lock; l'IMEI viene copiato prima di aprire il sito"),
    ("nobbi.com", "http://www.nobbi.com/tacquery.php",
     "storico, utile per i modelli vecchi; l'IMEI viene copiato prima di aprire il sito"),
    ("IMEI DB", "https://imeidb.xyz/",
     "aggiornato di frequente; l'IMEI viene copiato prima di aprire il sito"),
]


def link_verifica(imei: str) -> list[tuple[str, str, str]]:
    """`(nome, url, nota)` dei siti dove controllare un TAC a mano."""
    pulito = "".join(c for c in (imei or "") if c.isdigit())
    return [(nome, url.format(imei=pulito), nota)
            for nome, url, nota in SITI_VERIFICA_TAC]


def tac_inseriti() -> dict[str, tuple[str, str]]:
    """I TAC salvati dall'utente dentro l'app."""
    grezzo = storage.get_meta(_META_TAC_UTENTE)
    if not grezzo:
        return {}
    try:
        dati = json.loads(grezzo) if isinstance(grezzo, str) else grezzo
    except Exception:
        return {}
    if not isinstance(dati, dict):
        return {}
    voci = {}
    for tac, valore in dati.items():
        if isinstance(valore, (list, tuple)) and len(valore) == 2:
            voci[str(tac)] = (str(valore[0]), str(valore[1]))
    return voci


def tac_esterni() -> dict[str, tuple[str, str]]:
    """Le risposte già ottenute dal servizio esterno, e già pagate."""
    grezzo = storage.get_meta(_META_TAC_ESTERNI)
    if not grezzo:
        return {}
    try:
        dati = json.loads(grezzo) if isinstance(grezzo, str) else grezzo
    except Exception:
        return {}
    if not isinstance(dati, dict):
        return {}
    return {str(t): (str(v[0]), str(v[1])) for t, v in dati.items()
            if isinstance(v, (list, tuple)) and len(v) == 2}


def _ricorda_tac_esterno(tac: str, marca: str, modello: str) -> None:
    """Conserva una risposta comprata, perché non si compri due volte.

    Il piano gratuito è di cento interrogazioni al mese e la risposta
    finiva nel solo indice in memoria: su Render il processo riparte a
    ogni deploy e dopo ogni sonno, quindi lo stesso TAC sarebbe stato
    richiesto — e pagato — di nuovo. Con un archivio che viene salvato su
    Gist, invece, una risposta vale per sempre.

    I dati TAC non invecchiano: un codice assegnato a un modello resta
    quel modello. Non serve nessuna scadenza.
    """
    tac = "".join(c for c in (tac or "") if c.isdigit())[:8]
    if len(tac) != 8:
        return
    voci = tac_esterni()
    voci[tac] = (marca or "", modello or "")
    try:
        storage.set_meta(_META_TAC_ESTERNI, json.dumps(voci, ensure_ascii=False))
    except Exception:      # un archivio non scrivibile non deve far fallire una ricerca
        pass


def tac_assenti() -> dict[str, str]:
    """I TAC gia' chiesti fuori che il servizio ha dichiarato di non avere.

    Chiave il TAC, valore la data ISO della domanda: serve a sapere
    quando quel «no» diventa vecchio abbastanza da valere la pena
    richiederlo.
    """
    grezzo = storage.get_meta(_META_TAC_ASSENTI)
    if not grezzo:
        return {}
    try:
        dati = json.loads(grezzo) if isinstance(grezzo, str) else grezzo
    except Exception:
        return {}
    if not isinstance(dati, dict):
        return {}
    return {str(t): str(v) for t, v in dati.items() if v}


def _ricorda_tac_assente(tac: str) -> None:
    """Segna che questo TAC e' stato chiesto fuori e la risposta e' stata no.

    Si scrive SOLO su un no esplicito del servizio. Una chiamata fallita
    — rete giu', chiave scaduta, risposta illeggibile — non e' un no: e'
    un non-lo-so, e conservarlo come no significherebbe rendere ignoto
    per un mese un telefono che il servizio conosce benissimo.
    """
    tac = "".join(c for c in (tac or "") if c.isdigit())[:8]
    if len(tac) != 8:
        return
    voci = tac_assenti()
    voci[tac] = datetime.now(timezone.utc).isoformat()
    try:
        storage.set_meta(_META_TAC_ASSENTI, json.dumps(voci, ensure_ascii=False))
    except Exception:      # un archivio non scrivibile non deve far fallire una ricerca
        pass


def tac_gia_chiesto_invano(tac: str) -> bool:
    """True se il servizio esterno ha gia' detto di non conoscere questo TAC,
    abbastanza di recente da non valere la pena richiederlo."""
    tac = "".join(c for c in (tac or "") if c.isdigit())[:8]
    quando = tac_assenti().get(tac)
    if not quando:
        return False
    try:
        chiesto = datetime.fromisoformat(quando)
    except Exception:
        return False
    if chiesto.tzinfo is None:
        chiesto = chiesto.replace(tzinfo=timezone.utc)
    eta = (datetime.now(timezone.utc) - chiesto).days
    return eta < GIORNI_VALIDITA_TAC_ASSENTE


def dimentica_tac_assente(tac: str) -> None:
    """Toglie il «no» conservato, cosi' la prossima ricerca richiede davvero.

    La usa la pagina quando qualcuno chiede esplicitamente di riprovare:
    un mese e' la scadenza giusta per l'automatismo, ma chi ha appena
    letto altrove che telefono e' non deve aspettarlo.
    """
    tac = "".join(c for c in (tac or "") if c.isdigit())[:8]
    voci = tac_assenti()
    if voci.pop(tac, None) is None:
        return
    try:
        storage.set_meta(_META_TAC_ASSENTI, json.dumps(voci, ensure_ascii=False))
    except Exception:
        pass


def aggiungi_tac(tac: str, marca: str, modello: str) -> bool:
    """Salva un TAC verificato a mano. False se i dati non bastano.

    Non c'è nessuna validazione del *contenuto*: se qualcuno scrive un
    modello sbagliato, l'app lo mostrerà. È accettabile perché è un dato
    inserito deliberatamente da chi lo sta verificando in quel momento —
    ed è comunque meglio di un dato inventato da un'euristica.
    """
    tac = "".join(c for c in (tac or "") if c.isdigit())[:8]
    marca = (marca or "").strip()
    modello = (modello or "").strip()
    if len(tac) != 8 or not (marca or modello):
        return False

    voci = tac_inseriti()
    voci[tac] = (marca or "Sconosciuto", modello)
    storage.set_meta(_META_TAC_UTENTE, json.dumps(voci, ensure_ascii=False))
    reset_cache()
    return True


def rimuovi_tac(tac: str) -> bool:
    voci = tac_inseriti()
    if tac not in voci:
        return False
    del voci[tac]
    storage.set_meta(_META_TAC_UTENTE, json.dumps(voci, ensure_ascii=False))
    reset_cache()
    return True


def riga_csv(tac: str, marca: str = "Marca", modello: str = "Nome del modello") -> str:
    """La riga da incollare in `data/tac_modelli.csv` per renderlo permanente."""
    return f"{tac},{marca},{modello},verificato a mano"


def _indice_curato() -> dict[str, tuple[str, str]]:
    try:
        with open(FILE_TAC_CURATO, encoding="utf-8-sig") as f:
            return carica_tac_curati(f.read())
    except OSError:
        return {}


def _leggi_workbook(workbook, index: dict) -> None:
    """Righe valide del file scaricato dentro l'indice."""
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
            tac = _tac_normalizzato(row[i_tac])
            brand = str(row[i_brand] or "").strip()
            specs = str(row[i_specs] or "").strip()
            if tac and brand:
                index[tac] = (brand, specs)


def _voci_principali():
    """La base dati principale in flusso, senza dizionario intermedio.

    Stesso ordine di ripieghi di sempre — CSV, foglio di calcolo, copia
    nel repository — e stessi messaggi di stato: questa funzione ha preso
    il posto di `_indice_principale`, che faceva le stesse tre prove per
    consegnare un dizionario. Tenerle tutte e due avrebbe voluto dire due
    copie della stessa catena di ripieghi, che prima o poi smettono di
    somigliarsi.

    La differenza è che il caso normale — il CSV — non costruisce mai un
    dizionario di 248.000 voci per poi ricopiarlo nell'indice.
    """
    global _status
    grezzo = _cached_bytes()
    if grezzo and grezzo[:4] != _MAGIA_XLSX:
        flusso = _flusso_di_testo(grezzo)
        vuoto = True
        try:
            for voce in _righe_principali(flusso):
                vuoto = False
                yield voce
        except csv.Error:
            pass
        if not vuoto:
            return
    # Da qui in giù sono i ripieghi rari: lì il dizionario intermedio non
    # è un problema, perché o il file è piccolo (l'istantanea) o la
    # libreria del foglio di calcolo lo costruisce comunque.
    indice = _leggi_base_principale(grezzo)
    if not indice:
        indice = _leggi_base_principale(
            _cached_bytes_url(TAC_DB_XLSX_URL, _META_XLSX_BYTES, _META_XLSX_FETCHED))
        if indice:
            _status += " (dal foglio di calcolo, il CSV non era disponibile)"
    if not indice:
        indice = _istantanea_locale()
        if indice:
            _status += (f" — nessuna fonte in rete disponibile, si usa la copia "
                        f"nel repository ({len(indice)} TAC)")
    for tac, (marca, specs) in indice.items():
        yield tac, marca, specs


def _voci_imeidb():
    """La terza base dati in flusso.

    Misurata prima di essere adottata: 27.827 TAC, di cui 626 assenti
    dalla base principale. Poco — ma sono 626 telefoni che prima non si
    riconoscevano, per 1,1 MB.
    """
    grezzo = _cached_bytes_url(TAC_DB_IMEIDB_URL, _META_IMEIDB_BYTES,
                               _META_IMEIDB_FETCHED, minimo=100_000)
    flusso = _flusso_di_testo(grezzo)
    if flusso is None:
        return
    yield from _righe_imeidb(flusso)


def _voci_storiche():
    """La base dati storica in flusso (vedi `_indice_fallback`)."""
    grezzo = _cached_bytes_url(TAC_DB_FALLBACK_URL, _META_FALLBACK_BYTES,
                               _META_FALLBACK_FETCHED)
    flusso = _flusso_di_testo(grezzo)
    if flusso is None:
        return
    yield from _righe_osmocom(flusso)


def _istantanea_locale() -> dict[str, tuple[str, str]]:
    """La copia del database TAC conservata dentro il repository."""
    percorso = os.path.join(CARTELLA_DATI, "tac_era_android.csv.gz")
    try:
        with gzip.open(percorso, "rt", encoding="utf-8", errors="replace") as f:
            return _leggi_csv_tac(f.read())
    except FileNotFoundError:
        return {}
    except Exception:  # un file corrotto non deve impedire l'avvio
        return {}


# `PK\x03\x04` è l'inizio di ogni archivio zip, e un `.xlsx` è uno zip.
_MAGIA_XLSX = b"PK\x03\x04"


def _leggi_base_principale(grezzo: bytes | None) -> dict[str, tuple[str, str]]:
    """Interpreta la base dati principale riconoscendo il formato dai byte.

    IL FORMATO SI GUARDA, NON SI PRESUME. Il repository pubblica lo stesso
    dato in CSV e in xlsx, e l'app è passata dall'uno all'altro: decidere in
    base all'URL avrebbe significato che un file servito nel formato
    «sbagliato» — o una prova che ne inietta uno diverso — viene letto come
    se fosse l'altro, producendo zero righe senza nessun errore. I primi
    quattro byte lo dicono con certezza.
    """
    if not grezzo:
        return {}
    if grezzo[:4] == _MAGIA_XLSX:
        modulo = _openpyxl()
        if modulo is None:  # pragma: no cover
            return {}
        try:
            workbook = modulo.load_workbook(io.BytesIO(grezzo), read_only=True,
                                            data_only=True)
        except Exception as exc:
            globals()["_status"] = f"file scaricato ma non interpretabile: {exc}"
            return {}
        indice: dict[str, tuple[str, str]] = {}
        _leggi_workbook(workbook, indice)
        workbook.close()
        return indice
    return _leggi_csv_tac(grezzo.decode("utf-8", "replace"))


def _leggi_csv_tac(testo: str) -> dict[str, tuple[str, str]]:
    """`Brand,TAC,SPECS` — la forma del CSV della base dati principale."""
    try:
        return {tac: (marca, specs)
                for tac, marca, specs in _righe_principali(io.StringIO(testo or ""))}
    except csv.Error:
        return {}


# ======================================================================
# I CSV SI LEGGONO UNA RIGA ALLA VOLTA, NON TUTTI INSIEME
# ======================================================================
# Segnalato dall'utente il 31/08/2026: «il sito continua a crashare
# continuamente per saturamento della memoria». Misurato qui, sul
# database vero:
#
#     lettura dei byte dall'archivio      +19 MB
#     `.decode()` del testo intero        +11 MB
#     dizionario delle 248.359 righe      +50 MB, con un PICCO di +106
#     indice finale (liste di tuple)      +47 MB
#     ---------------------------------------------------------------
#     in tutto                            165 MB stabili, 217 di picco
#
# Su un servizio da 512 MB, con gli altri cataloghi e il thread di
# scansione nello stesso processo, quel picco è la morte per OOM — e si
# ripete a ogni avvio, perché l'indice si ricostruisce da capo.
#
# E il dato utile, misurato, sono **3,6 MB**: tutto il resto è la forma in
# cui lo si teneva. Un dizionario di liste di tuple di stringhe paga
# quattro oggetti Python per ogni risposta di ogni fonte, e ognuno costa
# più del testo che contiene.
#
# Da qui in poi: le righe si leggono in flusso (mai il testo intero in
# memoria, mai il dizionario intermedio) e finiscono in una stringa sola
# per TAC, che si srotola al momento della lettura — cioè per il singolo
# TAC cercato, non per i 77.000 che non interessano a nessuno.
def _flusso_di_testo(grezzo: bytes | None):
    """I byte scaricati letti come testo, senza copiarli tutti in memoria."""
    if not grezzo:
        return None
    return io.TextIOWrapper(io.BytesIO(grezzo), encoding="utf-8",
                            errors="replace", newline="")


# ======================================================================
# LO ZERO INIZIALE CHE IL FOGLIO DI CALCOLO SI MANGIA
# ======================================================================
# Misurato il 04/09/2026 sulla base principale scaricata: **6 344 righe su
# 254 996** hanno il TAC di SETTE cifre invece che di otto, e finivano
# tutte nel cestino perché il filtro chiedeva `len(tac) == 8`. Non sono
# righe rotte: sono i TAC che cominciano per zero — `01620200` (TCL Flip 2,
# 2024), `01307500` (Galaxy S2 HD LTE) — passati per un foglio di calcolo
# che ha letto la colonna come un numero e ha buttato via lo zero davanti.
#
# Lo zero si può rimettere senza inventare niente, ed è l'unica cifra
# possibile: le prime due cifre di un TAC sono l'ente che l'ha assegnato
# (il Reporting Body Identifier) e `01` è il PTCRB, cioè le assegnazioni
# nordamericane. Un TAC di sette cifre non è ambiguo — o è `0` + quelle
# sette, o non è un TAC.
#
# Quelle di SEI cifre invece si buttano, e non è un'incoerenza: sono 277
# righe che dicono tutte `NOKIA THIS IS A TEST IMEI TO BE USED`, e `00`
# non è un ente che assegna niente.
#
# Guadagno misurato: da 248 373 a 254 703 TAC distinti (+2,5 %).
def _tac_normalizzato(valore) -> str | None:
    """Le otto cifre di un TAC, o None se questa riga non ne contiene uno."""
    tac = str(valore if valore is not None else "").strip()
    if not tac.isdigit():
        return None
    if len(tac) == 7:
        return "0" + tac
    return tac if len(tac) == 8 else None


def _righe_principali(flusso):
    """`Brand,TAC,SPECS`, una riga alla volta: (tac, marca, specs)."""
    lettore = csv.reader(flusso)
    intestazione = next(lettore, None)
    if not intestazione:
        return
    posti = {str(nome or "").strip().lower(): i
             for i, nome in enumerate(intestazione)}
    i_tac, i_marca, i_specs = posti.get("tac"), posti.get("brand"), posti.get("specs")
    if i_tac is None or i_marca is None:
        return
    ultimo = max(i_tac, i_marca, i_specs if i_specs is not None else 0)
    for riga in lettore:
        if len(riga) <= ultimo:
            continue
        tac = _tac_normalizzato(riga[i_tac])
        marca = (riga[i_marca] or "").strip()
        if tac and marca:
            specs = (riga[i_specs] or "").strip() if i_specs is not None else ""
            yield tac, marca, specs


def _righe_imeidb(flusso):
    """`TAC,marca,modello,…` senza intestazione: colonne per posizione."""
    for riga in csv.reader(flusso):
        if len(riga) < 3:
            continue
        tac = _tac_normalizzato(riga[0])
        marca = str(riga[1] or "").strip()
        if tac and marca:
            yield tac, marca, str(riga[2] or "").strip()


def _righe_osmocom(flusso):
    """Come `_righe_imeidb`, ma saltando la riga di copyright iniziale.

    L'intestazione vera è la SECONDA riga del file (vedi
    `carica_tac_osmocom`): la si cerca fra le prime dieci e si legge da lì
    in avanti. Il flusso resta posizionato dopo l'intestazione, quindi non
    serve saltarla di nuovo.
    """
    for _ in range(10):
        riga = flusso.readline()
        if not riga:
            return
        if riga.lower().replace(" ", "").startswith("tac,"):
            break
    else:
        return
    yield from _righe_imeidb(flusso)


def _dell_era_android(specs: str) -> bool:
    """Se questa voce del database TAC merita di stare in RAM.

    Il criterio è dichiarato in `C.TAC_ANNO_MINIMO` (2017, Android 8) e
    ammorbidito dal codice modello: la maggioranza delle voci non dichiara
    nessun anno, e buttarle tutte significherebbe perdere anche telefoni
    recenti. Chi ha un codice resta, perché è il codice a rendere
    possibile una scheda tecnica; chi non ha né anno né codice non è
    comunque qualcosa a cui questa app sappia rispondere.
    """
    codice, anno = _split_code_and_year(_unglue_year(" ".join((specs or "").split())))
    if codice:
        return True
    if anno is None:
        # L'ANNO PUÒ ESSERE ATTACCATO A UNA PAROLA CORTA, e per due mesi
        # questo ha buttato via i telefoni più nuovi di tutti.
        #
        # Segnalato dall'utente il 31/08/2026 con l'IMEI 865587084948173:
        # la base dati lo conosce benissimo — `HONOR,86558708,"HONOR 400
        # PRO, N/A2025"` — e la pagina rispondeva «modello sconosciuto».
        # Quando il dataset non ha un codice modello scrive `N/A` e ci
        # attacca l'anno; `_unglue_year` però separa l'anno solo se
        # davanti ha almeno cinque caratteri (regola giusta, serve a non
        # spezzare `CPH2019` in `CPH 2019`), e `N/A` ne ha tre. Nessun
        # codice, nessun anno visto: fuori dall'indice.
        #
        # Colpiva esattamente i modelli appena usciti — HONOR 400 Pro,
        # REDMI 15, REDMI A5, Pixel 7a, i Tecno — cioè quelli per cui il
        # dataset non ha ancora il codice. 1.810 righe recuperate,
        # misurate sul file vero.
        #
        # La regola larga sta QUI e non dentro `_unglue_year`: lì
        # servirebbe a estrarre un codice, e spezzare `CPH2019` sarebbe un
        # danno vero. Qui si arriva solo dopo che nessun codice è stato
        # riconosciuto, e la domanda è più modesta: «questa riga dichiara
        # un anno da qualche parte?».
        anno = _anno_appiccicato(specs)
    try:
        return anno is not None and int(anno) >= C.TAC_ANNO_MINIMO
    except (TypeError, ValueError):
        return False


# Un anno in fondo a una parola, qualunque lunghezza abbia la parola:
# «N/A2025», «Pixel 7a2023», «KG5p2022». Deve chiudere la parola — così
# «BD202403» non diventa il 2024 — e non si applica mai a una riga in cui
# un codice modello è già stato riconosciuto (vedi `_dell_era_android`).
_ANNO_APPICCICATO_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9/\-]*?((?:19|20)\d{2})(?![0-9A-Za-z])")


def _anno_appiccicato(specs: str) -> str | None:
    trovato = _ANNO_APPICCICATO_RE.search(" ".join((specs or "").split()))
    return trovato.group(1) if trovato else None


def _build_index() -> dict[str, list[tuple[str, str, str]]]:
    """Indice completo dei TAC: per ogni TAC, TUTTE le risposte trovate.

    ATTENZIONE ALL'ORDINE DELLE USCITE ANTICIPATE. Prima, se il database
    scaricato non era disponibile, questa funzione usciva subito — e con
    lei sparivano anche la tabella verificata a mano e i TAC inseriti
    dentro l'app, che non c'entrano niente col download. Bastava un'ora
    senza rete perché l'app dimenticasse dati che aveva in casa.

    Ora le fonti locali si aggiungono SEMPRE, qualunque cosa faccia il
    download.

    **E NESSUNA RISPOSTA VIENE PIÙ BUTTATA.** Prima le fonti venivano fuse
    in un dizionario solo: chi arrivava dopo perdeva, e il disaccordo
    spariva senza lasciare traccia. Ma è proprio il disaccordo il dato che
    serve a chi controlla un IMEI — «questo numero dà un modello su un sito
    e un altro modello su un altro» è la situazione normale, non
    l'eccezione. L'ordine di questo elenco resta la precedenza: chi è primo
    è la risposta dell'app, gli altri sono il confronto.

    IL VALORE È UNA STRINGA SOLA, NON UNA LISTA DI TUPLE. Le risposte di un
    TAC stanno una dietro l'altra separate da caratteri di controllo, e si
    srotolano in `_voci_per_tac` — cioè per il TAC che qualcuno ha cercato,
    non per i 77.000 che nessuno cercherà. Vedi il commento lungo sopra
    `_flusso_di_testo` per i numeri: è la differenza fra 165 MB e 89.

    ANCHE L'ORDINAMENTO PER AFFIDABILITÀ È RIMANDATO ALLA LETTURA. Il
    punteggio di una risposta dipende SOLO dalle altre risposte dello
    stesso TAC (vedi `_punteggio_affidabilita`), quindi calcolarlo per
    tutti all'avvio dava lo stesso risultato di calcolarlo per quello
    cercato — pagando all'avvio, ogni avvio, 77.000 ordinamenti e altrettanti
    insiemi di parole che nessuno guardava.
    """
    global _status
    index: dict[str, str] = {}

    scartati = 0
    conteggi: dict[str, int] = {}
    nuovi: dict[str, int] = {}

    def aggiungi(fonte: str, voci, filtrabile: bool = True) -> None:
        nonlocal scartati
        taglia = filtrabile and C.TAC_SOLO_ERA_ANDROID
        quante = 0
        inediti = 0
        for tac, marca, specs in voci:
            # LE CORREZIONI UMANE NON SI FILTRANO MAI. Se qualcuno ha
            # inserito un TAC a mano, o è stato verificato nel repository,
            # quel dato è lì apposta: nessun criterio automatico può
            # decidere che non serviva.
            gia_noto = tac in index
            if taglia and not gia_noto and not _dell_era_android(specs):
                scartati += 1
                continue
            quante += 1
            if not gia_noto:
                inediti += 1
            voce = fonte + _CAMPO + marca + _CAMPO + specs
            precedente = index.get(tac)
            index[tac] = precedente + _VOCE + voce if precedente else voce
        conteggi[fonte] = quante
        nuovi[fonte] = inediti

    def coppie(dizionario) -> list[tuple[str, str, str]]:
        return [(tac, marca, specs)
                for tac, (marca, specs) in dizionario.items()]

    # L'ordine delle chiamate È l'ordine di precedenza.
    inseriti = tac_inseriti()
    curati = _indice_curato()

    aggiungi(FONTE_UTENTE, coppie(inseriti), filtrabile=False)
    aggiungi(FONTE_CURATA, coppie(curati), filtrabile=False)
    # Le risposte comprate al servizio esterno stanno sotto le verifiche
    # umane e sopra i database scaricati: sono puntuali e recenti, ma
    # restano di una fonte automatica. Non si filtrano per età — si sono
    # pagate proprio perché nessun altro conosceva quel TAC.
    aggiungi(FONTE_ESTERNA, coppie(tac_esterni()), filtrabile=False)
    # LE TRE BASI DATI SI LEGGONO UNA ALLA VOLTA, IN FLUSSO. Prima si
    # costruivano tutti e tre i dizionari e poi si copiavano nell'indice:
    # per un attimo la stessa informazione stava in memoria due volte, ed è
    # quell'attimo che faceva toccare i 217 MB di picco.
    aggiungi(FONTE_PRINCIPALE, _voci_principali())
    aggiungi(FONTE_IMEIDB, _voci_imeidb())
    aggiungi(FONTE_OSMOCOM, _voci_storiche())

    if not index:
        _status = "file interpretato ma nessuna riga valida trovata (formato cambiato?)"
    else:
        _status += f" — {len(index)} codici TAC indicizzati"
        # I conteggi sono ora le righe DAVVERO indicizzate, non la
        # dimensione del file: prima si dichiarava «base principale
        # 248359» e poi se ne tenevano 76737, e i due numeri sulla stessa
        # pagina non tornavano.
        _status += f" · base principale {conteggi.get(FONTE_PRINCIPALE, 0)}"
        if conteggi.get(FONTE_IMEIDB):
            _status += (f" · IMEIDB {conteggi[FONTE_IMEIDB]}"
                        f" (+{nuovi.get(FONTE_IMEIDB, 0)} nuovi)")
        if conteggi.get(FONTE_OSMOCOM):
            _status += (f" · storica {conteggi[FONTE_OSMOCOM]}"
                        f" (+{nuovi.get(FONTE_OSMOCOM, 0)} nuovi)")
        if curati:
            _status += f" · {len(curati)} verificati a mano"
        if inseriti:
            _status += f" · {len(inseriti)} inseriti da te"
        if scartati:
            # «FUORI DALL'INDICE» NON VUOL PIÙ DIRE «PERDUTI», e la
            # differenza va scritta qui: era la riga che faceva sembrare
            # normale non rispondere su un TAC che l'applicazione ha in
            # casa. Dal 31/08/2026 quelle righe si cercano nei file al
            # momento del bisogno (vedi `_seconda_lettura`).
            _status += (f" · {scartati} fuori dall'indice perché anteriori ad "
                        f"Android 8 e senza codice modello — restano "
                        f"cercabili nei file, una riga alla volta")
    return index


# Le fonti pubbliche sono utili ma non autorevoli: il loro ordine di
# download non deve decidere da solo quale telefono mostrare. I punteggi
# grandi delle prime due voci rendono esplicita l'eccezione importante:
# una correzione inserita dall'utente o verificata nel repository prevale
# sempre sull'euristica automatica.
_PESO_FONTE = {
    FONTE_UTENTE: 10_000,
    FONTE_CURATA: 9_000,
    FONTE_PRINCIPALE: 30,
    FONTE_IMEIDB: 20,
    FONTE_OSMOCOM: 10,
    FONTE_ESTERNA: 0,
}
_RE_MERCATO_EU = re.compile(
    r"\b(?:eea|europa|europe|european|italia|italy|italiano|italian)\b",
    re.IGNORECASE,
)


def _punteggio_affidabilita(voci: list[tuple[str, str, str]], posizione: int) -> int:
    """Affidabilità di una risposta TAC senza consultare altra rete.

    La preferenza europea si applica solo se la fonte la dichiara
    esplicitamente: «Global» da solo non basta, perché non identifica un
    mercato. Se non c'è un segnale verificabile si conserva il normale
    ordine di fiducia delle fonti, invece di indovinare una regione.
    """
    fonte, marca, specs = voci[posizione]
    base = _PESO_FONTE.get(fonte, 0)
    # Le correzioni umane sono decisioni, non candidati da ripesare.
    if base >= _PESO_FONTE[FONTE_CURATA]:
        return base

    # Questa funzione gira per TUTTI i TAC all'avvio: non deve chiamare
    # `parse_specs`, che può risolvere codici nei cataloghi esterni. Per il
    # ranking basta il primo campo (il nome commerciale) e il pattern locale
    # del codice, entrambi già contenuti nella riga TAC.
    def nome_e_codice(marca_candidata: str, specs_candidati: str) -> tuple[frozenset, str | None]:
        grezzo = " ".join(str(specs_candidati or "").split())
        nome = grezzo.split(",", 1)[0].strip() or grezzo
        codice, _anno = _split_code_and_year(grezzo)
        return _same_words_key(marca_candidata, nome), codice

    stessa_identita, codice = nome_e_codice(marca, specs)
    conferme = sum(
        nome_e_codice(altra_marca, altri_specs)[0] == stessa_identita
        for _altra_fonte, altra_marca, altri_specs in voci
    )
    # Due cataloghi indipendenti che descrivono lo stesso modello sono un
    # riscontro più affidabile della sola posizione in una lista.
    base += max(0, conferme - 1) * 40
    if codice:
        base += 10
    if _RE_MERCATO_EU.search(specs or ""):
        base += 100
    return base


def _ordina_per_affidabilita(
    voci: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """Ordina le risposte di un TAC dalla più affidabile alla meno tale.

    Il secondo elemento della chiave conserva l'ordine originale come
    spareggio: il filtro non rende instabili i casi in cui le prove sono
    equivalenti.
    """
    return [
        voce for _indice, voce in sorted(
            enumerate(voci),
            key=lambda coppia: (-_punteggio_affidabilita(voci, coppia[0]),
                                coppia[0]),
        )
    ]


def _indice_fallback() -> dict[str, tuple[str, str]]:
    """TAC dalla base dati storica, in forma di dizionario.

    L'indice vero la legge in flusso (`_voci_storiche`); questa resta la
    forma comoda per chi vuole guardarla tutta insieme — i test e chi
    misura la copertura. Poggia sullo stesso lettore, così non esistono
    due modi di interpretare lo stesso file.

    Fallisce in silenzio di proposito: è un supplemento, e se non è
    raggiungibile l'app deve continuare a funzionare con la prima base
    dati invece di non identificare più niente.
    """
    return {tac: (marca, modello) for tac, marca, modello in _voci_storiche()}


def carica_tac_osmocom(testo: str) -> dict[str, tuple[str, str]]:
    """Legge il CSV di Osmocom.

    **QUESTA FONTE NON HA MAI FUNZIONATO.** Il file comincia con una riga di
    copyright — «Osmocom TAC database under CC-BY-SA v3.0 …» — e
    l'intestazione vera è la SECONDA. Leggendo la prima riga come
    intestazione, la colonna `tac` non si trovava, la funzione usciva a mano
    vuota e l'indice restava identico. Da mesi l'app scaricava 3 MB ogni due
    settimane per ricavarne zero voci, e la Diagnostica non poteva
    accorgersene perché il download riusciva.

    L'altra particolarità è che l'intestazione ha DUE colonne chiamate
    `name`: la prima è la marca, la seconda il modello. Cercarle per nome
    darebbe due volte la stessa, quindi qui le colonne si prendono per
    posizione, che è l'unica cosa che le distingue.
    """
    return {tac: (marca, modello)
            for tac, marca, modello in _righe_osmocom(io.StringIO(testo or ""))}


def carica_tac_imeidb(testo: str) -> dict[str, tuple[str, str]]:
    """`TAC,marca,modello,…` senza intestazione."""
    return {tac: (marca, modello)
            for tac, marca, modello in _righe_imeidb(io.StringIO(testo or ""))}


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

# ======================================================================
# UN FORNITORE SOLO ERA UN PUNTO SINGOLO DI ROTTURA
# ======================================================================
# Segnalato dall'utente il 04/09/2026: «quel api key di hi cell tek non
# funziona». È la seconda volta (vedi v70), e il problema vero non è
# quale sia il guasto: è che quando quell'unico fornitore tace, l'ultima
# strada rimasta è chiusa e non ce n'è una seconda. Il piano gratuito è
# di cento interrogazioni al mese: anche quando funziona, finisce.
#
# Da qui in poi i fornitori sono UN ELENCO, provato in ordine, e si
# configurano dall'ambiente senza toccare il codice — che è la
# differenza fra «aspetto un rilascio» e «cambio una variabile su Render
# e riprovo». Tre sono abbastanza: sono le chiavi gratuite che una
# persona sola riesce realisticamente a tenere.
#
#     TAC_API_KEY        la chiave (senza, il fornitore è spento)
#     TAC_API_URL        l'indirizzo, se il fornitore l'ha cambiato
#     TAC_API_HEADER     l'intestazione di autenticazione
#     TAC_API_NOME       come chiamarlo in Diagnostica
#
# e le stesse quattro con il suffisso `_2` e `_3` per il secondo e il
# terzo. Il primo ha già i valori di HiCellTek, quindi chi aveva solo
# `TAC_API_KEY` non deve cambiare niente.
#
# L'indirizzo decide anche il verbo: se contiene `{tac}` si chiama in
# GET con le otto cifre al posto del segnaposto, altrimenti in POST con
# `{"query": "<tac>"}` nel corpo — le due forme che usano i servizi TAC.
_FORNITORI_PREDEFINITI = [
    # (suffisso, nome, url, intestazione)
    ("", "HiCellTek", TAC_API_URL, "X-Api-Key"),
    ("_2", "secondo servizio", "", "X-Api-Key"),
    ("_3", "terzo servizio", "", "X-Api-Key"),
]


def fornitori_tac() -> list[dict]:
    """I fornitori configurati, in ordine di interrogazione.

    Un fornitore senza chiave o senza indirizzo non compare: spento vuol
    dire assente, non «presente e sempre in errore».
    """
    elenco = []
    for suffisso, nome, url_base, intestazione in _FORNITORI_PREDEFINITI:
        # Il primo passa da `_chiave_api()` invece che dall'ambiente
        # diretto, e non e' un dettaglio: quella funzione e' il punto in
        # cui la chiave si legge da sempre, ed e' l'aggancio che le prove
        # sostituiscono per far finta di averne una. Leggere `C.env` qui
        # avrebbe scavalcato l'unico posto dove la lettura si puo'
        # osservare.
        chiave = (_chiave_api() if not suffisso
                  else C.env("TAC_API_KEY" + suffisso).strip())
        url = C.env("TAC_API_URL" + suffisso, url_base).strip()
        if not chiave or not url:
            continue
        elenco.append({
            "nome": C.env("TAC_API_NOME" + suffisso, nome).strip() or nome,
            "url": url,
            "chiave": chiave,
            "intestazione": (C.env("TAC_API_HEADER" + suffisso,
                                   intestazione).strip() or intestazione),
        })
    return elenco


def _intestazioni_fornitore(fornitore: dict) -> dict[str, str]:
    """Le intestazioni della chiamata, con l'unica cortesia che serve.

    `Authorization` senza schema non è un'intestazione valida, e chi
    incolla una chiave in una variabile d'ambiente incolla la chiave, non
    `Bearer` più la chiave. Se manca lo schema lo si mette; se c'è già —
    `Bearer …`, `Token …`, `Basic …` — non si tocca.
    """
    chiave = fornitore["chiave"]
    nome = fornitore["intestazione"]
    if nome.lower() == "authorization" and " " not in chiave:
        chiave = "Bearer " + chiave
    return {nome: chiave, "User-Agent": C.USER_AGENT}


def _chiave_api() -> str:
    """La chiave del PRIMO fornitore, dall'ambiente.

    Prima si leggeva da `st.secrets`, cioè dalla cassaforte di Streamlit.
    Tolta la dashboard, quel ramo non poteva che fallire — e falliva in
    silenzio dentro un `except`, quindi la funzione rispondeva «nessuna
    chiave» anche a chi la chiave l'aveva messa. Tutto il resto del
    progetto legge la configurazione da `C.env`; questa era l'unica
    eccezione, ed era rimasta indietro.
    """
    return C.env("TAC_API_KEY").strip()


def stato_servizio_esterno() -> str:
    """Se il servizio a pagamento è configurato, e quanto ha già risposto.

    Senza questa riga chi metteva la chiave non aveva NESSUN modo di
    sapere se era stata letta: la fonte si interroga solo per i TAC che
    nessun database locale conosce, quindi può passare molto tempo prima
    che un errore di configurazione si manifesti — e quando si manifesta
    sembra un buco dei dati, non una chiave sbagliata.
    """
    configurati = fornitori_tac()
    if not configurati:
        return ("non configurata — con una chiave in TAC_API_KEY i TAC che "
                "nessun database locale conosce vengono chiesti al servizio "
                "esterno (solo le 8 cifre del TAC, mai l'IMEI intero). Se ne "
                "possono mettere fino a tre: TAC_API_KEY, TAC_API_KEY_2, "
                "TAC_API_KEY_3, provati in quest'ordine")
    quante = len(tac_esterni())
    # QUALI fornitori, non «la chiave»: con un elenco, «chiave presente»
    # non dice piu' quale delle tre e' stata letta ne' in che ordine si
    # provano, che e' proprio cio' che serve sapere quando una non
    # funziona.
    pezzi = [", ".join(f["nome"] for f in configurati)
             + (" (in quest'ordine)" if len(configurati) > 1 else "")]
    pezzi.append(f"{quante} TAC risolti dal servizio e conservati"
                 if quante else "nessun TAC ancora risolto dal servizio")
    # E COM'E' ANDATA L'ULTIMA VOLTA.
    #
    # Segnalato dall'utente il 01/09/2026: «il servizio esterno non
    # funziona». Aveva ragione, e la cosa peggiore e' che NON SI POTEVA
    # SAPERE: ogni guasto — chiave rifiutata, quota finita, servizio giu',
    # rete che non passa — finiva nello stesso `return ("errore", None)`,
    # senza lasciare traccia da nessuna parte, e la pagina diceva
    # «modello sconosciuto» esattamente come quando il servizio risponde
    # «non lo conosco». Una chiave sbagliata e un TAC introvabile
    # raccontati con la stessa frase.
    ultimo = ultimo_esito_servizio()
    if ultimo.get("dettaglio"):
        quando = ultimo.get("quando") or ""
        pezzi.append(f"ultima chiamata: {ultimo['dettaglio']}"
                     + (f" ({quando[:16].replace('T', ' ')} UTC)" if quando else ""))
    else:
        pezzi.append("nessuna chiamata ancora registrata")
    return " · ".join(pezzi)


# ======================================================================
# COM'E' ANDATA L'ULTIMA CHIAMATA AL SERVIZIO ESTERNO
# ======================================================================
# Si conserva in archivio (sopravvive ai riavvii, che qui sono all'ordine
# del giorno) e si mostra in Diagnostica e in `/health`. La pausa dopo un
# guasto invece sta in memoria: e' una cortesia verso un servizio che sta
# male, non un dato da ricordare, e cosi' un riavvio la azzera da sola.
_META_ESITO_SERVIZIO = "imei_tac_servizio_ultimo"
_MINUTI_PAUSA_SERVIZIO = 5
#: nome del fornitore -> (quando, perché). LA PAUSA È DI CHI STA MALE,
#: NON DI TUTTI: con un elenco di fornitori, mettere in pausa «il
#: servizio» significherebbe che il primo che sbaglia zittisce anche i
#: due che funzionano — cioè l'esatto contrario del motivo per cui
#: l'elenco esiste.
_pausa_servizio: dict[str, tuple[float, str]] = {}
# La copia in memoria dell'ultimo esito, e non è un vezzo: `/health` la
# legge, e quella rotta la interroga l'host OGNI MINUTO. Il suo docstring
# promette di non toccare l'archivio, e una promessa del genere si
# mantiene o si toglie. Così il database si legge una volta sola per
# processo — al primo che chiede dopo un riavvio — e da lì in poi la
# risposta è già in mano.
_ultimo_esito: dict | None = None


def ultimo_esito_servizio() -> dict:
    """`{"quando", "esito", "dettaglio"}` dell'ultima chiamata, o `{}`."""
    global _ultimo_esito
    if _ultimo_esito is not None:
        return _ultimo_esito
    dati = {}
    grezzo = storage.get_meta(_META_ESITO_SERVIZIO)
    if grezzo:
        try:
            letto = json.loads(grezzo)
            dati = letto if isinstance(letto, dict) else {}
        except Exception:
            dati = {}
    _ultimo_esito = dati
    return dati


def _ricorda_esito_servizio(esito: str, dettaglio: str,
                            fornitore: str = "") -> None:
    global _ultimo_esito
    registrato = {
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "esito": esito,
        "dettaglio": (f"{fornitore}: {dettaglio}" if fornitore else dettaglio),
        "fornitore": fornitore,
    }
    _ultimo_esito = registrato
    try:
        storage.set_meta(_META_ESITO_SERVIZIO, json.dumps(registrato))
    except Exception:      # pragma: no cover - una diagnosi non rompe nulla
        pass
    # UN SERVIZIO CHE NON RISPONDE NON SI RIPROVA A OGNI PAGINA. Ogni
    # tentativo costa il tempo del timeout, e chi cerca lo aspetta per
    # ricevere comunque «non lo so». Cinque minuti sono abbastanza da non
    # martellare e abbastanza pochi da accorgersi subito quando torna.
    import time as _time
    if esito == "errore":
        _pausa_servizio[fornitore] = (_time.monotonic(), dettaglio)
    else:
        _pausa_servizio.pop(fornitore, None)


def servizio_in_pausa(fornitore: str = "") -> str | None:
    """Il motivo per cui non si richiama adesso QUESTO fornitore, se c'e'.

    Senza argomento risponde per il primo che sia in pausa: e' la forma
    che serve a chi vuole solo sapere se c'e' un guasto in corso.
    """
    import time as _time
    if fornitore:
        voci = [(fornitore, _pausa_servizio.get(fornitore))]
    else:
        voci = list(_pausa_servizio.items())
    for nome, pausa in voci:
        if not pausa:
            continue
        quando, dettaglio = pausa
        if _time.monotonic() - quando > _MINUTI_PAUSA_SERVIZIO * 60:
            _pausa_servizio.pop(nome, None)
            continue
        return dettaglio
    return None


def cerca_tac_online(tac: str) -> tuple[str, str] | None:
    """Marca e modello per un TAC, chiedendoli al servizio esterno.

    Ritorna None in ogni caso incerto: chiave assente, servizio non
    raggiungibile, risposta inattesa, TAC sconosciuto. Un servizio a
    pagamento che non risponde non deve mai diventare un dato inventato.

    Chi ha bisogno di sapere PERCHE' e' None — «non lo conosce» e «non ha
    risposto» si somigliano qui e sono opposti fuori — usa
    `cerca_tac_online_esito`.
    """
    return cerca_tac_online_esito(tac)[1]


def _interroga_fornitore(fornitore: dict, tac: str) -> tuple[str, tuple[str, str] | None]:
    """Chiede questo TAC a UN fornitore e traduce la sua risposta.

    Il verbo lo decide l'indirizzo: `{tac}` dentro l'URL vuol dire una
    rotta in GET (`…/tac/35692411`), la sua assenza vuol dire la POST con
    il corpo JSON. Sono le due forme in cui i servizi TAC si presentano,
    e indovinarne una sola significava non poterne cambiare.
    """
    nome = fornitore["nome"]
    url = fornitore["url"]
    try:
        if "{tac}" in url:
            risposta = requests.get(
                url.replace("{tac}", tac),
                headers=_intestazioni_fornitore(fornitore),
                timeout=C.HTTP_TIMEOUT,
            )
        else:
            risposta = requests.post(
                url,
                json={"query": tac},
                headers=_intestazioni_fornitore(fornitore),
                timeout=C.HTTP_TIMEOUT,
            )
    except Exception as errore:
        _ricorda_esito_servizio(
            "errore", f"non raggiungibile ({type(errore).__name__})", nome)
        return ("errore", None)

    stato = getattr(risposta, "status_code", 0)
    # 404 E' UNA RISPOSTA, NON UN GUASTO. Alcuni fornitori dicono «non ce
    # l'ho» con il codice HTTP invece che nel corpo: trattarlo come un
    # errore di rete significherebbe richiederlo — e pagarlo — per sempre.
    if stato == 404:
        _ricorda_esito_servizio("assente", "HTTP 404: TAC non in catalogo", nome)
        return ("assente", None)
    if stato != 200:
        _ricorda_esito_servizio("errore", _spiega_stato(stato), nome)
        return ("errore", None)
    try:
        dati = risposta.json()
    except Exception:
        _ricorda_esito_servizio("errore", "HTTP 200 ma risposta illeggibile", nome)
        return ("errore", None)
    if not isinstance(dati, dict):
        _ricorda_esito_servizio("errore",
                                "HTTP 200 ma risposta di forma inattesa", nome)
        return ("errore", None)

    corpo = dati.get("data") if isinstance(dati.get("data"), dict) else dati
    if not isinstance(corpo, dict):
        _ricorda_esito_servizio("errore",
                                "HTTP 200 ma risposta di forma inattesa", nome)
        return ("errore", None)

    # Il servizio dichiara esplicitamente l'esito con `found`: quando c'è,
    # va creduto. Un `found: false` con i campi vuoti non è una risposta
    # da interpretare, è un no.
    if corpo.get("found") is False:
        _ricorda_esito_servizio("assente", "non conosce questo TAC", nome)
        return ("assente", None)

    # I NOMI DEI CAMPI CAMBIANO DA UN FORNITORE ALL'ALTRO, e sono
    # l'unica cosa che impedisce a una chiave nuova di funzionare
    # subito. Si accettano quelli che usano davvero i servizi TAC —
    # inglese e italiano — invece di obbligare a un adattatore per
    # ognuno.
    marca = _testo_o_nome(corpo.get("brand") or corpo.get("manufacturer")
                          or corpo.get("marca") or corpo.get("vendor"))
    modello = _testo_o_nome(corpo.get("model") or corpo.get("modello")
                            or corpo.get("device") or corpo.get("name"))
    if not marca and not modello:
        # Il servizio ha risposto 200 senza dire che telefono e': per
        # questo TAC non ha niente. E' un no, non un guasto.
        _ricorda_esito_servizio("assente", "non conosce questo TAC", nome)
        return ("assente", None)

    # Il chipset arriva solo con i piani a pagamento, ma se c'è si prende:
    # è esattamente il dato che manca altrove, e viene da chi identifica il
    # dispositivo, non da una tabella scritta a mano.
    chipset = _testo_o_nome(corpo.get("chipset"))
    if chipset:
        modello = f"{modello}, {chipset}".strip(", ")

    _ricorda_esito_servizio("trovato", "risposta ricevuta", nome)
    return ("trovato", (marca or "Sconosciuto", modello))


def cerca_tac_online_esito(tac: str) -> tuple[str, tuple[str, str] | None]:
    """Come `cerca_tac_online`, ma dice anche com'e' andata.

    Ritorna `("trovato", (marca, modello))`, `("assente", None)` quando i
    servizi hanno risposto ed e' un no, oppure `("errore", None)` quando
    la domanda non e' nemmeno arrivata a destinazione o la risposta e'
    illeggibile.

    LA DIFFERENZA FRA «ASSENTE» E «ERRORE» E' TUTTO IL PUNTO. Solo il
    primo si puo' conservare: e' una risposta. Il secondo e' silenzio, e
    ricordare il silenzio come un no rende ignoto per un mese un
    telefono che il servizio conosce.

    **E CON PIÙ FORNITORI IL «NO» DIVENTA PIÙ CARO DA DARE.** Un
    fornitore che non conosce un TAC non chiude la questione: quello dopo
    puo' conoscerlo, ed e' esattamente il motivo per cui ce n'e' piu'
    d'uno. Si va avanti finche' uno risponde, e si conserva un «assente»
    solo se ALMENO UNO ha detto no e NESSUNO ha detto sì. Se hanno taciuto
    tutti e' un errore, e un errore non si conserva.
    """
    if requests is None:
        return ("errore", None)
    tac = "".join(c for c in (tac or "") if c.isdigit())[:8]
    if len(tac) != 8:
        return ("errore", None)

    qualcuno_ha_detto_no = False
    for fornitore in fornitori_tac():
        # OGNI STRADA DA QUI IN GIU' LASCIA DETTO COM'E' ANDATA. Prima
        # finivano tutte nello stesso `("errore", None)` muto: vedi il
        # commento in `stato_servizio_esterno`.
        if servizio_in_pausa(fornitore["nome"]):
            continue
        esito, risposta = _interroga_fornitore(fornitore, tac)
        if esito == "trovato":
            return (esito, risposta)
        if esito == "assente":
            qualcuno_ha_detto_no = True
    return ("assente", None) if qualcuno_ha_detto_no else ("errore", None)


# Un nome in codice Motorola come lo scrive il database TAC: il codename
# interno, poi l'eventuale marcatore di rete o di regione, poi due cifre
# d'anno. `PENANG5GNA23`, `IBIZA21`, `TAIPEI24`, `BRONCO23`.
_RE_CODENAME = re.compile(r"^([A-Za-z]+)(?:5G)?(?:NA|EU|IN|LATAM)?(\d{2})$")


def _nome_da_codename(nome: str) -> str:
    """Il nome commerciale di un nome in codice, se lo conosciamo già.

    SEGNALATO DALL'UTENTE IL 02/09/2026, ed è la domanda giusta: «è un
    moto g34, come mai gli altri lo trovano e noi no?». La riga del
    database dice `MOTOROLA, FOGO5G23` — che non è un nome mancante, è il
    NOME IN CODICE interno di quel telefono. E i database gratuiti lo
    scrivono così per tutta la produzione Motorola recente:

        MOTOROLA BRONCO23      bronco  → ThinkPhone
        MOTOROLA IBIZA21       ibiza   → G50
        MOTOROLA PENANG5G23    penang  → G53 5G
        MOTOROLA TAIPEI24      taipei  → G55
        MOTOROLA PAROS24       paros   → G75

    Il dizionario per tradurli è **dentro questo progetto da mesi**:
    `sources.MOTOROLA_LOLINET_DEVICES`, quaranta codename verificati
    sull'indice XDA e sul database community, che serve a cercare i
    firmware sul mirror lolinet. Nessuno aveva mai unito le due cose: il
    database TAC parlava in codice e noi avevamo il vocabolario chiuso in
    un cassetto.

    LA CORRISPONDENZA DEVE ESSERE ESATTA dopo aver tolto anno e
    marcatori: `sabahlite23` non diventa `sabahl` per somiglianza, e
    `fogo5g23` non diventa `fogos`. Somigliarsi non è essere lo stesso
    telefono, e questo progetto preferisce dire «non lo so» che indovinare
    — per quei casi c'è la tabella curata `data/tac_modelli.csv`, dove una
    riga la scrive una persona che il telefono ce l'ha in mano.
    """
    trovato = _RE_CODENAME.match(" ".join((nome or "").split()))
    if not trovato:
        return ""
    codename = trovato.group(1).lower()
    try:
        from . import sources
    except Exception:  # pragma: no cover - percorso difensivo
        return ""
    for _anno, noto, commerciale in sources.MOTOROLA_LOLINET_DEVICES:
        if noto.lower() == codename:
            return commerciale
    return ""


def _solo_la_marca(nome: str, brand: str) -> bool:
    """Se questo «nome» non è altro che il nome della marca.

    Parole identiche, non una dentro l'altra: «OPPO A74» contiene «OPPO»
    ma è un modello, «MOTOROLA» da solo non lo è.
    """
    def parole(testo: str) -> frozenset:
        return frozenset(p for p in re.sub(r"[^a-z0-9]+", " ",
                                           (testo or "").lower()).split() if p)

    di_marca = parole(brand)
    return bool(di_marca) and parole(nome) == di_marca


def _senza_la_marca_davanti(coda: str, brand: str) -> str:
    """La coda senza la marca ripetuta all'inizio: quello che resta è il
    modello.

    Si taglia DALL'ULTIMA occorrenza della parola di marca, non dalla
    prima: `Vivo Mobile vivo Y55` ha la ragione sociale in mezzo, e
    fermarsi alla prima lascerebbe «Mobile vivo Y55». Se la marca non
    compare affatto — `LG, SKT X SCREEN` — la coda si tiene intera,
    perché è comunque tutto quello che il database dice di quel telefono.
    """
    parole = (coda or "").split()
    marca = (brand or "").strip().lower()
    if not parole or not marca:
        return coda
    posizioni = [i for i, parola in enumerate(parole)
                 if parola.strip(",.").lower() == marca]
    if not posizioni:
        return coda
    resto = parole[posizioni[-1] + 1:]
    # Se dopo la marca non resta niente, meglio la coda com'era: un nome
    # vuoto non è un miglioramento.
    return " ".join(resto) if resto else coda


def _spiega_stato(stato: int) -> str:
    """Un numero HTTP e cosa vuol dire sono due cose diverse.

    «HTTP 401» dice tutto a chi sa leggerlo e niente a chi deve decidere
    cosa fare. Questi sono i tre guasti che capitano davvero a un servizio
    a chiave, e ognuno ha una mossa diversa: rifare la chiave, aspettare
    il mese nuovo, aspettare e basta.
    """
    if stato in (401, 403):
        return (f"HTTP {stato}: chiave rifiutata — da rifare o da "
                f"ricontrollare in TAC_API_KEY")
    if stato == 429:
        return (f"HTTP {stato}: troppe richieste o quota del mese finita "
                f"(il piano gratuito ne dà cento)")
    if stato >= 500:
        return f"HTTP {stato}: guasto del servizio, non nostro"
    return f"HTTP {stato}: risposta inattesa"


def _testo_o_nome(valore) -> str:
    """Il servizio restituisce alcuni campi come oggetti annidati.

    `brand` arriva come `{"name": "Samsung", "slug": "samsung"}`, non come
    stringa: convertirlo con `str()` produrrebbe la rappresentazione del
    dizionario dentro il nome del dispositivo. Altri campi sono stringhe
    semplici, quindi vanno gestiti entrambi i casi.
    """
    if isinstance(valore, dict):
        valore = valore.get("name") or valore.get("value") or ""
    return str(valore or "").strip()


# ======================================================================
# QUINDICI CIFRE NON SONO L'UNICA FORMA IN CUI UN IMEI ARRIVA
# ======================================================================
# Segnalato dall'utente il 04/09/2026: «ho bisogno di trovare piu imei
# possibili». Questo pezzo non costa nessuna fonte nuova, e finora
# buttava via due forme legittime su tre.
#
# Chi compone `*#06#` su un telefono non legge sempre quindici cifre:
#
#   16 cifre  è l'IMEISV, e sui Samsung è quello che lo schermo mostra
#             per primo. Le prime 14 sono le stesse dell'IMEI; al posto
#             della cifra di controllo ci sono DUE cifre che dicono la
#             versione del software.
#   14 cifre  è l'IMEI senza la cifra di controllo, come lo scrivono le
#             etichette sulla scatola e come lo restituiscono parecchi
#             gestionali, che quella cifra la calcolano e non la salvano.
#
# In tutte e tre le forme le prime OTTO cifre sono le stesse, e sono
# l'unica cosa che serve qui. Rifiutare le altre due significava mandare
# quel numero a `search_model`, cioè cercare un telefono che si chiama
# «351397403741486 12» e trovarne zero — con il messaggio sbagliato per
# giunta, perché diceva «non trovato» invece di «questo non è un IMEI».
def is_imei_like(imei: str) -> bool:
    """True per un IMEI in una qualunque delle sue tre lunghezze.

    Quattordici cifre (senza controllo), quindici (l'IMEI intero, anche
    con la cifra di controllo sbagliata) o sedici (l'IMEISV). Il TAC —
    le prime otto — è lo stesso in tutte e tre, ed è l'unica parte che
    questo modulo guarda.

    A transcription error in the last digit must not turn a TAC lookup into a
    model-name search: the first eight digits still identify the equipment
    type. Callers keep the Luhn result visible as a warning and never use the
    serial part for local identification.
    """
    digits = "".join(ch for ch in (imei or "") if ch.isdigit())
    return len(digits) in (14, 15, 16)


#: Le tre forme, con il nome da mostrare a chi legge.
FORMA_IMEI = "imei"
FORMA_SENZA_CONTROLLO = "senza cifra di controllo"
FORMA_IMEISV = "IMEISV"


def forma_imei(imei: str) -> str:
    """Quale delle tre forme è questo numero, o «» se non è nessuna.

    Serve alla pagina per non dire la cosa sbagliata: il controllo Luhn
    riguarda la quindicesima cifra, quindi su un numero che quella cifra
    non ce l'ha — 14 cifre — o che al suo posto ha la versione del
    software — 16 — «cifra di controllo errata» sarebbe un allarme falso
    su un numero perfettamente valido.
    """
    digits = "".join(ch for ch in (imei or "") if ch.isdigit())
    return {14: FORMA_SENZA_CONTROLLO,
            15: FORMA_IMEI,
            16: FORMA_IMEISV}.get(len(digits), "")


def is_valid_imei(imei: str) -> bool:
    """Controllo Luhn standard sui 15 cifre di un IMEI (solo formato, non
    verifica se è realmente assegnato/attivo).

    RESTA A QUINDICI CIFRE anche ora che `is_imei_like` ne accetta tre
    lunghezze, e non è una svista: Luhn è un controllo SULLA
    quindicesima cifra. Un numero che quella cifra non ce l'ha non è
    «non valido», è semplicemente un altro formato — vedi `forma_imei`,
    che è la funzione da usare per decidere cosa scrivere a schermo.
    """
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


def imei_con_cifra_di_controllo(imei: str) -> str | None:
    """Restituisce lo stesso IMEI con la quindicesima cifra Luhn corretta.

    Non interroga alcun database: corregge esclusivamente la cifra di
    controllo dal prefisso di 14 cifre. Per questo è un suggerimento di
    trascrizione utile a cercare e copiare il numero, non una conferma che
    l'IMEI sia assegnato, non bloccato o appartenente al telefono mostrato.
    """
    digits = "".join(ch for ch in (imei or "") if ch.isdigit())
    # DA QUATTORDICI CIFRE SI CALCOLA, NON SI CORREGGE, ed è il caso in
    # cui questa funzione serve di più: chi copia un IMEI da un'etichetta
    # o da un gestionale spesso non ha l'ultima cifra, e qui gliela si
    # restituisce invece di rispondere «niente». Da sedici (l'IMEISV) si
    # tengono le prime quattordici: le ultime due sono la versione del
    # software, non fanno parte dell'IMEI.
    if len(digits) in (14, 16):
        digits = digits[:14] + "0"
    if len(digits) != 15:
        return None
    totale = 0
    for indice, char in enumerate(digits[:14]):
        valore = int(char)
        if indice % 2 == 1:
            valore *= 2
            if valore > 9:
                valore -= 9
        totale += valore
    return digits[:14] + str((-totale) % 10)


def tac_di(imei: str) -> str:
    """Le 8 cifre che identificano il modello. Le altre sette identificano
    il singolo esemplare e non servono mai a questo modulo."""
    digits = "".join(ch for ch in (imei or "") if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else ""


def _voci_per_tac(tac: str) -> list[tuple[str, str, str]]:
    global _memory_index
    if _memory_index is None:
        # Prima del catalogo bulk si controllano le correzioni locali. Sono
        # dati piu' affidabili e, soprattutto, permettono alla ricerca IMEI
        # appena dopo un deploy di rispondere senza scaricare e indicizzare
        # centinaia di migliaia di TAC che non c'entrano con questa domanda.
        # L'indice completo viene comunque caricato appena serve un TAC non
        # presente qui: la copertura generale non si restringe.
        locali: list[tuple[str, str, str]] = []
        inserito = tac_inseriti().get(tac)
        curato = _indice_curato().get(tac)
        if inserito:
            locali.append((FONTE_UTENTE, inserito[0], inserito[1]))
        if curato:
            locali.append((FONTE_CURATA, curato[0], curato[1]))
        if locali:
            # Il percorso rapido evita il download/indice completo al primo
            # IMEI dopo un deploy, ma Diagnostica deve continuare a dire se
            # la risposta include un TAC inserito dall'utente. Altrimenti
            # sembra che il salvataggio non sia mai avvenuto, pur essendo
            # proprio il dato che ha fatto evitare il download pesante.
            dettaglio = []
            if curato:
                dettaglio.append("verificato a mano")
            if inserito:
                dettaglio.append("1 inserito da te")
            globals()["_status"] = (
                "risposta dal catalogo locale " + " · ".join(dettaglio)
            )
            return _ordina_per_affidabilita(locali)
        _memory_index = _build_index()
    # L'INDICE SI LEGGE UNA VOLTA SOLA, IN UNA LOCALE. Fra il controllo
    # `is None` qui sopra e la lettura qui sotto c'era una finestra, e
    # questa cache viene azzerata DA PRODUZIONE: `aggiungi_tac` e
    # `rimuovi_tac` chiamano `reset_cache()`, cioè la rotta `/tac/salva`.
    # Bastava che qualcuno salvasse un TAC dalla pagina mentre un altro
    # cercava un IMEI perché la seconda richiesta trovasse `None` e
    # rispondesse 500. Lo stesso schema è stato corretto in
    # `core/modelcodes.py`, dove un ciclo di sforzo con thread paralleli
    # l'ha fatto scattare davvero.
    indice = _memory_index
    voci = _voci_dalla_cella((indice or {}).get(tac))
    return voci or _seconda_lettura(tac)


# ======================================================================
# LA SECONDA LETTURA: quello che il filtro scarta non è più perduto
# ======================================================================
# Segnalato dall'utente il 31/08/2026: «trovare gli imei sta diventando
# difficile, su due imei non ne ha trovato neanche uno». Uno dei due era
# `865587084948173`, e la base dati lo conosce: `HONOR,86558708,"HONOR 400
# PRO, N/A2025"`. La pagina rispondeva «modello sconosciuto».
#
# La causa immediata era il difetto dell'anno appiccicato (vedi
# `_dell_era_android`), ma dietro c'è una scelta di fondo da correggere:
# l'indice tiene la sola era Android — 216.617 righe scartate su 248.373,
# misurate in produzione — e finora quelle righe erano semplicemente
# PERSE. Un dato che sta in un file dentro l'applicazione, e a cui
# l'applicazione risponde «non lo so», non è un buco di copertura: è un
# dato buttato.
#
# Il filtro però serve, ed è il motivo per cui l'indice sta in 22 MB
# invece che in 70. La via d'uscita è smettere di trattare «in memoria» e
# «disponibile» come la stessa cosa:
#
#     l'INDICE   è la via veloce, per l'era che interessa quasi sempre;
#     il FILE    è la via lenta, per tutto il resto — e non costa memoria.
#
# Misurato: scorrere le 248.373 righe cercando UN TAC costa **0,24
# secondi** e 0,2 MB, perché i byte sono già in archivio e si leggono in
# flusso. Si paga solo quando l'indice non sa rispondere, cioè proprio nel
# caso in cui prima si rispondeva «non lo so» — e prima di spendere una
# delle cento interrogazioni mensili del servizio esterno, che è la strada
# subito successiva.
_CACHE_SECONDE_LETTURE: dict[str, str] = {}
_MAX_SECONDE_LETTURE = 512


def _seconda_lettura(tac: str) -> list[tuple[str, str, str]]:
    """Cerca un TAC dentro i file, riga per riga, senza tenerli in memoria."""
    if not tac:
        return []
    if tac in _CACHE_SECONDE_LETTURE:
        return _voci_dalla_cella(_CACHE_SECONDE_LETTURE[tac])

    pezzi: list[str] = []
    for fonte, righe in ((FONTE_PRINCIPALE, _voci_principali),
                         (FONTE_IMEIDB, _voci_imeidb),
                         (FONTE_OSMOCOM, _voci_storiche)):
        try:
            for altro, marca, specs in righe():
                if altro == tac:
                    pezzi.append(fonte + _CAMPO + marca + _CAMPO + specs)
        except Exception:
            # Una fonte che non si legge non deve impedire alle altre di
            # rispondere: è la stessa regola dell'indice.
            continue

    cella = _VOCE.join(pezzi)
    # SI RICORDA ANCHE IL «NON C'È». Una pagina interroga questa funzione
    # più di una volta (l'identità, il confronto fra le fonti, il secondo
    # tempo della ricerca): senza memoria, un TAC sconosciuto farebbe
    # rileggere i file a ogni giro. Il tetto tiene la cosa piccola: è una
    # comodità, non un secondo indice.
    if len(_CACHE_SECONDE_LETTURE) >= _MAX_SECONDE_LETTURE:
        _CACHE_SECONDE_LETTURE.clear()
    _CACHE_SECONDE_LETTURE[tac] = cella
    return _voci_dalla_cella(cella)


def _voci_dalla_cella(cella) -> list[tuple[str, str, str]]:
    """Le risposte di un TAC, srotolate e messe in ordine di affidabilità.

    Accetta sia la stringa compatta dell'indice sia una lista di tuple:
    così un `_build_index` sostituito da una prova (`tests/test_core.py`)
    continua a funzionare senza sapere niente di come l'indice è fatto
    dentro.

    UNA FONTE PARLA UNA VOLTA SOLA, E VALE L'ULTIMA COSA CHE HA DETTO.
    Prima del flusso, ogni base dati veniva prima ridotta a dizionario, e
    lì una riga ripetuta sovrascriveva la precedente. Ora le righe arrivano
    tutte, quindi il duplicato si scarta qui — stesso esito, senza il
    dizionario intermedio. Sono 14 TAC su 248.359 nella base principale,
    ma la regola non cambia con la loro quantità.
    """
    if not cella:
        return []
    if isinstance(cella, str):
        grezze = [tuple(voce.split(_CAMPO)) for voce in cella.split(_VOCE)]
    else:
        grezze = [tuple(voce) for voce in cella]
    per_fonte: dict[str, tuple[str, str, str]] = {}
    for voce in grezze:
        if len(voce) != 3:
            continue
        per_fonte[voce[0]] = voce
    return _ordina_per_affidabilita(list(per_fonte.values()))


def identify(imei: str, solo_locale: bool = False) -> tuple[str, str] | None:
    """(brand, specs) dal TAC di un IMEI, o None se non identificabile.

    Con `solo_locale=True` non si esce mai in rete: si risponde con i
    database che stanno qui. Serve alla prima risposta della pagina, che
    deve arrivare subito — interrogare il servizio esterno lì significa
    far aspettare senza nemmeno poter dire perché, visto che la pagina
    non è ancora stata mandata. La chiamata esterna si fa nel secondo
    tempo, con la sua nota a schermo.

    L'IMEI passato qui non viene salvato né loggato: si usano solo i primi
    8 caratteri (il TAC) per la ricerca nell'indice.

    Quando più fonti conoscono lo stesso TAC vince la prima per precedenza
    (vedi `_build_index`). Le altre non vengono buttate: `confronto()` le
    restituisce tutte.
    """
    global _memory_index
    tac = tac_di(imei)
    if not tac:
        return None
    if solo_locale:
        voci = _voci_per_tac(tac)
        if not voci:
            return None
        _fonte, marca, specs = voci[0]
        return (marca, specs)

    voci = _voci_per_tac(tac)
    if voci:
        _fonte, marca, specs = voci[0]
        return (marca, specs)

    # Solo adesso, e solo se configurato, si chiede fuori: le
    # interrogazioni gratuite sono cento al mese e vanno spese sui
    # codici che i database locali non hanno.
    # Prima di spendere, si guarda se questa risposta è già stata comprata.
    gia_pagato = tac_esterni().get(tac)
    if gia_pagato:
        return gia_pagato

    # E NEMMENO SI RICOMPRA UN NO. Un TAC che il servizio ha gia'
    # dichiarato di non conoscere non va richiesto a ogni visita: costa
    # un'interrogazione del piano gratuito e la risposta e' la stessa.
    # Il «no» scade da solo dopo un mese (vedi `tac_gia_chiesto_invano`),
    # perche' i modelli nuovi vengono aggiunti di continuo.
    if tac_gia_chiesto_invano(tac):
        return None

    esito, esterno = cerca_tac_online_esito(tac)
    if esito == "trovato" and esterno:
        if _memory_index is not None:
            voce = FONTE_ESTERNA + _CAMPO + esterno[0] + _CAMPO + esterno[1]
            precedente = _memory_index.get(tac)
            _memory_index[tac] = (precedente + _VOCE + voce if precedente
                                  else voce)
        _ricorda_tac_esterno(tac, esterno[0], esterno[1])
        return esterno
    if esito == "assente":
        _ricorda_tac_assente(tac)
    return None


def confronto(imei: str) -> dict:
    """Che cosa dice OGNI fonte su questo TAC.

    **Perché è sempre disponibile, anche quando la ricerca è riuscita.**
    Lo stesso IMEI dà spesso un modello su un sito e un altro modello su un
    altro: i database TAC sono alimentati dalla community, si contraddicono,
    e nessuno è autorevole. Mostrare una risposta sola come se fosse LA
    risposta è il modo più efficace di far sbagliare telefono a chi sta
    preparando un test.

    Ritorna il TAC, l'elenco delle risposte (in ordine di precedenza) e se
    sono discordi. Il confronto è sui MODELLI riconosciuti, non sul testo
    grezzo: due fonti che scrivono «GALAXY A54 5G» e «Samsung Galaxy A54
    5G» dicono la stessa cosa, e segnalarle come discordi sarebbe rumore.
    """
    tac = tac_di(imei)
    if not tac:
        return {"tac": "", "voci": [], "discordi": False}

    voci = []
    for fonte, marca, specs in _voci_per_tac(tac):
        dettagli = parse_specs(marca, specs)
        voci.append({
            "fonte": fonte,
            "marca": marca,
            "modello": dettagli["model"],
            "codice": dettagli["code"],
            "anno": dettagli["year"],
            "raw": dettagli["raw"],
        })

    distinti = {_same_words_key(v["marca"], v["modello"]) for v in voci}
    return {"tac": tac, "voci": voci, "discordi": len(distinti) > 1}


def _same_words_key(marca: str, modello: str) -> frozenset:
    """Insieme delle parole significative: due grafie dello stesso telefono
    devono dare la stessa chiave, o ogni ricerca sembrerebbe discorde."""
    testo = f"{marca or ''} {modello or ''}".lower()
    return frozenset(p for p in re.sub(r"[^a-z0-9]+", " ", testo).split() if p)


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
    # Xiaomi/Redmi/POCO, le forme che la riga qui sopra NON prende.
    #
    # Quel pattern pretende 2-3 CIFRE dopo il gruppo di lettere, e mezza
    # produzione Xiaomi recente non ce le ha: `2406ERN9CC`, `24074RPD2I`,
    # `25078PC3EE`, `2510ERA8BT`, `22111317PI`. Sono i Redmi e i POCO
    # degli ultimi due anni, cioè i telefoni che si provano adesso.
    #
    # La seconda riga è la famiglia più vecchia, quella che comincia per
    # M: `M1910F4G` (Mi Note 10), `M2101K6G`, `M2012C3P1C`.
    #
    # Misurato sul file vero: 1.093 righe guadagnano un codice, e fra
    # quelle già indicizzate una sola cambia codice (`CELLON M8047UC
    # IQ180`, che di sigle ne ha due scritte in fila).
    re.compile(r"\b2\d{3,7}[A-Z][A-Z0-9]{1,6}\b"),
    re.compile(r"\bM\d{4}[A-Z][A-Z0-9]{1,5}\b"),
    re.compile(r"\bTA-\d{4}\b"),                        # Nokia: TA-1234
    # vivo/iQOO: V2124, V2307, V2529, V2283A. UNA lettera sola, ed è per
    # questo che mancavano: il pattern generico qui sotto ne pretende
    # almeno due, quindi NESSUN codice vivo veniva riconosciuto.
    #
    # Non è un dettaglio di catalogazione. Segnalato dall'utente il
    # 01/09/2026 con l'IMEI 862245059650208: la riga è `VIVO,86224505,
    # "VIVO Y76 5G, Vivo Mobile V2124"` e senza codice riconosciuto quel
    # telefono (a) restava fuori dall'indice, perché la riga non ha
    # nemmeno un anno, e (b) veniva cercato per nome invece che per
    # codice, che è la chiave esatta con cui le fonti rispondono —
    # `modelcodes` sa benissimo che V2124 è lo Y76 5G.
    #
    # Riguarda due terzi dei vivo del database (3.202 righe fuori contro
    # 1.610 dentro), fra cui modelli del 2025 come il V60 Lite 5G
    # (`V2529`).
    re.compile(r"\bV\d{4}[A-Z]{0,2}\b"),
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


# «N/A» come lo scrive il dataset quando un dato non ce l'ha, con
# l'eventuale anno attaccato: `N/A2025`, `N/A`, `n/a 2024`.
_RE_NON_DISPONIBILE = re.compile(r"\bN\s*/?\s*A\s*((?:19|20)\d{2})?\b",
                                 re.IGNORECASE)


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

    # QUANDO IL PRIMO CAMPO È SOLO LA MARCA, IL MODELLO STA NELLA CODA.
    #
    # Segnalato dall'utente il 02/09/2026 con l'IMEI 352643332782672: la
    # pagina diceva di aver riconosciuto il telefono e poi mostrava
    # «Motorola», senza modello e senza scheda. La riga è
    # `MOTOROLA,35264333,"MOTOROLA, FOGO5G23"`: il primo campo è la marca,
    # e questa funzione lo prendeva per nome commerciale.
    #
    # Non è un caso isolato — è la forma di **156.375 righe su 248.373**,
    # misurate sul file vero, e quasi tutte (156.159) hanno la stessa
    # struttura: `MARCA, MARCA MODELLO`.
    #
    #     INFINIX, INFINIX NOTE 50      → «NOTE 50», un telefono del 2025
    #     ZTE, ZTE BLADE V40 DESIGN     → «BLADE V40 DESIGN»
    #     SAMSUNG, SAMSUNG E1195        → «E1195»
    #     LG, SKT X SCREEN              → «SKT X SCREEN» (la marca non si
    #                                      ripete: si tiene la coda intera)
    #
    # Il modello era lì, scritto, e veniva sostituito dal nome della marca.
    # Contava poco finché quelle righe stavano fuori dall'indice; da quando
    # si cercano anche nei file (v67) sono tutte raggiungibili, e questo
    # difetto è diventato quello che si vede.
    # IL CONFRONTO DEVE ESSERE «È SOLO LA MARCA», NON «CONTIENE LA MARCA».
    # Con `_same_words`, che accetta un insieme contenuto nell'altro,
    # «OPPO A74» risultava uguale a «OPPO» e questa riga si mangiava il
    # nome di mezzo database: misurato subito, `OPPO A74, Oppo CPH2219`
    # diventava «Cph2219».
    if len(parti) > 1 and _solo_la_marca(nome, brand):
        senza_marca = _senza_la_marca_davanti(coda, brand)
        if senza_marca:
            nome = senza_marca

    # E SE QUEL NOME È UN NOME IN CODICE, LO TRADUCIAMO: il dizionario ce
    # l'abbiamo già in casa.
    #
    # Il nome che esce dalla tabella è già scritto come lo scrive
    # Motorola («ThinkPhone», non «Thinkphone»), quindi salta il
    # correttore di maiuscole di `_best_name`: quello serve ai nomi
    # TUTTI MAIUSCOLI del database TAC, e su un nome verificato non
    # correggerebbe, rovinerebbe.
    da_codename = _nome_da_codename(nome)

    codice, anno = _split_code_and_year(coda or grezzo)

    # «N/A» VUOL DIRE «NON CE L'HO», e non è né un codice né un produttore.
    #
    # Quando il dataset non conosce il codice modello scrive `N/A` e ci
    # attacca l'anno: `HONOR 400 PRO, N/A2025`. Senza questa riga la coda
    # finiva intera nel campo «produttore», e la pagina scriveva «Honor
    # 400 Pro (N/A2025)» — una sigla che sembra un codice modello e non lo
    # è. L'anno invece è un dato vero e si tiene.
    coda_senza_na = _RE_NON_DISPONIBILE.sub(" ", coda)
    if anno is None:
        trovato = _RE_NON_DISPONIBILE.search(coda)
        if trovato and trovato.group(1):
            anno = trovato.group(1)

    # Produttore: la coda ripulita da codice e anno. Si scarta se ripete il
    # nome o il brand, per non mostrare due volte la stessa informazione.
    produttore = coda_senza_na
    for pezzo in filter(None, [(codice or "") + (anno or ""), codice, anno]):
        produttore = produttore.replace(pezzo, " ")
    produttore = " ".join(produttore.replace("-", " ").split())
    if produttore and (
        _same_words(produttore, nome) or _same_words(produttore, brand)
        or len(produttore) < 3
    ):
        produttore = ""

    return {
        "model": da_codename or _best_name(nome, codice),
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
    # UNA SIGLA RESTA COME L'HANNO SCRITTA. `prettify_model` mette le
    # maiuscole come le mette un nome commerciale — «FOGO5G23» diventa
    # «Fogo5g23», che non è né il dato del database né un nome di
    # telefono: sembra solo un errore di battitura dell'app. Una parola
    # sola con dentro lettere e cifre è una sigla (un codice interno, un
    # nome in codice), e di una sigla si riporta la grafia della fonte.
    pulito = " ".join((nome_grezzo or "").split())
    if (" " not in pulito and any(c.isdigit() for c in pulito)
            and any(c.isalpha() for c in pulito)):
        return pulito
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
    global _memory_index, _status, _pausa_servizio, _ultimo_esito
    _memory_index = None
    _status = "non ancora caricato"
    _ultimo_esito = None
    # Anche la pausa del servizio esterno: chi azzera le cache sta
    # rimettendo le cose in ordine, e una pausa presa cinque minuti fa non
    # deve far sembrare spento un servizio che magari è appena tornato.
    _pausa_servizio = {}
    # Anche la memoria delle seconde letture: chi azzera la cache lo fa
    # perché un dato è cambiato (`/tac/salva`), e un «non c'è» ricordato da
    # prima risponderebbe al posto del dato nuovo.
    _CACHE_SECONDE_LETTURE.clear()
