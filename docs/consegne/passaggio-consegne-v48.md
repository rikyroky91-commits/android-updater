# Passaggio di consegne — v48 (2026-08-11)

## Punto di partenza

Il tasto ✨ AI in produzione veniva descritto come rotto: «o non trova
niente o trova alternative ai modelli». Invece di leggere solo il codice,
questa sessione ha **usato il sito vero** (android-updater.onrender.com)
con un browser, per vedere cosa succedeva davvero, non cosa ci si
aspettava succedesse. Nel farlo sono usciti tre problemi diversi, non
uno solo — e un quarto se ne è aggiunto mentre la sessione era in corso
(il sito è andato out of memory su Render).

## 1. Il bug vero dietro «trova alternative ai modelli»

Cercando «Xiaomi Poco X6» (sia a mano sia via AI, stesso risultato):
la scheda tecnica mostrava correttamente «Xiaomi Poco X6», ma la
tabella aggiornamenti sopra era intestata **«POCO X6 Pro 5G
Indonesia»** — un telefono diverso.

Causa: `core/sources.py::_piu_vicini` (usata da Xiaomi, Honor, Vivo,
Oppo quando non c'è un nome esatto in catalogo) sceglieva il candidato
con **meno parole in più**, assumendo che «meno parole aggiunte» = «più
vicino al telefono cercato». Per il POCO X6 questo si rompe: il modello
base non ha una voce propria nel tracker Xiaomi, esiste solo in coppia
con l'altro marchio («Redmi Note 13 Pro 5G / POCO X6 5G Global», 9
parole), mentre «POCO X6 **Pro** 5G Indonesia» (un telefono diverso) ne
ha solo 5. A parità di criterio vinceva il Pro.

**Fix**: si guarda la parola SUBITO DOPO la corrispondenza, non solo
quante parole in più ci sono in totale. Se è un marcatore di gamma
(pro, ultra, plus, max, lite, se, fe, neo, gt, prime, turbo, power,
mini, edge, air, fold, flip — `_PAROLE_VARIANTE`), il nome è un
telefono diverso e si scarta a favore di un candidato che non cambia
gamma, se ce n'è uno. Verificato che «Xiaomi Poco X6» ora risponde
correttamente con le varianti Redmi Note 13 Pro 5G / POCO X6 5G.
Tutti i test esistenti (compreso il caso «Redmi Note 13» già coperto)
continuano a passare — la regola vecchia resta corretta nei suoi casi,
qui si aggiunge il caso che non copriva.

## 2. Il tasto AI era vincolato allo stesso motore della ricerca normale

`aiquery.candidati_per()` costruisce l'elenco da cui il modello sceglie
usando `expand_query`, `suggest.suggest`, `did_you_mean` — gli stessi
strumenti della ricerca normale. Se quegli strumenti non trovano
niente, l'AI non ha nulla su cui lavorare: non è un motore diverso, è
lo stesso motore con un filtro sopra. Per molte ricerche funziona bene
(«quel samsung a07 nero preso l'anno scorso» → Galaxy A07, corretto),
ma non poteva MAI fare meglio della ricerca normale su un IMEI o su un
input senza candidati.

**Fix — due casi dove il tasto rispondeva peggio di «Cerca» sullo
stesso testo, entrambi in `web/main.py::api_interpreta`:**

- **IMEI**: quindici cifre non somigliano a nessun nome di catalogo,
  quindi finiva in «nessun candidato da sottoporre al modello». Ora si
  riconosce l'IMEI PRIMA di chiamare il modello e si passa il numero
  così com'è: la pagina del risultato lo riconosce da sola (stessa
  `pagina_ricerca` di sempre, stesso confronto fra i database TAC).
- **Nessuna corrispondenza utile**: prima si fermava su un messaggio
  d'errore nel pannello AI. Ora si ripiega sul testo digitato — la
  stessa ricerca che «Cerca» avrebbe fatto comunque — tenendo il
  motivo del mancato aiuto come spiegazione, non come vicolo cieco.

Regola generale ora vera: il tasto AI non risponde mai con meno di
quello che darebbe «Cerca» sullo stesso testo. Test aggiornati in
`tests/test_sito.py` (`TestInterpreteAI`).

## 3. Out of memory su Render — la causa più probabile

