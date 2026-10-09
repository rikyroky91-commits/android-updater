/* Il tasto chiaro/scuro nella testata (30/09/2026).
 *
 * Il tema iniziale lo decide lo script in testa a `base.html`, prima
 * del primo disegno; qui si gestisce solo il cambio. La scelta si salva
 * nel browser, e se il browser non lo permette (finestra privata, dati
 * bloccati) il cambio funziona lo stesso per la pagina aperta.
 *
 * Senza una scelta salvata la pagina segue il sistema operativo anche
 * DOPO l'apertura: chi ha il cambio automatico al tramonto lo vede
 * applicato senza ricaricare. Una scelta fatta col tasto invece vince
 * finché non la si cambia di nuovo.
 */
(function () {
  "use strict";

  var radice = document.documentElement;
  var CHIAVE = "mut-tema";

  function salvata() {
    try { return localStorage.getItem(CHIAVE); } catch (e) { return null; }
  }

  function applica(tema) {
    radice.setAttribute("data-tema", tema);
    var tasti = document.querySelectorAll("[data-tema-tasto]");
    for (var i = 0; i < tasti.length; i++) {
      var scuro = tema === "scuro";
      tasti[i].setAttribute("aria-pressed", scuro ? "true" : "false");
      tasti[i].setAttribute("title", scuro ? "Passa al tema chiaro" : "Passa al tema scuro");
    }
    // Chi disegna su canvas (il ring in home) legge i colori una volta
    // sola: gli si dice che sono cambiati.
    try {
      window.dispatchEvent(new CustomEvent("mut:tema", { detail: { tema: tema } }));
    } catch (e) { /* browser molto vecchi: niente evento, niente danno */ }
  }

  function avvia() {
    applica(radice.getAttribute("data-tema") === "scuro" ? "scuro" : "chiaro");
    // La dissolvenza solo dopo il primo disegno: vedi lo stile.
    window.requestAnimationFrame(function () {
      radice.classList.add("tema-in-transizione");
    });

    document.addEventListener("click", function (evento) {
      var tasto = evento.target.closest && evento.target.closest("[data-tema-tasto]");
      if (!tasto) return;
      var nuovo = radice.getAttribute("data-tema") === "scuro" ? "chiaro" : "scuro";
      try { localStorage.setItem(CHIAVE, nuovo); } catch (e) { /* solo per questa pagina */ }
      applica(nuovo);
    });

    if (window.matchMedia) {
      var sistema = window.matchMedia("(prefers-color-scheme: dark)");
      var segui = function (e) {
        var scelta = salvata();
        // (ad Halloween, senza una scelta salvata, si resta sul tema scuro)
        if (scelta !== "scuro" && scelta !== "chiaro" && !radice.classList.contains("halloween")) applica(e.matches ? "scuro" : "chiaro");
      };
      if (sistema.addEventListener) sistema.addEventListener("change", segui);
      else if (sistema.addListener) sistema.addListener(segui);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia);
  else avvia();
})();
