"""Il dataset esterno multi-marca: la copertura oltre la tabella scritta a mano."""
from __future__ import annotations

import os
import unittest

from core import soc, storage

# Estratto nella forma REALE del dataset: i valori sono letterali Python
# (`b'...'`), non stringhe semplici. È il dettaglio che avrebbe fatto
# fallire tutto in silenzio, riempiendo l'app di chip chiamati «b'Exynos'».
CSV = (
    "b'brand',b'Model Name',b'Chipset',b'CPU'\n"
    "b'samsung',b'Samsung Galaxy A Quantum',b'Exynos 980 (8 nm)',b'Octa-core'\n"
    "b'xiaomi',b'Xiaomi Redmi Note 10',b'Qualcomm SM6150 Snapdragon 678',b'Octa'\n"
    "b'samsung',b'Samsung Galaxy S20',b'Exynos 990 / Qualcomm SM8250',b'Octa'\n"
    "b'oppo',b'Oppo Reno6',b'Mediatek MT6877 Dimensity 900',b'Octa'\n"
)


class TestLetturaDataset(unittest.TestCase):

    def test_i_letterali_vengono_ripuliti(self):
        indice = soc.carica_dataset_esterno(CSV)
        voce = indice["GALAXY A QUANTUM"]
        self.assertNotIn("b'", voce.nome)
        self.assertIn("Exynos 980", voce.nome)

    def test_copre_marche_diverse_da_samsung(self):
        indice = soc.carica_dataset_esterno(CSV)
        self.assertIn("REDMI NOTE 10", indice)
        self.assertIn("RENO6", indice)

    def test_le_sigle_note_diventano_nomi_commerciali(self):
        indice = soc.carica_dataset_esterno(CSV)
        self.assertIn("Dimensity 900", indice["RENO6"].nome)

    def test_due_chip_per_lo_stesso_nome_restano_dichiarati_entrambi(self):
        """Il dataset è indicizzato per nome commerciale, quindi le
        varianti regionali finiscono nella stessa cella. Sceglierne una
        sarebbe una risposta sbagliata per metà dei telefoni."""
        voce = soc.carica_dataset_esterno(CSV)["GALAXY S20"]
        self.assertIn("Exynos 990", voce.nome)
        self.assertIn("oppure", voce.nome)
        self.assertIn("codice esatto", voce.nota)

    def test_la_provenienza_e_dichiarata(self):
        voce = soc.carica_dataset_esterno(CSV)["RENO6"]
        self.assertIn("dataset", voce.fonte)

    def test_csv_vuoto_o_senza_colonne_utili(self):
        self.assertEqual(soc.carica_dataset_esterno(""), {})
        self.assertEqual(soc.carica_dataset_esterno("a,b\n1,2\n"), {})


class TestNomiAmbigui(unittest.TestCase):
    """MISURATO SUL DATASET VERO, non ipotizzato: 25 chiavi su 14182 sono
    reclamate da telefoni diversi con chip diversi.

    Nasce dalla forma abbreviata che rende utile il dataset: «Samsung S24
    Ultra» trova «Galaxy S24 Ultra» proprio perché si indicizza anche il
    nome senza marca. Ma la stessa abbreviazione accorpa «Huawei P30» e
    «Motorola P30» sotto «P30», e «vivo U3» con «vivo iQOO U3» sotto «vivo
    U3». Tenendo la prima riga incontrata, il chip mostrato dipendeva
    dall'ordine delle righe nel CSV.
    """

    COLLISIONE = (
        "b'brand',b'Model Name',b'Chipset'\n"
        "b'huawei',b'Huawei P30',b'Kirin 980 (7 nm)'\n"
        "b'motorola',b'Motorola P30',b'Qualcomm SDM636 Snapdragon 636'\n"
        "b'oneplus',b'OnePlus 2',b'Qualcomm MSM8994 Snapdragon 810'\n"
    )

    def test_il_nome_abbreviato_conteso_non_risponde(self):
        indice = soc.carica_dataset_esterno(self.COLLISIONE)
        self.assertNotIn("P30", indice,
                         "«P30» risponde con il chip del telefono sbagliato")

    def test_i_nomi_completi_restano(self):
        """Si toglie l'ambiguità, non la copertura."""
        indice = soc.carica_dataset_esterno(self.COLLISIONE)
        self.assertIn("Kirin 980", indice["HUAWEI P30"].nome)
        self.assertIn("Snapdragon 636", indice["MOTOROLA P30"].nome)

    def test_le_chiavi_troppo_corte_non_entrano(self):
        """«OnePlus 2» abbreviato è «2»: una chiave che non può che
        rispondere a caso."""
        indice = soc.carica_dataset_esterno(self.COLLISIONE)
        self.assertNotIn("2", indice)
        self.assertIn("ONEPLUS 2", indice)

    def test_stesso_telefono_ripetuto_non_e_ambiguo(self):
        """Righe doppie dello stesso modello sono normali in un dump: non
        vanno confuse con due telefoni diversi."""
        doppio = (
            "b'brand',b'Model Name',b'Chipset'\n"
            "b'samsung',b'Samsung Galaxy S20',b'Exynos 990'\n"
            "b'samsung',b'Samsung Galaxy S20',b'Exynos 990 (7 nm+)'\n"
        )
        self.assertIn("GALAXY S20", soc.carica_dataset_esterno(doppio))


