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

### La 1.1.0 (13/10/2026)

- **La pagina conta di più.** `rileva()` entra negli shadow DOM aperti (Reddit e gli altri siti fatti coi web component), considera solidi anche video, iframe e `[role=button]`, e i titoli `h1`–`h4` dai 18 px in su. Le «scatole» (riquadri con sfondo, bordo o ombra, trovate a griglia con `elementsFromPoint`) danno una **sporgenza** sottile sul loro bordo alto, su cui si sale solo da sopra (`uno: true` in `urta`). Un lottatore lanciato, o volato via dopo un colpo, che attraversa una scatola la fa **sobbalzare** (`scuoti`, Web Animations con `composite: "add"`: niente stili toccati, la pagina non cambia); lo stesso fanno le esplosioni vicine e gli atterraggi pesanti.
- **Si vola di più**: dopo 8 secondi invece che dopo un minuto (`VOLO_DOPO`), un po' più spesso, e due volte su tre verso il bordo di un elemento più in alto (`quotaVolo`).
- **Classifica globale anche qui.** `prepara.js` mette `window.__ringClassifica`, che passa dal service worker (`sfondo.js`, due `fetch` verso `https://mobileupdatetracker.duckdns.org/api/corsa`, senza credenziali). Nessun permesso in più: il server risponde con CORS aperto (`_CORSA_CORS` in `web/main.py`). Il ring mostra classifica e campo del nome dovunque ci sia `__ringClassifica` (`conClassifica()`), non più solo sul sito. Il campo del nome sta nello shadow DOM.
- **Super guerrieri**: occhi fieri sul disegno di Riccardo (`occhioFiero`, solo per loro; l'orecchio va sul bordo della testa); Zefir e Brasa dell'11/10 con costumi nuovi.

### La 1.2.0 (16/10/2026)

Su richiesta di Riccardo: «un lavoro ex novo su tempi morti, animazioni e combat».

- **Meno tempi morti** (misurati con `tests/misura-lotta.cjs` su 46 pagine vere, primo minuto): si cammina più svelti e da lontano si corre, arrivati a tiro si colpisce subito, chi è su un elemento largo e ha l'avversario sotto si lascia cadere attraverso invece di camminare fino al bordo, chi vola scende all'altezza di chi è a terra, ci si regge solo sull'elemento sotto i piedi, il fumogeno acceca meno, un K.O. chiede un colpo in più. Colpi a segno al minuto: classico 17 → 25, duellanti 27 → 31, super guerrieri 17 → 18,5, maghi 28 → 27 (ora da lontano); tempo in piedi passato in pause oltre i 4 secondi: classico 45% → 31%, duellanti 12% → 9%, super guerrieri 16% → 13%, maghi 20% → 14%. Fra una misura e l'altra i numeri ballano di un paio di punti: sono simulazioni col caso dentro. È il lavoro del 02/10 (`61f8ca9`) che non era mai arrivato su `main`, rifatto sul motore di oggi.
- **Super guerrieri più fluidi e più da anime**: le pose si inseguono invece di scattare (veloci nei colpi, morbide nel resto), lo scatto in volo parte e frena, l'onda d'energia si carica a mani giunte sul fianco e parte coi palmi avanti, la carica dell'aura è a pugni stretti e tremando, il teletrasporto lascia un'immagine residua, i colpi forti hanno le linee d'impatto.
- **Limit Break**: la trasformazione si chiama così. Gli occhi del trasformato restano occhi (bianco, iride del colore della forma, sopracciglio staccato sopra); prima la scia degli occhi accesi passava sul viso come una visiera. La testa trasformata ha la calotta di capelli e non sembra più calva.
- **Maghi con un combattimento loro**, a distanza: stanno in una fascia di tiro, chi si avvicina troppo viene respinto (mossa nuova, **Respinta**, 10 di energia) o il mago sparisce **lontano** (prima la sparizione lo rimetteva accanto all'avversario), lo scudo si alza solo per le magie grosse, il mana si ricarica più in fretta e a secco ci si concentra. Distanza media fra i due: 122 → 193.
- **Corsa infinita, il ciclo**: tre **missioni** che restano fra una corsa e l'altra (arriva al round N, abbatti N nemici, sconfiggi N capi, evolvi un'arma, vinci round senza danni, fai N punti): fatte pagano monete e salgono di gradino, si vedono nella scelta e nel riepilogo, e in corsa si annunciano. **Il capo ogni cinque round** (5, 10, 15…), col forziere da tre premi; il cruscotto dice quando arriva. **Rimescola** alle carte di un livello, una volta a corsa più i **Dadi** della bottega (nuovo, fino a due).

**Secondo giro della 1.2.0 (16/10/2026, sempre prima dell'uscita)**, su richiesta di Riccardo («i round durano troppo poco»; «iniziare con pochi nemici e rallentare i primi round allungandoli e enfatizzando l'utilità del parry»; «un premio in crediti… per sbloccare caratteristiche perenni nel personaggio»):

- **Il parry.** S (o la voce «Parata» del controller, che ora hanno tutti gli stili) mette in guardia; con la tastiera la guardia dura finché si tiene premuto. Premuto entro 14 fotogrammi (circa un quarto di secondo) prima che arrivi un colpo o un morso è un **parry**: il colpo non fa niente, lampo e «PARRY!», chi l'ha tirato resta scoperto e parte da solo il contrattacco (braccio che spazza, poi affondo a due pugni). Premere a ripetizione non serve: dopo un tentativo a vuoto la finestra si riapre solo dopo due terzi di secondo. Poco prima di ogni morso gli occhi dello zombie fanno un lampo bianco: è il segnale.
- **La carica letale.** Ogni tanto uno zombie a terra si ferma, si carica all'indietro tremando con una **scintilla rossa** sopra la testa, poi parte di corsa piegato in avanti con una scia rossa, e i colpi non lo fermano. Col parry: nessun danno e il **contrattacco letale** (lui giù di colpo, un'onda d'urto che colpisce tutti quelli intorno). Con la parata normale passa un po' di danno; presa in pieno, fa molto male e si va a terra. La prima della corsa mostra il tasto da premere. Anche nell'orda del ring libero, più di rado.
- **I round.** Misurati con `tests/misura-corsa.cjs`, prima un'ondata durava in media 13 secondi (a volte 4), un duello 9. Ora i primi round hanno pochi nemici, distanziati, più lenti e più duri (`inizioCorsa`), e il ritmo cresce: ondate 34 secondi in media, il primo round 40, i duelli 21, la sopravvivenza 37.
- **Crediti e allenamento.** A fine corsa il **premio della corsa** in crediti (round, nemici, capi, parry, round puliti, cariche letali parate) si aggiunge alle monete raccolte. Coi crediti, oltre alla bottega, c'è l'**allenamento** di ogni personaggio (tasto «Allena» sopra «Gioca con»): Tempra, Colpo, Riflessi (parry più facile e contrattacco più forte), Arsenale, Seconda arma. Vale per sempre e solo per quel personaggio.
- **Missioni** ricalibrate sui round più lunghi, e una nuova: «Fai N parry in una corsa».

**Terzo giro della 1.2.0 (16/10/2026)**, su richiesta di Riccardo («nemici armati che lanciano anche con lancia granate una mossa da poter parare in parry e rimandare indietro, e quando muoiono rilasciano un fucile con motosega integrata che il protagonista può utilizzare per smembrare i nemici»; «scintilla parry quando si para», con due immagini di riferimento):

- **Il lampo del parry**, rifatto: nucleo bianco accecante, raggi a stella con due punte lunghe a croce, una bolla dorata trasparente, tre mezzelune bianche verso chi ha attaccato, righe di velocità e, dietro, un attimo di buio perché sulle pagine chiare si veda.
- **Il bruto armato** (nella corsa, quarto nemico nuovo, al massimo due insieme): grosso, grigio, corazzato, col lanciagranate all'anca. Tiene la distanza, punta (puntino rosso sulla canna), tira una granata a parabola che rimbalza e scoppia. Poco prima che arrivi la granata fa un **lampo bianco**: S premuto da lì in poi è un parry, la granata torna dritta sul bruto e scoppia fra gli zombie (forte, ad area); premuto prima del lampo è una parata (rimbalza via, arriva poco); presa in pieno toglie 10 di vita. La prima granata della corsa mostra il tasto.
- **Il fucile-sega**: il bruto morendo lo lascia sempre, e passandoci sopra lo si prende in mano (14 colpi; se lo si ha già, si ricarica). L'eroe spara da lontano e da vicino **sega**: lo zombie segato perde la testa e un braccio, che volano via («SQUARCH!»). Con gli schizzi spenti si sega lo stesso, ma senza pezzi.
- Premio della corsa: +10 crediti per granata rimandata.
- **La corsa a flusso** (Riccardo: «avere aumento di livello e fine round rallenta troppo il gioco… toglierei i round con un aumento fluido di nemici e meno interruzioni»). Niente più round: dopo il «Pronti…» l'orda non finisce mai, e quando la sua coda sta per finire arriva la fase dopo, attaccata (`prossimaFase`). In alto a destra la **minaccia** (il numero della fase) e il tempo; il nemico nuovo e il capo (ogni cinque) si annunciano in alto senza fermare niente; il premio della fase (anche «senza danni») arriva al volo. Niente duelli né sopravvivenza a tempo. Il forziere non ferma la lotta: si apre da solo dopo tre secondi a terra e i premi passano in una striscia in alto. A fermare restano solo le carte del livello, un quarto più rare. Misurato con l'eroe che gioca da solo (4 corse): 2,0-2,8 minuti, minaccia 5-6, carte 2,5-4,3 al minuto, una fase ogni 30 secondi circa.
- **Il parry al centro del gioco** (Riccardo: «non riesco a comprendere bene il parry e il contrattacco, non si capisce quando avviene e non vedo un contrattacco»; «incentriamo il gioco sulla tempistica della parata e del parry, massima attenzione sulle animazioni e i feedback»):
  - **L'anello del tempo**: intorno a chi gioca un anello si stringe verso il corpo contando i fotogrammi del colpo parabile che arriva per primo (morso, carica letale, granata, colpo dell'avversario); quando diventa d'oro è il momento di premere S. Una punta sull'anello dice da che parte arriva, un «!» sopra chi colpisce.
  - **In guardia** si vede uno scudo davanti: d'oro finché la finestra del parry è aperta, azzurro dopo (parata e basta).
  - **Il parry**: suono suo (un «ting» metallico), lampo, e mezzo secondo di **rallentatore**. Poi il **contrattacco**: scatto in avanti, fendente d'oro con la raggiera, «CONTRO!» in grande, il nemico vola via. Durante il contrattacco i morsi non prendono.
  - **Il tempo sbagliato si dice**: parata dopo una S premuta troppo presto → «TROPPO PRESTO!»; S premuta subito dopo un morso preso → «TROPPO TARDI!».
  - **Più colpi da parare**: il morso, negli ultimi sedici fotogrammi, non si ferma più coi colpi deboli e insegue di qualche passo chi arretra; cariche letali più frequenti (da 10-15 secondi all'inizio a 4-7). S gira l'eroe verso il colpo che arriva per primo. L'eroe che gioca da solo para (senza parry) finché chi gioca non usa la parata; poi la difesa è sua.
- **L'aggancio col mouse**: un clic su uno zombie lo aggancia (mirino rosso che gira e 🎯); l'eroe va da lui e lo colpisce per primo, ma se un altro lo sta mordendo prima si difende. Un altro clic sullo stesso, o sul vuoto, sgancia; morto lui, l'aggancio finisce.
- **Le carte da tastiera**: 1 2 3 (o Q W E) prendono la carta, le frecce la scelgono (si alza e brilla) e Invio la prende, R rimescola; sopra ogni carta il suo numero.
- **La donazione libera** (Riccardo: «un sistema di donazione libero a cui può essere legata la possibilità di mandare un messaggio e chiedere una feature o un personaggio aggiuntivo»; solo nell'estensione). In fondo alla tendina, se `url_donazione` in `premium.json` ha la pagina Ko-fi: una riga che invita a donare quanto si vuole e a scrivere nel messaggio la funzione o il personaggio che si vorrebbe, e il tasto «Sostieni Page Brawl» che apre Ko-fi. Ko-fi manda la donazione al sito (`/api/kofi`, `web/donazioni.py`), che tiene nome, importo e messaggio (non l'email) e li mostra agli amministratori in `/admin/donazioni`. Vuoto l'indirizzo, la sezione non c'è.

### Le due varianti

| Cartella | A cosa serve | Premium |
| --- | --- | --- |
| `pacchetto/` | Provarla caricandola a mano | Chiuso, con l'interruttore in cima alla tendina per vederla aperta e chiusa |
| `store/` | Quella da pubblicare | Dipende da `premium.json`. Oggi (`sblocco_gratis: true`) ha lo stesso interruttore della prova, col nome **Sblocca Premium gratis**: un clic e si apre tutto |

**Dalla 1.0.0 (10/10/2026) tutto gratis:** `premium_attivo: false` in `premium.json`, su richiesta di Riccardo («totalmente gratuito per questa versione»). Niente lucchetti, niente riquadro, niente interruttore, in tutte e due le cartelle; quello che sotto è detto «Premium» è aperto a tutti dal primo clic. Prima (dal 05/10) si usciva con `sblocco_gratis: true`, Premium apribile da chiunque con un tasto.

### Cosa è gratis e cosa è Premium

- **Gratis:** la lotta fra il robot e la mela, prese e lanci col mouse, il controller ad angolo, fumogeni e barattoli con le creature, la pioggia di oggetti, il terremoto con l'eruzione, jetpack, furia, barre della vita, la partita a dieci col volo fuori dal ring, il colpo finale, la trasformazione del robot e della mela, quello che i lottatori imparano.
- **Premium:** i personaggi (super guerrieri, maghi, duellanti) con le loro mosse, scontro di energie e trasformazioni comprese; pistola, spada, bomba, bazooka, lanciafiamme, pieghevole e le due esplosioni; pioggia, uragano, rallentatore, meteoriti, buco nero, orda di zombie (con le mosse in coppia) e le gravità diverse dalla Terra.

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

- **Super guerrieri** (Zefir e Brasa): volano, onde di energia, sfera gigante, teletrasporto, e la **trasformazione**, il **Limit Break** (fino al 16/10/2026 «sovraccarico»; due livelli: anelli di luce sopra la testa, capelli del colore della forma, iridi accese, colpi più forti).
- **Maghi** (Merlo e Ortica): bacchetta e scopa; dardi, raggio, gelo, rimpicciolimento, fulmine, levitazione, scudo, sparizione. Dal 10/10/2026 anche:
  - **Sciame di falene**: falene di luce che svolazzano verso l'altro e pungono (ogni tre punture, un colpo).
  - **Catene di rune**: un cerchio di rune si accende sotto i piedi dell'altro; se non ne esce prima che si chiuda, catene di luce lo legano per un paio di secondi.
  - **Pioggia di stelle**: la bacchetta al cielo e una pioggia di stelle cadenti intorno all'altro (ogni due che lo prendono, un colpo); un luccichio a terra avvisa dove cadranno.
  - **Maledizione di smeraldo**, la mossa finale: solo a energia piena, una lunga carica coi segni che l'annunciano, poi un raggio verde che passa attraverso scudi e ghiaccio. **Chi lo prende perde tutta la vita in un colpo**; ma è lento e si vede arrivare, e chi ha i riflessi si scansa o sparisce. I maghi la tirano più volentieri su chi è legato o gelato.
- **Duellanti** (Rovo e Scia): lama di energia; fendenti, affondi, lo scatto che attraversa l'avversario, la lama lanciata, le lame incrociate.

Nomi, facce e vestiti sono inventati qui: non richiamano personaggi di altri. Vale la pena tenerlo così anche nelle schede degli store.

**L'aspetto rifatto (10/10/2026).** Tutti e tre: braccia e gambe col contorno, testa con orecchio, naso e un'ombra, scarpe diverse per stile. I **maghi** hanno la tunica svasata con l'orlo che ondeggia, le pieghe e i ricami (stelle e luna), le maniche larghe, il cappello con la punta piegata, la fibbia e la luna, la bacchetta intagliata col cristallo che si accende, tre lucine che girano intorno; Merlo ha baffi arricciati e sopracciglia folte, Ortica le lentiggini. I **duellanti** la corazza a piastre con la linea accesa, lo spallaccio coi ribattini, i bracciali, le ginocchiere e gli stivali corazzati. I **combattenti** la casacca con lo scollo e il risvolto bordato, lo stemma sul petto, la cintura annodata con le code che sventolano, gli stivali col risvolto.

### Gli imprevisti nuovi (05/10/2026)

- **Pioggia e temporale.** Le gocce arrivano fino in fondo e si fermano sui bordi degli elementi della pagina. Dopo qualche secondo di pioggia cade un fulmine: chi tiene una spada o vola alto lo attira.
- **Terremoto con eruzione.** Le scosse sbilanciano chi è a terra (chi vola no); dal pavimento, lontano dai due, esce un vulcano che lancia lapilli e cola lava. Nell'estensione trema il mondo del ring, non la pagina del sito.
- **Meteoriti** (Premium). Un mirino a terra annuncia dove cadono; i lottatori si scansano o alzano la barriera. Qualcuno lascia un sasso caldo da raccogliere e tirare.
- **Orda di zombie** (Premium). I due smettono di picchiarsi e si mettono spalle a spalla; si coprono e si aiutano a rialzarsi. L'orda arriva a **ondate generate ogni volta diverse** (tipi di zombie, tema, lati d'arrivo).
  - **Arriva da sola**, col suo orologio: la prima fra un minuto e mezzo e due e dieci di lotta, poi una ogni quattro-sei minuti (con le sorprese accese). A sorpresa sono tre ondate.
  - Dal tasto della tendina non finisce finché i due reggono, e resta il primato delle ondate superate. Un secondo clic sul tasto la chiude.
  - **Tre vite**, i cuori accanto al conto dell'ondata: con tutti e due a terra insieme, le prime due volte si rialzano di scatto e l'urto butta indietro gli zombie; alla terza l'orda ha vinto.
  - L'orda **segue i due**: se finiscono su un altro piano della pagina, gli zombie affondano e rispuntano lì.
  - **Mosse in coppia** (05/10/2026). Non stanno solo spalle a spalla: ogni tanto, quando sono vicini e in piedi, ne fanno una. *Cavallina*: uno si abbassa, l'altro gli salta sopra e atterra di schianto in mezzo agli zombie dall'altra parte. *Cambio di lato*: si scambiano di posto girandosi intorno, e chi era in difficoltà prende il lato tranquillo. *Colpo insieme*: tutti e due dalla stessa parte, per buttare giù il più grosso. *Palla di cannone*: uno lancia l'altro raso terra contro la fila, e chi è lanciato torna indietro. Più a lungo va avanti l'orda senza una mossa in coppia, più ne hanno voglia. Durante la mossa i morsi non contano. Dal controller, durante la tregua, le quattro mosse prendono il posto di quelle che si fanno sull'altro.
