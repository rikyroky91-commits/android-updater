#!/usr/bin/env python3
"""Costruisce l'estensione del browser a partire dai file del sito.

Il ring ha UNA sola sorgente: `web/static/ring.js`, la tendina di
`web/templates/home.html` e il suo stile in `web/static/style.css`. Questo
script li copia in `estensione/pacchetto/` aggiungendo quello che serve a un
browser: il manifest, il service worker che parte al clic sull'icona, e
`prepara.js`, che crea canvas e tendina dentro uno shadow DOM (così lo stile
dei siti non li tocca) prima di far partire il ring.

Uso:
    python3 estensione/costruisci.py            # rigenera pacchetto/
    python3 estensione/costruisci.py --verifica # esce con 1 se pacchetto/ è vecchio

Il test `tests/test_estensione.py` usa `--verifica`: chi cambia il ring e
dimentica di rigenerare l'estensione se ne accorge subito.
"""
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
USCITA = Path(__file__).resolve().parent / "pacchetto"
VERSIONE = "0.1.0"
NOME = "Page Brawl"

MANIFEST = {
    "manifest_version": 3,
    "name": NOME,
    "version": VERSIONE,
    "description": "Un robot e una mela si picchiano sulla pagina che stai guardando: "
                   "prendili col mouse, lanciali, scommetti su chi vince.",
    "action": {"default_title": "Accendi o spegni la lotta su questa pagina"},
    "background": {"service_worker": "sfondo.js"},
    # Il permesso minimo: solo la scheda su cui si clicca l'icona.
    "permissions": ["activeTab", "scripting", "storage"],
    "icons": {"16": "icone/16.png", "48": "icone/48.png", "128": "icone/128.png"},
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
    await chrome.scripting.executeScript({ target: dove, func: (d) => { window.__ringDati = d; }, args: [dati] });
    // Il cursore a manina sopra i lottatori: inserito dall'estensione, così passa anche
    // sui siti con una Content-Security-Policy che vieta gli stili scritti nella pagina.
    await chrome.scripting.insertCSS({ target: dove, css: __STILE_PAGINA__ });
    await chrome.scripting.executeScript({ target: dove, files: ["prepara.js", "ring.js"] });
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
  var memoria = Object.assign({}, window.__ringDati || {});
  memoria["mut-ring"] = "on";                    // chi clicca l'icona vuole la lotta accesa
  window.__ringDeposito = {
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(memoria, k) ? memoria[k] : null; },
    setItem: function (k, v) {
      memoria[k] = String(v);
      if (k === "mut-ring") return;              // acceso/spento vale solo per questa pagina
      try { var o = {}; o[k] = String(v); chrome.storage.local.set(o); } catch (e) { /* resta in memoria */ }
    },
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
  window.__ringEstensione = {
    ospite: ospite,
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


def file_attesi() -> dict:
    html = '<canvas class="tela" data-ring aria-hidden="true"></canvas>\n<div class="ancora">\n  ' + tendina() + "\n</div>" + BARRETTA
    if "style=" in html:
        raise SystemExit("la tendina ha stili in linea: una CSP severa li bloccherebbe")
    prepara = (PREPARA
               .replace("__STILE__", json.dumps(STILE_BASE + stile_tendina(), ensure_ascii=False))
               .replace("__HTML__", json.dumps(html, ensure_ascii=False)))
    return {
        "manifest.json": json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n",
        "sfondo.js": SFONDO.replace("__STILE_PAGINA__", json.dumps(STILE_PAGINA, ensure_ascii=False)),
        "prepara.js": prepara,
        "ring.js": (RADICE / "web/static/ring.js").read_text(encoding="utf-8"),
    }


def main() -> int:
    attesi = file_attesi()
    if "--verifica" in sys.argv:
        vecchi = [nome for nome, testo in attesi.items()
                  if not (USCITA / nome).exists() or (USCITA / nome).read_text(encoding="utf-8") != testo]
        if vecchi:
            print("estensione/pacchetto è vecchio: " + ", ".join(vecchi) + " (rigenera con python3 estensione/costruisci.py)")
            return 1
        print("estensione/pacchetto è aggiornato")
        return 0
    (USCITA / "icone").mkdir(parents=True, exist_ok=True)
    for nome, testo in attesi.items():
        (USCITA / nome).write_text(testo, encoding="utf-8")
    for lato in (16, 48, 128):
        percorso = USCITA / "icone" / f"{lato}.png"
        if not percorso.exists():
            percorso.write_bytes(icona(lato))
    print("scritto " + str(USCITA))
    return 0


if __name__ == "__main__":
    sys.exit(main())
