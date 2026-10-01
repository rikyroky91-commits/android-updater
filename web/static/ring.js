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

  const tela = document.querySelector("[data-ring]");
  const scorre = document.querySelector("[data-scorre]");
  const orologio = document.querySelector("[data-orologio]");
  const barra = document.querySelector(".ultimora-barra");

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
  try { scelta = window.localStorage.getItem("mut-ring"); } catch (errore) { /* niente memoria */ }
  let fermo = scelta === "off" || (scelta !== "on" && preferisceFermo);

  // --- I tasti della striscia: pausa delle notizie e lotte accese/spente ---
  const tastoPausa = document.querySelector("[data-pausa]");
  if (tastoPausa && barra) {
    tastoPausa.hidden = false;
    tastoPausa.addEventListener("click", () => {
      const inPausa = barra.classList.toggle("in-pausa");
      tastoPausa.setAttribute("aria-pressed", inPausa ? "true" : "false");
    });
  }
  const tastoGioca = document.querySelector("[data-gioca]");
  function aggiornaTastoGioca() {
    if (!tastoGioca) return;
    tastoGioca.setAttribute("aria-pressed", fermo ? "false" : "true");
    tastoGioca.title = fermo ? "Accendi le lotte" : "Spegni le lotte e lascia solo le notizie";
  }
  if (tastoGioca) {
    tastoGioca.hidden = false;
    aggiornaTastoGioca();
    tastoGioca.addEventListener("click", () => {
      fermo = !fermo;
      try { window.localStorage.setItem("mut-ring", fermo ? "off" : "on"); } catch (errore) { /* pazienza */ }
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
  let fermoColpo = 0, scossa = 0, moltG = 1, ritmo = 1, daSpawnare = 0;
  let prossimoEvento = 700, prossimoTelefono = 360;
  let costume = "nessuno", tavolozza = null;
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
  const RIGA_MIN = 24;
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
    if (testata && testata.getBoundingClientRect) aggiungi(testata.getBoundingClientRect());

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
  const ABBASSA_MELA = 12;
  // A riposo le mani della mela stanno ai FIANCHI del frutto, una davanti e
  // una dietro, non sulla faccia.
  const LATI_MELA = { gomitoA: 14, manoA: 18, gomitoD: -13, manoD: -17 };
  function scheletro(tipo) {
    if (tipo !== "mela") return SCHELETRO;
    const q = {};
    for (const nome in SCHELETRO) {
      q[nome] = SCHELETRO[nome].slice();
      if (nome in LATI_MELA) { q[nome][1] = LATI_MELA[nome]; }
    }
    return q;
  }

  function crea(tipo, x, dir, base) {
    if (base === undefined) base = pavimento;
    const f = {
      tipo, dir, cx: x, base, supporto: null, p: {}, aste: [],
      forza: 1, ko: 0, rialzo: 0, stordito: 0, danni: 0, soglia: Math.round(caso(3, 6)),
      azione: null, t: 0, durata: 0, colpito: false, pensa: caso(20, 60), meta: x,
      passo: 0, dolore: 0, preso: null, scalata: null, inVolo: false, botta: 0, fantasma: false,
      aggr: caso(0.75, 1.3), furbo: caso(0.6, 1.4), furia: 0, tel: null, prendiTel: null, polv: 0,
      jet: 0, volaY: 0, caos: 0, ix: 0, iy: 0, fiamma: 0,
    };
    const sch = scheletro(tipo);
    for (const nome in sch) {
      let [h, dx, r] = sch[nome];
      if (tipo === "mela" && SPALLA_MELA.indexOf(nome) >= 0) h -= ABBASSA_MELA;
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
    danni = [];
    scritte = []; telefoni = []; particelle = []; evento = null;
    moltG = 1; ritmo = 1; daSpawnare = 0; fermoColpo = 0; scossa = 0;
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
    }
    if (f.tipo === "mela") for (const nome of SPALLA_MELA) q[nome][0] -= ABBASSA_MELA;
    // In coordinate della finestra.
    const fuori = {};
    for (const nome in q) {
      fuori[nome] = [f.cx + q[nome][1] * f.dir * S, f.base - q[nome][0] * S - 2 * S];
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
                   solleva: 16, lancia: 26, para: 26, schiva: 30 };

  function inizia(f, azione, meta) {
    f.azione = azione; f.t = 0; f.durata = DURATE[azione]; f.colpito = false;
    if (meta !== undefined) f.meta = meta;
    if (azione === "salto") {
      for (const n in f.p) { f.p[n].oy = f.p[n].y + 6.5 * S; f.p[n].ox = f.p[n].x - f.dir * 1.6 * S; }
    }
    if (azione === "schiva") {
      // Un balzo all'indietro, fuori portata.
      for (const n in f.p) { f.p[n].oy = f.p[n].y + 5 * S; f.p[n].ox = f.p[n].x + f.dir * 2.6 * S; }
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
    const b = f.p.bacino;
    f.jet = Math.round(caso(260, 560)); f.azione = null; f.scalata = null; f.pensa = 6;
    f.volaY = Math.max(110, Math.min(pavimento - 90 * S, b.y - caso(70, 170) * S));
    f.caos = impazzito ? Math.round(caso(200, 340)) : 0;
    for (const n in f.p) f.p[n].oy = f.p[n].y + 3.5 * S;
    scintille(b.x, b.y + 22 * S, 8, "#ffb62e");
  }

  function pensaVolo(f, altro) {
    if (f.azione) {
      f.t++;
      if (f.t >= f.durata) { f.azione = null; f.pensa = Math.round(caso(2, 14)); }
      return;
    }
    if (f.caos > 0 || --f.pensa > 0) return;
    const ob = altro.p.bacino, mio = f.p.bacino;
    f.dir = ob.x >= mio.x ? 1 : -1;
    if (altro.ko || altro.preso) {
      // L'avversario è a terra: si scende a festeggiare.
      f.jet = Math.min(f.jet, 70); f.meta = altro.cx; f.volaY = Math.min(pavimento - 60 * S, ob.y - 30 * S);
      f.pensa = 20; return;
    }
    f.volaY = Math.max(100, Math.min(pavimento - 70 * S, ob.y - caso(-8, 28) * S));
    const dx = Math.abs(ob.x - mio.x) / S;
    if (dx > 34) { f.meta = ob.x - f.dir * 27 * S; f.pensa = Math.round(caso(5, 16)); return; }
    f.meta = f.cx;
    inizia(f, scegli([[30 * f.aggr, "pugno"], [22 * f.aggr, "diretto"], [16, "montante"],
                      [16 * f.aggr, "calcio"], [8 * f.furbo, "para"], [8 * f.furbo, "schiva"]]));
  }

  // La spinta del jetpack: tiene il corpo alla quota voluta (o lo sbatte
  // in giro, se impazzisce). Si applica a tutti i punti, come una forza.
  function applicaSpinta(f) {
    const g = GRAVITA * S * moltG, b = f.p.bacino;
    let spinta;
    if (f.caos > 0) {
      f.caos--;
      if (f.caos % 12 === 0) {
        const a = caso(0, Math.PI * 2), m = caso(1.8, 3.6) * S;
        f.ix = Math.cos(a) * m; f.iy = Math.sin(a) * m - 1.2 * S;
      }
      spinta = g * 0.92;
      for (const n in f.p) { f.p[n].x += f.ix * 0.28; f.p[n].y += f.iy * 0.28; }
      f.p.testa.x += f.ix * 0.12; f.p.testa.y += f.iy * 0.12;
      if (f.caos === 0) f.volaY = Math.max(110, Math.min(pavimento - 90 * S, b.y));
      if (passi % 3 === 0) fiammata(f, -f.iy, -f.ix);
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
    if (f.ko || f.stordito || f.preso || f.scalata || f.inVolo) return;
    if (f.jet > 0) { pensaVolo(f, altro); return; }
    if (f.azione) {
      f.t++;
      const vicino = Math.abs(altro.base - f.base) <= 18 * S &&
        Math.abs(altro.cx - f.cx) < 27 * S && !altro.ko;
      const arrivato = Math.abs(f.meta - f.cx) < 3 * S;
      if (f.azione === "lancia" && f.t === 11 && f.tel) lanciaTelefono(f, altro);
      if (f.t >= f.durata || (f.azione === "avanza" && (vicino || arrivato))) {
        if (f.azione === "avanza" && f.prendiTel) {
          const t = f.prendiTel; f.prendiTel = null;
          if (arrivato && t.stato === "libero" && Math.abs(t.x - f.cx) < 16 * S) {
            t.stato = "portato"; t.da = f; f.tel = t; inizia(f, "solleva"); return;
          }
        }
        if (f.azione === "solleva" && f.tel) { inizia(f, "lancia"); return; }
        if (f.azione === "avanza" && arrivato && f.dopo) {
          const piano = f.dopo; f.dopo = null; f.azione = null;
          if (raggiungibile(f, piano.o)) { iniziaScalata(f, piano.o, piano.lato); return; }
        }
        f.azione = null; f.pensa = caso(3, 22);
      }
      return;
    }
    if (--f.pensa > 0) return;
    f.dopo = null;
    if (altro.ko || altro.preso) { inizia(f, Math.random() < 0.7 ? "esulta" : "provoca"); return; }
    // Un telefono per terra a portata di mano? Si raccoglie e si lancia.
    if (!f.tel && Math.abs(altro.base - f.base) <= 18 * S) {
      const t = telefonoVicino(f);
      if (t && Math.random() < 0.5 * f.furbo) {
        f.dir = t.x >= f.cx ? 1 : -1; f.prendiTel = t; inizia(f, "avanza", t.x); return;
      }
    }
    // Ogni tanto si accende il jetpack e si va a lottare in aria.
    if (!f.tel && Math.random() < 0.07 * f.furbo) { decolla(f, Math.random() < 0.22); return; }
    // L'avversario sta per colpire: ci si para o si schiva.
    if (altro.azione && COLPI[altro.azione] && Math.abs(altro.cx - f.cx) < 34 * S &&
        Math.abs(altro.base - f.base) <= 18 * S && Math.random() < 0.3 * f.furbo) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      inizia(f, Math.random() < 0.55 ? "para" : "schiva"); return;
    }

    const dy = altro.base - f.base;
    if (Math.abs(dy) <= 18 * S) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      const distanza = Math.abs(altro.cx - f.cx) / S;
      if (distanza > 34) {
        const azione = scegli([[74 * f.aggr, "avanza"], [14, "provoca"], [12, "salto"]]);
        inizia(f, azione, altro.cx);
      } else if (distanza < 22) {
        inizia(f, scegli([[45, "indietro"], [25, "montante"], [30, "pugno"]]));
      } else {
        inizia(f, scegli([[28 * f.aggr, "pugno"], [20 * f.aggr, "diretto"], [14, "montante"],
                          [22 * f.aggr, "calcio"], [8 / f.aggr, "indietro"], [8, "salto"]]));
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

  // Un muro sulla strada (un elemento più alto di un gradino): ci si sale.
  function ostacoloDavanti(f) {
    for (const o of ostacoli) {
      if (o === f.supporto) continue;
      const davanti = f.dir > 0 ? (o.l >= f.cx && o.l <= f.cx + 14 * S)
                                : (o.r <= f.cx && o.r >= f.cx - 14 * S);
      if (davanti && o.t < f.base - 8 * S && o.b > f.base - 30 * S && raggiungibile(f, o)) return o;
    }
    return null;
  }

  // --- I colpi ---------------------------------------------------------
  const COLPI = { pugno: ["manoA", 7, 13, 3.2], diretto: ["manoD", 8, 15, 3.8],
                  montante: ["manoA", 9, 17, 4.4], calcio: ["piedeA", 10, 19, 4.8] };
  const SUONI = ["POW!", "BAM!", "SBAM!", "TUMP!", "ZOT!", "PAF!"];

  function controllaColpo(f, altro) {
    const regola = COLPI[f.azione];
    if (!regola || f.colpito || altro.ko || altro.preso) return;
    const [arto, da, a, forza] = regola;
    if (f.t < da || f.t > a) return;
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

  function scrivi(testo, x, y, grande) {
    scritte.push({ testo, x: Math.max(50, Math.min(W - 50, x)), y: Math.max(26, y), vita: grande ? 70 : 26, grande });
  }

  const SUONI_TEL = ["DRIIN!", "CRACK!", "BIP!", "SPLASH!", "NOTIFICA!", "TRIIN!"];

  function colpisci(f, altro, forza, x, y, suono) {
    // Una parata di fronte ferma quasi tutto, ma il colpo si sente.
    if (altro.azione === "para" && altro.dir === -f.dir) {
      scrivi("PARATO!", x, y - 6 * S, false);
      scintille(x, y, 5, "#bfe9ff");
      for (const n in altro.p) altro.p[n].ox -= f.dir * forza * 0.12 * S;
      fermoColpo = 2;
      return;
    }
    if (f.furia > 0) forza *= 1.5;
    if (altro.tel) lasciaCadere(altro);
    if (altro.jet > 0 && Math.random() < 0.6) { altro.jet = 0; altro.caos = 0; }
    altro.danni++;
    const ko = altro.danni >= altro.soglia;
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
    if (ko) {
      altro.ko = Math.round(caso(110, 170)); altro.danni = 0; altro.soglia = Math.round(caso(3, 6));
      if (f.tipo) punteggio[f.tipo]++;
      // Ogni round un carattere nuovo: più aggressivo o più cauto.
      for (const l of lottatori) { l.aggr = caso(0.75, 1.3); l.furbo = caso(0.6, 1.4); }
      scrivi("K.O.!  " + punteggio.robot + "–" + punteggio.mela, altro.p.bacino.x, altro.base - 72 * S, true);
    } else {
      altro.stordito = 12;
    }
  }

  // --- La presa col mouse o col dito -----------------------------------
  const presa = { f: null, tel: null, punto: null, x: 0, y: 0, mosso: false };
  let appenaLanciato = false;

  let raggioPresa = 16;   // in unità S: il dito è più grosso del mouse
  function chiTrovo(x, y) {
    let migliore = null, distanza = raggioPresa * S;
    for (const f of lottatori) {
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
      if (t.stato === "portato") continue;
      const d = Math.hypot(t.x - x, t.y - y) - t.r * 0.6;
      if (d < d0) { d0 = d; migliore = t; }
    }
    return migliore;
  }
  const qualcosaSotto = (x, y) => !!(chiTrovo(x, y) || telefonoSotto(x, y));

  function prendi(evento) {
    if (fermo || (evento.button !== undefined && evento.button > 0)) return;
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
      t.stato = "volo"; t.protetto = 0; t.da = null; t.cool = 6; t.va = caso(-0.3, 0.3);
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
    }
    radiceHtml("remove", "ring-trascina");
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

  function urta(f, pt) {
    const r = pt.r;
    let urto = 0;
    const prima = Math.hypot(pt.x - pt.ox, pt.y - pt.oy);
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
  function aggiornaParticelle() {
    for (const q of particelle) {
      q.x += q.vx; q.y += q.vy; q.vita--;
      if (q.tipo === "scintilla") { q.vx *= 0.93; q.vy = q.vy * 0.93 + 0.12 * S; }
      else if (q.tipo === "polvere") { q.vx *= 0.96; q.vy *= 0.96; }
      else if (q.tipo === "fiamma") { q.vx *= 0.94; q.vy *= 0.97; }
      else { q.vy += 0.3 * S * moltG; q.rot += 0.3; if (q.y > pavimento) { q.y = pavimento; q.vy *= -0.4; q.vx *= 0.7; } }
    }
    particelle = particelle.filter((q) => q.vita > 0);
  }

  // --- I telefoni che girano per la pagina ------------------------------
  const TIPI_TEL = { classico: [8, 15], grande: [9.5, 19], pieghevole: [12, 13] };
  const COLORI_TEL = ["#2b2f3a", "#c9ced8", "#1f6fd1", "#d1493a", "#2e9e6b", "#8a63d2"];

  function nuovoTelefono(x, y, vx, vy) {
    const tipo = scegli([[50, "classico"], [30, "grande"], [20, "pieghevole"]]);
    const [w, h] = TIPI_TEL[tipo];
    telefoni.push({ x, y, ox: x - vx, oy: y - vy, a: caso(0, 6.28), va: caso(-0.15, 0.15), tipo,
                    w: w * S, h: h * S, r: 6.5 * S, stato: "libero", da: null, protetto: 0, cool: 0,
                    ultimo: null, crepe: 0, colore: COLORI_TEL[Math.floor(Math.random() * COLORI_TEL.length)] });
    if (telefoni.length > 6) {
      const vecchio = telefoni.findIndex((t) => t.stato === "libero");
      if (vecchio >= 0) telefoni.splice(vecchio, 1);
    }
    return telefoni[telefoni.length - 1];
  }

  function velocitaTel(t) { return Math.hypot(t.x - t.ox, t.y - t.oy); }

  function telefonoVicino(f) {
    let migliore = null, d0 = 260 * S;
    for (const t of telefoni) {
      if (t.stato !== "libero" || velocitaTel(t) > 2 * S) continue;
      if (Math.abs(t.y - (f.base - 6 * S)) > 22 * S) continue;
      const d = Math.abs(t.x - f.cx);
      if (d < d0) { d0 = d; migliore = t; }
    }
    return migliore;
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
    t.stato = "volo"; t.protetto = 14; t.da = f;
    const T = caso(32, 44);
    const tx = altro.p.collo.x + caso(-7, 7) * S, ty = altro.p.collo.y + caso(-7, 7) * S;
    let vx = (tx - t.x) / T, vy = (ty - t.y) / T - 0.5 * GRAVITA * S * moltG * T;
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
      if (t.x < o.l - r || t.x > o.r + r || t.y < o.t - r || t.y > o.b + r) continue;
      if (t.oy <= o.t - r + 1) { t.y = o.t - r; rim(vx * 0.86, vy > 1.1 * S ? -vy * 0.45 : 0, Math.abs(vy)); }
      else if (t.oy >= o.b + r - 1) { t.y = o.b + r; rim(vx, Math.abs(vy) * 0.3, Math.abs(vy)); }
      else if (t.ox <= o.l - r + 1) { t.x = o.l - r; rim(-Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
      else if (t.ox >= o.r + r - 1) { t.x = o.r + r; rim(Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    }
    if (t.x < r) { t.x = r; rim(Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    if (t.x > W - r) { t.x = W - r; rim(-Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    if (t.y < r) { t.y = r; rim(vx, Math.abs(vy) * 0.3, 0); }
    return urto;
  }

  function aggiornaTelefoni() {
    for (const t of telefoni) {
      if (t.protetto > 0) t.protetto--;
      if (t.cool > 0) t.cool--;
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
        t.x = t.ox = m.x + f.dir * 0.5 * S; t.y = t.oy = m.y - 5 * S; t.a = f.dir * 0.2;
        continue;
      }
      let vx = (t.x - t.ox) * 0.995, vy = (t.y - t.oy) * 0.995;
      const v = Math.hypot(vx, vy), lim = VELOCITA_MAX * S * 1.1;
      if (v > lim) { vx *= lim / v; vy *= lim / v; }
      t.ox = t.x; t.oy = t.y;
      t.x += vx; t.y += vy + GRAVITA * S * moltG;
      t.a += t.va;
      const urto = rimbalzaTel(t, vx, vy);
      if (urto > 13.5 * S && t.y > pavimento - t.r - 1) danneggiaStriscia(t.x, Math.min(1, urto / (VELOCITA_MAX * S)));
      if (urto > 4 * S) {
        polvere(t.x, t.y + t.r, 2);
        if (urto > 8 * S && t.crepe < 4) { t.crepe++; schegge(t.x, t.y, 4, "#cfe9ff"); scrivi(Math.random() < 0.5 ? "CRACK!" : "CLONK!", t.x, t.y - 14 * S, false); }
      }
      if (t.stato === "volo" && velocitaTel(t) < 1.2 * S && t.y > pavimento - t.r - 2) { t.stato = "libero"; t.da = null; }
      // Un telefono veloce che tocca un lottatore gli fa male.
      if (t.stato === "volo" || velocitaTel(t) > 6 * S) {
        for (const f of lottatori) {
          if (f.ko || f.preso || t.cool > 0 || (t.da === f && t.protetto > 0)) continue;
          if (t.ultimo === f && t.cool > 0) continue;
          for (const n of ["testa", "collo", "bacino"]) {
            const b = f.p[n];
            if (Math.hypot(t.x - b.x, t.y - b.y) < b.r + t.r * 0.9) {
              const forza = Math.max(3, Math.min(6.5, velocitaTel(t) / (2.2 * S)));
              const att = t.da && t.da !== f ? t.da : { dir: Math.sign(t.x - t.ox) || 1, tipo: null, furia: 0 };
              colpisci(att, f, forza, t.x, t.y, SUONI_TEL[Math.floor(Math.random() * SUONI_TEL.length)]);
              schegge(t.x, t.y, 6, t.colore);
              t.ox = t.x + (t.x - t.ox) * 0.3; t.oy = t.y - 2 * S; t.va = caso(-0.4, 0.4);
              t.cool = 20; t.ultimo = f; t.crepe = Math.min(5, t.crepe + 1);
              break;
            }
          }
        }
      }
    }
  }

  // --- Eventi a sorpresa -----------------------------------------------
  // Gli eventi NON si annunciano con scritte sulla pagina (01/10/2026, su
  // richiesta: toglievano pulizia al sito): si vedono da quello che succede.

  function avviaEvento() {
    const quale = scegli([[3, "luna"], [3, "furia"], [3, "pioggia"], [2, "rallenta"], [2, "terremoto"], [3, "jet"]]);
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
    moltG = 1; ritmo = 1; evento = null;
  }

  function aggiornaEventi() {
    if (fermo) return;
    if (--prossimoEvento <= 0) { avviaEvento(); prossimoEvento = Math.round(caso(1500, 2700)); }
    if (--prossimoTelefono <= 0) {
      if (telefoni.length < 4) nuovoTelefono(caso(60, W - 60), -16 * S, caso(-1.5, 1.5) * S, 0);
      prossimoTelefono = Math.round(caso(420, 1100));
    }
    if (daSpawnare > 0 && passi % 14 === 0) { daSpawnare--; nuovoTelefono(caso(60, W - 60), -16 * S, caso(-2, 2) * S, 0); }
    if (evento) {
      if (evento.nome === "terremoto" && passi % 6 === 0) {
        scossa = 4;
        for (const f of lottatori) for (const n in f.p) { f.p[n].ox += caso(-1.4, 1.4) * S; f.p[n].oy += caso(0, 1.6) * S; }
        for (const t of telefoni) if (t.stato === "libero") { t.oy += caso(1, 3) * S; t.ox += caso(-2, 2) * S; }
      }
      if (--evento.durata <= 0) fineEvento();
    }
    for (const f of lottatori) if (f.furia > 0) f.furia--;
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
  const VITA_DANNO = 2700;
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
    for (const d of danni) if (d.eta < 300 || (Math.abs(d.x - x) < 26 * S && d.eta < 400)) return;
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
    const barra = document.querySelector && document.querySelector(".ultimora-barra");
    if (barra && barra.classList) {
      barra.classList.remove("ultimora-colpita"); void barra.offsetWidth;
      barra.classList.add("ultimora-colpita", "ultimora-guasta");
    }
    scrivi(buco ? "CRASH!" : "CRACK!", x, pavimento - 16 * S, true);
  }
  function aggiornaDanni() {
    for (const d of danni) {
      d.eta++;
      if (d.buco && d.eta % 22 === 0 && d.eta < VITA_DANNO - 700) scintille(d.x + caso(-8, 8) * S, pavimento + 14 * S, 3, "#8ff0ff");
      if (d.buco && d.eta % 40 === 0) polvere(d.x, pavimento + 8 * S, 1);
    }
    danni = danni.filter((d) => d.eta < VITA_DANNO);
    if (!danni.length) {
      const barra = document.querySelector && document.querySelector(".ultimora-barra");
      if (barra && barra.classList) barra.classList.remove("ultimora-guasta");
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
    passi++;
    if (passi % 45 === 0) rileva();
    const [a, b] = lottatori;

    for (const [f, altro] of [[a, b], [b, a]]) {
      if (f.tel && (f.ko > 0 || f.stordito || f.preso || f.dolore)) lasciaCadere(f);
      if (f.polv > 0) f.polv--;
      if (f.preso) { f.forza = 0; continue; }
      if (f.ko > 0) {
        f.forza = 0;
        // Da lanciato, il conto alla rovescia parte solo quando si è fermato.
        const v = Math.hypot(f.p.bacino.x - f.p.bacino.ox, f.p.bacino.y - f.p.bacino.oy);
        if (!f.inVolo || v < 1.2 * S) {
          if (--f.ko === 0) { f.rialzo = 50; f.inVolo = false; f.cx = f.p.bacino.x; }
        }
      } else if (f.rialzo > 0) { f.forza = 1 - f.rialzo / 50; f.rialzo--; }
      else if (f.stordito > 0) { f.forza = 0.22; f.stordito--; }
      else f.forza = 1;
      if (f.dolore > 0) f.dolore--;
      if (f.botta > 0) f.botta--;

      if (f.ko > 0 || f.preso) { f.jet = 0; f.caos = 0; }
      if (f.caos > 0) f.forza = Math.min(f.forza, 0.35);
      if (!f.scalata) {
        const [y, chi] = appoggio(f);
        f.base = y; f.supporto = chi;
      }
      // In volo la «base» è il corpo stesso: il busto resta dritto da solo.
      if (f.jet > 0) { f.base = f.p.bacino.y + 30 * S; f.supporto = null; }
      pensa(f, altro);

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
        f.cx += Math.max(-2.2 * S, Math.min(2.2 * S, (f.meta - f.cx) * 0.08));
        f.passo += 0.12;
      } else if (f.azione === "avanza") {
        const davanti = ostacoloDavanti(f);
        if (davanti) iniziaScalata(f, davanti, f.dir > 0 ? -1 : 1);
        else {
          const verso = Math.sign(f.meta - f.cx) || f.dir;
          f.dir = verso;
          f.cx += verso * (Math.abs(f.meta - f.cx) > 220 * S ? 1.6 : 0.95) * S;
          f.passo += 0.28;
        }
      } else if (f.azione === "indietro") { f.cx -= f.dir * 1.0 * S; f.passo += 0.3; }
      else f.passo += 0.08;

      if (!f.scalata) {
        f.cx += (f.p.bacino.x - f.cx) * (f.forza < 1 ? 0.5 : 0.06);
        f.cx = Math.max(20 * S, Math.min(W - 20 * S, f.cx));
      }
    }
    // Non passarsi attraverso, se sono allo stesso livello.
    if (!a.ko && !b.ko && !a.preso && !b.preso && Math.abs(a.base - b.base) < 10 * S) {
      const d = b.cx - a.cx, minimo = 22 * S;
      if (Math.abs(d) < minimo) {
        const s = d >= 0 ? 1 : -1, sposta = (minimo - Math.abs(d)) / 2;
        a.cx -= s * sposta; b.cx += s * sposta;
      }
    }

    for (const f of lottatori) {
      // Muscoli.
      if (f.forza > 0) {
        const piede = Math.max(f.p.piedeA.y, f.p.piedeD.y);
        const inAria = !f.scalata && f.base - piede > 30 * S;
        let q;
        if (f.scalata) q = posaScalata(f);
        else if (inAria) {
          // Cadendo da un bordo i muscoli tengono solo la forma del corpo:
          // la discesa la fa la gravità, non un muscolo che tira giù.
          const vera = f.base; f.base = f.p.bacino.y + 30 * S; q = posa(f); f.base = vera;
        } else q = posa(f);
        const scatto = f.azione && COLPI[f.azione] ? 0.55 : 0.3;
        const intensita = f.scalata ? 1.3 : (inAria ? 0.35 : 1);
        for (const nome in q) {
          const pt = f.p[nome], [tx, ty] = q[nome];
          const k = TIRO[nome] * f.forza * intensita *
            (COLPI[f.azione] && (nome === COLPI[f.azione][0]) ? 1.6 : 1);
          const mx = (tx - pt.x) * k, my = (ty - pt.y) * k;
          pt.x += mx; pt.y += my;
          pt.ox += mx * (1 - scatto); pt.oy += my * (1 - scatto);
        }
      }
      // Tenuto in mano: il punto preso segue il puntatore, il resto penzola.
      if (f.preso) {
        const pt = f.p[f.preso];
        pt.ox = pt.x; pt.oy = pt.y;
        pt.x += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, presa.x - pt.x));
        pt.y += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, presa.y - pt.y));
      }
      // In volo si passa attraverso il testo e i campi (come un oggetto
      // sollevato): urtandoli punto per punto il corpo si deformava. Restano
      // solidi il pavimento (la striscia) e i bordi della finestra.
      if (f.jet > 0 && !f.preso) { f.fantasma = true; applicaSpinta(f); } else f.fiamma = 0;
      // Verlet.
      for (const n in f.p) {
        const pt = f.p[n];
        if (f.preso === n) continue;
        let vx = (pt.x - pt.ox) * 0.985, vy = (pt.y - pt.oy) * 0.985;
        const v = Math.hypot(vx, vy), lim = VELOCITA_MAX * S;
        if (v > lim) { vx *= lim / v; vy *= lim / v; }
        pt.ox = pt.x; pt.oy = pt.y;
        pt.x += vx; pt.y += vy + GRAVITA * S * moltG;
      }
      // Vincoli: aste, elementi della pagina, pavimento, bordi.
      let urto = 0;
      for (let giro = 0; giro < 5; giro++) {
        for (const [p1, p2, L] of f.aste) {
          const dx = p2.x - p1.x, dy = p2.y - p1.y;
          const d = Math.hypot(dx, dy) || 0.001;
          const c = (d - L) / d * 0.5;
          const fermo1 = f.preso && f.p[f.preso] === p1, fermo2 = f.preso && f.p[f.preso] === p2;
          if (fermo1) { p2.x -= dx * c * 2; p2.y -= dy * c * 2; }
          else if (fermo2) { p1.x += dx * c * 2; p1.y += dy * c * 2; }
          else { p1.x += dx * c; p1.y += dy * c; p2.x -= dx * c; p2.y -= dy * c; }
        }
        for (const n in f.p) {
          const pt = f.p[n];
          if (f.preso === n) continue;
          if (!f.fantasma) urto = Math.max(urto, urta(f, pt));
          if (pt.y > pavimento - pt.r) {
            const caduta = pt.y - pt.oy;
            if (caduta > 11.5 * S) danneggiaStriscia(pt.x, Math.min(1, caduta / (VELOCITA_MAX * S)));
            urto = Math.max(urto, Math.hypot(pt.x - pt.ox, pt.y - pt.oy));
            pt.y = pavimento - pt.r;
            if (pt.oy < pt.y) pt.oy = pt.y;
            pt.ox += (pt.x - pt.ox) * 0.3;
          }
          if (pt.y < pt.r) { pt.y = pt.r; pt.oy = pt.y; }
          if (pt.x < pt.r + 2) { pt.x = pt.r + 2; pt.ox = pt.x + (pt.x - pt.ox) * 0.4; }
          if (pt.x > W - pt.r - 2) { pt.x = W - pt.r - 2; pt.ox = pt.x + (pt.x - pt.ox) * 0.4; }
        }
      }
      if (f.fantasma && !f.preso && !dentroQualcosa(f)) f.fantasma = false;
      // Uno schianto dopo un lancio si sente.
      if (urto > 6 * S && !f.polv) { polvere(f.p.piedeA.x, f.base - 1, urto > 11 * S ? 6 : 3); f.polv = 14; }
      if (f.inVolo && urto > 9 * S && !f.botta) {
        scrivi(urto > 15 * S ? "SPLAT!" : "BONK!", f.p.bacino.x, f.p.bacino.y - 20 * S, false);
        f.botta = 30;
      }
    }
    controllaColpo(a, b); controllaColpo(b, a);
    aggiornaTelefoni(); aggiornaParticelle(); aggiornaEventi(); aggiornaDanni();
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
      if (f.preso || !(f.supporto || f.scalata)) continue;
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
    // Arto lontano e gamba lontana.
    arto(p.bacino, p.ginocchioD, p.piedeD, 5 * S, scuro);
    tondo(p.ginocchioD.x, p.ginocchioD.y, 2.8 * S, mani);
    arto(p.collo, p.gomitoD, p.manoD, 4.4 * S, scuro);
    tondo(p.gomitoD.x, p.gomitoD.y, 2.4 * S, mani);
    guanto(p.gomitoD, p.manoD, "#b92b22", 3.9 * S);
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
    ctx.restore();
    // Gamba e braccio vicini.
    arto(p.bacino, p.ginocchioA, p.piedeA, 5 * S, verde);
    tondo(p.ginocchioA.x, p.ginocchioA.y, 2.8 * S, scuro);
    for (const piede of [p.piedeD, p.piedeA]) {
      ctx.fillStyle = mani; rettangoloTondo(piede.x - 4.2 * S, piede.y - 2.6 * S, 8.4 * S, 4.8 * S, 1.8 * S); ctx.fill();
      ctx.fillStyle = scuro; ctx.fillRect(piede.x - 4 * S + (f.dir > 0 ? 0 : 6.2 * S), piede.y + 1.1 * S, 1.8 * S, 1.2 * S);
    }
    // Testa, con antenna a molla.
    const angT = Math.atan2(p.testa.y - p.collo.y, p.testa.x - p.collo.x) + Math.PI / 2;
    ctx.save(); ctx.translate(p.testa.x, p.testa.y); ctx.rotate(angT);
    const hatAlto = costume === "cuoco" || costume === "mago";
    if (!hatAlto && costume !== "astronauta") {
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
                    f.azione === "calcio" || f.azione === "lancia";
    const festa = f.azione === "esulta" || f.azione === "provoca";
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
    costumeTesta(f, scuro);
    ctx.restore();
    arto(p.collo, p.gomitoA, p.manoA, 4.4 * S, verde);
    tondo(p.gomitoA.x, p.gomitoA.y, 2.4 * S, scuro);
    guanto(p.gomitoA, p.manoA, "#e03a2f", 4.2 * S);
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
    } else if (f.azione === "pugno" || f.azione === "diretto" || f.azione === "montante" || f.azione === "calcio" || f.azione === "lancia") {
      ctx.ellipse(x, y + 0.04 * R, 0.2 * R, 0.17 * R, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#ff7a8a"; ctx.beginPath();
      ctx.ellipse(x, y + 0.1 * R, 0.12 * R, 0.07 * R, 0, 0, Math.PI * 2); ctx.fill();
    } else if (f.azione === "esulta") {
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

  function disegnaMela(f) {
    const p = f.p, nero = "#111";
    // Gambe senza incroci: il ginocchio si piega sempre verso la faccia,
    // qualunque cosa faccia la fisica (prima le gambe si intrecciavano).
    for (const piede of [p.piedeD, p.piedeA]) {
      const dx = piede.x - p.bacino.x, dy = piede.y - p.bacino.y, lun = Math.hypot(dx, dy) || 1;
      let nx = -dy / lun, ny = dx / lun;
      if (nx * f.dir < 0) { nx = -nx; ny = -ny; }
      const ginocchio = { x: p.bacino.x + dx / 2 + nx * 0.14 * lun, y: p.bacino.y + dy / 2 + ny * 0.14 * lun };
      arto(p.bacino, ginocchio, piede, 3.2 * S, nero);
      ctx.fillStyle = "#f7f7f7"; ctx.beginPath();
      ctx.ellipse(piede.x + f.dir * 1.5 * S, piede.y - 0.5 * S, 4.2 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = nero; ctx.lineWidth = 1.2 * S; ctx.stroke();
    }
    const spalla = { x: p.collo.x * 0.4 + p.bacino.x * 0.6, y: p.collo.y * 0.4 + p.bacino.y * 0.6 };
    zaino(f, 16 * S);
    // Le braccia partono dai FIANCHI del frutto, non dal centro: così non
    // attraversano la faccia.
    const tx = p.bacino.x - p.collo.x, ty = p.bacino.y - p.collo.y, tl = Math.hypot(tx, ty) || 1;
    let qx = -ty / tl, qy = tx / tl;
    if (qx * f.dir < 0) { qx = -qx; qy = -qy; }
    const lato = 12 * S;
    const spallaA = { x: spalla.x + qx * lato, y: spalla.y + qy * lato };
    const spallaD = { x: spalla.x - qx * lato, y: spalla.y - qy * lato };
    arto(spallaD, p.gomitoD, p.manoD, 3 * S, nero);
    const ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2;
    const cx = p.collo.x * 0.55 + p.bacino.x * 0.45, cy = p.collo.y * 0.55 + p.bacino.y * 0.45;
    const R = 14 * S;
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(ang);
    const sagoma = () => {
      ctx.beginPath();
      ctx.moveTo(0, -0.72 * R);
      ctx.bezierCurveTo(0.55 * R, -1.08 * R, 1.12 * R, -0.62 * R, 1.02 * R, 0.08 * R);
      ctx.bezierCurveTo(0.96 * R, 0.66 * R, 0.55 * R, 1.06 * R, 0.22 * R, 0.96 * R);
      ctx.bezierCurveTo(0.08 * R, 0.92 * R, -0.08 * R, 0.92 * R, -0.22 * R, 0.96 * R);
      ctx.bezierCurveTo(-0.55 * R, 1.06 * R, -0.96 * R, 0.66 * R, -1.02 * R, 0.08 * R);
      ctx.bezierCurveTo(-1.12 * R, -0.62 * R, -0.55 * R, -1.08 * R, 0, -0.72 * R);
      ctx.closePath();
    };
    // Polpa bianca con una sfumatura crema verso il bordo, poi la buccia.
    const polpa = ctx.createRadialGradient(-R * 0.2, -R * 0.2, R * 0.1, 0, 0, R * 1.05);
    polpa.addColorStop(0, "#ffffff"); polpa.addColorStop(1, "#f6efe1");
    sagoma(); ctx.fillStyle = polpa; ctx.fill();
    ctx.lineWidth = 2.6 * S; ctx.strokeStyle = "#111"; ctx.lineJoin = "round"; ctx.stroke();
    linea({ x: 0, y: -0.7 * R }, { x: 0.12 * R, y: -1.18 * R }, 1.8 * S, "#6b4423");
    ctx.fillStyle = "#3f9a3a"; ctx.beginPath();
    ctx.ellipse(0.42 * R, -1.08 * R, 0.34 * R, 0.14 * R, -0.45, 0, Math.PI * 2); ctx.fill();
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
    ctx.restore();
    // Tutt'e due le braccia stanno DAVANTI al corpo: prima quella lontana
    // finiva dietro la polpa e la mela sembrava avere una mano sola.
    for (const [gomito, mano, r, colore] of [[p.gomitoD, p.manoD, 3.9, "#1f56b8"], [p.gomitoA, p.manoA, 4.2, "#2f72e0"]]) {
      if (mano !== p.manoD) arto(spallaA, gomito, mano, 3 * S, nero);
      guanto(gomito, mano, colore, r * S);
    }
  }

  function disegnaTelefono(t) {
    ctx.save(); ctx.translate(t.x, t.y); ctx.rotate(t.a);
    const w = t.w, h = t.h;
    ctx.fillStyle = t.colore; ctx.strokeStyle = "#111"; ctx.lineWidth = 1.2 * S;
    rettangoloTondo(-w / 2, -h / 2, w, h, 2 * S); ctx.fill(); ctx.stroke();
    ctx.fillStyle = t.stato === "preso" ? "#7fe0ff" : "#10202e";
    rettangoloTondo(-w / 2 + 1.1 * S, -h / 2 + 1.5 * S, w - 2.2 * S, h - 3 * S, 1.2 * S); ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,.25)";
    ctx.beginPath(); ctx.moveTo(-w / 2 + 1.1 * S, -h / 2 + 1.5 * S); ctx.lineTo(w * 0.1, -h / 2 + 1.5 * S);
    ctx.lineTo(-w / 2 + 1.1 * S, h * 0.1); ctx.closePath(); ctx.fill();
    if (t.tipo === "pieghevole") { ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.moveTo(-w / 2, 0); ctx.lineTo(w / 2, 0); ctx.stroke(); }
    tondo(0, -h / 2 + 0.8 * S, 0.5 * S, "#000");
    if (t.crepe) {
      ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 0.7 * S; ctx.beginPath();
      for (let i = 0; i < t.crepe; i++) {
        const sx = (-0.3 + 0.2 * i) * w, sy = (-0.35 + 0.18 * i) * h;
        ctx.moveTo(sx, sy); ctx.lineTo(sx + 0.3 * w, sy + 0.25 * h); ctx.lineTo(sx + 0.15 * w, sy + 0.45 * h);
      }
      ctx.stroke();
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
    } else if (q.tipo === "polvere") {
      ctx.fillStyle = q.colore; ctx.beginPath(); ctx.arc(q.x, q.y, (2 + (1 - q.vita / q.max) * 4) * S, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.translate(q.x, q.y); ctx.rotate(q.rot); ctx.fillStyle = q.colore; ctx.fillRect(-1.6 * S, -1 * S, 3.2 * S, 2 * S);
    }
    ctx.restore();
  }

  function disegna() {
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    if (scossa > 0) ctx.translate(caso(-1, 1) * Math.min(4, scossa) * S, caso(-1, 1) * Math.min(4, scossa) * S);
    disegnaDanni();
    for (const t of telefoni) disegnaTelefono(t);
    const ordine = lottatori.slice().sort((x, y) => (y.ko ? 1 : 0) - (x.ko ? 1 : 0));
    for (const f of ordine) (f.tipo === "robot" ? disegnaRobot : disegnaMela)(f);
    // Le stelline di chi è stordito o al tappeto.
    for (const f of lottatori) {
      if (!(f.stordito > 0 || (f.ko > 0 && !f.inVolo))) continue;
      for (let i = 0; i < 3; i++) {
        const ang = passi * 0.12 + (i * Math.PI * 2) / 3;
        stella(f.p.testa.x + Math.cos(ang) * 11 * S, f.p.testa.y - 12 * S + Math.sin(ang) * 3.5 * S, 2.6 * S, "#ffd84a");
      }
    }
    for (const q of particelle) disegnaParticella(q);
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

  // Per i test nel browser: lo stato del ring, in sola lettura.
  window.__ring = {
    // Solo per i test: un telefono lanciato a mano.
    lanciaTelefono: (x, y, vx, vy) => { const t = nuovoTelefono(x, y, vx, vy); t.stato = "volo"; t.cool = 0; return telefoni.indexOf(t); },
    danneggiaStriscia: (x, forza) => danneggiaStriscia(x, forza),
    decolla: (tipo, impazzito) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) decolla(f, !!impazzito); },
    avviaEvento: (nome) => { prossimoEvento = 1e9; if (nome === "luna") { moltG = 0.45; evento = { nome, durata: 620 }; } },
    stato: () => ({ telefoni: telefoni.map((t) => ({ x: t.x, y: t.y, stato: t.stato, tipo: t.tipo })),
    costume, particelle: particelle.length, danniStriscia: danni.length,
    campoRicerca: !!document.querySelector(".ricerca-grande input"), evento: evento ? evento.nome : null, moltG,
    lottatori: lottatori.map((f) => ({
    danni: f.danni, tel: !!f.tel, furia: f.furia, vola: f.jet > 0, caos: f.caos > 0,
    tipo: f.tipo, ko: f.ko, azione: f.azione, preso: !!f.preso,
    scalando: !!f.scalata, base: f.base, sopraUnElemento: !!f.supporto,
    testa: { x: f.p.testa.x, y: f.p.testa.y }, bacino: { x: f.p.bacino.x, y: f.p.bacino.y },
  })), punteggio: Object.assign({}, punteggio), pavimento, larghezza: W, altezza: H,
    ostacoli: ostacoli.length, riquadri: ostacoli.map((o) => [o.l, o.t, o.r, o.b].map(Math.round)) }) };
})();
