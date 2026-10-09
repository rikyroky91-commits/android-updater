// Il tema di Halloween (09/10/2026): quando si accende da solo, e che cosa mette in giro.
// `web/static/halloween.js` gira qui dentro un finto browser: una finestra, una testata,
// la striscia delle notizie in fondo, un tasto, e un canvas che non disegna niente.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SORGENTE = fs.readFileSync(path.join(__dirname, "..", "web", "static", "halloween.js"), "utf8");

function finto({ memoria = {}, cerca = "", ridotto = false, larghezza = 1280, altezza = 800 } = {}) {
  const ascolta = {}, fotogrammi = [], classi = new Set();
  const nulla = new Proxy({}, { get: (o, k) => (k === "createRadialGradient" ? () => ({ addColorStop() {} }) : () => {}), set: () => true });
  const riquadro = (l, t, r, b) => ({ left: l, top: t, right: r, bottom: b, width: r - l, height: b - t });
  const tasto = { attr: {}, setAttribute(k, v) { this.attr[k] = v; }, closest: (sel) => (sel === "[data-halloween-tasto]" ? tasto : null) };
  const campo = { getBoundingClientRect: () => riquadro(200, 300, 900, 340), closest: () => null };
  const documento = {
    readyState: "complete", hidden: false, body: { appendChild() {} },
    documentElement: { classList: { toggle: (c, si) => (si ? classi.add(c) : classi.delete(c)), contains: (c) => classi.has(c), add: (c) => classi.add(c), remove: (c) => classi.delete(c) } },
    querySelector: (sel) => (sel === ".ultimora-barra" ? { getBoundingClientRect: () => riquadro(0, altezza - 40, larghezza, altezza) }
      : sel === ".testata" ? { getBoundingClientRect: () => riquadro(0, 0, larghezza, 70) } : null),
    querySelectorAll: (sel) => (sel === "[data-halloween-tasto]" ? [tasto] : /main input/.test(sel) ? [campo] : []),
    createElement: () => ({ style: {}, setAttribute() {}, getContext: () => nulla }),
    addEventListener: (t, fn) => { (ascolta["doc:" + t] = ascolta["doc:" + t] || []).push(fn); },
  };
  const finestra = {
    innerWidth: larghezza, innerHeight: altezza, devicePixelRatio: 1, location: { search: cerca },
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null), setItem: (k, v) => { memoria[k] = String(v); }, removeItem: (k) => { delete memoria[k]; } },
    matchMedia: (q) => ({ matches: ridotto && /reduce/.test(q) }),
    requestAnimationFrame: (fn) => { fotogrammi.push(fn); return fotogrammi.length; }, cancelAnimationFrame() {},
    addEventListener: (t, fn) => { (ascolta[t] = ascolta[t] || []).push(fn); }, dispatchEvent() {}, CustomEvent: function () {},
  };
  finestra.window = finestra; finestra.document = documento;
  vm.runInNewContext(SORGENTE, Object.assign(finestra, { CustomEvent: function () {}, Math, Date, setTimeout, clearTimeout }));
  const avanza = (n) => { for (let i = 0; i < n && fotogrammi.length; i++) fotogrammi.shift()(); };
  return { h: finestra.__halloween, classi, memoria, tasto, avanza, clic: () => (ascolta["doc:click"] || []).forEach((fn) => fn({ target: tasto })) };
}

test("si accende da solo dal 1° ottobre al 2 novembre; spento in stagione resta spento; si può forzare", () => {
  const { h } = finto();
  assert.strictEqual(h.decidi(2026, 10, 1, null, ""), true);
  assert.strictEqual(h.decidi(2026, 10, 31, null, ""), true);
  assert.strictEqual(h.decidi(2026, 11, 2, null, ""), true);
  assert.strictEqual(h.decidi(2026, 11, 3, null, ""), false);
  assert.strictEqual(h.decidi(2026, 9, 30, null, ""), false);
  assert.strictEqual(h.decidi(2026, 10, 20, "off-2026", ""), false, "spento col tasto, in stagione resta spento");
  assert.strictEqual(h.decidi(2027, 10, 20, "off-2026", ""), true, "l'anno dopo torna da solo");
  assert.strictEqual(h.decidi(2026, 6, 1, "on-2026", ""), true, "acceso a mano fuori stagione");
  assert.strictEqual(h.decidi(2026, 6, 1, null, "?halloween=1"), true);
  assert.strictEqual(h.decidi(2026, 10, 20, null, "?q=1&halloween=0"), false);
});

test("acceso: zucche, lucine, mani che camminano e scappano, zombie e pipistrelli che passano", () => {
  const f = finto({ cerca: "?halloween=1" });
  assert.ok(f.h.acceso());
  assert.ok(f.classi.has("halloween"));
  assert.strictEqual(f.tasto.attr["aria-pressed"], "true");
  f.avanza(5);
  let s = f.h.stato();
  assert.ok(s.zucche >= 3, "le zucche: " + s.zucche);
  assert.ok(s.mani.length >= 2, "le mani: " + s.mani.length);
  assert.ok(s.superfici >= 2, "il fondo e il campo di ricerca");
  const x0 = s.mani.map((m) => m.x);
  f.avanza(120);
  s = f.h.stato();
  assert.ok(s.mani.some((m, i) => Math.abs(m.x - x0[i]) > 5), "le mani camminano");
  // Il puntatore addosso a una mano: scappa.
  const m = s.mani[0];
  f.h.puntatore(m.x + 10, m.y);
  f.avanza(2);
  assert.ok(f.h.stato().mani[0].scappa > 0, "la mano scappa dal puntatore");
  // Uno zombie attraversa il fondo; i pipistrelli passano.
  f.h.zombie(); f.h.pipistrelli();
  const z0 = f.h.stato().zombie[0].x;
  f.avanza(200);
  const z = f.h.stato().zombie[0];
  assert.ok(z && Math.abs(z.x - z0) > 20, "lo zombie cammina");
  // Il tasto lo spegne, e la scelta resta.
  f.clic();
  assert.ok(!f.h.acceso());
  assert.ok(!f.classi.has("halloween"));
  assert.strictEqual(f.h.stato().mani.length, 0, "spento non resta niente in giro");
});

test("con «meno movimento» restano zucche e lucine, senza mani né zombie", () => {
  const f = finto({ cerca: "?halloween=1", ridotto: true });
  f.avanza(3);
  const s = f.h.stato();
  assert.ok(s.zucche >= 3);
  assert.strictEqual(s.mani.length, 0);
});
