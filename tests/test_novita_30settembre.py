"""Le quattro richieste del 30/09/2026.

1. L'ultim'ora in fondo alla home, con il ring dei due lottatori.
2. Il confronto fra le fonti IMEI subito sotto i link ai siti di
   verifica, aperto e non chiuso in fondo alla pagina.
3. Il tema scuro, attivabile in qualunque momento.
4. Il codice modello SEMPRE accanto al nome commerciale nei risultati.

Come il resto della suite, questi test leggono cosa c'è scritto nella
pagina, non se la pagina ha risposto 200: una striscia vuota, un tasto
che non esiste o un codice sparito rispondono 200 lo stesso.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_sito import _Sito, _SitoConLogin  # noqa: E402

_RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _senza_details(html: str) -> str:
    return re.sub(r"<details\b.*?</details>", "", html, flags=re.S)


def _riga_codice(html: str) -> str:
    """Il paragrafo «Codice modello» sotto il nome del risultato."""
    trovato = re.search(r'<p class="codice-modello" data-codice-modello>(.*?)</p>', html, flags=re.S)
    return trovato.group(1) if trovato else ""


# ======================================================================
# 1. L'ultim'ora in home
# ======================================================================
class TestUltimoraInHome(_Sito):
    def test_la_home_ha_la_striscia_con_le_notizie(self):
        pagina = self.client.get("/").text
        self.assertIn("data-ultimora", pagina)
        self.assertIn("Ultim'ora", pagina)
        self.assertIn('class="ultimora-voce"', pagina)
        # Le notizie dell'archivio di prova sono di maggio/giugno: più
        # vecchie di quattordici giorni, eppure la striscia non è vuota.
        self.assertIn("Galaxy S24", pagina)
        self.assertIn("Galaxy A07", pagina)

    def test_la_striscia_porta_il_codice_modello(self):
        pagina = self.client.get("/").text
        striscia = pagina[pagina.index("data-ultimora"):]
        self.assertIn("<code>SM-S921B</code>", striscia)
        self.assertIn("<code>SM-A075F</code>", striscia)

    def test_la_seconda_copia_non_si_legge_due_volte(self):
        """Lo scorrimento senza stacchi scrive le voci due volte: la
        seconda deve restare fuori dai lettori di schermo e dal tasto Tab."""
        pagina = self.client.get("/").text
        tutte = pagina.count('class="ultimora-voce"')
        nascoste = pagina.count('class="ultimora-voce" aria-hidden="true"')
        self.assertGreater(tutte, 0)
        self.assertEqual(tutte, nascoste * 2)
        self.assertEqual(pagina.count('tabindex="-1"') >= nascoste, True)

    def test_il_ring_e_lo_script_ci_sono(self):
        pagina = self.client.get("/").text
        self.assertIn("data-ring", pagina)
        self.assertIn('/static/ring.js?v=', pagina)
        self.assertIn('class="con-ultimora"', pagina)
        self.assertEqual(self.client.get("/static/ring.js").status_code, 200)

    def test_la_striscia_sta_fuori_dal_main(self):
        """Dentro `<main>` (un contesto di impilamento suo) il piè di
        pagina le si disegnava sopra: visto su mobile il 30/09/2026."""
        pagina = self.client.get("/").text
        self.assertGreater(pagina.index("data-ultimora"), pagina.index("</main>"))

    def test_solo_la_home_ha_la_striscia(self):
        self.assertNotIn("data-ultimora", self.client.get("/novita").text)
        self.assertNotIn("data-ultimora", self.client.get("/", params={"q": "SM-A075F"}).text)

    def test_una_notizia_senza_telefono_non_entra(self):
        from core import storage
        from web import main

        vera = storage.get_updates
        storage.get_updates = lambda **k: [{
            "id": "vivaldi", "brand": "Altri", "device_model": "",
            "title": "Vivaldi 7.6 changelog", "firmware_kind": "reported",
            "published": "2026-09-29"}] * 8
        self.addCleanup(setattr, storage, "get_updates", vera)
        self.assertEqual(main._notizie_ticker(), [])
        self.assertIn("Nessuna novità in archivio", self.client.get("/").text)

    def test_un_archivio_rotto_non_fa_cadere_la_home(self):
        from core import storage

        vera = storage.get_updates

        def rotta(**k):
            raise RuntimeError("database illeggibile")
        storage.get_updates = rotta
        self.addCleanup(setattr, storage, "get_updates", vera)
        risposta = self.client.get("/")
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("Nessuna novità in archivio", risposta.text)


# ======================================================================
# 2. Il confronto fra le fonti IMEI, in alto e aperto
# ======================================================================
class TestConfrontoImeiInAlto(_Sito):
    IMEI = "867051060315467"

    def test_sta_subito_sotto_i_link_ai_siti(self):
        pagina = self.client.get("/", params={"q": self.IMEI}).text
        link = pagina.index("Controlla lo stesso IMEI su un'altra fonte")
        confronto = pagina.index("Confronto fra le fonti IMEI")
        firmware = pagina.index('class="titolo-firmware"')
        self.assertLess(link, confronto)
        self.assertLess(confronto, firmware, "il confronto è ancora in fondo alla pagina")

    def test_i_risultati_si_vedono_senza_aprire_niente(self):
        pagina = _senza_details(self.client.get("/", params={"q": self.IMEI}).text)
        self.assertIn("Confronto fra le fonti IMEI", pagina)
        tabella = pagina[pagina.index("Confronto fra le fonti IMEI"):]
        self.assertIn("<table", tabella)
        self.assertIn("Codice modello", tabella)

    def test_compare_una_volta_sola(self):
        pagina = self.client.get("/", params={"q": self.IMEI}).text
        self.assertEqual(pagina.count("Confronto fra le fonti IMEI"), 1)

    def test_un_tac_ignoto_dice_la_lacuna_in_chiaro(self):
        pagina = _senza_details(self.client.get("/", params={"q": "998877660000000"}).text)
        self.assertIn("Confronto fra le fonti IMEI", pagina)
        self.assertIn("Nessuna delle basi dati locali conosce il TAC", pagina)


# ======================================================================
# 3. Il tema scuro
# ======================================================================
class TestTemaScuro(_SitoConLogin):
    def test_il_tasto_c_e_in_ogni_pagina(self):
        for percorso in ("/", "/novita", "/dispositivi", "/catalogo", "/parco",
                         "/?q=SM-A075F"):
            with self.subTest(percorso=percorso):
                pagina = self.client.get(percorso).text
                self.assertIn("data-tema-tasto", pagina)
                self.assertIn('aria-pressed="false"', pagina)
                self.assertIn("/static/tema.js?v=", pagina)

    def test_il_tema_si_decide_prima_del_primo_disegno(self):
        """Se lo decidesse `tema.js` (defer) chi usa il tema scuro vedrebbe
        un lampo bianco a ogni pagina."""
        pagina = self.client.get("/").text
        testa = pagina[:pagina.index("</head>")]
        self.assertIn('setAttribute("data-tema"', testa)
        self.assertIn("prefers-color-scheme: dark", testa)
        self.assertIn("mut-tema", testa)
        self.assertLess(testa.index('setAttribute("data-tema"'), len(testa))

    def test_lo_stile_ha_i_gettoni_scuri(self):
        with open(os.path.join(_RADICE, "web", "static", "style.css"), encoding="utf-8") as f:
            stile = f.read()
        blocco = stile[stile.index(':root[data-tema="scuro"] {'):]
        blocco = blocco[:blocco.index("}")]
        for gettone in ("--ink", "--paper", "--carta", "--neutral", "--filo",
                        "--fondo-firmware", "--testo-nota", "--fondo-avviso"):
            with self.subTest(gettone=gettone):
                self.assertIn(gettone + ":", blocco)

    def test_nessun_testo_dei_tasti_usa_il_colore_della_carta(self):
        """Col tema scuro `--carta` è scura: il testo dei tasti verdi e
        indaco scritto con quel colore diventava scuro su scuro."""
        with open(os.path.join(_RADICE, "web", "static", "style.css"), encoding="utf-8") as f:
            stile = f.read()
        for selettore in ('.ricerca button[type="submit"] {', ".tasto-ai {",
                          '.confronto-form button[type="submit"] {',
                          '.correzione-form button[type="submit"] {',
                          '.modulo-account button[type="submit"] {'):
            with self.subTest(selettore=selettore):
                regola = stile[stile.index(selettore):]
                regola = regola[:regola.index("}")]
                self.assertNotIn("color: var(--carta)", regola)

    def test_nessun_colore_scritto_a_mano_dove_c_e_testo_o_fondo(self):
        """I tre valori che erano scritti a mano e restavano chiari nel
        tema scuro (riquadro firmware, note, avviso IMEI)."""
        with open(os.path.join(_RADICE, "web", "static", "style.css"), encoding="utf-8") as f:
            stile = f.read()
        for vecchio in ("background: #f3f7f5", "color: #514f4e", "background: #fff8e9"):
            self.assertNotIn(vecchio, stile)

    def test_lo_script_del_tasto_viene_servito(self):
        risposta = self.client.get("/static/tema.js")
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("mut-tema", risposta.text)
        # Il salvataggio può fallire (finestra privata): va protetto.
        self.assertIn("try { localStorage.setItem", risposta.text)


# ======================================================================
# 4. Il codice modello, sempre
# ======================================================================
class TestCodiceModelloSempre(_Sito):
    def test_cercando_un_codice_il_codice_resta_sotto_il_nome(self):
        riga = _riga_codice(self.client.get("/", params={"q": "SM-A075F"}).text)
        self.assertIn("SM-A075F", riga)
        self.assertNotIn("dal catalogo per questo nome", riga)

    def test_cercando_un_nome_arriva_anche_il_codice(self):
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "device_model": "Galaxy A07",
            "model_code": "SM-A075F", "brand": "Samsung", "build": "A075FXXS1AYG1",
            "android_version": "16", "firmware_kind": "current",
            "source_label": "Endpoint FOTA ufficiale"}], "error": None})
        self.addCleanup(setattr, type(self), "RISPOSTA_RICERCA",
                        staticmethod(lambda q: {"items": [], "error": None}))
        pagina = self.client.get("/", params={"q": "Galaxy A07"}).text
        self.assertIn("SM-A075F", _riga_codice(pagina))

    def test_cercando_un_imei_il_codice_del_tac_sta_sotto_il_nome(self):
        pagina = self.client.get("/", params={"q": "867051060315467"}).text
        riga = _riga_codice(pagina)
        self.assertIn('class="codice-principale"', riga)
        self.assertRegex(riga, r'codice-principale">[^<]*\d')

    def test_anche_il_secondo_tempo_porta_il_codice(self):
        frammento = self.client.get("/ricerca/firmware", params={"q": "SM-A075F"}).text
        self.assertIn("SM-A075F", _riga_codice(frammento))

    def test_le_novita_portano_il_codice(self):
        from web import presenters as P

        self.assertEqual(P.voce_feed({"model_code": "SM-S921B"})["codice"], "SM-S921B")
        with open(os.path.join(_RADICE, "web", "templates", "novita.html"), encoding="utf-8") as f:
            self.assertIn("v.codice", f.read())


class TestCodiceModelloSempreConLogin(_SitoConLogin):
    def test_l_elenco_dei_dispositivi_mostra_il_codice(self):
        pagina = self.client.get("/dispositivi").text
        self.assertIn("<code>SM-S921B</code>", pagina)
        self.assertIn("<code>SM-A075F</code>", pagina)


class TestSceltaDelCodice(unittest.TestCase):
    """La regola di `_codici_da_mostrare`, senza pagina intorno."""

    def setUp(self):
        from web import main

        self.main = main
        self._vera = main._codici_del_risultato
        self.addCleanup(setattr, main, "_codici_del_risultato", self._vera)
        from core import modelcodes

        self._per_nome = modelcodes.codes_for_name
        self.addCleanup(setattr, modelcodes, "codes_for_name", self._per_nome)

    def _con_catalogo(self, codici):
        from core import modelcodes

        self.main._codici_del_risultato = lambda query, nome: list(codici)
        modelcodes.codes_for_name = lambda nome: list(codici)

    def test_un_nome_non_passa_per_codice(self):
        """La scheda senza codice rimette il suo titolo nel campo: «Galaxy
        S24» ha una cifra, ma non è un codice modello."""
        self._con_catalogo([])
        esito = self.main._codici_da_mostrare({
            "query": "Galaxy S24", "nome": "Samsung Galaxy S24", "trovato": True,
            "codice": "", "scheda": {"trovata": True, "codice": "Galaxy S24"}})
        self.assertEqual(esito["codici_modello"], [])
        self.assertTrue(esito["mostra_codice"])

    def test_senza_codice_la_lacuna_si_dichiara(self):
        self._con_catalogo([])
        esito = self.main._codici_da_mostrare({
            "query": "Telefono X1", "nome": "Telefono X1", "trovato": True,
            "codice": "", "scheda": {}})
        self.assertTrue(esito["mostra_codice"])
        self.assertEqual(esito["codici_modello"], [])

    def test_i_nomi_in_codice_interni_non_sono_codici(self):
        self._con_catalogo(["SAPPHIRE", "23129RAA4G"])
        esito = self.main._codici_da_mostrare({
            "query": "Redmi Note 13", "nome": "Redmi Note 13", "trovato": True,
            "codice": "", "scheda": {}})
        self.assertEqual(esito["codici_modello"], ["23129RAA4G"])
        self.assertNotIn("SAPPHIRE", esito["altri_codici"])
        self.assertTrue(esito["codice_dal_nome"])

    def test_il_riconoscimento_da_catalogo_preferisce_la_variante_europea(self):
        """Il catalogo dava SM-S9210 (Cina) per «Galaxy S24»: la variante
        che si prova in Europa è SM-S921B."""
        self._con_catalogo(["SM-S9210", "SM-S921B", "SM-S921U"])
        esito = self.main._codici_da_mostrare({
            "query": "Galaxy S24", "nome": "Samsung Galaxy S24", "trovato": True,
            "codice": "SM-S9210", "fonte": "Riconoscimento del codice modello (ricerca diretta)",
            "scheda": {"trovata": True, "codice": "SM-S9210"}})
        self.assertEqual(esito["codici_modello"], ["SM-S921B"])
        self.assertIn("SM-S9210", esito["altri_codici"])

    def test_il_codice_scritto_vince_sul_catalogo(self):
        self._con_catalogo(["SM-S921B", "SM-S921U"])
        esito = self.main._codici_da_mostrare({
            "query": "SM-S921U", "nome": "Samsung Galaxy S24", "trovato": True,
            "codice": "SM-S921U", "fonte": "Riconoscimento del codice modello (ricerca diretta)",
            "scheda": {}})
        self.assertEqual(esito["codici_modello"], ["SM-S921U"])
        self.assertFalse(esito["codice_dal_nome"])

    def test_il_codice_del_tac_vale_per_un_imei(self):
        self._con_catalogo([])
        esito = self.main._codici_da_mostrare(
            {"query": "2209116AG", "nome": "Redmi Note 12 Pro", "trovato": False,
             "codice": "", "scheda": {}},
            {"riconosciuto": True, "codice": "", "voci": [{"codice": "2209116AG"}]})
        self.assertEqual(esito["codici_modello"], ["2209116AG"])

    def test_la_cache_non_viene_toccata(self):
        self._con_catalogo(["SM-S921B"])
        originale = {"query": "Galaxy S24", "nome": "Galaxy S24", "trovato": True,
                     "codice": "", "scheda": {}}
        self.main._codici_da_mostrare(originale)
        self.assertNotIn("codici_modello", originale)

    def test_4g_e_5g_non_sono_mercati(self):
        """«Redmi Note 13 5G» senza «5G» è un altro telefono."""
        togli = lambda n: self.main._RE_MERCATO_IN_CODA.sub("", n).strip()  # noqa: E731
        self.assertEqual(togli("Redmi Note 13 NFC EEA"), "Redmi Note 13")
        self.assertEqual(togli("Redmi Note 14 Pro (India)"), "Redmi Note 14 Pro")
        self.assertEqual(togli("Redmi Note 13 5G"), "Redmi Note 13 5G")
        self.assertEqual(togli("Galaxy A56 5G"), "Galaxy A56 5G")
        self.assertEqual(togli("Phone (3)"), "Phone (3)")

    def test_troppe_varianti_si_riassumono(self):
        self._con_catalogo([f"SM-X{n:03d}B" for n in range(20)])
        esito = self.main._codici_da_mostrare({
            "query": "Galaxy X", "nome": "Galaxy X", "trovato": True, "codice": "", "scheda": {}})
        self.assertEqual(len(esito["codici_modello"]), 1)
        self.assertEqual(len(esito["altri_codici"]), 8)
        self.assertEqual(esito["altri_codici_in_piu"], 11)


if __name__ == "__main__":
    unittest.main()


# ======================================================================
# Il codice modello anche fuori dalla pagina: API e controllo notturno
# ======================================================================
class TestCodiceNellApiENelControlloNotturno(_Sito):
    def test_l_api_restituisce_i_codici(self):
        dati = self.client.get("/api/cerca", params={"q": "SM-A075F"}).json()
        self.assertIn("codici_modello", dati)
        self.assertEqual(dati["codici_modello"][0], "SM-A075F")

    def test_apple_usa_l_identificativo(self):
        from core import appledevices
        from web import main

        vera_id, vera_cat = appledevices.identifiers_for, main._codici_del_risultato
        appledevices.identifiers_for = lambda nome: ["iPhone17,1"] if nome == "iPhone 16 Pro" else []
        main._codici_del_risultato = lambda q, n: []
        self.addCleanup(setattr, appledevices, "identifiers_for", vera_id)
        self.addCleanup(setattr, main, "_codici_del_risultato", vera_cat)
        esito = main._codici_da_mostrare({"query": "iPhone 16 Pro", "nome": "Apple iPhone 16 Pro",
                                          "trovato": True, "codice": "", "scheda": {}})
        self.assertEqual(esito["codici_modello"], ["iPhone17,1"])

    def _controllo(self, risposte):
        import importlib.util

        percorso = os.path.join(_RADICE, "scripts", "controllo_notturno.py")
        spec = importlib.util.spec_from_file_location("controllo_notturno_prova", percorso)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        modulo.CASI = [("Galaxy A07", "a07", True)]
        modulo.cerca = lambda base, q: risposte
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as uscita:
            codice = modulo.main()
        return codice, uscita.getvalue()

    def test_il_controllo_notturno_segnala_un_codice_sparito(self):
        codice, testo = self._controllo({"nome": "Samsung Galaxy A07", "firmware": True,
                                         "codici_modello": []})
        self.assertEqual(codice, 1)
        self.assertIn("nessun codice modello", testo)

    def test_il_controllo_notturno_passa_col_codice(self):
        codice, _ = self._controllo({"nome": "Samsung Galaxy A07", "firmware": True,
                                     "codici_modello": ["SM-A075F"]})
        self.assertEqual(codice, 0)

    def test_un_sito_non_ancora_aggiornato_non_fa_scattare_l_allarme(self):
        """Fra il merge e il deploy il sito risponde senza il campo: non è
        un codice sparito, è un campo che non c'è ancora."""
        codice, _ = self._controllo({"nome": "Samsung Galaxy A07", "firmware": True})
        self.assertEqual(codice, 0)


