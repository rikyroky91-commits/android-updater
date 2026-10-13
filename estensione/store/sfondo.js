/* Il service worker dell'estensione: al clic sull'icona accende il ring
 * sulla scheda attiva; a un secondo clic lo spegne (e poi lo riaccende). */
async function avvia(tab) {
  if (!tab || !tab.id) return "nessuna scheda";
  const dove = { tabId: tab.id };
  try {
    const [{ result: gia }] = await chrome.scripting.executeScript({ target: dove, func: () => !!window.__ringEstensione });
    if (gia) {
      await chrome.scripting.executeScript({ target: dove, func: () => window.__ringEstensione.alterna() });
      return "alternato";
    }
    // La memoria dei lottatori (quello che hanno imparato, le
    // opzioni) è dell'estensione: uguale su tutti i siti.
    const dati = await chrome.storage.local.get(null);
    // `__lingueSoloDizionario`: il dizionario delle lingue serve solo alla tendina, la pagina non si tocca.
    await chrome.scripting.executeScript({ target: dove, func: (d) => { window.__ringDati = d; window.__lingueSoloDizionario = true; }, args: [dati] });
    // Il cursore a manina sopra i lottatori: inserito dall'estensione, così passa anche
    // sui siti con una Content-Security-Policy che vieta gli stili scritti nella pagina.
    await chrome.scripting.insertCSS({ target: dove, css: "html.ring-presa, html.ring-presa * { cursor: grab !important; } html.ring-trascina, html.ring-trascina * { cursor: grabbing !important; user-select: none !important; } html.ring-punta, html.ring-punta * { cursor: pointer !important; }" });
    await chrome.scripting.executeScript({ target: dove, files: ["lingue.js", "prepara.js", "ring.js"] });
    return "acceso";
  } catch (errore) {
    // Pagine dove un'estensione non può entrare (chrome://, il Web Store, i PDF).
    return "non permesso: " + (errore && errore.message);
  }
}
chrome.action.onClicked.addListener(avvia);
// Dal tasto sempre visibile (per chi l'ha acceso nelle opzioni) e dalla tendina.
// LA CLASSIFICA GLOBALE (13/10/2026): l'unica rete dell'estensione. Solo verso il server di
// Page Brawl, solo quando si apre la classifica o si manda il proprio punteggio (un nome scelto
// da chi gioca, i punti, il round, il personaggio). Il server risponde con CORS aperto: niente
// permessi in più sui siti.
const CLASSIFICA = "https://mobileupdatetracker.duckdns.org/api/corsa";
async function classifica(messaggio) {
  if (messaggio.azione === "carica") {
    const r = await fetch(CLASSIFICA + "/classifica?limite=10", { cache: "no-store", credentials: "omit" });
    if (!r.ok) throw new Error(String(r.status));
    return { ok: true, d: await r.json() };
  }
  const d = messaggio.dati || {};
  const corpo = { nome: String(d.nome || "").slice(0, 16), punti: +d.punti || 0, round: +d.round || 0, personaggio: String(d.personaggio || ""),
                  stile: String(d.stile || ""), uccisi: +d.uccisi || 0, durata: +d.durata || 0 };
  const r = await fetch(CLASSIFICA + "/punteggio", { method: "POST", credentials: "omit", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  return { ok: r.ok, d: await r.json().catch(() => ({})) };
}
chrome.runtime.onMessage.addListener((messaggio, mittente, rispondi) => {
  if (!messaggio) return;
  if (messaggio.tipo === "classifica") {
    classifica(messaggio).then(rispondi, (e) => rispondi({ ok: false, errore: String(e && e.message || e) }));
    return true;                                  // la risposta arriva dopo
  }
  if (messaggio.tipo === "avvia" && mittente.tab) avvia(mittente.tab);
  if (messaggio.tipo === "opzioni") chrome.runtime.openOptionsPage();
  if (messaggio.tipo === "guida") chrome.tabs.create({ url: chrome.runtime.getURL("benvenuto.html") });
});
// Tolto il permesso su tutti i siti dalle impostazioni del browser: via anche il tasto.
chrome.permissions.onRemoved.addListener(async () => {
  try {
    if (await chrome.permissions.contains({ origins: ["<all_urls>"] })) return;
    await chrome.scripting.unregisterContentScripts({ ids: ["pb-tasto"] });
    await chrome.storage.local.set({ "pb-sempre": "off" });
  } catch (errore) { /* non era registrato */ }
});
// Appena installata: la pagina che spiega come si usa.
chrome.runtime.onInstalled.addListener((dettagli) => {
  if (dettagli && dettagli.reason === "install") chrome.tabs.create({ url: chrome.runtime.getURL("benvenuto.html") });
});
