"""Test della fonte ufficiale OPPO per il piano ColorOS 16.

Il piano è utile per l'Android previsto, non per una build installata: i
test proteggono entrambi i lati della promessa e il matching da codice CPH.
"""
from __future__ import annotations

import unittest

from core import config as C
from core import sources


_PAGINA = """
<html><body>
  <h2>ColorOS 16 Official Version Roll-Out Schedule</h2>
  <p>November 2025</p>
  <p>OPPO Find N5</p>
  <p>OPPO Find X8 Pro</p>
  <p>OPPO Reno14 5G</p>
  <p>Q1 2026</p>
  <p>OPPO Find X5</p>
  <p>OPPO Reno10 Pro+ 5G</p>
  <p>ColorOS 15</p>
  <p>OPPO A6x</p>
</body></html>
"""


class _Risposta:
    status_code = 200
    text = _PAGINA


class TestPianoColorOS16(unittest.TestCase):
    def setUp(self):
        self._http = sources.http_get
        self._nome_canonico = sources.modelcodes.nome_canonico
        sources.http_get = lambda url, timeout=None, headers=None: _Risposta()
        sources.reset_oppo_coloros16_cache()

    def tearDown(self):
        sources.http_get = self._http
        sources.modelcodes.nome_canonico = self._nome_canonico
        sources.reset_oppo_coloros16_cache()

    def test_legge_solo_la_sezione_coloros16(self):
        items, errore = sources.fetch_oppo_coloros16()
        self.assertIsNone(errore)
        self.assertEqual([i.device for i in items], [
            "OPPO Find N5", "OPPO Find X8 Pro", "OPPO Reno14 5G",
            "OPPO Find X5", "OPPO Reno10 Pro+ 5G",
        ])

    def test_e_supporto_non_firmware_corrente(self):
        items, _ = sources.fetch_oppo_coloros16()
        item = items[0]
        self.assertEqual(item.android_version, 16)
        self.assertEqual(item.version, "ColorOS 16")
        self.assertEqual(item.firmware_kind, C.FW_SUPPORT)
        self.assertIn("non prova", item.summary)

    def test_codice_cph_risolto_nel_piano(self):
        sources.modelcodes.nome_canonico = lambda codice: {
            "CPH2307": "OPPO Find X5"
        }.get(codice.upper())
        items = sources._lookup_oppo_coloros16("CPH2307")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].device, "OPPO Find X5")

    def test_non_confondere_modello_escluso_dalla_sezione_successiva(self):
        self.assertEqual(sources._lookup_oppo_coloros16("OPPO A6x"), [])

    def test_cache_evita_seconda_richiesta(self):
        chiamate = []

        def conta(url, timeout=None, headers=None):
            chiamate.append(url)
            return _Risposta()

        sources.http_get = conta
        sources.fetch_oppo_coloros16()
        sources._lookup_oppo_coloros16("OPPO Find X5")
        self.assertEqual(chiamate, [sources.OPPO_COLOROS16_URL])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