A metà sessione il sito è andato OOM e si è riavviato (visto nei log
Render, subito dopo una ricerca). Causa più probabile, trovata
leggendo `core/sources.py`: **`fetch_xiaomi()`, `fetch_honor_aer()`,
`fetch_vivo_aer()`, `fetch_oppo_aer()` non avevano nessuna cache** —
ogni singola ricerca su un modello Xiaomi/Honor/Vivo/Oppo riscaricava
e rianalizzava l'INTERA fonte da zero. Per Xiaomi è lo storico
completo dal 2015 (migliaia di righe di YAML). `RICERCHE`
(`web/cache.py`, già esistente) evita di ripetere la STESSA ricerca,
ma non aiuta quando cambia il modello e resta il brand — che è il caso
comune quando più persone (o la stessa persona, come in questa
sessione) provano modelli diversi nello stesso brand in pochi minuti.

`web/cache.py` dice esplicitamente, dal 2026-08-10: «su un host da 512
MB — dove questa applicazione è **già stata riavviata d'ufficio per
memoria**». Non è la prima volta.

**Fix**: aggiunta una cache a tempo (`_CacheDiFonte`, stesso pattern
già usato per il canale Telegram e per ARB) a tutte e quattro le
fonti — 20 minuti per Xiaomi (aggiorna spesso), un'ora per le pagine
AER di Honor/Vivo/Oppo (cambiano raramente). Gli errori di rete NON
vengono messi in cache, per poter riprovare subito. Diversi test in
`test_core.py`/`test_niente_rete.py` mockavano `http_get` aspettandosi
una chiamata fresca per test: aggiornati con `reset_*_cache()` nel
`setUp`/`tearDown`, stesso pattern già in uso per `reset_telegram_cache`.

**Da verificare dopo il deploy**: se i riavvii per memoria continuano
anche con questa cache attiva, il prossimo sospetto è `/dispositivi`
(costruisce fino a 200 righe con risoluzione SoC per riga — locale, non
rete, ma comunque CPU) o il numero di sorgenti "ricche" tenute in
memoria insieme (8912+64398 codici TAC, 4766 schede specifiche, 14079
nomi SoC). Non toccato in questa sessione: prima si guarda se il fix
sopra basta da solo.

## 4. Canale Telegram OPlus ritirato

Su richiesta esplicita: il canale (`oplus_telegram`) risultava «0 voci»
nell'ultima scansione in Diagnostica — non stava dando niente da
sfruttare — e nel frattempo costava comunque un giro di rete a ogni
scansione periodica e a ogni ricerca live su un modello Oppo/OnePlus.
Spostato da `SOURCES` a `RETIRED_SOURCES` (stesso meccanismo già usato
per `oppo_official`) e tolto dall'elenco dei lookup live
(`_STRUCTURED_LOOKUPS_LIST`). **Il codice resta tutto**
(`fetch_oplus_telegram`, `_lookup_oplus_telegram`,
`core/telegram_tracker.py`): si riattiva con
`ENABLED_SOURCES="oplus_telegram"` per la scansione, e rimettendo a
mano la riga `StructuredLookup(...)` per la ricerca live, quando si
deciderà di riprenderlo.

## 5. Una pagina di risultato sola, non tre riquadri impilati

Per un IMEI riconosciuto la pagina mostrava tre riquadri separati, ognuno
col proprio bordo rosso, che ripetevano lo stesso nome/codice in forme
leggermente diverse fino a cinque volte («Galaxy A07», «SM-A075F» ×5).
Il processore — il dato tecnico più importante della scheda — finiva in
fondo al terzo riquadro, in una griglia di quattro voci tutte con lo
stesso peso visivo.

