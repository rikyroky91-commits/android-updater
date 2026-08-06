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

import re
import json
import sqlite3
import threading
from contextlib import contextmanager

from . import config as C
from .util import now_iso, utcnow

_local = threading.local()
_init_lock = threading.Lock()
_initialized: set[str] = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS updates (
    id              TEXT PRIMARY KEY,
    brand           TEXT NOT NULL,
    device_model    TEXT,
    device_key      TEXT,
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
"""


def connect() -> sqlite3.Connection:
    """Connessione per-thread (SQLite non ama le connessioni condivise)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(C.DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=15000")
        _local.conn = conn
    init_db()
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
        # Migrazione difensiva: i database creati prima dell'introduzione di
        # `source_trust` non hanno questa colonna, e CREATE TABLE IF NOT
        # EXISTS non la aggiunge da sola a una tabella già esistente.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(updates)")}
        if "source_trust" not in existing_cols:
            conn.execute("ALTER TABLE updates ADD COLUMN source_trust TEXT")
        conn.commit()
        _initialized.add(C.DB_PATH)


def reset_state() -> None:
    """Usato dai test per forzare la reinizializzazione su un nuovo file."""
    _initialized.clear()
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
    "id", "brand", "device_model", "device_key", "title", "os_version",
    "android_version", "skin_name", "skin_version", "build", "patch_level",
    "severity", "color", "severity_reason", "size_info", "link", "source",
    "source_label", "source_trust", "published", "is_relevant", "relevance_score", "relevance_note",
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
                          os_version  = COALESCE(NULLIF(os_version, ''), ?)
                    WHERE id = ?""",
                (
                    now, item.get("published"), item.get("link"), item.get("build"),
                    item.get("patch_level"), item.get("os_version"), item["id"],
                ),
            )
            return False

        values = {k: item.get(k) for k in _UPDATE_FIELDS}
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


def _parole_di_ricerca(search: str) -> list[str]:
    """Parole da cercare, ripulite dalle decorazioni.

    Le precisazioni fra parentesi vanno tolte: cercando «Oppo A6x
    (CPH2819)» la parola «cph2819» non compare in nessun campo del
    catalogo e ridurrebbe a zero i risultati, pur essendo il nome giusto.
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
        for word in _parole_di_ricerca(search):
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
    sql = "SELECT COUNT(*) AS n FROM updates" + (" WHERE is_relevant = 1" if only_relevant else "")
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
                   ORDER BY (published IS NULL) ASC, published DESC, first_seen DESC
               ) AS rn
          FROM updates
         WHERE device_key IS NOT NULL AND device_key <> '' AND is_relevant = 1
    ),
    agg AS (
        SELECT device_key,
               COUNT(*) AS updates_total,
               SUM(CASE WHEN COALESCE(published, first_seen) >= datetime('now','-30 days') THEN 1 ELSE 0 END) AS updates_30d,
               SUM(CASE WHEN COALESCE(published, first_seen) >= datetime('now','-90 days') THEN 1 ELSE 0 END) AS updates_90d,
               MAX(COALESCE(published, first_seen)) AS last_update_at
          FROM updates
         WHERE device_key IS NOT NULL AND device_key <> '' AND is_relevant = 1
         GROUP BY device_key
    )
    SELECT r.device_key, r.brand, r.device_model AS model,
           -- Valore più affidabile di ciascun campo: prima per affidabilità
           -- della fonte (una pagina ufficiale batte sempre una notizia
           -- generica, anche se quest'ultima è più recente), poi per data.
           -- Prima di questa correzione si sceglieva solo per data più
           -- recente, e una notizia rumorosa con un dato sbagliato poteva
           -- sovrascrivere quello corretto di una fonte ufficiale.
           COALESCE((SELECT u.os_version FROM updates u
                      WHERE u.device_key = r.device_key AND u.is_relevant = 1
                        AND (u.android_version IS NOT NULL OR u.skin_name IS NOT NULL)
                      ORDER BY CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC,
                               COALESCE(u.android_version, -1) DESC,
                               COALESCE(u.published, u.first_seen) DESC LIMIT 1),
                    r.os_version) AS os_version,
           (SELECT u.android_version FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.android_version IS NOT NULL
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
             ORDER BY CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, u.android_version DESC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS android_version,
           (SELECT u.build FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.build IS NOT NULL
             ORDER BY CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS build,
           (SELECT u.patch_level FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1 AND u.patch_level IS NOT NULL
             ORDER BY CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS patch_level,
           -- Affidabilità della fonte che ha dato il dato "vincente" sopra:
           -- distingue per il chiamante un dato certo (catalogo Xiaomi,
           -- controllo ufficiale Samsung/Motorola/Honor) da uno dedotto da
           -- una notizia, così una ricerca live può fidarsi di quello che
           -- ha già in archivio invece di ripeterne la ricerca sul web.
           (SELECT u.source_trust FROM updates u
             WHERE u.device_key = r.device_key AND u.is_relevant = 1
             ORDER BY CASE u.source_trust WHEN 'structured' THEN 0 WHEN 'curated' THEN 1 WHEN 'noisy' THEN 2 ELSE 3 END ASC, COALESCE(u.published, u.first_seen) DESC LIMIT 1) AS best_source_trust,
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
        for word in _parole_di_ricerca(search):
            sql += " AND (LOWER(r.device_model) LIKE ? OR LOWER(r.brand) LIKE ?)"
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
                WHERE device_key = ?
             ORDER BY (published IS NULL) ASC, published DESC, first_seen DESC
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
            """INSERT INTO watchlist (device_key, brand, model, note, added_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(device_key) DO UPDATE SET note = excluded.note""",
            (device_key, brand, model, note, now_iso()),
        )


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
                WHERE device_key IS NOT NULL AND device_key <> '' AND is_relevant = 1) AS devices,
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
