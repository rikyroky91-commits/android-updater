# Schede per il Chrome Web Store

Testi pronti da incollare nella console dello sviluppatore, per le due estensioni. Gli zip da caricare li scrive `python3 estensione/costruisci.py --zip` in `estensione/zip/`.

# Pubblicare, passo per passo

Controllato sulla documentazione di Chrome il 02/10/2026 e ricontrollato il 05/10/2026 (developer.chrome.com/docs/webstore: le pagine `publish`, `register` e `cws-dashboard-listing`). Il 05/10 ho ritrovato scritti lì: il caricamento dello zip, le quattro schede da compilare, i 30 giorni per pubblicare dopo l'approvazione, il limite di due estensioni per un editore nuovo, l'email dell'account che non si cambia, le immagini richieste. La cifra dell'iscrizione (5 dollari) e l'obbligo della verifica in due passaggi vengono dal controllo del 02/10: le pagine rilette il 05/10 non li riportano, quindi si confermano al momento dell'iscrizione.

**Un punto da verificare nella console: il video.** La pagina `cws-dashboard-listing` elenca fra le cose da fornire anche il link a un video YouTube che mostra l'estensione, e dichiara facoltativo solo il riquadro grande (1400×560). Non ho potuto aprire la console per vedere se il campo blocca davvero l'invio. Se lo blocca, basta mezzo minuto di schermo registrato con la lotta, il controller e l'orda, caricato su YouTube come «non in elenco».

## La 1.2.0 (16/10/2026): cosa cambia rispetto alla 1.1.0

- Lotte più fitte, super guerrieri più fluidi, il Limit Break al posto del «sovraccarico», maghi che combattono a distanza con la respinta, e il ciclo della corsa (missioni, il capo ogni cinque round, rimescola carte). Dettaglio in `LEGGIMI.md`, «La 1.2.0».
- Permessi e dati raccolti **invariati** rispetto alla 1.1.0: nella console non c'è niente da cambiare nella scheda privacy. Il tasto della donazione (quando `url_donazione` è impostato) apre soltanto ko-fi.com in una scheda: l'estensione non manda niente. L'informativa ha la sezione «Donazioni» (16/10).
- Testi dello store: le descrizioni della 1.1.0 restano valide. Se si vuole, nella descrizione lunga si può aggiungere una riga sulle missioni («Missions that carry over between runs, a boss every five rounds, card rerolls»).
- Da caricare: `python3 estensione/costruisci.py --zip` → `estensione/zip/page-brawl-1.2.0-store.zip`.

## La 1.1.0 (13/10/2026): cosa cambia rispetto alla 1.0.0

- Super guerrieri: occhi nuovi sul disegno di Riccardo (palpebra spessa che scende verso il naso, pupilla piccola); Zefir e Brasa dell'11/10 con costumi nuovi (Zefir gilet cremisi senza maniche e pantaloni antracite, Brasa casacca verde bosco col bordo oro, niente corazza) perché non ricalchino i personaggi di Dragon Ball.
- La pagina conta di più: si sale sul bordo alto di riquadri, card e post (sporgenze solo da sopra), si leggono anche gli elementi dentro i web component (shadow DOM aperti: Reddit e simili), i titoli di media grandezza sono solidi, si vola dopo 8 secondi invece che dopo un minuto e spesso verso un elemento più in alto; un lottatore lanciato contro un riquadro, o un'esplosione vicina, fa sobbalzare l'elemento vero (Web Animations, `composite: add`, niente modifiche alla pagina).
- Classifica globale anche nell'estensione: due chiamate dal service worker a `https://mobileupdatetracker.duckdns.org/api/corsa` (lettura della classifica, invio del punteggio solo quando si preme Invia). Nessun permesso nuovo: il server risponde con CORS aperto (`_CORSA_CORS` in `web/main.py`). **Va pubblicato il sito (unione su main) prima di inviare la 1.1.0**, sennò l'invio dall'estensione fallisce.
- Scheda dello store: descrizioni nuove che puntano sul roguelike e sul giocare mentre si lavora; descrizione breve nuova; cinque schermate nuove e riquadri promozionali in `scheda/1-1-0/`.
- **Privacy da aggiornare nella console**: ora esce un dato (la voce in classifica). Testi e caselle nella sezione «Scheda Privacy» qui sotto, e l'informativa è `https://mobileupdatetracker.duckdns.org/static/pagebrawl/privacy.html` (aggiornata per estensione e app; manca l'email di contatto da mettere al posto del segnaposto).

