/* IL TEMA NATALIZIO DI TUTTO IL SITO (02/10/2026, su richiesta).
 *
 * Un tasto nella testata, accanto a quello del tema scuro, lo accende e lo
 * spegne; la scelta resta nel browser (`mut-natale`). È separato dal ring
 * dei due lottatori: funziona su ogni pagina.
 *
 * Acceso:
 *   - nevica su tutta la finestra, col vento che cambia; i fiocchi si posano
 *     sul bordo alto degli elementi della pagina (titoli, campo di ricerca,
 *     tasti, tabelle, la striscia delle notizie) e ci si accumulano; il
 *     mucchio frana se diventa troppo ripido e si spazza via passandoci
 *     sopra col puntatore;
 *   - un albero addobbato e dei pupazzi di neve stanno sul fondo: toccati
 *     col puntatore i pupazzi vanno in pezzi, e i pezzi si riprendono e si
 *     rimettono a posto uno alla volta (base, busto, testa, poi naso e
 *     cappello);
 *   - cappellini rossi sulle faccine e su qualche lettera, e una fila di
 *     lucine sotto la testata: quelli li fa lo stile (`html.natale`).
 *
 * Il canvas non riceve clic: la pagina sotto resta usabile. Solo un pezzo
 * di pupazzo sotto il puntatore viene trattenuto.
 */
