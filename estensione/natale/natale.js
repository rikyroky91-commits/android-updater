/* IL TEMA NATALIZIO DI TUTTO IL SITO (02/10/2026, su richiesta).
 *
 * Un tasto nella testata, accanto a quello del tema scuro, lo accende e lo
 * spegne; la scelta resta nel browser (`mut-natale`). È separato dal ring
 * dei due lottatori: funziona su ogni pagina.
 *
 * Acceso:
 *   - nevica su tutta la finestra, a tre profondità, col vento che cambia; i
 *     fiocchi più grossi sono cristalli a sei punte che girano. Quelli vicini
 *     si posano sul bordo alto degli elementi della pagina (titoli, campi,
 *     tasti, tabelle, immagini) e ci si accumulano; il mucchio frana se
 *     diventa troppo ripido, luccica, e si spazza via col puntatore;
 *   - sotto gli elementi crescono piano i ghiaccioli: gocciolano, e toccati
 *     si staccano e cadono;
 *   - un albero addobbato coi regali sotto (un clic e si aprono in una
 *     pioggia di coriandoli) e dei pupazzi di neve stanno sul fondo: toccati
 *     col puntatore i pupazzi vanno in pezzi, e i pezzi si riprendono e si
 *     rimettono a posto uno alla volta (base, busto, testa, poi naso e
 *     cappello);
 *   - ogni tanto una slitta con le renne attraversa il cielo lasciando una
 *     scia di scintille, e agli angoli della finestra c'è la brina;
 *   - sul sito, cappellini rossi sulle faccine e su qualche lettera e una
 *     fila di lucine sotto la testata li fa lo stile (`html.natale`).
 *
 * FUORI DAL SITO (02/10/2026): lo stesso file è il cuore dell'estensione
 * «Page Snow» (`estensione/`). Lì `window.__nataleEstensione` dice dove
 * mettere il canvas (`radice`, uno shadow DOM) e se partire acceso; la neve
 * si posa su campi, tasti, immagini e titoli di qualunque pagina, i
 * cappellini e le lucine li disegna il canvas.
 *
 * Il canvas non riceve clic: la pagina sotto resta usabile. Solo un pezzo
 * di pupazzo o un regalo sotto il puntatore lo trattengono.
 */
