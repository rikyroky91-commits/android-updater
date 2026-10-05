/* Il secondo tempo della ricerca.
 *
 * La pagina arriva con il modello, la scheda tecnica e la foto già
 * pronti — quelle cose si sanno senza toccare la rete — e con una
 * rotellina al posto del firmware, che invece costa fino a dodici
 * secondi. Qui si va a prendere il risultato completo.
 *
 * SI SOSTITUISCE TUTTO IL RISULTATO, NON SOLO IL RIQUADRO DEL FIRMWARE.
 * Il primo tempo è una ricerca fatta senza rete, e può arrivare a
 * un'identità diversa da quella definitiva, o a nessuna: cercando
 * «a505» (05/10/2026) restavano in pagina il nome e il firmware del
 * Galaxy A50 senza scheda tecnica, senza foto e senza processore, perché
 * quelli stavano fuori dal riquadro e nessuno li aggiornava. Ora il
 * server manda l'intero risultato e qui lo si mette al posto di quello
 * provvisorio: dopo il secondo tempo la pagina è la stessa che si
 * otterrebbe caricando tutto insieme.
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

  // I parametri della pagina viaggiano con la richiesta: lo striscione
  // dell'AI (`ai`, `perche`, `alt`) e la nota «aggiunto al parco»
  // (`parco`) stanno dentro il risultato, e il server deve poterli
  // ridisegnare. `q` è quello dichiarato dalla pagina, non quello
  // dell'indirizzo: per un IMEI sono la stessa cosa, ma è la pagina a
  // dire qual è la domanda da rifare.
  function indirizzo() {
    var parametri;
    try {
      parametri = new URLSearchParams(window.location.search);
    } catch (e) {
      return "/ricerca/firmware?q=" + encodeURIComponent(query) + "&pagina=1";
    }
    parametri.delete("completo");
    parametri.delete("saved");
    parametri.set("q", query);
    parametri.set("pagina", "1");
    return "/ricerca/firmware?" + parametri.toString();
  }

  // Quale `<details>` è quale, per ritrovarlo dopo la sostituzione: la
  // classe e la posizione fra quelli con la stessa classe.
  function perOgniDettaglio(radice, fai) {
    var contati = {};
    Array.prototype.forEach.call(radice.querySelectorAll("details"), function (d) {
      var classe = d.className || "";
      contati[classe] = (contati[classe] || 0) + 1;
      fai(d, classe + "#" + contati[classe]);
    });
  }

  // Mette il risultato completo al posto di quello provvisorio. Torna
  // false se la risposta non è un risultato intero (per esempio il
  // messaggio «TAC non riconosciuto»): in quel caso vale la strada di
  // prima, che riempie il solo riquadro.
  function sostituisciRisultato(html) {
    var vecchio = document.getElementById("risultato-ricerca");
    if (!vecchio || !document.createElement("template").content) return false;
    var modello = document.createElement("template");
    modello.innerHTML = html;
    var nuovo = modello.content.querySelector("#risultato-ricerca");
    if (!nuovo) return false;

    // Chi nell'attesa ha aperto «Scheda tecnica completa» la ritrova
    // aperta: sostituire la pagina sotto gli occhi di chi la sta
    // leggendo non deve richiuderla.
    var aperti = [];
    perOgniDettaglio(vecchio, function (d, chiave) { if (d.open) aperti.push(chiave); });
    perOgniDettaglio(nuovo, function (d, chiave) {
      if (aperti.indexOf(chiave) !== -1) d.open = true;
    });

    vecchio.replaceWith(nuovo);
    var titolo = nuovo.getAttribute("data-titolo-pagina");
    if (titolo) document.title = titolo;
    return true;
  }

  fetch(indirizzo(), {
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
      if (sostituisciRisultato(html)) return;
      blocco.innerHTML = html;
      var nuovoNome = blocco.querySelector('[data-nome-risultato]');
      var nome = document.querySelector('header[data-nome-risultato]');
      if (nuovoNome && nome && nuovoNome !== nome) {
        nome.replaceWith(nuovoNome);
      }
      blocco.classList.remove("firmware-in-arrivo");
      blocco.classList.add("firmware-arrivato");
    })
    .catch(function () {
      if (scaduto) return;
      clearTimeout(timer);
      ripiego("Non sono riuscito a recuperare il firmware.");
    });
})();
