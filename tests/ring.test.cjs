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
      // Un canvas vero rifiuta un arco col raggio negativo (o che non è un numero) e l'eccezione
      // ferma il disegno di tutta la pagina: qui deve succedere lo stesso, sennò non ce ne accorgiamo.
      if (nome === "arc") return (x, y, r) => { if (!(r >= 0) || !Number.isFinite(x + y + r)) throw new Error("arc(" + x + ", " + y + ", " + r + "): un canvas vero qui si ferma"); };
      if (nome === "ellipse") return (x, y, rx, ry) => { if (!(rx >= 0) || !(ry >= 0) || !Number.isFinite(x + y + rx + ry)) throw new Error("ellipse(" + [x, y, rx, ry].join(", ") + "): un canvas vero qui si ferma"); };
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
      // Un'eccezione sola, voluta: nel colpo finale «in orbita» chi lo prende esce dall'alto per un secondo.
      assert.ok((punto.y >= 0 || f.fatVola) && punto.x >= 0 && punto.x <= s.larghezza, "fuori dalla finestra");
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
  // Dal 05/10/2026 dopo un minuto e mezzo-due arriva l'orda, e durante la tregua non ci si afferra:
  // di ogni prova resta meno lotta vera, quindi le prove passano da quattro a sei.
  let preso = false;
  for (let prova = 0; prova < 6 && !preso; prova++) {
    const amb = ambiente();
    amb.finestra.__ring.tempo(60);
    amb.avanza(60 * 120, (s) => { if (s.lottatori.some((f) => f.tenuto)) { preso = true; return false; } });
    dentro(amb);
  }
  assert.ok(preso, "nessuna presa in sei prove da due minuti di lotta");
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
  assert.ok(amb.stato().pioggia > 0, "non piove");
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
  // (senza colpo finale in questi secondi: «in orbita» e «schiacciata» mandano in alto apposta)
  amb.avanza(60 * 8, () => { amb.finestra.__ring.roundFatale(false); });
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
        // «In piedi»: non a terra, non in mano a qualcuno, non in volo, non stordito, non nella scena di un colpo finale
        // (lì le pose sono recitate) né dentro il buco nero.
        if (f.inScena || f.fuoriCampo || f.schiacciato > 0) { fila[f.tipo] = 0; continue; }
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
  amb.avanza(150);
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
    assert.ok(dalLato > 0, "nessun oggetto è entrato da un lato");
    assert.ok(dallAlto > 0, "nessun oggetto è caduto dall'alto");
    assert.ok(inCampo > 60, "in campo, all'altezza dei lottatori, non arriva quasi niente");
    dentro(amb);
  }
});

// --- Le novità del 05/10/2026: imprevisti rifatti, lottatori senza gambe, scontro di energie, orda di zombie ---

test("la pioggia arriva in fondo anche con una testata larga quanto la finestra, e non toglie le scintille ai colpi", () => {
  // Il guasto: ogni goccia moriva sul primo elemento che incontrava. Sul sito il primo è la
  // testata, larga quanto la finestra e attaccata al tetto: le gocce duravano un fotogramma e
  // la pioggia, accesa, non si vedeva. In più contavano fra le particelle e ne riempivano l'elenco.
  for (const estensione of [false, true]) {
    const amb = ambiente({ estensione, solidi: [[0, 0, 1200, 64], [300, 500, 700, 540]], memoria: { "mut-ring": "on" } });
    amb.avanza(30);
    const c = amb.finestra.__ring.comandi;
    c.sorprese(false);
    assert.notStrictEqual(c.imprevisto("acquazzone", true), false);
    amb.avanza(60 * 4);
    let s = amb.stato();
    assert.ok(s.piovendo && s.pioggia > 150, "piove poco o niente: " + s.pioggia);
    assert.ok(s.pioggiaInFondo > 40, "le gocce non arrivano in fondo alla finestra: " + s.pioggiaInFondo);
    assert.ok(!s.particelleTipi.pioggia && s.particelle < 150, "la pioggia riempie ancora l'elenco delle particelle");
    assert.ok(s.bagnato > 0.5, "il pavimento non si bagna");
    // dopo un po' il temporale porta i fulmini
    let fulmini = 0;
    amb.avanza(60 * 30, (st) => { fulmini = Math.max(fulmini, st.fulmini); });
    assert.ok(fulmini > 0, "in mezzo minuto di pioggia nemmeno un fulmine");
    dentro(amb);
    c.imprevisto("acquazzone", false);
    amb.avanza(60 * 3);
    s = amb.stato();
    assert.ok(!s.piovendo && s.pioggia === 0, "ha smesso di piovere ma le gocce restano");
  }
});

test("il terremoto si sente e arriva con l'eruzione: scosse, vulcano, lapilli, poi tutto torna fermo", () => {
  // Prima era una spinta di un pixel e mezzo ogni sei fotogrammi, che i muscoli assorbivano.
  let caduti = 0;
  for (let giro = 0; giro < 3; giro++) {
    const amb = ambiente({ solidi: [[300, 500, 700, 540]] });
    amb.avanza(60);
    const r = amb.finestra.__ring, c = r.comandi;
    c.sorprese(false);
    assert.notStrictEqual(c.colpo("terremoto"), false);
    assert.ok(amb.stato().sisma, "il terremoto non parte");
    assert.ok(amb.classi.has("ring-trema"), "la pagina non trema");
    let alto = 0, lapilli = 0, colate = 0, tremato = false, fuoco = false, fuori = false;
    amb.avanza(60 * 11, (s) => {
      if (!s.sisma) return;
      alto = Math.max(alto, s.sisma.alto); lapilli = Math.max(lapilli, s.lapilli); colate = Math.max(colate, s.colate);
      if (s.lottatori.some((f) => f.trema)) tremato = true;
      if (s.lottatori.some((f) => f.ko > 0 || f.stordito > 0)) caduti++;
      if (s.particelleTipi.fuoco > 0) fuoco = true;
      for (const f of s.lottatori) if (!(f.bacino.y <= s.pavimento + 0.01) || !Number.isFinite(f.bacino.x)) fuori = true;
    });
    assert.ok(tremato, "le scosse non arrivano ai lottatori");
    assert.ok(alto > 0.99, "il vulcano non spunta: " + alto);
    assert.ok(lapilli > 0 && fuoco, "il vulcano non erutta");
    assert.ok(colate > 0, "i lapilli non lasciano pozze di lava");
    assert.ok(!fuori, "qualcuno è finito sotto il pavimento");
    amb.avanza(60 * 6);
    const s = amb.stato();
    assert.strictEqual(s.sisma, null, "il terremoto non finisce");
    assert.ok(!amb.classi.has("ring-trema"), "la pagina continua a tremare");
    assert.strictEqual(s.lapilli, 0);
    dentro(amb);
  }
  assert.ok(caduti > 0, "in tre terremoti nessuno ha perso l'equilibrio né si è scottato");
});

test("chi vola non sente le scosse", () => {
  const amb = ambiente();
  amb.avanza(60);
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false);
  r.tempo(70); r.decolla("robot", false);
  amb.avanza(40);
  r.comandi.colpo("terremoto");
  let inVolo = 0, tremaInVolo = 0;
  amb.avanza(100, (s) => { const f = s.lottatori.find((l) => l.tipo === "robot"); if (f.vola) { inVolo++; if (f.trema) tremaInVolo++; } });
  assert.ok(inVolo > 30, "il robot non vola abbastanza a lungo per la prova");
  assert.strictEqual(tremaInVolo, 0, "le scosse arrivano anche a chi vola");
});

test("i meteoriti cadono, si annunciano col mirino, scoppiano e lasciano il segno", () => {
  let sassi = 0, colpiti = 0;
  for (let giro = 0; giro < 3; giro++) {
    const amb = ambiente({ solidi: [[300, 500, 700, 540]] });
    amb.avanza(60);
    const r = amb.finestra.__ring, c = r.comandi;
    c.sorprese(false);
    const danni0 = amb.stato().lottatori.reduce((n, f) => n + f.danni, 0);
    assert.notStrictEqual(c.colpo("meteoriti"), false);
    assert.ok(amb.stato().sciame >= 9, "lo sciame non parte");
    let insieme = 0, grossa = false, bruciature = 0, male = false;
    amb.avanza(60 * 13, (s) => {
      insieme = Math.max(insieme, s.meteore.length); bruciature = Math.max(bruciature, s.bruciature);
      for (const m of s.meteore) {
        if (m.grossa) grossa = true;
        assert.ok(Number.isFinite(m.x) && Number.isFinite(m.y) && m.by <= s.pavimento + 0.5, "meteorite senza un posto dove cadere");
      }
      if (s.lottatori.some((f) => f.ko > 0) || s.lottatori.reduce((n, f) => n + f.danni, 0) > danni0) male = true;
    });
    const s = amb.stato();
    assert.ok(insieme >= 1 && grossa, "non cade niente, o manca il meteorite grosso");
    assert.ok(bruciature >= 3, "gli impatti non lasciano il segno: " + bruciature);
    assert.strictEqual(s.sciame, 0); assert.strictEqual(s.meteore.length, 0);
    if (s.telefoni.some((t) => t.tipo === "sasso")) sassi++;
    if (male) colpiti++;
    dentro(amb);
  }
  assert.ok(colpiti > 0, "tre sciami e mai nessuno colpito o sbalzato");
});

// Quanto sta alto il collo di chi è in piedi: la mediana di un secondo, perché
// un fotogramma solo può cadere su un salto (collo più su) o su una caduta.
function altezzaInPiedi(amb, tipo) {
  const campioni = [];
  amb.avanza(60, (s) => { const f = s.lottatori.find((l) => l.tipo === tipo); if (!f.ko && !f.vola && !f.inVolo) campioni.push(f.base - f.collo.y); });
  campioni.sort((a, b) => a - b);
  return campioni.length ? campioni[Math.floor(campioni.length / 2)] : 46 * amb.stato().scala;
}

