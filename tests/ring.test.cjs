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

function ambiente({ ridotto = false, larghezza = 1200, altezza = 800, solidi = [] } = {}) {
  const richieste = [];
  const ascoltatori = {};
  const contesto2d = new Proxy({}, {
    get(obj, nome) {
      if (nome in obj) return obj[nome];
      if (nome === "createRadialGradient") return () => ({ addColorStop() {} });
      return () => {};
    },
    set(obj, nome, valore) { obj[nome] = valore; return true; },
  });
  const tela = { clientWidth: larghezza, clientHeight: altezza, width: 0, height: 0,
                 getContext: () => contesto2d };
  const pavimento = altezza - 44;
  const barra = { getBoundingClientRect: () => riquadro(0, pavimento, larghezza, altezza) };
  const elementi = solidi.map(([l, t, r, b]) => ({
    getBoundingClientRect: () => riquadro(l, t, r, b), closest: () => null,
  }));
  const classi = new Set();
  const documento = {
    hidden: false,
    documentElement: { classList: { add: (c) => classi.add(c), remove: (c) => classi.delete(c) } },
    fonts: null,
    body: { querySelectorAll: () => elementi },
    querySelector(sel) {
      if (sel === "[data-ring]") return tela;
      if (sel === ".ultimora-barra") return barra;
      return null;
    },
    addEventListener(tipo, fn) { (ascoltatori["doc:" + tipo] = ascoltatori["doc:" + tipo] || []).push(fn); },
  };
  const finestra = {
    devicePixelRatio: 1, innerWidth: larghezza, innerHeight: altezza, scrollY: 0,
    matchMedia: () => ({ matches: ridotto }),
    addEventListener(tipo, fn) { (ascoltatori[tipo] = ascoltatori[tipo] || []).push(fn); },
  };
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

test("chi ha chiesto meno movimento non ha animazione né presa", () => {
  const amb = ambiente({ ridotto: true });
  assert.strictEqual(amb.richieste.length, 0);
  assert.strictEqual(amb.stato().lottatori.length, 2);
  const f = amb.lottatore("robot");
  const e = amb.premi(f.bacino.x, f.bacino.y - 8);
  assert.ok(!e.bloccato);
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
