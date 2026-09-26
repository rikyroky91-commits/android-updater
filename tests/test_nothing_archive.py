"""Fonte Nothing/CMF (`core/nothing_archive.py` e `sources.fetch_nothing_archive`).

Albero e changelog in `tests/fixtures/nothing/` sono quelli VERI
dell'archivio, registrati il 26/09/2026: la C5.0 di Metroid è una Open
Beta, la B4.1 la stabile che la precede, la V3.5 una stabile che contiene
la frase «Updating to Open Beta ... won't be possible», il falso positivo
che il riconoscimento delle beta deve evitare.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, nothing_archive, sources  # noqa: E402

CARTELLA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "nothing")


def _leggi(nome: str) -> str:
    with open(os.path.join(CARTELLA, nome), encoding="utf-8") as f:
        return f.read()


ALBERO = json.loads(_leggi("albero.json"))
BETA = _leggi("Metroid-C5.0-260819-1642.md")
STABILE = _leggi("Metroid-B4.1-260814-1733.md")
STABILE_CON_DISCLAIMER = _leggi("Metroid-V3.5-250923-1421.md")


class FintaRisposta:
    def __init__(self, status=200, testo="", dati=None):
        self.status_code = status
        self.text = testo
        self._dati = dati

    def json(self):
        return self._dati


class TestLettura(unittest.TestCase):
    def test_nome_file(self):
        b = nothing_archive.build_dal_percorso(
            "website/docs/changelogs/metroid/Metroid-V3.5-250923-1421.md")
        self.assertEqual((b.versione, b.data, b.ora, b.android), ("3.5", "2025-09-23", "14:21", 15))
        self.assertEqual(b.nome_build, "Metroid-V3.5-250923-1421")

    def test_lettera_android(self):
        self.assertEqual(nothing_archive.ANDROID_PER_LETTERA["B"], 16)
        self.assertEqual(nothing_archive.ANDROID_PER_LETTERA["C"], 17)

    def test_albero_reale(self):
        per = nothing_archive.build_per_dispositivo(ALBERO)
        self.assertIn("metroid", per)
        self.assertGreaterEqual(len(per), 10)
        date = [b.chiave_ordine for b in per["metroid"]]
        self.assertEqual(date, sorted(date, reverse=True), "le build non sono dalla più recente")

    def test_beta_riconosciuta(self):
        self.assertTrue(nothing_archive.e_beta(BETA))

    def test_stabile_con_disclaimer_non_e_beta(self):
        self.assertIn("Open Beta", STABILE_CON_DISCLAIMER,
                      "la fixture non contiene più il falso positivo che questo test protegge")
        self.assertFalse(nothing_archive.e_beta(STABILE_CON_DISCLAIMER))
        self.assertFalse(nothing_archive.e_beta(STABILE))

    def test_patch(self):
        self.assertEqual(nothing_archive.patch_sicurezza(STABILE), "2026-08")
        self.assertIsNone(nothing_archive.patch_sicurezza("nessuna patch qui"))


class TestFonte(unittest.TestCase):
    def setUp(self):
        sources.reset_nothing_cache()
        self._http = sources.http_get
        albero_ridotto = {"tree": [v for v in ALBERO["tree"] if "/metroid/" in v["path"]
                                   or "/asteroids/" in v["path"]]}
        testi = {"Metroid-C5.0-260819-1642.md": BETA,
                 "Metroid-B4.1-260814-1733.md": STABILE}

        def finto_get(url, timeout=None, headers=None):
            if url == nothing_archive.TREE_URL:
                return FintaRisposta(dati=albero_ridotto)
            nome = url.rsplit("/", 1)[-1]
            if nome in testi:
                return FintaRisposta(testo=testi[nome])
            # Ogni altro changelog: una stabile generica.
            return FintaRisposta(testo="## Changelog\nUpdated to July 2026 security patch.\n")

        sources.http_get = finto_get

    def tearDown(self):
        sources.http_get = self._http
        sources.reset_nothing_cache()

    def test_la_beta_non_diventa_ultima_stabile(self):
        items, errore = sources.fetch_nothing_archive()
        self.assertIsNone(errore)
        phone3 = next(i for i in items if i.device == "Nothing Phone (3)")
        self.assertEqual(phone3.version, "Nothing OS 4.1")
        self.assertEqual(phone3.android_version, 16)
        self.assertEqual(phone3.firmware_kind, C.FW_CURRENT)
        self.assertEqual(phone3.model_code, "A024")
        self.assertIn("2026-08", phone3.summary)
        self.assertIn("Beta più recente: Nothing OS 5.0", phone3.summary)
        self.assertTrue(phone3.link.startswith(nothing_archive.BLOB_URL))

    def test_variante_condivisa(self):
        items, _ = sources.fetch_nothing_archive()
        nomi = {i.device for i in items}
        self.assertIn("Nothing Phone (3a)", nomi)
        self.assertIn("Nothing Phone (3a) Pro", nomi)

    def test_ricerca_per_nome_e_codice(self):
        self.assertEqual(sources._lookup_nothing("nothing phone 3")[0].device, "Nothing Phone (3)")
        self.assertEqual(sources._lookup_nothing("A024")[0].device, "Nothing Phone (3)")
        self.assertEqual(sources._lookup_nothing("Nothing Phone (3a) Pro")[0].device,
                         "Nothing Phone (3a) Pro")

    def test_forme_senza_phone_e_codice_nella_frase(self):
        """Dal banco di prova del 26/09/2026: «Nothing (3A)» finiva su un
        altro telefono e «Nothing A069» non trovava niente."""
        self.assertEqual(sources._lookup_nothing("Nothing (3A)")[0].device, "Nothing Phone (3a)")
        self.assertEqual(sources._lookup_nothing("nothing 3a pro")[0].device,
                         "Nothing Phone (3a) Pro")
        self.assertEqual(sources._lookup_nothing("Nothing A024")[0].device, "Nothing Phone (3)")

    def test_guasto_non_in_cache(self):
        sources.http_get = lambda *a, **k: FintaRisposta(status=403)
        items, errore = sources.fetch_nothing_archive()
        self.assertEqual(items, [])
        self.assertIn("403", errore)


if __name__ == "__main__":
    unittest.main()
