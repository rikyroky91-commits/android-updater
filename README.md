# Universal Mobile Update Tracker

Monitora i rilasci software reali (major release, feature drop, patch di
sicurezza) su più brand Android e su iOS, e dice **per ogni modello di
telefono** quale versione è arrivata e quando — così sai su cosa rilanciare
i test.

```bash
uvicorn web.main:app --reload           # il sito, su http://127.0.0.1:8000
python worker.py --once                 # una scansione sola (cron / GitHub Actions)
python worker.py                        # ciclo continuo, senza sito
python -m unittest discover -s tests    # 824 test
```

Regola di collaudo delle fonti: ogni modifica deve mantenere i casi di
regressione e aggiungere **almeno 10 modelli diversi** non presenti nella
matrice precedente. Non basta far tornare verde lo stesso telefono che ha
generato il difetto.

Il sito ha due pagine d'ingresso: `/` è **solo la barra di ricerca**, e
diventa la scheda di un modello quando le si dà qualcosa da cercare;
`/dispositivi` è l'archivio.

## Cosa fa

- **Ricerca unificata.** Un solo campo accetta un nome commerciale
  («Galaxy S24 Ultra»), un codice tecnico («RMX3939», «SM-S928B»,
  «CPH2791») o un IMEI di 15 cifre: riconosce da solo di cosa si tratta,
  controlla l'archivio *e* verifica online nello stesso clic. Non si ferma
  alla prima fonte che risponde — sceglie il risultato **che ha davvero la
  versione**.
- **Il nome e il codice portano allo stesso posto.**  Verificato con
  `strumenti-analisi-identita.py`, che confronta l'identità di 4300 modelli
  marca per marca e classifica le divergenze per causa: Samsung 100%,
  Pixel 100%, POCO 92%, Xiaomi 84%. Le marche più basse e il perché stanno
  in [`passaggio-consegne-v43.md`](passaggio-consegne-v43.md). «samsung s24» e
  «SM-S921B» danno la stessa versione, la stessa build e la stessa CPU: la
  ricerca prova le forme equivalenti in tutti e due i versi. Quando una
  fonte risponde per una variante precisa, l'app **dice quale**
  (`variante SM-S921B`) — perché due Galaxy S24 con lo stesso nome possono
  montare chip diversi.
- **L'archivio si ripara da solo, e non si perde.** Un file illeggibile
  viene messo da parte e sostituito senza riavviare l'app; una copia
  danneggiata non viene **mai** installata dall'archivio esterno né
  caricata su di esso, e un archivio vuoto non sovrascrive mai lo storico.
- **IMEI con il secondo parere sempre a portata di clic.** I database TAC
  gratuiti si contraddicono: lo stesso numero dà «Xiaomi 9A Sport» su una
  fonte e «Redmi 9A» su un'altra. L'app le mostra **tutte**, segnala quando
  non concordano, e tiene i collegamenti ai siti esterni sempre visibili —
  non solo quando la ricerca fallisce.
- **Vista per dispositivo.** Una riga per modello: versione attuale, build,
  data dell'ultimo aggiornamento, semaforo di freschezza e numero di update
  negli ultimi 30 e 90 giorni. Da lì si apre lo storico completo.
- **Parco di test.** Segni i device su cui provi la tua app e ricevi una
  notifica Telegram per *ogni* aggiornamento che li riguarda, anche le patch
  minori.
- **«Cosa è cambiato da quando l'ho testato».** Dichiari «testato adesso» e
  l'app fotografa la versione; da lì in poi dice, per ogni modello, se è
  cambiato qualcosa e **quanto profondamente** — salto di Android (retest
  completo), build diversa a parità di OS (smoke test), solo patch di
  sicurezza. È la domanda vera del QA: la versione attuale, da sola, non
  dice se vale la pena rilanciare i test.
- **Semaforo QA per dimensione.** Quando la fonte dichiara il peso del
  pacchetto, sopra 500 MB è sempre 🔴 (retest completo), sotto è 🟡 o 🟢.
