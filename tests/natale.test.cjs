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
function testa({ data, memoria = {}, cerca = "", scuroSistema = false, utc = null }) {
  const classi = new Set(), attr = {};
  const VeraData = Date;
  // `utc`: [ore, minuti] UTC; senza, mezzogiorno UTC (giorno pieno ad Acireale).
  function Finta(...a) { return a.length ? new VeraData(...a) : new VeraData(VeraData.UTC(data[0], data[1] - 1, data[2], ...(utc || [12, 0]))); }
  Finta.UTC = VeraData.UTC;
  const ctx = {
    Date: Finta, location: { search: cerca },
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null) },
    matchMedia: (q) => ({ matches: scuroSistema && /dark/.test(q) }), setTimeout() {},
    document: { documentElement: { classList: { add: (c) => classi.add(c), remove: (c) => classi.delete(c) }, setAttribute: (k, v) => { attr[k] = v; } } },
  };
  ctx.window = ctx;
  vm.runInNewContext(TESTA, ctx);
  return { classi: [...classi].sort().join(" "), tema: attr["data-tema"], cielo: attr["data-cielo"] || null, scelta: attr["data-tema-scelta"] };
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

test("base.html: il tema segue la scelta salvata, poi il sole di Acireale (giorno, tramonto, notte)", () => {
  // Il 15 ottobre ad Acireale il sole sorge verso le 05:10 UTC e tramonta verso le 16:35 UTC.
  assert.deepStrictEqual(testa({ data: [2026, 10, 15] }), { classi: "", tema: "chiaro", cielo: null, scelta: "auto" });
  assert.strictEqual(testa({ data: [2026, 10, 15], scuroSistema: true }).tema, "chiaro", "di giorno chiaro, anche se il sistema è scuro");
  const sera = testa({ data: [2026, 10, 15], utc: [16, 20] });
  assert.strictEqual(sera.tema, "chiaro"); assert.strictEqual(sera.cielo, "tramonto");
  const alba = testa({ data: [2026, 10, 15], utc: [5, 5] });
  assert.strictEqual(alba.cielo, "tramonto", "anche all'alba");
  const notte = testa({ data: [2026, 10, 15], utc: [21, 0] });
  assert.strictEqual(notte.tema, "scuro"); assert.strictEqual(notte.cielo, null);
  assert.strictEqual(testa({ data: [2026, 10, 15], utc: [2, 0] }).tema, "scuro");
  // D'estate il tramonto è più tardi: alle 17:00 UTC del 21 giugno è ancora giorno, alle 18:20 tramonto.
  assert.strictEqual(testa({ data: [2026, 6, 21], utc: [17, 0] }).cielo, null);
  assert.strictEqual(testa({ data: [2026, 6, 21], utc: [18, 20] }).cielo, "tramonto");
  // La scelta col tasto vince sul sole.
  assert.deepStrictEqual(testa({ data: [2026, 10, 15], utc: [21, 0], memoria: { "mut-tema": "chiaro" } }), { classi: "", tema: "chiaro", cielo: null, scelta: "chiaro" });
  assert.strictEqual(testa({ data: [2026, 10, 15], memoria: { "mut-tema": "scuro" } }).tema, "scuro");
  assert.strictEqual(testa({ data: [2026, 10, 15], utc: [16, 20], memoria: { "mut-tema": "auto" } }).cielo, "tramonto");
});

