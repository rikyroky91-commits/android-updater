/* Il velo di traduzione (static/lingue.js) senza browser: si carica lo
 * script in una sandbox e si prova la funzione che traduce un testo. */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SORGENTE = fs.readFileSync(path.join(__dirname, "..", "web", "static", "lingue.js"), "utf8");

function carica(memoria = {}) {
  const finestra = {
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null), setItem: (k, v) => { memoria[k] = String(v); } },
    addEventListener() {}, dispatchEvent() {},
  };
  const documento = {
    readyState: "loading", title: "", body: null,
    documentElement: { setAttribute() {}, classList: { add() {}, remove() {} } },
    addEventListener() {}, querySelectorAll: () => [],
  };
  const sandbox = { window: finestra, document: documento, WeakMap, Object, Number, Math, String, CustomEvent: function () {} };
  vm.createContext(sandbox);
  vm.runInContext(SORGENTE, sandbox);
  return finestra.__lingue;
}

test("le voci dell'interfaccia si traducono nelle quattro lingue", () => {
  const l = carica();
  assert.deepStrictEqual(Array.from(l.codici), ["it", "en", "es", "fr", "de"]);
  assert.strictEqual(l.traduci("Cerca", "en"), "Search");
  assert.strictEqual(l.traduci("Novità", "es"), "Novedades");
  assert.strictEqual(l.traduci("Parco di test", "fr"), "Parc de test");
  assert.strictEqual(l.traduci("Accedi", "de"), "Anmelden");
  assert.strictEqual(l.traduci("Cerca", "it"), null, "in italiano non si tocca niente");
});

test("spazi, faccine davanti e frecce in fondo restano dove sono", () => {
  const l = carica();
  assert.strictEqual(l.traduci("\n      Cerca  ", "en"), "\n      Search  ");
  assert.strictEqual(l.traduci("🕓 Recenti", "en"), "🕓 Recent");
  assert.strictEqual(l.traduci("Leggi →", "de"), "Lesen →");
  assert.strictEqual(l.traduci("✓ firmware verificato", "fr"), "✓ firmware vérifié");
});

test("le frasi con numeri: tempi, conteggi, esiti delle scommesse", () => {
  const l = carica();
  assert.strictEqual(l.traduci("4 mesi fa", "en"), "4 months ago");
  assert.strictEqual(l.traduci("1 ora fa", "en"), "1 hour ago");
  assert.strictEqual(l.traduci("· 2 anni fa", "es"), "· hace 2 años");
  assert.strictEqual(l.traduci("23 ore fa", "fr"), "il y a 23 heures");
  assert.strictEqual(l.traduci("3 giorni fa", "de"), "vor 3 Tagen");
  assert.strictEqual(l.traduci("1/1 fonti attive", "en"), "1/1 sources active");
  assert.strictEqual(l.traduci("Aggiornamenti di Galaxy A32", "en"), "Updates for Galaxy A32");
  assert.ok(/Staked 25 tokens on the robot \(×2\)/.test(l.traduci("Puntati 25 gettoni sul robot (×2): si decide al prossimo K.O.", "en")));
  assert.ok(/\+50/.test(l.traduci("Vinto! Ha vinto il robot: +50 gettoni.", "de")));
});

test("i dati non si toccano: nomi di modelli, build e testi sconosciuti restano come sono", () => {
  const l = carica();
  for (const dato of ["Galaxy S24 Ultra", "SM-S928B", "Android 14 · build S928BXXU1AXBC", "Xiaomi 12 EEA — Stable OS3.0.3.0.VLCEUXM", "frase mai vista"]) {
    assert.strictEqual(l.traduci(dato, "en"), null, dato);
  }
  assert.strictEqual(l.traduci("Controllo versione ufficiale (endpoint FOTA) · SM-A325F (ricerca diretta)", "en"),
    "Official version check (FOTA endpoint) · SM-A325F (direct lookup)");
});

test("ogni voce del dizionario ha quattro traduzioni non vuote", () => {
  const l = carica();
  for (const chiave of l.chiavi()) {
    for (const lingua of ["en", "es", "fr", "de"]) {
      const t = l.traduci(chiave, lingua);
      assert.ok(typeof t === "string" && t.trim().length > 0, chiave + " → " + lingua);
    }
  }
});
