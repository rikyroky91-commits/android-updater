/* IL METEO DI ACIREALE SUL SITO (10/11/2026, su richiesta: «effetti dinamici in base al meteo
 * effettivo che c'è ad Acireale (Catania)»).
 *
 * Legge il tempo di adesso da Open-Meteo (senza chiave, dal browser) e lo mette in scena su un
 * canvas che non riceve clic:
 *   - pioggerella e pioggia, più fitta e più inclinata col vento, con gli schizzi sul fondo;
 *   - temporale: pioggia forte, lampi che schiariscono la pagina e fulmini ramificati;
 *   - neve vera (se a Acireale nevica; col tema di Natale acceso la neve la fa già `natale.js`);
 *   - nebbia: banchi bassi che scivolano piano;
 *   - nuvole in quantità pari alla copertura reale, grigie e scure se piove;
 *   - sole con i raggi che girano (di giorno, cielo aperto) o luna nella sua fase vera e stelle
 *     che brillano (di notte);
 *   - vento: foglie che volano e righe di raffica, dal 22 km/h in su;
 *   - arcobaleno dopo gli acquazzoni di giorno.
 *
 * Il tasto nella testata li accende e li spegne (`mut-meteo` = "off" se spenti). Se la richiesta
 * non va a buon fine non si inventa niente: nessun effetto, e si riprova fra quindici minuti. I
 * dati restano in `localStorage` per quindici minuti (tre ore se la rete non risponde).
 * Con «meno movimento» il canvas resta spento. `?meteo=temporale` (o pioggia, pioggerella, neve,
 * nebbia, sereno, notte, nuvoloso, vento, acquazzone) forza una scena per provarla, senza rete.
 */
