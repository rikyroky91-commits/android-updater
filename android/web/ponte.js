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
  // La grafica scelta nell'app (fps, risoluzione, dettaglio): di serie 60 fps, 75 %, dettaglio medio.
  window.__ringGrafica = {
    fps: [30, 60, 120].indexOf(+dati["pb-fps"]) >= 0 ? +dati["pb-fps"] : 60,
    risoluzione: Math.max(50, Math.min(100, +dati["pb-risoluzione"] || 75)) / 100,
    dettaglio: ["basso", "medio", "alto"].indexOf(dati["pb-dettaglio"]) >= 0 ? dati["pb-dettaglio"] : "medio",
  };
  // LA CLASSIFICA GLOBALE (13/10/2026): la stessa del sito e dell'estensione. Rete solo quando
  // si apre la classifica o si manda il proprio punteggio (nome scelto, punti, round).
  var CLASSIFICA = "https://mobileupdatetracker.duckdns.org/api/corsa";
  window.__pbClassifica = {
    carica: function () {
      return fetch(CLASSIFICA + "/classifica?limite=10", { cache: "no-store", credentials: "omit" })
        .then(function (r) { if (!r.ok) throw r.status; return r.json(); });
    },
    invia: function (dati) {
      return fetch(CLASSIFICA + "/punteggio", { method: "POST", credentials: "omit", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dati) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, d: d }; }); });
    },
  };
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
  // IL PREMIUM (12/10/2026). Il motore sa già chiudere tre gruppi (`__ringPremium.bloccate`): qui li apre o
  // li chiude lo stato che dà l'app (Premium.java). "libero" = in questa build non c'è niente da comprare
  // (APK di prova): niente `__ringPremium`, tutto aperto. Toccare una cosa chiusa apre la scheda del Premium.
  var statoPremium = "libero";
  try { statoPremium = pb && pb.premium ? String(pb.premium()) : "libero"; } catch (e) { statoPremium = "libero"; }
  if (statoPremium !== "libero") {
    var premiumAttivo = statoPremium === "attivo", inAscolto = [];
    window.__ringPremium = {
      bloccate: { guerrieri: true, armi: true, meteo: true },
      attivo: function () { return premiumAttivo; },
      chiedi: function (gruppo) { try { pb.compra(String(gruppo || "")); } catch (e) { /* niente scheda */ } },
      ascolta: function (fn) { inAscolto.push(fn); },
    };
    // Chiamata dall'app quando Google Play conferma (o toglie) l'acquisto, a pagina aperta.
    window.__pbPremium = function (si) {
      premiumAttivo = !!si;
      for (var i = 0; i < inAscolto.length; i++) { try { inAscolto[i](); } catch (e) { /* un ascoltatore rotto non ferma gli altri */ } }
    };
  }
  window.__pbMessaggio = function (messaggio) {
    if (!pb) return;
    try { pb.messaggio(JSON.stringify(messaggio)); } catch (e) { /* niente */ }
  };
})();
