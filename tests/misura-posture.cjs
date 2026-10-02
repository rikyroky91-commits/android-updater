/* MISURA delle posture dei lottatori su tante pagine (non è un test: stampa numeri).
 *
 * Serve quando si tocca la fisica del ring: dice per quanta parte del tempo i
 * lottatori in piedi hanno le gambe incrociate, le ginocchia piegate
 * all'indietro o il busto storto, e quanto dura la fila più lunga di
 * fotogrammi «storti». Le pagine sono in `dati/pagine-vere.json`: i riquadri
 * degli elementi come li vede il ring, presi il 02/10/2026 da pypi.org,
 * github.com e da pagine di prova (notizie, negozio, documenti, modulo), a
 * 1280×800 e 390×760 e a varie altezze di scorrimento.
 *
 *   node tests/misura-posture.cjs                 tutte le pagine, tre stili, 30 s ciascuna
 *   STILI=",lame" SECONDI=60 DETTAGLIO=1 node tests/misura-posture.cjs
 *   RING_JS=/percorso/ring-vecchio.js node tests/misura-posture.cjs     per confrontare con una versione precedente
 *
 * Prima e dopo la correzione del 02/10/2026, su tutte le pagine:
 *   classico:   piegati 6,7% → 0,6%, gambe incrociate 15,9% → 0,6%, ginocchia al contrario 23,7% → 0,0%, fila più lunga 1446 → 19 fotogrammi
 *   duellanti:  4,0% → 0,6%, 55,3% → 1,7%, 60,8% → 0,1%, 690 → 12
 *   guerrieri:  2,4% → 0,3%, 37,7% → 1,2%, 42,2% → 0,1%, 225 → 15
 * «Dentro un elemento» è salito apposta (1% → 17%): chi è in piedi ora passa
 * davanti agli elementi della pagina invece di sbatterci contro.
 */
"use strict";
const fs = require("node:fs");
const path = require("node:path");

// L'ambiente finto è quello dei test del ring: si prende da lì, senza copiarlo.
const sorgente = fs.readFileSync(path.join(__dirname, "ring.test.cjs"), "utf8");
const preambolo = sorgente.slice(0, sorgente.indexOf("\ntest("))
  .replace('path.join(__dirname, "..", "web", "static", "ring.js")', 'process.env.RING_JS || path.join(__dirname, "..", "web", "static", "ring.js")');
const modulo = new module.constructor(__filename, module);
modulo.filename = __filename; modulo.paths = module.paths;
modulo._compile(preambolo + "\nmodule.exports = { ambiente };", __filename);
const { ambiente } = modulo.exports;

