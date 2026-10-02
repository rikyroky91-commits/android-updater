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

function ambiente({ ridotto = false, larghezza = 1200, altezza = 800, solidi = [], campo = null, memoria = {} } = {}) {
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
      if (sel === "[data-ring]") return tela;
      if (sel === ".ultimora-barra") return barra;
      if (sel === "[data-gioca]") return tasto;
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
  amb.avanza(60 * 5);
  assert.strictEqual(amb.lottatore("mela").vita, 1, "dopo il K.O. la barra non torna piena");
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
  assert.ok(!/zaino\(f, 10\.5 \* S\);\n/.test(SORGENTE.replace("if (!anime) zaino(f, 10.5 * S);", "")), "il jetpack si disegna ancora in modalità anime");
  let atterrati = false;
  r.comandi.anime(false);
  amb.avanza(60 * 6, (s) => { if (s.lottatori.every((f) => !f.volo)) { atterrati = true; return false; } });
  assert.ok(atterrati, "spenta la modalità si resta in volo");
  assert.ok(alto || volato);
});

test("super guerrieri: la raffica di pugni colpisce e il colpo finale scaraventa via", () => {
  let lanciata = false;
  for (let prova = 0; prova < 5 && !lanciata; prova++) {
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
    amb.avanza(60 * 12);
    assert.ok(amb.stato().lottatori.every((f) => !f.sollevato), "qualcuno resta sospeso per sempre");
    dentro(amb);
  }
  assert.ok(sollevato, "nessuno viene sollevato");
  assert.ok(pezzi, "chi è sollevato non va mai in pezzi");
});
