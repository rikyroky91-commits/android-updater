"""Il sito dentro un browser vero.

## Perché esiste (05/10/2026)

La segnalazione «cercando a505 non ho la scheda tecnica» è passata sotto
1.805 test verdi. Non per sfortuna: il difetto stava in quello che il
BROWSER fa con le risposte del server — mette un pezzo di HTML al posto di
un altro — e la suite leggeva le risposte una per una, come un browser
senza JavaScript. Ogni risposta era giusta; era la pagina che ne risultava
a essere sbagliata, e nessun test guardava la pagina.

Qui la si guarda: un server vero (uvicorn, su una porta locale), Chromium
vero, e le asserzioni sul documento che una persona ha davanti DOPO che gli
script hanno fatto il loro lavoro.

## Cosa NON è

Non è una seconda suite. I contenuti — quale firmware, quale nome, quale
scheda — li collaudano i test che leggono le risposte, che costano un
centesimo di questi. Qui stanno solo le cose che esistono soltanto nel
browser: la sostituzione del risultato, ciò che deve sopravvivere alla
sostituzione, la traduzione di quello che arriva dopo, gli errori degli
script.

## Il secondo tempo si comanda, non si aspetta

La fonte firmware finta resta ferma finché il test non la sblocca
(`threading.Event`). Così «mentre si aspetta» è uno stato in cui il test
può stare quanto vuole, non una finestra di qualche decimo di secondo da
centrare: un test che dipende da quanto è veloce la macchina passa su
quella di chi l'ha scritto e cade in CI, o peggio il contrario.

## Senza Playwright

In locale il file si salta, dichiarandolo. In CI no: `tests.yml` installa
Chromium e imposta `PROVA_BROWSER=1`, e con quella variabile un Playwright
che manca è un errore. Un file che si salta da solo ovunque è il modo più
silenzioso di smettere di collaudare.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AVVIA_WORKER"] = "0"

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - dipende dalla macchina
    sync_playwright = None

from test_ricerca_in_due_tempi import _ConLeSchede, _voce_samsung  # noqa: E402

OBBLIGATORIO = os.environ.get("PROVA_BROWSER") == "1"

# Quanto si aspetta, al massimo, che il browser finisca una cosa. È un tetto
# e non una pausa: quando la cosa succede il test prosegue subito.
ATTESA_MS = 15_000


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _NelBrowser(_ConLeSchede):
    """Un server vero e un Chromium vero attorno alle due fasi."""

    #: La domanda che il primo tempo non sa leggere e a cui la fonte
    #: firmware risponde: la forma generale della segnalazione.
    SCONOSCIUTA = "il galaxy che arriva dopo"

    @classmethod
    def setUpClass(cls):
        if sync_playwright is None:
            if OBBLIGATORIO:
                raise AssertionError(
                    "PROVA_BROWSER=1 ma Playwright non è installato: i test nel "
                    "browser non possono saltarsi da soli in CI")
            raise unittest.SkipTest("Playwright non installato: test nel browser saltati")
        super().setUpClass()

        import uvicorn

        from web.main import app

        cls.porta = _porta_libera()
        cls.base = f"http://127.0.0.1:{cls.porta}"
        cls._server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=cls.porta, log_level="error"))
        cls._filo = threading.Thread(target=cls._server.run, daemon=True)
        cls._filo.start()
        scadenza = time.monotonic() + 20
        while not cls._server.started:
            if time.monotonic() > scadenza:
                raise AssertionError("il server di prova non è partito")
            time.sleep(0.05)

        cls._pw = sync_playwright().start()
        try:
            cls._chromium = cls._pw.chromium.launch()
        except Exception as errore:
            cls._pw.stop()
            cls._ferma_server()
            if OBBLIGATORIO:
                raise
            raise unittest.SkipTest(f"Chromium non disponibile: {errore}")

    @classmethod
    def _ferma_server(cls):
        cls._server.should_exit = True
        cls._filo.join(timeout=10)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_chromium", None):
            cls._chromium.close()
            cls._pw.stop()
        if getattr(cls, "_server", None):
            cls._ferma_server()
            super().tearDownClass()

    def setUp(self):
        super().setUp()
        from core import scan

        # LA FONTE FIRMWARE ASPETTA IL TEST. Risponde solo quando
        # `self.via` viene alzata, così il primo tempo resta sullo schermo
        # per tutto il tempo che serve a guardarlo.
        self.via = threading.Event()
        voce = _voce_samsung("SM-A325F", "Galaxy A32", "A325FXXSCDYB2", 13)
        conta = type(self).chiamate
        via = self.via

        def lookup(query, *a, **kw):
            conta["lookup"] += 1
            via.wait(timeout=ATTESA_MS / 1000)
            if query.strip().lower() in (self.SCONOSCIUTA, "a325"):
                return [dict(voce)], None
            return [], None

        scan._lookup_structured_for = lookup

        self.contesto = self._chromium.new_context(locale="it-IT")
        self.pagina = self.contesto.new_page()
        self.pagina.set_default_timeout(ATTESA_MS)
        self.errori_js: list[str] = []
        self.pagina.on("pageerror", lambda e: self.errori_js.append(str(e)))
        # Fuori da qui non esce niente: le foto dei telefoni stanno su un
        # sito di terzi, e un test non deve dipendere da lui.
        self.pagina.route("**/*", lambda rotta: (
            rotta.continue_() if rotta.request.url.startswith(self.base)
            else rotta.abort()))

    def tearDown(self):
        self.via.set()          # nessuna richiesta resta appesa al test dopo
        self.contesto.close()
        super().tearDown()

    def _apri(self, domanda: str, **parametri) -> None:
        from urllib.parse import urlencode

        self.pagina.goto(f"{self.base}/?{urlencode({'q': domanda, **parametri})}",
                         wait_until="domcontentloaded")

    def _aspetta_il_firmware(self) -> None:
        """Sblocca il secondo tempo e aspetta che il firmware sia in pagina.

        Si aspetta il RIQUADRO DEL FIRMWARE, non un segno della
        sostituzione: quello compare comunque, sia che lo script cambi
        tutto il risultato sia che cambi solo lui. È ciò che i test
        guardano DOPO a dire quale delle due cose è successa.
        """
        self.via.set()
        self.pagina.wait_for_selector(".firmware-risultato")

    def _testo(self, selettore: str) -> str:
        return " ".join(self.pagina.inner_text(selettore).split())


class TestLaSchedaArrivaConIlSecondoTempo(_NelBrowser):
    """LA SEGNALAZIONE, com'era sullo schermo: nome e firmware del telefono
    giusto sopra una pagina senza scheda tecnica."""

    def test_prima_non_c_e_poi_c_e_senza_ricaricare(self):
        self._apri(self.SCONOSCIUTA)

        # MENTRE SI ASPETTA: il primo tempo non sa che telefono è.
        self.assertEqual(self.pagina.locator("section.scheda").count(), 0)
        self.assertEqual(self.pagina.locator("[data-firmware-per]").count(), 1)
        self.assertEqual(
            self.pagina.locator('form[action="/parco/aggiungi"]').count(), 0,
            "la pagina provvisoria offre il tasto del parco")
        # Un segno sulla pagina: se dopo c'è ancora, il risultato è stato
        # sostituito DENTRO questa pagina e non ricaricandola.
        self.pagina.evaluate("window.__questaPagina = true")

        self._aspetta_il_firmware()

        self.assertIn("Samsung Galaxy A32", self._testo("[data-nome-risultato] h2"))
        self.assertIn("A325FXXSCDYB2", self._testo(".firmware-risultato"))
        self.assertEqual(self.pagina.locator("section.scheda").count(), 1,
                         "il firmware è arrivato, la scheda tecnica no")
        self.assertEqual(self.pagina.locator(".rotella").count(), 0)
        self.assertIn("Helio G80", self._testo(".cpu-in-evidenza"))
        self.assertEqual(self.pagina.locator("details.completa").count(), 1)
        self.assertIn("Galaxy A32", self.pagina.title())
        self.assertTrue(self.pagina.evaluate("window.__questaPagina === true"),
                        "la pagina è stata ricaricata invece che aggiornata")
        self.assertEqual(self.errori_js, [])

    def test_il_tasto_del_parco_porta_i_valori_del_telefono_trovato(self):
        """Marca vuota e chiave costruita sul testo digitato: è quello che
        il tasto spediva quando restava quello del primo tempo."""
        self._apri(self.SCONOSCIUTA)
        self._aspetta_il_firmware()
        modulo = self.pagina.evaluate("""() => {
            const f = document.querySelector('form[action="/parco/aggiungi"]');
            return f && {chiave: f.chiave.value, brand: f.brand.value, modello: f.modello.value};
        }""")
        self.assertEqual(modulo, {"chiave": "samsung|a32", "brand": "Samsung",
                                  "modello": "Samsung Galaxy A32"})


class TestLaSostituzioneNonDisturba(_NelBrowser):
    """Il risultato cambia sotto gli occhi di chi lo sta usando: quello che
    quella persona ha fatto nell'attesa deve restare."""

    def test_la_scheda_aperta_resta_aperta_e_la_barra_non_si_tocca(self):
        self._apri("a325")
        # Il primo tempo «a325» lo riconosce: la scheda c'è già.
        self.pagina.wait_for_selector("details.completa")
        self.pagina.evaluate("document.querySelector('details.completa').open = true")
        self.pagina.fill("#q", "sto già scrivendo altro")

        self._aspetta_il_firmware()

        self.assertIn("A325FXXSCDYB2", self._testo(".firmware-risultato"))
        self.assertTrue(
            self.pagina.evaluate("document.querySelector('details.completa').open"),
            "la scheda tecnica completa si è richiusa da sola")
        self.assertEqual(self.pagina.input_value("#q"), "sto già scrivendo altro")
        self.assertEqual(self.errori_js, [])

    def test_in_un_altra_lingua_anche_quello_che_arriva_dopo_e_tradotto(self):
        """`lingue.js` traduce la pagina quando si carica e poi segue le
        modifiche. Il risultato completo arriva DOPO: se chi lo inserisce
        lo facesse in un modo che l'osservatore non vede, metà pagina
        tornerebbe in italiano a ogni ricerca."""
        self.contesto.add_init_script(
            "try { localStorage.setItem('mut-lingua', 'en'); } catch (e) {}")
        self._apri(self.SCONOSCIUTA)
        self._aspetta_il_firmware()
        self.pagina.wait_for_function(
            "document.querySelector('#risultato-ricerca').innerText"
            ".includes('Add to the test fleet')")
        testo = self._testo("#risultato-ricerca")
        self.assertIn("(direct lookup)", testo)
        self.assertNotIn("Aggiungi al parco di test", testo)

    def test_lo_striscione_dell_ai_resta_dopo_la_sostituzione(self):
        self._apri(self.SCONOSCIUTA, ai="quel samsung grigio")
        self.assertIn("quel samsung grigio", self._testo(".interpretato"))
        self._aspetta_il_firmware()
        self.assertIn("quel samsung grigio", self._testo(".interpretato"))


