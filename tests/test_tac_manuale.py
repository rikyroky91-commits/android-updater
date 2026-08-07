"""Inserimento del modello dentro l'app e verifica su più siti."""
from __future__ import annotations

import unittest

from core import imeicheck, storage


class TestLinkDiVerifica(unittest.TestCase):
    """Più di un sito, di proposito: hanno cataloghi diversi e un TAC
    assente da uno si trova spesso nell'altro."""

    def test_ce_ne_sono_diversi(self):
        self.assertGreaterEqual(len(imeicheck.link_verifica("351355315430630")), 3)

    def test_l_imei_finisce_solo_dove_serve(self):
        link = dict((n, u) for n, u, _ in imeicheck.link_verifica("351355315430630"))
        self.assertIn("351355315430630", link["imei.info"])
        # Gli altri sono pagine di ricerca: nessun identificativo nell'URL.
        self.assertNotIn("351355315430630", link["HiCellTek"])

    def test_url_ben_formati(self):
        for nome, url, nota in imeicheck.link_verifica("351355315430630"):
            with self.subTest(sito=nome):
                self.assertTrue(url.startswith("http"))
                self.assertTrue(nota)


class TestInserimentoManuale(unittest.TestCase):

    def setUp(self):
        storage.reset_state()
        storage.init_db()
        imeicheck.reset_cache()

    def tearDown(self):
        storage.reset_state()
        imeicheck.reset_cache()

    def test_salva_e_ritrova(self):
        self.assertTrue(imeicheck.aggiungi_tac("35135531", "Samsung", "Galaxy A54 5G"))
        self.assertEqual(imeicheck.identify("351355315430630"),
                         ("Samsung", "Galaxy A54 5G"))

    def test_vale_per_tutti_gli_imei_dello_stesso_modello(self):
        """Si salva il TAC, non l'IMEI: le altre sette cifre identificano
        il singolo esemplare e non c'entrano col modello."""
        imeicheck.aggiungi_tac("35135531", "Samsung", "Galaxy A54 5G")
        self.assertIsNotNone(imeicheck.identify("351355319999995"))

    def test_serve_almeno_marca_o_modello(self):
        self.assertFalse(imeicheck.aggiungi_tac("35135531", "", ""))

    def test_un_tac_malformato_viene_rifiutato(self):
        self.assertFalse(imeicheck.aggiungi_tac("123", "Samsung", "X"))
        self.assertFalse(imeicheck.aggiungi_tac("", "Samsung", "X"))

    def test_accetta_l_imei_intero_e_ne_tiene_le_prime_otto(self):
        self.assertTrue(imeicheck.aggiungi_tac("351355315430630", "Samsung", "X"))
        self.assertIn("35135531", imeicheck.tac_inseriti())

    def test_si_puo_correggere_e_togliere(self):
        imeicheck.aggiungi_tac("35135531", "Samsung", "Sbagliato")
        imeicheck.aggiungi_tac("35135531", "Samsung", "Giusto")
        self.assertEqual(imeicheck.identify("351355315430630")[1], "Giusto")
        self.assertTrue(imeicheck.rimuovi_tac("35135531"))
        self.assertEqual(imeicheck.tac_inseriti(), {})

    def test_la_riga_per_il_file_e_pronta_da_incollare(self):
        riga = imeicheck.riga_csv("35135531", "Samsung", "Galaxy A54 5G")
        self.assertEqual(riga.split(",")[:3], ["35135531", "Samsung", "Galaxy A54 5G"])


class TestLeFontiLocaliSopravvivonoAlDownload(unittest.TestCase):
    """Il difetto trovato scrivendo questa funzione.

    Se il database scaricato non era disponibile, `_build_index` usciva
    subito — e con lei sparivano anche la tabella verificata a mano e i
    TAC inseriti nell'app, che col download non c'entrano niente. Bastava
    un'ora senza rete perché l'app dimenticasse dati che aveva in casa.
    """

    def setUp(self):
        storage.reset_state()
        storage.init_db()
        imeicheck.reset_cache()
        self._cache = imeicheck._cached_bytes
        imeicheck._cached_bytes = lambda: None

    def tearDown(self):
        imeicheck._cached_bytes = self._cache
        storage.reset_state()
        imeicheck.reset_cache()

    def test_senza_download_i_dati_locali_valgono_lo_stesso(self):
        imeicheck.aggiungi_tac("35135531", "Samsung", "Galaxy A54 5G")
        self.assertEqual(imeicheck.identify("351355315430630"),
                         ("Samsung", "Galaxy A54 5G"))

    def test_lo_stato_dice_quanti_ne_hai_inseriti(self):
        imeicheck.aggiungi_tac("35135531", "Samsung", "X")
        imeicheck.identify("351355315430630")
        self.assertIn("inseriti da te", imeicheck.status())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
