/* I due lottatori della home (30/09/2026, rifatto l'01/10/2026 su richiesta).
 *
 * Un robottino verde e una mela (polpa bianca, contorni e occhi neri),
 * disegnati apposta per questo sito, si picchiano in un ciclo casuale.
 *
 * DALL'01/10/2026 IL RING È TUTTA LA PAGINA:
 *  - si prendono col mouse (o col dito) e si lanciano dove si vuole: la
 *    velocità del lancio è quella del gesto;
 *  - gli elementi della pagina sono corpi solidi: ogni riga di testo, il
 *    campo di ricerca, i tasti, la testata, la striscia dell'ultim'ora.
 *    Ci si sbatte contro, ci si atterra sopra, ci si cammina;
 *  - per raggiungere l'avversario scendono dai bordi e si arrampicano sui
 *    fianchi degli elementi, una mano dopo l'altra.
 *
 * COME SONO FATTI. Ognuno è una bambola di pezza (ragdoll) con integrazione
 * di Verlet: undici punti legati da aste di lunghezza fissa, con gravità e
 * attrito. Finché il lottatore è sveglio dei «muscoli» tirano ogni punto
 * verso la posa del momento (guardia, pugno, calcio, arrampicata…); da
 * K.O., o mentre lo si tiene in mano, i muscoli si spengono e il corpo
 * penzola o crolla da solo. Nessuna animazione è disegnata a mano.
 *
 * LE STESSE ATTENZIONI DELLA TRAMA DI SFONDO (`rete.js`):
 *  - il ciclo si ferma quando la scheda passa in secondo piano;
 *  - disegna a 30 fotogrammi al secondo, non 60;
 *  - chi ha chiesto meno movimento al sistema operativo vede i due
 *    lottatori fermi in guardia, e la striscia delle notizie ferma.
 *
 * Il canvas copre la finestra ma non intercetta i clic (`pointer-events:
 * none`): la pagina sotto resta usabile. La presa si fa ascoltando il
 * puntatore sulla finestra e controllando se sotto c'è un lottatore; solo
 * in quel caso il gesto viene trattenuto.
 */
(function () {
  "use strict";

  // DI CHI SONO I PEZZI DEL RING (02/10/2026). Sul sito stanno nella pagina.
  // Nell'estensione del browser (`estensione/`) stanno in uno shadow DOM a
  // parte, così lo stile dei siti non li tocca: l'estensione lo dichiara in
  // `window.__ringRadice`, e mette in `window.__ringDeposito` una memoria
  // sua (uguale su tutti i siti) al posto di `localStorage`.
  const mio = window.__ringRadice || document;
  const ospite = window.__ringRadice ? window.__ringRadice.host : null;
  let deposito = null;
  try { deposito = window.__ringDeposito || window.localStorage; } catch (errore) { /* niente memoria */ }

  // PREMIUM (02/10/2026). Sul sito è tutto libero. L'estensione può dichiarare
  // in `window.__ringPremium` quali gruppi di funzioni sono a pagamento
  // (`bloccate`: guerrieri, armi, meteo), se sono già sbloccate (`attivo()`) e
  // cosa fare quando si tocca una funzione bloccata (`chiedi(gruppo)`).
  const premio = window.__ringPremium || null;
  const libero = (gruppo) => !premio || premio.attivo() || !premio.bloccate[gruppo];
  function concesso(gruppo) {
    if (libero(gruppo)) return true;
    try { premio.chiedi(gruppo); } catch (errore) { /* resta bloccata */ }
    return false;
  }
  const ARMI_PREMIO = { pistola: 1, spada: 1, bomba: 1, duo: 1, bazooka: 1, lanciafiamme: 1 };
  // Gli imprevisti che nell'estensione stanno col meteo (a pagamento); il terremoto resta libero.
  const EVENTI_PREMIO = { meteoriti: 1, zombie: 1, buco: 1 };
  const MOSSE_PREMIO = { onda: 1, carica: 1, teletrasporto: 1, sfera: 1, disco: 1, lampo: 1, barriera: 1, autodistruzione: 1, telecinesi: 1,
                         trasforma: 1, dardi: 1, gelo: 1, rimpicciolisci: 1, fulmine: 1, levita: 1, scudo: 1, raggio: 1, sparizione: 1,
                         "scatto-lama": 1, "lancio-lama": 1, duello: 1, scontro: 1 };
  // A quale gruppo a pagamento appartiene un tasto della tendina (o nessuno).
  function gruppoDi(tasto) {
    const metti = tasto.getAttribute("data-metti"), colpo = tasto.getAttribute("data-colpo");
    if (metti) return ARMI_PREMIO[metti] ? "armi" : null;
    if (colpo) return MOSSE_PREMIO[colpo] ? "guerrieri" : EVENTI_PREMIO[colpo] ? "meteo" : colpo.indexOf("esplodi-") === 0 ? "armi" : null;
    if (tasto.hasAttribute("data-anime") || tasto.hasAttribute("data-stile")) return "guerrieri";
    if (tasto.hasAttribute("data-imprevisto") || tasto.hasAttribute("data-gravita")) return "meteo";
    return null;
  }

  const tela = mio.querySelector("[data-ring]");
  const scorre = mio.querySelector("[data-scorre]");
  const orologio = mio.querySelector("[data-orologio]");
  const barra = mio.querySelector(".ultimora-barra");

  // --- L'orologio della striscia, come in TV ---------------------------
  function aggiornaOra() {
    if (!orologio) return;
    const ora = new Date();
    orologio.textContent = String(ora.getHours()).padStart(2, "0") + ":" +
      String(ora.getMinutes()).padStart(2, "0");
  }
  aggiornaOra();
  setInterval(aggiornaOra, 15000);

  // --- Velocità costante dello scorrimento -----------------------------
  function tara() {
    if (!scorre) return;
    const meta = scorre.scrollWidth / 2;
    if (meta > 0) scorre.style.setProperty("--durata", Math.max(20, meta / 75) + "s");
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(tara);
  window.addEventListener("load", tara);

  if (!tela || !tela.getContext) return;
  const ctx = tela.getContext("2d");
  const preferisceFermo = !!(window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  // IL TASTO CHE SPEGNE TUTTO IL LIVELLO DELLE LOTTE (01/10/2026, su
  // richiesta): lascia la pagina pulita, con le sole notizie. La scelta resta
  // nel browser. Chi ha ridotto i movimenti nel telefono lo trova spento.
  let scelta = null;
  try { scelta = deposito.getItem("mut-ring"); } catch (errore) { /* niente memoria */ }
  let fermo = scelta === "off" || (scelta !== "on" && preferisceFermo);

  // --- I tasti della striscia: pausa delle notizie e lotte accese/spente ---
  const tastoPausa = mio.querySelector("[data-pausa]");
  if (tastoPausa && barra) {
    tastoPausa.hidden = false;
    tastoPausa.addEventListener("click", () => {
      const inPausa = barra.classList.toggle("in-pausa");
      tastoPausa.setAttribute("aria-pressed", inPausa ? "true" : "false");
    });
  }
  const tastoRadiale = mio.querySelector("[data-radiale]");
  const tastoGioca = mio.querySelector("[data-gioca]");
  function aggiornaTastoGioca() {
    if (!tastoGioca) return;
    tastoGioca.setAttribute("aria-pressed", fermo ? "false" : "true");
    tastoGioca.title = fermo ? "Accendi le lotte" : ospite ? "Spegni le lotte" : "Spegni le lotte e lascia solo le notizie";
  }
  if (tastoGioca) {
    tastoGioca.hidden = false;
    aggiornaTastoGioca();
    tastoGioca.addEventListener("click", () => {
      fermo = !fermo;
      try { deposito.setItem("mut-ring", fermo ? "off" : "on"); } catch (errore) { /* pazienza */ }
      aggiornaTastoGioca();
      if (fermo) spegni(); else accendi();
    });
  }

  // --- Stato del mondo -------------------------------------------------
  let W = 0, H = 0, S = 1, pavimento = 0;
  let ostacoli = [];
  let lottatori = [];
  let scritte = [];
  let punteggio = { robot: 0, mela: 0 };
  let inchiostro = "#201e1d";
  let accento = "#ec3013";
  let passi = 0;
  // Le novità dell'01/10/2026 (telefoni, eventi, particelle, costumi).
  let telefoni = [], particelle = [], evento = null;
  // Le novità del 02/10/2026: le creature dei barattoli, le nubi dei fumogeni
  // e il gran finale di chi arriva a dieci.
  let creature = [], nubi = [], finale = null;
  // Nell'estensione non piovono telefoni (su richiesta): solo fumogeni,
  // barattoli e, con Premium, le armi. Sul sito i telefoni restano.
  const senzaTelefoni = !!ospite;
  let fermoColpo = 0, scossa = 0, moltG = 1, ritmo = 1, daSpawnare = 0;
  let prossimoEvento = 700, prossimoTelefono = 360;
  // La corsa infinita (vedi «LA CORSA INFINITA»): lo stato sta qui in cima perché
  // il pannello e il primo disegno lo leggono mentre lo script si avvia.
  const sulSito = !window.__ringRadice;                        // l'estensione non parla con nessun server
  let corsa = null, recordCorsa = 0, tastiUI = [], campoNome = null;
  const classifica = { aperta: false, voci: null, letta: -1e9, stato: "", mia: -1 };
  // Le monete in banca e i potenziamenti permanenti della bottega: restano fra una corsa e l'altra.
  let banca = 0, bottega = {};
  try {
    const v = parseInt(deposito.getItem("mut-ring-banca"), 10); if (Number.isFinite(v) && v > 0) banca = v;
    const b = JSON.parse(deposito.getItem("mut-ring-bottega") || "{}"); if (b && typeof b === "object") bottega = b;
  } catch (errore) { /* da zero */ }

  // ·· L'AUDIO (09/10/2026, chiesto da Riccardo: «aggiungi l'audio a tutto da attivare opzionalmente») ··
  // Spento finché non lo si accende (tasto «Audio» nel pannello, e l'altoparlante
  // nel cruscotto della corsa); la scelta resta nel browser. Niente file: ogni
  // suono è sintetizzato al momento con Web Audio (oscillatori, rumore, filtri),
  // così pesa zero byte e va bene anche nell'estensione, che non scarica niente.
  //  - LE PAROLE. Quasi tutto quello che succede nel ring scrive già la sua
  //    onomatopea (POW!, CLANG!, KABOOM!, SPLAT!…): `scrivi` la passa a
  //    `suonaParola`, che la traduce in un suono della famiglia giusta. Così
  //    un'azione nuova che scrive la sua parola ha già il suo suono.
  //  - GLI EVENTI SENZA PAROLA (lo sparo, l'onda d'energia, il jetpack, i
  //    fulmini, le esplosioni, la mira, i menu della corsa) chiamano `suona`.
  //  - I SUONI CHE DURANO (pioggia, vento dell'uragano, ronzio del buco nero, la
  //    nota della mira che sale e scende con la linea) sono anelli che
  //    `aggiornaAudio` alza e abbassa.
  //  - Il suono viene da dove succede la cosa: sinistra o destra secondo la x.
  //  - Al massimo AUDIO.voci suoni insieme, e la stessa famiglia non si ripete
  //    prima di AUDIO.pausa millisecondi: in una mischia con l'orda sennò è rumore.
  // (tempi in passi di fisica: la stessa famiglia non prima di 3 passi, cioè 50 ms)
  const AUDIO = { volume: 0.42, voci: 14, pausa: 3 };
  const audio = { acceso: false, ctx: null, uscita: null, rumore: null, finiscono: [], ultimo: {}, anelli: {} };
  try { audio.acceso = deposito.getItem("mut-ring-audio") === "on"; } catch (errore) { /* resta spento */ }
  // Il contesto audio nasce al primo gesto (i browser non lasciano suonare prima).
  function preparaAudio() {
    if (!audio.acceso) return null;
    if (!audio.ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return null;
      try {
        const c = new Ctx();
        const comp = c.createDynamicsCompressor ? c.createDynamicsCompressor() : null;
        const g = c.createGain(); g.gain.value = AUDIO.volume;
        if (comp) { g.connect(comp); comp.connect(c.destination); } else g.connect(c.destination);
        // Un secondo di rumore bianco, riusato da tutti i suoni di rumore.
        const n = Math.floor(c.sampleRate || 44100), buf = c.createBuffer(1, n, c.sampleRate || 44100), d = buf.getChannelData(0);
        for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
        audio.ctx = c; audio.uscita = g; audio.rumore = buf;
      } catch (errore) { audio.ctx = null; return null; }
    }
    if (audio.ctx.state === "suspended" && audio.ctx.resume) { try { audio.ctx.resume(); } catch (errore) { /* al prossimo gesto */ } }
    return audio.ctx;
  }
  function accendiAudio(si) {
    audio.acceso = !!si;
    try { deposito.setItem("mut-ring-audio", audio.acceso ? "on" : "off"); } catch (errore) { /* pazienza */ }
    if (audio.acceso) { preparaAudio(); suona("clic"); }
    else for (const k in audio.anelli) fermaAnello(k);
    for (const b of dentroPannello("[data-audio]")) b.setAttribute("aria-pressed", audio.acceso ? "true" : "false");
    return audio.acceso;
  }
  // Dove va il suono: un nodo di panoramica (se il browser lo ha) attaccato all'uscita.
  function canaleAudio(x) {
    const c = audio.ctx;
    if (x === undefined || !c.createStereoPanner) return audio.uscita;
    const p = c.createStereoPanner();
    p.pan.value = Math.max(-0.8, Math.min(0.8, (x / Math.max(1, W)) * 2 - 1)) * 0.7;
    p.connect(audio.uscita);
    return p;
  }
  // Due mattoni: una nota (con scivolata) e un soffio di rumore filtrato.
  function notaAudio(c, out, t0, f0, f1, dur, tipo, vol, attacco) {
    const o = c.createOscillator(), g = c.createGain();
    o.type = tipo || "sine";
    o.frequency.setValueAtTime(Math.max(20, f0), t0);
    if (f1 && f1 !== f0) o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0002, vol), t0 + (attacco || 0.005));
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(out);
    o.start(t0); o.stop(t0 + dur + 0.02);
    return o;
  }
  function soffioAudio(c, out, t0, dur, vol, filtro, f0, f1, q) {
    const s = c.createBufferSource(), fl = c.createBiquadFilter(), g = c.createGain();
    s.buffer = audio.rumore;
    fl.type = filtro || "lowpass"; fl.Q.value = q || 0.8;
    fl.frequency.setValueAtTime(Math.max(30, f0), t0);
    if (f1 && f1 !== f0) fl.frequency.exponentialRampToValueAtTime(Math.max(30, f1), t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0002, vol), t0 + 0.006);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    s.connect(fl); fl.connect(g); g.connect(out);
    s.start(t0, Math.random() * 0.5); s.stop(t0 + dur + 0.02);
    return s;
  }
  const varia = (f, k) => f * (1 + (Math.random() * 2 - 1) * (k || 0.08));
  // Le ricette: ogni famiglia di suoni, con la sua durata (serve a contare le voci).
  const SUONI_AUDIO = {
    pugno: [0.16, (c, o, t, k) => { notaAudio(c, o, t, varia(150), 55, 0.13, "sine", 0.9 * k); soffioAudio(c, o, t, 0.06, 0.5 * k, "bandpass", varia(1400), 600, 1.2); }],
    forte: [0.3, (c, o, t, k) => { notaAudio(c, o, t, varia(110), 38, 0.26, "sine", 1 * k); soffioAudio(c, o, t, 0.12, 0.7 * k, "lowpass", 2600, 300); }],
    metallo: [0.45, (c, o, t, k) => { const f = varia(1250, 0.12); notaAudio(c, o, t, f, f * 0.98, 0.42, "triangle", 0.35 * k); notaAudio(c, o, t, f * 2.76, f * 2.7, 0.3, "sine", 0.18 * k); soffioAudio(c, o, t, 0.03, 0.3 * k, "highpass", 3000, 3000); }],
    taglio: [0.22, (c, o, t, k) => { soffioAudio(c, o, t, 0.2, 0.5 * k, "bandpass", varia(900), 5200, 2.5); }],
    sparo: [0.25, (c, o, t, k) => { soffioAudio(c, o, t, 0.18, 0.9 * k, "lowpass", 5000, 400); notaAudio(c, o, t, 220, 60, 0.1, "square", 0.25 * k); }],
    boom: [1.2, (c, o, t, k) => { soffioAudio(c, o, t, 1.1 * Math.min(1.4, k), 1 * Math.min(1, k), "lowpass", 900, 60, 0.6); notaAudio(c, o, t, 70, 28, 0.8, "sine", 0.9 * Math.min(1, k)); }],
    zap: [0.5, (c, o, t, k) => { notaAudio(c, o, t, 1800, 120, 0.45, "sawtooth", 0.28 * k); notaAudio(c, o, t, 900, 80, 0.45, "square", 0.12 * k); }],
    morso: [0.3, (c, o, t, k) => { const g = notaAudio(c, o, t, varia(95, 0.2), 70, 0.28, "sawtooth", 0.3 * k); g.detune.value = (Math.random() - 0.5) * 300; soffioAudio(c, o, t, 0.1, 0.3 * k, "bandpass", 500, 300, 2); }],
    splat: [0.3, (c, o, t, k) => { soffioAudio(c, o, t, 0.25, 0.6 * k, "lowpass", 1200, 150, 1.5); notaAudio(c, o, t, 180, 60, 0.12, "sine", 0.4 * k); }],
    soffio: [0.4, (c, o, t, k) => { soffioAudio(c, o, t, 0.38, 0.4 * k, "bandpass", 700, 300, 0.7); }],
    bip: [0.25, (c, o, t, k) => { const f = varia(1300, 0.15); notaAudio(c, o, t, f, f, 0.09, "square", 0.12 * k); notaAudio(c, o, t + 0.11, f * 1.25, f * 1.25, 0.09, "square", 0.12 * k); }],
    tonfo: [0.2, (c, o, t, k) => { notaAudio(c, o, t, varia(120), 70, 0.16, "triangle", 0.5 * k); soffioAudio(c, o, t, 0.05, 0.3 * k, "lowpass", 900, 300); }],
    ko: [1.4, (c, o, t, k) => { for (const [f, v] of [[196, 0.5], [294, 0.3], [392, 0.22]]) notaAudio(c, o, t, f, f * 0.99, 1.3, "sine", v * k, 0.01); soffioAudio(c, o, t, 0.2, 0.4 * k, "lowpass", 3000, 200); }],
    preso: [0.5, (c, o, t, k) => { [784, 988, 1319].forEach((f, i) => notaAudio(c, o, t + i * 0.06, f, f, 0.22, "triangle", 0.25 * k)); }],
    mancato: [0.5, (c, o, t, k) => { notaAudio(c, o, t, 330, 160, 0.42, "triangle", 0.3 * k); }],
    carica: [0.6, (c, o, t, k) => { notaAudio(c, o, t, 180, 900, 0.55, "sawtooth", 0.12 * k, 0.05); notaAudio(c, o, t, 360, 1800, 0.55, "sine", 0.1 * k, 0.05); }],
    potenza: [1, (c, o, t, k) => { notaAudio(c, o, t, 110, 440, 0.9, "sawtooth", 0.18 * k, 0.1); soffioAudio(c, o, t, 0.9, 0.3 * k, "bandpass", 300, 3000, 1); }],
    salto: [0.25, (c, o, t, k) => { notaAudio(c, o, t, varia(260), 620, 0.2, "sine", 0.3 * k); }],
    pop: [0.12, (c, o, t, k) => { notaAudio(c, o, t, 600, 1400, 0.08, "sine", 0.35 * k); }],
    acqua: [0.4, (c, o, t, k) => { soffioAudio(c, o, t, 0.35, 0.5 * k, "bandpass", 2400, 700, 1.4); }],
    gelo: [0.6, (c, o, t, k) => { for (let i = 0; i < 5; i++) notaAudio(c, o, t + i * 0.05, varia(2400, 0.2), varia(2600, 0.2), 0.12, "sine", 0.1 * k); soffioAudio(c, o, t, 0.5, 0.15 * k, "highpass", 4000, 6000); }],
    fiamma: [0.8, (c, o, t, k) => { soffioAudio(c, o, t, 0.75, 0.55 * k, "lowpass", 700, 1500, 0.9); }],
    onda: [1, (c, o, t, k) => { notaAudio(c, o, t, 140, 70, 0.95, "sawtooth", 0.16 * k, 0.04); soffioAudio(c, o, t, 0.9, 0.35 * k, "bandpass", 1200, 400, 1.2); }],
    jet: [0.7, (c, o, t, k) => { soffioAudio(c, o, t, 0.65, 0.4 * k, "bandpass", 400, 1600, 1); }],
    tuono: [2.2, (c, o, t, k) => { soffioAudio(c, o, t, 0.12, 0.8 * k, "highpass", 2000, 2000); soffioAudio(c, o, t + 0.05, 2, 0.9 * k, "lowpass", 500, 50, 0.5); }],
    clic: [0.06, (c, o, t, k) => { notaAudio(c, o, t, 1500, 1100, 0.04, "square", 0.08 * k); }],
    moneta: [0.35, (c, o, t, k) => { notaAudio(c, o, t, 988, 988, 0.08, "square", 0.1 * k); notaAudio(c, o, t + 0.07, 1319, 1319, 0.25, "square", 0.1 * k); }],
    premio: [0.6, (c, o, t, k) => { [523, 659, 784, 1047].forEach((f, i) => notaAudio(c, o, t + i * 0.07, f, f, 0.3, "triangle", 0.2 * k)); }],
    via: [0.9, (c, o, t, k) => { [392, 392, 523].forEach((f, i) => notaAudio(c, o, t + i * 0.22, f, f, i === 2 ? 0.5 : 0.16, "square", 0.12 * k)); }],
    vittoria: [1.1, (c, o, t, k) => { [523, 659, 784, 1047, 784, 1047].forEach((f, i) => notaAudio(c, o, t + i * 0.1, f, f, i === 5 ? 0.5 : 0.12, "square", 0.11 * k)); }],
    vita: [0.9, (c, o, t, k) => { [440, 349, 262].forEach((f, i) => notaAudio(c, o, t + i * 0.16, f, f * 0.97, 0.3, "triangle", 0.3 * k)); }],
    ultima: [1.2, (c, o, t, k) => { for (let i = 0; i < 2; i++) { notaAudio(c, o, t + i * 0.5, 70, 50, 0.16, "sine", 0.9 * k); notaAudio(c, o, t + i * 0.5 + 0.18, 64, 45, 0.16, "sine", 0.7 * k); } }],
    salvo: [1.2, (c, o, t, k) => { [392, 523, 659, 784, 1047].forEach((f, i) => notaAudio(c, o, t + i * 0.08, f, f, 0.5, "triangle", 0.22 * k)); }],
    fine: [1.6, (c, o, t, k) => { [392, 370, 349, 262].forEach((f, i) => notaAudio(c, o, t + i * 0.3, f, f * (i === 3 ? 0.9 : 1), i === 3 ? 0.9 : 0.26, "triangle", 0.28 * k)); }],
    scudo: [0.6, (c, o, t, k) => { notaAudio(c, o, t, 300, 600, 0.5, "sine", 0.25 * k, 0.03); notaAudio(c, o, t, 450, 900, 0.5, "triangle", 0.12 * k, 0.03); }],
    cura: [0.6, (c, o, t, k) => { [660, 880, 1100].forEach((f, i) => notaAudio(c, o, t + i * 0.09, f, f * 1.02, 0.3, "sine", 0.2 * k)); }],
  };
  // Il volume di ogni famiglia, misurato: registrati tutti in fila (`__ring.provaSuoni` in un
  // OfflineAudioContext) i fendenti, il jetpack e le fanfare uscivano un terzo degli altri.
  const VOLUMI_AUDIO = { taglio: 3, bip: 2.5, jet: 3, moneta: 3, via: 3.5, vittoria: 3.5, fiamma: 2.5, soffio: 2, potenza: 2.5, carica: 2,
                         onda: 1.8, morso: 2, acqua: 1.6, premio: 1.8, preso: 1.5, salvo: 1.6, fine: 1.5, cura: 1.8, clic: 1.5 };
  // Le parole del ring, raggruppate per famiglia (la parola italiana, prima della traduzione).
  const PAROLE_AUDIO = [
    [/^(POW|BAM|SBAM|TUMP|ZOT|PAF|BONK|TIÈ|ORA|DAI|STRIKE|GRAH)!/, "pugno"],
    [/^(CLANG|TING|TZING|PARATO)!/, "metallo"],
    [/^(SLASH|SWISH|WHOOSH|FIUU|MULINELLO)!/, "taglio"],
    [/^(FWOOSH)!/, "fiamma"],
    [/^(BOOM|BOOOM|KABOOM|KA-BOOOM|KRAK|CRASH|CREPA|METEORA)!/, "boom"],
    [/^BANG!/, "sparo"],
    [/^ZAAAP!/, "zap"],
    [/^(GNAM|CHOMP)!/, "morso"],
    [/^(SPLAT|SLURP)!/, "splat"],
    [/^(PUFF|COFF|PTUI)!/, "soffio"],
    [/^(DRIIN|TRIIN|BIP|NOTIFICA|BZZT|TIC|CLICK)!/, "bip"],
    [/^(SBONK|SLAP|TONF|CRACK|OPS|SCIVOLONE)!/, "tonfo"],
    [/^K\.O\.!/, "ko"],
    [/^PRESO!/, "preso"],
    [/^MANCATO!/, "mancato"],
    [/^MIRA!/, "carica"],
    [/^(SOVRACCARICO|COLOSSO|GRANDE ALBERO|CAVALIERE|SFERA FINALE|COLPO FINALE)/, "potenza"],
    [/^(SU|HOP|OPLÀ|VAI|CAMBIO|CINQUE)!/, "salto"],
    [/^POP!/, "pop"],
    [/^SPLASH!/, "acqua"],
    [/^BRRR!/, "gelo"],
    [/^ULTIMA POSSIBILIT/, "ultima"],
    [/^SALVO!/, "salvo"],
    [/^-1 /, "vita"],
  ];
  function suonaParola(testo, x, grande) {
    if (!audio.acceso) return;
    const t = String(testo);
    for (const [re, nome] of PAROLE_AUDIO) if (re.test(t)) { suona(nome, x, grande ? 1.2 : 1); return; }
  }
  function suona(nome, x, forza) {
    if (!audio.acceso || !SUONI_AUDIO[nome]) return false;
    const c = preparaAudio();
    if (!c || c.state === "closed") return false;
    if (passi - (audio.ultimo[nome] === undefined ? -1e9 : audio.ultimo[nome]) < AUDIO.pausa) return false;
    audio.finiscono = audio.finiscono.filter((p) => p > passi);
    if (audio.finiscono.length >= AUDIO.voci && nome !== "ko" && nome !== "fine" && nome !== "vita") return false;
    audio.ultimo[nome] = passi;
    const [dur, ricetta] = SUONI_AUDIO[nome];
    try {
      ricetta(c, canaleAudio(x), c.currentTime + 0.005, Math.max(0.2, Math.min(1.6, forza || 1)) * (VOLUMI_AUDIO[nome] || 1));
      audio.finiscono.push(passi + Math.ceil(dur * 60));
    } catch (errore) { return false; }
    return true;
  }
  // ·· I suoni che durano ··
  function anello(nome, crea) {
    if (audio.anelli[nome]) return audio.anelli[nome];
    const c = preparaAudio();
    if (!c) return null;
    try { audio.anelli[nome] = crea(c); } catch (errore) { audio.anelli[nome] = null; }
    return audio.anelli[nome];
  }
  function fermaAnello(nome) {
    const a = audio.anelli[nome];
    if (!a) return;
    try { for (const s of a.fonti) s.stop(); } catch (errore) { /* già fermo */ }
    audio.anelli[nome] = null;
  }
  // Un rumore continuo filtrato (pioggia, vento), o una nota continua (buco nero, mira).
  const anelloRumore = (filtro, f, q) => (c) => {
    const s = c.createBufferSource(), fl = c.createBiquadFilter(), g = c.createGain();
    s.buffer = audio.rumore; s.loop = true; fl.type = filtro; fl.frequency.value = f; fl.Q.value = q; g.gain.value = 0;
    s.connect(fl); fl.connect(g); g.connect(audio.uscita); s.start();
    return { fonti: [s], g, fl };
  };
  const anelloNota = (tipo, f) => (c) => {
    const o = c.createOscillator(), g = c.createGain();
    o.type = tipo; o.frequency.value = f; g.gain.value = 0;
    o.connect(g); g.connect(audio.uscita); o.start();
    return { fonti: [o], g, o };
  };
  function livelloAnello(nome, crea, quanto, imposta) {
    if (!(quanto > 0.001) && !audio.anelli[nome]) return;
    const a = anello(nome, crea);
    if (!a) return;
    const t = audio.ctx.currentTime;
    a.g.gain.setTargetAtTime(Math.max(0, quanto), t, 0.12);
    if (imposta) imposta(a, t);
    if (!(quanto > 0.001)) { a.spento = (a.spento || 0) + 1; if (a.spento > 40) fermaAnello(nome); } else a.spento = 0;
  }
  let fulminiSentiti = new WeakSet();
  // Ogni sei passi: pioggia, vento, buco nero, la nota della mira; e i tuoni dei fulmini nuovi.
  function aggiornaAudio() {
    if (!audio.acceso || !audio.ctx || passi % 6) return;
    for (const z of fulmini) if (!fulminiSentiti.has(z)) { fulminiSentiti.add(z); suona("tuono", z.x, z.cielo ? 1.2 : 0.8); }
    livelloAnello("pioggia", anelloRumore("bandpass", 1800, 0.6), piovendo ? 0.09 : 0);
    livelloAnello("vento", anelloRumore("lowpass", 500, 1.5), uragano ? 0.16 : 0,
                  (a, t) => a.fl.frequency.setTargetAtTime(380 + 260 * Math.sin(passi * 0.05), t, 0.3));
    livelloAnello("buco", anelloNota("sine", 52), buco ? 0.32 : 0, (a, t) => a.o.frequency.setTargetAtTime(48 + 10 * Math.sin(passi * 0.08), t, 0.2));
    // La mira canta: la nota sale quando la linea punta in alto, e si alza ancora quando aggancia qualcuno.
    livelloAnello("mira", anelloNota("triangle", 440), mira ? 0.07 : 0, (a, t) => {
      if (!mira) return;
      const k = (mira.a + MIRA.su) / (MIRA.su + MIRA.giu);       // 0 in alto, 1 in basso
      a.o.frequency.setTargetAtTime(880 - 420 * k, t, 0.04);
    });
  }

  let costume = "nessuno", tavolozza = null;
  // IL TEMPO DI GARA (01/10/2026, su richiesta): il primo minuto è
  // tranquillo (niente eventi né jetpack, solo telefoni e orologi, al massimo
  // due in giro) perché chi apre il sito deve poterlo usare. Dopo 60 secondi
  // si sblocca l'arsenale: tablet, portatili, eventi, jetpack, il pieghevole
  // della mela. Dopo 70 arrivano anche pistole e spade (da cartone animato).
  const CALMA = 60 * 60, ARMI = 70 * 60;
  let tempo = 0, prossimaArma = 0, prossimoDuo = 0, prossimaBombaRobot = 0, proiettili = [], pezzi = [];
  // Gli imprevisti scelti a mano dalla tendina (o arrivati a sorpresa).
  let acquazzone = false, uragano = null, gravitaScelta = 1, sorprese = true;
  // Il tema natalizio è di tutto il sito (tasto nella testata, `natale.js`):
  // ai lottatori dà il cappellino rosso e le palle di neve.
  const radiceNatale = document.documentElement;
  let natale = !!(radiceNatale && radiceNatale.classList && radiceNatale.classList.contains && radiceNatale.classList.contains("natale"));
  window.addEventListener("mut:natale", (e) => { natale = !!(e && e.detail && e.detail.acceso); });
  let arti = [], macchie = [], cumulo = 0, danniBordi = [], testataBasso = 0;
  // GLI IMPREVISTI RIFATTI (05/10/2026, su richiesta). La pioggia ha gocce sue
  // (non contano più fra le particelle), il terremoto arriva con un vulcano che
  // erutta, e piovono meteoriti. Vedi «Il meteo» e «Terremoto ed eruzione».
  let gocce = [], spruzzi = [], bagnato = 0, piovendo = false, pioveDa = 0, pioggiaFino = 0, prossimoLampo = 300;
  let sisma = null, lapilli = [], colate = [];
  let meteore = [], sciame = null, bruciature = [];
  let paginaScura = false;
  // Gravità: verso il basso (1) o verso il tetto (-1, «sottosopra»).
  let verso = 1;
  // Barre della vita e modalità «super guerrieri»: si scelgono dalla tendina.
  let barreVita = false, anime = false;
  // LO STILE dei lottatori (02/10/2026): "" i soliti picchiatori, oppure
  // super guerrieri, maghi, duellanti. `anime` resta il motore a energia
  // (volo, onde, teletrasporti): lo usano i guerrieri e i maghi.
  const STILI = ["guerrieri", "maghi", "lame"];
  let stile = "";
  try {
    barreVita = deposito.getItem("mut-ring-barre") === "on";
    const salvato = deposito.getItem("mut-ring-stile");
    stile = STILI.indexOf(salvato) >= 0 ? salvato : (deposito.getItem("mut-ring-anime") === "on" ? "guerrieri" : "");
  } catch (errore) { /* restano spente */ }
  if (!libero("guerrieri")) stile = "";
  anime = stile === "guerrieri" || stile === "maghi";
  const maghi = () => stile === "maghi", lame = () => stile === "lame";
  // Con uno stile acceso in campo non ci sono più il robot e la mela, ma due
  // personaggi inventati per quel tema (vedi ASPETTI): hanno un corpo umano
  // sullo scheletro del robot. `tipo` resta il lato: "robot" a sinistra,
  // "mela" a destra (punteggio, scommesse, quel che hanno imparato).
  const eMela = (f) => f.tipo === "mela" && !stile, eRobot = (f) => f.tipo === "robot" && !stile;
  // Schizzi e arti staccati: si possono spegnere dalla tendina.
  let cruento = true;
  try { cruento = deposito.getItem("mut-ring-cruento") !== "off"; } catch (errore) { /* resta acceso */ }
  // I danni alla striscia delle notizie (crepe, buchi), e il colore dello sfondo.
  let danni = [], sfondo = "#f2f2f2", barraAlta = 44;

  const caso = (a, b) => a + Math.random() * (b - a);
  const scegli = (voci) => {
    let totale = 0;
    for (const v of voci) totale += v[0];
    let r = Math.random() * totale;
    for (const v of voci) { if ((r -= v[0]) <= 0) return v[1]; }
    return voci[voci.length - 1][1];
  };

  // --- Il cervello: ogni lottatore impara dai colpi ----------------------
  // Ogni mossa ha un peso che sale quando va a segno (o quando para) e scende
  // quando si prende un colpo mentre la si fa o quando viene parata. Chi viene
  // colpito impara a pararsi e a schivare di più. I pesi rientrano piano verso
  // 1, così la varietà non si perde. L'esperienza dà il livello, e ogni livello
  // sblocca qualcosa: 2 serie di colpi, 3 contrattacco dopo una parata, 4
  // sfida chi vola, 5 più telefoni. Resta nel browser (nessun dato al server).
  const CHIAVE_CERVELLO = "mut-ring-cervello";
  const MOSSE = ["pugno", "diretto", "montante", "calcio", "para", "schiva", "salto", "provoca", "indietro", "presa"];
  const LIVELLO_MAX = 8;
  let cervello = {};
  function pulisciCervello(grezzo) {
    const puliti = {};
    for (const tipo of ["robot", "mela"]) {
      const c = grezzo && typeof grezzo === "object" ? grezzo[tipo] : null;
      const pesi = {};
      for (const m of MOSSE) {
        const v = c && c.pesi ? Number(c.pesi[m]) : 1;
        pesi[m] = Number.isFinite(v) ? Math.max(0.4, Math.min(2.6, v)) : 1;
      }
      const exp = c ? Number(c.exp) : 0;
      puliti[tipo] = { exp: Number.isFinite(exp) ? Math.max(0, Math.min(5000, Math.floor(exp))) : 0, pesi };
    }
    return puliti;
  }
  try { cervello = pulisciCervello(JSON.parse(deposito.getItem(CHIAVE_CERVELLO) || "null")); }
  catch (errore) { cervello = pulisciCervello(null); }
  let daSalvare = 0;
  function salvaCervello(subito) {
    if (!subito && ++daSalvare < 10) return;
    daSalvare = 0;
    try { deposito.setItem(CHIAVE_CERVELLO, JSON.stringify(cervello)); } catch (errore) { /* pazienza */ }
  }
  const livelloDi = (tipo) => (cervello[tipo] ? Math.min(LIVELLO_MAX, Math.floor(Math.sqrt(cervello[tipo].exp / 3))) : 0);
  const pesoMossa = (f, mossa) => (cervello[f.tipo] && cervello[f.tipo].pesi[mossa]) || 1;
  function impara(f, mossa, esito, esperienza) {
    const c = f && cervello[f.tipo];
    if (!c || MOSSE.indexOf(mossa) < 0) return;
    const prima = livelloDi(f.tipo);
    for (const m of MOSSE) c.pesi[m] = 1 + (c.pesi[m] - 1) * 0.994;
    c.pesi[mossa] = Math.max(0.4, Math.min(2.6, c.pesi[mossa] * (esito > 0 ? 1.08 : 0.94)));
    if ((mossa === "para" || mossa === "schiva") && c.pesi[mossa] > 1.8) c.pesi[mossa] = 1.8;
    c.exp = Math.min(5000, c.exp + (esperienza || 0));
    const dopo = livelloDi(f.tipo);
    if (dopo > prima) {
      // Livello nuovo: scintille verdi e un po' più di fiuto.
      f.furbo = Math.min(2, f.furbo + 0.08);
      const b = f.p && f.p.testa;
      if (b) scintille(b.x, b.y - 10 * S, 14, "#5fe08a");
      salvaCervello(true);
    } else salvaCervello(false);
  }
  // Il carattere di ogni round: casuale, ma chi ha esperienza è più furbo.
  function nuovoCarattere(f) {
    const l = livelloDi(f.tipo);
    f.aggr = caso(0.75, 1.3) + 0.02 * l;
    f.furbo = Math.min(2, caso(0.6, 1.4) + 0.07 * l);
  }

  function leggiColori() {
    const stile = getComputedStyle(document.documentElement);
    inchiostro = (stile.getPropertyValue("--ink") || "").trim() || "#201e1d";
    accento = (stile.getPropertyValue("--accent") || "").trim() || "#ec3013";
    try {
      const c = document.body && getComputedStyle(document.body).backgroundColor;
      if (c && c !== "rgba(0, 0, 0, 0)" && c !== "transparent") sfondo = c;
    } catch (errore) { /* resta il grigio chiaro */ }
    // Su una pagina scura la pioggia si disegna chiara, sennò non si vede.
    const rgb = /(\d+)[^\d]+(\d+)[^\d]+(\d+)/.exec(sfondo || "");
    paginaScura = !!rgb && (0.299 * rgb[1] + 0.587 * rgb[2] + 0.114 * rgb[3]) < 110;
  }

  // --- Gli elementi della pagina come corpi solidi ----------------------
  // Le righe di testo una per una (non il riquadro del paragrafo, che è
  // largo quanto la colonna anche quando la riga è corta), più i
  // controlli — campi, tasti, immagini — e la testata intera. Tutto in
  // coordinate della finestra, come il canvas.
  const SOLIDI = "input, button, select, textarea, img";
  const RIGA_MIN = 32;
  const FUORI = ".ultimora, script, style, canvas, noscript, datalist, [hidden], .sr-only";

  function riquadroUtile(r) {
    return r && r.width >= 10 && r.height >= 6 && r.height < 240 &&
      r.bottom > -40 && r.top < H + 40 && r.right > 0 && r.left < W;
  }

  function rileva() {
    const lista = [];
    const aggiungi = (r) => {
      if (riquadroUtile(r)) lista.push({ l: r.left, t: r.top, r: r.right, b: r.bottom });
    };
    const testata = document.querySelector(".testata");
    if (testata && testata.getBoundingClientRect) {
      const rt = testata.getBoundingClientRect();
      aggiungi(rt);
      testataBasso = rt.bottom > 0 && rt.bottom < H * 0.3 ? rt.bottom : 0;
    }

    const radice = document.body;
    if (radice && radice.querySelectorAll) {
      for (const el of radice.querySelectorAll(SOLIDI)) {
        if (el.closest && (el.closest(FUORI) || (testata && el.closest(".testata")))) continue;
        aggiungi(el.getBoundingClientRect());
      }
    }
    if (radice && document.createTreeWalker && document.createRange) {
      const giro = document.createTreeWalker(radice, 4 /* NodeFilter.SHOW_TEXT */);
      const intervallo = document.createRange();
      let nodo;
      while ((nodo = giro.nextNode()) && lista.length < 220) {
        if (!nodo.nodeValue || !nodo.nodeValue.trim()) continue;
        const padre = nodo.parentElement;
        if (!padre || padre.closest(FUORI) || padre.closest(SOLIDI) ||
            (testata && padre.closest(".testata"))) continue;
        intervallo.selectNodeContents(nodo);
        // Le scritte piccole (note, didascalie, righe di testo corrente) non
        // sono solide: i lottatori ci si incastravano di continuo.
        for (const r of intervallo.getClientRects()) if (r.height >= RIGA_MIN) aggiungi(r);
      }
    }
    // Le righe vicine sulla stessa linea diventano un pezzo solo: meno
    // calcoli e niente fessure fra una parola e l'altra dove incastrarsi.
    lista.sort((a, b) => a.t - b.t || a.l - b.l);
    const uniti = [];
    for (const o of lista) {
      const u = uniti[uniti.length - 1];
      if (u && Math.abs(u.t - o.t) < 4 && Math.abs(u.b - o.b) < 4 && o.l <= u.r + 10) {
        u.r = Math.max(u.r, o.r); u.l = Math.min(u.l, o.l);
      } else uniti.push(Object.assign({}, o));
    }
    // E le righe dello stesso paragrafo diventano un blocco: fra una riga e
    // l'altra ci sono tre pixel, e un lottatore in piedi su una riga si
    // ritrovava col corpo dentro quella di sopra.
    const blocchi = [];
    for (const o of uniti) {
      const sopra = blocchi.find((u) => o.t - u.b < 9 && o.t >= u.t &&
        Math.min(u.r, o.r) - Math.max(u.l, o.l) > 0.3 * Math.min(u.r - u.l, o.r - o.l));
      if (sopra) {
        sopra.l = Math.min(sopra.l, o.l); sopra.r = Math.max(sopra.r, o.r); sopra.b = Math.max(sopra.b, o.b);
      } else blocchi.push(o);
    }
    ostacoli = blocchi.slice(0, 160);
    pavimento = barra && barra.getBoundingClientRect ? barra.getBoundingClientRect().top : H;
    if (barra && barra.getBoundingClientRect) barraAlta = barra.getBoundingClientRect().height || 44;
    if (!(pavimento > 0)) pavimento = H;
  }

  // --- Il corpo --------------------------------------------------------
  // Altezze in unità «a scala 1» sopra il punto d'appoggio; dx verso la faccia.
  const SCHELETRO = {
    testa: [62, 2, 7], collo: [50, 1, 3], bacino: [28, 0, 4],
    gomitoA: [42, 8, 2], manoA: [50, 13, 3], gomitoD: [41, 3, 2], manoD: [49, 8, 3],
    ginocchioA: [14, 6, 2], piedeA: [0, 8, 2.5], ginocchioD: [14, -3, 2], piedeD: [0, -8, 2.5],
  };
  const ASTE = [
    ["testa", "collo"], ["collo", "bacino"],
    ["collo", "gomitoA"], ["gomitoA", "manoA"], ["collo", "gomitoD"], ["gomitoD", "manoD"],
    ["bacino", "ginocchioA"], ["ginocchioA", "piedeA"], ["bacino", "ginocchioD"], ["ginocchioD", "piedeD"],
    // Due aste «di sostegno» invisibili: tengono la testa sopra il bacino e
    // le ginocchia separate, così la bambola non si accartoccia.
    ["testa", "bacino"], ["ginocchioA", "ginocchioD"],
  ];
  const TIRO = {
    testa: 0.16, collo: 0.2, bacino: 0.2, gomitoA: 0.18, manoA: 0.26,
    gomitoD: 0.18, manoD: 0.24, ginocchioA: 0.2, piedeA: 0.26, ginocchioD: 0.2, piedeD: 0.26,
  };

  // Le mani della mela stanno più in basso di quelle del robot: appena sotto
  // gli occhi, dove una mela ha il «petto», non all'altezza della testa.
  const SPALLA_MELA = ["gomitoA", "manoA", "gomitoD", "manoD"];
  const ABBASSA_MELA = 6;
  // A riposo le mani della mela stanno ai FIANCHI del frutto, una davanti e
  // una dietro, non sulla faccia.
  const LATI_MELA = { gomitoA: 19, manoA: 23, gomitoD: -18, manoD: -22 };
  // Il frutto è largo: i punti del busto hanno un raggio più grande, così
  // urti e colpi coincidono con quello che si vede.
  const RAGGI_MELA = { testa: 6, collo: 10, bacino: 8 };
  let scheletroMela = null;
  function scheletro(tipo) {
    if (tipo !== "mela" || stile) return SCHELETRO;
    if (scheletroMela) return scheletroMela;
    const q = {};
    for (const nome in SCHELETRO) {
      q[nome] = SCHELETRO[nome].slice();
      if (nome in LATI_MELA) { q[nome][1] = LATI_MELA[nome]; }
      if (nome in RAGGI_MELA) { q[nome][2] = RAGGI_MELA[nome]; }
    }
    return (scheletroMela = q);
  }

  function crea(tipo, x, dir, base) {
    if (base === undefined) base = pavimento;
    const f = {
      tipo, dir, cx: x, base, supporto: null, p: {}, aste: [],
      forza: 1, ko: 0, rialzo: 0, stordito: 0, danni: 0, soglia: Math.round(caso(3, 6)),
      azione: null, t: 0, durata: 0, colpito: false, pensa: caso(20, 60), meta: x,
      passo: 0, dolore: 0, preso: null, scalata: null, inVolo: false, botta: 0, fantasma: false,
      aggr: caso(0.75, 1.3), furbo: caso(0.6, 1.4), furia: 0, tel: null, prendiTel: null, polv: 0,
      combo: 0, jet: 0, volaY: 0, caos: 0, giro: 0, rot: 0, ix: 0, iy: 0, fiamma: 0,
      arma: null, colpiArma: 0, tiene: null, tenuto: null, mossaPresa: null,
      paracadute: 0, para: 0, scendeApposta: 0, daBallare: false, ballo: null, esploso: null,
      segni: [], staccati: {}, palla: false, uraganoCd: 0,
      ki: 0, potenziato: 0, onda: null, koVero: false, vitaVista: 1, vitaScia: 1,
      accecato: 0, cratere: null, sfera: null,
      forma: 0, gelato: 0, ghiaccio: null, piccolo: 0, scala: 1, lama: null, caduta: null, daScatto: null,
      trema: 0, scotta: 0, fuga: null, corsa: 0, rivale: null, piano: null,
      colpoMano: 0, lanciato: 0, volo: false, scatto: 0, bersaglio: null, recupero: 0, insegui: 0, catena: 0, vel: null, morsi: [], taglio: null,
    };
    f.furbo = Math.min(2, f.furbo + 0.07 * livelloDi(tipo));
    const sch = scheletro(tipo);
    for (const nome in sch) {
      let [h, dx, r] = sch[nome];
      if (tipo === "mela" && !stile && SPALLA_MELA.indexOf(nome) >= 0) h -= ABBASSA_MELA;
      const px = x + dx * dir * S, py = base - h * S - 2 * S;
      f.p[nome] = { x: px, y: py, ox: px, oy: py, r: r * S };
    }
    for (const [a, b] of ASTE) {
      const pa = f.p[a], pb = f.p[b];
      f.aste.push([pa, pb, Math.hypot(pa.x - pb.x, pa.y - pb.y)]);
    }
    return f;
  }

  function dimensiona() {
    const rapporto = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth || tela.clientWidth; H = window.innerHeight || tela.clientHeight;
    tela.width = Math.floor(W * rapporto); tela.height = Math.floor(H * rapporto);
    // DIMENSIONE IN PIXEL ESPLICITI, non `100vh`: su iPhone `100vh` è l'altezza
    // con le barre del browser ritirate, più alta dell'area visibile, e il
    // canvas veniva stirato — gli omini disegnati più in basso di dove la
    // fisica li metteva, quindi niente presa e niente urti (01/10/2026).
    if (tela.style) { tela.style.width = W + "px"; tela.style.height = H + "px"; }
    ctx.setTransform(rapporto, 0, 0, rapporto, 0, 0);
    S = Math.max(0.8, Math.min(1.2, W / 1100));
  }

  function avvia() {
    dimensiona();
    rileva();
    const centro = W / 2, scarto = Math.min(90 * S, W * 0.18);
    // PARTENZA SUL CAMPO DI RICERCA (01/10/2026, su richiesta): il ring
    // iniziale è il bordo alto della barra. Se i due ne escono cadono sulla
    // pagina e, prima o poi, sulle notizie in fondo.
    let cx0 = centro, base0 = pavimento;
    const campo = document.querySelector && document.querySelector(".ricerca-grande input");
    const rc = campo && campo.getBoundingClientRect ? campo.getBoundingClientRect() : null;
    if (rc && rc.width > 200 && rc.top > 60 && rc.top < pavimento - 90 && rc.left < W) {
      cx0 = (rc.left + rc.right) / 2; base0 = rc.top;
    }
    lottatori = [crea("robot", cx0 - scarto, 1, base0), crea("mela", cx0 + scarto, -1, base0)];
    if (lame()) for (const f of lottatori) accendiLama(f);
    fulmini = []; duello = 0; sfida = null; sfidaPausa = 0; orda = null;
    danni = [];
    scritte = []; telefoni = []; particelle = []; evento = null;
    creature = []; nubi = []; finale = null; mira = null; lampoMira = null; miraBuio = 0; centroMira = null;
    gocce = []; spruzzi = []; bagnato = 0; pioveDa = 0; pioggiaFino = 0; prossimoLampo = 300;
    if (sisma) fineSisma();
    lapilli = []; colate = []; meteore = []; sciame = null; bruciature = [];
    moltG = 1; ritmo = 1; daSpawnare = 0; fermoColpo = 0; scossa = 0; buco = null;
    fatale = null; fataleBuio = 0; fataleSacco = []; fataleRound = false; fataleDebito = 0; fataleVoluto = 0; prossimoRoundFatale();
    tempo = 0; proiettili = []; pezzi = []; arti = []; macchie = []; cumulo = 0; danniBordi = [];
    prossimoEvento = CALMA + Math.round(caso(120, 600));
    prossimaOrda = Math.round(caso(ORDA.prima[0], ORDA.prima[1]) * 60);
    prossimoTelefono = 360; prossimaArma = ARMI + Math.round(caso(0, 240));
    prossimoDuo = CALMA + Math.round(caso(400, 1500));
    prossimaBombaRobot = CALMA + Math.round(caso(900, 2100));
    // Il robot si presenta con un costume e un colore a caso a ogni caricamento.
    costume = scegli([[2, "nessuno"], [2, "ninja"], [2, "cuoco"], [2, "astronauta"],
                      [2, "mago"], [2, "pirata"], [2, "eroe"]]);
    tavolozza = scegli([[3, ["#2fae74", "#1c6f4a", "#7dffd2", "#154d34"]],
                        [1, ["#3b8fd9", "#1f5a99", "#a5e6ff", "#173f6b"]],
                        [1, ["#ec8a3a", "#a8571a", "#ffe9a8", "#6e3a10"]],
                        [1, ["#8a63d2", "#5a3b99", "#e6d4ff", "#3d2766"]]]);
    leggiColori();
  }

  // --- Dove poggia un lottatore ----------------------------------------
  // La superficie più alta sotto i suoi piedi, fra il pavimento (la
  // striscia) e gli elementi della pagina.
  function appoggio(f) {
    if (verso < 0) {
      // Sottosopra: si «poggia» sotto il tetto o sotto il bordo basso di un elemento.
      const piede = Math.min(f.p.piedeA.y, f.p.piedeD.y);
      let y = 0, chi = null;
      for (const o of ostacoli) {
        if (f.cx < o.l - 3 * S || f.cx > o.r + 3 * S) continue;
        if (o.b > piede + 10 * S) continue;
        if (o.b > y) { y = o.b; chi = o; }
      }
      return [y, chi];
    }
    const piede = Math.max(f.p.piedeA.y, f.p.piedeD.y);
    let y = pavimento, chi = null;
    for (const o of ostacoli) {
      if (f.cx < o.l - 3 * S || f.cx > o.r + 3 * S) continue;
      if (o.t < piede - 10 * S) continue;
      if (o.t < y) { y = o.t; chi = o; }
    }
    return [y, chi];
  }

  // --- Le pose ---------------------------------------------------------
  function posa(f) {
    const q = {}, sch = scheletro(f.tipo);
    for (const nome in sch) q[nome] = [sch[nome][0], sch[nome][1]];
    const e = f.durata ? Math.sin(Math.PI * Math.min(1, f.t / f.durata)) : 0;
    const respiro = Math.sin(f.passo * 0.5 + (f.tipo === "mela" ? 1.7 : 0)) * 0.8;
    q.bacino[0] += respiro; q.collo[0] += respiro; q.testa[0] += respiro;

    if (f.azione === "avanza" || f.azione === "indietro") {
      const ph = f.passo;
      q.piedeA = [Math.max(0, 5 * Math.cos(ph)), 8 + 7 * Math.sin(ph)];
      q.piedeD = [Math.max(0, -5 * Math.cos(ph)), -8 - 7 * Math.sin(ph)];
      q.ginocchioA = [14 + Math.max(0, 3 * Math.cos(ph)), 6 + 4 * Math.sin(ph)];
      q.ginocchioD = [14 + Math.max(0, -3 * Math.cos(ph)), -3 - 4 * Math.sin(ph)];
    }
    // Prima di colpire ci si carica un attimo all'indietro (anticipazione).
    const carica = COLPI[f.azione] ? Math.max(0, 1 - f.t / 5) : 0;
    switch (f.azione) {
      case "pugno":
        q.manoA = [52, 13 + 17 * e - 9 * carica]; q.gomitoA = [48, 9 + 9 * e - 7 * carica];
        q.collo[1] += 3 * e - 3 * carica; q.testa[1] += 4 * e - 3 * carica; break;
      case "solleva": {
        const k = Math.min(1, f.t / 7);
        q.manoA = [50 + 27 * k, 13 - 8 * k]; q.gomitoA = [44 + 14 * k, 8 - 2 * k];
        q.manoD = [49 + 26 * k, 8 - 9 * k]; q.gomitoD = [41 + 15 * k, 3 - 4 * k];
        break;
      }
      case "lancia": {
        if (f.t < 11) {
          const k = f.t / 11;
          q.manoA = [78, 4 - 12 * k]; q.gomitoA = [62, 3 - 6 * k];
          q.manoD = [75, -4 - 8 * k]; q.gomitoD = [60, -3 - 5 * k];
          q.collo[1] -= 4 * k; q.testa[1] -= 5 * k;
        } else {
          const k = Math.min(1, (f.t - 11) / 10);
          q.manoA = [78 - 24 * k, -8 + 36 * k]; q.gomitoA = [62 - 12 * k, -3 + 18 * k];
          q.manoD = [75 - 22 * k, -12 + 30 * k]; q.gomitoD = [60 - 12 * k, -8 + 16 * k];
          q.collo[1] += 5 * k; q.testa[1] += 6 * k;
        }
        break;
      }
      case "para":
        q.manoA = [58, 9]; q.gomitoA = [46, 11]; q.manoD = [56, 5]; q.gomitoD = [44, 6];
        q.collo[1] -= 2; q.testa[1] -= 2; q.bacino[0] -= 2; break;
      case "schiva":
        q.piedeA = [10, 6]; q.piedeD = [10, -8]; q.ginocchioA = [20, 6]; q.ginocchioD = [20, -4];
        q.collo[1] -= 6; q.testa[1] -= 8; break;
      case "diretto":
        q.manoD = [51, 8 + 22 * e]; q.gomitoD = [47, 5 + 12 * e];
        q.collo[1] += 4 * e; q.testa[1] += 5 * e; q.bacino[1] += 2 * e; break;
      case "montante":
        q.manoA = [44 + 26 * e, 10 + 9 * e]; q.gomitoA = [42 + 12 * e, 8 + 5 * e];
        q.bacino[0] -= 3 * e; break;
      case "calcio":
        q.piedeA = [8 + 20 * e, 8 + 20 * e]; q.ginocchioA = [14 + 12 * e, 7 + 11 * e];
        q.collo[1] -= 4 * e; q.testa[1] -= 5 * e; break;
      case "testata":
        // Senza braccia si colpisce di testa: indietro un attimo, poi tutta in avanti.
        q.collo = [q.collo[0] - 3 * e, q.collo[1] + 9 * e - 5 * carica]; q.testa = [q.testa[0] - 5 * e, q.testa[1] + 19 * e - 8 * carica];
        q.bacino[1] += 3 * e; q.piedeA = [0, 8 + 7 * e]; break;
      case "provoca":
        q.manoD = [58 + 6 * Math.sin(f.t * 0.6), -4]; q.gomitoD = [52, -4];
        q.bacino[0] += 2 * Math.abs(Math.sin(f.t * 0.3)); break;
      case "esulta":
        q.manoA = [80, 6]; q.gomitoA = [68, 7]; q.manoD = [80, -6]; q.gomitoD = [68, -7];
        break;
      case "salto":
        q.piedeA = [10, 9]; q.piedeD = [10, -7]; q.ginocchioA = [20, 9]; q.ginocchioD = [20, -2];
        break;
      // --- Le mosse in coppia contro l'orda (vedi «LE MOSSE IN COPPIA») ---
      case "sgabello": {
        // Piegato in avanti, mani sulle ginocchia: l'alleato gli salta sopra.
        const k = Math.min(1, f.t / 7, Math.max(0, (f.durata - f.t) / 7));
        q.bacino = [28 - 5 * k, -3 * k]; q.collo = [50 - 19 * k, 1 + 11 * k]; q.testa = [62 - 27 * k, 2 + 19 * k];
        q.manoA = [50 - 33 * k, 13 - 3 * k]; q.gomitoA = [42 - 16 * k, 8 + 5 * k]; q.manoD = [49 - 32 * k, 8 - 9 * k]; q.gomitoD = [41 - 16 * k, 3 + 1 * k];
        q.ginocchioA = [14 - 1 * k, 6 + 4 * k]; q.ginocchioD = [14 - 1 * k, -3 + 1 * k];
        break;
      }
      case "cavallina": {
        const c = f.coppia;
        if (c && c.h > 2 * S) {
          // In aria a gambe larghe, le mani che spingono sulla schiena dell'altro e poi si aprono.
          const u = c.u;
          q.piedeA = [9, 17]; q.piedeD = [9, -15]; q.ginocchioA = [21, 13]; q.ginocchioD = [21, -9];
          q.manoA = [34 + 34 * u, 15 + 8 * u]; q.gomitoA = [42 + 14 * u, 11 + 4 * u]; q.manoD = [33 + 34 * u, 5 - 14 * u]; q.gomitoD = [41 + 14 * u, 2 - 8 * u];
          q.collo[1] += 6 - 4 * u; q.testa[1] += 9 - 6 * u;
        } else if (c && !c.fatto) {
          // La rincorsa.
          const ph = f.passo;
          q.piedeA = [Math.max(0, 6 * Math.cos(ph)), 9 + 8 * Math.sin(ph)]; q.piedeD = [Math.max(0, -6 * Math.cos(ph)), -8 - 8 * Math.sin(ph)];
          q.collo[1] += 5; q.testa[1] += 7; q.manoA = [44, 20]; q.manoD = [42, 12];
        } else {
          // Atterrato: giù sulle ginocchia, un pugno a terra.
          q.bacino[0] -= 9; q.collo = [36, 6]; q.testa = [46, 10]; q.manoA = [8, 16]; q.gomitoA = [24, 13]; q.manoD = [40, -12]; q.gomitoD = [36, -4];
          q.ginocchioA = [12, 12]; q.ginocchioD = [8, -6]; q.piedeA = [0, 10]; q.piedeD = [0, -12];
        }
        break;
      }
      case "trottola": {
        // La giravolta schiena contro schiena: braccia larghe, chi passa sopra raccoglie le gambe.
        const c = f.coppia, su = c && c.salta;
        q.manoA = [54, 24]; q.gomitoA = [51, 13]; q.manoD = [54, -20]; q.gomitoD = [50, -9];
        if (su) { q.piedeA = [8, 8]; q.piedeD = [8, -6]; q.ginocchioA = [19, 9]; q.ginocchioD = [19, -3]; }
        else { const giu = 9 * e; q.bacino[0] -= giu * 0.6; q.collo[0] -= giu; q.testa[0] -= giu; q.manoA[0] -= giu; q.manoD[0] -= giu; q.gomitoA[0] -= giu; q.gomitoD[0] -= giu; }
        break;
      }
      case "insieme": {
        // Si carica (le mani al petto, giù sulle gambe) e poi la spinta a due mani in fuori.
        const carico = Math.min(1, f.t / 12), spinge = f.t < 13 ? 0 : Math.min(1, (f.t - 13) / 4) * Math.max(0, 1 - Math.max(0, f.t - 24) / 12);
        q.bacino[0] -= 5 * carico * (1 - spinge); q.collo = [50 - 4 * carico + 2 * spinge, 1 - 4 * carico + 9 * spinge]; q.testa = [62 - 4 * carico + 2 * spinge, 2 - 5 * carico + 11 * spinge];
        q.manoA = [45 + 4 * spinge, 6 * (1 - spinge) + 30 * spinge]; q.gomitoA = [42 + 5 * spinge, 9 + 9 * spinge];
        q.manoD = [43 + 2 * spinge, 2 * (1 - spinge) + 27 * spinge]; q.gomitoD = [40 + 3 * spinge, 4 + 10 * spinge];
        q.ginocchioA = [14 - 2 * carico, 8 + 2 * spinge]; q.piedeA = [0, 10 + 5 * spinge];
        break;
      }
      case "fionda": {
        // Il lancio da bocce: il braccio indietro e poi avanti, basso.
        const k = f.t < 10 ? f.t / 10 : 1, va = f.t < 10 ? 0 : Math.min(1, (f.t - 10) / 6);
        q.bacino[0] -= 6 * k; q.collo = [50 - 10 * k, 1 + 6 * k + 8 * va]; q.testa = [62 - 12 * k, 2 + 9 * k + 10 * va];
        q.manoA = [26 - 6 * va, -14 * (1 - va) + 30 * va]; q.gomitoA = [34 - 4 * va, -5 * (1 - va) + 16 * va];
        q.manoD = [40, -10]; q.gomitoD = [40, -3]; q.ginocchioA = [12, 10]; q.piedeA = [0, 13];
        break;
      }
      case "bolide": {
        const c = f.coppia;
        if (c && !c.fatto) {
          // Raccolto a palla, che rotola: i pezzi del corpo girano intorno al centro.
          const giro = c.gira || 0, co = Math.cos(giro), si = Math.sin(giro);
          const palla = { bacino: [-2, -4], collo: [5, 3], testa: [1, 10], gomitoA: [0, 8], manoA: [-4, 9], gomitoD: [3, 7], manoD: [-2, 6],
                          ginocchioA: [5, 8], piedeA: [-6, 5], ginocchioD: [3, 6], piedeD: [-7, 2] };
          for (const n in palla) q[n] = [13 + palla[n][0] * co - palla[n][1] * si, palla[n][0] * si + palla[n][1] * co];
        }
        break;
      }
      case "fiammata": {
        // Tutt'e due le mani sull'arma, piantato sulle gambe: la vampata spinge indietro.
        const sp = f.t > 6 && f.t < 48 ? Math.sin(f.t * 0.7) * 1.2 : 0;
        q.manoA = [50 - sp, 22]; q.gomitoA = [44 - sp, 13]; q.manoD = [40 - sp, 16]; q.gomitoD = [36 - sp, 8];
        q.piedeA = [0, 12]; q.piedeD = [0, -12]; q.bacino[0] -= 2; q.testa[1] += 1;
        break;
      }
      case "spara": {
        // Braccio teso verso l'avversario; al colpo, il rinculo.
        const rinculo = f.t >= 10 && f.t < 18 ? (18 - f.t) / 8 : 0;
        q.manoA = [50 + 3 * rinculo, 25 - 5 * rinculo]; q.gomitoA = [48 + 1.5 * rinculo, 15 - 3 * rinculo];
        q.manoD = [47, 12]; q.gomitoD = [42, 6]; q.testa[1] += 1;
        break;
      }
      case "fendente":
        if (f.t < 10) {
          const k = f.t / 10;
          q.manoA = [56 + 24 * k, 12 - 14 * k]; q.gomitoA = [50 + 14 * k, 7 - 7 * k]; q.collo[1] -= 2 * k;
        } else {
          const k = Math.min(1, (f.t - 10) / 6);
          q.manoA = [80 - 40 * k, -2 + 26 * k]; q.gomitoA = [64 - 20 * k, 0 + 15 * k];
          q.collo[1] += 4 * k; q.testa[1] += 5 * k; q.piedeA = [0, 8 + 6 * k];
        }
        break;
      case "affondo": {
        // Un passo avanti e la lama dritta al petto.
        const a = (f.t < 8 ? f.t / 8 : 1) * (f.t > 14 ? 1 - Math.min(1, (f.t - 14) / 8) : 1);
        q.manoA = [50 - 2 * a, 10 + 24 * a - 8 * carica]; q.gomitoA = [49, 6 + 12 * a - 6 * carica];
        q.manoD = [44, -8]; q.gomitoD = [46, -4];
        q.piedeA = [0, 8 + 8 * a]; q.ginocchioA = [13, 8 + 6 * a]; q.collo[1] += 4 * a; q.testa[1] += 5 * a; q.bacino[1] += 2 * a;
        break;
      }
      case "rovescio":
        // Dal basso verso l'alto, di rovescio.
        if (f.t < 9) { const k = f.t / 9; q.manoA = [44 - 16 * k, 10 - 4 * k]; q.gomitoA = [44 - 6 * k, 8]; q.collo[1] -= 2 * k; }
        else {
          const k = Math.min(1, (f.t - 9) / 6);
          q.manoA = [28 + 50 * k, 6 + 26 * Math.sin(Math.PI * 0.75 * k)]; q.gomitoA = [38 + 26 * k, 8 + 10 * k];
          q.collo[1] += 3 * k; q.testa[1] += 3 * k;
        }
        break;
      case "scattoLama":
        if (f.t < 10) {
          // Raccolto, la lama al fianco.
          q.bacino[0] -= 5; q.collo[0] -= 6; q.testa[0] -= 6; q.collo[1] += 3; q.testa[1] += 4;
          q.ginocchioA = [11, 10]; q.ginocchioD = [11, -6]; q.piedeA = [0, 12]; q.piedeD = [0, -10];
          q.manoA = [34, -8]; q.gomitoA = [40, -2]; q.manoD = [36, 4]; q.gomitoD = [42, 4];
        } else if (f.t < 15) {
          // Lo scatto: tutto proteso in avanti.
          q.manoA = [46, 30]; q.gomitoA = [48, 16]; q.collo[1] += 7; q.testa[1] += 9;
          q.piedeD = [2, -18]; q.ginocchioD = [14, -8]; q.piedeA = [0, 10];
        } else {
          // Fermo, la lama bassa: l'effetto del taglio arriva un attimo dopo.
          q.manoA = [30, 22]; q.gomitoA = [40, 12]; q.manoD = [40, -4]; q.gomitoD = [44, -2];
          q.piedeA = [0, 12]; q.piedeD = [0, -8]; q.bacino[0] -= 2;
        }
        break;
      case "lancioLama":
        if (f.t < 14) { const k = f.t / 14; q.manoA = [60 + 12 * k, 4 - 18 * k]; q.gomitoA = [54 + 6 * k, 2 - 8 * k]; q.collo[1] -= 3 * k; }
        else { const k = Math.min(1, (f.t - 14) / 7); q.manoA = [72 - 24 * k, -14 + 42 * k]; q.gomitoA = [60 - 10 * k, -6 + 20 * k]; q.collo[1] += 4 * k; q.testa[1] += 5 * k; }
        break;
      case "pressa": {
        const tr = Math.sin(f.t * 1.3) * 0.8;
        q.manoA = [57 + tr, 21]; q.gomitoA = [50, 12]; q.manoD = [53 + tr, 18]; q.gomitoD = [46, 9];
        q.collo[1] += 4; q.testa[1] += 5; q.piedeD = [0, -14]; q.ginocchioD = [13, -8]; q.piedeA = [0, 9]; q.bacino[0] -= 2;
        break;
      }
      case "trasforma":
        if (f.t < 70) {
          // Pugni stretti, ginocchia piegate, la testa all'indietro: tutto trema.
          const tr = Math.sin(f.t * 2.1) * 0.8;
          q.piedeA = [0, 13]; q.piedeD = [0, -13]; q.ginocchioA = [11, 12]; q.ginocchioD = [11, -10];
          q.bacino[0] -= 5; q.collo[0] -= 4; q.testa[0] -= 2; q.testa[1] -= 3 + tr; q.collo[1] -= 1;
          q.manoA = [36, 15 + tr]; q.gomitoA = [42, 16]; q.manoD = [36, -13 - tr]; q.gomitoD = [42, -14];
        } else {
          q.manoA = [30, 13]; q.gomitoA = [41, 14]; q.manoD = [30, -11]; q.gomitoD = [41, -12];
          q.piedeA = [0, 11]; q.piedeD = [0, -11]; q.testa[1] -= 1;
        }
        break;
      case "gelo":
      case "rimpicciolisci":
        // Un colpo di bacchetta: indietro, poi di scatto in avanti.
        if (f.t < 14) { const k = f.t / 14; q.manoA = [56 + 16 * k, 8 - 12 * k]; q.gomitoA = [50 + 8 * k, 6 - 6 * k]; }
        else { const k = Math.min(1, (f.t - 14) / 5); q.manoA = [72 - 20 * k, -4 + 30 * k]; q.gomitoA = [58 - 8 * k, 14 * k]; q.collo[1] += 3 * k; q.testa[1] += 3 * k; }
        q.manoD = [40, -6]; q.gomitoD = [44, -3];
        break;
      case "fulmine":
        // La bacchetta al cielo, poi giù.
        if (f.t < 20) { q.manoA = [86, 5]; q.gomitoA = [70, 6]; }
        else { q.manoA = [54, 20]; q.gomitoA = [52, 11]; q.collo[1] += 3; }
        q.manoD = [40, -6]; q.gomitoD = [44, -3];
        break;
      case "levita": {
        const k = f.t < 74 ? Math.min(1, f.t / 12) : Math.max(0, 1 - (f.t - 74) / 5);
        q.manoA = [50 + 28 * k, 14 + 4 * k]; q.gomitoA = [46 + 12 * k, 10 + 3 * k];
        q.manoD = [38, -6]; q.gomitoD = [42, -3]; q.testa[1] += 1;
        break;
      }
      case "presa":
        if (f.tiene) {
          const [h, dx] = puntoPresa(f), su = eMela(f) ? ABBASSA_MELA : 0;
          q.manoA = [h - 1 + su, dx + 2]; q.manoD = [h - 3 + su, dx - 2];
          q.gomitoA = [(50 + h) / 2 + 4 + su, dx * 0.5 + 3]; q.gomitoD = [(50 + h) / 2 + 2 + su, dx * 0.5 - 1];
          if (f.mossaPresa === "suplex") { const k = Math.min(1, Math.max(0, f.t - 10) / 24); q.collo[1] -= 6 * k; q.testa[1] -= 9 * k; }
          else { q.collo[1] += 2; q.ginocchioA[0] -= 2; q.ginocchioD[0] -= 2; }
        } else {
          const k = Math.min(1, f.t / 10);
          q.manoA = [50, 13 + 15 * k]; q.gomitoA = [47, 9 + 8 * k]; q.manoD = [49, 8 + 17 * k]; q.gomitoD = [45, 4 + 9 * k];
          q.collo[1] += 3 * k; q.testa[1] += 4 * k;
        }
        break;
      case "sfera":
        if (f.t < 112) { q.manoA = [84, 6]; q.manoD = [84, -6]; q.gomitoA = [70, 7]; q.gomitoD = [70, -7]; q.testa[1] -= 1; }
        else { q.manoA = [46, 26]; q.manoD = [44, 22]; q.gomitoA = [52, 15]; q.gomitoD = [50, 11]; q.collo[1] += 4; q.testa[1] += 5; }
        q.piedeA = [0, 12]; q.piedeD = [0, -12];
        break;
      case "disco":
        if (f.t < 30) { q.manoA = [84, 4]; q.gomitoA = [69, 6]; }
        else { const k = Math.min(1, (f.t - 30) / 8); q.manoA = [84 - 34 * k, 4 + 24 * k]; q.gomitoA = [69 - 18 * k, 6 + 10 * k]; q.collo[1] += 4 * k; q.testa[1] += 5 * k; }
        break;
      case "lampo":
        q.manoA = [63, 9]; q.gomitoA = [52, 15]; q.manoD = [63, -3]; q.gomitoD = [52, -9];
        break;
      case "barriera":
        q.manoA = [50, 22]; q.gomitoA = [49, 12]; q.manoD = [50, -20]; q.gomitoD = [49, -10];
        q.piedeA = [0, 13]; q.piedeD = [0, -13]; q.bacino[0] -= 2;
        break;
      case "telecinesi": {
        // Una mano alzata e aperta; al botto si chiude a pugno, in basso.
        const k = f.t < 104 ? Math.min(1, f.t / 12) : Math.max(0, 1 - (f.t - 104) / 6);
        q.manoA = [50 + 28 * k, 14 + 4 * k]; q.gomitoA = [46 + 12 * k, 10 + 3 * k];
        q.manoD = [38, -6]; q.gomitoD = [42, -3]; q.testa[1] += 1;
        break;
      }
      case "avvinghia":
        q.manoA = [50, 26]; q.gomitoA = [49, 14]; q.manoD = [44, 24]; q.gomitoD = [44, 12];
        q.ginocchioA = [22, 12]; q.piedeA = [14, 22]; q.ginocchioD = [20, 10]; q.piedeD = [10, 20];
        break;
      case "carica": {
        const tr = Math.sin(f.t * 1.7) * 0.6;
        q.piedeA = [0, 12]; q.piedeD = [0, -12]; q.ginocchioA = [12, 11]; q.ginocchioD = [12, -9];
        q.bacino[0] -= 4; q.collo[0] -= 3; q.testa[0] -= 3; q.testa[1] += tr;
        q.manoA = [28, 16]; q.gomitoA = [39, 12]; q.manoD = [28, -12]; q.gomitoD = [39, -9];
        break;
      }
      case "spingi": {
        // Le due mani avanti contro la sfera, il corpo che ci si butta dietro: trema tutto.
        const tr = Math.sin(f.t * 1.3) * 0.8;
        q.piedeA = [0, 13]; q.piedeD = [0, -13]; q.ginocchioA = [13, 12]; q.ginocchioD = [13, -8];
        q.manoA = [56 + tr, 26]; q.manoD = [52 + tr, 24]; q.gomitoA = [52, 15]; q.gomitoD = [49, 12];
        q.collo[1] += 4; q.testa[1] += 5; q.bacino[0] -= 2;
        break;
      }
      case "onda":
        q.piedeA = [0, 13]; q.piedeD = [0, -10]; q.ginocchioA = [13, 11]; q.ginocchioD = [13, -7];
        if (f.t < 34) {
          q.manoA = [36, -6]; q.manoD = [38, -8]; q.gomitoA = [42, 4]; q.gomitoD = [42, 2];
          q.collo[1] -= 3; q.testa[1] -= 2;
        } else {
          q.manoA = [49, 27]; q.manoD = [48, 25]; q.gomitoA = [49, 15]; q.gomitoD = [48, 13];
          q.collo[1] += 3; q.testa[1] += 3;
        }
        if (eMela(f)) for (const nome of SPALLA_MELA) q[nome][0] += ABBASSA_MELA * 0.5;
        break;
      case "raffica":
        if (Math.floor(f.t / 6) % 2) { q.manoA = [50, 27]; q.gomitoA = [48, 15]; }
        else { q.manoD = [49, 26]; q.gomitoD = [46, 14]; }
        q.piedeA = [0, 11]; q.piedeD = [0, -9];
        break;
      case "palla":
        // Giù a raccogliere la neve, poi su e via, con una mano sola.
        if (f.t < 12) {
          const k = Math.sin(Math.PI * f.t / 12);
          q.bacino[0] -= 10 * k; q.collo[0] -= 14 * k; q.testa[0] -= 15 * k; q.collo[1] += 5 * k; q.testa[1] += 6 * k;
          q.ginocchioA[0] -= 3 * k; q.ginocchioD[0] -= 3 * k;
          q.manoA = [8 + 42 * (1 - k), 16]; q.gomitoA = [24 + 20 * (1 - k), 13];
        } else if (f.t < 20) {
          const k = (f.t - 12) / 8;
          q.manoA = [56 + 12 * k, 10 - 22 * k]; q.gomitoA = [50 + 8 * k, 6 - 10 * k]; q.collo[1] -= 3 * k;
        } else {
          const k = Math.min(1, (f.t - 20) / 6);
          q.manoA = [68 - 14 * k, -12 + 36 * k]; q.gomitoA = [58 - 6 * k, -4 + 18 * k]; q.collo[1] += 4 * k; q.testa[1] += 5 * k;
        }
        break;
      case "estrai":
        // La mela allunga la mano dietro, nel jetpack, e tira fuori il pieghevole.
        if (f.t < 14) {
          const k = f.t / 14;
          q.manoA = [50 + 8 * k, 13 - 30 * k]; q.gomitoA = [48 + 4 * k, 8 - 14 * k]; q.testa[1] -= 3 * k;
        } else {
          const k = Math.min(1, (f.t - 14) / 10);
          q.manoA = [58 + 26 * k, -17 + 20 * k]; q.gomitoA = [52 + 16 * k, -6 + 10 * k];
          q.manoD = [60 + 10 * k, 12]; q.gomitoD = [50, 8];
        }
        break;
      case "balla": {
        const ph = f.t * 0.22, sn = Math.sin(ph);
        switch (f.ballo) {
          case "floss":
            q.manoA = [30, 8 + 14 * sn]; q.gomitoA = [38, 5 + 8 * sn]; q.manoD = [30, -6 + 14 * sn]; q.gomitoD = [38, -3 + 8 * sn];
            q.bacino[1] -= 4 * sn; break;
          case "robot": {
            const k = Math.floor(f.t / 10) % 4;
            const A = [[62, 18], [48, 22], [70, 10], [44, 16]][k], D = [[44, -14], [64, -10], [48, -16], [66, -8]][k];
            q.manoA = A; q.gomitoA = [(A[0] + 50) / 2 + 2, A[1] * 0.55]; q.manoD = D; q.gomitoD = [(D[0] + 50) / 2 + 2, D[1] * 0.55];
            q.testa[1] += k % 2 ? 2 : -2; break;
          }
          case "dab":
            q.manoA = [74, -16]; q.gomitoA = [63, -8]; q.manoD = [62, 7]; q.gomitoD = [56, 11];
            q.testa[0] -= 4; q.testa[1] += 4; break;
          case "twist":
            q.bacino[1] += 5 * Math.sin(ph * 2); q.ginocchioA = [12, 8 + 4 * sn]; q.ginocchioD = [12, -4 + 4 * sn];
            q.bacino[0] -= 3; q.collo[0] -= 3; q.testa[0] -= 3;
            q.manoA = [44, 16 - 10 * sn]; q.gomitoA = [40, 10]; q.manoD = [44, -8 - 10 * sn]; q.gomitoD = [40, -6]; break;
          case "saltelli": {
            const su = Math.abs(sn);
            q.manoA = [44 + 36 * su, 10 + 8 * su]; q.gomitoA = [44 + 20 * su, 10 + 6 * su];
            q.manoD = [44 + 36 * su, -6 - 8 * su]; q.gomitoD = [44 + 20 * su, -4 - 6 * su];
            q.piedeA = [0, 6 + 8 * su]; q.piedeD = [0, -6 - 8 * su]; break;
          }
          case "moonwalk":
            q.piedeA = [Math.max(0, 3 * sn), 8 - 10 * sn]; q.piedeD = [Math.max(0, -3 * sn), -8 + 10 * sn];
            q.manoA = [40, 10 + 6 * sn]; q.manoD = [40, -6 - 6 * sn]; q.testa[1] -= 2; break;
          default:   // giravolta
            q.manoA = [58, 22]; q.gomitoA = [55, 12]; q.manoD = [58, -18]; q.gomitoD = [55, -8];
            q.piedeD = [6, -4]; q.ginocchioD = [16, -6];
        }
        break;
      }
    }
    // Accecato dal lampo: mani sugli occhi, barcollando.
    if (f.accecato > 0 && !f.azione) {
      const b = Math.sin(passi * 0.25) * 2;
      q.manoA = [61, 6 + b]; q.gomitoA = [51, 12]; q.manoD = [61, 0 + b]; q.gomitoD = [51, -5];
      q.testa[1] += b; q.collo[1] += b * 0.5;
    }
    // In volo da guerriero: gambe piegate all'indietro, busto proteso; nello
    // scatto il corpo si allunga, un pugno avanti e le gambe tese dietro.
    if (f.volo && f.jet > 0 && (!f.azione || f.azione === "avanza")) {
      if (f.scatto > 0) {
        q.manoA = [56, 22]; q.gomitoA = [53, 12]; q.manoD = [40, -10]; q.gomitoD = [44, -6];
        q.ginocchioA = [24, -9]; q.piedeA = [20, -21]; q.ginocchioD = [22, -12]; q.piedeD = [17, -25];
        q.collo[1] += 7; q.testa[1] += 9; q.bacino[1] -= 2;
      } else {
        const ond = Math.sin(passi * 0.08) * 1.5;
        q.ginocchioA = [16, 5]; q.piedeA = [5 + ond, -3]; q.ginocchioD = [15, -2]; q.piedeD = [4 - ond, -9];
        q.manoA = [42, 15]; q.gomitoA = [43, 9]; q.manoD = [42, 6]; q.gomitoD = [42, 1];
        q.collo[1] += 2; q.testa[1] += 3;
      }
    }
    if (f.azione === "rush") {
      if (f.t < 32) {
        const k = f.t % 8 < 4;
        q.manoA = k ? [52, 28] : [48, 12]; q.gomitoA = k ? [50, 16] : [45, 7];
        q.manoD = k ? [47, 8] : [51, 27]; q.gomitoD = k ? [44, 3] : [49, 15];
        q.collo[1] += 3; q.testa[1] += 3;
      } else if (f.t < 36) {
        q.manoA = [80, 10]; q.manoD = [80, 8]; q.gomitoA = [68, 6]; q.gomitoD = [68, 4]; q.collo[1] -= 2;
      } else {
        q.manoA = [42, 24]; q.manoD = [42, 22]; q.gomitoA = [52, 18]; q.gomitoD = [52, 16]; q.collo[1] += 5; q.testa[1] += 6;
      }
      if (eMela(f)) for (const nome of SPALLA_MELA) q[nome][0] += ABBASSA_MELA;
    }
    // Col paracadute aperto ci si tiene alle corde, con le gambe a penzoloni.
    if (f.paracadute) {
      q.manoA = [76, 6]; q.gomitoA = [64, 8]; q.manoD = [76, -6]; q.gomitoD = [64, -8];
      q.piedeA = [2, 5]; q.piedeD = [0, -4]; q.ginocchioA = [15, 5]; q.ginocchioD = [15, -3];
      if (eMela(f)) for (const nome of SPALLA_MELA) q[nome][0] += ABBASSA_MELA;
    }
    if (eMela(f)) for (const nome of SPALLA_MELA) q[nome][0] -= ABBASSA_MELA;
    // Senza una gamba si saltella, senza tutte e due ci si trascina; e chi è in
    // piedi, contro uno che sta per terra, i colpi li tira in giù.
    const ng = gambe(f);
    if (ng < 2 && !(f.jet > 0) && !f.paracadute) posaMutilata(f, q, ng, e, carica);
    else if (ng === 2 && COLPI[f.azione]) { const m = bersaglio(f); if (m) colpoMirato(f, q, m, e); }
    // Le mosse in coppia che staccano da terra: tutto il corpo sale insieme.
    if (f.coppia && f.coppia.h) for (const nome in q) q[nome][0] += f.coppia.h / S;
    if (f.alza) for (const nome in q) q[nome][0] += f.alza / S;
    // Chi sta per prendere il colpo finale barcolla, le braccia giù.
    if (fatale && f === fatale.a && !f.azione && !fatale.contato) {
      const d = Math.sin(passi * 0.22) * 4;
      q.testa[1] += d * 1.2; q.collo[1] += d * 0.7; q.bacino[0] -= 3;
      q.manoA = [33, 9 + d]; q.gomitoA = [41, 7 + d * 0.5]; q.manoD = [32, -3 + d]; q.gomitoD = [40, 1 + d * 0.5];
    }
    // In coordinate della finestra.
    const fuori = {};
    for (const nome in q) {
      fuori[nome] = [f.cx + q[nome][1] * f.dir * S, f.base - verso * (q[nome][0] * S + 2 * S)];
    }
    return fuori;
  }

  // --- SENZA GAMBE (05/10/2026, su richiesta) -------------------------------
  // Prima chi perdeva le gambe restava ritto a mezz'aria, sulle gambe che non
  // si vedevano più. Ora: con una gamba sola si saltella; senza nessuna ci si
  // butta a terra e ci si trascina sulle mani (la mela, che è tonda, si siede
  // e avanza sulle nocche), oppure ci si alza in volo, dove le gambe non
  // servono; senza nemmeno le braccia si va a strattoni, come un bruco, e si
  // colpisce di testa. Gli arti tornano da soli dopo qualche secondo.
  const gambe = (f) => (f.staccati.gA ? 0 : 1) + (f.staccati.gD ? 0 : 1);
  const braccia = (f) => (f.staccati.A ? 0 : 1) + (f.staccati.D ? 0 : 1);
  const striscia = (f) => gambe(f) === 0 && !(f.jet > 0);
  // Chi si trascina bocconi ha il bacino dietro le spalle, non sotto: di tanto (unità della posa).
  const DIETRO_STRISCIA = 16;
  // Quanto si va piano: saltellando, trascinandosi, o a strattoni.
  const andatura = (f) => {
    const ng = gambe(f), k = ng === 2 ? 1 : ng === 1 ? 0.72 : braccia(f) ? 0.5 : 0.32;
    // Nella corsa: il passo svelto, e le ferite dell'ultima possibilità.
    return corsa && corsa.chi && f.tipo === corsa.chi ? k * (1 + 0.12 * livello("velocita")) * (corsa.ultima ? CORSA.lento : 1) : k;
  };
  // Il gomito fra la spalla e la mano, piegato verso l'alto (unità della posa).
  function gomitoDi(sp, mano) {
    const L1 = 10.6, L2 = 9.4, dh = mano[0] - sp[0], dd = mano[1] - sp[1], lun = Math.hypot(dh, dd) || 1;
    const d = Math.min(L1 + L2 - 0.01, Math.max(Math.abs(L1 - L2) + 0.5, lun));
    const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d), alto = Math.sqrt(Math.max(0, L1 * L1 - a * a));
    let nh = dd / lun, nd = -dh / lun;
    if (nh < 0) { nh = -nh; nd = -nd; }
    return [sp[0] + dh / lun * a + nh * alto, sp[1] + dd / lun * a + nd * alto];
  }
  // Dove mirare, nelle unità della posa ([altezza, avanti]), quando uno dei due
  // sta per terra: la testa di chi striscia, o il bacino di chi è in piedi per
  // chi colpisce da terra. Fra due in piedi non serve (null).
  function bersaglio(f) {
    if (orda) {
      // Contro gli zombie si mira solo se serve: a quelli che strisciano (in basso), o da terra.
      const z = zombieVicino(f.cx, 60 * S);
      if (!z || !(z.tipo === "striscia" || striscia(f))) return null;
      const c = corpoZ(z), k = z.tipo === "striscia" ? 3 : 0;
      return [(f.base - c[k + 1]) * verso / S - 2, (c[k] - f.cx) * f.dir / S];
    }
    const a = f.rivale;
    if (!a || !a.p || a.esploso || f.jet > 0 || a.jet > 0 || Math.abs(a.base - f.base) > 22 * S) return null;
    const suoCollo = (f.base - a.p.collo.y) * verso / S - 2, basso = suoCollo <= 36;
    if (!basso && !striscia(f)) return null;
    const pt = basso ? a.p.testa : a.p.bacino;
    return [(f.base - pt.y) * verso / S - 2, (pt.x - f.cx) * f.dir / S];
  }
  function colpoMirato(f, q, m, e) {
    const az = f.azione;
    if (az === "pugno" || az === "diretto") {
      const b = az === "diretto" ? "D" : "A";
      // Ci si piega verso il bersaglio e il braccio lo va a cercare.
      const giu = Math.max(0, Math.min(1, (46 - m[0]) / 30)) * e;
      q.collo = [q.collo[0] - 14 * giu, q.collo[1] + 8 * giu]; q.testa = [q.testa[0] - 18 * giu, q.testa[1] + 13 * giu]; q.bacino[0] -= 3 * giu;
      const sp = q.collo, dh = m[0] - sp[0], dd = m[1] - sp[1], lun = Math.hypot(dh, dd) || 1, kk = Math.min(1, 21 / lun);
      const r = q["mano" + b], arrivo = [sp[0] + dh * kk, sp[1] + dd * kk];
      const mano = [r[0] + (arrivo[0] - r[0]) * e, r[1] + (arrivo[1] - r[1]) * e];
      q["mano" + b] = mano; q["gomito" + b] = [(sp[0] + mano[0]) / 2 + 2, (sp[1] + mano[1]) / 2 - 2];
    } else if (az === "calcio") {
      const anca = q.bacino, dh = m[0] - anca[0], dd = m[1] - anca[1], lun = Math.hypot(dh, dd) || 1, kk = Math.min(1, 28 / lun);
      const arrivo = [anca[0] + dh * kk, anca[1] + dd * kk];
      q.piedeA = [arrivo[0] * e, 8 + (arrivo[1] - 8) * e];
      q.ginocchioA = [(anca[0] + q.piedeA[0]) / 2 + 3 * e, (anca[1] + q.piedeA[1]) / 2 + 4 * e];
    }
  }
  function posaMutilata(f, q, ng, e, carica) {
    const ph = f.passo, az = f.azione, cammina = az === "avanza" || az === "indietro", mela = eMela(f);
    if (ng === 1) {
      const c = f.staccati.gA ? "D" : "A", v = c === "A" ? "D" : "A";        // c: la gamba che c'è
      const salto = cammina ? 7 * Math.abs(Math.sin(ph * 0.9)) : 0;
      for (const n in q) q[n][0] += salto * 0.85;
      // Il piede buono sotto il corpo, il moncone raccolto.
      q["piede" + c] = [salto, 1]; q["ginocchio" + c] = [14 + salto * 0.8, 5];
      q["ginocchio" + v] = [19 + salto, -4]; q["piede" + v] = [10 + salto, -9];
      if (!az || cammina) {
        // Le braccia larghe, a tenere l'equilibrio.
        const dond = Math.sin(passi * 0.13 + (f.tipo === "mela" ? 2 : 0)) * 2.2, su = salto * 0.85 - (mela ? ABBASSA_MELA : 0);
        q.manoA = [46 + dond + su, 21]; q.gomitoA = [46 + su, 11]; q.manoD = [46 - dond + su, -15]; q.gomitoD = [46 + su, -8];
        q.testa[1] += dond * 0.5; q.collo[1] += dond * 0.3;
      }
      return;
    }
    const nb = braccia(f), tira = cammina ? Math.sin(ph) : 0, co = cammina ? Math.cos(ph) : 0;
    const alzaA = 5 * Math.max(0, co), alzaD = 5 * Math.max(0, -co);
    if (mela) {
      // Seduta per terra: avanza sulle nocche, dondolando.
      const dond = cammina ? Math.sin(ph) * 3.5 : Math.sin(passi * 0.06) * 0.8, sob = nb ? 0 : (cammina ? 6 * Math.abs(Math.sin(ph)) : 0);
      q.bacino = [6 + sob, 0]; q.collo = [28 + sob, 1 + dond * 0.5]; q.testa = [40 + sob, 2 + dond];
      q.manoA = [2 + alzaA, 15 + 7 * tira]; q.gomitoA = [13, 19 + 3 * tira];
      q.manoD = [2 + alzaD, -13 - 7 * tira]; q.gomitoD = [13, -17 - 3 * tira];
      q.ginocchioA = [4, -14]; q.piedeA = [3, -28]; q.ginocchioD = [11, -12]; q.piedeD = [4, -24];
    } else {
      // Bocconi, col busto sollevato: una mano si allunga, si pianta, tira. Senza braccia, a strattoni.
      const su = nb ? 0 : (cammina ? 5 * Math.abs(Math.sin(ph)) : 0);
      // Il bacino sta dietro (vedi DIETRO_STRISCIA): il punto di riferimento sono le spalle.
      const d0 = -DIETRO_STRISCIA;
      q.bacino = [3 + su * 0.3, d0]; q.collo = [(nb ? 15 : 9) + su, d0 + 18 - su * 0.4]; q.testa = [(nb ? 26 : 19) + su, d0 + 24];
      const A = [1 + alzaA, d0 + 25 + 9 * tira], D = [1 + alzaD, d0 + 22 - 9 * tira];
      q.manoA = A; q.gomitoA = gomitoDi(q.collo, A); q.manoD = D; q.gomitoD = gomitoDi(q.collo, D);
      q.ginocchioA = [3, d0 - 15]; q.piedeA = [2, d0 - 29]; q.ginocchioD = [11.5, d0 - 12.5]; q.piedeD = [4, d0 - 24.5];
    }
    // I colpi da terra: ci si solleva su una mano e si tira con l'altra dove sta l'avversario.
    const m = bersaglio(f) || [mela ? 36 : 30, 30];
    if (az === "pugno" || az === "montante" || az === "diretto" || TAGLI[az] || az === "lancia" || az === "spara") {
      const b = az === "diretto" ? "D" : "A", ferma = b === "A" ? "D" : "A";
      const k = az === "spara" ? 1 : az === "lancia" ? (f.t < 11 ? 0 : Math.min(1, (f.t - 11) / 8)) : TAGLI[az] ? Math.max(0, Math.min(1, (f.t - 6) / 6)) : e;
      // Uno slancio in avanti con tutto il corpo, e il busto che si alza sulla mano ferma.
      if (!mela) { for (const n in q) q[n][1] += 7 * k; q.collo = [q.collo[0] + 7 * k, q.collo[1] + 2 * k]; q.testa = [q.testa[0] + 8 * k, q.testa[1] + 3 * k]; }
      const sp = q.collo, dh = m[0] - sp[0], dd = m[1] - sp[1], lun = Math.hypot(dh, dd) || 1, kk = Math.min(1, (mela ? 30 : 20.5) / lun);
      const arrivo = [sp[0] + dh * kk, sp[1] + dd * kk], r = q["mano" + b];
      const mano = [r[0] + (arrivo[0] - r[0]) * k + (az === "lancia" && f.t < 11 ? 12 : 0), r[1] + (arrivo[1] - r[1]) * k - 6 * carica];
      q["mano" + b] = mano; q["gomito" + b] = mela ? [(sp[0] + mano[0]) / 2 + 3, (sp[1] + mano[1]) / 2 + 4] : gomitoDi(sp, mano);
      if (!mela) { const piantata = [1, sp[1] + 3]; q["mano" + ferma] = piantata; q["gomito" + ferma] = gomitoDi(sp, piantata); }
    } else if (az === "testata") {
      q.collo = [q.collo[0] + 4 * e, q.collo[1] + 8 * e - 4 * carica]; q.testa = [q.testa[0] + 8 * e, q.testa[1] + 15 * e - 6 * carica];
    } else if (az === "para") {
      q.manoA = [q.testa[0] - 1, q.testa[1] + 8]; q.gomitoA = [q.collo[0] - 2, q.collo[1] + 9];
      q.manoD = [q.testa[0] - 6, q.testa[1] + 6]; q.gomitoD = [q.collo[0] - 5, q.collo[1] + 6];
    } else if (az === "esulta" || az === "provoca" || az === "balla") {
      // Da terra si festeggia come si può: un pugno al cielo (o tutti e due).
      const w = Math.sin(f.t * 0.5) * 3;
      q.manoA = [q.collo[0] + 17 + w, q.collo[1] + 5]; q.gomitoA = [q.collo[0] + 9, q.collo[1] + 7];
      if (az !== "provoca" && mela) { q.manoD = [q.collo[0] + 17 - w, q.collo[1] - 5]; q.gomitoD = [q.collo[0] + 9, q.collo[1] - 7]; }
    }
  }
  // Che arto serve per una mossa; senza, si ripiega su un'altra (vedi `inizia`).
  const SERVE = { pugno: "A", montante: "A", diretto: "D", calcio: "gA" };
  function mossaPossibile(f, azione) {
    const st = f.staccati, ng = gambe(f), aTerra = !(f.jet > 0);
    if (ng === 2 && !st.A && !st.D) {
      // Tutto intero: solo, contro chi sta per terra, niente montanti all'aria.
      if (azione === "montante") { const m = bersaglio(f); if (m && m[0] < 40) return Math.random() < 0.5 ? "calcio" : "pugno"; }
      return azione;
    }
    if (aTerra && ng < 2) {
      if (azione === "salto") return "provoca";
      if (azione === "schiva") return braccia(f) ? "para" : "indietro";
      if (azione === "balla") return "esulta";
      if (azione === "presa" || azione === "rush" || azione === "scattoLama") azione = "pugno";
    }
    if (azione === "para" && !braccia(f)) return "indietro";                   // senza braccia non ci si para
    if (azione === "presa" && braccia(f) < 2) azione = "pugno";
    if (!SERVE[azione]) return azione;
    const ok = (m) => !st[SERVE[m]] && (m !== "calcio" || !aTerra || ng === 2);
    if (ok(azione)) return azione;
    const altre = ["pugno", "diretto", "calcio"].filter(ok);
    return altre.length ? altre[Math.floor(Math.random() * altre.length)] : "testata";
  }
  // Senza gambe, che si fa: su in volo, o avanti sulle mani.
  function pensaSenzaGambe(f, altro) {
    if (f.daBallare) { f.daBallare = false; inizia(f, "esulta"); return; }
    if (altro.ko || altro.preso || altro.tenuto || altro.esploso) { inizia(f, Math.random() < 0.7 ? "esulta" : "provoca"); return; }
    f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
    const puoVolare = verso > 0 && !f.tel;
    if (!f.piano) f.piano = Math.random() < (anime ? 0.9 : 0.5) ? "vola" : "striscia";
    if (f.piano === "vola" && puoVolare) {
      f.piano = "striscia";                      // finito il volo, se le gambe non sono tornate, si striscia
      decolla(f, false); f.jet = Math.max(f.jet, 460); return;
    }
    const d = Math.abs(altro.cx - f.cx) / S, lontano = Math.abs(altro.base - f.base) > 18 * S || altro.jet > 0;
    if (puoSparare(f, d) && !lontano) { inizia(f, azioneArma(f.arma)); return; }
    if (lontano) {
      // L'altro è su un altro piano, o in volo: da terra non ci si arriva.
      if (puoVolare && Math.random() < 0.6) { decolla(f, false); f.jet = Math.max(f.jet, 360); return; }
      inizia(f, "provoca"); return;
    }
    if (d > 31) { inizia(f, "avanza", altro.cx - f.dir * 27 * S); return; }
    if (altro.azione && COLPI[altro.azione] && braccia(f) && Math.random() < 0.3 * f.furbo) { inizia(f, "para"); return; }
    if (f.arma && f.arma.tipo === "spada" && f.colpiArma > 0) { f.colpiArma--; inizia(f, "fendente"); return; }
    inizia(f, scegli([[30 * f.aggr * pesoMossa(f, "pugno"), "pugno"], [24 * f.aggr * pesoMossa(f, "diretto"), "diretto"],
                      [16 * pesoMossa(f, "montante"), "montante"], [8 * pesoMossa(f, "indietro"), "indietro"]]));
  }

  // La posa dell'arrampicata: mani alternate sul bordo, piedi contro la
  // parete, corpo appeso di fianco. `s` è il lato esterno (-1 sinistra).
  function posaScalata(f) {
    const sc = f.scalata, o = sc.o, s = sc.lato, xw = s < 0 ? o.l : o.r, y = sc.y;
    const ph = f.t * 0.3, su = Math.max(0, Math.sin(ph)), giu = Math.max(0, -Math.sin(ph));
    const presa = (dy) => Math.max(o.t - 1 * S, y - dy * S);
    return {
      bacino: [xw + s * 9 * S, y - 26 * S], collo: [xw + s * 6 * S, y - 48 * S],
      testa: [xw + s * 7 * S, y - 59 * S],
      manoA: [xw + s * 2 * S, presa(58 + 6 * su)], manoD: [xw + s * 2 * S, presa(52 + 6 * giu)],
      gomitoA: [xw + s * 8 * S, y - 47 * S], gomitoD: [xw + s * 8 * S, y - 43 * S],
      piedeA: [xw + s * 3 * S, y - 4 * S - 6 * S * giu], piedeD: [xw + s * 3 * S, y - 10 * S - 6 * S * su],
      ginocchioA: [xw + s * 14 * S, y - 14 * S], ginocchioD: [xw + s * 14 * S, y - 19 * S],
    };
  }

  // --- Il cervello: un ciclo casuale di azioni --------------------------
  const DURATE = { avanza: 110, indietro: 26, pugno: 18, diretto: 20, montante: 24,
                   calcio: 28, provoca: 50, esulta: 36, salto: 34,
                   solleva: 16, lancia: 26, para: 26, schiva: 30,
                   spara: 26, fiammata: 54, fendente: 26, presa: 42, estrai: 36, balla: 170, palla: 30,
                   carica: 70, onda: 80, raffica: 40, rush: 44,
                   sfera: 150, disco: 56, lampo: 40, barriera: 110, avvinghia: 96, telecinesi: 124,
                   trasforma: 96, gelo: 44, rimpicciolisci: 40, fulmine: 50, levita: 100,
                   affondo: 24, rovescio: 26, scattoLama: 44, lancioLama: 40, pressa: 50, testata: 22,
                   cavallina: 46, sgabello: 46, trottola: 34, insieme: 38, bolide: 50, fionda: 34 };

  function inizia(f, azione, meta) {
    azione = mossaPossibile(f, azione);
    f.azione = azione; f.t = 0; f.durata = DURATE[azione]; f.colpito = false; f.voltato = false; f.risposta = false; f.rispostaVista = false;
    if (meta !== undefined) f.meta = meta;
    if (azione === "presa") {
      f.mossaPresa = scegli([[3, "sopra"], [2, "rotea"], [2, "suplex"]]);
      f.durata = DURATE_PRESA[f.mossaPresa];
    }
    if (azione === "salto") {
      for (const n in f.p) { f.p[n].oy = f.p[n].y + verso * 6.5 * S; f.p[n].ox = f.p[n].x - f.dir * 1.6 * S; }
    }
    if (azione === "schiva") {
      // Un balzo all'indietro, fuori portata.
      for (const n in f.p) { f.p[n].oy = f.p[n].y + verso * 5 * S; f.p[n].ox = f.p[n].x + f.dir * 2.6 * S; }
    }
  }

  function iniziaScalata(f, o, lato) {
    f.scalata = { o, lato, y: f.base };
    f.azione = null; f.t = 0;
    f.dir = -lato;
  }

  // Si può salire su `o` da qui? Solo se il suo fianco arriva fino a
  // portata di mano: un blocco che galleggia a mezza pagina no.
  function raggiungibile(f, o) {
    return o && o.b >= f.base - 60 * S && o.t < f.base - 6 * S;
  }

  // --- Il jetpack: si decolla, si lotta in aria, ogni tanto impazzisce ----
  function decolla(f, impazzito) {
    if (f && f.p) suona("jet", f.p.bacino.x, 0.8);
    if (verso < 0) return;                       // sottosopra niente jetpack
    if (anime) { prendiIlVolo(f); return; }      // i super guerrieri volano da sé
    f.volo = false;
    const b = f.p.bacino;
    f.jet = Math.round(caso(260, 560)); f.azione = null; f.scalata = null; f.pensa = 6;
    f.volaY = Math.max(110, Math.min(pavimento - 90 * S, b.y - caso(70, 170) * S));
    f.caos = impazzito ? Math.round(caso(200, 340)) : 0;
    f.giro = (Math.random() < 0.5 ? -1 : 1) * caso(0.09, 0.16); f.rot = 0;
    for (const n in f.p) f.p[n].oy = f.p[n].y + 3.5 * S;
    scintille(b.x, b.y + 22 * S, 8, "#ffb62e");
  }

  function pensaVolo(f, altro) {
    if (f.azione) {
      f.t++;
      if (f.azione === "spara" && f.t === 10 && f.arma) spara(f, altro);
      if (f.azione === "fiammata" && f.arma) fiammata(f, altro);
      if (anime) eseguiAnime(f, altro);
      if (lame()) eseguiLama(f, altro);
      if (f.t >= f.durata) {
        if ((f.azione === "spara" || f.azione === "fiammata" || f.azione === "fendente") && f.arma && f.colpiArma <= 0) {
          f.tel = f.arma; f.arma.stato = "portato"; f.arma = null; inizia(f, "lancia"); return;
        }
        f.azione = null; f.pensa = Math.round(caso(2, 14));
      }
      if (f.azione === "lancia" && f.t === 11 && f.tel) lanciaTelefono(f, altro);
      return;
    }
    if (f.caos > 0 || f.scatto > 0 || f.recupero > 0 || --f.pensa > 0) return;
    // Arriva l'orda: si scende a terra, accanto all'alleato.
    if (orda) { f.jet = Math.min(f.jet, 24); f.meta = Math.max(orda.l + 20 * S, Math.min(orda.r - 20 * S, orda.cx + (orda.lati[f.tipo] || 1) * 15 * S)); f.pensa = 12; return; }
    if (f.volo) { pensaGuerriero(f, altro); return; }
    const ob = altro.p.bacino, mio = f.p.bacino;
    f.dir = ob.x >= mio.x ? 1 : -1;
    if (altro.ko || altro.preso) {
      // L'avversario è a terra: si scende a festeggiare.
      f.jet = Math.min(f.jet, 70); f.meta = altro.cx; f.volaY = Math.min(pavimento - 60 * S, ob.y - 30 * S);
      f.pensa = 20; return;
    }
    f.volaY = Math.max(100, Math.min(pavimento - 70 * S, ob.y - caso(-8, 28) * S));
    const dx = Math.abs(ob.x - mio.x) / S;
    if (puoSparare(f, dx) && Math.random() < 0.5) { inizia(f, azioneArma(f.arma)); return; }
    if (anime && f.ki >= 45 && dx > 70 && Math.random() < 0.3) { inizia(f, "onda"); return; }
    if (anime && f.ki >= 15 && dx > 90 && Math.random() < 0.25) { inizia(f, "raffica"); return; }
    if (f.arma && f.arma.tipo === "spada" && dx <= 44) { f.colpiArma--; inizia(f, "fendente"); return; }
    if (lamaPronta(f) && dx <= 44 && Math.abs(ob.y - mio.y) < 34 * S) { inizia(f, scegli([[3, "fendente"], [2, "affondo"], [2, "rovescio"]])); return; }
    if (dx > 34) { f.meta = ob.x - f.dir * 27 * S; f.pensa = Math.round(caso(5, 16)); return; }
    f.meta = f.cx;
    inizia(f, scegli([[30 * f.aggr * pesoMossa(f, "pugno"), "pugno"], [22 * f.aggr * pesoMossa(f, "diretto"), "diretto"],
                      [16 * pesoMossa(f, "montante"), "montante"], [16 * f.aggr * pesoMossa(f, "calcio"), "calcio"],
                      [8 * f.furbo * pesoMossa(f, "para"), "para"], [8 * f.furbo * pesoMossa(f, "schiva"), "schiva"]]));
  }

  // La spinta del jetpack: tiene il corpo alla quota voluta (o lo sbatte
  // in giro, se impazzisce). Si applica a tutti i punti, come una forza.
  function applicaSpinta(f) {
    const g = GRAVITA * S * moltG, b = f.p.bacino;
    let spinta;
    if (f.volo) {
      f.fiamma = 0;
      if (f.recupero > 0) { f.recupero--; return; }      // sbalzato: si riprende dopo un attimo
      if (f.scatto > 0) { for (const n in f.p) f.p[n].y -= g; return; }
      const meta = f.volaY + Math.sin(passi * 0.06 + (f.tipo === "mela" ? 2 : 0)) * 3 * S;
      const err = b.y - meta, vy = b.y - b.oy;
      spinta = Math.max(0, Math.min(3 * g, g + 0.02 * err + 0.3 * vy));
      for (const n in f.p) f.p[n].y -= spinta;
      if (passi % 6 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "scintilla", x: b.x + caso(-8, 8) * S, y: b.y + 22 * S, vx: caso(-0.3, 0.3) * S, vy: caso(0.5, 1.5) * S,
                          vita: 12, max: 12, colore: COLORI_ANIME[f.tipo] });
      }
      return;
    }
    if (f.caos > 0) {
      // Giri impazziti: il getto gira in tondo (cerchi e otto, a volte al
      // contrario), poi a secco di colpo e giù a schiantarsi.
      f.caos--;
      f.rot = (f.rot || caso(0, 6.28)) + f.giro;
      let m = (2.2 + 1.2 * Math.sin(f.caos * 0.05)) * S;
      f.ix = Math.cos(f.rot) * m; f.iy = Math.sin(f.rot) * m;
      // Mai contro il soffitto: in alto il giro si sposta in basso.
      if (b.y < 150) f.iy = Math.abs(f.iy);
      spinta = g * 0.92;
      for (const n in f.p) { f.p[n].x += f.ix * 0.28; f.p[n].y += f.iy * 0.28; }
      f.p.testa.x += f.ix * 0.12; f.p.testa.y += f.iy * 0.12;
      if (passi % 3 === 0) fiammata(f, -f.iy, -f.ix);
      if (f.caos === 0) {
        // Schianto: il getto si spegne e si piomba a terra.
        f.jet = 0; f.fiamma = 0; f.stordito = 70; f.forza = 0.2;
        for (const n in f.p) f.p[n].oy = f.p[n].y - 9 * S;
        scintille(b.x, b.y, 10, "#ffb62e");
        return;
      }
    } else {
      const err = b.y - f.volaY, vy = b.y - b.oy;
      spinta = Math.max(0, Math.min(2.2 * g, g + 0.004 * err + 0.14 * vy));
      // A secco di carburante si sente: la fiamma balbetta.
      if (f.jet < 45 && (passi & 3) === 0) spinta *= 0.2;
      if (passi % 2 === 0 && spinta > 0.5 * g) fiammata(f, 3.2, 0);
    }
    f.fiamma = spinta / (g * 1.6);
    for (const n in f.p) f.p[n].y -= spinta;
  }

  function fiammata(f, vy, vx) {
    const p = f.p, ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x);
    const x = p.bacino.x - f.dir * 9 * S + Math.cos(ang) * 4 * S, y = p.bacino.y + Math.sin(ang) * 4 * S + 3 * S;
    for (let i = 0; i < 2 && particelle.length < 170; i++) {
      particelle.push({ tipo: "fiamma", x: x + caso(-2, 2) * S, y, vx: (vx + caso(-0.7, 0.7)) * S * 0.6,
                        vy: (Math.max(1.5, vy) + caso(0, 1.4)) * S, vita: Math.round(caso(10, 18)), max: 18,
                        colore: ["#ff7a1a", "#ffb62e", "#fff1a0"][Math.floor(Math.random() * 3)] });
    }
  }

  function pensa(f, altro) {
    if (f.riparo > 0) f.riparo--;
    // Una mossa in coppia interrotta (un colpo, il ghiaccio, la fine dell'orda) non resta a metà.
    if (f.coppia && (f.ko || f.stordito || f.preso || f.tenuto || f.esploso || f.gelato > 0 || f.accecato > 0 || !orda || !MOSSE_COPPIA[f.azione])) {
      f.coppia = null;
      if (MOSSE_COPPIA[f.azione]) { f.azione = null; f.pensa = 6; }
    }
    // In scena per il colpo finale: i gesti li decide la scena, qui scorre solo il tempo della mossa.
    if (fatale && (f === fatale.da || f === fatale.a)) {
      if (f.azione && f.azione !== "avanza" && ++f.t >= f.durata) f.azione = null;
      return;
    }
    if (f.ko || f.stordito || f.preso || f.tenuto || f.esploso || f.scalata || f.inVolo || f.gelato > 0) return;
    if (f.accecato > 0) { f.accecato--; f.azione = null; f.scatto = 0; if (!(f.jet > 0) && f.accecato % 30 === 0) f.cx += caso(-6, 6) * S; return; }
    if (f.fuga && scappa(f)) return;
    if (f.jet > 0) { pensaVolo(f, altro); return; }
    if (f.azione) {
      f.t++;
      if (f.coppia) eseguiCoppia(f);
      if (f.azione === "spara" && f.t === 10 && f.arma) spara(f, altro);
      if (f.azione === "fiammata" && f.arma) fiammata(f, altro);
      if (f.azione === "estrai" && f.t === 14 && !f.tel) estraiDuo(f);
      if (anime) eseguiAnime(f, altro);
      else if (f.azione === "trasforma") eseguiTrasforma(f, altro);   // il ring libero: colosso e albero
      if (lame()) eseguiLama(f, altro);
      if (f.azione === "palla" && f.t === 11) f.palla = true;
      if (f.azione === "palla" && f.t === 21 && f.palla) tiraPalla(f, altro);
      const vicino = Math.abs(altro.base - f.base) <= 18 * S &&
        Math.abs(altro.cx - f.cx) < 27 * S && !altro.ko;
      const arrivato = Math.abs(f.meta - f.cx) < 3 * S;
      if (f.azione === "lancia" && f.t === 11 && f.tel) lanciaTelefono(f, altro);
      if (f.t >= f.durata || (f.azione === "avanza" && ((vicino && !(f.corsa > 0)) || arrivato))) {
        if (f.azione === "avanza" && f.prendiTel) {
          const t = f.prendiTel; f.prendiTel = null;
          if (arrivato && t.stato === "libero" && Math.abs(t.x - f.cx) < 16 * S) {
            if (eArma(t)) {
              // Un'arma si impugna e si tiene: pistola sei colpi, spada cinque fendenti.
              if (!f.arma) { t.stato = "impugnato"; t.da = f; f.arma = t; f.colpiArma = CARICHE[t.tipo] || 5; }
              f.azione = null; f.pensa = 4; return;
            }
            t.stato = "portato"; t.da = f; f.tel = t; inizia(f, "solleva"); return;
          }
        }
        if (f.azione === "solleva" && f.tel) { inizia(f, "lancia"); return; }
        if (f.azione === "estrai" && f.tel) { inizia(f, "lancia"); return; }
        // Finiti i colpi l'arma vuota si tira addosso all'avversario.
        if ((f.azione === "spara" || f.azione === "fiammata" || f.azione === "fendente") && f.arma && f.colpiArma <= 0) {
          f.tel = f.arma; f.arma.stato = "portato"; f.arma = null; inizia(f, "lancia"); return;
        }
        if (f.azione === "avanza" && arrivato && f.dopo) {
          const piano = f.dopo; f.dopo = null; f.azione = null;
          if (raggiungibile(f, piano.o)) { iniziaScalata(f, piano.o, piano.lato); return; }
        }
        f.azione = null; f.pensa = f.combo || f.ordine ? 1 : orda ? caso(2, 8) : caso(3, 22);
      }
      return;
    }
    if (--f.pensa > 0) return;
    f.dopo = null;
    if (corsa && pensaCorsa(f, altro)) return;
    // All'altro manca un colpo solo, e questo è il round buono: lo si chiude con la mossa finale.
    if (fataleRound && puoFinire(f, altro)) { avviaFatale(f, altro); return; }
    // Alle corde: nel ring libero ci si trasforma per rimontare, una volta sola a round.
    if (puoMutare(f) && f.danni >= f.soglia - 1) {
      f.mutato = true;
      if (Math.random() < 0.55) { inizia(f, "trasforma"); return; }
    }
    if (f.ordine && eseguiOrdine(f, altro)) return;
    if (orda) { if (eDellaCorsa(f)) pensaSolo(f); else pensaAlleato(f, altro); return; }
    if (gambe(f) === 0) { pensaSenzaGambe(f, altro); return; }
    // Ha appena vinto il round: balletto.
    if (f.daBallare) {
      f.daBallare = false;
      f.ballo = scegli([[2, "floss"], [2, "robot"], [2, "dab"], [2, "twist"], [2, "saltelli"], [1, "moonwalk"], [2, "giravolta"]]);
      inizia(f, "balla"); return;
    }
    if (altro.ko || altro.preso || altro.tenuto) { inizia(f, Math.random() < 0.7 ? "esulta" : "provoca"); return; }
    // I duellanti pensano con la lama; senza (lanciata, o col braccio staccato) tornano a fare a pugni.
    if (lame() && pensaLama(f, altro)) return;
    // La mela, ogni tanto e solo passato il primo minuto, tira fuori dal
    // jetpack il suo pieghevole: se prende il robot, lo fa a pezzi.
    const turno = f.tipo === "mela" ? prossimoDuo : prossimaBombaRobot;
    if (!stile && tempo >= turno && libero("armi") && !f.tel && !f.arma && !(altro.jet > 0) && !altro.esploso &&
        Math.abs(altro.cx - f.cx) < 480 * S && Math.random() < 0.35) {
      if (f.tipo === "mela") prossimoDuo = tempo + Math.round(caso(2400, 4200));
      else prossimaBombaRobot = tempo + Math.round(caso(2400, 4200));
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      inizia(f, "estrai"); return;
    }
    // Un telefono per terra a portata di mano? Si raccoglie e si lancia.
    if (!f.tel && !f.arma && Math.abs(altro.base - f.base) <= 18 * S) {
      const t = telefonoVicino(f);
      if (t && Math.random() < (eArma(t) || t.tipo === "bomba" || SPECIALI[t.tipo] ? 0.9 : 0.5 * f.furbo * (1 + 0.08 * livelloDi(f.tipo)))) {
        f.dir = t.x >= f.cx ? 1 : -1; f.prendiTel = t; inizia(f, "avanza", t.x); return;
      }
    }
    // Ogni tanto si accende il jetpack e si va a lottare in aria.
    const lv = livelloDi(f.tipo);
    // Chi ha imparato (livello 4) si alza in volo di proposito per inseguire
    // un avversario che sta volando.
    if (tempo >= CALMA && !f.tel && Math.random() < 0.045 * f.furbo * (lv >= 4 && altro.jet > 0 ? 5 : 1)) { decolla(f, altro.jet > 0 ? false : Math.random() < 0.3); return; }
    // L'avversario sta per colpire: ci si para o si schiva.
    if (altro.azione && COLPI[altro.azione] && Math.abs(altro.cx - f.cx) < 34 * S &&
        Math.abs(altro.base - f.base) <= 18 * S &&
        Math.random() < 0.3 * f.furbo * (pesoMossa(f, "para") + pesoMossa(f, "schiva")) / 2) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (anime && f.ki >= 15 && Math.random() < 0.4 && teletrasporta(f, altro)) return;
      const wp = pesoMossa(f, "para"), ws = pesoMossa(f, "schiva");
      inizia(f, Math.random() < wp / (wp + ws) ? "para" : "schiva"); return;
    }
    // Con un'arma in mano: pistola e bazooka sparano da lontano, il lanciafiamme
    // da media distanza, la spada si avvicina.
    if (f.arma && Math.abs(altro.base - f.base) <= 40 * S) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      const d = Math.abs(altro.cx - f.cx) / S, t = f.arma.tipo;
      if (SPARANO[t]) {
        if (puoSparare(f, d) && Math.random() < 0.6) { inizia(f, azioneArma(f.arma)); return; }
        if (t === "lanciafiamme" && d >= 150) { inizia(f, "avanza", altro.cx - f.dir * 90 * S); return; }
        if (t === "bazooka" && d <= 70) { inizia(f, "indietro"); return; }
        if (t === "pistola" && d <= 40 && Math.random() < 0.5) { inizia(f, "indietro"); return; }
      } else if (d <= 44) { f.colpiArma--; inizia(f, "fendente"); return; }
      else { inizia(f, "avanza", altro.cx - f.dir * 34 * S); return; }
    }
    // Super guerrieri: onde, raffiche, teletrasporti e carica dell'aura.
    if (anime && !f.arma && !f.tel) {
      const d = Math.abs(altro.cx - f.cx) / S;
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (mossaSpeciale(f, altro)) return;
      if (verso > 0 && (altro.volo && altro.jet > 0 ? Math.random() < 0.6 : Math.random() < 0.14)) { scatta(f, altro, 26); return; }
      if (!maghi() && d <= 40 && f.ki >= 8 && Math.random() < 0.25) { inizia(f, "rush"); return; }
      // I maghi da vicino si scostano, o sparano una raffica a bruciapelo.
      if (maghi() && d <= 40 && Math.random() < 0.45) { inizia(f, f.ki >= 15 && Math.random() < 0.5 ? "raffica" : "indietro"); return; }
      if (f.ki >= 45 && d > 70 && Math.abs(altro.p.collo.y - f.p.collo.y) < 60 * S && Math.random() < 0.3) { inizia(f, "onda"); return; }
      if (f.ki >= 15 && d > 110 && Math.random() < 0.18 && teletrasporta(f, altro)) return;
      if (f.ki >= 15 && d > 60 && Math.random() < 0.25) { inizia(f, "raffica"); return; }
      if (f.ki < 50 && d > 100 && Math.random() < 0.25) { inizia(f, "carica"); return; }
    }
    // A Natale ci si tira le palle di neve.
    if (natale && !f.arma && !f.tel && Math.abs(altro.cx - f.cx) > 50 * S && Math.random() < 0.35) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      inizia(f, "palla"); return;
    }
    const pesoPresa = !f.arma && !(altro.jet > 0) && !altro.tenuto && !altro.ko
      ? (tempo < CALMA ? 3 : 10) * pesoMossa(f, "presa") : 0;

    const dy = altro.base - f.base;
    // Sottosopra niente arrampicate: si va verso l'altro e si «cade» su.
    if (verso < 0 && Math.abs(dy) > 18 * S) { f.dir = altro.cx >= f.cx ? 1 : -1; inizia(f, "avanza", altro.cx); return; }
    if (Math.abs(dy) <= 18 * S) {
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      const distanza = Math.abs(altro.cx - f.cx) / S;
      if (distanza > 34 && vulcanoInMezzo(f, altro)) {
        // Il vulcano li separa: lo si scavalca in volo, o si aspetta provocando.
        if (verso > 0 && !f.tel && Math.random() < 0.4) { decolla(f, false); return; }
        inizia(f, scegli([[50, "provoca"], [25, "indietro"], [25, "para"]]));
      } else if (distanza > 34) {
        const azione = scegli([[74 * f.aggr, "avanza"], [14 * pesoMossa(f, "provoca"), "provoca"], [12 * pesoMossa(f, "salto"), "salto"]]);
        inizia(f, azione, altro.cx);
      } else if (distanza < 22) {
        inizia(f, scegli([[45 * pesoMossa(f, "indietro"), "indietro"], [25 * pesoMossa(f, "montante"), "montante"],
                          [30 * pesoMossa(f, "pugno"), "pugno"], [pesoPresa * 1.5, "presa"]]));
      } else {
        // Dopo un colpo a segno o una parata si va in serie: solo attacchi,
        // scelti ancora più in base a quel che ha funzionato.
        const serie = f.combo; f.combo = 0;
        const pa = serie ? 2 : 1;
        inizia(f, scegli([[28 * f.aggr * Math.pow(pesoMossa(f, "pugno"), pa), "pugno"],
                          [20 * f.aggr * Math.pow(pesoMossa(f, "diretto"), pa), "diretto"],
                          [14 * Math.pow(pesoMossa(f, "montante"), pa), "montante"],
                          [22 * f.aggr * Math.pow(pesoMossa(f, "calcio"), pa), "calcio"],
                          [serie ? 0 : 8 / f.aggr * pesoMossa(f, "indietro"), "indietro"],
                          [serie ? 0 : 8 * pesoMossa(f, "salto"), "salto"], [serie ? 0 : pesoPresa, "presa"]]));
      }
    } else if (dy > 0) {
      // L'avversario è più in basso: si va verso di lui, e se sta sotto
      // l'elemento su cui siamo, verso il bordo più vicino per scendere.
      const o = f.supporto;
      let meta = altro.cx;
      if (o && altro.cx >= o.l - 4 * S && altro.cx <= o.r + 4 * S) {
        meta = (f.cx - o.l < o.r - f.cx) ? o.l - 14 * S : o.r + 14 * S;
      }
      f.dir = meta >= f.cx ? 1 : -1;
      // Scende apposta da dove sta: se il salto è alto, apre il paracadute.
      if (o) f.scendeApposta = 300;
      inizia(f, "avanza", Math.max(10 * S, Math.min(W - 10 * S, meta)));
    } else {
      // Più in alto: ci si arrampica sul fianco dell'elemento su cui sta.
      const o = altro.supporto;
      if (raggiungibile(f, o)) {
        const lato = f.cx < (o.l + o.r) / 2 ? -1 : 1;
        const xw = lato < 0 ? o.l : o.r;
        const meta = xw + lato * 11 * S;
        f.dir = meta >= f.cx ? 1 : -1;
        if (Math.abs(meta - f.cx) < 4 * S) { iniziaScalata(f, o, lato); return; }
        inizia(f, "avanza", meta);
        f.dopo = { o, lato };
      } else {
        // Irraggiungibile: aspetta che scenda lui, provocandolo.
        inizia(f, scegli([[70, "provoca"], [30, "salto"]]));
      }
    }
  }

  const COLPI = { pugno: ["manoA", 7, 13, 3.2], diretto: ["manoD", 8, 15, 3.8],
                  montante: ["manoA", 9, 17, 4.4], calcio: ["piedeA", 10, 19, 4.8],
                  fendente: ["manoA", 10, 17, 5.4],
                  affondo: ["manoA", 6, 13, 5.0], rovescio: ["manoA", 10, 16, 5.2],
                  testata: ["testa", 8, 15, 3.6] };
  const SUONI = ["POW!", "BAM!", "SBAM!", "TUMP!", "ZOT!", "PAF!"];

  function controllaColpo(f, altro) {
    const regola = COLPI[f.azione];
    if (!regola || f.colpito || f.esploso) return;
    const [arto, da, a, forza] = regola;
    if (f.t < da || f.t > a) return;
    for (const k in ARTI) if (k !== "P" && f.staccati[k] && ARTI[k][1] === arto) return;   // col moncone non si colpisce
    const lama = !!TAGLI[f.azione];
    if (lama && !f.arma && !lamaPronta(f)) return;
    if (orda) {
      // Durante la tregua si picchiano gli zombie, non l'alleato.
      const m = f.p[arto], g = f.p.gomitoA, L = Math.hypot(m.x - g.x, m.y - g.y) || 1;
      for (const k of lama ? [8, 15, 22, 29] : [0]) {
        const x = m.x + (lama ? (m.x - g.x) / L * k * S : 0), y = m.y + (lama ? (m.y - g.y) / L * k * S : 0);
        const z = zombieToccato(x, y, (lama ? 4 : 6) * S);
        if (z) { f.colpito = true; colpisciZombie(z, forza * caso(0.9, 1.3) * (f.furia > 0 ? 1.5 : 1) * (lama ? 1.2 : 1), f.dir, x, y, f); return; }
      }
      return;
    }
    if (altro.ko || altro.preso || altro.tenuto) return;
    if (lama) {
      // La spada (o la lama di energia): si controlla tutta la lama, non solo la mano.
      const m = f.p.manoA, g = f.p.gomitoA, L = Math.hypot(m.x - g.x, m.y - g.y) || 1;
      const ux = (m.x - g.x) / L, uy = (m.y - g.y) / L;
      for (const k of [8, 15, 22, 29]) {
        const x = m.x + ux * k * S, y = m.y + uy * k * S;
        for (const bersaglio of ["testa", "collo", "bacino"]) {
          const b = altro.p[bersaglio];
          if (Math.hypot(x - b.x, y - b.y) < b.r + 4 * S) {
            f.colpito = true;
            colpisci(f, altro, forza * caso(0.9, 1.25), x, y, Math.random() < 0.5 ? "ZAC!" : "SWISH!");
            return;
          }
        }
      }
      return;
    }
    const m = f.p[arto];
    for (const bersaglio of ["testa", "collo", "bacino"]) {
      const b = altro.p[bersaglio];
      if (Math.hypot(m.x - b.x, m.y - b.y) < b.r + 6 * S) {
        f.colpito = true;
        colpisci(f, altro, forza * caso(0.85, 1.3), m.x, m.y);
        return;
      }
    }
  }

  // Le scritte disegnate seguono la lingua scelta, se il dizionario c'è (sul
  // sito è `lingue.js`; nell'estensione lo stesso file, accanto a questo).
  function dici(testo) {
    try {
      const l = window.__lingue;
      return (l && l.lingua() !== "it" && l.traduci(testo, l.lingua())) || testo;
    } catch (errore) { return testo; }
  }
  function scrivi(testo, x, y, grande) {
    if (audio.acceso) suonaParola(testo, x, grande);
    scritte.push({ testo: dici(testo), x: Math.max(50, Math.min(W - 50, x)), y: Math.max(26, y), vita: grande ? 70 : 26, grande });
  }

  const SUONI_TEL = ["DRIIN!", "CRACK!", "BIP!", "SPLASH!", "NOTIFICA!", "TRIIN!"];
  const SUONI_OGGETTO = { orologio: ["BZZT!", "BIP!", "TIC!"], tablet: ["SBONK!", "SLAP!", "TONF!"],
                          pc: ["THUD!", "CTRL+ALT+CANC!", "BSOD!"], pistola: ["TONK!", "CLANG!"], spada: ["CLANG!", "TONK!"],
                          bazooka: ["CLONK!", "TONK!"], lanciafiamme: ["CLONK!", "SBONK!"],
                          sasso: ["TONK!", "STOCK!", "SDENG!"] };

  function colpisci(f, altro, forza, x, y, suono) {
    if (fatale && altro && altro.tipo) return;                   // durante il colpo finale conta solo la scena
    if (altro && altro.fuoriCampo) return;                       // chi è dentro il buco nero non si può colpire
    // Nella corsa l'eroe non va K.O. a colpi contati: ogni colpo toglie vita alla corsa.
    const eroeColpito = !!(corsa && corsa.chi && altro && altro.tipo === corsa.chi);
    if (eroeColpito && (corsa.invuln > 0 || corsa.scudo > 0)) { scintille(x, y, 6, "#bfe9ff"); return; }
    // Il colpo che chiuderebbe il round, nel round buono: al suo posto parte la mossa finale.
    if (fataleRound && f && f.tipo && f.p && altro && altro.tipo && altro.danni + 1 >= altro.soglia && puoFinire(f, altro)) { avviaFatale(f, altro); return; }
    // Una parata di fronte ferma quasi tutto, ma il colpo si sente.
    if (altro.esploso) return;
    // TREGUA (l'orda di zombie): i colpi dell'uno non fanno niente all'altro.
    if (orda && f && f.tipo && altro.tipo && f.tipo !== altro.tipo) return;
    if (barrieraRegge(altro, forza, x, y)) return;
    const taglio = !!TAGLI[f.azione] || f.azione === "scattoLama";
    // Chi si sta trasformando non si tocca: il colpo rimbalza.
    if (altro.azione === "trasforma" && altro.t < 70) {
      scintille(x, y, 8, COLORI_ANIME[altro.tipo]);
      if (f.p) for (const n in f.p) f.p[n].ox += f.dir * 4 * S;
      fermoColpo = Math.max(fermoColpo, 2);
      return;
    }
    if (altro.azione === "para" && altro.dir === -f.dir) {
      impara(altro, "para", 1, 1); impara(f, f.azione, -1, 0);
      if (livelloDi(altro.tipo) >= 3 && Math.random() < 0.5) altro.combo = 1;
      scrivi(taglio || suono === "BANG!" ? "CLANG!" : "PARATO!", x, y - 6 * S, false);
      scintille(x, y, 5, "#bfe9ff");
      for (const n in altro.p) altro.p[n].ox -= f.dir * forza * 0.12 * S;
      fermoColpo = 2;
      return;
    }
    if (f.furia > 0) forza *= 1.5;
    if (f.potenziato > 0) forza *= f.forma >= 2 ? 1.7 : 1.4;
    if (f.piccolo > 0) forza *= 0.5;
    // Un colpo su chi è nel ghiaccio manda in pezzi il blocco, e fa più male.
    if (altro.gelato > 0) { rompiGhiaccio(altro, true); forza *= 1.3; }
    if (anime && f.p) { f.ki = Math.min(100, f.ki + 4); altro.ki = Math.min(100, altro.ki + 2); }
    if (altro.tel) lasciaCadere(altro);
    if (altro.tiene) molla(altro);
    altro.paracadute = 0; altro.scendeApposta = 0;
    if (altro.volo && altro.jet > 0) { altro.recupero = 24; altro.scatto = 0; }
    else if (altro.jet > 0 && Math.random() < 0.6) { altro.jet = 0; altro.caos = 0; }
    // L'eroe della corsa picchia più forte coi pugni pesanti, e ogni colpo carica il colpo finale.
    if (corsa && corsa.chi && f && f.tipo === corsa.chi && altro !== f) { altro.danni += forzaCorsa() - 1; caricaCorsa(CORSA.perColpo); }
    altro.danni++;
    let ko = altro.danni >= altro.soglia;
    if (eroeColpito) { altro.danni = 0; ko = feritaEroe(Math.min(forza, 7) * 2, x, y); }
    // Ha imparato qualcosa: chi ha colpito rifà volentieri quella mossa, chi
    // era a metà di un'altra azione la rimpiange, chi l'ha presa si copre di più.
    impara(f, f.azione, 1, ko ? 3 : 1);
    if (COLPI[altro.azione]) impara(altro, altro.azione, -1, 0);
    if (cervello[altro.tipo]) {
      const pe = cervello[altro.tipo].pesi;
      pe.para = Math.min(1.8, pe.para * 1.015); pe.schiva = Math.min(1.8, pe.schiva * 1.015);
    }
    if (livelloDi(f.tipo) >= 2 && !ko && Math.random() < 0.14 * livelloDi(f.tipo)) f.combo = 1;
    // Il segno del colpo, qualche schizzo e, con le armi pesanti, un arto via.
    segna(altro, x, y, forza);
    schizza(altro, x, y, Math.round(1 + forza * 0.35), forza / 4);
    if (taglio && eMela(altro) && Math.random() < 0.45 && taglia(altro, f)) { /* tagliata in due */ }
    else if (taglio && Math.random() < (lame() ? 0.5 : 0.35)) smembra(altro, x, y);
    else if (suono === "BANG!" && Math.random() < 0.2) smembra(altro, x, y);
    if (eMela(altro) && (forza > 4.6 || suono === "BANG!" || taglio) && Math.random() < 0.4) mordi(altro, x, y);
    scintille(x, y, ko ? 16 : 9, f.furia > 0 ? "#ff6a3a" : "#ffe27a");
    fermoColpo = ko ? 9 : 3;
    if (ko) scossa = 12;
    const spinta = forza * S * (ko ? 1.9 : 1);
    for (const n in altro.p) {
      const peso = n.startsWith("piede") || n.startsWith("ginocchio") ? 0.35 : 1;
      altro.p[n].ox -= f.dir * spinta * peso;
      altro.p[n].oy += spinta * (ko ? 0.55 : 0.3);
    }
    altro.dolore = 22;
    altro.azione = null;
    altro.scalata = null;
    scrivi(suono || SUONI[Math.floor(Math.random() * SUONI.length)], x, y - 6 * S, false);
    if (ko && eroeColpito) { altro.ko = Math.max(altro.ko, 70); altro.inVolo = true; }
    else if (ko) segnaKO(f, altro);
    else altro.stordito = 12;
  }

  function segnaKO(f, altro) {
    if (fatale && !fatale.io) return;                            // durante il colpo finale il K.O. lo dà la scena
    if (corsa && corsa.chi) { altro.koVero = true; koCorsa(f, altro); return; }
    altro.koVero = true;
    for (const l of lottatori) l.mutato = false;                 // il round nuovo: la rimonta torna buona
    if (altro.forma && altro.potenziato > 1) altro.potenziato = 1;
    risolviScommessa(f.tipo && f !== altro ? f.tipo : (altro.tipo === "robot" ? "mela" : "robot"));
    altro.ko = Math.round(caso(110, 170)); altro.danni = 0; altro.soglia = Math.round(caso(3, 6));
    if (f.tipo) punteggio[f.tipo]++;
    // Chi vince balla (01/10/2026, su richiesta), appena l'altro è giù.
    if (f.p && f !== altro) f.daBallare = true;
    // Ogni round un carattere nuovo: più aggressivo o più cauto.
    for (const l of lottatori) nuovoCarattere(l);
    salvaCervello(true);
    // (nel colpo finale il conto va più in alto: sotto ci sono già il titolo della scena e il rumore del colpo)
    scrivi("K.O.!  " + punteggio.robot + "–" + punteggio.mela, fatale ? (fatale.da.p.bacino.x + altro.p.bacino.x) / 2 : altro.p.bacino.x,
           Math.max(testataBasso + 30 * S, altro.base - (fatale ? 158 : 72) * S), true);
    prossimoRoundFatale();
    controllaFinale(f.tipo, altro, f);
  }

  // --- Prese e lanci dell'avversario -----------------------------------
  // Si afferra l'altro per il collo e: lo si alza sopra la testa e lo si
  // scaglia avanti, lo si fa roteare e lo si lascia andare, o lo si ribalta
  // all'indietro (suplex). Il punto preso segue le mani; il resto penzola.
  const DURATE_PRESA = { sopra: 42, rotea: 47, suplex: 38 };
  function puntoPresa(f) {
    const t = Math.max(0, f.t - 10);
    if (f.mossaPresa === "rotea") {
      const th = t * 0.3;
      return [60 + 6 * Math.sin(th * 0.5), 28 * Math.cos(th)];
    }
    if (f.mossaPresa === "suplex") {
      const th = Math.min(1, t / 24) * Math.PI * 0.92;
      return [50 + 38 * Math.sin(th), 26 * Math.cos(th)];
    }
    const k = Math.min(1, t / 14), indietro = t > 22 ? Math.min(1, (t - 22) / 8) : 0;
    return [50 + 36 * k, 22 - 20 * k - 8 * indietro];
  }
  function agguanta(f, altro) {
    f.tiene = altro;
    altro.tenuto = { da: f, x: altro.p.collo.x, y: altro.p.collo.y };
    altro.azione = null; altro.scalata = null; altro.jet = 0; altro.caos = 0; altro.paracadute = 0;
    if (altro.tel) lasciaCadere(altro);
    if (altro.arma) lasciaArma(altro);
    altro.fantasma = true;
    scrivi("HOP!", altro.p.collo.x, altro.p.collo.y - 16 * S, false);
  }
  function molla(f) {
    const v = f.tiene;
    f.tiene = null;
    if (!v) return;
    v.tenuto = null; v.ko = Math.max(v.ko, 30); v.inVolo = true;
  }
  function scaglia(f) {
    const v = f.tiene;
    f.tiene = null;
    if (!v) return;
    v.tenuto = null;
    const m = f.mossaPresa;
    const [vx, vy] = m === "suplex" ? [-f.dir * 4, 8] : m === "rotea" ? [f.dir * 13, -5] : [f.dir * 11, -6];
    for (const n in v.p) { v.p[n].ox = v.p[n].x - vx * S; v.p[n].oy = v.p[n].y - verso * vy * S; }
    v.inVolo = true;
    v.danni += 2;
    impara(f, "presa", 1, 2);
    scrivi(m === "suplex" ? "SUPLEX!" : m === "rotea" ? "WHEEE!" : "VOLA!", v.p.collo.x, v.p.collo.y - 18 * S, false);
    if (v.danni >= v.soglia) segnaKO(f, v);
    else v.ko = Math.max(v.ko, 50);
  }
  function aggiornaPresa(f, altro) {
    if (!f.tiene) {
      if (f.t !== 10) return;
      const ok = altro && !altro.ko && !altro.preso && !altro.tenuto && !altro.esploso && !(altro.jet > 0) &&
        altro.azione !== "schiva" && Math.abs(altro.base - f.base) <= 18 * S && Math.abs(altro.cx - f.cx) < 32 * S;
      if (!ok) { impara(f, "presa", -1, 0); f.azione = null; f.pensa = Math.round(caso(6, 16)); return; }
      agguanta(f, altro);
    }
    const [h, dx] = puntoPresa(f);
    f.tiene.tenuto.x = f.cx + dx * f.dir * S;
    f.tiene.tenuto.y = f.base - verso * (h * S + 2 * S);
  }

  // --- La presa col mouse o col dito -----------------------------------
  const presa = { f: null, tel: null, punto: null, x: 0, y: 0, mosso: false };
  let appenaLanciato = false, clicMio = false;

  let raggioPresa = 16;   // in unità S: il dito è più grosso del mouse
  function chiTrovo(x, y) {
    let migliore = null, distanza = raggioPresa * S;
    for (const f of lottatori) {
      if (f.esploso) continue;
      for (const n in f.p) {
        const d = Math.hypot(f.p[n].x - x, f.p[n].y - y) - f.p[n].r;
        if (d < distanza) { distanza = d; migliore = [f, n]; }
      }
      // Il busto (e la mela intera) si prende in tutta la sua larghezza.
      const cxB = (f.p.collo.x + f.p.bacino.x) / 2, cyB = (f.p.collo.y + f.p.bacino.y) / 2;
      if (Math.hypot(cxB - x, cyB - y) < 14 * S && (!migliore || distanza > 0)) {
        migliore = [f, "collo"]; distanza = 0;
      }
    }
    return migliore;
  }

  function telefonoSotto(x, y) {
    let migliore = null, d0 = (raggioPresa - 1) * S;
    for (const t of telefoni) {
      if (t.stato === "portato" || t.stato === "impugnato") continue;
      const d = Math.hypot(t.x - x, t.y - y) - t.r * 0.6;
      if (d < d0) { d0 = d; migliore = t; }
    }
    return migliore;
  }
  const qualcosaSotto = (x, y) => !!(chiTrovo(x, y) || telefonoSotto(x, y));

  function prendi(evento) {
    if (audio.acceso) preparaAudio();                            // i browser lasciano suonare solo dopo un gesto
    if (fermo || (evento.button !== undefined && evento.button > 0)) return;
    const bersaglio = evento.target;
    if (bersaglio && bersaglio.closest && bersaglio.closest(".ring-pannello, .ultimora-barra, .corsa-nome")) return;   // (il campo del nome della corsa è un vero modulo)
    // Nell'estensione i tasti stanno nello shadow DOM: un clic lì non prende lottatori.
    if (ospite && (bersaglio === ospite || (evento.composedPath && evento.composedPath().indexOf(ospite) >= 0))) return;
    // La mira sta sopra a tutto: il secondo tocco fa partire il colpo.
    if (mira) {
      sparaMira();
      clicMio = true;
      if (evento.preventDefault) evento.preventDefault();
      if (evento.stopPropagation) evento.stopPropagation();
      riparti();
      return;
    }
    // La corsa: i suoi tasti, e nei menu ogni tocco è suo.
    if (corsa || classifica.aperta) {
      const t = tastoCorsa(evento.clientX, evento.clientY);
      if (t) { suona("clic"); t.fa(); }
      else if (corsa && corsa.fase === "scelta") {
        // Nella scelta si può anche toccare direttamente il personaggio.
        const f = !corsa.bottega && lottatori.find((l) => l.p && !l.fuoriCampo && Math.hypot(l.p.bacino.x - evento.clientX, l.p.bacino.y - 12 * S - evento.clientY) < 46 * S);
        if (f) scegliEroe(f.tipo);
      }
      if (t || corsaModale()) {
        clicMio = true;
        if (evento.preventDefault) evento.preventDefault();
        if (evento.stopPropagation) evento.stopPropagation();
        riparti();
        return;
      }
    }
    // I tasti dello scontro di energie: si martellano. Vengono prima di tutto il resto.
    const tasto = sottoTastoSfida(evento.clientX, evento.clientY);
    if (tasto >= 0) {
      tifa(tasto ? sfida.b : sfida.a);
      clicMio = true;
      if (evento.preventDefault) evento.preventDefault();
      if (evento.stopPropagation) evento.stopPropagation();
      riparti();
      return;
    }
    // Il controller radiale sta sopra a tutto: un clic lì è un comando, non una presa.
    const zona = sottoRadiale(evento.clientX, evento.clientY);
    if (zona > -2) {
      if (zona === -1) radiale.giu = { x: evento.clientX, y: evento.clientY, mosso: false };
      else { const f = comandato(), ok = !!(f && ordina(f, vociRadiale()[zona][0])); radiale.lampo = { i: zona, ok, t: 8 }; radiale.detto = { i: zona, fino: tempo + 70 }; }
      radiale.sopra = zona; radiale.dito = evento.pointerType === "touch"; clicMio = true;
      if (evento.preventDefault) evento.preventDefault();
      if (evento.stopPropagation) evento.stopPropagation();
      riparti();
      return;
    }
    raggioPresa = evento.pointerType === "touch" ? 30 : 16;
    const tel = telefonoSotto(evento.clientX, evento.clientY);
    const trovato = tel ? null : chiTrovo(evento.clientX, evento.clientY);
    if (tel) {
      presa.f = null; presa.tel = tel; presa.x = evento.clientX; presa.y = evento.clientY; presa.mosso = false;
      tel.stato = "preso"; tel.da = null;
      if (evento.preventDefault) evento.preventDefault();
      if (evento.stopPropagation) evento.stopPropagation();
      radiceHtml("add", "ring-trascina");
      riparti();
      return;
    }
    if (!trovato) return;
    const [f, punto] = trovato;
    if (sfida && (f === sfida.a || f === sfida.b)) {
      tifa(f);
      if (evento.preventDefault) evento.preventDefault();
      if (evento.stopPropagation) evento.stopPropagation();
      clicMio = true;                                 // il clic che segue non arriva alla pagina sotto
      return;
    }
    presa.f = f; presa.punto = punto; presa.x = evento.clientX; presa.y = evento.clientY; presa.mosso = false;
    if (f.tiene) molla(f);
    if (f.tenuto && f.tenuto.da) molla(f.tenuto.da);
    f.paracadute = 0;
    f.preso = punto; f.azione = null; f.scalata = null; f.forza = 0;
    // In mano passa attraverso gli elementi, come un oggetto sollevato:
    // torna solido appena lasciato, quando non ne ha più nessuno addosso.
    f.fantasma = true;
    if (evento.preventDefault) evento.preventDefault();
    if (evento.stopPropagation) evento.stopPropagation();
    radiceHtml("add", "ring-trascina");
    riparti();
  }

  function muovi(evento) {
    if (radiale.giu) {
      // Trascinando il ritratto oltre metà finestra, il controller passa nell'altro angolo in basso.
      const q = radiale.giu;
      if (Math.hypot(evento.clientX - q.x, evento.clientY - q.y) > 8) q.mosso = true;
      if (q.mosso) {
        const lato = evento.clientX < W / 2 ? "sx" : "dx";
        if (lato !== radiale.lato) { radiale.lato = lato; try { deposito.setItem("mut-ring-radiale-lato", lato); } catch (errore) { /* pazienza */ } fattiInLa(); }
      }
      if (evento.preventDefault) evento.preventDefault();
      return;
    }
    if ((sfida || puntaSfida) && !presa.f && !presa.tel) {
      // Sopra un tasto dello scontro il puntatore è un dito.
      const su = sottoTastoSfida(evento.clientX, evento.clientY) >= 0;
      if (su !== puntaSfida) { puntaSfida = su; radiceHtml(su ? "add" : "remove", "ring-punta"); }
      if (su) return;
    }
    if (radiale.aperto && !presa.f && !presa.tel) {
      const zona = sottoRadiale(evento.clientX, evento.clientY);
      if (zona !== radiale.sopra) { radiale.sopra = zona; radiceHtml(zona > -2 ? "add" : "remove", "ring-punta"); if (zona > -2) radiceHtml("remove", "ring-presa"); }
      if (zona > -2) return;
    }
    if (presa.f || presa.tel) {
      if (Math.hypot(evento.clientX - presa.x, evento.clientY - presa.y) > 2) presa.mosso = true;
      presa.x = evento.clientX; presa.y = evento.clientY;
      if (evento.preventDefault) evento.preventDefault();
      return;
    }
    if (fermo || evento.pointerType === "touch") return;
    raggioPresa = 16;
    radiceHtml(qualcosaSotto(evento.clientX, evento.clientY) ? "add" : "remove", "ring-presa");
  }

  function lascia() {
    if (clicMio) { clicMio = false; appenaLanciato = true; setTimeout(() => { appenaLanciato = false; }, 0); }
    if (radiale.giu) {
      // Un clic secco sul centro: si passa a comandare l'altro.
      if (!radiale.giu.mosso && !(corsa && corsa.chi)) radiale.chi = radiale.chi === "robot" ? "mela" : "robot";
      radiale.giu = null;
      if (radiale.dito) radiale.sopra = -2;
      return;
    }
    if (radiale.dito) { radiale.sopra = -2; radiale.dito = false; }
    if (presa.tel) {
      const t = presa.tel;
      presa.tel = null;
      t.stato = "volo"; t.protetto = 0; t.da = null; t.lanciatore = null; t.cool = 6; t.va = caso(-0.3, 0.3);
      t.armato = !!SPECIALI[t.tipo];
      if (presa.mosso) { appenaLanciato = true; setTimeout(() => { appenaLanciato = false; }, 0); }
      radiceHtml("remove", "ring-trascina");
      return;
    }
    const f = presa.f;
    if (!f) return;
    presa.f = null;
    f.preso = null;
    // Lasciato sopra un elemento con i piedi un po' dentro: lo si posa
    // sopra, invece di farlo cadere attraverso. Solo se l'affondo è poco:
    // un lottatore lasciato a metà di un paragrafo ci cade attraverso.
    let su = 0;
    for (const n in f.p) {
      const pt = f.p[n];
      for (const o of ostacoli) {
        if (pt.x > o.l - pt.r && pt.x < o.r + pt.r && pt.y > o.t - pt.r && pt.y < o.b + pt.r) {
          su = Math.max(su, pt.y - (o.t - pt.r));
        }
      }
    }
    if (su > 0 && su < 40 * S) {
      for (const n in f.p) { f.p[n].y -= su; f.p[n].oy -= su; }
    }
    if (su < 40 * S) f.fantasma = dentroQualcosa(f);
    // Floscio finché non si ferma: poi si rialza da solo.
    f.ko = Math.max(f.ko, 40);
    f.inVolo = true;
    if (presa.mosso) {
      appenaLanciato = true;
      setTimeout(() => { appenaLanciato = false; }, 0);
      f.lanciato = 70;
    }
    radiceHtml("remove", "ring-trascina");
  }

  // Un lottatore portato col puntatore (o appena lanciato) è un'arma: se
  // arriva veloce addosso all'altro, lo colpisce.
  function colpoDaMano(f, altro) {
    if (f.colpoMano > 0) f.colpoMano--;
    if (f.lanciato > 0) f.lanciato--;
    if (!(f.preso || f.lanciato > 0) || f.colpoMano > 0 || f.esploso) return;
    if (!altro || altro.esploso || altro.preso || altro.ko > 0 && !altro.inVolo) return;
    const ref = f.preso ? f.p[f.preso] : f.p.bacino;
    const vx = ref.x - ref.ox, vy = ref.y - ref.oy, v = Math.hypot(vx, vy);
    if (v < 4 * S) return;
    for (const n of ["testa", "collo", "bacino", "manoA", "manoD", "piedeA", "piedeD"]) {
      const q = f.p[n];
      for (const m of ["testa", "collo", "bacino"]) {
        const b = altro.p[m];
        if (Math.hypot(q.x - b.x, q.y - b.y) < q.r + b.r + 5 * S) {
          const colpitore = Object.create(f);
          colpitore.dir = Math.sign(vx) || f.dir; colpitore.azione = null;
          const forza = Math.min(7.5, 2.4 + v / (1.6 * S));
          colpisci(colpitore, altro, forza, (q.x + b.x) / 2, (q.y + b.y) / 2, forza > 5.5 ? "SBONK!" : "TONK!");
          for (const k in altro.p) { altro.p[k].ox -= vx * 0.35; altro.p[k].oy -= vy * 0.35; }
          altro.inVolo = true; altro.ko = Math.max(altro.ko, forza > 5 ? 30 : 0);
          f.colpoMano = 22; f.dolore = 12;
          return;
        }
      }
    }
  }

  function radiceHtml(come, classe) {
    const radice = document.documentElement;
    if (radice && radice.classList) radice.classList[come](classe);
    if (classe === "ring-trema") tremaPagina = come === "add";
  }
  let tremaPagina = false;
  const radiceTrema = () => tremaPagina;

  window.addEventListener("pointerdown", prendi, { capture: true, passive: false });
  window.addEventListener("pointermove", muovi, { capture: true, passive: false });
  window.addEventListener("pointerup", lascia, { capture: true });
  window.addEventListener("pointercancel", lascia, { capture: true });
  // Sul telefono il dito che prende un lottatore non deve far scorrere la pagina.
  window.addEventListener("touchstart", (e) => {
    const t = e.touches && e.touches[0];
    raggioPresa = 30;
    if (t && !fermo && (mira || ((corsa || classifica.aperta) && (corsaModale() || tastoCorsa(t.clientX, t.clientY))) || qualcosaSotto(t.clientX, t.clientY) || sottoRadiale(t.clientX, t.clientY) > -2 || sottoTastoSfida(t.clientX, t.clientY) >= 0)) e.preventDefault();
  }, { passive: false });
  // Finché si tiene qualcosa col dito la pagina non deve scorrere.
  window.addEventListener("touchmove", (e) => {
    if ((presa.f || presa.tel || radiale.giu) && e.cancelable) e.preventDefault();
  }, { passive: false });
  // Un lancio che finisce sopra un collegamento non lo deve aprire.
  window.addEventListener("click", (e) => {
    if (appenaLanciato) { e.preventDefault(); e.stopPropagation(); }
  }, { capture: true });

  // --- Un passo di fisica (60 al secondo) ------------------------------
  const GRAVITA = 0.42;
  const VELOCITA_MAX = 15;

  // CHI È IN PIEDI usa gli elementi della pagina come PIATTAFORME (02/10/2026):
  // ci si posa da sopra, e per il resto il corpo ci passa davanti. Prima ogni
  // punto del corpo urtava ogni lato di ogni elemento: su una pagina vera, con
  // tasti, campi e immagini all'altezza della testa, i lottatori restavano
  // piegati o incastrati in fondo alla finestra. Chi vola via dopo un colpo o
  // è a terra, invece, urta e rimbalza su tutti i lati come prima.
  function urta(f, pt, piattaforma) {
    const r = pt.r;
    let urto = 0;
    const prima = Math.hypot(pt.x - pt.ox, pt.y - pt.oy);
    if (piattaforma) {
      for (const o of ostacoli) {
        if (pt.x < o.l - r || pt.x > o.r + r) continue;
        // Solo scendendo, e solo se un attimo prima si era sopra il bordo alto.
        if (pt.oy <= o.t - r + 1 && pt.y > o.t - r) {
          const vx = pt.x - pt.ox, vy = pt.y - pt.oy;
          pt.y = o.t - r; if (vy > 0) pt.oy = pt.y; pt.ox = pt.x - vx * 0.7;
          urto = Math.max(urto, prima);
        }
      }
      return urto;
    }
    for (const o of ostacoli) {
      const dentroX = pt.x >= o.l - r && pt.x <= o.r + r;
      // Attraversato in un passo solo (un lancio veloce su una riga sottile):
      // conta come urto sul lato da cui arrivava.
      if (dentroX && pt.oy <= o.t - r + 0.5 && pt.y > o.b + r) { pt.y = o.t - r + 0.01; }
      else if (dentroX && pt.oy >= o.b + r - 0.5 && pt.y < o.t - r) { pt.y = o.b + r - 0.01; }
      if (pt.x < o.l - r || pt.x > o.r + r || pt.y < o.t - r || pt.y > o.b + r) continue;
      const vx = pt.x - pt.ox, vy = pt.y - pt.oy;
      // Da che parte è entrato: dalla posizione di prima, non dalla
      // penetrazione minima, sennò una riga sottile si attraversa.
      let lato;
      if (pt.oy <= o.t - r + 1) lato = "su";
      else if (pt.oy >= o.b + r - 1) lato = "giu";
      else if (pt.ox <= o.l - r + 1) lato = "sx";
      else if (pt.ox >= o.r + r - 1) lato = "dx";
      else {
        const m = Math.min(pt.y - (o.t - r), (o.b + r) - pt.y, pt.x - (o.l - r), (o.r + r) - pt.x);
        lato = m === pt.y - (o.t - r) ? "su" : m === (o.b + r) - pt.y ? "giu"
             : m === pt.x - (o.l - r) ? "sx" : "dx";
      }
      if (lato === "su") { pt.y = o.t - r; if (vy > 0) pt.oy = pt.y; pt.ox = pt.x - vx * 0.7; }
      else if (lato === "giu") { pt.y = o.b + r; if (vy < 0) pt.oy = pt.y; }
      else if (lato === "sx") { pt.x = o.l - r; pt.ox = pt.x + Math.max(0, vx) * 0.3; }
      else { pt.x = o.r + r; pt.ox = pt.x + Math.min(0, vx) * 0.3; }
      urto = Math.max(urto, prima);
    }
    return urto;
  }

  function scambiaGambe(f) {
    for (const [a, d] of [["piedeA", "piedeD"], ["ginocchioA", "ginocchioD"]]) {
      const A = f.p[a], D = f.p[d];
      for (const k of ["x", "y", "ox", "oy"]) { const t = A[k]; A[k] = D[k]; D[k] = t; }
    }
  }
  // Le ginocchia che si DISEGNANO: fra l'anca e il piede, piegate sempre dalla
  // parte della faccia (o in su, a gamba distesa per terra). Quelle della
  // fisica finivano spesso piegate all'indietro. Da K.O. valgono quelle vere:
  // un corpo abbandonato si piega come capita.
  const COSCIA = 15.2, STINCO = 14.5;
  function ginocchia(f) {
    const p = f.p, k = f.ko > 0 ? 0 : Math.max(0, Math.min(1, f.forza * 1.5));
    const una = (g, piede) => {
      if (k <= 0) return g;
      const hx = p.bacino.x, hy = p.bacino.y, dx = piede.x - hx, dy = piede.y - hy, lun = Math.hypot(dx, dy) || 1;
      const L1 = COSCIA * S, L2 = STINCO * S, d = Math.max(Math.abs(L1 - L2) + 0.5, Math.min(L1 + L2 - 0.01, lun));
      const ux = dx / lun, uy = dy / lun;
      const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d), alto = Math.sqrt(Math.max(0, L1 * L1 - a * a));
      let nx = -uy, ny = ux;
      if (Math.abs(nx) > 0.25 ? nx * f.dir < 0 : ny * verso > 0) { nx = -nx; ny = -ny; }
      const ix = hx + ux * a + nx * alto, iy = hy + uy * a + ny * alto;
      return { x: g.x + (ix - g.x) * k, y: g.y + (iy - g.y) * k };
    };
    return [una(p.ginocchioA, p.piedeA), una(p.ginocchioD, p.piedeD)];
  }

  function dentroQualcosa(f) {
    for (const n in f.p) {
      const pt = f.p[n];
      for (const o of ostacoli) {
        if (pt.x > o.l - pt.r && pt.x < o.r + pt.r && pt.y > o.t - pt.r && pt.y < o.b + pt.r) return true;
      }
    }
    return false;
  }

  // --- Particelle: scintille, polvere, stelline -------------------------
  function scintille(x, y, n, colore) {
    for (let i = 0; i < n && particelle.length < 160; i++) {
      const a = caso(0, Math.PI * 2), v = caso(1.5, 5) * S;
      particelle.push({ tipo: "scintilla", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - S,
                        vita: Math.round(caso(12, 22)), max: 22, colore });
    }
  }
  function polvere(x, y, n) {
    for (let i = 0; i < n && particelle.length < 160; i++) {
      particelle.push({ tipo: "polvere", x: x + caso(-5, 5) * S, y, vx: caso(-1.2, 1.2) * S,
                        vy: caso(-0.9, -0.2) * S, vita: Math.round(caso(16, 28)), max: 28, colore: "#b9b4ab" });
    }
  }
  function schegge(x, y, n, colore) {
    for (let i = 0; i < n && particelle.length < 160; i++) {
      const a = caso(0, Math.PI * 2), v = caso(1, 4) * S;
      particelle.push({ tipo: "scheggia", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 2 * S,
                        vita: Math.round(caso(26, 44)), max: 44, colore, rot: caso(0, 6) });
    }
  }
  function nota(f) {
    if (particelle.length >= 170) return;
    const t = f.p.testa;
    particelle.push({ tipo: "nota", x: t.x + caso(-12, 12) * S, y: t.y - 14 * S, vx: caso(-0.4, 0.4) * S, vy: -caso(0.5, 0.9) * S,
                      vita: 55, max: 55, testo: Math.random() < 0.5 ? "\u266A" : "\u266B",
                      colore: ["#e0447a", "#2f72e0", "#2e9e6b", "#ec8a3a"][Math.floor(Math.random() * 4)] });
  }
  function aggiornaParticelle() {
    for (const q of particelle) {
      q.x += q.vx; q.y += q.vy; q.vita--;
      if (q.tipo === "onda" || q.tipo === "lampo" || q.tipo === "vento" || q.tipo === "zip" || q.tipo === "linea" || q.tipo === "taglio") continue;
      if (q.tipo === "mote") {
        // Un granello d'energia che vola verso la sfera che si sta formando.
        const s = q.verso && q.verso.sfera;
        if (!s) { q.vita = Math.min(q.vita, 6); continue; }
        const dx = s.x - q.x, dy = s.y - q.y, d = Math.hypot(dx, dy) || 1, v = Math.min(d, 9 * S);
        q.x += dx / d * v; q.y += dy / d * v;
        if (d < s.r) q.vita = 0;
        continue;
      }
      if (q.tipo === "nota") { q.vx = q.vx * 0.98 + Math.sin(q.vita * 0.2) * 0.05 * S; continue; }
      if (q.tipo === "fuoco") { q.vx *= 0.9; q.vy = q.vy * 0.9 - 0.04 * S; q.r *= 1.03; continue; }
      if (q.tipo === "fumo") { q.vx *= 0.97; q.vy *= 0.985; q.r *= 1.012; continue; }
      if (q.tipo === "brace") { q.vx *= 0.98; q.vy += 0.06 * S * verso; if (q.y > pavimento) q.vita = 0; continue; }
      if (q.tipo === "detrito" || q.tipo === "pezzetto" || q.tipo === "goccia" || q.tipo === "fiocco") {
        if (q.tipo === "detrito" || q.tipo === "pezzetto") { q.vy += 0.32 * S * moltG * verso; q.rot += q.va; }
        else if (q.tipo === "goccia") q.vy += 0.3 * S * moltG * verso;
        else if (q.tipo === "fiocco") q.x += Math.sin(q.fase + q.vita * 0.03) * 0.4 * S;
        // Dove tocca: il pavimento o il bordo alto di un elemento della pagina.
        let su = q.y >= pavimento - 1 ? pavimento - 1 : null;
        if (su === null) for (const o of ostacoli) if (q.x > o.l && q.x < o.r && q.y >= o.t && q.y - q.vy < o.t + 1) { su = o.t; break; }
        if (su === null) { if (q.x < 0 || q.x > W) { if (q.tipo === "detrito" || q.tipo === "pezzetto") { q.vx = -q.vx * 0.6; q.x = Math.max(0, Math.min(W, q.x)); } else q.vita = 0; } continue; }
        if (q.tipo === "detrito" || q.tipo === "pezzetto") {
          q.y = su; q.vy = Math.abs(q.vy) > 1.2 * S ? -Math.abs(q.vy) * 0.42 : 0; q.vx *= 0.7; q.va *= 0.7;
        } else {
          q.vita = 0;
          if (q.tipo === "goccia") macchia(q.x, su, q.r, q.colore);
          else if (q.tipo === "fiocco") { if (su === pavimento - 1) cumulo = Math.min(7 * S, cumulo + 0.025 * S); }
        }
        continue;
      }
      if (q.tipo === "scintilla") { q.vx *= 0.93; q.vy = q.vy * 0.93 + 0.12 * S; }
      else if (q.tipo === "polvere") { q.vx *= 0.96; q.vy *= 0.96; }
      else if (q.tipo === "fiamma") { q.vx *= 0.94; q.vy *= 0.97; }
      else { q.vy += 0.3 * S * moltG * verso; q.rot += 0.3; if (q.y > pavimento) { q.y = pavimento; q.vy *= -0.4; q.vx *= 0.7; } }
    }
    particelle = particelle.filter((q) => q.vita > 0);
  }

  // --- Gli oggetti che girano per la pagina -----------------------------
  // Telefoni, smartwatch, tablet e portatili (01/10/2026, su richiesta); dopo
  // 70 secondi anche pistole e spade. Ogni oggetto ha la sua sagoma, un peso
  // (un portatile fa più male di un orologio) e uno schermo dove si crepa.
  const FORME = {
    classico: { w: 8, h: 15, peso: 1 }, grande: { w: 9.5, h: 19, peso: 1.1 },
    pieghevole: { w: 12, h: 13, peso: 1.1 }, orologio: { w: 7, h: 8, peso: 0.7 },
    tablet: { w: 17, h: 23, peso: 1.3 }, pc: { w: 24, h: 17, peso: 1.6 },
    duo: { w: 13, h: 15, peso: 1.2 }, bomba: { w: 11, h: 11, peso: 1.2 },
    fumogeno: { w: 7, h: 13, peso: 0.6 }, barattolo: { w: 10, h: 13, peso: 0.7 }, sasso: { w: 11, h: 9, peso: 1.5 },
    pistola: { w: 15, h: 9, peso: 1, arma: true }, spada: { w: 32, h: 6, peso: 1, arma: true },
    // 05/10/2026, chieste da Riccardo: il bazooka spara razzi che scoppiano,
    // il lanciafiamme tiene una vampata lunga che brucia anche il pavimento.
    bazooka: { w: 34, h: 12, peso: 1.6, arma: true }, lanciafiamme: { w: 26, h: 13, peso: 1.4, arma: true },
  };
  const CARICHE = { pistola: 6, spada: 5, bazooka: 2, lanciafiamme: 3 };
  const SPARANO = { pistola: 1, bazooka: 1, lanciafiamme: 1 };
  const azioneArma = (t) => (t && t.tipo === "lanciafiamme" ? "fiammata" : "spara");
  // Da che distanza conviene usare l'arma che si ha in mano.
  function puoSparare(f, d) {
    const t = f.arma && f.arma.tipo;
    if (!t || !SPARANO[t] || f.colpiArma <= 0) return false;
    if (t === "bazooka") return d > 70;                          // il razzo scoppia: meglio da lontano
    if (t === "lanciafiamme") return d > 16 && d < 150;
    return d > 40;
  }
  const COLORI_TEL = ["#2b2f3a", "#c9ced8", "#1f6fd1", "#d1493a", "#2e9e6b", "#8a63d2"];
  const COLORI_PC = ["#b8bec9", "#3a3f4a", "#d9d4cc"];
  const eArma = (t) => !!(t && FORME[t.tipo] && FORME[t.tipo].arma);
  // Fumogeni e barattoli: non fanno male da soli, ma lanciati si aprono.
  const SPECIALI = { fumogeno: 1, barattolo: 1 };
  const ELEMENTI = { fuoco: { nome: "TIZZO", colore: "#ff7a1a" }, scossa: { nome: "ZIP", colore: "#ffd400" }, acqua: { nome: "BOLLA", colore: "#3aa0ff" } };
  const oggettoACaso = () => scegli([[3, "fumogeno"], [5, "barattolo"]].concat(libero("armi") ? [[2, "pistola"], [2, "spada"], [2, "bomba"], [1.2, "bazooka"], [1.6, "lanciafiamme"]] : []));

  function scegliForma() {
    if (senzaTelefoni) return scegli([[3, "fumogeno"], [5, "barattolo"]]);
    const telefono = () => scegli([[50, "classico"], [30, "grande"], [20, "pieghevole"]]);
    if (tempo >= CALMA && Math.random() < 0.16) return Math.random() < 0.65 ? "barattolo" : "fumogeno";
    if (tempo < CALMA) return Math.random() < 0.3 ? "orologio" : telefono();
    const q = scegli([[40, "telefono"], [20, "orologio"], [20, "tablet"], [20, "pc"]]);
    return q === "telefono" ? telefono() : q;
  }

  function nuovoTelefono(x, y, vx, vy, forma) {
    let el = null;
    if (forma && forma.indexOf("barattolo-") === 0) { el = forma.slice(10); forma = "barattolo"; }
    const tipo = forma && FORME[forma] ? forma : scegliForma();
    const F = FORME[tipo], w = F.w * S, h = F.h * S;
    let sch;
    if (F.arma || tipo === "bomba" || tipo === "sasso" || SPECIALI[tipo]) sch = null;
    else if (tipo === "tablet") sch = [-w / 2 + 1.6 * S, -h / 2 + 1.6 * S, w - 3.2 * S, h - 3.2 * S];
    else if (tipo === "orologio") sch = [-w / 2 + 1 * S, -h / 2 + 1 * S, w - 2 * S, h - 2 * S];
    else if (tipo === "pc") sch = [-w / 2 + 1.4 * S, -h / 2 + 1.4 * S, w - 2.8 * S, h * 0.68 - 2.8 * S];
    else sch = [-w / 2 + 1.1 * S, -h / 2 + 1.5 * S, w - 2.2 * S, h - 3 * S];
    const colori = tipo === "pc" || tipo === "tablet" ? COLORI_PC : COLORI_TEL;
    telefoni.push({ x, y, ox: x - vx, oy: y - vy, a: caso(0, 6.28), va: caso(-0.15, 0.15), tipo,
                    w, h, r: Math.max(5, Math.min(11, Math.max(F.w, F.h) * 0.42)) * S, sch, peso: F.peso,
                    stato: "libero", da: null, protetto: 0, cool: 0, apre: 1, fine: 0, morto: false, miccia: 0,
                    ultimo: null, crepe: 0, rotture: [], entra: 0, isolato: 0, scende: 0,
                    colore: tipo === "duo" ? "#d9d4cc" : colori[Math.floor(Math.random() * colori.length)] });
    if (tipo === "barattolo") telefoni[telefoni.length - 1].el = ELEMENTI[el] ? el : scegli([[1, "fuoco"], [1, "scossa"], [1, "acqua"]]);
    if (telefoni.length > 7) {
      const vecchio = telefoni.findIndex((t) => t.stato === "libero");
      if (vecchio >= 0) telefoni.splice(vecchio, 1);
    }
    return telefoni[telefoni.length - 1];
  }

  // GLI OGGETTI ENTRANO ANCHE DAI LATI (02/10/2026, su richiesta). Su certe
  // pagine quelli caduti dall'alto si fermavano tutti sulla testata o sul
  // primo titolo, dove nessuno arriva. Circa una volta su due arrivano da un
  // bordo, con un lancio morbido che li posa all'altezza dei lottatori; mentre
  // entrano non fanno male a nessuno.
  function faEntrare(forma, xAlto, vxAlto) {
    const vivi = lottatori.filter((f) => f.p && !f.esploso);
    if (!vivi.length || verso < 0 || Math.random() < 0.45) return nuovoTelefono(xAlto, -16 * S, vxAlto, 0, forma);
    const da = Math.random() < 0.5 ? -1 : 1;                           // −1: dal bordo sinistro
    const base = Math.max.apply(null, vivi.map((f) => f.base)), centro = vivi.reduce((t, f) => t + f.p.bacino.x, 0) / vivi.length;
    const x0 = da < 0 ? 0 : W, y0 = Math.max(30 * S, base - caso(70, 170) * S);
    const tx = Math.max(40 * S, Math.min(W - 40 * S, centro + caso(-170, 170) * S)), ty = base - 10 * S, T = caso(38, 58);
    const lim = VELOCITA_MAX * S * 0.9;
    const vx = Math.max(-lim, Math.min(lim, (tx - x0) / T));
    const vy = Math.max(-lim * 0.6, (ty - y0) / T - 0.5 * GRAVITA * S * moltG * T);
    const t = nuovoTelefono(x0, y0, vx, vy, forma);
    t.entra = 24; t.cool = Math.round(T) + 12;
    return t;
  }

  function velocitaTel(t) { return Math.hypot(t.x - t.ox, t.y - t.oy); }

  function telefonoVicino(f) {
    let migliore = null, d0 = 260 * S;
    for (const t of telefoni) {
      if (t.stato !== "libero" || velocitaTel(t) > 2 * S || t.tipo === "duo") continue;
      if (Math.abs(t.y - (f.base - verso * 6 * S)) > 22 * S) continue;
      const d = Math.abs(t.x - f.cx);
      if (d < d0) { d0 = d; migliore = t; }
    }
    return migliore;
  }

  function lasciaArma(f) {
    const t = f.arma;
    f.arma = null;
    if (t) { t.stato = "libero"; t.da = null; t.ox = t.x; t.oy = t.y + 1 * S; t.va = caso(-0.2, 0.2); }
  }

  function lasciaCadere(f) {
    const t = f.tel;
    f.tel = null;
    if (t && t.stato === "portato") { t.stato = "libero"; t.da = null; t.ox = t.x; t.oy = t.y; }
  }

  function lanciaTelefono(f, altro) {
    if (f && f.p) suona("taglio", f.p.bacino.x, 0.6);
    const t = f.tel;
    f.tel = null;
    if (!t) return;
    t.stato = "volo"; t.protetto = 14; t.da = f; t.lanciatore = f; t.armato = !!SPECIALI[t.tipo];
    const T = caso(32, 44), mira = puntoMira(f, altro);
    const tx = mira.x + caso(-7, 7) * S, ty = mira.y + caso(-7, 7) * S;
    let vx = (tx - t.x) / T, vy = (ty - t.y) / T - 0.5 * GRAVITA * S * moltG * verso * T;
    const lim = VELOCITA_MAX * S * 0.9;
    vx = Math.max(-lim, Math.min(lim, vx)); vy = Math.max(-lim, Math.min(lim * 0.5, vy));
    t.ox = t.x - vx; t.oy = t.y - vy; t.va = f.dir * caso(0.25, 0.5);
    scrivi("TIÈ!", f.p.manoA.x, f.p.manoA.y - 12 * S, false);
  }

  function rimbalzaTel(t, vx, vy) {
    // Solo contro il pavimento, gli elementi della pagina e i bordi.
    const r = t.r;
    let urto = 0;
    const rim = (nvx, nvy, forza) => {
      t.ox = t.x - nvx; t.oy = t.y - nvy; urto = Math.max(urto, forza);
      t.va = (t.va + (nvx * 0.05 - nvy * 0.02)) * 0.8 + caso(-0.05, 0.05);
    };
    if (t.y > pavimento - r) {
      t.y = pavimento - r;
      rim(vx * 0.86, vy > 1.1 * S ? -vy * 0.45 : 0, Math.abs(vy));
    }
    for (const o of ostacoli) {
      if (t.scende > 0) break;                     // sta scivolando giù dall'elemento su cui era rimasto
      if (t.x < o.l - r || t.x > o.r + r || t.y < o.t - r || t.y > o.b + r) continue;
      if (t.oy <= o.t - r + 1) { t.y = o.t - r; rim(vx * 0.86, vy > 1.1 * S ? -vy * 0.45 : 0, Math.abs(vy)); }
      else if (t.oy >= o.b + r - 1) { t.y = o.b + r; rim(vx, Math.abs(vy) * 0.3, Math.abs(vy)); }
      else if (t.ox <= o.l - r + 1) { t.x = o.l - r; rim(-Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
      else if (t.ox >= o.r + r - 1) { t.x = o.r + r; rim(Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    }
    if (t.entra > 0) { /* sta entrando da un bordo: il bordo non lo ferma */ }
    else if (t.x < r) { if (-vx > 12.5 * S) danneggiaBordo("sinistra", t.y, 0.8); t.x = r; rim(Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    else if (t.x > W - r) { if (vx > 12.5 * S) danneggiaBordo("destra", t.y, 0.8); t.x = W - r; rim(-Math.abs(vx) * 0.5, vy, Math.abs(vx)); }
    if (t.y < r) {
      if (-vy > 12.5 * S) danneggiaBordo("tetto", t.x, 0.8);
      t.y = r;
      if (verso < 0) rim(vx * 0.86, vy < -1.1 * S ? -vy * 0.45 : 0, Math.abs(vy));
      else rim(vx, Math.abs(vy) * 0.3, 0);
    }
    return urto;
  }

  function aggiornaTelefoni() {
    for (const t of telefoni) {
      if (t.inBuco) { t.ox = t.x; t.oy = t.y; continue; }       // dentro il buco nero: fermo (anche la miccia) finché non riesce
      if (t.protetto > 0) t.protetto--;
      if (t.cool > 0) t.cool--;
      if (t.entra > 0) t.entra--;
      if (t.scende > 0) t.scende--;
      if (t.tipo === "bomba") {
        if (!t.miccia && (t.stato === "portato" || t.stato === "preso")) t.miccia = t.stato === "preso" ? 300 : 150;
        if (t.miccia > 0) {
          if (--t.miccia <= 0) { scoppia(t); continue; }
          if (passi % 3 === 0 && particelle.length < MAX_PARTICELLE) {
            const ax = t.x + Math.cos(t.a - 0.9) * 7 * S, ay = t.y + Math.sin(t.a - 0.9) * 7 * S;
            particelle.push({ tipo: "scintilla", x: ax, y: ay, vx: caso(-1, 1) * S, vy: -caso(0.5, 1.5) * S, vita: 10, max: 10, colore: "#ffd84a" });
          }
        }
      }
      if (t.stato === "preso") {
        t.ox = t.x; t.oy = t.y;
        t.x += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, presa.x - t.x));
        t.y += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, presa.y - t.y));
        t.a += 0.04;
        continue;
      }
      if (t.stato === "portato") {
        const f = t.da, m = f && f.p.manoA;
        if (!f || f.tel !== t || !m) { t.stato = "libero"; continue; }
        t.x = t.ox = m.x + f.dir * 0.5 * S; t.y = t.oy = m.y - Math.max(5 * S, t.h * 0.45); t.a = f.dir * 0.2;
        if (t.tipo === "duo") { t.apre = Math.min(1, t.apre + 0.07); t.a = 0; }
        continue;
      }
      if (t.stato === "impugnato") {
        // In mano: l'arma segue l'avambraccio, come se lo continuasse.
        const f = t.da;
        if (!f || f.arma !== t) { t.stato = "libero"; continue; }
        const g = f.p.gomitoA, m = f.p.manoA;
        t.x = t.ox = m.x; t.y = t.oy = m.y;
        t.a = Math.atan2(m.y - g.y, m.x - g.x);
        continue;
      }
      let vx = (t.x - t.ox) * 0.995, vy = (t.y - t.oy) * 0.995;
      const v = Math.hypot(vx, vy), lim = VELOCITA_MAX * S * 1.1;
      if (v > lim) { vx *= lim / v; vy *= lim / v; }
      t.ox = t.x; t.oy = t.y;
      t.x += vx; t.y += vy + GRAVITA * S * moltG * verso;
      t.a += t.va;
      const urto = rimbalzaTel(t, vx, vy);
      // Un fumogeno o un barattolo lanciato si apre dove sbatte.
      if (t.armato && urto > 3 * S && apri(t)) continue;
      if (urto > 13.5 * S && t.y > pavimento - t.r - 1) danneggiaStriscia(t.x, Math.min(1, urto / (VELOCITA_MAX * S)));
      if (urto > 4 * S) {
        polvere(t.x, t.y + t.r, 2);
        if (urto > 8 * S && t.crepe < 4) {
          t.crepe++; rompiSchermo(t); schegge(t.x, t.y, 4, eArma(t) ? "#d9dde6" : "#cfe9ff");
          scrivi(eArma(t) ? "CLANG!" : Math.random() < 0.5 ? "CRACK!" : "CLONK!", t.x, t.y - 14 * S, false);
        }
      }
      // Un lancio finisce quando l'oggetto si ferma: sul pavimento subito, altrove
      // (sopra un elemento della pagina) dopo qualche fotogramma da fermo. Prima,
      // fermo su un elemento, restava «in volo» per sempre e nessuno lo raccoglieva.
      if (t.stato === "volo") {
        t.lento = velocitaTel(t) < 1.2 * S ? (t.lento || 0) + 1 : 0;
        if ((t.lento > 0 && t.y > pavimento - t.r - 2) || t.lento > 8) {
          // Un fumogeno o un barattolo lanciato che si è posato piano si apre lo stesso.
          if (t.armato && apri(t)) continue;
          t.stato = "libero"; t.da = null; t.lento = 0;
        }
      }
      // Fermo su un elemento dove nessun lottatore arriva (la testata, un titolo
      // in alto): dopo cinque secondi scivola giù fino al primo appoggio sotto.
      if (t.stato === "libero" && verso > 0 && t.tipo !== "duo" && t.y < pavimento - t.r - 3 * S && velocitaTel(t) < 0.8 * S &&
          !lottatori.some((f) => !f.esploso && Math.abs(t.y - (f.base - 6 * S)) <= 22 * S)) {
        if (++t.isolato > 300) { t.isolato = 0; t.scende = 8; }
      } else t.isolato = 0;
      // Il sasso di un meteorite si raffredda, e dopo mezzo minuto per terra si sbriciola.
      if (t.tipo === "sasso") {
        if (t.caldo > 0) t.caldo = Math.max(0, t.caldo - 0.004);
        if (t.stato === "libero" && ++t.fine > 1800) { t.morto = true; polvere(t.x, t.y, 6); continue; }
      }
      // Il pieghevole della mela che non ha preso nessuno si spegne in uno sbuffo.
      if (t.tipo === "duo" && t.stato === "libero" && ++t.fine > 90) { t.morto = true; polvere(t.x, t.y, 6); continue; }
      // Un oggetto veloce abbatte anche gli zombie.
      if (orda && t.cool <= 0 && (t.stato === "volo" || velocitaTel(t) > 6 * S)) {
        const z = zombieToccato(t.x, t.y, t.r * 0.7);
        if (z) {
          if (t.tipo === "bomba" && t.miccia > 0) { scoppia(t); continue; }
          if (!(t.armato && apri(t))) {
            colpisciZombie(z, Math.max(3, Math.min(6.5, velocitaTel(t) / (2.2 * S))) * t.peso, Math.sign(t.x - t.ox) || 1, t.x, t.y, t.da);
            t.ox = t.x + (t.x - t.ox) * 0.3; t.oy = t.y - 2 * S; t.cool = 16;
          } else continue;
        }
      }
      // Un telefono veloce che tocca un lottatore gli fa male.
      if (t.stato === "volo" || velocitaTel(t) > 6 * S) {
        for (const f of lottatori) {
          if (f.ko || f.preso || f.esploso || t.cool > 0 || (t.da === f && t.protetto > 0)) continue;
          if (t.ultimo === f && t.cool > 0) continue;
          for (const n of ["testa", "collo", "bacino"]) {
            const b = f.p[n];
            if (Math.hypot(t.x - b.x, t.y - b.y) < b.r + t.r * 0.9) {
              const att = t.da && t.da !== f ? t.da : { dir: Math.sign(t.x - t.ox) || 1, tipo: null, furia: 0 };
              if (t.armato && apri(t)) break;
              // Una bomba accesa che centra qualcuno scoppia subito.
              if (t.tipo === "bomba" && t.miccia > 0) { scoppia(t); break; }
              // Il pieghevole della mela: chi lo prende va in mille pezzi.
              if (t.tipo === "duo" && f !== t.lanciatore) {
                esplodiLottatore(f, att.tipo ? att : null);
                t.morto = true; break;
              }
              const forza = Math.max(3, Math.min(6.5, velocitaTel(t) / (2.2 * S))) * t.peso;
              const suoni = SUONI_OGGETTO[t.tipo] || SUONI_TEL;
              colpisci(att, f, forza, t.x, t.y, suoni[Math.floor(Math.random() * suoni.length)]);
              schegge(t.x, t.y, 6, t.colore);
              t.ox = t.x + (t.x - t.ox) * 0.3; t.oy = t.y - 2 * S; t.va = caso(-0.4, 0.4);
              t.cool = 20; t.ultimo = f; t.crepe = Math.min(5, t.crepe + 1); rompiSchermo(t);
              break;
            }
          }
          if (t.morto) break;
        }
      }
    }
    if (telefoni.some((t) => t.morto)) telefoni = telefoni.filter((t) => !t.morto);
  }

  // --- Pistole: proiettili da cartone -----------------------------------
  function spara(f, altro) {
    if (f && f.p) suona(f.arma && f.arma.tipo === "bazooka" ? "jet" : "sparo", f.p.bacino.x);
    const t = f.arma;
    if (!t || (t.tipo !== "pistola" && t.tipo !== "bazooka")) return;
    f.colpiArma--;
    const fl = Math.cos(t.a) < 0 ? -1 : 1, ca = Math.cos(t.a), sa = Math.sin(t.a);
    if (t.tipo === "bazooka") {
      // Il razzo: parte piano, insegue appena e scoppia su quello che tocca.
      const bocca = { x: t.x + ca * 19 * S, y: t.y + sa * 19 * S };
      const mira = puntoMira(f, altro);
      const d = Math.hypot(mira.x - bocca.x, mira.y - bocca.y) || 1, v = 7 * S;
      proiettili.push({ x: bocca.x, y: bocca.y, vx: (mira.x - bocca.x) / d * v, vy: (mira.y - bocca.y) / d * v,
                        da: f, vita: 170, grande: true, razzo: true, innesca: 7, r: 7 * S, colore: "#ff8a1a", bersaglio: altro });
      // Il contraccolpo e il fumo dietro.
      for (const n in f.p) f.p[n].ox += ca * 3 * S;
      for (let i = 0; i < 7 && particelle.length < MAX_PARTICELLE; i++) {
        particelle.push({ tipo: "fumo", x: t.x - ca * 14 * S + caso(-2, 2) * S, y: t.y - sa * 14 * S + caso(-2, 2) * S,
                          vx: -ca * caso(1, 2.6) * S, vy: -sa * caso(1, 2.6) * S - 0.4 * S,
                          vita: Math.round(caso(26, 44)), max: 44, r: caso(3, 6) * S, colore: Math.random() < 0.5 ? "#6d6a66" : "#8d8a85" });
      }
      scintille(bocca.x, bocca.y, 8, "#ffb62e");
      scossa = Math.max(scossa, 5);
      scrivi("FIUU!", bocca.x, bocca.y - 10 * S, false);
      return;
    }
    const mx = t.x + ca * 12.5 * S + sa * 3.3 * S * fl, my = t.y + sa * 12.5 * S - ca * 3.3 * S * fl;
    const mira = puntoMira(f, altro);
    const bx = mira.x + caso(-7, 7) * S, by = mira.y + caso(-9, 7) * S;
    const d = Math.hypot(bx - mx, by - my) || 1, v = 9.5 * S;
    proiettili.push({ x: mx, y: my, vx: (bx - mx) / d * v, vy: (by - my) / d * v, da: f, vita: 140 });
    scintille(mx, my, 6, "#ffe27a");
    for (let i = 0; i < 3 && particelle.length < 170; i++) {
      particelle.push({ tipo: "fiamma", x: mx, y: my, vx: f.dir * caso(0.5, 1.6) * S, vy: caso(-0.6, 0.6) * S,
                        vita: 8, max: 8, colore: ["#fff1a0", "#ffb62e"][i % 2] });
    }
    scrivi("BANG!", mx, my - 10 * S, false);
  }
  // Il lanciafiamme: una vampata lunga un paio di secondi. Chi ci finisce
  // dentro si becca un colpo solo (ma gli zombie bruciano di continuo), e il
  // pavimento resta annerito.
  function fiammata(f, altro) {
    if (f && f.p && !(f.t % 18)) suona("fiamma", f.p.bacino.x, 0.8);
    const t = f.arma;
    if (!t || t.tipo !== "lanciafiamme") return;
    if (f.t === 6) { f.colpiArma--; scrivi("FWOOSH!", t.x, t.y - 14 * S, false); }
    if (f.t < 6 || f.t > 46) return;
    const ca = Math.cos(t.a), sa = Math.sin(t.a);
    const mx = t.x + ca * 15 * S, my = t.y + sa * 15 * S;
    for (let i = 0; i < 3 && particelle.length < MAX_PARTICELLE; i++) {
      const vel = caso(3.4, 7.2) * S, ang = Math.atan2(sa, ca) + caso(-0.2, 0.2);
      particelle.push({ tipo: "fuoco", x: mx + caso(-2, 2) * S, y: my + caso(-2, 2) * S,
                        vx: Math.cos(ang) * vel, vy: Math.sin(ang) * vel - 0.6 * S,
                        vita: Math.round(caso(18, 30)), max: 30, r: caso(3, 7) * S });
    }
    if (f.t % 5 === 0 && particelle.length < MAX_PARTICELLE) {
      particelle.push({ tipo: "fumo", x: mx + ca * caso(20, 70) * S, y: my + sa * caso(20, 70) * S - 6 * S,
                        vx: ca * 0.6 * S, vy: -caso(0.4, 1) * S, vita: 40, max: 40, r: caso(4, 8) * S, colore: "#6d6a66" });
    }
    const R = 96 * S;
    const dentroIlCono = (x, y) => {
      const dx = x - mx, dy = y - my, dd = Math.hypot(dx, dy) || 1;
      return dd < R && (dx * ca + dy * sa) / dd > 0.74;
    };
    // Il segno nero sul pavimento, davanti a chi spara.
    if ((f.t % 9 === 0 || f.t === 24) && bruciature.length < 40 && Math.abs(sa) < 0.92) {
      const bx = mx + ca * caso(26, 80) * S;
      if (bx > 2 && bx < W - 2) bruciature.push({ x: bx, y: f.base - 1, r: caso(9, 15) * S, t: 0 });
    }
    if (f.t === 18 && altro && altro.p && !altro.esploso && !altro.preso && dentroIlCono(altro.p.bacino.x, altro.p.bacino.y)) {
      colpisci(f, altro, 3.4, altro.p.bacino.x, altro.p.bacino.y, "FWOOSH!");
      scintille(altro.p.bacino.x, altro.p.bacino.y, 10, "#ffb62e");
    }
    if (orda && f.t % 6 === 0) {
      for (const z of orda.zombie) {
        if (!vivoZ(z)) continue;
        const c = corpoZ(z);
        if (dentroIlCono(z.x, c[1])) colpisciZombie(z, 2.2, ca >= 0 ? 1 : -1, z.x, c[1], f);
      }
    }
  }
  // La sfera gigante (lenta, insegue un po', esplode forte) e il disco
  // tagliente (veloce, dritto, taglia). Attraversano la pagina.
  function aggiornaSpeciale(b) {
    b.vita--;
    if (b.grande && b.bersaglio && !b.bersaglio.esploso) {
      const t = b.bersaglio.p.collo, d = Math.hypot(t.x - b.x, t.y - b.y) || 1, v = Math.hypot(b.vx, b.vy);
      const k = b.razzo ? 0.012 : 0.03;                          // il razzo corregge appena la rotta
      b.vx += ((t.x - b.x) / d * v - b.vx) * k; b.vy += ((t.y - b.y) / d * v - b.vy) * k;
    }
    if (b.razzo && passi % 2 === 0 && particelle.length < MAX_PARTICELLE) {
      particelle.push({ tipo: "fumo", x: b.x - b.vx, y: b.y - b.vy, vx: -b.vx * 0.12, vy: -b.vy * 0.12 - 0.3 * S,
                        vita: 30, max: 30, r: caso(2.6, 5) * S, colore: Math.random() < 0.5 ? "#8d8a85" : "#b9b4ab" });
    }
    b.x += b.vx; b.y += b.vy;
    const r = b.grande ? b.r : 5 * S;
    if (b.grande) {
      // Il razzo si innesca appena uscito dal tubo: i primi fotogrammi passa sopra il pavimento e i bordi
      // senza scoppiare (sparando verso il basso, altrimenti, scoppiava addosso a chi lo spara).
      if (b.innesca > 0) b.innesca--;
      let tocca = b.vita <= 0 || (!b.innesca && (b.y + r * 0.7 > pavimento || b.x < r * 0.5 || b.x > W - r * 0.5 || b.y < r * 0.5));
      for (const f of lottatori) {
        if (f === b.da || f.esploso || f.preso) continue;
        for (const n of ["testa", "collo", "bacino"]) if (Math.hypot(f.p[n].x - b.x, f.p[n].y - b.y) < r + f.p[n].r) tocca = true;
      }
      if (tocca) {
        b.vita = 0;
        esplosione(b.x, Math.min(b.y, pavimento - 10 * S), b.razzo ? 1.6 : 1.9, b.da, true);
        scrivi(b.razzo ? "KABOOM!" : "KA-BOOOM!", b.x, Math.max(60, b.y - 50 * S), true);
      } else if (passi % 2 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "scintilla", x: b.x + caso(-1, 1) * r, y: b.y + caso(-1, 1) * r, vx: -b.vx * 0.3, vy: -b.vy * 0.3, vita: 14, max: 14, colore: b.colore });
      }
      return;
    }
    // Il disco.
    if (b.x < 0 || b.x > W) { danneggiaBordo(b.x < 0 ? "sinistra" : "destra", b.y, 0.8); b.vita = 0; return; }
    if (b.y < 0) { danneggiaBordo("tetto", b.x, 0.8); b.vita = 0; return; }
    if (b.y > pavimento - 2) { danneggiaStriscia(b.x, 0.6); scintille(b.x, pavimento - 2, 8, b.colore); b.vita = 0; return; }
    if (b.colpito) return;
    for (const f of lottatori) {
      if (f === b.da || f.ko || f.preso || f.esploso || f.tenuto) continue;
      for (const n of ["testa", "collo", "bacino"]) {
        const q = f.p[n];
        if (Math.hypot(q.x - b.x, q.y - b.y) < q.r + 7 * S) {
          b.colpito = true;
          const barriera = f.azione === "barriera";
          colpisci(b.da, f, 5, b.x, b.y, "ZAC!");
          if (barriera) { b.vita = 0; return; }
          if (!(eMela(f) && taglia(f, b.da))) smembra(f, b.x, b.y);
          return;
        }
      }
    }
  }

  function aggiornaProiettili() {
    const sbuffo = (b) => b.neve ? scintille(b.x, Math.min(b.y, pavimento - 1), 7, "#ffffff") : scintille(Math.max(0, Math.min(W, b.x)), Math.min(b.y, pavimento - 1), 4, "#ffe27a");
    scontriProiettili();
    for (const b of proiettili) {
      if (b.vita <= 0) { if (b.lamaDi) rientraLama(b.lamaDi); continue; }
      if (orda && !b.neve) {
        const z = zombieToccato(b.x, b.y, b.grande ? b.r : 5 * S);
        if (z) {
          colpisciZombie(z, b.grande ? 9 : b.disco ? 6 : b.energia ? 2.6 : 4.4, Math.sign(b.vx) || 1, b.x, b.y, b.da);
          if (!b.grande && !b.disco) { b.vita = 0; continue; }           // sfera gigante e disco passano oltre
        }
      }
      if (b.grande || b.disco) { aggiornaSpeciale(b); if (b.vita <= 0 && b.lamaDi) rientraLama(b.lamaDi); continue; }
      if (b.neve) b.vy += GRAVITA * S * moltG * verso * 0.6;
      b.x += b.vx; b.y += b.vy; b.vita--;
      if (b.y > pavimento - 1 || b.x < 0 || b.x > W || (b.y < 0 && !b.neve)) {
        b.vita = 0; sbuffo(b); continue;
      }
      for (const o of ostacoli) {
        if (b.x > o.l && b.x < o.r && b.y > o.t && b.y < o.b) { b.vita = 0; sbuffo(b); break; }
      }
      if (b.vita <= 0) continue;
      for (const f of lottatori) {
        if (f === b.da || f.ko || f.preso || f.esploso || f.tenuto) continue;
        if (orda && b.da && b.da.tipo) continue;                 // tregua: i colpi dell'alleato passano oltre
        for (const n of ["testa", "collo", "bacino"]) {
          const q = f.p[n];
          if (Math.hypot(q.x - b.x, q.y - b.y) < q.r + 4 * S) {
            // Una lama di energia rimanda indietro pallottole e sfere (non sempre).
            // Il cavaliere para tutto: con la lama doppia nessun colpo passa.
            if (!b.neve && !b.incanto && !b.deviato && lamaPronta(f) && b.vx * f.dir < 0 &&
                (f.azione === "para" || formaDi(f) === "cavaliere" || Math.random() < 0.55)) {
              b.vx = -b.vx; b.vy = caso(-2, 2) * S - b.vy * 0.3; b.da = f; b.deviato = true; b.vita = Math.max(b.vita, 60);
              b.x += b.vx * 2; b.y += b.vy * 2;
              scintille(b.x, b.y, 6, "#ffffff"); scrivi("TING!", b.x, b.y - 10 * S, false);
              break;
            }
            if (b.neve) { colpisci(b.da, f, 2.4, b.x, b.y, "SPLOF!"); sbuffo(b); }
            else if (b.incanto === "gelo") congela(f, b.da, b.x, b.y);
            else if (b.incanto === "piccolo") rimpicciolisci(f, b.da, b.x, b.y);
            else if (b.energia) { colpisci(b.da, f, 2.6, b.x, b.y, "ZAP!"); scintille(b.x, b.y, 6, b.colore); }
            else colpisci(b.da, f, 4.2, b.x, b.y, "BANG!");
            b.vita = 0; break;
          }
        }
        if (b.vita <= 0 || b.da === f) break;
      }
    }
    if (proiettili.length) proiettili = proiettili.filter((b) => b.vita > 0);
  }

  // --- Le armi segrete nel jetpack ---------------------------------------
  // La mela tira fuori il suo pieghevole, il robot una bomba già accesa:
  // tutti e due, se prendono in pieno l'altro, lo fanno a pezzi.
  function estraiDuo(f) {
    const m = f.p.manoA;
    const t = nuovoTelefono(m.x, m.y, 0, 0, f.tipo === "robot" ? "bomba" : "duo");
    t.stato = "portato"; t.da = f; t.apre = 0; t.a = 0;
    if (t.tipo === "bomba") t.miccia = 150;
    f.tel = t;
    scintille(m.x, m.y, 10, f.tipo === "robot" ? "#ffd84a" : "#d9c8ff");
  }

  // --- Un lottatore va in mille pezzi, e si rimonta -----------------------
  // Il robot si smonta in testa, busto, bulloni e arti; la mela in quattro
  // spicchi, picciolo con la foglia, occhi, braccia e gambe. I pezzi volano
  // con la fisica vera (rimbalzano su pagina e striscia), poi tornano a
  // posto uno alla volta, ognuno con un balzo ad arco.
  const ESPLOSO_VOLO = 170, ESPLOSO_PASSO = 9, ESPLOSO_RIMONTA = 28;
  const centroMela = (p) => corpoMela(p);
  function posaPezzo(pz, p) {
    const A = p[pz.a], B = pz.b ? p[pz.b] : null;
    if (pz.forma === "asta") return [(A.x + B.x) / 2, (A.y + B.y) / 2, Math.atan2(B.y - A.y, B.x - A.x), Math.hypot(B.x - A.x, B.y - A.y)];
    if (pz.forma === "spicchio" || pz.forma === "picciolo" || pz.forma === "occhio" || (pz.forma === "bombola" && pz.mela)) {
      // In coordinate del frutto: (u, v) in unità di raggio, ruotate col corpo.
      const c = centroMela(p), R = c.R, ca = Math.cos(c.ang), sa = Math.sin(c.ang);
      let u = pz.u, v = pz.v, ang = c.ang;
      if (pz.forma === "spicchio") { const a = pz.quarto * Math.PI / 2; u = Math.cos(a) * 0.6; v = Math.sin(a) * 0.6; ang += a; }
      return [c.x + (u * ca - v * sa) * R, c.y + (u * sa + v * ca) * R, ang, 0];
    }
    if (pz.forma === "busto" || pz.forma === "bombola") {
      const ang = Math.atan2(B.y - A.y, B.x - A.x) - Math.PI / 2, L = Math.hypot(B.x - A.x, B.y - A.y);
      let x = (A.x + B.x) / 2, y = (A.y + B.y) / 2;
      if (pz.forma === "bombola") { x += Math.cos(ang) * (pz.lato - pz.dir * 10.5) * S; y += Math.sin(ang) * (pz.lato - pz.dir * 10.5) * S; }
      return [x, y, ang, L];
    }
    if (pz.forma === "testa" || pz.forma === "capo") return [A.x, A.y, Math.atan2(A.y - B.y, A.x - B.x) + Math.PI / 2, 0];
    if (pz.forma === "antenna") return [A.x, A.y - 9 * S, 0, 0];
    if (pz.forma === "bullone") return [A.x + pz.off[0] * S, A.y + pz.off[1] * S, 0, 0];
    return [A.x, A.y, 0, 0];
  }
  function pezziDi(f) {
    const asta = (a, b, w, colore) => ({ forma: "asta", a, b, w: w * S, colore });
    if (stile) {
      // Un personaggio inventato va in pezzi come un pupazzo: niente sangue, e si rimonta.
      const A = aspetto(f);
      return [
        { forma: "scarpa", a: "piedeA", colore: A.scarpe }, { forma: "scarpa", a: "piedeD", colore: A.scarpe },
        asta("ginocchioA", "piedeA", 5, A.gambe), asta("ginocchioD", "piedeD", 5, A.gambe),
        asta("bacino", "ginocchioA", 5, A.gambe), asta("bacino", "ginocchioD", 5, A.gambe),
        { forma: "busto", a: "collo", b: "bacino", colore: A.tuta, liscio: true },
        asta("collo", "gomitoD", 4.2, A.maniche), asta("gomitoD", "manoD", 4.2, A.maniche),
        asta("collo", "gomitoA", 4.2, A.maniche), asta("gomitoA", "manoA", 4.2, A.maniche),
        { forma: "pugno", a: "manoD", colore: A.pelle }, { forma: "pugno", a: "manoA", colore: A.pelle },
        { forma: "capo", a: "testa", b: "collo", colore: A.pelle, capelli: A.cappello || A.capelli },
      ];
    }
    if (f.tipo === "mela") {
      const nero = "#111", dietro = -f.dir;
      return [
        { forma: "scarpa", a: "piedeA", colore: "#f7f7f7" }, { forma: "scarpa", a: "piedeD", colore: "#f7f7f7" },
        asta("ginocchioA", "piedeA", 3, nero), asta("ginocchioD", "piedeD", 3, nero),
        asta("bacino", "ginocchioA", 3, nero), asta("bacino", "ginocchioD", 3, nero),
        { forma: "spicchio", quarto: 0, colore: "#ffffff" }, { forma: "spicchio", quarto: 1, colore: "#ffffff" },
        { forma: "spicchio", quarto: 2, colore: "#ffffff" }, { forma: "spicchio", quarto: 3, colore: "#ffffff" },
        { forma: "bombola", mela: true, u: dietro * 1.15 - 0.19, v: 0.1, colore: "#7d8696" },
        { forma: "bombola", mela: true, u: dietro * 1.15 + 0.19, v: 0.1, colore: "#b3bbc9" },
        asta("collo", "gomitoD", 3, nero), asta("gomitoD", "manoD", 3, nero),
        asta("collo", "gomitoA", 3, nero), asta("gomitoA", "manoA", 3, nero),
        { forma: "guanto", a: "manoD", colore: "#1f56b8" }, { forma: "guanto", a: "manoA", colore: "#2f72e0" },
        { forma: "occhio", u: -0.34 + f.dir * 0.08, v: -0.16, colore: nero }, { forma: "occhio", u: 0.34 + f.dir * 0.08, v: -0.16, colore: nero },
        { forma: "picciolo", u: 0.06, v: -0.95, colore: "#6b4423" },
      ];
    }
    const T = tavolozza || ["#2fae74", "#1c6f4a", "#7dffd2", "#154d34"];
    return [
      { forma: "piede", a: "piedeA", colore: T[3] }, { forma: "piede", a: "piedeD", colore: T[3] },
      asta("ginocchioA", "piedeA", 5, T[0]), asta("ginocchioD", "piedeD", 5, T[1]),
      asta("bacino", "ginocchioA", 5, T[0]), asta("bacino", "ginocchioD", 5, T[1]),
      { forma: "busto", a: "collo", b: "bacino", colore: T[0] },
      { forma: "bombola", a: "collo", b: "bacino", colore: "#7d8696", lato: -2.6, dir: f.dir },
      { forma: "bombola", a: "collo", b: "bacino", colore: "#b3bbc9", lato: 2.6, dir: f.dir },
      asta("collo", "gomitoD", 4.4, T[1]), asta("gomitoD", "manoD", 4.4, T[1]),
      asta("collo", "gomitoA", 4.4, T[0]), asta("gomitoA", "manoA", 4.4, T[0]),
      { forma: "guanto", a: "manoD", colore: "#b92b22" }, { forma: "guanto", a: "manoA", colore: "#e03a2f" },
      { forma: "testa", a: "testa", b: "collo", colore: T[0] }, { forma: "antenna", a: "testa", colore: T[1] },
      { forma: "bullone", a: "collo", off: [3, 2], colore: "#9aa1ad" }, { forma: "bullone", a: "bacino", off: [-3, -2], colore: "#9aa1ad" },
      { forma: "bullone", a: "ginocchioA", off: [0, 0], colore: "#9aa1ad" },
    ];
  }
  function esplodiLottatore(f, att, senzaPunto) {
    if (f.esploso || !f.p || f.fuoriCampo) return;
    // Nella corsa l'eroe non va in pezzi: prende una gran botta e basta.
    if (corsa && corsa.chi && f.tipo === corsa.chi) {
      const b = f.p.bacino;
      feritaEroe(34, b.x, b.y);
      f.ko = Math.max(f.ko, 70); f.inVolo = true;
      return;
    }
    if (f.tel) lasciaCadere(f);
    if (f.arma) lasciaArma(f);
    if (f.tiene) molla(f);
    if (f.tenuto && f.tenuto.da) molla(f.tenuto.da);
    if (presa.f === f) { presa.f = null; radiceHtml("remove", "ring-trascina"); }
    f.preso = null; f.jet = 0; f.caos = 0; f.paracadute = 0; f.para = 0; f.azione = null; f.scalata = null;
    const p = f.p;
    const c = eMela(f) ? centroMela(p) : { x: (p.collo.x + p.bacino.x) / 2, y: (p.collo.y + p.bacino.y) / 2 };
    pezzi = pezzi.filter((pz) => pz.f !== f).concat(pezziDi(f).map((pz, i) => {
      const [x, y, ang, L] = posaPezzo(pz, p);
      const dx = x - c.x, dy = y - c.y, d = Math.hypot(dx, dy) || 1, v = caso(4, 10) * S;
      const vx = dx / d * v + caso(-2, 2) * S, vy = dy / d * v - caso(3, 7) * S;
      return Object.assign(pz, { f, x, y, ox: x - vx, oy: y - vy, ang, L, va: caso(-0.35, 0.35), ordine: i,
                                 casa: null, da: null, fatto: false });
    }));
    f.esploso = { t: 0, dir: f.dir, nuovo: null, x: c.x, base: pavimento };
    f.ko = 1e6; f.inVolo = false; f.dolore = 0; f.stordito = 0; f.segni = []; f.staccati = {}; f.morsi = []; f.taglio = null;
    arti = arti.filter((a) => a.f !== f);
    esplosione(c.x, c.y, 1.4, att);
    scossa = 18; fermoColpo = 10;
    schegge(c.x, c.y, 12, stile ? aspetto(f).tuta : f.tipo === "mela" ? "#ffffff" : (tavolozza || ["#2fae74"])[0]);
    if (eMela(f)) schizza(f, c.x, c.y, 10, 3);
    scrivi("KABOOM!", c.x, c.y - 40 * S, true);
    f.cratere = null; f.accecato = 0; f.sfera = null;
    // Il corpo non c'è più finché non si rimonta: i suoi punti restano fermi, dentro la finestra
    // (lo scoppio li spingeva sotto il pavimento, e lì restavano fino al rimontaggio).
    for (const n in f.p) {
      const pt = f.p[n];
      pt.x = pt.ox = Math.max(pt.r + 2, Math.min(W - pt.r - 2, pt.x)); pt.y = pt.oy = Math.max(pt.r, Math.min(pavimento - pt.r, pt.y));
    }
    if (senzaPunto) { salvaCervello(true); return; }
    const vincitore = att && att.tipo && att !== f ? att.tipo : altroTipo(f.tipo);
    risolviScommessa(vincitore);
    punteggio[vincitore]++;
    controllaFinale(vincitore, null, null);
    const chi = lottatori.find((l) => l.tipo === vincitore);
    if (chi && chi !== f && !chi.esploso) chi.daBallare = true;
    salvaCervello(true);
  }
  function rimbalzaPezzo(pz) {
    let vx = (pz.x - pz.ox) * 0.99, vy = (pz.y - pz.oy) * 0.99;
    pz.ox = pz.x; pz.oy = pz.y;
    pz.x += vx; pz.y += vy + GRAVITA * S * moltG * verso; pz.ang += pz.va;
    const r = 3.5 * S;
    if (pz.y > pavimento - r) { pz.y = pavimento - r; pz.oy = pz.y + Math.max(0, vy) * 0.4; pz.ox = pz.x - vx * 0.7; pz.va *= 0.7; }
    for (const o of ostacoli) {
      if (pz.x > o.l && pz.x < o.r && pz.y > o.t - r && pz.y < o.b && pz.oy <= o.t - r + 1) {
        pz.y = o.t - r; pz.oy = pz.y + Math.max(0, vy) * 0.4; pz.ox = pz.x - vx * 0.7; pz.va *= 0.7;
      }
    }
    if (pz.x < r) { pz.x = r; pz.ox = pz.x + Math.abs(vx) * 0.5; }
    if (pz.x > W - r) { pz.x = W - r; pz.ox = pz.x - Math.abs(vx) * 0.5; }
    if (pz.y < r) { pz.y = r; pz.oy = pz.y - Math.max(0, -vy) * 0.4; pz.ox = pz.x - vx * 0.7; }
  }
  function aggiornaEsplosione(f) {
    const e = f.esploso, miei = pezzi.filter((pz) => pz.f === f);
    e.t++;
    if (e.rientro) { if (e.t >= RIENTRO) rientra(f); return; }
    if (e.t === ESPLOSO_VOLO) {
      // Si rimonta dove è finito il pezzo più grosso, sul primo appoggio sotto.
      const centro = miei.find((pz) => pz.forma === "busto" || pz.forma === "spicchio") || miei[0];
      const x = Math.max(30 * S, Math.min(W - 30 * S, centro ? centro.x : W / 2));
      let base = pavimento;
      for (const o of ostacoli) if (x >= o.l && x <= o.r && o.t >= (centro ? centro.y : 0) - 4 * S && o.t < base) base = o.t;
      e.nuovo = crea(f.tipo, x, e.dir, base); e.x = x; e.base = base;
      for (const pz of miei) pz.casa = posaPezzo(pz, e.nuovo.p);
    }
    for (const pz of miei) {
      const inizio = ESPLOSO_VOLO + pz.ordine * ESPLOSO_PASSO;
      if (!pz.casa || e.t < inizio) { rimbalzaPezzo(pz); continue; }
      if (!pz.da) pz.da = [pz.x, pz.y, pz.ang, pz.L];
      const k = Math.min(1, (e.t - inizio) / ESPLOSO_RIMONTA), q = k * k * (3 - 2 * k);
      const arco = Math.sin(Math.PI * k) * 36 * S;
      let da = pz.casa[2] - pz.da[2];
      da = ((da + Math.PI) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) - Math.PI;
      pz.x = pz.da[0] + (pz.casa[0] - pz.da[0]) * q;
      pz.y = pz.da[1] + (pz.casa[1] - pz.da[1]) * q - arco;
      pz.ang = pz.da[2] + da * q; pz.L = pz.da[3] + (pz.casa[3] - pz.da[3]) * q;
      pz.ox = pz.x; pz.oy = pz.y;
      if (k >= 1 && !pz.fatto) { pz.fatto = true; scintille(pz.x, pz.y, 4, eRobot(f) ? "#7dffd2" : "#ffffff"); }
    }
    if (e.t >= ESPLOSO_VOLO + miei.length * ESPLOSO_PASSO + ESPLOSO_RIMONTA + 8) {
      const n = e.nuovo || crea(f.tipo, e.x, e.dir, e.base);
      f.p = n.p; f.aste = n.aste; f.cx = e.x; f.base = e.base; f.dir = e.dir;
      f.esploso = null; f.ko = 0; f.rialzo = 0; f.stordito = 30; f.danni = 0; f.koVero = false;
      f.inVolo = false; f.fantasma = false; f.azione = null; f.pensa = 20;
      pezzi = pezzi.filter((pz) => pz.f !== f);
      scintille(f.p.collo.x, f.p.collo.y, 14, eRobot(f) ? "#7dffd2" : "#ffffff");
    }
  }

  // --- La partita finisce a dieci (02/10/2026, su richiesta) -------------
  // Chi arriva a dieci K.O. chiude la partita col colpo che manda l'altro
  // FUORI DAL RING: l'azione si ferma un attimo sul colpo, il corpo parte
  // dritto verso il bordo della finestra, e dove esce si apre un ventaglio
  // di luce. Poi il conto riparte da zero e lo sconfitto rientra dall'alto.
  const TRAGUARDO = 10, RIENTRO = 150;
  const CORIANDOLI = ["#ff5a5f", "#ffcf3a", "#3ddc97", "#4aa8ff", "#c77dff", "#ffffff"];
  function controllaFinale(tipo, perdente, att) {
    if (finale || !tipo || punteggio[tipo] < TRAGUARDO) return;
    const chi = lottatori.find((l) => l.tipo === tipo);
    finale = { tipo, t: 0, q: 0, punti: punteggio.robot + "–" + punteggio.mela, perso: null, lampo: null,
               nome: stile ? ASPETTI[stile][tipo].nome : dici(tipo === "robot" ? "ROBOT" : "MELA"),
               colore: COLORI_ANIME[tipo] };
    if (chi && !chi.esploso) chi.daBallare = true;
    if (!perdente || !perdente.p || perdente.esploso || perdente.preso) return;
    if (perdente.tenuto && perdente.tenuto.da) molla(perdente.tenuto.da);
    if (perdente.tel) lasciaCadere(perdente);
    if (perdente.arma) lasciaArma(perdente);
    if (perdente.tiene) molla(perdente);
    const p = perdente.p, dir = (att && att.dir) || (chi && p.bacino.x < chi.p.bacino.x ? -1 : 1);
    perdente.tenuto = null; perdente.fuori = 1; perdente.ko = 1e6; perdente.inVolo = true; perdente.fantasma = true;
    perdente.jet = 0; perdente.caos = 0; perdente.paracadute = 0; perdente.para = 0; perdente.azione = null;
    perdente.scalata = null; perdente.cratere = null;
    for (const n in p) {
      const giro = n === "testa" || n === "collo" ? 2 : n.startsWith("piede") ? -2 : 0;      // parte ruotando un po'
      p[n].ox = p[n].x - dir * (25 + giro) * S; p[n].oy = p[n].y + verso * 13 * S;
    }
    finale.perso = perdente; finale.x = p.collo.x; finale.y = p.collo.y;
    fermoColpo = 24; scossa = 18;
  }
  function volaFuori(f) {
    const p = f.p;
    let esce = ++f.fuori > 80;
    for (const n in p) {
      const pt = p[n], vx = pt.x - pt.ox, vy = pt.y - pt.oy;
      pt.ox = pt.x; pt.oy = pt.y; pt.x += vx; pt.y += vy;
    }
    for (let giro = 0; giro < 3; giro++) {
      for (const [p1, p2, L] of f.aste) {
        const dx = p2.x - p1.x, dy = p2.y - p1.y, d = Math.hypot(dx, dy) || 0.001, c = (d - L) / d * 0.5;
        p1.x += dx * c; p1.y += dy * c; p2.x -= dx * c; p2.y -= dy * c;
      }
    }
    if (particelle.length < MAX_PARTICELLE) {
      particelle.push({ tipo: "fumo", x: p.bacino.x, y: p.bacino.y, vx: 0, vy: 0, vita: 20, max: 20, r: 6 * S, colore: "#ffffff" });
    }
    for (const n of ["testa", "bacino"]) {
      const pt = p[n];
      if (pt.x < 10 * S || pt.x > W - 10 * S || pt.y < 10 * S || (verso < 0 && pt.y > pavimento - 6 * S)) esce = true;
    }
    if (esce) esceDalRing(f);
  }
  function esceDalRing(f) {
    const b = f.p.bacino, vx = b.x - b.ox, vy = b.y - b.oy, v = Math.hypot(vx, vy) || 1;
    const x = Math.max(0, Math.min(W, b.x + vx * 1.5)), y = Math.max(0, Math.min(pavimento, b.y + vy * 1.5));
    if (finale) finale.lampo = { x, y, ux: -vx / v, uy: -vy / v, t: 0 };
    scossa = 26; fermoColpo = Math.max(fermoColpo, 4);
    const a0 = Math.atan2(-vy, -vx);
    for (let i = 0; i < 44 && particelle.length < MAX_PARTICELLE; i++) {
      const a = a0 + caso(-1, 1), vel = caso(3, 12) * S;
      particelle.push({ tipo: "detrito", x, y, vx: Math.cos(a) * vel, vy: Math.sin(a) * vel - 2 * S, vita: 130, max: 130, rot: 0,
                        va: caso(-0.4, 0.4), lato: caso(2.2, 4.6) * S, colore: CORIANDOLI[i % CORIANDOLI.length] });
    }
    if (x <= 1) danneggiaBordo("sinistra", y, 1); else if (x >= W - 1) danneggiaBordo("destra", y, 1); else if (y <= 1) danneggiaBordo("tetto", x, 1);
    // Sparisce (come chi va in pezzi) e rientra fra poco dal suo lato.
    for (const n in f.p) {
      const pt = f.p[n];
      pt.x = pt.ox = Math.max(8, Math.min(W - 8, pt.x)); pt.y = pt.oy = Math.max(8, Math.min(pavimento - 8, pt.y));
    }
    arti = arti.filter((a) => a.f !== f);
    f.esploso = { t: 0, dir: f.tipo === "robot" ? 1 : -1, nuovo: null, x: W * (f.tipo === "robot" ? 0.3 : 0.7), base: pavimento, rientro: true };
    f.fuori = 0; f.inVolo = false; f.fantasma = false; f.dolore = 0; f.stordito = 0; f.segni = []; f.staccati = {}; f.morsi = [];
    f.taglio = null; f.accecato = 0; f.sfera = null; f.cratere = null;
  }
  function rientra(f) {
    const e = f.esploso, n = crea(f.tipo, e.x, e.dir, pavimento);
    if (verso > 0) {
      const su = n.p.testa.y - 26 * S;
      for (const k in n.p) { n.p[k].y -= su; n.p[k].oy = n.p[k].y - 3 * S; }
    }
    f.p = n.p; f.aste = n.aste; f.cx = e.x; f.base = pavimento; f.dir = e.dir;
    f.esploso = null; f.ko = 40; f.rialzo = 0; f.stordito = 0; f.danni = 0; f.koVero = false;
    f.inVolo = verso > 0; f.fantasma = false; f.azione = null; f.pensa = 20;
    if (lame() && f.lama) accendiLama(f);
    scintille(f.p.collo.x, f.p.collo.y, 14, COLORI_ANIME[f.tipo]);
  }
  function aggiornaFinale() {
    if (!finale) return;
    finale.t++;
    if (finale.lampo) finale.lampo.t++;
    const p = finale.perso;
    if (p ? (!p.esploso && !p.fuori) || finale.t > 420 : finale.t > 210) {
      punteggio.robot = 0; punteggio.mela = 0; finale = null;
      scrivi("NUOVA PARTITA!", W / 2, H * 0.32, true);
    }
  }
  function disegnaFinale(sopra) {
    if (!finale) return;
    if (!sopra) {
      // Il colpo decisivo: per un attimo tutto il resto si spegne.
      if (finale.perso && finale.t < 2) {
        const k = Math.min(1, ++finale.q / 5);
        ctx.save(); ctx.fillStyle = "rgba(12,10,24," + 0.62 * k + ")"; ctx.fillRect(0, 0, W, H);
        ctx.translate(finale.x, finale.y); ctx.lineCap = "round";
        for (let i = 0; i < 28; i++) {
          const a = i * 2.399, r0 = (22 + (i * 37 % 23)) * S, r1 = r0 + (50 + (i * 53 % 170)) * S * k;
          ctx.strokeStyle = i % 3 ? "rgba(255,255,255,.8)" : finale.colore; ctx.lineWidth = (1 + i % 3) * S;
          ctx.beginPath(); ctx.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); ctx.lineTo(Math.cos(a) * r1, Math.sin(a) * r1); ctx.stroke();
        }
        ctx.restore();
      }
      return;
    }
    const z = finale.lampo;
    if (z && z.t < 64) {
      // Il ventaglio di luce dal punto in cui è uscito.
      const k = z.t / 64, L = Math.hypot(W, H) * 0.8 * Math.min(1, (z.t + 1) / 7), a0 = Math.atan2(z.uy, z.ux);
      ctx.save(); ctx.translate(z.x, z.y); ctx.globalAlpha = Math.max(0, 1 - k * k);
      for (let i = 0; i < 9; i++) {
        const a = a0 + (i - 4) * 0.21 + Math.sin(i * 7.3) * 0.05, lun = L * (0.5 + 0.5 * Math.abs(Math.sin(i * 2.7 + 1)));
        const larg = (0.05 + 0.03 * (i % 3)) * (1 - 0.6 * k);
        ctx.fillStyle = i % 2 ? CORIANDOLI[(i >> 1) % 5] : finale.colore;
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a - larg) * lun, Math.sin(a - larg) * lun);
        ctx.lineTo(Math.cos(a) * lun * 1.14, Math.sin(a) * lun * 1.14); ctx.lineTo(Math.cos(a + larg) * lun, Math.sin(a + larg) * lun);
        ctx.closePath(); ctx.fill();
      }
      const R = 110 * S * (1 - 0.5 * k), g = ctx.createRadialGradient(0, 0, 0, 0, 0, R);
      g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.5, "rgba(255,255,255,.55)"); g.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    // Il cartello: chi ha vinto e com'è finita.
    const tb = finale.t - (finale.perso ? 14 : 6);
    if (tb > 0) {
      const sc = 1 + 0.5 * Math.max(0, 1 - tb / 12), riga = Math.round(Math.min(30 * S, W / 13));
      ctx.save(); ctx.translate(W / 2, Math.max(70 * S, H * 0.3)); ctx.scale(sc, sc); ctx.globalAlpha = Math.min(1, tb / 6);
      ctx.textAlign = "center"; ctx.lineJoin = "round"; ctx.strokeStyle = "#141414";
      ctx.font = "800 " + riga + "px Archivo, sans-serif"; ctx.lineWidth = riga * 0.22; ctx.fillStyle = finale.colore;
      const t1 = finale.nome + " " + dici("VINCE!");
      ctx.strokeText(t1, 0, 0); ctx.fillText(t1, 0, 0);
      ctx.font = "800 " + Math.round(riga * 0.52) + "px Archivo, sans-serif"; ctx.lineWidth = riga * 0.14; ctx.fillStyle = "#ffcf3a";
      const t2 = finale.punti + (finale.perso ? "  ·  " + dici("FUORI DAL RING!") : "");
      ctx.strokeText(t2, 0, riga * 0.85); ctx.fillText(t2, 0, riga * 0.85);
      ctx.restore();
    }
  }

  // --- Fumogeni e barattoli (02/10/2026, su richiesta) -------------------
  // Il fumogeno lanciato apre una nube: chi ci finisce dentro non vede più
  // niente (tranne chi l'ha lanciato). Il barattolo lanciato si rompe e
  // libera una creatura, che per qualche secondo combatte per chi l'ha
  // lanciato: TIZZO soffia fuoco, ZIP chiama un fulmine, BOLLA spara un
  // getto d'acqua che spinge lontano. Personaggi inventati per questo ring.
  function apri(t) {
    if (t.morto) return false;
    const per = t.lanciatore && t.lanciatore.tipo ? t.lanciatore.tipo : null;
    if (t.tipo === "fumogeno") {
      nubi.push({ x: t.x, y: Math.min(t.y, pavimento - 26 * S), t: 0, per });
      scrivi("PUFF!", t.x, t.y - 16 * S, false);
    } else if (t.tipo === "barattolo") {
      if (creature.length >= 3) return false;
      schegge(t.x, t.y, 8, "#cfe9ff");
      nuovaCreatura(t.el, t.x, t.y, per);
    } else return false;
    t.morto = true; t.armato = false;
    return true;
  }
  function aggiornaNubi() {
    for (const n of nubi) {
      n.t++;
      if (n.t < 250 && passi % 2 === 0 && particelle.length < MAX_PARTICELLE - 40) {
        particelle.push({ tipo: "fumo", x: n.x + caso(-42, 42) * S, y: n.y + caso(-26, 22) * S, vx: caso(-0.5, 0.5) * S, vy: -caso(0.1, 0.5) * S,
                          vita: 80, max: 80, r: caso(9, 15) * S, colore: passi % 4 < 2 ? "#bdb8cc" : "#dedbe8" });
      }
      if (n.t > 260) continue;
      for (const f of lottatori) {
        if (f.tipo === n.per || f.esploso || f.fuori || f.ko > 0 || f.preso || f.tenuto) continue;
        if (Math.hypot(f.p.testa.x - n.x, f.p.testa.y - n.y) < 64 * S) {
          if (!(f.accecato > 0)) scrivi("COFF!", f.p.testa.x, f.p.testa.y - 18 * S, false);
          f.accecato = Math.max(f.accecato, 24);
        }
      }
    }
    if (nubi.length) nubi = nubi.filter((n) => n.t < 300);
  }
  function nuovaCreatura(el, x, y, per) {
    if (!ELEMENTI[el]) el = "fuoco";
    const c = { el, x: Math.max(16 * S, Math.min(W - 16 * S, x)), y: Math.min(y, pavimento - 12 * S), vy: -5 * S, per: per || null,
                t: 0, vita: 600, dir: 1, attesa: 45, colpo: 0, creatura: true };
    creature.push(c);
    scrivi(ELEMENTI[el].nome + "!", c.x, c.y - 26 * S, true);
    scintille(c.x, c.y, 12, ELEMENTI[el].colore);
    return c;
  }
  function bersaglioDi(c) {
    let scelto = null, d0 = 1e9;
    for (const f of lottatori) {
      if (f.esploso || f.fuori || f.tipo === c.per) continue;
      const d = Math.abs(f.p.bacino.x - c.x);
      if (d < d0) { d0 = d; scelto = f; }
    }
    return scelto;
  }
  function aggiornaCreature() {
    if (!creature.length) return;
    for (const c of creature) {
      c.t++;
      const vola = c.el === "fuoco", f = bersaglioDi(c), g = GRAVITA * S * Math.max(0.3, moltG);
      if (vola) {
        // TIZZO galleggia all'altezza di chi insegue.
        const quota = (f ? Math.min(pavimento, f.base) : pavimento) - 42 * S;
        c.y += (quota + Math.sin(c.t * 0.09) * 5 * S - c.y) * 0.08; c.aTerra = true;
      } else {
        // Le altre camminano: sul pavimento o sul primo elemento della pagina sotto i piedi.
        const prima = c.y;
        c.vy += g; c.y += c.vy;
        let suolo = pavimento;
        for (const o of ostacoli) if (c.x >= o.l && c.x <= o.r && o.t >= prima + 16 * S - 2 && o.t < suolo) suolo = o.t;
        c.aTerra = c.vy >= 0 && c.y >= suolo - 16 * S;
        if (c.aTerra) { c.y = suolo - 16 * S; c.vy = 0; }
        // L'avversario sta più in alto: un salto fin lassù.
        if (c.aTerra && f && f.base < suolo - 20 * S && Math.abs(f.p.bacino.x - c.x) < 130 * S && c.t % 30 === 0) {
          c.vy = -Math.sqrt(2 * g * (suolo - f.base + 18 * S));
        }
      }
      if (c.t > c.vita) continue;
      if (c.colpo) { c.colpo++; attaccoCreatura(c, f); }
      else if (f) {
        const dx = f.p.bacino.x - c.x, d = Math.abs(dx), lontano = (c.el === "scossa" ? 150 : c.el === "acqua" ? 120 : 90) * S;
        c.dir = dx >= 0 ? 1 : -1;
        if (d > lontano) {
          c.x += c.dir * (c.el === "acqua" ? 1.4 : 2) * S;
          if (!vola && c.aTerra && c.vy === 0 && c.t % (c.el === "scossa" ? 14 : 22) === 0) c.vy = -(c.el === "scossa" ? 3.4 : 2.2) * S;
        } else if (d < 46 * S) c.x -= c.dir * 1.2 * S;
        if (c.attesa > 0) c.attesa--;
        else if (d <= lontano + 24 * S && !(f.ko > 0)) c.colpo = 1;
      }
      c.x = Math.max(14 * S, Math.min(W - 14 * S, c.x));
      if (vola && passi % 5 === 0 && particelle.length < MAX_PARTICELLE - 60) {
        particelle.push({ tipo: "scintilla", x: c.x + caso(-5, 5) * S, y: c.y - 8 * S, vx: caso(-0.4, 0.4) * S, vy: -caso(0.8, 1.8) * S, vita: 12, max: 12, colore: "#ffb62e" });
      }
    }
    const via = creature.filter((c) => c.t > c.vita + 14);
    for (const c of via) polvere(c.x, c.y, 6);
    if (via.length) creature = creature.filter((c) => c.t <= c.vita + 14);
  }
  function attaccoCreatura(c, f) {
    const att = { dir: c.dir, tipo: c.per, furia: 0, azione: null, creatura: true };
    const davanti = f && (f.p.collo.x - c.x) * c.dir > -10 * S;
    const metti = (q) => { if (particelle.length < MAX_PARTICELLE - 20) particelle.push(q); };
    if (c.el === "fuoco") {
      if (c.colpo >= 8 && c.colpo <= 30) {
        for (let i = 0; i < 2; i++) {
          metti({ tipo: "fuoco", x: c.x + c.dir * 9 * S, y: c.y - 2 * S, vx: c.dir * caso(3.5, 7) * S, vy: caso(-1.3, 0.6) * S,
                  vita: 20, max: 20, r: caso(2.6, 4.6) * S });
        }
      }
      if (c.colpo === 8) scrivi("FWOOSH!", c.x + c.dir * 30 * S, c.y - 16 * S, false);
      if (c.colpo === 17 && davanti && Math.abs(f.p.collo.x - c.x) < 125 * S && Math.abs(f.p.bacino.y - c.y) < 70 * S && !(f.ko > 0)) {
        colpisci(att, f, 3.6, f.p.collo.x, (f.p.collo.y + f.p.bacino.y) / 2, "AHI!");
      }
      if (c.colpo >= 40) { c.colpo = 0; c.attesa = 100; }
    } else if (c.el === "scossa") {
      if (c.colpo < 16 && c.colpo % 3 === 0) scintille(c.x + caso(-9, 9) * S, c.y + caso(-9, 5) * S, 2, "#fff3b0");
      if (c.colpo === 16 && f && !(f.ko > 0)) fulmini.push({ x: f.p.collo.x, t: 0, da: att, contro: f, forza: 4.2, punti: null });
      if (c.colpo >= 36) { c.colpo = 0; c.attesa = 130; }
    } else {
      if (c.colpo >= 6 && c.colpo <= 30) {
        for (let i = 0; i < 2; i++) {
          metti({ tipo: "goccia", x: c.x + c.dir * 8 * S, y: c.y - 5 * S, vx: c.dir * caso(5, 8.5) * S, vy: -caso(1.2, 3) * S,
                  vita: 50, max: 50, r: caso(1.6, 3) * S, colore: i ? "#8fd0ff" : "#3aa0ff" });
        }
      }
      if (c.colpo === 6) scrivi("SPLASH!", c.x + c.dir * 30 * S, c.y - 18 * S, false);
      if (c.colpo === 16 && davanti && Math.abs(f.p.collo.x - c.x) < 150 * S && Math.abs(f.p.bacino.y - c.y) < 80 * S && !(f.ko > 0)) {
        colpisci(att, f, 2.6, f.p.bacino.x, f.p.bacino.y - 6 * S, "SPLASH!");
        // Il getto spinge lontano più di quanto faccia male.
        for (const n in f.p) { f.p[n].ox -= c.dir * 9 * S; f.p[n].oy += 2.5 * S * verso; }
      }
      if (c.colpo >= 42) { c.colpo = 0; c.attesa = 110; }
    }
  }
  function occhiCreatura(x, y, d, r, arrabbiato) {
    for (const lato of [-1, 1]) {
      const ox = x + lato * r * 1.25;
      ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "#111"; ctx.lineWidth = 0.8 * S;
      ctx.beginPath(); ctx.ellipse(ox, y, r, r * 1.2, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      tondo(ox + d * r * 0.35, y + r * 0.15, r * 0.5, "#111");
      if (arrabbiato) {
        ctx.lineWidth = 1.1 * S; ctx.beginPath();
        ctx.moveTo(ox - lato * r * 1.1, y - r * 1.9); ctx.lineTo(ox + lato * r * 0.9, y - r * 1.2); ctx.stroke();
      }
    }
  }
  function disegnaCreatura(c) {
    const E = ELEMENTI[c.el], nasce = Math.min(1, c.t / 10), fine = c.t > c.vita ? Math.max(0, 1 - (c.t - c.vita) / 14) : 1;
    if (c.t > c.vita - 90 && c.t < c.vita && c.t % 10 < 3) return;      // lampeggia: sta per andarsene
    const d = c.dir, att = c.colpo > 0;
    ctx.save(); ctx.translate(c.x, c.y); ctx.scale(1.35 * nasce * fine, 1.35 * nasce * fine);
    ctx.lineJoin = "round"; ctx.lineCap = "round";
    // Di chi è: una bandierina col colore di chi l'ha liberata.
    if (c.per) {
      ctx.fillStyle = COLORI_ANIME[c.per]; ctx.strokeStyle = "#111"; ctx.lineWidth = 0.8 * S;
      ctx.beginPath(); ctx.moveTo(0, -27 * S); ctx.lineTo(4 * S, -23.5 * S); ctx.lineTo(0, -20 * S); ctx.lineTo(-4 * S, -23.5 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    if (c.el === "fuoco") {
      // TIZZO: una fiammella che galleggia, con due braccini di brace.
      const tr = Math.sin(c.t * 0.45) * 2 * S, g = ctx.createRadialGradient(0, 3 * S, 1 * S, 0, 0, 15 * S);
      g.addColorStop(0, "#fff6c2"); g.addColorStop(0.45, "#ffb62e"); g.addColorStop(1, "#f2501d");
      ctx.fillStyle = g; ctx.strokeStyle = "#111"; ctx.lineWidth = 1.2 * S;
      ctx.beginPath(); ctx.moveTo(tr - d * 2 * S, -18 * S);
      ctx.bezierCurveTo(7 * S, -10 * S, 12 * S, -3 * S, 10 * S, 4 * S);
      ctx.bezierCurveTo(8 * S, 11 * S, -8 * S, 11 * S, -10 * S, 4 * S);
      ctx.bezierCurveTo(-12 * S, -3 * S, -5 * S, -8 * S, tr - d * 2 * S, -18 * S);
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = "rgba(255,246,194,.85)"; ctx.beginPath(); ctx.ellipse(0, 4 * S, 5 * S, 4.5 * S, 0, 0, Math.PI * 2); ctx.fill();
      for (const lato of [-1, 1]) {
        const su = att && lato === d ? -4 * S : Math.sin(c.t * 0.3 + lato) * 1.5 * S;
        ctx.fillStyle = "#ff8a1a"; ctx.beginPath(); ctx.ellipse(lato * 12.5 * S, 3 * S + su, 3.2 * S, 2.4 * S, lato * 0.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
      occhiCreatura(d * 1.6 * S, -1 * S, d, 2 * S, true);
      if (att) { ctx.fillStyle = "#7a1a0c"; ctx.beginPath(); ctx.ellipse(d * 2.4 * S, 5 * S, 2.6 * S, 2.2 * S, 0, 0, Math.PI * 2); ctx.fill(); }
    } else if (c.el === "scossa") {
      // ZIP: una scintilla a punte, due zampette a saetta e un'antenna.
      const n = 9, giro = c.t * (att ? 0.25 : 0.04);
      ctx.strokeStyle = "#111"; ctx.lineWidth = 1.3 * S;
      for (const lato of [-1, 1]) {
        ctx.beginPath(); ctx.moveTo(lato * 3.5 * S, 6 * S); ctx.lineTo(lato * 6 * S, 8.5 * S); ctx.lineTo(lato * 3 * S, 9.5 * S); ctx.lineTo(lato * 5.5 * S, 12 * S); ctx.stroke();
      }
      ctx.beginPath(); ctx.moveTo(0, -9 * S); ctx.lineTo(2 * S, -13 * S); ctx.lineTo(-1.5 * S, -14.5 * S); ctx.lineTo(1 * S, -18 * S); ctx.stroke();
      tondo(1 * S, -18.5 * S, 1.5 * S, "#fff3b0");
      ctx.fillStyle = att && c.t % 4 < 2 ? "#fff8c9" : "#ffd400"; ctx.lineWidth = 1.2 * S; ctx.beginPath();
      for (let i = 0; i < n * 2; i++) {
        const a = giro + i * Math.PI / n, r = (i % 2 ? 7.2 : 11.2 + (att ? Math.sin(c.t + i) * 1.6 : 0)) * S;
        ctx[i ? "lineTo" : "moveTo"](Math.cos(a) * r, Math.sin(a) * r);
      }
      ctx.closePath(); ctx.fill(); ctx.stroke();
      occhiCreatura(d * 1.4 * S, -1 * S, d, 1.9 * S, att);
      ctx.strokeStyle = "#111"; ctx.lineWidth = 0.9 * S; ctx.beginPath(); ctx.arc(d * 1.4 * S, 2.6 * S, 2 * S, 0.15 * Math.PI, 0.85 * Math.PI); ctx.stroke();
    } else {
      // BOLLA: una goccia che ondeggia, col ciuffo d'onda e due pinnette.
      const sq = 1 + Math.sin(c.t * 0.22) * 0.06, g = ctx.createLinearGradient(0, -14 * S, 0, 10 * S);
      g.addColorStop(0, "#bfe6ff"); g.addColorStop(1, "#2f8fe8");
      ctx.scale(1 / sq, sq);
      ctx.strokeStyle = "#0d3b7a"; ctx.lineWidth = 1.2 * S;
      for (const lato of [-1, 1]) {
        ctx.fillStyle = "#2f8fe8"; ctx.beginPath(); ctx.ellipse(lato * 6 * S, 9.5 * S, 4 * S, 2 * S, lato * 0.25, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
      ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(-d * 4 * S, -17 * S);
      ctx.bezierCurveTo(4 * S, -13 * S, 11 * S, -6 * S, 11 * S, 1 * S);
      ctx.bezierCurveTo(11 * S, 13 * S, -11 * S, 13 * S, -11 * S, 1 * S);
      ctx.bezierCurveTo(-11 * S, -6 * S, -6 * S, -10 * S, -d * 4 * S, -17 * S);
      ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1.5 * S; ctx.beginPath(); ctx.arc(-d * 3 * S, -2 * S, 6 * S, Math.PI * 1.05, Math.PI * 1.45); ctx.stroke();
      occhiCreatura(d * 2 * S, -1 * S, d, 2 * S, false);
      ctx.fillStyle = "#0d3b7a"; ctx.beginPath();
      ctx.ellipse(d * 3.4 * S, 4.6 * S, (att ? 2.2 : 1.3) * S, (att ? 2.4 : 0.9) * S, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  // --- Le esplosioni ----------------------------------------------------
  // Una sola ricetta per bombe e pieghevole: lampo, onda d'urto, palla di
  // fuoco che si gonfia e si spegne in fumo, detriti che volano e rimbalzano
  // su pagina e pavimento, braci che ricadono piano. E una spinta vera: i
  // lottatori, gli oggetti e i pezzi vicini vengono sbalzati via.
  const MAX_PARTICELLE = 320;
  function esplosione(x, y, potenza, att, inPieno) {
    suona("boom", x, potenza);
    const R = 80 * S * potenza;
    scossa = Math.max(scossa, Math.round(10 + 8 * potenza)); fermoColpo = Math.max(fermoColpo, 6);
    const metti = (q) => { if (particelle.length < MAX_PARTICELLE) particelle.push(q); };
    metti({ tipo: "lampo", x, y, vx: 0, vy: 0, vita: 7, max: 7, r: R * 1.4 });
    metti({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 24, max: 24, colore: "#fff3b0" });
    for (let i = 0; i < 9 * potenza; i++) {
      const a = caso(0, Math.PI * 2), d = caso(0, 0.35) * R;
      metti({ tipo: "fuoco", x: x + Math.cos(a) * d, y: y + Math.sin(a) * d, vx: Math.cos(a) * caso(0.3, 1.4) * S,
              vy: Math.sin(a) * caso(0.3, 1.4) * S - 0.6 * S, vita: Math.round(caso(18, 30)), max: 30, r: caso(8, 16) * S * potenza });
    }
    for (let i = 0; i < 10 * potenza; i++) {
      metti({ tipo: "fumo", x: x + caso(-0.4, 0.4) * R, y: y + caso(-0.3, 0.2) * R, vx: caso(-0.5, 0.5) * S, vy: -caso(0.4, 1.1) * S,
              vita: Math.round(caso(50, 90)), max: 90, r: caso(6, 12) * S * potenza, colore: Math.random() < 0.5 ? "#6d6a66" : "#8d8a85" });
    }
    for (let i = 0; i < 22 * potenza; i++) {
      const a = caso(Math.PI * 1.05, Math.PI * 1.95 + Math.PI * 0.6), v = caso(4, 12) * S * Math.sqrt(potenza);
      metti({ tipo: "detrito", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - caso(1, 4) * S, vita: Math.round(caso(70, 130)), max: 130,
              rot: caso(0, 6), va: caso(-0.4, 0.4), lato: caso(1.4, 3.2) * S,
              colore: ["#2b2f3a", "#5a4030", "#7d8696", "#3a3a3a"][Math.floor(Math.random() * 4)] });
    }
    for (let i = 0; i < 16 * potenza; i++) {
      const a = caso(0, Math.PI * 2), v = caso(2, 8) * S;
      metti({ tipo: "brace", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 2 * S, vita: Math.round(caso(40, 80)), max: 80,
              colore: Math.random() < 0.5 ? "#ffb62e" : "#ff6a1a" });
    }
    scintille(x, y, Math.round(14 * potenza), "#ffe27a");
    if (orda) for (const z of orda.zombie) if (vivoZ(z) && Math.hypot(z.x - x, corpoZ(z)[1] - y) < R * 1.1) colpisciZombie(z, 9, z.x >= x ? 1 : -1, z.x, corpoZ(z)[1], att);
    // La spinta: più forte vicino, niente oltre il raggio.
    for (const f of lottatori) {
      if (f.esploso || f.preso || f.fuoriCampo) continue;
      const b = f.p.bacino, dx = b.x - x, dy = b.y - y, d = Math.hypot(dx, dy) || 1;
      if (d > R * 1.6) continue;
      const k = Math.max(0, 1 - d / (R * 1.6)), ux = dx / d, uy = dy / d - 0.6;
      if (f.tiene) molla(f);
      if (f.tenuto && f.tenuto.da) molla(f.tenuto.da);
      for (const n in f.p) { f.p[n].ox -= ux * 13 * S * k; f.p[n].oy -= uy * 11 * S * k; }
      // Durante la tregua la bomba dell'alleato non manda in pezzi l'altro.
      if (inPieno && d < R * 0.42 && !(orda && att && att.tipo && att.tipo !== f.tipo)) { esplodiLottatore(f, att && att !== f ? att : null); continue; }
      if (d < R) {
        const chi = att && att !== f ? att : { dir: dx >= 0 ? 1 : -1, tipo: null, furia: 0 };
        colpisci(chi, f, 3 + 5 * k, b.x, b.y, "BOOM!");
        if (Math.random() < 0.6) smembra(f, x, y);
        if (eMela(f)) mordi(f, x, y);
      }
      f.inVolo = true; f.ko = Math.max(f.ko, 40); f.jet = 0; f.paracadute = 0;
    }
    for (const t of telefoni) {
      if (t.stato === "portato" || t.stato === "impugnato" || t.stato === "preso") continue;
      const dx = t.x - x, dy = t.y - y, d = Math.hypot(dx, dy) || 1;
      if (d > R * 1.8) continue;
      const k = 1 - d / (R * 1.8);
      t.ox = t.x - dx / d * 12 * S * k; t.oy = t.y - (dy / d - 0.7) * 12 * S * k; t.va += caso(-0.5, 0.5);
      t.stato = "volo"; t.da = null;
    }
    for (const pz of pezzi.concat(arti)) {
      const dx = pz.x - x, dy = pz.y - y, d = Math.hypot(dx, dy) || 1;
      if (d < R * 1.8) { const k = 1 - d / (R * 1.8); pz.ox = pz.x - dx / d * 10 * S * k; pz.oy = pz.y - (dy / d - 0.6) * 10 * S * k; }
    }
    if (y > pavimento - 70 * S) danneggiaStriscia(x, Math.min(1, 0.7 + 0.3 * potenza));
    if (x < R) danneggiaBordo("sinistra", y, 0.9);
    if (x > W - R) danneggiaBordo("destra", y, 0.9);
    if (y < R) danneggiaBordo("tetto", x, 0.9);
  }

  // --- Le bombe ----------------------------------------------------------
  // Si raccolgono e si lanciano come i telefoni, ma con la miccia accesa:
  // scoppiano quando finisce, o subito se centrano qualcuno.
  function scoppia(t) {
    if (t.morto) return;
    t.morto = true;
    const f = t.da && t.da.tel === t ? t.da : null;
    if (f) f.tel = null;
    esplosione(t.x, t.y, 1.15, t.lanciatore || null, true);
    scrivi("BOOM!", t.x, t.y - 30 * S, true);
  }

  // --- I danni che si vedono --------------------------------------------
  // Ogni colpo lascia un segno dove arriva: ammaccature sul robot, lividi
  // marroni sulla mela. Spariscono in un minuto. Con «effetti cruenti»
  // accesi (si spengono dalla tendina) i colpi fanno anche schizzare olio
  // nero dal robot e succo rosso dalla mela, che macchiano dove cadono.
  function segna(f, x, y, forza) {
    if (!f.p || !f.segni) return;
    const p = f.p, testa = Math.hypot(x - p.testa.x, y - p.testa.y) < Math.hypot(x - (p.collo.x + p.bacino.x) / 2, y - (p.collo.y + p.bacino.y) / 2);
    let ox, oy, ang, lim;
    if (eMela(f)) {
      const c = corpoMela(p); ox = c.x; oy = c.y; ang = c.ang; lim = [c.R / S * 0.7, c.R / S * 0.7];
    } else if (testa) {
      ox = p.testa.x; oy = p.testa.y; ang = Math.atan2(p.testa.y - p.collo.y, p.testa.x - p.collo.x) + Math.PI / 2; lim = [6.5, 5.5];
    } else {
      ox = (p.collo.x + p.bacino.x) / 2; oy = (p.collo.y + p.bacino.y) / 2;
      ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2; lim = [6.5, 9];
    }
    const dx = x - ox, dy = y - oy, c = Math.cos(-ang), s2 = Math.sin(-ang);
    const u = Math.max(-lim[0], Math.min(lim[0], (dx * c - dy * s2) / S)), v = Math.max(-lim[1], Math.min(lim[1], (dx * s2 + dy * c) / S));
    f.segni.push({ parte: eMela(f) ? "frutto" : testa ? "testa" : "busto", u, v,
                   r: Math.min(4.2, 1.6 + forza * 0.35), vita: 3600, seme: Math.random() * 6 });
    if (f.segni.length > 10) f.segni.shift();
  }
  function schizza(f, x, y, n, forza) {
    if (!cruento || !f.p) return;
    const robot = eRobot(f);
    for (let i = 0; i < n && particelle.length < MAX_PARTICELLE; i++) {
      const a = caso(-Math.PI, 0), v = caso(1.5, 3.5) * S * Math.sqrt(forza);
      particelle.push({ tipo: "goccia", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vita: 90, max: 90,
                        r: caso(0.9, 1.8) * S, colore: robot ? "#1b1b1b" : "#d8343f" });
    }
    if (robot) scintille(x, y, 3, "#ffe27a");
  }
  function macchia(x, y, r, colore) {
    macchie.push({ x, y, r: r * caso(1.2, 2), colore, vita: 900, schiacciata: caso(0.4, 0.6) });
    if (macchie.length > 24) macchie.shift();
  }
  // Gli arti si staccano con le armi pesanti (spada, pistola, bomba) e,
  // dopo qualche secondo, tornano al loro posto da soli: è un cartone.
  const ARTI = { A: ["gomitoA", "manoA", "braccio"], D: ["gomitoD", "manoD", "braccio"],
                 gA: ["ginocchioA", "piedeA", "gamba"], gD: ["ginocchioD", "piedeD", "gamba"],
                 P: ["testa", "testa", "picciolo"] };   // il picciolo della mela, l'antenna del robot
  function smembra(f, x, y) {
    if (!cruento || !f.p || f.esploso) return;
    // I personaggi inventati non hanno né picciolo né antenna da perdere.
    const liberi = Object.keys(ARTI).filter((k) => !f.staccati[k] && !(stile && k === "P"));
    if (!liberi.length) return;
    const k = liberi[Math.floor(Math.random() * liberi.length)], [g, m, forma] = ARTI[k];
    f.staccati[k] = 1;
    if (k === "A" && f.arma) lasciaArma(f);
    if (k === "A" && f.tel) lasciaCadere(f);
    if (forma === "gamba") {
      // Senza gambe si decide subito: su in volo, o avanti sulle mani.
      f.piano = null; f.pensa = Math.min(f.pensa, 16);
      if (gambe(f) === 0 && f.tel) lasciaCadere(f);
    }
    let P = f.p[g], Q = f.p[m];
    if (forma === "picciolo") {
      const c = eMela(f) ? corpoMela(f.p) : null;
      P = Q = c ? { x: c.x - Math.sin(c.ang) * -0.95 * c.R, y: c.y + Math.cos(c.ang) * -0.95 * c.R } : { x: f.p.testa.x, y: f.p.testa.y - 10 * S };
    }
    const vx = (P.x - x) * 0.08 + caso(-3, 3) * S, vy = -caso(4, 8) * S;
    const T = tavolozza || ["#2fae74", "#1c6f4a", "#7dffd2", "#154d34"], A = stile ? aspetto(f) : null;
    arti.push({ f, chiave: k, forma, x: (P.x + Q.x) / 2, y: (P.y + Q.y) / 2, ox: (P.x + Q.x) / 2 - vx, oy: (P.y + Q.y) / 2 - vy,
                ang: Math.atan2(Q.y - P.y, Q.x - P.x), va: caso(-0.4, 0.4), L: 20 * S, t: 0, da: null, grosso: !!A || f.tipo === "robot", olio: eRobot(f),
                colore: A ? (forma === "braccio" ? A.maniche : A.gambe) : f.tipo === "robot" ? (k.endsWith("D") ? T[1] : T[0]) : "#111",
                estremo: A ? (forma === "braccio" ? A.pelle : A.scarpe)
                           : forma === "braccio" ? (f.tipo === "robot" ? (k === "A" ? "#e03a2f" : "#b92b22") : (k === "A" ? "#2f72e0" : "#1f56b8"))
                                                 : (f.tipo === "robot" ? T[3] : "#f7f7f7") });
    if (forma !== "picciolo" || f.tipo === "mela") schizza(f, P.x, P.y, forma === "picciolo" ? 3 : 7, 2);
    else scintille(P.x, P.y, 6, "#ffe27a");
    scrivi(forma === "braccio" ? "AHIA!" : "OPS!", P.x, P.y - 14 * S, false);
  }
  // La mela si smembra a modo suo: i colpi forti le portano via un morso
  // (che si richiude piano), la spada la taglia in due (le metà si aprono e
  // poi si rincollano).
  const TAGLIO_CHIUDE = 230;
  function mordi(f, x, y) {
    if (!cruento || !eMela(f) || !f.p || f.esploso || f.taglio) return;
    const c = corpoMela(f.p), dx = x - c.x, dy = y - c.y, ca = Math.cos(-c.ang), sa = Math.sin(-c.ang);
    const lx = dx * ca - dy * sa, ly = dx * sa + dy * ca, a = Math.atan2(ly, lx);
    const m = { x: Math.cos(a) * 0.98, y: Math.sin(a) * 0.98, r: caso(0.32, 0.46), k: 0, vita: 2400 };
    if (!f.morsi) f.morsi = [];
    if (f.morsi.some((o) => Math.hypot(o.x - m.x, o.y - m.y) < o.r + m.r + 0.08)) return;
    f.morsi.push(m);
    if (f.morsi.length > 4) f.morsi.shift();
    // Il pezzo che vola via, e il succo.
    const wx = c.x + (Math.cos(c.ang) * m.x - Math.sin(c.ang) * m.y) * c.R;
    const wy = c.y + (Math.sin(c.ang) * m.x + Math.cos(c.ang) * m.y) * c.R;
    if (particelle.length < MAX_PARTICELLE) {
      particelle.push({ tipo: "pezzetto", x: wx, y: wy, vx: Math.cos(c.ang + a) * caso(2, 4) * S, vy: -caso(3, 6) * S,
                        vita: 140, max: 140, rot: caso(0, 6), va: caso(-0.3, 0.3), lato: m.r * c.R });
    }
    schizza(f, wx, wy, 5, 1.5);
  }
  function taglia(f, att) {
    if (!cruento || !eMela(f) || !f.p || f.esploso || f.taglio) return false;
    f.taglio = { ang: caso(-0.5, 0.5) + (Math.random() < 0.5 ? 0 : Math.PI / 2), t: 0 };
    f.morsi = [];
    f.ko = Math.max(f.ko, TAGLIO_CHIUDE + 40); f.inVolo = true;
    const c = corpoMela(f.p);
    schizza(f, c.x, c.y, 12, 3);
    scintille(c.x, c.y, 10, "#ffffff");
    scrivi("SLASH!", c.x, c.y - 30 * S, true);
    return true;
  }
  function aggiornaMela(f) {
    if (f.morsi && f.morsi.length) {
      for (const m of f.morsi) { m.vita--; m.k = m.vita > 300 ? Math.min(1, m.k + 0.2) : Math.max(0, m.vita / 300); }
      if (f.morsi[0].vita <= 0) f.morsi = f.morsi.filter((m) => m.vita > 0);
    }
    if (f.taglio) {
      const t = ++f.taglio.t;
      if (cruento && t < TAGLIO_CHIUDE && t % 16 === 0) { const c = corpoMela(f.p); schizza(f, c.x, c.y, 1, 0.5); }
      if (t === TAGLIO_CHIUDE + 22) { const c = corpoMela(f.p); scintille(c.x, c.y, 10, "#ffffff"); scrivi("CLICK!", c.x, c.y - 26 * S, false); }
      if (t > TAGLIO_CHIUDE + 24) f.taglio = null;
    }
  }

  const ARTO_VIA = 420, ARTO_TORNA = 30;
  function aggiornaArti() {
    for (const a of arti) {
      a.t++;
      const f = a.f;
      if (!f.p || f.esploso || !lottatori.includes(f)) { a.morto = true; continue; }
      if (a.t < ARTO_VIA) {
        rimbalzaPezzo(a);
        if (cruento && a.t % 9 === 0 && a.t < 160) schizza(f, a.x, a.y, 1, 0.5);
        continue;
      }
      // Torna a casa con un balzo: alla spalla o all'anca.
      const casa = a.forma === "braccio" ? f.p.collo : a.forma === "picciolo" ? f.p.testa : f.p.bacino;
      if (!a.da) a.da = [a.x, a.y, a.ang];
      const k = Math.min(1, (a.t - ARTO_VIA) / ARTO_TORNA), q = k * k * (3 - 2 * k);
      a.x = a.da[0] + (casa.x - a.da[0]) * q; a.y = a.da[1] + (casa.y - a.da[1]) * q - Math.sin(Math.PI * k) * 40 * S;
      a.ang = a.da[2] + 4 * Math.PI * q; a.ox = a.x; a.oy = a.y;
      if (k >= 1) { a.morto = true; f.staccati[a.chiave] = 0; if (a.forma === "gamba") f.piano = null; scintille(casa.x, casa.y, 6, "#7dffd2"); scrivi("CLICK!", casa.x, casa.y - 16 * S, false); }
    }
    if (arti.some((a) => a.morto)) arti = arti.filter((a) => !a.morto);
    for (const f of lottatori) {
      if (eMela(f)) aggiornaMela(f);
      if (f.segni && f.segni.length) { for (const sg of f.segni) sg.vita--; if (f.segni[0].vita <= 0) f.segni = f.segni.filter((sg) => sg.vita > 0); }
      // Dal moncone, ogni tanto, una goccia.
      if (cruento && passi % 14 === 0 && !f.esploso) {
        for (const k in f.staccati) if (f.staccati[k] && k !== "P") { const pt = k.startsWith("g") ? f.p.bacino : f.p.collo; schizza(f, pt.x, pt.y + 2 * S, 1, 0.4); }
      }
    }
    for (const m of macchie) m.vita--;
    if (macchie.length && macchie[0].vita <= 0) macchie = macchie.filter((m) => m.vita > 0);
  }

  // --- Il meteo: pioggia, neve di Natale, uragano -----------------------
  // LA PIOGGIA (rifatta il 05/10/2026: accesa, non si vedeva). Ogni goccia
  // moriva sul primo elemento della pagina che incontrava, e sul sito il primo
  // è la testata: larga quanto la finestra e attaccata al tetto. Le gocce
  // duravano un fotogramma. Ora cadono davanti alla pagina fino al pavimento;
  // una su quattro si ferma sul bordo alto di un elemento (mai su quelli
  // attaccati al tetto) e lì schizza. Stanno in un elenco loro: prima
  // riempivano quello delle particelle e, piovendo, sparivano le scintille
  // dei colpi. Dopo qualche secondo di pioggia arrivano i fulmini: chi
  // impugna una spada o vola in alto li attira.
  function nuovaGoccia() {
    const vy = caso(11, 15) * S, vx = (-2 + Math.sin(tempo * 0.004) * 1.4 + (uragano ? Math.sign(uragano.vx) * 3.5 : 0)) * S;
    const x = caso(-80, W + 80), y = -caso(8, 40) * S;
    let fondo = pavimento, sopra = false;
    if (Math.random() < 0.26) {
      for (const o of ostacoli) {
        if (o.t < 14 || o.t >= fondo) continue;
        const xo = x + vx * (o.t - y) / vy;
        if (xo > o.l && xo < o.r) { fondo = o.t; sopra = true; }
      }
    }
    gocce.push({ x, y, vx, vy, lung: caso(9, 17) * S, fondo, sopra });
  }
  function fulmineDalCielo() {
    const vivi = lottatori.filter((f) => f.p && !f.esploso && !f.fuori && !f.preso);
    let chi = vivi.find((f) => f.arma && f.arma.tipo === "spada") || null;
    if (!chi) {
      const alti = vivi.filter((f) => f.jet > 0 && f.p.bacino.y < pavimento - 150 * S);
      if (alti.length && Math.random() < 0.7) chi = alti[Math.floor(Math.random() * alti.length)];
    }
    if (!chi && vivi.length && Math.random() < 0.25) chi = vivi[Math.floor(Math.random() * vivi.length)];
    const x = chi ? chi.p.collo.x : caso(50 * S, W - 50 * S);
    fulmini.push({ x, t: 0, da: neutro(Math.random() < 0.5 ? -1 : 1), cielo: true, forza: 5, punti: null });
  }
  function aggiornaPioggia() {
    piovendo = acquazzone || tempo < pioggiaFino;
    if (piovendo) {
      pioveDa++;
      const quante = Math.max(2, Math.round(W / 230)), tetto = Math.round(Math.max(160, W * 0.36));
      for (let i = 0; i < quante && gocce.length < tetto; i++) nuovaGoccia();
      bagnato = Math.min(1, bagnato + 0.004);
      if (pioveDa > 240 && --prossimoLampo <= 0) { fulmineDalCielo(); prossimoLampo = Math.round(caso(420, 900)); }
      // Chi cammina nell'acqua la solleva.
      if (passi % 8 === 0 && bagnato > 0.3) {
        for (const f of lottatori) {
          if (f.p && !f.esploso && !f.supporto && (f.azione === "avanza" || f.azione === "indietro") && spruzzi.length < 70) {
            spruzzi.push({ x: f.p.piedeD.x, y: pavimento, t: 0 });
          }
        }
      }
    } else { pioveDa = 0; bagnato = Math.max(0, bagnato - 0.0015); }
    if (!gocce.length && !spruzzi.length) return;
    let vive = 0;
    for (let i = 0; i < gocce.length; i++) {
      const g = gocce[i];
      g.x += g.vx; g.y += g.vy;
      if (g.y >= g.fondo) {
        if (spruzzi.length < 70 && (g.sopra || Math.random() < 0.55)) spruzzi.push({ x: g.x, y: g.fondo, t: 0 });
        continue;
      }
      gocce[vive++] = g;
    }
    gocce.length = vive;
    for (const z of spruzzi) z.t++;
    if (spruzzi.length && spruzzi[0].t > 9) spruzzi = spruzzi.filter((z) => z.t <= 9);
  }
  function disegnaPioggia() {
    if (!gocce.length && !spruzzi.length && bagnato < 0.02) return;
    ctx.save();
    if (bagnato > 0.02) {
      // Il cielo si incupisce appena, in alto; il pavimento luccica e si formano le pozze.
      const g = ctx.createLinearGradient(0, 0, 0, H * 0.42);
      g.addColorStop(0, "rgba(52,64,88," + (0.2 * bagnato * (piovendo ? 1 : 0.4)).toFixed(3) + ")"); g.addColorStop(1, "rgba(52,64,88,0)");
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H * 0.42);
      ctx.fillStyle = "rgba(120,175,240," + (0.5 * bagnato).toFixed(3) + ")"; ctx.fillRect(0, pavimento - 2.4 * S, W, 2.4 * S);
      ctx.fillStyle = "rgba(160,205,255," + (0.6 * bagnato).toFixed(3) + ")";
      for (let i = 0; i < 6; i++) {
        const x = W * (0.09 + 0.165 * i + 0.03 * Math.sin(i * 5.3)), larga = (16 + 13 * ((i * 7) % 3)) * S * bagnato;
        ctx.beginPath(); ctx.ellipse(x, pavimento - 1.6 * S, larga, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.lineCap = "round";
    ctx.strokeStyle = paginaScura ? "rgba(196,220,255,.6)" : "rgba(58,104,178,.62)"; ctx.lineWidth = 1.35 * S;
    ctx.beginPath();
    for (const g of gocce) { const k = g.lung / g.vy; ctx.moveTo(g.x, g.y); ctx.lineTo(g.x - g.vx * k, g.y - g.lung); }
    ctx.stroke();
    ctx.strokeStyle = paginaScura ? "rgba(214,232,255,.8)" : "rgba(58,104,178,.75)"; ctx.lineWidth = 1.1 * S;
    ctx.beginPath();
    for (const z of spruzzi) {
      const r = (1.5 + z.t * 0.75) * S;
      ctx.moveTo(z.x - r, z.y - r * 0.55); ctx.lineTo(z.x - r * 0.4, z.y - 0.6 * S);
      ctx.moveTo(z.x + r, z.y - r * 0.55); ctx.lineTo(z.x + r * 0.4, z.y - 0.6 * S);
    }
    ctx.stroke();
    ctx.restore();
  }

  function aggiornaMeteo() {
    aggiornaPioggia();
    // La neve, l'albero e i pupazzi del tema natalizio li fa `natale.js` per
    // tutto il sito: qui restano solo i cappellini e le palle di neve.
    if (uragano) {
      const u = uragano;
      u.t++;
      u.x += u.vx;
      if (u.x < 80 * S || u.x > W - 80 * S) u.vx = -u.vx;
      const alto = Math.min(320 * S, pavimento - testataBasso - 40 * S);
      for (const f of lottatori) {
        if (f.esploso || f.preso || f.tenuto || verso < 0) continue;
        if (f.uraganoCd > 0) { f.uraganoCd--; continue; }
        const b = f.p.bacino, dx = b.x - u.x;
        if (Math.abs(dx) < 60 * S && b.y > pavimento - alto) {
          // Preso dal vortice: gira intorno all'imbuto e sale.
          f.ko = Math.max(f.ko, 25); f.inVolo = true; f.jet = 0; f.paracadute = 0; f.fantasma = true;
          const fase = u.t * 0.12 + (f.tipo === "mela" ? Math.PI : 0), raggio = (24 + 40 * (pavimento - b.y) / alto) * S;
          const tx = u.x + Math.cos(fase) * raggio;
          for (const n in f.p) { const q = f.p[n]; q.x += (tx - b.x) * 0.05; q.y -= GRAVITA * S * moltG * 1.35; }
          if (b.y < pavimento - alto) {
            // In cima viene sputato via di lato.
            const lato = Math.random() < 0.5 ? -1 : 1;
            for (const n in f.p) { f.p[n].ox = f.p[n].x - lato * 10 * S; f.p[n].oy = f.p[n].y + 2 * S; }
            f.uraganoCd = 160; scrivi("WHOOSH!", b.x, b.y - 20 * S, false);
          }
        } else if (Math.abs(dx) < 320 * S) {
          for (const n in f.p) f.p[n].x -= Math.sign(dx) * 0.22 * S * (1 - Math.abs(dx) / (320 * S));
        }
      }
      for (const t of telefoni) {
        if (t.stato === "portato" || t.stato === "impugnato" || t.stato === "preso") continue;
        const dx = t.x - u.x;
        if (Math.abs(dx) < 60 * S && t.y > pavimento - alto) {
          t.stato = "volo"; t.da = null;
          t.x += (u.x + Math.cos(u.t * 0.15 + t.r) * 34 * S - t.x) * 0.06; t.y -= GRAVITA * S * moltG * 1.4; t.va += 0.02;
          if (t.y < pavimento - alto) { t.ox = t.x + Math.sign(dx || 1) * -9 * S; }
        }
      }
      if (passi % 3 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "vento", x: u.vx > 0 ? -20 : W + 20, y: caso(80, pavimento - 10), vx: Math.sign(u.vx) * caso(8, 14) * S, vy: 0,
                          vita: 120, max: 120, lung: caso(20, 60) * S });
      }
    }
  }
  // L'uragano: una nuvola scura in alto, un imbuto che si torce e serpeggia,
  // nastri di vento che gli girano intorno (davanti chiari, dietro scuri),
  // detriti che orbitano e una nube di polvere alla base.
  function disegnaUragano() {
    const u = uragano, alto = Math.min(320 * S, pavimento - testataBasso - 40 * S), t = u.t;
    const larg = (k) => (7 + 64 * Math.pow(k, 1.5)) * S;
    const asse = (k) => u.x + Math.sin(t * 0.035 + k * 3.2) * 16 * S * k + Math.sin(t * 0.11 + k * 7) * 3 * S * k;
    const yk = (k) => pavimento - k * alto;
    const N = 24;
    ctx.save();
    // 1. La sagoma dell'imbuto, con una sfumatura dall'alto al basso.
    const g = ctx.createLinearGradient(0, yk(1), 0, pavimento);
    g.addColorStop(0, "rgba(78,86,98,.55)"); g.addColorStop(0.7, "rgba(110,116,124,.38)"); g.addColorStop(1, "rgba(150,140,120,.28)");
    ctx.fillStyle = g; ctx.beginPath();
    for (let i = 0; i <= N; i++) { const k = i / N; ctx[i ? "lineTo" : "moveTo"](asse(k) - larg(k), yk(k)); }
    for (let i = N; i >= 0; i--) { const k = i / N; ctx.lineTo(asse(k) + larg(k), yk(k)); }
    ctx.closePath(); ctx.fill();
    // 2. I nastri di vento a spirale: prima quelli dietro, poi quelli davanti.
    ctx.lineCap = "round";
    for (const davanti of [false, true]) {
      for (let s = 0; s < 9; s++) {
        const fase = t * 0.16 + s * 0.7;
        ctx.strokeStyle = davanti ? "rgba(235,238,242,.75)" : "rgba(55,60,70,.35)";
        ctx.beginPath();
        let su = false;
        for (let i = 0; i <= 36; i++) {
          const k = i / 36, th = fase + k * 9, fronte = Math.cos(th) > 0;
          if (fronte !== davanti || k < 0.03) { su = false; continue; }
          const x = asse(k) + Math.sin(th) * larg(k), y = yk(k) + Math.cos(th) * larg(k) * 0.12;
          ctx.lineWidth = (1 + 1.6 * k) * S;
          if (su) ctx.lineTo(x, y); else { ctx.moveTo(x, y); su = true; }
        }
        ctx.stroke();
      }
    }
    // 3. Detriti che orbitano: fogli, foglie e sassi.
    for (let i = 0; i < 12; i++) {
      const k = 0.08 + ((i * 0.37 + t * 0.002) % 0.85), th = t * (0.12 + (i % 3) * 0.03) + i * 1.7;
      const x = asse(k) + Math.sin(th) * larg(k) * 1.05, y = yk(k) + Math.cos(th) * larg(k) * 0.14;
      ctx.save(); ctx.translate(x, y); ctx.rotate(th * 2);
      ctx.globalAlpha = Math.cos(th) > 0 ? 0.95 : 0.4;
      ctx.fillStyle = ["#f4f1e8", "#5f9a3a", "#8a7a66", "#d9a520"][i % 4];
      if (i % 4 === 0) ctx.fillRect(-3 * S, -2 * S, 6 * S, 4 * S);
      else if (i % 4 === 1) { ctx.beginPath(); ctx.ellipse(0, 0, 3.6 * S, 1.6 * S, 0, 0, Math.PI * 2); ctx.fill(); }
      else { ctx.beginPath(); ctx.arc(0, 0, 1.8 * S, 0, Math.PI * 2); ctx.fill(); }
      ctx.restore();
    }
    // 4. La nuvola temporalesca in cima.
    const cx = asse(1), cy = yk(1) - 4 * S, cw = larg(1) * 1.5;
    for (const [dx, dy, r, c] of [[-0.85, 0.15, 0.42, "#59606b"], [0.85, 0.12, 0.44, "#59606b"], [-0.4, -0.2, 0.55, "#6b727d"],
                                 [0.4, -0.18, 0.58, "#6b727d"], [0, 0.05, 0.6, "#4e545e"]]) {
      ctx.globalAlpha = 0.5; ctx.fillStyle = c;
      ctx.beginPath(); ctx.ellipse(cx + dx * cw + Math.sin(t * 0.02 + dx) * 3 * S, cy + dy * cw * 0.3, r * cw * 0.62, r * cw * 0.34, 0, 0, Math.PI * 2); ctx.fill();
    }
    if (t % 160 < 6) {
      // Un lampo nella nuvola.
      ctx.globalAlpha = 1; ctx.strokeStyle = "#fff6b0"; ctx.lineWidth = 2 * S; ctx.lineJoin = "miter";
      let x = cx + caso(-0.5, 0.5) * cw, y = cy;
      ctx.beginPath(); ctx.moveTo(x, y);
      for (let i = 0; i < 4; i++) { x += caso(-10, 10) * S; y += caso(8, 14) * S; ctx.lineTo(x, y); }
      ctx.stroke();
    }
    // 5. La polvere che gira alla base.
    for (let i = 0; i < 8; i++) {
      const th = t * 0.09 + i * 0.8, r = (18 + (i % 3) * 10) * S;
      ctx.globalAlpha = 0.28; ctx.fillStyle = "#a99c86";
      ctx.beginPath(); ctx.ellipse(asse(0) + Math.cos(th) * r * 1.4, pavimento - 6 * S + Math.sin(th) * 3 * S, (9 + (i % 2) * 5) * S, 5 * S, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }
  function disegnaAlbero() {
    const x = Math.max(60 * S, Math.min(W - 60 * S, 70 * S)), y = pavimento;
    ctx.save();
    ctx.fillStyle = "#6b4423"; ctx.fillRect(x - 4 * S, y - 14 * S, 8 * S, 14 * S);
    const piani = [[0, 34, 26], [20, 28, 24], [38, 21, 22], [54, 14, 18]];
    for (const [su, largo, alto] of piani) {
      ctx.fillStyle = "#2e8b4e"; ctx.strokeStyle = "#1c5a33"; ctx.lineWidth = 1.2 * S;
      ctx.beginPath(); ctx.moveTo(x - largo * S, y - (14 + su) * S); ctx.lineTo(x + largo * S, y - (14 + su) * S);
      ctx.lineTo(x, y - (14 + su + alto) * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2 * S; ctx.beginPath();
      ctx.moveTo(x - largo * 0.7 * S, y - (16 + su) * S); ctx.lineTo(x + largo * 0.7 * S, y - (16 + su) * S); ctx.stroke();
    }
    const palline = [[-18, 22, "#d8343f"], [14, 26, "#ffcf3a"], [-6, 42, "#2f72e0"], [12, 50, "#d8343f"], [-8, 60, "#ffcf3a"], [4, 72, "#d8343f"]];
    for (const [dx, su, c] of palline) {
      const accesa = (Math.floor(passi / 20) + dx) % 3 !== 0;
      tondo(x + dx * S, y - su * S, 2.3 * S, accesa ? c : mix(c, "#000000", 0.4));
    }
    stella(x, y - 94 * S, 6 * S, "#ffd84a");
    ctx.restore();
  }
  // Il cappellino rosso, in coordinate della testa (o del frutto).
  function cappellino(dx, dy, largo, verso) {
    ctx.save(); ctx.translate(dx, dy); ctx.rotate(verso * 0.25);
    ctx.fillStyle = "#d8343f"; ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S;
    ctx.beginPath(); ctx.moveTo(-largo, 0); ctx.quadraticCurveTo(-largo * 0.2, -largo * 1.6, verso * largo * 1.3, -largo * 0.9);
    ctx.lineTo(largo, 0); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#ffffff"; rettangoloTondo(-largo * 1.1, -largo * 0.25, largo * 2.2, largo * 0.5, largo * 0.25); ctx.fill(); ctx.stroke();
    tondo(verso * largo * 1.3, -largo * 0.9, largo * 0.32, "#ffffff");
    ctx.restore();
  }
  // La palla di neve: si raccoglie da terra e si tira ad arco.
  function tiraPalla(f, altro) {
    const m = f.p.manoA, g = GRAVITA * S * moltG * verso * 0.6, T = caso(26, 34);
    const tx = altro.p.collo.x + caso(-6, 6) * S, ty = altro.p.collo.y + caso(-6, 6) * S;
    proiettili.push({ x: m.x, y: m.y, vx: (tx - m.x) / T, vy: (ty - m.y) / T - 0.5 * g * T, da: f, vita: 200, neve: true });
    f.palla = false;
  }

  // --- TERREMOTO ED ERUZIONE (05/10/2026, su richiesta) -------------------
  // Prima il terremoto era una spinta di un pixel e mezzo ogni sei fotogrammi:
  // i muscoli la assorbivano e non si vedeva niente. Ora dura dieci secondi e
  // ha tre tempi. LE SCOSSE: il suolo scappa sotto i piedi, chi cammina può
  // perdere l'equilibrio, gli oggetti saltano, dagli elementi della pagina
  // cadono calcinacci (e sul sito trema la pagina: `html.ring-trema`). IL
  // VULCANO sfonda il pavimento. L'ERUZIONE: fontana di lava, lapilli che
  // ricadono sul ring e lasciano pozze roventi. Chi vola non sente le scosse;
  // il fianco del vulcano non si attraversa a piedi; chi finisce sopra la
  // bocca mentre erutta viene sparato in aria.
  const SISMA = { sale: 60, cono: 150, erutta: 450, cala: 520, fine: 600 };
  const CONO_BASE = 78, CONO_ALTO = 72, CONO_BOCCA = 13;
  // Chi fa male senza essere uno dei due: un fulmine, un lapillo, un meteorite.
  const neutro = (dir) => ({ dir: dir || 1, tipo: null, furia: 0, azione: null, creatura: true });
  function avviaSisma() {
    if (sisma) { sisma.t = Math.min(sisma.t, SISMA.cono); return; }      // già in corso: il vulcano si risveglia
    let x = W / 2;
    for (let i = 0; i < 10; i++) {
      x = caso(0.18, 0.82) * W;
      if (!lottatori.some((f) => f.p && !f.esploso && Math.abs(f.p.bacino.x - x) < 120 * S)) break;
    }
    sisma = { t: 0, x, alto: 0, k: 0, colpi: 0, prossimo: 0, seme: Math.random() * 100, fermo: false };
    radiceHtml("add", "ring-trema");
  }
  function fineSisma() {
    sisma = null;
    radiceHtml("remove", "ring-trema");
  }
  // Quanto è alto il vulcano sopra il pavimento, in un punto.
  function altoVulcano(x) {
    if (!sisma || sisma.alto <= 0) return 0;
    const u = Math.abs(x - sisma.x) / (CONO_BASE * S), bocca = CONO_BOCCA / CONO_BASE;
    if (u >= 1) return 0;
    return CONO_ALTO * S * sisma.alto * (u <= bocca ? 1 : Math.pow((1 - u) / (1 - bocca), 1.25));
  }
  const cimaVulcano = () => pavimento - CONO_ALTO * S * (sisma ? sisma.alto : 0);
  // C'è il vulcano fra questi due, tutti e due a terra?
  function vulcanoInMezzo(f, altro) {
    if (!sisma || sisma.alto < 0.4) return false;
    return (f.cx - sisma.x) * (altro.cx - sisma.x) < 0 && f.base >= pavimento - 30 * S && altro.base >= pavimento - 30 * S;
  }
  // Una scossa: il suolo va di lato e chi ci sta sopra lo segue coi piedi.
  function scossone(s) {
    const k = s.k, lato = ++s.colpi % 2 ? 1 : -1, j = lato * caso(2.4, 4.6) * S * k;
    for (const f of lottatori) {
      if (!f.p || f.esploso || f.fuori || f.preso || f.tenuto || f.jet > 0 || f.gelato > 0) continue;
      if (f.scalata) {
        // Appeso a un bordo: ogni tanto la presa cede.
        if (Math.random() < 0.07 * k) { f.scalata = null; f.inVolo = true; f.ko = Math.max(f.ko, 26); scrivi("OPS!", f.p.testa.x, f.p.testa.y - 16 * S, false); }
        continue;
      }
      const piede = verso > 0 ? Math.max(f.p.piedeA.y, f.p.piedeD.y) : Math.min(f.p.piedeA.y, f.p.piedeD.y);
      if ((f.base - piede) * verso > 9 * S) continue;                     // sta cadendo: non tocca terra
      for (const n in f.p) {
        const peso = n.startsWith("piede") ? 1.5 : n.startsWith("ginocchio") ? 1.1 : n === "testa" ? 0.3 : 0.6;
        f.p[n].ox -= j * peso; f.p[n].oy += caso(0.6, 2.8) * S * k * verso;
      }
      f.trema = 9;
      if (!f.ko && Math.random() < 0.03 * k * (f.azione === "avanza" ? 1.7 : 1)) {
        for (const n of ["testa", "collo"]) f.p[n].ox -= j * 2.5;
        f.ko = Math.max(f.ko, 38); f.inVolo = true; f.azione = null;
        scrivi("OPS!", f.p.testa.x, f.p.testa.y - 16 * S, false);
      }
    }
    for (const t of telefoni) if (t.stato === "libero") { t.oy += caso(1.5, 4) * S * k; t.ox += caso(-2.5, 2.5) * S * k; t.va += caso(-0.2, 0.2); }
    for (const c of creature) if (c.aTerra && c.el !== "fuoco") c.vy = -caso(1.5, 3) * S * k;
    // Calcinacci: sassolini dal bordo basso di due elementi a caso (o dal tetto), polvere dal pavimento.
    for (let i = 0; i < 2 && particelle.length < MAX_PARTICELLE - 90; i++) {
      const o = ostacoli.length && Math.random() < 0.75 ? ostacoli[Math.floor(Math.random() * ostacoli.length)] : null;
      const x = o ? caso(o.l, o.r) : caso(0, W), y = o ? o.b : 2;
      if (y > pavimento - 30 * S) continue;
      particelle.push({ tipo: "detrito", x, y, vx: caso(-0.6, 0.6) * S, vy: caso(0, 1) * S, vita: 110, max: 110, rot: caso(0, 6),
                        va: caso(-0.3, 0.3), lato: caso(1.4, 3) * S, colore: i ? "#9a948a" : "#b9b4ab" });
    }
    if (s.colpi % 2 === 0 && particelle.length < MAX_PARTICELLE - 90) {
      particelle.push({ tipo: "polvere", x: caso(0, W), y: pavimento - 2, vx: caso(-1.2, 1.2) * S, vy: -caso(0.3, 1) * S,
                        vita: Math.round(caso(16, 28)), max: 28, colore: "#b9b4ab" });
    }
  }
  function sbuffoLava(x, y, k) {
    const metti = (q) => { if (particelle.length < MAX_PARTICELLE - 30) particelle.push(q); };
    for (let i = 0; i < 3 * k; i++) {
      metti({ tipo: "fuoco", x: x + caso(-4, 4) * S, y: y - 2 * S, vx: caso(-0.8, 0.8) * S, vy: -caso(0.4, 1.4) * S,
              vita: Math.round(caso(12, 20)), max: 20, r: caso(3, 5.5) * S });
    }
    for (let i = 0; i < 5 * k; i++) {
      const a = caso(Math.PI * 1.1, Math.PI * 1.9), v = caso(2, 5.5) * S;
      metti({ tipo: "brace", x, y: y - 2 * S, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vita: Math.round(caso(26, 50)), max: 50,
              colore: Math.random() < 0.5 ? "#ffb62e" : "#ff6a1a" });
    }
  }
  function nuovaColata(x, y, r) {
    colate.push({ x, y, r: r * caso(2.2, 3.2), t: 0, vita: Math.round(caso(240, 330)), seme: Math.random() * 6 });
    if (colate.length > 14) colate.shift();
  }
  // Un lapillo: una bomba di lava sparata dalla bocca. Quattro su dieci sono
  // tirati addosso a uno dei due; gli altri ricadono dove capita.
  function nuovoLapillo(mirato) {
    const s = sisma;
    if (!s || lapilli.length >= 16) return;
    const x0 = s.x + caso(-6, 6) * S, y0 = cimaVulcano() - 4 * S, g = GRAVITA * S * Math.max(0.35, moltG) * 0.8;
    const vivi = lottatori.filter((f) => f.p && !f.esploso && !f.fuori);
    let vx, vy;
    if (mirato && vivi.length) {
      const f = vivi[Math.floor(Math.random() * vivi.length)], T = caso(48, 66);
      const tx = f.p.bacino.x + caso(-26, 26) * S, ty = Math.min(pavimento, f.base) - 6 * S;
      vx = (tx - x0) / T; vy = (ty - y0) / T - 0.5 * g * T;
    } else { vx = caso(-6.5, 6.5) * S; vy = -caso(8.5, 13) * S; }
    const lim = VELOCITA_MAX * S;
    vx = Math.max(-lim * 0.7, Math.min(lim * 0.7, vx)); vy = Math.max(-lim, Math.min(-3 * S, vy));
    lapilli.push({ x: x0, y: y0, vx, vy, g, r: caso(3.2, 5.6) * S, scia: [], t: 0, sopra: Math.random() < 0.55, morto: false });
  }
  // La scottatura: un colpo leggero e un salto via dal caldo.
  function scotta(f, lato) {
    if (f.scotta > 0 || f.esploso || f.preso || !f.p) return false;
    f.scotta = 55;
    colpisci(neutro(lato), f, 2.6, f.p.bacino.x, f.p.bacino.y, "SCOTTA!");
    if (f.azione === "barriera") return false;
    for (const n in f.p) { f.p[n].oy += verso * 5.5 * S; f.p[n].ox -= lato * 3.5 * S; }
    sbuffoLava(f.p.piedeA.x, f.p.piedeA.y, 0.4);
    return true;
  }
  function vulcanoContro(f, erutta) {
    const s = sisma;
    if (!f.p || f.esploso || f.fuori || f.preso || f.tenuto) return;
    const b = f.p.bacino, dx = b.x - s.x, cima = cimaVulcano(), lato = dx >= 0 ? 1 : -1;
    // Sopra la bocca mentre erutta: la fontana lo spara in aria.
    if (erutta && Math.abs(dx) < (CONO_BOCCA + 8) * S && b.y > cima - 100 * S && b.y < cima + 30 * S && !(f.scotta > 0)) {
      scotta(f, lato);
      if (f.azione === "barriera") return;
      for (const n in f.p) { f.p[n].oy = f.p[n].y + 13 * S; f.p[n].ox = f.p[n].x - lato * caso(1, 4) * S; }
      f.inVolo = true; f.ko = Math.max(f.ko, 44); f.jet = 0; f.caos = 0; f.paracadute = 0; f.azione = null; f.scalata = null;
      scrivi("FWOOSH!", b.x, b.y - 30 * S, false);
      return;
    }
    const zona = CONO_BASE * S * 0.82 * s.alto;
    if (Math.abs(dx) >= zona || b.y < cima - 30 * S || f.jet > 0 || verso < 0) return;
    // Il fianco spinge fuori: di qui a piedi non si passa.
    const fuori = Math.min(3.2 * S, (zona - Math.abs(dx)) * 0.14 + 0.4 * S);
    for (const n in f.p) { f.p[n].x += lato * fuori; f.p[n].ox += lato * fuori; }
    f.cx += lato * fuori;
    if (f.azione === "avanza" && (f.meta - f.cx) * lato < 0) { f.azione = null; f.pensa = Math.round(caso(8, 20)); f.prendiTel = null; }
    if (erutta) scotta(f, lato);
  }
  function aggiornaLava() {
    for (const b of lapilli) {
      b.t++; b.vy += b.g;
      const py = b.y;
      b.x += b.vx; b.y += b.vy;
      if (passi % 2 === 0) { b.scia.push(b.x, b.y); if (b.scia.length > 12) b.scia.splice(0, 2); }
      if (b.x < b.r || b.x > W - b.r) { b.vx = -b.vx * 0.6; b.x = Math.max(b.r, Math.min(W - b.r, b.x)); }
      let giu = null;
      const suolo = pavimento - altoVulcano(b.x);
      if (b.y >= suolo - b.r && b.t > 6) giu = suolo;
      else if (b.sopra && b.vy > 0) {
        for (const o of ostacoli) if (o.t > 14 && b.x > o.l && b.x < o.r && py <= o.t && b.y >= o.t - b.r) { giu = o.t; break; }
      }
      if (giu === null && (b.y < -400 * S || b.t > 420)) { b.morto = true; continue; }
      let preso = null;
      if (b.t > 8) {
        for (const f of lottatori) {
          if (!f.p || f.esploso || f.fuori || f.preso) continue;
          for (const n of ["testa", "collo", "bacino"]) {
            if (Math.hypot(f.p[n].x - b.x, f.p[n].y - b.y) < f.p[n].r + b.r + 1.5 * S) { preso = f; break; }
          }
          if (preso) break;
        }
      }
      if (preso) {
        b.morto = true;
        colpisci(neutro(Math.sign(b.vx) || 1), preso, 4, b.x, b.y, "TSSS!");
        sbuffoLava(b.x, b.y, 1);
      } else if (giu !== null) {
        b.morto = true;
        // Sul fianco del vulcano non resta una pozza: solo uno sbuffo.
        if (giu !== suolo || altoVulcano(b.x) < 2 * S) nuovaColata(b.x, giu, b.r);
        sbuffoLava(b.x, giu, 0.7);
      }
    }
    if (lapilli.some((b) => b.morto)) lapilli = lapilli.filter((b) => !b.morto);
    for (const c of colate) {
      c.t++;
      if (c.t > c.vita * 0.62) continue;                    // ormai è roccia: non scotta più
      for (const f of lottatori) {
        if (!f.p || f.esploso || f.fuori || f.preso || f.tenuto || f.jet > 0 || f.scotta > 0) continue;
        for (const n of ["piedeA", "piedeD", "bacino"]) {
          const pt = f.p[n];
          if (Math.abs(pt.x - c.x) < c.r + 3 * S && Math.abs(pt.y - c.y) < 9 * S) { scotta(f, f.p.bacino.x >= c.x ? 1 : -1); break; }
        }
      }
    }
    if (colate.some((c) => c.t >= c.vita)) colate = colate.filter((c) => c.t < c.vita);
  }
  function aggiornaSisma() {
    for (const f of lottatori) if (f.scotta > 0) f.scotta--;
    if (lapilli.length || colate.length) aggiornaLava();
    const s = sisma;
    if (!s) return;
    const T = ++s.t;
    s.k = T < 90 ? 0.35 + 0.65 * T / 90 : T < SISMA.erutta + 20 ? 1 : Math.max(0, 1 - (T - SISMA.erutta - 20) / 70);
    const su = Math.min(1, Math.max(0, (T - SISMA.sale) / (SISMA.cono - SISMA.sale)));
    s.alto = T < SISMA.cala ? su * su * (3 - 2 * su) : Math.max(0, 1 - (T - SISMA.cala) / (SISMA.fine - SISMA.cala));
    if (s.k > 0) {
      scossa = Math.max(scossa, Math.round(2 + 4 * s.k));
      if (T % 5 === 0) scossone(s);
      if (T === 34 || T === 240) danneggiaStriscia(caso(0.15, 0.85) * W, 0.6);
    } else if (!s.fermo) { s.fermo = true; radiceHtml("remove", "ring-trema"); }
    const metti = (q) => { if (particelle.length < MAX_PARTICELLE - 40) particelle.push(q); };
    const cima = cimaVulcano();
    // Il cono che sfonda il pavimento: polvere e sassi alla base.
    if (T > SISMA.sale && T < SISMA.cono && T % 3 === 0) {
      const lato = T % 6 ? 1 : -1, x = s.x + lato * caso(0.3, 1) * CONO_BASE * S * Math.max(0.3, s.alto);
      metti({ tipo: "polvere", x, y: pavimento - 3 * S, vx: lato * caso(0.4, 1.6) * S, vy: -caso(0.3, 1.1) * S, vita: 26, max: 28, colore: "#8a7f70" });
      metti({ tipo: "detrito", x, y: pavimento - altoVulcano(x) - 2 * S, vx: lato * caso(0.5, 3) * S, vy: -caso(1.5, 5) * S, vita: 90, max: 90,
              rot: caso(0, 6), va: caso(-0.3, 0.3), lato: caso(1.8, 3.6) * S, colore: Math.random() < 0.5 ? "#5a4338" : "#3a2c26" });
    }
    if (T === SISMA.cono) {
      // Il botto: parte l'eruzione.
      scossa = Math.max(scossa, 18); fermoColpo = Math.max(fermoColpo, 5);
      metti({ tipo: "lampo", x: s.x, y: cima, vx: 0, vy: 0, vita: 9, max: 9, r: 170 * S });
      metti({ tipo: "onda", x: s.x, y: cima, vx: 0, vy: 0, vita: 26, max: 26, colore: "#ffb62e" });
      scrivi("BOOOM!", s.x, Math.max(50, cima - 46 * S), true);
      for (let i = 0; i < 5; i++) nuovoLapillo(false);
    }
    const erutta = T >= SISMA.cono && T < SISMA.erutta;
    if (erutta) {
      if (T % 2 === 0) {
        metti({ tipo: "fuoco", x: s.x + caso(-7, 7) * S, y: cima - 2 * S, vx: caso(-1.4, 1.4) * S, vy: -caso(2.5, 6) * S,
                vita: Math.round(caso(16, 26)), max: 26, r: caso(4.5, 8.5) * S });
      }
      if (T % 3 === 0) {
        metti({ tipo: "brace", x: s.x + caso(-6, 6) * S, y: cima - 3 * S, vx: caso(-3.4, 3.4) * S, vy: -caso(5, 10.5) * S,
                vita: Math.round(caso(40, 76)), max: 76, colore: Math.random() < 0.5 ? "#ffb62e" : "#ff6a1a" });
      }
      if (--s.prossimo <= 0) { nuovoLapillo(Math.random() < 0.4); s.prossimo = Math.round(caso(11, 22)); }
    }
    if (T >= SISMA.cono - 30 && T < SISMA.cala && T % (erutta ? 4 : 7) === 0) {
      metti({ tipo: "fumo", x: s.x + caso(-9, 9) * S, y: cima - 8 * S, vx: caso(-0.5, 0.9) * S, vy: -caso(1, 2.2) * S,
              vita: Math.round(caso(60, 100)), max: 100, r: caso(8, 14) * S, colore: Math.random() < 0.5 ? "#4d4a48" : "#6d6a66" });
    }
    if (s.alto > 0.15) for (const f of lottatori) vulcanoContro(f, erutta);
    if (T >= SISMA.fine) fineSisma();
  }
  function disegnaVulcano() {
    const s = sisma;
    if (!s || s.alto <= 0.01) return;
    const B = CONO_BASE * S, x0 = s.x, y0 = pavimento, cima = cimaVulcano(), bocca = CONO_BOCCA * S, T = s.t, u0 = CONO_BOCCA / CONO_BASE;
    const erutta = T >= SISMA.cono && T < SISMA.erutta;
    const caldo = T < SISMA.cono - 30 ? 0 : T < SISMA.cono ? (T - SISMA.cono + 30) / 30 : T < SISMA.erutta ? 1 : Math.max(0, 1 - (T - SISMA.erutta) / 90);
    const ruga = (i) => Math.sin(i * 12.9898 + s.seme) * 2.4 * S * s.alto;
    ctx.save();
    if (caldo > 0) {
      // Il bagliore sopra la bocca.
      const R = (56 + (erutta ? 10 * Math.sin(passi * 0.4) : 0)) * S, g = ctx.createRadialGradient(x0, cima, 2 * S, x0, cima, R);
      g.addColorStop(0, "rgba(255,196,84," + (0.6 * caldo).toFixed(3) + ")"); g.addColorStop(1, "rgba(255,110,30,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x0, cima, R, 0, Math.PI * 2); ctx.fill();
    }
    // Il cono: fianchi frastagliati e la bocca incavata.
    const N = 12, punti = [];
    for (let i = 0; i <= N; i++) { const u = 1 - (i / N) * (1 - u0), x = x0 - u * B; punti.push([x, y0 - altoVulcano(x) + (i && i < N ? ruga(i) : 0)]); }
    for (let i = N; i >= 0; i--) { const u = 1 - (i / N) * (1 - u0), x = x0 + u * B; punti.push([x, y0 - altoVulcano(x) + (i && i < N ? ruga(i + 20) : 0)]); }
    ctx.beginPath(); ctx.moveTo(punti[0][0], y0 + 1);
    for (let i = 0; i <= N; i++) ctx.lineTo(punti[i][0], punti[i][1]);
    ctx.quadraticCurveTo(x0, cima + 9 * S * s.alto, punti[N + 1][0], punti[N + 1][1]);
    for (let i = N + 2; i < punti.length; i++) ctx.lineTo(punti[i][0], punti[i][1]);
    ctx.lineTo(punti[punti.length - 1][0], y0 + 1); ctx.closePath();
    const corpo = ctx.createLinearGradient(0, cima, 0, y0);
    corpo.addColorStop(0, "#6a4d3f"); corpo.addColorStop(0.5, "#4a3830"); corpo.addColorStop(1, "#2c2420");
    ctx.fillStyle = corpo; ctx.fill();
    ctx.strokeStyle = "#17120f"; ctx.lineWidth = 1.4 * S; ctx.lineJoin = "round"; ctx.stroke();
    // Le rughe della roccia.
    ctx.strokeStyle = "rgba(20,14,10,.45)"; ctx.lineWidth = 1 * S; ctx.beginPath();
    for (const [lato, u1, u2] of [[-1, 0.3, 0.62], [-1, 0.5, 0.9], [1, 0.26, 0.5], [1, 0.44, 0.84], [1, 0.66, 0.95]]) {
      const xa = x0 + lato * u1 * B, xb = x0 + lato * u2 * B;
      ctx.moveTo(xa, y0 - altoVulcano(xa) + 4 * S * s.alto); ctx.lineTo(xb, y0 - altoVulcano(xb) * 0.35);
    }
    ctx.stroke();
    if (caldo > 0) {
      // Le colate sui fianchi: scendono piano, poi si raffreddano.
      ctx.lineCap = "round"; ctx.lineJoin = "round";
      const rivoli = [[-1, 0.78, 0], [1, 0.56, 40], [1, 0.94, 90], [-1, 0.42, 130]];
      for (const [lato, arriva, ritardo] of rivoli) {
        const p = Math.max(0, Math.min(1, (T - SISMA.cono - ritardo) / 170)) * arriva;
        if (p <= 0.02) continue;
        ctx.beginPath();
        for (let i = 0; i <= 10; i++) {
          const u = u0 * 0.6 + (p - u0 * 0.6) * (i / 10), x = x0 + lato * (u * B + Math.sin(i * 1.7 + ritardo) * 2.2 * S);
          const y = y0 - altoVulcano(x0 + lato * u * B) + 1.6 * S;
          if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
        }
        ctx.globalAlpha = 0.35 + 0.65 * caldo;
        ctx.strokeStyle = caldo > 0.5 ? "#ff6a1a" : "#8f3a1c"; ctx.lineWidth = 4.2 * S; ctx.stroke();
        if (caldo > 0.35) { ctx.strokeStyle = "#ffe27a"; ctx.lineWidth = 1.5 * S; ctx.globalAlpha = caldo; ctx.stroke(); }
      }
      ctx.globalAlpha = caldo;
      // La lava nella bocca.
      const lava = ctx.createLinearGradient(0, cima - 3 * S, 0, cima + 6 * S);
      lava.addColorStop(0, "#fff3b0"); lava.addColorStop(1, "#ff6a1a");
      ctx.fillStyle = lava; ctx.beginPath();
      ctx.ellipse(x0, cima + 3.4 * S * s.alto, bocca * 0.92, (2.6 + (erutta ? 0.8 * Math.sin(passi * 0.5) : 0)) * S, 0, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;
    }
    // I sassi smossi alla base.
    ctx.fillStyle = "#3a2c26"; ctx.strokeStyle = "#17120f"; ctx.lineWidth = 0.9 * S;
    for (let i = 0; i < 6; i++) {
      const lato = i % 2 ? 1 : -1, x = x0 + lato * (0.72 + 0.09 * i) * B * Math.min(1, s.alto * 1.4), r = (2.4 + (i * 7 % 3)) * S * Math.min(1, s.alto * 2);
      ctx.beginPath(); ctx.ellipse(x, y0 - r * 0.6, r * 1.2, r * 0.8, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    ctx.restore();
  }
  // Le pozze di lava lasciate dai lapilli: gialle, poi arancioni, poi roccia.
  function disegnaColate() {
    if (!colate.length) return;
    ctx.save();
    for (const c of colate) {
      const k = c.t / c.vita, nasce = Math.min(1, c.t / 8), rx = c.r * nasce, cy = c.y - 1.4 * S;
      ctx.globalAlpha = k > 0.8 ? Math.max(0, (1 - k) / 0.2) : 1;
      if (k < 0.62) {
        const g = ctx.createRadialGradient(c.x, cy, 1, c.x, cy, rx * 1.9);
        g.addColorStop(0, "rgba(255,150,40," + (0.42 * (1 - k / 0.62)).toFixed(3) + ")"); g.addColorStop(1, "rgba(255,110,30,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(c.x, cy, rx * 1.9, 9 * S, 0, 0, Math.PI * 2); ctx.fill();
      }
      ctx.fillStyle = k < 0.22 ? "#ffd84a" : k < 0.42 ? "#ff8a1a" : k < 0.62 ? "#c8431a" : "#4a3a34";
      ctx.strokeStyle = k < 0.62 ? "#7a2410" : "#241c18"; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.ellipse(c.x, cy, rx, 3 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      if (k < 0.42) { ctx.fillStyle = "#fff3b0"; ctx.beginPath(); ctx.ellipse(c.x + Math.sin(c.seme) * rx * 0.3, cy - 0.4 * S, rx * 0.35, 1.1 * S, 0, 0, Math.PI * 2); ctx.fill(); }
      else if (k < 0.62) { ctx.fillStyle = "#3a2018"; for (const d of [-0.5, 0.1, 0.55]) { ctx.beginPath(); ctx.ellipse(c.x + d * rx, cy + 0.3 * S, rx * 0.16, 0.9 * S, 0, 0, Math.PI * 2); ctx.fill(); } }
    }
    ctx.restore();
  }
  function disegnaLapilli() {
    if (!lapilli.length) return;
    ctx.save(); ctx.lineCap = "round";
    for (const b of lapilli) {
      const n = b.scia.length / 2;
      for (let i = 1; i < n; i++) {
        ctx.strokeStyle = "rgba(255,138,36," + (0.55 * i / n).toFixed(3) + ")"; ctx.lineWidth = b.r * 1.5 * i / n;
        ctx.beginPath(); ctx.moveTo(b.scia[2 * i - 2], b.scia[2 * i - 1]); ctx.lineTo(b.scia[2 * i], b.scia[2 * i + 1]); ctx.stroke();
      }
      ctx.globalAlpha = 0.35; tondo(b.x, b.y, b.r * 2.3, "#ff8a1a");
      ctx.globalAlpha = 1; tondo(b.x, b.y, b.r, "#3a2620");
      tondo(b.x - b.r * 0.15, b.y - b.r * 0.15, b.r * 0.6, "#ff9a2a"); tondo(b.x - b.r * 0.25, b.y - b.r * 0.25, b.r * 0.26, "#fff3b0");
    }
    ctx.restore();
  }

  // --- I METEORITI (05/10/2026, su richiesta) ------------------------------
  // Uno sciame: una decina di sassi infuocati che arrivano di sbieco, tutti
  // dalla stessa parte, e l'ultimo è il più grosso. Ognuno si annuncia con un
  // mirino rosso dove cadrà: chi è sveglio si scansa (o alza la barriera). Dove
  // cadono scoppiano, sbalzano via chi è vicino, bruciano il pavimento e ogni
  // tanto lasciano un sasso ancora caldo, da raccogliere e tirare.
  function avviaMeteore(quanti) {
    sciame = { resta: quanti || Math.round(caso(9, 13)), attesa: 24, inclina: (Math.random() < 0.5 ? -1 : 1) * caso(0.3, 0.55) };
  }
  function nuovaMeteora(grossa) {
    const vivi = lottatori.filter((f) => f.p && !f.esploso && !f.fuori);
    const mira = vivi.length && Math.random() < (grossa ? 0.8 : 0.45) ? vivi[Math.floor(Math.random() * vivi.length)] : null;
    const bx = Math.max(24 * S, Math.min(W - 24 * S, mira ? mira.p.bacino.x + caso(-46, 46) * S * (grossa ? 0.4 : 1) : caso(40 * S, W - 40 * S)));
    const by = verso > 0 && mira && mira.supporto && !(mira.jet > 0) ? mira.supporto.t : pavimento - altoVulcano(bx);
    const ang = (sciame ? sciame.inclina : 0.4) + caso(-0.07, 0.07), v = caso(10, 13.5) * S * (grossa ? 0.8 : 1);
    const vx = Math.sin(ang) * v, vy = Math.cos(ang) * v, n = Math.max(40, Math.round((by + 40 * S) / vy));
    const forma = [];
    for (let i = 0; i < 8; i++) forma.push(caso(0.78, 1.12));
    meteore.push({ x: bx - vx * n, y: by - vy * n, vx, vy, r: (grossa ? 13 : caso(4.6, 8)) * S, bx, by, n, t: 0, grossa: !!grossa,
                   scia: [], rot: caso(0, 6), va: caso(-0.2, 0.2), forma, morta: false });
    // Chi se ne accorge in tempo si scansa.
    for (const f of vivi) {
      if (f.ko || f.preso || f.tenuto || f.fuga) continue;
      if (Math.abs(f.p.bacino.x - bx) < 62 * S && Math.abs(Math.min(pavimento, f.base) - by) < 40 * S &&
          Math.random() < Math.min(0.85, 0.3 * f.furbo + 0.05 * livelloDi(f.tipo))) f.fuga = { x: bx, fino: tempo + n, fatto: false };
    }
  }
  // Un meteorite sta per cadere qui: via di corsa, o barriera per chi ce l'ha.
  const LASCIABILI = { avanza: 1, indietro: 1, provoca: 1, esulta: 1, para: 1, carica: 1, balla: 1 };
  function scappa(f) {
    const q = f.fuga;
    if (tempo >= q.fino) { f.fuga = null; return false; }
    if (q.fatto || (f.azione && !LASCIABILI[f.azione])) return false;
    q.fatto = true;
    const via = f.cx >= q.x ? 1 : -1;
    if (f.jet > 0) { f.meta = Math.max(30 * S, Math.min(W - 30 * S, f.cx + via * 110 * S)); f.pensa = 24; f.azione = null; return true; }
    if (anime && f.ki >= 20 && Math.random() < 0.45) { inizia(f, "barriera"); f.durata = Math.max(30, q.fino - tempo + 12); return true; }
    let meta = f.cx + via * 95 * S;
    if (meta < 26 * S || meta > W - 26 * S) meta = f.cx - via * 95 * S;      // contro il bordo: dall'altra parte
    f.dir = meta >= f.cx ? 1 : -1; f.prendiTel = null; f.dopo = null;
    inizia(f, "avanza", meta); f.corsa = Math.max(20, q.fino - tempo + 10);
    return true;
  }
  function impatto(m, diretto) {
    const pot = m.grossa ? 1.5 : 0.55 + m.r / (16 * S), R = 62 * S * pot, aTerra = Math.abs(m.y - m.by) < 22 * S;
    const x = m.x, y = aTerra ? m.by : m.y;
    m.morta = true;
    scossa = Math.max(scossa, Math.round(6 + 7 * pot)); fermoColpo = Math.max(fermoColpo, m.grossa ? 5 : 2);
    const metti = (q) => { if (particelle.length < MAX_PARTICELLE - 20) particelle.push(q); };
    metti({ tipo: "lampo", x, y, vx: 0, vy: 0, vita: 6, max: 6, r: R * 1.3 });
    metti({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 20, max: 20, colore: "#ffd9a0" });
    for (let i = 0; i < 4 * pot; i++) {
      const a = caso(Math.PI, Math.PI * 2), d = caso(0, 0.3) * R;
      metti({ tipo: "fuoco", x: x + Math.cos(a) * d, y: y + Math.sin(a) * d, vx: Math.cos(a) * caso(0.3, 1.2) * S, vy: Math.sin(a) * caso(0.3, 1.2) * S - 0.5 * S,
              vita: Math.round(caso(14, 24)), max: 24, r: caso(6, 11) * S * pot });
    }
    for (let i = 0; i < 4 * pot; i++) {
      metti({ tipo: "fumo", x: x + caso(-0.3, 0.3) * R, y: y - caso(0, 0.2) * R, vx: caso(-0.5, 0.5) * S, vy: -caso(0.4, 1.1) * S,
              vita: Math.round(caso(40, 70)), max: 70, r: caso(5, 10) * S * pot, colore: Math.random() < 0.5 ? "#6d6a66" : "#8d8a85" });
    }
    for (let i = 0; i < 10 * pot; i++) {
      const a = caso(Math.PI * 1.08, Math.PI * 1.92), v = caso(3, 9) * S * Math.sqrt(pot);
      metti({ tipo: "detrito", x, y: y - 2 * S, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vita: Math.round(caso(60, 110)), max: 110, rot: caso(0, 6),
              va: caso(-0.4, 0.4), lato: caso(1.4, 3.4) * S, colore: ["#3a2c26", "#5a4338", "#7d6a5c"][i % 3] });
    }
    for (let i = 0; i < 8 * pot; i++) {
      const a = caso(Math.PI, Math.PI * 2), v = caso(2, 7) * S;
      metti({ tipo: "brace", x, y: y - 2 * S, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vita: Math.round(caso(30, 60)), max: 60,
              colore: Math.random() < 0.5 ? "#ffb62e" : "#ff6a1a" });
    }
    for (const f of lottatori) {
      if (!f.p || f.esploso || f.fuori || f.preso) continue;
      const b = f.p.bacino, dx = b.x - x, dy = b.y - 14 * S - y, d = Math.hypot(dx, dy) || 1;
      const k = f === diretto ? 1 : Math.max(0, 1 - d / (R * 1.5));
      if (k <= 0) continue;
      const lato = f === diretto ? (Math.sign(m.vx) || 1) : (dx >= 0 ? 1 : -1);
      if (f === diretto || d < R) {
        colpisci(neutro(lato), f, f === diretto ? 4.6 + 2 * pot : 2.6 + 3.4 * k * pot, b.x, b.y - 10 * S, f === diretto ? "SBAM!" : "BOOM!");
        if (f.azione === "barriera") continue;                       // la barriera ha tenuto
        if (cruento && Math.random() < (f === diretto ? 0.3 : 0.12) * pot) smembra(f, x, y);
        if (eMela(f) && Math.random() < 0.3) mordi(f, x, y);
      }
      if (f.tiene) molla(f);
      if (f.tenuto && f.tenuto.da) molla(f.tenuto.da);
      const ux = f === diretto ? lato * 0.8 : dx / d, uy = (f === diretto ? 0 : dy / d) - 0.7;
      for (const n in f.p) { f.p[n].ox -= ux * 10 * S * k * Math.sqrt(pot); f.p[n].oy -= uy * 8 * S * k; }
      if (k > 0.35) { f.inVolo = true; f.ko = Math.max(f.ko, 34); f.jet = 0; f.caos = 0; f.paracadute = 0; f.scalata = null; }
    }
    for (const t of telefoni) {
      if (t.stato === "portato" || t.stato === "impugnato" || t.stato === "preso") continue;
      const dx = t.x - x, dy = t.y - y, d = Math.hypot(dx, dy) || 1;
      if (d > R * 1.6) continue;
      const k = 1 - d / (R * 1.6);
      t.ox = t.x - dx / d * 9 * S * k; t.oy = t.y - (dy / d - 0.7) * 9 * S * k; t.va += caso(-0.4, 0.4);
    }
    for (const pz of pezzi.concat(arti)) {
      const dx = pz.x - x, dy = pz.y - y, d = Math.hypot(dx, dy) || 1;
      if (d < R * 1.6) { const k = 1 - d / (R * 1.6); pz.ox = pz.x - dx / d * 8 * S * k; pz.oy = pz.y - (dy / d - 0.6) * 8 * S * k; }
    }
    if (orda) for (const z of orda.zombie) if (vivoZ(z) && Math.hypot(z.x - x, corpoZ(z)[1] - y) < R) colpisciZombie(z, 9, z.x >= x ? 1 : -1, z.x, corpoZ(z)[1], null);
    if (!aTerra) return;
    bruciature.push({ x, y: m.by, r: 15 * S * pot, t: 0 });
    if (bruciature.length > 10) bruciature.shift();
    if (m.by >= pavimento - 2) danneggiaStriscia(x, m.grossa ? 0.95 : 0.55);
    if (m.grossa) scrivi("KA-BOOOM!", x, Math.max(60, y - 50 * S), true);
    // Ogni tanto resta un sasso ancora caldo: si raccoglie e si tira.
    else if (Math.random() < 0.4 && telefoni.filter((t) => t.tipo === "sasso").length < 2) {
      const t = nuovoTelefono(x, y - 8 * S, caso(-2, 2) * S, -caso(2, 4.5) * S, "sasso");
      t.caldo = 1; t.cool = 30;
    }
  }
  function aggiornaMeteore() {
    if (sciame && --sciame.attesa <= 0) {
      nuovaMeteora(sciame.resta === 1);
      sciame.attesa = Math.round(caso(16, 44));
      if (--sciame.resta <= 0) sciame = null;
    }
    for (const m of meteore) {
      m.t++; m.x += m.vx; m.y += m.vy; m.rot += m.va;
      if (passi % 2 === 0) { m.scia.push(m.x, m.y); if (m.scia.length > 18) m.scia.splice(0, 2); }
      if (passi % 3 === 0 && particelle.length < MAX_PARTICELLE - 60) {
        particelle.push({ tipo: "brace", x: m.x + caso(-1, 1) * m.r, y: m.y + caso(-1, 1) * m.r, vx: -m.vx * 0.15 + caso(-0.6, 0.6) * S, vy: -m.vy * 0.15,
                          vita: Math.round(caso(14, 26)), max: 26, colore: Math.random() < 0.5 ? "#ffb62e" : "#ff6a1a" });
      }
      let diretto = null;
      for (const f of lottatori) {
        if (!f.p || f.esploso || f.fuori || f.preso) continue;
        for (const n of ["testa", "collo", "bacino"]) {
          if (Math.hypot(f.p[n].x - m.x, f.p[n].y - m.y) < f.p[n].r + m.r + 2 * S) { diretto = f; break; }
        }
        if (diretto) break;
      }
      if (diretto || m.y >= m.by - m.r * 0.5 || m.t > m.n + 40) impatto(m, diretto);
    }
    if (meteore.some((m) => m.morta)) meteore = meteore.filter((m) => !m.morta);
    for (const q of bruciature) {
      q.t++;
      if (q.t < 110 && q.t % 16 === 0 && particelle.length < MAX_PARTICELLE - 80) {
        particelle.push({ tipo: "fumo", x: q.x + caso(-0.5, 0.5) * q.r, y: q.y - 4 * S, vx: caso(-0.2, 0.2) * S, vy: -caso(0.4, 0.9) * S,
                          vita: 50, max: 50, r: caso(3, 6) * S, colore: "#8d8a85" });
      }
    }
    if (bruciature.length && bruciature[0].t > 520) bruciature = bruciature.filter((q) => q.t <= 520);
  }
  // Il mirino dove cadrà un meteorite, e il segno bruciato che lascia.
  function disegnaMirini() {
    if (!meteore.length && !bruciature.length) return;
    ctx.save();
    for (const q of bruciature) {
      const a = Math.min(1, (520 - q.t) / 160);
      ctx.globalAlpha = 0.5 * a; ctx.fillStyle = "#1c1612";
      ctx.beginPath(); ctx.ellipse(q.x, q.y - 1.2 * S, q.r, 3.2 * S, 0, 0, Math.PI * 2); ctx.fill();
      if (q.t < 150) {
        ctx.globalAlpha = (1 - q.t / 150) * 0.9; ctx.fillStyle = "#ff8a1a";
        ctx.beginPath(); ctx.ellipse(q.x, q.y - 1.2 * S, q.r * 0.5, 1.6 * S, 0, 0, Math.PI * 2); ctx.fill();
      }
    }
    for (const m of meteore) {
      const k = Math.min(1, m.t / m.n), r = (m.grossa ? 34 : 22) * S * (1.25 - 0.55 * k), luce = 0.5 + 0.35 * Math.sin(m.t * 0.55);
      ctx.globalAlpha = 1;
      ctx.fillStyle = "rgba(226,60,30," + (0.1 + 0.2 * k).toFixed(3) + ")";
      ctx.beginPath(); ctx.ellipse(m.bx, m.by - 1.5 * S, r, r * 0.26, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "rgba(226,60,30," + luce.toFixed(3) + ")"; ctx.lineWidth = 1.7 * S; ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(m.bx - r * 1.25, m.by - 1.5 * S); ctx.lineTo(m.bx - r * 0.7, m.by - 1.5 * S);
      ctx.moveTo(m.bx + r * 0.7, m.by - 1.5 * S); ctx.lineTo(m.bx + r * 1.25, m.by - 1.5 * S);
      ctx.stroke();
    }
    ctx.restore();
  }
  function disegnaMeteore() {
    if (!meteore.length) return;
    ctx.save(); ctx.lineCap = "round";
    for (const m of meteore) {
      // La scia di fuoco: larga vicino al sasso, a punta in fondo.
      const n = m.scia.length / 2;
      for (let i = 1; i < n; i++) {
        const k = i / n;
        ctx.strokeStyle = "rgba(255," + Math.round(120 + 90 * k) + ",40," + (0.6 * k).toFixed(3) + ")"; ctx.lineWidth = m.r * 2 * k;
        ctx.beginPath(); ctx.moveTo(m.scia[2 * i - 2], m.scia[2 * i - 1]); ctx.lineTo(m.scia[2 * i], m.scia[2 * i + 1]); ctx.stroke();
      }
      if (n) {
        ctx.strokeStyle = "rgba(255,240,180,.8)"; ctx.lineWidth = m.r * 0.6;
        ctx.beginPath(); ctx.moveTo(m.scia[Math.max(0, 2 * n - 8)], m.scia[Math.max(1, 2 * n - 7)]); ctx.lineTo(m.x, m.y); ctx.stroke();
      }
      ctx.globalAlpha = 0.4; tondo(m.x, m.y, m.r * 2.1, "#ff8a1a"); ctx.globalAlpha = 1;
      ctx.save(); ctx.translate(m.x, m.y); ctx.rotate(m.rot);
      ctx.fillStyle = "#3a2c26"; ctx.strokeStyle = "#17120f"; ctx.lineWidth = 1 * S; ctx.lineJoin = "round"; ctx.beginPath();
      m.forma.forEach((q, i) => { const a = (i / m.forma.length) * Math.PI * 2; ctx[i ? "lineTo" : "moveTo"](Math.cos(a) * m.r * q, Math.sin(a) * m.r * q); });
      ctx.closePath(); ctx.fill(); ctx.stroke();
      tondo(m.r * 0.2, -m.r * 0.25, m.r * 0.22, "#241c18"); tondo(-m.r * 0.35, m.r * 0.2, m.r * 0.16, "#241c18");
      ctx.restore();
      // Il fronte incandescente, dalla parte in cui va.
      const a = Math.atan2(m.vy, m.vx);
      ctx.strokeStyle = "#ffe27a"; ctx.lineWidth = 1.6 * S; ctx.beginPath(); ctx.arc(m.x, m.y, m.r * 1.05, a - 1.1, a + 1.1); ctx.stroke();
    }
    ctx.restore();
  }

  // --- L'ORDA DI ZOMBIE (05/10/2026, su richiesta) --------------------------
  // Un imprevisto che cambia le parti: dal pavimento spuntano gli zombie, a
  // ondate, dai due lati. I due lottatori fanno TREGUA: smettono di colpirsi
  // (i colpi dell'uno non fanno più niente all'altro), si mettono spalle a
  // spalla e ognuno tiene il suo lato. SI COPRONO: chi ha il lato libero si
  // volta ad aiutare l'altro se uno zombie gli è addosso; se l'alleato va a
  // terra lo si raggiunge, lo si difende da tutti e due i lati e lo si aiuta
  // a rialzarsi prima. Finita l'orda si danno il cinque, e si ricomincia.
  // I morsi degli zombie non contano per i K.O. della partita né per le
  // scommesse: stordiscono, e al terzo buttano a terra per un po'.
  //
  // LE ONDATE (05/10/2026, su richiesta): l'orda è una serie di ondate, ognuna
  // GENERATA sul momento da una ricetta (`ricettaOndata`): un tema che decide
  // di che tipo sono (mista, sciame di svelti, striscianti, pesante, gonfia),
  // un punteggio da spendere che cresce a ogni ondata, da che parte arrivano
  // (dai due lati, da uno solo, a tenaglia, a gruppi) e con che ritmo. I tipi
  // si sbloccano man mano: i LENTI dalla prima; gli SVELTI (un colpo e vanno
  // giù, ma mordono in fretta) e gli STRISCIANTI (bassi: i pugni dritti gli
  // passano sopra, ci vogliono calci e colpi in giù) dalla seconda; i GONFI
  // (scoppiando stendono gli zombie vicini e fanno tossire chi è lì) dalla
  // terza; i GROSSI (sei colpi, e con una manata buttano a terra) dalla quarta.
  // L'orda a sorpresa dura tre ondate. Quella chiamata dalla tendina va avanti
  // finché i due reggono (o finché non la si ferma dallo stesso tasto): finisce
  // quando sono a terra tutti e due insieme. Resta il primato delle ondate superate.
  //
  // Tre ritocchi del 05/10/2026, dopo la prima prova di Riccardo («non arriva
  // mai», «c'è solo la prima ondata»):
  //  - L'ORDA HA IL SUO OROLOGIO. Non si pesca più fra gli imprevisti (uno su
  //    dieci, e non prima di due minuti e mezzo: in pratica non arrivava). La
  //    prima arriva fra un minuto e mezzo e due e dieci di lotta, poi una ogni
  //    quattro-sei minuti.
  //  - TRE VITE. Con tutti e due a terra l'orda finiva subito, spesso già alla
  //    seconda ondata. Ora le prime due volte i due si rialzano di scatto e
  //    l'urto butta indietro gli zombie; alla terza l'orda ha vinto. Le vite
  //    sono i cuori accanto al conto dell'ondata.
  //  - L'ORDA SEGUE I DUE. Restava legata al piano dov'era cominciata: buttati
  //    giù da un elemento della pagina, i due restavano sotto e gli zombie
  //    sopra, fermi, fino allo scadere dell'ondata (40 secondi). Ora, se per
  //    un secondo nessuno dei due è più su quel piano, gli zombie affondano e
  //    rispuntano dove stanno loro.
  const ORDA = { sorpresa: 3, pausa: 150, festa: 150, limite: 2400, vite: 3, prima: [90, 130], poi: [240, 360] };
  let prossimaOrda = 0;
  const ZOMBI = {
    lento: { costo: 1, hp: 2, vel: [0.6, 0.95], scala: 1, dal: 1, carica: 22, portata: 27 },
    svelto: { costo: 1.5, hp: 1, vel: [1.7, 2.2], scala: 0.9, dal: 2, carica: 14, portata: 25 },
    striscia: { costo: 1.2, hp: 1, vel: [0.75, 1], scala: 1, dal: 2, carica: 20, portata: 30 },
    gonfio: { costo: 2, hp: 2, vel: [0.5, 0.7], scala: 1.1, dal: 3, carica: 26, portata: 27 },
    grosso: { costo: 4, hp: 6, vel: [0.38, 0.5], scala: 1.36, dal: 4, carica: 30, portata: 34 },
    // Le varianti potenziate della corsa (09/10/2026): nel ring libero non escono mai (`dal` 99).
    // Il corazzato ha elmo e piastra e i colpi deboli gli fanno metà; il rabbioso è rosso e
    // corre; il capo è il boss: enorme, lento, e la sua manata butta giù.
    corazzato: { costo: 2.5, hp: 4, vel: [0.55, 0.75], scala: 1.05, dal: 99, carica: 24, portata: 28 },
    rabbioso: { costo: 2, hp: 2, vel: [2.3, 2.8], scala: 0.95, dal: 99, carica: 12, portata: 26 },
    capo: { costo: 20, hp: 20, vel: [0.42, 0.5], scala: 1.9, dal: 99, carica: 34, portata: 46 },
  };
  const pesante = (z) => z.tipo === "grosso" || z.tipo === "capo";
  const TEMI_ONDATA = {
    mista: { lento: 5, svelto: 2, striscia: 2, gonfio: 1.5, grosso: 1 },
    sciame: { lento: 1, svelto: 6 },
    strisciante: { lento: 2, striscia: 6 },
    gonfia: { lento: 2, gonfio: 5, svelto: 1 },
    pesante: { lento: 3, grosso: 4, gonfio: 1 },
  };
  const ARRIVI = ["lati", "lati", "sinistra", "destra", "tenaglia", "gruppi"];
  const TONI_ZOMBIE = [["#7d8fa6", "#4b5a70"], ["#a08670", "#6a5444"], ["#7a9a78", "#4a6a4c"], ["#9a7da0", "#644a6a"]];
  let orda = null, primatoOrda = 0;
  try { const v = parseInt(deposito.getItem("mut-ring-corsa"), 10); if (Number.isFinite(v) && v > 0) recordCorsa = v; } catch (errore) { /* da zero */ }
  try { const v = parseInt(deposito.getItem("mut-ring-ondate"), 10); if (Number.isFinite(v) && v > 0 && v < 1000) primatoOrda = v; } catch (errore) { /* si parte da zero */ }
  const tregua = () => !!orda;
  // Un generatore di numeri a caso col seme: la stessa orda (stesso seme) dà le stesse ondate.
  function generatore(seme) {
    let a = seme >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  // La ricetta di un'ondata: chi arriva, da dove, quando.
  function ricettaOndata(n, rng) {
    const fra = (a, b) => a + rng() * (b - a), pesca = (voci) => voci[Math.floor(rng() * voci.length)];
    const aperti = Object.keys(ZOMBI).filter((t) => ZOMBI[t].dal <= n);
    const temi = Object.keys(TEMI_ONDATA).filter((t) => t === "mista" || Object.keys(TEMI_ONDATA[t]).some((k) => k !== "lento" && aperti.indexOf(k) >= 0 && TEMI_ONDATA[t][k] >= 4));
    const tema = n === 1 ? "mista" : pesca(temi), pesi = TEMI_ONDATA[tema];
    let punti = Math.min(40, n === 1 ? 6 : 5 + 3 * n), grossi = 0;
    const tipi = [];
    while (punti >= 1 && tipi.length < 34) {
      const scelta = aperti.filter((t) => pesi[t] && ZOMBI[t].costo <= punti && (t !== "grosso" || grossi < 1 + Math.floor(n / 4)));
      let tipo = "lento";
      if (scelta.length) {
        let tot = 0; for (const t of scelta) tot += pesi[t];
        let r = rng() * tot;
        for (const t of scelta) { tipo = t; if ((r -= pesi[t]) <= 0) break; }
      }
      if (tipo === "grosso") grossi++;
      tipi.push(tipo); punti -= ZOMBI[tipo].costo;
    }
    // Mescolati; il grosso, se c'è, non arriva per primo.
    for (let i = tipi.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); const t = tipi[i]; tipi[i] = tipi[j]; tipi[j] = t; }
    if (tipi[0] === "grosso" && tipi.length > 1) { tipi[0] = tipi[tipi.length - 1]; tipi[tipi.length - 1] = "grosso"; }
    const arrivo = n === 1 ? "lati" : pesca(ARRIVI), passo = Math.max(18, 62 - 4 * n);
    let lato = rng() < 0.5 ? -1 : 1;
    const coda = tipi.map((tipo, i) => {
      let attesa = Math.round(passo * fra(0.6, 1.4));
      if (arrivo === "lati") lato = -lato;
      else if (arrivo === "sinistra" || arrivo === "destra") lato = rng() < 0.85 ? (arrivo === "sinistra" ? -1 : 1) : (arrivo === "sinistra" ? 1 : -1);
      else if (arrivo === "tenaglia") { lato = -lato; if (i % 2) attesa = 4; else attesa = Math.round(passo * fra(1.2, 1.9)); }
      else { if (i % 3 === 0) { lato = rng() < 0.5 ? -1 : 1; attesa = Math.round(passo * fra(2, 3)); } else attesa = Math.round(fra(8, 16)); }
      return { tipo, lato, attesa: i ? attesa : 30 };
    });
    return { n, tema, arrivo, coda, totale: coda.length, insieme: Math.min(10, 4 + n) };
  }
  function avviaOrda(ondate, seme) {
    // Nella corsa si combatte da soli: chi è in panchina non conta.
    const inCampo = lottatori.filter((l) => !l.fuoriCampo), a = inCampo[0], b = inCampo[1] || inCampo[0];
    if (orda || !a || !b) return;
    // Dove si combatte: l'elemento su cui stanno tutti e due, se è largo; sennò il pavimento.
    const oa = verso > 0 && !(a.jet > 0) ? appoggio(a)[1] : null, ob = verso > 0 && !(b.jet > 0) ? appoggio(b)[1] : null;
    const o = oa && oa === ob && oa.r - oa.l > 320 * S ? oa : null;
    const sx = a.p.bacino.x <= b.p.bacino.x ? a : b, dx = sx === a ? b : a;
    seme = seme || Math.floor(Math.random() * 1e9) + 1;
    orda = { t: 0, fase: "pausa", pausa: 36, festa: 0, su: !!o, base: o ? o.t : pavimento, l: o ? o.l : 0, r: o ? o.r : W, zombie: [],
             ondata: 0, ondate: ondate || 0, superate: 0, ricetta: null, tOndata: 0, seme, rng: generatore(seme), prossimo: 0, nati: 0, uccisi: 0, uccisiOndata: 0,
             sopraffatti: 0, vite: ORDA.vite, altrove: 0, coppiaAttesa: 110, coppie: {}, lati: { [sx.tipo]: -1, [dx.tipo]: 1 }, cx: (a.cx + b.cx) / 2, vinta: false };
    if (sfida) { sfida = null; sfidaPausa = 40; }
    for (const f of [a, b]) {
      if (f.tiene) molla(f);
      if (f.tenuto && f.tenuto.tele !== undefined) { f.tenuto = null; f.ko = Math.max(f.ko, 30); f.inVolo = true; }
      f.onda = null; f.scatto = 0; f.insegui = 0; f.combo = 0; f.morsiZ = 0; f.zMira = null; f.cinque = true; f.daBallare = false; f.ordine = null;
      if (!f.ko && !f.esploso && !f.preso) { f.azione = null; f.pensa = 14; f.durata = 0; }
    }
    if (!corsa) scrivi("TREGUA!", (a.p.testa.x + b.p.testa.x) / 2, Math.min(a.p.testa.y, b.p.testa.y) - 26 * S, false);
  }
  function nuovaOndata() {
    const q = orda;
    q.ondata++; q.fase = "lotta"; q.tOndata = 0; q.uccisiOndata = 0; q.sopraffatti = 0;
    q.ricetta = q.corsa || ricettaOndata(q.ondata, q.rng);
    q.prossimo = q.ricetta.coda[0].attesa;
    for (const f of lottatori) f.cinque = false;
    // Che ne comincia un'altra si deve vedere: il numero, piccolo, sopra i due.
    if (q.ondata > 1 && !corsa) scrivi(dici("Ondata") + " " + q.ondata, q.cx, q.base - 84 * S, false);
  }
  // Tutti e due a terra, ma una vita c'è ancora: su di scatto, e l'urto butta indietro gli zombie vicini.
  function riscossa() {
    const q = orda;
    q.sopraffatti = 0;
    let somma = 0, n = 0;
    for (const f of lottatori) {
      if (!f.p || f.esploso || f.fuori) continue;
      f.ko = Math.min(f.ko, 6); f.morsiZ = 0; f.stordito = 0; f.dolore = 0; f.pensa = 12;
      somma += f.p.bacino.x; n++;
    }
    const x = n ? somma / n : q.cx, y = q.base - 26 * S;
    for (const z of q.zombie) {
      if (z.stato === "giu" || Math.abs(z.x - x) > 190 * S) continue;
      z.vx = (z.x >= x ? 1 : -1) * 10 * S; z.botta = 80; z.lampo = 10;
      if (z.stato === "colpo") { z.stato = "va"; z.s = 0; }
    }
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 18, max: 18, colore: "#ffffff" });
    scintille(x, y, 16, "#ffe27a");
    scrivi("SU!", x, y - 44 * S, false);
    scossa = Math.max(scossa, 8);
  }
  // L'orda va dove stanno i due: gli zombie affondano dov'erano e rispuntano sul loro piano.
  function traslocaOrda(chi) {
    const q = orda;
    // Il piano più basso fra quelli dove stanno; un elemento stretto non basta, si combatte a terra.
    let f = chi[0];
    for (const l of chi) if (l.base > f.base) f = l;
    const o = appoggio(f)[1], largo = o && o.r - o.l > 320 * S ? o : null, base = largo ? largo.t : pavimento;
    q.altrove = -120;
    if (Math.abs(base - q.base) < 8 * S) return;                 // è già lì: saranno loro a scendere
    for (const z of q.zombie) if (z.stato !== "giu") polvere(z.x, q.base - 2, 3);
    q.base = base; q.su = !!largo; q.l = largo ? largo.l : 0; q.r = largo ? largo.r : W;
    q.cx = Math.max(q.l + 40 * S, Math.min(q.r - 40 * S, chi.reduce((t, l) => t + l.p.bacino.x, 0) / chi.length));
    q.zombie = q.zombie.filter((z) => z.stato !== "giu");
    for (const z of q.zombie) {
      z.x = Math.max(q.l + 8 * S, Math.min(q.r - 8 * S, q.cx + z.lato * caso(130, 300) * S));
      z.stato = "esce"; z.s = 0; z.vx = 0; z.botta = 0; z.dir = -z.lato;
      polvere(z.x, q.base - 1, 4);
    }
    q.traslochi = (q.traslochi || 0) + 1;
  }
  function fineOndata() {
    const q = orda;
    q.superate = q.ondata;
    if (!q.ondate && q.superate > primatoOrda) {
      primatoOrda = q.superate;
      try { deposito.setItem("mut-ring-ondate", String(primatoOrda)); } catch (errore) { /* pazienza */ }
    }
    for (const f of lottatori) { f.morsiZ = 0; if (anime && !f.esploso) f.ki = Math.min(100, f.ki + 20); }
    if (q.ondate && q.ondata >= q.ondate) { fineOrda(true); return; }
    q.fase = "pausa"; q.pausa = ORDA.pausa;
  }
  function nuovoZombie(tipo, lato) {
    const q = orda, Z = ZOMBI[tipo] || ZOMBI.lento;
    // Dal terreno, a qualche passo dai due (non dal bordo della finestra: ci metterebbero una vita).
    const x = Math.max(q.l + 8 * S, Math.min(q.r - 8 * S, q.cx + lato * caso(150, 330) * S));
    // Dalla nona ondata in poi sono più svelti, e ogni quattro ondate reggono un colpo in più.
    // (nella corsa l'ondata è sempre la prima: conta il round)
    const oltre = Math.max(0, corsa && corsa.chi ? corsa.round - 3 : q.ondata - 8), svelti = Math.min(1.8, 1 + 0.05 * oltre);
    q.zombie.push({ x, lato, dir: -lato, tipo: ZOMBI[tipo] ? tipo : "lento", t: 0, s: 0, stato: "esce", hp: Z.hp + Math.floor(oltre / 4), vel: caso(Z.vel[0], Z.vel[1]) * svelti,
                    tono: Math.floor(Math.random() * TONI_ZOMBIE.length), fase: caso(0, 6), vx: 0, botta: 0, lampo: 0, cade: 0, occhio: Math.random() < 0.5 ? 1 : -1 });
    q.nati++;
    polvere(x, q.base - 1, 4);
    const z = q.zombie[q.zombie.length - 1];
    if (z.tipo === "capo") {
      z.x = Math.max(q.l + 60 * S, Math.min(q.r - 60 * S, z.x));             // è largo: dentro la finestra per intero
      z.hp = z.hpMax = 18 + 3 * (corsa ? corsa.round : 1);
      scossa = Math.max(scossa, 14); polvere(x, q.base - 1, 14);
      scrivi(dici("Il capo") + "!", x, q.base - 140 * S, true);
    }
  }
  const vivoZ = (z) => !z.inBuco && (z.stato === "va" || z.stato === "colpo" || (z.stato === "esce" && z.s > 22));
  // Lo zombie vivo più vicino a un punto, entro un raggio; `lato` (facoltativo) chiede quelli da una parte sola.
  function zombieVicino(x, raggio, lato) {
    let scelto = null, d0 = raggio;
    if (!orda) return null;
    for (const z of orda.zombie) {
      if (!vivoZ(z) || (lato && (z.x - x) * lato < 0)) continue;
      const d = Math.abs(z.x - x);
      if (d < d0) { d0 = d; scelto = z; }
    }
    return scelto;
  }
  // Dove stanno petto e testa di uno zombie: [x, y, raggio, x, y, raggio]. Lo strisciante è basso.
  function corpoZ(z) {
    const sc = ZOMBI[z.tipo].scala, b = orda.base;
    if (z.tipo === "striscia") return [z.x, b - 9 * S, 9 * S, z.x + z.dir * 14 * S, b - 13 * S, 7 * S];
    return [z.x, b - 34 * S * sc, 10 * S * sc, z.x + z.dir * 2 * S, b - 52 * S * sc, 8 * S * sc];
  }
  // Lo zombie toccato da un punto (un pugno, una pallottola, un oggetto), se c'è.
  function zombieToccato(x, y, r) {
    if (!orda) return null;
    for (const z of orda.zombie) {
      if (!vivoZ(z)) continue;
      const c = corpoZ(z);
      if (Math.hypot(c[0] - x, c[1] - y) < c[2] + r || Math.hypot(c[3] - x, c[4] - y) < c[5] + r) return z;
    }
    return null;
  }
  function colpisciZombie(z, forza, dir, x, y, da) {
    if (!orda || !vivoZ(z)) return false;
    const grosso = pesante(z), forte = forza >= 4.4;
    // Nella corsa: i pugni pesanti dell'eroe contano di più, la corazza ferma metà dei colpi deboli.
    const molt = (corsa && corsa.chi && da && da.tipo === corsa.chi ? forzaCorsa() : 1) * (z.tipo === "corazzato" && !forte ? 0.5 : 1);
    z.hp -= (forte ? 2 : 1) * molt; z.lampo = 5; z.s = 0;
    // Il grosso barcolla solo ai colpi forti, e quasi non si sposta.
    z.botta = grosso ? (forte ? 12 : 3) : 18;
    z.vx = dir * Math.min(8, 2.5 + forza) * 0.55 * S * (grosso ? 0.3 : 1);
    scintille(x, y, 7, "#ffe27a");
    fermoColpo = Math.max(fermoColpo, 2);
    if (z.hp > 0) { z.stato = "va"; scrivi(SUONI[Math.floor(Math.random() * SUONI.length)], x, y - 8 * S, false); return true; }
    z.stato = "giu"; z.cade = dir || 1; orda.uccisi++; orda.uccisiOndata++;
    if (corsa) corsaUcciso(z);
    schegge(x, y, 5, TONI_ZOMBIE[z.tono][0]);
    if (cruento) {
      for (let i = 0; i < 4 && particelle.length < MAX_PARTICELLE; i++) {
        const a = caso(-Math.PI, 0), v = caso(1.5, 3.5) * S;
        particelle.push({ tipo: "goccia", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vita: 90, max: 90, r: caso(0.9, 1.8) * S, colore: "#7fae4a" });
      }
    }
    scrivi("SPLAT!", x, y - 8 * S, false);
    if (da && da.p && anime) da.ki = Math.min(100, da.ki + 6);
    if (z.tipo === "gonfio") scoppioGonfio(z);
    return true;
  }
  // Il gonfio scoppia: una nube verde che stende gli zombie vicini e fa tossire chi c'è dentro.
  function scoppioGonfio(z) {
    const c = corpoZ(z), x = c[0], y = c[1], R = 58 * S;
    for (let i = 0; i < 9 && particelle.length < MAX_PARTICELLE - 20; i++) {
      particelle.push({ tipo: "fumo", x: x + caso(-0.5, 0.5) * R, y: y + caso(-0.4, 0.3) * R, vx: caso(-0.9, 0.9) * S, vy: -caso(0.2, 0.9) * S,
                        vita: Math.round(caso(46, 76)), max: 76, r: caso(8, 15) * S, colore: Math.random() < 0.5 ? "#9fce5a" : "#c4e58a" });
    }
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 16, max: 16, colore: "#b6e36a" });
    scrivi("PUFF!", x, y - 26 * S, false);
    scossa = Math.max(scossa, 6);
    for (const w of orda.zombie) if (w !== z && vivoZ(w) && Math.abs(w.x - x) < R) colpisciZombie(w, 5, w.x >= x ? 1 : -1, w.x, corpoZ(w)[1], null);
    for (const f of lottatori) {
      if (!f.p || f.esploso || f.ko > 0 || f.preso || f.azione === "barriera") continue;
      if (Math.abs(f.p.bacino.x - x) < R * 0.8 && Math.abs(f.p.bacino.y - y) < 60 * S) {
        if (!(f.accecato > 0)) scrivi("COFF!", f.p.testa.x, f.p.testa.y - 18 * S, false);
        f.accecato = Math.max(f.accecato, 50);
      }
    }
  }
  // Il morso: non è un colpo della partita. Stordisce, spinge, e al terzo butta a terra.
  // La manata del grosso butta a terra subito.
  function morso(z, f) {
    if (f.coppia || f.riparo > 0) return;              // a metà di una mossa in coppia (e un attimo dopo) non lo prendono
    const x = (z.x + f.p.collo.x) / 2, y = f.p.collo.y + 4 * S, grosso = pesante(z);
    if (f.azione === "para" && f.dir === -z.dir) {
      scintille(x, y, 5, "#bfe9ff"); scrivi("PARATO!", x, y - 8 * S, false);
      z.botta = 22; z.vx = -z.dir * 2.4 * S;
      if (grosso) for (const n in f.p) f.p[n].ox -= z.dir * 4 * S;
      return;
    }
    if (barrieraRegge(f, grosso ? 5 : 2.4, x, y)) { z.botta = 30; z.vx = -z.dir * 4 * S; return; }
    // Nella corsa il morso toglie vita alla corsa; se ha tolto una vita, l'eroe va giù.
    if (corsa && corsa.chi && f.tipo === corsa.chi) {
      if (corsa.invuln > 0 || corsa.scudo > 0) { z.botta = 24; z.vx = -z.dir * 3 * S; scintille(x, y, 5, "#bfe9ff"); return; }
      if (feritaEroe(MORSO_CORSA[z.tipo] || 8, x, y)) f.morsiZ = 2;
      if (z.tipo === "capo") { scossa = Math.max(scossa, 12); if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: z.x, y: orda.base - 4 * S, vx: 0, vy: 0, vita: 18, max: 18, colore: "#c9a0ff" }); }
    }
    f.morsiZ = (f.morsiZ || 0) + 1;
    scintille(x, y, 6, "#b6e36a");
    scrivi(grosso ? "SBAM!" : ["GNAM!", "GRAH!", "CHOMP!"][f.morsiZ % 3], x, y - 10 * S, false);
    for (const n in f.p) f.p[n].ox -= z.dir * (grosso ? 7 : 2.6) * S;
    f.dolore = 22; f.azione = null; f.stordito = Math.max(f.stordito, 12); f.scalata = null; f.ordine = null;
    if (f.tel) lasciaCadere(f);
    if (f.gelato > 0) rompiGhiaccio(f, true);
    segna(f, x, y, 2.4); schizza(f, x, y, 1, 0.6);
    fermoColpo = Math.max(fermoColpo, grosso ? 4 : 2);
    if (grosso || f.morsiZ % 3 === 0) {
      // A terra per un po' (l'alleato arriva a coprire).
      for (const n in f.p) { f.p[n].ox -= z.dir * 3 * S; f.p[n].oy += verso * 2 * S; }
      f.ko = Math.max(f.ko, grosso ? 90 : 110); f.inVolo = true; f.jet = 0;
      if (f.arma) lasciaArma(f);
      if (grosso) scossa = Math.max(scossa, 8);
    }
  }
  function fineOrda(vinta) {
    const q = orda;
    q.fase = "festa"; q.festa = 0; q.vinta = vinta;
    if (q.ricetta) q.ricetta.coda = [];
    // Quelli rimasti si sbriciolano.
    for (const z of q.zombie) if (z.stato !== "giu") { z.stato = "giu"; z.s = 0; z.cade = -z.dir; polvere(z.x, q.base - 20 * S, 4); }
    for (const f of lottatori) { f.zMira = null; f.cinque = false; f.ordine = null; if (!f.ko && !f.esploso && !f.preso && !f.tenuto) { f.azione = null; f.pensa = 6; } }
  }
  function aggiornaOrda() {
    const q = orda;
    if (!q) return;
    q.t++;
    if (q.coppiaAttesa > 0) q.coppiaAttesa--;
    if (q.fase === "lotta") q.senzaCoppia = (q.senzaCoppia || 0) + 1;
    const [a, b] = lottatori;
    if (q.fase === "pausa") { if (--q.pausa <= 0) nuovaOndata(); }
    else if (q.fase === "lotta") {
      const R = q.ricetta, vivi = q.zombie.reduce((n, z) => n + (z.stato !== "giu" ? 1 : 0), 0);
      if (R.coda.length && vivi < R.insieme && --q.prossimo <= 0) {
        const v = R.coda.shift();
        nuovoZombie(v.tipo, v.lato);
        q.prossimo = R.coda.length ? R.coda[0].attesa : 0;
      }
      if (!R.coda.length && vivi === 0) fineOndata();
      else if (++q.tOndata > (corsa ? 7200 : ORDA.limite)) {
        // Troppo lunga: quelli rimasti si sbriciolano e si passa oltre.
        R.coda = [];
        for (const z of q.zombie) if (z.stato !== "giu") { z.stato = "giu"; z.s = 0; z.cade = -z.dir; polvere(z.x, q.base - 20 * S, 4); }
        fineOndata();
      }
      // Sopraffatti: a terra tutti e due insieme per un secondo e mezzo. Le
      // prime volte ci si rialza di scatto; finite le vite, l'orda ha vinto.
      if (orda === q && q.fase === "lotta" && !corsa) {
        q.sopraffatti = lottatori.every((f) => f.ko > 0 || f.esploso) ? q.sopraffatti + 1 : 0;
        if (q.sopraffatti > 90) { if (--q.vite > 0) riscossa(); else fineOrda(false); }
      }
    } else if (++q.festa > ORDA.festa) {
      // Fine della tregua: si torna a picchiarsi.
      orda = null;
      if (evento && evento.nome === "zombie") fineEvento();
      prossimaOrda = Math.max(prossimaOrda, Math.round(caso(ORDA.poi[0], ORDA.poi[1]) * 60));     // la prossima non subito
      for (const f of lottatori) { f.zMira = null; f.cinque = false; f.pensa = Math.round(caso(20, 50)); }
      return;
    }
    // L'orda segue i due: se per un secondo nessuno di quelli in piedi sta più sul suo piano, trasloca.
    if (q.fase !== "festa" && verso > 0) {
      const inPiedi = lottatori.filter((f) => f.p && !f.esploso && !f.fuori && !f.fuoriCampo && !(f.ko > 0) && !f.preso && !f.tenuto && !(f.jet > 0) && !f.inVolo && !f.scalata);
      if (q.altrove < 0) q.altrove++;
      else if (inPiedi.length && !inPiedi.some((f) => Math.abs(Math.min(pavimento, f.base) - q.base) <= 26 * S)) { if (++q.altrove > 55) traslocaOrda(inPiedi); }
      else q.altrove = 0;
    }
    // Il centro della formazione segue i due solo se si sono spostati davvero.
    const visti = lottatori.filter((l) => l.p && !l.esploso && !l.fuoriCampo);
    if (q.fase !== "festa" && visti.length) {
      const m = Math.max(q.l + 40 * S, Math.min(q.r - 40 * S, visti.reduce((t, l) => t + l.p.bacino.x, 0) / visti.length));
      if (Math.abs(m - q.cx) > 50 * S) q.cx += (m - q.cx) * 0.04;
    }
    for (const z of q.zombie) {
      if (z.inBuco) continue;                                    // dentro il buco nero: fermo finché non riesce
      const Z = ZOMBI[z.tipo];
      z.t++; z.s++;
      if (z.lampo > 0) z.lampo--;
      if (z.gelo > 0) z.gelo--;
      z.x += z.vx; z.vx *= 0.86;
      z.x = Math.max(q.l + 6 * S, Math.min(q.r - 6 * S, z.x));
      if (z.stato === "giu") continue;
      if (z.stato === "esce") { if (z.s % 6 === 0 && z.s < 40) polvere(z.x, q.base - 1, 1); if (z.s >= 46) { z.stato = "va"; z.s = 0; } continue; }
      if (z.botta > 0) { z.botta--; continue; }
      // Va verso il lottatore sveglio più vicino che sta su questo piano.
      let f = null, d0 = 1e9;
      for (const l of lottatori) {
        if (!l.p || l.esploso || l.fuori || l.fuoriCampo || l.ko > 0) continue;
        const d = Math.abs(l.p.bacino.x - z.x) + (Math.abs(Math.min(pavimento, l.base) - q.base) > 26 * S || l.jet > 0 ? 400 * S : 0);
        if (d < d0) { d0 = d; f = l; }
      }
      if (!f) { z.fase += 0.04; continue; }                  // tutti a terra: ciondola e aspetta
      const dx = f.p.bacino.x - z.x, sopra = Math.abs(Math.min(pavimento, f.base) - q.base) < 26 * S && !(f.jet > 0);
      z.dir = dx >= 0 ? 1 : -1;
      if (z.stato === "colpo") {
        if (z.s === Z.carica && sopra && Math.abs(dx) < (Z.portata + 7) * S && !f.ko && !f.esploso && !f.preso) morso(z, f);
        if (z.s >= Z.carica + 26) { z.stato = "va"; z.s = 0; }
        continue;
      }
      if (sopra && Math.abs(dx) < Z.portata * S) { z.stato = "colpo"; z.s = 0; continue; }
      // Avanti, senza montarsi addosso: chi ha un altro zombie subito davanti aspetta (lo svelto scarta e passa).
      const davanti = z.tipo !== "svelto" && q.zombie.some((w) => w !== z && w.stato !== "giu" && w.stato !== "esce" && (w.x - z.x) * z.dir > 0 && Math.abs(w.x - z.x) < 15 * S);
      if (!davanti && Math.abs(dx) > (Z.portata - 5) * S) { z.x += z.dir * z.vel * S; z.fase += 0.12 + z.vel * 0.08; }
    }
    if (q.zombie.some((z) => z.stato === "giu" && z.s > 50)) q.zombie = q.zombie.filter((z) => !(z.stato === "giu" && z.s > 50));
  }
  // Durante la tregua: spalle a spalla, ognuno il suo lato, e ci si copre.
  function pensaAlleato(f, altro) {
    const q = orda, lato = q.lati[f.tipo] || (f.cx <= altro.cx ? -1 : 1);
    // Fra un'ondata e l'altra: un attimo di festa, poi di nuovo al proprio posto.
    if (q.fase === "pausa" && !f.cinque && q.ondata > 0) { f.cinque = true; f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1; inizia(f, "esulta"); return; }
    if (q.fase === "festa") {
      // L'orda è finita: uno di fronte all'altro, e il cinque.
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (!f.cinque) {
        f.cinque = true;
        if (q.vinta && altro.cinque && !altro.ko && Math.abs(altro.cx - f.cx) < 90 * S) {
          scrivi("CINQUE!", (f.p.testa.x + altro.p.testa.x) / 2, Math.min(f.p.testa.y, altro.p.testa.y) - 22 * S, false);
          scintille((f.p.manoA.x + altro.p.manoA.x) / 2, Math.min(f.p.manoA.y, altro.p.manoA.y) - 20 * S, 10, "#ffe27a");
        }
      }
      inizia(f, "esulta"); return;
    }
    // Non è sul piano dove arriva l'orda: ci va, come farebbe per raggiungere l'altro.
    if (Math.abs(f.base - q.base) > 18 * S) {
      if (f.base < q.base) {
        const o = f.supporto, meta = o ? ((f.cx - o.l < o.r - f.cx) ? o.l - 14 * S : o.r + 14 * S) : q.cx;
        f.dir = meta >= f.cx ? 1 : -1;
        if (o) f.scendeApposta = 300;
        inizia(f, "avanza", Math.max(10 * S, Math.min(W - 10 * S, meta))); return;
      }
      // L'orda è più su. Se l'alleato è lassù lo si raggiunge; sennò si aspetta: sarà l'orda a scendere.
      if (!(altro.p && !altro.esploso && Math.abs(Math.min(pavimento, altro.base) - q.base) <= 26 * S)) { f.pensa = 10; return; }
      const o = ostacoli.find((u) => Math.abs(u.t - q.base) < 8 * S && u.r > q.l && u.l < q.r);
      if (raggiungibile(f, o)) {
        const fianco = f.cx < (o.l + o.r) / 2 ? -1 : 1, meta = (fianco < 0 ? o.l : o.r) + fianco * 11 * S;
        f.dir = meta >= f.cx ? 1 : -1;
        if (Math.abs(meta - f.cx) < 4 * S) { iniziaScalata(f, o, fianco); return; }
        inizia(f, "avanza", meta); f.dopo = { o, lato: fianco }; return;
      }
      if (verso > 0 && !f.tel) { decolla(f, false); return; }
      f.pensa = 20; return;
    }
    // 0. Una mossa in due, se è il momento (vedi «LE MOSSE IN COPPIA»).
    if (q.fase === "lotta" && !(q.coppiaAttesa > 0) && pensaCoppia(f, altro, lato)) return;
    // 1. Uno zombie a portata di braccio: lo si colpisce, da qualunque parte arrivi.
    const z = zombieVicino(f.cx, 40 * S);
    if (z) {
      f.dir = z.x >= f.cx ? 1 : -1; f.zMira = z;
      if (f.arma && f.arma.tipo === "spada" && f.colpiArma > 0) { f.colpiArma--; inizia(f, "fendente"); return; }
      if (lamaPronta(f)) { inizia(f, scegli([[3, "fendente"], [2, "affondo"], [2, "rovescio"]])); return; }
      // Lo strisciante è basso: calci e colpi in giù (li aggiusta la posa, vedi `bersaglio`).
      if (z.tipo === "striscia") { inizia(f, scegli([[5, "calcio"], [3, "pugno"], [2, "diretto"]])); return; }
      if (Math.abs(z.x - f.cx) < 19 * S) { inizia(f, scegli([[3, "montante"], [2, "indietro"]])); return; }
      // Il grosso sta per calare la manata: chi è furbo si para.
      if (pesante(z) && z.stato === "colpo" && z.s < 20 && braccia(f) && Math.random() < 0.3 * f.furbo) { inizia(f, "para"); return; }
      inizia(f, scegli([[28 * pesoMossa(f, "pugno"), "pugno"], [22 * pesoMossa(f, "diretto"), "diretto"],
                        [18 * pesoMossa(f, "montante"), "montante"], [24 * pesoMossa(f, "calcio"), "calcio"]]));
      return;
    }
    const giu = altro.ko > 0 && !altro.esploso && !altro.preso;
    // 2. L'alleato ha uno zombie addosso e il mio lato è libero: vado a coprirlo.
    const suLui = !altro.esploso ? zombieVicino(altro.p.bacino.x, 36 * S) : null;
    const mioLato = zombieVicino(f.cx, 115 * S, lato);
    if (suLui && (!mioLato || giu)) {
      f.dir = suLui.x >= f.cx ? 1 : -1;
      inizia(f, "avanza", suLui.x - f.dir * 28 * S); f.corsa = 40; return;
    }
    // 3. Da lontano, contro quelli che arrivano dal mio lato: pistola, onda, raffica.
    const arriva = zombieVicino(f.cx, 1e9, lato);
    if (arriva && Math.abs(arriva.x - f.cx) > 46 * S && !giu) {
      if (f.arma && SPARANO[f.arma.tipo] && f.colpiArma > 0) { f.dir = lato; f.zMira = arriva; inizia(f, azioneArma(f.arma)); return; }
      if (anime && braccia(f) && !striscia(f)) {
        const quanti = orda.zombie.reduce((n, w) => n + (vivoZ(w) && (w.x - f.cx) * lato > 0 ? 1 : 0), 0);
        if (f.ki >= 45 && quanti >= 2 && Math.random() < 0.5) { f.dir = lato; inizia(f, "onda"); return; }
        if (f.ki >= 15 && Math.random() < 0.35) { f.dir = lato; f.zMira = arriva; inizia(f, "raffica"); return; }
      }
    }
    // 4. Al proprio posto: spalle all'alleato (o accanto a lui, se è a terra).
    const centro = giu ? altro.p.bacino.x : q.cx;
    const posto = Math.max(q.l + 14 * S, Math.min(q.r - 14 * S, centro + lato * (giu ? 22 : 15) * S));
    if (Math.abs(posto - f.cx) > 7 * S) {
      f.dir = posto >= f.cx ? 1 : -1; inizia(f, "avanza", posto);
      if (giu) f.corsa = 30;
      // Due passi per mettersi a posto si fanno senza voltare le spalle al proprio lato.
      if (Math.abs(posto - f.cx) < 46 * S) { f.voltato = true; f.dir = lato; }
      return;
    }
    f.dir = lato;
    if (giu && !altro.inVolo && Math.abs(altro.p.bacino.x - f.cx) < 44 * S) {
      // Una mano all'alleato: si rialza prima.
      altro.ko = Math.max(1, altro.ko - 30);
      if (!altro.aiutato) { altro.aiutato = true; scrivi("SU!", altro.p.bacino.x, altro.p.bacino.y - 34 * S, false); }
    } else altro.aiutato = false;
    f.pensa = 8;
  }
  // --- LE MOSSE IN COPPIA (05/10/2026, su richiesta) ------------------------
  // Durante l'orda i due non stanno solo spalle a spalla: ogni tanto fanno una
  // mossa in due. La decide chi dei due sta pensando (`pensaCoppia`), se
  // l'altro è lì accanto e libero; fra una e l'altra passano due-quattro
  // secondi. Si chiedono anche dal controller, che durante la tregua le mette
  // al posto delle mosse fatte sull'altro.
  //  - CAVALLINA. Dal mio lato non arriva nessuno, dal suo sì (o c'è un
  //    grosso). L'alleato si piega, io prendo la rincorsa, gli salto sopra e
  //    atterro più in là, in mezzo a loro: lo schianto vale due colpi per chi
  //    è lì sotto. Da lì il lato di là è mio, e lui guarda dall'altra parte.
  //  - CAMBIO DI LATO. L'alleato sta per andare giù e il mio lato è
  //    tranquillo: una giravolta schiena contro schiena, ci scambiamo di
  //    posto, e a metà giro chi è troppo vicino prende una manata.
  //  - COLPO INSIEME. Accerchiati, due o più per parte: un attimo per caricare
  //    e poi una spinta a due mani in fuori, nello stesso istante. Indietro
  //    tutti quelli entro qualche passo (coi personaggi a energia arriva più
  //    lontano e fa più male, e costa 20 di energia a testa).
  //  - PALLA DI CANNONE. Una fila dal mio lato: l'alleato mi lancia rasoterra,
  //    rotolo in mezzo a loro e li butto giù come birilli.
  // Finché la mossa dura i morsi non arrivano.
  const COPPIA = { attesa: [130, 250], vicini: 64 };
  const MOSSE_COPPIA = { cavallina: 1, sgabello: 1, trottola: 1, insieme: 1, bolide: 1, fionda: 1 };
  const VOCI_COPPIA = [["cavallina", "\u{1F938}", "Cavallina"], ["trottola", "\u{1F504}", "Cambio di lato"], ["insieme", "\u{1F91C}", "Colpo insieme"], ["bolide", "\u{1F3B3}", "Palla di cannone"]];
  const E_DI_COPPIA = { cavallina: 1, trottola: 1, insieme: 1, bolide: 1 };
  const prontoCoppia = (f) => !!(f.p && !f.ko && !f.esploso && !f.fuori && !f.preso && !f.tenuto && !(f.gelato > 0) && !(f.accecato > 0) && !(f.stordito > 0) &&
                                !(f.jet > 0) && !f.inVolo && !f.scalata && !f.coppia && gambe(f) === 2 && braccia(f) === 2);
  function coppiaPossibile(f, altro) {
    const q = orda;
    return !!(q && q.fase === "lotta" && verso > 0 && f && altro && prontoCoppia(f) && prontoCoppia(altro) &&
              Math.abs(f.base - q.base) < 8 * S && Math.abs(altro.base - q.base) < 8 * S && Math.abs(altro.cx - f.cx) < COPPIA.vicini * S);
  }
  // Quanti zombie in piedi da una parte di un punto, entro un certo raggio.
  const contaZ = (x, lato, raggio) => orda.zombie.reduce((n, z) => n + (vivoZ(z) && (z.x - x) * lato > 0 && Math.abs(z.x - x) < raggio ? 1 : 0), 0);
  // Dove atterrare con la cavallina: in mezzo ai primi che arrivano dal lato dell'alleato (o sul grosso).
  function metaCavallina(f, altro) {
    const va = altro.cx >= f.cx ? 1 : -1;
    const di = orda.zombie.filter((z) => vivoZ(z) && (z.x - altro.cx) * va > 20 * S && Math.abs(z.x - altro.cx) < 200 * S).sort((a, b) => Math.abs(a.x - altro.cx) - Math.abs(b.x - altro.cx));
    if (!di.length) return undefined;
    // Non proprio in mezzo: un passo prima, così lo schianto li prende e chi atterra non resta in bocca al grosso.
    const grosso = di.find((z) => z.tipo === "grosso");
    if (grosso) return grosso.x - va * 34 * S;
    const primi = di.slice(0, 3);
    return primi.reduce((t, z) => t + z.x, 0) / primi.length - va * 12 * S;
  }
  function coppia(tipo, f, altro, dove) {
    if (!coppiaPossibile(f, altro)) return false;
    const q = orda, lato = f.cx <= altro.cx ? -1 : 1;            // da che parte sto io, rispetto a lui
    const mx = (f.cx + altro.cx) / 2, my = Math.min(f.p.testa.y, altro.p.testa.y) - 24 * S;
    const comincia = (l, azione, dati) => {
      if (l.tel) lasciaCadere(l);
      l.zMira = null; l.ordine = null; l.onda = null; l.scatto = 0; l.fuga = null;
      inizia(l, azione);
      l.coppia = Object.assign({ tipo, con: l === f ? altro : f, h: 0, u: 0, fatto: false }, dati);
    };
    if (tipo === "cavallina") {
      const va = -lato;                                          // verso dove si salta: oltre l'alleato
      let x1 = dove !== undefined ? dove : altro.cx + va * 72 * S;
      x1 = va > 0 ? Math.max(altro.cx + 38 * S, Math.min(altro.cx + 190 * S, x1)) : Math.min(altro.cx - 38 * S, Math.max(altro.cx - 190 * S, x1));
      x1 = Math.max(q.l + 14 * S, Math.min(q.r - 14 * S, x1));
      if ((x1 - altro.cx) * va < 30 * S) return false;           // non c'è posto dove atterrare
      f.dir = va; altro.dir = va;
      const lungo = Math.abs(x1 - f.cx);
      comincia(f, "cavallina", { ruolo: "salta", x0: f.cx, xp: altro.cx, x1, va,
                              alto: Math.max(20 * S, Math.min((42 + 0.1 * lungo / S) * S, q.base - testataBasso - 96 * S)) });   // mai oltre il bordo in alto
      comincia(altro, "sgabello", { ruolo: "regge" });
      f.durata = altro.durata = Math.round(36 + lungo / (9 * S));
      scrivi("OPLÀ!", mx, my, false);
    } else if (tipo === "trottola") {
      f.dir = lato; altro.dir = -lato;
      comincia(f, "trottola", { x0: f.cx, x1: altro.cx, lato, salta: true });
      comincia(altro, "trottola", { x0: altro.cx, x1: f.cx, lato: -lato, salta: false, fatto: true });
      scrivi("CAMBIO!", mx, my, false);
    } else if (tipo === "insieme") {
      f.dir = lato; altro.dir = -lato;
      comincia(f, "insieme", { lato });
      comincia(altro, "insieme", { lato: -lato });
      scrivi("ORA!", mx, my, false);
    } else if (tipo === "bolide") {
      const x1 = Math.max(q.l + 14 * S, Math.min(q.r - 14 * S, f.cx + lato * 215 * S));
      if (Math.abs(x1 - f.cx) < 70 * S) return false;            // troppo poca strada per rotolare
      f.dir = lato; altro.dir = lato;
      comincia(f, "bolide", { ruolo: "rotola", x0: f.cx, x1, lato, presi: [], gira: 0 });
      comincia(altro, "fionda", { ruolo: "lancia" });
      scrivi("VAI!", mx, my, false);
    } else return false;
    q.coppiaAttesa = Math.round(caso(COPPIA.attesa[0], COPPIA.attesa[1]));
    q.coppie[tipo] = (q.coppie[tipo] || 0) + 1; q.senzaCoppia = 0;
    return true;
  }
  // Atterrando (o girando) in mezzo a loro: un colpo a tutti quelli entro il raggio.
  function schianto(f, x, raggio, forza) {
    const q = orda;
    let presi = 0;
    for (const z of q.zombie) {
      if (!vivoZ(z) || Math.abs(z.x - x) > raggio) continue;
      const via = z.x >= x ? 1 : -1;
      colpisciZombie(z, forza, via, z.x, corpoZ(z)[1], f);
      z.vx = via * 7.5 * S * (pesante(z) ? 0.35 : 1); z.botta = Math.max(z.botta, pesante(z) ? 50 : 30);
      presi++;
    }
    polvere(x - 9 * S, q.base - 1, 5); polvere(x + 9 * S, q.base - 1, 5);
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y: q.base - 8 * S, vx: 0, vy: 0, vita: 14, max: 14, colore: "#ffffff" });
    scossa = Math.max(scossa, 7); fermoColpo = Math.max(fermoColpo, 3);
    return presi;
  }
  // La spinta a due mani del colpo insieme: via tutti quelli dal proprio lato.
  function spazzata(f, lato) {
    const forte = anime && f.ki >= 20, raggio = (forte ? 140 : 86) * S, colore = anime ? COLORI_ANIME[f.tipo] : "#ffffff", y = f.p.collo.y;
    if (forte) f.ki -= 20;
    for (const z of orda.zombie) {
      if (!vivoZ(z) || (z.x - f.cx) * lato < -8 * S || Math.abs(z.x - f.cx) > raggio) continue;
      colpisciZombie(z, forte ? 4.6 : 3, lato, z.x, corpoZ(z)[1], f);
      z.vx = lato * (forte ? 10 : 8) * S * (pesante(z) ? 0.35 : 1); z.botta = Math.max(z.botta, 30);
    }
    for (let i = 0; i < 3 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "onda", x: f.cx + lato * (20 + 26 * i) * S, y, vx: lato * 3 * S, vy: 0, vita: 10 + 4 * i, max: 10 + 4 * i, colore });
    }
    scintille(f.p.manoA.x, f.p.manoA.y, 10, colore);
    scossa = Math.max(scossa, 6);
  }
  const scambiaLati = (f, altro, lato) => { orda.lati[f.tipo] = lato; orda.lati[altro.tipo] = -lato; };
  // Un fotogramma di mossa in coppia: dove sta, quanto è alto, e il momento del colpo.
  function eseguiCoppia(f) {
    const c = f.coppia, q = orda;
    if (!q || !MOSSE_COPPIA[f.azione]) { f.coppia = null; return; }
    const k = Math.min(1, f.t / f.durata), morbido = (u) => u * u * (3 - 2 * u);
    f.fantasma = true;                                           // passa davanti agli elementi della pagina, come chi vola
    if (c.tipo === "cavallina" && c.ruolo === "salta") {
      const stacco = 0.24, atterra = 0.86, xs = c.xp - c.va * 21 * S;
      if (k < stacco) { f.cx = c.x0 + (xs - c.x0) * morbido(k / stacco); c.h = 0; f.passo += 0.5; }
      else if (k < atterra) { c.u = (k - stacco) / (atterra - stacco); f.cx = xs + (c.x1 - xs) * c.u; c.h = c.alto * Math.sin(Math.PI * c.u); }
      else {
        f.cx = c.x1; c.h = 0;
        if (!c.fatto) { c.fatto = true; c.presi = schianto(f, c.x1, 56 * S, 4.6); scambiaLati(f, c.con, c.va); f.riparo = 34; }
      }
    } else if (c.tipo === "trottola") {
      f.cx = c.x0 + (c.x1 - c.x0) * morbido(k);
      c.h = c.salta ? 22 * S * Math.sin(Math.PI * k) : 0;
      if (k >= 0.5 && !c.girato) { c.girato = true; f.dir = -c.lato; }
      if (c.salta && k >= 0.5 && !c.fatto) {
        c.fatto = true;
        c.presi = schianto(f, (c.x0 + c.x1) / 2, 62 * S, 3);
        scambiaLati(f, c.con, -c.lato);
      }
    } else if (c.tipo === "insieme") {
      if (f.t >= 14 && !c.fatto) { c.fatto = true; spazzata(f, c.lato); }
    } else if (c.tipo === "bolide" && c.ruolo === "rotola") {
      const parte = 0.2, arriva = 0.8;
      if (k < parte) f.cx = c.x0;
      else if (k < arriva) {
        const u = (k - parte) / (arriva - parte);
        f.cx = c.x0 + (c.x1 - c.x0) * (1 - (1 - u) * (1 - u));   // parte forte e rallenta
        c.gira += 0.42;
        for (const z of q.zombie) {
          if (!vivoZ(z) || Math.abs(z.x - f.cx) > 16 * S || c.presi.indexOf(z) >= 0) continue;
          c.presi.push(z);
          colpisciZombie(z, 3, c.lato, z.x, corpoZ(z)[1], f);
          z.vx = c.lato * 5.5 * S * (pesante(z) ? 0.35 : 1); z.botta = Math.max(z.botta, 44);
        }
        if (f.t % 3 === 0) polvere(f.cx - c.lato * 8 * S, q.base - 1, 1);
      } else {
        f.cx = c.x1;
        if (!c.fatto) { c.fatto = true; f.riparo = 30; if (c.presi.length >= 3) scrivi("STRIKE!", f.cx, q.base - 62 * S, false); }
      }
    }
  }
  // Chi sta pensando guarda se è il momento di una mossa in due. Più tempo
  // passa dall'ultima, meno ci vuole per farne un'altra (`voglia`): così se
  // ne vede una ogni dieci secondi circa anche coi personaggi che gli zombie
  // li fermano da lontano.
  function pensaCoppia(f, altro, lato) {
    if (!coppiaPossibile(f, altro) || Math.random() > 0.75) return false;
    const voglia = Math.min(2, Math.floor((orda.senzaCoppia || 0) / 300));
    const mieiVicini = contaZ(f.cx, lato, 66 * S), suoiVicini = contaZ(altro.cx, -lato, 66 * S);
    const miei = contaZ(f.cx, lato, 125 * S), suoi = contaZ(altro.cx, -lato, 135 * S);
    // Accerchiati: tutti e due insieme. (Chi ha l'energia per farlo arrivare lontano non aspetta che siano addosso.)
    const largo = anime && f.ki >= 20 && altro.ki >= 20, daMe = largo ? contaZ(f.cx, lato, 135 * S) : mieiVicini, daLui = largo ? contaZ(altro.cx, -lato, 135 * S) : suoiVicini;
    if (daMe >= 1 && daLui >= 1 && daMe + daLui >= 4 - voglia) return coppia("insieme", f, altro);
    // L'alleato sta per andare giù (due morsi su tre, o molta meno vita) e io sono tranquillo: cambio di lato.
    if (suoiVicini >= 1 && mieiVicini === 0 && ((altro.morsiZ || 0) % 3 === 2 || vitaVera(altro) < vitaVera(f) - 0.3)) return coppia("trottola", f, altro);
    // Dal mio lato nessuno, dal suo tre o più (o un grosso): gli salto sopra e atterro in mezzo a loro.
    const grossoDaLui = orda.zombie.some((z) => vivoZ(z) && z.tipo === "grosso" && (z.x - altro.cx) * -lato > 20 * S && Math.abs(z.x - altro.cx) < 180 * S);
    if (miei === 0 && (suoi >= 3 - voglia || grossoDaLui)) return coppia("cavallina", f, altro, metaCavallina(f, altro));
    // Una fila dal mio lato, ancora lontana, e l'alleato libero: mi faccio lanciare.
    if (contaZ(f.cx, lato, 220 * S) >= 4 - voglia && mieiVicini <= 1 && suoiVicini === 0) return coppia("bolide", f, altro);
    return false;
  }

  // Dove tira chi spara o lancia: all'avversario, o durante la tregua allo zombie che ha scelto.
  function puntoMira(f, altro) {
    if (orda && orda.fase === "lotta") {
      const z = f.zMira && vivoZ(f.zMira) ? f.zMira : zombieVicino(f.cx, 1e9, f.dir) || zombieVicino(f.cx, 1e9);
      return z ? { x: z.x, y: corpoZ(z)[1] } : { x: f.cx + f.dir * 220 * S, y: f.p.collo.y };
    }
    return { x: altro.p.collo.x, y: altro.p.collo.y };
  }
  // Lo strisciante: mezzo zombie che si tira avanti sulle braccia.
  function disegnaStrisciante(z, T, pelle, scura, nero) {
    const d = z.dir, va = z.stato === "va" && !(z.botta > 0), ph = z.fase;
    const colpo = z.stato === "colpo" ? (z.s < 20 ? z.s / 20 : Math.max(0, 1 - (z.s - 20) / 10)) : 0;
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    // Il busto steso, che finisce a brandelli dove c'erano le gambe.
    ctx.fillStyle = T[0]; ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S; ctx.beginPath();
    ctx.moveTo(d * 9 * S, -13 * S - 3 * S * colpo); ctx.lineTo(d * 11 * S, -4 * S); ctx.lineTo(-d * 9 * S, -1.5 * S); ctx.lineTo(-d * 14 * S, -4 * S);
    ctx.lineTo(-d * 11 * S, -6 * S); ctx.lineTo(-d * 15 * S, -8 * S); ctx.lineTo(-d * 9 * S, -9.5 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    // Le braccia: una si allunga, l'altra tira.
    for (const [fase, tono] of [[Math.PI, scura], [0, pelle]]) {
      const a = va ? Math.sin(ph + fase) : 0.3, su = va ? Math.max(0, Math.cos(ph + fase)) : 0;
      const spalla = { x: d * 8 * S, y: -10 * S - 3 * S * colpo }, mano = { x: d * (20 + 7 * a + 5 * colpo) * S, y: -2 * S - (4 * su + 9 * colpo) * S };
      const gomito = { x: (spalla.x + mano.x) / 2, y: Math.min(spalla.y, mano.y) - 4 * S };
      ctx.strokeStyle = nero; ctx.lineWidth = 5.2 * S; ctx.beginPath(); ctx.moveTo(spalla.x, spalla.y); ctx.lineTo(gomito.x, gomito.y); ctx.lineTo(mano.x, mano.y); ctx.stroke();
      ctx.strokeStyle = tono; ctx.lineWidth = 3.2 * S; ctx.beginPath(); ctx.moveTo(spalla.x, spalla.y); ctx.lineTo(gomito.x, gomito.y); ctx.lineTo(mano.x, mano.y); ctx.stroke();
    }
    // La testa alzata, a bocca aperta.
    ctx.save(); ctx.translate(d * 14 * S, -15 * S - 3 * S * colpo); ctx.rotate(d * 0.25);
    ctx.fillStyle = pelle; ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S;
    ctx.beginPath(); ctx.arc(0, 0, 7 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#f4f7e6"; ctx.lineWidth = 0.8 * S;
    ctx.beginPath(); ctx.arc(d * 3.6 * S, -1.2 * S, 2.2 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    tondo(d * 4.2 * S, -1.2 * S, 0.8 * S, nero);
    ctx.fillStyle = "#3a1f24"; ctx.beginPath(); ctx.ellipse(d * 2.6 * S, 3.4 * S, (2 + 1.2 * colpo) * S, (1.4 + 1.4 * colpo) * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.restore();
  }
  function disegnaZombie(z) {
    const q = orda, T = TONI_ZOMBIE[z.tono], d = z.dir, nero = "#17171c", Z = ZOMBI[z.tipo], sc = Z.scala;
    const gonfio = z.tipo === "gonfio", grosso = pesante(z), rabbioso = z.tipo === "rabbioso", svelto = z.tipo === "svelto" || rabbioso;
    const corazzato = z.tipo === "corazzato", capo = z.tipo === "capo";
    const pelle = z.lampo > 0 ? "#ffffff" : z.gelo > 0 ? "#cfeeff" : rabbioso ? "#d9a08c" : capo ? "#8aa47c" : corazzato ? "#93b48a" : gonfio ? "#b9dc6e" : grosso ? "#86a878" : svelto ? "#b7d1a6" : "#9dbf8c";
    const scura = rabbioso ? "#a8604c" : gonfio ? "#8fb650" : grosso ? "#628556" : "#6f9164";
    const emerge = z.stato === "esce" ? Math.max(0, 1 - z.s / 46) : 0;
    const k = z.stato === "giu" ? Math.min(1, z.s / 16) : 0;                   // 0 in piedi, 1 steso
    ctx.save();
    if (z.stato === "giu") ctx.globalAlpha = Math.max(0, 1 - Math.max(0, z.s - 26) / 24);
    // Chi sta uscendo dal terreno si vede solo sopra la linea del suolo.
    const fin = Math.max(1, sc);
    // Il ritaglio serve solo a chi sta uscendo dal terreno; per gli altri costa e basta (con trenta zombie si sente).
    if (z.stato === "esce") { ctx.beginPath(); ctx.rect(z.x - 80 * S * fin, q.base - 120 * S * fin, 160 * S * fin, 120 * S * fin); ctx.clip(); }
    // Il capo: un alone viola dietro, che pulsa.
    if (capo && z.stato !== "giu") {
      const g = ctx.createRadialGradient(z.x, q.base - 60 * S, 10 * S, z.x, q.base - 60 * S, 90 * S);
      g.addColorStop(0, "rgba(170,90,255,.28)"); g.addColorStop(1, "rgba(170,90,255,0)");
      ctx.fillStyle = g; ctx.fillRect(z.x - 90 * S, q.base - 150 * S, 180 * S, 150 * S);
    }
    ctx.translate(z.x, q.base + emerge * 62 * S * sc);
    ctx.scale(sc, sc);
    if (z.tipo === "striscia") {
      if (k > 0) { ctx.translate(0, 3 * S * k); ctx.scale(1, 1 - 0.5 * k); }
      disegnaStrisciante(z, T, pelle, scura, nero);
      ctx.restore(); return;
    }
    if (k > 0) ctx.rotate(-z.cade * k * 1.5);
    const cammina = z.stato === "va" && !(z.botta > 0), ph = z.fase, dond = Math.sin(z.t * 0.07 + z.fase) * 1.4 * S;
    const colpo = z.stato === "colpo" ? (z.s < Z.carica ? z.s / Z.carica : Math.max(0, 1 - (z.s - Z.carica) / 12)) : 0;
    const indietro = z.botta > 0 ? -d * Math.min(1, z.botta / 10) * 5 * S : 0;
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    // Le gambe: strascicate, una più rigida dell'altra.
    const anca = { x: indietro * 0.4, y: -26 * S };
    const p1 = { x: d * (cammina ? 6 * Math.sin(ph) : 3) * S, y: -1.5 * S - (cammina ? Math.max(0, 2.5 * Math.cos(ph)) : 0) * S };
    const p2 = { x: -d * (cammina ? 5 * Math.sin(ph) : 4) * S, y: -1.5 * S };
    ctx.strokeStyle = nero; ctx.lineWidth = (grosso ? 8 : 6.4) * S;
    for (const p of [p2, p1]) { ctx.beginPath(); ctx.moveTo(anca.x, anca.y); ctx.lineTo((anca.x + p.x) / 2 + d * 1.5 * S, (anca.y + p.y) / 2); ctx.lineTo(p.x, p.y); ctx.stroke(); }
    ctx.strokeStyle = T[1]; ctx.lineWidth = (grosso ? 6 : 4.4) * S;
    for (const p of [p2, p1]) { ctx.beginPath(); ctx.moveTo(anca.x, anca.y); ctx.lineTo((anca.x + p.x) / 2 + d * 1.5 * S, (anca.y + p.y) / 2); ctx.lineTo(p.x, p.y); ctx.stroke(); }
    for (const p of [p2, p1]) { ctx.fillStyle = "#3a3f4a"; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.ellipse(p.x + d * 1.4 * S, p.y, 4.2 * S, 2.4 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); }
    // Il busto, piegato in avanti (lo svelto di più), con la maglia a brandelli.
    const spalla = { x: d * ((svelto ? 10 : 5) + 3 * colpo) * S + indietro + dond, y: (svelto ? -45 : -47) * S };
    const largo = grosso ? 1.35 : 1;
    ctx.save(); ctx.translate((anca.x + spalla.x) / 2, (anca.y + spalla.y) / 2); ctx.rotate(Math.atan2(spalla.y - anca.y, spalla.x - anca.x) + Math.PI / 2);
    ctx.scale(largo, 1);
    ctx.fillStyle = T[0]; ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S; ctx.beginPath();
    ctx.moveTo(-7.5 * S, -12 * S); ctx.lineTo(7.5 * S, -12 * S); ctx.lineTo(7.5 * S, 10 * S); ctx.lineTo(4 * S, 13 * S); ctx.lineTo(1.5 * S, 9.5 * S);
    ctx.lineTo(-2 * S, 13.5 * S); ctx.lineTo(-4.5 * S, 10 * S); ctx.lineTo(-7.5 * S, 12 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = T[1]; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.moveTo(-3 * S, -8 * S); ctx.lineTo(1 * S, -3 * S); ctx.lineTo(-2 * S, 1 * S); ctx.stroke();
    if (corazzato || capo) {
      // La corazza: una piastra di metallo coi ribattini.
      ctx.fillStyle = capo ? "#5d5470" : "#8d96a6"; ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S;
      rettangoloTondo(-6.5 * S, -10 * S, 13 * S, 15 * S, 3 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = capo ? "#b48cff" : "#5f6877";
      for (const [u, v] of [[-4, -7.5], [4, -7.5], [-4, 2.5], [4, 2.5]]) { ctx.beginPath(); ctx.arc(u * S, v * S, 0.9 * S, 0, Math.PI * 2); ctx.fill(); }
    }
    if (gonfio) {
      // La pancia gonfia, che pulsa: sta per scoppiare.
      const batte = 1 + 0.07 * Math.sin(z.t * 0.3);
      ctx.fillStyle = pelle; ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S;
      ctx.beginPath(); ctx.ellipse(d * 2 * S, 3 * S, 10.5 * S * batte, 10 * S * batte, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.fillStyle = scura; for (const [u, v, r] of [[-3, 0, 1.6], [4, 5, 1.3], [5, -3, 1]]) { ctx.beginPath(); ctx.arc((d * 2 + u) * S, (3 + v) * S, r * S, 0, Math.PI * 2); ctx.fill(); }
    }
    ctx.restore();
    // La testa: storta, un occhio grande e uno piccolo, la bocca aperta.
    const testa = { x: spalla.x + d * 3 * S, y: spalla.y - 10 * S + Math.sin(z.t * 0.11) * 0.8 * S };
    ctx.save(); ctx.translate(testa.x, testa.y); ctx.rotate(d * (0.22 + 0.08 * Math.sin(z.t * 0.05)) - (z.botta > 0 ? d * 0.4 : 0));
    if (grosso) ctx.scale(0.86, 0.86);
    ctx.fillStyle = pelle; ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S;
    ctx.beginPath(); ctx.arc(0, 0, 8 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = scura; ctx.beginPath(); ctx.ellipse(-d * 3.4 * S, 2.6 * S, 2.4 * S, 1.6 * S, 0.4, 0, Math.PI * 2); ctx.fill();
    if (corazzato || capo) {
      // L'elmo: una calotta di metallo con la fessura; quello del capo ha le corna.
      ctx.fillStyle = capo ? "#4a4258" : "#8d96a6"; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.arc(0, -1 * S, 9.2 * S, Math.PI, Math.PI * 2); ctx.lineTo(9.2 * S, 1.5 * S); ctx.lineTo(-9.2 * S, 1.5 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = capo ? "#2a2433" : "#5f6877"; ctx.lineWidth = 1.2 * S; ctx.beginPath(); ctx.moveTo(-8 * S, -4 * S); ctx.lineTo(8 * S, -4 * S); ctx.stroke();
      if (capo) {
        ctx.fillStyle = "#efe6d2"; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
        for (const lato of [-1, 1]) {
          ctx.beginPath(); ctx.moveTo(lato * 6 * S, -7 * S); ctx.quadraticCurveTo(lato * 15 * S, -10 * S, lato * 14 * S, -20 * S); ctx.quadraticCurveTo(lato * 10 * S, -12 * S, lato * 3 * S, -8.5 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
        }
      }
    } else if (svelto && !rabbioso) {
      // Lo svelto ha un cappuccio stracciato.
      ctx.fillStyle = T[1]; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S; ctx.beginPath();
      ctx.arc(0, 0, 8.6 * S, Math.PI * (d > 0 ? 0.95 : 1.25), Math.PI * (d > 0 ? 1.75 : 2.05)); ctx.lineTo(-d * 9.5 * S, 4 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (grosso) {
      // Il grosso ha un secchio ammaccato in testa.
      ctx.fillStyle = "#8d96a6"; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S; ctx.beginPath();
      ctx.moveTo(-8.6 * S, -2.5 * S); ctx.lineTo(-6.6 * S, -12 * S); ctx.lineTo(6.6 * S, -12 * S); ctx.lineTo(8.6 * S, -2.5 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "#5f6877"; ctx.beginPath(); ctx.moveTo(-7.6 * S, -6 * S); ctx.lineTo(7.6 * S, -6 * S); ctx.stroke();
    } else {
      ctx.strokeStyle = "#3d4a36"; ctx.lineWidth = 1.2 * S; ctx.beginPath();
      for (const u of [-4, -1, 2.5]) { ctx.moveTo(u * S, -7.4 * S); ctx.lineTo((u - d * 1.6) * S, -10.5 * S); }
      ctx.stroke();
    }
    if (z.stato === "giu") {
      ctx.strokeStyle = nero; ctx.lineWidth = 1.2 * S; ctx.beginPath();
      for (const u of [d * 4.4, d * 0.2]) { ctx.moveTo((u - 1.4) * S, -2.6 * S); ctx.lineTo((u + 1.4) * S, 0.2 * S); ctx.moveTo((u + 1.4) * S, -2.6 * S); ctx.lineTo((u - 1.4) * S, 0.2 * S); }
      ctx.stroke();
    } else {
      const grande = z.occhio > 0 ? d * 4.4 : d * 0.2, piccolo = z.occhio > 0 ? d * 0.2 : d * 4.4;
      ctx.fillStyle = "#f4f7e6"; ctx.strokeStyle = nero; ctx.lineWidth = 0.8 * S;
      ctx.beginPath(); ctx.arc(grande * S, -1.4 * S, 2.5 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.arc(piccolo * S, -1 * S, 1.5 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      tondo((grande + d * 0.6) * S, -1.4 * S, 0.9 * S, svelto ? "#b3261e" : nero); tondo((piccolo + d * 0.3) * S, -1 * S, 0.6 * S, svelto ? "#b3261e" : nero);
      if (rabbioso || capo) {
        // Occhi accesi: rossi il rabbioso, viola il capo.
        const brilla = rabbioso ? "#ff3b30" : "#c9a0ff";
        ctx.save(); ctx.shadowColor = brilla; ctx.shadowBlur = 6 * S;
        tondo((grande + d * 0.6) * S, -1.4 * S, 1.6 * S, brilla); tondo((piccolo + d * 0.3) * S, -1 * S, 1.1 * S, brilla);
        ctx.restore();
      }
    }
    ctx.fillStyle = "#3a1f24"; ctx.strokeStyle = nero; ctx.lineWidth = 0.8 * S;
    ctx.beginPath(); ctx.ellipse(d * 2.6 * S, 4 * S, (2.2 + 1.2 * colpo) * S, (1.5 + 1.6 * colpo) * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.restore();
    // Le braccia tese in avanti; quando morde si alzano e calano (il grosso le cala dall'alto).
    for (const [su, tono] of [[2.5, scura], [-2.5, pelle]]) {
      const alza = (grosso ? 22 : 9) * colpo * (1 - colpo) * 4;
      const mano = { x: spalla.x + d * (19 + 6 * colpo) * S, y: spalla.y + (su - alza + Math.sin(z.t * 0.09 + su) * 1.2 + (svelto ? 5 : 0)) * S };
      const gomito = { x: (spalla.x + mano.x) / 2, y: (spalla.y + mano.y) / 2 + 2.2 * S };
      ctx.strokeStyle = nero; ctx.lineWidth = (grosso ? 7.4 : 5.4) * S; ctx.beginPath(); ctx.moveTo(spalla.x, spalla.y + su * S); ctx.lineTo(gomito.x, gomito.y); ctx.lineTo(mano.x, mano.y); ctx.stroke();
      ctx.strokeStyle = T[0]; ctx.lineWidth = (grosso ? 5.4 : 3.4) * S; ctx.beginPath(); ctx.moveTo(spalla.x, spalla.y + su * S); ctx.lineTo(gomito.x, gomito.y); ctx.stroke();
      ctx.strokeStyle = tono; ctx.beginPath(); ctx.moveTo(gomito.x, gomito.y); ctx.lineTo(mano.x, mano.y); ctx.stroke();
      ctx.fillStyle = tono; ctx.strokeStyle = nero; ctx.lineWidth = 0.9 * S; ctx.beginPath(); ctx.arc(mano.x, mano.y, (grosso ? 3.8 : 2.7) * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    ctx.restore();
  }
  // In alto: che ondata è e quanti ne restano (una testina a zombie, piena finché è in piedi).
  function disegnaOrda() {
    const q = orda;
    if (!q) return;
    for (const z of q.zombie) if (!z.inBuco) disegnaZombie(z);
    if (q.fase === "festa" || !q.ricetta || corsa) return;      // nella corsa il conto lo tiene il suo cruscotto
    const n = q.ricetta.totale, abbattuti = q.fase === "pausa" ? n : q.uccisiOndata, passo = Math.min(10.5 * S, (W - 150 * S) / n), r = Math.min(3.6 * S, passo * 0.36);
    const y = verso < 0 ? pavimento - 54 * S : Math.max(22 * S, testataBasso + 22 * S) + (barreVita ? 36 * S : 0), x0 = W / 2 - (n - 1) * passo / 2 + 30 * S;
    ctx.save();
    ctx.font = "800 " + Math.round(11 * S) + "px Archivo, sans-serif"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
    ctx.lineWidth = 3 * S; ctx.strokeStyle = "#ffffff"; ctx.lineJoin = "round"; ctx.fillStyle = "#141414";
    const scritta = dici("Ondata") + " " + q.ondata + (q.ondate ? "/" + q.ondate : primatoOrda ? "  ★" + primatoOrda : "");
    ctx.strokeText(scritta, x0 - 10 * S, y); ctx.fillText(scritta, x0 - 10 * S, y);
    for (let i = 0; i < n; i++) {
      const viva = i >= abbattuti;
      ctx.globalAlpha = viva ? 1 : 0.35;
      ctx.fillStyle = viva ? "#9dbf8c" : "#d9d4cc"; ctx.strokeStyle = "#17171c"; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.arc(x0 + i * passo, y, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      if (viva && r > 3 * S) { tondo(x0 + i * passo - 1.2 * S, y - 0.5 * S, 0.8 * S, "#17171c"); tondo(x0 + i * passo + 1.4 * S, y - 0.3 * S, 0.5 * S, "#17171c"); }
    }
    // Le vite dei due: un cuore per ogni volta che possono ancora rialzarsi insieme.
    ctx.globalAlpha = 1; ctx.textAlign = "left"; ctx.font = "800 " + Math.round(12 * S) + "px sans-serif";
    ctx.lineWidth = 3 * S; ctx.strokeStyle = "#ffffff"; ctx.fillStyle = "#e0443a";
    const cuori = "\u2665".repeat(Math.max(0, q.vite));
    ctx.strokeText(cuori, x0 + (n - 1) * passo + 12 * S, y + 0.5 * S); ctx.fillText(cuori, x0 + (n - 1) * passo + 12 * S, y + 0.5 * S);
    ctx.restore();
  }

  // --- IL CONTROLLER RADIALE (05/10/2026, su richiesta) ----------------------
  // Un quarto di disco semitrasparente, attaccato all'angolo in basso a
  // destra, che si apre dal suo tasto (quello col joypad) e non c'entra con
  // la tendina: funziona con la tendina aperta o chiusa (se è aperta, è lei a
  // farsi in là). Nell'angolo c'è il personaggio che si sta comandando: un
  // clic lì e si passa all'altro. Gli spicchi sono le sue mosse: un clic e la fa. Le mosse cambiano coi
  // personaggi scelti; quelle a energia sono spente finché l'energia non basta.
  // Una mossa da vicino chiesta da lontano: prima ci va di corsa, poi colpisce.
  // Durante l'orda i comandi valgono contro gli zombie; durante uno scontro di
  // energie ogni comando è tifo. Il resto del tempo il lottatore pensa da sé.
  //   [mossa, icona, nome, energia che serve]
  const VOCI_RADIALE = {
    "": [["pugno", "\u{1F44A}", "Pugno"], ["calcio", "\u{1F9B5}", "Calcio"], ["montante", "⤴️", "Montante"], ["presa", "\u{1F93C}", "Presa"],
         ["para", "\u{1F6E1}️", "Parata"], ["salto", "\u{1F998}", "Salto"], ["jet", "\u{1F680}", "Jetpack"], ["lancia", "\u{1F4E6}", "Lancia un oggetto"]],
    guerrieri: [["onda", "\u{1F300}", "Onda energetica", 45], ["sfera", "\u{1F31E}", "Sfera gigante", 60], ["disco", "\u{1F4BF}", "Disco tagliente", 20],
                ["raffica", "\u2728", "Raffica di sfere", 15], ["rush", "\u{1F44A}", "Raffica di pugni", 8], ["telecinesi", "\u270B", "Presa a distanza", 50],
                ["lampo", "\u{1F4A1}", "Lampo accecante", 15],
                ["barriera", "\u{1F6E1}\uFE0F", "Barriera", 20], ["teletrasporto", "\u26A1", "Teletrasporto", 15], ["carica", "\u{1F525}", "Carica l'aura"],
                ["trasforma", "\u{1F31F}", "Trasformazione", 40], ["avvinghia", "\u{1F4A5}", "Autodistruzione", 30]],
    maghi: [["raffica", "\u2728", "Dardi magici", 15], ["onda", "\u{1F300}", "Raggio", 45], ["gelo", "\u2744\uFE0F", "Gelo", 20], ["rimpicciolisci", "\u{1F52E}", "Rimpicciolisci", 25],
            ["fulmine", "\u26A1", "Fulmine", 25], ["levita", "\u{1F388}", "Levitazione", 30],
            ["barriera", "\u{1F6E1}\uFE0F", "Scudo magico", 20], ["teletrasporto", "\u{1F4A8}", "Sparizione", 15], ["carica", "\u{1F525}", "Carica l'aura"]],
    lame: [["fendente", "\u2694\uFE0F", "Fendente"], ["affondo", "\u{1F5E1}\uFE0F", "Affondo"], ["rovescio", "\u21A9\uFE0F", "Rovescio"], ["scattoLama", "\u{1F4A8}", "Scatto tagliente"],
           ["lancioLama", "\u{1F3AF}", "Lama lanciata"], ["duello", "\u2716\uFE0F", "Incrocio di lame"],
           ["para", "\u{1F6E1}\uFE0F", "Parata"], ["salto", "\u{1F998}", "Salto"], ["jet", "\u{1F680}", "Jetpack"]],
  };
  const DA_VICINO = { pugno: 1, calcio: 1, montante: 1, presa: 1, rush: 1, fendente: 1, affondo: 1, rovescio: 1 };
  // Le mosse che si fanno sull'altro lottatore e basta: durante la tregua restano spente.
  const SULL_ALTRO = { levita: 1, presa: 1, teletrasporto: 1, telecinesi: 1, avvinghia: 1, duello: 1 };
  const radiale = { aperto: false, apre: 0, chi: "robot", lato: "dx", sopra: -2, giu: null, lampo: null, detto: null, dito: false, posto: -1 };
  try { radiale.aperto = deposito.getItem("mut-ring-radiale") === "on"; if (deposito.getItem("mut-ring-radiale-lato") === "sx") radiale.lato = "sx"; } catch (errore) { /* resta chiuso */ }
  if (radiale.aperto) radiale.apre = 1;
  // Durante la tregua le mosse che si fanno sull'altro lasciano il posto a quelle che si fanno CON l'altro.
  let vociTregua = null, vociTreguaDi = null;
  const vociRadiale = () => {
    const base = VOCI_RADIALE[stile] || VOCI_RADIALE[""];
    if (!orda || orda.fase === "festa") return base;
    if (corsa && corsa.chi) return base.filter((v) => !SULL_ALTRO[v[0]]);       // da soli: niente mosse in coppia
    if (vociTreguaDi !== base) { vociTreguaDi = base; vociTregua = base.filter((v) => !SULL_ALTRO[v[0]]).concat(VOCI_COPPIA); }
    return vociTregua;
  };
  const comandato = () => lottatori.find((l) => l.tipo === radiale.chi) || lottatori[0] || null;
  // Può fare questa mossa adesso? (per spegnere lo spicchio, e per rifiutare il comando)
  function puoFare(f, voce) {
    if (!f || !f.p || f.esploso || f.fuori) return false;
    if (corsa && (!corsa.chi || corsa.fase !== "lotta")) return false;          // fra un round e l'altro non c'è nessuno da picchiare
    if (sfida && (f === sfida.a || f === sfida.b)) return true;                  // nello scontro ogni comando è tifo
    if (f.ko > 0 || f.preso || f.tenuto || f.gelato > 0 || f.accecato > 0 || f.scalata || f.inVolo) return false;
    const id = voce[0];
    if (voce[3] && f.ki < voce[3]) return false;
    if (E_DI_COPPIA[id]) return coppiaPossibile(f, lottatori.find((l) => l !== f));
    if (orda && SULL_ALTRO[id]) return false;                                    // sull'alleato no
    if (id === "duello") return !duello && lamaPronta(f);
    if (id === "trasforma" && f.potenziato > 0 && f.forma >= 2) return false;
    if (id === "jet") return verso > 0;
    if (id === "lancia") return !!(f.tel || telefonoVicino(f)) && gambe(f) > 0;
    if ((id === "scattoLama" || id === "lancioLama" || TAGLI[id]) && !lamaPronta(f)) return false;
    if (striscia(f) && !(id === "pugno" || id === "montante" || id === "para" || id === "jet")) return false;
    return true;
  }
  // Il comando: fa partire la mossa (o ci manda il lottatore, se serve arrivare vicino).
  function ordina(f, id) {
    const altro = lottatori.find((l) => l !== f), voce = vociRadiale().find((v) => v[0] === id);
    if (!f || !altro || !voce || !puoFare(f, voce)) return false;
    if (sfida && (f === sfida.a || f === sfida.b)) return tifa(f);
    const z = orda && orda.fase === "lotta" ? zombieVicino(f.cx, 1e9) : null, tx = z ? z.x : altro.p.bacino.x;
    f.dir = tx >= f.p.bacino.x ? 1 : -1; f.zMira = z; f.fuga = null; f.ordine = null; f.stordito = 0;
    if (id === "jet") { if (f.jet > 0) f.jet = Math.min(f.jet, 20); else decolla(f, false); return true; }
    if (E_DI_COPPIA[id]) return coppia(id, f, altro, id === "cavallina" ? metaCavallina(f, altro) : undefined);
    if (id === "teletrasporto") return teletrasporta(f, altro);
    if (id === "duello") {
      // L'incrocio di lame si fa in due: per qualche secondo, appena sono vicini, le lame si incrociano.
      duello = 420;
      for (const l of lottatori) { l.jet = 0; l.pensa = Math.min(l.pensa, 4); if (l.lama && l.lama.lanciata) rientraLama(l); }
      return true;
    }
    if (id === "lancia") {
      if (f.tel) { inizia(f, "lancia"); return true; }
      const t = telefonoVicino(f);
      f.dir = t.x >= f.cx ? 1 : -1; f.prendiTel = t; f.ordine = { azione: "lancia", fino: tempo + 400 };
      inizia(f, "avanza", t.x); f.corsa = 80;
      return true;
    }
    if (f.tel) lasciaCadere(f);
    // Una mossa da vicino chiesta da lontano: prima ci si arriva, di corsa.
    const stessoPiano = Math.abs((z ? orda.base : altro.base) - f.base) <= 18 * S;
    if (DA_VICINO[id] && !(f.jet > 0) && stessoPiano && Math.abs(tx - f.cx) > 38 * S) {
      f.ordine = { azione: id, fino: tempo + 200 };
      inizia(f, "avanza", tx - f.dir * 27 * S); f.corsa = 90;
      return true;
    }
    if (id === "fendente" && f.arma && f.arma.tipo === "spada") f.colpiArma--;
    if (id === "trasforma") f.ki = 100;
    inizia(f, id);
    f.scatto = 0;
    return true;
  }
  // L'ordine rimasto in sospeso (si stava arrivando): adesso che è libero, lo esegue.
  function eseguiOrdine(f, altro) {
    const o = f.ordine;
    f.ordine = null;
    if (!o || tempo > o.fino) return false;
    if (o.azione === "lancia") { if (f.tel) { inizia(f, "lancia"); return true; } return false; }
    const z = orda && orda.fase === "lotta" ? zombieVicino(f.cx, 1e9) : null, tx = z ? z.x : altro.p.bacino.x;
    f.dir = tx >= f.p.bacino.x ? 1 : -1; f.zMira = z;
    if (Math.abs(tx - f.cx) > 48 * S) {
      // Il bersaglio si è spostato: ancora qualche passo.
      f.ordine = o; inizia(f, "avanza", tx - f.dir * 27 * S); f.corsa = 60;
      return true;
    }
    inizia(f, o.azione);
    return true;
  }
  // La forma (05/10/2026, su richiesta): un quarto di disco attaccato
  // all'angolo in basso a destra, appoggiato ai due bordi; il cerchio non si
  // chiude, si ferma ai bordi. Nell'angolo c'è il ritratto di chi si comanda
  // (dal vivo: è la sua testa in questo momento), con la vita e l'energia
  // lungo l'orlo. Intorno, due fasce a spicchi: dentro le mosse di servizio,
  // fuori gli attacchi. Aspetto da videogioco: pannelli scuri, bordi del
  // colore del personaggio, lo spicchio sotto il puntatore si accende.
  // Trascinando il ritratto oltre metà finestra, passa nell'altro angolo.
  const RAD = { centro: 64, dentro: 124, fuori: 188 };
  function geometriaRadiale() {
    const U = Math.max(S, 1), n = vociRadiale().length, sx = radiale.lato === "sx" ? 1 : -1;
    const x = sx < 0 ? W : 0, y = pavimento;
    const nFuori = n > 5 ? Math.ceil(n * 0.58) : n, spicchi = [];
    for (let i = 0; i < n; i++) {
      const giro = i < nFuori ? 1 : 0, quanti = giro ? nFuori : n - nFuori, k = giro ? i : i - nFuori;
      // L'angolo si misura dal bordo di sotto (0) al bordo di lato (un quarto di giro).
      const a0 = (Math.PI / 2) * k / quanti, a1 = (Math.PI / 2) * (k + 1) / quanti, am = (a0 + a1) / 2;
      const r0 = (giro ? RAD.dentro : RAD.centro) * U, r1 = (giro ? RAD.fuori : RAD.dentro) * U, rm = (r0 + r1) / 2;
      spicchi.push({ i, giro, q: (k + 0.5) / quanti, a0, a1, r0, r1, dx: sx * Math.cos(am), dy: -Math.sin(am), x: x + sx * Math.cos(am) * rm, y: y - Math.sin(am) * rm });
    }
    return { U, centro: RAD.centro * U, x, y, n, spicchi, sx, largo: (RAD.fuori + 10) * U };
  }
  // Che cosa c'è del controller sotto il puntatore: -1 il ritratto, 0..n-1 uno spicchio, -2 niente.
  function sottoRadiale(x, y) {
    if (!radiale.aperto || radiale.apre < 0.6 || fermo || !lottatori.length) return -2;
    const g = geometriaRadiale(), ax = (x - g.x) * g.sx, ay = g.y - y;
    if (ax < -1 || ay < -1) return -2;
    const d = Math.hypot(ax, ay);
    if (d > RAD.fuori * g.U) return -2;
    if (d <= g.centro) return -1;
    const fi = Math.atan2(Math.max(0, ay), Math.max(0, ax));
    for (const q of g.spicchi) if (d > q.r0 && d <= q.r1 && fi >= q.a0 - 1e-6 && fi <= q.a1 + 1e-6) return q.i;
    return -2;
  }
  // Quando il controller è aperto a destra, tendina e barretta dei tasti gli
  // fanno posto: gli si dice quanto è largo, e ci pensa lo stile.
  function fattiInLa() {
    const largo = radiale.aperto && radiale.lato !== "sx" && lottatori.length ? Math.round(geometriaRadiale().largo) : 0;
    if (largo === radiale.posto) return;
    radiale.posto = largo;
    for (const el of [pannello, tastoRadiale && tastoRadiale.parentNode]) {
      if (!el || !el.classList || !el.style || !el.style.setProperty) continue;
      el.classList.toggle("con-controller", largo > 0);
      el.style.setProperty("--controller", largo + "px");
    }
  }
  function apriRadiale(apri) {
    radiale.aperto = !!apri; radiale.sopra = -2; radiale.giu = null;
    if (preferisceFermo) radiale.apre = radiale.aperto ? 1 : 0;
    try { deposito.setItem("mut-ring-radiale", radiale.aperto ? "on" : "off"); } catch (errore) { /* pazienza */ }
    if (tastoRadiale) tastoRadiale.setAttribute("aria-pressed", radiale.aperto ? "true" : "false");
    if (!radiale.aperto) radiceHtml("remove", "ring-punta");
    fattiInLa();
  }
  // Un pezzo di corona fra due raggi e due angoli (misurati dal bordo di sotto).
  const giroDi = (g, fi) => (g.sx < 0 ? Math.PI + fi : -fi);
  function spicchio(g, r0, r1, f0, f1) {
    const anti = g.sx > 0;
    ctx.beginPath(); ctx.arc(g.x, g.y, r1, giroDi(g, f0), giroDi(g, f1), anti); ctx.arc(g.x, g.y, Math.max(0.01, r0), giroDi(g, f1), giroDi(g, f0), !anti); ctx.closePath();
  }
  function arcoDi(g, r, f0, f1) { ctx.beginPath(); ctx.arc(g.x, g.y, r, giroDi(g, f0), giroDi(g, f1), g.sx > 0); }
  function disegnaRadiale() {
    // Si apre e si chiude uscendo dall'angolo (con «meno movimento», di colpo).
    radiale.apre = preferisceFermo ? (radiale.aperto ? 1 : 0) : Math.max(0, Math.min(1, radiale.apre + (radiale.aperto ? 0.075 : -0.11)));
    if (radiale.apre <= 0 || !lottatori.length) return;
    const f = comandato();
    if (!f) return;
    fattiInLa();
    const g = geometriaRadiale(), voci = vociRadiale(), U = g.U, col = COLORI_ANIME[f.tipo], quarto = Math.PI / 2;
    const detto = radiale.detto && tempo < radiale.detto.fino ? radiale.detto.i : -2;
    const vivo = radiale.sopra > -2 || radiale.giu || detto > -2 ? 0.96 : 0.62;        // semitrasparente finché non ci si va sopra
    const esce = 1 - Math.pow(1 - radiale.apre, 3);
    ctx.save();
    ctx.translate(g.x, g.y); ctx.scale(esce, esce); ctx.translate(-g.x, -g.y);
    ctx.lineJoin = "round"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    for (const q of g.spicchi) {
      // Si accendono lungo l'angolo: prima quelli coricati, per ultimi quelli dritti.
      const entra = Math.max(0, Math.min(1, radiale.apre * 2.3 - q.q - (q.giro ? 0.25 : 0)));
      if (entra <= 0) continue;
      const voce = voci[q.i], ok = puoFare(f, voce), sopra = radiale.sopra === q.i && ok;
      const lampo = radiale.lampo && radiale.lampo.i === q.i && radiale.lampo.t > 0;
      spicchio(g, q.r0, q.r1, q.a0, q.a1);
      ctx.globalAlpha = vivo * entra;
      ctx.fillStyle = lampo ? (radiale.lampo.ok ? "#ffffff" : "#e0443a") : sopra ? col : q.giro ? "#2a3044" : "#191c29";
      if (sopra) { ctx.shadowColor = col; ctx.shadowBlur = 18 * U; }
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.globalAlpha = vivo * entra * (ok ? 0.75 : 0.3);
      ctx.strokeStyle = sopra ? "#ffffff" : ok ? col : "#8a90a6"; ctx.lineWidth = (sopra ? 2 : 1.1) * U; ctx.stroke();
      ctx.globalAlpha = vivo * entra * (ok ? 1 : 0.3);
      ctx.font = Math.round((q.giro ? 22 : 20) * U * (sopra ? 1.16 : 1)) + "px sans-serif"; ctx.fillStyle = "#ffffff";
      ctx.fillText(voce[1], q.x, q.y + (voce[3] ? -4 : 1) * U);
      if (voce[3]) {
        // Sotto l'icona, l'energia che vuole: rossa se non basta.
        ctx.font = "800 " + Math.round(8.5 * U) + "px Archivo, sans-serif";
        ctx.fillStyle = sopra || lampo ? "#10121a" : f.ki >= voce[3] ? "#dfe6ff" : "#ff7a6e";
        ctx.globalAlpha = vivo * entra * (ok ? 0.95 : 0.7);
        ctx.fillText(String(voce[3]), q.x, q.y + 13 * U);
      }
    }
    // L'orlo: una riga del colore del personaggio e le tacche, da strumento di bordo.
    ctx.globalAlpha = vivo * Math.min(1, radiale.apre * 1.5); ctx.strokeStyle = col; ctx.lineCap = "butt";
    ctx.lineWidth = 2 * U; arcoDi(g, (RAD.fuori + 1) * U, 0, quarto); ctx.stroke();
    ctx.lineWidth = 1 * U; ctx.globalAlpha *= 0.6;
    ctx.beginPath();
    for (let k = 1; k < 18; k++) {
      const fi = quarto * k / 18, c = g.sx * Math.cos(fi), sn = -Math.sin(fi), lungo = k % 3 === 0 ? 7 : 4;
      ctx.moveTo(g.x + c * (RAD.fuori + 3) * U, g.y + sn * (RAD.fuori + 3) * U); ctx.lineTo(g.x + c * (RAD.fuori + 3 + lungo) * U, g.y + sn * (RAD.fuori + 3 + lungo) * U);
    }
    ctx.stroke();
    // Il centro, nell'angolo: il ritratto di chi si comanda (un clic e si
    // cambia), e lungo l'orlo la sua vita e la sua energia.
    ctx.globalAlpha = Math.min(1, vivo + 0.25);
    spicchio(g, 0, g.centro, 0, quarto); ctx.fillStyle = "#0e1019"; ctx.fill();
    ctx.strokeStyle = radiale.sopra === -1 ? "#ffffff" : col; ctx.lineWidth = 2.2 * U; arcoDi(g, g.centro, 0, quarto); ctx.stroke();
    const vita = vitaVera(f), spazio = 0.09;
    ctx.lineCap = "round"; ctx.lineWidth = 3.4 * U;
    ctx.strokeStyle = "rgba(255,255,255,.14)"; arcoDi(g, g.centro - 6.5 * U, spazio, quarto - spazio); ctx.stroke();
    if (vita > 0.01) { ctx.strokeStyle = vita > 0.5 ? "#3ddc84" : vita > 0.25 ? "#ffc53d" : "#ff5a4e"; arcoDi(g, g.centro - 6.5 * U, spazio, spazio + (quarto - 2 * spazio) * vita); ctx.stroke(); }
    if (anime) {
      ctx.lineWidth = 3 * U;
      ctx.strokeStyle = "rgba(255,255,255,.14)"; arcoDi(g, g.centro - 12.5 * U, spazio * 1.15, quarto - spazio * 1.15); ctx.stroke();
      if (f.ki > 1) { ctx.strokeStyle = col; arcoDi(g, g.centro - 12.5 * U, spazio * 1.15, spazio * 1.15 + (quarto - 2.3 * spazio) * Math.min(1, f.ki / 100)); ctx.stroke(); }
    }
    const rx = g.x + g.sx * 24 * U, ry = g.y - 25 * U, rr = 15 * U, intero = !f.esploso && !f.fuori && f.p && f.p.testa;
    ctx.save();
    ctx.beginPath(); ctx.arc(rx, ry, rr, 0, Math.PI * 2); ctx.fillStyle = "#242a3c"; ctx.fill(); ctx.clip();
    if (intero) {
      // Il ritratto dal vivo: lo stesso lottatore, inquadrato sulla testa.
      const k = 1.05 * U / (S * Math.max(0.5, f.scala || 1));
      ctx.globalAlpha = 1; ctx.shadowBlur = 0;
      ctx.translate(rx - f.p.testa.x * k, ry - f.p.testa.y * k); ctx.scale(k, k);
      (stile ? disegnaUmano : f.tipo === "robot" ? disegnaRobot : disegnaMela)(f);
    } else { ctx.font = Math.round(17 * U) + "px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = "#ffffff"; ctx.fillText("\u{1F4A5}", rx, ry + 1 * U); }
    ctx.restore();
    ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineCap = "butt";
    ctx.globalAlpha = 1; ctx.strokeStyle = col; ctx.lineWidth = 2 * U; ctx.beginPath(); ctx.arc(rx, ry, rr, 0, Math.PI * 2); ctx.stroke();
    // La spia: verde se può agire, rossa se è a terra o bloccato.
    const pronto = intero && !(f.ko > 0) && !f.preso && !f.tenuto && !(f.gelato > 0);
    ctx.fillStyle = pronto ? "#3ddc84" : "#ff5a4e"; ctx.strokeStyle = "#0e1019"; ctx.lineWidth = 1.6 * U;
    ctx.beginPath(); ctx.arc(rx - g.sx * 11 * U, ry + 11 * U, 4 * U, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.globalAlpha = 0.8; ctx.fillStyle = "#ffffff"; ctx.font = "800 " + Math.round(10 * U) + "px sans-serif"; ctx.fillText("⇄", g.x + g.sx * 9 * U, g.y - 7 * U);
    // Oltre l'orlo, dalla parte dello spicchio che si ha sotto il puntatore, il nome della mossa.
    const quale = radiale.sopra >= 0 ? radiale.sopra : detto;
    let testo = "", dx = g.sx * Math.SQRT1_2, dy = -Math.SQRT1_2;
    if (radiale.apre >= 1 && quale >= 0 && voci[quale]) { testo = dici(voci[quale][2]); dx = g.spicchi[quale].dx; dy = g.spicchi[quale].dy; }
    else if (radiale.apre >= 1 && radiale.sopra === -1 && !radiale.giu) testo = (stile ? aspetto(f).nome : f.tipo === "robot" ? "ROBOT" : dici("Mela").toUpperCase()) + "  ⇄  " + dici("Cambia personaggio");
    if (testo) {
      ctx.font = "700 " + Math.round(12 * U) + "px Archivo, sans-serif";
      const misura = ctx.measureText ? ctx.measureText(testo) : null, larga = (misura && misura.width) || testo.length * 7 * U;
      const fuoriDa = (RAD.fuori + 16) * U, xx = Math.max(larga / 2 + 12 * U, Math.min(W - larga / 2 - 12 * U, g.x + dx * (fuoriDa + larga / 2 + 8 * U)));
      // Mai nella fascia in fondo: nell'estensione lì ci sono i tasti, che stanno sopra il canvas.
      const yy = Math.max(16 * U, Math.min(g.y - Math.max(60 * U, 76), g.y + dy * (fuoriDa + 13 * U)));
      ctx.globalAlpha = 0.95; ctx.fillStyle = "#0e1019"; rettangoloTondo(xx - larga / 2 - 9 * U, yy - 11.5 * U, larga + 18 * U, 23 * U, 6 * U); ctx.fill();
      ctx.strokeStyle = col; ctx.lineWidth = 1.2 * U; ctx.stroke();
      ctx.fillStyle = "#ffffff"; ctx.fillText(testo, xx, yy + 0.5 * U);
    }
    ctx.restore();
    // E sopra la testa di chi si comanda, una freccetta del suo colore.
    if (radiale.aperto && !f.esploso && !f.fuori) {
      const t = f.p.testa, yy = t.y - (24 + Math.sin(passi * 0.12) * 2.5) * S;
      ctx.save(); ctx.fillStyle = col; ctx.strokeStyle = "#141414"; ctx.lineWidth = 1.2 * S; ctx.lineJoin = "round";
      ctx.beginPath(); ctx.moveTo(t.x - 6 * S, yy - 8 * S); ctx.lineTo(t.x + 6 * S, yy - 8 * S); ctx.lineTo(t.x, yy); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.restore();
    }
    if (radiale.lampo && radiale.lampo.t > 0) radiale.lampo.t--;
  }

  // --- Modalità «super guerrieri» (stile anime, personaggi e mosse nostre) --
  // Energia (0-100) che si ricarica piano da sola e in fretta caricando
  // l'aura; si spende in raffiche di sfere, onde energetiche e teletrasporti.
  // Caricando a piena energia ci si potenzia: aura fissa, fulmini, colpi più forti.
  const COLORI_ANIME = { robot: "#56e1ff", mela: "#ff62d6" };

  // ·· LE TRASFORMAZIONI (05/10/2026, chieste da Riccardo) ··
  // Chi si potenzia non cambia solo colore: cambia proprio corpo, e ogni
  // coppia di personaggi ha la sua.
  //   super guerrieri   loro stessi, gonfiati: massa doppia, cresta ritta, casacca strappata
  //   robot e mela      il robot diventa un colosso d'acciaio, la mela un albero
  //   duellanti         il cavaliere incappucciato, con la lama doppia che para tutto
  //   maghi             per ora niente di nuovo: restano la trance e l'aura
  // I capelli accesi della forma: oro a Zefir, viola a Brasa; più chiari alla seconda.
  const CRESTA = { robot: ["#f0ae25", "#ffe066"], mela: ["#9b4fe0", "#cf9bff"] };
  function formaDi(f) {
    if (!f || !(f.potenziato > 0) || !f.forma) return null;
    if (stile === "guerrieri") return "super";
    if (stile === "lame") return "cavaliere";
    if (!stile) return f.tipo === "robot" ? "colosso" : "albero";
    return null;
  }
  // Quanto si disegna più grandi (la fisica resta quella di prima: cambia solo il disegno).
  function quantoGrosso(f) {
    const q = formaDi(f);
    return q === "colosso" || q === "albero" ? 1.44 : q === "super" ? 1.2 : 1;
  }
  const coloreAnime = (f) => (formaDi(f) === "super" ? CRESTA[f.tipo][Math.min(1, (f.forma || 1) - 1)] : COLORI_ANIME[f.tipo]);
  const GRIDO_FORMA = { colosso: "COLOSSO!", albero: "GRANDE ALBERO!", cavaliere: "CAVALIERE!" };
  const maniDi = (f) => (maghi() ? puntaBacchetta(f) : { x: (f.p.manoA.x + f.p.manoD.x) / 2, y: (f.p.manoA.y + f.p.manoD.y) / 2 });
  function eseguiAnime(f, altro) {
    if (f.azione === "carica") {
      f.ki = Math.min(100, f.ki + 1.1);
      if (f.t % 3 === 0 && particelle.length < MAX_PARTICELLE) {
        const b = f.p.bacino;
        particelle.push({ tipo: "scintilla", x: b.x + caso(-16, 16) * S, y: b.y + 20 * S, vx: caso(-0.3, 0.3) * S, vy: -caso(2, 4) * S,
                          vita: 18, max: 18, colore: COLORI_ANIME[f.tipo] });
      }
      if (f.t % 9 === 0 && particelle.length < MAX_PARTICELLE && f.base >= pavimento - 2) {
        particelle.push({ tipo: "detrito", x: f.cx + caso(-30, 30) * S, y: f.base - 2, vx: caso(-0.4, 0.4) * S, vy: -caso(3, 5) * S,
                          vita: 70, max: 70, rot: 0, va: caso(-0.2, 0.2), lato: caso(1.6, 3) * S, colore: "#9a948a" });
      }
      if (f.t % 20 === 0) scossa = Math.max(scossa, 2);
      // A piena energia: i guerrieri si trasformano (fino alla seconda forma), i maghi vanno in trance.
      if (f.ki >= 100) {
        if (stile === "guerrieri") { if (!(f.potenziato > 0) || f.forma < 2) inizia(f, "trasforma"); }
        else if (!f.potenziato) potenzia(f);
      }
    }
    if (f.azione === "onda" && f.t === 34) sparaOnda(f);
    if (f.azione === "raffica" && f.t >= 8 && f.t <= 32 && (f.t - 8) % 6 === 0) sparaSfera(f, altro);
    if (f.azione === "rush") eseguiRush(f, altro);
    eseguiSpeciale(f, altro);
  }
  // Nel ring libero la trasformazione è la rimonta di chi sta per cadere: una a round.
  function puoMutare(f) {
    return !!(!stile && !f.mutato && !(f.potenziato > 0) && f.p && !f.ko && !f.esploso && !f.preso && !f.tenuto && !f.fuori &&
              !(f.jet > 0) && !f.inVolo && !f.scalata && !(f.gelato > 0) && !fatale && !orda && !sfida && !buco && verso > 0 &&
              gambe(f) === 2 && braccia(f) === 2);
  }
  function potenzia(f) {
    if (f && f.p) suona("potenza", f.p.bacino.x);
    f.potenziato = 720; f.ki = 60;
    if (!stile || stile === "lame") f.forma = 1;                  // il colosso, l'albero, il cavaliere
    const b = f.p.bacino;
    particelle.push({ tipo: "onda", x: b.x, y: b.y - 10 * S, vx: 0, vy: 0, vita: 24, max: 24, colore: COLORI_ANIME[f.tipo] });
    scintille(b.x, b.y - 10 * S, 22, COLORI_ANIME[f.tipo]);
    scossa = Math.max(scossa, 10);
  }
  function sparaOnda(f) {
    if (f && f.p) suona("onda", f.p.bacino.x);
    // Chi risponde al colpo dell'altro tira anche con meno energia: quella che ha.
    if (f.ki < 45 && !(f.risposta && f.ki >= 5)) return;
    f.ki = Math.max(0, f.ki - 45);
    f.onda = { vita: 46, len: 0, colpito: false, muro: false, scontro: null, x0: 0, y0: 0, dir: f.dir };
  }
  function sparaSfera(f, altro) {
    if (f.ki < 4) return;
    f.ki -= 3;
    const m = maghi() ? puntaBacchetta(f) : (f.t % 12 === 8 ? f.p.manoA : f.p.manoD);
    const mira = puntoMira(f, altro);
    const bx = mira.x + caso(-8, 8) * S, by = mira.y + caso(-8, 8) * S;
    const d = Math.hypot(bx - m.x, by - m.y) || 1, v = 8 * S;
    proiettili.push({ x: m.x, y: m.y, vx: (bx - m.x) / d * v, vy: (by - m.y) / d * v, da: f, vita: 160, energia: true, stella: maghi(), colore: COLORI_ANIME[f.tipo] });
  }
  function zip(x, y, colore) {
    if (particelle.length >= MAX_PARTICELLE) return;
    particelle.push({ tipo: "zip", x, y, vx: 0, vy: 0, vita: 14, max: 14, colore });
    particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 12, max: 12, colore });
    // I maghi spariscono in una nuvoletta.
    for (let i = 0; maghi() && i < 6 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "polvere", x: x + caso(-10, 10) * S, y: y + caso(-18, 18) * S, vx: caso(-1.2, 1.2) * S, vy: caso(-1, 0.2) * S,
                        vita: Math.round(caso(16, 26)), max: 28, colore: "#c9a6ff" });
    }
  }
  function teletrasporta(f, altro) {
    if (f && f.p) suona("zap", f.p.bacino.x, 0.5);
    if (f.esploso || f.tenuto || f.preso || f.ko || !altro || altro.esploso) return false;
    f.ki = Math.max(0, f.ki - 15);
    const da = { x: f.p.bacino.x, y: f.p.bacino.y };
    const lato = f.cx < altro.cx ? 1 : -1;
    let nx = altro.cx + lato * 30 * S;
    if (nx < 30 * S || nx > W - 30 * S) nx = altro.cx - lato * 30 * S;
    nx = Math.max(30 * S, Math.min(W - 30 * S, nx));
    const dx = nx - f.cx, dy = altro.base - f.base;
    for (const n in f.p) { f.p[n].x += dx; f.p[n].y += dy; f.p[n].ox = f.p[n].x; f.p[n].oy = f.p[n].y; }
    f.cx = nx; f.base = altro.base; f.caos = 0; f.paracadute = 0; f.scalata = null; f.inVolo = false; f.onda = null; f.scatto = 0;
    if (altro.volo && altro.jet > 0) {
      if (!(f.volo && f.jet > 0)) prendiIlVolo(f);
      for (const n in f.p) f.p[n].oy = f.p[n].y;
      f.volaY = f.p.bacino.y; f.recupero = 0;
    } else f.jet = 0;
    f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
    zip(da.x, da.y, COLORI_ANIME[f.tipo]); zip(f.p.bacino.x, f.p.bacino.y, COLORI_ANIME[f.tipo]);
    inizia(f, scegli([[3, "pugno"], [2, "calcio"], [2, "montante"]]));
    return true;
  }
  function aggiornaOnde() {
    for (const f of lottatori) {
      const o = f.onda;
      if (!o) continue;
      if (f.ko || f.preso || f.tenuto || f.esploso || f.azione !== "onda") o.vita = Math.min(o.vita, 8);
      o.vita--;
      const m = maniDi(f);
      o.dir = f.dir; o.x0 = m.x + f.dir * 4 * S; o.y0 = m.y;
      o.max = f.dir > 0 ? W - o.x0 : o.x0;
      o.len = Math.min(o.max, o.len + 30 * S);
      o.scontro = null;
    }
    // Due onde una contro l'altra: parte lo scontro di energie (vedi più sotto).
    const [a, b] = lottatori;
    if (sfidaPausa > 0) sfidaPausa--;
    if (sfida) aggiornaSfida();
    else if (!sfidaPausa && a && b && a.onda && b.onda && !a.onda.colpito && !b.onda.colpito && a.onda.dir === -b.onda.dir &&
             Math.abs(a.onda.y0 - b.onda.y0) < 30 * S) {
      const sx = a.onda.dir > 0 ? a : b, dx = sx === a ? b : a;
      if (sx.onda.x0 < dx.onda.x0 - 40 * S && sx.onda.x0 + sx.onda.len >= dx.onda.x0 - dx.onda.len) { iniziaSfida("onda", sx, dx); aggiornaSfida(); }
    }
    for (const f of lottatori) {
      const o = f.onda;
      if (!o) continue;
      const altro = lottatori.find((l) => l !== f);
      if (!o.colpito && o.scontro === null && altro && !altro.ko && !altro.esploso && !altro.preso) {
        for (const n of ["testa", "collo", "bacino"]) {
          const q = altro.p[n], lungo = (q.x - o.x0) * o.dir;
          if (Math.abs(q.y - o.y0) < 9 * S + q.r && lungo > 0 && lungo < o.len) {
            o.colpito = true;
            colpisci(f, altro, 7.5 * (f.potenziato ? 1.3 : 1), q.x, q.y, "ZAAAP!");
            for (const k in altro.p) { altro.p[k].ox -= o.dir * 7 * S; altro.p[k].oy += 2 * S; }
            altro.inVolo = true; altro.ko = Math.max(altro.ko, 40);
            if (Math.random() < 0.3) smembra(altro, q.x, q.y);
            break;
          }
        }
      }
      // L'onda spazza via gli zombie che trova sulla sua strada.
      if (orda && o.scontro === null) {
        for (const z of orda.zombie) {
          const lungo = (z.x - o.x0) * o.dir;
          if (vivoZ(z) && lungo > 0 && lungo < o.len && Math.abs(corpoZ(z)[1] - o.y0) < 30 * S) colpisciZombie(z, 9, o.dir, z.x, o.y0, f);
        }
      }
      if (!o.muro && o.scontro === null && o.len >= o.max - 1) {
        o.muro = true;
        danneggiaBordo(o.dir > 0 ? "destra" : "sinistra", o.y0, 1);
        scintille(o.dir > 0 ? W - 2 : 2, o.y0, 14, COLORI_ANIME[f.tipo]);
      }
      if (o.vita <= 0) f.onda = null;
    }
  }

  // --- LO SCONTRO DI ENERGIE (05/10/2026, su richiesta) ---------------------
  // Quando uno carica un colpo d'energia l'altro prova a caricare lo stesso
  // (`rispondeUguale`): i due colpi partono insieme, si incontrano a metà e
  // comincia una lotta nella lotta. Prima due onde che si incrociavano si
  // spingevano a caso per meno di un secondo e non vinceva nessuno.
  //
  // LE REGOLE (niente dadi: decide quello che i due hanno in quel momento).
  //  1. LA SPINTA di ognuno vale 10, per: 1,3 se è trasformato o in trance (1,5
  //     alla seconda forma); 1,25 se è in furia; +2% per ogni livello
  //     d'esperienza; 0,6 se gli manca un braccio; da 0,7 a 1 secondo quanta
  //     vita gli resta; 0,6 se è rimpicciolito.
  //  2. IL FIATO di ognuno è 30 più l'energia che gli è rimasta dopo aver
  //     tirato. Tenere il colpo costa 0,2 di fiato a fotogramma (12 al secondo),
  //     e il fiato speso si porta via l'energia.
  //  3. GLI STRATTONI: una volta al secondo ognuno dà uno strattone, a turno, a
  //     mezzo secondo l'uno dall'altro. Comincia chi ha caricato per primo. Uno
  //     strattone costa 10 di fiato, dura 24 fotogrammi e raddoppia la spinta.
  //  4. SENZA FIATO niente strattoni, e la spinta crolla al 30%.
  //  5. IL PUNTO D'INCONTRO nasce a metà e va verso chi in quel momento spinge
  //     meno, tanto più in fretta quanto più le spinte sono diverse. Vince chi
  //     lo porta addosso all'altro: lo travolge (un colpo che vale doppio).
  //  6. Se restano senza fiato tutti e due (o dopo otto secondi) il punto
  //     esplode dove si trova: lo prende chi l'ha nella sua metà. Se è rimasto
  //     al centro, volano via tutti e due, illesi.
  //  7. Chi molla perde: un K.O., un colpo preso da fuori, il lampo negli
  //     occhi, il ghiaccio.
  //  8. IL TIFO: durante lo scontro spuntano due tasti, uno per parte, ai
  //     capi della barra. Ogni clic (o tocco) sul tasto di uno dei due, o su
  //     di lui, gli ridà 3 di fiato e gli dà una mano: un quarto di spinta
  //     in più, che svanisce in mezzo secondo. I clic si sommano (fino al
  //     triplo della spinta): cliccando in fretta si vince anche contro uno
  //     più forte.
  // Vale per le onde (e il raggio dei maghi) e per le sfere giganti, che si
  // fondono in una sola e restano a mezz'aria finché uno dei due non cede.
  const SFIDA = { base: 10, fiato: 30, consumo: 0.2, turno: 60, strattone: 10, dura: 24, forte: 2, secco: 0.3, vel: 0.03, pari: 0.1,
                  durata: 480, tifo: 3, tetto: 130, mano: 0.25, manoCala: 0.94, manoTetto: 2 };
  let sfida = null, sfidaPausa = 0, ultimaSfida = null, puntaSfida = false;
  function spintaDi(f) {
    let F = SFIDA.base;
    if (f.potenziato > 0) F *= f.forma >= 2 ? 1.5 : 1.3;
    if (f.furia > 0) F *= 1.25;
    F *= 1 + 0.02 * livelloDi(f.tipo);
    if (braccia(f) < 2) F *= 0.6;
    F *= 0.7 + 0.3 * vitaVera(f);
    if (f.piccolo > 0) F *= 0.6;
    return F;
  }
  function iniziaSfida(tipo, sx, dx, dove) {
    sfida = { tipo, a: sx, b: dx, u: 0, t: 0, azione: tipo === "onda" ? "onda" : "spingi", x: dove ? dove.x : 0, y: dove ? dove.y : 0, r: dove ? dove.r : 0,
              fiato: [SFIDA.fiato + sx.ki + (tipo === "sfera" ? (sx.caricaSfera || 0) * 0.5 : 0), SFIDA.fiato + dx.ki + (tipo === "sfera" ? (dx.caricaSfera || 0) * 0.5 : 0)],
              spinte: [0, 0], tifo: [0, 0], su: [0, 0], strattoni: [0, 0], colori: [COLORI_ANIME[sx.tipo], COLORI_ANIME[dx.tipo]],
              // Il primo strattone è di chi ha caricato per primo; a pari, di chi ha più energia.
              primo: sx.t !== dx.t ? (sx.t > dx.t ? 0 : 1) : (dx.ki > sx.ki ? 1 : 0) };
    for (const f of [sx, dx]) {
      if (tipo !== "onda") { f.jet = f.volo ? f.jet : 0; f.azione = "spingi"; f.t = 0; f.colpito = false; f.caricaSfera = 0; }
      f.durata = 1e6; f.scatto = 0; f.fuga = null;
    }
    sx.dir = 1; dx.dir = -1;
    scossa = Math.max(scossa, 10); fermoColpo = Math.max(fermoColpo, 4);
  }
  // Un clic su uno dei due mentre si spingono: il tifo gli ridà fiato.
  function tifa(f) {
    const s = sfida;
    if (!s || (f !== s.a && f !== s.b)) return false;
    const i = f === s.a ? 0 : 1;
    s.fiato[i] = Math.min(SFIDA.tetto, s.fiato[i] + SFIDA.tifo); s.tifo[i]++;
    if (!s.mano) s.mano = [0, 0];
    s.mano[i] = Math.min(SFIDA.manoTetto, s.mano[i] + SFIDA.mano);
    if (s.tasti) s.tasti[i].premuto = 7;
    const t = f.p.testa;
    scintille(t.x + caso(-8, 8) * S, t.y - 14 * S, 3, s.colori[i]);
    if (s.tifo[i] % 4 === 1) scrivi("DAI!", t.x, t.y - 22 * S, false);
    return true;
  }
  function aggiornaSfida() {
    const s = sfida, A = s.a, B = s.b;
    s.t++;
    const regge = (f) => !!(f.p && !f.esploso && !f.ko && !f.preso && !f.tenuto && !(f.gelato > 0) && !(f.accecato > 0) &&
                            f.azione === s.azione && (s.tipo !== "onda" || f.onda));
    const ra = regge(A), rb = regge(B);
    if (!ra || !rb) { fineSfida(ra ? A : rb ? B : null, "molla"); return; }
    // Le spinte, il fiato e gli strattoni a turno.
    const F = [0, 0];
    for (const i of [0, 1]) {
      const f = i ? B : A;
      s.fiato[i] = Math.max(0, s.fiato[i] - SFIDA.consumo);
      if (s.su[i] > 0) s.su[i]--;
      if ((s.t - 1 + (i === s.primo ? 0 : SFIDA.turno / 2)) % SFIDA.turno === 0 && s.fiato[i] >= SFIDA.strattone) {
        s.fiato[i] -= SFIDA.strattone; s.su[i] = SFIDA.dura; s.strattoni[i]++;
        const m = maniDi(f);
        scintille(m.x, m.y, 10, s.colori[i]);
        if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: m.x, y: m.y, vx: 0, vy: 0, vita: 12, max: 12, colore: s.colori[i] });
        if (s.strattoni[i] % 2 === 1) scrivi(["HAAA!", "YAAH!", "GRRR!"][(s.strattoni[i] + i) % 3], f.p.testa.x, f.p.testa.y - 20 * S, false);
        scossa = Math.max(scossa, 6);
      }
      if (!s.mano) s.mano = [0, 0];
      F[i] = spintaDi(f) * (s.su[i] > 0 ? SFIDA.forte : 1) * (s.fiato[i] <= 0 ? SFIDA.secco : 1) * (1 + s.mano[i]);
      s.mano[i] *= SFIDA.manoCala;
      f.ki = Math.max(0, Math.min(100, s.fiato[i] - SFIDA.fiato));
      f.durata = 1e6;
    }
    s.spinte = F;
    s.u += SFIDA.vel * (F[0] - F[1]) / (F[0] + F[1]);
    // Dove sta il punto d'incontro.
    let xa, xb;
    if (s.tipo === "onda") { xa = A.onda.x0; xb = B.onda.x0; s.y = (A.onda.y0 + B.onda.y0) / 2; }
    else { const ma = maniDi(A), mb = maniDi(B); xa = ma.x + 14 * S; xb = mb.x - 14 * S; s.y += ((ma.y + mb.y) / 2 - 20 * S - s.y) * 0.08; }
    if (xb - xa < 30 * S) { fineSfida(null, "tempo"); return; }
    const mezzo = (xa + xb) / 2, meta = (xb - xa) / 2 - (s.tipo === "onda" ? 10 * S : s.r * 0.6);
    s.x = mezzo + Math.max(-1, Math.min(1, s.u)) * Math.max(10 * S, meta);
    if (s.tipo === "onda") {
      A.onda.len = Math.max(4, s.x - xa); B.onda.len = Math.max(4, xb - s.x);
      A.onda.scontro = B.onda.scontro = s.x;
      A.onda.vita = Math.max(A.onda.vita, 12); B.onda.vita = Math.max(B.onda.vita, 12);
    } else s.r = Math.min(46 * S, s.r + 0.03 * S);
    // Si vede e si sente: scintille dal punto, la pagina che vibra, i sassi che si alzano.
    if (s.t % 2 === 0) scintille(s.x + caso(-4, 4) * S, s.y + caso(-6, 6) * S, 2, s.t % 4 ? "#ffffff" : s.colori[s.t % 8 ? 0 : 1]);
    if (s.t % 9 === 0 && particelle.length < MAX_PARTICELLE - 40) {
      particelle.push({ tipo: "onda", x: s.x, y: s.y, vx: 0, vy: 0, vita: 14, max: 14, colore: s.t % 18 ? "#ffffff" : s.colori[0] });
      if (s.y > pavimento - 80 * S) {
        particelle.push({ tipo: "detrito", x: s.x + caso(-40, 40) * S, y: pavimento - 2, vx: caso(-0.5, 0.5) * S, vy: -caso(2.5, 5) * S,
                          vita: 60, max: 60, rot: 0, va: caso(-0.2, 0.2), lato: caso(1.6, 3) * S, colore: "#9a948a" });
      }
    }
    scossa = Math.max(scossa, 2);
    if (s.u >= 1) fineSfida(A, "travolto");
    else if (s.u <= -1) fineSfida(B, "travolto");
    else if ((s.fiato[0] <= 0 && s.fiato[1] <= 0) || s.t >= SFIDA.durata) fineSfida(Math.abs(s.u) < SFIDA.pari ? null : s.u > 0 ? A : B, "tempo");
  }
  function fineSfida(vince, come) {
    const s = sfida, A = s.a, B = s.b, perde = vince ? (vince === A ? B : A) : null;
    sfida = null; sfidaPausa = 40;
    if (puntaSfida) { puntaSfida = false; radiceHtml("remove", "ring-punta"); }
    ultimaSfida = { tipo: s.tipo, vince: vince ? vince.tipo : null, come, u: s.u, t: s.t, tifo: s.tifo.slice(), strattoni: s.strattoni.slice(), fiato: s.fiato.slice() };
    const libera = (f, attesa) => { if (f.azione === s.azione) { f.azione = null; f.pensa = attesa; } f.durata = 0; };
    if (s.tipo === "sfera") {
      // La sfera fusa scoppia dov'è: addosso a chi ha perso, o a metà strada.
      libera(A, 24); libera(B, 24);
      if (perde && perde.p && !perde.esploso) {
        scrivi("KA-BOOOM!", perde.p.collo.x, Math.max(60, perde.p.collo.y - 50 * S), true);
        esplodiLottatore(perde, vince);
      } else {
        esplosione(s.x, Math.min(s.y, pavimento - 10 * S), 1.5, null, false);
        scrivi("KA-BOOOM!", s.x, Math.max(60, s.y - 50 * S), true);
      }
      return;
    }
    if (come === "molla") {
      // Uno ha mollato: l'onda dell'altro passa, e fa quello che fa un'onda.
      for (const f of [A, B]) {
        if (f.onda) { f.onda.scontro = null; f.onda.vita = f === vince ? Math.max(f.onda.vita, 16) : Math.min(f.onda.vita, 2); }
        if (f.azione === "onda") { f.durata = f.t + (f === vince ? 18 : 2); }
      }
      return;
    }
    const metti = (q) => { if (particelle.length < MAX_PARTICELLE) particelle.push(q); };
    metti({ tipo: "lampo", x: s.x, y: s.y, vx: 0, vy: 0, vita: 10, max: 10, r: 200 * S });
    for (const k of [0, 8]) metti({ tipo: "onda", x: s.x, y: s.y, vx: 0, vy: 0, vita: 22 + k, max: 22 + k, colore: k ? "#ffffff" : s.colori[vince === B ? 1 : 0] });
    scintille(s.x, s.y, 22, "#ffffff");
    scossa = Math.max(scossa, 16); fermoColpo = Math.max(fermoColpo, 8);
    if (!vince) {
      // Pari: lo scoppio a metà li sbalza via tutti e due, senza danni.
      for (const [f, lato] of [[A, -1], [B, 1]]) {
        if (f.onda) f.onda = null;
        for (const n in f.p) { f.p[n].ox = f.p[n].x - lato * 8 * S; f.p[n].oy = f.p[n].y + verso * 4 * S; }
        f.azione = null; f.jet = 0; f.inVolo = true; f.ko = Math.max(f.ko, 34); f.durata = 0;
      }
      scrivi("BOOM!", s.x, s.y - 30 * S, true);
      return;
    }
    // Travolto: l'onda di chi ha vinto passa e si porta via l'altro.
    const lato = vince === A ? 1 : -1, c = perde.p.collo;
    perde.onda = null;
    if (vince.onda) { vince.onda.scontro = null; vince.onda.colpito = true; vince.onda.vita = 16; }
    vince.durata = vince.t + 18;
    vince.dir = lato;
    if (come === "travolto") perde.danni++;                     // il colpo pieno vale doppio
    colpisci(vince, perde, come === "travolto" ? 9 : 6.5, c.x, c.y, "ZAAAP!");
    for (const n in perde.p) { perde.p[n].ox = perde.p[n].x - lato * 12 * S; perde.p[n].oy = perde.p[n].y + verso * 4.5 * S; }
    perde.inVolo = true; perde.ko = Math.max(perde.ko, 60); perde.jet = 0; perde.azione = null; perde.durata = 0;
    if (come === "travolto" && Math.random() < 0.35) smembra(perde, c.x, c.y);
    for (let i = 0; i < 3; i++) metti({ tipo: "fuoco", x: c.x + caso(-10, 10) * S, y: c.y + caso(-10, 10) * S, vx: lato * caso(0.5, 2) * S, vy: -caso(0.3, 1) * S, vita: 18, max: 18, r: caso(7, 12) * S });
  }
  // «L'ALTRO CERCA DI CARICARE LO STESSO COLPO». Mentre uno carica un colpo
  // d'energia (dal quinto fotogramma, finché c'è tempo per rispondere)
  // l'avversario, se è libero, prova a rispondere con lo stesso: ci riesce
  // tanto più spesso quanto più è furbo ed esperto (dal 74% al 95%), una prova
  // sola per colpo. Parte in pari con l'altro: i due colpi escono insieme. Chi
  // ha poca energia tira lo stesso con quella che ha, e nello scontro avrà meno
  // fiato. Chi non può (o non se ne accorge) si difende come prima.
  //   [fino a che fotogramma si può rispondere, energia minima per provarci]
  const SPECCHIO = { onda: [16, 10], sfera: [60, 25], raffica: [7, 8], disco: [16, 20], gelo: [9, 20], rimpicciolisci: [9, 25], lancioLama: [8, 0] };
  const MOLLABILI = { pugno: 1, diretto: 1, montante: 1, calcio: 1, testata: 1, salto: 1, schiva: 1, solleva: 1, palla: 1 };
  function rispondeUguale(f, altro) {
    const m = altro.azione, regola = SPECCHIO[m];
    if (!regola || altro.t < 5 || altro.t > regola[0] || altro.rispostaVista || altro.risposta || sfida || orda) return false;
    if (m === "lancioLama" ? !lamaPronta(f) : (!anime || f.ki < regola[1])) return false;
    if (f.ko || f.stordito || f.preso || f.tenuto || f.esploso || f.scalata || f.inVolo || f.gelato > 0 || f.accecato > 0 || f.scatto > 0 || f.recupero > 0) return false;
    // Per rispondere si lascia quello che si stava facendo (un pugno a vuoto, un salto, l'oggetto che si aveva in mano).
    if ((f.azione && !LASCIABILI[f.azione] && !MOLLABILI[f.azione]) || striscia(f) || !braccia(f) || f.arma || altro.ko || altro.esploso) return false;
    const dy = Math.abs(altro.p.collo.y - f.p.collo.y), d = Math.abs(altro.p.bacino.x - f.p.bacino.x);
    if (d < (m === "onda" ? 70 : 50) * S || (m === "onda" && dy > (f.jet > 0 ? 70 : 26) * S)) return false;
    altro.rispostaVista = true;                              // una prova sola per colpo
    if (Math.random() > Math.min(0.95, 0.65 + 0.15 * f.furbo + 0.03 * livelloDi(f.tipo))) return false;
    f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
    if (f.tel) lasciaCadere(f);
    inizia(f, m);
    if (f.azione !== m) return false;
    f.t = altro.t - (f === lottatori[1] ? 1 : 0);          // in pari: i due colpi escono nello stesso fotogramma
    f.risposta = true; f.specchio = 24;
    // In volo ci si mette alla stessa altezza dell'altro.
    if (f.jet > 0) f.volaY = f.p.bacino.y + (altro.p.collo.y - f.p.collo.y);
    const mani = maniDi(f);
    scintille(mani.x, mani.y, 8, COLORI_ANIME[f.tipo]);
    return true;
  }
  // Colpi uguali che si incontrano a mezz'aria. Le sferette si annullano una a
  // una; il disco le taglia e passa; due dischi (o due lame lanciate) si
  // spezzano; la sfera gigante inghiotte le piccole e cresce; due sfere
  // giganti si fondono e parte lo scontro.
  function scontriProiettili() {
    const n = proiettili.length;
    if (n < 2) return;
    for (let i = 0; i < n; i++) {
      const p1 = proiettili[i];
      if (p1.vita <= 0 || p1.neve) continue;
      for (let j = i + 1; j < n; j++) {
        const p2 = proiettili[j];
        if (p2.vita <= 0 || p2.neve || p1.da === p2.da || !p1.da || !p2.da) continue;
        const r1 = p1.grande ? p1.r : p1.disco ? 10 * S : 5 * S, r2 = p2.grande ? p2.r : p2.disco ? 10 * S : 5 * S;
        if (Math.hypot(p1.x - p2.x, p1.y - p2.y) > r1 + r2) continue;
        const x = (p1.x + p2.x) / 2, y = (p1.y + p2.y) / 2;
        if (p1.grande && p2.grande) {
          // Due sfere giganti: si fondono, e chi le ha lanciate le spinge.
          const a = p1.da, b = p2.da, sx = a.p.bacino.x <= b.p.bacino.x ? a : b, dx = sx === a ? b : a;
          const pronto = (f) => f.p && !f.esploso && !f.ko && !f.preso && !f.tenuto && !(f.gelato > 0) && !(f.accecato > 0) && braccia(f) > 0;
          p1.vita = 0; p2.vita = 0;
          if (!sfida && pronto(a) && pronto(b) && dx.p.bacino.x - sx.p.bacino.x > 110 * S) iniziaSfida("sfera", sx, dx, { x, y, r: Math.max(p1.r, p2.r) * 1.15 });
          else { esplosione(x, Math.min(y, pavimento - 10 * S), 1.9, null, true); scrivi("KA-BOOOM!", x, Math.max(60, y - 50 * S), true); }
          break;
        }
        if (p1.grande || p2.grande) {
          const g = p1.grande ? p1 : p2, piccolo = g === p1 ? p2 : p1;
          if (piccolo.disco) continue;                         // il disco la attraversa
          piccolo.vita = 0; g.r = Math.min(44 * S, g.r + 1.5 * S);
          scintille(piccolo.x, piccolo.y, 4, g.colore);
          if (piccolo === p1) break;
          continue;
        }
        if (!!p1.disco !== !!p2.disco) {
          // Un disco contro una sferetta (o una pallottola): il disco passa.
          const piccolo = p1.disco ? p2 : p1;
          piccolo.vita = 0; scintille(x, y, 5, "#ffffff");
          if (piccolo === p1) break;
          continue;
        }
        p1.vita = 0; p2.vita = 0;
        scintille(x, y, 8, "#ffffff"); scintille(x, y, 4, p1.colore || "#ffe27a"); scintille(x, y, 4, p2.colore || "#ffe27a");
        if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 10, max: 10, colore: "#ffffff" });
        if (p1.disco && passi - ultimoTzing > 12) { ultimoTzing = passi; scrivi("CLANG!", x, y - 12 * S, false); scossa = Math.max(scossa, 4); }
        else if (passi - ultimoTzing > 24) { ultimoTzing = passi; scrivi("TZING!", x, y - 12 * S, false); }
        break;
      }
    }
  }
  let ultimoTzing = 0;
  // La barra dello scontro: di qua e di là i due colori, il segno bianco dove
  // sta il punto d'incontro; sotto, il fiato che resta a ciascuno.
  // Dove sta la barra del tiro alla fune: sopra i due, a metà strada.
  function barraSfida(s) {
    const A = s.a, B = s.b, w = Math.min(190 * S, W - 40), h = 9 * S, cx = Math.max(w / 2 + 12, Math.min(W - w / 2 - 12, (A.p.bacino.x + B.p.bacino.x) / 2));
    const y = Math.max(testataBasso + 46 * S, Math.min(pavimento - 60 * S, Math.min(A.p.testa.y, B.p.testa.y, s.y - (s.r || 0)) - 46 * S));
    return { w, h, cx, y, x0: cx - w / 2 };
  }
  // I due tasti da martellare, ai capi della barra (sopra, se di lato non c'è posto). Una volta messi non si
  // spostano più fino alla fine dello scontro: si devono poter cliccare in fretta.
  function tastiSfida() {
    const s = sfida;
    if (!s || !s.x || s.t < 2) return null;
    if (!s.tasti) {
      const U = Math.max(S, 1), r = 27 * U, b = barraSfida(s), cy = b.y + b.h / 2, posto = b.x0 - 12 * S - 2 * r >= 4 && b.x0 + b.w + 12 * S + 2 * r <= W - 4;
      s.tasti = [-1, 1].map((lato, i) => ({
        f: i ? s.b : s.a, r, premuto: 0,
        x: posto ? (lato < 0 ? b.x0 - 12 * S - r : b.x0 + b.w + 12 * S + r) : Math.max(r + 6, Math.min(W - r - 6, b.cx + lato * (r + 8 * S))),
        y: posto ? cy : Math.max(r + 6, b.y - 14 * S - r),
      }));
    }
    return s.tasti;
  }
  function sottoTastoSfida(x, y) {
    const T = fermo ? null : tastiSfida();
    if (T) for (let i = 0; i < 2; i++) if (Math.hypot(x - T[i].x, y - T[i].y) <= T[i].r + 5) return i;
    return -1;
  }
  function disegnaTastiSfida() {
    const T = tastiSfida();
    if (!T) return;
    const s = sfida, k = Math.min(1, (s.t - 1) / 10), giro = Math.PI * 2;
    ctx.save();
    ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineJoin = "round"; ctx.lineCap = "round";
    T.forEach((b, i) => {
      if (b.premuto > 0) b.premuto--;
      const col = s.colori[i], batte = Math.sin(passi * 0.35 + i * 1.7), r = Math.max(1, b.r * k * (b.premuto > 0 ? 0.88 : 1 + batte * 0.045));
      // Un alone che pulsa: «cliccami».
      ctx.globalAlpha = 0.28 * k; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(b.x, b.y, r + (7 + batte * 3) * S, 0, giro); ctx.fill();
      ctx.globalAlpha = k; ctx.fillStyle = b.premuto > 0 ? col : "#12141d"; ctx.beginPath(); ctx.arc(b.x, b.y, r, 0, giro); ctx.fill();
      ctx.strokeStyle = b.premuto > 0 ? "#ffffff" : col; ctx.lineWidth = 3 * S; ctx.stroke();
      // Lungo l'orlo, il fiato di quello per cui si tifa: cliccando si riempie.
      const pieno = Math.max(0, Math.min(1, s.fiato[i] / SFIDA.tetto));
      const dentro = r - 6 * S;                      // (mentre il tasto spunta è ancora troppo piccolo per l'anello)
      if (dentro > 3) {
        ctx.lineWidth = 3.6 * S; ctx.strokeStyle = "rgba(255,255,255,.16)"; ctx.beginPath(); ctx.arc(b.x, b.y, dentro, 0, giro); ctx.stroke();
        if (pieno > 0.01) { ctx.strokeStyle = "#ffffff"; ctx.beginPath(); ctx.arc(b.x, b.y, dentro, -Math.PI / 2, -Math.PI / 2 + giro * pieno); ctx.stroke(); }
      }
      if (r < 8) return;
      ctx.font = Math.round(r * 0.7) + "px sans-serif"; ctx.fillStyle = "#ffffff"; ctx.fillText("\u{1F44A}", b.x, b.y - r * 0.14);
      ctx.font = "800 " + Math.round(r * 0.34) + "px Archivo, sans-serif"; ctx.fillStyle = b.premuto > 0 ? "#12141d" : col; ctx.fillText(dici("DAI!"), b.x, b.y + r * 0.5);
    });
    ctx.restore();
  }
  function disegnaSfida() {
    const s = sfida;
    if (!s || !s.x) return;
    const A = s.a, B = s.b, k = Math.min(1, s.t / 8);
    ctx.save();
    // Il punto d'incontro: un nodo bianco che pulsa, coi lampi dei due colori.
    const R = (s.tipo === "onda" ? 15 : 0) * S + Math.sin(passi * 0.9) * 2 * S;
    if (s.tipo === "sfera") {
      const mx = (s.u + 1) / 2;
      disegnaSferaGrande(s.x, s.y, s.r, mx > 0.5 ? s.colori[0] : s.colori[1]);
      ctx.globalAlpha = 0.55; ctx.fillStyle = mx > 0.5 ? s.colori[1] : s.colori[0];
      ctx.beginPath(); ctx.arc(s.x, s.y, s.r, mx > 0.5 ? -Math.PI / 2 : Math.PI / 2, mx > 0.5 ? Math.PI / 2 : Math.PI * 1.5); ctx.fill();
      ctx.globalAlpha = 1;
    } else {
      for (const [col, lato] of [[s.colori[0], -1], [s.colori[1], 1]]) {
        ctx.globalAlpha = 0.5; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(s.x + lato * 5 * S, s.y, R * 1.5, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1; tondo(s.x, s.y, R, "#ffffff");
    }
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.5 * S; ctx.lineJoin = "miter"; ctx.globalAlpha = 0.9;
    const raggio = s.tipo === "onda" ? R : s.r;
    for (let i = 0; i < 4; i++) {
      const a = caso(0, Math.PI * 2);
      let x = s.x + Math.cos(a) * raggio, y = s.y + Math.sin(a) * raggio;
      ctx.beginPath(); ctx.moveTo(x, y);
      for (let j = 0; j < 3; j++) { x += Math.cos(a) * caso(5, 12) * S + caso(-5, 5) * S; y += Math.sin(a) * caso(5, 12) * S + caso(-5, 5) * S; ctx.lineTo(x, y); }
      ctx.stroke();
    }
    // La barra.
    const { w, h, cx, y, x0 } = barraSfida(s);
    const segno = x0 + w * (Math.max(-1, Math.min(1, s.u)) + 1) / 2;
    ctx.globalAlpha = k;
    ctx.fillStyle = "#141414"; rettangoloTondo(x0 - 2.5 * S, y - 2.5 * S, w + 5 * S, h + 5 * S, 5 * S); ctx.fill();
    ctx.fillStyle = s.su[0] > 0 && passi % 4 < 2 ? "#ffffff" : s.colori[0]; ctx.fillRect(x0, y, segno - x0, h);
    ctx.fillStyle = s.su[1] > 0 && passi % 4 < 2 ? "#ffffff" : s.colori[1]; ctx.fillRect(segno, y, x0 + w - segno, h);
    ctx.fillStyle = "rgba(255,255,255,.3)"; ctx.fillRect(x0, y, w, h * 0.35);
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "#141414"; ctx.lineWidth = 1.2 * S;
    ctx.beginPath(); ctx.moveTo(segno, y - 4 * S); ctx.lineTo(segno + 4.5 * S, y + h / 2); ctx.lineTo(segno, y + h + 4 * S); ctx.lineTo(segno - 4.5 * S, y + h / 2); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "rgba(20,20,20,.55)"; ctx.fillRect(cx - 0.6 * S, y - 2 * S, 1.2 * S, h + 4 * S);
    // Il fiato: due barrette che si accorciano verso l'esterno.
    const hf = 4 * S, yf = y + h + 5 * S, mezzo = w / 2 - 5 * S;
    for (const i of [0, 1]) {
      const q = Math.min(1, s.fiato[i] / 100), secco = s.fiato[i] <= 0, bx = i ? cx + 5 * S : cx - 5 * S - mezzo;
      ctx.fillStyle = "#141414"; ctx.fillRect(bx - 1 * S, yf - 1 * S, mezzo + 2 * S, hf + 2 * S);
      ctx.fillStyle = secco ? (passi % 10 < 5 ? "#e0443a" : "#141414") : s.fiato[i] < 25 ? "#f2c230" : "#ffffff";
      if (secco) ctx.fillRect(bx, yf, mezzo, hf);
      else if (i) ctx.fillRect(bx, yf, mezzo * q, hf); else ctx.fillRect(bx + mezzo * (1 - q), yf, mezzo * q, hf);
    }
    // Il tempo che resta: una riga sottile sopra la barra.
    const resta = Math.max(0, 1 - s.t / SFIDA.durata);
    ctx.fillStyle = resta < 0.25 && passi % 10 < 5 ? "#e0443a" : "#141414"; ctx.fillRect(cx - w / 2 * resta, y - 6.5 * S, w * resta, 2 * S);
    ctx.restore();
  }
  function disegnaOnda(f) {
    const o = f.onda, col = COLORI_ANIME[f.tipo];
    const k = Math.min(1, o.vita / 10), y = o.y0, x1 = o.x0, x2 = o.x0 + o.dir * o.len;
    // Nello scontro, chi è rimasto senza fiato ha l'onda sottile, che balbetta.
    const io = sfida && sfida.tipo === "onda" ? (sfida.a === f ? 0 : sfida.b === f ? 1 : -1) : -1;
    const secco = io < 0 ? 1 : sfida.fiato[io] <= 0 ? (passi % 6 < 3 ? 0.45 : 0.7) : sfida.su[io] > 0 ? 1.5 : 1;
    const w = (8 + Math.sin(passi * 0.8) * 1.4) * S * k * secco, l = Math.min(x1, x2), r = Math.max(x1, x2);
    ctx.save();
    ctx.globalAlpha = 0.3; ctx.fillStyle = col; rettangoloTondo(l, y - w * 1.9, r - l, w * 3.8, w * 1.9); ctx.fill();
    ctx.globalAlpha = 0.85; rettangoloTondo(l, y - w, r - l, w * 2, w); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff"; rettangoloTondo(l, y - w * 0.42, r - l, w * 0.84, w * 0.42); ctx.fill();
    ctx.globalAlpha = 0.5; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x2, y, w * 2.2, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1; tondo(x2, y, w * 1.1, "#ffffff");
    ctx.globalAlpha = 0.6; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x1, y, w * 1.6, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
  // La sfera che si carica fra le mani prima dell'onda.
  function disegnaCaricaOnda(f) {
    const m = maniDi(f), k = Math.min(1, f.t / 34), col = COLORI_ANIME[f.tipo];
    ctx.save();
    ctx.globalAlpha = 0.45; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(m.x, m.y, (3 + 9 * k) * S, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1; tondo(m.x, m.y, (1.5 + 4 * k) * S, "#ffffff");
    ctx.restore();
  }
  function disegnaAura(f) {
    const p = f.p, c = { x: (p.collo.x + p.bacino.x) / 2, y: (p.collo.y + p.bacino.y) / 2 }, col = coloreAnime(f);
    const forte = f.azione === "carica" ? 1 : 0.7, sotto = c.y + 30 * S;
    ctx.save();
    ctx.fillStyle = col;
    for (let i = 0; i < 7; i++) {
      const off = Math.cos((i / 7) * Math.PI * 2 + passi * 0.03) * 17 * S;
      const alto = (58 + 16 * Math.sin(passi * 0.45 + i * 1.3)) * S * forte, ondeggia = Math.sin(passi * 0.3 + i) * 5 * S;
      ctx.globalAlpha = 0.16 * forte + 0.05;
      ctx.beginPath(); ctx.moveTo(c.x + off - 11 * S, sotto);
      ctx.quadraticCurveTo(c.x + off - 18 * S, c.y, c.x + off + ondeggia, sotto - alto);
      ctx.quadraticCurveTo(c.x + off + 18 * S, c.y, c.x + off + 11 * S, sotto); ctx.closePath(); ctx.fill();
    }
    if (f.potenziato > 0) {
      ctx.globalAlpha = 0.9; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.3 * S; ctx.lineJoin = "miter";
      for (let i = 0; i < 2; i++) {
        let x = c.x + caso(-22, 22) * S, y = c.y + caso(-40, 20) * S;
        ctx.beginPath(); ctx.moveTo(x, y);
        for (let k = 0; k < 4; k++) { x += caso(-6, 6) * S; y += caso(3, 7) * S; ctx.lineTo(x, y); }
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // --- Il volo dei super guerrieri ----------------------------------------
  // In modalità anime niente jetpack: si vola e basta. Si sta sospesi con le
  // gambe piegate, si scatta da un punto all'altro lasciando immagini
  // residue e linee di velocità, ci si scambia raffiche di pugni a mezz'aria,
  // gli scatti che si incontrano fanno un'onda d'urto, e chi colpisce forte
  // ricompare davanti all'avversario che vola via per rimandarlo indietro.
  const VOLO_VEL = 10;
  function prendiIlVolo(f) {
    const b = f.p.bacino;
    f.volo = true; f.jet = Math.round(caso(900, 1600)); f.caos = 0; f.azione = null; f.scalata = null; f.pensa = 8;
    f.volaY = Math.max(110, Math.min(pavimento - 70 * S, b.y - caso(60, 150) * S));
    f.paracadute = 0;
    for (const n in f.p) f.p[n].oy = f.p[n].y + 6 * S;
    const col = COLORI_ANIME[f.tipo];
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: b.x, y: b.y + 26 * S, vx: 0, vy: 0, vita: 16, max: 16, colore: col });
    for (let i = 0; i < 10 && particelle.length < MAX_PARTICELLE; i++) {
      const lato = i % 2 ? 1 : -1;
      particelle.push({ tipo: "polvere", x: b.x + lato * caso(4, 18) * S, y: b.y + 28 * S, vx: lato * caso(1.5, 3) * S, vy: -caso(0.2, 0.8) * S,
                        vita: Math.round(caso(18, 28)), max: 28, colore: "#b9b4ab" });
    }
  }
  // Lo scatto: un tratto in linea retta ad alta velocità verso un punto che
  // insegue l'avversario.
  function scatta(f, altro, frames) {
    if (!(f.jet > 0)) prendiIlVolo(f);
    f.scatto = frames || 22; f.bersaglio = altro; f.azione = null;
  }
  function aggiornaScatto(f) {
    const a = f.bersaglio, b = f.p.bacino;
    if (!a || a.esploso || f.ko || f.preso || f.tenuto) { f.scatto = 0; return; }
    const lato = b.x <= a.p.bacino.x ? -1 : 1;
    const tx = a.p.bacino.x + lato * 32 * S, ty = a.p.bacino.y;
    const dx = tx - b.x, dy = ty - b.y, d = Math.hypot(dx, dy);
    f.dir = -lato;
    if (d < 7 * S || --f.scatto <= 0) {
      f.scatto = 0;
      // Arrivato: si attacca subito.
      if (d < 40 * S && !a.ko) inizia(f, !maghi() && f.ki >= 8 && Math.random() < 0.55 ? "rush" : scegli([[3, "pugno"], [2, "calcio"], [2, "montante"]]));
      return;
    }
    const passo = Math.min(d, VOLO_VEL * S * (f.forma > 0 && f.potenziato > 0 ? 1.35 : 1)), ux = dx / d, uy = dy / d;
    for (const n in f.p) { const q = f.p[n]; q.x += ux * passo; q.y += uy * passo; q.ox += ux * passo; q.oy += uy * passo; }
    f.cx += ux * passo; f.meta = f.cx; f.volaY = b.y; f.base = b.y + 30 * S;
    f.vel = { x: ux, y: uy };
    if (passi % 2 === 0) residua(f);
    if (passi % 2 === 1 && particelle.length < MAX_PARTICELLE) {
      particelle.push({ tipo: "linea", x: b.x - ux * 18 * S + caso(-10, 10) * S * uy, y: b.y - uy * 18 * S + caso(-10, 10) * S * ux,
                        vx: -ux * 3 * S, vy: -uy * 3 * S, vita: 10, max: 10, lung: caso(14, 30) * S, colore: COLORI_ANIME[f.tipo] });
    }
  }
  // Un'immagine residua: la sagoma del corpo, ferma dove era, che sbiadisce.
  function residua(f) {
    if (scie.length > 24) scie.shift();
    const punti = {};
    for (const n in f.p) punti[n] = { x: f.p[n].x, y: f.p[n].y };
    scie.push({ f, punti, vita: 12, colore: COLORI_ANIME[f.tipo] });
  }
  function disegnaScie() {
    for (const sc of scie) {
      const p = sc.punti;
      ctx.save(); ctx.globalAlpha = 0.3 * sc.vita / 12; ctx.strokeStyle = sc.colore; ctx.fillStyle = sc.colore;
      ctx.lineCap = "round"; ctx.lineWidth = 5 * S; ctx.beginPath();
      for (const [a, b] of ASTE.slice(0, 10)) { ctx.moveTo(p[a].x, p[a].y); ctx.lineTo(p[b].x, p[b].y); }
      ctx.stroke();
      if (eMela(sc.f)) { const c = corpoMela(p); ctx.beginPath(); ctx.arc(c.x, c.y, c.R, 0, Math.PI * 2); ctx.fill(); }
      else { ctx.beginPath(); ctx.arc(p.testa.x, p.testa.y, 8.5 * S, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 15 * S; ctx.beginPath(); ctx.moveTo(p.collo.x, p.collo.y); ctx.lineTo(p.bacino.x, p.bacino.y); ctx.stroke(); }
      ctx.restore();
    }
  }
  let scie = [];

  function pensaGuerriero(f, altro) {
    const ob = altro.p.bacino, mio = f.p.bacino;
    f.dir = ob.x >= mio.x ? 1 : -1;
    if (altro.ko || altro.preso || altro.esploso) {
      // Ha vinto: scende a terra e (se è il caso) balla.
      f.jet = Math.min(f.jet, 40); f.meta = f.cx; f.pensa = 20; return;
    }
    const dx = Math.abs(ob.x - mio.x) / S, dy = Math.abs(ob.y - mio.y) / S, d = Math.hypot(dx, dy);
    if (f.jet < 60 || Math.random() < 0.025) { f.jet = Math.min(f.jet, 30); f.pensa = 30; return; }   // atterra
    if (mossaSpeciale(f, altro)) return;
    if (d > 60 && Math.random() < 0.55) { scatta(f, altro, 26); return; }
    if (!maghi() && d <= 46 && f.ki >= 8 && Math.random() < 0.4) { inizia(f, "rush"); return; }
    if (f.ki >= 45 && d > 70 && dy < 50 && Math.random() < 0.3) { inizia(f, "onda"); return; }
    if (f.ki >= 15 && d > 80 && Math.random() < 0.25) { inizia(f, "raffica"); return; }
    if (f.ki >= 15 && Math.random() < 0.12 && teletrasporta(f, altro)) return;
    if (d > 34) { scatta(f, altro, 16); return; }
    f.volaY = ob.y + caso(-6, 6) * S; f.meta = f.cx;
    inizia(f, scegli([[30 * f.aggr * pesoMossa(f, "pugno"), "pugno"], [22 * f.aggr * pesoMossa(f, "diretto"), "diretto"],
                      [16 * pesoMossa(f, "montante"), "montante"], [16 * f.aggr * pesoMossa(f, "calcio"), "calcio"],
                      [8 * f.furbo * pesoMossa(f, "para"), "para"], [maghi() ? 0 : 10 * f.ki / 100, "rush"]]));
  }

  // Raffica di pugni a distanza ravvicinata, chiusa da un colpo a due mani
  // che scaraventa via l'avversario (verso il basso se si è in aria).
  function colpettino(f, altro, x, y) {
    if (altro.azione === "para" && altro.dir === -f.dir) { scintille(x, y, 3, "#bfe9ff"); return; }
    scintille(x, y, 4, "#ffe27a");
    for (const n in altro.p) altro.p[n].ox -= f.dir * 0.5 * S;
    altro.dolore = 10; altro.stordito = Math.max(altro.stordito, 6); altro.azione = null;
    if (Math.random() < 0.3) segna(altro, x, y, 2);
    if (Math.random() < 0.25) schizza(altro, x, y, 1, 0.5);
    fermoColpo = Math.max(fermoColpo, 1);
    f.ki = Math.min(100, f.ki + 1);
  }
  function eseguiRush(f, altro) {
    const b = f.p.bacino, ob = altro.p.bacino;
    const vicino = Math.hypot(ob.x - b.x, ob.y - b.y) < 42 * S && !altro.ko && !altro.esploso && !altro.preso;
    // Si resta attaccati all'avversario, a distanza di pugno (non dentro).
    if (f.t < 30 && Math.abs(ob.x - b.x) < 26 * S) {
      const step = -f.dir * Math.min(3 * S, 26 * S - Math.abs(ob.x - b.x));
      for (const n in f.p) { f.p[n].x += step; f.p[n].ox += step; }
      f.cx += step;
    }
    if (!vicino && f.t < 30 && Math.hypot(ob.x - b.x, ob.y - b.y) < 90 * S) {
      const tx = ob.x - f.dir * 31 * S, step = Math.max(-5 * S, Math.min(5 * S, tx - b.x));
      for (const n in f.p) { f.p[n].x += step; f.p[n].ox += step; }
      f.cx += step;
      if (f.jet > 0) f.volaY = ob.y;
    }
    if (f.t < 30 && f.t % 4 === 2 && vicino) {
      const m = f.t % 8 === 2 ? f.p.manoA : f.p.manoD;
      colpettino(f, altro, (m.x + altro.p.collo.x) / 2, (m.y + altro.p.collo.y) / 2);
      if (f.t % 8 === 2 && passi % 2 === 0) scrivi(Math.random() < 0.5 ? "PAM!" : "TUM!", altro.p.collo.x, altro.p.collo.y - 14 * S, false);
    }
    if (f.t === 37 && vicino) {
      const inAria = altro.jet > 0 || altro.base - Math.max(altro.p.piedeA.y, altro.p.piedeD.y) > 20 * S;
      colpisci(f, altro, 6.5, altro.p.collo.x, altro.p.collo.y, "SBAAM!");
      const [vx, vy] = inAria ? [f.dir * 4, 14] : [f.dir * 12, -7];
      for (const n in altro.p) { altro.p[n].ox = altro.p[n].x - vx * S; altro.p[n].oy = altro.p[n].y - verso * vy * S; }
      altro.inVolo = true; altro.ko = Math.max(altro.ko, 50); altro.jet = 0; altro.recupero = 0;
      scossa = Math.max(scossa, 8);
      if (f.ki >= 15 && Math.random() < 0.6) { f.insegui = 10; f.catena = 0; }
    }
  }
  // Ping-pong: ricompare davanti a chi vola via e lo rispedisce indietro.
  function aggiornaInseguimento(f, altro) {
    if (!(f.insegui > 0) || --f.insegui > 0) return;
    const b = altro.p.bacino, vx = b.x - b.ox, vy = b.y - b.oy, v = Math.hypot(vx, vy);
    if (!altro.inVolo || v < 5 * S || altro.esploso || f.ko || f.preso || f.tenuto || f.ki < 10) { f.catena = 0; return; }
    let px = b.x + vx * 9, py = b.y + vy * 9;
    px = Math.max(40 * S, Math.min(W - 40 * S, px)); py = Math.max(80 * S, Math.min(pavimento - 40 * S, py));
    const da = { x: f.p.bacino.x, y: f.p.bacino.y }, sx = px + Math.sign(vx || 1) * 22 * S - f.p.bacino.x, sy = py - f.p.bacino.y;
    for (const n in f.p) { const q = f.p[n]; q.x += sx; q.y += sy; q.ox = q.x; q.oy = q.y; }
    f.cx += sx; f.ki -= 8;
    if (!(f.jet > 0)) prendiIlVolo(f);
    f.volaY = f.p.bacino.y; f.base = f.p.bacino.y + 30 * S;
    f.dir = vx > 0 ? -1 : 1;
    zip(da.x, da.y, COLORI_ANIME[f.tipo]); zip(f.p.bacino.x, f.p.bacino.y, COLORI_ANIME[f.tipo]);
    inizia(f, Math.random() < 0.5 ? "calcio" : "montante"); f.colpito = true;
    // Il colpo arriva subito: si rimanda indietro (l'ultimo della serie giù a terra).
    f.catena = (f.catena || 0) + 1;
    const ultimo = f.catena >= 3 || f.ki < 10;
    colpisci(f, altro, 4.2, (b.x + f.p.collo.x) / 2, (b.y + f.p.collo.y) / 2, ultimo ? "CRASH!" : "BAM!");
    const [nx, ny] = ultimo ? [f.dir * 3, 15] : [-vx * 0.9 / S, -Math.abs(vy) / S * 0.4 - 4];
    for (const n in altro.p) { altro.p[n].ox = altro.p[n].x - nx * S; altro.p[n].oy = altro.p[n].y - verso * ny * S; }
    altro.inVolo = true; altro.ko = Math.max(altro.ko, 40);
    if (!ultimo) f.insegui = 12; else f.catena = 0;
  }
  // Due scatti che si incontrano: onda d'urto e tutti e due respinti.
  function controllaScontro() {
    const [a, b] = lottatori;
    if (!a || !b || !(a.scatto > 0) || !(b.scatto > 0)) return;
    const pa = a.p.bacino, pb = b.p.bacino, d = Math.hypot(pa.x - pb.x, pa.y - pb.y);
    if (d > 34 * S) return;
    const x = (pa.x + pb.x) / 2, y = (pa.y + pb.y) / 2, ux = (pb.x - pa.x) / (d || 1), uy = (pb.y - pa.y) / (d || 1);
    a.scatto = b.scatto = 0;
    for (const [f, s] of [[a, -1], [b, 1]]) {
      for (const n in f.p) { f.p[n].ox = f.p[n].x - s * ux * 7 * S; f.p[n].oy = f.p[n].y - s * uy * 7 * S; }
      f.recupero = 18; f.azione = null; f.pensa = 10;
    }
    for (const k of [0, 6]) if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 24 + k, max: 24 + k, colore: "#ffffff" });
    scintille(x, y, 20, "#ffffff"); scintille(x, y, 10, COLORI_ANIME[a.tipo]); scintille(x, y, 10, COLORI_ANIME[b.tipo]);
    scossa = Math.max(scossa, 12); fermoColpo = 6;
  }

  // --- Le mosse speciali dei super guerrieri (02/10/2026) -----------------
  // Tutte nostre, col sapore degli anime di combattimento: la sfera gigante
  // che raccoglie energia da tutta la pagina, il disco tagliente, il lampo
  // che acceca, la barriera, e l'autodistruzione avvinghiati all'avversario
  // (che resta a terra in un cratere).
  function mossaSpeciale(f, altro) {
    const b = f.p.bacino, ob = altro.p.bacino, d = Math.hypot(ob.x - b.x, ob.y - b.y) / S;
    if (maghi()) return incantesimo(f, altro);
    // La trasformazione: a piena energia, o quando si sta per perdere.
    if (stile === "guerrieri" && !(f.potenziato > 0) && d > 40 &&
        ((f.ki >= 90 && Math.random() < 0.5) || (f.ki >= 40 && f.danni >= f.soglia - 1 && Math.random() < 0.45))) {
      f.ki = 100; inizia(f, "trasforma"); return true;
    }
    // Con le spalle al muro: ci si avvinghia e ci si fa saltare in aria.
    if (f.ki >= 30 && d < 320 && (f.danni >= f.soglia - 1 ? Math.random() < 0.3 : Math.random() < 0.02)) { inizia(f, "avvinghia"); return true; }
    // L'altro sta preparando qualcosa di grosso: barriera.
    if (f.ki >= 20 && (altro.azione === "onda" || altro.azione === "raffica" || altro.azione === "disco" || altro.sfera) && Math.random() < 0.4) { inizia(f, "barriera"); return true; }
    if (f.ki >= 85 && d > 110 && Math.random() < 0.35) { inizia(f, "sfera"); return true; }
    if (f.ki >= 60 && d > 50 && !altro.tenuto && (altro.stordito > 0 || altro.accecato > 0 ? Math.random() < 0.5 : Math.random() < 0.06)) { inizia(f, "telecinesi"); return true; }
    if (f.ki >= 25 && d > 70 && Math.random() < 0.12) { inizia(f, "disco"); return true; }
    if (f.ki >= 15 && d < 200 && !(altro.accecato > 0) && Math.random() < 0.07) { inizia(f, "lampo"); return true; }
    return false;
  }
  function eseguiSpeciale(f, altro) {
    if (f.azione === "sfera") {
      const m = { x: (f.p.manoA.x + f.p.manoD.x) / 2, y: Math.min(f.p.manoA.y, f.p.manoD.y) };
      if (f.t < 112 && !f.sfera) { f.caricaSfera = f.ki; f.ki = 0; f.sfera = { x: m.x, y: m.y - 10 * S, r: 4 * S }; }
      if (f.sfera && f.t < 112) {
        const k = f.t / 112;
        f.sfera.r = (4 + 30 * k) * S; f.sfera.x = m.x; f.sfera.y = m.y - 8 * S - f.sfera.r;
        // L'energia arriva da tutta la pagina.
        if (particelle.length < MAX_PARTICELLE) {
          const lato = Math.floor(Math.random() * 3);
          particelle.push({ tipo: "mote", x: lato === 0 ? 0 : lato === 1 ? W : caso(0, W), y: lato === 2 ? pavimento : caso(testataBasso, pavimento),
                            vx: 0, vy: 0, vita: 90, max: 90, verso: f, colore: Math.random() < 0.5 ? "#ffffff" : COLORI_ANIME[f.tipo] });
        }
        if (f.t % 30 === 0) scossa = Math.max(scossa, 2);
      }
      if (f.t === 112 && f.sfera) {
        const s = f.sfera, bx = altro.p.collo.x, by = altro.p.collo.y, d = Math.hypot(bx - s.x, by - s.y) || 1, v = 4.6 * S;
        proiettili.push({ x: s.x, y: s.y, vx: (bx - s.x) / d * v, vy: (by - s.y) / d * v, da: f, vita: 420, grande: true, r: s.r,
                          bersaglio: altro, colore: COLORI_ANIME[f.tipo] });
        f.sfera = null;
      }
    }
    if (f.azione === "disco" && f.t === 30 && f.ki >= 20) {
      f.ki -= 20;
      const m = f.p.manoA, bx = altro.p.collo.x, by = altro.p.collo.y, d = Math.hypot(bx - m.x, by - (m.y - 12 * S)) || 1, v = 10 * S;
      proiettili.push({ x: m.x, y: m.y - 12 * S, vx: (bx - m.x) / d * v, vy: (by - (m.y - 12 * S)) / d * v, da: f, vita: 200, disco: true,
                        colore: COLORI_ANIME[f.tipo] });
    }
    if (f.azione === "lampo" && f.t === 14 && f.ki >= 12) {
      f.ki -= 12;
      const t = f.p.testa;
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "lampo", x: t.x, y: t.y, vx: 0, vy: 0, vita: 14, max: 14, r: 420 * S });
      for (let i = 0; i < 10; i++) scintille(t.x, t.y, 2, "#ffffff");
      const lontano = Math.hypot(altro.p.testa.x - t.x, altro.p.testa.y - t.y) > 520 * S;
      if (orda) {
        // Durante la tregua il lampo non è per l'alleato: ferma per un paio di secondi gli zombie intorno.
        for (const z of orda.zombie) if (vivoZ(z) && Math.abs(z.x - t.x) < 320 * S) { z.botta = Math.max(z.botta, 110); z.lampo = 10; }
      } else if (!lontano && !altro.ko && !altro.esploso && altro.azione !== "barriera") {
        altro.accecato = 170; altro.azione = null; altro.scatto = 0; altro.onda = null;
        if (altro.tel) lasciaCadere(altro);
      }
    }
    if (f.azione === "barriera") {
      f.ki -= 0.25;
      if (f.ki <= 0) { f.ki = 0; f.azione = null; f.pensa = 10; }
    }
    if (f.azione === "avvinghia") eseguiAvvinghia(f, altro);
    if (f.azione === "telecinesi") eseguiTelecinesi(f, altro);
    if (f.azione === "trasforma") eseguiTrasforma(f, altro);
    if (f.azione === "gelo" && f.t === 16 && f.ki >= 20) { f.ki -= 20; lanciaIncanto(f, altro, "gelo"); }
    if (f.azione === "rimpicciolisci" && f.t === 16 && f.ki >= 25) { f.ki -= 25; lanciaIncanto(f, altro, "piccolo"); }
    if (f.azione === "fulmine" && f.t === 18 && f.ki >= 25) { f.ki -= 25; fulmini.push({ x: puntoMira(f, altro).x, t: 0, da: f, punti: null }); }
    if (f.azione === "levita") eseguiLevita(f, altro);
  }
  // La presa a distanza: con una mano alzata si solleva l'avversario, che
  // resta sospeso a braccia e gambe larghe mentre una luce gli cresce dentro;
  // quando il pugno si chiude, va in mille pezzi (e poi si rimonta).
  const TELE_BOTTO = 112;
  function eseguiTelecinesi(f, altro) {
    if (f.t === 1) {
      if (altro.ko || altro.esploso || altro.preso || altro.tenuto || f.ki < 50) { f.azione = null; return; }
      f.ki -= 50;
      if (altro.tel) lasciaCadere(altro);
      if (altro.arma) lasciaArma(altro);
      if (altro.tiene) molla(altro);
      altro.jet = 0; altro.volo = false; altro.scatto = 0; altro.azione = null; altro.onda = null; altro.sfera = null; altro.paracadute = 0;
      altro.tenuto = { da: f, x: altro.p.collo.x, y: altro.p.collo.y, tele: 0 };
      altro.fantasma = true;
      zip(altro.p.bacino.x, altro.p.bacino.y, COLORI_ANIME[f.tipo]);
    }
    const t = altro.tenuto;
    if (!t || t.da !== f || altro.preso || altro.esploso) { f.azione = null; return; }
    t.tele = f.t;
    // Su, piano, fino a mezz'aria; poi fermo lì a tremare.
    const quota = Math.max(testataBasso + 90 * S, Math.min(pavimento - 230 * S, altro.base - 230 * S));
    if (t.y > quota) t.y -= 2.2 * S;
    t.x += caso(-1, 1) * S * Math.min(1, f.t / 60);
    t.x = Math.max(40 * S, Math.min(W - 40 * S, t.x));
    // Braccia e gambe tirate in fuori.
    const c = altro.p.collo;
    for (const n of ["manoA", "manoD", "piedeA", "piedeD"]) {
      const q = altro.p[n], lato = (n.endsWith("A") ? 1 : -1) * altro.dir;
      q.x += lato * 1.1 * S; q.y += (n.startsWith("mano") ? -0.9 : 0.25) * S;
    }
    if (f.t % 6 === 0) scintille(c.x + caso(-12, 12) * S, c.y + caso(-6, 20) * S, 2, "#fff3b0");
    if (f.t > 60) scossa = Math.max(scossa, 2);
    if (f.t >= TELE_BOTTO) {
      altro.tenuto = null;
      esplodiLottatore(altro, f);
      f.azione = null; f.pensa = 30;
    }
  }
  function disegnaTelecinesi(f) {
    // La luce che cresce dentro chi è sollevato, coi raggi che escono.
    const p = f.p, k = Math.min(1, f.tenuto.tele / TELE_BOTTO), x = (p.collo.x + p.bacino.x) / 2, y = (p.collo.y + p.bacino.y) / 2;
    ctx.save();
    const n = 9, lung = (10 + 46 * k) * S * (0.85 + 0.15 * Math.sin(passi * 0.9));
    ctx.fillStyle = "rgba(255,214,90," + (0.35 + 0.4 * k) + ")";
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + 0.3 * Math.sin(passi * 0.1 + i), w = (3 + 4 * k) * S;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a + 1.57) * w, y + Math.sin(a + 1.57) * w);
      ctx.lineTo(x + Math.cos(a) * lung * (i % 2 ? 1 : 0.7), y + Math.sin(a) * lung * (i % 2 ? 1 : 0.7));
      ctx.lineTo(x + Math.cos(a - 1.57) * w, y + Math.sin(a - 1.57) * w);
      ctx.closePath(); ctx.fill();
    }
    for (const [dx, dy, r] of [[0, 0, 1], [-0.6, 0.5, 0.7], [0.6, 0.4, 0.75], [-0.4, -0.6, 0.6], [0.5, -0.5, 0.65], [0, 0.9, 0.6]]) {
      const rr = (4 + 15 * k) * S * r, g = ctx.createRadialGradient(x + dx * rr, y + dy * rr, 0, x + dx * rr, y + dy * rr, rr);
      g.addColorStop(0, "rgba(255,255,235," + (0.5 + 0.45 * k) + ")"); g.addColorStop(1, "rgba(255,190,60,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x + dx * rr, y + dy * rr, rr, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }
  // La barriera ferma tutto, ma costa energia a ogni colpo; finita quella, va in frantumi.
  function barrieraRegge(f, forza, x, y) {
    if (f.azione !== "barriera") return false;
    const costo = 6 + forza * 2.5;
    const c = f.p.collo;
    if (f.ki >= costo) {
      f.ki -= costo;
      scintille(x, y, 8, COLORI_ANIME[f.tipo]);
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 10, max: 10, colore: COLORI_ANIME[f.tipo] });
      fermoColpo = Math.max(fermoColpo, 2);
      return true;
    }
    f.ki = 0; f.azione = null;
    schegge(c.x, c.y, 14, COLORI_ANIME[f.tipo]);
    scrivi("CRASH!", c.x, c.y - 40 * S, false);
    return false;
  }
  // Avvinghiati all'avversario: ci si aggrappa, si lampeggia sempre più in
  // fretta e si salta in aria. Chi si fa esplodere si rimonta; l'altro resta
  // a terra in un cratere.
  function eseguiAvvinghia(f, altro) {
    if (altro.esploso || altro.preso || (altro.ko > 0 && !altro.inVolo)) { f.azione = null; return; }
    const tx = altro.p.collo.x - f.dir * 12 * S, ty = altro.p.collo.y + 2 * S;
    if (f.t === 1) {
      f.ki = Math.max(0, f.ki - 30);
      zip(f.p.bacino.x, f.p.bacino.y, COLORI_ANIME[f.tipo]);
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (altro.jet > 0 && !(f.jet > 0)) prendiIlVolo(f);
    }
    const dx = tx - f.p.collo.x, dy = ty - f.p.collo.y, k = f.t === 1 ? 1 : 0.6;
    for (const n in f.p) { const q = f.p[n]; q.x += dx * k; q.y += dy * k; q.ox += dx * k; q.oy += dy * k; }
    f.cx += dx * k; f.scatto = 0; f.fantasma = true;
    if (f.jet > 0) f.volaY = f.p.bacino.y; else f.base = altro.base;
    // L'altro si divincola ma non si libera (quasi mai).
    altro.stordito = Math.max(altro.stordito, 4); altro.dolore = 8; altro.azione = null; altro.scatto = 0;
    for (const n of ["manoA", "manoD", "testa"]) altro.p[n].ox += caso(-1.5, 1.5) * S;
    if (f.t === 44 && altro.ki >= 35 && Math.random() < 0.25) {
      altro.ki -= 35;
      for (const n in f.p) { f.p[n].ox = f.p[n].x + f.dir * 9 * S; f.p[n].oy = f.p[n].y + 4 * S; }
      f.azione = null; f.stordito = 40; f.inVolo = true; f.ko = Math.max(f.ko, 30);
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: altro.p.collo.x, y: altro.p.collo.y, vx: 0, vy: 0, vita: 16, max: 16, colore: COLORI_ANIME[altro.tipo] });
      return;
    }
    const ogni = Math.max(2, Math.round(12 - f.t / 8));
    if (f.t % ogni === 0) scintille(f.p.collo.x, f.p.collo.y, 3, "#ff7a1a");
    if (f.t > 50) scossa = Math.max(scossa, 2);
    if (f.t >= 82) autodistruzione(f, altro);
  }
  function autodistruzione(f, altro) {
    f.azione = null;
    const giaKO = altro.koVero;
    esplodiLottatore(f, null, true);
    if (altro.esploso) return;
    if (!altro.koVero) segnaKO(f, altro);
    else if (!giaKO) { punteggio[f.tipo]++; controllaFinale(f.tipo, null, null); }
    altro.ko = 340; altro.inVolo = true; altro.jet = 0; altro.volo = false; altro.accecato = 0; altro.danni = 0;
    // Giù di schianto: dove tocca terra si apre il cratere.
    for (const n in altro.p) { altro.p[n].ox = altro.p[n].x - caso(-1, 1) * S; altro.p[n].oy = altro.p[n].y - verso * 12 * S; }
    altro.cratere = { attesa: true };
  }
  // La posa nel cratere: sdraiato di fianco, un braccio piegato sotto, un
  // ginocchio alzato.
  const POSA_CRATERE = { bacino: [2, 7], collo: [-17, 6], testa: [-28, 5.5], gomitoA: [-12, 3], manoA: [-22, 2.5],
                         gomitoD: [-20, 13], manoD: [-12, 8], ginocchioA: [13, 14], piedeA: [11, 2.5], ginocchioD: [15, 4], piedeD: [27, 3] };
  function posaCratere(f) {
    const c = f.cratere, q = {};
    for (const n in POSA_CRATERE) q[n] = [c.x + POSA_CRATERE[n][0] * c.dir * S, c.y - verso * POSA_CRATERE[n][1] * S];
    return q;
  }
  function aggiornaCratere(f) {
    const c = f.cratere;
    if (!c) return;
    if (c.attesa) {
      const b = f.p.bacino, v = Math.hypot(b.x - b.ox, b.y - b.oy);
      c.cadute = (c.cadute || 0) + 1;
      const giu = Math.abs(f.base - b.y) < 22 * S;
      if ((giu && v < 5 * S) || c.cadute > 200) {
        f.cratere = { x: b.x, y: f.base, t: 0, dir: f.dir, sassi: [0, 1, 2, 3, 4, 5, 6].map(() => [caso(-1, 1), caso(0.6, 1.4), caso(1.5, 3.5)]) };
        f.inVolo = false;          // fermo nel cratere: il conto alla rovescia del K.O. parte da qui
        polvere(b.x, f.base - 2, 12); scossa = Math.max(scossa, 10);
        for (let i = 0; i < 10 && particelle.length < MAX_PARTICELLE; i++) {
          particelle.push({ tipo: "detrito", x: b.x + caso(-30, 30) * S, y: f.base - 2, vx: caso(-3, 3) * S, vy: -caso(2, 6) * S * verso,
                            vita: 90, max: 90, rot: 0, va: caso(-0.3, 0.3), lato: caso(1.6, 3.4) * S, colore: "#8a7f70" });
        }
        if (f.base >= pavimento - 2) danneggiaStriscia(b.x, 0.85);
      }
      return;
    }
    c.t++;
    if (f.ko > 0 && !f.esploso) {
      if (c.t % 14 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "fumo", x: c.x + caso(-18, 18) * S, y: c.y - 8 * S, vx: caso(-0.2, 0.2) * S, vy: -caso(0.4, 0.9) * S,
                          vita: 60, max: 60, r: caso(3, 6) * S, colore: "#8d8a85" });
      }
    } else {
      c.fine = (c.fine || 0) + 1;
      if (c.fine > 150) f.cratere = null;
    }
  }
  function disegnaCratere(c) {
    if (!c || c.attesa) return;
    const a = c.fine ? Math.max(0, 1 - c.fine / 150) : Math.min(1, c.t / 8);
    ctx.save(); ctx.globalAlpha = a; ctx.translate(c.x, c.y);
    ctx.fillStyle = "rgba(92,74,54,.34)"; ctx.beginPath(); ctx.ellipse(0, 0, 58 * S, 9 * S, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "rgba(60,46,32,.42)"; ctx.beginPath(); ctx.ellipse(0, 1 * S, 42 * S, 6 * S, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "rgba(40,30,20,.7)"; ctx.lineWidth = 1.2 * S; ctx.lineCap = "round"; ctx.beginPath();
    for (let i = 0; i < 12; i++) {
      const an = (i / 12) * Math.PI * 2 + 0.2, x1 = Math.cos(an) * 44 * S, y1 = Math.sin(an) * 6.5 * S;
      const lung = (16 + (i * 37 % 13)) * S;
      ctx.moveTo(x1, y1); ctx.lineTo(x1 + Math.cos(an) * lung * 0.6, y1 + Math.sin(an) * lung * 0.16 + ((i % 2) ? 1.5 : -1.5) * S);
      ctx.lineTo(x1 + Math.cos(an) * lung, y1 + Math.sin(an) * lung * 0.2);
    }
    ctx.stroke();
    ctx.fillStyle = "#8a7f70";
    for (const [u, k, r] of c.sassi) { ctx.beginPath(); ctx.ellipse(u * 56 * S, -k * 2 * S, r * S, r * 0.7 * S, 0, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function disegnaSferaGrande(x, y, r, colore) {
    ctx.save();
    const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.1, x, y, r);
    g.addColorStop(0, "#ffffff"); g.addColorStop(0.4, colore); g.addColorStop(1, mix(colore, "#000000", 0.3));
    ctx.globalAlpha = 0.3; ctx.fillStyle = colore; ctx.beginPath(); ctx.arc(x, y, r * 1.4, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 0.95; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = mix(colore, "#000000", 0.35); ctx.lineWidth = 1.4 * S; ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 1.2 * S;
    for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.ellipse(x, y, r * 0.95, r * (0.25 + 0.2 * i), passi * 0.05 + i * 1.1, 0, Math.PI * 2); ctx.stroke(); }
    ctx.restore();
  }
  function disegnaDisco(x, y, r, colore) {
    ctx.save(); ctx.translate(x, y);
    ctx.globalAlpha = 0.4; ctx.fillStyle = colore; ctx.beginPath(); ctx.ellipse(0, 0, r * 1.25, r * 0.36, 0, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = "#fff9d0"; ctx.beginPath();
    for (let i = 0; i <= 28; i++) {
      const a = (i / 28) * Math.PI * 2, rr = r * (i % 2 ? 1 : 0.86), ph = a + passi * 0.6;
      const px = Math.cos(ph) * rr, py = Math.sin(ph) * rr * 0.26;
      if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
    }
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = colore; ctx.lineWidth = 1.2 * S; ctx.stroke();
    ctx.restore();
  }
  function disegnaBarriera(f) {
    const p = f.p, x = (p.testa.x + p.bacino.x) / 2, y = (p.testa.y + p.bacino.y) / 2 + 6 * S, r = 44 * S, col = COLORI_ANIME[f.tipo];
    ctx.save();
    const g = ctx.createRadialGradient(x, y, r * 0.55, x, y, r);
    g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(1, col);
    ctx.globalAlpha = 0.3 + 0.08 * Math.sin(passi * 0.3); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 0.85; ctx.strokeStyle = col; ctx.lineWidth = 1.8 * S; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1.4 * S;
    ctx.beginPath(); ctx.arc(x, y, r * 0.86, passi * 0.05, passi * 0.05 + 0.9); ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r * 0.86, passi * 0.05 + Math.PI, passi * 0.05 + Math.PI + 0.5); ctx.stroke();
    ctx.restore();
  }

  // --- I PERSONAGGI NUOVI (02/10/2026, su richiesta) ----------------------
  // Tre stili, tutti disegnati e inventati qui. I SUPER GUERRIERI hanno ora
  // una trasformazione, il «sovraccarico»: anelli di luce sopra la testa,
  // occhi accesi, colpi più forti (e una seconda forma, con tre sfere che
  // orbitano). I MAGHI lottano a incantesimi con la bacchetta e volano sulla
  // scopa. I DUELLANTI hanno una lama di energia: fendenti, affondi, lo
  // scatto che attraversa l'avversario, la lama lanciata, le lame incrociate.

  // ·· La trasformazione: la carica, poi il lampo e il corpo nuovo ··
  function eseguiTrasforma(f, altro) {
    const b = f.p.bacino, col = coloreAnime(f);
    if (f.t < 70) {
      // La carica: la pagina trema sempre di più e chi è vicino viene tenuto lontano.
      f.ki = 100;
      scossa = Math.max(scossa, 1 + f.t / 14);
      if (f.t % 2 === 0 && particelle.length < MAX_PARTICELLE) {
        particelle.push({ tipo: "scintilla", x: b.x + caso(-20, 20) * S, y: f.base - 2 * S, vx: caso(-0.3, 0.3) * S, vy: -caso(2.5, 5) * S,
                          vita: 20, max: 20, colore: Math.random() < 0.4 ? "#ffffff" : col });
      }
      if (f.t % 7 === 0 && particelle.length < MAX_PARTICELLE && f.base >= pavimento - 2) {
        particelle.push({ tipo: "detrito", x: f.cx + caso(-34, 34) * S, y: f.base - 2, vx: caso(-0.4, 0.4) * S, vy: -caso(3, 6) * S,
                          vita: 70, max: 70, rot: 0, va: caso(-0.2, 0.2), lato: caso(1.6, 3.2) * S, colore: "#9a948a" });
      }
      if (f.t % 16 === 0 && particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: b.x, y: b.y - 10 * S, vx: 0, vy: 0, vita: 18, max: 18, colore: col });
      const d = altro.p.bacino.x - b.x;
      if (!altro.esploso && !altro.preso && !altro.tenuto && Math.abs(d) < 90 * S && Math.abs(altro.p.bacino.y - b.y) < 90 * S) {
        for (const n in altro.p) altro.p[n].ox -= Math.sign(d || 1) * 0.5 * S;
      }
      return;
    }
    if (f.t !== 70) return;
    if (stile === "guerrieri") {
      f.forma = Math.min(2, (f.potenziato > 0 ? f.forma : 0) + 1);
      f.potenziato = 1500; f.ki = 100;
    } else if (stile === "maghi") { potenzia(f); f.potenziato = 900; }
    else { f.forma = 1; f.potenziato = 900; f.ki = 100; }
    f.danni = Math.max(0, f.danni - 1);
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "lampo", x: b.x, y: b.y - 14 * S, vx: 0, vy: 0, vita: 12, max: 12, r: 240 * S });
    for (const k of [0, 8]) if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x: b.x, y: b.y - 12 * S, vx: 0, vy: 0, vita: 22 + k, max: 22 + k, colore: k ? "#ffffff" : col });
    scintille(b.x, b.y - 14 * S, 26, col); scintille(b.x, b.y - 14 * S, 12, "#ffffff");
    scossa = Math.max(scossa, 14); fermoColpo = Math.max(fermoColpo, 6);
    scrivi(GRIDO_FORMA[formaDi(f)] || (f.forma >= 2 ? "SOVRACCARICO II!" : "SOVRACCARICO!"), b.x, b.y - 62 * S, true);
    // L'onda d'urto sbalza via l'avversario, senza fargli danno.
    // (se anche l'altro si sta trasformando non lo tocca: si trasformano insieme, senza spingersi)
    if (!altro.esploso && !altro.preso && !altro.tenuto && altro.azione !== "trasforma") {
      const d = altro.p.bacino.x - b.x;
      if (Math.hypot(d, altro.p.bacino.y - b.y) < 200 * S) {
        const s = Math.sign(d || f.dir);
        // La spinta non lo butta mai fuori dalla finestra (volando ci finiva, una volta ogni tanto).
        const spinta = Math.max(0, Math.min(8 * S, s > 0 ? (W - 16 * S - altro.p.bacino.x) / 3 : (altro.p.bacino.x - 16 * S) / 3));
        for (const n in altro.p) { altro.p[n].ox -= s * spinta; altro.p[n].oy += verso * 3 * S; }
        altro.azione = null; altro.stordito = Math.max(altro.stordito, 20);
        altro.scatto = 0; altro.onda = null;
        if (altro.tel) lasciaCadere(altro);
      }
    }
  }
  // Finita l'energia si torna normali, col fiatone.
  function fineForma(f) {
    f.forma = 0;
    if (!f.p || f.esploso) return;
    const t = f.p.testa;
    for (let i = 0; i < 8 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "polvere", x: t.x + caso(-10, 10) * S, y: t.y - 14 * S, vx: caso(-1, 1) * S, vy: -caso(0.3, 1.2) * S,
                        vita: 24, max: 28, colore: COLORI_ANIME[f.tipo] });
    }
    if (!f.ko) f.stordito = Math.max(f.stordito, 30);
  }
  function cimaDi(f) {
    const t = f.p.testa, c = f.p.collo, L = Math.hypot(t.x - c.x, t.y - c.y) || 1;
    return { x: t.x + (t.x - c.x) / L * 13 * S, y: t.y + (t.y - c.y) / L * 13 * S };
  }
  function disegnaForma(f) {
    const col = coloreAnime(f), cima = cimaDi(f);
    const y0 = cima.y - 5 * S * verso + Math.sin(passi * 0.08) * 1.2 * S;
    ctx.save();
    ctx.lineCap = "round";
    // Gli anelli sopra la testa: un alone e quattro archi che girano.
    for (let i = 0; i < f.forma; i++) {
      const rx = (11 + 4 * i) * S, ry = (3 + 1.2 * i) * S, yy = y0 - i * 4.5 * S * verso, giro = passi * 0.07 * (i ? -1 : 1);
      ctx.globalAlpha = 0.35; ctx.strokeStyle = col; ctx.lineWidth = 4.5 * S;
      ctx.beginPath(); ctx.ellipse(cima.x, yy, rx, ry, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 1; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.6 * S;
      for (let k = 0; k < 4; k++) { ctx.beginPath(); ctx.ellipse(cima.x, yy, rx, ry, 0, giro + k * Math.PI / 2, giro + k * Math.PI / 2 + 1.1); ctx.stroke(); }
    }
    // Seconda forma: tre sfere in orbita attorno al corpo.
    if (f.forma >= 2) {
      const cx = (f.p.collo.x + f.p.bacino.x) / 2, cy = (f.p.collo.y + f.p.bacino.y) / 2;
      for (let k = 0; k < 3; k++) {
        const a = passi * 0.09 + k * Math.PI * 2 / 3, x = cx + Math.cos(a) * 24 * S, y = cy + Math.sin(a) * 9 * S - 4 * S;
        ctx.globalAlpha = 0.4; tondo(x, y, 4.2 * S, col);
        ctx.globalAlpha = 1; tondo(x, y, 1.9 * S, "#ffffff");
      }
    }
    // Gli occhi accesi lasciano una scia.
    const ox = f.p.testa.x + f.dir * 3 * S, oy = f.p.testa.y;
    ctx.globalAlpha = 0.55; ctx.strokeStyle = col; ctx.lineWidth = 2 * S;
    ctx.beginPath(); ctx.moveTo(ox, oy); ctx.quadraticCurveTo(ox - f.dir * 7 * S, oy - 1 * S, ox - f.dir * 15 * S, oy - (4 + Math.sin(passi * 0.3) * 1.5) * S); ctx.stroke();
    ctx.restore();
  }

  // ·· I maghi ··
  const puntaBacchetta = (f) => {
    const g = f.p.gomitoA, m = f.p.manoA, L = Math.hypot(m.x - g.x, m.y - g.y) || 1;
    return { x: m.x + (m.x - g.x) / L * 14 * S, y: m.y + (m.y - g.y) / L * 14 * S };
  };
  const INCANTI = { gelo: 1, rimpicciolisci: 1, fulmine: 1, levita: 1, raffica: 1, onda: 1, carica: 1, barriera: 1, lampo: 1 };
  // Che incantesimo fare adesso (o nessuno: allora decide il resto del cervello).
  function incantesimo(f, altro) {
    const b = f.p.bacino, ob = altro.p.bacino, d = Math.hypot(ob.x - b.x, ob.y - b.y) / S;
    const fermo = altro.gelato > 0 || altro.stordito > 0 || altro.accecato > 0;
    if (f.ki >= 20 && (altro.azione === "onda" || altro.azione === "raffica" || altro.azione === "fulmine" || altro.azione === "gelo" || altro.azione === "rimpicciolisci") && Math.random() < 0.4) { inizia(f, "barriera"); return true; }
    if (f.ki >= 30 && d > 60 && !altro.tenuto && (fermo ? Math.random() < 0.3 : Math.random() < 0.07)) { inizia(f, "levita"); return true; }
    if (f.ki >= 25 && Math.random() < (fermo ? 0.35 : 0.12)) { inizia(f, "fulmine"); return true; }
    if (f.ki >= 20 && d > 50 && !(altro.gelato > 0) && Math.random() < 0.12) { inizia(f, "gelo"); return true; }
    if (f.ki >= 25 && d > 50 && !(altro.piccolo > 0) && Math.random() < 0.08) { inizia(f, "rimpicciolisci"); return true; }
    if (f.ki >= 15 && d < 200 && !(altro.accecato > 0) && Math.random() < 0.05) { inizia(f, "lampo"); return true; }
    return false;
  }
  function lanciaIncanto(f, altro, tipo) {
    const m = puntaBacchetta(f), bx = altro.p.collo.x, by = (altro.p.collo.y + altro.p.bacino.y) / 2;
    const d = Math.hypot(bx - m.x, by - m.y) || 1, v = 8.5 * S;
    proiettili.push({ x: m.x, y: m.y, vx: (bx - m.x) / d * v, vy: (by - m.y) / d * v, da: f, vita: 170, energia: true, incanto: tipo,
                      colore: tipo === "gelo" ? "#7fd4f7" : "#b77bff" });
    scintille(m.x, m.y, 6, tipo === "gelo" ? "#dff6ff" : "#e4ccff");
  }
  // Il gelo: chi lo prende resta in un blocco di ghiaccio, fermo com'era. Il
  // blocco cade e si appoggia sul piede più basso; un colpo lo manda in pezzi.
  function congela(f, da, x, y) {
    suona("gelo", x);
    if (f.esploso || f.preso || f.tenuto || barrieraRegge(f, 3, x, y)) return;
    if (f.tel) lasciaCadere(f);
    if (f.tiene) molla(f);
    f.azione = null; f.scatto = 0; f.onda = null; f.sfera = null; f.jet = 0; f.volo = false; f.caos = 0; f.paracadute = 0; f.scalata = null;
    f.gelato = 190;
    const anc = (f.p.piedeA.y - f.p.piedeD.y) * verso >= 0 ? "piedeA" : "piedeD", a = f.p[anc];
    f.ghiaccio = { anc, off: {} };
    for (const n in f.p) f.ghiaccio.off[n] = { x: f.p[n].x - a.x, y: f.p[n].y - a.y };
    scintille(x, y, 10, "#dff6ff");
    scrivi("BRRR!", f.p.collo.x, f.p.collo.y - 34 * S, false);
    if (da && da.p) da.ki = Math.min(100, da.ki + 3);
  }
  function rompiGhiaccio(f, forte) {
    f.gelato = 0; f.ghiaccio = null;
    const c = f.p.collo;
    schegge(c.x, c.y + 8 * S, forte ? 16 : 8, "#bfeaff");
    if (forte) scrivi("CRACK!", c.x, c.y - 34 * S, false);
    if (!f.ko) f.stordito = Math.max(f.stordito, forte ? 12 : 24);
  }
  function disegnaGhiaccio(f) {
    let l = 1e9, t = 1e9, r = -1e9, b = -1e9;
    for (const n in f.p) { const q = f.p[n]; l = Math.min(l, q.x - q.r); r = Math.max(r, q.x + q.r); t = Math.min(t, q.y - q.r); b = Math.max(b, q.y + q.r); }
    l -= 9 * S; r += 9 * S; t -= 12 * S; b += 2 * S;
    const k = Math.min(1, f.gelato / 20), s = 7 * S;
    ctx.save();
    const g = ctx.createLinearGradient(l, t, r, b);
    g.addColorStop(0, "#eefbff"); g.addColorStop(1, "#86cdf0");
    ctx.fillStyle = g; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.6 * S; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(l + s, t); ctx.lineTo(r - s * 0.6, t + s * 0.3); ctx.lineTo(r, t + s * 1.4); ctx.lineTo(r - s * 0.3, b);
    ctx.lineTo(l + s * 0.4, b); ctx.lineTo(l, b - s); ctx.lineTo(l + s * 0.2, t + s); ctx.closePath();
    ctx.globalAlpha = 0.1 + 0.42 * k; ctx.fill();
    ctx.globalAlpha = 0.9 * k; ctx.stroke();
    ctx.strokeStyle = "#3f9fd0"; ctx.lineWidth = 0.9 * S; ctx.globalAlpha = 0.6 * k; ctx.stroke();
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.3 * S; ctx.globalAlpha = 0.85 * k; ctx.lineCap = "round"; ctx.beginPath();
    ctx.moveTo(l + s * 1.3, t + s * 1.2); ctx.lineTo(l + s * 1.0, t + (b - t) * 0.5);
    ctx.moveTo(l + s * 2.1, t + s); ctx.lineTo(l + s * 1.9, t + s * 2.4); ctx.stroke();
    ctx.restore();
  }
  // Rimpicciolito: per qualche secondo si è alti la metà e i colpi contano la metà.
  function rimpicciolisci(f, da, x, y) {
    if (f.esploso || barrieraRegge(f, 3, x, y)) return;
    f.piccolo = 520;
    const c = f.p.collo;
    for (let i = 0; i < 10 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "polvere", x: c.x + caso(-14, 14) * S, y: c.y + caso(-10, 24) * S, vx: caso(-1.4, 1.4) * S, vy: caso(-1.2, 0.2) * S,
                        vita: Math.round(caso(18, 30)), max: 30, colore: "#c9a6ff" });
    }
    scrivi("PUFF!", c.x, c.y - 30 * S, false);
    if (da && da.p) da.ki = Math.min(100, da.ki + 3);
  }
  // Il fulmine: un attimo di preavviso, poi cade dal tetto dove stava l'avversario.
  let fulmini = [];
  function aggiornaFulmini() {
    for (const z of fulmini) {
      if (++z.t !== 12) continue;
      const f = z.da;
      const sotto = (l) => !!(l && l.p && !l.esploso && !l.fuori && !l.preso && Math.abs(l.p.collo.x - z.x) < 20 * S);
      const altro = z.cielo ? lottatori.find(sotto) : (z.contro || lottatori.find((l) => l !== f));
      const preso = sotto(altro);
      const giu = preso ? altro.p.testa.y : pavimento;
      const n = 7;
      z.punti = [[z.x + caso(-30, 30) * S, 0]];
      for (let i = 1; i <= n; i++) z.punti.push([z.x + (i === n ? 0 : caso(-14, 14) * S), giu * i / n]);
      const m = z.punti[3];
      z.ramo = [m, [m[0] + caso(18, 34) * S * (Math.random() < 0.5 ? -1 : 1), m[1] + caso(20, 44) * S]];
      danneggiaBordo("tetto", z.punti[0][0], 0.6);
      scossa = Math.max(scossa, 9); fermoColpo = Math.max(fermoColpo, 3);
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "lampo", x: z.x, y: giu, vx: 0, vy: 0, vita: 8, max: 8, r: 150 * S });
      if (orda) for (const w of orda.zombie) if (vivoZ(w) && Math.abs(w.x - z.x) < 24 * S) colpisciZombie(w, 9, w.x >= z.x ? 1 : -1, w.x, corpoZ(w)[1], f && f.p ? f : null);
      if (preso && f && (f.p || f.creatura)) {
        const prima = f.dir;
        if (f.p) f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        colpisci(f, altro, z.forza || 6.2, z.x, altro.p.collo.y, "KRAK!");
        f.dir = prima;
        if (!altro.ko) altro.stordito = Math.max(altro.stordito, 40);
      } else {
        danneggiaStriscia(z.x, 0.7); scintille(z.x, pavimento - 2, 12, "#fff3b0");
        scrivi("KRAK!", z.x, pavimento - 40 * S, false);
      }
    }
    if (fulmini.length) fulmini = fulmini.filter((z) => z.t < 22);
  }
  function disegnaFulmine(z) {
    ctx.save(); ctx.lineCap = "round"; ctx.lineJoin = "round";
    if (!z.punti) {
      // Il preavviso: un filo di luce e un cerchio a terra.
      ctx.globalAlpha = 0.2 + 0.2 * (z.t % 4 < 2 ? 1 : 0); ctx.strokeStyle = "#fff3b0"; ctx.lineWidth = 1.2 * S;
      ctx.beginPath(); ctx.moveTo(z.x, 0); ctx.lineTo(z.x, pavimento); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(z.x, pavimento - 1, (6 + z.t * 1.4) * S, (2 + z.t * 0.3) * S, 0, 0, Math.PI * 2); ctx.stroke();
    } else {
      const k = Math.max(0, (22 - z.t) / 10);
      const traccia = () => {
        ctx.beginPath(); ctx.moveTo(z.punti[0][0], z.punti[0][1]);
        for (let i = 1; i < z.punti.length; i++) ctx.lineTo(z.punti[i][0], z.punti[i][1]);
        ctx.moveTo(z.ramo[0][0], z.ramo[0][1]); ctx.lineTo(z.ramo[1][0], z.ramo[1][1]);
      };
      ctx.globalAlpha = 0.45 * k; ctx.strokeStyle = "#ffe27a"; ctx.lineWidth = 9 * S; traccia(); ctx.stroke();
      ctx.globalAlpha = Math.min(1, k); ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2.6 * S; traccia(); ctx.stroke();
    }
    ctx.restore();
  }
  // La levitazione: la bacchetta alza l'avversario a mezz'aria, lo tiene lì
  // un momento e lo lascia cadere di schianto.
  function eseguiLevita(f, altro) {
    if (f.t === 1) {
      if (altro.ko || altro.esploso || altro.preso || altro.tenuto || f.ki < 30) { f.azione = null; return; }
      f.ki -= 30;
      if (altro.tel) lasciaCadere(altro);
      if (altro.arma) lasciaArma(altro);
      if (altro.tiene) molla(altro);
      altro.jet = 0; altro.volo = false; altro.scatto = 0; altro.azione = null; altro.onda = null; altro.sfera = null; altro.paracadute = 0;
      altro.tenuto = { da: f, x: altro.p.collo.x, y: altro.p.collo.y, y0: altro.p.collo.y, tele: 0, magia: true };
      altro.fantasma = true;
    }
    const t = altro.tenuto;
    if (!t || t.da !== f || altro.preso || altro.esploso) { f.azione = null; return; }
    t.tele = f.t;
    if (f.t < 70) {
      const su = t.y - verso * 2.4 * S;
      if ((t.y0 - t.y) * verso < 160 * S && su > testataBasso + 70 * S && su < pavimento - 50 * S) t.y = su;
      t.x = Math.max(40 * S, Math.min(W - 40 * S, t.x + Math.sin(f.t * 0.2) * 1.2 * S));
    }
    if (f.t >= 78) {
      // Giù di schianto: la botta, all'arrivo, conta come un colpo.
      altro.tenuto = null;
      for (const n in altro.p) { altro.p[n].ox = altro.p[n].x; altro.p[n].oy = altro.p[n].y - verso * 15 * S; }
      altro.inVolo = true; altro.ko = Math.max(altro.ko, 60); altro.caduta = f;
      f.azione = null; f.pensa = 20;
    }
  }
  function disegnaLevitazione(f) {
    const p = f.p, x = (p.collo.x + p.bacino.x) / 2, y = (p.collo.y + p.bacino.y) / 2, col = COLORI_ANIME[f.tenuto.da.tipo];
    ctx.save();
    ctx.globalAlpha = 0.16; ctx.fillStyle = col; ctx.beginPath();
    ctx.moveTo(x - 9 * S, y + 26 * S); ctx.lineTo(x + 9 * S, y + 26 * S); ctx.lineTo(x + 22 * S, pavimento); ctx.lineTo(x - 22 * S, pavimento); ctx.closePath(); ctx.fill();
    ctx.globalAlpha = 1;
    for (let i = 0; i < 6; i++) {
      const a = passi * 0.12 + i * Math.PI / 3;
      stella(x + Math.cos(a) * 27 * S, y + Math.sin(a) * 10 * S, 2.3 * S, i % 2 ? "#ffffff" : col);
    }
    ctx.restore();
  }
  function disegnaBacchetta(f) {
    if ((f.staccati && f.staccati.A) || f.tel || f.arma) return;
    const m = f.p.manoA, q = puntaBacchetta(f), col = COLORI_ANIME[f.tipo], lancia = !!INCANTI[f.azione];
    linea(m, q, 2.1 * S, "#5a3a1e");
    linea({ x: m.x + (q.x - m.x) * 0.72, y: m.y + (q.y - m.y) * 0.72 }, q, 1.5 * S, "#f3e3c2");
    ctx.save();
    ctx.globalAlpha = lancia ? 0.55 : 0.3; tondo(q.x, q.y, (lancia ? 4.5 + Math.sin(passi * 0.6) : 2.6) * S, col);
    ctx.globalAlpha = 1; tondo(q.x, q.y, 1.3 * S, "#ffffff");
    ctx.restore();
  }
  // In volo i maghi stanno a cavallo di una scopa.
  function disegnaScopa(f) {
    const b = f.p.bacino, d = f.dir, y = b.y + 5 * S;
    const testa = { x: b.x + d * 26 * S, y: y - 3 * S }, coda = { x: b.x - d * 20 * S, y: y + 2 * S };
    const sv = Math.sin(passi * 0.5) * 1.2 * S;
    ctx.save();
    ctx.fillStyle = "#d9a441"; ctx.strokeStyle = "#8a6420"; ctx.lineWidth = 1 * S; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(coda.x, coda.y - 2.2 * S); ctx.lineTo(coda.x - d * 16 * S, coda.y - 6 * S + sv);
    ctx.lineTo(coda.x - d * 19 * S, coda.y + 1 * S - sv); ctx.lineTo(coda.x - d * 15 * S, coda.y + 7 * S + sv);
    ctx.lineTo(coda.x, coda.y + 2.6 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.restore();
    linea(coda, testa, 2.4 * S, "#7a5230");
    linea({ x: coda.x, y: coda.y - 2.6 * S }, { x: coda.x, y: coda.y + 3 * S }, 1.8 * S, "#5a3a1e");
  }

  // ·· I duellanti ··
  const TAGLI = { fendente: 1, affondo: 1, rovescio: 1 };
  const lamaPronta = (f) => !!(stile === "lame" && f.lama && !f.lama.lanciata && !(f.staccati && f.staccati.A) && !f.tel && !f.arma);
  function accendiLama(f) { f.lama = { acceso: 0, lanciata: false, fuori: 0, scia: [] }; }
  // Base e punta della lama, nella finestra: continua l'avambraccio.
  function lamaDi(f) {
    const g = f.p.gomitoA, m = f.p.manoA, L = Math.hypot(m.x - g.x, m.y - g.y) || 1;
    const ux = (m.x - g.x) / L, uy = (m.y - g.y) / L, lung = 31 * S * Math.min(1, f.lama ? f.lama.acceso : 1);
    return { x0: m.x + ux * 4 * S, y0: m.y + uy * 4 * S, x1: m.x + ux * (4 * S + lung), y1: m.y + uy * (4 * S + lung), ux, uy, lung };
  }
  let duello = 0;
  function pensaLama(f, altro) {
    if (!lamaPronta(f)) return false;
    if (Math.abs(altro.base - f.base) > 40 * S) return false;      // livelli diversi: scale e discese come sempre
    const d = Math.abs(altro.cx - f.cx) / S;
    f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
    if (duello > 0 && lamaPronta(altro) && !altro.stordito && !(altro.jet > 0)) {
      // Chiesto dalla tendina: ci si viene incontro e si colpisce insieme.
      if (d > 44) { inizia(f, "avanza", altro.cx - f.dir * 34 * S); return true; }
      inizia(f, "fendente");
      if (!TAGLI[altro.azione]) { altro.dir = -f.dir; inizia(altro, "fendente"); }
      return true;
    }
    if (altro.azione && (TAGLI[altro.azione] || altro.azione === "scattoLama") && d < 60 && Math.random() < 0.35 * f.furbo) { inizia(f, "para"); return true; }
    if (d <= 44) {
      inizia(f, scegli([[30 * f.aggr, "fendente"], [24 * f.aggr, "affondo"], [20, "rovescio"], [8 * f.furbo, "para"], [8, "indietro"]]));
      return true;
    }
    if (altro.jet > 0 && verso > 0 && Math.random() < 0.3) { decolla(f, false); return true; }
    if (d > 60 && d < 260 && !(altro.jet > 0) && Math.random() < 0.28) { inizia(f, "scattoLama"); return true; }
    if (d > 150 && Math.random() < 0.1) { inizia(f, "lancioLama"); return true; }
    inizia(f, "avanza", altro.cx - f.dir * 34 * S);
    return true;
  }
  function eseguiLama(f, altro) {
    if (f.azione === "scattoLama") {
      if (f.t === 1) { f.daScatto = null; if (!lamaPronta(f)) { f.azione = null; return; } }
      if (f.t === 10) {
        // Dall'altra parte dell'avversario in quattro fotogrammi.
        const arrivo = Math.max(24 * S, Math.min(W - 24 * S, altro.p.bacino.x + f.dir * 46 * S));
        f.daScatto = { passo: (arrivo - f.p.bacino.x) / 4, parato: altro.azione === "para" && altro.dir === -f.dir, dir: f.dir, vale: false };
      }
      const ds = f.daScatto;
      if (!ds) return;
      if (f.t >= 10 && f.t < 14) {
        residua(f);
        for (const n in f.p) { f.p[n].x += ds.passo; f.p[n].ox += ds.passo; }
        f.cx += ds.passo; f.meta = f.cx; f.fantasma = true;
        if (particelle.length < MAX_PARTICELLE) {
          particelle.push({ tipo: "linea", x: f.p.bacino.x, y: f.p.bacino.y + caso(-16, 10) * S, vx: -ds.dir * 3 * S, vy: 0, vita: 10, max: 10,
                            lung: caso(16, 34) * S, colore: COLORI_ANIME[f.tipo] });
        }
      }
      if (f.t === 14) {
        const c = altro.p.collo, y = (c.y + altro.p.bacino.y) / 2;
        const passato = (f.p.bacino.x - altro.p.bacino.x) * ds.dir > 0;
        const vicino = Math.abs(altro.p.bacino.y - f.p.bacino.y) < 50 * S && !altro.esploso && !altro.preso && !altro.tenuto;
        if (particelle.length < MAX_PARTICELLE) {
          particelle.push({ tipo: "taglio", x: c.x, y, vx: 0, vy: 0, vita: 26, max: 26, ang: -ds.dir * caso(0.2, 0.5), lung: 46 * S, colore: COLORI_ANIME[f.tipo] });
        }
        if (passato && vicino) {
          if (ds.parato) { scintille(c.x, y, 12, "#ffffff"); scrivi("CLANG!", c.x, y - 12 * S, false); fermoColpo = Math.max(fermoColpo, 3); }
          else { ds.vale = true; altro.azione = null; altro.scatto = 0; if (!altro.ko) altro.stordito = Math.max(altro.stordito, 20); }
        }
      }
      if (f.t === 32) {
        // Si volta a guardare: solo adesso il taglio fa effetto.
        f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        if (ds.vale && !altro.esploso && !altro.preso) colpisci(f, altro, 6.2, altro.p.collo.x, (altro.p.collo.y + altro.p.bacino.y) / 2, "ZAC!");
      }
    }
    if (f.azione === "lancioLama" && f.t === 14 && lamaPronta(f)) {
      const l = lamaDi(f), bx = altro.p.collo.x, by = altro.p.collo.y, d = Math.hypot(bx - l.x0, by - l.y0) || 1, v = 10.5 * S;
      proiettili.push({ x: l.x0, y: l.y0, vx: (bx - l.x0) / d * v, vy: (by - l.y0) / d * v, da: f, vita: 170, disco: true, lamaDi: f,
                        colore: COLORI_ANIME[f.tipo] });
      f.lama.lanciata = true; f.lama.fuori = 0;
    }
    if (f.azione === "pressa") {
      // Lame incrociate: ci si spinge, piovono scintille, e alla fine uno dei due cede.
      if (altro.azione !== "pressa") { f.azione = null; f.pensa = 6; return; }
      f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
      if (f.tipo !== "robot") return;                // i conti si fanno una volta sola per coppia
      const la = lamaDi(f), lb = lamaDi(altro), x = (la.x1 + lb.x1) / 2, y = (la.y1 + lb.y1) / 2;
      if (f.t % 2 === 0) scintille(x, y, 2, f.t % 4 ? "#ffffff" : "#ffe27a");
      if (f.t % 12 === 0) scossa = Math.max(scossa, 2);
      const spinta = Math.sin(f.t * 0.21) * 0.5 * S * f.dir;
      f.cx += spinta; altro.cx += spinta;
      if (f.t >= 44) {
        // Come nello scontro di energie, niente dadi: la spinta di ognuno (vedi `spintaDi`) per la grinta del round.
        const vince = spintaDi(f) * f.aggr >= spintaDi(altro) * altro.aggr ? f : altro, perde = vince === f ? altro : f;
        for (const n in perde.p) { perde.p[n].ox -= vince.dir * 6 * S; perde.p[n].oy += verso * 1.5 * S; }
        perde.azione = null; perde.stordito = Math.max(perde.stordito, 34);
        vince.azione = null; vince.pensa = 2; vince.combo = 1;
        scintille(x, y, 10, "#ffffff");
        scrivi("SWISH!", x, y - 12 * S, false);
      }
    }
  }
  // Due lame che si incontrano a metà colpo: nessuno dei due va a segno.
  function controllaLame(a, b) {
    if (!TAGLI[a.azione] || !TAGLI[b.azione] || a.colpito || b.colpito || !lamaPronta(a) || !lamaPronta(b)) return;
    const ra = COLPI[a.azione], rb = COLPI[b.azione];
    if (a.t < ra[1] - 2 || a.t > ra[2] || b.t < rb[1] - 2 || b.t > rb[2]) return;
    const la = lamaDi(a), lb = lamaDi(b);
    const ax = (la.x0 + la.x1) / 2, ay = (la.y0 + la.y1) / 2, bx = (lb.x0 + lb.x1) / 2, by = (lb.y0 + lb.y1) / 2;
    if (Math.hypot(ax - bx, ay - by) > 28 * S) return;
    const x = (ax + bx) / 2, y = (ay + by) / 2;
    a.colpito = b.colpito = true;
    scintille(x, y, 14, "#ffffff"); scintille(x, y, 6, COLORI_ANIME.robot); scintille(x, y, 6, COLORI_ANIME.mela);
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 12, max: 12, colore: "#ffffff" });
    scrivi("CLANG!", x, y - 12 * S, false);
    scossa = Math.max(scossa, 5); fermoColpo = Math.max(fermoColpo, 4);
    if ((duello > 0 || Math.random() < 0.5) && !(a.jet > 0) && !(b.jet > 0)) {
      duello = 0;
      inizia(a, "pressa"); inizia(b, "pressa");
      return;
    }
    const dir = Math.sign(b.cx - a.cx) || 1;
    for (const [f, s] of [[a, -1], [b, 1]]) {
      for (const n in f.p) f.p[n].ox -= s * dir * 3.5 * S;
      f.azione = null; f.pensa = Math.round(caso(4, 12));
    }
  }
  function aggiornaLame() {
    if (duello > 0) duello--;
    for (const f of lottatori) {
      const L = f.lama;
      if (!L) continue;
      L.acceso = Math.min(1, L.acceso + 0.12);
      if (L.lanciata && ++L.fuori > 240) rientraLama(f);
      const colpo = lamaPronta(f) && !f.esploso && (TAGLI[f.azione] || (f.azione === "scattoLama" && f.t >= 9 && f.t <= 16));
      if (colpo) { const l = lamaDi(f); L.scia.push({ x0: l.x0, y0: l.y0, x1: l.x1, y1: l.y1 }); if (L.scia.length > 6) L.scia.shift(); }
      else if (L.scia.length) L.scia.shift();
    }
  }
  // La lama lanciata torna in mano: si riaccende da capo.
  function rientraLama(f) {
    if (!f || !f.lama) return;
    f.lama.lanciata = false; f.lama.fuori = 0; f.lama.acceso = 0;
    if (f.p && !f.esploso) scintille(f.p.manoA.x, f.p.manoA.y, 6, COLORI_ANIME[f.tipo]);
  }
  function sagomaLama(x0, y0, x1, y1, larg) {
    const L = Math.hypot(x1 - x0, y1 - y0) || 1, ux = (x1 - x0) / L, uy = (y1 - y0) / L, nx = -uy * larg, ny = ux * larg, punta = Math.min(6 * S, L * 0.4);
    ctx.beginPath(); ctx.moveTo(x0 + nx, y0 + ny);
    ctx.lineTo(x1 - ux * punta + nx * 0.75, y1 - uy * punta + ny * 0.75); ctx.lineTo(x1, y1);
    ctx.lineTo(x1 - ux * punta - nx * 0.75, y1 - uy * punta - ny * 0.75); ctx.lineTo(x0 - nx, y0 - ny); ctx.closePath(); ctx.fill();
  }
  function disegnaLama(f) {
    const L = f.lama;
    if (!L || L.lanciata || (f.staccati && f.staccati.A) || f.tel || f.arma) return;
    const l = lamaDi(f), col = COLORI_ANIME[f.tipo], m = f.p.manoA;
    const doppia = formaDi(f) === "cavaliere";
    ctx.save(); ctx.lineCap = "round";
    // La scia del colpo.
    ctx.fillStyle = col;
    for (let i = 1; i < L.scia.length; i++) {
      const a = L.scia[i - 1], b = L.scia[i];
      ctx.globalAlpha = 0.3 * i / L.scia.length;
      ctx.beginPath(); ctx.moveTo(a.x0, a.y0); ctx.lineTo(a.x1, a.y1); ctx.lineTo(b.x1, b.y1); ctx.lineTo(b.x0, b.y0); ctx.closePath(); ctx.fill();
    }
    ctx.globalAlpha = 1;
    // L'impugnatura scura, con la guardia del colore della lama.
    linea({ x: m.x - l.ux * 5 * S, y: m.y - l.uy * 5 * S }, { x: l.x0, y: l.y0 }, 3.2 * S, "#23262e");
    linea({ x: m.x - l.ux * 5.5 * S, y: m.y - l.uy * 5.5 * S }, { x: m.x - l.ux * 4.5 * S, y: m.y - l.uy * 4.5 * S }, 4 * S, "#8d96a6");
    linea({ x: l.x0 - l.uy * 4 * S, y: l.y0 + l.ux * 4 * S }, { x: l.x0 + l.uy * 4 * S, y: l.y0 - l.ux * 4 * S }, 2.4 * S, col);
    if (l.lung > 1) {
      // La lama: alone, colore, anima bianca; tremola e finisce a punta.
      // Il cavaliere ne ha due, una per parte della stessa impugnatura.
      const tr = 0.85 + 0.15 * Math.sin(passi * 0.9 + (f.tipo === "mela" ? 2 : 0));
      const lame = [[l.x0, l.y0, l.x1, l.y1]];
      if (doppia) {
        const q = l.lung * 0.78;
        lame.push([m.x - l.ux * 5 * S, m.y - l.uy * 5 * S, m.x - l.ux * (5 * S + q), m.y - l.uy * (5 * S + q)]);
      }
      for (const [x0, y0, x1, y1] of lame) {
        ctx.fillStyle = col; ctx.globalAlpha = 0.28 * tr; sagomaLama(x0, y0, x1, y1, 5.2 * S);
        ctx.globalAlpha = 0.9; sagomaLama(x0, y0, x1, y1, 2.6 * S);
        ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff"; sagomaLama(x0, y0, x1, y1, 1.1 * S);
      }
    }
    ctx.restore();
  }
  function disegnaLamaVolante(b) {
    const a = passi * 0.7, ux = Math.cos(a) * 16 * S, uy = Math.sin(a) * 16 * S;
    ctx.save();
    ctx.fillStyle = b.colore; ctx.globalAlpha = 0.25; ctx.beginPath(); ctx.arc(b.x, b.y, 17 * S, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 0.9; sagomaLama(b.x - ux, b.y - uy, b.x + ux, b.y + uy, 2.6 * S);
    ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff"; sagomaLama(b.x - ux, b.y - uy, b.x + ux, b.y + uy, 1.1 * S);
    ctx.restore();
  }
  // I duellanti portano una sciarpa lunga, del colore della lama.
  function sciarpa(f) {
    const col = COLORI_ANIME[f.tipo], p = f.p;
    const x = p.collo.x - f.dir * 3 * S, y = p.collo.y + 2 * S;
    const lag = Math.max(-10 * S, Math.min(10 * S, (p.collo.ox - p.collo.x) * 6));
    ctx.save(); ctx.strokeStyle = col; ctx.lineCap = "round"; ctx.lineWidth = 3 * S;
    for (const k of [0, 1]) {
      ctx.globalAlpha = k ? 0.7 : 1;
      ctx.beginPath(); ctx.moveTo(x, y);
      ctx.quadraticCurveTo(x - f.dir * 10 * S + lag * 0.5, y + (2 + 5 * k + 2 * Math.sin(passi * 0.2 + k)) * S,
                           x - f.dir * (20 + 3 * k) * S + lag, y + (-2 + 9 * k + 3 * Math.sin(passi * 0.26 + k * 2)) * S);
      ctx.stroke();
    }
    ctx.restore();
  }

  // ·· I personaggi inventati ··
  // Due per stile, uno per lato. Nomi, facce e vestiti sono nostri: non
  // richiamano né il robot né la mela, né personaggi di altri.
  const ASPETTI = {
    guerrieri: {
      robot: { nome: "ZEFIR", pelle: "#e8b98a", capelli: "#22324f", tuta: "#1f8f8a", bordo: "#f4f1e6", maniche: "#e8b98a", gambe: "#22324f", scarpe: "#3a3f4a", testa: "onda" },
      mela: { nome: "BRASA", pelle: "#9a623c", capelli: "#d43d7a", tuta: "#7a1f2b", bordo: "#f0b23a", maniche: "#9a623c", gambe: "#1d1d24", scarpe: "#f0b23a", testa: "treccia" },
    },
    maghi: {
      robot: { nome: "MERLO", pelle: "#f0c9a4", capelli: "#e3e6ea", tuta: "#4b2f8f", bordo: "#ffd84a", maniche: "#4b2f8f", gambe: "#4b2f8f", scarpe: "#5a3a1e", testa: "cappello", cappello: "#4b2f8f", veste: true, barba: true },
      mela: { nome: "ORTICA", pelle: "#c98f6a", capelli: "#e8742a", tuta: "#1f6f7a", bordo: "#bfe36a", maniche: "#1f6f7a", gambe: "#1f6f7a", scarpe: "#2a2a33", testa: "cappello", cappello: "#1f6f7a", veste: true, codini: true },
    },
    lame: {
      robot: { nome: "ROVO", pelle: "#d9a77c", capelli: "#1b1e27", tuta: "#27314a", bordo: "#56e1ff", maniche: "#27314a", gambe: "#1b1e27", scarpe: "#27314a", testa: "visiera" },
      mela: { nome: "SCIA", pelle: "#f1d2b8", capelli: "#ff62d6", tuta: "#e9e6ee", bordo: "#ff62d6", maniche: "#e9e6ee", gambe: "#3a3340", scarpe: "#8a8494", testa: "caschetto" },
    },
  };
  const aspetto = (f) => ASPETTI[stile][f.tipo];
  const nomeProprio = (tipo) => { const n = ASPETTI[stile][tipo].nome; return n.charAt(0) + n.slice(1).toLowerCase(); };
  const scuro = (colore) => mix(colore, "#000000", 0.22);

  const NERO = "#17171c";
  // I capelli del trasformato: ciocche che scendono dietro la testa e si aprono
  // verso l'esterno, con la punta che va in fuori. Arrivano a metà schiena, non oltre.
  function ciocca(x0, y0, x1, y1, w, curva) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy) || 1;
    const nx = -dy / L, ny = dx / L;                              // normale alla ciocca
    const mx = x0 + dx * 0.55 + nx * curva, my = y0 + dy * 0.55 + ny * curva;
    ctx.beginPath();
    ctx.moveTo(x0 + nx * w, y0 + ny * w);
    ctx.quadraticCurveTo(mx + nx * w * 0.8, my + ny * w * 0.8, x1, y1);
    ctx.quadraticCurveTo(mx - nx * w * 0.8, my - ny * w * 0.8, x0 - nx * w, y0 - ny * w);
    ctx.closePath(); ctx.fill(); ctx.stroke();
  }
  function chiomaSuper(f, col, scura) {
    const p = f.p, d = f.dir, t = p.testa, b = p.bacino;
    const giu = Math.hypot(b.x - t.x, b.y - t.y) || 1;
    const on = Math.sin(passi * 0.06) * 2.4 * S;
    const chiaro = mix(col, "#ffffff", 0.3);
    ctx.save(); ctx.lineJoin = "round"; ctx.strokeStyle = NERO; ctx.lineWidth = 1.2 * S;
    // [x della punta (in unità, negativo = dietro), y della punta (in frazioni di schiena), larghezza, curva, tono]
    const ciocche = [[-30, 0.10, 6.5, 7, 1], [-27, 0.42, 7.5, 9, 0], [-20, 0.78, 8, 10, 0],
                     [-12, 0.98, 7.5, 7, 1], [-24, 0.62, 6, 6, 2], [-6, 0.72, 6, 4, 2]];
    for (const [fuori, lungo, largo, curva, tono] of ciocche) {
      ctx.fillStyle = tono === 0 ? scura : tono === 1 ? col : chiaro;
      ciocca(t.x - d * 3 * S, t.y - 4 * S,
             t.x + d * fuori * S + on, t.y + giu * lungo,
             largo * S, -d * curva * S);
    }
    ctx.restore();
  }
  // La cresta del trasformato: ciuffi grossi, ritti e piegati all'indietro, nel colore della forma.
  function crestaSuper(f, col, d) {
    ctx.fillStyle = col; ctx.strokeStyle = NERO; ctx.lineWidth = 1.2 * S; ctx.lineJoin = "round";
    for (const [giro, lun] of [[-0.34, 17], [-0.08, 22], [0.2, 19], [0.5, 14], [0.8, 10]]) {
      const a = -Math.PI / 2 - d * giro, base = 7.2 * S, larg = 0.28;
      const px = Math.cos(a) * (base + lun * S) - d * 5 * S, py = Math.sin(a) * (base + lun * S);
      ctx.beginPath();
      ctx.moveTo(Math.cos(a - larg) * base, Math.sin(a - larg) * base);
      ctx.quadraticCurveTo(Math.cos(a) * (base + lun * 0.55 * S) - d * 1.5 * S, Math.sin(a) * (base + lun * 0.6 * S), px, py);
      ctx.quadraticCurveTo(Math.cos(a + larg) * (base + lun * 0.5 * S), Math.sin(a + larg) * (base + lun * 0.5 * S),
                           Math.cos(a + larg) * base, Math.sin(a + larg) * base);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    // Le due ciocche corte davanti alla fronte.
    for (const lato of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(lato * 4.6 * S, -5.8 * S);
      ctx.lineTo(lato * 9 * S, -11.5 * S);
      ctx.lineTo(lato * 7.8 * S, -4 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    }
  }
  function pugno(gomito, mano, A, colore, lontano, grande) {
    const L = Math.hypot(mano.x - gomito.x, mano.y - gomito.y) || 1, ux = (mano.x - gomito.x) / L, uy = (mano.y - gomito.y) / L;
    // Il polsino, poi la mano.
    linea({ x: mano.x - ux * 5 * S, y: mano.y - uy * 5 * S }, { x: mano.x - ux * 2.4 * S, y: mano.y - uy * 2.4 * S }, (grande ? 6.4 : 4.6) * S, colore);
    ctx.fillStyle = lontano ? scuro(A.pelle) : A.pelle; ctx.strokeStyle = "#17171c"; ctx.lineWidth = 1 * S;
    ctx.beginPath(); ctx.arc(mano.x, mano.y, (grande ? 4.6 : 3.2) * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  }
  // La faccia, nel riferimento della testa (su = -y): cambia con quello che succede.
  function facciaUmana(f, A, luce) {
    const d = f.dir, nero = "#17171c";
    const attacca = !!COLPI[f.azione] || !!TAGLI[f.azione] || ["lancia", "spara", "presa", "rush", "scattoLama", "pressa", "gelo", "rimpicciolisci", "fulmine", "raffica", "onda", "lancioLama", "spingi", "testata"].indexOf(f.azione) >= 0;
    const festa = f.azione === "esulta" || f.azione === "provoca" || f.azione === "balla";
    const urla = f.azione === "trasforma" || f.azione === "carica";
    const ey = -0.6 * S;
    if (A.testa === "visiera") {
      // Il duellante guarda da dietro una visiera accesa.
      ctx.fillStyle = "#12141b"; rettangoloTondo(-7.6 * S + d * 0.8 * S, ey - 2.6 * S, 15.2 * S, 5 * S, 2.2 * S); ctx.fill();
      ctx.strokeStyle = f.ko ? "#5b6170" : A.bordo; ctx.lineWidth = 1.5 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(d * 0.8 * S - 4.6 * S, ey - 0.1 * S); ctx.lineTo(d * 0.8 * S + 4.6 * S, ey - (attacca ? 1 : 0.1) * S * d); ctx.stroke();
    } else if (f.ko || f.rialzo > 30 || f.dolore || f.stordito) {
      occhi(f, 0, ey, 2.8 * S, 1.3 * S, nero);
    } else if (festa) {
      ctx.strokeStyle = nero; ctx.lineWidth = 1.3 * S; ctx.lineCap = "round";
      for (const lato of [-1, 1]) { ctx.beginPath(); ctx.arc(lato * 2.8 * S + d * 1.2 * S, ey + 0.8 * S, 1.5 * S, Math.PI * 1.05, Math.PI * 1.95); ctx.stroke(); }
    } else {
      const batte = Math.floor(passi / 3) % 80 === 0 ? 0.3 : 1;
      for (const lato of [-1, 1]) {
        const x0 = lato * 2.8 * S + d * 1.2 * S;
        ctx.fillStyle = luce || nero; ctx.beginPath(); ctx.ellipse(x0, ey, 1.25 * S, 1.6 * S * batte, 0, 0, Math.PI * 2); ctx.fill();
        if (!luce) tondo(x0 + d * 0.4 * S, ey - 0.5 * S, 0.45 * S, "#ffffff");
        if (attacca || urla || luce) {
          ctx.strokeStyle = nero; ctx.lineWidth = 1.2 * S; ctx.lineCap = "round"; ctx.beginPath();
          ctx.moveTo(x0 - 1.8 * S, ey - (lato === d ? 3.4 : 2.3) * S); ctx.lineTo(x0 + 1.8 * S, ey - (lato === d ? 2.3 : 3.4) * S); ctx.stroke();
        }
      }
    }
    // La bocca.
    const bx = d * 1.6 * S, by = 3.6 * S;
    ctx.strokeStyle = nero; ctx.fillStyle = nero; ctx.lineWidth = 1.2 * S; ctx.lineCap = "round"; ctx.beginPath();
    if (f.ko || f.rialzo > 30) { ctx.ellipse(bx, by, 1.5 * S, 1.1 * S, 0, 0, Math.PI * 2); ctx.stroke(); }
    else if (f.dolore || f.stordito) { ctx.moveTo(bx - 2.2 * S, by + 0.5 * S); ctx.lineTo(bx - 0.7 * S, by - 0.5 * S); ctx.lineTo(bx + 0.7 * S, by + 0.5 * S); ctx.lineTo(bx + 2.2 * S, by - 0.5 * S); ctx.stroke(); }
    else if (urla) { ctx.ellipse(bx, by + 0.3 * S, 2 * S, 2.3 * S, 0, 0, Math.PI * 2); ctx.fill(); }
    else if (attacca) { ctx.ellipse(bx, by, 1.8 * S, 1.3 * S, 0, 0, Math.PI * 2); ctx.fill(); }
    else if (festa) { ctx.moveTo(bx - 2.4 * S, by - 0.6 * S); ctx.quadraticCurveTo(bx, by + 2.6 * S, bx + 2.4 * S, by - 0.6 * S); ctx.closePath(); ctx.fill(); }
    else { ctx.moveTo(bx - 1.8 * S, by); ctx.quadraticCurveTo(bx, by + 1.2 * S, bx + 1.8 * S, by); ctx.stroke(); }
  }
  // Capelli e cappelli, sempre nel riferimento della testa.
  function capoUmano(f, A, bordo, dietro) {
    const d = f.dir, nero = "#17171c", sv = Math.sin(passi * 0.25) * S;
    const lag = Math.max(-5 * S, Math.min(5 * S, (f.p.testa.ox - f.p.testa.x) * 2));
    ctx.strokeStyle = nero; ctx.lineWidth = 1 * S; ctx.lineJoin = "round"; ctx.lineCap = "round";
    if (dietro) {
      // Quello che sta dietro la testa: trecce, codini, la fascia che sventola.
      if (A.testa === "treccia") {
        for (let i = 0; i < 5; i++) {
          const k = i / 4;
          tondo(-d * (7.5 + 3.5 * k) * S + lag * k, (-2 + 15 * k) * S + sv * k, (3.3 - 1.5 * k) * S, A.capelli);
        }
        tondo(-d * 11.4 * S + lag, 14.6 * S + sv, 1.5 * S, bordo);
      } else if (A.codini) {
        for (const k of [0, 1]) tondo(-d * (8 + 2.5 * k) * S + lag * 0.6, (1 + 4 * k) * S + sv * 0.5, (4 - 0.8 * k) * S, A.capelli);
      } else if (A.testa === "onda") {
        ctx.strokeStyle = bordo; ctx.lineWidth = 1.8 * S;
        for (const k of [0, 1]) {
          ctx.beginPath(); ctx.moveTo(-d * 7.6 * S, -3 * S);
          ctx.quadraticCurveTo(-d * 12 * S + lag, (-2 + 3 * k) * S + sv, -d * (16 + 2 * k) * S + lag * 1.5, (0 + 6 * k) * S - sv);
          ctx.stroke();
        }
      }
      return;
    }
    ctx.fillStyle = A.capelli;
    if (A.testa === "onda") {
      // Un ciuffo pettinato all'indietro e la fascia in fronte.
      ctx.beginPath(); ctx.moveTo(d * 7.4 * S, -3.6 * S); ctx.quadraticCurveTo(d * 6 * S, -11.5 * S, -d * 1 * S, -11 * S);
      ctx.quadraticCurveTo(-d * 7 * S, -11.5 * S, -d * 11 * S, -9 * S); ctx.quadraticCurveTo(-d * 8.6 * S, -6 * S, -d * 8.2 * S, 0.5 * S);
      ctx.quadraticCurveTo(-d * 6 * S, -5 * S, d * 7.4 * S, -3.6 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = bordo; ctx.lineWidth = 2 * S; ctx.beginPath(); ctx.moveTo(d * 7.7 * S, -3.3 * S); ctx.quadraticCurveTo(0, -5.2 * S, -d * 7.9 * S, -3 * S); ctx.stroke();
    } else if (A.testa === "treccia") {
      ctx.beginPath(); ctx.moveTo(d * 7.6 * S, -2.4 * S); ctx.quadraticCurveTo(d * 5 * S, -10.6 * S, -d * 2 * S, -9.6 * S);
      ctx.quadraticCurveTo(-d * 9.6 * S, -8.6 * S, -d * 8.4 * S, 1.5 * S); ctx.quadraticCurveTo(-d * 5 * S, -4.4 * S, d * 2 * S, -4.8 * S);
      ctx.quadraticCurveTo(d * 5.4 * S, -4.6 * S, d * 7.6 * S, -2.4 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = bordo; ctx.lineWidth = 1.6 * S; ctx.beginPath(); ctx.moveTo(-d * 6.6 * S, -6.6 * S); ctx.lineTo(-d * 8.8 * S, -2.6 * S); ctx.stroke();
    } else if (A.testa === "cappello") {
      if (A.barba) {
        // Una barba bianca a punta, coi baffi.
        ctx.fillStyle = A.capelli; ctx.beginPath(); ctx.moveTo(-d * 4.6 * S, 1.6 * S); ctx.quadraticCurveTo(d * 2 * S, 3.4 * S, d * 7.6 * S, 1.2 * S);
        ctx.quadraticCurveTo(d * 6.4 * S, 10 * S, d * 2.4 * S + lag * 0.5, 16 * S); ctx.quadraticCurveTo(-d * 2.6 * S, 9 * S, -d * 4.6 * S, 1.6 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      } else {
        // La frangia.
        ctx.beginPath(); ctx.moveTo(d * 7.7 * S, -2.2 * S); ctx.quadraticCurveTo(d * 2 * S, -6.4 * S, -d * 7.9 * S, -3.4 * S);
        ctx.lineTo(-d * 7.4 * S, -5.6 * S); ctx.lineTo(d * 7 * S, -5.6 * S); ctx.closePath(); ctx.fill();
      }
      // Il cappello a punta, con la falda larga, la fascia e una stella.
      ctx.fillStyle = A.cappello; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.moveTo(-7.4 * S, -5.4 * S); ctx.quadraticCurveTo(-d * 2 * S, -15 * S, -d * 4.6 * S + lag, -25 * S + sv);
      ctx.quadraticCurveTo(d * 3 * S, -15 * S, 7.4 * S, -5.4 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(0, -5.4 * S, 13 * S, 2.8 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = bordo; ctx.lineWidth = 1.8 * S; ctx.beginPath(); ctx.moveTo(-6.4 * S, -7.6 * S); ctx.quadraticCurveTo(0, -6.2 * S, 6.4 * S, -7.6 * S); ctx.stroke();
      stella(-d * 1 * S, -12.6 * S, 1.9 * S, bordo);
    } else if (A.testa === "visiera") {
      // Capelli corti e scuri, tirati su.
      ctx.beginPath(); ctx.moveTo(d * 7.6 * S, -4.4 * S); ctx.quadraticCurveTo(d * 5 * S, -11.4 * S, -d * 3 * S, -10.4 * S);
      ctx.quadraticCurveTo(-d * 9 * S, -8.4 * S, -d * 8.2 * S, -1 * S); ctx.quadraticCurveTo(-d * 6 * S, -5.4 * S, d * 7.6 * S, -4.4 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else {
      // Il caschetto: copre la nuca fino al mento, con la frangia.
      ctx.beginPath(); ctx.moveTo(d * 7.8 * S, -2 * S); ctx.quadraticCurveTo(d * 6 * S, -11.6 * S, -d * 1.6 * S, -10.6 * S);
      ctx.quadraticCurveTo(-d * 10.6 * S, -9 * S, -d * 9.6 * S, 5.4 * S + sv * 0.4); ctx.lineTo(-d * 5.2 * S, 5 * S);
      ctx.quadraticCurveTo(-d * 5.4 * S, -3.4 * S, d * 1 * S, -4.6 * S); ctx.quadraticCurveTo(d * 5 * S, -4.4 * S, d * 7.8 * S, -2 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
  }
  function disegnaUmano(f) {
    const p = f.p, A = aspetto(f), st = f.staccati || {}, nero = "#17171c", d = f.dir, [ginA, ginD] = ginocchia(f);
    // Trasformato: i bordi del vestito e gli occhi si accendono del suo colore.
    const forma = formaDi(f), sup = forma === "super", cavaliere = forma === "cavaliere";
    const acceso = !!forma;
    const crine = coloreAnime(f);
    const bordo = acceso ? coloreAnime(f) : A.bordo;
    if (f.furia > 0) {
      const g = ctx.createRadialGradient(p.bacino.x, p.bacino.y - 14 * S, 4 * S, p.bacino.x, p.bacino.y - 14 * S, 38 * S);
      g.addColorStop(0, "rgba(255,70,30,.45)"); g.addColorStop(1, "rgba(255,70,30,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.bacino.x, p.bacino.y - 14 * S, 38 * S, 0, Math.PI * 2); ctx.fill();
    }
    if (!anime) zaino(f, 9.5 * S);                 // i duellanti il jetpack ce l'hanno ancora
    if (A.veste) mantello(f, p, scuro(A.tuta));
    if (cavaliere) mantello(f, p, "#1a1b22");
    if (sup) chiomaSuper(f, crine, scuro(crine));
    // Gamba e braccio lontani.
    if (!st.gD) arto(p.bacino, ginD, p.piedeD, (sup ? 6.6 : 5) * S, scuro(A.gambe));
    if (!st.D) {
      // Trasformato: braccia più grosse, avambraccio pieno, pugno grande.
      arto(p.collo, p.gomitoD, p.manoD, (sup ? 6 : 4.2) * S, scuro(A.maniche));
      if (sup) linea(p.gomitoD, p.manoD, 7 * S, scuro(mix(A.pelle, "#ffffff", 0.1)));
      pugno(p.gomitoD, p.manoD, A, scuro(bordo), true, sup);
    }
    if (!st.gA) arto(p.bacino, ginA, p.piedeA, (sup ? 6.6 : 5) * S, A.gambe);
    // Le scarpe.
    for (const piede of [p.piedeD, p.piedeA]) {
      if ((piede === p.piedeD && st.gD) || (piede === p.piedeA && st.gA)) continue;
      ctx.fillStyle = A.scarpe; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.ellipse(piede.x + d * 1.4 * S, piede.y - 0.4 * S, 4.4 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    // La veste lunga dei maghi segue le ginocchia.
    if (A.veste) {
      const ord = [[ginA, p.piedeA], [ginD, p.piedeD]].sort((u, v) => (u[0].x - v[0].x) * d);
      const giu = ([g, pd]) => ({ x: g.x + (pd.x - g.x) * 0.5, y: g.y + (pd.y - g.y) * 0.5 });
      const dietro = giu(ord[0]), davanti = giu(ord[1]);
      ctx.fillStyle = A.tuta; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S; ctx.lineJoin = "round"; ctx.beginPath();
      ctx.moveTo(p.bacino.x - d * 8 * S, p.bacino.y - 4 * S); ctx.lineTo(p.bacino.x + d * 8 * S, p.bacino.y - 4 * S);
      ctx.lineTo(davanti.x + d * 5.5 * S, davanti.y); ctx.lineTo(dietro.x - d * 5.5 * S, dietro.y); ctx.closePath(); ctx.fill(); ctx.stroke();
      linea({ x: dietro.x - d * 5 * S, y: dietro.y - 1.4 * S }, { x: davanti.x + d * 5 * S, y: davanti.y - 1.4 * S }, 1.6 * S, bordo);
    }
    // Il busto.
    const ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2;
    const lung = Math.hypot(p.bacino.x - p.collo.x, p.bacino.y - p.collo.y);
    ctx.save();
    ctx.translate((p.collo.x + p.bacino.x) / 2, (p.collo.y + p.bacino.y) / 2); ctx.rotate(ang);
    if (sup) {
      // Trasformato: spalle larghe, vita stretta, pettorali in vista e la casacca strappata.
      const alto = -lung / 2 - 5 * S, basso = lung / 2 + 5 * S;
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(-6 * S, basso);
      ctx.quadraticCurveTo(-12.5 * S, (alto + basso) / 2, -12 * S, alto + 4 * S);
      ctx.quadraticCurveTo(-11.5 * S, alto - 2 * S, -5 * S, alto - 2.5 * S);
      ctx.quadraticCurveTo(0, alto - 3.5 * S, 5 * S, alto - 2.5 * S);
      ctx.quadraticCurveTo(11.5 * S, alto - 2 * S, 12 * S, alto + 4 * S);
      ctx.quadraticCurveTo(12.5 * S, (alto + basso) / 2, 6 * S, basso);
      ctx.closePath();
      const g = ctx.createLinearGradient(0, alto, 0, basso);
      g.addColorStop(0, mix(A.pelle, "#ffffff", 0.2)); g.addColorStop(1, scuro(A.pelle));
      ctx.fillStyle = g; ctx.fill();
      ctx.strokeStyle = nero; ctx.lineWidth = 1.3 * S; ctx.stroke();
      // Pettorali e ventre, segnati appena.
      ctx.strokeStyle = scuro(A.pelle); ctx.lineWidth = 1.3 * S; ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(-8 * S, alto + 11 * S); ctx.quadraticCurveTo(0, alto + 15 * S, 8 * S, alto + 11 * S);
      ctx.moveTo(0, alto + 4 * S); ctx.lineTo(0, alto + 24 * S);
      ctx.moveTo(-5.5 * S, alto + 18 * S); ctx.lineTo(-5 * S, alto + 23 * S);
      ctx.moveTo(5.5 * S, alto + 18 * S); ctx.lineTo(5 * S, alto + 23 * S);
      ctx.stroke();
      // La casacca strappata: due lembi sulle spalle, con lo strappo frastagliato.
      ctx.fillStyle = A.tuta; ctx.strokeStyle = nero; ctx.lineWidth = 1.2 * S;
      for (const lato of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(lato * 12.4 * S, alto + 3 * S);
        ctx.quadraticCurveTo(lato * 11 * S, alto - 2.4 * S, lato * 4.6 * S, alto - 2 * S);
        ctx.lineTo(lato * 6 * S, alto + 7 * S);
        ctx.lineTo(lato * 8.4 * S, alto + 4 * S);
        ctx.lineTo(lato * 8 * S, alto + 13 * S);
        ctx.lineTo(lato * 10.6 * S, alto + 7.5 * S);
        ctx.lineTo(lato * 11.4 * S, alto + 16 * S);
        ctx.closePath(); ctx.fill(); ctx.stroke();
      }
      // La fascia in vita, annodata.
      ctx.fillStyle = bordo; ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
      ctx.beginPath(); rettangoloTondo(-8 * S, basso - 9 * S, 16 * S, 5 * S, 1.8 * S); ctx.fill(); ctx.stroke();
      ctx.beginPath(); rettangoloTondo(-d * 5.6 * S - 1.4 * S, basso - 8 * S, 2.8 * S, 9 * S, 1.2 * S); ctx.fill(); ctx.stroke();
    } else {
      ctx.fillStyle = sfumatura(0, 0, lung, mix(A.tuta, "#ffffff", 0.18), A.tuta); ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S;
      rettangoloTondo(-7.6 * S, -lung / 2 - 3 * S, 15.2 * S, lung + 7 * S, 5 * S); ctx.fill(); ctx.stroke();
    }
    ctx.strokeStyle = bordo; ctx.lineCap = "round"; ctx.lineWidth = 1.6 * S; ctx.beginPath();
    if (sup) { /* la casacca strappata se l'è già disegnata */ }
    else if (stile === "guerrieri") {
      // La casacca incrociata e la fascia in vita, annodata.
      ctx.moveTo(-5 * S, -lung / 2 - 2 * S); ctx.lineTo(d * 3 * S, lung / 2 - 6 * S);
      ctx.moveTo(5 * S, -lung / 2 - 2 * S); ctx.lineTo(d * 0.5 * S, -lung / 2 + 5 * S); ctx.stroke();
      ctx.fillStyle = bordo; ctx.fillRect(-7.6 * S, lung / 2 - 5.4 * S, 15.2 * S, 2.8 * S);
      ctx.fillRect(-d * 4.4 * S - 1 * S, lung / 2 - 4.6 * S, 2 * S, 7.5 * S);
    } else if (stile === "maghi") {
      // Il cordone in vita e le stelle sulla veste.
      ctx.moveTo(-7.6 * S, lung / 2 - 4 * S); ctx.lineTo(7.6 * S, lung / 2 - 4 * S); ctx.stroke();
      stella(-d * 2.6 * S, -lung / 2 + 5.5 * S, 1.8 * S, bordo); stella(d * 3 * S, -lung / 2 + 11 * S, 1.3 * S, bordo);
    } else {
      // La giacca del duellante: una riga accesa e lo spallaccio.
      ctx.moveTo(d * 1.5 * S, -lung / 2 - 1.5 * S); ctx.lineTo(d * 1.5 * S, lung / 2 + 2 * S); ctx.stroke();
      ctx.fillStyle = scuro(A.tuta); ctx.strokeStyle = nero; ctx.lineWidth = 1 * S;
      rettangoloTondo(-8.6 * S, -lung / 2 - 4 * S, 17.2 * S, 5.4 * S, 2.6 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#1b1e27"; ctx.fillRect(-7.6 * S, lung / 2 - 4.6 * S, 15.2 * S, 2.2 * S);
    }
    disegnaSegni(f, "busto");
    ctx.restore();
    // La testa.
    const angT = Math.atan2(p.testa.y - p.collo.y, p.testa.x - p.collo.x) + Math.PI / 2;
    ctx.save(); ctx.translate(p.testa.x, p.testa.y); ctx.rotate(angT);
    if (!sup) capoUmano(f, A, bordo, true);                        // trasformato, i capelli sono la cresta
    else crestaSuper(f, crine, d);
    ctx.fillStyle = A.pelle; ctx.strokeStyle = nero; ctx.lineWidth = 1.1 * S;
    ctx.beginPath(); ctx.arc(0, 0, 8 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    facciaUmana(f, A, acceso ? coloreAnime(f) : null);
    disegnaSegni(f, "testa");
    if (!sup) capoUmano(f, A, bordo, false);
    if (cavaliere) {
      // Il cappuccio cala sulla testa e lascia in ombra la faccia; resta accesa la fessura della maschera.
      ctx.fillStyle = "#1a1b22"; ctx.strokeStyle = "#0d0e12"; ctx.lineWidth = 1.3 * S; ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(-10.6 * S, 1.6 * S);
      ctx.quadraticCurveTo(-11.4 * S, -13 * S, 0, -13.4 * S);
      ctx.quadraticCurveTo(11.4 * S, -13 * S, 10.6 * S, 1.6 * S);
      ctx.lineTo(8 * S, 8.4 * S); ctx.quadraticCurveTo(0, 1.2 * S, -8 * S, 8.4 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#101219";
      ctx.beginPath(); ctx.ellipse(d * 0.8 * S, 0.4 * S, 7.6 * S, 4.6 * S, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = f.ko ? "#5b6170" : bordo; ctx.lineWidth = 1.7 * S; ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(d * 0.8 * S - 5 * S, 0.2 * S); ctx.lineTo(d * 0.8 * S + 5 * S, 0.2 * S - d * 1.2 * S); ctx.stroke();
    }
    const tg = temaGravita();
    if (tg === "luna" || tg === "spazio") { ctx.save(); ctx.translate(0, -1 * S); casco(13.5 * S); ctx.restore(); }
    ctx.restore();
    // Il braccio vicino.
    if (!st.A) {
      arto(p.collo, p.gomitoA, p.manoA, (sup ? 6 : 4.2) * S, A.maniche);
      if (sup) linea(p.gomitoA, p.manoA, 7 * S, mix(A.pelle, "#ffffff", 0.1));
      pugno(p.gomitoA, p.manoA, A, bordo, false, sup);
    }
    if (f.palla && !st.A) tondo(p.manoA.x, p.manoA.y - 3 * S, 3 * S, "#ffffff");
  }
  // Si cambia stile: escono di scena i vecchi lottatori ed entrano i nuovi,
  // in una nuvoletta, dove stavano gli altri. Il punteggio resta.
  function cambiaCorpi() {
    if (!lottatori.length) return;
    for (const t of telefoni) if (t.stato !== "libero") { t.stato = "libero"; t.da = null; t.ox = t.x; t.oy = t.y; }
    proiettili = []; arti = []; pezzi = []; scie = []; fulmini = []; duello = 0; sfida = null;
    presa.f = null; radiceHtml("remove", "ring-trascina");
    lottatori = lottatori.map((v) => {
      const x = Math.max(30 * S, Math.min(W - 30 * S, Number.isFinite(v.cx) ? v.cx : W / 2));
      const f = crea(v.tipo, x, v.dir, Math.min(Number.isFinite(v.base) ? v.base : pavimento, pavimento));
      for (let i = 0; i < 9 && particelle.length < MAX_PARTICELLE; i++) {
        particelle.push({ tipo: "polvere", x: x + caso(-14, 14) * S, y: f.base - caso(4, 56) * S, vx: caso(-1.3, 1.3) * S, vy: caso(-1, 0.2) * S,
                          vita: Math.round(caso(18, 30)), max: 30, colore: "#d9d4cc" });
      }
      return f;
    });
    if (lame()) for (const f of lottatori) accendiLama(f);
  }

  // Tutto quello che si disegna di un lottatore, nell'ordine giusto. Chi è
  // stato rimpicciolito viene disegnato in scala, coi piedi fermi dove sono.
  function disegnaLottatore(f) {
    // Schiacciato dal colpo finale: piatto come una frittella, e poi torna su di scatto.
    const piatto = f.schiacciato > 0;
    if (piatto) {
      let giu = -1e9;
      for (const n in f.p) giu = Math.max(giu, f.p[n].y);
      const q = f.schiacciato > 12 ? 0.22 : 0.22 + 0.78 * (1 - f.schiacciato / 12), px = f.p.bacino.x;
      ctx.save(); ctx.translate(px, giu); ctx.scale(1 + (1 - q) * 0.5, q); ctx.translate(-px, -giu);
    }
    disegnaLottatoreIntero(f);
    if (piatto) ctx.restore();
  }
  function disegnaLottatoreIntero(f) {
    const k = f.scala * quantoGrosso(f), stretto = Math.abs(k - 1) > 0.02;
    if (stretto) {
      const px = f.p.bacino.x, py = verso > 0 ? Math.max(f.p.piedeA.y, f.p.piedeD.y) : Math.min(f.p.piedeA.y, f.p.piedeD.y);
      ctx.save(); ctx.translate(px, py); ctx.scale(k, k); ctx.translate(-px, -py);
    }
    disegnaParacadute(f);
    if (anime && (f.azione === "carica" || f.azione === "trasforma" || f.potenziato > 0 || (f.azione === "onda" && f.t < 34) || f.scatto > 0 ||
                  (sfida && (sfida.a === f || sfida.b === f)))) disegnaAura(f);
    if (stile === "maghi" && f.volo && f.jet > 0) disegnaScopa(f);
    if (stile === "lame") sciarpa(f);
    (stile ? disegnaUmano : f.tipo === "robot" ? disegnaRobot : disegnaMela)(f);
    if (stile === "maghi") disegnaBacchetta(f);
    if (stile === "lame") disegnaLama(f);
    if (stile === "guerrieri" && f.forma > 0 && f.potenziato > 0) disegnaForma(f);
    if (stretto) ctx.restore();
    if (f.gelato > 0) disegnaGhiaccio(f);
  }

  // --- Le barre della vita ------------------------------------------------
  // In alto, sotto la testata, come in un picchiaduro: robot a sinistra,
  // mela a destra, il punteggio in mezzo. La parte persa resta chiara per
  // un attimo prima di sparire. In modalità anime, sotto, l'energia.
  function vitaVera(f) {
    if (f.esploso || f.koVero) return 0;
    return Math.max(0, 1 - f.danni / Math.max(1, f.soglia));
  }
  function aggiornaVite() {
    for (const f of lottatori) {
      const v = vitaVera(f);
      f.vitaVista += (v - f.vitaVista) * 0.2;
      if (f.vitaScia > f.vitaVista) f.vitaScia = Math.max(f.vitaVista, f.vitaScia - 0.006);
      else f.vitaScia = f.vitaVista;
    }
  }
  function disegnaBarre() {
    // Sottosopra i lottatori stanno in alto: le barre scendono sopra la striscia.
    const m = 16, h = 12 * S, w = Math.min(300 * S, (W - 2 * m - 70 * S) / 2);
    const y = verso < 0 ? pavimento - (anime ? 34 : 26) * S : Math.max(22 * S, testataBasso + 22 * S);
    ctx.save();
    ctx.font = "800 " + Math.round(11 * S) + "px Archivo, sans-serif"; ctx.textBaseline = "bottom";
    ctx.lineWidth = 3 * S; ctx.strokeStyle = "#ffffff"; ctx.lineJoin = "round";
    for (const f of lottatori) {
      const sinistra = f.tipo === "robot", x = sinistra ? m : W - m - w;
      ctx.fillStyle = "#1b1b1b"; rettangoloTondo(x - 2 * S, y - 2 * S, w + 4 * S, h + 4 * S, 4 * S); ctx.fill();
      const pieno = (k) => (sinistra ? [x, k * w] : [x + w - k * w, k * w]);
      let [ax, aw] = pieno(f.vitaScia);
      ctx.fillStyle = "#ffb3a8"; ctx.fillRect(ax, y, aw, h);
      [ax, aw] = pieno(f.vitaVista);
      ctx.fillStyle = f.vitaVista > 0.5 ? "#2fbf71" : f.vitaVista > 0.25 ? "#f2c230" : "#e0443a";
      ctx.fillRect(ax, y, aw, h);
      ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.fillRect(ax, y, aw, h * 0.35);
      ctx.textAlign = sinistra ? "left" : "right";
      const nome = (stile ? aspetto(f).nome : f.tipo === "robot" ? "ROBOT" : dici("Mela").toUpperCase()) + (f.forma > 0 && f.potenziato > 0 ? " " + "\u2605".repeat(f.forma) : "");
      ctx.fillStyle = "#141414"; ctx.strokeText(nome, sinistra ? x : x + w, y - 3 * S); ctx.fillText(nome, sinistra ? x : x + w, y - 3 * S);
      if (anime) {
        const yk = y + h + 4 * S, hk = 5 * S;
        ctx.fillStyle = "#1b1b1b"; ctx.fillRect(x - 1 * S, yk - 1 * S, w + 2 * S, hk + 2 * S);
        const kw = (f.ki / 100) * w;
        ctx.fillStyle = f.ki >= 100 && passi % 10 < 5 ? "#ffffff" : COLORI_ANIME[f.tipo];
        ctx.fillRect(sinistra ? x : x + w - kw, yk, kw, hk);
      }
    }
    ctx.textAlign = "center";
    ctx.font = "800 " + Math.round(15 * S) + "px Archivo, sans-serif";
    const punti = punteggio.robot + " – " + punteggio.mela;
    ctx.fillStyle = "#141414"; ctx.strokeText(punti, W / 2, y + h + 2 * S); ctx.fillText(punti, W / 2, y + h + 2 * S);
    ctx.restore();
  }

  // --- IL COLPO FINALE (05/10/2026, su richiesta) ----------------------------
  // Una volta ogni tre round, a caso, il round non finisce con un colpo
  // qualunque ma con una mossa finale: quando all'avversario manca un colpo
  // solo, chi sta per vincere lo chiude con una scena tutta sua. Il resto si
  // ferma a guardare: intorno si fa buio, i colpi normali non contano, gli
  // imprevisti aspettano.
  //   in orbita     un montante lo spedisce oltre il bordo in alto; una stella, e ricade
  //   flipper       un calcio, e rimbalza tre volte fra i bordi della finestra
  //   schiacciata   gli salta sopra da molto in alto: resta piatto come una frittella
  //   onda finale   (super guerrieri) un'onda a bruciapelo lo porta fino al bordo
  //   statua        (maghi) lo gela, poi una saetta e il ghiaccio va in pezzi
  //   taglio netto  (duellanti) uno scatto attraverso, un attimo fermi, poi cade
  // Quale round tocca lo decide un sacchetto di tre (uno sì, due no) mescolato:
  // se il round scelto finisce prima che la mossa si possa fare, vale per il
  // round dopo. Niente colpo finale sul punto che chiude la partita a dieci
  // (quello ha già la sua uscita di scena), né durante orda, scontro di
  // energie, terremoto o buco nero. Vale un K.O. come gli altri.
  const FATALE = { ogni: 3, buio: 0.44, dove: { orbita: 27, flipper: 30, schiacciata: 62, onda: 92, statua: 110, taglio: 74, sferona: 150, meteora: 30, vortice: 96, crepa: 150 } };
  let fatale = null, fataleSacco = [], fataleRound = false, fataliFatti = 0, fataleBuio = 0, fataleDebito = 0, fataleVoluto = 0;
  function prossimoRoundFatale() {
    if (!fataleSacco.length) {
      fataleSacco = [true];
      for (let i = 1; i < FATALE.ogni; i++) fataleSacco.push(false);
      for (let i = fataleSacco.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); const v = fataleSacco[i]; fataleSacco[i] = fataleSacco[j]; fataleSacco[j] = v; }
    }
    const tocca = fataleSacco.pop();
    // Il round buono non usato (K.O. da lontano, in volo…) resta buono; e se nel frattempo ne esce
    // un altro dal sacchetto, quello resta «a credito»: così alla lunga è davvero uno su tre.
    if (fataleRound) { if (tocca) fataleDebito = Math.min(2, fataleDebito + 1); return; }
    if (tocca) fataleRound = true;
    else if (fataleDebito > 0) { fataleDebito--; fataleRound = true; }
  }
  // A comando (il tasto del menu): parte appena i due sono in piedi e vicini; se entro sei secondi
  // non capita, il round in corso diventa quello buono.
  function vogliaFatale() {
    if (!fataleVoluto || fatale) { fataleVoluto = 0; return; }
    const ordine = fataleVoluto % 2 ? [lottatori[0], lottatori[1]] : [lottatori[1], lottatori[0]];
    for (const [f, altro] of [ordine, [ordine[1], ordine[0]]]) {
      if (f && altro && puoFinire(f, altro, true)) { fataleVoluto = 0; altro.danni = Math.max(altro.danni, altro.soglia - 1); avviaFatale(f, altro); return; }
    }
    if (--fataleVoluto <= 0) { fataleVoluto = 0; fataleRound = true; }
  }
  const inPiediPerFinale = (l) => !!(l.p && !l.ko && !l.esploso && !l.preso && !l.tenuto && !l.fuori && !l.fuoriCampo && !(l.jet > 0) && !l.inVolo && !l.scalata && !(l.gelato > 0));
  function puoFinire(f, altro, comunque) {
    return !!((fataleRound || comunque) && !fatale && !orda && !sfida && !buco && !sisma && !finale && verso > 0 &&
              (comunque || altro.danni >= altro.soglia - 1) && punteggio[f.tipo] < TRAGUARDO - 1 &&
              inPiediPerFinale(f) && inPiediPerFinale(altro) && gambe(f) === 2 && braccia(f) === 2 && !(f.accecato > 0) && !(f.stordito > 0) &&
              Math.abs(f.base - altro.base) < 10 * S && Math.abs(altro.cx - f.cx) < 320 * S);
  }
  function avviaFatale(da, a, tipo) {
    const scelte = [[2, "orbita"], [2, "flipper"], [2, "schiacciata"], [2.4, "sferona"], [2, "meteora"], [2.2, "vortice"], [2.2, "crepa"]];
    if (stile === "guerrieri") scelte.push([4, "onda"]);
    if (stile === "maghi") scelte.push([4, "statua"]);
    if (lame() && lamaPronta(da)) scelte.push([4, "taglio"]);
    if (!tipo || !FATALE.dove[tipo]) tipo = scegli(scelte);
    fataleRound = false;
    for (const l of [da, a]) {
      if (l.tel) lasciaCadere(l);
      if (l.tiene) molla(l);
      l.azione = null; l.onda = null; l.sfera = null; l.scatto = 0; l.ordine = null; l.fuga = null; l.combo = 0; l.dopo = null; l.prendiTel = null;
    }
    da.dir = a.cx >= da.cx ? 1 : -1; a.dir = -da.dir;
    fatale = { da, a, tipo, t: 0, fase: "annuncio", m: 0, dir: da.dir, contato: false, d: {} };
    scrivi("COLPO FINALE!", (da.p.testa.x + a.p.testa.x) / 2, Math.min(da.p.testa.y, a.p.testa.y) - 44 * S, true);
    fermoColpo = Math.max(fermoColpo, 6);
  }
  // Tutto il corpo spostato (o girato intorno al bacino) di peso: chi è in scena non lo muove la fisica.
  function muoviTutto(f, dx, dy) { for (const n in f.p) { const q = f.p[n]; q.x += dx; q.y += dy; q.ox = q.x; q.oy = q.y; } f.cx += dx; }
  function ruotaTutto(f, ang) {
    const c = f.p.bacino, co = Math.cos(ang), si = Math.sin(ang);
    for (const n in f.p) {
      const q = f.p[n];
      if (q === c) continue;
      const x = q.x - c.x, y = q.y - c.y;
      q.x = c.x + x * co - y * si; q.y = c.y + x * si + y * co; q.ox = q.x; q.oy = q.y;
    }
  }
  // Quando una mossa finale scoppia davvero: la pagina se ne accorge. Crepe
  // nella striscia delle notizie, crepe (e buchi) nei bordi della finestra,
  // bruciature per terra e gli oggetti in giro che si rompono.
  function sfondaPagina(x, y, forza) {
    // Più è grosso il colpo, più lontano si crepa: la striscia ne regge cinque per volta.
    for (const dx of (forza >= 1.2 ? [-200, -110, 0, 110, 200] : [-90, 0, 90])) {
      const px = Math.max(20 * S, Math.min(W - 20 * S, x + dx * S));
      danneggiaStriscia(px, Math.min(1, forza), true);
    }
    const lato = x < W * 0.34 ? "sinistra" : x > W * 0.66 ? "destra" : "sopra";
    danneggiaBordo(lato, lato === "sopra" ? x : y, Math.min(1, forza));
    if (lato !== "sopra") danneggiaBordo("sopra", x, Math.min(1, forza * 0.7));
    for (let i = 0; i < Math.round(3 * forza) && bruciature.length < 40; i++) {
      bruciature.push({ x: x + caso(-70, 70) * S * forza, y: pavimento - 1, r: caso(16, 30) * S * forza, t: 0 });
    }
    for (const t of telefoni) {
      if (t.stato === "impugnato" || Math.hypot(t.x - x, t.y - y) > 220 * S * forza) continue;
      t.crepe = Math.min(5, (t.crepe || 0) + 2); rompiSchermo(t);
      t.stato = "volo"; t.ox = t.x - (t.x - x) * 0.14; t.oy = t.y - (t.y - y) * 0.14 - 2 * S;
    }
    for (let i = 0; i < 14 && particelle.length < MAX_PARTICELLE; i++) {
      const a = caso(0, Math.PI * 2), v = caso(2, 7) * S;
      particelle.push({ tipo: "detrito", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 2 * S,
                        vita: Math.round(caso(60, 120)), max: 120, rot: caso(0, 6), va: caso(-0.3, 0.3),
                        lato: caso(2, 4.4) * S, colore: Math.random() < 0.5 ? "#8a7f70" : "#b9b4ab" });
    }
    scossa = Math.max(scossa, 26);
  }
  // ·· LA MIRA DELLA MOSSA FINALE (09/10/2026, chiesta da Riccardo) ··
  // Premi una volta: il tempo rallenta, si fa buio e dalle mani del personaggio
  // parte una linea di tiro che ruota su e giù in diagonale, come una lancetta.
  // Premi la seconda volta: il colpo parte lungo la linea e prende tutto quello
  // che attraversa. Se non spari entro qualche secondo parte da solo.
  // `giro` è quanto ruota la linea a ogni tic di fisica e `lento` quanto rallenta
  // il tempo: insieme fanno una passata in poco più di un secondo. Rallentare di
  // più rende la linea a scatti, perché la fisica gira meno volte del disegno.
  // `su` e `giu` sono gli angoli massimi sopra e sotto l'orizzonte, in radianti.
  const MIRA = { giro: 0.036, attesa: 140, lento: 0.55, spesso: 9, su: 1.0, giu: 0.6 };
  let mira = null, miraBuio = 0, lampoMira = null;
  // Il verso: dove sono i nemici più vicini.
  function versoMira(f) {
    const x0 = f.p.bacino.x;
    let meglio = 1e9, dir = f.dir || 1;
    for (const l of lottatori) if (l !== f && l.p && !l.esploso && !l.fuoriCampo) {
      const d = Math.abs(l.p.bacino.x - x0); if (d < meglio) { meglio = d; dir = l.p.bacino.x >= x0 ? 1 : -1; }
    }
    if (orda) for (const z of orda.zombie) if (vivoZ(z)) {
      const d = Math.abs(z.x - x0); if (d < meglio) { meglio = d; dir = z.x >= x0 ? 1 : -1; }
    }
    return dir;
  }
  // Da dove parte la linea: le mani, che nella carica stanno davanti al petto.
  function origineMira(m) {
    const p = m.da.p;
    return { x: (p.manoA.x + p.manoD.x) / 2 + m.dir * 6 * S, y: (p.manoA.y + p.manoD.y) / 2 };
  }
  // Fin dove arriva: il bordo della finestra, il pavimento o la striscia in alto.
  function fineMira(o, dir, a) {
    const dx = dir * Math.cos(a), dy = Math.sin(a);
    let k = dx > 0 ? (W - o.x) / dx : o.x / -dx;
    if (dy > 0.001) k = Math.min(k, (pavimento - o.y) / dy);
    if (dy < -0.001) k = Math.min(k, (testataBasso - o.y) / dy);
    k = Math.max(0, k);
    return { x: o.x + dx * k, y: o.y + dy * k, dx, dy, k };
  }
  function avviaMira(f) {
    if (mira || !f || !f.p || f.esploso || f.ko > 0 || fatale) return false;
    const dir = versoMira(f);
    f.dir = dir;
    // Nella corsa l'occhio fermo fa girare la linea più piano.
    mira = { da: f, dir, a: -0.15, v: -MIRA.giro * (1 - 0.18 * livello("mira")), t: 0, ritmo0: ritmo };
    ritmo = MIRA.lento;
    f.azione = null; f.ordine = null; f.pensa = 1e9;                // resta fermo a caricare
    inizia(f, "carica"); f.durata = 1e9;
    scrivi("MIRA!", f.p.bacino.x, f.base - 92 * S, true);
    return true;
  }
  function chiudiMira(sparato) {
    if (!mira) return;
    const f = mira.da;
    ritmo = mira.ritmo0;
    mira = null;
    if (f && f.p && !f.esploso) { f.azione = null; f.pensa = sparato ? 24 : 10; }
  }
  function aggiornaMira() {
    miraBuio += ((mira ? 0.62 : 0) - miraBuio) * 0.14;
    if (!mira) return;
    const m = mira, f = m.da;
    if (!f.p || f.esploso || f.ko > 0 || f.preso || f.tenuto) { chiudiMira(false); return; }
    m.t++;
    f.dir = m.dir;
    f.ki = Math.max(f.ki || 0, 60);
    m.a += m.v;
    if (m.a <= -MIRA.su) { m.a = -MIRA.su; m.v = Math.abs(m.v); }
    else if (m.a >= MIRA.giu) { m.a = MIRA.giu; m.v = -Math.abs(m.v); }
    if (m.t % 4 === 0 && particelle.length < MAX_PARTICELLE) {
      const o = origineMira(m);
      particelle.push({ tipo: "scintilla", x: o.x + caso(-6, 6) * S, y: o.y + caso(-6, 6) * S, vx: 0, vy: -caso(0.4, 1.4) * S,
                        vita: 16, max: 16, colore: COLORI_ANIME[f.tipo] || "#56e1ff" });
    }
    if (m.t > MIRA.attesa) sparaMira();                            // chi non spara, spara da solo
  }
  // Quanto un cerchio sta vicino alla linea: la distanza dal punto più vicino del
  // segmento, e dove sta quel punto.
  function sullaLinea(o, e, x, y) {
    const t = Math.max(0, Math.min(e.k, (x - o.x) * e.dx + (y - o.y) * e.dy));
    const px = o.x + e.dx * t, py = o.y + e.dy * t;
    return { d: Math.hypot(x - px, y - py), x: px, y: py };
  }
  // Chi sta sulla linea in questo momento: serve al colpo e al mirino, che si
  // aggancia quando la linea attraversa qualcuno.
  function toccatiMira(m, o, e) {
    const largo = MIRA.spesso * S, out = { lott: [], zombie: [], creature: [] };
    for (const l of lottatori) {
      if (l === m.da || !l.p || l.esploso || l.fuoriCampo) continue;
      let dove = null;
      for (const n in l.p) {
        const q = l.p[n], v = sullaLinea(o, e, q.x, q.y);
        if (v.d <= (q.r || 4) + largo && (!dove || v.d < dove.d)) dove = v;
      }
      if (dove) out.lott.push({ l, x: dove.x, y: dove.y });
    }
    if (orda) for (const z of orda.zombie) {
      if (!vivoZ(z)) continue;
      const c = corpoZ(z), v1 = sullaLinea(o, e, c[0], c[1]), v2 = sullaLinea(o, e, c[3], c[4]);
      if (v1.d <= c[2] + largo || v2.d <= c[5] + largo) out.zombie.push({ z, c, x: z.x, y: c[1] });
    }
    for (const c of creature) {
      if (c.t > c.vita) continue;                                  // c.vita è quanto dura, c.t quanto ha vissuto
      if (sullaLinea(o, e, c.x, c.y).d <= 16 * S + largo) out.creature.push(c);
    }
    return out;
  }
  // Il colpo: un raggio dalle mani fino al bordo, lungo la linea.
  function sparaMira() {
    if (!mira) return { presi: 0, zombie: 0 };
    const m = mira, f = m.da, col = COLORI_ANIME[f.tipo] || "#56e1ff";
    const o = origineMira(m), e = fineMira(o, m.dir, m.a), chi = toccatiMira(m, o, e), colpi = [];
    // Nella corsa il colpo è molto più forte; all'ultima possibilità, se prende qualcuno, salva il round.
    if (corsa && corsa.chi && f.tipo === corsa.chi && corsa.fase === "lotta" && colpoMiraCorsa(chi) && corsa.ultima) vinciRound("salvezza");
    for (const t of chi.lott) { colpisci(f, t.l, 7.5, t.x, t.y, "ZAAAP!"); colpi.push([t.x, t.y]); }
    for (const t of chi.zombie) { colpisciZombie(t.z, 9, m.dir, t.z.x, t.c[1], f); colpi.push([t.x, t.y]); }
    for (const c of chi.creature) { c.vita = c.t; polvere(c.x, c.y, 8); colpi.push([c.x, c.y]); }
    const presi = chi.lott.length, zPresi = chi.zombie.length + chi.creature.length;
    lampoMira = { ox: o.x, oy: o.y, fx: e.x, fy: e.y, t: 0, colore: col, preso: presi + zPresi > 0, colpi };
    suona("zap", o.x, 1.5);
    scossa = Math.max(scossa, 14); fermoColpo = Math.max(fermoColpo, 7);
    for (let i = 0; i < 30 && particelle.length < MAX_PARTICELLE; i++) {
      const k = Math.random(), sp = caso(1, 4) * S, lato = Math.random() < 0.5 ? 1 : -1;
      particelle.push({ tipo: "scintilla", x: o.x + (e.x - o.x) * k, y: o.y + (e.y - o.y) * k,
                        vx: -e.dy * sp * lato + e.dx * S, vy: e.dx * sp * lato + e.dy * S,
                        vita: Math.round(caso(14, 30)), max: 30, colore: Math.random() < 0.4 ? "#ffffff" : col });
    }
    for (const [x, y] of colpi) scintille(x, y, 10, "#ffd84a");
    scintille(e.x, e.y, 8, col);                                   // dove il raggio sbatte
    scrivi(presi + zPresi > 0 ? "PRESO!" : "MANCATO!", f.p.bacino.x + m.dir * 120 * S, f.base - 110 * S, true);
    chiudiMira(true);
    return { presi, zombie: zPresi };
  }
  // Un tratto che sfuma lungo la linea: pieno vicino alle mani, trasparente in fondo.
  function trattoMira(o, e, colore, largo, alfa, sfuma) {
    const g = ctx.createLinearGradient(o.x, o.y, e.x, e.y);
    g.addColorStop(0, colore); g.addColorStop(1, sfuma ? "rgba(255,255,255,0)" : colore);
    ctx.globalAlpha = Math.max(0, Math.min(1, alfa)); ctx.strokeStyle = g; ctx.lineWidth = largo;
    ctx.beginPath(); ctx.moveTo(o.x, o.y); ctx.lineTo(e.x, e.y); ctx.stroke();
  }
  // Il mirino: un cerchio, quattro tacche che girano, un punto in mezzo.
  function mirino(x, y, r, colore, giro) {
    ctx.globalAlpha = 0.95; ctx.strokeStyle = colore; ctx.lineWidth = 2 * S;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
    ctx.lineWidth = 2.6 * S;
    for (let i = 0; i < 4; i++) {
      const a = giro + i * Math.PI / 2;
      ctx.beginPath(); ctx.moveTo(x + Math.cos(a) * r * 0.55, y + Math.sin(a) * r * 0.55); ctx.lineTo(x + Math.cos(a) * r * 1.45, y + Math.sin(a) * r * 1.45); ctx.stroke();
    }
    ctx.fillStyle = colore; ctx.beginPath(); ctx.arc(x, y, 2 * S, 0, Math.PI * 2); ctx.fill();
  }
  let centroMira = null;                                           // dove sta la luce mentre il buio sfuma
  function disegnaMira() {
    if (mira && mira.da.p) centroMira = { x: mira.da.p.bacino.x, y: mira.da.p.bacino.y };
    if (miraBuio > 0.01 && centroMira) {
      // Il buio tutto intorno, con la luce su chi mira.
      const g = ctx.createRadialGradient(centroMira.x, centroMira.y, 60 * S, centroMira.x, centroMira.y, Math.max(W, H) * 0.8);
      g.addColorStop(0, "rgba(6,4,20,0)"); g.addColorStop(0.35, "rgba(6,4,20," + (miraBuio * 0.75).toFixed(3) + ")");
      g.addColorStop(1, "rgba(6,4,20," + Math.min(0.85, miraBuio * 1.25).toFixed(3) + ")");
      ctx.save(); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); ctx.restore();
    }
    if (lampoMira) {
      // Il colpo: un raggio a tre strati che si allarga e svanisce, un lampo alle mani, un anello su ogni colpito.
      const L = lampoMira, k = Math.max(0, 1 - L.t / 26), h = MIRA.spesso * S * (1 + 1.6 * (1 - k)), o = { x: L.ox, y: L.oy }, e = { x: L.fx, y: L.fy };
      ctx.save(); ctx.lineCap = "round";
      ctx.shadowColor = L.colore; ctx.shadowBlur = 26 * S;
      trattoMira(o, e, L.colore, h * 1.6, k, false);
      ctx.shadowBlur = 10 * S; ctx.shadowColor = "#ffffff";
      trattoMira(o, e, "#ffffff", h * 0.6, k, false);
      ctx.shadowBlur = 0;
      const R = (18 + 40 * (1 - k)) * S, g = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, R);
      g.addColorStop(0, "rgba(255,255,255," + k.toFixed(3) + ")"); g.addColorStop(1, "rgba(255,255,255,0)");
      ctx.globalAlpha = 1; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(o.x, o.y, R, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "#ffd84a"; ctx.lineWidth = 3 * S * k + 0.5;
      for (const [x, y] of L.colpi || []) { ctx.globalAlpha = k; ctx.beginPath(); ctx.arc(x, y, (8 + 46 * (1 - k)) * S, 0, Math.PI * 2); ctx.stroke(); }
      ctx.restore();
      if (++L.t > 26) lampoMira = null;
    }
    if (!mira) return;
    const m = mira, f = m.da, col = COLORI_ANIME[f.tipo] || "#56e1ff", pulsa = 0.5 + 0.5 * Math.sin(passi * 0.45);
    const o = origineMira(m), e = fineMira(o, m.dir, m.a), lungo = e.k, chi = toccatiMira(m, o, e);
    const preso = chi.lott.length + chi.zombie.length + chi.creature.length > 0, oro = "#ffd84a";
    ctx.save(); ctx.lineCap = "round";
    // L'arco dove gira la lancetta, con una tacca a ogni capo.
    const A = 52 * S, a0 = m.dir > 0 ? -MIRA.su : Math.PI - MIRA.giu, a1 = m.dir > 0 ? MIRA.giu : Math.PI + MIRA.su;
    ctx.globalAlpha = 0.45; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.4 * S;
    ctx.setLineDash([2 * S, 5 * S]); ctx.beginPath(); ctx.arc(o.x, o.y, A, a0, a1); ctx.stroke(); ctx.setLineDash([]);
    for (const a of [a0, a1]) { ctx.beginPath(); ctx.moveTo(o.x + Math.cos(a) * (A - 5 * S), o.y + Math.sin(a) * (A - 5 * S)); ctx.lineTo(o.x + Math.cos(a) * (A + 5 * S), o.y + Math.sin(a) * (A + 5 * S)); ctx.stroke(); }
    // La linea: alone largo, corpo colorato, anima bianca; tutto sfuma verso il fondo.
    const tinta = preso ? oro : col;
    ctx.shadowColor = tinta; ctx.shadowBlur = 14 * S;
    trattoMira(o, e, tinta, 5 * S, 0.75, true);
    ctx.shadowBlur = 0;
    trattoMira(o, e, "#ffffff", 1.8 * S, 0.95, true);
    // L'energia che corre lungo la linea, dalle mani verso il fondo.
    ctx.fillStyle = "#ffffff";
    const gap = 46 * S;
    for (let d = (passi * 7 * S) % gap; d < lungo; d += gap) {
      const x = o.x + e.dx * d, y = o.y + e.dy * d, r = 2.6 * S * (1 - d / (lungo + 1)) + 0.6 * S;
      ctx.globalAlpha = 0.9 * (1 - d / (lungo + 1)); ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    }
    // Il mirino: in fondo alla linea, o agganciato sul primo colpito.
    const primo = chi.lott[0] || chi.zombie[0] || null;
    if (primo) {
      mirino(primo.x, primo.y, (13 + 2 * pulsa) * S, oro, passi * 0.08);
      for (const t of chi.lott.concat(chi.zombie).slice(1)) mirino(t.x, t.y, 9 * S, oro, -passi * 0.08);
    } else mirino(e.x, e.y, 9 * S, col, passi * 0.05);
    // La carica fra le mani, col tempo che resta tutto intorno.
    const Rc = (7 + 3 * pulsa) * S, g = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, Rc * 2.2);
    g.addColorStop(0, "#ffffff"); g.addColorStop(0.35, col); g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.globalAlpha = 1; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(o.x, o.y, Rc * 2.2, 0, Math.PI * 2); ctx.fill();
    const resta = Math.max(0, 1 - m.t / MIRA.attesa), Rt = 20 * S;
    ctx.globalAlpha = 0.35; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 4.5 * S;
    ctx.beginPath(); ctx.arc(o.x, o.y, Rt, 0, Math.PI * 2); ctx.stroke();
    if (resta > 0.005) {
      const c2 = resta > 0.3 ? col : "#ff5a4a";
      ctx.globalAlpha = 1; ctx.strokeStyle = c2; ctx.lineWidth = 3.4 * S; ctx.shadowColor = c2; ctx.shadowBlur = 10 * S;
      ctx.beginPath(); ctx.arc(o.x, o.y, Rt, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * resta); ctx.stroke();
      ctx.shadowBlur = 0;
    }
    ctx.restore();
  }

  // Il K.O. della mossa finale: uno solo, nel momento che decide la scena.
  function contaFatale() {
    const F = fatale;
    if (F.contato) return;
    F.contato = true; F.io = true;
    segnaKO(F.da, F.a);
    F.io = false;
    fataliFatti++;
  }
  function lasciaAndare(f, vx, vy) {
    f.fatVola = false; f.inVolo = true; f.fantasma = true;
    for (const n in f.p) { f.p[n].ox = f.p[n].x - vx; f.p[n].oy = f.p[n].y - vy; }
  }
  function fineFatale(annullato) {
    const F = fatale;
    if (!F) return;
    fatale = null;
    F.da.alza = 0;
    if (F.a.fatVola) lasciaAndare(F.a, 0, 0);
    if (annullato && !F.contato) fataleRound = true;            // non si è fatta: resta buona per dopo
    for (const l of [F.da, F.a]) if (!l.ko && !l.esploso) { l.azione = null; l.pensa = 12; }
  }
  function aggiornaFatale() {
    fataleBuio += ((fatale ? FATALE.buio : 0) - fataleBuio) * 0.12;
    if (fataleVoluto && !fatale) vogliaFatale();
    const F = fatale;
    if (!F) return;
    const da = F.da, a = F.a, D = F.d, dir = F.dir;
    F.t++;
    // Qualcosa da fuori ha rotto la scena (il puntatore, un'esplosione prima del colpo): si lascia perdere.
    if (da.preso || a.preso || da.esploso || a.esploso || da.fuoriCampo || a.fuoriCampo || orda || (!F.contato && (da.ko > 0 || a.ko > 0)) || F.t > 520) { fineFatale(true); return; }
    if (a.fatVola) a.ko = Math.max(a.ko, 70);
    if (F.fase === "annuncio") {
      // Chi chiude va a mettersi alla distanza giusta; l'altro barcolla.
      const meta = Math.max(24 * S, Math.min(W - 24 * S, a.cx - dir * FATALE.dove[F.tipo] * S)), manca = meta - da.cx;
      if (Math.abs(manca) > 5 * S && F.t < 100) {
        if (da.azione !== "avanza") { da.azione = "avanza"; da.t = 0; da.durata = 999; }
        da.meta = meta; da.corsa = 4; da.voltato = Math.sign(manca) !== dir; if (da.voltato) da.dir = dir;
      } else if (F.t >= 34) {
        if (Math.abs(manca) > 5 * S) { zip(da.p.bacino.x, da.p.bacino.y, COLORI_ANIME[da.tipo]); muoviTutto(da, manca, 0); }
        da.azione = null; da.dir = dir; da.voltato = false; F.fase = "mossa"; F.m = 0;
      } else if (da.azione === "avanza") da.azione = null;
      return;
    }
    if (F.fase === "fine") { if (++F.m > 34) fineFatale(false); return; }
    const m = F.m++;
    const colpo = (testo) => {
      const c = a.p.collo;
      contaFatale();
      fermoColpo = Math.max(fermoColpo, 9); scossa = Math.max(scossa, 12);
      scintille(c.x, c.y, 16, "#ffffff");
      if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "lampo", x: c.x, y: c.y, vx: 0, vy: 0, vita: 8, max: 8, r: 150 * S });
      if (testo) scrivi(testo, c.x, c.y - 26 * S, false);
    };
    if (F.tipo === "sferona") {
      // Si carica sopra la testa una sfera enorme, poi la lascia cadere addosso
      // all'altro: scoppia, e la pagina si crepa davvero (05/10/2026, chiesto da Riccardo).
      const carica = 112, viaggio = 26;
      if (m === 0) { inizia(da, "sfera"); da.durata = 999; D.r = 5 * S; D.volo = 0; }
      if (m <= carica) {
        const k = m / carica, mani = { x: (da.p.manoA.x + da.p.manoD.x) / 2, y: Math.min(da.p.manoA.y, da.p.manoD.y) };
        D.r = (5 + 138 * k * k) * S;                             // enorme: più del doppio della sfera normale
        D.x = mani.x; D.y = mani.y - D.r * 0.82;
        scossa = Math.max(scossa, 1 + 9 * k);
        if (m % 2 === 0 && particelle.length < MAX_PARTICELLE - 20) {
          const lato = Math.floor(Math.random() * 3);
          particelle.push({ tipo: "mote", x: lato === 0 ? 0 : lato === 1 ? W : caso(0, W), y: lato === 2 ? pavimento : caso(testataBasso, pavimento),
                            vx: 0, vy: 0, vita: 70, max: 70, verso: { sfera: D }, colore: Math.random() < 0.5 ? "#ffffff" : COLORI_ANIME[da.tipo] });
        }
        if (m % 10 === 0 && particelle.length < MAX_PARTICELLE && da.base >= pavimento - 2) {
          particelle.push({ tipo: "detrito", x: da.cx + caso(-40, 40) * S, y: da.base - 2, vx: caso(-0.5, 0.5) * S, vy: -caso(3, 6) * S,
                            vita: 70, max: 70, rot: 0, va: caso(-0.2, 0.2), lato: caso(1.6, 3.2) * S, colore: "#9a948a" });
        }
        if (m === Math.round(carica * 0.55)) scrivi("SFERA FINALE!", D.x, D.y - D.r - 16 * S, true);
      } else if (m <= carica + viaggio) {
        // Giù, dritta addosso a lui.
        const k = (m - carica) / viaggio, c = a.p.collo;
        D.volo = D.volo || { x0: D.x, y0: D.y };
        D.x = D.volo.x0 + (c.x - D.volo.x0) * k; D.y = D.volo.y0 + (c.y - D.volo.y0) * k;
        da.azione = null;
        if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "scintilla", x: D.x + caso(-1, 1) * D.r, y: D.y + caso(-1, 1) * D.r, vx: 0, vy: 0, vita: 12, max: 12, colore: COLORI_ANIME[da.tipo] });
      } else if (!D.scoppiata) {
        D.scoppiata = true;
        const x = a.p.bacino.x, y = Math.min(a.p.bacino.y, pavimento - 10 * S);
        colpo("KA-BOOOM!");
        // Lo scoppio non lo manda in pezzi (il K.O. della scena è già contato) ma sfonda la pagina.
        esplosione(x, y, 3.4, da, false);
        sfondaPagina(x, y, 1.5);
        da.ko = 0; da.inVolo = false;
        lasciaAndare(a, -dir * 9 * S, -7 * S);
        a.ko = Math.max(a.ko, 120);
        fermoColpo = Math.max(fermoColpo, 14);
        D.r = 0;
      } else if (m > carica + viaggio + 16) { F.fase = "fine"; F.m = 0; }
      return;
    }
    if (F.tipo === "meteora") {
      // Lo manda per aria con un calcio e gli tira addosso una meteora.
      if (m === 0) inizia(da, "montante");
      if (m === 11) { colpo("SBAM!"); a.fatVola = true; a.fantasma = true; D.vy = -17 * S; D.base = a.base; }
      if (a.fatVola && !D.ferma) {
        muoviTutto(a, 0, D.vy); ruotaTutto(a, 0.16 * dir); D.vy += 0.55 * S;
        if (D.vy > 0 && a.p.bacino.y > testataBasso + 150 * S) { D.ferma = true; D.m0 = m; D.mx = a.p.bacino.x; D.my = Math.max(testataBasso + 40 * S, a.p.bacino.y - 90 * S); }
      }
      if (D.ferma && !D.scoppiata) {
        // Resta appeso lassù mentre la meteora arriva da sopra.
        const giu = m - D.m0, lungo = 44;
        for (const n in a.p) { a.p[n].oy = a.p[n].y; a.p[n].ox = a.p[n].x; }
        if (giu === 2) { D.alta = -140 * S; scrivi("METEORA!", a.p.bacino.x, Math.max(testataBasso + 20 * S, a.p.bacino.y - 120 * S), true); }
        if (giu >= 2) {
          const k = Math.min(1, (giu - 2) / lungo);
          D.mety = D.alta + (a.p.bacino.y - D.alta) * k * k;
          D.metx = D.mx + (a.p.bacino.x - D.mx) * k;
          D.raggioM = (16 + 22 * k) * S;
          scossa = Math.max(scossa, 4 + 10 * k);
          if (particelle.length < MAX_PARTICELLE) {
            particelle.push({ tipo: "fuoco", x: D.metx + caso(-6, 6) * S, y: D.mety - caso(6, 20) * S, vx: caso(-0.6, 0.6) * S, vy: -caso(1, 3) * S,
                              vita: 20, max: 20, r: caso(4, 9) * S });
          }
          if (k >= 1) {
            D.scoppiata = true;
            const x = a.p.bacino.x, y = Math.min(a.p.bacino.y, pavimento - 10 * S);
            colpo("KA-BOOOM!");
            esplosione(x, y, 2.4, da, false);
            sfondaPagina(x, y, 0.9);
            da.ko = 0; da.inVolo = false;
            lasciaAndare(a, caso(-3, 3) * S, 12 * S);
            a.ko = Math.max(a.ko, 120); D.dopo = 0;
            fermoColpo = Math.max(fermoColpo, 14);
          }
        }
      }
      if (D.scoppiata && ++D.dopo > 22) { F.fase = "fine"; F.m = 0; }
      return;
    }
    if (F.tipo === "vortice") {
      // Un mulinello che lo tira su e lo trascina da una parte all'altra della pagina,
      // raschiando quello che trova, poi lo pianta a terra (05/10/2026, chiesto da Riccardo).
      const parte = 12, giro = 132;
      if (m === 0) { inizia(da, "spingi"); da.durata = 999; }
      if (m === parte) {
        colpo("FWOOSH!");
        a.fatVola = true; a.fantasma = true;
        D.x0 = a.p.bacino.x; D.base = a.base; D.ang = 0; D.r = 20 * S; D.cx = D.x0; D.graffio = 0;
        // (di lato e più in alto del conto dei K.O., che compare nello stesso momento)
        scrivi("MULINELLO!", Math.max(100 * S, Math.min(W - 100 * S, D.x0 - dir * 150 * S)), Math.max(testataBasso + 24 * S, D.base - 212 * S), true);
      }
      if (a.fatVola && m > parte && m <= parte + giro) {
        const k = (m - parte) / giro;
        D.ang += 0.36;
        D.r = (20 + 40 * Math.sin(Math.PI * k)) * S;
        D.alto = Math.min(1, (m - parte) / 26) * (120 + 70 * Math.sin(Math.PI * k)) * S;
        // Spazzata: lo porta di là e lo riporta indietro, restando dentro la finestra.
        const quanto = Math.min(W * 0.3, 240 * S);
        D.cx = Math.max(70 * S, Math.min(W - 70 * S, D.x0 + Math.sin(k * Math.PI * 2) * quanto * dir));
        const x = D.cx + Math.cos(D.ang) * D.r, y = D.base - D.alto + Math.sin(D.ang) * D.r * 0.28;
        muoviTutto(a, Math.max(26 * S, Math.min(W - 26 * S, x)) - a.p.bacino.x, Math.max(testataBasso + 30 * S, Math.min(pavimento - 20 * S, y)) - a.p.bacino.y);
        ruotaTutto(a, 0.2 * dir);
        scossa = Math.max(scossa, 5);
        // Il piede del mulinello raschia il pavimento e la striscia, e tira a sé quello che trova.
        if (++D.graffio % 26 === 0) danneggiaStriscia(D.cx, 0.5, true);
        if (m % 3 === 0 && particelle.length < MAX_PARTICELLE) {
          particelle.push({ tipo: "polvere", x: D.cx + caso(-40, 40) * S, y: D.base - 2, vx: caso(-2, 2) * S, vy: -caso(2, 5) * S,
                            vita: 40, max: 40, colore: Math.random() < 0.5 ? "#8a7f70" : "#b9b4ab" });
        }
        for (const t of telefoni) {
          if (t.stato === "impugnato" || t.stato === "portato" || Math.abs(t.x - D.cx) > 150 * S) continue;
          t.stato = "volo"; t.ox = t.x - (D.cx - t.x) * 0.1; t.oy = t.y - (D.base - 60 * S - t.y) * 0.08;
        }
      }
      if (m === parte + giro + 1) {
        // Giù di schianto.
        D.finito = true;
        const x = Math.max(30 * S, Math.min(W - 30 * S, a.p.bacino.x));
        muoviTutto(a, x - a.p.bacino.x, D.base - 12 * S - a.p.bacino.y);
        colpo("SBAM!");
        sfondaPagina(x, D.base - 10 * S, 1.1);
        lasciaAndare(a, 0, 6 * S);
        a.ko = Math.max(a.ko, 120);
        fermoColpo = Math.max(fermoColpo, 12);
      }
      if (m > parte + giro + 20) { F.fase = "fine"; F.m = 0; }
      return;
    }
    if (F.tipo === "crepa") {
      // Un pugno nel pavimento: la crepa corre verso di lui spaccando la pagina, e lo sbalza via.
      const salto = 16, giu = 30;
      if (m === 0) { inizia(da, "salto"); da.durata = 999; D.fronte = 0; }
      if (m <= salto) da.alza = 96 * S * (m / salto);
      else if (m <= giu) da.alza = 96 * S * (1 - (m - salto) / (giu - salto));
      if (m === giu) {
        da.alza = 0; da.azione = null;
        scossa = Math.max(scossa, 22); fermoColpo = Math.max(fermoColpo, 8);
        scrivi("CREPA!", da.cx, da.base - 70 * S, true);
        polvere(da.cx, da.base - 2, 10);
        danneggiaStriscia(da.cx, 0.8, true);
      }
      if (m > giu && !F.contato) {
        // Il fronte della crepa, che avanza a scatti verso di lui.
        D.fronte += 14 * S;
        const px = da.cx + dir * D.fronte;
        if (Math.floor(D.fronte / (60 * S)) !== Math.floor((D.fronte - 14 * S) / (60 * S))) {
          danneggiaStriscia(Math.max(20 * S, Math.min(W - 20 * S, px)), 0.75, true);
          polvere(px, da.base - 2, 5);
          scossa = Math.max(scossa, 10);
        }
        if (particelle.length < MAX_PARTICELLE) {
          particelle.push({ tipo: "detrito", x: px, y: da.base - 2, vx: caso(-1.5, 1.5) * S, vy: -caso(3, 7) * S,
                            vita: 70, max: 70, rot: caso(0, 6), va: caso(-0.3, 0.3), lato: caso(2, 4) * S, colore: "#8a7f70" });
        }
        if (Math.abs(px - a.cx) < 30 * S || D.fronte > Math.abs(a.cx - da.cx) + 30 * S) {
          colpo("KRAK!");
          sfondaPagina(a.cx, a.base - 10 * S, 1.3);
          a.fatVola = true; a.fantasma = true; D.vy = -15 * S; D.giu = false;
        }
      }
      if (a.fatVola && F.contato) {
        muoviTutto(a, dir * 1.6 * S, D.vy); ruotaTutto(a, 0.14 * dir); D.vy += 0.75 * S;
        if (D.vy > 0 && a.p.bacino.y >= a.base - 14 * S) { lasciaAndare(a, dir * 2 * S, 3 * S); a.ko = Math.max(a.ko, 110); D.posato = 0; }
      }
      if (F.contato && !a.fatVola && ++D.posato > 24) { F.fase = "fine"; F.m = 0; }
      if (m > 300) { F.fase = "fine"; F.m = 0; }
      return;
    }
    if (F.tipo === "orbita") {
      if (m === 0) inizia(da, "montante");
      if (m === 11) { colpo("SBAM!"); a.fatVola = true; a.fantasma = true; D.vy = -24 * S; D.x = a.p.bacino.x; D.base = a.base; }
      if (a.fatVola && !D.su) {
        muoviTutto(a, 0, D.vy); ruotaTutto(a, 0.22 * dir); D.vy -= 0.6 * S;
        if (particelle.length < MAX_PARTICELLE && m % 2 === 0) particelle.push({ tipo: "fumo", x: a.p.bacino.x, y: a.p.bacino.y, vx: 0, vy: 2 * S, vita: 18, max: 18, r: 5 * S, colore: "#ffffff" });
        if (a.p.bacino.y < -120 * S) { D.su = true; D.attesa = 54; D.stella = 34; }
      } else if (D.su && !D.giu) {
        if (D.stella > 0) D.stella--;
        if (--D.attesa <= 0) { D.giu = true; muoviTutto(a, D.x - a.p.bacino.x, -90 * S - a.p.bacino.y); }
      } else if (D.giu && a.fatVola) {
        muoviTutto(a, 0, 30 * S); ruotaTutto(a, -0.3 * dir);
        // Ricade dov'era partito (il piano se lo ricorda la scena: da lassù il suo «sotto» sarebbe la testata).
        if (a.p.bacino.y >= D.base - 16 * S) {
          muoviTutto(a, 0, D.base - 14 * S - a.p.bacino.y);
          a.base = D.base; D.atterrato = true;
          lasciaAndare(a, 0, 0);
          scossa = Math.max(scossa, 14); fermoColpo = Math.max(fermoColpo, 5);
          polvere(a.p.bacino.x - 12 * S, D.base - 1, 6); polvere(a.p.bacino.x + 12 * S, D.base - 1, 6);
          schegge(a.p.bacino.x, D.base - 4 * S, 8, "#b9b3a8");
          scrivi("CRASH!", a.p.bacino.x, D.base - 46 * S, false);
          F.fase = "fine"; F.m = 0;
        }
      }
    } else if (F.tipo === "flipper") {
      if (m === 0) inizia(da, "calcio");
      if (m === 13) { colpo("BAM!"); a.fatVola = true; a.fantasma = true; D.vx = dir * 17 * S; D.vy = -3.2 * S; D.rimbalzi = 0; D.dopo = 0; }
      if (a.fatVola) {
        muoviTutto(a, D.vx, D.vy); ruotaTutto(a, 0.42 * Math.sign(D.vx));
        D.vy += 0.16 * S;
        // (i margini tengono dentro la finestra anche la testa, che gira intorno al bacino)
        const b = a.p.bacino, alto = testataBasso + 50 * S, basso = a.base - 46 * S;
        if (b.y > basso && D.vy > 0) D.vy = -Math.abs(D.vy) * 0.7;
        if (b.y < alto && D.vy < 0) D.vy = Math.abs(D.vy) * 0.7;
        if ((b.x > W - 42 * S && D.vx > 0) || (b.x < 42 * S && D.vx < 0)) {
          D.vx = -D.vx * 0.93; D.rimbalzi++;
          scossa = Math.max(scossa, 9); fermoColpo = Math.max(fermoColpo, 3);
          scintille(b.x, b.y, 12, "#ffe27a"); scrivi("BONK!", Math.max(40, Math.min(W - 40, b.x)), b.y - 22 * S, false);
        }
        if (D.rimbalzi >= 3 && ++D.dopo > 16) { lasciaAndare(a, D.vx * 0.5, D.vy); F.fase = "fine"; F.m = 0; }
      }
    } else if (F.tipo === "schiacciata") {
      const su = 16, fermo = 32, giu = 38, morbido = (u) => u * u * (3 - 2 * u);
      // Quanto sale: molto, ma senza uscire dalla finestra se si combatte su un elemento in alto.
      if (m === 0) { inizia(da, "salto"); da.durata = 60; D.x0 = da.cx; D.alto = Math.max(36 * S, Math.min(124 * S, a.base - testataBasso - 84 * S)); }
      da.fantasma = true;
      if (m <= su) { const u = morbido(m / su); da.alza = D.alto * u; muoviTutto(da, D.x0 + (a.cx - D.x0) * u - da.cx, 0); }
      else if (m <= fermo) da.alza = D.alto + Math.sin((m - su) * 0.5) * 3 * S;
      else if (m <= giu) da.alza = D.alto * (1 - (m - fermo) / (giu - fermo));
      if (m === giu) {
        da.alza = 0;
        colpo("SPIAT!");
        a.schiacciato = 150; a.fantasma = false;
        polvere(a.cx - 16 * S, a.base - 1, 6); polvere(a.cx + 16 * S, a.base - 1, 6);
        scossa = Math.max(scossa, 16);
      }
      if (m > giu && m <= giu + 12) muoviTutto(da, dir * 3.2 * S, 0);         // scende di lato
      if (m === giu + 14) { da.azione = null; F.fase = "fine"; F.m = 0; }
    } else if (F.tipo === "onda") {
      const parte = 28, dura = 62;
      if (m === 0) { inizia(da, "onda"); da.durata = 999; }
      const mani = maniDi(da);
      if (m < parte && m % 2 === 0) scintille(mani.x + caso(-10, 10) * S, mani.y + caso(-10, 10) * S, 2, COLORI_ANIME[da.tipo]);
      if (m === parte) { colpo("ZAAAP!"); a.fatVola = true; a.fantasma = true; D.raggio = 1; }
      if (m >= parte && m < parte + dura) {
        D.x0 = mani.x; D.y = mani.y; D.raggio = Math.min(1, (m - parte) / 4) * Math.min(1, (parte + dura - m) / 10);
        const b = a.p.bacino, bordo = dir > 0 ? W - 44 * S : 44 * S;
        if ((bordo - b.x) * dir > 2 * S) { muoviTutto(a, dir * Math.min(15 * S, Math.abs(bordo - b.x)), Math.min(0, a.base - 44 * S - b.y) * 0.3); ruotaTutto(a, 0.1 * dir); }
        else { if (!D.muro) { D.muro = true; scossa = Math.max(scossa, 12); scrivi("BONK!", Math.max(40, Math.min(W - 40, b.x)), b.y - 24 * S, false); } muoviTutto(a, caso(-1, 1) * S, caso(-1, 1) * S); }
        scossa = Math.max(scossa, 3);
        if (m % 2 === 0) scintille(a.p.collo.x, a.p.collo.y, 3, COLORI_ANIME[da.tipo]);
      }
      if (m === parte + dura) { D.raggio = 0; da.azione = null; lasciaAndare(a, -dir * 2 * S, 0); F.fase = "fine"; F.m = 0; }
    } else if (F.tipo === "statua") {
      if (m === 0) inizia(da, "gelo");
      if (m === 14) { a.azione = null; congela(a, da, a.p.collo.x, a.p.collo.y); if (!(a.gelato > 0)) { fineFatale(true); return; } a.gelato = 400; }
      if (m === 46) inizia(da, "fulmine");
      if (m === 58) { D.saetta = 9; D.sx = a.p.collo.x; D.sy = a.p.collo.y; }
      if (D.saetta > 0) D.saetta--;
      if (m === 60) {
        rompiGhiaccio(a, true);
        colpo("");
        schegge(a.p.collo.x, a.p.collo.y, 18, "#dff4ff");
        for (const n in a.p) { a.p[n].ox = a.p[n].x + dir * -3 * S; a.p[n].oy = a.p[n].y + 3 * S; }
        a.inVolo = true;
      }
      if (m === 78) { F.fase = "fine"; F.m = 0; }
    } else if (F.tipo === "taglio") {
      const parte = 8, arriva = 15, zac = 50;
      if (m === 0) { inizia(da, "affondo"); da.durata = 999; D.x0 = da.cx; D.x1 = Math.max(24 * S, Math.min(W - 24 * S, a.cx + dir * 72 * S)); D.y = a.p.collo.y + 8 * S; }
      da.fantasma = true;
      if (m >= parte && m <= arriva) { const u = (m - parte) / (arriva - parte); muoviTutto(da, D.x0 + (D.x1 - D.x0) * u - da.cx, 0); D.scia = 1; }
      if (m > arriva && D.scia > 0) D.scia = Math.max(0, D.scia - 0.06);
      if (m === arriva + 1) { da.azione = null; scintille(a.p.collo.x, D.y, 6, "#ffffff"); }
      if (m === zac) {
        D.taglio = 10;
        colpo("ZAC!");
        for (const n in a.p) { a.p[n].ox = a.p[n].x + dir * 2 * S; a.p[n].oy = a.p[n].y + 2 * S; }
      }
      if (D.taglio > 0) D.taglio--;
      if (m === zac + 20) { F.fase = "fine"; F.m = 0; }
    }
    // Chi è portato in giro dalla scena non finisce sotto il piano né oltre i bordi di lato
    // (in alto sì: «in orbita» esce apposta dalla finestra, per un secondo).
    if (a.fatVola || D.atterrato) {
      D.atterrato = false;
      const piano = Math.min(pavimento, D.base !== undefined ? D.base : a.base) - 1;
      for (const n in a.p) {
        const q = a.p[n];
        if (q.y > piano) { q.y = piano; q.oy = piano; }
        if (q.x < 2) { q.x = 2; q.ox = 2; } else if (q.x > W - 2) { q.x = W - 2; q.ox = W - 2; }
      }
    }
  }
  // Il buio intorno ai due, sotto i lottatori.
  function disegnaBuioFatale() {
    if (fataleBuio < 0.01) return;
    const F = fatale;
    const cx = F ? (F.da.p.bacino.x + F.a.p.bacino.x) / 2 : W / 2, cy = F ? Math.min(pavimento, Math.max(0, (F.da.p.bacino.y + F.a.p.bacino.y) / 2)) : pavimento - 60 * S;
    const g = ctx.createRadialGradient(cx, cy, 70 * S, cx, cy, Math.max(W, H) * 0.75);
    g.addColorStop(0, "rgba(10,8,22,0)"); g.addColorStop(0.5, "rgba(10,8,22," + (fataleBuio * 0.8).toFixed(3) + ")"); g.addColorStop(1, "rgba(10,8,22," + fataleBuio.toFixed(3) + ")");
    ctx.save(); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); ctx.restore();
  }
  // Quello che la scena aggiunge sopra i lottatori: le stelline di chi barcolla, la stella in cielo, l'onda, la saetta, il taglio.
  function disegnaFatale() {
    const F = fatale;
    if (!F) return;
    const da = F.da, a = F.a, D = F.d, col = COLORI_ANIME[da.tipo], dir = F.dir;
    ctx.save();
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    if (F.fase === "annuncio" || (F.fase === "mossa" && !F.contato && F.tipo !== "statua")) {
      // Le stelline che girano sopra la testa di chi sta per prenderle.
      const t = a.p.testa;
      for (let i = 0; i < 3; i++) {
        const ang = passi * 0.14 + i * 2.1, x = t.x + Math.cos(ang) * 11 * S, y = t.y - 15 * S + Math.sin(ang) * 3 * S;
        ctx.fillStyle = "#ffd84a"; ctx.strokeStyle = "#141414"; ctx.lineWidth = 0.8 * S;
        ctx.beginPath();
        for (let k = 0; k < 8; k++) { const r = (k % 2 ? 1.4 : 3.4) * S, aa = k * Math.PI / 4; if (k) ctx.lineTo(x + Math.cos(aa) * r, y + Math.sin(aa) * r); else ctx.moveTo(x + r, y); }
        ctx.closePath(); ctx.fill(); ctx.stroke();
      }
    }
    if (F.tipo === "sferona" && D.r > 0) {
      disegnaSferaGrande(D.x, D.y, D.r, col);
    }
    if (F.tipo === "vortice" && D.cx !== undefined && !D.finito) {
      // L'imbuto: righe che girano, strette in basso e larghe in alto.
      const base = D.base, alto = D.alto || 0;
      ctx.globalAlpha = 0.75; ctx.strokeStyle = "#5c5347"; ctx.lineWidth = 2.6 * S;
      for (let i = 0; i < 8; i++) {
        const u = i / 7, y = base - alto * u - 6 * S, rr = (12 + 54 * u) * S;
        const sf = Math.sin(D.ang * 0.8 + i * 1.1);
        ctx.beginPath(); ctx.ellipse(D.cx + sf * 6 * S, y, rr, rr * 0.32, 0, 0, Math.PI * 2); ctx.stroke();
      }
      ctx.globalAlpha = 0.34; ctx.fillStyle = "#6f6557";
      ctx.beginPath(); ctx.moveTo(D.cx - 12 * S, base); ctx.lineTo(D.cx - 62 * S, base - alto - 8 * S);
      ctx.lineTo(D.cx + 62 * S, base - alto - 8 * S); ctx.lineTo(D.cx + 12 * S, base); ctx.closePath(); ctx.fill();
      ctx.globalAlpha = 1;
    }
    if (F.tipo === "crepa" && D.fronte > 0) {
      // La crepa che corre sul pavimento: una spezzata nera che si allarga.
      const y = da.base - 1, passo = 22 * S;
      ctx.globalAlpha = 0.95; ctx.strokeStyle = "#241f1b"; ctx.lineWidth = 5 * S;
      ctx.beginPath(); ctx.moveTo(da.cx, y);
      for (let x = passo; x <= D.fronte; x += passo) {
        const px = da.cx + dir * x;
        ctx.lineTo(px, y - ((x / passo) % 2 ? 5 : 1) * S);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    if (F.tipo === "meteora" && D.ferma && !D.scoppiata && D.raggioM > 0) {
      // La meteora che cala: sasso scuro, alone di fuoco, scia.
      const x = D.metx, y = D.mety, r = D.raggioM;
      ctx.globalAlpha = 0.5; ctx.fillStyle = "#ff8a1a";
      ctx.beginPath(); ctx.moveTo(x - r * 0.8, y); ctx.lineTo(x, y - r * 7); ctx.lineTo(x + r * 0.8, y); ctx.closePath(); ctx.fill();
      ctx.globalAlpha = 0.85; tondo(x, y, r * 1.5, "#ffb62e");
      ctx.globalAlpha = 1; tondo(x, y, r, "#4a4038");
      ctx.strokeStyle = "#2a241f"; ctx.lineWidth = 1.4 * S;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
      for (let i = 0; i < 3; i++) tondo(x + Math.cos(i * 2.1) * r * 0.45, y + Math.sin(i * 2.1) * r * 0.4, r * 0.18, "#2a241f");
    }
    if (F.tipo === "orbita" && D.stella > 0) {
      // Dove è sparito, una stella che brilla e si spegne.
      const x = Math.max(20, Math.min(W - 20, D.x)), y = Math.max(16, testataBasso + 16 * S), k = Math.sin(Math.PI * (1 - D.stella / 34)), r = Math.max(0.5, 15 * S * k);
      ctx.globalAlpha = Math.min(1, k * 1.5); ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2.4 * S;
      ctx.beginPath(); ctx.moveTo(x - r, y); ctx.lineTo(x + r, y); ctx.moveTo(x, y - r); ctx.lineTo(x, y + r); ctx.stroke();
      ctx.lineWidth = 1.2 * S; ctx.beginPath(); ctx.moveTo(x - r * 0.5, y - r * 0.5); ctx.lineTo(x + r * 0.5, y + r * 0.5); ctx.moveTo(x - r * 0.5, y + r * 0.5); ctx.lineTo(x + r * 0.5, y - r * 0.5); ctx.stroke();
      ctx.fillStyle = "#ffe27a"; ctx.beginPath(); ctx.arc(x, y, Math.max(0.5, r * 0.22), 0, Math.PI * 2); ctx.fill();
    }
    if (F.tipo === "onda" && D.raggio > 0) {
      // L'onda finale: dalle mani fino a lui, larga, col cuore bianco.
      const x1 = a.p.collo.x, y = D.y, spesso = (20 + Math.sin(passi * 0.9) * 3) * S * D.raggio;
      for (const [colore, k, alfa] of [[col, 1.5, 0.35], [col, 1, 0.9], ["#ffffff", 0.45, 1]]) {
        ctx.globalAlpha = alfa * D.raggio; ctx.strokeStyle = colore; ctx.lineWidth = Math.max(0.5, spesso * k);
        ctx.beginPath(); ctx.moveTo(D.x0, y); ctx.lineTo(x1, a.p.collo.y); ctx.stroke();
      }
      ctx.globalAlpha = 0.8 * D.raggio; ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(x1, a.p.collo.y, Math.max(0.5, spesso * 0.95), 0, Math.PI * 2); ctx.fill();
    }
    if (F.tipo === "statua" && D.saetta > 0) {
      // La saetta che manda in pezzi la statua.
      ctx.globalAlpha = Math.min(1, D.saetta / 5); ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 3.2 * S; ctx.shadowColor = "#9fd8ff"; ctx.shadowBlur = 12 * S;
      ctx.beginPath(); ctx.moveTo(D.sx + 14 * S, 0);
      const passiGiu = 7;
      for (let i = 1; i <= passiGiu; i++) ctx.lineTo(D.sx + (i === passiGiu ? 0 : Math.sin(i * 2.3 + passi) * 16 * S), D.sy * i / passiGiu);
      ctx.stroke(); ctx.shadowBlur = 0;
    }
    if (F.tipo === "taglio") {
      if (D.scia > 0) {
        // La scia dello scatto, da dov'era a dov'è.
        ctx.globalAlpha = D.scia; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 3 * S;
        ctx.beginPath(); ctx.moveTo(D.x0, D.y); ctx.lineTo(da.cx, D.y); ctx.stroke();
        ctx.globalAlpha = D.scia * 0.5; ctx.strokeStyle = col; ctx.lineWidth = 8 * S; ctx.stroke();
      }
      if (D.taglio > 0) {
        // Il taglio arriva dopo: una riga bianca di traverso, e cade.
        const c = a.p.collo, k = D.taglio / 10;
        ctx.globalAlpha = k; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = (2 + 5 * k) * S;
        ctx.beginPath(); ctx.moveTo(c.x - 26 * S, c.y + 20 * S); ctx.lineTo(c.x + 26 * S, c.y - 12 * S); ctx.stroke();
      }
    }
    ctx.restore();
  }

  // --- IL BUCO NERO (05/10/2026, su richiesta) -------------------------------
  // Si apre in un punto a caso, a mezz'aria, e per una decina di secondi tira
  // dentro tutto quello che gli passa vicino: i lottatori, gli oggetti, gli
  // zombie, i colpi d'energia. Chi ci finisce dentro sparisce e ne esce
  // DALL'ALTRA PARTE DELLO SCHERMO, a specchio (chi entra a destra esce a
  // sinistra), un po' intontito. Poi il buco si richiude.
  //  - La presa cresce man mano che ci si avvicina e dentro il raggio della
  //    bocca risucchia; chi è a terra o tenuto non viene tirato.
  //  - Quello che gli finisce addosso resta fermo un attimo, girando (è la
  //    «spirale»), e poi riesce dall'altra parte: niente teletrasporti
  //    istantanei che non si capiscono.
  //  - Durante l'orda vale anche per gli zombie: entrano da una parte e
  //    rispuntano dall'altra, che li rimette in gioco invece di toglierli.
  //  - È gratis? No: sta col meteo, come i meteoriti e l'orda.
  const BUCO = { apre: 36, dura: 540, chiude: 46, raggio: 150, bocca: 26, presa: 0.9, giro: 14, uscita: 34, vortice: 18, cattura: 0.55 };
  let buco = null;
  function avviaBuco(x, y) {
    if (buco) { buco.t = Math.min(buco.t, BUCO.apre); return; }
    const sopra = Math.max(testataBasso + 70 * S, pavimento - 300 * S);
    // Senza un punto preciso si apre dove c'è qualcosa da risucchiare: vicino a uno dei due
    // (o in mezzo, se sono vicini), all'altezza del busto o poco sopra.
    if (x === undefined || y === undefined) {
      const vivi = lottatori.filter((f) => f.p && !f.esploso && !f.fuori && !f.fuoriCampo);
      if (vivi.length) {
        const f = vivi[Math.floor(Math.random() * vivi.length)], g = vivi.find((l) => l !== f);
        const cx = g && Math.abs(g.cx - f.cx) < 200 * S ? (f.cx + g.cx) / 2 : f.cx;
        if (x === undefined) x = cx + caso(-80, 80) * S;
        // (i due possono stare su un elemento della pagina, in alto: il buco si apre lì, non verso il fondo)
        if (y === undefined) y = Math.max(testataBasso + 46 * S, Math.min(pavimento - 60 * S, f.p.bacino.y - caso(10, 70) * S));
      } else {
        if (x === undefined) x = caso(0.22, 0.78) * W;
        if (y === undefined) y = caso(sopra, pavimento - 90 * S);
      }
    }
    buco = { x, y, t: 0, fase: "apre", r: 0, giro: 0, dentro: [], passati: 0, seme: Math.random() * 6.28 };
    bucoVisti++;
    buco.x = Math.max(90 * S, Math.min(W - 90 * S, buco.x));
    scossa = Math.max(scossa, 6);
  }
  function fineBuco() {
    if (!buco) return;
    // Quello che era ancora dentro esce subito, dove si sarebbe aperto.
    for (const d of buco.dentro.slice()) sputaBuco(d, true);
    buco = null;
  }
  const raggioBuco = () => (buco.fase === "apre" ? buco.t / BUCO.apre : buco.fase === "chiude" ? Math.max(0, 1 - buco.t / BUCO.chiude) : 1) * BUCO.bocca * S;
  // Dall'altra parte dello schermo, a specchio. Col buco in mezzo allo schermo
  // l'uscita cadrebbe dentro la sua presa, e si rientrerebbe subito: in quel
  // caso si esce al bordo più lontano.
  function doveEsce(x, y) {
    let u = W - x;
    if (Math.abs(u - x) < BUCO.raggio * 1.25 * S) u = x < W / 2 ? W - 40 * S : 40 * S;
    return { x: Math.max(26 * S, Math.min(W - 26 * S, u)), y: Math.max(testataBasso + 30 * S, Math.min(pavimento - 40 * S, y)) };
  }
  function inghiotti(cosa, tipo) {
    buco.dentro.push({ cosa, tipo, t: 0, uscita: doveEsce(buco.x, buco.y) });
    buco.passati++;
    scintille(buco.x, buco.y, 8, "#c9a6ff");
    if (tipo === "lottatore") {
      const f = cosa;
      f.fuoriCampo = true; f.azione = null; f.coppia = null; f.onda = null; f.sfera = null; f.scatto = 0; f.jet = 0; f.paracadute = 0; f.fuga = null;
      f.ordine = null; f.scalata = null; f.supporto = null;
      if (f.tel) lasciaCadere(f);
      if (f.arma) lasciaArma(f);
      if (f.tiene) molla(f);
      // Da qui resta fermo dov'è, fuori dal gioco: il vortice che se lo porta dentro è solo disegnato (vedi `disegna`).
      for (const n in f.p) { f.p[n].ox = f.p[n].x; f.p[n].oy = f.p[n].y; }
      f.vortice = BUCO.vortice;
      scrivi("SLURP!", buco.x, buco.y - (BUCO.bocca + 14) * S, false);
    } else if (tipo === "zombie") cosa.inBuco = true;
    else if (tipo === "oggetto") { cosa.inBuco = true; cosa.stato = "volo"; cosa.da = null; cosa.x = cosa.ox = buco.x; cosa.y = cosa.oy = buco.y; }
  }
  function sputaBuco(d, subito) {
    const i = buco.dentro.indexOf(d);
    if (i >= 0) buco.dentro.splice(i, 1);
    const u = d.uscita;
    if (d.tipo === "lottatore") {
      const f = d.cosa;
      f.fuoriCampo = false; f.vortice = 0;
      let dx = u.x - f.p.bacino.x, dy = u.y - f.p.bacino.y;
      // Tutto intero dentro la finestra, comunque fosse girato quando è entrato.
      let x0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (const n in f.p) { const q = f.p[n]; x0 = Math.min(x0, q.x + dx); x1 = Math.max(x1, q.x + dx); y1 = Math.max(y1, q.y + dy); }
      if (y1 > pavimento - 2) dy -= y1 - (pavimento - 2);
      if (x0 < 4) dx += 4 - x0; else if (x1 > W - 4) dx -= x1 - (W - 4);
      for (const n in f.p) { const q = f.p[n]; q.x += dx; q.y += dy; q.ox = q.x - caso(-1, 1) * S; q.oy = q.y - caso(1, 2) * S; }
      u.x = f.p.bacino.x; u.y = f.p.bacino.y;
      f.cx = u.x; f.base = pavimento; f.supporto = null; f.inVolo = true; f.fantasma = true;
      f.ko = Math.max(f.ko, subito ? 20 : 34); f.stordito = Math.max(f.stordito, 20); f.pensa = 10; f.riBuco = 70;
      scrivi("PTUI!", u.x, u.y - 24 * S, false);
    } else if (d.tipo === "zombie") {
      const z = d.cosa;
      z.inBuco = false;
      if (orda) {
        z.x = Math.max(orda.l + 8 * S, Math.min(orda.r - 8 * S, u.x));
        z.lato = z.x < orda.cx ? -1 : 1; z.dir = -z.lato; z.vx = 0; z.botta = 20; z.stato = "esce"; z.s = 0;
        polvere(z.x, orda.base - 1, 4);
      }
    } else {
      const t = d.cosa;
      t.inBuco = false;
      t.x = u.x; t.y = u.y; t.ox = t.x + caso(-1, 1) * S; t.oy = t.y - caso(1, 3) * S; t.stato = "volo"; t.da = null; t.cool = 70;
    }
    zip(u.x, u.y, "#c9a6ff");
    scintille(u.x, u.y, 10, "#c9a6ff");
  }
  function aggiornaBuco() {
    if (!buco) return;
    const b = buco;
    b.t++; b.giro += 0.2;
    if (b.fase === "apre" && b.t >= BUCO.apre) { b.fase = "aperto"; b.t = 0; }
    else if (b.fase === "aperto" && b.t >= BUCO.dura) { b.fase = "chiude"; b.t = 0; }
    else if (b.fase === "chiude" && b.t >= BUCO.chiude) { fineBuco(); return; }
    b.r = raggioBuco();
    // Chi è dentro gira per un attimo e poi esce dall'altra parte.
    for (const d of b.dentro.slice()) {
      if (++d.t >= BUCO.uscita) { sputaBuco(d, false); continue; }
      if (d.tipo === "lottatore" && d.cosa.vortice > 0) d.cosa.vortice--;
    }
    if (b.fase === "chiude") return;
    const forte = b.fase === "aperto" ? 1 : b.t / BUCO.apre, R = BUCO.raggio * S;
    // I lottatori: tirati verso la bocca, e dentro il raggio vengono inghiottiti.
    for (const f of lottatori) {
      if (!f.p || f.esploso || f.preso || f.tenuto || f.fuoriCampo || f.fuori) continue;
      if (f.riBuco > 0) continue;                               // appena sputato fuori: un attimo di tregua
      if (fatale && (f === fatale.da || f === fatale.a)) continue;   // nel colpo finale conta solo la scena
      const q = f.p.bacino, dx = b.x - q.x, dy = b.y - q.y, d = Math.hypot(dx, dy) || 1;
      if (d > R) continue;
      // Chi arriva a metà del raggio è preso: da lì il vortice se lo porta dentro, anche da terra.
      if (d < Math.max(b.r + 10 * S, R * BUCO.cattura * forte)) { inghiotti(f, "lottatore"); continue; }
      if (f.ko > 0 && !f.inVolo) continue;                      // chi è a terra non lo tira
      const tira = BUCO.presa * forte * (1 - d / R) * S;
      for (const n in f.p) { f.p[n].x += dx / d * tira; f.p[n].y += dy / d * tira; }
      f.cx += dx / d * tira;
      if (passi % 10 === 0) scintille(q.x, q.y, 1, "#c9a6ff");
    }
    // Gli oggetti: quelli liberi o in volo.
    for (const t of telefoni) {
      if (t.inBuco || t.stato === "portato" || t.stato === "impugnato" || t.stato === "preso") continue;
      const dx = b.x - t.x, dy = b.y - t.y, d = Math.hypot(dx, dy) || 1;
      if (d > R) continue;
      if (d < b.r + 8 * S) { inghiotti(t, "oggetto"); continue; }
      const tira = BUCO.presa * 1.5 * forte * (1 - d / R) * S;
      if (t.cool > 0) continue;                                 // appena uscito: non lo riprende subito
      t.stato = "volo"; t.x += dx / d * tira; t.y += dy / d * tira; t.ox = t.x - dx / d * tira * 0.4; t.oy = t.y - dy / d * tira * 0.4;
    }
    // Gli zombie, durante l'orda: entrano da una parte e rispuntano dall'altra.
    if (orda) {
      for (const z of orda.zombie) {
        if (z.inBuco || !vivoZ(z)) continue;
        const c = corpoZ(z), dx = b.x - z.x, dy = b.y - c[1], d = Math.hypot(dx, dy) || 1;
        if (d > R) continue;
        if (d < Math.max(b.r + 12 * S, R * BUCO.cattura * forte)) { inghiotti(z, "zombie"); polvere(z.x, orda.base - 20 * S, 4); continue; }
        z.x += dx / d * BUCO.presa * 1.2 * forte * (1 - d / R) * S;
      }
    }
    // I colpi d'energia: ci finiscono dentro e spariscono.
    for (const q of proiettili) {
      if (q.vita <= 0) continue;
      if (Math.hypot(b.x - q.x, b.y - q.y) < b.r + 6 * S) { q.vita = 0; scintille(q.x, q.y, 6, "#c9a6ff"); }
    }
    // Polvere che gira intorno.
    if (passi % 2 === 0 && particelle.length < MAX_PARTICELLE - 30) {
      const a = caso(0, Math.PI * 2), r = caso(R * 0.45, R);
      particelle.push({ tipo: "mote", x: b.x + Math.cos(a) * r, y: b.y + Math.sin(a) * r, vx: 0, vy: 0, vita: 40, max: 40,
                        verso: { sfera: b }, colore: Math.random() < 0.4 ? "#c9a6ff" : "#ffffff" });
    }
  }
  function disegnaBuco() {
    if (!buco) return;
    const b = buco, R = BUCO.raggio * S, k = b.r / (BUCO.bocca * S);
    ctx.save();
    // L'alone che risucchia: un cerchio che si stringe, con dentro la luce stirata.
    const g = ctx.createRadialGradient(b.x, b.y, b.r * 0.6, b.x, b.y, R);
    g.addColorStop(0, "rgba(90,40,160,.55)"); g.addColorStop(0.45, "rgba(60,25,110,.22)"); g.addColorStop(1, "rgba(40,16,80,0)");
    ctx.globalAlpha = k; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(b.x, b.y, R, 0, Math.PI * 2); ctx.fill();
    // Le spirali.
    ctx.strokeStyle = "#c9a6ff"; ctx.lineCap = "round";
    for (let i = 0; i < 3; i++) {
      const a0 = b.seme + b.giro + i * Math.PI * 2 / 3;
      ctx.globalAlpha = 0.5 * k; ctx.lineWidth = 2 * S;
      ctx.beginPath();
      for (let u = 0; u <= 1.001; u += 0.08) {
        const rr = b.r + (R * 0.78 - b.r) * u, aa = a0 - u * 3.4;
        const px = b.x + Math.cos(aa) * rr, py = b.y + Math.sin(aa) * rr * 0.92;
        if (u === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
    // La bocca: nera, con l'orlo di luce.
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#07060c"; ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#e3d2ff"; ctx.lineWidth = 2.4 * S * k; ctx.stroke();
    ctx.globalAlpha = 0.5 * k; ctx.strokeStyle = "#c9a6ff"; ctx.lineWidth = 6 * S * k;
    ctx.beginPath(); ctx.arc(b.x, b.y, b.r + 4 * S, 0, Math.PI * 2); ctx.stroke();
    // Chi è dentro: un puntino che gira e si stringe verso il centro.
    ctx.globalAlpha = 1;
    for (const d of b.dentro) {
      const u = d.t / BUCO.uscita, rr = b.r * (1 - u) * 0.8, aa = b.giro * 3 + d.t * 0.3;
      const col = d.tipo === "lottatore" ? COLORI_ANIME[d.cosa.tipo] : d.tipo === "zombie" ? "#9dbf8c" : "#dcd6cc";
      tondo(b.x + Math.cos(aa) * rr, b.y + Math.sin(aa) * rr, Math.max(0.6, 3.4 * S * (1 - u)), col);
    }
    // E dall'altra parte, dove si viene sputati fuori, un lampo che avvisa.
    if (b.dentro.length) {
      const u = doveEsce(b.x, b.y), pulsa = 0.4 + 0.3 * Math.sin(passi * 0.4);
      ctx.globalAlpha = pulsa; ctx.strokeStyle = "#c9a6ff"; ctx.lineWidth = 2 * S;
      ctx.beginPath(); ctx.arc(u.x, u.y, (14 + 6 * Math.sin(passi * 0.3)) * S, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
  }

  // --- Eventi a sorpresa -----------------------------------------------
  // Gli eventi NON si annunciano con scritte sulla pagina (01/10/2026, su
  // richiesta: toglievano pulizia al sito): si vedono da quello che succede.

  const EVENTI_DA = { meteoriti: 100 * 60, buco: 70 * 60 };
  let bucoVisti = 0;
  function avviaEvento(forzato) {
    const meteo = libero("meteo");
    // I meteoriti non arrivano prima di cento secondi di lotta. L'orda non
    // sta in questo elenco: ha il suo orologio (vedi `aggiornaEventi`).
    // Il buco nero, la prima volta, non si tira a sorte: dopo settanta secondi è il primo imprevisto
    // che capita (un imprevisto nuovo che non si vede mai non serve a niente). Poi va nel mucchio.
    const quale = forzato ? forzato : meteo && !buco && !bucoVisti && tempo >= EVENTI_DA.buco ? "buco" :
                  scegli([[3, "luna"], [3, "furia"], [3, "pioggia"], [2, "rallenta"], [2.5, "terremoto"], [3, "jet"], [uragano || !meteo ? 0 : 1, "uragano"],
                          [meteo && tempo >= EVENTI_DA.meteoriti ? 2.5 : 0, "meteoriti"], [meteo && !acquazzone ? 2 : 0, "temporale"],
                          [meteo && !buco && tempo >= EVENTI_DA.buco ? 3 : 0, "buco"]]);
    if (quale === "uragano") { uragano = { x: Math.random() < 0.5 ? 100 * S : W - 100 * S, vx: 1.1 * S, t: 0 }; evento = { nome: quale, durata: 600 }; return; }
    if (quale === "luna") { moltG = 0.45; evento = { nome: quale, durata: 620 };  }
    else if (quale === "pioggia") { daSpawnare = 7;  }
    else if (quale === "rallenta") { ritmo = 0.45; evento = { nome: quale, durata: 150 };  }
    else if (quale === "jet") { for (const f of lottatori) if (!f.ko && !f.preso && !f.fuoriCampo) decolla(f, true); }
    else if (quale === "terremoto") { avviaSisma(); evento = { nome: quale, durata: SISMA.fine }; }
    else if (quale === "meteoriti") { avviaMeteore(); evento = { nome: quale, durata: 520 }; }
    else if (quale === "buco") { avviaBuco(); evento = { nome: quale, durata: BUCO.apre + BUCO.dura + BUCO.chiude + 10 }; }
    else if (quale === "zombie") { avviaOrda(ORDA.sorpresa); evento = { nome: quale, durata: 60 * 240 }; }
    else if (quale === "temporale") { pioggiaFino = tempo + 1100; evento = { nome: quale, durata: 1100 }; }
    else {
      const f = lottatori[Math.floor(Math.random() * lottatori.length)];
      f.furia = 560;
    }
  }

  function fineEvento() {
    if (evento && evento.nome === "uragano" && !uraganoFisso) uragano = null;
    if (evento && evento.nome === "buco") fineBuco();
    moltG = gravitaScelta; evento = null;
    // Se si sta mirando il tempo resta lento: torna normale quando parte il colpo.
    if (mira) mira.ritmo0 = rallentaFisso ? 0.45 : 1; else ritmo = rallentaFisso ? 0.45 : 1;
  }
  let uraganoFisso = false, rallentaFisso = false;

  function aggiornaEventi() {
    if (fermo) return;
    if (fatale) { prossimoEvento = Math.max(prossimoEvento, 90); prossimaOrda = Math.max(prossimaOrda, 90); }      // durante il colpo finale gli imprevisti aspettano
    if (--prossimoEvento <= 0) { if (sorprese && !evento) avviaEvento(); prossimoEvento = Math.round(caso(1500, 2700)); }
    // L'orda di zombie, col suo orologio. Se in quel momento c'è altro in corso, aspetta che finisca.
    if (--prossimaOrda <= 0) {
      if (!sorprese || !libero("meteo")) prossimaOrda = 600;
      else if (!evento && !orda && !sfida && lottatori.length === 2 && lottatori.every((f) => f.p && !f.esploso && !f.fuori)) {
        avviaOrda(ORDA.sorpresa);
        if (orda) { evento = { nome: "zombie", durata: 60 * 240 }; prossimaOrda = Math.round(caso(ORDA.poi[0], ORDA.poi[1]) * 60); }
      }
    }
    if (--prossimoTelefono <= 0) {
      const calmo = tempo < CALMA, inGiro = telefoni.filter((t) => !eArma(t)).length;
      if (inGiro < (calmo ? 2 : 4)) faEntrare(undefined, caso(60, W - 60), caso(-1.5, 1.5) * S);
      prossimoTelefono = Math.round(calmo ? caso(600, 1200) : caso(380, 950));
    }
    // Dopo 70 secondi piovono anche le armi, una alla volta.
    if (tempo >= ARMI && libero("armi") && --prossimaArma <= 0) {
      if (telefoni.filter((t) => eArma(t) || t.tipo === "bomba").length < 2) {
        faEntrare(scegli([[2, "pistola"], [2, "spada"], [1, "bomba"], [1.2, "bazooka"], [1.6, "lanciafiamme"]]), caso(80, W - 80), caso(-1, 1) * S);
      }
      prossimaArma = Math.round(caso(800, 1600));
    }
    if (daSpawnare > 0 && passi % 14 === 0) {
      daSpawnare--;
      const t = faEntrare(senzaTelefoni ? oggettoACaso() : undefined, caso(60, W - 60), caso(-2, 2) * S);
      // Nella pioggia di oggetti dell'estensione tutto arriva già innescato.
      if (senzaTelefoni) { t.armato = !!SPECIALI[t.tipo]; if (t.tipo === "bomba") t.miccia = Math.round(caso(140, 260)); }
    }
    if (evento && --evento.durata <= 0) fineEvento();
    for (const f of lottatori) {
      if (f.furia > 0) f.furia--;
      if (f.potenziato > 0 && --f.potenziato === 0 && f.forma) fineForma(f);
      // Il colosso sbuffa vapore dagli scarichi, l'albero perde qualche foglia.
      if (f.potenziato > 0 && f.forma && !stile && f.p && passi % 7 === 0 && particelle.length < MAX_PARTICELLE - 20) {
        if (f.tipo === "robot") {
          particelle.push({ tipo: "fumo", x: f.p.collo.x - f.dir * caso(6, 13) * S, y: f.p.collo.y - caso(2, 7) * S,
                            vx: -f.dir * caso(0.2, 0.7) * S, vy: -caso(0.6, 1.4) * S, vita: 44, max: 44, r: caso(3, 6) * S, colore: "#8d8a85" });
        } else {
          particelle.push({ tipo: "detrito", x: f.cx + caso(-26, 26) * S, y: f.p.testa.y - caso(4, 22) * S,
                            vx: caso(-0.7, 0.7) * S, vy: caso(0.3, 1.1) * S, vita: 90, max: 90, rot: caso(0, 6), va: caso(-0.12, 0.12),
                            lato: caso(1.8, 3) * S, colore: Math.random() < 0.5 ? "#3f9a3a" : "#2d7a2b" });
        }
      }
      if (anime && !f.esploso) f.ki = Math.min(100, f.ki + (f.forma > 0 && f.potenziato > 0 ? 0.12 : 0.04));
      if (f.piccolo > 0) f.piccolo--;
      f.scala += ((f.piccolo > 0 ? 0.55 : 1) - f.scala) * 0.15;
    }
    if (scossa > 0) scossa--;
  }

  // La faccina accanto al titolo perde il filo se i lottatori le arrivano vicino.
  let faccina = null, faccinaRiquadro = null;
  function aggiornaFaccina() {
    if (!faccina) {
      faccina = document.querySelector(".furbetto") || false;
    }
    if (!faccina || !faccina.getBoundingClientRect) return;
    const r = faccina.getBoundingClientRect();
    const margine = 70 * S;
    let vicino = false;
    for (const f of lottatori) {
      for (const n of ["testa", "collo", "bacino", "manoA", "manoD"]) {
        const pt = f.p[n];
        if (pt.x > r.left - margine && pt.x < r.right + margine && pt.y > r.top - margine && pt.y < r.bottom + margine) vicino = true;
      }
    }
    for (const t of telefoni) {
      if (t.x > r.left - margine && t.x < r.right + margine && t.y > r.top - margine && t.y < r.bottom + margine) vicino = true;
    }
    if (faccina.classList) faccina.classList[vicino ? "add" : "remove"]("stordito");
  }

  // --- La striscia delle notizie si rompe -------------------------------
  // Un lottatore (o un telefono) che si schianta sulla striscia la
  // danneggia: crepe che partono dal punto d'urto, e se il colpo è forte
  // un buco coi fili scoperti che sfavillano. Dopo una quarantina di
  // secondi i danni si «riparano» da soli: le notizie devono restare leggibili.
  const VITA_DANNO = 2000;
  function crepa(x0, y0, lun, ang) {
    const pt = [[x0, y0]];
    let x = x0, y = y0, a = ang;
    for (let i = 0; i < 5; i++) {
      a += caso(-0.7, 0.7);
      x += Math.cos(a) * lun / 5; y += Math.sin(a) * lun / 5;
      pt.push([x, y]);
    }
    return pt;
  }
  function danneggiaStriscia(x, forza, forzato) {
    if (!(pavimento < H - 4) || fermo) return;
    // Un danno nuovo al massimo ogni 5 secondi circa: la striscia deve
    // restare quasi sempre leggibile. Le mosse finali passano avanti.
    if (!forzato) for (const d of danni) if (d.eta < 420 || (Math.abs(d.x - x) < 26 * S && d.eta < 400)) return;
    const n = Math.round(3 + forza * 5);
    const crepe = [];
    for (let i = 0; i < n; i++) {
      crepe.push(crepa(0, 0, caso(14, 40 + forza * 40) * S, caso(0.15, Math.PI - 0.15)));
    }
    let buco = null;
    if (forza > 0.72 && danni.filter((d) => d.buco).length < 3) {
      const r = caso(9, 15) * S, pts = [];
      for (let i = 0; i < 9; i++) {
        const a = (i / 9) * Math.PI * 2, rr = r * caso(0.55, 1.15);
        pts.push([Math.cos(a) * rr * 1.3, Math.sin(a) * rr * 0.9]);
      }
      buco = pts;
    }
    danni.push({ x, eta: 0, crepe, buco, forza });
    if (danni.length > 5) danni.shift();
    scintille(x, pavimento + 4 * S, 12, "#ffe27a");
    schegge(x, pavimento + 2 * S, 8, "#ffffff");
    schegge(x, pavimento + 2 * S, 5, "#1f7a5a");
    scossa = Math.max(scossa, 6);
    const barra = mio.querySelector && mio.querySelector(".ultimora-barra");
    if (barra && barra.classList) {
      barra.classList.remove("ultimora-colpita"); void barra.offsetWidth;
      barra.classList.add("ultimora-colpita", "ultimora-guasta");
    }
    scrivi(buco ? "CRASH!" : "CRACK!", x, pavimento - 16 * S, true);
  }
  function aggiornaDanni() {
    for (const d of danniBordi) d.eta++;
    if (danniBordi.length && danniBordi[0].eta >= VITA_DANNO) danniBordi = danniBordi.filter((d) => d.eta < VITA_DANNO);
    for (const d of danni) {
      d.eta++;
      if (d.buco && d.eta % 22 === 0 && d.eta < VITA_DANNO - 700) scintille(d.x + caso(-8, 8) * S, pavimento + 14 * S, 3, "#8ff0ff");
      if (d.buco && d.eta % 40 === 0) polvere(d.x, pavimento + 8 * S, 1);
    }
    danni = danni.filter((d) => d.eta < VITA_DANNO);
    if (!danni.length) {
      const barra = mio.querySelector && mio.querySelector(".ultimora-barra");
      if (barra && barra.classList) barra.classList.remove("ultimora-guasta");
    }
  }
  // --- I bordi e il tetto della pagina si rompono -------------------------
  // Come la striscia: crepe che entrano nella pagina dal punto d'urto e, se
  // il colpo è forte, un buco da cui si vede il vuoto (nero, con le stelle).
  // Al massimo un danno nuovo ogni 5 s per lato; si riparano in ~33 s.
  function danneggiaBordo(lato, pos, forza) {
    if (fermo) return;
    for (const d of danniBordi) if (d.lato === lato && (d.eta < 300 || (Math.abs(d.pos - pos) < 30 * S && d.eta < 900))) return;
    const [a0, a1] = lato === "sinistra" ? [-Math.PI / 2 + 0.2, Math.PI / 2 - 0.2]
                   : lato === "destra" ? [Math.PI / 2 + 0.2, Math.PI * 1.5 - 0.2] : [0.15, Math.PI - 0.15];
    const crepe = [];
    for (let i = 0, n = Math.round(3 + forza * 5); i < n; i++) crepe.push(crepa(0, 0, caso(14, 40 + forza * 45) * S, caso(a0, a1)));
    let buco = null;
    if (forza > 0.6) {
      const r = caso(10, 18) * S;
      buco = [];
      for (let i = 0; i < 10; i++) { const a = (i / 10) * Math.PI * 2, rr = r * caso(0.6, 1.15); buco.push([Math.cos(a) * rr, Math.sin(a) * rr]); }
    }
    danniBordi.push({ lato, pos, eta: 0, crepe, buco, forza, stelle: [0, 1, 2, 3].map(() => [caso(-0.6, 0.6), caso(-0.6, 0.6)]) });
    if (danniBordi.length > 8) danniBordi.shift();
    const [x, y] = puntoBordo({ lato, pos });
    scintille(x, y, 10, "#ffe27a");
    for (let i = 0; i < 8 && particelle.length < MAX_PARTICELLE; i++) {
      particelle.push({ tipo: "detrito", x, y, vx: (lato === "destra" ? -1 : lato === "sinistra" ? 1 : caso(-1, 1)) * caso(1, 4) * S,
                        vy: caso(-2, 2) * S, vita: 90, max: 90, rot: caso(0, 6), va: caso(-0.3, 0.3), lato: caso(1.4, 3) * S, colore: "#9a948a" });
    }
    scossa = Math.max(scossa, 6);
    scrivi(buco ? "CRASH!" : "CRACK!", Math.max(60, Math.min(W - 60, x)), Math.max(30, y + (lato === "tetto" ? 30 * S : 0)), true);
  }
  const puntoBordo = (d) => (d.lato === "sinistra" ? [0, d.pos] : d.lato === "destra" ? [W, d.pos] : [d.pos, 0]);
  function disegnaBordi() {
    for (const d of danniBordi) {
      const vita = Math.min(1, (VITA_DANNO - d.eta) / 600);
      if (vita <= 0) continue;
      const [x, y] = puntoBordo(d);
      ctx.save(); ctx.globalAlpha = vita; ctx.translate(x, y);
      if (d.buco) {
        ctx.beginPath(); d.buco.forEach(([bx, by], i) => (i ? ctx.lineTo(bx, by) : ctx.moveTo(bx, by))); ctx.closePath();
        ctx.fillStyle = "#0d0f14"; ctx.fill();
        ctx.lineWidth = 2 * S; ctx.strokeStyle = "#3a3a3a"; ctx.lineJoin = "round"; ctx.stroke();
        for (const [sx, sy] of d.stelle) tondo(sx * 14 * S, sy * 14 * S, 0.8 * S, "#ffffff");
      }
      ctx.lineCap = "round"; ctx.lineJoin = "round";
      for (const c of d.crepe) {
        ctx.beginPath(); c.forEach(([cx, cy], i) => (i ? ctx.lineTo(cx, cy) : ctx.moveTo(cx, cy)));
        ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2.4 * S; ctx.stroke();
        ctx.strokeStyle = "#141414"; ctx.lineWidth = 1.1 * S; ctx.stroke();
      }
      ctx.restore();
    }
  }

  function disegnaDanni() {
    if (!danni.length) return;
    ctx.save();
    ctx.beginPath(); ctx.rect(0, pavimento - 1, W, barraAlta + 2); ctx.clip();
    for (const d of danni) {
      const resta = VITA_DANNO - d.eta;
      const vita = Math.min(1, resta / 600);
      ctx.globalAlpha = Math.max(0, vita);
      const y0 = pavimento + 1.5 * S;
      if (d.buco) {
        const k = vita < 1 ? 0.4 + 0.6 * vita : 1;
        ctx.save(); ctx.translate(d.x, pavimento + barraAlta * 0.5); ctx.scale(k, k);
        ctx.beginPath(); d.buco.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath();
        ctx.fillStyle = sfondo; ctx.fill();
        ctx.lineWidth = 2 * S; ctx.strokeStyle = "#141414"; ctx.lineJoin = "round"; ctx.stroke();
        ctx.lineWidth = 1 * S; ctx.strokeStyle = "#ffcf3a";
        ctx.beginPath(); ctx.moveTo(-3 * S, -3 * S); ctx.lineTo(1 * S, 0); ctx.lineTo(-1 * S, 3 * S);
        ctx.moveTo(4 * S, -2 * S); ctx.lineTo(1 * S, 1 * S); ctx.stroke();
        ctx.restore();
      }
      ctx.lineCap = "round"; ctx.lineJoin = "round";
      for (const c of d.crepe) {
        ctx.beginPath();
        c.forEach(([x, y], i) => (i ? ctx.lineTo(d.x + x, y0 + y) : ctx.moveTo(d.x + x, y0 + y)));
        ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2.4 * S; ctx.stroke();
        ctx.strokeStyle = "#141414"; ctx.lineWidth = 1.1 * S; ctx.stroke();
      }
    }
    ctx.restore();
  }

  function passo() {
    passi++; tempo++;
    if (passi % 45 === 0) rileva();
    const [a, b] = lottatori;

    for (const [f, altro] of [[a, b], [b, a]]) {
      f.rivale = altro;
      if (f.esploso || f.fuoriCampo) continue;
      if (f.tel && (f.ko > 0 || f.stordito || f.preso || f.dolore || f.tenuto)) lasciaCadere(f);
      if (f.arma && (f.ko > 0 || f.preso || f.tenuto)) lasciaArma(f);
      if (f.tiene && (f.ko > 0 || f.preso || f.tenuto)) molla(f);
      if (f.polv > 0) f.polv--;
      if (f.riBuco > 0) f.riBuco--;
      if (f.schiacciato > 0 && --f.schiacciato === 12) { scrivi("POP!", f.p.bacino.x, f.p.bacino.y - 30 * S, false); for (const n in f.p) f.p[n].oy = f.p[n].y + 3 * S; }
      if (f.scendeApposta > 0) f.scendeApposta--;
      // Chi era sollevato a distanza cade se chi lo teneva smette (o viene colpito).
      if (f.tenuto && f.tenuto.tele !== undefined && ((f.tenuto.da.azione !== "telecinesi" && f.tenuto.da.azione !== "levita") || f.preso)) { f.tenuto = null; f.ko = Math.max(f.ko, 40); f.inVolo = true; }
      // Il ghiaccio si scioglie da solo, o va in pezzi se si viene presi.
      if (f.gelato > 0 && (f.preso || f.tenuto || --f.gelato === 0)) rompiGhiaccio(f, false);
      if (f.preso || f.tenuto) { f.forza = 0; f.jet = 0; f.paracadute = 0; continue; }
      aggiornaCratere(f);
      if (f.sfera && f.azione !== "sfera") { scintille(f.sfera.x, f.sfera.y, 14, COLORI_ANIME[f.tipo]); f.sfera = null; }
      if (f.ko > 0) {
        f.forza = f.cratere && !f.cratere.attesa ? 0.75 : 0;
        // Da lanciato, il conto alla rovescia parte solo quando si è fermato.
        const bc = f.p.bacino, v = Math.hypot(bc.x - bc.ox, bc.y - bc.oy);
        // «Fermo» è anche chi non si sposta più da mezzo secondo (02/10/2026): un
        // corpo incastrato, o tenuto in posa nel cratere, trema sul posto con una
        // velocità che non scende mai sotto la soglia, e restava a terra per sempre.
        if (f.inVolo) {
          const q = f.koDove;
          if (q && Math.hypot(bc.x - q.x, bc.y - q.y) < 5 * S) q.n++; else f.koDove = { x: bc.x, y: bc.y, n: 0 };
        } else f.koDove = null;
        if (!f.inVolo || v < 1.2 * S || (f.koDove && f.koDove.n > 30)) {
          if (--f.ko === 0) { f.rialzo = 50; f.inVolo = false; f.cx = f.p.bacino.x; f.koVero = false; f.koDove = null; }
        }
      } else if (f.rialzo > 0) { f.forza = 1 - f.rialzo / 50; f.rialzo--; }
      else if (f.stordito > 0) { f.forza = 0.22; f.stordito--; }
      else f.forza = 1;
      // Durante le scosse si sta in piedi a fatica.
      if (f.trema > 0) { f.trema--; f.forza = Math.min(f.forza, 0.5); }
      if (f.gelato > 0) f.forza = 0;
      if (f.dolore > 0) f.dolore--;
      if (f.botta > 0) f.botta--;

      if (f.ko > 0 || f.preso) { f.jet = 0; f.caos = 0; f.scatto = 0; }
      if (!(f.jet > 0)) { f.volo = false; f.scatto = 0; }
      if (anime) aggiornaInseguimento(f, altro);
      if (f.caos > 0) f.forza = Math.min(f.forza, 0.35);
      // Nel colpo finale il piano resta quello della scena: chi salta altissimo per la schiacciata
      // non deve «posarsi» su un elemento della pagina che si trova a passare lì sotto.
      const inScena = fatale && fatale.fase !== "fine" && (f === fatale.da || f === fatale.a);
      if (!f.scalata && !inScena) {
        const [y, chi] = appoggio(f);
        f.base = y; f.supporto = chi;
      }
      // In volo la «base» è il corpo stesso: il busto resta dritto da solo.
      if (f.jet > 0) { f.base = f.p.bacino.y + 30 * S; f.supporto = null; }
      if (f.specchio > 0) f.specchio--;
      rispondeUguale(f, altro);
      pensa(f, altro);
      // La presa sull'avversario: lo si tiene finché dura la mossa, poi via.
      if (f.azione === "presa") aggiornaPresa(f, altro);
      else if (f.tiene) scaglia(f);
      if (f.azione === "balla") {
        if (f.ballo === "giravolta" && f.t % 10 === 0) f.dir = -f.dir;
        if (f.ballo === "dab" && f.t % 42 === 0 && f.t) f.dir = -f.dir;
        if (f.ballo === "moonwalk") f.cx -= f.dir * 0.5 * S;
        if (f.ballo === "saltelli" && f.t % 28 === 14) for (const n in f.p) f.p[n].oy = f.p[n].y + verso * 3.2 * S;
        if (f.t % 20 === 1) nota(f);
      }
      // Il paracadute: solo scendendo apposta da un elemento, mai da lanciato.
      {
        const piede = Math.max(f.p.piedeA.y, f.p.piedeD.y);
        if (!f.paracadute && verso > 0 && f.scendeApposta > 0 && !f.inVolo && !f.ko && !f.jet && !f.scalata &&
            f.base - piede > 45 * S && f.p.bacino.y - f.p.bacino.oy > 0) {
          f.paracadute = 1; f.scendeApposta = 0;
        } else if (f.paracadute && (f.base - piede < 4 * S || f.ko || f.inVolo || f.jet > 0)) {
          f.paracadute = 0;
          if (f.base - piede < 4 * S) polvere(f.p.bacino.x, f.base - 1, 3);
        }
        f.para = f.paracadute ? Math.min(1, f.para + 0.09) : Math.max(0, f.para - 0.1);
      }

      if (f.scalata) {
        const sc = f.scalata;
        f.t++;
        sc.y -= 0.8 * S;
        f.base = sc.y;
        if (sc.y <= sc.o.t + 2 * S) {
          // In cima: una spinta in su e verso l'interno, e si è sopra.
          const s = sc.lato;
          f.cx = (s < 0 ? sc.o.l : sc.o.r) - s * 14 * S;
          for (const n in f.p) { f.p[n].oy = f.p[n].y + 4.5 * S; f.p[n].ox = f.p[n].x + s * 2.2 * S; }
          f.scalata = null; f.base = sc.o.t; f.supporto = sc.o; f.pensa = 8;
        }
      } else if (f.jet > 0) {
        f.jet--;
        if (f.volo && f.scatto > 0) aggiornaScatto(f);
        else {
          const v = f.volo ? 4.5 : 2.2;
          f.cx += Math.max(-v * S, Math.min(v * S, (f.meta - f.cx) * (f.volo ? 0.12 : 0.08)));
        }
        f.passo += 0.12;
      } else if (f.azione === "avanza" && piovendo && !f.supporto && gambe(f) === 2 && Math.random() < 0.0025) {
        // Con la pioggia, sulla striscia bagnata si scivola.
        for (const n of ["piedeA", "piedeD", "ginocchioA", "ginocchioD"]) f.p[n].ox -= f.dir * 5 * S;
        for (const n of ["testa", "collo"]) f.p[n].ox += f.dir * 3 * S;
        f.ko = Math.max(f.ko, 45); f.inVolo = true; f.azione = null;
        scrivi("SCIVOLONE!", f.p.bacino.x, f.p.bacino.y - 30 * S, false);
      } else if (f.azione === "avanza") {
        // Camminando si passa davanti agli elementi: ci si arrampica solo per
        // raggiungere l'avversario che sta più in alto (lo decide `pensa`).
        const lato = Math.sign(f.meta - f.cx) || f.dir;
        if (!f.voltato) f.dir = lato;
        // Di corsa, se sta scappando da un meteorite.
        const corre = f.corsa > 0, ng = gambe(f);
        if (corre) f.corsa--;
        // Chi si trascina avanza a strappi, quando la mano piantata tira.
        const strappo = ng === 0 ? 0.45 + 0.9 * Math.abs(Math.sin(f.passo)) : 1;
        f.cx += lato * (corre ? 2.3 : Math.abs(f.meta - f.cx) > 220 * S ? 1.6 : 0.95) * S * andatura(f) * strappo;
        f.passo += ng === 0 ? 0.2 : corre ? 0.5 : 0.28;
        if (ng === 0 && passi % 16 === 0 && !f.polv) polvere(f.p.manoA.x, f.base - 1, 1);
      } else if (f.azione === "indietro") { f.cx -= f.dir * 1.0 * S * andatura(f); f.passo += gambe(f) === 0 ? 0.2 : 0.3; }
      else f.passo += 0.08;

      if (!f.scalata) {
        const dietro = striscia(f) && !eMela(f) && f.forza >= 1 ? DIETRO_STRISCIA * S * f.dir : 0;
        f.cx += (f.p.bacino.x + dietro - f.cx) * (f.forza < 1 ? 0.5 : 0.06);
        f.cx = Math.max(20 * S, Math.min(W - 20 * S, f.cx));
      }
    }
    // Non passarsi attraverso, se sono allo stesso livello.
    if (!a.ko && !b.ko && !a.preso && !b.preso && !a.tenuto && !b.tenuto && !a.coppia && !b.coppia && !fatale && Math.abs(a.base - b.base) < 10 * S) {
      const d = b.cx - a.cx, minimo = 26 * S;
      if (Math.abs(d) < minimo) {
        const s = d >= 0 ? 1 : -1, sposta = (minimo - Math.abs(d)) / 2;
        a.cx -= s * sposta; b.cx += s * sposta;
      }
    }

    for (const f of lottatori) {
      if (f.esploso) { aggiornaEsplosione(f); continue; }
      if (f.fuoriCampo) continue;                                // dentro il buco nero: fermo finché non riesce
      if (f.fatVola) continue;                                   // portato in giro dal colpo finale
      if (f.fuori) { volaFuori(f); continue; }
      // Il punto tenuto fermo: dal puntatore o dalle mani dell'avversario.
      const fisso = f.preso || (f.tenuto ? "collo" : null);
      // Muscoli.
      if (f.forza > 0) {
        const piede = verso > 0 ? Math.max(f.p.piedeA.y, f.p.piedeD.y) : Math.min(f.p.piedeA.y, f.p.piedeD.y);
        const inAria = !f.scalata && !f.coppia && !f.alza && (f.base - piede) * verso > 30 * S;
        let q;
        if (f.scalata) q = posaScalata(f);
        else if (f.cratere && !f.cratere.attesa && f.ko > 0) q = posaCratere(f);
        else if (inAria) {
          // Cadendo da un bordo i muscoli tengono solo la forma del corpo:
          // la discesa la fa la gravità, non un muscolo che tira giù.
          const vera = f.base; f.base = f.p.bacino.y + verso * (striscia(f) ? 6 : 30) * S; q = posa(f); f.base = vera;
        } else q = posa(f);
        const scatto = f.azione && COLPI[f.azione] ? 0.55 : 0.3;
        const intensita = f.scalata || (f.cratere && !f.cratere.attesa && f.ko > 0) ? 1.3 : f.coppia || f.alza ? 1.7 : (inAria ? 0.35 : 1);
        for (const nome in q) {
          const pt = f.p[nome], [tx, ty] = q[nome];
          const k = TIRO[nome] * f.forza * intensita *
            (COLPI[f.azione] && (nome === COLPI[f.azione][0]) ? 1.6 : 1);
          const mx = (tx - pt.x) * k, my = (ty - pt.y) * k;
          pt.x += mx; pt.y += my;
          pt.ox += mx * (1 - scatto); pt.oy += my * (1 - scatto);
        }
      }
      // LE GAMBE NON SI INCROCIANO (02/10/2026). «A» è la gamba davanti: se
      // voltandosi (o rialzandosi) finisce dietro l'altra, le due si scambiano
      // il nome invece di passarsi attraverso. Prima restavano incrociate
      // per quasi metà del tempo.
      if (!f.ko && !f.preso && !f.tenuto && !f.scalata && !f.gelato && f.azione !== "balla" && !(f.staccati.gA || f.staccati.gD) &&
          (f.p.piedeA.x - f.p.piedeD.x) * f.dir < -2 * S) scambiaGambe(f);
      // Tenuto in mano: il punto preso segue il puntatore, il resto penzola.
      if (fisso) {
        const pt = f.p[fisso], tx = f.preso ? presa.x : f.tenuto.x, ty = f.preso ? presa.y : f.tenuto.y;
        pt.ox = pt.x; pt.oy = pt.y;
        pt.x += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, tx - pt.x));
        pt.y += Math.max(-VELOCITA_MAX * S, Math.min(VELOCITA_MAX * S, ty - pt.y));
      }
      // In volo si passa attraverso il testo e i campi (come un oggetto
      // sollevato): urtandoli punto per punto il corpo si deformava. Restano
      // solidi il pavimento (la striscia) e i bordi della finestra.
      if (f.jet > 0 && !f.preso) { f.fantasma = true; applicaSpinta(f); } else f.fiamma = 0;
      // Verlet.
      for (const n in f.p) {
        const pt = f.p[n];
        if (fisso === n) continue;
        let vx = (pt.x - pt.ox) * 0.985, vy = (pt.y - pt.oy) * 0.985;
        const v = Math.hypot(vx, vy), lim = VELOCITA_MAX * S;
        if (v > lim) { vx *= lim / v; vy *= lim / v; }
        // Col paracadute si scende piano, ondeggiando un po'.
        if (f.para > 0.3) { vy = Math.min(vy, 1.5 * S); vx = vx * 0.96 + Math.sin(passi * 0.05) * 0.05 * S; }
        pt.ox = pt.x; pt.oy = pt.y;
        pt.x += vx; pt.y += vy + GRAVITA * S * moltG * verso;
      }
      // Vincoli: aste, elementi della pagina, pavimento, bordi.
      let urto = 0;
      const piattaforma = !(f.ko > 0 || f.inVolo) && verso > 0;
      for (let giro = 0; giro < 5; giro++) {
        for (const [p1, p2, L] of f.aste) {
          const dx = p2.x - p1.x, dy = p2.y - p1.y;
          const d = Math.hypot(dx, dy) || 0.001;
          const c = (d - L) / d * 0.5;
          const fermo1 = fisso && f.p[fisso] === p1, fermo2 = fisso && f.p[fisso] === p2;
          if (fermo1) { p2.x -= dx * c * 2; p2.y -= dy * c * 2; }
          else if (fermo2) { p1.x += dx * c * 2; p1.y += dy * c * 2; }
          else { p1.x += dx * c; p1.y += dy * c; p2.x -= dx * c; p2.y -= dy * c; }
        }
        for (const n in f.p) {
          const pt = f.p[n];
          if (fisso === n) continue;
          if (!f.fantasma) urto = Math.max(urto, urta(f, pt, piattaforma));
          if (pt.y > pavimento - pt.r) {
            const caduta = pt.y - pt.oy;
            if (caduta > 11.5 * S) danneggiaStriscia(pt.x, Math.min(1, caduta / (VELOCITA_MAX * S)));
            urto = Math.max(urto, Math.hypot(pt.x - pt.ox, pt.y - pt.oy));
            pt.y = pavimento - pt.r;
            if (pt.oy < pt.y) pt.oy = pt.y;
            pt.ox += (pt.x - pt.ox) * (piovendo ? 0.05 : 0.3);
          }
          if (pt.y < pt.r) {
            // Il tetto: si rompe se ci si sbatte forte, e a gravità rovesciata è il pavimento.
            if (pt.oy - pt.y > 9 * S) danneggiaBordo("tetto", pt.x, Math.min(1, (pt.oy - pt.y) / (VELOCITA_MAX * S)));
            urto = Math.max(urto, Math.hypot(pt.x - pt.ox, pt.y - pt.oy));
            pt.y = pt.r; pt.oy = pt.y;
            if (verso < 0) pt.ox += (pt.x - pt.ox) * 0.3;
          }
          if (pt.x < pt.r + 2) {
            if (pt.ox - pt.x > 8.5 * S) danneggiaBordo("sinistra", pt.y, Math.min(1, (pt.ox - pt.x) / (VELOCITA_MAX * S)));
            pt.x = pt.r + 2; pt.ox = pt.x + (pt.x - pt.ox) * 0.4;
          }
          if (pt.x > W - pt.r - 2) {
            if (pt.x - pt.ox > 8.5 * S) danneggiaBordo("destra", pt.y, Math.min(1, (pt.x - pt.ox) / (VELOCITA_MAX * S)));
            pt.x = W - pt.r - 2; pt.ox = pt.x + (pt.x - pt.ox) * 0.4;
          }
        }
      }
      // Nel ghiaccio il corpo resta rigido: ogni punto dov'era rispetto al piede d'appoggio.
      if (f.gelato > 0 && f.ghiaccio) {
        const anc = f.p[f.ghiaccio.anc], vx = anc.x - anc.ox, vy = anc.y - anc.oy;
        for (const n in f.p) { const pt = f.p[n], o = f.ghiaccio.off[n]; pt.x = anc.x + o.x; pt.y = anc.y + o.y; pt.ox = pt.x - vx; pt.oy = pt.y - vy; }
      }
      // Lasciato cadere dalla levitazione: la botta a terra conta come un colpo del mago.
      if (f.caduta && (urto > 7 * S || !f.inVolo)) {
        const mago = f.caduta; f.caduta = null;
        if (urto > 7 * S && mago.p && !mago.esploso && !f.esploso) colpisci(mago, f, 4.5, f.p.bacino.x, f.p.bacino.y, "SBAM!");
      }
      if (f.fantasma && !f.preso && !f.tenuto && !dentroQualcosa(f)) f.fantasma = false;
      // Uno schianto dopo un lancio si sente.
      if (urto > 6 * S && !f.polv) { polvere(f.p.piedeA.x, f.base - 1, urto > 11 * S ? 6 : 3); f.polv = 14; }
      if (f.inVolo && urto > 9 * S && !f.botta) {
        scrivi(urto > 15 * S ? "SPLAT!" : "BONK!", f.p.bacino.x, f.p.bacino.y - 20 * S, false);
        f.botta = 30;
      }
    }
    if (lame()) controllaLame(a, b);
    controllaColpo(a, b); controllaColpo(b, a);
    colpoDaMano(a, b); colpoDaMano(b, a);
    aggiornaLame(); aggiornaFulmini();
    aggiornaTelefoni(); aggiornaCreature(); aggiornaNubi(); aggiornaFinale(); aggiornaProiettili(); aggiornaParticelle(); aggiornaEventi(); aggiornaDanni();
    aggiornaArti(); aggiornaMeteo(); aggiornaSisma(); aggiornaMeteore(); aggiornaBuco(); aggiornaFatale(); aggiornaMira(); aggiornaCorsa(); aggiornaAudio(); aggiornaOrda(); aggiornaOnde(); aggiornaVite();
    if (anime) controllaScontro();
    for (const sc of scie) sc.vita--;
    if (scie.length && scie[0].vita <= 0) scie = scie.filter((sc) => sc.vita > 0);
    if (anime) {
      for (const f of lottatori) {
        const altro = lottatori.find((l) => l !== f);
        if (!sfida && f.azione !== "onda" && altro && altro.onda && !altro.onda.colpito && f.ki >= 15 && !f.ko && Math.random() < 0.02) teletrasporta(f, altro);
      }
    }
    if (passi % 10 === 0) aggiornaFaccina();
    for (const s of scritte) { s.vita--; s.y -= 0.35 * S; }
    scritte = scritte.filter((s) => s.vita > 0);
  }

  // --- Lo scorrimento della pagina -------------------------------------
  // Gli elementi si spostano nella finestra: chi ci sta sopra si sposta
  // con loro, chi sta sulla striscia (che è fissa) resta dov'è.
  let ultimoScroll = window.scrollY || 0;
  window.addEventListener("scroll", () => {
    const ora = window.scrollY || 0, dy = ora - ultimoScroll;
    ultimoScroll = ora;
    if (!dy) return;
    for (const f of lottatori) {
      if (f.preso || f.esploso || !(f.supporto || f.scalata)) continue;
      for (const n in f.p) { f.p[n].y -= dy; f.p[n].oy -= dy; }
      if (f.scalata) f.scalata.y -= dy;
      f.base -= dy;
    }
    if (orda && orda.su) orda.base -= dy;
    if (!fermo) rileva();
  }, { passive: true });

  // --- Il disegno ------------------------------------------------------
  function linea(p1, p2, spessore, colore) {
    ctx.strokeStyle = colore; ctx.lineWidth = spessore; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
  }
  function arto(a, b, c, spessore, colore) {
    ctx.strokeStyle = colore; ctx.lineWidth = spessore; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(c.x, c.y); ctx.stroke();
  }
  function tondo(x, y, r, colore) {
    ctx.fillStyle = colore; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }
  function rettangoloTondo(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
  }
  function occhi(f, x, y, distanza, raggio, colore) {
    ctx.strokeStyle = colore; ctx.fillStyle = colore; ctx.lineWidth = 1.3 * S; ctx.lineCap = "round";
    for (const lato of [-1, 1]) {
      const ex = x + lato * distanza + f.dir * 1.2 * S;
      if (f.ko || f.rialzo > 30) {
        ctx.beginPath();
        ctx.moveTo(ex - raggio, y - raggio); ctx.lineTo(ex + raggio, y + raggio);
        ctx.moveTo(ex + raggio, y - raggio); ctx.lineTo(ex - raggio, y + raggio); ctx.stroke();
      } else if (f.dolore) {
        ctx.beginPath(); ctx.moveTo(ex - raggio, y); ctx.lineTo(ex + raggio, y); ctx.stroke();
      } else {
        ctx.beginPath(); ctx.arc(ex, y, raggio, 0, Math.PI * 2); ctx.fill();
      }
    }
  }

  // IL ROBOT: un personaggio originale (scatola verde con visiera), con colori
  // e costume a caso a ogni caricamento, espressioni che cambiano e
  // un'antenna che oscilla (01/10/2026).
  function sfumatura(x, y, r, chiaro, scuro) {
    const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.4, r * 0.1, x, y, r * 1.2);
    g.addColorStop(0, chiaro); g.addColorStop(1, scuro);
    return g;
  }
  function mix(c1, c2, k) {
    const n = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
    const A = n(c1), B = n(c2);
    return "rgb(" + A.map((v, i) => Math.round(v + (B[i] - v) * k)).join(",") + ")";
  }
  function stella(x, y, r, colore) {
    ctx.fillStyle = colore; ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const raggio = i % 2 ? r * 0.45 : r, ang = -Math.PI / 2 + (i * Math.PI) / 5;
      ctx.lineTo(x + Math.cos(ang) * raggio, y + Math.sin(ang) * raggio);
    }
    ctx.closePath(); ctx.fill();
  }

  // IL GUANTONE DA PUGILE, al posto della manina: il polsino bianco, il
  // corpo del guanto lungo l'avambraccio, il pollice e un riflesso.
  function guanto(gomito, mano, colore, r) {
    const ang = Math.atan2(mano.y - gomito.y, mano.x - gomito.x);
    ctx.save(); ctx.translate(mano.x, mano.y); ctx.rotate(ang);
    ctx.fillStyle = "#f4f4f4"; ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S;
    rettangoloTondo(-r * 1.9, -r * 0.7, r * 1.1, r * 1.4, r * 0.3); ctx.fill(); ctx.stroke();
    ctx.fillStyle = colore;
    ctx.beginPath(); ctx.ellipse(r * 0.15, 0, r * 1.25, r * 1.05, 0, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 1.3 * S; ctx.stroke();
    ctx.beginPath(); ctx.ellipse(r * 0.05, r * 0.85, r * 0.55, r * 0.38, -0.3, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 1 * S; ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 1 * S; ctx.lineCap = "round";
    ctx.beginPath(); ctx.arc(r * 0.2, 0, r * 0.75, -2.2, -1.2); ctx.stroke();
    ctx.restore();
  }

  // IL JETPACK: due bombole sul dorso, con gli ugelli e, quando spinge, la fiamma.
  function zaino(f, indietro) {
    const p = f.p, tx = p.bacino.x - p.collo.x, ty = p.bacino.y - p.collo.y, tl = Math.hypot(tx, ty) || 1;
    const ux = tx / tl, uy = ty / tl;
    let nx = -uy, ny = ux;
    if (nx * f.dir > 0) { nx = -nx; ny = -ny; }          // verso la schiena
    const cx = p.collo.x + tx * 0.5 + nx * indietro, cy = p.collo.y + ty * 0.5 + ny * indietro;
    const ang = Math.atan2(ty, tx) - Math.PI / 2;
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(ang);
    for (const [dx, col] of [[-2.6, "#7d8696"], [2.6, "#b3bbc9"]]) {
      ctx.fillStyle = col; ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S;
      rettangoloTondo((dx - 2.6) * S, -9 * S, 5.2 * S, 18 * S, 2.4 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#e8741a"; ctx.fillRect((dx - 2.6) * S, -3 * S, 5.2 * S, 2.2 * S);
      ctx.fillStyle = "#2b2f3a"; ctx.beginPath();
      ctx.moveTo((dx - 2.2) * S, 9 * S); ctx.lineTo((dx + 2.2) * S, 9 * S);
      ctx.lineTo((dx + 3.2) * S, 12 * S); ctx.lineTo((dx - 3.2) * S, 12 * S); ctx.closePath(); ctx.fill();
      if (f.fiamma > 0.05) {
        const lung = (6 + 14 * Math.min(1.4, f.fiamma)) * S * (0.8 + 0.4 * Math.random());
        const g = ctx.createLinearGradient(0, 12 * S, 0, 12 * S + lung);
        g.addColorStop(0, "#fff7b0"); g.addColorStop(0.45, "#ffb62e"); g.addColorStop(1, "rgba(255,90,20,0)");
        ctx.fillStyle = g; ctx.beginPath();
        ctx.moveTo((dx - 2.6) * S, 12 * S); ctx.lineTo((dx + 2.6) * S, 12 * S); ctx.lineTo(dx * S, 12 * S + lung);
        ctx.closePath(); ctx.fill();
      }
    }
    ctx.restore();
  }

  function mantello(f, p, colore) {
    const dietro = -f.dir;
    const lag = Math.max(-9 * S, Math.min(9 * S, (p.collo.ox - p.collo.x) * 7));
    const onda = Math.sin(f.passo * 1.6) * 2.2 * S;
    const A = { x: p.collo.x + dietro * 2 * S, y: p.collo.y + 1 * S };
    const B = { x: p.bacino.x + dietro * 3 * S, y: p.bacino.y - 3 * S };
    const T1 = { x: A.x + dietro * 17 * S + lag, y: A.y + 24 * S + onda };
    const T2 = { x: B.x + dietro * 11 * S + lag * 0.7, y: B.y + 16 * S - onda };
    ctx.fillStyle = colore; ctx.beginPath();
    ctx.moveTo(A.x, A.y);
    ctx.quadraticCurveTo(A.x + dietro * 15 * S + lag * 0.5, A.y + 10 * S, T1.x, T1.y);
    ctx.quadraticCurveTo((T1.x + T2.x) / 2, Math.max(T1.y, T2.y) + 3 * S, T2.x, T2.y);
    ctx.lineTo(B.x, B.y); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0,.25)"; ctx.lineWidth = 1 * S; ctx.stroke();
  }

  function costumeTesta(f, scuro) {
    // Si disegna nel sistema di riferimento della testa: l'origine è il
    // centro, il «su» è -y, la scatola va da -8.5 a 8.5 in larghezza.
    switch (costume) {
      case "ninja":
        ctx.fillStyle = "#1b1b24"; rettangoloTondo(-9 * S, -7.5 * S, 18 * S, 5.2 * S, 2 * S); ctx.fill();
        ctx.fillStyle = "#e23b2e"; ctx.fillRect(-9 * S, -4.3 * S, 18 * S, 1.3 * S);
        ctx.strokeStyle = "#1b1b24"; ctx.lineWidth = 2.2 * S; ctx.lineCap = "round";
        for (const k of [0, 1]) {
          ctx.beginPath(); ctx.moveTo(-f.dir * 8 * S, -5.5 * S);
          ctx.quadraticCurveTo(-f.dir * (13 + 3 * Math.sin(f.passo * 2 + k)) * S, (-3 + 4 * k) * S,
                               -f.dir * (18 + 2 * Math.sin(f.passo * 2.5 + k)) * S, (-1 + 7 * k) * S);
          ctx.stroke();
        }
        break;
      case "cuoco":
        ctx.fillStyle = "#fbfbfb"; ctx.strokeStyle = "#c9c9c9"; ctx.lineWidth = 1 * S;
        rettangoloTondo(-6.5 * S, -13 * S, 13 * S, 7 * S, 1.5 * S); ctx.fill(); ctx.stroke();
        for (const [cx, cy, r] of [[-5.5, -15, 4.4], [0, -17.5, 5.2], [5.5, -15, 4.4]]) {
          ctx.beginPath(); ctx.arc(cx * S, cy * S, r * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        }
        ctx.fillStyle = "#fbfbfb"; ctx.fillRect(-6 * S, -13.5 * S, 12 * S, 4 * S);
        break;
      case "mago":
        ctx.fillStyle = "#4b2f8f";
        ctx.beginPath(); ctx.moveTo(-8 * S, -7 * S); ctx.lineTo(f.dir * 2 * S, -24 * S); ctx.lineTo(8 * S, -7 * S); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.ellipse(0, -7 * S, 12 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill();
        stella(-2 * S, -13 * S, 2 * S, "#ffd84a"); stella(3 * S, -9.5 * S, 1.4 * S, "#ffd84a");
        break;
      case "pirata":
        ctx.fillStyle = "#c8332a"; rettangoloTondo(-9 * S, -8 * S, 18 * S, 4.6 * S, 2 * S); ctx.fill();
        tondo(-3 * S, -5.8 * S, 0.8 * S, "#fff"); tondo(2 * S, -6.2 * S, 0.8 * S, "#fff"); tondo(6 * S, -5.6 * S, 0.8 * S, "#fff");
        ctx.strokeStyle = "#c8332a"; ctx.lineWidth = 2.4 * S; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(-f.dir * 8 * S, -6 * S);
        ctx.quadraticCurveTo(-f.dir * 13 * S, (-3 + 2 * Math.sin(f.passo * 2)) * S, -f.dir * 16 * S, (1 + 3 * Math.sin(f.passo * 2.4)) * S); ctx.stroke();
        ctx.fillStyle = "#0a0a0a"; ctx.beginPath(); ctx.ellipse(f.dir * 2.8 * S, -0.3 * S, 3.6 * S, 3.1 * S, 0, 0, Math.PI * 2); ctx.fill();
        break;
      case "astronauta":
        ctx.fillStyle = "rgba(190,225,255,.22)"; ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1.6 * S;
        ctx.beginPath(); ctx.arc(0, -1 * S, 12.5 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 1.4 * S;
        ctx.beginPath(); ctx.arc(0, -1 * S, 9.5 * S, Math.PI * 1.15, Math.PI * 1.45); ctx.stroke();
        ctx.fillStyle = "#d9dde6"; ctx.fillRect(-6 * S, 10 * S, 12 * S, 2.4 * S);
        break;
      case "eroe":
        ctx.save(); ctx.globalAlpha = 0.45;
        ctx.fillStyle = "#14141c"; rettangoloTondo(-9.4 * S, -3.6 * S, 18.8 * S, 6.4 * S, 3 * S); ctx.fill();
        ctx.restore();
        break;
    }
  }

  function disegnaRobot(f) {
    const p = f.p, T = tavolozza || ["#2fae74", "#1c6f4a", "#7dffd2", "#154d34"];
    const verde = T[0], scuro = T[1], luce = T[2], mani = T[3];
    const colosso = formaDi(f) === "colosso";                     // trasformato: corazza, spallacci e nucleo acceso
    const sp = colosso ? 1.7 : 1;                                 // da colosso anche braccia e gambe sono travi
    const chiaro = mix(verde, "#ffffff", 0.35);
    if (f.furia > 0) {
      const g = ctx.createRadialGradient(p.bacino.x, p.bacino.y - 14 * S, 4 * S, p.bacino.x, p.bacino.y - 14 * S, 38 * S);
      g.addColorStop(0, "rgba(255,70,30,.45)"); g.addColorStop(1, "rgba(255,70,30,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.bacino.x, p.bacino.y - 14 * S, 38 * S, 0, Math.PI * 2); ctx.fill();
    }
    if (costume === "eroe") mantello(f, p, "#e8941c");
    zaino(f, 10.5 * S);
    const st = f.staccati || {}, [ginA, ginD] = ginocchia(f);
    // Arto lontano e gamba lontana.
    if (!st.gD) { arto(p.bacino, ginD, p.piedeD, 5 * S * sp, scuro); tondo(ginD.x, ginD.y, 2.8 * S * sp, mani); }
    if (!st.D) {
      arto(p.collo, p.gomitoD, p.manoD, 4.4 * S * sp, scuro);
      tondo(p.gomitoD.x, p.gomitoD.y, 2.4 * S * sp, mani);
      guanto(p.gomitoD, p.manoD, "#b92b22", 3.9 * S);
    }
    // Busto.
    const ang = Math.atan2(p.bacino.y - p.collo.y, p.bacino.x - p.collo.x) - Math.PI / 2;
    const lung = Math.hypot(p.bacino.x - p.collo.x, p.bacino.y - p.collo.y);
    ctx.save();
    ctx.translate((p.collo.x + p.bacino.x) / 2, (p.collo.y + p.bacino.y) / 2); ctx.rotate(ang);
    if (colosso) {
      // La corazza larga, sotto quella solita, e i due scarichi che fumano ai lati del collo.
      ctx.fillStyle = mix(scuro, "#000000", 0.2); ctx.strokeStyle = "#17171c"; ctx.lineWidth = 1.2 * S;
      rettangoloTondo(-12.5 * S, -lung / 2 - 2.5 * S, 25 * S, lung + 8 * S, 5 * S); ctx.fill(); ctx.stroke();
      for (const lato of [-1, 1]) {
        ctx.fillStyle = mani;
        rettangoloTondo(lato * 10.6 * S - (lato < 0 ? 4 * S : 0), -lung / 2 - 9 * S, 4 * S, 9 * S, 1.6 * S); ctx.fill(); ctx.stroke();
      }
    }
    ctx.fillStyle = sfumatura(0, 0, lung, chiaro, verde);
    rettangoloTondo(-8.5 * S, -lung / 2 - 3 * S, 17 * S, lung + 7 * S, 4 * S); ctx.fill();
    ctx.strokeStyle = scuro; ctx.lineWidth = 1.1 * S; ctx.stroke();
    ctx.fillStyle = scuro; rettangoloTondo(-5.2 * S, -lung / 2 + 2.5 * S, 10.4 * S, 7 * S, 1.8 * S); ctx.fill();
    const lampeggia = Math.floor(f.passo * 1.2) % 3;
    for (let i = 0; i < 3; i++) {
      tondo((-3 + 3 * i) * S, -lung / 2 + 6 * S, 1.2 * S,
            f.ko ? "#555" : (i === lampeggia ? "#fff6a8" : ["#ffcf3a", "#ff6b4a", luce][i]));
    }
    ctx.fillStyle = scuro; ctx.fillRect(-8.5 * S, lung / 2 - 4.5 * S, 17 * S, 2 * S);
    tondo(0, lung / 2 - 3.5 * S, 1.6 * S, "#ffcf3a");
    if (colosso) {
      // La trave delle spalle, sopra tutto: larga, coi bulloni e due luci agli angoli.
      ctx.fillStyle = scuro; ctx.strokeStyle = "#17171c"; ctx.lineWidth = 1.3 * S;
      rettangoloTondo(-16 * S, -lung / 2 - 1.5 * S, 32 * S, 8.5 * S, 3 * S); ctx.fill(); ctx.stroke();
      for (const lato of [-1, 1]) {
        tondo(lato * 12.4 * S, -lung / 2 + 2.8 * S, 1.8 * S, mani);
        tondo(lato * 7 * S, -lung / 2 + 2.8 * S, 1.3 * S, mix(scuro, "#000000", 0.3));
        ctx.fillStyle = f.ko ? "#555" : luce;
        ctx.beginPath(); ctx.ellipse(lato * 15 * S, -lung / 2 + 2.8 * S, 1.4 * S, 2.2 * S, 0, 0, Math.PI * 2); ctx.fill();
      }
    }
    if (colosso) {
      // Il nucleo nel petto: pulsa e illumina la corazza.
      const pul = 0.76 + 0.24 * Math.sin(passi * 0.16), y0 = -lung * 0.1;
      ctx.save();
      const g = ctx.createRadialGradient(0, y0, 1 * S, 0, y0, 13 * S);
      g.addColorStop(0, "rgba(255,230,140,.95)"); g.addColorStop(0.45, "rgba(255,190,60,.5)"); g.addColorStop(1, "rgba(255,170,40,0)");
      ctx.globalAlpha = pul; ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(0, y0, 13 * S, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
      tondo(0, y0, 4.4 * S * pul, "#fff3c4");
      ctx.strokeStyle = "#ffcf3a"; ctx.lineWidth = 1.6 * S;
      ctx.beginPath(); ctx.arc(0, y0, 6.4 * S, 0, Math.PI * 2); ctx.stroke();
    }
    if (costume === "eroe") stella(0, -lung / 2 + 14 * S, 2.6 * S, "#ffe27a");
    disegnaSegni(f, "busto");
    ctx.restore();
    // Gamba e braccio vicini.
    if (!st.gA) { arto(p.bacino, ginA, p.piedeA, 5 * S * sp, verde); tondo(ginA.x, ginA.y, 2.8 * S * sp, scuro); }
    for (const piede of [p.piedeD, p.piedeA]) {
      if ((piede === p.piedeD && st.gD) || (piede === p.piedeA && st.gA)) continue;
      if (colosso) {
        ctx.fillStyle = scuro; ctx.strokeStyle = "#17171c"; ctx.lineWidth = 1.2 * S;
        rettangoloTondo(piede.x - 6.6 * S, piede.y - 4.2 * S, 13.2 * S, 7 * S, 2.2 * S); ctx.fill(); ctx.stroke();
      }
      ctx.fillStyle = mani; rettangoloTondo(piede.x - 4.2 * S, piede.y - 2.6 * S, 8.4 * S, 4.8 * S, 1.8 * S); ctx.fill();
      ctx.fillStyle = scuro; ctx.fillRect(piede.x - 4 * S + (f.dir > 0 ? 0 : 6.2 * S), piede.y + 1.1 * S, 1.8 * S, 1.2 * S);
    }
    // Testa, con antenna a molla.
    const angT = Math.atan2(p.testa.y - p.collo.y, p.testa.x - p.collo.x) + Math.PI / 2;
    ctx.save(); ctx.translate(p.testa.x, p.testa.y); ctx.rotate(angT);
    const hatAlto = costume === "cuoco" || costume === "mago" || natale;
    if (!hatAlto && costume !== "astronauta" && !(f.staccati && f.staccati.P)) {
      const oscilla = Math.max(-5 * S, Math.min(5 * S, (p.testa.ox - p.testa.x) * 1.4)) + Math.sin(f.passo * 1.7) * 0.8 * S;
      ctx.strokeStyle = scuro; ctx.lineWidth = 1.4 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(0, -7 * S); ctx.quadraticCurveTo(oscilla * 0.4, -10 * S, oscilla, -13 * S); ctx.stroke();
      tondo(oscilla, -13.6 * S, 2.1 * S, (Math.floor(f.passo * 2) % 2 && !f.ko) ? "#ff4d3a" : "#ffcf3a");
    }
    ctx.fillStyle = sfumatura(0, -2 * S, 10 * S, chiaro, verde); rettangoloTondo(-8.5 * S, -7.5 * S, 17 * S, 15 * S, 4 * S); ctx.fill();
    ctx.strokeStyle = scuro; ctx.lineWidth = 1.1 * S; ctx.stroke();
    ctx.fillStyle = "#0f2a1f"; rettangoloTondo(-6.8 * S, -3.8 * S, 13.6 * S, 7 * S, 2.6 * S); ctx.fill();
    // Occhi: cambiano con quello che succede.
    const attacca = f.azione === "pugno" || f.azione === "diretto" || f.azione === "montante" ||
                    f.azione === "calcio" || f.azione === "lancia" || f.azione === "spara" ||
                    !!TAGLI[f.azione] || f.azione === "scattoLama" || f.azione === "pressa" || f.azione === "presa";
    const festa = f.azione === "esulta" || f.azione === "provoca" || f.azione === "balla";
    const ey = -0.3 * S, ex = f.dir * 0.8 * S;
    ctx.lineCap = "round";
    if (f.ko || f.rialzo > 30) {
      occhi(f, 0, ey, 2.8 * S, 1.4 * S, luce);
    } else if (f.dolore || f.stordito) {
      ctx.strokeStyle = luce; ctx.lineWidth = 1.4 * S; ctx.beginPath();
      ctx.moveTo(-4.2 * S, ey - 1.4 * S); ctx.lineTo(-1.6 * S, ey + 1.4 * S);
      ctx.moveTo(-1.6 * S, ey - 1.4 * S); ctx.lineTo(-4.2 * S, ey + 1.4 * S);
      ctx.stroke(); tondo(2.8 * S, ey, 1.9 * S, luce);
    } else if (festa) {
      ctx.strokeStyle = luce; ctx.lineWidth = 1.5 * S;
      for (const lato of [-1, 1]) { ctx.beginPath(); ctx.arc(lato * 2.9 * S + ex, ey + 1 * S, 1.7 * S, Math.PI * 1.05, Math.PI * 1.95); ctx.stroke(); }
    } else if (f.furia > 0 || attacca) {
      const col = f.furia > 0 ? "#ff6a4a" : luce;
      ctx.strokeStyle = col; ctx.lineWidth = 1.5 * S;
      for (const lato of [-1, 1]) {
        const x0 = lato * 2.9 * S + ex;
        tondo(x0, ey + 0.4 * S, 1.3 * S, col);
        ctx.beginPath(); ctx.moveTo(x0 - 2 * S, ey - (lato === f.dir ? 3 : 1.8) * S); ctx.lineTo(x0 + 2 * S, ey - (lato === f.dir ? 1.8 : 3) * S); ctx.stroke();
      }
    } else {
      const batte = Math.floor(passi / 3) % 90 === 0 ? 0.35 : 1;
      ctx.fillStyle = luce;
      for (const lato of [-1, 1]) { ctx.beginPath(); ctx.ellipse(lato * 2.9 * S + ex, ey, 1.4 * S, 1.4 * S * batte, 0, 0, Math.PI * 2); ctx.fill(); }
    }
    disegnaSegni(f, "testa");
    if (colosso) {
      // La mascella corazzata e i due paraorecchie: la testa da gigante.
      ctx.fillStyle = scuro; ctx.strokeStyle = "#17171c"; ctx.lineWidth = 1.2 * S;
      rettangoloTondo(-6.4 * S, 3.4 * S, 12.8 * S, 4.6 * S, 1.6 * S); ctx.fill(); ctx.stroke();
      for (const lato of [-1, 1]) {
        rettangoloTondo(lato * 6.2 * S - (lato < 0 ? 3.4 * S : 0), -3.6 * S, 3.4 * S, 7.6 * S, 1.4 * S); ctx.fill(); ctx.stroke();
      }
    }
    if (natale) cappellino(0, -7 * S, 9 * S, f.dir); else costumeTesta(f, scuro);
    const tg = temaGravita();
    if ((tg === "luna" || tg === "spazio") && costume !== "astronauta") { ctx.save(); ctx.translate(0, -1 * S); casco(12.5 * S); ctx.restore(); }
    ctx.restore();
    if (!st.A) {
      arto(p.collo, p.gomitoA, p.manoA, 4.4 * S * sp, verde);
      tondo(p.gomitoA.x, p.gomitoA.y, 2.4 * S * sp, scuro);
      guanto(p.gomitoA, p.manoA, "#e03a2f", 4.2 * S);
      if (f.palla) tondo(p.manoA.x, p.manoA.y - 3 * S, 3 * S, "#ffffff");
    }
    if (colosso) {
      // Gli spallacci, sopra le braccia: è questa la sagoma che fa il gigante.
      const c = p.collo, ang2 = Math.atan2(p.bacino.y - c.y, p.bacino.x - c.x) - Math.PI / 2;
      ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(ang2);
      ctx.strokeStyle = "#17171c"; ctx.lineWidth = 1.3 * S; ctx.lineJoin = "round";
      for (const lato of [-1, 1]) {
        ctx.fillStyle = lato === f.dir ? scuro : mix(scuro, "#000000", 0.28);
        rettangoloTondo(lato * 6.5 * S - (lato < 0 ? 10 * S : 0), -4.5 * S, 10 * S, 12 * S, 3.4 * S); ctx.fill(); ctx.stroke();
        ctx.fillStyle = f.ko ? "#555" : luce;
        ctx.fillRect(lato * 9 * S - (lato < 0 ? 5.6 * S : 0), -0.6 * S, 5.6 * S, 2 * S);
      }
      ctx.restore();
    }
  }

  // LA MELA: polpa bianca dentro, contorni neri, occhi neri
  // (01/10/2026, su richiesta). Un frutto intero col picciolo e la foglia.
  // La bocca della mela cambia con quello che succede: serena a riposo,
  // aperta quando colpisce, storta quando prende un colpo, lingua fuori da K.O.
  function bocca(f, R) {
    const x = f.dir * 0.1 * R, y = 0.4 * R, w = 0.3 * R;
    ctx.strokeStyle = "#111"; ctx.fillStyle = "#111"; ctx.lineWidth = 1.5 * S; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath();
    if (f.ko || f.rialzo > 30) {
      ctx.moveTo(x - w * 0.8, y); ctx.lineTo(x + w * 0.8, y); ctx.stroke();
      ctx.fillStyle = "#ff7a8a"; ctx.beginPath();
      ctx.ellipse(x + f.dir * w * 0.3, y + 0.14 * R, 0.12 * R, 0.16 * R, 0, 0, Math.PI * 2); ctx.fill();
      ctx.lineWidth = 1 * S; ctx.stroke();
    } else if (f.dolore || f.stordito) {
      const n = 6;
      for (let i = 0; i <= n; i++) {
        const px = x - w + (2 * w * i) / n, py = y + (i % 2 ? -0.06 : 0.06) * R;
        if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
      }
      ctx.stroke();
    } else if (["pugno", "diretto", "montante", "calcio", "lancia", "spara", "fendente", "affondo", "rovescio", "scattoLama", "pressa", "trasforma", "presa", "estrai"].indexOf(f.azione) >= 0) {
      ctx.ellipse(x, y + 0.04 * R, 0.2 * R, 0.17 * R, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#ff7a8a"; ctx.beginPath();
      ctx.ellipse(x, y + 0.1 * R, 0.12 * R, 0.07 * R, 0, 0, Math.PI * 2); ctx.fill();
    } else if (f.azione === "esulta" || f.azione === "balla") {
      ctx.moveTo(x - w, y - 0.04 * R); ctx.quadraticCurveTo(x, y + 0.5 * R, x + w, y - 0.04 * R); ctx.closePath();
      ctx.fillStyle = "#111"; ctx.fill();
      ctx.fillStyle = "#fff"; ctx.fillRect(x - w * 0.6, y - 0.03 * R, w * 1.2, 0.07 * R);
    } else if (f.azione === "provoca") {
      ctx.moveTo(x - w, y); ctx.quadraticCurveTo(x, y + 0.14 * R, x + w, y - 0.1 * R); ctx.stroke();
      ctx.fillStyle = "#ff7a8a"; ctx.beginPath();
      ctx.ellipse(x + f.dir * w * 0.5, y + 0.12 * R, 0.1 * R, 0.14 * R, 0, 0, Math.PI * 2); ctx.fill();
      ctx.lineWidth = 1 * S; ctx.stroke();
    } else if (f.azione === "salto" || f.azione === "indietro") {
      ctx.ellipse(x, y + 0.03 * R, 0.1 * R, 0.1 * R, 0, 0, Math.PI * 2); ctx.stroke();
    } else {
      const sorriso = 0.12 + 0.04 * Math.sin(f.passo * 0.2);
      ctx.moveTo(x - w * 0.8, y); ctx.quadraticCurveTo(x, y + sorriso * R * 2, x + w * 0.8, y); ctx.stroke();
    }
  }

  // Il frutto occupa tutto lo spazio fra il bacino e la testa: la mela è
  // alta quanto il robot e i colpi arrivano dove la si vede (01/10/2026:
  // prima era più bassa e i pugni sopra di lei colpivano l'aria).
  function corpoMela(p) {
    const A = p.testa, B = p.bacino;
    const L = Math.hypot(B.x - A.x, B.y - A.y) || 1;
    return { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2, ang: Math.atan2(B.y - A.y, B.x - A.x) - Math.PI / 2,
             R: Math.max(12 * S, Math.min(21 * S, L * 0.53)) };
  }
  function sagomaMela(R) {
    ctx.beginPath();
    ctx.moveTo(0, -0.72 * R);
    ctx.bezierCurveTo(0.55 * R, -1.08 * R, 1.12 * R, -0.62 * R, 1.02 * R, 0.08 * R);
    ctx.bezierCurveTo(0.96 * R, 0.66 * R, 0.55 * R, 1.06 * R, 0.22 * R, 0.96 * R);
    ctx.bezierCurveTo(0.08 * R, 0.92 * R, -0.08 * R, 0.92 * R, -0.22 * R, 0.96 * R);
    ctx.bezierCurveTo(-0.55 * R, 1.06 * R, -0.96 * R, 0.66 * R, -1.02 * R, 0.08 * R);
    ctx.bezierCurveTo(-1.12 * R, -0.62 * R, -0.55 * R, -1.08 * R, 0, -0.72 * R);
    ctx.closePath();
  }

  // La mela trasformata: un albero. Tronco al posto del corpo, chioma intorno
  // al frutto (che resta la faccia), rami al posto delle braccia, radici ai piedi.
  function disegnaAlbero(f, p, c, R) {
    const legno = "#6b4423", venatura = "#4a2f18";
    const b = p.bacino, dx = c.x - b.x, dy = c.y - b.y, L = Math.hypot(dx, dy) || 1;
    const ux = dx / L, uy = dy / L, nx = -uy, ny = ux;
    const su = (k, lato) => ({ x: b.x + ux * L * k + nx * lato * S, y: b.y + uy * L * k + ny * lato * S });
    ctx.fillStyle = legno; ctx.strokeStyle = "#111"; ctx.lineWidth = 1.5 * S; ctx.lineJoin = "round";
    ctx.beginPath();
    let q = su(-0.12, 11); ctx.moveTo(q.x, q.y);
    q = su(0.5, 7.5); const r2 = su(1.05, 5.5); ctx.quadraticCurveTo(q.x, q.y, r2.x, r2.y);
    q = su(1.05, -5.5); ctx.lineTo(q.x, q.y);
    q = su(0.5, -7.5); const r3 = su(-0.12, -11); ctx.quadraticCurveTo(q.x, q.y, r3.x, r3.y);
    ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = venatura; ctx.lineWidth = 1.3 * S; ctx.lineCap = "round"; ctx.beginPath();
    for (const k of [-4, 0, 4]) {
      const a = su(0.08, k), z = su(0.92, k * 0.55);
      ctx.moveTo(a.x, a.y); ctx.lineTo(z.x, z.y);
    }
    ctx.stroke();
    // La chioma: ciuffi tondi dietro al frutto, che ondeggiano piano.
    const on = Math.sin(passi * 0.045) * 2.2 * S;
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 + 0.3, rr = R * (1.22 + 0.2 * Math.sin(i * 2.3));
      tondo(c.x + Math.cos(a) * rr + on * Math.cos(i * 1.3), c.y + Math.sin(a) * rr * 0.94 - R * 0.22 + on * 0.4,
            R * (0.46 + 0.11 * Math.sin(i * 1.7)), i % 2 ? "#2d7a2b" : "#3f9a3a");
    }
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2 + 1.1, rr = R * 1.05;
      tondo(c.x + Math.cos(a) * rr, c.y + Math.sin(a) * rr * 0.94 - R * 0.3, R * 0.3, i % 2 ? "#4fb04a" : "#2d7a2b");
    }
  }
  function disegnaMela(f) {
    const p = f.p, nero = "#111";
    const albero = formaDi(f) === "albero", legno = "#6b4423", ramo = "#4a2f18";
    // Gambe senza incroci: il ginocchio si piega sempre verso la faccia,
    // qualunque cosa faccia la fisica (prima le gambe si intrecciavano).
    const st = f.staccati || {};
    for (const piede of [p.piedeD, p.piedeA]) {
      if ((piede === p.piedeD && st.gD) || (piede === p.piedeA && st.gA)) continue;
      const dx = piede.x - p.bacino.x, dy = piede.y - p.bacino.y, lun = Math.hypot(dx, dy) || 1;
      let nx = -dy / lun, ny = dx / lun;
      if (nx * f.dir < 0) { nx = -nx; ny = -ny; }
      const ginocchio = { x: p.bacino.x + dx / 2 + nx * 0.14 * lun, y: p.bacino.y + dy / 2 + ny * 0.14 * lun };
      arto(p.bacino, ginocchio, piede, albero ? 7.4 * S : 3.2 * S, albero ? legno : nero);
      if (albero) {
        // Le radici, al posto delle scarpe.
        ctx.strokeStyle = legno; ctx.lineWidth = 3.2 * S; ctx.lineCap = "round"; ctx.beginPath();
        for (const k of [-1, 0, 1]) { ctx.moveTo(piede.x, piede.y - 1 * S); ctx.lineTo(piede.x + k * 6 * S + f.dir * 1.5 * S, piede.y + 2.4 * S); }
        ctx.stroke();
      } else {
        ctx.fillStyle = "#f7f7f7"; ctx.beginPath();
        ctx.ellipse(piede.x + f.dir * 1.5 * S, piede.y - 0.5 * S, 4.2 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = nero; ctx.lineWidth = 1.2 * S; ctx.stroke();
      }
    }
    const c = corpoMela(p), R = c.R;
    if (albero) disegnaAlbero(f, p, c, R);
    zaino(f, R + 2 * S);
    // Le braccia partono dai FIANCHI del frutto, non dal centro: così non
    // attraversano la faccia.
    let qx = Math.cos(c.ang), qy = Math.sin(c.ang);
    if (qx * f.dir < 0) { qx = -qx; qy = -qy; }
    const giu = { x: -Math.sin(c.ang), y: Math.cos(c.ang) };
    const spalla = { x: c.x + giu.x * 0.15 * R, y: c.y + giu.y * 0.15 * R };
    const spallaA = { x: spalla.x + qx * 0.86 * R, y: spalla.y + qy * 0.86 * R };
    const spallaD = { x: spalla.x - qx * 0.86 * R, y: spalla.y - qy * 0.86 * R };
    if (!st.D) {
      arto(spallaD, p.gomitoD, p.manoD, albero ? 6.2 * S : 3 * S, albero ? ramo : nero);
      if (albero) tondo(p.manoD.x, p.manoD.y, R * 0.34, "#2d7a2b");
    }
    ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.ang);
    const frutto = () => {
      // I morsi: buchi nella sagoma (ritagliati via) col bordo di polpa.
      const morsi = f.morsi || [];
      if (morsi.length) {
        ctx.save(); ctx.beginPath(); ctx.rect(-3 * R, -3 * R, 6 * R, 6 * R);
        for (const m of morsi) { const r = m.r * R * m.k; ctx.moveTo(m.x * R + r, m.y * R); ctx.arc(m.x * R, m.y * R, r, 0, Math.PI * 2); }
        ctx.clip("evenodd");
      }
      // Polpa bianca con una sfumatura crema verso il bordo, poi la buccia.
      const polpa = ctx.createRadialGradient(-R * 0.2, -R * 0.2, R * 0.1, 0, 0, R * 1.05);
      polpa.addColorStop(0, "#ffffff"); polpa.addColorStop(1, "#f6efe1");
      sagomaMela(R); ctx.fillStyle = polpa; ctx.fill();
      ctx.lineWidth = 2.6 * S; ctx.strokeStyle = "#111"; ctx.lineJoin = "round"; ctx.stroke();
      if (!st.P) {
        linea({ x: 0, y: -0.7 * R }, { x: 0.12 * R, y: -1.18 * R }, 1.8 * S, "#6b4423");
        ctx.fillStyle = "#3f9a3a"; ctx.beginPath();
        ctx.ellipse(0.42 * R, -1.08 * R, 0.34 * R, 0.14 * R, -0.45, 0, Math.PI * 2); ctx.fill();
      }
      // Occhi neri, con un puntino di luce: guardano verso l'avversario.
      const exs = [-0.34 * R + f.dir * 0.08 * R, 0.34 * R + f.dir * 0.08 * R];
      if (f.ko || f.rialzo > 30 || f.dolore) {
        occhi(f, f.dir * 0.08 * R - f.dir * 1.2 * S, -0.16 * R, 0.34 * R, 0.13 * R, "#111");
      } else {
        for (const ex of exs) {
          ctx.fillStyle = "#111"; ctx.beginPath();
          ctx.ellipse(ex, -0.16 * R, 0.15 * R, 0.21 * R, 0, 0, Math.PI * 2); ctx.fill();
          tondo(ex + f.dir * 0.05 * R, -0.24 * R, 0.05 * R, "#ffffff");
        }
        ctx.strokeStyle = "#111"; ctx.lineWidth = 1.4 * S; ctx.lineCap = "round"; ctx.beginPath();
        for (let i = 0; i < 2; i++) {
          const lato = i === 0 ? -1 : 1, x0 = exs[i];
          ctx.moveTo(x0 - 0.2 * R, -0.48 * R + (lato === f.dir ? 0.08 : -0.02) * R);
          ctx.lineTo(x0 + 0.2 * R, -0.48 * R + (lato === f.dir ? -0.02 : 0.08) * R);
        }
        ctx.stroke();
      }
      bocca(f, R);
      disegnaSegni(f, "frutto");
      if (natale) cappellino(0.04 * R, -0.74 * R, 0.6 * R, f.dir);
      if (morsi.length) {
        ctx.restore();
        // Il bordo del morso: polpa color crema e la dentatura.
        ctx.save(); sagomaMela(R); ctx.clip();
        for (const m of morsi) {
          const r = m.r * R * m.k;
          ctx.strokeStyle = "#f1dfb6"; ctx.lineWidth = 3.2 * S; ctx.beginPath(); ctx.arc(m.x * R, m.y * R, r + 1.6 * S, 0, Math.PI * 2); ctx.stroke();
          ctx.strokeStyle = "#111"; ctx.lineWidth = 1.5 * S; ctx.beginPath();
          for (let i = 0; i <= 24; i++) {
            const a = (i / 24) * Math.PI * 2, rr = r + (i % 2 ? 0.9 : 0) * S;
            if (i) ctx.lineTo(m.x * R + Math.cos(a) * rr, m.y * R + Math.sin(a) * rr); else ctx.moveTo(m.x * R + rr, m.y * R);
          }
          ctx.stroke();
        }
        ctx.restore();
      }
    };
    const tg = temaGravita();
    if (f.taglio) {
      // Tagliata in due dalla spada: le metà si aprono, poi si richiudono.
      const tg2 = f.taglio, a = tg2.ang, nx = -Math.sin(a), ny = Math.cos(a);
      const apri = tg2.t < TAGLIO_CHIUDE ? Math.min(1, tg2.t / 10) : Math.max(0, 1 - (tg2.t - TAGLIO_CHIUDE) / 22);
      const d = 8 * S * apri;
      for (const lato of [1, -1]) {
        ctx.save();
        ctx.translate(nx * lato * d, ny * lato * d + (lato > 0 ? 2 * S * apri : 0)); ctx.rotate(lato * 0.18 * apri);
        ctx.beginPath();
        const ux = Math.cos(a) * 3 * R, uy = Math.sin(a) * 3 * R;
        ctx.moveTo(-ux, -uy); ctx.lineTo(ux, uy); ctx.lineTo(ux + nx * lato * 3 * R, uy + ny * lato * 3 * R); ctx.lineTo(-ux + nx * lato * 3 * R, -uy + ny * lato * 3 * R);
        ctx.closePath(); ctx.clip();
        frutto();
        // La faccia del taglio: polpa crema col torsolo e i semi.
        ctx.save(); sagomaMela(R); ctx.clip();
        ctx.strokeStyle = "#f1dfb6"; ctx.lineWidth = 4 * S; ctx.beginPath(); ctx.moveTo(-ux, -uy); ctx.lineTo(ux, uy); ctx.stroke();
        ctx.strokeStyle = "#111"; ctx.lineWidth = 1.4 * S; ctx.stroke();
        ctx.fillStyle = "#4a2e1a";
        for (const k of [-0.15, 0.15]) { ctx.beginPath(); ctx.ellipse(Math.cos(a) * k * R + nx * lato * 2 * S, Math.sin(a) * k * R + ny * lato * 2 * S, 1.6 * S, 1 * S, a, 0, Math.PI * 2); ctx.fill(); }
        ctx.restore();
        ctx.restore();
      }
    } else frutto();
    if (tg === "luna" || tg === "spazio") casco(1.3 * R);
    ctx.restore();
    // Tutt'e due le braccia stanno DAVANTI al corpo: prima quella lontana
    // finiva dietro la polpa e la mela sembrava avere una mano sola.
    for (const [gomito, mano, r, colore] of [[p.gomitoD, p.manoD, 3.9, "#1f56b8"], [p.gomitoA, p.manoA, 4.2, "#2f72e0"]]) {
      if ((mano === p.manoD && st.D) || (mano === p.manoA && st.A)) continue;
      if (mano !== p.manoD) arto(spallaA, gomito, mano, albero ? 6.2 * S : 3 * S, albero ? ramo : nero);
      if (albero) tondo(mano.x, mano.y, R * 0.34, "#3f9a3a");
      guanto(gomito, mano, colore, r * S);
    }
    if (f.palla && !st.A) tondo(p.manoA.x, p.manoA.y - 3 * S, 3 * S, "#ffffff");
  }

  // Una rottura dello schermo: una ragnatela che parte dal punto d'urto, con
  // raggi spezzati e qualche anello. Tutto in coordinate locali del telefono
  // e, al disegno, ritagliato dentro lo schermo: non esce mai dal telefono.
  function rompiSchermo(t) {
    if (!t.sch) return;
    const [sx, sy, w, h] = t.sch;
    const cx = sx + w / 2 + caso(-0.3, 0.3) * w, cy = sy + h / 2 + caso(-0.3, 0.3) * h;
    const raggi = [], n = 4 + Math.floor(Math.random() * 2);
    const base = caso(0, Math.PI * 2);
    for (let i = 0; i < n; i++) {
      const a = base + (i / n) * Math.PI * 2 + caso(-0.25, 0.25);
      const lung = caso(0.35, 0.8) * Math.max(w, h);
      const pts = [[cx, cy]];
      let x = cx, y = cy, aa = a;
      for (let k = 1; k <= 3; k++) {
        aa += caso(-0.3, 0.3);
        x += Math.cos(aa) * lung / 3; y += Math.sin(aa) * lung / 3;
        pts.push([x, y]);
      }
      raggi.push(pts);
    }
    t.rotture.push({ cx, cy, raggi, anelli: [caso(0.07, 0.12) * w, caso(0.17, 0.25) * w] });
    if (t.rotture.length > 2) t.rotture.shift();
  }

  // Le armi, da cartone: origine sull'impugnatura, +x verso la punta.
  function disegnaArma(t) {
    if (Math.cos(t.a) < 0) ctx.scale(1, -1);          // l'impugnatura resta in basso
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S; ctx.lineJoin = "round";
    if (t.tipo === "pistola") {
      ctx.fillStyle = "#5a4030"; ctx.beginPath();
      ctx.moveTo(-2.6 * S, -1.4 * S); ctx.lineTo(1.6 * S, -1.4 * S); ctx.lineTo(0.6 * S, 4.2 * S); ctx.lineTo(-3.6 * S, 4.2 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#2b2f3a"; rettangoloTondo(-3.4 * S, -5.6 * S, 14.6 * S, 4.6 * S, 1.3 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#ff8a1a"; ctx.fillRect(10 * S, -5.6 * S, 2.2 * S, 4.6 * S); ctx.strokeRect(10 * S, -5.6 * S, 2.2 * S, 4.6 * S);
      ctx.strokeStyle = "rgba(255,255,255,.35)"; ctx.beginPath(); ctx.moveTo(-1.5 * S, -4.4 * S); ctx.lineTo(8 * S, -4.4 * S); ctx.stroke();
      ctx.strokeStyle = "#111"; ctx.beginPath(); ctx.arc(2.2 * S, 0.2 * S, 1.6 * S, 0, Math.PI); ctx.stroke();
    } else if (t.tipo === "bazooka") {
      // Un tubo lungo con la bocca svasata, il mirino e l'impugnatura.
      ctx.fillStyle = "#3f4a3a"; rettangoloTondo(-13 * S, -4 * S, 28 * S, 8 * S, 2.4 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#2f382c"; ctx.beginPath();
      ctx.moveTo(15 * S, -4 * S); ctx.lineTo(19 * S, -6.4 * S); ctx.lineTo(19 * S, 6.4 * S); ctx.lineTo(15 * S, 4 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#2f382c"; rettangoloTondo(-16 * S, -3 * S, 4 * S, 6 * S, 1.4 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#5a4030"; ctx.beginPath();
      ctx.moveTo(-5 * S, 3.6 * S); ctx.lineTo(-1 * S, 3.6 * S); ctx.lineTo(-2 * S, 9 * S); ctx.lineTo(-6 * S, 9 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#8d96a6"; rettangoloTondo(2 * S, -7.4 * S, 7 * S, 3.4 * S, 1.2 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#d14b2a"; ctx.fillRect(-9 * S, -2.2 * S, 3 * S, 4.4 * S);
    } else if (t.tipo === "lanciafiamme") {
      // Il serbatoio dietro, il tubo e la fiammella sempre accesa alla bocca.
      ctx.fillStyle = "#b24a2a"; rettangoloTondo(-13 * S, -5.4 * S, 10 * S, 10.8 * S, 3 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#2b2f3a"; rettangoloTondo(-4 * S, -2.6 * S, 16 * S, 5.2 * S, 1.8 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#8d96a6"; ctx.beginPath();
      ctx.moveTo(11 * S, -3.6 * S); ctx.lineTo(15 * S, -4.6 * S); ctx.lineTo(15 * S, 4.6 * S); ctx.lineTo(11 * S, 3.6 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#5a4030"; ctx.beginPath();
      ctx.moveTo(-1 * S, 2.4 * S); ctx.lineTo(3 * S, 2.4 * S); ctx.lineTo(2 * S, 8 * S); ctx.lineTo(-2 * S, 8 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      const sp = 0.7 + 0.3 * Math.sin(passi * 0.5);
      tondo(16.4 * S, 0, 1.9 * S * sp, "#ffb62e"); tondo(16.4 * S, 0, 0.9 * S * sp, "#fff1a0");
    } else {
      const g = ctx.createLinearGradient(0, -1.6 * S, 0, 1.6 * S);
      g.addColorStop(0, "#f4f7fb"); g.addColorStop(1, "#9aa6b6");
      ctx.fillStyle = g; ctx.beginPath();
      ctx.moveTo(4 * S, -1.5 * S); ctx.lineTo(27 * S, -1.5 * S); ctx.lineTo(31 * S, 0); ctx.lineTo(27 * S, 1.5 * S); ctx.lineTo(4 * S, 1.5 * S);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 0.6 * S;
      ctx.beginPath(); ctx.moveTo(6 * S, -0.3 * S); ctx.lineTo(25 * S, -0.3 * S); ctx.stroke();
      ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S;
      ctx.fillStyle = "#d9a520"; rettangoloTondo(2.2 * S, -4.6 * S, 2.2 * S, 9.2 * S, 0.8 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#6b4423"; ctx.fillRect(-5 * S, -1.3 * S, 7.2 * S, 2.6 * S); ctx.strokeRect(-5 * S, -1.3 * S, 7.2 * S, 2.6 * S);
      tondo(-5.8 * S, 0, 1.9 * S, "#d9a520"); ctx.beginPath(); ctx.arc(-5.8 * S, 0, 1.9 * S, 0, Math.PI * 2); ctx.stroke();
    }
  }

  function disegnaTelefono(t) {
    ctx.save(); ctx.translate(t.x, t.y); ctx.rotate(t.a);
    if (eArma(t)) { disegnaArma(t); ctx.restore(); return; }
    if (t.tipo === "fumogeno") {
      // Una bomboletta col tappo e l'anello: grigia, con la fascia viola.
      const w = t.w, h = t.h;
      ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S; ctx.lineJoin = "round";
      ctx.fillStyle = "#8f95a3"; rettangoloTondo(-w / 2, -h / 2 + 2 * S, w, h - 2 * S, 1.8 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#9a6be0"; ctx.fillRect(-w / 2 + 0.6 * S, -1.5 * S, w - 1.2 * S, 3.4 * S);
      ctx.fillStyle = "#3a3f4a"; ctx.fillRect(-2 * S, -h / 2, 4 * S, 2.4 * S); ctx.strokeRect(-2 * S, -h / 2, 4 * S, 2.4 * S);
      ctx.beginPath(); ctx.arc(3.6 * S, -h / 2 + 0.6 * S, 1.8 * S, 0, Math.PI * 2); ctx.stroke();
      ctx.restore(); return;
    }
    if (t.tipo === "barattolo") {
      // Un barattolo di vetro col tappo di sughero: dentro brilla la creatura.
      const w = t.w, h = t.h, E = ELEMENTI[t.el] || ELEMENTI.fuoco, batte = 0.55 + 0.25 * Math.sin(passi * 0.2 + t.x);
      ctx.lineJoin = "round";
      ctx.fillStyle = "rgba(210,236,255,.55)"; ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S;
      rettangoloTondo(-w / 2, -h / 2 + 3 * S, w, h - 3 * S, 2.6 * S); ctx.fill();
      ctx.globalAlpha = batte; tondo(0, 2 * S, 3.4 * S, E.colore); ctx.globalAlpha = 1; tondo(0, 2 * S, 1.6 * S, "#ffffff");
      ctx.strokeStyle = "#111"; rettangoloTondo(-w / 2, -h / 2 + 3 * S, w, h - 3 * S, 2.6 * S); ctx.stroke();
      ctx.fillStyle = "#b98a54"; ctx.fillRect(-w / 2 + 1.6 * S, -h / 2, w - 3.2 * S, 3.4 * S); ctx.strokeRect(-w / 2 + 1.6 * S, -h / 2, w - 3.2 * S, 3.4 * S);
      ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.moveTo(-w / 2 + 2 * S, -h / 2 + 6 * S); ctx.lineTo(-w / 2 + 2 * S, h / 2 - 3 * S); ctx.stroke();
      ctx.restore(); return;
    }
    if (t.tipo === "sasso") {
      // Un pezzo di meteorite: scuro, bitorzoluto, con le crepe ancora accese.
      const r = 5.6 * S, caldo = t.caldo || 0;
      if (caldo > 0.05) { ctx.globalAlpha = 0.4 * caldo; tondo(0, 0, r * 2, "#ff8a1a"); ctx.globalAlpha = 1; }
      ctx.fillStyle = "#3a2c26"; ctx.strokeStyle = "#17120f"; ctx.lineWidth = 1 * S; ctx.lineJoin = "round"; ctx.beginPath();
      [1, 0.82, 1.08, 0.9, 1.1, 0.8, 1.02, 0.88].forEach((q, i) => { const a = (i / 8) * Math.PI * 2; ctx[i ? "lineTo" : "moveTo"](Math.cos(a) * r * q, Math.sin(a) * r * q * 0.85); });
      ctx.closePath(); ctx.fill(); ctx.stroke();
      tondo(-r * 0.3, -r * 0.25, r * 0.2, "#5a4338");
      if (caldo > 0.05) {
        ctx.globalAlpha = caldo; ctx.strokeStyle = "#ffb62e"; ctx.lineWidth = 0.9 * S; ctx.lineCap = "round"; ctx.beginPath();
        ctx.moveTo(-r * 0.6, r * 0.1); ctx.lineTo(-r * 0.1, r * 0.3); ctx.lineTo(r * 0.2, -r * 0.1); ctx.lineTo(r * 0.65, 0.05 * r); ctx.stroke();
      }
      ctx.restore(); return;
    }
    if (t.tipo === "bomba") {
      const r = 5.2 * S, rosso = t.miccia > 0 && t.miccia < 60 && passi % 8 < 4;
      ctx.fillStyle = rosso ? "#7a1a14" : "#1d1d22"; ctx.strokeStyle = "#000"; ctx.lineWidth = 1 * S;
      ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      tondo(-r * 0.35, -r * 0.35, r * 0.28, "rgba(255,255,255,.45)");
      ctx.fillStyle = "#555b66"; ctx.fillRect(-1.8 * S, -r - 2 * S, 3.6 * S, 2.6 * S);
      ctx.strokeStyle = "#8a6a3a"; ctx.lineWidth = 1.1 * S; ctx.beginPath();
      ctx.moveTo(0, -r - 2 * S); ctx.quadraticCurveTo(2.5 * S, -r - 5 * S, 4.5 * S, -r - 4 * S); ctx.stroke();
      if (t.miccia > 0) stella(4.5 * S, -r - 4 * S, (1.6 + Math.random()) * S, passi % 4 < 2 ? "#ffd84a" : "#ff8a1a");
      ctx.restore(); return;
    }
    const w = t.w, h = t.h;
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1.2 * S; ctx.lineJoin = "round";
    if (t.tipo === "duo") {
      // Il pieghevole si apre a libro mentre la mela lo tira fuori, e brilla.
      if (t.stato === "portato") {
        const alone = ctx.createRadialGradient(0, 0, 2 * S, 0, 0, 20 * S);
        alone.addColorStop(0, "rgba(220,200,255,.75)"); alone.addColorStop(1, "rgba(220,200,255,0)");
        ctx.fillStyle = alone; ctx.beginPath(); ctx.arc(0, 0, 20 * S, 0, Math.PI * 2); ctx.fill();
      }
      ctx.scale(0.5 + 0.5 * t.apre, 1);
    }
    if (t.tipo === "orologio") {
      ctx.fillStyle = mix(t.colore, "#000000", 0.2);
      rettangoloTondo(-w * 0.32, -h / 2 - 5 * S, w * 0.64, h + 10 * S, 1.6 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#c9ced8"; rettangoloTondo(-w / 2, -h / 2, w, h, 2.4 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#9aa1ad"; ctx.fillRect(w / 2, -1.2 * S, 1.3 * S, 2.4 * S);
    } else if (t.tipo === "pc") {
      // Il portatile aperto: il coperchio con lo schermo e, sotto, la tastiera.
      ctx.fillStyle = mix(t.colore, "#000000", 0.15); ctx.beginPath();
      ctx.moveTo(-w / 2, h * 0.18); ctx.lineTo(w / 2, h * 0.18); ctx.lineTo(w / 2 + 2.4 * S, h / 2); ctx.lineTo(-w / 2 - 2.4 * S, h / 2);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "rgba(0,0,0,.35)";
      for (let i = 0; i < 6; i++) ctx.fillRect((-w / 2 + 1.5 * S) + i * (w - 3 * S) / 6, h * 0.27, (w - 3 * S) / 6 - 0.8 * S, 1.3 * S);
      ctx.fillStyle = t.colore; rettangoloTondo(-w / 2, -h / 2, w, h * 0.68, 1.6 * S); ctx.fill(); ctx.stroke();
    } else {
      ctx.fillStyle = t.colore;
      rettangoloTondo(-w / 2, -h / 2, w, h, (t.tipo === "tablet" ? 2.8 : 2) * S); ctx.fill(); ctx.stroke();
    }
    const [sx, sy, sw, sh] = t.sch;
    if (t.tipo === "duo") {
      const g = ctx.createLinearGradient(sx, sy, sx + sw, sy + sh);
      g.addColorStop(0, "#6b4bd8"); g.addColorStop(0.5, "#d65aa8"); g.addColorStop(1, "#f2a64a");
      ctx.fillStyle = t.stato === "preso" ? "#7fe0ff" : g;
    } else ctx.fillStyle = t.stato === "preso" ? "#7fe0ff" : "#10202e";
    rettangoloTondo(sx, sy, sw, sh, 1.2 * S); ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,.25)";
    ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + sw * 0.6, sy); ctx.lineTo(sx, sy + sh * 0.6); ctx.closePath(); ctx.fill();
    if (t.tipo === "pieghevole") { ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.moveTo(-w / 2, 0); ctx.lineTo(w / 2, 0); ctx.stroke(); }
    if (t.tipo === "duo") {
      ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.lineWidth = 0.8 * S; ctx.beginPath(); ctx.moveTo(0, -h / 2); ctx.lineTo(0, h / 2); ctx.stroke();
      ctx.fillStyle = "#000"; rettangoloTondo(-sw * 0.18, sy + 0.8 * S, sw * 0.36, 1.4 * S, 0.7 * S); ctx.fill();
    } else if (t.tipo !== "orologio" && t.tipo !== "pc") tondo(0, -h / 2 + 0.8 * S, 0.5 * S, "#000");
    if (t.rotture && t.rotture.length) {
      // Ritaglio: le crepe vivono solo dentro lo schermo.
      ctx.save();
      rettangoloTondo(sx, sy, sw, sh, 1.2 * S); ctx.clip();
      for (const r of t.rotture) {
        // Macchia scura dove il vetro ha ceduto.
        ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.beginPath(); ctx.arc(r.cx, r.cy, r.anelli[0] * 0.9, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = "rgba(235,246,255,.9)"; ctx.lineWidth = 0.55 * S; ctx.lineJoin = "round"; ctx.beginPath();
        for (const pts of r.raggi) {
          ctx.moveTo(pts[0][0], pts[0][1]);
          for (let k = 1; k < pts.length; k++) ctx.lineTo(pts[k][0], pts[k][1]);
        }
        ctx.stroke();
        ctx.strokeStyle = "rgba(235,246,255,.5)"; ctx.lineWidth = 0.4 * S; ctx.beginPath();
        for (const rr of r.anelli) { ctx.moveTo(r.cx + rr, r.cy); ctx.arc(r.cx, r.cy, rr, 0, Math.PI * 2); }
        ctx.stroke();
      }
      ctx.restore();
    }
    ctx.restore();
  }

  function disegnaParticella(q) {
    ctx.save();
    ctx.globalAlpha = Math.max(0, Math.min(1, q.vita / (q.max * 0.6)));
    if (q.tipo === "scintilla") {
      ctx.strokeStyle = q.colore; ctx.lineWidth = 1.6 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x - q.vx * 1.6, q.y - q.vy * 1.6); ctx.stroke();
    } else if (q.tipo === "fiamma") {
      ctx.fillStyle = q.colore; ctx.beginPath();
      ctx.arc(q.x, q.y, Math.max(0.5, (1 + 3.2 * (q.vita / q.max))) * S, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "mote") {
      ctx.globalAlpha = 0.9; ctx.fillStyle = q.colore; ctx.beginPath(); ctx.arc(q.x, q.y, 1.8 * S, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "linea") {
      const v = Math.hypot(q.vx, q.vy) || 1;
      ctx.strokeStyle = q.colore; ctx.lineWidth = 1.4 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x + q.vx / v * q.lung, q.y + q.vy / v * q.lung); ctx.stroke();
    } else if (q.tipo === "taglio") {
      // Il segno di un taglio: una riga di luce che si assottiglia.
      const k = q.vita / q.max, dx = Math.cos(q.ang) * q.lung * (1.2 - 0.2 * k), dy = Math.sin(q.ang) * q.lung * (1.2 - 0.2 * k);
      ctx.lineCap = "round"; ctx.globalAlpha = 0.5 * k; ctx.strokeStyle = q.colore; ctx.lineWidth = 6 * S * k;
      ctx.beginPath(); ctx.moveTo(q.x - dx, q.y - dy); ctx.lineTo(q.x + dx, q.y + dy); ctx.stroke();
      ctx.globalAlpha = k; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.8 * S * k; ctx.stroke();
    } else if (q.tipo === "zip") {
      ctx.strokeStyle = q.colore; ctx.lineWidth = 1.6 * S; ctx.lineCap = "round"; ctx.beginPath();
      for (const dx of [-9, -3, 3, 9]) { ctx.moveTo(q.x + dx * S, q.y - 34 * S); ctx.lineTo(q.x + dx * S, q.y + 24 * S); }
      ctx.stroke();
    } else if (q.tipo === "lampo") {
      const g = ctx.createRadialGradient(q.x, q.y, 0, q.x, q.y, q.r);
      g.addColorStop(0, "rgba(255,255,240,.95)"); g.addColorStop(0.4, "rgba(255,226,122,.55)"); g.addColorStop(1, "rgba(255,180,60,0)");
      ctx.globalAlpha = q.vita / q.max; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "fuoco") {
      const k = q.vita / q.max;
      ctx.fillStyle = k > 0.75 ? "#fff3b0" : k > 0.5 ? "#ffb62e" : k > 0.28 ? "#ff6a1a" : "#6e4a3a";
      ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "fumo") {
      ctx.globalAlpha = 0.55 * q.vita / q.max; ctx.fillStyle = q.colore;
      ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "detrito") {
      ctx.translate(q.x, q.y); ctx.rotate(q.rot); ctx.fillStyle = q.colore;
      ctx.fillRect(-q.lato / 2, -q.lato * 0.35, q.lato, q.lato * 0.7);
    } else if (q.tipo === "pezzetto") {
      // Il boccone portato via: polpa bianca con la buccia nera sul bordo.
      ctx.translate(q.x, q.y); ctx.rotate(q.rot);
      const r = q.lato;
      ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(0, 0, r, Math.PI, Math.PI * 2); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = "#f1dfb6"; ctx.lineWidth = 1.4 * S; ctx.stroke();
      ctx.strokeStyle = "#111"; ctx.lineWidth = 2 * S; ctx.beginPath(); ctx.arc(0, 0, r, Math.PI, Math.PI * 2); ctx.stroke();
    } else if (q.tipo === "brace") {
      ctx.fillStyle = (passi + Math.round(q.x)) % 6 < 3 ? q.colore : "#fff1a0";
      ctx.beginPath(); ctx.arc(q.x, q.y, 1.3 * S, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "goccia") {
      ctx.globalAlpha = 0.9; ctx.fillStyle = q.colore; ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill();
    } else if (q.tipo === "fiocco") {
      ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "rgba(70,100,135,.55)"; ctx.lineWidth = 0.8 * S;
      ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    } else if (q.tipo === "vento") {
      ctx.globalAlpha = 0.4; ctx.strokeStyle = "#7d8696"; ctx.lineWidth = 1.2 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(q.x, q.y); ctx.lineTo(q.x - Math.sign(q.vx) * q.lung, q.y); ctx.stroke();
    } else if (q.tipo === "nota") {
      ctx.fillStyle = q.colore; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2 * S;
      ctx.font = "700 " + Math.round(14 * S) + "px sans-serif"; ctx.textAlign = "center";
      ctx.strokeText(q.testo, q.x, q.y); ctx.fillText(q.testo, q.x, q.y);
    } else if (q.tipo === "onda") {
      const k = 1 - q.vita / q.max;
      ctx.globalAlpha = Math.max(0, 1 - k);
      ctx.strokeStyle = q.colore; ctx.lineWidth = (6 - 4 * k) * S;
      ctx.beginPath(); ctx.arc(q.x, q.y, (10 + 70 * k) * S, 0, Math.PI * 2); ctx.stroke();
    } else if (q.tipo === "polvere") {
      ctx.fillStyle = q.colore; ctx.beginPath(); ctx.arc(q.x, q.y, (2 + (1 - q.vita / q.max) * 4) * S, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.translate(q.x, q.y); ctx.rotate(q.rot); ctx.fillStyle = q.colore; ctx.fillRect(-1.6 * S, -1 * S, 3.2 * S, 2 * S);
    }
    ctx.restore();
  }

  function disegnaProiettile(b) {
    if (b.razzo) {
      // Il razzo: un cilindro con la punta e le alette, e la coda di fuoco.
      const a = Math.atan2(b.vy, b.vx);
      ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(a);
      ctx.fillStyle = "#ffb62e"; ctx.globalAlpha = 0.55;
      ctx.beginPath(); ctx.moveTo(-6 * S, -3.4 * S); ctx.lineTo(-20 * S, 0); ctx.lineTo(-6 * S, 3.4 * S); ctx.closePath(); ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = "#111"; ctx.lineWidth = 1.1 * S; ctx.lineJoin = "round";
      ctx.fillStyle = "#3f4a3a"; rettangoloTondo(-7 * S, -3 * S, 12 * S, 6 * S, 1.6 * S); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#d14b2a"; ctx.beginPath();
      ctx.moveTo(5 * S, -3 * S); ctx.lineTo(11 * S, 0); ctx.lineTo(5 * S, 3 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#2f382c"; ctx.beginPath();
      ctx.moveTo(-7 * S, -3 * S); ctx.lineTo(-10 * S, -5.4 * S); ctx.lineTo(-10 * S, 5.4 * S); ctx.lineTo(-7 * S, 3 * S); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.restore();
      return;
    }
    if (b.grande) { disegnaSferaGrande(b.x, b.y, b.r, b.colore); return; }
    if (b.disco) { if (b.lamaDi) disegnaLamaVolante(b); else disegnaDisco(b.x, b.y, 11 * S, b.colore); return; }
    if (b.incanto || b.stella) {
      // Gli incantesimi sono stelle con la coda.
      const v = Math.hypot(b.vx, b.vy) || 1;
      ctx.save(); ctx.strokeStyle = b.colore; ctx.globalAlpha = 0.5; ctx.lineWidth = 2.4 * S; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(b.x - b.vx / v * 16 * S, b.y - b.vy / v * 16 * S); ctx.lineTo(b.x, b.y); ctx.stroke();
      ctx.globalAlpha = 1; stella(b.x, b.y, (b.incanto ? 5.4 : 3.8) * S, b.colore); stella(b.x, b.y, (b.incanto ? 2.6 : 1.8) * S, "#ffffff");
      ctx.restore();
      return;
    }
    if (b.energia) {
      ctx.save(); ctx.globalAlpha = 0.45; ctx.fillStyle = b.colore; ctx.beginPath(); ctx.arc(b.x, b.y, 6 * S, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1; tondo(b.x, b.y, 2.6 * S, "#ffffff"); ctx.restore();
      return;
    }
    if (b.neve) {
      tondo(b.x, b.y, 3.2 * S, "#ffffff");
      ctx.strokeStyle = "rgba(0,0,0,.25)"; ctx.lineWidth = 0.8 * S; ctx.beginPath(); ctx.arc(b.x, b.y, 3.2 * S, 0, Math.PI * 2); ctx.stroke();
      return;
    }
    const v = Math.hypot(b.vx, b.vy) || 1, ux = b.vx / v, uy = b.vy / v;
    ctx.save();
    ctx.strokeStyle = "rgba(255,226,122,.55)"; ctx.lineWidth = 2 * S; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(b.x - ux * 12 * S, b.y - uy * 12 * S); ctx.lineTo(b.x, b.y); ctx.stroke();
    ctx.translate(b.x, b.y); ctx.rotate(Math.atan2(uy, ux));
    ctx.fillStyle = "#ffb62e"; ctx.strokeStyle = "#111"; ctx.lineWidth = 0.9 * S;
    rettangoloTondo(-2.6 * S, -1.3 * S, 5.2 * S, 2.6 * S, 1.3 * S); ctx.fill(); ctx.stroke();
    ctx.restore();
  }

  // Il paracadute: una cupola a spicchi bianchi e colorati, con le corde
  // fino alle mani. Si apre e si richiude piano (f.para va da 0 a 1).
  function disegnaParacadute(f) {
    const k = f.para;
    if (!(k > 0.02)) return;
    const p = f.p, sx = p.manoA.x < p.manoD.x ? p.manoA : p.manoD, dx = sx === p.manoA ? p.manoD : p.manoA;
    const sway = Math.max(-6 * S, Math.min(6 * S, (p.bacino.x - p.bacino.ox) * 6));
    const cx = (sx.x + dx.x) / 2 - sway, cy = Math.min(sx.y, dx.y) - 30 * S * k, w = 27 * S * k, h = 16 * S * k;
    const [c1, c2] = f.tipo === "robot" ? ["#ff5a4a", "#ffffff"] : ["#2f72e0", "#ffffff"];
    ctx.save();
    ctx.strokeStyle = "rgba(20,20,20,.7)"; ctx.lineWidth = 0.8 * S; ctx.beginPath();
    for (const fr of [-1, -0.35, 0.35, 1]) { const m = fr < 0 ? sx : dx; ctx.moveTo(cx + fr * w, cy); ctx.lineTo(m.x, m.y); }
    ctx.stroke();
    const cupola = () => {
      ctx.beginPath(); ctx.moveTo(cx - w, cy);
      ctx.bezierCurveTo(cx - w, cy - h * 1.6, cx + w, cy - h * 1.6, cx + w, cy);
      for (let i = 2; i >= 0; i--) {
        const x1 = cx - w + (2 * w) * i / 3, x2 = cx - w + (2 * w) * (i + 1) / 3;
        ctx.quadraticCurveTo((x1 + x2) / 2, cy - 4 * S * k, x1, cy);
      }
      ctx.closePath();
    };
    cupola(); ctx.fillStyle = c1; ctx.fill();
    ctx.save(); cupola(); ctx.clip();
    ctx.fillStyle = c2; ctx.fillRect(cx - w / 6, cy - h * 2, w / 3, h * 3);
    ctx.fillRect(cx - w, cy - h * 2, w / 4, h * 3); ctx.fillRect(cx + w * 0.75, cy - h * 2, w / 4, h * 3);
    ctx.restore();
    cupola(); ctx.strokeStyle = "#111"; ctx.lineWidth = 1.2 * S; ctx.stroke();
    ctx.restore();
  }

  // I segni dei colpi, nel sistema di riferimento della parte colpita.
  function disegnaSegni(f, parte) {
    if (!f.segni || !f.segni.length) return;
    for (const sg of f.segni) {
      if (sg.parte !== parte) continue;
      const x = sg.u * S, y = sg.v * S, r = sg.r * S, a = Math.min(1, sg.vita / 600);
      ctx.save(); ctx.globalAlpha = a;
      if (stile) {
        // Un livido, sui personaggi in carne e ossa.
        const g = ctx.createRadialGradient(x, y, 0, x, y, r * 1.2);
        g.addColorStop(0, "rgba(96,52,120,.6)"); g.addColorStop(0.6, "rgba(120,70,130,.35)"); g.addColorStop(1, "rgba(130,80,140,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 1.2, 0, Math.PI * 2); ctx.fill();
      } else if (f.tipo === "mela") {
        // Livido marrone, come una mela ammaccata vera.
        const g = ctx.createRadialGradient(x, y, 0, x, y, r * 1.3);
        g.addColorStop(0, "rgba(120,72,34,.75)"); g.addColorStop(0.6, "rgba(150,96,50,.45)"); g.addColorStop(1, "rgba(160,110,60,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 1.3, 0, Math.PI * 2); ctx.fill();
      } else {
        // Ammaccatura: una conca scura e due graffi chiari.
        ctx.fillStyle = "rgba(0,0,0,.28)"; ctx.beginPath();
        for (let i = 0; i < 7; i++) {
          const an = (i / 7) * Math.PI * 2, rr = r * (0.7 + 0.3 * Math.sin(sg.seme + i * 2.3));
          if (i) ctx.lineTo(x + Math.cos(an) * rr, y + Math.sin(an) * rr); else ctx.moveTo(x + Math.cos(an) * rr, y + Math.sin(an) * rr);
        }
        ctx.closePath(); ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,.6)"; ctx.lineWidth = 0.6 * S; ctx.beginPath();
        ctx.moveTo(x - r * 0.6, y - r * 0.2); ctx.lineTo(x + r * 0.5, y + r * 0.3);
        ctx.moveTo(x - r * 0.3, y + r * 0.5); ctx.lineTo(x + r * 0.6, y - r * 0.1); ctx.stroke();
      }
      ctx.restore();
    }
  }

  // Un arto staccato che vola (e poi torna).
  function disegnaArto(a) {
    ctx.save(); ctx.translate(a.x, a.y); ctx.rotate(a.ang);
    if (a.forma === "picciolo") {
      if (a.f.tipo === "mela") {
        ctx.strokeStyle = "#6b4423"; ctx.lineWidth = 1.8 * S; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(0, 4 * S); ctx.lineTo(1.6 * S, -4 * S); ctx.stroke();
        ctx.fillStyle = "#3f9a3a"; ctx.beginPath(); ctx.ellipse(5.5 * S, -3 * S, 5 * S, 2.1 * S, -0.45, 0, Math.PI * 2); ctx.fill();
      } else {
        ctx.strokeStyle = a.colore; ctx.lineWidth = 1.4 * S; ctx.beginPath(); ctx.moveTo(0, 5 * S); ctx.lineTo(0, -3 * S); ctx.stroke();
        tondo(0, -3.6 * S, 2.1 * S, "#ffcf3a");
      }
      ctx.restore(); return;
    }
    const L = a.L, robot = a.grosso, w = robot ? 4.6 * S : 3 * S;
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S;
    ctx.fillStyle = a.colore; rettangoloTondo(-L / 2, -w / 2, L, w, w / 2); ctx.fill(); if (robot) ctx.stroke();
    tondo(-L / 2, 0, w * 0.6, a.olio ? "#1b1b1b" : "#d8343f");
    if (a.forma === "braccio") {
      ctx.fillStyle = a.estremo; ctx.beginPath(); ctx.ellipse(L / 2 + 2 * S, 0, 4.4 * S, 3.8 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    } else {
      ctx.fillStyle = a.estremo; ctx.beginPath(); ctx.ellipse(L / 2 + 1.5 * S, 1 * S, 4.4 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    ctx.restore();
  }

  // Un pezzo del robot esploso.
  function disegnaPezzo(pz) {
    ctx.save(); ctx.translate(pz.x, pz.y); ctx.rotate(pz.ang);
    ctx.strokeStyle = "#111"; ctx.lineWidth = 1 * S; ctx.fillStyle = pz.colore;
    switch (pz.forma) {
      case "asta": rettangoloTondo(-pz.L / 2, -pz.w / 2, pz.L, pz.w, pz.w / 2); ctx.fill(); ctx.stroke(); break;
      case "busto":
        rettangoloTondo(-8.5 * S, -pz.L / 2 - 3 * S, 17 * S, pz.L + 7 * S, 4 * S); ctx.fill(); ctx.stroke();
        for (let i = 0; i < 3 && !pz.liscio; i++) tondo((-3 + 3 * i) * S, -pz.L / 2 + 6 * S, 1.2 * S, "#555");
        break;
      case "bombola": rettangoloTondo(-2.6 * S, -9 * S, 5.2 * S, 18 * S, 2.4 * S); ctx.fill(); ctx.stroke(); break;
      case "testa":
        rettangoloTondo(-8.5 * S, -7.5 * S, 17 * S, 15 * S, 4 * S); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#0f2a1f"; rettangoloTondo(-6.8 * S, -3.8 * S, 13.6 * S, 7 * S, 2.6 * S); ctx.fill();
        ctx.strokeStyle = "#7dffd2"; ctx.lineWidth = 1.3 * S; ctx.beginPath();
        for (const ex of [-2.9, 2.9]) {
          ctx.moveTo((ex - 1.3) * S, -1.5 * S); ctx.lineTo((ex + 1.3) * S, 1.1 * S);
          ctx.moveTo((ex + 1.3) * S, -1.5 * S); ctx.lineTo((ex - 1.3) * S, 1.1 * S);
        }
        ctx.stroke(); break;
      case "capo":
        // La testa di un personaggio inventato: la faccia stordita e i capelli (o il cappello).
        ctx.beginPath(); ctx.arc(0, 0, 8 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = pz.capelli; ctx.beginPath(); ctx.arc(0, -1 * S, 8.4 * S, Math.PI * 1.08, Math.PI * 1.92); ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.lineWidth = 1.2 * S; ctx.beginPath();
        for (const ex of [-2.8, 2.8]) {
          ctx.moveTo((ex - 1.2) * S, 0.2 * S); ctx.lineTo((ex + 1.2) * S, 2.4 * S);
          ctx.moveTo((ex + 1.2) * S, 0.2 * S); ctx.lineTo((ex - 1.2) * S, 2.4 * S);
        }
        ctx.stroke(); break;
      case "pugno": ctx.beginPath(); ctx.arc(0, 0, 3.3 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); break;
      case "guanto":
        ctx.beginPath(); ctx.ellipse(0, 0, 4.6 * S, 3.9 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#f4f4f4"; ctx.fillRect(-6 * S, -2 * S, 2 * S, 4 * S); break;
      case "piede": rettangoloTondo(-4.2 * S, -2.6 * S, 8.4 * S, 4.8 * S, 1.8 * S); ctx.fill(); ctx.stroke(); break;
      case "spicchio": {
        // Un quarto di mela: polpa bianca, buccia nera sul bordo, due semi.
        const R = 17 * S;
        ctx.beginPath(); ctx.moveTo(-0.6 * R, 0); ctx.arc(-0.6 * R, 0, R, -Math.PI / 4, Math.PI / 4); ctx.closePath();
        ctx.fillStyle = "#ffffff"; ctx.fill();
        ctx.lineWidth = 1 * S; ctx.strokeStyle = "#d9cfbd"; ctx.stroke();
        ctx.beginPath(); ctx.arc(-0.6 * R, 0, R, -Math.PI / 4, Math.PI / 4); ctx.lineWidth = 2.6 * S; ctx.strokeStyle = "#111"; ctx.stroke();
        ctx.fillStyle = "#4a2e1a";
        for (const [x, y] of [[-0.12, -0.08], [-0.12, 0.08]]) { ctx.beginPath(); ctx.ellipse(x * R, y * R, 0.07 * R, 0.04 * R, 0, 0, Math.PI * 2); ctx.fill(); }
        break;
      }
      case "picciolo":
        ctx.strokeStyle = "#6b4423"; ctx.lineWidth = 1.8 * S; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(0, 3 * S); ctx.lineTo(1.6 * S, -4 * S); ctx.stroke();
        ctx.fillStyle = "#3f9a3a"; ctx.beginPath(); ctx.ellipse(5.5 * S, -3 * S, 4.6 * S, 2 * S, -0.45, 0, Math.PI * 2); ctx.fill();
        break;
      case "occhio":
        ctx.fillStyle = "#111"; ctx.beginPath(); ctx.ellipse(0, 0, 2.1 * S, 2.9 * S, 0, 0, Math.PI * 2); ctx.fill();
        tondo(0.6 * S, -1 * S, 0.7 * S, "#ffffff"); break;
      case "scarpa":
        ctx.beginPath(); ctx.ellipse(0, 0, 4.2 * S, 2.6 * S, 0, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 1.2 * S; ctx.stroke(); break;
      case "antenna":
        ctx.strokeStyle = pz.colore; ctx.lineWidth = 1.4 * S; ctx.beginPath(); ctx.moveTo(0, 4 * S); ctx.lineTo(0, -3 * S); ctx.stroke();
        tondo(0, -3.6 * S, 2.1 * S, "#ffcf3a"); break;
      default: tondo(0, 0, 1.7 * S, pz.colore); ctx.beginPath(); ctx.arc(0, 0, 1.7 * S, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
  }

  // --- Lo scenario della gravità ----------------------------------------
  // Sulla Luna la Terra nel cielo, le stelle e il suolo coi crateri; nello
  // Spazio un pianeta con gli anelli, stelle e sassi che fluttuano; su Giove
  // il pianeta a fasce con la macchia rossa e un suolo arancione. Solo nei
  // margini, sottile: la pagina resta leggibile.
  const STELLE = Array.from({ length: 36 }, (_, i) => ({ u: ((i * 73) % 97) / 97, v: ((i * 37) % 89) / 89, f: i * 0.7 }));
  const temaGravita = () => (verso < 0 ? "sottosopra" : moltG < 0.2 ? "spazio" : moltG < 0.7 ? "luna" : moltG > 1.3 ? "giove" : "terra");
  function disegnaScenario() {
    const tema = temaGravita();
    if (tema === "terra") return;
    const cieloA = testataBasso + 8, cieloB = pavimento - 40 * S;
    ctx.save();
    if (tema === "luna" || tema === "spazio") {
      for (const st of STELLE) {
        const a = 0.35 + 0.35 * Math.sin(passi * 0.05 + st.f);
        ctx.globalAlpha = a; stella(st.u * W, cieloA + st.v * (cieloB - cieloA), (1.2 + (st.f % 1)) * S, "#8e9ab0");
      }
      ctx.globalAlpha = 1;
    }
    const px = W - 80 * S, py = cieloA + 110 * S;
    if (tema === "luna") {
      // La Terra, con un'ombra sul lato in ombra.
      const r = 24 * S;
      ctx.save(); ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.clip();
      ctx.fillStyle = "#3f7fd6"; ctx.fillRect(px - r, py - r, 2 * r, 2 * r);
      ctx.fillStyle = "#5aa55a";
      for (const [dx, dy, rx, ry] of [[-8, -6, 9, 6], [7, 6, 8, 10], [10, -12, 5, 4]]) { ctx.beginPath(); ctx.ellipse(px + dx * S, py + dy * S, rx * S, ry * S, 0.4, 0, Math.PI * 2); ctx.fill(); }
      ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = 2 * S;
      ctx.beginPath(); ctx.arc(px - 4 * S, py + 2 * S, 14 * S, 3.6, 4.6); ctx.stroke();
      const om = ctx.createLinearGradient(px - r, py, px + r, py);
      om.addColorStop(0.55, "rgba(10,15,30,0)"); om.addColorStop(1, "rgba(10,15,30,.55)");
      ctx.fillStyle = om; ctx.fillRect(px - r, py - r, 2 * r, 2 * r);
      ctx.restore();
      ctx.strokeStyle = "rgba(20,30,60,.5)"; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.stroke();
      suolo("#cfccc5", "#b3afa7");
    } else if (tema === "spazio") {
      const r = 20 * S;
      ctx.strokeStyle = "#e8c27a"; ctx.lineWidth = 3 * S;
      ctx.beginPath(); ctx.ellipse(px, py, r * 1.9, r * 0.5, -0.3, Math.PI, Math.PI * 2); ctx.stroke();
      const g = ctx.createRadialGradient(px - r * 0.4, py - r * 0.4, r * 0.2, px, py, r);
      g.addColorStop(0, "#e6a8f0"); g.addColorStop(1, "#8a4fb0");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.ellipse(px, py, r * 1.9, r * 0.5, -0.3, 0, Math.PI); ctx.stroke();
      // Qualche sasso che fluttua, e ogni tanto una cometa.
      for (let i = 0; i < 3; i++) {
        const x = ((passi * (0.25 + i * 0.1) + i * 400) % (W + 80)) - 40, y = cieloA + (0.2 + 0.25 * i) * (cieloB - cieloA);
        ctx.save(); ctx.translate(x, y); ctx.rotate(passi * 0.01 * (i + 1));
        ctx.fillStyle = "#9a948a"; ctx.beginPath();
        ctx.moveTo(-5 * S, -2 * S); ctx.lineTo(-1 * S, -5 * S); ctx.lineTo(5 * S, -3 * S); ctx.lineTo(4 * S, 3 * S); ctx.lineTo(-3 * S, 4 * S);
        ctx.closePath(); ctx.fill(); ctx.restore();
      }
      const ciclo = passi % 900;
      if (ciclo < 160) {
        const k = ciclo / 160, cx = -40 + k * (W + 80), cy = cieloA + 30 * S + k * 80 * S;
        const coda = ctx.createLinearGradient(cx, cy, cx - 70 * S, cy - 20 * S);
        coda.addColorStop(0, "rgba(140,200,255,.8)"); coda.addColorStop(1, "rgba(140,200,255,0)");
        ctx.strokeStyle = coda; ctx.lineWidth = 3 * S; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx - 70 * S, cy - 20 * S); ctx.stroke();
        tondo(cx, cy, 2.6 * S, "#ffffff");
      }
    } else if (tema === "giove") {
      const r = 32 * S;
      ctx.save(); ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.clip();
      const fasce = ["#e8d2b0", "#c98d5a", "#efe0c8", "#b9774a", "#e8d2b0", "#c98d5a", "#efe0c8"];
      fasce.forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(px - r, py - r + i * (2 * r / fasce.length), 2 * r, 2 * r / fasce.length + 1); });
      ctx.fillStyle = "#c4553a"; ctx.beginPath(); ctx.ellipse(px + 10 * S, py + 9 * S, 8 * S, 4.5 * S, 0, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
      ctx.strokeStyle = "rgba(90,50,20,.45)"; ctx.lineWidth = 1 * S; ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.stroke();
      suolo("#d9a066", "#b9774a");
    }
    ctx.restore();
  }
  // Un suolo sottile appoggiato sulla striscia, coi crateri.
  function suolo(chiaro, scuro) {
    const alto = 9 * S;
    ctx.fillStyle = chiaro; ctx.beginPath(); ctx.moveTo(0, pavimento);
    for (let x = 0; x <= W + 30; x += 30) ctx.lineTo(x, pavimento - alto * (0.6 + 0.4 * Math.sin(x * 0.037)));
    ctx.lineTo(W, pavimento); ctx.closePath(); ctx.fill();
    ctx.fillStyle = scuro;
    for (let x = 40; x < W; x += 110) { ctx.beginPath(); ctx.ellipse(x, pavimento - alto * 0.35, 9 * S, 2.2 * S, 0, 0, Math.PI * 2); ctx.fill(); }
  }
  // Il casco a bolla, sulla Luna e nello Spazio.
  function casco(r) {
    ctx.fillStyle = "rgba(190,225,255,.18)"; ctx.strokeStyle = "rgba(120,160,200,.85)"; ctx.lineWidth = 1.4 * S;
    ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 1.4 * S;
    ctx.beginPath(); ctx.arc(0, 0, r * 0.78, Math.PI * 1.15, Math.PI * 1.45); ctx.stroke();
  }

  function disegna() {
    ctx.clearRect(0, 0, W, H);
    disegnaScenario();
    ctx.save();
    if (scossa > 0) ctx.translate(caso(-1, 1) * Math.min(4, scossa) * S, caso(-1, 1) * Math.min(4, scossa) * S);
    disegnaDanni();
    disegnaBordi();
    for (const m of macchie) {
      ctx.globalAlpha = Math.min(0.85, m.vita / 300); ctx.fillStyle = m.colore;
      ctx.beginPath(); ctx.ellipse(m.x, m.y, m.r, m.r * m.schiacciata, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    if (cumulo > 0.3 * S) {
      ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "rgba(70,100,135,.5)"; ctx.lineWidth = 1.2 * S; ctx.beginPath();
      ctx.moveTo(0, pavimento + 1);
      for (let x = 0; x <= W + 20; x += 20) ctx.lineTo(x, pavimento - cumulo * (0.7 + 0.3 * Math.sin(x * 0.05)));
      ctx.lineTo(W, pavimento + 1); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    if (uragano) disegnaUragano();
    disegnaFinale(false);
    disegnaBuioFatale();
    disegnaMira();
    disegnaVulcano(); disegnaColate(); disegnaMirini();
    for (const t of telefoni) if (t.stato !== "impugnato" && !t.inBuco) disegnaTelefono(t);
    for (const pz of pezzi) disegnaPezzo(pz);
    for (const f of lottatori) disegnaCratere(f.cratere);
    disegnaScie();
    disegnaOrda();
    disegnaFondoCorsa();
    const ordine = lottatori.slice().sort((x, y) => (y.ko ? 1 : 0) - (x.ko ? 1 : 0));
    for (const f of ordine) {
      if (f.esploso) continue;
      if (!f.fuoriCampo) disegnaLottatore(f);
      else if (f.vortice > 0 && buco) {
        // Nel vortice: si vede ancora, girando intorno alla bocca e sempre più piccolo, finché ci sparisce dentro.
        // (È solo disegno: i suoi punti restano fermi dov'era quando è stato preso.)
        const u = 1 - f.vortice / BUCO.vortice, k = Math.pow(1 - u, 1.3);
        ctx.save(); ctx.translate(buco.x, buco.y); ctx.rotate(u * 5.4); ctx.scale(k, k); ctx.translate(-buco.x, -buco.y);
        disegnaLottatore(f);
        ctx.restore();
      }
    }
    for (const c of creature) disegnaCreatura(c);
    for (const t of telefoni) if (t.stato === "impugnato") disegnaTelefono(t);
    for (const a of arti) disegnaArto(a);
    for (const b of proiettili) disegnaProiettile(b);
    disegnaLapilli(); disegnaMeteore(); disegnaBuco(); disegnaFatale();
    for (const z of fulmini) disegnaFulmine(z);
    // Le stelline di chi è stordito o al tappeto.
    for (const f of lottatori) {
      if (f.esploso || f.fuoriCampo || f.gelato > 0 || !(f.stordito > 0 || f.accecato > 0 || (f.ko > 0 && !f.inVolo))) continue;
      for (let i = 0; i < 3; i++) {
        const ang = passi * 0.12 + (i * Math.PI * 2) / 3;
        stella(f.p.testa.x + Math.cos(ang) * 11 * S, f.p.testa.y - 12 * S + Math.sin(ang) * 3.5 * S, 2.6 * S, "#ffd84a");
      }
    }
    for (const f of lottatori) {
      if (f.esploso) continue;
      if (f.tenuto && f.tenuto.tele !== undefined) (f.tenuto.magia ? disegnaLevitazione : disegnaTelecinesi)(f);
      if (f.azione === "barriera") disegnaBarriera(f);
      if (f.sfera) disegnaSferaGrande(f.sfera.x, f.sfera.y, f.sfera.r, COLORI_ANIME[f.tipo]);
      if (f.azione === "disco" && f.t < 30) disegnaDisco(f.p.manoA.x, f.p.manoA.y - 12 * S, (3 + 8 * f.t / 30) * S, COLORI_ANIME[f.tipo]);
      if (f.azione === "avvinghia") {
        // Lampeggia sempre più in fretta prima del botto.
        const c = f.p.collo, k = 0.5 + 0.5 * Math.sin(f.t * f.t * 0.012);
        const g = ctx.createRadialGradient(c.x, c.y, 2 * S, c.x, c.y, (26 + f.t * 0.25) * S);
        g.addColorStop(0, "rgba(255,255,255," + (0.5 + 0.4 * k) + ")"); g.addColorStop(0.5, "rgba(255,120,40," + 0.45 * k + ")"); g.addColorStop(1, "rgba(255,80,20,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(c.x, c.y, (26 + f.t * 0.25) * S, 0, Math.PI * 2); ctx.fill();
      }
    }
    for (const f of lottatori) {
      if (f.onda) disegnaOnda(f);
      else if (anime && f.azione === "onda" && f.t < 34 && !f.esploso) disegnaCaricaOnda(f);
    }
    disegnaSfida();
    for (const q of particelle) disegnaParticella(q);
    disegnaPioggia();
    disegnaFinale(true);
    if (barreVita && !corsa) disegnaBarre();
    ctx.restore();
    disegnaTastiSfida();
    disegnaRadiale();
    for (const s of scritte) {
      ctx.save();
      ctx.globalAlpha = Math.min(1, s.vita / 12);
      ctx.font = "800 " + Math.round((s.grande ? 17 : 12) * S) + "px Archivo, sans-serif";
      ctx.textAlign = "center";
      ctx.lineWidth = 3 * S; ctx.strokeStyle = s.grande ? "#141414" : "#fff";
      ctx.fillStyle = s.grande ? "#ffcf3a" : accento;
      ctx.strokeText(s.testo, s.x, s.y); ctx.fillText(s.testo, s.x, s.y);
      ctx.restore();
    }
    disegnaCorsa();
  }

  // --- Il ciclo --------------------------------------------------------
  let ultimo = 0, riserva = 0, fotogramma = 0, richiesta = null;
  const PASSO_MS = 1000 / 60;

  function ciclo(adesso) {
    richiesta = null;
    if (document.hidden || fermo) return;
    if (!ultimo) ultimo = adesso;
    // Nella corsa si tiene il conto di quanto dura un fotogramma: se il telefono fatica, meno zombie insieme.
    if (corsa && corsa.chi && ultimo && adesso > ultimo) corsa.dtMedio = (corsa.dtMedio || 16.7) * 0.97 + Math.min(200, adesso - ultimo) * 0.03;
    riserva += Math.min(100, adesso - ultimo) * ritmo;
    ultimo = adesso;
    let giri = 0;
    // Un colpo secco ferma l'azione per qualche fotogramma: si sente di più.
    // Nella corsa, mentre si sceglie una carta o si apre un forziere, il tempo è fermo.
    if (corsa && corsa.pausa) riserva = 0;
    else if (fermoColpo > 0) { fermoColpo--; riserva = 0; }
    else {
      while (riserva >= PASSO_MS && giri < 4) { passo(); riserva -= PASSO_MS; giri++; }
      if (giri === 4) riserva = 0;
    }
    // Un disegno ogni due (30 fps); mentre se ne tiene uno in mano, tutti.
    if (presa.f || presa.tel || (fotogramma++ & 1) === 0) disegna();
    richiesta = requestAnimationFrame(ciclo);
  }
  function riparti() {
    if (fermo || richiesta || document.hidden) return;
    ultimo = 0; riserva = 0;
    richiesta = requestAnimationFrame(ciclo);
  }

  // Spegne il livello delle lotte: niente disegno, niente presa, niente
  // danni sulla striscia. Restano le notizie, l'orologio e i tasti.
  function spegni() {
    presa.f = null; presa.tel = null; appenaLanciato = false;
    radiceHtml("remove", "ring-trascina"); radiceHtml("remove", "ring-presa"); radiceHtml("remove", "ring-punta");
    radiale.giu = null; radiale.sopra = -2;
    ctx.clearRect(0, 0, W, H);
    if (tela.style) tela.style.display = "none";
    lottatori = []; telefoni = []; particelle = []; danni = []; scritte = []; evento = null;
    if (radiale.posto > 0) fattiInLa();              // spento, tendina e tasti tornano al loro posto
    creature = []; nubi = []; finale = null;
    proiettili = []; pezzi = [];
    gocce = []; spruzzi = []; bagnato = 0; piovendo = false; orda = null; sfida = null;
    if (sisma) fineSisma();
    lapilli = []; colate = []; meteore = []; sciame = null; bruciature = [];
    moltG = 1; ritmo = 1; mira = null; lampoMira = null; miraBuio = 0; centroMira = null;
    if (barra && barra.classList) barra.classList.remove("ultimora-guasta", "ultimora-colpita");
    if (faccina && faccina.classList) faccina.classList.remove("stordito");
  }
  function accendi() {
    if (tela.style) tela.style.display = "";
    avvia();
    riparti();
  }

  if (fermo) { dimensiona(); spegni(); } else { avvia(); riparti(); }

  let attesa = null;
  window.addEventListener("resize", () => {
    clearTimeout(attesa);
    attesa = setTimeout(() => {
      tara();
      if (fermo) return;
      dimensiona(); rileva();
      for (const f of lottatori) f.cx = Math.max(20 * S, Math.min(W - 20 * S, f.cx));
    }, 150);
  });
  if (window.visualViewport && window.visualViewport.addEventListener) {
    window.visualViewport.addEventListener("resize", () => window.dispatchEvent && window.dispatchEvent(new Event("resize")));
  }
  window.addEventListener("load", () => { if (!fermo) rileva(); });
  window.addEventListener("mut:tema", () => { leggiColori(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) riparti(); });

  // --- Le scommesse ------------------------------------------------------
  // Gettoni finti, salvati solo in questo browser. Si punta su chi vince il
  // prossimo K.O.; la quota segue il punteggio (chi sta perdendo paga di più).
  let gettoni = 100, scommessa = null, esito = "";
  try {
    const g = parseInt(deposito.getItem("mut-ring-gettoni"), 10);
    if (Number.isFinite(g) && g >= 0 && g < 1e7) gettoni = g;
  } catch (errore) { /* si parte da 100 */ }
  const altroTipo = (tipo) => (tipo === "robot" ? "mela" : "robot");
  const NOMI = { robot: "il robot", mela: "la mela" }, SU = { robot: "sul robot", mela: "sulla mela" };
  function quota(tipo) {
    const mio = (punteggio[tipo] || 0) + 1, suo = (punteggio[altroTipo(tipo)] || 0) + 1;
    return Math.max(1.3, Math.min(4, Math.round((1 + suo / mio) * 10) / 10));
  }
  function salvaGettoni() { try { deposito.setItem("mut-ring-gettoni", String(gettoni)); } catch (errore) { /* pazienza */ } }
  function scommetti(tipo, importo) {
    importo = Math.floor(Number(importo));
    if (scommessa || !(tipo in NOMI) || !(importo > 0) || importo > gettoni) return false;
    gettoni -= importo;
    scommessa = { su: tipo, importo, quota: quota(tipo) };
    esito = "Puntati " + importo + " gettoni " + (stile ? "su " + nomeProprio(tipo) : SU[tipo]) + " (×" + scommessa.quota + "): si decide al prossimo K.O.";
    salvaGettoni(); aggiornaPannello();
    return true;
  }
  function risolviScommessa(vincitore) {
    if (!scommessa) { aggiornaPannello(); return; }
    const sc = scommessa;
    scommessa = null;
    if (vincitore === sc.su) {
      const vinti = Math.round(sc.importo * sc.quota);
      gettoni += vinti;
      esito = "Vinto! Ha vinto " + (stile ? nomeProprio(vincitore) : NOMI[vincitore]) + ": +" + vinti + " gettoni.";
      const f = lottatori.find((l) => l.tipo === vincitore);
      if (f) scrivi("+" + vinti, f.p.testa.x, f.p.testa.y - 30 * S, true);
    } else {
      esito = "Perso: ha vinto " + (stile ? nomeProprio(vincitore) : NOMI[vincitore]) + ". Meno " + sc.importo + " gettoni.";
    }
    if (gettoni <= 0) esito += " Gettoni finiti: puoi ricaricarli.";
    salvaGettoni(); aggiornaPannello();
  }

  // --- I comandi della tendina ------------------------------------------
  function assicuraAcceso() {
    if (!fermo) return;
    fermo = false;
    try { deposito.setItem("mut-ring", "on"); } catch (errore) { /* pazienza */ }
    aggiornaTastoGioca(); accendi();
  }
  // Le mosse dei personaggi nuovi: lo stile a cui appartengono e l'azione che fanno partire.
  const MOSSE_STILE = { trasforma: ["guerrieri", "trasforma"],
                        dardi: ["maghi", "raffica"], gelo: ["maghi", "gelo"], rimpicciolisci: ["maghi", "rimpicciolisci"], fulmine: ["maghi", "fulmine"],
                        levita: ["maghi", "levita"], scudo: ["maghi", "barriera"], raggio: ["maghi", "onda"], sparizione: ["maghi", "teletrasporto"],
                        "scatto-lama": ["lame", "scattoLama"], "lancio-lama": ["lame", "lancioLama"], duello: ["lame", "duello"] };
  const MOSSE_TENDINA = { sfera: "sfera", disco: "disco", lampo: "lampo", barriera: "barriera", autodistruzione: "avvinghia", telecinesi: "telecinesi" };
  const comandi = {
    metti(forma) {
      if (corsa) return false;                                  // durante la corsa il pannello non tocca la lotta
      if (ARMI_PREMIO[forma] && !concesso("armi")) return false;
      assicuraAcceso();
      if (!lottatori.length) return;
      if (forma === "duo") {
        const m = lottatori.find((l) => l.tipo === "mela");
        if (m && !m.ko && !m.preso && !m.tenuto && !m.tel) { if (m.arma) lasciaArma(m); m.jet = 0; inizia(m, "estrai"); return; }
      }
      const cx = lottatori.reduce((t, l) => t + l.p.bacino.x, 0) / lottatori.length;
      const x = Math.max(40 * S, Math.min(W - 40 * S, cx + caso(-160, 160) * S));
      const t = faEntrare(forma, x, caso(-1, 1) * S);
      if (t.tipo === "bomba") t.miccia = 380;
    },
    gravita(v) {
      if (corsa) return false;                                  // durante la corsa il pannello non tocca la lotta
      if (String(v) !== "1" && !concesso("meteo")) return false;
      if (v === "su") {
        // Sottosopra: la gravità tira verso il tetto.
        assicuraAcceso();
        verso = -1; gravitaScelta = 1; moltG = 1;
        for (const f of lottatori) { f.jet = 0; f.caos = 0; f.paracadute = 0; f.scalata = null; f.inVolo = true; f.ko = Math.max(f.ko, 30); }
        return;
      }
      v = Number(v);
      if (!(v > 0 && v <= 2)) return;
      if (verso < 0) for (const f of lottatori) { f.inVolo = true; f.ko = Math.max(f.ko, 30); }
      verso = 1;
      gravitaScelta = v;
      if (!evento || evento.nome !== "luna") moltG = v;
    },
    imprevisto(nome, acceso) {
      if (corsa) return false;                                  // durante la corsa il pannello non tocca la lotta
      if (acceso && !concesso("meteo")) return false;
      if (acceso) assicuraAcceso();
      if (nome === "acquazzone") acquazzone = !!acceso;
      else if (nome === "natale") natale = !!acceso;
      else if (nome === "uragano") {
        uraganoFisso = !!acceso;
        uragano = acceso ? (uragano || { x: 100 * S, vx: 1.1 * S, t: 0 }) : null;
        if (!acceso && evento && evento.nome === "uragano") evento = null;
      } else if (nome === "rallenta") { rallentaFisso = !!acceso; ritmo = acceso ? 0.45 : 1; }
    },
    colpo(nome) {
      if (corsa) return false;                                  // durante la corsa il pannello non tocca la lotta
      const gruppo = MOSSE_PREMIO[nome] ? "guerrieri" : EVENTI_PREMIO[nome] ? "meteo" : nome.indexOf("esplodi-") === 0 ? "armi" : null;
      if (gruppo && !concesso(gruppo)) return false;
      assicuraAcceso();
      if (nome === "terremoto") avviaSisma();
      else if (nome === "buco") { if (buco) fineBuco(); else avviaBuco(); }
      else if (nome === "fatale") {
        // A comando: uno dei due, a caso, chiude l'altro appena sono in piedi tutti e due, vicini, sullo stesso piano.
        if (fatale) return;                                       // ce n'è già uno in scena
        fataleVoluto = 360 + (Math.random() < 0.5 ? 1 : 0);
        vogliaFatale();
      }
      else if (nome === "muta") {
        // Si trasformano tutti e due. Le forme dei personaggi a pagamento restano a pagamento.
        if (stile && !concesso("guerrieri")) return false;
        let qualcuno = false;
        for (const f of lottatori) {
          if (!f.p || f.ko || f.esploso || f.preso || f.tenuto || f.fuori || f.azione === "trasforma") continue;
          if (stile === "guerrieri" && f.potenziato > 0 && f.forma >= 2) continue;
          f.mutato = true; f.ki = 100; inizia(f, "trasforma"); qualcuno = true;
        }
        if (!qualcuno) return false;
      }
      else if (nome === "mira") {
        // La mira a comando: il primo in piedi apre la linea di tiro. Il secondo tocco spara.
        if (mira) { sparaMira(); return true; }
        const pronti = lottatori.filter((f) => f.p && !f.ko && !f.esploso && !f.preso && !f.tenuto);
        if (!pronti.length || !avviaMira(pronti[Math.floor(Math.random() * pronti.length)])) return false;
      }
      else if (nome === "meteoriti") avviaMeteore();
      else if (nome === "zombie") { if (orda) { if (orda.fase !== "festa") fineOrda(false); } else avviaOrda(0); }
      else if (nome === "jet") { for (const f of lottatori) if (!f.ko && !f.preso && !f.tenuto && !f.esploso) decolla(f, Math.random() < 0.4); }
      else if (nome === "telefoni") daSpawnare = 7;
      else if (nome === "furia") { const f = lottatori[Math.floor(Math.random() * lottatori.length)]; if (f) f.furia = 560; }
      else if (nome in MOSSE_TENDINA) {
        if (stile !== "guerrieri") { comandi.stile("guerrieri"); aggiornaInterruttori(); }
        const pronti = lottatori.filter((f) => !f.ko && !f.preso && !f.tenuto && !f.esploso && !(f.accecato > 0));
        const f = pronti[Math.floor(Math.random() * pronti.length)];
        if (!f) return;
        const altro = lottatori.find((l) => l !== f);
        f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        f.ki = 100; f.scatto = 0;
        inizia(f, MOSSE_TENDINA[nome]);
      }
      else if (nome === "scontro") {
        // Lo scontro di energie a comando: tutti e due a terra, carichi, uno di fronte all'altro.
        if (!anime) { comandi.stile("guerrieri"); aggiornaInterruttori(); }
        const [a, b] = lottatori;
        if (!a || !b || sfida || [a, b].some((f) => f.ko || f.preso || f.tenuto || f.esploso || f.fuori || !braccia(f) || gambe(f) === 0)) return;
        // Faccia a faccia sullo stesso piano, a una certa distanza: se serve compaiono lì.
        const o = a.supporto && a.supporto === b.supporto && a.supporto.r - a.supporto.l > 300 * S ? a.supporto : null;
        const base = o ? o.t : pavimento, l = (o ? o.l : 0) + 34 * S, r = (o ? o.r : W) - 34 * S, largo = Math.min(260 * S, r - l);
        const m = Math.max(l + largo / 2, Math.min(r - largo / 2, (a.p.bacino.x + b.p.bacino.x) / 2)), lato = a.p.bacino.x <= b.p.bacino.x ? -1 : 1;
        for (const [f, sgn] of [[a, lato], [b, -lato]]) {
          const lontani = Math.abs(a.p.bacino.x - b.p.bacino.x) >= 170 * S && !(f.jet > 0) && Math.abs(f.base - base) < 4 * S &&
            Math.abs(Math.max(f.p.piedeA.y, f.p.piedeD.y) - base) < 12 * S;
          if (lontani) continue;
          const x = m + sgn * largo / 2, dx = x - f.p.bacino.x, dy = base - 30 * S - f.p.bacino.y;
          zip(f.p.bacino.x, f.p.bacino.y, COLORI_ANIME[f.tipo]);
          for (const n in f.p) { f.p[n].x += dx; f.p[n].y += dy; f.p[n].ox = f.p[n].x; f.p[n].oy = f.p[n].y; }
          f.cx = x; f.base = base; f.supporto = o; f.inVolo = false; f.fantasma = false;
          zip(f.p.bacino.x, f.p.bacino.y, COLORI_ANIME[f.tipo]);
        }
        for (const f of [a, b]) {
          const altro = f === a ? b : a;
          f.jet = 0; f.scatto = 0; f.stordito = 0; f.accecato = 0; f.gelato = 0; f.ghiaccio = null; f.scalata = null; f.recupero = 0; f.paracadute = 0;
          f.ki = Math.max(f.ki, 45);
          f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
          inizia(f, "onda");
        }
      }
      else if (nome === "onda" || nome === "carica" || nome === "teletrasporto") {
        if (stile !== "guerrieri") { comandi.stile("guerrieri"); aggiornaInterruttori(); }
        const pronti = lottatori.filter((f) => !f.ko && !f.preso && !f.tenuto && !f.esploso);
        const f = pronti[Math.floor(Math.random() * pronti.length)];
        if (!f) return;
        const altro = lottatori.find((l) => l !== f);
        f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        if (nome === "onda") { f.ki = Math.max(f.ki, 45); f.jet = 0; inizia(f, "onda"); }
        else if (nome === "carica") { for (const l of pronti) { l.jet = 0; l.ki = Math.max(l.ki, 40); inizia(l, "carica"); } }
        else { f.ki = Math.max(f.ki, 15); teletrasporta(f, altro); }
      }
      else if (nome in MOSSE_STILE) {
        const [st, azione] = MOSSE_STILE[nome];
        if (stile !== st) { comandi.stile(st); aggiornaInterruttori(); }
        if (azione === "duello") { duello = 420; for (const f of lottatori) { f.jet = 0; f.pensa = Math.min(f.pensa, 4); if (f.lama && f.lama.lanciata) rientraLama(f); } return; }
        const pronti = lottatori.filter((f) => !f.ko && !f.preso && !f.tenuto && !f.esploso && !(f.accecato > 0) && !(f.gelato > 0) && (st !== "lame" || lamaPronta(f)));
        const f = pronti[Math.floor(Math.random() * pronti.length)];
        if (!f) return;
        const altro = lottatori.find((l) => l !== f);
        f.dir = altro.p.bacino.x >= f.p.bacino.x ? 1 : -1;
        f.ki = 100; f.scatto = 0; f.stordito = 0;
        if (st === "lame") f.jet = 0;
        if (azione === "teletrasporto") teletrasporta(f, altro);
        else inizia(f, azione);
      }
      else if (nome === "esplodi-robot" || nome === "esplodi-mela") {
        const tipo = nome.slice(8), f = lottatori.find((l) => l.tipo === tipo);
        if (f && !f.esploso) esplodiLottatore(f, lottatori.find((l) => l.tipo !== tipo));
      }
    },
    sorprese(acceso) { sorprese = !!acceso; },
    barre(acceso) {
      barreVita = !!acceso;
      try { deposito.setItem("mut-ring-barre", barreVita ? "on" : "off"); } catch (errore) { /* pazienza */ }
    },
    anime(acceso) { return comandi.stile(acceso ? "guerrieri" : (stile === "guerrieri" ? "" : stile)); },
    // Chi sono i due lottatori: "" i soliti, "guerrieri", "maghi", "lame".
    stile(nome) {
      if (corsa && corsa.fase !== "scelta") return false;        // nella corsa si sceglie solo all'inizio
      nome = STILI.indexOf(nome) >= 0 ? nome : "";
      if (nome && !concesso("guerrieri")) return false;
      if (nome) assicuraAcceso();
      const prima = stile;
      stile = nome;
      anime = stile === "guerrieri" || stile === "maghi";
      try {
        deposito.setItem("mut-ring-stile", stile);
        deposito.setItem("mut-ring-anime", stile === "guerrieri" ? "on" : "off");
      } catch (errore) { /* pazienza */ }
      // Personaggi nuovi: escono i vecchi, entrano quelli dello stile scelto.
      if (stile !== prima) cambiaCorpi();
      for (const f of lottatori) if (anime) f.ki = Math.max(f.ki, 50);
      if (stile && !barreVita) barreVita = true;
      aggiornaInterruttori();
    },
    cruento(acceso) {
      cruento = !!acceso;
      try { deposito.setItem("mut-ring-cruento", cruento ? "on" : "off"); } catch (errore) { /* pazienza */ }
      if (!cruento) { macchie = []; particelle = particelle.filter((q) => q.tipo !== "goccia"); }
    },
    ricomincia() {
      if (corsa) return false;
      assicuraAcceso();
      avvia();
      moltG = gravitaScelta; ritmo = rallentaFisso ? 0.45 : 1;
      if (uraganoFisso) uragano = { x: 100 * S, vx: 1.1 * S, t: 0 };
    },
    // La corsa infinita e la sua classifica (09/10/2026).
    corsa() { return apriCorsa(); },
    // L'audio (09/10/2026): spento finché non lo si accende.
    audio(si) { return accendiAudio(si === undefined ? !audio.acceso : !!si); },
    classifica(si) { apriClassifica(si === undefined ? !classifica.aperta : si); },
    scommetti, ricarica() { if (!scommessa && gettoni < 10) { gettoni = 100; esito = "Gettoni ricaricati."; salvaGettoni(); aggiornaPannello(); } },
  };

  if (tastoRadiale) {
    tastoRadiale.hidden = false;
    tastoRadiale.setAttribute("aria-pressed", radiale.aperto ? "true" : "false");
    tastoRadiale.addEventListener("click", () => { const apri = !radiale.aperto; if (apri) assicuraAcceso(); apriRadiale(apri); riparti(); });
  }
  // --- La tendina (si apre dal tasto col guantone) -----------------------
  const pannello = mio.querySelector("[data-pannello]");
  const tastoOpzioni = mio.querySelector("[data-opzioni]");
  const dentroPannello = (sel) => (pannello && pannello.querySelectorAll ? Array.from(pannello.querySelectorAll(sel)) : []);
  function aggiornaPannello() {
    if (!pannello || !pannello.querySelector) return;
    const g = pannello.querySelector("[data-gettoni]");
    if (g) g.textContent = String(gettoni);
    for (const b of dentroPannello("[data-quota]")) b.textContent = "×" + quota(b.getAttribute("data-quota"));
    for (const b of dentroPannello("[data-punta]")) b.disabled = !!scommessa || gettoni <= 0;
    const e = pannello.querySelector("[data-esito]");
    if (e) e.textContent = esito || (gettoni > 0 ? "Punta su chi vince il prossimo K.O." : "Gettoni finiti.");
    const r = pannello.querySelector("[data-ricarica]");
    if (r) r.hidden = !!scommessa || gettoni >= 10;
  }
  function aggiornaInterruttori() {
    if (!pannello || !pannello.querySelector) return;
    const b = pannello.querySelector("[data-barre]"), a = pannello.querySelector("[data-anime]");
    if (b) b.setAttribute("aria-pressed", String(barreVita));
    if (a) a.setAttribute("aria-pressed", String(stile === "guerrieri"));
    for (const t of dentroPannello("[data-stile]")) t.setAttribute("aria-pressed", String(stile === t.getAttribute("data-stile")));
    // Si vedono solo le mosse dei personaggi scelti.
    for (const g of dentroPannello("[data-mosse]")) g.hidden = g.getAttribute("data-mosse") !== stile;
    // Sui tasti delle scommesse, i nomi di chi è in campo.
    for (const n of dentroPannello("[data-nome]")) {
      if (n.vero === undefined) n.vero = n.textContent;
      const lato = n.getAttribute("data-nome"), nuovo = stile ? (lato === "robot" ? "\uD83D\uDD35 " : "\uD83D\uDFE3 ") + nomeProprio(lato) : n.vero;
      if (n.textContent !== nuovo) n.textContent = nuovo;
    }
    const nota = pannello.querySelector("[data-mosse-nota]");
    if (nota) nota.hidden = !!stile;
  }
  function apriPannello(apri) {
    if (!pannello || !tastoOpzioni) return;
    pannello.classList.toggle("aperto", apri);
    tastoOpzioni.setAttribute("aria-expanded", apri ? "true" : "false");
    if (apri) aggiornaPannello();
  }
  if (pannello && tastoOpzioni) {
    pannello.hidden = false;
    tastoOpzioni.hidden = false;
    tastoOpzioni.addEventListener("click", () => apriPannello(!pannello.classList.contains("aperto")));
    const chiudi = pannello.querySelector("[data-chiudi]");
    if (chiudi) chiudi.addEventListener("click", () => { apriPannello(false); tastoOpzioni.focus(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && pannello.classList.contains("aperto")) { apriPannello(false); tastoOpzioni.focus(); } });
    for (const b of dentroPannello("[data-metti]")) b.addEventListener("click", () => comandi.metti(b.getAttribute("data-metti")));
    for (const b of dentroPannello("[data-colpo]")) b.addEventListener("click", () => comandi.colpo(b.getAttribute("data-colpo")));
    // La corsa si gioca sul canvas: il pannello si chiude, sennò la copre.
    for (const b of dentroPannello("[data-corsa]")) b.addEventListener("click", () => { apriPannello(false); comandi.corsa(); });
    for (const b of dentroPannello("[data-audio]")) { b.setAttribute("aria-pressed", audio.acceso ? "true" : "false"); b.addEventListener("click", () => comandi.audio()); }
    for (const b of dentroPannello("[data-classifica]")) {
      if (!sulSito) b.hidden = true;                             // l'estensione non manda e non chiede niente a nessuno
      else b.addEventListener("click", () => { apriPannello(false); comandi.classifica(true); });
    }
    for (const b of dentroPannello("[data-imprevisto]")) {
      b.addEventListener("click", () => {
        const acceso = b.getAttribute("aria-pressed") !== "true";
        b.setAttribute("aria-pressed", acceso ? "true" : "false");
        if (comandi.imprevisto(b.getAttribute("data-imprevisto"), acceso) === false) b.setAttribute("aria-pressed", "false");
      });
    }
    const gravita = pannello.querySelector("[data-gravita]");
    if (gravita) gravita.addEventListener("change", () => { if (comandi.gravita(gravita.value) === false) gravita.value = "1"; });
    const sorp = pannello.querySelector("[data-sorprese]");
    if (sorp) sorp.addEventListener("click", () => { const a = sorp.getAttribute("aria-pressed") !== "true"; sorp.setAttribute("aria-pressed", String(a)); comandi.sorprese(a); });
    const crue = pannello.querySelector("[data-cruento]");
    if (crue) {
      crue.setAttribute("aria-pressed", String(cruento));
      crue.addEventListener("click", () => { const a = crue.getAttribute("aria-pressed") !== "true"; crue.setAttribute("aria-pressed", String(a)); comandi.cruento(a); });
    }
    for (const [sel, nome] of [["[data-barre]", "barre"], ["[data-anime]", "anime"]]) {
      const b = pannello.querySelector(sel);
      if (b) b.addEventListener("click", () => { const a = b.getAttribute("aria-pressed") !== "true"; comandi[nome](a); aggiornaInterruttori(); });
    }
    for (const b of dentroPannello("[data-stile]")) {
      b.addEventListener("click", () => { const s = b.getAttribute("data-stile"); comandi.stile(stile === s ? "" : s); aggiornaInterruttori(); });
    }
    aggiornaInterruttori();
    const ric = pannello.querySelector("[data-ricomincia]");
    if (ric) ric.addEventListener("click", () => comandi.ricomincia());
    const importo = pannello.querySelector("[data-importo]");
    for (const b of dentroPannello("[data-punta]")) {
      b.addEventListener("click", () => {
        let v = importo ? importo.value : "25";
        if (v === "tutto") v = gettoni;
        if (!scommetti(b.getAttribute("data-punta"), Math.min(Number(v), gettoni))) aggiornaPannello();
      });
    }
    const ricarica = pannello.querySelector("[data-ricarica]");
    if (ricarica) ricarica.addEventListener("click", () => comandi.ricarica());
    aggiornaPannello();
    segnaBloccati();
    if (premio && premio.ascolta) premio.ascolta(segnaBloccati);
  }
  // I tasti delle funzioni a pagamento portano il lucchetto finché Premium non
  // è attivo; se Premium viene tolto, quello che era acceso si spegne.
  function segnaBloccati() {
    if (!premio || !pannello) return;
    for (const b of dentroPannello("[data-metti], [data-colpo], [data-anime], [data-stile], [data-imprevisto]")) {
      const g = gruppoDi(b);
      b.classList.toggle("bloccato", !!g && !libero(g));
    }
    if (!libero("guerrieri") && stile) { comandi.stile(""); aggiornaInterruttori(); }
    if (!libero("meteo")) {
      for (const b of dentroPannello("[data-imprevisto]")) {
        if (b.getAttribute("aria-pressed") === "true") { b.setAttribute("aria-pressed", "false"); comandi.imprevisto(b.getAttribute("data-imprevisto"), false); }
      }
      const gravita = pannello.querySelector("[data-gravita]");
      if (gravita && gravita.value !== "1") { gravita.value = "1"; comandi.gravita("1"); }
      else if (verso < 0 || gravitaScelta !== 1) comandi.gravita("1");
    }
  }

  // Per i test nel browser: lo stato del ring, in sola lettura.
  // ·· LA CORSA INFINITA (09/10/2026, chiesta da Riccardo; rifatta la sera stessa) ··
  // Una modalità vera, dal menu del ring. Si sceglie un personaggio e si lotta
  // da soli, un round dopo l'altro, finché restano vite. La prima versione si
  // fermava a ogni round per un premio e un negozio; Riccardo: «vorrei che
  // l'azione sia sempre crescente come un endless run, in modo da rilasciare
  // dopamina costante». Le sue scelte: round senza respiro, armi automatiche,
  // forzieri dai capi, corsa davvero infinita. Quindi:
  //  - I ROUND si susseguono con uno stacco di un secondo e mezzo, niente menu.
  //    Ognuno è più grande del precedente: più zombie, più insieme, più duri.
  //    Tipi a sorte: ondata, duello, sopravvivenza a tempo, ondata col capo.
  //  - LE GEMME. Ogni nemico abbattuto lascia una gemma; passandoci vicino la
  //    calamita la tira all'eroe. Ogni livello ferma il gioco un attimo e offre
  //    tre carte: un'arma nuova, un livello in più per un'arma, un potenziamento,
  //    o un'evoluzione.
  //  - LE ARMI AUTOMATICHE colpiscono da sole mentre l'eroe lotta: telefoni in
  //    orbita, onda d'urto, fulmine, aura di fuoco, dardi, lama rotante. Cinque
  //    livelli ciascuna; al quinto, con il potenziamento abbinato, l'evoluzione.
  //    Si parte con l'arma della propria famiglia di personaggi.
  //  - I FORZIERI li lasciano il capo e l'avversario del duello: uno o tre premi.
  //  - A TERRA cadono monete e, ogni tanto, oggetti che riempiono i tre posti.
  //  - LE MONETE restano fra una corsa e l'altra (nel browser) e si spendono
  //    nella bottega, nella schermata di scelta: potenziamenti permanenti.
  //  - TRE VITE che non tornano. Persa l'ultima si resta in piedi feriti e
  //    lenti; il colpo finale si ricarica piano, e se va a segno salva il round
  //    e ridà una vita. Se si va giù di nuovo, è finita.
  //  - CLASSIFICA: a fine corsa, sul sito, nome e punteggio. L'estensione non
  //    manda niente a nessuno: tiene il record nel browser e basta.
  // Il compagno che non lotta sta «in panchina»: fuori campo, come chi è dentro
  // il buco nero, e torna solo per i duelli, da avversario.
  const CORSA = { vite: 3, viteMax: 5, hp: 100, ultima: 0.3, lento: 0.55, energia: 100, perUcciso: 4, perColpo: 5, ricarica: 0.12,
                  intro: 90, vinto: 60, invulnerabile: 110, cura: 0.06, tempo: [30, 40], calamita: 70, maxGemme: 140, maxZombie: 34 };
  const TIPI_ROUND = { ondata: ["\u{1F9DF}", "Ondata"], duello: ["⚔️", "Duello"], tempo: ["⏱️", "Sopravvivenza"], boss: ["\u{1F480}", "Il capo"] };
  // I potenziamenti che escono a ogni livello. `abbinata` delle armi indica quale serve per l'evoluzione.
  const POTERI = {
    cuore: { icona: "❤️", nome: "Cuore d'acciaio", max: 5, testo: () => "+15 " + dici("vita massima") },
    forza: { icona: "\u{1F44A}", nome: "Pugni pesanti", max: 5, testo: () => "+15% " + dici("danni") },
    velocita: { icona: "\u{1F45F}", nome: "Passo svelto", max: 3, testo: () => "+12% " + dici("velocità") },
    pelle: { icona: "\u{1F6E1}️", nome: "Pelle dura", max: 4, testo: () => "-10% " + dici("danni presi") },
    carica: { icona: "\u{1F50B}", nome: "Energia", max: 3, testo: () => dici("Colpo finale più in fretta") },
    mira: { icona: "\u{1F3AF}", nome: "Occhio fermo", max: 3, testo: () => dici("La mira gira più piano") },
    sete: { icona: "\u{1FA78}", nome: "Sete", max: 3, testo: () => "+1 " + dici("vita per ogni nemico") },
    tasche: { icona: "\u{1FA99}", nome: "Tasche piene", max: 3, testo: () => dici("Più monete a terra") },
    calamita: { icona: "\u{1F9F2}", nome: "Calamita", max: 4, testo: () => dici("Raccogli da più lontano") },
    ricarica: { icona: "⏳", nome: "Ricarica", max: 4, testo: () => dici("Armi più rapide") },
    area: { icona: "⭕", nome: "Area", max: 4, testo: () => dici("Armi più grandi") },
  };
  const ARMI_CORSA = {
    orbita: { icona: "\u{1F4F1}", nome: "Telefoni in orbita", abbinata: "velocita", evo: "Stormo di telefoni", testi: ["Telefoni che girano intorno e colpiscono", "+1 telefono", "Più veloci", "+1 telefono", "Più larghi e più forti"] },
    onda: { icona: "\u{1F4AB}", nome: "Onda d'urto", abbinata: "cuore", evo: "Onda gigante", testi: ["Un'onda parte da te e spinge via tutti", "Più spesso", "Più larga", "Più forte", "Più spesso e più larga"] },
    fulmine: { icona: "⚡", nome: "Fulmine", abbinata: "carica", evo: "Tempesta", testi: ["Un fulmine cade su un nemico", "+1 fulmine", "Più spesso", "+1 fulmine", "+2 fulmini"] },
    aura: { icona: "\u{1F525}", nome: "Aura di fuoco", abbinata: "pelle", evo: "Inferno", testi: ["Brucia chi ti sta vicino", "Più larga", "Più forte", "Più larga", "Più forte e più rapida"] },
    dardi: { icona: "✨", nome: "Dardi", abbinata: "mira", evo: "Pioggia di dardi", testi: ["Dardi che cercano il nemico più vicino", "Più spesso", "+1 dardo", "Passano attraverso", "+1 dardo"] },
    lama: { icona: "\u{1F300}", nome: "Lama rotante", abbinata: "forza", evo: "Doppia lama", testi: ["Una lama lanciata che torna indietro", "Più lontano", "Più forte", "Più spesso", "Più grande"] },
  };
  // L'arma con cui si parte: quella della propria famiglia di personaggi.
  const ARMA_DI_PARTENZA = { "": { robot: "dardi", mela: "orbita" }, guerrieri: { robot: "onda", mela: "onda" }, maghi: { robot: "fulmine", mela: "fulmine" }, lame: { robot: "lama", mela: "lama" } };
  // Gli oggetti che cadono a terra e vanno nei tre posti (la calamita si usa subito).
  const OGGETTI = {
    pozione: { icona: "\u{1F9EA}", nome: "Pozione", peso: 3, testo: "Metà vita subito" },
    scudo: { icona: "\u{1F6E1}️", nome: "Scudo", peso: 1.5, testo: "Niente danni per sei secondi" },
    bomba: { icona: "\u{1F4A3}", nome: "Bomba", peso: 2, testo: "Scoppia intorno a te" },
    gelo: { icona: "❄️", nome: "Gelo", peso: 1.5, testo: "Ferma tutti i nemici" },
    carica: { icona: "\u{1F50B}", nome: "Carica", peso: 1, testo: "Colpo finale pronto" },
    calamita: { icona: "\u{1F9F2}", nome: "Calamita", peso: 2, testo: "Tira a te tutte le gemme" },
    bazooka: { icona: "\u{1F680}", nome: "Bazooka", peso: 0.8, testo: "Due razzi" },
    lanciafiamme: { icona: "\u{1F525}", nome: "Lanciafiamme", peso: 0.8, testo: "Tre fiammate" },
  };
  // La bottega: potenziamenti permanenti, pagati con le monete di tutte le corse.
  const BOTTEGA = {
    vita: { icona: "❤️", nome: "Più vita", max: 5, costo: 50, testo: "+10 vita all'inizio" },
    forza: { icona: "\u{1F44A}", nome: "Più forza", max: 5, costo: 70, testo: "+6% danni" },
    pelle: { icona: "\u{1F6E1}️", nome: "Corazza", max: 3, costo: 90, testo: "-5% danni presi" },
    calamita: { icona: "\u{1F9F2}", nome: "Calamita", max: 3, costo: 60, testo: "Raccogli da più lontano" },
    ricarica: { icona: "⏳", nome: "Ricarica", max: 3, costo: 110, testo: "Armi più rapide" },
    fortuna: { icona: "\u{1F340}", nome: "Fortuna", max: 3, costo: 100, testo: "Forzieri più ricchi, più oggetti" },
    avidita: { icona: "\u{1F4B0}", nome: "Avidità", max: 5, costo: 80, testo: "+10% monete" },
    rinascita: { icona: "\u{1F496}", nome: "Rinascita", max: 1, costo: 600, testo: "Si parte con una vita in più" },
  };
  const costoBottega = (id) => Math.round(BOTTEGA[id].costo * Math.pow(1.6, bottega[id] || 0));
  const IMPREVISTI_CORSA = { luna: ["\u{1F319}", "Gravità lunare"], pioggia: ["\u{1F4F1}", "Pioggia di telefoni"], terremoto: ["\u{1F30B}", "Terremoto"],
                            meteoriti: ["☄️", "Meteoriti"], buco: ["\u{1F573}️", "Buco nero"], temporale: ["⛈️", "Temporale"],
                            jet: ["\u{1F680}", "Jetpack impazziti"], uragano: ["\u{1F32A}️", "Uragano"] };
  // Il danno di un morso, prima della pelle dura e della crescita a ogni round.
  const MORSO_CORSA = { lento: 6, svelto: 5, striscia: 5, gonfio: 6, grosso: 15, corazzato: 8, rabbioso: 6, capo: 20 };
  const PUNTI_ZOMBIE = { lento: 10, svelto: 10, striscia: 10, gonfio: 12, grosso: 30, corazzato: 20, rabbioso: 20, capo: 300 };
  const GEMMA_ZOMBIE = { lento: 1, svelto: 1, striscia: 1, gonfio: 2, grosso: 4, corazzato: 3, rabbioso: 2, capo: 25 };
  const PERSONAGGI_CORSA = [["", "Classici"], ["guerrieri", "Super guerrieri"], ["maghi", "Maghi"], ["lame", "Duellanti"]];
  const eroe = () => (corsa && corsa.chi ? lottatori.find((l) => l.tipo === corsa.chi) || null : null);
  const nemicoCorsa = () => (corsa && corsa.chi ? lottatori.find((l) => l.tipo !== corsa.chi) || null : null);
  const eDellaCorsa = (f) => !!(corsa && corsa.chi && f && f.tipo === corsa.chi);
  const livello = (id) => (corsa && corsa.livelli[id]) || 0;
  const forzaCorsa = () => (1 + 0.15 * livello("forza")) * (1 + 0.06 * (bottega.forza || 0));
  // I danni presi crescono a ogni round e, dal decimo, sempre più in fretta: infinita sì, ma prima o poi si cade.
  const crescita = () => { const r = corsa ? corsa.round : 1; return 1 + 0.06 * Math.max(0, r - 1) + 0.02 * Math.pow(Math.max(0, r - 10), 1.5); };
  const pelleCorsa = () => (1 - 0.1 * livello("pelle")) * (1 - 0.05 * (bottega.pelle || 0));
  const areaCorsa = () => 1 + 0.12 * livello("area");
  const ricaricaCorsa = () => (1 - 0.08 * livello("ricarica")) * (1 - 0.04 * (bottega.ricarica || 0));
  const raggioCalamita = () => CORSA.calamita * S * (1 + 0.4 * livello("calamita") + 0.25 * (bottega.calamita || 0));
  const nomeDi = (tipo) => (stile ? nomeProprio(tipo) : dici(tipo === "robot" ? "Robot" : "Mela"));
  const xpPerLivello = (l) => Math.round(5 + 4 * l + Math.pow(l, 1.55));
  function salvaBottega() {
    try { deposito.setItem("mut-ring-banca", String(banca)); deposito.setItem("mut-ring-bottega", JSON.stringify(bottega)); } catch (errore) { /* pazienza */ }
  }

  // In panchina: fuori campo, fermo, niente in mano.
  function panchina(f) {
    if (!f) return;
    if (f.tel) lasciaCadere(f);
    if (f.arma) lasciaArma(f);
    if (f.tiene) molla(f);
    Object.assign(f, { fuoriCampo: true, panchina: true, azione: null, ordine: null, onda: null, sfera: null, jet: 0, scatto: 0, furia: 0, coppia: null,
                       fuga: null, ko: 0, stordito: 0, gelato: 0, ghiaccio: null, potenziato: 0, forma: 0, koVero: false, accecato: 0, tenuto: null, preso: null });
  }
  // Un corpo nuovo, in piedi dove si vuole: si sostituisce nel ring a quello di prima.
  function corpoNuovo(tipo, x, dir, base) {
    const i = lottatori.findIndex((l) => l.tipo === tipo);
    const f = crea(tipo, x, dir, base);
    if (lame()) accendiLama(f);
    if (anime) f.ki = 50;
    if (i >= 0) lottatori[i] = f;
    return f;
  }
  function daiArma(f, forma) {
    if (!f || !f.p) return;
    const t = nuovoTelefono(f.p.manoA.x, f.p.manoA.y, 0, 0, forma);
    if (f.arma) lasciaArma(f);
    t.stato = "impugnato"; t.da = f; f.arma = t; f.colpiArma = CARICHE[forma] || 5;
  }

  // ·· Aprire, scegliere, chiudere ··
  function apriCorsa() {
    if (corsa) { if (corsa.fase === "lotta" || corsa.fase === "intro" || corsa.fase === "vinto") finisciCorsa(); return true; }
    assicuraAcceso();
    const prima = { sorprese, acquazzone, uraganoFisso, rallentaFisso, verso, gravita: gravitaScelta, radiale: radiale.aperto, chi: radiale.chi };
    sorprese = false; acquazzone = false; uraganoFisso = false; rallentaFisso = false; uragano = null; verso = 1; gravitaScelta = 1;
    comandi.ricomincia();                                         // un ring pulito (prima di accendere la corsa: dopo è bloccato)
    corsa = { fase: "scelta", t: 0, chi: null, prima };
    prossimoEvento = 1e9; prossimaOrda = 1e9; fataleRound = false; fataleDebito = 0; fataleVoluto = 0;
    aggiornaInterruttori();
    riparti();
    return true;
  }
  function scegliEroe(tipo) {
    if (!corsa || corsa.fase !== "scelta" || corsa.bottega || (tipo !== "robot" && tipo !== "mela")) return false;
    const seme = corsa.semeVoluto || Math.floor(Math.random() * 1e9) + 1;
    // Classici e duellanti non hanno l'energia delle onde: partono con più vita.
    const hp0 = (anime ? CORSA.hp : CORSA.hp + 20) + 10 * (bottega.vita || 0);
    Object.assign(corsa, {
      chi: tipo, stile, seme, rng: generatore(seme), round: 0, tipo: null, tipi: [], vite: CORSA.vite + (bottega.rinascita || 0), energia: 30,
      hp: hp0, hpMax: hp0, ultima: false, salvezze: 0, monete: 0, punti: 0, uccisi: 0, livelli: {}, slot: [null, null, null],
      liv: 1, xp: 0, daScegliere: 0, scelta: null, forziere: null, pausa: false, armi: {}, armiT: {},
      gemme: [], aTerra: [], forzieri: [], onde: [], saette: [], dardi: [], lame: [], numeri: [],
      invuln: 0, scudo: 0, imprevisti: [], prossimoImprevisto: 0, nemicoGiu: false, iniziata: Date.now(), danniRound: 0, inviato: false, nome: "",
    });
    try { corsa.nome = deposito.getItem("mut-ring-nome") || ""; } catch (errore) { /* niente nome */ }
    corsa.armi[(ARMA_DI_PARTENZA[stile] || ARMA_DI_PARTENZA[""])[tipo]] = 1;
    panchina(nemicoCorsa());
    const f = eroe();
    f.dir = 1; f.pensa = 20; f.danni = 0; f.soglia = 99;
    radiale.chi = tipo;
    if (!radiale.aperto) apriRadiale(true);
    scrivi(nomeDi(tipo) + "!", f.p.bacino.x, f.base - 90 * S, true);
    nuovoRound();
    return true;
  }
  // Fine della corsa: il riepilogo, il record, le monete in banca, il nome per la classifica.
  function finisciCorsa() {
    if (!corsa || corsa.fase === "fine" || !corsa.chi) return;
    if (mira) chiudiMira(false);
    corsa.fase = "fine"; corsa.t = 0; corsa.pausa = false; corsa.scelta = null; corsa.forziere = null;
    suona("fine");
    if (orda && orda.fase !== "festa") fineOrda(false);
    const n = nemicoCorsa();
    if (n && !n.panchina) panchina(n);
    corsa.inBanca = Math.round(corsa.monete * (1 + 0.1 * (bottega.avidita || 0)));
    banca += corsa.inBanca; salvaBottega();
    if (corsa.punti > recordCorsa) {
      recordCorsa = corsa.punti; corsa.record = true;
      try { deposito.setItem("mut-ring-corsa", String(recordCorsa)); } catch (errore) { /* pazienza */ }
    }
    if (sulSito) { caricaClassifica(); mostraNome(true); }
  }
  // Fuori dalla corsa: si torna al ring di sempre, com'era prima.
  function chiudiCorsa() {
    if (!corsa) return;
    const p = corsa.prima;
    mostraNome(false);
    if (mira) chiudiMira(false);
    corsa = null;
    sorprese = p.sorprese; acquazzone = p.acquazzone; uraganoFisso = p.uraganoFisso; rallentaFisso = p.rallentaFisso; gravitaScelta = p.gravita; verso = p.verso;
    radiale.chi = p.chi;
    if (radiale.aperto !== p.radiale) apriRadiale(p.radiale);
    comandi.ricomincia();
    aggiornaInterruttori();
  }
  function ricominciaCorsa() {
    if (!corsa) return;
    const prima = corsa.prima;
    mostraNome(false);
    corsa = null;
    apriCorsa();
    corsa.prima = prima;
  }
  // La bottega: si apre dalla schermata di scelta.
  function compraBottega(id) {
    if (!BOTTEGA[id] || (bottega[id] || 0) >= BOTTEGA[id].max) return false;
    const prezzo = costoBottega(id);
    if (banca < prezzo) return false;
    banca -= prezzo; bottega[id] = (bottega[id] || 0) + 1;
    salvaBottega(); suona("moneta");
    return true;
  }

  // ·· I round ··
  function scegliTipoRound(n) {
    if (corsa.prossimoTipo) { const t = corsa.prossimoTipo; corsa.prossimoTipo = null; return t; }
    if (n === 1) return "ondata";
    const prima = corsa.tipo, r = corsa.rng;
    const voci = [[5, "ondata"], [prima === "duello" ? 0 : 2, "duello"], [n >= 3 && prima !== "tempo" ? 2.4 : 0, "tempo"], [n >= 3 && prima !== "boss" ? 2.2 : 0, "boss"]];
    let tot = 0; for (const v of voci) tot += v[0];
    let x = r() * tot;
    for (const v of voci) if ((x -= v[0]) <= 0) return v[1];
    return "ondata";
  }
  function nuovoRound() {
    const c = corsa;
    c.round++;
    c.tipo = scegliTipoRound(c.round);
    c.tipi.push(c.tipo);
    c.fase = "intro"; c.t = 0; c.nemicoGiu = false; c.danniRound = 0; c.variante = null; c.scadenza = 0;
    // Un po' di fiato fra un round e l'altro (le vite, quelle, non tornano).
    if (!c.ultima) c.hp = Math.min(c.hpMax, c.hp + Math.round(c.hpMax * CORSA.cura));
    // Gli imprevisti: dal secondo round, sempre più spesso.
    c.imprevisti = []; c.lanciati = 0;
    const quanti = c.round < 2 ? 0 : c.rng() < Math.min(0.75, 0.25 + 0.06 * c.round) ? (c.round >= 6 && c.rng() < 0.4 ? 2 : 1) : 0;
    const nomi = Object.keys(IMPREVISTI_CORSA);
    while (c.imprevisti.length < quanti) {
      const nome = nomi[Math.floor(c.rng() * nomi.length)];
      if (c.imprevisti.indexOf(nome) < 0 && !(nome === "buco" && c.tipo === "duello")) c.imprevisti.push(nome);
    }
    c.prossimoImprevisto = 200;
    if (c.tipo === "duello") c.variante = scegliVariante(c.round);
    suona("via");
  }
  function scegliVariante(n) {
    const r = corsa.rng, v = [];
    const voci = ["furioso", "armato"].concat(stile === "maghi" || n < 6 ? [] : ["gigante"]);
    if (n >= 3) v.push(voci[Math.floor(r() * voci.length)]);
    if (n >= 9) { const altra = voci.filter((x) => v.indexOf(x) < 0); v.push(altra[Math.floor(r() * altra.length)]); }
    return v;
  }
  function iniziaLotta() {
    const c = corsa;
    c.fase = "lotta"; c.t = 0;
    // L'orda del round prima può essere ancora nella sua festa: via, sennò il round nuovo risulterebbe già vinto
    // (e nel duello la tregua dell'orda impedirebbe ai due di colpirsi).
    if (orda) { orda = null; for (const l of lottatori) { l.zMira = null; l.cinque = false; } }
    if (c.tipo === "duello") { entraNemico(); return; }
    let ricetta = ricettaCorsa(c.round, c.tipo === "tempo" ? 2 : 1);
    if (c.tipo === "tempo") {
      ricetta.insieme = Math.min(CORSA.maxZombie, ricetta.insieme + 4);
      c.scadenza = Math.round((CORSA.tempo[0] + c.rng() * (CORSA.tempo[1] - CORSA.tempo[0])) * 60);
    }
    if (c.tipo === "boss") {
      // Il capo arriva a metà dell'ondata, in mezzo agli altri.
      ricetta.coda.splice(Math.floor(ricetta.coda.length * 0.4), 0, { tipo: "capo", lato: c.rng() < 0.5 ? -1 : 1, attesa: 60 });
      ricetta.totale = ricetta.coda.length;
    }
    avviaOrda(1, Math.floor(c.rng() * 1e9) + 1);
    if (orda) { orda.corsa = ricetta; orda.pausa = 10; }
  }
  // La ricetta di un round: sempre più zombie, più insieme, più varianti. Si
  // incollano le ricette del ring libero finché non si arriva al totale.
  function ricettaCorsa(n, molt) {
    const totale = Math.round((8 + 4.5 * n) * (molt || 1));
    const R = ricettaOndata(Math.min(14, n), corsa.rng);
    for (let k = 1; R.coda.length < totale && k < 12; k++) R.coda = R.coda.concat(ricettaOndata(Math.min(14, n + k), corsa.rng).coda);
    R.coda = R.coda.slice(0, Math.min(140, totale));
    R.insieme = Math.min(CORSA.maxZombie, 6 + 2 * n);
    const pc = Math.min(0.45, 0.06 * (n - 1)), pr = Math.min(0.5, 0.07 * (n - 1));
    for (const v of R.coda) {
      v.attesa = Math.max(4, Math.round(v.attesa * 0.55));
      if (v.tipo === "lento" && corsa.rng() < pc) v.tipo = "corazzato";
      else if ((v.tipo === "svelto" || v.tipo === "striscia") && corsa.rng() < pr) v.tipo = "rabbioso";
    }
    R.coda[0].attesa = 10;
    R.totale = R.coda.length;
    return R;
  }
  // Il duello: l'altro personaggio entra dal lato opposto, potenziato a seconda del round.
  function entraNemico() {
    const c = corsa, f = eroe(), tipo = c.chi === "robot" ? "mela" : "robot";
    const lato = f.p.bacino.x < W / 2 ? 1 : -1;
    const x = Math.max(60 * S, Math.min(W - 60 * S, f.p.bacino.x + lato * Math.min(320 * S, W * 0.35)));
    const n = corpoNuovo(tipo, x, -lato, f.base);
    n.supporto = f.supporto;
    const v = c.variante || [];
    n.soglia = Math.round((6 + 0.9 * c.round) * (v.indexOf("gigante") >= 0 ? 1.4 : 1) * (v.length > 1 ? 1.15 : 1));
    n.danni = 0; n.pensa = 30; n.dir = -lato; n.cdArmi = {};
    if (v.indexOf("furioso") >= 0) n.furia = 1e7;
    if (v.indexOf("armato") >= 0) { daiArma(n, c.round >= 6 ? "lanciafiamme" : "bazooka"); n.riarma = 900; }
    if (v.indexOf("gigante") >= 0) { potenzia(n); n.potenziato = 1e7; if (stile === "guerrieri") n.forma = 1; }
    if (anime) n.ki = 60;
    for (let i = 0; i < 18 && particelle.length < MAX_PARTICELLE; i++) particelle.push({ tipo: "scintilla", x: x + caso(-20, 20) * S, y: f.base - caso(0, 80) * S, vx: caso(-2, 2) * S, vy: -caso(0.5, 3) * S, vita: 24, max: 24, colore: "#ffffff" });
    polvere(x, f.base - 1, 8);
    scrivi(nomeNemico(), x, f.base - 96 * S, true);
  }
  // La mela (e le sue versioni) è femmina: «Mela furiosa», «Brasa armata».
  const VARIANTI_F = { furioso: "furiosa", armato: "armata", gigante: "gigante" };
  const conVariante = (tipo, v) => nomeDi(tipo) + (v.length ? " " + v.map((x) => dici(tipo === "mela" ? VARIANTI_F[x] : x)).join(" ") : "");
  function nomeNemico() {
    const n = nemicoCorsa();
    return n ? conVariante(n.tipo, (corsa && corsa.variante) || []) : "";
  }
  function vinciRound(come) {
    const c = corsa;
    if (!c || c.fase !== "lotta") return;
    c.fase = "vinto"; c.t = 0;
    if (mira) chiudiMira(false);
    if (orda && orda.fase !== "festa") fineOrda(true);
    const punti = 50 * c.round + (c.danniRound === 0 ? 50 * c.round : 0);
    c.punti += punti;
    suona(come === "salvezza" ? "salvo" : "vittoria");
    if (come === "salvezza") {
      c.ultima = false; c.vite = 1; c.hp = Math.round(c.hpMax * 0.5); c.salvezze++;
      scrivi("SALVO!", eroe().p.bacino.x, eroe().base - 120 * S, true);
    }
    c.ultimoPremio = { punti, pulito: c.danniRound === 0 };
    const f = eroe();
    if (f && !f.ko && !f.esploso) { f.azione = null; f.daBallare = c.tipo === "duello"; f.pensa = 20; }
  }
  // Fra un round e l'altro: l'avversario esce, e si riparte.
  function prossimoRound() {
    const n = nemicoCorsa();
    if (n && !n.panchina) { polvere(n.p.bacino.x, n.base - 1, 6); panchina(n); }
    nuovoRound();
  }

  // ·· Gemme, monete, oggetti, forzieri ··
  function lasciaGemma(x, y, valore, tipo) {
    const c = corsa, base = orda ? orda.base : (eroe() ? eroe().base : pavimento);
    if (tipo === "gemma" && c.gemme.length >= CORSA.maxGemme) { daiEsperienza(valore); return; }      // troppe a terra: valgono subito
    c.gemme.push({ x, y, vx: caso(-1.4, 1.4) * S, vy: -caso(1.5, 3.5) * S, base, valore, tipo: tipo || "gemma", t: 0, tirata: false });
  }
  function lasciaOggetto(x, y, id) {
    corsa.aTerra.push({ id, x, y, vy: -3 * S, base: orda ? orda.base : (eroe() ? eroe().base : pavimento), t: 0 });
  }
  function oggettoCorsa() {
    let tot = 0; for (const id in OGGETTI) tot += OGGETTI[id].peso;
    let x = corsa.rng() * tot;
    for (const id in OGGETTI) if ((x -= OGGETTI[id].peso) <= 0) return id;
    return "pozione";
  }
  function daiEsperienza(v) {
    const c = corsa;
    c.xp += v;
    while (c.xp >= xpPerLivello(c.liv)) { c.xp -= xpPerLivello(c.liv); c.liv++; c.daScegliere++; c.punti += 20 * c.liv; }
  }
  // Le carte di un livello: armi nuove, livelli delle armi, evoluzioni, potenziamenti.
  function carteLivello(quante) {
    const c = corsa, pesi = [];
    const mie = Object.keys(c.armi);
    for (const id in ARMI_CORSA) {
      const l = c.armi[id] || 0;
      if (!l && mie.length < 6) pesi.push([mie.length < 3 ? 5 : 2.5, { arma: id }]);
      else if (l > 0 && l < 5) pesi.push([3, { arma: id }]);
      else if (l === 5 && livello(ARMI_CORSA[id].abbinata) > 0) pesi.push([9, { arma: id, evo: true }]);
    }
    for (const id in POTERI) if (livello(id) < POTERI[id].max) pesi.push([2, { potere: id }]);
    const carte = [];
    while (carte.length < quante && pesi.length) {
      let tot = 0; for (const p of pesi) tot += p[0];
      let x = c.rng() * tot, i = 0;
      for (; i < pesi.length - 1; i++) if ((x -= pesi[i][0]) <= 0) break;
      carte.push(pesi[i][1]); pesi.splice(i, 1);
    }
    // Tutto al massimo: restano vita e monete.
    while (carte.length < quante) carte.push(carte.length % 2 ? { monete: 25 } : { cura: true });
    return carte;
  }
  function applicaCarta(k) {
    const c = corsa;
    if (k.arma) c.armi[k.arma] = k.evo ? 6 : (c.armi[k.arma] || 0) + 1;
    else if (k.potere) {
      c.livelli[k.potere] = livello(k.potere) + 1;
      if (k.potere === "cuore") { c.hpMax += 15; c.hp += 15; }
    } else if (k.monete) c.monete += k.monete;
    else if (k.cura) c.hp = c.hpMax;
    else if (k.vita) { if (c.ultima) { c.ultima = false; c.vite = 1; c.hp = Math.max(c.hp, Math.round(c.hpMax * 0.5)); } else c.vite = Math.min(CORSA.viteMax, c.vite + 1); }
  }
  function apriLivello() {
    const c = corsa;
    c.scelta = { carte: carteLivello(3), liv: c.liv - c.daScegliere + 1 };
    c.pausa = true;
    suona("premio");
  }
  function prendiCarta(i) {
    const c = corsa;
    if (!c || !c.scelta || !c.scelta.carte[i]) return false;
    applicaCarta(c.scelta.carte[i]);
    c.daScegliere = Math.max(0, c.daScegliere - 1);
    c.scelta = null; c.pausa = false;
    const f = eroe();
    if (f && f.p) scintille(f.p.bacino.x, f.p.bacino.y - 20 * S, 16, "#ffd84a");
    return true;
  }
  // Il forziere: uno o tre premi scelti fra quelli che uscirebbero a un livello, più monete.
  function apriForziere() {
    const c = corsa, fortuna = bottega.fortuna || 0;
    const tanti = c.rng() < 0.15 + 0.08 * fortuna ? 3 : 1;
    const premi = carteLivello(tanti).map((k) => (k.monete || k.cura) ? k : k);
    if (c.rng() < 0.08 + 0.03 * fortuna) premi.push({ vita: true });
    else if (c.hp < c.hpMax * 0.6) premi.push({ cura: true });
    const monete = Math.round((10 + c.rng() * 15) * (1 + 0.2 * fortuna));
    for (const k of premi) applicaCarta(k);
    c.monete += monete;
    c.forziere = { premi, monete, t: 0 };
    c.pausa = true;
    suona("salvo");
  }
  function chiudiForziere() {
    if (!corsa || !corsa.forziere) return false;
    corsa.forziere = null; corsa.pausa = false;
    return true;
  }
  // Gemme e oggetti: cadono, si posano, la calamita li tira; fra un round e l'altro arrivano tutti.
  function aggiornaRaccolta() {
    const c = corsa, f = eroe();
    if (!f || !f.p) return;
    const hx = f.p.bacino.x, hy = f.p.bacino.y, R = raggioCalamita(), tutte = c.fase !== "lotta" || c.calamitaTutto > 0;
    if (c.calamitaTutto > 0) c.calamitaTutto--;
    const restano = [];
    for (const g of c.gemme) {
      g.t++;
      const dx = hx - g.x, dy = hy - g.y, d = Math.hypot(dx, dy);
      // L'eroe lotta da solo e non va a raccoglierle: dopo due secondi e mezzo a terra arrivano da sole,
      // così i livelli scattano durante la lotta e non tutti insieme a fine round.
      if (!g.tirata && (tutte || d < R || g.t > 150)) { g.tirata = true; g.t = 0; }
      if (g.tirata) {
        const v = Math.min(16 * S, 2 * S + g.t * 0.08 * S);
        g.x += dx / (d || 1) * Math.min(d, v); g.y += dy / (d || 1) * Math.min(d, v);
        if (d < 14 * S) {
          if (g.tipo === "moneta") { c.monete += g.valore; suona("moneta", g.x, 0.5); }
          else { daiEsperienza(g.valore); if (passi % 3 === 0) suona("pop", g.x, 0.35); }
          continue;
        }
      } else {
        g.vy += 0.3 * S; g.x += g.vx; g.y += g.vy; g.vx *= 0.96;
        if (g.y > g.base - 4 * S) { g.y = g.base - 4 * S; g.vy = 0; g.vx *= 0.6; }
        g.x = Math.max(8 * S, Math.min(W - 8 * S, g.x));
      }
      restano.push(g);
    }
    c.gemme = restano;
    // Gli oggetti: si prendono passandoci sopra (o fra un round e l'altro), se c'è un posto libero.
    c.aTerra = c.aTerra.filter((o) => {
      o.t++;
      o.vy += 0.3 * S; o.y += o.vy;
      if (o.y > o.base - 8 * S) { o.y = o.base - 8 * S; o.vy = 0; }
      const vicino = Math.hypot(hx - o.x, hy - o.y) < 34 * S;
      if (o.id === "calamita" && (vicino || tutte)) { c.calamitaTutto = 90; suona("carica", o.x); scrivi("\u{1F9F2}!", o.x, o.y - 20 * S, false); return false; }
      const posto = c.slot.indexOf(null);
      if ((vicino || tutte) && posto >= 0) { c.slot[posto] = o.id; suona("clic", o.x); scintille(o.x, o.y, 8, "#ffffff"); return false; }
      return o.t < 60 * 40;
    });
    // I forzieri: si aprono toccandoli, o comunque a fine round.
    if (!c.pausa && !mira) {
      const i = c.forzieri.findIndex((z) => tutte || Math.hypot(hx - z.x, hy - z.y) < 40 * S);
      if (i >= 0) { c.forzieri.splice(i, 1); apriForziere(); }
    }
    for (const z of c.forzieri) { z.vy = (z.vy || 0) + 0.3 * S; z.y += z.vy; if (z.y > z.base - 12 * S) { z.y = z.base - 12 * S; z.vy = 0; } }
  }

  // ·· Le armi automatiche ··
  // Su chi si può colpire: gli zombie in piedi e, nel duello, l'avversario.
  function bersagliCorsa() {
    const out = [];
    if (orda) for (const z of orda.zombie) if (vivoZ(z)) { const c = corpoZ(z); out.push({ z, x: c[0], y: c[1], r: c[2] * 1.4 }); }
    const n = nemicoCorsa();
    if (n && n.p && !n.fuoriCampo && !n.koVero && corsa.tipo === "duello") out.push({ l: n, x: n.p.bacino.x, y: n.p.bacino.y - 8 * S, r: 18 * S });
    return out;
  }
  function numero(x, y, v) {
    const c = corsa;
    if (c.numeri.length > 60) c.numeri.shift();
    c.numeri.push({ x: x + caso(-6, 6) * S, y, v: Math.max(1, Math.round(v * 10)), t: 0 });
  }
  // Un colpo d'arma: agli zombie toglie vita (e sotto zero li abbatte col solito SPLAT), all'avversario riempie la barra.
  function colpoArma(b, danno, dir, spinta, chiave) {
    const f = eroe();
    danno *= forzaCorsa();
    if (b.z) {
      const z = b.z;
      if (!vivoZ(z)) return false;
      z.hp -= danno * (z.tipo === "corazzato" ? 0.7 : 1); z.lampo = 4;
      if (spinta) { z.vx = dir * spinta * S * (pesante(z) ? 0.25 : 1); if (!pesante(z)) z.botta = Math.max(z.botta, 8); }
      numero(b.x, b.y - 18 * S, danno);
      if (z.hp <= 0) { z.hp = 0.01; colpisciZombie(z, 9, dir || 1, z.x, b.y, f); }
      return true;
    }
    const n = b.l;
    n.cdArmi = n.cdArmi || {};
    if ((n.cdArmi[chiave] || 0) > passi) return false;
    n.cdArmi[chiave] = passi + 30;
    n.danni += danno * 0.14;
    scintille(b.x, b.y, 6, "#ffd84a"); numero(b.x, b.y - 30 * S, danno);
    if (spinta) for (const k in n.p) n.p[k].ox -= dir * spinta * 0.4 * S;
    if (n.danni >= n.soglia && f) { n.danni = n.soglia - 1; f.dir = dir || 1; colpisci(f, n, 6, b.x, b.y, "POW!"); }
    return true;
  }
  function aggiornaArmi() {
    const c = corsa, f = eroe();
    if (!f || !f.p || f.fuoriCampo || c.fase !== "lotta") return;
    const hx = f.p.bacino.x, hy = f.p.bacino.y - 6 * S, A = areaCorsa(), K = ricaricaCorsa(), T = c.armiT;
    const B = bersagliCorsa();
    const tic = (id, cd) => { T[id] = (T[id] || 0) + 1; if (T[id] >= cd * K) { T[id] = 0; return true; } return false; };
    // Telefoni in orbita.
    const lo = c.armi.orbita;
    if (lo) {
      const evo = lo === 6, n = evo ? 8 : 1 + Math.ceil(lo / 2) + (lo >= 4 ? 1 : 0), R = (evo ? 74 : 44 + 5 * lo) * S * A;
      c.giro = (c.giro || 0) + (evo ? 0.09 : lo >= 3 ? 0.07 : 0.055);
      c.telefoni = [];
      for (let i = 0; i < n; i++) {
        const a = c.giro + i * Math.PI * 2 / n, x = hx + Math.cos(a) * R, y = hy + Math.sin(a) * R * 0.62;
        c.telefoni.push({ x, y, a });
        for (const b of B) {
          if (Math.hypot(b.x - x, b.y - y) > b.r + 9 * S * A) continue;
          const chi = b.z || b.l;
          if ((chi.cdOrbita || 0) > passi) continue;
          chi.cdOrbita = passi + 20;
          colpoArma(b, (evo ? 2.2 : 0.9 + 0.15 * lo), Math.sign(b.x - hx) || 1, 2, "orbita");
        }
      }
    } else c.telefoni = null;
    // Onda d'urto.
    const lw = c.armi.onda;
    if (lw && tic("onda", lw === 6 ? 110 : 230 - 22 * lw)) {
      c.onde.push({ x: hx, y: hy, r: 8 * S, R: (lw === 6 ? 210 : 90 + 18 * lw) * S * A, forza: lw === 6 ? 3 : 1.2 + 0.25 * lw, presi: new Set() });
      suona("soffio", hx, 0.6);
    }
    c.onde = c.onde.filter((o) => {
      o.r += 6 * S;
      for (const b of B) {
        const chi = b.z || b.l;
        if (o.presi.has(chi) || Math.abs(Math.hypot(b.x - o.x, b.y - o.y) - o.r) > 16 * S + b.r) continue;
        o.presi.add(chi);
        colpoArma(b, o.forza, Math.sign(b.x - o.x) || 1, 7, "onda");
      }
      return o.r < o.R;
    });
    // Fulmine.
    const lf = c.armi.fulmine;
    if (lf && B.length && tic("fulmine", lf === 6 ? 70 : 210 - 24 * lf)) {
      const quanti = lf === 6 ? 7 : [1, 2, 2, 3, 5][lf - 1];
      const scelti = B.slice().sort(() => Math.random() - 0.5).slice(0, quanti);
      for (const b of scelti) {
        c.saette.push({ x: b.x, y: b.y, t: 0, punti: null });
        colpoArma(b, lf === 6 ? 5 : 2.6 + 0.4 * lf, Math.random() < 0.5 ? -1 : 1, 1, "fulmine");
      }
      suona("tuono", scelti[0].x, 0.45);
    }
    c.saette = c.saette.filter((s) => ++s.t < 12);
    // Aura di fuoco.
    const la = c.armi.aura;
    if (la) {
      const R = (la === 6 ? 96 : 34 + 8 * la) * S * A;
      c.aura = R;
      if (tic("aura", la === 6 ? 14 : la >= 5 ? 18 : 24)) for (const b of B) if (Math.hypot(b.x - hx, b.y - hy) < R + b.r) colpoArma(b, la === 6 ? 1.6 : 0.45 + 0.15 * la, Math.sign(b.x - hx) || 1, 0.8, "aura");
    } else c.aura = 0;
    // Dardi.
    const ld = c.armi.dardi;
    if (ld && B.length && tic("dardi", ld === 6 ? 26 : (ld >= 2 ? 64 : 78))) {
      const quanti = ld === 6 ? 5 : ld >= 5 ? 3 : ld >= 3 ? 2 : 1;
      const vicini = B.slice().sort((p, q) => Math.hypot(p.x - hx, p.y - hy) - Math.hypot(q.x - hx, q.y - hy));
      for (let i = 0; i < quanti; i++) {
        const b = vicini[i % vicini.length];
        c.dardi.push({ x: hx, y: hy - 10 * S, vx: 0, vy: -3 * S, bersaglio: b.z || b.l, vita: 100, passa: ld === 6 ? 4 : ld >= 4 ? 2 : 1, presi: new Set(), forza: ld === 6 ? 2.6 : 1.1 + 0.2 * ld });
      }
    }
    c.dardi = c.dardi.filter((d) => {
      const t = d.bersaglio, bb = B.find((b) => (b.z || b.l) === t) || B.find((b) => !d.presi.has(b.z || b.l));
      if (bb) { const dx = bb.x - d.x, dy = bb.y - d.y, l = Math.hypot(dx, dy) || 1; d.vx += dx / l * 1.1 * S; d.vy += dy / l * 1.1 * S; d.bersaglio = bb.z || bb.l; }
      const v = Math.hypot(d.vx, d.vy), max = 9 * S;
      if (v > max) { d.vx *= max / v; d.vy *= max / v; }
      d.x += d.vx; d.y += d.vy;
      for (const b of B) {
        const chi = b.z || b.l;
        if (d.presi.has(chi) || Math.hypot(b.x - d.x, b.y - d.y) > b.r + 4 * S) continue;
        d.presi.add(chi); d.passa--;
        colpoArma(b, d.forza, Math.sign(d.vx) || 1, 2, "dardi");
        if (d.passa <= 0) return false;
      }
      return --d.vita > 0 && d.x > -20 && d.x < W + 20 && d.y > -20 && d.y < H + 20;
    });
    // Lama rotante: va e torna, e colpisce tutto quello che attraversa.
    const ll = c.armi.lama;
    if (ll && tic("lama", ll === 6 ? 80 : (ll >= 4 ? 120 : 150))) {
      const lontano = (ll === 6 ? 300 : 150 + 25 * ll) * S * A;
      for (const dir of ll === 6 ? [1, -1] : [f.dir || 1]) c.lame.push({ x: hx, y: hy, dir, va: lontano, fatto: 0, torna: false, presi: new Set(), r: (ll >= 5 ? 16 : 12) * S * A, forza: ll === 6 ? 4 : 1.6 + 0.35 * ll });
      suona("taglio", hx, 0.7);
    }
    c.lame = c.lame.filter((l) => {
      const v = 8 * S;
      if (!l.torna) { l.x += l.dir * v; l.fatto += v; if (l.fatto >= l.va) { l.torna = true; l.presi = new Set(); } }
      else { const dx = hx - l.x, dy = hy - l.y, d = Math.hypot(dx, dy); if (d < 14 * S) return false; l.x += dx / d * v * 1.2; l.y += dy / d * v * 1.2; }
      for (const b of B) {
        const chi = b.z || b.l;
        if (l.presi.has(chi) || Math.hypot(b.x - l.x, b.y - l.y) > b.r + l.r) continue;
        l.presi.add(chi);
        colpoArma(b, l.forza, l.torna ? -l.dir : l.dir, 4, "lama");
      }
      return true;
    });
    for (const n of c.numeri) { n.t++; n.y -= 0.6 * S; }
    c.numeri = c.numeri.filter((n) => n.t < 40);
  }

  // ·· Ferite, vite, ultima possibilità ··
  // Restituisce true se il colpo ha tolto una vita (il chiamante butta a terra).
  function feritaEroe(danno, x, y) {
    const c = corsa, f = eroe();
    if (!c || c.fase !== "lotta" || !f || c.pausa) return false;
    if (c.invuln > 0 || c.scudo > 0) { scintille(x, y, 6, "#bfe9ff"); return false; }
    danno = Math.max(1, Math.round(danno * crescita() * pelleCorsa()));
    c.hp -= danno; c.danniRound += danno;
    caricaCorsa(Math.min(danno, 30) * 0.25);                       // un colpo enorme non riempie il colpo finale
    c.lampo = 8;
    if (c.hp > 0) return false;
    if (c.ultima) { c.hp = 0; finisciCorsa(); return true; }
    c.vite--;
    if (c.vite > 0) {
      c.hp = c.hpMax; c.invuln = CORSA.invulnerabile;
      scrivi("-1 ❤️", f.p.bacino.x, f.base - 100 * S, true);
      respingiTutti(f, 9);
      return true;
    }
    // Finite le vite: l'ultima possibilità. Il colpo finale NON si riempie: si ricarica piano mentre si
    // resiste feriti, e dopo ogni salvataggio ancora più piano (pieno subito, chi mirava bene non cadeva mai).
    c.ultima = true; c.hp = Math.round(c.hpMax * CORSA.ultima); c.invuln = CORSA.invulnerabile;
    scrivi("ULTIMA POSSIBILITÀ!", f.p.bacino.x, f.base - 120 * S, true);
    respingiTutti(f, 11);
    return true;
  }
  // Un'onda d'urto intorno all'eroe: indietro gli zombie e l'avversario.
  function respingiTutti(f, forza) {
    const x = f.p.bacino.x, y = f.p.bacino.y;
    if (orda) for (const z of orda.zombie) {
      if (!vivoZ(z) || Math.abs(z.x - x) > 200 * S) continue;
      z.vx = (z.x >= x ? 1 : -1) * forza * S * (pesante(z) ? 0.4 : 1); z.botta = 70; z.lampo = 8;
      if (z.stato === "colpo") { z.stato = "va"; z.s = 0; }
    }
    const n = nemicoCorsa();
    if (n && !n.fuoriCampo && n.p && Math.abs(n.p.bacino.x - x) < 220 * S) {
      for (const k in n.p) n.p[k].ox -= (n.p.bacino.x >= x ? 1 : -1) * forza * S;
      n.azione = null; n.stordito = Math.max(n.stordito, 30);
    }
    if (particelle.length < MAX_PARTICELLE) particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 20, max: 20, colore: "#ffffff" });
    scintille(x, y, 16, "#ffe27a");
    scossa = Math.max(scossa, 10);
  }
  function caricaCorsa(quanto) {
    if (!corsa || corsa.fase !== "lotta") return;
    corsa.energia = Math.min(CORSA.energia, corsa.energia + quanto * (1 + 0.35 * livello("carica")));
  }
  // Un nemico giù: gemma, a volte una moneta o un oggetto, punti, energia, la sete.
  function corsaUcciso(z) {
    const c = corsa;
    if (!c || !c.chi || c.fase !== "lotta") return;
    c.uccisi++;
    c.punti += PUNTI_ZOMBIE[z.tipo] || 10;
    caricaCorsa(z.tipo === "capo" ? 30 : CORSA.perUcciso);
    if (livello("sete")) c.hp = Math.min(c.hpMax, c.hp + livello("sete"));
    const p = corpoZ(z), x = p[0], y = p[1];
    lasciaGemma(x, y, GEMMA_ZOMBIE[z.tipo] || 1, "gemma");
    if (c.rng() < 0.06 + 0.03 * livello("tasche")) lasciaGemma(x, y, 1 + livello("tasche"), "moneta");
    if (z.tipo === "capo") { c.forzieri.push({ x, y, base: orda.base, vy: -4 * S }); lasciaOggetto(x + 20 * S, y, oggettoCorsa()); for (let i = 0; i < 6; i++) lasciaGemma(x, y, 3, "moneta"); }
    else if (c.rng() < 0.012 * (1 + 0.3 * (bottega.fortuna || 0))) lasciaOggetto(x, y, oggettoCorsa());
  }
  // Il K.O. nella corsa: niente conto del ring, niente balletto per l'avversario; l'avversario lascia un forziere.
  function koCorsa(f, altro) {
    altro.ko = Math.round(caso(150, 190)); altro.danni = 0;
    scrivi("K.O.!", altro.p.bacino.x, Math.max(testataBasso + 30 * S, altro.base - 72 * S), true);
    if (altro.tipo !== corsa.chi && corsa.fase === "lotta") {
      corsa.uccisi++; corsa.punti += 150 + 25 * corsa.round;
      if (livello("sete")) corsa.hp = Math.min(corsa.hpMax, corsa.hp + 3 * livello("sete"));
      const x = altro.p.bacino.x, y = altro.p.bacino.y;
      corsa.forzieri.push({ x, y, base: altro.base, vy: -4 * S });
      for (let i = 0; i < 5; i++) lasciaGemma(x, y, 2 + Math.floor(corsa.round / 3), "gemma");
      vinciRound("ko");
    }
  }

  // ·· Il tasto del colpo finale e gli oggetti ··
  function tastoFinale() {
    const c = corsa, f = eroe();
    if (!c || c.fase !== "lotta" || !f || mira || c.pausa) return false;
    if (c.energia < CORSA.energia) { if (f.p) scrivi("Non ancora carico", f.p.bacino.x, f.base - 96 * S, false); return false; }
    if (!avviaMira(f)) return false;
    c.energia = 0;
    return true;
  }
  // Che cosa fa il colpo della mira nella corsa: gli zombie sulla linea vanno giù
  // (il capo perde un quarto della vita), l'avversario ne perde quasi metà. Se
  // si è all'ultima possibilità e il colpo prende qualcuno, il round è vinto.
  function colpoMiraCorsa(chi) {
    const c = corsa;
    for (const t of chi.zombie) { if (t.z.tipo === "capo") t.z.hp -= Math.max(2, (t.z.hpMax || 20) * 0.25); else t.z.hp = Math.min(t.z.hp, 1); }
    for (const t of chi.lott) if (t.l.tipo !== c.chi) t.l.danni += t.l.soglia * 0.42;
    return chi.lott.length + chi.zombie.length + chi.creature.length > 0;
  }
  function usaOggetto(i) {
    const c = corsa, f = eroe();
    if (!c || c.fase !== "lotta" || !f || !c.slot[i] || mira || c.pausa) return false;
    const id = c.slot[i], x = f.p.bacino.x, y = f.p.bacino.y;
    c.slot[i] = null;
    suona({ pozione: "cura", scudo: "scudo", carica: "carica", gelo: "gelo", bomba: "boom", bazooka: "metallo", lanciafiamme: "metallo", calamita: "carica" }[id], x, id === "bomba" ? 1.4 : 1);
    if (id === "pozione") { c.hp = Math.min(c.hpMax, c.hp + Math.round(c.hpMax * 0.5)); scintille(x, y - 20 * S, 14, "#7dffb0"); }
    else if (id === "scudo") c.scudo = 360;
    else if (id === "carica") c.energia = CORSA.energia;
    else if (id === "calamita") c.calamitaTutto = 90;
    else if (id === "bazooka" || id === "lanciafiamme") daiArma(f, id);
    else if (id === "gelo") {
      if (orda) for (const z of orda.zombie) if (vivoZ(z)) { z.botta = Math.max(z.botta, 240); z.gelo = 240; if (z.stato === "colpo") { z.stato = "va"; z.s = 0; } }
      const n = nemicoCorsa();
      if (n && !n.fuoriCampo && !n.ko) congela(n, f, n.p.bacino.x, n.p.bacino.y);
      for (let k = 0; k < 30 && particelle.length < MAX_PARTICELLE; k++) particelle.push({ tipo: "scintilla", x: caso(0, W), y: caso(testataBasso, pavimento), vx: 0, vy: caso(0.4, 1.4) * S, vita: 40, max: 40, colore: "#dff6ff" });
    } else if (id === "bomba") {
      const R = 170 * S;
      if (particelle.length < MAX_PARTICELLE - 4) {
        particelle.push({ tipo: "lampo", x, y, vx: 0, vy: 0, vita: 8, max: 8, r: R * 1.2 });
        particelle.push({ tipo: "onda", x, y, vx: 0, vy: 0, vita: 24, max: 24, colore: "#fff3b0" });
      }
      for (let k = 0; k < 14 && particelle.length < MAX_PARTICELLE; k++) {
        const a = caso(0, Math.PI * 2), d = caso(0.1, 0.5) * R;
        particelle.push({ tipo: "fuoco", x: x + Math.cos(a) * d, y: y + Math.sin(a) * d * 0.5, vx: Math.cos(a) * S, vy: -caso(0.4, 1.4) * S, vita: 26, max: 30, r: caso(9, 18) * S });
      }
      scossa = Math.max(scossa, 16); fermoColpo = Math.max(fermoColpo, 6);
      for (const b of bersagliCorsa()) if (Math.hypot(b.x - x, b.y - y) < R) colpoArma(b, 6, Math.sign(b.x - x) || 1, 9, "bomba");
      scrivi("BOOM!", x, y - 50 * S, true);
    }
    return true;
  }

  // ·· Il passo della corsa (dentro `passo`) ··
  function aggiornaCorsa() {
    const c = corsa;
    if (!c) return;
    c.t++;
    if (c.lampo > 0) c.lampo--;
    if (c.invuln > 0) c.invuln--;
    if (c.scudo > 0) c.scudo--;
    if (c.fase === "fine") { if (sulSito && classifica.voci && passi - classifica.letta > 600) caricaClassifica(); return; }
    if (!c.chi) return;
    // La valvola: con fotogrammi oltre i 45 ms di media, al massimo 20 zombie insieme (finché non si torna sotto i 30).
    if (c.dtMedio > 45) c.affanno = true; else if (c.dtMedio < 30) c.affanno = false;
    if (orda && orda.ricetta) { orda.ricetta.insiemeBase = orda.ricetta.insiemeBase || orda.ricetta.insieme; orda.ricetta.insieme = c.affanno ? Math.min(20, orda.ricetta.insiemeBase) : orda.ricetta.insiemeBase; }
    aggiornaRaccolta();
    aggiornaArmi();
    // Un livello in sospeso: le tre carte, appena non si sta mirando né aprendo un forziere.
    if (c.daScegliere > 0 && !c.scelta && !c.forziere && !mira && c.fase !== "fine") apriLivello();
    if (c.fase === "intro" && c.t >= CORSA.intro) iniziaLotta();
    else if (c.fase === "lotta") {
      // All'ultima possibilità il colpo finale si ricarica piano, e più piano dopo ogni salvataggio.
      if (c.ultima && !mira) c.energia = Math.min(CORSA.energia, c.energia + CORSA.ricarica / (1 + c.salvezze));
      // Gli imprevisti del round, uno alla volta.
      if (c.imprevisti.length && --c.prossimoImprevisto <= 0) {
        if (!evento && !fatale) { avviaEvento(c.imprevisti[c.lanciati] || c.imprevisti[0]); c.lanciati++; }
        c.prossimoImprevisto = c.lanciati >= c.imprevisti.length ? 1e9 : 600;
      }
      if (c.tipo === "tempo") {
        if (orda) orda.tOndata = 0;
        if (--c.scadenza <= 0) { vinciRound("tempo"); return; }
      }
      if (c.tipo !== "duello" && c.t > 30 && (!orda || (orda.fase === "festa" && orda.vinta))) { vinciRound("ondata"); return; }
      if (c.tipo === "duello") {
        const n = nemicoCorsa();
        // Chi è armato, ogni tanto, si ricarica.
        if (n && n.riarma > 0 && --n.riarma === 0) { if (!n.arma && !n.ko && !n.fuoriCampo) daiArma(n, c.round >= 6 ? "lanciafiamme" : "bazooka"); n.riarma = 900; }
      }
    } else if (c.fase === "vinto" && c.t >= CORSA.vinto && !c.forzieri.length && !c.forziere) prossimoRound();
  }
  // Che cosa fa l'eroe quando non c'è niente da picchiare; e i due, mentre si sceglie.
  function pensaCorsa(f, altro) {
    const c = corsa;
    if (c.fase === "scelta") {
      const posto = f.tipo === "robot" ? W * 0.36 : W * 0.64;
      if (Math.abs(f.cx - posto) > 10 * S && !f.supporto) { f.dir = posto >= f.cx ? 1 : -1; inizia(f, "avanza", posto); return true; }
      f.dir = f.tipo === "robot" ? 1 : -1;
      if (Math.random() < 0.25) inizia(f, scegli([[3, "esulta"], [2, "provoca"], [1, "para"]]));
      else f.pensa = Math.round(caso(30, 70));
      return true;
    }
    if (!eDellaCorsa(f)) return false;
    if (c.fase === "lotta" && (orda || c.tipo === "duello")) return false;
    if (c.fase === "vinto" && f.daBallare) return false;               // il balletto dopo il duello
    if (c.fase === "fine") { f.pensa = 60; return true; }
    f.pensa = Math.round(caso(30, 60));
    if (Math.random() < 0.3) inizia(f, "esulta");
    return true;
  }
  // L'eroe da solo contro l'orda: picchia quello che ha a portata, spara a chi
  // arriva, va incontro al più vicino.
  function pensaSolo(f) {
    const q = orda;
    if (q.fase !== "lotta") { f.pensa = 10; return; }
    const z = zombieVicino(f.cx, 40 * S);
    if (z) {
      f.dir = z.x >= f.cx ? 1 : -1; f.zMira = z;
      if (f.arma && f.arma.tipo === "spada" && f.colpiArma > 0) { f.colpiArma--; inizia(f, "fendente"); return; }
      if (lamaPronta(f)) { inizia(f, scegli([[3, "fendente"], [2, "affondo"], [2, "rovescio"]])); return; }
      if (z.tipo === "striscia") { inizia(f, scegli([[5, "calcio"], [3, "pugno"], [2, "diretto"]])); return; }
      if (Math.abs(z.x - f.cx) < 19 * S) { inizia(f, scegli([[3, "montante"], [2, "indietro"]])); return; }
      if (pesante(z) && z.stato === "colpo" && z.s < 20 && braccia(f) && Math.random() < 0.35 * f.furbo) { inizia(f, "para"); return; }
      inizia(f, scegli([[28 * pesoMossa(f, "pugno"), "pugno"], [22 * pesoMossa(f, "diretto"), "diretto"],
                        [18 * pesoMossa(f, "montante"), "montante"], [24 * pesoMossa(f, "calcio"), "calcio"]]));
      return;
    }
    const arriva = zombieVicino(f.cx, 1e9);
    if (!arriva) { f.pensa = 8; return; }
    const lato = arriva.x >= f.cx ? 1 : -1, d = Math.abs(arriva.x - f.cx);
    if (d > 46 * S) {
      if (f.arma && SPARANO[f.arma.tipo] && f.colpiArma > 0) { f.dir = lato; f.zMira = arriva; inizia(f, azioneArma(f.arma)); return; }
      if (anime && braccia(f) && !striscia(f)) {
        const quanti = q.zombie.reduce((n, w) => n + (vivoZ(w) && (w.x - f.cx) * lato > 0 ? 1 : 0), 0);
        if (f.ki >= 45 && quanti >= 2 && Math.random() < 0.5) { f.dir = lato; inizia(f, "onda"); return; }
        if (f.ki >= 15 && Math.random() < 0.35) { f.dir = lato; f.zMira = arriva; inizia(f, "raffica"); return; }
      }
    }
    // Incontro al più vicino, ma senza buttarsi in mezzo: ci si ferma a un passo.
    f.dir = lato;
    if (d > 34 * S) { inizia(f, "avanza", arriva.x - lato * 30 * S); return; }
    f.pensa = 4;
  }

  // ·· La classifica (solo sul sito) ··
  // Le chiamate al server le fa `static/classifica.js`, che carica solo il sito: qui non c'è rete.
  const rete = () => (sulSito && window.__ringClassifica) || null;
  function caricaClassifica() {
    const r = rete();
    if (!r) return;
    classifica.letta = passi;
    if (!classifica.voci) classifica.stato = "carico";
    r.carica()
      .then((d) => { classifica.voci = Array.isArray(d.voci) ? d.voci : []; classifica.stato = ""; })
      .catch(() => { classifica.stato = "errore"; });
  }
  function inviaPunteggio(nome) {
    const c = corsa;
    nome = String(nome || "").replace(/\s+/g, " ").trim().slice(0, 16);
    const r = rete();
    if (!c || !c.chi || c.inviato || !nome || !r) return false;
    c.inviato = "invio"; c.nome = nome;
    try { deposito.setItem("mut-ring-nome", nome); } catch (errore) { /* pazienza */ }
    r.invia({ nome, punti: c.punti, round: c.round, personaggio: c.chi, stile: c.stile, uccisi: c.uccisi, durata: Math.round((Date.now() - c.iniziata) / 1000) })
      .then(({ ok, d }) => {
        if (!corsa) return;
        if (!ok) { corsa.inviato = false; corsa.erroreInvio = (d && d.errore) || "Non è andata"; mostraNome(true); return; }
        corsa.inviato = "fatto"; corsa.posizione = d.posizione || 0;
        if (Array.isArray(d.voci)) classifica.voci = d.voci;
        classifica.mia = d.id || -1;
      })
      .catch(() => { if (corsa) { corsa.inviato = false; corsa.erroreInvio = "Non è andata"; mostraNome(true); } });
    mostraNome(false);
    return true;
  }
  // Il campo per il nome: un vero campo di testo sopra il canvas, solo sul sito.
  function mostraNome(si) {
    if (!sulSito || !document.createElement || !document.body) return;
    if (!si) { if (campoNome && campoNome.parentNode) campoNome.parentNode.removeChild(campoNome); campoNome = null; return; }
    if (campoNome || !corsa || corsa.inviato) return;
    const modulo = document.createElement("form");
    modulo.className = "corsa-nome";
    modulo.setAttribute("style", "position:fixed;z-index:2147483000;display:flex;gap:6px;align-items:center;left:50%;transform:translateX(-50%);");
    const campo = document.createElement("input");
    campo.type = "text"; campo.maxLength = 16; campo.value = corsa.nome || ""; campo.placeholder = dici("Il tuo nome");
    campo.setAttribute("aria-label", dici("Il tuo nome per la classifica"));
    campo.setAttribute("style", "font:700 16px Archivo,sans-serif;padding:8px 10px;border-radius:8px;border:2px solid #ffd84a;background:#17171c;color:#fff;width:170px;");
    const tasto = document.createElement("button");
    tasto.type = "submit"; tasto.textContent = dici("Invia");
    tasto.setAttribute("style", "font:800 15px Archivo,sans-serif;padding:9px 14px;border-radius:8px;border:0;background:#ffd84a;color:#17171c;cursor:pointer;");
    modulo.appendChild(campo); modulo.appendChild(tasto);
    modulo.addEventListener("submit", (e) => { e.preventDefault(); inviaPunteggio(campo.value); });
    for (const tipo of ["pointerdown", "mousedown", "touchstart", "keydown"]) modulo.addEventListener(tipo, (e) => e.stopPropagation());
    document.body.appendChild(modulo);
    campoNome = modulo;
    posizionaNome();
  }
  function posizionaNome() {
    if (campoNome && campoNome.style) campoNome.style.top = Math.round(corsa && corsa.yNome ? corsa.yNome : H * 0.45) + "px";
  }
  function apriClassifica(si) {
    classifica.aperta = !!si;
    if (si) { assicuraAcceso(); caricaClassifica(); riparti(); }
  }

  // ·· Il disegno della corsa ··
  // Aspetto da videogioco, come il controller: pannelli scuri, bordi nel colore
  // del personaggio, l'oro per quello che si può toccare. Ogni tasto disegnato
  // finisce in `tastiUI`, che il tocco (vedi `prendi`) controlla per primo.
  const ORO = "#ffd84a", FONDO_UI = "rgba(18,16,28,.93)", GRIGIO_UI = "#b9b4c8";
  const coloreCorsa = () => (corsa && corsa.chi ? COLORI_ANIME[corsa.chi] : "#56e1ff");
  const cifre = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  function caratteri(px, peso) { ctx.font = (peso || 800) + " " + Math.max(9, Math.round(px)) + "px Archivo, sans-serif"; }
  function largoTesto(t, px) { const m = ctx.measureText ? ctx.measureText(t) : null; return (m && m.width) || t.length * px * 0.56; }
  function scriviUI(t, x, y, px, colore, allinea, peso) {
    caratteri(px, peso); ctx.textAlign = allinea || "left"; ctx.textBaseline = "middle"; ctx.fillStyle = colore || "#ffffff"; ctx.fillText(t, x, y);
  }
  function righeUI(t, largo, px) {
    caratteri(px, 600);
    const out = []; let r = "";
    for (const p of String(t).split(" ")) { const prova = r ? r + " " + p : p; if (r && largoTesto(prova, px) > largo) { out.push(r); r = p; } else r = prova; }
    if (r) out.push(r);
    return out;
  }
  function pannelloUI(x, y, w, h, r, bordo, fondo) {
    ctx.fillStyle = fondo || FONDO_UI; rettangoloTondo(x, y, w, h, r); ctx.fill();
    if (bordo) { ctx.strokeStyle = bordo; ctx.lineWidth = 2 * S; ctx.stroke(); }
  }
  // Un tasto: rettangolo arrotondato con la scritta; spento, è grigio e non si tocca.
  function tastoUI(x, y, w, h, etichetta, fa, opz) {
    opz = opz || {};
    const spento = !!opz.spento, colore = spento ? "#4a4658" : opz.colore || ORO;
    ctx.save();
    if (!spento && opz.brilla) { ctx.shadowColor = colore; ctx.shadowBlur = 14 * S; }
    pannelloUI(x, y, w, h, Math.min(10 * S, h / 2), opz.bordo || null, colore);
    ctx.restore();
    scriviUI(etichetta, x + w / 2, y + h / 2 + 1, opz.px || 14 * S, spento ? "#8d889c" : opz.scritta || "#17171c", "center");
    if (!spento && fa) tastiUI.push({ x, y, w, h, fa });
  }
  function cuore(x, y, r, pieno, colore) {
    ctx.beginPath();
    ctx.moveTo(x, y + r * 0.9);
    ctx.bezierCurveTo(x - r * 1.6, y - r * 0.1, x - r * 0.7, y - r * 1.3, x, y - r * 0.45);
    ctx.bezierCurveTo(x + r * 0.7, y - r * 1.3, x + r * 1.6, y - r * 0.1, x, y + r * 0.9);
    ctx.closePath();
    ctx.fillStyle = pieno ? colore || "#ff4d6d" : "rgba(255,255,255,.12)"; ctx.fill();
    ctx.strokeStyle = pieno ? "#17171c" : "rgba(255,255,255,.35)"; ctx.lineWidth = 1.4 * S; ctx.stroke();
  }
  function barraUI(x, y, w, h, k, colore, scia) {
    k = Math.max(0, Math.min(1, k));
    ctx.fillStyle = "#0c0b12"; rettangoloTondo(x - 1.5 * S, y - 1.5 * S, w + 3 * S, h + 3 * S, h / 2 + 1.5 * S); ctx.fill();
    if (scia !== undefined && scia > k) { ctx.fillStyle = "#ffb3a8"; rettangoloTondo(x, y, w * Math.min(1, scia), h, h / 2); ctx.fill(); }
    if (k > 0.004) { ctx.fillStyle = colore; rettangoloTondo(x, y, Math.max(h, w * k), h, h / 2); ctx.fill(); ctx.fillStyle = "rgba(255,255,255,.3)"; ctx.fillRect(x + h / 2, y + 1, Math.max(0, w * k - h), h * 0.3); }
  }
  // A terra, sotto i lottatori: l'aura di fuoco, le gemme, le monete, gli oggetti, i forzieri.
  function disegnaTerraCorsa() {
    const c = corsa, f = eroe();
    ctx.save();
    if (c.aura && f && f.p && c.fase === "lotta") {
      const b = f.p.bacino, R = c.aura * (0.95 + 0.05 * Math.sin(passi * 0.4)), evo = c.armi.aura === 6;
      const g = ctx.createRadialGradient(b.x, b.y, R * 0.2, b.x, b.y, R);
      g.addColorStop(0, "rgba(255,140,40,0)"); g.addColorStop(0.75, evo ? "rgba(255,70,20,.28)" : "rgba(255,140,40,.2)"); g.addColorStop(1, "rgba(255,90,30,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(b.x, b.y, R, 0, Math.PI * 2); ctx.fill();
    }
    for (const g of c.gemme) {
      const r = (g.tipo === "moneta" ? 4.6 : 3.4 + Math.min(4, g.valore * 0.6)) * S, y = g.y - (g.tirata ? 0 : Math.abs(Math.sin(g.t * 0.08)) * 2 * S);
      if (g.tipo === "moneta") {
        ctx.fillStyle = ORO; ctx.strokeStyle = "#8a6510"; ctx.lineWidth = 1.2 * S;
        ctx.beginPath(); ctx.arc(g.x, y, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#fff3b0"; ctx.beginPath(); ctx.arc(g.x - r * 0.3, y - r * 0.3, r * 0.3, 0, Math.PI * 2); ctx.fill();
      } else {
        const col = g.valore >= 4 ? "#ff4d6d" : g.valore >= 2 ? "#2fbf71" : "#56b8ff";
        ctx.fillStyle = col; ctx.strokeStyle = "#0c0b12"; ctx.lineWidth = 1 * S;
        ctx.beginPath(); ctx.moveTo(g.x, y - r * 1.3); ctx.lineTo(g.x + r, y); ctx.lineTo(g.x, y + r * 1.3); ctx.lineTo(g.x - r, y); ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,.7)"; ctx.beginPath(); ctx.moveTo(g.x, y - r * 1.1); ctx.lineTo(g.x + r * 0.4, y - r * 0.2); ctx.lineTo(g.x, y); ctx.closePath(); ctx.fill();
      }
    }
    for (const o of c.aTerra) {
      const y = o.y - Math.abs(Math.sin(o.t * 0.06)) * 4 * S, lampeggia = o.t > 60 * 34 && passi % 12 < 6;
      if (lampeggia) continue;
      ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.strokeStyle = coloreCorsa(); ctx.lineWidth = 2 * S;
      ctx.beginPath(); ctx.arc(o.x, y, 12 * S, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      scriviUI(OGGETTI[o.id].icona, o.x, y + 1, 13 * S, "#ffffff", "center");
    }
    for (const z of c.forzieri) {
      const y = z.y - Math.abs(Math.sin(passi * 0.08)) * 5 * S;
      const g = ctx.createRadialGradient(z.x, y, 2 * S, z.x, y, 34 * S);
      g.addColorStop(0, "rgba(255,216,74,.55)"); g.addColorStop(1, "rgba(255,216,74,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(z.x, y, 34 * S, 0, Math.PI * 2); ctx.fill();
      scriviUI("\u{1F381}", z.x, y, 24 * S, "#ffffff", "center");
    }
    ctx.restore();
  }
  // Le armi automatiche, sopra i lottatori: telefoni, onde, fulmini, dardi, lame, e i numeri dei colpi.
  function disegnaArmiCorsa() {
    const c = corsa, col = coloreCorsa();
    ctx.save(); ctx.lineCap = "round"; ctx.lineJoin = "round";
    for (const o of c.onde) {
      const k = 1 - o.r / o.R;
      ctx.globalAlpha = Math.max(0, k) * 0.85; ctx.strokeStyle = c.armi.onda === 6 ? ORO : "#bfe9ff"; ctx.lineWidth = (3 + 5 * k) * S;
      ctx.beginPath(); ctx.ellipse(o.x, o.y, o.r, o.r * 0.55, 0, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.globalAlpha = 1;
    if (c.telefoni) for (const t of c.telefoni) {
      const evo = c.armi.orbita === 6;
      ctx.save(); ctx.translate(t.x, t.y); ctx.rotate(t.a * 2);
      ctx.fillStyle = "#17171c"; rettangoloTondo(-5 * S, -8 * S, 10 * S, 16 * S, 2.5 * S); ctx.fill();
      ctx.fillStyle = evo ? ORO : col; ctx.fillRect(-3.6 * S, -6 * S, 7.2 * S, 10.5 * S);
      ctx.restore();
    }
    for (const sa of c.saette) {
      const k = 1 - sa.t / 12;
      if (!sa.punti) { sa.punti = []; for (let y = testataBasso + 10 * S; y < sa.y; y += 18 * S) sa.punti.push([sa.x + caso(-10, 10) * S, y]); sa.punti.push([sa.x, sa.y]); }
      ctx.globalAlpha = k; ctx.strokeStyle = "#fff6a8"; ctx.lineWidth = 4 * S; ctx.shadowColor = "#fff6a8"; ctx.shadowBlur = 12 * S;
      ctx.beginPath(); sa.punti.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke();
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.6 * S; ctx.stroke(); ctx.shadowBlur = 0;
    }
    ctx.globalAlpha = 1;
    for (const d of c.dardi) {
      // (un alone disegnato, non un'ombra sfumata: con quindici dardi l'ombra costava troppo)
      ctx.fillStyle = "rgba(201,160,255,.35)"; ctx.beginPath(); ctx.arc(d.x, d.y, 7 * S, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = c.armi.dardi === 6 ? ORO : "#e9d8ff";
      ctx.beginPath(); ctx.arc(d.x, d.y, 3.4 * S, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "rgba(201,160,255,.6)"; ctx.lineWidth = 2 * S; ctx.beginPath(); ctx.moveTo(d.x, d.y); ctx.lineTo(d.x - d.vx * 2, d.y - d.vy * 2); ctx.stroke();
    }
    ctx.shadowBlur = 0;
    for (const l of c.lame) {
      ctx.save(); ctx.translate(l.x, l.y); ctx.rotate(passi * 0.5 * l.dir);
      ctx.strokeStyle = c.armi.lama === 6 ? ORO : "#e8eef7"; ctx.lineWidth = 3.4 * S;
      for (const a of [0, Math.PI]) { ctx.beginPath(); ctx.arc(0, 0, l.r, a, a + Math.PI * 0.7); ctx.stroke(); }
      ctx.fillStyle = "#17171c"; ctx.beginPath(); ctx.arc(0, 0, 3 * S, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    caratteri(11 * S, 900); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineWidth = 3 * S; ctx.strokeStyle = "#17171c";
    for (const n of c.numeri) {
      ctx.globalAlpha = Math.max(0, 1 - n.t / 40); ctx.fillStyle = n.v >= 30 ? ORO : "#ffffff";
      const t = String(n.v / 10 >= 10 ? Math.round(n.v / 10) : (n.v / 10).toFixed(1).replace(/\.0$/, ""));
      ctx.strokeText(t, n.x, n.y); ctx.fillText(t, n.x, n.y);
    }
    ctx.restore();
  }
  // Sotto i lottatori: il buio dei menu, l'aura rossa dell'ultima possibilità.
  function disegnaFondoCorsa() {
    const c = corsa;
    if (classifica.aperta || (c && (c.fase === "scelta" || c.fase === "fine"))) {
      ctx.save(); ctx.fillStyle = "rgba(10,8,22,.62)"; ctx.fillRect(0, 0, W, H); ctx.restore();
    }
    if (!c || !c.chi) return;
    const f = eroe();
    if (c.fase !== "fine") disegnaTerraCorsa();
    if (c.ultima && f && f.p && c.fase === "lotta") {
      const b = f.p.bacino, k = 0.55 + 0.45 * Math.sin(passi * 0.16), R = 70 * S;
      const g = ctx.createRadialGradient(b.x, b.y, 4 * S, b.x, b.y, R);
      g.addColorStop(0, "rgba(255,60,40," + (0.42 * k).toFixed(3) + ")"); g.addColorStop(1, "rgba(255,60,40,0)");
      ctx.save(); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(b.x, b.y, R, 0, Math.PI * 2); ctx.fill();
      const v = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.max(W, H) * 0.75);
      v.addColorStop(0, "rgba(160,10,10,0)"); v.addColorStop(1, "rgba(160,10,10," + (0.28 + 0.12 * k).toFixed(3) + ")");
      ctx.fillStyle = v; ctx.fillRect(0, 0, W, H); ctx.restore();
    }
  }
  // Sopra a tutto: l'interfaccia della corsa, i menu, la classifica.
  function disegnaCorsa() {
    tastiUI = [];
    const c = corsa;
    if (c) {
      ctx.save(); ctx.lineJoin = "round"; ctx.lineCap = "round";
      if (c.fase === "scelta") disegnaScelta();
      else if (c.chi) {
        disegnaScudoEroe();
        if (c.fase !== "fine") { disegnaArmiCorsa(); disegnaHud(); }
        if (c.fase === "intro") disegnaIntro();
        else if (c.fase === "vinto") disegnaVinto();
        else if (c.fase === "fine") disegnaFine();
        if (c.scelta) disegnaLivello();
        else if (c.forziere) disegnaForziere();
      }
      ctx.restore();
    }
    if (classifica.aperta) { ctx.save(); disegnaClassifica(W / 2, testataBasso + 40 * S, Math.min(420 * S, W - 32), true); ctx.restore(); }
  }
  function disegnaScudoEroe() {
    const c = corsa, f = eroe();
    if (!f || !f.p || f.fuoriCampo) return;
    const b = f.p.bacino;
    if (c.scudo > 0) {
      const k = c.scudo < 60 ? (passi % 8 < 4 ? 0.3 : 1) : 1;
      ctx.save(); ctx.globalAlpha = 0.85 * k;
      const g = ctx.createRadialGradient(b.x, b.y - 10 * S, 20 * S, b.x, b.y - 10 * S, 52 * S);
      g.addColorStop(0, "rgba(140,220,255,0)"); g.addColorStop(0.8, "rgba(140,220,255,.25)"); g.addColorStop(1, "rgba(200,240,255,.7)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(b.x, b.y - 10 * S, 52 * S, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "#dff6ff"; ctx.lineWidth = 2 * S; ctx.stroke(); ctx.restore();
    } else if (c.invuln > 0 && passi % 10 < 5) {
      ctx.save(); ctx.globalAlpha = 0.6; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2 * S;
      ctx.beginPath(); ctx.arc(b.x, b.y - 10 * S, 46 * S, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    }
  }
  // Il cruscotto: vite, vita, energia, monete; il round in alto a destra; il colpo finale e gli oggetti in basso.
  function disegnaHud() {
    const c = corsa, col = coloreCorsa(), m = 12 * S, y0 = testataBasso + 14 * S;
    // In cima, per tutta la larghezza: l'esperienza verso il prossimo livello.
    const kx = Math.min(1, c.xp / xpPerLivello(c.liv));
    ctx.fillStyle = "rgba(12,11,18,.75)"; ctx.fillRect(0, testataBasso + 2 * S, W, 7 * S);
    ctx.fillStyle = "#56b8ff"; ctx.fillRect(0, testataBasso + 2 * S, W * kx, 7 * S);
    ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.fillRect(0, testataBasso + 2 * S, W * kx, 2 * S);
    // In alto a sinistra.
    const w = Math.min(250 * S, W * 0.5 - 2 * m), h = 70 * S;
    pannelloUI(m, y0, w, h, 10 * S, c.lampo > 0 ? "#ff4d4d" : col);
    scriviUI(nomeDi(c.chi).toUpperCase() + "  ·  " + dici("Liv.") + " " + c.liv, m + 10 * S, y0 + 13 * S, 12 * S, col);
    const nCuori = Math.max(CORSA.vite, c.vite);
    for (let i = 0; i < nCuori; i++) cuore(m + w - 14 * S - (nCuori - 1 - i) * 17 * S, y0 + 13 * S, 6.2 * S, i < c.vite, c.ultima ? "#ff3b30" : null);
    const k = c.hp / c.hpMax;
    barraUI(m + 10 * S, y0 + 25 * S, w - 20 * S, 11 * S, k, c.ultima ? "#ff3b30" : k > 0.5 ? "#2fbf71" : k > 0.25 ? "#f2c230" : "#e0443a");
    scriviUI(Math.max(0, Math.ceil(c.hp)) + " / " + c.hpMax, m + w / 2, y0 + 31 * S, 9 * S, "#ffffff", "center");
    const pieno = c.energia >= CORSA.energia;
    barraUI(m + 10 * S, y0 + 43 * S, w - 20 * S, 6 * S, c.energia / CORSA.energia, pieno ? (passi % 20 < 10 ? ORO : "#fff3b0") : "#56b8ff");
    scriviUI("\u{1FA99} " + c.monete + "   ☠ " + c.uccisi, m + 10 * S, y0 + 60 * S, 11 * S, ORO);
    scriviUI(cifre(c.punti) + " " + dici("punti"), m + w - 10 * S, y0 + 60 * S, 11 * S, "#ffffff", "right");
    // In alto a destra: il round, che cosa c'è da fare, gli imprevisti, l'uscita.
    const w2 = Math.min(210 * S, W * 0.5 - 2 * m), x2 = W - m - w2, T = TIPI_ROUND[c.tipo] || ["", ""];
    pannelloUI(x2, y0, w2, h, 10 * S, "rgba(255,255,255,.25)");
    scriviUI(dici("Round") + " " + c.round, x2 + 10 * S, y0 + 14 * S, 15 * S, "#ffffff");
    scriviUI(T[0] + " " + dici(T[1]), x2 + 10 * S, y0 + 34 * S, 11 * S, GRIGIO_UI, "left", 700);
    scriviUI(obiettivo(), x2 + 10 * S, y0 + 54 * S, 12 * S, ORO);
    let xi = x2 + w2 - 12 * S;
    for (let i = c.imprevisti.length - 1; i >= 0; i--) { scriviUI(IMPREVISTI_CORSA[c.imprevisti[i]][0], xi, y0 + 34 * S, 14 * S, "#ffffff", "right"); xi -= 20 * S; }
    // L'audio si accende e si spegne anche da qui, senza aprire il pannello.
    tastoUI(x2 + w2 - (c.esci > passi ? 106 : 60) * S, y0 + 6 * S, 26 * S, 22 * S, audio.acceso ? "🔊" : "🔇", () => accendiAudio(!audio.acceso), { colore: "#3a3647", scritta: "#ffffff", px: 12 * S });
    // L'uscita chiede conferma: un tocco la arma, il secondo (entro tre secondi) chiude la corsa.
    if (c.esci > passi) tastoUI(x2 + w2 - 76 * S, y0 + 6 * S, 70 * S, 22 * S, dici("Esci?"), () => finisciCorsa(), { colore: "#e0443a", scritta: "#ffffff", px: 11 * S });
    else tastoUI(x2 + w2 - 30 * S, y0 + 6 * S, 24 * S, 22 * S, "✕", () => { c.esci = passi + 180; }, { colore: "#3a3647", scritta: "#ffffff", px: 12 * S });
    // Il capo o l'avversario: la sua barra, in alto al centro (sui telefoni, sotto i tasti).
    const nemico = barraNemico();
    if (nemico) {
      const largo = W > 640, wn = largo ? Math.min(260 * S, W - w - w2 - 6 * m) : Math.min(220 * S, W - 2 * m), xn = W / 2 - wn / 2;
      const yn = largo ? y0 : y0 + h + 92 * S;
      pannelloUI(xn - 10 * S, yn, wn + 20 * S, 40 * S, 10 * S, "#e0443a");
      scriviUI(nemico.nome, W / 2, yn + 12 * S, 12 * S, "#ffffff", "center");
      barraUI(xn, yn + 24 * S, wn, 9 * S, nemico.k, "#e0443a");
    }
    if (c.fase === "lotta" || c.fase === "vinto") disegnaComandiCorsa(m, y0 + h + 10 * S);
  }
  function obiettivo() {
    const c = corsa;
    if (c.fase === "intro") return dici("Pronti…");
    if (c.fase !== "lotta") return dici("Fatto!");
    if (c.tipo === "tempo") { const s = Math.max(0, Math.ceil(c.scadenza / 60)); return "⏳ " + Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); }
    if (c.tipo === "duello") return dici("Mandalo K.O.");
    if (orda && orda.ricetta) { const tot = orda.ricetta.totale; return "\u{1F9DF} " + Math.min(tot, orda.uccisiOndata) + " / " + tot; }
    return "";
  }
  function barraNemico() {
    const c = corsa;
    if (c.tipo === "duello" && (c.fase === "lotta" || c.fase === "vinto")) {
      const n = nemicoCorsa();
      if (!n || n.fuoriCampo) return null;
      return { nome: nomeNemico(), k: n.koVero ? 0 : 1 - n.danni / Math.max(1, n.soglia) };
    }
    if (c.tipo === "boss" && orda) {
      const z = orda.zombie.find((q) => q.tipo === "capo" && q.stato !== "giu");
      if (z) return { nome: dici("Il capo"), k: z.hp / (z.hpMax || 1) };
    }
    return null;
  }
  // Sotto il cruscotto, in alto a sinistra: il colpo finale e i tre posti degli oggetti.
  // (In basso coprivano la lotta, che finisce spesso sulla striscia delle notizie.)
  function disegnaComandiCorsa(xs, ys) {
    const c = corsa, sx = 1, R = 30 * S, r = 20 * S;
    const x0 = xs + R + 4 * S, y0 = ys + R + 4 * S;
    const pronto = c.energia >= CORSA.energia && c.fase === "lotta" && !mira, k = c.energia / CORSA.energia;
    const col = c.ultima ? "#ff3b30" : ORO, pulsa = 0.5 + 0.5 * Math.sin(passi * 0.3);
    if (pronto) { ctx.fillStyle = col; ctx.globalAlpha = 0.25 + 0.2 * pulsa; ctx.beginPath(); ctx.arc(x0, y0, R + (8 + 6 * pulsa) * S, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1; }
    ctx.fillStyle = pronto ? col : "#2a2735"; ctx.beginPath(); ctx.arc(x0, y0, R, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "#0c0b12"; ctx.lineWidth = 5 * S; ctx.beginPath(); ctx.arc(x0, y0, R + 4 * S, 0, Math.PI * 2); ctx.stroke();
    if (k > 0.005) { ctx.strokeStyle = pronto ? "#ffffff" : "#56b8ff"; ctx.lineWidth = 4 * S; ctx.beginPath(); ctx.arc(x0, y0, R + 4 * S, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.min(1, k)); ctx.stroke(); }
    scriviUI("\u{1F3AF}", x0, y0 - 6 * S, 20 * S, "#ffffff", "center");
    scriviUI(dici("Finale"), x0, y0 + 15 * S, 9 * S, pronto ? "#17171c" : GRIGIO_UI, "center");
    tastiUI.push({ x: x0 - R, y: y0 - R, w: 2 * R, h: 2 * R, fa: () => tastoFinale() });
    for (let i = 0; i < 3; i++) {
      const x = x0 + sx * (R + 18 * S + r + i * (2 * r + 10 * S)), y = y0, id = c.slot[i];
      ctx.fillStyle = id ? "#2a2735" : "rgba(20,18,30,.28)"; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = id ? coloreCorsa() : "rgba(40,36,52,.55)"; ctx.lineWidth = 2 * S;
      if (!id) ctx.setLineDash([4 * S, 4 * S]);
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
      if (id) { scriviUI(OGGETTI[id].icona, x, y + 1, 18 * S, "#ffffff", "center"); tastiUI.push({ x: x - r, y: y - r, w: 2 * r, h: 2 * r, fa: () => usaOggetto(i) }); }
      scriviUI(String(i + 1), x + r * 0.72, y - r * 0.72, 9 * S, GRIGIO_UI, "center");
    }
    // Le armi e i loro livelli (una stella per l'evoluzione).
    const armi = Object.keys(c.armi), ya = y0 + R + 22 * S;
    armi.forEach((id, i) => {
      const x = xs + 4 * S + i * 34 * S, l = c.armi[id], evo = l === 6;
      pannelloUI(x, ya - 14 * S, 30 * S, 34 * S, 7 * S, evo ? "#ff62d6" : "rgba(255,255,255,.3)");
      scriviUI(ARMI_CORSA[id].icona, x + 15 * S, ya, 15 * S, "#ffffff", "center");
      if (evo) scriviUI("★", x + 15 * S, ya + 14 * S, 9 * S, "#ff62d6", "center");
      else for (let k = 0; k < 5; k++) { ctx.fillStyle = k < l ? ORO : "rgba(255,255,255,.2)"; ctx.fillRect(x + 4 * S + k * 4.6 * S, ya + 12 * S, 3.4 * S, 3 * S); }
    });
  }
  function disegnaIntro() {
    const c = corsa, t = c.t / CORSA.intro, a = Math.min(1, t * 6, (1 - t) * 5), T = TIPI_ROUND[c.tipo];
    const w = Math.min(380 * S, W - 32), h = (c.tipo === "duello" || c.imprevisti.length ? 128 : 100) * S, x = W / 2 - w / 2, y = H * 0.32 - h / 2;
    ctx.save(); ctx.globalAlpha = Math.max(0, a);
    pannelloUI(x, y, w, h, 14 * S, coloreCorsa());
    scriviUI(dici("Round") + " " + c.round, W / 2, y + 30 * S, 30 * S, "#ffffff", "center", 900);
    scriviUI(T[0] + "  " + dici(T[1]), W / 2, y + 62 * S, 17 * S, ORO, "center");
    let riga = y + 92 * S;
    if (c.tipo === "duello") { scriviUI(dici("Contro") + " " + nomeNemicoAtteso(), W / 2, riga, 12 * S, GRIGIO_UI, "center", 700); riga += 20 * S; }
    if (c.imprevisti.length) scriviUI(dici("Imprevisti") + ": " + c.imprevisti.map((n) => IMPREVISTI_CORSA[n][0] + " " + dici(IMPREVISTI_CORSA[n][1])).join("  "), W / 2, riga, 12 * S, GRIGIO_UI, "center", 700);
    ctx.restore();
  }
  function nomeNemicoAtteso() {
    return conVariante(corsa.chi === "robot" ? "mela" : "robot", corsa.variante || []);
  }
  function disegnaVinto() {
    const c = corsa, t = c.t / CORSA.vinto, a = Math.min(1, t * 6, (1 - t) * 4), P = c.ultimoPremio || { monete: 0, punti: 0 };
    ctx.save(); ctx.globalAlpha = Math.max(0, a);
    const y = H * 0.32;
    caratteri(30 * S, 900); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineWidth = 5 * S; ctx.strokeStyle = "#17171c"; ctx.fillStyle = ORO;
    ctx.strokeText(dici("Round superato!"), W / 2, y); ctx.fillText(dici("Round superato!"), W / 2, y);
    caratteri(15 * S, 800); ctx.lineWidth = 4 * S; ctx.fillStyle = "#ffffff";
    const riga = "+" + cifre(P.punti) + " " + dici("punti");
    ctx.strokeText(riga, W / 2, y + 32 * S); ctx.fillText(riga, W / 2, y + 32 * S);
    if (P.pulito) { ctx.fillStyle = "#7dffb0"; ctx.strokeText(dici("Senza un graffio!"), W / 2, y + 56 * S); ctx.fillText(dici("Senza un graffio!"), W / 2, y + 56 * S); }
    ctx.restore();
  }
  function disegnaScelta() {
    const c = corsa, top = testataBasso + 20 * S;
    caratteri(34 * S, 900); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineWidth = 6 * S; ctx.strokeStyle = "#17171c"; ctx.fillStyle = ORO;
    ctx.strokeText(dici("Corsa infinita"), W / 2, top + 22 * S); ctx.fillText(dici("Corsa infinita"), W / 2, top + 22 * S);
    scriviUI(dici("Scegli chi lotta. Round dopo round, finché hai vite."), W / 2, top + 52 * S, 13 * S, "#ffffff", "center", 600);
    // Le quattro famiglie di personaggi: si cambiano dal vivo, i due si trasformano lì sotto.
    const n = PERSONAGGI_CORSA.length, wt = Math.min(130 * S, (W - 32 - (n - 1) * 8) / n), xt = W / 2 - (n * wt + (n - 1) * 8) / 2;
    PERSONAGGI_CORSA.forEach(([st, nome], i) => {
      const scelto = st === stile, chiuso = st && !libero("guerrieri");
      tastoUI(xt + i * (wt + 8), top + 72 * S, wt, 30 * S, (chiuso ? "\u{1F512} " : "") + dici(nome), () => { if (!scelto) comandi.stile(st); },
              { colore: scelto ? ORO : "#2a2735", scritta: scelto ? "#17171c" : "#ffffff", px: 12 * S, bordo: scelto ? null : "rgba(255,255,255,.25)" });
    });
    // Sopra la testa di ognuno, il suo tasto.
    for (const f of lottatori) {
      if (!f.p || f.fuoriCampo) continue;
      const x = f.p.testa.x, y = Math.max(top + 130 * S, f.p.testa.y - 52 * S), w = 140 * S;
      tastoUI(x - w / 2, y - 17 * S, w, 34 * S, dici("Gioca con") + " " + nomeDi(f.tipo), () => scegliEroe(f.tipo), { brilla: true, px: 13 * S });
    }
    const yb = pavimento - 34 * S;
    if (recordCorsa) scriviUI(dici("Il tuo record") + ": " + cifre(recordCorsa), W / 2, yb - 26 * S, 12 * S, ORO, "center");
    const tasti = [[dici("Bottega") + " \u{1FA99} " + cifre(banca), () => { c.bottega = true; }]]
      .concat(sulSito ? [[dici("Classifica"), () => apriClassifica(true)]] : [], [[dici("Esci"), () => chiudiCorsa()]]);
    const wb = Math.min(140 * S, (W - 32 - (tasti.length - 1) * 10) / tasti.length), xb = W / 2 - (tasti.length * wb + (tasti.length - 1) * 10) / 2;
    tasti.forEach(([t, fa], i) => tastoUI(xb + i * (wb + 10), yb - 14 * S, wb, 30 * S, t, fa, { colore: "#2a2735", scritta: "#ffffff", bordo: "rgba(255,255,255,.3)", px: 12 * S }));
    if (c.bottega) { tastiUI = []; disegnaBottega(); }            // la bottega copre tutto: sotto non si tocca niente
  }
  // Una carta: il premio o l'oggetto del negozio.
  function carta(x, y, w, h, icona, nome, sopra, testo, bordo) {
    pannelloUI(x, y, w, h, 12 * S, bordo);
    const u = Math.min(1, w / (170 * S));
    scriviUI(icona, x + w / 2, y + 34 * S * u, 34 * S * u, "#ffffff", "center");
    scriviUI(nome, x + w / 2, y + 70 * S * u, 14 * S * u, "#ffffff", "center", 900);
    if (sopra) scriviUI(sopra, x + w / 2, y + 90 * S * u, 11 * S * u, ORO, "center", 800);
    const righe = righeUI(testo, w - 16 * S, 11 * S * u);
    righe.slice(0, 4).forEach((r, i) => scriviUI(r, x + w / 2, y + (112 + 15 * i) * S * u, 11 * S * u, GRIGIO_UI, "center", 600));
  }
  // Che cosa dice una carta: arma nuova, livello, evoluzione, potenziamento.
  function infoCarta(k) {
    const c = corsa;
    if (k.arma) {
      const A = ARMI_CORSA[k.arma], l = c.armi[k.arma] || 0;
      if (k.evo) return { icona: A.icona, nome: dici(A.evo), sopra: dici("Evoluzione!"), testo: dici("Al massimo, e oltre"), bordo: "#ff62d6" };
      return { icona: A.icona, nome: dici(A.nome), sopra: l ? dici("Livello") + " " + (l + 1) : dici("Arma nuova"), testo: dici(A.testi[l]), bordo: ORO };
    }
    if (k.potere) { const P = POTERI[k.potere], l = livello(k.potere); return { icona: P.icona, nome: dici(P.nome), sopra: l ? dici("Livello") + " " + (l + 1) : dici("Nuovo"), testo: P.testo(l), bordo: coloreCorsa() }; }
    if (k.monete) return { icona: "\u{1FA99}", nome: "+" + k.monete, sopra: "", testo: dici("Monete"), bordo: ORO };
    if (k.vita) return { icona: "\u{1F496}", nome: dici("Una vita in più"), sopra: "", testo: "+1 " + dici("vita"), bordo: "#ff4d6d" };
    return { icona: "\u{1FA79}", nome: dici("Rimessa a nuovo"), sopra: "", testo: dici("Vita al massimo"), bordo: "#7dffb0" };
  }
  function velo(a) { ctx.save(); ctx.fillStyle = "rgba(10,8,22," + a + ")"; ctx.fillRect(0, 0, W, H); ctx.restore(); }
  function disegnaLivello() {
    tastiUI = [];                                                  // sotto il velo non si tocca niente
    const c = corsa, carte = c.scelta.carte, n = carte.length, gap = 12 * S, w = Math.min(180 * S, (W - 32 - (n - 1) * gap) / n), h = Math.min(220 * S, w * 1.25 + 20 * S);
    const y = Math.max(testataBasso + 120 * S, H * 0.42 - h / 2), x0 = W / 2 - (n * w + (n - 1) * gap) / 2;
    velo(0.55);
    titoloMenu(dici("Livello") + " " + c.scelta.liv + "!", y - 30 * S);
    carte.forEach((k, i) => {
      const I = infoCarta(k), x = x0 + i * (w + gap);
      ctx.save();
      if (k.evo) { ctx.shadowColor = "#ff62d6"; ctx.shadowBlur = (14 + 8 * Math.sin(passi * 0.2)) * S; }
      carta(x, y, w, h, I.icona, I.nome, I.sopra, I.testo, I.bordo);
      ctx.restore();
      tastiUI.push({ x, y, w, h, fa: () => prendiCarta(i) });
    });
  }
  function disegnaForziere() {
    tastiUI = [];
    const F = corsa.forziere, cx = W / 2, cy = Math.max(testataBasso + 150 * S, H * 0.36);
    F.t++;
    velo(0.6);
    // I raggi che girano dietro al forziere.
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(passi * 0.01);
    for (let i = 0; i < 12; i++) { ctx.rotate(Math.PI / 6); ctx.fillStyle = i % 2 ? "rgba(255,216,74,.18)" : "rgba(255,255,255,.08)"; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-18 * S, -170 * S); ctx.lineTo(18 * S, -170 * S); ctx.closePath(); ctx.fill(); }
    ctx.restore();
    const salta = Math.max(0, 1 - F.t / 20);
    scriviUI("\u{1F381}", cx, cy - 10 * S - 20 * S * salta, (54 + 10 * Math.sin(passi * 0.15)) * S, "#ffffff", "center");
    titoloMenu(dici("Forziere!"), cy - 80 * S);
    const righe = F.premi.map(infoCarta), w = Math.min(300 * S, W - 32);
    righe.forEach((I, i) => {
      const y = cy + 50 * S + i * 34 * S;
      if (F.t < 14 + i * 10) return;                                // escono uno alla volta
      pannelloUI(cx - w / 2, y - 14 * S, w, 28 * S, 8 * S, I.bordo);
      scriviUI(I.icona, cx - w / 2 + 18 * S, y, 15 * S, "#ffffff", "center");
      scriviUI(I.nome + (I.sopra ? "  ·  " + I.sopra : ""), cx - w / 2 + 34 * S, y, 12 * S, "#ffffff", "left", 800);
    });
    const yb = cy + 50 * S + righe.length * 34 * S;
    scriviUI("+" + F.monete + " \u{1FA99}", cx, yb + 4 * S, 14 * S, ORO, "center");
    if (F.t > 14 + righe.length * 10) tastoUI(cx - 70 * S, yb + 22 * S, 140 * S, 34 * S, dici("Avanti") + " ▶", () => chiudiForziere(), { brilla: true, px: 14 * S });
  }
  function disegnaBottega() {
    const ids = Object.keys(BOTTEGA), w = Math.min(460 * S, W - 24), rh = 38 * S, h = 70 * S + ids.length * rh + 50 * S;
    const x = W / 2 - w / 2, y = Math.max(testataBasso + 10 * S, H / 2 - h / 2);
    velo(0.5);
    pannelloUI(x, y, w, h, 14 * S, ORO);
    scriviUI(dici("Bottega"), W / 2, y + 24 * S, 20 * S, ORO, "center", 900);
    scriviUI(dici("Monete in banca") + ": \u{1FA99} " + cifre(banca), W / 2, y + 48 * S, 12 * S, "#ffffff", "center", 700);
    ids.forEach((id, i) => {
      const B = BOTTEGA[id], l = bottega[id] || 0, yy = y + 70 * S + i * rh, pieno = l >= B.max, p = costoBottega(id);
      scriviUI(B.icona, x + 22 * S, yy + rh / 2, 16 * S, "#ffffff", "center");
      scriviUI(dici(B.nome), x + 40 * S, yy + rh / 2 - 6 * S, 12 * S, "#ffffff", "left", 800);
      scriviUI(dici(B.testo), x + 40 * S, yy + rh / 2 + 8 * S, 10 * S, GRIGIO_UI, "left", 600);
      for (let k = 0; k < B.max; k++) { ctx.fillStyle = k < l ? ORO : "rgba(255,255,255,.2)"; ctx.fillRect(x + w - 150 * S + k * 9 * S, yy + rh / 2 - 3 * S, 6 * S, 6 * S); }
      tastoUI(x + w - 92 * S, yy + 6 * S, 80 * S, rh - 12 * S, pieno ? dici("Al massimo") : "\u{1FA99} " + cifre(p), () => compraBottega(id), { spento: pieno || banca < p, px: 11 * S });
    });
    tastoUI(W / 2 - 60 * S, y + h - 42 * S, 120 * S, 30 * S, dici("Chiudi"), () => { corsa.bottega = false; }, { colore: "#2a2735", scritta: "#ffffff", bordo: "rgba(255,255,255,.3)", px: 12 * S });
  }
  function titoloMenu(t, y) {
    caratteri(24 * S, 900); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineWidth = 5 * S; ctx.strokeStyle = "#17171c"; ctx.fillStyle = "#ffffff";
    ctx.strokeText(t, W / 2, y); ctx.fillText(t, W / 2, y);
  }
  function disegnaFine() {
    const c = corsa, w = Math.min(440 * S, W - 24), x = W / 2 - w / 2, y = testataBasso + 16 * S;
    const lista = sulSito ? 10 : 0, h = (sulSito ? 216 : 166) * S + lista * 20 * S;
    pannelloUI(x, y, w, h, 14 * S, coloreCorsa());
    scriviUI(dici("La corsa è finita"), W / 2, y + 26 * S, 22 * S, "#ffffff", "center", 900);
    scriviUI(dici("Round") + " " + c.round + "  ·  " + cifre(c.punti) + " " + dici("punti") + "  ·  " + c.uccisi + " " + dici("nemici"), W / 2, y + 52 * S, 13 * S, ORO, "center");
    scriviUI(c.record ? dici("Nuovo record!") : dici("Il tuo record") + ": " + cifre(recordCorsa), W / 2, y + 72 * S, 12 * S, c.record ? "#7dffb0" : GRIGIO_UI, "center", 700);
    scriviUI(dici("Liv.") + " " + c.liv + "  ·  +" + (c.inBanca || 0) + " \u{1FA99} " + dici("in banca") + " (" + cifre(banca) + ")", W / 2, y + 92 * S, 12 * S, ORO, "center", 700);
    let yy = y + 112 * S;
    if (sulSito) {
      c.yNome = yy - 4 * S; posizionaNome();
      const msg = c.inviato === "fatto" ? (c.posizione ? dici("Sei in classifica, posizione") + " " + c.posizione : dici("Inviato!"))
        : c.inviato === "invio" ? dici("Invio…") : c.erroreInvio ? dici(c.erroreInvio) : "";
      if (msg) scriviUI(msg, W / 2, yy + 46 * S, 12 * S, c.erroreInvio && !c.inviato ? "#ff8a80" : "#7dffb0", "center", 700);
      disegnaClassifica(W / 2, yy + 62 * S, w - 24 * S, false);
      yy += 70 * S + lista * 20 * S + 26 * S;
    } else {
      scriviUI(dici("La classifica globale è sul sito."), W / 2, yy + 4 * S, 11 * S, GRIGIO_UI, "center", 600);
      yy += 30 * S;
    }
    tastoUI(W / 2 - 130 * S, yy, 120 * S, 34 * S, dici("Ancora"), () => ricominciaCorsa(), { brilla: true, px: 14 * S });
    tastoUI(W / 2 + 10 * S, yy, 120 * S, 34 * S, dici("Esci"), () => chiudiCorsa(), { colore: "#2a2735", scritta: "#ffffff", bordo: "rgba(255,255,255,.3)", px: 14 * S });
  }
  // La classifica: i primi dieci, aggiornati da soli ogni dieci secondi.
  function disegnaClassifica(cx, y, w, finestra) {
    if (finestra) {
      if (passi - classifica.letta > 600) caricaClassifica();
      pannelloUI(cx - w / 2, y, w, 290 * S, 14 * S, ORO);
      scriviUI(dici("Classifica globale"), cx, y + 24 * S, 18 * S, ORO, "center", 900);
      y += 44 * S;
      tastoUI(cx - 60 * S, y + 222 * S, 120 * S, 30 * S, dici("Chiudi"), () => apriClassifica(false), { colore: "#2a2735", scritta: "#ffffff", bordo: "rgba(255,255,255,.3)", px: 12 * S });
    }
    const voci = classifica.voci;
    if (!voci) { scriviUI(classifica.stato === "errore" ? dici("Classifica non raggiungibile") : dici("Carico la classifica…"), cx, y + 20 * S, 12 * S, GRIGIO_UI, "center", 600); return; }
    if (!voci.length) { scriviUI(dici("Nessuno ancora: sii il primo!"), cx, y + 20 * S, 12 * S, GRIGIO_UI, "center", 600); return; }
    voci.slice(0, 10).forEach((v, i) => {
      const yy = y + 10 * S + i * 20 * S, mia = classifica.mia >= 0 && v.id === classifica.mia;
      if (mia) { ctx.fillStyle = "rgba(255,216,74,.18)"; ctx.fillRect(cx - w / 2 + 4 * S, yy - 9 * S, w - 8 * S, 18 * S); }
      scriviUI((i + 1) + ".", cx - w / 2 + 14 * S, yy, 12 * S, i < 3 ? ORO : GRIGIO_UI, "left");
      scriviUI(String(v.nome || "?").slice(0, 16), cx - w / 2 + 42 * S, yy, 12 * S, "#ffffff", "left", 700);
      scriviUI("R" + (v.round || 0), cx + w * 0.14, yy, 11 * S, GRIGIO_UI, "center", 700);
      scriviUI(cifre(v.punti || 0), cx + w / 2 - 14 * S, yy, 12 * S, ORO, "right");
    });
  }
  // Il tocco sui tasti della corsa: l'ultimo disegnato sopra vince.
  function tastoCorsa(x, y) {
    for (let i = tastiUI.length - 1; i >= 0; i--) { const t = tastiUI[i]; if (x >= t.x && x <= t.x + t.w && y >= t.y && y <= t.y + t.h) return t; }
    return null;
  }
  // I menu prendono tutti i tocchi: sotto non si afferra nessuno.
  const corsaModale = () => !!(classifica.aperta || (corsa && (corsa.fase === "scelta" || corsa.fase === "fine" || corsa.scelta || corsa.forziere)));

  window.__ring = {
    // Solo per i test: il conto dei K.O., una creatura, una nube.
    punti: (robot, mela) => { punteggio.robot = robot; punteggio.mela = mela; },
    creatura: (el, per, x) => { nuovaCreatura(el, x === undefined ? W / 2 : x, pavimento - 40 * S, per); },
    nube: (x, per) => { nubi.push({ x, y: pavimento - 30 * S, t: 0, per: per || null }); },
    // Solo per i test: un telefono lanciato a mano.
    proiettile: (x, y, vx, vy, da) => { const f = lottatori.find((l) => l.tipo === da) || null; proiettili.push({ x, y, vx, vy, da: f, vita: 140 }); return proiettili.length; },
    lanciaTelefono: (x, y, vx, vy, forma) => { const t = nuovoTelefono(x, y, vx, vy, forma); t.stato = "volo"; t.cool = 0; t.armato = !!SPECIALI[t.tipo]; return telefoni.indexOf(t); },
    tempo: (secondi) => { tempo = Math.round(secondi * 60); },
    dai: (tipo, forma) => {
      const f = lottatori.find((l) => l.tipo === tipo);
      if (!f) return;
      const t = nuovoTelefono(f.p.manoA.x, f.p.manoA.y, 0, 0, forma);
      if (eArma(t)) { if (f.arma) lasciaArma(f); t.stato = "impugnato"; t.da = f; f.arma = t; f.colpiArma = CARICHE[forma] || 5; }
      else { t.stato = "portato"; t.da = f; f.tel = t; }
      return eArma(t) ? "arma" : "oggetto";
    },
    afferra: (tipo, mossa) => {
      const f = lottatori.find((l) => l.tipo === tipo), altro = lottatori.find((l) => l.tipo !== tipo);
      if (!f || !altro || altro.ko || altro.esploso) return false;
      inizia(f, "presa"); if (mossa) { f.mossaPresa = mossa; f.durata = DURATE_PRESA[mossa]; }
      f.t = 10; agguanta(f, altro); return true;
    },
    duo: () => { const m = lottatori.find((l) => l.tipo === "mela"); if (m && !m.ko) { m.pensa = 0; prossimoDuo = 0; inizia(m, "estrai"); } },
    esplodi: (tipo) => { const f = lottatori.find((l) => l.tipo === (tipo || "robot")), a = lottatori.find((l) => l.tipo !== (tipo || "robot")); if (f) esplodiLottatore(f, a); },
    paracadute: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) f.scendeApposta = 300; },
    comandi,
    // Solo per i test: un lottatore spostato di peso a un'altra x, fermo dov'è.
    sposta: (tipo, x) => { const f = lottatori.find((l) => l.tipo === tipo); if (!f || !f.p) return; const dx = x - f.cx; for (const n in f.p) { f.p[n].x += dx; f.p[n].ox = f.p[n].x; } f.cx = x; f.azione = null; f.ordine = null; },
    // Il controller radiale: aperto o chiuso, e un comando dato a mano.
    radiale: (apri) => { apriRadiale(apri); }, ordina: (tipo, id) => { const f = lottatori.find((l) => l.tipo === tipo); return !!(f && ordina(f, id)); },
    // Solo per i test: il colpo finale a comando (chi lo dà e quale), e il round buono.
    fatale: (chi, tipo) => { const f = lottatori.find((l) => l.tipo === chi), a = lottatori.find((l) => l.tipo !== chi); if (!f || !a || !puoFinire(f, a, true)) return false; a.danni = Math.max(a.danni, a.soglia - 1); avviaFatale(f, a, tipo); return true; },
    roundFatale: (si) => { fataleRound = !!si; },
    // Solo per i test: il buco nero dove si vuole.
    buco: (x, y) => { avviaBuco(x, y); },
    // Solo per i test: una mossa in coppia a comando (la comincia `chi`), e l'attesa fra una e l'altra.
    coppia: (tipo, chi, dove) => { const f = lottatori.find((l) => l.tipo === chi), a = lottatori.find((l) => l.tipo !== chi); return !!(f && a && coppia(tipo, f, a, dove)); },
    coppiaAttesa: (n) => { if (orda) orda.coppiaAttesa = n; },
    // Solo per i test: la ricetta di un'ondata da un seme, e un'orda col seme scelto.
    ricettaOndata: (n, seme) => { const rng = generatore(seme); let r = null; for (let i = 1; i <= n; i++) r = ricettaOndata(i, rng); return { tema: r.tema, arrivo: r.arrivo, insieme: r.insieme, coda: r.coda.map((v) => v.tipo + (v.lato < 0 ? "<" : ">") + v.attesa) }; },
    orda: (ondate, seme) => { avviaOrda(ondate, seme); },
    zombie: (tipo, x) => { if (orda) { nuovoZombie(tipo, x < orda.cx ? -1 : 1); const z = orda.zombie[orda.zombie.length - 1]; z.x = x; z.stato = "va"; z.s = 0; } },
    // Solo per i test: la spinta di un lottatore nello scontro, e l'energia che ha.
    spinta: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); return f ? spintaDi(f) : 0; },
    energia: (tipo, ki) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) f.ki = ki; },
    tifa: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); return !!(f && tifa(f)); },
    // Solo per i test: un colpo secco dell'uno all'altro; dice di quanto sono saliti i danni.
    colpo: (da, a) => {
      const f = lottatori.find((l) => l.tipo === da), g = lottatori.find((l) => l.tipo === a);
      if (!f || !g || g.esploso) return 0;
      const prima = g.danni + (g.koVero ? 100 : 0);
      colpisci(f, g, 4, g.p.collo.x, g.p.collo.y);
      return g.danni + (g.koVero ? 100 : 0) - prima;
    },
    // Solo per i test: fa partire una mossa a un lottatore, a piena energia.
    mossa: (tipo, azione) => {
      const f = lottatori.find((l) => l.tipo === tipo), a = lottatori.find((l) => l.tipo !== tipo);
      if (!f || !a) return false;
      f.dir = a.p.bacino.x >= f.p.bacino.x ? 1 : -1; f.ki = 100; f.pensa = 0;
      inizia(f, azione); return true;
    },
    incanta: (tipo, cosa) => {
      const f = lottatori.find((l) => l.tipo === tipo), a = lottatori.find((l) => l.tipo !== tipo);
      if (!f) return;
      if (cosa === "gelo") congela(f, a, f.p.collo.x, f.p.collo.y); else rimpicciolisci(f, a, f.p.collo.x, f.p.collo.y);
    },
    smembra: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) smembra(f, f.p.bacino.x, f.p.bacino.y); },
    // Solo per i test: stacca proprio quegli arti ("gA", "gD", "A", "D"), e sceglie se volare o strisciare.
    stacca: (tipo, arti, piano) => {
      const f = lottatori.find((l) => l.tipo === tipo);
      if (!f) return;
      for (const k of arti) { if (ARTI[k] && !f.staccati[k]) { f.staccati[k] = 1; if (k === "A" && f.arma) lasciaArma(f); } }
      if (f.tel) lasciaCadere(f);
      f.piano = piano || null; f.pensa = 4;
    },
    riattacca: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) { f.staccati = {}; f.piano = null; arti = arti.filter((a) => a.f !== f); } },
    mordi: () => { const f = lottatori.find((l) => l.tipo === "mela"); if (f) { const c = corpoMela(f.p); mordi(f, c.x + c.R, c.y); } },
    scatta: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo), a = lottatori.find((l) => l.tipo !== tipo); if (f && a) scatta(f, a, 30); },
    rush: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) { f.ki = Math.max(f.ki, 20); inizia(f, "rush"); } },
    taglia: () => { const f = lottatori.find((l) => l.tipo === "mela"); return !!(f && taglia(f, null)); },
    scoppia: (x, y, inPieno) => esplosione(x, y, 1.15, null, !!inPieno),
    ko: (tipo) => { const f = lottatori.find((l) => l.tipo === tipo), a = lottatori.find((l) => l.tipo !== tipo); if (f && a) segnaKO(a, f); },
    danneggiaStriscia: (x, forza) => danneggiaStriscia(x, forza),
    rompiTelefono: (i, n) => { const t = telefoni[i]; if (!t) return null; for (let k = 0; k < n; k++) { t.crepe = Math.min(5, t.crepe + 1); rompiSchermo(t); } t.va = 0; t.a = 0; t.stato = "libero"; return { x: t.x, y: t.y, w: t.w, h: t.h }; },
    cervello: () => JSON.parse(JSON.stringify(cervello)),
    livello: (tipo) => livelloDi(tipo),
    impara: (tipo, mossa, esito, esp) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) impara(f, mossa, esito, esp); },
    decolla: (tipo, impazzito) => { const f = lottatori.find((l) => l.tipo === tipo); if (f) decolla(f, !!impazzito); },
    avviaEvento: (nome) => { prossimoEvento = 1e9; prossimaOrda = 1e9; if (nome === "luna") { moltG = 0.45; evento = { nome, durata: 620 }; } },
    danneggiaBordo: (lato, pos, forza) => danneggiaBordo(lato, pos, forza),
    // Solo per le prove: suona tutti i suoni in fila dentro un contesto dato (un OfflineAudioContext), per ascoltarli e misurarli.
    provaSuoni: (c, gap) => {
      const prima = [audio.ctx, audio.uscita, audio.rumore];
      const g = c.createGain(), comp = c.createDynamicsCompressor();
      g.gain.value = AUDIO.volume; g.connect(comp); comp.connect(c.destination);
      const n = Math.floor(c.sampleRate), buf = c.createBuffer(1, n, c.sampleRate), d = buf.getChannelData(0);
      for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
      audio.ctx = c; audio.uscita = g; audio.rumore = buf;
      const nomi = Object.keys(SUONI_AUDIO);
      try { nomi.forEach((nome, i) => SUONI_AUDIO[nome][1](c, canaleAudio(W / 2), 0.1 + i * gap, VOLUMI_AUDIO[nome] || 1)); }
      finally { audio.ctx = prima[0]; audio.uscita = prima[1]; audio.rumore = prima[2]; }
      return nomi;
    },
    // Solo per i test: la corsa senza toccare il canvas.
    corsa: {
      apri: (seme) => { const ok = apriCorsa(); if (corsa && seme) corsa.semeVoluto = seme; return ok; },
      scegli: (tipo) => scegliEroe(tipo), carta: (i) => prendiCarta(i), compra: (id) => compraBottega(id), bottega: (si) => { if (corsa) corsa.bottega = !!si; },
      esperienza: (n) => { if (corsa && corsa.chi) daiEsperienza(n); }, arma: (id, l) => { if (corsa && corsa.chi) corsa.armi[id] = l; },
      potere: (id, l) => { if (corsa && corsa.chi) corsa.livelli[id] = l; }, lascia: (id) => { const f = eroe(); if (f && corsa.chi) lasciaOggetto(f.p.bacino.x, f.p.bacino.y - 30 * S, id); },
      forziere: () => { if (corsa && corsa.chi) apriForziere(); }, salta: (n) => { if (corsa && corsa.chi) corsa.round = n - 1; }, chiudiForziere: () => chiudiForziere(), banca: (n) => { if (n !== undefined) { banca = n; salvaBottega(); } return banca; },
      usa: (i) => usaOggetto(i), finale: () => tastoFinale(), ferisci: (n) => { if (corsa) corsa.invuln = 0; return feritaEroe(n, W / 2, pavimento - 40 * S); },
      vinci: () => vinciRound("prova"), prossimo: (tipo) => { if (corsa) corsa.prossimoTipo = tipo; }, finisci: () => finisciCorsa(), chiudi: () => chiudiCorsa(),
      monete: (n) => { if (corsa) corsa.monete = n; }, energia: (n) => { if (corsa) corsa.energia = n; }, dai: (id, i) => { if (corsa) corsa.slot[i || 0] = id; },
      tocca: (x, y) => { const t = tastoCorsa(x, y); if (t) t.fa(); return !!t; }, tasti: () => tastiUI.map((t) => ({ x: t.x, y: t.y, w: t.w, h: t.h })),
    },
    // Solo per i test: apri la mira, spostala a un'altezza, spara.
    mira: (tipo) => avviaMira(lottatori.find((l) => l.tipo === tipo) || lottatori[0]),
    // punta la linea verso un punto della finestra e la ferma lì
    miraA: (x, y) => {
      if (!mira) return false;
      const o = origineMira(mira);
      mira.dir = x >= o.x ? 1 : -1; mira.da.dir = mira.dir;
      mira.a = Math.max(-MIRA.su, Math.min(MIRA.giu, Math.atan2(y - o.y, Math.abs(x - o.x)))); mira.v = 0;
      return true;
    },
    spara: () => sparaMira(),
    stato: () => ({ telefoni: telefoni.map((t) => ({ x: t.x, y: t.y, stato: t.stato, tipo: t.tipo })),
    danniBordi: danniBordi.map((d) => d.lato), verso, barreVita, anime, stile, fulmini: fulmini.length, duello,
    tempo, pezzi: pezzi.length, proiettili: proiettili.length,
    sfereGrandi: proiettili.filter((b) => b.grande && !b.razzo).length, razzi: proiettili.filter((b) => b.razzo).length, dischi: proiettili.filter((b) => b.disco).length, gettoni, scommessa: scommessa ? Object.assign({}, scommessa) : null,
    fatale: fatale ? { tipo: fatale.tipo, fase: fatale.fase, t: fatale.t, da: fatale.da.tipo, a: fatale.a.tipo, contato: fatale.contato,
                       r: fatale.d && fatale.d.r ? fatale.d.r : 0 } : null,
    fataleRound, fataliFatti, fataleBuio, fataleVoluto, fataleDebito,
    corsa: corsa ? { fase: corsa.fase, chi: corsa.chi, round: corsa.round, tipo: corsa.tipo, tipi: (corsa.tipi || []).slice(), vite: corsa.vite, hp: corsa.hp, hpMax: corsa.hpMax,
                     energia: corsa.energia, ultima: corsa.ultima, monete: corsa.monete, punti: corsa.punti, uccisi: corsa.uccisi, livelli: Object.assign({}, corsa.livelli),
                     slot: (corsa.slot || []).slice(), variante: corsa.variante ? corsa.variante.slice() : null, liv: corsa.liv, xp: corsa.xp, pausa: !!corsa.pausa,
                     armi: Object.assign({}, corsa.armi || {}), carte: corsa.scelta ? corsa.scelta.carte.map((k) => k.arma ? (k.evo ? "evo:" : "arma:") + k.arma : k.potere ? "potere:" + k.potere : k.monete ? "monete" : k.vita ? "vita" : "cura") : null,
                     forziere: corsa.forziere ? corsa.forziere.premi.length : 0, gemme: (corsa.gemme || []).length, aTerra: (corsa.aTerra || []).map((o) => o.id), forzieri: (corsa.forzieri || []).length,
                     onde: (corsa.onde || []).length, dardi: (corsa.dardi || []).length, lame: (corsa.lame || []).length, telefoni: corsa.telefoni ? corsa.telefoni.length : 0, bottega: !!corsa.bottega,
                     imprevisti: (corsa.imprevisti || []).slice(), invuln: corsa.invuln || 0, scudo: corsa.scudo || 0, scadenza: corsa.scadenza || 0,
                     tasti: tastiUI.length, modale: corsaModale() } : null,
    classifica: { aperta: classifica.aperta, voci: classifica.voci ? classifica.voci.length : null }, recordCorsa, banca, bottega: Object.assign({}, bottega),
    audio: { acceso: audio.acceso, pronto: !!audio.ctx, anelli: Object.keys(audio.anelli).filter((k) => audio.anelli[k]) },
    mira: mira ? (() => { const o = origineMira(mira), e = fineMira(o, mira.dir, mira.a);
                          return { a: mira.a, v: mira.v, dir: mira.dir, t: mira.t, da: mira.da.tipo, resta: Math.max(0, MIRA.attesa - mira.t), ox: o.x, oy: o.y, fx: e.x, fy: e.y }; })() : null,
    lampoMira: lampoMira ? { ox: lampoMira.ox, oy: lampoMira.oy, fx: lampoMira.fx, fy: lampoMira.fy, t: lampoMira.t, preso: lampoMira.preso } : null,
    buco: buco ? { x: buco.x, y: buco.y, r: buco.r, fase: buco.fase, dentro: buco.dentro.map((d) => d.tipo), passati: buco.passati, uscita: doveEsce(buco.x, buco.y) } : null,
    arti: arti.length, macchie: macchie.length, acquazzone, natale, uragano: !!uragano, cruento, ritmo,
    pioggia: gocce.length, pioggiaInFondo: gocce.reduce((n, g) => n + (g.y > pavimento * 0.7 ? 1 : 0), 0), piovendo, bagnato, sisma: sisma ? { t: sisma.t, x: sisma.x, alto: sisma.alto, forza: sisma.k } : null,
    lapilli: lapilli.length, colate: colate.length, meteore: meteore.map((m) => ({ x: m.x, y: m.y, bx: m.bx, by: m.by, grossa: m.grossa })),
    sciame: sciame ? sciame.resta : 0, bruciature: bruciature.length, trema: radiceTrema(),
    orda: orda ? { fase: orda.fase, t: orda.t, base: orda.base, cx: orda.cx, nati: orda.nati, uccisi: orda.uccisi, lati: Object.assign({}, orda.lati),
                   ondata: orda.ondata, ondate: orda.ondate, superate: orda.superate, seme: orda.seme, vite: orda.vite, traslochi: orda.traslochi || 0, l: orda.l, r: orda.r,
                   coppie: Object.assign({}, orda.coppie), coppiaAttesa: orda.coppiaAttesa, latiDi: Object.assign({}, orda.lati),
                   ricetta: orda.ricetta ? { tema: orda.ricetta.tema, arrivo: orda.ricetta.arrivo, totale: orda.ricetta.totale, insieme: orda.ricetta.insieme, restano: orda.ricetta.coda.length } : null,
                   zombie: orda.zombie.map((z) => ({ x: z.x, stato: z.stato, hp: z.hp, lato: z.lato, tipo: z.tipo })) } : null, primatoOrda,
    radiale: (() => { const g = lottatori.length ? geometriaRadiale() : { x: 0, y: 0, centro: 0, spicchi: [], largo: 0 };
                      return { aperto: radiale.aperto, apre: radiale.apre, chi: radiale.chi, lato: radiale.lato, x: g.x, y: g.y, centro: g.centro, largo: g.largo, voci: vociRadiale().map((v) => v[0]),
                               spicchi: g.spicchi.map((q) => ({ x: q.x, y: q.y, giro: q.giro })),
                               accese: vociRadiale().map((v) => puoFare(comandato(), v)) }; })(),
    sfida: sfida ? { tasti: (tastiSfida() || []).map((b) => ({ x: b.x, y: b.y, r: b.r })), mano: (sfida.mano || [0, 0]).slice(),
                     tipo: sfida.tipo, u: sfida.u, t: sfida.t, fiato: sfida.fiato.slice(), spinte: sfida.spinte.slice(), x: sfida.x, y: sfida.y,
                     strattoni: sfida.strattoni.slice(), primo: sfida.primo,
                     sinistra: sfida.a.tipo, destra: sfida.b.tipo } : null, ultimaSfida: ultimaSfida ? Object.assign({}, ultimaSfida) : null,
    particelleTipi: particelle.reduce((m, q) => { m[q.tipo] = (m[q.tipo] || 0) + 1; return m; }, {}),
    costume, particelle: particelle.length, danniStriscia: danni.length,
    campoRicerca: !!document.querySelector(".ricerca-grande input"), evento: evento ? evento.nome : null, moltG,
    lottatori: lottatori.map((f) => ({
    danni: f.danni, tel: !!f.tel, arma: f.arma ? f.arma.tipo : null, colpiArma: f.colpiArma, furia: f.furia, vola: f.jet > 0, caos: f.caos > 0,
    arma: f.arma ? f.arma.tipo : null, tiene: !!f.tiene, tenuto: !!f.tenuto, paracadute: !!f.paracadute,
    ballo: f.azione === "balla" ? f.ballo : null, esploso: !!f.esploso,
    segni: f.segni ? f.segni.length : 0, staccati: Object.keys(f.staccati || {}).filter((k) => f.staccati[k]),
    ki: f.ki, potenziato: f.potenziato > 0, onda: !!f.onda, vita: vitaVera(f),
    forma: f.potenziato > 0 ? f.forma : 0, gelato: f.gelato > 0, piccolo: f.piccolo > 0, scala: f.scala,
    lama: lamaPronta(f), lamaLanciata: !!(f.lama && f.lama.lanciata), soglia: f.soglia,
    morsi: f.morsi ? f.morsi.length : 0, tagliata: !!f.taglio, volo: !!(f.volo && f.jet > 0),
    trasformazione: formaDi(f), mutato: !!f.mutato, sferaR: f.sfera ? f.sfera.r : 0,
    coppia: f.coppia ? f.coppia.tipo : null, alto: f.coppia ? f.coppia.h : 0, fuoriCampo: !!f.fuoriCampo, inScena: !!(fatale && (f === fatale.da || f === fatale.a)), fatVola: !!f.fatVola, schiacciato: f.schiacciato || 0, alza: f.alza || 0,
    gambe: gambe(f), braccia: braccia(f), striscia: striscia(f), piano: f.piano, cx: f.cx, trema: f.trema > 0, risposta: !!f.risposta, ordine: f.ordine ? f.ordine.azione : null,
    accecato: f.accecato > 0, cratere: !!(f.cratere && !f.cratere.attesa), sfera: !!f.sfera,
    sollevato: !!(f.tenuto && f.tenuto.tele !== undefined),
    tipo: f.tipo, ko: f.ko, azione: f.azione, preso: !!f.preso,
    scalando: !!f.scalata, base: f.base, sopraUnElemento: !!f.supporto,
    testa: { x: f.p.testa.x, y: f.p.testa.y }, bacino: { x: f.p.bacino.x, y: f.p.bacino.y },
    collo: { x: f.p.collo.x, y: f.p.collo.y }, piede: { x: f.p.piedeA.x, y: f.p.piedeA.y },
    // Tutti i punti del corpo, per misurare le posture nei test.
    punti: Object.keys(f.p).reduce((m, n) => { m[n] = [f.p[n].x, f.p[n].y]; return m; }, {}),
    ginocchiaViste: (eMela(f) ? [f.p.piedeA, f.p.piedeD].map((pd) => {
      const dx = pd.x - f.p.bacino.x, dy = pd.y - f.p.bacino.y, lun = Math.hypot(dx, dy) || 1;
      let nx = -dy / lun; let ny = dx / lun; if (nx * f.dir < 0) { nx = -nx; ny = -ny; }
      return { x: f.p.bacino.x + dx / 2 + nx * 0.14 * lun, y: f.p.bacino.y + dy / 2 + ny * 0.14 * lun };
    }) : ginocchia(f)).map((g) => [g.x, g.y]),
    fuori: f.fuori || 0, tenuto: !!f.tenuto,
    dir: f.dir, forza: f.forza, stordito: f.stordito, rialzo: f.rialzo, inVolo: f.inVolo, fantasma: f.fantasma,
  })), punteggio: Object.assign({}, punteggio), pavimento, testataBasso, larghezza: W, altezza: H, scala: S,
    creature: creature.map((c) => ({ el: c.el, x: c.x, y: c.y, per: c.per, colpo: c.colpo })), nubi: nubi.length,
    finale: finale ? { tipo: finale.tipo, t: finale.t, uscito: !!finale.lampo, lancio: !!finale.perso } : null,
    ostacoli: ostacoli.length, riquadri: ostacoli.map((o) => [o.l, o.t, o.r, o.b].map(Math.round)) }) };
})();
