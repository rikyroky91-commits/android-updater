/* Il ring sopra l'ultim'ora della home (30/09/2026, su richiesta).
 *
 * Due lottatori — un robottino verde e una mela rossa, disegnati apposta
 * per questo sito — si picchiano in un ciclo casuale usando come
 * pavimento il filo rosso sopra la striscia delle notizie.
 *
 * COME SONO FATTI. Ognuno è una bambola di pezza (ragdoll) con integrazione
 * di Verlet: undici punti (testa, collo, bacino, gomiti, mani, ginocchia,
 * piedi) legati da aste di lunghezza fissa, con gravità, attrito col
 * pavimento e pareti ai due lati. Finché il lottatore è in piedi, dei
 * «muscoli» tirano ogni punto verso la posa del momento (guardia, pugno,
 * calcio, salto, esultanza); quando va K.O. i muscoli si spengono e il
 * corpo crolla da solo, poi si rialza piano piano. Nessuna animazione è
 * disegnata a mano: è tutta fisica, per questo ogni scontro è diverso.
 *
 * LE STESSE ATTENZIONI DELLA TRAMA DI SFONDO (`rete.js`):
 *  - il ciclo si ferma quando la scheda passa in secondo piano;
 *  - disegna a 30 fotogrammi al secondo, non 60: è una decorazione, e chi
 *    fa QA tiene questa scheda aperta tutto il giorno;
 *  - chi ha chiesto meno movimento al sistema operativo vede i due
 *    lottatori fermi in guardia, e la striscia delle notizie ferma (si
 *    scorre a mano).
 *
 * Il canvas non intercetta i clic (`pointer-events: none` nello stile).
 */