// MISURA delle posture su tante disposizioni di pagina (non è un test: stampa numeri).
const DISP = JSON.parse(fs.readFileSync(process.env.RIQUADRI || path.join(__dirname, "dati", "pagine-vere.json"), "utf8"));
const STILI = (process.env.STILI || ",lame,guerrieri").split(",");
const SECONDI = Number(process.env.SECONDI || 30);
function incrociano(a, b, c, d) {                 // i segmenti ab e cd si tagliano?
  const o = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return o(a, b, c) !== o(a, b, d) && o(c, d, a) !== o(c, d, b) && o(a, b, c) !== 0 && o(c, d, a) !== 0;
}
const tot = {};
const righe = [];
for (const [nome, d] of Object.entries(DISP)) {
  for (const stile of STILI) {
    const amb = ambiente({ larghezza: d.W, altezza: d.H, solidi: d.riquadri, estensione: true, memoria: { "mut-ring": "on", "mut-ring-cruento": "off" } });
    amb.avanza(20);
    const r = amb.finestra.__ring;
    if (stile) r.comandi.stile(stile);
    r.tempo(75);                                  // oltre la calma: jetpack, eventi, tutto
    const m = { fot: 0, piegato: 0, incrociate: 0, ginocchia: 0, dentro: 0, filaMax: 0, terra: 0, ko: 0 };
    const fila = {};
    let errore = null;
    try {
      amb.avanza(60 * SECONDI, (s) => {
        const S = s.scala, ost = s.riquadri;
        for (const f of s.lottatori) {
          if (f.esploso) continue;
          if (f.ko > 0) m.ko++;
          // «In piedi»: non a terra, non preso, non in volo, non stordito, non in arrampicata.
          if (f.ko > 0 || f.preso || f.tenuto || f.vola || f.scalando || f.stordito > 0 || f.rialzo > 0 || f.inVolo || f.gelato) { fila[f.tipo] = 0; continue; }
          m.fot++;
          const p = f.punti;
          if (p.piedeA[1] >= s.pavimento - 6 * S) m.terra++;
          const dx = p.collo[0] - p.bacino[0], dy = p.bacino[1] - p.collo[1];
          const storto = Math.abs(Math.atan2(dx, dy)) > 0.7 || p.testa[1] > p.collo[1] + 2 * S;
          if (storto) { m.piegato++; fila[f.tipo] = (fila[f.tipo] || 0) + 1; m.filaMax = Math.max(m.filaMax, fila[f.tipo]); } else fila[f.tipo] = 0;
          // Le gambe che si tagliano: coscia o stinco di una con coscia o stinco dell'altra.
          const gv = f.ginocchiaViste || [p.ginocchioA, p.ginocchioD];
          const A = [p.bacino, gv[0], p.piedeA], D = [p.bacino, gv[1], p.piedeD];
          // (In volo le gambe sono raccolte dietro e viste di lato si sovrappongono: lì non conta.)
          if (!f.vola && Math.hypot(p.piedeA[0] - p.piedeD[0], p.piedeA[1] - p.piedeD[1]) > 5 * S &&
              (incrociano(A[1], A[2], D[1], D[2]) || incrociano(A[0], A[1], D[1], D[2]) || incrociano(A[1], A[2], D[0], D[1]))) m.incrociate++;
          // Le ginocchia piegate all'indietro (dalla parte opposta alla faccia).
          for (const [g, pd] of [[gv[0], p.piedeA], [gv[1], p.piedeD]]) {
            const mx = (p.bacino[0] + pd[0]) / 2;
            if ((g[0] - mx) * f.dir < -3 * S) { m.ginocchia++; break; }
          }
          // Testa, collo o bacino dentro un elemento della pagina.
          for (const n of ["testa", "collo", "bacino"]) {
            if (ost.some((o) => p[n][0] > o[0] + 2 && p[n][0] < o[2] - 2 && p[n][1] > o[1] + 2 && p[n][1] < o[3] - 2)) { m.dentro++; break; }
          }
        }
      });
    } catch (e) { errore = String(e && e.message || e).slice(0, 80); }
    righe.push([nome, stile || "classico", m, errore]);
    const t = tot[stile || "classico"] = tot[stile || "classico"] || { fot: 0, piegato: 0, incrociate: 0, ginocchia: 0, dentro: 0, filaMax: 0, terra: 0, ko: 0, errori: 0 };
    for (const k of ["fot", "piegato", "incrociate", "ginocchia", "dentro", "terra", "ko"]) t[k] += m[k];
    t.filaMax = Math.max(t.filaMax, m.filaMax); if (errore) t.errori++;
  }
}
const pc = (a, b) => (b ? (100 * a / b).toFixed(1) : "-").padStart(5) + "%";
if (process.env.DETTAGLIO) for (const [n, s, m, e] of righe) console.log(n.padEnd(24), s.padEnd(9), "piegato", pc(m.piegato, m.fot), "gambe", pc(m.incrociate, m.fot), "ginocchia", pc(m.ginocchia, m.fot), "dentro", pc(m.dentro, m.fot), "fila", String(m.filaMax).padStart(5), "a terra", pc(m.terra, m.fot), e || "");
for (const [s, t] of Object.entries(tot)) console.log("TOTALE", s.padEnd(9), "in piedi", t.fot, "| piegato", pc(t.piegato, t.fot), "| gambe incrociate", pc(t.incrociate, t.fot), "| ginocchia al contrario", pc(t.ginocchia, t.fot), "| dentro un elemento", pc(t.dentro, t.fot), "| fila più lunga di storto", t.filaMax, "| a terra", pc(t.terra, t.fot), "| errori", t.errori);
