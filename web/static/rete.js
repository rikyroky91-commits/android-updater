/* La trama di rete dietro la pagina.
 *
 * È l'elemento del prototipo che con Streamlit non si poteva fare in
 * nessun modo: gli script venivano rimossi dall'HTML iniettato, e un
 * componente vero sarebbe finito dentro un iframe — cioè DENTRO la
 * pagina, non dietro, che è l'opposto di uno sfondo. Qui la pagina è
 * nostra e il canvas sta dove deve stare.
 *
 * Due scelte deliberate rispetto al prototipo:
 *
 * 1. NON GIRA DI CONTINUO. Il prototipo usa un ciclo di animazione
 *    permanente. Questa è una scheda che chi fa QA tiene aperta tutta la
 *    giornata: un ciclo che ridisegna sessanta volte al secondo per otto
 *    ore consuma batteria per una decorazione. Qui i nodi si spostano di
 *    pochissimo e il ciclo si ferma da solo quando la scheda passa in
 *    secondo piano.
 *
 * 2. RISPETTA `prefers-reduced-motion`. Chi ha chiesto meno animazioni al
 *    sistema operativo ottiene la trama disegnata una volta e ferma:
 *    l'immagine resta, il moto no.
 */
(function () {
  "use strict";

  const tela = document.getElementById("rete");
  if (!tela || !tela.getContext) return;

  const contesto = tela.getContext("2d");
  const fermo = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const COLORE = "rgb(90, 160, 120)";
  const DISTANZA = 165;      // oltre questa, due nodi non si collegano
  const DENSITA = 26000;     // un nodo ogni tot pixel quadrati

  let nodi = [];
  let animazione = null;

  function dimensiona() {
    const rapporto = Math.min(window.devicePixelRatio || 1, 2);
    tela.width = Math.floor(window.innerWidth * rapporto);
    tela.height = Math.floor(window.innerHeight * rapporto);
    contesto.setTransform(rapporto, 0, 0, rapporto, 0, 0);

    // I nodi si ricreano in proporzione alla finestra: su uno schermo
    // grande una manciata di punti sparirebbe, su uno piccolo una folla
    // di punti coprirebbe il testo.
    const quanti = Math.max(14, Math.min(64,
      Math.round((window.innerWidth * window.innerHeight) / DENSITA)));
    nodi = [];
    for (let i = 0; i < quanti; i++) {
      nodi.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        dx: (Math.random() - 0.5) * 0.14,
        dy: (Math.random() - 0.5) * 0.14
      });
    }
  }

  function disegna() {
    const larghezza = window.innerWidth;
    const altezza = window.innerHeight;
    contesto.clearRect(0, 0, larghezza, altezza);

    for (let i = 0; i < nodi.length; i++) {
      for (let j = i + 1; j < nodi.length; j++) {
        const dx = nodi[i].x - nodi[j].x;
        const dy = nodi[i].y - nodi[j].y;
        const distanza = Math.hypot(dx, dy);
        if (distanza > DISTANZA) continue;
        // Più due nodi sono vicini, più la linea è visibile: è quello che
        // dà alla trama l'aspetto di una rete invece che di un reticolo.
        contesto.globalAlpha = (1 - distanza / DISTANZA) * 0.28;
        contesto.strokeStyle = COLORE;
        contesto.lineWidth = 1;
        contesto.beginPath();
        contesto.moveTo(nodi[i].x, nodi[i].y);
        contesto.lineTo(nodi[j].x, nodi[j].y);
        contesto.stroke();
      }
    }

    contesto.globalAlpha = 0.34;
    contesto.fillStyle = COLORE;
    for (const nodo of nodi) {
      contesto.beginPath();
      contesto.arc(nodo.x, nodo.y, 1.9, 0, Math.PI * 2);
      contesto.fill();
    }
    contesto.globalAlpha = 1;
  }

  function passo() {
    for (const nodo of nodi) {
      nodo.x += nodo.dx;
      nodo.y += nodo.dy;
      // Rimbalzo ai bordi: i nodi restano dentro senza dover ricreare
      // l'insieme quando escono.
      if (nodo.x < 0 || nodo.x > window.innerWidth) nodo.dx *= -1;
      if (nodo.y < 0 || nodo.y > window.innerHeight) nodo.dy *= -1;
    }
    disegna();
    animazione = window.requestAnimationFrame(passo);
  }

  function avvia() {
    if (fermo || animazione !== null) return;
    animazione = window.requestAnimationFrame(passo);
  }

  function sospendi() {
    if (animazione === null) return;
    window.cancelAnimationFrame(animazione);
    animazione = null;
  }

  dimensiona();
  disegna();
  avvia();

  // Ridimensionare una finestra genera decine di eventi al secondo:
  // ricostruire i nodi a ognuno farebbe sfarfallare la trama.
  let attesa = null;
  window.addEventListener("resize", function () {
    window.clearTimeout(attesa);
    attesa = window.setTimeout(function () {
      dimensiona();
      disegna();
    }, 180);
  });

  // Scheda in secondo piano: si smette di disegnare. Nessuno sta
  // guardando, e il portatile lo sente.
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) sospendi(); else avvia();
  });
})();
