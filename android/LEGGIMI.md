# Page Brawl per Android

Lo stesso ring dell'estensione (`web/static/ring.js` → `estensione/store/ring.js`), sul telefono vero, in **quattro modalità** scelte nell'app:

| Modalità | Cosa succede |
| --- | --- |
| **Blocco schermo** | Accendi lo schermo col telefono bloccato e il blocco schermo diventa il ring (la bolla c'è solo lì). Sbloccando sparisce. |
| **Tutto il telefono** | La bolla col guantone su qualsiasi app: un tocco e quella schermata diventa il ring. |
| **Solo Chrome** | La bolla compare solo mentre Chrome è in primo piano, e i solidi sono solo gli elementi della pagina. Uscendo da Chrome il ring si chiude. |
| **Nell'app** | Arene a schermo intero: **lava** (piattaforma sospesa, due pedane, chi cade nella lava va K.O.), **cielo** (pedane sopra un prato), **ring** classico. C'è anche la corsa infinita. |

In più: riquadro nelle impostazioni rapide (ring sullo schermo di adesso, in ogni modalità) e browser interno («Pagina web», anche da Condividi → Page Brawl).

**Il telefono resta usabile mentre giocano**: sopra lo schermo la finestra dei lottatori lascia passare tutti i tocchi all'app sotto; sono toccabili solo i comandi, ognuno in una finestra grande quanto lui. Per questo lì i lottatori non si prendono col dito (nelle arene sì).

**I comandi** (`Comandi.java`, nativi, uguali in tutte le modalità):
- capsula in alto: pausa · i due lottatori (anello = vita, tocco = lo comandi tu) e il punteggio · ⋯ · ✕ (toglie il gioco);
- menu ⋯: tasti sì/no, lottatori sì/no, riduci a icona (resta un puntino), opzioni del ring (la tendina del motore);
- 4 tasti nell'angolo in basso a destra: la mossa base grande nell'angolo, tre abilità attorno. Scariche sono in bianco e nero e si colorano man mano che si ricaricano (energia del lottatore e attesa dopo l'uso); quando un'abilità non in vista è pronta prende il posto della più scarica. Vibrano al tocco, al rifiuto e quando una si ricarica;
- la bolla: tocco = ring, pressione lunga = sparisce (torna riaprendo l'app o riaccendendo lo schermo).

Dello schermo si leggono **solo le posizioni** dei riquadri, solo mentre il ring è acceso: nessun testo, niente salvato, niente inviato.

## Cosa serve al motore

Tre cose opzionali in `ring.js` (12/10/2026), che sito ed estensione non usano:
- `window.__ringArena = { lava: altezza }`: pavimento = superficie della lava, chi la tocca va K.O. (punto all'altro) e rientra sulla piattaforma; i lottatori non scendono dai bordi da soli, provano a spingere giù l'avversario, chi vola giù ha un ultimo balzo. Con `lava: 0` è un'arena normale: si parte e si rientra sulla pedana più larga;
- `__ring.mosse()`, `__ring.cambia()`, `__ring.pannello(apri)`: quello che leggono i comandi nativi;
- `__ring.pausa(si)`: ferma il tempo e addormenta il ciclo.
- `window.__ringGrafica` / `__ring.grafica({ fps, risoluzione, dettaglio })`: 30/60/120 fotogrammi al secondo (sopra i 60 interpolati fra un passo della fisica e l'altro), densità del canvas 50–100 % di quella dello schermo, dettaglio basso/medio/alto (particelle 90/320/480, niente ombre sfumate nel basso). Nell'app: sezione GRAPHICS delle impostazioni, vale subito anche a partita aperta; a 120 fps l'app chiede allo schermo i 120 Hz.

## Perché l'accessibilità

Android non lascia a nessuna app sostituire il blocco schermo o le altre app: può solo disegnarci sopra. L'unica finestra che sta anche sopra il blocco schermo è quella di un servizio di accessibilità (`TYPE_ACCESSIBILITY_OVERLAY`), ed è anche l'unico modo per sapere dove stanno gli elementi delle altre app. Il permesso «sovrapponi ad altre app» non basta: non copre il blocco schermo e non dice niente di cosa c'è sotto.

Su Android 13 e successivi, per un'app installata da file l'interruttore dell'accessibilità è grigio finché non si apre **Info app → ⋮ → Consenti impostazioni con restrizioni**. L'app lo spiega («Interruttore grigio?»).

## I file

- `app/java/com/rikyroky/pagebrawl/`
  - `Ring.java` il servizio: bolla, lettura dello schermo, finestra del ring, ponte `PB` con la pagina
  - `Riquadro.java` il riquadro delle impostazioni rapide
  - `Principale.java` la schermata dell'app (in codice, niente layout XML)
  - `Browser.java` il browser col ring nella pagina
  - `Memoria.java` la memoria del ring (le chiavi di `chrome.storage.local` dell'estensione) e le opzioni
  - `Comandi.java`, `Disegni.java`, `OspiteVista.java` i comandi nativi (capsula, menu, 4 tasti) e dove si appoggiano
  - `Arena.java` le arene a schermo intero
- `web/` le pagine dell'app: `schermo.html` + `schermo.js` (gli elementi dello schermo come `<img>` trasparenti, che ring.js conta fra i solidi), `arena.html` (le tre arene), `ponte.js` (memoria e messaggi verso Java, misura dei lottatori), `comandi.js` + `mobile.css` (stile da telefono, tendina a foglio, `<select>` rifatte: sopra le altre app il menu di sistema non si apre)
- `costruisci.py` costruisce l'APK

## Costruire

```
python3 android/costruisci.py            # → android/build/PageBrawl.apk
python3 android/costruisci.py --aab      # + PageBrawl.aab per il Play Store
python3 android/costruisci.py --aab --leggera   # piano B senza accessibilità (PageBrawl-lite.*)
python3 android/costruisci.py --solo-asset
```

Prima di tutto `python3 estensione/costruisci.py`, se il ring del sito è cambiato: l'app prende i file da `estensione/store/`. Ritocchi automatici, che si fermano con un errore se l'originale cambia: `prepara.js` chiama `window.__pbSalva` / `window.__pbMessaggio` al posto di `chrome.storage` / `chrome.runtime` e salta la scelta del modo sopra lo schermo, e in `ring.js` la misura dei lottatori (`S`) la decide `window.__pbScala` (lato corto dello schermo, 400 px = 1, per S/M/L nell'app).

Niente Gradle. Servono `aapt2`, `android.jar` (piattaforma 36: `android-36.jar` in `~/tools`, da github.com/Sable/android-platforms), `bundletool.jar` per l'AAB, `javac`, `d8` o `dx.jar`, `apksigner.jar`: da `$ANDROID_HOME` se c'è l'SDK, altrimenti dalla cartella `$ATTREZZI_ANDROID` (di serie `~/tools`). Il Java è senza lambda: lo compila anche `dx`.

La firma è una chiave **di prova** (`firma/pagebrawl-debug.jks`, password `pagebrawl`), come la debug.keystore di Android: serve perché ogni nuova versione si installi sopra la vecchia. Per il Play Store ci vorrà una chiave vera, tenuta fuori dal repo.

## Play Store (1.5.0, 12/10/2026)

Guida, fattibilità, testi e risposte: documento «Page Brawl su Google Play: guida e fattibilità» nel progetto.
- Target API 36 (obbligatorio dal 31/08/2026): `Bordi.java` gestisce lo schermo da bordo a bordo e il tasto Indietro di Android 16; nelle arene capsula e tasti stanno fuori dalla tacca.
- Avviso e consenso per l'accessibilità (norme Play per chi non è uno strumento di accessibilità): `Principale.disegnaAvviso()`; senza `Memoria.consenso` il servizio non guarda niente.
- Con `--aab` i personaggi di partenza sono robot e mela (i guerrieri richiamano Dragon Ball); `--guerrieri` li rimette.
- `--leggera`: manifest senza servizio di accessibilità né riquadro, `Variante.LEGGERA` nasconde le modalità. Codice versione +1.
- La chiave di caricamento `firma/pagebrawl-upload.jks` (+ `.txt` con la password) resta fuori da git; con Play App Signing Google firma le APK vere.
- Foto e video dello store: `store/promo/cattura.py` (riprese del motore vero in Chromium, con `vetrina.js` che ridisegna i comandi nativi) e `store/promo/componi.py` (schermate, grafica, icona, video). Escono in `store/consegna/` (fuori da git). L'informativa sulla privacy è `web/static/pagebrawl/privacy.html`.

## Premium (12/10/2026)

Gratis con sblocco Premium a acquisto unico (Riccardo: «facciamo gratuito con sblocco premium»). Il Premium apre i tre gruppi che il motore sa già chiudere (`window.__ringPremium.bloccate`): `guerrieri` (stili di personaggi), `armi`, `meteo` (imprevisti grossi e gravità).
- `Premium.java` lo stato (nelle opzioni dell'app, non nella memoria del gioco che le pagine web possono scrivere) e gli ascoltatori; `Acquisto.java` la scheda con prezzo, «Restore purchase», «Not now» (attività trasparente, apribile anche dal servizio); `ponte.js` definisce `__ringPremium` e `__pbPremium(si)`; `PB.premium()` dà "libero", "attivo" o "chiuso", `PB.compra(gruppo)` apre la scheda.
- `app/java-billing/PremiumGoogle.java` il pagamento vero (Google Play Billing 9.1.0, prodotto `premium` a acquisto unico, conferma entro 3 giorni). Lo compila solo Gradle; senza (APK di prova) vale il Premium finto: tutto aperto.
- Build del Play: `.github/workflows/android-play.yml` (Gradle 8.14.3, AGP 8.13, progetto in `android/gradle-progetto/` che legge i sorgenti di `android/app` e quello che prepara `costruisci.py --gradle --aab [--leggera]`). Esce una pre-release `android-<commit>` con gli AAB non firmati; si firmano con `python3 android/costruisci.py --firma PageBrawl-completa-nonfirmato.aab`.

## 1.5.1 e 1.6.0

- **1.5.1** (13/10/2026, su `main` dal 16/10): spegnendo lo schermo il ring si **sospende** invece di chiudersi (la partita o la corsa riprende da dov'era), niente più comandi rimasti sullo schermo dopo la chiusura, «Leaderboard» nel menu ⋯, l'APK di prova esce nella pre-release insieme agli AAB.
- **1.6.0** (16/10/2026, versionCode 11, lite 12): il motore della 1.2.0 dell'estensione (meno tempi morti, super guerrieri più fluidi, Limit Break, maghi a distanza con la respinta, missioni, capo ogni cinque round, rimescola carte; vedi `estensione/LEGGIMI.md`, «La 1.2.0»). Nel secondo giro: parry, carica letale, round più lunghi, crediti e allenamento (stesso dettaglio). Senza tastiera il parry passa dalla voce «Parata», che ora hanno tutti gli stili; non è detto che i quattro tasti nativi la mostrino sempre (`Comandi.java` sceglie le abilità da mostrare), da provare sul telefono. Niente di nuovo lato Java: il cruscotto nativo della corsa non mostra ancora missioni e prossimo capo, che si vedono nelle schermate del motore (scelta, carte, riepilogo).

## Installare

1. Se c'è l'APK fatto prima con Capacitor (stesso nome, `com.rikyroky.pagebrawl`, firma diversa): disinstallarlo.
2. Aprire `PageBrawl.apk` sul telefono e consentire l'installazione da quella app.
3. Aprire Page Brawl → **Attiva** → App installate → Page Brawl → attiva.
