# Schede per il Chrome Web Store

Testi pronti da incollare nella console dello sviluppatore, per le due estensioni. Gli zip da caricare li scrive `python3 estensione/costruisci.py --zip` in `estensione/zip/`.

# Pubblicare, passo per passo

Controllato sulla documentazione di Chrome il 02/10/2026 e ricontrollato il 05/10/2026 (developer.chrome.com/docs/webstore: le pagine `publish`, `register` e `cws-dashboard-listing`). Il 05/10 ho ritrovato scritti lì: il caricamento dello zip, le quattro schede da compilare, i 30 giorni per pubblicare dopo l'approvazione, il limite di due estensioni per un editore nuovo, l'email dell'account che non si cambia, le immagini richieste. La cifra dell'iscrizione (5 dollari) e l'obbligo della verifica in due passaggi vengono dal controllo del 02/10: le pagine rilette il 05/10 non li riportano, quindi si confermano al momento dell'iscrizione.

**Un punto da verificare nella console: il video.** La pagina `cws-dashboard-listing` elenca fra le cose da fornire anche il link a un video YouTube che mostra l'estensione, e dichiara facoltativo solo il riquadro grande (1400×560). Non ho potuto aprire la console per vedere se il campo blocca davvero l'invio. Se lo blocca, basta mezzo minuto di schermo registrato con la lotta, il controller e l'orda, caricato su YouTube come «non in elenco».

## In breve, per questa uscita (0.9.0, Premium sbloccabile gratis)

1. `python3 estensione/costruisci.py --zip` e si carica `estensione/zip/page-brawl-0.9.0-store.zip`.
2. `premium.json` è già a posto: `premium_attivo: true`, `sblocco_gratis: true`, `url_acquisto` vuoto. Chi installa vede i lucchetti e, in cima alla tendina, il tasto **Sblocca Premium gratis**.
3. Nella scheda dello store si incollano le descrizioni di questa pagina (dicono che Premium per ora è gratis) e, nelle istruzioni per la verifica, il testo del passo 8: spiega al revisore come aprire tutto.
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
   The glove button opens the options panel. Items marked with a padlock are "Premium": during this release Premium is free. Press "Unlock Premium for free" at the top of the panel and every padlock opens. No account, no payment, no network request.
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

