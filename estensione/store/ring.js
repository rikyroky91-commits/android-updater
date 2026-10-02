/* I due lottatori della home (30/09/2026, rifatto l'01/10/2026 su richiesta).
 *
 * Un robottino verde e una mela (polpa bianca, contorni e occhi neri),
 * disegnati apposta per questo sito, si picchiano in un ciclo casuale.
 *
 * DALL'01/10/2026 IL RING È TUTTA LA PAGINA:
 *  - si prendono col mouse (o col dito) e si lanciano dove si vuole: la
 *    velocità del lancio è quella del gesto;
 *  - gli elementi della pagina sono corpi solidi: ogni riga di testo, il
 *    campo di ricerca, i tasti, la testata, la striscia dell'ultim'ora.
 *    Ci si sbatte contro, ci si atterra sopra, ci si cammina;
 *  - per raggiungere l'avversario scendono dai bordi e si arrampicano sui
 *    fianchi degli elementi, una mano dopo l'altra.
 *
 * COME SONO FATTI. Ognuno è una bambola di pezza (ragdoll) con integrazione
 * di Verlet: undici punti legati da aste di lunghezza fissa, con gravità e
 * attrito. Finché il lottatore è sveglio dei «muscoli» tirano ogni punto
 * verso la posa del momento (guardia, pugno, calcio, arrampicata…); da
 * K.O., o mentre lo si tiene in mano, i muscoli si spengono e il corpo
 * penzola o crolla da solo. Nessuna animazione è disegnata a mano.
 *
 * LE STESSE ATTENZIONI DELLA TRAMA DI SFONDO (`rete.js`):
 *  - il ciclo si ferma quando la scheda passa in secondo piano;
 *  - disegna a 30 fotogrammi al secondo, non 60;
 *  - chi ha chiesto meno movimento al sistema operativo vede i due
 *    lottatori fermi in guardia, e la striscia delle notizie ferma.
 *
 * Il canvas copre la finestra ma non intercetta i clic (`pointer-events:
 * none`): la pagina sotto resta usabile. La presa si fa ascoltando il
 * puntatore sulla finestra e controllando se sotto c'è un lottatore; solo
 * in quel caso il gesto viene trattenuto.
 */
(function () {
  "use strict";

  // DI CHI SONO I PEZZI DEL RING (02/10/2026). Sul sito stanno nella pagina.
  // Nell'estensione del browser (`estensione/`) stanno in uno shadow DOM a
  // parte, così lo stile dei siti non li tocca: l'estensione lo dichiara in
  // `window.__ringRadice`, e mette in `window.__ringDeposito` una memoria
  // sua (uguale su tutti i siti) al posto di `localStorage`.
  const mio = window.__ringRadice || document;
  const ospite = window.__ringRadice ? window.__ringRadice.host : null;
  let deposito = null;
  try { deposito = window.__ringDeposito || window.localStorage; } catch (errore) { /* niente memoria */ }

  // PREMIUM (02/10/2026). Sul sito è tutto libero. L'estensione può dichiarare
  // in `window.__ringPremium` quali gruppi di funzioni sono a pagamento
  // (`bloccate`: guerrieri, armi, meteo), se sono già sbloccate (`attivo()`) e
  // cosa fare quando si tocca una funzione bloccata (`chiedi(gruppo)`).
  const premio = window.__ringPremium || null;
  const libero = (gruppo) => !premio || premio.attivo() || !premio.bloccate[gruppo];
  function concesso(gruppo) {
    if (libero(gruppo)) return true;
    try { premio.chiedi(gruppo); } catch (errore) { /* resta bloccata */ }
    return false;
  }
  const ARMI_PREMIO = { pistola: 1, spada: 1, bomba: 1, duo: 1 };
  const MOSSE_PREMIO = { onda: 1, carica: 1, teletrasporto: 1, sfera: 1, disco: 1, lampo: 1, barriera: 1, autodistruzione: 1, telecinesi: 1,
                         trasforma: 1, dardi: 1, gelo: 1, rimpicciolisci: 1, fulmine: 1, levita: 1, scudo: 1, raggio: 1, sparizione: 1,
                         "scatto-lama": 1, "lancio-lama": 1, duello: 1 };
  // A quale gruppo a pagamento appartiene un tasto della tendina (o nessuno).
  function gruppoDi(tasto) {
    const metti = tasto.getAttribute("data-metti"), colpo = tasto.getAttribute("data-colpo");
    if (metti) return ARMI_PREMIO[metti] ? "armi" : null;
    if (colpo) return MOSSE_PREMIO[colpo] ? "guerrieri" : colpo.indexOf("esplodi-") === 0 ? "armi" : null;
    if (tasto.hasAttribute("data-anime") || tasto.hasAttribute("data-stile")) return "guerrieri";
    if (tasto.hasAttribute("data-imprevisto") || tasto.hasAttribute("data-gravita")) return "meteo";
    return null;
  }

  const tela = mio.querySelector("[data-ring]");
  const scorre = mio.querySelector("[data-scorre]");
  const orologio = mio.querySelector("[data-orologio]");
  const barra = mio.querySelector(".ultimora-barra");

  // --- L'orologio della striscia, come in TV ---------------------------
  function aggiornaOra() {
    if (!orologio) return;
    const ora = new Date();
    orologio.textContent = String(ora.getHours()).padStart(2, "0") + ":" +
      String(ora.getMinutes()).padStart(2, "0");
  }
  aggiornaOra();
  setInterval(aggiornaOra, 15000);

  // --- Velocità costante dello scorrimento -----------------------------
  function tara() {
    if (!scorre) return;
    const meta = scorre.scrollWidth / 2;
    if (meta > 0) scorre.style.setProperty("--durata", Math.max(20, meta / 75) + "s");
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(tara);
  window.addEventListener("load", tara);

  if (!tela || !tela.getContext) return;
  const ctx = tela.getContext("2d");
  const preferisceFermo = !!(window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  // IL TASTO CHE SPEGNE TUTTO IL LIVELLO DELLE LOTTE (01/10/2026, su
  // richiesta): lascia la pagina pulita, con le sole notizie. La scelta resta
  // nel browser. Chi ha ridotto i movimenti nel telefono lo trova spento.
  let scelta = null;
  try { scelta = deposito.getItem("mut-ring"); } catch (errore) { /* niente memoria */ }
  let fermo = scelta === "off" || (scelta !== "on" && preferisceFermo);

  // --- I tasti della striscia: pausa delle notizie e lotte accese/spente ---
  const tastoPausa = mio.querySelector("[data-pausa]");
  if (tastoPausa && barra) {
    tastoPausa.hidden = false;
    tastoPausa.addEventListener("click", () => {
      const inPausa = barra.classList.toggle("in-pausa");
      tastoPausa.setAttribute("aria-pressed", inPausa ? "true" : "false");
    });
  }
  const tastoGioca = mio.querySelector("[data-gioca]");
  function aggiornaTastoGioca() {
    if (!tastoGioca) return;
    tastoGioca.setAttribute("aria-pressed", fermo ? "false" : "true");
    tastoGioca.title = fermo ? "Accendi le lotte" : ospite ? "Spegni le lotte" : "Spegni le lotte e lascia solo le notizie";
  }
  if (tastoGioca) {
    tastoGioca.hidden = false;
    aggiornaTastoGioca();
    tastoGioca.addEventListener("click", () => {
      fermo = !fermo;
      try { deposito.setItem("mut-ring", fermo ? "off" : "on"); } catch (errore) { /* pazienza */ }
      aggiornaTastoGioca();
      if (fermo) spegni(); else accendi();
    });
  }

  // --- Stato del mondo -------------------------------------------------
  let W = 0, H = 0, S = 1, pavimento = 0;
  let ostacoli = [];
  let lottatori = [];
  let scritte = [];
  let punteggio = { robot: 0, mela: 0 };
  let inchiostro = "#201e1d";
  let accento = "#ec3013";
  let passi = 0;
  // Le novità dell'01/10/2026 (telefoni, eventi, particelle, costumi).
  let telefoni = [], particelle = [], evento = null;
  // Le novità del 02/10/2026: le creature dei barattoli, le nubi dei fumogeni
  // e il gran finale di chi arriva a dieci.
  let creature = [], nubi = [], finale = null;
  // Nell'estensione non piovono telefoni (su richiesta): solo fumogeni,
  // barattoli e, con Premium, le armi. Sul sito i telefoni restano.
  const senzaTelefoni = !!ospite;
  let fermoColpo = 0, scossa = 0, moltG = 1, ritmo = 1, daSpawnare = 0;
  let prossimoEvento = 700, prossimoTelefono = 360;
  let costume = "nessuno", tavolozza = null;
  // IL TEMPO DI GARA (01/10/2026, su richiesta): il primo minuto è
  // tranquillo (niente eventi né jetpack, solo telefoni e orologi, al massimo
  // due in giro) perché chi apre il sito deve poterlo usare. Dopo 60 secondi
  // si sblocca l'arsenale: tablet, portatili, eventi, jetpack, il pieghevole
  // della mela. Dopo 70 arrivano anche pistole e spade (da cartone animato).
  const CALMA = 60 * 60, ARMI = 70 * 60;
  let tempo = 0, prossimaArma = 0, prossimoDuo = 0, prossimaBombaRobot = 0, proiettili = [], pezzi = [];
  // Gli imprevisti scelti a mano dalla tendina (o arrivati a sorpresa).
  let acquazzone = false, uragano = null, gravitaScelta = 1, sorprese = true;
  // Il tema natalizio è di tutto il sito (tasto nella testata, `natale.js`):
  // ai lottatori dà il cappellino rosso e le palle di neve.
  const radiceNatale = document.documentElement;
  let natale = !!(radiceNatale && radiceNatale.classList && radiceNatale.classList.contains && radiceNatale.classList.contains("natale"));
  window.addEventListener("mut:natale", (e) => { natale = !!(e && e.detail && e.detail.acceso); });
  let arti = [], macchie = [], cumulo = 0, danniBordi = [], testataBasso = 0;
  // Gravità: verso il basso (1) o verso il tetto (-1, «sottosopra»).
  let verso = 1;
  // Barre della vita e modalità «super guerrieri»: si scelgono dalla tendina.
  let barreVita = false, anime = false;
  // LO STILE dei lottatori (02/10/2026): "" i soliti picchiatori, oppure
  // super guerrieri, maghi, duellanti. `anime` resta il motore a energia
  // (volo, onde, teletrasporti): lo usano i guerrieri e i maghi.
  const STILI = ["guerrieri", "maghi", "lame"];
  let stile = "";
  try {
    barreVita = deposito.getItem("mut-ring-barre") === "on";
    const salvato = deposito.getItem("mut-ring-stile");
    stile = STILI.indexOf(salvato) >= 0 ? salvato : (deposito.getItem("mut-ring-anime") === "on" ? "guerrieri" : "");
  } catch (errore) { /* restano spente */ }
  if (!libero("guerrieri")) stile = "";
  anime = stile === "guerrieri" || stile === "maghi";
  const maghi = () => stile === "maghi", lame = () => stile === "lame";
  // Con uno stile acceso in campo non ci sono più il robot e la mela, ma due
  // personaggi inventati per quel tema (vedi ASPETTI): hanno un corpo umano
  // sullo scheletro del robot. `tipo` resta il lato: "robot" a sinistra,
  // "mela" a destra (punteggio, scommesse, quel che hanno imparato).
  const eMela = (f) => f.tipo === "mela" && !stile, eRobot = (f) => f.tipo === "robot" && !stile;
  // Schizzi e arti staccati: si possono spegnere dalla tendina.
  let cruento = true;
  try { cruento = deposito.getItem("mut-ring-cruento") !== "off"; } catch (errore) { /* resta acceso */ }
  // I danni alla striscia delle notizie (crepe, buchi), e il colore dello sfondo.
  let danni = [], sfondo = "#f2f2f2", barraAlta = 44;

  const caso = (a, b) => a + Math.random() * (b - a);
  const scegli = (voci) => {
    let totale = 0;
    for (const v of voci) totale += v[0];
    let r = Math.random() * totale;
    for (const v of voci) { if ((r -= v[0]) <= 0) return v[1]; }
    return voci[voci.length - 1][1];
  };

  // --- Il cervello: ogni lottatore impara dai colpi ----------------------
  // Ogni mossa ha un peso che sale quando va a segno (o quando para) e scende
  // quando si prende un colpo mentre la si fa o quando viene parata. Chi viene
  // colpito impara a pararsi e a schivare di più. I pesi rientrano piano verso
  // 1, così la varietà non si perde. L'esperienza dà il livello, e ogni livello
  // sblocca qualcosa: 2 serie di colpi, 3 contrattacco dopo una parata, 4
  // sfida chi vola, 5 più telefoni. Resta nel browser (nessun dato al server).
  const CHIAVE_CERVELLO = "mut-ring-cervello";
  const MOSSE = ["pugno", "diretto", "montante", "calcio", "para", "schiva", "salto", "provoca", "indietro", "presa"];
  const LIVELLO_MAX = 8;
  let cervello = {};
  function pulisciCervello(grezzo) {
    const puliti = {};
    for (const tipo of ["robot", "mela"]) {
      const c = grezzo && typeof grezzo === "object" ? grezzo[tipo] : null;
      const pesi = {};
      for (const m of MOSSE) {
        const v = c && c.pesi ? Number(c.pesi[m]) : 1;
        pesi[m] = Number.isFinite(v) ? Math.max(0.4, Math.min(2.6, v)) : 1;
      }
      const exp = c ? Number(c.exp) : 0;
      puliti[tipo] = { exp: Number.isFinite(exp) ? Math.max(0, Math.min(5000, Math.floor(exp))) : 0, pesi };
    }
    return puliti;
  }
  try { cervello = pulisciCervello(JSON.parse(deposito.getItem(CHIAVE_CERVELLO) || "null")); }
  catch (errore) { cervello = pulisciCervello(null); }
  let daSalvare = 0;
  function salvaCervello(subito) {
    if (!subito && ++daSalvare < 10) return;
    daSalvare = 0;
    try { deposito.setItem(CHIAVE_CERVELLO, JSON.stringify(cervello)); } catch (errore) { /* pazienza */ }
  }
  const livelloDi = (tipo) => (cervello[tipo] ? Math.min(LIVELLO_MAX, Math.floor(Math.sqrt(cervello[tipo].exp / 3))) : 0);
  const pesoMossa = (f, mossa) => (cervello[f.tipo] && cervello[f.tipo].pesi[mossa]) || 1;
  function impara(f, mossa, esito, esperienza) {
    const c = f && cervello[f.tipo];
    if (!c || MOSSE.indexOf(mossa) < 0) return;
    const prima = livelloDi(f.tipo);
    for (const m of MOSSE) c.pesi[m] = 1 + (c.pesi[m] - 1) * 0.994;
    c.pesi[mossa] = Math.max(0.4, Math.min(2.6, c.pesi[mossa] * (esito > 0 ? 1.08 : 0.94)));
    if ((mossa === "para" || mossa === "schiva") && c.pesi[mossa] > 1.8) c.pesi[mossa] = 1.8;
    c.exp = Math.min(5000, c.exp + (esperienza || 0));
    const dopo = livelloDi(f.tipo);
    if (dopo > prima) {
      // Livello nuovo: scintille verdi e un po' più di fiuto.
      f.furbo = Math.min(2, f.furbo + 0.08);
      const b = f.p && f.p.testa;
      if (b) scintille(b.x, b.y - 10 * S, 14, "#5fe08a");
      salvaCervello(true);
    } else salvaCervello(false);
  }
  // Il carattere di ogni round: casuale, ma chi ha esperienza è più furbo.
  function nuovoCarattere(f) {
    const l = livelloDi(f.tipo);
    f.aggr = caso(0.75, 1.3) + 0.02 * l;
    f.furbo = Math.min(2, caso(0.6, 1.4) + 0.07 * l);
  }

  function leggiColori() {
    const stile = getComputedStyle(document.documentElement);
    inchiostro = (stile.getPropertyValue("--ink") || "").trim() || "#201e1d";
    accento = (stile.getPropertyValue("--accent") || "").trim() || "#ec3013";
    try {
      const c = document.body && getComputedStyle(document.body).backgroundColor;
      if (c && c !== "rgba(0, 0, 0, 0)" && c !== "transparent") sfondo = c;
    } catch (errore) { /* resta il grigio chiaro */ }
  }

  // --- Gli elementi della pagina come corpi solidi ----------------------
  // Le righe di testo una per una (non il riquadro del paragrafo, che è
  // largo quanto la colonna anche quando la riga è corta), più i
  // controlli — campi, tasti, immagini — e la testata intera. Tutto in
  // coordinate della finestra, come il canvas.
  const SOLIDI = "input, button, select, textarea, img";
  const RIGA_MIN = 32;
  const FUORI = ".ultimora, script, style, canvas, noscript, datalist, [hidden], .sr-only";

  function riquadroUtile(r) {
    return r && r.width >= 10 && r.height >= 6 && r.height < 240 &&
      r.bottom > -40 && r.top < H + 40 && r.right > 0 && r.left < W;
  }

  function rileva() {
    const lista = [];
    const aggiungi = (r) => {
      if (riquadroUtile(r)) lista.push({ l: r.left, t: r.top, r: r.right, b: r.bottom });
    };
    const testata = document.querySelector(".testata");
    if (testata && testata.getBoundingClientRect) {
      const rt = testata.getBoundingClientRect();
      aggiungi(rt);
      testataBasso = rt.bottom > 0 && rt.bottom < H * 0.3 ? rt.bottom : 0;
    }

    const radice = document.body;
    if (radice && radice.querySelectorAll) {
      for (const el of radice.querySelectorAll(SOLIDI)) {
        if (el.closest && (el.closest(FUORI) || (testata && el.closest(".testata")))) continue;
        aggiungi(el.getBoundingClientRect());
      }
    }
    if (radice && document.createTreeWalker && document.createRange) {
      const giro = document.createTreeWalker(radice, 4 /* NodeFilter.SHOW_TEXT */);
      const intervallo = document.createRange();
      let nodo;
      while ((nodo = giro.nextNode()) && lista.length < 220) {
        if (!nodo.nodeValue || !nodo.nodeValue.trim()) continue;
        const padre = nodo.parentElement;
        if (!padre || padre.closest(FUORI) || padre.closest(SOLIDI) ||
            (testata && padre.closest(".testata"))) continue;
        intervallo.selectNodeContents(nodo);
        // Le scritte piccole (note, didascalie, righe di testo corrente) non
        // sono solide: i lottatori ci si incastravano di continuo.
        for (const r of intervallo.getClientRects()) if (r.height >= RIGA_MIN) aggiungi(r);
      }
    }
    // Le righe vicine sulla stessa linea diventano un pezzo solo: meno
    // calcoli e niente fessure fra una parola e l'altra dove incastrarsi.
    lista.sort((a, b) => a.t - b.t || a.l - b.l);
    const uniti = [];
    for (const o of lista) {
      const u = uniti[uniti.length - 1];
      if (u && Math.abs(u.t - o.t) < 4 && Math.abs(u.b - o.b) < 4 && o.l <= u.r + 10) {
        u.r = Math.max(u.r, o.r); u.l = Math.min(u.l, o.l);
      } else uniti.push(Object.assign({}, o));
    }
    // E le righe dello stesso paragrafo diventano un blocco: fra una riga e
    // l'altra ci sono tre pixel, e un lottatore in piedi su una riga si
    // ritrovava col corpo dentro quella di sopra.
    const blocchi = [];
    for (const o of uniti) {
      const sopra = blocchi.find((u) => o.t - u.b < 9 && o.t >= u.t &&
        Math.min(u.r, o.r) - Math.max(u.l, o.l) > 0.3 * Math.min(u.r - u.l, o.r - o.l));
      if (sopra) {
        sopra.l = Math.min(sopra.l, o.l); sopra.r = Math.max(sopra.r, o.r); sopra.b = Math.max(sopra.b, o.b);
      } else blocchi.push(o);
    }
    ostacoli = blocchi.slice(0, 160);
    pavimento = barra && barra.getBoundingClientRect ? barra.getBoundingClientRect().top : H;
    if (barra && barra.getBoundingClientRect) barraAlta = barra.getBoundingClientRect().height || 44;
    if (!(pavimento > 0)) pavimento = H;
  }

  // --- Il corpo --------------------------------------------------------
  // Altezze in unità «a scala 1» sopra il punto d'appoggio; dx verso la faccia.
  const SCHELETRO = {
    testa: [62, 2, 7], collo: [50, 1, 3], bacino: [28, 0, 4],
    gomitoA: [42, 8, 2], manoA: [50, 13, 3], gomitoD: [41, 3, 2], manoD: [49, 8, 3],
    ginocchioA: [14, 6, 2], piedeA: [0, 8, 2.5], ginocchioD: [14, -3, 2], piedeD: [0, -8, 2.5],
  };
  const ASTE = [
    ["testa", "collo"], ["collo", "bacino"],
    ["collo", "gomitoA"], ["gomitoA", "manoA"], ["collo", "gomitoD"], ["gomitoD", "manoD"],
    ["bacino", "ginocchioA"], ["ginocchioA", "piedeA"], ["bacino", "ginocchioD"], ["ginocchioD", "piedeD"],
    // Due aste «di sostegno» invisibili: tengono la testa sopra il bacino e
    // le ginocchia separate, così la bambola non si accartoccia.
    ["testa", "bacino"], ["ginocchioA", "ginocchioD"],
  ];
  const TIRO = {
    testa: 0.16, collo: 0.2, bacino: 0.2, gomitoA: 0.18, manoA: 0.26,
    gomitoD: 0.18, manoD: 0.24, ginocchioA: 0.2, piedeA: 0.26, ginocchioD: 0.2, piedeD: 0.26,
  };

  // Le mani della mela stanno più in basso di quelle del robot: appena sotto
  // gli occhi, dove una mela ha il «petto», non all'altezza della testa.
  const SPALLA_MELA = ["gomitoA", "manoA", "gomitoD", "manoD"];
  const ABBASSA_MELA = 6;
  // A riposo le mani della mela stanno ai FIANCHI del frutto, una davanti e
  // una dietro, non sulla faccia.
  const LATI_MELA = { gomitoA: 19, manoA: 23, gomitoD: -18, manoD: -22 };
  // Il frutto è largo: i punti del busto hanno un raggio più grande, così
  // urti e colpi coincidono con quello che si vede.
  const RAGGI_MELA = { testa: 6, collo: 10, bacino: 8 };
  let scheletroMela = null;
  function scheletro(tipo) {
    if (tipo !== "mela" || stile) return SCHELETRO;
    if (scheletroMela) return scheletroMela;
    const q = {};
    for (const nome in SCHELETRO) {
      q[nome] = SCHELETRO[nome].slice();
      if (nome in LATI_MELA) { q[nome][1] = LATI_MELA[nome]; }
      if (nome in RAGGI_MELA) { q[nome][2] = RAGGI_MELA[nome]; }
    }
    return (scheletroMela = q);
  }

  function crea(tipo, x, dir, base) {
    if (base === undefined) base = pavimento;
    const f = {
      tipo, dir, cx: x, base, supporto: null, p: {}, aste: [],
      forza: 1, ko: 0, rialzo: 0, stordito: 0, danni: 0, soglia: Math.round(caso(3, 6)),
      azione: null, t: 0, durata: 0, colpito: false, pensa: caso(20, 60), meta: x,
      passo: 0, dolore: 0, preso: null, scalata: null, inVolo: false, botta: 0, fantasma: false,
      aggr: caso(0.75, 1.3), furbo: caso(0.6, 1.4), furia: 0, tel: null, prendiTel: null, polv: 0,
      combo: 0, jet: 0, volaY: 0, caos: 0, giro: 0, rot: 0, ix: 0, iy: 0, fiamma: 0,
      arma: null, colpiArma: 0, tiene: null, tenuto: null, mossaPresa: null,
      paracadute: 0, para: 0, scendeApposta: 0, daBallare: false, ballo: null, esploso: null,
      segni: [], staccati: {}, palla: false, uraganoCd: 0,
      ki: 0, potenziato: 0, onda: null, koVero: false, vitaVista: 1, vitaScia: 1,
      accecato: 0, cratere: null, sfera: null,
      forma: 0, gelato: 0, ghiaccio: null, piccolo: 0, scala: 1, lama: null, caduta: null, daScatto: null,
      colpoMano: 0, lanciato: 0, volo: false, scatto: 0, bersaglio: null, recupero: 0, insegui: 0, catena: 0, vel: null, morsi: [], taglio: null,
    };
    f.furbo = Math.min(2, f.furbo + 0.07 * livelloDi(tipo));
    const sch = scheletro(tipo);
    for (const nome in sch) {
      let [h, dx, r] = sch[nome];
      if (tipo === "mela" && !stile && SPALLA_MELA.indexOf(nome) >= 0) h -= ABBASSA_MELA;
      const px = x + dx * dir * S, py = base - h * S - 2 * S;
      f.p[nome] = { x: px, y: py, ox: px, oy: py, r: r * S };
    }
    for (const [a, b] of ASTE) {
      const pa = f.p[a], pb = f.p[b];
      f.aste.push([pa, pb, Math.hypot(pa.x - pb.x, pa.y - pb.y)]);
    }
    return f;
  }

  function dimensiona() {
    const rapporto = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth || tela.clientWidth; H = window.innerHeight || tela.clientHeight;
    tela.width = Math.floor(W * rapporto); tela.height = Math.floor(H * rapporto);
    // DIMENSIONE IN PIXEL ESPLICITI, non `100vh`: su iPhone `100vh` è l'altezza
    // con le barre del browser ritirate, più alta dell'area visibile, e il
    // canvas veniva stirato — gli omini disegnati più in basso di dove la
    // fisica li metteva, quindi niente presa e niente urti (01/10/2026).
    if (tela.style) { tela.style.width = W + "px"; tela.style.height = H + "px"; }
    ctx.setTransform(rapporto, 0, 0, rapporto, 0, 0);
    S = Math.max(0.8, Math.min(1.2, W / 1100));
  }

  function avvia() {
    dimensiona();
    rileva();
    const centro = W / 2, scarto = Math.min(90 * S, W * 0.18);
    // PARTENZA SUL CAMPO DI RICERCA (01/10/2026, su richiesta): il ring
    // iniziale è il bordo alto della barra. Se i due ne escono cadono sulla
    // pagina e, prima o poi, sulle notizie in fondo.
    let cx0 = centro, base0 = pavimento;
    const campo = document.querySelector && document.querySelector(".ricerca-grande input");
    const rc = campo && campo.getBoundingClientRect ? campo.getBoundingClientRect() : null;
    if (rc && rc.width > 200 && rc.top > 60 && rc.top < pavimento - 90 && rc.left < W) {
      cx0 = (rc.left + rc.right) / 2; base0 = rc.top;
    }
    lottatori = [crea("robot", cx0 - scarto, 1, base0), crea("mela", cx0 + scarto, -1, base0)];
    if (lame()) for (const f of lottatori) accendiLama(f);
    fulmini = []; duello = 0;
    danni = [];
    scritte = []; telefoni = []; particelle = []; evento = null;
    creature = []; nubi = []; finale = null;
    moltG = 1; ritmo = 1; daSpawnare = 0; fermoColpo = 0; scossa = 0;
    tempo = 0; proiettili = []; pezzi = []; arti = []; macchie = []; cumulo = 0; danniBordi = [];
    prossimoEvento = CALMA + Math.round(caso(120, 600));
    prossimoTelefono = 360; prossimaArma = ARMI + Math.round(caso(0, 240));
    prossimoDuo = CALMA + Math.round(caso(400, 1500));
    prossimaBombaRobot = CALMA + Math.round(caso(900, 2100));
    // Il robot si presenta con un costume e un colore a caso a ogni caricamento.
    costume = scegli([[2, "nessuno"], [2, "ninja"], [2, "cuoco"], [2, "astronauta"],
                      [2, "mago"], [2, "pirata"], [2, "eroe"]]);
    tavolozza = scegli([[3, ["#2fae74", "#1c6f4a", "#7dffd2", "#154d34"]],
                        [1, ["#3b8fd9", "#1f5a99", "#a5e6ff", "#173f6b"]],
                        [1, ["#ec8a3a", "#a8571a", "#ffe9a8", "#6e3a10"]],
                        [1, ["#8a63d2", "#5a3b99", "#e6d4ff", "#3d2766"]]]);
    leggiColori();
  }

  // --- Dove poggia un lottatore ----------------------------------------
  // La superficie più alta sotto i suoi piedi, fra il pavimento (la
  // striscia) e gli elementi della pagina.
  function appoggio(f) {
    if (verso < 0) {
      // Sottosopra: si «poggia» sotto il tetto o sotto il bordo basso di un elemento.
      const piede = Math.min(f.p.piedeA.y, f.p.piedeD.y);
      let y = 0, chi = null;
      for (const o of ostacoli) {
        if (f.cx < o.l - 3 * S || f.cx > o.r + 3 * S) continue;
        if (o.b > piede + 10 * S) continue;
        if (o.b > y) { y = o.b; chi = o; }
      }
      return [y, chi];
    }
    const piede = Math.max(f.p.piedeA.y, f.p.piedeD.y);
    let y = pavimento, chi = null;
    for (const o of ostacoli) {
      if (f.cx < o.l - 3 * S || f.cx > o.r + 3 * S) continue;
      if (o.t < piede - 10 * S) continue;
      if (o.t < y) { y = o.t; chi = o; }
    }
    return [y, chi];
  }

  // --- Le pose ---------------------------------------------------------
  function posa(f) {
    const q = {}, sch = scheletro(f.tipo);
    for (const nome in sch) q[nome] = [sch[nome][0], sch[nome][1]];
    const e = f.durata ? Math.sin(Math.PI * Math.min(1, f.t / f.durata)) : 0;
    const respiro = Math.sin(f.passo * 0.5 + (f.tipo === "mela" ? 1.7 : 0)) * 0.8;
    q.bacino[0] += respiro; q.collo[0] += respiro; q.testa[0] += respiro;

    if (f.azione === "avanza" || f.azione === "indietro") {
      const ph = f.passo;
      q.piedeA = [Math.max(0, 5 * Math.cos(ph)), 8 + 7 * Math.sin(ph)];
      q.piedeD = [Math.max(0, -5 * Math.cos(ph)), -8 - 7 * Math.sin(ph)];
      q.ginocchioA = [14 + Math.max(0, 3 * Math.cos(ph)), 6 + 4 * Math.sin(ph)];
      q.ginocchioD = [14 + Math.max(0, -3 * Math.cos(ph)), -3 - 4 * Math.sin(ph)];
    }
    // Prima di colpire ci si carica un attimo all'indietro (anticipazione).
    const carica = COLPI[f.azione] ? Math.max(0, 1 - f.t / 5) : 0;
    switch (f.azione) {
      case "pugno":
        q.manoA = [52, 13 + 17 * e - 9 * carica]; q.gomitoA = [48, 9 + 9 * e - 7 * carica];
        q.collo[1] += 3 * e - 3 * carica; q.testa[1] += 4 * e - 3 * carica; break;
      case "solleva": {
        const k = Math.min(1, f.t / 7);
        q.manoA = [50 + 27 * k, 13 - 8 * k]; q.gomitoA = [44 + 14 * k, 8 - 2 * k];
        q.manoD = [49 + 26 * k, 8 - 9 * k]; q.gomitoD = [41 + 15 * k, 3 - 4 * k];
        break;
      }
      case "lancia": {
        if (f.t < 11) {
          const k = f.t / 11;
          q.manoA = [78, 4 - 12 * k]; q.gomitoA = [62, 3 - 6 * k];
          q.manoD = [75, -4 - 8 * k]; q.gomitoD = [60, -3 - 5 * k];
          q.collo[1] -= 4 * k; q.testa[1] -= 5 * k;
        } else {
          const k = Math.min(1, (f.t - 11) / 10);
          q.manoA = [78 - 24 * k, -8 + 36 * k]; q.gomitoA = [62 - 12 * k, -3 + 18 * k];
          q.manoD = [75 - 22 * k, -12 + 30 * k]; q.gomitoD = [60 - 12 * k, -8 + 16 * k];
          q.collo[1] += 5 * k; q.testa[1] += 6 * k;
        }
        break;
      }
      case "para":
        q.manoA = [58, 9]; q.gomitoA = [46, 11]; q.manoD = [56, 5]; q.gomitoD = [44, 6];
        q.collo[1] -= 2; q.testa[1] -= 2; q.bacino[0] -= 2; break;
      case "schiva":
        q.piedeA = [10, 6]; q.piedeD = [10, -8]; q.ginocchioA = [20, 6]; q.ginocchioD = [20, -4];
        q.collo[1] -= 6; q.testa[1] -= 8; break;
      case "diretto":
        q.manoD = [51, 8 + 22 * e]; q.gomitoD = [47, 5 + 12 * e];
        q.collo[1] += 4 * e; q.testa[1] += 5 * e; q.bacino[1] += 2 * e; break;
      case "montante":
        q.manoA = [44 + 26 * e, 10 + 9 * e]; q.gomitoA = [42 + 12 * e, 8 + 5 * e];
        q.bacino[0] -= 3 * e; break;
      case "calcio":
        q.piedeA = [8 + 20 * e, 8 + 20 * e]; q.ginocchioA = [14 + 12 * e, 7 + 11 * e];
        q.collo[1] -= 4 * e; q.testa[1] -= 5 * e; break;
      case "provoca":
        q.manoD = [58 + 6 * Math.sin(f.t * 0.6), -4]; q.gomitoD = [52, -4];
        q.bacino[0] += 2 * Math.abs(Math.sin(f.t * 0.3)); break;
      case "esulta":
        q.manoA = [80, 6]; q.gomitoA = [68, 7]; q.manoD = [80, -6]; q.gomitoD = [68, -7];
        break;
      case "salto":
        q.piedeA = [10, 9]; q.piedeD = [10, -7]; q.ginocchioA = [20, 9]; q.ginocchioD = [20, -2];
        break;
      case "spara": {
        // Braccio teso verso l'avversario; al colpo, il rinculo.
        const rinculo = f.t >= 10 && f.t < 18 ? (18 - f.t) / 8 : 0;
        q.manoA = [50 + 3 * rinculo, 25 - 5 * rinculo]; q.gomitoA = [48 + 1.5 * rinculo, 15 - 3 * rinculo];
        q.manoD = [47, 12]; q.gomitoD = [42, 6]; q.testa[1] += 1;
        break;
      }
      case "fendente":
        if (f.t < 10) {
          const k = f.t / 10;
          q.manoA = [56 + 24 * k, 12 - 14 * k]; q.gomitoA = [50 + 14 * k, 7 - 7 * k]; q.collo[1] -= 2 * k;
        } else {
          const k = Math.min(1, (f.t - 10) / 6);
          q.manoA = [80 - 40 * k, -2 + 26 * k]; q.gomitoA = [64 - 20 * k, 0 + 15 * k];
          q.collo[1] += 4 * k; q.testa[1] += 5 * k; q.piedeA = [0, 8 + 6 * k];
        }
        break;
      case "affondo": {
        // Un passo avanti e la lama dritta al petto.
        const a = (f.t < 8 ? f.t / 8 : 1) * (f.t > 14 ? 1 - Math.min(1, (f.t - 14) / 8) : 1);
        q.manoA = [50 - 2 * a, 10 + 24 * a - 8 * carica]; q.gomitoA = [49, 6 + 12 * a - 6 * carica];
        q.manoD = [44, -8]; q.gomitoD = [46, -4];
        q.piedeA = [0, 8 + 8 * a]; q.ginocchioA = [13, 8 + 6 * a]; q.collo[1] += 4 * a; q.testa[1] += 5 * a; q.bacino[1] += 2 * a;
        break;
      }
      case "rovescio":
        // Dal basso verso l'alto, di rovescio.
        if (f.t < 9) { const k = f.t / 9; q.manoA = [44 - 16 * k, 10 - 4 * k]; q.gomitoA = [44 - 6 * k, 8]; q.collo[1] -= 2 * k; }
        else {
          const k = Math.min(1, (f.t - 9) / 6);
          q.manoA = [28 + 50 * k, 6 + 26 * Math.sin(Math.PI * 0.75 * k)]; q.gomitoA = [38 + 26 * k, 8 + 10 * k];
          q.collo[1] += 3 * k; q.testa[1] += 3 * k;
        }
        break;
      case "scattoLama":
        if (f.t < 10) {
          // Raccolto, la lama al fianco.
          q.bacino[0] -= 5; q.collo[0] -= 6; q.testa[0] -= 6; q.collo[1] += 3; q.testa[1] += 4;
          q.ginocchioA = [11, 10]; q.ginocchioD = [11, -6]; q.piedeA = [0, 12]; q.piedeD = [0, -10];
          q.manoA = [34, -8]; q.gomitoA = [40, -2]; q.manoD = [36, 4]; q.gomitoD = [42, 4];
        } else if (f.t < 15) {
          // Lo scatto: tutto proteso in avanti.
          q.manoA = [46, 30]; q.gomitoA = [48, 16]; q.collo[1] += 7; q.testa[1] += 9;
          q.piedeD = [2, -18]; q.ginocchioD = [14, -8]; q.piedeA = [0, 10];
        } else {
          // Fermo, la lama bassa: l'effetto del taglio arriva un attimo dopo.
          q.manoA = [30, 22]; q.gomitoA = [40, 12]; q.manoD = [40, -4]; q.gomitoD = [44, -2];
          q.piedeA = [0, 12]; q.piedeD = [0, -8]; q.bacino[0] -= 2;
        }
        break;
      case "lancioLama":
        if (f.t < 14) { const k = f.t / 14; q.manoA = [60 + 12 * k, 4 - 18 * k]; q.gomitoA = [54 + 6 * k, 2 - 8 * k]; q.collo[1] -= 3 * k; }
        else { const k = Math.min(1, (f.t - 14) / 7); q.manoA = [72 - 24 * k, -14 + 42 * k]; q.gomitoA = [60 - 10 * k, -6 + 20 * k]; q.collo[1] += 4 * k; q.testa[1] += 5 * k; }
        break;
      case "pressa": {
        const tr = Math.sin(f.t * 1.3) * 0.8;
        q.manoA = [57 + tr, 21]; q.gomitoA = [50, 12]; q.manoD = [53 + tr, 18]; q.gomitoD = [46, 9];
        q.collo[1] += 4; q.testa[1] += 5; q.piedeD = [0, -14]; q.ginocchioD = [13, -8]; q.piedeA = [0, 9]; q.bacino[0] -= 2;
        break;
      }
      case "trasforma":
        if (f.t < 70) {
          // Pugni stretti, ginocchia piegate, la testa all'indietro: tutto trema.
          const tr = Math.sin(f.t * 2.1) * 0.8;
          q.piedeA = [0, 13]; q.piedeD = [0, -13]; q.ginocchioA = [11, 12]; q.ginocchioD = [11, -10];
          q.bacino[0] -= 5; q.collo[0] -= 4; q.testa[0] -= 2; q.testa[1] -= 3 + tr; q.collo[1] -= 1;
          q.manoA = [36, 15 + tr]; q.gomitoA = [42, 16]; q.manoD = [36, -13 - tr]; q.gomitoD = [42, -14];
        } else {
          q.manoA = [30, 13]; q.gomitoA = [41, 14]; q.manoD = [30, -11]; q.gomitoD = [41, -12];
          q.piedeA = [0, 11]; q.piedeD = [0, -11]; q.testa[1] -= 1;
        }
        break;
      case "gelo":
      case "rimpicciolisci":
        // Un colpo di bacchetta: indietro, poi di scatto in avanti.
        if (f.t < 14) { const k = f.t / 14; q.manoA = [56 + 16 * k, 8 - 12 * k]; q.gomitoA = [50 + 8 * k, 6 - 6 * k]; }
        else { const k = Math.min(1, (f.t - 14) / 5); q.manoA = [72 - 20 * k, -4 + 30 * k]; q.gomitoA = [58 - 8 * k, 14 * k]; q.collo[1] += 3 * k; q.testa[1] += 3 * k; }
        q.manoD = [40, -6]; q.gomitoD = [44, -3];
        break;
      case "fulmine":
        // La bacchetta al cielo, poi giù.
        if (f.t < 20) { q.manoA = [86, 5]; q.gomitoA = [70, 6]; }
        else { q.manoA = [54, 20]; q.gomitoA = [52, 11]; q.collo[1] += 3; }
        q.manoD = [40, -6]; q.gomitoD = [44, -3];
        break;
      case "levita": {
        const k = f.t < 74 ? Math.min(1, f.t / 12) : Math.max(0, 1 - (f.t - 74) / 5);
        q.manoA = [50 + 28 * k, 14 + 4 * k]; q.gomitoA = [46 + 12 * k, 10 + 3 * k];
        q.manoD = [38, -6]; q.gomitoD = [42, -3]; q.testa[1] += 1;
        break;
      }
      case "presa":
        if (f.tiene) {
          const [h, dx] = puntoPresa(f), su = eMela(f) ? ABBASSA_MELA : 0;
          q.manoA = [h - 1 + su, dx + 2]; q.manoD = [h - 3 + su, dx - 2];
          q.gomitoA = [(50 + h) / 2 + 4 + su, dx * 0.5 + 3]; q.gomitoD = [(50 + h) / 2 + 2 + su, dx * 0.5 - 1];
          if (f.mossaPresa === "suplex") { const k = Math.min(1, Math.max(0, f.t - 10) / 24); q.collo[1] -= 6 * k; q.testa[1] -= 9 * k; }
          else { q.collo[1] += 2; q.ginocchioA[0] -= 2; q.ginocchioD[0] -= 2; }
        } else {
          const k = Math.min(1, f.t / 10);
          q.manoA = [50, 13 + 15 * k]; q.gomitoA = [47, 9 + 8 * k]; q.manoD = [49, 8 + 17 * k]; q.gomitoD = [45, 4 + 9 * k];
          q.collo[1] += 3 * k; q.testa[1] += 4 * k;
        }
        break;
      case "sfera":
        if (f.t < 112) { q.manoA = [84, 6]; q.manoD = [84, -6]; q.gomitoA = [70, 7]; q.gomitoD = [70, -7]; q.testa[1] -= 1; }
        else { q.manoA = [46, 26]; q.manoD = [44, 22]; q.gomitoA = [52, 15]; q.gomitoD = [50, 11]; q.collo[1] += 4; q.testa[1] += 5; }
        q.piedeA = [0, 12]; q.piedeD = [0, -12];
        break;
      case "disco":
        if (f.t < 30) { q.manoA = [84, 4]; q.gomitoA = [69, 6]; }
        else { const k = Math.min(1, (f.t - 30) / 8); q.manoA = [84 - 34 * k, 4 + 24 * k]; q.gomitoA = [69 - 18 * k, 6 + 10 * k]; q.collo[1] += 4 * k; q.testa[1] += 5 * k; }
        break;
      case "lampo":
        q.manoA = [63, 9]; q.gomitoA = [52, 15]; q.manoD = [63, -3]; q.gomitoD = [52, -9];
        break;
      case "barriera":
        q.manoA = [50, 22]; q.gomitoA = [49, 12]; q.manoD = [50, -20]; q.gomitoD = [49, -10];
        q.piedeA = [0, 13]; q.piedeD = [0, -13]; q.bacino[0] -= 2;
        break;
      case "telecinesi": {
        // Una mano alzata e aperta; al botto si chiude a pugno, in basso.
        const k = f.t < 104 ? Math.min(1, f.t / 12) : Math.max(0, 1 - (f.t - 104) / 6);
        q.manoA = [50 + 28 * k, 14 + 4 * k]; q.gomitoA = [46 + 12 * k, 10 + 3 * k];
        q.manoD = [38, -6]; q.gomitoD = [42, -3]; q.testa[1] += 1;
        break;
      }
      case "avvinghia":
        q.manoA = [50, 26]; q.gomitoA = [49, 14]; q.manoD = [44, 24]; q.gomitoD = [44, 12];
        q.ginocchioA = [22, 12]; q.piedeA = [14, 22]; q.ginocchioD = [20, 10]; q.piedeD = [10, 20];
        break;
      case "carica": {
        const tr = Math.sin(f.t * 1.7) * 0.6;
        q.piedeA = [0, 12]; q.piedeD = [0, -12]; q.ginocchioA = [12, 11]; q.ginocchioD = [12, -9];
        q.bacino[0] -= 4; q.collo[0] -= 3; q.testa[0] -= 3; q.testa[1] += tr;
        q.manoA = [28, 16]; q.gomitoA = [39, 12]; q.manoD = [28, -12]; q.gomitoD = [39, -9];
        break;
      }
      case "onda":
        q.piedeA = [0, 13]; q.piedeD = [0, -10]; q.ginocchioA = [13, 11]; q.ginocchioD = [13, -7];
        if (f.t < 34) {
          q.manoA = [36, -6]; q.manoD = [38, -8]; q.gomitoA = [42, 4]; q.gomitoD = [42, 2];
          q.collo[1] -= 3; q.testa[1] -= 2;
        } else {
          q.manoA = [49, 27]; q.manoD = [48, 25]; q.gomitoA = [49, 15]; q.gomitoD = [48, 13];
          q.collo[1] += 3; q.testa[1] += 3;
        }
        if (eMela(f)) for (const nome of SPALLA_MELA) q[nome][0] += ABBASSA_MELA * 0.5;
        break;
      case "raffica":
        if (Math.floor(f.t / 6) % 2) { q.manoA = [50, 27]; q.gomitoA = [48, 15]; }
        else { q.manoD = [49, 26]; q.gomitoD = [46, 14]; }
        q.piedeA = [0, 11]; q.piedeD = [0, -9];
        break;
      case "palla":
        // Giù a raccogliere la neve, poi su e via, con una mano sola.
        if (f.t < 12) {
          const k = Math.sin(Math.PI * f.t / 12);
          q.bacino[0] -= 10 * k; q.collo[0] -= 14 * k; q.testa[0] -= 15 * k; q.collo[1] += 5 * k; q.testa[1] += 6 * k;
          q.ginocchioA[0] -= 3 * k; q.ginocchioD[0] -= 3 * k;
          q.manoA = [8 + 42 * (1 - k), 16]; q.gomitoA = [24 + 20 * (1 - k), 13];
        } else if (f.t < 20) {
          const k = (f.t - 12) / 8;
          q.manoA = [56 + 12 * k, 10 - 22 * k]; q.gomitoA = [50 + 8 * k, 6 - 10 * k]; q.collo[1] -= 3 * k;
        } else {
          const k = Math.min(1, (f.t - 20) / 6);
          q.manoA = [68 - 14 * k, -12 + 36 * k]; q.gomitoA = [58 - 6 * k, -4 + 18 * k]; q.collo[1] += 4 * k; q.testa[1] += 5 * k;
        }
        break;
      case "estrai":
        // La mela allunga la mano dietro, nel jetpack, e tira fuori il pieghevole.
        if (f.t < 14) {
          const k = f.t / 14;
          q.manoA = [50 + 8 * k, 13 - 30 * k]; q.gomitoA = [48 + 4 * k, 8 - 14 * k]; q.testa[1] -= 3 * k;
        } else {
          const k = Math.min(1, (f.t - 14) / 10);
          q.manoA = [58 + 26 * k, -17 + 20 * k]; q.gomitoA = [52 + 16 * k, -6 + 10 * k];
          q.manoD = [60 + 10 * k, 12]; q.gomitoD = [50, 8];
        }
        break;
      case "balla": {
        const ph = f.t * 0.22, sn = Math.sin(ph);
        switch (f.ballo) {
          case "floss":
            q.manoA = [30, 8 + 14 * sn]; q.gomitoA = [38, 5 + 8 * sn]; q.manoD = [30, -6 + 14 * sn]; q.gomitoD = [38, -3 + 8 * sn];
            q.bacino[1] -= 4 * sn; break;
          case "robot": {
            const k = Math.floor(f.t / 10) % 4;
            const A = [[62, 18], [48, 22], [70, 10], [44, 16]][k], D = [[44, -14], [64, -10], [48, -16], [66, -8]][k];
            q.manoA = A; q.gomitoA = [(A[0] + 50) / 2 + 2, A[1] * 0.55]; q.manoD = D; q.gomitoD = [(D[0] + 50) / 2 + 2, D[1] * 0.55];
            q.testa[1] += k % 2 ? 2 : -2; break;
          }
          case "dab":
            q.manoA = [74, -16]; q.gomitoA = [63, -8]; q.manoD = [62, 7]; q.gomitoD = [56, 11];
            q.testa[0] -= 4; q.testa[1] += 4; break;
          case "twist":
            q.bacino[1] += 5 * Math.sin(ph * 2); q.ginocchioA = [12, 8 + 4 * sn]; q.ginocchioD = [12, -4 + 4 * sn];
            q.bacino[0] -= 3; q.collo[0] -= 3; q.testa[0] -= 3;
            q.manoA = [44, 16 - 10 * sn]; q.gomitoA = [40, 10]; q.manoD = [44, -8 - 10 * sn]; q.gomitoD = [40, -6]; break;
          case "saltelli": {
            const su = Math.abs(sn);
            q.manoA = [44 + 36 * su, 10 + 8 * su]; q.gomitoA = [44 + 20 * su, 10 + 6 * su];
            q.manoD = [44 + 36 * su, -6 - 8 * su]; q.gomitoD = [44 + 20 * su, -4 - 6 * su];
            q.piedeA = [0, 6 + 8 * su]; q.piedeD = [0, -6 - 8 * su]; break;
          }
          case "moonwalk":
            q.piedeA = [Math.max(0, 3 * sn), 8 - 10 * sn]; q.piedeD = [Math.max(0, -3 * sn), -8 + 10 * sn];
            q.manoA = [40, 10 + 6 * sn]; q.manoD = [40, -6 - 6 * sn]; q.testa[1] -= 2; break;
          default:   // giravolta
            q.manoA = [58, 22]; q.gomitoA = [55, 12]; q.manoD = [58, -18]; q.gomitoD = [55, -8];
            q.piedeD = [6, -4]; q.ginocchioD = [16, -6];
        }
        break;
      }
    }
    // Accecato dal lampo: mani sugli occhi, barcollando.
    if (f.accecato > 0 && !f.azione) {
      const b = Math.sin(passi * 0.25) * 2;
      q.manoA = [61, 6 + b]; q.gomitoA = [51, 12]; q.manoD = [61, 0 + b]; q.gomitoD = [51, -5];
      q.testa[1] += b; q.collo[1] += b * 0.5;
    }
    // In volo da guerriero: gambe piegate all'indietro, busto proteso; nello
    // scatto il corpo si allunga, un pugno avanti e le gambe tese dietro.
    if (f.volo && f.jet > 0 && (!f.azione || f.azione === "avanza")) {
      if (f.scatto > 0) {
        q.manoA = [56, 22]; q.gomitoA = [53, 12]; q.manoD = [40, -10]; q.gomitoD = [44, -6];
        q.ginocchioA = [24, -9]; q.piedeA = [20, -21]; q.ginocchioD = [22, -12]; q.piedeD = [17, -25];
        q.collo[1] += 7; q.testa[1] += 9; q.bacino[1] -= 2;
      } else {
        const ond = Math.sin(passi * 0.08) * 1.5;
        q.ginocchioA = [16, 5]; q.piedeA = [5 + ond, -3]; q.ginocchioD = [15, -2]; q.piedeD = [4 - ond, -9];
        q.manoA = [42, 15]; q.gomitoA = [43, 9]; q.manoD = [42, 6]; q.gomitoD = [42, 1];
        q.collo[1] += 2; q.testa[1] += 3;
      }
    }
    if (f.azione === "rush") {
      if (f.t < 32) {
        const k = f.t % 8 < 4;
        q.manoA = k ? [52, 28] : [48, 12]; q.gomitoA = k ? [50, 16] : [45, 7];
        q.manoD = k ? [47, 8] : [51, 27]; q.gomitoD = k ? [44, 3] : [49, 15];
        q.collo[1] += 3; q.testa[1] += 3;
      } else if (f.t < 36) {
        q.manoA = [80, 10]; q.manoD = [80, 8]; q.gomitoA = [68, 6]; q.gomitoD = [68, 4]; q.collo[1] -= 2;
      } else {
        q.manoA = [42, 24]; q.manoD = [42, 22]; q.gomitoA = [52, 18]; q.gomitoD = [52, 16]; q.collo[1] += 5; q.testa[1] += 6;
      }
      if (eMela(f)) for (const nome of SPALLA_MELA) q[nome][0] += ABBASSA_MELA;
    }
    // Col paracadute aperto ci si tiene alle corde, con le gambe a penzoloni.
    if (f.paracadute) {
      q.manoA = [76, 6]; q.gomitoA = [64, 8]; q.manoD = [76, -6]; q.gomitoD = [64, -8];
      q.piedeA = [2, 5]; q.piedeD = [0, -4]; q.ginocchioA = [15, 5]; q.ginocchioD = [15, -3];
      if (eMela(f)) for (const nome of SPALLA_MELA) q[nome][0] += ABBASSA_MELA;
    }
    if (eMela(f)) for (const nome of SPALLA_MELA) q[nome][0] -= ABBASSA_MELA;
    // In coordinate della finestra.
    const fuori = {};
    for (const nome in q) {
      fuori[nome] = [f.cx + q[nome][1] * f.dir * S, f.base - verso * (q[nome][0] * S + 2 * S)];
    }
    return fuori;
  }

  // La posa dell'arrampicata: mani alternate sul bordo, piedi contro la
  // parete, corpo appeso di fianco. `s` è il lato esterno (-1 sinistra).
  function posaScalata(f) {
    const sc = f.scalata, o = sc.o, s = sc.lato, xw = s < 0 ? o.l : o.r, y = sc.y;
    const ph = f.t * 0.3, su = Math.max(0, Math.sin(ph)), giu = Math.max(0, -Math.sin(ph));
    const presa = (dy) => Math.max(o.t - 1 * S, y - dy * S);
    return {
      bacino: [xw + s * 9 * S, y - 26 * S], collo: [xw + s * 6 * S, y - 48 * S],
      testa: [xw + s * 7 * S, y - 59 * S],
      manoA: [xw + s * 2 * S, presa(58 + 6 * su)], manoD: [xw + s * 2 * S, presa(52 + 6 * giu)],
      gomitoA: [xw + s * 8 * S, y - 47 * S], gomitoD: [xw + s * 8 * S, y - 43 * S],
      piedeA: [xw + s * 3 * S, y - 4 * S - 6 * S * giu], piedeD: [xw + s * 3 * S, y - 10 * S - 6 * S * su],
      ginocchioA: [xw + s * 14 * S, y - 14 * S], ginocchioD: [xw + s * 14 * S, y - 19 * S],
    };
  }

  // --- Il cervello: un ciclo casuale di azioni --------------------------
  const DURATE = { avanza: 110, indietro: 26, pugno: 18, diretto: 20, montante: 24,
                   calcio: 28, provoca: 50, esulta: 36, salto: 34,
                   solleva: 16, lancia: 26, para: 26, schiva: 30,
                   spara: 26, fendente: 26, presa: 42, estrai: 36, balla: 170, palla: 30,
                   carica: 70, onda: 80, raffica: 40, rush: 44,
                   sfera: 150, disco: 56, lampo: 40, barriera: 110, avvinghia: 96, telecinesi: 124,
                   trasforma: 96, gelo: 44, rimpicciolisci: 40, fulmine: 50, levita: 100,
                   affondo: 24, rovescio: 26, scattoLama: 44, lancioLama: 40, pressa: 50 };

  function inizia(f, azione, meta) {
    f.azione = azione; f.t = 0; f.durata = DURATE[azione]; f.colpito = false;
    if (meta !== undefined) f.meta = meta;
    if (azione === "presa") {
      f.mossaPresa = scegli([[3, "sopra"], [2, "rotea"], [2, "suplex"]]);
      f.durata = DURATE_PRESA[f.mossaPresa];
    }
    if (azione === "salto") {
      for (const n in f.p) { f.p[n].oy = f.p[n].y + verso * 6.5 * S; f.p[n].ox = f.p[n].x - f.dir * 1.6 * S; }
    }
    if (azione === "schiva") {
      // Un balzo all'indietro, fuori portata.
      for (const n in f.p) { f.p[n].oy = f.p[n].y + verso * 5 * S; f.p[n].ox = f.p[n].x + f.dir * 2.6 * S; }
    }
  }

  function iniziaScalata(f, o, lato) {
    f.scalata = { o, lato, y: f.base };
    f.azione = null; f.t = 0;
    f.dir = -lato;
  }

  // Si può salire su `o` da qui? Solo se il suo fianco arriva fino a
  // portata di mano: un blocco che galleggia a mezza pagina no.
  function raggiungibile(f, o) {
    return o && o.b >= f.base - 60 * S && o.t < f.base - 6 * S;
  }

  // --- Il jetpack: si decolla, si lotta in aria, ogni tanto impazzisce ----
  function decolla(f, impazzito) {
    if (verso < 0) return;                       // sottosopra niente jetpack
    if (anime) { prendiIlVolo(f); return; }      // i super guerrieri volano da sé
    f.volo = false;
    const b = f.p.bacino;
    f.jet = Math.round(caso(260, 560)); f.azione = null; f.scalata = null; f.pensa = 6;
    f.volaY = Math.max(110, Math.min(pavimento - 90 * S, b.y - caso(70, 170) * S));
    f.caos = impazzito ? Math.round(caso(200, 340)) : 0;
    f.giro = (Math.random() < 0.5 ? -1 : 1) * caso(0.09, 0.16); f.rot = 0;
    for (const n in f.p) f.p[n].oy = f.p[n].y + 3.5 * S;
    scintille(b.x, b.y + 22 * S, 8, "#ffb62e");
  }

  function pensaVolo(f, altro) {
    if (f.azione) {
      f.t++;
      if (f.azione === "spara" && f.t === 10 && f.arma) spara(f, altro);
      if (anime) eseguiAnime(f, altro);
      if (lame()) eseguiLama(f, altro);
      if (f.t >= f.durata) {
        if ((f.azione === "spara" || f.azione === "fendente") && f.arma && f.colpiArma <= 0) {
          f.tel = f.arma; f.arma.stato = "portato"; f.arma = null; inizia(f, "lancia"); return;
        }
        f.azione = null; f.pensa = Math.round(caso(2, 14));
      }
      if (f.azione === "lancia" && f.t === 11 && f.tel) lanciaTelefono(f, altro);
      return;
    }
    if (f.caos > 0 || f.scatto > 0 || f.recupero > 0 || --f.pensa > 0) return;
    if (f.volo) { pensaGuerriero(f, altro); return; }
    const ob = altro.p.bacino, mio = f.p.bacino;
    f.dir = ob.x >= mio.x ? 1 : -1;
    if (altro.ko || altro.preso) {
      // L'avversario è a terra: si scende a festeggiare.
      f.jet = Math.min(f.jet, 70); f.meta = altro.cx; f.volaY = Math.min(pavimento - 60 * S, ob.y - 30 * S);
      f.pensa = 20; return;
    }
    f.volaY = Math.max(100, Math.min(pavimento - 70 * S, ob.y - caso(-8, 28) * S));
    const dx = Math.abs(ob.x - mio.x) / S;
    if (f.arma && f.arma.tipo === "pistola" && dx > 40 && Math.random() < 0.5) { inizia(f, "spara"); return; }
    if (anime && f.ki >= 45 && dx > 70 && Math.random() < 0.3) { inizia(f, "onda"); return; }
    if (anime && f.ki >= 15 && dx > 90 && Math.random() < 0.25) { inizia(f, "raffica"); return; }
    if (f.arma && f.arma.tipo === "spada" && dx <= 44) { f.colpiArma--; inizia(f, "fendente"); return; }
    if (lamaPronta(f) && dx <= 44 && Math.abs(ob.y - mio.y) < 34 * S) { inizia(f, scegli([[3, "fendente"], [2, "affondo"], [2, "rovescio"]])); return; }
    if (dx > 34) { f.meta = ob.x - f.dir * 27 * S; f.pensa = Math.round(caso(5, 16)); return; }
    f.meta = f.cx;
    inizia(f, scegli([[30 * f.aggr * pesoMossa(f, "pugno"), "pugno"], [22 * f.aggr * pesoMossa(f, "diretto"), "diretto"],
                      [16 * pesoMossa(f, "montante"), "montante"], [16 * f.aggr * pesoMossa(f, "calcio"), "calcio"],
                      [8 * f.furbo * pesoMossa(f, "para"), "para"], [8 * f.furbo * pesoMossa(f, "schiva"), "schiva"]]));
  }

  // La spinta del jetpack: tiene il corpo alla quota voluta (o lo sbatte
  // in giro, se impazzisce). Si applica a tutti i punti, come una forza.
  function applicaSpinta(f) {
    const g = GRAVITA * S * moltG, b = f.p.bacino;
    let spinta;
    if (f.volo) {
      f.fiamma = 0;
      if (f.recupero > 0) { f.recupero--; return; }      // sbalzato: si riprende dopo un attimo
      if (f.scatto > 0) { for (const n in f.p) f.p[n].y -= g; return; }
      const meta = f.volaY + Math.sin(passi * 0.06 + (f.tipo === "mela" ? 2 : 0)) * 3 * S;
      const err = b.y - meta, vy = b.y - b.oy;
      spinta = Math.max(0, Math.min(3 * g, g + 0.02 * err + 0.3 * vy));
      for (const n in f.p) f.p[n].y -= spinta;
      if (passi % 6 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "scintilla", x: b.x + caso(-8, 8) * S, y: b.y + 22 * S, vx: caso(-0.3, 0.3) * S, vy: caso(0.5, 1.5) * S,
                          vita: 12, max: 12, colore: COLORI_ANIME[f.tipo] });
      }
      return;
    }
    if (f.caos > 0) {
      // Giri impazziti: il getto gira in tondo (cerchi e otto, a volte al
      // contrario), poi a secco di colpo e giù a schiantarsi.
      f.caos--;
      f.rot = (f.rot || caso(0, 6.28)) + f.giro;
      let m = (2.2 + 1.2 * Math.sin(f.caos * 0.05)) * S;
      f.ix = Math.cos(f.rot) * m; f.iy = Math.sin(f.rot) * m;
      // Mai contro il soffitto: in alto il giro si sposta in basso.
      if (b.y < 150) f.iy = Math.abs(f.iy);
      spinta = g * 0.92;
      for (const n in f.p) { f.p[n].x += f.ix * 0.28; f.p[n].y += f.iy * 0.28; }
      f.p.testa.x += f.ix * 0.12; f.p.testa.y += f.iy * 0.12;
      if (passi % 3 === 0) fiammata(f, -f.iy, -f.ix);
      if (f.caos === 0) {
        // Schianto: il getto si spegne e si piomba a terra.
        f.jet = 0; f.fiamma = 0; f.stordito = 70; f.forza = 0.2;
        for (const n in f.p) f.p[n].oy = f.p[n].y - 9 * S;
        scintille(b.x, b.y, 10, "#ffb62e");
        return;
      }
    } else {
      const err = b.y - f.volaY, vy = b.y - b.oy;
      spinta = Math.max(0, Math.min(2.2 * g, g + 0.004 * err + 0.14 * vy));
      // A secco di carburante si sente: la fiamma balbetta.
      if (f.jet < 45 && (passi & 3) === 0) spinta *= 0.2;
      if (passi % 2 === 0 && spinta > 0.5 * g) fiammata(f, 3.2, 0);
    }
    f.fiamma = spinta / (g * 1.6);
    for (const n in f.p) f.p[n].y -= spinta;
  }

  function fiammata(f, vy, vx) {
    const p = f.p, ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x);
    const x = p.bacino.x - f.dir * 9 * S + Math.cos(ang) * 4 * S, y = p.bacino.y + Math.sin(ang) * 4 * S + 3 * S;
    for (let i = 0; i < 2 && particelle.length < 170; i++) {
      particelle.push({ tipo: "fiamma", x: x + caso(-2, 2) * S, y, vx: (vx + caso(-0.7, 0.7)) * S * 0.6,
                        vy: (Math.max(1.5, vy) + caso(0, 1.4)) * S, vita: Math.round(caso(10, 18)), max: 18,
                        colore: ["#ff7a1a", "#ffb62e", "#fff1a0"][Math.floor(Math.random() * 3)] });
    }
  }

  function pensa(f, altro) {
    if (f.ko || f.stordito || f.preso || f.tenuto || f.esploso || f.scalata || f.inVolo || f.gelato > 0) return;
    if (f.accecato > 0) { f.accecato--; f.azione = null; f.scatto = 0; if (!(f.jet > 0) && f.accecato % 30 === 0) f.cx += caso(-6, 6) * S; return; }
    if (f.jet > 0) { pensaVolo(f, altro); return; }
    if (f.azione) {
      f.t++;
      if (f.azione === "spara" && f.t === 10 && f.arma) spara(f, altro);
      if (f.azione === "estrai" && f.t === 14 && !f.tel) estraiDuo(f);
      if (anime) eseguiAnime(f, altro);
      if (lame()) eseguiLama(f, altro);
      if (f.azione === "palla" && f.t === 11) f.palla = true;
      if (f.azione === "palla" && f.t === 21 && f.palla) tiraPalla(f, altro);
      const vicino = Math.abs(altro.base - f.base) <= 18 * S &&
        Math.abs(altro.cx - f.cx) < 27 * S && !altro.ko;
      const arrivato = Math.abs(f.meta - f.cx) < 3 * S;
      if (f.azione === "lancia" && f.t === 11 && f.tel) lanciaTelefono(f, altro);
      if (f.t >= f.durata || (f.azione === "avanza" && (vicino || arrivato))) {
        if (f.azione === "avanza" && f.prendiTel) {
          const t = f.prendiTel; f.prendiTel = null;
          if (arrivato && t.stato === "libero" && Math.abs(t.x - f.cx) < 16 * S) {
            if (eArma(t)) {
              // Un'arma si impugna e si tiene: pistola sei colpi, spada cinque fendenti.
              if (!f.arma) { t.stato = "impugnato"; t.da = f; f.arma = t; f.colpiArma = t.tipo === "pistola" ? 6 : 5; }
              f.azione = null; f.pensa = 4; return;
            }
            t.stato = "portato"; t.da = f; f.tel = t; inizia(f, "solleva"); return;
          }
        }
        if (f.azione === "solleva" && f.tel) { inizia(f, "lancia"); return; }
        if (f.azione === "estrai" && f.tel) { inizia(f, "lancia"); return; }
        // Finiti i colpi l'arma vuota si tira addosso all'avversario.
        if ((f.azione === "spara" || f.azione === "fendente") && f.arma && f.colpiArma <= 0) {
          f.tel = f.arma; f.arma.stato = "portato"; f.arma = null; inizia(f, "lancia"); return;
        }
        if (f.azione === "avanza" && arrivato && f.dopo) {
          const piano = f.dopo; f.dopo = null; f.azione = null;
          if (raggiungibile(f, piano.o)) { iniziaScalata(f, piano.o, piano.lato); return; }
        }
        f.azione = null; f.pensa = f.combo ? 1 : caso(3, 22);
      }
      return;
    }
    if (--f.pensa > 0) return;
    f.dopo = null;
    // Ha appena vinto il round: balletto.
    if (f.daBallare) {
      f.daBallare = false;
      f.ballo = scegli([[2, "floss"], [2, "robot"], [2, "dab"], [2, "twist"], [2, "saltelli"], [1, "moonwalk"], [2, "giravolta"]]);
      inizia(f, "balla"); return;
    }
    if (altro.ko || altro.preso || altro.tenuto) { inizia(f, Math.random() < 0.7 ? "esulta" : "provoca"); return; }
    // I duellanti pensano con la lama; senza (lanciata, o col braccio staccato) tornano a fare a pugni.
    if (lame() && pensaLama(f, altro)) return;
    // La mela, ogni tanto e solo passato il primo minuto, tira fuori dal
    // jetpack il suo pieghevole: se prende il robot, lo fa a pezzi.
    const turno = f.tipo === "mela" ? prossimoDuo : prossimaBombaRobot;
    if (!stile && tempo >= turno && libero("armi") && !f.tel && !f.arma && !(altro.jet > 0) && !altro.esploso &&
        Math.abs(altro.cx - f.cx) < 480 * S && Math.random() < 0.35) {
      if (f.tipo === "mela") prossimoDuo = tempo + Math.round(caso(2400, 4200));
      else prossimaBombaRobot = tempo + Math.round(caso(2400, 4200));
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      inizia(f, "estrai"); return;
    }
    // Un telefono per terra a portata di mano? Si raccoglie e si lancia.
    if (!f.tel && !f.arma && Math.abs(altro.base - f.base) <= 18 * S) {
      const t = telefonoVicino(f);
      if (t && Math.random() < (eArma(t) || t.tipo === "bomba" || SPECIALI[t.tipo] ? 0.9 : 0.5 * f.furbo * (1 + 0.08 * livelloDi(f.tipo)))) {
        f.dir = t.x >= f.cx ? 1 : -1; f.prendiTel = t; inizia(f, "avanza", t.x); return;
      }
    }
    // Ogni tanto si accende il jetpack e si va a lottare in aria.
    const lv = livelloDi(f.tipo);
    // Chi ha imparato (livello 4) si alza in volo di proposito per inseguire
    // un avversario che sta volando.
    if (tempo >= CALMA && !f.tel && Math.random() < 0.045 * f.furbo * (lv >= 4 && altro.jet > 0 ? 5 : 1)) { decolla(f, altro.jet > 0 ? false : Math.random() < 0.3); return; }
    // L'avversario sta per colpire: ci si para o si schiva.
    if (altro.azione && COLPI[altro.azione] && Math.abs(altro.cx - f.cx) < 34 * S &&
        Math.abs(altro.base - f.base) <= 18 * S &&
        Math.random() < 0.3 * f.furbo * (pesoMossa(f, "para") + pesoMossa(f, "schiva")) / 2) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (anime && f.ki >= 15 && Math.random() < 0.4 && teletrasporta(f, altro)) return;
      const wp = pesoMossa(f, "para"), ws = pesoMossa(f, "schiva");
      inizia(f, Math.random() < wp / (wp + ws) ? "para" : "schiva"); return;
    }
    // Con un'arma in mano: la pistola spara da lontano, la spada si avvicina.
    if (f.arma && Math.abs(altro.base - f.base) <= 40 * S) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      const d = Math.abs(altro.cx - f.cx) / S;
      if (f.arma.tipo === "pistola") {
        if (d > 40 && Math.random() < 0.6) { inizia(f, "spara"); return; }
        if (d <= 40 && Math.random() < 0.5) { inizia(f, "indietro"); return; }
      } else if (d <= 44) { f.colpiArma--; inizia(f, "fendente"); return; }
      else { inizia(f, "avanza", altro.cx - f.dir * 34 * S); return; }
    }
    // Super guerrieri: onde, raffiche, teletrasporti e carica dell'aura.
    if (anime && !f.arma && !f.tel) {
      const d = Math.abs(altro.cx - f.cx) / S;
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (mossaSpeciale(f, altro)) return;
      if (verso > 0 && (altro.volo && altro.jet > 0 ? Math.random() < 0.6 : Math.random() < 0.14)) { scatta(f, altro, 26); return; }
      if (!maghi() && d <= 40 && f.ki >= 8 && Math.random() < 0.25) { inizia(f, "rush"); return; }
      // I maghi da vicino si scostano, o sparano una raffica a bruciapelo.
      if (maghi() && d <= 40 && Math.random() < 0.45) { inizia(f, f.ki >= 15 && Math.random() < 0.5 ? "raffica" : "indietro"); return; }
      if (f.ki >= 45 && d > 70 && Math.abs(altro.p.collo.y - f.p.collo.y) < 60 * S && Math.random() < 0.3) { inizia(f, "onda"); return; }
      if (f.ki >= 15 && d > 110 && Math.random() < 0.18 && teletrasporta(f, altro)) return;
      if (f.ki >= 15 && d > 60 && Math.random() < 0.25) { inizia(f, "raffica"); return; }
      if (f.ki < 50 && d > 100 && Math.random() < 0.25) { inizia(f, "carica"); return; }
    }
    // A Natale ci si tira le palle di neve.
    if (natale && !f.arma && !f.tel && Math.abs(altro.cx - f.cx) > 50 * S && Math.random() < 0.35) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      inizia(f, "palla"); return;
    }
    const pesoPresa = !f.arma && !(altro.jet > 0) && !altro.tenuto && !altro.ko
      ? (tempo < CALMA ? 3 : 10) * pesoMossa(f, "presa") : 0;

    const dy = altro.base - f.base;
    // Sottosopra niente arrampicate: si va verso l'altro e si «cade» su.
    if (verso < 0 && Math.abs(dy) > 18 * S) { f.dir = altro.cx >= f.cx ? 1 : -1; inizia(f, "avanza", altro.cx); return; }
    if (Math.abs(dy) <= 18 * S) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      const distanza = Math.abs(altro.cx - f.cx) / S;
      if (distanza > 34) {
        const azione = scegli([[74 * f.aggr, "avanza"], [14 * pesoMossa(f, "provoca"), "provoca"], [12 * pesoMossa(f, "salto"), "salto"]]);
        inizia(f, azione, altro.cx);
      } else if (distanza < 22) {
        inizia(f, scegli([[45 * pesoMossa(f, "indietro"), "indietro"], [25 * pesoMossa(f, "montante"), "montante"],
                          [30 * pesoMossa(f, "pugno"), "pugno"], [pesoPresa * 1.5, "presa"]]));
      } else {
        // Dopo un colpo a segno o una parata si va in serie: solo attacchi,
        // scelti ancora più in base a quel che ha funzionato.
        const serie = f.combo; f.combo = 0;
        const pa = serie ? 2 : 1;
        inizia(f, scegli([[28 * f.aggr * Math.pow(pesoMossa(f, "pugno"), pa), "pugno"],
                          [20 * f.aggr * Math.pow(pesoMossa(f, "diretto"), pa), "diretto"],
                          [14 * Math.pow(pesoMossa(f, "montante"), pa), "montante"],
                          [22 * f.aggr * Math.pow(pesoMossa(f, "calcio"), pa), "calcio"],
                          [serie ? 0 : 8 / f.aggr * pesoMossa(f, "indietro"), "indietro"],
                          [serie ? 0 : 8 * pesoMossa(f, "salto"), "salto"], [serie ? 0 : pesoPresa, "presa"]]));
      }
    } else if (dy > 0) {
      // L'avversario è più in basso: si va verso di lui, e se sta sotto
      // l'elemento su cui siamo, verso il bordo più vicino per scendere.
      const o = f.supporto;
      let meta = altro.cx;
      if (o && altro.cx >= o.l - 4 * S && altro.cx <= o.r + 4 * S) {
        meta = (f.cx - o.l < o.r - f.cx) ? o.l - 14 * S : o.r + 14 * S;
      }
      f.dir = meta >= f.cx ? 1 : -1;
      // Scende apposta da dove sta: se il salto è alto, apre il paracadute.
      if (o) f.scendeApposta = 300;
      inizia(f, "avanza", Math.max(10 * S, Math.min(W - 10 * S, meta)));
    } else {
      // Più in alto: ci si arrampica sul fianco dell'elemento su cui sta.
      const o = altro.supporto;
      if (raggiungibile(f, o)) {
        const lato = f.cx < (o.l + o.r) / 2 ? -1 : 1;
        const xw = lato < 0 ? o.l : o.r;
        const meta = xw + lato * 11 * S;
        f.dir = meta >= f.cx ? 1 : -1;
        if (Math.abs(meta - f.cx) < 4 * S) { iniziaScalata(f, o, lato); return; }
        inizia(f, "avanza", meta);
        f.dopo = { o, lato };
      } else {
        // Irraggiungibile: aspetta che scenda lui, provocandolo.
        inizia(f, scegli([[70, "provoca"], [30, "salto"]]));
      }
    }
  }

  const COLPI = { pugno: ["manoA", 7, 13, 3.2], diretto: ["manoD", 8, 15, 3.8],
                  montante: ["manoA", 9, 17, 4.4], calcio: ["piedeA", 10, 19, 4.8],
                  fendente: ["manoA", 10, 17, 5.4],
                  affondo: ["manoA", 6, 13, 5.0], rovescio: ["manoA", 10, 16, 5.2] };
  const SUONI = ["POW!", "BAM!", "SBAM!", "TUMP!", "ZOT!", "PAF!"];

  function controllaColpo(f, altro) {
    const regola = COLPI[f.azione];
    if (!regola || f.colpito || altro.ko || altro.preso || altro.tenuto || f.esploso) return;
    const [arto, da, a, forza] = regola;
    if (f.t < da || f.t > a) return;
    for (const k in ARTI) if (f.staccati[k] && ARTI[k][1] === arto) return;   // col moncone non si colpisce
    if (TAGLI[f.azione]) {
      // La spada (o la lama di energia): si controlla tutta la lama, non solo la mano.
      if (!f.arma && !lamaPronta(f)) return;
      const m = f.p.manoA, g = f.p.gomitoA, L = Math.hypot(m.x - g.x, m.y - g.y) || 1;
      const ux = (m.x - g.x) / L, uy = (m.y - g.y) / L;
      for (const k of [8, 15, 22, 29]) {
        const x = m.x + ux * k * S, y = m.y + uy * k * S;
        for (const bersaglio of ["testa", "collo", "bacino"]) {
          const b = altro.p[bersaglio];
          if (Math.hypot(x - b.x, y - b.y) < b.r + 4 * S) {
            f.colpito = true;
            colpisci(f, altro, forza * caso(0.9, 1.25), x, y, Math.random() < 0.5 ? "ZAC!" : "SWISH!");
            return;
          }
        }
      }
      return;
    }
    const m = f.p[arto];
    for (const bersaglio of ["testa", "collo", "bacino"]) {
      const b = altro.p[bersaglio];
      if (Math.hypot(m.x - b.x, m.y - b.y) < b.r + 6 * S) {
        f.colpito = true;
        colpisci(f, altro, forza * caso(0.85, 1.3), m.x, m.y);
        return;
      }
    }
  }

  // Le scritte disegnate seguono la lingua scelta, se il dizionario c'è (sul
  // sito è `lingue.js`; nell'estensione lo stesso file, accanto a questo).
  function dici(testo) {
    try {
      const l = window.__lingue;
      return (l && l.lingua() !== "it" && l.traduci(testo, l.lingua())) || testo;
    } catch (errore) { return testo; }
  }
  function scrivi(testo, x, y, grande) {
    scritte.push({ testo: dici(testo), x: Math.max(50, Math.min(W - 50, x)), y: Math.max(26, y), vita: grande ? 70 : 26, grande });
  }

  const SUONI_TEL = ["DRIIN!", "CRACK!", "BIP!", "SPLASH!", "NOTIFICA!", "TRIIN!"];
  const SUONI_OGGETTO = { orologio: ["BZZT!", "BIP!", "TIC!"], tablet: ["SBONK!", "SLAP!", "TONF!"],
                          pc: ["THUD!", "CTRL+ALT+CANC!", "BSOD!"], pistola: ["TONK!", "CLANG!"], spada: ["CLANG!", "TONK!"] };

  function colpisci(f, altro, forza, x, y, suono) {
    // Una parata di fronte ferma quasi tutto, ma il colpo si sente.
    if (altro.esploso) return;
    if (barrieraRegge(altro, forza, x, y)) return;
    const taglio = !!TAGLI[f.azione] || f.azione === "scattoLama";
    // Chi si sta trasformando non si tocca: il colpo rimbalza.
    if (altro.azione === "trasforma" && altro.t < 70) {
      scintille(x, y, 8, COLORI_ANIME[altro.tipo]);
      if (f.p) for (const n in f.p) f.p[n].ox += f.dir * 4 * S;
      fermoColpo = Math.max(fermoColpo, 2);
      return;
    }
    if (altro.azione === "para" && altro.dir === -f.dir) {
      impara(altro, "para", 1, 1); impara(f, f.azione, -1, 0);
      if (livelloDi(altro.tipo) >= 3 && Math.random() < 0.5) altro.combo = 1;
      scrivi(taglio || suono === "BANG!" ? "CLANG!" : "PARATO!", x, y - 6 * S, false);
      scintille(x, y, 5, "#bfe9ff");
      for (const n in altro.p) altro.p[n].ox -= f.dir * forza * 0.12 * S;
      fermoColpo = 2;
      return;
    }
    if (f.furia > 0) forza *= 1.5;
    if (f.potenziato > 0) forza *= f.forma >= 2 ? 1.7 : 1.4;
    if (f.piccolo > 0) forza *= 0.5;
    // Un colpo su chi è nel ghiaccio manda in pezzi il blocco, e fa più male.
    if (altro.gelato > 0) { rompiGhiaccio(altro, true); forza *= 1.3; }
    if (anime && f.p) { f.ki = Math.min(100, f.ki + 4); altro.ki = Math.min(100, altro.ki + 2); }
    if (altro.tel) lasciaCadere(altro);
    if (altro.tiene) molla(altro);
    altro.paracadute = 0; altro.scendeApposta = 0;
    if (altro.volo && altro.jet > 0) { altro.recupero = 24; altro.scatto = 0; }
    else if (altro.jet > 0 && Math.random() < 0.6) { altro.jet = 0; altro.caos = 0; }
    altro.danni++;
    const ko = altro.danni >= altro.soglia;
    // Ha imparato qualcosa: chi ha colpito rifà volentieri quella mossa, chi
    // era a metà di un'altra azione la rimpiange, chi l'ha presa si copre di più.
    impara(f, f.azione, 1, ko ? 3 : 1);
    if (COLPI[altro.azione]) impara(altro, altro.azione, -1, 0);
    if (cervello[altro.tipo]) {
      const pe = cervello[altro.tipo].pesi;
      pe.para = Math.min(1.8, pe.para * 1.015); pe.schiva = Math.min(1.8, pe.schiva * 1.015);
    }
    if (livelloDi(f.tipo) >= 2 && !ko && Math.random() < 0.14 * livelloDi(f.tipo)) f.combo = 1;
    // Il segno del colpo, qualche schizzo e, con le armi pesanti, un arto via.
    segna(altro, x, y, forza);
    schizza(altro, x, y, Math.round(1 + forza * 0.35), forza / 4);
    if (taglio && eMela(altro) && Math.random() < 0.45 && taglia(altro, f)) { /* tagliata in due */ }
    else if (taglio && Math.random() < (lame() ? 0.5 : 0.35)) smembra(altro, x, y);
    else if (suono === "BANG!" && Math.random() < 0.2) smembra(altro, x, y);
    if (eMela(altro) && (forza > 4.6 || suono === "BANG!" || taglio) && Math.random() < 0.4) mordi(altro, x, y);
    scintille(x, y, ko ? 16 : 9, f.furia > 0 ? "#ff6a3a" : "#ffe27a");
    fermoColpo = ko ? 9 : 3;
    if (ko) scossa = 12;
    const spinta = forza * S * (ko ? 1.9 : 1);
    for (const n in altro.p) {
      const peso = n.startsWith("piede") || n.startsWith("ginocchio") ? 0.35 : 1;
      altro.p[n].ox -= f.dir * spinta * peso;
      altro.p[n].oy += spinta * (ko ? 0.55 : 0.3);
    }
    altro.dolore = 22;
    altro.azione = null;
    altro.scalata = null;
    scrivi(suono || SUONI[Math.floor(Math.random() * SUONI.length)], x, y - 6 * S, false);
    if (ko) segnaKO(f, altro);
    else altro.stordito = 12;
  }

  function segnaKO(f, altro) {
    altro.koVero = true;
    risolviScommessa(f.tipo && f !== altro ? f.tipo : (altro.tipo === "robot" ? "mela" : "robot"));
    altro.ko = Math.round(caso(110, 170)); altro.danni = 0; altro.soglia = Math.round(caso(3, 6));
    if (f.tipo) punteggio[f.tipo]++;
    // Chi vince balla (01/10/2026, su richiesta), appena l'altro è giù.
    if (f.p && f !== altro) f.daBallare = true;
    // Ogni round un carattere nuovo: più aggressivo o più cauto.
    for (const l of lottatori) nuovoCarattere(l);
    salvaCervello(true);
    scrivi("K.O.!  " + punteggio.robot + "–" + punteggio.mela, altro.p.bacino.x, altro.base - 72 * S, true);
    controllaFinale(f.tipo, altro, f);
  }

  // --- Prese e lanci dell'avversario -----------------------------------
  // Si afferra l'altro per il collo e: lo si alza sopra la testa e lo si
  // scaglia avanti, lo si fa roteare e lo si lascia andare, o lo si ribalta
  // all'indietro (suplex). Il punto preso segue le mani; il resto penzola.
  const DURATE_PRESA = { sopra: 42, rotea: 47, suplex: 38 };
  function puntoPresa(f) {
    const t = Math.max(0, f.t - 10);
    if (f.mossaPresa === "rotea") {
      const th = t * 0.3;
      return [60 + 6 * Math.sin(th * 0.5), 28 * Math.cos(th)];
    }
    if (f.mossaPresa === "suplex") {
      const th = Math.min(1, t / 24) * Math.PI * 0.92;
      return [50 + 38 * Math.sin(th), 26 * Math.cos(th)];
    }
    const k = Math.min(1, t / 14), indietro = t > 22 ? Math.min(1, (t - 22) / 8) : 0;
    return [50 + 36 * k, 22 - 20 * k - 8 * indietro];
  }
  function agguanta(f, altro) {
    f.tiene = altro;
    altro.tenuto = { da: f, x: altro.p.collo.x, y: altro.p.collo.y };
    altro.azione = null; altro.scalata = null; altro.jet = 0; altro.caos = 0; altro.paracadute = 0;
    if (altro.tel) lasciaCadere(altro);
    if (altro.arma) lasciaArma(altro);
    altro.fantasma = true;
    scrivi("HOP!", altro.p.collo.x, altro.p.collo.y - 16 * S, false);
  }
  function molla(f) {
    const v = f.tiene;
    f.tiene = null;
    if (!v) return;
    v.tenuto = null; v.ko = Math.max(v.ko, 30); v.inVolo = true;
  }
  function scaglia(f) {
    const v = f.tiene;
    f.tiene = null;
    if (!v) return;
    v.tenuto = null;
    const m = f.mossaPresa;
    const [vx, vy] = m === "suplex" ? [-f.dir * 4, 8] : m === "rotea" ? [f.dir * 13, -5] : [f.dir * 11, -6];
    for (const n in v.p) { v.p[n].ox = v.p[n].x - vx * S; v.p[n].oy = v.p[n].y - verso * vy * S; }
    v.inVolo = true;
    v.danni += 2;
    impara(f, "presa", 1, 2);
    scrivi(m === "suplex" ? "SUPLEX!" : m === "rotea" ? "WHEEE!" : "VOLA!", v.p.collo.x, v.p.collo.y - 18 * S, false);
    if (v.danni >= v.soglia) segnaKO(f, v);
    else v.ko = Math.max(v.ko, 50);
  }
  function aggiornaPresa(f, altro) {
    if (!f.tiene) {
      if (f.t !== 10) return;
      const ok = altro && !altro.ko && !altro.preso && !altro.tenuto && !altro.esploso && !(altro.jet > 0) &&
        altro.azione !== "schiva" && Math.abs(altro.base - f.base) <= 18 * S && Math.abs(altro.cx - f.cx) < 32 * S;
      if (!ok) { impara(f, "presa", -1, 0); f.azione = null; f.pensa = Math.round(caso(6, 16)); return; }
      agguanta(f, altro);
    }
    const [h, dx] = puntoPresa(f);
    f.tiene.tenuto.x = f.cx + dx * f.dir * S;
    f.tiene.tenuto.y = f.base - verso * (h * S + 2 * S);
  }

  // --- La presa col mouse o col dito -----------------------------------
  const presa = { f: null, tel: null, punto: null, x: 0, y: 0, mosso: false };
  let appenaLanciato = false;

  let raggioPresa = 16;   // in unità S: il dito è più grosso del mouse
  function chiTrovo(x, y) {
    let migliore = null, distanza = raggioPresa * S;
    for (const f of lottatori) {
      if (f.esploso) continue;
      for (const n in f.p) {
        const d = Math.hypot(f.p[n].x - x, f.p[n].y - y) - f.p[n].r;
        if (d < distanza) { distanza = d; migliore = [f, n]; }
      }
      // Il busto (e la mela intera) si prende in tutta la sua larghezza.
      const cxB = (f.p.collo.x + f.p.bacino.x) / 2, cyB = (f.p.collo.y + f.p.bacino.y) / 2;
      if (Math.hypot(cxB - x, cyB - y) < 14 * S && (!migliore || distanza > 0)) {
        migliore = [f, "collo"]; distanza = 0;
      }
    }
    return migliore;
  }

  function telefonoSotto(x, y) {
    let migliore = null, d0 = (raggioPresa - 1) * S;
    for (const t of telefoni) {
      if (t.stato === "portato" || t.stato === "impugnato") continue;
      const d = Math.hypot(t.x - x, t.y - y) - t.r * 0.6;
      if (d < d0) { d0 = d; migliore = t; }
    }
    return migliore;
  }
  const qualcosaSotto = (x, y) => !!(chiTrovo(x, y) || telefonoSotto(x, y));

  function prendi(evento) {
    if (fermo || (evento.button !== undefined && evento.button > 0)) return;
    const bersaglio = evento.target;
    if (bersaglio && bersaglio.closest && bersaglio.closest(".ring-pannello, .ultimora-barra")) return;
    // Nell'estensione i tasti stanno nello shadow DOM: un clic lì non prende lottatori.
    if (ospite && (bersaglio === ospite || (evento.composedPath && evento.composedPath().indexOf(ospite) >= 0))) return;
    raggioPresa = evento.pointerType === "touch" ? 30 : 16;
    const tel = telefonoSotto(evento.clientX, evento.clientY);
    const trovato = tel ? null : chiTrovo(evento.clientX, evento.clientY);
    if (tel) {
      presa.f = null; presa.tel = tel; presa.x = evento.clientX; presa.y = evento.clientY; presa.mosso = false;
      tel.stato = "preso"; tel.da = null;
      if (evento.preventDefault) evento.preventDefault();
      if (evento.stopPropagation) evento.stopPropagation();
      radiceHtml("add", "ring-trascina");
      riparti();
      return;
    }
    if (!trovato) return;
    const [f, punto] = trovato;
    presa.f = f; presa.punto = punto; presa.x = evento.clientX; presa.y = evento.clientY; presa.mosso = false;
    if (f.tiene) molla(f);
    if (f.tenuto && f.tenuto.da) molla(f.tenuto.da);
    f.paracadute = 0;
    f.preso = punto; f.azione = null; f.scalata = null; f.forza = 0;
    // In mano passa attraverso gli elementi, come un oggetto sollevato:
    // torna solido appena lasciato, quando non ne ha più nessuno addosso.
    f.fantasma = true;
    if (evento.preventDefault) evento.preventDefault();
    if (evento.stopPropagation) evento.stopPropagation();
    radiceHtml("add", "ring-trascina");
    riparti();
  }

  function muovi(evento) {
    if (presa.f || presa.tel) {
      if (Math.hypot(evento.clientX - presa.x, evento.clientY - presa.y) > 2) presa.mosso = true;
      presa.x = evento.clientX; presa.y = evento.clientY;
      if (evento.preventDefault) evento.preventDefault();
      return;
    }
    if (fermo || evento.pointerType === "touch") return;
    raggioPresa = 16;
    radiceHtml(qualcosaSotto(evento.clientX, evento.clientY) ? "add" : "remove", "ring-presa");
  }

  function lascia() {
    if (presa.tel) {
      const t = presa.tel;
      presa.tel = null;
      t.stato = "volo"; t.protetto = 0; t.da = null; t.lanciatore = null; t.cool = 6; t.va = caso(-0.3, 0.3);
      t.armato = !!SPECIALI[t.tipo];
      if (presa.mosso) { appenaLanciato = true; setTimeout(() => { appenaLanciato = false; }, 0); }
      radiceHtml("remove", "ring-trascina");
      return;
    }
    const f = presa.f;
    if (!f) return;
    presa.f = null;
    f.preso = null;
    // Lasciato sopra un elemento con i piedi un po' dentro: lo si posa
    // sopra, invece di farlo cadere attraverso. Solo se l'affondo è poco:
    // un lottatore lasciato a metà di un paragrafo ci cade attraverso.
    let su = 0;
    for (const n in f.p) {
      const pt = f.p[n];
      for (const o of ostacoli) {
        if (pt.x > o.l - pt.r && pt.x < o.r + pt.r && pt.y > o.t - pt.r && pt.y < o.b + pt.r) {
          su = Math.max(su, pt.y - (o.t - pt.r));
        }
      }
    }
    if (su > 0 && su < 40 * S) {
      for (const n in f.p) { f.p[n].y -= su; f.p[n].oy -= su; }
    }
    if (su < 40 * S) f.fantasma = dentroQualcosa(f);
    // Floscio finché non si ferma: poi si rialza da solo.
    f.ko = Math.max(f.ko, 40);
    f.inVolo = true;
    if (presa.mosso) {
      appenaLanciato = true;
      setTimeout(() => { appenaLanciato = false; }, 0);
      f.lanciato = 70;
    }
    radiceHtml("remove", "ring-trascina");
  }

  // Un lottatore portato col puntatore (o appena lanciato) è un'arma: se
  // arriva veloce addosso all'altro, lo colpisce.
  function colpoDaMano(f, altro) {
    if (f.colpoMano > 0) f.colpoMano--;
    if (f.lanciato > 0) f.lanciato--;
    if (!(f.preso || f.lanciato > 0) || f.colpoMano > 0 || f.esploso) return;
    if (!altro || altro.esploso || altro.preso || altro.ko > 0 && !altro.inVolo) return;
    const ref = f.preso ? f.p[f.preso] : f.p.bacino;
    const vx = ref.x - ref.ox, vy = ref.y - ref.oy, v = Math.hypot(vx, vy);
    if (v < 4 * S) return;
    for (const n of ["testa", "collo", "bacino", "manoA", "manoD", "piedeA", "piedeD"]) {
      const q = f.p[n];
      for (const m of ["testa", "collo", "bacino"]) {
        const b = altro.p[m];
        if (Math.hypot(q.x - b.x, q.y - b.y) < q.r + b.r + 5 * S) {
          const colpitore = Object.create(f);
          colpitore.dir = Math.sign(vx) || f.dir; colpitore.azione = null;
          const forza = Math.min(7.5, 2.4 + v / (1.6 * S));
          colpisci(colpitore, altro, forza, (q.x + b.x) / 2, (q.y + b.y) / 2, forza > 5.5 ? "SBONK!" : "TONK!");
          for (const k in altro.p) { altro.p[k].ox -= vx * 0.35; altro.p[k].oy -= vy * 0.35; }
          altro.inVolo = true; altro.ko = Math.max(altro.ko, forza > 5 ? 30 : 0);
          f.colpoMano = 22; f.dolore = 12;
          return;
        }
      }
    }
  }

  function radiceHtml(come, classe) {
    const radice = document.documentElement;
    if (radice && radice.classList) radice.classList[come](classe);
  }

  window.addEventListener("pointerdown", prendi, { capture: true, passive: false });
  window.addEventListener("pointermove", muovi, { capture: true, passive: false });
  window.addEventListener("pointerup", lascia, { capture: true });
  window.addEventListener("pointercancel", lascia, { capture: true });
  // Sul telefono il dito che prende un lottatore non deve far scorrere la pagina.
  window.addEventListener("touchstart", (e) => {
    const t = e.touches && e.touches[0];
    raggioPresa = 30;
    if (t && !fermo && qualcosaSotto(t.clientX, t.clientY)) e.preventDefault();
  }, { passive: false });
  // Finché si tiene qualcosa col dito la pagina non deve scorrere.
  window.addEventListener("touchmove", (e) => {
    if ((presa.f || presa.tel) && e.cancelable) e.preventDefault();
  }, { passive: false });
  // Un lancio che finisce sopra un collegamento non lo deve aprire.
  window.addEventListener("click", (e) => {
    if (appenaLanciato) { e.preventDefault(); e.stopPropagation(); }
  }, { capture: true });

  // --- Un passo di fisica (60 al secondo) ------------------------------
  const GRAVITA = 0.42;
  const VELOCITA_MAX = 15;

  // CHI È IN PIEDI usa gli elementi della pagina come PIATTAFORME (02/10/2026):
  // ci si posa da sopra, e per il resto il corpo ci passa davanti. Prima ogni
  // punto del corpo urtava ogni lato di ogni elemento: su una pagina vera, con
  // tasti, campi e immagini all'altezza della testa, i lottatori restavano
  // piegati o incastrati in fondo alla finestra. Chi vola via dopo un colpo o
  // è a terra, invece, urta e rimbalza su tutti i lati come prima.
  function urta(f, pt, piattaforma) {
    const r = pt.r;
    let urto = 0;
    const prima = Math.hypot(pt.x - pt.ox, pt.y - pt.oy);
    if (piattaforma) {
      for (const o of ostacoli) {
        if (pt.x < o.l - r || pt.x > o.r + r) continue;
        // Solo scendendo, e solo se un attimo prima si era sopra il bordo alto.
        if (pt.oy <= o.t - r + 1 && pt.y > o.t - r) {
          const vx = pt.x - pt.ox, vy = pt.y - pt.oy;
          pt.y = o.t - r; if (vy > 0) pt.oy = pt.y; pt.ox = pt.x - vx * 0.7;
          urto = Math.max(urto, prima);
        }
      }
      return urto;
    }
    for (const o of ostacoli) {
      const dentroX = pt.x >= o.l - r && pt.x <= o.r + r;
      // Attraversato in un passo solo (un lancio veloce su una riga sottile):
      // conta come urto sul lato da cui arrivava.
      if (dentroX && pt.oy <= o.t - r + 0.5 && pt.y > o.b + r) { pt.y = o.t - r + 0.01; }
      else if (dentroX && pt.oy >= o.b + r - 0.5 && pt.y < o.t - r) { pt.y = o.b + r - 0.01; }
      if (pt.x < o.l - r || pt.x > o.r + r || pt.y < o.t - r || pt.y > o.b + r) continue;
      const vx = pt.x - pt.ox, vy = pt.y - pt.oy;
      // Da che parte è entrato: dalla posizione di prima, non dalla
      // penetrazione minima, sennò una riga sottile si attraversa.
      let lato;
      if (pt.oy <= o.t - r + 1) lato = "su";
      else if (pt.oy >= o.b + r - 1) lato = "giu";
      else if (pt.ox <= o.l - r + 1) lato = "sx";
      else if (pt.ox >= o.r + r - 1) lato = "dx";
      else {
        const m = Math.min(pt.y - (o.t - r), (o.b + r) - pt.y, pt.x - (o.l - r), (o.r + r) - pt.x);
        lato = m === pt.y - (o.t - r) ? "su" : m === (o.b + r) - pt.y ? "giu"
             : m === pt.x - (o.l - r) ? "sx" : "dx";
      }
      if (lato === "su") { pt.y = o.t - r; if (vy > 0) pt.oy = pt.y; pt.ox = pt.x - vx * 0.7; }
      else if (lato === "giu") { pt.y = o.b + r; if (vy < 0) pt.oy = pt.y; }
      else if (lato === "sx") { pt.x = o.l - r; pt.ox = pt.x + Math.max(0, vx) * 0.3; }
      else { pt.x = o.r + r; pt.ox = pt.x + Math.min(0, vx) * 0.3; }
      urto = Math.max(urto, prima);
    }
    return urto;
  }

  function scambiaGambe(f) {
    for (const [a, d] of [["piedeA", "piedeD"], ["ginocchioA", "ginocchioD"]]) {
      const A = f.p[a], D = f.p[d];
      for (const k of ["x", "y", "ox", "oy"]) { const t = A[k]; A[k] = D[k]; D[k] = t; }
    }
  }
  // Le ginocchia che si DISEGNANO: fra l'anca e il piede, piegate sempre dalla
  // parte della faccia (o in su, a gamba distesa per terra). Quelle della
  // fisica finivano spesso piegate all'indietro. Da K.O. valgono quelle vere:
  // un corpo abbandonato si piega come capita.
  const COSCIA = 15.2, STINCO = 14.5;
  function ginocchia(f) {
    const p = f.p, k = f.ko > 0 ? 0 : Math.max(0, Math.min(1, f.forza * 1.5));
    const una = (g, piede) => {
      if (k <= 0) return g;
      const hx = p.bacino.x, hy = p.bacino.y, dx = piede.x - hx, dy = piede.y - hy, lun = Math.hypot(dx, dy) || 1;
      const L1 = COSCIA * S, L2 = STINCO * S, d = Math.max(Math.abs(L1 - L2) + 0.5, Math.min(L1 + L2 - 0.01, lun));
      const ux = dx / lun, uy = dy / lun;
      const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d), alto = Math.sqrt(Math.max(0, L1 * L1 - a * a));
      let nx = -uy, ny = ux;
      if (Math.abs(nx) > 0.25 ? nx * f.dir < 0 : ny * verso > 0) { nx = -nx; ny = -ny; }
      const ix = hx + ux * a + nx * alto, iy = hy + uy * a + ny * alto;
      return { x: g.x + (ix - g.x) * k, y: g.y + (iy - g.y) * k };
    };
    return [una(p.ginocchioA, p.piedeA), una(p.ginocchioD, p.piedeD)];
  }

  function dentroQualcosa(f) {
    for (const n in f.p) {
      const pt = f.p[n];
      for (const o of ostacoli) {
        if (pt.x > o.l - pt.r && pt.x < o.r + pt.r && pt.y > o.t - pt.r && pt.y < o.b + pt.r) return true;
      }
    }
    return false;
  }

  // --- Particelle: scintille, polvere, stelline -------------------------
  function scintille(x, y, n, colore) {
    for (let i = 0; i < n && particelle.length < 160; i++) {
      const a = caso(0, Math.PI * 2), v = caso(1.5, 5) * S;
      particelle.push({ tipo: "scintilla", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - S,
                        vita: Math.round(caso(12, 22)), max: 22, colore });
    }
  }
  function polvere(x, y, n) {
    for (let i = 0; i < n && particelle.length < 160; i++) {
      particelle.push({ tipo: "polvere", x: x + caso(-5, 5) * S, y, vx: caso(-1.2, 1.2) * S,
                        vy: caso(-0.9, -0.2) * S, vita: Math.round(caso(16, 28)), max: 28, colore: "#b9b4ab" });
    }
  }
  function schegge(x, y, n, colore) {
    for (let i = 0; i < n && particelle.length < 160; i++) {
      const a = caso(0, Math.PI * 2), v = caso(1, 4) * S;
      particelle.push({ tipo: "scheggia", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 2 * S,
                        vita: Math.round(caso(26, 44)), max: 44, colore, rot: caso(0, 6) });
    }
  }
  function nota(f) {
    if (particelle.length >= 170) return;
    const t = f.p.testa;
    particelle.push({ tipo: "nota", x: t.x + caso(-12, 12) * S, y: t.y - 14 * S, vx: caso(-0.4, 0.4) * S, vy: -caso(0.5, 0.9) * S,
                      vita: 55, max: 55, testo: Math.random() < 0.5 ? "\u266A" : "\u266B",
                      colore: ["#e0447a", "#2f72e0", "#2e9e6b", "#ec8a3a"][Math.floor(Math.random() * 4)] });
  }
  function aggiornaParticelle() {
    for (const q of particelle) {
      q.x += q.vx; q.y += q.vy; q.vita--;
      if (q.tipo === "onda" || q.tipo === "lampo" || q.tipo === "vento" || q.tipo === "zip" || q.tipo === "linea" || q.tipo === "taglio") continue;
      if (q.tipo === "mote") {
        // Un granello d'energia che vola verso la sfera che si sta formando.
        const s = q.verso && q.verso.sfera;
        if (!s) { q.vita = Math.min(q.vita, 6); continue; }
        const dx = s.x - q.x, dy = s.y - q.y, d = Math.hypot(dx, dy) || 1, v = Math.min(d, 9 * S);
        q.x += dx / d * v; q.y += dy / d * v;
        if (d < s.r) q.vita = 0;
        continue;
      }
      if (q.tipo === "nota") { q.vx = q.vx * 0.98 + Math.sin(q.vita * 0.2) * 0.05 * S; continue; }
      if (q.tipo === "fuoco") { q.vx *= 0.9; q.vy = q.vy * 0.9 - 0.04 * S; q.r *= 1.03; continue; }
      if (q.tipo === "fumo") { q.vx *= 0.97; q.vy *= 0.985; q.r *= 1.012; continue; }
      if (q.tipo === "brace") { q.vx *= 0.98; q.vy += 0.06 * S * verso; if (q.y > pavimento) q.vita = 0; continue; }
      if (q.tipo === "detrito" || q.tipo === "pezzetto" || q.tipo === "goccia" || q.tipo === "pioggia" || q.tipo === "fiocco") {
        if (q.tipo === "detrito" || q.tipo === "pezzetto") { q.vy += 0.32 * S * moltG * verso; q.rot += q.va; }
        else if (q.tipo === "goccia") q.vy += 0.3 * S * moltG * verso;
        else if (q.tipo === "fiocco") q.x += Math.sin(q.fase + q.vita * 0.03) * 0.4 * S;
        // Dove tocca: il pavimento o il bordo alto di un elemento della pagina.
        let su = q.y >= pavimento - 1 ? pavimento - 1 : null;
        if (su === null) for (const o of ostacoli) if (q.x > o.l && q.x < o.r && q.y >= o.t && q.y - q.vy < o.t + 1) { su = o.t; break; }
        if (su === null) { if (q.x < 0 || q.x > W) { if (q.tipo === "detrito" || q.tipo === "pezzetto") { q.vx = -q.vx * 0.6; q.x = Math.max(0, Math.min(W, q.x)); } else q.vita = 0; } continue; }
        if (q.tipo === "detrito" || q.tipo === "pezzetto") {
          q.y = su; q.vy = Math.abs(q.vy) > 1.2 * S ? -Math.abs(q.vy) * 0.42 : 0; q.vx *= 0.7; q.va *= 0.7;
        } else {
          q.vita = 0;
          if (q.tipo === "goccia") macchia(q.x, su, q.r, q.colore);
          else if (q.tipo === "fiocco") { if (su === pavimento - 1) cumulo = Math.min(7 * S, cumulo + 0.025 * S); }
          else if (Math.random() < 0.3 && particelle.length < MAX_PARTICELLE) {
            particelle.push({ tipo: "scintilla", x: q.x, y: su, vx: caso(-1, 1) * S, vy: -caso(0.5, 1.5) * S, vita: 8, max: 8, colore: "#9cc3ee" });
          }
        }
        continue;
      }
      if (q.tipo === "scintilla") { q.vx *= 0.93; q.vy = q.vy * 0.93 + 0.12 * S; }
      else if (q.tipo === "polvere") { q.vx *= 0.96; q.vy *= 0.96; }
      else if (q.tipo === "fiamma") { q.vx *= 0.94; q.vy *= 0.97; }
      else { q.vy += 0.3 * S * moltG * verso; q.rot += 0.3; if (q.y > pavimento) { q.y = pavimento; q.vy *= -0.4; q.vx *= 0.7; } }
    }
    particelle = particelle.filter((q) => q.vita > 0);
  }

  // --- Gli oggetti che girano per la pagina -----------------------------
  // Telefoni, smartwatch, tablet e portatili (01/10/2026, su richiesta); dopo
  // 70 secondi anche pistole e spade. Ogni oggetto ha la sua sagoma, un peso
  // (un portatile fa più male di un orologio) e uno schermo dove si crepa.
  const FORME = {
    classico: { w: 8, h: 15, peso: 1 }, grande: { w: 9.5, h: 19, peso: 1.1 },
    pieghevole: { w: 12, h: 13, peso: 1.1 }, orologio: { w: 7, h: 8, peso: 0.7 },
    tablet: { w: 17, h: 23, peso: 1.3 }, pc: { w: 24, h: 17, peso: 1.6 },
    duo: { w: 13, h: 15, peso: 1.2 }, bomba: { w: 11, h: 11, peso: 1.2 },
    fumogeno: { w: 7, h: 13, peso: 0.6 }, barattolo: { w: 10, h: 13, peso: 0.7 },
    pistola: { w: 15, h: 9, peso: 1, arma: true }, spada: { w: 32, h: 6, peso: 1, arma: true },
  };
  const COLORI_TEL = ["#2b2f3a", "#c9ced8", "#1f6fd1", "#d1493a", "#2e9e6b", "#8a63d2"];
  const COLORI_PC = ["#b8bec9", "#3a3f4a", "#d9d4cc"];
  const eArma = (t) => !!(t && FORME[t.tipo] && FORME[t.tipo].arma);
  // Fumogeni e barattoli: non fanno male da soli, ma lanciati si aprono.
  const SPECIALI = { fumogeno: 1, barattolo: 1 };
  const ELEMENTI = { fuoco: { nome: "TIZZO", colore: "#ff7a1a" }, scossa: { nome: "ZIP", colore: "#ffd400" }, acqua: { nome: "BOLLA", colore: "#3aa0ff" } };
  const oggettoACaso = () => scegli([[3, "fumogeno"], [5, "barattolo"]].concat(libero("armi") ? [[2, "pistola"], [2, "spada"], [2, "bomba"]] : []));

  function scegliForma() {
    if (senzaTelefoni) return scegli([[3, "fumogeno"], [5, "barattolo"]]);
    const telefono = () => scegli([[50, "classico"], [30, "grande"], [20, "pieghevole"]]);
    if (tempo >= CALMA && Math.random() < 0.16) return Math.random() < 0.65 ? "barattolo" : "fumogeno";
    if (tempo < CALMA) return Math.random() < 0.3 ? "orologio" : telefono();
    const q = scegli([[40, "telefono"], [20, "orologio"], [20, "tablet"], [20, "pc"]]);
    return q === "telefono" ? telefono() : q;
  }

  function nuovoTelefono(x, y, vx, vy, forma) {
    let el = null;
    if (forma && forma.indexOf("barattolo-") === 0) { el = forma.slice(10); forma = "barattolo"; }
    const tipo = forma && FORME[forma] ? forma : scegliForma();
    const F = FORME[tipo], w = F.w * S, h = F.h * S;
    let sch;
    if (F.arma || tipo === "bomba" || SPECIALI[tipo]) sch = null;
    else if (tipo === "tablet") sch = [-w / 2 + 1.6 * S, -h / 2 + 1.6 * S, w - 3.2 * S, h - 3.2 * S];
    else if (tipo === "orologio") sch = [-w / 2 + 1 * S, -h / 2 + 1 * S, w - 2 * S, h - 2 * S];
    else if (tipo === "pc") sch = [-w / 2 + 1.4 * S, -h / 2 + 1.4 * S, w - 2.8 * S, h * 0.68 - 2.8 * S];
    else sch = [-w / 2 + 1.1 * S, -h / 2 + 1.5 * S, w - 2.2 * S, h - 3 * S];
    const colori = tipo === "pc" || tipo === "tablet" ? COLORI_PC : COLORI_TEL;
    telefoni.push({ x, y, ox: x - vx, oy: y - vy, a: caso(0, 6.28), va: caso(-0.15, 0.15), tipo,
                    w, h, r: Math.max(5, Math.min(11, Math.max(F.w, F.h) * 0.42)) * S, sch, peso: F.peso,
                    stato: "libero", da: null, protetto: 0, cool: 0, apre: 1, fine: 0, morto: false, miccia: 0,
                    ultimo: null, crepe: 0, rotture: [], entra: 0, isolato: 0, scende: 0,
                    colore: tipo === "duo" ? "#d9d4cc" : colori[Math.floor(Math.random() * colori.length)] });
    if (tipo === "barattolo") telefoni[telefoni.length - 1].el = ELEMENTI[el] ? el : scegli([[1, "fuoco"], [1, "scossa"], [1, "acqua"]]);
    if (telefoni.length > 7) {
      const vecchio = telefoni.findIndex((t) => t.stato === "libero");
      if (vecchio >= 0) telefoni.splice(vecchio, 1);
    }
    return telefoni[telefoni.length - 1];
  }

  // GLI OGGETTI ENTRANO ANCHE DAI LATI (02/10/2026, su richiesta). Su certe
  // pagine quelli caduti dall'alto si fermavano tutti sulla testata o sul
  // primo titolo, dove nessuno arriva. Circa una volta su due arrivano da un
  // bordo, con un lancio morbido che li posa all'altezza dei lottatori; mentre
  // entrano non fanno male a nessuno.
  function faEntrare(forma, xAlto, vxAlto) {
    const vivi = lottatori.filter((f) => f.p && !f.esploso);
    if (!vivi.length || verso < 0 || Math.random() < 0.45) return nuovoTelefono(xAlto, -16 * S, vxAlto, 0, forma);
    const da = Math.random() < 0.5 ? -1 : 1;                           // −1: dal bordo sinistro
    const base = Math.max.apply(null, vivi.map((f) => f.base)), centro = vivi.reduce((t, f) => t + f.p.bacino.x, 0) / vivi.length;
    const x0 = da < 0 ? 0 : W, y0 = Math.max(30 * S, base - caso(70, 170) * S);
    const tx = Math.max(40 * S, Math.min(W - 40 * S, centro + caso(-170, 170) * S)), ty = base - 10 * S, T = caso(38, 58);
    const lim = VELOCITA_MAX * S * 0.9;
    const vx = Math.max(-lim, Math.min(lim, (tx - x0) / T));
    const vy = Math.max(-lim * 0.6, (ty - y0) / T - 0.5 * GRAVITA * S * moltG * T);
    const t = nuovoTelefono(x0, y0, vx, vy, forma);
    t.entra = 24; t.cool = Math.round(T) + 12;
    return t;
  }

  function velocitaTel(t) { return Math.hypot(t.x - t.ox, t.y - t.oy); }

  function telefonoVicino(f) {
    let migliore = null, d0 = 260 * S;
    for (const t of telefoni) {
      if (t.stato !== "libero" || velocitaTel(t) > 2 * S || t.tipo === "duo") continue;
      if (Math.abs(t.y - (f.base - verso * 6 * S)) > 22 * S) continue;
      const d = Math.abs(t.x - f.cx);
      if (d < d0) { d0 = d; migliore = t; }
    }
    return migliore;
  }

  function lasciaArma(f) {
    const t = f.arma;
    f.arma = null;
    if (t) { t.stato = "libero"; t.da = null; t.ox = t.x; t.oy = t.y + 1 * S; t.va = caso(-0.2, 0.2); }
  }

  function lasciaCadere(f) {
    const t = f.tel;
    f.tel = null;
    if (t && t.stato === "portato") { t.stato = "libero"; t.da = null; t.ox = t.x; t.oy = t.y; }
  }

  function lanciaTelefono(f, altro) {
    const t = f.tel;
    f.tel = null;
    if (!t) return;
    t.stato = "volo"; t.protetto = 14; t.da = f; t.lanciatore = f; t.armato = !!SPECIALI[t.tipo];
    const T = caso(32, 44);
    const tx = altro.p.collo.x + caso(-7, 7) * S, ty = altro.p.collo.y + caso(-7, 7) * S;
    let vx = (tx - t.x) / T, vy = (ty - t.y) / T - 0.5 * GRAVITA * S * moltG * verso * T;
    const lim = VELOCITA_MAX * S * 0.9;
    vx = Math.max(-lim, Math.min(lim, vx)); vy = Math.max(-lim, Math.min(lim * 0.5, vy));
    t.ox = t.x - vx; t.oy = t.y - vy; t.va = f.dir * caso(0.25, 0.5);
    scrivi("TIÈ!", f.p.manoA.x, f.p.manoA.y - 12 * S, false);
  }

  function rimbalzaTel(t, vx, vy) {
    // Solo contro il pavimento, gli elementi della pagina e i bordi.
    const r = t.r;
    let urto = 0;
    const rim = (nvx, nvy, forza) => {
      t.ox = t.x - nvx; t.oy = t.y - nvy; urto = Math.max(urto, forza);
      t.va = (t.va + (nvx * 0.05 - nvy * 0.02)) * 0.8 + caso(-0.05, 0.05);
    };
    if (t.y > pavimento - r) {
      t.y = pavimento - r;
      rim(vx * 0.86, vy > 1.1 * S ? -vy * 0.45 : 0, Math.abs(vy));
    }
    for (const o of ostacoli) {
      if (t.scende > 0) break;                     // sta scivolando giù dall'elemento su cui era rimasto
      if (t.x < o.l - r || t.x > o.r + r || t.y < o.t - r || t.y > o.b + r) continue;
      if (t.oy <= o.t - r + 1) { t.y = o.t - r; rim(vx * 0.86, vy > 1.1 * S ? -vy * 0.45 : 0, Math.abs(vy)); }
      else if (t.oy >= o.b + r - 1) { t.y = o.b + r; rim(vx, Math.abs(vy) * 0.3, Math.abs(vy)); }
      else if (t.ox <= o.l - r + 1) { t.x = o.l - r; rim(-Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
      else if (t.ox >= o.r + r - 1) { t.x = o.r + r; rim(Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    }
    if (t.entra > 0) { /* sta entrando da un bordo: il bordo non lo ferma */ }
    else if (t.x < r) { if (-vx > 12.5 * S) danneggiaBordo("sinistra", t.y, 0.8); t.x = r; rim(Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    else if (t.x > W - r) { if (vx > 12.5 * S) danneggiaBordo("destra", t.y, 0.8); t.x = W - r; rim(-Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    if (t.y < r) {
      if (-vy > 12.5 * S) danneggiaBordo("tetto", t.x, 0.8);
      t.y = r;
      if (verso < 0) rim(vx * 0.86, vy < -1.1 * S ? -vy * 0.45 : 0, Math.abs(vy));
      else rim(vx, Math.abs(vy) * 0.3, 0);
    }
    return urto;
  }

  function aggiornaTelefoni() {
    for (const t of telefoni) {
      if (t.protetto > 0) t.protetto--;
      if (t.cool > 0) t.cool--;
      if (t.entra > 0) t.entra--;
      if (t.scende > 0) t.scende--;
      if (t.tipo === "bomba") {
        if (!t.miccia && (t.stato === "portato" || t.stato === "preso")) t.miccia = t.stato === "preso" ? 300 : 150;
        if (t.miccia > 0) {
          if (--t.miccia <= 0) { scoppia(t); continue; }
          if (passi % 3 === 0 && particelle.length < MAX_PARTICELLE) {
            const ax = t.x + Math.cos(t.a - 0.9) * 7 * S, ay = t.y + Math.sin(t.a - 0.9) * 7 * S;
            particelle.push({ tipo: "scintilla", x: ax, y: ay, vx: caso(-1, 1) * S, vy: -caso(0.5, 1.5) * S, vita: 10, max: 10, colore: "#ffd84a" });
          }
        }
      }
      if (t.stato === "preso") {
        t.ox = t.x; t.oy = t.y;
        t.x += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, presa.x - t.x));
        t.y += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, presa.y - t.y));
        t.a += 0.04;
        continue;
      }
      if (t.stato === "portato") {
        const f = t.da, m = f && f.p.manoA;
        if (!f || f.tel !== t || !m) { t.stato = "libero"; continue; }
        t.x = t.ox = m.x + f.dir * 0.5 * S; t.y = t.oy = m.y - Math.max(5 * S, t.h * 0.45); t.a = f.dir * 0.2;
        if (t.tipo === "duo") { t.apre = Math.min(1, t.apre + 0.07); t.a = 0; }
        continue;
      }
      if (t.stato === "impugnato") {
        // In mano: l'arma segue l'avambraccio, come se lo continuasse.
        const f = t.da;
        if (!f || f.arma !== t) { t.stato = "libero"; continue; }
        const g = f.p.gomitoA, m = f.p.manoA;
        t.x = t.ox = m.x; t.y = t.oy = m.y;
        t.a = Math.atan2(m.y - g.y, m.x - g.x);
        continue;
      }
      let vx = (t.x - t.ox) * 0.995, vy = (t.y - t.oy) * 0.995;
      const v = Math.hypot(vx, vy), lim = VELOCITA_MAX * S * 1.1;
      if (v > lim) { vx *= lim / v; vy *= lim / v; }
      t.ox = t.x; t.oy = t.y;
      t.x += vx; t.y += vy + GRAVITA * S * moltG * verso;
      t.a += t.va;
      const urto = rimbalzaTel(t, vx, vy);
      // Un fumogeno o un barattolo lanciato si apre dove sbatte.
      if (t.armato && urto > 3 * S && apri(t)) continue;
      if (urto > 13.5 * S && t.y > pavimento - t.r - 1) danneggiaStriscia(t.x, Math.min(1, urto / (VELOCITA_MAX * S)));
      if (urto > 4 * S) {
        polvere(t.x, t.y + t.r, 2);
        if (urto > 8 * S && t.crepe < 4) {
          t.crepe++; rompiSchermo(t); schegge(t.x, t.y, 4, eArma(t) ? "#d9dde6" : "#cfe9ff");
          scrivi(eArma(t) ? "CLANG!" : Math.random() < 0.5 ? "CRACK!" : "CLONK!", t.x, t.y - 14 * S, false);
        }
      }
      // Un lancio finisce quando l'oggetto si ferma: sul pavimento subito, altrove
      // (sopra un elemento della pagina) dopo qualche fotogramma da fermo. Prima,
      // fermo su un elemento, restava «in volo» per sempre e nessuno lo raccoglieva.
      if (t.stato === "volo") {
        t.lento = velocitaTel(t) < 1.2 * S ? (t.lento || 0) + 1 : 0;
        if ((t.lento > 0 && t.y > pavimento - t.r - 2) || t.lento > 8) {
          // Un fumogeno o un barattolo lanciato che si è posato piano si apre lo stesso.
          if (t.armato && apri(t)) continue;
          t.stato = "libero"; t.da = null; t.lento = 0;
        }
      }
      // Fermo su un elemento dove nessun lottatore arriva (la testata, un titolo
      // in alto): dopo cinque secondi scivola giù fino al primo appoggio sotto.
      if (t.stato === "libero" && verso > 0 && t.tipo !== "duo" && t.y < pavimento - t.r - 3 * S && velocitaTel(t) < 0.8 * S &&
          !lottatori.some((f) => !f.esploso && Math.abs(t.y - (f.base - 6 * S)) <= 22 * S)) {
        if (++t.isolato > 300) { t.isolato = 0; t.scende = 8; }
      } else t.isolato = 0;
      // Il pieghevole della mela che non ha preso nessuno si spegne in uno sbuffo.
      if (t.tipo === "duo" && t.stato === "libero" && ++t.fine > 90) { t.morto = true; polvere(t.x, t.y, 6); continue; }
      // Un telefono veloce che tocca un lottatore gli fa male.
      if (t.stato === "volo" || velocitaTel(t) > 6 * S) {
        for (const f of lottatori) {
          if (f.ko || f.preso || f.esploso || t.cool > 0 || (t.da === f && t.protetto > 0)) continue;
          if (t.ultimo === f && t.cool > 0) continue;
          for (const n of ["testa", "collo", "bacino"]) {
            const b = f.p[n];
            if (Math.hypot(t.x - b.x, t.y - b.y) < b.r + t.r * 0.9) {
              const att = t.da && t.da !== f ? t.da : { dir: Math.sign(t.x - t.ox) || 1, tipo: null, furia: 0 };
              if (t.armato && apri(t)) break;
              // Una bomba accesa che centra qualcuno scoppia subito.
              if (t.tipo === "bomba" && t.miccia > 0) { scoppia(t); break; }
              // Il pieghevole della mela: chi lo prende va in mille pezzi.
              if (t.tipo === "duo" && f !== t.lanciatore) {
                esplodiLottatore(f, att.tipo ? att : null);
                t.morto = true; break;
              }
              const forza = Math.max(3, Math.min(6.5, velocitaTel(t) / (2.2 * S))) * t.peso;
              const suoni = SUONI_OGGETTO[t.tipo] || SUONI_TEL;
              colpisci(att, f, forza, t.x, t.y, suoni[Math.floor(Math.random() * suoni.length)]);
              schegge(t.x, t.y, 6, t.colore);
              t.ox = t.x + (t.x - t.ox) * 0.3; t.oy = t.y - 2 * S; t.va = caso(-0.4, 0.4);
              t.cool = 20; t.ultimo = f; t.crepe = Math.min(5, t.crepe + 1); rompiSchermo(t);
              break;
            }
          }
          if (t.morto) break;
        }
      }
    }
    if (telefoni.some((t) => t.morto)) telefoni = telefoni.filter((t) => !t.morto);
  }

  // --- Pistole: proiettili da cartone -----------------------------------
  function spara(f, altro) {
    const t = f.arma;
    if (!t || t.tipo !== "pistola") return;
    f.colpiArma--;
    const fl = Math.cos(t.a) < 0 ? -1 : 1, ca = Math.cos(t.a), sa = Math.sin(t.a);
    const mx = t.x + ca * 12.5 * S + sa * 3.3 * S * fl, my = t.y + sa * 12.5 * S - ca * 3.3 * S * fl;
    const bx = altro.p.collo.x + caso(-7, 7) * S, by = altro.p.collo.y + caso(-9, 7) * S;
    const d = Math.hypot(bx - mx, by - my) || 1, v = 9.5 * S;
    proiettili.push({ x: mx, y: my, vx: (bx - mx) / d * v, vy: (by - my) / d * v, da: f, vita: 140 });
    scintille(mx, my, 6, "#ffe27a");
    for (let i = 0; i < 3 && particelle.length < 170; i++) {
      particelle.push({ tipo: "fiamma", x: mx, y: my, vx: f.dir * caso(0.5, 1.6) * S, vy: caso(-0.6, 0.6) * S,
                        vita: 8, max: 8, colore: ["#fff1a0", "#ffb62e"][i % 2] });
    }
    scrivi("BANG!", mx, my - 10 * S, false);
  }
  // La sfera gigante (lenta, insegue un po', esplode forte) e il disco
  // tagliente (veloce, dritto, taglia). Attraversano la pagina.
  function aggiornaSpeciale(b) {
    b.vita--;
    if (b.grande && b.bersaglio && !b.bersaglio.esploso) {
      const t = b.bersaglio.p.collo, d = Math.hypot(t.x - b.x, t.y - b.y) || 1, v = Math.hypot(b.vx, b.vy);
      b.vx += ((t.x - b.x) / d * v - b.vx) * 0.03; b.vy += ((t.y - b.y) / d * v - b.vy) * 0.03;
    }
    b.x += b.vx; b.y += b.vy;
    const r = b.grande ? b.r : 5 * S;
    if (b.grande) {
      let tocca = b.y + r * 0.7 > pavimento || b.x < r * 0.5 || b.x > W - r * 0.5 || b.y < r * 0.5 || b.vita <= 0;
      for (const f of lottatori) {
        if (f === b.da || f.esploso || f.preso) continue;
        for (const n of ["testa", "collo", "bacino"]) if (Math.hypot(f.p[n].x - b.x, f.p[n].y - b.y) < r + f.p[n].r) tocca = true;
      }
      if (tocca) {
        b.vita = 0;
        esplosione(b.x, Math.min(b.y, pavimento - 10 * S), 1.9, b.da, true);
        scrivi("KA-BOOOM!", b.x, Math.max(60, b.y - 50 * S), true);
      } else if (passi % 2 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "scintilla", x: b.x + caso(-1, 1) * r, y: b.y + caso(-1, 1) * r, vx: -b.vx * 0.3, vy: -b.vy * 0.3, vita: 14, max: 14, colore: b.colore });
      }
      return;
    }
    // Il disco.
    if (b.x < 0 || b.x > W) { danneggiaBordo(b.x < 0 ? "sinistra" : "destra", b.y, 0.8); b.vita = 0; return; }
    if (b.y < 0) { danneggiaBordo("tetto", b.x, 0.8); b.vita = 0; return; }
    if (b.y > pavimento - 2) { danneggiaStriscia(b.x, 0.6); scintille(b.x, pavimento - 2, 8, b.colore); b.vita = 0; return; }
    if (b.colpito) return;
    for (const f of lottatori) {
      if (f === b.da || f.ko || f.preso || f.esploso || f.tenuto) continue;
      for (const n of ["testa", "collo", "bacino"]) {
        const q = f.p[n];
        if (Math.hypot(q.x - b.x, q.y - b.y) < q.r + 7 * S) {
          b.colpito = true;
          const barriera = f.azione === "barriera";
          colpisci(b.da, f, 5, b.x, b.y, "ZAC!");
          if (barriera) { b.vita = 0; return; }
          if (!(eMela(f) && taglia(f, b.da))) smembra(f, b.x, b.y);
          return;
        }
      }
    }
  }

  function aggiornaProiettili() {
    const sbuffo = (b) => b.neve ? scintille(b.x, Math.min(b.y, pavimento - 1), 7, "#ffffff") : scintille(Math.max(0, Math.min(W, b.x)), Math.min(b.y, pavimento - 1), 4, "#ffe27a");
    for (const b of proiettili) {
      if (b.grande || b.disco) { aggiornaSpeciale(b); if (b.vita <= 0 && b.lamaDi) rientraLama(b.lamaDi); continue; }
      if (b.neve) b.vy += GRAVITA * S * moltG * verso * 0.6;
      b.x += b.vx; b.y += b.vy; b.vita--;
      if (b.y > pavimento - 1 || b.x < 0 || b.x > W || (b.y < 0 && !b.neve)) {
        b.vita = 0; sbuffo(b); continue;
      }
      for (const o of ostacoli) {
        if (b.x > o.l && b.x < o.r && b.y > o.t && b.y < o.b) { b.vita = 0; sbuffo(b); break; }
      }
      if (b.vita <= 0) continue;
      for (const f of lottatori) {
        if (f === b.da || f.ko || f.preso || f.esploso || f.tenuto) continue;
        for (const n of ["testa", "collo", "bacino"]) {
          const q = f.p[n];
          if (Math.hypot(q.x - b.x, q.y - b.y) < q.r + 4 * S) {
            // Una lama di energia rimanda indietro pallottole e sfere (non sempre).
            if (!b.neve && !b.incanto && !b.deviato && lamaPronta(f) && b.vx * f.dir < 0 && (f.azione === "para" || Math.random() < 0.55)) {
              b.vx = -b.vx; b.vy = caso(-2, 2) * S - b.vy * 0.3; b.da = f; b.deviato = true; b.vita = Math.max(b.vita, 60);
              b.x += b.vx * 2; b.y += b.vy * 2;
              scintille(b.x, b.y, 6, "#ffffff"); scrivi("TING!", b.x, b.y - 10 * S, false);
              break;
            }
            if (b.neve) { colpisci(b.da, f, 2.4, b.x, b.y, "SPLOF!"); sbuffo(b); }
            else if (b.incanto === "gelo") congela(f, b.da, b.x, b.y);
            else if (b.incanto === "piccolo") rimpicciolisci(f, b.da, b.x, b.y);
            else if (b.energia) { colpisci(b.da, f, 2.6, b.x, b.y, "ZAP!"); scintille(b.x, b.y, 6, b.colore); }
            else colpisci(b.da, f, 4.2, b.x, b.y, "BANG!");
            b.vita = 0; break;
          }
        }
        if (b.vita <= 0 || b.da === f) break;
      }
    }
    if (proiettili.length) proiettili = proiettili.filter((b) => b.vita > 0);
  }

  // --- Le armi segrete nel jetpack ---------------------------------------
  // La mela tira fuori il suo pieghevole, il robot una bomba già accesa:
  // tutti e due, se prendono in pieno l'altro, lo fanno a pezzi.
  function estraiDuo(f) {
    const m = f.p.manoA;
    const t = nuovoTelefono(m.x, m.y, 0, 0, f.tipo === "robot" ? "bomba" : "duo");
    t.stato = "portato"; t.da = f; t.apre = 0; t.a = 0;
    if (t.tipo === "bomba") t.miccia = 150;
    f.tel = t;
    scintille(m.x, m.y, 10, f.tipo === "robot" ? "#ffd84a" : "#d9c8ff");
  }

  // --- Un lottatore va in mille pezzi, e si rimonta -----------------------
  // Il robot si smonta in testa, busto, bulloni e arti; la mela in quattro
  // spicchi, picciolo con la foglia, occhi, braccia e gambe. I pezzi volano
  // con la fisica vera (rimbalzano su pagina e striscia), poi tornano a
  // posto uno alla volta, ognuno con un balzo ad arco.
  const ESPLOSO_VOLO = 170, ESPLOSO_PASSO = 9, ESPLOSO_RIMONTA = 28;
  const centroMela = (p) => corpoMela(p);
  function posaPezzo(pz, p) {
    const A = p[pz.a], B = pz.b ? p[pz.b] : null;
    if (pz.forma === "asta") return [(A.x + B.x) / 2, (A.y + B.y) / 2, Math.atan2(B.y - A.y, B.x - A.x), Math.hypot(B.x - A.x, B.y - A.y)];
    if (pz.forma === "spicchio" || pz.forma === "picciolo" || pz.forma === "occhio" || (pz.forma === "bombola" && pz.mela)) {
      // In coordinate del frutto: (u, v) in unità di raggio, ruotate col corpo.
      const c = centroMela(p), R = c.R, ca = Math.cos(c.ang), sa = Math.sin(c.ang);
      let u = pz.u, v = pz.v, ang = c.ang;
      if (pz.forma === "spicchio") { const a = pz.quarto * Math.PI / 2; u = Math.cos(a) * 0.6; v = Math.sin(a) * 0.6; ang += a; }
      return [c.x + (u * ca - v * sa) * R, c.y + (u * sa + v * ca) * R, ang, 0];
    }
    if (pz.forma === "busto" || pz.forma === "bombola") {
      const ang = Math.atan2(B.y - A.y, B.x - A.x) - Math.PI / 2, L = Math.hypot(B.x - A.x, B.y - A.y);
      let x = (A.x + B.x) / 2, y = (A.y + B.y) / 2;
      if (pz.forma === "bombola") { x += Math.cos(ang) * (pz.lato - pz.dir * 10.5) * S; y += Math.sin(ang) * (pz.lato - pz.dir * 10.5) * S; }
      return [x, y, ang, L];
    }
    if (pz.forma === "testa" || pz.forma === "capo") return [A.x, A.y, Math.atan2(A.y - B.y, A.x - B.x) + Math.PI / 2, 0];
    if (pz.forma === "antenna") return [A.x, A.y - 9 * S, 0, 0];
    if (pz.forma === "bullone") return [A.x + pz.off[0] * S, A.y + pz.off[1] * S, 0, 0];
    return [A.x, A.y, 0, 0];
  }
  function pezziDi(f) {
    const asta = (a, b, w, colore) => ({ forma: "asta", a, b, w: w * S, colore });
    if (stile) {
      // Un personaggio inventato va in pezzi come un pupazzo: niente sangue, e si rimonta.
      const A = aspetto(f);
      return [
        { forma: "scarpa", a: "piedeA", colore: A.scarpe }, { forma: "scarpa", a: "piedeD", colore: A.scarpe },
        asta("ginocchioA", "piedeA", 5, A.gambe), asta("ginocchioD", "piedeD", 5, A.gambe),
        asta("bacino", "ginocchioA", 5, A.gambe), asta("bacino", "ginocchioD", 5, A.gambe),
        { forma: "busto", a: "collo", b: "bacino", colore: A.tuta, liscio: true },
        asta("collo", "gomitoD", 4.2, A.maniche), asta("gomitoD", "manoD", 4.2, A.maniche),
        asta("collo", "gomitoA", 4.2, A.maniche), asta("gomitoA", "manoA", 4.2, A.maniche),
        { forma: "pugno", a: "manoD", colore: A.pelle }, { forma: "pugno", a: "manoA", colore: A.pelle },
        { forma: "capo", a: "testa", b: "collo", colore: A.pelle, capelli: A.cappello || A.capelli },
      ];
    }
    if (f.tipo === "mela") {
      const nero = "#111", dietro = -f.dir;
      return [
        { forma: "scarpa", a: "piedeA", colore: "#f7f7f7" }, { forma: "scarpa", a: "piedeD", colore: "#f7f7f7" },
        asta("ginocchioA", "piedeA", 3, nero), asta("ginocchioD", "piedeD", 3, nero),
        asta("bacino", "ginocchioA", 3, nero), asta("bacino", "ginocchioD", 3, nero),
        { forma: "spicchio", quarto: 0, colore: "#ffffff" }, { forma: "spicchio", quarto: 1, colore: "#ffffff" },
        { forma: "spicchio", quarto: 2, colore: "#ffffff" }, { forma: "spicchio", quarto: 3, colore: "#ffffff" },
        { forma: "bombola", mela: true, u: dietro * 1.15 - 0.19, v: 0.1, colore: "#7d8696" },
        { forma: "bombola", mela: true, u: dietro * 1.15 + 0.19, v: 0.1, colore: "#b3bbc9" },
        asta("collo", "gomitoD", 3, nero), asta("gomitoD", "manoD", 3, nero),
        asta("collo", "gomitoA", 3, nero), asta("gomitoA", "manoA", 3, nero),
        { forma: "guanto", a: "manoD", colore: "#1f56b8" }, { forma: "guanto", a: "manoA", colore: "#2f72e0" },
        { forma: "occhio", u: -0.34 + f.dir * 0.08, v: -0.16, colore: nero }, { forma: "occhio", u: 0.34 + f.dir * 0.08, v: -0.16, colore: nero },
        { forma: "picciolo", u: 0.06, v: -0.95, colore: "#6b4423" },
      ];
    }
    const T = tavolozza || ["#2fae74", "#1c6f4a", "#7dffd2", "#154d34"];
    return [
      { forma: "piede", a: "piedeA", colore: T[3] }, { forma: "piede", a: "piedeD", colore: T[3] },
      asta("ginocchioA", "piedeA", 5, T[0]), asta("ginocchioD", "piedeD", 5, T[1]),
      asta("bacino", "ginocchioA", 5, T[0]), asta("bacino", "ginocchioD", 5, T[1]),
      { forma: "busto", a: "collo", b: "bacino", colore: T[0] },
      { forma: "bombola", a: "collo", b: "bacino", colore: "#7d8696", lato: -2.6, dir: f.dir },
      { forma: "bombola", a: "collo", b: "bacino", colore: "#b3bbc9", lato: 2.6, dir: f.dir },
      asta("collo", "gomitoD", 4.4, T[1]), asta("gomitoD", "manoD", 4.4, T[1]),
      asta("collo", "gomitoA", 4.4, T[0]), asta("gomitoA", "manoA", 4.4, T[0]),
      { forma: "guanto", a: "manoD", colore: "#b92b22" }, { forma: "guanto", a: "manoA", colore: "#e03a2f" },
      { forma: "testa", a: "testa", b: "collo", colore: T[0] }, { forma: "antenna", a: "testa", colore: T[1] },
      { forma: "bullone", a: "collo", off: [3, 2], colore: "#9aa1ad" }, { forma: "bullone", a: "bacino", off: [-3, -2], colore: "#9aa1ad" },
      { forma: "bullone", a: "ginocchioA", off: [0, 0], colore: "#9aa1ad" },
    ];
  }
  function esplodiLottatore(f, att, senzaPunto) {
    if (f.esploso || !f.p) return;
    if (f.tel) lasciaCadere(f);
    if (f.arma) lasciaArma(f);
    if (f.tiene) molla(f);
    if (f.tenuto && f.tenuto.da) molla(f.tenuto.da);
    if (presa.f === f) { presa.f = null; radiceHtml("remove", "ring-trascina"); }
    f.preso = null; f.jet = 0; f.caos = 0; f.paracadute = 0; f.para = 0; f.azione = null; f.scalata = null;
    const p = f.p;
    const c = eMela(f) ? centroMela(p) : { x: (p.collo.x + p.bacino.x) / 2, y: (p.collo.y + p.bacino.y) / 2 };
    pezzi = pezzi.filter((pz) => pz.f !== f).concat(pezziDi(f).map((pz, i) => {
      const [x, y, ang, L] = posaPezzo(pz, p);
      const dx = x - c.x, dy = y - c.y, d = Math.hypot(dx, dy) || 1, v = caso(4, 10) * S;
      const vx = dx / d * v + caso(-2, 2) * S, vy = dy / d * v - caso(3, 7) * S;
      return Object.assign(pz, { f, x, y, ox: x - vx, oy: y - vy, ang, L, va: caso(-0.35, 0.35), ordine: i,
                                 casa: null, da: null, fatto: false });
    }));
    f.esploso = { t: 0, dir: f.dir, nuovo: null, x: c.x, base: pavimento };
    f.ko = 1e6; f.inVolo = false; f.dolore = 0; f.stordito = 0; f.segni = []; f.staccati = {}; f.morsi = []; f.taglio = null;
    arti = arti.filter((a) => a.f !== f);
    esplosione(c.x, c.y, 1.4, att);
    scossa = 18; fermoColpo = 10;
    schegge(c.x, c.y, 12, stile ? aspetto(f).tuta : f.tipo === "mela" ? "#ffffff" : (tavolozza || ["#2fae74"])[0]);
    if (eMela(f)) schizza(f, c.x, c.y, 10, 3);
    scrivi("KABOOM!", c.x, c.y - 40 * S, true);
    f.cratere = null; f.accecato = 0; f.sfera = null;
    if (senzaPunto) { salvaCervello(true); return; }
    const vincitore = att && att.tipo && att !== f ? att.tipo : altroTipo(f.tipo);
    risolviScommessa(vincitore);
    punteggio[vincitore]++;
    controllaFinale(vincitore, null, null);
    const chi = lottatori.find((l) => l.tipo === vincitore);
    if (chi && chi !== f && !chi.esploso) chi.daBallare = true;
    salvaCervello(true);
  }
  function rimbalzaPezzo(pz) {
    let vx = (pz.x - pz.ox) * 0.99, vy = (pz.y - pz.oy) * 0.99;
    pz.ox = pz.x; pz.oy = pz.y;
    pz.x += vx; pz.y += vy + GRAVITA * S * moltG * verso; pz.ang += pz.va;
    const r = 3.5 * S;
    if (pz.y > pavimento - r) { pz.y = pavimento - r; pz.oy = pz.y + Math.max(0, vy) * 0.4; pz.ox = pz.x - vx * 0.7; pz.va *= 0.7; }
    for (const o of ostacoli) {
      if (pz.x > o.l && pz.x < o.r && pz.y > o.t - r && pz.y < o.b && pz.oy <= o.t - r + 1) {
        pz.y = o.t - r; pz.oy = pz.y + Math.max(0, vy) * 0.4; pz.ox = pz.x - vx * 0.7; pz.va *= 0.7;
      }
    }
    if (pz.x < r) { pz.x = r; pz.ox = pz.x + Math.abs(vx) * 0.5; }
    if (pz.x > W - r) { pz.x = W - r; pz.ox = pz.x - Math.abs(vx) * 0.5; }
    if (pz.y < r) { pz.y = r; pz.oy = pz.y - Math.max(0, -vy) * 0.4; pz.ox = pz.x - vx * 0.7; }
  }
  function aggiornaEsplosione(f) {
    const e = f.esploso, miei = pezzi.filter((pz) => pz.f === f);
    e.t++;
    if (e.rientro) { if (e.t >= RIENTRO) rientra(f); return; }
    if (e.t === ESPLOSO_VOLO) {
      // Si rimonta dove è finito il pezzo più grosso, sul primo appoggio sotto.
      const centro = miei.find((pz) => pz.forma === "busto" || pz.forma === "spicchio") || miei[0];
      const x = Math.max(30 * S, Math.min(W - 30 * S, centro ? centro.x : W / 2));
      let base = pavimento;
      for (const o of ostacoli) if (x >= o.l && x <= o.r && o.t >= (centro ? centro.y : 0) - 4 * S && o.t < base) base = o.t;
      e.nuovo = crea(f.tipo, x, e.dir, base); e.x = x; e.base = base;
      for (const pz of miei) pz.casa = posaPezzo(pz, e.nuovo.p);
    }
    for (const pz of miei) {
      const inizio = ESPLOSO_VOLO + pz.ordine * ESPLOSO_PASSO;
      if (!pz.casa || e.t < inizio) { rimbalzaPezzo(pz); continue; }
      if (!pz.da) pz.da = [pz.x, pz.y, pz.ang, pz.L];
      const k = Math.min(1, (e.t - inizio) / ESPLOSO_RIMONTA), q = k * k * (3 - 2 * k);
      const arco = Math.sin(Math.PI * k) * 36 * S;
      let da = pz.casa[2] - pz.da[2];
      da = ((da + Math.PI) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) - Math.PI;
      pz.x = pz.da[0] + (pz.casa[0] - pz.da[0]) * q;
      pz.y = pz.da[1] + (pz.casa[1] - pz.da[1]) * q - arco;
      pz.ang = pz.da[2] + da * q; pz.L = pz.da[3] + (pz.casa[3] - pz.da[3]) * q;
      pz.ox = pz.x; pz.oy = pz.y;
      if (k >= 1 && !pz.fatto) { pz.fatto = true; scintille(pz.x, pz.y, 4, eRobot(f) ? "#7dffd2" : "#ffffff"); }
    }
    if (e.t >= ESPLOSO_VOLO + miei.length * ESPLOSO_PASSO + ESPLOSO_RIMONTA + 8) {
      const n = e.nuovo || crea(f.tipo, e.x, e.dir, e.base);
      f.p = n.p; f.aste = n.aste; f.cx = e.x; f.base = e.base; f.dir = e.dir;
      f.esploso = null; f.ko = 0; f.rialzo = 0; f.stordito = 30; f.danni = 0; f.koVero = false;
      f.inVolo = false; f.fantasma = false; f.azione = null; f.pensa = 20;
      pezzi = pezzi.filter((pz) => pz.f !== f);
      scintille(f.p.collo.x, f.p.collo.y, 14, eRobot(f) ? "#7dffd2" : "#ffffff");
    }
  }

  // --- La partita finisce a dieci (02/10/2026, su richiesta) -------------
  // Chi arriva a dieci K.O. chiude la partita col colpo che manda l'altro
  // FUORI DAL RING: l'azione si ferma un attimo sul colpo, il corpo parte
  // dritto verso il bordo della finestra, e dove esce si apre un ventaglio
  // di luce. Poi il conto riparte da zero e lo sconfitto rientra dall'alto.
  const TRAGUARDO = 10, RIENTRO = 150;
  const CORIANDOLI = ["#ff5a5f", "#ffcf3a", "#3ddc97", "#4aa8ff", "#c77dff", "#ffffff"];
  function controllaFinale(tipo, perdente, att) {
    if (finale || !tipo || punteggio[tipo] < TRAGUARDO) return;
    const chi = lottatori.find((l) => l.tipo === tipo);
    finale = { tipo, t: 0, q: 0, punti: punteggio.robot + "–" + punteggio.mela, perso: null, lampo: null,
               nome: stile ? ASPETTI[stile][tipo].nome : dici(tipo === "robot" ? "ROBOT" : "MELA"),
               colore: COLORI_ANIME[tipo] };
    if (chi && !chi.esploso) chi.daBallare = true;
    if (!perdente || !perdente.p || perdente.esploso || perdente.preso) return;
    if (perdente.tenuto && perdente.tenuto.da) molla(perdente.tenuto.da);
    if (perdente.tel) lasciaCadere(perdente);
    if (perdente.arma) lasciaArma(perdente);
    if (perdente.tiene) molla(perdente);
    const p = perdente.p, dir = (att && att.dir) || (chi && p.bacino.x < chi.p.bacino.x ? -1 : 1);
    perdente.tenuto = null; perdente.fuori = 1; perdente.ko = 1e6; perdente.inVolo = true; perdente.fantasma = true;
    perdente.jet = 0; perdente.caos = 0; perdente.paracadute = 0; perdente.para = 0; perdente.azione = null;
    perdente.scalata = null; perdente.cratere = null;
    for (const n in p) {
      const giro = n === "testa" || n === "collo" ? 2 : n.startsWith("piede") ? -2 : 0;      // parte ruotando un po'
      p[n].ox = p[n].x - dir * (25 + giro) * S; p[n].oy = p[n].y + verso * 13 * S;
    }
    finale.perso = perdente; finale.x = p.collo.x; finale.y = p.collo.y;
    fermoColpo = 24; scossa = 18;
  }
  function volaFuori(f) {
    const p = f.p;
    let esce = ++f.fuori > 80;
    for (const n in p) {
      const pt = p[n], vx = pt.x - pt.ox, vy = pt.y - pt.oy;
      pt.ox = pt.x; pt.oy = pt.y; pt.x += vx; pt.y += vy;
    }
    for (let giro = 0; giro < 3; giro++) {
      for (const [p1, p2, L] of f.aste) {
        const dx = p2.x - p1.x, dy = p2.y - p1.y, d = Math.hypot(dx, dy) || 0.001, c = (d - L) / d * 0.5;
        p1.x += dx * c; p1.y += dy * c; p2.x -= dx * c; p2.y -= dy * c;
      }
    }
    if (particelle.length < MAX_PARTICELLE) {
      particelle.push({ tipo: "fumo", x: p.bacino.x, y: p.bacino.y, vx: 0, vy: 0, vita: 20, max: 20, r: 6 * S, colore: "#ffffff" });
    }
    for (const n of ["testa", "bacino"]) {
      const pt = p[n];
      if (pt.x < 10 * S || pt.x > W - 10 * S || pt.y < 10 * S || (verso < 0 && pt.y > pavimento - 6 * S)) esce = true;
    }
    if (esce) esceDalRing(f);
  }
  function esceDalRing(f) {
    const b = f.p.bacino, vx = b.x - b.ox, vy = b.y - b.oy, v = Math.hypot(vx, vy) || 1;
    const x = Math.max(0, Math.min(W, b.x + vx * 1.5)), y = Math.max(0, Math.min(pavimento, b.y + vy * 1.5));
    if (finale) finale.lampo = { x, y, ux: -vx / v, uy: -vy / v, t: 0 };
    scossa = 26; fermoColpo = Math.max(fermoColpo, 4);
    const a0 = Math.atan2(-vy, -vx);
    for (let i = 0; i < 44 && particelle.length < MAX_PARTICELLE; i++) {
      const a = a0 + caso(-1, 1), vel = caso(3, 12) * S;
      particelle.push({ tipo: "detrito", x, y, vx: Math.cos(a) * vel, vy: Math.sin(a) * vel - 2 * S, vita: 130, max: 130, rot: 0,
                        va: caso(-0.4, 0.4), lato: caso(2.2, 4.6) * S, colore: CORIANDOLI[i % CORIANDOLI.length] });
    }
    if (x <= 1) danneggiaBordo("sinistra", y, 1); else if (x >= W - 1) danneggiaBordo("destra", y, 1); else if (y <= 1) danneggiaBordo("tetto", x, 1);
    // Sparisce (come chi va in pezzi) e rientra fra poco dal suo lato.
    for (const n in f.p) {
      const pt = f.p[n];
      pt.x = pt.ox = Math.max(8, Math.min(W - 8, pt.x)); pt.y = pt.oy = Math.max(8, Math.min(pavimento - 8, pt.y));
    }
    arti = arti.filter((a) => a.f !== f);
    f.esploso = { t: 0, dir: f.tipo === "robot" ? 1 : -1, nuovo: null, x: W * (f.tipo === "robot" ? 0.3 : 0.7), base: pavimento, rientro: true };
    f.fuori = 0; f.inVolo = false; f.fantasma = false; f.dolore = 0; f.stordito = 0; f.segni = []; f.staccati = {}; f.morsi = [];
    f.taglio = null; f.accecato = 0; f.sfera = null; f.cratere = null;
  }
  function rientra(f) {
    const e = f.esploso, n = crea(f.tipo, e.x, e.dir, pavimento);
    if (verso > 0) {
      const su = n.p.testa.y - 26 * S;
      for (const k in n.p) { n.p[k].y -= su; n.p[k].oy = n.p[k].y - 3 * S; }
    }
    f.p = n.p; f.aste = n.aste; f.cx = e.x; f.base = pavimento; f.dir = e.dir;
    f.esploso = null; f.ko = 40; f.rialzo = 0; f.stordito = 0; f.danni = 0; f.koVero = false;
    f.inVolo = verso > 0; f.fantasma = false; f.azione = null; f.pensa = 20;
    if (lame() && f.lama) accendiLama(f);
    scintille(f.p.collo.x, f.p.collo.y, 14, COLORI_ANIME[f.tipo]);
  }
  function aggiornaFinale() {
    if (!finale) return;
    finale.t++;
    if (finale.lampo) finale.lampo.t++;
    const p = finale.perso;
    if (p ? (!p.esploso && !p.fuori) || finale.t > 420 : finale.t > 210) {
      punteggio.robot = 0; punteggio.mela = 0; finale = null;
      scrivi("NUOVA PARTITA!", W / 2, H * 0.32, true);
    }
  }
  function disegnaFinale(sopra) {
    if (!finale) return;
    if (!sopra) {
      // Il colpo decisivo: per un attimo tutto il resto si spegne.
      if (finale.perso && finale.t < 2) {
        const k = Math.min(1, ++finale.q / 5);
        ctx.save(); ctx.fillStyle = "rgba(12,10,24," + 0.62 * k + ")"; ctx.fillRect(0, 0, W, H);
        ctx.translate(finale.x, finale.y); ctx.lineCap = "round";
        for (let i = 0; i < 28; i++) {
          const a = i * 2.399, r0 = (22 + (i * 37 % 23)) * S, r1 = r0 + (50 + (i * 53 % 170)) * S * k;
          ctx.strokeStyle = i % 3 ? "rgba(255,255,255,.8)" : finale.colore; ctx.lineWidth = (1 + i % 3) * S;
          ctx.beginPath(); ctx.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); ctx.lineTo(Math.cos(a) * r1, Math.sin(a) * r1); ctx.stroke();
        }
        ctx.restore();
      }
      return;
    }
    const z = finale.lampo;
    if (z && z.t < 64) {
      // Il ventaglio di luce dal punto in cui è uscito.
      const k = z.t / 64, L = Math.hypot(W, H) * 0.8 * Math.min(1, (z.t + 1) / 7), a0 = Math.atan2(z.uy, z.ux);
      ctx.save(); ctx.translate(z.x, z.y); ctx.globalAlpha = Math.max(0, 1 - k * k);
      for (let i = 0; i < 9; i++) {
        const a = a0 + (i - 4) * 0.21 + Math.sin(i * 7.3) * 0.05, lun = L * (0.5 + 0.5 * Math.abs(Math.sin(i * 2.7 + 1)));
        const larg = (0.05 + 0.03 * (i % 3)) * (1 - 0.6 * k);
        ctx.fillStyle = i % 2 ? CORIANDOLI[(i >> 1) % 5] : finale.colore;
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a - larg) * lun, Math.sin(a - larg) * lun);
        ctx.lineTo(Math.cos(a) * lun * 1.14, Math.sin(a) * lun * 1.14); ctx.lineTo(Math.cos(a + larg) * lun, Math.sin(a + larg) * lun);
        ctx.closePath(); ctx.fill();
      }
      const R = 110 * S * (1 - 0.5 * k), g = ctx.createRadialGradient(0, 0, 0, 0, 0, R);
      g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.5, "rgba(255,255,255,.55)"); g.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    // Il cartello: chi ha vinto e com'è finita.
    const tb = finale.t - (finale.perso ? 14 : 6);
    if (tb > 0) {
      const sc = 1 + 0.5 * Math.max(0, 1 - tb / 12), riga = Math.round(Math.min(30 * S, W / 13));
      ctx.save(); ctx.translate(W / 2, Math.max(70 * S, H * 0.3)); ctx.scale(sc, sc); ctx.globalAlpha = Math.min(1, tb / 6);
      ctx.textAlign = "center"; ctx.lineJoin = "round"; ctx.strokeStyle = "#141414";
      ctx.font = "800 " + riga + "px Archivo, sans-serif"; ctx.lineWidth = riga * 0.22; ctx.fillStyle = finale.colore;
      const t1 = finale.nome + " " + dici("VINCE!");
      ctx.strokeText(t1, 0, 0); ctx.fillText(t1, 0, 0);
      ctx.font = "800 " + Math.round(riga * 0.52) + "px Archivo, sans-serif"; ctx.lineWidth = riga * 0.14; ctx.fillStyle = "#ffcf3a";
      const t2 = finale.punti + (finale.perso ? "  ·  " + dici("FUORI DAL RING!") : "");
      ctx.strokeText(t2, 0, riga * 0.85); ctx.fillText(t2, 0, riga * 0.85);
      ctx.restore();
    }
  }

  // --- Fumogeni e barattoli (02/10/2026, su richiesta) -------------------
  // Il fumogeno lanciato apre una nube: chi ci finisce dentro non vede più
  // niente (tranne chi l'ha lanciato). Il barattolo lanciato si rompe e
  // libera una creatura, che per qualche secondo combatte per chi l'ha
  // lanciato: TIZZO soffia fuoco, ZIP chiama un fulmine, BOLLA spara un
  // getto d'acqua che spinge lontano. Personaggi inventati per questo ring.
  function apri(t) {
    if (t.morto) return false;
    const per = t.lanciatore && t.lanciatore.tipo ? t.lanciatore.tipo : null;
    if (t.tipo === "fumogeno") {
      nubi.push({ x: t.x, y: Math.min(t.y, pavimento - 26 * S), t: 0, per });
      scrivi("PUFF!", t.x, t.y - 16 * S, false);
    } else if (t.tipo === "barattolo") {
      if (creature.length >= 3) return false;
      schegge(t.x, t.y, 8, "#cfe9ff");
      nuovaCreatura(t.el, t.x, t.y, per);
    } else return false;
    t.morto = true; t.armato = false;
    return true;
  }
  function aggiornaNubi() {
    for (const n of nubi) {
      n.t++;
      if (n.t < 250 && passi % 2 === 0 && particelle.length < MAX_PARTICELLE - 40) {
        particelle.push({ tipo: "fumo", x: n.x + caso(-42, 42) * S, y: n.y + caso(-26, 22) * S, vx: caso(-0.5, 0.5) * S, vy: -caso(0.1, 0.5) * S,
                          vita: 80, max: 80, r: caso(9, 15) * S, colore: passi % 4 < 2 ? "#bdb8cc" : "#dedbe8" });
      }
      if (n.t > 260) continue;
      for (const f of lottatori) {
        if (f.tipo === n.per || f.esploso || f.fuori || f.ko > 0 || f.preso || f.tenuto) continue;
        if (Math.hypot(f.p.testa.x - n.x, f.p.testa.y - n.y) < 64 * S) {
          if (!(f.accecato > 0)) scrivi("COFF!", f.p.testa.x, f.p.testa.y - 18 * S, false);
          f.accecato = Math.max(f.accecato, 24);
        }
      }
    }
    if (nubi.length) nubi = nubi.filter((n) => n.t < 300);
  }
  function nuovaCreatura(el, x, y, per) {
    if (!ELEMENTI[el]) el = "fuoco";
    const c = { el, x: Math.max(16 * S, Math.min(W - 16 * S, x)), y: Math.min(y, pavimento - 12 * S), vy: -5 * S, per: per || null,
                t: 0, vita: 600, dir: 1, attesa: 45, colpo: 0, creatura: true };
    creature.push(c);
    scrivi(ELEMENTI[el].nome + "!", c.x, c.y - 26 * S, true);
    scintille(c.x, c.y, 12, ELEMENTI[el].colore);
    return c;
  }
  function bersaglioDi(c) {
    let scelto = null, d0 = 1e9;
    for (const f of lottatori) {
      if (f.esploso || f.fuori || f.tipo === c.per) continue;
      const d = Math.abs(f.p.bacino.x - c.x);
      if (d < d0) { d0 = d; scelto = f; }
    }
    return scelto;
  }
  function aggiornaCreature() {
    if (!creature.length) return;
    for (const c of creature) {
      c.t++;
      const vola = c.el === "fuoco", f = bersaglioDi(c), g = GRAVITA * S * Math.max(0.3, moltG);
      if (vola) {
        // TIZZO galleggia all'altezza di chi insegue.
        const quota = (f ? Math.min(pavimento, f.base) : pavimento) - 42 * S;
        c.y += (quota + Math.sin(c.t * 0.09) * 5 * S - c.y) * 0.08; c.aTerra = true;
      } else {
        // Le altre camminano: sul pavimento o sul primo elemento della pagina sotto i piedi.
        const prima = c.y;
        c.vy += g; c.y += c.vy;
        let suolo = pavimento;
        for (const o of ostacoli) if (c.x >= o.l && c.x <= o.r && o.t >= prima + 16 * S - 2 && o.t < suolo) suolo = o.t;
        c.aTerra = c.vy >= 0 && c.y >= suolo - 16 * S;
        if (c.aTerra) { c.y = suolo - 16 * S; c.vy = 0; }
        // L'avversario sta più in alto: un salto fin lassù.
        if (c.aTerra && f && f.base < suolo - 20 * S && Math.abs(f.p.bacino.x - c.x) < 130 * S && c.t % 30 === 0) {
          c.vy = -Math.sqrt(2 * g * (suolo - f.base + 18 * S));
        }
      }
      if (c.t > c.vita) continue;
      if (c.colpo) { c.colpo++; attaccoCreatura(c, f); }
      else if (f) {
        const dx = f.p.bacino.x - c.x, d = Math.abs(dx), lontano = (c.el === "scossa" ? 150 : c.el === "acqua" ? 120 : 90) * S;
        c.dir = dx >= 0 ? 1 : -1;
        if (d > lontano) {
          c.x += c.dir * (c.el === "acqua" ? 1.4 : 2) * S;
          if (!vola && c.aTerra && c.vy === 0 && c.t % (c.el === "scossa" ? 14 : 22) === 0) c.vy = -(c.el === "scossa" ? 3.4 : 2.2) * S;
        } else if (d < 46 * S) c.x -= c.dir * 1.2 * S;
        if (c.attesa > 0) c.attesa--;
        else if (d <= lontano + 24 * S && !(f.ko > 0)) c.colpo = 1;
      }
      c.x = Math.max(14 * S, Math.min(W - 14 * S, c.x));
      if (vola && passi % 5 === 0 && particelle.length < MAX_PARTICELLE - 60) {
        particelle.push({ tipo: "scintilla", x: c.x + caso(-5, 5) * S, y: c.y - 8 * S, vx: caso(-0.4, 0.4) * S, vy: -caso(0.8, 1.8) * S, vita: 12, max: 12, colore: "#ffb62e" });
      }
    }
    const via = creature.filter((c) => c.t > c.vita + 14);
    for (const c of via) polvere(c.x, c.y, 6);
    if (via.length) creature = creature.filter((c) => c.t <= c.vita + 14);
  }
  function attaccoCreatura(c, f) {
    const att = { dir: c.dir, tipo: c.per, furia: 0, azione: null, creatura: true };
    const davanti = f && (f.p.collo.x - c.x) * c.dir > -10 * S;
    const metti = (q) => { if (particelle.length < MAX_PARTICELLE - 20) particelle.push(q); };
    if (c.el === "fuoco") {
      if (c.colpo >= 8 && c.colpo <= 30) {
        for (let i = 0; i < 2; i++) {
          metti({ tipo: "fuoco", x: c.x + c.dir * 9 * S, y: c.y - 2 * S, vx: c.dir * caso(3.5, 7) * S, vy: caso(-1.3, 0.6) * S,
                  vita: 20, max: 20, r: caso(2.6, 4.6) * S });
        }
      }
      if (c.colpo === 8) scrivi("FWOOSH!", c.x + c.dir * 30 * S, c.y - 16 * S, false);
      if (c.colpo === 17 && davanti && Math.abs(f.p.collo.x - c.x) < 125 * S && Math.abs(f.p.bacino.y - c.y) < 70 * S && !(f.ko > 0)) {
        colpisci(att, f, 3.6, f.p.collo.x, (f.p.collo.y + f.p.bacino.y) / 2, "AHI!");
      }
      if (c.colpo >= 40) { c.colpo = 0; c.attesa = 100; }
    } else if (c.el === "scossa") {
      if (c.colpo < 16 && c.colpo % 3 === 0) scintille(c.x + caso(-9, 9) * S, c.y + caso(-9, 5) * S, 2, "#fff3b0");
      if (c.colpo === 16 && f && !(f.ko > 0)) fulmini.push({ x: f.p.collo.x, t: 0, da: att, contro: f, forza: 4.2, punti: null });
      if (c.colpo >= 36) { c.colpo = 0; c.attesa = 130; }
    } else {
      if (c.colpo >= 6 && c.colpo <= 30) {
        for (let i = 0; i < 2; i++) {
          metti({ tipo: "goccia", x: c.x + c.dir * 8 * S, y: c.y - 5 * S, vx: c.dir * caso(5, 8.5) * S, vy: -caso(1.2, 3) * S,
                  vita: 50, max: 50, r: caso(1.6, 3) * S, colore: i ? "#8fd0ff" : "#3aa0ff" });
        }
      }
      if (c.colpo === 6) scrivi("SPLASH!", c.x + c.dir * 30 * S, c.y - 18 * S, false);
      if (c.colpo === 16 && davanti && Math.abs(f.p.collo.x - c.x) < 150 * S && Math.abs(f.p.bacino.y - c.y) < 80 * S && !(f.ko > 0)) {
        colpisci(att, f, 2.6, f.p.bacino.x, f.p.bacino.y - 6 * S, "SPLASH!");
        // Il getto spinge lontano più di quanto faccia male.
        for (const n in f.p) { f.p[n].ox -= c.dir * 9 * S; f.p[n].oy += 2.5 * S * verso; }
      }
      if (c.colpo >= 42) { c.colpo = 0; c.attesa = 110; }
    }
  }
  function occhiCreatura(x, y, d, r, arrabbiato) {
    for (const lato of [-1, 1]) {
      const ox = x + lato * r * 1.25;
      ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "#111"; ctx.lineWidth = 0.8 * S;
      ctx.beginPath(); ctx.ellipse(ox, y, r, r * 1.2, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      tondo(ox + d * r * 0.35, y + r * 0.15, r * 0.5, "#111");
      if (arrabbiato) {
        ctx.lineWidth = 1.1 * S; ctx.beginPath();
        ctx.moveTo(ox - lato * r * 1.1, y - r * 1.9); ctx.lineTo(ox + lato * r * 0.9, y - r * 1.2); ctx.stroke();
      }
    }
  }
  function disegnaCreatura(c) {
    const E = ELEMENTI[c.el], nasce = Math.min(1, c.t / 10), fine = c.t > c.vita ? Math.max(0, 1 - (c.t - c.vita) / 14) : 1;
    if (c.t > c.vita - 90 && c.t < c.vita && c.t % 10 < 3) return;      // lampeggia: sta per andarsene
    const d = c.dir, att = c.colpo > 0;
    ctx.save(); ctx.translate(c.x, c.y); ctx.scale(1.35 * nasce * fine, 1.35 * nasce * fine);
    ctx.lineJoin = "round"; ctx.lineCap = "round";
    // Di chi è: una bandierina col colore di chi l'ha liberata.
    if (c.per) {
      ctx.fillStyle = COLORI_ANIME[c.per]; ctx.strokeStyle = "#111"; ctx.lineWidth = 0.8 * S;
      ctx.beginPath(); ctx.moveTo(0, -27 * S); ctx.lineTo(4 * S, -23.5 * S); ctx.lineTo(0, -20 * S); ctx.lineTo(-4 * S, -23.5 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    if (c.el === "fuoco") {
      // TIZZO: una fiammella che galleggia, con due braccini di brace.
      const tr = Math.sin(c.t * 0.45) * 2 * S, g = ctx.createRadialGradient(0, 3 * S, 1 * S, 0, 0, 15 * S);
      g.addColorStop(0, "#fff6c2"); g.addColorStop(0.45, "#ffb62e"); g.addColorStop(1, "#f2501d");
      ctx.fillStyle = g; ctx.strokeStyle = "#111"; ctx.lineWidth = 1.2 * S;
      ctx.beginPath(); ctx.moveTo(tr - d * 2 * S, -18 * S);
      ctx.bezierCurveTo(7 * S, -10 * S, 12 * S, -3 * S, 10 * S, 4 * S);
      ctx.bezierCurveTo(8 * S, 11 * S, -8 * S, 11 * S, -10 * S, 4 * S);
      ctx.bezierCurveTo(-12 * S, -3 * S, -5 * S, -8 * S, tr - d * 2 * S, -18 * S);
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = "rgba(255,246,194,.85)"; ctx.beginPath(); ctx.ellipse(0, 4 * S, 5 * S, 4.5 * S, 0, 0, Math.PI * 2); ctx.fill();
      for (const lato of [-1, 1]) {
        const su = att && lato === d ? -4 * S : Math.sin(c.t * 0.3 + lato) * 1.5 * S;
        ctx.fillStyle = "#ff8a1a"; ctx.beginPath(); ctx.ellipse(lato * 12.5 * S, 3 * S + su, 3.2 * S, 2.4 * S, lato * 0.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
      occhiCreatura(d * 1.6 * S, -1 * S, d, 2 * S, true);
      if (att) { ctx.fillStyle = "#7a1a0c"; ctx.beginPath(); ctx.ellipse(d * 2.4 * S, 5 * S, 2.6 * S, 2.2 * S, 0, 0, Math.PI * 2); ctx.fill(); }
    } else if (c.el === "scossa") {
      // ZIP: una scintilla a punte, due zampette a saetta e un'antenna.
      const n = 9, giro = c.t * (att ? 0.25 : 0.04);
      ctx.strokeStyle = "#111"; ctx.lineWidth = 1.3 * S;
      for (const lato of [-1, 1]) {
        ctx.beginPath(); ctx.moveTo(lato * 3.5 * S, 6 * S); ctx.lineTo(lato * 6 * S, 8.5 * S); ctx.lineTo(lato * 3 * S, 9.5 * S); ctx.lineTo(lato * 5.5 * S, 12 * S); ctx.stroke();
      }
      ctx.beginPath(); ctx.moveTo(0, -9 * S); ctx.lineTo(2 * S, -13 * S); ctx.lineTo(-1.5 * S, -14.5 * S); ctx.lineTo(1 * S, -18 * S); ctx.stroke();
      tondo(1 * S, -18.5 * S, 1.5 * S, "#fff3b0");
      ctx.fillStyle = att && c.t % 4 < 2 ? "#fff8c9" : "#ffd400"; ctx.lineWidth = 1.2 * S; ctx.beginPath();
      for (let i = 0; i < n * 2; i++) {
        const a = giro + i * Math.PI / n, r = (i % 2 ? 7.2 : 11.2 + (att ? Math.sin(c.t + i) * 1.6 : 0)) * S;
        ctx[i ? "lineTo" : "moveTo"](Math.cos(a) * r, Math.sin(a) * r);
      }
      ctx.closePath(); ctx.fill(); ctx.stroke();
      occhiCreatura(d * 1.4 * S, -1 * S, d, 1.9 * S, att);
      ctx.strokeStyle = "#111"; ctx.lineWidth = 0.9 * S; ctx.beginPath(); ctx.arc(d * 1.4 * S, 2.6 * S, 2 * S, 0.15 * Math.PI, 0.85 * Math.PI); ctx.stroke();
    } else {
      // BOLLA: una goccia che ondeggia, col ciuffo d'onda e due pinnette.
      const sq = 1 + Math.sin(c.t * 0.22) * 0.06, g = ctx.createLinearGradient(0, -14 * S, 0, 10 * S);
      g.addColorStop(0, "#bfe6ff"); g.addColorStop(1, "#2f8fe8");
      ctx.scale(1 / sq, sq);
      ctx.strokeStyle = "#0d3b7a"; ctx.lineWidth = 1.2 * S;
      for (const lato of [-1, 1]) {
        ctx.fillStyle = "#2f8fe8"; ctx.beginPath(); ctx.ellipse(lato * 6 * S, 9.5 * S, 4 * S, 2 * S, lato * 0.25, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
      ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(-d * 4 * S, -17 * S);
      ctx.bezierCurveTo(4 * S, -13 * S, 11 * S, -6 * S, 11 * S, 1 * S);
      ctx.bezierCurveTo(11 * S, 13 * S, -11 * S, 13 * S, -11 * S, 1 * S);
      ctx.bezierCurveTo(-11 * S, -6 * S, -6 * S, -10 * S, -d * 4 * S, -17 * S);
      ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1.5 * S; ctx.beginPath(); ctx.arc(-d * 3 * S, -2 * S, 6 * S, Math.PI * 1.05, Math.PI * 1.45); ctx.stroke();
      occhiCreatura(d * 2 * S, -1 * S, d, 2 * S, false);
      ctx.fillStyle = "#0d3b7a"; ctx.beginPath();
      ctx.ellipse(d * 3.4 * S, 4.6 * S, (att ? 2.2 : 1.3) * S, (att ? 2.4 : 0.9) * S, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  // --- Le esplosioni ----------------------------------------------------
  // Una sola ricetta per bombe e pieghevole: lampo, onda d'urto, palla di
  // fuoco che si gonfia e si spegne in fumo, detriti che volano e rimbalzano
  // su pagina e pavimento, braci che ricadono piano. E una spinta vera: i
  // lottatori, gli oggetti e i pezzi vicini vengono sbalzati via.
  const MAX_PARTICELLE = 320;
  function esplosione(x, y, potenza, att, inPieno) {
    const R = 80 * S * potenza;
    scossa = Math.max(scossa, Math.round(10 + 8 * potenza)); fermoColpo = Math.max(fermoColpo, 6);
    const metti = (q) => { if (particelle.length < MAX_PARTICELLE) particelle.push(q); };
    metti({ tipo: "lampo", x, y, vx: 0, vy: 0, vita: 7, max: 7, r: R * 1.4 });
    metti({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 24, max: 24, colore: "#fff3b0" });
    for (let i = 0; i < 9 * potenza; i++) {
      const a = caso(0, Math.PI * 2), d = caso(0, 0.35) * R;
      metti({ tipo: "fuoco", x: x + Math.cos(a) * d, y: y + Math.sin(a) * d, vx: Math.cos(a) * caso(0.3, 1.4) * S,
              vy: Math.sin(a) * caso(0.3, 1.4) * S - 0.6 * S, vita: Math.round(caso(18, 30)), max: 30, r: caso(8, 16) * S * potenza });
    }
    for (let i = 0; i < 10 * potenza; i++) {
      metti({ tipo: "fumo", x: x + caso(-0.4, 0.4) * R, y: y + caso(-0.3, 0.2) * R, vx: caso(-0.5, 0.5) * S, vy: -caso(0.4, 1.1) * S,
              vita: Math.round(caso(50, 90)), max: 90, r: caso(6, 12) * S * potenza, colore: Math.random() < 0.5 ? "#6d6a66" : "#8d8a85" });
    }
    for (let i = 0; i < 22 * potenza; i++) {
      const a = caso(Math.PI * 1.05, Math.PI * 1.95 + Math.PI * 0.6), v = caso(4, 12) * S * Math.sqrt(potenza);
      metti({ tipo: "detrito", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - caso(1, 4) * S, vita: Math.round(caso(70, 130)), max: 130,
              rot: caso(0, 6), va: caso(-0.4, 0.4), lato: caso(1.4, 3.2) * S,
              colore: ["#2b2f3a", "#5a4030", "#7d8696", "#3a3a3a"][Math.floor(Math.random() * 4)] });
    }
    for (let i = 0; i < 16 * potenza; i++) {
      const a = caso(0, Math.PI * 2), v = caso(2, 8) * S;
      metti({ tipo: "brace", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 2 * S, vita: Math.round(caso(40, 80)), max: 80,
              colore: Math.random() < 0.5 ? "#ffb62e" : "#ff6a1a" });
    }
    scintille(x, y, Math.round(14 * potenza), "#ffe27a");
    // La spinta: più forte vicino, niente oltre il raggio.
    for (const f of lottatori) {
      if (f.esploso || f.preso) continue;
      const b = f.p.bacino, dx = b.x - x, dy = b.y - y, d = Math.hypot(dx, dy) || 1;
      if (d > R * 1.6) continue;
      const k = Math.max(0, 1 - d / (R * 1.6)), ux = dx / d, uy = dy / d - 0.6;
      if (f.tiene) molla(f);
      if (f.tenuto && f.tenuto.da) molla(f.tenuto.da);
      for (const n in f.p) { f.p[n].ox -= ux * 13 * S * k; f.p[n].oy -= uy * 11 * S * k; }
      if (inPieno && d < R * 0.42) { esplodiLottatore(f, att && att !== f ? att : null); continue; }
      if (d < R) {
        const chi = att && att !== f ? att : { dir: dx >= 0 ? 1 : -1, tipo: null, furia: 0 };
        colpisci(chi, f, 3 + 5 * k, b.x, b.y, "BOOM!");
        if (Math.random() < 0.6) smembra(f, x, y);
        if (eMela(f)) mordi(f, x, y);
      }
      f.inVolo = true; f.ko = Math.max(f.ko, 40); f.jet = 0; f.paracadute = 0;
    }
    for (const t of telefoni) {
      if (t.stato === "portato" || t.stato === "impugnato" || t.stato === "preso") continue;
      const dx = t.x - x, dy = t.y - y, d = Math.hypot(dx, dy) || 1;
      if (d > R * 1.8) continue;
      const k = 1 - d / (R * 1.8);
      t.ox = t.x - dx / d * 12 * S * k; t.oy = t.y - (dy / d - 0.7) * 12 * S * k; t.va += caso(-0.5, 0.5);
      t.stato = "volo"; t.da = null;
    }
    for (const pz of pezzi.concat(arti)) {
      const dx = pz.x - x, dy = pz.y - y, d = Math.hypot(dx, dy) || 1;
      if (d < R * 1.8) { const k = 1 - d / (R * 1.8); pz.ox = pz.x - dx / d * 10 * S * k; pz.oy = pz.y - (dy / d - 0.6) * 10 * S * k; }
    }
    if (y > pavimento - 70 * S) danneggiaStriscia(x, Math.min(1, 0.7 + 0.3 * potenza));
    if (x < R) danneggiaBordo("sinistra", y, 0.9);
    if (x > W - R) danneggiaBordo("destra", y, 0.9);
    if (y < R) danneggiaBordo("tetto", x, 0.9);
  }

  // --- Le bombe ----------------------------------------------------------
  // Si raccolgono e si lanciano come i telefoni, ma con la miccia accesa:
  // scoppiano quando finisce, o subito se centrano qualcuno.
  function scoppia(t) {
    if (t.morto) return;
    t.morto = true;
    const f = t.da && t.da.tel === t ? t.da : null;
    if (f) f.tel = null;
    esplosione(t.x, t.y, 1.15, t.lanciatore || null, true);
    scrivi("BOOM!", t.x, t.y - 30 * S, true);
  }

  // --- I danni che si vedono --------------------------------------------
  // Ogni colpo lascia un segno dove arriva: ammaccature sul robot, lividi
  // marroni sulla mela. Spariscono in un minuto. Con «effetti cruenti»
  // accesi (si spengono dalla tendina) i colpi fanno anche schizzare olio
  // nero dal robot e succo rosso dalla mela, che macchiano dove cadono.
  function segna(f, x, y, forza) {
    if (!f.p || !f.segni) return;
    const p = f.p, testa = Math.hypot(x - p.testa.x, y - p.testa.y) < Math.hypot(x - (p.collo.x + p.bacino.x) / 2, y - (p.collo.y + p.bacino.y) / 2);
    let ox, oy, ang, lim;
    if (eMela(f)) {
      const c = corpoMela(p); ox = c.x; oy = c.y; ang = c.ang; lim = [c.R / S * 0.7, c.R / S * 0.7];
    } else if (testa) {
      ox = p.testa.x; oy = p.testa.y; ang = Math.atan2(p.testa.y - p.collo.y, p.testa.x - p.collo.x) + Math.PI / 2; lim = [6.5, 5.5];
    } else {
      ox = (p.collo.x + p.bacino.x) / 2; oy = (p.collo.y + p.bacino.y) / 2;
      ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2; lim = [6.5, 9];
    }
    const dx = x - ox, dy = y - oy, c = Math.cos(-ang), s2 = Math.sin(-ang);
    const u = Math.max(-lim[0], Math.min(lim[0], (dx * c - dy * s2) / S)), v = Math.max(-lim[1], Math.min(lim[1], (dx * s2 + dy * c) / S));
    f.segni.push({ parte: eMela(f) ? "frutto" : testa ? "testa" : "busto", u, v,
                   r: Math.min(4.2, 1.6 + forza * 0.35), vita: 3600, seme: Math.random() * 6 });
    if (f.segni.length > 10) f.segni.shift();
  }
  function schizza(f, x, y, n, forza) {
    if (!cruento || !f.p) return;
    const robot = eRobot(f);
    for (let i = 0; i < n && particelle.length < MAX_PARTICELLE; i++) {
      const a = caso(-Math.PI, 0), v = caso(1.5, 3.5) * S * Math.sqrt(forza);
      particelle.push({ tipo: "goccia", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vita: 90, max: 90,
                        r: caso(0.9, 1.8) * S, colore: robot ? "#1b1b1b" : "#d8343f" });
    }
    if (robot) scintille(x, y, 3, "#ffe27a");
  }
  function macchia(x, y, r, colore) {
    macchie.push({ x, y, r: r * caso(1.2, 2), colore, vita: 900, schiacciata: caso(0.4, 0.6) });
    if (macchie.length > 24) macchie.shift();
  }
  // Gli arti si staccano con le armi pesanti (spada, pistola, bomba) e,
  // dopo qualche secondo, tornano al loro posto da soli: è un cartone.
  const ARTI = { A: ["gomitoA", "manoA", "braccio"], D: ["gomitoD", "manoD", "braccio"],
                 gA: ["ginocchioA", "piedeA", "gamba"], gD: ["ginocchioD", "piedeD", "gamba"],
                 P: ["testa", "testa", "picciolo"] };   // il picciolo della mela, l'antenna del robot
  function smembra(f, x, y) {
    if (!cruento || !f.p || f.esploso) return;
    // I personaggi inventati non hanno né picciolo né antenna da perdere.
    const liberi = Object.keys(ARTI).filter((k) => !f.staccati[k] && !(stile && k === "P"));
    if (!liberi.length) return;
    const k = liberi[Math.floor(Math.random() * liberi.length)], [g, m, forma] = ARTI[k];
    f.staccati[k] = 1;
    if (k === "A" && f.arma) lasciaArma(f);
    if (k === "A" && f.tel) lasciaCadere(f);
    let P = f.p[g], Q = f.p[m];
    if (forma === "picciolo") {
      const c = eMela(f) ? corpoMela(f.p) : null;
      P = Q = c ? { x: c.x - Math.sin(c.ang) * -0.95 * c.R, y: c.y + Math.cos(c.ang) * -0.95 * c.R } : { x: f.p.testa.x, y: f.p.testa.y - 10 * S };
    }
    const vx = (P.x - x) * 0.08 + caso(-3, 3) * S, vy = -caso(4, 8) * S;
    const T = tavolozza || ["#2fae74", "#1c6f4a", "#7dffd2", "#154d34"], A = stile ? aspetto(f) : null;
    arti.push({ f, chiave: k, forma, x: (P.x + Q.x) / 2, y: (P.y + Q.y) / 2, ox: (P.x + Q.x) / 2 - vx, oy: (P.y + Q.y) / 2 - vy,
                ang: Math.atan2(Q.y - P.y, Q.x - P.x), va: caso(-0.4, 0.4), L: 20 * S, t: 0, da: null, grosso: !!A || f.tipo === "robot", olio: eRobot(f),
                colore: A ? (forma === "braccio" ? A.maniche : A.gambe) : f.tipo === "robot" ? (k.endsWith("D") ? T[1] : T[0]) : "#111",
                estremo: A ? (forma === "braccio" ? A.pelle : A.scarpe)
                           : forma === "braccio" ? (f.tipo === "robot" ? (k === "A" ? "#e03a2f" : "#b92b22") : (k === "A" ? "#2f72e0" : "#1f56b8"))
                                                 : (f.tipo === "robot" ? T[3] : "#f7f7f7") });
    if (forma !== "picciolo" || f.tipo === "mela") schizza(f, P.x, P.y, forma === "picciolo" ? 3 : 7, 2);
    else scintille(P.x, P.y, 6, "#ffe27a");
    scrivi(forma === "braccio" ? "AHIA!" : "OPS!", P.x, P.y - 14 * S, false);
  }
  // La mela si smembra a modo suo: i colpi forti le portano via un morso
  // (che si richiude piano), la spada la taglia in due (le metà si aprono e
  // poi si rincollano).
  const TAGLIO_CHIUDE = 230;
  function mordi(f, x, y) {
    if (!cruento || !eMela(f) || !f.p || f.esploso || f.taglio) return;
    const c = corpoMela(f.p), dx = x - c.x, dy = y - c.y, ca = Math.cos(-c.ang), sa = Math.sin(-c.ang);
    const lx = dx * ca - dy * sa, ly = dx * sa + dy * ca, a = Math.atan2(ly, lx);
    const m = { x: Math.cos(a) * 0.98, y: Math.sin(a) * 0.98, r: caso(0.32, 0.46), k: 0, vita: 2400 };
    if (!f.morsi) f.morsi = [];
    if (f.morsi.some((o) => Math.hypot(o.x - m.x, o.y - m.y) < o.r + m.r + 0.08)) return;
    f.morsi.push(m);
    if (f.morsi.length > 4) f.morsi.shift();
    // Il pezzo che vola via, e il succo.
    const wx = c.x + (Math.cos(c.ang) * m.x - Math.sin(c.ang) * m.y) * c.R;
    const wy = c.y + (Math.sin(c.ang) * m.x + Math.cos(c.ang) * m.y) * c.R;
    if (particelle.length < MAX_PARTICELLE) {
      particelle.push({ tipo: "pezzetto", x: wx, y: wy, vx: Math.cos(c.ang + a) * caso(2, 4) * S, vy: -caso(3, 6) * S,
                        vita: 140, max: 140, rot: caso(0, 6), va: caso(-0.3, 0.3), lato: m.r * c.R });
    }
    schizza(f, wx, wy, 5, 1.5);
  }
  function taglia(f, att) {
    if (!cruento || !eMela(f) || !f.p || f.esploso || f.taglio) return false;
    f.taglio = { ang: caso(-0.5, 0.5) + (Math.random() < 0.5 ? 0 : Math.PI / 2), t: 0 };
    f.morsi = [];
    f.ko = Math.max(f.ko, TAGLIO_CHIUDE + 40); f.inVolo = true;
    const c = corpoMela(f.p);
    schizza(f, c.x, c.y, 12, 3);
    scintille(c.x, c.y, 10, "#ffffff");
    scrivi("SLASH!", c.x, c.y - 30 * S, true);
    return true;
  }
  function aggiornaMela(f) {
    if (f.morsi && f.morsi.length) {
      for (const m of f.morsi) { m.vita--; m.k = m.vita > 300 ? Math.min(1, m.k + 0.2) : Math.max(0, m.vita / 300); }
      if (f.morsi[0].vita <= 0) f.morsi = f.morsi.filter((m) => m.vita > 0);
    }
    if (f.taglio) {
      const t = ++f.taglio.t;
      if (cruento && t < TAGLIO_CHIUDE && t % 16 === 0) { const c = corpoMela(f.p); schizza(f, c.x, c.y, 1, 0.5); }
      if (t === TAGLIO_CHIUDE + 22) { const c = corpoMela(f.p); scintille(c.x, c.y, 10, "#ffffff"); scrivi("CLICK!", c.x, c.y - 26 * S, false); }
      if (t > TAGLIO_CHIUDE + 24) f.taglio = null;
    }
  }

  const ARTO_VIA = 420, ARTO_TORNA = 30;
  function aggiornaArti() {
    for (const a of arti) {
      a.t++;
      const f = a.f;
      if (!f.p || f.esploso || !lottatori.includes(f)) { a.morto = true; continue; }
      if (a.t < ARTO_VIA) {
        rimbalzaPezzo(a);
        if (cruento && a.t % 9 === 0 && a.t < 160) schizza(f, a.x, a.y, 1, 0.5);
        continue;
      }
      // Torna a casa con un balzo: alla spalla o all'anca.
      const casa = a.forma === "braccio" ? f.p.collo : a.forma === "picciolo" ? f.p.testa : f.p.bacino;
      if (!a.da) a.da = [a.x, a.y, a.ang];
      const k = Math.min(1, (a.t - ARTO_VIA) / ARTO_TORNA), q = k * k * (3 - 2 * k);
      a.x = a.da[0] + (casa.x - a.da[0]) * q; a.y = a.da[1] + (casa.y - a.da[1]) * q - Math.sin(Math.PI * k) * 40 * S;
      a.ang = a.da[2] + 4 * Math.PI * q; a.ox = a.x; a.oy = a.y;
      if (k >= 1) { a.morto = true; f.staccati[a.chiave] = 0; scintille(casa.x, casa.y, 6, "#7dffd2"); scrivi("CLICK!", casa.x, casa.y - 16 * S, false); }
    }
    if (arti.some((a) => a.morto)) arti = arti.filter((a) => !a.morto);
    for (const f of lottatori) {
      if (eMela(f)) aggiornaMela(f);
      if (f.segni && f.segni.length) { for (const sg of f.segni) sg.vita--; if (f.segni[0].vita <= 0) f.segni = f.segni.filter((sg) => sg.vita > 0); }
      // Dal moncone, ogni tanto, una goccia.
      if (cruento && passi % 14 === 0 && !f.esploso) {
        for (const k in f.staccati) if (f.staccati[k] && k !== "P") { const pt = k.startsWith("g") ? f.p.bacino : f.p.collo; schizza(f, pt.x, pt.y + 2 * S, 1, 0.4); }
      }
    }
    for (const m of macchie) m.vita--;
    if (macchie.length && macchie[0].vita <= 0) macchie = macchie.filter((m) => m.vita > 0);
  }

  // --- Il meteo: pioggia, neve di Natale, uragano -----------------------
  function aggiornaMeteo() {
    if (acquazzone) {
      for (let i = 0; i < 3 && particelle.length < MAX_PARTICELLE; i++) {
        particelle.push({ tipo: "pioggia", x: caso(-40, W + 40), y: -10, vx: -1.6 * S, vy: caso(9, 12) * S, vita: 200, max: 200 });
      }
    }
    // La neve, l'albero e i pupazzi del tema natalizio li fa `natale.js` per
    // tutto il sito: qui restano solo i cappellini e le palle di neve.
    if (uragano) {
      const u = uragano;
      u.t++;
      u.x += u.vx;
      if (u.x < 80 * S || u.x > W - 80 * S) u.vx = -u.vx;
      const alto = Math.min(320 * S, pavimento - testataBasso - 40 * S);
      for (const f of lottatori) {
        if (f.esploso || f.preso || f.tenuto || verso < 0) continue;
        if (f.uraganoCd > 0) { f.uraganoCd--; continue; }
        const b = f.p.bacino, dx = b.x - u.x;
        if (Math.abs(dx) < 60 * S && b.y > pavimento - alto) {
          // Preso dal vortice: gira intorno all'imbuto e sale.
          f.ko = Math.max(f.ko, 25); f.inVolo = true; f.jet = 0; f.paracadute = 0; f.fantasma = true;
          const fase = u.t * 0.12 + (f.tipo === "mela" ? Math.PI : 0), raggio = (24 + 40 * (pavimento - b.y) / alto) * S;
          const tx = u.x + Math.cos(fase) * raggio;
          for (const n in f.p) { const q = f.p[n]; q.x += (tx - b.x) * 0.05; q.y -= GRAVITA * S * moltG * 1.35; }
          if (b.y < pavimento - alto) {
            // In cima viene sputato via di lato.
            const lato = Math.random() < 0.5 ? -1 : 1;
            for (const n in f.p) { f.p[n].ox = f.p[n].x - lato * 10 * S; f.p[n].oy = f.p[n].y + 2 * S; }
            f.uraganoCd = 160; scrivi("WHOOSH!", b.x, b.y - 20 * S, false);
          }
        } else if (Math.abs(dx) < 320 * S) {
          for (const n in f.p) f.p[n].x -= Math.sign(dx) * 0.22 * S * (1 - Math.abs(dx) / (320 * S));
        }
      }
      for (const t of telefoni) {
        if (t.stato === "portato" || t.stato === "impugnato" || t.stato === "preso") continue;
        const dx = t.x - u.x;
        if (Math.abs(dx) < 60 * S && t.y > pavimento - alto) {
          t.stato = "volo"; t.da = null;
          t.x += (u.x + Math.cos(u.t * 0.15 + t.r) * 34 * S - t.x) * 0.06; t.y -= GRAVITA * S * moltG * 1.4; t.va += 0.02;
          if (t.y < pavimento - alto) { t.ox = t.x + Math.sign(dx || 1) * -9 * S; }
        }
      }
      if (passi % 3 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "vento", x: u.vx > 0 ? -20 : W + 20, y: caso(80, pavimento - 10), vx: Math.sign(u.vx) * caso(8, 14) * S, vy: 0,
                          vita: 120, max: 120, lung: caso(20, 60) * S });
      }
    }
  }
  // L'uragano: una nuvola scura in alto, un imbuto che si torce e serpeggia,
  // nastri di vento che gli girano intorno (davanti chiari, dietro scuri),
  // detriti che orbitano e una nube di polvere alla base.
  function disegnaUragano() {
    const u = uragano, alto = Math.min(320 * S, pavimento - testataBasso - 40 * S), t = u.t;
    const larg = (k) => (7 + 64 * Math.pow(k, 1.5)) * S;
    const asse = (k) => u.x + Math.sin(t * 0.035 + k * 3.2) * 16 * S * k + Math.sin(t * 0.11 + k * 7) * 3 * S * k;
    const yk = (k) => pavimento - k * alto;
    const N = 24;
    ctx.save();
    // 1. La sagoma dell'imbuto, con una sfumatura dall'alto al basso.
    const g = ctx.createLinearGradient(0, yk(1), 0, pavimento);
    g.addColorStop(0, "rgba(78,86,98,.55)"); g.addColorStop(0.7, "rgba(110,116,124,.38)"); g.addColorStop(1, "rgba(150,140,120,.28)");
    ctx.fillStyle = g; ctx.beginPath();
    for (let i = 0; i <= N; i++) { const k = i / N; ctx[i ? "lineTo" : "moveTo"](asse(k) - larg(k), yk(k)); }
    for (let i = N; i >= 0; i--) { const k = i / N; ctx.lineTo(asse(k) + larg(k), yk(k)); }
    ctx.closePath(); ctx.fill();
    // 2. I nastri di vento a spirale: prima quelli dietro, poi quelli davanti.
    ctx.lineCap = "round";
    for (const davanti of [false, true]) {
      for (let s = 0; s < 9; s++) {
        const fase = t * 0.16 + s * 0.7;
        ctx.strokeStyle = davanti ? "rgba(235,238,242,.75)" : "rgba(55,60,70,.35)";
        ctx.beginPath();
        let su = false;
        for (let i = 0; i <= 36; i++) {
          const k = i / 36, th = fase + k * 9, fronte = Math.cos(th) > 0;
          if (fronte !== davanti || k < 0.03) { su = false; continue; }
          const x = asse(k) + Math.sin(th) * larg(k), y = yk(k) + Math.cos(th) * larg(k) * 0.12;
          ctx.lineWidth = (1 + 1.6 * k) * S;
          if (su) ctx.lineTo(x, y); else { ctx.moveTo(x, y); su = true; }
        }
        ctx.stroke();
      }
    }
    // 3. Detriti che orbitano: fogli, foglie e sassi.
    for (let i = 0; i < 12; i++) {
      const k = 0.08 + ((i * 0.37 + t * 0.002) % 0.85), th = t * (0.12 + (i % 3) * 0.03) + i * 1.7;
      const x = asse(k) + Math.sin(th) * larg(k) * 1.05, y = yk(k) + Math.cos(th) * larg(k) * 0.14;
      ctx.save(); ctx.translate(x, y); ctx.rotate(th * 2);
      ctx.globalAlpha = Math.cos(th) > 0 ? 0.95 : 0.4;
      ctx.fillStyle = ["#f4f1e8", "#5f9a3a", "#8a7a66", "#d9a520"][i % 4];
      if (i % 4 === 0) ctx.fillRect(-3 * S, -2 * S, 6 * S, 4 * S);
      else if (i % 4 === 1) { ctx.beginPath(); ctx.ellipse(0, 0, 3.6 * S, 1.6 * S, 0, 0, Math.PI * 2); ctx.fill(); }
      else { ctx.beginPath(); ctx.arc(0, 0, 1.8 * S, 0, Math.PI * 2); ctx.fill(); }
      ctx.restore();
    }
    // 4. La nuvola temporalesca in cima.
    const cx = asse(1), cy = yk(1) - 4 * S, cw = larg(1) * 1.5;
    for (const [dx, dy, r, c] of [[-0.85, 0.15, 0.42, "#59606b"], [0.85, 0.12, 0.44, "#59606b"], [-0.4, -0.2, 0.55, "#6b727d"],
                                 [0.4, -0.18, 0.58, "#6b727d"], [0, 0.05, 0.6, "#4e545e"]]) {
      ctx.globalAlpha = 0.5; ctx.fillStyle = c;
      ctx.beginPath(); ctx.ellipse(cx + dx * cw + Math.sin(t * 0.02 + dx) * 3 * S, cy + dy * cw * 0.3, r * cw * 0.62, r * cw * 0.34, 0, 0, Math.PI * 2); ctx.fill();
    }
    if (t % 160 < 6) {
      // Un lampo nella nuvola.
      ctx.globalAlpha = 1; ctx.strokeStyle = "#fff6b0"; ctx.lineWidth = 2 * S; ctx.lineJoin = "miter";
      let x = cx + caso(-0.5, 0.5) * cw, y = cy;
      ctx.beginPath(); ctx.moveTo(x, y);
      for (let i = 0; i < 4; i++) { x += caso(-10, 10) * S; y += caso(8, 14) * S; ctx.lineTo(x, y); }
      ctx.stroke();
    }
    // 5. La polvere che gira alla base.
    for (let i = 0; i < 8; i++) {
      const th = t * 0.09 + i * 0.8, r = (18 + (i % 3) * 10) * S;
      ctx.globalAlpha = 0.28; ctx.fillStyle = "#a99c86";
      ctx.beginPath(); ctx.ellipse(asse(0) + Math.cos(th) * r * 1.4, pavimento - 6 * S + Math.sin(th) * 3 * S, (9 + (i % 2) * 5) * S, 5 * S, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }
  function disegnaAlbero() {
    const x = Math.max(60 * S, Math.min(W - 60 * S, 70 * S)), y = pavimento;
    ctx.save();
    ctx.fillStyle = "#6b4423"; ctx.fillRect(x - 4 * S, y - 14 * S, 8 * S, 14 * S);
    const piani = [[0, 34, 26], [20, 28, 24], [38, 21, 22], [54, 14, 18]];
    for (const [su, largo, alto] of piani) {
      ctx.fillStyle = "#2e8b4e"; ctx.strokeStyle = "#1c5a33"; ctx.lineWidth = 1.2 * S;
      ctx.beginPath(); ctx.moveTo(x - largo * S, y - (14 + su) * S); ctx.lineTo(x + largo * S, y - (14 + su) * S);
      ctx.lineTo(x, y - (14 + su + alto) * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2 * S; ctx.beginPath();
      ctx.moveTo(x - largo * 0.7 * S, y - (16 + su) * S); ctx.lineTo(x + largo * 0.7 * S, y - (16 + su) * S); ctx.stroke();
    }
    const palline = [[-18, 22, "#d8343f"], [14, 26, "#ffcf3a"], [-6, 42, "#2f72e0"], [12, 50, "#d8343f"], [-8, 60, "#ffcf3a"], [4, 72, "#d8343f"]];
    for (const [dx, su, c] of palline) {
      const accesa = (Math.floor(passi / 20) + dx) % 3 !== 0;
      tondo(x + dx * S, y - su * S, 2.3 * S, accesa ? c : mix(c, "#000000", 0.4));
    }
    stella(x, y - 94 * S, 6 * S, "#ffd84a");
    ctx.restore();
  }
  // Il cappellino rosso, in coordinate della testa (o del frutto).
  function cappellino(dx, dy, largo, verso) {
    ctx.save(); ctx.translate(dx, dy); ctx.rotate(verso * 0.25);
    ctx.fillStyle = "#d8343f"; ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S;
    ctx.beginPath(); ctx.moveTo(-largo, 0); ctx.quadraticCurveTo(-largo * 0.2, -largo * 1.6, verso * largo * 1.3, -largo * 0.9);
    ctx.lineTo(largo, 0); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#ffffff"; rettangoloTondo(-largo * 1.1, -largo * 0.25, largo * 2.2, largo * 0.5, largo * 0.25); ctx.fill(); ctx.stroke();
    tondo(verso * largo * 1.3, -largo * 0.9, largo * 0.32, "#ffffff");
    ctx.restore();
  }
  // La palla di neve: si raccoglie da terra e si tira ad arco.
  function tiraPalla(f, altro) {
    const m = f.p.manoA, g = GRAVITA * S * moltG * verso * 0.6, T = caso(26, 34);
    const tx = altro.p.collo.x + caso(-6, 6) * S, ty = altro.p.collo.y + caso(-6, 6) * S;
    proiettili.push({ x: m.x, y: m.y, vx: (tx - m.x) / T, vy: (ty - m.y) / T - 0.5 * g * T, da: f, vita: 200, neve: true });
    f.palla = false;
  }

  // --- Modalità «super guerrieri» (stile anime, personaggi e mosse nostre) --
  // Energia (0-100) che si ricarica piano da sola e in fretta caricando
  // l'aura; si spende in raffiche di sfere, onde energetiche e teletrasporti.
  // Caricando a piena energia ci si potenzia: aura fissa, fulmini, colpi più forti.
  const COLORI_ANIME = { robot: "#56e1ff", mela: "#ff62d6" };
  const maniDi = (f) => (maghi() ? puntaBacchetta(f) : { x: (f.p.manoA.x + f.p.manoD.x) / 2, y: (f.p.manoA.y + f.p.manoD.y) / 2 });
  function eseguiAnime(f, altro) {
    if (f.azione === "carica") {
      f.ki = Math.min(100, f.ki + 1.1);
      if (f.t % 3 === 0 && particelle.length < MAX_PARTICELLE) {
        const b = f.p.bacino;
        particelle.push({ tipo: "scintilla", x: b.x + caso(-16, 16) * S, y: b.y + 20 * S, vx: caso(-0.3, 0.3) * S, vy: -caso(2, 4) * S,
                          vita: 18, max: 18, colore: COLORI_ANIME[f.tipo] });
      }
      if (f.t % 9 === 0 && particelle.length < MAX_PARTICELLE && f.base >= pavimento - 2) {
        particelle.push({ tipo: "detrito", x: f.cx + caso(-30, 30) * S, y: f.base - 2, vx: caso(-0.4, 0.4) * S, vy: -caso(3, 5) * S,
                          vita: 70, max: 70, rot: 0, va: caso(-0.2, 0.2), lato: caso(1.6, 3) * S, colore: "#9a948a" });
      }
      if (f.t % 20 === 0) scossa = Math.max(scossa, 2);
      // A piena energia: i guerrieri si trasformano (fino alla seconda forma), i maghi vanno in trance.
      if (f.ki >= 100) {
        if (stile === "guerrieri") { if (!(f.potenziato > 0) || f.forma < 2) inizia(f, "trasforma"); }
        else if (!f.potenziato) potenzia(f);
      }
    }
    if (f.azione === "onda" && f.t === 34) sparaOnda(f);
    if (f.azione === "raffica" && f.t >= 8 && f.t <= 32 && (f.t - 8) % 6 === 0) sparaSfera(f, altro);
    if (f.azione === "rush") eseguiRush(f, altro);
    eseguiSpeciale(f, altro);
  }
  function potenzia(f) {
    f.potenziato = 720; f.ki = 60;
    const b = f.p.bacino;
    particelle.push({ tipo: "onda", x: b.x, y: b.y - 10 * S, vx: 0, vy: 0, vita: 24, max: 24, colore: COLORI_ANIME[f.tipo] });
    scintille(b.x, b.y - 10 * S, 22, COLORI_ANIME[f.tipo]);
    scossa = Math.max(scossa, 10);
  }
  function sparaOnda(f) {
    if (f.ki < 45) return;
    f.ki -= 45;
    f.onda = { vita: 46, len: 0, colpito: false, muro: false, scontro: null, x0: 0, y0: 0, dir: f.dir };
  }
  function sparaSfera(f, altro) {
    if (f.ki < 4) return;
    f.ki -= 3;
    const m = maghi() ? puntaBacchetta(f) : (f.t % 12 === 8 ? f.p.manoA : f.p.manoD);
    const bx = altro.p.collo.x + caso(-8, 8) * S, by = altro.p.collo.y + caso(-8, 8) * S;
    const d = Math.hypot(bx - m.x, by - m.y) || 1, v = 8 * S;
    proiettili.push({ x: m.x, y: m.y, vx: (bx - m.x) / d * v, vy: (by - m.y) / d * v, da: f, vita: 160, energia: true, stella: maghi(), colore: COLORI_ANIME[f.tipo] });
  }
  function zip(x, y, colore) {
    if (particelle.length >= MAX_PARTICELLE) return;
    particelle.push({ tipo: "zip", x, y, vx: 0, vy: 0, vita: 14, max: 14, colore });
    particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 12, max: 12, colore });
    // I maghi spariscono in una nuvoletta.
    for (let i = 0; maghi() && i < 6 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "polvere", x: x + caso(-10, 10) * S, y: y + caso(-18, 18) * S, vx: caso(-1.2, 1.2) * S, vy: caso(-1, 0.2) * S,
                        vita: Math.round(caso(16, 26)), max: 28, colore: "#c9a6ff" });
    }
  }
  function teletrasporta(f, altro) {
    if (f.esploso || f.tenuto || f.preso || f.ko || !altro || altro.esploso) return false;
    f.ki = Math.max(0, f.ki - 15);
    const da = { x: f.p.bacino.x, y: f.p.bacino.y };
    const lato = f.cx < altro.cx ? 1 : -1;
    let nx = altro.cx + lato * 30 * S;
    if (nx < 30 * S || nx > W - 30 * S) nx = altro.cx - lato * 30 * S;
    nx = Math.max(30 * S, Math.min(W - 30 * S, nx));
    const dx = nx - f.cx, dy = altro.base - f.base;
    for (const n in f.p) { f.p[n].x += dx; f.p[n].y += dy; f.p[n].ox = f.p[n].x; f.p[n].oy = f.p[n].y; }
    f.cx = nx; f.base = altro.base; f.caos = 0; f.paracadute = 0; f.scalata = null; f.inVolo = false; f.onda = null; f.scatto = 0;
    if (altro.volo && altro.jet > 0) {
      if (!(f.volo && f.jet > 0)) prendiIlVolo(f);
      for (const n in f.p) f.p[n].oy = f.p[n].y;
      f.volaY = f.p.bacino.y; f.recupero = 0;
    } else f.jet = 0;
    f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
    zip(da.x, da.y, COLORI_ANIME[f.tipo]); zip(f.p.bacino.x, f.p.bacino.y, COLORI_ANIME[f.tipo]);
    inizia(f, scegli([[3, "pugno"], [2, "calcio"], [2, "montante"]]));
    return true;
  }
  function aggiornaOnde() {
    for (const f of lottatori) {
      const o = f.onda;
      if (!o) continue;
      if (f.ko || f.preso || f.tenuto || f.esploso || f.azione !== "onda") o.vita = Math.min(o.vita, 8);
      o.vita--;
      const m = maniDi(f);
      o.dir = f.dir; o.x0 = m.x + f.dir * 4 * S; o.y0 = m.y;
      o.max = f.dir > 0 ? W - o.x0 : o.x0;
      o.len = Math.min(o.max, o.len + 30 * S);
      o.scontro = null;
    }
    // Due onde una contro l'altra: si spingono, e il punto d'incontro sfavilla.
    const [a, b] = lottatori;
    if (a && b && a.onda && b.onda && a.onda.dir === -b.onda.dir && Math.abs(a.onda.y0 - b.onda.y0) < 28 * S) {
      const sx = a.onda.dir > 0 ? a : b, dx = sx === a ? b : a;
      if (sx.onda.x0 < dx.onda.x0 && sx.onda.x0 + sx.onda.len >= dx.onda.x0 - dx.onda.len) {
        if (scontroX === null) scontroX = (sx.onda.x0 + dx.onda.x0) / 2;
        scontroX += ((sx.potenziato ? 1 : 0) - (dx.potenziato ? 1 : 0) + caso(-1.4, 1.4)) * S;
        scontroX = Math.max(sx.onda.x0 + 10 * S, Math.min(dx.onda.x0 - 10 * S, scontroX));
        sx.onda.len = scontroX - sx.onda.x0; dx.onda.len = dx.onda.x0 - scontroX;
        sx.onda.scontro = dx.onda.scontro = scontroX;
        scintille(scontroX, (sx.onda.y0 + dx.onda.y0) / 2, 4, "#ffffff");
        scossa = Math.max(scossa, 3);
      }
    } else scontroX = null;
    for (const f of lottatori) {
      const o = f.onda;
      if (!o) continue;
      const altro = lottatori.find((l) => l !== f);
      if (!o.colpito && o.scontro === null && altro && !altro.ko && !altro.esploso && !altro.preso) {
        for (const n of ["testa", "collo", "bacino"]) {
          const q = altro.p[n], lungo = (q.x - o.x0) * o.dir;
          if (Math.abs(q.y - o.y0) < 9 * S + q.r && lungo > 0 && lungo < o.len) {
            o.colpito = true;
            colpisci(f, altro, 7.5 * (f.potenziato ? 1.3 : 1), q.x, q.y, "ZAAAP!");
            for (const k in altro.p) { altro.p[k].ox -= o.dir * 7 * S; altro.p[k].oy += 2 * S; }
            altro.inVolo = true; altro.ko = Math.max(altro.ko, 40);
            if (Math.random() < 0.3) smembra(altro, q.x, q.y);
            break;
          }
        }
      }
      if (!o.muro && o.scontro === null && o.len >= o.max - 1) {
        o.muro = true;
        danneggiaBordo(o.dir > 0 ? "destra" : "sinistra", o.y0, 1);
        scintille(o.dir > 0 ? W - 2 : 2, o.y0, 14, COLORI_ANIME[f.tipo]);
      }
      if (o.vita <= 0) f.onda = null;
    }
  }
  let scontroX = null;
  function disegnaOnda(f) {
    const o = f.onda, col = COLORI_ANIME[f.tipo];
    const k = Math.min(1, o.vita / 10), y = o.y0, x1 = o.x0, x2 = o.x0 + o.dir * o.len;
    const w = (8 + Math.sin(passi * 0.8) * 1.4) * S * k, l = Math.min(x1, x2), r = Math.max(x1, x2);
    ctx.save();
    ctx.globalAlpha = 0.3; ctx.fillStyle = col; rettangoloTondo(l, y - w * 1.9, r - l, w * 3.8, w * 1.9); ctx.fill();
    ctx.globalAlpha = 0.85; rettangoloTondo(l, y - w, r - l, w * 2, w); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff"; rettangoloTondo(l, y - w * 0.42, r - l, w * 0.84, w * 0.42); ctx.fill();
    ctx.globalAlpha = 0.5; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x2, y, w * 2.2, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1; tondo(x2, y, w * 1.1, "#ffffff");
    ctx.globalAlpha = 0.6; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x1, y, w * 1.6, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
  // La sfera che si carica fra le mani prima dell'onda.
  function disegnaCaricaOnda(f) {
    const m = maniDi(f), k = Math.min(1, f.t / 34), col = COLORI_ANIME[f.tipo];
    ctx.save();
    ctx.globalAlpha = 0.45; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(m.x, m.y, (3 + 9 * k) * S, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1; tondo(m.x, m.y, (1.5 + 4 * k) * S, "#ffffff");
    ctx.restore();
  }
  function disegnaAura(f) {
    const p = f.p, c = { x: (p.collo.x + p.bacino.x) / 2, y: (p.collo.y + p.bacino.y) / 2 }, col = COLORI_ANIME[f.tipo];
    const forte = f.azione === "carica" ? 1 : 0.7, sotto = c.y + 30 * S;
    ctx.save();
    ctx.fillStyle = col;
    for (let i = 0; i < 7; i++) {
      const off = Math.cos((i / 7) * Math.PI * 2 + passi * 0.03) * 17 * S;
      const alto = (58 + 16 * Math.sin(passi * 0.45 + i * 1.3)) * S * forte, ondeggia = Math.sin(passi * 0.3 + i) * 5 * S;
      ctx.globalAlpha = 0.16 * forte + 0.05;
      ctx.beginPath(); ctx.moveTo(c.x + off - 11 * S, sotto);
      ctx.quadraticCurveTo(c.x + off - 18 * S, c.y, c.x + off + ondeggia, sotto - alto);
      ctx.quadraticCurveTo(c.x + off + 18 * S, c.y, c.x + off + 11 * S, sotto); ctx.closePath(); ctx.fill();
    }
    if (f.potenziato > 0) {
      ctx.globalAlpha = 0.9; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.3 * S; ctx.lineJoin = "miter";
      for (let i = 0; i < 2; i++) {
        let x = c.x + caso(-22, 22) * S, y = c.y + caso(-40, 20) * S;
        ctx.beginPath(); ctx.moveTo(x, y);
        for (let k = 0; k < 4; k++) { x += caso(-6, 6) * S; y += caso(3, 7) * S; ctx.lineTo(x, y); }
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // --- Il volo dei super guerrieri ----------------------------------------
  // In modalità anime niente jetpack: si vola e basta. Si sta sospesi con le
  // gambe piegate, si scatta da un punto all'altro lasciando immagini
  // residue e linee di velocità, ci si scambia raffiche di pugni a mezz'aria,
  // gli scatti che si incontrano fanno un'onda d'urto, e chi colpisce forte
  // ricompare davanti all'avversario che vola via per rimandarlo indietro.
  const VOLO_VEL = 10;
  function prendiIlVolo(f) {
    const b = f.p.bacino;
    f.volo = true; f.jet = Math.round(caso(900, 1600)); f.caos = 0; f.azione = null; f.scalata = null; f.pensa = 8;
    f.volaY = Math.max(110, Math.min(pavimento - 70 * S, b.y - caso(60, 150) * S));
    f.paracadute = 0;
    for (const n in f.p) f.p[n].oy = f.p[n].y + 6 * S;
    const col = COLORI_ANIME[f.tipo];
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: b.x, y: b.y + 26 * S, vx: 0, vy: 0, vita: 16, max: 16, colore: col });
    for (let i = 0; i < 10 && particelle.length < MAX_PARTICELLE; i++) {
      const lato = i % 2 ? 1 : -1;
      particelle.push({ tipo: "polvere", x: b.x + lato * caso(4, 18) * S, y: b.y + 28 * S, vx: lato * caso(1.5, 3) * S, vy: -caso(0.2, 0.8) * S,
                        vita: Math.round(caso(18, 28)), max: 28, colore: "#b9b4ab" });
    }
  }
  // Lo scatto: un tratto in linea retta ad alta velocità verso un punto che
  // insegue l'avversario.
  function scatta(f, altro, frames) {
    if (!(f.jet > 0)) prendiIlVolo(f);
    f.scatto = frames || 22; f.bersaglio = altro; f.azione = null;
  }
  function aggiornaScatto(f) {
    const a = f.bersaglio, b = f.p.bacino;
    if (!a || a.esploso || f.ko || f.preso || f.tenuto) { f.scatto = 0; return; }
    const lato = b.x <= a.p.bacino.x ? -1 : 1;
    const tx = a.p.bacino.x + lato * 32 * S, ty = a.p.bacino.y;
    const dx = tx - b.x, dy = ty - b.y, d = Math.hypot(dx, dy);
    f.dir = -lato;
    if (d < 7 * S || --f.scatto <= 0) {
      f.scatto = 0;
      // Arrivato: si attacca subito.
      if (d < 40 * S && !a.ko) inizia(f, !maghi() && f.ki >= 8 && Math.random() < 0.55 ? "rush" : scegli([[3, "pugno"], [2, "calcio"], [2, "montante"]]));
      return;
    }
    const passo = Math.min(d, VOLO_VEL * S * (f.forma > 0 && f.potenziato > 0 ? 1.35 : 1)), ux = dx / d, uy = dy / d;
    for (const n in f.p) { const q = f.p[n]; q.x += ux * passo; q.y += uy * passo; q.ox += ux * passo; q.oy += uy * passo; }
    f.cx += ux * passo; f.meta = f.cx; f.volaY = b.y; f.base = b.y + 30 * S;
    f.vel = { x: ux, y: uy };
    if (passi % 2 === 0) residua(f);
    if (passi % 2 === 1 && particelle.length < MAX_PARTICELLE) {
      particelle.push({ tipo: "linea", x: b.x - ux * 18 * S + caso(-10, 10) * S * uy, y: b.y - uy * 18 * S + caso(-10, 10) * S * ux,
                        vx: -ux * 3 * S, vy: -uy * 3 * S, vita: 10, max: 10, lung: caso(14, 30) * S, colore: COLORI_ANIME[f.tipo] });
    }
  }
  // Un'immagine residua: la sagoma del corpo, ferma dove era, che sbiadisce.
  function residua(f) {
    if (scie.length > 24) scie.shift();
    const punti = {};
    for (const n in f.p) punti[n] = { x: f.p[n].x, y: f.p[n].y };
    scie.push({ f, punti, vita: 12, colore: COLORI_ANIME[f.tipo] });
  }
  function disegnaScie() {
    for (const sc of scie) {
      const p = sc.punti;
      ctx.save(); ctx.globalAlpha = 0.3 * sc.vita / 12; ctx.strokeStyle = sc.colore; ctx.fillStyle = sc.colore;
      ctx.lineCap = "round"; ctx.lineWidth = 5 * S; ctx.beginPath();
      for (const [a, b] of ASTE.slice(0, 10)) { ctx.moveTo(p[a].x, p[a].y); ctx.lineTo(p[b].x, p[b].y); }
      ctx.stroke();
      if (eMela(sc.f)) { const c = corpoMela(p); ctx.beginPath(); ctx.arc(c.x, c.y, c.R, 0, Math.PI * 2); ctx.fill(); }
      else { ctx.beginPath(); ctx.arc(p.testa.x, p.testa.y, 8.5 * S, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 15 * S; ctx.beginPath(); ctx.moveTo(p.collo.x, p.collo.y); ctx.lineTo(p.bacino.x, p.bacino.y); ctx.stroke(); }
      ctx.restore();
    }
  }
  let scie = [];

  function pensaGuerriero(f, altro) {
    const ob = altro.p.bacino, mio = f.p.bacino;
    f.dir = ob.x >= mio.x ? 1 : -1;
    if (altro.ko || altro.preso || altro.esploso) {
      // Ha vinto: scende a terra e (se è il caso) balla.
      f.jet = Math.min(f.jet, 40); f.meta = f.cx; f.pensa = 20; return;
    }
    const dx = Math.abs(ob.x - mio.x) / S, dy = Math.abs(ob.y - mio.y) / S, d = Math.hypot(dx, dy);
    if (f.jet < 60 || Math.random() < 0.025) { f.jet = Math.min(f.jet, 30); f.pensa = 30; return; }   // atterra
    if (mossaSpeciale(f, altro)) return;
    if (d > 60 && Math.random() < 0.55) { scatta(f, altro, 26); return; }
    if (!maghi() && d <= 46 && f.ki >= 8 && Math.random() < 0.4) { inizia(f, "rush"); return; }
    if (f.ki >= 45 && d > 70 && dy < 50 && Math.random() < 0.3) { inizia(f, "onda"); return; }
    if (f.ki >= 15 && d > 80 && Math.random() < 0.25) { inizia(f, "raffica"); return; }
    if (f.ki >= 15 && Math.random() < 0.12 && teletrasporta(f, altro)) return;
    if (d > 34) { scatta(f, altro, 16); return; }
    f.volaY = ob.y + caso(-6, 6) * S; f.meta = f.cx;
    inizia(f, scegli([[30 * f.aggr * pesoMossa(f, "pugno"), "pugno"], [22 * f.aggr * pesoMossa(f, "diretto"), "diretto"],
                      [16 * pesoMossa(f, "montante"), "montante"], [16 * f.aggr * pesoMossa(f, "calcio"), "calcio"],
                      [8 * f.furbo * pesoMossa(f, "para"), "para"], [maghi() ? 0 : 10 * f.ki / 100, "rush"]]));
  }

  // Raffica di pugni a distanza ravvicinata, chiusa da un colpo a due mani
  // che scaraventa via l'avversario (verso il basso se si è in aria).
  function colpettino(f, altro, x, y) {
    if (altro.azione === "para" && altro.dir === -f.dir) { scintille(x, y, 3, "#bfe9ff"); return; }
    scintille(x, y, 4, "#ffe27a");
    for (const n in altro.p) altro.p[n].ox -= f.dir * 0.5 * S;
    altro.dolore = 10; altro.stordito = Math.max(altro.stordito, 6); altro.azione = null;
    if (Math.random() < 0.3) segna(altro, x, y, 2);
    if (Math.random() < 0.25) schizza(altro, x, y, 1, 0.5);
    fermoColpo = Math.max(fermoColpo, 1);
    f.ki = Math.min(100, f.ki + 1);
  }
  function eseguiRush(f, altro) {
    const b = f.p.bacino, ob = altro.p.bacino;
    const vicino = Math.hypot(ob.x - b.x, ob.y - b.y) < 42 * S && !altro.ko && !altro.esploso && !altro.preso;
    // Si resta attaccati all'avversario, a distanza di pugno (non dentro).
    if (f.t < 30 && Math.abs(ob.x - b.x) < 26 * S) {
      const step = -f.dir * Math.min(3 * S, 26 * S - Math.abs(ob.x - b.x));
      for (const n in f.p) { f.p[n].x += step; f.p[n].ox += step; }
      f.cx += step;
    }
    if (!vicino && f.t < 30 && Math.hypot(ob.x - b.x, ob.y - b.y) < 90 * S) {
      const tx = ob.x - f.dir * 31 * S, step = Math.max(-5 * S, Math.min(5 * S, tx - b.x));
      for (const n in f.p) { f.p[n].x += step; f.p[n].ox += step; }
      f.cx += step;
      if (f.jet > 0) f.volaY = ob.y;
    }
    if (f.t < 30 && f.t % 4 === 2 && vicino) {
      const m = f.t % 8 === 2 ? f.p.manoA : f.p.manoD;
      colpettino(f, altro, (m.x + altro.p.collo.x) / 2, (m.y + altro.p.collo.y) / 2);
      if (f.t % 8 === 2 && passi % 2 === 0) scrivi(Math.random() < 0.5 ? "PAM!" : "TUM!", altro.p.collo.x, altro.p.collo.y - 14 * S, false);
    }
    if (f.t === 37 && vicino) {
      const inAria = altro.jet > 0 || altro.base - Math.max(altro.p.piedeA.y, altro.p.piedeD.y) > 20 * S;
      colpisci(f, altro, 6.5, altro.p.collo.x, altro.p.collo.y, "SBAAM!");
      const [vx, vy] = inAria ? [f.dir * 4, 14] : [f.dir * 12, -7];
      for (const n in altro.p) { altro.p[n].ox = altro.p[n].x - vx * S; altro.p[n].oy = altro.p[n].y - verso * vy * S; }
      altro.inVolo = true; altro.ko = Math.max(altro.ko, 50); altro.jet = 0; altro.recupero = 0;
      scossa = Math.max(scossa, 8);
      if (f.ki >= 15 && Math.random() < 0.6) { f.insegui = 10; f.catena = 0; }
    }
  }
  // Ping-pong: ricompare davanti a chi vola via e lo rispedisce indietro.
  function aggiornaInseguimento(f, altro) {
    if (!(f.insegui > 0) || --f.insegui > 0) return;
    const b = altro.p.bacino, vx = b.x - b.ox, vy = b.y - b.oy, v = Math.hypot(vx, vy);
    if (!altro.inVolo || v < 5 * S || altro.esploso || f.ko || f.preso || f.tenuto || f.ki < 10) { f.catena = 0; return; }
    let px = b.x + vx * 9, py = b.y + vy * 9;
    px = Math.max(40 * S, Math.min(W - 40 * S, px)); py = Math.max(80 * S, Math.min(pavimento - 40 * S, py));
    const da = { x: f.p.bacino.x, y: f.p.bacino.y }, sx = px + Math.sign(vx || 1) * 22 * S - f.p.bacino.x, sy = py - f.p.bacino.y;
    for (const n in f.p) { const q = f.p[n]; q.x += sx; q.y += sy; q.ox = q.x; q.oy = q.y; }
    f.cx += sx; f.ki -= 8;
    if (!(f.jet > 0)) prendiIlVolo(f);
    f.volaY = f.p.bacino.y; f.base = f.p.bacino.y + 30 * S;
    f.dir = vx > 0 ? -1 : 1;
    zip(da.x, da.y, COLORI_ANIME[f.tipo]); zip(f.p.bacino.x, f.p.bacino.y, COLORI_ANIME[f.tipo]);
    inizia(f, Math.random() < 0.5 ? "calcio" : "montante"); f.colpito = true;
    // Il colpo arriva subito: si rimanda indietro (l'ultimo della serie giù a terra).
    f.catena = (f.catena || 0) + 1;
    const ultimo = f.catena >= 3 || f.ki < 10;
    colpisci(f, altro, 4.2, (b.x + f.p.collo.x) / 2, (b.y + f.p.collo.y) / 2, ultimo ? "CRASH!" : "BAM!");
    const [nx, ny] = ultimo ? [f.dir * 3, 15] : [-vx * 0.9 / S, -Math.abs(vy) / S * 0.4 - 4];
    for (const n in altro.p) { altro.p[n].ox = altro.p[n].x - nx * S; altro.p[n].oy = altro.p[n].y - verso * ny * S; }
    altro.inVolo = true; altro.ko = Math.max(altro.ko, 40);
    if (!ultimo) f.insegui = 12; else f.catena = 0;
  }
  // Due scatti che si incontrano: onda d'urto e tutti e due respinti.
  function controllaScontro() {
    const [a, b] = lottatori;
    if (!a || !b || !(a.scatto > 0) || !(b.scatto > 0)) return;
    const pa = a.p.bacino, pb = b.p.bacino, d = Math.hypot(pa.x - pb.x, pa.y - pb.y);
    if (d > 34 * S) return;
    const x = (pa.x + pb.x) / 2, y = (pa.y + pb.y) / 2, ux = (pb.x - pa.x) / (d || 1), uy = (pb.y - pa.y) / (d || 1);
    a.scatto = b.scatto = 0;
    for (const [f, s] of [[a, -1], [b, 1]]) {
      for (const n in f.p) { f.p[n].ox = f.p[n].x - s * ux * 7 * S; f.p[n].oy = f.p[n].y - s * uy * 7 * S; }
      f.recupero = 18; f.azione = null; f.pensa = 10;
    }
    for (const k of [0, 6]) if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 24 + k, max: 24 + k, colore: "#ffffff" });
    scintille(x, y, 20, "#ffffff"); scintille(x, y, 10, COLORI_ANIME[a.tipo]); scintille(x, y, 10, COLORI_ANIME[b.tipo]);
    scossa = Math.max(scossa, 12); fermoColpo = 6;
  }

  // --- Le mosse speciali dei super guerrieri (02/10/2026) -----------------
  // Tutte nostre, col sapore degli anime di combattimento: la sfera gigante
  // che raccoglie energia da tutta la pagina, il disco tagliente, il lampo
  // che acceca, la barriera, e l'autodistruzione avvinghiati all'avversario
  // (che resta a terra in un cratere).
  function mossaSpeciale(f, altro) {
    const b = f.p.bacino, ob = altro.p.bacino, d = Math.hypot(ob.x - b.x, ob.y - b.y) / S;
    if (maghi()) return incantesimo(f, altro);
    // La trasformazione: a piena energia, o quando si sta per perdere.
    if (stile === "guerrieri" && !(f.potenziato > 0) && d > 40 &&
        ((f.ki >= 90 && Math.random() < 0.5) || (f.ki >= 40 && f.danni >= f.soglia - 1 && Math.random() < 0.45))) {
      f.ki = 100; inizia(f, "trasforma"); return true;
    }
    // Con le spalle al muro: ci si avvinghia e ci si fa saltare in aria.
    if (f.ki >= 30 && d < 320 && (f.danni >= f.soglia - 1 ? Math.random() < 0.3 : Math.random() < 0.02)) { inizia(f, "avvinghia"); return true; }
    // L'altro sta preparando qualcosa di grosso: barriera.
    if (f.ki >= 20 && (altro.azione === "onda" || altro.azione === "raffica" || altro.azione === "disco" || altro.sfera) && Math.random() < 0.4) { inizia(f, "barriera"); return true; }
    if (f.ki >= 85 && d > 110 && Math.random() < 0.35) { inizia(f, "sfera"); return true; }
    if (f.ki >= 60 && d > 50 && !altro.tenuto && (altro.stordito > 0 || altro.accecato > 0 ? Math.random() < 0.5 : Math.random() < 0.06)) { inizia(f, "telecinesi"); return true; }
    if (f.ki >= 25 && d > 70 && Math.random() < 0.12) { inizia(f, "disco"); return true; }
    if (f.ki >= 15 && d < 200 && !(altro.accecato > 0) && Math.random() < 0.07) { inizia(f, "lampo"); return true; }
    return false;
  }
  function eseguiSpeciale(f, altro) {
    if (f.azione === "sfera") {
      const m = { x: (f.p.manoA.x + f.p.manoD.x) / 2, y: Math.min(f.p.manoA.y, f.p.manoD.y) };
      if (f.t === 1) { f.ki = 0; f.sfera = { x: m.x, y: m.y - 10 * S, r: 4 * S }; }
      if (f.sfera && f.t < 112) {
        const k = f.t / 112;
        f.sfera.r = (4 + 30 * k) * S; f.sfera.x = m.x; f.sfera.y = m.y - 8 * S - f.sfera.r;
        // L'energia arriva da tutta la pagina.
        if (particelle.length < MAX_PARTICELLE) {
          const lato = Math.floor(Math.random() * 3);
          particelle.push({ tipo: "mote", x: lato === 0 ? 0 : lato === 1 ? W : caso(0, W), y: lato === 2 ? pavimento : caso(testataBasso, pavimento),
                            vx: 0, vy: 0, vita: 90, max: 90, verso: f, colore: Math.random() < 0.5 ? "#ffffff" : COLORI_ANIME[f.tipo] });
        }
        if (f.t % 30 === 0) scossa = Math.max(scossa, 2);
      }
      if (f.t === 112 && f.sfera) {
        const s = f.sfera, bx = altro.p.collo.x, by = altro.p.collo.y, d = Math.hypot(bx - s.x, by - s.y) || 1, v = 4.6 * S;
        proiettili.push({ x: s.x, y: s.y, vx: (bx - s.x) / d * v, vy: (by - s.y) / d * v, da: f, vita: 420, grande: true, r: s.r,
                          bersaglio: altro, colore: COLORI_ANIME[f.tipo] });
        f.sfera = null;
      }
    }
    if (f.azione === "disco" && f.t === 30 && f.ki >= 20) {
      f.ki -= 20;
      const m = f.p.manoA, bx = altro.p.collo.x, by = altro.p.collo.y, d = Math.hypot(bx - m.x, by - (m.y - 12 * S)) || 1, v = 10 * S;
      proiettili.push({ x: m.x, y: m.y - 12 * S, vx: (bx - m.x) / d * v, vy: (by - (m.y - 12 * S)) / d * v, da: f, vita: 200, disco: true,
                        colore: COLORI_ANIME[f.tipo] });
    }
    if (f.azione === "lampo" && f.t === 14 && f.ki >= 12) {
      f.ki -= 12;
      const t = f.p.testa;
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "lampo", x: t.x, y: t.y, vx: 0, vy: 0, vita: 14, max: 14, r: 420 * S });
      for (let i = 0; i < 10; i++) scintille(t.x, t.y, 2, "#ffffff");
      const lontano = Math.hypot(altro.p.testa.x - t.x, altro.p.testa.y - t.y) > 520 * S;
      if (!lontano && !altro.ko && !altro.esploso && altro.azione !== "barriera") {
        altro.accecato = 170; altro.azione = null; altro.scatto = 0; altro.onda = null;
        if (altro.tel) lasciaCadere(altro);
      }
    }
    if (f.azione === "barriera") {
      f.ki -= 0.25;
      if (f.ki <= 0) { f.ki = 0; f.azione = null; f.pensa = 10; }
    }
    if (f.azione === "avvinghia") eseguiAvvinghia(f, altro);
    if (f.azione === "telecinesi") eseguiTelecinesi(f, altro);
    if (f.azione === "trasforma") eseguiTrasforma(f, altro);
    if (f.azione === "gelo" && f.t === 16 && f.ki >= 20) { f.ki -= 20; lanciaIncanto(f, altro, "gelo"); }
    if (f.azione === "rimpicciolisci" && f.t === 16 && f.ki >= 25) { f.ki -= 25; lanciaIncanto(f, altro, "piccolo"); }
    if (f.azione === "fulmine" && f.t === 18 && f.ki >= 25) { f.ki -= 25; fulmini.push({ x: altro.p.collo.x, t: 0, da: f, punti: null }); }
    if (f.azione === "levita") eseguiLevita(f, altro);
  }
  // La presa a distanza: con una mano alzata si solleva l'avversario, che
  // resta sospeso a braccia e gambe larghe mentre una luce gli cresce dentro;
  // quando il pugno si chiude, va in mille pezzi (e poi si rimonta).
  const TELE_BOTTO = 112;
  function eseguiTelecinesi(f, altro) {
    if (f.t === 1) {
      if (altro.ko || altro.esploso || altro.preso || altro.tenuto || f.ki < 50) { f.azione = null; return; }
      f.ki -= 50;
      if (altro.tel) lasciaCadere(altro);
      if (altro.arma) lasciaArma(altro);
      if (altro.tiene) molla(altro);
      altro.jet = 0; altro.volo = false; altro.scatto = 0; altro.azione = null; altro.onda = null; altro.sfera = null; altro.paracadute = 0;
      altro.tenuto = { da: f, x: altro.p.collo.x, y: altro.p.collo.y, tele: 0 };
      altro.fantasma = true;
      zip(altro.p.bacino.x, altro.p.bacino.y, COLORI_ANIME[f.tipo]);
    }
    const t = altro.tenuto;
    if (!t || t.da !== f || altro.preso || altro.esploso) { f.azione = null; return; }
    t.tele = f.t;
    // Su, piano, fino a mezz'aria; poi fermo lì a tremare.
    const quota = Math.max(testataBasso + 90 * S, Math.min(pavimento - 230 * S, altro.base - 230 * S));
    if (t.y > quota) t.y -= 2.2 * S;
    t.x += caso(-1, 1) * S * Math.min(1, f.t / 60);
    t.x = Math.max(40 * S, Math.min(W - 40 * S, t.x));
    // Braccia e gambe tirate in fuori.
    const c = altro.p.collo;
    for (const n of ["manoA", "manoD", "piedeA", "piedeD"]) {
      const q = altro.p[n], lato = (n.endsWith("A") ? 1 : -1) * altro.dir;
      q.x += lato * 1.1 * S; q.y += (n.startsWith("mano") ? -0.9 : 0.25) * S;
    }
    if (f.t % 6 === 0) scintille(c.x + caso(-12, 12) * S, c.y + caso(-6, 20) * S, 2, "#fff3b0");
    if (f.t > 60) scossa = Math.max(scossa, 2);
    if (f.t >= TELE_BOTTO) {
      altro.tenuto = null;
      esplodiLottatore(altro, f);
      f.azione = null; f.pensa = 30;
    }
  }
  function disegnaTelecinesi(f) {
    // La luce che cresce dentro chi è sollevato, coi raggi che escono.
    const p = f.p, k = Math.min(1, f.tenuto.tele / TELE_BOTTO), x = (p.collo.x + p.bacino.x) / 2, y = (p.collo.y + p.bacino.y) / 2;
    ctx.save();
    const n = 9, lung = (10 + 46 * k) * S * (0.85 + 0.15 * Math.sin(passi * 0.9));
    ctx.fillStyle = "rgba(255,214,90," + (0.35 + 0.4 * k) + ")";
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + 0.3 * Math.sin(passi * 0.1 + i), w = (3 + 4 * k) * S;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a + 1.57) * w, y + Math.sin(a + 1.57) * w);
      ctx.lineTo(x + Math.cos(a) * lung * (i % 2 ? 1 : 0.7), y + Math.sin(a) * lung * (i % 2 ? 1 : 0.7));
      ctx.lineTo(x + Math.cos(a - 1.57) * w, y + Math.sin(a - 1.57) * w);
      ctx.closePath(); ctx.fill();
    }
    for (const [dx, dy, r] of [[0, 0, 1], [-0.6, 0.5, 0.7], [0.6, 0.4, 0.75], [-0.4, -0.6, 0.6], [0.5, -0.5, 0.65], [0, 0.9, 0.6]]) {
      const rr = (4 + 15 * k) * S * r, g = ctx.createRadialGradient(x + dx * rr, y + dy * rr, 0, x + dx * rr, y + dy * rr, rr);
      g.addColorStop(0, "rgba(255,255,235," + (0.5 + 0.45 * k) + ")"); g.addColorStop(1, "rgba(255,190,60,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x + dx * rr, y + dy * rr, rr, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }
  // La barriera ferma tutto, ma costa energia a ogni colpo; finita quella, va in frantumi.
  function barrieraRegge(f, forza, x, y) {
    if (f.azione !== "barriera") return false;
    const costo = 6 + forza * 2.5;
    const c = f.p.collo;
    if (f.ki >= costo) {
      f.ki -= costo;
      scintille(x, y, 8, COLORI_ANIME[f.tipo]);
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 10, max: 10, colore: COLORI_ANIME[f.tipo] });
      fermoColpo = Math.max(fermoColpo, 2);
      return true;
    }
    f.ki = 0; f.azione = null;
    schegge(c.x, c.y, 14, COLORI_ANIME[f.tipo]);
    scrivi("CRASH!", c.x, c.y - 40 * S, false);
    return false;
  }
  // Avvinghiati all'avversario: ci si aggrappa, si lampeggia sempre più in
  // fretta e si salta in aria. Chi si fa esplodere si rimonta; l'altro resta
  // a terra in un cratere.
  function eseguiAvvinghia(f, altro) {
    if (altro.esploso || altro.preso || (altro.ko > 0 && !altro.inVolo)) { f.azione = null; return; }
    const tx = altro.p.collo.x - f.dir * 12 * S, ty = altro.p.collo.y + 2 * S;
    if (f.t === 1) {
      f.ki = Math.max(0, f.ki - 30);
      zip(f.p.bacino.x, f.p.bacino.y, COLORI_ANIME[f.tipo]);
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (altro.jet > 0 && !(f.jet > 0)) prendiIlVolo(f);
    }
    const dx = tx - f.p.collo.x, dy = ty - f.p.collo.y, k = f.t === 1 ? 1 : 0.6;
    for (const n in f.p) { const q = f.p[n]; q.x += dx * k; q.y += dy * k; q.ox += dx * k; q.oy += dy * k; }
    f.cx += dx * k; f.scatto = 0; f.fantasma = true;
    if (f.jet > 0) f.volaY = f.p.bacino.y; else f.base = altro.base;
    // L'altro si divincola ma non si libera (quasi mai).
    altro.stordito = Math.max(altro.stordito, 4); altro.dolore = 8; altro.azione = null; altro.scatto = 0;
    for (const n of ["manoA", "manoD", "testa"]) altro.p[n].ox += caso(-1.5, 1.5) * S;
    if (f.t === 44 && altro.ki >= 35 && Math.random() < 0.25) {
      altro.ki -= 35;
      for (const n in f.p) { f.p[n].ox = f.p[n].x + f.dir * 9 * S; f.p[n].oy = f.p[n].y + 4 * S; }
      f.azione = null; f.stordito = 40; f.inVolo = true; f.ko = Math.max(f.ko, 30);
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: altro.p.collo.x, y: altro.p.collo.y, vx: 0, vy: 0, vita: 16, max: 16, colore: COLORI_ANIME[altro.tipo] });
      return;
    }
    const ogni = Math.max(2, Math.round(12 - f.t / 8));
    if (f.t % ogni === 0) scintille(f.p.collo.x, f.p.collo.y, 3, "#ff7a1a");
    if (f.t > 50) scossa = Math.max(scossa, 2);
    if (f.t >= 82) autodistruzione(f, altro);
  }
  function autodistruzione(f, altro) {
    f.azione = null;
    const giaKO = altro.koVero;
    esplodiLottatore(f, null, true);
    if (altro.esploso) return;
    if (!altro.koVero) segnaKO(f, altro);
    else if (!giaKO) { punteggio[f.tipo]++; controllaFinale(f.tipo, null, null); }
    altro.ko = 340; altro.inVolo = true; altro.jet = 0; altro.volo = false; altro.accecato = 0; altro.danni = 0;
    // Giù di schianto: dove tocca terra si apre il cratere.
    for (const n in altro.p) { altro.p[n].ox = altro.p[n].x - caso(-1, 1) * S; altro.p[n].oy = altro.p[n].y - verso * 12 * S; }
    altro.cratere = { attesa: true };
  }
  // La posa nel cratere: sdraiato di fianco, un braccio piegato sotto, un
  // ginocchio alzato.
  const POSA_CRATERE = { bacino: [2, 7], collo: [-17, 6], testa: [-28, 5.5], gomitoA: [-12, 3], manoA: [-22, 2.5],
                         gomitoD: [-20, 13], manoD: [-12, 8], ginocchioA: [13, 14], piedeA: [11, 2.5], ginocchioD: [15, 4], piedeD: [27, 3] };
  function posaCratere(f) {
    const c = f.cratere, q = {};
    for (const n in POSA_CRATERE) q[n] = [c.x + POSA_CRATERE[n][0] * c.dir * S, c.y - verso * POSA_CRATERE[n][1] * S];
    return q;
  }
  function aggiornaCratere(f) {
    const c = f.cratere;
    if (!c) return;
    if (c.attesa) {
      const b = f.p.bacino, v = Math.hypot(b.x - b.ox, b.y - b.oy);
      c.cadute = (c.cadute || 0) + 1;
      const giu = Math.abs(f.base - b.y) < 22 * S;
      if ((giu && v < 5 * S) || c.cadute > 200) {
        f.cratere = { x: b.x, y: f.base, t: 0, dir: f.dir, sassi: [0, 1, 2, 3, 4, 5, 6].map(() => [caso(-1, 1), caso(0.6, 1.4), caso(1.5, 3.5)]) };
        f.inVolo = false;          // fermo nel cratere: il conto alla rovescia del K.O. parte da qui
        polvere(b.x, f.base - 2, 12); scossa = Math.max(scossa, 10);
        for (let i = 0; i < 10 && particelle.length < MAX_PARTICELLE; i++) {
          particelle.push({ tipo: "detrito", x: b.x + caso(-30, 30) * S, y: f.base - 2, vx: caso(-3, 3) * S, vy: -caso(2, 6) * S * verso,
                            vita: 90, max: 90, rot: 0, va: caso(-0.3, 0.3), lato: caso(1.6, 3.4) * S, colore: "#8a7f70" });
        }
        if (f.base >= pavimento - 2) danneggiaStriscia(b.x, 0.85);
      }
      return;
    }
    c.t++;
    if (f.ko > 0 && !f.esploso) {
      if (c.t % 14 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "fumo", x: c.x + caso(-18, 18) * S, y: c.y - 8 * S, vx: caso(-0.2, 0.2) * S, vy: -caso(0.4, 0.9) * S,
                          vita: 60, max: 60, r: caso(3, 6) * S, colore: "#8d8a85" });
      }
    } else {
      c.fine = (c.fine || 0) + 1;
      if (c.fine > 150) f.cratere = null;
    }
  }
  function disegnaCratere(c) {
    if (!c || c.attesa) return;
    const a = c.fine ? Math.max(0, 1 - c.fine / 150) : Math.min(1, c.t / 8);
    ctx.save(); ctx.globalAlpha = a; ctx.translate(c.x, c.y);
    ctx.fillStyle = "rgba(92,74,54,.34)"; ctx.beginPath(); ctx.ellipse(0, 0, 58 * S, 9 * S, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "rgba(60,46,32,.42)"; ctx.beginPath(); ctx.ellipse(0, 1 * S, 42 * S, 6 * S, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "rgba(40,30,20,.7)"; ctx.lineWidth = 1.2 * S; ctx.lineCap = "round"; ctx.beginPath();
    for (let i = 0; i < 12; i++) {
      const an = (i / 12) * Math.PI * 2 + 0.2, x1 = Math.cos(an) * 44 * S, y1 = Math.sin(an) * 6.5 * S;
      const lung = (16 + (i * 37 % 13)) * S;
      ctx.moveTo(x1, y1); ctx.lineTo(x1 + Math.cos(an) * lung * 0.6, y1 + Math.sin(an) * lung * 0.16 + ((i % 2) ? 1.5 : -1.5) * S);
      ctx.lineTo(x1 + Math.cos(an) * lung, y1 + Math.sin(an) * lung * 0.2);
    }
    ctx.stroke();
    ctx.fillStyle = "#8a7f70";
    for (const [u, k, r] of c.sassi) { ctx.beginPath(); ctx.ellipse(u * 56 * S, -k * 2 * S, r * S, r * 0.7 * S, 0, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function disegnaSferaGrande(x, y, r, colore) {
    ctx.save();
    const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.1, x, y, r);
    g.addColorStop(0, "#ffffff"); g.addColorStop(0.4, colore); g.addColorStop(1, mix(colore, "#000000", 0.3));
    ctx.globalAlpha = 0.3; ctx.fillStyle = colore; ctx.beginPath(); ctx.arc(x, y, r * 1.4, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 0.95; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = mix(colore, "#000000", 0.35); ctx.lineWidth = 1.4 * S; ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 1.2 * S;
    for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.ellipse(x, y, r * 0.95, r * (0.25 + 0.2 * i), passi * 0.05 + i * 1.1, 0, Math.PI * 2); ctx.stroke(); }
    ctx.restore();
  }
  function disegnaDisco(x, y, r, colore) {
    ctx.save(); ctx.translate(x, y);
    ctx.globalAlpha = 0.4; ctx.fillStyle = colore; ctx.beginPath(); ctx.ellipse(0, 0, r * 1.25, r * 0.36, 0, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = "#fff9d0"; ctx.beginPath();
    for (let i = 0; i <= 28; i++) {
      const a = (i / 28) * Math.PI * 2, rr = r * (i % 2 ? 1 : 0.86), ph = a + passi * 0.6;
      const px = Math.cos(ph) * rr, py = Math.sin(ph) * rr * 0.26;
      if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
    }
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = colore; ctx.lineWidth = 1.2 * S; ctx.stroke();
    ctx.restore();
  }
  function disegnaBarriera(f) {
    const p = f.p, x = (p.testa.x + p.bacino.x) / 2, y = (p.testa.y + p.bacino.y) / 2 + 6 * S, r = 44 * S, col = COLORI_ANIME[f.tipo];
    ctx.save();
    const g = ctx.createRadialGradient(x, y, r * 0.55, x, y, r);
    g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(1, col);
    ctx.globalAlpha = 0.3 + 0.08 * Math.sin(passi * 0.3); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 0.85; ctx.strokeStyle = col; ctx.lineWidth = 1.8 * S; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1.4 * S;
    ctx.beginPath(); ctx.arc(x, y, r * 0.86, passi * 0.05, passi * 0.05 + 0.9); ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r * 0.86, passi * 0.05 + Math.PI, passi * 0.05 + Math.PI + 0.5); ctx.stroke();
    ctx.restore();
  }

  // --- I PERSONAGGI NUOVI (02/10/2026, su richiesta) ----------------------
  // Tre stili, tutti disegnati e inventati qui. I SUPER GUERRIERI hanno ora
  // una trasformazione, il «sovraccarico»: anelli di luce sopra la testa,
  // occhi accesi, colpi più forti (e una seconda forma, con tre sfere che
  // orbitano). I MAGHI lottano a incantesimi con la bacchetta e volano sulla
  // scopa. I DUELLANTI hanno una lama di energia: fendenti, affondi, lo
  // scatto che attraversa l'avversario, la lama lanciata, le lame incrociate.

  // ·· La trasformazione dei super guerrieri ··
  function eseguiTrasforma(f, altro) {
    const b = f.p.bacino, col = COLORI_ANIME[f.tipo];
    if (f.t < 70) {
      // La carica: la pagina trema sempre di più e chi è vicino viene tenuto lontano.
      f.ki = 100;
      scossa = Math.max(scossa, 1 + f.t / 14);
      if (f.t % 2 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "scintilla", x: b.x + caso(-20, 20) * S, y: f.base - 2 * S, vx: caso(-0.3, 0.3) * S, vy: -caso(2.5, 5) * S,
                          vita: 20, max: 20, colore: Math.random() < 0.4 ? "#ffffff" : col });
      }
      if (f.t % 7 === 0 && particelle.length < MAX_PARTICELLE && f.base >= pavimento - 2) {
        particelle.push({ tipo: "detrito", x: f.cx + caso(-34, 34) * S, y: f.base - 2, vx: caso(-0.4, 0.4) * S, vy: -caso(3, 6) * S,
                          vita: 70, max: 70, rot: 0, va: caso(-0.2, 0.2), lato: caso(1.6, 3.2) * S, colore: "#9a948a" });
      }
      if (f.t % 16 === 0 && particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: b.x, y: b.y - 10 * S, vx: 0, vy: 0, vita: 18, max: 18, colore: col });
      const d = altro.p.bacino.x - b.x;
      if (!altro.esploso && !altro.preso && !altro.tenuto && Math.abs(d) < 90 * S && Math.abs(altro.p.bacino.y - b.y) < 90 * S) {
        for (const n in altro.p) altro.p[n].ox -= Math.sign(d || 1) * 0.5 * S;
      }
      return;
    }
    if (f.t !== 70) return;
    f.forma = Math.min(2, (f.potenziato > 0 ? f.forma : 0) + 1);
    f.potenziato = 1500; f.ki = 100; f.danni = Math.max(0, f.danni - 1);
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "lampo", x: b.x, y: b.y - 14 * S, vx: 0, vy: 0, vita: 12, max: 12, r: 240 * S });
    for (const k of [0, 8]) if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: b.x, y: b.y - 12 * S, vx: 0, vy: 0, vita: 22 + k, max: 22 + k, colore: k ? "#ffffff" : col });
    scintille(b.x, b.y - 14 * S, 26, col); scintille(b.x, b.y - 14 * S, 12, "#ffffff");
    scossa = Math.max(scossa, 14); fermoColpo = Math.max(fermoColpo, 6);
    scrivi(f.forma >= 2 ? "SOVRACCARICO II!" : "SOVRACCARICO!", b.x, b.y - 62 * S, true);
    // L'onda d'urto sbalza via l'avversario, senza fargli danno.
    if (!altro.esploso && !altro.preso && !altro.tenuto) {
      const d = altro.p.bacino.x - b.x;
      if (Math.hypot(d, altro.p.bacino.y - b.y) < 200 * S) {
        const s = Math.sign(d || f.dir);
        for (const n in altro.p) { altro.p[n].ox -= s * 8 * S; altro.p[n].oy += verso * 3 * S; }
        altro.azione = null; altro.scatto = 0; altro.onda = null; altro.stordito = Math.max(altro.stordito, 20);
        if (altro.tel) lasciaCadere(altro);
      }
    }
  }
  // Finita l'energia si torna normali, col fiatone.
  function fineForma(f) {
    f.forma = 0;
    if (!f.p || f.esploso) return;
    const t = f.p.testa;
    for (let i = 0; i < 8 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "polvere", x: t.x + caso(-10, 10) * S, y: t.y - 14 * S, vx: caso(-1, 1) * S, vy: -caso(0.3, 1.2) * S,
                        vita: 24, max: 28, colore: COLORI_ANIME[f.tipo] });
    }
    if (!f.ko) f.stordito = Math.max(f.stordito, 30);
  }
  function cimaDi(f) {
    const t = f.p.testa, c = f.p.collo, L = Math.hypot(t.x - c.x, t.y - c.y) || 1;
    return { x: t.x + (t.x - c.x) / L * 13 * S, y: t.y + (t.y - c.y) / L * 13 * S };
  }
  function disegnaForma(f) {
    const col = COLORI_ANIME[f.tipo], cima = cimaDi(f);
    const y0 = cima.y - 5 * S * verso + Math.sin(passi * 0.08) * 1.2 * S;
    ctx.save();
    ctx.lineCap = "round";
    // Gli anelli sopra la testa: un alone e quattro archi che girano.
    for (let i = 0; i < f.forma; i++) {
      const rx = (11 + 4 * i) * S, ry = (3 + 1.2 * i) * S, yy = y0 - i * 4.5 * S * verso, giro = passi * 0.07 * (i ? -1 : 1);
      ctx.globalAlpha = 0.35; ctx.strokeStyle = col; ctx.lineWidth = 4.5 * S;
      ctx.beginPath(); ctx.ellipse(cima.x, yy, rx, ry, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 1; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.6 * S;
      for (let k = 0; k < 4; k++) { ctx.beginPath(); ctx.ellipse(cima.x, yy, rx, ry, 0, giro + k * Math.PI / 2, giro + k * Math.PI / 2 + 1.1); ctx.stroke(); }
    }
    // Seconda forma: tre sfere in orbita attorno al corpo.
    if (f.forma >= 2) {
      const cx = (f.p.collo.x + f.p.bacino.x) / 2, cy = (f.p.collo.y + f.p.bacino.y) / 2;
      for (let k = 0; k < 3; k++) {
        const a = passi * 0.09 + k * Math.PI * 2 / 3, x = cx + Math.cos(a) * 24 * S, y = cy + Math.sin(a) * 9 * S - 4 * S;
        ctx.globalAlpha = 0.4; tondo(x, y, 4.2 * S, col);
        ctx.globalAlpha = 1; tondo(x, y, 1.9 * S, "#ffffff");
      }
    }
    // Gli occhi accesi lasciano una scia.
    const ox = f.p.testa.x + f.dir * 3 * S, oy = f.p.testa.y;
    ctx.globalAlpha = 0.55; ctx.strokeStyle = col; ctx.lineWidth = 2 * S;
    ctx.beginPath(); ctx.moveTo(ox, oy); ctx.quadraticCurveTo(ox - f.dir * 7 * S, oy - 1 * S, ox - f.dir * 15 * S, oy - (4 + Math.sin(passi * 0.3) * 1.5) * S); ctx.stroke();
    ctx.restore();
  }

  // ·· I maghi ··
  const puntaBacchetta = (f) => {
    const g = f.p.gomitoA, m = f.p.manoA, L = Math.hypot(m.x - g.x, m.y - g.y) || 1;
    return { x: m.x + (m.x - g.x) / L * 14 * S, y: m.y + (m.y - g.y) / L * 14 * S };
  };
  const INCANTI = { gelo: 1, rimpicciolisci: 1, fulmine: 1, levita: 1, raffica: 1, onda: 1, carica: 1, barriera: 1, lampo: 1 };
  // Che incantesimo fare adesso (o nessuno: allora decide il resto del cervello).
  function incantesimo(f, altro) {
    const b = f.p.bacino, ob = altro.p.bacino, d = Math.hypot(ob.x - b.x, ob.y - b.y) / S;
    const fermo = altro.gelato > 0 || altro.stordito > 0 || altro.accecato > 0;
    if (f.ki >= 20 && (altro.azione === "onda" || altro.azione === "raffica" || altro.azione === "fulmine" || altro.azione === "gelo" || altro.azione === "rimpicciolisci") && Math.random() < 0.4) { inizia(f, "barriera"); return true; }
    if (f.ki >= 30 && d > 60 && !altro.tenuto && (fermo ? Math.random() < 0.3 : Math.random() < 0.07)) { inizia(f, "levita"); return true; }
    if (f.ki >= 25 && Math.random() < (fermo ? 0.35 : 0.12)) { inizia(f, "fulmine"); return true; }
    if (f.ki >= 20 && d > 50 && !(altro.gelato > 0) && Math.random() < 0.12) { inizia(f, "gelo"); return true; }
    if (f.ki >= 25 && d > 50 && !(altro.piccolo > 0) && Math.random() < 0.08) { inizia(f, "rimpicciolisci"); return true; }
    if (f.ki >= 15 && d < 200 && !(altro.accecato > 0) && Math.random() < 0.05) { inizia(f, "lampo"); return true; }
    return false;
  }
  function lanciaIncanto(f, altro, tipo) {
    const m = puntaBacchetta(f), bx = altro.p.collo.x, by = (altro.p.collo.y + altro.p.bacino.y) / 2;
    const d = Math.hypot(bx - m.x, by - m.y) || 1, v = 8.5 * S;
    proiettili.push({ x: m.x, y: m.y, vx: (bx - m.x) / d * v, vy: (by - m.y) / d * v, da: f, vita: 170, energia: true, incanto: tipo,
                      colore: tipo === "gelo" ? "#7fd4f7" : "#b77bff" });
    scintille(m.x, m.y, 6, tipo === "gelo" ? "#dff6ff" : "#e4ccff");
  }
  // Il gelo: chi lo prende resta in un blocco di ghiaccio, fermo com'era. Il
  // blocco cade e si appoggia sul piede più basso; un colpo lo manda in pezzi.
  function congela(f, da, x, y) {
    if (f.esploso || f.preso || f.tenuto || barrieraRegge(f, 3, x, y)) return;
    if (f.tel) lasciaCadere(f);
    if (f.tiene) molla(f);
    f.azione = null; f.scatto = 0; f.onda = null; f.sfera = null; f.jet = 0; f.volo = false; f.caos = 0; f.paracadute = 0; f.scalata = null;
    f.gelato = 190;
    const anc = (f.p.piedeA.y - f.p.piedeD.y) * verso >= 0 ? "piedeA" : "piedeD", a = f.p[anc];
    f.ghiaccio = { anc, off: {} };
    for (const n in f.p) f.ghiaccio.off[n] = { x: f.p[n].x - a.x, y: f.p[n].y - a.y };
    scintille(x, y, 10, "#dff6ff");
    scrivi("BRRR!", f.p.collo.x, f.p.collo.y - 34 * S, false);
    if (da && da.p) da.ki = Math.min(100, da.ki + 3);
  }
  function rompiGhiaccio(f, forte) {
    f.gelato = 0; f.ghiaccio = null;
    const c = f.p.collo;
    schegge(c.x, c.y + 8 * S, forte ? 16 : 8, "#bfeaff");
    if (forte) scrivi("CRACK!", c.x, c.y - 34 * S, false);
    if (!f.ko) f.stordito = Math.max(f.stordito, forte ? 12 : 24);
  }
  function disegnaGhiaccio(f) {
    let l = 1e9, t = 1e9, r = -1e9, b = -1e9;
    for (const n in f.p) { const q = f.p[n]; l = Math.min(l, q.x - q.r); r = Math.max(r, q.x + q.r); t = Math.min(t, q.y - q.r); b = Math.max(b, q.y + q.r); }
    l -= 9 * S; r += 9 * S; t -= 12 * S; b += 2 * S;
    const k = Math.min(1, f.gelato / 20), s = 7 * S;
    ctx.save();
    const g = ctx.createLinearGradient(l, t, r, b);
    g.addColorStop(0, "#eefbff"); g.addColorStop(1, "#86cdf0");
    ctx.fillStyle = g; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.6 * S; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(l + s, t); ctx.lineTo(r - s * 0.6, t + s * 0.3); ctx.lineTo(r, t + s * 1.4); ctx.lineTo(r - s * 0.3, b);
    ctx.lineTo(l + s * 0.4, b); ctx.lineTo(l, b - s); ctx.lineTo(l + s * 0.2, t + s); ctx.closePath();
    ctx.globalAlpha = 0.1 + 0.42 * k; ctx.fill();
    ctx.globalAlpha = 0.9 * k; ctx.stroke();
    ctx.strokeStyle = "#3f9fd0"; ctx.lineWidth = 0.9 * S; ctx.globalAlpha = 0.6 * k; ctx.stroke();
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.3 * S; ctx.globalAlpha = 0.85 * k; ctx.lineCap = "round"; ctx.beginPath();
    ctx.moveTo(l + s * 1.3, t + s * 1.2); ctx.lineTo(l + s * 1.0, t + (b - t) * 0.5);
    ctx.moveTo(l + s * 2.1, t + s); ctx.lineTo(l + s * 1.9, t + s * 2.4); ctx.stroke();
    ctx.restore();
  }
  // Rimpicciolito: per qualche secondo si è alti la metà e i colpi contano la metà.
  function rimpicciolisci(f, da, x, y) {
    if (f.esploso || barrieraRegge(f, 3, x, y)) return;
    f.piccolo = 520;
    const c = f.p.collo;
    for (let i = 0; i < 10 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "polvere", x: c.x + caso(-14, 14) * S, y: c.y + caso(-10, 24) * S, vx: caso(-1.4, 1.4) * S, vy: caso(-1.2, 0.2) * S,
                        vita: Math.round(caso(18, 30)), max: 30, colore: "#c9a6ff" });
    }
    scrivi("PUFF!", c.x, c.y - 30 * S, false);
    if (da && da.p) da.ki = Math.min(100, da.ki + 3);
  }
  // Il fulmine: un attimo di preavviso, poi cade dal tetto dove stava l'avversario.
  let fulmini = [];
  function aggiornaFulmini() {
    for (const z of fulmini) {
      if (++z.t !== 12) continue;
      const f = z.da, altro = z.contro || lottatori.find((l) => l !== f);
      const preso = !!(altro && !altro.esploso && !altro.preso && Math.abs(altro.p.collo.x - z.x) < 20 * S);
      const giu = preso ? altro.p.testa.y : pavimento;
      const n = 7;
      z.punti = [[z.x + caso(-30, 30) * S, 0]];
      for (let i = 1; i <= n; i++) z.punti.push([z.x + (i === n ? 0 : caso(-14, 14) * S), giu * i / n]);
      const m = z.punti[3];
      z.ramo = [m, [m[0] + caso(18, 34) * S * (Math.random() < 0.5 ? -1 : 1), m[1] + caso(20, 44) * S]];
      danneggiaBordo("tetto", z.punti[0][0], 0.6);
      scossa = Math.max(scossa, 9); fermoColpo = Math.max(fermoColpo, 3);
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "lampo", x: z.x, y: giu, vx: 0, vy: 0, vita: 8, max: 8, r: 150 * S });
      if (preso && f && (f.p || f.creatura)) {
        const prima = f.dir;
        if (f.p) f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        colpisci(f, altro, z.forza || 6.2, z.x, altro.p.collo.y, "KRAK!");
        f.dir = prima;
        if (!altro.ko) altro.stordito = Math.max(altro.stordito, 40);
      } else {
        danneggiaStriscia(z.x, 0.7); scintille(z.x, pavimento - 2, 12, "#fff3b0");
        scrivi("KRAK!", z.x, pavimento - 40 * S, false);
      }
    }
    if (fulmini.length) fulmini = fulmini.filter((z) => z.t < 22);
  }
  function disegnaFulmine(z) {
    ctx.save(); ctx.lineCap = "round"; ctx.lineJoin = "round";
    if (!z.punti) {
      // Il preavviso: un filo di luce e un cerchio a terra.
      ctx.globalAlpha = 0.2 + 0.2 * (z.t % 4 < 2 ? 1 : 0); ctx.strokeStyle = "#fff3b0"; ctx.lineWidth = 1.2 * S;
      ctx.beginPath(); ctx.moveTo(z.x, 0); ctx.lineTo(z.x, pavimento); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(z.x, pavimento - 1, (6 + z.t * 1.4) * S, (2 + z.t * 0.3) * S, 0, 0, Math.PI * 2); ctx.stroke();
    } else {
      const k = Math.max(0, (22 - z.t) / 10);
      const traccia = () => {
        ctx.beginPath(); ctx.moveTo(z.punti[0][0], z.punti[0][1]);
        for (let i = 1; i < z.punti.length; i++) ctx.lineTo(z.punti[i][0], z.punti[i][1]);
        ctx.moveTo(z.ramo[0][0], z.ramo[0][1]); ctx.lineTo(z.ramo[1][0], z.ramo[1][1]);
      };
      ctx.globalAlpha = 0.45 * k; ctx.strokeStyle = "#ffe27a"; ctx.lineWidth = 9 * S; traccia(); ctx.stroke();
      ctx.globalAlpha = Math.min(1, k); ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2.6 * S; traccia(); ctx.stroke();
    }
    ctx.restore();
  }
  // La levitazione: la bacchetta alza l'avversario a mezz'aria, lo tiene lì
  // un momento e lo lascia cadere di schianto.
  function eseguiLevita(f, altro) {
    if (f.t === 1) {
      if (altro.ko || altro.esploso || altro.preso || altro.tenuto || f.ki < 30) { f.azione = null; return; }
      f.ki -= 30;
      if (altro.tel) lasciaCadere(altro);
      if (altro.arma) lasciaArma(altro);
      if (altro.tiene) molla(altro);
      altro.jet = 0; altro.volo = false; altro.scatto = 0; altro.azione = null; altro.onda = null; altro.sfera = null; altro.paracadute = 0;
      altro.tenuto = { da: f, x: altro.p.collo.x, y: altro.p.collo.y, y0: altro.p.collo.y, tele: 0, magia: true };
      altro.fantasma = true;
    }
    const t = altro.tenuto;
    if (!t || t.da !== f || altro.preso || altro.esploso) { f.azione = null; return; }
    t.tele = f.t;
    if (f.t < 70) {
      const su = t.y - verso * 2.4 * S;
      if ((t.y0 - t.y) * verso < 160 * S && su > testataBasso + 70 * S && su < pavimento - 50 * S) t.y = su;
      t.x = Math.max(40 * S, Math.min(W - 40 * S, t.x + Math.sin(f.t * 0.2) * 1.2 * S));
    }
    if (f.t >= 78) {
      // Giù di schianto: la botta, all'arrivo, conta come un colpo.
      altro.tenuto = null;
      for (const n in altro.p) { altro.p[n].ox = altro.p[n].x; altro.p[n].oy = altro.p[n].y - verso * 15 * S; }
      altro.inVolo = true; altro.ko = Math.max(altro.ko, 60); altro.caduta = f;
      f.azione = null; f.pensa = 20;
    }
  }
  function disegnaLevitazione(f) {
    const p = f.p, x = (p.collo.x + p.bacino.x) / 2, y = (p.collo.y + p.bacino.y) / 2, col = COLORI_ANIME[f.tenuto.da.tipo];
    ctx.save();
    ctx.globalAlpha = 0.16; ctx.fillStyle = col; ctx.beginPath();
    ctx.moveTo(x - 9 * S, y + 26 * S); ctx.lineTo(x + 9 * S, y + 26 * S); ctx.lineTo(x + 22 * S, pavimento); ctx.lineTo(x - 22 * S, pavimento); ctx.closePath(); ctx.fill();
    ctx.globalAlpha = 1;
    for (let i = 0; i < 6; i++) {
      const a = passi * 0.12 + i * Math.PI / 3;
      stella(x + Math.cos(a) * 27 * S, y + Math.sin(a) * 10 * S, 2.3 * S, i % 2 ? "#ffffff" : col);
    }
    ctx.restore();
  }
  function disegnaBacchetta(f) {
    if ((f.staccati && f.staccati.A) || f.tel || f.arma) return;
    const m = f.p.manoA, q = puntaBacchetta(f), col = COLORI_ANIME[f.tipo], lancia = !!INCANTI[f.azione];
    linea(m, q, 2.1 * S, "#5a3a1e");
    linea({ x: m.x + (q.x - m.x) * 0.72, y: m.y + (q.y - m.y) * 0.72 }, q, 1.5 * S, "#f3e3c2");
    ctx.save();
    ctx.globalAlpha = lancia ? 0.55 : 0.3; tondo(q.x, q.y, (lancia ? 4.5 + Math.sin(passi * 0.6) : 2.6) * S, col);
    ctx.globalAlpha = 1; tondo(q.x, q.y, 1.3 * S, "#ffffff");
    ctx.restore();
  }
  // In volo i maghi stanno a cavallo di una scopa.
  function disegnaScopa(f) {
    const b = f.p.bacino, d = f.dir, y = b.y + 5 * S;
    const testa = { x: b.x + d * 26 * S, y: y - 3 * S }, coda = { x: b.x - d * 20 * S, y: y + 2 * S };
    const sv = Math.sin(passi * 0.5) * 1.2 * S;
    ctx.save();
    ctx.fillStyle = "#d9a441"; ctx.strokeStyle = "#8a6420"; ctx.lineWidth = 1 * S; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(coda.x, coda.y - 2.2 * S); ctx.lineTo(coda.x - d * 16 * S, coda.y - 6 * S + sv);
    ctx.lineTo(coda.x - d * 19 * S, coda.y + 1 * S - sv); ctx.lineTo(coda.x - d * 15 * S, coda.y + 7 * S + sv);
    ctx.lineTo(coda.x, coda.y + 2.6 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.restore();
    linea(coda, testa, 2.4 * S, "#7a5230");
    linea({ x: coda.x, y: coda.y - 2.6 * S }, { x: coda.x, y: coda.y + 3 * S }, 1.8 * S, "#5a3a1e");
  }

  // ·· I duellanti ··
  const TAGLI = { fendente: 1, affondo: 1, rovescio: 1 };
  const lamaPronta = (f) => !!(stile === "lame" && f.lama && !f.lama.lanciata && !(f.staccati && f.staccati.A) && !f.tel && !f.arma);
  function accendiLama(f) { f.lama = { acceso: 0, lanciata: false, fuori: 0, scia: [] }; }
  // Base e punta della lama, nella finestra: continua l'avambraccio.
  function lamaDi(f) {
    const g = f.p.gomitoA, m = f.p.manoA, L = Math.hypot(m.x - g.x, m.y - g.y) || 1;
    const ux = (m.x - g.x) / L, uy = (m.y - g.y) / L, lung = 31 * S * Math.min(1, f.lama ? f.lama.acceso : 1);
    return { x0: m.x + ux * 4 * S, y0: m.y + uy * 4 * S, x1: m.x + ux * (4 * S + lung), y1: m.y + uy * (4 * S + lung), ux, uy, lung };
  }
  let duello = 0;
  function pensaLama(f, altro) {
    if (!lamaPronta(f)) return false;
    if (Math.abs(altro.base - f.base) > 40 * S) return false;      // livelli diversi: scale e discese come sempre
    const d = Math.abs(altro.cx - f.cx) / S;
    f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
    if (duello > 0 && lamaPronta(altro) && !altro.stordito && !(altro.jet > 0)) {
      // Chiesto dalla tendina: ci si viene incontro e si colpisce insieme.
      if (d > 44) { inizia(f, "avanza", altro.cx - f.dir * 34 * S); return true; }
      inizia(f, "fendente");
      if (!TAGLI[altro.azione]) { altro.dir = -f.dir; inizia(altro, "fendente"); }
      return true;
    }
    if (altro.azione && (TAGLI[altro.azione] || altro.azione === "scattoLama") && d < 60 && Math.random() < 0.35 * f.furbo) { inizia(f, "para"); return true; }
    if (d <= 44) {
      inizia(f, scegli([[30 * f.aggr, "fendente"], [24 * f.aggr, "affondo"], [20, "rovescio"], [8 * f.furbo, "para"], [8, "indietro"]]));
      return true;
    }
    if (altro.jet > 0 && verso > 0 && Math.random() < 0.3) { decolla(f, false); return true; }
    if (d > 60 && d < 260 && !(altro.jet > 0) && Math.random() < 0.28) { inizia(f, "scattoLama"); return true; }
    if (d > 150 && Math.random() < 0.1) { inizia(f, "lancioLama"); return true; }
    inizia(f, "avanza", altro.cx - f.dir * 34 * S);
    return true;
  }
  function eseguiLama(f, altro) {
    if (f.azione === "scattoLama") {
      if (f.t === 1) { f.daScatto = null; if (!lamaPronta(f)) { f.azione = null; return; } }
      if (f.t === 10) {
        // Dall'altra parte dell'avversario in quattro fotogrammi.
        const arrivo = Math.max(24 * S, Math.min(W - 24 * S, altro.p.bacino.x + f.dir * 46 * S));
        f.daScatto = { passo: (arrivo - f.p.bacino.x) / 4, parato: altro.azione === "para" && altro.dir === -f.dir, dir: f.dir, vale: false };
      }
      const ds = f.daScatto;
      if (!ds) return;
      if (f.t >= 10 && f.t < 14) {
        residua(f);
        for (const n in f.p) { f.p[n].x += ds.passo; f.p[n].ox += ds.passo; }
        f.cx += ds.passo; f.meta = f.cx; f.fantasma = true;
        if (particelle.length < MAX_PARTICELLE) {
          particelle.push({ tipo: "linea", x: f.p.bacino.x, y: f.p.bacino.y + caso(-16, 10) * S, vx: -ds.dir * 3 * S, vy: 0, vita: 10, max: 10,
                            lung: caso(16, 34) * S, colore: COLORI_ANIME[f.tipo] });
        }
      }
      if (f.t === 14) {
        const c = altro.p.collo, y = (c.y + altro.p.bacino.y) / 2;
        const passato = (f.p.bacino.x - altro.p.bacino.x) * ds.dir > 0;
        const vicino = Math.abs(altro.p.bacino.y - f.p.bacino.y) < 50 * S && !altro.esploso && !altro.preso && !altro.tenuto;
        if (particelle.length < MAX_PARTICELLE) {
          particelle.push({ tipo: "taglio", x: c.x, y, vx: 0, vy: 0, vita: 26, max: 26, ang: -ds.dir * caso(0.2, 0.5), lung: 46 * S, colore: COLORI_ANIME[f.tipo] });
        }
        if (passato && vicino) {
          if (ds.parato) { scintille(c.x, y, 12, "#ffffff"); scrivi("CLANG!", c.x, y - 12 * S, false); fermoColpo = Math.max(fermoColpo, 3); }
          else { ds.vale = true; altro.azione = null; altro.scatto = 0; if (!altro.ko) altro.stordito = Math.max(altro.stordito, 20); }
        }
      }
      if (f.t === 32) {
        // Si volta a guardare: solo adesso il taglio fa effetto.
        f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        if (ds.vale && !altro.esploso && !altro.preso) colpisci(f, altro, 6.2, altro.p.collo.x, (altro.p.collo.y + altro.p.bacino.y) / 2, "ZAC!");
      }
    }
    if (f.azione === "lancioLama" && f.t === 14 && lamaPronta(f)) {
      const l = lamaDi(f), bx = altro.p.collo.x, by = altro.p.collo.y, d = Math.hypot(bx - l.x0, by - l.y0) || 1, v = 10.5 * S;
      proiettili.push({ x: l.x0, y: l.y0, vx: (bx - l.x0) / d * v, vy: (by - l.y0) / d * v, da: f, vita: 170, disco: true, lamaDi: f,
                        colore: COLORI_ANIME[f.tipo] });
      f.lama.lanciata = true; f.lama.fuori = 0;
    }
    if (f.azione === "pressa") {
      // Lame incrociate: ci si spinge, piovono scintille, e alla fine uno dei due cede.
      if (altro.azione !== "pressa") { f.azione = null; f.pensa = 6; return; }
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (f.tipo !== "robot") return;                // i conti si fanno una volta sola per coppia
      const la = lamaDi(f), lb = lamaDi(altro), x = (la.x1 + lb.x1) / 2, y = (la.y1 + lb.y1) / 2;
      if (f.t % 2 === 0) scintille(x, y, 2, f.t % 4 ? "#ffffff" : "#ffe27a");
      if (f.t % 12 === 0) scossa = Math.max(scossa, 2);
      const spinta = Math.sin(f.t * 0.21) * 0.5 * S * f.dir;
      f.cx += spinta; altro.cx += spinta;
      if (f.t >= 44) {
        const vince = Math.random() < f.aggr / (f.aggr + altro.aggr) ? f : altro, perde = vince === f ? altro : f;
        for (const n in perde.p) { perde.p[n].ox -= vince.dir * 6 * S; perde.p[n].oy += verso * 1.5 * S; }
        perde.azione = null; perde.stordito = Math.max(perde.stordito, 34);
        vince.azione = null; vince.pensa = 2; vince.combo = 1;
        scintille(x, y, 10, "#ffffff");
        scrivi("SWISH!", x, y - 12 * S, false);
      }
    }
  }
  // Due lame che si incontrano a metà colpo: nessuno dei due va a segno.
  function controllaLame(a, b) {
    if (!TAGLI[a.azione] || !TAGLI[b.azione] || a.colpito || b.colpito || !lamaPronta(a) || !lamaPronta(b)) return;
    const ra = COLPI[a.azione], rb = COLPI[b.azione];
    if (a.t < ra[1] - 2 || a.t > ra[2] || b.t < rb[1] - 2 || b.t > rb[2]) return;
    const la = lamaDi(a), lb = lamaDi(b);
    const ax = (la.x0 + la.x1) / 2, ay = (la.y0 + la.y1) / 2, bx = (lb.x0 + lb.x1) / 2, by = (lb.y0 + lb.y1) / 2;
    if (Math.hypot(ax - bx, ay - by) > 28 * S) return;
    const x = (ax + bx) / 2, y = (ay + by) / 2;
    a.colpito = b.colpito = true;
    scintille(x, y, 14, "#ffffff"); scintille(x, y, 6, COLORI_ANIME.robot); scintille(x, y, 6, COLORI_ANIME.mela);
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 12, max: 12, colore: "#ffffff" });
    scrivi("CLANG!", x, y - 12 * S, false);
    scossa = Math.max(scossa, 5); fermoColpo = Math.max(fermoColpo, 4);
    if ((duello > 0 || Math.random() < 0.5) && !(a.jet > 0) && !(b.jet > 0)) {
      duello = 0;
      inizia(a, "pressa"); inizia(b, "pressa");
      return;
    }
    const dir = Math.sign(b.cx - a.cx) || 1;
    for (const [f, s] of [[a, -1], [b, 1]]) {
      for (const n in f.p) f.p[n].ox -= s * dir * 3.5 * S;
      f.azione = null; f.pensa = Math.round(caso(4, 12));
    }
  }
  function aggiornaLame() {
    if (duello > 0) duello--;
    for (const f of lottatori) {
      const L = f.lama;
      if (!L) continue;
      L.acceso = Math.min(1, L.acceso + 0.12);
      if (L.lanciata && ++L.fuori > 240) rientraLama(f);
      const colpo = lamaPronta(f) && !f.esploso && (TAGLI[f.azione] || (f.azione === "scattoLama" && f.t >= 9 && f.t <= 16));
      if (colpo) { const l = lamaDi(f); L.scia.push({ x0: l.x0, y0: l.y0, x1: l.x1, y1: l.y1 }); if (L.scia.length > 6) L.scia.shift(); }
      else if (L.scia.length) L.scia.shift();
    }
  }
  // La lama lanciata torna in mano: si riaccende da capo.
  function rientraLama(f) {
    if (!f || !f.lama) return;
    f.lama.lanciata = false; f.lama.fuori = 0; f.lama.acceso = 0;
    if (f.p && !f.esploso) scintille(f.p.manoA.x, f.p.manoA.y, 6, COLORI_ANIME[f.tipo]);
  }
  function sagomaLama(x0, y0, x1, y1, larg) {
    const L = Math.hypot(x1 - x0, y1 - y0) || 1, ux = (x1 - x0) / L, uy = (y1 - y0) / L, nx = -uy * larg, ny = ux * larg, punta = Math.min(6 * S, L * 0.4);
    ctx.beginPath(); ctx.moveTo(x0 + nx, y0 + ny);
    ctx.lineTo(x1 - ux * punta + nx * 0.75, y1 - uy * punta + ny * 0.75); ctx.lineTo(x1, y1);
    ctx.lineTo(x1 - ux * punta - nx * 0.75, y1 - uy * punta - ny * 0.75); ctx.lineTo(x0 - nx, y0 - ny); ctx.closePath(); ctx.fill();
  }
  function disegnaLama(f) {
    const L = f.lama;
    if (!L || L.lanciata || (f.staccati && f.staccati.A) || f.tel || f.arma) return;
    const l = lamaDi(f), col = COLORI_ANIME[f.tipo], m = f.p.manoA;
    ctx.save(); ctx.lineCap = "round";
    // La scia del colpo.
    ctx.fillStyle = col;
    for (let i = 1; i < L.scia.length; i++) {
      const a = L.scia[i - 1], b = L.scia[i];
      ctx.globalAlpha = 0.3 * i / L.scia.length;
      ctx.beginPath(); ctx.moveTo(a.x0, a.y0); ctx.lineTo(a.x1, a.y1); ctx.lineTo(b.x1, b.y1); ctx.lineTo(b.x0, b.y0); ctx.closePath(); ctx.fill();
    }
    ctx.globalAlpha = 1;
    // L'impugnatura scura, con la guardia del colore della lama.
    linea({ x: m.x - l.ux * 5 * S, y: m.y - l.uy * 5 * S }, { x: l.x0, y: l.y0 }, 3.2 * S, "#23262e");
    linea({ x: m.x - l.ux * 5.5 * S, y: m.y - l.uy * 5.5 * S }, { x: m.x - l.ux * 4.5 * S, y: m.y - l.uy * 4.5 * S }, 4 * S, "#8d96a6");
    linea({ x: l.x0 - l.uy * 4 * S, y: l.y0 + l.ux * 4 * S }, { x: l.x0 + l.uy * 4 * S, y: l.y0 - l.ux * 4 * S }, 2.4 * S, col);
    if (l.lung > 1) {
      // La lama: alone, colore, anima bianca; tremola e finisce a punta.
      const tr = 0.85 + 0.15 * Math.sin(passi * 0.9 + (f.tipo === "mela" ? 2 : 0));
      ctx.fillStyle = col; ctx.globalAlpha = 0.28 * tr; sagomaLama(l.x0, l.y0, l.x1, l.y1, 5.2 * S);
      ctx.globalAlpha = 0.9; sagomaLama(l.x0, l.y0, l.x1, l.y1, 2.6 * S);
      ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff"; sagomaLama(l.x0, l.y0, l.x1, l.y1, 1.1 * S);
    }
    ctx.restore();
  }
  function disegnaLamaVolante(b) {
    const a = passi * 0.7, ux = Math.cos(a) * 16 * S, uy = Math.sin(a) * 16 * S;
    ctx.save();
    ctx.fillStyle = b.colore; ctx.globalAlpha = 0.25; ctx.beginPath(); ctx.arc(b.x, b.y, 17 * S, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 0.9; sagomaLama(b.x - ux, b.y - uy, b.x + ux, b.y + uy, 2.6 * S);
    ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff"; sagomaLama(b.x - ux, b.y - uy, b.x + ux, b.y + uy, 1.1 * S);
    ctx.restore();
  }
  // I duellanti portano una sciarpa lunga, del colore della lama.
  function sciarpa(f) {
    const col = COLORI_ANIME[f.tipo], p = f.p;
    const x = p.collo.x - f.dir * 3 * S, y = p.collo.y + 2 * S;
    const lag = Math.max(-10 * S, Math.min(10 * S, (p.collo.ox - p.collo.x) * 6));
    ctx.save(); ctx.strokeStyle = col; ctx.lineCap = "round"; ctx.lineWidth = 3 * S;
    for (const k of [0, 1]) {
      ctx.globalAlpha = k ? 0.7 : 1;
      ctx.beginPath(); ctx.moveTo(x, y);
      ctx.quadraticCurveTo(x - f.dir * 10 * S + lag * 0.5, y + (2 + 5 * k + 2 * Math.sin(passi * 0.2 + k)) * S,
                           x - f.dir * (20 + 3 * k) * S + lag, y + (-2 + 9 * k + 3 * Math.sin(passi * 0.26 + k * 2)) * S);
      ctx.stroke();
    }
    ctx.restore();
  }

  // ·· I personaggi inventati ··
  // Due per stile, uno per lato. Nomi, facce e vestiti sono nostri: non
  // richiamano né il robot né la mela, né personaggi di altri.
  const ASPETTI = {
    guerrieri: {
      robot: { nome: "ZEFIR", pelle: "#e8b98a", capelli: "#22324f", tuta: "#1f8f8a", bordo: "#f4f1e6", maniche: "#e8b98a", gambe: "#22324f", scarpe: "#3a3f4a", testa: "onda" },
      mela: { nome: "BRASA", pelle: "#9a623c", capelli: "#d43d7a", tuta: "#7a1f2b", bordo: "#f0b23a", maniche: "#9a623c", gambe: "#1d1d24", scarpe: "#f0b23a", testa: "treccia" },
    },
    maghi: {
      robot: { nome: "MERLO", pelle: "#f0c9a4", capelli: "#e3e6ea", tuta: "#4b2f8f", bordo: "#ffd84a", maniche: "#4b2f8f", gambe: "#4b2f8f", scarpe: "#5a3a1e", testa: "cappello", cappello: "#4b2f8f", veste: true, barba: true },
      mela: { nome: "ORTICA", pelle: "#c98f6a", capelli: "#e8742a", tuta: "#1f6f7a", bordo: "#bfe36a", maniche: "#1f6f7a", gambe: "#1f6f7a", scarpe: "#2a2a33", testa: "cappello", cappello: "#1f6f7a", veste: true, codini: true },
    },
    lame: {
      robot: { nome: "ROVO", pelle: "#d9a77c", capelli: "#1b1e27", tuta: "#27314a", bordo: "#56e1ff", maniche: "#27314a", gambe: "#1b1e27", scarpe: "#27314a", testa: "visiera" },
      mela: { nome: "SCIA", pelle: "#f1d2b8", capelli: "#ff62d6", tuta: "#e9e6ee", bordo: "#ff62d6", maniche: "#e9e6ee", gambe: "#3a3340", scarpe: "#8a8494", testa: "caschetto" },
    },
  };
  const aspetto = (f) => ASPETTI[stile][f.tipo];
  const nomeProprio = (tipo) => { const n = ASPETTI[stile][tipo].nome; return n.charAt(0) + n.slice(1).toLowerCase(); };
  const scuro = (colore) => mix(colore, "#000000", 0.22);

  function pugno(gomito, mano, A, colore, lontano) {
    const L = Math.hypot(mano.x - gomito.x, mano.y - gomito.y) || 1, ux = (mano.x - gomito.x) / L, uy = (mano.y - gomito.y) / L;
    // Il polsino, poi la mano.
    linea({ x: mano.x - ux * 5 * S, y: mano.y - uy * 5 * S }, { x: mano.x - ux * 2.4 * S, y: mano.y - uy * 2.4 * S }, 4.6 * S, colore);
    ctx.fillStyle = lontano ? scuro(A.pelle) : A.pelle; ctx.strokeStyle = "#17171c"; ctx.lineWidth = 1 * S;
    ctx.beginPath(); ctx.arc(mano.x, mano.y, 3.2 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  }
  // La faccia, nel riferimento della testa (su = -y): cambia con quello che succede.
  function facciaUmana(f, A, luce) {
    const d = f.dir, nero = "#17171c";
    const attacca = !!COLPI[f.azione] || !!TAGLI[f.azione] || ["lancia", "spara", "presa", "rush", "scattoLama", "pressa", "gelo", "rimpicciolisci", "fulmine", "raffica", "onda", "lancioLama"].indexOf(f.azione) >= 0;
    const festa = f.azione === "esulta" || f.azione === "provoca" || f.azione === "balla";
    const urla = f.azione === "trasforma" || f.azione === "carica";
    const ey = -0.6 * S;
    if (A.testa === "visiera") {
      // Il duellante guarda da dietro una visiera accesa.
      ctx.fillStyle = "#12141b"; rettangoloTondo(-7.6 * S + d * 0.8 * S, ey - 2.6 * S, 15.2 * S, 5 * S, 2.2 * S); ctx.fill();
      ctx.strokeStyle = f.ko ? "#5b6170" : A.bordo; ctx.lineWidth = 1.5 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(d * 0.8 * S - 4.6 * S, ey - 0.1 * S); ctx.lineTo(d * 0.8 * S + 4.6 * S, ey - (attacca ? 1 : 0.1) * S * d); ctx.stroke();
    } else if (f.ko || f.rialzo > 30 || f.dolore || f.stordito) {
      occhi(f, 0, ey, 2.8 * S, 1.3 * S, nero);
    } else if (festa) {
      ctx.strokeStyle = nero; ctx.lineWidth = 1.3 * S; ctx.lineCap = "round";
      for (const lato of [-1, 1]) { ctx.beginPath(); ctx.arc(lato * 2.8 * S + d * 1.2 * S, ey + 0.8 * S, 1.5 * S, Math.PI * 1.05, Math.PI * 1.95); ctx.stroke(); }
    } else {
      const batte = Math.floor(passi / 3) % 80 === 0 ? 0.3 : 1;
      for (const lato of [-1, 1]) {
        const x0 = lato * 2.8 * S + d * 1.2 * S;
        ctx.fillStyle = luce || nero; ctx.beginPath(); ctx.ellipse(x0, ey, 1.25 * S, 1.6 * S * batte, 0, 0, Math.PI * 2); ctx.fill();
        if (!luce) tondo(x0 + d * 0.4 * S, ey - 0.5 * S, 0.45 * S, "#ffffff");
        if (attacca || urla || luce) {
          ctx.strokeStyle = nero; ctx.lineWidth = 1.2 * S; ctx.lineCap = "round"; ctx.beginPath();
          ctx.moveTo(x0 - 1.8 * S, ey - (lato === d ? 3.4 : 2.3) * S); ctx.lineTo(x0 + 1.8 * S, ey - (lato === d ? 2.3 : 3.4) * S); ctx.stroke();
        }
      }
    }
    // La bocca.
    const bx = d * 1.6 * S, by = 3.6 * S;
    ctx.strokeStyle = nero; ctx.fillStyle = nero; ctx.lineWidth = 1.2 * S; ctx.lineCap = "round"; ctx.beginPath();
    if (f.ko || f.rialzo > 30) { ctx.ellipse(bx, by, 1.5 * S, 1.1 * S, 0, 0, Math.PI * 2); ctx.stroke(); }
    else if (f.dolore || f.stordito) { ctx.moveTo(bx - 2.2 * S, by + 0.5 * S); ctx.lineTo(bx - 0.7 * S, by - 0.5 * S); ctx.lineTo(bx + 0.7 * S, by + 0.5 * S); ctx.lineTo(bx + 2.2 * S, by - 0.5 * S); ctx.stroke(); }
    else if (urla) { ctx.ellipse(bx, by + 0.3 * S, 2 * S, 2.3 * S, 0, 0, Math.PI * 2); ctx.fill(); }
    else if (attacca) { ctx.ellipse(bx, by, 1.8 * S, 1.3 * S, 0, 0, Math.PI * 2); ctx.fill(); }
    else if (festa) { ctx.moveTo(bx - 2.4 * S, by - 0.6 * S); ctx.quadraticCurveTo(bx, by + 2.6 * S, bx + 2.4 * S, by - 0.6 * S); ctx.closePath(); ctx.fill(); }
    else { ctx.moveTo(bx - 1.8 * S, by); ctx.quadraticCurveTo(bx, by + 1.2 * S, bx + 1.8 * S, by); ctx.stroke(); }
  }
  // Capelli e cappelli, sempre nel riferimento della testa.
  function capoUmano(f, A, bordo, dietro) {
    const d = f.dir, nero = "#17171c", sv = Math.sin(passi * 0.25) * S;
    const lag = Math.max(-5 * S, Math.min(5 * S, (f.p.testa.ox - f.p.testa.x) * 2));
    ctx.strokeStyle = nero; ctx.lineWidth = 1 * S; ctx.lineJoin = "round"; ctx.lineCap = "round";
    if (dietro) {
      // Quello che sta dietro la testa: trecce, codini, la fascia che sventola.
      if (A.testa === "treccia") {
        for (let i = 0; i < 5; i++) {
          const k = i / 4;
          tondo(-d * (7.5 + 3.5 * k) * S + lag * k, (-2 + 15 * k) * S + sv * k, (3.3 - 1.5 * k) * S, A.capelli);
        }
        tondo(-d * 11.4 * S + lag, 14.6 * S + sv, 1.5 * S, bordo);
      } else if (A.codini) {
        for (const k of [0, 1]) tondo(-d * (8 + 2.5 * k) * S + lag * 0.6, (1 + 4 * k) * S + sv * 0.5, (4 - 0.8 * k) * S, A.capelli);
      } else if (A.testa === "onda") {
        ctx.strokeStyle = bordo; ctx.lineWidth = 1.8 * S;
        for (const k of [0, 1]) {
          ctx.beginPath(); ctx.moveTo(-d * 7.6 * S, -3 * S);
          ctx.quadraticCurveTo(-d * 12 * S + lag, (-2 + 3 * k) * S + sv, -d * (16 + 2 * k) * S + lag * 1.5, (0 + 6 * k) * S - sv);
          ctx.stroke();
        }
      }
      return;
    }
    ctx.fillStyle = A.capelli;
    if (A.testa === "onda") {
      // Un ciuffo pettinato all'indietro e la fascia in fronte.
      ctx.beginPath(); ctx.moveTo(d * 7.4 * S, -3.6 * S); ctx.quadraticCurveTo(d * 6 * S, -11.5 * S, -d * 1 * S, -11 * S);
      ctx.quadraticCurveTo(-d * 7 * S, -11.5 * S, -d * 11 * S, -9 * S); ctx.quadraticCurveTo(-d * 8.6 * S, -6 * S, -d * 8.2 * S, 0.5 * S);
      ctx.quadraticCurveTo(-d * 6 * S, -5 * S, d * 7.4 * S, -3.6 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = bordo; ctx.lineWidth = 2 * S; ctx.beginPath(); ctx.moveTo(d * 7.7 * S, -3.3 * S); ctx.quadraticCurveTo(0, -5.2 * S, -d * 7.9 * S, -3 * S); ctx.stroke();
    } else if (A.testa === "treccia") {
      ctx.beginPath(); ctx.moveTo(d * 7.6 * S, -2.4 * S); ctx.quadraticCurveTo(d * 5 * S, -10.6 * S, -d * 2 * S, -9.6 * S);
      ctx.quadraticCurveTo(-d * 9.6 * S, -8.6 * S, -d * 8.4 * S, 1.5 * S); ctx.quadraticCurveTo(-d * 5 * S, -4.4 * S, d * 2 * S, -4.8 * S);
      ctx.quadraticCurveTo(d * 5.4 * S, -4.6 * S, d * 7.6 * S, -2.4 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = bordo; ctx.lineWidth = 1.6 * S; ctx.beginPath(); ctx.moveTo(-d * 6.6 * S, -6.6 * S); ctx.lineTo(-d * 8.8 * S, -2.6 * S); ctx.stroke();
    } else if (A.testa === "cappello") {
      if (A.barba) {
        // Una barba bianca a punta, coi baffi.
        ctx.fillStyle = A.capelli; ctx.beginPath(); ctx.moveTo(-d * 4.6 * S, 1.6 * S); ctx.quadraticCurveTo(d * 2 * S, 3.4 * S, d * 7.6 * S, 1.2 * S);
        ctx.quadraticCurveTo(d * 6.4 * S, 10 * S, d * 2.4 * S + lag * 0.5, 16 * S); ctx.quadraticCurveTo(-d * 2.6 * S, 9 * S, -d * 4.6 * S, 1.6 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      } else {
        // La frangia.
        ctx.beginPath(); ctx.moveTo(d * 7.7 * S, -2.2 * S); ctx.quadraticCurveTo(d * 2 * S, -6.4 * S, -d * 7.9 * S, -3.4 * S);
        ctx.lineTo(-d * 7.4 * S, -5.6 * S); ctx.lineTo(d * 7 * S, -5.6 * S); ctx.closePath(); ctx.fill();
      }
      // Il cappello a punta, con la falda larga, la fascia e una stella.
      ctx.fillStyle = A.cappello; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.moveTo(-7.4 * S, -5.4 * S); ctx.quadraticCurveTo(-d * 2 * S, -15 * S, -d * 4.6 * S + lag, -25 * S + sv);
      ctx.quadraticCurveTo(d * 3 * S, -15 * S, 7.4 * S, -5.4 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(0, -5.4 * S, 13 * S, 2.8 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = bordo; ctx.lineWidth = 1.8 * S; ctx.beginPath(); ctx.moveTo(-6.4 * S, -7.6 * S); ctx.quadraticCurveTo(0, -6.2 * S, 6.4 * S, -7.6 * S); ctx.stroke();
      stella(-d * 1 * S, -12.6 * S, 1.9 * S, bordo);
    } else if (A.testa === "visiera") {
      // Capelli corti e scuri, tirati su.
      ctx.beginPath(); ctx.moveTo(d * 7.6 * S, -4.4 * S); ctx.quadraticCurveTo(d * 5 * S, -11.4 * S, -d * 3 * S, -10.4 * S);
      ctx.quadraticCurveTo(-d * 9 * S, -8.4 * S, -d * 8.2 * S, -1 * S); ctx.quadraticCurveTo(-d * 6 * S, -5.4 * S, d * 7.6 * S, -4.4 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else {
      // Il caschetto: copre la nuca fino al mento, con la frangia.
      ctx.beginPath(); ctx.moveTo(d * 7.8 * S, -2 * S); ctx.quadraticCurveTo(d * 6 * S, -11.6 * S, -d * 1.6 * S, -10.6 * S);
      ctx.quadraticCurveTo(-d * 10.6 * S, -9 * S, -d * 9.6 * S, 5.4 * S + sv * 0.4); ctx.lineTo(-d * 5.2 * S, 5 * S);
      ctx.quadraticCurveTo(-d * 5.4 * S, -3.4 * S, d * 1 * S, -4.6 * S); ctx.quadraticCurveTo(d * 5 * S, -4.4 * S, d * 7.8 * S, -2 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
  }
  function disegnaUmano(f) {
    const p = f.p, A = aspetto(f), st = f.staccati || {}, nero = "#17171c", d = f.dir, [ginA, ginD] = ginocchia(f);
    // Trasformato: i bordi del vestito e gli occhi si accendono del suo colore.
    const acceso = stile === "guerrieri" && f.forma > 0 && f.potenziato > 0;
    const bordo = acceso ? COLORI_ANIME[f.tipo] : A.bordo;
    if (f.furia > 0) {
      const g = ctx.createRadialGradient(p.bacino.x, p.bacino.y - 14 * S, 4 * S, p.bacino.x, p.bacino.y - 14 * S, 38 * S);
      g.addColorStop(0, "rgba(255,70,30,.45)"); g.addColorStop(1, "rgba(255,70,30,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.bacino.x, p.bacino.y - 14 * S, 38 * S, 0, Math.PI * 2); ctx.fill();
    }
    if (!anime) zaino(f, 9.5 * S);                 // i duellanti il jetpack ce l'hanno ancora
    if (A.veste) mantello(f, p, scuro(A.tuta));
    // Gamba e braccio lontani.
    if (!st.gD) arto(p.bacino, ginD, p.piedeD, 5 * S, scuro(A.gambe));
    if (!st.D) { arto(p.collo, p.gomitoD, p.manoD, 4.2 * S, scuro(A.maniche)); pugno(p.gomitoD, p.manoD, A, scuro(bordo), true); }
    if (!st.gA) arto(p.bacino, ginA, p.piedeA, 5 * S, A.gambe);
    // Le scarpe.
    for (const piede of [p.piedeD, p.piedeA]) {
      if ((piede === p.piedeD && st.gD) || (piede === p.piedeA && st.gA)) continue;
      ctx.fillStyle = A.scarpe; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.ellipse(piede.x + d * 1.4 * S, piede.y - 0.4 * S, 4.4 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    // La veste lunga dei maghi segue le ginocchia.
    if (A.veste) {
      const ord = [[ginA, p.piedeA], [ginD, p.piedeD]].sort((u, v) => (u[0].x - v[0].x) * d);
      const giu = ([g, pd]) => ({ x: g.x + (pd.x - g.x) * 0.5, y: g.y + (pd.y - g.y) * 0.5 });
      const dietro = giu(ord[0]), davanti = giu(ord[1]);
      ctx.fillStyle = A.tuta; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S; ctx.lineJoin = "round"; ctx.beginPath();
      ctx.moveTo(p.bacino.x - d * 8 * S, p.bacino.y - 4 * S); ctx.lineTo(p.bacino.x + d * 8 * S, p.bacino.y - 4 * S);
      ctx.lineTo(davanti.x + d * 5.5 * S, davanti.y); ctx.lineTo(dietro.x - d * 5.5 * S, dietro.y); ctx.closePath(); ctx.fill(); ctx.stroke();
      linea({ x: dietro.x - d * 5 * S, y: dietro.y - 1.4 * S }, { x: davanti.x + d * 5 * S, y: davanti.y - 1.4 * S }, 1.6 * S, bordo);
    }
    // Il busto.
    const ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2;
    const lung = Math.hypot(p.bacino.x - p.collo.x, p.bacino.y - p.collo.y);
    ctx.save();
    ctx.translate((p.collo.x + p.bacino.x) / 2, (p.collo.y + p.bacino.y) / 2); ctx.rotate(ang);
    ctx.fillStyle = sfumatura(0, 0, lung, mix(A.tuta, "#ffffff", 0.18), A.tuta); ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S;
    rettangoloTondo(-7.6 * S, -lung / 2 - 3 * S, 15.2 * S, lung + 7 * S, 5 * S); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = bordo; ctx.lineCap = "round"; ctx.lineWidth = 1.6 * S; ctx.beginPath();
    if (stile === "guerrieri") {
      // La casacca incrociata e la fascia in vita, annodata.
      ctx.moveTo(-5 * S, -lung / 2 - 2 * S); ctx.lineTo(d * 3 * S, lung / 2 - 6 * S);
      ctx.moveTo(5 * S, -lung / 2 - 2 * S); ctx.lineTo(d * 0.5 * S, -lung / 2 + 5 * S); ctx.stroke();
      ctx.fillStyle = bordo; ctx.fillRect(-7.6 * S, lung / 2 - 5.4 * S, 15.2 * S, 2.8 * S);
      ctx.fillRect(-d * 4.4 * S - 1 * S, lung / 2 - 4.6 * S, 2 * S, 7.5 * S);
    } else if (stile === "maghi") {
      // Il cordone in vita e le stelle sulla veste.
      ctx.moveTo(-7.6 * S, lung / 2 - 4 * S); ctx.lineTo(7.6 * S, lung / 2 - 4 * S); ctx.stroke();
      stella(-d * 2.6 * S, -lung / 2 + 5.5 * S, 1.8 * S, bordo); stella(d * 3 * S, -lung / 2 + 11 * S, 1.3 * S, bordo);
    } else {
      // La giacca del duellante: una riga accesa e lo spallaccio.
      ctx.moveTo(d * 1.5 * S, -lung / 2 - 1.5 * S); ctx.lineTo(d * 1.5 * S, lung / 2 + 2 * S); ctx.stroke();
      ctx.fillStyle = scuro(A.tuta); ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
      rettangoloTondo(-8.6 * S, -lung / 2 - 4 * S, 17.2 * S, 5.4 * S, 2.6 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#1b1e27"; ctx.fillRect(-7.6 * S, lung / 2 - 4.6 * S, 15.2 * S, 2.2 * S);
    }
    disegnaSegni(f, "busto");
    ctx.restore();
    // La testa.
    const angT = Math.atan2(p.testa.y - p.collo.y, p.testa.x - p.collo.x) + Math.PI / 2;
    ctx.save(); ctx.translate(p.testa.x, p.testa.y); ctx.rotate(angT);
    capoUmano(f, A, bordo, true);
    ctx.fillStyle = A.pelle; ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S;
    ctx.beginPath(); ctx.arc(0, 0, 8 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    facciaUmana(f, A, acceso ? COLORI_ANIME[f.tipo] : null);
    disegnaSegni(f, "testa");
    capoUmano(f, A, bordo, false);
    const tg = temaGravita();
    if (tg === "luna" || tg === "spazio") { ctx.save(); ctx.translate(0, -1 * S); casco(13.5 * S); ctx.restore(); }
    ctx.restore();
    // Il braccio vicino.
    if (!st.A) { arto(p.collo, p.gomitoA, p.manoA, 4.2 * S, A.maniche); pugno(p.gomitoA, p.manoA, A, bordo, false); }
    if (f.palla && !st.A) tondo(p.manoA.x, p.manoA.y - 3 * S, 3 * S, "#ffffff");
  }
  // Si cambia stile: escono di scena i vecchi lottatori ed entrano i nuovi,
  // in una nuvoletta, dove stavano gli altri. Il punteggio resta.
  function cambiaCorpi() {
    if (!lottatori.length) return;
    for (const t of telefoni) if (t.stato !== "libero") { t.stato = "libero"; t.da = null; t.ox = t.x; t.oy = t.y; }
    proiettili = []; arti = []; pezzi = []; scie = []; fulmini = []; duello = 0;
    presa.f = null; radiceHtml("remove", "ring-trascina");
    lottatori = lottatori.map((v) => {
      const x = Math.max(30 * S, Math.min(W - 30 * S, Number.isFinite(v.cx) ? v.cx : W / 2));
      const f = crea(v.tipo, x, v.dir, Math.min(Number.isFinite(v.base) ? v.base : pavimento, pavimento));
      for (let i = 0; i < 9 && particelle.length < MAX_PARTICELLE; i++) {
        particelle.push({ tipo: "polvere", x: x + caso(-14, 14) * S, y: f.base - caso(4, 56) * S, vx: caso(-1.3, 1.3) * S, vy: caso(-1, 0.2) * S,
                          vita: Math.round(caso(18, 30)), max: 30, colore: "#d9d4cc" });
      }
      return f;
    });
    if (lame()) for (const f of lottatori) accendiLama(f);
  }

  // Tutto quello che si disegna di un lottatore, nell'ordine giusto. Chi è
  // stato rimpicciolito viene disegnato in scala, coi piedi fermi dove sono.
  function disegnaLottatore(f) {
    const k = f.scala, stretto = k < 0.98;
    if (stretto) {
      const px = f.p.bacino.x, py = verso > 0 ? Math.max(f.p.piedeA.y, f.p.piedeD.y) : Math.min(f.p.piedeA.y, f.p.piedeD.y);
      ctx.save(); ctx.translate(px, py); ctx.scale(k, k); ctx.translate(-px, -py);
    }
    disegnaParacadute(f);
    if (anime && (f.azione === "carica" || f.azione === "trasforma" || f.potenziato > 0 || (f.azione === "onda" && f.t < 34) || f.scatto > 0)) disegnaAura(f);
    if (stile === "maghi" && f.volo && f.jet > 0) disegnaScopa(f);
    if (stile === "lame") sciarpa(f);
    (stile ? disegnaUmano : f.tipo === "robot" ? disegnaRobot : disegnaMela)(f);
    if (stile === "maghi") disegnaBacchetta(f);
    if (stile === "lame") disegnaLama(f);
    if (stile === "guerrieri" && f.forma > 0 && f.potenziato > 0) disegnaForma(f);
    if (stretto) ctx.restore();
    if (f.gelato > 0) disegnaGhiaccio(f);
  }

  // --- Le barre della vita ------------------------------------------------
  // In alto, sotto la testata, come in un picchiaduro: robot a sinistra,
  // mela a destra, il punteggio in mezzo. La parte persa resta chiara per
  // un attimo prima di sparire. In modalità anime, sotto, l'energia.
  function vitaVera(f) {
    if (f.esploso || f.koVero) return 0;
    return Math.max(0, 1 - f.danni / Math.max(1, f.soglia));
  }
  function aggiornaVite() {
    for (const f of lottatori) {
      const v = vitaVera(f);
      f.vitaVista += (v - f.vitaVista) * 0.2;
      if (f.vitaScia > f.vitaVista) f.vitaScia = Math.max(f.vitaVista, f.vitaScia - 0.006);
      else f.vitaScia = f.vitaVista;
    }
  }
  function disegnaBarre() {
    // Sottosopra i lottatori stanno in alto: le barre scendono sopra la striscia.
    const m = 16, h = 12 * S, w = Math.min(300 * S, (W - 2 * m - 70 * S) / 2);
    const y = verso < 0 ? pavimento - (anime ? 34 : 26) * S : Math.max(22 * S, testataBasso + 22 * S);
    ctx.save();
    ctx.font = "800 " + Math.round(11 * S) + "px Archivo, sans-serif"; ctx.textBaseline = "bottom";
    ctx.lineWidth = 3 * S; ctx.strokeStyle = "#ffffff"; ctx.lineJoin = "round";
    for (const f of lottatori) {
      const sinistra = f.tipo === "robot", x = sinistra ? m : W - m - w;
      ctx.fillStyle = "#1b1b1b"; rettangoloTondo(x - 2 * S, y - 2 * S, w + 4 * S, h + 4 * S, 4 * S); ctx.fill();
      const pieno = (k) => (sinistra ? [x, k * w] : [x + w - k * w, k * w]);
      let [ax, aw] = pieno(f.vitaScia);
      ctx.fillStyle = "#ffb3a8"; ctx.fillRect(ax, y, aw, h);
      [ax, aw] = pieno(f.vitaVista);
      ctx.fillStyle = f.vitaVista > 0.5 ? "#2fbf71" : f.vitaVista > 0.25 ? "#f2c230" : "#e0443a";
      ctx.fillRect(ax, y, aw, h);
      ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.fillRect(ax, y, aw, h * 0.35);
      ctx.textAlign = sinistra ? "left" : "right";
      const nome = (stile ? aspetto(f).nome : f.tipo === "robot" ? "ROBOT" : dici("Mela").toUpperCase()) + (f.forma > 0 && f.potenziato > 0 ? " " + "\u2605".repeat(f.forma) : "");
      ctx.fillStyle = "#141414"; ctx.strokeText(nome, sinistra ? x : x + w, y - 3 * S); ctx.fillText(nome, sinistra ? x : x + w, y - 3 * S);
      if (anime) {
        const yk = y + h + 4 * S, hk = 5 * S;
        ctx.fillStyle = "#1b1b1b"; ctx.fillRect(x - 1 * S, yk - 1 * S, w + 2 * S, hk + 2 * S);
        const kw = (f.ki / 100) * w;
        ctx.fillStyle = f.ki >= 100 && passi % 10 < 5 ? "#ffffff" : COLORI_ANIME[f.tipo];
        ctx.fillRect(sinistra ? x : x + w - kw, yk, kw, hk);
      }
    }
    ctx.textAlign = "center";
    ctx.font = "800 " + Math.round(15 * S) + "px Archivo, sans-serif";
    const punti = punteggio.robot + " – " + punteggio.mela;
    ctx.fillStyle = "#141414"; ctx.strokeText(punti, W / 2, y + h + 2 * S); ctx.fillText(punti, W / 2, y + h + 2 * S);
    ctx.restore();
  }

  // --- Eventi a sorpresa -----------------------------------------------
  // Gli eventi NON si annunciano con scritte sulla pagina (01/10/2026, su
  // richiesta: toglievano pulizia al sito): si vedono da quello che succede.

  function avviaEvento() {
    const quale = scegli([[3, "luna"], [3, "furia"], [3, "pioggia"], [2, "rallenta"], [2, "terremoto"], [3, "jet"], [uragano || !libero("meteo") ? 0 : 1, "uragano"]]);
    if (quale === "uragano") { uragano = { x: Math.random() < 0.5 ? 100 * S : W - 100 * S, vx: 1.1 * S, t: 0 }; evento = { nome: quale, durata: 600 }; return; }
    if (quale === "luna") { moltG = 0.45; evento = { nome: quale, durata: 620 };  }
    else if (quale === "pioggia") { daSpawnare = 7;  }
    else if (quale === "rallenta") { ritmo = 0.45; evento = { nome: quale, durata: 150 };  }
    else if (quale === "jet") { for (const f of lottatori) if (!f.ko && !f.preso) decolla(f, true); }
    else if (quale === "terremoto") { evento = { nome: quale, durata: 230 };  }
    else {
      const f = lottatori[Math.floor(Math.random() * lottatori.length)];
      f.furia = 560;
    }
  }

  function fineEvento() {
    if (evento && evento.nome === "uragano" && !uraganoFisso) uragano = null;
    moltG = gravitaScelta; ritmo = rallentaFisso ? 0.45 : 1; evento = null;
  }
  let uraganoFisso = false, rallentaFisso = false;

  function aggiornaEventi() {
    if (fermo) return;
    if (--prossimoEvento <= 0) { if (sorprese && !evento) avviaEvento(); prossimoEvento = Math.round(caso(1500, 2700)); }
    if (--prossimoTelefono <= 0) {
      const calmo = tempo < CALMA, inGiro = telefoni.filter((t) => !eArma(t)).length;
      if (inGiro < (calmo ? 2 : 4)) faEntrare(undefined, caso(60, W - 60), caso(-1.5, 1.5) * S);
      prossimoTelefono = Math.round(calmo ? caso(600, 1200) : caso(380, 950));
    }
    // Dopo 70 secondi piovono anche le armi, una alla volta.
    if (tempo >= ARMI && libero("armi") && --prossimaArma <= 0) {
      if (telefoni.filter((t) => eArma(t) || t.tipo === "bomba").length < 2) {
        faEntrare(scegli([[2, "pistola"], [2, "spada"], [1, "bomba"]]), caso(80, W - 80), caso(-1, 1) * S);
      }
      prossimaArma = Math.round(caso(800, 1600));
    }
    if (daSpawnare > 0 && passi % 14 === 0) {
      daSpawnare--;
      const t = faEntrare(senzaTelefoni ? oggettoACaso() : undefined, caso(60, W - 60), caso(-2, 2) * S);
      // Nella pioggia di oggetti dell'estensione tutto arriva già innescato.
      if (senzaTelefoni) { t.armato = !!SPECIALI[t.tipo]; if (t.tipo === "bomba") t.miccia = Math.round(caso(140, 260)); }
    }
    if (evento) {
      if (evento.nome === "terremoto" && passi % 6 === 0) {
        scossa = 4;
        for (const f of lottatori) for (const n in f.p) { f.p[n].ox += caso(-1.4, 1.4) * S; f.p[n].oy += caso(0, 1.6) * S; }
        for (const t of telefoni) if (t.stato === "libero") { t.oy += caso(1, 3) * S; t.ox += caso(-2, 2) * S; }
      }
      if (--evento.durata <= 0) fineEvento();
    }
    for (const f of lottatori) {
      if (f.furia > 0) f.furia--;
      if (f.potenziato > 0 && --f.potenziato === 0 && f.forma) fineForma(f);
      if (anime && !f.esploso) f.ki = Math.min(100, f.ki + (f.forma > 0 && f.potenziato > 0 ? 0.12 : 0.04));
      if (f.piccolo > 0) f.piccolo--;
      f.scala += ((f.piccolo > 0 ? 0.55 : 1) - f.scala) * 0.15;
    }
    if (scossa > 0) scossa--;
  }

  // La faccina accanto al titolo perde il filo se i lottatori le arrivano vicino.
  let faccina = null, faccinaRiquadro = null;
  function aggiornaFaccina() {
    if (!faccina) {
      faccina = document.querySelector(".furbetto") || false;
    }
    if (!faccina || !faccina.getBoundingClientRect) return;
    const r = faccina.getBoundingClientRect();
    const margine = 70 * S;
    let vicino = false;
    for (const f of lottatori) {
      for (const n of ["testa", "collo", "bacino", "manoA", "manoD"]) {
        const pt = f.p[n];
        if (pt.x > r.left - margine && pt.x < r.right + margine && pt.y > r.top - margine && pt.y < r.bottom + margine) vicino = true;
      }
    }
    for (const t of telefoni) {
      if (t.x > r.left - margine && t.x < r.right + margine && t.y > r.top - margine && t.y < r.bottom + margine) vicino = true;
    }
    if (faccina.classList) faccina.classList[vicino ? "add" : "remove"]("stordito");
  }

  // --- La striscia delle notizie si rompe -------------------------------
  // Un lottatore (o un telefono) che si schianta sulla striscia la
  // danneggia: crepe che partono dal punto d'urto, e se il colpo è forte
  // un buco coi fili scoperti che sfavillano. Dopo una quarantina di
  // secondi i danni si «riparano» da soli: le notizie devono restare leggibili.
  const VITA_DANNO = 2000;
  function crepa(x0, y0, lun, ang) {
    const pt = [[x0, y0]];
    let x = x0, y = y0, a = ang;
    for (let i = 0; i < 5; i++) {
      a += caso(-0.7, 0.7);
      x += Math.cos(a) * lun / 5; y += Math.sin(a) * lun / 5;
      pt.push([x, y]);
    }
    return pt;
  }
  function danneggiaStriscia(x, forza) {
    if (!(pavimento < H - 4) || fermo) return;
    // Un danno nuovo al massimo ogni 5 secondi circa: la striscia deve
    // restare quasi sempre leggibile.
    for (const d of danni) if (d.eta < 420 || (Math.abs(d.x - x) < 26 * S && d.eta < 400)) return;
    const n = Math.round(3 + forza * 5);
    const crepe = [];
    for (let i = 0; i < n; i++) {
      crepe.push(crepa(0, 0, caso(14, 40 + forza * 40) * S, caso(0.15, Math.PI - 0.15)));
    }
    let buco = null;
    if (forza > 0.72 && danni.filter((d) => d.buco).length < 3) {
      const r = caso(9, 15) * S, pts = [];
      for (let i = 0; i < 9; i++) {
        const a = (i / 9) * Math.PI * 2, rr = r * caso(0.55, 1.15);
        pts.push([Math.cos(a) * rr * 1.3, Math.sin(a) * rr * 0.9]);
      }
      buco = pts;
    }
    danni.push({ x, eta: 0, crepe, buco, forza });
    if (danni.length > 5) danni.shift();
    scintille(x, pavimento + 4 * S, 12, "#ffe27a");
    schegge(x, pavimento + 2 * S, 8, "#ffffff");
    schegge(x, pavimento + 2 * S, 5, "#1f7a5a");
    scossa = Math.max(scossa, 6);
    const barra = mio.querySelector && mio.querySelector(".ultimora-barra");
    if (barra && barra.classList) {
      barra.classList.remove("ultimora-colpita"); void barra.offsetWidth;
      barra.classList.add("ultimora-colpita", "ultimora-guasta");
    }
    scrivi(buco ? "CRASH!" : "CRACK!", x, pavimento - 16 * S, true);
  }
  function aggiornaDanni() {
    for (const d of danniBordi) d.eta++;
    if (danniBordi.length && danniBordi[0].eta >= VITA_DANNO) danniBordi = danniBordi.filter((d) => d.eta < VITA_DANNO);
    for (const d of danni) {
      d.eta++;
      if (d.buco && d.eta % 22 === 0 && d.eta < VITA_DANNO - 700) scintille(d.x + caso(-8, 8) * S, pavimento + 14 * S, 3, "#8ff0ff");
      if (d.buco && d.eta % 40 === 0) polvere(d.x, pavimento + 8 * S, 1);
    }
    danni = danni.filter((d) => d.eta < VITA_DANNO);
    if (!danni.length) {
      const barra = mio.querySelector && mio.querySelector(".ultimora-barra");
      if (barra && barra.classList) barra.classList.remove("ultimora-guasta");
    }
  }
  // --- I bordi e il tetto della pagina si rompono -------------------------
  // Come la striscia: crepe che entrano nella pagina dal punto d'urto e, se
  // il colpo è forte, un buco da cui si vede il vuoto (nero, con le stelle).
  // Al massimo un danno nuovo ogni 5 s per lato; si riparano in ~33 s.
  function danneggiaBordo(lato, pos, forza) {
    if (fermo) return;
    for (const d of danniBordi) if (d.lato === lato && (d.eta < 300 || (Math.abs(d.pos - pos) < 30 * S && d.eta < 900))) return;
    const [a0, a1] = lato === "sinistra" ? [-Math.PI / 2 + 0.2, Math.PI / 2 - 0.2]
                   : lato === "destra" ? [Math.PI / 2 + 0.2, Math.PI * 1.5 - 0.2] : [0.15, Math.PI - 0.15];
    const crepe = [];
    for (let i = 0, n = Math.round(3 + forza * 5); i < n; i++) crepe.push(crepa(0, 0, caso(14, 40 + forza * 45) * S, caso(a0, a1)));
    let buco = null;
    if (forza > 0.6) {
      const r = caso(10, 18) * S;
      buco = [];
      for (let i = 0; i < 10; i++) { const a = (i / 10) * Math.PI * 2, rr = r * caso(0.6, 1.15); buco.push([Math.cos(a) * rr, Math.sin(a) * rr]); }
    }
    danniBordi.push({ lato, pos, eta: 0, crepe, buco, forza, stelle: [0, 1, 2, 3].map(() => [caso(-0.6, 0.6), caso(-0.6, 0.6)]) });
    if (danniBordi.length > 8) danniBordi.shift();
    const [x, y] = puntoBordo({ lato, pos });
    scintille(x, y, 10, "#ffe27a");
    for (let i = 0; i < 8 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "detrito", x, y, vx: (lato === "destra" ? -1 : lato === "sinistra" ? 1 : caso(-1, 1)) * caso(1, 4) * S,
                        vy: caso(-2, 2) * S, vita: 90, max: 90, rot: caso(0, 6), va: caso(-0.3, 0.3), lato: caso(1.4, 3) * S, colore: "#9a948a" });
    }
    scossa = Math.max(scossa, 6);
    scrivi(buco ? "CRASH!" : "CRACK!", Math.max(60, Math.min(W - 60, x)), Math.max(30, y + (lato === "tetto" ? 30 * S : 0)), true);
  }
  const puntoBordo = (d) => (d.lato === "sinistra" ? [0, d.pos] : d.lato === "destra" ? [W, d.pos] : [d.pos, 0]);
  function disegnaBordi() {
    for (const d of danniBordi) {
      const vita = Math.min(1, (VITA_DANNO - d.eta) / 600);
      if (vita <= 0) continue;
      const [x, y] = puntoBordo(d);
      ctx.save(); ctx.globalAlpha = vita; ctx.translate(x, y);
      if (d.buco) {
        ctx.beginPath(); d.buco.forEach(([bx, by], i) => (i ? ctx.lineTo(bx, by) : ctx.moveTo(bx, by))); ctx.closePath();
        ctx.fillStyle = "#0d0f14"; ctx.fill();
        ctx.lineWidth = 2 * S; ctx.strokeStyle = "#3a3a3a"; ctx.lineJoin = "round"; ctx.stroke();
        for (const [sx, sy] of d.stelle) tondo(sx * 14 * S, sy * 14 * S, 0.8 * S, "#ffffff");
      }
      ctx.lineCap = "round"; ctx.lineJoin = "round";
      for (const c of d.crepe) {
        ctx.beginPath(); c.forEach(([cx, cy], i) => (i ? ctx.lineTo(cx, cy) : ctx.moveTo(cx, cy)));
        ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2.4 * S; ctx.stroke();
        ctx.strokeStyle = "#141414"; ctx.lineWidth = 1.1 * S; ctx.stroke();
      }
      ctx.restore();
    }
  }

  function disegnaDanni() {
    if (!danni.length) return;
    ctx.save();
    ctx.beginPath(); ctx.rect(0, pavimento - 1, W, barraAlta + 2); ctx.clip();
    for (const d of danni) {
      const resta = VITA_DANNO - d.eta;
      const vita = Math.min(1, resta / 600);
      ctx.globalAlpha = Math.max(0, vita);
      const y0 = pavimento + 1.5 * S;
      if (d.buco) {
        const k = vita < 1 ? 0.4 + 0.6 * vita : 1;
        ctx.save(); ctx.translate(d.x, pavimento + barraAlta * 0.5); ctx.scale(k, k);
        ctx.beginPath(); d.buco.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath();
        ctx.fillStyle = sfondo; ctx.fill();
        ctx.lineWidth = 2 * S; ctx.strokeStyle = "#141414"; ctx.lineJoin = "round"; ctx.stroke();
        ctx.lineWidth = 1 * S; ctx.strokeStyle = "#ffcf3a";
        ctx.beginPath(); ctx.moveTo(-3 * S, -3 * S); ctx.lineTo(1 * S, 0); ctx.lineTo(-1 * S, 3 * S);
        ctx.moveTo(4 * S, -2 * S); ctx.lineTo(1 * S, 1 * S); ctx.stroke();
        ctx.restore();
      }
      ctx.lineCap = "round"; ctx.lineJoin = "round";
      for (const c of d.crepe) {
        ctx.beginPath();
        c.forEach(([x, y], i) => (i ? ctx.lineTo(d.x + x, y0 + y) : ctx.moveTo(d.x + x, y0 + y)));
        ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2.4 * S; ctx.stroke();
        ctx.strokeStyle = "#141414"; ctx.lineWidth = 1.1 * S; ctx.stroke();
      }
    }
    ctx.restore();
  }

  function passo() {
    passi++; tempo++;
    if (passi % 45 === 0) rileva();
    const [a, b] = lottatori;

    for (const [f, altro] of [[a, b], [b, a]]) {
      if (f.esploso) continue;
      if (f.tel && (f.ko > 0 || f.stordito || f.preso || f.dolore || f.tenuto)) lasciaCadere(f);
      if (f.arma && (f.ko > 0 || f.preso || f.tenuto)) lasciaArma(f);
      if (f.tiene && (f.ko > 0 || f.preso || f.tenuto)) molla(f);
      if (f.polv > 0) f.polv--;
      if (f.scendeApposta > 0) f.scendeApposta--;
      // Chi era sollevato a distanza cade se chi lo teneva smette (o viene colpito).
      if (f.tenuto && f.tenuto.tele !== undefined && ((f.tenuto.da.azione !== "telecinesi" && f.tenuto.da.azione !== "levita") || f.preso)) { f.tenuto = null; f.ko = Math.max(f.ko, 40); f.inVolo = true; }
      // Il ghiaccio si scioglie da solo, o va in pezzi se si viene presi.
      if (f.gelato > 0 && (f.preso || f.tenuto || --f.gelato === 0)) rompiGhiaccio(f, false);
      if (f.preso || f.tenuto) { f.forza = 0; f.jet = 0; f.paracadute = 0; continue; }
      aggiornaCratere(f);
      if (f.sfera && f.azione !== "sfera") { scintille(f.sfera.x, f.sfera.y, 14, COLORI_ANIME[f.tipo]); f.sfera = null; }
      if (f.ko > 0) {
        f.forza = f.cratere && !f.cratere.attesa ? 0.75 : 0;
        // Da lanciato, il conto alla rovescia parte solo quando si è fermato.
        const bc = f.p.bacino, v = Math.hypot(bc.x - bc.ox, bc.y - bc.oy);
        // «Fermo» è anche chi non si sposta più da mezzo secondo (02/10/2026): un
        // corpo incastrato, o tenuto in posa nel cratere, trema sul posto con una
        // velocità che non scende mai sotto la soglia, e restava a terra per sempre.
        if (f.inVolo) {
          const q = f.koDove;
          if (q && Math.hypot(bc.x - q.x, bc.y - q.y) < 5 * S) q.n++; else f.koDove = { x: bc.x, y: bc.y, n: 0 };
        } else f.koDove = null;
        if (!f.inVolo || v < 1.2 * S || (f.koDove && f.koDove.n > 30)) {
          if (--f.ko === 0) { f.rialzo = 50; f.inVolo = false; f.cx = f.p.bacino.x; f.koVero = false; f.koDove = null; }
        }
      } else if (f.rialzo > 0) { f.forza = 1 - f.rialzo / 50; f.rialzo--; }
      else if (f.stordito > 0) { f.forza = 0.22; f.stordito--; }
      else f.forza = 1;
      if (f.gelato > 0) f.forza = 0;
      if (f.dolore > 0) f.dolore--;
      if (f.botta > 0) f.botta--;

      if (f.ko > 0 || f.preso) { f.jet = 0; f.caos = 0; f.scatto = 0; }
      if (!(f.jet > 0)) { f.volo = false; f.scatto = 0; }
      if (anime) aggiornaInseguimento(f, altro);
      if (f.caos > 0) f.forza = Math.min(f.forza, 0.35);
      if (!f.scalata) {
        const [y, chi] = appoggio(f);
        f.base = y; f.supporto = chi;
      }
      // In volo la «base» è il corpo stesso: il busto resta dritto da solo.
      if (f.jet > 0) { f.base = f.p.bacino.y + 30 * S; f.supporto = null; }
      pensa(f, altro);
      // La presa sull'avversario: lo si tiene finché dura la mossa, poi via.
      if (f.azione === "presa") aggiornaPresa(f, altro);
      else if (f.tiene) scaglia(f);
      if (f.azione === "balla") {
        if (f.ballo === "giravolta" && f.t % 10 === 0) f.dir = -f.dir;
        if (f.ballo === "dab" && f.t % 42 === 0 && f.t) f.dir = -f.dir;
        if (f.ballo === "moonwalk") f.cx -= f.dir * 0.5 * S;
        if (f.ballo === "saltelli" && f.t % 28 === 14) for (const n in f.p) f.p[n].oy = f.p[n].y + verso * 3.2 * S;
        if (f.t % 20 === 1) nota(f);
      }
      // Il paracadute: solo scendendo apposta da un elemento, mai da lanciato.
      {
        const piede = Math.max(f.p.piedeA.y, f.p.piedeD.y);
        if (!f.paracadute && verso > 0 && f.scendeApposta > 0 && !f.inVolo && !f.ko && !f.jet && !f.scalata &&
            f.base - piede > 45 * S && f.p.bacino.y - f.p.bacino.oy > 0) {
          f.paracadute = 1; f.scendeApposta = 0;
        } else if (f.paracadute && (f.base - piede < 4 * S || f.ko || f.inVolo || f.jet > 0)) {
          f.paracadute = 0;
          if (f.base - piede < 4 * S) polvere(f.p.bacino.x, f.base - 1, 3);
        }
        f.para = f.paracadute ? Math.min(1, f.para + 0.09) : Math.max(0, f.para - 0.1);
      }

      if (f.scalata) {
        const sc = f.scalata;
        f.t++;
        sc.y -= 0.8 * S;
        f.base = sc.y;
        if (sc.y <= sc.o.t + 2 * S) {
          // In cima: una spinta in su e verso l'interno, e si è sopra.
          const s = sc.lato;
          f.cx = (s < 0 ? sc.o.l : sc.o.r) - s * 14 * S;
          for (const n in f.p) { f.p[n].oy = f.p[n].y + 4.5 * S; f.p[n].ox = f.p[n].x + s * 2.2 * S; }
          f.scalata = null; f.base = sc.o.t; f.supporto = sc.o; f.pensa = 8;
        }
      } else if (f.jet > 0) {
        f.jet--;
        if (f.volo && f.scatto > 0) aggiornaScatto(f);
        else {
          const v = f.volo ? 4.5 : 2.2;
          f.cx += Math.max(-v * S, Math.min(v * S, (f.meta - f.cx) * (f.volo ? 0.12 : 0.08)));
        }
        f.passo += 0.12;
      } else if (f.azione === "avanza" && acquazzone && !f.supporto && Math.random() < 0.0025) {
        // Con la pioggia, sulla striscia bagnata si scivola.
        for (const n of ["piedeA", "piedeD", "ginocchioA", "ginocchioD"]) f.p[n].ox -= f.dir * 5 * S;
        for (const n of ["testa", "collo"]) f.p[n].ox += f.dir * 3 * S;
        f.ko = Math.max(f.ko, 45); f.inVolo = true; f.azione = null;
        scrivi("SCIVOLONE!", f.p.bacino.x, f.p.bacino.y - 30 * S, false);
      } else if (f.azione === "avanza") {
        // Camminando si passa davanti agli elementi: ci si arrampica solo per
        // raggiungere l'avversario che sta più in alto (lo decide `pensa`).
        const lato = Math.sign(f.meta - f.cx) || f.dir;
        f.dir = lato;
        f.cx += lato * (Math.abs(f.meta - f.cx) > 220 * S ? 1.6 : 0.95) * S;
        f.passo += 0.28;
      } else if (f.azione === "indietro") { f.cx -= f.dir * 1.0 * S; f.passo += 0.3; }
      else f.passo += 0.08;

      if (!f.scalata) {
        f.cx += (f.p.bacino.x - f.cx) * (f.forza < 1 ? 0.5 : 0.06);
        f.cx = Math.max(20 * S, Math.min(W - 20 * S, f.cx));
      }
    }
    // Non passarsi attraverso, se sono allo stesso livello.
    if (!a.ko && !b.ko && !a.preso && !b.preso && !a.tenuto && !b.tenuto && Math.abs(a.base - b.base) < 10 * S) {
      const d = b.cx - a.cx, minimo = 26 * S;
      if (Math.abs(d) < minimo) {
        const s = d >= 0 ? 1 : -1, sposta = (minimo - Math.abs(d)) / 2;
        a.cx -= s * sposta; b.cx += s * sposta;
      }
    }

    for (const f of lottatori) {
      if (f.esploso) { aggiornaEsplosione(f); continue; }
      if (f.fuori) { volaFuori(f); continue; }
      // Il punto tenuto fermo: dal puntatore o dalle mani dell'avversario.
      const fisso = f.preso || (f.tenuto ? "collo" : null);
      // Muscoli.
      if (f.forza > 0) {
        const piede = verso > 0 ? Math.max(f.p.piedeA.y, f.p.piedeD.y) : Math.min(f.p.piedeA.y, f.p.piedeD.y);
        const inAria = !f.scalata && (f.base - piede) * verso > 30 * S;
        let q;
        if (f.scalata) q = posaScalata(f);
        else if (f.cratere && !f.cratere.attesa && f.ko > 0) q = posaCratere(f);
        else if (inAria) {
          // Cadendo da un bordo i muscoli tengono solo la forma del corpo:
          // la discesa la fa la gravità, non un muscolo che tira giù.
          const vera = f.base; f.base = f.p.bacino.y + verso * 30 * S; q = posa(f); f.base = vera;
        } else q = posa(f);
        const scatto = f.azione && COLPI[f.azione] ? 0.55 : 0.3;
        const intensita = f.scalata || (f.cratere && !f.cratere.attesa && f.ko > 0) ? 1.3 : (inAria ? 0.35 : 1);
        for (const nome in q) {
          const pt = f.p[nome], [tx, ty] = q[nome];
          const k = TIRO[nome] * f.forza * intensita *
            (COLPI[f.azione] && (nome === COLPI[f.azione][0]) ? 1.6 : 1);
          const mx = (tx - pt.x) * k, my = (ty - pt.y) * k;
          pt.x += mx; pt.y += my;
          pt.ox += mx * (1 - scatto); pt.oy += my * (1 - scatto);
        }
      }
      // LE GAMBE NON SI INCROCIANO (02/10/2026). «A» è la gamba davanti: se
      // voltandosi (o rialzandosi) finisce dietro l'altra, le due si scambiano
      // il nome invece di passarsi attraverso. Prima restavano incrociate
      // per quasi metà del tempo.
      if (!f.ko && !f.preso && !f.tenuto && !f.scalata && !f.gelato && f.azione !== "balla" && !(f.staccati.gA || f.staccati.gD) &&
          (f.p.piedeA.x - f.p.piedeD.x) * f.dir < -2 * S) scambiaGambe(f);
      // Tenuto in mano: il punto preso segue il puntatore, il resto penzola.
      if (fisso) {
        const pt = f.p[fisso], tx = f.preso ? presa.x : f.tenuto.x, ty = f.preso ? presa.y : f.tenuto.y;
        pt.ox = pt.x; pt.oy = pt.y;
        pt.x += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, tx - pt.x));
        pt.y += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, ty - pt.y));
      }
      // In volo si passa attraverso il testo e i campi (come un oggetto
      // sollevato): urtandoli punto per punto il corpo si deformava. Restano
      // solidi il pavimento (la striscia) e i bordi della finestra.
      if (f.jet > 0 && !f.preso) { f.fantasma = true; applicaSpinta(f); } else f.fiamma = 0;
      // Verlet.
      for (const n in f.p) {
        const pt = f.p[n];
        if (fisso === n) continue;
        let vx = (pt.x - pt.ox) * 0.985, vy = (pt.y - pt.oy) * 0.985;
        const v = Math.hypot(vx, vy), lim = VELOCITA_MAX * S;
        if (v > lim) { vx *= lim / v; vy *= lim / v; }
        // Col paracadute si scende piano, ondeggiando un po'.
        if (f.para > 0.3) { vy = Math.min(vy, 1.5 * S); vx = vx * 0.96 + Math.sin(passi * 0.05) * 0.05 * S; }
        pt.ox = pt.x; pt.oy = pt.y;
        pt.x += vx; pt.y += vy + GRAVITA * S * moltG * verso;
      }
      // Vincoli: aste, elementi della pagina, pavimento, bordi.
      let urto = 0;
      const piattaforma = !(f.ko > 0 || f.inVolo) && verso > 0;
      for (let giro = 0; giro < 5; giro++) {
        for (const [p1, p2, L] of f.aste) {
          const dx = p2.x - p1.x, dy = p2.y - p1.y;
          const d = Math.hypot(dx, dy) || 0.001;
          const c = (d - L) / d * 0.5;
          const fermo1 = fisso && f.p[fisso] === p1, fermo2 = fisso && f.p[fisso] === p2;
          if (fermo1) { p2.x -= dx * c * 2; p2.y -= dy * c * 2; }
          else if (fermo2) { p1.x += dx * c * 2; p1.y += dy * c * 2; }
          else { p1.x += dx * c; p1.y += dy * c; p2.x -= dx * c; p2.y -= dy * c; }
        }
        for (const n in f.p) {
          const pt = f.p[n];
          if (fisso === n) continue;
          if (!f.fantasma) urto = Math.max(urto, urta(f, pt, piattaforma));
          if (pt.y > pavimento - pt.r) {
            const caduta = pt.y - pt.oy;
            if (caduta > 11.5 * S) danneggiaStriscia(pt.x, Math.min(1, caduta / (VELOCITA_MAX * S)));
            urto = Math.max(urto, Math.hypot(pt.x - pt.ox, pt.y - pt.oy));
            pt.y = pavimento - pt.r;
            if (pt.oy < pt.y) pt.oy = pt.y;
            pt.ox += (pt.x - pt.ox) * (acquazzone ? 0.05 : 0.3);
          }
          if (pt.y < pt.r) {
            // Il tetto: si rompe se ci si sbatte forte, e a gravità rovesciata è il pavimento.
            if (pt.oy - pt.y > 9 * S) danneggiaBordo("tetto", pt.x, Math.min(1, (pt.oy - pt.y) / (VELOCITA_MAX * S)));
            urto = Math.max(urto, Math.hypot(pt.x - pt.ox, pt.y - pt.oy));
            pt.y = pt.r; pt.oy = pt.y;
            if (verso < 0) pt.ox += (pt.x - pt.ox) * 0.3;
          }
          if (pt.x < pt.r + 2) {
            if (pt.ox - pt.x > 8.5 * S) danneggiaBordo("sinistra", pt.y, Math.min(1, (pt.ox - pt.x) / (VELOCITA_MAX * S)));
            pt.x = pt.r + 2; pt.ox = pt.x + (pt.x - pt.ox) * 0.4;
          }
          if (pt.x > W - pt.r - 2) {
            if (pt.x - pt.ox > 8.5 * S) danneggiaBordo("destra", pt.y, Math.min(1, (pt.x - pt.ox) / (VELOCITA_MAX * S)));
            pt.x = W - pt.r - 2; pt.ox = pt.x + (pt.x - pt.ox) * 0.4;
          }
        }
      }
      // Nel ghiaccio il corpo resta rigido: ogni punto dov'era rispetto al piede d'appoggio.
      if (f.gelato > 0 && f.ghiaccio) {
        const anc = f.p[f.ghiaccio.anc], vx = anc.x - anc.ox, vy = anc.y - anc.oy;
        for (const n in f.p) { const pt = f.p[n], o = f.ghiaccio.off[n]; pt.x = anc.x + o.x; pt.y = anc.y + o.y; pt.ox = pt.x - vx; pt.oy = pt.y - vy; }
      }
      // Lasciato cadere dalla levitazione: la botta a terra conta come un colpo del mago.
      if (f.caduta && (urto > 7 * S || !f.inVolo)) {
        const mago = f.caduta; f.caduta = null;
        if (urto > 7 * S && mago.p && !mago.esploso && !f.esploso) colpisci(mago, f, 4.5, f.p.bacino.x, f.p.bacino.y, "SBAM!");
      }
      if (f.fantasma && !f.preso && !f.tenuto && !dentroQualcosa(f)) f.fantasma = false;
      // Uno schianto dopo un lancio si sente.
      if (urto > 6 * S && !f.polv) { polvere(f.p.piedeA.x, f.base - 1, urto > 11 * S ? 6 : 3); f.polv = 14; }
      if (f.inVolo && urto > 9 * S && !f.botta) {
        scrivi(urto > 15 * S ? "SPLAT!" : "BONK!", f.p.bacino.x, f.p.bacino.y - 20 * S, false);
        f.botta = 30;
      }
    }
    if (lame()) controllaLame(a, b);
    controllaColpo(a, b); controllaColpo(b, a);
    colpoDaMano(a, b); colpoDaMano(b, a);
    aggiornaLame(); aggiornaFulmini();
    aggiornaTelefoni(); aggiornaCreature(); aggiornaNubi(); aggiornaFinale(); aggiornaProiettili(); aggiornaParticelle(); aggiornaEventi(); aggiornaDanni();
    aggiornaArti(); aggiornaMeteo(); aggiornaOnde(); aggiornaVite();
    if (anime) controllaScontro();
    for (const sc of scie) sc.vita--;
    if (scie.length && scie[0].vita <= 0) scie = scie.filter((sc) => sc.vita > 0);
    if (anime) {
      for (const f of lottatori) {
        const altro = lottatori.find((l) => l !== f);
        if (altro && altro.onda && !altro.onda.colpito && f.ki >= 15 && !f.ko && Math.random() < 0.02) teletrasporta(f, altro);
      }
    }
    if (passi % 10 === 0) aggiornaFaccina();
    for (const s of scritte) { s.vita--; s.y -= 0.35 * S; }
    scritte = scritte.filter((s) => s.vita > 0);
  }

  // --- Lo scorrimento della pagina -------------------------------------
  // Gli elementi si spostano nella finestra: chi ci sta sopra si sposta
  // con loro, chi sta sulla striscia (che è fissa) resta dov'è.
  let ultimoScroll = window.scrollY || 0;
  window.addEventListener("scroll", () => {
    const ora = window.scrollY || 0, dy = ora - ultimoScroll;
    ultimoScroll = ora;
    if (!dy) return;
    for (const f of lottatori) {
      if (f.preso || f.esploso || !(f.supporto || f.scalata)) continue;
      for (const n in f.p) { f.p[n].y -= dy; f.p[n].oy -= dy; }
      if (f.scalata) f.scalata.y -= dy;
      f.base -= dy;
    }
    if (!fermo) rileva();
  }, { passive: true });

  // --- Il disegno ------------------------------------------------------
  function linea(p1, p2, spessore, colore) {
    ctx.strokeStyle = colore; ctx.lineWidth = spessore; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
  }
  function arto(a, b, c, spessore, colore) {
    ctx.strokeStyle = colore; ctx.lineWidth = spessore; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(c.x, c.y); ctx.stroke();
  }
  function tondo(x, y, r, colore) {
    ctx.fillStyle = colore; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }
  function rettangoloTondo(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
  }
  function occhi(f, x, y, distanza, raggio, colore) {
    ctx.strokeStyle = colore; ctx.fillStyle = colore; ctx.lineWidth = 1.3 * S; ctx.lineCap = "round";
    for (const lato of [-1, 1]) {
      const ex = x + lato * distanza + f.dir * 1.2 * S;
      if (f.ko || f.rialzo > 30) {
        ctx.beginPath();
        ctx.moveTo(ex - raggio, y - raggio); ctx.lineTo(ex + raggio, y + raggio);
        ctx.moveTo(ex + raggio, y - raggio); ctx.lineTo(ex - raggio, y + raggio); ctx.stroke();
      } else if (f.dolore) {
        ctx.beginPath(); ctx.moveTo(ex - raggio, y); ctx.lineTo(ex + raggio, y); ctx.stroke();
      } else {
        ctx.beginPath(); ctx.arc(ex, y, raggio, 0, Math.PI * 2); ctx.fill();
      }
    }
  }

  // IL ROBOT: un personaggio originale (scatola verde con visiera), con colori
  // e costume a caso a ogni caricamento, espressioni che cambiano e
  // un'antenna che oscilla (01/10/2026).
  function sfumatura(x, y, r, chiaro, scuro) {
    const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.4, r * 0.1, x, y, r * 1.2);
    g.addColorStop(0, chiaro); g.addColorStop(1, scuro);
    return g;
  }
  function mix(c1, c2, k) {
    const n = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
    const A = n(c1), B = n(c2);
    return "rgb(" + A.map((v, i) => Math.round(v + (B[i] - v) * k)).join(",") + ")";
  }
  function stella(x, y, r, colore) {
    ctx.fillStyle = colore; ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const raggio = i % 2 ? r * 0.45 : r, ang = -Math.PI / 2 + (i * Math.PI) / 5;
      ctx.lineTo(x + Math.cos(ang) * raggio, y + Math.sin(ang) * raggio);
    }
    ctx.closePath(); ctx.fill();
  }

  // IL GUANTONE DA PUGILE, al posto della manina: il polsino bianco, il
  // corpo del guanto lungo l'avambraccio, il pollice e un riflesso.
  function guanto(gomito, mano, colore, r) {
    const ang = Math.atan2(mano.y - gomito.y, mano.x - gomito.x);
    ctx.save(); ctx.translate(mano.x, mano.y); ctx.rotate(ang);
    ctx.fillStyle = "#f4f4f4"; ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S;
    rettangoloTondo(-r * 1.9, -r * 0.7, r * 1.1, r * 1.4, r * 0.3); ctx.fill(); ctx.stroke();
    ctx.fillStyle = colore;
    ctx.beginPath(); ctx.ellipse(r * 0.15, 0, r * 1.25, r * 1.05, 0, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 1.3 * S; ctx.stroke();
    ctx.beginPath(); ctx.ellipse(r * 0.05, r * 0.85, r * 0.55, r * 0.38, -0.3, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 1 * S; ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 1 * S; ctx.lineCap = "round";
    ctx.beginPath(); ctx.arc(r * 0.2, 0, r * 0.75, -2.2, -1.2); ctx.stroke();
    ctx.restore();
  }

  // IL JETPACK: due bombole sul dorso, con gli ugelli e, quando spinge, la fiamma.
  function zaino(f, indietro) {
    const p = f.p, tx = p.bacino.x - p.collo.x, ty = p.bacino.y - p.collo.y, tl = Math.hypot(tx, ty) || 1;
    const ux = tx / tl, uy = ty / tl;
    let nx = -uy, ny = ux;
    if (nx * f.dir > 0) { nx = -nx; ny = -ny; }          // verso la schiena
    const cx = p.collo.x + tx * 0.5 + nx * indietro, cy = p.collo.y + ty * 0.5 + ny * indietro;
    const ang = Math.atan2(ty, tx) - Math.PI / 2;
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(ang);
    for (const [dx, col] of [[-2.6, "#7d8696"], [2.6, "#b3bbc9"]]) {
      ctx.fillStyle = col; ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S;
      rettangoloTondo((dx - 2.6) * S, -9 * S, 5.2 * S, 18 * S, 2.4 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#e8741a"; ctx.fillRect((dx - 2.6) * S, -3 * S, 5.2 * S, 2.2 * S);
      ctx.fillStyle = "#2b2f3a"; ctx.beginPath();
      ctx.moveTo((dx - 2.2) * S, 9 * S); ctx.lineTo((dx + 2.2) * S, 9 * S);
      ctx.lineTo((dx + 3.2) * S, 12 * S); ctx.lineTo((dx - 3.2) * S, 12 * S); ctx.closePath(); ctx.fill();
      if (f.fiamma > 0.05) {
        const lung = (6 + 14 * Math.min(1.4, f.fiamma)) * S * (0.8 + 0.4 * Math.random());
        const g = ctx.createLinearGradient(0, 12 * S, 0, 12 * S + lung);
        g.addColorStop(0, "#fff7b0"); g.addColorStop(0.45, "#ffb62e"); g.addColorStop(1, "rgba(255,90,20,0)");
        ctx.fillStyle = g; ctx.beginPath();
        ctx.moveTo((dx - 2.6) * S, 12 * S); ctx.lineTo((dx + 2.6) * S, 12 * S); ctx.lineTo(dx * S, 12 * S + lung);
        ctx.closePath(); ctx.fill();
      }
    }
    ctx.restore();
  }

  function mantello(f, p, colore) {
    const dietro = -f.dir;
    const lag = Math.max(-9 * S, Math.min(9 * S, (p.collo.ox - p.collo.x) * 7));
    const onda = Math.sin(f.passo * 1.6) * 2.2 * S;
    const A = { x: p.collo.x + dietro * 2 * S, y: p.collo.y + 1 * S };
    const B = { x: p.bacino.x + dietro * 3 * S, y: p.bacino.y - 3 * S };
    const T1 = { x: A.x + dietro * 17 * S + lag, y: A.y + 24 * S + onda };
    const T2 = { x: B.x + dietro * 11 * S + lag * 0.7, y: B.y + 16 * S - onda };
    ctx.fillStyle = colore; ctx.beginPath();
    ctx.moveTo(A.x, A.y);
    ctx.quadraticCurveTo(A.x + dietro * 15 * S + lag * 0.5, A.y + 10 * S, T1.x, T1.y);
    ctx.quadraticCurveTo((T1.x + T2.x) / 2, Math.max(T1.y, T2.y) + 3 * S, T2.x, T2.y);
    ctx.lineTo(B.x, B.y); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0,.25)"; ctx.lineWidth = 1 * S; ctx.stroke();
  }

  function costumeTesta(f, scuro) {
    // Si disegna nel sistema di riferimento della testa: l'origine è il
    // centro, il «su» è -y, la scatola va da -8.5 a 8.5 in larghezza.
    switch (costume) {
      case "ninja":
        ctx.fillStyle = "#1b1b24"; rettangoloTondo(-9 * S, -7.5 * S, 18 * S, 5.2 * S, 2 * S); ctx.fill();
        ctx.fillStyle = "#e23b2e"; ctx.fillRect(-9 * S, -4.3 * S, 18 * S, 1.3 * S);
        ctx.strokeStyle = "#1b1b24"; ctx.lineWidth = 2.2 * S; ctx.lineCap = "round";
        for (const k of [0, 1]) {
          ctx.beginPath(); ctx.moveTo(-f.dir * 8 * S, -5.5 * S);
          ctx.quadraticCurveTo(-f.dir * (13 + 3 * Math.sin(f.passo * 2 + k)) * S, (-3 + 4 * k) * S,
                               -f.dir * (18 + 2 * Math.sin(f.passo * 2.5 + k)) * S, (-1 + 7 * k) * S);
          ctx.stroke();
        }
        break;
      case "cuoco":
        ctx.fillStyle = "#fbfbfb"; ctx.strokeStyle = "#c9c9c9"; ctx.lineWidth = 1 * S;
        rettangoloTondo(-6.5 * S, -13 * S, 13 * S, 7 * S, 1.5 * S); ctx.fill(); ctx.stroke();
        for (const [cx, cy, r] of [[-5.5, -15, 4.4], [0, -17.5, 5.2], [5.5, -15, 4.4]]) {
          ctx.beginPath(); ctx.arc(cx * S, cy * S, r * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        }
        ctx.fillStyle = "#fbfbfb"; ctx.fillRect(-6 * S, -13.5 * S, 12 * S, 4 * S);
        break;
      case "mago":
        ctx.fillStyle = "#4b2f8f";
        ctx.beginPath(); ctx.moveTo(-8 * S, -7 * S); ctx.lineTo(f.dir * 2 * S, -24 * S); ctx.lineTo(8 * S, -7 * S); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.ellipse(0, -7 * S, 12 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill();
        stella(-2 * S, -13 * S, 2 * S, "#ffd84a"); stella(3 * S, -9.5 * S, 1.4 * S, "#ffd84a");
        break;
      case "pirata":
        ctx.fillStyle = "#c8332a"; rettangoloTondo(-9 * S, -8 * S, 18 * S, 4.6 * S, 2 * S); ctx.fill();
        tondo(-3 * S, -5.8 * S, 0.8 * S, "#fff"); tondo(2 * S, -6.2 * S, 0.8 * S, "#fff"); tondo(6 * S, -5.6 * S, 0.8 * S, "#fff");
        ctx.strokeStyle = "#c8332a"; ctx.lineWidth = 2.4 * S; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(-f.dir * 8 * S, -6 * S);
        ctx.quadraticCurveTo(-f.dir * 13 * S, (-3 + 2 * Math.sin(f.passo * 2)) * S, -f.dir * 16 * S, (1 + 3 * Math.sin(f.passo * 2.4)) * S); ctx.stroke();
        ctx.fillStyle = "#0a0a0a"; ctx.beginPath(); ctx.ellipse(f.dir * 2.8 * S, -0.3 * S, 3.6 * S, 3.1 * S, 0, 0, Math.PI * 2); ctx.fill();
        break;
      case "astronauta":
        ctx.fillStyle = "rgba(190,225,255,.22)"; ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1.6 * S;
        ctx.beginPath(); ctx.arc(0, -1 * S, 12.5 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 1.4 * S;
        ctx.beginPath(); ctx.arc(0, -1 * S, 9.5 * S, Math.PI * 1.15, Math.PI * 1.45); ctx.stroke();
        ctx.fillStyle = "#d9dde6"; ctx.fillRect(-6 * S, 10 * S, 12 * S, 2.4 * S);
        break;
      case "eroe":
        ctx.save(); ctx.globalAlpha = 0.45;
        ctx.fillStyle = "#14141c"; rettangoloTondo(-9.4 * S, -3.6 * S, 18.8 * S, 6.4 * S, 3 * S); ctx.fill();
        ctx.restore();
        break;
    }
  }

  function disegnaRobot(f) {
    const p = f.p, T = tavolozza || ["#2fae74", "#1c6f4a", "#7dffd2", "#154d34"];
    const verde = T[0], scuro = T[1], luce = T[2], mani = T[3];
    const chiaro = mix(verde, "#ffffff", 0.35);
    if (f.furia > 0) {
      const g = ctx.createRadialGradient(p.bacino.x, p.bacino.y - 14 * S, 4 * S, p.bacino.x, p.bacino.y - 14 * S, 38 * S);
      g.addColorStop(0, "rgba(255,70,30,.45)"); g.addColorStop(1, "rgba(255,70,30,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.bacino.x, p.bacino.y - 14 * S, 38 * S, 0, Math.PI * 2); ctx.fill();
    }
    if (costume === "eroe") mantello(f, p, "#e8941c");
    zaino(f, 10.5 * S);
    const st = f.staccati || {}, [ginA, ginD] = ginocchia(f);
    // Arto lontano e gamba lontana.
    if (!st.gD) { arto(p.bacino, ginD, p.piedeD, 5 * S, scuro); tondo(ginD.x, ginD.y, 2.8 * S, mani); }
    if (!st.D) {
      arto(p.collo, p.gomitoD, p.manoD, 4.4 * S, scuro);
      tondo(p.gomitoD.x, p.gomitoD.y, 2.4 * S, mani);
      guanto(p.gomitoD, p.manoD, "#b92b22", 3.9 * S);
    }
    // Busto.
    const ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2;
    const lung = Math.hypot(p.bacino.x - p.collo.x, p.bacino.y - p.collo.y);
    ctx.save();
    ctx.translate((p.collo.x + p.bacino.x) / 2, (p.collo.y + p.bacino.y) / 2); ctx.rotate(ang);
    ctx.fillStyle = sfumatura(0, 0, lung, chiaro, verde);
    rettangoloTondo(-8.5 * S, -lung / 2 - 3 * S, 17 * S, lung + 7 * S, 4 * S); ctx.fill();
    ctx.strokeStyle = scuro; ctx.lineWidth = 1.1 * S; ctx.stroke();
    ctx.fillStyle = scuro; rettangoloTondo(-5.2 * S, -lung / 2 + 2.5 * S, 10.4 * S, 7 * S, 1.8 * S); ctx.fill();
    const lampeggia = Math.floor(f.passo * 1.2) % 3;
    for (let i = 0; i < 3; i++) {
      tondo((-3 + 3 * i) * S, -lung / 2 + 6 * S, 1.2 * S,
            f.ko ? "#555" : (i === lampeggia ? "#fff6a8" : ["#ffcf3a", "#ff6b4a", luce][i]));
    }
    ctx.fillStyle = scuro; ctx.fillRect(-8.5 * S, lung / 2 - 4.5 * S, 17 * S, 2 * S);
    tondo(0, lung / 2 - 3.5 * S, 1.6 * S, "#ffcf3a");
    if (costume === "eroe") stella(0, -lung / 2 + 14 * S, 2.6 * S, "#ffe27a");
    disegnaSegni(f, "busto");
    ctx.restore();
    // Gamba e braccio vicini.
    if (!st.gA) { arto(p.bacino, ginA, p.piedeA, 5 * S, verde); tondo(ginA.x, ginA.y, 2.8 * S, scuro); }
    for (const piede of [p.piedeD, p.piedeA]) {
      if ((piede === p.piedeD && st.gD) || (piede === p.piedeA && st.gA)) continue;
      ctx.fillStyle = mani; rettangoloTondo(piede.x - 4.2 * S, piede.y - 2.6 * S, 8.4 * S, 4.8 * S, 1.8 * S); ctx.fill();
      ctx.fillStyle = scuro; ctx.fillRect(piede.x - 4 * S + (f.dir > 0 ? 0 : 6.2 * S), piede.y + 1.1 * S, 1.8 * S, 1.2 * S);
    }
    // Testa, con antenna a molla.
    const angT = Math.atan2(p.testa.y - p.collo.y, p.testa.x - p.collo.x) + Math.PI / 2;
    ctx.save(); ctx.translate(p.testa.x, p.testa.y); ctx.rotate(angT);
    const hatAlto = costume === "cuoco" || costume === "mago" || natale;
    if (!hatAlto && costume !== "astronauta" && !(f.staccati && f.staccati.P)) {
      const oscilla = Math.max(-5 * S, Math.min(5 * S, (p.testa.ox - p.testa.x) * 1.4)) + Math.sin(f.passo * 1.7) * 0.8 * S;
      ctx.strokeStyle = scuro; ctx.lineWidth = 1.4 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(0, -7 * S); ctx.quadraticCurveTo(oscilla * 0.4, -10 * S, oscilla, -13 * S); ctx.stroke();
      tondo(oscilla, -13.6 * S, 2.1 * S, (Math.floor(f.passo * 2) % 2 && !f.ko) ? "#ff4d3a" : "#ffcf3a");
    }
    ctx.fillStyle = sfumatura(0, -2 * S, 10 * S, chiaro, verde); rettangoloTondo(-8.5 * S, -7.5 * S, 17 * S, 15 * S, 4 * S); ctx.fill();
    ctx.strokeStyle = scuro; ctx.lineWidth = 1.1 * S; ctx.stroke();
    ctx.fillStyle = "#0f2a1f"; rettangoloTondo(-6.8 * S, -3.8 * S, 13.6 * S, 7 * S, 2.6 * S); ctx.fill();
    // Occhi: cambiano con quello che succede.
    const attacca = f.azione === "pugno" || f.azione === "diretto" || f.azione === "montante" ||
                    f.azione === "calcio" || f.azione === "lancia" || f.azione === "spara" ||
                    !!TAGLI[f.azione] || f.azione === "scattoLama" || f.azione === "pressa" || f.azione === "presa";
    const festa = f.azione === "esulta" || f.azione === "provoca" || f.azione === "balla";
    const ey = -0.3 * S, ex = f.dir * 0.8 * S;
    ctx.lineCap = "round";
    if (f.ko || f.rialzo > 30) {
      occhi(f, 0, ey, 2.8 * S, 1.4 * S, luce);
    } else if (f.dolore || f.stordito) {
      ctx.strokeStyle = luce; ctx.lineWidth = 1.4 * S; ctx.beginPath();
      ctx.moveTo(-4.2 * S, ey - 1.4 * S); ctx.lineTo(-1.6 * S, ey + 1.4 * S);
      ctx.moveTo(-1.6 * S, ey - 1.4 * S); ctx.lineTo(-4.2 * S, ey + 1.4 * S);
      ctx.stroke(); tondo(2.8 * S, ey, 1.9 * S, luce);
    } else if (festa) {
      ctx.strokeStyle = luce; ctx.lineWidth = 1.5 * S;
      for (const lato of [-1, 1]) { ctx.beginPath(); ctx.arc(lato * 2.9 * S + ex, ey + 1 * S, 1.7 * S, Math.PI * 1.05, Math.PI * 1.95); ctx.stroke(); }
    } else if (f.furia > 0 || attacca) {
      const col = f.furia > 0 ? "#ff6a4a" : luce;
      ctx.strokeStyle = col; ctx.lineWidth = 1.5 * S;
      for (const lato of [-1, 1]) {
        const x0 = lato * 2.9 * S + ex;
        tondo(x0, ey + 0.4 * S, 1.3 * S, col);
        ctx.beginPath(); ctx.moveTo(x0 - 2 * S, ey - (lato === f.dir ? 3 : 1.8) * S); ctx.lineTo(x0 + 2 * S, ey - (lato === f.dir ? 1.8 : 3) * S); ctx.stroke();
      }
    } else {
      const batte = Math.floor(passi / 3) % 90 === 0 ? 0.35 : 1;
      ctx.fillStyle = luce;
      for (const lato of [-1, 1]) { ctx.beginPath(); ctx.ellipse(lato * 2.9 * S + ex, ey, 1.4 * S, 1.4 * S * batte, 0, 0, Math.PI * 2); ctx.fill(); }
    }
    disegnaSegni(f, "testa");
    if (natale) cappellino(0, -7 * S, 9 * S, f.dir); else costumeTesta(f, scuro);
    const tg = temaGravita();
    if ((tg === "luna" || tg === "spazio") && costume !== "astronauta") { ctx.save(); ctx.translate(0, -1 * S); casco(12.5 * S); ctx.restore(); }
    ctx.restore();
    if (!st.A) {
      arto(p.collo, p.gomitoA, p.manoA, 4.4 * S, verde);
      tondo(p.gomitoA.x, p.gomitoA.y, 2.4 * S, scuro);
      guanto(p.gomitoA, p.manoA, "#e03a2f", 4.2 * S);
      if (f.palla) tondo(p.manoA.x, p.manoA.y - 3 * S, 3 * S, "#ffffff");
    }
  }

  // LA MELA: polpa bianca dentro, contorni neri, occhi neri
  // (01/10/2026, su richiesta). Un frutto intero col picciolo e la foglia.
  // La bocca della mela cambia con quello che succede: serena a riposo,
  // aperta quando colpisce, storta quando prende un colpo, lingua fuori da K.O.
  function bocca(f, R) {
    const x = f.dir * 0.1 * R, y = 0.4 * R, w = 0.3 * R;
    ctx.strokeStyle = "#111"; ctx.fillStyle = "#111"; ctx.lineWidth = 1.5 * S; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath();
    if (f.ko || f.rialzo > 30) {
      ctx.moveTo(x - w * 0.8, y); ctx.lineTo(x + w * 0.8, y); ctx.stroke();
      ctx.fillStyle = "#ff7a8a"; ctx.beginPath();
      ctx.ellipse(x + f.dir * w * 0.3, y + 0.14 * R, 0.12 * R, 0.16 * R, 0, 0, Math.PI * 2); ctx.fill();
      ctx.lineWidth = 1 * S; ctx.stroke();
    } else if (f.dolore || f.stordito) {
      const n = 6;
      for (let i = 0; i <= n; i++) {
        const px = x - w + (2 * w * i) / n, py = y + (i % 2 ? -0.06 : 0.06) * R;
        if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
      }
      ctx.stroke();
    } else if (["pugno", "diretto", "montante", "calcio", "lancia", "spara", "fendente", "affondo", "rovescio", "scattoLama", "pressa", "trasforma", "presa", "estrai"].indexOf(f.azione) >= 0) {
      ctx.ellipse(x, y + 0.04 * R, 0.2 * R, 0.17 * R, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#ff7a8a"; ctx.beginPath();
      ctx.ellipse(x, y + 0.1 * R, 0.12 * R, 0.07 * R, 0, 0, Math.PI * 2); ctx.fill();
    } else if (f.azione === "esulta" || f.azione === "balla") {
      ctx.moveTo(x - w, y - 0.04 * R); ctx.quadraticCurveTo(x, y + 0.5 * R, x + w, y - 0.04 * R); ctx.closePath();
      ctx.fillStyle = "#111"; ctx.fill();
      ctx.fillStyle = "#fff"; ctx.fillRect(x - w * 0.6, y - 0.03 * R, w * 1.2, 0.07 * R);
    } else if (f.azione === "provoca") {
      ctx.moveTo(x - w, y); ctx.quadraticCurveTo(x, y + 0.14 * R, x + w, y - 0.1 * R); ctx.stroke();
      ctx.fillStyle = "#ff7a8a"; ctx.beginPath();
      ctx.ellipse(x + f.dir * w * 0.5, y + 0.12 * R, 0.1 * R, 0.14 * R, 0, 0, Math.PI * 2); ctx.fill();
      ctx.lineWidth = 1 * S; ctx.stroke();
    } else if (f.azione === "salto" || f.azione === "indietro") {
      ctx.ellipse(x, y + 0.03 * R, 0.1 * R, 0.1 * R, 0, 0, Math.PI * 2); ctx.stroke();
    } else {
      const sorriso = 0.12 + 0.04 * Math.sin(f.passo * 0.2);
      ctx.moveTo(x - w * 0.8, y); ctx.quadraticCurveTo(x, y + sorriso * R * 2, x + w * 0.8, y); ctx.stroke();
    }
  }

  // Il frutto occupa tutto lo spazio fra il bacino e la testa: la mela è
  // alta quanto il robot e i colpi arrivano dove la si vede (01/10/2026:
  // prima era più bassa e i pugni sopra di lei colpivano l'aria).
  function corpoMela(p) {
    const A = p.testa, B = p.bacino;
    const L = Math.hypot(B.x - A.x, B.y - A.y) || 1;
    return { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2, ang: Math.atan2(B.y - A.y, B.x - A.x) - Math.PI / 2,
             R: Math.max(12 * S, Math.min(21 * S, L * 0.53)) };
  }
  function sagomaMela(R) {
    ctx.beginPath();
    ctx.moveTo(0, -0.72 * R);
    ctx.bezierCurveTo(0.55 * R, -1.08 * R, 1.12 * R, -0.62 * R, 1.02 * R, 0.08 * R);
    ctx.bezierCurveTo(0.96 * R, 0.66 * R, 0.55 * R, 1.06 * R, 0.22 * R, 0.96 * R);
    ctx.bezierCurveTo(0.08 * R, 0.92 * R, -0.08 * R, 0.92 * R, -0.22 * R, 0.96 * R);
    ctx.bezierCurveTo(-0.55 * R, 1.06 * R, -0.96 * R, 0.66 * R, -1.02 * R, 0.08 * R);
    ctx.bezierCurveTo(-1.12 * R, -0.62 * R, -0.55 * R, -1.08 * R, 0, -0.72 * R);
    ctx.closePath();
  }

  function disegnaMela(f) {
    const p = f.p, nero = "#111";
    // Gambe senza incroci: il ginocchio si piega sempre verso la faccia,
    // qualunque cosa faccia la fisica (prima le gambe si intrecciavano).
    const st = f.staccati || {};
    for (const piede of [p.piedeD, p.piedeA]) {
      if ((piede === p.piedeD && st.gD) || (piede === p.piedeA && st.gA)) continue;
      const dx = piede.x - p.bacino.x, dy = piede.y - p.bacino.y, lun = Math.hypot(dx, dy) || 1;
      let nx = -dy / lun, ny = dx / lun;
      if (nx * f.dir < 0) { nx = -nx; ny = -ny; }
      const ginocchio = { x: p.bacino.x + dx / 2 + nx * 0.14 * lun, y: p.bacino.y + dy / 2 + ny * 0.14 * lun };
      arto(p.bacino, ginocchio, piede, 3.2 * S, nero);
      ctx.fillStyle = "#f7f7f7"; ctx.beginPath();
      ctx.ellipse(piede.x + f.dir * 1.5 * S, piede.y - 0.5 * S, 4.2 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = nero; ctx.lineWidth = 1.2 * S; ctx.stroke();
    }
    const c = corpoMela(p), R = c.R;
    zaino(f, R + 2 * S);
    // Le braccia partono dai FIANCHI del frutto, non dal centro: così non
    // attraversano la faccia.
    let qx = Math.cos(c.ang), qy = Math.sin(c.ang);
    if (qx * f.dir < 0) { qx = -qx; qy = -qy; }
    const giu = { x: -Math.sin(c.ang), y: Math.cos(c.ang) };
    const spalla = { x: c.x + giu.x * 0.15 * R, y: c.y + giu.y * 0.15 * R };
    const spallaA = { x: spalla.x + qx * 0.86 * R, y: spalla.y + qy * 0.86 * R };
    const spallaD = { x: spalla.x - qx * 0.86 * R, y: spalla.y - qy * 0.86 * R };
    if (!st.D) arto(spallaD, p.gomitoD, p.manoD, 3 * S, nero);
    ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.ang);
    const frutto = () => {
      // I morsi: buchi nella sagoma (ritagliati via) col bordo di polpa.
      const morsi = f.morsi || [];
      if (morsi.length) {
        ctx.save(); ctx.beginPath(); ctx.rect(-3 * R, -3 * R, 6 * R, 6 * R);
        for (const m of morsi) { const r = m.r * R * m.k; ctx.moveTo(m.x * R + r, m.y * R); ctx.arc(m.x * R, m.y * R, r, 0, Math.PI * 2); }
        ctx.clip("evenodd");
      }
      // Polpa bianca con una sfumatura crema verso il bordo, poi la buccia.
      const polpa = ctx.createRadialGradient(-R * 0.2, -R * 0.2, R * 0.1, 0, 0, R * 1.05);
      polpa.addColorStop(0, "#ffffff"); polpa.addColorStop(1, "#f6efe1");
      sagomaMela(R); ctx.fillStyle = polpa; ctx.fill();
      ctx.lineWidth = 2.6 * S; ctx.strokeStyle = "#111"; ctx.lineJoin = "round"; ctx.stroke();
      if (!st.P) {
        linea({ x: 0, y: -0.7 * R }, { x: 0.12 * R, y: -1.18 * R }, 1.8 * S, "#6b4423");
        ctx.fillStyle = "#3f9a3a"; ctx.beginPath();
        ctx.ellipse(0.42 * R, -1.08 * R, 0.34 * R, 0.14 * R, -0.45, 0, Math.PI * 2); ctx.fill();
      }
      // Occhi neri, con un puntino di luce: guardano verso l'avversario.
      const exs = [-0.34 * R + f.dir * 0.08 * R, 0.34 * R + f.dir * 0.08 * R];
      if (f.ko || f.rialzo > 30 || f.dolore) {
        occhi(f, f.dir * 0.08 * R - f.dir * 1.2 * S, -0.16 * R, 0.34 * R, 0.13 * R, "#111");
      } else {
        for (const ex of exs) {
          ctx.fillStyle = "#111"; ctx.beginPath();
          ctx.ellipse(ex, -0.16 * R, 0.15 * R, 0.21 * R, 0, 0, Math.PI * 2); ctx.fill();
          tondo(ex + f.dir * 0.05 * R, -0.24 * R, 0.05 * R, "#ffffff");
        }
        ctx.strokeStyle = "#111"; ctx.lineWidth = 1.4 * S; ctx.lineCap = "round"; ctx.beginPath();
        for (let i = 0; i < 2; i++) {
          const lato = i === 0 ? -1 : 1, x0 = exs[i];
          ctx.moveTo(x0 - 0.2 * R, -0.48 * R + (lato === f.dir ? 0.08 : -0.02) * R);
          ctx.lineTo(x0 + 0.2 * R, -0.48 * R + (lato === f.dir ? -0.02 : 0.08) * R);
        }
        ctx.stroke();
      }
      bocca(f, R);
      disegnaSegni(f, "frutto");
      if (natale) cappellino(0.04 * R, -0.74 * R, 0.6 * R, f.dir);
      if (morsi.length) {
        ctx.restore();
        // Il bordo del morso: polpa color crema e la dentatura.
        ctx.save(); sagomaMela(R); ctx.clip();
        for (const m of morsi) {
          const r = m.r * R * m.k;
          ctx.strokeStyle = "#f1dfb6"; ctx.lineWidth = 3.2 * S; ctx.beginPath(); ctx.arc(m.x * R, m.y * R, r + 1.6 * S, 0, Math.PI * 2); ctx.stroke();
          ctx.strokeStyle = "#111"; ctx.lineWidth = 1.5 * S; ctx.beginPath();
          for (let i = 0; i <= 24; i++) {
            const a = (i / 24) * Math.PI * 2, rr = r + (i % 2 ? 0.9 : 0) * S;
            if (i) ctx.lineTo(m.x * R + Math.cos(a) * rr, m.y * R + Math.sin(a) * rr); else ctx.moveTo(m.x * R + rr, m.y * R);
          }
          ctx.stroke();
        }
        ctx.restore();
      }
    };
    const tg = temaGravita();
    if (f.taglio) {
      // Tagliata in due dalla spada: le metà si aprono, poi si richiudono.
      const tg2 = f.taglio, a = tg2.ang, nx = -Math.sin(a), ny = Math.cos(a);
      const apri = tg2.t < TAGLIO_CHIUDE ? Math.min(1, tg2.t / 10) : Math.max(0, 1 - (tg2.t - TAGLIO_CHIUDE) / 22);
      const d = 8 * S * apri;
      for (const lato of [1, -1]) {
        ctx.save();
        ctx.translate(nx * lato * d, ny * lato * d + (lato > 0 ? 2 * S * apri : 0)); ctx.rotate(lato * 0.18 * apri);
        ctx.beginPath();
        const ux = Math.cos(a) * 3 * R, uy = Math.sin(a) * 3 * R;
        ctx.moveTo(-ux, -uy); ctx.lineTo(ux, uy); ctx.lineTo(ux + nx * lato * 3 * R, uy + ny * lato * 3 * R); ctx.lineTo(-ux + nx * lato * 3 * R, -uy + ny * lato * 3 * R);
        ctx.closePath(); ctx.clip();
        frutto();
        // La faccia del taglio: polpa crema col torsolo e i semi.
        ctx.save(); sagomaMela(R); ctx.clip();
        ctx.strokeStyle = "#f1dfb6"; ctx.lineWidth = 4 * S; ctx.beginPath(); ctx.moveTo(-ux, -uy); ctx.lineTo(ux, uy); ctx.stroke();
        ctx.strokeStyle = "#111"; ctx.lineWidth = 1.4 * S; ctx.stroke();
        ctx.fillStyle = "#4a2e1a";
        for (const k of [-0.15, 0.15]) { ctx.beginPath(); ctx.ellipse(Math.cos(a) * k * R + nx * lato * 2 * S, Math.sin(a) * k * R + ny * lato * 2 * S, 1.6 * S, 1 * S, a, 0, Math.PI * 2); ctx.fill(); }
        ctx.restore();
        ctx.restore();
      }
    } else frutto();
    if (tg === "luna" || tg === "spazio") casco(1.3 * R);
    ctx.restore();
    // Tutt'e due le braccia stanno DAVANTI al corpo: prima quella lontana
    // finiva dietro la polpa e la mela sembrava avere una mano sola.
    for (const [gomito, mano, r, colore] of [[p.gomitoD, p.manoD, 3.9, "#1f56b8"], [p.gomitoA, p.manoA, 4.2, "#2f72e0"]]) {
      if ((mano === p.manoD && st.D) || (mano === p.manoA && st.A)) continue;
      if (mano !== p.manoD) arto(spallaA, gomito, mano, 3 * S, nero);
      guanto(gomito, mano, colore, r * S);
    }
    if (f.palla && !st.A) tondo(p.manoA.x, p.manoA.y - 3 * S, 3 * S, "#ffffff");
  }

  // Una rottura dello schermo: una ragnatela che parte dal punto d'urto, con
  // raggi spezzati e qualche anello. Tutto in coordinate locali del telefono
  // e, al disegno, ritagliato dentro lo schermo: non esce mai dal telefono.
  function rompiSchermo(t) {
    if (!t.sch) return;
    const [sx, sy, w, h] = t.sch;
    const cx = sx + w / 2 + caso(-0.3, 0.3) * w, cy = sy + h / 2 + caso(-0.3, 0.3) * h;
    const raggi = [], n = 4 + Math.floor(Math.random() * 2);
    const base = caso(0, Math.PI * 2);
    for (let i = 0; i < n; i++) {
      const a = base + (i / n) * Math.PI * 2 + caso(-0.25, 0.25);
      const lung = caso(0.35, 0.8) * Math.max(w, h);
      const pts = [[cx, cy]];
      let x = cx, y = cy, aa = a;
      for (let k = 1; k <= 3; k++) {
        aa += caso(-0.3, 0.3);
        x += Math.cos(aa) * lung / 3; y += Math.sin(aa) * lung / 3;
        pts.push([x, y]);
      }
      raggi.push(pts);
    }
    t.rotture.push({ cx, cy, raggi, anelli: [caso(0.07, 0.12) * w, caso(0.17, 0.25) * w] });
    if (t.rotture.length > 2) t.rotture.shift();
  }

  // Le armi, da cartone: origine sull'impugnatura, +x verso la punta.
  function disegnaArma(t) {
    if (Math.cos(t.a) < 0) ctx.scale(1, -1);          // l'impugnatura resta in basso
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S; ctx.lineJoin = "round";
    if (t.tipo === "pistola") {
      ctx.fillStyle = "#5a4030"; ctx.beginPath();
      ctx.moveTo(-2.6 * S, -1.4 * S); ctx.lineTo(1.6 * S, -1.4 * S); ctx.lineTo(0.6 * S, 4.2 * S); ctx.lineTo(-3.6 * S, 4.2 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#2b2f3a"; rettangoloTondo(-3.4 * S, -5.6 * S, 14.6 * S, 4.6 * S, 1.3 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#ff8a1a"; ctx.fillRect(10 * S, -5.6 * S, 2.2 * S, 4.6 * S); ctx.strokeRect(10 * S, -5.6 * S, 2.2 * S, 4.6 * S);
      ctx.strokeStyle = "rgba(255,255,255,.35)"; ctx.beginPath(); ctx.moveTo(-1.5 * S, -4.4 * S); ctx.lineTo(8 * S, -4.4 * S); ctx.stroke();
      ctx.strokeStyle = "#111"; ctx.beginPath(); ctx.arc(2.2 * S, 0.2 * S, 1.6 * S, 0, Math.PI); ctx.stroke();
    } else {
      const g = ctx.createLinearGradient(0, -1.6 * S, 0, 1.6 * S);
      g.addColorStop(0, "#f4f7fb"); g.addColorStop(1, "#9aa6b6");
      ctx.fillStyle = g; ctx.beginPath();
      ctx.moveTo(4 * S, -1.5 * S); ctx.lineTo(27 * S, -1.5 * S); ctx.lineTo(31 * S, 0); ctx.lineTo(27 * S, 1.5 * S); ctx.lineTo(4 * S, 1.5 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 0.6 * S;
      ctx.beginPath(); ctx.moveTo(6 * S, -0.3 * S); ctx.lineTo(25 * S, -0.3 * S); ctx.stroke();
      ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S;
      ctx.fillStyle = "#d9a520"; rettangoloTondo(2.2 * S, -4.6 * S, 2.2 * S, 9.2 * S, 0.8 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#6b4423"; ctx.fillRect(-5 * S, -1.3 * S, 7.2 * S, 2.6 * S); ctx.strokeRect(-5 * S, -1.3 * S, 7.2 * S, 2.6 * S);
      tondo(-5.8 * S, 0, 1.9 * S, "#d9a520"); ctx.beginPath(); ctx.arc(-5.8 * S, 0, 1.9 * S, 0, Math.PI * 2); ctx.stroke();
    }
  }

  function disegnaTelefono(t) {
    ctx.save(); ctx.translate(t.x, t.y); ctx.rotate(t.a);
    if (eArma(t)) { disegnaArma(t); ctx.restore(); return; }
    if (t.tipo === "fumogeno") {
      // Una bomboletta col tappo e l'anello: grigia, con la fascia viola.
      const w = t.w, h = t.h;
      ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S; ctx.lineJoin = "round";
      ctx.fillStyle = "#8f95a3"; rettangoloTondo(-w / 2, -h / 2 + 2 * S, w, h - 2 * S, 1.8 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#9a6be0"; ctx.fillRect(-w / 2 + 0.6 * S, -1.5 * S, w - 1.2 * S, 3.4 * S);
      ctx.fillStyle = "#3a3f4a"; ctx.fillRect(-2 * S, -h / 2, 4 * S, 2.4 * S); ctx.strokeRect(-2 * S, -h / 2, 4 * S, 2.4 * S);
      ctx.beginPath(); ctx.arc(3.6 * S, -h / 2 + 0.6 * S, 1.8 * S, 0, Math.PI * 2); ctx.stroke();
      ctx.restore(); return;
    }
    if (t.tipo === "barattolo") {
      // Un barattolo di vetro col tappo di sughero: dentro brilla la creatura.
      const w = t.w, h = t.h, E = ELEMENTI[t.el] || ELEMENTI.fuoco, batte = 0.55 + 0.25 * Math.sin(passi * 0.2 + t.x);
      ctx.lineJoin = "round";
      ctx.fillStyle = "rgba(210,236,255,.55)"; ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S;
      rettangoloTondo(-w / 2, -h / 2 + 3 * S, w, h - 3 * S, 2.6 * S); ctx.fill();
      ctx.globalAlpha = batte; tondo(0, 2 * S, 3.4 * S, E.colore); ctx.globalAlpha = 1; tondo(0, 2 * S, 1.6 * S, "#ffffff");
      ctx.strokeStyle = "#111"; rettangoloTondo(-w / 2, -h / 2 + 3 * S, w, h - 3 * S, 2.6 * S); ctx.stroke();
      ctx.fillStyle = "#b98a54"; ctx.fillRect(-w / 2 + 1.6 * S, -h / 2, w - 3.2 * S, 3.4 * S); ctx.strokeRect(-w / 2 + 1.6 * S, -h / 2, w - 3.2 * S, 3.4 * S);
      ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.moveTo(-w / 2 + 2 * S, -h / 2 + 6 * S); ctx.lineTo(-w / 2 + 2 * S, h / 2 - 3 * S); ctx.stroke();
      ctx.restore(); return;
    }
    if (t.tipo === "bomba") {
      const r = 5.2 * S, rosso = t.miccia > 0 && t.miccia < 60 && passi % 8 < 4;
      ctx.fillStyle = rosso ? "#7a1a14" : "#1d1d22"; ctx.strokeStyle = "#000"; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      tondo(-r * 0.35, -r * 0.35, r * 0.28, "rgba(255,255,255,.45)");
      ctx.fillStyle = "#555b66"; ctx.fillRect(-1.8 * S, -r - 2 * S, 3.6 * S, 2.6 * S);
      ctx.strokeStyle = "#8a6a3a"; ctx.lineWidth = 1.1 * S; ctx.beginPath();
      ctx.moveTo(0, -r - 2 * S); ctx.quadraticCurveTo(2.5 * S, -r - 5 * S, 4.5 * S, -r - 4 * S); ctx.stroke();
      if (t.miccia > 0) stella(4.5 * S, -r - 4 * S, (1.6 + Math.random()) * S, passi % 4 < 2 ? "#ffd84a" : "#ff8a1a");
      ctx.restore(); return;
    }
    const w = t.w, h = t.h;
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1.2 * S; ctx.lineJoin = "round";
    if (t.tipo === "duo") {
      // Il pieghevole si apre a libro mentre la mela lo tira fuori, e brilla.
      if (t.stato === "portato") {
        const alone = ctx.createRadialGradient(0, 0, 2 * S, 0, 0, 20 * S);
        alone.addColorStop(0, "rgba(220,200,255,.75)"); alone.addColorStop(1, "rgba(220,200,255,0)");
        ctx.fillStyle = alone; ctx.beginPath(); ctx.arc(0, 0, 20 * S, 0, Math.PI * 2); ctx.fill();
      }
      ctx.scale(0.5 + 0.5 * t.apre, 1);
    }
    if (t.tipo === "orologio") {
      ctx.fillStyle = mix(t.colore, "#000000", 0.2);
      rettangoloTondo(-w * 0.32, -h / 2 - 5 * S, w * 0.64, h + 10 * S, 1.6 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#c9ced8"; rettangoloTondo(-w / 2, -h / 2, w, h, 2.4 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#9aa1ad"; ctx.fillRect(w / 2, -1.2 * S, 1.3 * S, 2.4 * S);
    } else if (t.tipo === "pc") {
      // Il portatile aperto: il coperchio con lo schermo e, sotto, la tastiera.
      ctx.fillStyle = mix(t.colore, "#000000", 0.15); ctx.beginPath();
      ctx.moveTo(-w / 2, h * 0.18); ctx.lineTo(w / 2, h * 0.18); ctx.lineTo(w / 2 + 2.4 * S, h / 2); ctx.lineTo(-w / 2 - 2.4 * S, h / 2);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "rgba(0,0,0,.35)";
      for (let i = 0; i < 6; i++) ctx.fillRect((-w / 2 + 1.5 * S) + i * (w - 3 * S) / 6, h * 0.27, (w - 3 * S) / 6 - 0.8 * S, 1.3 * S);
      ctx.fillStyle = t.colore; rettangoloTondo(-w / 2, -h / 2, w, h * 0.68, 1.6 * S); ctx.fill(); ctx.stroke();
    } else {
      ctx.fillStyle = t.colore;
      rettangoloTondo(-w / 2, -h / 2, w, h, (t.tipo === "tablet" ? 2.8 : 2) * S); ctx.fill(); ctx.stroke();
    }
    const [sx, sy, sw, sh] = t.sch;
    if (t.tipo === "duo") {
      const g = ctx.createLinearGradient(sx, sy, sx + sw, sy + sh);
      g.addColorStop(0, "#6b4bd8"); g.addColorStop(0.5, "#d65aa8"); g.addColorStop(1, "#f2a64a");
      ctx.fillStyle = t.stato === "preso" ? "#7fe0ff" : g;
    } else ctx.fillStyle = t.stato === "preso" ? "#7fe0ff" : "#10202e";
    rettangoloTondo(sx, sy, sw, sh, 1.2 * S); ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,.25)";
    ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + sw * 0.6, sy); ctx.lineTo(sx, sy + sh * 0.6); ctx.closePath(); ctx.fill();
    if (t.tipo === "pieghevole") { ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.moveTo(-w / 2, 0); ctx.lineTo(w / 2, 0); ctx.stroke(); }
    if (t.tipo === "duo") {
      ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.lineWidth = 0.8 * S; ctx.beginPath(); ctx.moveTo(0, -h / 2); ctx.lineTo(0, h / 2); ctx.stroke();
      ctx.fillStyle = "#000"; rettangoloTondo(-sw * 0.18, sy + 0.8 * S, sw * 0.36, 1.4 * S, 0.7 * S); ctx.fill();
    } else if (t.tipo !== "orologio" && t.tipo !== "pc") tondo(0, -h / 2 + 0.8 * S, 0.5 * S, "#000");
    if (t.rotture && t.rotture.length) {
      // Ritaglio: le crepe vivono solo dentro lo schermo.
      ctx.save();
      rettangoloTondo(sx, sy, sw, sh, 1.2 * S); ctx.clip();
      for (const r of t.rotture) {
        // Macchia scura dove il vetro ha ceduto.
        ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.beginPath(); ctx.arc(r.cx, r.cy, r.anelli[0] * 0.9, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = "rgba(235,246,255,.9)"; ctx.lineWidth = 0.55 * S; ctx.lineJoin = "round"; ctx.beginPath();
        for (const pts of r.raggi) {
          ctx.moveTo(pts[0][0], pts[0][1]);
          for (let k = 1; k < pts.length; k++) ctx.lineTo(pts[k][0], pts[k][1]);
        }
        ctx.stroke();
        ctx.strokeStyle = "rgba(235,246,255,.5)"; ctx.lineWidth = 0.4 * S; ctx.beginPath();
        for (const rr of r.anelli) { ctx.moveTo(r.cx + rr, r.cy); ctx.arc(r.cx, r.cy, rr, 0, Math.PI * 2); }
        ctx.stroke();
      }
      ctx.restore();
    }
    ctx.restore();
  }

  function disegnaParticella(q) {
    ctx.save();
    ctx.globalAlpha = Math.max(0, Math.min(1, q.vita / (q.max * 0.6)));
    if (q.tipo === "scintilla") {
      ctx.strokeStyle = q.colore; ctx.lineWidth = 1.6 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x - q.vx * 1.6, q.y - q.vy * 1.6); ctx.stroke();
    } else if (q.tipo === "fiamma") {
      ctx.fillStyle = q.colore; ctx.beginPath();
      ctx.arc(q.x, q.y, Math.max(0.5, (1 + 3.2 * (q.vita / q.max))) * S, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "mote") {
      ctx.globalAlpha = 0.9; ctx.fillStyle = q.colore; ctx.beginPath(); ctx.arc(q.x, q.y, 1.8 * S, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "linea") {
      const v = Math.hypot(q.vx, q.vy) || 1;
      ctx.strokeStyle = q.colore; ctx.lineWidth = 1.4 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x + q.vx / v * q.lung, q.y + q.vy / v * q.lung); ctx.stroke();
    } else if (q.tipo === "taglio") {
      // Il segno di un taglio: una riga di luce che si assottiglia.
      const k = q.vita / q.max, dx = Math.cos(q.ang) * q.lung * (1.2 - 0.2 * k), dy = Math.sin(q.ang) * q.lung * (1.2 - 0.2 * k);
      ctx.lineCap = "round"; ctx.globalAlpha = 0.5 * k; ctx.strokeStyle = q.colore; ctx.lineWidth = 6 * S * k;
      ctx.beginPath(); ctx.moveTo(q.x - dx, q.y - dy); ctx.lineTo(q.x + dx, q.y + dy); ctx.stroke();
      ctx.globalAlpha = k; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.8 * S * k; ctx.stroke();
    } else if (q.tipo === "zip") {
      ctx.strokeStyle = q.colore; ctx.lineWidth = 1.6 * S; ctx.lineCap = "round"; ctx.beginPath();
      for (const dx of [-9, -3, 3, 9]) { ctx.moveTo(q.x + dx * S, q.y - 34 * S); ctx.lineTo(q.x + dx * S, q.y + 24 * S); }
      ctx.stroke();
    } else if (q.tipo === "lampo") {
      const g = ctx.createRadialGradient(q.x, q.y, 0, q.x, q.y, q.r);
      g.addColorStop(0, "rgba(255,255,240,.95)"); g.addColorStop(0.4, "rgba(255,226,122,.55)"); g.addColorStop(1, "rgba(255,180,60,0)");
      ctx.globalAlpha = q.vita / q.max; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "fuoco") {
      const k = q.vita / q.max;
      ctx.fillStyle = k > 0.75 ? "#fff3b0" : k > 0.5 ? "#ffb62e" : k > 0.28 ? "#ff6a1a" : "#6e4a3a";
      ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "fumo") {
      ctx.globalAlpha = 0.55 * q.vita / q.max; ctx.fillStyle = q.colore;
      ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "detrito") {
      ctx.translate(q.x, q.y); ctx.rotate(q.rot); ctx.fillStyle = q.colore;
      ctx.fillRect(-q.lato / 2, -q.lato * 0.35, q.lato, q.lato * 0.7);
    } else if (q.tipo === "pezzetto") {
      // Il boccone portato via: polpa bianca con la buccia nera sul bordo.
      ctx.translate(q.x, q.y); ctx.rotate(q.rot);
      const r = q.lato;
      ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(0, 0, r, Math.PI, Math.PI * 2); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = "#f1dfb6"; ctx.lineWidth = 1.4 * S; ctx.stroke();
      ctx.strokeStyle = "#111"; ctx.lineWidth = 2 * S; ctx.beginPath(); ctx.arc(0, 0, r, Math.PI, Math.PI * 2); ctx.stroke();
    } else if (q.tipo === "brace") {
      ctx.fillStyle = (passi + Math.round(q.x)) % 6 < 3 ? q.colore : "#fff1a0";
      ctx.beginPath(); ctx.arc(q.x, q.y, 1.3 * S, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "goccia") {
      ctx.globalAlpha = 0.9; ctx.fillStyle = q.colore; ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "pioggia") {
      ctx.globalAlpha = 1; ctx.strokeStyle = "rgba(90,140,210,.55)"; ctx.lineWidth = 1.1 * S;
      ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x - q.vx * 1.2, q.y - q.vy * 1.2); ctx.stroke();
    } else if (q.tipo === "fiocco") {
      ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "rgba(70,100,135,.55)"; ctx.lineWidth = 0.8 * S;
      ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    } else if (q.tipo === "vento") {
      ctx.globalAlpha = 0.4; ctx.strokeStyle = "#7d8696"; ctx.lineWidth = 1.2 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x - Math.sign(q.vx) * q.lung, q.y); ctx.stroke();
    } else if (q.tipo === "nota") {
      ctx.fillStyle = q.colore; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2 * S;
      ctx.font = "700 " + Math.round(14 * S) + "px sans-serif"; ctx.textAlign = "center";
      ctx.strokeText(q.testo, q.x, q.y); ctx.fillText(q.testo, q.x, q.y);
    } else if (q.tipo === "onda") {
      const k = 1 - q.vita / q.max;
      ctx.globalAlpha = Math.max(0, 1 - k);
      ctx.strokeStyle = q.colore; ctx.lineWidth = (6 - 4 * k) * S;
      ctx.beginPath(); ctx.arc(q.x, q.y, (10 + 70 * k) * S, 0, Math.PI * 2); ctx.stroke();
    } else if (q.tipo === "polvere") {
      ctx.fillStyle = q.colore; ctx.beginPath(); ctx.arc(q.x, q.y, (2 + (1 - q.vita / q.max) * 4) * S, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.translate(q.x, q.y); ctx.rotate(q.rot); ctx.fillStyle = q.colore; ctx.fillRect(-1.6 * S, -1 * S, 3.2 * S, 2 * S);
    }
    ctx.restore();
  }

  function disegnaProiettile(b) {
    if (b.grande) { disegnaSferaGrande(b.x, b.y, b.r, b.colore); return; }
    if (b.disco) { if (b.lamaDi) disegnaLamaVolante(b); else disegnaDisco(b.x, b.y, 11 * S, b.colore); return; }
    if (b.incanto || b.stella) {
      // Gli incantesimi sono stelle con la coda.
      const v = Math.hypot(b.vx, b.vy) || 1;
      ctx.save(); ctx.strokeStyle = b.colore; ctx.globalAlpha = 0.5; ctx.lineWidth = 2.4 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(b.x - b.vx / v * 16 * S, b.y - b.vy / v * 16 * S); ctx.lineTo(b.x, b.y); ctx.stroke();
      ctx.globalAlpha = 1; stella(b.x, b.y, (b.incanto ? 5.4 : 3.8) * S, b.colore); stella(b.x, b.y, (b.incanto ? 2.6 : 1.8) * S, "#ffffff");
      ctx.restore();
      return;
    }
    if (b.energia) {
      ctx.save(); ctx.globalAlpha = 0.45; ctx.fillStyle = b.colore; ctx.beginPath(); ctx.arc(b.x, b.y, 6 * S, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1; tondo(b.x, b.y, 2.6 * S, "#ffffff"); ctx.restore();
      return;
    }
    if (b.neve) {
      tondo(b.x, b.y, 3.2 * S, "#ffffff");
      ctx.strokeStyle = "rgba(0,0,0,.25)"; ctx.lineWidth = 0.8 * S; ctx.beginPath(); ctx.arc(b.x, b.y, 3.2 * S, 0, Math.PI * 2); ctx.stroke();
      return;
    }
    const v = Math.hypot(b.vx, b.vy) || 1, ux = b.vx / v, uy = b.vy / v;
    ctx.save();
    ctx.strokeStyle = "rgba(255,226,122,.55)"; ctx.lineWidth = 2 * S; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(b.x - ux * 12 * S, b.y - uy * 12 * S); ctx.lineTo(b.x, b.y); ctx.stroke();
    ctx.translate(b.x, b.y); ctx.rotate(Math.atan2(uy, ux));
    ctx.fillStyle = "#ffb62e"; ctx.strokeStyle = "#111"; ctx.lineWidth = 0.9 * S;
    rettangoloTondo(-2.6 * S, -1.3 * S, 5.2 * S, 2.6 * S, 1.3 * S); ctx.fill(); ctx.stroke();
    ctx.restore();
  }

  // Il paracadute: una cupola a spicchi bianchi e colorati, con le corde
  // fino alle mani. Si apre e si richiude piano (f.para va da 0 a 1).
  function disegnaParacadute(f) {
    const k = f.para;
    if (!(k > 0.02)) return;
    const p = f.p, sx = p.manoA.x < p.manoD.x ? p.manoA : p.manoD, dx = sx === p.manoA ? p.manoD : p.manoA;
    const sway = Math.max(-6 * S, Math.min(6 * S, (p.bacino.x - p.bacino.ox) * 6));
    const cx = (sx.x + dx.x) / 2 - sway, cy = Math.min(sx.y, dx.y) - 30 * S * k, w = 27 * S * k, h = 16 * S * k;
    const [c1, c2] = f.tipo === "robot" ? ["#ff5a4a", "#ffffff"] : ["#2f72e0", "#ffffff"];
    ctx.save();
    ctx.strokeStyle = "rgba(20,20,20,.7)"; ctx.lineWidth = 0.8 * S; ctx.beginPath();
    for (const fr of [-1, -0.35, 0.35, 1]) { const m = fr < 0 ? sx : dx; ctx.moveTo(cx + fr * w, cy); ctx.lineTo(m.x, m.y); }
    ctx.stroke();
    const cupola = () => {
      ctx.beginPath(); ctx.moveTo(cx - w, cy);
      ctx.bezierCurveTo(cx - w, cy - h * 1.6, cx + w, cy - h * 1.6, cx + w, cy);
      for (let i = 2; i >= 0; i--) {
        const x1 = cx - w + (2 * w) * i / 3, x2 = cx - w + (2 * w) * (i + 1) / 3;
        ctx.quadraticCurveTo((x1 + x2) / 2, cy - 4 * S * k, x1, cy);
      }
      ctx.closePath();
    };
    cupola(); ctx.fillStyle = c1; ctx.fill();
    ctx.save(); cupola(); ctx.clip();
    ctx.fillStyle = c2; ctx.fillRect(cx - w / 6, cy - h * 2, w / 3, h * 3);
    ctx.fillRect(cx - w, cy - h * 2, w / 4, h * 3); ctx.fillRect(cx + w * 0.75, cy - h * 2, w / 4, h * 3);
    ctx.restore();
    cupola(); ctx.strokeStyle = "#111"; ctx.lineWidth = 1.2 * S; ctx.stroke();
    ctx.restore();
  }

  // I segni dei colpi, nel sistema di riferimento della parte colpita.
  function disegnaSegni(f, parte) {
    if (!f.segni || !f.segni.length) return;
    for (const sg of f.segni) {
      if (sg.parte !== parte) continue;
      const x = sg.u * S, y = sg.v * S, r = sg.r * S, a = Math.min(1, sg.vita / 600);
      ctx.save(); ctx.globalAlpha = a;
      if (stile) {
        // Un livido, sui personaggi in carne e ossa.
        const g = ctx.createRadialGradient(x, y, 0, x, y, r * 1.2);
        g.addColorStop(0, "rgba(96,52,120,.6)"); g.addColorStop(0.6, "rgba(120,70,130,.35)"); g.addColorStop(1, "rgba(130,80,140,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 1.2, 0, Math.PI * 2); ctx.fill();
      } else if (f.tipo === "mela") {
        // Livido marrone, come una mela ammaccata vera.
        const g = ctx.createRadialGradient(x, y, 0, x, y, r * 1.3);
        g.addColorStop(0, "rgba(120,72,34,.75)"); g.addColorStop(0.6, "rgba(150,96,50,.45)"); g.addColorStop(1, "rgba(160,110,60,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 1.3, 0, Math.PI * 2); ctx.fill();
      } else {
        // Ammaccatura: una conca scura e due graffi chiari.
        ctx.fillStyle = "rgba(0,0,0,.28)"; ctx.beginPath();
        for (let i = 0; i < 7; i++) {
          const an = (i / 7) * Math.PI * 2, rr = r * (0.7 + 0.3 * Math.sin(sg.seme + i * 2.3));
          if (i) ctx.lineTo(x + Math.cos(an) * rr, y + Math.sin(an) * rr); else ctx.moveTo(x + Math.cos(an) * rr, y + Math.sin(an) * rr);
        }
        ctx.closePath(); ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,.6)"; ctx.lineWidth = 0.6 * S; ctx.beginPath();
        ctx.moveTo(x - r * 0.6, y - r * 0.2); ctx.lineTo(x + r * 0.5, y + r * 0.3);
        ctx.moveTo(x - r * 0.3, y + r * 0.5); ctx.lineTo(x + r * 0.6, y - r * 0.1); ctx.stroke();
      }
      ctx.restore();
    }
  }

  // Un arto staccato che vola (e poi torna).
  function disegnaArto(a) {
    ctx.save(); ctx.translate(a.x, a.y); ctx.rotate(a.ang);
    if (a.forma === "picciolo") {
      if (a.f.tipo === "mela") {
        ctx.strokeStyle = "#6b4423"; ctx.lineWidth = 1.8 * S; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(0, 4 * S); ctx.lineTo(1.6 * S, -4 * S); ctx.stroke();
        ctx.fillStyle = "#3f9a3a"; ctx.beginPath(); ctx.ellipse(5.5 * S, -3 * S, 5 * S, 2.1 * S, -0.45, 0, Math.PI * 2); ctx.fill();
      } else {
        ctx.strokeStyle = a.colore; ctx.lineWidth = 1.4 * S; ctx.beginPath(); ctx.moveTo(0, 5 * S); ctx.lineTo(0, -3 * S); ctx.stroke();
        tondo(0, -3.6 * S, 2.1 * S, "#ffcf3a");
      }
      ctx.restore(); return;
    }
    const L = a.L, robot = a.grosso, w = robot ? 4.6 * S : 3 * S;
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S;
    ctx.fillStyle = a.colore; rettangoloTondo(-L / 2, -w / 2, L, w, w / 2); ctx.fill(); if (robot) ctx.stroke();
    tondo(-L / 2, 0, w * 0.6, a.olio ? "#1b1b1b" : "#d8343f");
    if (a.forma === "braccio") {
      ctx.fillStyle = a.estremo; ctx.beginPath(); ctx.ellipse(L / 2 + 2 * S, 0, 4.4 * S, 3.8 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    } else {
      ctx.fillStyle = a.estremo; ctx.beginPath(); ctx.ellipse(L / 2 + 1.5 * S, 1 * S, 4.4 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    ctx.restore();
  }

  // Un pezzo del robot esploso.
  function disegnaPezzo(pz) {
    ctx.save(); ctx.translate(pz.x, pz.y); ctx.rotate(pz.ang);
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S; ctx.fillStyle = pz.colore;
    switch (pz.forma) {
      case "asta": rettangoloTondo(-pz.L / 2, -pz.w / 2, pz.L, pz.w, pz.w / 2); ctx.fill(); ctx.stroke(); break;
      case "busto":
        rettangoloTondo(-8.5 * S, -pz.L / 2 - 3 * S, 17 * S, pz.L + 7 * S, 4 * S); ctx.fill(); ctx.stroke();
        for (let i = 0; i < 3 && !pz.liscio; i++) tondo((-3 + 3 * i) * S, -pz.L / 2 + 6 * S, 1.2 * S, "#555");
        break;
      case "bombola": rettangoloTondo(-2.6 * S, -9 * S, 5.2 * S, 18 * S, 2.4 * S); ctx.fill(); ctx.stroke(); break;
      case "testa":
        rettangoloTondo(-8.5 * S, -7.5 * S, 17 * S, 15 * S, 4 * S); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#0f2a1f"; rettangoloTondo(-6.8 * S, -3.8 * S, 13.6 * S, 7 * S, 2.6 * S); ctx.fill();
        ctx.strokeStyle = "#7dffd2"; ctx.lineWidth = 1.3 * S; ctx.beginPath();
        for (const ex of [-2.9, 2.9]) {
          ctx.moveTo((ex - 1.3) * S, -1.5 * S); ctx.lineTo((ex + 1.3) * S, 1.1 * S);
          ctx.moveTo((ex + 1.3) * S, -1.5 * S); ctx.lineTo((ex - 1.3) * S, 1.1 * S);
        }
        ctx.stroke(); break;
      case "capo":
        // La testa di un personaggio inventato: la faccia stordita e i capelli (o il cappello).
        ctx.beginPath(); ctx.arc(0, 0, 8 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = pz.capelli; ctx.beginPath(); ctx.arc(0, -1 * S, 8.4 * S, Math.PI * 1.08, Math.PI * 1.92); ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.lineWidth = 1.2 * S; ctx.beginPath();
        for (const ex of [-2.8, 2.8]) {
          ctx.moveTo((ex - 1.2) * S, 0.2 * S); ctx.lineTo((ex + 1.2) * S, 2.4 * S);
          ctx.moveTo((ex + 1.2) * S, 0.2 * S); ctx.lineTo((ex - 1.2) * S, 2.4 * S);
        }
        ctx.stroke(); break;
      case "pugno": ctx.beginPath(); ctx.arc(0, 0, 3.3 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); break;
      case "guanto":
        ctx.beginPath(); ctx.ellipse(0, 0, 4.6 * S, 3.9 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#f4f4f4"; ctx.fillRect(-6 * S, -2 * S, 2 * S, 4 * S); break;
      case "piede": rettangoloTondo(-4.2 * S, -2.6 * S, 8.4 * S, 4.8 * S, 1.8 * S); ctx.fill(); ctx.stroke(); break;
      case "spicchio": {
        // Un quarto di mela: polpa bianca, buccia nera sul bordo, due semi.
        const R = 17 * S;
        ctx.beginPath(); ctx.moveTo(-0.6 * R, 0); ctx.arc(-0.6 * R, 0, R, -Math.PI / 4, Math.PI / 4); ctx.closePath();
        ctx.fillStyle = "#ffffff"; ctx.fill();
        ctx.lineWidth = 1 * S; ctx.strokeStyle = "#d9cfbd"; ctx.stroke();
        ctx.beginPath(); ctx.arc(-0.6 * R, 0, R, -Math.PI / 4, Math.PI / 4); ctx.lineWidth = 2.6 * S; ctx.strokeStyle = "#111"; ctx.stroke();
        ctx.fillStyle = "#4a2e1a";
        for (const [x, y] of [[-0.12, -0.08], [-0.12, 0.08]]) { ctx.beginPath(); ctx.ellipse(x * R, y * R, 0.07 * R, 0.04 * R, 0, 0, Math.PI * 2); ctx.fill(); }
        break;
      }
      case "picciolo":
        ctx.strokeStyle = "#6b4423"; ctx.lineWidth = 1.8 * S; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(0, 3 * S); ctx.lineTo(1.6 * S, -4 * S); ctx.stroke();
        ctx.fillStyle = "#3f9a3a"; ctx.beginPath(); ctx.ellipse(5.5 * S, -3 * S, 4.6 * S, 2 * S, -0.45, 0, Math.PI * 2); ctx.fill();
        break;
      case "occhio":
        ctx.fillStyle = "#111"; ctx.beginPath(); ctx.ellipse(0, 0, 2.1 * S, 2.9 * S, 0, 0, Math.PI * 2); ctx.fill();
        tondo(0.6 * S, -1 * S, 0.7 * S, "#ffffff"); break;
      case "scarpa":
        ctx.beginPath(); ctx.ellipse(0, 0, 4.2 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 1.2 * S; ctx.stroke(); break;
      case "antenna":
        ctx.strokeStyle = pz.colore; ctx.lineWidth = 1.4 * S; ctx.beginPath(); ctx.moveTo(0, 4 * S); ctx.lineTo(0, -3 * S); ctx.stroke();
        tondo(0, -3.6 * S, 2.1 * S, "#ffcf3a"); break;
      default: tondo(0, 0, 1.7 * S, pz.colore); ctx.beginPath(); ctx.arc(0, 0, 1.7 * S, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
  }

  // --- Lo scenario della gravità ----------------------------------------
  // Sulla Luna la Terra nel cielo, le stelle e il suolo coi crateri; nello
  // Spazio un pianeta con gli anelli, stelle e sassi che fluttuano; su Giove
  // il pianeta a fasce con la macchia rossa e un suolo arancione. Solo nei
  // margini, sottile: la pagina resta leggibile.
  const STELLE = Array.from({ length: 36 }, (_, i) => ({ u: ((i * 73) % 97) / 97, v: ((i * 37) % 89) / 89, f: i * 0.7 }));
  const temaGravita = () => (verso < 0 ? "sottosopra" : moltG < 0.2 ? "spazio" : moltG < 0.7 ? "luna" : moltG > 1.3 ? "giove" : "terra");
  function disegnaScenario() {
    const tema = temaGravita();
    if (tema === "terra") return;
    const cieloA = testataBasso + 8, cieloB = pavimento - 40 * S;
    ctx.save();
    if (tema === "luna" || tema === "spazio") {
      for (const st of STELLE) {
        const a = 0.35 + 0.35 * Math.sin(passi * 0.05 + st.f);
        ctx.globalAlpha = a; stella(st.u * W, cieloA + st.v * (cieloB - cieloA), (1.2 + (st.f % 1)) * S, "#8e9ab0");
      }
      ctx.globalAlpha = 1;
    }
    const px = W - 80 * S, py = cieloA + 110 * S;
    if (tema === "luna") {
      // La Terra, con un'ombra sul lato in ombra.
      const r = 24 * S;
      ctx.save(); ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.clip();
      ctx.fillStyle = "#3f7fd6"; ctx.fillRect(px - r, py - r, 2 * r, 2 * r);
      ctx.fillStyle = "#5aa55a";
      for (const [dx, dy, rx, ry] of [[-8, -6, 9, 6], [7, 6, 8, 10], [10, -12, 5, 4]]) { ctx.beginPath(); ctx.ellipse(px + dx * S, py + dy * S, rx * S, ry * S, 0.4, 0, Math.PI * 2); ctx.fill(); }
      ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 2 * S;
      ctx.beginPath(); ctx.arc(px - 4 * S, py + 2 * S, 14 * S, 3.6, 4.6); ctx.stroke();
      const om = ctx.createLinearGradient(px - r, py, px + r, py);
      om.addColorStop(0.55, "rgba(10,15,30,0)"); om.addColorStop(1, "rgba(10,15,30,.55)");
      ctx.fillStyle = om; ctx.fillRect(px - r, py - r, 2 * r, 2 * r);
      ctx.restore();
      ctx.strokeStyle = "rgba(20,30,60,.5)"; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.stroke();
      suolo("#cfccc5", "#b3afa7");
    } else if (tema === "spazio") {
      const r = 20 * S;
      ctx.strokeStyle = "#e8c27a"; ctx.lineWidth = 3 * S;
      ctx.beginPath(); ctx.ellipse(px, py, r * 1.9, r * 0.5, -0.3, Math.PI, Math.PI * 2); ctx.stroke();
      const g = ctx.createRadialGradient(px - r * 0.4, py - r * 0.4, r * 0.2, px, py, r);
      g.addColorStop(0, "#e6a8f0"); g.addColorStop(1, "#8a4fb0");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.ellipse(px, py, r * 1.9, r * 0.5, -0.3, 0, Math.PI); ctx.stroke();
      // Qualche sasso che fluttua, e ogni tanto una cometa.
      for (let i = 0; i < 3; i++) {
        const x = ((passi * (0.25 + i * 0.1) + i * 400) % (W + 80)) - 40, y = cieloA + (0.2 + 0.25 * i) * (cieloB - cieloA);
        ctx.save(); ctx.translate(x, y); ctx.rotate(passi * 0.01 * (i + 1));
        ctx.fillStyle = "#9a948a"; ctx.beginPath();
        ctx.moveTo(-5 * S, -2 * S); ctx.lineTo(-1 * S, -5 * S); ctx.lineTo(5 * S, -3 * S); ctx.lineTo(4 * S, 3 * S); ctx.lineTo(-3 * S, 4 * S);
        ctx.closePath(); ctx.fill(); ctx.restore();
      }
      const ciclo = passi % 900;
      if (ciclo < 160) {
        const k = ciclo / 160, cx = -40 + k * (W + 80), cy = cieloA + 30 * S + k * 80 * S;
        const coda = ctx.createLinearGradient(cx, cy, cx - 70 * S, cy - 20 * S);
        coda.addColorStop(0, "rgba(140,200,255,.8)"); coda.addColorStop(1, "rgba(140,200,255,0)");
        ctx.strokeStyle = coda; ctx.lineWidth = 3 * S; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx - 70 * S, cy - 20 * S); ctx.stroke();
        tondo(cx, cy, 2.6 * S, "#ffffff");
      }
    } else if (tema === "giove") {
      const r = 32 * S;
      ctx.save(); ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.clip();
      const fasce = ["#e8d2b0", "#c98d5a", "#efe0c8", "#b9774a", "#e8d2b0", "#c98d5a", "#efe0c8"];
      fasce.forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(px - r, py - r + i * (2 * r / fasce.length), 2 * r, 2 * r / fasce.length + 1); });
      ctx.fillStyle = "#c4553a"; ctx.beginPath(); ctx.ellipse(px + 10 * S, py + 9 * S, 8 * S, 4.5 * S, 0, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
      ctx.strokeStyle = "rgba(90,50,20,.45)"; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.stroke();
      suolo("#d9a066", "#b9774a");
    }
    ctx.restore();
  }
  // Un suolo sottile appoggiato sulla striscia, coi crateri.
  function suolo(chiaro, scuro) {
    const alto = 9 * S;
    ctx.fillStyle = chiaro; ctx.beginPath(); ctx.moveTo(0, pavimento);
    for (let x = 0; x <= W + 30; x += 30) ctx.lineTo(x, pavimento - alto * (0.6 + 0.4 * Math.sin(x * 0.037)));
    ctx.lineTo(W, pavimento); ctx.closePath(); ctx.fill();
    ctx.fillStyle = scuro;
    for (let x = 40; x < W; x += 110) { ctx.beginPath(); ctx.ellipse(x, pavimento - alto * 0.35, 9 * S, 2.2 * S, 0, 0, Math.PI * 2); ctx.fill(); }
  }
  // Il casco a bolla, sulla Luna e nello Spazio.
  function casco(r) {
    ctx.fillStyle = "rgba(190,225,255,.18)"; ctx.strokeStyle = "rgba(120,160,200,.85)"; ctx.lineWidth = 1.4 * S;
    ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 1.4 * S;
    ctx.beginPath(); ctx.arc(0, 0, r * 0.78, Math.PI * 1.15, Math.PI * 1.45); ctx.stroke();
  }

  function disegna() {
    ctx.clearRect(0, 0, W, H);
    disegnaScenario();
    ctx.save();
    if (scossa > 0) ctx.translate(caso(-1, 1) * Math.min(4, scossa) * S, caso(-1, 1) * Math.min(4, scossa) * S);
    disegnaDanni();
    disegnaBordi();
    for (const m of macchie) {
      ctx.globalAlpha = Math.min(0.85, m.vita / 300); ctx.fillStyle = m.colore;
      ctx.beginPath(); ctx.ellipse(m.x, m.y, m.r, m.r * m.schiacciata, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    if (cumulo > 0.3 * S) {
      ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "rgba(70,100,135,.5)"; ctx.lineWidth = 1.2 * S; ctx.beginPath();
      ctx.moveTo(0, pavimento + 1);
      for (let x = 0; x <= W + 20; x += 20) ctx.lineTo(x, pavimento - cumulo * (0.7 + 0.3 * Math.sin(x * 0.05)));
      ctx.lineTo(W, pavimento + 1); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    if (uragano) disegnaUragano();
    disegnaFinale(false);
    for (const t of telefoni) if (t.stato !== "impugnato") disegnaTelefono(t);
    for (const pz of pezzi) disegnaPezzo(pz);
    for (const f of lottatori) disegnaCratere(f.cratere);
    disegnaScie();
    const ordine = lottatori.slice().sort((x, y) => (y.ko ? 1 : 0) - (x.ko ? 1 : 0));
    for (const f of ordine) {
      if (f.esploso) continue;
      disegnaLottatore(f);
    }
    for (const c of creature) disegnaCreatura(c);
    for (const t of telefoni) if (t.stato === "impugnato") disegnaTelefono(t);
    for (const a of arti) disegnaArto(a);
    for (const b of proiettili) disegnaProiettile(b);
    for (const z of fulmini) disegnaFulmine(z);
    // Le stelline di chi è stordito o al tappeto.
    for (const f of lottatori) {
      if (f.esploso || f.gelato > 0 || !(f.stordito > 0 || f.accecato > 0 || (f.ko > 0 && !f.inVolo))) continue;
      for (let i = 0; i < 3; i++) {
        const ang = passi * 0.12 + (i * Math.PI * 2) / 3;
        stella(f.p.testa.x + Math.cos(ang) * 11 * S, f.p.testa.y - 12 * S + Math.sin(ang) * 3.5 * S, 2.6 * S, "#ffd84a");
      }
    }
    for (const f of lottatori) {
      if (f.esploso) continue;
      if (f.tenuto && f.tenuto.tele !== undefined) (f.tenuto.magia ? disegnaLevitazione : disegnaTelecinesi)(f);
      if (f.azione === "barriera") disegnaBarriera(f);
      if (f.sfera) disegnaSferaGrande(f.sfera.x, f.sfera.y, f.sfera.r, COLORI_ANIME[f.tipo]);
      if (f.azione === "disco" && f.t < 30) disegnaDisco(f.p.manoA.x, f.p.manoA.y - 12 * S, (3 + 8 * f.t / 30) * S, COLORI_ANIME[f.tipo]);
      if (f.azione === "avvinghia") {
        // Lampeggia sempre più in fretta prima del botto.
        const c = f.p.collo, k = 0.5 + 0.5 * Math.sin(f.t * f.t * 0.012);
        const g = ctx.createRadialGradient(c.x, c.y, 2 * S, c.x, c.y, (26 + f.t * 0.25) * S);
        g.addColorStop(0, "rgba(255,255,255," + (0.5 + 0.4 * k) + ")"); g.addColorStop(0.5, "rgba(255,120,40," + 0.45 * k + ")"); g.addColorStop(1, "rgba(255,80,20,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(c.x, c.y, (26 + f.t * 0.25) * S, 0, Math.PI * 2); ctx.fill();
      }
    }
    for (const f of lottatori) {
      if (f.onda) disegnaOnda(f);
      else if (anime && f.azione === "onda" && f.t < 34 && !f.esploso) disegnaCaricaOnda(f);
    }
    for (const q of particelle) disegnaParticella(q);
    disegnaFinale(true);
    if (barreVita) disegnaBarre();
    ctx.restore();
    for (const s of scritte) {
      ctx.save();
      ctx.globalAlpha = Math.min(1, s.vita / 12);
      ctx.font = "800 " + Math.round((s.grande ? 17 : 12) * S) + "px Archivo, sans-serif";
      ctx.textAlign = "center";
      ctx.lineWidth = 3 * S; ctx.strokeStyle = s.grande ? "#141414" : "#fff";
      ctx.fillStyle = s.grande ? "#ffcf3a" : accento;
      ctx.strokeText(s.testo, s.x, s.y); ctx.fillText(s.testo, s.x, s.y);
      ctx.restore();
    }
  }

  // --- Il ciclo --------------------------------------------------------
  let ultimo = 0, riserva = 0, fotogramma = 0, richiesta = null;
  const PASSO_MS = 1000 / 60;

  function ciclo(adesso) {
    richiesta = null;
    if (document.hidden || fermo) return;
    if (!ultimo) ultimo = adesso;
    riserva += Math.min(100, adesso - ultimo) * ritmo;
    ultimo = adesso;
    let giri = 0;
    // Un colpo secco ferma l'azione per qualche fotogramma: si sente di più.
    if (fermoColpo > 0) { fermoColpo--; riserva = 0; }
    else {
      while (riserva >= PASSO_MS && giri < 4) { passo(); riserva -= PASSO_MS; giri++; }
      if (giri === 4) riserva = 0;
    }
    // Un disegno ogni due (30 fps); mentre se ne tiene uno in mano, tutti.
    if (presa.f || presa.tel || (fotogramma++ & 1) === 0) disegna();
    richiesta = requestAnimationFrame(ciclo);
  }
  function riparti() {
    if (fermo || richiesta || document.hidden) return;
    ultimo = 0; riserva = 0;
    richiesta = requestAnimationFrame(ciclo);
  }

  // Spegne il livello delle lotte: niente disegno, niente presa, niente
  // danni sulla striscia. Restano le notizie, l'orologio e i tasti.
  function spegni() {
    presa.f = null; presa.tel = null; appenaLanciato = false;
    radiceHtml("remove", "ring-trascina"); radiceHtml("remove", "ring-presa");
    ctx.clearRect(0, 0, W, H);
    if (tela.style) tela.style.display = "none";
    lottatori = []; telefoni = []; particelle = []; danni = []; scritte = []; evento = null;
    creature = []; nubi = []; finale = null;
    proiettili = []; pezzi = [];
    moltG = 1; ritmo = 1;
    if (barra && barra.classList) barra.classList.remove("ultimora-guasta", "ultimora-colpita");
    if (faccina && faccina.classList) faccina.classList.remove("stordito");
  }
  function accendi() {
    if (tela.style) tela.style.display = "";
    avvia();
    riparti();
  }

  if (fermo) { dimensiona(); spegni(); } else { avvia(); riparti(); }

  let attesa = null;
  window.addEventListener("resize", () => {
    clearTimeout(attesa);
    attesa = setTimeout(() => {
      tara();
      if (fermo) return;
      dimensiona(); rileva();
      for (const f of lottatori) f.cx = Math.max(20 * S, Math.min(W - 20 * S, f.cx));
    }, 150);
  });
  if (window.visualViewport && window.visualViewport.addEventListener) {
    window.visualViewport.addEventListener("resize", () => window.dispatchEvent && window.dispatchEvent(new Event("resize")));
  }
  window.addEventListener("load", () => { if (!fermo) rileva(); });
  window.addEventListener("mut:tema", () => { leggiColori(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) riparti(); });

  // --- Le scommesse ------------------------------------------------------
  // Gettoni finti, salvati solo in questo browser. Si punta su chi vince il
  // prossimo K.O.; la quota segue il punteggio (chi sta perdendo paga di più).
  let gettoni = 100, scommessa = null, esito = "";
  try {
    const g = parseInt(deposito.getItem("mut-ring-gettoni"), 10);
    if (Number.isFinite(g) && g >= 0 && g < 1e7) gettoni = g;
  } catch (errore) { /* si parte da 100 */ }
  const altroTipo = (tipo) => (tipo === "robot" ? "mela" : "robot");
  const NOMI = { robot: "il robot", mela: "la mela" }, SU = { robot: "sul robot", mela: "sulla mela" };
  function quota(tipo) {
    const mio = (punteggio[tipo] || 0) + 1, suo = (punteggio[altroTipo(tipo)] || 0) + 1;
    return Math.max(1.3, Math.min(4, Math.round((1 + suo / mio) * 10) / 10));
  }
  function salvaGettoni() { try { deposito.setItem("mut-ring-gettoni", String(gettoni)); } catch (errore) { /* pazienza */ } }
  function scommetti(tipo, importo) {
    importo = Math.floor(Number(importo));
    if (scommessa || !(tipo in NOMI) || !(importo > 0) || importo > gettoni) return false;
    gettoni -= importo;
    scommessa = { su: tipo, importo, quota: quota(tipo) };
    esito = "Puntati " + importo + " gettoni " + (stile ? "su " + nomeProprio(tipo) : SU[tipo]) + " (×" + scommessa.quota + "): si decide al prossimo K.O.";
    salvaGettoni(); aggiornaPannello();
    return true;
  }
  function risolviScommessa(vincitore) {
    if (!scommessa) { aggiornaPannello(); return; }
    const sc = scommessa;
    scommessa = null;
    if (vincitore === sc.su) {
      const vinti = Math.round(sc.importo * sc.quota);
      gettoni += vinti;
      esito = "Vinto! Ha vinto " + (stile ? nomeProprio(vincitore) : NOMI[vincitore]) + ": +" + vinti + " gettoni.";
      const f = lottatori.find((l) => l.tipo === vincitore);
      if (f) scrivi("+" + vinti, f.p.testa.x, f.p.testa.y - 30 * S, true);
    } else {
      esito = "Perso: ha vinto " + (stile ? nomeProprio(vincitore) : NOMI[vincitore]) + ". Meno " + sc.importo + " gettoni.";
    }
    if (gettoni <= 0) esito += " Gettoni finiti: puoi ricaricarli.";
    salvaGettoni(); aggiornaPannello();
  }

  // --- I comandi della tendina ------------------------------------------
  function assicuraAcceso() {
    if (!fermo) return;
    fermo = false;
    try { deposito.setItem("mut-ring", "on"); } catch (errore) { /* pazienza */ }
    aggiornaTastoGioca(); accendi();
  }
  // Le mosse dei personaggi nuovi: lo stile a cui appartengono e l'azione che fanno partire.
  const MOSSE_STILE = { trasforma: ["guerrieri", "trasforma"],
                        dardi: ["maghi", "raffica"], gelo: ["maghi", "gelo"], rimpicciolisci: ["maghi", "rimpicciolisci"], fulmine: ["maghi", "fulmine"],
                        levita: ["maghi", "levita"], scudo: ["maghi", "barriera"], raggio: ["maghi", "onda"], sparizione: ["maghi", "teletrasporto"],
                        "scatto-lama": ["lame", "scattoLama"], "lancio-lama": ["lame", "lancioLama"], duello: ["lame", "duello"] };
  const MOSSE_TENDINA = { sfera: "sfera", disco: "disco", lampo: "lampo", barriera: "barriera", autodistruzione: "avvinghia", telecinesi: "telecinesi" };
  const comandi = {
    metti(forma) {
      if (ARMI_PREMIO[forma] && !concesso("armi")) return false;
      assicuraAcceso();
      if (!lottatori.length) return;
      if (forma === "duo") {
        const m = lottatori.find((l) => l.tipo === "mela");
        if (m && !m.ko && !m.preso && !m.tenuto && !m.tel) { if (m.arma) lasciaArma(m); m.jet = 0; inizia(m, "estrai"); return; }
      }
      const cx = lottatori.reduce((t, l) => t + l.p.bacino.x, 0) / lottatori.length;
      const x = Math.max(40 * S, Math.min(W - 40 * S, cx + caso(-160, 160) * S));
      const t = faEntrare(forma, x, caso(-1, 1) * S);
      if (t.tipo === "bomba") t.miccia = 380;
    },
    gravita(v) {
      if (String(v) !== "1" && !concesso("meteo")) return false;
      if (v === "su") {
        // Sottosopra: la gravità tira verso il tetto.
        assicuraAcceso();
        verso = -1; gravitaScelta = 1; moltG = 1;
        for (const f of lottatori) { f.jet = 0; f.caos = 0; f.paracadute = 0; f.scalata = null; f.inVolo = true; f.ko = Math.max(f.ko, 30); }
        return;
      }
      v = Number(v);
      if (!(v > 0 && v <= 2)) return;
      if (verso < 0) for (const f of lottatori) { f.inVolo = true; f.ko = Math.max(f.ko, 30); }
      verso = 1;
      gravitaScelta = v;
      if (!evento || evento.nome !== "luna") moltG = v;
    },
    imprevisto(nome, acceso) {
      if (acceso && !concesso("meteo")) return false;
      if (acceso) assicuraAcceso();
      if (nome === "acquazzone") acquazzone = !!acceso;
      else if (nome === "natale") natale = !!acceso;
      else if (nome === "uragano") {
        uraganoFisso = !!acceso;
        uragano = acceso ? (uragano || { x: 100 * S, vx: 1.1 * S, t: 0 }) : null;
        if (!acceso && evento && evento.nome === "uragano") evento = null;
      } else if (nome === "rallenta") { rallentaFisso = !!acceso; ritmo = acceso ? 0.45 : 1; }
    },
    colpo(nome) {
      const gruppo = MOSSE_PREMIO[nome] ? "guerrieri" : nome.indexOf("esplodi-") === 0 ? "armi" : null;
      if (gruppo && !concesso(gruppo)) return false;
      assicuraAcceso();
      if (nome === "terremoto") evento = { nome, durata: 230 };
      else if (nome === "jet") { for (const f of lottatori) if (!f.ko && !f.preso && !f.tenuto && !f.esploso) decolla(f, Math.random() < 0.4); }
      else if (nome === "telefoni") daSpawnare = 7;
      else if (nome === "furia") { const f = lottatori[Math.floor(Math.random() * lottatori.length)]; if (f) f.furia = 560; }
      else if (nome in MOSSE_TENDINA) {
        if (stile !== "guerrieri") { comandi.stile("guerrieri"); aggiornaInterruttori(); }
        const pronti = lottatori.filter((f) => !f.ko && !f.preso && !f.tenuto && !f.esploso && !(f.accecato > 0));
        const f = pronti[Math.floor(Math.random() * pronti.length)];
        if (!f) return;
        const altro = lottatori.find((l) => l !== f);
        f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        f.ki = 100; f.scatto = 0;
        inizia(f, MOSSE_TENDINA[nome]);
      }
      else if (nome === "onda" || nome === "carica" || nome === "teletrasporto") {
        if (stile !== "guerrieri") { comandi.stile("guerrieri"); aggiornaInterruttori(); }
        const pronti = lottatori.filter((f) => !f.ko && !f.preso && !f.tenuto && !f.esploso);
        const f = pronti[Math.floor(Math.random() * pronti.length)];
        if (!f) return;
        const altro = lottatori.find((l) => l !== f);
        f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        if (nome === "onda") { f.ki = Math.max(f.ki, 45); f.jet = 0; inizia(f, "onda"); }
        else if (nome === "carica") { for (const l of pronti) { l.jet = 0; l.ki = Math.max(l.ki, 40); inizia(l, "carica"); } }
        else { f.ki = Math.max(f.ki, 15); teletrasporta(f, altro); }
      }
      else if (nome in MOSSE_STILE) {
        const [st, azione] = MOSSE_STILE[nome];
        if (stile !== st) { comandi.stile(st); aggiornaInterruttori(); }
        if (azione === "duello") { duello = 420; for (const f of lottatori) { f.jet = 0; f.pensa = Math.min(f.pensa, 4); if (f.lama && f.lama.lanciata) rientraLama(f); } return; }
        const pronti = lottatori.filter((f) => !f.ko && !f.preso && !f.tenuto && !f.esploso && !(f.accecato > 0) && !(f.gelato > 0) && (st !== "lame" || lamaPronta(f)));
        const f = pronti[Math.floor(Math.random() * pronti.length)];
        if (!f) return;
        const altro = lottatori.find((l) => l !== f);
        f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        f.ki = 100; f.scatto = 0; f.stordito = 0;
        if (st === "lame") f.jet = 0;
        if (azione === "teletrasporto") teletrasporta(f, altro);
        else inizia(f, azione);
      }
      else if (nome === "esplodi-robot" || nome === "esplodi-mela") {
        const tipo = nome.slice(8), f = lottatori.find((l) => l.tipo === tipo);
        if (f && !f.esploso) esplodiLottatore(f, lottatori.find((l) => l.tipo !== tipo));
      }
    },
    sorprese(acceso) { sorprese = !!acceso; },
    barre(acceso) {
      barreVita = !!acceso;
      try { deposito.setItem("mut-ring-barre", barreVita ? "on" : "off"); } catch (errore) { /* pazienza */ }
    },
    anime(acceso) { return comandi.stile(acceso ? "guerrieri" : (stile === "guerrieri" ? "" : stile)); },
    // Chi sono i due lottatori: "" i soliti, "guerrieri", "maghi", "lame".
    stile(nome) {
      nome = STILI.indexOf(nome) >= 0 ? nome : "";
      if (nome && !concesso("guerrieri")) return false;
      if (nome) assicuraAcceso();
      const prima = stile;
      stile = nome;
      anime = stile === "guerrieri" || stile === "maghi";
      try {
        deposito.setItem("mut-ring-stile", stile);
        deposito.setItem("mut-ring-anime", stile === "guerrieri" ? "on" : "off");
      } catch (errore) { /* pazienza */ }
      // Personaggi nuovi: escono i vecchi, entrano quelli dello stile scelto.
      if (stile !== prima) cambiaCorpi();
      for (const f of lottatori) if (anime) f.ki = Math.max(f.ki, 50);
      if (stile && !barreVita) barreVita = true;
      aggiornaInterruttori();
    },
    cruento(acceso) {
      cruento = !!acceso;
      try { deposito.setItem("mut-ring-cruento", cruento ? "on" : "off"); } catch (errore) { /* pazienza */ }
      if (!cruento) { macchie = []; particelle = particelle.filter((q) => q.tipo !== "goccia"); }
    },
    ricomincia() {
      assicuraAcceso();
      avvia();
      moltG = gravitaScelta; ritmo = rallentaFisso ? 0.45 : 1;
      if (uraganoFisso) uragano = { x: 100 * S, vx: 1.1 * S, t: 0 };
    },
    scommetti, ricarica() { if (!scommessa && gettoni < 10) { gettoni = 100; esito = "Gettoni ricaricati."; salvaGettoni(); aggiornaPannello(); } },
  };

  // --- La tendina (si apre dal tasto col guantone) -----------------------
  const pannello = mio.querySelector("[data-pannello]");
  const tastoOpzioni = mio.querySelector("[data-opzioni]");
  const dentroPannello = (sel) => (pannello && pannello.querySelectorAll ? Array.from(pannello.querySelectorAll(sel)) : []);
  function aggiornaPannello() {
    if (!pannello || !pannello.querySelector) return;
    const g = pannello.querySelector("[data-gettoni]");
    if (g) g.textContent = String(gettoni);
    for (const b of dentroPannello("[data-quota]")) b.textContent = "×" + quota(b.getAttribute("data-quota"));
    for (const b of dentroPannello("[data-punta]")) b.disabled = !!scommessa || gettoni <= 0;
    const e = pannello.querySelector("[data-esito]");
    if (e) e.textContent = esito || (gettoni > 0 ? "Punta su chi vince il prossimo K.O." : "Gettoni finiti.");
    const r = pannello.querySelector("[data-ricarica]");
    if (r) r.hidden = !!scommessa || gettoni >= 10;
  }
  function aggiornaInterruttori() {
    if (!pannello || !pannello.querySelector) return;
    const b = pannello.querySelector("[data-barre]"), a = pannello.querySelector("[data-anime]");
    if (b) b.setAttribute("aria-pressed", String(barreVita));
    if (a) a.setAttribute("aria-pressed", String(stile === "guerrieri"));
    for (const t of dentroPannello("[data-stile]")) t.setAttribute("aria-pressed", String(stile === t.getAttribute("data-stile")));
    // Si vedono solo le mosse dei personaggi scelti.
    for (const g of dentroPannello("[data-mosse]")) g.hidden = g.getAttribute("data-mosse") !== stile;
    // Sui tasti delle scommesse, i nomi di chi è in campo.
    for (const n of dentroPannello("[data-nome]")) {
      if (n.vero === undefined) n.vero = n.textContent;
      const lato = n.getAttribute("data-nome"), nuovo = stile ? (lato === "robot" ? "\uD83D\uDD35 " : "\uD83D\uDFE3 ") + nomeProprio(lato) : n.vero;
      if (n.textContent !== nuovo) n.textContent = nuovo;
    }
    const nota = pannello.querySelector("[data-mosse-nota]");
    if (nota) nota.hidden = !!stile;
  }
  function apriPannello(apri) {
    if (!pannello || !tastoOpzioni) return;
    pannello.classList.toggle("aperto", apri);
    tastoOpzioni.setAttribute("aria-expanded", apri ? "true" : "false");
    if (apri) aggiornaPannello();
  }
  if (pannello && tastoOpzioni) {
    pannello.hidden = false;
    tastoOpzioni.hidden = false;
    tastoOpzioni.addEventListener("click", () => apriPannello(!pannello.classList.contains("aperto")));
    const chiudi = pannello.querySelector("[data-chiudi]");
    if (chiudi) chiudi.addEventListener("click", () => { apriPannello(false); tastoOpzioni.focus(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && pannello.classList.contains("aperto")) { apriPannello(false); tastoOpzioni.focus(); } });
    for (const b of dentroPannello("[data-metti]")) b.addEventListener("click", () => comandi.metti(b.getAttribute("data-metti")));
    for (const b of dentroPannello("[data-colpo]")) b.addEventListener("click", () => comandi.colpo(b.getAttribute("data-colpo")));
    for (const b of dentroPannello("[data-imprevisto]")) {
      b.addEventListener("click", () => {
        const acceso = b.getAttribute("aria-pressed") !== "true";
        b.setAttribute("aria-pressed", acceso ? "true" : "false");
        if (comandi.imprevisto(b.getAttribute("data-imprevisto"), acceso) === false) b.setAttribute("aria-pressed", "false");
      });
    }
    const gravita = pannello.querySelector("[data-gravita]");
    if (gravita) gravita.addEventListener("change", () => { if (comandi.gravita(gravita.value) === false) gravita.value = "1"; });
    const sorp = pannello.querySelector("[data-sorprese]");
    if (sorp) sorp.addEventListener("click", () => { const a = sorp.getAttribute("aria-pressed") !== "true"; sorp.setAttribute("aria-pressed", String(a)); comandi.sorprese(a); });
    const crue = pannello.querySelector("[data-cruento]");
    if (crue) {
      crue.setAttribute("aria-pressed", String(cruento));
      crue.addEventListener("click", () => { const a = crue.getAttribute("aria-pressed") !== "true"; crue.setAttribute("aria-pressed", String(a)); comandi.cruento(a); });
    }
    for (const [sel, nome] of [["[data-barre]", "barre"], ["[data-anime]", "anime"]]) {
      const b = pannello.querySelector(sel);
      if (b) b.addEventListener("click", () => { const a = b.getAttribute("aria-pressed") !== "true"; comandi[nome](a); aggiornaInterruttori(); });
    }
    for (const b of dentroPannello("[data-stile]")) {
      b.addEventListener("click", () => { const s = b.getAttribute("data-stile"); comandi.stile(stile === s ? "" : s); aggiornaInterruttori(); });
    }
    aggiornaInterruttori();
    const ric = pannello.querySelector("[data-ricomincia]");
    if (ric) ric.addEventListener("click", () => comandi.ricomincia());
    const importo = pannello.querySelector("[data-importo]");
    for (const b of dentroPannello("[data-punta]")) {
      b.addEventListener("click", () => {
        let v = importo ? importo.value : "25";
        if (v === "tutto") v = gettoni;
        if (!scommetti(b.getAttribute("data-punta"), Math.min(Number(v), gettoni))) aggiornaPannello();
      });
    }
    const ricarica = pannello.querySelector("[data-ricarica]");
    if (ricarica) ricarica.addEventListener("click", () => comandi.ricarica());
    aggiornaPannello();
    segnaBloccati();
    if (premio && premio.ascolta) premio.ascolta(segnaBloccati);
  }
  // I tasti delle funzioni a pagamento portano il lucchetto finché Premium non
  // è attivo; se Premium viene tolto, quello che era acceso si spegne.
  function segnaBloccati() {
    if (!premio || !pannello) return;
    for (const b of dentroPannello("[data-metti], [data-colpo], [data-anime], [data-stile], [data-imprevisto]")) {
      const g = gruppoDi(b);
      b.classList.toggle("bloccato", !!g && !libero(g));
    }
    if (!libero("guerrieri") && stile) { comandi.stile(""); aggiornaInterruttori(); }
    if (!libero("meteo")) {
      for (const b of dentroPannello("[data-imprevisto]")) {
        if (b.getAttribute("aria-pressed") === "true") { b.setAttribute("aria-pressed", "false"); comandi.imprevisto(b.getAttribute("data-imprevisto"), false); }
      }
      const gravita = pannello.querySelector("[data-gravita]");
      if (gravita && gravita.value !== "1") { gravita.value = "1"; comandi.gravita("1"); }
      else if (verso < 0 || gravitaScelta !== 1) comandi.gravita("1");
    }
  }

  // Per i test nel browser: lo stato del ring, in sola lettura.
  window.__ring = {
    // Solo per i test: il conto dei K.O., una creatura, una nube.
    punti: (robot, mela) => { punteggio.robot = robot; punteggio.mela = mela; },
    creatura: (el, per, x) => { nuovaCreatura(el, x === undefined ? W / 2 : x, pavimento - 40 * S, per); },
    nube: (x, per) => { nubi.push({ x, y: pavimento - 30 * S, t: 0, per: per || null }); },
    // Solo per i test: un telefono lanciato a mano.
    lanciaTelefono: (x, y, vx, vy, forma) => { const t = nuovoTelefono(x, y, vx, vy, forma); t.stato = "volo"; t.cool = 0; t.armato = !!SPECIALI[t.tipo]; return telefoni.indexOf(t); },
    tempo: (secondi) => { tempo = Math.round(secondi * 60); },
    dai: (tipo, forma) => {
      const f = lottatori.find((l) => l.tipo === tipo);
      if (!f) return;
      const t = nuovoTelefono(f.p.manoA.x, f.p.manoA.y, 0, 0, forma);
      if (eArma(t)) { if (f.arma) lasciaArma(f); t.stato = "impugnato"; t.da = f; f.arma = t; f.colpiArma = forma === "pistola" ? 6 : 5; }
      else { t.stato = "portato"; t.da = f; f.tel = t; }
    },
    afferra: (tipo, mossa) => {
      const f = lottatori.find((l) => l.tipo === tipo), altro = lottatori.find((l) => l.tipo !== tipo);
      if (!f || !altro || altro.ko || altro.esploso) return false;
      inizia(f, "presa"); if (mossa) { f.mossaPresa = mossa; f.durata = DURATE_PRESA[mossa]; }
      f.t = 10; agguanta(f, altro); return true;
    },
    duo: () => { const m = lottatori.find((l) => l.tipo === "mela"); if (m && !m.ko) { m.pensa = 0; prossimoDuo = 0; inizia(m, "estrai"); } },
    esplodi: (tipo) => { const f = lottatori.find((l) => l.tipo === (tipo || "robot")), a = lottatori.find((l) => l.tipo !== (tipo || "robot")); if (f) esplodiLottatore(f, a); },
    paracadute: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) f.scendeApposta = 300; },
    comandi,
    // Solo per i test: fa partire una mossa a un lottatore, a piena energia.
    mossa: (tipo, azione) => {
      const f = lottatori.find((l) => l.tipo === tipo), a = lottatori.find((l) => l.tipo !== tipo);
      if (!f || !a) return false;
      f.dir = a.p.bacino.x >= f.p.bacino.x ? 1 : -1; f.ki = 100; f.pensa = 0;
      inizia(f, azione); return true;
    },
    incanta: (tipo, cosa) => {
      const f = lottatori.find((l) => l.tipo === tipo), a = lottatori.find((l) => l.tipo !== tipo);
      if (!f) return;
      if (cosa === "gelo") congela(f, a, f.p.collo.x, f.p.collo.y); else rimpicciolisci(f, a, f.p.collo.x, f.p.collo.y);
    },
    smembra: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) smembra(f, f.p.bacino.x, f.p.bacino.y); },
    mordi: () => { const f = lottatori.find((l) => l.tipo === "mela"); if (f) { const c = corpoMela(f.p); mordi(f, c.x + c.R, c.y); } },
    scatta: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo), a = lottatori.find((l) => l.tipo !== tipo); if (f && a) scatta(f, a, 30); },
    rush: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) { f.ki = Math.max(f.ki, 20); inizia(f, "rush"); } },
    taglia: () => { const f = lottatori.find((l) => l.tipo === "mela"); return !!(f && taglia(f, null)); },
    scoppia: (x, y, inPieno) => esplosione(x, y, 1.15, null, !!inPieno),
    ko: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo), a = lottatori.find((l) => l.tipo !== tipo); if (f && a) segnaKO(a, f); },
    danneggiaStriscia: (x, forza) => danneggiaStriscia(x, forza),
    rompiTelefono: (i, n) => { const t = telefoni[i]; if (!t) return null; for (let k = 0; k < n; k++) { t.crepe = Math.min(5, t.crepe + 1); rompiSchermo(t); } t.va = 0; t.a = 0; t.stato = "libero"; return { x: t.x, y: t.y, w: t.w, h: t.h }; },
    cervello: () => JSON.parse(JSON.stringify(cervello)),
    livello: (tipo) => livelloDi(tipo),
    impara: (tipo, mossa, esito, esp) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) impara(f, mossa, esito, esp); },
    decolla: (tipo, impazzito) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) decolla(f, !!impazzito); },
    avviaEvento: (nome) => { prossimoEvento = 1e9; if (nome === "luna") { moltG = 0.45; evento = { nome, durata: 620 }; } },
    danneggiaBordo: (lato, pos, forza) => danneggiaBordo(lato, pos, forza),
    stato: () => ({ telefoni: telefoni.map((t) => ({ x: t.x, y: t.y, stato: t.stato, tipo: t.tipo })),
    danniBordi: danniBordi.map((d) => d.lato), verso, barreVita, anime, stile, fulmini: fulmini.length, duello,
    tempo, pezzi: pezzi.length, proiettili: proiettili.length,
    sfereGrandi: proiettili.filter((b) => b.grande).length, dischi: proiettili.filter((b) => b.disco).length, gettoni, scommessa: scommessa ? Object.assign({}, scommessa) : null,
    arti: arti.length, macchie: macchie.length, acquazzone, natale, uragano: !!uragano, cruento, ritmo,
    particelleTipi: particelle.reduce((m, q) => { m[q.tipo] = (m[q.tipo] || 0) + 1; return m; }, {}),
    costume, particelle: particelle.length, danniStriscia: danni.length,
    campoRicerca: !!document.querySelector(".ricerca-grande input"), evento: evento ? evento.nome : null, moltG,
    lottatori: lottatori.map((f) => ({
    danni: f.danni, tel: !!f.tel, furia: f.furia, vola: f.jet > 0, caos: f.caos > 0,
    arma: f.arma ? f.arma.tipo : null, tiene: !!f.tiene, tenuto: !!f.tenuto, paracadute: !!f.paracadute,
    ballo: f.azione === "balla" ? f.ballo : null, esploso: !!f.esploso,
    segni: f.segni ? f.segni.length : 0, staccati: Object.keys(f.staccati || {}).filter((k) => f.staccati[k]),
    ki: f.ki, potenziato: f.potenziato > 0, onda: !!f.onda, vita: vitaVera(f),
    forma: f.potenziato > 0 ? f.forma : 0, gelato: f.gelato > 0, piccolo: f.piccolo > 0, scala: f.scala,
    lama: lamaPronta(f), lamaLanciata: !!(f.lama && f.lama.lanciata), soglia: f.soglia,
    morsi: f.morsi ? f.morsi.length : 0, tagliata: !!f.taglio, volo: !!(f.volo && f.jet > 0),
    accecato: f.accecato > 0, cratere: !!(f.cratere && !f.cratere.attesa), sfera: !!f.sfera,
    sollevato: !!(f.tenuto && f.tenuto.tele !== undefined),
    tipo: f.tipo, ko: f.ko, azione: f.azione, preso: !!f.preso,
    scalando: !!f.scalata, base: f.base, sopraUnElemento: !!f.supporto,
    testa: { x: f.p.testa.x, y: f.p.testa.y }, bacino: { x: f.p.bacino.x, y: f.p.bacino.y },
    collo: { x: f.p.collo.x, y: f.p.collo.y }, piede: { x: f.p.piedeA.x, y: f.p.piedeA.y },
    // Tutti i punti del corpo, per misurare le posture nei test.
    punti: Object.keys(f.p).reduce((m, n) => { m[n] = [f.p[n].x, f.p[n].y]; return m; }, {}),
    ginocchiaViste: (eMela(f) ? [f.p.piedeA, f.p.piedeD].map((pd) => {
      const dx = pd.x - f.p.bacino.x, dy = pd.y - f.p.bacino.y, lun = Math.hypot(dx, dy) || 1;
      let nx = -dy / lun; let ny = dx / lun; if (nx * f.dir < 0) { nx = -nx; ny = -ny; }
      return { x: f.p.bacino.x + dx / 2 + nx * 0.14 * lun, y: f.p.bacino.y + dy / 2 + ny * 0.14 * lun };
    }) : ginocchia(f)).map((g) => [g.x, g.y]),
    fuori: f.fuori || 0, tenuto: !!f.tenuto,
    dir: f.dir, forza: f.forza, stordito: f.stordito, rialzo: f.rialzo, inVolo: f.inVolo, fantasma: f.fantasma,
  })), punteggio: Object.assign({}, punteggio), pavimento, larghezza: W, altezza: H, scala: S,
    creature: creature.map((c) => ({ el: c.el, x: c.x, y: c.y, per: c.per, colpo: c.colpo })), nubi: nubi.length,
    finale: finale ? { tipo: finale.tipo, t: finale.t, uscito: !!finale.lampo, lancio: !!finale.perso } : null,
    ostacoli: ostacoli.length, riquadri: ostacoli.map((o) => [o.l, o.t, o.r, o.b].map(Math.round)) }) };
})();