- **Buco nero** (Premium, 05/10/2026). Si apre vicino ai due e per nove secondi tira a sé quello che ha intorno: lottatori, oggetti, zombie, colpi d'energia. Chi ci finisce dentro esce dalla parte opposta dello schermo, a specchio, un po' stordito ma senza danni e senza cambiare il punteggio. A sorpresa arriva la prima volta dopo il primo minuto abbondante di lotta, poi ogni tanto. Dal tasto della tendina si apre e, ricliccando, si chiude.
- **Scontro di energie** (coi personaggi a energia). Chi vede caricare un colpo d'energia prova a caricare lo stesso: i due colpi si incontrano e parte un tiro alla fune. Vince chi spinge di più; le regole sono scritte nel commento sopra `SFIDA` in `ring.js`. Durante lo scontro **spuntano due tasti**, uno per parte, ai capi della barra: ogni clic su un tasto dà al suo lottatore fiato e una spinta in più, e cliccando in fretta lo si fa vincere anche se parte sfavorito.

Chi resta senza gambe si trascina sulle mani o vola; con una gamba sola saltella; senza braccia tira calci e testate.

### Il colpo finale (05/10/2026, gratis)

Circa un round su tre si chiude con una scena: quando all'altro manca un colpo solo e i due sono in piedi, vicini, sullo stesso piano, il colpo che lo chiuderebbe diventa una mossa finale. La scena si fa buia, compare «COLPO FINALE!» e parte una di queste:

