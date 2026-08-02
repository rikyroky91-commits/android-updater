"""Test del catalogo Android Enterprise Recommended.

Come per la fonte Oppo, le voci usate qui sono **registrate dall'API vera**
(`tests/fixtures/aer_devices.json`, 28 voci reali su 706, catturate il
2026-08-02) e non ricostruite a mano.

Il test più importante di questo file è
`test_la_versione_attuale_non_si_prende_da_qui`: fissa per iscritto un
errore che è molto facile commettere e impossibile da notare a occhio.
"""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import aer_catalog as aer  # noqa: E402
from core import config as C  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "fixtures", "aer_devices.json")
with open(_FIXTURES, encoding="utf-8") as _f:
    CATALOGO = json.load(_f)

VOCI = CATALOGO["items"]


def voce(nome: str) -> dict:
    for v in VOCI:
        if v["displayName"] == nome:
            return v
    raise AssertionError(f"«{nome}» non è più nella fixture: ricatturala")


class TestLetturaVoceReale(unittest.TestCase):
    def test_codici_modello_estratti_dalla_stringa(self):
        """L'API scrive i codici come stringa unica separata da virgole,
        non come lista: `"CPH2791, PLG110"`."""
        letto = aer.parse_device(voce("OPPO Find X9 Pro"))
        self.assertIn("CPH2791", letto["model_codes"])
        self.assertIn("PLG110", letto["model_codes"])

    def test_brand_ricondotto_a_quelli_del_tracker(self):
        self.assertEqual(aer.parse_device(voce("OPPO Find X9 Pro"))["brand"], C.OPPO)
        self.assertEqual(aer.parse_device(voce("OnePlus 12"))["brand"], C.OPPO)
        self.assertEqual(aer.parse_device(voce("realme 14 Pro 5G"))["brand"], C.OPPO)
        self.assertEqual(aer.parse_device(voce("Google Pixel 9"))["brand"], C.PIXEL)
        self.assertEqual(aer.parse_device(voce("Samsung Galaxy S25 Ultra"))["brand"], C.SAMSUNG)

    def test_marca_sconosciuta_non_scartata(self):
        """Il catalogo comprende produttori industriali che l'app non
        traccia: vanno classificati «altri», non buttati via."""
        estranei = [v for v in VOCI
                    if str(v.get("brand", "")).lower() not in aer._BRAND_MAP]
        if not estranei:
            self.skipTest("nessuna marca estranea nella fixture")
        letto = aer.parse_device(estranei[0])
        self.assertEqual(letto["brand"], C.OTHER)
        self.assertTrue(letto["device_model"])

    def test_finestra_di_supporto_letta(self):
        """È il dato che giustifica questa fonte: fino a quando il modello
        riceve patch, e con che cadenza."""
        letto = aer.parse_device(voce("realme 14 Pro 5G"))
        self.assertRegex(letto["security_until"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(letto["security_frequency"], "quarterly")

    def test_dataNotProvided_diventa_assenza(self):
        """L'API scrive la stringa «dataNotProvided» invece di omettere il
        campo. Finirebbe stampata tale e quale in interfaccia."""
        letto = aer.parse_device(voce("OPPO Find X9 Pro"))
        self.assertIsNone(letto["launch_android"])
        for valore in letto.values():
            self.assertNotEqual(valore, "dataNotProvided")

    def test_versione_di_lancio_come_numero(self):
        letto = aer.parse_device(voce("OPPO Find N2 Flip"))
        self.assertEqual(letto["launch_android"], 13)


class TestVersioneAttuale(unittest.TestCase):
    """Il punto delicato di tutta questa fonte."""

    def test_la_versione_attuale_non_si_prende_da_qui(self):
        """`hardwareFeatures.os` sembra la versione attuale e non lo è: il
        Galaxy S21 FE vi risulta Android 16, che non ha mai ricevuto.
        Nessun campo prodotto da questo modulo deve contenerla."""
        grezzo = voce("Samsung Galaxy S21 FE 5G")
        self.assertEqual((grezzo.get("hardwareFeatures") or {}).get("os"), "Android 16",
                         "la fixture non rappresenta più il caso che questo test protegge")
        letto = aer.parse_device(grezzo)
        self.assertNotIn("android_version", letto)
        self.assertNotIn("os_version", letto)
        self.assertNotIn("build", letto)

    def test_chiedere_la_versione_attuale_e_un_errore_esplicito(self):
        with self.assertRaises(NotImplementedError):
            aer.verifica_versione_attuale(voce("Samsung Galaxy S21 FE 5G"))

    def test_il_campo_os_non_distingue_i_dispositivi(self):
        """Prova del nove: se `os` fosse una rilevazione, dispositivi di
        generazioni diverse avrebbero valori diversi. Non è così."""
        valori = {(v.get("hardwareFeatures") or {}).get("os") for v in VOCI}
        self.assertLess(len(valori), len(VOCI) / 3,
                        "il campo os sembra ora differenziato: rivalutare la scelta")


class TestIndicizzazione(unittest.TestCase):
    def setUp(self):
        aer.reset_cache()
        aer._dispositivi, aer._per_nome, aer._per_codice = aer._indicizza(VOCI)
        # Senza questo il catalogo risulta scaduto e `carica()` andrebbe in
        # rete: un test che tocca la rete fallisce a caso e smette di essere
        # creduto.
        aer._scaricato_a = time.monotonic()

    def tearDown(self):
        aer.reset_cache()

    def test_ricerca_per_codice_tecnico(self):
        trovato = aer.lookup("CPH2791")
        self.assertIsNotNone(trovato)
        self.assertEqual(trovato["device_model"], "OPPO Find X9 Pro")

    def test_codice_minuscolo_riconosciuto(self):
        self.assertIsNotNone(aer.lookup("cph2791"))

    def test_ricerca_per_nome_con_e_senza_marca(self):
        for scritto in ("OPPO Find X9 Pro", "find x9 pro", "FindX9Pro", "  Find  X9  Pro "):
            self.assertIsNotNone(aer.lookup(scritto), f"«{scritto}» non trovato")

    def test_nome_composto_indicizzato_su_ogni_prodotto(self):
        """«OPPO Reno13 F 5G / Reno13 FS 5G» è una voce sola per due
        prodotti: chi cerca il secondo nome deve trovarla lo stesso."""
        composti = [v for v in VOCI if "/" in v["displayName"]]
        if not composti:
            self.skipTest("nessun nome composto nella fixture")
        _d, per_nome, _c = aer._indicizza(composti)
        primo = composti[0]["displayName"]
        secondo = primo.split("/")[-1].strip()
        self.assertIn(aer.normalize(secondo), per_nome,
                      f"«{secondo}» non indicizzato da «{primo}»")

    def test_codice_a_nome_commerciale(self):
        self.assertEqual(aer.name_for_code("CPH2791"), "OPPO Find X9 Pro")

    def test_nomi_nudi_ambigui_non_producono_abbinamenti_falsi(self):
        """«OnePlus 12» e «Redmi 12» si riducono entrambi a `12` una volta
        tolta la marca. Prima della correzione «OnePlus 12» restituiva
        «Redmi 12»: un dato sbagliato che sembra buono, cioè il peggior
        esito possibile. La forma contesa va scartata, non assegnata."""
        self.assertEqual(aer.normalize_short("OnePlus 12"), aer.normalize_short("Redmi 12"))
        trovato = aer.lookup("OnePlus 12")
        self.assertTrue(
            trovato is None or trovato["device_model"] == "OnePlus 12",
            f"abbinamento falso: «OnePlus 12» → «{trovato and trovato['device_model']}»",
        )

    def test_il_nome_completo_resta_risolvibile(self):
        """La difesa contro le ambiguità non deve rendere irraggiungibili i
        modelli che un nome completo identifica benissimo."""
        for nome in ("OnePlus 12", "Redmi 12"):
            trovato = aer.lookup(nome)
            self.assertIsNotNone(trovato, f"«{nome}» non più trovabile")
            self.assertEqual(trovato["device_model"], nome)

    def test_testo_sconosciuto_non_inventa_nulla(self):
        self.assertIsNone(aer.lookup("Nokia 3310"))
        self.assertIsNone(aer.lookup(""))


class TestGuastoDellaFonte(unittest.TestCase):
    def test_errore_di_rete_non_azzera_il_catalogo_gia_in_memoria(self):
        """Meglio un catalogo di ieri che nessun catalogo: un guasto
        temporaneo non deve far sparire i dispositivi dall'app."""
        aer.reset_cache()
        aer._dispositivi, aer._per_nome, aer._per_codice = aer._indicizza(VOCI)
        aer._scaricato_a = 0.0        # scaduto: forza un nuovo scaricamento

        originale = aer._scarica
        aer._scarica = lambda: (_ for _ in ()).throw(OSError("rete assente"))
        try:
            risultato = aer.carica()
        finally:
            aer._scarica = originale

        self.assertEqual(len(risultato), len(VOCI))
        self.assertIn("non raggiungibile", aer.status())
        aer.reset_cache()

    def test_risposta_senza_items_non_passa_per_buona(self):
        aer.reset_cache()
        originale = aer._scarica
        aer._scarica = lambda: (_ for _ in ()).throw(ValueError("manca 'items'"))
        try:
            self.assertEqual(aer.carica(), [])
        finally:
            aer._scarica = originale
            aer.reset_cache()


if __name__ == "__main__":
    unittest.main(verbosity=2)
