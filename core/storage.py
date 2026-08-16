"""Persistenza su SQLite.

Sostituisce i quattro file JSON della versione precedente. Vantaggi concreti:

* scritture atomiche e concorrenti (thread di background + UI) senza lock manuali;
* storico per dispositivo interrogabile con una query invece che ricostruito
  a mano in memoria;
* dedup e retention gestite dal database;
* schema esplicito → niente più `AttributeError` da file con formato inatteso.

Il modulo usa solo la stdlib, quindi è testabile senza rete e senza Streamlit.
"""
from __future__ import annotations

import base64
import gzip
import re
import json
import sqlite3
import os
import threading
from datetime import datetime, timezone
from contextlib import contextmanager

from . import config as C
from .util import now_iso, utcnow

_local = threading.local()
_init_lock = threading.Lock()
# Incrementato ogni volta che il FILE del database cambia sotto i piedi.
_generazione = 0
_initialized: set[str] = set()
# Ultimo file messo da parte perché illeggibile, per poterlo dire a chi usa
# l'app invece di far sparire l'archivio senza spiegazioni.
_ultima_riparazione: str | None = None


def ultima_riparazione() -> str | None:
    """Il file messo da parte nell'ultima riparazione, o None."""
    return _ultima_riparazione

SCHEMA = """
CREATE TABLE IF NOT EXISTS updates (
    id              TEXT PRIMARY KEY,
    brand           TEXT NOT NULL,
    device_model    TEXT,
    device_key      TEXT,
    model_code      TEXT,
    title           TEXT NOT NULL,
    os_version      TEXT,
    android_version INTEGER,
    skin_name       TEXT,
    skin_version    TEXT,
    build           TEXT,
    patch_level     TEXT,
    severity        TEXT,
    color           TEXT,
    severity_reason TEXT,
    size_info       TEXT,
    link            TEXT,
    source          TEXT,
    source_label    TEXT,
    source_trust    TEXT,
    -- current/factory/support/beta/reported: only current enters the
    -- device view, history and notifications.
    firmware_kind   TEXT NOT NULL DEFAULT 'reported',
    published       TEXT,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    is_relevant     INTEGER NOT NULL DEFAULT 1,
    relevance_score INTEGER DEFAULT 0,
    relevance_note  TEXT,
    notified_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_updates_device ON updates(device_key);
CREATE INDEX IF NOT EXISTS idx_updates_brand  ON updates(brand);
CREATE INDEX IF NOT EXISTS idx_updates_seen   ON updates(first_seen);

CREATE TABLE IF NOT EXISTS watchlist (
    device_key TEXT PRIMARY KEY,
    brand      TEXT NOT NULL,
    model      TEXT NOT NULL,
    note       TEXT,
    added_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    update_id  TEXT,
    brand      TEXT,
    device     TEXT,
    version    TEXT,
    severity   TEXT,
    link       TEXT,
    kind       TEXT,
    ok         INTEGER,
    sent_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    total_found   INTEGER DEFAULT 0,
    new_items     INTEGER DEFAULT 0,
    notifications INTEGER DEFAULT 0,
    duration_s    REAL,
    error         TEXT
);

CREATE TABLE IF NOT EXISTS source_status (
    source      TEXT PRIMARY KEY,
    label       TEXT,
    ok          INTEGER,
    items_found INTEGER DEFAULT 0,
    last_error  TEXT,
    last_ok_at  TEXT,
    checked_at  TEXT
);

-- Quante voci ha restituito ciascuna fonte, scansione per scansione.
-- Serve a intercettare il guasto SILENZIOSO: una fonte che continua a
-- rispondere senza errori ma con molti meno dati di prima (il caso di
-- Xiaomi passata da 1276 a 40 voci resterebbe altrimenti invisibile,
-- perché formalmente la fonte è «verde»).
CREATE TABLE IF NOT EXISTS source_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    items_found INTEGER NOT NULL,
    ok          INTEGER NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_history ON source_history(source, id DESC);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Cronologia delle ricerche di modello: un rigo per ogni ricerca live che ha
-- trovato qualcosa, condensato a modello + firmware, per un riepilogo veloce
-- senza dover riaprire la scheda dispositivo completa.
CREATE TABLE IF NOT EXISTS search_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    query       TEXT NOT NULL,
    device_key  TEXT,
    brand       TEXT,
    model       TEXT NOT NULL,
    firmware    TEXT,
    link        TEXT,
    searched_at TEXT NOT NULL
);

-- Fotografia dello stato software al momento in cui si è dichiarato «testato».
-- È il riferimento contro cui si dice «cosa è cambiato da allora»: senza,
-- l'app sa dire solo qual è la versione attuale, che non è la domanda del QA.
-- Non viene MAI toccata da `rebuild_if_logic_changed`: è un dato inserito da
-- una persona, non il risultato dell'interpretazione di una fonte.
CREATE TABLE IF NOT EXISTS test_baseline (
    device_key      TEXT PRIMARY KEY,
    brand           TEXT,
    model           TEXT,
    os_version      TEXT,
    android_version INTEGER,
    build           TEXT,
    patch_level     TEXT,
    tested_at       TEXT NOT NULL,
    note            TEXT NOT NULL DEFAULT ''
);

-- Cache immagini modello (query di ricerca -> URL Wikipedia), per non
-- interrogare Wikipedia a ogni rerun di Streamlit per lo stesso modello.
CREATE TABLE IF NOT EXISTS device_images (
    query      TEXT PRIMARY KEY,
    image_url  TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL
);

-- Il nome commerciale scelto A MANO per un codice modello, quando i nomi
-- veri sono più di uno e nessuno è oggettivamente «il» nome — vedi il
-- docstring di `modelcodes.nome_canonico`. Stessa idea di `imeicheck.
-- aggiungi_tac` (una correzione verificata da una persona vince su ogni
-- fonte scaricata), applicata al nome invece che al modello di un TAC:
-- chi ha il telefono in mano lo sa meglio di qualsiasi euristica sul
-- dataset comunitario.
CREATE TABLE IF NOT EXISTS nomi_modello (
    codice      TEXT PRIMARY KEY,
    nome        TEXT NOT NULL,
    impostato_il TEXT NOT NULL
);

-- Accesso al parco di test: l'unica parte del sito dietro login. Uno
-- stato invece di un semplice booleano perché un account nasce sempre
-- «in_attesa» e non deve poter entrare finché l'amministratore non lo
-- porta ad «approvato» — vedi core/auth.py e web/account.py.
CREATE TABLE IF NOT EXISTS utenti (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    username          TEXT NOT NULL UNIQUE,
    email             TEXT NOT NULL,
    password_hash     TEXT NOT NULL,
    admin             INTEGER NOT NULL DEFAULT 0,
    stato             TEXT NOT NULL DEFAULT 'in_attesa',
    creato_il         TEXT NOT NULL,
    approvato_il      TEXT,
    tentativi_falliti INTEGER NOT NULL DEFAULT 0,
    bloccato_fino_a   TEXT
);

-- Allegati delle righe del parco di test: QUI CI SONO SOLO I METADATI.
-- Il contenuto del file vive fuori da questo database (vedi
-- core/allegati.py), e non per pignoleria: il salvataggio esterno
-- ricarica ogni volta l'INTERO file del database, quindi una foto messa
-- qui dentro verrebbe rispedita per intero a ogni salvataggio, per
-- sempre. Con i metadati separati dal contenuto, il database resta
-- piccolo e un allegato si carica una volta sola.
CREATE TABLE IF NOT EXISTS allegati_parco (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_key  TEXT NOT NULL,
    nome        TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    byte        INTEGER NOT NULL,
    -- Il nome con cui il contenuto è conservato nell'archivio esterno.
    -- È l'impronta del contenuto, non il nome scelto da chi carica: due
    -- file identici occupano un posto solo, e un nome con caratteri
    -- strani non può rompere l'archivio.
    impronta    TEXT NOT NULL,
    caricato_il TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_allegati_device ON allegati_parco(device_key);

-- La richiesta di approvazione inviata via email. Il link porta un token
-- generato con secrets.token_urlsafe: qui si conserva solo il suo hash
-- SHA-256, mai il valore in chiaro, con lo stesso principio delle
-- password — una lettura del database non basta a fabbricare
-- un'approvazione (vedi core/auth.py).
CREATE TABLE IF NOT EXISTS richieste_accesso (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    utente_id   INTEGER NOT NULL,
    token_hash  TEXT NOT NULL,
    scade_il    TEXT NOT NULL,
    usata       INTEGER NOT NULL DEFAULT 0,
    creata_il   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_richieste_utente ON richieste_accesso(utente_id);
"""


