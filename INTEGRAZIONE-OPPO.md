# Endpoint Oppo — trovato, verificato, e come collegarlo

Risposta al **compito prioritario** del documento di passaggio consegne.
Verificato il 2026-08-02.

## L'indirizzo interno

La pagina `support.oppo.com/…/software-download/?m=Find%20X2` è davvero un
guscio: nell'HTML grezzo il titolo è `OPPO XX Download Firmware`. Il dato
arriva da una chiamata che il browser esegue dopo il caricamento, definita
in `software-detail.min.js`:

```
POST https://par-sow-cms.oppo.com/oppo-server/softwareUpgrade/info
Content-Type: application/json

{"region": "it", "langId": "1040", "seriesLangId": "1040", "model": "Find X2"}
```

Risposta (accorciata, è quella vera):

```json
{"code": "1", "msg": "SUCCESS!", "data": [{
  "prefix": "OPPO", "machineModel": "Find X2",
  "softwareVersion": "CPH2023_11_A.42",
  "fileSize": "3644", "releaseDate": "2020-12-19 02:28:23",
  "versionPath": "https://assorted.downloads.oppo.com/firmware/CPH2023/CPH2023EU_11_OTA_0920_all_….ozip",
  "content": "<p>[Sicurezza]</p><p>· Aggiunte le patch di sicurezza Android di settembre 2020…</p>"
}]}
```

Elenco dei modelli disponibili, stessa API:

```
POST {host}/softwareUpgrade/model
{"region": "in", "langId": "1033", "seriesLangId": "1033"}
```

Due host, l'API è regionalizzata e una regione non risponde sull'host
sbagliato:

| host | regioni verificate |
|---|---|
| `https://par-sow-cms.oppo.com/oppo-server` | it de fr es nl pl |
| `https://sgp-sow-cms.oppo.com/oppo-server` | in tw ae au th id my ph sg jp nz pk bd lk np kh mm eg sa ng ke hk za |

`SOWAPIPATH`, `SOWREGION` e `SOWLANGID` sono dichiarati in chiaro
nell'HTML di ogni pagina del sito: non c'è niente da indovinare.

## Le due condizioni per fermarsi: nessuna delle due si verifica

* **Firma calcolata dal JavaScript** — non c'è. Il corpo della richiesta è
  JSON in chiaro, nessun header di autenticazione, nessun token.
* **User-Agent dell'app ufficiale** — non serve. Le chiamate qui girano con
  `C.USER_AGENT`, cioè identificandosi onestamente per quello che sono. È
  la differenza rispetto a `oppo_official` (API OxygenUpdater) in
  `RETIRED_SOURCES`, che rispondeva 403 a chiunque non si fingesse l'app.

Anche cambiando il parametro `model` funziona: è il meccanismo previsto
dalla pagina stessa.

## Il limite, che cambia la portata del guadagno

Questo **non** è l'elenco di tutti gli Oppo: è l'archivio dei **firmware
completi scaricabili**, che Oppo pubblica solo per i modelli fino al
2021-2022 circa. L'unione di tutte le regioni dà **94 modelli**, il più
recente dei quali è un Reno4 / A54. Per un Find X9 Pro o un Reno13 l'API
risponde `code=1` con `data` vuoto — nessun errore, semplicemente nessun
dato.

Quindi:

* per **~94 modelli Oppo** si passa da «versione di fabbrica dedotta da
  GSMArena» a **versione firmware ufficiale, con data di rilascio reale,
  peso del pacchetto e livello di patch di sicurezza**, più lo storico
  delle release precedenti (fino a 25 per il Find X);
* per tutti gli altri **non cambia nulla**, e GSMArena resta il ripiego
  esattamente come prima.

Non è la copertura che il documento sperava, ma è dato ufficiale vero, e
l'alternativa non esiste: OPPO non pubblica da nessuna parte la versione
OTA corrente dei modelli recenti.

## Cosa c'è già, pronto

`core/oppo_official.py` — modulo autonomo, dipende solo da `core/config.py`
e dalla stdlib (niente `requests`, quindi il workflow orario di GitHub
Actions non va toccato).

