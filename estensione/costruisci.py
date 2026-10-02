#!/usr/bin/env python3
"""Costruisce l'estensione del browser a partire dai file del sito.

Il ring ha UNA sola sorgente: `web/static/ring.js`, la tendina di
`web/templates/home.html` e il suo stile in `web/static/style.css`. Questo
script li copia in `estensione/pacchetto/` aggiungendo quello che serve a un
browser: il manifest, il service worker che parte al clic sull'icona, e
`prepara.js`, che crea canvas e tendina dentro uno shadow DOM (così lo stile
dei siti non li tocca) prima di far partire il ring.

Si costruiscono DUE varianti, uguali in tutto tranne una cosa:
  - `pacchetto/`  da caricare a mano per provare: nella tendina c'è un
    interruttore «Premium di prova» per vedere il gioco bloccato e sbloccato;
  - `store/`      da pubblicare: niente interruttore di prova. Premium si
    compra dall'indirizzo scritto in `premium.json` (`url_acquisto`); finché è
    vuoto il tasto dice «Premium arriva presto».

Uso:
    python3 estensione/costruisci.py            # rigenera pacchetto/ e store/
    python3 estensione/costruisci.py --verifica # esce con 1 se sono vecchi
    python3 estensione/costruisci.py --zip      # rigenera e prepara i due zip in estensione/zip/

Il test `tests/test_estensione.py` usa `--verifica`: chi cambia il ring e
dimentica di rigenerare l'estensione se ne accorge subito.
"""
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
QUI = Path(__file__).resolve().parent
VARIANTI = {"pacchetto": {"premium_di_prova": True}, "store": {"premium_di_prova": False}}
VERSIONE = "0.3.0"
NOME = "Page Brawl"

MANIFEST = {
    "manifest_version": 3,
    "name": "__MSG_nome__",
    "version": VERSIONE,
    "description": "__MSG_descrizione__",
    "default_locale": "en",
    "action": {"default_title": "__MSG_titolo__"},
    "background": {"service_worker": "sfondo.js"},
    # Il permesso minimo: solo la scheda su cui si clicca l'icona.
    "permissions": ["activeTab", "scripting", "storage"],
    # Facoltativo, chiesto solo a chi accende «tasto su tutti i siti» nelle opzioni.
    "optional_host_permissions": ["<all_urls>"],
    "options_ui": {"page": "opzioni.html", "open_in_tab": False},
    "icons": {"16": "icone/16.png", "48": "icone/48.png", "128": "icone/128.png"},
}

# Nome, descrizione breve (al massimo 132 caratteri: è il limite dello store),
# titolo del tasto e i testi della pagina delle opzioni, nelle lingue dell'estensione.
MESSAGGI = {
    "en": {
        "descrizione": "A robot and an apple brawl on the page you are viewing. Grab them, throw them, bet on the winner.",
        "titolo": "Start or stop the brawl on this page",
        "opzioniTitolo": "Page Brawl options",
        "sempreEtichetta": "Show the power button on every site",
        "sempreSpiega": "A small button stays in the bottom right corner of every page: one click starts the brawl, without going through the toolbar icon. To put it there, the browser will ask you to let Page Brawl run on all sites. Nothing is read from the pages and nothing is sent anywhere.",
        "sempreNegato": "Permission not granted: the button stays off.",
    },
    "it": {
        "descrizione": "Un robot e una mela si picchiano sulla pagina che stai guardando. Prendili, lanciali, scommetti su chi vince.",
        "titolo": "Accendi o spegni la lotta su questa pagina",
        "opzioniTitolo": "Opzioni di Page Brawl",
        "sempreEtichetta": "Mostra il tasto di accensione su tutti i siti",
        "sempreSpiega": "Un tastino resta nell'angolo in basso a destra di ogni pagina: un clic e la lotta parte, senza passare dall'icona nella barra. Per metterlo lì il browser ti chiede di lasciar funzionare Page Brawl su tutti i siti. Dalle pagine non viene letto niente e non viene inviato niente.",
        "sempreNegato": "Permesso non concesso: il tasto resta spento.",
    },
    "es": {
        "descrizione": "Un robot y una manzana se pelean en la página que estás viendo. Agárralos, lánzalos y apuesta por el ganador.",
        "titolo": "Enciende o apaga la pelea en esta página",
        "opzioniTitolo": "Opciones de Page Brawl",
        "sempreEtichetta": "Mostrar el botón de encendido en todos los sitios",
        "sempreSpiega": "Un botoncito se queda en la esquina inferior derecha de cada página: un clic y empieza la pelea, sin pasar por el icono de la barra. Para ponerlo ahí, el navegador te pedirá que dejes funcionar Page Brawl en todos los sitios. No se lee nada de las páginas y no se envía nada.",
        "sempreNegato": "Permiso no concedido: el botón sigue apagado.",
    },
    "fr": {
        "descrizione": "Un robot et une pomme se battent sur la page que vous regardez. Attrapez-les, lancez-les, pariez sur le vainqueur.",
        "titolo": "Lancer ou arrêter le combat sur cette page",
        "opzioniTitolo": "Options de Page Brawl",
        "sempreEtichetta": "Afficher le bouton de mise en marche sur tous les sites",
        "sempreSpiega": "Un petit bouton reste dans le coin inférieur droit de chaque page : un clic et le combat commence, sans passer par l'icône de la barre. Pour l'y placer, le navigateur vous demandera de laisser Page Brawl fonctionner sur tous les sites. Rien n'est lu dans les pages et rien n'est envoyé.",
        "sempreNegato": "Autorisation refusée : le bouton reste désactivé.",
    },
    "de": {
        "descrizione": "Ein Roboter und ein Apfel prügeln sich auf der Seite, die du gerade ansiehst. Pack sie, wirf sie, wette auf den Sieger.",
        "titolo": "Kampf auf dieser Seite starten oder stoppen",
        "opzioniTitolo": "Optionen von Page Brawl",
        "sempreEtichetta": "Einschaltknopf auf allen Websites anzeigen",
        "sempreSpiega": "Ein kleiner Knopf bleibt unten rechts auf jeder Seite: ein Klick und der Kampf beginnt, ohne das Symbol in der Leiste. Dafür fragt der Browser, ob Page Brawl auf allen Websites laufen darf. Aus den Seiten wird nichts gelesen und nichts wird gesendet.",
        "sempreNegato": "Berechtigung nicht erteilt: Der Knopf bleibt aus.",
    },
}