def integrita_file(percorso: str) -> str | None:
    """None se QUEL file è un database sano, altrimenti il motivo.

    Vale per un file qualsiasi, non solo per quello in uso: serve a
    controllare una copia **prima** di installarla al posto del database
    buono. Un archivio esterno che contiene una copia danneggiata la
    rimetterebbe altrimenti al suo posto a ogni avvio, e il guasto
    tornerebbe da solo dopo ogni riparazione.

    `quick_check` costa una frazione di `integrity_check` e trova gli
    stessi danni strutturali: abbastanza per decidere se il file è
    utilizzabile.
    """
    if not os.path.exists(percorso):
        return None
    try:
        conn = sqlite3.connect(percorso, timeout=5)
        try:
            esito = conn.execute("PRAGMA quick_check(1)").fetchone()
            # `quick_check` supera anche un file vuoto o troncato a zero:
            # è la lettura delle tabelle che rivela il guasto.
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return str(exc)
    except Exception:
        return None
    if esito and str(esito[0]).lower() != "ok":
        return str(esito[0])
    return None


def integrita() -> str | None:
    """None se il database in uso è sano, altrimenti il motivo del guasto."""
    return integrita_file(C.DB_PATH)


def ripara_se_corrotto() -> str | None:
    """Mette da parte un database illeggibile e riparte da uno vuoto.

    **Perché serve.** Un file corrotto fa fallire OGNI pagina: l'app
    diventa inutilizzabile finché qualcuno non la riavvia a mano, ed è
    esattamente quello che succedeva. Ma il danno è quasi sempre
    circoscritto al file, e l'archivio si ripopola da solo alla scansione
    successiva: insistere su un file rotto non recupera niente e blocca
    tutto.

    Il file guasto NON viene cancellato ma rinominato, perché è l'unica
    prova di cosa è andato storto e potrebbe contenere il parco di test.
    Ritorna il nome del file messo da parte, o None se non c'era nulla da
    riparare.
    """
    guasto = integrita()
    if not guasto:
        return None

    global _ultima_riparazione
    reset_state()
    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    da_parte = f"{C.DB_PATH}.corrotto-{marca}"
    try:
        os.replace(C.DB_PATH, da_parte)
    except OSError:
        return None
    # UNA RIPARAZIONE SILENZIOSA È UN DATO PERSO SENZA SPIEGAZIONE.
    # Da quando la riparazione può scattare in qualunque momento — non più
    # solo all'avvio — chi usa l'app potrebbe vedere l'archivio tornare
    # vuoto senza che nessuno gliene dica il motivo. L'evento resta qui, e
    # l'interfaccia lo riporta.
    _ultima_riparazione = da_parte
    # I giornali appartengono al file appena messo da parte: lasciarli qui
    # farebbe applicare a un database nuovo le transazioni di uno vecchio,
    # che è il modo più rapido di corromperlo di nuovo.
    for coda in ("-wal", "-shm", "-journal"):
        try:
            os.remove(C.DB_PATH + coda)
        except OSError:
            pass
    return da_parte


def connect() -> sqlite3.Connection:
    """Connessione per-thread (SQLite non ama le connessioni condivise).

    Il contatore di generazione serve al thread di scansione, che lavora
    in sottofondo e tiene una connessione sua. Quando il file viene
    sostituito — da un ripristino o da una riparazione — quella
    connessione punterebbe ancora al file di prima e continuerebbe a
    scriverci sopra, riportando in vita esattamente il guasto appena
    risolto. `reset_state()` incrementa il contatore; ogni thread se ne
    accorge alla prima operazione e riapre.
    """
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "generazione", -1) != _generazione:
        try:
            conn.close()
        except Exception:
            pass
        conn = None
        _local.conn = None
    if conn is None:
        try:
            conn = _apri()
        except sqlite3.DatabaseError:
            # IL FILE È ILLEGGIBILE, E QUI SI PUÒ ANCORA USCIRNE.
            #
            # Fino alla v41 la riparazione girava solo all'avvio, dentro
            # una funzione con la cache di Streamlit: un file che si
            # rompeva DOPO — durante una scansione, o perché l'archivio
            # esterno ne ha rimesso al suo posto uno guasto — non veniva
            # più riparato per tutta la vita del processo. Ogni pagina
            # falliva, e l'unica via d'uscita era riavviare a mano.
            #
            # Riparare qui vale per chiunque tocchi l'archivio, thread di
            # scansione compreso, e non dipende da quale pagina si stava
            # guardando.
            ripara_se_corrotto()
            conn = _apri()
        _local.conn = conn
        _local.generazione = _generazione
    try:
        init_db()
    except sqlite3.DatabaseError:
        # Alcuni danni non si vedono all'apertura ma alla prima lettura
        # dello schema: stessa via d'uscita, una volta sola.
        ripara_se_corrotto()
        conn = _apri()
        _local.conn = conn
        _local.generazione = _generazione
        init_db()
    return conn


