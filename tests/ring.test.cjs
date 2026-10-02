/* I due lottatori della home (static/ring.js) senza browser.
 *
 * Si carica lo script in una sandbox con un DOM finto — una finestra di
 * 1200×800, la striscia dell'ultim'ora come pavimento, qualche «tasto»
 * come elemento solido della pagina, un puntatore che si muove a comando
 * — e si fa girare la fisica per qualche minuto simulato.
 *
 * Quello che si difende:
 *   - i lottatori restano dentro la finestra e non esplodono (coordinate
 *     NaN: il guasto tipico di queste simulazioni);
 *   - è una lotta vera: qualcuno va K.O.;
 *   - si prendono col puntatore, si portano in giro e si lanciano;
 *   - gli elementi della pagina reggono chi ci atterra sopra;
 *   - per raggiungere l'avversario ci si arrampica;
 *   - chi ha chiesto meno movimento non ha né animazione né presa;
 *   - a scheda nascosta il ciclo si ferma.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SORGENTE = fs.readFileSync(path.join(__dirname, "..", "web", "static", "ring.js"), "utf8");

function riquadro(l, t, r, b) {
  return { left: l, top: t, right: r, bottom: b, width: r - l, height: b - t };
}

function ambiente({ ridotto = false, larghezza = 1200, altezza = 800, solidi = [], campo = null, memoria = {}, estensione = false, premio = null } = {}) {
  const richieste = [];
  const ascoltatori = {};
  const contesto2d = new Proxy({}, {
    get(obj, nome) {
      if (nome in obj) return obj[nome];
      if (nome === "createRadialGradient" || nome === "createLinearGradient") return () => ({ addColorStop() {} });
      return () => {};
    },
    set(obj, nome, valore) { obj[nome] = valore; return true; },
  });
  const tela = { clientWidth: larghezza, clientHeight: altezza, width: 0, height: 0, style: {},
                 getContext: () => contesto2d };
  const pavimento = altezza - 44;
  const barra = { getBoundingClientRect: () => riquadro(0, pavimento, larghezza, altezza) };
  const elementi = solidi.map(([l, t, r, b]) => ({
    getBoundingClientRect: () => riquadro(l, t, r, b), closest: () => null,
  }));
  const classi = new Set();
  const tasto = { hidden: true, attr: {}, title: "", ascolta: {},
    addEventListener(t, fn) { this.ascolta[t] = fn; }, setAttribute(k, v) { this.attr[k] = v; } };
  const documento = {
    hidden: false,
    documentElement: { classList: { add: (c) => classi.add(c), remove: (c) => classi.delete(c) } },
    fonts: null,
    body: { querySelectorAll: () => elementi },
    querySelector(sel) {
      // Nell'estensione i pezzi del ring non stanno nella pagina.
      if (!estensione) {
        if (sel === "[data-ring]") return tela;
        if (sel === ".ultimora-barra") return barra;
        if (sel === "[data-gioca]") return tasto;
      }
      if (sel === ".ricerca-grande input" && campo) return { getBoundingClientRect: () => riquadro(...campo) };
      return null;
    },
    addEventListener(tipo, fn) { (ascoltatori["doc:" + tipo] = ascoltatori["doc:" + tipo] || []).push(fn); },
  };
  const finestra = {
    devicePixelRatio: 1, innerWidth: larghezza, innerHeight: altezza, scrollY: 0,
    matchMedia: () => ({ matches: ridotto }),
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null), setItem: (k, v) => { memoria[k] = String(v); } },
    addEventListener(tipo, fn) { (ascoltatori[tipo] = ascoltatori[tipo] || []).push(fn); },
  };
  if (estensione) {
    // Come fa `estensione/pacchetto/prepara.js`: i pezzi in una radice a parte
    // (senza striscia: il pavimento è il fondo della finestra) e una memoria propria.
    finestra.__ringRadice = { host: {}, querySelector: (sel) => (sel === "[data-ring]" ? tela : sel === "[data-gioca]" ? tasto : null) };
    finestra.__ringDeposito = finestra.localStorage;
    finestra.localStorage = { getItem() { throw new Error("il ring dell'estensione non deve usare localStorage"); }, setItem() { throw new Error("no"); } };
  }
  if (premio) finestra.__ringPremium = premio;
  const sandbox = {
    window: finestra, document: documento, Math, Date, Object, JSON, String, Number,
    getComputedStyle: () => ({ getPropertyValue: () => "" }),
    requestAnimationFrame: (fn) => { richieste.push(fn); return richieste.length; },
    setInterval: () => 0, setTimeout: () => 0, clearTimeout: () => {},
  };
  vm.createContext(sandbox);
  vm.runInContext(SORGENTE, sandbox);
  let adesso = 0;
  const lancia = (tipo, evento) => {
    for (const fn of ascoltatori[tipo] || []) fn(evento);
  };
  const evento = (x, y, extra = {}) => Object.assign({
    clientX: x, clientY: y, button: 0, pointerType: "mouse",
    preventDefault() { this.bloccato = true; }, stopPropagation() {},
  }, extra);
  const amb = {
    finestra, documento, richieste, ascoltatori, classi, pavimento,
    tela, tasto, memoria,
    stato: () => finestra.__ring.stato(),
    lottatore: (tipo) => finestra.__ring.stato().lottatori.find((f) => f.tipo === tipo),
    // Fa girare N fotogrammi da ~16,7 ms, come farebbe il browser.
    avanza(fotogrammi, ognuno) {
      for (let i = 0; i < fotogrammi; i++) {
        const fn = richieste.shift();
        if (!fn) return i;
        adesso += 1000 / 60;
        fn(adesso);
        if (ognuno && ognuno(amb.stato()) === false) return i;
      }
      return fotogrammi;
    },
    premi: (x, y) => { const e = evento(x, y); lancia("pointerdown", e); return e; },
    muovi: (x, y) => lancia("pointermove", evento(x, y)),
    rilascia: (x, y) => lancia("pointerup", evento(x, y)),
    // Prende un lottatore per il busto e lo porta in (x, y), un po' alla volta.
    porta(tipo, x, y, passi = 30) {
      const f = amb.lottatore(tipo);
      const da = { x: f.bacino.x, y: f.bacino.y - 8 };
      const e = amb.premi(da.x, da.y);
      for (let i = 1; i <= passi; i++) {
        amb.muovi(da.x + (x - da.x) * i / passi, da.y + (y - da.y) * i / passi);
        amb.avanza(2);
      }
      return e;
    },
  };
  return amb;
}

function dentro(amb) {
  const s = amb.stato();
  for (const f of s.lottatori) {
    for (const punto of [f.testa, f.bacino]) {
      assert.ok(Number.isFinite(punto.x) && Number.isFinite(punto.y), "coordinate non finite");
      assert.ok(punto.y <= s.pavimento + 0.01, "sotto il pavimento");
      assert.ok(punto.y >= 0 && punto.x >= 0 && punto.x <= s.larghezza, "fuori dalla finestra");
    }
  }
}

test("i lottatori restano dentro la finestra e non esplodono", () => {
  const amb = ambiente({ solidi: [[300, 600, 700, 630], [900, 690, 1100, 720]] });
  for (let blocco = 0; blocco < 60; blocco++) { amb.avanza(60); dentro(amb); }
});

test("in piedi la testa sta sopra il bacino", () => {
  const amb = ambiente();
  amb.avanza(90);
  for (const f of amb.stato().lottatori) {
    if (!f.ko) assert.ok(f.testa.y < f.bacino.y, f.tipo + " a testa in giù da sveglio");
  }
});

test("è una lotta vera: prima o poi qualcuno va K.O.", () => {
  const amb = ambiente();
  let ko = false;
  for (let blocco = 0; blocco < 240 && !ko; blocco++) {
    amb.avanza(60);
    const p = amb.stato().punteggio;
    ko = p.robot + p.mela > 0;
  }
  assert.ok(ko, "in quattro minuti nessuno è andato al tappeto");
});

test("si prende col puntatore e si porta dove si vuole", () => {
  const amb = ambiente();
  amb.avanza(30);
  const e = amb.porta("mela", 200, 150);
  assert.ok(e.bloccato, "la presa non ha trattenuto il gesto");
  assert.ok(amb.classi.has("ring-trascina"), "il cursore non dice che si sta trascinando");
  const mela = amb.lottatore("mela");
  assert.ok(mela.preso);
  assert.ok(Math.abs(mela.bacino.x - 200) < 40 && mela.bacino.y < 220,
    "la mela non ha seguito il puntatore: " + JSON.stringify(mela.bacino));
  amb.rilascia(200, 150);
  assert.ok(!amb.classi.has("ring-trascina"));
  amb.avanza(240);
  dentro(amb);
  assert.ok(amb.lottatore("mela").bacino.y > 600, "lasciata in aria, la mela non è caduta");
});

test("un clic lontano dai lottatori non viene trattenuto", () => {
  const amb = ambiente();
  amb.avanza(30);
  const e = amb.premi(50, 50);
  assert.ok(!e.bloccato, "un clic sulla pagina è stato rubato dal ring");
});

test("si lancia: la velocità del gesto diventa la velocità del volo", () => {
  const amb = ambiente();
  amb.avanza(30);
  amb.porta("robot", 300, 400, 10);
  // Uno strattone veloce verso destra, poi si lascia.
  for (const x of [360, 440, 520]) { amb.muovi(x, 380); amb.avanza(1); }
  amb.rilascia(520, 380);
  const prima = amb.lottatore("robot").bacino.x;
  amb.avanza(12);
  assert.ok(amb.lottatore("robot").bacino.x - prima > 40, "il lancio non ha portato velocità");
  amb.avanza(400);
  dentro(amb);
});

test("un elemento della pagina regge chi ci atterra sopra", () => {
  const amb = ambiente({ solidi: [[450, 400, 950, 430]] });
  amb.avanza(30);
  amb.porta("mela", 700, 300);
  amb.rilascia(700, 300);
  let sopra = false;
  amb.avanza(240, (s) => {
    const m = s.lottatori.find((f) => f.tipo === "mela");
    if (m.sopraUnElemento && Math.abs(m.base - 400) < 1) { sopra = true; return false; }
  });
  assert.ok(sopra, "la mela è passata attraverso l'elemento");
  const m = amb.lottatore("mela");
  assert.ok(m.bacino.y < 400, "il corpo è dentro l'elemento");
});

test("per raggiungere l'avversario ci si arrampica", () => {
  // Un gradino largo e basso: il robot ci arriva, la mela ci mette un po'
  // a scenderne. Il caso fa la sua parte, quindi si riprova qualche volta.
  let scalato = false;
  for (let prova = 0; prova < 6 && !scalato; prova++) {
    const amb = ambiente({ solidi: [[300, 710, 1100, 740]] });
    amb.avanza(20);
    amb.porta("mela", 700, 640);
    amb.rilascia(700, 640);
    amb.avanza(1800, (s) => {
      if (s.lottatori.find((f) => f.tipo === "robot").scalando) { scalato = true; return false; }
    });
    dentro(amb);
  }
  assert.ok(scalato, "il robot non si è mai arrampicato");
});

test("chi ha chiesto meno movimento trova le lotte spente: niente animazione né presa", () => {
  const amb = ambiente({ ridotto: true });
  assert.strictEqual(amb.richieste.length, 0);
  assert.strictEqual(amb.stato().lottatori.length, 0);
  assert.strictEqual(amb.tela.style.display, "none");
  const e = amb.premi(300, 300);
  assert.ok(!e.bloccato);
});

test("il tasto spegne tutto il livello delle lotte e lo riaccende", () => {
  const amb = ambiente();
  amb.avanza(60);
  assert.strictEqual(amb.tasto.hidden, false);
  assert.strictEqual(amb.stato().lottatori.length, 2);
  amb.tasto.ascolta.click();
  assert.strictEqual(amb.stato().lottatori.length, 0, "dopo lo spegnimento ci sono ancora lottatori");
  assert.strictEqual(amb.tela.style.display, "none");
  assert.strictEqual(amb.memoria["mut-ring"], "off");
  assert.strictEqual(amb.stato().telefoni.length, 0);
  amb.avanza(5);
  assert.strictEqual(amb.richieste.length, 0, "il ciclo gira ancora da spento");
  const e = amb.premi(300, 300);
  assert.ok(!e.bloccato, "da spento il ring ruba ancora i clic");
  amb.tasto.ascolta.click();
  assert.strictEqual(amb.memoria["mut-ring"], "on");
  assert.strictEqual(amb.stato().lottatori.length, 2);
  assert.notStrictEqual(amb.tela.style.display, "none");
  amb.avanza(120); dentro(amb);
});

test("la scelta «spento» si ricorda alla visita dopo; «acceso» batte il movimento ridotto", () => {
  assert.strictEqual(ambiente({ memoria: { "mut-ring": "off" } }).stato().lottatori.length, 0);
  const acceso = ambiente({ ridotto: true, memoria: { "mut-ring": "on" } });
  assert.strictEqual(acceso.stato().lottatori.length, 2);
  assert.ok(acceso.richieste.length > 0);
});

test("gli eventi non scrivono più scritte grandi sulla pagina", () => {
  const amb = ambiente();
  for (let blocco = 0; blocco < 30; blocco++) amb.avanza(60);
  amb.finestra.__ring.avviaEvento("luna");
  assert.ok(!/PIOGGIA|LUNARE|RALLENTATORE|TERREMOTO|FURIA/.test(SORGENTE.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "")),
    "ci sono ancora annunci a schermo");
});

test("a scheda nascosta il ciclo si ferma, e riparte quando torna visibile", () => {
  const amb = ambiente();
  amb.avanza(10);
  amb.documento.hidden = true;
  amb.avanza(1);
  assert.strictEqual(amb.richieste.length, 0, "il ciclo gira ancora a scheda nascosta");
  amb.documento.hidden = false;
  for (const fn of amb.ascoltatori["doc:visibilitychange"] || []) fn();
  assert.strictEqual(amb.richieste.length, 1);
});

test("i telefoni compaiono a caso, restano nella finestra e non esplodono", () => {
  const amb = ambiente({ solidi: [[300, 600, 700, 630]] });
  let visti = 0;
  for (let blocco = 0; blocco < 120; blocco++) {
    amb.avanza(60);
    const s = amb.stato();
    visti = Math.max(visti, s.telefoni.length);
    for (const t of s.telefoni) {
      assert.ok(Number.isFinite(t.x) && Number.isFinite(t.y), "telefono con coordinate non finite");
      assert.ok(t.x >= 0 && t.x <= s.larghezza && t.y <= s.pavimento + 0.5, "telefono fuori dalla finestra");
    }
  }
  assert.ok(visti > 0, "in due minuti non è comparso nessun telefono");
});

test("un telefono lanciato addosso a un lottatore gli fa male", () => {
  const amb = ambiente();
  amb.avanza(30);
  const m = amb.lottatore("mela");
  amb.finestra.__ring.lanciaTelefono(m.testa.x - 60, m.testa.y - 2, 8, 0);
  const prima = m.danni;
  let colpito = false;
  amb.avanza(30, (s) => {
    if (s.lottatori.find((f) => f.tipo === "mela").danni > prima || s.punteggio.robot + s.punteggio.mela > 0) { colpito = true; return false; }
  });
  assert.ok(colpito, "il telefono è passato attraverso la mela");
});

test("un telefono si prende col puntatore e si lancia", () => {
  const amb = ambiente();
  amb.avanza(10);
  const i = amb.finestra.__ring.lanciaTelefono(200, 100, 0, 0);
  amb.avanza(1);
  let t = amb.stato().telefoni[i];
  const e = amb.premi(t.x, t.y);
  assert.ok(e.bloccato, "la presa sul telefono non ha trattenuto il gesto");
  for (const x of [260, 340, 440]) { amb.muovi(x, 90); amb.avanza(1); }
  assert.strictEqual(amb.stato().telefoni[i].stato, "preso");
  amb.rilascia(440, 90);
  const prima = amb.stato().telefoni[i].x;
  amb.avanza(8);
  assert.ok(amb.stato().telefoni[i].x - prima > 20, "il lancio non ha dato velocità al telefono");
});

test("gli eventi cambiano le regole: la gravità lunare rallenta la caduta", () => {
  const amb = ambiente();
  amb.avanza(5);
  amb.finestra.__ring.avviaEvento("luna");
  assert.strictEqual(amb.stato().moltG, 0.45);
  assert.strictEqual(amb.stato().evento, "luna");
  for (let blocco = 0; blocco < 20; blocco++) { amb.avanza(60); dentro(amb); }
});

test("il robot si presenta con un costume tra quelli previsti", () => {
  const amb = ambiente();
  assert.ok(["nessuno", "ninja", "cuoco", "astronauta", "mago", "pirata", "eroe"].includes(amb.stato().costume));
});

test("un lottatore raccoglie un telefono da terra e lo lancia", () => {
  let lanciato = false;
  for (let prova = 0; prova < 8 && !lanciato; prova++) {
    const amb = ambiente();
    amb.avanza(10);
    const r = amb.lottatore("robot");
    const i = amb.finestra.__ring.lanciaTelefono(r.bacino.x + 40, amb.pavimento - 12, 0, 0);
    amb.avanza(1500, (s) => {
      if (s.lottatori.some((f) => f.tel)) { lanciato = true; return false; }
    });
    dentro(amb);
  }
  assert.ok(lanciato, "nessuno ha mai raccolto un telefono da terra");
});

test("la partenza è sul bordo alto della barra di ricerca", () => {
  const amb = ambiente({ campo: [100, 320, 1000, 380], solidi: [[100, 320, 1000, 380]] });
  const s = amb.stato();
  assert.ok(s.campoRicerca);
  for (const f of s.lottatori) {
    assert.ok(Math.abs(f.bacino.y - 320) < 70, f.tipo + " non parte dalla barra: " + f.bacino.y);
    assert.ok(f.bacino.x > 300 && f.bacino.x < 800);
  }
  amb.avanza(60);
  for (const f of amb.stato().lottatori) assert.ok(f.base < 400, "è già caduto giù dalla barra");
});

test("chi si schianta sulle notizie le danneggia, e poi si riparano", () => {
  const amb = ambiente();
  amb.avanza(30);
  amb.porta("robot", 600, 120, 10);
  amb.rilascia(600, 120);
  let danneggiata = false;
  amb.avanza(240, (s) => { if (s.danniStriscia > 0) { danneggiata = true; return false; } });
  assert.ok(danneggiata, "una caduta dall'alto non ha lasciato segni sulla striscia");
  amb.avanza(120); dentro(amb);
  // Con le crepe disegnate niente deve esplodere; i danni non superano il
  // massimo e, col tempo, si riparano (almeno una volta la striscia è intatta).
  let intatta = false;
  for (let blocco = 0; blocco < 300; blocco++) {
    amb.avanza(60); dentro(amb);
    const n = amb.stato().danniStriscia;
    assert.ok(n <= 5, "troppi danni insieme: " + n);
    if (n === 0) intatta = true;
  }
  assert.ok(intatta, "i danni non si riparano mai");
});

test("il canvas ha la dimensione esatta dell'area visibile, non 100vh (iPhone)", () => {
  const amb = ambiente({ larghezza: 390, altezza: 664 });
  assert.strictEqual(amb.tela.style.width, "390px");
  assert.strictEqual(amb.tela.style.height, "664px");
});

test("col dito si prende anche un po' più lontano che col mouse", () => {
  const amb = ambiente();
  amb.avanza(30);
  const f = amb.lottatore("robot");
  const lontano = { x: f.bacino.x + 24, y: f.bacino.y - 8 };
  const mouse = amb.premi(lontano.x, lontano.y);
  amb.rilascia(lontano.x, lontano.y);
  const e = Object.assign({ clientX: lontano.x, clientY: lontano.y, button: 0, pointerType: "touch",
    preventDefault() { this.bloccato = true; }, stopPropagation() {} });
  for (const fn of amb.ascoltatori.pointerdown || []) fn(e);
  assert.ok(e.bloccato, "il dito non ha preso il lottatore");
  amb.rilascia(lontano.x, lontano.y);
});

test("col jetpack si decolla e si resta in quota, dentro la finestra", () => {
  // Un colpo dell'avversario può spegnere il jetpack: si riprova.
  let riuscito = false, ultimo = "";
  for (let prova = 0; prova < 4 && !riuscito; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    const prima = amb.lottatore("robot").bacino.y;
    amb.finestra.__ring.decolla("robot", false);
    amb.avanza(150);
    const f = amb.lottatore("robot");
    dentro(amb);
    if (f.vola && f.bacino.y < prima - 40 && f.testa.y < f.bacino.y) riuscito = true;
    else ultimo = prima + " → " + f.bacino.y + (f.vola ? "" : " (non in volo)");
  }
  assert.ok(riuscito, "il robot non si è alzato in volo: " + ultimo);
});

test("col jetpack impazzito si sbatte in giro ma non si esce dalla finestra né si esplode", () => {
  const amb = ambiente({ solidi: [[300, 500, 700, 530], [800, 300, 1000, 330]] });
  amb.avanza(20);
  amb.finestra.__ring.decolla("robot", true);
  amb.finestra.__ring.decolla("mela", true);
  let visto = false;
  for (let blocco = 0; blocco < 30; blocco++) {
    amb.avanza(60); dentro(amb);
    if (amb.stato().lottatori.some((f) => f.caos)) visto = true;
  }
  assert.ok(visto, "il jetpack non è mai impazzito");
});

test("finito il carburante si torna giù e si continua a lottare", () => {
  const amb = ambiente();
  amb.avanza(20);
  amb.finestra.__ring.decolla("mela", false);
  let atterrata = false;
  amb.avanza(60 * 25, (s) => { if (!s.lottatori.find((f) => f.tipo === "mela").vola) { atterrata = true; return false; } });
  dentro(amb);
  assert.ok(atterrata, "il jetpack non finisce mai");
});

test("lottando prima o poi qualcuno si alza in volo da solo", () => {
  let volato = false;
  for (let prova = 0; prova < 6 && !volato; prova++) {
    const amb = ambiente();
    // Il primo minuto è calmo: il jetpack si accende solo dopo.
    amb.avanza(60 * 120, (s) => { if (s.lottatori.some((f) => f.vola)) { volato = true; return false; } });
    dentro(amb);
  }
  assert.ok(volato, "in dodici minuti nessuno ha mai acceso il jetpack");
});

test("imparano: i colpi a segno alzano il peso della mossa e l'esperienza, e si ricorda", () => {
  const memoria = {};
  const amb = ambiente({ memoria });
  const r = amb.finestra.__ring;
  assert.strictEqual(r.livello("robot"), 0);
  for (let i = 0; i < 40; i++) r.impara("robot", "montante", 1, 1);
  const c = r.cervello();
  assert.ok(c.robot.pesi.montante > 1.5, "il montante non è diventato la mossa preferita");
  assert.ok(c.robot.pesi.montante <= 2.6, "il peso non ha un tetto");
  assert.ok(c.robot.pesi.pugno < 1.01 && c.robot.pesi.pugno > 0.9, "le altre mosse devono restare vicine a 1");
  assert.ok(r.livello("robot") >= 2, "l'esperienza non alza il livello");
  assert.ok(JSON.parse(memoria["mut-ring-cervello"]).robot.exp >= 30, "il cervello non viene salvato");
  // alla visita dopo si riparte da quello che hanno imparato
  const dopo = ambiente({ memoria });
  assert.strictEqual(dopo.finestra.__ring.livello("robot"), r.livello("robot"));
  assert.ok(dopo.finestra.__ring.cervello().robot.pesi.montante > 1.5);
  // la mela non ne sa niente: ognuno impara per conto suo
  assert.strictEqual(dopo.finestra.__ring.livello("mela"), 0);
});

test("chi sbaglia mossa la usa meno, ma mai fino a zero", () => {
  const amb = ambiente();
  const r = amb.finestra.__ring;
  for (let i = 0; i < 200; i++) r.impara("mela", "calcio", -1, 0);
  const w = r.cervello().mela.pesi.calcio;
  assert.ok(w < 0.6 && w >= 0.4, "peso fuori dai limiti: " + w);
});

test("un cervello salvato male (dati sporchi) non rompe niente", () => {
  const sporco = JSON.stringify({ robot: { exp: "boh", pesi: { pugno: 1e9, calcio: "x", para: -4 } }, mela: 7 });
  const amb = ambiente({ memoria: { "mut-ring-cervello": sporco } });
  const c = amb.finestra.__ring.cervello();
  assert.strictEqual(c.robot.exp, 0);
  assert.strictEqual(c.robot.pesi.pugno, 2.6);
  assert.strictEqual(c.robot.pesi.calcio, 1);
  assert.strictEqual(c.robot.pesi.para, 0.4);
  const rotto = ambiente({ memoria: { "mut-ring-cervello": "{non json" } });
  assert.strictEqual(rotto.finestra.__ring.livello("robot"), 0);
  dentro(rotto);
});

test("lottando davvero l'esperienza cresce e viene salvata", () => {
  const memoria = {};
  const amb = ambiente({ memoria });
  amb.avanza(60 * 90);
  dentro(amb);
  const c = amb.finestra.__ring.cervello();
  assert.ok(c.robot.exp + c.mela.exp > 0, "in un minuto e mezzo nessun colpo ha insegnato nulla");
  assert.ok(memoria["mut-ring-cervello"], "niente salvato");
  const pesi = Object.values(c.robot.pesi).concat(Object.values(c.mela.pesi));
  assert.ok(pesi.every((w) => w >= 0.4 && w <= 2.6));
});

test("il primo minuto è tranquillo: niente jetpack, niente eventi, al massimo due oggetti, nessuna arma", () => {
  for (let prova = 0; prova < 3; prova++) {
    const amb = ambiente();
    amb.avanza(60 * 58, (s) => {
      assert.ok(!s.lottatori.some((f) => f.vola), "jetpack acceso nel primo minuto");
      assert.strictEqual(s.evento, null, "evento nel primo minuto");
      assert.ok(s.telefoni.length <= 2, "troppi oggetti nel primo minuto: " + s.telefoni.length);
      for (const t of s.telefoni) assert.ok(["classico", "grande", "pieghevole", "orologio"].includes(t.tipo), "oggetto grosso nel primo minuto: " + t.tipo);
    });
    dentro(amb);
  }
});

test("dopo 70 secondi arrivano le armi; si impugnano, si usano e restano dentro la finestra", () => {
  const amb = ambiente();
  amb.avanza(10);
  amb.finestra.__ring.tempo(70);
  let viste = false, impugnata = false, sparato = false;
  for (let blocco = 0; blocco < 120 && !(impugnata && sparato); blocco++) {
    amb.avanza(60, (s) => {
      if (s.telefoni.some((t) => t.tipo === "pistola" || t.tipo === "spada")) viste = true;
      if (s.lottatori.some((f) => f.arma)) impugnata = true;
      if (s.proiettili > 0) sparato = true;
    });
    dentro(amb);
    if (blocco === 20 && !impugnata) amb.finestra.__ring.dai("robot", "pistola");
  }
  assert.ok(viste, "in due minuti dopo i 70 secondi non è caduta nessuna arma");
  assert.ok(impugnata, "nessuno ha mai impugnato un'arma");
  assert.ok(sparato, "con la pistola in mano non si è mai sparato");
});

test("la spada colpisce da più lontano di un pugno", () => {
  let colpito = false;
  for (let prova = 0; prova < 5 && !colpito; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    amb.finestra.__ring.dai("robot", "spada");
    amb.avanza(60 * 20, (s) => { if (s.lottatori.find((f) => f.tipo === "mela").danni > 0 || s.punteggio.robot > 0) { colpito = true; return false; } });
    dentro(amb);
  }
  assert.ok(colpito, "con la spada il robot non ha mai colpito la mela");
});

test("si lanciano anche tablet, portatili e smartwatch, e fanno male", () => {
  for (const forma of ["tablet", "pc", "orologio"]) {
    const amb = ambiente();
    amb.avanza(30);
    const m = amb.lottatore("mela");
    const i = amb.finestra.__ring.lanciaTelefono(m.testa.x - 60, m.testa.y - 2, 8, 0, forma);
    assert.strictEqual(amb.stato().telefoni[i].tipo, forma);
    let colpito = false;
    amb.avanza(30, (s) => { if (s.lottatori.find((f) => f.tipo === "mela").danni > 0 || s.punteggio.robot + s.punteggio.mela > 0) { colpito = true; return false; } });
    assert.ok(colpito, forma + " è passato attraverso la mela");
    amb.avanza(120); dentro(amb);
  }
});

test("chi manda K.O. l'altro fa un balletto", () => {
  let ballato = false;
  for (let prova = 0; prova < 4 && !ballato; prova++) {
    const amb = ambiente();
    for (let blocco = 0; blocco < 240 && !ballato; blocco++) {
      amb.avanza(60, (s) => { if (s.lottatori.some((f) => f.ballo)) { ballato = true; return false; } });
    }
    dentro(amb);
  }
  assert.ok(ballato, "nessun balletto dopo un K.O.");
});

test("si afferra l'avversario, lo si tiene e lo si scaglia via", () => {
  for (const mossa of ["sopra", "rotea", "suplex"]) {
    const amb = ambiente();
    amb.avanza(30);
    assert.ok(amb.finestra.__ring.afferra("robot", mossa));
    assert.ok(amb.lottatore("mela").tenuto, "la mela non risulta presa");
    amb.avanza(10);
    assert.ok(amb.lottatore("robot").tiene, "il robot ha mollato subito");
    let lanciata = false;
    amb.avanza(80, (s) => { if (!s.lottatori.find((f) => f.tipo === "mela").tenuto) { lanciata = true; return false; } });
    assert.ok(lanciata, "con la mossa " + mossa + " la mela non viene mai lasciata");
    assert.ok(!amb.lottatore("robot").tiene);
    amb.avanza(240); dentro(amb);
  }
});

test("lottando, prima o poi uno afferra l'altro da solo", () => {
  let preso = false;
  for (let prova = 0; prova < 4 && !preso; prova++) {
    const amb = ambiente();
    amb.finestra.__ring.tempo(60);
    amb.avanza(60 * 120, (s) => { if (s.lottatori.some((f) => f.tenuto)) { preso = true; return false; } });
    dentro(amb);
  }
  assert.ok(preso, "nessuna presa in otto minuti di lotta");
});

test("chi scende apposta da una piattaforma alta apre il paracadute; chi viene lanciato no", () => {
  const amb = ambiente({ solidi: [[400, 300, 800, 330]], campo: [400, 300, 800, 330] });
  amb.avanza(30);
  let aperto = false;
  // il robot cammina giù dal bordo per andare dalla mela, messa in basso
  amb.porta("mela", 1000, amb.pavimento - 60, 10); amb.rilascia(1000, amb.pavimento - 60);
  amb.avanza(60 * 30, (s) => { if (s.lottatori.some((f) => f.paracadute)) { aperto = true; return false; } });
  assert.ok(aperto, "scendendo dalla piattaforma nessuno ha aperto il paracadute");
  amb.avanza(60 * 6); dentro(amb);
  // lanciato dal puntatore: niente paracadute
  const lanciato = ambiente();
  lanciato.avanza(30);
  lanciato.porta("robot", 600, 100, 10); lanciato.rilascia(600, 100);
  lanciato.avanza(200, (s) => { assert.ok(!s.lottatori.find((f) => f.tipo === "robot").paracadute, "paracadute aperto da lanciato"); });
});

test("il pieghevole della mela fa esplodere il robot, che si rimonta pezzo per pezzo", () => {
  const amb = ambiente();
  amb.avanza(30);
  amb.finestra.__ring.esplodi();
  let s = amb.stato();
  assert.ok(s.lottatori.find((f) => f.tipo === "robot").esploso, "il robot non risulta esploso");
  assert.ok(s.pezzi >= 15, "troppi pochi pezzi: " + s.pezzi);
  assert.strictEqual(s.punteggio.mela, 1, "l'esplosione non conta come K.O.");
  let rimontato = false;
  amb.avanza(60 * 12, (st) => {
    for (const f of st.lottatori) assert.ok(Number.isFinite(f.testa.x) && Number.isFinite(f.bacino.y));
    if (!st.lottatori.find((f) => f.tipo === "robot").esploso) { rimontato = true; return false; }
  });
  assert.ok(rimontato, "il robot non si è mai rimontato");
  assert.strictEqual(amb.stato().pezzi, 0);
  amb.avanza(300); dentro(amb);
});

test("la mela tira fuori il pieghevole dal jetpack e lo lancia", () => {
  let esploso = false;
  for (let prova = 0; prova < 6 && !esploso; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    amb.finestra.__ring.tempo(61);
    amb.finestra.__ring.duo();
    amb.avanza(60 * 4, (s) => { if (s.lottatori.find((f) => f.tipo === "robot").esploso) { esploso = true; return false; } });
    dentro(amb);
  }
  assert.ok(esploso, "il pieghevole non ha mai fatto esplodere il robot");
});

test("scommesse: si punta, si vince al K.O. giusto, si perde a quello sbagliato, e i gettoni restano", () => {
  const memoria = {};
  const amb = ambiente({ memoria });
  amb.avanza(30);
  const r = amb.finestra.__ring;
  assert.strictEqual(amb.stato().gettoni, 100);
  assert.ok(r.comandi.scommetti("robot", 25));
  assert.ok(!r.comandi.scommetti("mela", 10), "si può puntare due volte insieme");
  assert.strictEqual(amb.stato().gettoni, 75);
  const quota = amb.stato().scommessa.quota;
  r.ko("mela");                               // vince il robot
  assert.strictEqual(amb.stato().gettoni, 75 + Math.round(25 * quota));
  assert.strictEqual(amb.stato().scommessa, null);
  const dopo = amb.stato().gettoni;
  assert.ok(r.comandi.scommetti("robot", 10));
  r.ko("robot");                              // vince la mela
  assert.strictEqual(amb.stato().gettoni, dopo - 10);
  assert.ok(!r.comandi.scommetti("mela", 1e6), "si può puntare più di quel che si ha");
  assert.strictEqual(memoria["mut-ring-gettoni"], String(dopo - 10));
  assert.strictEqual(ambiente({ memoria }).stato().gettoni, dopo - 10, "i gettoni non restano nel browser");
});

test("un'esplosione vera: fuoco, fumo, detriti e braci, e chi è vicino viene sbalzato", () => {
  const amb = ambiente();
  amb.avanza(30);
  const m = amb.lottatore("mela");
  amb.finestra.__ring.scoppia(m.bacino.x - 30, m.bacino.y);
  amb.avanza(2);
  const tipi = amb.stato().particelleTipi;
  for (const t of ["fuoco", "fumo", "detrito", "brace"]) assert.ok(tipi[t] > 0, "manca " + t);
  amb.avanza(10);
  assert.ok(Math.abs(amb.lottatore("mela").bacino.x - m.bacino.x) > 15, "la mela non è stata sbalzata");
  amb.avanza(60 * 4); dentro(amb);
});

test("una bomba messa in campo prima o poi scoppia", () => {
  const amb = ambiente();
  amb.avanza(30);
  amb.finestra.__ring.comandi.metti("bomba");
  assert.ok(amb.stato().telefoni.some((t) => t.tipo === "bomba"));
  let scoppiata = false;
  amb.avanza(60 * 12, (s) => { if ((s.particelleTipi.fuoco || 0) > 0) { scoppiata = true; return false; } });
  assert.ok(scoppiata, "la bomba non è mai scoppiata");
  amb.avanza(60 * 3); dentro(amb);
});

test("un arto staccato vola via e poi torna al suo posto; con gli effetti spenti non si stacca niente", () => {
  const amb = ambiente();
  amb.avanza(30);
  amb.finestra.__ring.smembra("robot");
  assert.strictEqual(amb.lottatore("robot").staccati.length, 1);
  assert.strictEqual(amb.stato().arti, 1);
  let tornato = false;
  amb.avanza(60 * 10, (s) => { if (s.arti === 0 && s.lottatori.find((f) => f.tipo === "robot").staccati.length === 0) { tornato = true; return false; } });
  assert.ok(tornato, "l'arto non è mai tornato");
  amb.finestra.__ring.comandi.cruento(false);
  amb.finestra.__ring.smembra("mela");
  assert.strictEqual(amb.lottatore("mela").staccati.length, 0);
  assert.strictEqual(amb.memoria["mut-ring-cruento"], "off");
  dentro(amb);
});

test("i colpi lasciano segni sul corpo", () => {
  let segnato = false;
  for (let prova = 0; prova < 3 && !segnato; prova++) {
    const amb = ambiente();
    amb.avanza(60 * 60, (s) => { if (s.lottatori.some((f) => f.segni > 0)) { segnato = true; return false; } });
  }
  assert.ok(segnato, "in un minuto di lotta nessun segno");
});

test("imprevisti a mano: pioggia, palle di neve col tema natalizio, uragano, gravità; tutto resta stabile", () => {
  const amb = ambiente({ solidi: [[300, 600, 700, 630]] });
  amb.avanza(30);
  const c = amb.finestra.__ring.comandi;
  c.gravita(0.12); assert.strictEqual(amb.stato().moltG, 0.12);
  c.gravita(1);
  c.imprevisto("acquazzone", true);
  amb.avanza(60 * 20); dentro(amb);
  assert.ok(amb.stato().particelleTipi.pioggia > 0, "non piove");
  c.imprevisto("acquazzone", false);
  // Il tema natalizio lo accende il sito (natale.js) con un evento: ai
  // lottatori dà cappellini e palle di neve; la neve non è più del ring.
  for (const fn of amb.ascoltatori["mut:natale"] || []) fn({ detail: { acceso: true } });
  assert.strictEqual(amb.stato().natale, true, "l'evento del tema natalizio non arriva al ring");
  let palla = false;
  amb.avanza(60 * 60, (s) => { if (s.lottatori.some((f) => f.azione === "palla")) palla = true; });
  dentro(amb);
  assert.ok(!(amb.stato().particelleTipi.fiocco > 0), "il ring nevica ancora per conto suo");
  assert.ok(palla, "a Natale nessuno ha tirato palle di neve");
  for (const fn of amb.ascoltatori["mut:natale"] || []) fn({ detail: { acceso: false } });
  assert.strictEqual(amb.stato().natale, false);
  c.imprevisto("uragano", true);
  let alzato = false;
  amb.avanza(60 * 40, (s) => { if (s.lottatori.some((f) => f.bacino.y < s.pavimento - 120)) alzato = true; dentro(amb); });
  assert.ok(alzato, "l'uragano non ha sollevato nessuno");
  c.imprevisto("uragano", false);
  assert.strictEqual(amb.stato().uragano, false);
  c.imprevisto("rallenta", true); assert.strictEqual(amb.stato().ritmo, 0.45);
  c.imprevisto("rallenta", false); assert.strictEqual(amb.stato().ritmo, 1);
});

test("i comandi della tendina riaccendono le lotte se erano spente", () => {
  const amb = ambiente({ memoria: { "mut-ring": "off" } });
  assert.strictEqual(amb.stato().lottatori.length, 0);
  amb.finestra.__ring.comandi.metti("spada");
  assert.strictEqual(amb.stato().lottatori.length, 2);
  assert.ok(amb.stato().telefoni.some((t) => t.tipo === "spada"));
});

test("anche la mela va in pezzi e si rimonta; la vittoria va al robot", () => {
  const amb = ambiente();
  amb.avanza(30);
  amb.finestra.__ring.esplodi("mela");
  const s = amb.stato();
  assert.ok(s.lottatori.find((f) => f.tipo === "mela").esploso);
  assert.ok(s.pezzi >= 15, "troppi pochi pezzi: " + s.pezzi);
  assert.strictEqual(s.punteggio.robot, 1);
  let rimontata = false;
  amb.avanza(60 * 12, (st) => {
    for (const f of st.lottatori) assert.ok(Number.isFinite(f.testa.x) && Number.isFinite(f.bacino.y));
    if (!st.lottatori.find((f) => f.tipo === "mela").esploso) { rimontata = true; return false; }
  });
  assert.ok(rimontata, "la mela non si è mai rimontata");
  assert.strictEqual(amb.stato().pezzi, 0);
  amb.avanza(300); dentro(amb);
});

test("tutti e due in pezzi insieme: ognuno si rimonta coi suoi", () => {
  const amb = ambiente();
  amb.avanza(30);
  amb.finestra.__ring.esplodi("robot");
  amb.finestra.__ring.esplodi("mela");
  assert.ok(amb.stato().lottatori.every((f) => f.esploso));
  amb.avanza(60 * 12);
  assert.ok(amb.stato().lottatori.every((f) => !f.esploso), "qualcuno è rimasto in pezzi");
  assert.strictEqual(amb.stato().pezzi, 0);
  amb.avanza(120); dentro(amb);
});

test("una bomba che scoppia addosso fa a pezzi chi la prende in pieno, non chi è lontano", () => {
  const amb = ambiente();
  amb.avanza(30);
  const r = amb.lottatore("robot");
  amb.finestra.__ring.scoppia(r.bacino.x, r.bacino.y, true);
  const s = amb.stato();
  assert.ok(s.lottatori.find((f) => f.tipo === "robot").esploso, "preso in pieno, il robot non è andato in pezzi");
  assert.ok(!s.lottatori.find((f) => f.tipo === "mela").esploso, "la mela era lontana");
  amb.avanza(60 * 12); dentro(amb);
  assert.ok(amb.stato().lottatori.every((f) => !f.esploso));
});

test("i bordi e il tetto della pagina si rompono quando ci si sbatte forte, e poi si riparano", () => {
  const amb = ambiente();
  amb.avanza(30);
  amb.porta("robot", 1050, 300, 40);
  // lanciato forte contro il bordo destro, da vicino
  for (const x of [1090, 1130, 1170]) { amb.muovi(x, 300); amb.avanza(1); }
  amb.rilascia(1170, 300);
  let rotto = false;
  amb.avanza(120, (s) => { if (s.danniBordi.includes("destra")) { rotto = true; return false; } });
  assert.ok(rotto, "sbattendo forte sul bordo destro non si è rotto niente");
  amb.finestra.__ring.danneggiaBordo("tetto", 400, 1);
  amb.finestra.__ring.danneggiaBordo("sinistra", 300, 0.5);
  assert.ok(amb.stato().danniBordi.includes("tetto") && amb.stato().danniBordi.includes("sinistra"));
  // Il tetto lo si colpisce di rado: il suo danno deve sparire da solo.
  let riparato = false;
  for (let blocco = 0; blocco < 60 && !riparato; blocco++) { amb.avanza(60); riparato = !amb.stato().danniBordi.includes("tetto"); }
  assert.ok(riparato, "il tetto non si ripara mai");
  dentro(amb);
});

test("gravità sottosopra: si cade verso il tetto e lì si sta in piedi a testa in giù", () => {
  const amb = ambiente({ solidi: [[0, 0, 1200, 64]] });
  amb.avanza(30);
  amb.finestra.__ring.comandi.gravita("su");
  assert.strictEqual(amb.stato().verso, -1);
  amb.avanza(60 * 6);
  const aTestaInGiu = { robot: false, mela: false };
  amb.avanza(60 * 20, (st) => {
    for (const f of st.lottatori) {
      assert.ok(f.bacino.y < 260, f.tipo + " non sta verso il tetto: " + f.bacino.y);
      if (f.testa.y > f.bacino.y + 10) aTestaInGiu[f.tipo] = true;
    }
  });
  assert.ok(aTestaInGiu.robot && aTestaInGiu.mela, "qualcuno non si è mai messo a testa in giù: " + JSON.stringify(aTestaInGiu));
  dentro(amb);
  amb.finestra.__ring.comandi.gravita("1");
  assert.strictEqual(amb.stato().verso, 1);
  amb.avanza(60 * 8);
  for (const f of amb.stato().lottatori) assert.ok(f.bacino.y > 600, f.tipo + " non è tornato giù");
  dentro(amb);
});

test("barre della vita: si accendono dalla tendina, si ricordano, e la vita scende coi colpi", () => {
  const memoria = {};
  const amb = ambiente({ memoria });
  amb.avanza(30);
  amb.finestra.__ring.comandi.barre(true);
  assert.strictEqual(memoria["mut-ring-barre"], "on");
  assert.strictEqual(ambiente({ memoria }).stato().barreVita, true);
  const m = amb.lottatore("mela");
  assert.strictEqual(m.vita, 1);
  amb.finestra.__ring.lanciaTelefono(m.testa.x - 60, m.testa.y - 2, 8, 0, "pc");
  let scesa = false;
  amb.avanza(60, (s) => { if (s.lottatori.find((f) => f.tipo === "mela").vita < 1) { scesa = true; return false; } });
  assert.ok(scesa, "la vita della mela non è scesa");
  amb.finestra.__ring.ko("mela");
  assert.strictEqual(amb.lottatore("mela").vita, 0, "a K.O. la barra non è vuota");
  // (Si guarda quando si rialza: ora che si lotta più fitto, cinque secondi dopo può averne già prese altre.)
  let piena = false;
  amb.avanza(60 * 8, (s) => { const f = s.lottatori.find((l) => l.tipo === "mela"); if (!f.ko && f.vita === 1) { piena = true; return false; } });
  assert.ok(piena, "dopo il K.O. la barra non torna piena");
});

test("super guerrieri: energia, onda energetica che colpisce e rompe il bordo, raffica, teletrasporto, potenziamento", () => {
  const amb = ambiente();
  amb.avanza(30);
  const r = amb.finestra.__ring;
  r.comandi.anime(true);
  assert.strictEqual(amb.stato().anime, true);
  assert.strictEqual(amb.stato().barreVita, true, "le barre non si accendono con la modalità anime");
  let onda = false, colpita = false, bordo = false, teletr = false, potenziato = false, energia = false;
  for (let prova = 0; prova < 6; prova++) {
    r.comandi.colpo("onda");
    amb.avanza(150, (s) => {
      if (s.lottatori.some((f) => f.onda)) onda = true;
      if (s.danniBordi.length) bordo = true;
      if (s.lottatori.some((f) => f.danni > 0) || s.punteggio.robot + s.punteggio.mela > 0) colpita = true;
    });
  }
  const prima = amb.lottatore("robot").bacino.x;
  r.comandi.colpo("teletrasporto");
  for (const f of amb.stato().lottatori) if (Math.abs(f.bacino.x - (f.tipo === "robot" ? prima : -1e9)) > 40) teletr = true;
  for (let prova = 0; prova < 4 && !potenziato; prova++) {
    r.comandi.colpo("carica");
    amb.avanza(60 * 4, (s) => { if (s.lottatori.some((f) => f.potenziato)) { potenziato = true; return false; } });
  }
  amb.avanza(60 * 90, (s) => { if (s.proiettili > 0) { energia = true; return false; } });
  dentro(amb);
  assert.ok(onda, "nessuna onda energetica");
  assert.ok(colpita || bordo, "l'onda non ha colpito niente");
  assert.ok(teletr, "il teletrasporto non ha spostato nessuno");
  assert.ok(potenziato, "caricando l'aura nessuno si è potenziato");
  assert.ok(energia, "in 90 secondi nessuna sfera di energia");
  r.comandi.anime(false);
  assert.strictEqual(amb.memoria["mut-ring-anime"], "off");
  dentro(amb);
});

test("robot e mela sono alti uguali: il frutto va dal bacino alla testa e i colpi lo prendono", () => {
  const amb = ambiente();
  amb.avanza(8);           // appena in piedi, prima che comincino a darsele
  const r = amb.lottatore("robot"), m = amb.lottatore("mela");
  assert.ok(Math.abs((r.bacino.y - r.testa.y) - (m.bacino.y - m.testa.y)) < 6, "altezze diverse");
  assert.ok(Math.abs(r.testa.y - m.testa.y) < 12, "teste a quote diverse: " + r.testa.y + " / " + m.testa.y);
});

test("super guerrieri: niente jetpack, si vola, si scatta con le immagini residue e si torna giù", () => {
  const amb = ambiente();
  amb.avanza(30);
  const r = amb.finestra.__ring;
  r.comandi.anime(true);
  r.scatta("robot");
  let volato = false, alto = false;
  amb.avanza(60 * 6, (s) => {
    const f = s.lottatori.find((l) => l.tipo === "robot");
    if (f.volo) volato = true;
    if (f.bacino.y < s.pavimento - 120) alto = true;
    dentro(amb);
  });
  assert.ok(volato, "il robot non ha preso il volo");
  // In modalità anime in campo ci sono i personaggi inventati, e il loro jetpack si disegna solo fuori dal motore a energia.
  assert.ok(SORGENTE.includes("(stile ? disegnaUmano : f.tipo === \"robot\" ? disegnaRobot : disegnaMela)(f);"), "con uno stile acceso si disegnano ancora robot e mela");
  assert.ok(SORGENTE.includes("if (!anime) zaino(f, 9.5 * S);"), "il jetpack si disegna ancora in modalità anime");
  let atterrati = false;
  r.comandi.anime(false);
  amb.avanza(60 * 6, (s) => { if (s.lottatori.every((f) => !f.volo)) { atterrati = true; return false; } });
  assert.ok(atterrati, "spenta la modalità si resta in volo");
  assert.ok(alto || volato);
});

test("super guerrieri: la raffica di pugni colpisce e il colpo finale scaraventa via", () => {
  let lanciata = false;
  for (let prova = 0; prova < 9 && !lanciata; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.comandi.anime(true);
    // i due a contatto
    const m = amb.lottatore("mela");
    amb.porta("robot", m.bacino.x - 26, m.bacino.y - 8, 20); amb.rilascia(m.bacino.x - 26, m.bacino.y - 8);
    amb.avanza(70);
    r.rush("robot");
    amb.avanza(60, (s) => { const f = s.lottatori.find((l) => l.tipo === "mela"); if (f.ko > 0 || f.danni > 0) { lanciata = true; return false; } });
    dentro(amb);
  }
  assert.ok(lanciata, "la raffica non ha mai colpito");
});

test("super guerrieri in combattimento libero: volano, scattano e restano stabili", () => {
  const amb = ambiente({ solidi: [[300, 500, 700, 530]] });
  amb.avanza(30);
  amb.finestra.__ring.comandi.anime(true);
  let volo = false;
  amb.avanza(60 * 60, (s) => { if (s.lottatori.some((f) => f.volo)) volo = true; dentro(amb); });
  assert.ok(volo, "in un minuto in modalità anime nessuno ha volato");
});

test("la mela si smembra: morsi che si richiudono, taglio in due che si rincolla, picciolo che salta", () => {
  const amb = ambiente();
  amb.avanza(30);
  const r = amb.finestra.__ring;
  r.mordi();
  assert.strictEqual(amb.lottatore("mela").morsi, 1, "nessun morso");
  assert.ok(r.taglia(), "la mela non si taglia");
  assert.ok(amb.lottatore("mela").tagliata);
  let rincollata = false;
  amb.avanza(60 * 8, (s) => { if (!s.lottatori.find((f) => f.tipo === "mela").tagliata) { rincollata = true; return false; } });
  assert.ok(rincollata, "le due metà non si rincollano");
  let picciolo = false;
  for (let i = 0; i < 30 && !picciolo; i++) {
    r.smembra("mela");
    if (amb.lottatore("mela").staccati.includes("P")) picciolo = true;
    amb.avanza(60 * 8);
  }
  assert.ok(picciolo, "il picciolo non salta mai");
  amb.finestra.__ring.comandi.cruento(false);
  r.mordi();
  dentro(amb);
});

test("un omino portato col puntatore colpisce l'altro se ci sbatte contro", () => {
  let colpita = false;
  for (let prova = 0; prova < 4 && !colpita; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    let m = amb.lottatore("mela");
    amb.porta("robot", m.bacino.x - 110, m.bacino.y - 14, 12);
    // lo si sbatte contro la mela, inseguendola
    for (let i = 1; i <= 24 && !colpita; i++) {
      m = amb.lottatore("mela");
      amb.muovi(m.bacino.x + 60, m.bacino.y - 14); amb.avanza(1);
      const s = amb.stato(), f = s.lottatori.find((l) => l.tipo === "mela");
      if (f.danni > 0 || f.ko > 0 || s.punteggio.robot > 0) colpita = true;
    }
    amb.rilascia(m.bacino.x + 60, m.bacino.y - 14);
    amb.avanza(120); dentro(amb);
  }
  assert.ok(colpita, "portato col puntatore, il robot non ha colpito la mela");
});

test("sfera gigante: si carica sopra la testa, parte ed esplode", () => {
  // Un colpo dell'avversario durante la carica la fa svanire: si riprova.
  let carica = false, partita = false, esplosa = false;
  for (let prova = 0; prova < 6 && !esplosa; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    amb.finestra.__ring.comandi.colpo("sfera");
    let vista = false;
    amb.avanza(60 * 12, (s) => {
      if (s.lottatori.some((f) => f.sfera)) carica = true;
      if (s.sfereGrandi > 0) { partita = true; vista = true; }
      if (vista && s.sfereGrandi === 0 && (s.particelleTipi.fuoco || 0) > 0) { esplosa = true; return false; }
    });
    amb.avanza(60 * 6); dentro(amb);
  }
  assert.ok(carica, "la sfera non si carica");
  assert.ok(partita, "la sfera non parte");
  assert.ok(esplosa, "la sfera non esplode");
});

test("autodistruzione: avvinghiato all'altro salta in aria, l'altro resta nel cratere e poi si rialza", () => {
  let cratere = false, pezzi = false, punto = false;
  for (let prova = 0; prova < 4 && !cratere; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.comandi.colpo("autodistruzione");
    let vittima = null;
    amb.avanza(60 * 9, (s) => {
      const esploso = s.lottatori.find((f) => f.esploso);
      if (esploso) { pezzi = true; vittima = s.lottatori.find((f) => !f.esploso); }
      if (vittima && s.lottatori.find((f) => f.tipo === vittima.tipo).cratere) { cratere = true; }
      if (s.punteggio.robot + s.punteggio.mela === 1) punto = true;
    });
    if (cratere) {
      // la vittima si rialza da sola e chi è saltato in aria si rimonta
      let rialzata = false, rimontato = false;
      amb.avanza(60 * 14, (s) => {
        if (!s.lottatori.find((f) => f.tipo === vittima.tipo).ko) rialzata = true;
        if (s.lottatori.every((f) => !f.esploso)) rimontato = true;
        if (rialzata && rimontato) return false;
      });
      assert.ok(rialzata, "la vittima resta nel cratere per sempre");
      assert.ok(rimontato, "chi si è fatto esplodere non si rimonta");
    }
    dentro(amb);
  }
  assert.ok(pezzi, "nessuno è saltato in aria");
  assert.ok(cratere, "la vittima non è finita nel cratere");
  assert.ok(punto, "l'autodistruzione non ha dato un punto solo");
});

test("disco tagliente, lampo accecante e barriera", () => {
  const amb = ambiente();
  amb.avanza(30);
  const r = amb.finestra.__ring;
  let disco = false;
  for (let i = 0; i < 5 && !disco; i++) {
    r.comandi.colpo("disco");
    amb.avanza(120, (s) => { if (s.dischi > 0) { disco = true; return false; } });
  }
  assert.ok(disco, "il disco non parte");
  amb.avanza(60 * 8);
  let accecato = false;
  for (let i = 0; i < 10 && !accecato; i++) {
    r.comandi.colpo("lampo");
    amb.avanza(60 * 4, (s) => { if (s.lottatori.some((f) => f.accecato)) { accecato = true; return false; } });
  }
  assert.ok(accecato, "il lampo non acceca nessuno");
  amb.avanza(60 * 5);
  // la barriera ferma un telefono lanciato addosso
  let retto = false;
  for (let i = 0; i < 10 && !retto; i++) {
    r.comandi.colpo("barriera");
    const f = amb.stato().lottatori.find((l) => l.azione === "barriera");
    if (!f) { amb.avanza(60); continue; }
    const prima = f.danni;
    r.lanciaTelefono(f.testa.x - 70, f.testa.y, 9, 0, "pc");
    amb.avanza(20);
    const dopo = amb.stato().lottatori.find((l) => l.tipo === f.tipo);
    if (dopo.danni === prima && !dopo.ko) retto = true;
    amb.avanza(60 * 3);
  }
  assert.ok(retto, "la barriera non ha fermato il colpo");
  dentro(amb);
});

test("presa a distanza: l'avversario viene sollevato e poi va in pezzi", () => {
  let sollevato = false, pezzi = false;
  for (let prova = 0; prova < 5 && !pezzi; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    amb.finestra.__ring.comandi.colpo("telecinesi");
    let base = null;
    amb.avanza(60 * 4, (s) => {
      const v = s.lottatori.find((f) => f.sollevato);
      if (v) { sollevato = true; if (base === null) base = v.bacino.y; if (v.bacino.y < base - 80) sollevato = true; }
      if (s.lottatori.some((f) => f.esploso)) { pezzi = true; return false; }
      dentro(amb);
    });
    // Nessuno resta sospeso per sempre. (Si conta quanto dura ogni presa: a
    // un istante fisso può essercene in corso una nuova, e il test cadeva una volta su venti.)
    const fila = {};
    amb.avanza(60 * 12, (st) => {
      for (const f of st.lottatori) {
        fila[f.tipo] = f.sollevato ? (fila[f.tipo] || 0) + 1 : 0;
        assert.ok(fila[f.tipo] < 60 * 6, "qualcuno resta sospeso per sempre");
      }
    });
    dentro(amb);
  }
  assert.ok(sollevato, "nessuno viene sollevato");
  assert.ok(pezzi, "chi è sollevato non va mai in pezzi");
});

test("nell'estensione: i pezzi stanno in una radice a parte, il pavimento è il fondo della finestra, la memoria è la sua", () => {
  const memoria = { "mut-ring": "on" };
  const amb = ambiente({ estensione: true, memoria, ridotto: true });
  const s = amb.stato();
  assert.strictEqual(s.lottatori.length, 2, "il ring non parte dalla radice dell'estensione");
  assert.strictEqual(s.pavimento, 800, "senza striscia il pavimento è il fondo della finestra");
  amb.avanza(60 * 20); dentro(amb);
  amb.finestra.__ring.comandi.barre(true);
  assert.strictEqual(memoria["mut-ring-barre"], "on", "le opzioni non finiscono nella memoria dell'estensione");
  // un clic dentro l'ospite (tasti e tendina) non deve prendere un lottatore
  const f = amb.lottatore("robot");
  const e = { clientX: f.bacino.x, clientY: f.bacino.y - 8, button: 0, pointerType: "mouse", target: amb.finestra.__ringRadice.host,
              preventDefault() { this.bloccato = true; }, stopPropagation() {} };
  for (const fn of amb.ascoltatori.pointerdown || []) fn(e);
  assert.ok(!e.bloccato, "un clic sui tasti dell'estensione ha preso un lottatore");
});

test("Premium: senza sblocco armi, super guerrieri e meteo restano chiusi (e si chiede), il resto è libero", () => {
  let attivo = false;
  const chieste = [];
  const premio = { bloccate: { guerrieri: true, armi: true, meteo: true }, attivo: () => attivo, chiedi: (g) => chieste.push(g) };
  const amb = ambiente({ premio, memoria: { "mut-ring-anime": "on" } });
  amb.avanza(30);
  const c = amb.finestra.__ring.comandi;
  assert.strictEqual(amb.stato().anime, false, "la modalità a pagamento salvata si riaccende da sola senza Premium");
  assert.strictEqual(c.metti("spada"), false);
  assert.strictEqual(c.anime(true), false);
  assert.strictEqual(c.colpo("sfera"), false);
  assert.strictEqual(c.colpo("esplodi-robot"), false);
  assert.strictEqual(c.gravita("0.45"), false);
  assert.strictEqual(c.imprevisto("uragano", true), false);
  assert.deepStrictEqual(chieste, ["armi", "guerrieri", "guerrieri", "armi", "meteo", "meteo"]);
  const s = amb.stato();
  assert.ok(!s.telefoni.some((t) => t.tipo === "spada") && !s.anime && s.moltG === 1 && !s.uragano && !s.lottatori.some((f) => f.esploso));
  // quello che è gratis funziona
  c.metti("tablet"); c.barre(true); c.colpo("terremoto");
  assert.ok(amb.stato().telefoni.some((t) => t.tipo === "tablet"));
  assert.strictEqual(amb.stato().barreVita, true);
  // e in tre minuti di lotta non compare da sola nessuna arma né esplosione da jetpack
  amb.finestra.__ring.tempo(70);
  amb.avanza(60 * 180, (st) => {
    for (const t of st.telefoni) assert.ok(!["pistola", "spada", "bomba", "duo"].includes(t.tipo), "arma comparsa senza Premium: " + t.tipo);
  });
  dentro(amb);
  // con Premium attivo si apre tutto
  attivo = true;
  assert.notStrictEqual(c.metti("spada"), false);
  assert.notStrictEqual(c.anime(true), false);
  assert.strictEqual(amb.stato().anime, true);
  assert.notStrictEqual(c.gravita("0.45"), false);
  assert.strictEqual(amb.stato().moltG, 0.45);
});

test("sul sito (senza Premium dichiarato) è tutto libero", () => {
  const amb = ambiente();
  amb.avanza(30);
  const c = amb.finestra.__ring.comandi;
  assert.notStrictEqual(c.metti("spada"), false);
  assert.notStrictEqual(c.anime(true), false);
  assert.ok(amb.stato().telefoni.some((t) => t.tipo === "spada"));
});

// --- I personaggi nuovi (02/10/2026): trasformazione, maghi, duellanti ---

test("super guerrieri: la trasformazione accende la prima forma, poi la seconda, e cambiando personaggi finisce", () => {
  let prima = false, seconda = false;
  for (let prova = 0; prova < 5 && !seconda; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.mossa("robot", "trasforma");
    assert.strictEqual(amb.stato().stile, "", "una mossa di prova non deve cambiare lo stile da sola");
    r.comandi.stile("guerrieri");
    r.mossa("robot", "trasforma");
    amb.avanza(110, (s) => { if (s.lottatori[0].forma === 1 && s.lottatori[0].potenziato) { prima = true; return false; } });
    if (!prima) continue;
    for (let i = 0; i < 4 && !seconda; i++) {
      r.mossa("robot", "trasforma");
      amb.avanza(110, (s) => { if (s.lottatori[0].forma === 2) { seconda = true; return false; } });
    }
    dentro(amb);
    if (seconda) {
      r.comandi.stile("");
      assert.strictEqual(amb.stato().lottatori[0].forma, 0);
      assert.strictEqual(amb.stato().lottatori[0].potenziato, false);
      assert.strictEqual(amb.stato().anime, false);
    }
  }
  assert.ok(prima, "la trasformazione non parte");
  assert.ok(seconda, "la seconda forma non arriva");
});

test("super guerrieri: dalla tendina la trasformazione parte e, lottando, prima o poi ci si trasforma da soli", () => {
  const amb = ambiente();
  amb.avanza(30);
  const r = amb.finestra.__ring;
  r.comandi.colpo("trasforma");
  assert.strictEqual(amb.stato().stile, "guerrieri");
  assert.ok(amb.stato().lottatori.some((f) => f.azione === "trasforma"));
  let daSoli = false;
  for (let prova = 0; prova < 3 && !daSoli; prova++) {
    r.comandi.ricomincia();
    amb.avanza(60 * 240, (s) => { if (s.lottatori.some((f) => f.forma > 0)) { daSoli = true; return false; } });
    dentro(amb);
  }
  assert.ok(daSoli, "in quattro minuti nessuno si è trasformato da solo");
});

test("maghi: lo stile si sceglie e si ricorda; il gelo blocca e poi si scioglie, il rimpicciolimento passa", () => {
  const amb = ambiente();
  amb.avanza(30);
  const r = amb.finestra.__ring;
  r.comandi.stile("maghi");
  assert.strictEqual(amb.stato().stile, "maghi");
  assert.strictEqual(amb.stato().anime, true, "i maghi usano il motore a energia");
  assert.strictEqual(amb.memoria["mut-ring-stile"], "maghi");
  assert.strictEqual(amb.memoria["mut-ring-anime"], "off");
  r.incanta("mela", "gelo");
  assert.strictEqual(amb.lottatore("mela").gelato, true);
  // (Si aspetta finché si scioglie: l'altro mago può congelarla di nuovo.)
  amb.avanza(60 * 5);
  amb.avanza(60 * 30, (st) => (st.lottatori.find((l) => l.tipo === "mela").gelato ? undefined : false));
  assert.strictEqual(amb.lottatore("mela").gelato, false, "il ghiaccio non si scioglie");
  dentro(amb);
  r.incanta("robot", "piccolo");
  amb.avanza(40);
  assert.ok(amb.lottatore("robot").piccolo && amb.lottatore("robot").scala < 0.7, "non rimpicciolisce");
  // (Si aspetta finché torna: l'altro mago può rimpicciolirlo di nuovo, e i colpi fermano l'azione per qualche fotogramma.)
  amb.avanza(60 * 40, (st) => { const f = st.lottatori.find((l) => l.tipo === "robot"); return f.piccolo || f.scala <= 0.95 ? undefined : false; });
  assert.ok(!amb.lottatore("robot").piccolo && amb.lottatore("robot").scala > 0.95, "non torna grande");
  dentro(amb);
  // Un altro ambiente con lo stile salvato riparte da maghi.
  const amb2 = ambiente({ memoria: { "mut-ring-stile": "maghi" } });
  amb2.avanza(10);
  assert.strictEqual(amb2.stato().stile, "maghi");
});

test("maghi: nel ghiaccio non ci si muove, e un colpo lo manda in pezzi", () => {
  // Il ghiaccio si scioglie da solo dopo 190 fotogrammi: se va in pezzi prima, è stato un colpo.
  let colpito = false;
  for (let prova = 0; prova < 8 && !colpito; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.comandi.stile("lame");                     // l'altro ha una lama: prima o poi il colpo arriva
    amb.avanza(60);
    r.incanta("mela", "gelo");
    assert.strictEqual(amb.lottatore("mela").gelato, true);
    let schegge = false;
    amb.avanza(150, (s) => {
      const m = s.lottatori.find((f) => f.tipo === "mela");
      if (m.gelato) assert.strictEqual(m.azione, null, "nel ghiaccio non si agisce");
      if (s.particelleTipi.scheggia) schegge = true;
      if (!m.gelato && schegge) { colpito = true; return false; }
    });
    dentro(amb);
  }
  assert.ok(colpito, "il ghiaccio non è mai andato in pezzi sotto i colpi");
});

test("maghi: dardi, gelo, fulmine e levitazione dalla tendina", () => {
  let dardi = false, gelato = false, fulmine = false, tetto = false, sollevato = false, sceso = false;
  for (let prova = 0; prova < 6 && !(dardi && gelato && fulmine && sollevato && sceso); prova++) {
    const amb = ambiente();
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.comandi.colpo("dardi");
    assert.strictEqual(amb.stato().stile, "maghi", "una mossa da mago non accende i maghi");
    amb.avanza(60, (s) => { if (s.proiettili > 0) { dardi = true; return false; } });
    for (let i = 0; i < 4 && !gelato; i++) {
      r.comandi.colpo("gelo");
      amb.avanza(120, (s) => { if (s.lottatori.some((f) => f.gelato)) { gelato = true; return false; } });
    }
    r.comandi.colpo("fulmine");
    amb.avanza(90, (s) => { if (s.fulmini > 0) fulmine = true; if (s.danniBordi.includes("tetto")) tetto = true; });
    for (let i = 0; i < 4 && !sceso; i++) {
      r.comandi.colpo("levita");
      amb.avanza(160, (s) => {
        if (s.lottatori.some((f) => f.sollevato)) sollevato = true;
        if (sollevato && !s.lottatori.some((f) => f.sollevato)) { sceso = true; return false; }
      });
    }
    amb.avanza(60 * 4); dentro(amb);
  }
  assert.ok(dardi, "nessun dardo");
  assert.ok(gelato, "il gelo non ha preso nessuno");
  assert.ok(fulmine && tetto, "il fulmine non è caduto dal tetto");
  assert.ok(sollevato && sceso, "la levitazione non alza e non lascia cadere");
});

test("maghi in combattimento libero: incantesimi, e tutto resta stabile", () => {
  const amb = ambiente({ solidi: [[300, 560, 700, 590]] });
  amb.avanza(30);
  amb.finestra.__ring.comandi.stile("maghi");
  let incanti = false, colpi = false;
  amb.avanza(60 * 120, (s) => {
    if (s.proiettili > 0 || s.fulmini > 0 || s.lottatori.some((f) => f.gelato || f.piccolo || f.sollevato)) incanti = true;
    if (s.punteggio.robot + s.punteggio.mela > 0) colpi = true;
  });
  dentro(amb);
  assert.ok(incanti, "in due minuti nessun incantesimo");
  assert.ok(colpi, "in due minuti nessun K.O. fra maghi");
});

test("duellanti: hanno la lama, si colpiscono, lo scatto attraversa l'avversario, la lama lanciata torna", () => {
  let lame = false, passato = false, lanciata = false, tornata = false, danno = false;
  for (let prova = 0; prova < 6 && !(passato && tornata && danno); prova++) {
    const amb = ambiente();
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.comandi.stile("lame");
    const s0 = amb.stato();
    assert.strictEqual(s0.stile, "lame");
    assert.strictEqual(s0.anime, false, "i duellanti non usano il motore a energia");
    lame = s0.lottatori.every((f) => f.lama);
    // Lo scatto: chi lo fa finisce dall'altra parte.
    for (let i = 0; i < 4 && !passato; i++) {
      const a = amb.lottatore("robot").bacino.x < amb.lottatore("mela").bacino.x;
      r.mossa("robot", "scattoLama");
      amb.avanza(16);
      const b = amb.lottatore("robot").bacino.x < amb.lottatore("mela").bacino.x;
      if (a !== b) passato = true;
      amb.avanza(60, (s) => { if (s.lottatori.some((f) => f.danni > 0) || s.punteggio.robot + s.punteggio.mela > 0) danno = true; });
    }
    r.comandi.colpo("lancio-lama");
    amb.avanza(300, (s) => {
      if (s.lottatori.some((f) => f.lamaLanciata)) lanciata = true;
      if (lanciata && !s.lottatori.some((f) => f.lamaLanciata)) { tornata = true; return false; }
    });
    amb.avanza(60 * 20, (s) => { if (s.lottatori.some((f) => f.danni > 0) || s.punteggio.robot + s.punteggio.mela > 0) danno = true; });
    dentro(amb);
    r.comandi.stile("");
    assert.ok(amb.stato().lottatori.every((f) => !f.lama), "tolto lo stile la lama resta");
  }
  assert.ok(lame, "non hanno la lama");
  assert.ok(passato, "lo scatto non attraversa l'avversario");
  assert.ok(lanciata && tornata, "la lama lanciata non parte o non torna");
  assert.ok(danno, "con le lame nessuno si fa male");
});

test("duellanti: le lame si incrociano; con gli effetti spenti non si stacca niente, accesi sì", () => {
  let pressa = false;
  for (let prova = 0; prova < 5 && !pressa; prova++) {
    const amb = ambiente();
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.comandi.colpo("duello");
    assert.strictEqual(amb.stato().stile, "lame");
    amb.avanza(60 * 12, (s) => { if (s.lottatori.every((f) => f.azione === "pressa")) { pressa = true; return false; } });
    amb.avanza(120); dentro(amb);
  }
  assert.ok(pressa, "le lame non si incrociano");
  const spento = ambiente({ memoria: { "mut-ring-cruento": "off" } });
  spento.avanza(30);
  spento.finestra.__ring.comandi.stile("lame");
  spento.avanza(60 * 60, (s) => {
    assert.strictEqual(s.arti, 0, "un arto staccato con gli effetti spenti");
    assert.ok(!s.lottatori.some((f) => f.tagliata), "mela tagliata con gli effetti spenti");
  });
  dentro(spento);
  let tagli = false;
  for (let prova = 0; prova < 4 && !tagli; prova++) {
    const acceso = ambiente();
    acceso.avanza(30);
    acceso.finestra.__ring.comandi.stile("lame");
    acceso.avanza(60 * 90, (s) => { if (s.arti > 0 || s.lottatori.some((f) => f.tagliata || f.staccati.length)) { tagli = true; return false; } });
    dentro(acceso);
  }
  assert.ok(tagli, "in un minuto e mezzo di lame nessun taglio");
});

test("Premium: maghi, duellanti e le loro mosse sono chiusi come i super guerrieri", () => {
  let attivo = false;
  const chieste = [];
  const premio = { bloccate: { guerrieri: true, armi: true, meteo: true }, attivo: () => attivo, chiedi: (g) => chieste.push(g) };
  const amb = ambiente({ premio, memoria: { "mut-ring-stile": "maghi" } });
  amb.avanza(30);
  const c = amb.finestra.__ring.comandi;
  assert.strictEqual(amb.stato().stile, "", "lo stile a pagamento salvato si riaccende da solo senza Premium");
  assert.strictEqual(c.stile("maghi"), false);
  assert.strictEqual(c.stile("lame"), false);
  for (const mossa of ["trasforma", "gelo", "fulmine", "levita", "scatto-lama", "duello"]) assert.strictEqual(c.colpo(mossa), false, mossa);
  assert.ok(chieste.length === 8 && chieste.every((g) => g === "guerrieri"));
  assert.strictEqual(amb.stato().stile, "");
  attivo = true;
  assert.notStrictEqual(c.stile("lame"), false);
  assert.strictEqual(amb.stato().stile, "lame");
});

// --- 02/10/2026: gambe, piattaforme, gran finale, fumogeni e barattoli ----
function incrociano(a, b, c, d) {                 // i segmenti ab e cd si tagliano?
  const o = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return o(a, b, c) !== o(a, b, d) && o(c, d, a) !== o(c, d, b) && o(a, b, c) !== 0 && o(c, d, a) !== 0;
}

test("in piedi su una pagina piena: le gambe non restano incrociate, le ginocchia non si piegano all'indietro, nessuno resta piegato", () => {
  // Una pagina vera: righe di testo, tasti e immagini all'altezza del corpo e della testa.
  const solidi = [[60, 700, 420, 730], [460, 690, 700, 760], [720, 640, 1100, 700], [100, 600, 380, 640], [500, 560, 900, 600], [900, 730, 1180, 770]];
  for (const stile of ["", "guerrieri", "lame"]) {
    const amb = ambiente({ estensione: true, altezza: 800, solidi, memoria: { "mut-ring": "on", "mut-ring-cruento": "off" } });
    amb.avanza(20);
    if (stile) amb.finestra.__ring.comandi.stile(stile);
    let fot = 0, incrociate = 0, ginocchia = 0, piegato = 0, fila = {}, filaMax = 0;
    amb.avanza(60 * 45, (s) => {
      for (const f of s.lottatori) {
        // «In piedi»: non a terra, non in mano a qualcuno, non in volo, non stordito.
        if (f.esploso || f.ko > 0 || f.preso || f.tenuto || f.vola || f.scalando || f.stordito > 0 || f.rialzo > 0 || f.inVolo || f.gelato || f.fuori || f.azione === "balla") { fila[f.tipo] = 0; continue; }
        fot++;
        const p = f.punti, gv = f.ginocchiaViste;
        if (Math.hypot(p.piedeA[0] - p.piedeD[0], p.piedeA[1] - p.piedeD[1]) > 5 * s.scala &&
            (incrociano(gv[0], p.piedeA, gv[1], p.piedeD) || incrociano(p.bacino, gv[0], gv[1], p.piedeD) || incrociano(gv[0], p.piedeA, p.bacino, gv[1]))) incrociate++;
        if ([[gv[0], p.piedeA], [gv[1], p.piedeD]].some(([g, pd]) => (g[0] - (p.bacino[0] + pd[0]) / 2) * f.dir < -3 * s.scala)) ginocchia++;
        const storto = Math.abs(Math.atan2(p.collo[0] - p.bacino[0], p.bacino[1] - p.collo[1])) > 0.7 || p.testa[1] > p.collo[1] + 2 * s.scala;
        if (storto) { piegato++; fila[f.tipo] = (fila[f.tipo] || 0) + 1; filaMax = Math.max(filaMax, fila[f.tipo]); } else fila[f.tipo] = 0;
      }
    });
    dentro(amb);
    assert.ok(fot > 600, "quasi mai in piedi (" + fot + ") con lo stile «" + stile + "»");
    // prima della correzione: gambe incrociate 16–55%, ginocchia al contrario 24–61%, piegati fino a 24 secondi di fila
    // (i numeri su 46 pagine vere li dà `node tests/misura-posture.cjs`)
    assert.ok(incrociate / fot < 0.08, "gambe incrociate per il " + Math.round(100 * incrociate / fot) + "% del tempo («" + stile + "»)");
    assert.ok(ginocchia / fot < 0.04, "ginocchia all'indietro per il " + Math.round(100 * ginocchia / fot) + "% del tempo («" + stile + "»)");
    assert.ok(piegato / fot < 0.12, "piegati per il " + Math.round(100 * piegato / fot) + "% del tempo («" + stile + "»)");
    assert.ok(filaMax < 300, "qualcuno resta piegato per " + filaMax + " fotogrammi di fila («" + stile + "»)");
  }
});

test("chi è in piedi passa davanti agli elementi della pagina e ci si posa solo da sopra", () => {
  // Un muro davanti a ciascuno, all'altezza del busto: camminando non ci si ferma né ci si arrampica.
  const amb = ambiente({ solidi: [[560, 640, 640, 756]] });
  amb.avanza(30);
  let scalate = 0;
  amb.avanza(60 * 25, (s) => { if (s.lottatori.some((f) => f.scalando)) scalate++; });
  assert.strictEqual(scalate, 0, "ci si arrampica su un elemento qualunque incontrato camminando");
  dentro(amb);
  // Da sopra invece regge: lasciato cadere sul muro, ci si posa.
  const amb2 = ambiente({ solidi: [[520, 640, 680, 756]] });
  amb2.avanza(30);
  amb2.porta("robot", 600, 520);
  amb2.rilascia(600, 520);
  let sopra = 0;
  amb2.avanza(60 * 2, (s) => { const f = s.lottatori.find((l) => l.tipo === "robot"); if (f.sopraUnElemento && Math.abs(f.base - 640) < 2) sopra++; });
  assert.ok(sopra > 5, "lasciato sopra un elemento, ci è passato attraverso");
});

test("a dieci K.O. la partita finisce: lo sconfitto vola fuori dal ring, il conto riparte da zero e lui rientra", () => {
  for (const stile of ["", "guerrieri"]) {
    const amb = ambiente({ memoria: stile ? { "mut-ring-stile": stile, "mut-ring-anime": "on" } : {} });
    amb.avanza(60);
    const r = amb.finestra.__ring;
    r.punti(9, 4);
    r.ko("mela");
    let s = amb.stato();
    assert.ok(s.finale && s.finale.tipo === "robot" && s.finale.lancio, "il decimo K.O. non apre il finale");
    assert.strictEqual(s.punteggio.robot, 10);
    let volo = 0, uscito = false, sparito = false, rientrato = false;
    amb.avanza(60 * 9, (st) => {
      dentro(amb);
      const m = st.lottatori.find((f) => f.tipo === "mela");
      if (m.fuori) volo++;
      if (st.finale && st.finale.uscito) uscito = true;
      if (uscito && m.esploso) sparito = true;
      if (sparito && !m.esploso) rientrato = true;
    });
    assert.ok(volo > 3 && volo < 90, "il volo fuori dal ring dura " + volo + " fotogrammi");
    assert.ok(uscito && sparito && rientrato, "uscita " + uscito + ", sparito " + sparito + ", rientrato " + rientrato);
    s = amb.stato();
    assert.strictEqual(s.finale, null, "il finale non si chiude");
    assert.ok(s.punteggio.robot + s.punteggio.mela <= 2 && s.punteggio.robot < 10, "il conto non riparte da zero: " + JSON.stringify(s.punteggio));
    amb.avanza(60 * 20); dentro(amb);
    assert.ok(amb.stato().lottatori.every((f) => !f.fuori), "qualcuno resta fuori dal ring");
  }
  // Sotto i dieci non succede niente di speciale.
  const amb = ambiente();
  amb.avanza(60);
  amb.finestra.__ring.punti(3, 4);
  amb.finestra.__ring.ko("mela");
  assert.strictEqual(amb.stato().finale, null);
});

test("il barattolo lanciato libera una creatura che combatte per chi l'ha lanciato e poi se ne va; il fumogeno acceca chi sta nella nube", () => {
  const amb = ambiente();
  amb.avanza(60);
  const r = amb.finestra.__ring;
  // Messi in campo dalla tendina cadono dal cielo e restano interi: si aprono solo se lanciati.
  r.comandi.metti("barattolo-fuoco"); r.comandi.metti("fumogeno");
  amb.avanza(75);                              // il tempo di toccare terra, non quello di raccoglierli e lanciarli
  let s = amb.stato();
  assert.strictEqual(s.telefoni.map((t) => t.tipo).sort().join(","), "barattolo,fumogeno");
  assert.strictEqual(s.creature.length + s.nubi, 0, "un oggetto caduto dal cielo si è aperto da solo");
  // Lanciati: il barattolo si rompe e nasce la creatura del suo elemento, il fumogeno apre la nube.
  const amb1 = ambiente();
  amb1.avanza(60);
  amb1.finestra.__ring.lanciaTelefono(120, 600, 0, 9, "barattolo-acqua");
  amb1.finestra.__ring.lanciaTelefono(1080, 600, 0, 9, "fumogeno");
  amb1.avanza(40);
  s = amb1.stato();
  assert.strictEqual(s.creature.map((c) => c.el).join(","), "acqua", "il barattolo lanciato non libera la sua creatura");
  assert.strictEqual(s.nubi, 1, "il fumogeno lanciato non apre la nube");
  assert.ok(!s.telefoni.some((t) => t.tipo === "barattolo" || t.tipo === "fumogeno"), "l'oggetto aperto resta in giro");
  // Una creatura per parte: quella del robot attacca la mela, e viceversa; quella di nessuno il più vicino.
  r.creatura("fuoco", "robot", 200); r.creatura("acqua", "mela", 1000); r.creatura("scossa", null, 600);
  assert.strictEqual(amb.stato().creature.map((c) => c.el + ":" + c.per).join(" "), "fuoco:robot acqua:mela scossa:null");
  const attacchi = {};
  amb.avanza(60 * 9, (st) => { for (const c of st.creature) if (c.colpo) attacchi[c.el] = 1; dentro(amb); });
  assert.strictEqual(Object.keys(attacchi).sort().join(","), "acqua,fuoco,scossa", "non tutte le creature attaccano");
  // Dopo una decina di secondi se ne vanno (i colpi fermano l'azione per qualche fotogramma: si aspetta con margine).
  amb.avanza(60 * 20, (st) => (st.creature.length ? undefined : false));
  assert.strictEqual(amb.stato().creature.length, 0, "le creature non se ne vanno");
  // il fumogeno: chi è nella nube non vede, tranne chi l'ha lanciato
  const amb2 = ambiente();
  amb2.avanza(60);
  amb2.finestra.__ring.nube(amb2.lottatore("mela").bacino.x, "robot");
  let ciecoMela = 0, ciecoRobot = 0;
  amb2.avanza(60 * 3, (st) => { if (st.lottatori.find((f) => f.tipo === "mela").accecato) ciecoMela++; if (st.lottatori.find((f) => f.tipo === "robot").accecato) ciecoRobot++; });
  assert.ok(ciecoMela > 20, "chi sta nella nube ci vede benissimo");
  assert.strictEqual(ciecoRobot, 0, "il fumogeno acceca anche chi l'ha lanciato");
  amb2.avanza(60 * 8);
  assert.strictEqual(amb2.stato().nubi, 0, "la nube non si dirada");
  assert.ok(!amb2.lottatore("mela").accecato, "accecato per sempre");
});

test("nell'estensione non piovono telefoni: solo fumogeni e barattoli, e con Premium anche le armi", () => {
  const TELEFONI = ["classico", "grande", "pieghevole", "orologio", "tablet", "pc"];
  let attivo = false;
  const premio = { bloccate: { guerrieri: true, armi: true, meteo: true }, attivo: () => attivo, chiedi() {} };
  const amb = ambiente({ estensione: true, premio, memoria: { "mut-ring": "on" } });
  amb.avanza(30);
  const r = amb.finestra.__ring, visti = {};
  r.tempo(75);
  const guarda = (st) => { for (const t of st.telefoni) { visti[t.tipo] = 1; assert.ok(!TELEFONI.includes(t.tipo), "nell'estensione è comparso un telefono: " + t.tipo); } };
  amb.avanza(60 * 60, guarda);
  r.comandi.colpo("telefoni");
  amb.avanza(60 * 8, guarda);
  assert.ok(visti.fumogeno || visti.barattolo, "non cade niente");
  assert.ok(!visti.pistola && !visti.spada && !visti.bomba, "armi senza Premium");
  // la pioggia arriva innescata: si aprono nubi e barattoli
  attivo = true;
  let aperti = 0;
  for (let giro = 0; giro < 4; giro++) {
    r.comandi.colpo("telefoni");
    amb.avanza(60 * 8, (st) => { guarda(st); if (st.nubi || st.creature.length) aperti++; });
  }
  assert.ok(aperti > 0, "nella pioggia di oggetti non si apre niente");
  assert.ok(visti.pistola || visti.spada || visti.bomba, "con Premium nella pioggia non arrivano le armi");
  dentro(amb);
  // sul sito i telefoni restano
  const sito = ambiente();
  sito.avanza(30);
  sito.finestra.__ring.comandi.colpo("telefoni");
  sito.avanza(60 * 4);
  assert.ok(sito.stato().telefoni.some((t) => TELEFONI.includes(t.tipo)), "sul sito la pioggia di telefoni è sparita");
});

test("nessuno resta a terra per sempre: il conto del K.O. riparte anche per chi trema sul posto", () => {
  // Il caso trovato il 02/10/2026: steso nel cratere (tenuto in posa) e rimesso «in volo» da uno
  // scoppio vicino, il corpo tremava sul posto, la velocità non scendeva mai sotto la soglia e il
  // conto alla rovescia non ripartiva: restava in fondo alla pagina finché non lo si prendeva.
  // Col ring di prima succedeva una volta su due.
  let crateri = 0;
  for (let giro = 0; giro < 8; giro++) {
    const amb = ambiente({ memoria: { "mut-ring-anime": "on", "mut-ring-stile": "guerrieri" } });
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.mossa("robot", "avvinghia");
    let nel = false;
    amb.avanza(60 * 6, (s) => { if (s.lottatori.find((f) => f.tipo === "mela").cratere) { nel = true; return false; } });
    if (!nel) continue;
    crateri++;
    amb.avanza(20);
    const m = amb.lottatore("mela");
    r.scoppia(m.bacino.x + 60, m.bacino.y - 10);
    const fermo = {};
    amb.avanza(60 * 20, (s) => {
      for (const f of s.lottatori) {
        const conta = f.ko > 0 && f.ko < 1e5 && !f.esploso && !f.preso && !f.tenuto;
        fermo[f.tipo] = conta && fermo[f.tipo] && fermo[f.tipo].ko === f.ko ? { ko: f.ko, n: fermo[f.tipo].n + 1 } : { ko: f.ko, n: 0 };
        assert.ok(fermo[f.tipo].n < 60 * 6, "a terra col conto fermo da sei secondi: " + f.tipo);
      }
    });
    dentro(amb);
  }
  assert.ok(crateri >= 3, "il cratere non si forma quasi mai: " + crateri);
});

test("gli oggetti entrano anche dai lati, e quelli rimasti dove nessuno arriva scivolano giù", () => {
  // Una pagina con la testata e un titolo larghi quanto la finestra: tutto quello che cade
  // dall'alto ci si ferma sopra. Prima restava lì, e in campo non arrivava più niente.
  for (const estensione of [false, true]) {
    const amb = ambiente({ estensione, solidi: [[0, 60, 1200, 100], [0, 170, 1200, 210]], memoria: { "mut-ring": "on" } });
    amb.avanza(30);
    const r = amb.finestra.__ring;
    r.tempo(75);
    let dalLato = 0, dallAlto = 0, inCampo = 0;
    const fermi = new Map();
    amb.avanza(60 * 150, (s) => {
      const aTerra = s.lottatori.every((f) => f.esploso || f.base >= s.pavimento - 1);
      const visti = new Set();
      for (const t of s.telefoni) {
        assert.ok(Number.isFinite(t.x) && Number.isFinite(t.y) && t.x >= 0 && t.x <= s.larghezza && t.y <= s.pavimento + 0.5, "oggetto fuori dalla finestra");
        if ((t.x <= 1 || t.x >= s.larghezza - 1) && t.y > 20) dalLato++;
        if (t.y < 0) dallAlto++;
        if (t.stato === "libero" && t.y > s.pavimento - 40) inCampo++;
        if (aTerra && t.stato === "libero" && t.y < 215) {
          const k = Math.round(t.x) + ":" + Math.round(t.y);
          visti.add(k);
          const n = (fermi.get(k) || 0) + 1;
          fermi.set(k, n);
          assert.ok(n < 60 * 9, "un oggetto resta fermo in alto, dove nessuno arriva");
        }
      }
      for (const k of fermi.keys()) if (!visti.has(k)) fermi.delete(k);
    });
    // (Se in campo ci sono già quattro oggetti non ne nascono altri: qualcuno si mette a mano.)
    for (let i = 0; i < 20 && !(dalLato && dallAlto); i++) {
      r.comandi.metti(estensione ? "fumogeno" : "orologio");
      const t = amb.stato().telefoni.slice(-1)[0];
      if (t && (t.x <= 1 || t.x >= amb.stato().larghezza - 1) && t.y > 20) dalLato++;
      if (t && t.y < 0) dallAlto++;
      amb.avanza(30);
    }
    assert.ok(dalLato > 0, "nessun oggetto è entrato da un lato");
    assert.ok(dallAlto > 0, "nessun oggetto è caduto dall'alto");
    assert.ok(inCampo > 60, "in campo, all'altezza dei lottatori, non arriva quasi niente");
    dentro(amb);
  }
});

test("si lotta davvero: pochi tempi morti, e chi sta sopra un elemento scende a cercare l'altro", () => {
  // 02/10/2026, su segnalazione («a volte sembrano fermi»). Prima: 24 colpi a segno al minuto,
  // il 22% del tempo in piedi passato in pause di oltre quattro secondi senza un colpo, il 15%
  // con tutti e due fermi. I numeri su 46 pagine li dà `node tests/misura-lotta.cjs`.
  let fot = 0, pronti = 0, colpi = 0, inPausa = 0, fermi2 = 0;
  for (let giro = 0; giro < 8; giro++) {
    const amb = ambiente({ estensione: true, memoria: { "mut-ring": "on" } });
    amb.avanza(20);
    let prima = null, senza = 0;
    amb.avanza(60 * 45, (s) => {
      const [a, b] = s.lottatori;
      fot++;
      const colpo = prima && s.lottatori.some((f, i) => f.danni > prima[i].danni || (f.ko > 0 && !(prima[i].ko > 0)));
      prima = s.lottatori.map((f) => ({ danni: f.danni, ko: f.ko }));
      if (colpo) colpi++;
      if (a.ko > 0 || b.ko > 0 || a.esploso || b.esploso) { senza = 0; return; }
      pronti++;
      const fermo = (f) => (!f.azione && !f.vola && !(f.stordito > 0) && !f.inVolo && !f.scalando) || f.azione === "provoca";
      if (fermo(a) && fermo(b)) fermi2++;
      if (colpo) { if (senza > 240) inPausa += senza; senza = 0; } else senza++;
    });
    if (senza > 240) inPausa += senza;
    dentro(amb);
  }
  const alMinuto = colpi / (fot / 3600);
  assert.ok(alMinuto > 27, "pochi colpi a segno: " + alMinuto.toFixed(1) + " al minuto");
  assert.ok(inPausa / pronti < 0.22, "troppe pause lunghe: " + Math.round(100 * inPausa / pronti) + "% del tempo in piedi");
  assert.ok(fermi2 / pronti < 0.11, "fermi tutti e due per il " + Math.round(100 * fermi2 / pronti) + "% del tempo");
  // Uno sopra un elemento largo quanto la pagina, l'altro sotto e senza modo di salire: chi sta
  // sopra si lascia cadere attraverso. Prima camminava fino al bordo (20 secondi), o non scendeva mai.
  for (let giro = 0; giro < 3; giro++) {
    const amb = ambiente({ solidi: [[60, 420, 1140, 450]] });
    amb.avanza(30);
    amb.porta("mela", 600, 330);
    amb.rilascia(600, 330);
    let sopra = false, insieme = false;
    amb.avanza(60 * 10, (s) => {
      const m = s.lottatori.find((f) => f.tipo === "mela"), r = s.lottatori.find((f) => f.tipo === "robot");
      dentro(amb);
      if (m.sopraUnElemento && !m.ko) sopra = true;
      if (sopra && Math.abs(m.bacino.y - r.bacino.y) < 20 && !m.ko && !r.ko && !m.inVolo) { insieme = true; return false; }
    });
    assert.ok(sopra, "la mela non si è posata sull'elemento");
    assert.ok(insieme, "chi sta sopra non scende a cercare l'altro");
  }
});
