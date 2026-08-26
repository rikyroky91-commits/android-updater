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

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

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
_memory_index: dict[str, list[tuple[str, str, str]]] | None = None
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
        tac = (riga.get("tac") or "").strip()
        marca = (riga.get("marca") or "").strip()
        modello = (riga.get("modello") or "").strip()
        if len(tac) == 8 and tac.isdigit() and (marca or modello):
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
            tac = str(row[i_tac] or "").strip()
            brand = str(row[i_brand] or "").strip()
            specs = str(row[i_specs] or "").strip()
            if len(tac) == 8 and tac.isdigit() and brand:
                index[tac] = (brand, specs)


def _indice_principale() -> dict[str, tuple[str, str]]:
    """La base dati principale, qualunque formato arrivi."""
    global _status
    indice = _leggi_base_principale(_cached_bytes())
    if indice:
        return indice

    # RIPIEGO SUL FOGLIO DI CALCOLO. Stesso dato, stesso repository: serve
    # solo se il CSV sparisse o cambiasse forma.
    grezzo = _cached_bytes_url(TAC_DB_XLSX_URL, _META_XLSX_BYTES, _META_XLSX_FETCHED)
    indice = _leggi_base_principale(grezzo)
    if indice:
        _status += " (dal foglio di calcolo, il CSV non era disponibile)"
        return indice

    # ULTIMA SPIAGGIA: LA COPIA CHE VIAGGIA NEL REPOSITORY.
    #
    # Fin qui ogni strada passava dalla rete. Il 17/08/2026 quella fonte
    # ha risposto `HTTP 429` e il risultato è stato che nessun IMEI veniva
    # più riconosciuto: un dato che esiste solo in rete è un dato che si
    # può perdere, e questo qui cambia raramente — sono codici assegnati
    # ai modelli, non notizie.
    #
    # La copia contiene la sola era Android (mezzo megabyte compresso, la
    # genera `scripts/aggiorna_istantanea_tac.py`) e resta l'ULTIMA delle
    # scelte: quando la rete risponde si usa il dato fresco, che conosce
    # anche i modelli usciti dopo l'ultima istantanea.
    indice = _istantanea_locale()
    if indice:
        _status += (f" — nessuna fonte in rete disponibile, si usa la copia "
                    f"nel repository ({len(indice)} TAC)")
    return indice


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
        if openpyxl is None:  # pragma: no cover
            return {}
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(grezzo), read_only=True,
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
    indice: dict[str, tuple[str, str]] = {}
    try:
        for riga in csv.DictReader(io.StringIO(testo or "")):
            tac = (riga.get("TAC") or riga.get("tac") or "").strip()
            marca = (riga.get("Brand") or riga.get("brand") or "").strip()
            specs = (riga.get("SPECS") or riga.get("specs") or "").strip()
            if len(tac) == 8 and tac.isdigit() and marca:
                indice[tac] = (marca, specs)
    except csv.Error:
        return {}
    return indice


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
    try:
        return anno is not None and int(anno) >= C.TAC_ANNO_MINIMO
    except (TypeError, ValueError):
        return False


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
    """
    global _status
    index: dict[str, list[tuple[str, str, str]]] = {}

    scartati = 0

    def aggiungi(fonte: str, voci: dict[str, tuple[str, str]],
                 filtrabile: bool = True) -> None:
        nonlocal scartati
        taglia = filtrabile and C.TAC_SOLO_ERA_ANDROID
        for tac, (marca, specs) in voci.items():
            # LE CORREZIONI UMANE NON SI FILTRANO MAI. Se qualcuno ha
            # inserito un TAC a mano, o è stato verificato nel repository,
            # quel dato è lì apposta: nessun criterio automatico può
            # decidere che non serviva.
            if taglia and tac not in index and not _dell_era_android(specs):
                scartati += 1
                continue
            index.setdefault(tac, []).append((fonte, marca, specs))

    # L'ordine delle chiamate È l'ordine di precedenza.
    inseriti = tac_inseriti()
    curati = _indice_curato()

    principale = _indice_principale()
    imeidb = _indice_imeidb()
    storica = _indice_fallback()

    aggiungi(FONTE_UTENTE, inseriti, filtrabile=False)
    aggiungi(FONTE_CURATA, curati, filtrabile=False)
    # Le risposte comprate al servizio esterno stanno sotto le verifiche
    # umane e sopra i database scaricati: sono puntuali e recenti, ma
    # restano di una fonte automatica. Non si filtrano per età — si sono
    # pagate proprio perché nessun altro conosceva quel TAC.
    aggiungi(FONTE_ESTERNA, tac_esterni(), filtrabile=False)
    aggiungi(FONTE_PRINCIPALE, principale)
    aggiungi(FONTE_IMEIDB, imeidb)
    aggiungi(FONTE_OSMOCOM, storica)

    # L'ordine di caricamento non è più una sentenza sul modello giusto.
    # Le correzioni umane restano assolute; fra le fonti pubbliche, invece,
    # si applica un punteggio riproducibile che premia riscontri indipendenti
    # e indicazioni esplicite di disponibilità europea.
    for tac, voci in index.items():
        index[tac] = _ordina_per_affidabilita(voci)

    if not index:
        _status = "file interpretato ma nessuna riga valida trovata (formato cambiato?)"
    else:
        nuovi_imeidb = len(set(imeidb) - set(principale))
        nuovi_storica = len(set(storica) - set(principale) - set(imeidb))
        _status += f" — {len(index)} codici TAC indicizzati"
        _status += f" · base principale {len(principale)}"
        if imeidb:
            _status += f" · IMEIDB {len(imeidb)} (+{nuovi_imeidb} nuovi)"
        if storica:
            _status += f" · storica {len(storica)} (+{nuovi_storica} nuovi)"
        if curati:
            _status += f" · {len(curati)} verificati a mano"
        if inseriti:
            _status += f" · {len(inseriti)} inseriti da te"
        if scartati:
            _status += (f" · {scartati} scartati perché anteriori ad Android 8 "
                        f"e senza codice modello")
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

    return carica_tac_osmocom(testo)


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
    indice: dict[str, tuple[str, str]] = {}
    righe = (testo or "").splitlines()
    inizio = None
    for i, riga in enumerate(righe[:10]):
        if riga.lower().replace(" ", "").startswith("tac,"):
            inizio = i
            break
    if inizio is None:
        return {}

    lettore = csv.reader(io.StringIO("\n".join(righe[inizio:])))
    next(lettore, None)      # l'intestazione, già individuata
    for riga in lettore:
        if len(riga) < 3:
            continue
        tac = str(riga[0] or "").strip()
        marca = str(riga[1] or "").strip()
        modello = str(riga[2] or "").strip()
        if len(tac) == 8 and tac.isdigit() and marca:
            indice[tac] = (marca, modello)
    return indice


def _indice_imeidb() -> dict[str, tuple[str, str]]:
    """Terza base dati TAC. Stesso spirito della seconda: buchi diversi.

    Misurata prima di essere adottata: 27 827 TAC, di cui 626 assenti dalla
    base principale. Poco — ma sono 626 telefoni che prima non si
    riconoscevano, per 1,1 MB.
    """
    raw = _cached_bytes_url(TAC_DB_IMEIDB_URL, _META_IMEIDB_BYTES,
                            _META_IMEIDB_FETCHED, minimo=100_000)
    if not raw:
        return {}
    return carica_tac_imeidb(raw.decode("utf-8", "replace"))


def carica_tac_imeidb(testo: str) -> dict[str, tuple[str, str]]:
    """`TAC,marca,modello,…` senza intestazione."""
    indice: dict[str, tuple[str, str]] = {}
    for riga in csv.reader(io.StringIO(testo or "")):
        if len(riga) < 3:
            continue
        tac = str(riga[0] or "").strip()
        marca = str(riga[1] or "").strip()
        modello = str(riga[2] or "").strip()
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
    """La chiave, dall'ambiente.

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
    if not _chiave_api():
        return ("non configurata — con una chiave in TAC_API_KEY i TAC che "
                "nessun database locale conosce vengono chiesti al servizio "
                "esterno (solo le 8 cifre del TAC, mai l'IMEI intero)")
    quante = len(tac_esterni())
    if not quante:
        return "chiave presente · nessun TAC ancora chiesto al servizio"
    return (f"chiave presente · {quante} TAC risolti dal servizio e conservati "
            f"(non verranno richiesti di nuovo)")


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


