"""Regressioni per i fallback *per codice* dei brand senza endpoint OTA.

I casi non sono correzioni manuali di tre modelli: verificano che il flusso
parta da qualunque codice riconosciuto e conservi sia la regione sia la
semantica prudente del dato osservato.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core import config as C
from core import motorola_catalog, sources


class _Response:
    status_code = 200

    def __init__(self, text: str):
        self.text = text


_MOTOROLA_PAGE = """
<div class="file-list-item"><a href="https://support.halabtech.com/index.php?a=downloads&b=file&id=1">
XT2523-3_fastboot_lamu_g_user_15_VVTA35.51-137-10_cabf9d_release-keys.zip</a>
<span class="file-date">Date: 14-04-2026</span></div>
<div class="file-list-item"><a href="https://support.halabtech.com/index.php?a=downloads&b=file&id=2">
XT2523-3_fastboot_lamu_g_user_15_VVTAS35.51-153-3_76a43c_release-keys.zip</a>
<span class="file-date">Date: 13-07-2026</span></div>
"""

_REALME_PAGE = """
RMX5313export_15_A.69_2026012009304000.zip
RMX5313export_15_A.80_2026052400251900.zip
"""


class TestBrandCodeFallbacks(unittest.TestCase):
    def tearDown(self):
        motorola_catalog.reset_cache()
        sources.reset_realme_firmware_cache()

    def test_catalogo_motorola_inverte_il_nome_ufficiale(self):
        motorola_catalog.carica_da({"XT2523-3": "motorola moto g05"})
        self.assertEqual(motorola_catalog.codes_for_name("moto g05"), ["XT2523-3"])

    def test_catalogo_motorola_incluso_risponde_a_freddo(self):
        """Un deploy senza download non puo' trasformare G05 in sola identita'."""
        motorola_catalog.reset_cache()
        self.assertIn("XT2523-3", motorola_catalog.codes_for_name("moto g05"))

    def test_motorola_archivio_copre_codice_fuori_lista_manuale(self):
        motorola_catalog.carica_da({"XT2523-3": "moto g05"})
        with patch.object(sources, "http_get", return_value=_Response(_MOTOROLA_PAGE)):
            found = sources._lookup_motorola("moto g05")

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].model_code, "XT2523-3")
        self.assertEqual(found[0].android_version, 15)
        self.assertEqual(found[0].build, "VVTAS35.51-153-3")
        self.assertEqual(found[0].firmware_kind, C.FW_REPORTED)
        self.assertEqual(found[0].published[:10], "2026-07-13")

    def test_router_non_scarta_moto_come_se_fosse_un_altra_marca(self):
        """La via completa deve conservare ``moto`` == ``Motorola``.

        Non basta che il parser dell'archivio restituisca la build: questa
        regressione aveva il risultato in mano e lo eliminava nel filtro di
        sotto-marca prima di poterlo mostrare all'utente.
        """
        motorola_catalog.carica_da({"XT2523-3": "motorola moto g05"})
        only_motorola = [sources.StructuredLookup(
            C.VIVO, sources._lookup_motorola, "alto", "test Motorola",
            firmware_kind=C.FW_REPORTED,
        )]
        with patch.object(sources, "_lookup_order", return_value=only_motorola), \
             patch.object(sources, "http_get", return_value=_Response(_MOTOROLA_PAGE)):
            found, note = sources.lookup_model_structured("moto g05")

        self.assertIsNone(note)
        self.assertEqual([(item.model_code, item.build) for item in found], [
            ("XT2523-3", "VVTAS35.51-153-3"),
        ])

    def test_realme_fuori_aer_arriva_all_archivio_per_codice(self):
        # RMX5313 non è nel piano AER; il dataset lo identifica comunque e
        # l'archivio restituisce la build più alta del ramo Export.
        with patch.object(sources, "realme_official_codes", return_value={}), \
             patch.object(sources, "realme_name_variants", return_value={}), \
             patch.object(sources.modelcodes, "resolve", return_value=["realme Note 70T"]), \
             patch.object(sources.modelcodes, "nome_canonico", return_value="realme Note 70T"), \
             patch.object(sources, "http_get", return_value=_Response(_REALME_PAGE)):
            found = sources._lookup_realme_firmware_archive("RMX5313")

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].device, "realme Note 70T")
        self.assertEqual(found[0].build, "A.80")
        self.assertEqual(found[0].android_version, 15)
        self.assertEqual(found[0].firmware_kind, C.FW_REPORTED)

    def test_realme_fuori_europa_non_inventa_un_nome_europeo(self):
        """Con il solo nome cinese disponibile si conserva il codice RMX.

        La priorità europea vale quando il dataset o la tabella curata la
        dimostrano; tradurre ``真我 14`` in un rebrand immaginato sarebbe
        peggio del mostrare l'identificativo certo del dispositivo.
        """
        with patch.object(sources.modelcodes, "_indice_override_nomi", return_value={}), \
             patch.object(sources.modelcodes, "nome_canonico", return_value="真我 14"), \
             patch.object(sources.modelcodes, "_e_il_codice", return_value=False):
            name = sources._nome_realme_per_codice(
                "RMX5075", ["真我 14", "realme 真我14"])

        self.assertEqual(name, "realme RMX5075")

    def test_honor_codice_raggiunge_il_bollettino_ufficiale(self):
        source_item = sources.RawItem(
            title="HONOR Magic7 Lite — aggiornamenti di sicurezza trimestrali",
            brand=C.HUAWEI,
            device="HONOR Magic7 Lite",
            firmware_kind=C.FW_SUPPORT,
        )
        with patch.object(sources, "fetch_honor_security_bulletin",
                          return_value=([source_item], None)), \
             patch.object(sources.modelcodes, "nome_canonico",
                          return_value="HONOR Magic7 Lite"), \
             patch.object(sources.modelcodes, "resolve",
                          return_value=["HONOR Magic7 Lite"]):
            found = sources._lookup_honor_security("BRP-NX1M")

        self.assertEqual(found, [source_item])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
