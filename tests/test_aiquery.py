"""Test dell'interprete AI della ricerca.

Il test che conta in questo file è `TestIlFiltro`: verifica che quello che
il modello propone venga **ricontrollato contro i nostri cataloghi** e
scartato se non c'è. È la differenza fra un aiuto alla ricerca e una fonte
di dati inventati, e non può dipendere da come è scritto il prompt — un
prompt si può disattendere, un `if` no.

Nessun test qui esce in rete: `_chiama` è sostituita, e c'è un test che
verifica che sia davvero l'unico punto che la tocca.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import aiquery  # noqa: E402
from core import specs  # noqa: E402
from core import suggest  # noqa: E402

_FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "specs_devices.tar.gz")
with open(_FIXTURE, "rb") as _f:
    SCHEDE = specs.leggi_archivio(_f.read())


def risposta_con(scelte, motivo="perché sì"):
    """Il TESTO che `_chiama` restituisce, qualunque sia il fornitore.

    Le differenze fra Gemini, Anthropic e OpenAI stanno tutte dentro
    `_chiama`: sopra di essa il modulo non sa con chi sta parlando, e i
    test non devono saperlo neanche loro.
    """
    import json

    return json.dumps({"scelte": scelte, "motivo": motivo})


class _Base(unittest.TestCase):
    def setUp(self):
        specs.carica_da(SCHEDE, "fixture")
        suggest.reset_cache()
        self._chiavi_prima = {v: os.environ.get(v)
                              for v, *_ in aiquery.FORNITORI}
        for variabile, *_ in aiquery.FORNITORI:
            os.environ.pop(variabile, None)
        os.environ["GEMINI_API_KEY"] = "chiave-finta-per-i-test"
        self._chiama_prima = aiquery._chiama

    def tearDown(self):
        aiquery._chiama = self._chiama_prima
        for variabile, valore in self._chiavi_prima.items():
            if valore is None:
                os.environ.pop(variabile, None)
            else:
                os.environ[variabile] = valore
        specs.reset_cache()
        suggest.reset_cache()


class TestSpegnimento(unittest.TestCase):
    """Senza chiave la funzione è spenta, non rotta."""

    def setUp(self):
        self._prima = {v: os.environ.pop(v, None) for v, *_ in aiquery.FORNITORI}

    def tearDown(self):
        for variabile, valore in self._prima.items():
            if valore is not None:
                os.environ[variabile] = valore

    def test_non_disponibile_senza_chiave(self):
        self.assertFalse(aiquery.disponibile())
        self.assertIsNone(aiquery.fornitore())
        self.assertIn("spenta", aiquery.status())

    def test_interpreta_dice_perche_invece_di_sollevare(self):
        esito = aiquery.interpreta("qualunque cosa")
        self.assertFalse(esito.riuscita)
        self.assertIn("chiave", esito.errore)


class TestIlFiltro(_Base):
    """Quello che il modello propone deve esistere nei nostri cataloghi."""

    def test_una_proposta_valida_passa(self):
        aiquery._chiama = lambda domanda: risposta_con(["SM-A075F"])
        esito = aiquery.interpreta("sm a075f", candidati=["SM-A075F", "SM-A076B"])
        self.assertEqual(esito.proposte, ("SM-A075F",))
        self.assertEqual(esito.scartate, ())

    def test_un_modello_inventato_viene_scartato(self):
        """IL TEST PIÙ IMPORTANTE DEL FILE.

        Il modello propone un codice che non esiste in nessun catalogo.
        Deve cadere, e deve essere contato: le proposte scartate sono il
        termometro del meccanismo.
        """
        aiquery._chiama = lambda domanda: risposta_con(
            ["SM-A075F", "SM-Z999X Galaxy Immaginario"])
        esito = aiquery.interpreta("a07", candidati=["SM-A075F", "SM-A076B"])
        self.assertEqual(esito.proposte, ("SM-A075F",))
        self.assertEqual(esito.scartate, ("SM-Z999X Galaxy Immaginario",))

    def test_tutte_inventate_significa_nessuna_proposta(self):
        aiquery._chiama = lambda domanda: risposta_con(["Nokia Lumia 4000"])
        esito = aiquery.interpreta("boh", candidati=["SM-A075F"])
        self.assertEqual(esito.proposte, ())
        self.assertFalse(esito.riuscita)
        self.assertIn("nessuna corrispondenza", esito.errore)

    def test_la_scrittura_diversa_non_e_un_invenzione(self):
        """Un modello che riscrive «SM-A075F» come «sm a075f» sta
        indicando la voce giusta: scartarla sarebbe assurdo. Il confronto
        ignora maiuscole, spazi e trattini — e nient'altro."""
        aiquery._chiama = lambda domanda: risposta_con(["sm a075f"])
        esito = aiquery.interpreta("a07", candidati=["SM-A075F"])
        self.assertEqual(esito.proposte, ("SM-A075F",))

    def test_elenco_vuoto_e_una_risposta_corretta(self):
        aiquery._chiama = lambda domanda: risposta_con([], motivo="non riconosco")
        esito = aiquery.interpreta("xyz", candidati=["SM-A075F"])
        self.assertEqual(esito.proposte, ())
        self.assertEqual(esito.scartate, ())

    def test_doppioni_contati_una_volta_sola(self):
        aiquery._chiama = lambda domanda: risposta_con(["SM-A075F", "SM-A075F"])
        esito = aiquery.interpreta("a07", candidati=["SM-A075F"])
        self.assertEqual(esito.proposte, ("SM-A075F",))


