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

function finto({ memoria = {}, cerca = "", ridotto = false, larghezza = 1280, altezza = 800, natale = null, sessione = null, classiIniziali = [] } = {}) {
  const ascolta = {}, fotogrammi = [], classi = new Set(classiIniziali);
  const nulla = new Proxy({}, { get: (o, k) => (k === "createRadialGradient" || k === "createLinearGradient" ? () => ({ addColorStop() {} }) : () => {}), set: () => true });
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
  if (natale) finestra.__natale = natale;
  if (sessione) finestra.sessionStorage = { getItem: (k) => (k in sessione ? sessione[k] : null), setItem: (k, v) => { sessione[k] = String(v); } };
  finestra.window = finestra; finestra.document = documento;
  vm.runInNewContext(SORGENTE, Object.assign(finestra, { CustomEvent: function () {}, Math, Date, setTimeout, clearTimeout }));
  const avanza = (n) => { for (let i = 0; i < n && fotogrammi.length; i++) fotogrammi.shift()(); };
  return { h: finestra.__halloween, classi, memoria, tasto, avanza, fotogrammi, clic: () => (ascolta["doc:click"] || []).forEach((fn) => fn({ target: tasto })) };
}

test("si accende da solo dal 1° ottobre al 1° novembre; spento in stagione resta spento; si può forzare", () => {
  const { h } = finto();
  assert.strictEqual(h.decidi(2026, 10, 1, null, ""), true);
  assert.strictEqual(h.decidi(2026, 10, 31, null, ""), true);
  assert.strictEqual(h.decidi(2026, 11, 1, null, ""), true);
  assert.strictEqual(h.decidi(2026, 11, 2, null, ""), false, "il 2 novembre è del passaggio a Natale");
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

test("al passaggio del mouse: la lucina toccata si spegne e si riaccende, la zucca si sveglia", () => {
  const f = finto({ cerca: "?halloween=1" });
  f.avanza(3);
  let s = f.h.stato();
  assert.strictEqual(s.lucineSpente, 0);
  const l = s.lampadine[4];
  f.h.puntatore(l.x, l.y + 7);
  f.avanza(2);
  assert.strictEqual(f.h.stato().lucineSpente, 1, "la lucina sotto il puntatore si spegne");
  f.h.puntatore(-999, -999);
  f.avanza(200);
  assert.strictEqual(f.h.stato().lucineSpente, 0, "e dopo un po' si riaccende da sola");
  const z = f.h.stato().posZucche[0];
  f.h.puntatore(z.x, z.y);
  f.avanza(20);
  assert.ok(f.h.stato().zuccheSveglie >= 1, "la zucca sotto il puntatore si sveglia");
  f.h.puntatore(-999, -999);
  f.avanza(150);
  assert.strictEqual(f.h.stato().zuccheSveglie, 0, "e si riaddormenta");
});

// --- IL PASSAGGIO A NATALE (02/11/2026) -------------------------------------------------------
// Un finto `__natale` che si segna chi lo chiama: il passaggio lo deve accendere e far soffiare.
function natalino() {
  const chiamate = [];
  return { chiamate, arriva() { chiamate.push("arriva"); }, soffia(f, d) { chiamate.push("soffia:" + f + ":" + d); } };
}

test("il passaggio: la neve gela gli zombie, incappuccia le zucche, spegne le lucine; la tormenta porta via tutto e resta Natale", () => {
  const natale = natalino(), sessione = {};
  const f = finto({ cerca: "?passaggio=1", natale, sessione, memoria: {} });
  const T = f.h.tempiPassaggio;
  assert.ok(f.h.acceso(), "il passaggio parte con Halloween acceso");
  assert.ok(f.classi.has("halloween"));
  assert.ok(f.h.passaggio(), "la scena è partita");
  let s = f.h.stato();
  assert.ok(s.zombie.length >= 2, "almeno uno zombie per lato in scena: " + s.zombie.length);
  assert.ok(s.pipistrelli >= 2 && s.zucche >= 3 && s.mani.length >= 2);
  f.avanza(T.neve - 5);
  assert.deepStrictEqual(natale.chiamate, [], "prima un attimo di Halloween com'è");
  f.avanza(10);
  assert.deepStrictEqual(natale.chiamate, ["arriva"], "poi comincia a nevicare");
  f.avanza(T.raffica - T.neve - 10);
  s = f.h.stato();
  assert.ok(s.zombieGelati >= 1, "gli zombie sono nel ghiaccio prima della tormenta");
  assert.ok(s.zuccheInnevate >= 3, "le zucche hanno il cappuccio di neve");
  assert.ok(f.h.passaggio().spente >= 10, "le lucine si spengono una a una: " + f.h.passaggio().spente);
  assert.strictEqual(s.mani.length, 0, "le mani sono scappate fuori dalla finestra");
  assert.strictEqual(s.pipistrelli, 0, "i pipistrelli sono volati via");
  const xz = s.zombie.map((z) => z.x);
  f.avanza(60);
  assert.ok(natale.chiamate.some((c) => /^soffia:/.test(c)), "arriva la tormenta");
  s = f.h.stato();
  assert.ok(s.zuccheInViaggio >= 1, "le zucche rotolano via");
  assert.ok(s.zombie.some((z, i) => z.x > xz[i] + 5), "i blocchi di ghiaccio scivolano col vento");
  f.avanza(T.fine + T.sfuma);
  assert.strictEqual(f.h.passaggio(), null, "la scena è finita");
  assert.ok(!f.h.acceso(), "Halloween se n'è andato");
  assert.ok(!f.classi.has("halloween") && !f.classi.has("passaggio"));
  s = f.h.stato();
  assert.strictEqual(s.zucche + s.zombie.length + s.mani.length + s.pipistrelli, 0, "non resta niente di Halloween in giro");
  assert.strictEqual(sessione["mut-passaggio"], "fatto", "una volta per scheda");
  assert.ok(!("mut-halloween" in f.memoria), "il passaggio non è una scelta: niente salvato");
  assert.ok(f.fotogrammi.length === 0, "il ciclo si è fermato");
});

test("il passaggio con «meno movimento» va dritto a Natale; il tasto con la zucca lo interrompe", () => {
  const natale = natalino();
  const f = finto({ cerca: "?passaggio=1", ridotto: true, natale, sessione: {} });
  assert.strictEqual(f.h.passaggio(), null);
  assert.ok(!f.h.acceso());
  assert.deepStrictEqual(natale.chiamate, ["arriva"]);
  // Chiesto dallo script di `base.html` con la classe: un clic sulla zucca a metà scena chiude il passaggio.
  const g = finto({ classiIniziali: ["passaggio"], natale: natalino(), sessione: {} });
  assert.ok(g.h.passaggio());
  g.avanza(50);
  g.clic();
  assert.strictEqual(g.h.passaggio(), null);
  assert.ok(!g.h.acceso() && !g.classi.has("halloween") && !g.classi.has("passaggio"));
});

// --- natale.js sul sito: la stagione, l'arrivo, la scelta salvata ------------------------------
const NATALE = fs.readFileSync(path.join(__dirname, "..", "web", "static", "natale.js"), "utf8");
function nataleFinto({ memoria = {}, classiIniziali = [] } = {}) {
  const fotogrammi = [], classi = new Set(classiIniziali);
  const nulla = new Proxy({}, { get: (o, k) => (k === "createRadialGradient" || k === "createLinearGradient" ? () => ({ addColorStop() {} }) : () => {}), set: () => true });
  const tasto = { attr: {}, setAttribute(k, v) { this.attr[k] = v; } };
  const documento = {
    readyState: "complete", hidden: false, body: { appendChild() {} },
    documentElement: { getAttribute: () => "scuro", classList: { toggle: (c, si) => (si ? classi.add(c) : classi.delete(c)), contains: (c) => classi.has(c), add: (c) => classi.add(c), remove: (c) => classi.delete(c) } },
    querySelector: () => null, querySelectorAll: (sel) => (sel === "[data-natale-tasto]" ? [tasto] : []),
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

test("natale.js: stagione dal 2 novembre al 6 gennaio; arriva() accende senza salvare; spento in stagione si ricorda", () => {
  const { n } = nataleFinto();
  assert.strictEqual(n.stagione(2026, 11, 1), 0);
  assert.strictEqual(n.stagione(2026, 11, 2), 2026);
  assert.strictEqual(n.stagione(2026, 12, 31), 2026);
  assert.strictEqual(n.stagione(2027, 1, 6), 2026);
  assert.strictEqual(n.stagione(2027, 1, 7), 0);
  // Acceso o spento lo dice la classe messa da `base.html`.
  assert.ok(!n.acceso());
  assert.ok(nataleFinto({ classiIniziali: ["natale"] }).n.acceso());
  // arriva(): acceso, classe messa, niente in memoria; la neve e poi albero e pupazzi spuntano.
  const f = nataleFinto();
  f.n.arriva();
  assert.ok(f.n.acceso() && f.classi.has("natale"));
  assert.deepStrictEqual(f.memoria, {}, "il passaggio non salva la scelta");
  assert.strictEqual(f.n.stato().ingresso, 0);
  f.n.soffia(5, 120);
  f.avanza(100);
  assert.ok(f.n.stato().vento > 2, "la tormenta soffia: " + f.n.stato().vento);
  assert.ok(f.n.stato().fiocchi > 50);
  f.avanza(600);
  assert.strictEqual(f.n.stato().ingresso, 1, "l'arrivo finisce");
  // Il tasto: spento in stagione si ricorda con l'anno della stagione; riacceso torna di serie.
  const anno = new Date(), sn = n.stagione(anno.getFullYear(), anno.getMonth() + 1, anno.getDate());
  f.n.imposta(false);
  assert.strictEqual(f.memoria["mut-natale"], sn ? "off-" + sn : undefined);
  f.n.imposta(true);
  assert.strictEqual(f.memoria["mut-natale"], sn ? undefined : "on");
});

// --- Lo script in testa a `base.html`: decide le classi prima del primo disegno ----------------
const BASE = fs.readFileSync(path.join(__dirname, "..", "web", "templates", "base.html"), "utf8");
const TESTA = BASE.slice(BASE.indexOf("<script>(function(){") + 8, BASE.indexOf("</script>", BASE.indexOf("<script>(function(){")));
function testa({ data, memoria = {}, sessione = {}, cerca = "", ridotto = false }) {
  const classi = new Set(), attr = {};
  const VeraData = Date;
  function Finta() { return new VeraData(data[0], data[1] - 1, data[2], 12); }
  const ctx = {
    Date: Finta, location: { search: cerca },
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null) },
    sessionStorage: { getItem: (k) => (k in sessione ? sessione[k] : null) },
    matchMedia: (q) => ({ matches: ridotto && /reduce/.test(q) }), setTimeout() {},
    document: { documentElement: { classList: { add: (c) => classi.add(c), remove: (c) => classi.delete(c) }, setAttribute: (k, v) => { attr[k] = v; } } },
  };
  ctx.window = ctx;
  vm.runInNewContext(TESTA, ctx);
  return { classi: [...classi].sort().join(" "), tema: attr["data-tema"] };
}

test("base.html: Halloween fino al 1° novembre, poi il passaggio una volta per scheda, poi Natale fino al 6 gennaio", () => {
  assert.strictEqual(testa({ data: [2026, 10, 31] }).classi, "halloween");
  assert.strictEqual(testa({ data: [2026, 10, 31] }).tema, "scuro");
  assert.strictEqual(testa({ data: [2026, 11, 1] }).classi, "halloween");
  assert.strictEqual(testa({ data: [2026, 11, 2] }).classi, "halloween passaggio", "il 2 novembre parte il passaggio");
  assert.strictEqual(testa({ data: [2026, 11, 8] }).classi, "halloween passaggio");
  assert.strictEqual(testa({ data: [2026, 11, 2], sessione: { "mut-passaggio": "fatto" } }).classi, "natale", "già visto in questa scheda");
  assert.strictEqual(testa({ data: [2026, 11, 2], ridotto: true }).classi, "natale", "meno movimento: subito Natale");
  assert.strictEqual(testa({ data: [2026, 11, 9] }).classi, "natale");
  assert.strictEqual(testa({ data: [2026, 12, 25] }).classi, "natale");
  assert.strictEqual(testa({ data: [2027, 1, 6] }).classi, "natale");
  assert.strictEqual(testa({ data: [2027, 1, 7] }).classi, "");
  assert.strictEqual(testa({ data: [2026, 7, 1] }).classi, "");
  // Le scelte salvate.
  assert.strictEqual(testa({ data: [2026, 11, 3], memoria: { "mut-natale": "off-2026" } }).classi, "", "Natale spento in stagione: niente passaggio né Natale");
  assert.strictEqual(testa({ data: [2027, 1, 3], memoria: { "mut-natale": "off-2026" } }).classi, "", "la stagione 2026 finisce a gennaio 2027");
  assert.strictEqual(testa({ data: [2027, 11, 20], memoria: { "mut-natale": "off-2026" } }).classi, "natale", "l'anno dopo torna da solo");
  assert.strictEqual(testa({ data: [2026, 11, 3], memoria: { "mut-halloween": "off-2026" } }).classi, "natale", "chi ha spento Halloween non lo rivede andare via");
  assert.strictEqual(testa({ data: [2026, 7, 1], memoria: { "mut-natale": "on" } }).classi, "natale", "acceso a mano resta acceso");
  assert.strictEqual(testa({ data: [2026, 11, 3], memoria: { "mut-natale": "off" } }).classi, "halloween passaggio", "il vecchio «off» senza anno non blocca la stagione");
  assert.strictEqual(testa({ data: [2026, 11, 3], cerca: "?natale=0" }).classi, "");
  assert.strictEqual(testa({ data: [2026, 7, 1], cerca: "?passaggio=1" }).classi, "halloween passaggio");
  assert.strictEqual(testa({ data: [2026, 11, 3], memoria: { "mut-tema": "chiaro" } }).tema, "chiaro", "il tema scelto vince anche nel passaggio");
});