def cerca_tac_online_esito(tac: str) -> tuple[str, tuple[str, str] | None]:
    """Come `cerca_tac_online`, ma dice anche com'e' andata.

    Ritorna `("trovato", (marca, modello))`, `("assente", None)` quando il
    servizio ha risposto ed e' un no, oppure `("errore", None)` quando la
    domanda non e' nemmeno arrivata a destinazione o la risposta e'
    illeggibile.

    LA DIFFERENZA FRA «ASSENTE» E «ERRORE» E' TUTTO IL PUNTO. Solo il
    primo si puo' conservare: e' una risposta. Il secondo e' silenzio, e
    ricordare il silenzio come un no rende ignoto per un mese un
    telefono che il servizio conosce.
    """
    chiave = _chiave_api()
    if not chiave or requests is None:
        return ("errore", None)
    tac = "".join(c for c in (tac or "") if c.isdigit())[:8]
    if len(tac) != 8:
        return ("errore", None)

    try:
        risposta = requests.post(
            TAC_API_URL,
            json={"query": tac},
            headers={"X-Api-Key": chiave, "User-Agent": C.USER_AGENT},
            timeout=C.HTTP_TIMEOUT,
        )
    except Exception:
        return ("errore", None)
    stato = getattr(risposta, "status_code", 0)
    # 404 E' UNA RISPOSTA, NON UN GUASTO. Alcuni fornitori dicono «non ce
    # l'ho» con il codice HTTP invece che nel corpo: trattarlo come un
    # errore di rete significherebbe richiederlo — e pagarlo — per sempre.
    if stato == 404:
        return ("assente", None)
    if stato != 200:
        return ("errore", None)
    try:
        dati = risposta.json()
    except Exception:
        return ("errore", None)
    if not isinstance(dati, dict):
        return ("errore", None)

    corpo = dati.get("data") if isinstance(dati.get("data"), dict) else dati

    # Il servizio dichiara esplicitamente l'esito con `found`: quando c'è,
    # va creduto. Un `found: false` con i campi vuoti non è una risposta
    # da interpretare, è un no.
    if corpo.get("found") is False:
        return ("assente", None)

    marca = _testo_o_nome(corpo.get("brand") or corpo.get("manufacturer"))
    modello = _testo_o_nome(corpo.get("model"))
    if not marca and not modello:
        # Il servizio ha risposto 200 senza dire che telefono e': per
        # questo TAC non ha niente. E' un no, non un guasto.
        return ("assente", None)

    # Il chipset arriva solo con i piani a pagamento, ma se c'è si prende:
    # è esattamente il dato che manca altrove, e viene da chi identifica il
    # dispositivo, non da una tabella scritta a mano.
    chipset = _testo_o_nome(corpo.get("chipset"))
    if chipset:
        modello = f"{modello}, {chipset}".strip(", ")

    return ("trovato", (marca or "Sconosciuto", modello))


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


def is_imei_like(imei: str) -> bool:
    """True for a 15-digit value, even when the Luhn check digit is wrong.

    A transcription error in the last digit must not turn a TAC lookup into a
    model-name search: the first eight digits still identify the equipment
    type. Callers keep the Luhn result visible as a warning and never use the
    serial part for local identification.
    """
    digits = "".join(ch for ch in (imei or "") if ch.isdigit())
    return len(digits) == 15


def is_valid_imei(imei: str) -> bool:
    """Controllo Luhn standard sui 15 cifre di un IMEI (solo formato, non
    verifica se è realmente assegnato/attivo)."""
    digits = "".join(ch for ch in (imei or "") if ch.isdigit())
    if not is_imei_like(digits):
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
    return list((indice or {}).get(tac) or [])


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
            _memory_index.setdefault(tac, []).append(
                (FONTE_ESTERNA, esterno[0], esterno[1]))
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