class TestQuandoIlSecondoTempoNonArriva(_NelBrowser):
    def test_un_errore_del_server_si_dice_e_si_offre_la_pagina_intera(self):
        """Una rotellina che gira per sempre è peggio di un errore."""
        self.pagina.route("**/ricerca/firmware*",
                          lambda rotta: rotta.fulfill(status=500, body="guasto"))
        self._apri(self.SCONOSCIUTA)
        self.pagina.wait_for_function(
            "document.querySelector('[data-firmware-per]')"
            ".innerText.includes('Non sono riuscito')")
        collegamento = self.pagina.get_attribute("[data-firmware-per] a", "href")
        self.assertIn("completo=1", collegamento)
        self.assertEqual(self.pagina.locator(".rotella").count(), 0)

    def test_la_pagina_intera_non_aspetta_niente(self):
        """È la via d'uscita offerta qui sopra, e quella di chi non ha
        JavaScript: deve arrivare già completa."""
        self.via.set()
        self._apri(self.SCONOSCIUTA, completo=1)
        self.assertEqual(self.pagina.locator("[data-firmware-per]").count(), 0)
        self.assertEqual(self.pagina.locator("section.scheda").count(), 1)
        self.assertEqual(
            self.pagina.locator('form[action="/parco/aggiungi"]').count(), 1)