- **Filtro anti-rumore a punteggio.** Pesa insieme segnali strutturali
  (build number, patch level, versione OS) e linguistici, e penalizza gli
  annunci al futuro («will get», «expected to»). Da una ricerca generica di
  notizie pretende in più una **prova di distribuzione** — un numero di
  build, un livello di patch o una frase di rollout: nominare un telefono e
  una versione dice di cosa parla l'articolo, non che sia successo qualcosa.
- **Diagnostica.** Stato di ogni fonte, andamento nel tempo, elenco di ciò
  che il filtro ha scartato e perché, e una funzione che **ripercorre passo
  per passo una ricerca** per capire perché un modello non si trova.

## Onestà del dato: tre categorie diverse

È il punto su cui l'applicazione è più severa con sé stessa, perché
confonderle è il modo più efficace di renderla inutile:

| | significato | esempio |
|---|---|---|
| **versione attuale** | quella installata oggi dopo gli aggiornamenti | Samsung FOTA, Apple, Pixel, Xiaomi, Motorola, archivio Oppo |
| **versione di fabbrica** | quella con cui il telefono è uscito | pagine AER (Honor, realme, vivo), GSMArena |
| **indizio da notizia** | un articolo che parla di un rilascio | feed editoriali, ricerche Google News |

Una versione di fabbrica non viene **mai** presentata come attuale, e una
fonte che conferma soltanto l'esistenza di un modello lo dichiara invece di
far credere di avere una risposta.

## Fonti