(function () {
  "use strict";

  var est = window.__nataleEstensione || null;
  var radice = document.documentElement;
  var CHIAVE = "mut-natale";
  var acceso = false;
  if (est) acceso = est.acceso !== false;
  else { try { acceso = window.localStorage.getItem(CHIAVE) === "on"; } catch (e) { /* resta spento */ } }

  var tela = null, ctx = null, W = 0, H = 0, richiesta = null, passi = 0;
  var fiocchi = [], superfici = [], cumuli = new Map(), pupazzi = [], sbuffi = [];
  var ghiacci = new Map(), brillii = [], coriandoli = [], regali = [], cappelli = [], slitta = null, prossimaSlitta = 420;
  var pavimento = 0, vento = 0, raffica = 0, scuro = false;
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
    if (!est) { try { window.localStorage.setItem(CHIAVE, acceso ? "on" : "off"); } catch (e) { /* solo per questa pagina */ } }
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
  // Lo sfondo della pagina è scuro? Serve per il contorno dei fiocchi.
  function fondoScuro() {
    if (!est) return radice.getAttribute("data-tema") === "scuro";
    try {
      var nodi = [document.body, radice];
      for (var i = 0; i < nodi.length; i++) {
        var m = nodi[i] && window.getComputedStyle(nodi[i]).backgroundColor.match(/[\d.]+/g);
        if (m && (m.length < 4 || Number(m[3]) > 0.5)) return (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]) < 110;
      }
    } catch (e) { /* si resta sul chiaro */ }
    return false;
  }

  // --- Dove si posa la neve ---------------------------------------------
  var POSATOI = est
    ? "input:not([type=hidden]), button, [role=button], table, img, select, textarea, video, blockquote, pre"
    : "main input:not([type=hidden]), main button, main table, main img, main select, main textarea, " +
      ".pieduccio, [class*='scheda'], .tema-tasto, .conto";
  var TITOLI = est ? "h1, h2, h3" : "main h1, main h2";
  function visibile(r) { return r && r.width >= 14 && r.height >= 6 && r.bottom > 0 && r.top < H && r.right > 0 && r.left < W; }
  function rileva() {
    var nuove = [], nuoviCappelli = [];
    function aggiungi(chiave, r, tetto, elemento) {
      if (!visibile(r) || nuove.length > 70) return;
      var n = Math.max(2, Math.ceil(r.width / 5));
      var pila = cumuli.get(chiave);
      if (!pila || pila.length !== n) { pila = new Float32Array(n); cumuli.set(chiave, pila); }
      var s = { l: r.left, t: r.top, r: r.right, tetto: tetto, pila: pila, ghiacci: null, sotto: 0 };
      // I ghiaccioli: solo sotto gli elementi veri, abbastanza larghi e lontani dal fondo.
      if (elemento && r.width >= 50 && r.height >= 18 && r.bottom < pavimento - 12 && r.bottom < H - 4 && ghiacci.size < 16) {
        var g = ghiacci.get(chiave);
        if (!g) {
          g = [];
          var quanti = Math.max(2, Math.min(7, Math.round(r.width / 40)));
          for (var k = 0; k < quanti; k++) g.push({ u: (k + caso(0.2, 0.8)) / quanti, lung: 0, max: caso(5, 9 + Math.min(9, r.width / 40)), larg: caso(1.6, 2.8) });
          ghiacci.set(chiave, g);
        }
        s.ghiacci = g; s.sotto = r.bottom;
      } else if (elemento && ghiacci.has(chiave)) { s.ghiacci = ghiacci.get(chiave); s.sotto = r.bottom; }
      nuove.push(s);
    }
    // Il fondo: il bordo alto della striscia delle notizie, o il fondo della finestra.
    var barra = est ? null : document.querySelector(".ultimora-barra");
    var rb = barra && barra.getBoundingClientRect ? barra.getBoundingClientRect() : null;
    pavimento = rb && rb.top > 0 && rb.top < H ? rb.top : H;
    aggiungi("fondo", { left: 0, right: W, top: pavimento, bottom: pavimento + 10, width: W, height: 10 }, 18, false);
    var i, els = document.querySelectorAll(POSATOI);
    for (i = 0; i < els.length && i < 400; i++) {
      var el = els[i];
      if (el.closest && el.closest(".ring-pannello, .ultimora, [hidden]")) continue;
      var r = el.getBoundingClientRect();
      if (est && (r.width > W * 0.96 || r.height > H * 0.9)) continue;          // uno sfondo a tutta pagina non è un posatoio
      aggiungi(el, r, 9, true);
      // Fuori dal sito: un cappellino sulle immagini piccole e quadrate (facce, stemmi).
      if (est && el.tagName === "IMG" && nuoviCappelli.length < 8 && visibile(r) && r.width >= 28 && r.width <= 140 && r.height / r.width > 0.8 && r.height / r.width < 1.25) {
        nuoviCappelli.push({ x: r.left + r.width * 0.3, y: r.top + r.height * 0.04, s: r.width * 0.02 + 0.35, ang: -0.3 });
      }
    }
    // I titoli: riga per riga, larghi quanto il testo (non quanto la colonna).
    var titoli = document.querySelectorAll(TITOLI);
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
        // Fuori dal sito: un cappellino sulla prima lettera dei primi titoli.
        if (est && k === 0 && nuoviCappelli.length < 8 && visibile(riga) && riga.height >= 18) {
          nuoviCappelli.push({ x: riga.left + riga.height * 0.3, y: riga.top + riga.height * 0.2, s: riga.height * 0.022, ang: -0.28 });
        }
        // Il bordo alto del riquadro sta sopra le lettere: si scende all'altezza delle maiuscole.
        riga.top += riga.height * 0.2;
        aggiungi(titoli[i].tagName + i + ":" + k, riga, 6, false);
      }
    }
    superfici = nuove; cappelli = nuoviCappelli;
    scuro = fondoScuro();
    for (i = 0; i < pupazzi.length; i++) pupazzi[i].base = pavimento;
    for (i = 0; i < regali.length; i++) regali[i].base = pavimento;
  }

  // --- I fiocchi --------------------------------------------------------
  // Tre profondità in una sola: `z` va da 0 (lontano: piccolo, lento, tenue)
  // a 1 (vicino: grosso e veloce). Solo i vicini si posano sugli elementi.
  function nuovoFiocco(inAlto) {
    var z = Math.random(), r = 0.9 + z * z * 3.1;
    return { x: caso(-40, W + 40), y: inAlto ? caso(-H, 0) : caso(-20, -4), py: -30, vx: caso(-0.3, 0.3), vy: 0.6 + z * 1.9 + caso(0, 0.4),
             r: r, z: z, fase: caso(0, 6.28), cristallo: r > 2.6 && Math.random() < 0.65, ang: caso(0, 6.28), va: caso(-0.03, 0.03) };
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
    if (sbuffi.length > 140) return;
    sbuffi.push({ x: x, y: y, vx: vx + caso(-0.4, 0.4), vy: vy + caso(-0.6, 0.2), vita: 60, r: caso(1, 2.4) });
  }
  function brillio(x, y, colore) {
    if (brillii.length > 60) return;
    brillii.push({ x: x, y: y, vita: 34, max: 34, r: caso(2, 4), colore: colore || "#ffffff" });
  }
  // Il puntatore spazza via la neve posata e stacca i ghiaccioli.
  function spazza() {
    if (Math.abs(puntatore.vx) + Math.abs(puntatore.vy) < 1.5) return;
    for (var k = 0; k < superfici.length; k++) {
      var s = superfici[k];
      if (s.ghiacci && puntatore.x > s.l - 6 && puntatore.x < s.r + 6 && puntatore.y > s.sotto - 4 && puntatore.y < s.sotto + 26) {
        for (var g = 0; g < s.ghiacci.length; g++) {
          var gh = s.ghiacci[g], gx = s.l + gh.u * (s.r - s.l);
          if (gh.lung > 2.5 && Math.abs(puntatore.x - gx) < 7 && puntatore.y < s.sotto + gh.lung + 6) {
            // Si stacca e cade intero, poi ricresce da capo.
            sbuffi.push({ x: gx, y: s.sotto + gh.lung * 0.5, vx: puntatore.vx * 0.1, vy: 0.5, vita: 90, r: gh.larg, ghiacciolo: gh.lung });
            gh.lung = 0;
          }
        }
      }
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
  function aggiornaGhiaccioli() {
    for (var k = 0; k < superfici.length; k++) {
      var s = superfici[k];
      if (!s.ghiacci) continue;
      for (var g = 0; g < s.ghiacci.length; g++) {
        var gh = s.ghiacci[g];
        if (gh.lung < gh.max) gh.lung = Math.min(gh.max, gh.lung + 0.012);
        // Ogni tanto una goccia dalla punta.
        else if (!ridotto && Math.random() < 0.0012) sbuffi.push({ x: s.l + gh.u * (s.r - s.l), y: s.sotto + gh.lung, vx: 0, vy: 0.6, vita: 80, r: 1.1, goccia: true });
      }
    }
  }

  // --- I pupazzi di neve ------------------------------------------------
  // Cinque pezzi: base, busto (con braccia, sciarpa e bottoni), testa (con
  // gli occhi), naso e cappello. `hx`, `hy` sono il posto di ognuno rispetto
  // al punto d'appoggio del pupazzo.
  var ORDINE = { base: null, busto: "base", testa: "busto", naso: "testa", cappello: "testa" };
  var SCIARPE = [["#d8343f", "#8f1f28"], ["#2f8f5a", "#1c5a38"], ["#2f72e0", "#1d4a99"]];
  function nuovoPupazzo(x, scala) {
    var s = scala, pezzi = [
      { tipo: "base", r: 22 * s, hx: 0, hy: -21 * s },
      { tipo: "busto", r: 16 * s, hx: 0, hy: -54 * s },
      { tipo: "testa", r: 11 * s, hx: 0, hy: -77 * s },
      { tipo: "naso", r: 5 * s, hx: 0, hy: -76 * s },
      { tipo: "cappello", r: 9 * s, hx: 0, hy: -91 * s },
    ];
    var p = { x: x, base: pavimento, scala: s, pezzi: pezzi, verso: x > W / 2 ? -1 : 1, attendeUscita: false, festa: 0, sciarpa: SCIARPE[pupazzi.length % SCIARPE.length] };
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

  // --- I regali sotto l'albero ------------------------------------------
  var CARTE = [["#d8343f", "#ffd84a"], ["#2f8f5a", "#f4f1e6"], ["#2f72e0", "#ffcf3a"], ["#8a4fd0", "#f4f1e6"]];
  function nuovoRegalo(x, w, h, i) { return { x: x, w: w, h: h, base: pavimento, carta: CARTE[i % CARTE.length], salto: 0, fermo: 0 }; }
  function regaloSotto(x, y) {
    for (var i = 0; i < regali.length; i++) {
      var g = regali[i];
      if (x >= g.x - g.w / 2 - 2 && x <= g.x + g.w / 2 + 2 && y >= g.base - g.h - 6 && y <= g.base + 2) return g;
    }
    return null;
  }
  // Un regalo si apre: il coperchio salta e piovono coriandoli e stelline.
  function apri(g) {
    if (g.fermo > 0) return;
    g.salto = 46; g.fermo = 80;
    var colori = ["#d8343f", "#ffd84a", "#2f8f5a", "#2f72e0", "#f08a24", "#ffffff"];
    for (var i = 0; i < 26 && coriandoli.length < 140; i++) {
      coriandoli.push({ x: g.x + caso(-g.w * 0.3, g.w * 0.3), y: g.base - g.h, vx: caso(-2.6, 2.6), vy: -caso(3.5, 8), ang: caso(0, 6.28), va: caso(-0.3, 0.3),
                        vita: Math.round(caso(70, 120)), colore: colori[i % colori.length], w: caso(2.5, 4.5), h: caso(1.6, 3) });
    }
    for (i = 0; i < 5; i++) brillio(g.x + caso(-g.w, g.w), g.base - g.h - caso(6, 40), "#ffd84a");
  }

  // --- La slitta --------------------------------------------------------
  function partiSlitta() {
    var verso = Math.random() < 0.5 ? 1 : -1;
    slitta = { x: verso > 0 ? -220 : W + 220, y: caso(54, Math.max(60, Math.min(150, H * 0.2))), verso: verso, t: 0 };
  }
  function aggiornaSlitta() {
    if (!slitta) { if (!ridotto && passi >= prossimaSlitta) partiSlitta(); return; }
    slitta.t++; slitta.x += slitta.verso * 3.1;
    if (slitta.t % 3 === 0) brillio(slitta.x - slitta.verso * caso(70, 100), slitta.y + Math.sin(slitta.t * 0.05) * 9 + caso(2, 14), Math.random() < 0.5 ? "#ffd84a" : "#ffffff");
    if (slitta.x < -260 || slitta.x > W + 260) { slitta = null; prossimaSlitta = passi + Math.round(caso(1800, 3600)); }
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
      ctx.fillStyle = q.pup.sciarpa[0]; ctx.strokeStyle = q.pup.sciarpa[1]; ctx.lineWidth = 1;
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
      // Cappello a cilindro con la fascia e un rametto di agrifoglio.
      ctx.fillStyle = "#22262e"; ctx.fillRect(-12 * s, 4 * s, 24 * s, 3 * s);
      ctx.fillRect(-8 * s, -10 * s, 16 * s, 14 * s);
      ctx.fillStyle = q.pup.sciarpa[0]; ctx.fillRect(-8 * s, 0, 16 * s, 3.4 * s);
      tondo(-v * 4 * s, 0.6 * s, 1.5 * s, "#2f8f5a"); tondo(-v * 6.2 * s, 2 * s, 1.5 * s, "#2f8f5a"); tondo(-v * 5.2 * s, 1.6 * s, 1 * s, "#d8343f");
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
  // Un luccichio: una stella a quattro punte sottili.
  function scintilla(x, y, r, colore, alfa) {
    ctx.save(); ctx.globalAlpha = alfa; ctx.fillStyle = colore; ctx.beginPath();
    for (var i = 0; i < 8; i++) { var a = (i / 8) * Math.PI * 2, rr = i % 2 ? r * 0.22 : r; ctx[i ? "lineTo" : "moveTo"](x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  // L'albero: quattro piani a balze con la neve sopra, la ghirlanda, le palline e la stella.
  var PALLINE = [[-18, 22, "#d8343f"], [14, 26, "#ffcf3a"], [-6, 42, "#2f72e0"], [12, 50, "#d8343f"], [-8, 60, "#ffcf3a"], [4, 72, "#d8343f"], [-14, 34, "#f4f1e6"], [6, 36, "#8a4fd0"]];
  function disegnaAlbero(x, y, s) {
    ctx.fillStyle = "#6b4423"; ctx.strokeStyle = "#4a2e17"; ctx.lineWidth = 1;
    ctx.fillRect(x - 4.5 * s, y - 15 * s, 9 * s, 15 * s); ctx.strokeRect(x - 4.5 * s, y - 15 * s, 9 * s, 15 * s);
    var piani = [[0, 35, 27], [20, 29, 25], [38, 22, 23], [54, 15, 20]], i;
    for (i = 0; i < piani.length; i++) {
      var su = piani[i][0], largo = piani[i][1] * s, alto = piani[i][2] * s, yb = y - (14 + su) * s;
      var g = ctx.createLinearGradient(x - largo, 0, x + largo, 0);
      g.addColorStop(0, "#2f9152"); g.addColorStop(0.55, "#2a8249"); g.addColorStop(1, "#1f683a");
      ctx.fillStyle = g; ctx.strokeStyle = "#174d2b"; ctx.lineWidth = 1.2; ctx.lineJoin = "round";
      // Il bordo basso a balze.
      ctx.beginPath(); ctx.moveTo(x, yb - alto); ctx.lineTo(x - largo, yb);
      for (var k = 0; k < 4; k++) ctx.quadraticCurveTo(x - largo + (k + 0.5) * largo / 2, yb + 4.5 * s, x - largo + (k + 1) * largo / 2, yb);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      // La neve sul piano.
      ctx.fillStyle = "rgba(255,255,255,.92)"; ctx.beginPath();
      ctx.moveTo(x, yb - alto); ctx.lineTo(x - largo * 0.42, yb - alto * 0.55);
      ctx.quadraticCurveTo(x - largo * 0.2, yb - alto * 0.42, x, yb - alto * 0.52);
      ctx.quadraticCurveTo(x + largo * 0.2, yb - alto * 0.4, x + largo * 0.42, yb - alto * 0.55); ctx.closePath(); ctx.fill();
    }
    // La ghirlanda dorata, a festoni.
    ctx.strokeStyle = "#e9b93c"; ctx.lineWidth = 1.6 * s; ctx.lineCap = "round";
    for (i = 0; i < 3; i++) {
      var yg = y - (24 + i * 19) * s, lg = (27 - i * 7) * s;
      ctx.beginPath(); ctx.moveTo(x - lg, yg); ctx.quadraticCurveTo(x, yg + 9 * s, x + lg, yg - 3 * s); ctx.stroke();
    }
    for (i = 0; i < PALLINE.length; i++) {
      var accesa = (Math.floor(passi / 24) + i) % 3 !== 0, px = x + PALLINE[i][0] * s, py = y - PALLINE[i][1] * s;
      if (accesa) { ctx.save(); ctx.globalAlpha = 0.28; tondo(px, py, 5.2 * s, PALLINE[i][2]); ctx.restore(); }
      tondo(px, py, 2.7 * s, accesa ? PALLINE[i][2] : "#8a8a8a");
      tondo(px - 0.9 * s, py - 0.9 * s, 0.8 * s, "rgba(255,255,255,.85)");
    }
    // La stella, col suo alone che pulsa.
    var puls = 0.5 + 0.5 * Math.sin(passi * 0.08);
    ctx.save(); ctx.globalAlpha = 0.2 + 0.2 * puls; tondo(x, y - 95 * s, (10 + 3 * puls) * s, "#ffe27a"); ctx.restore();
    stella(x, y - 95 * s, 6.5 * s, "#ffd84a");
    scintilla(x, y - 95 * s, (9 + 4 * puls) * s, "#ffffff", 0.5 * puls);
  }
  function disegnaRegalo(g) {
    var w = g.w, h = g.h, x = g.x - w / 2, y = g.base - h;
    var k = g.salto > 0 ? Math.sin(Math.PI * g.salto / 46) : 0;         // quanto è alzato il coperchio
    ctx.save();
    ctx.fillStyle = g.carta[0]; ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.lineWidth = 1;
    ctx.fillRect(x, y, w, h); ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = g.carta[1]; ctx.fillRect(g.x - w * 0.09, y, w * 0.18, h);
    // Il coperchio, col fiocco: salta e ruota quando il regalo si apre.
    ctx.translate(g.x, y - 14 * k); ctx.rotate(-0.5 * k);
    ctx.fillStyle = g.carta[0]; ctx.fillRect(-w / 2 - 2, -h * 0.24, w + 4, h * 0.26); ctx.strokeRect(-w / 2 - 2, -h * 0.24, w + 4, h * 0.26);
    ctx.fillStyle = g.carta[1]; ctx.fillRect(-w * 0.09, -h * 0.24, w * 0.18, h * 0.26);
    ctx.beginPath(); ctx.ellipse(-w * 0.14, -h * 0.32, w * 0.15, h * 0.1, -0.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(w * 0.14, -h * 0.32, w * 0.15, h * 0.1, 0.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.restore();
  }
  // Un cappellino rosso col bordo e il pompon bianchi (fuori dal sito, su titoli e immagini).
  function disegnaCappello(c) {
    var s = c.s;
    ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.ang);
    ctx.fillStyle = "#d8343f"; ctx.strokeStyle = "#8f1f28"; ctx.lineWidth = 1; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(-9 * s, 0); ctx.quadraticCurveTo(-4 * s, -16 * s, 9 * s, -19 * s);
    ctx.quadraticCurveTo(15 * s, -14 * s, 16 * s, -6 * s); ctx.quadraticCurveTo(10 * s, -10 * s, 9 * s, 0); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "rgba(110,140,180,.8)";
    ctx.beginPath(); ctx.ellipse(0, 0.5 * s, 11 * s, 3.4 * s, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.arc(16.5 * s, -5 * s, 3.4 * s, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.restore();
  }
  // Le lucine: un filo che fa le onde in cima alla finestra, con le lampadine che si accendono a turno.
  var COLORI_LUCI = ["#e23b3b", "#f4b63a", "#3aa657", "#3a7be2", "#c05be0"];
  function disegnaLuci() {
    var passoPioli = 150, n = Math.max(2, Math.ceil(W / passoPioli)), largo = W / n, i;
    var yFilo = function (x) { var f = (x % largo) / largo; return 5 + 15 * Math.sin(Math.PI * f); };
    ctx.strokeStyle = scuro ? "#3d6b52" : "#1f4a32"; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(0, 5);
    for (var x = 0; x <= W; x += 8) ctx.lineTo(x, yFilo(x));
    ctx.stroke();
    var quante = Math.floor(W / 30);
    for (i = 0; i < quante; i++) {
      var lx = 15 + i * 30, ly = yFilo(lx) + 5, col = COLORI_LUCI[i % COLORI_LUCI.length];
      var k = ridotto ? 0.8 : 0.45 + 0.55 * Math.max(0, Math.sin(passi * 0.045 + i * 1.9));
      ctx.fillStyle = "#2b2f3a"; ctx.fillRect(lx - 1.6, ly - 5, 3.2, 3);
      ctx.save(); ctx.globalAlpha = 0.3 * k; tondo(lx, ly + 1, 8, col); ctx.restore();
      ctx.save(); ctx.globalAlpha = 0.45 + 0.55 * k; ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(lx, ly + 1, 2.7, 4, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      tondo(lx - 0.8, ly - 0.4, 0.8, "rgba(255,255,255," + (0.5 + 0.4 * k) + ")");
    }
  }
  // La brina ai quattro angoli della finestra.
  function disegnaBrina() {
    var r = Math.min(120, W * 0.2), angoli = [[0, 0], [W, 0], [0, H], [W, H]];
    for (var i = 0; i < 4; i++) {
      var x = angoli[i][0], y = angoli[i][1];
      var g = ctx.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, scuro ? "rgba(220,236,250,.34)" : "rgba(190,220,245,.5)"); g.addColorStop(1, "rgba(200,225,245,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      // Qualche ago di ghiaccio, corto e tenue: brina, non crepe.
      ctx.strokeStyle = scuro ? "rgba(235,245,255,.22)" : "rgba(150,190,225,.34)"; ctx.lineWidth = 0.8; ctx.lineCap = "round"; ctx.beginPath();
      for (var k = 0; k < 5; k++) {
        var a = (x ? Math.PI : 0) + (y ? -1 : 1) * (x ? -1 : 1) * (0.16 + k * 0.31), l = r * (0.24 + 0.08 * ((k * 7) % 3)), d0 = r * 0.12;
        var ax = x + Math.cos(a) * d0, ay = y + Math.sin(a) * d0, bx = x + Math.cos(a) * (d0 + l), by = y + Math.sin(a) * (d0 + l);
        ctx.moveTo(ax, ay); ctx.lineTo(bx, by);
        for (var z = 0; z < 2; z++) {
          var t = 0.45 + z * 0.3, mx = ax + (bx - ax) * t, my = ay + (by - ay) * t;
          ctx.moveTo(mx, my); ctx.lineTo(mx + Math.cos(a + 0.8) * l * 0.22, my + Math.sin(a + 0.8) * l * 0.22);
          ctx.moveTo(mx, my); ctx.lineTo(mx + Math.cos(a - 0.8) * l * 0.22, my + Math.sin(a - 0.8) * l * 0.22);
        }
      }
      ctx.stroke();
    }
  }
  function disegnaRenna(x, y, v, fase) {
    var marrone = "#8a5a33", scuroR = "#5e3b20";
    ctx.strokeStyle = scuroR; ctx.lineWidth = 1.6; ctx.lineCap = "round"; ctx.beginPath();
    for (var k = 0; k < 4; k++) {
      var gx = x + v * (k < 2 ? 8 : -8) + (k % 2 ? 2 : -2), a = Math.sin(fase + k * 1.6) * 0.7 * v;
      ctx.moveTo(gx, y + 3); ctx.lineTo(gx + Math.sin(a) * 9, y + 3 + Math.cos(a) * 9);
    }
    ctx.stroke();
    ctx.fillStyle = marrone; ctx.beginPath(); ctx.ellipse(x, y, 12, 5.4, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(x + v * 13, y - 7, 4.6, 3.4, v * -0.5, 0, Math.PI * 2); ctx.fill();
    ctx.lineWidth = 3; ctx.strokeStyle = marrone; ctx.beginPath(); ctx.moveTo(x + v * 9, y - 2); ctx.lineTo(x + v * 12, y - 6); ctx.stroke();
    ctx.lineWidth = 1.1; ctx.strokeStyle = scuroR; ctx.beginPath();
    ctx.moveTo(x + v * 12, y - 10); ctx.lineTo(x + v * 10, y - 16); ctx.moveTo(x + v * 11, y - 13); ctx.lineTo(x + v * 14, y - 16);
    ctx.moveTo(x + v * 14, y - 10); ctx.lineTo(x + v * 15, y - 15); ctx.stroke();
    tondo(x - v * 12, y - 2, 1.8, "#f4f1e6");
  }
  function disegnaSlitta() {
    var v = slitta.verso, x = slitta.x, y = slitta.y + Math.sin(slitta.t * 0.05) * 9, fase = slitta.t * 0.35;
    ctx.save();
    // Le redini.
    ctx.strokeStyle = "#e9b93c"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x - v * 12, y - 4); ctx.lineTo(x + v * 70, y - 2); ctx.stroke();
    disegnaRenna(x + v * 74, y + Math.sin(fase) * 2, v, fase);
    disegnaRenna(x + v * 40, y + Math.sin(fase + 1.5) * 2, v, fase + 1.5);
    // La slitta: il pattino dorato, la scocca rossa, il sacco.
    ctx.strokeStyle = "#e9b93c"; ctx.lineWidth = 2; ctx.lineCap = "round"; ctx.beginPath();
    ctx.moveTo(x - v * 26, y + 12); ctx.lineTo(x + v * 12, y + 12); ctx.quadraticCurveTo(x + v * 22, y + 12, x + v * 22, y + 3); ctx.stroke();
    ctx.fillStyle = "#c8102e"; ctx.strokeStyle = "#7d0a1c"; ctx.lineWidth = 1; ctx.beginPath();
    ctx.moveTo(x - v * 24, y - 6); ctx.lineTo(x + v * 4, y - 2); ctx.quadraticCurveTo(x + v * 16, y - 2, x + v * 17, y - 9);
    ctx.lineTo(x + v * 19, y + 8); ctx.lineTo(x - v * 24, y + 8); ctx.closePath(); ctx.fill(); ctx.stroke();
    tondo(x - v * 17, y - 9, 8, "#7a5230");
    // Chi guida: cappotto rosso, barba bianca, cappello.
    tondo(x - v * 3, y - 7, 6.5, "#d8343f"); tondo(x - v * 1, y - 15, 4, "#f0c9a4"); tondo(x + v * 0.5, y - 12.5, 3.2, "#ffffff");
    ctx.fillStyle = "#d8343f"; ctx.beginPath(); ctx.moveTo(x - v * 5, y - 17); ctx.lineTo(x + v * 3, y - 17); ctx.lineTo(x - v * 6, y - 25); ctx.closePath(); ctx.fill();
    tondo(x - v * 6.5, y - 25, 1.8, "#ffffff");
    ctx.restore();
  }
  // Un fiocco a cristallo: sei bracci con le barbe.
  function cristallo(f, colore, spessore) {
    ctx.strokeStyle = colore; ctx.lineWidth = spessore; ctx.lineCap = "round"; ctx.beginPath();
    for (var k = 0; k < 6; k++) {
      var a = f.ang + k * Math.PI / 3, c = Math.cos(a), s = Math.sin(a), R = f.r * 1.9;
      ctx.moveTo(f.x, f.y); ctx.lineTo(f.x + c * R, f.y + s * R);
      var mx = f.x + c * R * 0.6, my = f.y + s * R * 0.6;
      ctx.moveTo(mx, my); ctx.lineTo(mx + Math.cos(a + 0.9) * R * 0.32, my + Math.sin(a + 0.9) * R * 0.32);
      ctx.moveTo(mx, my); ctx.lineTo(mx + Math.cos(a - 0.9) * R * 0.32, my + Math.sin(a - 0.9) * R * 0.32);
    }
    ctx.stroke();
  }
  function profiloNeve(s) {
    var pila = s.pila, n = pila.length, passo = (s.r - s.l) / n;
    ctx.beginPath(); ctx.moveTo(s.l, s.t + 1);
    var px = s.l, py = s.t - pila[0] * 0.5;
    ctx.lineTo(px, py);
    for (var k = 0; k < n; k++) {
      var x = s.l + (k + 0.5) * passo, y = s.t - pila[k];
      ctx.quadraticCurveTo(px, py, (px + x) / 2, (py + y) / 2);
      px = x; py = y;
    }
    ctx.quadraticCurveTo(px, py, s.r, s.t - pila[n - 1] * 0.5);
    ctx.lineTo(s.r, s.t + 1);
  }

  function disegna() {
    ctx.clearRect(0, 0, W, H);
    var i, k, f;
    var stretto = W < 640, sA = stretto ? 0.62 : 1;
    var bordoNeve = scuro ? "rgba(190,210,235,.7)" : "rgba(110,140,180,.75)";
    disegnaBrina();
    // I fiocchi lontani stanno dietro a tutto.
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = scuro ? "rgba(200,220,245,.25)" : "rgba(90,125,170,.42)"; ctx.lineWidth = 0.7;
    ctx.globalAlpha = 0.7;
    for (i = 0; i < fiocchi.length; i++) { f = fiocchi[i]; if (f.z >= 0.35) continue; ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); }
    ctx.globalAlpha = 1;
    if (slitta) disegnaSlitta();
    disegnaAlbero(stretto ? 30 : 48, pavimento, stretto ? sA : 0.9);
    for (i = 0; i < regali.length; i++) disegnaRegalo(regali[i]);
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
    // I ghiaccioli sotto gli elementi.
    for (i = 0; i < superfici.length; i++) {
      var sg = superfici[i];
      if (!sg.ghiacci) continue;
      for (k = 0; k < sg.ghiacci.length; k++) {
        var gh = sg.ghiacci[k];
        if (gh.lung < 1) continue;
        var gx = sg.l + gh.u * (sg.r - sg.l);
        ctx.fillStyle = "rgba(214,236,250,.88)"; ctx.strokeStyle = "rgba(110,150,190,.85)"; ctx.lineWidth = 0.8; ctx.lineJoin = "round";
        ctx.beginPath(); ctx.moveTo(gx - gh.larg, sg.sotto); ctx.lineTo(gx + gh.larg, sg.sotto); ctx.lineTo(gx, sg.sotto + gh.lung); ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 0.7; ctx.beginPath(); ctx.moveTo(gx - gh.larg * 0.35, sg.sotto + 1); ctx.lineTo(gx - 0.2, sg.sotto + gh.lung * 0.7); ctx.stroke();
      }
    }
    // La neve posata: un profilo morbido, bianco, col bordo e un'ombra al piede.
    ctx.lineJoin = "round";
    for (i = 0; i < superfici.length; i++) {
      var s = superfici[i], pila = s.pila, n = pila.length, vuota = true;
      for (k = 0; k < n; k++) if (pila[k] > 0.4) { vuota = false; break; }
      if (vuota) continue;
      profiloNeve(s); ctx.closePath(); ctx.fillStyle = "#ffffff"; ctx.fill();
      ctx.strokeStyle = bordoNeve; ctx.lineWidth = 1.1; profiloNeve(s); ctx.stroke();
      ctx.strokeStyle = "rgba(150,180,215,.45)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(s.l + 2, s.t + 0.5); ctx.lineTo(s.r - 2, s.t + 0.5); ctx.stroke();
    }
    if (est) { for (i = 0; i < cappelli.length; i++) disegnaCappello(cappelli[i]); disegnaLuci(); }
    // I fiocchi vicini, gli sbuffi, i coriandoli, i luccichii.
    for (i = 0; i < fiocchi.length; i++) {
      f = fiocchi[i];
      if (f.z < 0.35) continue;
      if (f.cristallo) {
        if (!scuro) cristallo(f, "rgba(90,125,170,.7)", 2);
        cristallo(f, "#ffffff", 1.05);
      } else {
        ctx.fillStyle = "#ffffff"; ctx.strokeStyle = scuro ? "rgba(200,220,245,.35)" : "rgba(90,125,170,.6)"; ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
    }
    for (i = 0; i < sbuffi.length; i++) {
      var b = sbuffi[i];
      ctx.globalAlpha = Math.min(1, b.vita / 20);
      if (b.ghiacciolo) {
        ctx.fillStyle = "rgba(214,236,250,.9)"; ctx.strokeStyle = "rgba(110,150,190,.85)"; ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.moveTo(b.x - b.r, b.y - b.ghiacciolo / 2); ctx.lineTo(b.x + b.r, b.y - b.ghiacciolo / 2); ctx.lineTo(b.x, b.y + b.ghiacciolo / 2); ctx.closePath(); ctx.fill(); ctx.stroke();
      } else if (b.goccia) {
        tondo(b.x, b.y, b.r, "rgba(150,195,235,.9)");
      } else {
        ctx.fillStyle = "#ffffff"; ctx.strokeStyle = scuro ? "rgba(200,220,245,.35)" : "rgba(90,125,170,.6)"; ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    for (i = 0; i < coriandoli.length; i++) {
      var c = coriandoli[i];
      ctx.save(); ctx.globalAlpha = Math.min(1, c.vita / 20); ctx.translate(c.x, c.y); ctx.rotate(c.ang);
      ctx.fillStyle = c.colore; ctx.fillRect(-c.w / 2, -c.h / 2, c.w, c.h); ctx.restore();
    }
    for (i = 0; i < brillii.length; i++) {
      var br = brillii[i], kb = Math.sin(Math.PI * br.vita / br.max);
      scintilla(br.x, br.y, br.r * (0.5 + kb), br.colore, kb);
    }
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
      f.x += f.vx + vento * (0.4 + 0.6 * f.z) + Math.sin(f.fase + passi * 0.03) * 0.35; f.y += f.vy; f.ang += f.va;
      var posato = false;
      // Solo i fiocchi vicini si posano: quelli lontani passano dietro.
      for (var k = 0; f.z >= 0.35 && k < superfici.length; k++) {
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
    for (i = 0; i < sbuffi.length; i++) {
      var b = sbuffi[i];
      b.x += b.vx + (b.ghiacciolo || b.goccia ? 0 : vento * 0.5); b.y += b.vy; b.vy += b.ghiacciolo || b.goccia ? 0.22 : 0.06; b.vita--;
      if ((b.ghiacciolo || b.goccia) && b.y > pavimento - 2) {
        b.vita = 0;
        if (b.ghiacciolo) for (var z = 0; z < 4; z++) sbuffo(b.x, pavimento - 2, caso(-1.4, 1.4), -caso(0.5, 1.8));
      }
    }
    if (sbuffi.length && passi % 10 === 0) sbuffi = sbuffi.filter(function (b2) { return b2.vita > 0; });
    for (i = 0; i < coriandoli.length; i++) {
      var c = coriandoli[i];
      c.x += c.vx; c.y += c.vy; c.vy += 0.16; c.vx *= 0.985; c.ang += c.va; c.vita--;
      if (c.y > pavimento - 1) { c.y = pavimento - 1; c.vy = 0; c.vx *= 0.7; c.va = 0; }
    }
    if (coriandoli.length && passi % 10 === 0) coriandoli = coriandoli.filter(function (c2) { return c2.vita > 0; });
    for (i = 0; i < brillii.length; i++) brillii[i].vita--;
    if (brillii.length && passi % 10 === 0) brillii = brillii.filter(function (b3) { return b3.vita > 0; });
    // La neve posata luccica qua e là.
    if (!ridotto && passi % 9 === 0 && superfici.length) {
      var sl = superfici[Math.floor(Math.random() * superfici.length)], cl = Math.floor(Math.random() * sl.pila.length);
      if (sl.pila[cl] > 2) brillio(sl.l + (cl + 0.5) * (sl.r - sl.l) / sl.pila.length, sl.t - sl.pila[cl] * caso(0.3, 0.9));
    }
    for (i = 0; i < regali.length; i++) { if (regali[i].salto > 0) regali[i].salto--; if (regali[i].fermo > 0) regali[i].fermo--; }
    aggiornaGhiaccioli();
    aggiornaSlitta();
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
    var quanti = ridotto ? 45 : Math.max(80, Math.min(300, Math.round(W * H / 4000)));
    fiocchi = [];
    for (var i = 0; i < quanti; i++) fiocchi.push(nuovoFiocco(true));
    pupazzi = [];
    var stretto = W < 640, s = stretto ? 0.62 : 1;
    // Fuori dal sito in basso a destra c'è il tasto dell'estensione: il pupazzo sta un po' più in qua.
    pupazzi.push(nuovoPupazzo(W - (stretto ? 46 : est ? 150 : 96), s));
    if (W > 1100) pupazzi.push(nuovoPupazzo(est ? 190 : 128, 0.8));       // solo se c'è margine accanto alla colonna
    // I regali ai piedi dell'albero.
    regali = [];
    var xa = stretto ? 30 : 48, k = stretto ? 0.62 : 0.9;
    regali.push(nuovoRegalo(xa - 20 * k, 17 * k, 13 * k, 0), nuovoRegalo(xa + 21 * k, 20 * k, 16 * k, 1));
    if (!stretto) regali.push(nuovoRegalo(xa + 44, 15, 12, 2));
  }
  function avvia() {
    if (!tela) {
      tela = document.createElement("canvas");
      tela.className = "natale-tela"; tela.setAttribute("aria-hidden", "true");
      (est && est.radice ? est.radice : document.body).appendChild(tela);
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
    ghiacci = new Map(); brillii = []; coriandoli = []; regali = []; cappelli = []; slitta = null; prossimaSlitta = passi + 420;
  }

  // --- Puntatore --------------------------------------------------------
  // Quello che è dell'estensione (il suo tasto) non si tocca.
  function mio(e) { return !!(est && est.ospite && e.composedPath && e.composedPath().indexOf(est.ospite) >= 0); }
  window.addEventListener("pointermove", function (e) {
    if (!acceso) return;
    puntatore.vx = e.clientX - puntatore.x; puntatore.vy = e.clientY - puntatore.y;
    puntatore.x = e.clientX; puntatore.y = e.clientY;
    if (Math.abs(puntatore.vx) > 80 || Math.abs(puntatore.vy) > 80) { puntatore.vx = 0; puntatore.vy = 0; }
    if (presa) { if (e.cancelable) e.preventDefault(); return; }
    tocca(e.clientX, e.clientY);
    if (e.pointerType !== "touch") radice.classList.toggle("natale-presa", !!pezzoSotto(e.clientX, e.clientY, 6) || !!regaloSotto(e.clientX, e.clientY));
  }, { capture: true, passive: false });
  window.addEventListener("pointerdown", function (e) {
    if (!acceso || (e.button !== undefined && e.button > 0) || mio(e)) return;
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
    var g = regaloSotto(e.clientX, e.clientY);
    if (g) { apri(g); appenaPreso = true; setTimeout(function () { appenaPreso = false; }, 400); if (e.cancelable) e.preventDefault(); e.stopImmediatePropagation(); return; }
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
  // Un pezzo posato (o un regalo aperto) sopra un collegamento non lo deve aprire.
  var appenaPreso = false;
  window.addEventListener("pointerup", function () { if (presa) { appenaPreso = true; setTimeout(function () { appenaPreso = false; }, 0); } }, true);
  window.addEventListener("click", function (e) { if (appenaPreso && !mio(e)) { e.preventDefault(); e.stopPropagation(); } }, true);

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
    acceso: function () { return acceso; },
    // Solo per i test: fa partire subito la slitta, apre un regalo.
    slitta: function () { partiSlitta(); },
    apri: function (i) { if (regali[i || 0]) apri(regali[i || 0]); },
    stato: function () {
      var neve = 0, ghiaccioli = 0;
      for (var i = 0; i < superfici.length; i++) {
        for (var k = 0; k < superfici[i].pila.length; k++) neve += superfici[i].pila[k];
        if (superfici[i].ghiacci) for (k = 0; k < superfici[i].ghiacci.length; k++) if (superfici[i].ghiacci[k].lung > 1) ghiaccioli++;
      }
      return { acceso: acceso, fiocchi: fiocchi.length, cristalli: fiocchi.filter(function (f) { return f.cristallo; }).length,
               superfici: superfici.length, neve: neve, ghiaccioli: ghiaccioli, pavimento: pavimento, scuro: scuro,
               regali: regali.map(function (g) { return { x: g.x, y: g.base - g.h / 2, aperto: g.salto > 0 }; }),
               coriandoli: coriandoli.length, brillii: brillii.length, cappelli: cappelli.length, slitta: slitta ? { x: slitta.x, y: slitta.y } : null,
               pupazzi: pupazzi.map(function (p) {
                 return { x: p.x, base: p.base, intero: intero(p),
                          pezzi: p.pezzi.map(function (q) { var c = casa(q); return { tipo: q.tipo, x: q.x, y: q.y, r: q.r, posto: q.posto, casa: c, ammesso: ammesso(q) }; }) };
               }) };
    },
  };
})();
