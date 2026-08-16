# Guida: portare il login in produzione su Render

Controllato adesso (15/08/2026): **il sito live
(`android-updater.onrender.com/parco`) mostra ancora la tabella
pubblica, senza login** — le consegne v61/v62 non sono ancora state
applicate al repository che Render legge. I passi sotto partono da lì.

Non posso completare io questi passaggi: entrare nel tuo account
GitHub/Render, o scrivere una password/chiave al posto tuo, sono cose
che non faccio mai, nemmeno con il permesso esplicito — è una regola
che vale per qualunque credenziale, non una scelta di questo progetto.
Quello che posso fare — e ho fatto — è prepararti i valori esatti da
incollare, così restano solo copia-incolla.

## Parte A — Portare il codice su GitHub

Render fa il deploy da GitHub, non dai file che ti mando: prima questi
vanno applicati al repository vero.

1. Scarica ed estrai `android-updater-parco-test-ricerca-ordina-15ago.zip`
   (contiene già tutto: login, ricerca e ordinamento nel parco).
2. Vai su `github.com/rikyroky91-commits/android-updater`.
3. Se preferisci non usare `git`: apri la cartella estratta, seleziona
   tutti i file e le cartelle, trascinali nella pagina GitHub del
   repository (o usa "Add file → Upload files" in alto a destra).
   GitHub sovrascrive i file esistenti e aggiunge quelli nuovi
   automaticamente — è lo stesso modo in cui hai applicato le consegne
   precedenti (`git log` mostra i tuoi commit "Add files via upload").
4. In basso, scrivi un messaggio di commit (es. "Login parco di test")
   e conferma su "Commit changes".
5. Render nota il nuovo commit e avvia da solo un nuovo deploy — lo
   vedi nel pannello Render, sezione "Events", di solito entro un
   minuto.

## Parte B — Le variabili d'ambiente (il cuore della richiesta)

Su [dashboard.render.com](https://dashboard.render.com) → il tuo
servizio (`mobile-update-tracker`) → scheda **Environment** → **Add
Environment Variable**, una alla volta:

| Nome | Valore | Note |
|---|---|---|
| `ADMIN_USERNAME` | a scelta tua, es. `riccardo` | il nome utente con cui farai login |
| `ADMIN_EMAIL` | la tua email | solo per riferimento, non serve per accedere |
| `ADMIN_PASSWORD` | una password tua, **almeno 10 caratteri** | scegli tu il valore — non incollare qui una password che usi altrove |
| `SESSION_SECRET` | `b3a513ca018126e5ab1a53c7ef8db89fafc03facaa7baeaeb3fae161222ec6e1` | generata da me adesso apposta, casuale a 64 caratteri: usa questa o generane un'altra tua (vedi nota sotto) |

Facoltative, solo se vuoi ricevere davvero l'email di approvazione
(altrimenti le richieste restano visibili comunque su
`/admin/richieste` dopo il login):

| Nome | Valore |
|---|---|
| `SMTP_USERNAME` | un indirizzo Gmail |
| `SMTP_PASSWORD` | una **password per le app** di quell'account (non la password normale — si genera su [myaccount.google.com](https://myaccount.google.com) → Sicurezza → Verifica in due passaggi → Password per le app) |

**Nota su `SESSION_SECRET`**: la stringa qui sopra l'ho generata io in
questo momento, non è collegata a nessun account — puoi usarla così
com'è, oppure generarne una tua sul tuo computer con
`openssl rand -hex 32` (Mac/Linux) se preferisci che non sia mai
passata da questa conversazione.

Dopo aver aggiunto tutte le variabili, clicca **Save Changes** in
fondo alla pagina: Render riavvia da solo il servizio (non serve fare
altro). Il riavvio impiega di solito 1-2 minuti.

## Parte C — Primo accesso

1. Apri `https://android-updater.onrender.com/diagnostica` e controlla
   la riga **"Amministratore parco di test"** nella tabella
   "Cataloghi" (l'ho aggiunta apposta in questo giro): deve dire
   `creato (riccardo)` o il tuo `ADMIN_USERNAME`. Se dice "non
   configurato", una delle tre variabili non è arrivata al servizio —
   ricontrolla di averle salvate e che il deploy sia terminato.
2. Apri `https://android-updater.onrender.com/login`.
3. Entra con `ADMIN_USERNAME` e `ADMIN_PASSWORD` appena impostati.
4. Dovresti finire su `/parco`, ora protetto.

Se vedi "nome utente o password non corretti": controlla di aver
salvato le variabili su Render (non solo scritte, anche "Save Changes")
e che il deploy sia terminato (pannello Render → Events → l'ultimo
deploy deve dire "Live").

## Parte D — Provare davvero la registrazione (facoltativo ma consigliato)

1. Da un altro browser (o in incognito, per non essere già loggato),
   vai su `/registrati` e crea un account di prova.
2. Se hai impostato `SMTP_USERNAME`/`SMTP_PASSWORD`: dovrebbe arrivarti
   un'email su Riccardo.cucurullo91@gmail.com entro pochi secondi, con
   un link per approvare o rifiutare.
3. In ogni caso, da amministratore loggato puoi vedere e decidere la
   stessa richiesta su `/admin/richieste`.
4. Approva l'account di prova e verifica che riesca ad accedere a
   `/parco` da quel secondo browser.

## Cosa ho verificato/fatto io in questo giro

* Il sito live non ha ancora il login (controllato adesso, vedi sopra)
  — confermato che la Parte A è ancora da fare.
* Ho aggiunto la riga "Amministratore parco di test" in Diagnostica
  (Parte C, punto 1): prima questo dato esisteva solo internamente,
  senza aggiungerla non avresti potuto controllare da fuori se il
  bootstrap dell'account fosse andato a buon fine senza già provare
  a fare login.
* La stringa `SESSION_SECRET` sopra è generata con lo stesso metodo
  crittograficamente sicuro (`secrets.token_hex`) usato dal codice
  stesso per generarne una al volo quando manca — la differenza è che
  questa, impostata su Render, resta la stessa a ogni riavvio, invece
  di cambiare (e disconnettere tutti) ogni volta che il piano gratuito
  si riaddormenta e si risveglia.