## In breve, per questa uscita (1.0.0, tutto gratis)

Decisione di Riccardo del 10/10/2026: «metterlo totalmente gratuito per questa versione». Iscrizione da sviluppatore pagata da Riccardo il 10/10. Effetti cruenti lasciati come sono (decisione sua: se la revisione li contesta si tolgono dalla variante `store`).

**Chi può compilare la console.** Chrome non lascia comandare da un'estensione le pagine del Web Store (`chrome.google.com/webstore`: «The extensions gallery cannot be scripted»), e il browser integrato dell'app Claude non le apre. Quindi caricamento e compilazione li fa Riccardo a mano. Il 10/10 gli è stata messa in `Download\Page Brawl store\` la cartella pronta: lo zip, le cinque schermate già numerate nell'ordine, il riquadro 440×280, l'icona e `TESTI-DA-INCOLLARE.txt` con ogni campo nell'ordine della console.

1. `python3 estensione/costruisci.py --zip` e si carica `estensione/zip/page-brawl-1.0.0-store.zip`.
2. `premium.json`: `premium_attivo: false`. Niente lucchetti, niente riquadro Premium, niente tasto di sblocco: tutto aperto dal primo clic.
3. Nella scheda dello store si incollano le descrizioni di questa pagina (non parlano più di Premium) e, nelle istruzioni per la verifica, il testo del passo 8.
4. In «Distribuzione» l'estensione resta **gratis** e senza acquisti in-app.
5. Niente informativa sulla privacy da aggiungere: non si raccoglie niente e non si vende niente.

## Tutti i passi

1. **Account.** Vai su `chrome.google.com/webstore/devconsole` con l'account Google che vuoi usare come editore (l'email si vede sulla scheda e non si cambia facilmente: meglio una dedicata). Paga l'iscrizione: 5 dollari, una volta sola, vale per tutte le estensioni. Accendi la verifica in due passaggi dell'account Google: senza, la console non lascia pubblicare.
2. **Profilo dell'editore.** In «Account» metti il nome dell'editore e verifica l'email di contatto. Un editore nuovo può avere al massimo **due estensioni pubblicate**: Page Brawl e Page Snow ci stanno giuste.
3. **Decidi Premium prima di caricare** (vedi «Prima di premere Invia» qui sotto). Tre uscite possibili in `premium.json`: `sblocco_gratis: true` (quella di oggi: lucchetti, e un tasto che apre tutto gratis), `premium_attivo: false` (niente lucchetti, niente Premium), oppure `sblocco_gratis: false` con un `url_acquisto` vero (si vende). Poi `python3 estensione/costruisci.py --zip`.
4. **Carica.** «Nuovo elemento» → scegli `estensione/zip/page-brawl-<versione>-store.zip` → «Carica». Lo zip ha `manifest.json` in cima, come vuole lo store.
5. **Scheda dello store.** Descrizione lunga (qui sotto, in inglese; con «Aggiungi lingua» anche l'italiano), categoria, lingua. Immagini: icona 128×128, almeno una schermata 1280×800 e al massimo cinque (in `scheda/` ce ne sono undici: l'elenco in fondo dice quali cinque caricare), riquadro promozionale 440×280 (`scheda/promo-440x280.png`).
6. **Privacy.** Scopo unico, una giustificazione per ogni permesso, «No, non uso codice remoto», nessun dato raccolto, le tre dichiarazioni finali. I testi sono qui sotto, da incollare.
7. **Distribuzione.** Gratis, pubblica, tutti i paesi. (Se un giorno vendi Premium fuori dallo store, l'estensione resta «gratis» qui: il pagamento non passa da Google.)
8. **Istruzioni per la verifica.** Non servono credenziali. Testo da incollare:

   ```
   Open any web page and click the toolbar icon: two characters start fighting. The power button in the bottom right corner turns everything off.
   The gamepad button opens a corner controller: click a slice to trigger a move, click the portrait to switch fighter.
   The glove button opens the options panel: every feature is free and unlocked, there is nothing to buy. "Endless run" in the panel starts the single-player mode. No account, no payment, no network request.
   ```
9. **Invia.** «Invia per la revisione». Se togli la spunta «Pubblica automaticamente», dopo l'approvazione hai 30 giorni per pubblicare a mano; scaduti, va reinviata.
10. **Attesa.** Di solito pochi giorni, a volte qualche settimana. Il permesso facoltativo su tutti i siti (`<all_urls>`) è fra quelli che allungano la revisione: la giustificazione qui sotto serve a quello. Oltre tre settimane si scrive all'assistenza.
11. **Aggiornamenti.** Si alza `VERSIONE` in `costruisci.py` (lo store rifiuta uno zip con la stessa versione), si rifà lo zip e si carica con «Carica nuova versione». Ogni aggiornamento ripassa dalla revisione.
12. **Raccogliere i pareri.** Arrivano dalle recensioni sulla pagina dello store. Nella console, «Scheda dello store» → «Campi aggiuntivi», c'è il campo **Support URL**: l'indirizzo di una pagina di assistenza, che compare fra i dettagli dell'estensione. Senza, chi ha un problema può solo lasciare una recensione. Va bene anche una pagina semplice con un modulo o un indirizzo email.
13. **Quando si decide di vendere.** `sblocco_gratis: false`, `url_acquisto` vero, versione nuova. Chi ha già sbloccato resta sbloccato (lo stato sta nel suo browser). Prima di farlo vanno riscritte le righe «Premium is free for now» delle descrizioni e va aggiunta l'informativa sulla privacy (vedi «Scheda Privacy»).

Per Page Snow gli stessi passi con `page-snow-<versione>.zip` e la sua scheda in fondo.

# Page Brawl

Zip: `page-brawl-<versione>-store.zip`.

## Prima di premere «Invia»

1. **Premium.** Per la 1.0.0 (10/10/2026) `premium_attivo: false`: tutto gratis, niente lucchetti; `python3 estensione/costruisci.py` non stampa niente su Premium. Quella che segue era la scelta del 05/10, superata: si esce con `sblocco_gratis: true`. Chi installa vede i tasti col lucchetto (i tre stili di personaggi con le loro mosse, le armi, il meteo, i meteoriti, il buco nero, l'orda) e, in cima alla tendina, il tasto **Sblocca Premium gratis** che li apre tutti. Da controllare prima di inviare: `python3 estensione/costruisci.py` deve stampare «Premium si sblocca gratis anche in store/». Se invece avvisa che manca l'indirizzo di acquisto, `premium.json` non è quello giusto e i lucchetti resterebbero chiusi senza rimedio.
2. **Nome.** «Page Brawl» è provvisorio: va cercato nello store e tra i marchi registrati prima di usarlo.
3. **Marchi.** I personaggi a pagamento sono inventati (nomi, facce, vestiti) e scheda e schermate non nominano prodotti o personaggi di altri: tenerlo così. Restano il robot e la mela della lotta gratis, che a qualcuno ricordano due marchi: se si vuole togliere ogni dubbio, anche loro si possono sostituire con due personaggi inventati. Un parere legale prima di vendere resta da chiedere.
4. **Effetti cruenti.** Lo store vieta la violenza gratuita. Partono spenti e le schermate non li mostrano, ma l'interruttore c'è: non so dire come lo giudica un revisore. La scelta più prudente è toglierlo dalla variante `store`.

## Nome e descrizione breve

Stanno già nel pacchetto (`_locales/`), in cinque lingue.

- **Nome:** Page Brawl
- **Descrizione breve (EN):** An endless roguelike survivor on any web page: every site is a new arena. Many fighters, hordes, dragons, auto-weapons. Free.

Riscritta con la 1.0.0 (Riccardo, 10/10: «la descrizione che parla solo di un robot e una mela non indica la realtà attuale: adesso è un endless roguelike survivor con tanti personaggi e tanti nemici, usabile in ogni pagina web, dove ogni sito è un ring nuovo»). Sta nel pacchetto (`_locales/`), in cinque lingue, come la lunga qui sotto. Con la 1.0.0 il gioco parte in inglese qualunque sia la lingua del browser (le altre quattro si scelgono nelle opzioni), e coi super guerrieri come personaggi di partenza (Riccardo: «come personaggi principali metti i guerrieri, che poi possono essere cambiati nella selezione dei personaggi»).

## Categoria e lingua

- **Categoria:** Just for Fun (da ricontrollare nella console: l'elenco cambia).
- **Lingua della scheda:** inglese; aggiungere la versione italiana qui sotto.

## Descrizione lunga (EN)

```
Page Brawl is a roguelike survivor that you play on top of the web page you already have open. Click the icon and the site you are reading becomes the arena: headings, buttons, images and cards turn into platforms, and every website plays differently. A run takes a few minutes, so it fits between one email and the next.

