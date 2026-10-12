/* Gli elementi dello schermo del telefono come corpi solidi (12/10/2026).
 *
 * Il servizio (Ring.java) passa con `PB.schermo()` un JSON in pixel fisici:
 *   { nodi: [[sinistra, alto, destra, basso], ...],   // coordinate dello schermo
 *     ox, oy,                                          // dove comincia la pagina sullo schermo
 *     alto }                                           // altezza della barra di stato
 * e lo ripassa con `__pbSchermo.disegna(...)` quando lo schermo sotto cambia
 * (una notifica che arriva, l'orologio, la rotazione).
 * Qui diventano immagini trasparenti grandi uguali: ring.js le legge come
 * solidi (`img` è fra i suoi SOLIDI) a ogni giro di `rileva()`.
 */
(function () {
  "use strict";
  var VUOTA = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  var scatola = document.getElementById("solidi");
  var info = { alto: 0, quanti: 0 };

  function disegna(dati) {
    if (!dati || !scatola) return;
    var r = window.devicePixelRatio || 1;
    var ox = +dati.ox || 0, oy = +dati.oy || 0;
    var largo = window.innerWidth, altoPagina = window.innerHeight;
    info.alto = (+dati.alto || 0) / r;
    var pezzi = document.createDocumentFragment(), n = 0;
    var nodi = Array.isArray(dati.nodi) ? dati.nodi : [];
    for (var i = 0; i < nodi.length; i++) {
      var q = nodi[i];
      if (!q || q.length < 4) continue;
      var sx = (q[0] - ox) / r, sy = (q[1] - oy) / r, dx = (q[2] - ox) / r, dy = (q[3] - oy) / r;
      // Fuori dalla pagina (la barra di navigazione resta sotto il pavimento).
      if (dx <= 0 || dy <= 0 || sx >= largo || sy >= altoPagina - 4) continue;
      dy = Math.min(dy, altoPagina - 4);
      if (dx - sx < 8 || dy - sy < 6) continue;
      var img = new Image();
      img.alt = ""; img.src = VUOTA; img.draggable = false;
      img.style.left = sx + "px"; img.style.top = sy + "px";
      img.style.width = (dx - sx) + "px"; img.style.height = (dy - sy) + "px";
      pezzi.appendChild(img); n++;
    }
    scatola.textContent = "";
    scatola.appendChild(pezzi);
    info.quanti = n;
  }

  window.__pbSchermo = { disegna: disegna, info: info };

  // Dove stanno i lottatori, 20 volte al secondo (solo quando cambia): l'app ci mette sopra una zona
  // toccabile che li segue, così si possono prendere col dito senza togliere i tocchi al telefono.
  var ultimiCorpi = "";
  setInterval(function () {
    try {
      if (!window.PB || !window.PB.corpi || !window.__ring || !window.__ring.corpi) return;
      var c = JSON.stringify(window.__ring.corpi());
      if (c !== ultimiCorpi) { ultimiCorpi = c; window.PB.corpi(c); }
    } catch (e) { /* il prossimo giro */ }
  }, 50);
  try { if (window.PB && window.PB.schermo) disegna(JSON.parse(window.PB.schermo())); } catch (e) { /* schermo vuoto: si lotta sul pavimento */ }
})();