- **In orbita**: un montante e l'altro esce dall'alto della finestra; dopo un attimo ricade.
- **Flipper**: un calcio, e rimbalza tre volte fra i bordi della finestra.
- **Schiacciata**: chi vince salta molto in alto e gli atterra sopra; l'altro resta piatto come una frittella per un paio di secondi.
- **Onda finale** (super guerrieri): un'onda a bruciapelo lo porta fino al bordo.
- **Statua** (maghi): lo gela, poi una saetta manda il ghiaccio in pezzi.
- **Maledizione di smeraldo** (maghi, 10/10/2026): il raggio verde a bruciapelo, che lo solleva e lo lascia giù.
- **Taglio netto** (duellanti): uno scatto attraverso, un attimo fermi, poi l'altro cade.
- **Sfera finale** (05/10/2026): si carica sopra la testa una sfera enorme, più del doppio della sfera gigante dei super guerrieri, e gliela lascia cadere addosso. Lo scoppio **sfonda la pagina**: la striscia delle notizie si crepa in cinque punti (coi buchi veri), i bordi si rovinano, il pavimento resta bruciato e i telefoni lì intorno si spaccano.
- **Meteora**: lo manda per aria con un montante e gli tira addosso una meteora; cadendo lascia lo stesso genere di segni.
- **Mulinello**: un imbuto di vento lo tira su e lo trascina da una parte all'altra della pagina raschiando quello che trova, poi lo pianta a terra.
- **Crepa**: un pugno nel pavimento, e la crepa corre verso di lui spaccando la striscia man mano che passa.