def _apri() -> sqlite3.Connection:
    """Apre la connessione, e se qualcosa va storto NON lascia il file
    aperto.

    `sqlite3.connect()` riesce sempre — è la prima istruzione a toccare il
    contenuto che scopre un file illeggibile. Lasciare in giro quella
    connessione mezza aperta impedisce poi di spostare il file guasto:
    su Windows un file con un descrittore aperto non si rinomina, e la
    riparazione falliva in silenzio subito dopo aver capito cosa fare.
    """
    conn = sqlite3.connect(C.DB_PATH, timeout=30, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=15000")
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        raise
    return conn


def init_db() -> None:
    if C.DB_PATH in _initialized:
        return
    with _init_lock:
        if C.DB_PATH in _initialized:
            return
        conn = getattr(_local, "conn", None)
        if conn is None:  # pragma: no cover - percorso difensivo
            conn = sqlite3.connect(C.DB_PATH, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            _local.conn = conn
        conn.executescript(SCHEMA)
        # Migrazione difensiva: i database creati prima delle nuove colonne
        # non le hanno, e CREATE TABLE IF NOT EXISTS non le aggiunge da sola.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(updates)")}
        for colonna in ("source_trust", "model_code", "firmware_kind"):
            if colonna not in existing_cols:
                conn.execute(f"ALTER TABLE updates ADD COLUMN {colonna} TEXT")
        conn.commit()
        _initialized.add(C.DB_PATH)


def reset_state() -> None:
    """Chiude la connessione e segnala a tutti i thread di riaprire."""
    global _generazione, _ultima_riparazione
    _generazione += 1
    _initialized.clear()
    _ultima_riparazione = None
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def close_thread_connection() -> None:
    """Chiude solo la connessione SQLite del thread chiamante.

    I worker che preriscaldano i cataloghi restano vivi nel pool. Se uno di
    loro ha consultato la cache SQLite, tenere la connessione thread-local
    aperta non porta alcun vantaggio (il worker è inattivo) ma trattiene un
    file handle e memoria; su Windows impedisce anche la rimozione di un DB
    temporaneo. Il thread principale continua a usare la propria connessione
    tramite `connect()` come prima.
    """
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


@contextmanager
def transaction():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# Updates
# ----------------------------------------------------------------------
_UPDATE_FIELDS = [
    "id", "brand", "device_model", "device_key", "model_code", "title", "os_version",
    "android_version", "skin_name", "skin_version", "build", "patch_level",
    "severity", "color", "severity_reason", "size_info", "link", "source",
    "source_label", "source_trust", "firmware_kind", "published", "is_relevant", "relevance_score", "relevance_note",
]


def upsert_update(item: dict) -> bool:
    """Inserisce o aggiorna un item. Restituisce True se è la prima volta che lo vediamo."""
    now = now_iso()
    with transaction() as conn:
        existing = conn.execute("SELECT id FROM updates WHERE id = ?", (item["id"],)).fetchone()
        if existing:
            # Item già noto: aggiorniamo solo i campi che possono arricchirsi
            # (una seconda fonte può fornire la data o il build number mancante).
            conn.execute(
                """UPDATE updates
                      SET last_seen   = ?,
                          published   = COALESCE(published, ?),
                          link        = COALESCE(NULLIF(link, ''), ?),
                          build       = COALESCE(build, ?),
                          patch_level = COALESCE(patch_level, ?),
                          os_version  = COALESCE(NULLIF(os_version, ''), ?),
                          model_code  = COALESCE(model_code, ?)
                    WHERE id = ?""",
                (
                    now, item.get("published"), item.get("link"), item.get("build"),
                    item.get("patch_level"), item.get("os_version"),
                    item.get("model_code"), item["id"],
                ),
            )
            return False

        values = {k: item.get(k) for k in _UPDATE_FIELDS}
        # Retrocompatibilità per chi costruisce record interni (migrazioni,
        # test e import): prima dell'introduzione della colonna tali record
        # erano tutti firmware effettivi. Le fonti reali passano sempre la
        # semantica esplicita da `scan.normalize`.
        values["firmware_kind"] = item.get("firmware_kind") or C.FW_CURRENT
        values["is_relevant"] = 1 if item.get("is_relevant", True) else 0
        values["first_seen"] = item.get("first_seen") or now
        values["last_seen"] = now
        columns = ", ".join(values)
        placeholders = ", ".join(f":{k}" for k in values)
        conn.execute(f"INSERT INTO updates ({columns}) VALUES ({placeholders})", values)
        return True


def mark_notified(update_id: str) -> None:
    with transaction() as conn:
        conn.execute("UPDATE updates SET notified_at = ? WHERE id = ?", (now_iso(), update_id))


def is_notified(update_id: str) -> bool:
    conn = connect()
    row = conn.execute("SELECT notified_at FROM updates WHERE id = ?", (update_id,)).fetchone()
    return bool(row and row["notified_at"])


def clear_notified() -> int:
    with transaction() as conn:
        cur = conn.execute("UPDATE updates SET notified_at = NULL WHERE notified_at IS NOT NULL")
        return cur.rowcount


def parole_di_ricerca(search: str) -> list[str]:
    """Parole da cercare, ripulite dalle decorazioni.

    Le precisazioni fra parentesi vanno tolte: cercando «Oppo A6x
    (CPH2819)» la parola «cph2819» non compare in nessun campo del
    catalogo e ridurrebbe a zero i risultati, pur essendo il nome giusto.

    Pubblica (non `_parole_di_ricerca`) perché oltre alle query SQL qui
    sotto la usa anche `web/main.py::pagina_parco` per filtrare in
    Python la lista già caricata del parco di test — stessa
    tokenizzazione, nessuna query duplicata per un elenco che resta
    piccolo per costruzione.
    """
    senza_parentesi = re.sub(r"\([^)]*\)", " ", search or "")
    return [p for p in senza_parentesi.lower().split() if p]


def get_updates(
    *,
    brands: list[str] | None = None,
    severities: list[str] | None = None,
    device_key: str | None = None,
    only_relevant: bool = True,
    since_days: int | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    sql = ["SELECT * FROM updates WHERE 1=1"]
    params: list = []
    if only_relevant:
        sql.append("AND is_relevant = 1")
        # Un rollout riportato con una prova concreta resta utile quando
        # non esiste una build interrogabile. Non supera CURRENT nelle
        # viste per dispositivo; factory/support/beta non sono firmware.
        sql.append("AND firmware_kind IN ('current', 'reported')")
    if brands:
        sql.append(f"AND brand IN ({','.join('?' * len(brands))})")
        params += brands
    if severities:
        sql.append(f"AND severity IN ({','.join('?' * len(severities))})")
        params += severities
    if device_key:
        sql.append("AND device_key = ?")
        params.append(device_key)
    if since_days:
        sql.append("AND COALESCE(published, first_seen) >= datetime('now', ?)")
        params.append(f"-{int(since_days)} days")
    if search:
        for word in parole_di_ricerca(search):
            sql.append(
                "AND (LOWER(title) LIKE ? OR LOWER(COALESCE(device_model,'')) LIKE ? "
                "OR LOWER(COALESCE(build,'')) LIKE ? OR LOWER(brand) LIKE ?)"
            )
            needle = f"%{word}%"
            params += [needle, needle, needle, needle]
    # ORDINAMENTO PER DATA DI USCITA REALE.
    # Prima si ordinava per COALESCE(published, first_seen): così un
    # aggiornamento uscito mesi fa ma rilevato oggi finiva in cima, davanti
    # a uno uscito ieri. È esattamente l'opposto di quello che serve.
    # Ora le voci con una data di rilascio vera vengono per prime, in ordine
    # cronologico; quelle senza (i controlli di stato ufficiali, che non
    # pubblicano una data per release) vanno in coda, ordinate per
    # rilevazione, invece di essere mescolate come se fossero recenti.
    sql.append("ORDER BY (published IS NULL) ASC, published DESC, first_seen DESC")
    if limit:
        sql.append("LIMIT ?")
        params.append(int(limit))
    conn = connect()
    rows = rows_to_dicts(conn.execute(" ".join(sql), params).fetchall())
    for row in rows:
        # Alcune fonti "di stato attuale" (es. controllo versione ufficiale
        # Samsung/Honor) non hanno una data di rilascio propria: senza
        # questo flag, la data di rilevazione della scansione veniva
        # mostrata come se fosse la data di uscita dell'aggiornamento,
        # distorcendo panoramica e grafici (tutto sembrava "di oggi").
        row["published_is_estimated"] = row.get("published") is None
    return rows


def count_updates(only_relevant: bool = True) -> int:
    conn = connect()
    sql = ("SELECT COUNT(*) AS n FROM updates"
           + (" WHERE is_relevant = 1 AND firmware_kind IN ('current', 'reported')"
              if only_relevant else ""))
    return conn.execute(sql).fetchone()["n"]


# ----------------------------------------------------------------------
# Vista per dispositivo
# ----------------------------------------------------------------------
def get_devices(brands: list[str] | None = None, search: str | None = None) -> list[dict]:
    """Una riga per dispositivo, con l'ultimo aggiornamento noto.

    È la query che alimenta la schermata «Dispositivi»: per ogni modello dice
    qual è l'ultima versione arrivata, quando, e quanti update ha ricevuto
    negli ultimi 30/90 giorni.
    """
    sql = """
    WITH ranked AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY device_key
                   ORDER BY CASE firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                            (published IS NULL) ASC, published DESC, first_seen DESC
               ) AS rn
          FROM updates
         WHERE device_key IS NOT NULL AND device_key <> '' AND is_relevant = 1 AND firmware_kind IN ('current', 'reported')
    ),
    agg AS (
        SELECT device_key,
               COUNT(*) AS updates_total,
               SUM(CASE WHEN COALESCE(published, first_seen) >= datetime('now','-30 days') THEN 1 ELSE 0 END) AS updates_30d,
               SUM(CASE WHEN COALESCE(published, first_seen) >= datetime('now','-90 days') THEN 1 ELSE 0 END) AS updates_90d,
               MAX(COALESCE(published, first_seen)) AS last_update_at,
               -- TUTTI i nomi con cui questo telefono è stato visto, non
               -- solo quello della rilevazione più recente. Da quando le
               -- grafie diverse dello stesso modello convergono su una
               -- chiave sola («Galaxy S24 Ultra» e «Samsung S24 Ultra»),
               -- la ricerca deve trovarlo con qualunque di quelle grafie:
               -- filtrare sul solo nome vincente farebbe sparire il
               -- dispositivo per chi lo chiama con l'altro nome.
               GROUP_CONCAT(DISTINCT device_model) AS nomi_noti
          FROM updates
         WHERE device_key IS NOT NULL AND device_key <> '' AND is_relevant = 1 AND firmware_kind IN ('current', 'reported')
         GROUP BY device_key
    )
    SELECT r.device_key, r.brand,
           -- IL NOME LO SCEGLIE LA FONTE PIÙ AFFIDABILE, non la più
           -- recente. Quando due grafie dello stesso telefono si fondono
           -- in una riga sola, la scheda deve portare il nome ufficiale
           -- («Galaxy S24 Ultra») e non quello digitato in una ricerca
           -- («Samsung S24 Ultra»): è lo stesso criterio già usato qui
           -- sotto per versione, build e patch.
           COALESCE((SELECT u.device_model FROM updates u
                      WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.firmware_kind IN ('current', 'reported')
                        AND u.device_model IS NOT NULL AND u.device_model <> ''
                      ORDER BY CASE u.firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                               CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC,
                               COALESCE(u.published, u.first_seen) DESC LIMIT 1),
                    r.device_model) AS model,
           -- Valore più affidabile di ciascun campo: prima per affidabilità
           -- della fonte (una pagina ufficiale batte sempre una notizia
           -- generica, anche se quest'ultima è più recente), poi per data.
           -- Prima di questa correzione si sceglieva solo per data più
           -- recente, e una notizia rumorosa con un dato sbagliato poteva
           -- sovrascrivere quello corretto di una fonte ufficiale.
           COALESCE((SELECT u.os_version FROM updates u
                      WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.firmware_kind IN ('current', 'reported')
                        AND (u.android_version IS NOT NULL OR u.skin_name IS NOT NULL)
                      ORDER BY CASE u.firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                               CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC,
                               COALESCE(u.android_version, -1) DESC,
                               COALESCE(u.published, u.first_seen) DESC LIMIT 1),
                    r.os_version) AS os_version,
           (SELECT u.android_version FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.firmware_kind IN ('current', 'reported') AND u.android_version IS NOT NULL
             -- A PARITA' DI AFFIDABILITA' VINCE LA VERSIONE PIU' ALTA,
             -- non la piu' recentemente vista. Un telefono Android non
             -- torna indietro di major: se due fonti ugualmente
             -- affidabili dicono 11 e 13, quella giusta e' 13, anche se
             -- l'articolo che diceva 11 e' stato incontrato ieri.
             -- E' il difetto osservato su Galaxy A32 (SM-A325F), dato
             -- per Android 11 del 2021 quando era gia' su Android 13.
             -- L'ordine per affidabilita' resta PRIMA: una fonte
             -- ufficiale che dice 13 batte comunque una notizia che
             -- dice 14.
             ORDER BY CASE u.firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                               CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, u.android_version DESC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS android_version,
           (SELECT u.build FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.firmware_kind IN ('current', 'reported') AND u.build IS NOT NULL
             ORDER BY CASE u.firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                               CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS build,
           (SELECT u.patch_level FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.firmware_kind IN ('current', 'reported') AND u.patch_level IS NOT NULL
             ORDER BY CASE u.firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                               CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS patch_level,
           -- Il codice della variante da cui viene il dato. Serve al chip:
           -- risolto per codice è esatto, risolto per nome può solo dire
           -- «Exynos oppure Snapdragon». `app.chip_di()` lo leggeva già,
           -- ma la colonna non esisteva e la lettura era morta.
           (SELECT u.model_code FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.firmware_kind IN ('current', 'reported')
               AND u.model_code IS NOT NULL AND u.model_code <> ''
             ORDER BY CASE u.firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                               CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS model_code,
           -- Affidabilità della fonte che ha dato il dato "vincente" sopra:
           -- distingue per il chiamante un dato certo (catalogo Xiaomi,
           -- controllo ufficiale Samsung/Motorola/Honor) da uno dedotto da
           -- una notizia, così una ricerca live può fidarsi di quello che
           -- ha già in archivio invece di ripeterne la ricerca sul web.
           (SELECT u.source_trust FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.firmware_kind IN ('current', 'reported')
             ORDER BY CASE u.firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                               CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS best_source_trust,
           r.severity, r.color, r.link, r.title, r.source_label,
           a.updates_total, a.updates_30d, a.updates_90d, a.last_update_at,
           CASE WHEN w.device_key IS NULL THEN 0 ELSE 1 END AS watched,
           w.note AS watch_note
      FROM ranked r
      JOIN agg a ON a.device_key = r.device_key
      LEFT JOIN watchlist w ON w.device_key = r.device_key
     WHERE r.rn = 1
    """
    params: list = []
    if brands:
        sql += f" AND r.brand IN ({','.join('?' * len(brands))})"
        params += brands
    if search:
        # Ogni parola cercata deve comparire da qualche parte (modello o
        # marca), non l'intera frase come stringa letterale: altrimenti
        # "samsung s24" non troverebbe mai "Galaxy S24 Ultra" / "Samsung",
        # perché nessun singolo campo contiene quella frase esatta.
        # Si cerca in TUTTI i nomi noti del dispositivo, non solo in quello
        # mostrato: chi ha cercato «Samsung S24 Ultra» deve ritrovarlo
        # anche ora che la scheda si chiama «Galaxy S24 Ultra».
        for word in parole_di_ricerca(search):
            sql += " AND (LOWER(COALESCE(a.nomi_noti, r.device_model)) LIKE ? OR LOWER(r.brand) LIKE ?)"
            needle = f"%{word}%"
            params += [needle, needle]
    sql += " ORDER BY a.last_update_at DESC"
    conn = connect()
    return rows_to_dicts(conn.execute(sql, params).fetchall())


def get_device_history(device_key: str, limit: int = 50) -> list[dict]:
    conn = connect()
    rows = rows_to_dicts(
        conn.execute(
            """SELECT * FROM updates
                WHERE device_key = ? AND firmware_kind IN ('current', 'reported')
             ORDER BY CASE firmware_kind WHEN 'current' THEN 0 ELSE 1 END ASC,
                      (published IS NULL) ASC, published DESC, first_seen DESC
                LIMIT ?""",
            (device_key, limit),
        ).fetchall()
    )
    for row in rows:
        row["published_is_estimated"] = row.get("published") is None
    return rows


# ----------------------------------------------------------------------
# Watchlist (parco dispositivi di test)
# ----------------------------------------------------------------------
def add_to_watchlist(device_key: str, brand: str, model: str, note: str = "") -> None:
    with transaction() as conn:
        conn.execute(
            # Riaggiungere un modello già nel parco NON cancella la nota
            # che ci hai scritto sopra. Finché `note` era un campo che
            # nessuna pagina mostrava, sovrascriverlo con la stringa
            # vuota di `/parco/aggiungi` non si notava; da quando la nota
            # è una colonna che si compila a mano, sarebbe una perdita di
            # dati silenziosa al primo click sbagliato.
            """INSERT INTO watchlist (device_key, brand, model, note, added_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(device_key) DO UPDATE SET
                 note = CASE WHEN excluded.note <> '' THEN excluded.note
                             ELSE watchlist.note END""",
            (device_key, brand, model, note, now_iso()),
        )


def imposta_nota_parco(device_key: str, testo: str) -> None:
    """La nota libera della riga del parco. Solo per i modelli che nel
    parco ci sono già: scriverla su un device_key qualunque creerebbe
    righe fantasma senza marca né modello."""
    with transaction() as conn:
        conn.execute("UPDATE watchlist SET note = ? WHERE device_key = ?",
                     (testo, device_key))


def remove_from_watchlist(device_key: str) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM watchlist WHERE device_key = ?", (device_key,))


def get_watchlist() -> list[dict]:
    conn = connect()
    return rows_to_dicts(conn.execute("SELECT * FROM watchlist ORDER BY brand, model").fetchall())


def watched_keys() -> set[str]:
    conn = connect()
    return {r["device_key"] for r in conn.execute("SELECT device_key FROM watchlist").fetchall()}


# ----------------------------------------------------------------------
# Utenti e accesso al parco di test
# ----------------------------------------------------------------------
STATO_IN_ATTESA = "in_attesa"
STATO_APPROVATO = "approvato"
STATO_RIFIUTATO = "rifiutato"


def crea_utente(username: str, email: str, password_hash: str, *,
                 admin: bool = False, stato: str = STATO_IN_ATTESA) -> int:
    ora = now_iso()
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO utenti (username, email, password_hash, admin, stato,
                                    creato_il, approvato_il)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, email, password_hash, int(admin), stato, ora,
             ora if stato == STATO_APPROVATO else None),
        )
        return cur.lastrowid


def get_utente(utente_id: int) -> dict | None:
    conn = connect()
    riga = conn.execute("SELECT * FROM utenti WHERE id = ?", (utente_id,)).fetchone()
    return dict(riga) if riga else None


def get_utente_per_username(username: str) -> dict | None:
    """Case-insensitive: due username diversi solo per maiuscole
    creerebbero confusione, non due account distinti utili a qualcuno."""
    conn = connect()
    riga = conn.execute(
        "SELECT * FROM utenti WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    return dict(riga) if riga else None


def esiste_admin() -> bool:
    conn = connect()
    return conn.execute("SELECT 1 FROM utenti WHERE admin = 1 LIMIT 1").fetchone() is not None


def get_utenti_in_attesa() -> list[dict]:
    conn = connect()
    return rows_to_dicts(conn.execute(
        "SELECT * FROM utenti WHERE stato = ? ORDER BY creato_il", (STATO_IN_ATTESA,)
    ).fetchall())


def imposta_stato_utente(utente_id: int, stato: str) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE utenti SET stato = ?, approvato_il = ? WHERE id = ?",
            (stato, now_iso() if stato == STATO_APPROVATO else None, utente_id),
        )


def registra_tentativo_fallito(utente_id: int, blocca_fino_a: str | None) -> None:
    with transaction() as conn:
        conn.execute(
            """UPDATE utenti SET tentativi_falliti = tentativi_falliti + 1,
                                  bloccato_fino_a = ? WHERE id = ?""",
            (blocca_fino_a, utente_id),
        )


def reset_tentativi_falliti(utente_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE utenti SET tentativi_falliti = 0, bloccato_fino_a = NULL WHERE id = ?",
            (utente_id,),
        )


def imposta_password(utente_id: int, password_hash: str) -> None:
    with transaction() as conn:
        conn.execute("UPDATE utenti SET password_hash = ? WHERE id = ?",
                     (password_hash, utente_id))


def crea_richiesta_accesso(utente_id: int, token_hash: str, scade_il: str) -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO richieste_accesso (utente_id, token_hash, scade_il, creata_il)
               VALUES (?, ?, ?, ?)""",
            (utente_id, token_hash, scade_il, now_iso()),
        )
        return cur.lastrowid


def get_richiesta_accesso(richiesta_id: int) -> dict | None:
    conn = connect()
    riga = conn.execute(
        "SELECT * FROM richieste_accesso WHERE id = ?", (richiesta_id,)
    ).fetchone()
    return dict(riga) if riga else None


def segna_richiesta_usata(richiesta_id: int) -> None:
    with transaction() as conn:
        conn.execute("UPDATE richieste_accesso SET usata = 1 WHERE id = ?", (richiesta_id,))


# ----------------------------------------------------------------------
# Allegati del parco di test (solo metadati — vedi core/allegati.py)
# ----------------------------------------------------------------------
def aggiungi_allegato(device_key: str, nome: str, tipo: str, byte: int,
                      impronta: str) -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO allegati_parco (device_key, nome, tipo, byte, impronta, caricato_il)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (device_key, nome, tipo, byte, impronta, now_iso()),
        )
        return cur.lastrowid


def get_allegato(allegato_id: int) -> dict | None:
    conn = connect()
    riga = conn.execute(
        "SELECT * FROM allegati_parco WHERE id = ?", (allegato_id,)).fetchone()
    return dict(riga) if riga else None


def get_allegati_per_device() -> dict[str, list[dict]]:
    """Tutti gli allegati raggruppati per modello, in una query sola: la
    pagina del parco disegna molte righe e una query per riga sarebbe il
    solito moltiplicatore nascosto."""
    conn = connect()
    raggruppati: dict[str, list[dict]] = {}
    for riga in conn.execute(
            "SELECT * FROM allegati_parco ORDER BY caricato_il").fetchall():
        raggruppati.setdefault(riga["device_key"], []).append(dict(riga))
    return raggruppati


def elimina_allegato(allegato_id: int) -> dict | None:
    """Torna la riga eliminata, così chi chiama sa quale impronta può
    togliere dall'archivio esterno."""
    allegato = get_allegato(allegato_id)
    if not allegato:
        return None
    with transaction() as conn:
        conn.execute("DELETE FROM allegati_parco WHERE id = ?", (allegato_id,))
    return allegato


def impronta_ancora_usata(impronta: str) -> bool:
    """Due righe possono puntare allo stesso contenuto (lo stesso file
    allegato a due modelli): il contenuto si cancella dall'archivio
    esterno solo quando NESSUNA riga lo nomina più."""
    conn = connect()
    return conn.execute(
        "SELECT 1 FROM allegati_parco WHERE impronta = ? LIMIT 1", (impronta,)
    ).fetchone() is not None


# ----------------------------------------------------------------------
# Baseline di test («l'ultima volta che ho provato l'app su questo device»)
# ----------------------------------------------------------------------
def set_test_baseline(device: dict, note: str = "", tested_at: str | None = None) -> dict:
    """Fotografa lo stato software attuale di un dispositivo.

    `device` è una riga di `get_devices()`. Ogni nuova fotografia sostituisce
    la precedente: la domanda è sempre «cosa è cambiato dall'ULTIMA volta»,
    non dalla prima.
    """
    from .retest import snapshot

    stato = snapshot(device)
    riga = {
        "device_key": device["device_key"],
        "brand": device.get("brand"),
        "model": device.get("model") or device.get("device_model"),
        "tested_at": tested_at or now_iso(),
        "note": note or "",
        **stato,
    }
    with transaction() as conn:
        conn.execute(
            """INSERT INTO test_baseline
                   (device_key, brand, model, os_version, android_version,
                    build, patch_level, tested_at, note)
               VALUES (:device_key, :brand, :model, :os_version, :android_version,
                       :build, :patch_level, :tested_at, :note)
               ON CONFLICT(device_key) DO UPDATE SET
                   brand = excluded.brand, model = excluded.model,
                   os_version = excluded.os_version,
                   android_version = excluded.android_version,
                   build = excluded.build, patch_level = excluded.patch_level,
                   tested_at = excluded.tested_at, note = excluded.note""",
            riga,
        )
    return riga


def get_test_baseline(device_key: str) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM test_baseline WHERE device_key = ?", (device_key,)
    ).fetchone()
    return dict(row) if row else None


