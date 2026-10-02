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
    await chrome.scripting.executeScript({ target: dove, func: (d) => { window.__ringDati = d; }, args: [dati] });
    // Il cursore a manina sopra i lottatori: inserito dall'estensione, così passa anche
    // sui siti con una Content-Security-Policy che vieta gli stili scritti nella pagina.
    await chrome.scripting.insertCSS({ target: dove, css: "html.ring-presa, html.ring-presa * { cursor: grab !important; } html.ring-trascina, html.ring-trascina * { cursor: grabbing !important; user-select: none !important; }" });
    await chrome.scripting.executeScript({ target: dove, files: ["prepara.js", "ring.js"] });
    return "acceso";
  } catch (errore) {
    // Pagine dove un'estensione non può entrare (chrome://, il Web Store, i PDF).
    return "non permesso: " + (errore && errore.message);
  }
}
chrome.action.onClicked.addListener(avvia);