test("senza gambe ci si trascina sulle mani o si vola; con una gamba sola si resta in piedi; tornate le gambe ci si rialza", () => {
  // Prima chi perdeva le gambe restava ritto a mezz'aria, sulle gambe che non si vedevano più.
  for (const stile of ["", "lame"]) {
    let colpiDaTerra = 0, bassoTot = 0, nTot = 0;
    for (let giro = 0; giro < 3 && !colpiDaTerra; giro++) {
      const amb = ambiente({ memoria: stile ? { "mut-ring-stile": stile } : {} });
      const r = amb.finestra.__ring;
      r.comandi.sorprese(false);
      const alto = altezzaInPiedi(amb, "robot");
      assert.ok(alto > 40 * amb.stato().scala, "in piedi il collo dovrebbe stare in alto: " + alto);
      r.stacca("robot", ["gA", "gD"], "striscia");
      let punti = amb.stato().punteggio.robot, danni = amb.lottatore("mela").danni;
      amb.avanza(60 * 25, (s) => {
        const f = s.lottatori.find((l) => l.tipo === "robot"), m = s.lottatori.find((l) => l.tipo === "mela");
        assert.strictEqual(f.gambe, 0);
        if (!f.ko && !f.vola && !f.inVolo && f.forza >= 1) { nTot++; if (f.base - f.collo.y < alto * 0.6) bassoTot++; }
        if (s.punteggio.robot > punti || m.danni > danni) { if (f.striscia) colpiDaTerra++; }
        punti = s.punteggio.robot; danni = m.danni;
      });
      dentro(amb);
      // tornate le gambe, in un paio di secondi è di nuovo in piedi
      r.riattacca("robot");
      let ritto = false;
      amb.avanza(60 * 6, (s) => { const f = s.lottatori.find((l) => l.tipo === "robot"); if (!f.ko && !f.vola && f.forza >= 1 && f.base - f.collo.y > alto * 0.8) ritto = true; });
      assert.ok(ritto, "riavute le gambe non si rialza");
    }
    assert.ok(nTot > 200 && bassoTot / nTot > 0.7, "senza gambe non sta per terra (" + stile + "): " + bassoTot + "/" + nTot);
    assert.ok(colpiDaTerra > 0, "da terra non riesce mai a colpire (" + stile + ")");
  }
  // in volo
  const amb = ambiente();
  amb.avanza(60);
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false);
  r.stacca("mela", ["gA", "gD"], "vola");
  let vola = false;
  amb.avanza(60 * 3, (s) => { if (s.lottatori.find((l) => l.tipo === "mela").vola) vola = true; });
  assert.ok(vola, "senza gambe, col piano di volare, non decolla");
  // una gamba sola: in piedi, saltellando
  const una = ambiente();
  una.finestra.__ring.comandi.sorprese(false);
  const alto = altezzaInPiedi(una, "robot");
  una.finestra.__ring.stacca("robot", ["gA"]);
  // (un salto o un calcio già partiti quando la gamba si stacca finiscono: contano quelli cominciati dopo)
  let su = 0, n = 0, calci = 0, inCorso = true;
  una.avanza(60 * 15, (s) => {
    const f = s.lottatori.find((l) => l.tipo === "robot");
    assert.strictEqual(f.gambe, 1);
    if (f.azione !== "calcio" && f.azione !== "salto") inCorso = false;
    else if (!inCorso) calci++;
    if (!f.ko && !f.vola && !f.inVolo && f.forza >= 1 && !f.scalando) { n++; if (f.base - f.collo.y > alto * 0.75) su++; }
  });
  assert.ok(n > 100 && su / n > 0.7, "con una gamba sola non resta in piedi: " + su + "/" + n);
  assert.strictEqual(calci, 0, "con una gamba sola non si tirano calci né si salta");
  dentro(una);
});

test("senza braccia niente pugni: calci e testate", () => {
  const amb = ambiente();
  amb.avanza(60);
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false);
  r.stacca("robot", ["A", "D"]);
  const viste = {};
  amb.avanza(60 * 40, (s) => { const f = s.lottatori.find((l) => l.tipo === "robot"); if (f.azione) viste[f.azione] = true; });
  for (const no of ["pugno", "diretto", "montante", "presa", "para"]) assert.ok(!viste[no], "senza braccia ha fatto: " + no);
  assert.ok(viste.testata || viste.calcio, "senza braccia non attacca più");
  dentro(amb);
});

// Fa partire lo scontro a comando e aspetta che finisca: restituisce com'è andata (o null).
function scontro(prepara, durante) {
  const amb = ambiente({ memoria: { "mut-ring-stile": "guerrieri" } });
  amb.avanza(40);
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false);
  if (prepara(r, amb) === false) return null;
  r.comandi.colpo("scontro");
  let partito = false, max = null, danni = null;
  amb.avanza(60 * 14, (s) => {
    if (s.sfida) {
      if (!partito) danni = s.lottatori.map((f) => f.danni);
      partito = true; max = s.sfida;
      if (durante) durante(r, s);
    } else if (partito) return false;
  });
  const s = amb.stato();
  if (!partito || s.sfida || !s.ultimaSfida) return null;
  dentro(amb);
  return Object.assign({ fiatoInizio: max, danniPrima: danni, stato: s }, s.ultimaSfida);
}
// Riprova se uno dei due ha mollato per un colpo arrivato da fuori (un telefono in testa).
function scontroPulito(prepara, durante) {
  for (let i = 0; i < 6; i++) { const e = scontro(prepara, durante); if (e && e.come !== "molla") return e; }
  assert.fail("lo scontro di energie non parte, o finisce sempre perché uno molla");
}

test("scontro di energie: a parità di spinta vince chi ha più energia, e chi perde paga", () => {
  for (const [robot, mela, atteso] of [[100, 50, "robot"], [50, 100, "mela"]]) {
    const e = scontroPulito((r) => { r.energia("robot", robot); r.energia("mela", mela); });
    assert.strictEqual(e.tipo, "onda");
    assert.strictEqual(e.vince, atteso, "con " + robot + " contro " + mela + " ha vinto " + e.vince + " (" + e.come + ")");
    assert.ok(e.strattoni[atteso === "robot" ? 0 : 1] > e.strattoni[atteso === "robot" ? 1 : 0], "chi ha più fiato non ha dato più strattoni");
    // chi perde prende il colpo (uno, o due se travolto, o va K.O.), chi vince niente
    const perde = e.stato.lottatori.find((f) => f.tipo !== atteso), i = e.stato.lottatori.indexOf(perde);
    const vince = e.stato.lottatori.find((f) => f.tipo === atteso), j = e.stato.lottatori.indexOf(vince);
    assert.ok(perde.danni > e.danniPrima[i] || e.stato.punteggio[atteso] > 0 || perde.ko > 0, "chi ha perso non ha pagato");
    assert.strictEqual(vince.danni, e.danniPrima[j], "chi ha vinto si è fatto male");
  }
});

test("scontro di energie: a parità di energia vince chi spinge di più (il trasformato), anche se risponde", () => {
  for (const forte of ["robot", "mela"]) {
    const e = scontroPulito((r, amb) => {
      r.mossa(forte, "trasforma");
      let fatto = false;
      amb.avanza(60 * 4, (s) => { if (s.lottatori.find((f) => f.tipo === forte).potenziato) { fatto = true; return false; } });
      if (!fatto) return false;
      amb.avanza(60);
      assert.ok(Math.abs(r.spinta(forte) / r.spinta(forte === "robot" ? "mela" : "robot") - 1.3) < 0.31, "la spinta del trasformato non è quella delle regole");
      r.energia("robot", 80); r.energia("mela", 80);
    });
    assert.strictEqual(e.vince, forte, "a pari energia ha vinto il più debole (" + e.come + ", u=" + e.u.toFixed(2) + ")");
  }
});

test("scontro di energie: il tifo conta, e le regole danno sempre lo stesso esito", () => {
  // Stessa energia, stessa spinta: senza tifo finisce sempre allo stesso modo...
  const esiti = new Set();
  for (let i = 0; i < 3; i++) { const e = scontroPulito((r) => { r.energia("robot", 70); r.energia("mela", 70); }); esiti.add(String(e.vince)); }
  assert.strictEqual(esiti.size, 1, "a parità di tutto l'esito cambia da una volta all'altra: " + Array.from(esiti).join(", "));
  // ...ma col pubblico che tifa per la mela vince lei, anche partendo con meno energia.
  const e = scontroPulito((r) => { r.energia("robot", 80); r.energia("mela", 60); }, (r, s) => { if (s.sfida.t % 6 === 0) assert.ok(r.tifa("mela"), "il tifo non arriva"); });
  assert.strictEqual(e.vince, "mela", "col tifo non è cambiato niente");
  assert.ok(e.tifo[1] > 10 && e.tifo[0] === 0);
});

test("quando uno carica un colpo d'energia l'altro prova a caricare lo stesso, e i due colpi si scontrano", () => {
  for (const [stile, mossa] of [["guerrieri", "onda"], ["maghi", "onda"], ["guerrieri", "sfera"]]) {
    // La risposta è una scelta col caso dentro (dal 74% in su, se è in condizione di
    // rispondere): si contano parecchie prove e si chiede che non sia un'eccezione.
    let prove = 0, risposte = 0, scontri = 0;
    for (let giro = 0; giro < 24; giro++) {
      const amb = ambiente({ memoria: { "mut-ring-stile": stile } });
      amb.avanza(40);
      const r = amb.finestra.__ring;
      r.comandi.sorprese(false);
      const prima = amb.stato().lottatori;
      if (prima.some((f) => f.ko || f.vola || f.stordito) || Math.abs(prima[0].bacino.x - prima[1].bacino.x) < 110 * amb.stato().scala) continue;
      r.energia("mela", 90);
      if (!r.mossa("robot", mossa)) continue;
      prove++;
      let risposto = false, scontro = false;
      amb.avanza(mossa === "sfera" ? 60 * 6 : 60 * 2, (s) => {
        const m = s.lottatori.find((f) => f.tipo === "mela");
        if (m.azione === mossa && m.risposta) risposto = true;
        if (s.sfida) scontro = true;
      });
      if (risposto) risposte++;
      if (scontro) scontri++;
      dentro(amb);
    }
    assert.ok(prove >= 12, "troppo poche prove valide: " + prove);
    assert.ok(risposte >= prove * 0.35, stile + "/" + mossa + ": l'altro risponde troppo di rado: " + risposte + "/" + prove);
    assert.ok(scontri >= risposte * 0.6, stile + "/" + mossa + ": i due colpi non si scontrano: " + scontri + "/" + risposte);
  }
});

