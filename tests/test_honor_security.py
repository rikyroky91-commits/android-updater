"""Bollettino sicurezza HONOR: supporto dichiarato, non firmware inventato."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C  # noqa: E402
from core import sources  # noqa: E402


_PAGINA = """
<div>
  <p class="des-tit">Modelli con aggiornamenti di sicurezza mensili</p>
  <p class="des">Serie HONOR Magic: HONOR Magic8 Pro, HONOR Magic V5</p>
  <p class="des-tit">Modelli che supportano gli aggiornamenti della sicurezza bimestrali</p>
  <p class="des">Serie HONOR N: HONOR 600 Pro, HONOR 600</p>
  <p class="des-tit">Modelli con aggiornamenti di sicurezza trimestrali</p>
  <p class="des">Serie HONOR Magic: HONOR Magic5 Pro, HONOR Magic7 Lite</p>
  <p class="des">Serie HONOR X: HONOR X8b, HONOR X7b</p>
</div>
"""


class TestHonorSecurityBulletin(unittest.TestCase):
    def test_parser_conserva_modello_e_cadenza(self):
        found = dict(sources._parse_honor_security_bulletin(_PAGINA))
        self.assertEqual(found["HONOR Magic8 Pro"], "mensili")
        self.assertEqual(found["HONOR 600"], "bimestrali")
        self.assertEqual(found["HONOR Magic5 Pro"], "trimestrali")
        self.assertEqual(found["HONOR X8b"], "trimestrali")

    def test_lookup_dichiara_solo_supporto(self):
        previous = sources.fetch_honor_security_bulletin
        sources.fetch_honor_security_bulletin = lambda: ([
            sources.RawItem(title="HONOR Magic5 Pro", device="HONOR Magic5 Pro",
                            brand=C.HUAWEI, firmware_kind=C.FW_SUPPORT),
        ], None)
        try:
            found = sources._lookup_honor_security("HONOR Magic5 Pro")
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].firmware_kind, C.FW_SUPPORT)
            self.assertIsNone(found[0].android_version)
        finally:
            sources.fetch_honor_security_bulletin = previous