test("tema.js: stessa formula dello script in testa; il tasto gira auto → chiaro → scuro → auto", () => {
  const TEMA = fs.readFileSync(path.join(__dirname, "..", "web", "static", "tema.js"), "utf8");
  const memoria = {}, attr = {}, ascoltatori = {}, tasto = { attr: {}, setAttribute(k, v) { this.attr[k] = v; }, closest: () => tasto };
  const finestra = {
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null), setItem: (k, v) => { memoria[k] = String(v); } },
    requestAnimationFrame() {}, dispatchEvent() {}, setInterval() {},
    document: {
      readyState: "complete", querySelectorAll: () => [tasto], addEventListener: (t, fn) => { ascoltatori[t] = fn; },
      documentElement: { classList: { add() {} }, getAttribute: (k) => (k in attr ? attr[k] : null), setAttribute: (k, v) => { attr[k] = v; }, removeAttribute: (k) => { delete attr[k]; } },
    },
  };
  finestra.window = finestra;
  vm.runInNewContext(TEMA, Object.assign(finestra, { CustomEvent: function () {}, Math, Date, setTimeout }));
  const t = finestra.__tema;
  for (const [g, m, ore] of [[[2026, 10, 15], 0, [5, 5]], [[2026, 10, 15], 0, [12, 0]], [[2026, 10, 15], 0, [16, 20]], [[2026, 10, 15], 0, [21, 0]], [[2026, 6, 21], 0, [18, 20]], [[2026, 12, 21], 0, [15, 30]]]) {
    const d = new Date(Date.UTC(g[0], g[1] - 1, g[2], ...ore));
    const f = t.fase(d), h = testa({ data: g, utc: ore });
    assert.strictEqual(h.cielo === "tramonto" ? "tramonto" : h.tema === "scuro" ? "notte" : "giorno", f, `stessa fase il ${g} alle ${ore}`);
  }
  // Tramonto del 21 dicembre ad Acireale verso le 15:40 UTC (16:40 in Italia), con un paio di minuti di margine.
  const s = t.sole(new Date(Date.UTC(2026, 11, 21, 12)));
  assert.ok(Math.abs(s.tramonto - (15 * 60 + 40)) < 8, "tramonto " + s.tramonto);
  assert.strictEqual(attr["data-tema-scelta"], "auto");
  const clic = () => ascoltatori.click({ target: tasto });
  clic(); assert.strictEqual(memoria["mut-tema"], "chiaro"); assert.strictEqual(attr["data-tema"], "chiaro"); assert.ok(!("data-cielo" in attr));
  clic(); assert.strictEqual(memoria["mut-tema"], "scuro"); assert.strictEqual(attr["data-tema"], "scuro"); assert.strictEqual(tasto.attr["aria-pressed"], "true");
  clic(); assert.strictEqual(memoria["mut-tema"], "auto"); assert.strictEqual(attr["data-tema-scelta"], "auto");
});

test("natale.js: le lampadine si spengono al passaggio del puntatore e poi si riaccendono", () => {
  assert.ok(/function spegniVicine/.test(NATALE) && /spegniVicine\(e\.clientX, e\.clientY\)/.test(NATALE), "il puntatore spegne le lampadine vicine");
  assert.ok(/luciSpente\[l\.c\] = SPENTA/.test(NATALE));
  assert.ok(/if \(--luciSpente\[c\] <= 0\) delete luciSpente\[c\]/.test(NATALE), "dopo un po' si riaccendono");
});

test("natale.js: la slitta lancia i regali, che cadono, si posano e, aperti, svaniscono", () => {
  const f = nataleFinto({ classiIniziali: ["natale"] });
  f.avanza(2);
  const prima = f.n.stato().regali.length;
  f.n.slitta();
  let visti = 0;
  for (let i = 0; i < 2600; i++) { f.avanza(1); visti = Math.max(visti, f.n.stato().cadenti); }
  const st = f.n.stato(), caduti = st.regali.filter((g) => g.caduto);
  assert.ok(visti >= 1, "qualche regalo in volo");
  assert.strictEqual(st.cadenti, 0, "tutti a terra");
  assert.ok(caduti.length >= 2 && caduti.length <= 6, "posati sul fondo: " + caduti.length);
  assert.strictEqual(st.regali.length, prima + caduti.length);
  caduti.forEach((g) => assert.ok(Math.abs(g.y - (st.pavimento - 10)) < 12, "a terra"));
  const i = st.regali.findIndex((g) => g.caduto);
  f.n.apri(i);
  f.avanza(200);
  assert.strictEqual(f.n.stato().regali.length, st.regali.length - 1, "aperto, se ne va");
});
