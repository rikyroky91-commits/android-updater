/* GENERATO da estensione/costruisci.py: non modificare a mano.
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
  radice.innerHTML = "<button type=\"button\"><svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" aria-hidden=\"true\"><path d=\"M12 3v9\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.4\" stroke-linecap=\"round\"/><path d=\"M7.1 6.3a8 8 0 1 0 9.8 0\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.4\" stroke-linecap=\"round\"/></svg></button>";
  try {
    var foglio = new CSSStyleSheet();
    foglio.replaceSync("\nbutton {\n  width: 48px; height: 48px; border-radius: 50%; border: 1px solid #d4d0c8; background: #ffffff; color: #201e1d;\n  opacity: .75; cursor: pointer; display: grid; place-items: center; padding: 0; box-shadow: 0 6px 18px rgba(0, 0, 0, .18);\n}\nbutton:hover { opacity: 1; border-color: #1f7a5a; color: #1f7a5a; }\n@media (prefers-color-scheme: dark) { button { background: #1c1b1a; color: #ebe9e6; border-color: #3a3835; } }\n");
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
