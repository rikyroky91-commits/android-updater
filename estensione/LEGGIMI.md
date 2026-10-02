# Le estensioni del browser

Due estensioni, costruite dagli stessi file del sito:

| Estensione | Cosa fa | Cartelle | Sorgente |
| --- | --- | --- | --- |
| **Page Brawl** | Il ring: due lottatori che si picchiano sulla pagina aperta | `pacchetto/` (prova a mano), `store/` (da pubblicare) | `web/static/ring.js`, `web/static/lingue.js`, la tendina di `web/templates/home.html` |
| **Page Snow** | Il tema di Natale: neve che si accumula, lucine, ghiaccioli, albero, pupazzi | `natale/` | `web/static/natale.js` |

I nomi sono provvisori. Tutto si rigenera con `python3 estensione/costruisci.py`; il test `tests/test_estensione.py` fallisce se una cartella è rimasta indietro rispetto ai file del sito.

## Provarle in Chrome (o Edge, Brave, Opera, Vivaldi)

1. `python3 estensione/costruisci.py --zip` scrive gli zip in `estensione/zip/`. Scompattane uno: la cartella che ottieni contiene direttamente `manifest.json`.
2. Apri `chrome://extensions` e accendi **Modalità sviluppatore** in alto a destra.
3. **Carica estensione non pacchettizzata** e scegli quella cartella. Se Chrome risponde «File manifest mancante», hai scelto una cartella sopra o sotto: va scelta quella con dentro `manifest.json`.
4. Fissa l'icona nella barra (il menu a forma di puzzle), apri un sito qualunque e clicca l'icona.

Non funzionano, per regola di Chrome, su `chrome://…`, sul Chrome Web Store e sui PDF.

## Page Brawl

Un clic sull'icona accende la lotta sulla scheda aperta. In basso a destra compaiono due tasti: il guantone apre le opzioni, quello di accensione spegne tutto e resta da solo in vista, pronto a riaccendere. Un altro clic sull'icona fa lo stesso del tasto di accensione.

### Il tasto su tutti i siti

