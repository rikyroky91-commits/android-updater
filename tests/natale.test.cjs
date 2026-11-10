// Il tema di Natale sul sito: la stagione, la scelta salvata, e lo script in testa a `base.html`
// che decide la classe `html.natale` prima del primo disegno. (Dal 10/11/2026 niente Halloween.)
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const NATALE = fs.readFileSync(path.join(__dirname, "..", "web", "static", "natale.js"), "utf8");
function nataleFinto({ memoria = {}, classiIniziali = [] } = {}) {
  const fotogrammi = [], classi = new Set(classiIniziali);
  const nulla = new Proxy({}, { get: (o, k) => (k === "createRadialGradient" || k === "createLinearGradient" ? () => ({ addColorStop() {} }) : () => {}), set: () => true });
  const tasto = { attr: {}, setAttribute(k, v) { this.attr[k] = v; } };
  const testata = { getBoundingClientRect: () => ({ left: 0, top: 0, right: 1280, bottom: 70, width: 1280, height: 70 }) };
  const documento = {
    readyState: "complete", hidden: false, body: { appendChild() {} },
    documentElement: { getAttribute: () => "scuro", classList: { toggle: (c, si) => (si ? classi.add(c) : classi.delete(c)), contains: (c) => classi.has(c), add: (c) => classi.add(c), remove: (c) => classi.delete(c) } },
    querySelector: (sel) => (sel === ".testata" ? testata : null), querySelectorAll: (sel) => (sel === "[data-natale-tasto]" ? [tasto] : []),
    createElement: () => ({ style: {}, setAttribute() {}, getContext: () => nulla }), addEventListener() {},
  };
  const finestra = {
    innerWidth: 1280, innerHeight: 800, devicePixelRatio: 1, location: { search: "" },
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null), setItem: (k, v) => { memoria[k] = String(v); }, removeItem: (k) => { delete memoria[k]; } },
    matchMedia: () => ({ matches: false }), getComputedStyle: () => ({ backgroundColor: "" }),
    requestAnimationFrame: (fn) => { fotogrammi.push(fn); return fotogrammi.length; }, cancelAnimationFrame() {},
    addEventListener() {}, dispatchEvent() {},
  };
  finestra.window = finestra; finestra.document = documento;
  vm.runInNewContext(NATALE, Object.assign(finestra, { CustomEvent: function () {}, Math, Date, Map, Float32Array, setTimeout, clearTimeout }));
  return { n: finestra.__natale, classi, memoria, avanza: (k) => { for (let i = 0; i < k && fotogrammi.length; i++) fotogrammi.shift()(); } };
}

test("natale.js: stagione dal 2 novembre al 6 gennaio; spento in stagione si ricorda con l'anno", () => {
  const { n } = nataleFinto();
  assert.strictEqual(n.stagione(2026, 11, 1), 0);
  assert.strictEqual(n.stagione(2026, 11, 2), 2026);
  assert.strictEqual(n.stagione(2026, 12, 31), 2026);
  assert.strictEqual(n.stagione(2027, 1, 6), 2026);
  assert.strictEqual(n.stagione(2027, 1, 7), 0);
  assert.ok(!n.acceso());
  assert.ok(nataleFinto({ classiIniziali: ["natale"] }).n.acceso());
  const f = nataleFinto({ classiIniziali: ["natale"] });
  const oggi = new Date(), sn = n.stagione(oggi.getFullYear(), oggi.getMonth() + 1, oggi.getDate());
  f.n.imposta(false);
  assert.strictEqual(f.memoria["mut-natale"], sn ? "off-" + sn : undefined);
  f.n.imposta(true);
  assert.strictEqual(f.memoria["mut-natale"], sn ? undefined : "on");
});

