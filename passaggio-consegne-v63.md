# Passaggio di consegne — v63 (2026-08-16)

Continua da `passaggio-consegne-v62.md`. Questo giro **non aggiunge una
funzione nuova**: prende il lavoro sugli account arrivato via zip
(v61 login e approvazione, v62 ricerca e ordinamento nel parco), lo
rivede riga per riga, corregge tre difetti trovati durante la revisione e
lo mette finalmente **dentro il repository** — che è il passo che
mancava perché Render potesse vederlo.

## Da dove si partiva

Lo zip `android-updater-parco-test-ricerca-ordina-15ago.zip` conteneva
l'intero repository al commit `377c389` (il lavoro di Codex) più le
modifiche v61/v62. Confrontato file per file con `origin/main`, il
delta reale è esattamente quello dichiarato nelle consegne — otto file
toccati e undici nuovi, nient'altro:

```
nuovi    core/auth.py  core/mail.py  web/account.py  web/auth_web.py
         web/contesto.py  tests/test_account.py
         web/templates/{login,registrati,admin_richieste,
                        admin_richiesta_token,account_password}.html
toccati  core/config.py  core/storage.py  render.yaml  web/main.py
         web/static/style.css  web/templates/{base,parco}.html
         tests/test_sito.py
```

Il resto delle differenze erano solo fine-riga (LF contro CRLF), non
contenuto: verificate e scartate, non applicate.

**Il sito live non aveva ancora niente di tutto questo** — controllato su
`/diagnostica`, dove la riga «Amministratore parco di test» (aggiunta
apposta dalla v62) non compariva. Ora il codice è nel repository, che è
la premessa perché compaia.

## La revisione: cosa regge e cosa no

Regge, e non è poco: scrypt con sale per password (nessuna dipendenza
esterna), sessioni firmate HMAC senza stato da mantenere, blocco dopo
cinque tentativi, tempo di risposta uniforme sugli username inesistenti,
token di approvazione salvato solo come hash, stato dell'account
riletto dal database a ogni richiesta invece che solo al login. Le
scelte sono documentate dove servono e i 33 test nuovi coprono il
percorso intero, non solo i casi facili.

I tre difetti sotto sono quelli che ho trovato — e per ciascuno c'è ora
un test che fallisce se qualcuno lo reintroduce.

### -11. Uno username già preso buttava giù il sito intero

Il peggiore dei tre, e non è un caso di laboratorio.

`/registrati` è pubblico e **non richiede che un amministratore esista
già**: chiunque può registrarsi con lo stesso nome che tu hai messo in
`ADMIN_USERNAME`. Su Render il disco è effimero, quindi
`assicura_admin()` riparte a ogni riavvio e se lo trova davanti:
l'`INSERT` violava il vincolo `UNIQUE` di `utenti.username`, e
l'eccezione risaliva da `avvio()` fino al ciclo di vita di FastAPI.

L'effetto non era «il parco di test resta senza amministratore». Era
**l'intero sito che non parte** — ricerca, dispositivi, aggiornamenti,
diagnostica, tutto quello che con gli account non c'entra nulla.

Verificato prima di correggere, non dedotto dal codice:

```
utente normale creato, esiste_admin = False
sqlite3.IntegrityError: UNIQUE constraint failed: utenti.username
```

Correzione in `web/account.py::assicura_admin`, due strati:

* si controlla che lo username sia libero prima di inserirlo, e se non
  lo è si torna una riga di diagnostica che dice cosa fare. **Non** si
  promuove l'account esistente ad amministratore: sarebbe regalare i
  permessi a chi si è registrato per primo con quel nome, che è
  esattamente il modo in cui un difetto del genere diventa un attacco.
* tutta la funzione non solleva più: qualunque guasto imprevisto
  diventa una riga in `STATO_AVVIO`, visibile su `/diagnostica`. Il
  bootstrap di un account non deve poter impedire l'avvio del sito.

### -12. Il parametro `next` poteva portare fuori dal sito

`_next_sicuro` accettava qualunque valore che cominciasse per `/` e non
per `//`. Ma **il browser normalizza la barra rovescia in barra dritta
prima di risolvere l'indirizzo**: `/\esempio.invalid` passava il
controllo come percorso locale e veniva poi seguito come
`//esempio.invalid`, cioè un altro dominio.

È il classico redirect aperto: un link a
`/login?next=/\sito-finto.invalid` porta al login VERO di questo sito
(dominio giusto, lucchetto giusto) e sbatte fuori su un sito qualunque
subito dopo aver inserito le credenziali. Ora la barra rovescia è
rifiutata ovunque nel valore — un percorso legittimo di questo sito non
ne contiene mai una.

### -13. Cambiare password non chiudeva le sessioni già aperte

Una sessione firmata non ha uno stato lato server da cancellare: era il
compromesso dichiarato della v61, e per la scadenza va benissimo. Ma
significava che il cookie ottenuto con la password VECCHIA restava
valido fino alla sua scadenza naturale (12 ore) anche dopo il cambio —
proprio nel caso che conta, perché chi cambia password di solito lo fa
sospettando che qualcun altro sia entrato.