Quale round tocca lo decide un sacchetto di tre (uno sì, due no) mescolato ogni volta. Se il round buono finisce in un altro modo (K.O. da lontano, in volo), resta buono per quello dopo. Vale un K.O. come gli altri. Non capita sul punto che chiude la partita a dieci, né durante orda, scontro di energie, terremoto o buco nero; se si afferra uno dei due col mouse, salta. Il tasto «Colpo finale» della tendina lo fa partire appena i due sono in piedi e vicini.

### Le trasformazioni (05/10/2026)

Chi si potenzia non cambia solo colore: cambia proprio corpo.

- **Super guerrieri**: restano loro, ma gonfiati: cresta di capelli ritta e piegata all'indietro (oro a Zefir, viola a Brasa, più chiara alla seconda forma), petto scoperto coi muscoli segnati, casacca ridotta a brandelli sulle spalle, fascia in vita, braccia e pugni più grossi.
- **Robot e mela** (il ring gratis): il robot diventa un **colosso** corazzato con gli spallacci e il nucleo acceso, la mela un **albero** con tronco, chioma e foglie che cadono. Qui la trasformazione è la rimonta di chi sta per cadere: arriva da sola quando manca un colpo al K.O., una volta sola a round, e il tasto «Trasforma i due» la fa partire a mano.
- **Duellanti**: il **cavaliere** incappucciato, col mantello, la maschera accesa e la lama a due punte, che respinge sempre i colpi che gli arrivano addosso.
- **Maghi**: per ora restano com'erano (trance e aura). Da fare, se piace il resto.