class TestRisposteMalformate(_Base):
    """Il modello «di solito» risponde JSON. «Di solito» non è un contratto."""

    def test_json_dentro_i_backtick(self):
        aiquery._chiama = lambda domanda: (
            '```json\n{"scelte": ["SM-A075F"], "motivo": "ok"}\n```')
        esito = aiquery.interpreta("a07", candidati=["SM-A075F"])
        self.assertEqual(esito.proposte, ("SM-A075F",))

    def test_json_con_una_frase_attorno(self):
        aiquery._chiama = lambda domanda: (
            'Ecco: {"scelte": ["SM-A075F"], "motivo": "ok"} spero vada')
        esito = aiquery.interpreta("a07", candidati=["SM-A075F"])
        self.assertEqual(esito.proposte, ("SM-A075F",))

    def test_risposta_illeggibile_non_solleva(self):
        aiquery._chiama = lambda domanda: "boh"
        esito = aiquery.interpreta("a07", candidati=["SM-A075F"])
        self.assertFalse(esito.riuscita)
        self.assertIn("non interpretabile", esito.errore)

    def test_chiamata_fallita_non_solleva(self):
        def esplodi(domanda):
            raise RuntimeError("HTTP 429")

        aiquery._chiama = esplodi
        esito = aiquery.interpreta("a07", candidati=["SM-A075F"])
        self.assertFalse(esito.riuscita)
        # NON lo stato nudo: il dettaglio sulla quota e sul progetto non
        # serve nella pagina di ricerca e trasforma un aiuto in un errore
        # tecnico. Chi cerca un telefono deve poter proseguire.
        self.assertIn("temporaneamente non disponibile", esito.errore)
        self.assertNotIn("quota", esito.errore.lower())

    def test_nessun_candidato_e_un_errore_diverso(self):
        """«Non gli è stato dato niente su cui lavorare» e «non ha
        trovato niente» sono due difetti diversi: confonderli manda a
        cercare il problema dove non è."""
        aiquery._chiama = lambda domanda: risposta_con(["qualcosa"])
        esito = aiquery.interpreta("a07", candidati=[])
        self.assertIn("nessun candidato", esito.errore)


