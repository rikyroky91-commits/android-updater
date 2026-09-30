/* Il ring della home (static/ring.js) senza browser.
 *
 * Si carica lo script in una sandbox con un DOM finto (un canvas che
 * non disegna niente, un orologio che avanza a comando) e si fa girare
 * la fisica per qualche minuto simulato. Quello che si difende:
 *   - i lottatori restano dentro il ring: né sotto il pavimento, né oltre
 *     le pareti, né coordinate NaN (una bambola di Verlet che esplode è
 *     il guasto tipico di queste simulazioni);
 *   - il ciclo è davvero casuale e davvero una lotta: qualcuno va K.O.;
 *   - chi ha chiesto meno movimento non ottiene un ciclo di animazione;
 *   - a scheda nascosta il ciclo si ferma.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SORGENTE = fs.readFileSync(path.join(__dirname, "..", "web", "static", "ring.js"), "utf8");

function ambiente({ ridotto = false, larghezza = 1200 } = {}) {
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
  const tela = {
    clientWidth: larghezza, clientHeight: 118, width: 0, height: 0,
    getContext: () => contesto2d,
  };
  const documento = {
    hidden: false,
    documentElement: {},
    fonts: null,
    querySelector(sel) {
      if (sel === "[data-ring]") return tela;
      return null;
    },
    addEventListener(tipo, fn) { (ascoltatori["doc:" + tipo] = ascoltatori["doc:" + tipo] || []).push(fn); },
  };
  const finestra = {
    devicePixelRatio: 1,
    matchMedia: () => ({ matches: ridotto }),
    addEventListener(tipo, fn) { (ascoltatori[tipo] = ascoltatori[tipo] || []).push(fn); },
  };
  const sandbox = {
    window: finestra, document: documento, Math, Date, Object, JSON, String, Number,
    getComputedStyle: () => ({ getPropertyValue: () => "" }),
    requestAnimationFrame: (fn) => { richieste.push(fn); return richieste.length; },
    setInterval: () => 0, setTimeout: () => 0, clearTimeout: () => {},
  };
  sandbox.window.requestAnimationFrame = sandbox.requestAnimationFrame;
  vm.createContext(sandbox);
  vm.runInContext(SORGENTE, sandbox);
  let adesso = 0;
  return {
    finestra, documento, richieste, ascoltatori,
    stato: () => finestra.__ring.stato(),
    // Fa girare N fotogrammi da ~16,7 ms, come farebbe il browser.
    avanza(fotogrammi) {
      for (let i = 0; i < fotogrammi; i++) {
        const fn = richieste.shift();
        if (!fn) return i;
        adesso += 1000 / 60;
        fn(adesso);
      }
      return fotogrammi;
    },
  };
}

test("i lottatori restano dentro il ring e non esplodono", () => {
  const amb = ambiente();
  for (let blocco = 0; blocco < 60; blocco++) {      // ~60 s simulati
    amb.avanza(60);
    const s = amb.stato();
    for (const f of s.lottatori) {
      for (const punto of [f.testa, f.bacino]) {
        assert.ok(Number.isFinite(punto.x) && Number.isFinite(punto.y), "coordinate non finite");
        assert.ok(punto.y <= s.suolo + 0.01, "sotto il pavimento");
        assert.ok(punto.x >= 0 && punto.x <= s.larghezza, "oltre le pareti");
      }
    }
  }
});

test("in piedi la testa sta sopra il bacino", () => {
  const amb = ambiente();
  amb.avanza(90);
  const s = amb.stato();
  for (const f of s.lottatori) {
    if (!f.ko) assert.ok(f.testa.y < f.bacino.y, f.tipo + " a testa in giù da sveglio");
  }
});

test("è una lotta vera: prima o poi qualcuno va K.O.", () => {
  const amb = ambiente();
  let ko = false;
  for (let blocco = 0; blocco < 240 && !ko; blocco++) {   // fino a 4 minuti simulati
    amb.avanza(60);
    const p = amb.stato().punteggio;
    ko = p.robot + p.mela > 0;
  }
  assert.ok(ko, "in quattro minuti nessuno è andato al tappeto");
});

test("su uno schermo stretto la lotta regge lo stesso", () => {
  const amb = ambiente({ larghezza: 320 });
  amb.avanza(1800);
  const s = amb.stato();
  for (const f of s.lottatori) {
    assert.ok(f.bacino.x > 0 && f.bacino.x < 320);
  }
});

test("chi ha chiesto meno movimento non ha un ciclo di animazione", () => {
  const amb = ambiente({ ridotto: true });
  assert.strictEqual(amb.richieste.length, 0);
  // I lottatori ci sono, fermi in guardia.
  assert.strictEqual(amb.stato().lottatori.length, 2);
});

test("a scheda nascosta il ciclo si ferma, e riparte quando torna visibile", () => {
  const amb = ambiente();
  amb.avanza(10);
  amb.documento.hidden = true;
  amb.avanza(1);                      // questo fotogramma vede la scheda nascosta
  assert.strictEqual(amb.richieste.length, 0, "il ciclo gira ancora a scheda nascosta");
  amb.documento.hidden = false;
  for (const fn of amb.ascoltatori["doc:visibilitychange"] || []) fn();
  assert.strictEqual(amb.richieste.length, 1);
});
