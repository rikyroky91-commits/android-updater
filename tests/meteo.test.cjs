// Il meteo di Acireale sul sito (10/11/2026): dal codice del tempo di Open-Meteo alla scena, i
// casi senza rete, la scelta salvata e il tasto. `web/static/meteo.js` gira in un finto browser.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SORGENTE = fs.readFileSync(path.join(__dirname, "..", "web", "static", "meteo.js"), "utf8");

function finto({ memoria = {}, cerca = "", ridotto = false, risposta = null, rifiuta = false, scuro = false } = {}) {
  const fotogrammi = [], classi = new Set(), attributi = {}, chiamate = [], ascolta = {};
  const nulla = new Proxy({}, { get: (o, k) => (k === "createRadialGradient" || k === "createLinearGradient" ? () => ({ addColorStop() {} }) : () => {}), set: () => true });
  const tasto = { attr: { "aria-pressed": "true" }, setAttribute(k, v) { this.attr[k] = v; } };
  const documento = {
    readyState: "complete", hidden: false, body: { appendChild() {} },
    documentElement: { getAttribute: (k) => (k === "data-tema" ? (scuro ? "scuro" : "chiaro") : attributi[k] || null), setAttribute: (k, v) => { attributi[k] = v; }, classList: { contains: (c) => classi.has(c), add: (c) => classi.add(c) } },
    querySelector: () => null, querySelectorAll: (sel) => (sel === "[data-meteo-tasto]" ? [tasto] : []),
    createElement: () => ({ style: {}, setAttribute() {}, getContext: () => nulla }),
    addEventListener: (t, fn) => { (ascolta[t] = ascolta[t] || []).push(fn); },
  };
  const finestra = {
    innerWidth: 1280, innerHeight: 800, devicePixelRatio: 1, location: { search: cerca },
    localStorage: { getItem: (k) => (k in memoria ? memoria[k] : null), setItem: (k, v) => { memoria[k] = String(v); }, removeItem: (k) => { delete memoria[k]; } },
    matchMedia: (q) => ({ matches: ridotto && /reduce/.test(q) }),
    requestAnimationFrame: (fn) => { fotogrammi.push(fn); return fotogrammi.length; }, cancelAnimationFrame() {},
    addEventListener() {},
    fetch: (url) => { chiamate.push(url); return rifiuta ? Promise.reject(new Error("niente rete")) : Promise.resolve({ ok: true, json: () => Promise.resolve({ current: risposta }) }); },
  };
  finestra.window = finestra; finestra.document = documento;
  vm.runInNewContext(SORGENTE, Object.assign(finestra, { Math, Date, JSON, Promise, Error, Number, setTimeout, clearTimeout, setInterval: () => 0 }));
  return { m: finestra.__meteo, memoria, classi, attributi, tasto, chiamate, clic: () => (ascolta.click || []).forEach((fn) => fn({ target: { closest: (s) => (s === "[data-meteo-tasto]" ? tasto : null) } })) };
}
const attendi = () => new Promise((r) => setTimeout(r, 5));

test("dai codici del tempo alla scena: pioggia, temporale, neve, nebbia, sereno di giorno e di notte", () => {
  const { m } = finto({ cerca: "?meteo=sereno" });
  const c = (weather_code, extra = {}) => m.classifica(Object.assign({ weather_code, is_day: 1, cloud_cover: 50, wind_speed_10m: 5, temperature_2m: 15 }, extra));
  assert.strictEqual(c(0, { cloud_cover: 2 }).chiave, "sereno");
  assert.strictEqual(c(0, { cloud_cover: 2, is_day: 0 }).chiave, "notte");
  assert.strictEqual(c(2).chiave, "poco");
  assert.strictEqual(c(3, { cloud_cover: 70 }).chiave, "nuvoloso");
  assert.strictEqual(c(3, { cloud_cover: 100 }).chiave, "coperto");
  assert.strictEqual(c(45).chiave, "nebbia");
  assert.ok(c(48).nebbia > c(45).nebbia);
  assert.strictEqual(c(53).chiave, "pioggerella");
  assert.strictEqual(c(63).chiave, "pioggia");
  assert.ok(c(65).pioggia > c(63).pioggia && c(63).pioggia > c(53).pioggia, "più forte il codice, più fitta la pioggia");
  assert.strictEqual(c(81).chiave, "acquazzone");
  assert.ok(c(81).arcobaleno, "dopo l'acquazzone di giorno, l'arcobaleno");
  assert.ok(!c(81, { is_day: 0 }).arcobaleno);
  assert.strictEqual(c(73).chiave, "neve");
  assert.ok(c(73).neve > 0 && c(73).nuvole >= 0.8);
  const t = c(95);
  assert.strictEqual(t.chiave, "temporale");
  assert.ok(t.temporale && t.pioggia > 0.5 && t.nuvole >= 0.95);
  assert.ok(c(99).pioggia >= c(95).pioggia);
  // Senza copertura nuvolosa nel dato, la dice il codice.
  assert.ok(m.classifica({ weather_code: 3, is_day: 1 }).nuvole > 0.8);
  assert.ok(m.classifica({ weather_code: 0, is_day: 1 }).nuvole < 0.1);
});

test("il vento: da Ovest spinge a destra, e le foglie volano solo oltre i 22 km/h", () => {
  const f = finto({ cerca: "?meteo=vento" });
  f.m.avanza(5);
  const s = f.m.stato();
  assert.ok(s.scena.vento >= 22 && s.foglie > 0 && s.raffiche > 0, JSON.stringify(s));
  assert.strictEqual(f.attributi["data-meteo"], "poco");
  const calmo = finto({ cerca: "?meteo=sereno" });
  calmo.m.avanza(5);
  assert.strictEqual(calmo.m.stato().foglie, 0);
});

