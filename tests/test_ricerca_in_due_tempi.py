"""La pagina risponde in due tempi: prima il modello, poi il firmware.

Proposta dall'utente il 17/08/2026: «per velocizzare la ricerca non puoi
anche prima di tutto trovare il modello e poi tramite caricamento
secondario caricare scheda tecnica e firmware quando questo è lento?».

Misurato prima di scrivere una riga: a cataloghi caldi l'identità e la
scheda tecnica costano zero, la ricerca firmware fino a dodici secondi su
dodici. Erano due domande diverse dentro la stessa attesa — e chi guarda
ha già davanti la foto e le specifiche del telefono giusto mentre aspetta
un dato che riguarda altro.

Il rischio di questa divisione è UNO SOLO e questi test lo presidiano: due
strade per la stessa domanda che finiscono per rispondere due cose
diverse sullo stesso telefono.
"""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AVVIA_WORKER"] = "0"


def _testo(html: str) -> str:
    return " ".join(re.sub(r"<[^>]*>", " ", html).split())


class BaseDueTempi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cartella = tempfile.mkdtemp(prefix="duetempi-")
        os.environ["DB_PATH"] = os.path.join(cartella, "t.db")

        from core import config as C, scan, storage

        C.DB_PATH = os.environ["DB_PATH"]
        C.COOKIE_SECURE = False
        # ACCESO QUI, ED È IL PUNTO. `tests/conftest.py` lo spegne per
        # tutta la suite, perché quarantadue test leggono la pagina come
        # farebbe un browser senza JavaScript. Questo file è il posto in
        # cui la modalità di produzione viene collaudata davvero.
        cls._due_tempi_prima = C.RICERCA_IN_DUE_TEMPI
        C.RICERCA_IN_DUE_TEMPI = True
        storage.reset_state()
        storage.init_db()

        # NESSUN TEST QUI TOCCA LA RETE. Le due fasi si distinguono
        # esattamente per questo: la prima non deve chiamare nessuno, e
        # il modo più onesto di verificarlo è far esplodere la rete.
        cls._live_originale = scan.sources.search_model_live
        cls._lookup_originale = scan._lookup_structured_for
        cls.chiamate = {"live": 0, "lookup": 0}

        def live_finta(query, *a, **kw):
            cls.chiamate["live"] += 1
            return [], None

        def lookup_finto(query, *a, **kw):
            cls.chiamate["lookup"] += 1
            return [], None

        scan.sources.search_model_live = live_finta
        scan._lookup_structured_for = lookup_finto

        from fastapi.testclient import TestClient

        from web.main import app

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from core import config as C, scan

        scan.sources.search_model_live = cls._live_originale
        scan._lookup_structured_for = cls._lookup_originale
        # SI RIMETTE COM'ERA, non a un valore scelto da qui. Forzarlo a
        # `False` significava lasciare in eredità uno stato agli altri
        # file: dodici test di `test_sito.py` passavano SOLO perché
        # questo file girava prima (ordine alfabetico) e spegneva
        # l'interruttore per loro. Da soli misuravano il vuoto — e un
        # test che passa grazie a un altro è peggio di un test rosso,
        # perché non lo scopri mai.
        C.RICERCA_IN_DUE_TEMPI = cls._due_tempi_prima

    def setUp(self):
        from web.main import RICERCHE

        RICERCHE.svuota() if hasattr(RICERCHE, "svuota") else None
        type(self).chiamate["live"] = 0
        type(self).chiamate["lookup"] = 0


