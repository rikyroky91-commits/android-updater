"""Test delle correzioni alla radice del caso Galaxy A32.

Tre difetti indipendenti, ognuno capace da solo di produrre la risposta
sbagliata che l'utente ha visto.
"""
from __future__ import annotations

import gzip
import unittest

from core import skinmap, sources


class _Risposta:
    def __init__(self, testo="", status_code=200, content=None):
        self.text = testo
        self.status_code = status_code
        self.content = content if content is not None else testo.encode()


XML = ('<?xml version="1.0" encoding="UTF-8"?><versioninfo><firmware><version>'
       '<latest o="13">A325FXXSCDYB2/A325FOXMCDYB2/A325FXXSCDYB2</latest>'
       '</version></firmware></versioninfo>')


class TestUserAgentFota(unittest.TestCase):
    """La radice del guasto Samsung.

    L'endpoint FOTA serve il client ufficiale Samsung e con uno
    User-Agent da browser risponde 403. Il controllo versione lo chiamava
    con quello generico del progetto: ogni region falliva in silenzio, e
    la ricerca finiva per rispondere con una fonte di ripiego. Da fuori
    sembrava che il modello non fosse coperto — in realtà non gli veniva
    mai chiesto niente.
    """

    def setUp(self):
        self._http = sources.http_get

    def tearDown(self):
        sources.http_get = self._http

    def test_la_richiesta_porta_lo_user_agent_del_client_samsung(self):
        visti = []

        def get(url, timeout=None, headers=None):
            visti.append((headers or {}).get("User-Agent"))
            return _Risposta(XML)

        sources.http_get = get
        sources._fota_get("https://fota-cloud-dn.ospserver.net/x/y/version.xml")
        self.assertEqual(visti, [sources.FOTA_USER_AGENT])

    def test_lo_user_agent_generico_non_viene_piu_usato_qui(self):
        visti = []

        def get(url, timeout=None, headers=None):
            visti.append((headers or {}).get("User-Agent"))
            return _Risposta(XML)

        sources.http_get = get
        sources._samsung_fus_latest("SM-A325F")
        self.assertTrue(visti)
        for agente in visti:
            self.assertEqual(agente, sources.FOTA_USER_AGENT)


class TestGzipNonDichiarato(unittest.TestCase):
    """L'altro modo silenzioso di non funzionare.

    Il server può restituire gzip senza dichiararlo: in quel caso
    `response.text` è un blocco binario in cui la ricerca del numero di
    build non trova nulla, e la region viene scartata come se non avesse
    risposto.
    """

    def setUp(self):
        self._http = sources.http_get

    def tearDown(self):
        sources.http_get = self._http

    def test_la_risposta_compressa_viene_decompressa(self):
        compresso = gzip.compress(XML.encode())
        sources.http_get = lambda url, timeout=None, headers=None: _Risposta(
            testo="\ufffd\ufffd binario", content=compresso)
        testo = sources._fota_get("https://fota-cloud-dn.ospserver.net/x/y/version.xml")
        self.assertIn("A325FXXSCDYB2", testo or "")

    def test_la_build_viene_letta_da_una_risposta_compressa(self):
        compresso = gzip.compress(XML.encode())
        sources.http_get = lambda url, timeout=None, headers=None: _Risposta(
            testo="binario", content=compresso)
        pda, android, csc = sources._samsung_fus_latest("SM-A325F")
        self.assertEqual(pda, "A325FXXSCDYB2")
        self.assertEqual(android, "13")

    def test_una_risposta_non_xml_e_non_gzip_non_solleva(self):
        sources.http_get = lambda url, timeout=None, headers=None: _Risposta(
            testo="", content=b"\x00\x01\x02")
        self.assertIsNone(sources._samsung_fus_latest("SM-A325F")[0])

    def test_http_non_200_viene_saltato(self):
        sources.http_get = lambda url, timeout=None, headers=None: _Risposta("", 403)
        self.assertIsNone(sources._fota_get("https://fota-cloud-dn.ospserver.net/x/y/z.xml"))


