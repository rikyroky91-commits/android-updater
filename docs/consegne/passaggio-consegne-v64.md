# Passaggio di consegne — v64 (2026-08-16)

Continua da `passaggio-consegne-v63.md`, lo stesso giorno. La v63 aveva
portato gli account in produzione; questa cambia il parco di test da
dentro, su tre richieste esplicite:

> «Le voci *rispetto all'ultima prova* e *cosa fare* sono insensate.
> Inserirei possibilità di inserire una nota nella casella *rispetto
> all'ultima prova* e inserire file dove c'è *cosa fare*. È importante
> che git salvi a ogni cambiamento, a ogni creazione di account, a ogni
> nota, a ogni click. Puoi farlo senza appesantire tutto?»

Tre chiarimenti fatti prima di scrivere codice, perché ognuno cambiava
il lavoro in modo sostanziale: che fine fanno le due colonne, dove
vivono i file, e cosa vuol dire davvero «a ogni click».

## -14. Le colonne: il pallino resta, «Cosa fare» va via

Scelta dell'utente fra tre: **tenere il pallino di stato, togliere «Cosa
fare»**, nota e allegati al loro posto.

Il motivo per cui il pallino non segue «Cosa fare» nella soppressione è
che le due colonne non erano insensate allo stesso modo. Il pallino
(«Invariato», «Mai testato») è l'unica cosa in quella tabella che il
sito sa da solo: confronta il firmware di adesso con la fotografia presa
quando hai segnato il test. «Cosa fare» invece riscriveva quel confronto
come consiglio — «Nessun retest necessario» — cioè occupava la larghezza
di una colonna per ripetere il pallino accanto con più parole. Quel
posto ora ce l'ha la nota, che è l'unica cosa che il sito NON può
sapere.

Il consiglio non è sparito del tutto: è finito nel `title` del pallino,
dove si legge passandoci sopra senza occupare spazio.

La tabella del parco ora è: Brand · Modello · Data del test · Stato ·
Note · Allegati.

## -15. La nota

Una casella di testo per riga, dentro un `<details>` chiuso: sei righe
con un'area di testo sempre aperta sono un questionario, non un elenco.
Si salva con un POST a `/parco/nota` e si torna **al parco come lo si
stava guardando** — se eri su `?q=galaxy&ordina=meno_recente`, ci
ritorni, invece di ritrovarti l'elenco intero da rifiltrare.

La nota vive nella colonna `note` di `watchlist`, che esisteva da sempre
e non era mostrata da nessuna pagina. Questo ha fatto emergere subito un
difetto latente: `/parco/aggiungi` chiama `add_to_watchlist` con nota
vuota, e l'`ON CONFLICT` sovrascriveva. Finché la nota non si vedeva non
se ne accorgeva nessuno; da adesso riaggiungere un modello già nel parco
avrebbe cancellato quello che ci avevi scritto. Ora l'aggiornamento
avviene solo se la nota nuova non è vuota.

### I link diventano un tasto

Richiesta: «quando inserisco un link nelle note lo trasformi in un tasto
"Link" senza visualizzare l'intero link». Fatto in
`web/presenters.py::nota_con_link`: un indirizzo lungo dentro una
tabella la sfonda in larghezza e non si legge comunque, quindi resta nel
`href` e nel `title` (si vede passandoci sopra) ma a schermo è un tasto
tondo di cinque lettere.

Due dettagli che non si vedono ma contano:

* **È l'unico punto del progetto dove si costruisce HTML a mano**, quindi
  l'autoescape di Jinja non lavora: ogni pezzo di testo passa per
  `escape()` prima di essere concatenato. Una nota che contiene
  `<script>` si legge come `<script>`, non si esegue.
* **Solo `http://` e `https://`** diventano tasti. Uno schema come
  `javascript:` dentro un `href` sarebbe codice che parte al click.
* La punteggiatura finale resta fuori dal link: «vedi
  https://esempio.invalid/a.» non produce un indirizzo che finisce col
  punto.

## -16. Gli allegati

Scelta dell'utente: **archivio separato dal database**, non file dentro
il database.

