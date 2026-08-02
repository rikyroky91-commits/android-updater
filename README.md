# Universal Mobile Update Tracker

Monitora i rilasci software Android reali (major release, feature drop, patch di
sicurezza) su più brand e ti dice, **per ogni modello di telefono**, quale
versione è arrivata e quando — così sai su cosa rilanciare i test.

```
streamlit run app.py          # dashboard
python worker.py --once       # una scansione sola (cron / GitHub Actions)
python worker.py              # ciclo continuo, senza UI
python -m unittest discover -s tests    # test
```

## Cosa fa

- **Ricerca unificata.** Un solo campo in cima alla pagina accetta un nome
  commerciale ("Galaxy S24 Ultra"), un codice tecnico ("RMX3939", "SM-S928B")
  o un IMEI di 15 cifre — riconosce da solo di cosa si tratta, controlla
  l'archivio *e* verifica online nello stesso click. Se il modello è già noto
  da una fonte ufficiale/strutturata, quella risposta precisa (versione,
  build, data) vince sempre su una notizia, anche quando la verifica live non
  trova nulla di nuovo in quel momento.
- **Semaforo QA per dimensione.** Quando la fonte dichiara il peso del
  pacchetto (il catalogo Xiaomi lo fa sempre), sopra 500 MB è sempre 🔴
  (retest completo), sotto è 🟡 o 🟢 a seconda che sia un aggiornamento
  funzionale o solo una patch.
- **Vista per dispositivo.** Una riga per modello: versione attuale, build
  number, data dell'ultimo aggiornamento, semaforo di freschezza (recente / in
  ritardo / fermo) e numero di update negli ultimi 30 e 90 giorni. Da lì si apre
  lo storico completo di quel modello, con foto (via Wikipedia, in cache).
- **Parco di test.** Segni i device su cui provi la tua app e ricevi una
  notifica Telegram per *ogni* aggiornamento che li riguarda, anche le patch
  minori. Gli altri device notificano solo da `NOTIFY_MIN_SEVERITY` in su
  (di default include tutto il semaforo rosso/giallo/verde: solo i canali
  beta restano silenziosi).
- **Filtro anti-rumore a punteggio.** Non più solo parole chiave: pesa insieme
  segnali strutturali (build number, patch level, versione OS) e linguistici, e
  penalizza gli annunci al futuro (*"will get"*, *"expected to"*) che erano la
  fonte principale di falsi positivi. Le ricerche generiche Google News
  (fallback per Oppo/vivo/Motorola/brand minori) scartano inoltre qualunque
  articolo senza un modello riconosciuto: non contano come aggiornamento se
  non si sa a quale device applicarlo.
- **Diagnostica.** Stato di ogni fonte, storico scansioni, ed elenco di ciò che
  il filtro ha **scartato** con il motivo: serve a tarare le soglie.

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
| `DISABLED_SOURCES` | — | chiavi separate da virgola, es. `news_minor,9to5google` |
| `EXTRA_FEEDS` | — | feed aggiuntivi: `url\|Etichetta\|Brand\|trust ;; url2\|…` |

## Architettura

```
app.py             dashboard Streamlit (unico file che importa streamlit)
worker.py          scansione headless, per cron o macchina sempre accesa
core/
  config.py        parametri, brand, severità, soglia dimensione
  extract.py       brand, modello, versione OS, build number, patch level
  classify.py      punteggio di rilevanza + severità (semaforo per dimensione)
  sources.py       fonti dati (registro estendibile) + ricerca live on-demand
  modelcodes.py    codice tecnico (RMX3939, SM-S928B...) → nome commerciale
  imeicheck.py     IMEI → marca/modello via TAC (l'IMEI non viene mai salvato)
  images.py        foto del modello via Wikipedia, con cache su DB
  storage.py       SQLite: updates, watchlist, notifiche, scansioni, stato fonti,
                   cronologia ricerche, cache immagini
  notify.py        Telegram (HTML, rate limit, digest)
  scan.py          normalizza → deduplica → salva → notifica; search_model()
                   per la ricerca on-demand (archivio prima, poi live)
tests/test_core.py
```

Il core non importa Streamlit: gli stessi moduli girano nella dashboard, nel
worker e nei test.

### Deduplica

La chiave di un item è `brand|modello|build-o-versione`. Lo stesso rollout
riportato da tre testate diverse produce **un solo** record e **una sola**
notifica. Quando il modello non è riconoscibile si ricade su `fonte|hash(titolo)`.

## Fonti

| Fonte | Affidabilità | Cosa dà |
|---|---|---|
| Pixel OTA (pagine per-release developer.android.com) | strutturata | device, Android, build ufficiali |
| MIUI/HyperOS Updates Tracker | strutturata | catalogo completo (~1300 device), versione, peso, data |
| Samsung — controllo versione FOTA | strutturata | build/Android per ~23 modelli S/A/Z più diffusi |
| Motorola — mirror lolinet.com | strutturata | build ufficiale per ~35 modelli Razr/Edge/G 2022-2025 |
| Honor — Android Enterprise Recommended | strutturata | versione di partenza + impegno futuro per modello |
| OxygenUpdater (API JSON) | curata→fallback | Oppo/OnePlus/realme; l'API storica è morta (403), ricade su ricerca news |
| SamMobile, HuaweiCentral, PiunikaWeb, GSMArena | curata | feed editoriali dedicati/multi-brand |
| 9to5Google, ricerche Google News (vivo/iQOO, Motorola, brand minori) | rumorosa | fallback per i brand senza fonte dedicata; scarta articoli senza un modello riconosciuto |
| Ricerca live (`search_model`) | on-demand | query mirata al modello esatto scritto dall'utente, non limitata al giro periodico |

Il catalogo Xiaomi e la ricerca IMEI/codice modello dipendono da `pyyaml` e
`openpyxl` — installali con `pip install -r requirements.txt` (il workflow
GitHub Actions in `.github/workflows/scan.yml` usa un elenco ridotto apposta
per il worker headless: se aggiungi dipendenze a una fonte, aggiornalo anche
lì o la scansione oraria automatica smette silenziosamente di coprire quella
fonte).

Apri la scheda **Diagnostica** dopo la prima scansione: le fonti in rosso
hanno un URL o un formato cambiato da correggere in `core/sources.py`.

## Persistenza in hosting stateless

Streamlit Community Cloud addormenta il container e azzera il disco: lo storico
per dispositivo — che è il cuore di questa app — si perde. Tre strade, in ordine
di sforzo:

1. **Worker separato** su una macchina sempre accesa (Raspberry, VPS, container),
   con `TRACKER_DB` su un volume persistente. La dashboard legge lo stesso file.
2. **GitHub Actions** ogni ora: `python worker.py --once` e commit di `tracker.db`
   nel repo. Zero infrastruttura, storico conservato, notifiche puntuali.
3. **Postgres gestito** (Supabase, Neon): sostituire `core/storage.py` è
   circoscritto, perché è l'unico modulo che parla col database.

Anche senza persistenza le notifiche continuano a funzionare, ma dopo ogni
riavvio il tracker rimanda gli avvisi già inviati: tienine conto.