Di suo l'estensione entra in una pagina solo quando clicchi l'icona (`activeTab`). Chi vuole il tasto di accensione su ogni pagina lo accende nelle opzioni (in fondo alla tendina, o dal menu dell'estensione): il browser chiede allora il permesso su tutti i siti, che è **facoltativo** e si toglie spegnendo la stessa spunta. Chi non lo accende non vede mai l'avviso sui dati di tutti i siti.

### Le due varianti

| Cartella | A cosa serve | Premium |
| --- | --- | --- |
| `pacchetto/` | Provarla caricandola a mano | Chiuso, con un interruttore **Premium di prova** in cima alla tendina per vederla aperta e chiusa |
| `store/` | Quella da pubblicare | Chiuso, senza interruttore di prova. Il tasto dice «Premium arriva presto» finché manca l'indirizzo di acquisto |

### Cosa è gratis e cosa è Premium

- **Gratis:** la lotta fra il robot e la mela, prese e lanci col mouse, fumogeni e barattoli con le creature, la pioggia di oggetti, terremoto, jetpack, furia, barre della vita, scommesse, la partita a dieci col volo fuori dal ring, quello che i lottatori imparano.
- **Premium:** i personaggi (super guerrieri, maghi, duellanti) con le loro mosse; pistola, spada, bomba, pieghevole e le due esplosioni; pioggia, uragano, rallentatore e le gravità diverse dalla Terra.

I tasti Premium portano un lucchetto. Cliccandone uno si apre il riquadro in cima alla tendina.

### Niente telefoni, ma fumogeni e barattoli (02/10/2026)

Nell'estensione non piovono telefoni (sul sito sì: è un sito di telefoni). Cadono:

- **Fumogeni.** Lanciati aprono una nube: chi ci finisce dentro non vede e barcolla per qualche secondo, tranne chi l'ha lanciato.
- **Barattoli.** Lanciati si rompono e liberano una creatura che per dieci secondi combatte per chi l'ha lanciato: **Tizzo** (fuoco, soffia fiamme), **Zip** (elettricità, chiama un fulmine), **Bolla** (acqua, un getto che spinge lontano). Al massimo tre creature insieme. Sono personaggi inventati qui.
- **Armi** (pistola, spada, bomba), solo con Premium.

Caduti dal cielo restano interi: si aprono solo se lanciati, dai lottatori o col mouse. Nella **pioggia di oggetti** arrivano già innescati.

### La partita a dieci

Chi arriva a dieci K.O. chiude la partita: sul colpo l'azione si ferma un attimo, lo sconfitto parte dritto fuori dalla finestra, dal punto in cui esce si apre un ventaglio di luce, poi il conto riparte da zero e lui rientra dall'alto.

### La guida per chi installa

Alla prima installazione si apre `benvenuto.html`: cinque passi e le cose da sapere, nelle cinque lingue (i testi sono nei messaggi dell'estensione, in `costruisci.py`). Si riapre da «Come funziona» in fondo alla tendina e dalla pagina delle opzioni. Page Snow ha la sua, più corta.

### I personaggi

Scelto uno stile, in campo non ci sono più il robot e la mela ma due personaggi inventati per quel tema:

- **Super guerrieri** (Zefir e Brasa): volano, onde di energia, sfera gigante, teletrasporto, e la **trasformazione** («sovraccarico», due forme: anelli di luce sopra la testa, bordi e occhi accesi, colpi più forti).
- **Maghi** (Merlo e Ortica): bacchetta e scopa; dardi, raggio, gelo, rimpicciolimento, fulmine, levitazione, scudo, sparizione.
- **Duellanti** (Rovo e Scia): lama di energia; fendenti, affondi, lo scatto che attraversa l'avversario, la lama lanciata, le lame incrociate.

Nomi, facce e vestiti sono inventati qui: non richiamano personaggi di altri. Vale la pena tenerlo così anche nelle schede degli store.

### Premium: cosa c'è e cosa manca

Le scelte stanno in `premium.json`:

- `premium_attivo`: `true` chiude le funzioni Premium; `false` toglie lucchetti e riquadro, tutto gratis.
- `url_acquisto`: la pagina dove si compra (deve cominciare con `https://`). Vuoto: il tasto resta spento con «Premium arriva presto».

**Manca la verifica dell'acquisto.** Oggi Premium si accende solo scrivendo `pb-premium = on` nella memoria dell'estensione (lo fa l'interruttore di prova). Il passo successivo è collegare un servizio di licenze, che controlla la chiave e scrive quel valore. Il blocco è nel codice dell'estensione, quindi chi sa usare gli strumenti per sviluppatori può aggirarlo: vale come barriera per l'utente normale, non come protezione.

### Lingua ed effetti cruenti

- La tendina e le scritte seguono la lingua del browser: italiano, inglese, spagnolo, francese, tedesco. Ogni altra lingua vede l'inglese. Il dizionario è `web/static/lingue.js`, lo stesso del sito; nell'estensione traduce solo la tendina, mai la pagina.
- Schizzi e arti staccati partono **spenti**. Si accendono dalla tendina (Imprevisti → «Schizzi e arti staccati»).

## Page Snow

Un clic sull'icona accende il Natale sulla scheda aperta; il tasto col fiocco, in basso a destra, lo spegne e lo riaccende. È gratis, senza Premium.

- Nevica a tre profondità; i fiocchi vicini si posano su campi, tasti, immagini e titoli della pagina, e la neve si accumula, luccica, frana, si spazza col puntatore.
- Sotto gli elementi crescono i ghiaccioli: gocciolano, e toccati si staccano.
- Lucine in cima alla finestra, cappellini rossi sui titoli e sulle immagini piccole, brina agli angoli.
- Sul fondo l'albero coi regali (un clic e si aprono) e i pupazzi di neve, che toccati vanno in pezzi e si rimontano a mano.
- Ogni tanto passa una slitta con le renne.

Nelle opzioni c'è una sola scelta: **accendere da solo il tema su tutti i siti**. Anche qui il permesso su tutti i siti è facoltativo. Con quella scelta accesa, spegnere dal tasto col fiocco vale per tutte le pagine, finché non lo riaccendi.

## Come sono fatte

- **Una sola sorgente.** Le cartelle sono generate da `costruisci.py` a partire dai file del sito. Dopo ogni modifica al ring o al tema di Natale: `python3 estensione/costruisci.py`.
- **Permesso minimo.** `activeTab` + `scripting` + `storage`. Non leggono e non mandano niente: nessuna richiesta di rete.
- **Isolate dalla pagina.** Canvas, tasti e tendina stanno in uno shadow DOM: lo stile del sito non li deforma, e una Content-Security-Policy severa non li blocca.
- **Memoria dell'estensione.** Quello che i lottatori imparano, i gettoni, le opzioni e lo stato di Premium stanno in `chrome.storage.local`: sono gli stessi su tutti i siti.

## Pubblicare

`python3 estensione/costruisci.py --zip` scrive in `estensione/zip/` tre zip coi file alla radice: `page-brawl-…-prova.zip` (da provare a mano), `page-brawl-…-store.zip` e `page-snow-….zip` (da caricare negli store). Testi, giustificazioni dei permessi e schermate sono in `SCHEDA-STORE.md`, `scheda/` e `scheda-natale/`.

## Limiti noti

- Il pavimento è il fondo della finestra; gli ostacoli del ring sono campi, tasti, immagini e scritte grandi della pagina (i primi 160).
- La richiesta del permesso su tutti i siti (la finestrella del browser) non è stata provata in un Chrome vero: nelle prove automatiche il permesso era già dato.
- Le traduzioni in spagnolo, francese e tedesco non sono state riviste da un madrelingua.
