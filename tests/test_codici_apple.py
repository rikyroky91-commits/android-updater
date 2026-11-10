"""I numeri A degli iPhone (10/11/2026).

Riccardo: «quando faccio una ricerca degli iphone ho bisogno che mi spunti
il codice modello ben visibile esempio: A2354 A1552». Il codice di un
iPhone è il numero A (A2403), non l'identificativo interno (iPhone13,2) che
la pagina mostrava fino a oggi. La tabella viene dalla pagina ufficiale
Apple e sta in `data/apple_codici_modello.csv`: nessuna rete.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_novita_30settembre import _riga_codice  # noqa: E402
from tests.test_sito import _Sito  # noqa: E402

_RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTabellaApple(unittest.TestCase):
    def setUp(self):
        from core import appledevices
        appledevices.reset_cache()

    def test_numero_a_nome(self):
        from core import appledevices as A
        self.assertEqual(A.name_for_model_number("A2403"), "iPhone 12")
        self.assertEqual(A.name_for_model_number("a 1586"), "iPhone 6")
        self.assertEqual(A.name_for_model_number("A3102"), "iPhone 15 Pro")
        self.assertIsNone(A.name_for_model_number("A9999"))
        self.assertIsNone(A.name_for_model_number("SM-A075F"))

    def test_prima_la_variante_europea(self):
        from core import appledevices as A
        codici = [c for c, _ in A.model_numbers_for("Apple iPhone 12")]
        self.assertEqual(codici[0], "A2403")
        self.assertEqual(set(codici), {"A2403", "A2172", "A2402", "A2404"})
        # Il refuso di Apple («other countires») non sposta la variante europea.
        self.assertEqual(A.model_numbers_for("iPhone 13")[0][0], "A2633")

    def test_le_generazioni_della_se_non_si_confondono(self):
        from core import appledevices as A
        self.assertEqual(A.model_numbers_for("iPhone SE (2nd generation)")[0][0], "A2296")
        self.assertEqual(A.model_numbers_for("iPhone SE (3rd generation)")[0][0], "A2783")
        self.assertEqual(A.model_numbers_for("iPhone SE"), [], "senza generazione non si sceglie a caso")
        # Il nome di ipsw.me con la precisazione fra parentesi ritrova il telefono.
        self.assertIn("A1901", [c for c, _ in A.model_numbers_for("iPhone X (Global)")])

    def test_tabella_completa(self):
        from core import appledevices as A
        A.model_numbers_for("iPhone 12")
        self.assertGreaterEqual(len(A._nome_per_codice), 200)
        for nome in ("iPhone 6", "iPhone 8", "iPhone 11", "iPhone 14 Pro", "iPhone 16e", "iPhone 17"):
            self.assertTrue(A.model_numbers_for(nome), nome)

    def test_lo_script_legge_la_pagina_apple(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "aggiorna_codici_apple", os.path.join(_RADICE, "scripts", "aggiorna_codici_apple.py"))
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        pagina = ("<h2>iPhone 12</h2><p>Model numbers: A2172 (United States), A2402 (Canada, Japan), "
                  "A2404 (China Mainland), A2403 (other countries and regions)</p><p>Details: …</p>"
                  "<h2>iPhone X</h2><p>Model numbers: A1865, A1901, A1902 (Japan<sup>2</sup>)</p><p>Details: …</p>")
        voci = modulo.estrai(pagina)
        self.assertIn(("iPhone 12", "A2403", "other countries and regions"), voci)
        self.assertIn(("iPhone X", "A1902", "Japan"), voci)
        self.assertEqual(len(voci), 7)


class TestRicercaPerNumeroA(unittest.TestCase):
    def test_il_numero_a_diventa_il_nome(self):
        from core import sources
        self.assertIn("iPhone 12", sources.expand_query("A2403"))
        self.assertIn("iPhone 12", sources.expand_query("apple a2403"))
        self.assertIn("iPhone 6", sources.expand_query("iPhone A1586"))


class TestCodiceInPagina(_Sito):
    def test_codici_da_mostrare(self):
        from web import main
        esito = main._codici_da_mostrare({"query": "iPhone 15 Pro", "nome": "Apple iPhone 15 Pro",
                                          "trovato": True, "codice": "", "scheda": {}})
        self.assertEqual(esito["codici_modello"], ["A3102"])
        self.assertTrue({"A2848", "A3101", "A3104"} <= set(esito["altri_codici"]))
        self.assertEqual(esito["mercati_codici"]["A3102"], "Italia, Europa e resto del mondo")
        self.assertEqual(esito["mercati_codici"]["A2848"], "Stati Uniti")
        # Cercando un numero A, è quello in testa.
        esito = main._codici_da_mostrare({"query": "a2848", "nome": "iPhone 15 Pro",
                                          "trovato": True, "codice": "", "scheda": {}})
        self.assertEqual(esito["codici_modello"], ["A2848"])
        self.assertFalse(esito["codice_dal_nome"])

    def test_la_pagina_mostra_il_numero_a(self):
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "device_model": "iPhone 12", "brand": "Apple",
            "os_version": "iOS 26.1", "firmware_kind": "current",
            "source_label": "ipsw.me"}], "error": None})
        self.addCleanup(setattr, type(self), "RISPOSTA_RICERCA",
                        staticmethod(lambda q: {"items": [], "error": None}))
        riga = _riga_codice(self.client.get("/", params={"q": "iPhone 12"}).text)
        self.assertIn('codice-principale">A2403<', riga)
        self.assertIn("Italia, Europa e resto del mondo", riga)
        self.assertIn("A2172", riga)
        self.assertIn("Stati Uniti", riga)
        riga = _riga_codice(self.client.get("/", params={"q": "A2172"}).text)
        self.assertIn('codice-principale">A2172<', riga)


if __name__ == "__main__":
    unittest.main()
