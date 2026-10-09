/* IL TEMA DI HALLOWEEN DI TUTTO IL SITO (09/10/2026, su richiesta).
 *
 * Riccardo: «crea un tema halloween che è attivato automaticamente nel sito.
 * Con zucche, luci e zombie tipiche e mani senza arti che camminano in giro,
 * tema scuro attivato di standard».
 *
 * QUANDO: si accende da solo dal 1° ottobre al 2 novembre (la data è quella
 * del browser). Il tasto con la zucca nella testata lo spegne e lo riaccende;
 * spento in stagione resta spento fino alla stagione dopo (`mut-halloween`
 * = "off-2026"), acceso fuori stagione resta acceso fino a fine anno
 * ("on-2026"). `?halloween=1` (o `=0`) nell'indirizzo lo forza per quella
 * pagina. La classe `html.halloween` e il tema scuro di partenza li mette lo
 * script in testa a `base.html`, prima del primo disegno (chi ha scelto il
 * chiaro col suo tasto lo tiene); qui si disegna e si gestisce il tasto.
 *
 * ACCESO, su un canvas sopra la pagina che non riceve clic:
 *   - zucche intagliate sul fondo della finestra e sopra qualche elemento della
 *     pagina, con la candela che tremola dentro;
 *   - una fila di lucine arancio, viola e verdi appesa sotto la testata, che si
 *     accendono a onde;
 *   - zombie che attraversano il fondo della finestra, strascicando i piedi, a
 *     braccia tese;
 *   - mani senza braccio che zampettano sulle dita sul fondo e sugli elementi:
 *     si fermano a tamburellare, saltano da un elemento all'altro e scappano
 *     dal puntatore;
 *   - pipistrelli ogni tanto, nebbia bassa sul fondo, ragnatele negli angoli.
 * Con «meno movimento» restano zucche, lucine e ragnatele, ferme.
 *
 * Tutti i disegni sono nostri.
 */