def get_test_baselines() -> dict[str, dict]:
    """Tutte le baseline, indicizzate per device_key (una sola query)."""
    conn = connect()
    return {
        r["device_key"]: dict(r)
        for r in conn.execute("SELECT * FROM test_baseline").fetchall()
    }


def clear_test_baseline(device_key: str) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM test_baseline WHERE device_key = ?", (device_key,))


# ----------------------------------------------------------------------
# Notifiche, scansioni, stato fonti
# ----------------------------------------------------------------------
def log_notification(item: dict, kind: str = "auto", ok: bool = True) -> None:
    with transaction() as conn:
        conn.execute(
            """INSERT INTO notifications (update_id, brand, device, version, severity, link, kind, ok, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.get("id"), item.get("brand"),
                item.get("device_model") or item.get("title"),
                item.get("os_version") or item.get("build") or "—",
                item.get("severity"), item.get("link"), kind, 1 if ok else 0, now_iso(),
            ),
        )


def get_notifications(limit: int = 50) -> list[dict]:
    conn = connect()
    return rows_to_dicts(
        conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    )


def log_search(query: str, item: dict) -> None:
    """Registra una ricerca di modello riuscita, condensata a modello +
    firmware. Chiamata una volta per ricerca (il risultato più recente
    trovato), non una volta per ogni notizia intercettata."""
    firmware = (
        item.get("os_version")
        or item.get("build")
        or (f"patch {item['patch_level']}" if item.get("patch_level") else None)
        or "—"
    )
    with transaction() as conn:
        conn.execute(
            """INSERT INTO search_log (query, device_key, brand, model, firmware, link, searched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                query, item.get("device_key"), item.get("brand"),
                item.get("device_model") or query, firmware,
                item.get("link"), now_iso(),
            ),
        )


