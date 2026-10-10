# Passaggio di consegne — v62 (2026-08-15)

Continua direttamente da `passaggio-consegne-v61.md` (login e
approvazione del parco di test). Tre richieste di questo giro: un test
reale dell'invio email, ricerca e ordinamento per data di test dentro il
parco, e una verifica esplicita che tutto questo non rischi di far
sforare i 512 MB di RAM del piano gratuito di Render.

## Il test reale dell'email — perché non l'ho potuto fare da qui

Ho provato a inviare davvero l'email di richiesta verso
`Riccardo.cucurullo91@gmail.com` con un account Gmail via SMTP, come
farebbe il sito in produzione. **Non ci sono riuscito, e non è un bug
del codice**: l'ambiente in cui giro io ha l'accesso di rete limitato a
un elenco di indirizzi consentiti (i registri dei pacchetti, poco
altro) — l'ho verificato con una connessione diretta all'indirizzo IP
di `smtp.gmail.com:587`, che va in timeout indipendentemente da
username o password. Nessuna credenziale risolverebbe questo: è un
blocco di rete prima ancora di arrivare al login SMTP.

Il codice che invia l'email (`core/mail.py::invia`) è collaudato a
fondo con l'invio SMTP sostituito da un doppio finto (i test in
`tests/test_account.py` verificano che venga chiamato con
l'indirizzo, l'oggetto e il link giusti) — quello che non ho potuto
verificare da qui è la parte che sta FUORI dal codice: che Gmail accetti
davvero la connessione e la password per le app, e che il messaggio
arrivi nella tua casella. Render non ha questa restrizione di rete (è
un servizio pubblico, non un ambiente isolato come questo): il primo
vero test end-to-end avverrà lì, non prima.

**Cosa serve per farlo, quando applichi questa consegna:**