Era la scelta giusta e il motivo è un numero: ogni salvataggio ricarica
il file INTERO del database — oggi 5,7 MB compressi, ~7,6 MB una volta
in base64. Un allegato messo dentro il database verrebbe rispedito per
intero a ogni salvataggio, per sempre; dieci foto da 2 MB e il
salvataggio passa da 7,6 MB a una trentina, ogni volta, avvicinandosi al
tetto dei Gist.

Quindi: `allegati_parco` nel database porta **solo i metadati** (nome,
tipo, peso, impronta), il contenuto sta fuori.

**Dove, esattamente — e qui ho cambiato la proposta iniziale.** Avevo
detto «un Gist separato», che avrebbe voluto dire una variabile nuova da
creare a mano su Render. Guardando il codice si è visto che non serve: un
Gist tiene più file, la PATCH dell'API tocca solo quelli che nomina, e
`backup._leggi_da_gist` sceglie il proprio **per nome** invece di
prendere il primo. Gli allegati stanno quindi nello **stesso Gist** del
salvataggio, come file separati che non si vedono fra loro — zero
configurazione nuova, `BACKUP_GIST_ID` e `BACKUP_GITHUB_TOKEN` sono già
impostati. C'è un test che verifica proprio che caricare un allegato non
tocchi il file del database.

Altre scelte:

* **Il nome del file nell'archivio è l'impronta SHA-256 del contenuto**,
  non il nome scelto da chi carica. Due file identici occupano un posto
  solo (e allegarne uno a due modelli non lo carica due volte), e un
  nome con caratteri strani — o uguale a quello del database — non può
  rompere l'archivio. Il contenuto si cancella solo quando **nessuna**
  riga lo nomina più.
* **La copia in `/tmp` è una cache, non la conservazione**: chi apre un
  allegato appena caricato non aspetta un giro verso GitHub; dopo un
  riavvio la cache è vuota e il primo che lo apre lo riporta giù. C'è un
  test che simula proprio il riavvio.
* **Sopra 1 MB l'API dei Gist tronca** il contenuto e rimanda al
  `raw_url`: senza quel ramo si servirebbe un file a metà, che è peggio
  di un file mancante perché sembra funzionare. Collaudato.
* **Limiti**: 5 MB per file (`ALLEGATI_MAX_MB`), 10 per modello
  (`ALLEGATI_MAX_PER_MODELLO`), tipi immagine/PDF/testo. Il rifiuto dice
  il peso vero e il limite, non «errore».
* **Gli allegati sono dietro login** come il resto del parco.
* Non si ridimensionano le immagini: servirebbe Pillow, una dipendenza
  pesante per un piano da 512 MB. Il limite dichiarato costa zero e si
  capisce subito.

### Un difetto trovato mentre lo collaudavo

`migra_chiavi_dispositivo()` riscrive le chiavi del parco quando cambia
la regola che le genera, e il suo stesso docstring spiega perché: senza,
«un dispositivo seguito resterebbe agganciato a una chiave che non
esiste più». `allegati_parco` è indicizzata per chiave esattamente come
il parco — e la migrazione non la conosceva, perché l'ho aggiunta adesso.
Gli allegati sarebbero spariti dalla riga pur essendo ancora
nell'archivio esterno.

Trovato per caso, montando una demo con chiavi in forma vecchia e
vedendo la colonna Allegati vuota. Corretto, con un test che fallisce se
la migrazione torna a ignorarli — e che contiene un'asserzione in più
per non passare a vuoto il giorno in cui quella chiave smettesse di
cambiare forma.

## -17. Il salvataggio «a ogni cambiamento»

Scelta dell'utente fra tre: **subito ma raggruppato entro ~60 secondi**.

La richiesta letterale era «a ogni click». Il costo, misurato e non
supposto: 7,6 MB di invio per ogni nota scritta, ogni allegato, ogni
«Segna test», ogni registrazione — su un piano gratuito da 512 MB con la
scansione che gira in sottofondo, cioè esattamente l'appesantimento che
la domanda «puoi farlo senza appesantire tutto?» voleva evitare.