test("colpi uguali che si incontrano a mezz'aria si annullano", () => {
  let annullati = 0;
  for (let giro = 0; giro < 6 && !annullati; giro++) {
    const amb = ambiente({ memoria: { "mut-ring-stile": "guerrieri" } });
    amb.avanza(40);
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false);
    r.energia("mela", 90);
    r.mossa("robot", "raffica"); r.mossa("mela", "raffica");
    let max = 0, scesi = false;
    amb.avanza(90, (s) => { if (s.proiettili < max - 1) scesi = true; max = Math.max(max, s.proiettili); if (s.lottatori.some((f) => f.danni > 0)) return; });
    const s = amb.stato();
    // tutte e due le raffiche partite e nessuno colpito: si sono mangiate a vicenda
    if (max >= 4 && scesi && s.lottatori.every((f) => f.danni === 0 && !f.ko)) annullati++;
  }
  assert.ok(annullati > 0, "due raffiche una contro l'altra arrivano sempre a segno");
});

test("orda di zombie: tregua, spalle a spalla, ci si copre; finita l'orda si ricomincia", () => {
  for (const stile of ["", "guerrieri"]) {
    const amb = ambiente({ memoria: stile ? { "mut-ring-stile": stile } : {} });
    amb.avanza(60);
    const r = amb.finestra.__ring, c = r.comandi;
    c.sorprese(false);
    const punti = JSON.stringify(amb.stato().punteggio);
    r.orda(2, 7 + stile.length);                       // due ondate, come quando arriva a sorpresa (lì sono tre)
    assert.ok(amb.stato().orda, "l'orda non parte");
    // durante la tregua un colpo dell'uno non fa niente all'altro
    assert.strictEqual(r.colpo("robot", "mela"), 0, "durante la tregua i due si fanno ancora male");
    assert.strictEqual(r.colpo("mela", "robot"), 0);
    let lotta = 0, spalle = 0, insieme = 0, uccisi = 0, festa = false, aTerra = 0, inCoppia = 0;
    amb.avanza(60 * 90, (s) => {
      if (!s.orda) return false;
      if (s.orda.fase === "festa") { festa = true; return; }
      if (s.orda.fase !== "lotta") return;
      lotta++; uccisi = s.orda.uccisi;
      insieme = Math.max(insieme, s.orda.zombie.filter((z) => z.stato !== "giu").length);
      const [x, y] = s.lottatori, sin = x.cx <= y.cx ? x : y, des = sin === x ? y : x;
      if (x.ko || y.ko) aTerra++;
      else if (x.coppia || y.coppia) inCoppia++;                 // una mossa in coppia: stanno collaborando lo stesso
      else if (Math.abs(x.cx - y.cx) < 56 * s.scala && sin.dir === -1 && des.dir === 1) spalle++;
      for (const z of s.orda.zombie) assert.ok(Number.isFinite(z.x) && z.x >= 0 && z.x <= s.larghezza, "zombie fuori dalla finestra");
    });
    const s = amb.stato();
    assert.strictEqual(s.orda, null, "l'orda non finisce mai");
    assert.ok(festa, "finita l'orda non si festeggia");
    // I guerrieri li abbattono a raffiche appena spuntano: in piedi nello stesso momento ne restano meno.
    assert.ok(insieme >= (stile ? 2 : 3), "arrivano troppo pochi zombie insieme: " + insieme);
    assert.ok(uccisi >= 8, "ne abbattono troppo pochi: " + uccisi);
    // Con le mosse in coppia (05/10/2026) la formazione si rompe e si rifà di continuo: misurato su 40 orde,
    // spalle a spalla o in una mossa in coppia per il 66% del tempo in mediana, mai sotto il 35%.
    assert.ok(spalle + inCoppia > (lotta - aTerra) * 0.25, "non stanno quasi mai spalle a spalla: " + spalle + "+" + inCoppia + "/" + (lotta - aTerra));
    assert.ok(spalle > (lotta - aTerra) * 0.12, "spalle a spalla non ci stanno più: " + spalle + "/" + (lotta - aTerra));
    assert.strictEqual(JSON.stringify(s.punteggio), punti, "i morsi degli zombie hanno cambiato il punteggio della partita");
    dentro(amb);
    // finita la tregua i colpi tornano a contare
    amb.avanza(30);
    let conta = 0;
    for (let i = 0; i < 8 && !conta; i++) { conta = r.colpo("robot", "mela"); amb.avanza(20); }
    assert.ok(conta > 0, "finita l'orda i due non si fanno più male");
  }
});

test("l'alleato a terra viene coperto e aiutato a rialzarsi", () => {
  let aiutati = 0;
  for (let giro = 0; giro < 6 && !aiutati; giro++) {
    const amb = ambiente();
    amb.avanza(60);
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false);
    r.orda(0, 11 + giro);
    // il tempo di mettersi spalle a spalla
    amb.avanza(60 * 3);
    const [x0, y0] = amb.stato().lottatori;
    if (x0.ko || y0.ko || Math.abs(x0.cx - y0.cx) > 60 * amb.stato().scala) continue;
    // la mela va al tappeto: da sola ci resterebbe almeno 110 fotogrammi
    r.ko("mela");
    assert.ok(amb.lottatore("mela").ko >= 110);
    let vicino = 0, n = 0, durata = 0;
    amb.avanza(60 * 8, (s) => {
      const m = s.lottatori.find((f) => f.tipo === "mela"), rb = s.lottatori.find((f) => f.tipo === "robot");
      if (!s.orda || s.orda.fase !== "lotta" || !(m.ko > 0)) return false;
      durata++;
      if (!rb.ko) { n++; if (Math.abs(rb.cx - m.bacino.x) < 70 * s.scala) vicino++; }
    });
    if (n > 10 && vicino / n > 0.5 && durata < 100) aiutati++;
    dentro(amb);
  }
  assert.ok(aiutati > 0, "con l'alleato a terra l'altro non gli resta accanto, o non lo aiuta a rialzarsi prima");
});

test("Premium: meteoriti e orda stanno col meteo, il terremoto con l'eruzione resta libero", () => {
  const chieste = [];
  const premio = { bloccate: { guerrieri: true, armi: true, meteo: true }, attivo: () => false, chiedi: (g) => chieste.push(g) };
  const amb = ambiente({ premio, estensione: true, memoria: { "mut-ring": "on" } });
  amb.avanza(30);
  const c = amb.finestra.__ring.comandi;
  assert.strictEqual(c.colpo("meteoriti"), false);
  assert.strictEqual(c.colpo("zombie"), false);
  assert.strictEqual(c.colpo("scontro"), false);
  assert.deepStrictEqual(chieste, ["meteo", "meteo", "guerrieri"]);
  let s = amb.stato();
  assert.ok(!s.sciame && !s.orda && !s.sfida);
  assert.notStrictEqual(c.colpo("terremoto"), false);
  assert.ok(amb.stato().sisma, "il terremoto, che è gratis, non parte");
  // e a sorpresa, senza Premium, non arrivano né sciami né orde né temporali
  amb.finestra.__ring.tempo(61);
  amb.avanza(60 * 240, (st) => { assert.ok(!st.sciame && !st.orda && !st.piovendo, "imprevisto a pagamento arrivato a sorpresa senza Premium"); });
  dentro(amb);
});

test("l'orda arriva a ondate generate: stesso seme stessa ondata, semi diversi ondate diverse, e crescono", () => {
  const amb = ambiente();
  amb.avanza(30);
  const r = amb.finestra.__ring;
  const tipi = new Set(), temi = new Set(), arrivi = new Set();
  for (const seme of [1, 2, 3, 99]) {
    let prima = 0;
    for (let n = 1; n <= 12; n++) {
      const a = r.ricettaOndata(n, seme), b = r.ricettaOndata(n, seme);
      assert.deepStrictEqual(a, b, "lo stesso seme deve dare la stessa ondata");
      assert.ok(a.coda.length >= 3 && a.coda.length <= 34, "ondata " + n + " di " + a.coda.length);
      assert.ok(a.insieme >= 5 && a.insieme <= 10);
      if (n === 1) { prima = a.coda.length; assert.ok(a.coda.every((v) => /^(lento|svelto)/.test(v)), "alla prima ondata arrivano già i tipi difficili: " + a.coda); }
      if (n === 12) assert.ok(a.coda.length > prima, "le ondate non crescono");
      temi.add(a.tema); arrivi.add(a.arrivo);
      for (const v of a.coda) tipi.add(v.replace(/[<>].*/, ""));
    }
  }
  assert.notDeepStrictEqual(r.ricettaOndata(5, 1), r.ricettaOndata(5, 2), "semi diversi danno la stessa ondata");
  assert.ok(tipi.size >= 5, "pochi tipi di zombie: " + [...tipi]);
  assert.ok(temi.size >= 3 && arrivi.size >= 3, "ondate tutte uguali: " + [...temi] + " / " + [...arrivi]);
});

