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
  // al browser.
  //
  // SESSANTA SECONDI, NON TRENTA. Il primo valore l'avevo preso da una
  // misura fatta sul portatile; segnalato dall'utente il 17/08/2026 su
  // un IMEI realme, dove il frammento costa 14 secondi in locale e su
  // Render — macchina condivisa, istanza appena sveglia — supera i
  // trenta. Il risultato era il peggiore possibile: una ricerca che
  // stava per riuscire veniva buttata via, e il ripiego offerto rifà da
  // capo la stessa ricerca, più lenta. Meglio aspettare: il budget del
  // server (dodici secondi per le notizie) è il vero limite, questo è
  // solo la rete di sicurezza per quando non risponde nessuno.
  var scaduto = false;
  var timer = setTimeout(function () {
    scaduto = true;
    ripiego("La ricerca del firmware sta impiegando troppo.");
  }, 60000);

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
      // QUANDO IL MODELLO ARRIVA DA FUORI SI RICARICA LA PAGINA INTERA.
      // In quel caso il primo tempo non sapeva ancora CHE TELEFONO è —
      // il TAC non era in nessun database locale — quindi non c'è solo
      // la riga del firmware da mettere: mancano l'identità, la scheda
      // tecnica e la foto, che stanno fuori da questo blocco. La
      // risposta esterna intanto è stata conservata, quindi la seconda
      // visita è immediata e non ricompra niente.
      // ...MA SOLO SE DA FUORI E' ARRIVATO DAVVERO QUALCOSA. Se il TAC
      // non lo conosce nemmeno l'archivio esterno, la pagina ricaricata
      // e' identica a questa: stessa rotellina, stessa fetch, stessa
      // ricarica. Un ciclo infinito, e ogni giro spende
      // un'interrogazione del piano gratuito. Il server lo dichiara nel
      // frammento; qui si ricarica solo quando c'e' un'identita' nuova
      // da mostrare.
      if (blocco.getAttribute("data-ricarica") === "1" &&
          html.indexOf("data-identita=\"ignota\"") === -1) {
        window.location.reload();
        return;
      }
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