class TestPrimoTempo(BaseDueTempi):
    def test_la_pagina_non_tocca_la_rete(self):
        """È tutto il punto: la prima risposta deve costare zero."""
        self.client.get("/?q=SM-A546B")
        self.assertEqual(self.chiamate["live"], 0)
        self.assertEqual(self.chiamate["lookup"], 0)

    def test_il_nome_del_modello_c_e_subito(self):
        pagina = self.client.get("/?q=SM-A546B").text
        self.assertIn("Galaxy A54", pagina)

    def test_il_nome_c_e_anche_mentre_si_aspetta(self):
        """SPARITO IN PRODUZIONE il 17/08/2026. Spostando il titolo dentro
        il frammento — perché quando il primo tempo non risolve deve poter
        essere corretto dal secondo — era sparito del tutto dalla fase di
        attesa: rotellina sopra una scheda tecnica senza intestazione,
        cioè l'esatto contrario di «prima si trova il modello»."""
        # Si usa un IMEI e non un codice modello perché il nome arriva
        # dalla copia del database TAC che viaggia nel repository: è
        # l'unico modo di verificare questa cosa senza dipendere da un
        # catalogo scaricato, cioè dalla connessione di chi lancia i test.
        pagina = self.client.get("/?q=861206074094914").text
        self.assertIn("firmware-in-arrivo", pagina)
        self.assertIn("<h2>realme Note 50</h2>", pagina)

    def test_mentre_si_aspetta_non_si_dichiara_un_esito(self):
        """«Nessun firmware» durante la ricerca è una risposta che non
        c'è ancora: peggio del silenzio, perché sembra definitiva."""
        pagina = self.client.get("/?q=codice-che-non-esiste-xyz").text
        blocco = pagina.split('firmware-in-arrivo')[1].split('</div>')[0]
        self.assertNotIn("Nessun firmware", blocco)

    def test_la_rotellina_sta_dove_andranno_i_dati(self):
        """Richiesta esplicita dell'utente: «lo fai capire a schermo con
        una rotellina fatta bene dove dovrebbero stare gli altri dati»."""
        pagina = self.client.get("/?q=SM-A546B").text
        self.assertIn('data-firmware-per="SM-A546B"', pagina)
        self.assertIn("rotella", pagina)
        self.assertIn("Cerco il firmware", pagina)

    def test_chi_non_ha_javascript_ha_una_via_d_uscita(self):
        """Senza, resterebbe davanti a una rotellina per sempre."""
        pagina = self.client.get("/?q=SM-A546B").text
        self.assertIn("<noscript>", pagina)
        self.assertIn("completo=1", pagina)

    def test_con_completo_la_pagina_torna_intera(self):
        pagina = self.client.get("/?q=SM-A546B&completo=1").text
        self.assertNotIn("data-firmware-per", pagina)
        self.assertGreaterEqual(self.chiamate["lookup"], 1)

    def test_l_interruttore_generale_spegne_tutto(self):
        from core import config as C

        C.RICERCA_IN_DUE_TEMPI = False
        try:
            self.assertNotIn("data-firmware-per",
                             self.client.get("/?q=SM-A546B").text)
        finally:
            C.RICERCA_IN_DUE_TEMPI = True


class TestSecondoTempo(BaseDueTempi):
    def test_il_frammento_non_e_una_pagina(self):
        """Deve entrare dentro la pagina già aperta, non sostituirla."""
        pezzo = self.client.get("/ricerca/firmware?q=SM-A546B").text
        self.assertNotIn("<html", pezzo.lower())
        self.assertNotIn("<nav", pezzo.lower())

    def test_il_frammento_cerca_davvero(self):
        self.client.get("/ricerca/firmware?q=SM-A546B")
        self.assertGreaterEqual(self.chiamate["lookup"], 1)

    def test_dice_la_stessa_cosa_della_pagina_intera(self):
        """IL TEST PIÙ IMPORTANTE DI QUESTO FILE. Due strade per la
        stessa domanda che divergono sono peggio di una strada lenta:
        una pagina direbbe una versione e l'altra un'altra, sullo
        stesso telefono, senza che nessuno se ne accorga."""
        for q in ("SM-A546B", "CPH2781", "codice-che-non-esiste"):
            with self.subTest(q=q):
                pezzo = _testo(self.client.get(f"/ricerca/firmware?q={q}").text)
                intera = _testo(self.client.get(f"/?q={q}&completo=1").text)
                self.assertTrue(pezzo)
                self.assertIn(pezzo[:60], intera)

    def test_un_imei_richiede_l_imei_non_il_modello(self):
        """Segnalato dall'utente il 17/08/2026 con l'IMEI
        861206074094914: il TAC risponde «Note 50», e il secondo tempo
        chiedeva QUEL nome invece dell'IMEI. Cercato da solo, senza
        l'ancoraggio al TAC, «Note 50» risolve su «realme C60» — un altro
        telefono, con un'altra scheda tecnica e un'altra foto. La pagina
        cambiava telefono sotto gli occhi di chi guardava."""
        imei = "861206074094914"
        pagina = self.client.get(f"/?q={imei}").text
        chiesto = re.search(r'data-firmware-per="([^"]*)"', pagina)
        self.assertIsNotNone(chiesto, "manca il blocco del secondo tempo")
        self.assertEqual(chiesto.group(1), imei)
        # E la via d'uscita senza JavaScript deve portare allo stesso posto.
        self.assertIn(f"/?q={imei}&amp;completo=1", pagina)

    def test_una_domanda_vuota_non_da_errore(self):
        risposta = self.client.get("/ricerca/firmware?q=")
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta.text.strip(), "")


class TestLaCacheNonSiSporca(BaseDueTempi):
    def test_il_risultato_parziale_non_finisce_in_memoria(self):
        """Se ci finisse, verrebbe servito come completo a chiunque
        cerchi lo stesso modello nei minuti successivi — compreso il
        secondo caricamento, che resterebbe fermo sulla rotellina."""
        from web.main import _esito_ricerca

        parziale = _esito_ricerca("SM-A546B", senza_rete=True)
        self.assertTrue(parziale.get("firmware_in_arrivo"))
        self.assertEqual(self.chiamate["lookup"], 0)

        completo = _esito_ricerca("SM-A546B")
        self.assertGreaterEqual(self.chiamate["lookup"], 1)
        self.assertFalse(completo.get("firmware_in_arrivo"))


if __name__ == "__main__":
    unittest.main()
