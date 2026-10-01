/* Le ricerche recenti DI TUTTI (01/10/2026, su richiesta).
 *
 * Il tasto «Recenti» accanto a «Cerca» apre l'elenco degli ultimi telefoni
 * cercati da chiunque abbia aperto il sito, non solo da chi guarda: l'elenco
 * lo tiene il server (`/api/ricerche-recenti`) e lo registra lui, quando una
 * ricerca va a buon fine. Sono nomi di telefoni: mai il testo digitato, mai
 * un IMEI.
 *
 * Lo stesso elenco alimenta il `<datalist>` del campo (freccia giù), che è
 * il modo di tastiera di arrivarci.
 */
(function () {
  "use strict";

  let voci = [];

  function popolaDatalist() {
    document.querySelectorAll("datalist#ricerche-recenti").forEach(function (dl) {
      dl.innerHTML = "";
      voci.forEach(function (voce) {
        const opzione = document.createElement("option");
        opzione.value = voce;
        dl.appendChild(opzione);
      });
    });
  }

  function carica() {
    return fetch("/api/ricerche-recenti", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : { voci: [] }; })
      .then(function (dati) {
        voci = Array.isArray(dati.voci)
          ? dati.voci.filter(function (v) { return typeof v === "string" && v.trim(); })
          : [];
        popolaDatalist();
      })
      .catch(function () { voci = []; });
  }

  function costruisciPannello(modulo, tasto) {
    const pannello = document.createElement("div");
    pannello.id = "pannello-recenti";
    pannello.className = "pannello-recenti";
    pannello.hidden = true;
    pannello.setAttribute("role", "region");
    pannello.setAttribute("aria-label", "Ricerche recenti di tutti");
    modulo.insertAdjacentElement("afterend", pannello);

    function disegna() {
      pannello.innerHTML = "";
      const titolo = document.createElement("p");
      titolo.className = "pannello-recenti-titolo";
      titolo.textContent = "Cercati di recente da tutti";
      pannello.appendChild(titolo);
      if (!voci.length) {
        const vuoto = document.createElement("p");
        vuoto.className = "pannello-recenti-vuoto";
        vuoto.textContent = "Ancora nessuna ricerca: compaiono qui appena qualcuno ne fa una.";
        pannello.appendChild(vuoto);
        return;
      }
      const lista = document.createElement("ul");
      voci.forEach(function (voce) {
        const riga = document.createElement("li");
        const link = document.createElement("a");
        link.href = "/?q=" + encodeURIComponent(voce);
        link.textContent = voce;
        riga.appendChild(link);
        lista.appendChild(riga);
      });
      pannello.appendChild(lista);
    }

    function apri(aperto) {
      if (aperto) {
        disegna();
        // Si aggiorna ogni volta che si apre: altri hanno cercato nel frattempo.
        carica().then(function () { if (!pannello.hidden) disegna(); });
      }
      pannello.hidden = !aperto;
      tasto.setAttribute("aria-expanded", aperto ? "true" : "false");
    }
    tasto.hidden = false;
    tasto.addEventListener("click", function () { apri(pannello.hidden); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !pannello.hidden) { apri(false); tasto.focus(); }
    });
    document.addEventListener("click", function (e) {
      if (pannello.hidden) return;
      if (pannello.contains(e.target) || tasto.contains(e.target)) return;
      apri(false);
    });
  }

  document.querySelectorAll("form.ricerca").forEach(function (modulo) {
    const tasto = modulo.querySelector(".tasto-recenti");
    if (tasto) costruisciPannello(modulo, tasto);
  });
  carica();
})();
