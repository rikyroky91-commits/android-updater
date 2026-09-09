"""Catalogo TAC su disco: nessuna connessione persistente o dizionario bulk.

Il file è una cache ricostruibile, separata dal backup degli account.
La costruzione è transazionale: i lettori vedono il vecchio catalogo oppure
quello nuovo, mai un'importazione parziale.
"""
from collections.abc import MutableMapping
from contextlib import closing
import os
import sqlite3


class TacIndex(MutableMapping):
    def __init__(self, path):
        self.path = os.path.abspath(path)

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        try:
            conn.execute("PRAGMA cache_size=-1024")
        except sqlite3.DatabaseError:
            conn.close()
            raise
        return conn

    def current(self, signature):
        if not os.path.isfile(self.path):
            return False
        try:
            with closing(self.connect()) as conn:
                row = conn.execute("SELECT signature FROM generation").fetchone()
                return bool(row and row[0] == signature)
        except sqlite3.DatabaseError:
            return False

    def rebuild(self, rows, signature):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        try:
            conn = self.connect()
        except sqlite3.DatabaseError:
            # È solo una cache ricostruibile, mai il database degli account.
            os.replace(self.path, self.path + ".corrupt")
            conn = self.connect()
        with closing(conn) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS catalog (tac TEXT PRIMARY KEY, cell TEXT NOT NULL) WITHOUT ROWID")
            conn.execute("CREATE TABLE IF NOT EXISTS generation (signature TEXT NOT NULL)")
            conn.execute("DELETE FROM catalog")
            conn.executemany(
                "INSERT INTO catalog(tac, cell) VALUES (?, ?) ON CONFLICT(tac) "
                "DO UPDATE SET cell=catalog.cell || char(30) || excluded.cell", rows)
            conn.execute("DELETE FROM generation")
            conn.execute("INSERT INTO generation VALUES (?)", (signature(),))

    def __getitem__(self, tac):
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT cell FROM catalog WHERE tac=?", (tac,)).fetchone()
        if row is None:
            raise KeyError(tac)
        return row[0]

    def __setitem__(self, tac, cell):
        with closing(self.connect()) as conn, conn:
            conn.execute("INSERT INTO catalog VALUES (?, ?) ON CONFLICT(tac) DO UPDATE SET cell=excluded.cell", (tac, cell))

    def __delitem__(self, tac):
        with closing(self.connect()) as conn, conn:
            if not conn.execute("DELETE FROM catalog WHERE tac=?", (tac,)).rowcount:
                raise KeyError(tac)

    def __iter__(self):
        with closing(self.connect()) as conn:
            for row in conn.execute("SELECT tac FROM catalog"):
                yield row[0]

    def __len__(self):
        with closing(self.connect()) as conn:
            return conn.execute("SELECT count(*) FROM catalog").fetchone()[0]

    def __bool__(self):
        # Nessun count(*) per ogni ricerca.
        return True