Quello che serviva davvero è che una modifica non potesse restare fuori
dal salvataggio per mezz'ora. Ora una modifica **alza una bandierina**
(`backup.segna_modificato`) e un thread la raccoglie entro
`RITARDO_SALVATAGGIO` (60 secondi): dieci modifiche di fila diventano un
invio solo invece di dieci, e la più vecchia della raffica ha comunque
aspettato meno di un minuto invece di trenta.

Tre dettagli:

* **La scansione NON alza la bandierina.** Scrive in continuazione e
  terrebbe il salvataggio sempre acceso: per lei resta
  `salva_se_serve()` con il suo intervallo di mezz'ora, che è il ritmo
  giusto per dati che si riscaricano da soli. La bandierina è per le
  azioni di una persona.
* **Si salva anche all'arresto.** Render manda un SIGTERM prima di
  spegnere: il thread si sveglia e salva subito quello che ha in
  sospeso, invece di portarselo via. C'è un test che lo verifica con un
  ritardo di 300 secondi, cioè in una situazione in cui senza quel
  passaggio la modifica sarebbe persa di sicuro.
* `_backup_subito()` in `web/main.py` non lancia più un thread per
  click: delega alla bandierina. I due test che sorvegliavano quel
  comportamento (le correzioni di nome modello e TAC) sono stati
  riscritti per collaudare la catena nuova **fino a `salva()`**, non
  solo che la bandierina si alzi.

## File

Nuovi: `core/allegati.py`, `tests/test_parco_note_allegati.py`,
`guida-account-amministratore.md` (dal giro precedente, stessa giornata).

Toccati: `core/backup.py` (bandierina, thread, arresto),
`core/storage.py` (`imposta_nota_parco`, tabella `allegati_parco` e le
sue funzioni, nota protetta in `add_to_watchlist`, migrazione delle
chiavi), `core/config.py` (`ALLEGATI_MAX_MB`,
`ALLEGATI_MAX_PER_MODELLO`), `web/main.py` (quattro rotte nuove, le
colonne, due righe di diagnostica, avvio/arresto del thread),
`web/presenters.py` (`nota_con_link`), `web/templates/parco.html`,
`web/static/style.css`, `tests/test_sito.py`.

## Test

`python -m pytest -q` → **1159 passed, 458 subtests passed, 3 failed**.

I tre falliti sono gli stessi della v63 e **non sono di questo giro**:
`TestTettoDiTempoRicerca` (dipende dai tempi della macchina) e due di
`TestRealmeNomiRegionali`, tutti in `tests/test_core.py`, verificati
identici sullo zip non modificato prima ancora di cominciare.

Il parco è stato anche provato a mano, con un sito vero su un archivio
finto: nota salvata e riletta, link diventato tasto, due allegati
elencati con il loro nome, `/diagnostica` che dice «Salvataggio continuo:
attivo (salva entro 60s da una modifica)».

## Cosa resta aperto

Oltre ai punti di v61/v62/v63 (CSRF non estesa al resto del sito, niente
rate-limit sulla registrazione, niente «password dimenticata», niente
revoca di un account già approvato, il logout senza protezione CSRF):

* **La ricerca nel parco non guarda dentro le note.** Cerca solo marca e
  modello. Ora che le note contengono il lavoro vero, cercarci dentro
  sarebbe probabilmente la cosa più utile da aggiungere.
* **Gli allegati non hanno un'anteprima.** Una foto si apre in una
  scheda nuova; non c'è una miniatura nella tabella. Farla vuol dire o
  ridimensionare le immagini (Pillow, dipendenza pesante) o mandare al
  browser il file intero come miniatura, che su una riga con dieci
  allegati è peggio del problema.
* **Nessun limite complessivo alla dimensione del Gist.** C'è il limite
  per file e per modello, ma non uno globale: con molti modelli e molti
  allegati il Gist può crescere parecchio. Non è un problema oggi (tre
  dispositivi), lo diventerebbe con cinquanta.
* **Il salvataggio all'arresto dipende da come Render spegne il
  servizio.** Se il processo venisse ucciso senza SIGTERM, l'ultima
  finestra di 60 secondi si perde comunque. È il compromesso accettato
  scegliendo il raggruppamento al posto dell'invio per click.
