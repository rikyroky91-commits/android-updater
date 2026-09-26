"""Ripiego scheda tecnica dalla pagina «specs» ufficiale realme.

La fixture è un frammento VERO della pagina italiana del realme 14 Pro 5G,
registrato il 26/09/2026 (vedi `core/specs._scheda_realme_da_html`).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import specs  # noqa: E402

_FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures",
                        "realme_14_pro_5g_specs.html")
with open(_FIXTURE, encoding="utf-8") as _f:
    PAGINA = _f.read()
URL = "https://www.realme.com/it/realme-14-pro-5g/specs"


class TestPaginaRealme(unittest.TestCase):
    def test_campi_letti(self):
        s = specs._scheda_realme_da_html("realme 14 Pro 5G", PAGINA, URL)
        self.assertIsNotNone(s)
        self.assertEqual(s.chipset, "Dimensity 7300 Energy")
        self.assertEqual(s.ram_gb, (8, 12))
        self.assertEqual(s.storage_gb, (128, 256, 512))
        self.assertEqual(s.batteria, "6000 mAh")
        self.assertEqual(s.ricarica, "45 W")
        self.assertEqual(s.camera_post, "50 MP")
        self.assertEqual(s.camera_front, "16 MP")
        self.assertEqual(s.fonte, specs.FONTE_REALME_LABEL)

    def test_titolo_di_un_altro_telefono(self):
        """La pagina deve nominare il telefono cercato: niente scheda di un
        altro modello solo perché l'indirizzo ha risposto."""
        self.assertIsNone(specs._scheda_realme_da_html("realme C75", PAGINA, URL))

    def test_slug(self):
        self.assertEqual(specs._slug_realme("realme 14 Pro 5G"),
                         ["realme-14-pro-5g", "realme-14-pro"])
        self.assertEqual(specs._slug_realme("realme 13 Pro+"),
                         ["realme-13-pro-plus", "realme-13-pro-plus-5g"])
        self.assertEqual(specs._slug_realme("Galaxy S24"), [])


if __name__ == "__main__":
    unittest.main()