(function () {
  "use strict";

  var radice = document.documentElement;
  var CHIAVE = "mut-halloween";
  var ridotto = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // La stagione: dal 1° ottobre al 2 novembre.
  function inStagione(d) { var m = d.getMonth(), g = d.getDate(); return m === 9 || (m === 10 && g <= 2); }
  function decidi(d, salvata, indirizzo) {
    var forza = /[?&]halloween=(1|0)\b/.exec(indirizzo || "");
    if (forza) return forza[1] === "1";
    var anno = d.getFullYear();
    if (salvata === "off-" + anno && inStagione(d)) return false;
    if (salvata === "on-" + anno) return true;
    return inStagione(d);
  }
  var salvata = null;
  try { salvata = window.localStorage.getItem(CHIAVE); } catch (e) { /* niente scelta */ }
  var acceso = decidi(new Date(), salvata, window.location ? window.location.search : "");

  var tela = null, ctx = null, W = 0, H = 0, richiesta = null, passi = 0;
  var pavimento = 0, sottoTestata = 0, superfici = [];
  var zucche = [], zombie = [], mani = [], pipistrelli = [], nebbia = [];
  var prossimoZombie = 240, prossimoPipistrello = 300;
  var puntatore = { x: -999, y: -999 };

  function caso(a, b) { return a + Math.random() * (b - a); }

  // --- Il tasto ---------------------------------------------------------
  function aggiornaTasti() {
    var tasti = document.querySelectorAll ? document.querySelectorAll("[data-halloween-tasto]") : [];
    for (var i = 0; i < tasti.length; i++) {
      tasti[i].setAttribute("aria-pressed", acceso ? "true" : "false");
      tasti[i].setAttribute("title", acceso ? "Spegni il tema di Halloween" : "Accendi il tema di Halloween");
    }
  }
  function imposta(nuovo) {
    acceso = !!nuovo;
    var d = new Date(), anno = d.getFullYear();
    try {
      if (acceso === inStagione(d)) window.localStorage.removeItem(CHIAVE);
      else window.localStorage.setItem(CHIAVE, (acceso ? "on-" : "off-") + anno);
    } catch (e) { /* solo per questa pagina */ }
    radice.classList.toggle("halloween", acceso);
    aggiornaTasti();
    try { window.dispatchEvent(new CustomEvent("mut:halloween", { detail: { acceso: acceso } })); } catch (e) { /* pazienza */ }
    if (acceso) avvia(); else spegni();
  }

  // --- Il canvas e dove si sta ------------------------------------------
  function dimensiona() {
    var rapporto = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    tela.width = Math.floor(W * rapporto); tela.height = Math.floor(H * rapporto);
    tela.style.width = W + "px"; tela.style.height = H + "px";
    ctx.setTransform(rapporto, 0, 0, rapporto, 0, 0);
  }
  var POSATOI = "main input:not([type=hidden]), main button, main table, .pieduccio, [class*='scheda'], .conto";
  function rileva() {
    // Il fondo: il bordo alto della striscia delle notizie, o il fondo della finestra.
    var barra = document.querySelector(".ultimora-barra");
    var rb = barra && barra.getBoundingClientRect ? barra.getBoundingClientRect() : null;
    pavimento = rb && rb.top > 0 && rb.top < H ? rb.top : H;
    var testa = document.querySelector(".testata");
    var rt = testa && testa.getBoundingClientRect ? testa.getBoundingClientRect() : null;
    sottoTestata = rt ? Math.max(0, rt.bottom) : 0;
    var nuove = [{ el: "fondo", l: 0, r: W, t: pavimento }];
    var els = document.querySelectorAll ? document.querySelectorAll(POSATOI) : [];
    for (var i = 0; i < els.length && nuove.length < 30; i++) {
      var el = els[i];
      if (el.closest && el.closest(".ring-pannello, .ultimora, [hidden], .testata")) continue;
      var r = el.getBoundingClientRect();
      if (r.width < 60 || r.height < 12 || r.top < sottoTestata + 60 || r.top > pavimento - 20 || r.right < 0 || r.left > W) continue;
      nuove.push({ el: el, l: r.left, r: r.right, t: r.top });
    }
    superfici = nuove;
  }
  function superficie(el) {
    for (var i = 0; i < superfici.length; i++) if (superfici[i].el === el) return superfici[i];
    return null;
  }

  // --- Chi popola la pagina ---------------------------------------------
  function popola() {
    var stretto = W < 640;
    zucche = [];
    // Sul fondo: due o tre zucche agli angoli, di misure diverse.
    zucche.push({ el: "fondo", u: stretto ? 0.06 : 0.035, r: stretto ? 15 : 22, fase: caso(0, 6), faccia: 0 });
    zucche.push({ el: "fondo", u: stretto ? 0.16 : 0.08, r: stretto ? 10 : 14, fase: caso(0, 6), faccia: 1 });
    if (!stretto) zucche.push({ el: "fondo", u: 0.955, r: 19, fase: caso(0, 6), faccia: 2 });
    // Sopra gli elementi: qualche zucchetta.
    for (var i = 1, n = 0; i < superfici.length && n < (stretto ? 2 : 4); i += 2, n++) {
      zucche.push({ el: superfici[i].el, u: caso(0.75, 0.92), r: caso(8, 11), fase: caso(0, 6), faccia: n % 3 });
    }
    mani = [];
    var quante = ridotto ? 0 : stretto ? 2 : 4;
    for (i = 0; i < quante; i++) {
      var s = i < 2 || superfici.length < 2 ? superfici[0] : superfici[1 + Math.floor(Math.random() * (superfici.length - 1))];
      mani.push(nuovaMano(s, caso(0.1, 0.9)));
    }
    zombie = []; pipistrelli = [];
    nebbia = [];
    for (i = 0; i < (stretto ? 4 : 7); i++) nebbia.push({ x: caso(0, W), r: caso(60, 140), v: caso(0.1, 0.35) * (Math.random() < 0.5 ? -1 : 1), a: caso(0.05, 0.11) });
    prossimoZombie = passi + 120;
  }
  function nuovaMano(s, u) {
    return { el: s.el, x: s.l + (s.r - s.l) * u, y: s.t, dir: Math.random() < 0.5 ? -1 : 1, v: caso(0.7, 1.3), passo: caso(0, 6),
             ferma: 0, tamburo: 0, scappa: 0, salto: null, pelle: ["#9fb59a", "#b7c4a8", "#a6a3b8"][Math.floor(Math.random() * 3)], s: caso(1.5, 1.9) * (W < 640 ? 0.8 : 1) };
  }
  function nuovoZombie() {
    var da = Math.random() < 0.5 ? -1 : 1, stretto = W < 640;
    zombie.push({ x: da < 0 ? -40 : W + 40, dir: -da, v: caso(0.35, 0.6), fase: caso(0, 6), s: stretto ? 0.75 : caso(0.95, 1.15),
                  toni: [["#7d8fa6", "#4b5a70"], ["#a08670", "#6a5444"], ["#7a9a78", "#4a6a4c"], ["#9a7da0", "#644a6a"]][Math.floor(Math.random() * 4)],
                  occhio: Math.random() < 0.5 ? 1 : -1, sosta: 0 });
  }
  function nuovoPipistrello() {
    var da = Math.random() < 0.5 ? -1 : 1;
    pipistrelli.push({ x: da < 0 ? -30 : W + 30, y: caso(sottoTestata + 40, Math.max(sottoTestata + 60, pavimento * 0.55)), dir: -da, v: caso(2.2, 3.4), fase: caso(0, 6), s: caso(0.7, 1.1) });
  }

  // --- Il passo ---------------------------------------------------------
  function passo() {
    passi++;
    var i;
    // Gli zombie: uno alla volta (due sui computer), ogni dieci-venti secondi.
    if (passi >= prossimoZombie && zombie.length < (W < 640 ? 1 : 2)) { nuovoZombie(); prossimoZombie = passi + Math.round(caso(600, 1200)); }
    for (i = zombie.length - 1; i >= 0; i--) {
      var z = zombie[i];
      if (z.sosta > 0) z.sosta--;
      else { z.x += z.dir * z.v; z.fase += 0.07 + z.v * 0.05; if (Math.random() < 0.002) z.sosta = Math.round(caso(60, 140)); }
      if (z.x < -60 || z.x > W + 60) zombie.splice(i, 1);
    }
    // Le mani.
    for (i = 0; i < mani.length; i++) muoviMano(mani[i]);
    // I pipistrelli.
    if (passi >= prossimoPipistrello) {
      var n = 1 + Math.floor(Math.random() * 3);
      for (i = 0; i < n; i++) nuovoPipistrello();
      prossimoPipistrello = passi + Math.round(caso(420, 900));
    }
    for (i = pipistrelli.length - 1; i >= 0; i--) {
      var p = pipistrelli[i];
      p.x += p.dir * p.v; p.fase += 0.35; p.y += Math.sin(p.fase * 0.3) * 0.9;
      if (p.x < -50 || p.x > W + 50) pipistrelli.splice(i, 1);
    }
    for (i = 0; i < nebbia.length; i++) { var q = nebbia[i]; q.x += q.v; if (q.x < -q.r) q.x = W + q.r; if (q.x > W + q.r) q.x = -q.r; }
  }
  function muoviMano(m) {
    if (m.salto) {
      // In volo da un elemento all'altro: una parabola.
      var S = m.salto; S.t++;
      var u = Math.min(1, S.t / S.dur);
      m.x = S.x0 + (S.x1 - S.x0) * u; m.y = S.y0 + (S.y1 - S.y0) * u - Math.sin(Math.PI * u) * S.h;
      if (u >= 1) { m.salto = null; m.el = S.el; m.y = S.y1; m.ferma = 20; }
      return;
    }
    var s = superficie(m.el) || superfici[0];
    if (!s) return;
    if (s.el !== m.el) m.el = s.el;
    m.y = s.t;
    // Il puntatore vicino: scappa di corsa dall'altra parte.
    var dx = m.x - puntatore.x, dy = m.y - puntatore.y;
    if (Math.abs(dx) < 70 && Math.abs(dy) < 50 && m.scappa <= 0) { m.scappa = 50; m.dir = dx >= 0 ? 1 : -1; m.ferma = 0; m.tamburo = 0; }
    if (m.scappa > 0) m.scappa--;
    if (m.ferma > 0) { m.ferma--; if (m.tamburo > 0) m.tamburo--; return; }
    var v = m.v * (m.scappa > 0 ? 3 : 1);
    m.x += m.dir * v; m.passo += 0.22 * v;
    // Ogni tanto si ferma a tamburellare con le dita.
    if (m.scappa <= 0 && Math.random() < 0.004) { m.ferma = Math.round(caso(70, 150)); m.tamburo = m.ferma; return; }
    // In fondo all'elemento: si gira, o salta (giù sul fondo, o su un altro elemento).
    if (m.x < s.l + 8 || m.x > s.r - 8) {
      m.x = Math.max(s.l + 8, Math.min(s.r - 8, m.x));
      if (superfici.length > 1 && Math.random() < 0.45) {
        var meta = s.el === "fondo" ? superfici[1 + Math.floor(Math.random() * (superfici.length - 1))] : (Math.random() < 0.6 ? superfici[0] : superfici[Math.floor(Math.random() * superfici.length)]);
        if (meta && meta !== s) {
          var x1 = Math.max(meta.l + 12, Math.min(meta.r - 12, m.x + m.dir * caso(20, 120)));
          m.salto = { t: 0, dur: Math.round(caso(40, 60)), x0: m.x, y0: m.y, x1: x1, y1: meta.t, h: Math.max(40, (m.y - meta.t) + 50), el: meta.el };
          m.dir = x1 >= m.x ? 1 : -1;
          return;
        }
      }
      m.dir = -m.dir;
    }
  }

  // --- I disegni --------------------------------------------------------
  function disegnaZucca(x, y, r, fase, faccia) {
    var fiamma = 0.75 + 0.25 * Math.sin(passi * 0.21 + fase) * Math.sin(passi * 0.13 + fase * 2) + (ridotto ? 0.2 : Math.random() * 0.08);
    // Il bagliore a terra.
    var g = ctx.createRadialGradient(x, y - r * 0.6, r * 0.2, x, y - r * 0.6, r * 3);
    g.addColorStop(0, "rgba(255,150,40," + (0.28 * fiamma).toFixed(3) + ")"); g.addColorStop(1, "rgba(255,150,40,0)");
    ctx.fillStyle = g; ctx.fillRect(x - r * 3, y - r * 3.6, r * 6, r * 4);
    var cy = y - r * 0.82;
    ctx.lineWidth = Math.max(1, r * 0.07); ctx.strokeStyle = "#3a1d07";
    // Gli spicchi: quelli di lato prima, poi quello davanti.
    var spicchi = [[-0.45, 0.62, "#d8621a"], [0.45, 0.62, "#d8621a"], [-0.2, 0.75, "#ee7a22"], [0.2, 0.75, "#ee7a22"], [0, 0.6, "#f58a2a"]];
    for (var i = 0; i < spicchi.length; i++) {
      ctx.fillStyle = spicchi[i][2];
      ctx.beginPath(); ctx.ellipse(x + spicchi[i][0] * r, cy, r * spicchi[i][1], r * 0.82, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    // Il picciolo.
    ctx.fillStyle = "#5b6b2a"; ctx.beginPath();
    ctx.moveTo(x - r * 0.1, cy - r * 0.75); ctx.quadraticCurveTo(x - r * 0.05, cy - r * 1.15, x + r * 0.22, cy - r * 1.2);
    ctx.lineTo(x + r * 0.16, cy - r * 1.02); ctx.lineTo(x + r * 0.1, cy - r * 0.75); ctx.closePath(); ctx.fill(); ctx.stroke();
    // La faccia intagliata, accesa dalla candela.
    var luce = "rgba(255," + Math.round(200 + 40 * fiamma) + "," + Math.round(60 + 60 * fiamma) + "," + (0.75 + 0.25 * fiamma).toFixed(3) + ")";
    ctx.fillStyle = luce; ctx.beginPath();
    var oy = cy - r * 0.2;
    if (faccia === 1) {
      // occhi tondi
      ctx.arc(x - r * 0.3, oy, r * 0.14, 0, Math.PI * 2); ctx.moveTo(x + r * 0.44, oy); ctx.arc(x + r * 0.3, oy, r * 0.14, 0, Math.PI * 2);
    } else {
      ctx.moveTo(x - r * 0.45, oy + r * 0.1); ctx.lineTo(x - r * 0.3, oy - r * 0.18); ctx.lineTo(x - r * 0.15, oy + r * 0.1);
      ctx.moveTo(x + r * 0.15, oy + r * 0.1); ctx.lineTo(x + r * 0.3, oy - r * 0.18); ctx.lineTo(x + r * 0.45, oy + r * 0.1);
    }
    ctx.fill();
    // Il naso e la bocca a denti.
    ctx.beginPath(); ctx.moveTo(x - r * 0.07, cy + r * 0.05); ctx.lineTo(x, cy - r * 0.08); ctx.lineTo(x + r * 0.07, cy + r * 0.05); ctx.fill();
    ctx.beginPath();
    var my = cy + r * 0.25, mw = r * (faccia === 2 ? 0.5 : 0.6);
    ctx.moveTo(x - mw, my); ctx.quadraticCurveTo(x, my + r * 0.45, x + mw, my);
    var denti = faccia === 2 ? 3 : 4;
    for (var k = denti; k >= 0; k--) { var px = x - mw + (2 * mw) * k / denti; ctx.lineTo(px, my + (k % 2 ? r * 0.12 : r * 0.02)); }
    ctx.closePath(); ctx.fill();
  }
  function disegnaLucine() {
    var y0 = sottoTestata + 2, passoL = W < 640 ? 28 : 34, campata = W < 640 ? 140 : 200;
    ctx.strokeStyle = "rgba(30,24,20,.85)"; ctx.lineWidth = 1.3;
    ctx.beginPath();
    for (var x = 0; x <= W; x += 6) { var u = (x % campata) / campata; var y = y0 + Math.sin(Math.PI * u) * 14; if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
    ctx.stroke();
    var colori = ["#ff8a1a", "#a64dff", "#7dff4a"];
    for (var i = 0, xb = passoL / 2; xb < W; xb += passoL, i++) {
      var ub = (xb % campata) / campata, yb = y0 + Math.sin(Math.PI * ub) * 14;
      var acceso = ridotto ? 1 : 0.35 + 0.65 * Math.max(0, Math.sin(passi * 0.05 - i * 0.55));
      var c = colori[i % 3];
      ctx.globalAlpha = 0.3 * acceso; ctx.fillStyle = c; ctx.beginPath(); ctx.arc(xb, yb + 7, 9, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 0.45 + 0.55 * acceso; ctx.beginPath(); ctx.ellipse(xb, yb + 7, 3.2, 4.6, 0, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1; ctx.fillStyle = "#2a2420"; ctx.fillRect(xb - 2, yb + 1, 4, 3);
    }
  }
  function disegnaRagnatela(x, y, sx, r) {
    ctx.strokeStyle = "rgba(200,200,215,.38)"; ctx.lineWidth = 1;
    var raggi = 6, giri = 5, i, k;
    ctx.beginPath();
    for (i = 0; i <= raggi; i++) { var a = (Math.PI / 2) * i / raggi; ctx.moveTo(x, y); ctx.lineTo(x + sx * Math.cos(a) * r, y + Math.sin(a) * r); }
    for (k = 1; k <= giri; k++) {
      var rr = r * k / (giri + 0.4);
      for (i = 0; i <= raggi; i++) {
        var b = (Math.PI / 2) * i / raggi, px = x + sx * Math.cos(b) * rr, py = y + Math.sin(b) * rr;
        if (i === 0) ctx.moveTo(px, py);
        else { var bm = (Math.PI / 2) * (i - 0.5) / raggi, cr = rr * 0.86; ctx.quadraticCurveTo(x + sx * Math.cos(bm) * cr, y + Math.sin(bm) * cr, px, py); }
      }
    }
    ctx.stroke();
    // Il ragnetto, appeso al suo filo.
    var fy = y + r * 0.9 + (ridotto ? 0 : Math.sin(passi * 0.02) * 10), fx = x + sx * r * 0.35;
    ctx.beginPath(); ctx.moveTo(fx, y); ctx.lineTo(fx, fy); ctx.stroke();
    ctx.fillStyle = "#17171c"; ctx.beginPath(); ctx.arc(fx, fy, 3.2, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#17171c"; ctx.lineWidth = 0.9; ctx.beginPath();
    for (i = -1; i <= 1; i += 2) for (k = 0; k < 3; k++) { ctx.moveTo(fx, fy); ctx.lineTo(fx + i * 5, fy - 2 + k * 2.5); }
    ctx.stroke();
  }
  function disegnaZombie(z) {
    var x = z.x, y = pavimento, s = z.s, d = z.dir, ph = z.fase, nero = "#17171c";
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    var cammina = z.sosta <= 0, dond = Math.sin(ph * 0.5) * 1.5;
    var anca = { x: 0, y: -26 };
    var p1 = { x: d * (cammina ? 6 * Math.sin(ph) : 3), y: -1.5 - (cammina ? Math.max(0, 2.5 * Math.cos(ph)) : 0) };
    var p2 = { x: -d * (cammina ? 5 * Math.sin(ph) : 4), y: -1.5 };
    var gambe = [p2, p1], i;
    ctx.strokeStyle = nero; ctx.lineWidth = 6.4;
    for (i = 0; i < 2; i++) { ctx.beginPath(); ctx.moveTo(anca.x, anca.y); ctx.lineTo((anca.x + gambe[i].x) / 2 + d * 1.5, (anca.y + gambe[i].y) / 2); ctx.lineTo(gambe[i].x, gambe[i].y); ctx.stroke(); }
    ctx.strokeStyle = z.toni[1]; ctx.lineWidth = 4.4;
    for (i = 0; i < 2; i++) { ctx.beginPath(); ctx.moveTo(anca.x, anca.y); ctx.lineTo((anca.x + gambe[i].x) / 2 + d * 1.5, (anca.y + gambe[i].y) / 2); ctx.lineTo(gambe[i].x, gambe[i].y); ctx.stroke(); }
    // Il busto, piegato in avanti, con la maglia a brandelli.
    var spalla = { x: d * 6 + dond, y: -47 };
    ctx.save(); ctx.translate((anca.x + spalla.x) / 2, (anca.y + spalla.y) / 2); ctx.rotate(Math.atan2(spalla.y - anca.y, spalla.x - anca.x) + Math.PI / 2);
    ctx.fillStyle = z.toni[0]; ctx.strokeStyle = nero; ctx.lineWidth = 1.1; ctx.beginPath();
    ctx.moveTo(-7.5, -12); ctx.lineTo(7.5, -12); ctx.lineTo(7.5, 10); ctx.lineTo(4, 13); ctx.lineTo(1.5, 9.5); ctx.lineTo(-2, 13.5); ctx.lineTo(-4.5, 10); ctx.lineTo(-7.5, 12); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.restore();
    // La testa storta, un occhio grande e uno piccolo.
    var pelle = "#9dbf8c", tx = spalla.x + d * 3, ty = spalla.y - 10 + Math.sin(passi * 0.11 + ph) * 0.8;
    ctx.save(); ctx.translate(tx, ty); ctx.rotate(d * 0.22);
    ctx.fillStyle = pelle; ctx.strokeStyle = nero; ctx.lineWidth = 1.1; ctx.beginPath(); ctx.arc(0, 0, 8, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    var grande = z.occhio > 0 ? d * 4.4 : d * 0.2, piccolo = z.occhio > 0 ? d * 0.2 : d * 4.4;
    ctx.fillStyle = "#f4f7e6"; ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.arc(grande, -1.4, 2.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.arc(piccolo, -1, 1.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = nero; ctx.beginPath(); ctx.arc(grande + d * 0.6, -1.4, 0.9, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#3a1f24"; ctx.beginPath(); ctx.ellipse(d * 2.6, 4, 2.2, 1.6 + Math.abs(Math.sin(passi * 0.05 + ph)), 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#3d4a36"; ctx.lineWidth = 1.2; ctx.beginPath();
    var u; for (u = -4; u <= 2.5; u += 3.25) { ctx.moveTo(u, -7.4); ctx.lineTo(u - d * 1.6, -10.5); }
    ctx.stroke(); ctx.restore();
    // Le braccia tese in avanti.
    var brac = [[2.5, "#6f9164"], [-2.5, pelle]];
    for (i = 0; i < 2; i++) {
      var su = brac[i][0], mano = { x: spalla.x + d * 19, y: spalla.y + su + Math.sin(passi * 0.09 + su) * 1.2 }, gom = { x: (spalla.x + mano.x) / 2, y: (spalla.y + mano.y) / 2 + 2.2 };
      ctx.strokeStyle = nero; ctx.lineWidth = 5.4; ctx.beginPath(); ctx.moveTo(spalla.x, spalla.y + su); ctx.lineTo(gom.x, gom.y); ctx.lineTo(mano.x, mano.y); ctx.stroke();
      ctx.strokeStyle = brac[i][1]; ctx.lineWidth = 3.4; ctx.stroke();
    }
    ctx.restore();
  }
  // La mano che cammina: vista di lato, il palmo in giù, quattro dita per zampe e il pollice in fuori;
  // dietro il polso, un polsino cucito (niente braccio, niente sangue).
  function disegnaMano(m) {
    var s = m.s, d = m.dir, nero = "#17171c";
    ctx.save(); ctx.translate(m.x, m.y); ctx.scale(d * s, s);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    var inAria = !!m.salto, alto = inAria ? 8 : 10;
    // Le dita: due segmenti ciascuna; camminando si alternano, ferme tamburellano.
    for (var k = 0; k < 4; k++) {
      var base = { x: 6 - k * 3.2, y: -alto + 1 }, fase = m.passo + k * 1.6;
      var alza = m.tamburo > 0 ? Math.max(0, Math.sin(passi * 0.6 + k * 1.3)) * 3 : inAria ? 2 : Math.max(0, Math.sin(fase)) * 2.5;
      var avanti = m.tamburo > 0 || inAria ? 0 : Math.cos(fase) * 2.2;
      var nocca = { x: base.x + 4 + avanti * 0.5, y: base.y - 2 - alza * 0.5 }, punta = { x: base.x + 5 + avanti, y: inAria ? base.y + 6 : -alza };
      ctx.strokeStyle = nero; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(base.x, base.y); ctx.lineTo(nocca.x, nocca.y); ctx.lineTo(punta.x, punta.y); ctx.stroke();
      ctx.strokeStyle = m.pelle; ctx.lineWidth = 2.4; ctx.stroke();
    }
    // Il dorso della mano.
    ctx.fillStyle = m.pelle; ctx.strokeStyle = nero; ctx.lineWidth = 1.1;
    ctx.beginPath(); ctx.ellipse(1, -alto - 1, 9, 4.6, -0.08, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    // Le nocche e il pollice in fuori.
    ctx.strokeStyle = "rgba(23,23,28,.45)"; ctx.lineWidth = 0.8; ctx.beginPath();
    for (k = 0; k < 3; k++) { ctx.moveTo(5 - k * 3.2, -alto - 3.5); ctx.lineTo(5.6 - k * 3.2, -alto - 2.2); }
    ctx.stroke();
    ctx.strokeStyle = nero; ctx.lineWidth = 3.8; ctx.beginPath(); ctx.moveTo(-1, -alto + 1); ctx.lineTo(3, -alto + 4.5); ctx.stroke();
    ctx.strokeStyle = m.pelle; ctx.lineWidth = 2.2; ctx.stroke();
    // Il polsino cucito.
    ctx.fillStyle = "#4b4258"; ctx.strokeStyle = nero; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.ellipse(-8.5, -alto - 1, 2.6, 4.4, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = "#d9d3c5"; ctx.lineWidth = 0.7; ctx.beginPath();
    for (k = -1; k <= 1; k++) { ctx.moveTo(-9.6, -alto - 1 + k * 2.4); ctx.lineTo(-7.4, -alto - 0.2 + k * 2.4); }
    ctx.stroke();
    ctx.restore();
  }
  function disegnaPipistrello(p) {
    var a = Math.sin(p.fase), s = p.s;
    ctx.save(); ctx.translate(p.x, p.y); ctx.scale(p.dir * s, s);
    // (scuro su scuro non si vedrebbe: un orlo viola)
    ctx.fillStyle = "#24182f"; ctx.strokeStyle = "#8a63b8"; ctx.lineWidth = 1.2;
    for (var lato = -1; lato <= 1; lato += 2) {
      ctx.beginPath(); ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(lato * 8, -10 * a - 4, lato * 18, -8 * a);
      ctx.quadraticCurveTo(lato * 14, -2 * a + 2, lato * 12, 2);
      ctx.quadraticCurveTo(lato * 8, 0, lato * 6, 4);
      ctx.quadraticCurveTo(lato * 3, 1, 0, 3); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    ctx.beginPath(); ctx.ellipse(0, 1, 3.6, 4.6, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-2.6, -2.5); ctx.lineTo(-1.8, -6); ctx.lineTo(-0.6, -3); ctx.moveTo(2.6, -2.5); ctx.lineTo(1.8, -6); ctx.lineTo(0.6, -3); ctx.fill();
    ctx.fillStyle = "#ffcf3a"; ctx.fillRect(-1.6, -0.6, 1, 1); ctx.fillRect(0.6, -0.6, 1, 1);
    ctx.restore();
  }
  function disegna() {
    ctx.clearRect(0, 0, W, H);
    var i;
    // La nebbia bassa.
    if (!ridotto) {
      for (i = 0; i < nebbia.length; i++) {
        var q = nebbia[i], g = ctx.createRadialGradient(q.x, pavimento, 4, q.x, pavimento, q.r);
        g.addColorStop(0, "rgba(170,150,200," + q.a + ")"); g.addColorStop(1, "rgba(170,150,200,0)");
        ctx.fillStyle = g; ctx.fillRect(q.x - q.r, pavimento - q.r, q.r * 2, q.r);
      }
    }
    var webY = sottoTestata + 4, webR = W < 640 ? 46 : 70;
    disegnaRagnatela(0, webY, 1, webR);
    disegnaRagnatela(W, webY, -1, webR * 0.8);
    for (i = 0; i < pipistrelli.length; i++) disegnaPipistrello(pipistrelli[i]);
    for (i = 0; i < zombie.length; i++) disegnaZombie(zombie[i]);
    for (i = 0; i < zucche.length; i++) {
      var z = zucche[i], s = superficie(z.el);
      if (!s) continue;
      disegnaZucca(s.l + (s.r - s.l) * z.u, s.t, z.r, z.fase, z.faccia);
    }
    for (i = 0; i < mani.length; i++) disegnaMano(mani[i]);
    disegnaLucine();
  }
  function ciclo() {
    richiesta = null;
    if (!acceso || document.hidden) return;
    passo();
    disegna();
    if (!ridotto) richiesta = window.requestAnimationFrame(ciclo);
  }
  function riparti() { if (acceso && !richiesta && !document.hidden) richiesta = window.requestAnimationFrame(ciclo); }

  function avvia() {
    if (!tela) {
      tela = document.createElement("canvas");
      tela.className = "halloween-tela"; tela.setAttribute("aria-hidden", "true");
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
    if (tela) { ctx.clearRect(0, 0, W, H); tela.style.display = "none"; }
    zucche = []; zombie = []; mani = []; pipistrelli = []; nebbia = [];
  }

  window.addEventListener("pointermove", function (e) { puntatore.x = e.clientX; puntatore.y = e.clientY; }, { passive: true });
  var attesa = null;
  window.addEventListener("resize", function () {
    if (!acceso || !tela) return;
    clearTimeout(attesa);
    attesa = setTimeout(function () { var larga = W; dimensiona(); rileva(); if (Math.abs(larga - W) > 40) popola(); riparti(); }, 150);
  });
  window.addEventListener("scroll", function () { if (acceso && tela) { rileva(); riparti(); } }, { passive: true });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) riparti(); });
  document.addEventListener("click", function (e) {
    var tasto = e.target && e.target.closest && e.target.closest("[data-halloween-tasto]");
    if (tasto) imposta(!acceso);
  });

  function pronto() {
    radice.classList.toggle("halloween", acceso);
    aggiornaTasti();
    if (acceso) avvia();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", pronto);
  else pronto();

  // Per i test.
  window.__halloween = {
    imposta: imposta,
    acceso: function () { return acceso; },
    decidi: function (anno, mese, giorno, salvata, indirizzo) { return decidi(new Date(anno, mese - 1, giorno), salvata, indirizzo); },
    zombie: function () { nuovoZombie(); },
    pipistrelli: function () { nuovoPipistrello(); },
    puntatore: function (x, y) { puntatore.x = x; puntatore.y = y; },
    passi: function (n) { for (var i = 0; i < n; i++) passo(); disegna(); },
    stato: function () {
      return { acceso: acceso, zucche: zucche.length, zombie: zombie.map(function (z) { return { x: z.x, dir: z.dir }; }), pipistrelli: pipistrelli.length,
               mani: mani.map(function (m) { return { x: m.x, y: m.y, dir: m.dir, scappa: m.scappa, salta: !!m.salto }; }),
               superfici: superfici.length, pavimento: pavimento, sottoTestata: sottoTestata };
    },
  };
})();
