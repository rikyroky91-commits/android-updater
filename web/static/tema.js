/* Il tasto del tema nella testata (30/09/2026; tre posizioni dall'11/11/2026).
 *
 * Il tema iniziale lo decide lo script in testa a `base.html`, prima
 * del primo disegno; qui si gestiscono il cambio e il passare delle ore.
 * La scelta si salva nel browser, e se il browser non lo permette
 * (finestra privata, dati bloccati) il cambio funziona lo stesso per la
 * pagina aperta.
 *
 * IL TEMA DINAMICO (11/11/2026, su richiesta: «un tema dinamico tra
 * chiaro, tramonto e dark notte»). Senza una scelta salvata, o con la
 * scelta «auto», il tema segue il sole di Acireale (lo stesso posto del
 * meteo): chiaro di giorno, tramonto da un'ora prima che il sole cali a
 * quaranta minuti dopo (e nei quaranta minuti attorno all'alba), scuro di
 * notte. Alba e tramonto si calcolano qui, con la formula della NOAA
 * (precisione di un paio di minuti), senza rete. Il cambio avviene da
 * solo mentre la pagina è aperta: si ricontrolla ogni minuto.
 *
 * Il tasto gira fra tre posizioni: auto → chiaro → scuro → auto. Il
 * tramonto è un tema chiaro (`data-tema="chiaro"`) con `data-cielo=
 * "tramonto"` sopra: chi disegna su canvas e guarda solo chiaro/scuro
 * non deve sapere niente di nuovo.
 */
(function () {
  "use strict";

  var radice = document.documentElement;
  var CHIAVE = "mut-tema";
  var LAT = 37.61, LON = 15.16;     // Acireale
  var TITOLI = {
    auto: "Tema automatico (giorno, tramonto, notte): passa al chiaro",
    chiaro: "Tema chiaro: passa allo scuro",
    scuro: "Tema scuro: passa all'automatico"
  };

  function salvata() {
    try { return localStorage.getItem(CHIAVE); } catch (e) { return null; }
  }
  function scelta() {
    var s = salvata();
    return s === "chiaro" || s === "scuro" ? s : "auto";
  }

  // Alba e tramonto ad Acireale, in minuti dalla mezzanotte UTC del giorno di `d`.
  function sole(d) {
    var rad = Math.PI / 180;
    var n = Math.floor((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(d.getUTCFullYear(), 0, 0)) / 864e5);
    var g = 2 * Math.PI / 365 * (n - 1);
    var eq = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
    var dec = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g);
    var lat = LAT * rad;
    var ha = Math.acos(Math.cos(90.833 * rad) / (Math.cos(lat) * Math.cos(dec)) - Math.tan(lat) * Math.tan(dec)) / rad;
    return { alba: 720 - 4 * (LON + ha) - eq, tramonto: 720 - 4 * (LON - ha) - eq };
  }
  // "giorno", "tramonto" o "notte" (il tramonto vale anche per l'alba).
  function fase(d) {
    var s = sole(d), u = d.getUTCHours() * 60 + d.getUTCMinutes();
    if ((u >= s.tramonto - 60 && u <= s.tramonto + 40) || (u >= s.alba - 40 && u <= s.alba + 40)) return "tramonto";
    return u > s.alba && u < s.tramonto ? "giorno" : "notte";
  }

  function applica(modo) {
    var f = modo === "auto" ? fase(new Date()) : null;
    var tema = modo === "auto" ? (f === "notte" ? "scuro" : "chiaro") : modo;
    var prima = radice.getAttribute("data-tema") + "/" + (radice.getAttribute("data-cielo") || "");
    radice.setAttribute("data-tema", tema);
    radice.setAttribute("data-tema-scelta", modo);
    if (f === "tramonto") radice.setAttribute("data-cielo", "tramonto");
    else radice.removeAttribute("data-cielo");
    var tasti = document.querySelectorAll("[data-tema-tasto]");
    for (var i = 0; i < tasti.length; i++) {
      tasti[i].setAttribute("aria-pressed", tema === "scuro" ? "true" : "false");
      tasti[i].setAttribute("title", TITOLI[modo]);
      tasti[i].setAttribute("aria-label", TITOLI[modo]);
    }
    // Chi disegna su canvas (il ring in home) legge i colori una volta
    // sola: gli si dice che sono cambiati.
    if (prima !== tema + "/" + (f === "tramonto" ? "tramonto" : "")) {
      try {
        window.dispatchEvent(new CustomEvent("mut:tema", { detail: { tema: tema, cielo: f === "tramonto" ? "tramonto" : null } }));
      } catch (e) { /* browser molto vecchi: niente evento, niente danno */ }
    }
  }

  function avvia() {
    applica(scelta());
    // La dissolvenza solo dopo il primo disegno: vedi lo stile.
    window.requestAnimationFrame(function () {
      radice.classList.add("tema-in-transizione");
    });

    document.addEventListener("click", function (evento) {
      var tasto = evento.target.closest && evento.target.closest("[data-tema-tasto]");
      if (!tasto) return;
      var ora = radice.getAttribute("data-tema-scelta") || scelta();
      var nuovo = ora === "auto" ? "chiaro" : ora === "chiaro" ? "scuro" : "auto";
      try { localStorage.setItem(CHIAVE, nuovo); } catch (e) { /* solo per questa pagina */ }
      applica(nuovo);
    });

    // Il sole si muove anche a pagina aperta.
    setInterval(function () {
      if ((radice.getAttribute("data-tema-scelta") || "auto") === "auto") applica("auto");
    }, 60000);
  }

  window.__tema = { fase: fase, sole: sole };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia);
  else avvia();
})();