test("ondate: fra una e l'altra c'è una pausa, il conto sale, a comando non finiscono e il primato resta", () => {
  const memoria = {};
  const amb = ambiente({ memoria });
  amb.avanza(60);
  const r = amb.finestra.__ring, c = r.comandi;
  c.sorprese(false);
  c.anime(true);                                     // i super guerrieri reggono qualche ondata
  amb.avanza(30);
  assert.notStrictEqual(c.colpo("zombie"), false);
  let s = amb.stato();
  assert.ok(s.orda && s.orda.ondate === 0, "dalla tendina l'orda deve essere senza fine");
  assert.ok(s.orda.ondata <= 1);
  let pause = 0, massima = 1, tipi = new Set(), prima = "lotta";
  amb.avanza(60 * 150, (st) => {
    if (!st.orda || st.orda.fase === "festa") return false;
    if (st.orda.fase === "pausa" && prima !== "pausa") pause++;
    prima = st.orda.fase;
    massima = Math.max(massima, st.orda.ondata);
    for (const z of st.orda.zombie) tipi.add(z.tipo);
    if (st.orda.superate >= 3) return false;
  });
  s = amb.stato();
  assert.ok(massima >= 2 && pause >= 1, "non si arriva mai alla seconda ondata: " + massima + " (pause " + pause + ")");
  assert.ok(s.primatoOrda >= 1 && memoria["mut-ring-ondate"] === String(s.primatoOrda), "il primato delle ondate non resta: " + s.primatoOrda + " / " + memoria["mut-ring-ondate"]);
  // un altro clic sullo stesso tasto la chiude
  if (s.orda && s.orda.fase !== "festa") { c.colpo("zombie"); assert.strictEqual(amb.stato().orda.fase, "festa"); }
  amb.avanza(60 * 6);
  assert.strictEqual(amb.stato().orda, null, "chiusa a mano, l'orda non se ne va");
  dentro(amb);
});

test("controller ad angolo: sta nell'angolo in basso a destra, comanda il personaggio scelto e lo cambia", () => {
  const memoria = {};
  const amb = ambiente({ memoria });
  amb.avanza(60);
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false);
  let s = amb.stato();
  assert.strictEqual(s.radiale.aperto, false, "il controller parte chiuso");
  // chiuso, un clic nell'angolo non è suo
  let e = amb.premi(s.larghezza - 20, amb.pavimento - 20); amb.rilascia(0, 0);
  assert.ok(!e.bloccato);
  r.radiale(true);
  assert.strictEqual(memoria["mut-ring-radiale"], "on");
  amb.avanza(40);
  s = amb.stato();
  const g = s.radiale;
  assert.strictEqual(g.x, s.larghezza, "non è attaccato al bordo destro");
  assert.strictEqual(g.y, amb.pavimento, "non è appoggiato in basso");
  assert.strictEqual(g.spicchi.length, 8);
  // un quarto di giro e basta: tutti gli spicchi stanno dentro l'angolo
  for (const q of g.spicchi) assert.ok(q.x < g.x && q.y < g.y && q.x > g.x - g.largo && q.y > g.y - g.largo, "spicchio fuori dall'angolo");
  assert.strictEqual(g.voci.join(), "pugno,calcio,montante,presa,para,salto,jet,lancia");
  // un clic su uno spicchio: il robot (è lui il primo che si comanda) fa quella mossa, e il clic non passa alla pagina
  let fatto = false;
  for (let giro = 0; giro < 20 && !fatto; giro++) {
    amb.avanza(50);
    const st = amb.stato(), para = st.radiale.voci.indexOf("para");
    if (!st.radiale.accese[para]) continue;
    e = amb.premi(g.spicchi[para].x, g.spicchi[para].y); amb.rilascia(0, 0);
    assert.ok(e.bloccato, "il clic sul controller arriva alla pagina");
    assert.strictEqual(amb.lottatore("robot").azione, "para");
    fatto = true;
  }
  assert.ok(fatto, "il robot non è mai stato in grado di parare");
  // una mossa da vicino chiesta da lontano: prima ci va, poi colpisce
  let arrivato = false;
  for (let giro = 0; giro < 12 && !arrivato; giro++) {
    r.sposta("robot", 200); r.sposta("mela", 900);
    amb.avanza(30);
    if (!r.ordina("robot", "pugno")) continue;
    assert.strictEqual(amb.lottatore("robot").ordine, "pugno", "da lontano il pugno deve restare in sospeso");
    amb.avanza(260, (st) => { const f = st.lottatori.find((l) => l.tipo === "robot"); if (f.azione === "pugno") { arrivato = Math.abs(f.cx - st.lottatori.find((l) => l.tipo === "mela").cx) < 70 * st.scala; return false; } });
  }
  assert.ok(arrivato, "chiesto da lontano, il pugno non arriva mai a segno");
  // il ritratto nell'angolo: un clic e si comanda l'altro
  e = amb.premi(g.x - 15, g.y - 15); amb.rilascia(g.x - 15, g.y - 15);
  assert.ok(e.bloccato);
  assert.strictEqual(amb.stato().radiale.chi, "mela");
  // trascinato oltre metà finestra passa nell'angolo di sinistra
  amb.premi(g.x - 15, g.y - 15); amb.muovi(g.x - 200, g.y - 40); amb.muovi(100, g.y - 40); amb.rilascia(100, g.y - 40);
  s = amb.stato();
  assert.strictEqual(s.radiale.lato, "sx"); assert.strictEqual(s.radiale.x, 0); assert.strictEqual(s.radiale.chi, "mela");
  for (const q of s.radiale.spicchi) assert.ok(q.x > 0 && q.x < s.radiale.largo && q.y < s.radiale.y);
  r.radiale(false);
  assert.strictEqual(memoria["mut-ring-radiale"], "off");
  dentro(amb);
});

test("controller: le mosse sono quelle dei personaggi scelti, quelle a energia si spengono se l'energia non basta", () => {
  // Ci sono tutte le mosse della tendina: la presa a distanza, il lampo e l'autodistruzione
  // dei guerrieri, la sparizione dei maghi, l'incrocio di lame dei duellanti.
  const attese = { guerrieri: 12, maghi: 9, lame: 9 }, devono = { guerrieri: ["telecinesi", "lampo", "avvinghia"], maghi: ["teletrasporto"], lame: ["duello"] };
  for (const stile of Object.keys(attese)) {
    const amb = ambiente({ memoria: { "mut-ring-stile": stile, "mut-ring-radiale": "on" } });
    amb.avanza(60);
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false);
    let s = amb.stato();
    assert.strictEqual(s.radiale.aperto, true, "il controller non si ricorda di essere aperto");
    assert.strictEqual(s.radiale.voci.length, attese[stile], stile);
    for (const id of devono[stile]) assert.ok(s.radiale.voci.indexOf(id) >= 0, stile + ": nel controller manca " + id);
    assert.strictEqual(s.radiale.spicchi.filter((q) => q.giro === 1).length, Math.ceil(attese[stile] * 0.58));
    // tutti dentro l'angolo, nessuno sopra un altro
    for (const q of s.radiale.spicchi) assert.ok(q.x < s.radiale.x && q.y < s.radiale.y && q.x > s.radiale.x - s.radiale.largo && q.y > s.radiale.y - s.radiale.largo, "spicchio fuori dall'angolo");
    for (let i = 0; i < s.radiale.spicchi.length; i++) for (let j = 0; j < i; j++) {
      const a = s.radiale.spicchi[i], b = s.radiale.spicchi[j];
      assert.ok(Math.hypot(a.x - b.x, a.y - b.y) > 24 * s.scala, stile + ": due spicchi troppo vicini per cliccarli");
    }
    if (stile === "lame") continue;
    const onda = s.radiale.voci.indexOf("onda");
    let provato = false;
    for (let giro = 0; giro < 20 && !provato; giro++) {
      r.sposta("robot", 300); r.sposta("mela", 800);
      amb.avanza(40);
      const f = amb.lottatore("robot");
      if (f.ko || f.azione === "onda" || amb.stato().sfida) continue;
      r.energia("robot", 0);
      assert.strictEqual(amb.stato().radiale.accese[onda], false, stile + ": senza energia l'onda deve restare spenta");
      assert.strictEqual(r.ordina("robot", "onda"), false);
      r.energia("robot", 100);
      if (!amb.stato().radiale.accese[onda]) continue;
      const q = amb.stato().radiale.spicchi[onda];
      amb.premi(q.x, q.y); amb.rilascia(0, 0);
      assert.strictEqual(amb.lottatore("robot").azione, "onda", stile + ": con l'energia piena l'onda non parte");
      provato = true;
    }
    assert.ok(provato, stile + ": non si è mai potuta provare l'onda");
    amb.avanza(400);
    dentro(amb);
  }
});

test("controller durante l'orda: i comandi valgono contro gli zombie, mai contro l'alleato", () => {
  const amb = ambiente();
  amb.avanza(60);
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false);
  r.radiale(true);
  r.orda(0, 5);
  amb.avanza(60 * 4);
  let colpi = 0;
  for (let giro = 0; giro < 30; giro++) {
    amb.avanza(25);
    const s = amb.stato();
    if (!s.orda || s.orda.fase !== "lotta") break;
    assert.strictEqual(s.radiale.voci.indexOf("presa"), -1, "durante la tregua la presa (che è sull'alleato) non va offerta");
    assert.ok(s.radiale.voci.indexOf("cavallina") >= 0, "durante la tregua il controller deve offrire le mosse in coppia");
    if (r.ordina("robot", "pugno")) colpi++;
    assert.strictEqual(r.colpo("robot", "mela"), 0, "comandato a mano, il robot fa male all'alleato");
  }
  assert.ok(colpi > 0, "durante l'orda il controller non comanda mai");
  dentro(amb);
});

