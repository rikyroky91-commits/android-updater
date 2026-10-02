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
VERSIONE = "0.2.0"
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
    "icons": {"16": "icone/16.png", "48": "icone/48.png", "128": "icone/128.png"},
}

# Nome, descrizione breve (al massimo 132 caratteri: è il limite dello store)
# e titolo del tasto, nelle lingue dell'estensione.
MESSAGGI = {
    "en": ("A robot and an apple brawl on the page you are viewing. Grab them, throw them, bet on the winner.",
           "Start or stop the brawl on this page"),
    "it": ("Un robot e una mela si picchiano sulla pagina che stai guardando. Prendili, lanciali, scommetti su chi vince.",
           "Accendi o spegni la lotta su questa pagina"),
    "es": ("Un robot y una manzana se pelean en la página que estás viendo. Agárralos, lánzalos y apuesta por el ganador.",
           "Enciende o apaga la pelea en esta página"),
    "fr": ("Un robot et une pomme se battent sur la page que vous regardez. Attrapez-les, lancez-les, pariez sur le vainqueur.",
           "Lancer ou arrêter le combat sur cette page"),
    "de": ("Ein Roboter und ein Apfel prügeln sich auf der Seite, die du gerade ansiehst. Pack sie, wirf sie, wette auf den Sieger.",
           "Kampf auf dieser Seite starten oder stoppen"),
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
.tasto[data-gioca][aria-pressed="false"] { opacity: .6; }
.tasto[data-gioca][aria-pressed="false"] .omino-taglio { display: none; }
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

BARRETTA = """
  <div class="barretta">
    <button type="button" class="tasto" data-opzioni hidden aria-expanded="false"
            title="Opzioni del combattimento: scommesse, armi, imprevisti">&#129354;</button>
    <button type="button" class="tasto" data-gioca hidden aria-pressed="true" aria-label="Lotte accese o spente"
            title="Spegni le lotte">
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <circle cx="12" cy="5" r="2.6" fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M12 8v7M7 11h10M12 15l-4 6M12 15l4 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <path class="omino-taglio" d="M4 20L20 4" stroke="#d8343f" stroke-width="2.6" stroke-linecap="round"/>
      </svg>
    </button>
  </div>
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
    // Un altro clic sull'icona: spegne e nasconde tutto, o riaccende.
    alterna: function () {
      var tasto = radice.querySelector("[data-gioca]"), acceso = tasto.getAttribute("aria-pressed") === "true";
      if (ospite.style.display === "none") { ospite.style.display = ""; if (!acceso) tasto.click(); }
      else { if (acceso) tasto.click(); ospite.style.display = "none"; }
    },
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
      <p data-premio-cosa>Premium sblocca i super guerrieri con le mosse speciali, le armi e le bombe, il meteo e la gravità.</p>
      <button type="button" class="ring-tasto ring-largo" data-premio-compra>Sblocca Premium</button>__PROVA__
    </section>"""
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
    }
    for lingua, (descrizione, titolo) in MESSAGGI.items():
        if len(descrizione) > 132:
            raise SystemExit(f"descrizione {lingua} troppo lunga per lo store: {len(descrizione)} caratteri")
        messaggi = {"nome": {"message": NOME}, "descrizione": {"message": descrizione}, "titolo": {"message": titolo}}
        attesi[f"_locales/{lingua}/messages.json"] = json.dumps(messaggi, ensure_ascii=False, indent=2) + "\n"
    return attesi


def main() -> int:
    verifica = "--verifica" in sys.argv
    vecchi = []
    for variante in VARIANTI:
        uscita = QUI / variante
        attesi = file_attesi(variante)
        if verifica:
            vecchi += [f"{variante}/{nome}" for nome, testo in attesi.items()
                       if not (uscita / nome).exists() or (uscita / nome).read_text(encoding="utf-8") != testo]
            continue
        for nome, testo in attesi.items():
            (uscita / nome).parent.mkdir(parents=True, exist_ok=True)
            (uscita / nome).write_text(testo, encoding="utf-8")
        (uscita / "icone").mkdir(parents=True, exist_ok=True)
        for lato in (16, 48, 128):
            percorso = uscita / "icone" / f"{lato}.png"
            if not percorso.exists():
                percorso.write_bytes(icona(lato))
        print("scritto " + str(uscita))
    if not verifica and premium()["premium"] and not premium()["urlAcquisto"]:
        print("ATTENZIONE: Premium è chiuso ma manca l'indirizzo di acquisto: in store/ le funzioni Premium "
              "non si possono sbloccare. Prima di pubblicare metti url_acquisto in premium.json, "
              "oppure premium_attivo: false per uscire con tutto gratis.")
    if "--zip" in sys.argv and not verifica:
        import zipfile
        (QUI / "zip").mkdir(exist_ok=True)
        for variante in VARIANTI:
            nome = QUI / "zip" / f"page-brawl-{VERSIONE}-{'prova' if variante == 'pacchetto' else 'store'}.zip"
            with zipfile.ZipFile(nome, "w", zipfile.ZIP_DEFLATED) as z:
                # I file stanno alla RADICE dello zip: lo vuole lo store, e così la
                # cartella estratta si carica a mano senza scendere di un livello.
                for f in sorted((QUI / variante).rglob("*")):
                    if f.is_file():
                        z.write(f, f.relative_to(QUI / variante).as_posix())
            print("zip " + str(nome))
    if verifica:
        if vecchi:
            print("estensione vecchia: " + ", ".join(vecchi) + " (rigenera con python3 estensione/costruisci.py)")
            return 1
        print("estensione aggiornata (pacchetto/ e store/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
