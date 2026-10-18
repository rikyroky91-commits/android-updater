# Passaggio di consegne: Mobile Update Tracker e Page Brawl

Documento vivo. Ultimo aggiornamento: **18/10/2026 notte**, sul ramo `claude/parry-brawl-web` (prima corsa guidata e schede dei nemici nuovi, bestia armata rifatta, scelta del personaggio rifatta; prima ancora agguato del fucile-sega, livelli più lenti, terreno deciso dall'ospite; il sito del gioco, **Parry Brawl Survivor**, è a parte). `main` è al 18/10 (`e591acd`).

Questo file è il punto di ingresso per chiunque lavori sul repository: persone, Claude, Codex o altri agenti. Si tiene **sempre aggiornato** (regola in fondo, sezione 9). I passaggi di consegne dei singoli giri restano in `docs/consegne/` come archivio storico: questo li riassume e li sostituisce come riferimento.

Nel repository convivono **due progetti** che condividono codice, server e deploy:

| | Mobile Update Tracker (M.U.T.) | Page Brawl |
| --- | --- | --- |
| Cos'è | Sito che dice, per ogni modello di telefono, quale firmware è uscito e quando, e da un IMEI ricava il modello | Gioco: due lottatori ragdoll che si picchiano usando gli elementi della pagina (o dello schermo) come terreno |
| Dove vive | `core/`, `web/`, `worker.py`, `data/`, `scripts/` | `web/static/ring.js` (motore), `estensione/`, `android/` |
| Uscite | Sito su `https://mobileupdatetracker.duckdns.org` | Ring nella home del sito, estensione Chrome, app Android |
| Stato | In produzione | Estensione 1.1.0 pubblicata sul Chrome Web Store; app Android 1.5.1 su `main` |

Page Brawl è nato il 30/09/2026 come animazione della home del sito ed è cresciuto fino a diventare un prodotto a sé. Per questo il motore sta ancora sotto `web/static/` e la classifica globale passa dal server del tracker.

Proprietario e unico decisore: **Riccardo** (account GitHub `rikyroky91-commits`). Le citazioni fra virgolette in questo documento sono sue decisioni.

---

## 1. Stato attuale (16/10/2026)

### Versioni

| Componente | Versione | Dove si legge | Note |
| --- | --- | --- | --- |
| Sito M.U.T. | commit su `main` | `/health` → `versione.commit` | deploy automatico su Oracle a ogni push su `main` |
| `DATA_LOGIC_VERSION` | 34 | `core/config.py` | si alza quando cambia l'interpretazione di una fonte |
| Estensione Page Brawl | 1.2.0 su `main` (unita il 17/10); 1.1.0 nello store | `estensione/costruisci.py` → `VERSIONE` | `premium_attivo: false`: tutto gratis. La 1.1.0 è pubblicata sul Chrome Web Store (aggiornata il 14/10); **la 1.2.0 va caricata a mano** (`python3 estensione/costruisci.py --zip`) |
| Estensione Page Snow | 0.2.0 | `estensione/costruisci.py` → `NATALE_VERSIONE` | tema di Natale, non pubblicata |
| App Android | 1.6.0, versionCode 11 (lite: 12) su `main` (unita il 17/10) | `android/costruisci.py` → `VERSIONE`, `CODICE_VERSIONE` | AAB e APK nelle pre-release `android-<commit>`; mai provata da Claude su un telefono vero |

### Rami con lavoro non unito a `main`

Il flusso del repository è **push diretto su `main`** (nessuna PR è mai stata unita; le 11 PR esistenti sono tutte chiuse). Rami da guardare:

| Ramo | Cosa contiene | Da fare |
| --- | --- | --- |
| `claude/parry-brawl-web` (18/10) | Musica a tempo (attacchi sul battito, «tic» d'avviso, risposta al parry, taratura del ritardo), API per i comandi touch (`tempoParry`, `premi`, `lascia`, `musica`, `calibra`), nome, motto e logo del menu decisi dall'ospite (`__ringNome`, `__ringMotto`); poi stamina della guardia tenuta, arena «cortile» con pedane che si rompono (`__ringUrto`, `__ring.rileva`), secondo modo rinominabile dall'ospite (`__ringModoLibero`, `__ringModoScelto`). Serve al sito nuovo `rikyroky91-commits/parry-brawl-survivor` | Da unire a `main` con l'accordo di Riccardo: estensione e app prendono la musica (di serie solo nella corsa) |
| `claude/exciting-cori-6cwl9m` (16-17/10) | Page Brawl 1.2.0 / Android 1.6.0, unito a `main` il 17/10 (`f8d3910`); dopo, **il parry, seconda volta** (parry perfetto, equilibrio e colpo di grazia, catena, attacchi rossi, tre manate del capo, guardia che si consuma) | **Unito a `main` il 17/10**, anche il parry nuovo (avanti veloce, su richiesta di Riccardo: «unisci»). Cancellabile |
| `claude/ultimora-tema-scuro-codice-modello` (02/10) | Commit `61f8ca9` «lotte più fitte, meno tempi morti», mai arrivato su `main` | **Rifatto a mano il 16/10** sul ramo qui sopra (con lo strumento `tests/misura-lotta.cjs` che stava lì). Cancellabile (quello nuovo è su `main` dal 17/10) |

### Pulizia dei rami (verificata il 16/10/2026)

Controllo fatto su ogni ramo remoto con `git rev-list origin/main..<ramo>`, poi con `git cherry` e confrontando il codice per i commit rimasti fuori.

**Cancellabili, perché ogni commit è già in `main` (26):** `agent/firmware-source-semantics`, `agent/fix-backup-diagnostics`, `agent/fix-complete-search-output`, `agent/imei-resilience-ai-preload`, `agent/rank-imei-candidates`, `claude/audio`, `claude/corsa-crescente`, `claude/corsa-infinita`, `claude/corsa-verticale`, `claude/estensione-1.1.0`, `claude/estensione-gratis-1.0`, `claude/estensione-modi-gioco`, `claude/imei-samsung-not-found-8z4c9d`, `claude/ring-controller-orda-tasto-scontro`, `claude/ring-senza-gambe-scontri-eventi`, `claude/test-rimonta-ballerino`, `claude/trasformazioni-scimmia-colosso-albero`, `codex/android-data-rilascio`, `codex/firmware-marche-prioritarie`, `codex/fix-g30-identity`, `codex/installed-software-tests`, `codex/memoria-diagnostica-v76`, `codex/oom-background-memory`, `codex/ui-compact-firmware`, `codex/ui-device-first`, `estensione-modi-gioco`.

**Cancellabili, perché il contenuto è in `main` sotto altri commit (4):**
- `claude/secondo-tempo-pagina-intera`: `git cherry` dà i due commit come già applicati.
- `agent/fix-imei-specs-performance`: è solo il merge di due rami che stanno già tutti e due in `main`.
- `agent/fix-imei-note-50-results`: l'ordinamento dei TAC per affidabilità (`_punteggio_affidabilita`, `_ordina_per_affidabilita`) è in `core/imeicheck.py`.
- `claude/corsa-difficile`: la corsa più difficile del 09/10 è in `main`, poi ritoccata ancora (`ultima: 0.3`, `ricarica`, `salvezze`, cuore +15).

**Unite a `main` il 16/10, ora cancellabili anche loro:** `claude/android-ring` (1.5.1) e `claude/loving-cannon-1t7wdu` (ricerca per codice). La CI rossa di quest'ultimo veniva da due test casuali del ring (`ring.test.cjs` n. 59 «imprevisti a mano» e n. 96 «oggetti dai lati»), non dalla correzione: i test Python erano verdi.

**Da tenere:** nessuno. Dal 17/10 anche `claude/exciting-cori-6cwl9m` e `claude/ultimora-tema-scuro-codice-modello` sono su `main` e si possono cancellare.

### Stato dei test (verificato il 16/10/2026)

- **CI su `main` (`df97c09`)**: `tests.yml` verde (run 144, Python 3.12).
- **In locale, in un container Linux con Python 3.13**: il 16/10 sera, a suite intera, i falliti erano 18-27 e sempre gli stessi con e senza le modifiche del giro (provato togliendole con `git stash`): oltre ai 9 di realme qui sotto cadono test di ricerca a tempo (`test_core.py` «tetto di tempo», `test_nome_e_codice.py`, `test_specs.py`, regressioni A325F e codice) quando la macchina è carica. In CI passano tutti. Al 15/10: 1858 passati, 9 falliti, tutti dello stesso caso: `TestRealmeNomiRegionali::test_differenza_di_nome_dichiarata_non_nascosta` e 8 sottocasi di `TestMatriceRicerca` su realme C61/C63/RMX3939 («realme C61» atteso, arriva solo «realme C63»). In CI passano: la differenza è d'ambiente (versione di Python o ordine dei dati), non ancora capita. Prima di toccare la ricerca realme, riprodurlo con Python 3.12.
- **Test del ring resi meno casuali (16/10, ramo del giro)**: con le lotte più fitte la CI di `1f3f3a5` è caduta due volte di fila su tre test che però non avevano un errore nel gioco: n. 65 «gravità sottosopra» e n. 101 «senza gambe» (chi riparte col jetpack, fino a nove secondi, non è «tornato giù» né «in piedi»), e una gamba persa nella lotta prima di `stacca` che tornava da sola dopo sette secondi («CLICK!»); e la carica letale (scritte «SBAM!» di altri colpi, eroe invulnerabile appena colpito, carica andata a vuoto). Corretti i test, non il gioco; ognuno rilanciato da solo 42-84 volte senza cadute. Col bruto armato (stesso giorno) i test Node sono 201; in locale, a suite intera, sono caduti a caso anche il n. 34 «notizie danneggiate» e il n. 91 «davanti agli elementi», che da soli passano 12 volte su 12.
- **Test Node del ring**: alcuni test sono statistici (lotte vere, con il caso) e cadono di rado. L'arena di lava e il n. 96 «oggetti dai lati», i più fragili, sono stati resi robusti il 17/10 (vedi registro). Resta da tenere d'occhio il n. 59 «imprevisti a mano» (l'uragano che non solleva nessuno, o «fuori dalla finestra»), caduto due volte di fila in CI il 15 e il 16/10 su commit che non toccavano il gioco. Anche «parry a vista» (n. 191 circa) cade 1-2 volte su 4 da solo, uguale col motore del 18/10 sera prima della guida. Prima di dare la colpa a una modifica, rilanciare quel test da solo qualche volta e confrontarlo col motore di `main` (`RING_JS` in `misura-lotta`, o `git stash` e lo stesso test).

### Cose in sospeso che dipendono da Riccardo

- **Chrome Web Store**: Page Brawl è **pubblicata** in versione 1.1.0, aggiornata il 14/10/2026 (controllato il 16/10 sulla pagina pubblica: <https://chromewebstore.google.com/detail/page-brawl/fhpgfhllcdfbhalcmfbdlolpgbgpnloi>, ID `fhpgfhllcdfbhalcmfbdlolpgbgpnloi`). Google l'ha approvata senza avvisare, cosa normale per lo store: l'esito si legge nella console sviluppatore o sulla pagina pubblica, non sempre arriva un'email. **Page Snow non risulta pubblicata.**
- **Google Play**: AAB non firmati pronti nelle pre-release GitHub `android-<commit>`. Firma, console e invio a mano. Stato da confermare.
- **Email di contatto** nell'informativa privacy (`web/static/pagebrawl/privacy.html`, riga «[email di contatto dello sviluppatore]»): manca, serve per entrambi gli store.
- **Donazioni di Page Brawl (Ko-fi, solo estensione)**: il codice c'è (sul ramo del giro), manca l'account. Da fare: aprire la pagina Ko-fi; mettere il suo indirizzo (`https://ko-fi.com/<nome>`) in `estensione/premium.json` → `url_donazione` e rigenerare; su Ko-fi → More → API → Webhooks mettere `https://mobileupdatetracker.duckdns.org/api/kofi` e copiare il Verification Token in `KOFI_VERIFICATION_TOKEN` su Oracle (`imposta-chiavi.ps1`); provare col tasto «Send Test» di Ko-fi e guardare `/admin/donazioni`. Finché `url_donazione` è vuoto il tasto nell'estensione non c'è; finché il token manca il sito rifiuta i webhook.
- **Chiave IMEI Check Pro** approvata (secondo fornitore TAC): richiesta da fare, poi `TAC_API_PROVIDER_2` e `TAC_API_KEY_2` su Oracle.

---

## 2. Regole che valgono per tutto il repository

Queste regole sono nate da errori veri. Violarne una ha già rotto qualcosa almeno una volta.

1. **Mai committare `tracker.db`** né altri `.db`: contiene account, email, hash delle password e il parco di test. Il vecchio workflow `scan.yml` che lo committava ogni ora è stato tolto apposta.
2. **I test non toccano la rete.** `tests/conftest.py` stacca il socket per tutta la suite. Se un test passa solo con `TEST_CON_RETE=1`, il test è sbagliato. Le fixture vengono da dati veri registrati (`scripts/registra_fixture_cataloghi.py`), mai inventati.
3. **Regola delle fonti**: ogni modifica a una fonte firmware mantiene i casi di regressione e aggiunge **almeno 10 modelli diversi** non presenti prima. Non basta far tornare verde il telefono che ha generato il difetto.
4. **Onestà del dato**: versione attuale, versione di fabbrica e indizio da notizia sono tre cose diverse e non si confondono mai. Un disaccordo fra fonti si mostra, non si corregge in silenzio. Un telefono non torna indietro di versione: se succede, è «dato incoerente».
5. **`DATA_LOGIC_VERSION`** si alza quando cambia il modo di leggere una fonte, altrimenti i dati sbagliati restano in archivio. Parco e baseline non vengono toccati dalla ricostruzione.
6. **Una sola sorgente per il ring**: si modifica solo `web/static/ring.js` (e `lingue.js`, `natale.js`). Le cartelle `estensione/pacchetto/`, `estensione/store/`, `estensione/natale/` e gli asset Android sono **generati**. `tests/test_estensione.py` fallisce se sono rimaste indietro.
7. **Segreti solo nei pannelli** (Oracle `~/sito.env`, Render Environment, GitHub Secrets). Mai nel codice, nei log o nei commit. La chiave di caricamento Android (`android/firma/pagebrawl-upload.*`) è in `.gitignore`.
8. **Personaggi inventati**: nomi, facce e vestiti di Page Brawl non devono richiamare personaggi di altri (Dragon Ball in particolare). Vale per codice, schermate e schede degli store.
9. **Lingua**: codice, commenti, commit e documenti in italiano, come il resto del repository. Il gioco parte in inglese di serie.
10. **Prima di dire «funziona»**: suite verde, e per il sito il commit giusto su `/health` dopo il deploy.

---

## 3. Mobile Update Tracker

### 3.1 Cosa fa

Un campo solo accetta nome commerciale («Galaxy S24 Ultra»), codice tecnico («SM-S928B», «RMX3939», «CPH2791») o IMEI di 15 cifre. Risponde in due tempi: prima identità e scheda del modello, poi il firmware (fino a 13 s di rete, con cache di 15 minuti). In più: archivio per dispositivo, parco di test con notifiche Telegram, baseline «cosa è cambiato da quando l'ho testato», confronto fra il software installato e l'ultimo uscito, novità tradotte con Gemini, diagnostica delle fonti, area amministratore per account e TAC da verificare.

Dettaglio completo delle funzioni in `README.md`, delle fonti (comprese quelle scartate e perché) in `FONTI.md`.

### 3.2 Architettura

```
web/main.py          rotte FastAPI (4.400 righe): nessuna formattazione dentro
web/presenters.py    dati → testo, senza rete
web/templates/       Jinja, nessuna decisione dentro
web/static/          JS e CSS del sito, compreso ring.js (Page Brawl)
core/sources.py      tutte le fonti firmware + ricerca live (6.500 righe)
core/imeicheck.py    IMEI → modello via TAC, da più basi dati mostrate tutte
core/tac_index.py    indice TAC su SQLite separato: <DB_PATH>.tac.sqlite3
core/storage.py      schema SQLite e query
core/scan.py         normalizza → deduplica → salva → notifica
core/backup.py       copia cifrata del DB su Gist
core/config.py       parametri, DATA_LOGIC_VERSION con lo storico
worker.py            scansione senza sito (cron o ciclo)
app.py               vecchia dashboard Streamlit, tenuta in parallelo su richiesta
data/                cataloghi versionati: TAC, codici, SoC, schede curate
scripts/             manutenzione, controllo notturno, benchmark
```

Il `core/` non sa che il sito esiste: gli stessi moduli girano nel sito, nel worker e nei test.

### 3.3 Lavorare in locale

```bash
pip install -r requirements-web.txt      # NON requirements.txt: quello è di app.py (Streamlit)
uvicorn web.main:app --reload            # http://127.0.0.1:8000
python worker.py --once                  # una scansione
AVVIA_WORKER=0 python -m pytest tests/ -q
PROVA_BROWSER=1 python -m pytest tests/test_browser.py   # serve Playwright + Chromium
node --test tests/ring.test.cjs tests/lingue.test.cjs tests/halloween.test.cjs tests/confronto-installato.test.cjs
```

Due file di dipendenze, e scambiarli è un errore già fatto: `requirements-web.txt` per sito, worker e Dockerfile; `requirements.txt` per Streamlit Cloud.

### 3.4 Dove gira e come si pubblica

| Ambiente | Ruolo | Come si aggiorna |
| --- | --- | --- |
| **Oracle Cloud Always Free** (VM Ubuntu, 12 GB) | **Sito principale** dal 26/09/2026. Docker Compose: `web` + Caddy (HTTPS automatico). DB persistente nel volume `archivio` | Automatico: `.github/workflows/deploy-oracle.yml` a ogni push su `main` (esclusi `*.md` e `tracker.db`). Copia via tar+SSH, ricostruisce, poi verifica che `/health` risponda **col commit appena pubblicato** |
| Render (piano gratuito, 512 MB) | Istanza in parallelo, legge lo stesso Gist in sola lettura | `render.yaml`, `autoDeployTrigger: checksPass`. Render aveva sospeso il servizio per i 5 GB di banda esauriti |
| Streamlit Cloud | `app.py`, la dashboard storica | Legge `requirements.txt` |

Configurazione Oracle: `deploy/oracle/setup.sh` (una volta sulla VM), `deploy/oracle/imposta-chiavi.ps1` (inserisce le chiavi in `~/sito.env` da Windows). Segreti GitHub necessari: `ORACLE_HOST`, `ORACLE_USER`, `ORACLE_SSH_KEY`. Variabile di repository `SITE_URL`.

Altri workflow:
- `tests.yml`: suite Python + test nel browser + test Node, su `main`, `codex/**`, `claude/**` e PR. I test Node del ring, che contengono caso, si riprovano una volta: due cadute di fila sono un errore vero.
- `controllo-notturno.yml`: alle 03:40 UTC una trentina di ricerche note contro il sito vero (`scripts/controllo_notturno.py`). Se una si rompe, arriva l'email di GitHub.
- `sveglia.yml`: chiama `/health` ogni 10 minuti. Serviva per Render che dorme; GitHub strozza le pianificazioni, quindi non è affidabile.
- `android-play.yml`: vedi Page Brawl.

### 3.5 Variabili d'ambiente

Elenco e significato in `configurazione.esempio.toml`, `render.yaml` e `deploy/oracle/imposta-chiavi.ps1`. Le più importanti:

| Variabile | A cosa serve |
| --- | --- |
| `DB_PATH` | archivio SQLite (Oracle: `/home/app/archivio/tracker.db`; Render: `/tmp`) |
| `BACKUP_GIST_ID`, `BACKUP_GITHUB_TOKEN`, `BACKUP_ENCRYPTION_KEY` | backup cifrato. **La chiave deve essere la stessa su tutti gli host**, o i backup non si leggono |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL` | l'amministratore nasce da qui all'avvio, se il backup non ne porta uno (`guida-account-amministratore.md`) |
| `SESSION_SECRET` | firma dei cookie; la genera `setup.sh` |
| `TAC_API_KEY`, `TAC_API_KEY_2`, `TAC_API_PROVIDER_2`, `TAC_API_KEY_3` | fornitori TAC esterni, provati in ordine (`guida-servizi-tac.md`) |
| `GEMINI_API_KEY` | interprete AI della ricerca e traduzione delle novità |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | notifiche del parco |
| `BREVO_API_KEY`, `SMTP_*` | email (recupero password, richieste di accesso) |
| `MEMORIA_SOGLIA_MB` | sopra questa soglia il processo si alleggerisce (Render 380, Oracle 3000) |
| `PRERISCALDA_*` | caricamento anticipato di cataloghi e fonti: spento su Render, acceso su Oracle |
| `KOFI_VERIFICATION_TOKEN` | le donazioni di Page Brawl (dal 16/10/2026): il token dei webhook di Ko-fi. Vuoto, `/api/kofi` risponde 503 e non salva niente |

### 3.6 Checklist di rilascio del sito

1. Suite Python e Node verdi in locale; `tests.yml` verde sul commit.
2. Se è cambiata l'interpretazione di una fonte: `DATA_LOGIC_VERSION` + 1, con la riga nello storico di `core/config.py`.
3. Push su `main` → `deploy-oracle` → controllare che il job finisca col commit giusto.
4. A mano: una ricerca per nome, una per codice, una per IMEI; `/diagnostica` da amministratore; `/admin/tac`.
5. Il mattino dopo: esito del controllo notturno.
6. Rollback: ridistribuire il commit precedente (`workflow_dispatch` su quel commit, o revert + push). L'indice TAC è una cache separata e si ricostruisce.

### 3.7 Storia in breve

| Periodo | Cosa è successo |
| --- | --- |
| fino all'11/08/2026 | Dashboard Streamlit (`app.py`). Consegne caricate su GitHub **via zip dal browser** («Add files via upload»): così si sono perse più volte `.github/` e le cartelle col punto |
| 10-11/08 | Nasce il sito FastAPI (v47-v48); Streamlit tolto e poi rimesso in parallelo su richiesta |
| 12-18/08 | v53-v64: identità nome/codice coerente, correzioni manuali dei nomi, backup su Gist cifrato, login e account per il parco di test, note e allegati, ricerca in due tempi, test senza rete |
| 31/08-09/09 | v66-v76: memoria su Render (OOM a 512 MB), IMEI e TAC (Motorola che il database scrive col codename, tre fornitori TAC, HiCellTek bloccato da un antibot), indice TAC su SQLite, registro `/admin/tac`, metadati di rilascio in `/health` |
| 09-11/09 | Fonti firmware prioritarie (OPPO, realme, Honor, Redmi), software installato e test, riduzione dei picchi di memoria |
| 26/09 | **Trasloco su Oracle Cloud** (Render sospeso per banda). Controllo notturno, nome M.U.T., novità rifatte, Nothing/CMF |
| 01-02/10 | Home con ultim'ora, tema scuro, codice modello sempre visibile. Nasce il ring (Page Brawl) |
| 09-10/10 | Tema di Halloween; `POST /scansione` dietro login con pausa di 10 minuti; correzioni anonime in coda di verifica |
| 15/10 | Correzione della ricerca per codice (`SM-A575G` che diventava Galaxy A05s), unita il 16/10 |

Il dettaglio di ogni giro è in `docs/consegne/passaggio-consegne-v<NN>.md`.

### 3.8 Problemi noti

- **Fornitore TAC HiCellTek**: risponde con la pagina «Security check» di un antibot (o2switch). Non è dimostrato che la chiave sia valida né che l'API sia raggiungibile dal server. IMEI Check Pro è configurato nel codice ma mai collaudato con una chiave vera.
- **TAC ambigui**: i database gratuiti si contraddicono e per Motorola scrivono codename (`FOGO5G23`). La traduzione è solo per corrispondenza esatta; i casi ambigui si risolvono con righe curate in `data/tac_modelli.csv`.
- **Test legati a Linux**: alcune prove di memoria leggono `/proc` e falliscono su Windows; non è un difetto del codice.
- **Render**: piano gratuito, 512 MB, dorme dopo 15 minuti, banda limitata. Va considerato un ripiego.
- **`sveglia.yml`** non garantisce nulla: GitHub salta le pianificazioni anche di ore.
- **Link rotto** nel README a `docs/consegne/passaggio-consegne-v43.md`, che non esiste più.
- Traduzioni ES/FR/DE del sito non riviste da madrelingua.

### 3.9 Miglioramenti possibili

In ordine di guadagno stimato:
1. Aggiungere alla ricerca per codice (unita il 16/10) un collaudo su 10 codici veri che i cataloghi non conoscono ma i TAC sì.
2. Ottenere e collaudare dal server la chiave IMEI Check Pro (`python scripts/verifica_servizi_tac.py --live`), poi decidere se tenere HiCellTek.
3. Monitor esterno vero (UptimeRobot o simile) al posto di `sveglia.yml`, che controlli anche il commit.
4. Spezzare `web/main.py` e `core/sources.py`: oltre 4.000 e 6.000 righe rendono lento ogni giro e alto il rischio di conflitti fra agenti in parallelo.
5. Spostare Page Brawl fuori da `web/static/` in una cartella sua (vedi 4.10).
6. Decidere se `app.py` (Streamlit) serve ancora: è una seconda base di codice che nessuno collauda.
7. Pulire i rami vecchi su GitHub.

---

## 4. Page Brawl

### 4.1 Un motore, quattro uscite

```
web/static/ring.js  (+ lingue.js)            ← l'unico posto dove si modifica il gioco
   │
   ├── sito: home di M.U.T., ring sulla pagina vera, classifica via /api/corsa
   │
   └── python3 estensione/costruisci.py      ← rigenera, con ritocchi automatici
          ├── estensione/pacchetto/  (prova a mano)
          ├── estensione/store/      (da pubblicare sul Chrome Web Store)
          └── estensione/natale/     (Page Snow, da web/static/natale.js)
                 │
                 └── python3 android/costruisci.py   ← prende estensione/store/
                        └── app Android (asset + android/web/ + Java)
```

**Ordine obbligatorio dopo una modifica al ring:** `python3 estensione/costruisci.py`, poi `python3 android/costruisci.py`. I ritocchi automatici di `costruisci.py` si fermano con un errore se il punto originale cambia: è voluto, va aggiornato il ritocco, non aggirato.

`ring.js` è un unico file di circa 14.500 righe. Ogni lottatore è una ragdoll Verlet di undici punti con «muscoli» che tirano verso la posa; gli elementi della pagina sono corpi solidi. Il commento in testa al file spiega il modello.

### 4.2 Contratto fra motore e ospite

Il motore legge dall'ambiente degli hook opzionali. Sul sito nessuno è impostato; estensione e app li definiscono.

| Hook | Chi lo imposta | A cosa serve |
| --- | --- | --- |
| `window.__ringRadice` | estensione, app | shadow DOM dove vivono canvas e tendina |
| `window.__ringDeposito` | estensione, app | memoria al posto di `localStorage` (`chrome.storage.local`, o Java) |
| `window.__ringPremium` | estensione, app | gruppi bloccati (`guerrieri`, `armi`, `meteo`), `attivo()`, `chiedi(gruppo)` |
| `window.__ringClassifica` | estensione (service worker), app (`ponte.js`) | lettura e invio della classifica globale |
| `window.__ringArena` | app | arena con lava: `{ lava: altezza }` |
| `window.__ringHudEsterno` | app | niente cruscotto né controller a ventaglio: li disegnano i comandi nativi |
| `window.__ringGrafica` | app | fps 30/60/120, risoluzione 50-100 %, dettaglio basso/medio/alto |
| `window.__ringBordoOggetti` | app | oggetti tenuti lontani dai bordi (lottatori incastrati negli angoli) |
| `window.__ringSceltaModo`, `__ringEstensione`, `__ringDati` | estensione, app | scelta del modo e dati dell'ospite |
| `window.__ringNome`, `__ringMotto` | sito del gioco | nome nel logo del menu e nella guida (di serie «Page Brawl»; tre parole vanno su due righe) e motto sotto il logo |
| `window.__ringMusicaBase` | sito del gioco | musica di serie: `"sempre"`, `"corsa"` (di serie), `"mai"` |
| `__ring.tempoParry()`, `premi(id)`, `lascia(id)`, `musica(o)`, `calibra(...)` | sito del gioco (`hud.js`) | tasto Parata a tempo, azioni dei tasti anche a tastiera spenta, musica e taratura del ritardo audio |
| `window.__ringUrto(u)`, `__ring.rileva()` | arene (`android/web/arena.html`) | il motore dice dove arriva una botta (`{x, y, r, forza, tipo, el}`: esplosione, meteora, urto, pavimento, sisma); l'arena crepa e fa crollare le pedane fragili, poi chiede di rileggere i solidi |
| `window.__ringModoLibero`, `__ringModoScelto(modo)` | sito del gioco | rinomina la seconda voce del menu («1 contro 1», con `unoControUno` si comanda il proprio lottatore da subito) e avvisa l'ospite del modo scelto (il sito cambia arena con `__pbArena`) |
| `window.__ringAccount` (`stato()`, `apri()`) | sito del gioco | voce «Account» nel menu principale (col segno «OSPITE» se non si è entrati) e, nel roster, l'avviso che da ospite i progressi restano solo sul dispositivo |
| `window.__ringRoster` | sito del gioco | accanto al menu iniziale i personaggi con le doti dell'allenamento, da alzare coi crediti |
| `[data-ring-fuori]` (attributo), `window.__ringSuggerimenti`, `__ringRadialeInBasso`, `__ringSuolo` | sito del gioco | i tocchi dentro un elemento con l'attributo non arrivano al motore; `false`: niente suggerimenti dei tasti sul canvas; controller nell'angolo dello schermo e non sul pavimento; zombie, gemme e forzieri escono dal terreno, che riceve le botte `"emerge"` |
| `__ring.mosse()`, `cambia()`, `pannello()`, `pausa()`, `grafica()`, `corpi()` | letti dall'app | comandi nativi e stato del motore; dal 18/10 `mosse().lottatori[i].vola` (in volo col jetpack), per ↑ e ↓ del sito del gioco |

Chi aggiunge un hook lo scrive in questa tabella e in `android/LEGGIMI.md`.

### 4.3 Estensione del browser

Guida completa in `estensione/LEGGIMI.md`; testi per lo store, privacy e passi di pubblicazione in `estensione/SCHEDA-STORE.md`; schermate in `estensione/scheda/` (quelle della 1.1.0 in `scheda/1-1-0/`).

- Permessi minimi: `activeTab`, `scripting`, `storage`. Il permesso su tutti i siti è facoltativo (tasto su ogni pagina).
- **Premium**: `estensione/premium.json`. Oggi `premium_attivo: false`, tutto gratis («totalmente gratuito per questa versione», 10/10). Il blocco è nel codice del client: barriera per l'utente normale, non protezione. Nessuna verifica di acquisto esiste.
- **1.1.0 (13/10)**: shadow DOM aperti, sporgenze sulle «scatole», elementi che sobbalzano, volo dopo 8 s, classifica globale dal service worker verso `https://mobileupdatetracker.duckdns.org/api/corsa` senza credenziali, occhi nuovi dei super guerrieri.
- **1.1.0 pubblicata** il 14/10/2026. La classifica dell'estensione dipende dalle rotte `/api/corsa` del sito, in produzione da `df97c09`. Verificare nella console che la scheda privacy dichiari il dato che ora esce (il nome in classifica).
- Pubblicare: `python3 estensione/costruisci.py --zip` → `estensione/zip/page-brawl-<versione>-store.zip`. La console del Web Store la compila Riccardo a mano: Chrome non lascia automatizzarla.
- Ogni nuova versione: alzare `VERSIONE` in `estensione/costruisci.py`, rigenerare, rifare lo zip.

### 4.4 App Android

Guida completa in `android/LEGGIMI.md`. Pacchetto `com.rikyroky.pagebrawl`, minSdk 26, targetSdk 36.

Quattro modalità: **blocco schermo**, **tutto il telefono** (bolla col guantone su qualsiasi app), **solo Chrome**, **nell'app** (arene lava, cielo, ring e corsa infinita). Più riquadro nelle impostazioni rapide e browser interno.

Perché un **servizio di accessibilità**: è l'unica finestra che Android lascia stare sopra il blocco schermo (`TYPE_ACCESSIBILITY_OVERLAY`) ed è l'unico modo di sapere dove stanno gli elementi delle altre app. Si leggono solo le posizioni dei riquadri, solo a ring acceso; nessun testo, niente salvato o inviato. Su Android 13+ da APK l'interruttore è grigio finché non si apre Info app → ⋮ → «Consenti impostazioni con restrizioni».

File principali in `android/app/java/com/rikyroky/pagebrawl/`: `Ring.java` (servizio), `Comandi.java` + `Disegni.java` + `OspiteVista.java` (comandi nativi), `Arena.java`, `Principale.java` (UI in codice, avviso e consenso), `Memoria.java`, `Premium.java` + `Acquisto.java`, `Bordi.java` (edge-to-edge e Indietro di Android 16), `Browser.java`, `Riquadro.java`. Il pagamento vero è in `app/java-billing/PremiumGoogle.java`.

**Due modi di costruire**, e non sono equivalenti:

| | `android/costruisci.py` (locale, senza Gradle) | `.github/workflows/android-play.yml` (Gradle) |
| --- | --- | --- |
| Attrezzi | `aapt2`, `android.jar` 36, `javac`, `d8`/`dx`, `apksigner`, `bundletool` da `$ANDROID_HOME` o `~/tools` | Gradle 8.14.3, AGP 8.13, JDK 17 |
| Premium | **finto**: tutto aperto (niente Billing) | Google Play Billing 9.1.0, prodotto `premium` a acquisto unico |
| Uscita | `android/build/PageBrawl.apk` firmato con la chiave di prova | pre-release GitHub `android-<commit>` con due AAB **non firmati** (completa e leggera) |
| Uso | prove sul telefono | Play Store |

Comandi:

```bash
python3 android/costruisci.py                    # APK di prova
python3 android/costruisci.py --aab              # anche AAB (personaggi di partenza robot e mela)
python3 android/costruisci.py --aab --guerrieri  # AAB coi super guerrieri di partenza
python3 android/costruisci.py --leggera          # piano B senza accessibilità né riquadro (versionCode +1)
python3 android/costruisci.py --solo-asset       # solo gli asset, per provare l'arena nel browser
python3 android/costruisci.py --firma PageBrawl-completa-nonfirmato.aab   # firma con la chiave di caricamento
```

Firme: `android/firma/pagebrawl-debug.jks` (password `pagebrawl`) è **di prova** e sta nel repo apposta, perché ogni APK si installi sopra il precedente. La chiave di caricamento `android/firma/pagebrawl-upload.jks` + `.txt` **non sta nel repo** (è in `.gitignore`); se si perde, va chiesto a Google il reset della chiave di caricamento. Con Play App Signing la firma finale la mette Google.

Per una nuova versione: alzare `VERSIONE` e `CODICE_VERSIONE` in `android/costruisci.py` (la leggera prende `CODICE_VERSIONE + 1`, quindi il prossimo codice libero è sempre +2).

Play Store, decisioni prese il 12/10: gratis con Premium a acquisto unico («facciamo gratuito con sblocco premium»); avviso e consenso espliciti per l'accessibilità (norme Play per chi non è uno strumento di accessibilità); variante leggera come piano B se Google rifiuta l'accessibilità. Foto e video dello store: `android/store/promo/cattura.py` e `componi.py`, uscita in `android/store/consegna/` (fuori da git). Il documento «Page Brawl su Google Play: guida e fattibilità» sta nel progetto Claude, non nel repository.

### 4.5 Classifica globale

`GET /api/corsa/classifica` e `POST /api/corsa/punteggio` in `web/main.py`, CORS aperto (`_CORSA_CORS`), niente cookie né account. Il server controlla nome, personaggio e stile ammessi, un tetto di punti che cresce col quadrato del round, una durata minima di 5 s per round e un limite di invii per IP in memoria. Il punteggio arriva dal client, quindi chi vuole barare può: il controllo ferma solo i valori impossibili.

Dipendenza da ricordare: **estensione e app dipendono dal dominio del tracker**. Se il sito cambia dominio o va giù, la classifica smette di funzionare negli store.

#### 4.5 bis Account dei giocatori di Parry Brawl Survivor (18/10/2026)

Il sito del gioco su GitHub Pages (`https://rikyroky91-commits.github.io/parry-brawl-survivor/`) registra i giocatori e tiene il loro salvataggio su questo server, in `web/giocatori.py` (router incluso da `web/main.py`):

- `POST /api/giocatore/registra` `{nick, email, password}` → `{token, nick, salvataggio: null}`; nick 3-20 caratteri (lettere ASCII, cifre, spazio, `_`, `-`), unico senza distinguere maiuscole; email unica; password da 8 a 200 caratteri. Doppione → 409.
- `POST /api/giocatore/accedi` `{login, password}` (login = nick o email) → `{token, nick, salvataggio, aggiornato}`; credenziali sbagliate → 401 con un messaggio unico che non dice se l'account esiste.
- `GET /api/giocatore/salvataggio` e `PUT /api/giocatore/salvataggio` `{salvataggio: {…}}` (oggetto JSON, al massimo 64 KB serializzato, altrimenti 413) con `Authorization: Bearer <token>`; `POST /api/giocatore/esci` invalida il gettone.

Tabelle **separate** `giocatori` e `gettoni_giocatori`: un giocatore non è un utente del tracker e non ne riceve mai i permessi. Password con lo stesso scrypt di `core/auth.py`; del gettone (`secrets.token_urlsafe(32)`, 180 giorni) si tiene solo lo SHA-256. L'email non torna in nessuna risposta e non si scrive nei log. CORS solo per `https://rikyroky91-commits.github.io`, `http://localhost:8765` e `http://127.0.0.1:8765` (metodi GET POST PUT OPTIONS, intestazioni Authorization e Content-Type, niente cookie). Limite per IP in memoria: 5 registrazioni l'ora, 15 accessi ogni 10 minuti. Test: `tests/test_giocatori.py`. **Va in linea solo quando il ramo è unito a `main`** (deploy su Oracle); fino ad allora il sito del gioco riceve 404.

### 4.6 Contenuti e decisioni di gioco

- Gratis: robot e mela, prese e lanci, controller ad angolo, fumogeni e barattoli con le creature (Tizzo, Zip, Bolla), pioggia di oggetti, terremoto, jetpack, partita a dieci, colpo finale, trasformazioni di robot e mela, corsa infinita, audio sintetizzato, tastiera rimappabile.
- Gruppi «Premium» (oggi aperti a tutti nell'estensione): `guerrieri` (super guerrieri Zefir e Brasa, maghi Merlo e Ortica, duellanti Rovo e Scia), `armi`, `meteo` (meteoriti, buco nero, orda di zombie, gravità).
- Le **scommesse coi gettoni** sono state tolte da sito, estensione e app il 12/10.
- Effetti cruenti spenti di serie; Riccardo ha scelto di lasciare l'interruttore. Se un revisore li contesta, si tolgono dalla variante `store`.
- Di serie il gioco parte in inglese e coi super guerrieri («come personaggi principali metti i guerrieri»), tranne l'AAB del Play che parte con robot e mela.
- Super guerrieri ridisegnati l'11/10 e il 13/10 sul pupazzo di Riccardo, con costumi scelti perché non ricalchino Dragon Ball. Le **animazioni** invece devono essere «affini al mondo Dragon Ball» (16/10): stile del genere (scatti con immagini residue, onde caricate al fianco, carica dell'aura, linee d'impatto), mai gesti firma di un personaggio preciso.
- La trasformazione dei super guerrieri si chiama **Limit Break** in tutte le lingue (16/10, prima «sovraccarico»).
- I **maghi combattono a distanza** (16/10): fascia di tiro in `MAGO`, respinta, sparizione lontana (`sparizioneMago`). Duellanti e classici (robot e mela) restano com'erano per scelta di Riccardo («spadaccini e androidi li lascerei così per ora»): li toccano solo le correzioni generali dei tempi morti.

### 4.6 bis La musica a tempo (18/10/2026)

Riccardo: «un tappeto musicale ritmico che va a ritmo con i nemici e il parry», attacchi annunciati «non rari ma con un'ottima tempistica». In `ring.js`, sezione «LA MUSICA A TEMPO»:

- Musica sintetizzata a strati (cassa, rullante, piatti, basso, pad, arpeggio) su La minore – Fa – Do – Sol; lo strato sale con la lotta, col capo e con la catena di parry. 112,5 BPM (un battito ogni 32 passi), 128,6 dal primo minuto di lotta, 150 dal terzo; il tempo cambia solo a inizio battuta.
- L'orologio è quello dell'audio; i passi della fisica ci si agganciano (`agganciaPasso`). Ogni morso (e la carica letale) **prenota un ottavo** della griglia (`prenotaColpo`), al massimo uno per battito, e la carica si allunga o si accorcia a ogni passo (`ritoccaCarica`) perché il colpo arrivi lì anche dopo i fermi dei colpi secchi. Un battito prima (o mezzo) suona un «tic» dalla parte di chi attacca; per l'attacco rosso anche un soffio che sale. I draghi tirano sugli ottavi; le tre manate del capo stanno a un ottavo l'una dall'altra (a un battito sopra i 150 BPM).
- Il parry mette un accordo sul sedicesimo dopo (col piatto se perfetto), un colpo preso ovatta la musica, il rallentatore la chiude in un filtro.
- Impostazioni nuove: «Musica» (sempre / solo nella corsa / mai) e «Ritardo audio» (ms, per le cuffie Bluetooth; il sito lo misura toccando a tempo con `__ring.calibra`).
- Senza audio acceso la musica non c'è e **niente cambia** rispetto a prima: i test Node girano senza audio. `__ring.musicaFinta(true, passi)` accende la griglia senza suono per i test.
- **Non provato a orecchio su un telefono vero**: il suono è stato solo fatto girare in Chromium senza ascoltarlo. Da sentire: volume relativo della musica (`MUSICA.volume` 0,5) e degli effetti, e se il «tic» si sente nella mischia.

### 4.6 ter Stamina, arena che si rompe, 1 contro 1 (18/10/2026)

- **Stamina**: Riccardo, «stare sempre in parata fa diminuire la stamina». La guardia tenuta da chi gioca, dopo la finestra del parry, consuma `GUARDIA.tenuta` (0,3) a passo: piena si svuota in circa 5,5 s e, vuota, si rompe come per i colpi (stordimento). Si ricarica solo fuori guardia, come prima.
- **Arena «cortile»** (`?tipo=arena` in `android/web/arena.html`): pavimento di pietra largo da bordo a bordo, tre lastre sospese. Riccardo: «un ring distruttibile con le mosse e gli imprevisti». Le pedane fragili (le tre del cortile, le due piccole della lava, le tre isolette del cielo; mai il pavimento né la piattaforma grande della lava) hanno 100 punti, si crepano a vista, crollano in pezzi e tornano dopo 15 s se nessuno sta nel loro spazio. Nell'app è il primo riquadro delle arene.
- **Sito**: la corsa si gioca nel cortile; «1 contro 1» sulla lava prende il posto del combattimento libero.
- **Attacchi che si leggono** (18/10, Riccardo: «non si capisce quando attaccano»): in carica lo zombie si tira indietro e alza le braccia sopra la testa; per terra la zona del colpo si riempie, rossa e d'oro nella finestra del parry; al colpo scatta in avanti con una scia bianca ad arco (`tempoColpoZ`, `disegnaAvvisoColpo`).
- **Vita del capo** sopra la sua testa, sopra l'equilibrio; tolto il pannello grande in alto (resta quello del rivale nel duello).
- **Bruto armato primo fra i nemici nuovi** (prima era il quarto: arrivava alla minaccia 5, oltre i due minuti, e Riccardo non l'aveva visto).
- Non provato su un telefono vero; i danni (esplosione 70 × forza, meteora 85, urto di un corpo 4-16, terremoto 60 × forza ogni mezzo secondo) sono a occhio.

### 4.7 Test

`tests/ring.test.cjs` (circa 180 prove; con gli altri file Node sono 193) simula il motore in Node; `tests/test_estensione.py` controlla che le cartelle generate siano allineate e che i ritocchi reggano. Sono simulazioni col caso dentro: una caduta isolata si riprova, due di fila vanno indagate.

Tre strumenti di misura, che non sono test: `tests/misura-posture.cjs`, `tests/misura-corsa.cjs` (quanto durano i round della corsa e quanto dura una corsa, con l'eroe che gioca da solo; `PARRY=1` simula chi fa il parry alle cariche letali) e `tests/misura-lotta.cjs` (quanto si lotta davvero su 46 pagine vere: colpi al minuto, pause lunghe, cosa fanno i lottatori; `STILI=maghi SECONDI=60 node tests/misura-lotta.cjs`, `RING_JS=altro-ring.js` per confrontare con una versione vecchia). Ogni modifica a IA, ritmo o movimento si misura prima e dopo con `misura-lotta`.

**Trappola già presa:** `ring.js` è un'unica funzione enorme, quindi due `function` con lo stesso nome non danno errore, l'ultima vince in silenzio. Il 16/10 una `sparisci` nuova dei maghi ha sostituito quella vecchia (che fa sparire chi esce dal ring o cade nella lava) e ha rotto tre test che non c'entravano. Prima di aggiungere una funzione: `grep -n "function nome" web/static/ring.js`.

### 4.8 Storia in breve

| Data | Tappa |
| --- | --- |
| 30/09-01/10 | Robot e mela nella home del sito; la pagina diventa il ring; armi, jetpack, lottatori che imparano |
| 02/10 | Tre stili di personaggi; **estensione** Page Brawl e Page Snow; Premium predisposto; lingue |
| 05-06/10 | Controller ad angolo, orda a ondate, scontri di energie, buco nero, colpo finale, trasformazioni (estensione 0.5-0.6) |
| 09/10 | Corsa infinita (roguelike survivor) con classifica sul sito, audio, mira del colpo finale |
| 10/10 | Corsa verticale, tastiera, maghi e duellanti rifatti; **estensione 1.0.0 tutta gratis**; iscrizione al Web Store |
| 11/10 | Super guerrieri rifatti |
| 12/10 | **App Android** da 1.0 a 1.5.0 in un giorno: quattro modalità, lava, comandi nativi, grafica 30/60/120 fps, target API 36, consenso accessibilità, variante leggera, Billing con Gradle in CI |
| 13/10 | **Estensione 1.1.0**: la pagina conta di più, classifica globale ovunque. Android 1.5.1 (unita il 16/10) |
| 16/10 | **1.2.0 / Android 1.6.0** (sul ramo): tempi morti, super guerrieri più fluidi e Limit Break, maghi a distanza, missioni, capo ogni cinque round, rimescola |

### 4.9 Problemi noti

- **Mai provato su un telefono vero** in modo sistematico: le prove sono state su emulatore e Chromium. Il controller dell'estensione è stato provato col mouse e col tocco simulato.
- **Accessibilità e Play Store**: Google può rifiutare un'app non di accessibilità che usa quel servizio. Il piano B (`--leggera`) esiste ma perde blocco schermo, «tutto il telefono» e «solo Chrome».
- **Premium dell'estensione** senza verifica d'acquisto; Premium dell'app senza verifica lato server dell'acquisto (solo Billing sul dispositivo).
- **Classifica** con punteggi dichiarati dal client.
- La docstring di `android/costruisci.py` parla ancora di piattaforma 34 in un punto; la build usa la 36.
- Nome «Page Brawl» provvisorio: mai verificato fra i marchi registrati. Robot e mela possono ricordare due marchi noti.
- Maghi senza trasformazione vera (solo trance e aura).
- **Corsa a flusso (17/10)**: senza round la classifica tiene nel campo `round` il livello di minaccia raggiunto (il server lo controlla come prima: una fase dura ~30 s, sopra i 5 s per round del controllo). Le voci vecchie in classifica restano coi round veri. Non provato a mano.
- **Bruto armato (16/10)**: l'eroe automatico non para le granate, quindi chi lascia giocare l'eroe da solo arriva un po' meno lontano (misurato con `misura-corsa`, 4 corse: round 4-7 e 2,0-3,1 minuti, contro 5-6 e 2,6-3,2 senza bruto; con la granata a 10 invece di 12). Contro la granata il parry non è «14 fotogrammi prima del colpo» ma «premuto dopo il lampo bianco» (`aggiornaGranata`): quanto vola dipende da come si sposta l'eroe, e coi fotogrammi un giocatore non ce la faceva. Provato solo in Chromium e coi test, non a mano su un telefono.
- **Parry, seconda volta (17/10)**: tarature (equilibrio per parry 0,45, perfetto 0,7; guardia 100 con morso 22, grosso 34, carica 50; capo con tre colpi a 18 fotogrammi l'uno dall'altro) scelte a occhio e coi test, non provate a mano da una persona. Il colpo di grazia vale anche per i colpi automatici dell'eroe, non solo per quelli comandati. Le tre manate del capo sono più difficili sul telefono, dove la parata passa dal controller.
- Traduzioni ES/FR/DE del gioco non riviste da madrelingua.
- Il tema di Halloween si spegne da solo il 2 novembre; Page Snow e il tema di Natale del sito vanno ricontrollati prima di dicembre.

### 4.10 Miglioramenti possibili

1. Rendere la prova su telefono vero un passo fisso della checklist Android.
1. Tempi morti, il resto: la lotta classica passa ancora il 31% del tempo in piedi in pause lunghe, quasi tutte con i due su piani diversi o uno in volo col jetpack che l'altro non raggiunge. È il prossimo punto da misurare e sistemare (con l'accordo di Riccardo, perché tocca robot e mela).
1. Il cruscotto nativo della corsa nell'app (Comandi.java) non mostra missioni e prossimo capo, e non ha un tasto fisso per la parata: il parry sul telefono passa dalla voce «Parata» del controller, che i quattro tasti nativi non sempre mostrano. Un tasto Parata fisso nei comandi nativi è il prossimo passo per l'app.
1. Corse lasciate all'eroe automatico: con la carica letale finiscono un po' prima (2-4 minuti invece di 2-6), perché l'IA para ma non fa il parry. Chi gioca e fa il parry arriva più lontano: è voluto, ma va tenuto d'occhio.
2. Spostare il motore in una cartella `pagebrawl/` con `ring.js` diviso in moduli (fisica, personaggi, eventi, corsa, interfaccia) e un passo di build che li unisca: 14.500 righe in un file sono il collo di bottiglia di ogni modifica.
3. Verifica degli acquisti lato server (Play Developer API) prima di vendere davvero.
4. Classifica: firma o controllo di plausibilità più stretto (durata reale, eventi della partita), e un dominio proprio per Page Brawl, così gli store non dipendono dal tracker.
5. Trasformazione dei maghi.
6. Revisione delle traduzioni e verifica del nome come marchio.

### 4.11 Checklist di rilascio Page Brawl

1. Modifiche solo in `web/static/ring.js` / `lingue.js`; `node --test tests/ring.test.cjs` verde.
2. `python3 estensione/costruisci.py` e `pytest tests/test_estensione.py`.
3. Estensione: `VERSIONE` + 1, `--zip`, prova a mano in Chrome con `page-brawl-<v>-prova.zip`, aggiornare `SCHEDA-STORE.md` se cambiano testi, permessi o dati raccolti.
4. Android: `VERSIONE` e `CODICE_VERSIONE`, APK di prova sul telefono, push (parte `android-play.yml`), scaricare gli AAB dalla pre-release, `--firma`, caricare in console.
5. Se il gioco usa nuove rotte del server: pubblicare **prima** il sito, poi le uscite negli store.
6. Aggiornare questo documento.

---

## 5. Trappole già incontrate

- **Upload via zip dal browser di GitHub** salta le cartelle che iniziano col punto: così sono sparite `.github/` e `.streamlit/`. Usare git.
- **Docker su Oracle**: il 26/09 un «Conflict. The container name /sito-web-1 is already in use» ha lasciato il sito spento. Il workflow ora toglie il container e riprova, e controlla il commit su `/health`.
- **Firewall Oracle**: le immagini Ubuntu hanno regole iptables che bloccano tutto tranne SSH anche con la Security List aperta. `setup.sh` le sistema.
- **Memoria su 512 MB**: l'allocatore non restituisce la memoria liberata; vedi consegne v66, v71, v72 e `oom`. Su Oracle il problema non c'è, ma il codice deve restare sostenibile su Render.
- **Cache dei file statici**: dopo un deploy la pagina si è rotta finché i file non sono stati firmati contro la cache (01/10).
- **Agenti in parallelo** (Codex, Claude, agent/*) hanno prodotto sessioni divergenti da riconciliare a mano (v53-v55). Un ramo per giro, e unire presto.

---

## 6. Dove trovare cosa

| Domanda | File |
| --- | --- |
| Cosa fa il sito, nel dettaglio | `README.md` |
| Perché una fonte c'è o non c'è | `FONTI.md`, `INTEGRAZIONE-OPPO.md` |
| Servizi TAC e chiavi | `guida-servizi-tac.md` |
| Account amministratore | `guida-account-amministratore.md` |
| Render passo per passo | `guida-configurazione-render.md` (storico, agosto) |
| Un giro passato | `docs/consegne/` |
| Estensione | `estensione/LEGGIMI.md`, `estensione/SCHEDA-STORE.md` |
| App Android | `android/LEGGIMI.md` |
| Informativa privacy di Page Brawl | `web/static/pagebrawl/privacy.html` |

---

## 7. Per chi arriva adesso: primo giorno

1. Leggere questo file, poi `README.md`.
2. `pip install -r requirements-web.txt pytest httpx`, far girare suite Python e Node: devono essere verdi prima di toccare qualcosa.
3. Aprire `https://mobileupdatetracker.duckdns.org/health` e confrontare il commit con `main`.
4. Guardare la tabella dei rami non uniti (sezione 1) e chiedere a Riccardo quali sono ancora vivi.
5. Lavorare su un ramo, aggiornare questo documento nello stesso commit.

---

## 8. Registro delle modifiche

Una riga per giro, la più recente in alto. Data, chi, cosa, commit o ramo.

| Data | Chi | Cosa | Commit / ramo |
| --- | --- | --- | --- |
| 18/10/2026 | Claude | Guida bloccata sul primo morso dello zombie svelto (Riccardo: «anche se premo parata non va avanti»): `ritmoAiuto` fermava il tempo anche con l'eroe a terra, stordito o a metà del contrattacco, quando il tasto non può aprire la guardia, e restava fermo per sempre. Ora si ferma solo se si può parare, e il tasto premuto (`aiuto.premutoT`, in `eseguiTasto`) fa ripartire comunque per 40 passi. Test nuovo. Verificati solo i test della guida (3/3, due volte), non la suite intera; **non ancora nel sito** (`motore.json` di parry-brawl-survivor è ancora a `0f57e65`) | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Giro di Riccardo dal telefono, seconda parte. **La prima corsa giocata con la guida** («La guida, giocata»: `corsa.guida`, `aggiornaGuida`, `corsa.aiuto` e `ritmoAiuto`, `fuocoAiuto`, `disegnaBannerGuida`). Prima versione con schede da leggere, rifatta su richiesta di Riccardo («deve essere un gameplay guidato… rallenta quando si avvicina l'avversario e nel momento del parry aspetta che il giocatore prema»): finché `mut-ring-guida` non è «fatta» la prima corsa è una lezione giocata, con l'orda trattenuta (niente spawn né `prossimaFase`, sorprese e `tLotta` fermi, gli zombie dell'ondata si sbriciolano), l'eroe che non attacca e resta in mezzo, nessun danno. Passi: benvenuto, la parata (a 22 fotogrammi dal morso il gioco si ferma e aspetta il tasto; un tocco vale come tenuto), il parry (rallenta da 40 fotogrammi, si ferma dentro la finestra, «ORA!»; la guardia di prima si chiude e il riposo si azzera), da soli (solo rallentato; dopo due errori ancora una volta fermo), fine. Riga in alto, chiamata d'oro a tempo fermo, camera che stringe sul colpo (`camminaCamera`), «Salta la guida» (anche Esc). `tempoParry()` dice `aiuto` e `fermo`: il sito fa pulsare la parata con «PREMI!»/«TIENI!». **I nemici nuovi** (`SCHEDE_NEMICI`, `presentati` in `mut-ring-presentati`): la prima volta in campo il gioco si ferma, la camera va sul nemico e un fumetto accanto dice cosa fa, l'attacco e come fermarlo; poi il suo primo colpo parabile è guidato come nel parry (`GUIDATI`, `aiuto.tipo`; la carica rossa con `aiuto.rossa`; i colpi della bestia: `minacciaParry` ora dà `da` anche per i tiri). Il fucile-sega: fumetto, poi il gioco si ferma col nemico vicino finché non si preme per l'agguato. Dati del gioco: sul sito finiscono nel salvataggio dell'account. Nei test `ambiente()` parte con guida fatta e nemici già visti (`nuovo: true` per il giocatore nuovo); due test nuovi. **La parata lasciata** (`lascia("para")`, keyup) resta aperta almeno quanto la finestra del parry: col tocco veloce sul telefono si chiudeva dopo sei fotogrammi. **La bestia armata** (prima «bruto armato»: Riccardo voleva le locuste di Gears of War; non copiata, disegno originale): `disegnaBestia` al posto del corpo da zombie (pelle blu ardesia, spalle larghe, creste d'osso, gambe da bestia, coda, zanne), pose sue (corsa bassa, accovacciata, in ginocchio a mirare, calcio dell'arma), più veloce, sposta la posizione a scatti fra un tiro e l'altro e schiva con un balzo indietro o sopra la testa (`iniziaScattoBruto`, `scattoBruto`, intoccabile in aria). **La scelta del personaggio rifatta** (`disegnaScelta`, `schedaEroe`): fondo, titolo e righe del menu principale, una scheda per personaggio col ritratto e GIOCA, missioni sotto (`disegnaMissioni` ha un massimo di righe), bottega e classifica in fondo, «‹ Menu» in alto. 93 voci nuove in `lingue.js` (quattro lingue) | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Giro di Riccardo dal telefono (sito del gioco): **l'agguato del fucile-sega** (`AGGUATO`, `agguatoSega`, `eseguiSquarcio`, `squarcia`, `tagliaInDue`, `rompiSega`): con la motosega in mano la parata mette in posa (dura 150 passi anche a tocco singolo: `lascia("para")` non la chiude); il primo zombie o lottatore a portata (66 px) parte lo «squarcio» a rallentatore (56 fotogrammi, zoom, fermo): lo zombie va in due metà vere (la sua figura ritagliata sopra e sotto la pancia, particelle `pezzoZ` forma `meta`), braccia, testa e poltiglia per il ring; il capo perde un terzo; l'avversario del duello perde due arti. Poi la sega si rompe e vola via (`pezzoZ` forma `sega`, l'arma `morto`). Chi gioca non sega più da solo (`segaPronta`); gli altri lottatori rompono la sega dopo la prima segata. `tempoParry()` dice `sega`, `agguato`, `squarcio` (il sito disegna la motosega sul tasto). **Livelli della corsa**: `xpPerLivello` +50 al primo livello, a calare fino a zero al tredicesimo (misura con l'eroe da solo, 12 corse: livello medio a un minuto da 4,4 a 1,9; le corse automatiche durano un po' meno, da 1,9 a 1,6 minuti, perché arrivano meno carte). **Terreno dall'ospite**: `window.__ringAltezzaSuolo(tipo, W, H, largo)` in arena.html (arena e lava), per il sito che ci mette i tasti touch sotto. Test: fucile-sega riscritto, tre test con `esperienza()` alzata a 70. Node 217/218 a suite intera (n. 132 «trasformazioni», statistico, da solo passa 2 su 2), Python 1893 verdi. Provato in Chromium headless a misura di telefono; **non provato su un iPhone vero** | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Giro di Riccardo dal telefono: **zombie che scavano** col suolo vivo (`z.scava`, `sottoTerra`: 0-14 sotto terra col suolo che si gonfia e sputa terra, al 14 la mano sfonda e si apre la buca, poi risale a tre strattoni) e **solo dal pavimento in basso**: con l'orda su una lastra si esce sotto e si salta su (`balzaSu`; `traslocaOrda` non fa più spuntare nessuno dalla lastra). **Il morso** (`morsoZ`): bocca che si spalanca coi denti nella carica, testa indietro, poi scatto avanti con le fauci che si chiudono e lo schiocco, mani a tagliola. **Il bruto** (i «Locust» di Riccardo): esce da un pozzo di lava (`buche` con `lava`), raffiche di tre colpi del fucile-sega col raggio rosso di mira (`raffica`, `sparaProiettile`, tiri `proiettile` che col parry tornano a chi li ha sparati e contano nell'anello), indietreggia se si è troppo vicini, e se l'eroe è su una lastra resta giù e spara da lì (`brutoDaSotto`); il nemico nuovo della minaccia entra in testa alla coda (`prossimaFase`: prima arrivava dopo tutta la coda della fase prima, e alla minaccia 4 il bruto non si era ancora visto). **Contrattacco rifatto** più corto (32 passi), lento solo un attimo sui colpi, con le mosse vere (montante, calcio, doppio diretto); lampo a schermo dimezzato. Controller radiale nell'angolo alto quanto la fascia del pavimento. **Classifica dal menu principale** che non si apriva (il menu si riapriva sopra). Node 210/210. Provato in Chromium (fotogrammi di scavo, bruto, contrattacco, classifica), non su un telefono vero | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Account nel menu principale del gioco (`__ringAccount`, Riccardo: «accedi o gioca come ospite, ma fai capire che per conservare statistiche e upgrade serve l'account»): voce «Account» con «OSPITE», avviso nel roster; il sito apre «Benvenuto: registrati, accedi o gioca come ospite» una volta per visita. Node 208/210 a suite intera, le due cadute (n. 46 pieghevole, n. 132 mira) da sole 2 su 2 | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | **Il contrattacco in scena** (Riccardo: «ogni parry un contrattacco a rallentatore, animazioni fluide fra personaggio e nemico»; spunti dai video indicati, Prince of Persia: The Lost Crown e i metroidvania col parry, non visti: YouTube blocca il container): per chi gioca il «contro» dura 46 passi (`CINEMA`), con camera che stringe sui due e bande nere, rallentatore a rampa (`rampaCinema`), scatto con immagini residue, montante che solleva, fendente girato, colpo finale che scaraventa giù e apre il terreno; se il nemico cade prima si va dritti al colpo finale a vuoto; all'orlo dell'equilibrio il colpo è di grazia. Nemici: zombie che si possono tenere in aria (`vAlzo`, `ruota`), reazione alla botta (`reaz`), il colpo cala ad arco con ritorno, la stella d'oro sulla mano quando si apre la finestra del parry. **Roster** accanto al menu iniziale (`__ringRoster`, `disegnaRoster`): famiglie, ritratti dal vivo, le cinque doti dell'allenamento coi crediti. Lo stato espone `cinema`; tre test del parry adattati alla sequenza più lunga (170 fotogrammi invece di 50, zoom e rallentatore contano anche la sequenza). Node 210/210. Provato in Chromium (fotogrammi della sequenza, roster che compra), **non** su un telefono vero | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Account dei giocatori di Parry Brawl Survivor sul server (`web/giocatori.py`, sezione 4.5 bis): `POST /api/giocatore/registra`, `POST /api/giocatore/accedi` (nick o email), `GET`/`PUT /api/giocatore/salvataggio` (Bearer, JSON fino a 64 KB), `POST /api/giocatore/esci`; tabelle nuove `giocatori` e `gettoni_giocatori`, separate dagli utenti del tracker; scrypt di `core/auth.py`, gettoni salvati solo come SHA-256 (180 giorni); CORS per il sito su GitHub Pages e per `localhost:8765`; limite per IP. `tests/test_giocatori.py` 13/13; suite Python 1884 passati, 9 caduti in `test_core.py` (realme C61/C63) già rossi sul commit di partenza, non toccati. In linea solo dopo l'unione a `main` | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Sito Parry Brawl Survivor, pulizia dell'interfaccia (Riccardo: suggerimenti dei tasti sopra il menu, tre tasti vecchi nell'angolo, il menu del sito che bloccava il gioco, controller sul pavimento, «cerchio giallo bruttissimo», stamina su una barra a parte). Nel motore: `[data-ring-fuori]` (i tocchi sui pannelli dell'ospite non li prende più il motore: era il blocco), `__ringSuggerimenti`, `__ringRadialeInBasso`, `__ringSuolo`; lo scudo della guardia è anche la stamina (tolto l'arco sotto i piedi); la frenesia è una pozza di luce sul terreno invece dell'anello coi pallini; il **terreno che si apre** (`squarciaSuolo`, buche disegnate): zombie che escono con zolle e schegge, gemme e forziere delle sorprese che escono dal suolo; botta nuova `"emerge"` per l'arena. In `arena.html` il pavimento del cortile tiene i segni (buche, crepe, brace e bruciature, trema col terremoto). Node 204/205 a suite intera, due cadute casuali in due giri diversi (n. 70 maghi, n. 164 lava) che da sole passano 2 su 2. Effetti del terreno **non visti a occhio** in una corsa vera, solo il codice e i test | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | `mosse()` dice chi è in volo (`vola`), per le frecce facoltative del sito Parry Brawl Survivor sul PC (↑ decolla, ↓ atterra). Node 218/218 | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Attacchi degli zombie leggibili (carica, zona per terra rossa/oro, scia del colpo), vita del capo sopra la testa, bruto armato primo fra i nuovi. Node 218/218 | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Stamina della guardia tenuta, arena «cortile» con pedane che si rompono (anche nelle arene lava e cielo, e nell'app), «1 contro 1» al posto del combattimento libero sul sito; tre test nuovi. Node 218/218 | `claude/parry-brawl-web` |
| 18/10/2026 | Claude | Musica a tempo nel motore e API per i comandi touch del sito nuovo **Parry Brawl Survivor** (repo `parry-brawl-survivor`, costruito da questo motore a un commit fissato); logo e motto del menu decisi dall'ospite; due test nuovi (morsi sulla griglia, azioni a tastiera spenta). Test Node: due cadute casuali isolate (n. 76 e n. 86), da sole passano 3 su 3. Non unito a `main` | `claude/parry-brawl-web` |
| 17/10/2026 | Claude | CI rossa su `main` (anche sull'unione di prima, `f8d3910`) per due test instabili già noti, sistemati: l'arena di lava (3 su 20) ora spegne gli imprevisti, tiene fermo il robot lontano dal bordo mentre prova la lava e guarda dove la mela ricompare appena rientra; «gli oggetti entrano dai lati» (1 su 20: dall'alto ne arriva meno di uno su due, a caso) guarda altri 150 s se non li ha visti tutti e due. Dopo: 0 su 40 e 0 su 20, suite Node 214 su 214. Nessuna modifica al gioco | `main` |
| 17/10/2026 | Claude | **Unito a `main`** il parry, seconda volta (avanti veloce del ramo `claude/exciting-cori-6cwl9m`, CI verde sul ramo): il push pubblica il sito su Oracle. Da fare a mano, come prima: caricare la 1.2.0 sul Chrome Web Store, l'AAB su Play, l'account Ko-fi | `main` |
| 17/10/2026 | Claude | CI rossa sul parry nuovo: «la mira… gli zombie si falciano» è caduto una volta in CI (0 su 30 in locale). Il test sceglieva anche uno zombie addosso al robot, dietro l'origine della linea: ora ne sceglie uno ad almeno 80 px. Reso robusto anche il test del Limit Break (la trasformazione si richiede di nuovo se un colpo la interrompe). Nessuna modifica al gioco | `claude/exciting-cori-6cwl9m` |
| 17/10/2026 | Claude | Il parry, seconda volta (spunti da Sekiro, God of War, Expedition 33, Lies of P; il video indicato da Riccardo non si è potuto scaricare, viste solo le anteprime): parry perfetto negli ultimi 5 fotogrammi, lampo bianco e zoom sull'impatto, equilibrio dei nemici e colpo di grazia, catena ×N, anello rosso e «!!» sulla carica letale, tre manate del capo con «CONTRO TOTALE», guardia che si consuma e si rompe, barra dell'equilibrio sotto quella del capo, pagina nuova nella guida, 12 traduzioni. Provato coi test e in Chromium, non a mano | `claude/exciting-cori-6cwl9m` |
| 17/10/2026 | Claude | **Unito a `main`** il ramo `claude/exciting-cori-6cwl9m` (Page Brawl 1.2.0 / Android 1.6.0, donazioni Ko-fi, corsa a flusso, parry al centro, menu): il push pubblica il sito su Oracle. Da fare a mano: caricare la 1.2.0 sul Chrome Web Store, l'AAB su Play, l'account Ko-fi | `main` |
| 17/10/2026 | Claude | CI rossa sul menu: il test «super guerrieri… restano stabili» cadeva circa una volta su 25 anche prima (provato col commit precedente). Causa vera nel gioco: nei colpi finali chi vola (mulinello, orbita…) contro un bordo usciva di qualche pixel con la testa. Corretto: margine del mulinello a 64 px, chi prende il colpo spostato via dal bordo all'inizio, e `tieniDentroFatale` a ogni passo. 360 prove senza uscite | `claude/exciting-cori-6cwl9m` |
| 17/10/2026 | Claude | Menu nuovo sul canvas: principale (al posto della scelta del modo), guida in sei pagine, impostazioni (volume, anello e aiuto al parry, rallentatore, scossa, difficoltà, tasti), pausa con Esc o ⏸; tasto «Menu» nella tendina; 89 traduzioni | `claude/exciting-cori-6cwl9m` |
| 17/10/2026 | Claude | Parry al centro: anello del tempo, scudo in guardia, rallentatore e suono del parry, contrattacco visibile, «troppo presto / troppo tardi», morsi che non si interrompono vicino al colpo, cariche letali più frequenti; aggancio col mouse | `claude/exciting-cori-6cwl9m` |
| 17/10/2026 | Claude | Corsa a flusso (niente round: fasi di «minaccia» attaccate, capo ogni cinque, forziere senza pausa, livelli un quarto più lenti), tasti fissi W aura / D pugni / A onda con la camminata sulle frecce (migrazione dei tasti salvati), carte e forziere da tastiera (1 2 3, frecce e Invio, R) | `claude/exciting-cori-6cwl9m` |
| 16/10/2026 | Claude | Donazione libera con Ko-fi, solo nell'estensione (scelta di Riccardo): tasto «Sostieni Page Brawl» nella tendina (`url_donazione` in `premium.json`), webhook `/api/kofi` col token, tabella `donazioni` (nome, importo, messaggio; niente email), pagina `/admin/donazioni`; informativa aggiornata. Manca l'account Ko-fi | `claude/exciting-cori-6cwl9m` |
| 16/10/2026 | Claude | Bruto armato (granata parabile e rimandabile col parry, al lampo bianco), fucile-sega che lascia morendo (spara e sega, zombie in pezzi), +10 crediti a granata rimandata. Corretto un difetto vecchio: il getto del jetpack (`fiammata`) era coperto dal lanciafiamme con lo stesso nome e non si vedeva; tolta una `disegnaAlbero` morta; nuovo test contro le funzioni doppie | `claude/exciting-cori-6cwl9m` |
| 16/10/2026 | Claude | Lampo del parry rifatto dalle immagini di Riccardo: nucleo bianco, raggi a stella con punte a croce, bolla dorata, mezzelune verso chi attacca, righe di velocità, e un attimo di buio dietro perché sulle pagine chiare si veda | `claude/exciting-cori-6cwl9m` |
| 16/10/2026 | Claude | CI rossa del secondo giro: tre test del ring resi robusti (jetpack dopo la gravità e dopo le gambe, gamba persa prima del test, carica letale a vuoto o con l'eroe invulnerabile). Nessuna modifica al gioco | `claude/exciting-cori-6cwl9m` |
| 16/10/2026 | Claude | Page Brawl 1.2.0, secondo giro: parry con S (guardia tenuta, finestra di 14 fotogrammi, contrattacco), carica letale degli zombie (scintilla rossa, rincorsa, contrattacco letale ad area), primi round lenti e round più lunghi (13 → 34 s), premio in crediti e allenamento per personaggio. Non su `main` | `claude/exciting-cori-6cwl9m` |
| 16/10/2026 | Claude | Page Brawl 1.2.0 / Android 1.6.0: tempi morti rifatti da `61f8ca9` e misurati, super guerrieri più fluidi, Limit Break (occhi e capelli sistemati), maghi a distanza con la respinta, missioni, capo ogni cinque round, rimescola. Non su `main` | `claude/exciting-cori-6cwl9m` |
| 16/10/2026 | Claude | Unite a `main` Android 1.5.1 (`claude/android-ring`) e la correzione della ricerca per codice (`claude/loving-cannon-1t7wdu`), dopo revisione del codice e test della ricerca verdi | `main` |
| 16/10/2026 | Claude | Controllati tutti i rami remoti contro `main`: 30 cancellabili, 3 da tenere; trovato il lavoro perso `61f8ca9` (lotte più fitte). Verificato che l'estensione 1.1.0 è pubblicata | `claude/exciting-cori-6cwl9m` |
| 16/10/2026 | Claude | Creato questo documento unico di consegna (tracker + Page Brawl) e la regola di aggiornamento in `CLAUDE.md` | `claude/exciting-cori-6cwl9m` |
| 15/10/2026 | Claude | Ricerca per codice: niente sostituzioni dall'AI, codice cercato nei TAC | `c2d65de` |
| 13/10/2026 | Claude | Android 1.5.1: sospensione a schermo spento, comandi orfani, Leaderboard nel menu | `d9779b8` |
| 13/10/2026 | Claude | Page Brawl 1.1.0 estensione, classifica globale con CORS | `df97c09` |
| 12/10/2026 | Claude | App Android 1.0 → 1.5.0, Billing, Gradle in CI | `86e52de` … `9b746b0` |

Le voci precedenti stanno in `git log` e in `docs/consegne/`.

---

## 9. Regola di aggiornamento

Chi chiude un giro di lavoro (persona o agente), **nello stesso commit**:

1. aggiorna la data e il commit in cima;
2. aggiunge una riga al registro (sezione 8);
3. aggiorna le tabelle di stato (versioni, rami non uniti, cose in sospeso) se sono cambiate;
4. sposta un problema da «Problemi noti» al registro quando è risolto, e aggiunge quelli nuovi;
5. se il giro è grande, scrive anche `docs/consegne/passaggio-consegne-<nome>.md` col dettaglio e lo collega da qui.

Un documento di consegna che non dice la verità sullo stato è peggio di nessun documento: se qualcosa non è stato verificato, si scrive «non verificato».
