/* Il risultato della ricerca: copia al clic e tendina delle varianti.
 *
 * OGNI DATO SI COPIA CON UN CLIC (10/11/2026). Chi usa questa pagina ne
 * porta via dei pezzi — un codice modello, una build, il nome del SoC —
 * per incollarli in un ticket o in un foglio: selezionare a mano una build
 * di quattordici caratteri senza prendere lo spazio accanto è il gesto
 * più ripetuto e più scomodo del sito.
 *
 * COSA SI COPIA. Ciò che porta `data-copia` (col valore dell'attributo, se
 * c'è: «Android 17» e non «Ultimo Android verificato: Android 17») e, senza
 * doverlo marcare uno per uno nei template, ogni dato dentro il risultato:
 * codici, celle delle tabelle, valori delle specifiche, il nome.
 *
 * COSA NON SI TOCCA. Un clic su un collegamento, un tasto, il titolo di
 * una tendina o un campo fa quello che ha sempre fatto. E chi sta
 * selezionando del testo col mouse non viene interrotto: se alla fine del
 * clic c'è una selezione, non si copia niente.
 *
 * TUTTO PER DELEGA SUL DOCUMENTO, perché il secondo tempo della ricerca
 * sostituisce l'intero risultato (`firmware-in-arrivo.js`): un ascoltatore
 * attaccato ai singoli elementi morirebbe con loro.
 */
(function () {
  "use strict";

  var ZONA = "#risultato-ricerca, .scheda, .completa";
  var DATI = "[data-copia], code, dd, td, th[scope='row'], [data-nome-risultato] h2, " +
             ".misure strong, .cpu-in-evidenza strong, .mercato-codice";
  var INTERATTIVI = "a, button, summary, input, select, textarea, label, [data-non-copiare]";

  function testoDi(el) {
    var esplicito = el.getAttribute("data-copia");
    if (esplicito) return esplicito.trim();
    var copia = el.cloneNode(true);
    // La pastiglia 4G/5G è una qualifica accanto al nome, non il nome.
    Array.prototype.forEach.call(
      copia.querySelectorAll(".pastiglia-rete, .nota, [data-non-copiare]"),
      function (n) { n.remove(); });
    return (copia.textContent || "").replace(/\s+/g, " ").trim();
  }

  function scrivi(testo) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(testo);
    }
    // Pagine non sicure e browser vecchi: il vecchio modo, con un campo.
    return new Promise(function (ok, no) {
      var campo = document.createElement("textarea");
      campo.value = testo;
      campo.setAttribute("readonly", "");
      campo.style.cssText = "position:fixed;top:-100px;opacity:0";
      document.body.appendChild(campo);
      campo.select();
      var fatto = false;
      try { fatto = document.execCommand("copy"); } catch (e) { fatto = false; }
      campo.remove();
      if (fatto) { ok(); } else { no(); }
    });
  }

  var avviso = null, timerAvviso = null;
  function mostraAvviso(testo, riuscito) {
    if (!avviso) {
      avviso = document.createElement("div");
      avviso.className = "avviso-copia";
      avviso.setAttribute("role", "status");
      avviso.setAttribute("aria-live", "polite");
      document.body.appendChild(avviso);
    }
    var corto = testo.length > 60 ? testo.slice(0, 57) + "…" : testo;
    avviso.textContent = (riuscito ? "Copiato: " : "Non sono riuscito a copiare: ") + corto;
    avviso.classList.toggle("fallito", !riuscito);
    avviso.classList.add("visibile");
    clearTimeout(timerAvviso);
    timerAvviso = setTimeout(function () { avviso.classList.remove("visibile"); }, 1800);
  }

  function copia(el) {
    var testo = testoDi(el);
    if (!testo || testo === "—") return;
    scrivi(testo).then(function () {
      el.classList.add("copiato");
      setTimeout(function () { el.classList.remove("copiato"); }, 900);
      mostraAvviso(testo, true);
    }, function () { mostraAvviso(testo, false); });
  }

  // Il riepilogo: una riga per dato, solo quelli che la pagina mostra.
  function riepilogo() {
    var radice = document.getElementById("risultato-ricerca");
    if (!radice) return "";
    function uno(selettore) {
      var el = radice.querySelector(selettore);
      return el ? testoDi(el) : "";
    }
    var righe = [];
    function riga(etichetta, valore) { if (valore && valore !== "—") righe.push(etichetta + ": " + valore); }
    riga("Modello", uno("[data-nome-risultato] h2"));
    riga("Codice modello", uno(".codice-principale"));
    riga("SoC", uno(".cpu-in-evidenza strong"));
    riga("Firmware", uno(".dato-firmware .firmware-versione"));
    Array.prototype.forEach.call(radice.querySelectorAll(".dato-firmware .firmware-voci li"), function (li) {
      var e = li.querySelector(".etichetta"), v = li.querySelector("code");
      if (e && v) riga(testoDi(e), testoDi(v));
    });
    var tac = radice.querySelector(".etichetta-imei code");
    if (tac) riga("TAC", testoDi(tac));
    return righe.join("\n");
  }

  function datoSotto(bersaglio) {
    if (!bersaglio || !bersaglio.closest) return null;
    var el = bersaglio.closest(DATI);
    if (!el || !el.closest(ZONA)) return null;
    // Un collegamento DENTRO il dato (il titolo di una notizia in tabella)
    // resta un collegamento; un dato dentro un collegamento pure.
    var attivo = bersaglio.closest(INTERATTIVI);
    if (attivo && (el.contains(attivo) || attivo.contains(el))) return null;
    return el;
  }

  document.addEventListener("click", function (evento) {
    var tasto = evento.target.closest && evento.target.closest("[data-apri-varianti]");
    if (tasto) {
      var riga = tasto.closest("[data-codice-modello]");
      if (!riga) return;
      var aperte = riga.classList.toggle("varianti-aperte");
      tasto.setAttribute("aria-expanded", aperte ? "true" : "false");
      return;
    }
    var tutto = evento.target.closest && evento.target.closest("[data-riepilogo-risultato]");
    if (tutto) {
      var testo = riepilogo();
      if (!testo) return;
      scrivi(testo).then(function () {
        mostraAvviso(testo.split("\n").length + " righe del riepilogo", true);
      }, function () { mostraAvviso("il riepilogo", false); });
      return;
    }
    var el = datoSotto(evento.target);
    if (!el) return;
    var selezione = window.getSelection && window.getSelection();
    if (selezione && String(selezione).trim()) return;
    copia(el);
  });

  // Da tastiera: i dati marcati `data-copia` con `tabindex` rispondono a
  // Invio e Spazio come un tasto.
  document.addEventListener("keydown", function (evento) {
    if (evento.key !== "Enter" && evento.key !== " ") return;
    var el = evento.target;
    if (!el || !el.matches || !el.matches("[data-copia][tabindex]")) return;
    evento.preventDefault();
    copia(el);
  });
})();
