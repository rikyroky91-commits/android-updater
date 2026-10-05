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
                frammento = self.client.get(f"/ricerca/firmware?q={q}").text
                # Il nome ora precede la scheda, mentre il firmware viene dopo.
                # Confrontiamo i due contenuti senza imporne la contiguità.
                intestazione = re.search(r"<header data-nome-risultato>(.*?)</header>", frammento, re.S)
                pezzo = _testo(re.sub(r"<header data-nome-risultato>.*?</header>", "", frammento, flags=re.S))
                intera = _testo(self.client.get(f"/?q={q}&completo=1").text)
                if intestazione:
                    self.assertIn(_testo(intestazione.group(1)), intera)
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


# ======================================================================
# Il secondo tempo ridisegna TUTTO il risultato (05/10/2026)
# ======================================================================
_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _risultato_della_pagina(html: str) -> str:
    """Il contenitore del risultato, ritagliato da una pagina intera."""
    inizio = html.index('<div id="risultato-ricerca"')
    return html[inizio:html.index("</main>", inizio)].strip()


def _voce_samsung(codice: str, nome: str, build: str, android: int) -> dict:
    """Quello che il controllo versione Samsung restituisce per un codice,
    nella forma che `scan._lookup_structured_for` consegna alla ricerca."""
    from core import config as C, scan, sources

    grezza = sources.RawItem(
        title=f"{nome} ({codice}) — build {build} (EUX)",
        link=f"https://fota-cloud-dn.ospserver.net/firmware/EUX/{codice}/version.xml",
        brand=C.SAMSUNG, device=nome, model_code=codice, build=build,
        android_version=android,
        size_info=f"Controllo versione ufficiale (endpoint FOTA) · {codice}",
    )
    fonte = sources.Source(
        key="official_lookup",
        label=f"Controllo versione ufficiale (endpoint FOTA) · {codice} (ricerca diretta)",
        trust=C.TRUST_STRUCTURED, fetch=None, brand=C.SAMSUNG, homepage="",
        firmware_kind=C.FW_CURRENT,
    )
    return scan.normalize(grezza, fonte)