Chi è trasformato si disegna più grande (la fisica resta quella di prima) e picchia più forte, come già faceva il potenziamento.

### Le armi nuove (05/10/2026)

- **Bazooka**: due colpi. Spara un razzo che vola piano, corregge appena la rotta e scoppia su quello che tocca; chi ce l'ha tiene le distanze. Si innesca appena uscito dal tubo, così sparando verso il basso non scoppia addosso a chi spara.
- **Lanciafiamme**: tre vampate. Una fiammata lunga un paio di secondi che brucia chi ha davanti e annerisce il pavimento; chi ce l'ha si avvicina invece di scappare.

Tutte e due stanno nel gruppo **armi** (Premium) e piovono col resto delle armi.

### La corsa infinita (09/10/2026, gratis)

Dal pannello, «Corsa infinita» trasforma il ring in un gioco che cresce senza sosta: si sceglie un personaggio e si lotta da soli, un round dopo l'altro senza menu in mezzo (ondata, duello, sopravvivenza a tempo, ondata col capo), ognuno più grande del precedente. I nemici lasciano gemme; a ogni livello il gioco si ferma un attimo e offre tre carte: armi che colpiscono da sole (telefoni in orbita, onda d'urto, fulmine, aura di fuoco, dardi, lama rotante) con cinque livelli e un'evoluzione, o potenziamenti. Ogni round con l'orda porta un nemico nuovo (il botto che scoppia, il gelido che rallenta, il saltatore, lo sputatore, e tre draghetti volanti che tirano fuoco, fulmini o veleno), e ogni round ha i suoi protagonisti, mai quelli di prima. Ogni dodici-diciotto secondi una sorpresa: lo zombie d'oro, una pioggia di gemme, un forziere col paracadute, la frenesia. Lasciando fare all'eroe una corsa dura dai due ai cinque minuti; giocando, di più. I capi e l'avversario del duello lasciano forzieri. A terra cadono monete e oggetti per i tre posti. Le monete restano nel browser fra una corsa e l'altra e comprano potenziamenti permanenti nella bottega. Tre vite che non tornano; finite quelle, un'ultima possibilità col colpo finale da mirare.

