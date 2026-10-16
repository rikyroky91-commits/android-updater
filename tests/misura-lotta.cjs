/* MISURA di quanto si lotta davvero (non è un test: stampa numeri).
 *
 * Su tante pagine (`dati/pagine-vere.json`) dice, per ogni stile: quanti colpi
 * a segno al minuto, quanto tempo passa senza che succeda niente, cosa stanno
 * facendo i lottatori quando potrebbero lottare, e cosa c'era di mezzo nelle
 * pause lunghe (livelli diversi, distanza, attese).
 *
 * Prima e dopo la revisione del 02/10/2026 (primo minuto di gara, 46 pagine):
 *   classico:  colpi a segno al minuto 23 → 34, pause lunghe 29% → 4% del tempo in piedi, fermi tutti e due 15% → 6%
 *   duellanti: 28 → 31, 13% → 9%, 11% → 5%
 *   guerrieri: 19 → 21, 19% → 9%, 8% → 4%
 *   maghi:     29 → 32, 21% → 13%, 7% → 5%
 * Passato il primo minuto (TEMPO=75), classico: 17 → 26 colpi al minuto, pause lunghe 32-43% → 15-19%.
 *
 *   node tests/misura-lotta.cjs
 *   STILI=",lame" SECONDI=90 node tests/misura-lotta.cjs
 *   RING_JS=/percorso/ring-vecchio.js node tests/misura-lotta.cjs
 */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const sorgente = fs.readFileSync(path.join(__dirname, "ring.test.cjs"), "utf8");
const preambolo = sorgente.slice(0, sorgente.indexOf("\ntest("))
  .replace('path.join(__dirname, "..", "web", "static", "ring.js")', 'process.env.RING_JS || path.join(__dirname, "..", "web", "static", "ring.js")');
const modulo = new module.constructor(__filename, module);
modulo.filename = __filename; modulo.paths = module.paths;
modulo._compile(preambolo + "\nmodule.exports = { ambiente };", __filename);
const { ambiente } = modulo.exports;