test("controller: la presa a distanza c'è e afferra l'altro da lontano; durante la tregua resta spenta", () => {
  let presi = 0, prove = 0;
  for (let giro = 0; giro < 10 && presi < 2; giro++) {
    const amb = ambiente({ memoria: { "mut-ring-stile": "guerrieri" } });
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false);
    amb.avanza(60);
    r.sposta("robot", 300); r.sposta("mela", 800); r.energia("robot", 100);
    amb.avanza(3);
    const g = amb.stato().radiale, k = g.voci.indexOf("telecinesi");
    if (!g.accese[k]) continue;
    r.radiale(true); amb.avanza(30);
    const q = amb.stato().radiale.spicchi[k];
    amb.premi(q.x, q.y); amb.rilascia(0, 0);
    if (amb.lottatore("robot").azione !== "telecinesi") continue;
    prove++;
    let preso = false;
    amb.avanza(150, (s) => { if (s.lottatori.find((f) => f.tipo === "mela").tenuto) { preso = true; return false; } });
    if (preso) presi++;
    amb.avanza(300); dentro(amb);
  }
  assert.ok(prove >= 2, "la presa a distanza dal controller non parte: " + prove);
  assert.ok(presi >= 1, "la presa a distanza non afferra mai: " + presi + "/" + prove);
  // senza energia è spenta; durante l'orda sparisce (è una mossa sull'altro, che ora è un alleato) e al suo posto ci sono le mosse in coppia
  const amb = ambiente({ memoria: { "mut-ring-stile": "guerrieri" } });
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false); amb.avanza(60);
  r.energia("robot", 10);
  let s = amb.stato();
  assert.strictEqual(s.radiale.accese[s.radiale.voci.indexOf("telecinesi")], false);
  r.orda(0, 9); amb.avanza(90); r.energia("robot", 100);
  s = amb.stato();
  for (const id of ["telecinesi", "avvinghia", "teletrasporto"]) assert.strictEqual(s.radiale.voci.indexOf(id), -1, id + " offerta durante la tregua");
  for (const id of ["cavallina", "trottola", "insieme", "bolide"]) assert.ok(s.radiale.voci.indexOf(id) >= 0, id + " manca dal controller durante la tregua");
  assert.strictEqual(s.radiale.voci.length, s.radiale.accese.length);
});

test("l'orda arriva da sola, col suo orologio: non nel primo minuto e mezzo, ma entro pochi minuti sì", () => {
  // Riccardo, 05/10/2026: «l'ondata di zombie non arriva mai». Era pescata una volta su dieci fra gli imprevisti.
  let arrivate = 0;
  for (let giro = 0; giro < 3; giro++) {
    const amb = ambiente();
    let quando = -1, n = 0;
    amb.avanza(60 * 190, (s) => { n++; if (s.orda) { quando = n / 60; return false; } });
    const s = amb.stato();
    if (!s.orda) continue;
    arrivate++;
    assert.ok(quando >= 88, "l'orda è arrivata troppo presto: " + quando.toFixed(0) + " s");
    assert.strictEqual(s.orda.ondate, 3, "a sorpresa le ondate sono tre");
    assert.strictEqual(s.evento, "zombie");
    // finita, non ne riparte subito un'altra
    amb.avanza(60 * 150, (st) => (st.orda ? undefined : false));
    if (amb.stato().orda) continue;                    // tre ondate lunghe: capita
    amb.avanza(60 * 60, (st) => { assert.ok(!st.orda, "finita un'orda ne è ripartita subito un'altra"); });
    dentro(amb);
  }
  assert.ok(arrivate >= 2, "in tre minuti di lotta l'orda non arriva: " + arrivate + "/3");
  // con le sorprese spente non arriva
  const amb = ambiente();
  amb.finestra.__ring.comandi.sorprese(false);
  amb.avanza(60 * 200, (s) => { assert.ok(!s.orda, "orda a sorpresa con le sorprese spente"); });
});

test("orda: con tutti e due a terra ci si rialza di scatto due volte; alla terza l'orda ha vinto", () => {
  // Prima finiva alla prima caduta in due, spesso già alla seconda ondata: «c'è solo la prima ondata».
  const amb = ambiente();
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false);
  amb.avanza(60);
  r.orda(0, 3);
  amb.avanza(120);
  assert.strictEqual(amb.stato().orda.vite, 3);
  for (const attese of [2, 1]) {
    // giù tutti e due, e ci restano: dopo un secondo e mezzo scatta la riscossa
    let n = 0;
    amb.avanza(60 * 6, (s) => {
      if (!s.orda || s.orda.vite === attese) return false;
      for (const f of s.lottatori) if (!f.ko) r.ko(f.tipo);
      n++;
    });
    let s = amb.stato();
    assert.ok(s.orda && s.orda.fase !== "festa", "alla caduta numero " + (3 - attese) + " l'orda è finita");
    assert.strictEqual(s.orda.vite, attese);
    assert.ok(n >= 85, "la riscossa è scattata troppo presto: " + n);
    // si rialzano subito, e gli zombie vicini sono stati buttati indietro
    let inPiedi = false;
    amb.avanza(60, (st) => { if (st.lottatori.every((f) => !f.ko)) { inPiedi = true; return false; } });
    assert.ok(inPiedi, "dopo la riscossa non si rialzano");
  }
  amb.avanza(60 * 6, (s) => { if (!s.orda || s.orda.fase === "festa") return false; for (const f of s.lottatori) if (!f.ko) r.ko(f.tipo); });
  assert.ok(!amb.stato().orda || amb.stato().orda.fase === "festa", "finite le vite l'orda non finisce");
  amb.avanza(60 * 5);
  assert.strictEqual(amb.stato().orda, null);
  dentro(amb);
});

test("orda: se i due finiscono su un altro piano, gli zombie rispuntano lì", () => {
  // Buttati giù da un elemento della pagina restavano sotto, e gli zombie sopra, fermi fino allo scadere dell'ondata.
  let traslochi = 0;
  for (let giro = 0; giro < 4 && !traslochi; giro++) {
    const amb = ambiente({ solidi: [[250, 420, 950, 450]] });
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false);
    amb.avanza(60);
    // tutti e due a terra, e l'orda comincia lì
    amb.porta("robot", 520, amb.pavimento - 60, 12); amb.rilascia(520, amb.pavimento - 60);
    amb.porta("mela", 640, amb.pavimento - 60, 12); amb.rilascia(640, amb.pavimento - 60);
    amb.avanza(90);
    r.orda(0, 4 + giro);
    amb.avanza(150);
    let s = amb.stato();
    if (!s.orda || Math.abs(s.orda.base - amb.pavimento) > 2) continue;
    // li si porta sopra l'elemento
    amb.porta("robot", 520, 360, 14); amb.rilascia(520, 360);
    amb.porta("mela", 660, 360, 14); amb.rilascia(660, 360);
    let su = false;
    amb.avanza(60 * 5, (st) => { if (st.orda && Math.abs(st.orda.base - 420) < 3) { su = true; return false; } });
    if (!su) continue;
    s = amb.stato();
    assert.ok(s.orda.traslochi >= 1);
    assert.ok(s.orda.l >= 250 && s.orda.r <= 950, "l'orda non si è stretta sull'elemento");
    for (const z of s.orda.zombie) if (z.stato !== "giu") assert.ok(z.x >= 250 && z.x <= 950, "uno zombie è rimasto fuori dall'elemento");
    traslochi++;
    // e lassù si continua a combattere
    const prima = s.orda.uccisi;
    amb.avanza(60 * 25, (st) => (st.orda && st.orda.uccisi > prima + 1 ? false : undefined));
    assert.ok(amb.stato().orda && amb.stato().orda.uccisi > prima, "dopo il trasloco non si abbatte più nessuno");
    dentro(amb);
  }
  assert.ok(traslochi > 0, "l'orda non ha mai seguito i due sull'altro piano");
});

test("scontro di energie: spuntano due tasti, e martellando quello di chi parte sfavorito lo si fa vincere", () => {
  // senza tasti: con 50 contro 100 vince la mela
  const senza = scontroPulito((r) => { r.energia("robot", 50); r.energia("mela", 100); });
  assert.strictEqual(senza.vince, "mela");
  // col tasto del robot cliccato cinque volte al secondo vince lui
  let tasti = null, bloccati = 0, clic = 0;
  const amb0 = { premi: null };
  const e = scontroPulito((r, amb) => { amb0.amb = amb; r.energia("robot", 50); r.energia("mela", 100); tasti = null; bloccati = 0; clic = 0; }, (r, s) => {
    if (!s.sfida.tasti.length) return;
    if (!tasti) {
      tasti = s.sfida.tasti;
      assert.strictEqual(tasti.length, 2);
      assert.ok(tasti[0].x < tasti[1].x, "il tasto di sinistra deve stare a sinistra");
      for (const t of tasti) assert.ok(t.x - t.r >= 0 && t.x + t.r <= s.larghezza && t.y - t.r >= 0 && t.y + t.r <= s.pavimento, "tasto fuori dalla finestra");
      assert.ok(tasti[1].x - tasti[0].x > tasti[0].r * 2, "i due tasti si sovrappongono");
    } else {
      // una volta messi non si spostano: si devono poter cliccare in fretta
      assert.ok(Math.abs(s.sfida.tasti[0].x - tasti[0].x) < 0.5 && Math.abs(s.sfida.tasti[0].y - tasti[0].y) < 0.5, "il tasto si sposta durante lo scontro");
    }
    if (s.sfida.t % 12 === 0) {
      const sinistra = s.sfida.sinistra === "robot" ? 0 : 1;
      const ev = amb0.amb.premi(tasti[sinistra].x, tasti[sinistra].y); amb0.amb.rilascia(tasti[sinistra].x, tasti[sinistra].y);
      clic++; if (ev.bloccato) bloccati++;
    }
  });
  assert.ok(clic >= 5 && bloccati === clic, "i clic sul tasto arrivano alla pagina: " + bloccati + "/" + clic);
  assert.strictEqual(e.vince, "robot", "martellando il tasto non si vince (" + e.come + ", " + clic + " clic)");
  assert.ok(e.tifo[e.stato.ultimaSfida ? 0 : 0] + e.tifo[1] === clic, "non tutti i clic sono diventati tifo");
});