```python
from core.oppo_official import fetch_oppo_official

dato, errore = fetch_oppo_official("oppo reno 4 pro")
# → ({'device_model': 'Reno4 Pro', 'build': 'CPH2109_11_A.17',
#     'published': '2020-09-07 19:47:00', 'size_mb': 3711,
#     'changelog': '[Security] · Added the September 2020 Android security patch…',
#     'link': 'https://assorted.downloads.oppo.com/…',
#     'versioni_archiviate': 1, 'source_trust': 'structured', …}, None)
```

Tre esiti distinti, e la distinzione è la parte che conta:

| ritorno | significato |
|---|---|
| `(dict, None)` | trovato |
| `(None, None)` | modello fuori dall'archivio — **normale, non un guasto** |
| `(None, "…")` | la fonte non ha risposto — questo sì va segnalato |

Se il secondo caso venisse trattato come errore, Diagnostica mostrerebbe la
fonte Oppo in rosso praticamente sempre, e un allarme che suona sempre non
viene più letto.

`tests/test_oppo_official.py` — 21 test, tutti verdi, che girano **sulle
risposte registrate dal servizio vero** (`tests/fixtures/oppo_api.json`),
non su risposte inventate. Se un giorno il formato cambia, il modo giusto
di aggiornarli è ricatturare il file.

## Collegamento in `sources.py` — fatto

Registrata in `_STRUCTURED_LOOKUPS_LIST` come `StructuredLookup` per
`C.OPPO`, **prima** delle due fonti Oppo che danno la versione di fabbrica
(elenco AER e piano realme) e prima di GSMArena. `_lookup_oppo_support()`
traduce la risposta in `RawItem`.

Due scelte che vale la pena aver scritto:

* **`costo="basso"`, pur facendo una richiesta per dispositivo.** Il
  catalogo dei modelli coperti sta in memoria, quindi un nome che non c'è
  viene escluso *senza toccare la rete*: la richiesta si paga solo quando il
  modello esiste davvero. Marcandola `"alto"` entrava in gioco solo a marca
  già dedotta, e **«find x2» scritto senza «oppo» non trovava niente** — lo
  ha rivelato la matrice di ricerca, appena aggiunta la riga.
* **Niente `size_gb`.** Sono tutte ROM complete da 3-4 GB: passarle al
  semaforo QA renderebbe 🔴 MAJOR anche una patch di sicurezza. La
  dimensione resta come testo in `size_info`, la severità la decide
  l'euristica sul changelog.

Il nome del modello porta la marca (`OPPO Find X2`, non `Find X2`), presa
dal campo `prefix` dell'API: le altre fonti Oppo scrivono «OPPO A6x», e un
nome senza marca avrebbe prodotto un `device_key` diverso per lo stesso
telefono — due dispositivi in archivio, ciascuno con metà della storia.

`DATA_LOGIC_VERSION` è a **18**.

### Verifica dal vivo, attraverso il vero percorso di ricerca

```
OPPO Find X2     -> OPPO Find X2    CPH2023_11_A.29  2020-08-18  3.8 GB · 3 versioni in archivio
find x2          -> OPPO Find X2    CPH2023_11_A.29  2020-08-18  3.8 GB · 3 versioni in archivio
oppo reno 4 pro  -> OPPO Reno4 Pro  CPH2109_11_A.17  2020-09-07  3.6 GB
A54              -> OPPO A54        CPH2239_11_A.07  2021-05-11  3.1 GB
OPPO Find X9 Pro -> OPPO Find X9 Pro  (nessuna build) — ricade sull'elenco AER, come deve
Galaxy S24 Ultra -> Galaxy S24 Ultra  S928BXXS6DZG1  — Samsung invariata
```

La quinta riga è la più importante: un modello moderno **non** produce dati
falsi, ricade sulla fonte successiva.

## Nota su OnePlus (punto 3 dei possibili sviluppi)

Il documento ipotizzava che risolvere Oppo risolvesse anche OnePlus. Non è
così: `oppo.com` e `oneplus.com` sono due siti diversi, e questa API copre
solo i modelli a marchio OPPO. Ho provato `service.oneplus.com` (**403** a
qualunque accesso automatico) e `oneplus.com/global/support/software-upgrade`
(**404**). Dettagli in `FONTI.md`.
