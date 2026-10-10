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
 *   - AL PASSAGGIO DEL MOUSE (10/10/2026): le zucche si svegliano (un saltello,
 *     la candela che divampa, gli occhi che seguono il puntatore, la bocca che
 *     ride) e le lucine toccate si spengono con uno sbuffo di fumo, oscillano
 *     e si riaccendono da sole dopo un paio di secondi, tremolando;
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
  var lucine = []; // per lampadina: { spenta: fotogrammi, dondola: ampiezza }
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
    zucche.push(nuovaZucca("fondo", stretto ? 0.06 : 0.035, stretto ? 15 : 22, 0));
    zucche.push(nuovaZucca("fondo", stretto ? 0.16 : 0.08, stretto ? 10 : 14, 1));
    if (!stretto) zucche.push(nuovaZucca("fondo", 0.955, 19, 2));
    // Sopra gli elementi: qualche zucchetta.
    for (var i = 1, n = 0; i < superfici.length && n < (stretto ? 2 : 4); i += 2, n++) {
      zucche.push(nuovaZucca(superfici[i].el, caso(0.75, 0.92), caso(8, 11), n % 3));
    }
    lucine = [];
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
  function nuovaZucca(el, u, r, faccia) {
    // `sveglia` va da 0 a 1 col puntatore vicino; `salta` conta il saltello.
    return { el: el, u: u, r: r, fase: caso(0, 6), faccia: faccia, sveglia: 0, salta: 0, x: 0, y: 0 };
  }
  // Tre carnagioni da non morto: [chiara, media, ombra].
  var PELLI = [["#c9d6b4", "#9fb38f", "#6e8463"], ["#d3cfc0", "#aaa596", "#77725f"], ["#bfc0d6", "#9597b4", "#666884"]];
  function nuovaMano(s, u) {
    return { el: s.el, x: s.l + (s.r - s.l) * u, y: s.t, dir: Math.random() < 0.5 ? -1 : 1, v: caso(0.7, 1.3), passo: caso(0, 6),
             ferma: 0, tamburo: 0, scappa: 0, salto: null, carica: 0, pronto: null, atterra: 0,
             pelle: PELLI[Math.floor(Math.random() * PELLI.length)], s: caso(1.25, 1.55) * (W < 640 ? 0.8 : 1) };
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
    // Le zucche e le lucine sentono il puntatore.
    for (i = 0; i < zucche.length; i++) svegliaZucca(zucche[i]);
    tocca(Lampadine(), true);
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
    if (m.carica > 0) {
      // La rincorsa: si accuccia sulle dita, poi parte.
      if (--m.carica === 0) { m.salto = m.pronto; m.pronto = null; }
      return;
    }
    if (m.atterra > 0) m.atterra--;
    if (m.salto) {
      // In volo da un elemento all'altro: una parabola.
      var S = m.salto; S.t++;
      var u = Math.min(1, S.t / S.dur);
      m.x = S.x0 + (S.x1 - S.x0) * u; m.y = S.y0 + (S.y1 - S.y0) * u - Math.sin(Math.PI * u) * S.h;
      // L'inclinazione segue la traiettoria: muso in su alla partenza, in giù all'arrivo.
      m.pendenza = Math.max(-0.6, Math.min(0.6, (S.y1 - S.y0) / Math.max(1, Math.abs(S.x1 - S.x0)) * 0.3 - Math.cos(Math.PI * u) * 0.5));
      if (u >= 1) { m.salto = null; m.el = S.el; m.y = S.y1; m.ferma = 20; m.atterra = 14; m.pendenza = 0; }
      return;
    }
    var s = superficie(m.el) || superfici[0];
    if (!s) return;
    if (s.el !== m.el) m.el = s.el;
    m.y = s.t;
    // Il puntatore vicino: scappa di corsa dall'altra parte.
    var dx = m.x - puntatore.x, dy = m.y - puntatore.y;
    if (Math.abs(dx) < 70 && Math.abs(dy) < 50 && m.scappa <= 0) { m.scappa = 50; m.dir = dx >= 0 ? 1 : -1; m.ferma = 0; m.tamburo = 0; m.sobbalzo = 10; }
    if (m.sobbalzo > 0) m.sobbalzo--;
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
          m.pronto = { t: 0, dur: Math.round(caso(40, 60)), x0: m.x, y0: m.y, x1: x1, y1: meta.t, h: Math.max(40, (m.y - meta.t) + 50), el: meta.el };
          m.carica = 12;
          m.dir = x1 >= m.x ? 1 : -1;
          return;
        }
      }
      m.dir = -m.dir;
    }
  }

  // --- Il puntatore su zucche e lucine ---------------------------------
  function vicinoA(x, y, raggio) { var dx = puntatore.x - x, dy = puntatore.y - y; return dx * dx + dy * dy < raggio * raggio; }
  function svegliaZucca(z) {
    var s = superficie(z.el);
    if (!s) return;
    var cx = s.l + (s.r - s.l) * z.u, cy = s.t - z.r * 0.82, vicino = vicinoA(cx, cy, z.r * 1.7 + 10);
    // Appena la si sfiora fa un saltello; poi resta sveglia finché il puntatore è lì.
    if (vicino && z.sveglia < 0.3 && z.salta <= 0 && !ridotto) z.salta = 26;
    z.sveglia += vicino ? (1 - z.sveglia) * 0.15 : -z.sveglia * 0.05;
    if (z.salta > 0) z.salta--;
  }
  // Dove stanno le lampadine: una ogni `passoL` pixel, appese al filo che fa le campate.
  function Lampadine() {
    var y0 = sottoTestata + 2, passoL = W < 640 ? 28 : 34, campata = W < 640 ? 140 : 200, pos = [];
    for (var xb = passoL / 2; xb < W; xb += passoL) pos.push({ x: xb, y: y0 + Math.sin(Math.PI * ((xb % campata) / campata)) * 14 });
    return pos;
  }
  // Una lampadina toccata si spegne (con uno sbuffo e un dondolio) e resta spenta finché
  // il puntatore le sta addosso, più un paio di secondi; poi si riaccende tremolando.
  function tocca(pos, conTempo) {
    for (var i = 0; i < pos.length; i++) {
      var l = lucine[i] || (lucine[i] = { spenta: 0, dondola: 0 });
      if (vicinoA(pos[i].x, pos[i].y + 7, 16)) {
        if (l.spenta <= 0) l.dondola = 1;
        l.spenta = 150;
      } else if (conTempo && l.spenta > 0) l.spenta--;
      if (conTempo) l.dondola *= 0.965;
    }
  }

  // --- I disegni --------------------------------------------------------
  function disegnaZucca(z, x, y) {
    var r = z.r, sv = ridotto ? (vicinoA(x, y - r * 0.82, r * 1.7 + 10) ? 1 : 0) : z.sveglia;
    var fiamma = 0.75 + 0.25 * Math.sin(passi * 0.21 + z.fase) * Math.sin(passi * 0.13 + z.fase * 2) + (ridotto ? 0.2 : Math.random() * 0.08);
    fiamma += 0.35 * sv;
    // Il bagliore a terra: sveglia, la candela divampa.
    var g = ctx.createRadialGradient(x, y - r * 0.6, r * 0.2, x, y - r * 0.6, r * (3 + 1.2 * sv));
    g.addColorStop(0, "rgba(255,150,40," + Math.min(0.6, 0.28 * fiamma * (1 + sv)).toFixed(3) + ")"); g.addColorStop(1, "rgba(255,150,40,0)");
    ctx.fillStyle = g; ctx.fillRect(x - r * 4.2, y - r * 4.8, r * 8.4, r * 5.2);
    // Il saltello: su e giù con un po' di elastico, schiacciata alla partenza e all'arrivo.
    var t = z.salta > 0 ? 1 - z.salta / 26 : 0, k = z.salta > 0 ? Math.sin(Math.PI * t) : 0;
    var schiaccia = z.salta > 0 && (t < 0.15 || t > 0.85) ? 0.1 : 0, cresce = 1 + 0.1 * sv;
    ctx.save();
    ctx.translate(x, y - k * r * 0.7);
    ctx.scale(cresce * (1 - 0.06 * k + schiaccia), cresce * (1 + 0.1 * k - schiaccia));
    if (z.salta > 0) ctx.rotate(Math.sin(t * Math.PI * 2) * 0.12);
    var cy = -r * 0.82;
    ctx.lineWidth = Math.max(1, r * 0.07); ctx.strokeStyle = "#3a1d07";
    // Gli spicchi: quelli di lato prima, poi quello davanti.
    var spicchi = [[-0.45, 0.62, "#d8621a"], [0.45, 0.62, "#d8621a"], [-0.2, 0.75, "#ee7a22"], [0.2, 0.75, "#ee7a22"], [0, 0.6, "#f58a2a"]];
    for (var i = 0; i < spicchi.length; i++) {
      ctx.fillStyle = spicchi[i][2];
      ctx.beginPath(); ctx.ellipse(spicchi[i][0] * r, cy, r * spicchi[i][1], r * 0.82, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    // Il picciolo.
    ctx.fillStyle = "#5b6b2a"; ctx.beginPath();
    ctx.moveTo(-r * 0.1, cy - r * 0.75); ctx.quadraticCurveTo(-r * 0.05, cy - r * 1.15, r * 0.22, cy - r * 1.2);
    ctx.lineTo(r * 0.16, cy - r * 1.02); ctx.lineTo(r * 0.1, cy - r * 0.75); ctx.closePath(); ctx.fill(); ctx.stroke();
    // La faccia intagliata, accesa dalla candela. Sveglia, gli occhi guardano il puntatore.
    var luce = "rgba(255," + Math.round(Math.min(255, 200 + 40 * fiamma)) + "," + Math.round(Math.min(200, 60 + 60 * fiamma)) + "," + Math.min(1, 0.75 + 0.25 * fiamma).toFixed(3) + ")";
    var gx = Math.max(-1, Math.min(1, (puntatore.x - x) / 150)) * r * 0.08 * sv, gy = Math.max(-1, Math.min(1, (puntatore.y - y) / 150)) * r * 0.06 * sv;
    ctx.fillStyle = luce; ctx.beginPath();
    var oy = cy - r * 0.2 + gy, ox = gx;
    if (z.faccia === 1) {
      // occhi tondi
      ctx.arc(ox - r * 0.3, oy, r * (0.14 + 0.03 * sv), 0, Math.PI * 2); ctx.moveTo(ox + r * 0.44, oy); ctx.arc(ox + r * 0.3, oy, r * (0.14 + 0.03 * sv), 0, Math.PI * 2);
    } else {
      var su = r * (0.18 + 0.06 * sv);
      ctx.moveTo(ox - r * 0.45, oy + r * 0.1); ctx.lineTo(ox - r * 0.3, oy - su); ctx.lineTo(ox - r * 0.15, oy + r * 0.1);
      ctx.moveTo(ox + r * 0.15, oy + r * 0.1); ctx.lineTo(ox + r * 0.3, oy - su); ctx.lineTo(ox + r * 0.45, oy + r * 0.1);
    }
    ctx.fill();
    // Il naso e la bocca a denti: sveglia, ride a bocca aperta.
    ctx.beginPath(); ctx.moveTo(-r * 0.07, cy + r * 0.05); ctx.lineTo(0, cy - r * 0.08); ctx.lineTo(r * 0.07, cy + r * 0.05); ctx.fill();
    ctx.beginPath();
    var my = cy + r * 0.25, mw = r * (z.faccia === 2 ? 0.5 : 0.6) * (1 + 0.1 * sv);
    ctx.moveTo(-mw, my); ctx.quadraticCurveTo(0, my + r * (0.45 + 0.3 * sv), mw, my);
    var denti = z.faccia === 2 ? 3 : 4;
    for (var q = denti; q >= 0; q--) { var px = -mw + (2 * mw) * q / denti; ctx.lineTo(px, my + (q % 2 ? r * 0.12 : r * 0.02)); }
    ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  function disegnaLucine() {
    var y0 = sottoTestata + 2, campata = W < 640 ? 140 : 200, pos = Lampadine(), i;
    if (ridotto) tocca(pos, false);
    ctx.strokeStyle = "rgba(30,24,20,.85)"; ctx.lineWidth = 1.3;
    ctx.beginPath();
    for (var x = 0; x <= W; x += 6) { var u = (x % campata) / campata; var y = y0 + Math.sin(Math.PI * u) * 14; if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
    ctx.stroke();
    var colori = ["#ff8a1a", "#a64dff", "#7dff4a"];
    for (i = 0; i < pos.length; i++) {
      var xb = pos[i].x, yb = pos[i].y, l = lucine[i] || { spenta: 0, dondola: 0 }, c = colori[i % 3];
      var onda = ridotto ? 1 : 0.35 + 0.65 * Math.max(0, Math.sin(passi * 0.05 - i * 0.55));
      // Spenta; negli ultimi istanti prima di riaccendersi, tremola.
      var spenta = l.spenta > 0 && !(l.spenta < 26 && !ridotto && Math.random() < 0.45);
      ctx.save(); ctx.translate(xb, yb + 1);
      if (l.dondola > 0.02) ctx.rotate(Math.sin(passi * 0.22 + i) * 0.7 * l.dondola);
      if (spenta) {
        ctx.fillStyle = "#3b3632"; ctx.strokeStyle = "rgba(0,0,0,.5)"; ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.ellipse(0, 6, 3.2, 4.6, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,.18)"; ctx.beginPath(); ctx.ellipse(-1.1, 4.6, 0.9, 1.6, 0, 0, Math.PI * 2); ctx.fill();
      } else {
        ctx.fillStyle = c;
        ctx.globalAlpha = 0.3 * onda; ctx.beginPath(); ctx.arc(0, 6, 9, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 0.45 + 0.55 * onda; ctx.beginPath(); ctx.ellipse(0, 6, 3.2, 4.6, 0, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = "#2a2420"; ctx.fillRect(-2, 0, 4, 3);
      ctx.restore();
      // Lo sbuffo di fumo appena spenta.
      if (l.spenta > 112 && !ridotto) {
        var f = (150 - l.spenta) / 38;
        ctx.strokeStyle = "rgba(190,185,200," + (0.55 * (1 - f)).toFixed(3) + ")"; ctx.lineWidth = 1.4;
        ctx.beginPath(); ctx.moveTo(xb, yb + 3);
        for (var k = 1; k <= 6; k++) ctx.lineTo(xb + Math.sin(k * 1.3 + f * 4) * 2.5 * f, yb + 3 - k * (2 + 6 * f));
        ctx.stroke();
      }
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
  // LA MANO CHE CAMMINA (rifatta il 10/10/2026: «troppo brutte»). Vista di lato, il dorso
  // in su: quattro dita a tre falangi per zampe, che si muovono a coppie alternate come un
  // ragno (indice e anulare, medio e mignolo), il pollice che aiuta, il dorso che ondeggia a
  // ogni passo. Prima di saltare si accuccia, in volo raccoglie le dita, atterrando si
  // schiaccia; ferma, tamburella dal mignolo all'indice. Pelle da non morto con le unghie,
  // una cicatrice cucita, e al polso la manica strappata (niente braccio, niente sangue).
  var FALANGI = [6.2, 4.8, 3.6];
  function dito(P0, T, larga, pelle, chiara) {
    var dx = T.x - P0.x, dy = T.y - P0.y, dist = Math.max(0.01, Math.sqrt(dx * dx + dy * dy));
    // Arcuato verso l'alto, tanto più quanto il dito è raccolto.
    var nx = dy / dist, ny = -dx / dist, arco = 1.6 + Math.max(0, FALANGI[0] + FALANGI[1] + FALANGI[2] - dist) * 0.55;
    var P1 = { x: P0.x + dx * 0.4 + nx * arco, y: P0.y + dy * 0.4 + ny * arco };
    var P2 = { x: P0.x + dx * 0.76 + nx * arco * 0.6, y: P0.y + dy * 0.76 + ny * arco * 0.6 };
    var tratti = [[P0, P1, 1], [P1, P2, 0.84], [P2, T, 0.68]], i;
    ctx.strokeStyle = "#17171c";
    for (i = 0; i < 3; i++) { ctx.lineWidth = larga * tratti[i][2] + 1.3; ctx.beginPath(); ctx.moveTo(tratti[i][0].x, tratti[i][0].y); ctx.lineTo(tratti[i][1].x, tratti[i][1].y); ctx.stroke(); }
    ctx.strokeStyle = pelle;
    for (i = 0; i < 3; i++) { ctx.lineWidth = larga * tratti[i][2]; ctx.beginPath(); ctx.moveTo(tratti[i][0].x, tratti[i][0].y); ctx.lineTo(tratti[i][1].x, tratti[i][1].y); ctx.stroke(); }
    // Il riflesso sul dorso del dito e le nocche.
    if (chiara) {
      ctx.strokeStyle = chiara; ctx.lineWidth = larga * 0.3; ctx.beginPath();
      ctx.moveTo(P0.x + nx * larga * 0.25, P0.y + ny * larga * 0.25); ctx.lineTo(P1.x + nx * larga * 0.25, P1.y + ny * larga * 0.25); ctx.lineTo(P2.x + nx * larga * 0.2, P2.y + ny * larga * 0.2); ctx.stroke();
    }
    ctx.fillStyle = "rgba(23,23,28,.35)";
    ctx.beginPath(); ctx.arc(P1.x, P1.y, larga * 0.22, 0, Math.PI * 2); ctx.arc(P2.x, P2.y, larga * 0.18, 0, Math.PI * 2); ctx.fill();
    // L'unghia, giallastra, sull'ultima falange.
    var ux = P2.x + (T.x - P2.x) * 0.62 + nx * larga * 0.22, uy = P2.y + (T.y - P2.y) * 0.62 + ny * larga * 0.22;
    ctx.fillStyle = "#e6dcaa"; ctx.strokeStyle = "rgba(23,23,28,.6)"; ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.ellipse(ux, uy, larga * 0.36, larga * 0.2, Math.atan2(T.y - P2.y, T.x - P2.x), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  }
  function disegnaMano(m) {
    var s = m.s, d = m.dir, nero = "#17171c", pelle = m.pelle;
    var inAria = !!m.salto, accucciata = m.carica > 0 ? 1 - m.carica / 12 : 0;
    var tamburella = m.tamburo > 0 && !inAria, scappa = m.scappa > 0 && !inAria;
    var cammina = !inAria && !accucciata && m.ferma <= 0;
    var f = m.passo, k;
    // L'altezza del dorso e la sua inclinazione.
    var h = 8.5 + (scappa ? 1.8 : 0);
    if (cammina) h += 0.9 * Math.cos(2 * f);
    h -= 4 * accucciata + (m.atterra > 0 ? 3.5 * m.atterra / 14 : 0);
    if (m.sobbalzo > 0) h += 5 * Math.sin(Math.PI * (1 - m.sobbalzo / 10));
    var incl = inAria ? (m.pendenza || 0) : cammina ? 0.05 * Math.sin(2 * f) : -0.14 * accucciata;
    var co = Math.cos(incl), si = Math.sin(incl);
    function corpo(px, py) { return { x: px * co - py * si, y: -h + px * si + py * co }; }

    ctx.save(); ctx.translate(m.x, m.y); ctx.scale(d * s, s);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    // L'ombra a terra.
    if (!inAria) { ctx.fillStyle = "rgba(0,0,0,.32)"; ctx.beginPath(); ctx.ellipse(1, 0.6, 13, 2.1, 0, 0, Math.PI * 2); ctx.fill(); }
    // Le righe della fuga.
    if (scappa) {
      ctx.strokeStyle = "rgba(220,215,235,.5)"; ctx.lineWidth = 1;
      ctx.beginPath();
      for (k = 0; k < 3; k++) { var ry = -h - 2 + k * 3.2, ox = (passi * 1.7 + k * 5) % 6; ctx.moveTo(-17 - ox, ry); ctx.lineTo(-23 - ox - k, ry); }
      ctx.stroke();
    }
    // Dove sta la punta di ogni dito: [radice sul dorso, appoggio a riposo].
    var radici = [[7.8, -2.6], [7.3, -3.5], [6.5, -4.3], [5.4, -4.9]], riposo = [17, 14.4, 11.8, 9.2];
    function punta(i) {
      var r = corpo(radici[i][0], radici[i][1]);
      if (inAria) {
        var rq = corpo(radici[i][0] + 3.5, radici[i][1] + 3.8 + Math.sin(passi * 0.5 + i) * 0.7);
        return rq;
      }
      if (tamburella) {
        var alza = Math.pow(Math.max(0, Math.sin(passi * 0.33 - (3 - i) * 0.85)), 3) * 4.5;
        return { x: riposo[i] - 1, y: -alza };
      }
      if (accucciata) return { x: riposo[i] + 1.2 * accucciata, y: 0 };
      if (m.atterra > 0) return { x: riposo[i] + (i % 2 ? -1.6 : 1.6) * m.atterra / 14, y: 0 };
      if (!cammina) return { x: riposo[i], y: 0 };
      var fk = f + (i % 2) * Math.PI;
      return { x: riposo[i] - 5 * Math.cos(fk), y: -Math.max(0, Math.sin(fk)) * 3.4 };
    }
    // Prima le dita lontane (medio e mignolo), più in ombra.
    for (k = 3; k >= 1; k -= 2) dito(corpo(radici[k][0], radici[k][1]), punta(k), k === 3 ? 2 : 2.3, pelle[2], null);
    // La manica strappata al polso, dietro il dorso.
    var p1 = corpo(-10, -7.6), p2 = corpo(-15.5, -8.6), p3 = corpo(-16.5, 1), p4 = corpo(-10, 0.8);
    ctx.fillStyle = "#3d3350"; ctx.strokeStyle = nero; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.lineTo(p3.x, p3.y); ctx.lineTo(p4.x, p4.y);
    // l'orlo strappato verso la mano
    var denti = [[-8.6, -0.8], [-10.2, -2.4], [-8.4, -3.8], [-10, -5.4], [-8.8, -6.8]];
    for (k = 0; k < denti.length; k++) { var q = corpo(denti[k][0], denti[k][1]); ctx.lineTo(q.x, q.y); }
    ctx.closePath(); ctx.fill(); ctx.stroke();
    var b1 = corpo(-14.2, -8.2), b2 = corpo(-15, 0.9);
    ctx.strokeStyle = "#6a5a86"; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(b1.x, b1.y); ctx.lineTo(b2.x, b2.y); ctx.stroke();
    // Un filo che penzola dalla manica.
    var fl = corpo(-15.8, -1), fl2 = corpo(-19 - Math.sin(passi * 0.15) * 1.5, 2.5 + Math.cos(passi * 0.15));
    ctx.strokeStyle = "#5c4f75"; ctx.lineWidth = 0.7; ctx.beginPath(); ctx.moveTo(fl.x, fl.y); ctx.quadraticCurveTo(fl.x - 1.5, fl.y + 2, fl2.x, fl2.y); ctx.stroke();
    // Il dorso: dal polso alle nocche, con le nocche in rilievo.
    var forma = [[-10.6, -0.3, "m"], [-2, 1.2, 6.6, -0.3, "q"], [9.4, -1.4, 8.3, -4.2, "q"], [6.9, -6.9, 4.9, -6.3, "q"], [3.6, -7.4, 2.1, -6.7, "q"],
                 [0.4, -7.5, -1.6, -6.9, "q"], [-6.5, -7.6, -10.6, -6.3, "q"]];
    var alto = corpo(0, -7.5), basso = corpo(0, 1);
    var sfuma = ctx.createLinearGradient(alto.x, alto.y, basso.x, basso.y);
    sfuma.addColorStop(0, pelle[0]); sfuma.addColorStop(0.55, pelle[1]); sfuma.addColorStop(1, pelle[2]);
    ctx.fillStyle = sfuma; ctx.strokeStyle = nero; ctx.lineWidth = 1.1;
    ctx.beginPath();
    for (k = 0; k < forma.length; k++) {
      var v = forma[k];
      if (v[v.length - 1] === "m") { var mm = corpo(v[0], v[1]); ctx.moveTo(mm.x, mm.y); }
      else { var c1 = corpo(v[0], v[1]), c2 = corpo(v[2], v[3]); ctx.quadraticCurveTo(c1.x, c1.y, c2.x, c2.y); }
    }
    ctx.closePath(); ctx.fill(); ctx.stroke();
    // I tendini sul dorso e le grinze delle nocche.
    ctx.strokeStyle = "rgba(23,23,28,.22)"; ctx.lineWidth = 0.6; ctx.beginPath();
    for (k = 0; k < 3; k++) { var t0 = corpo(-7.5, -4.4 + k * 1.1), t1 = corpo(5 - k * 1.3, -5.6 + k * 0.9); ctx.moveTo(t0.x, t0.y); ctx.lineTo(t1.x, t1.y); }
    for (k = 0; k < 3; k++) { var g0 = corpo(5.4 - k * 1.5, -6.2), g1 = corpo(5.9 - k * 1.5, -5); ctx.moveTo(g0.x, g0.y); ctx.lineTo(g1.x, g1.y); }
    ctx.stroke();
    // La cicatrice cucita.
    var cA = corpo(-6.2, -6.6), cB = corpo(-1.2, -2.4);
    ctx.strokeStyle = "#5a3848"; ctx.lineWidth = 0.9; ctx.beginPath(); ctx.moveTo(cA.x, cA.y); ctx.lineTo(cB.x, cB.y); ctx.stroke();
    ctx.strokeStyle = "#2b1d26"; ctx.lineWidth = 0.6; ctx.beginPath();
    for (k = 1; k <= 4; k++) {
      var tq = k / 5, px = -6.2 + 5 * tq, py = -6.6 + 4.2 * tq, a1 = corpo(px - 0.9, py + 0.9), a2 = corpo(px + 0.9, py - 0.9);
      ctx.moveTo(a1.x, a1.y); ctx.lineTo(a2.x, a2.y);
    }
    ctx.stroke();
    // Le dita vicine (indice e anulare), poi il pollice che aiuta a spingere.
    for (k = 2; k >= 0; k -= 2) dito(corpo(radici[k][0], radici[k][1]), punta(k), 2.4, pelle[1], pelle[0]);
    var radiceP = corpo(-0.5, -0.4), puntaP;
    if (inAria) puntaP = corpo(2, 3);
    else if (cammina) { var fp = f + Math.PI / 2; puntaP = { x: 4 - 2.5 * Math.cos(fp), y: -Math.max(0, Math.sin(fp)) * 2 }; }
    else puntaP = { x: 4, y: 0 };
    dito(radiceP, puntaP, 2.6, pelle[1], pelle[0]);
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
      disegnaZucca(z, s.l + (s.r - s.l) * z.u, s.t);
    }
    for (i = 0; i < mani.length; i++) disegnaMano(mani[i]);
    disegnaLucine();
  }
  function ciclo() {
    richiesta = null;
    if (!acceso || document.hidden) return;
    // Partito con la finestra ancora senza misure (una scheda aperta dietro, un
    // pannello nascosto): appena le misure arrivano si rifà tutto.
    if (window.innerWidth !== W || window.innerHeight !== H) { var larga = W; dimensiona(); rileva(); if (Math.abs(larga - W) > 40) popola(); }
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

  window.addEventListener("pointermove", function (e) {
    puntatore.x = e.clientX; puntatore.y = e.clientY;
    // Con «meno movimento» non c'è un ciclo che ridisegna: lo si fa qui, così
    // le lucine si spengono e le zucche si illuminano lo stesso (senza saltelli).
    if (ridotto && acceso && tela) riparti();
  }, { passive: true });
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
    mani: function () { return mani; },
    passi: function (n) { for (var i = 0; i < n; i++) passo(); disegna(); },
    stato: function () {
      return { acceso: acceso, zucche: zucche.length,
               zuccheSveglie: zucche.filter(function (z) { return z.sveglia > 0.5; }).length,
               lucineSpente: lucine.filter(function (l) { return l && l.spenta > 0; }).length,
               lampadine: Lampadine(), zombie: zombie.map(function (z) { return { x: z.x, dir: z.dir }; }), pipistrelli: pipistrelli.length,
               mani: mani.map(function (m) { return { x: m.x, y: m.y, dir: m.dir, scappa: m.scappa, salta: !!m.salto || m.carica > 0 }; }),
               posZucche: zucche.map(function (z) { var s = superficie(z.el); return s ? { x: s.l + (s.r - s.l) * z.u, y: s.t - z.r * 0.82 } : null; }),
               superfici: superfici.length, pavimento: pavimento, sottoTestata: sottoTestata };
    },
  };
})();
