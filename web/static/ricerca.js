/* Feedback visivo sul tasto «Cerca».
 *
 * La ricerca è una navigazione GET vera, non una chiamata AJAX: si preme
 * «Cerca» (o Invio) e il browser carica una pagina nuova. Su una rete
 * lenta, o quando la ricerca live interroga più fonti (vedi
 * `core/sources.py::lookup_model_structured`), passano diversi secondi
 * prima che si veda un cambiamento — e senza nulla che si muova nel
 * frattempo sembra che il tasto non abbia funzionato, non che stia
 * lavorando. Segnalato dall'utente: "voglio un feedback visivo che sta
 * cercando".
 *
 * Stesso trattamento già usato per il tasto ✨ AI in `ai.js`: bottone
 * disabilitato, rotellina, testo che cambia — qui applicato al tasto
 * «Cerca» di ogni form `.ricerca` della pagina (testata e home).
 */
(function () {
  "use strict";

  document.querySelectorAll("form.ricerca").forEach(function (modulo) {
    const campo = modulo.querySelector("input[name='q']");
    const bottone = modulo.querySelector("button[type='submit']");
    if (!campo || !bottone) return;

    const testoOriginale = bottone.innerHTML;

    function ripristina() {
      bottone.disabled = false;
      bottone.classList.remove("in-corso");
      bottone.innerHTML = testoOriginale;
    }

    modulo.addEventListener("submit", function () {
      // Niente da cercare, niente rotellina: si lascia che la pagina
      // gestisca il campo vuoto come già fa (es. `required`, se presente).
      if (!campo.value.trim()) return;
      bottone.disabled = true;
      bottone.classList.add("in-corso");
      bottone.innerHTML =
        '<span class="rotella rotella-chiara" aria-hidden="true"></span>' +
        "<span>Cercando…</span>";
    });

    // BFCACHE: tornando indietro col tasto «Indietro» del browser, la
    // pagina può ripresentarsi esattamente com'era al momento dell'invio
    // — tasto disabilitato e rotellina compresi. Senza questo, la ricerca
    // successiva sembrerebbe bloccata per sempre.
    window.addEventListener("pageshow", ripristina);
  });
})();