(function () {
  "use strict";

  var radice = document.documentElement;
  var CHIAVE = "mut-natale";
  var acceso = false;
  try { acceso = window.localStorage.getItem(CHIAVE) === "on"; } catch (e) { /* resta spento */ }

  var tela = null, ctx = null, W = 0, H = 0, richiesta = null, passi = 0;
  var fiocchi = [], superfici = [], cumuli = new Map(), pupazzi = [], sbuffi = [];
  var pavimento = 0, vento = 0, raffica = 0;
  var puntatore = { x: -999, y: -999, vx: 0, vy: 0 };
  var presa = null;
  var ridotto = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  function caso(a, b) { return a + Math.random() * (b - a); }

  // --- Il tasto ---------------------------------------------------------
  function aggiornaTasti() {
    var tasti = document.querySelectorAll("[data-natale-tasto]");
    for (var i = 0; i < tasti.length; i++) {
      tasti[i].setAttribute("aria-pressed", acceso ? "true" : "false");
      tasti[i].setAttribute("title", acceso ? "Spegni il tema natalizio" : "Accendi il tema natalizio");
    }
  }
  function imposta(nuovo) {
    acceso = !!nuovo;
    try { window.localStorage.setItem(CHIAVE, acceso ? "on" : "off"); } catch (e) { /* solo per questa pagina */ }
    radice.classList.toggle("natale", acceso);
    aggiornaTasti();
    try { window.dispatchEvent(new CustomEvent("mut:natale", { detail: { acceso: acceso } })); } catch (e) { /* pazienza */ }
    if (acceso) avvia(); else spegni();
  }

  // --- Il canvas --------------------------------------------------------
  function dimensiona() {
    var rapporto = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    tela.width = Math.floor(W * rapporto); tela.height = Math.floor(H * rapporto);
    tela.style.width = W + "px"; tela.style.height = H + "px";
    ctx.setTransform(rapporto, 0, 0, rapporto, 0, 0);
  }

  // --- Dove si posa la neve ---------------------------------------------
  var POSATOI = "main input:not([type=hidden]), main button, main table, main img, main select, main textarea, " +
                ".pieduccio, [class*='scheda'], .tema-tasto, .conto";
  function visibile(r) { return r && r.width >= 14 && r.height >= 6 && r.bottom > 0 && r.top < H && r.right > 0 && r.left < W; }
  function rileva() {
    var nuove = [];
    function aggiungi(chiave, r, tetto) {
      if (!visibile(r) || nuove.length > 70) return;
      var n = Math.max(2, Math.ceil(r.width / 5));
      var pila = cumuli.get(chiave);
      if (!pila || pila.length !== n) { pila = new Float32Array(n); cumuli.set(chiave, pila); }
      nuove.push({ l: r.left, t: r.top, r: r.right, tetto: tetto, pila: pila });
    }
    // Il fondo: il bordo alto della striscia delle notizie, o il fondo della finestra.
    var barra = document.querySelector(".ultimora-barra");
    var rb = barra && barra.getBoundingClientRect ? barra.getBoundingClientRect() : null;
    pavimento = rb && rb.top > 0 && rb.top < H ? rb.top : H;
    aggiungi("fondo", { left: 0, right: W, top: pavimento, bottom: pavimento + 10, width: W, height: 10 }, 18);
    var i, els = document.querySelectorAll(POSATOI);
    for (i = 0; i < els.length; i++) {
      if (els[i].closest && els[i].closest(".ring-pannello, .ultimora, [hidden]")) continue;
      aggiungi(els[i], els[i].getBoundingClientRect(), 9);
    }
    // I titoli: riga per riga, larghi quanto il testo (non quanto la colonna).
    var titoli = document.querySelectorAll("main h1, main h2");
    for (i = 0; i < titoli.length && i < 12; i++) {
      var intervallo = document.createRange();
      intervallo.selectNodeContents(titoli[i]);
      var rr = intervallo.getClientRects(), righe = [];
      for (var k = 0; k < rr.length; k++) {
        var q = rr[k], ultima = righe[righe.length - 1];
        if (q.width < 4) continue;
        if (ultima && Math.abs(ultima.top - q.top) < q.height * 0.6) { ultima.left = Math.min(ultima.left, q.left); ultima.right = Math.max(ultima.right, q.right); ultima.top = Math.min(ultima.top, q.top); }
        else righe.push({ left: q.left, right: q.right, top: q.top, bottom: q.bottom });
      }
      for (k = 0; k < righe.length; k++) {
        var riga = righe[k];
        riga.width = riga.right - riga.left; riga.height = riga.bottom - riga.top;
        // Il bordo alto del riquadro sta sopra le lettere: si scende all'altezza delle maiuscole.
        riga.top += riga.height * 0.2;
        aggiungi(titoli[i].tagName + i + ":" + k, riga, 6);
      }
    }
    superfici = nuove;
    for (i = 0; i < pupazzi.length; i++) pupazzi[i].base = pavimento;
  }

  // --- I fiocchi --------------------------------------------------------
  function nuovoFiocco(inAlto) {
    return { x: caso(-40, W + 40), y: inAlto ? caso(-H, 0) : caso(-20, -4), py: -30, vx: caso(-0.3, 0.3), vy: caso(1, 2.5),
             r: caso(1.3, 3.3), fase: caso(0, 6.28) };
  }
  function posa(f, s) {
    var pila = s.pila, n = pila.length, i = Math.max(0, Math.min(n - 1, Math.floor((f.x - s.l) / (s.r - s.l) * n)));
    if (pila[i] >= s.tetto) return false;                       // pieno: il fiocco scivola via
    var quanto = 0.75 * f.r;
    for (var d = -2; d <= 2; d++) {
      var j = i + d;
      if (j >= 0 && j < n) pila[j] = Math.min(s.tetto, pila[j] + quanto * (d === 0 ? 1 : Math.abs(d) === 1 ? 0.55 : 0.25));
    }
    return true;
  }
  function assesta() {
    // Un mucchio troppo ripido frana verso il vicino più basso; ai bordi cade giù.
    for (var k = 0; k < superfici.length; k++) {
      var s = superfici[k], p = s.pila, n = p.length;
      for (var i = 0; i < n - 1; i++) {
        var d = p[i] - p[i + 1];
        if (d > 2.2) { p[i] -= 0.5; p[i + 1] += 0.5; } else if (d < -2.2) { p[i] += 0.5; p[i + 1] -= 0.5; }
      }
      if (s.tetto < 12) {
        if (p[0] > 3 && Math.random() < 0.3) { p[0] -= 0.6; sbuffo(s.l - 1, s.t - p[0], -0.4, 0.4); }
        if (p[n - 1] > 3 && Math.random() < 0.3) { p[n - 1] -= 0.6; sbuffo(s.r + 1, s.t - p[n - 1], 0.4, 0.4); }
      }
    }
  }
  function sbuffo(x, y, vx, vy) {
    if (sbuffi.length > 120) return;
    sbuffi.push({ x: x, y: y, vx: vx + caso(-0.4, 0.4), vy: vy + caso(-0.6, 0.2), vita: 60, r: caso(1, 2.4) });
  }
  // Il puntatore spazza via la neve posata.
  function spazza() {
    if (Math.abs(puntatore.vx) + Math.abs(puntatore.vy) < 1.5) return;
    for (var k = 0; k < superfici.length; k++) {
      var s = superfici[k];
      if (puntatore.x < s.l - 8 || puntatore.x > s.r + 8 || puntatore.y < s.t - 22 || puntatore.y > s.t + 8) continue;
      var p = s.pila, n = p.length, c = Math.floor((puntatore.x - s.l) / (s.r - s.l) * n);
      for (var i = Math.max(0, c - 3); i <= Math.min(n - 1, c + 3); i++) {
        if (p[i] > 0.6) {
          var tolta = Math.min(p[i], 1.2);
          p[i] -= tolta;
          if (Math.random() < 0.5) sbuffo(s.l + (i + 0.5) * (s.r - s.l) / n, s.t - p[i], puntatore.vx * 0.15, -1.2);
        }
      }
    }
  }

  // --- I pupazzi di neve ------------------------------------------------
  // Cinque pezzi: base, busto (con braccia, sciarpa e bottoni), testa (con
  // gli occhi), naso e cappello. `hx`, `hy` sono il posto di ognuno rispetto
  // al punto d'appoggio del pupazzo.
  var ORDINE = { base: null, busto: "base", testa: "busto", naso: "testa", cappello: "testa" };
  function nuovoPupazzo(x, scala) {
    var s = scala, pezzi = [
      { tipo: "base", r: 22 * s, hx: 0, hy: -21 * s },
      { tipo: "busto", r: 16 * s, hx: 0, hy: -54 * s },
      { tipo: "testa", r: 11 * s, hx: 0, hy: -77 * s },
      { tipo: "naso", r: 5 * s, hx: 0, hy: -76 * s },
      { tipo: "cappello", r: 9 * s, hx: 0, hy: -91 * s },
    ];
    var p = { x: x, base: pavimento, scala: s, pezzi: pezzi, verso: x > W / 2 ? -1 : 1, attendeUscita: false, festa: 0 };
    for (var i = 0; i < pezzi.length; i++) {
      var q = pezzi[i];
      q.x = q.ox = x + q.hx; q.y = q.oy = p.base + q.hy; q.ang = 0; q.va = 0; q.posto = true; q.pup = p;
    }
    return p;
  }
  function casa(q) { return { x: q.pup.x + q.hx, y: q.pup.base + q.hy }; }
  function intero(p) { for (var i = 0; i < p.pezzi.length; i++) if (!p.pezzi[i].posto) return false; return true; }
  function pezzoDi(p, tipo) { for (var i = 0; i < p.pezzi.length; i++) if (p.pezzi[i].tipo === tipo) return p.pezzi[i]; return null; }
  function ammesso(q) { var sotto = ORDINE[q.tipo]; return !sotto || pezzoDi(q.pup, sotto).posto; }
  function smonta(p, px, py) {
    for (var i = 0; i < p.pezzi.length; i++) {
      var q = p.pezzi[i], c = casa(q);
      q.posto = false; q.x = c.x; q.y = c.y;
      var dx = q.x - px, dy = q.y - py, d = Math.hypot(dx, dy) || 1, v = caso(3, 7);
      q.ox = q.x - (dx / d * v + caso(-1.5, 1.5) + puntatore.vx * 0.2); q.oy = q.y - (dy / d * v - caso(2, 5));
      q.va = caso(-0.25, 0.25);
    }
    for (i = 0; i < 14; i++) sbuffo(p.x + caso(-20, 20) * p.scala, p.base - caso(10, 80) * p.scala, caso(-2, 2), caso(-2, 0));
  }
  function tocca(x, y) {
    // Un pupazzo intero sotto il puntatore va in pezzi.
    for (var i = 0; i < pupazzi.length; i++) {
      var p = pupazzi[i];
      if (!intero(p)) continue;
      var dentro = false;
      for (var k = 0; k < p.pezzi.length; k++) { var c = casa(p.pezzi[k]); if (Math.hypot(c.x - x, c.y - y) < p.pezzi[k].r + 4) dentro = true; }
      if (p.attendeUscita) { if (!dentro && Math.hypot(p.x - x, p.base - 50 * p.scala - y) > 70 * p.scala) p.attendeUscita = false; continue; }
      if (dentro) smonta(p, x, y);
    }
  }
  function pezzoSotto(x, y, raggio) {
    var migliore = null, d0 = 1e9;
    for (var i = 0; i < pupazzi.length; i++) {
      for (var k = 0; k < pupazzi[i].pezzi.length; k++) {
        var q = pupazzi[i].pezzi[k];
        if (q.posto) continue;
        var d = Math.hypot(q.x - x, q.y - y) - q.r;
        if (d < raggio && d < d0) { d0 = d; migliore = q; }
      }
    }
    return migliore;
  }
  function aggiornaPupazzi() {
    for (var i = 0; i < pupazzi.length; i++) {
      var p = pupazzi[i];
      if (p.festa > 0) p.festa--;
      for (var k = 0; k < p.pezzi.length; k++) {
        var q = p.pezzi[k];
        if (q.posto) { var c = casa(q); q.x = q.ox = c.x; q.y = q.oy = c.y; q.ang = 0; continue; }
        if (presa === q) {
          q.ox = q.x; q.oy = q.y;
          q.x += Math.max(-30, Math.min(30, puntatore.x - q.x)); q.y += Math.max(-30, Math.min(30, puntatore.y - q.y));
          q.ang *= 0.8;
          continue;
        }
        var vx = (q.x - q.ox) * 0.985, vy = (q.y - q.oy) * 0.985;
        q.ox = q.x; q.oy = q.y; q.x += vx; q.y += vy + 0.45; q.ang += q.va;
        var suolo = p.base - q.r * (q.tipo === "cappello" || q.tipo === "naso" ? 0.6 : 1);
        if (q.y > suolo) { q.y = suolo; q.oy = q.y + Math.max(0, vy) * 0.3; q.ox = q.x - vx * 0.8; q.va = q.tipo === "naso" || q.tipo === "cappello" ? q.va * 0.6 : vx / q.r; }
        if (q.x < q.r) { q.x = q.r; q.ox = q.x + Math.abs(vx) * 0.5; }
        if (q.x > W - q.r) { q.x = W - q.r; q.ox = q.x - Math.abs(vx) * 0.5; }
      }
    }
    // Le palle libere non si compenetrano.
    var libere = [];
    for (i = 0; i < pupazzi.length; i++) for (k = 0; k < pupazzi[i].pezzi.length; k++) { var z = pupazzi[i].pezzi[k]; if (!z.posto && z !== presa && z.r > 8) libere.push(z); }
    for (i = 0; i < libere.length; i++) for (k = i + 1; k < libere.length; k++) {
      var a = libere[i], b = libere[k], dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01, m = a.r + b.r;
      if (d < m) { var s = (m - d) / d * 0.5; a.x -= dx * s * 0.5; b.x += dx * s * 0.5; a.y -= dy * s * 0.3; b.y += dy * s * 0.3; }
    }
  }
  function lasciaPezzo() {
    var q = presa;
    presa = null;
    radice.classList.remove("natale-trascina");
    if (!q) return;
    var c = casa(q);
    if (ammesso(q) && Math.hypot(c.x - q.x, c.y - q.y) < 30 * q.pup.scala + 8) {
      q.posto = true; q.x = c.x; q.y = c.y;
      for (var i = 0; i < 6; i++) sbuffo(c.x + caso(-q.r, q.r), c.y + caso(-q.r, q.r), caso(-1, 1), caso(-1.5, 0));
      if (intero(q.pup)) { q.pup.attendeUscita = true; q.pup.festa = 70; }
    } else {
      q.ox = q.x - puntatore.vx * 0.6; q.oy = q.y - puntatore.vy * 0.6; q.va = caso(-0.2, 0.2);
    }
  }

  // --- Disegno ----------------------------------------------------------
  function tondo(x, y, r, colore) { ctx.fillStyle = colore; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
  function palla(r) {
    var g = ctx.createRadialGradient(-r * 0.3, -r * 0.35, r * 0.1, 0, 0, r);
    g.addColorStop(0, "#ffffff"); g.addColorStop(1, "#dfe8f3");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#7f93ad"; ctx.lineWidth = 1.3; ctx.stroke();
  }
  function disegnaPezzo(q) {
    var s = q.pup.scala, v = q.pup.verso;
    ctx.save(); ctx.translate(q.x, q.y); ctx.rotate(q.ang);
    if (q.tipo === "base") palla(q.r);
    else if (q.tipo === "busto") {
      // Le braccia di rametti, dietro la palla.
      ctx.strokeStyle = "#6b4423"; ctx.lineWidth = 2 * s; ctx.lineCap = "round"; ctx.beginPath();
      ctx.moveTo(-12 * s, -2 * s); ctx.lineTo(-30 * s, -12 * s); ctx.moveTo(-25 * s, -9 * s); ctx.lineTo(-29 * s, -3 * s);
      ctx.moveTo(12 * s, -2 * s); ctx.lineTo(30 * s, -14 * s); ctx.moveTo(25 * s, -11 * s); ctx.lineTo(31 * s, -8 * s);
      ctx.stroke();
      palla(q.r);
      for (var i = 0; i < 3; i++) tondo(0, (-7 + 7 * i) * s, 1.7 * s, "#22262e");
      // La sciarpa.
      ctx.fillStyle = "#d8343f"; ctx.strokeStyle = "#8f1f28"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.ellipse(0, -13 * s, 12 * s, 4 * s, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(v * 6 * s, -11 * s); ctx.lineTo(v * 11 * s, 2 * s); ctx.lineTo(v * 5 * s, 3 * s); ctx.lineTo(v * 2 * s, -10 * s); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (q.tipo === "testa") {
      palla(q.r);
      tondo(-3.6 * s + v * 1.5 * s, -2.5 * s, 1.5 * s, "#22262e"); tondo(3.6 * s + v * 1.5 * s, -2.5 * s, 1.5 * s, "#22262e");
      for (var k = -2; k <= 2; k++) tondo(k * 2 * s + v * 1.5 * s, (5 - Math.abs(k) * 0.8) * s, 0.8 * s, "#22262e");
    } else if (q.tipo === "naso") {
      ctx.fillStyle = "#f08a24"; ctx.strokeStyle = "#a95a10"; ctx.lineWidth = 1; ctx.beginPath();
      ctx.moveTo(0, -2.2 * s); ctx.lineTo(v * 12 * s, 0.6 * s); ctx.lineTo(0, 2.2 * s); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else {
      // Cappello a cilindro con la fascia rossa.
      ctx.fillStyle = "#22262e"; ctx.fillRect(-12 * s, 4 * s, 24 * s, 3 * s);
      ctx.fillRect(-8 * s, -10 * s, 16 * s, 14 * s);
      ctx.fillStyle = "#d8343f"; ctx.fillRect(-8 * s, 0, 16 * s, 3.4 * s);
    }
    ctx.restore();
  }
  function disegnaSagoma(q) {
    var c = casa(q);
    ctx.save(); ctx.setLineDash([4, 4]); ctx.strokeStyle = "rgba(90,120,160,.8)"; ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.arc(c.x, c.y, q.r, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
  }
  function stella(x, y, r, colore) {
    ctx.fillStyle = colore; ctx.beginPath();
    for (var i = 0; i < 10; i++) { var a = (i / 10) * Math.PI * 2 - Math.PI / 2, rr = i % 2 ? r * 0.45 : r; ctx[i ? "lineTo" : "moveTo"](x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
    ctx.closePath(); ctx.fill();
  }
  function disegnaAlbero(x, y, s) {
    ctx.fillStyle = "#6b4423"; ctx.fillRect(x - 4 * s, y - 14 * s, 8 * s, 14 * s);
    var piani = [[0, 34, 26], [20, 28, 24], [38, 21, 22], [54, 14, 18]];
    for (var i = 0; i < piani.length; i++) {
      var su = piani[i][0], largo = piani[i][1], alto = piani[i][2];
      ctx.fillStyle = "#2e8b4e"; ctx.strokeStyle = "#1c5a33"; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(x - largo * s, y - (14 + su) * s); ctx.lineTo(x + largo * s, y - (14 + su) * s);
      ctx.lineTo(x, y - (14 + su + alto) * s); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 2.2 * s; ctx.lineCap = "round"; ctx.beginPath();
      ctx.moveTo(x - largo * 0.7 * s, y - (16 + su) * s); ctx.lineTo(x + largo * 0.7 * s, y - (16 + su) * s); ctx.stroke();
    }
    var palline = [[-18, 22, "#d8343f"], [14, 26, "#ffcf3a"], [-6, 42, "#2f72e0"], [12, 50, "#d8343f"], [-8, 60, "#ffcf3a"], [4, 72, "#d8343f"]];
    for (i = 0; i < palline.length; i++) {
      var accesa = (Math.floor(passi / 24) + i) % 3 !== 0;
      tondo(x + palline[i][0] * s, y - palline[i][1] * s, 2.4 * s, accesa ? palline[i][2] : "#6d6d6d");
    }
    stella(x, y - 94 * s, 6 * s, "#ffd84a");
  }

  function disegna() {
    ctx.clearRect(0, 0, W, H);
    var i, k, scuro = radice.getAttribute("data-tema") === "scuro";
    var stretto = W < 640, sA = stretto ? 0.62 : 1;
    disegnaAlbero(stretto ? 30 : 48, pavimento, stretto ? sA : 0.9);
    // Pupazzi: prima le sagome di dove va il prossimo pezzo, poi i pezzi.
    for (i = 0; i < pupazzi.length; i++) {
      var p = pupazzi[i];
      if (!intero(p)) for (k = 0; k < p.pezzi.length; k++) if (!p.pezzi[k].posto && ammesso(p.pezzi[k])) disegnaSagoma(p.pezzi[k]);
      for (k = 0; k < p.pezzi.length; k++) if (p.pezzi[k] !== presa) disegnaPezzo(p.pezzi[k]);
      if (p.festa > 0) for (k = 0; k < 5; k++) {
        var a = passi * 0.2 + k * 1.26;
        stella(p.x + Math.cos(a) * 30 * p.scala, p.base - 50 * p.scala + Math.sin(a) * 44 * p.scala, 3.5, "#ffd84a");
      }
    }
    // La neve posata.
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = scuro ? "rgba(190,210,235,.7)" : "rgba(110,140,180,.75)"; ctx.lineWidth = 1.1; ctx.lineJoin = "round";
    for (i = 0; i < superfici.length; i++) {
      var s = superfici[i], pila = s.pila, n = pila.length, passo = (s.r - s.l) / n, vuota = true;
      for (k = 0; k < n; k++) if (pila[k] > 0.4) { vuota = false; break; }
      if (vuota) continue;
      ctx.beginPath(); ctx.moveTo(s.l, s.t + 1);
      for (k = 0; k < n; k++) ctx.lineTo(s.l + (k + 0.5) * passo, s.t - pila[k]);
      ctx.lineTo(s.r, s.t + 1); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.moveTo(s.l, s.t + 1);
      for (k = 0; k < n; k++) ctx.lineTo(s.l + (k + 0.5) * passo, s.t - pila[k]);
      ctx.lineTo(s.r, s.t + 1); ctx.stroke();
    }
    // I fiocchi e gli sbuffi.
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = scuro ? "rgba(200,220,245,.35)" : "rgba(90,125,170,.6)"; ctx.lineWidth = 0.8;
    for (i = 0; i < fiocchi.length; i++) { var f = fiocchi[i]; ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); }
    for (i = 0; i < sbuffi.length; i++) { var b = sbuffi[i]; ctx.globalAlpha = Math.min(1, b.vita / 20); ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); }
    ctx.globalAlpha = 1;
    if (presa) disegnaPezzo(presa);
  }

  // --- Il ciclo ---------------------------------------------------------
  function passo() {
    passi++;
    if (passi % 30 === 0) { rileva(); assesta(); }
    // Il vento gira piano, con qualche raffica.
    if (raffica > 0) raffica--; else if (!ridotto && Math.random() < 0.002) raffica = Math.round(caso(90, 200));
    var meta = Math.sin(passi * 0.004) * 0.7 + (raffica > 0 ? Math.sin(passi * 0.004 + 1) * 2.4 : 0);
    vento += (meta - vento) * 0.02;
    for (var i = 0; i < fiocchi.length; i++) {
      var f = fiocchi[i];
      f.py = f.y;
      f.x += f.vx + vento + Math.sin(f.fase + passi * 0.03) * 0.35; f.y += f.vy;
      var posato = false;
      for (var k = 0; k < superfici.length; k++) {
        var s = superfici[k];
        if (f.x < s.l || f.x > s.r) continue;
        var n = s.pila.length, col = Math.max(0, Math.min(n - 1, Math.floor((f.x - s.l) / (s.r - s.l) * n)));
        var cima = s.t - s.pila[col];
        if (f.py <= cima && f.y >= cima) {
          if (posa(f, s)) { posato = true; if (Math.random() < 0.25) sbuffo(f.x, cima, caso(-0.8, 0.8), -0.8); }
          else if (k === 0) posato = true;               // sul fondo pieno il fiocco sparisce
          break;
        }
      }
      if (posato || f.y > H + 10 || f.x < -60 || f.x > W + 60) fiocchi[i] = nuovoFiocco(false);
    }
    for (i = 0; i < sbuffi.length; i++) { var b = sbuffi[i]; b.x += b.vx + vento * 0.5; b.y += b.vy; b.vy += 0.06; b.vita--; }
    if (sbuffi.length && passi % 10 === 0) sbuffi = sbuffi.filter(function (b2) { return b2.vita > 0; });
    spazza();
    aggiornaPupazzi();
    puntatore.vx *= 0.8; puntatore.vy *= 0.8;
  }
  function ciclo() {
    richiesta = null;
    if (!acceso || document.hidden) return;
    passo();
    disegna();
    richiesta = window.requestAnimationFrame(ciclo);
  }
  function riparti() { if (acceso && !richiesta && !document.hidden) richiesta = window.requestAnimationFrame(ciclo); }

  function popola() {
    var quanti = ridotto ? 45 : Math.max(70, Math.min(260, Math.round(W * H / 4600)));
    fiocchi = [];
    for (var i = 0; i < quanti; i++) fiocchi.push(nuovoFiocco(true));
    pupazzi = [];
    var stretto = W < 640, s = stretto ? 0.62 : 1;
    pupazzi.push(nuovoPupazzo(W - (stretto ? 46 : 96), s));
    if (W > 1100) pupazzi.push(nuovoPupazzo(128, 0.8));       // solo se c'è margine accanto alla colonna
  }
  function avvia() {
    if (!tela) {
      tela = document.createElement("canvas");
      tela.className = "natale-tela"; tela.setAttribute("aria-hidden", "true");
      document.body.appendChild(tela);
      ctx = tela.getContext("2d");
      if (!ctx) { tela = null; return; }
    }
    tela.style.display = "";
    dimensiona(); rileva(); popola();
    riparti();
  }
  function spegni() {
    if (richiesta) { window.cancelAnimationFrame(richiesta); richiesta = null; }
    presa = null;
    radice.classList.remove("natale-presa", "natale-trascina");
    if (tela) { ctx.clearRect(0, 0, W, H); tela.style.display = "none"; }
    fiocchi = []; sbuffi = []; pupazzi = []; cumuli = new Map(); superfici = [];
  }

  // --- Puntatore --------------------------------------------------------
  window.addEventListener("pointermove", function (e) {
    if (!acceso) return;
    puntatore.vx = e.clientX - puntatore.x; puntatore.vy = e.clientY - puntatore.y;
    puntatore.x = e.clientX; puntatore.y = e.clientY;
    if (Math.abs(puntatore.vx) > 80 || Math.abs(puntatore.vy) > 80) { puntatore.vx = 0; puntatore.vy = 0; }
    if (presa) { if (e.cancelable) e.preventDefault(); return; }
    tocca(e.clientX, e.clientY);
    if (e.pointerType !== "touch") radice.classList.toggle("natale-presa", !!pezzoSotto(e.clientX, e.clientY, 6));
  }, { capture: true, passive: false });
  window.addEventListener("pointerdown", function (e) {
    if (!acceso || (e.button !== undefined && e.button > 0)) return;
    if (e.target && e.target.closest && e.target.closest(".ring-pannello, .ultimora-barra, .testata")) return;
    puntatore.x = e.clientX; puntatore.y = e.clientY; puntatore.vx = puntatore.vy = 0;
    var q = pezzoSotto(e.clientX, e.clientY, e.pointerType === "touch" ? 18 : 6);
    if (q) {
      presa = q;
      radice.classList.add("natale-trascina");
      if (e.cancelable) e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }
    tocca(e.clientX, e.clientY);
  }, { capture: true, passive: false });
  function su() { if (presa) lasciaPezzo(); }
  window.addEventListener("pointerup", su, { capture: true });
  window.addEventListener("pointercancel", su, { capture: true });
  // Sul telefono, mentre si tiene un pezzo, la pagina non deve scorrere.
  window.addEventListener("touchstart", function (e) {
    var t = e.touches && e.touches[0];
    if (acceso && t && pezzoSotto(t.clientX, t.clientY, 18) && e.cancelable) e.preventDefault();
  }, { passive: false });
  window.addEventListener("touchmove", function (e) { if (presa && e.cancelable) e.preventDefault(); }, { passive: false });
  // Un pezzo posato sopra un collegamento non lo deve aprire.
  var appenaPreso = false;
  window.addEventListener("pointerup", function () { if (presa) { appenaPreso = true; setTimeout(function () { appenaPreso = false; }, 0); } }, true);
  window.addEventListener("click", function (e) { if (appenaPreso) { e.preventDefault(); e.stopPropagation(); } }, true);

  var attesa = null;
  function riordina() {
    if (!acceso || !tela) return;
    clearTimeout(attesa);
    attesa = setTimeout(function () {
      var larga = W;
      dimensiona(); rileva();
      if (Math.abs(larga - W) > 40) popola();
    }, 150);
  }
  window.addEventListener("resize", riordina);
  window.addEventListener("scroll", function () { if (acceso && tela) rileva(); }, { passive: true });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) riparti(); });

  document.addEventListener("click", function (e) {
    var tasto = e.target.closest && e.target.closest("[data-natale-tasto]");
    if (tasto) imposta(!acceso);
  });

  function pronto() {
    radice.classList.toggle("natale", acceso);
    aggiornaTasti();
    if (acceso) avvia();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", pronto);
  else pronto();

  // Per i test nel browser.
  window.__natale = {
    imposta: imposta,
    stato: function () {
      var neve = 0;
      for (var i = 0; i < superfici.length; i++) for (var k = 0; k < superfici[i].pila.length; k++) neve += superfici[i].pila[k];
      return { acceso: acceso, fiocchi: fiocchi.length, superfici: superfici.length, neve: neve, pavimento: pavimento,
               pupazzi: pupazzi.map(function (p) {
                 return { x: p.x, base: p.base, intero: intero(p),
                          pezzi: p.pezzi.map(function (q) { var c = casa(q); return { tipo: q.tipo, x: q.x, y: q.y, r: q.r, posto: q.posto, casa: c, ammesso: ammesso(q) }; }) };
               }) };
    },
  };
})();
