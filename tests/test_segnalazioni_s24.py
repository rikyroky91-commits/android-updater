"""Le segnalazioni sullo schermo del 06/08: S24 Ultra doppio e IMEI muto."""
from __future__ import annotations

import unittest

from core import config as C, extract, imeicheck, soc


class TestNomeCommercialeScrittoInPiuModi(unittest.TestCase):
    """Il chip non si trovava per «Samsung S24 Ultra».

    La tabella conosceva solo la grafia «Galaxy S24 Ultra». Ma nessuno
    digita così, e nemmeno le fonti di notizie scrivono così: il nome
    arriva ora con la marca davanti, ora senza la parola di gamma.
    """

    def setUp(self):
        soc.reset_cache()

    def test_tutte_le_grafie_trovano_lo_stesso_chip(self):
        atteso = soc.per_modello("Galaxy S24 Ultra")
        self.assertIsNotNone(atteso)
        for forma in ("Samsung S24 Ultra", "S24 Ultra", "samsung s24 ultra",
                      "Samsung Galaxy S24 Ultra"):
            with self.subTest(forma=forma):
                trovato = soc.per_modello(forma)
                self.assertIsNotNone(trovato, f"«{forma}» non trova il chip")
                self.assertEqual(trovato.nome, atteso.nome)

    def test_le_varianti_generate(self):
        forme = set(soc.varianti_nome("Galaxy S24 Ultra"))
        self.assertIn("S24 ULTRA", forme)
        self.assertIn("SAMSUNG S24 ULTRA", forme)
        self.assertIn("GALAXY S24 ULTRA", forme)

    def test_la_gamma_giusta_per_ogni_marca(self):
        self.assertIn("XIAOMI REDMI NOTE 13", soc.varianti_nome("Redmi Note 13"))
        self.assertIn("NOTE 13", soc.varianti_nome("Redmi Note 13"))

    def test_non_fonde_telefoni_diversi(self):
        """Le varianti non devono far collassare due modelli distinti."""
        self.assertNotEqual(soc.per_modello("Galaxy A32 4G").nome,
                            soc.per_modello("Galaxy A32 5G").nome)


class TestMarcaSenzaLaParolaGalaxy(unittest.TestCase):
    """«S24 Ultra» finiva sotto «Altri brand».

    Risultato: lo stesso telefono in archivio due volte, una riga sotto
    Samsung e una sotto la categoria residuale, ciascuna con metà della
    storia.
    """

    def test_le_gamme_inequivocabili_sono_samsung(self):
        for testo in ("S24 Ultra", "S23 FE", "Note20 Ultra", "Z Fold6",
                      "Z Flip5", "Tab S9"):
            with self.subTest(testo=testo):
                self.assertEqual(extract.detect_brand(testo), C.SAMSUNG)

    def test_la_serie_a_resta_ambigua(self):
        """«A15» è insieme un Galaxy A15 e un OPPO A15: indovinare qui
        sarebbe peggio che tacere."""
        self.assertIsNone(extract.detect_brand("A15"))
        self.assertEqual(extract.detect_brand("OPPO A15"), C.OPPO)

    def test_non_ruba_dispositivi_ad_altre_marche(self):
        self.assertEqual(extract.detect_brand("iPhone 15"), C.APPLE)
        self.assertNotEqual(extract.detect_brand("Redmi Note 13"), C.SAMSUNG)


class TestSecondaBaseDatiTac(unittest.TestCase):
    """Un IMEI valido che «non esiste» è quasi sempre un buco di copertura."""

    def test_l_imei_segnalato_e_formalmente_valido(self):
        """Se la cifra di controllo torna, il problema non è l'IMEI: è il
        database che non conosce quel TAC."""
        self.assertTrue(imeicheck.is_valid_imei("351355315430630"))

    def test_la_seconda_base_dati_e_configurata(self):
        self.assertTrue(imeicheck.TAC_DB_FALLBACK_URL.startswith("http"))
        self.assertNotEqual(imeicheck.TAC_DB_FALLBACK_URL, imeicheck.TAC_DB_URL)

    def test_il_csv_storico_viene_interpretato(self):
        originale = imeicheck._cached_bytes_url
        csv_testo = ("tac,manufacturer,model\n"
                     "35135531,Samsung,Galaxy Storico\n"
                     "12345678,Nokia,3310\n"
                     "abc,Rotta,Riga\n")
        imeicheck._cached_bytes_url = lambda *a, **k: csv_testo.encode()
        try:
            indice = imeicheck._indice_fallback()
        finally:
            imeicheck._cached_bytes_url = originale
        self.assertEqual(indice["35135531"], ("Samsung", "Galaxy Storico"))
        self.assertNotIn("abc", indice)

    def test_se_la_seconda_non_risponde_non_rompe_niente(self):
        """È un supplemento: se non è raggiungibile l'app deve continuare
        a identificare con la prima base dati."""
        originale = imeicheck._cached_bytes_url
        imeicheck._cached_bytes_url = lambda *a, **k: None
        try:
            self.assertEqual(imeicheck._indice_fallback(), {})
        finally:
            imeicheck._cached_bytes_url = originale


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
