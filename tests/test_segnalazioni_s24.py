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


class TestRicercaTacOnline(unittest.TestCase):
    """La terza via per i TAC che i database locali non hanno.

    Vincolo che la rende accettabile: esce **solo il TAC di 8 cifre**, mai
    l'IMEI intero. Le cifre restanti identificano il singolo telefono e
    non devono lasciare la macchina.
    """

    def setUp(self):
        self._chiave = imeicheck._chiave_api
        self._requests = imeicheck.requests

    def tearDown(self):
        imeicheck._chiave_api = self._chiave
        imeicheck.requests = self._requests
        imeicheck.reset_cache()

    def test_senza_chiave_non_esce_nessuna_richiesta(self):
        """Comportamento predefinito: l'app funziona come prima."""
        imeicheck._chiave_api = lambda: ""

        class Sentinella:
            def post(self, *a, **k):
                raise AssertionError("nessuna richiesta doveva partire")

        imeicheck.requests = Sentinella()
        self.assertIsNone(imeicheck.cerca_tac_online("35135531"))

    def test_esce_solo_il_tac_mai_l_imei_intero(self):
        inviati = []

        class Finto:
            def post(self, url, json=None, headers=None, timeout=None):
                inviati.append(json)

                class R:
                    status_code = 200

                    @staticmethod
                    def json():
                        return {"manufacturer": "Samsung", "model": "Galaxy Test"}

                return R()

        imeicheck._chiave_api = lambda: "chiave-finta"
        imeicheck.requests = Finto()
        imeicheck.cerca_tac_online("351355315430630")
        self.assertEqual(inviati, [{"query": "35135531"}])

    def test_una_risposta_valida_diventa_marca_e_modello(self):
        class Finto:
            def post(self, *a, **k):
                class R:
                    status_code = 200

                    @staticmethod
                    def json():
                        return {"data": {"manufacturer": "Samsung",
                                         "model": "Galaxy A54 5G"}}

                return R()

        imeicheck._chiave_api = lambda: "k"
        imeicheck.requests = Finto()
        self.assertEqual(imeicheck.cerca_tac_online("35135531"),
                         ("Samsung", "Galaxy A54 5G"))

    def test_ogni_incertezza_diventa_nessuna_risposta(self):
        """Un servizio che non risponde non deve diventare un dato
        inventato."""
        casi = [(500, {}), (200, {"manufacturer": "", "model": ""}), (200, [])]
        for stato, corpo in casi:
            with self.subTest(stato=stato, corpo=corpo):
                class Finto:
                    def post(self, *a, **k):
                        class R:
                            status_code = stato

                            @staticmethod
                            def json():
                                return corpo

                        return R()

                imeicheck._chiave_api = lambda: "k"
                imeicheck.requests = Finto()
                self.assertIsNone(imeicheck.cerca_tac_online("35135531"))

    def test_un_tac_malformato_non_viene_nemmeno_chiesto(self):
        class Sentinella:
            def post(self, *a, **k):
                raise AssertionError("non doveva partire")

        imeicheck._chiave_api = lambda: "k"
        imeicheck.requests = Sentinella()
        self.assertIsNone(imeicheck.cerca_tac_online("123"))
        self.assertIsNone(imeicheck.cerca_tac_online(""))