ENDLESS RUN: THE ROGUELIKE
• Pick a fighter and survive wave after wave. Every round is bigger and faster than the last, and almost every round brings a new enemy.
• Defeated enemies drop gems. Every level up pauses the game and offers 3 cards: new automatic weapons, upgrades, or an evolution. No two runs build the same way.
• Six auto-weapons that fire on their own: orbiting phones, shockwave, lightning, fire aura, homing darts, spinning blade. Take one to level 5 with its paired upgrade and it evolves.
• Enemies: shamblers, crawlers, bloaters, armored and enraged zombies, boomers that explode, frost biters that slow you down, leapers, spitters, brutes, bosses with their own health bar, crows diving from above and little dragons breathing fire, lightning or venom.
• Ground and sky: fly up to hunt the dragons, then slam down on the crowd.
• Surprises every few seconds: a golden zombie running off with coins, a rain of gems, a chest on a parachute, a frenzy that doubles your weapons.
• Three lives that don't come back, and one last chance: aim your finishing move along a sweeping line, and if it lands you get a life back.
• Coins carry over between runs: spend them in the Workshop on permanent upgrades and go further every time.
• Global leaderboard: at the end of a run, type a name and see where you rank against everyone else.

THE PAGE IS PART OF THE GAME
• Fighters climb on headings, buttons, images and cards, and fly up to land on them.
• Throw a fighter into a card, or let a bomb go off next to it, and the real element on the page jolts and bounces back.
• Works on news sites, shops, forums and the web apps you use every day, including pages built with web components.

