# Schede per il Chrome Web Store

Testi pronti da incollare nella console dello sviluppatore, per le due estensioni. Gli zip da caricare li scrive `python3 estensione/costruisci.py --zip` in `estensione/zip/`.

# Pubblicare, passo per passo

Controllato sulla documentazione di Chrome il 02/10/2026 e ricontrollato il 05/10/2026 (developer.chrome.com/docs/webstore: le pagine `publish`, `register` e `cws-dashboard-listing`). Il 05/10 ho ritrovato scritti lì: il caricamento dello zip, le quattro schede da compilare, i 30 giorni per pubblicare dopo l'approvazione, il limite di due estensioni per un editore nuovo, l'email dell'account che non si cambia, le immagini richieste. La cifra dell'iscrizione (5 dollari) e l'obbligo della verifica in due passaggi vengono dal controllo del 02/10: le pagine rilette il 05/10 non li riportano, quindi si confermano al momento dell'iscrizione.

**Un punto da verificare nella console: il video.** La pagina `cws-dashboard-listing` elenca fra le cose da fornire anche il link a un video YouTube che mostra l'estensione, e dichiara facoltativo solo il riquadro grande (1400×560). Non ho potuto aprire la console per vedere se il campo blocca davvero l'invio. Se lo blocca, basta mezzo minuto di schermo registrato con la lotta, il controller e l'orda, caricato su YouTube come «non in elenco».

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
Page Brawl turns any web page into an arena. Click the icon and the fight starts right on the site you are reading: the fighters run and jump on its headings, buttons and images, so every site is a new arena with its own platforms.

TWO MODES
• Every time you start, choose how to play: Endless run or Free combat. Characters, items and surprises live in the Free combat menu.

ENDLESS RUN: A ROGUELIKE SURVIVOR
• Pick your fighter and survive round after round, with no menus in between. Every round is bigger, faster and different from the last one.
• A new enemy in almost every round: shamblers, crawlers, bloaters, armored and enraged zombies, boomers that explode, frosty biters that slow you down, leapers, spitters, brutes, a boss with a health bar, ghoul crows diving from the sky, and little dragons that shoot fire, lightning or venom.
• Ground and sky at the same time: your fighter takes off to hunt flying enemies and slams back down on the crowd below.
• Defeated enemies drop gems. Every level up pauses the action and offers three cards: automatic weapons (orbiting phones, shockwave, lightning, fire aura, homing darts, spinning blade), upgrades, and evolutions when a weapon reaches level five with its paired upgrade.
• Surprises every few seconds: a golden zombie running off with coins, a rain of gems, a chest floating down on a parachute, a frenzy that doubles your weapons.
• Duels against the other fighter, survival rounds against the clock, boss rounds with chests.
• Three lives that don't come back, and a last chance: aim your final move along a sweeping line, and if it hits, you get a life back.
• Coins stay between runs and buy permanent upgrades in the workshop. Your best score stays on your device.
• Runs are short and intense, a few minutes each, and the better you play, the longer you last.

MANY FIGHTERS
• Four families, two fighters each, switchable at the start of every run. You start with the super warriors, who fly, fire energy waves and transform. Then the wizards, who freeze, shrink and ride brooms, the duelists with energy blades, and the classic robot and apple.

FREE COMBAT
• Two fighters brawl on their own: grab them with the mouse, throw them, hit one with the other.
• Smoke bombs, jars that release fire, lightning and water creatures, weapons and bombs.
• Zombie hordes where the two team up back to back, a black hole, meteorites, rain, hurricanes, slow motion and strange gravity.
• Energy clashes you win by hammering a button, finishing moves with short cinematic scenes, transformations, health bars and token bets.
• A corner controller to command every move with one click.

KEYBOARD AND SOUND
• Play with the keyboard: Q W E R T Y for moves, A and D to walk, F to fly, Z for the final move, X C V for items. Every key can be remapped.
• Optional sound, synthesized on the spot, coming from the side of the screen where things happen.

Everything is free: nothing to unlock, nothing to buy, no account.

The power button in the corner turns everything off. The page itself is never changed. Game language: English by default, Italian, Spanish, French and German in the options.

Privacy: Page Brawl collects nothing and sends nothing. It only runs on the tab where you click its icon. Your settings, coins and records stay on your device.

Cartoon violence only. Stronger effects are off by default and can be enabled in the panel.

