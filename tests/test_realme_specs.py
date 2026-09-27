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

    def test_json_ld_e_alimentatori(self):
        """Il JSON-LD delle pagine recenti si legge; i watt degli
        alimentatori in vendita nel menu non sono la ricarica del telefono."""
        pagina = ('<title>realme P4 Full Specifications</title>'
                  '<nav>realme SUPERVOOC 80W Power Adapter</nav>'
                  '<script type="application/ld+json">{"additionalProperty":['
                  '{"@type":"PropertyValue","name":"Chipset","value":"Qualcomm Snapdragon 685, 8-core CPU"},'
                  '{"@type":"PropertyValue","name":"Display","value":"6.8 inches, 120Hz AMOLED"},'
                  '{"@type":"PropertyValue","name":"Battery and Charging","value":"7000mAh (Typical), 45W SUPERVOOC"}'
                  ']}</script>')
        s = specs._scheda_realme_da_html("realme P4", pagina, URL)
        self.assertEqual(s.chipset, "Qualcomm Snapdragon 685")
        self.assertEqual(s.batteria, "7000 mAh")
        self.assertEqual(s.ricarica, "45 W")
        self.assertEqual(s.display, "6.8 pollici")

    def test_slug(self):
        self.assertEqual(specs._slug_realme("realme 14 Pro 5G"),
                         ["realme-14-pro-5g", "realme-14-pro"])
        self.assertEqual(specs._slug_realme("realme 13 Pro+"),
                         ["realme-13-pro-plus", "realme-13-pro-plus-5g"])
        # «GT8» sul sito ufficiale è «gt-8».
        self.assertIn("realme-gt-8-pro", specs._slug_realme("realme GT8 Pro"))
        self.assertEqual(specs._slug_realme("Galaxy S24"), [])


if __name__ == "__main__":
    unittest.main()