class TestFileStaticiFirmati(unittest.TestCase):
    """Dopo un deploy il browser non deve riusare il vecchio style.css."""

    def test_gli_stili_e_gli_script_hanno_la_firma(self):
        import re
        from fastapi.testclient import TestClient
        from web.main import app
        pagina = TestClient(app).get("/").text
        for nome in ("style.css", "tema.js", "ring.js"):
            self.assertRegex(pagina, r'/static/%s\?v=[0-9a-f]{10}' % re.escape(nome))

    def test_la_firma_cambia_col_contenuto(self):
        from web import contesto
        a = contesto.statico("style.css")
        self.assertRegex(a, r"^/static/style\.css\?v=[0-9a-f]{10}$")
        self.assertEqual(contesto.statico("non-esiste.css"), "/static/non-esiste.css")


class TestRecentiFaccinaStriscia(unittest.TestCase):
    """Tasto «Recenti», faccina stordita, striscia verde (01/10/2026)."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from web.main import app
        cls.client = TestClient(app)
        cls.home = cls.client.get("/").text
        cls.css = cls.client.get("/static/style.css").text
        cls.js = cls.client.get("/static/ricerche-recenti.js").text

    def test_il_tasto_recenti_sta_accanto_a_cerca_e_nasce_nascosto(self):
        i = self.home.index('class="tasto-recenti"')
        self.assertGreater(i, self.home.index(">Cerca</button>"))
        self.assertIn("hidden", self.home[i:i + 120])
        self.assertIn('aria-controls="pannello-recenti"', self.home)

    def test_lo_script_costruisce_il_pannello_globale(self):
        for pezzo in ("costruisciPannello", "pannello-recenti", "/api/ricerche-recenti", "Escape"):
            self.assertIn(pezzo, self.js)
        # Le recenti sono di TUTTI e le tiene il server: niente localStorage.
        self.assertNotIn("localStorage", self.js)

    def test_la_faccina_ha_la_versione_stordita(self):
        self.assertIn("faccia-stordita", self.home)
        self.assertIn("🥴", self.home)
        self.assertIn(".furbetto.stordito .faccia-stordita", self.css)

    def test_la_striscia_e_verde_e_non_rossa(self):
        blocco = self.css[self.css.index(".ultimora-barra {"):self.css.index(".ultimora-ora {")]
        self.assertIn("border-top: 3px solid var(--verde)", blocco)
        self.assertNotIn("var(--accent)", blocco)
        etichetta = self.css[self.css.index(".ultimora-etichetta {"):self.css.index(".ultimora-nastro {")]
        self.assertIn("background: var(--verde)", etichetta)
        self.assertIn("Barlow Condensed", self.css)
        self.assertIn("Barlow+Condensed", self.home)


class TestStrisciaSempreInMovimento(unittest.TestCase):
    """Con «Riduci movimento» attivo (iPhone) le notizie devono scorrere lo
    stesso, più piano, con un tasto per fermarle; il ring è opt-in."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from web.main import app
        cls.client = TestClient(app)
        cls.home = cls.client.get("/").text
        cls.css = cls.client.get("/static/style.css").text

    def test_i_due_tasti_ci_sono_e_nascono_nascosti(self):
        for marca in ("data-pausa", "data-gioca"):
            i = self.home.index(marca)
            self.assertIn("hidden", self.home[i:i + 40])

    def test_ridurre_i_movimenti_non_spegne_piu_lo_scorrimento(self):
        i = self.css.index("CHI HA RIDOTTO I MOVIMENTI")
        blocco = self.css[i:self.css.index("@media print", i)]
        self.assertNotIn("animation: none", blocco)
        self.assertIn("animation-duration: calc(var(--durata, 90s) * 1.6)", blocco)
        self.assertIn(".ultimora-barra.in-pausa .ultimora-scorre", blocco)

    def test_il_ring_si_accende_con_un_tasto_e_si_ricorda(self):
        js = self.client.get("/static/ring.js").text
        self.assertIn('"mut-ring"', js)
        self.assertIn("preferisceFermo", js)
        self.assertIn("function spegni", js)


