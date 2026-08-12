# Passaggio di consegne — v57 (2026-08-12)

## -5. La pagina Diagnostica non diceva niente sul backup esterno

Segnalato dall'utente con screenshot della Diagnostica vera, subito dopo
aver ricevuto il fix del punto -3 sotto (il backup immediato a ogni
correzione): non c'era nessun modo di vedere da fuori se il backup fosse
configurato e funzionante. Va detto con chiarezza: la risposta precedente
di questa sessione aveva affermato che una sezione così esistesse già —
non era vero, era un'assunzione sbagliata che lo screenshot ha corretto.

**Fix**: nuova sezione «Backup esterno» in `/diagnostica` (stesso stile
delle altre tabelle della pagina): stato (Non configurato / Attivo /
Errore / Configurato ma in attesa del primo salvataggio — un quarto
stato aggiunto apposta, perché mostrare alla lettera lo stato interno
del modulo backup appena dopo un riavvio dice "non configurato" anche
quando la configurazione c'è, semplicemente perché nessun salvataggio è
ancora girato in quella sessione), ultimo salvataggio riuscito, ultimo
ripristino, ultimo esito testuale. Nuovo presenter
`web/presenters.py::stato_backup()`.

Test nuovi: `tests/test_presenters.py::TestStatoBackup` (4), `tests/
test_sito.py::TestLePagineSiDisegnano::
test_la_diagnostica_mostra_lo_stato_del_backup` (1). Dettagli completi
in `FONTI.md`.

**Per chi controlla ora se il backup del punto -3 funziona davvero**:
apri `/diagnostica` e guarda la sezione «Backup esterno». "Non
configurato" significa che `BACKUP_GIST_ID`/`BACKUP_GITHUB_TOKEN` non
sono ancora impostati su Render — vedi la guida passo passo data
all'utente in chat per configurarli.

## -4. `CPH2781` mostrava «F31» invece di «A6 Pro»: una tabella curata per le ambiguità vere

Segnalato dall'utente, con un'istruzione esplicita: «sistema dalla
radice». Verificato con più fonti indipendenti (GSMArena Cina/India,
oppo.com/en, DeviceAtlas, Gizmochina, GSMchoice): `CPH2781` è un caso
reale di stesso hardware venduto con due nomi commerciali diversi in due
mercati — «OPPO F31 5G» in Cina, «OPPO A6 Pro 5G» nei mercati
Global/India/Medio Oriente. Nessuno dei due è sbagliato:
`nome_canonico()` sceglieva «F31» solo perché è più corto.

**Fix**: nuovo file `data/nomi_modello.csv`, stessa filosofia di
`data/soc_modelli.csv` (curata a mano, corta di proposito, solo righe
verificate). `nome_canonico()` applica una riga SOLO se il nome scritto
è ancora fra quelli che `resolve()` conferma per quel codice — sceglie
fra nomi già verificati, non ne inventa mai uno nuovo. A differenza
della correzione manuale di un utente (che vive nel database effimero,
vedi punto -3 sotto), questo file viaggia nel repository: sopravvive a
un reset completo, per sempre. Prima riga: `CPH2781 → OPPO A6 Pro`; il
nome cinese resta comunque visibile come «gemello» nel menu di
correzione.

Risponde anche alla richiesta più ampia di farsi aiutare da una ricerca
esterna «per migliorare mano a mano»: la ricerca (fatta qui con più
fonti indipendenti) entra nell'app come riga verificata e firmata in un
file leggibile e contestabile — mai come un suggerimento applicato in
tempo reale. Stesso principio già scritto in `core/aiquery.py` per il
tasto «+AI»: un sistema esterno non diventa mai una fonte da solo, può
solo scegliere fra candidati che i cataloghi del progetto hanno già.

Test nuovi: `tests/test_nome_e_codice.py::TestIdentitaDalCodice` (+3),
`tests/test_nome_e_codice.py::TestCaricaOverrideNomi` (5, il parser del
CSV). Dettagli completi in `FONTI.md`.

## -3. La correzione del nome non sopravviveva a un riavvio

Segnalato dall'utente: «assicurati che quando correggo il nome il
risultato si salvi perché sembra che non lo faccia».