| Fonte | Tipo | Cosa dà |
|---|---|---|
| Samsung — controllo versione FOTA | strutturata | build e Android **attuali** |
| Apple — `api.ipsw.me` | strutturata | versione **attuale** per dispositivo |
| Google Pixel — pagine OTA | strutturata | build **attuali** |
| MIUI/HyperOS Updates Tracker | strutturata | ~1300 device, versione, peso, data |
| Motorola — mirror lolinet.com | strutturata | build ufficiali |
| **Oppo — archivio firmware ufficiale** | strutturata | versione **rilasciata**, data e changelog per ~94 modelli fino al 2021-22 |
| **OPPO ColorOS 16 — piano ufficiale** | strutturata | 42 modelli con Android 16 previsto; non è una conferma della build installata |
| OnePlus / OPPO — tracker ARB | curata | build osservata per regione, codice variante e Android 14/15/16; non ufficiale |
| Honor / realme / **vivo** — pagine AER | strutturata | versione di fabbrica, finestra di supporto |
| realme — archivio tecnico per codice RMX | curata | build osservata per regione (GDPR europea prima dell'Export), chiaramente non OTA ufficiale |
| **Android Enterprise Recommended (JSON)** | strutturata | 706 device di 40+ marche: 1404 **codici modello**, fine del supporto, cadenza patch. Unica fonte per OnePlus |
| Catalogo specifiche GSMArena (mirror JSON) | strutturata | scheda hardware di 4766 modelli, indicizzata per **codice** — dieci marche |
| **versus.com** | strutturata | scheda hardware di HONOR, realme, Huawei e Nothing, le quattro marche che il mirror GSMArena non copre |
| GSMArena, SamMobile, HuaweiCentral, PiunikaWeb | curata | feed editoriali |
| Ricerche Google News | rumorosa | ripiego per i brand senza fonte dedicata |

Dettaglio completo dell'indagine sulle fonti, comprese quelle **provate e
scartate** con la risposta del server, in [`FONTI.md`](FONTI.md).
L'endpoint Oppo è documentato in
[`INTEGRAZIONE-OPPO.md`](INTEGRAZIONE-OPPO.md).

## Architettura

```
web/               il sito: FastAPI, template Jinja, CSS nostro
  main.py            le rotte — nessuna formattazione dentro
  presenters.py      dati → testo leggibile — nessuna rete, si collauda da solo
  cache.py           la memoria corta delle ricerche (vedi sotto)
  templates/         HTML — nessuna decisione dentro
worker.py          scansione headless, per cron o macchina sempre accesa
core/
  config.py        parametri, brand, severità, DATA_LOGIC_VERSION
  util.py          date, formattazione, slug — zero dipendenze esterne
  extract.py       brand, modello, versione OS, build number, patch level
  classify.py      punteggio di rilevanza + severità (semaforo QA)
  sources.py       tutte le fonti + ricerca live + diagnosi di una query
  aer_catalog.py   catalogo Android Enterprise Recommended (JSON)
  oppo_official.py archivio firmware ufficiale Oppo
  modelcodes.py    codice tecnico → nome commerciale
  appledevices.py  identificatore Apple → nome commerciale
  imeicheck.py     IMEI → marca/modello via TAC, da tre basi dati che si
                   contraddicono e che vengono mostrate tutte
                   (l'IMEI non viene mai salvato)
  images.py        foto del modello via Wikipedia, con cache
  storage.py       SQLite: schema, query, aggregazione per dispositivo
  scan.py          normalizza → deduplica → salva → notifica; search_model()
  notify.py        Telegram
  suggest.py       completamento e correzione degli errori di battitura
  retest.py        confronto fra la baseline testata e lo stato attuale
  oplus_arb.py     tracker ARB OnePlus/OPPO: build correnti per regione
  soc.py           quale chip monta un modello (per codice, non per nome)
  skinmap.py       One UI/ColorOS/MIUI -> versione Android, con le eccezioni
  telegram_tracker.py  lettura del canale rollout OxygenOS/ColorOS
                   (parser puro, zero rete: scarica sources.py)
  backup.py        persistenza del database fra i riavvii (Gist/URL)
tests/             721 test, nessuno tocca la rete — verificato, non promesso:
                   test_niente_rete.py blocca il socket e fallisce se un
                   percorso di ricerca prova a uscire
```

Il core non sa che il sito esiste: gli stessi moduli girano nel sito, nel
worker e nei test. La dashboard Streamlit (`app.py`) è stata tolta il
2026-08-10, quando il sito è andato in produzione.

### Le ricerche si ricordano per un quarto d'ora

Una ricerca costa fino a tredici secondi di rete, misurati sul sito vero,
e due ricerche identiche ne costavano ventisei: fra l'una e l'altra non
c'era nessuna memoria. Le fonti pubblicano un firmware al massimo una
volta al giorno e la scansione gira una volta all'ora, quindi tenere una
risposta per quindici minuti non nasconde niente che sia cambiato. Si
spegne con `SEARCH_CACHE_SECONDS=0`.

### Deduplica e identità del dispositivo

La chiave di un item è `brand|modello|build-o-versione`. Lo stesso rollout
riportato da tre testate produce **un solo** record e **una sola** notifica.

Il nome del modello entra nella chiave in forma canonica: le parole che
ripetono una marca già implicita non contano. «Galaxy S24 Ultra», «Samsung
S24 Ultra» e «S24 Ultra» sono lo stesso telefono — le fonti ufficiali usano
la prima grafia, chi cerca digita la seconda. Vale solo dove la parola non
può distinguere nulla (Samsung, Apple, Google): sotto «Oppo / Realme /
OnePlus» le sottomarche distinguono eccome, e fonderle mostrerebbe la
versione di un telefono sotto il nome di un altro.

Cambiare quella forma invalida le chiavi già scritte — parco di test e
baseline compresi, che la ricostruzione non tocca. Per questo esiste
`storage.migra_chiavi_dispositivo()`, che gira all'avvio, una volta sola, e
fonde i doppioni tenendo l'iscrizione più vecchia e la baseline più recente.

### Baseline di test e versioni che retrocedono

La fotografia sta in `test_baseline` e **non** viene toccata da
`rebuild_if_logic_changed`: è un dato inserito da una persona, non il
risultato dell'interpretazione di una fonte, e ricostruirlo è impossibile.

Due regole valgono la pena di essere dette:

- **Un campo che sparisce non è un aggiornamento.** Se la fotografia aveva
  una build e oggi il campo è vuoto, è una fonte che non risponde più.
  Trattarlo come cambiamento avrebbe prodotto «da ritestare» su tutto il
  parco a ogni giornata storta di una fonte.
- **Un telefono non torna indietro.** Se lo stato attuale dichiara una
  versione *inferiore* alla fotografia, il dato è sbagliato: viene
  etichettato «dato incoerente» e **mostrato**, non corretto in silenzio.
  Nascondere un disaccordo fra fonti è il modo più efficace di far sembrare
  affidabile un archivio che non lo è.

### `DATA_LOGIC_VERSION`

In `core/config.py`, con lo storico completo delle correzioni. Va
incrementata ogni volta che cambia il modo in cui una fonte viene
interpretata: all'avvio l'app azzera e ricostruisce gli aggiornamenti
raccolti, altrimenti una correzione resta invisibile perché i dati sbagliati
restano in archivio. Parco di test e cronologia non vengono toccati.

## Configurazione

Tutto si configura con variabili d'ambiente — sul pannello di Render, o
nella shell in locale. `configurazione.esempio.toml` le elenca con il
loro significato.

> Il file di esempio **non** sta più in `.streamlit/`: l'upload dal
> browser di GitHub salta le cartelle che iniziano con un punto, ed è il
> motivo per cui `.streamlit/config.toml` non è mai arrivato nel
> repository e la dashboard aveva smesso di partire senza che si vedesse.

| Variabile | Default | Effetto |
|---|---|---|
| `TRACKER_DB` | `tracker.db` | percorso del database SQLite |
| `SCAN_INTERVAL_MINUTES` | `60` | intervallo fra due scansioni |
| `RELEVANCE_THRESHOLD` | `3` | soglia del filtro (più alto = più severo) |
| `NOTIFY_MIN_SEVERITY` | `SECURITY` | `MAJOR`, `FEATURE`, `SECURITY` o `BETA` |
| `NOTIFY_ONLY_WATCHLIST` | `false` | notifica solo il parco di test |
| `RETENTION_DAYS` | `400` | dopo quanto si cancella lo storico |
| `DISABLED_SOURCES` | — | chiavi separate da virgola |
| `EXTRA_FEEDS` | — | feed aggiuntivi: `url\|Etichetta\|Brand\|trust ;; …` |
| `BACKUP_GIST_ID`, `BACKUP_GITHUB_TOKEN` | — | persistenza su Gist privato |
| `GEMINI_API_KEY` | — | accende il tasto ✨ accanto a «Cerca» (quota gratuita) |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | — | alternative a consumo, se manca la prima |
| `AI_QUERY_MODEL` | scelto fra quelli gratuiti | forza un modello preciso |

## Persistenza in hosting stateless

Il piano gratuito di Render addormenta il servizio dopo quindici minuti
senza visite e azzera il disco a ogni riavvio: lo
storico per dispositivo — che è il cuore di questa app — si perde.
`core/backup.py` sincronizza il file SQLite su un Gist privato; **si
configura dalla scheda Diagnostica**, l'app crea il Gist da sé e serve solo
un token GitHub con permesso `gist`.

> I dataset scaricati (codici modello, database TAC, chip) vivono dentro lo
> stesso file, quindi il suo peso non è un dettaglio: vengono conservati
> **compressi** con `storage.set_blob()`. In esadecimale — la forma usata
> fino alla v39 — occupavano 63 MB invece di 16, in un file che viene
> caricato ogni mezz'ora e committato ogni ora.

In alternativa: un worker su una macchina sempre accesa con `TRACKER_DB` su
volume persistente, oppure il workflow GitHub Actions in
`.github/workflows/scan.yml`, che esegue `python worker.py --once` ogni ora
e committa `tracker.db` nel repo.

> Il workflow orario installa solo `requests feedparser pyyaml openpyxl`, di
> proposito: se aggiungi una dipendenza a una fonte, aggiornalo o la
> scansione automatica smette **in silenzio** di coprire quella fonte.