// --- Mosse in coppia durante l'orda (05/10/2026) ---------------------------
// Riccardo: «nella modalità zombie non devono stare solo spalla a spalla,
// devono avere collaborazioni dinamiche». I due in formazione, con gli zombie
// addosso, e la mossa data a comando.
function inFormazione(seme, stile) {
  const amb = ambiente({ memoria: stile ? { "mut-ring-stile": stile } : {} });
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false); amb.avanza(60);
  r.sposta("robot", 560); r.sposta("mela", 640);
  r.orda(0, seme); amb.avanza(60); r.coppiaAttesa(1e6);       // da soli non ne fanno: le comanda la prova
  for (let i = 0; i < 400; i++) {
    amb.avanza(1);
    const s = amb.stato();
    if (!s.orda || s.orda.fase !== "lotta") continue;
    if (Math.abs(s.lottatori[0].cx - s.lottatori[1].cx) < 60 * s.scala && s.lottatori.every((f) => !f.ko && !f.inVolo && !f.coppia)) {
      const cx = (s.lottatori[0].cx + s.lottatori[1].cx) / 2;
      for (const [tipo, dx] of [["lento", 110], ["lento", 130], ["svelto", 150], ["lento", 185], ["lento", -40], ["lento", 44]]) r.zombie(tipo, cx + dx);
      return amb;
    }
  }
  return null;
}
const saluteOrda = (s) => s.orda.zombie.reduce((t, z) => t + (z.stato !== "giu" ? z.hp : 0), 0) - s.orda.uccisi * 100;

test("orda, mosse in coppia: cavallina, cambio di lato, colpo insieme e palla di cannone fanno quello che dicono", () => {
  const fatte = { cavallina: 0, trottola: 0, insieme: 0, bolide: 0 };
  for (const tipo of Object.keys(fatte)) {
    for (let k = 0; k < 4 && fatte[tipo] < 2; k++) {
      const amb = inFormazione(3 + k);
      if (!amb) continue;
      const r = amb.finestra.__ring;
      if (!r.coppia(tipo, "robot")) continue;
      const s0 = amb.stato(), punti = JSON.stringify(s0.punteggio), salute0 = saluteOrda(s0);
      const robot0 = s0.lottatori.find((f) => f.tipo === "robot"), mela0 = s0.lottatori.find((f) => f.tipo === "mela");
      assert.ok(s0.lottatori.some((f) => f.coppia), tipo + ": partita, ma nessuno la sta facendo");
      let alto = 0, lontano = 0, durata = 0, morsi = 0;
      const danni0 = robot0.danni + mela0.danni;
      amb.avanza(120, (s) => {
        const f = s.lottatori.find((l) => l.tipo === "robot");
        if (!s.orda || !s.lottatori.some((l) => l.coppia)) return false;
        durata++;
        alto = Math.max(alto, f.alto / s.scala); lontano = Math.max(lontano, Math.abs(f.cx - robot0.cx) / s.scala);
        morsi = Math.max(morsi, s.lottatori[0].danni + s.lottatori[1].danni - danni0);
        for (const l of s.lottatori) assert.ok(Number.isFinite(l.cx + l.bacino.x + l.bacino.y), tipo + ": coordinate non finite");
      });
      const s1 = amb.stato(), robot1 = s1.lottatori.find((f) => f.tipo === "robot"), mela1 = s1.lottatori.find((f) => f.tipo === "mela");
      assert.ok(durata >= 20 && durata < 110, tipo + ": dura " + durata + " fotogrammi");
      assert.strictEqual(morsi, 0, tipo + ": durante la mossa in coppia gli zombie mordono lo stesso");
      assert.strictEqual(JSON.stringify(s1.punteggio), punti, tipo + ": ha cambiato il punteggio della partita");
      assert.ok(s1.orda && s1.orda.coppie[tipo] === 1, tipo + ": non viene contata");
      const scambiati = (robot0.cx < mela0.cx) !== (robot1.cx < mela1.cx);
      if (tipo === "cavallina") {
        assert.ok(alto > 30, "cavallina: non salta sopra il compagno (alto " + alto.toFixed(0) + ")");
        assert.ok(scambiati && lontano > 60, "cavallina: non atterra dall'altra parte del compagno");
        assert.ok(saluteOrda(s1) < salute0, "cavallina: atterrando non colpisce nessuno");
        assert.notStrictEqual(s1.orda.latiDi.robot, s0.orda.latiDi.robot, "cavallina: i lati da tenere non si scambiano");
      } else if (tipo === "trottola") {
        assert.ok(scambiati, "cambio di lato: i due non si scambiano di posto");
        assert.notStrictEqual(s1.orda.latiDi.robot, s0.orda.latiDi.robot, "cambio di lato: i lati da tenere non si scambiano");
        assert.strictEqual(s1.orda.latiDi.robot, -s1.orda.latiDi.mela);
      } else if (tipo === "insieme") {
        assert.ok(!scambiati, "colpo insieme: i due si sono scambiati di posto");
        assert.ok(saluteOrda(s1) < salute0, "colpo insieme: non fa male a nessuno zombie");
      } else {
        assert.ok(lontano > 120, "palla di cannone: chi viene lanciato non va lontano (" + lontano.toFixed(0) + ")");
        assert.ok(saluteOrda(s1) < salute0, "palla di cannone: non travolge nessuno zombie");
      }
      amb.avanza(240); dentro(amb);
      fatte[tipo]++;
    }
    assert.ok(fatte[tipo] >= 2, tipo + ": a comando non parte quasi mai (" + fatte[tipo] + ")");
  }
});

test("orda, mosse in coppia: i due le fanno da soli, e durante la tregua il controller le comanda", () => {
  // da soli
  let fatte = 0, tipi = {};
  for (let k = 0; k < 4 && fatte < 3; k++) {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); amb.avanza(60); r.orda(0, 20 + k);
    amb.avanza(60 * 50, (s) => { if (!s.orda) return false; });
    const s = amb.stato();
    if (s.orda) for (const t in s.orda.coppie) { fatte += s.orda.coppie[t]; tipi[t] = 1; }
    dentro(amb);
  }
  assert.ok(fatte >= 3, "da soli non fanno quasi mai una mossa in coppia: " + fatte);
  assert.ok(Object.keys(tipi).length >= 2, "da soli fanno sempre la stessa: " + Object.keys(tipi));
  // dal controller: lo spicchio «Cavallina» c'è, si accende quando si può e il clic la fa partire
  let partite = 0;
  for (let k = 0; k < 5 && !partite; k++) {
    const amb = inFormazione(11 + k);
    if (!amb) continue;
    const r = amb.finestra.__ring;
    r.radiale(true); amb.avanza(30);
    let g = amb.stato().radiale;
    const i = g.voci.indexOf("cavallina");
    assert.ok(i >= 0, "nel controller, durante la tregua, manca la cavallina");
    // lo spicchio si accende quando i due sono pronti (in piedi, vicini, non storditi da un morso)
    for (let n = 0; n < 240 && !g.accese[i]; n++) { amb.avanza(1); g = amb.stato().radiale; }
    if (!g.accese[i]) continue;
    amb.premi(g.spicchi[i].x, g.spicchi[i].y); amb.rilascia(0, 0);
    amb.avanza(8);
    if (amb.stato().lottatori.some((f) => f.coppia === "cavallina" || f.coppia === "sgabello")) partite++;
  }
  assert.ok(partite > 0, "dal controller la cavallina non parte");
  // fuori dalla tregua le mosse in coppia non ci sono
  const amb = ambiente();
  amb.avanza(60);
  assert.strictEqual(amb.stato().radiale.voci.indexOf("cavallina"), -1);
  assert.strictEqual(amb.finestra.__ring.coppia("cavallina", "robot"), false, "la mossa in coppia parte anche senza orda");
});

// --- Buco nero (05/10/2026) -------------------------------------------------
// Riccardo: «buco nero che risucchia tutto quello che c'è in zona e lo spawna
// dall'altra parte dello schermo».
test("buco nero: risucchia un lottatore e lo fa uscire dall'altra parte dello schermo, senza toccare il punteggio", () => {
  let passati = 0;
  for (let k = 0; k < 4; k++) {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); amb.avanza(60);
    r.sposta("robot", 300); r.sposta("mela", 1040); amb.avanza(5);
    const f0 = amb.lottatore("robot");
    // una volta all'altezza del busto, una volta più in alto: chi è a terra lì sotto viene preso lo stesso
    r.buco(f0.cx + 30, f0.bacino.y - (k % 2 ? 60 * amb.stato().scala : 10));
    const s0 = amb.stato();
    assert.ok(s0.buco && s0.buco.fase === "apre", "il buco nero non si apre");
    assert.ok(s0.buco.uscita.x > s0.larghezza / 2 && Math.abs(s0.buco.uscita.x - s0.buco.x) > 300, "l'uscita non è dall'altra parte dello schermo");
    let dentroPer = 0, entrato = null, uscito = null, n = 0, chiuso = -1;
    amb.avanza(60 * 14, (s) => {
      n++;
      const f = s.lottatori.find((l) => l.tipo === "robot");
      assert.ok(Number.isFinite(f.cx + f.bacino.x + f.bacino.y), "coordinate non finite");
      if (f.fuoriCampo) { dentroPer++; if (!entrato) entrato = { punti: JSON.stringify(s.punteggio), ko: f.ko }; }
      else if (entrato && !uscito) uscito = { x: f.bacino.x, y: f.bacino.y, punti: JSON.stringify(s.punteggio) };
      if (!s.buco) { chiuso = n; return false; }
    });
    const s = amb.stato();
    assert.ok(chiuso > 0 && chiuso < 60 * 13, "il buco nero non si chiude");
    assert.ok(s.lottatori.every((f) => !f.fuoriCampo), "qualcuno è rimasto dentro il buco nero");
    if (entrato) {
      passati++;
      assert.ok(dentroPer >= 10 && dentroPer < 120, "dentro il buco per " + dentroPer + " fotogrammi");
      assert.ok(uscito, "entrato e mai uscito");
      assert.ok(uscito.x > s.larghezza / 2 + 100, "esce dalla stessa parte: x " + Math.round(uscito.x));
      assert.ok(uscito.y > 0 && uscito.y < s.pavimento, "esce fuori dalla finestra");
      assert.strictEqual(uscito.punti, entrato.punti, "passare nel buco nero ha cambiato il punteggio");
    }
    amb.avanza(200); dentro(amb);
  }
  assert.ok(passati >= 3, "il lottatore accanto al buco non viene quasi mai risucchiato: " + passati + "/4");
});