class TestCacheCompressa(unittest.TestCase):
    """I file scaricati vivono dentro `tracker.db`, che viene caricato su un
    Gist ogni mezz'ora e committato ogni ora. In esadecimale occupavano il
    doppio della loro dimensione: 63 MB in tutto, misurati sui file veri."""

    def setUp(self):
        import tempfile
        from core import config as C
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        from core import config as C
        storage.reset_state()
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale

    def test_andata_e_ritorno(self):
        dati = ("b'brand',b'Model Name'\n" + "b'x',b'y'\n" * 500).encode()
        storage.set_blob("prova", dati)
        self.assertEqual(storage.get_blob("prova"), dati)

    def test_comprime_davvero(self):
        dati = ("riga ripetuta,con virgole\n" * 5000).encode()
        storage.set_blob("prova", dati)
        self.assertLess(len(storage.get_meta("prova")), len(dati) / 5)

    def test_legge_ancora_il_formato_precedente(self):
        """Un'installazione già avviata ha in archivio l'esadecimale: senza
        questa tolleranza riscaricherebbe decine di MB al primo avvio."""
        dati = b"contenuto di prova"
        storage.set_meta("vecchia", dati.hex())
        self.assertEqual(storage.get_blob("vecchia"), dati)

    def test_un_valore_illeggibile_non_solleva(self):
        storage.set_meta("rotta", "non e ne base64 ne esadecimale ###")
        self.assertIsNone(storage.get_blob("rotta"))
        self.assertIsNone(storage.get_blob("mai_scritta"))

    def test_un_valore_non_testuale_non_solleva(self):
        """`meta` conserva JSON qualsiasi: qualcuno potrebbe averci messo
        un numero, e leggerlo come file non deve far cadere l'app."""
        storage.set_meta("numero", 42)
        self.assertIsNone(storage.get_blob("numero"))


class TestPrecedenze(unittest.TestCase):
    """L'ordine delle fonti è la garanzia di correttezza."""

    def setUp(self):
        soc.reset_cache()
        self._originale = soc._indice_dataset
        soc._indice_dataset = lambda: soc.carica_dataset_esterno(CSV)

    def tearDown(self):
        soc._indice_dataset = self._originale
        soc.reset_cache()

    def test_la_tabella_curata_vince_sul_dataset(self):
        """Il dataset non distingue Exynos e Snapdragon sullo stesso nome;
        la tabella curata sì, perché è indicizzata per codice. Quindi la
        curata deve avere la precedenza, sempre."""
        curato = soc.per_modello("SM-G980F")
        self.assertIn("Exynos 990", curato.etichetta)
        self.assertNotIn("oppure", curato.nome)

    def test_il_dataset_copre_dove_la_curata_tace(self):
        trovato = soc.per_modello("Redmi Note 10")
        self.assertIsNotNone(trovato)
        self.assertIn("Snapdragon 678", trovato.nome)

    def test_un_modello_ignoto_resta_ignoto(self):
        self.assertIsNone(soc.per_modello("Telefono Inesistente 999"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
