# Page Brawl: il ring come estensione del browser

Il robot e la mela del sito, su qualunque pagina. Nome provvisorio.

## Provarla in Chrome (o Edge, Brave, Opera, Vivaldi)

1. Scarica la cartella `estensione/pacchetto/` (o scompatta lo zip).
2. Apri `chrome://extensions` e accendi **Modalità sviluppatore** in alto a destra.
3. **Carica estensione non pacchettizzata** e scegli la cartella `pacchetto`.
4. Fissa l'icona col guantone nella barra (il menu a forma di puzzle), apri un sito qualunque e clicca l'icona.

Un clic sull'icona accende la lotta sulla scheda aperta; un altro clic la spegne e nasconde tutto. In basso a destra ci sono due tasti: il guantone apre le opzioni, l'omino barrato mette in pausa le lotte.

Non funziona, per regola di Chrome, su `chrome://…`, sul Chrome Web Store e sui PDF.

## Come è fatta

- **Una sola sorgente.** `pacchetto/` è generato da `costruisci.py` a partire da `web/static/ring.js`, dalla tendina di `web/templates/home.html` e dal suo stile. Dopo ogni modifica al ring: `python3 estensione/costruisci.py`. Il test `tests/test_estensione.py` fallisce se ci si dimentica.
- **Permesso minimo.** `activeTab` + `scripting` + `storage`: l'estensione vede una pagina solo quando ci clicchi sopra l'icona. Non legge e non manda niente: nessuna richiesta di rete.
- **Isolata dalla pagina.** Canvas, tasti e tendina stanno in uno shadow DOM: lo stile del sito non li deforma, e una Content-Security-Policy severa non li blocca.
- **Memoria dell'estensione.** Quello che i lottatori imparano, i gettoni e le opzioni stanno in `chrome.storage.local`: sono gli stessi su tutti i siti.

## Limiti noti

- La tendina è in italiano.
- Il pavimento è il fondo della finestra; gli ostacoli sono campi, tasti, immagini e scritte grandi della pagina.
- Su pagine molto lunghe e piene la ricerca degli ostacoli è limitata ai primi 160.