Does not run on browser pages (chrome://), the Chrome Web Store or PDF files.
```

## Descrizione lunga (IT)

```
Page Brawl trasforma qualsiasi pagina web in un'arena. Clicca l'icona e la lotta parte sul sito che stai leggendo: i lottatori corrono e saltano su titoli, tasti e immagini della pagina, quindi ogni sito è un ring nuovo, con le sue piattaforme.

DUE MODI
• A ogni accensione scegli come giocare: Corsa infinita o Combattimento libero. Personaggi, oggetti e imprevisti stanno nel menu del Combattimento libero.

CORSA INFINITA: UN SURVIVOR ROGUELIKE
• Scegli il tuo lottatore e sopravvivi round dopo round, senza menu in mezzo. Ogni round è più grande, più veloce e diverso dal precedente.
• Un nemico nuovo quasi a ogni round: zombie lenti, striscianti, gonfi, corazzati e rabbiosi, il botto che esplode, il gelido che ti rallenta, il saltatore, lo sputatore, il bestione, un capo con la sua barra della vita, corvacci che piombano dal cielo e draghetti che tirano fuoco, fulmini o veleno.
• Terra e cielo insieme: il tuo lottatore decolla per prendere i nemici in volo e ripiomba di schianto sulla folla.
• I nemici abbattuti lasciano gemme. A ogni livello il gioco si ferma e offre tre carte: armi automatiche (telefoni in orbita, onda d'urto, fulmine, aura di fuoco, dardi a ricerca, lama rotante), potenziamenti, ed evoluzioni quando un'arma arriva al quinto livello col suo potenziamento.
• Sorprese ogni pochi secondi: lo zombie d'oro che scappa con le monete, una pioggia di gemme, un forziere col paracadute, la frenesia che raddoppia le armi.
• Duelli contro l'altro lottatore, round di sopravvivenza a tempo, round col capo e i forzieri.
• Tre vite che non tornano, e un'ultima possibilità: mira il colpo finale lungo una linea che oscilla, e se va a segno ti ridà una vita.
• Le monete restano fra una corsa e l'altra e comprano potenziamenti permanenti nella bottega. Il tuo record resta sul tuo dispositivo.
• Partite corte e intense, pochi minuti l'una; più giochi bene, più duri.

TANTI PERSONAGGI
• Quattro famiglie, due lottatori ciascuna, da cambiare all'inizio di ogni corsa. Si parte coi super guerrieri, che volano, lanciano onde di energia e si trasformano. Poi i maghi, che congelano, rimpiccioliscono e volano sulla scopa, i duellanti con le lame di energia, e il robot e la mela classici.

COMBATTIMENTO LIBERO
• Due lottatori si picchiano da soli: prendili col mouse, lanciali, usa l'uno per colpire l'altro.
• Fumogeni, barattoli che liberano creature di fuoco, fulmini e acqua, armi e bombe.
• Orde di zombie in cui i due si alleano spalle a spalla, il buco nero, meteoriti, pioggia, uragani, rallentatore e gravità strane.
• Scontri di energie da vincere martellando un tasto, colpi finali con brevi scene, trasformazioni, barre della vita e scommesse coi gettoni.
• Un controller nell'angolo per comandare ogni mossa con un clic.

TASTIERA E AUDIO
• Si gioca anche da tastiera: Q W E R T Y le mosse, A e D per camminare, F per volare, Z il colpo finale, X C V gli oggetti. Ogni tasto si cambia.
• Audio facoltativo, sintetizzato al momento, che arriva dal lato dello schermo dove succede la cosa.

È tutto gratis: niente da sbloccare, niente da comprare, nessun account.

Il tasto di accensione nell'angolo spegne tutto. La pagina non viene mai modificata. Lingua del gioco: inglese di serie, italiano, spagnolo, francese e tedesco nelle opzioni.

Privacy: Page Brawl non raccoglie e non invia niente. Funziona solo sulla scheda in cui clicchi la sua icona. Opzioni, monete e record restano sul tuo dispositivo.

Solo violenza da cartone animato. Gli effetti più forti sono spenti e si accendono dalla tendina.

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
| `storage` | Saves the user's options, the in-game tokens and coins, the keyboard mapping and what the fighters have learned locally, so they are the same on every site. Nothing is sent anywhere. |
| Host facoltativo (`<all_urls>`) | Optional and off by default. It is requested only when the user turns on "Show the power button on every site" in the options page; it is used to place that one button on each page so the animation can be started without the toolbar icon. No page content is read or transmitted. Turning the option off removes the permission. |

**Codice remoto:** No, I am not using remote code.

**Uso dei dati:** nessuna casella spuntata (l'estensione non raccoglie dati). Spuntare le tre dichiarazioni finali: i dati non vengono venduti, non vengono usati per scopi estranei, non servono a valutare l'affidabilità creditizia.

**Informativa sulla privacy:** per un'estensione che non raccoglie dati l'indirizzo non è obbligatorio, e con la 1.0.0 tutta gratis resta così: non parte nessuna richiesta di rete. Quando si aggiunge l'acquisto di Premium diventa necessario, perché il servizio di pagamento tratta l'email di chi compra.

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
- Restano in cartella, di riserva: `2-opzioni.png` (la tendina con le scommesse), `3-premium-guerrieri.png`, `4-premium-maghi.png`, `5-premium-duellanti.png`. Sono della versione 0.4: mostrano due tasti nell'angolo invece di tre.
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
