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

Un clic sull'icona accende la lotta sulla scheda aperta. In basso a destra compaiono tre tasti: il joypad apre il controller, il guantone apre le opzioni, quello di accensione spegne tutto e resta da solo in vista, pronto a riaccendere. Un altro clic sull'icona fa lo stesso del tasto di accensione.

### Il controller ad angolo (05/10/2026)

Il tasto col joypad apre un quarto di ruota attaccato all'angolo in basso a destra della finestra, semitrasparente finché non ci si passa sopra. Non dipende dalla tendina: funziona con la tendina aperta o chiusa, e quando è aperto tendina e tasti gli si mettono accanto.

- **Nell'angolo** c'è il ritratto dal vivo del lottatore che si comanda, con la vita e l'energia lungo l'orlo e una spia verde o rossa. Un clic sul ritratto passa all'altro lottatore. Trascinandolo oltre metà finestra il controller va nell'angolo di sinistra.
- **Intorno**, due fasce a spicchi: fuori gli attacchi, dentro le mosse di servizio. Un clic e il lottatore la fa. Le mosse cambiano coi personaggi scelti e sono tutte quelle della tendina (per i super guerrieri anche presa a distanza, lampo accecante e autodistruzione; per i maghi la sparizione; per i duellanti l'incrocio di lame). Sotto l'icona c'è l'energia che serve, rossa se non basta, e lo spicchio resta spento finché la mossa non si può fare.
- Una mossa da vicino chiesta da lontano: prima ci va di corsa, poi colpisce.
- Durante l'orda i comandi valgono contro gli zombie. Durante uno scontro di energie ogni comando è tifo per il proprio lottatore.

Il resto del tempo il lottatore continua a pensare da sé: il controller dà ordini, non toglie l'iniziativa. È gratis.

### Il tasto su tutti i siti

Di suo l'estensione entra in una pagina solo quando clicchi l'icona (`activeTab`). Chi vuole il tasto di accensione su ogni pagina lo accende nelle opzioni (in fondo alla tendina, o dal menu dell'estensione): il browser chiede allora il permesso su tutti i siti, che è **facoltativo** e si toglie spegnendo la stessa spunta. Chi non lo accende non vede mai l'avviso sui dati di tutti i siti.

### Le due varianti

| Cartella | A cosa serve | Premium |
| --- | --- | --- |
| `pacchetto/` | Provarla caricandola a mano | Chiuso, con l'interruttore in cima alla tendina per vederla aperta e chiusa |
| `store/` | Quella da pubblicare | Dipende da `premium.json`. Oggi (`sblocco_gratis: true`) ha lo stesso interruttore della prova, col nome **Sblocca Premium gratis**: un clic e si apre tutto |

Con `sblocco_gratis: true` le due cartelle sono uguali. La scelta è stata presa il 05/10/2026: si esce con Premium apribile da chiunque, in attesa dei pareri di chi la usa.

### Cosa è gratis e cosa è Premium

- **Gratis:** la lotta fra il robot e la mela, prese e lanci col mouse, il controller ad angolo, fumogeni e barattoli con le creature, la pioggia di oggetti, il terremoto con l'eruzione, jetpack, furia, barre della vita, scommesse, la partita a dieci col volo fuori dal ring, quello che i lottatori imparano.
- **Premium:** i personaggi (super guerrieri, maghi, duellanti) con le loro mosse, scontro di energie compreso; pistola, spada, bomba, pieghevole e le due esplosioni; pioggia, uragano, rallentatore, meteoriti, orda di zombie e le gravità diverse dalla Terra.

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

Alla prima installazione si apre `benvenuto.html`: sei passi (l'ultimo è il controller) e le cose da sapere, nelle cinque lingue (i testi sono nei messaggi dell'estensione, in `costruisci.py`). Si riapre da «Come funziona» in fondo alla tendina e dalla pagina delle opzioni. Page Snow ha la sua, più corta.

### I personaggi

Scelto uno stile, in campo non ci sono più il robot e la mela ma due personaggi inventati per quel tema:

- **Super guerrieri** (Zefir e Brasa): volano, onde di energia, sfera gigante, teletrasporto, e la **trasformazione** («sovraccarico», due forme: anelli di luce sopra la testa, bordi e occhi accesi, colpi più forti).
- **Maghi** (Merlo e Ortica): bacchetta e scopa; dardi, raggio, gelo, rimpicciolimento, fulmine, levitazione, scudo, sparizione.
- **Duellanti** (Rovo e Scia): lama di energia; fendenti, affondi, lo scatto che attraversa l'avversario, la lama lanciata, le lame incrociate.

Nomi, facce e vestiti sono inventati qui: non richiamano personaggi di altri. Vale la pena tenerlo così anche nelle schede degli store.

### Gli imprevisti nuovi (05/10/2026)

- **Pioggia e temporale.** Le gocce arrivano fino in fondo e si fermano sui bordi degli elementi della pagina. Dopo qualche secondo di pioggia cade un fulmine: chi tiene una spada o vola alto lo attira.
- **Terremoto con eruzione.** Le scosse sbilanciano chi è a terra (chi vola no); dal pavimento, lontano dai due, esce un vulcano che lancia lapilli e cola lava. Nell'estensione trema il mondo del ring, non la pagina del sito.
- **Meteoriti** (Premium). Un mirino a terra annuncia dove cadono; i lottatori si scansano o alzano la barriera. Qualcuno lascia un sasso caldo da raccogliere e tirare.
- **Orda di zombie** (Premium). I due smettono di picchiarsi e si mettono spalle a spalla; si coprono e si aiutano a rialzarsi. L'orda arriva a **ondate generate ogni volta diverse** (tipi di zombie, tema, lati d'arrivo).
  - **Arriva da sola**, col suo orologio: la prima fra un minuto e mezzo e due e dieci di lotta, poi una ogni quattro-sei minuti (con le sorprese accese). A sorpresa sono tre ondate.
  - Dal tasto della tendina non finisce finché i due reggono, e resta il primato delle ondate superate. Un secondo clic sul tasto la chiude.
  - **Tre vite**, i cuori accanto al conto dell'ondata: con tutti e due a terra insieme, le prime due volte si rialzano di scatto e l'urto butta indietro gli zombie; alla terza l'orda ha vinto.
  - L'orda **segue i due**: se finiscono su un altro piano della pagina, gli zombie affondano e rispuntano lì.
- **Scontro di energie** (coi personaggi a energia). Chi vede caricare un colpo d'energia prova a caricare lo stesso: i due colpi si incontrano e parte un tiro alla fune. Vince chi spinge di più; le regole sono scritte nel commento sopra `SFIDA` in `ring.js`. Durante lo scontro **spuntano due tasti**, uno per parte, ai capi della barra: ogni clic su un tasto dà al suo lottatore fiato e una spinta in più, e cliccando in fretta lo si fa vincere anche se parte sfavorito.

Chi resta senza gambe si trascina sulle mani o vola; con una gamba sola saltella; senza braccia tira calci e testate.

### Premium: cosa c'è e cosa manca

Le scelte stanno in `premium.json`:

- `premium_attivo`: `true` tiene chiuse le funzioni Premium; `false` toglie lucchetti e riquadro, tutto gratis e senza traccia di Premium.
- `sblocco_gratis`: `true` lascia lucchetti e riquadro, ma mette in cima alla tendina il tasto **Sblocca Premium gratis** anche nella variante da pubblicare. È l'interruttore della variante di prova: un clic apre tutto, un altro richiude. `false` lo toglie dallo store.
- `url_acquisto`: la pagina dove si compra (deve cominciare con `https://`). Vuoto: il tasto di acquisto resta spento con «Premium arriva presto», e con lo sblocco gratis non si vede.

Per tornare a vendere: `sblocco_gratis: false`, un `url_acquisto` vero, `python3 estensione/costruisci.py --zip`, versione nuova nello store. Chi aveva già sbloccato resta sbloccato: lo stato sta nella memoria dell'estensione sul suo computer.

**Manca la verifica dell'acquisto.** Oggi Premium si accende solo scrivendo `pb-premium = on` nella memoria dell'estensione (lo fa l'interruttore). Il passo successivo è collegare un servizio di licenze, che controlla la chiave e scrive quel valore. Il blocco è nel codice dell'estensione, quindi chi sa usare gli strumenti per sviluppatori può aggirarlo: vale come barriera per l'utente normale, non come protezione.

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

`python3 estensione/costruisci.py --zip` scrive in `estensione/zip/` tre zip coi file alla radice: `page-brawl-…-prova.zip` (da provare a mano), `page-brawl-…-store.zip` e `page-snow-….zip` (da caricare negli store). La guida passo per passo, i testi, le giustificazioni dei permessi e le schermate sono in `SCHEDA-STORE.md`, `scheda/` e `scheda-natale/`.

## Limiti noti

- Il pavimento è il fondo della finestra; gli ostacoli del ring sono campi, tasti, immagini e scritte grandi della pagina (i primi 160).
- Durante il terremoto nell'estensione la pagina del sito resta ferma (sul sito Mobile Update Tracker trema anche la pagina): muovere il contenuto di un sito qualunque sposterebbe i suoi elementi fissi.
- Il controller è stato provato col mouse e col tocco simulato, non su un telefono vero.
- La richiesta del permesso su tutti i siti (la finestrella del browser) non è stata provata in un Chrome vero: nelle prove automatiche il permesso era già dato.
- Le traduzioni in spagnolo, francese e tedesco non sono state riviste da un madrelingua.
