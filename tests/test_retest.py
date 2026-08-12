"""«Cosa è cambiato dall'ultima volta che ho testato».

Il test che conta di più qui è
`test_una_versione_che_retrocede_e_un_dato_incoerente`: fissa per iscritto
che un telefono non torna indietro, e che quando l'archivio dice il
contrario la risposta giusta è mostrarlo, non sceglierne una delle due in
silenzio.

Subito dopo viene `test_un_campo_sparito_non_e_un_aggiornamento`: senza
quella regola bastava una fonte con una giornata storta per far comparire
«da ritestare» su tutto il parco.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, retest, storage  # noqa: E402


def device(**campi) -> dict:
    base = {
        "device_key": "samsung|galaxy-s24-ultra",
        "brand": C.SAMSUNG,
        "model": "Galaxy S24 Ultra",
        "android_version": 15,
        "os_version": "One UI 7.0",
        "build": "S928BXXU5CYA1",
        "patch_level": "2026-05-01",
    }
    base.update(campi)
    return base


def baseline(**campi) -> dict:
    base = device()
    base["tested_at"] = "2026-06-01T10:00:00"
    base["note"] = ""
    base.update(campi)
    return base


class TestConfronto(unittest.TestCase):
    def test_senza_baseline_lo_stato_e_mai_testato(self):
        esito = retest.confronta(device(), None)
        self.assertEqual(esito["stato"], retest.MAI_TESTATO)
        self.assertEqual(esito["cambiamenti"], [])

    def test_nessun_cambiamento(self):
        esito = retest.confronta(device(), baseline())
        self.assertEqual(esito["stato"], retest.INVARIATO)
        self.assertEqual(esito["azione"], "Nessun retest necessario")

    def test_salto_di_android_e_major(self):
        esito = retest.confronta(
            device(android_version=16, os_version="One UI 8.0"), baseline())
        self.assertEqual(esito["stato"], retest.DA_RITESTARE)
        self.assertEqual(esito["severita"], C.SEV_MAJOR)
        self.assertIn("Android 15 → 16", esito["riassunto"])

    def test_solo_la_build_cambia_e_feature(self):
        esito = retest.confronta(device(build="S928BXXU6DYB2"), baseline())
        self.assertEqual(esito["stato"], retest.DA_RITESTARE)
        self.assertEqual(esito["severita"], C.SEV_FEATURE)

    def test_solo_la_patch_cambia_e_security(self):
        esito = retest.confronta(device(patch_level="2026-07-01"), baseline())
        self.assertEqual(esito["stato"], retest.DA_RITESTARE)
        self.assertEqual(esito["severita"], C.SEV_SECURITY)
        self.assertEqual(len(esito["cambiamenti"]), 1)

    def test_vince_il_cambiamento_piu_grave(self):
        """Patch e Android cambiano insieme: l'azione da suggerire è quella
        del cambiamento più profondo, non la media né l'ultimo trovato."""
        esito = retest.confronta(
            device(android_version=16, os_version="One UI 8.0",
                   build="S928BXXU6DYB2", patch_level="2026-07-01"),
            baseline(),
        )
        self.assertEqual(esito["severita"], C.SEV_MAJOR)
        self.assertEqual(len(esito["cambiamenti"]), 4)

    def test_ritocco_di_skin_non_e_un_salto_di_versione(self):
        """One UI 7.0 → 7.0.1 non è One UI 7 → 8: stessa cifra principale,
        quindi smoke test e non retest completo."""
        esito = retest.confronta(device(os_version="One UI 7.0.1"), baseline())
        self.assertEqual(esito["severita"], C.SEV_FEATURE)

    def test_salto_di_skin_a_parita_di_android_e_major(self):
        esito = retest.confronta(device(os_version="One UI 8.0"), baseline())
        self.assertEqual(esito["severita"], C.SEV_MAJOR)


