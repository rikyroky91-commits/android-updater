# Page Brawl: il ring come estensione del browser

Il robot e la mela del sito, su qualunque pagina. Nome provvisorio.

## Le due varianti

| Cartella | A cosa serve | Premium |
| --- | --- | --- |
| `pacchetto/` | Provarla caricandola a mano | Chiuso, con un interruttore **Premium di prova** in cima alla tendina per vederla aperta e chiusa |
| `store/` | Quella da pubblicare | Chiuso, senza interruttore di prova. Il tasto dice «Premium arriva presto» finché manca l'indirizzo di acquisto |

Sono generate tutte e due da `costruisci.py`; cambia solo quel tasto.

## Provarla in Chrome (o Edge, Brave, Opera, Vivaldi)

1. Scompatta `page-brawl-…-prova.zip`. La cartella che ottieni contiene direttamente `manifest.json`.
2. Apri `chrome://extensions` e accendi **Modalità sviluppatore** in alto a destra.
3. **Carica estensione non pacchettizzata** e scegli quella cartella. Se Chrome risponde «File manifest mancante», hai scelto una cartella sopra o sotto: va scelta quella con dentro `manifest.json`.
4. Fissa l'icona col guantone nella barra (il menu a forma di puzzle), apri un sito qualunque e clicca l'icona.

Un clic sull'icona accende la lotta sulla scheda aperta; un altro clic la spegne e nasconde tutto. In basso a destra ci sono due tasti: il guantone apre le opzioni, l'omino barrato mette in pausa le lotte.

Non funziona, per regola di Chrome, su `chrome://…`, sul Chrome Web Store e sui PDF.

## Cosa è gratis e cosa è Premium

- **Gratis:** la lotta, prese e lanci col mouse, telefoni, smartwatch, tablet e portatili, terremoto, jetpack, furia, barre della vita, scommesse, quello che i lottatori imparano.
- **Premium:** i super guerrieri con le nove mosse speciali; pistola, spada, bomba, pieghevole e le due esplosioni; pioggia, uragano, rallentatore e le gravità diverse dalla Terra.

I tasti Premium portano un lucchetto. Cliccandone uno si apre il riquadro in cima alla tendina.

Le scelte stanno in `premium.json`:

- `premium_attivo`: `true` chiude le funzioni Premium; `false` toglie lucchetti e riquadro, tutto gratis.
- `url_acquisto`: la pagina dove si compra (deve cominciare con `https://`). Vuoto: il tasto resta spento con «Premium arriva presto».

**Cosa manca per vendere davvero:** la verifica dell'acquisto. Oggi Premium si accende solo scrivendo `pb-premium = on` nella memoria dell'estensione (lo fa l'interruttore di prova). Il passo successivo è collegare un servizio di licenze, che controlla la chiave e scrive quel valore. Il blocco è nel codice dell'estensione, quindi chi sa usare gli strumenti per sviluppatori può aggirarlo: vale come barriera per l'utente normale, non come protezione.

## Lingua ed effetti cruenti

- La tendina e le scritte seguono la lingua del browser: italiano, inglese, spagnolo, francese, tedesco. Ogni altra lingua vede l'inglese. Il dizionario è `web/static/lingue.js`, lo stesso del sito; nell'estensione traduce solo la tendina, mai la pagina.
- Schizzi e arti staccati partono **spenti**. Si accendono dalla tendina (Imprevisti → «Schizzi e arti staccati»).

## Come è fatta

- **Una sola sorgente.** Le due cartelle sono generate da `costruisci.py` a partire da `web/static/ring.js`, `web/static/lingue.js`, dalla tendina di `web/templates/home.html` e dal suo stile. Dopo ogni modifica al ring: `python3 estensione/costruisci.py`. Il test `tests/test_estensione.py` fallisce se ci si dimentica.
- **Permesso minimo.** `activeTab` + `scripting` + `storage`: l'estensione vede una pagina solo quando ci clicchi sopra l'icona. Non legge e non manda niente: nessuna richiesta di rete.
- **Isolata dalla pagina.** Canvas, tasti e tendina stanno in uno shadow DOM: lo stile del sito non li deforma, e una Content-Security-Policy severa non li blocca.
- **Memoria dell'estensione.** Quello che i lottatori imparano, i gettoni, le opzioni e lo stato di Premium stanno in `chrome.storage.local`: sono gli stessi su tutti i siti.

## Pubblicare

`python3 estensione/costruisci.py --zip` scrive in `estensione/zip/` i due zip, con i file alla radice. Quello da caricare nello store è `page-brawl-…-store.zip`. Testi, giustificazioni dei permessi e schermate sono in `SCHEDA-STORE.md` e `scheda/`.

## Limiti noti

- Il pavimento è il fondo della finestra; gli ostacoli sono campi, tasti, immagini e scritte grandi della pagina.
- Su pagine molto lunghe e piene la ricerca degli ostacoli è limitata ai primi 160.
- Le traduzioni in spagnolo, francese e tedesco non sono state riviste da un madrelingua.
