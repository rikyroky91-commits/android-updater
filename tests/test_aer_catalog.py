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
        # `None` = mai scaricato, quindi il prossimo `carica()` riprova.
        # Prima qui c'era `0.0`, che sembrava «scaduto da sempre» e invece
        # è un istante di `time.monotonic()` quasi coincidente con l'avvio
        # del processo: la cache risultava FRESCA, `_scarica` non veniva
        # mai chiamato e il test falliva su una macchina appena avviata
        # mentre passava su una accesa da più di dodici ore.
        aer._scaricato_a = None

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


class TestIntegrazioneNelleFonti(unittest.TestCase):
    """Il catalogo AER si AGGIUNGE alle fonti esistenti, non le sostituisce.

    La misura del 2026-08-02 dice perché: sulla pagina ufficiale Honor ha 26
    modelli tutti con versione contro i 21 del JSON, e vivo 20 contro 15.
    Sostituirle avrebbe tolto dati. Quello che questa fonte aggiunge e che
    nessun'altra dà sono i codici modello verificati, la finestra di
    supporto, e OnePlus — che non ha nessun'altra fonte strutturata.
    """

    def setUp(self):
        from core import sources
        self.sources = sources
        aer.reset_cache()
        aer._dispositivi, aer._per_nome, aer._per_codice = aer._indicizza(VOCI)
        aer._scaricato_a = time.monotonic()

    def tearDown(self):
        aer.reset_cache()

    def test_le_fonti_per_marca_restano_tutte(self):
        """Il punto della scelta: nessuna fonte ufficiale è stata rimossa."""
        chiavi = {s.key for s in self.sources.all_sources()}
        for attesa in ("honor_aer", "realme_aer", "oppo_aer", "vivo_aer", "aer_catalog"):
            self.assertIn(attesa, chiavi, f"la fonte «{attesa}» è sparita dal registro")

    def test_nome_samsung_allineato_alle_altre_fonti(self):
        """L'AER scrive «Samsung Galaxy S25 Ultra», la fonte FOTA produce
        «Galaxy S25 Ultra». Senza allineamento sarebbero due dispositivi
        distinti in archivio, ciascuno con metà della storia."""
        self.assertEqual(
            self.sources.nome_aer_normalizzato("Samsung Galaxy S25 Ultra", "Samsung"),
            "Galaxy S25 Ultra")
        self.assertEqual(
            self.sources.nome_aer_normalizzato("Google Pixel 10 Pro Fold", "Google"),
            "Pixel 10 Pro Fold")

    def test_motorola_ricondotto_alla_forma_del_progetto(self):
        """L'AER scrive «Motorola moto g14», il resto del progetto «Moto
        G14»: senza questo erano due dispositivi diversi. È il doppione che
        ha fatto fallire un test della cronologia ricerche."""
        self.assertEqual(
            self.sources.nome_aer_normalizzato("Motorola moto g14", "Motorola"),
            "Moto G14")

    def test_le_altre_marche_tengono_il_prefisso(self):
        """Lì il prefisso È la convenzione del progetto: toglierlo
        creerebbe il problema opposto."""
        for nome in ("OPPO Find X9 Pro", "vivo V70", "realme 14 Pro 5G",
                     "HONOR 600e", "OnePlus 12", "Redmi 12"):
            self.assertEqual(self.sources.nome_aer_normalizzato(nome), nome)

    def test_la_versione_di_lancio_non_diventa_versione_del_dispositivo(self):
        """Il punto più delicato dell'integrazione.

        Questa fonte conosce solo la versione DI LANCIO. Dichiararla come
        `android_version` la rendeva un dato strutturato che scavalcava le
        altre fonti: in prova, un «Moto G14 — patch di luglio 2026»,
        datato e attuale, veniva sostituito in cronologia da un «Android
        14» di fabbrica. Per un tracker degli aggiornamenti è il contrario
        di quello che serve.
        """
        con_versione = [d for d in aer.all_devices() if d["launch_android"]]
        self.assertTrue(con_versione, "la fixture non ha device con versione di lancio")
        item = self.sources._item_da_aer(con_versione[0])
        self.assertIsNone(item.android_version)
        # Non va persa, però: resta leggibile e marcata come di fabbrica.
        self.assertIn("FABBRICA", item.size_info.upper())

    def test_il_titolo_non_contiene_versioni_ne_date(self):
        """`RawItem.text` (titolo + versione + build + sommario) è il testo
        che gli estrattori rileggono: una versione scritta nel titolo
        ricrea il campo appena tolto, e «patch fino a 2031-10-30» diventa
        un livello di patch datato 2031 — un dato falso, nel futuro.
        `size_info` invece non entra in `text`, ed è lì che i dettagli
        vanno scritti."""
        from core import extract
        for device in aer.all_devices():
            item = self.sources._item_da_aer(device)
            estratto = extract.extract_all(item.text)
            self.assertIsNone(estratto.android_version,
                              f"versione estraibile dal titolo: «{item.title}»")
            self.assertIsNone(estratto.patch_level,
                              f"data estraibile dal titolo: «{item.title}»")

    def test_ricerca_per_codice_tecnico(self):
        """È il motivo più frequente di ricerca a vuoto: un codice che
        nessun dataset conosce. Qui ce ne sono 1404 verificati."""
        trovati = self.sources._lookup_aer_catalog("CPH2791")
        self.assertTrue(trovati)
        self.assertEqual(trovati[0].device, "OPPO Find X9 Pro")

    def test_finestra_di_supporto_riportata(self):
        trovati = self.sources._lookup_aer_catalog("CPH2791")
        self.assertIn("patch fino a", trovati[0].size_info)

    def test_modello_sconosciuto_non_inventa_nulla(self):
        self.assertEqual(self.sources._lookup_aer_catalog("Nokia 3310"), [])

    def test_fonte_irraggiungibile_riportata_non_sollevata(self):
        aer.reset_cache()
        originale = aer.carica
        aer.carica = lambda forza=False: []
        try:
            items, errore = self.sources.fetch_aer_catalog()
        finally:
            aer.carica = originale
        self.assertEqual(items, [])
        self.assertTrue(errore, "una fonte vuota deve dichiarare il motivo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