class TestMappaSkinAndroid(unittest.TestCase):
    """Il caso segnalato: «Android 12» accanto a «One UI 5.0»."""

    def test_one_ui_5_e_android_13(self):
        self.assertEqual(skinmap.android_da_skin("One UI", "5.0"), 13)
        self.assertEqual(skinmap.android_da_skin("One UI", "5.1"), 13)

    def test_la_contraddizione_viene_riconosciuta(self):
        conflitto = skinmap.contraddizione("One UI", "5.0", 12)
        self.assertIsNotNone(conflitto)
        self.assertIn("Android 13", conflitto)

    def test_nessun_falso_allarme_quando_i_dati_concordano(self):
        self.assertIsNone(skinmap.contraddizione("One UI", "5.0", 13))

    def test_la_versione_lunga_batte_quella_corta(self):
        """One UI 3.1.1 gira su Android 12 mentre 3.1 sta su Android 11:
        le eccezioni stanno sempre nel numero lungo."""
        self.assertEqual(skinmap.android_da_skin("One UI", "3.1"), 11)
        self.assertEqual(skinmap.android_da_skin("One UI", "3.1.1"), 12)

    def test_emui_11_gira_su_android_10(self):
        """Huawei ha rotto di proposito l'allineamento: dedurlo dal numero
        darebbe la risposta sbagliata."""
        self.assertEqual(skinmap.android_da_skin("EMUI", "11"), 10)
        self.assertIsNone(skinmap.contraddizione("EMUI", "11", 10))

    def test_le_corrispondenze_non_univoche_non_deducono(self):
        """MIUI e le ColorOS antecedenti alla 11 hanno pubblicato la stessa
        major su Android diversi: lì si tace invece di indovinare."""
        for skin, versione in (("MIUI", "12.5"), ("MIUI", "12"),
                               ("ColorOS", "7.2")):
            with self.subTest(skin=skin, versione=versione):
                self.assertIsNone(skinmap.android_da_skin(skin, versione))

    def test_e_quindi_non_accusano_nessuno(self):
        """Dove la corrispondenza non è certa, una discrepanza non è una
        prova di errore: il controllo deve tacere."""
        self.assertIsNone(skinmap.contraddizione("MIUI", "12.5", 11))
        self.assertIsNone(skinmap.contraddizione("MIUI", "12.5", 10))

    def test_harmonyos_non_e_android(self):
        self.assertIsNone(skinmap.android_da_skin("HarmonyOS", "5"))
        self.assertIsNone(skinmap.contraddizione("HarmonyOS", "5", 14))

    def test_skin_sconosciuta(self):
        self.assertIsNone(skinmap.android_da_skin("SkinInventata", "1.0"))
        self.assertIsNone(skinmap.android_da_skin(None, None))

    def test_alias_di_scrittura(self):
        for nome in ("One UI", "OneUI", "one ui", "Samsung One UI"):
            with self.subTest(nome=nome):
                self.assertEqual(skinmap.android_da_skin(nome, "5.1"), 13)

    def test_etichetta_leggibile(self):
        self.assertEqual(skinmap.descrizione("One UI", "5.1"),
                         "One UI 5.1 (Android 13)")
        self.assertEqual(skinmap.descrizione("MIUI", "12.5"), "MIUI 12.5")


class TestChipSerieA(unittest.TestCase):
    """La copertura del processore oltre la serie S."""

    def setUp(self):
        from core import soc
        self.soc = soc
        soc.reset_cache()

    def test_il_modello_del_caso_segnalato(self):
        chip = self.soc.per_modello("SM-A325F")
        self.assertIn("Helio G80", chip.etichetta)

    def test_anche_scritto_senza_prefisso(self):
        self.assertIsNotNone(self.soc.per_modello("a325f"))

    def test_le_due_varianti_dell_a32_hanno_chip_diversi(self):
        """4G e 5G sono telefoni diversi con lo stesso nome di famiglia."""
        quattro = self.soc.per_modello("SM-A325F")
        cinque = self.soc.per_modello("SM-A326B")
        self.assertNotEqual(quattro.nome, cinque.nome)
        self.assertIn("Dimensity 720", cinque.etichetta)

    def test_nessun_codice_inventato_dentro_un_altro_codice(self):
        """Senza confini di parola, dentro «CPH2649» si legge «H264» e si
        finisce per cercare un inesistente «SM-H264»."""
        self.assertEqual(self.soc.codici_da_testo("OnePlus 13 CPH2649"), ["CPH2649"])

    def test_nessun_doppione_fra_i_candidati(self):
        self.assertEqual(self.soc.codici_da_testo("SM-S921B"), ["SM-S921B"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