test("natale.js: Halloween e il passaggio non ci sono più; le palline appese ballano senza errori", () => {
  assert.ok(!/halloween/i.test(NATALE.replace(/\/\*[\s\S]*?\*\//, "")), "niente Halloween nel codice");
  const f = nataleFinto({ classiIniziali: ["natale"] });
  assert.strictEqual(f.n.arriva, undefined);
  assert.strictEqual(f.n.soffia, undefined);
  f.avanza(400);
  assert.ok(f.n.stato().fiocchi > 50, "nevica");
  assert.strictEqual(f.n.stato().ingresso, 1);
});

// --- Lo script in testa a `base.html`: decide le classi prima del primo disegno ----------------
const BASE = fs.readFileSync(path.join(__dirname, "..", "web", "templates", "base.html"), "utf8");
const TESTA = BASE.slice(BASE.indexOf("<script>(function(){") + 8, BASE.indexOf("</script>", BASE.indexOf("<script>(function(){")));
function testa({ data, memoria = {}, cerca = "", scuroSistema = false }) {
  const classi = new Set(), attr = {};
  const VeraData = Date;
  function Finta() { return new VeraData(data[0], data[1] - 1, data[2], 12); }
  const ctx = {
    Date: Finta, location: { search: cerca },
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null) },
    matchMedia: (q) => ({ matches: scuroSistema && /dark/.test(q) }), setTimeout() {},
    document: { documentElement: { classList: { add: (c) => classi.add(c), remove: (c) => classi.delete(c) }, setAttribute: (k, v) => { attr[k] = v; } } },
  };
  ctx.window = ctx;
  vm.runInNewContext(TESTA, ctx);
  return { classi: [...classi].sort().join(" "), tema: attr["data-tema"] };
}

test("base.html: Natale dal 2 novembre al 6 gennaio, mai Halloween né passaggio", () => {
  assert.ok(!/halloween|passaggio/i.test(TESTA.replace(/\/\*[\s\S]*?\*\//g, "")), "lo script non nomina più Halloween");
  assert.strictEqual(testa({ data: [2026, 10, 31] }).classi, "");
  assert.strictEqual(testa({ data: [2026, 10, 31], cerca: "?halloween=1" }).classi, "", "il vecchio parametro non fa più niente");
  assert.strictEqual(testa({ data: [2026, 11, 1] }).classi, "");
  assert.strictEqual(testa({ data: [2026, 11, 2] }).classi, "natale", "dal 2 novembre subito Natale, senza passaggio");
  assert.strictEqual(testa({ data: [2026, 11, 9] }).classi, "natale");
  assert.strictEqual(testa({ data: [2026, 12, 25] }).classi, "natale");
  assert.strictEqual(testa({ data: [2027, 1, 6] }).classi, "natale");
  assert.strictEqual(testa({ data: [2027, 1, 7] }).classi, "");
  assert.strictEqual(testa({ data: [2026, 7, 1] }).classi, "");
  assert.strictEqual(testa({ data: [2026, 11, 3], memoria: { "mut-natale": "off-2026" } }).classi, "");
  assert.strictEqual(testa({ data: [2027, 1, 3], memoria: { "mut-natale": "off-2026" } }).classi, "", "la stagione 2026 finisce a gennaio 2027");
  assert.strictEqual(testa({ data: [2027, 11, 20], memoria: { "mut-natale": "off-2026" } }).classi, "natale", "l'anno dopo torna da solo");
  assert.strictEqual(testa({ data: [2026, 7, 1], memoria: { "mut-natale": "on" } }).classi, "natale", "acceso a mano resta acceso");
  assert.strictEqual(testa({ data: [2026, 11, 3], cerca: "?natale=0" }).classi, "");
  assert.strictEqual(testa({ data: [2026, 7, 1], cerca: "?natale=1" }).classi, "natale");
});

test("base.html: il tema segue la scelta salvata, poi il sistema", () => {
  assert.strictEqual(testa({ data: [2026, 10, 15] }).tema, "chiaro");
  assert.strictEqual(testa({ data: [2026, 10, 15], scuroSistema: true }).tema, "scuro");
  assert.strictEqual(testa({ data: [2026, 10, 15], memoria: { "mut-tema": "chiaro" }, scuroSistema: true }).tema, "chiaro");
});
