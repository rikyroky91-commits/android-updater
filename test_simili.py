"""Telefoni con hardware simile (`core/simili.py`, rotta `/simili`).

Il criterio è stretto di proposito — stessa marca VERA e stesso chip
commerciale — e i test collaudano soprattutto quello che NON deve passare:
un OnePlus proposto per un Oppo, un Galaxy A con un chip diverso, l'Android
di lancio di un telefono confrontato con l'ultimo Android di un altro.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import simili as S  # noqa: E402

from tests.test_sito import _Sito, _SitoConLogin  # noqa: E402


class TestChiaveChip(unittest.TestCase):
    def test_sigla_processo_e_mercato_non_contano(self):
        for testo in ("Qualcomm SM8650-AB Snapdragon 8 Gen 3 (4 nm)",
                      "Qualcomm SM8650-AC Snapdragon 8 Gen 3 (4 nm) - USA/Canada/China",
                      "Qualcomm Snapdragon 8 Gen 3 for Galaxy (SM8650-AC)"):
            with self.subTest(testo=testo):
                self.assertEqual(S.chiavi_chip(testo), ("snapdragon 8 gen 3",))

    def test_chip_vicini_restano_diversi(self):
        """7s Gen 2 non è 7 Gen 2, G99 Ultra non è G99, 730G non è 730."""
        coppie = [("Snapdragon 7s Gen 2", "Snapdragon 7 Gen 2"),
                  ("Mediatek Helio G99 Ultra", "Mediatek Helio G99 (6 nm)"),
                  ("Qualcomm SDM730 Snapdragon 730G (8 nm)",
                   "Qualcomm SDM730 Snapdragon 730 (8 nm)"),
                  ("Snapdragon 865 5G+", "Snapdragon 865 5G")]
        for a, b in coppie:
            with self.subTest(a=a, b=b):
                self.assertNotEqual(S.chiavi_chip(a), S.chiavi_chip(b))

    def test_stesso_chip_scritto_in_modi_diversi(self):
        coppie = [("Unisoc T612 (12 nm)", "Unisoc Tiger T612 (12 nm)"),
                  ("Mediatek MT6769V/CU Helio G80 (12 nm)", "Mediatek Helio G80"),
                  ("Qualcomm SM8250 Snapdragon 865 5G (7 nm+)", "Snapdragon 865"),
                  ("Apple A14 Bionic (5 nm)", "Apple A14")]
        for a, b in coppie:
            with self.subTest(a=a, b=b):
                self.assertEqual(S.chiavi_chip(a), S.chiavi_chip(b))

    def test_varianti_su_piu_righe_e_con_oppure(self):
        self.assertEqual(
            S.chiavi_chip("Qualcomm SM8650-AC Snapdragon 8 Gen 3 (4 nm) - USA\n"
                          "Exynos 2400 (4 nm) - International"),
            ("snapdragon 8 gen 3", "exynos 2400"))
        self.assertEqual(
            S.chiavi_chip("Samsung Exynos 2400 oppure Qualcomm Snapdragon 8 Gen 3 for Galaxy"),
            ("exynos 2400", "snapdragon 8 gen 3"))

    def test_la_sola_famiglia_non_identifica_un_chip(self):
        for testo in ("Qualcomm Snapdragon", "Spreadtrum", "Exynos", "", None):
            with self.subTest(testo=testo):
                self.assertEqual(S.chiavi_chip(testo), ())


class TestMarca(unittest.TestCase):
    def test_sottomarchi_con_lo_stesso_software(self):
        self.assertEqual(S.marca_di("Xiaomi Redmi Note 13"), "xiaomi")
        self.assertEqual(S.marca_di("POCO X6"), "xiaomi")
        self.assertEqual(S.marca_di("Galaxy A55"), "samsung")
        self.assertEqual(S.marca_di("vivo iQOO Z9"), "vivo")

    def test_oneplus_non_e_oppo(self):
        """Stesso gruppo del tracker, software diverso."""
        self.assertNotEqual(S.marca_di("OnePlus Nord CE4"), S.marca_di("Oppo Reno11"))

    def test_android_di_lancio_e_la_prima_versione(self):
        self.assertEqual(S.android_di_lancio(
            "Android 11, upgradable to Android 13, One UI 5"), 11)
        self.assertIsNone(S.android_di_lancio("Tizen OS 5.5"))


def _riga(nome, chip, os_lancio="", rilascio="", marca="Samsung"):
    return {"nome": nome, "marca": marca, "chipset": chip,
            "os_lancio": os_lancio, "rilascio": rilascio}


_CANDIDATI = [
    _riga("Samsung Galaxy A34", "Mediatek Dimensity 1080 (6 nm)", "Android 13", "2023, March"),
    _riga("Samsung Galaxy M34", "Mediatek Dimensity 1080 (6 nm)", "Android 14", "2023, July"),
    _riga("Samsung Galaxy A35", "Exynos 1380 (5 nm)", "Android 14", "2024, March"),
    _riga("Samsung Galaxy Tab S9 FE", "Exynos 1380 (5 nm)", "Android 13", "2023"),
    _riga("Oppo Reno8", "Mediatek Dimensity 1300 (6 nm)", "Android 12", "2022",
          marca="Oppo / Realme / OnePlus"),
    _riga("OnePlus Nord 2T", "Mediatek Dimensity 1300 (6 nm)", "Android 12", "2022",
          marca="Oppo / Realme / OnePlus"),
    _riga("Samsung Galaxy A54", "Exynos 1380 (5 nm)", "Android 13", "2023, March"),
]


def _chiave(marca, nome):
    return f"{marca.lower()}|{nome.lower()}"


class TestTrova(unittest.TestCase):
    def test_stessa_marca_e_stesso_chip_sono_obbligatori(self):
        esito = S.trova(nome="Samsung Galaxy A54", chip="Exynos 1380",
                        android_lancio=13, candidati=_CANDIDATI)
        nomi = [v["nome"] for v in esito["simili"]]
        self.assertEqual(nomi, ["Samsung Galaxy A35"])
        self.assertNotIn("Samsung Galaxy A54", nomi, "il telefono stesso non è un simile")
        self.assertNotIn("Samsung Galaxy Tab S9 FE", nomi, "un tablet non è un telefono")

    def test_il_telefono_cercato_non_e_simile_a_se_stesso(self):
        """Da SM-A556B la ricerca mostra «Samsung Galaxy A55 5G», il
        catalogo lo chiama «Samsung Galaxy A55»: stesso telefono, e in
        produzione compariva in cima ai propri simili."""
        candidati = _CANDIDATI + [_riga("Samsung Galaxy A55", "Exynos 1480 (4 nm)"),
                                  _riga("Samsung Galaxy M56", "Exynos 1480 (4 nm)")]
        esito = S.trova(nome="Samsung Galaxy A55 5G", chip="Samsung Exynos 1480 (S5E8845)",
                        candidati=candidati, altri_nomi=("Samsung Galaxy A55",))
        self.assertEqual([v["nome"] for v in esito["simili"]], ["Samsung Galaxy M56"])

    def test_il_suffisso_di_rete_del_nome_cercato_non_lo_rende_un_altro(self):
        """Secondo correttivo, verificato in produzione: ricerca e scheda
        dicevano entrambe «Galaxy A55 5G», il catalogo «Galaxy A55»."""
        candidati = _CANDIDATI + [_riga("Samsung Galaxy A55", "Exynos 1480 (4 nm)"),
                                  _riga("Samsung Galaxy M56", "Exynos 1480 (4 nm)")]
        esito = S.trova(nome="Samsung Galaxy A55 5G", chip="Exynos 1480",
                        candidati=candidati, altri_nomi=("Samsung Galaxy A55 5G",))
        self.assertEqual([v["nome"] for v in esito["simili"]], ["Samsung Galaxy M56"])

    def test_un_candidato_con_un_altro_suffisso_resta_diverso(self):
        candidati = [_riga("Samsung Galaxy A07 4G", "Mediatek Helio G99")]
        esito = S.trova(nome="Samsung Galaxy A07 5G", chip="Mediatek Helio G99",
                        candidati=candidati)
        self.assertEqual([v["nome"] for v in esito["simili"]], ["Samsung Galaxy A07 4G"])

    def test_oneplus_finisce_fra_le_altre_marche(self):
        esito = S.trova(nome="Oppo Reno8", chip="Mediatek Dimensity 1300",
                        candidati=_CANDIDATI)
        self.assertEqual(esito["simili"], [])
        self.assertEqual([v["nome"] for v in esito["altre_marche"]], ["OnePlus Nord 2T"])

    def test_prima_lo_stesso_android_di_lancio(self):
        esito = S.trova(nome="Samsung Galaxy A24", chip="Mediatek Dimensity 1080",
                        android_lancio=14, candidati=_CANDIDATI)
        self.assertEqual([v["nome"] for v in esito["simili"]],
                         ["Samsung Galaxy M34", "Samsung Galaxy A34"])
        self.assertEqual(esito["simili"][0]["stesso_software"], "lancio")
        self.assertIsNone(esito["simili"][1]["stesso_software"])

    def test_archivio_e_lancio_non_si_mescolano(self):
        """Android 14 in archivio per il riferimento, 14 al lancio per il
        candidato: NON è lo stesso software, sono due dati diversi."""
        esito = S.trova(nome="Samsung Galaxy A24", chip="Dimensity 1080",
                        android_archivio=14, candidati=_CANDIDATI)
        self.assertTrue(all(v["stesso_software"] is None for v in esito["simili"]))

    def test_archivio_contro_archivio_vince(self):
        archivio = {_chiave("Samsung", "Samsung Galaxy A34"): {"android_version": "15"}}
        esito = S.trova(nome="Samsung Galaxy A24", chip="Dimensity 1080",
                        android_archivio=15, android_lancio=14, candidati=_CANDIDATI,
                        archivio=archivio, chiave_di=_chiave)
        primo = esito["simili"][0]
        self.assertEqual((primo["nome"], primo["stesso_software"]),
                         ("Samsung Galaxy A34", "archivio"))
        self.assertTrue(primo["in_archivio"])

    def test_il_parco_viene_prima_a_parita_di_software(self):
        esito = S.trova(nome="Samsung Galaxy A24", chip="Dimensity 1080",
                        candidati=_CANDIDATI, chiave_di=_chiave,
                        in_parco={_chiave("Samsung", "Samsung Galaxy A34")})
        self.assertEqual(esito["simili"][0]["nome"], "Samsung Galaxy A34")
        self.assertTrue(esito["simili"][0]["in_parco"])

    def test_chip_ignoto_niente_proposte(self):
        esito = S.trova(nome="Samsung Galaxy A24", chip=None, candidati=_CANDIDATI)
        self.assertEqual(esito["simili"], [])
        self.assertTrue(esito["motivo_vuoto"])

    def test_marca_fuori_catalogo_lo_dice(self):
        esito = S.trova(nome="realme C63", chip="Unisoc T612", candidati=_CANDIDATI)
        self.assertTrue(esito["marca_non_coperta"])

    def test_candidato_con_piu_chip_segnalato(self):
        candidati = _CANDIDATI + [_riga(
            "Samsung Galaxy S24", "Qualcomm SM8650-AC Snapdragon 8 Gen 3 (4 nm) - USA\n"
            "Exynos 2400 (4 nm) - International")]
        esito = S.trova(nome="Samsung Galaxy S24+", chip="Exynos 2400", candidati=candidati)
        self.assertEqual(esito["simili"][0]["nome"], "Samsung Galaxy S24")
        self.assertTrue(esito["simili"][0]["solo_una_variante"])


_SIMILE_A56 = {
    "nome": "Samsung Galaxy A36 Test", "marca": "Samsung", "foto": None,
    "codici": ["SM-ZZ999"], "rilascio": "2025, March", "chipset": "Exynos 1580 (4 nm)",
    "os_lancio": "Android 15, One UI 7", "ram_gb": [8], "storage_gb": [128],
}
_ALTRA_MARCA_A56 = dict(_SIMILE_A56, nome="Xiaomi Test 1580", marca="Xiaomi / Redmi / POCO",
                        codici=["ZZX1580"])


class _ConCandidati:
    def setUp(self):
        super().setUp()
        from core import specs

        self._originali = list(specs._schede)
        specs.carica_da(self._originali + [_SIMILE_A56, _ALTRA_MARCA_A56],
                        "fixture di test + simili")

    def tearDown(self):
        from core import specs
        from web.main import RICERCHE

        specs.carica_da(self._originali, "fixture di test")
        RICERCHE.svuota()
        super().tearDown()


class TestPaginaSimili(_ConCandidati, _Sito):
    def test_propone_stessa_marca_stesso_chip(self):
        pagina = self.client.get("/simili", params={"q": "Galaxy A56"}).text
        self.assertIn("Samsung Galaxy A36 Test", pagina)
        self.assertIn("Stesso processore, altre marche", pagina)
        self.assertIn("Xiaomi Test 1580", pagina)

    def test_anonimo_non_vede_il_parco(self):
        pagina = self.client.get("/simili", params={"q": "Galaxy A56"}).text
        self.assertNotIn("Aggiungi al parco", pagina)

    def test_il_tasto_sta_nella_pagina_di_ricerca(self):
        pagina = self.client.get("/", params={"q": "Galaxy A56"}).text
        self.assertIn('action="/simili"', pagina)
        self.assertIn("Trova un telefono con hardware simile", pagina)

    def test_pagina_vuota_spiega_a_cosa_serve(self):
        risposta = self.client.get("/simili")
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("stessa\n  marca", risposta.text)


class TestPaginaSimiliConLogin(_ConCandidati, _SitoConLogin):
    def test_si_aggiunge_al_parco_e_si_torna_qui(self):
        from core import extract, storage

        pagina = self.client.get("/simili", params={"q": "Galaxy A56"}).text
        self.assertIn("Aggiungi al parco", pagina)
        chiave = extract.device_key("Samsung", "Samsung Galaxy A36 Test")
        risposta = self.client.post("/parco/aggiungi", data={
            "chiave": chiave, "brand": "Samsung", "modello": "Samsung Galaxy A36 Test",
            "ritorno": "/simili?q=Galaxy%20A56"}, follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)
        self.assertTrue(risposta.headers["location"].startswith("/simili?q=Galaxy%20A56"))
        self.assertIn(chiave, storage.watched_keys())
        dopo = self.client.get("/simili", params={"q": "Galaxy A56"}).text
        self.assertIn("nel parco", dopo)
        storage.remove_from_watchlist(chiave)


if __name__ == "__main__":
    unittest.main()
