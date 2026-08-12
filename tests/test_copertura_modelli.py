"""Copertura per modello: dal nome commerciale al codice, e dal codice al
controllo versione ufficiale.

È il punto in cui l'applicazione mantiene o tradisce la sua promessa —
«dammi un telefono, ti dico a che versione è» — e per mesi l'ha tradita su
Samsung senza che si vedesse: il dataset conosceva 2332 codici `SM-`, il
controllo versione era già generico, ma chi cercava «Galaxy A55» non
otteneva nulla, perché il catalogo lo chiama «Galaxy A55 5G» e il confronto
era esatto. Dati presenti, meccanismo funzionante, risultato zero.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, modelcodes, sources, storage  # noqa: E402

# Dataset ridotto ma nella FORMA REALE del CSV di Google Play, comprese le
# righe che portano il suffisso di connettività nel nome commerciale.
CSV_PLAY = (
    "Retail Branding,Marketing Name,Device,Model\n"
    '"Samsung","Galaxy A55 5G","a55x","SM-A556B"\n'
    '"Samsung","Galaxy A55 5G","a55x","SM-A556E"\n'
    '"Samsung","Galaxy S24 Ultra","e3q","SM-S928B"\n'
    '"Samsung","Galaxy S24","dm1q","SM-S921B"\n'
    '"Samsung","Galaxy Z Flip6","b6q","SM-F741B"\n'
    '"Samsung","Galaxy M15 5G","m15x","SM-M156B"\n'
    '"Oppo","Find X9 Pro","OP5E8EL1","CPH2791"\n'
)


class BaseDataset(unittest.TestCase):
    """Un database PROPRIO, non quello che ha lasciato il file di test
    precedente.

    `modelcodes.resolve()` tiene la sua cache nella tabella `meta`, quindi
    tocca il database anche in un test che sembra parlare solo di CSV.
    Ereditando `C.DB_PATH` da chi ha girato prima si finiva a leggere un
    file che non era un database, e il guasto sembrava di questo file.
    """

    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._orig_download = modelcodes._download
        modelcodes._download = lambda url, key: (
            CSV_PLAY.encode("utf-8") if url == modelcodes.GOOGLE_PLAY_URL else None
        )
        modelcodes.reset_cache()
        modelcodes.resolve("")

    def tearDown(self):
        modelcodes._download = self._orig_download
        modelcodes.reset_cache()
        storage.reset_state()
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale


class TestNomeVersoCodice(BaseDataset):
    def test_nome_esatto(self):
        self.assertIn("SM-S928B", modelcodes.codes_for_name("Galaxy S24 Ultra"))

    def test_suffisso_di_connettivita_omesso_dall_utente(self):
        """IL CASO CHE MANCAVA. Il catalogo scrive «Galaxy A55 5G», le
        persone cercano «Galaxy A55»."""
        codici = modelcodes.codes_for_name("Galaxy A55")
        self.assertIn("SM-A556B", codici)

    def test_suffisso_scritto_dall_utente_ma_non_nel_catalogo(self):
        """E il caso opposto, per simmetria."""
        self.assertIn("SM-S921B", modelcodes.codes_for_name("Galaxy S24 5G"))

    def test_marca_davanti_al_nome(self):
        self.assertIn("SM-A556B", modelcodes.codes_for_name("Samsung Galaxy A55"))

    def test_le_gamme_non_si_fondono(self):
        """La tolleranza vale per le sigle di CONNETTIVITÀ, mai per quelle
        di gamma: unire «Galaxy S24» e «Galaxy S24 Ultra» restituirebbe il
        codice sbagliato, che è molto peggio di nessun codice perché un dato
        falso non si nota."""
        base = set(modelcodes.codes_for_name("Galaxy S24"))
        ultra = set(modelcodes.codes_for_name("Galaxy S24 Ultra"))
        self.assertTrue(base and ultra)
        self.assertFalse(base & ultra, "S24 e S24 Ultra condividono un codice")

    def test_nome_sconosciuto_non_inventa_codici(self):
        self.assertEqual(modelcodes.codes_for_name("Nokia 3310"), [])
        self.assertEqual(modelcodes.codes_for_name(""), [])

    def test_suffisso_non_divora_il_nome(self):
        """`_senza_suffissi` non deve ridurre a niente un nome che è tutto
        suffisso: «5G» da solo non è un modello."""
        self.assertEqual(modelcodes._senza_suffissi("5g"), "5g")


class TestParcoDiTestNellaScansione(unittest.TestCase):
    """Un modello nel parco di test dev'essere interrogato dalla scansione
    periodica anche se non è nella tabella scritta a mano — altrimenti chi
    lo segue non riceve mai una notifica, cioè esattamente lo scopo per cui
    l'ha aggiunto."""

    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._orig_download = modelcodes._download
        modelcodes._download = lambda url, key: (
            CSV_PLAY.encode("utf-8") if url == modelcodes.GOOGLE_PLAY_URL else None
        )
        modelcodes.reset_cache()
        modelcodes.resolve("")

    def tearDown(self):
        modelcodes._download = self._orig_download
        modelcodes.reset_cache()
        storage.reset_state()
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale

    def test_modello_seguito_entra_nella_scansione(self):
        base = {codice for codice, _ in sources.SAMSUNG_FUS_DEVICES}
        self.assertNotIn("SM-M156B", base,
                         "la tabella copre già l'M15: il test non prova più nulla")

        storage.add_to_watchlist("samsung|galaxym15", C.SAMSUNG, "Galaxy M15")
        codici = {codice for codice, _ in sources._samsung_da_controllare()}
        self.assertIn("SM-M156B", codici)

    def test_la_tabella_di_base_resta(self):
        codici = {codice for codice, _ in sources._samsung_da_controllare()}
        for codice, _nome in sources.SAMSUNG_FUS_DEVICES:
            self.assertIn(codice, codici)

    def test_nessun_duplicato(self):
        storage.add_to_watchlist("samsung|galaxys24ultra", C.SAMSUNG, "Galaxy S24 Ultra")
        coppie = sources._samsung_da_controllare()
        codici = [c for c, _ in coppie]
        self.assertEqual(len(codici), len(set(codici)))

    def test_altre_marche_ignorate(self):
        """Il controllo versione è quello di Samsung: un Oppo nel parco di
        test non deve farlo interrogare con un codice che non capisce."""
        storage.add_to_watchlist("oppo|findx9pro", C.OPPO, "Find X9 Pro")
        codici = {codice for codice, _ in sources._samsung_da_controllare()}
        self.assertNotIn("CPH2791", codici)

    def test_tetto_al_numero_di_modelli(self):
        """Una richiesta per modello, ogni ora: senza un tetto un parco di
        test grande allungherebbe la scansione senza limite."""
        for i in range(sources.SAMSUNG_WATCHLIST_MAX + 10):
            storage.add_to_watchlist(f"samsung|finto{i}", C.SAMSUNG, f"Galaxy A55")
        coppie = sources._samsung_da_controllare()
        aggiunti = len(coppie) - len(sources.SAMSUNG_FUS_DEVICES)
        self.assertLessEqual(aggiunti, sources.SAMSUNG_WATCHLIST_MAX)

    def test_database_non_pronto_non_rompe_la_scansione(self):
        originale = storage.get_watchlist
        storage.get_watchlist = lambda: (_ for _ in ()).throw(RuntimeError("db assente"))
        try:
            coppie = sources._samsung_da_controllare()
        finally:
            storage.get_watchlist = originale
        self.assertEqual(len(coppie), len(sources.SAMSUNG_FUS_DEVICES))


if __name__ == "__main__":
    unittest.main(verbosity=2)
