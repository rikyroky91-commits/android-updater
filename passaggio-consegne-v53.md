# Passaggio di consegne — v53 (2026-08-12)

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

## Stato dei test

**991 test passati, 407 subtest passati, 0 falliti** (954 sulla base
ricevuta → 980 dopo il primo giro → 985 dopo il secondo → 991 ora).

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

## Cosa resta aperto

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

## Consegna

Zip consegnato: `android-updater-fix-12ago-v53.zip` (sostituisce il
v52, che copriva solo il secondo giro di fix). Ricorda di applicarlo al
repository vero — vedi "IMPORTANTE per chi riprende da qui" sopra.