**Causa**: il salvataggio funzionava (finiva subito in `tracker.db`),
ma quel database vive in `/tmp` — disco effimero per scelta — e la sola
copia duratura è il backup su Gist, caricato prima SOLO a fine di ogni
scansione periodica, non più spesso di 30 minuti. Sul piano gratuito il
servizio si addormenta dopo ~15 minuti senza visite, portando via con sé
anche il thread di scansione: una correzione fatta in quella finestra
poteva restare solo nel database locale e sparire al riavvio successivo
— che su questo piano è la norma, non l'eccezione.

**Fix**: `POST /modello/correggi` e `POST /tac/salva` ora avviano subito
un backup in un thread separato (`_backup_subito()` in `web/main.py`),
senza aspettare il prossimo giro di scansione.

**ATTENZIONE — questo fix presuppone qualcosa da controllare su
Render**: se `BACKUP_GIST_ID` e `BACKUP_GITHUB_TOKEN` non sono
configurati nel pannello Render (sono `sync: false` in `render.yaml`:
esistono come variabile ma il valore va messo a mano, non viaggia nel
repository), `backup.salva()` non fa niente e NESSUNA correzione
sopravvive a un riavvio, con o senza questo fix — perché non esiste
nessuna copia duratura da nessuna parte. Vale la pena verificarlo prima
di considerare chiuso questo problema: la scheda Diagnostica del sito
mostra lo stato del backup (`core/backup.py::stato()`).

Test nuovi: `tests/test_sito.py::TestCorrezioneAvviaSubitoIlBackup` (2).
Dettagli completi in `FONTI.md`.

## -2. Un realme «7» senza lettere, e i nomi che il firmware non conosce

Segnalato dall'utente facendo dei test veri, due bug distinti con lo
stesso sintomo — nessun nome mostrato:

**Il realme «7» (`RMX2151`)**: «7» è l'UNICO nome vero che il dataset
conosce per quel codice, senza marca. Fix: `nome_canonico()` ripara SOLO
il caso in cui il nome scelto non ha UNA lettera, aggiungendo la marca
dichiarata dal dataset (mai indovinata) — non tocca `resolve()` né la
scelta già misurata di non prefissare la marca a ogni nome (avrebbe
peggiorato la coerenza Xiaomi dall'83% al 49%, vedi `FONTI.md`).

**Il codice Xiaomi `M1910F4G` (Mi Note 10)**: non aveva la forma di un
codice per `looks_like_model_code` — nessuno dei pattern in
`_MODEL_CODE_SHAPES` copriva lo stile Xiaomi «M + 4 cifre + lettera +
cifre». Non un dettaglio cosmetico: quella funzione decide
l'instradamento in tutta l'app (ricerca firmware Xiaomi, gemelli,
correzione del nome). Fix: aggiunta la forma mancante — riapre tutti e
tre i percorsi in un colpo solo. Fix complementare in `_cerca_davvero`:
quando non c'è nessun risultato con firmware ma la scheda tecnica ha
comunque risolto un nome vero, quel nome diventa l'intestazione della
pagina invece del solo codice grezzo ripetuto.

Test nuovi: `tests/test_regressione_ricerca_codice.py::
TestCodiceXiaomiStileClassico` (3), `tests/test_sito.py::
TestNomeDallaSchedaSenzaFirmware` (3). Dettagli completi in `FONTI.md`.

## -1. RMX3933, quarto giro: la forma sintetica sceglieva la marca sul nome sbagliato

Segnalato dall'utente, di nuovo con screenshot del sito: il menu di
correzione proponeva «Realme C61», non «Realme Note 60». Causa: il fix
del terzo giro generava UNA sola forma sintetica, scegliendo come base
il nome vero più corto fra tutti — «C61» (3 lettere) batteva «Note 60»
(7). Non c'è modo di indovinare algoritmicamente quale nome vero sia
«quello giusto»: fix, `_opzioni_correzione` ora genera una forma
sintetica per OGNI nome vero, non una sola — «Realme C61», «Realme Note
60», «Realme Note 60s», «Realme NARZO N61» compaiono tutte.

## -0.5. Nome commerciale scritto a mano, come per un TAC sconosciuto

Richiesta esplicita dell'utente: la stessa via d'uscita già disponibile
per un TAC sconosciuto (campo di testo libero) mancava per il nome di
un modello. Aggiunto un `<details>` annidato chiuso di default («Non
trovi il nome giusto? Scrivilo tu»), stesso campo `nome`, stessa rotta
`POST /modello/correggi` — zero cambi lato server. A differenza delle
forme proposte nel menu, un nome scritto a mano non è garantito trovare
una scheda tecnica, e la pagina lo dice esplicitamente. Compare sempre
quando c'è un codice a cui agganciare una correzione, anche quando il
menu a tendina non avrebbe alternative da proporre.

Dettagli completi di entrambi i fix in `FONTI.md`.

## 0. Il build su Render falliva quando il repository viene ricreato da zero

Segnalato dall'utente con lo screenshot del log di Render, dopo aver
cancellato l'intero repository e ricaricato tutti i file: il build
Docker falliva con `failed to calculate checksum of ref ...:
"/tracker.db": not found`.

**Causa**: `Dockerfile` copiava `tracker.db` con un nome esatto — un
file che normalmente esiste perché un workflow orario di GitHub Actions
lo committa, ma che un repository appena ricreato non ha ancora. La sua
assenza faceva fallire l'INTERA build, anche se il codice Python
(`web/main._semina_archivio()`) gestisce già benissimo un `tracker.db`
mancante (è un ramo previsto, non un errore — l'app parte comunque, da
un archivio vuoto che si ripopola).

**Fix**: `COPY --chown=app tracker.db* ./` — l'asterisco rende il file
opzionale. Verificato con una build Docker isolata (`FROM scratch`,
nessun accesso di rete necessario) sia SENZA il file (build riuscita,
prima falliva) sia CON il file (build riuscita, file copiato
correttamente) — non solo letto sulla documentazione. Dettagli in
`FONTI.md`.

Da ora in poi un repository ricreato da zero, o un primissimo deploy
prima che il workflow orario abbia mai girato, non fa più fallire la
build per questo motivo — indipendentemente da quale zip di consegna
viene applicato.

## Punto di partenza: due sessioni divergenti, riconciliate

Questo giro è partito da un caricamento dell'utente (`androidupdatermain
5.zip`) che rifletteva il lavoro di un'ALTRA sessione — con accesso di
rete pieno, che l'ambiente di questa sessione non ha verso
`versus.com`/`realme.com`/`storage.googleapis.com` (solo
`raw.githubusercontent.com`, usato dal dataset MobileModels, è
raggiungibile qui). Quella sessione aveva costruito `core/versus.py` e
`core/aer_catalog.py` (v49) e ottimizzato la velocità di ricerca (v50),
ma partiva da una copia di questa sessione precedente alla v15 (la
pagina di confronto fra due modelli): mancava del tutto.

**Riconciliazione**: la base più recente (quella con versus.com e AER)
è stata adottata come punto di partenza, e la pagina di confronto è
stata riapplicata sopra — non scelta l'una o l'altra. Verificato: 954
test passati sulla base ricevuta, prima di qualsiasi modifica.

## 1. Scheda tecnica assente per un codice, presente per il nome — stesso telefono

Segnalato dall'utente sul sito vero, con screenshot: cercare «rmx 3933»
non mostrava la scheda tecnica; cercare «realme Note 60» — lo STESSO
identico telefono, stesso codice — sì.

**Causa**: `core/specs.py::_ripiego_esterno()` (il ripiego su
versus.com per HONOR/realme/Huawei/Nothing, introdotto in v49) decide se
procedere guardando se il testo **comincia** con il nome della marca
(`versus.marca_scoperta`). Un codice modello non lo scrive mai, e nemmeno
il nome canonico scelto da `modelcodes.nome_canonico` per un codice con
più nomi veri (sceglie il più corto — vedi il punto 2 sotto): «Note 60s»
non porta «realme» in testa, «realme Note 60» sì.

Il dato per risolverlo c'era già in mano e restava inutilizzato:
`web/presenters.py::scheda_tecnica()` calcola la marca dal catalogo AER
ufficiale (`aer_catalog.lookup(codice).get("brand_aer")` — non indovinata
dal testo) ma non la passava a `specs.cerca`/`soc.per_modello`.

**Fix**: `specs.cerca()`, `specs._ripiego_esterno()` e
`soc.per_modello()` accettano ora un parametro `marca` opzionale, usato
SOLO come secondo tentativo (dopo che il testo grezzo da solo non basta);
`scheda_tecnica()` lo calcola prima di chiamarli e lo passa a entrambi.
Dettagli e log di verifica in `FONTI.md`.

Test nuovi: `tests/test_specs.py::TestRipiegoEsternoConMarca` (5),
`tests/test_specs.py::TestSocDalCatalogo::
test_marca_arriva_fino_al_ripiego_esterno` (1), `tests/
test_presenters.py` (4, file nuovo — non esisteva un test unitario per
`web/presenters.py`).

## 1bis. Stesso bug, secondo giro: RMX3933 non è nel catalogo AER

Il fix del punto 1 non bastava per RMX3933 specificamente — quel codice
non è fra i modelli che aderiscono al programma Android Enterprise
Recommended, quindi `marca_aer` restava vuota per QUALSIASI forma del
nome. Segnalato di nuovo dall'utente, con l'osservazione aggiuntiva che
«realme Note 60» non compariva affatto fra le opzioni della correzione a
mano, e che quella forma (con la marca) aveva la scheda mentre «Note 60»
(senza) no.

**Fix 1 — la marca anche dai nomi veri, non solo dall'AER**:
`scheda_tecnica()` ha ora un secondo ripiego: se l'AER non basta, guarda
tutti i nomi veri del codice (`modelcodes.resolve`) e chiede a
`versus.marca_scoperta` se uno di questi la dichiara. Per RMX3933 basta
«NARZO N61» (narzo → realme, riconosciuto senza che la parola «realme»
compaia da nessuna parte).

**Fix 2 — unire i nomi che sono la stessa forma con/senza marca**:
`_nomi_gemelli` (`web/main.py`) mostrava «Note 60» e «realme Note 60»
come due gemelli distinti — la stessa forma commerciale, non due
telefoni. Ora raggruppa per nome normalizzato (senza prefisso di marca)
e tiene solo la forma più corta per gruppo. La stessa lista alimenta il
menu della correzione a mano: ora offre solo forme davvero distinte.

Test nuovi: `tests/test_nome_e_codice.py` (+2), `tests/
test_presenters.py::TestMarcaDaiNomiVeriQuandoLAerNonBasta` (3).
Dettagli completi in `FONTI.md`.

## 1ter. Terzo giro: «realme Note 60» non può comparire perché il dataset non la scrive mai

Segnalato di nuovo dall'utente: nel menu «Non è il nome giusto?» per
RMX3933 non compare «realme Note 60». Verificato sul dataset live:
`modelcodes.resolve("RMX3933")` restituisce oggi `['C61', 'Note 60',
'Note 60s', 'NARZO N61']` — nessuna di queste forme scrive «realme» per
esteso, solo «NARZO N61» (sinonimo). Il Fix 2 sopra risolve la scheda
tecnica (si trova comunque, qualunque nome si scelga), ma i «gemelli»
sono per design solo forme VERIFICATE dal dataset: non può comparirci
una stringa che il dataset non ha mai scritto.

**Fix**: `web/presenters.py::marca_probabile()` — la logica di
rilevamento marca del Fix 1, estratta in una funzione condivisa (prima
viveva solo dentro `scheda_tecnica`) — più `web/main.py::
_opzioni_correzione(nome, gemelli, codice)`, che usa quella marca per
aggiungere, SOLO al menu di correzione (non alle pastiglie «noto anche
come», che restano gemelli puri), una forma sintetica «Marca + nome più
corto» via `versus.con_marca` — per RMX3933, «Realme Note 60». Sicuro
per costruzione: la scheda tecnica si calcola dal CODICE, non dal nome
mostrato, quindi qualunque forma si scelga nel menu resta collegata
alla stessa identica scheda — la garanzia esplicitamente richiesta
dall'utente.

Test nuovi: `tests/test_nome_e_codice.py::TestOpzioniCorrezione` (4),
`tests/test_sito.py::TestCorrezioneNomeModelloConMarcaSintetica` (2).
Dettagli completi in `FONTI.md`.

## 2. Correzione a mano del nome commerciale, per codice

Richiesta esplicita dell'utente, arrivata mentre si indagava il bug
sopra: poter dire quale, fra i nomi veri di un codice (RMX3933 ne ha
quattro: C61, Note 60, Note 60s, NARZO N61 — piattaforme regionali
diverse, non un errore), è quello giusto per il telefono che si ha in
mano — e farlo ricordare per ogni ricerca futura.

**Perché non un'euristica migliore**: verificato cercando RMX3933 su più
fonti indipendenti (rivenditori, DeviceAtlas, manuali) — «Note 60» è il
nome più diffuso globalmente, ma almeno una fonte lo vende come «Note
60s», e nessuna dice con certezza qual è "il" nome per il mercato di chi
cerca. Non è un caso da risolvere indovinando meglio: è il caso per cui
questa funzionalità esiste.

**Design**: le opzioni proposte (`risultato.opzioni_correzione`, vedi
punto 1ter) sono sempre forme collegabili a una scheda tecnica, mai un
campo di testo libero — altrimenti si rischierebbe di salvare un refuso
come se fosse un dato ufficiale.

**Dove**: nuova tabella `nomi_modello` (`core/storage.py`, `codice →
nome`, stessa idea di `imeicheck.aggiungi_tac` — una correzione umana
vince su ogni fonte scaricata). Applicata in `web/main.py::
_cerca_davvero()` come ULTIMO passaggio (vince anche sulla convergenza
col nome d'archivio), agganciata al codice tramite
`_codici_del_risultato` — la stessa funzione già usata da
`_nomi_gemelli`, non una terza via — così vale cercando con QUALSIASI
nome vero dello stesso codice, non solo con la forma scritta la prima
volta.

Nuova rotta `POST /modello/correggi`; interfaccia in un `<details>`
chiuso di default sotto i "gemelli" in `ricerca.html`, con l'opzione di
tornare alla scelta automatica.

Test nuovi: `tests/test_core.py::TestStorage` (+7, le funzioni di
persistenza), `tests/test_sito.py::TestCorrezioneNomeModello` (5,
end-to-end: senza correzione, con correzione, la correzione vale
cercando con un nome diverso, reset, invalidazione della cache).

## 3. Pagina di confronto riapplicata, poi ridisegnata

La pagina `/confronto` (v15 della sessione precedente) non esisteva
nella base ricevuta (vedi "Punto di partenza" sopra). Riapplicata prima
senza modifiche di sostanza (stessa rotta, stessi dati, stessi test).

**Poi segnalato dall'utente come confuso**: foto e nome vivevano in una
griglia CSS separata dalla tabella dei dati sottostante — nessuna
struttura teneva insieme, in verticale, «tutto ciò che appartiene ad A»
rispetto a «tutto ciò che appartiene a B».

**Fix**: foto e nome sono entrate dentro la STESSA `<table>` dei dati,
come righe di `<thead>` con `<colgroup>`/`table-layout: fixed`. Un
bordo sinistro marcato sulla colonna B, essendo la stessa tabella
dall'inizio alla fine, diventa un'unica linea verticale continua dalla
foto fino all'ultima caratteristica — il divisorio netto richiesto.
Nessun dato o funzionalità cambiati, solo la struttura HTML/CSS.
Verificato visivamente (screenshot desktop e mobile). Dettagli in
`FONTI.md`.

Test invariati (`TestConfronto`, 5 + 1 in `TestRicerca`): la struttura
del template è cambiata, il contenuto testuale verificato dai test no.

## Ricerche recenti, con la freccia giù della tastiera

Richiesta esplicita dell'utente. Nuovo `web/static/ricerche-recenti.js`:
un `<datalist>` nativo collegato alla barra di ricerca (risponde alla
freccia giù senza bisogno di un menu costruito a mano) e salvato in
`localStorage` del browser (client-side: nessun dato personale lascia il
dispositivo). Mostra le ultime 8 ricerche, più recente per prima,
deduplica senza distinguere maiuscole/minuscole, con un pulsante
«Cancella le ricerche recenti» che compare solo quando c'è qualcosa da
cancellare — solo nella barra grande della home, non ripetuto in ogni
pagina.

## Stato dei test

**1018 test passati, 416 subtest passati, 0 falliti** (954 sulla base
ricevuta → 980 → 985 → 991 → 994 → 997 → 1013 → 1018 nei giri successivi
di questa sessione).

## IMPORTANTE per chi riprende da qui: il gap del deploy

Questa sessione (Cowork, sandbox cloud) **non ha accesso a git, push o
deploy**. Ogni consegna è uno zip scaricato dall'utente
(`android-updater-fix-12ago-vNN.zip`); perché il sito su Render lo
serva davvero, qualcuno con accesso al repository (l'altra sessione con
rete piena, o l'utente stesso) deve applicarlo e pushare.

Successo dopo la consegna del v52: l'utente ha segnalato con screenshot
del sito vero che «non c'è nulla di quello che abbiamo lavorato
nell'ultimo commit» — verificato che gli screenshot corrispondevano
esattamente al comportamento PRE-fix. Non era un regresso introdotto
qui: era semplicemente che il v52 non era ancora stato applicato al
repository. Vale la pena controllare questo prima di aprire un nuovo
giro di debug quando un fix "sembra non funzionare" sul sito vero.

**Stesso principio vale ora per il punto -3**: se le correzioni
continuano a sembrare "non salvate" dopo questa consegna, il primo
sospetto non è il codice — è se `BACKUP_GIST_ID`/`BACKUP_GITHUB_TOKEN`
sono davvero configurati su Render. Senza quei due segreti, questo
fix non ha niente su cui agire.

## Cosa resta aperto

* **Verificare che il backup su Gist sia configurato su Render**
  (`BACKUP_GIST_ID`, `BACKUP_GITHUB_TOKEN` — vedi punto -3): senza,
  nessuna correzione a mano sopravvive a un riavvio, indipendentemente
  da questo o futuri fix applicativi. Ora si vede direttamente in
  `/diagnostica` → «Backup esterno» (punto -5) invece di doverlo dedurre.
* `data/nomi_modello.csv` (punto -4) ha per ora una sola riga. Crescerà
  solo quando emerge un caso concreto verificato — non è pensata per
  essere riempita preventivamente, la stessa scelta già fatta per
  `data/soc_modelli.csv`.
* La correzione a mano del nome vale per la RICERCA (`_cerca_davvero`).
  Non tocca `modelcodes.nome_canonico()` in sé, quindi punti del
  progetto che chiamano `nome_canonico` direttamente (non attraverso
  `_cerca_davvero`) — se ce ne sono, non ancora verificato — non la
  vedono. Da controllare se emerge un caso concreto.
* Nessuna pagina elenca le correzioni salvate finora (`storage.
  get_nomi_modello()` esiste ma non è ancora esposta in Diagnostica o
  altrove). Utile se le correzioni si accumulano.
* La riconciliazione fra questa sessione e l'altra (con accesso di rete
  pieno) resta manuale: ogni caricamento futuro va di nuovo confrontato
  a mano per capire cosa è cambiato dall'altra parte. Non c'è un modo
  automatico di saperlo da qui.
* La marca per il ripiego versus.com ora si trova in due modi (AER, poi
  i nomi veri del codice) ma resta possibile che un codice non abbia
  NESSUNA delle due — nessuna voce AER e nessun nome vero che comincia
  con una marca riconosciuta da `versus.marca_scoperta`. In quel caso la
  scheda resta assente, correttamente (non si inventa una marca), ma
  vale la pena controllare se capita spesso quando emerge un caso reale.
* Il divisorio della pagina di confronto è verificato visivamente in
  questa sessione, ma non con uno screenshot test automatico (il
  progetto non ne ha ancora): un cambiamento futuro al CSS potrebbe
  romperlo senza che i test esistenti se ne accorgano, dato che
  verificano il contenuto testuale, non il layout.
* La forma Xiaomi aggiunta a `_MODEL_CODE_SHAPES` (punto -2) copre lo
  stile classico «M + 4 cifre + lettera + cifre». Se emergono altri
  stili di codice non coperti (di questa o altre marche), lo stesso
  sintomo — scheda trovata, nome assente in testata — è il segnale da
  cercare.

## Consegna

Zip consegnato: `android-updater-fix-12ago-v57.zip` (sostituisce il
v56: aggiunge il punto -5, la sezione di stato del backup in
Diagnostica, segnalata dall'utente subito dopo aver ricevuto il v56).
Ricorda di applicarlo al repository vero — vedi "IMPORTANTE per chi
riprende da qui" sopra.