Nell'estensione la corsa è gratis, come il colpo finale, ma i personaggi a pagamento restano a pagamento: nella scelta le tre famiglie hanno il lucchetto finché Premium è chiuso. Gli imprevisti della corsa capitano anche senza Premium, perché non si scelgono: fanno parte del round.

Dalla 1.1.0 la classifica globale c'è anche nell'estensione (vedi sopra, «La 1.1.0»). Record, monete, bottega e missioni restano nel browser.

### L'audio (09/10/2026, gratis)

Spento finché non lo si accende (tasto «Audio» nella tendina, o l'altoparlante nel cruscotto della corsa). Niente file: ogni suono è sintetizzato al momento con Web Audio, quindi l'estensione non scarica niente. Il contesto audio nasce solo al primo gesto, come vogliono i browser.

### La tastiera (09/10/2026, gratis)

Con il ring acceso si gioca anche da tastiera, sul lottatore del controller (dal 16/10/2026, su richiesta di Riccardo): W carica l'aura, D la raffica di pugni, A l'onda energetica (se i personaggi in campo hanno quelle mosse, cioè super guerrieri e, per aura e onda, maghi); Q E R T Y U I O P J K L fanno le mosse del controller nell'ordine dei suoi spicchi; le frecce ← → camminano, S para (tenuto è guardia, al momento giusto è un parry: vedi «Secondo giro della 1.2.0»), F vola o atterra, G cambia personaggio, H apre il controller; Z il colpo finale (nella mira: spara), X C V i tre oggetti della corsa. Nella corsa ← → (o A e D) scelgono il robot o la mela; le carte del livello si prendono con 1 2 3 (o Q W E), oppure con le frecce e Invio, R rimescola. Chi aveva salvato i tasti di prima prende quelli nuovi, tranne quelli cambiati a mano. Si leggono i tasti fisici, quindi su una tastiera francese o tedesca sono gli stessi posti. Mai mentre si scrive in un campo, mai con Ctrl, Alt o Cmd, e a ring spento i tasti restano della pagina. Nella tendina, sezione «Tastiera», si spegne e si rimappa (un clic sul tasto, poi quello nuovo; Esc annulla).

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
- **Memoria dell'estensione.** Quello che i lottatori imparano, le opzioni e lo stato di Premium stanno in `chrome.storage.local`: sono gli stessi su tutti i siti.

## Pubblicare

`python3 estensione/costruisci.py --zip` scrive in `estensione/zip/` tre zip coi file alla radice: `page-brawl-…-prova.zip` (da provare a mano), `page-brawl-…-store.zip` e `page-snow-….zip` (da caricare negli store). La guida passo per passo, i testi, le giustificazioni dei permessi e le schermate sono in `SCHEDA-STORE.md`, `scheda/` e `scheda-natale/`.

## Limiti noti

- Il pavimento è il fondo della finestra; gli ostacoli del ring sono campi, tasti, immagini e scritte grandi della pagina (i primi 160).
- Durante il terremoto nell'estensione la pagina del sito resta ferma (sul sito Mobile Update Tracker trema anche la pagina): muovere il contenuto di un sito qualunque sposterebbe i suoi elementi fissi.
- Il controller è stato provato col mouse e col tocco simulato, non su un telefono vero.
- La richiesta del permesso su tutti i siti (la finestrella del browser) non è stata provata in un Chrome vero: nelle prove automatiche il permesso era già dato.
- Le traduzioni in spagnolo, francese e tedesco non sono state riviste da un madrelingua.
