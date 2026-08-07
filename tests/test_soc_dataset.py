"""Il dataset esterno multi-marca: la copertura oltre la tabella scritta a mano."""
from __future__ import annotations

import unittest

from core import soc

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
