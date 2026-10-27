"""Una ricerca partita da un IMEI non può rispondere con il telefono di un
altro produttore.

Segnalato dall'utente il 27/10/2026 con l'IMEI 867232055130331, un moto
g05: il database TAC scrive «SECUMORE, SECUMORE G05», la ricerca per «G05»
è debole, l'AI la traduce in «Motorola moto g05» e la pagina usciva con
titolo SECUMORE G05, codice XT2523-3 e firmware del moto.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core import aiquery, imeicheck
from web import main


def _imei(marca: str, modello: str, codice: str = "") -> dict:
    return {"marca": marca, "modello": modello, "codice": codice,
            "modello_cercato": codice or modello}


def _trovato(nome: str, codice: str = "") -> dict:
    return {"trovato": True, "nome": nome, "codice": codice}


class TestRispostaDiUnAltraMarca(unittest.TestCase):
    def test_marche_diverse(self):
        casi = [
            (_imei("SECUMORE", "G05"), _trovato("Motorola moto g05", "XT2523-3")),
            (_imei("ZTE", "A15"), _trovato("Samsung Galaxy A15", "SM-A155F")),
            (_imei("NUBIA", "A56"), _trovato("Galaxy A56 5G")),
            (_imei("VIVO", "Y05"), _trovato("Motorola moto g05")),
            (_imei("OnePlus", "Nord CE 3"), _trovato("realme 12x 5G")),
            (_imei("SAMSUNG", "Galaxy A16"), _trovato("Redmi Note 13")),
        ]
        for imei, risultato in casi:
            with self.subTest(tac=imei["marca"], trovato=risultato["nome"]):
                self.assertTrue(main._risposta_di_unaltra_marca(risultato, imei))

    def test_stesso_produttore_scritto_in_un_altro_modo(self):
        casi = [
            (_imei("MOTOROLA", "MOTO G05"), _trovato("Motorola moto g05")),
            (_imei("LENOVO", "MOTO G05"), _trovato("Motorola moto g05")),
            (_imei("REDMI", "Note 13"), _trovato("Xiaomi Redmi Note 13")),
            (_imei("POCO", "X6 Pro"), _trovato("Xiaomi POCO X6 Pro 5G")),
            (_imei("SAMSUNG", "A15"), _trovato("Galaxy A15")),
            (_imei("GOOGLE", "Pixel 8"), _trovato("Google Pixel 8")),
            (_imei("vivo", "Y36"), _trovato("vivo Y36")),
            (_imei("HUAWEI", "nova 12"), _trovato("Huawei nova 12 SE")),
        ]
        for imei, risultato in casi:
            with self.subTest(tac=imei["marca"], trovato=risultato["nome"]):
                self.assertFalse(main._risposta_di_unaltra_marca(risultato, imei))

    def test_senza_marca_riconoscibile_non_si_scarta(self):
        # «Non so» non è «è un altro»: il nome HMD di un Nokia, un nome
        # senza produttore, una marca minore che il catalogo conosce.
        casi = [
            (_imei("HMD", "G21"), _trovato("Nokia G21")),
            (_imei("TCL", "40 SE"), _trovato("40 SE")),
            (_imei("ZTE", "Blade A75"), _trovato("ZTE Blade A75 5G")),
        ]
        for imei, risultato in casi:
            with self.subTest(tac=imei["marca"], trovato=risultato["nome"]):
                self.assertFalse(main._risposta_di_unaltra_marca(risultato, imei))

    def test_niente_trovato_niente_da_scartare(self):
        self.assertFalse(main._risposta_di_unaltra_marca(
            {"trovato": False, "nome": "Motorola moto g05"}, _imei("SECUMORE", "G05")))


class TestPaginaImeiNonIbrida(unittest.TestCase):
    def test_il_firmware_del_moto_non_finisce_sotto_secumore(self):
        main.RICERCHE.svuota()
        finta = aiquery.Interpretazione(proposte=("Motorola moto g05",),
                                        motivo="corrisponde alla sigla G05")
        vero = main._cerca_davvero

        def cerca(q, senza_rete=False):
            if "moto g05" in q.lower():
                return {"trovato": True, "nome": "Motorola moto g05",
                        "codice": "XT2523-3", "query": q, "riga": "Android 15",
                        "fonte": "Motorola", "senza_firmware": False,
                        "scheda": {"trovata": False}}
            return vero(q, senza_rete=senza_rete)

        try:
            with patch.object(aiquery, "disponibile", return_value=True), \
                 patch.object(aiquery, "interpreta", return_value=finta), \
                 patch.object(main, "_cerca_davvero", side_effect=cerca), \
                 patch.object(main.imeicheck, "identify",
                              return_value=("SECUMORE", "SECUMORE, SECUMORE G05")):
                imei = main._esito_imei("867232055130331")
                cercato = main._esito_ricerca(imei["modello_cercato"])
                # La premessa del difetto: senza il freno questa sarebbe la pagina.
                self.assertEqual(cercato.get("codice"), "XT2523-3")
                pagina = main._ancora_esito_imei(cercato, imei)
        finally:
            main.RICERCHE.svuota()

        self.assertEqual(pagina["nome"], "SECUMORE G05")
        self.assertNotEqual(pagina["codice"], "XT2523-3")
        self.assertNotIn("Android 15", pagina.get("riga") or "")
        self.assertFalse(pagina.get("ai_da"))
        self.assertFalse(pagina.get("ai_a"))


class TestTacCurato(unittest.TestCase):
    def test_86723205_e_un_moto_g05(self):
        with open(imeicheck.FILE_TAC_CURATO, encoding="utf-8-sig") as f:
            curati = imeicheck.carica_tac_curati(f.read())
        self.assertEqual(curati["86723205"], ("Motorola", "moto g05"))


if __name__ == "__main__":
    unittest.main()