**Fix**:
- `_imei.html` diviso in due: `_imei_identita.html` (una riga
  compatta — «IMEI riconosciuto · TAC ...» — dentro lo stesso riquadro
  del risultato) e `_imei_confronto.html` (il confronto fra i database
  TAC e la correzione manuale, ora in un `<details>` dopo la scheda —
  disponibile, non in cima a competere per l'attenzione).
- `ricerca.html`: un `<section class="esito">` solo, che contiene IMEI
  + nome + firmware + «forse cercavi», invece di due sezioni separate.
- `_scheda.html`: nuovo parametro `senza_intestazione` (passato solo
  da `ricerca.html`, dove il nome l'ha già detto il riquadro sopra;
  `dispositivo.html` non lo passa e mantiene il titolo, perché lì è
  l'unico punto che dice quale telefono è).
- Il processore ha ora una riga sua (`.cpu-in-evidenza`), più grande e
  separata dalla griglia RAM/Archiviazione/Batteria, invece di essere
  la prima di quattro voci identiche.
- CSS: quando esito e scheda sono adiacenti (`.esito-con-scheda`) si
  fondono in un pannello solo — stesso bordo, angoli continui, una
  riga sottile a separarli invece di uno spazio vuoto e un'ombra
  ripetuta.

Non ancora fatto in questa sessione: verifica visiva sul sito vero
dopo il deploy (il rendering è stato controllato con `TestClient` +
i test esistenti, non con uno screenshot del sito in produzione).

## 6. La versione Streamlit (`app.py`) è tornata, in parallelo

Rimossa dal repository nella v47 (test rossi, mai caricata
`.streamlit/config.toml`, rallentava il build di Render). L'utente ha poi
chiesto esplicitamente di mantenere «attive e aggiornate tutte e due le
versioni» — sito FastAPI e dashboard Streamlit — e un secondo screenshot
ha mostrato Streamlit Cloud in un ciclo di crash («Main module does not
exist: .../app.py») perché il file, ovviamente, non c'era più.

**Fix**: `app.py` ripristinato dal contenuto salvato nel progetto Claude
(non da git — non c'era più nella storia recente in una forma pulita).
Le due app ora hanno **due file di dipendenze separati**, non uno solo:

- `requirements.txt` (radice) — quello che **Streamlit Cloud scopre da
  solo**: `streamlit`, `requests`, `feedparser`. `app.py` non importa
  pandas, quindi pandas non c'è.
- `requirements-web.txt` — quello che **il `Dockerfile` installa per
  Render** (`COPY --chown=app requirements-web.txt .`): il contenuto che
  prima stava nell'unico `requirements.txt`, invariato.

Perché due file e non uno: Streamlit Cloud e Render fanno build
completamente separate, su host diversi. Un file solo avrebbe rimesso
streamlit (e la sua dozzina di dipendenze indirette) nell'immagine
Docker di Render a ogni build — esattamente il peso e il tempo di build
che la v46 aveva tolto apposta. Con due file, ogni host installa solo
quello che gli serve davvero.

`tests/test_dipendenze.py` (che protegge da un incidente di produzione
reale del 2026-08-05, un pin di `starlette` mancante) è stato aggiornato
di conseguenza: legge `requirements-web.txt` per le garanzie sul sito
(niente streamlit/pandas lì dentro), e un nuovo
`TestRequirementsStreamlit` legge `requirements.txt` per le garanzie
sul lato Streamlit (streamlit c'è, pandas no).

**Non fatto in questa sessione**: verifica che Streamlit Cloud riparta
davvero dopo il deploy — il crash era nel «main module does not exist»,
non in un errore di `app.py` stesso, quindi ripristinare il file dovrebbe
bastare, ma non è stato osservato in produzione.

## 7. Ricerca live più corta nel caso peggiore

Il reclamo «il sito è sempre lentissimo» (dopo aver escluso che fosse un
problema mobile — la UI su schermo stretto va bene) non riguarda solo
gli OOM del §3: riguarda anche il tempo che OGNI ricerca nuova (non in
cache) impiega quando la ricerca live su Google News (`search_model_live`
in `core/sources.py`) non trova niente al primo tentativo.

Causa: `SEARCH_BUDGET_SECONDS` (12s) controlla il tempo TOTALE fra un
tentativo e il successivo, ma non interrompe una richiesta già partita —
`requests.get(timeout=SEARCH_HTTP_TIMEOUT)` con `SEARCH_HTTP_TIMEOUT=8`
poteva bloccare la ricerca per gli 8 secondi pieni, e con
`_news_attempts` che prova fino a quattro formulazioni per candidato,
due tentativi consecutivi in timeout bastavano da soli a spiegare i
16,6s misurati il 10/08 (il commento in `web/cache.py` li cita) — il
budget di 12s non li fermava perché il secondo tentativo era già
partito quando il primo tornava.

**Fix**: `SEARCH_HTTP_TIMEOUT` abbassato da 8 a 5 secondi
(`core/config.py`). Le ricerche che TROVANO qualcosa rispondono in
frazioni di secondo — misurato, non solo dedotto — quindi accorciare il
timeout non le tocca; accorcia solo l'attesa nel caso peggiore, quando
una fonte non risponde affatto. Configurabile via variabile d'ambiente
`SEARCH_HTTP_TIMEOUT` come prima, per chi volesse tararlo diversamente
in produzione.

## 8. Un codice con più nomi commerciali veri non ne nascondeva più di uno

Segnalato con due esempi concreti, in produzione: cercando `realme
RMX3933` la pagina rispondeva «C61» — e chi ha in mano quel telefono lo
sa come «Note 60». Cercando `CPH2781` rispondeva «OPPO F31», mentre è
anche «OPPO A6 Pro». Non è un dato inventato: `modelcodes.resolve()`
(che unisce KHwang9883/MobileModels e **la lista ufficiale Google dei
dispositivi certificati Play Store**,
`storage.googleapis.com/play_public/supported_devices.csv` — sì, la
pagina che l'utente ha segnalato durante questa stessa sessione: era già
una delle due fonti di questo modulo, non una nuova) restituisce
davvero più nomi per lo stesso codice — `RMX3933` è insieme «C61»,
«Note 60», «Note 60s» e «NARZO N61», la stessa piattaforma venduta con
nomi diversi in mercati diversi. `nome_canonico()` ne sceglie UNO, per
necessità (una chiave sola per dispositivo in archivio), col criterio
già esistente (il più corto) — corretto per l'identità interna, ma
silenzioso sull'ambiguità verso chi guarda la pagina.

**Fix**: nuova funzione `_nomi_gemelli()` in `web/main.py` — non
un «forse», come `_forse_cercavi` (somiglianza di stringa), ma i nomi
VERI dello stesso codice, letti dalla stessa riga del dataset. Compaiono
in un paragrafo proprio, «Questo codice è noto anche come:», subito
sotto il risultato. Gestito anche il caso in cui il codice cercato ha
la marca davanti («realme RMX3933», non ha la forma di un codice finché
non si toglie «realme» — stessa correzione già fatta altrove in
`expand_query` per la stessa ragione, misurata: senza, i gemelli
mostrati erano quelli del codice **del nome trovato** — RMX3930, il
codice proprio di «C61» — non quelli del codice scritto, RMX3933).
Test in `tests/test_nome_e_codice.py` (`TestIdentitaDalCodice`, quattro
nuovi casi) e uno end-to-end in `tests/test_sito.py`.

## 9. Il logo del telefono sbagliato

Segnalato con uno screenshot: cercando lo stesso `realme RMX3933`, la
scheda tecnica mostrava un logo Xiaomi al posto di uno realme. Causa:
`core/images.py::find_device_image`, che cerca su Wikipedia e prende il
PRIMO risultato senza verificare che parli davvero del telefono cercato
— rischio che il commento del modulo segnalava già come noto
("Wikipedia... risponde sempre qualcosa e proprio per questo può
rispondere il telefono sbagliato"), ma mai trasformato in un controllo
vero.

**Fix**: `_titolo_pertinente()`, nuova funzione — il titolo trovato deve
condividere almeno una parola (di almeno tre lettere) con la domanda,
o viene scartato a favore di nessuna immagine piuttosto che
un'immagine sbagliata. Criterio deliberatamente permissivo (una parola
sola, non un confronto sulla marca) perché lo scopo non è un confronto
esatto — è scartare un titolo che non c'entra nulla. Test in
`tests/test_core.py::TestImmagineDispositivo`.

## 10. I 4 link di verifica IMEI erano nel codice ma non si vedevano

Segnalato come funzione mancante — non lo era: `imeicheck.link_verifica()`
li restituisce sempre, ma il fix §5 di questa stessa sessione li aveva
spostati dentro il `<details>` del confronto TAC, insieme alla tabella
più ingombrante. Chi cerca un IMEI non apre quel riquadro per scoprire
che i link ci sono — la funzione era nel codice ma introvabile, che per
chi la usa equivale a non esserci.

**Fix**: i 4 link («Controlla lo stesso IMEI su un'altra fonte») si
sono spostati in `_imei_identita.html`, sempre visibili subito sotto il
risultato. Il `<details>` di `_imei_confronto.html` resta per la
tabella di confronto dettagliata e la correzione manuale — quello sì
materiale da consultare solo a bisogno.

## 12. "Tutti i modelli" Oppo/Xiaomi/HONOR/realme/Motorola (11/08/2026, stesso giorno)

Richiesta ancora più esplicita: scheda tecnica e ultimo aggiornamento per
**ogni modello** di queste 5 marche. Prima di aggiungere altro codice, ho
misurato quanto è già coperto — cambia molto marca per marca (dettaglio
completo in `FONTI.md`, sezione dedicata):

- **Oppo, Xiaomi, Motorola: la scheda tecnica è già per ogni modello**,
  gratis, senza altro lavoro — sono 3 delle 11 marche coperte da
  `specs.py` (archivio GSMArena, ~4700 schede, si aggiorna da solo). Non
  lo sapevo con certezza fino a stamattina: l'ho verificato leggendo il
  perimetro dichiarato del modulo.
- **HONOR e realme restano fuori da `specs.py`**: aggiunti altri 4 modelli
  verificati a mano (realme Note 60 — **il tuo telefono, RMX3933**, ora
  anche con il chip oltre che con il nome —, Honor Magic6 Pro, realme 14
  Pro+), che si sommano ai 7 di stamattina. **11 modelli in tutto: un
  inizio più ampio, non "tutti".**
- **Firmware ("ultimo aggiornamento")**: Xiaomi e Motorola erano già a
  posto (tracker MIUI/HyperOS e mirror lolinet, 35 modelli 2022-2025).
  Oppo è parziale ma è già il massimo ottenibile senza infrangere le
  regole del progetto (vedi sotto). **realme è il buco più profondo delle
  cinque**: nessuna fonte — nemmeno community — copre firmware corrente
  per realme, verificato di nuovo oggi con una ricerca dedicata.
- **Ho cercato seriamente un'alternativa** prima di scrivere "non c'è
  soluzione": le API OTA ufficiali di Oppo/realme richiedono di fingersi
  l'app del telefono — è la stessa regola già scritta nel progetto per
  OxygenUpdater, non un limite nuovo. Cercato un tracker community per
  realme o HONOR equivalente a quello che già copre OnePlus/Oppo
  (`oplus_arb`): non trovato, solo mirror dello stesso archivio legacy già
  noto. Se un giorno ne emerge uno nuovo, va misurato con lo stesso metodo
  prima di collegarlo (non basta che esista, va contato quante release
  vere dà su un campione — è così che si è deciso di ritirare il canale
  Telegram al punto 4).

## 11. Investimento su HONOR/HUAWEI/realme/Nothing (11/08/2026)

Richiesta dell'utente: catalogo specifiche e firmware "cosi per ogni marca
grande", con priorità su chip e versione Android per ogni modello. Lavoro
di ricerca e primo lotto di dati, dettagliato in `FONTI.md` (sezione
"Investire su HONOR, HUAWEI, realme, Nothing"):

- **Nessun dataset sostitutivo trovato**: ripetuta la ricerca di un
  catalogo pronto multi-marca aggiornato; stessa conclusione già
  documentata — solo script di scraping da eseguire in proprio o dataset
  a livello di nome commerciale (inutili dove serve il codice esatto).
- **`data/soc_modelli.csv` esteso** con 11 righe (7 modelli recenti fra le
  4 marche fuori dal perimetro di `specs.py`), ciascuna verificata a mano
  su GSMArena l'11/08/2026 — stesso metodo già in uso per la serie Galaxy
  S, non uno scarico bulk. Nuovi test in
  `tests/test_soc.py::TestMarcheFuoriDalPerimetroSpecs`.
- **Scoperta di scopo su HUAWEI**: da Mate 70 in poi (dic. 2024) i telefoni
  Huawei non sono più Android — HarmonyOS NEXT non ha base AOSP. Per quei
  modelli "manca il firmware Android" sarebbe un dato falso, non
  incompleto. Il progetto non distingue ancora questo caso da un vero
  buco — vedi punto aperto qui sotto.
- **Nothing ha una pista reale**, diversa da Oppo/OnePlus/realme (buco
  confermato senza alternative): l'archivio community
  `spike0en/nothing_archive` è attivo, aggiornato, alimentato da OTA
  ufficiali — ma non ancora integrato (richiede un parser per le sue
  tabelle HTML).
- **Verificato Samsung**: la ricerca live di un codice `SM-` qualunque
  (non solo i ~23 della lista di scansione periodica) passa comunque dal
  confronto multi-regione in `_lookup_samsung()` — nessuna modifica
  necessaria, era già a posto.
- **Motore IA (`aiquery.py`)**: valutato, non modificato. I buchi trovati
  sono di disponibilità del dato (nessuna fonte esiste), non di
  interpretazione — non è un problema che il motore IA possa risolvere
  per design (non inventa mai un dato).

## 13. «realme c63» rispondeva «C61»: un nome ambiguo usato come identità

Segnalato dall'utente con uno screenshot dal sito vero, dopo il lavoro dei
punti 11-12: cercando «realme c63» la pagina mostrava «C61» — niente
foto, niente CPU, aggiornamenti di RMX3930 (il vero C61 secondo Android
Enterprise Recommended) invece di RMX3939 (il vero C63, verificato in
questa stessa sessione). Domanda dell'utente: "aggiornamento firmware su
quali basi?" — domanda giusta, perché la base era un dato vero ma di un
telefono diverso.

**Causa**: `core/modelcodes.py::resolve("RMX3939")` restituisce
`['C61', 'C63', 'C65s', 'NARZO N63']` — il dataset community
(KHwang9883/MobileModels) registra "C61" come nome ANCHE di RMX3930 e
RMX3933, non solo di RMX3939. `core/scan.py::forme_equivalenti()` provava
ogni nome restituito come forma di ricerca equivalente, senza controllare
che il nome fosse univoco: la fonte ufficiale (AER, dato vero) rispondeva
per "C61" con i dati di RMX3930, e quella risposta sostituiva
silenziosamente quella cercata.

**Fix**: `modelcodes.resolve_senza_ambiguita()`, nuova funzione — tiene
solo i nomi che risolvono a un solo codice (verificato col percorso
inverso `codes_for_name`). Usata in `forme_equivalenti()` al posto di
`resolve()` nei tre punti che espandono un codice ai suoi nomi. Stesso
principio applicato a `nome_canonico()` (sceglie IL nome da mostrare per
un codice): un nome non ambiguo ora vince su uno ambiguo, prima del
criterio alfabetico che prima faceva vincere "C61" su "C63". Corretta
anche la nota di copertura in `web/presenters.py::scheda_tecnica`, che
diceva "specifiche non disponibili" pure quando il processore ERA stato
trovato dalla tabella curata — la stessa indagine l'ha resa visibile.

Dettaglio completo (con l'output reale delle chiamate, non solo la
descrizione) in `FONTI.md`, sezione "Bug reale trovato dall'utente".
Nuovi test, tutti senza rete:
`tests/test_nome_e_codice.py::TestNomeAmbiguoNonReindirizzaAUnAltroTelefono`
e `tests/test_sito.py::TestNotaCoperturaConChipTrovato`. Suite completa
dopo la correzione: 901 test passati (era 896 prima di questo bug).

## 14. Stesso bug, secondo codice: cercare «RMX3939» rispondeva coi dati di «RMX3930»

Segnalato dall'utente subito dopo aver ricevuto il fix del punto 13, con
altri due screenshot: cercando `RMX3939` DIRETTAMENTE (non più il nome
«realme c63»), la pagina mostrava titolo e CPU giusti ma una riga
"aggiornamenti" contraddittoria — "RMX3939 — stesso dispositivo di
«realme C61», codice RMX3939: realme C61 (RMX3930) — Android 14 di
fabbrica...". Domanda dell'utente: "ti aspettavi questo risultato?
perché io no" — onestamente no, perché veniva da un percorso di codice
che il fix del punto 13 non toccava.

**Causa**: un bug GEMELLO del punto 13, ma in una funzione diversa.
Verificato leggendo la pagina ufficiale realme vera: la sigla «C61»
compare davvero due volte, in due punti distinti della stessa pagina (una
riga AER a sé, e dentro il gruppo composto di RMX3939) — non
un'invenzione del dataset community, la fonte più autorevole del
progetto lo fa anche lei. Ma la causa immediata era
`core/sources.py::expand_query()` — la funzione che genera le forme di
ricerca per OGNI fonte strutturata (realme compresa), separata da
`scan.py::forme_equivalenti()` corretta al punto 13 e non esaminata
insieme ad essa. Chiamava `modelcodes.resolve(codice)` senza filtro,
aggiungendo "C61" come forma A SÉ STANTE — e "C61" da solo risolve
legittimamente al VERO C61 (RMX3930), risposta giusta per la domanda
"C61", sbagliata per la domanda "RMX3939".

**Fix**: `expand_query()` ora usa `resolve_senza_ambiguita()` anziché
`resolve()`. Nuova `core/sources.py::_realme_nomi_ambigui()` — stesso
principio applicato alla mappatura ufficiale realme (separata dal dataset
community), usata per filtrare i candidati interni di `_lookup_realme()`.

**Correzione al criterio stesso**, scoperta testando questo fix: la prima
versione di `resolve_senza_ambiguita` scartava un nome condiviso da
QUALUNQUE altro codice — troppo severo, misurato sulla suite: rompeva
`SM-A325F/M/N → "Galaxy A32"` (tre codici regionali per lo STESSO
Samsung, non un'ambiguità). Criterio corretto: un nome resta valido solo
se ogni codice fratello che lo rivendica ha lo stesso insieme completo di
nomi — non basta contare i codici, conta se sono davvero lo stesso
telefono. Stesso principio applicato a `_realme_nomi_ambigui()`, per non
rompere allo stesso modo `RMX3491/3492/3493 → "realme 9i"`.

Dettaglio completo (con l'output reale delle chiamate) in `FONTI.md`.
Nuovo test, senza rete, che riproduce la struttura a due voci della
pagina vera: `tests/test_core.py::TestRealmeNomeCondivisoDaDueCodici` (4
test). Suite completa dopo la correzione: 905 test passati, 407 subtest
passati, zero falliti (era 901 prima di questo bug).

## 17. «sm-921b» non trova nulla: chiarito, non un bug — più il feedback visivo alla ricerca

Due richieste distinte dall'utente nello stesso messaggio, con screenshot
della ricerca «sm-921b» che non trova firmware e propone «SM-S921B» come
alternativa.

**La domanda "se scrivo in minuscolo non lo trova?"**: verificato col
codice, non solo a occhio — la ricerca uppercasa la query PRIMA di ogni
confronto (`core/sources.py::_code_candidates`, `normalizza_codice_modello`),
quindi maiuscole o minuscole non fanno nessuna differenza:

```python
>>> sources.looks_like_model_code("sm-921b")
False
>>> sources.looks_like_model_code("SM-921B")
False
>>> sources.looks_like_model_code("Sm-921B")
False
```

tutte e tre false, identiche. La causa vera è un'altra: il codice reale è
`SM-S921B` (una S dopo il prefisso, poi le tre cifre e la lettera finale),
e «sm-921b» manca esattamente quella lettera — non è scritto in minuscolo,
è INCOMPLETO. Senza quella lettera il testo non ha la forma di un codice
Samsung riconosciuto (`_MODEL_CODE_SHAPES` la richiede esplicitamente), e
il motore corregge già l'errore da solo mostrando «Forse cercavi»
(`core/suggest.py::did_you_mean` → `codici_simili`, un confronto per
similarità fra codici) — che è esattamente il comportamento visto nello
screenshot: nessun crash, nessun dato sbagliato, solo un suggerimento al
posto di un risultato diretto. Nessuna modifica al codice per questo
punto: la richiesta ha portato a verificare l'ipotesi (maiuscole/minuscole)
e a escluderla con dati, non a trovare un bug.

**Il feedback visivo mentre cerca**: qui sì una richiesta concreta,
implementata. Il tasto «Cerca» è un submit GET vero (ricarica la pagina,
non una chiamata AJAX): su una ricerca live che interroga più fonti,
passano diversi secondi senza che nulla si muova sullo schermo, e sembra
che il tasto non abbia funzionato. Nuovo file `web/static/ricerca.js`,
incluso in `base.html` per ogni pagina: all'invio del form `.ricerca`,
il tasto si disabilita, mostra una rotellina e il testo cambia in
«Cercando…» — stesso linguaggio visivo già usato per il tasto ✨ AI
(`ai.js`, `.rotella`), colori adattati al bottone verde invece che
indaco. Gestito anche il ritorno con «Indietro» del browser (bfcache):
altrimenti la pagina potrebbe ripresentarsi col tasto ancora disabilitato
dalla ricerca precedente. Verificato che il form e lo script compaiono
nell'HTML reso (`TestClient`, senza rete) e che tutta la suite (905 test)
resta verde — nessun test automatico dedicato al comportamento JS lato
browser, che questo progetto non ha mai avuto strumenti per testare.

## Cosa resta aperto

0. **HONOR: gap di copertura noto, non un bug nuovo — verificato con un
   caso reale**. IMEI `865911065397905` → TAC `86591106` → HONOR 70,
   codice `FNE-NX9` (letto e separato correttamente dall'anno
   concatenato nel dato grezzo, verificato riga per riga — non sembra
   un troncamento). Il risultato mostra solo il nome perché HONOR non è
   nel catalogo specifiche (`nota_copertura` lo dichiara già) e la fonte
   ufficiale Honor (AER) conferma il modello ma non pubblica una
   versione firmware interrogabile per dispositivo — sono due limiti
   GIÀ dichiarati onestamente dalla pagina (`senza_firmware`,
   `nota_copertura`), non un dato inventato o sbagliato. Resta aperto SE
   l'utente vuole che si investa nell'aggiungere una fonte firmware
   Honor più precisa, o HONOR al catalogo specifiche: è un lavoro
   separato, più grande di un fix, non affrontato qui.
1. **Deploy e osservazione**: tutti i fix sopra sono nel codice, non
   ancora in produzione. Da guardare in Diagnostica e nei log Render
   dopo il deploy: se il sito resta lento o va ancora OOM, il prossimo
   passo è profilare `/dispositivi` (vedi §3) — anche se una lettura del
   codice in questa sessione lo trova già ottimizzato (nessuna chiamata
   di rete, solo le prime 200 righe costruite, non tutte e millecinque-
   cento) — o considerare una cache anche sul risultato della ricerca
   live per lo STESSO modello fra ricerche diverse (oggi la cache
   `RICERCHE` in `web/cache.py` copre solo la ricerca identica, non due
   ricerche diverse sullo stesso telefono).
2. **Streamlit Cloud**: da osservare dopo il deploy che il ripristino di
   `app.py` risolva davvero il ciclo di crash (vedi §6).
3. **Test dal vivo del tasto AI in produzione con traffico reale**: i
   fix sono coperti da test automatici e da prove manuali nel browser
   durante la sessione, ma non da un periodo di osservazione in
   produzione.
4. **Suite completa verificata**: 905 test passati, 407 subtest passati,
   zero falliti (`python3 -m pytest tests/`), inclusi i test aggiornati
   per i punti 4, 6, 8, 9, 10, 11, 12, 13 e 14 di questo documento.
5. **Estensione del catalogo specifiche a HONOR/HUAWEI/realme/Nothing**:
   `data/soc_modelli.csv` è passato da 89 a 126 righe in questa sessione,
   con un inserimento metodico marca-per-marca su richiesta esplicita
   dell'utente (realme, poi HONOR, con Oppo/Xiaomi/Motorola già coperti
   automaticamente da `specs.py` — vedi punto 11) fatto in due round —
   dettaglio riga per riga e le due correzioni fatte durante il lavoro
   (sigle chip MediaTek indovinate poi tolte; una fonte scartata perché
   incoerente) in `FONTI.md`. Resta comunque una copertura parziale su un
   mercato di centinaia di modelli: se l'utente vuole continuare, il
   lavoro è ripetibile (una riga verificata a mano alla volta) ma non ha
   una scorciatoia automatica — nessun dataset pronto esiste, per motivi
   già documentati in `FONTI.md`.
6. **HUAWEI: distinguere "non è più Android" da "manca il dato"**: i
   modelli da Mate 70 in poi (HarmonyOS NEXT) non sono più Android. Il
   progetto non ha ancora un modo per etichettare questo caso in modo
   distinto da un vero buco di copertura firmware — rischio concreto di
   mostrare "non disponibile" dove la risposta corretta sarebbe "questo
   telefono non usa più Android". Lavoro non affrontato in questa
   sessione, consigliato come priorità prima di altri interventi su
   Huawei.
7. **Archivio firmware Nothing non ancora integrato**: `nothing_archive`
   (community, aggiornato, OTA ufficiali) è una fonte reale trovata in
   questa sessione ma richiede un parser per le sue tabelle HTML — non
   costruito qui, vedi punto 11.
8. **Fallback specifiche HONOR/realme per nome (versus.com/hdblog.it),
   indagato ma non costruito**: dettaglio in `FONTI.md`, sezione "Siti di
   confronto come fonte specifiche". Hanno dati reali (chip, RAM, OS) ma
   MAI il codice modello — utilizzabili solo come fallback per nome, sotto
   la tabella curata, mai sopra. Non implementato qui perché da questo
   ambiente non arrivano richieste dirette a quei siti (stesso limite di
   rete già visto con `codeload.github.com`): si vede solo la lettura
   mediata di `WebFetch`, non l'HTML vero, e costruire un parser su una
   struttura non vista significherebbe indovinare. Da fare dalla sessione
   con accesso di rete normale, misurando la resa reale (hdblog.it ha già
   risposto 429 a due richieste isolate — va verificato con un rate-limit
   serio) prima di collegarlo.
9. **Nomi ambigui: corretti due casi trovati dall'utente, non un audit
   sistematico**. I punti 13 e 14 correggono "C61" (community e fonte
   ufficiale realme) perché sono i casi che l'utente ha segnalato con
   screenshot dal sito vero — non una ricerca esaustiva di ogni nome
   condiviso da più codici nei due dataset. È anche emerso, correggendo il
   punto 14, che **due percorsi di codice diversi generano le "forme di
   ricerca equivalenti"** per fonti diverse: `scan.py::forme_equivalenti()`
   e `sources.py::expand_query()` — corretti entrambi ora, ma se in futuro
   ne comparisse un terzo (una nuova fonte con la propria logica di
   espansione nomi↔codici, come realme aveva già la propria prima di
   questo giro) andrebbe controllato con lo stesso criterio, non dato per
   scontato che erediti la correzione. Se l'utente nota ancora un caso di
   "dati del telefono sbagliato", il modo più rapido per trovarlo è lo
   stesso usato qui: cercare il codice ESATTO che il sito mostra come
   sbagliato, non solo il nome, perché è cercando il CODICE (non il nome)
   che questo secondo bug è saltato fuori.