1. **Premium.** Scelta del 05/10/2026: si esce con `sblocco_gratis: true`. Chi installa vede i tasti col lucchetto (i tre stili di personaggi con le loro mosse, le armi, il meteo, i meteoriti, il buco nero, l'orda) e, in cima alla tendina, il tasto **Sblocca Premium gratis** che li apre tutti. Da controllare prima di inviare: `python3 estensione/costruisci.py` deve stampare «Premium si sblocca gratis anche in store/». Se invece avvisa che manca l'indirizzo di acquisto, `premium.json` non è quello giusto e i lucchetti resterebbero chiusi senza rimedio.
2. **Nome.** «Page Brawl» è provvisorio: va cercato nello store e tra i marchi registrati prima di usarlo.
3. **Marchi.** I personaggi a pagamento sono inventati (nomi, facce, vestiti) e scheda e schermate non nominano prodotti o personaggi di altri: tenerlo così. Restano il robot e la mela della lotta gratis, che a qualcuno ricordano due marchi: se si vuole togliere ogni dubbio, anche loro si possono sostituire con due personaggi inventati. Un parere legale prima di vendere resta da chiedere.
4. **Effetti cruenti.** Lo store vieta la violenza gratuita. Partono spenti e le schermate non li mostrano, ma l'interruttore c'è: non so dire come lo giudica un revisore. La scelta più prudente è toglierlo dalla variante `store`.

## Nome e descrizione breve

Stanno già nel pacchetto (`_locales/`), in cinque lingue.

- **Nome:** Page Brawl
- **Descrizione breve (EN):** A robot and an apple brawl on the page you are viewing. Grab them, throw them, bet on the winner.

La descrizione breve non cambia con questa uscita.

## Categoria e lingua

- **Categoria:** Just for Fun (da ricontrollare nella console: l'elenco cambia).
- **Lingua della scheda:** inglese; aggiungere la versione italiana qui sotto.

## Descrizione lunga (EN)

```
Click the icon and a little robot and an apple start fighting on whatever page you have open. They walk on the page's headings, buttons and images, trade punches, grab and throw each other, and dance when they win.

Join in:
• Pick a fighter up with the mouse and throw it, or use it to hit the other one.
• Smoke bombs and glass jars fall into the ring. A thrown smoke bomb blinds whoever is caught in the cloud. A thrown jar breaks and releases a small creature of fire, lightning or water that fights for whoever threw it.
• Take control: the gamepad button opens a corner controller. Pick a fighter and trigger their moves with one click.
• Trigger an earthquake with a volcanic eruption, hand out jetpacks, or start an item shower.
• Turn on health bars and bet tokens on the winner.
• First to ten wins: the tenth K.O. sends the loser flying out of the ring, then the match starts over.
• Finishing moves: about one round in three ends with a short scene. The lights go down and the winner launches the other into orbit, bounces them off the edges of the window, flattens them like a pancake, drops a huge energy sphere or a meteor on them, or cracks the floor open — and the page itself ends up cracked and scorched.
• Transformations: the robot turns into a steel colossus and the apple into a towering tree when one of them is one hit away from a K.O.
• Optional sound: off until you switch it on. Every punch, explosion, zombie and jingle is synthesized on the spot (nothing is downloaded) and comes from the side of the screen where it happens.
• Endless run that keeps escalating: pick a fighter and play alone, round after round, each one bigger than the last. Enemies drop gems, every level offers three cards with weapons that strike on their own and evolve, bosses drop chests, coins stay between runs and buy permanent upgrades. Three lives that don't come back, and an aimed final move. Your best score stays on your device.
• The fighters learn: the more they fight, the more varied their moves get.

The power button in the corner turns everything off and on again. The page itself is never changed. A short "How it works" page opens after installation and can be reopened from the panel.

Premium is free for now: press "Unlock Premium for free" at the top of the panel. It adds:
• Three sets of original characters, each with its own moves and its own transformed body (blazing crests and torn jackets, hooded knights). Super warriors fly, fire energy waves and transform. Wizards cast freezing, shrinking and lightning spells and ride brooms. Duelists fight with energy blades.
• Energy clashes: when one fighter charges an energy attack the other answers with the same one, the two beams meet and it becomes a tug of war. Two buttons pop up: hammer the one on your fighter's side to win it.
• A zombie horde that shows up on its own: the two stop fighting each other, stand back to back and hold out, with three lives, against waves that are never the same twice. They team up too: leapfrog over the partner, side swap, double strike, cannonball.
• A black hole that swallows whatever is nearby (fighters, items, zombies) and spits it out on the other side of the screen.
• Weapons and bombs, bazooka and flamethrower included.
• Weather and gravity: rain and thunderstorms, a hurricane, meteorites, slow motion, Moon, space and upside-down gravity.

Privacy: Page Brawl collects nothing and sends nothing. It only runs on the tab where you click its icon, and it has no access to any other tab. Your settings and tokens are stored on your device.

Cartoon violence only. Stronger effects are off by default and can be enabled in the options.

Does not run on browser pages (chrome://), the Chrome Web Store or PDF files.
```

## Descrizione lunga (IT)

```
Clicca l'icona e un robottino e una mela cominciano a picchiarsi sulla pagina che hai aperto. Camminano su titoli, tasti e immagini della pagina, si prendono a pugni, si afferrano, si lanciano e ballano quando vincono.

Partecipa anche tu:
• Prendi un lottatore col mouse e lancialo, oppure usalo per colpire l'altro.
• Nel ring cadono fumogeni e barattoli di vetro. Il fumogeno lanciato acceca chi finisce nella nube. Il barattolo lanciato si rompe e libera una piccola creatura di fuoco, di fulmini o d'acqua, che combatte per chi l'ha lanciato.
• Prendi il comando: il tasto col joypad apre un controller nell'angolo. Scegli un lottatore e fagli fare le sue mosse con un clic.
• Scatena un terremoto con l'eruzione, distribuisci i jetpack o fai piovere oggetti.
• Accendi le barre della vita e scommetti i gettoni su chi vince.
• Si gioca a dieci: il decimo K.O. manda lo sconfitto fuori dal ring, poi si ricomincia.
• Colpi finali: circa un round su tre si chiude con una breve scena. Si abbassano le luci e chi vince manda l'altro in orbita, lo fa rimbalzare fra i bordi della finestra, lo schiaccia come una frittella, gli lascia cadere addosso una sfera enorme o una meteora, o spacca il pavimento: e la pagina resta crepata e bruciata.
• Trasformazioni: il robot diventa un colosso d'acciaio e la mela un albero enorme quando a uno dei due manca un colpo al K.O.
• Audio facoltativo: spento finché non lo accendi. Pugni, esplosioni, zombie e fanfare sono sintetizzati al momento (non si scarica niente) e arrivano dal lato dello schermo dove succede la cosa.
• Corsa infinita che cresce senza sosta: scegli un personaggio e gioca da solo, un round dopo l'altro, ognuno più grande del precedente. I nemici lasciano gemme, a ogni livello tre carte con armi che colpiscono da sole e si evolvono, i capi lasciano forzieri, le monete restano fra una corsa e l'altra e comprano potenziamenti permanenti. Tre vite che non tornano, e un colpo finale da mirare. Il tuo record resta sul tuo dispositivo.
• I lottatori imparano: più combattono, più le mosse diventano varie.

Il tasto di accensione nell'angolo spegne e riaccende tutto. La pagina non viene mai modificata. Dopo l'installazione si apre una breve pagina «Come funziona», che si riapre dalla tendina.

Premium per ora è gratis: premi «Sblocca Premium gratis» in cima alla tendina. Aggiunge:
• Tre coppie di personaggi originali, ognuna con le sue mosse e la sua trasformazione (cresta accesa e casacca a brandelli, cavalieri incappucciati). I super guerrieri volano, lanciano onde di energia e si trasformano. I maghi congelano, rimpiccioliscono, scagliano fulmini e volano sulla scopa. I duellanti combattono con lame di energia.
• Gli scontri di energie: quando uno carica un colpo d'energia l'altro risponde con lo stesso, i due raggi si incontrano e diventa un tiro alla fune. Spuntano due tasti: martella quello dalla parte del tuo lottatore per farlo vincere.
• L'orda di zombie, che arriva da sola: i due smettono di picchiarsi, si mettono spalle a spalla e resistono, con tre vite, a ondate mai due volte uguali. E si danno una mano: cavallina sopra il compagno, cambio di lato, colpo insieme, palla di cannone.
• Il buco nero, che risucchia quello che ha intorno (lottatori, oggetti, zombie) e lo risputa dall'altra parte dello schermo.
• Armi e bombe, bazooka e lanciafiamme compresi.
• Meteo e gravità: pioggia e temporali, uragano, meteoriti, rallentatore, Luna, spazio e gravità sottosopra.

Privacy: Page Brawl non raccoglie e non invia niente. Funziona solo sulla scheda in cui clicchi la sua icona e non ha accesso alle altre. Opzioni e gettoni restano sul tuo dispositivo.

Solo violenza da cartone animato. Gli effetti più forti sono spenti e si accendono dalle opzioni.

Non funziona sulle pagine del browser (chrome://), sul Chrome Web Store e sui PDF.
```

## Scheda «Privacy»

**Scopo unico (single purpose):**

```
Page Brawl shows an animated cartoon fight on top of the page the user is viewing, started and stopped by clicking the extension icon.
```

**Giustificazione dei permessi:**

| Permesso | Testo da incollare |
| --- | --- |
| `activeTab` | The animation is drawn on the current tab only after the user clicks the extension icon. activeTab gives access to that single tab for that click, so no host permissions are needed. |
| `scripting` | Used to inject the extension's own bundled scripts and one small style rule into the tab the user clicked on. No remote code is loaded. |
| `storage` | Saves the user's options, the in-game tokens, what the fighters have learned and the Premium state locally, so they are the same on every site. Nothing is sent anywhere. |
| Host facoltativo (`<all_urls>`) | Optional and off by default. It is requested only when the user turns on "Show the power button on every site" in the options page; it is used to place that one button on each page so the animation can be started without the toolbar icon. No page content is read or transmitted. Turning the option off removes the permission. |

**Codice remoto:** No, I am not using remote code.

**Uso dei dati:** nessuna casella spuntata (l'estensione non raccoglie dati). Spuntare le tre dichiarazioni finali: i dati non vengono venduti, non vengono usati per scopi estranei, non servono a valutare l'affidabilità creditizia.

**Informativa sulla privacy:** per un'estensione che non raccoglie dati l'indirizzo non è obbligatorio, e con Premium sbloccabile gratis resta così: lo sblocco è un valore scritto nella memoria dell'estensione, non parte nessuna richiesta di rete. Quando si aggiunge l'acquisto di Premium diventa necessario, perché il servizio di pagamento tratta l'email di chi compra.

## Immagini

- **Icona 128×128:** `store/icone/128.png`.
- **Schermate 1280×800** (cartella `scheda/`, su una pagina dimostrativa inventata, senza marchi; effetti cruenti spenti). Lo store ne accetta al massimo cinque. **Le cinque da caricare per questa uscita**, in quest'ordine:
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
