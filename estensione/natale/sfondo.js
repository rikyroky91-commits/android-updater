/* Il service worker di Page Snow: al clic sull'icona accende la neve sulla
 * scheda attiva; a un secondo clic la spegne (e poi la riaccende). */
async function avvia(tab) {
  if (!tab || !tab.id) return "nessuna scheda";
  const dove = { tabId: tab.id };
  try {
    const [{ result: gia }] = await chrome.scripting.executeScript({ target: dove, func: () => !!window.__nataleEstensione });
    if (gia) {
      await chrome.scripting.executeScript({ target: dove, func: () => window.__nataleEstensione.alterna() });
      return "alternato";
    }
    // `__nataleAvvio`: chiesto con un clic, parte acceso (da solo, su tutti i siti, guarda prima se è stato spento).
    await chrome.scripting.executeScript({ target: dove, func: () => { window.__nataleAvvio = true; } });
    await chrome.scripting.insertCSS({ target: dove, files: ["pagina.css"] });
    await chrome.scripting.executeScript({ target: dove, files: ["prepara.js", "natale.js"] });
    return "acceso";
  } catch (errore) {
    // Pagine dove un'estensione non può entrare (chrome://, il Web Store, i PDF).
    return "non permesso: " + (errore && errore.message);
  }
}
chrome.action.onClicked.addListener(avvia);
// Tolto il permesso su tutti i siti dalle impostazioni del browser: il tema torna manuale.
chrome.permissions.onRemoved.addListener(async () => {
  try {
    if (await chrome.permissions.contains({ origins: ["<all_urls>"] })) return;
    await chrome.scripting.unregisterContentScripts({ ids: ["ps-auto"] });
    await chrome.storage.local.set({ "ps-sempre": "off" });
  } catch (errore) { /* non era registrato */ }
});
