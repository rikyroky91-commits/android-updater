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
