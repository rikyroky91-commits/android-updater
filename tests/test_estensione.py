"""L'estensione del browser (`estensione/`) usa gli stessi file del sito.

Quello che si difende:
  - il pacchetto è aggiornato: chi cambia `ring.js`, la tendina o il suo stile
    e dimentica `python3 estensione/costruisci.py` lo scopre qui;
  - il manifest chiede il permesso minimo (la scheda su cui si clicca), non
    l'accesso a tutti i siti;
  - niente codice caricato da fuori: tutto sta nel pacchetto.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
ESTENSIONE = RADICE / "estensione"
# Due varianti: `pacchetto` si carica a mano e ha l'interruttore «Premium di
# prova»; `store` è quella da pubblicare, e l'interruttore ce l'ha solo finché
# `premium.json` dice `sblocco_gratis: true` (05/10/2026: si esce così, in
# attesa dei pareri di chi la usa).
VARIANTI = {nome: ESTENSIONE / nome for nome in ("pacchetto", "store")}
LINGUE = ("en", "it", "es", "fr", "de")


class TestEstensione(unittest.TestCase):

    def test_le_due_varianti_sono_aggiornate_con_i_file_del_sito(self):
        esito = subprocess.run([sys.executable, str(ESTENSIONE / "costruisci.py"), "--verifica"],
                               capture_output=True, text=True)
        self.assertEqual(esito.returncode, 0, esito.stdout + esito.stderr)

    def test_manifest_v3_col_permesso_minimo(self):
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                m = json.loads((cartella / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(m["manifest_version"], 3)
                self.assertEqual(sorted(m["permissions"]), ["activeTab", "scripting", "storage"])
                self.assertNotIn("host_permissions", m)
                self.assertNotIn("content_scripts", m)       # parte solo al clic sull'icona
                # L'accesso a tutti i siti è solo FACOLTATIVO: lo chiede la pagina delle opzioni a chi vuole il tasto ovunque.
                self.assertEqual(m["optional_host_permissions"], ["<all_urls>"])
                self.assertTrue((cartella / m["options_ui"]["page"]).exists())
                for lato in ("16", "48", "128"):
                    self.assertTrue((cartella / m["icons"][lato]).exists())
                self.assertTrue((cartella / m["background"]["service_worker"]).exists())

    def test_nome_e_descrizione_in_cinque_lingue_dentro_i_limiti_dello_store(self):
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                m = json.loads((cartella / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(m["default_locale"], "en")
                self.assertEqual(m["name"], "__MSG_nome__")
                for lingua in LINGUE:
                    messaggi = json.loads((cartella / "_locales" / lingua / "messages.json").read_text(encoding="utf-8"))
                    self.assertEqual({k for k in messaggi if not k.startswith("guida")},
                                     {"nome", "descrizione", "titolo", "opzioniTitolo", "sempreEtichetta", "sempreSpiega", "sempreNegato"})
                    self.assertLessEqual(len(messaggi["nome"]["message"]), 45)          # limite del Chrome Web Store
                    self.assertLessEqual(len(messaggi["descrizione"]["message"]), 132)  # idem

    def test_ring_e_dizionario_sono_gli_stessi_file_del_sito(self):
        for nome, cartella in VARIANTI.items():
            for file in ("ring.js", "lingue.js"):
                with self.subTest(variante=nome, file=file):
                    self.assertEqual((cartella / file).read_text(encoding="utf-8"),
                                     (RADICE / "web" / "static" / file).read_text(encoding="utf-8"))

    def test_niente_codice_da_fuori_e_niente_rete(self):
        for nome, cartella in VARIANTI.items():
            for file in ("prepara.js", "sfondo.js", "ring.js", "lingue.js", "tasto.js", "opzioni.js"):
                testo = (cartella / file).read_text(encoding="utf-8")
                for vietato in ("fetch(", "XMLHttpRequest", "eval(", "new Function", "importScripts(", "<script"):
                    self.assertNotIn(vietato, testo, f"{nome}/{file}: {vietato}")

    def test_la_tendina_sta_in_uno_shadow_dom_con_lo_stile_costruito(self):
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                testo = (cartella / "prepara.js").read_text(encoding="utf-8")
                self.assertIn("attachShadow", testo)
                self.assertIn("adoptedStyleSheets", testo)
                self.assertIn("data-pannello", testo)
                self.assertIn("__ringDeposito", testo)
                self.assertIn("chrome.storage.local", testo)

    def test_la_lingua_e_quella_del_browser_e_la_pagina_non_viene_tradotta(self):
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                prepara = (cartella / "prepara.js").read_text(encoding="utf-8")
                sfondo = (cartella / "sfondo.js").read_text(encoding="utf-8")
                self.assertIn("chrome.i18n.getUILanguage()", prepara)
                self.assertIn("__lingue.copri(radice", prepara)
                self.assertIn("__lingueSoloDizionario = true", sfondo)      # il dizionario non tocca la pagina
                self.assertLess(sfondo.index('"lingue.js"'), sfondo.index('"prepara.js"'))
                self.assertLess(sfondo.index('"prepara.js"'), sfondo.index('"ring.js"'))

    def test_il_tasto_di_accensione_resta_in_vista_e_quello_su_tutti_i_siti_e_una_scelta(self):
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                prepara = (cartella / "prepara.js").read_text(encoding="utf-8")
                # Spento resta solo il tasto: il resto sparisce con `data-spento` sull'ospite.
                self.assertIn(":host([data-spento]) .tela", prepara)
                self.assertIn('ospite.setAttribute("data-spento"', prepara)
                self.assertNotIn('ospite.style.display = "none"', prepara)
                # Il tasto su ogni pagina si registra solo dalle opzioni, dopo la richiesta del permesso.
                opzioni = (cartella / "opzioni.js").read_text(encoding="utf-8")
                self.assertLess(opzioni.index("chrome.permissions.request(TUTTI)"), opzioni.index("registerContentScripts"))
                self.assertIn("chrome.permissions.remove(TUTTI)", opzioni)
                sfondo = (cartella / "sfondo.js").read_text(encoding="utf-8")
                self.assertNotIn("scripting.registerContentScripts", sfondo) # mai da solo
                self.assertIn('messaggio.tipo === "avvia" && mittente.tab', sfondo)
                tasto = (cartella / "tasto.js").read_text(encoding="utf-8")
                self.assertIn('chrome.runtime.sendMessage({ tipo: "avvia" })', tasto)
                self.assertIn("window.top !== window", tasto)                # non nei riquadri dentro le pagine
                self.assertNotIn("<script", (cartella / "opzioni.html").read_text(encoding="utf-8").replace('<script src="opzioni.js"></script>', ""))

    def test_gli_effetti_cruenti_partono_spenti(self):
        # Lo store non ammette violenza gratuita: schizzi e arti staccati li accende chi li vuole.
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                testo = (cartella / "prepara.js").read_text(encoding="utf-8")
                self.assertIn('memoria["mut-ring-cruento"] = "off"', testo)

    def test_premium_e_predisposto_e_nello_store_si_sblocca_gratis_solo_se_lo_dice_premium_json(self):
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                testo = (cartella / "prepara.js").read_text(encoding="utf-8")
                self.assertIn("window.__ringPremium", testo)
                self.assertIn("bloccate: { guerrieri: true, armi: true, meteo: true }", testo)
                self.assertIn("data-premio-compra", testo)
        scelte = json.loads((ESTENSIONE / "premium.json").read_text(encoding="utf-8"))
        gratis = bool(scelte.get("premium_attivo", True)) and bool(scelte.get("sblocco_gratis", False))
        prova = (VARIANTI["pacchetto"] / "prepara.js").read_text(encoding="utf-8")
        store = (VARIANTI["store"] / "prepara.js").read_text(encoding="utf-8")
        # Nella variante di prova l'interruttore c'è sempre.
        self.assertIn("data-premio-prova aria-pressed", prova)
        # In quella da pubblicare c'è solo quando Premium si regala: allora è lo stesso della prova.
        self.assertEqual("data-premio-prova aria-pressed" in store, gratis)
        self.assertIn('"premiumDiProva": ' + ("true" if gratis else "false"), store)
        if gratis:
            self.assertIn("Sblocca Premium gratis", store)
            self.assertNotIn("solo in questa versione", store)

    def test_lo_sblocco_gratis_e_una_scelta_che_si_spegne_da_premium_json(self):
        """Le tre uscite possibili della variante da pubblicare, provate sul costruttore."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("costruisci_estensione", ESTENSIONE / "costruisci.py")
        costruisci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(costruisci)
        casi = {
            "gratis": ({"premium": True, "urlAcquisto": "", "sbloccoGratis": True}, True, True),
            "chiuso": ({"premium": True, "urlAcquisto": "https://esempio.invalid/premium", "sbloccoGratis": False}, True, False),
            "tutto libero": ({"premium": False, "urlAcquisto": "", "sbloccoGratis": False}, False, False),
        }
        for nome, (scelte, riquadro, interruttore) in casi.items():
            with self.subTest(caso=nome):
                costruisci.premium = lambda scelte=scelte: dict(scelte)
                store = costruisci.file_attesi("store")["prepara.js"]
                self.assertEqual("data-premio-compra>Sblocca Premium" in store, riquadro)
                self.assertEqual("data-premio-prova aria-pressed" in store, interruttore)
                self.assertEqual('"premium": true' in store, riquadro)
                # la variante di prova ha sempre l'interruttore, finché Premium esiste
                self.assertEqual("data-premio-prova aria-pressed" in costruisci.file_attesi("pacchetto")["prepara.js"], riquadro)

    def test_il_controller_ha_il_suo_tasto_e_i_tasti_gli_fanno_posto(self):
        """05/10/2026: il controller ad angolo si apre dal suo tasto, accanto a quello delle opzioni."""
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                prepara = (cartella / "prepara.js").read_text(encoding="utf-8")
                self.assertIn("data-radiale hidden", prepara)
                self.assertLess(prepara.index("data-radiale hidden"), prepara.index("data-opzioni hidden"))
                self.assertIn(".barretta.con-controller", prepara)
                self.assertIn(".ring-pannello.con-controller", prepara)
                self.assertIn(":host([data-spento]) [data-radiale]", prepara)      # spento resta solo il tasto di accensione
                self.assertIn("html.ring-punta", (cartella / "sfondo.js").read_text(encoding="utf-8"))
        ring = (RADICE / "web" / "static" / "ring.js").read_text(encoding="utf-8")
        self.assertIn('mio.querySelector("[data-radiale]")', ring)
        self.assertIn('data-radiale', (RADICE / "web" / "templates" / "home.html").read_text(encoding="utf-8"))

    def test_buco_nero_e_colpo_finale_hanno_il_loro_tasto_e_stanno_nella_guida(self):
        """05/10/2026: buco nero (Premium, col meteo) e colpo finale (gratis) arrivano anche nel plug-in."""
        import re
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                prepara = (cartella / "prepara.js").read_text(encoding="utf-8")
                for tasto in ("buco", "fatale", "zombie"):
                    self.assertIn(f'data-colpo=\\"{tasto}\\"', prepara)
                guida = (cartella / "benvenuto.html").read_text(encoding="utf-8")
                self.assertIn('data-msg="guidaS9"', guida)
                for lingua in LINGUE:
                    messaggi = json.loads((cartella / "_locales" / lingua / "messages.json").read_text(encoding="utf-8"))
                    self.assertTrue(messaggi["guidaS9"]["message"])
        ring = (RADICE / "web" / "static" / "ring.js").read_text(encoding="utf-8")
        premio = re.search(r"const EVENTI_PREMIO = \{([^}]*)\}", ring).group(1)
        self.assertIn("buco", premio)                                  # il buco nero sta col meteo a pagamento
        self.assertNotIn("fatale", premio)                             # il colpo finale è di tutti

    def test_trasformazioni_armi_nuove_e_colpi_finali_stanno_nel_plug_in(self):
        """05/10/2026: forme nuove (col tasto gratis «Trasforma i due»), bazooka e lanciafiamme (armi, a pagamento)."""
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                prepara = (cartella / "prepara.js").read_text(encoding="utf-8")
                for tasto in ("muta", "fatale"):
                    self.assertIn(f'data-colpo=\\"{tasto}\\"', prepara)
                for arma in ("bazooka", "lanciafiamme"):
                    self.assertIn(f'data-metti=\\"{arma}\\"', prepara)
                guida = (cartella / "benvenuto.html").read_text(encoding="utf-8")
                self.assertIn('data-msg="guidaS10"', guida)
                for lingua in LINGUE:
                    messaggi = json.loads((cartella / "_locales" / lingua / "messages.json").read_text(encoding="utf-8"))
                    self.assertTrue(messaggi["guidaS10"]["message"])
        ring = (RADICE / "web" / "static" / "ring.js").read_text(encoding="utf-8")
        armi = re.search(r"const ARMI_PREMIO = \{([^}]*)\}", ring).group(1)
        for arma in ("bazooka", "lanciafiamme"):
            self.assertIn(arma, armi)                                  # le armi nuove restano a pagamento
        mosse = re.search(r"const MOSSE_PREMIO = \{(.*?)\};", ring, re.S).group(1)
        self.assertNotIn("muta:", mosse)                               # cambiare forma nel ring libero è gratis

    def test_niente_telefoni_nell_estensione_ma_fumogeni_e_barattoli(self):
        """02/10/2026: nel plug-in non piovono telefoni. Via i tasti che li mettono in campo;
        restano le armi (Premium) e arrivano fumogeni e barattoli. Sul sito i telefoni restano."""
        import re
        for nome, cartella in VARIANTI.items():
            with self.subTest(variante=nome):
                testo = (cartella / "prepara.js").read_text(encoding="utf-8")
                messi = set(re.findall(r'data-metti=\\"([a-z-]+)\\"', testo))
                self.assertEqual(messi, {"pistola", "spada", "bomba", "duo", "bazooka", "lanciafiamme",
                                         "fumogeno", "barattolo-fuoco", "barattolo-scossa", "barattolo-acqua"})
                self.assertIn("Pioggia di oggetti", testo)
                self.assertNotIn("Pioggia di telefoni", testo)
        casa = (RADICE / "web" / "templates" / "home.html").read_text(encoding="utf-8")
        for forma in ("classico", "orologio", "tablet", "pc", "fumogeno", "barattolo-fuoco"):
            self.assertIn(f'data-metti="{forma}"', casa)
        self.assertIn("Pioggia di telefoni", casa)
        ring = (RADICE / "web" / "static" / "ring.js").read_text(encoding="utf-8")
        self.assertIn("const senzaTelefoni = !!ospite;", ring)

    def test_la_guida_per_chi_ha_appena_installato(self):
        """Una pagina di benvenuto che si apre alla prima installazione e si riapre dalla tendina e dalle opzioni."""
        import re
        for nome, cartella in list(VARIANTI.items()) + [("natale", NATALE)]:
            with self.subTest(estensione=nome):
                pagina = (cartella / "benvenuto.html").read_text(encoding="utf-8")
                chiavi = set(re.findall(r'data-msg="([A-Za-z0-9]+)"', pagina))
                self.assertGreaterEqual(len(chiavi), 12)
                self.assertNotIn("<script>", pagina)                      # niente script scritti nella pagina (CSP delle estensioni)
                self.assertIn('<script src="benvenuto.js"></script>', pagina)
                for file in ("benvenuto.css", "benvenuto.js", "icone/128.png"):
                    self.assertTrue((cartella / file).exists(), file)
                for lingua in LINGUE:
                    messaggi = json.loads((cartella / "_locales" / lingua / "messages.json").read_text(encoding="utf-8"))
                    for chiave in chiavi | {"guidaLink"}:
                        self.assertTrue(messaggi.get(chiave, {}).get("message"), f"{nome}/{lingua}: manca {chiave}")
                sfondo = (cartella / "sfondo.js").read_text(encoding="utf-8")
                self.assertIn("chrome.runtime.onInstalled.addListener", sfondo)
                self.assertIn('dettagli.reason === "install"', sfondo)     # non a ogni aggiornamento
                self.assertIn('href="benvenuto.html"', (cartella / "opzioni.html").read_text(encoding="utf-8"))
                for vietato in ("fetch(", "XMLHttpRequest", "eval(", "new Function"):
                    self.assertNotIn(vietato, (cartella / "benvenuto.js").read_text(encoding="utf-8"))
        for nome, cartella in VARIANTI.items():
            testo = (cartella / "prepara.js").read_text(encoding="utf-8")
            self.assertIn("data-guida", testo)
            self.assertIn('tipo: "guida"', testo)
            self.assertIn('messaggio.tipo === "guida"', (cartella / "sfondo.js").read_text(encoding="utf-8"))
        # la riga su Premium c'è solo se Premium è chiuso
        scelte = json.loads((ESTENSIONE / "premium.json").read_text(encoding="utf-8"))
        self.assertEqual("guidaS5" in (VARIANTI["store"] / "benvenuto.html").read_text(encoding="utf-8"), bool(scelte.get("premium_attivo", True)))

    def test_l_indirizzo_di_acquisto_e_vuoto_o_https(self):
        dati = json.loads((ESTENSIONE / "premium.json").read_text(encoding="utf-8"))
        url = dati.get("url_acquisto", "")
        self.assertTrue(url == "" or url.startswith("https://"), url)