test("buco nero: passano anche oggetti e zombie; a comando si apre e si richiude, e nessuno resta dentro", () => {
  // un oggetto per aria accanto al buco
  let oggetti = 0;
  for (let k = 0; k < 3 && !oggetti; k++) {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); amb.avanza(60);
    r.sposta("robot", 150); r.sposta("mela", 250);
    const i = r.lanciaTelefono(600, 400, 0, 0, "classico");
    r.buco(620, 400);
    let p = 0;
    amb.avanza(60 * 13, (s) => { if (!s.buco) return false; p = s.buco.passati; });
    const t = amb.stato().telefoni[i];
    if (p >= 1 && t && Math.abs(t.x - 620) > 250) oggetti++;
    dentro(amb);
  }
  assert.ok(oggetti > 0, "l'oggetto accanto al buco non passa dall'altra parte");
  // gli zombie
  let zombie = 0;
  for (let k = 0; k < 3 && !zombie; k++) {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); amb.avanza(60);
    r.sposta("robot", 300); r.sposta("mela", 380);
    r.orda(0, 7 + k); amb.avanza(90);
    const s0 = amb.stato();
    for (const dx of [0, 14, 30]) r.zombie("lento", 900 + dx);
    r.buco(910, s0.pavimento - 40);
    let p = 0, sinistra = false;
    amb.avanza(60 * 13, (s) => {
      if (!s.buco) return false;
      p = s.buco.passati;
      if (s.orda) for (const z of s.orda.zombie) { assert.ok(Number.isFinite(z.x) && z.x >= 0 && z.x <= s.larghezza, "zombie fuori dalla finestra"); }
    });
    if (p >= 1) zombie++;
    dentro(amb);
  }
  assert.ok(zombie > 0, "gli zombie accanto al buco non vengono risucchiati");
  // a comando: si apre vicino ai due, e ricliccando si chiude subito lasciando uscire chi c'era
  for (let k = 0; k < 6; k++) {
    const amb = ambiente(k % 2 ? { memoria: { "mut-ring-stile": "guerrieri" } } : {});
    const r = amb.finestra.__ring, c = r.comandi;
    c.sorprese(false); amb.avanza(60 * (1 + k));
    c.colpo("buco");
    const s0 = amb.stato();
    assert.ok(s0.buco, "a comando il buco nero non si apre");
    assert.ok(s0.lottatori.some((f) => Math.abs(f.cx - s0.buco.x) < 200 * s0.scala), "a comando si apre lontano da tutti e due");
    let dentroQualcuno = false;
    amb.avanza(60 + k * 40, (s) => { if (s.lottatori.some((f) => f.fuoriCampo)) { dentroQualcuno = true; return false; } });
    c.colpo("buco");
    let s = amb.stato();
    assert.strictEqual(s.buco, null, "ricliccando il buco nero non si chiude");
    assert.ok(s.lottatori.every((f) => !f.fuoriCampo), "chiuso il buco, qualcuno è rimasto dentro" + (dentroQualcuno ? " (c'era)" : ""));
    amb.avanza(240, (st) => { for (const f of st.lottatori) assert.ok(Number.isFinite(f.cx + f.bacino.x + f.bacino.y), "coordinate non finite"); });
    dentro(amb);
  }
});

test("buco nero: arriva anche da solo, la prima volta poco dopo il primo minuto", () => {
  // Come per l'orda: un imprevisto nuovo che non si vede mai non serve a niente.
  let visti = 0;
  for (let giro = 0; giro < 3 && visti < 2; giro++) {
    const amb = ambiente();
    let n = 0, quando = -1;
    amb.avanza(60 * 260, (s) => { n++; if (s.buco) { quando = n / 60; return false; } });
    if (quando < 0) continue;
    visti++;
    assert.ok(quando >= 70, "il buco nero arriva troppo presto: " + quando.toFixed(0) + " s");
    amb.avanza(60 * 12);
    assert.strictEqual(amb.stato().buco, null, "arrivato a sorpresa, non si chiude più");
    dentro(amb);
  }
  assert.ok(visti >= 2, "in quattro minuti il buco nero non arriva quasi mai: " + visti);
});

// --- Colpo finale (05/10/2026) ----------------------------------------------
// Riccardo: «un sistema di fatality con mosse finali e animazioni particolari
// quando l'avversario ha poca vita, casuale una volta ogni 3 round».
test("colpo finale: ogni scena fa buio, conta un K.O. solo e lascia tutti nella finestra", () => {
  for (const [stile, tipo] of [["", "orbita"], ["", "flipper"], ["", "schiacciata"], ["guerrieri", "onda"], ["maghi", "statua"], ["lame", "taglio"]]) {
    let fatte = 0;
    for (let k = 0; k < 4 && fatte < 2; k++) {
      const amb = ambiente({ memoria: stile ? { "mut-ring-stile": stile } : {} });
      const r = amb.finestra.__ring;
      r.comandi.sorprese(false); r.roundFatale(false); amb.avanza(50);
      let partita = false;
      for (let i = 0; i < 200 && !partita; i++) { amb.avanza(3); r.roundFatale(false); partita = r.fatale("robot", tipo); }   // solo quello chiesto dalla prova
      if (!partita) continue;
      const s0 = amb.stato(), punti = s0.punteggio.robot + s0.punteggio.mela, robotPunti = s0.punteggio.robot;
      assert.strictEqual(s0.fataliFatti, 0);
      assert.ok(s0.fatale && s0.fatale.tipo === tipo && s0.fatale.fase === "annuncio" && s0.fatale.da === "robot" && s0.fatale.a === "mela", tipo + ": la scena non parte");
      const dx0 = Math.sign(s0.lottatori.find((f) => f.tipo === "mela").cx - s0.lottatori.find((f) => f.tipo === "robot").cx);
      const fasi = [];
      let n = 0, buio = 0, minY = 1e9, minX = 1e9, maxX = -1e9, salto = 0, piatto = 0, gelo = false, oltre = false, colpiInScena = 0;
      amb.avanza(60 * 12, (s) => {
        n++;
        const F = s.fatale;
        if (!F) return false;
        if (fasi[fasi.length - 1] !== F.fase) fasi.push(F.fase);
        const m = s.lottatori.find((f) => f.tipo === "mela"), rb = s.lottatori.find((f) => f.tipo === "robot");
        assert.ok(Number.isFinite(m.bacino.x + m.bacino.y + rb.bacino.x + rb.bacino.y + m.cx + rb.cx), tipo + ": coordinate non finite");
        assert.ok(m.bacino.x >= 0 && m.bacino.x <= s.larghezza && m.bacino.y <= s.pavimento + 1, tipo + ": la vittima esce dalla finestra (" + Math.round(m.bacino.x) + ", " + Math.round(m.bacino.y) + ")");
        if (tipo !== "orbita") assert.ok(m.bacino.y >= 0, tipo + ": la vittima esce dall'alto");
        assert.ok(rb.bacino.y >= 0 && rb.bacino.y <= s.pavimento + 1, tipo + ": chi colpisce esce dalla finestra");
        assert.ok(s.punteggio.robot + s.punteggio.mela - punti <= 1, tipo + ": la scena conta più di un K.O.");
        buio = Math.max(buio, s.fataleBuio); minY = Math.min(minY, m.bacino.y); minX = Math.min(minX, m.bacino.x); maxX = Math.max(maxX, m.bacino.x);
        salto = Math.max(salto, rb.alza / s.scala); piatto = Math.max(piatto, m.schiacciato); gelo = gelo || m.gelato;
        if (Math.sign(m.cx - rb.cx) === -dx0) oltre = true;
        // durante la scena i colpi normali non contano
        if (n % 20 === 5 && !F.contato) colpiInScena += r.colpo("robot", "mela") + r.colpo("mela", "robot");
      });
      const s = amb.stato();
      assert.strictEqual(s.fatale, null, tipo + ": la scena non finisce");
      assert.strictEqual(fasi.join(">"), "annuncio>mossa>fine", tipo + ": fasi " + fasi.join(">"));
      assert.ok(n > 100 && n < 420, tipo + ": dura " + n + " fotogrammi");
      assert.ok(buio > 0.3, tipo + ": la scena non si oscura");
      assert.strictEqual(colpiInScena, 0, tipo + ": durante la scena i colpi normali contano");
      assert.strictEqual(s.punteggio.robot, robotPunti + 1, tipo + ": non vale un K.O. per chi la fa");
      assert.strictEqual(s.punteggio.robot + s.punteggio.mela, punti + 1, tipo + ": K.O. contati " + (s.punteggio.robot + s.punteggio.mela - punti));
      assert.strictEqual(s.fataliFatti, 1);
      if (tipo === "orbita") assert.ok(minY < 0, "in orbita: non esce dall'alto");
      if (tipo === "flipper") assert.ok(maxX - minX > s.larghezza * 0.7, "flipper: non rimbalza da un bordo all'altro (" + Math.round(minX) + ".." + Math.round(maxX) + ")");
      if (tipo === "schiacciata") assert.ok(salto > 30 && piatto > 0, "schiacciata: salto " + salto.toFixed(0) + ", schiacciato " + piatto);
      if (tipo === "onda") assert.ok(minX < 90 * s.scala || maxX > s.larghezza - 90 * s.scala, "onda finale: non lo porta fino al bordo");
      if (tipo === "statua") assert.ok(gelo, "statua: non lo gela");
      if (tipo === "taglio") assert.ok(oltre, "taglio netto: chi colpisce non passa dall'altra parte");
      // poi tutto torna com'era: luce, vittima in piedi e intera, nessuno fuori (e niente altro colpo finale nel frattempo)
      amb.avanza(500, () => { r.roundFatale(false); });
      const s2 = amb.stato(), m2 = s2.lottatori.find((f) => f.tipo === "mela"), r2 = s2.lottatori.find((f) => f.tipo === "robot");
      assert.ok(s2.fataleBuio < 0.03, tipo + ": resta buio");
      assert.ok(!m2.fatVola && !m2.schiacciato && !r2.alza, tipo + ": la vittima resta com'era nella scena");
      dentro(amb);
      fatte++;
    }
    assert.ok(fatte >= 2, tipo + ": la scena non parte quasi mai (" + fatte + ")");
  }
});