const DISP = JSON.parse(fs.readFileSync(process.env.RIQUADRI || path.join(__dirname, "dati", "pagine-vere.json"), "utf8"));
const STILI = (process.env.STILI || ",lame,guerrieri,maghi").split(",");
const SECONDI = Number(process.env.SECONDI || 60);
const TEMPO = Number(process.env.TEMPO || 0);          // secondi di gara già passati (75: oltre la calma)
const PAUSA = 60 * 4;                                  // quattro secondi senza un colpo: una pausa lunga
for (const stile of STILI) {
  const t = { fot: 0, pronti: 0, azioni: {}, colpi: 0, pausaMax: 0, inPausa: 0, cause: {}, ko: 0, distanza: 0, stati: {}, fermi2: 0, fermi1: 0, filaFermi: 0 };
  for (const [nome, d] of Object.entries(DISP)) {
    const amb = ambiente({ larghezza: d.W, altezza: d.H, solidi: d.riquadri, estensione: true, memoria: { "mut-ring": "on", "mut-ring-cruento": "off" } });
    amb.avanza(20);
    const r = amb.finestra.__ring;
    if (stile) r.comandi.stile(stile);
    if (TEMPO) r.tempo(TEMPO);
    let prima = null, senza = 0, cause = {}, fila = 0;
    amb.avanza(60 * SECONDI, (s) => {
      const [a, b] = s.lottatori;
      t.fot++;
      const colpo = prima && s.lottatori.some((f, i) => f.danni > prima[i].danni || (f.ko > 0 && !(prima[i].ko > 0)) || (f.esploso && !prima[i].esploso));
      prima = s.lottatori.map((f) => ({ danni: f.danni, ko: f.ko, esploso: f.esploso }));
      if (colpo) t.colpi++;
      const fuori = (f) => f.ko > 0 || f.esploso || f.preso || f.fuori;
      if (fuori(a) || fuori(b)) { t.ko++; senza = 0; cause = {}; return; }       // qualcuno è giù: non è una pausa
      t.pronti++;
      const S = s.scala, dist = Math.abs(a.bacino.x - b.bacino.x) / S, dy = Math.abs(a.base - b.base) / S;
      t.distanza += dist;
      // «Fermo»: in piedi senza fare niente, o a provocare. Chi cammina, colpisce, vola o barcolla non è fermo.
      const fermo = (f) => (!f.azione && !f.vola && !(f.stordito > 0) && !f.inVolo && !f.scalando) || f.azione === "provoca" || f.azione === "esulta";
      const quanti = (fermo(a) ? 1 : 0) + (fermo(b) ? 1 : 0);
      if (quanti === 2) { t.fermi2++; fila++; t.filaFermi = Math.max(t.filaFermi, fila); } else fila = 0;
      if (quanti === 1) t.fermi1++;
      const st = a.vola && b.vola ? "tutti e due in volo" : a.vola || b.vola ? "uno in volo" : dy > 18 ? "a terra, livelli diversi" : "a terra, stesso livello";
      (t.stati[st] = t.stati[st] || { fot: 0, colpi: 0 }).fot++;
      if (colpo) t.stati[st].colpi++;
      for (const f of s.lottatori) { const k = (f.vola ? "volo:" : "") + (f.azione || (f.stordito > 0 ? "(stordito)" : f.accecato ? "(accecato)" : f.gelato ? "(gelato)" : f.tenuto ? "(tenuto)" : f.inVolo ? "(in aria)" : f.scalando ? "(scala)" : "(fermo)")); t.azioni[k] = (t.azioni[k] || 0) + 1; }
      if (colpo) { if (senza > PAUSA) { t.inPausa += senza; for (const k in cause) t.cause[k] = (t.cause[k] || 0) + cause[k]; } senza = 0; cause = {}; return; }
      senza++;
      t.pausaMax = Math.max(t.pausaMax, senza);
      const c = dy > 18 ? "livelli diversi" : dist > 120 ? "lontani (>120)" : dist > 40 ? "a mezza distanza" : "vicini";
      cause[c] = (cause[c] || 0) + 1;
    });
    if (senza > PAUSA) { t.inPausa += senza; for (const k in cause) t.cause[k] = (t.cause[k] || 0) + cause[k]; }
  }
  const pc = (x, y) => (y ? (100 * x / y).toFixed(1) : "-") + "%";
  const az = Object.entries(t.azioni).sort((x, y) => y[1] - x[1]).slice(0, 12).map(([k, v]) => k + " " + pc(v, t.pronti * 2)).join(", ");
  const ca = Object.entries(t.cause).sort((x, y) => y[1] - x[1]).map(([k, v]) => k + " " + pc(v, t.inPausa)).join(", ");
  console.log("\n== " + (stile || "classico") + " ==");
  console.log("colpi a segno al minuto:", (t.colpi / (t.fot / 3600)).toFixed(1), "| tutti e due in piedi:", pc(t.pronti, t.fot), "| distanza media:", Math.round(t.distanza / t.pronti));
  console.log("pause oltre 4 s senza un colpo:", pc(t.inPausa, t.pronti), "del tempo in piedi | pausa più lunga:", (t.pausaMax / 60).toFixed(1), "s");
  console.log("fermi tutti e due:", pc(t.fermi2, t.pronti), "(fila più lunga", (t.filaFermi / 60).toFixed(1), "s) | fermo uno solo:", pc(t.fermi1, t.pronti));
  console.log("nelle pause lunghe:", ca);
  console.log("cosa fanno:", az);
  console.log("per situazione:", Object.entries(t.stati).map(([k, v]) => k + ": " + pc(v.fot, t.pronti) + " del tempo, " + (v.colpi / (v.fot / 3600)).toFixed(0) + " colpi/min").join(" | "));
}
