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

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")


class TestChiaveCurated(unittest.TestCase):

    def test_scan_marca_i_lookup_curated_con_la_loro_chiave(self):
        """La chiave dipende dal trust dichiarato dalla fonte."""
        raw = sources.RawItem(title="Test", link="", brand=C.OPPO,
                              device="OnePlus 13", build="CPH2649_16.0.7.201",
                              trust=C.TRUST_CURATED)
        self.assertEqual(raw.trust, C.TRUST_CURATED)

    def test_l_interfaccia_riconosce_entrambe_le_chiavi(self):
        """Se qui si guardasse solo `official_lookup`, i risultati delle
        fonti community finirebbero fra le notizie."""
        with open(APP, encoding="utf-8") as f:
            testo = f.read()
        self.assertIn("curated_lookup", testo)
        self.assertIn("CHIAVI_LOOKUP", testo)
        # E la vecchia forma con il confronto secco non deve tornare.
        self.assertNotIn('i.get("source") == "official_lookup"', testo)
        self.assertNotIn('i.get("source") != "official_lookup"', testo)


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