FOUR FAMILIES OF FIGHTERS
• Super warriors who fly, fire energy waves and power up; wizards who freeze, shrink and ride brooms; duelists with energy blades; the classic robot and apple.

FREE COMBAT
• Prefer to watch? Two fighters brawl on their own. Grab them with the mouse, throw them, or use one to hit the other.
• Items, creature jars, a black hole, meteorites, zombie hordes where the two team up, energy clashes, finishing moves and a corner controller for every move.

KEYBOARD AND SOUND
• W charges the aura, D throws a punch flurry, A fires the energy wave; Q E R T Y for the other moves, arrow keys to walk, S to block and parry, F to fly, Z for the finishing move, X C V for items. Every key can be remapped.
• Optional synthesized sound.

Free. No account, no ads, nothing to buy.

The power button in the corner turns everything off at once. The page is never changed and never read: Page Brawl only measures where things are on screen.
Privacy: the only data that leaves your browser is a leaderboard entry (a name you type and your score), and only when you press Send. Settings, coins and records stay on your device.

Cartoon violence. Stronger effects are off by default.
Does not run on browser pages (chrome://), the Chrome Web Store or PDF files.
```

## Descrizione lunga (IT)

```
Page Brawl è un survivor roguelike che giochi sopra la pagina web che hai già aperta. Clicchi l'icona e il sito che stai leggendo diventa l'arena: titoli, tasti, immagini e riquadri diventano piattaforme, e ogni sito si gioca in modo diverso. Una corsa dura pochi minuti, ci sta fra una mail e l'altra.

CORSA INFINITA: IL ROGUELIKE
• Scegli un lottatore e sopravvivi ondata dopo ondata. Ogni round è più grande e più veloce del precedente, e quasi ogni round porta un nemico nuovo.
• I nemici abbattuti lasciano gemme. A ogni livello il gioco si ferma e offre 3 carte: armi automatiche nuove, potenziamenti o un'evoluzione. Nessuna corsa si costruisce uguale.
• Sei armi automatiche che colpiscono da sole: telefoni in orbita, onda d'urto, fulmine, aura di fuoco, dardi a ricerca, lama rotante. Portane una al livello 5 col suo potenziamento e si evolve.
• Nemici: zombie lenti, striscianti, gonfi, corazzati e rabbiosi, il botto che esplode, il gelido che ti rallenta, il saltatore, lo sputatore, il bestione, capi con la loro barra della vita, corvacci in picchiata e draghetti che sputano fuoco, fulmini o veleno.
• Terra e cielo: voli su a caccia dei draghi e ripiombi sulla folla.
• Sorprese ogni pochi secondi: lo zombie d'oro che scappa con le monete, la pioggia di gemme, il forziere col paracadute, la frenesia che raddoppia le armi.
• Tre vite che non tornano e un'ultima possibilità: mira il colpo finale lungo una linea che oscilla, e se va a segno ti ridà una vita.
• Le monete restano fra una corsa e l'altra: spendile nella Bottega in potenziamenti permanenti e arrivi più lontano ogni volta.
• Classifica globale: a fine corsa scrivi un nome e vedi dove sei rispetto a tutti gli altri.

LA PAGINA FA PARTE DEL GIOCO
• I lottatori salgono su titoli, tasti, immagini e riquadri, e ci volano sopra per atterrarci.
• Lancia un lottatore contro un riquadro, o fai scoppiare una bomba lì accanto, e l'elemento vero della pagina sobbalza e torna a posto.
• Funziona su siti di notizie, negozi, forum e le web app che usi ogni giorno, anche quelle fatte coi web component.

QUATTRO FAMIGLIE DI LOTTATORI
• Super guerrieri che volano, lanciano onde di energia e si trasformano; maghi che congelano, rimpiccioliscono e volano sulla scopa; duellanti con le lame di energia; il robot e la mela classici.

COMBATTIMENTO LIBERO
• Preferisci guardare? Due lottatori si picchiano da soli. Prendili col mouse, lanciali, usa l'uno per colpire l'altro.
• Oggetti, barattoli con le creature, buco nero, meteoriti, orde di zombie in cui i due si alleano, scontri di energie, colpi finali e un controller nell'angolo per ogni mossa.

TASTIERA E AUDIO
• W carica l'aura, D la raffica di pugni, A l'onda energetica; Q E R T Y le altre mosse, le frecce per camminare, S para e fa il parry, F per volare, Z il colpo finale, X C V gli oggetti. Ogni tasto si cambia.
• Audio facoltativo, sintetizzato al momento.

Gratis. Niente account, niente pubblicità, niente da comprare.

Il tasto di accensione nell'angolo spegne tutto in un colpo. La pagina non viene mai modificata né letta: Page Brawl misura solo dove stanno le cose sullo schermo.
Privacy: l'unico dato che esce dal browser è una voce in classifica (un nome che scrivi tu e il tuo punteggio), e solo quando premi Invia. Opzioni, monete e record restano sul tuo dispositivo.

Violenza da cartone animato. Gli effetti più forti partono spenti.
Non funziona sulle pagine del browser (chrome://), sul Chrome Web Store e sui PDF.
```

## Scheda «Privacy»

**Scopo unico (single purpose):**

```
Page Brawl is a cartoon fighting game (an endless roguelike survivor plus a free-for-all brawl) played on top of the page the user is viewing, started and stopped by clicking the extension icon.
```

**Giustificazione dei permessi:**

| Permesso | Testo da incollare |
| --- | --- |
| `activeTab` | The animation is drawn on the current tab only after the user clicks the extension icon. activeTab gives access to that single tab for that click, so no host permissions are needed. |
| `scripting` | Used to inject the extension's own bundled scripts and one small style rule into the tab the user clicked on. No remote code is loaded. |
| `storage` | Saves the user's options, the in-game coins, the keyboard mapping and what the fighters have learned locally, so they are the same on every site. Stored data is never sent anywhere. |
| Host facoltativo (`<all_urls>`) | Optional and off by default. It is requested only when the user turns on "Show the power button on every site" in the options page; it is used to place that one button on each page so the animation can be started without the toolbar icon. No page content is read or transmitted. Turning the option off removes the permission. |

**Codice remoto:** No, I am not using remote code.

**Uso dei dati (dalla 1.1.0):** spuntare **«Informazioni che consentono l'identificazione personale»**. Il nome della classifica è uno pseudonimo scelto dal giocatore, ma qualcuno può scriverci il proprio nome vero: dichiararlo è la scelta prudente, e non dichiararlo rischia un rifiuto. Le altre caselle restano vuote (niente salute, finanze, autenticazione, comunicazioni, posizione, cronologia, attività o contenuti dei siti). Le tre dichiarazioni finali restano tutte spuntate.

**Informativa sulla privacy (dalla 1.1.0, obbligatoria):** `https://mobileupdatetracker.duckdns.org/static/pagebrawl/privacy.html`, la stessa dell'app Android, con la sezione sulla classifica globale. Prima di inviare va messa l'email di contatto al posto del segnaposto.

## Immagini

- **Icona 128×128:** `store/icone/128.png`.
- **Schermate 1280×800** (cartella `scheda/`, su una pagina dimostrativa inventata, senza marchi; effetti cruenti spenti). Lo store ne accetta al massimo cinque. **Le cinque da caricare per la 1.0.0**, in quest'ordine: `12-corsa.png` (la corsa infinita: draghetti, corvacci, zombie nuovi, fulmini, il cruscotto), `13-livello.png` (le tre carte di un livello), `11-colpo-finale.png`, `7-orda.png`, `8-scontro.png`. Niente lucchetti in nessuna (`9-sblocco.png` non va più caricata: mostra il riquadro Premium).

Elenco della 0.9.0, superato:
  1. `6-controller.png`: il controller ad angolo coi super guerrieri, una mossa appena comandata.
  2. `7-orda.png`: il robot e la mela spalle a spalla contro l'orda, con l'ondata in corso e le tre vite in alto.
  3. `8-scontro.png`: lo scontro di energie, col tiro alla fune sopra i due raggi e i due tasti da martellare.
  4. `1-creature.png`: il robot e la mela con le creature dei barattoli (fuoco e acqua).
  5. `9-sblocco.png`: la tendina, col riquadro «Unlock Premium for free» e i lucchetti.
- Nuove con la 0.6.0, pronte se si vuole cambiarne una: `10-buco-nero.png` (il robot risucchiato dal buco nero, con l'anello dell'uscita dall'altra parte) e `11-colpo-finale.png` (la scena «in orbita», buia, con la scritta FINISHING MOVE!). Il colpo finale è gratis: `11` può prendere il posto di `1-creature.png` se si vuole mostrare la novità a chi non sblocca niente.
- Restano in cartella, di riserva: `2-opzioni.png` (la tendina con le vecchie scommesse, tolte il 12/10/2026: non usarla), `3-premium-guerrieri.png`, `4-premium-maghi.png`, `5-premium-duellanti.png`. Sono della versione 0.4: mostrano due tasti nell'angolo invece di tre.
- **Riquadro promozionale 440×280:** `scheda/promo-440x280.png` (la documentazione lo dà per richiesto).
- **Riquadro grande 1400×560:** facoltativo, non c'è.

## Altri store

- **Edge Add-ons:** lo stesso zip, nessuna tassa di iscrizione.
- **Firefox:** serve un adattamento (lo sfondo non può essere un service worker).
- **Safari:** serve l'Apple Developer Program e Xcode.

# Page Snow

Zip: `page-snow-<versione>.zip`. Gratis, senza acquisti.

## Prima di premere «Invia»

1. **Nome.** «Page Snow» è provvisorio: va cercato nello store e tra i marchi registrati.
2. **Stagione.** Le revisioni dello store possono richiedere giorni: per essere online a dicembre conviene inviarla entro metà novembre.

## Nome e descrizione breve

Nel pacchetto (`natale/_locales/`), in cinque lingue.

- **Nome:** Page Snow
- **Descrizione breve (EN):** Snow falls on the page you are viewing and piles up on it. Lights, icicles, a tree with gifts, snowmen to take apart.

## Categoria

Just for Fun (da ricontrollare nella console).

## Descrizione lunga (EN)

```
Click the icon and it starts snowing on the page you have open.

• Snow at three depths, with wind and six-pointed crystals. The nearest flakes land on the page's headings, buttons, fields and images, pile up, sparkle, slide off, and can be swept away with the pointer.
• Icicles grow under the page's elements. They drip, and break off when you touch them.
• String lights across the top of the window, red hats on headings and small pictures, frost in the corners.
• A decorated tree with gifts to open, and snowmen: touch one and it falls apart, then put it back together piece by piece.
• Now and then a sleigh crosses the sky.

The snowflake button in the corner turns everything off and on again. The page stays fully usable: text, links and forms work as usual.

In the options you can choose to have the theme start by itself on every site. Only then does the browser ask for access to all sites.

Privacy: Page Snow collects nothing and sends nothing.

Does not run on browser pages (chrome://), the Chrome Web Store or PDF files.
```

## Descrizione lunga (IT)

```
Clicca l'icona e sulla pagina che hai aperto comincia a nevicare.

• Neve a tre profondità, col vento e i cristalli a sei punte. I fiocchi più vicini si posano su titoli, tasti, campi e immagini della pagina, si accumulano, luccicano, franano, e si spazzano via col puntatore.
• Sotto gli elementi della pagina crescono i ghiaccioli. Gocciolano, e toccati si staccano.
• Lucine in cima alla finestra, cappellini rossi sui titoli e sulle immagini piccole, brina agli angoli.
• Un albero addobbato coi regali da aprire, e i pupazzi di neve: toccane uno e va in pezzi, poi rimontalo un pezzo alla volta.
• Ogni tanto una slitta attraversa il cielo.

Il tasto col fiocco nell'angolo spegne e riaccende tutto. La pagina resta usabile: testo, collegamenti e moduli funzionano come sempre.

Nelle opzioni puoi scegliere di far partire il tema da solo su ogni sito. Solo allora il browser chiede l'accesso a tutti i siti.

Privacy: Page Snow non raccoglie e non invia niente.

Non funziona sulle pagine del browser (chrome://), sul Chrome Web Store e sui PDF.
```

## Scheda «Privacy»

**Scopo unico:**

```
Page Snow decorates the page the user is viewing with an animated winter theme (falling and settling snow, lights, a tree, snowmen), turned on and off from the extension icon or its on-page button.
```

| Permesso | Testo da incollare |
| --- | --- |
| `activeTab` | The decoration is drawn on the current tab only after the user clicks the extension icon. activeTab gives access to that single tab for that click. |
| `scripting` | Used to inject the extension's own bundled script and one small style rule into the tab the user clicked on. No remote code is loaded. |
| `storage` | Remembers locally whether the user turned the theme off, and the "every site" choice. Nothing is sent anywhere. |
| Host facoltativo (`<all_urls>`) | Optional and off by default. It is requested only when the user turns on "Turn the Christmas theme on automatically on every site" in the options page, so the decoration can start without a click on each page. Page content is only measured (positions of headings, buttons, fields and images) to decide where snow settles; nothing is stored or transmitted. Turning the option off removes the permission. |

**Codice remoto:** No. **Uso dei dati:** nessuna casella spuntata; spuntare le tre dichiarazioni finali.

## Immagini

- **Icona 128×128:** `natale/icone/128.png`.
- **Schermate 1280×800** (cartella `scheda-natale/`): `1-pagina-chiara.png`, `2-pagina-scura.png`.
- **Riquadro promozionale 440×280:** `scheda-natale/promo-440x280.png`.
