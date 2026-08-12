/* Il tasto ✨ accanto a «Cerca».
 *
 * COSA FA E COSA NON FA. Manda al modello quello che è scritto nella
 * casella e riceve indietro **chiavi di ricerca**, non risposte: ogni
 * proposta diventa un collegamento a una ricerca normale sulle fonti di
 * sempre. Da questa strada non esce mai un dato tecnico — processore,
 * RAM, versione software continuano a venire da dove venivano.
 *
 * Il vincolo non è affidato a questo file né al prompt: il modello sceglie
 * fra candidati che gli passa il server, e quello che propone viene
 * ricontrollato lì contro i cataloghi e scartato se non c'è. Qui si
 * disegna quello che è già stato filtrato.
 */
(function () {
  "use strict";

  const bottone = document.getElementById("btn-ai");
  const esito = document.getElementById("esito-ai");
  const casella = document.getElementById("q");
  if (!bottone || !esito || !casella) return;

  function scrivi(html) {
    esito.innerHTML = html;
    esito.hidden = false;
  }

  function scappa(testo) {
    const nodo = document.createElement("div");
    nodo.textContent = testo;
    return nodo.innerHTML;
  }

  bottone.addEventListener("click", async function () {
    const domanda = casella.value.trim();
    if (!domanda) {
      // Senza niente da interpretare si riporta il cursore nella casella
      // invece di chiamare il modello con una stringa vuota.
      casella.focus();
      return;
    }

    bottone.disabled = true;
    bottone.classList.add("in-corso");
    // UNA ROTELLINA, non un riquadro con dentro «Interpreto…». Una riga
    // di testo che compare sotto il campo sposta la pagina e sembra un
    // messaggio d'errore; la rotellina resta dov'è il pulsante e dice
    // «sto lavorando» senza dire altro.
    scrivi('<p class="in-attesa"><span class="rotella" aria-hidden="true"></span>'
           + '<span>Interpreto la ricerca…</span></p>');

    try {
      const corpo = new FormData();
      corpo.append("q", domanda);
      const risposta = await fetch("/api/interpreta", {
        method: "POST",
        body: corpo
      });
      const dati = await risposta.json();

      // LA RICERCA PARTE DA SOLA, non si ferma su un elenco di link.
      //
      // Prima questo tasto restituiva delle proposte da cliccare: chi
      // cercava «samsung s23» leggeva «forse cercavi S23+ o S23 Ultra» e
      // doveva scegliere — cioè faceva lui il lavoro per cui aveva
      // premuto il tasto. L'AI qui è la ricerca normale POTENZIATA: si
      // prende l'interpretazione migliore e la si cerca davvero.
      //
      // Le altre proposte non si perdono: viaggiano nell'indirizzo, e la
      // pagina del risultato le mostra come alternative insieme a quello
      // che era stato scritto.
      if (dati.proposte && dati.proposte.length) {
        const indirizzo = new URLSearchParams();
        indirizzo.set("q", dati.proposte[0]);
        indirizzo.set("ai", domanda);
        for (const altra of dati.proposte.slice(1, 4)) indirizzo.append("alt", altra);
        if (dati.motivo) indirizzo.set("perche", dati.motivo);
        window.location = "/?" + indirizzo.toString();
        return;                   // la pagina sta cambiando: non si disegna altro
      }

      let html = '<p class="nota">Nessuna interpretazione utile' +
                 (dati.errore ? " — " + scappa(dati.errore) : "") + "</p>";
      // Le proposte scartate sono il termometro del meccanismo: se il
      // modello inizia a proporre telefoni che non esistono nei nostri
      // cataloghi si vede qui, e intanto sono già cadute.
      if (dati.scartate && dati.scartate.length) {
        html += '<p class="nota">Scartate ' + dati.scartate.length +
                " proposte fuori catalogo.</p>";
      }
      scrivi(html);
    } catch (errore) {
      scrivi('<p class="nota">Interpretazione non riuscita: ' +
             "il server non ha risposto.</p>");
    } finally {
      bottone.disabled = false;
      bottone.classList.remove("in-corso");
    }
  });

  // Invio nella casella = ricerca normale. Il tasto ✨ è una scelta
  // esplicita e non deve poter partire per sbaglio.
  casella.addEventListener("input", function () {
    esito.hidden = true;
  });
})();
