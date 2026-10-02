/* GENERATO da estensione/costruisci.py: non modificare a mano.
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
  radice.innerHTML = "<div class=\"barretta\"><button type=\"button\" aria-pressed=\"true\"><svg viewBox=\"0 0 24 24\" width=\"20\" height=\"20\" aria-hidden=\"true\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\"><path d=\"M12 2.5v19M3.8 7.2l16.4 9.6M20.2 7.2L3.8 16.8\"/><path d=\"M9.6 4.4L12 6.6l2.4-2.2M9.6 19.6L12 17.4l2.4 2.2M4.2 10.4l3-.8-.8-3M19.8 13.6l-3 .8.8 3M19.8 10.4l-3-.8.8-3M4.2 13.6l3 .8-.8 3\"/></svg></button></div>";
  try {
    var foglio = new CSSStyleSheet();
    foglio.replaceSync("\n*, *::before, *::after { box-sizing: border-box; }\n.natale-tela { position: fixed; top: 0; left: 0; display: block; pointer-events: none; }\n.barretta { position: fixed; right: 12px; bottom: 68px; pointer-events: auto; }\nbutton {\n  width: 44px; height: 44px; border-radius: 50%; border: 1px solid #d4d0c8; background: #ffffff; color: #6b6660;\n  cursor: pointer; display: grid; place-items: center; padding: 0; box-shadow: 0 6px 18px rgba(0, 0, 0, .18); opacity: .8;\n}\nbutton:hover { opacity: 1; }\nbutton[aria-pressed=\"true\"] { background: #c8102e; border-color: #c8102e; color: #ffffff; opacity: 1; }\n@media (prefers-color-scheme: dark) { button { background: #1c1b1a; color: #bdb9b3; border-color: #3a3835; } }\n@media print { :host { display: none; } }\n");
    radice.adoptedStyleSheets = [foglio];
  } catch (e) {
    var stile = document.createElement("style");
    stile.textContent = "\n*, *::before, *::after { box-sizing: border-box; }\n.natale-tela { position: fixed; top: 0; left: 0; display: block; pointer-events: none; }\n.barretta { position: fixed; right: 12px; bottom: 68px; pointer-events: auto; }\nbutton {\n  width: 44px; height: 44px; border-radius: 50%; border: 1px solid #d4d0c8; background: #ffffff; color: #6b6660;\n  cursor: pointer; display: grid; place-items: center; padding: 0; box-shadow: 0 6px 18px rgba(0, 0, 0, .18); opacity: .8;\n}\nbutton:hover { opacity: 1; }\nbutton[aria-pressed=\"true\"] { background: #c8102e; border-color: #c8102e; color: #ffffff; opacity: 1; }\n@media (prefers-color-scheme: dark) { button { background: #1c1b1a; color: #bdb9b3; border-color: #3a3835; } }\n@media print { :host { display: none; } }\n";
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
