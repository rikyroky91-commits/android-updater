/* Il ponte fra il ring e l'app Android (12/10/2026).
 *
 * Nell'estensione la memoria dei lottatori sta in `chrome.storage.local` e i
 * messaggi vanno al service worker. Nell'app tutti e due passano dall'oggetto
 * `PB` che il codice Java mette nella pagina:
 *   PB.dati()          la memoria salvata (JSON), letta una volta all'avvio;
 *   PB.salva(json)     una o più chiavi da ricordare;
 *   PB.messaggio(json) { tipo: "opzioni" | "guida" } dalla tendina.
 * `costruisci.py` riscrive `prepara.js` dell'estensione perché chiami
 * `window.__pbSalva` e `window.__pbMessaggio` al posto delle API di Chrome.
 */
(function () {
  "use strict";
  if (window.__ringEstensione) return;
  var pb = window.PB || null;
  var dati = {};
  try { dati = JSON.parse(pb ? pb.dati() : "{}") || {}; } catch (e) { dati = {}; }
  window.__ringDati = dati;
  // Il dizionario delle lingue serve solo alla tendina: la pagina sotto non si traduce.
  window.__lingueSoloDizionario = true;
  // Vita, round, colpo finale e oggetti della corsa li disegna l'app (comandi nativi), non il canvas.
  window.__ringHudEsterno = true;
  // Gli oggetti restano almeno a un decimo dai bordi dello schermo: negli angoli i lottatori si incastravano.
  window.__ringBordoOggetti = 0.1;
  window.__pbSalva = function (oggetto) {
    if (!pb) return;
    try { pb.salva(JSON.stringify(oggetto)); } catch (e) { /* resta in memoria per questa volta */ }
  };
  // LA MISURA DEI LOTTATORI SUL TELEFONO. ring.js li fa grandi in proporzione alla
  // larghezza di un computer (W / 1100, mai sotto 0,8): su un telefono restavano
  // piccoli e sempre uguali. Qui la misura parte dal lato corto dello schermo
  // (400 px = 1) e si sceglie nell'app: piccoli, medi, grandi (`pb-taglia`).
  var TAGLIE = { piccoli: 0.8, medi: 1, grandi: 1.25 };
  var taglia = TAGLIE[dati["pb-taglia"]] || 1;
  window.__pbScala = function (W, H) {
    var lato = Math.min(W, H) || 400;
    return Math.max(0.85, Math.min(1.25, lato / 400)) * taglia;
  };
  window.__pbMessaggio = function (messaggio) {
    if (!pb) return;
    try { pb.messaggio(JSON.stringify(messaggio)); } catch (e) { /* niente */ }
  };
})();
