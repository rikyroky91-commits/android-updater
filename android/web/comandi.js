/* I comandi dell'arena su telefono (12/10/2026).
 *
 * In tutti e due i modi (sopra lo schermo e nel browser interno):
 *  - lo stile per telefono (`mobile.css`, incollato qui da costruisci.py).
 * Sopra lo schermo, in più:
 *  - ✕ in alto a sinistra chiude il ring e ridà lo schermo (anche il tasto
 *    Indietro del telefono fa lo stesso); il tasto di accensione sparisce,
 *    farebbe la stessa cosa;
 *  - le due tendine a scelta (`<select>`: puntata e gravità) diventano tasti
 *    con un elenco disegnato qui: sopra le altre app la pagina vive in un
 *    servizio, e il menu di sistema di una `<select>` lì non si può aprire.
 */
(function () {
  "use strict";
  var radice = window.__ringRadice;
  if (!radice || !radice.querySelector || radice.__pbComandi) return;
  radice.__pbComandi = true;
  var schermo = window.__pbModo === "schermo";
  var pb = window.PB || null;

  function aggiungiStile(testo) {
    try {
      var foglio = new CSSStyleSheet();
      foglio.replaceSync(testo);
      radice.adoptedStyleSheets = Array.prototype.slice.call(radice.adoptedStyleSheets || []).concat([foglio]);
    } catch (e) {
      var st = document.createElement("style"); st.textContent = testo; radice.appendChild(st);
    }
  }
  aggiungiStile(__MOBILE_CSS__);
  if (!schermo) return;
  if (radice.host) radice.host.setAttribute("data-pb-schermo", "");

  function chiudi() { try { if (pb) pb.chiudi(); } catch (e) { /* niente */ } }
  var info = (window.__pbSchermo && window.__pbSchermo.info) || { alto: 0 };
  var esci = document.createElement("button");
  esci.type = "button"; esci.className = "pb-tasto"; esci.textContent = "\u2715";
  esci.setAttribute("aria-label", "Chiudi il ring"); esci.title = "Chiudi il ring";
  esci.style.left = "12px";
  esci.style.top = (Math.max(info.alto, 8) + 8) + "px";
  document.body.appendChild(esci);
  esci.addEventListener("click", chiudi);

  // Lotte spente dalla tendina: il ring si chiude.
  var accensione = radice.querySelector("[data-gioca]");
  if (accensione) new MutationObserver(function () {
    if (accensione.getAttribute("aria-pressed") === "false") chiudi();
  }).observe(accensione, { attributes: true, attributeFilter: ["aria-pressed"] });

  // --- Le <select> come tasti con un elenco ------------------------------
  var STILE = [
    ".pb-scelta { font: inherit; width: 100%; text-align: left; padding: 6px 28px 6px 10px; border-radius: 8px;",
    "  border: 1px solid var(--bordo, #d4d0c8); background: var(--carta, #fff); color: var(--ink, #201e1d); position: relative; }",
    ".pb-scelta::after { content: '\\25BE'; position: absolute; right: 10px; top: 50%; transform: translateY(-50%); }",
    ".pb-scelta:disabled { opacity: .5; }",
    ".pb-menu { position: fixed; z-index: 10; max-height: 50vh; overflow: auto; min-width: 160px; padding: 4px;",
    "  border-radius: 10px; border: 1px solid var(--bordo, #d4d0c8); background: var(--carta, #fff); color: var(--ink, #201e1d);",
    "  box-shadow: 0 10px 28px rgba(0,0,0,.28); pointer-events: auto; }",
    ".pb-menu button { display: block; width: 100%; text-align: left; font: inherit; padding: 10px 12px; border: 0;",
    "  border-radius: 7px; background: transparent; color: inherit; }",
    ".pb-menu button[aria-selected='true'] { background: var(--verde-tenue, rgba(31,122,90,.14)); font-weight: 600; }"
  ].join("\n");
  aggiungiStile(STILE);

  var menuAperto = null;
  function chiudiMenu() { if (menuAperto) { menuAperto.remove(); menuAperto = null; } }
  function etichetta(sel) {
    var o = sel.options[sel.selectedIndex];
    return o ? o.textContent : "";
  }
  function sostituisci(sel) {
    if (sel.__pbScelta) return;
    var b = document.createElement("button");
    b.type = "button"; b.className = "pb-scelta";
    sel.__pbScelta = b;
    sel.style.display = "none";
    sel.parentNode.insertBefore(b, sel.nextSibling);
    function allinea() { b.textContent = etichetta(sel); b.disabled = sel.disabled; }
    allinea();
    sel.addEventListener("change", allinea);
    new MutationObserver(allinea).observe(sel, { subtree: true, childList: true, characterData: true, attributes: true });
    b.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (menuAperto) { chiudiMenu(); return; }
      var m = document.createElement("div");
      m.className = "pb-menu"; m.setAttribute("role", "listbox");
      for (var i = 0; i < sel.options.length; i++) (function (o, i) {
        var v = document.createElement("button");
        v.type = "button"; v.textContent = o.textContent; v.disabled = o.disabled;
        v.setAttribute("aria-selected", i === sel.selectedIndex ? "true" : "false");
        v.addEventListener("click", function (e2) {
          e2.stopPropagation();
          sel.selectedIndex = i;
          sel.dispatchEvent(new Event("input", { bubbles: true }));
          sel.dispatchEvent(new Event("change", { bubbles: true }));
          allinea(); chiudiMenu();
        });
        m.appendChild(v);
      })(sel.options[i], i);
      radice.appendChild(m);
      var r = b.getBoundingClientRect(), alto = m.offsetHeight;
      var sotto = window.innerHeight - r.bottom - 8;
      m.style.left = Math.max(8, Math.min(r.left, window.innerWidth - m.offsetWidth - 8)) + "px";
      m.style.top = (sotto >= alto || sotto >= r.top ? r.bottom + 4 : Math.max(8, r.top - alto - 4)) + "px";
      m.style.minWidth = Math.max(160, r.width) + "px";
      menuAperto = m;
    });
  }
  function cerca() {
    var tutte = radice.querySelectorAll("select");
    for (var i = 0; i < tutte.length; i++) sostituisci(tutte[i]);
  }
  cerca();
  new MutationObserver(cerca).observe(radice, { subtree: true, childList: true });
  radice.addEventListener("click", function () { chiudiMenu(); });
})();
