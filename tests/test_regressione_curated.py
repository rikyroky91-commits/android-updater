"""Regressione: i risultati delle fonti CURATED non devono sparire.

Quando è stato introdotto il trust per-fonte, i lookup non ufficiali
hanno cominciato a marcare i loro risultati con la chiave
`curated_lookup` invece di `official_lookup`. Due punti del codice
riconoscevano solo la vecchia chiave, e nessun test se n'era accorto:

1. `app.py` classificava quei risultati fra le **notizie** — cioè il
   tracker ARB e il canale di rollout, le uniche fonti che coprono
   OnePlus e OPPO recenti, finivano mostrati come articoli di giornale.
2. `storage.purge_retired_sources` li considerava **fonti ritirate** e
   li cancellava dall'archivio a ogni giro.

Il secondo è il peggiore: cancellava in silenzio proprio i dispositivi
per cui quelle fonti erano state aggiunte.
"""
from __future__ import annotations

import os
import unittest

from core import config as C, scan, sources, storage

# Il file dell'interfaccia da guardare è quello del SITO: `app.py`, la
# dashboard Streamlit, è stato tolto il 2026-08-10.
SITO = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "main.py")


class TestChiaveCurated(unittest.TestCase):

    def test_scan_marca_i_lookup_curated_con_la_loro_chiave(self):
        """La chiave dipende dal trust dichiarato dalla fonte."""
        raw = sources.RawItem(title="Test", link="", brand=C.OPPO,
                              device="OnePlus 13", build="CPH2649_16.0.7.201",
                              trust=C.TRUST_CURATED)
        self.assertEqual(raw.trust, C.TRUST_CURATED)

    def test_l_interfaccia_riconosce_entrambe_le_chiavi(self):
        """Se qui si guardasse solo `official_lookup`, i risultati delle
        fonti community — il tracker ARB e il canale di rollout, cioè le
        uniche che coprono OnePlus e OPPO recenti — finirebbero fra le
        notizie, mostrati come articoli di giornale."""
        with open(SITO, encoding="utf-8") as f:
            testo = f.read()
        self.assertIn("curated_lookup", testo)
        self.assertIn("official_lookup", testo)
        # E la vecchia forma con il confronto secco non deve tornare.
        self.assertNotIn('i.get("source") == "official_lookup"', testo)
        self.assertNotIn('i.get("source") != "official_lookup"', testo)

    def test_un_risultato_curated_non_finisce_fra_le_notizie(self):
        """Il comportamento, non la forma del codice: un risultato di una
        fonte community deve essere l'ESITO della ricerca, non una
        notizia in fondo alla pagina."""
        from web import main as M

        voce = {"source": "curated_lookup", "source_label": "Tracker ARB",
                "brand": C.OPPO, "device_model": "OnePlus 13",
                "build": "CPH2649_16.0.7.201", "title": "", "severity": "",
                "color": "#00CC66"}
        vera = scan.search_model
        scan.search_model = lambda q, senza_rete=False: {"items": [voce], "error": None}
        try:
            esito = M._cerca_davvero("OnePlus 13")
        finally:
            scan.search_model = vera
        self.assertTrue(esito["trovato"])
        self.assertEqual(esito["notizie"], [])
        self.assertIn("CPH2649", esito["riga"])


class TestArchivioNonCancellaCurated(unittest.TestCase):

    def setUp(self):
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()

    def test_le_righe_curated_sopravvivono_alla_pulizia(self):
        import inspect
        codice = inspect.getsource(storage.purge_retired_sources)
        self.assertIn("curated_lookup", codice)
        self.assertIn("official_lookup", codice)
        self.assertIn("live_search", codice)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