SFONDO = """/* Il service worker dell'estensione: al clic sull'icona accende il ring
 * sulla scheda attiva; a un secondo clic lo spegne (e poi lo riaccende). */
async function avvia(tab) {
  if (!tab || !tab.id) return "nessuna scheda";
  const dove = { tabId: tab.id };
  try {
    const [{ result: gia }] = await chrome.scripting.executeScript({ target: dove, func: () => !!window.__ringEstensione });
    if (gia) {
      await chrome.scripting.executeScript({ target: dove, func: () => window.__ringEstensione.alterna() });
      return "alternato";
    }
    // La memoria dei lottatori (quello che hanno imparato, i gettoni, le
    // opzioni) è dell'estensione: uguale su tutti i siti.
    const dati = await chrome.storage.local.get(null);
    // `__lingueSoloDizionario`: il dizionario delle lingue serve solo alla tendina, la pagina non si tocca.
    await chrome.scripting.executeScript({ target: dove, func: (d) => { window.__ringDati = d; window.__lingueSoloDizionario = true; }, args: [dati] });
    // Il cursore a manina sopra i lottatori: inserito dall'estensione, così passa anche
    // sui siti con una Content-Security-Policy che vieta gli stili scritti nella pagina.
    await chrome.scripting.insertCSS({ target: dove, css: __STILE_PAGINA__ });
    await chrome.scripting.executeScript({ target: dove, files: ["lingue.js", "prepara.js", "ring.js"] });
    return "acceso";
  } catch (errore) {
    // Pagine dove un'estensione non può entrare (chrome://, il Web Store, i PDF).
    return "non permesso: " + (errore && errore.message);
  }
}
chrome.action.onClicked.addListener(avvia);
// Dal tasto sempre visibile (per chi l'ha acceso nelle opzioni) e dalla tendina.
chrome.runtime.onMessage.addListener((messaggio, mittente) => {
  if (!messaggio) return;
  if (messaggio.tipo === "avvia" && mittente.tab) avvia(mittente.tab);
  if (messaggio.tipo === "opzioni") chrome.runtime.openOptionsPage();
});
// Tolto il permesso su tutti i siti dalle impostazioni del browser: via anche il tasto.
chrome.permissions.onRemoved.addListener(async () => {
  try {
    if (await chrome.permissions.contains({ origins: ["<all_urls>"] })) return;
    await chrome.scripting.unregisterContentScripts({ ids: ["pb-tasto"] });
    await chrome.storage.local.set({ "pb-sempre": "off" });
  } catch (errore) { /* non era registrato */ }
});
"""

STILE_BASE = """
:host {
  --carta: #ffffff; --ink: #201e1d; --bordo: #d4d0c8; --filo: rgba(32, 30, 29, .14);
  --verde: #1f7a5a; --verde-tenue: rgba(31, 122, 90, .14); --fondo-firmware: #f3f7f5; --su-tinta: #ffffff;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; font-size: 15px; line-height: 1.35;
}
@media (prefers-color-scheme: dark) {
  :host { --carta: #1c1b1a; --ink: #ebe9e6; --bordo: #3a3835; --filo: rgba(235, 233, 230, .14);
          --verde: #46c291; --verde-tenue: rgba(70, 194, 145, .16); --fondo-firmware: #17231e; }
}
/* Il carattere si fissa QUI DENTRO e non sull'ospite: lo stile della pagina può
   arrivare fino all'ospite (un `* { font-family: … !important }`), ma non oltre. */
.barretta, .ring-pannello {
  font: 15px/1.35 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--ink);
  text-align: left; letter-spacing: normal; text-transform: none; word-spacing: normal;
}
*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
.tela { position: fixed; top: 0; left: 0; display: block; pointer-events: none; touch-action: none; }
.ancora { position: fixed; right: 0; left: 0; bottom: 58px; height: 0; pointer-events: none; }
.barretta {
  position: fixed; right: 12px; bottom: 12px; display: flex; gap: 6px; padding: 5px;
  pointer-events: auto; background: var(--carta); color: var(--ink);
  border: 1px solid var(--bordo); border-radius: 999px; box-shadow: 0 6px 18px rgba(0, 0, 0, .18);
}
.tasto {
  width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--bordo); background: var(--carta);
  color: var(--ink); font: inherit; font-size: 17px; cursor: pointer; display: grid; place-items: center; padding: 0;
}
.tasto:hover { border-color: var(--verde); }
.tasto[aria-expanded="true"] { background: var(--verde-tenue); }
.tasto[data-gioca] { color: var(--verde); }
.tasto[data-gioca][aria-pressed="false"] { color: var(--ink); opacity: .65; }
/* Spento: resta solo il tasto di accensione. */
:host([data-spento]) .tela, :host([data-spento]) .ancora, :host([data-spento]) [data-opzioni] { display: none !important; }
h3 { font-weight: 700; }
/* Premium: i tasti chiusi portano il lucchetto; in cima alla tendina il riquadro che spiega e sblocca. */
.ring-tasto.bloccato { opacity: .72; }
.ring-tasto.bloccato::after { content: "\\1F512"; float: right; margin-left: .3rem; font-size: .8em; }
.premio { border: 1px solid var(--bordo); border-radius: 10px; padding: .55rem .65rem; margin: .5rem 0 .2rem; background: var(--fondo-firmware); }
.premio p { margin: 0 0 .45rem; font-size: .84rem; }
.premio .premio-avviso { font-weight: 700; color: #b3261e; }
.premio.cercato { outline: 2px solid var(--verde); }
.premio .ring-tasto { margin-top: .3rem; }
.premio [data-premio-compra] { background: var(--verde); border-color: var(--verde); color: var(--su-tinta); font-weight: 700; }
"""

STILE_PAGINA = ("html.ring-presa, html.ring-presa * { cursor: grab !important; } "
                "html.ring-trascina, html.ring-trascina * { cursor: grabbing !important; user-select: none !important; }")