class TestRicercheRecentiDiTutti(unittest.TestCase):
    """Le ricerche recenti le tiene il server e le vedono tutti (01/10/2026)."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from core import storage
        from web.main import app
        self.storage = storage
        self.client = TestClient(app)
        with storage.transaction() as conn:
            conn.execute("DELETE FROM ricerche_recenti")

    def test_si_registra_un_nome_e_lo_vede_un_altro_visitatore(self):
        self.assertTrue(self.storage.registra_ricerca_recente("Samsung Galaxy S24"))
        # Un «altro» visitatore: client nuovo, nessun cookie condiviso.
        from fastapi.testclient import TestClient
        from web.main import app
        altro = TestClient(app)
        voci = altro.get("/api/ricerche-recenti").json()["voci"]
        self.assertEqual(voci, ["Samsung Galaxy S24"])

    def test_gli_imei_e_i_numeri_lunghi_non_si_registrano(self):
        for testo in ("867051060315467", "IMEI 86705106", "x" * 70, ""):
            self.assertFalse(self.storage.registra_ricerca_recente(testo), testo)
        self.assertEqual(self.storage.ricerche_recenti(), [])

    def test_ordine_dal_piu_recente_e_senza_doppioni(self):
        for nome in ("Pixel 9", "Galaxy S24", "pixel 9"):
            self.storage.registra_ricerca_recente(nome)
        self.assertEqual(self.storage.ricerche_recenti(), ["pixel 9", "Galaxy S24"])

    def test_una_ricerca_riuscita_finisce_nell_elenco_di_tutti(self):
        from unittest import mock
        from web import main
        esito = dict(main._esito_vuoto("galaxy s24"), trovato=True, nome="Samsung Galaxy S24")
        with mock.patch.object(main, "_esito_ricerca", return_value=esito):
            self.client.get("/", params={"q": "galaxy s24"}, headers={"user-agent": "Mozilla/5.0 (iPhone)"})
        self.assertIn("Samsung Galaxy S24", self.storage.ricerche_recenti())

    def test_crawler_e_ricerche_non_riuscite_non_contano(self):
        from unittest import mock
        from web import main
        esito = dict(main._esito_vuoto("galaxy s24"), trovato=True, nome="Samsung Galaxy S24")
        with mock.patch.object(main, "_esito_ricerca", return_value=esito):
            self.client.get("/", params={"q": "galaxy s24"}, headers={"user-agent": "GPTBot/1.0"})
        self.assertEqual(self.storage.ricerche_recenti(), [])
        non_trovato = dict(main._esito_vuoto("xyz"), trovato=False, nome="xyz")
        with mock.patch.object(main, "_esito_ricerca", return_value=non_trovato):
            self.client.get("/", params={"q": "xyz"}, headers={"user-agent": "Mozilla/5.0"})
        self.assertEqual(self.storage.ricerche_recenti(), [])


class TestTendinaDelRing(unittest.TestCase):
    """01/10/2026: l'omino barrato spegne tutto, il guantone apre la tendina
    con scommesse, armi da mettere in campo e imprevisti."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from web.main import app
        cls.client = TestClient(app)
        cls.home = cls.client.get("/").text
        cls.css = cls.client.get("/static/style.css").text

    def test_il_guantone_apre_la_tendina_e_l_omino_barrato_spegne(self):
        i = self.home.index("data-opzioni")
        self.assertIn("hidden", self.home[i:i + 40])
        self.assertIn('aria-controls="ring-pannello"', self.home[i:i + 120])
        j = self.home.index("data-gioca")
        blocco = self.home[j:self.home.index("</button>", j)]
        self.assertIn("omino-taglio", blocco)
        self.assertNotIn("&#129354;", blocco)

    def test_la_tendina_nasce_nascosta_e_ha_tutte_le_sezioni(self):
        i = self.home.index("data-pannello")
        self.assertIn("hidden", self.home[i:i + 30])
        for marca in ('data-punta="robot"', 'data-punta="mela"', "data-gettoni", "data-esito",
                      'data-metti="pistola"', 'data-metti="spada"', 'data-metti="bomba"', 'data-metti="tablet"',
                      'data-metti="pc"', 'data-metti="orologio"', 'data-metti="duo"', "data-gravita",
                      'data-imprevisto="acquazzone"', 'data-imprevisto="natale"', 'data-imprevisto="uragano"',
                      "data-sorprese", "data-cruento", "data-ricomincia"):
            self.assertIn(marca, self.home)

    def test_la_tendina_riceve_i_clic_e_sale_dalla_striscia(self):
        blocco = self.css[self.css.index(".ring-pannello {"):self.css.index(".ring-pannello.aperto")]
        self.assertIn("pointer-events: auto", blocco)
        self.assertIn("bottom: calc(100% + 8px)", blocco)
        self.assertIn(".ultimora-gioca[aria-pressed=\"false\"] .omino-taglio { display: none; }", self.css)
