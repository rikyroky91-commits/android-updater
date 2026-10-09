/* La classifica della corsa infinita (09/10/2026): le due chiamate al server.
 *
 * Stanno qui, in un file a parte caricato solo dal sito, e non in `ring.js`:
 * `ring.js` va anche nell'estensione del browser, che per promessa (e per un
 * test, `tests/test_estensione.py`) non manda niente a nessuno. Il ring usa
 * `window.__ringClassifica` se c'è; nell'estensione non c'è, e la corsa tiene
 * solo il record nel browser.
 */
(function () {
  "use strict";
  window.__ringClassifica = {
    carica: () => fetch("/api/corsa/classifica", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
    invia: (dati) => fetch("/api/corsa/punteggio", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dati),
    }).then((r) => r.json().then((d) => ({ ok: r.ok, d }))),
  };
})();