def get_search_history(limit: int = 30) -> list[dict]:
    conn = connect()
    return rows_to_dicts(
        conn.execute(
            "SELECT * FROM search_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    )


def clear_search_history() -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM search_log")


def get_cached_image(query: str) -> str | None:
    """None = mai cercata prima. Stringa vuota = cercata, nessuna trovata."""
    conn = connect()
    row = conn.execute(
        "SELECT image_url FROM device_images WHERE query = ?", (query.lower().strip(),)
    ).fetchone()
    return row["image_url"] if row else None


def cache_image(query: str, image_url: str) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO device_images (query, image_url, fetched_at) VALUES (?, ?, ?)",
            (query.lower().strip(), image_url or "", now_iso()),
        )


# ----------------------------------------------------------------------
# Nomi commerciali corretti a mano (per codice modello)
# ----------------------------------------------------------------------
def set_nome_modello(codice: str, nome: str) -> None:
    """Salva il nome scelto a mano per un codice — vince su ogni fonte.

    Un nome vuoto (dopo `strip`) CANCELLA la correzione invece di
    salvarne una vuota: è la via per «torna a scegliere in automatico»,
    senza bisogno di una rotta separata.
    """
    codice_pulito = (codice or "").strip().upper()
    nome_pulito = (nome or "").strip()
    if not codice_pulito:
        return
    with transaction() as conn:
        if not nome_pulito:
            conn.execute("DELETE FROM nomi_modello WHERE codice = ?", (codice_pulito,))
            return
        conn.execute(
            """INSERT INTO nomi_modello (codice, nome, impostato_il)
               VALUES (?, ?, ?)
               ON CONFLICT(codice) DO UPDATE SET
                   nome = excluded.nome, impostato_il = excluded.impostato_il""",
            (codice_pulito, nome_pulito, now_iso()),
        )


def get_nome_modello(codice: str) -> str | None:
    """Il nome corretto a mano per questo codice, o None se non c'è."""
    codice_pulito = (codice or "").strip().upper()
    if not codice_pulito:
        return None
    conn = connect()
    row = conn.execute(
        "SELECT nome FROM nomi_modello WHERE codice = ?", (codice_pulito,)
    ).fetchone()
    return row["nome"] if row else None


def get_nomi_modello() -> dict[str, dict]:
    """Tutte le correzioni, indicizzate per codice — per la diagnostica."""
    conn = connect()
    return {
        row["codice"]: {"nome": row["nome"], "impostato_il": row["impostato_il"]}
        for row in conn.execute(
            "SELECT * FROM nomi_modello ORDER BY impostato_il DESC").fetchall()
    }


def start_scan() -> int:
    with transaction() as conn:
        cur = conn.execute("INSERT INTO scans (started_at) VALUES (?)", (now_iso(),))
        return cur.lastrowid


def finish_scan(scan_id: int, *, total: int, new_items: int, notifications: int,
                duration: float, error: str | None = None) -> None:
    with transaction() as conn:
        conn.execute(
            """UPDATE scans SET finished_at = ?, total_found = ?, new_items = ?,
                                notifications = ?, duration_s = ?, error = ?
                WHERE id = ?""",
            (now_iso(), total, new_items, notifications, duration, error, scan_id),
        )


def last_scan() -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM scans WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def get_scans(limit: int = 20) -> list[dict]:
    conn = connect()
    return rows_to_dicts(
        conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    )


def record_source_status(source: str, label: str, ok: bool, items_found: int, error: str | None) -> None:
    now = now_iso()
    with transaction() as conn:
        conn.execute(
            """INSERT INTO source_status (source, label, ok, items_found, last_error, last_ok_at, checked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source) DO UPDATE SET
                   label = excluded.label,
                   ok = excluded.ok,
                   items_found = excluded.items_found,
                   last_error = excluded.last_error,
                   last_ok_at = COALESCE(excluded.last_ok_at, source_status.last_ok_at),
                   checked_at = excluded.checked_at""",
            (source, label, 1 if ok else 0, items_found, error, now if ok else None, now),
        )


def get_source_status() -> list[dict]:
    conn = connect()
    righe = rows_to_dicts(
        conn.execute("SELECT * FROM source_status ORDER BY label").fetchall())
    for riga in righe:
        riga["degrado"] = _valuta_degrado(conn, riga)
    return righe


# Sotto questa soglia una fonte è considerata «impoverita»: ha restituito
# meno di questa frazione di quanto restituiva di norma.
_SOGLIA_DEGRADO = 0.5
# Numero di scansioni precedenti su cui calcolare il valore di riferimento.
_STORICO_CONFRONTO = 8
# Sotto questo numero di voci le variazioni percentuali non dicono nulla:
# una fonte che passa da 3 a 1 voce non è un guasto, è normale oscillazione.
_MINIMO_SIGNIFICATIVO = 10


def _valuta_degrado(conn, stato: dict) -> dict | None:
    """Verifica se una fonte rende molto meno del solito.

    È il guasto che sfugge a tutti i controlli: la fonte risponde, non dà
    errori, risulta verde — ma restituisce una frazione dei dati di prima
    perché il sito ha cambiato struttura e il riconoscimento coglie solo
    una parte delle righe.

    Il confronto è con la MEDIANA delle scansioni precedenti, non con
    l'ultima: un singolo giro andato male (una richiesta scaduta, un
    momento di rete lenta) non deve far gridare al guasto. La mediana
    ignora questi casi isolati, la media no.
    """
    if not stato.get("ok"):
        return None      # già segnalata come errore: non serve altro
    attuale = stato.get("items_found") or 0

    precedenti = [
        riga["items_found"] for riga in conn.execute(
            """SELECT items_found FROM source_history
                WHERE source = ? AND ok = 1
             ORDER BY id DESC LIMIT ?""",
            (stato["source"], _STORICO_CONFRONTO + 1),
        ).fetchall()
    ][1:]  # si esclude la rilevazione corrente

    if len(precedenti) < 3:
        return None      # storico troppo breve per dire qualcosa

    ordinati = sorted(precedenti)
    mediana = ordinati[len(ordinati) // 2]
    if mediana < _MINIMO_SIGNIFICATIVO:
        return None      # numeri troppo piccoli perché una percentuale abbia senso

    if attuale >= mediana * _SOGLIA_DEGRADO:
        return None

    calo = round((1 - attuale / mediana) * 100)
    return {
        "attuale": attuale,
        "atteso": mediana,
        "calo_percentuale": calo,
        "messaggio": (
            f"{attuale} voci invece delle {mediana} abituali (−{calo}%): "
            "la fonte risponde ma restituisce molti meno dati del solito, "
            "probabile cambio di formato della pagina"
        ),
    }


def record_source_history(source: str, items_found: int, ok: bool) -> None:
    """Annota quante voci ha dato questa fonte in questa scansione."""
    with transaction() as conn:
        conn.execute(
            "INSERT INTO source_history (source, items_found, ok, recorded_at) VALUES (?, ?, ?, ?)",
            (source, int(items_found), 1 if ok else 0, now_iso()),
        )
        # Si conservano solo le ultime rilevazioni per fonte: lo storico
        # serve al confronto, non all'archiviazione.
        conn.execute(
            """DELETE FROM source_history
                WHERE source = ? AND id NOT IN (
                      SELECT id FROM source_history WHERE source = ?
                   ORDER BY id DESC LIMIT ?)""",
            (source, source, _STORICO_CONFRONTO * 3),
        )


def get_source_history(source: str, limit: int = 20) -> list[dict]:
    conn = connect()
    return rows_to_dicts(conn.execute(
        """SELECT items_found, ok, recorded_at FROM source_history
            WHERE source = ? ORDER BY id DESC LIMIT ?""",
        (source, limit),
    ).fetchall())


def set_meta(key: str, value) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def get_meta(key: str, default=None):
    conn = connect()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------
# File scaricati messi in archivio
# ----------------------------------------------------------------------
def set_blob(key: str, dati: bytes) -> None:
    """Conserva un file scaricato dentro `meta`, COMPRESSO.

    **Perché non basta l'esadecimale.** Era la forma usata da tutti e tre i
    moduli che scaricano un dataset, e raddoppia la dimensione di ciò che
    conserva. Misurato sui file veri:

        catalogo Google Play      4,7 MB → 9,4 MB in archivio
        database TAC (xlsx)      10,7 MB → 21,4 MB
        dataset dei chip         12,2 MB → 24,5 MB
        codici MobileModels       0,9 MB → 1,7 MB
        database TAC storico      3,2 MB → 6,4 MB
                                          ───────
                                          63 MB dentro tracker.db

    E `tracker.db` non è un file qualsiasi: viene compresso e caricato su un
    Gist ogni mezz'ora, e committato ogni ora dal workflow di GitHub Actions
    — che su un file da 63 MB comincia a incontrare i limiti di GitHub.
    Compressi diventano 16 MB, di cui 13 sono l'xlsx, che è già un archivio
    compresso e non si comprime oltre.

    Non è solo una questione di spazio: ogni salvataggio riscrive tutto, e
    una scrittura lunga interrotta a metà è uno dei modi in cui un database
    SQLite diventa illeggibile.
    """
    set_meta(key, base64.b64encode(gzip.compress(dati, 6)).decode("ascii"))


def get_blob(key: str) -> bytes | None:
    """Rilegge un file conservato con `set_blob`.

    Accetta ANCHE il vecchio formato esadecimale: un'installazione già
    avviata ha in archivio quello, e senza questa tolleranza riscaricherebbe
    decine di megabyte al primo avvio, per nulla.
    """
    grezzo = get_meta(key)
    if not grezzo or not isinstance(grezzo, str):
        return None
    try:
        return gzip.decompress(base64.b64decode(grezzo))
    except Exception:
        try:
            return bytes.fromhex(grezzo)
        except ValueError:
            return None


# ----------------------------------------------------------------------
# Manutenzione
# ----------------------------------------------------------------------
def purge_old(days: int | None = None) -> int:
    days = days or C.RETENTION_DAYS
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM updates WHERE COALESCE(published, first_seen) < datetime('now', ?)",
            (f"-{int(days)} days",),
        )
        conn.execute("DELETE FROM notifications WHERE sent_at < datetime('now', ?)", (f"-{int(days)} days",))
        conn.execute("DELETE FROM scans WHERE started_at < datetime('now', ?)", (f"-{int(days)} days",))
        return cur.rowcount


_LOGIC_VERSION_KEY = "data_logic_version"


def rebuild_if_logic_changed() -> int:
    """Azzera gli aggiornamenti raccolti se sono stati interpretati da una
    versione precedente della logica di lettura delle fonti.

    I dati in archivio sono il RISULTATO dell'interpretazione delle fonti:
    correggere un errore di lettura senza rimuovere ciò che quell'errore
    aveva già prodotto lascia i valori sbagliati visibili per sempre. È
    quanto accaduto con iOS 26 attribuito a un iPhone 8: la correzione era
    attiva e la ricerca dava il dato giusto, ma la scheda dispositivo
    continuava a mostrare il vecchio valore rimasto in archivio.

    Non si perde nulla di irrecuperabile: gli aggiornamenti vengono
    ricostruiti alla prima scansione. Watchlist, storico notifiche,
    cronologia ricerche e **baseline di test** NON vengono toccati: sono
    dati inseriti da una persona, non il risultato dell'interpretazione di
    una fonte, e ricostruirli è impossibile.

    Conseguenza da tenere presente: fra l'azzeramento e la prima scansione
    il confronto con la baseline vede i campi vuoti. Non produce un falso
    «da ritestare» perché `core/retest.py` tratta un campo sparito come un
    buco di copertura, non come un cambiamento.
    """
    memorizzata = get_meta(_LOGIC_VERSION_KEY)
    if memorizzata == C.DATA_LOGIC_VERSION:
        return 0
    with transaction() as conn:
        cur = conn.execute("DELETE FROM updates")
        rimossi = cur.rowcount or 0
    set_meta(_LOGIC_VERSION_KEY, C.DATA_LOGIC_VERSION)
    return rimossi


# ----------------------------------------------------------------------
# Migrazione delle chiavi dispositivo
# ----------------------------------------------------------------------
_CHIAVI_KEY = "schema_chiavi_dispositivo"
# 1 → chiave = marca | nome ripulito dai separatori
# 2 → le parole di marca che non distinguono nulla escono dalla chiave,
#     così «Galaxy S24 Ultra» e «Samsung S24 Ultra» sono un telefono solo
_CHIAVI_VERSIONE = 2


def migra_chiavi_dispositivo() -> dict:
    """Ricalcola le chiavi dispositivo con la regola corrente.

    **Perché non basta azzerare gli aggiornamenti.** Cambiare la forma di
    `extract.device_key()` fa convergere le righe nuove, ma quelle già
    scritte restano com'erano — ed è esattamente il motivo per cui il
    doppione «Galaxy S24 Ultra» / «Samsung S24 Ultra» è sopravvissuto alla
    correzione del riconoscimento della marca: la logica era giusta, i dati
    no.

    Soprattutto, `rebuild_if_logic_changed()` NON tocca parco di test e
    baseline, e giustamente — sono dati inseriti da una persona. Ma quelle
    tabelle sono indicizzate proprio per chiave: senza questa migrazione un
    dispositivo seguito resterebbe agganciato a una chiave che non esiste
    più, cioè sparirebbe dal parco di test pur essendo ancora in archivio.

    Le collisioni sono il caso normale, non l'eccezione — è lo scopo
    dell'operazione — e si risolvono tenendo il dato più utile:
    per il parco di test l'iscrizione più vecchia (con la sua nota), per la
    baseline la fotografia più recente, perché la domanda è sempre «cosa è
    cambiato dall'ULTIMA volta».
    """
    from .extract import device_key

    esito = {"aggiornamenti": 0, "parco_di_test": 0, "baseline": 0, "ricerche": 0}
    if get_meta(_CHIAVI_KEY) == _CHIAVI_VERSIONE:
        return esito

    with transaction() as conn:
        # --- Aggiornamenti: la chiave si ricalcola riga per riga ---------
        righe = conn.execute(
            """SELECT id, brand, device_model, device_key FROM updates
                WHERE device_key IS NOT NULL AND device_key <> ''"""
        ).fetchall()
        for riga in righe:
            nuova = device_key(riga["brand"], riga["device_model"])
            if nuova and nuova != riga["device_key"]:
                conn.execute("UPDATE updates SET device_key = ? WHERE id = ?",
                             (nuova, riga["id"]))
                esito["aggiornamenti"] += 1

        # --- Parco di test: chiave primaria, quindi si riscrive ----------
        iscritti = rows_to_dicts(conn.execute("SELECT * FROM watchlist").fetchall())
        # La corrispondenza vecchia-chiave → nuova-chiave si raccoglie
        # QUI, prima che il ciclo sotto riscriva `device_key` dentro le
        # voci: dopo, l'originale non sarebbe più leggibile da nessuna
        # parte e gli allegati non saprebbero più chi seguire.
        rinomina: dict[str, str] = {}
        migliori: dict[str, dict] = {}
        for voce in iscritti:
            nuova = device_key(voce["brand"], voce["model"]) or voce["device_key"]
            if nuova != voce["device_key"]:
                rinomina[voce["device_key"]] = nuova
            voce["device_key"] = nuova
            precedente = migliori.get(nuova)
            if precedente is None:
                migliori[nuova] = voce
                continue
            # Vince l'iscrizione più vecchia: è quella con la storia.
            if (voce["added_at"] or "") < (precedente["added_at"] or ""):
                voce["note"] = voce["note"] or precedente["note"]
                migliori[nuova] = voce
            else:
                precedente["note"] = precedente["note"] or voce["note"]
        if iscritti:
            conn.execute("DELETE FROM watchlist")
            for voce in migliori.values():
                conn.execute(
                    """INSERT INTO watchlist (device_key, brand, model, note, added_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (voce["device_key"], voce["brand"], voce["model"],
                     voce["note"], voce["added_at"]),
                )
            esito["parco_di_test"] = len(iscritti) - len(migliori)

        # --- Allegati: seguono la riga del parco a cui appartengono ------
        # Sono indicizzati per chiave dispositivo come il parco, quindi
        # senza questo passaggio resterebbero agganciati a una chiave che
        # non esiste più: gli allegati sparirebbero dalla riga pur essendo
        # ancora nell'archivio esterno, esattamente il guasto che il
        # docstring qui sopra descrive per il parco di test.
        for vecchia, nuova in rinomina.items():
            conn.execute("UPDATE allegati_parco SET device_key = ? WHERE device_key = ?",
                         (nuova, vecchia))

        # --- Baseline di test: vince la fotografia più recente -----------
        baseline = rows_to_dicts(conn.execute("SELECT * FROM test_baseline").fetchall())
        recenti: dict[str, dict] = {}
        for voce in baseline:
            nuova = device_key(voce["brand"], voce["model"]) or voce["device_key"]
            voce["device_key"] = nuova
            precedente = recenti.get(nuova)
            if precedente is None or (voce["tested_at"] or "") > (precedente["tested_at"] or ""):
                recenti[nuova] = voce
        if baseline:
            conn.execute("DELETE FROM test_baseline")
            for voce in recenti.values():
                conn.execute(
                    """INSERT INTO test_baseline
                           (device_key, brand, model, os_version, android_version,
                            build, patch_level, tested_at, note)
                       VALUES (:device_key, :brand, :model, :os_version, :android_version,
                               :build, :patch_level, :tested_at, :note)""",
                    voce,
                )
            esito["baseline"] = len(baseline) - len(recenti)

        # --- Cronologia ricerche: nessun vincolo, aggiornamento diretto --
        for riga in conn.execute(
            "SELECT id, brand, model, device_key FROM search_log "
            "WHERE device_key IS NOT NULL AND device_key <> ''"
        ).fetchall():
            nuova = device_key(riga["brand"], riga["model"])
            if nuova and nuova != riga["device_key"]:
                conn.execute("UPDATE search_log SET device_key = ? WHERE id = ?",
                             (nuova, riga["id"]))
                esito["ricerche"] += 1

    set_meta(_CHIAVI_KEY, _CHIAVI_VERSIONE)
    return esito


def purge_retired_sources(valid_keys) -> int:
    """Rimuove le righe provenienti da fonti che non esistono più nel
    registro (una fonte sostituita lascerebbe altrimenti i suoi dati in
    archivio a tempo indefinito, senza più nessuno che li aggiorni).

    Pulisce ANCHE la tabella dello stato fonti: senza questo, una fonte
    ritirata resta visibile in Diagnostica con il suo ultimo errore per
    sempre, sembrando un guasto attuale quando in realtà non viene più
    nemmeno interrogata (è successo con la vecchia fonte Apple sostituita:
    mostrava un errore TLS di 35 minuti prima mentre tutte le altre fonti
    riportavano «pochi istanti fa»).
    """
    # `curated_lookup` e' nato con le fonti community (tracker ARB, canale
    # rollout): senza di lui nell'elenco, la pulizia delle fonti ritirate
    # cancellerebbe a ogni giro proprio i dispositivi che quelle fonti
    # sono le uniche a coprire.
    chiavi = list(dict.fromkeys(
        list(valid_keys) + ["live_search", "official_lookup", "curated_lookup"]))
    if not chiavi:
        return 0
    segnaposto = ",".join("?" * len(chiavi))
    with transaction() as conn:
        cur = conn.execute(
            f"DELETE FROM updates WHERE source IS NOT NULL AND source NOT IN ({segnaposto})",
            chiavi,
        )
        rimossi = cur.rowcount or 0
        conn.execute(
            f"DELETE FROM source_status WHERE source NOT IN ({segnaposto})",
            chiavi,
        )
        return rimossi


def stats() -> dict:
    conn = connect()
    row = conn.execute(
        """SELECT
              (SELECT COUNT(*) FROM updates WHERE is_relevant = 1) AS updates_relevant,
              (SELECT COUNT(*) FROM updates) AS updates_total,
              (SELECT COUNT(DISTINCT device_key) FROM updates
                WHERE device_key IS NOT NULL AND device_key <> '' AND is_relevant = 1 AND firmware_kind IN ('current', 'reported')) AS devices,
              (SELECT COUNT(*) FROM watchlist) AS watched,
              (SELECT COUNT(*) FROM notifications) AS notifications,
              (SELECT COUNT(*) FROM updates WHERE notified_at IS NOT NULL) AS notified_items
        """
    ).fetchone()
    data = dict(row)
    data["last_scan"] = last_scan()
    data["db_path"] = C.DB_PATH
    data["now"] = utcnow().isoformat()
    return data
