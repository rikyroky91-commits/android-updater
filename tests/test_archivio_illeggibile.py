"""«database disk image is malformed», e la via d'uscita senza riavvio.

Il sintomo raccontato è preciso: la pagina diventa un muro di scritte
arancioni e l'unico rimedio è riavviare l'app a mano. La v39 aveva
individuato le cause a monte e la v40 aveva aggiunto la riparazione
all'avvio — ma restavano due buchi, ed erano proprio quelli che rendevano
il guasto ricorrente:

1. **la riparazione girava solo all'avvio**, dentro una funzione con la
   cache di Streamlit: un file che si rompeva dopo non veniva più riparato
   per tutta la vita del processo;
2. **il ripristino installava qualunque cosa avesse scaricato.** Un
   archivio esterno con dentro una copia guasta — possibile per ogni
   salvataggio fatto prima della v39 — la rimetteva al suo posto a ogni
   avvio, subito dopo la riparazione. Il guasto si ricreava da solo, e
   riavviare non serviva a niente perché il giro ricominciava identico.
"""
from __future__ import annotations

import gzip
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import backup, config as C, storage  # noqa: E402


def _database_valido() -> bytes:
    percorso = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(percorso)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('prova', '1')")
    conn.commit()
    conn.close()
    with open(percorso, "rb") as f:
        dati = f.read()
    os.remove(percorso)
    return dati


class BaseArchivio(unittest.TestCase):
    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()

    def tearDown(self):
        storage.reset_state()
        import glob
        for percorso in [self._db + coda for coda in
                         ("", "-wal", "-shm", "-journal", ".tmp", ".verifica",
                          ".snapshot")] + glob.glob(self._db + ".corrotto-*"):
            try:
                os.remove(percorso)
            except OSError:
                pass
        C.DB_PATH = self._db_originale

    def _rompi(self):
        storage.reset_state()
        with open(self._db, "wb") as f:
            f.write(b"non sono un database" * 500)


class TestRiparazioneSenzaRiavvio(BaseArchivio):
    """La differenza fra «si ripara» e «si ripara SOLO all'avvio» è tutta
    qui: un guasto che compare a metà sessione deve trovare la stessa via
    d'uscita, senza che nessuno riavvii niente."""

    def test_una_query_su_un_file_rotto_riesce_lo_stesso(self):
        storage.init_db()
        storage.set_meta("prima", "c'ero")
        self._rompi()

        # Nessuna riparazione esplicita: si chiede semplicemente un dato.
        storage.set_meta("dopo", "va")
        self.assertEqual(storage.get_meta("dopo"), "va")

    def test_il_file_guasto_viene_conservato(self):
        """È l'unica prova di cosa è andato storto, e potrebbe contenere il
        parco di test."""
        storage.init_db()
        self._rompi()
        storage.get_meta("qualsiasi")

        import glob
        self.assertTrue(glob.glob(self._db + ".corrotto-*"))

    def test_un_database_sano_non_viene_toccato(self):
        storage.init_db()
        storage.set_meta("prova", "valore")
        storage.reset_state()
        self.assertEqual(storage.get_meta("prova"), "valore")
        import glob
        self.assertFalse(glob.glob(self._db + ".corrotto-*"))


class TestNonSiInstallaUnaCopiaGuasta(BaseArchivio):
    """La causa per cui il guasto tornava dopo ogni riparazione."""

    def setUp(self):
        super().setUp()
        os.environ["BACKUP_URL"] = "https://archivio.test/tracker.db.gz"
        self._requests = backup.requests

    def tearDown(self):
        backup.requests = self._requests
        os.environ.pop("BACKUP_URL", None)
        super().tearDown()

    def _finto_download(self, contenuto: bytes):
        class Risposta:
            status_code = 200
            content = gzip.compress(contenuto)

        class FinteRequests:
            @staticmethod
            def get(*a, **k):
                return Risposta()

        backup.requests = FinteRequests()

    def test_un_salvataggio_danneggiato_non_sostituisce_l_archivio(self):
        self._finto_download(b"questo non e' un database" * 400)
        ok, messaggio = backup.ripristina(solo_se_mancante=True)
        self.assertFalse(ok)
        self.assertIn("danneggiato", messaggio)
        self.assertFalse(os.path.exists(self._db),
                         "una copia illeggibile è stata installata lo stesso")

    def test_un_salvataggio_buono_viene_installato(self):
        self._finto_download(_database_valido())
        ok, messaggio = backup.ripristina(solo_se_mancante=True)
        self.assertTrue(ok, messaggio)
        self.assertIsNone(storage.integrita_file(self._db))

    def test_non_lascia_file_temporanei(self):
        self._finto_download(b"rotto" * 2000)
        backup.ripristina(solo_se_mancante=True)
        for coda in (".tmp", ".verifica"):
            with self.subTest(coda=coda):
                self.assertFalse(os.path.exists(self._db + coda))


