/* Il secondo tempo della ricerca.
 *
 * La pagina arriva con il modello, la scheda tecnica e la foto già
 * pronti — quelle cose si sanno senza toccare la rete — e con una
 * rotellina al posto del firmware, che invece costa fino a dodici
 * secondi. Qui si va a prendere quel pezzo e lo si mette al suo posto.
 *
 * SE QUALCOSA VA STORTO NON SI LASCIA GIRARE LA ROTELLINA. Una rotellina
 * eterna è peggio di un errore: chi guarda non sa se aspettare o
 * ricaricare. In ogni ramo che fallisce si scrive cosa è successo e si
 * offre il collegamento alla pagina fatta tutta dal server.
 */
(function () {
  "use strict";

  var blocco = document.querySelector("[data-firmware-per]");
  if (!blocco) return;

  var query = blocco.getAttribute("data-firmware-per") || "";
  if (!query) return;

  function ripiego(messaggio) {
    var completo = "/?q=" + encodeURIComponent(query) + "&completo=1";
    blocco.innerHTML =
      '<p class="riga-esito">' + messaggio + "</p>" +
      '<p class="nota"><a href="' + completo + '">Riprova caricando tutto insieme →</a></p>';
  }

  // Un tetto anche qui: il server ha il suo, ma se la risposta non
  // arriva proprio (rete caduta, istanza riavviata) nessuno lo applica
  // al browser. Trenta secondi sono oltre il peggio misurato.
  var scaduto = false;
  var timer = setTimeout(function () {
    scaduto = true;
    ripiego("La ricerca del firmware sta impiegando troppo.");
  }, 30000);

  fetch("/ricerca/firmware?q=" + encodeURIComponent(query), {
    headers: { "Accept": "text/html" },
    credentials: "same-origin"
  })
    .then(function (risposta) {
      if (!risposta.ok) throw new Error("HTTP " + risposta.status);
      return risposta.text();
    })
    .then(function (html) {
      if (scaduto) return;
      clearTimeout(timer);
      blocco.innerHTML = html;
      blocco.classList.remove("firmware-in-arrivo");
      blocco.classList.add("firmware-arrivato");
    })
    .catch(function () {
      if (scaduto) return;
      clearTimeout(timer);
      ripiego("Non sono riuscito a recuperare il firmware.");
    });
})();
