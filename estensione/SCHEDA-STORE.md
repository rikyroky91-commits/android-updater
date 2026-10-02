# Scheda per il Chrome Web Store

Testi pronti da incollare nella console dello sviluppatore. Il pacchetto da caricare è `zip/page-brawl-<versione>-store.zip` (`python3 estensione/costruisci.py --zip`).

## Prima di premere «Invia»

1. **Premium.** Con `premium_attivo: true` e `url_acquisto` vuoto, chi installa vede 19 tasti col lucchetto e nessun modo di aprirli. O si collega prima il negozio, o si esce con `premium_attivo: false` (tutto gratis) e si chiude dopo.
2. **Nome.** «Page Brawl» è provvisorio: va cercato nello store e tra i marchi registrati prima di usarlo.
3. **Marchi.** Scheda e schermate non nominano Android, Apple né il cartone a cui i super guerrieri fanno il verso. Tenerlo così. Un parere legale prima di vendere resta da chiedere.
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
• Super warriors: flight, energy waves, a giant sphere, teleport and more special moves.
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
• I super guerrieri: volo, onde di energia, la sfera gigante, il teletrasporto e altre mosse speciali.
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

**Codice remoto:** No, I am not using remote code.

**Uso dei dati:** nessuna casella spuntata (l'estensione non raccoglie dati). Spuntare le tre dichiarazioni finali: i dati non vengono venduti, non vengono usati per scopi estranei, non servono a valutare l'affidabilità creditizia.

**Informativa sulla privacy:** per un'estensione che non raccoglie dati l'indirizzo non è obbligatorio. Quando si aggiunge l'acquisto di Premium diventa necessario, perché il servizio di pagamento tratta l'email di chi compra.

## Immagini

- **Icona 128×128:** `store/icone/128.png`.
- **Schermate 1280×800** (cartella `scheda/`, su una pagina dimostrativa inventata, senza marchi):
  1. `1-ko.png`: fine dell'incontro, col balletto.
  2. `2-telefoni.png`: pioggia di telefoni.
  3. `3-opzioni.png`: la tendina, con i tasti Premium.
  4. `4-premium-sfera.png`: super guerrieri, la sfera gigante.
  5. `5-premium-uragano.png`: l'uragano.
- **Riquadro promozionale 440×280:** da fare (facoltativo, ma senza non si entra nelle vetrine dello store).

## Altri store

- **Edge Add-ons:** lo stesso zip, nessuna tassa di iscrizione.
- **Firefox:** serve un adattamento (lo sfondo non può essere un service worker).
- **Safari:** serve l'Apple Developer Program e Xcode.
