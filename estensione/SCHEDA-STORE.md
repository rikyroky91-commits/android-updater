# Schede per il Chrome Web Store

Testi pronti da incollare nella console dello sviluppatore, per le due estensioni. Gli zip da caricare li scrive `python3 estensione/costruisci.py --zip` in `estensione/zip/`.

# Page Brawl

Zip: `page-brawl-<versione>-store.zip`.

## Prima di premere «Invia»

1. **Premium.** Con `premium_attivo: true` e `url_acquisto` vuoto, chi installa vede 12 tasti col lucchetto (i tre stili di personaggi, le armi, il meteo) e nessun modo di aprirli. O si collega prima il negozio, o si esce con `premium_attivo: false` (tutto gratis) e si chiude dopo.
2. **Nome.** «Page Brawl» è provvisorio: va cercato nello store e tra i marchi registrati prima di usarlo.
3. **Marchi.** I personaggi a pagamento sono inventati (nomi, facce, vestiti) e scheda e schermate non nominano prodotti o personaggi di altri: tenerlo così. Restano il robot e la mela della lotta gratis, che a qualcuno ricordano due marchi: se si vuole togliere ogni dubbio, anche loro si possono sostituire con due personaggi inventati. Un parere legale prima di vendere resta da chiedere.
4. **Effetti cruenti.** Lo store vieta la violenza gratuita. Partono spenti e le schermate non li mostrano, ma l'interruttore c'è: non so dire come lo giudica un revisore. La scelta più prudente è toglierlo dalla variante `store`.

## Nome e descrizione breve

Stanno già nel pacchetto (`_locales/`), in cinque lingue.

- **Nome:** Page Brawl
- **Descrizione breve (EN):** A robot and an apple brawl on the page you are viewing. Grab them, throw them, bet on the winner.

## Categoria e lingua

- **Categoria:** Just for Fun (da ricontrollare nella console: l'elenco cambia).
- **Lingua della scheda:** inglese; aggiungere la versione italiana qui sotto.

## Descrizione lunga (EN)

```
Click the icon and a little robot and an apple start fighting on whatever page you have open. They walk on the page's headings, buttons and images, trade punches, grab and throw each other, and dance when they win.

Join in:
• Pick a fighter up with the mouse and throw it, or use it to hit the other one.
• Drop phones, smartwatches, tablets and laptops into the ring.
• Trigger an earthquake, hand out jetpacks, or start a phone shower.
• Turn on health bars and bet tokens on the winner.
• The fighters learn: the more they fight, the more varied their moves get.

Click the icon again and everything disappears. The page itself is never changed.

Premium adds:
• Three sets of original characters, each with its own moves. Super warriors fly, fire energy waves and transform. Wizards cast freezing, shrinking and lightning spells and ride brooms. Duelists fight with energy blades.
• Weapons and bombs.
• Weather and gravity: rain, a hurricane, slow motion, Moon, space and upside-down gravity.

Privacy: Page Brawl collects nothing and sends nothing. It only runs on the tab where you click its icon, and it has no access to any other tab. Your settings and tokens are stored on your device.

Cartoon violence only. Stronger effects are off by default and can be enabled in the options.

Does not run on browser pages (chrome://), the Chrome Web Store or PDF files.
```

## Descrizione lunga (IT)

```
Clicca l'icona e un robottino e una mela cominciano a picchiarsi sulla pagina che hai aperto. Camminano su titoli, tasti e immagini della pagina, si prendono a pugni, si afferrano, si lanciano e ballano quando vincono.

Partecipa anche tu:
• Prendi un lottatore col mouse e lancialo, oppure usalo per colpire l'altro.
• Metti in campo telefoni, smartwatch, tablet e portatili.
• Scatena un terremoto, distribuisci i jetpack o fai piovere telefoni.
• Accendi le barre della vita e scommetti i gettoni su chi vince.
• I lottatori imparano: più combattono, più le mosse diventano varie.

Un altro clic sull'icona e sparisce tutto. La pagina non viene mai modificata.

Premium aggiunge:
• Tre coppie di personaggi originali, ognuna con le sue mosse. I super guerrieri volano, lanciano onde di energia e si trasformano. I maghi congelano, rimpiccioliscono, scagliano fulmini e volano sulla scopa. I duellanti combattono con lame di energia.
• Armi e bombe.
• Meteo e gravità: pioggia, uragano, rallentatore, Luna, spazio e gravità sottosopra.

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

**Informativa sulla privacy:** per un'estensione che non raccoglie dati l'indirizzo non è obbligatorio. Quando si aggiunge l'acquisto di Premium diventa necessario, perché il servizio di pagamento tratta l'email di chi compra.

## Immagini

- **Icona 128×128:** `store/icone/128.png`.
- **Schermate 1280×800** (cartella `scheda/`, su una pagina dimostrativa inventata, senza marchi; effetti cruenti spenti):
  1. `1-ko.png`: fine dell'incontro fra il robot e la mela.
  2. `2-opzioni.png`: la tendina, coi personaggi e i tasti Premium.
  3. `3-premium-guerrieri.png`: i super guerrieri trasformati.
  4. `4-premium-maghi.png`: i maghi, il fulmine.
  5. `5-premium-duellanti.png`: i duellanti, le lame incrociate.
- **Riquadro promozionale 440×280:** da fare (facoltativo, ma senza non si entra nelle vetrine dello store).

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
