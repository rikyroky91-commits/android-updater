/* GENERATO da estensione/costruisci.py: non modificare a mano.
 *
 * La pagina delle opzioni: una sola scelta, il tema di Natale acceso da solo
 * su tutti i siti. Accenderla fa chiedere al browser il permesso (facoltativo)
 * su tutti i siti e registra gli script del tema; spegnerla toglie tutto.
 */
(function () {
  "use strict";
  var TUTTI = { origins: ["<all_urls>"] }, ID = "ps-auto";
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
          await chrome.scripting.registerContentScripts([{ id: ID, js: ["prepara.js", "natale.js"], css: ["pagina.css"], matches: ["<all_urls>"], runAt: "document_idle" }]);
        }
        await chrome.storage.local.set({ "ps-sempre": "on" });
      } else {
        if (await registrato()) await chrome.scripting.unregisterContentScripts({ ids: [ID] });
        await chrome.storage.local.set({ "ps-sempre": "off" });
        try { await chrome.permissions.remove(TUTTI); } catch (e) { /* già tolto */ }
      }
    } catch (e) {
      esito.textContent = String((e && e.message) || e);
      await leggi();
    }
  });
  leggi();
})();