(function () {
  "use strict";

  const tela = document.querySelector("[data-ring]");
  const scorre = document.querySelector("[data-scorre]");
  const orologio = document.querySelector("[data-orologio]");

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
  // La durata dipende da quanto è lunga la striscia: con una durata fissa
  // dieci notizie correrebbero il doppio di cinque. Qui si fissa la
  // VELOCITÀ (pixel al secondo) e la durata ne discende.
  function tara() {
    if (!scorre) return;
    const meta = scorre.scrollWidth / 2;
    if (meta > 0) scorre.style.setProperty("--durata", Math.max(20, meta / 75) + "s");
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(tara);
  window.addEventListener("load", tara);

  if (!tela || !tela.getContext) return;
  const ctx = tela.getContext("2d");
  const fermo = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- Stato del mondo -------------------------------------------------
  let W = 0, H = 0, S = 1, suolo = 0;
  let lottatori = [];
  let scritte = [];
  let punteggio = { robot: 0, mela: 0 };
  let inchiostro = "#201e1d";
  let accento = "#ec3013";

  const caso = (a, b) => a + Math.random() * (b - a);
  const scegli = (voci) => {
    // [[peso, valore], ...]
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
  }

  // --- Il corpo --------------------------------------------------------
  // Altezze in unità «a scala 1» sopra il pavimento; dx verso la faccia.
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
    // le ginocchia separate, così una bambola di pezza non si accartoccia
    // in un gomitolo quando crolla.
    ["testa", "bacino"], ["ginocchioA", "ginocchioD"],
  ];
  // Quanto tira il muscolo di ciascun punto (le estremità sono più svelte).
  const TIRO = {
    testa: 0.16, collo: 0.2, bacino: 0.2, gomitoA: 0.18, manoA: 0.26,
    gomitoD: 0.18, manoD: 0.24, ginocchioA: 0.2, piedeA: 0.26, ginocchioD: 0.2, piedeD: 0.26,
  };

  function crea(tipo, x, dir) {
    const f = {
      tipo, dir, cx: x, p: {}, aste: [],
      forza: 1, ko: 0, rialzo: 0, stordito: 0, danni: 0, soglia: Math.round(caso(3, 6)),
      azione: null, t: 0, durata: 0, colpito: false, pensa: caso(20, 60),
      passo: 0, dolore: 0,
    };
    for (const nome in SCHELETRO) {
      const [h, dx, r] = SCHELETRO[nome];
      const px = x + dx * dir * S, py = suolo - h * S;
      f.p[nome] = { x: px, y: py, ox: px, oy: py, r: r * S };
    }
    for (const [a, b] of ASTE) {
      const pa = f.p[a], pb = f.p[b];
      f.aste.push([pa, pb, Math.hypot(pa.x - pb.x, pa.y - pb.y)]);
    }
    return f;
  }

  function avvia() {
    const rapporto = Math.min(window.devicePixelRatio || 1, 2);
    W = tela.clientWidth; H = tela.clientHeight;
    tela.width = Math.floor(W * rapporto); tela.height = Math.floor(H * rapporto);
    ctx.setTransform(rapporto, 0, 0, rapporto, 0, 0);
    S = H / 100;
    suolo = H - 1;
    const centro = W / 2, scarto = Math.min(90 * S, W * 0.18);
    lottatori = [crea("robot", centro - scarto, 1), crea("mela", centro + scarto, -1)];
    scritte = [];
    leggiColori();
  }

  // --- Le pose ---------------------------------------------------------
  function posa(f) {
    const q = {};
    for (const nome in SCHELETRO) q[nome] = [SCHELETRO[nome][0], SCHELETRO[nome][1]];
    const e = f.durata ? Math.sin(Math.PI * Math.min(1, f.t / f.durata)) : 0;
    const respiro = Math.sin(f.passo * 0.5 + (f.tipo === "mela" ? 1.7 : 0)) * 0.8;
    q.bacino[0] += respiro; q.collo[0] += respiro; q.testa[0] += respiro;

    // Camminare: i piedi si alternano e si sollevano.
    if (f.azione === "avanza" || f.azione === "indietro") {
      const ph = f.passo;
      q.piedeA = [Math.max(0, 5 * Math.cos(ph)), 8 + 7 * Math.sin(ph)];
      q.piedeD = [Math.max(0, -5 * Math.cos(ph)), -8 - 7 * Math.sin(ph)];
      q.ginocchioA = [14 + Math.max(0, 3 * Math.cos(ph)), 6 + 4 * Math.sin(ph)];
      q.ginocchioD = [14 + Math.max(0, -3 * Math.cos(ph)), -3 - 4 * Math.sin(ph)];
    }
    switch (f.azione) {
      case "pugno":
        q.manoA = [52, 13 + 17 * e]; q.gomitoA = [48, 9 + 9 * e];
        q.collo[1] += 3 * e; q.testa[1] += 4 * e; break;
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
    return q;
  }

  // --- Il cervello: un ciclo casuale di azioni --------------------------
  const DURATE = { avanza: 50, indietro: 26, pugno: 18, diretto: 20, montante: 24,
                   calcio: 28, provoca: 50, esulta: 36, salto: 34 };

  function inizia(f, azione) {
    f.azione = azione; f.t = 0; f.durata = DURATE[azione]; f.colpito = false;
    if (azione === "salto") {
      for (const n in f.p) { f.p[n].oy = f.p[n].y + 6.5 * S; f.p[n].ox = f.p[n].x - f.dir * 1.6 * S; }
    }
  }

  function pensa(f, altro) {
    if (f.ko || f.stordito) return;
    if (f.azione) {
      f.t++;
      if (f.t >= f.durata ||
          (f.azione === "avanza" && Math.abs(altro.cx - f.cx) < 27 * S)) {
        f.azione = null; f.pensa = caso(3, 22);
      }
      return;
    }
    if (--f.pensa > 0) return;
    // Rivolto verso l'avversario, quando non sta colpendo.
    f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
    const distanza = Math.abs(altro.cx - f.cx) / S;
    if (altro.ko) { inizia(f, Math.random() < 0.7 ? "esulta" : "salto"); return; }
    if (distanza > 34) {
      inizia(f, scegli([[74, "avanza"], [14, "provoca"], [12, "salto"]]));
    } else if (distanza < 22) {
      inizia(f, scegli([[45, "indietro"], [25, "montante"], [30, "pugno"]]));
    } else {
      inizia(f, scegli([[28, "pugno"], [20, "diretto"], [14, "montante"], [22, "calcio"],
                        [8, "indietro"], [8, "salto"]]));
    }
  }

  // --- I colpi ---------------------------------------------------------
  const COLPI = { pugno: ["manoA", 7, 13, 3.2], diretto: ["manoD", 8, 15, 3.8],
                  montante: ["manoA", 9, 17, 4.4], calcio: ["piedeA", 10, 19, 4.8] };
  const SUONI = ["POW!", "BAM!", "SBAM!", "TUMP!", "ZOT!", "PAF!"];

  function controllaColpo(f, altro) {
    const regola = COLPI[f.azione];
    if (!regola || f.colpito || altro.ko) return;
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

  function colpisci(f, altro, forza, x, y) {
    altro.danni++;
    const ko = altro.danni >= altro.soglia;
    const spinta = forza * S * (ko ? 1.9 : 1);
    for (const n in altro.p) {
      const peso = n.startsWith("piede") || n.startsWith("ginocchio") ? 0.35 : 1;
      altro.p[n].ox -= f.dir * spinta * peso;
      altro.p[n].oy += spinta * (ko ? 0.55 : 0.3);
    }
    altro.dolore = 22;
    altro.azione = null;
    scritte.push({ testo: SUONI[Math.floor(Math.random() * SUONI.length)], x, y: y - 6 * S,
                   vita: 26, grande: false });
    if (ko) {
      altro.ko = Math.round(caso(110, 170)); altro.danni = 0; altro.soglia = Math.round(caso(3, 6));
      punteggio[f.tipo]++;
      scritte.push({ testo: "K.O.!  " + punteggio.robot + "–" + punteggio.mela,
                     x: Math.max(60, Math.min(W - 60, altro.p.bacino.x)), y: Math.max(26, suolo - 72 * S), vita: 70, grande: true });
    } else {
      altro.stordito = 12;
    }
  }

  // --- Un passo di fisica (60 al secondo) ------------------------------
  const GRAVITA = 0.42;

  function passo() {
    const [a, b] = lottatori;
    for (const [f, altro] of [[a, b], [b, a]]) {
      // Forza dei muscoli: spenti da K.O., deboli da storditi, e tornano
      // piano quando ci si rialza.
      if (f.ko > 0) { f.forza = 0; if (--f.ko === 0) f.rialzo = 50; }
      else if (f.rialzo > 0) { f.forza = 1 - f.rialzo / 50; f.rialzo--; }
      else if (f.stordito > 0) { f.forza = 0.22; f.stordito--; }
      else f.forza = 1;
      if (f.dolore > 0) f.dolore--;

      pensa(f, altro);
      if (f.azione === "avanza") { f.cx += f.dir * (Math.abs(altro.cx - f.cx) > 220 * S ? 1.6 : 0.95) * S; f.passo += 0.28; }
      else if (f.azione === "indietro") { f.cx -= f.dir * 1.0 * S; f.passo += 0.3; }
      else f.passo += 0.08;
      // Il punto d'appoggio segue il corpo: dopo una spinta il lottatore
      // resta dove è finito invece di tornare di scatto dov'era.
      f.cx += (f.p.bacino.x - f.cx) * (f.forza < 1 ? 0.5 : 0.06);
      f.cx = Math.max(26 * S, Math.min(W - 26 * S, f.cx));
    }
    // Non passarsi attraverso.
    if (!a.ko && !b.ko) {
      const d = b.cx - a.cx, minimo = 22 * S;
      if (Math.abs(d) < minimo) {
        const s = d >= 0 ? 1 : -1, sposta = (minimo - Math.abs(d)) / 2;
        a.cx -= s * sposta; b.cx += s * sposta;
      }
    }

    for (const f of lottatori) {
      // Muscoli.
      if (f.forza > 0) {
        const q = posa(f);
        const scatto = f.azione && COLPI[f.azione] ? 0.55 : 0.3;
        for (const nome in q) {
          const pt = f.p[nome], [h, dx] = q[nome];
          const k = TIRO[nome] * f.forza * (COLPI[f.azione] && (nome === COLPI[f.azione][0]) ? 1.6 : 1);
          const tx = f.cx + dx * f.dir * S, ty = suolo - h * S;
          const mx = (tx - pt.x) * k, my = (ty - pt.y) * k;
          pt.x += mx; pt.y += my;
          pt.ox += mx * (1 - scatto); pt.oy += my * (1 - scatto);
        }
      }
      // Verlet.
      for (const n in f.p) {
        const pt = f.p[n];
        const vx = (pt.x - pt.ox) * 0.985, vy = (pt.y - pt.oy) * 0.985;
        pt.ox = pt.x; pt.oy = pt.y;
        pt.x += vx; pt.y += vy + GRAVITA * S;
      }
      // Vincoli: aste, pavimento, pareti.
      for (let giro = 0; giro < 5; giro++) {
        for (const [p1, p2, L] of f.aste) {
          const dx = p2.x - p1.x, dy = p2.y - p1.y;
          const d = Math.hypot(dx, dy) || 0.001;
          const c = (d - L) / d * 0.5;
          p1.x += dx * c; p1.y += dy * c; p2.x -= dx * c; p2.y -= dy * c;
        }
        for (const n in f.p) {
          const pt = f.p[n];
          if (pt.y > suolo - pt.r) {
            pt.y = suolo - pt.r;
            if (pt.oy < pt.y) pt.oy = pt.y;              // niente rimbalzo
            pt.ox += (pt.x - pt.ox) * 0.3;               // attrito
          }
          if (pt.y < pt.r) { pt.y = pt.r; pt.oy = pt.y; }
          if (pt.x < pt.r + 2) { pt.x = pt.r + 2; pt.ox = pt.x + (pt.x - pt.ox) * 0.4; }
          if (pt.x > W - pt.r - 2) { pt.x = W - pt.r - 2; pt.ox = pt.x + (pt.x - pt.ox) * 0.4; }
        }
      }
    }
    controllaColpo(a, b); controllaColpo(b, a);
    for (const s of scritte) { s.vita--; s.y -= 0.35 * S; }
    scritte = scritte.filter((s) => s.vita > 0);
  }

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
    // Da K.O. gli occhi sono due crocette; col dolore, due fessure.
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

  function disegnaRobot(f) {
    const p = f.p, verde = "#2fae74", scuro = "#1c6f4a";
    // Arti di dietro, più scuri: danno profondità senza un'ombra vera.
    arto(p.bacino, p.ginocchioD, p.piedeD, 5 * S, scuro);
    arto(p.collo, p.gomitoD, p.manoD, 4.4 * S, scuro);
    tondo(p.manoD.x, p.manoD.y, 3.2 * S, "#154d34");
    // Busto: una scatola orientata come la schiena.
    const ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2;
    const lung = Math.hypot(p.bacino.x - p.collo.x, p.bacino.y - p.collo.y);
    ctx.save();
    ctx.translate((p.collo.x + p.bacino.x) / 2, (p.collo.y + p.bacino.y) / 2); ctx.rotate(ang);
    ctx.fillStyle = verde; rettangoloTondo(-8.5 * S, -lung / 2 - 3 * S, 17 * S, lung + 7 * S, 4 * S); ctx.fill();
    ctx.fillStyle = scuro; rettangoloTondo(-4.5 * S, -lung / 2 + 3 * S, 9 * S, 6 * S, 1.5 * S); ctx.fill();
    tondo(-1.8 * S, -lung / 2 + 6 * S, 1.2 * S, f.ko ? "#555" : "#ffcf3a");
    tondo(1.8 * S, -lung / 2 + 6 * S, 1.2 * S, f.ko ? "#555" : "#ff6b4a");
    ctx.restore();
    // Arti davanti.
    arto(p.bacino, p.ginocchioA, p.piedeA, 5 * S, verde);
    for (const piede of [p.piedeD, p.piedeA]) {
      ctx.fillStyle = "#154d34"; rettangoloTondo(piede.x - 4 * S, piede.y - 2.5 * S, 8 * S, 4.5 * S, 1.5 * S); ctx.fill();
    }
    // Testa: un cubo con visiera e antenna.
    const angT = Math.atan2(p.testa.y - p.collo.y, p.testa.x - p.collo.x) + Math.PI / 2;
    ctx.save(); ctx.translate(p.testa.x, p.testa.y); ctx.rotate(angT);
    linea({ x: 0, y: -7 * S }, { x: 0, y: -13 * S }, 1.4 * S, scuro);
    tondo(0, -13.5 * S, 2 * S, (Math.floor(f.passo * 2) % 2 && !f.ko) ? "#ff4d3a" : "#ffcf3a");
    ctx.fillStyle = verde; rettangoloTondo(-8.5 * S, -7.5 * S, 17 * S, 15 * S, 4 * S); ctx.fill();
    ctx.fillStyle = "#0f2a1f"; rettangoloTondo(-6.5 * S, -3.5 * S, 13 * S, 6.5 * S, 2.5 * S); ctx.fill();
    occhi(f, 0, -0.3 * S, 2.8 * S, 1.4 * S, "#7dffd2");
    ctx.restore();
    arto(p.collo, p.gomitoA, p.manoA, 4.4 * S, verde);
    tondo(p.manoA.x, p.manoA.y, 3.4 * S, "#154d34");
  }

  function disegnaMela(f) {
    const p = f.p, rosso = "#d9372f";
    arto(p.bacino, p.ginocchioD, p.piedeD, 3.2 * S, inchiostro);
    arto(p.collo, p.gomitoD, p.manoD, 3 * S, inchiostro);
    tondo(p.manoD.x, p.manoD.y, 3.3 * S, "#f2f2f2");
    arto(p.bacino, p.ginocchioA, p.piedeA, 3.2 * S, inchiostro);
    for (const piede of [p.piedeD, p.piedeA]) {
      ctx.fillStyle = "#b52520"; ctx.beginPath();
      ctx.ellipse(piede.x + f.dir * 1.5 * S, piede.y - 0.5 * S, 4.2 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill();
    }
    // Il corpo è la mela: un frutto intero, col picciolo e una foglia.
    const ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2;
    const cx = p.collo.x * 0.55 + p.bacino.x * 0.45, cy = p.collo.y * 0.55 + p.bacino.y * 0.45;
    const R = 14 * S;
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(ang);
    const sfumatura = ctx.createRadialGradient(-R * 0.35, -R * 0.35, R * 0.2, 0, 0, R * 1.2);
    sfumatura.addColorStop(0, "#f0605a"); sfumatura.addColorStop(1, "#a9231d");
    ctx.fillStyle = sfumatura;
    ctx.beginPath();
    ctx.moveTo(0, -0.72 * R);
    ctx.bezierCurveTo(0.55 * R, -1.08 * R, 1.12 * R, -0.62 * R, 1.02 * R, 0.08 * R);
    ctx.bezierCurveTo(0.96 * R, 0.66 * R, 0.55 * R, 1.06 * R, 0.22 * R, 0.96 * R);
    ctx.bezierCurveTo(0.08 * R, 0.92 * R, -0.08 * R, 0.92 * R, -0.22 * R, 0.96 * R);
    ctx.bezierCurveTo(-0.55 * R, 1.06 * R, -0.96 * R, 0.66 * R, -1.02 * R, 0.08 * R);
    ctx.bezierCurveTo(-1.12 * R, -0.62 * R, -0.55 * R, -1.08 * R, 0, -0.72 * R);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.beginPath(); ctx.ellipse(-0.45 * R, -0.35 * R, 0.16 * R, 0.3 * R, -0.5, 0, Math.PI * 2); ctx.fill();
    linea({ x: 0, y: -0.7 * R }, { x: 0.12 * R, y: -1.18 * R }, 1.8 * S, "#6b4423");
    ctx.fillStyle = "#3f9a3a"; ctx.beginPath();
    ctx.ellipse(0.42 * R, -1.08 * R, 0.34 * R, 0.14 * R, -0.45, 0, Math.PI * 2); ctx.fill();
    // Faccia: occhi bianchi, pupille verso l'avversario, sopracciglia arrabbiate.
    for (const lato of [-1, 1]) tondo(lato * 0.34 * R + f.dir * 0.08 * R, -0.18 * R, 0.2 * R, "#fff");
    occhi(f, f.dir * 0.08 * R, -0.16 * R, 0.34 * R, 0.09 * R, "#1a1a1a");
    if (!f.ko) {
      ctx.strokeStyle = "#1a1a1a"; ctx.lineWidth = 1.4 * S; ctx.beginPath();
      for (const lato of [-1, 1]) {
        const x0 = lato * 0.34 * R + f.dir * 0.08 * R;
        ctx.moveTo(x0 - 0.2 * R, -0.46 * R + (lato === f.dir ? 0.08 : -0.02) * R);
        ctx.lineTo(x0 + 0.2 * R, -0.46 * R + (lato === f.dir ? -0.02 : 0.08) * R);
      }
      ctx.stroke();
    }
    ctx.restore();
    arto(p.collo, p.gomitoA, p.manoA, 3 * S, inchiostro);
    tondo(p.manoA.x, p.manoA.y, 3.5 * S, "#f7f7f7");
    ctx.strokeStyle = inchiostro; ctx.lineWidth = 0.9 * S;
    ctx.beginPath(); ctx.arc(p.manoA.x, p.manoA.y, 3.5 * S, 0, Math.PI * 2); ctx.stroke();
  }

  function disegna() {
    ctx.clearRect(0, 0, W, H);
    // Chi è a terra si disegna per primo: chi è in piedi gli sta davanti.
    const ordine = lottatori.slice().sort((x, y) => (y.ko ? 1 : 0) - (x.ko ? 1 : 0));
    for (const f of ordine) (f.tipo === "robot" ? disegnaRobot : disegnaMela)(f);
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
    if (document.hidden) return;
    if (!ultimo) ultimo = adesso;
    riserva += Math.min(100, adesso - ultimo);
    ultimo = adesso;
    let giri = 0;
    while (riserva >= PASSO_MS && giri < 4) { passo(); riserva -= PASSO_MS; giri++; }
    if (giri === 4) riserva = 0;
    // Un disegno ogni due: 30 fotogrammi al secondo bastano a una
    // decorazione e costano la metà.
    if ((fotogramma++ & 1) === 0) disegna();
    richiesta = requestAnimationFrame(ciclo);
  }
  function riparti() {
    if (fermo || richiesta || document.hidden) return;
    ultimo = 0; riserva = 0;
    richiesta = requestAnimationFrame(ciclo);
  }

  function inGuardiaFermi() {
    // Per chi ha chiesto meno movimento: una sola posa, assestata.
    for (let i = 0; i < 90; i++) {
      for (const f of lottatori) { f.azione = null; f.pensa = 1e9; }
      passo();
    }
    disegna();
  }

  avvia();
  if (fermo) inGuardiaFermi(); else riparti();

  let attesa = null;
  window.addEventListener("resize", () => {
    clearTimeout(attesa);
    attesa = setTimeout(() => { avvia(); tara(); if (fermo) inGuardiaFermi(); }, 150);
  });
  window.addEventListener("mut:tema", () => { leggiColori(); if (fermo) disegna(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) riparti(); });

  // Per i test nel browser: lo stato del ring, senza esporre i comandi.
  window.__ring = { stato: () => ({ lottatori: lottatori.map((f) => ({
    tipo: f.tipo, ko: f.ko, azione: f.azione,
    testa: { x: f.p.testa.x, y: f.p.testa.y }, bacino: { x: f.p.bacino.x, y: f.p.bacino.y },
  })), punteggio: Object.assign({}, punteggio), suolo, larghezza: W }) };
})();