test("colpo finale: tocca a un round su tre, a caso; quello non usato resta buono", () => {
  const amb = ambiente();
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false); amb.avanza(30);
  r.roundFatale(false);
  const buoni = [];
  for (let i = 0; i < 60; i++) {
    r.ko(i % 2 ? "robot" : "mela");
    if (amb.stato().fataleRound) { buoni.push(i); r.roundFatale(false); }      // come se fosse stato usato
  }
  assert.ok(buoni.length >= 19 && buoni.length <= 21, "su 60 round, quelli buoni sono " + buoni.length);
  const passi = {};
  for (let i = 1; i < buoni.length; i++) { const d = buoni[i] - buoni[i - 1]; passi[d] = 1; assert.ok(d >= 1 && d <= 5, "fra due round buoni ne passano " + d); }
  assert.ok(Object.keys(passi).length >= 2, "il round buono cade sempre allo stesso posto: non è a caso");
  // quello non usato resta buono, e uno uscito nel frattempo resta a credito: alla lunga è sempre uno su tre
  const amb2 = ambiente();
  const r2 = amb2.finestra.__ring;
  r2.comandi.sorprese(false); amb2.avanza(30);
  r2.roundFatale(true);
  let usati = 0;
  for (let i = 0; i < 60; i++) {
    r2.ko(i % 2 ? "robot" : "mela");
    assert.ok(i >= 12 || amb2.stato().fataleRound, "il round buono non usato è andato perso");
    if (i >= 12 && amb2.stato().fataleRound) { usati++; r2.roundFatale(false); }
  }
  assert.ok(usati >= 17 && usati <= 20, "dopo dodici round a vuoto, su 48 se ne usano " + usati);
});

test("colpo finale: nel round buono il colpo che chiuderebbe diventa la mossa finale; negli altri round mai", () => {
  let conFinale = 0, prove = 0;
  for (let k = 0; k < 8 && conFinale < 3; k++) {
    const amb = ambiente(k % 2 ? { memoria: { "mut-ring-stile": "lame" } } : {});
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); amb.avanza(40);
    r.roundFatale(true);
    prove++;
    let visto = false;
    amb.avanza(60 * 40, (s) => {
      if (s.fatale) visto = true;
      if (s.punteggio.robot + s.punteggio.mela > 0) return false;
    });
    amb.avanza(60 * 8, (s) => { if (!s.fatale) return false; });
    const s = amb.stato();
    if (visto && s.fataliFatti === 1) { conFinale++; assert.strictEqual(s.punteggio.robot + s.punteggio.mela, 1); }
    dentro(amb);
  }
  assert.ok(conFinale >= 3, "nel round buono il primo K.O. è quasi sempre un K.O. normale: " + conFinale + "/" + prove);
  // negli altri round: mai
  const amb = ambiente();
  const r = amb.finestra.__ring;
  r.comandi.sorprese(false); amb.avanza(40);
  r.roundFatale(false);
  let ko = 0;
  amb.avanza(60 * 70, (s) => { r.roundFatale(false); assert.strictEqual(s.fatale, null, "colpo finale in un round che non è quello buono"); ko = Math.max(ko, s.punteggio.robot + s.punteggio.mela); });
  assert.ok(ko >= 1, "in settanta secondi nessun K.O.");
  assert.strictEqual(amb.stato().fataliFatti, 0);
});

test("colpo finale: non sul punto che chiude la partita, non durante orda o buco nero; se si afferra uno dei due salta", () => {
  // sul punto partita
  let provato = false;
  for (let k = 0; k < 5 && !provato; k++) {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); amb.avanza(40);
    for (let i = 0; i < 9; i++) { r.ko("mela"); r.roundFatale(false); }
    assert.strictEqual(amb.stato().punteggio.robot, 9);
    for (let i = 0; i < 400 && !provato; i++) {
      amb.avanza(3); r.roundFatale(false);
      const s = amb.stato();
      if (s.punteggio.robot !== 9 || s.punteggio.mela >= 9) break;
      assert.strictEqual(r.fatale("robot"), false, "colpo finale sul punto che chiude la partita");
      if (r.fatale("mela")) provato = true;                    // l'altro, che non è sul punto partita, può
    }
  }
  assert.ok(provato, "non si è mai arrivati a provare il punto partita");
  // durante l'orda e col buco nero aperto
  {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); amb.avanza(40);
    r.orda(0, 3);
    amb.avanza(240, () => { assert.strictEqual(r.fatale("robot"), false, "colpo finale durante l'orda"); assert.strictEqual(r.fatale("mela"), false); });
  }
  {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); amb.avanza(40);
    r.buco(900, 200);
    amb.avanza(240, (s) => { if (!s.buco) return false; assert.strictEqual(r.fatale("robot"), false, "colpo finale col buco nero aperto"); });
  }
  // un buco nero aperto addosso a scena iniziata non la disturba: chi è in scena non viene risucchiato
  let conBuco = 0;
  for (let k = 0; k < 5 && conBuco < 2; k++) {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); r.roundFatale(false); amb.avanza(50);
    let partita = false;
    for (let i = 0; i < 200 && !partita; i++) { amb.avanza(3); r.roundFatale(false); partita = r.fatale("robot", k % 2 ? "orbita" : "schiacciata"); }
    if (!partita) continue;
    const punti = amb.stato().punteggio.robot;
    amb.avanza(8);
    const m = amb.lottatore("mela");
    r.buco(m.bacino.x + 10, m.bacino.y - 20);
    amb.avanza(60 * 10, (s) => {
      if (!s.fatale) return false;
      assert.ok(s.lottatori.every((f) => !f.fuoriCampo), "risucchiato durante il colpo finale");
      for (const f of s.lottatori) assert.ok(f.bacino.y <= s.pavimento + 1 && (f.bacino.y >= 0 || f.fatVola), "fuori dalla finestra durante il colpo finale col buco aperto");
    });
    const s = amb.stato();
    assert.strictEqual(s.fatale, null);
    assert.strictEqual(s.punteggio.robot, punti + 1, "col buco nero aperto la scena non arriva in fondo");
    assert.strictEqual(s.fataliFatti, 1);
    conBuco++;
  }
  assert.ok(conBuco >= 2, "colpo finale col buco nero: mai provato");
  // afferrato a metà dell'annuncio: la scena salta, niente K.O., e il round resta buono
  let saltate = 0;
  for (let k = 0; k < 6 && saltate < 2; k++) {
    const amb = ambiente();
    const r = amb.finestra.__ring;
    r.comandi.sorprese(false); r.roundFatale(false); amb.avanza(50);
    let partita = false;
    for (let i = 0; i < 200 && !partita; i++) { amb.avanza(3); r.roundFatale(false); partita = r.fatale("robot", "schiacciata"); }
    if (!partita) continue;
    const punti = JSON.stringify(amb.stato().punteggio);
    amb.avanza(6);
    const m = amb.lottatore("mela");
    amb.premi(m.bacino.x, m.bacino.y - 8);
    amb.muovi(m.bacino.x + 6, m.bacino.y - 14);
    amb.avanza(4);
    const s = amb.stato();
    if (!s.lottatori.find((f) => f.tipo === "mela").preso) { amb.rilascia(0, 0); continue; }
    assert.strictEqual(s.fatale, null, "afferrata la vittima, la scena va avanti");
    assert.strictEqual(JSON.stringify(s.punteggio), punti, "scena saltata, ma il K.O. è contato");
    assert.strictEqual(s.fataliFatti, 0);
    assert.strictEqual(s.fataleRound, true, "scena saltata: il round buono è andato perso");
    amb.rilascia(m.bacino.x + 6, m.bacino.y - 14);
    amb.avanza(200); dentro(amb);
    saltate++;
  }
  assert.ok(saltate >= 2, "non si riesce ad afferrare la vittima durante l'annuncio: " + saltate);
});

test("colpo finale: il tasto del menu lo fa partire appena i due sono in piedi e vicini, ed è gratis", () => {
  const premio = { bloccate: { guerrieri: true, armi: true, meteo: true }, attivo: () => false, chiedi: () => {} };
  let partiti = 0;
  for (let k = 0; k < 5; k++) {
    const amb = ambiente(k === 0 ? { premio, estensione: true, memoria: { "mut-ring": "on" } } : k % 2 ? { memoria: { "mut-ring-stile": "maghi" } } : {});
    const r = amb.finestra.__ring, c = r.comandi;
    c.sorprese(false); amb.avanza(60 * (1 + k), () => { r.roundFatale(false); });
    assert.notStrictEqual(c.colpo("fatale"), false, "il colpo finale non è libero");
    if (k === 0) assert.strictEqual(c.colpo("buco"), false, "senza Premium il buco nero si apre lo stesso");
    let visto = -1, n = 0;
    amb.avanza(60 * 7, (s) => { n++; if (s.fatale) { visto = n; return false; } });
    if (visto < 0) { assert.ok(amb.stato().fataleRound, "il tasto non ha lasciato traccia: passati sei secondi il round in corso deve diventare quello buono"); continue; }
    partiti++;
    amb.avanza(60 * 9, (s) => { r.roundFatale(false); if (!s.fatale) return false; });
    assert.strictEqual(amb.stato().fatale, null);
    assert.strictEqual(amb.stato().fataliFatti, 1);
    dentro(amb);
  }
  // (coi maghi in volo sulla scopa può non partire entro i sei secondi: misurato, 26 volte su 30)
  assert.ok(partiti >= 3, "col tasto il colpo finale parte di rado: " + partiti + "/5");
});