1. Su Render → il tuo servizio → Environment, imposta `SMTP_USERNAME`
   (un indirizzo Gmail) e `SMTP_PASSWORD` (una «password per le app»,
   generata su myaccount.google.com — non la password normale
   dell'account Google).
2. Registra un account di prova da `/registrati`.
3. Entro qualche secondo dovrebbe arrivare l'email a
   `Riccardo.cucurullo91@gmail.com` (o all'indirizzo che hai messo in
   `ADMIN_APPROVAL_EMAIL`, se l'hai cambiato) con il link di conferma.
4. Se non arriva, la richiesta resta comunque visibile e decidibile su
   `/admin/richieste` da amministratore collegato — quindi anche se il
   primo tentativo SMTP non va a segno (password per le app scritta
   male, provider che blocca l'invio automatico...) nessuno resta
   bloccato fuori dal parco di test.

Se preferisci, posso anche solo scriverti qui i passaggi e lasciare che
sia tu a fare la prova su Render direttamente — evita di dovermi dare
una password per le app, anche solo temporanea, in chat.

## -10. Ricerca e ordinamento per data di test nel parco

Richiesta esplicita: «Metti anche una ricerca dentro il parco test e la
possibilità di ordinare i dispositivi in base al tempo in cui sono
stati testati».

**Ricerca**: una casella di testo sopra la tabella (`/parco?q=...`),
filtra per marca o modello con la stessa tokenizzazione già usata dalla
ricerca dispositivi (`storage.parole_di_ricerca`, resa pubblica apposta
— prima era `_parole_di_ricerca`, uso interno solo di `storage.py`).
Filtro fatto in Python sulla lista già caricata, non con una query SQL
in più: il parco è per natura piccolo (i modelli che qualcuno ha scelto
di seguire, non l'intero catalogo), quindi non ha senso una query
dedicata solo per questo.

**Ordinamento**: un menu con due opzioni oltre al default (marca e
modello, come prima) — «Test meno recente prima» e «Test più recente
prima». La scelta più delicata è cosa fare dei dispositivi MAI testati,
che non hanno una data con cui confrontarsi: restano un gruppo a parte
invece di essere infilati nell'ordinamento per confronto di stringhe
(che li avrebbe messi arbitrariamente in cima o in fondo come effetto
collaterale, non come scelta). In cima quando l'ordine è «meno recente
prima» — sono la cosa più urgente da testare, letteralmente non sono
mai stati provati. In fondo quando l'ordine è «più recente prima» — non
hanno una recency con cui competere con chi è stato testato davvero.

Ricerca e ordinamento si combinano (`/parco?q=galaxy&ordina=meno_recente`)
e restano nell'indirizzo, quindi condivisibili o salvabili come segnalibro.

File toccati: `web/main.py` (`_ordina_righe_parco`, filtro e query
param nuovi su `pagina_parco`), `web/templates/parco.html` (il modulo
di ricerca/ordinamento, il messaggio «nessun risultato» distinto da
«parco vuoto»), `web/static/style.css` (`.parco-filtri`),
`core/storage.py` (`_parole_di_ricerca` → `parole_di_ricerca`, resa
pubblica). Test nuovi in `tests/test_sito.py::TestParcoDiTest`: ricerca
che filtra, ricerca senza risultati, ordinamento più/meno recente,
i mai-testati come gruppo a parte in entrambe le direzioni (+4).

## I 512 MB di Render — verificato, non solo dichiarato

Prima di consegnare ho misurato, non solo ragionato a tavolino:

* **Un hash scrypt costa davvero circa 16 MB**, transitori — misurato
  con `resource.getrusage` prima e dopo una chiamata a
  `auth.hash_password`: 13,4 MB → 29,6 MB di picco, poi la memoria non
  cresce più nelle chiamate successive (20 verifiche di fila restano a
  29,6 MB, nessuna perdita che si accumula). Questo era già il
  ragionamento dietro la scelta dei parametri scrypt nella consegna
  precedente (`N=2**14`, la stessa soglia già citata nel progetto per
  il precaricamento dei cataloghi); ora è un numero misurato, non solo
  un limite teorico.
* **Succede solo durante login, registrazione o cambio password** — mai
  durante la scansione in sottofondo o il caricamento dei cataloghi, che
  sono i momenti che il progetto ha già identificato come i più
  delicati per la memoria (da cui `PRERISCALDA_CATALOGHI` di default
  disattivato, un catalogo alla volta). Per un progetto a uso personale
  con pochissimi accessi contemporanei, anche più login nello stesso
  istante resterebbero un multiplo piccolo di 16 MB, non un problema.
* **Ricerca e ordinamento nel parco non aggiungono niente**: lavorano
  su liste già caricate in memoria da chiamate che esistevano prima
  (`storage.get_devices()`, `storage.get_watchlist()`), non aprono
  nuove query né caricano nuovi cataloghi.
* **Le sessioni non occupano memoria del processo**: sono cookie
  firmati letti dalla richiesta, non una tabella di sessioni attive
  mantenuta in RAM che potrebbe crescere con il numero di utenti.

Nessuna modifica di questo giro tocca i cataloghi bulk (TAC, specifiche,
SoC) che sono la vera fonte di rischio già gestita altrove nel
progetto.

## Cosa resta aperto

Oltre ai punti già elencati in `passaggio-consegne-v61.md` (CSRF non
estesa al resto del sito, nessun rate-limit sulla registrazione,
nessuna via per recuperare la password dell'unico amministratore...):

* **Il test reale dell'email non è stato fatto da questa sessione** per
  il motivo di rete spiegato sopra — resta da fare su Render al primo
  deploy di questa consegna.
* La ricerca nel parco filtra SOLO marca e modello, non lo stato del
  confronto (`invariato`/`da ritestare`/...): se in futuro il parco
  cresce molto, potrebbe valere la pena poter filtrare anche per quello
  invece di solo cercare per nome.

## Consegna

Zip: `android-updater-parco-test-ricerca-ordina-15ago.zip`. Come la
consegna precedente, contiene l'intero repository (compreso il lavoro
di Codex e la consegna v61) con sopra le modifiche di questo giro —
applica lo zip intero, non i singoli file.

Test: `python3 -m pytest -q` → 1139 passed, 452 subtests passed (era
1135/452 dopo la v61).
