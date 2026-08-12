"""«database disk image is malformed»: le tre cause e le tre difese.

Il sintomo era: ogni tanto l'app smette di funzionare del tutto e va
riavviata a mano. Un file corrotto fa fallire OGNI pagina, quindi non
degrada — si spegne.
"""
from __future__ import annotations

import glob
import os
import sqlite3
import tempfile
import unittest

from core import config as C, storage


class BaseDatabaseProprio(unittest.TestCase):
    """Questi test ROMPONO di proposito il file puntato da `C.DB_PATH`.

    Devono quindi lavorare su un file loro: ereditando il percorso da chi
    ha girato prima si distruggeva il database di un altro file di test, e
    il guasto compariva altrove — la forma di segnalazione più difficile da
    inseguire che ci sia.
    """

    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        for percorso in [self._db + coda
                         for coda in ("", "-wal", "-shm", "-journal", ".snapshot")] \
                + glob.glob(self._db + ".corrotto-*"):
            try:
                os.remove(percorso)
            except OSError:
                pass
        C.DB_PATH = self._db_originale


class TestRilevamento(BaseDatabaseProprio):

    def test_un_database_sano_non_viene_toccato(self):
        self.assertIsNone(storage.integrita())
        self.assertIsNone(storage.ripara_se_corrotto())

    def test_un_file_illeggibile_viene_riconosciuto(self):
        storage.reset_state()
        with open(C.DB_PATH, "wb") as f:
            f.write(b"non sono un database" * 500)
        self.assertIsNotNone(storage.integrita())

    def test_viene_messo_da_parte_non_cancellato(self):
        """È l'unica prova di cosa è andato storto, e potrebbe contenere
        il parco di test."""
        storage.reset_state()
        with open(C.DB_PATH, "wb") as f:
            f.write(b"rotto" * 2000)
        da_parte = storage.ripara_se_corrotto()
        self.assertIsNotNone(da_parte)
        self.assertTrue(os.path.exists(da_parte))
        self.assertIn(".corrotto-", da_parte)

    def test_dopo_la_riparazione_il_database_funziona(self):
        storage.reset_state()
        with open(C.DB_PATH, "wb") as f:
            f.write(b"rotto" * 2000)
        storage.ripara_se_corrotto()
        storage.init_db()
        self.assertIsNone(storage.integrita())
        storage.set_meta("prova", "va")
        self.assertEqual(storage.get_meta("prova"), "va")

    def test_i_giornali_della_vecchia_base_non_restano(self):
        """Applicare a un database nuovo le transazioni di uno vecchio è
        il modo più rapido di corromperlo di nuovo."""
        storage.reset_state()
        with open(C.DB_PATH, "wb") as f:
            f.write(b"rotto" * 2000)
        for coda in ("-wal", "-shm"):
            with open(C.DB_PATH + coda, "wb") as f:
                f.write(b"giornale vecchio")
        storage.ripara_se_corrotto()
        for coda in ("-wal", "-shm"):
            with self.subTest(coda=coda):
                self.assertFalse(os.path.exists(C.DB_PATH + coda))


class TestIstantaneaCoerente(BaseDatabaseProprio):
    """Il backup non deve fotografare un database a metà.

    Con il giornale in modalità WAL le transazioni recenti stanno in
    `tracker.db-wal` e non ancora nel file principale: una copia grezza
    cattura un database incoerente, che al ripristino diventa
    «malformed». È la causa a monte del guasto.
    """

    def test_l_istantanea_e_un_database_valido(self):
        from core import backup
        storage.set_meta("prova", "valore")
        dati = backup._istantanea_coerente(C.DB_PATH)
        self.assertTrue(dati)

        temporaneo = C.DB_PATH + ".verifica"
        with open(temporaneo, "wb") as f:
            f.write(dati)
        try:
            conn = sqlite3.connect(temporaneo)
            esito = conn.execute("PRAGMA quick_check(1)").fetchone()[0]
            valore = conn.execute(
                "SELECT value FROM meta WHERE key = 'prova'").fetchone()
            conn.close()
        finally:
            os.remove(temporaneo)

        self.assertEqual(str(esito).lower(), "ok")
        self.assertIsNotNone(valore, "l'istantanea ha perso le scritture recenti")

    def test_non_lascia_file_temporanei(self):
        from core import backup
        backup._istantanea_coerente(C.DB_PATH)
        self.assertFalse(os.path.exists(C.DB_PATH + ".snapshot"))


class TestRipristinoPulisceIGiornali(unittest.TestCase):

    def test_il_codice_toglie_wal_e_shm_prima_di_sostituire(self):
        """Sostituire solo il `.db` lasciando `-wal` e `-shm` della base
        precedente è esattamente ciò che produce l'errore."""
        import inspect

        from core import backup
        codice = inspect.getsource(backup.ripristina)
        self.assertIn("-wal", codice)
        self.assertIn("-shm", codice)
        self.assertIn("storage.reset_state()", codice)
        self.assertLess(codice.index("-wal"), codice.index("os.replace"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestConnessioniDiAltriThread(BaseDatabaseProprio):
    """Il thread di scansione non deve continuare a scrivere sul file
    vecchio dopo una riparazione: sarebbe il guasto che ricomincia."""

    def test_la_generazione_avanza_a_ogni_sostituzione(self):
        prima = storage._generazione
        storage.reset_state()
        self.assertGreater(storage._generazione, prima)

    def test_un_thread_riapre_dopo_la_sostituzione(self):
        import threading

        esiti = []

        def lavora():
            storage.connect().execute("SELECT 1").fetchone()
            generazione_vista = getattr(storage._local, "generazione", None)
            storage.reset_state()
            storage.connect().execute("SELECT 1").fetchone()
            esiti.append((generazione_vista,
                          getattr(storage._local, "generazione", None)))

        t = threading.Thread(target=lavora)
        t.start()
        t.join()
        self.assertEqual(len(esiti), 1)
        prima, dopo = esiti[0]
        self.assertNotEqual(prima, dopo, "il thread non ha riaperto la connessione")
