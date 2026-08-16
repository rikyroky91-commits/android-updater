"""La foto mostrata dev'essere DI QUEL telefono.

Il controllo di pertinenza nasceva per fermare un errore fra marche
diverse (un realme C61 che rispondeva con un telefono Xiaomi). Bastava
una parola in comune — e per vivo, Honor e realme la marca sta DENTRO il
nome del modello, quindi qualunque telefono della stessa marca passava.

Misurato il 16/08/2026 interrogando Wikipedia davvero:
    «vivo V30» -> Vivo V40        «vivo Y36» -> Vivo X300 Pro
    «Moto G24» -> Motorola Moto   (la pagina generica della serie)

Una foto sbagliata e' peggio di nessuna foto: una casella vuota si vede,
un telefono plausibile ma sbagliato no.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import images  # noqa: E402


class TestPertinenzaDelTitolo(unittest.TestCase):
    def test_la_sigla_del_modello_deve_combaciare(self):
        for query, titolo in (("vivo V30", "Vivo V40"),
                              ("vivo Y36", "Vivo X300 Pro"),
                              ("Galaxy S24", "Samsung Galaxy S23")):
            with self.subTest(query=query, titolo=titolo):
                self.assertFalse(
                    images._titolo_pertinente(query, titolo),
                    f"«{query}» non deve accettare la pagina di «{titolo}»")

    def test_una_pagina_generica_di_serie_non_basta(self):
        self.assertFalse(images._titolo_pertinente("Moto G24", "Motorola Moto"))

    def test_il_modello_giusto_passa(self):
        for query, titolo in (("vivo X100", "Vivo X100"),
                              ("Galaxy S24 Ultra", "Samsung Galaxy S24 Ultra"),
                              ("realme C67", "Realme C67"),
                              ("Honor Magic6 Pro", "Honor Magic6 Pro")):
            with self.subTest(query=query):
                self.assertTrue(images._titolo_pertinente(query, titolo))

    def test_i_nomi_senza_cifre_restano_permissivi(self):
        """«Nothing Phone», «Pixel Fold»: senza una sigla numerica non c'e'
        niente da confrontare, e la regola stretta li escluderebbe tutti."""
        self.assertTrue(images._titolo_pertinente("Nothing Phone", "Nothing Phone"))
        self.assertTrue(images._titolo_pertinente("Pixel Fold", "Google Pixel Fold"))

    def test_marche_diverse_restano_escluse(self):
        """Il caso originale per cui il controllo e' nato."""
        self.assertFalse(images._titolo_pertinente("realme C61", "Xiaomi Redmi 12C"))


class TestLaDomandaPerLaFoto(unittest.TestCase):
    """`brand` in questo progetto NON e' una marca: e' la sigla della
    FAMIGLIA di fonti («Vivo / iQOO / Motorola»). Usarla nella domanda
    produceva «Vivo / iQOO / Motorola vivo X90 smartphone», a cui
    Wikipedia rispondeva «Android (operating system)» — su quasi tutti i
    telefoni, perche' solo Samsung e Pixel hanno una sigla che e' davvero
    una marca."""

    def test_la_sigla_di_gruppo_non_finisce_nella_domanda(self):
        from web.presenters import _domanda_per_la_foto

        for gruppo in ("Vivo / iQOO / Motorola", "Xiaomi / Redmi / POCO",
                       "Huawei / Honor", "Oppo / Realme / OnePlus"):
            with self.subTest(gruppo=gruppo):
                domanda = _domanda_per_la_foto(gruppo, "vivo X90")
                self.assertNotIn("/", domanda)
                self.assertEqual(domanda, "vivo X90")

    def test_una_marca_vera_resta_nella_domanda(self):
        from web.presenters import _domanda_per_la_foto

        self.assertEqual(_domanda_per_la_foto("Samsung", "Galaxy S24 Ultra"),
                         "Samsung Galaxy S24 Ultra")

    def test_senza_marca_resta_il_solo_modello(self):
        from web.presenters import _domanda_per_la_foto

        self.assertEqual(_domanda_per_la_foto("", "Moto G24"), "Moto G24")


if __name__ == "__main__":
    unittest.main()