test("le scene di prova: la pioggia ha gocce, il temporale lampi, la nebbia banchi, la neve fiocchi, la notte stelle", () => {
  const scena = (nome) => { const f = finto({ cerca: "?meteo=" + nome }); f.m.avanza(10); return f.m.stato(); };
  assert.ok(scena("pioggia").gocce > 100);
  assert.ok(scena("pioggerella").gocce < scena("pioggia").gocce, "la pioggerella è meno fitta");
  assert.ok(scena("nebbia").banchi > 0);
  assert.ok(scena("neve").fiocchi > 50);
  assert.ok(scena("notte").stelle > 20);
  assert.strictEqual(scena("sereno").gocce, 0);
  const t = finto({ cerca: "?meteo=temporale" });
  let lampi = 0;
  for (let i = 0; i < 1500 && lampi === 0; i++) { t.m.avanza(1); if (t.m.stato().fulmine) lampi++; }
  assert.ok(lampi > 0, "in meno di 25 secondi c'è un fulmine");
  const lungo = finto({ cerca: "?meteo=temporale" });
  lungo.m.avanza(2000);
  assert.ok(lungo.m.stato().gocce > 100);
});

test("col tema di Natale la neve vera non si somma a quella di natale.js", () => {
  const f = finto({ cerca: "?meteo=neve" });
  f.classi.add("natale");
  f.m.applica({ weather_code: 73, is_day: 1, cloud_cover: 100 });
  assert.strictEqual(f.m.stato().fiocchi, 0);
});

test("la luna ha una fase vera: nuova il 6 gennaio 2000, piena due settimane dopo", () => {
  const { m } = finto({ cerca: "?meteo=sereno" });
  assert.ok(Math.min(m.etaLuna(new Date(Date.UTC(2000, 0, 6, 18, 14))), 1 - m.etaLuna(new Date(Date.UTC(2000, 0, 6, 18, 14)))) < 0.01);
  assert.ok(Math.abs(m.etaLuna(new Date(Date.UTC(2000, 0, 21, 4, 40))) - 0.5) < 0.03);
});

test("dalla rete: chiama Open-Meteo per Acireale, tiene il dato quindici minuti e lo mostra sul tasto", async () => {
  const f = finto({ risposta: { weather_code: 61, is_day: 1, cloud_cover: 90, wind_speed_10m: 12, temperature_2m: 14.4, wind_direction_10m: 270 } });
  await attendi();
  assert.strictEqual(f.chiamate.length, 1);
  assert.match(f.chiamate[0], /^https:\/\/api\.open-meteo\.com\/v1\/forecast\?latitude=37\.61&longitude=15\.16&/);
  assert.match(f.chiamate[0], /current=[^&]*weather_code/);
  assert.strictEqual(f.attributi["data-meteo"], "pioggia");
  assert.match(f.tasto.attr.title, /Acireale: pioggia, 14 °C/);
  assert.ok(f.memoria["mut-meteo-dati"], "dato salvato");
  // Un dato fresco evita la richiesta.
  const g = finto({ memoria: { "mut-meteo-dati": f.memoria["mut-meteo-dati"] }, risposta: null });
  await attendi();
  assert.strictEqual(g.chiamate.length, 0);
  assert.strictEqual(g.attributi["data-meteo"], "pioggia");
});

test("senza rete: dato vecchio ma sotto le tre ore sì, più vecchio no; mai un tempo inventato", async () => {
  const dato = { weather_code: 45, is_day: 1, cloud_cover: 80, wind_speed_10m: 3, temperature_2m: 9 };
  const recente = finto({ rifiuta: true, memoria: { "mut-meteo-dati": JSON.stringify({ t: Date.now() - 60 * 60 * 1000, dati: dato }) } });
  await attendi();
  assert.strictEqual(recente.attributi["data-meteo"], "nebbia");
  const antico = finto({ rifiuta: true, memoria: { "mut-meteo-dati": JSON.stringify({ t: Date.now() - 5 * 60 * 60 * 1000, dati: dato }) } });
  await attendi();
  assert.strictEqual(antico.attributi["data-meteo"], undefined);
  assert.strictEqual(antico.m.stato().scena, null);
  const nessuno = finto({ rifiuta: true });
  await attendi();
  assert.strictEqual(nessuno.m.stato().scena, null);
});

test("il tasto accende e spegne e ricorda la scelta; con «meno movimento» non si disegna niente", () => {
  const f = finto({ cerca: "?meteo=pioggia" });
  assert.ok(f.m.acceso());
  f.clic();
  assert.ok(!f.m.acceso());
  assert.strictEqual(f.memoria["mut-meteo"], "off");
  assert.strictEqual(f.tasto.attr["aria-pressed"], "false");
  f.clic();
  assert.ok(f.m.acceso());
  assert.ok(!("mut-meteo" in f.memoria));
  const spento = finto({ cerca: "?meteo=pioggia", memoria: { "mut-meteo": "off" } });
  assert.ok(!spento.m.acceso());
  spento.m.avanza(5);
  assert.strictEqual(spento.m.stato().passi, 0);
  assert.strictEqual(spento.m.stato().gocce, 0);
  const fermo = finto({ cerca: "?meteo=temporale", ridotto: true });
  fermo.m.avanza(10);
  assert.strictEqual(fermo.m.stato().passi, 0, "niente animazione");
});