(function () {
  "use strict";

  var radice = document.documentElement;
  var CHIAVE = "mut-meteo", CACHE = "mut-meteo-dati";
  var URL_METEO = "https://api.open-meteo.com/v1/forecast?latitude=37.61&longitude=15.16" +
    "&current=temperature_2m,weather_code,is_day,cloud_cover,wind_speed_10m,wind_direction_10m" +
    "&wind_speed_unit=kmh&timezone=Europe%2FRome";
  var FRESCO = 15 * 60 * 1000, VECCHIO = 3 * 60 * 60 * 1000;

  var ridotto = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var acceso = true;
  try { acceso = window.localStorage.getItem(CHIAVE) !== "off"; } catch (e) { /* si resta accesi */ }
  var forzato = null;
  try { var fz = /[?&]meteo=([a-z]+)/.exec((window.location && window.location.search) || ""); if (fz) forzato = fz[1]; } catch (e2) { /* niente */ }

  var tela = null, ctx = null, W = 0, H = 0, richiesta = null, passi = 0;
  var stato = null;                          // la scena: vedi `classifica`
  var gocce = [], schizzi = [], fiocchi = [], nuvole = [], banchi = [], foglie = [], raffiche = [], stelle = [];
  var lampo = 0, fulmine = null, prossimoLampo = 200, secondoLampo = 0;
  var fondo = 0, ultimoFondo = -999, scuro = false;

  function caso(a, b) { return a + Math.random() * (b - a); }
  function limita(x, a, b) { return Math.max(a, Math.min(b, x)); }

  // --- Dal codice del tempo alla scena -------------------------------------
  // Codici WMO di Open-Meteo: 0 sereno, 1-3 nuvole, 45/48 nebbia, 51-57 pioggerella, 61-67 pioggia,
  // 71-77 neve, 80-82 acquazzoni, 85/86 neve a rovesci, 95-99 temporale.
  var NOMI = { sereno: "sereno", poco: "poco nuvoloso", nuvoloso: "nuvoloso", coperto: "coperto", nebbia: "nebbia",
               pioggerella: "pioggerella", pioggia: "pioggia", acquazzone: "acquazzone", temporale: "temporale", neve: "neve", notte: "notte serena" };
  var PIOGGIA = { 51: 0.22, 53: 0.34, 55: 0.46, 56: 0.34, 57: 0.46, 61: 0.5, 63: 0.72, 65: 0.95, 66: 0.62, 67: 0.86, 80: 0.5, 81: 0.78, 82: 1 };
  var NEVE = { 71: 0.4, 73: 0.65, 75: 0.92, 77: 0.35, 85: 0.5, 86: 0.85 };
  var NEBBIA = { 45: 0.6, 48: 0.85 };
  var TEMPORALE = { 95: 0.78, 96: 0.95, 99: 1 };
  var NUVOLE_CODICE = { 0: 0.04, 1: 0.2, 2: 0.5, 3: 0.92 };

  function classifica(d) {
    var c = Number(d.weather_code), giorno = d.is_day === 1 || d.is_day === true;
    var copertura = typeof d.cloud_cover === "number" ? limita(d.cloud_cover / 100, 0, 1) : (c in NUVOLE_CODICE ? NUVOLE_CODICE[c] : 0.6);
    var s = { codice: c, giorno: giorno, temp: typeof d.temperature_2m === "number" ? d.temperature_2m : null,
              nuvole: copertura, pioggia: 0, neve: 0, nebbia: 0, temporale: false, vento: Math.max(0, Number(d.wind_speed_10m) || 0),
              dir: Number(d.wind_direction_10m) || 270, arcobaleno: false, chiave: "sereno" };
    if (c in PIOGGIA) s.pioggia = PIOGGIA[c];
    if (c in NEVE) s.neve = NEVE[c];
    if (c in NEBBIA) s.nebbia = NEBBIA[c];
    if (c in TEMPORALE) { s.temporale = true; s.pioggia = TEMPORALE[c]; }
    if (s.pioggia || s.neve || s.temporale) s.nuvole = Math.max(s.nuvole, s.temporale ? 0.95 : 0.8);
    if (s.nebbia) s.nuvole = Math.max(s.nuvole, 0.5);
    s.arcobaleno = giorno && (c === 80 || c === 81 || c === 82) && copertura < 0.9;
    s.chiave = s.temporale ? "temporale" : s.neve ? "neve" : s.nebbia ? "nebbia"
      : c >= 80 && c <= 82 ? "acquazzone" : s.pioggia >= 0.5 ? "pioggia" : s.pioggia ? "pioggerella"
      : s.nuvole > 0.85 ? "coperto" : s.nuvole > 0.5 ? "nuvoloso" : s.nuvole > 0.18 ? "poco"
      : giorno ? "sereno" : "notte";
    return s;
  }
  // Scene di prova per `?meteo=`: stessi campi che manda Open-Meteo.
  var PROVE = {
    sereno: { weather_code: 0, is_day: 1, cloud_cover: 3, wind_speed_10m: 6, temperature_2m: 22 },
    notte: { weather_code: 0, is_day: 0, cloud_cover: 5, wind_speed_10m: 4, temperature_2m: 14 },
    nuvoloso: { weather_code: 3, is_day: 1, cloud_cover: 85, wind_speed_10m: 12, temperature_2m: 17 },
    pioggerella: { weather_code: 53, is_day: 1, cloud_cover: 90, wind_speed_10m: 10, temperature_2m: 15 },
    pioggia: { weather_code: 63, is_day: 1, cloud_cover: 95, wind_speed_10m: 18, temperature_2m: 14 },
    acquazzone: { weather_code: 81, is_day: 1, cloud_cover: 70, wind_speed_10m: 20, temperature_2m: 16 },
    temporale: { weather_code: 95, is_day: 1, cloud_cover: 100, wind_speed_10m: 34, temperature_2m: 13 },
    neve: { weather_code: 73, is_day: 1, cloud_cover: 100, wind_speed_10m: 8, temperature_2m: -1 },
    nebbia: { weather_code: 45, is_day: 1, cloud_cover: 80, wind_speed_10m: 3, temperature_2m: 9 },
    vento: { weather_code: 1, is_day: 1, cloud_cover: 25, wind_speed_10m: 48, wind_direction_10m: 300, temperature_2m: 15 },
  };

  // Le fasi della luna: 0 nuova, 0.5 piena. Dalla luna nuova del 6 gennaio 2000.
  function etaLuna(data) {
    var giorni = (data.getTime() / 86400000) + 2440587.5 - 2451550.26;
    var eta = (giorni % 29.530588) / 29.530588;
    return eta < 0 ? eta + 1 : eta;
  }

  // --- Il tasto ----------------------------------------------------------
  function testoStato() {
    if (!stato) return "Effetti meteo di Acireale";
    return "Acireale: " + NOMI[stato.chiave] + (stato.temp !== null ? ", " + Math.round(stato.temp) + " °C" : "");
  }
  function aggiornaTasti() {
    var tasti = document.querySelectorAll("[data-meteo-tasto]");
    for (var i = 0; i < tasti.length; i++) {
      tasti[i].setAttribute("aria-pressed", acceso ? "true" : "false");
      tasti[i].setAttribute("title", testoStato() + (acceso ? " · clic per spegnere" : " · clic per accendere"));
    }
  }
  function imposta(nuovo) {
    acceso = !!nuovo;
    try { if (acceso) window.localStorage.removeItem(CHIAVE); else window.localStorage.setItem(CHIAVE, "off"); } catch (e) { /* per questa pagina */ }
    aggiornaTasti();
    if (acceso) avvia(); else spegni();
  }

  // --- La scena ------------------------------------------------------------
  function costruisci() {
    if (!stato || !W) return;
    var larg = limita(W / 1280, 0.5, 1.3), i;
    gocce = []; fiocchi = []; nuvole = []; banchi = []; foglie = []; raffiche = []; stelle = [];
    var nGocce = stato.pioggia ? Math.round((40 + stato.pioggia * 300) * larg) : 0;
    for (i = 0; i < nGocce; i++) gocce.push(nuovaGoccia(true));
    var nNeve = stato.neve && !radice.classList.contains("natale") ? Math.round((30 + stato.neve * 190) * larg) : 0;
    for (i = 0; i < nNeve; i++) fiocchi.push({ x: caso(0, W), y: caso(0, H), r: caso(1, 3.2), vy: caso(0.6, 1.8), fase: caso(0, 6.28) });
    var nNuvole = Math.round(stato.nuvole * 7 * larg + (stato.nuvole > 0.1 ? 1 : 0));
    for (i = 0; i < nNuvole; i++) nuvole.push(nuovaNuvola(caso(-150, W + 150)));
    nuvole.sort(function (a, b) { return a.z - b.z; });
    var nBanchi = stato.nebbia ? 7 : 0;
    for (i = 0; i < nBanchi; i++) banchi.push({ x: caso(-200, W), y: H * caso(0.25, 1), w: caso(380, 760), v: caso(0.12, 0.4), fase: caso(0, 6.28) });
    var nFoglie = stato.vento >= 22 ? Math.min(16, Math.round((stato.vento - 18) / 2)) : 0;
    for (i = 0; i < nFoglie; i++) foglie.push(nuovaFoglia(true));
    var nRaffiche = stato.vento >= 30 ? Math.min(8, Math.round((stato.vento - 24) / 4)) : 0;
    for (i = 0; i < nRaffiche; i++) raffiche.push({ x: caso(-300, W), y: caso(40, H - 40), l: caso(90, 220), v: caso(10, 18), fase: caso(0, 6.28) });
    if (!stato.giorno && stato.nuvole < 0.75) for (i = 0; i < 70; i++) stelle.push({ x: caso(0, W), y: caso(0, H * 0.7), r: caso(0.5, 1.5), fase: caso(0, 6.28), v: caso(0.02, 0.07) });
    prossimoLampo = Math.round(caso(60, 240));
  }
  // Il vento verso destra (+1) o sinistra (-1): da Ovest (270°) spinge a destra.
  function versoVento() { return -Math.sin((stato.dir || 270) * Math.PI / 180); }
  function inclina() { return limita(versoVento() * stato.vento / 55, -0.7, 0.7); }
  function nuovaGoccia(inAlto) {
    var z = Math.random();
    return { x: caso(-100, W + 100), y: inAlto ? caso(-H, H) : caso(-60, -4), lung: 9 + z * 16 + (stato ? stato.pioggia * 6 : 0), vy: 13 + z * 15, z: z };
  }
  function nuovaFoglia(dentro) {
    var verso = versoVento() >= 0 ? 1 : -1;
    var colori = ["#a8742f", "#8a8a2e", "#c0872c", "#6e6f2a", "#9c5a26"];
    return { x: dentro ? caso(0, W) : (verso > 0 ? -20 : W + 20), y: caso(H * 0.15, H * 0.95), vx: caso(2.5, 5.5) * verso, vy: caso(-0.4, 0.6),
             rot: caso(0, 6.28), vr: caso(-0.15, 0.15), r: caso(3, 6), fase: caso(0, 6.28), col: colori[Math.floor(Math.random() * colori.length)] };
  }

  // --- Il canvas -----------------------------------------------------------
  function dimensiona() {
    var rapporto = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    tela.width = Math.floor(W * rapporto); tela.height = Math.floor(H * rapporto);
    tela.style.width = W + "px"; tela.style.height = H + "px";
    ctx.setTransform(rapporto, 0, 0, rapporto, 0, 0);
    costruisci();
  }
  function creaTela() {
    if (tela) return true;
    try {
      tela = document.createElement("canvas");
      tela.className = "meteo-tela"; tela.setAttribute("aria-hidden", "true");
      ctx = tela.getContext("2d");
      if (!ctx) { tela = null; return false; }
      document.body.appendChild(tela);
      dimensiona();
      window.addEventListener("resize", function () { if (tela) dimensiona(); });
    } catch (e) { tela = null; return false; }
    return true;
  }
  function rileva() {
    scuro = radice.getAttribute("data-tema") === "scuro";
    var barra = document.querySelector(".ultimora-barra"), r = barra && barra.getBoundingClientRect ? barra.getBoundingClientRect() : null;
    fondo = r && r.top > 0 && r.top < H ? r.top : H;
  }

  // --- Disegno ---------------------------------------------------------------
  function sole(x, y, forza) {
    var g = ctx.createRadialGradient(x, y, 0, x, y, 260);
    g.addColorStop(0, "rgba(255,214,90," + (0.5 * forza) + ")"); g.addColorStop(0.25, "rgba(255,190,60," + (0.2 * forza) + ")"); g.addColorStop(1, "rgba(255,190,60,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 260, 0, Math.PI * 2); ctx.fill();
    ctx.save(); ctx.translate(x, y); ctx.rotate(passi * 0.0025);
    for (var i = 0; i < 12; i++) {
      ctx.rotate(Math.PI / 6);
      var lungo = i % 2 ? 150 : 215, k = 0.5 + 0.5 * Math.sin(passi * 0.02 + i);
      ctx.fillStyle = "rgba(255,205,80," + ((0.05 + 0.04 * k) * forza) + ")";
      ctx.beginPath(); ctx.moveTo(0, -26); ctx.lineTo(-13, -lungo); ctx.lineTo(13, -lungo); ctx.closePath(); ctx.fill();
    }
    ctx.restore();
    ctx.fillStyle = "rgba(255,226,120," + (0.92 * forza) + ")"; ctx.beginPath(); ctx.arc(x, y, 30, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "rgba(255,246,200," + (0.7 * forza) + ")"; ctx.beginPath(); ctx.arc(x - 6, y - 6, 15, 0, Math.PI * 2); ctx.fill();
  }
  function luna(x, y, r, eta, forza) {
    var g = ctx.createRadialGradient(x, y, r * 0.8, x, y, r * 4);
    g.addColorStop(0, "rgba(200,215,255," + (0.22 * forza) + ")"); g.addColorStop(1, "rgba(200,215,255,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "rgba(70,82,115," + (0.5 * forza) + ")"; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    var k = Math.cos(2 * Math.PI * eta), cresce = eta < 0.5;
    ctx.fillStyle = "rgba(245,245,225," + (0.95 * forza) + ")";
    ctx.beginPath();
    ctx.arc(x, y, r, -Math.PI / 2, Math.PI / 2, !cresce);
    ctx.ellipse(x, y, Math.max(0.01, Math.abs(k)) * r, r, 0, Math.PI / 2, -Math.PI / 2, (k > 0) === cresce);
    ctx.closePath(); ctx.fill();
  }
  // LE NUVOLE (11/11/2026, su richiesta: «le nuvole sono brutte e statiche», e poi «sembrano molto
  // brutte dagli screen» per le sagome piatte della prima prova). Ogni nuvola è un cumulo morbido:
  // gli sbuffi si dipingono una volta sola su un foglietto suo, sfocati, così i bordi sfumano come
  // vapore; sopra si stende l'ombra della pancia e la luce sulla cima. Mentre passa galleggia e
  // respira piano. Due profondità: le lontane piccole, tenui e lente, le vicine grandi e più svelte.
  function nuovaNuvola(x) {
    var z = Math.random(), s = (0.55 + z * 0.75) * limita(W / 1280, 0.6, 1.2), w = caso(140, 240) * s;
    return { x: x, y: caso(70, Math.max(120, H * 0.3)) + (1 - z) * 16, z: z, s: s, w: w,
             v: 0.12 + z * 0.42 + caso(0, 0.08), fase: caso(0, 6.28), foglio: null, chiave: "" };
  }
  // I colori della scena: [luce, ombra, trasparenza].
  function tavolozza(buia) {
    if (buia) return ["#a3a9b6", "#5f6676", scuro ? 0.75 : 0.85];
    if (radice.getAttribute("data-cielo") === "tramonto") return ["#fff3ea", "#e8b2bc", 0.92];
    if (stato.giorno) return scuro ? ["#d7dce6", "#8e98aa", 0.32] : ["#ffffff", "#cdd6e4", 0.95];
    return ["#8e98b8", "#3a4262", scuro ? 0.55 : 0.5];
  }
  // Il foglietto di una nuvola: una fila bassa di sbuffi medi che fa la base, e sopra tre-cinque
  // sbuffi grandi, più alti al centro. Il foglio si misura sugli sbuffi veri (più il margine della
  // sfocatura), così niente bordo resta tagliato dritto.
  function foglietto(w, luce, ombra, sfoca) {
    var sb = [], k, nt = Math.round(caso(3, 5));
    // La base: due sbuffi bassi alle estremità (il resto lo fa l'ellisse liscia più sotto).
    sb.push([-w * 0.36, -w * 0.1, w * 0.1], [w * 0.36, -w * 0.1, w * 0.1]);
    for (k = 0; k < nt; k++) {
      var ut = nt > 1 ? k / (nt - 1) - 0.5 : 0, cu = 1 - 4 * ut * ut, rt = w * (0.14 + 0.1 * cu) * caso(0.9, 1.12);
      sb.push([ut * w * 0.55 + caso(-0.04, 0.04) * w, -w * 0.12 - rt * 0.55 - cu * w * 0.05, rt]);
    }
    var x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (k = 0; k < sb.length; k++) { x0 = Math.min(x0, sb[k][0] - sb[k][2]); x1 = Math.max(x1, sb[k][0] + sb[k][2]); y0 = Math.min(y0, sb[k][1] - sb[k][2]); y1 = Math.max(y1, sb[k][1] + sb[k][2]); }
    var m = Math.ceil(sfoca * 3 + 2), f = document.createElement("canvas");
    f.width = Math.ceil(x1 - x0 + 2 * m); f.height = Math.ceil(y1 - y0 + 2 * m);
    var c = f.getContext("2d");
    if (!c) return null;
    var ox = m - x0, oy = m - y0, base = oy - w * 0.04;
    var morbido = "filter" in c;
    if (morbido) c.filter = "blur(" + sfoca.toFixed(1) + "px)";
    c.fillStyle = luce; c.beginPath();
    for (k = 0; k < sb.length; k++) { c.moveTo(ox + sb[k][0] + sb[k][2], oy + sb[k][1]); c.arc(ox + sb[k][0], oy + sb[k][1], sb[k][2], 0, Math.PI * 2); }
    c.moveTo(ox + w * 0.46, oy - w * 0.09); c.ellipse(ox, oy - w * 0.09, w * 0.46, w * 0.075, 0, 0, Math.PI * 2);
    c.fill();
    if (morbido) c.filter = "none";
    // L'ombra sale dal fondo fino a metà; la luce viene dall'alto a sinistra. Solo dentro la nuvola.
    c.globalCompositeOperation = "source-atop";
    var g = c.createLinearGradient(0, m, 0, base);
    g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(0.55, "rgba(255,255,255,0)"); g.addColorStop(1, ombra);
    c.fillStyle = g; c.fillRect(0, 0, f.width, f.height);
    var cx = ox - w * 0.12, cy = m + (base - m) * 0.25;
    var gl = c.createRadialGradient(cx, cy, 0, cx, cy, w * 0.45);
    gl.addColorStop(0, "rgba(255,255,255,.5)"); gl.addColorStop(1, "rgba(255,255,255,0)");
    c.fillStyle = gl; c.fillRect(0, 0, f.width, f.height);
    c.globalCompositeOperation = "source-over";
    return { tela: f, ox: ox, oy: oy };
  }
  function prepara(n, t) {
    var chiave = t[0] + t[1];
    if (n.foglio && n.chiave === chiave) return;
    n.foglio = foglietto(n.w, t[0], t[1], Math.max(2, 4.5 * n.s));
    n.chiave = chiave;
  }
  function disegnaNuvole(buia) {
    if (!nuvole.length) return;
    var t = tavolozza(buia);
    for (var i = 0; i < nuvole.length; i++) {
      var n = nuvole[i];
      if (n.x < -n.w - 80 || n.x > W + n.w + 80) continue;
      prepara(n, t);
      if (!n.foglio) continue;
      // Galleggia appena e respira: si allarga e si abbassa di un soffio, piano.
      var y = n.y + Math.sin(n.fase + passi * 0.007) * 2.5, r = 1 + 0.025 * Math.sin(n.fase * 1.3 + passi * 0.005);
      var fo = n.foglio;
      ctx.save(); ctx.globalAlpha = t[2] * (0.62 + 0.38 * n.z);
      ctx.translate(n.x, y); ctx.scale(r, 2 - r);
      ctx.drawImage(fo.tela, -fo.ox, -fo.oy);
      ctx.restore();
    }
  }
  function arcobaleno() {
    var colori = ["255,70,70", "255,150,50", "255,220,70", "80,200,110", "70,150,240", "120,90,220"];
    var cx = W * 0.32, cy = H * 1.08, r0 = Math.min(H * 0.95, W * 0.7), k = limita(0.5 + 0.5 * Math.sin(passi * 0.004), 0.55, 1);
    for (var i = 0; i < colori.length; i++) {
      ctx.strokeStyle = "rgba(" + colori[i] + "," + (0.16 * k) + ")"; ctx.lineWidth = 9;
      ctx.beginPath(); ctx.arc(cx, cy, r0 - i * 9, Math.PI * 1.08, Math.PI * 1.92); ctx.stroke();
    }
  }
  // Un fulmine: dal cielo scende a zig zag, con un paio di rami.
  function nuovoFulmine() {
    var x = caso(W * 0.1, W * 0.9), y = 0, punti = [[x, y]], rami = [];
    var arrivo = H * caso(0.35, 0.7);
    while (y < arrivo) {
      x += caso(-34, 34); y += caso(22, 48); punti.push([x, y]);
      if (Math.random() < 0.22 && y < arrivo * 0.8) {
        var rx = x, ry = y, ramo = [[rx, ry]], d = Math.random() < 0.5 ? -1 : 1;
        for (var k = 0; k < 4; k++) { rx += d * caso(10, 28); ry += caso(14, 30); ramo.push([rx, ry]); }
        rami.push(ramo);
      }
    }
    return { punti: punti, rami: rami, vita: 14 };
  }
  function tracciaFulmine(f) {
    var a = limita(f.vita / 14, 0, 1);
    ctx.save(); ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.shadowColor = "rgba(190,215,255,.95)"; ctx.shadowBlur = 16;
    var linee = [f.punti].concat(f.rami);
    for (var j = 0; j < linee.length; j++) {
      var p = linee[j];
      ctx.strokeStyle = "rgba(235,243,255," + (0.95 * a) + ")"; ctx.lineWidth = j ? 1.4 : 2.6;
      ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]);
      for (var i = 1; i < p.length; i++) ctx.lineTo(p[i][0], p[i][1]);
      ctx.stroke();
    }
    ctx.restore();
  }
  function foglia(f) {
    ctx.save(); ctx.translate(f.x, f.y); ctx.rotate(f.rot); ctx.scale(1, 0.55 + 0.45 * Math.cos(f.fase + passi * 0.1));
    ctx.fillStyle = f.col; ctx.beginPath(); ctx.moveTo(-f.r, 0); ctx.quadraticCurveTo(0, -f.r * 0.9, f.r, 0); ctx.quadraticCurveTo(0, f.r * 0.9, -f.r, 0); ctx.fill();
    ctx.restore();
  }

  function disegna() {
    ctx.clearRect(0, 0, W, H);
    if (!stato) return;
    var i, buia = stato.temporale || stato.pioggia >= 0.5 || stato.nuvole > 0.9 && stato.pioggia > 0;
    // Il cielo: sole o luna e stelle, attenuati dalle nuvole.
    var aperto = 1 - stato.nuvole * 0.85;
    if (stato.giorno && aperto > 0.12 && !stato.pioggia && !stato.nebbia) sole(W - (W < 640 ? 60 : 120), W < 640 ? 70 : 110, aperto);
    else if (!stato.giorno && aperto > 0.12 && !stato.pioggia) {
      for (i = 0; i < stelle.length; i++) {
        var st = stelle[i], b = 0.4 + 0.6 * Math.abs(Math.sin(st.fase + passi * st.v));
        ctx.fillStyle = "rgba(255,255,235," + (b * aperto * (scuro ? 0.9 : 0.55)) + ")";
        ctx.beginPath(); ctx.arc(st.x, st.y, st.r, 0, Math.PI * 2); ctx.fill();
      }
      luna(W - (W < 640 ? 60 : 120), W < 640 ? 70 : 110, 22, etaLuna(new Date()), aperto);
    }
    if (stato.arcobaleno) arcobaleno();
    disegnaNuvole(buia);
    // La nebbia: banchi bassi e un velo.
    if (stato.nebbia) {
      var veloA = (scuro ? 0.08 : 0.1) * stato.nebbia;
      ctx.fillStyle = scuro ? "rgba(170,182,200," + veloA + ")" : "rgba(150,162,176," + veloA + ")"; ctx.fillRect(0, 0, W, H);
      for (i = 0; i < banchi.length; i++) {
        var bn = banchi[i], by = bn.y + Math.sin(bn.fase + passi * 0.006) * 14;
        ctx.save(); ctx.translate(bn.x, by); ctx.scale(1, 0.3);
        var g = ctx.createRadialGradient(0, 0, 0, 0, 0, bn.w / 2);
        var colore = scuro ? "185,196,214" : "160,172,186";
        g.addColorStop(0, "rgba(" + colore + "," + (0.3 * stato.nebbia) + ")"); g.addColorStop(1, "rgba(" + colore + ",0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, bn.w / 2, 0, Math.PI * 2); ctx.fill();
        ctx.restore();
      }
    }
    // La neve vera.
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = scuro ? "rgba(200,220,245,.3)" : "rgba(90,125,170,.5)"; ctx.lineWidth = 0.7;
    for (i = 0; i < fiocchi.length; i++) { var f = fiocchi[i]; ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); }
    // La pioggia.
    if (gocce.length) {
      var sl = inclina();
      ctx.lineCap = "round";
      for (i = 0; i < gocce.length; i++) {
        var d = gocce[i], a = 0.18 + d.z * 0.34;
        ctx.strokeStyle = scuro ? "rgba(180,208,245," + a + ")" : "rgba(55,95,165," + (a + 0.1) + ")"; ctx.lineWidth = 0.8 + d.z * 0.9;
        ctx.beginPath(); ctx.moveTo(d.x, d.y); ctx.lineTo(d.x - sl * d.lung, d.y - d.lung); ctx.stroke();
      }
      for (i = 0; i < schizzi.length; i++) {
        var sc = schizzi[i], k = sc.vita / 10;
        ctx.strokeStyle = scuro ? "rgba(190,215,248," + (0.5 * k) + ")" : "rgba(60,100,170," + (0.55 * k) + ")"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.ellipse(sc.x, sc.y, (11 - sc.vita) * 0.7 + 1, (11 - sc.vita) * 0.25 + 0.4, 0, Math.PI, Math.PI * 2); ctx.stroke();
      }
    }
    // Vento: raffiche e foglie.
    for (i = 0; i < raffiche.length; i++) {
      var rf = raffiche[i], dv = versoVento() >= 0 ? 1 : -1;
      ctx.strokeStyle = scuro ? "rgba(220,230,245,.16)" : "rgba(90,110,140,.18)"; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(rf.x, rf.y);
      for (var t = 1; t <= 6; t++) ctx.lineTo(rf.x - dv * rf.l * t / 6, rf.y + Math.sin(rf.fase + passi * 0.05 + t * 0.7) * 4);
      ctx.stroke();
    }
    for (i = 0; i < foglie.length; i++) foglia(foglie[i]);
    // I lampi: la pagina si schiarisce un istante, poi il fulmine.
    if (lampo > 0.02) { ctx.fillStyle = "rgba(235,242,255," + (lampo * (scuro ? 0.3 : 0.4)) + ")"; ctx.fillRect(0, 0, W, H); }
    if (fulmine) tracciaFulmine(fulmine);
  }

  // --- Il ciclo ----------------------------------------------------------------
  function passo() {
    passi++;
    if (passi % 45 === 0) rileva();
    var i;
    if (stato.pioggia && gocce.length) {
      var sl = inclina();
      for (i = 0; i < gocce.length; i++) {
        var d = gocce[i];
        d.y += d.vy; d.x += sl * d.vy;
        if (d.y > fondo) {
          if (schizzi.length < 60 && Math.random() < 0.35 && d.z > 0.3) schizzi.push({ x: d.x, y: fondo, vita: 10 });
          gocce[i] = nuovaGoccia(false);
        }
      }
      for (i = schizzi.length - 1; i >= 0; i--) { if (--schizzi[i].vita <= 0) schizzi.splice(i, 1); }
    }
    for (i = 0; i < fiocchi.length; i++) {
      var f = fiocchi[i];
      f.y += f.vy; f.x += Math.sin(f.fase + passi * 0.03) * 0.5 + versoVento() * stato.vento * 0.03;
      if (f.y > H + 4) { f.y = -4; f.x = caso(0, W); }
      if (f.x < -6) f.x = W + 6; else if (f.x > W + 6) f.x = -6;
    }
    var vv = versoVento() >= 0 ? 1 : -1, corsa = 0.7 + Math.min(1.6, stato.vento * 0.035);
    // Le nuvole corrono col vento: le vicine più svelte. Quella che esce rientra dall'altro lato, nuova.
    for (i = 0; i < nuvole.length; i++) {
      var n = nuvole[i]; n.x += vv * n.v * corsa;
      if (n.x > W + n.w + 60 || n.x < -n.w - 60) { nuvole[i] = nuovaNuvola(vv > 0 ? -n.w - 50 : W + n.w + 50); }
    }
    for (i = 0; i < banchi.length; i++) { var b = banchi[i]; b.x += vv * b.v; if (b.x > W + 400) b.x = -400; else if (b.x < -400) b.x = W + 400; }
    for (i = 0; i < foglie.length; i++) {
      var fo = foglie[i];
      fo.x += fo.vx; fo.y += fo.vy + Math.sin(fo.fase + passi * 0.08) * 1.2; fo.rot += fo.vr;
      if (fo.x < -30 || fo.x > W + 30 || fo.y < -30 || fo.y > H + 30) foglie[i] = nuovaFoglia(false);
    }
    for (i = 0; i < raffiche.length; i++) {
      var rf = raffiche[i]; rf.x += vv * rf.v;
      if (rf.x > W + rf.l + 40 || rf.x < -rf.l - 40) { rf.x = vv > 0 ? -rf.l : W + rf.l; rf.y = caso(40, H - 40); }
    }
    if (stato.temporale) {
      if (--prossimoLampo <= 0) {
        lampo = 1; fulmine = nuovoFulmine();
        secondoLampo = Math.random() < 0.55 ? 9 : 0;
        prossimoLampo = Math.round(caso(240, 720));
      }
      if (secondoLampo > 0 && --secondoLampo === 0) { lampo = 0.8; fulmine = nuovoFulmine(); }
    }
    if (lampo > 0) lampo *= 0.88;
    if (fulmine && --fulmine.vita <= 0) fulmine = null;
  }
  function ciclo() {
    richiesta = null;
    if (!acceso || !tela) return;
    if (!document.hidden && stato) { passo(); disegna(); }
    richiesta = window.requestAnimationFrame(ciclo);
  }
  function avvia() {
    if (ridotto || !stato) return;
    if (!creaTela()) return;
    tela.style.display = "block";
    costruisci(); rileva();
    if (!richiesta) richiesta = window.requestAnimationFrame(ciclo);
  }
  function spegni() {
    if (richiesta && window.cancelAnimationFrame) window.cancelAnimationFrame(richiesta);
    richiesta = null;
    if (tela) { tela.style.display = "none"; ctx.clearRect(0, 0, W, H); }
  }

  // --- I dati ---------------------------------------------------------------------
  function applica(d) {
    stato = classifica(d);
    radice.setAttribute("data-meteo", stato.chiave);
    aggiornaTasti();
    if (acceso) avvia();
  }
  function leggiCache() {
    try {
      var c = JSON.parse(window.localStorage.getItem(CACHE) || "null");
      if (c && c.t && c.dati && typeof c.dati.weather_code === "number") return c;
    } catch (e) { /* niente */ }
    return null;
  }
  function scarica() {
    if (forzato || !window.fetch) return;
    var cache = leggiCache(), ora = Date.now();
    if (cache && ora - cache.t < FRESCO) { if (!stato) applica(cache.dati); return; }
    var stop = window.AbortController ? new window.AbortController() : null;
    var scade = setTimeout(function () { if (stop) stop.abort(); }, 8000);
    window.fetch(URL_METEO, stop ? { signal: stop.signal } : undefined)
      .then(function (r) { if (!r.ok) throw new Error("meteo " + r.status); return r.json(); })
      .then(function (j) {
        clearTimeout(scade);
        if (!j || !j.current || typeof j.current.weather_code !== "number") throw new Error("meteo: risposta senza dati");
        try { window.localStorage.setItem(CACHE, JSON.stringify({ t: Date.now(), dati: j.current })); } catch (e) { /* pazienza */ }
        applica(j.current);
      })
      .catch(function () {
        clearTimeout(scade);
        // Niente rete: si usa l'ultimo dato se è di meno di tre ore, altrimenti nessun effetto (non si inventa il tempo).
        if (!stato && cache && ora - cache.t < VECCHIO) applica(cache.dati);
      });
  }

  document.addEventListener("click", function (e) {
    var tasto = e.target && e.target.closest && e.target.closest("[data-meteo-tasto]");
    if (tasto) imposta(!acceso);
  });
  document.addEventListener("visibilitychange", function () { if (!document.hidden && acceso && stato && !richiesta && tela) richiesta = window.requestAnimationFrame(ciclo); });

  function pronto() {
    aggiornaTasti();
    if (forzato && PROVE[forzato]) applica(PROVE[forzato]);
    else { scarica(); setInterval(scarica, FRESCO); }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", pronto);
  else pronto();

  // Per i test e per provare una scena a mano: `__meteo.provaScena("temporale")`.
  window.__meteo = {
    classifica: classifica,
    etaLuna: etaLuna,
    imposta: imposta,
    acceso: function () { return acceso; },
    provaScena: function (nome) { if (PROVE[nome]) applica(PROVE[nome]); },
    applica: applica,
    stato: function () {
      return { acceso: acceso, scena: stato, gocce: gocce.length, fiocchi: fiocchi.length, nuvole: nuvole.length, banchi: banchi.length,
               foglie: foglie.length, raffiche: raffiche.length, stelle: stelle.length, lampo: lampo, fulmine: !!fulmine, passi: passi };
    },
    // Solo per i test: avanti di n fotogrammi, senza aspettare il browser.
    avanza: function (n) { for (var i = 0; i < n && stato && tela; i++) { passo(); disegna(); } },
  };
})();
