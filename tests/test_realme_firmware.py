"""Regressioni della fonte Realme a codice, senza rete vera."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, sources  # noqa: E402


class Risposta:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class TestArchivioTecnicoRealme(unittest.TestCase):
    """La regione e Android vengono dal nome del pacchetto, non da testo
    editoriale potenzialmente errato del catalogo."""

    CATALOGO = """
        RMX3939export_15_C.16_2026011618222600.zip
        Realme C63 Firmware [Android 16 NA]
        RMX3939GDPR_15_C.10_2025111718411900.zip
        RMX3939GDPR_15_C.14_2026032018524900.zip
        RMX3939export_14_A.81_2025061020564700.zip
    """

    def setUp(self):
        self._http_get = sources.http_get
        self._official_codes = sources.realme_official_codes
        self._modelcodes_resolve = sources.modelcodes.resolve
        self._modelcodes_codes_for_name = sources.modelcodes.codes_for_name
        self._aer_lookup = sources.aer_catalog.lookup
        self.calls = []
        sources.reset_realme_firmware_cache()
        sources.realme_official_codes = lambda: {
            "RMX3939": ("realme C63/Narzo 63/C61", "trimestrale")
        }

        def fake_get(url, timeout=None, headers=None):
            self.calls.append(url)
            return Risposta(200, self.CATALOGO)

        sources.http_get = fake_get

    def tearDown(self):
        sources.http_get = self._http_get
        sources.realme_official_codes = self._official_codes
        sources.modelcodes.resolve = self._modelcodes_resolve
        sources.modelcodes.codes_for_name = self._modelcodes_codes_for_name
        sources.aer_catalog.lookup = self._aer_lookup
        sources.reset_realme_firmware_cache()

    def test_preferisce_gdpr_e_legge_android_dal_pacchetto(self):
        items = sources._lookup_realme_firmware_archive("RMX3939")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].device, "realme C63")
        self.assertEqual(items[0].build, "C.14")
        self.assertEqual(items[0].android_version, 15)
        self.assertIn("Europa (GDPR)", items[0].size_info)
        self.assertEqual(items[0].trust, C.TRUST_CURATED)
        self.assertEqual(items[0].firmware_kind, C.FW_REPORTED)
        self.assertEqual(items[1].build, "C.16")
        # Il catalogo scrive Android 16 nella descrizione, ma `_15_` nel
        # nome della build è il metadato coerente e viene mantenuto.
        self.assertEqual(items[1].android_version, 15)

    def test_cache_per_codice_e_nome_commerciale(self):
        sources._lookup_realme_firmware_archive("realme C63")
        sources._lookup_realme_firmware_archive("RMX3939")
        self.assertEqual(len(self.calls), sources._REALME_FIRMWARE_SEARCH_PAGES)
        self.assertTrue(all("keyword=RMX3939" in url for url in self.calls))

    def test_nomi_regionali_e_nome_ambiguo_restano_codici_diversi(self):
        """C61 è stato venduto sia come RMX3930 sia come alias di RMX3939:
        non deve diventare C63 per effetto della normalizzazione del nome."""
        sources.realme_official_codes = lambda: {
            "RMX3930": ("realme C61", "trimestrale"),
            "RMX3939": ("realme C63/Narzo 63/C61", "trimestrale"),
        }
        self.assertEqual(sources._realme_codice_verificato("C63")[0], "RMX3939")
        self.assertEqual(sources._realme_codice_verificato("Narzo 63")[0], "RMX3939")
        self.assertEqual(sources._realme_codice_verificato("realme C61")[0], "RMX3930")

    def test_codice_non_confermato_non_interroga_l_archivio(self):
        self.assertEqual(sources._lookup_realme_firmware_archive("RMX9999"), [])
        self.assertEqual(self.calls, [])

    def test_assenza_verificata_viene_memorizzata_per_codice(self):
        """Un RMX senza pacchetto non deve fare quattro GET per ognuna delle
        sue forme regionali; un errore HTTP, invece, non sarebbe cachabile."""
        self.CATALOGO = "nessun pacchetto RMX3939 in questa pagina"
        self.assertEqual(sources._lookup_realme_firmware_archive("RMX3939"), [])
        self.assertEqual(sources._lookup_realme_firmware_archive("realme C63"), [])
        self.assertEqual(len(self.calls), sources._REALME_FIRMWARE_SEARCH_PAGES)

    def test_formati_moderni_leggono_build_android_e_regione_europea(self):
        """Il formato 2025+ non contiene più il vecchio ``_15_C.14``.

        Questa è una regressione del problema trovato nel collaudo reale:
        l'archivio aveva i file, ma il parser non restituiva nulla.
        """
        sources.realme_official_codes = lambda: {
            "RMX5011": ("realme GT 7 Pro", "trimestrale")
        }
        self.CATALOGO = """
            RMX5011export_11_15.0.0.1120EX01_2025111010101010.zip
            RMX5011GDPR_11_16.0.2.400EX01_2026021010101010.zip
            RMX5011 16.0.3.500(EX01) [GDPR].zip
            RMX5011 16.0.3.500(EX01) [Export].zip
        """

        items = sources._lookup_realme_firmware_archive("RMX5011")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].device, "realme GT 7 Pro")
        self.assertEqual(items[0].android_version, 16)
        self.assertEqual(items[0].build, "16.0.3.500(EX01)")
        self.assertIn("Europa (GDPR)", items[0].size_info)
        self.assertIn("senza data interna", items[0].summary)
        self.assertEqual(items[1].android_version, 16)
        self.assertIn("Globale / Export", items[1].size_info)

    def test_archivio_oppo_cph_usa_lo_stesso_formato_moderno(self):
        """La serie A OPPO usa CPH e lo stesso nome package moderno.

        CPH2683 (OPPO A3) non è nell'archivio firmware OPPO legacy: senza
        questo percorso la scheda resta senza una build pur avendo il
        pacchetto GDPR nell'archivio tecnico.
        """
        sources.modelcodes.resolve = lambda codice: (
            ["OPPO A3"] if codice.upper() == "CPH2683" else []
        )
        # Il caso verifica il ripiego del catalogo locale; AER ha dati live
        # e può legittimamente indicare una variante regionale più precisa.
        sources.aer_catalog.lookup = lambda codice: None
        self.CATALOGO = """
            CPH2683export_11_15.0.0.1301EX01_2025102315070000.zip
            CPH2683GDPR_11_15.0.0.1200EX01_2025082220180000.zip
        """

        items = sources._lookup_oppo_firmware_archive("CPH2683")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].device, "OPPO A3")
        self.assertEqual(items[0].android_version, 15)
        self.assertEqual(items[0].build, "15.0.0.1200(EX01)")
        self.assertIn("Archivio tecnico OPPO", items[0].size_info)
        self.assertIn("Europa (GDPR)", items[0].size_info)

    def test_oppo_cph_conserva_il_nome_europeo_aer_sul_rebrand(self):
        """Un CPH può avere nomi diversi fuori Europa.

        CPH2781 è A6 Pro 5G nel catalogo europeo e F31 in India: la
        scheda AER ufficiale deve prevalere, altrimenti una ricerca per
        codice restituisce un telefono di un altro mercato.
        """
        sources.modelcodes.resolve = lambda codice: (
            ["OPPO F31", "OPPO A6 Pro 5G"] if codice.upper() == "CPH2781" else []
        )
        sources.aer_catalog.lookup = lambda codice: (
            {"device_model": "OPPO A6 Pro 5G"} if codice.upper() == "CPH2781" else None
        )
        self.CATALOGO = "CPH2781GDPR_11_16.0.5.1000EX01_2026030101010101.zip"

        items = sources._lookup_oppo_firmware_archive("CPH2781")

        self.assertEqual(items[0].device, "OPPO A6 Pro 5G")
        self.assertEqual(items[0].android_version, 16)
        self.assertIn("Europa (GDPR)", items[0].size_info)

    def test_matrice_dieci_modelli_aggiuntivi_non_regredisce(self):
        """Ogni ampliamento della fonte deve provare almeno dieci modelli
        oltre ai casi storici C63/C61. Sono modelli reali, scelti da famiglie
        diverse, per evitare una correzione valida per un solo RMX."""
        nuovi = {
            "RMX3493": "realme 9i",
            "RMX3286": "realme Narzo 50",
            "RMX3624": "realme C33",
            "RMX3511": "realme C35",
            "RMX3516": "realme Narzo 50A Prime",
            "RMX3501": "realme C31",
            "RMX3686": "realme 10 Pro+ 5G",
            "RMX3890": "realme C67 4G",
            "RMX3750": "realme Narzo 60 5G",
            "RMX3371": "realme GT NEO 3T",
        }
        sources.realme_official_codes = lambda: {
            codice: (nome, "trimestrale") for codice, nome in nuovi.items()
        }

        def catalogo_per_codice(url, timeout=None, headers=None):
            self.calls.append(url)
            codice = url.split("keyword=", 1)[1].split("&", 1)[0]
            return Risposta(200, f"{codice}GDPR_15_C.17_2026032112345600.zip")

        sources.http_get = catalogo_per_codice
        risultati = {
            codice: sources._lookup_realme_firmware_archive(codice)
            for codice in nuovi
        }

        self.assertEqual(set(risultati), set(nuovi))
        for codice, nome in nuovi.items():
            with self.subTest(codice=codice):
                item = risultati[codice][0]
                self.assertEqual(item.device, nome)
                self.assertEqual(item.model_code, codice)
                self.assertEqual(item.android_version, 15)
                self.assertEqual(item.build, "C.17")
        self.assertEqual(
            len(self.calls),
            len(nuovi) * sources._REALME_FIRMWARE_SEARCH_PAGES,
        )


if __name__ == "__main__":
    unittest.main()
