# Universal Mobile Update Tracker

Monitora i rilasci software reali (major release, feature drop, patch di
sicurezza) su più brand Android e su iOS, e dice **per ogni modello di
telefono** quale versione è arrivata e quando — così sai su cosa rilanciare
i test.

```bash
streamlit run app.py                    # dashboard
python worker.py --once                 # una scansione sola (cron / GitHub Actions)
python worker.py                        # ciclo continuo, senza UI
python -m unittest discover -s tests    # 581 test
```

## Cosa fa

- **Ricerca unificata.** Un solo campo accetta un nome commerciale
  («Galaxy S24 Ultra»), un codice tecnico («RMX3939», «SM-S928B»,
  «CPH2791») o un IMEI di 15 cifre: riconosce da solo di cosa si tratta,
  controlla l'archivio *e* verifica online nello stesso clic. Non si ferma
  alla prima fonte che risponde — sceglie il risultato **che ha davvero la
  versione**.
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
  annunci al futuro («will get», «expected to»).
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
| Honor / realme / **vivo** — pagine AER | strutturata | versione di fabbrica, finestra di supporto |
| **Android Enterprise Recommended (JSON)** | strutturata | 706 device di 40+ marche: 1404 **codici modello**, fine del supporto, cadenza patch. Unica fonte per OnePlus |
| GSMArena, SamMobile, HuaweiCentral, PiunikaWeb | curata | feed editoriali |
| Ricerche Google News | rumorosa | ripiego per i brand senza fonte dedicata |

Dettaglio completo dell'indagine sulle fonti, comprese quelle **provate e
scartate** con la risposta del server, in [`FONTI.md`](FONTI.md).
L'endpoint Oppo è documentato in
[`INTEGRAZIONE-OPPO.md`](INTEGRAZIONE-OPPO.md).

## Architettura

```
app.py             dashboard Streamlit (unico file che importa streamlit)
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
  imeicheck.py     IMEI → marca/modello via TAC (l'IMEI non viene mai salvato)
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
tests/             581 test, nessuno tocca la rete — verificato, non promesso:
                   test_niente_rete.py blocca il socket e fallisce se un
                   percorso di ricerca prova a uscire
```

Il core non importa Streamlit: gli stessi moduli girano nella dashboard,
nel worker e nei test.

### Deduplica

La chiave di un item è `brand|modello|build-o-versione`. Lo stesso rollout
riportato da tre testate produce **un solo** record e **una sola** notifica.

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

Copia `.streamlit/secrets.toml.example` in `.streamlit/secrets.toml`:

```toml
TELEGRAM_TOKEN = "123456:ABC..."
TELEGRAM_CHAT_ID = "-1001234567890"
```

Tutti i parametri sono anche variabili d'ambiente (utile per il worker):

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

## Persistenza in hosting stateless

Streamlit Community Cloud addormenta il container e azzera il disco: lo
storico per dispositivo — che è il cuore di questa app — si perde.
`core/backup.py` sincronizza il file SQLite su un Gist privato; **si
configura dalla scheda Diagnostica**, l'app crea il Gist da sé e serve solo
un token GitHub con permesso `gist`.

In alternativa: un worker su una macchina sempre accesa con `TRACKER_DB` su
volume persistente, oppure il workflow GitHub Actions in
`.github/workflows/scan.yml`, che esegue `python worker.py --once` ogni ora
e committa `tracker.db` nel repo.

> Il workflow orario installa solo `requests feedparser pyyaml openpyxl`, di
> proposito: se aggiungi una dipendenza a una fonte, aggiornalo o la
> scansione automatica smette **in silenzio** di coprire quella fonte.
