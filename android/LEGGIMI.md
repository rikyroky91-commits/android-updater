# Page Brawl per Android

Lo stesso ring dell'estensione (`estensione/store/ring.js`), ma sul telefono vero:

| Dove | Come |
| --- | --- |
| **Qualsiasi app, la Home, il blocco schermo** | Un servizio di accessibilità (`Ring.java`) legge dove stanno gli elementi sullo schermo (icone, testi, tasti, notifiche, l'orologio del blocco schermo) e ci mette sopra una pagina trasparente col ring: ogni elemento diventa un corpo solido, i lottatori ci atterrano, camminano e si arrampicano. |
| **Pagine web** | In Chrome basta la bolla. In più c'è il browser dell'app (`Browser.java`), anche da «Condividi → Page Brawl» o «Apri con»: mette il ring dentro la pagina vera, come l'estensione per computer. |

Il ring parte da: la bolla col guantone (sopra tutto, anche sul blocco schermo), il riquadro nelle impostazioni rapide, «Gioca sulla Home» nell'app, o da solo quando si accende lo schermo (interruttore «Blocco schermo», spento di serie). Si chiude con ✕, col tasto Indietro, spegnendo lo schermo, o sbloccando il telefono se era partito da solo.

Dello schermo si leggono **solo le posizioni** dei riquadri, solo mentre il ring è acceso: nessun testo, niente salvato, niente inviato.

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
- `web/` le pagine dell'app: `schermo.html` + `schermo.js` (gli elementi dello schermo come `<img>` trasparenti, che ring.js conta fra i solidi), `ponte.js` (memoria e messaggi verso Java, misura dei lottatori), `comandi.js` + `mobile.css` (✕, stile da telefono, `<select>` rifatte: sopra le altre app il menu di sistema non si apre)
- `costruisci.py` costruisce l'APK

## Costruire

```
python3 android/costruisci.py            # → android/build/PageBrawl.apk
python3 android/costruisci.py --solo-asset
```

Prima di tutto `python3 estensione/costruisci.py`, se il ring del sito è cambiato: l'app prende i file da `estensione/store/`. Due ritocchi automatici, che si fermano con un errore se l'originale cambia: `prepara.js` chiama `window.__pbSalva` / `window.__pbMessaggio` al posto di `chrome.storage` / `chrome.runtime`, e in `ring.js` la misura dei lottatori (`S`) la decide `window.__pbScala` (lato corto dello schermo, 400 px = 1, per S/M/L nell'app).

Niente Gradle. Servono `aapt2`, `android.jar` (piattaforma 34), `javac`, `d8` o `dx.jar`, `apksigner.jar`: da `$ANDROID_HOME` se c'è l'SDK, altrimenti dalla cartella `$ATTREZZI_ANDROID` (di serie `~/tools`). Il Java è senza lambda: lo compila anche `dx`.

La firma è una chiave **di prova** (`firma/pagebrawl-debug.jks`, password `pagebrawl`), come la debug.keystore di Android: serve perché ogni nuova versione si installi sopra la vecchia. Per il Play Store ci vorrà una chiave vera, tenuta fuori dal repo.

## Installare

1. Se c'è l'APK fatto prima con Capacitor (stesso nome, `com.rikyroky.pagebrawl`, firma diversa): disinstallarlo.
2. Aprire `PageBrawl.apk` sul telefono e consentire l'installazione da quella app.
3. Aprire Page Brawl → **Attiva** → App installate → Page Brawl → attiva.