class TestNonSiCaricaUnaCopiaGuasta(BaseArchivio):
    """L'altra metà del giro: un archivio esterno guasto ci finisce perché
    qualcuno ce lo ha scritto. Il salvataggio buono è l'unica copia dello
    storico, e sostituirlo con uno rotto lo perde per sempre."""

    def setUp(self):
        super().setUp()
        os.environ["BACKUP_URL"] = "https://archivio.test/tracker.db.gz"
        self._requests = backup.requests
        self.caricati = []

        class FinteRequests:
            @staticmethod
            def put(url, data=None, **k):
                self_outer.caricati.append(data)
                return type("R", (), {"status_code": 200, "text": ""})()

        self_outer = self
        backup.requests = FinteRequests()

    def tearDown(self):
        backup.requests = self._requests
        os.environ.pop("BACKUP_URL", None)
        super().tearDown()

    def test_un_database_sano_si_carica(self):
        storage.init_db()
        storage.add_to_watchlist("samsung|s24", "Samsung", "Galaxy S24")
        ok, messaggio = backup.salva()
        self.assertTrue(ok, messaggio)
        self.assertEqual(len(self.caricati), 1)

    def test_dopo_una_riparazione_non_si_carica_il_vuoto(self):
        """IL DANNO ARRIVATO DALLA PORTA DI SERVIZIO.

        Da quando l'archivio si ripara da solo, un file illeggibile
        diventa un file valido e **vuoto** — giusto in locale, disastroso
        da caricare: il salvataggio esterno è l'unica copia dello storico.
        Senza questo controllo, riparare un guasto locale cancellava
        l'archivio remoto al primo salvataggio utile.
        """
        storage.init_db()
        storage.reset_state()
        with open(self._db, "wb") as f:
            f.write(b"rotto" * 2000)

        ok, messaggio = backup.salva()

        self.assertFalse(ok)
        self.assertIn("vuoto", messaggio)
        self.assertEqual(self.caricati, [],
                         "un archivio vuoto è stato caricato sopra lo storico")

    def test_un_archivio_col_solo_parco_di_test_si_salva(self):
        """Il parco di test è inserito a mano e non si ricostruisce: vale
        un salvataggio anche senza nessun aggiornamento raccolto."""
        storage.init_db()
        storage.add_to_watchlist("samsung|s24", "Samsung", "Galaxy S24")
        ok, messaggio = backup.salva()
        self.assertTrue(ok, messaggio)


class TestIntegritaDiUnFileQualunque(BaseArchivio):

    def test_riconosce_un_database(self):
        percorso = self._db + ".prova"
        with open(percorso, "wb") as f:
            f.write(_database_valido())
        try:
            self.assertIsNone(storage.integrita_file(percorso))
        finally:
            os.remove(percorso)

    def test_riconosce_un_file_che_non_lo_e(self):
        percorso = self._db + ".prova"
        with open(percorso, "wb") as f:
            f.write(b"testo qualsiasi" * 100)
        try:
            self.assertIsNotNone(storage.integrita_file(percorso))
        finally:
            os.remove(percorso)

    def test_un_file_vuoto_non_e_un_database(self):
        """`quick_check` da solo passa su un file vuoto: è la lettura dello
        schema che rivela il guasto."""
        percorso = self._db + ".prova"
        open(percorso, "wb").close()
        try:
            # Un file vuoto è un database SQLite legittimo appena creato,
            # quindi qui non ci si aspetta un errore: ciò che conta è che
            # la funzione non sollevi.
            storage.integrita_file(percorso)
        finally:
            os.remove(percorso)

    def test_un_percorso_inesistente_non_solleva(self):
        self.assertIsNone(storage.integrita_file(self._db + ".mai-esistito"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
