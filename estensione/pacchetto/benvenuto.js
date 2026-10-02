/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * La pagina di benvenuto: riempie i testi nella lingua del browser e porta
 * alle opzioni.
 */
(function () {
  "use strict";
  var m = function (chiave) { return chrome.i18n.getMessage(chiave) || chiave; };
  document.querySelectorAll("[data-msg]").forEach(function (el) { el.textContent = m(el.getAttribute("data-msg")); });
  document.title = m("guidaTitolo");
  try { document.documentElement.lang = chrome.i18n.getUILanguage(); } catch (e) { /* resta senza */ }
  document.getElementById("opzioni").addEventListener("click", function () { chrome.runtime.openOptionsPage(); });
})();