class TestDatiSospetti(unittest.TestCase):
    def test_una_versione_che_retrocede_e_un_dato_incoerente(self):
        """Un telefono non torna a una versione precedente. Se l'archivio lo
        dice, il dato è sbagliato — e va mostrato, non scelto in silenzio."""
        esito = retest.confronta(device(android_version=14), baseline())
        self.assertEqual(esito["stato"], retest.INCOERENTE)
        self.assertIsNone(esito["severita"])
        self.assertIn("15 → 14", esito["riassunto"])
        self.assertIn("non torna", esito["azione"])

    def test_anche_la_patch_che_retrocede_e_incoerente(self):
        esito = retest.confronta(device(patch_level="2026-03-01"), baseline())
        self.assertEqual(esito["stato"], retest.INCOERENTE)

    def test_una_patch_in_forma_non_riconosciuta_non_inventa_un_ordine(self):
        """`July 2026` non si confronta con `2026-05-01` senza interpretare:
        meglio registrare un cambiamento che affermare una regressione."""
        esito = retest.confronta(device(patch_level="July 2026"), baseline())
        self.assertEqual(esito["stato"], retest.DA_RITESTARE)

    def test_la_build_non_produce_mai_una_regressione(self):
        """Il formato delle build cambia fra generazioni e regioni: un
        ordinamento alfabetico non descrive nessuna realtà."""
        esito = retest.confronta(device(build="AAA000"), baseline())
        self.assertEqual(esito["stato"], retest.DA_RITESTARE)

    def test_un_campo_sparito_non_e_un_aggiornamento(self):
        """Una fonte che smette di pubblicare la build non aggiorna il
        telefono: sarebbe un «da ritestare» a ogni giornata storta."""
        esito = retest.confronta(device(build=None, patch_level=""), baseline())
        self.assertEqual(esito["stato"], retest.INVARIATO)
        self.assertEqual(esito["mancanti"], ["Build", "Patch"])

    def test_archivio_appena_azzerato_non_produce_falsi_retest(self):
        """Fra `rebuild_if_logic_changed` e la prima scansione i campi sono
        tutti vuoti: non deve diventare «tutto il parco da ritestare»."""
        vuoto = device(android_version=None, os_version=None,
                       build=None, patch_level=None)
        esito = retest.confronta(vuoto, baseline())
        self.assertEqual(esito["stato"], retest.INVARIATO)
        self.assertEqual(len(esito["mancanti"]), 4)


class TestPersistenza(unittest.TestCase):
    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_salvataggio_e_rilettura(self):
        storage.set_test_baseline(device(), note="provato con la build 42")
        letta = storage.get_test_baseline("samsung|galaxy-s24-ultra")
        self.assertEqual(letta["android_version"], 15)
        self.assertEqual(letta["build"], "S928BXXU5CYA1")
        self.assertEqual(letta["note"], "provato con la build 42")
        self.assertTrue(letta["tested_at"])

    def test_una_nuova_fotografia_sostituisce_la_precedente(self):
        """La domanda è sempre «cosa è cambiato dall'ULTIMA volta»."""
        storage.set_test_baseline(device())
        storage.set_test_baseline(device(android_version=16, os_version="One UI 8.0"))
        letta = storage.get_test_baseline("samsung|galaxy-s24-ultra")
        self.assertEqual(letta["android_version"], 16)
        self.assertEqual(
            retest.confronta(device(android_version=16, os_version="One UI 8.0"),
                             letta)["stato"],
            retest.INVARIATO,
        )

    def test_cancellazione(self):
        storage.set_test_baseline(device())
        storage.clear_test_baseline("samsung|galaxy-s24-ultra")
        self.assertIsNone(storage.get_test_baseline("samsung|galaxy-s24-ultra"))

    def test_l_azzeramento_della_logica_non_tocca_le_baseline(self):
        """`rebuild_if_logic_changed` cancella gli aggiornamenti raccolti,
        che si ricostruiscono. La baseline no: l'ha inserita una persona."""
        storage.set_test_baseline(device())
        storage.set_meta("data_logic_version", C.DATA_LOGIC_VERSION - 1)
        storage.rebuild_if_logic_changed()
        self.assertIsNotNone(storage.get_test_baseline("samsung|galaxy-s24-ultra"))

    def test_riepilogo_conta_per_stato(self):
        uno = device()
        due = device(device_key="google|pixel-9", model="Pixel 9",
                     android_version=16, os_version="Android 16")
        storage.set_test_baseline(uno)
        storage.set_test_baseline(due)
        baselines = storage.get_test_baselines()
        self.assertEqual(len(baselines), 2)

        conteggio = retest.riepilogo(
            [uno, device(device_key="google|pixel-9", model="Pixel 9",
                         android_version=17, os_version="Android 17"),
             device(device_key="honor|x8c", model="HONOR X8c")],
            baselines,
        )
        self.assertEqual(conteggio[retest.INVARIATO], 1)
        self.assertEqual(conteggio[retest.DA_RITESTARE], 1)
        self.assertEqual(conteggio[retest.MAI_TESTATO], 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
