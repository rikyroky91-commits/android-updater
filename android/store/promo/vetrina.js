/* I comandi nativi dell'app ridisegnati in HTML, solo per foto e video dello store (12/10/2026).
 *
 * Nell'app capsula e tasti sono viste Android (Comandi.java + Disegni.java) e nel browser di
 * Playwright non ci sono. Qui si rifanno uguali (stesse misure in dp, stessi colori, stessa
 * disposizione) e si leggono dal motore vero: __ring.mosse() dà vita, punteggio, energia e mosse.
 * Con __vetrinaAutoMosse un tasto pronto si "preme" da solo ogni tanto (__ring.ordina, come il tasto vero).
 */
(function () {
  "use strict";
  var VETRO = "rgba(18,22,20,0.55)", FILO = "rgba(255,255,255,0.15)", BIANCO = "rgba(255,255,255,0.95)";
  var alto = (window.__vetrinaAlto || 30) + 8;     // barra di stato + 8 dp, come Comandi.dispone()
  var css = document.createElement("style");
  css.textContent = [
    "#vt-capsula{position:fixed;left:50%;transform:translateX(-50%);top:" + alto + "px;height:44px;display:flex;align-items:center;",
    "padding:2px 4px;border-radius:24px;background:" + VETRO + ";border:1px solid " + FILO + ";z-index:2147483646;",
    "backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);font:500 15px/1 Roboto,system-ui,sans-serif;color:" + BIANCO + ";pointer-events:none}",
    "#vt-capsula svg{display:block}",
    "#vt-punti{min-width:52px;text-align:center;letter-spacing:.2px;white-space:nowrap}",
    ".vt-tasto{position:fixed;z-index:2147483646;pointer-events:none;transition:transform .08s}",
  ].join("");
  document.head.appendChild(css);

  function svg(w, h, dentro) { return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + " " + h + '">' + dentro + "</svg>"; }
  var u = 40 * 0.18;
  var pausa = svg(40, 40, '<rect x="' + (20 - u) + '" y="' + (20 - u) + '" width="' + (u * 0.7) + '" height="' + (2 * u) + '" rx="1" fill="' + BIANCO + '"/>' +
    '<rect x="' + (20 + u * 0.3) + '" y="' + (20 - u) + '" width="' + (u * 0.7) + '" height="' + (2 * u) + '" rx="1" fill="' + BIANCO + '"/>');
  var altro = svg(40, 40, [-1, 0, 1].map(function (i) { return '<circle cx="' + (20 + i * u * 0.95) + '" cy="20" r="' + (u * 0.24) + '" fill="' + BIANCO + '"/>'; }).join(""));
  var chiudi = svg(40, 40, '<g stroke="' + BIANCO + '" stroke-width="2" stroke-linecap="round"><line x1="' + (20 - u * 0.8) + '" y1="' + (20 - u * 0.8) + '" x2="' + (20 + u * 0.8) + '" y2="' + (20 + u * 0.8) + '"/>' +
    '<line x1="' + (20 + u * 0.8) + '" y1="' + (20 - u * 0.8) + '" x2="' + (20 - u * 0.8) + '" y2="' + (20 + u * 0.8) + '"/></g>');

  var capsula = document.createElement("div");
  capsula.id = "vt-capsula";
  capsula.innerHTML = pausa + '<span id="vt-a"></span><span id="vt-punti">0 – 0</span><span id="vt-b"></span>' + altro + chiudi;
  document.body.appendChild(capsula);

  // L'avatar: iniziale nel cerchio del colore, l'anello è la vita (Disegni.Avatar).
  var vista = { a: 1, b: 1 };
  function avatar(lettera, colore, vita, ko, comandato) {
    var r = 20 - 2.5, cx = 18, cy = 20, giro = 2 * Math.PI * r;
    var c = vita < 0.34 ? "#ff5a4e" : colore;
    return svg(36, 40, '<g opacity="' + (ko ? 0.45 : 1) + '">' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="' + colore + '" fill-opacity="0.25"/>' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="' + (comandato ? 3 : 2.2) + '"/>' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + c + '" stroke-width="' + (comandato ? 3 : 2.2) + '" stroke-linecap="round" ' +
      'stroke-dasharray="' + (giro * Math.max(0, Math.min(1, vita))) + " " + giro + '" transform="rotate(-90 ' + cx + " " + cy + ')"/>' +
      '<text x="' + cx + '" y="' + (cy + r * 0.34) + '" text-anchor="middle" font-size="' + (r * 0.95) + '" font-weight="700" fill="' + BIANCO + '" font-family="Roboto,system-ui,sans-serif">' + lettera + "</text>" +
      (comandato ? '<circle cx="' + cx + '" cy="38.8" r="1.6" fill="' + colore + '"/>' : "") + "</g>");
  }

  // I quattro tasti nell'angolo in basso a destra (Comandi.dispone): la mossa base grande nell'angolo.
  var tasti = [];
  for (var i = 0; i < 4; i++) {
    var lato = i === 0 ? 66 : 54, cx = 60, cy = 60;
    if (i > 0) { var a = (180 + 45 * (i - 1)) * Math.PI / 180; cx += Math.round(-Math.cos(a) * 94); cy += Math.round(-Math.sin(a) * 94); }
    var t = document.createElement("div");
    t.className = "vt-tasto";
    t.style.width = t.style.height = lato + "px";
    t.style.right = (cx - lato / 2) + "px";
    t.style.bottom = ((window.__vetrinaBasso || 16) + cy - lato / 2) + "px";
    document.body.appendChild(t);
    tasti.push({ el: t, lato: lato, id: null });
  }
  function tasto(T, voce, ki, colore) {
    var r = T.lato / 2 - 3, c = T.lato / 2, giro = 2 * Math.PI * r;
    var carica = voce.costo > 0 ? Math.min(1, ki / voce.costo) : 1, pronta = voce.pronta && carica >= 1;
    var sat = carica * carica;
    T.el.innerHTML = svg(T.lato, T.lato,
      '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="' + (pronta ? "rgba(18,22,20,0.65)" : "rgba(18,22,20,0.45)") + '"/>' +
      '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2.5"/>' +
      (pronta ? '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="' + colore + '" stroke-width="2.5"/>'
        : carica > 0 ? '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="rgba(255,255,255,0.8)" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="' + (giro * carica) + " " + giro + '" transform="rotate(-90 ' + c + " " + c + ')"/>' : "") +
      '<text x="' + c + '" y="' + c + '" dominant-baseline="central" text-anchor="middle" font-size="' + (r * 0.95) + '" style="filter:saturate(' + sat + ')" opacity="' + (pronta ? 1 : 0.45 + 0.4 * carica) + '">' + voce.icona + "</text>");
    return pronta;
  }

  var ultimaMossa = 0;
  function giro() {
    var R = window.__ring;
    if (!R || !R.mosse) return;
    var m;
    try { m = R.mosse(); } catch (e) { return; }
    var ch = m && m.corsaHud, inCorsa = !!(m && m.corsa);
    var vedo = m && m.acceso !== false && !m.scelta && m.lottatori && m.lottatori.length >= 2 && !window.__vetrinaSpenta
      && (!inCorsa || (ch && ch.fase === "lotta"));
    capsula.style.display = vedo ? "flex" : "none";
    tasti.forEach(function (T) { T.el.style.display = vedo && !window.__vetrinaSenzaTasti ? "block" : "none"; });
    if (!vedo) return;
    if (inCorsa) {
      // La corsa (Comandi.leggi): un solo avatar, vita del tuo eroe, cuori, round e obiettivo; niente tasti.
      var e = ch.chi === m.lottatori[1].tipo ? m.lottatori[1] : m.lottatori[0];
      vista.a += (ch.hp / Math.max(1, ch.hpMax) - vista.a) * 0.35;
      document.getElementById("vt-a").innerHTML = avatar((e.nome || "?")[0].toUpperCase(), e.colore, vista.a, false, true);
      document.getElementById("vt-b").innerHTML = "";
      document.getElementById("vt-punti").textContent = "\u2665" + ch.vite + "  \u00b7  R" + ch.round + (ch.obiettivo ? "  \u00b7  " + ch.obiettivo : "");
      document.getElementById("vt-punti").style.padding = "0 8px";
      tasti.forEach(function (T) { T.el.style.display = "none"; });
      return;
    }
    var A = m.lottatori[0], B = m.lottatori[1], chi = m.chi;
    vista.a += ((A.vita || 0) - vista.a) * 0.35; vista.b += ((B.vita || 0) - vista.b) * 0.35;
    document.getElementById("vt-a").innerHTML = avatar((A.nome || "?")[0].toUpperCase(), A.colore, vista.a, A.ko, chi === A.tipo);
    document.getElementById("vt-b").innerHTML = avatar((B.nome || "?")[0].toUpperCase(), B.colore, vista.b, B.ko, chi === B.tipo);
    var p = m.punteggio || {};
    document.getElementById("vt-punti").textContent = (p[A.tipo] || 0) + " – " + (p[B.tipo] || 0);
    var io = chi === B.tipo ? B : A, ki = io.ki || 0, voci = m.voci || [];
    var pronte = [];
    tasti.forEach(function (T, i) { var v = voci[i]; if (!v) { T.el.innerHTML = ""; return; } if (tasto(T, v, ki, io.colore)) pronte.push({ v: v, T: T }); });
    // Ogni tanto il lottatore che comandi usa un'abilità pronta: il tasto si abbassa come sotto un dito.
    var ora = Date.now();
    if (window.__vetrinaAutoMosse && pronte.length && ora - ultimaMossa > (window.__vetrinaOgni || 2600)) {
      ultimaMossa = ora;
      var s = pronte[Math.floor(Math.random() * pronte.length)];
      s.T.el.style.transform = "scale(0.9)";
      setTimeout(function () { s.T.el.style.transform = ""; }, 140);
      try { R.ordina && R.ordina(chi, s.v.id); } catch (e) { /* mossa non disponibile ora */ }
    }
  }
  setInterval(giro, 1000 / 15);
})();