class TestNessunaPaginaRompeIPropriScript(_NelBrowser):
    """Il giro delle pagine: ognuna deve caricarsi e nessuno script deve
    lanciare un errore. Non dice che la pagina è giusta — dice che non è
    rotta, ed è la cosa che un deploy sbagliato fa per prima."""

    PAGINE = (
        "/", "/?q=SM-A546B&completo=1", "/?q=codice-che-non-esiste&completo=1",
        "/novita", "/dispositivi", "/catalogo", "/diagnostica",
        "/confronto?a=SM-A546B&b=SM-A325F", "/simili?q=SM-A325F",
        "/login", "/registrati", "/parco",
    )

    def test_ogni_pagina_si_carica_senza_errori_javascript(self):
        self.via.set()
        for percorso in self.PAGINE:
            with self.subTest(pagina=percorso):
                self.errori_js.clear()
                risposta = self.pagina.goto(self.base + percorso, wait_until="load")
                self.assertLess(risposta.status, 400, f"{percorso}: HTTP {risposta.status}")
                # Gli script sono `defer`: a `load` hanno già girato. Un
                # istante in più per ciò che parte da un timer d'avvio.
                self.pagina.wait_for_timeout(150)
                self.assertEqual(self.errori_js, [], f"{percorso}: errore negli script")
                self.assertGreater(len(self.pagina.inner_text("main")), 20)


if __name__ == "__main__":
    unittest.main()
