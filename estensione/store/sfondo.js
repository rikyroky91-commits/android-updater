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
    // La memoria dei lottatori (quello che hanno imparato, i gettoni, le
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
chrome.runtime.onMessage.addListener((messaggio, mittente) => {
  if (!messaggio) return;
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