class TestSceltaDelFornitore(_Base):
    """Si prende il primo per cui esiste una chiave, in ordine di elenco."""

    def test_gemini_ha_la_precedenza(self):
        """È l'unico con una quota gratuita permanente: se c'è, si usa
        quello, anche quando ci sono anche gli altri."""
        os.environ["ANTHROPIC_API_KEY"] = "anche-questa"
        os.environ["OPENAI_API_KEY"] = "e-questa"
        try:
            nome, _chiave, _modello = aiquery.fornitore()
            self.assertEqual(nome, "Gemini")
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)

    def test_si_scende_al_successivo_se_manca_il_primo(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ["OPENAI_API_KEY"] = "solo-questa"
        try:
            nome, _chiave, modello = aiquery.fornitore()
            self.assertEqual(nome, "OpenAI")
            self.assertIn("gpt", modello)
        finally:
            os.environ.pop("OPENAI_API_KEY", None)

    def test_lo_stato_dice_quale_fornitore(self):
        self.assertIn("Gemini", aiquery.status())


class TestModelliDiRiserva(_Base):
    """Un modello dismesso non risponde «non esiste»: risponde 429.

    IL CASO REALE. `gemini-2.0-flash` è stato spento il 1° giugno 2026.
    L'applicazione lo chiedeva ancora, e Google rispondeva «quota
    esaurita» — che manda a cercare un problema di limiti dove c'è un
    nome vecchio. Da qui l'elenco: si prova in ordine e ci si ferma al
    primo che risponde.
    """

    def test_si_scende_al_modello_successivo_su_429(self):
        tentati = []

        def finto(url, **kwargs):
            tentati.append(url)

            class Risposta:
                status_code = 429 if len(tentati) == 1 else 200

                @staticmethod
                def json():
                    if len(tentati) == 1:
                        return {"error": {"message": "quota"}}
                    return {"candidates": [{"content": {"parts": [
                        {"text": '{"scelte": ["SM-A075F"], "motivo": "ok"}'}]}}]}

            return Risposta()

        vero = aiquery.requests.post
        aiquery.requests.post = finto
        try:
            esito = aiquery.interpreta("a07", candidati=["SM-A075F"])
        finally:
            aiquery.requests.post = vero
        self.assertEqual(len(tentati), 2, "non ha provato il modello di riserva")
        self.assertEqual(esito.proposte, ("SM-A075F",))

    def test_un_errore_non_riprovabile_non_gira_tutta_la_lista(self):
        """Su una chiave sbagliata cambiare modello non aiuta, e provarli
        tutti nasconderebbe la causa vera dietro quattro tentativi."""
        tentati = []

        def finto(url, **kwargs):
            tentati.append(url)

            class Risposta:
                status_code = 500

                @staticmethod
                def json():
                    return {"error": {"message": "guasto interno"}}

            return Risposta()

        vero = aiquery.requests.post
        aiquery.requests.post = finto
        try:
            aiquery.interpreta("a07", candidati=["SM-A075F"])
        finally:
            aiquery.requests.post = vero
        self.assertEqual(len(tentati), 1)

    def test_il_modello_scelto_a_mano_scavalca_la_lista(self):
        os.environ["AI_QUERY_MODEL"] = "gemini-qualcosa-di-preciso"
        try:
            self.assertEqual(aiquery.modelli_da_provare(),
                             ["gemini-qualcosa-di-preciso"])
        finally:
            os.environ.pop("AI_QUERY_MODEL", None)

    def test_nessun_modello_dismesso_nella_lista(self):
        """I nomi spenti vanno tolti, non lasciati in coda.

        `gemini-2.0-flash` era quello che l'applicazione chiedeva in
        produzione il 2026-08-10, e la risposta era **429 quota
        esaurita** — non «modello inesistente». Un nome morto in fondo
        alla lista non fa danno perché cade e si passa oltre, ma costa
        una richiesta e rimette in circolo proprio quell'errore.
        """
        for spento in ("gemini-2.0-flash", "gemini-2.0-flash-lite",
                       "gemini-2.5-flash", "gemini-2.5-flash-lite",
                       "gemini-1.5-flash", "gemini-1.5-pro"):
            with self.subTest(modello=spento):
                self.assertNotIn(spento, aiquery.MODELLI_GEMINI)

    def test_i_piccoli_vengono_provati_per_primi(self):
        """Il vincolo è la quota gratuita, non la bravura: su un compito
        che è scegliere fra venti righe, un «lite» dà la stessa risposta
        consumando una frazione della quota."""
        primo = aiquery.MODELLI_GEMINI[0]
        self.assertIn("lite", primo,
                      f"il primo modello provato è «{primo}»: su quota "
                      "gratuita conviene partire dal più piccolo")


class TestCandidati(_Base):
    """Se il candidato giusto non è nell'elenco, il modello non può trovarlo."""

    def test_il_codice_storpiato_finisce_fra_i_candidati(self):
        candidati = aiquery.candidati_per("SMA075F")
        self.assertIn("SM-A075F", candidati)

    def test_la_frase_intera_arriva_al_nome(self):
        """Non è l'inizio di nessun nome e non somiglia a nessuno: ci si
        arriva solo guardando quali nomi contengono le parole scritte."""
        candidati = aiquery.candidati_per("quel samsung galaxy a56 preso l'anno scorso")
        self.assertTrue(any("A56" in c for c in candidati), candidati)

    def test_elenco_limitato(self):
        self.assertLessEqual(len(aiquery.candidati_per("galaxy", limite=10)), 10)


class TestNienteRete(_Base):
    def test_la_rete_passa_solo_da_chiama(self):
        """Se un giorno qualcuno aggiunge una seconda chiamata HTTP in
        questo modulo, questo test se ne accorge."""
        chiamate = []

        def registra(domanda):
            chiamate.append(domanda)
            return risposta_con(["SM-A075F"])

        aiquery._chiama = registra
        aiquery.interpreta("a07", candidati=["SM-A075F"])
        self.assertEqual(len(chiamate), 1)
        # E la richiesta deve contenere i candidati: è ciò che vincola la
        # scelta del modello a quello che conosciamo.
        self.assertIn("SM-A075F", chiamate[0])


class TestVerificaConFontiUfficiali(_Base):
    def setUp(self):
        super().setUp()
        self._verifica_prima = aiquery._chiama_verifica_gemini

    def tearDown(self):
        aiquery._chiama_verifica_gemini = self._verifica_prima
        super().tearDown()

    def test_tiene_solo_fonti_del_produttore(self):
        import json

        aiquery._chiama_verifica_gemini = lambda *_args: json.dumps({
            "sintesi": "Controlla la pagina Samsung.",
            "fonti": [
                {"titolo": "Supporto Samsung", "url": "https://www.samsung.com/it/support/"},
                {"titolo": "Blog esterno", "url": "https://example.org/firmware"},
            ],
        })
        esito = aiquery.verifica("Galaxy A05s")
        self.assertEqual(esito.fonti, (("Supporto Samsung", "https://www.samsung.com/it/support/"),))

    def test_non_si_finge_un_firmware_se_non_torna_una_fonte(self):
        import json

        aiquery._chiama_verifica_gemini = lambda *_args: json.dumps({
            "sintesi": "Nessuna pagina ufficiale trovata.",
            "fonti": [{"titolo": "Blog", "url": "https://example.org/"}],
        })
        esito = aiquery.verifica("modello ignoto")
        self.assertFalse(esito.fonti)
        self.assertIn("ufficiale", esito.errore)


class TestSuggerimentiEstesi(unittest.TestCase):
    """Il livello gratuito: correzione dei refusi anche sui CODICI."""

    def setUp(self):
        specs.carica_da(SCHEDE, "fixture")
        suggest.reset_cache()

    def tearDown(self):
        specs.reset_cache()
        suggest.reset_cache()

    def test_i_nomi_del_catalogo_specifiche_entrano_nei_suggerimenti(self):
        self.assertIn("Samsung Galaxy A07 4G", suggest.catalog())

    def test_il_codice_senza_trattino_viene_corretto(self):
        """`SMA075F` è la forma in cui un codice si copia male, ed era
        quella che non trovava niente."""
        self.assertEqual(suggest.codici_simili("SMA075F"), ["SM-A075F"])

    def test_il_codice_con_una_lettera_sbagliata(self):
        self.assertIn("SM-A075F", suggest.codici_simili("SM-A075G"))

    def test_did_you_mean_usa_i_codici_quando_sembra_un_codice(self):
        self.assertIn("SM-A075F", suggest.did_you_mean("SMA075F"))

    def test_un_nome_commerciale_non_viene_trattato_da_codice(self):
        self.assertFalse(suggest.sembra_un_codice("Samsung Galaxy A07 4G"))
        self.assertTrue(suggest.sembra_un_codice("SM-A075F"))

    def test_i_codici_restano_fuori_dai_completamenti(self):
        """Come completamento un codice non aiuta a scrivere un nome: il
        catalogo dei nomi e quello dei codici restano due cose."""
        self.assertNotIn("SM-A075F", suggest.catalog())


if __name__ == "__main__":
    unittest.main()


class TestICandidatiContengonoLaRispostaGiusta(_Base):
    """IL LIMITE VERO DEL MECCANISMO, ed era stato lasciato aperto.

    «Se il candidato corretto non è nell'elenco, il modello non può
    trovarlo» sta scritto in cima a `core/aiquery.py` da sempre. E
    l'elenco per «samsung s23» era: `SAMSUNG-SM-T537A`,
    `Samsung 心系天下 三星 W23`, `Samsung Gem`… senza «Galaxy S23».

    Il modello faceva il suo mestiere e sceglieva il meno peggio —
    «Samsung Galaxy S23+» — ed è esattamente la segnalazione ricevuta:
    «ho cercato samsung s23 ma mi ha detto forse cercavi s23 plus o
    ultra». Non era il modello a sbagliare, era il paniere.
    """

    def test_il_modello_liscio_e_fra_i_candidati(self):
        for query, atteso in (("samsung s23", "Galaxy S23"),
                              ("samsung s24", "Galaxy S24"),
                              ("samsung a55", "Galaxy A55")):
            with self.subTest(query=query):
                candidati = aiquery.candidati_per(query)
                self.assertTrue(
                    any(c.lower().startswith(atteso.lower()) for c in candidati),
                    f"«{atteso}» non è fra i candidati di «{query}»: {candidati[:6]}")

    def test_le_forme_della_ricerca_normale_vengono_per_prime(self):
        """Sono i candidati migliori che il progetto sappia produrre: se
        finissero in fondo, il taglio a quaranta li butterebbe via.

        Tutte tranne la prima, che è la domanda tale e quale: vedi il
        test qui sotto.
        """
        from core import sources

        candidati = aiquery.candidati_per("samsung s24")
        forme = [f for f in sources.expand_query("samsung s24")
                 if f.lower() != "samsung s24"]
        self.assertEqual(candidati[:len(forme)], forme)

    def test_quello_che_e_stato_scritto_non_e_una_proposta(self):
        """Il modello rispondeva «samsung s23» a chi aveva scritto
        «samsung s23»: una proposta che non propone niente, e una riga
        che dice «hai scritto X, ho cercato X». Se la forma scritta
        bastava, bastava anche premere Invio."""
        for query in ("samsung s23", "Galaxy S24"):
            with self.subTest(query=query):
                self.assertNotIn(query.lower(),
                                 [c.lower() for c in aiquery.candidati_per(query)])

    def test_ma_un_codice_copiato_male_resta_coperto(self):
        """IL CONFRONTO È SUL TESTO, NON SULLA CHIAVE NORMALIZZATA.

        Con la chiave — che toglie trattini e maiuscole — «SMA075F» e
        «SM-A075F» sono la stessa cosa, e il candidato giusto spariva:
        l'elenco restava VUOTO proprio per il caso in cui questo tasto
        serve di più.
        """
        candidati = aiquery.candidati_per("SMA075F")
        self.assertIn("SM-A075F", candidati)

    def test_un_codice_storpiato_resta_coperto(self):
        """La strada vecchia non deve essere stata scavalcata."""
        self.assertIn("SM-A075F", aiquery.candidati_per("SMA075F"))


class TestPrimaIlPiuFedele(unittest.TestCase):
    """Chi scrive «S23» vuole l'S23, non l'S23+.

    IL PROMPT NON BASTAVA. La regola gli è scritta, ma per «samsung s23»
    il modello continuava a mettere davanti «Galaxy S23+» — e la prima
    proposta è quella che la pagina cerca davvero, quindi si finiva sul
    telefono sbagliato. È la distinzione di tutto il progetto:
    un'istruzione si può disattendere, un riordino no.
    """

    def test_il_modello_liscio_passa_davanti_alle_varianti(self):
        casi = [
            ("samsung s23", ["Galaxy S23+", "Galaxy S23", "Galaxy S23 Ultra"], "Galaxy S23"),
            ("samsung s24", ["Galaxy S24 Ultra", "Galaxy S24", "Galaxy S24 FE"], "Galaxy S24"),
            ("redmi note 13", ["Redmi Note 13 Pro+", "Redmi Note 13"], "Redmi Note 13"),
            ("pixel 9", ["Pixel 9 Pro", "Pixel 9", "Pixel 9a"], "Pixel 9"),
        ]
        for query, proposte, atteso in casi:
            with self.subTest(query=query):
                self.assertEqual(
                    aiquery._prima_il_piu_fedele(query, proposte)[0], atteso)

    def test_chi_chiede_la_variante_riceve_la_variante(self):
        """La regola non deve tirare tutto verso il modello base: chi
        scrive «ultra» l'ultra lo vuole davvero."""
        proposte = aiquery._prima_il_piu_fedele(
            "galaxy s23 ultra", ["Galaxy S23", "Galaxy S23 Ultra"])
        self.assertEqual(proposte[0], "Galaxy S23 Ultra")

    def test_se_nessuna_corrisponde_non_si_tocca_l_ordine(self):
        """«quel samsung nero» e un codice copiato male: lì il confronto
        per parole non dice niente, e riordinare vorrebbe dire scavalcare
        il giudizio del modello proprio dove sta facendo il suo lavoro."""
        for query, proposte in (("quel samsung nero", ["Galaxy A56 5G", "Galaxy A55"]),
                                ("SMA075F", ["SM-A075M", "SM-A075F"])):
            with self.subTest(query=query):
                self.assertEqual(aiquery._prima_il_piu_fedele(query, proposte),
                                 proposte)

    def test_le_parole_di_marca_non_contano(self):
        """Chi scrive «samsung s23» la marca la scrive proprio perché il
        catalogo non la usa: «Galaxy S23» deve risultare fedele."""
        self.assertEqual(
            aiquery._prima_il_piu_fedele("samsung galaxy s23",
                                         ["Galaxy S23 Ultra", "Galaxy S23"])[0],
            "Galaxy S23")

    def test_una_proposta_sola_resta_com_e(self):
        self.assertEqual(aiquery._prima_il_piu_fedele("s23", ["Galaxy S23+"]),
                         ["Galaxy S23+"])