La revoca dell'account era già gestita così (lo stato si rilegge a ogni
richiesta); la password no.

Correzione senza aggiungere una tabella di sessioni: nel payload firmato
del cookie c'è ora anche un'**impronta** dell'hash della password
(`core/auth.py::impronta_password` — sedici cifre di
`sha256(password_hash)`, che parte dall'hash già salato e quindi non
aggiunge niente da cui risalire alla password). `web/auth_web.py` la
riconfronta a ogni richiesta con l'hash attuale: quando l'hash cambia,
tutti i cookie vecchi smettono di valere nello stesso istante. A chi ha
appena cambiato password di sua volontà la risposta dà subito un cookie
nuovo, così non si butta fuori da solo.

Funziona anche per una password reimpostata a mano sul database, che
oggi è l'unica via di recupero (vedi «Cosa resta aperto»).

## File toccati in questo giro

* `core/auth.py` — `impronta_password` e `leggi_sessione_completa`
  nuove; `crea_sessione` porta l'impronta nel payload firmato.
  `leggi_sessione` resta com'era, per chi vuole solo l'id.
* `web/auth_web.py` — `utente_da_richiesta` confronta anche l'impronta.
* `web/account.py` — `assicura_admin` a prova di username occupato e di
  eccezioni; `_next_sicuro` rifiuta la barra rovescia;
  `_imposta_cookie_sessione` nuovo (usato da login e cambio password).
* `tests/test_account.py` — quattro test nuovi, uno per difetto più uno
  sul caso legittimo del redirect (`TestBootstrapAdminConflitto`,
  `TestRitornoDopoLogin`, `TestLaSessioneSeguelaPassword`).
* `tests/test_sito.py` — la sessione finta del `setUp` ora costruisce
  l'impronta come farebbe il login vero.
* `.gitignore` — rimesso: su `origin/main` non c'era più, e senza,
  `__pycache__/` e i file `.db-wal` finiscono nel repository al primo
  `git add`.

## Test

`python -m pytest -q` → **1141 passed, 458 subtests passed, 3 failed**.

I tre falliti **non c'entrano con gli account e non sono di questo
giro**: sono `TestTettoDiTempoRicerca::test_ricerca_lenta_viene_interrotta_entro_il_tetto`
e due di `TestRealmeNomiRegionali`, tutti in `tests/test_core.py`.
Verificato eseguendoli sullo zip non modificato: falliscono identici
anche lì. Il primo dipende dai tempi di esecuzione della macchina, gli
altri due dai nomi regionali Realme — vanno guardati, ma è un lavoro
suo, non una regressione di questa consegna.

`tests/test_account.py` e `tests/test_sito.py` da soli: 131 passed.

## Cosa resta aperto

Restano tutti i punti della v61/v62 (CSRF non estesa al resto del sito,
nessun rate-limit sulla registrazione, nessun «password dimenticata»,
nessun modo di revocare un account approvato dall'interfaccia, il test
reale dell'email ancora da fare su Render). In più, da questa revisione:

* **Il logout non ha protezione CSRF.** Un sito ostile può far uscire
  chi lo visita. È un fastidio, non un furto — chi lo subisce rifà
  login — ed è il motivo per cui non l'ho corretto insieme agli altri
  tre: il rimedio è aggiungere un campo nascosto in `base.html`, cioè
  toccare la testata di ogni pagina, per un guasto che non fa perdere
  nulla.
* **Il vincolo `UNIQUE` su `utenti.username` è sensibile alle
  maiuscole, le ricerche no** (`COLLATE NOCASE`). Oggi non fa danno —
  registrazione e bootstrap controllano entrambi con `NOCASE` prima di
  inserire — ma le due regole restano disallineate a livello di schema,
  e sistemarlo davvero vuol dire migrare la tabella.
* **Gli account vivono nella stessa banca dati effimera di tutto il
  resto.** La persistenza vera è il salvataggio su Gist, che gira ogni
  30 minuti (`BACKUP_EVERY_MINUTES`): una registrazione approvata nella
  mezz'ora che precede un riavvio può sparire, e la persona deve
  rifarla. L'amministratore no, quello si ricrea da solo dalle variabili
  d'ambiente — ma proprio per questo **una password cambiata da
  `/account/password` torna quella di `ADMIN_PASSWORD`** se il riavvio
  cade prima del salvataggio. Se l'account diventa una cosa seria,
  l'intervallo di backup va accorciato o gli utenti vanno tenuti
  altrove.
* **Il backup su Gist ora contiene anche gli hash delle password e le
  email di chi si registra.** Il Gist è privato (`"public": False` in
  `core/backup.py::crea_archivio`) e gli hash sono scrypt salati, quindi
  non è un'esposizione — ma il `BACKUP_GITHUB_TOKEN` adesso protegge
  dati personali oltre a un catalogo di firmware, e va trattato di
  conseguenza.
