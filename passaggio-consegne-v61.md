# Passaggio di consegne — v61 (2026-08-15)

## Contesto: questa consegna arriva dopo una review, non dopo un bug

Le versioni precedenti di questo file (v53→v60) documentano i giri di
correzione fatti da questa sessione via zip, applicati a mano al
repository. Nel frattempo il progetto è stato mostrato a un altro
agente (Codex), che ha lavorato **direttamente sul repository GitHub**
(`rikyroky91-commits/android-updater`, commit `07e1a58`→`377c389`): due
assi distinti fiducia/tipo-di-dato in `core/imeicheck.py` e
`core/config.py`, priorità di affidabilità sul TAC, tolleranza sulla
cifra di controllo IMEI, precaricamento dei cataloghi in fase di build.
La review di quel lavoro (positiva nel complesso, con tre punti aperti
verificati dal vivo) è stata consegnata a parte come documento nel
progetto Claude, non ripetuta qui.

Questa consegna riparte da lì: `git clone` della repo, aggiunge il
login del parco di test SOPRA il lavoro di Codex, non lo tocca.

## -9. Login per il parco di test, con approvazione via email

Richiesta esplicita dell'utente: «volevo che la parte del parco test sia
riservato alla login e un account con standard di sicurezza elevati e
la registrazione riservata alla accettazione solamente da me ricevendo
la richiesta a Riccardo.cucurullo91@gmail.com». Due chiarimenti fatti
prima di scrivere codice (il resto del sito è già in produzione, un
errore di progettazione qui sarebbe costato più che altrove): chi può
registrarsi (tu più chiunque tu approvi, non solo un account tuo) e
come mandare l'email (SMTP con un account Gmail, non un servizio
transazionale nuovo da configurare).

### Cosa cambia per chi usa il sito

`/parco` (pagina, e le tre azioni POST che aggiungono/tolgono un
modello o registrano un test) è ora l'unica parte del sito dietro
login. Ricerca, dispositivi, aggiornamenti, catalogo, diagnostica
restano pubblici come prima — non era nella richiesta e renderli
privati avrebbe tolto lo scopo del progetto (sapere in tempo reale se
c'è un update, anche senza account).

Chi non ha un account vede **Accedi** in testata; chi vuole un account
lo richiede da `/registrati` — nasce subito nel database ma resta
`in_attesa`, non può entrare in nessuna pagina finché l'amministratore
non lo approva.

### Come funziona l'approvazione

Un'unica persona può approvare: l'amministratore. Nasce al primo avvio
da tre variabili d'ambiente (`ADMIN_USERNAME`, `ADMIN_EMAIL`,
`ADMIN_PASSWORD`, vedi sotto) — senza tutte e tre, il parco di test
resta inaccessibile finché non le imposti, di proposito: nessun
amministratore con credenziali indovinabili scritte nel codice.

Ogni registrazione manda un'email a `Riccardo.cucurullo91@gmail.com`
(configurabile con `ADMIN_APPROVAL_EMAIL`, quell'indirizzo è il
default) con un link a token — uso singolo, scade dopo una settimana —
che apre una pagina di conferma con due pulsanti, **senza dover prima
fare login**: pensata per poterla decidere dal telefono, dal link
ricevuto. Se l'email non parte (SMTP non configurato, o un problema di
consegna) la richiesta resta comunque visibile e decidibile accedendo
come amministratore su `/admin/richieste` — l'email è una comodità, non
l'unico canale, stesso principio per cui le notifiche Telegram non sono
mai state l'unico modo di vedere un aggiornamento in questo progetto.

### Gli «standard di sicurezza elevati» richiesti, in concreto

* **Password**: `hashlib.scrypt` (stdlib, nessuna dipendenza nuova),
  sale casuale per ogni password, parametri scelti per restare dentro
  il limite di RAM del piano gratuito di Render (lo stesso vincolo già
  documentato per il precaricamento dei cataloghi). Minimo 10
  caratteri, nessuna regola di complessità obbligatoria (maiuscole/
  simboli): la letteratura NIST la sconsiglia, spinge verso password
  prevedibili più che robuste.
