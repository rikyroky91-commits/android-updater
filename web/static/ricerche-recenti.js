/* Le ultime ricerche, a portata di freccia giù.
 *
 * Richiesto dall'utente: poter riaprire in fretta una ricerca già fatta,
 * premendo la freccia giù nella barra invece di riscriverla da capo.
 *
 * PERCHÉ NEL BROWSER E NON NELL'ARCHIVIO. Non è un dato del progetto —
 * non dice niente su un modello, un firmware, un aggiornamento — è una
 * comodità per chi sta cercando, e cambia da persona a persona: quello
 * che conta è la cronologia DI CHI STA USANDO QUESTO BROWSER ORA, non un
 * elenco condiviso da tutti quelli che aprono il sito. `localStorage`
 * è la scelta giusta per questo motivo, non solo per comodità tecnica.
 *
 * COME COMPARE LA FRECCIA GIÙ. Il campo è collegato a un `<datalist>`
 * (vedi `_ricerca.html`) tramite l'attributo `list`: è il browser stesso
 * a mostrare l'elenco quando il campo ha il fuoco e si preme giù, senza
 * bisogno di disegnare un menu a mano — più affidabile su tastiera e
 * lettore di schermo di un widget scritto qui.
 */
(function () {
  "use strict";

  const CHIAVE = "mut_ricerche_recenti";
  const MASSIMO = 8;

  function leggi() {
    try {
      const grezzo = window.localStorage.getItem(CHIAVE);
      const elenco = grezzo ? JSON.parse(grezzo) : [];
      return Array.isArray(elenco) ? elenco.filter(function (v) {
        return typeof v === "string" && v.trim();
      }) : [];
    } catch (errore) {
      // Storage negato o pieno (modalità privata, per esempio): si
      // riparte senza cronologia invece di far fallire la ricerca.
      return [];
    }
  }

  function scrivi(elenco) {
    try {
      window.localStorage.setItem(CHIAVE, JSON.stringify(elenco));
    } catch (errore) {
      // Stesso ragionamento di `leggi`: un salvataggio fallito non deve
      // interrompere niente, la ricerca vera è già partita.
    }
  }

  function aggiungi(query) {
    const pulita = query.trim();
    if (!pulita) return;
    let elenco = leggi().filter(function (voce) {
      return voce.toLowerCase() !== pulita.toLowerCase();
    });
    elenco.unshift(pulita);
    if (elenco.length > MASSIMO) elenco = elenco.slice(0, MASSIMO);
    scrivi(elenco);
  }

  function popola(datalist) {
    datalist.innerHTML = "";
    leggi().forEach(function (voce) {
      const opzione = document.createElement("option");
      opzione.value = voce;
      datalist.appendChild(opzione);
    });
  }

  // IL TASTO «CANCELLA» SOLO SULLA RICERCA GRANDE (la home). Sulla barra
  // piccola, ripetuta in cima a ogni pagina, un tasto in più ripetuto
  // ovunque sarebbe rumore per un'azione che si fa una volta ogni tanto;
  // sulla home, dove la barra è l'unico contenuto, ha lo spazio ed è
  // dove chi vuole ripulire la cronologia la va a cercare.
  function aggiungiTastoCancella(modulo, datalist) {
    if (!modulo.classList.contains("ricerca-grande")) return;
    if (!leggi().length) return;
    if (modulo.parentNode.querySelector(".ricerche-recenti-cancella")) return;
    const tasto = document.createElement("button");
    tasto.type = "button";
    tasto.className = "ricerche-recenti-cancella link-discreto";
    tasto.textContent = "Cancella le ricerche recenti";
    tasto.addEventListener("click", function () {
      scrivi([]);
      popola(datalist);
      tasto.remove();
    });
    modulo.insertAdjacentElement("afterend", tasto);
  }

  // IL PANNELLO DEI «RECENTI»: un elenco vero, con ogni ricerca cliccabile e
  // una crocetta per toglierla, aperto dal tasto accanto a «Cerca». Il
  // `<datalist>` resta (freccia giù), ma non si vede su telefono e non dice
  // che esiste: questo è il modo visibile di arrivarci.
  function costruisciPannello(modulo, tasto) {
    const pannello = document.createElement("div");
    pannello.id = "pannello-recenti";
    pannello.className = "pannello-recenti";
    pannello.hidden = true;
    pannello.setAttribute("role", "region");
    pannello.setAttribute("aria-label", "Ricerche recenti");
    modulo.insertAdjacentElement("afterend", pannello);

    function disegna() {
      pannello.innerHTML = "";
      const elenco = leggi();
      if (!elenco.length) {
        const vuoto = document.createElement("p");
        vuoto.className = "pannello-recenti-vuoto";
        vuoto.textContent = "Nessuna ricerca recente: compaiono qui appena ne fai una.";
        pannello.appendChild(vuoto);
        return;
      }
      const lista = document.createElement("ul");
      elenco.forEach(function (voce) {
        const riga = document.createElement("li");
        const link = document.createElement("a");
        link.href = "/?q=" + encodeURIComponent(voce);
        link.textContent = voce;
        const togli = document.createElement("button");
        togli.type = "button";
        togli.className = "pannello-recenti-togli";
        togli.setAttribute("aria-label", "Togli «" + voce + "» dai recenti");
        togli.textContent = "\u00d7";
        togli.addEventListener("click", function () {
          scrivi(leggi().filter(function (v) { return v !== voce; }));
          const dl = document.querySelector("datalist#ricerche-recenti");
          if (dl) popola(dl);
          disegna();
        });
        riga.appendChild(link);
        riga.appendChild(togli);
        lista.appendChild(riga);
      });
      pannello.appendChild(lista);
      const svuota = document.createElement("button");
      svuota.type = "button";
      svuota.className = "pannello-recenti-svuota link-discreto";
      svuota.textContent = "Cancella tutte";
      svuota.addEventListener("click", function () {
        scrivi([]);
        document.querySelectorAll("datalist#ricerche-recenti").forEach(popola);
        document.querySelectorAll(".ricerche-recenti-cancella").forEach(function (t) { t.remove(); });
        disegna();
      });
      pannello.appendChild(svuota);
    }

    function apri(aperto) {
      if (aperto) disegna();
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
    const campo = modulo.querySelector("input[name='q']");
    const datalist = modulo.querySelector("datalist#ricerche-recenti");
    if (!campo || !datalist) return;

    popola(datalist);
    aggiungiTastoCancella(modulo, datalist);
    const tastoRecenti = modulo.querySelector(".tasto-recenti");
    if (tastoRecenti) costruisciPannello(modulo, tastoRecenti);

    // Una ricerca arrivata da un link (un suggerimento, un recente, un
    // segnalibro) non passa dall'invio del modulo: il campo però è già
    // compilato dal server, e quella È una ricerca fatta.
    if (campo.value && campo.value.trim()) aggiungi(campo.value);

    // SI SALVA ALL'INVIO, non a ogni carattere digitato: una ricerca
    // scritta e poi cancellata senza premere Invio non è una ricerca
    // fatta, e non deve sporcare la cronologia.
    modulo.addEventListener("submit", function () {
      aggiungi(campo.value);
    });
  });
})();