class _ConLeSchede(BaseDueTempi):
    """Le due fasi, con il catalogo delle schede tecniche caricato.

    Serve la scheda del Galaxy A32, che sta nella fixture registrata dal
    catalogo vero (`tests/fixtures/specs_devices.tar.gz`): la segnalazione
    riguarda proprio una scheda che c'è e che la pagina non mostra.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from core import specs

        with open(os.path.join(_FIXTURES, "specs_devices.tar.gz"), "rb") as f:
            specs.carica_da(specs.leggi_archivio(f.read()), "fixture di test")
        cls._ripiego_prima = specs.RIPIEGO_ESTERNO
        specs.RIPIEGO_ESTERNO = False

    @classmethod
    def tearDownClass(cls):
        from core import specs

        specs.RIPIEGO_ESTERNO = cls._ripiego_prima
        specs.reset_cache()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        from core import scan

        self._lookup_della_classe = scan._lookup_structured_for

    def tearDown(self):
        from core import scan

        scan._lookup_structured_for = self._lookup_della_classe

    def _il_secondo_tempo_trova(self, domanda: str, voce: dict) -> None:
        """La fonte firmware risponde a QUESTA domanda, e solo nel secondo
        tempo: il primo non la interroga per costruzione."""
        from core import scan

        conta = type(self).chiamate

        def lookup(query, *a, **kw):
            conta["lookup"] += 1
            if query.strip().lower() == domanda.lower():
                return [dict(voce)], None
            return [], None

        scan._lookup_structured_for = lookup


class TestIlSecondoTempoRidisegnaTutto(_ConLeSchede):
    """SEGNALATO DALL'UTENTE IL 05/10/2026 cercando «a505»: «non ho la
    scheda tecnica».

    La pagina mostrava il nome e il firmware del Galaxy A50 — arrivati con
    il secondo tempo — ma nessuna scheda, nessuna foto, nessun processore:
    quelli li disegna il primo tempo, che quel codice non l'aveva
    riconosciuto, e il secondo tempo sostituiva soltanto il riquadro del
    firmware. Ricaricando compariva tutto, perché il risultato completo
    era ormai in cache: la scheda c'era, era la pagina a non andarsela a
    prendere.

    Qui il caso è ricostruito senza dipendere da UN codice: una domanda
    che il primo tempo non sa leggere e a cui la fonte firmware risponde.
    È la forma generale del difetto — vale per un codice senza la lettera
    del mercato, per un nome scritto a modo proprio che traduce l'AI, per
    qualunque identità che arrivi solo dalla rete.
    """

    DOMANDA = "il galaxy della segnalazione"

    def setUp(self):
        super().setUp()
        self._il_secondo_tempo_trova(
            self.DOMANDA, _voce_samsung("SM-A325F", "Galaxy A32", "A325FXXSCDYB2", 13))

    def test_il_primo_tempo_da_solo_non_ha_la_scheda(self):
        """La premessa: senza rete questa domanda non porta a nessun
        telefono. Se un giorno il primo tempo imparasse a leggerla, questo
        test lo direbbe — e gli altri della classe starebbero misurando
        un caso che non esiste più."""
        pagina = self.client.get("/", params={"q": self.DOMANDA}).text
        self.assertIn("data-firmware-per", pagina)
        self.assertNotIn('<section class="scheda">', pagina)
        self.assertEqual(self.chiamate["lookup"], 0)

    def test_il_solo_riquadro_del_firmware_non_puo_portarla(self):
        """Perché non bastava: la risposta di prima conosce il telefono —
        nome, build — ma la scheda sta fuori da quel riquadro."""
        riquadro = self.client.get("/ricerca/firmware", params={"q": self.DOMANDA}).text
        self.assertIn("Galaxy A32", riquadro)
        self.assertIn("A325FXXSCDYB2", riquadro)
        self.assertNotIn('<section class="scheda">', riquadro)
        self.assertNotIn('id="risultato-ricerca"', riquadro)

    def test_con_il_secondo_tempo_arrivano_scheda_foto_e_processore(self):
        intero = self.client.get("/ricerca/firmware",
                                 params={"q": self.DOMANDA, "pagina": 1}).text
        self.assertIn('id="risultato-ricerca"', intero)
        self.assertIn("Galaxy A32", intero)
        self.assertIn("A325FXXSCDYB2", intero)
        self.assertIn('<section class="scheda">', intero)
        self.assertIn("Helio G80", intero)
        self.assertIn("Scheda tecnica completa", intero)
        self.assertRegex(intero, r'<img src="https://[^"]+" alt="Samsung Galaxy A32"')
        # Niente più attesa dentro quello che si mette in pagina: se ci
        # fosse, lo script ripartirebbe da capo.
        self.assertNotIn("data-firmware-per", intero)

    def test_resta_un_pezzo_di_pagina_non_una_pagina(self):
        intero = self.client.get("/ricerca/firmware",
                                 params={"q": self.DOMANDA, "pagina": 1}).text
        self.assertNotIn("<html", intero.lower())
        self.assertNotIn("<nav", intero.lower())
        self.assertNotIn('role="search"', intero,
                         "la barra di ricerca non va ridisegnata: chi sta già "
                         "scrivendo un'altra domanda la perderebbe")
        # ...e la premessa di quel controllo: nella pagina intera c'è.
        self.assertIn('role="search"',
                      self.client.get("/", params={"q": self.DOMANDA}).text)

    def test_e_la_stessa_cosa_che_disegna_la_pagina_intera(self):
        """IL TEST CHE TIENE INSIEME LE DUE STRADE. Non «contiene le stesse
        parole»: è lo stesso HTML, carattere per carattere, del risultato
        che il server disegna facendo tutto insieme. Qualunque cosa la
        pagina impari a mostrare domani, il secondo tempo la mostra —
        senza che qualcuno debba ricordarsi di aggiungerla in due posti."""
        imei = "861206074094914"
        for q in (self.DOMANDA, "SM-A546B", "a325", "CPH2781",
                  "codice-che-non-esiste", imei):
            with self.subTest(q=q):
                intera = self.client.get("/", params={"q": q, "completo": 1}).text
                pezzo = self.client.get("/ricerca/firmware",
                                        params={"q": q, "pagina": 1}).text
                self.assertEqual(pezzo.strip(), _risultato_della_pagina(intera))

    def test_il_titolo_della_scheda_del_browser_viaggia_con_il_risultato(self):
        intero = self.client.get("/ricerca/firmware",
                                 params={"q": self.DOMANDA, "pagina": 1}).text
        titolo = re.search(r'data-titolo-pagina="([^"]*)"', intero)
        self.assertIsNotNone(titolo)
        self.assertIn("Galaxy A32", titolo.group(1))

    def test_lo_striscione_dell_ai_non_si_perde(self):
        """`ai=` sta nell'indirizzo della pagina, non nella domanda: lo
        script lo rimanda, e il risultato ridisegnato deve dire ancora
        che cosa è stato cercato al posto di chi ha scritto."""
        intero = _testo(self.client.get(
            "/ricerca/firmware",
            params={"q": self.DOMANDA, "pagina": 1, "ai": "quel samsung nero",
                    "perche": "nero è un colore, non un modello",
                    "alt": ["Galaxy A33", "Galaxy A34"]}).text)
        self.assertIn("Hai scritto «quel samsung nero»", intero)
        self.assertIn("nero è un colore, non un modello", intero)
        self.assertIn("Oppure: Galaxy A33 , Galaxy A34", intero)

    def test_lo_script_e_la_pagina_parlano_dello_stesso_contenitore(self):
        """Tre file devono dire la stessa parola: il template che apre il
        contenitore, la rotta che lo rende quando riceve `pagina`, lo
        script che lo chiede e lo sostituisce. Se uno dei tre cambia nome
        lo script non trova più niente da sostituire e ripiega in
        silenzio sul solo riquadro — cioè il difetto torna senza che
        nessun altro test diventi rosso."""
        pagina = self.client.get("/", params={"q": self.DOMANDA}).text
        self.assertIn('<div id="risultato-ricerca"', pagina)
        radice = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(radice, "web", "static", "firmware-in-arrivo.js"),
                  encoding="utf-8") as f:
            script = f.read()
        self.assertIn('getElementById("risultato-ricerca")', script)
        self.assertIn('querySelector("#risultato-ricerca")', script)
        self.assertIn('parametri.set("pagina", "1")', script)


class TestCioCheScriveAspettaIlRisultatoCompleto(_ConLeSchede):
    """La parte che nessuno aveva segnalato, ed era la peggiore.

    Il tasto «Aggiungi al parco di test» sta fuori dal riquadro del
    firmware, quindi restava quello del PRIMO tempo — con i suoi valori:
    marca vuota (senza rete nessuna fonte l'ha dichiarata) e, per un
    modello non ancora in archivio, una chiave costruita sul testo
    digitato. Un telefono aggiunto da lì entrava nel parco sotto una
    chiave che l'archivio non avrebbe mai usato: nessun aggiornamento lo
    avrebbe mai fatto segnalare, che è l'unica cosa per cui il parco
    esiste.
    """

    DOMANDA = "il galaxy da mettere nel parco"

    def setUp(self):
        super().setUp()
        self._il_secondo_tempo_trova(
            self.DOMANDA, _voce_samsung("SM-A325F", "Galaxy A32", "A325FXXSCDYB2", 13))

    def test_la_pagina_provvisoria_non_offre_il_tasto_del_parco(self):
        pagina = self.client.get("/", params={"q": self.DOMANDA}).text
        self.assertIn("data-firmware-per", pagina)
        self.assertNotIn('action="/parco/aggiungi"', pagina)

    def test_ne_la_correzione_del_nome(self):
        """Salva su un CODICE, e quello del primo tempo può essere di un
        altro telefono."""
        pagina = self.client.get("/", params={"q": "SM-A546B"}).text
        self.assertIn("data-firmware-per", pagina)
        self.assertNotIn('action="/modello/correggi"', pagina)

    def test_il_tasto_arriva_con_i_valori_del_risultato_completo(self):
        from core import config as C
        from web.main import _esito_ricerca

        intero = self.client.get("/ricerca/firmware",
                                 params={"q": self.DOMANDA, "pagina": 1}).text
        completo = _esito_ricerca(self.DOMANDA)
        self.assertEqual(completo["brand"], C.SAMSUNG)
        self.assertTrue(completo["chiave_parco"].startswith("samsung|"),
                        completo["chiave_parco"])
        self.assertIn('action="/parco/aggiungi"', intero)
        self.assertIn(f'name="chiave" value="{completo["chiave_parco"]}"', intero)
        self.assertIn(f'name="brand" value="{C.SAMSUNG}"', intero)
        self.assertIn(f'name="modello" value="{completo["nome"]}"', intero)

    def test_senza_due_tempi_il_tasto_c_e_subito(self):
        """La pagina fatta tutta insieme non è provvisoria: lì niente
        aspetta niente."""
        pagina = self.client.get("/", params={"q": self.DOMANDA, "completo": 1}).text
        self.assertIn('action="/parco/aggiungi"', pagina)


class TestLeRicercheRecentiNelSecondoTempo(_ConLeSchede):
    """In due tempi una ricerca riuscita non entrava fra le «Recenti».

    La pagina registra solo ciò che è `trovato`, e il primo tempo non lo
    è mai: senza rete nessuna fonte risponde. Restava registrato solo chi
    ricaricava la pagina entro la durata della cache.
    """

    DOMANDA = "il galaxy delle recenti"
    BROWSER = {"user-agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/130.0"}

    def setUp(self):
        super().setUp()
        from core import storage

        self._il_secondo_tempo_trova(
            self.DOMANDA, _voce_samsung("SM-A325F", "Galaxy A32", "A325FXXSCDYB2", 13))
        with storage.transaction() as conn:
            conn.execute("DELETE FROM ricerche_recenti")

    def test_il_primo_tempo_non_puo_registrarla(self):
        from core import storage

        self.client.get("/", params={"q": self.DOMANDA}, headers=self.BROWSER)
        self.assertEqual(storage.ricerche_recenti(), [])

    def test_la_registra_il_secondo_tempo_con_il_nome_trovato(self):
        from core import storage

        self.client.get("/ricerca/firmware", params={"q": self.DOMANDA, "pagina": 1},
                        headers=self.BROWSER)
        self.assertEqual(storage.ricerche_recenti(), ["Samsung Galaxy A32"])

    def test_un_crawler_non_entra_nell_elenco(self):
        from core import storage

        self.client.get("/ricerca/firmware", params={"q": self.DOMANDA, "pagina": 1},
                        headers={"user-agent": "GPTBot/1.0"})
        self.assertEqual(storage.ricerche_recenti(), [])

    def test_una_ricerca_a_vuoto_nemmeno(self):
        from core import storage

        self.client.get("/ricerca/firmware",
                        params={"q": "codice-che-non-esiste", "pagina": 1},
                        headers=self.BROWSER)
        self.assertEqual(storage.ricerche_recenti(), [])


# ======================================================================
# Il codice scritto senza la lettera del mercato (05/10/2026)
# ======================================================================
class TestCodiceSenzaMercatoNelPrimoTempo(_ConLeSchede):
    """«a505» è il Galaxy A50, e per saperlo non serve la rete.

    È la forma esatta della segnalazione. Il secondo tempo ci arrivava
    provando `SM-A505F`, `SM-A505FN`… contro la fonte Samsung; il primo
    restava con «A505», un codice che nessun catalogo ha, e disegnava la
    pagina di un telefono sconosciuto. I test usano «a325» perché il
    Galaxy A32 è nelle fixture registrate — codici e scheda: la regola è
    la stessa per ogni radice Samsung.
    """

    def test_nome_scheda_e_processore_ci_sono_subito(self):
        for scritto in ("a325", "A325", "sm-a325", "samsung a325"):
            with self.subTest(scritto=scritto):
                pagina = self.client.get("/", params={"q": scritto}).text
                self.assertIn("data-firmware-per", pagina)
                self.assertIn("Samsung Galaxy A32", _testo(pagina))
                self.assertIn('<section class="scheda">', pagina)
                self.assertIn("Helio G80", pagina)
        self.assertEqual(self.chiamate["lookup"], 0,
                         "il primo tempo ha toccato una fonte firmware")
        self.assertEqual(self.chiamate["live"], 0)

    def test_il_codice_mostrato_e_quello_completo(self):
        from web.main import _cerca_davvero

        self.assertEqual(_cerca_davvero("a325", senza_rete=True)["codice"], "SM-A325F")


class TestCompletaCodice(unittest.TestCase):
    """`sources.completa_codice`: quale telefono c'è dietro una radice."""

    def tearDown(self):
        from core import modelcodes

        modelcodes.reset_cache()

    def test_la_radice_porta_al_codice_internazionale(self):
        from core import sources

        self.assertEqual(sources.completa_codice("a325"), "SM-A325F")
        self.assertEqual(sources.completa_codice("SM-A325"), "SM-A325F")
        self.assertEqual(sources.completa_codice("a546"), "SM-A546B")

    def test_prima_l_internazionale_poi_la_cina(self):
        """In ordine alfabetico `SM-S9210` (Cina) viene prima di
        `SM-S921B`: è il difetto già corretto per la ricerca per nome
        («samsung s24» rispondeva con la variante cinese), rimasto aperto
        sulla strada del codice incompleto."""
        from core import modelcodes, sources

        self.assertEqual(modelcodes.codici_per_prefisso("SM-S921")[0], "SM-S9210",
                         "la fixture non riproduce più la trappola: scegline un'altra")
        self.assertEqual(sources.completamenti_del_codice("SM-S921")[0], "SM-S921B")
        self.assertEqual(sources.completa_codice("s921"), "SM-S921B")
        # ...e nello stesso ordine arrivano alle fonti firmware: il primo
        # codice completo che il secondo tempo prova è l'internazionale.
        completi = [f for f in sources.expand_query("s921")
                    if f.startswith("SM-S921") and f != "SM-S921"]
        self.assertEqual(completi[0], "SM-S921B", completi)

    def test_un_codice_completo_o_un_nome_non_si_toccano(self):
        from core import sources

        for testo in ("SM-A325F", "RMX3939", "Galaxy A32", "samsung a32", ""):
            with self.subTest(testo=testo):
                self.assertIsNone(sources.completa_codice(testo))

    def test_il_5g_nel_nome_non_fa_due_telefoni(self):
        """Righe vere del dataset: sotto `SM-A546` la variante cinese è
        scritta come le altre, ma in molte famiglie una riga dice
        «Galaxy S21» e l'altra «Galaxy S21 5G»."""
        from core import modelcodes, sources

        modelcodes.carica_indice({
            "SM-G991B": ["Galaxy S21 5G"], "SM-G991N": ["Galaxy S21"],
            "SM-G9910": ["Galaxy S21 5G"],
        })
        self.assertEqual(sources.completa_codice("g991"), "SM-G991B")

    def test_una_radice_con_telefoni_diversi_non_si_indovina(self):
        """Righe vere del dataset (05/10/2026). `SM-A305` è il Galaxy A30
        in Europa e il Galaxy A40s in Cina; `SM-W201` è l'inizio di sei
        telefoni diversi. Sceglierne uno sarebbe inventare un modello:
        decide il secondo tempo, che ha le fonti."""
        from core import modelcodes, sources

        modelcodes.carica_indice({
            "SM-A305F": ["Galaxy A30"], "SM-A305FN": ["Galaxy A30"],
            "SM-A3050": ["Galaxy A40s"], "SM-A3058": ["Galaxy A40s"],
            "SM-W2014": ["三星 W2014"], "SM-W2015": ["三星 W2015"],
            "SM-W2016": ["三星 W2016"],
        })
        self.assertIsNone(sources.completa_codice("a305"))
        self.assertIsNone(sources.completa_codice("SM-W201"))
        # ...ma i completamenti restano tutti disponibili al secondo tempo,
        # con l'internazionale per primo.
        self.assertEqual(sources.completamenti_del_codice("SM-A305")[0], "SM-A305F")


if __name__ == "__main__":
    unittest.main()