* **Sessioni**: un cookie httponly, `Secure` (disattivabile con
  `COOKIE_SECURE=false` solo per collaudare in locale su http), firmato
  HMAC-SHA256 — non alterabile senza conoscere la chiave di firma.
  Nessuna tabella di sessioni da mantenere: la scadenza vive dentro il
  payload firmato.
* **Blocco dopo tentativi falliti**: 5 tentativi sbagliati bloccano
  l'account per 15 minuti (`LOGIN_MAX_TENTATIVI`, `LOGIN_BLOCCO_MINUTI`),
  anche se il tentativo successivo ha la password giusta.
* **Tempo di risposta uniforme**: un login con uno username inesistente
  esegue comunque un hash scrypt (su una password fittizia) prima di
  rispondere «credenziali non valide» — altrimenti il solo tempo di
  risposta rivelerebbe quali username esistono.
* **CSRF**: doppio invio (cookie + campo nascosto) su login,
  registrazione, cambio password, approvazione/rifiuto — non estesa al
  resto del sito, che non ne aveva bisogno prima e continua a non
  averne (vedi "Cosa resta aperto").
* **Token di approvazione**: mai il valore in chiaro nel database, solo
  il suo hash SHA-256 — una lettura del database (un backup, per
  esempio) non basta a fabbricare un'approvazione.
* **Revoca in tempo reale**: se l'amministratore rifiuta un account
  dopo che questo ha già una sessione aperta, la sessione smette di
  funzionare alla richiesta successiva (lo stato si rilegge dal
  database a ogni pagina, non solo al login).

### File nuovi

* `core/auth.py` — password, sessioni, CSRF, token di approvazione.
  Solo stdlib, collaudabile senza rete (stesso principio di
  `core/util.py`).
* `core/mail.py` — l'unica email che il sito manda, stessa struttura di
  `core/notify.py` (testo separato dall'invio, l'esito torna sempre a
  chi chiama, mai un'eccezione silenziosa).
* `web/auth_web.py` — legge la sessione dal cookie della richiesta,
  guardie di accesso.
* `web/contesto.py` — template Jinja2 e il contesto comune a ogni
  pagina, estratti da `web/main.py` perché `web/account.py` doveva
  poterli usare senza creare un'importazione circolare.
* `web/account.py` — tutte le rotte: login, logout, registrazione,
  pannello approvazioni, conferma via token, cambio password.
* Cinque template nuovi in `web/templates/`: `login.html`,
  `registrati.html`, `admin_richieste.html`,
  `admin_richiesta_token.html`, `account_password.html`.
* `tests/test_account.py` — 33 test nuovi: hashing e verifica password,
  sessioni valide/scadute/manomesse, CSRF, l'intero percorso
  registrazione → email (con mock) → approvazione (sia dal pannello sia
  dal link a token) → login, blocco dopo tentativi falliti, cambio
  password.

### File toccati

* `core/config.py` — variabili nuove, tutte lette a runtime come il
  resto del file (vedi sotto per l'elenco su Render).
* `core/storage.py` — due tabelle nuove (`utenti`, `richieste_accesso`)
  e le funzioni CRUD.
* `web/main.py` — le quattro rotte del parco di test ora controllano la
  sessione prima di procedere; l'avvio crea l'amministratore se non
  esiste ancora.
* `web/static/style.css`, `web/templates/base.html` — stile dei nuovi
  moduli, e la testata mostra «Accedi» o il nome di chi è collegato.
* `render.yaml` — sei variabili nuove come `sync: false` (si impostano
  a mano sul pannello Render, mai nel repository).
* `tests/test_sito.py` — `/parco` non è più nell'elenco «ogni pagina
  risponde 200 senza login» (ha ora un test suo in `test_account.py`);
  `TestParcoDiTest` collega un account già approvato prima di ogni
  test, tramite una nuova classe base `_SitoConLogin`.

### Cosa impostare su Render prima che sia utilizzabile

Senza questi tre, il parco di test resta inaccessibile (non un bug: è
la scelta di non avere un amministratore con credenziali indovinabili):

* `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` — creano il tuo
  account al primo avvio. Cambiati una volta soli: un riavvio successivo
  con le stesse variabili NON ricrea né tocca l'account (altrimenti un
  cambio password fatto da `/account/password` sparirebbe a ogni
  riavvio del piano gratuito).
* `SESSION_SECRET` — una stringa lunga a caso (es. `openssl rand -hex
  32`). Senza, l'app ne genera una casuale a ogni avvio: funziona, ma
  disconnette tutti a ogni riavvio del piano gratuito.

Per l'email di approvazione (facoltativi — senza, la richiesta resta
comunque visibile su `/admin/richieste`):