NATALE = ESTENSIONE / "natale"


class TestEstensioneDiNatale(unittest.TestCase):
    """«Page Snow»: la seconda estensione, solo il tema di Natale."""

    def test_manifest_v3_col_permesso_minimo_e_quello_su_tutti_i_siti_facoltativo(self):
        m = json.loads((NATALE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["manifest_version"], 3)
        self.assertEqual(sorted(m["permissions"]), ["activeTab", "scripting", "storage"])
        self.assertNotIn("host_permissions", m)
        self.assertNotIn("content_scripts", m)
        self.assertEqual(m["optional_host_permissions"], ["<all_urls>"])
        for lato in ("16", "48", "128"):
            self.assertTrue((NATALE / m["icons"][lato]).exists())
        for file in (m["background"]["service_worker"], m["options_ui"]["page"], "pagina.css"):
            self.assertTrue((NATALE / file).exists(), file)

    def test_il_cuore_e_lo_stesso_file_del_sito(self):
        self.assertEqual((NATALE / "natale.js").read_text(encoding="utf-8"),
                         (RADICE / "web" / "static" / "natale.js").read_text(encoding="utf-8"))

    def test_nome_e_descrizione_in_cinque_lingue_dentro_i_limiti_dello_store(self):
        for lingua in LINGUE:
            messaggi = json.loads((NATALE / "_locales" / lingua / "messages.json").read_text(encoding="utf-8"))
            self.assertEqual(messaggi["nome"]["message"], "Page Snow")
            self.assertLessEqual(len(messaggi["descrizione"]["message"]), 132)
            self.assertEqual({k for k in messaggi if not k.startswith("guida")},
                             {"nome", "descrizione", "titolo", "opzioniTitolo", "sempreEtichetta", "sempreSpiega", "sempreNegato"})

    def test_niente_codice_da_fuori_e_niente_rete(self):
        for file in ("prepara.js", "sfondo.js", "natale.js", "opzioni.js"):
            testo = (NATALE / file).read_text(encoding="utf-8")
            for vietato in ("fetch(", "XMLHttpRequest", "eval(", "new Function", "importScripts(", "<script"):
                self.assertNotIn(vietato, testo, f"{file}: {vietato}")

    def test_il_tema_parte_al_clic_e_da_solo_soltanto_per_chi_lo_sceglie(self):
        sfondo = (NATALE / "sfondo.js").read_text(encoding="utf-8")
        self.assertIn("window.__nataleAvvio = true", sfondo)
        self.assertLess(sfondo.index('"prepara.js"'), sfondo.index('"natale.js"'))
        self.assertNotIn("scripting.registerContentScripts", sfondo)
        opzioni = (NATALE / "opzioni.js").read_text(encoding="utf-8")
        self.assertLess(opzioni.index("chrome.permissions.request(TUTTI)"), opzioni.index("registerContentScripts"))
        self.assertIn('js: ["prepara.js", "natale.js"]', opzioni)
        prepara = (NATALE / "prepara.js").read_text(encoding="utf-8")
        self.assertIn("attachShadow", prepara)
        self.assertIn("window.top !== window", prepara)
        self.assertIn('"ps-spento"', prepara)                 # spento dal tasto, resta spento sulle altre pagine

    def test_natale_js_sa_stare_fuori_dal_sito(self):
        js = (RADICE / "web" / "static" / "natale.js").read_text(encoding="utf-8")
        self.assertIn("window.__nataleEstensione", js)
        self.assertIn("est && est.radice ? est.radice : document.body", js)    # il canvas nello shadow DOM
        # Sul sito non cambia niente: la scelta resta in `mut-natale` e il tasto è quello della testata.
        self.assertIn('"mut-natale"', js)
        self.assertIn("[data-natale-tasto]", js)


if __name__ == "__main__":
    unittest.main()