ICONA_ACCENSIONE = ('<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">'
                    '<path d="M12 3v9" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>'
                    '<path d="M7.1 6.3a8 8 0 1 0 9.8 0" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>')

# Il tasto di accensione è `data-gioca`, quello che il ring già conosce: acceso
# c'è tutto, spento resta solo lui (vedi `:host([data-spento])`).
BARRETTA = """
  <div class="barretta">
    <button type="button" class="tasto" data-opzioni hidden aria-expanded="false"
            title="Opzioni del combattimento: scommesse, armi, imprevisti">&#129354;</button>
    <button type="button" class="tasto" data-gioca hidden aria-pressed="true" aria-label="Lotte accese o spente"
            title="Spegni le lotte">__ICONA__</button>
  </div>
""".replace("__ICONA__", ICONA_ACCENSIONE)

# Il tasto per chi lo vuole su ogni pagina: uno script minuscolo, registrato
# solo dopo che l'utente l'ha chiesto nelle opzioni e ha dato il permesso.
TASTO = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * Il tasto di accensione sempre visibile: in basso a destra, su ogni pagina.
 * Un clic chiede al service worker di far partire il ring su questa scheda.
 */
(function () {
  "use strict";
  if (window.top !== window || window.__ringEstensione || document.getElementById("page-brawl") || document.getElementById("page-brawl-tasto")) return;
  var ospite = document.createElement("div");
  ospite.id = "page-brawl-tasto";
  ospite.style.cssText = "all: initial; position: fixed; right: 12px; bottom: 12px; z-index: 2147483646;";
  var radice = ospite.attachShadow({ mode: "open" });
  radice.innerHTML = __HTML__;
  try {
    var foglio = new CSSStyleSheet();
    foglio.replaceSync(__STILE__);
    radice.adoptedStyleSheets = [foglio];
  } catch (e) { /* senza stile resta un tasto qualunque */ }
  var tasto = radice.querySelector("button"), titolo = "";
  try { titolo = chrome.i18n.getMessage("titolo"); } catch (e) { /* niente titolo */ }
  tasto.title = titolo; tasto.setAttribute("aria-label", titolo);
  tasto.addEventListener("click", function () {
    try { chrome.runtime.sendMessage({ tipo: "avvia" }); }
    catch (e) { ospite.remove(); }             // estensione aggiornata o tolta: il tasto non serve più
  });
  document.documentElement.appendChild(ospite);
})();
"""
STILE_TASTO = """
button {
  width: 48px; height: 48px; border-radius: 50%; border: 1px solid #d4d0c8; background: #ffffff; color: #201e1d;
  opacity: .75; cursor: pointer; display: grid; place-items: center; padding: 0; box-shadow: 0 6px 18px rgba(0, 0, 0, .18);
}
button:hover { opacity: 1; border-color: #1f7a5a; color: #1f7a5a; }
@media (prefers-color-scheme: dark) { button { background: #1c1b1a; color: #ebe9e6; border-color: #3a3835; } }
"""

OPZIONI_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Page Brawl</title>
<link rel="stylesheet" href="opzioni.css">
</head>
<body>
<h1 data-msg="opzioniTitolo"></h1>
<label><input type="checkbox" id="sempre"> <span data-msg="sempreEtichetta"></span></label>
<p data-msg="sempreSpiega"></p>
<p id="esito" role="status"></p>
<script src="opzioni.js"></script>
</body>
</html>
"""
OPZIONI_CSS = """body { font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; margin: 16px 18px; min-width: 320px; max-width: 520px; color: #201e1d; }
h1 { font-size: 18px; margin: 0 0 12px; }
label { display: flex; gap: 8px; align-items: flex-start; font-weight: 600; }
p { margin: 10px 0 0; color: #4a4744; }
#esito { color: #b3261e; min-height: 1.4em; }
@media (prefers-color-scheme: dark) { body { background: #1c1b1a; color: #ebe9e6; } p { color: #bdb9b3; } }
"""
OPZIONI_JS = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * La pagina delle opzioni: una sola scelta, il tasto di accensione su tutti i
 * siti. Accenderla fa chiedere al browser il permesso (facoltativo) su tutti
 * i siti e registra lo script del tasto; spegnerla toglie l'uno e l'altro.
 */
(function () {
  "use strict";
  var TUTTI = { origins: ["<all_urls>"] }, ID = "pb-tasto";
  var casella = document.getElementById("sempre"), esito = document.getElementById("esito");
  var m = function (chiave) { return chrome.i18n.getMessage(chiave) || chiave; };
  document.querySelectorAll("[data-msg]").forEach(function (el) { el.textContent = m(el.getAttribute("data-msg")); });
  document.title = m("opzioniTitolo");
  async function registrato() { return (await chrome.scripting.getRegisteredContentScripts({ ids: [ID] })).length > 0; }
  async function leggi() { casella.checked = (await chrome.permissions.contains(TUTTI)) && (await registrato()); }
  casella.addEventListener("change", async function () {
    esito.textContent = "";
    try {
      if (casella.checked) {
        // La richiesta va fatta subito, dentro il clic: è il browser a mostrare la domanda.
        var concesso = await chrome.permissions.request(TUTTI);
        if (!concesso) { casella.checked = false; esito.textContent = m("sempreNegato"); return; }
        if (!(await registrato())) {
          await chrome.scripting.registerContentScripts([{ id: ID, js: ["tasto.js"], matches: ["<all_urls>"], runAt: "document_idle" }]);
        }
        await chrome.storage.local.set({ "pb-sempre": "on" });
      } else {
        if (await registrato()) await chrome.scripting.unregisterContentScripts({ ids: [ID] });
        await chrome.storage.local.set({ "pb-sempre": "off" });
        try { await chrome.permissions.remove(TUTTI); } catch (e) { /* già tolto */ }
      }
    } catch (e) {
      esito.textContent = String((e && e.message) || e);
      await leggi();
    }
  });
  leggi();
})();
"""

PREPARA = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * Prepara la pagina per il ring: crea, dentro uno shadow DOM, il canvas, la
 * tendina delle opzioni e i due tasti; dichiara al ring dove stanno
 * (`window.__ringRadice`) e gli dà una memoria che vale su tutti i siti
 * (`window.__ringDeposito`, sopra `chrome.storage.local`).
 */
(function () {
  "use strict";
  if (window.__ringEstensione) return;
  var CONFIG = __CONFIG__;
  var memoria = Object.assign({}, window.__ringDati || {});
  memoria["mut-ring"] = "on";                    // chi clicca l'icona vuole la lotta accesa
  // Schizzi e arti staccati partono spenti: si accendono dalla tendina.
  if (!Object.prototype.hasOwnProperty.call(memoria, "mut-ring-cruento")) memoria["mut-ring-cruento"] = "off";
  function ricorda(k, v) {
    memoria[k] = String(v);
    try { var o = {}; o[k] = String(v); chrome.storage.local.set(o); } catch (e) { /* resta in memoria */ }
  }
  window.__ringDeposito = {
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(memoria, k) ? memoria[k] : null; },
    setItem: function (k, v) {
      if (k === "mut-ring") { memoria[k] = String(v); return; }   // acceso/spento vale solo per questa pagina
      ricorda(k, v);
    },
  };

  // PREMIUM. Tre gruppi di funzioni sono a pagamento; lo stato sta nella
  // memoria dell'estensione. Il ring chiede qui se un gruppo è libero e, se
  // non lo è, fa aprire il riquadro in cima alla tendina.
  var premiumAttivo = memoria["pb-premium"] === "on", inAscolto = [];
  function impostaPremium(valore) {
    premiumAttivo = !!valore;
    ricorda("pb-premium", premiumAttivo ? "on" : "off");
    for (var i = 0; i < inAscolto.length; i++) { try { inAscolto[i](); } catch (e) { /* un ascoltatore rotto non ferma gli altri */ } }
    aggiornaRiquadro(false);
  }
  // `premium_attivo: false` in premium.json: niente di chiuso, tutto gratis.
  if (CONFIG.premium) window.__ringPremium = {
    bloccate: { guerrieri: true, armi: true, meteo: true },
    attivo: function () { return premiumAttivo; },
    chiedi: function () { aggiornaRiquadro(true); },
    ascolta: function (fn) { inAscolto.push(fn); },
  };
  var ospite = document.createElement("div");
  ospite.id = "page-brawl";
  ospite.style.cssText = "all: initial; position: fixed; inset: 0; z-index: 2147483646; pointer-events: none;";
  var radice = ospite.attachShadow({ mode: "open" });
  radice.innerHTML = __HTML__;
  // Lo stile come foglio «costruito»: a differenza di un <style> non lo ferma
  // la Content-Security-Policy dei siti che vietano gli stili in pagina.
  try {
    var foglio = new CSSStyleSheet();
    foglio.replaceSync(__STILE__);
    radice.adoptedStyleSheets = [foglio];
  } catch (e) {
    var stile = document.createElement("style");
    stile.textContent = __STILE__;
    radice.appendChild(stile);
  }
  document.documentElement.appendChild(ospite);
  window.__ringRadice = radice;
  // Se c'era il tasto sempre visibile, da qui in poi lo sostituisce la barretta.
  var solo = document.getElementById("page-brawl-tasto");
  if (solo) solo.remove();

  // Il tasto di accensione resta sempre in vista: spento, il resto sparisce
  // (canvas, tendina, tasto delle opzioni); riacceso, torna tutto.
  var accensione = radice.querySelector("[data-gioca]");
  function allinea() {
    if (accensione.getAttribute("aria-pressed") === "true") { ospite.removeAttribute("data-spento"); return; }
    ospite.setAttribute("data-spento", "");
    var tendina = radice.querySelector("[data-pannello]"), apri = radice.querySelector("[data-opzioni]");
    if (tendina) tendina.classList.remove("aperto");
    if (apri) apri.setAttribute("aria-expanded", "false");
  }
  new MutationObserver(allinea).observe(accensione, { attributes: true, attributeFilter: ["aria-pressed"] });
  var versoOpzioni = radice.querySelector("[data-opzioni-estensione]");
  if (versoOpzioni) versoOpzioni.addEventListener("click", function () {
    try { chrome.runtime.sendMessage({ tipo: "opzioni" }); } catch (e) { /* estensione ricaricata */ }
  });

  // Il riquadro Premium: cosa sblocca, il tasto per comprarlo e, nella sola
  // variante di prova, un interruttore per vedere il gioco aperto e chiuso.
  function aggiornaRiquadro(cercato) {
    var q = function (sel) { return radice.querySelector(sel); };
    var riquadro = q("[data-premio]");
    if (!riquadro) return;
    q("[data-premio-avviso]").hidden = premiumAttivo || !cercato;
    q("[data-premio-attivo]").hidden = !premiumAttivo;
    q("[data-premio-cosa]").hidden = premiumAttivo;
    var compra = q("[data-premio-compra]");
    compra.hidden = premiumAttivo;
    compra.disabled = !CONFIG.urlAcquisto;
    compra.textContent = CONFIG.urlAcquisto ? "Sblocca Premium" : "Premium arriva presto";
    var prova = q("[data-premio-prova]");
    if (prova) prova.setAttribute("aria-pressed", premiumAttivo ? "true" : "false");
    riquadro.classList.toggle("cercato", !!cercato && !premiumAttivo);
    if (cercato && !premiumAttivo) {
      var pannello = q("[data-pannello]"), apri = q("[data-opzioni]");
      if (pannello && !pannello.classList.contains("aperto") && apri) apri.click();
      if (pannello) pannello.scrollTop = 0;
    }
  }
  (function () {
    var compra = radice.querySelector("[data-premio-compra]"), prova = radice.querySelector("[data-premio-prova]");
    if (compra) compra.addEventListener("click", function () { if (CONFIG.urlAcquisto) window.open(CONFIG.urlAcquisto, "_blank", "noopener"); });
    if (prova) prova.addEventListener("click", function () { impostaPremium(!premiumAttivo); });
    aggiornaRiquadro(false);
  })();

  // La lingua: quella del browser, se è una delle cinque; altrimenti inglese.
  // Il dizionario è lo stesso del sito (`lingue.js`), applicato solo qui dentro.
  try {
    var lingua = (memoria["pb-lingua"] || (chrome.i18n && chrome.i18n.getUILanguage()) || navigator.language || "en").slice(0, 2).toLowerCase();
    if (window.__lingue) window.__lingue.copri(radice, window.__lingue.codici.indexOf(lingua) >= 0 ? lingua : "en");
  } catch (e) { /* resta in italiano */ }
  window.__ringEstensione = {
    ospite: ospite,
    premium: impostaPremium,
    // Un altro clic sull'icona nella barra fa lo stesso del tasto di accensione.
    alterna: function () { accensione.click(); },
  };
})();
"""


def tendina() -> str:
    pagina = (RADICE / "web/templates/home.html").read_text(encoding="utf-8")
    inizio = pagina.index('<div class="ring-pannello"')
    fine = pagina.index('<div class="ultimora-barra">')
    blocco = pagina[inizio:fine].rstrip()
    if "{%" in blocco or "{{" in blocco or "{#" in blocco:
        raise SystemExit("la tendina contiene Jinja: l'estensione non la può usare così")
    return blocco


def stile_tendina() -> str:
    css = (RADICE / "web/static/style.css").read_text(encoding="utf-8")
    inizio = css.index("/* --- La tendina del ring")
    coda = "@media (prefers-reduced-motion: reduce) { .ring-pannello, .ring-pannello.aperto { transition: none; } }"
    fine = css.index(coda, inizio) + len(coda)
    return css[inizio:fine]


def icona(lato: int) -> bytes:
    """Un guantone rosso su fondo verde scuro, disegnato qui (niente file esterni)."""
    import io
    from PIL import Image, ImageDraw
    k = 4
    n = lato * k
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 0.22, fill=(22, 70, 54, 255))
    # il polsino, poi il guanto e il pollice
    d.rounded_rectangle([n * 0.30, n * 0.68, n * 0.66, n * 0.86], radius=n * 0.05, fill=(245, 245, 245, 255))
    d.ellipse([n * 0.22, n * 0.16, n * 0.74, n * 0.74], fill=(224, 58, 47, 255))
    d.ellipse([n * 0.58, n * 0.36, n * 0.84, n * 0.66], fill=(200, 44, 36, 255))
    d.arc([n * 0.30, n * 0.24, n * 0.60, n * 0.54], start=190, end=280, fill=(255, 255, 255, 200), width=max(1, n // 24))
    uscita = io.BytesIO()
    img.resize((lato, lato), Image.LANCZOS).save(uscita, format="PNG", optimize=True)
    return uscita.getvalue()


RIQUADRO_PREMIO = """
    <section class="premio" data-premio>
      <p class="premio-avviso" data-premio-avviso hidden>Questa funzione fa parte di Premium.</p>
      <p data-premio-attivo hidden>Premium attivo.</p>
      <p data-premio-cosa>Premium sblocca i personaggi (super guerrieri, maghi e duellanti) con le loro mosse, le armi e le bombe, il meteo e la gravità.</p>
      <button type="button" class="ring-tasto ring-largo" data-premio-compra>Sblocca Premium</button>__PROVA__
    </section>"""
VERSO_OPZIONI = """  <section class="ring-sezione">
      <button type="button" class="ring-tasto ring-largo" data-opzioni-estensione>&#9881; Tasto di accensione su tutti i siti</button>
    </section>
  """
TASTO_PROVA = """
      <button type="button" class="ring-tasto ring-largo" data-premio-prova aria-pressed="false">Premium di prova (solo in questa versione)</button>"""


def premium() -> dict:
    """Le due scelte di `premium.json`.

    `premium_attivo`: se falso non c'è niente di chiuso (utile per uscire con
    tutto gratis finché non si vende). `url_acquisto`: dove si compra; finché è
    vuoto il tasto resta «Premium arriva presto».
    """
    percorso = QUI / "premium.json"
    dati = json.loads(percorso.read_text(encoding="utf-8")) if percorso.exists() else {}
    url = str(dati.get("url_acquisto") or "").strip()
    if url and not url.startswith("https://"):
        raise SystemExit("premium.json: url_acquisto deve cominciare con https://")
    return {"premium": bool(dati.get("premium_attivo", True)), "urlAcquisto": url}


def file_attesi(variante: str) -> dict:
    opzioni = VARIANTI[variante]
    pannello = tendina()
    testa = '<div class="ring-pannello-testa">'
    fine_testa = pannello.index("</div>", pannello.index(testa)) + len("</div>")
    scelte = premium()
    if scelte["premium"]:
        riquadro = RIQUADRO_PREMIO.replace("__PROVA__", TASTO_PROVA if opzioni["premium_di_prova"] else "")
        pannello = pannello[:fine_testa] + riquadro + pannello[fine_testa:]
    # In fondo alla tendina, la strada per le opzioni dell'estensione.
    fine = pannello.rindex("</div>")
    pannello = pannello[:fine] + VERSO_OPZIONI + pannello[fine:]
    html = '<canvas class="tela" data-ring aria-hidden="true"></canvas>\n<div class="ancora">\n  ' + pannello + "\n</div>" + BARRETTA
    if "style=" in html:
        raise SystemExit("la tendina ha stili in linea: una CSP severa li bloccherebbe")
    config = dict(scelte, premiumDiProva=scelte["premium"] and opzioni["premium_di_prova"])
    prepara = (PREPARA
               .replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
               .replace("__STILE__", json.dumps(STILE_BASE + stile_tendina(), ensure_ascii=False))
               .replace("__HTML__", json.dumps(html, ensure_ascii=False)))
    attesi = {
        "manifest.json": json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n",
        "sfondo.js": SFONDO.replace("__STILE_PAGINA__", json.dumps(STILE_PAGINA, ensure_ascii=False)),
        "prepara.js": prepara,
        "ring.js": (RADICE / "web/static/ring.js").read_text(encoding="utf-8"),
        "lingue.js": (RADICE / "web/static/lingue.js").read_text(encoding="utf-8"),
        "tasto.js": (TASTO.replace("__HTML__", json.dumps('<button type="button">' + ICONA_ACCENSIONE + "</button>"))
                          .replace("__STILE__", json.dumps(STILE_TASTO))),
        "opzioni.html": OPZIONI_HTML, "opzioni.css": OPZIONI_CSS, "opzioni.js": OPZIONI_JS,
    }
    for lingua, testi in MESSAGGI.items():
        if set(testi) != set(MESSAGGI["en"]):
            raise SystemExit(f"messaggi {lingua}: chiavi diverse dall'inglese")
        if len(testi["descrizione"]) > 132:
            raise SystemExit(f"descrizione {lingua} troppo lunga per lo store: {len(testi['descrizione'])} caratteri")
        messaggi = {"nome": {"message": NOME}}
        messaggi.update({chiave: {"message": testo} for chiave, testo in testi.items()})
        attesi[f"_locales/{lingua}/messages.json"] = json.dumps(messaggi, ensure_ascii=False, indent=2) + "\n"
    return attesi


# ---------------------------------------------------------------------------
# PAGE SNOW: la seconda estensione, solo il tema di Natale (02/10/2026).
# Il cuore è `web/static/natale.js`, lo stesso file del sito: qui gli si dice
# dove mettere il canvas e gli si mette accanto un tasto per accendere e
# spegnere. Gratis, nessun Premium.
# ---------------------------------------------------------------------------
NATALE_VERSIONE = "0.1.0"
NATALE_NOME = "Page Snow"
NATALE_MANIFEST = {
    "manifest_version": 3,
    "name": "__MSG_nome__",
    "version": NATALE_VERSIONE,
    "description": "__MSG_descrizione__",
    "default_locale": "en",
    "action": {"default_title": "__MSG_titolo__"},
    "background": {"service_worker": "sfondo.js"},
    "permissions": ["activeTab", "scripting", "storage"],
    # Facoltativo: solo per chi sceglie, nelle opzioni, il Natale su tutti i siti.
    "optional_host_permissions": ["<all_urls>"],
    "options_ui": {"page": "opzioni.html", "open_in_tab": False},
    "icons": {"16": "icone/16.png", "48": "icone/48.png", "128": "icone/128.png"},
}
NATALE_MESSAGGI = {
    "en": {
        "descrizione": "Snow falls on the page you are viewing and piles up on it. Lights, icicles, a tree with gifts, snowmen to take apart.",
        "titolo": "Turn the snow on or off on this page",
        "opzioniTitolo": "Page Snow options",
        "sempreEtichetta": "Turn the Christmas theme on automatically on every site",
        "sempreSpiega": "Every page you open gets the snow without clicking the toolbar icon; the snowflake button in the bottom right corner turns it off and on again everywhere. To do this, the browser will ask you to let Page Snow run on all sites. Nothing is read from the pages and nothing is sent anywhere.",
        "sempreNegato": "Permission not granted: the theme stays manual.",
    },
    "it": {
        "descrizione": "Nevica sulla pagina che stai guardando, e la neve si accumula. Lucine, ghiaccioli, un albero coi regali, pupazzi da smontare.",
        "titolo": "Accendi o spegni la neve su questa pagina",
        "opzioniTitolo": "Opzioni di Page Snow",
        "sempreEtichetta": "Accendi da solo il tema di Natale su tutti i siti",
        "sempreSpiega": "Ogni pagina che apri ha la neve senza cliccare l'icona nella barra; il tasto col fiocco in basso a destra la spegne e la riaccende dappertutto. Per farlo il browser ti chiede di lasciar funzionare Page Snow su tutti i siti. Dalle pagine non viene letto niente e non viene inviato niente.",
        "sempreNegato": "Permesso non concesso: il tema resta manuale.",
    },
    "es": {
        "descrizione": "Nieva sobre la página que estás viendo y la nieve se acumula. Luces, carámbanos, un árbol con regalos y muñecos de nieve.",
        "titolo": "Enciende o apaga la nieve en esta página",
        "opzioniTitolo": "Opciones de Page Snow",
        "sempreEtichetta": "Encender solo el tema de Navidad en todos los sitios",
        "sempreSpiega": "Cada página que abres tiene nieve sin pulsar el icono de la barra; el botón del copo, abajo a la derecha, la apaga y la vuelve a encender en todas partes. Para ello, el navegador te pedirá que dejes funcionar Page Snow en todos los sitios. No se lee nada de las páginas y no se envía nada.",
        "sempreNegato": "Permiso no concedido: el tema sigue siendo manual.",
    },
    "fr": {
        "descrizione": "Il neige sur la page que vous regardez et la neige s'accumule. Guirlandes, glaçons, sapin et cadeaux, bonshommes de neige.",
        "titolo": "Activer ou arrêter la neige sur cette page",
        "opzioniTitolo": "Options de Page Snow",
        "sempreEtichetta": "Activer automatiquement le thème de Noël sur tous les sites",
        "sempreSpiega": "Chaque page ouverte a sa neige sans cliquer sur l'icône de la barre ; le bouton au flocon, en bas à droite, l'arrête et la relance partout. Pour cela, le navigateur vous demandera de laisser Page Snow fonctionner sur tous les sites. Rien n'est lu dans les pages et rien n'est envoyé.",
        "sempreNegato": "Autorisation refusée : le thème reste manuel.",
    },
    "de": {
        "descrizione": "Es schneit auf der Seite, die du ansiehst, und der Schnee bleibt liegen. Lichter, Eiszapfen, ein Baum mit Geschenken, Schneemänner.",
        "titolo": "Schnee auf dieser Seite ein- oder ausschalten",
        "opzioniTitolo": "Optionen von Page Snow",
        "sempreEtichetta": "Weihnachtsdesign auf allen Websites automatisch einschalten",
        "sempreSpiega": "Jede geöffnete Seite bekommt Schnee, ohne das Symbol in der Leiste anzuklicken; der Knopf mit der Flocke unten rechts schaltet ihn überall aus und wieder ein. Dafür fragt der Browser, ob Page Snow auf allen Websites laufen darf. Aus den Seiten wird nichts gelesen und nichts wird gesendet.",
        "sempreNegato": "Berechtigung nicht erteilt: Das Design bleibt manuell.",
    },
}
NATALE_PAGINA_CSS = ("html.natale-presa, html.natale-presa * { cursor: grab !important; }\n"
                     "html.natale-trascina, html.natale-trascina * { cursor: grabbing !important; user-select: none !important; }\n")
NATALE_SFONDO = """/* Il service worker di Page Snow: al clic sull'icona accende la neve sulla
 * scheda attiva; a un secondo clic la spegne (e poi la riaccende). */
async function avvia(tab) {
  if (!tab || !tab.id) return "nessuna scheda";
  const dove = { tabId: tab.id };
  try {
    const [{ result: gia }] = await chrome.scripting.executeScript({ target: dove, func: () => !!window.__nataleEstensione });
    if (gia) {
      await chrome.scripting.executeScript({ target: dove, func: () => window.__nataleEstensione.alterna() });
      return "alternato";
    }
    // `__nataleAvvio`: chiesto con un clic, parte acceso (da solo, su tutti i siti, guarda prima se è stato spento).
    await chrome.scripting.executeScript({ target: dove, func: () => { window.__nataleAvvio = true; } });
    await chrome.scripting.insertCSS({ target: dove, files: ["pagina.css"] });
    await chrome.scripting.executeScript({ target: dove, files: ["prepara.js", "natale.js"] });
    return "acceso";
  } catch (errore) {
    // Pagine dove un'estensione non può entrare (chrome://, il Web Store, i PDF).
    return "non permesso: " + (errore && errore.message);
  }
}
chrome.action.onClicked.addListener(avvia);
// Tolto il permesso su tutti i siti dalle impostazioni del browser: il tema torna manuale.
chrome.permissions.onRemoved.addListener(async () => {
  try {
    if (await chrome.permissions.contains({ origins: ["<all_urls>"] })) return;
    await chrome.scripting.unregisterContentScripts({ ids: ["ps-auto"] });
    await chrome.storage.local.set({ "ps-sempre": "off" });
  } catch (errore) { /* non era registrato */ }
});
"""
ICONA_FIOCCO = ('<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
                '<path d="M12 2.5v19M3.8 7.2l16.4 9.6M20.2 7.2L3.8 16.8"/>'
                '<path d="M9.6 4.4L12 6.6l2.4-2.2M9.6 19.6L12 17.4l2.4 2.2M4.2 10.4l3-.8-.8-3M19.8 13.6l-3 .8.8 3M19.8 10.4l-3-.8.8-3M4.2 13.6l3 .8-.8 3"/></svg>')
NATALE_STILE = """
*, *::before, *::after { box-sizing: border-box; }
.natale-tela { position: fixed; top: 0; left: 0; display: block; pointer-events: none; }
.barretta { position: fixed; right: 12px; bottom: 68px; pointer-events: auto; }
button {
  width: 44px; height: 44px; border-radius: 50%; border: 1px solid #d4d0c8; background: #ffffff; color: #6b6660;
  cursor: pointer; display: grid; place-items: center; padding: 0; box-shadow: 0 6px 18px rgba(0, 0, 0, .18); opacity: .8;
}
button:hover { opacity: 1; }
button[aria-pressed="true"] { background: #c8102e; border-color: #c8102e; color: #ffffff; opacity: 1; }
@media (prefers-color-scheme: dark) { button { background: #1c1b1a; color: #bdb9b3; border-color: #3a3835; } }
@media print { :host { display: none; } }
"""
NATALE_PREPARA = """/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * Prepara la pagina per il tema di Natale: uno shadow DOM che tiene il
 * canvas della neve (`natale.js` ce lo mette da sé) e il tasto col fiocco
 * per spegnere e riaccendere.
 */
(function () {
  "use strict";
  if (window.top !== window || window.__nataleEstensione) return;
  // Caricato da solo (scelta «su tutti i siti») parte spento e guarda se l'utente l'aveva spento;
  // caricato da un clic sull'icona parte acceso.
  var daSolo = !window.__nataleAvvio;
  var ospite = document.createElement("div");
  ospite.id = "page-snow";
  ospite.style.cssText = "all: initial; position: fixed; inset: 0; z-index: 2147483645; pointer-events: none;";
  var radice = ospite.attachShadow({ mode: "open" });
  radice.innerHTML = __HTML__;
  try {
    var foglio = new CSSStyleSheet();
    foglio.replaceSync(__STILE__);
    radice.adoptedStyleSheets = [foglio];
  } catch (e) {
    var stile = document.createElement("style");
    stile.textContent = __STILE__;
    radice.appendChild(stile);
  }
  document.documentElement.appendChild(ospite);
  var tasto = radice.querySelector("button"), titolo = "";
  try { titolo = chrome.i18n.getMessage("titolo"); } catch (e) { /* niente titolo */ }
  tasto.title = titolo; tasto.setAttribute("aria-label", titolo);
  function mostra(acceso) { tasto.setAttribute("aria-pressed", acceso ? "true" : "false"); }
  mostra(!daSolo);
  window.__nataleEstensione = {
    radice: radice, ospite: ospite, acceso: !daSolo,
    // Dal tasto o da un altro clic sull'icona: spegne o riaccende. Con «su tutti i siti» la scelta vale ovunque.
    alterna: function () {
      var nuovo = !window.__natale.acceso();
      window.__natale.imposta(nuovo); mostra(nuovo);
      if (daSolo) { try { chrome.storage.local.set({ "ps-spento": nuovo ? "off" : "on" }); } catch (e) { /* solo per questa pagina */ } }
    },
  };
  tasto.addEventListener("click", function () { window.__nataleEstensione.alterna(); });
  if (daSolo) {
    try {
      chrome.storage.local.get("ps-spento").then(function (dati) {
        var su = dati["ps-spento"] !== "on";
        if (su && window.__natale) window.__natale.imposta(true);
        mostra(su);
      });
    } catch (e) { /* resta spento */ }
  }
})();
"""
NATALE_OPZIONI_JS = OPZIONI_JS.replace('ID = "pb-tasto"', 'ID = "ps-auto"').replace(
    '{ id: ID, js: ["tasto.js"], matches: ["<all_urls>"], runAt: "document_idle" }',
    '{ id: ID, js: ["prepara.js", "natale.js"], css: ["pagina.css"], matches: ["<all_urls>"], runAt: "document_idle" }'
).replace('"pb-sempre"', '"ps-sempre"').replace(
    "La pagina delle opzioni: una sola scelta, il tasto di accensione su tutti i\n * siti. Accenderla fa chiedere al browser il permesso (facoltativo) su tutti\n * i siti e registra lo script del tasto; spegnerla toglie l'uno e l'altro.",
    "La pagina delle opzioni: una sola scelta, il tema di Natale acceso da solo\n * su tutti i siti. Accenderla fa chiedere al browser il permesso (facoltativo)\n * su tutti i siti e registra gli script del tema; spegnerla toglie tutto.")


def icona_natale(lato: int) -> bytes:
    """Un fiocco di neve bianco su fondo rosso, disegnato qui."""
    import io
    import math
    from PIL import Image, ImageDraw
    k = 4
    n = lato * k
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 0.22, fill=(200, 16, 46, 255))
    c, r, w = n / 2, n * 0.34, max(2, round(n * 0.07))
    for i in range(6):
        a = math.pi / 2 + i * math.pi / 3
        x, y = c + math.cos(a) * r, c + math.sin(a) * r
        d.line([c, c, x, y], fill=(255, 255, 255, 255), width=w)
        mx, my = c + math.cos(a) * r * 0.62, c + math.sin(a) * r * 0.62
        for lato_barba in (0.8, -0.8):
            d.line([mx, my, mx + math.cos(a + lato_barba) * r * 0.32, my + math.sin(a + lato_barba) * r * 0.32], fill=(255, 255, 255, 255), width=max(2, w - 2))
    d.ellipse([c - w, c - w, c + w, c + w], fill=(255, 255, 255, 255))
    uscita = io.BytesIO()
    img.resize((lato, lato), Image.LANCZOS).save(uscita, format="PNG", optimize=True)
    return uscita.getvalue()


def file_natale() -> dict:
    html = '<div class="barretta"><button type="button" aria-pressed="true">' + ICONA_FIOCCO + "</button></div>"
    attesi = {
        "manifest.json": json.dumps(NATALE_MANIFEST, ensure_ascii=False, indent=2) + "\n",
        "sfondo.js": NATALE_SFONDO,
        "prepara.js": (NATALE_PREPARA.replace("__HTML__", json.dumps(html)).replace("__STILE__", json.dumps(NATALE_STILE))),
        "natale.js": (RADICE / "web/static/natale.js").read_text(encoding="utf-8"),
        "pagina.css": NATALE_PAGINA_CSS,
        "opzioni.html": OPZIONI_HTML.replace("<title>Page Brawl</title>", "<title>Page Snow</title>"),
        "opzioni.css": OPZIONI_CSS, "opzioni.js": NATALE_OPZIONI_JS,
    }
    for lingua, testi in NATALE_MESSAGGI.items():
        if set(testi) != set(NATALE_MESSAGGI["en"]):
            raise SystemExit(f"messaggi di Natale {lingua}: chiavi diverse dall'inglese")
        if len(testi["descrizione"]) > 132:
            raise SystemExit(f"descrizione di Natale {lingua} troppo lunga per lo store: {len(testi['descrizione'])} caratteri")
        messaggi = {"nome": {"message": NATALE_NOME}}
        messaggi.update({chiave: {"message": testo} for chiave, testo in testi.items()})
        attesi[f"_locales/{lingua}/messages.json"] = json.dumps(messaggi, ensure_ascii=False, indent=2) + "\n"
    return attesi


# Le cartelle che si costruiscono: i file attesi, l'icona, il nome dello zip.
PRODOTTI = {
    "pacchetto": (lambda: file_attesi("pacchetto"), icona, f"page-brawl-{VERSIONE}-prova.zip"),
    "store": (lambda: file_attesi("store"), icona, f"page-brawl-{VERSIONE}-store.zip"),
    "natale": (file_natale, icona_natale, f"page-snow-{NATALE_VERSIONE}.zip"),
}


def main() -> int:
    verifica = "--verifica" in sys.argv
    vecchi = []
    for cartella, (attesi_di, icona_di, _zip) in PRODOTTI.items():
        uscita = QUI / cartella
        attesi = attesi_di()
        if verifica:
            vecchi += [f"{cartella}/{nome}" for nome, testo in attesi.items()
                       if not (uscita / nome).exists() or (uscita / nome).read_text(encoding="utf-8") != testo]
            continue
        for nome, testo in attesi.items():
            (uscita / nome).parent.mkdir(parents=True, exist_ok=True)
            (uscita / nome).write_text(testo, encoding="utf-8")
        (uscita / "icone").mkdir(parents=True, exist_ok=True)
        for lato in (16, 48, 128):
            percorso = uscita / "icone" / f"{lato}.png"
            if not percorso.exists():
                percorso.write_bytes(icona_di(lato))
        print("scritto " + str(uscita))
    if not verifica and premium()["premium"] and not premium()["urlAcquisto"]:
        print("ATTENZIONE: Premium è chiuso ma manca l'indirizzo di acquisto: in store/ le funzioni Premium "
              "non si possono sbloccare. Prima di pubblicare metti url_acquisto in premium.json, "
              "oppure premium_attivo: false per uscire con tutto gratis.")
    if "--zip" in sys.argv and not verifica:
        import zipfile
        (QUI / "zip").mkdir(exist_ok=True)
        for cartella, (_attesi, _icona, nome_zip) in PRODOTTI.items():
            nome = QUI / "zip" / nome_zip
            with zipfile.ZipFile(nome, "w", zipfile.ZIP_DEFLATED) as z:
                # I file stanno alla RADICE dello zip: lo vuole lo store, e così la
                # cartella estratta si carica a mano senza scendere di un livello.
                for f in sorted((QUI / cartella).rglob("*")):
                    if f.is_file():
                        z.write(f, f.relative_to(QUI / cartella).as_posix())
            print("zip " + str(nome))
    if verifica:
        if vecchi:
            print("estensione vecchia: " + ", ".join(vecchi) + " (rigenera con python3 estensione/costruisci.py)")
            return 1
        print("estensioni aggiornate (pacchetto/, store/ e natale/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
