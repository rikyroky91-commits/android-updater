/* MISURA della corsa infinita (non è un test: stampa numeri).
 *
 * L'eroe gioca da solo (prende la prima carta, chiude i forzieri) per qualche corsa con semi diversi, e si
 * misura quanto dura ogni round in lotta (secondi), quanti round si fanno, quanto dura la corsa.
 *
 *   node tests/misura-corsa.cjs
 *   CORSE=6 MINUTI=8 STILE=guerrieri node tests/misura-corsa.cjs
 *   PARRY=1 node tests/misura-corsa.cjs     (un giocatore che fa il parry alle cariche letali)
 *   RING_JS=/percorso/ring-vecchio.js node tests/misura-corsa.cjs
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

const CORSE = Number(process.env.CORSE || 6), MINUTI = Number(process.env.MINUTI || 8), STILE = process.env.STILE || "";
const perTipo = {}, perRound = {}, finali = [], letali = new Set();
for (let k = 0; k < CORSE; k++) {
  const amb = ambiente({ memoria: STILE ? { "mut-ring-stile": STILE } : {} });
  const r = amb.finestra.__ring;
  amb.avanza(30);
  r.corsa.apri(1000 + k * 77); amb.avanza(20); r.corsa.scegli(k % 2 ? "mela" : "robot");
  let prima = null, inizio = 0, fot = 0, finita = false, ultimaS = -999;
  amb.avanza(60 * 60 * MINUTI, (s) => {
    fot++;
    const c = s.corsa;
    if (!c) return false;
    if (c.carte) r.corsa.carta(0);
    // PARRY=1: un giocatore che preme la parata quando la carica letale (o un morso) sta per arrivare.
    if (process.env.PARRY && s.orda) {
      const f = s.lottatori.find((l) => l.tipo === c.chi);
      for (const z of s.orda.zombie) {
        const d = Math.abs(z.x - f.bacino.x);
        if ((z.stato === "letale" && d < 75 && d > 45) && (fot - ultimaS > 30)) { r.tastoGiu("KeyS"); ultimaS = fot; }
      }
    }
    if (c.forziere) r.corsa.chiudiForziere();
    if (c.fase === "lotta" && (!prima || prima.fase !== "lotta")) inizio = fot;
    if (prima && prima.fase === "lotta" && c.fase !== "lotta") {
      const sec = (fot - inizio) / 60;
      (perTipo[prima.tipo] = perTipo[prima.tipo] || []).push(sec);
      (perRound[prima.round] = perRound[prima.round] || []).push(sec);
    }
    if (s.orda) for (const z of s.orda.zombie) if (z.stato === "mira") letali.add(k + ":" + Math.round(z.x / 50) + ":" + Math.floor(fot / 60));
    if (c.fase === "fine") { finali.push({ round: c.round, minuti: c.minuti, punti: c.punti }); finita = true; return false; }
    prima = { fase: c.fase, tipo: c.tipo, round: c.round };
  });
  if (!finita) finali.push({ round: amb.stato().corsa.round, minuti: amb.stato().corsa.minuti, punti: amb.stato().corsa.punti, viva: true });
}
const media = (a) => a.reduce((x, y) => x + y, 0) / a.length;
console.log("durata dei round in lotta (secondi), per tipo:");
for (const [t, v] of Object.entries(perTipo)) console.log("  " + t.padEnd(8), "media", media(v).toFixed(1), "min", Math.min(...v).toFixed(1), "max", Math.max(...v).toFixed(1), "(" + v.length + ")");
console.log("per round:", Object.entries(perRound).slice(0, 15).map(([n, v]) => n + ":" + media(v).toFixed(0) + "s").join("  "));
console.log("cariche letali viste (circa):", letali.size, "in", CORSE, "corse");
console.log("corse:", finali.map((f) => "R" + f.round + " " + f.minuti.toFixed(1) + "min" + (f.viva ? " (ancora viva)" : "")).join(" | "));