* `SMTP_USERNAME`, `SMTP_PASSWORD` — un account Gmail e una «password
  per le app» generata su myaccount.google.com (non la password
  normale dell'account).

Test: `python3 -m pytest -q` → 1135 passed, 452 subtests passed (era
1102/450 prima di questa consegna).

## Cosa resta aperto

* **CSRF non estesa al resto del sito.** Le rotte esistenti (aggiungi/
  togli dal parco, correzione nome modello, backup...) non ne hanno mai
  avuta bisogno finché erano pubbliche; ora che il parco è dietro
  login, un attacco CSRF su quelle rotte specifiche avrebbe più senso
  di prima. Non l'ho estesa perché sarebbe un cambiamento molto più
  ampio (ogni modulo del sito), non chiesto esplicitamente — ma è il
  primo punto da considerare se l'ambito della richiesta si allarga.
* **Nessun rate-limit sulla REGISTRAZIONE in sé** (solo sul login):
  qualcuno potrebbe compilare il modulo molte volte, generando molte
  righe `in_attesa` e molte email. Impatto limitato (l'amministratore
  vede comunque tutto prima che accada nulla), ma se diventa un
  problema pratico serve un limite per IP o per email.
* **Un utente rifiutato non può richiedere di nuovo un account con lo
  stesso username** (la registrazione blocca su username già
  esistente, in qualunque stato). Scelta deliberata — impedisce di
  aggirare un rifiuto spammando la stessa richiesta — ma se capita un
  caso reale («mi sono sbagliato a scrivere l'email») serve una via per
  far ripartire quella persona, oggi non c'è.
* **Verifica email non fatta**: il campo email della registrazione non
  è confermato con un link — usato solo per sapere chi ha chiesto
  l'account, non per autenticare. Non richiesto esplicitamente, ma vale
  la pena saperlo se in futuro l'email diventasse un canale di recupero
  password (oggi non esiste un «password dimenticata»: se l'unico
  amministratore perde la password, va reimpostata ricreando l'account
  a mano nel database, non c'è un percorso automatico).
* **Nessun modo di revocare o eliminare un account dall'interfaccia**
  una volta approvato (solo rifiutarlo prima). Se serve togliere
  l'accesso a qualcuno dopo l'approvazione, oggi va fatto a mano sul
  database.
* Il resto dei punti aperti delle consegne precedenti (v53→v60) non è
  stato ricontrollato in questo giro: questa sessione si è concentrata
  sulla richiesta esplicita del login, non su una nuova revisione
  generale del progetto.

## Consegna

Zip: `android-updater-parco-test-login-15ago.zip`. Contiene l'intero
repository clonato da GitHub (commit `377c389`, il lavoro di Codex) con
sopra le modifiche di questa sessione — non solo i file nuovi: applica
lo zip intero al posto della cartella locale, non incollare i singoli
file, per non perdere il lavoro di Codex né le modifiche di questa
consegna.
