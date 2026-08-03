# Mobile Update Tracker — passaggio consegne (v23)

Aggiorna e sostituisce `passaggio-consegne-v20.md`. Le parti non ripetute
qui (fonti provate e scartate, endpoint Oppo, catalogo AER, riscrittura
dell'interfaccia) restano valide come scritte lì.

---

## Cos'è

App Streamlit per QA: dato un telefono (nome commerciale, codice modello o
IMEI), dice **a che versione software è arrivato**, **quando**, e ora anche
**se è cambiato da quando l'hai testato**.

- Repo GitHub: **`rikyroky91-commits/android-updater`**
- Deploy su Streamlit Community Cloud
- **`DATA_LOGIC_VERSION` = 22** — invariata, e la ragione conta: in questa
  sessione non è cambiato il modo in cui una fonte viene *interpretata*,
  quindi non c'è motivo di azzerare l'archivio. Incrementarla «per
  sicurezza» costerebbe una ricostruzione completa senza guadagnarci nulla.
- **335 test**, tutti verdi, nessuno tocca la rete — e stavolta è
  verificato, non promesso (vedi sotto)

```bash
python -m unittest discover -s tests
```

---

## Cosa è stato fatto in questa sessione

### 1. Due bug, entrambi trovati eseguendo la suite ricevuta

La suite arrivava con **2 test rossi su 309**. Nessuno dei due era un test
capriccioso: erano difetti veri.

**La cache del catalogo AER non scadeva mai.** In `core/aer_catalog.py` il
sentinel «mai scaricato» era `_scaricato_a = 0.0`, confrontato con
`time.monotonic()`. Ma lo zero di `monotonic()` è arbitrario — è il boot
della macchina, non un'epoca. Su un container appena avviato `monotonic()`
vale una manciata di secondi: `0.0` non significava «scaduto da sempre» ma
«scaricato 94 secondi fa».

L'errore era mascherato da `_dispositivi is not None`, che faceva da guardia
di fatto, quindi in produzione il primo caricamento funzionava lo stesso.
È saltato fuori solo perché un test provava a forzare la scadenza — e
falliva su una macchina appena avviata mentre sarebbe passato su una accesa
da più di dodici ore. Ora `_scaricato_a: float | None = None`, con il
controllo di freschezza esplicito.

**Due test uscivano davvero in rete.** `TestRicercaOnDemandFontiUfficiali`
sostituiva diligentemente `sources.http_get`, ma **`aer_catalog` e
`oppo_official` hanno un client `urllib` proprio e non ci passano**: ogni
ricerca contattava per davvero `androidenterprisepartners.withgoogle.com` e
`sgp-sow-cms.oppo.com`. Conseguenza:
`test_brand_senza_fonte_dedicata_degrada_pulitamente` passava con la rete e
falliva senza, cioè non verificava affatto quello che dichiarava di
verificare.

Aggiunta `aer_catalog.carica_da(voci)` per indicizzare un elenco già in mano
senza rete: prima l'unica via era riassegnare dall'esterno le variabili
interne di un altro modulo. I test ora partono dalla fixture registrata
(`tests/fixtures/aer_devices.json`) e l'asserzione è diventata specifica —
quale fonte ha risposto, e che **non millanta una versione**, che è il punto
delicato del catalogo AER.

### 2. «Nessun test tocca la rete» — verificato invece che ricordato

È l'errore n. 10 del documento precedente, e si era ripresentato. Il rimedio
non è ricordarsene meglio: `tests/test_niente_rete.py` **blocca il socket**
(`socket.create_connection` e `socket.socket.connect`) e fallisce dicendo
*quale indirizzo* un percorso stava per contattare.

Ha trovato subito il secondo caso (Oppo), che non stavo cercando. Un elenco
scritto a mano dei punti d'accesso alla rete invecchierebbe alla prima fonte
aggiunta; questo no.

Il file contiene tre verifiche:

- `search_model()` con gli agganci a posto **non apre nessuna connessione**;
- `run_scan()` con la rete assente **arriva in fondo** e lascia un errore
  leggibile per **ogni** fonte — e nessuna fonte si dichiara OK, che
  significherebbe star servendo una cache come dato fresco;
- le fonti singole restituiscono un errore invece di sollevarlo.

### 3. «Cosa è cambiato da quando l'ho testato» — il punto 3 delle cose rimaste

Era descritto così nel documento precedente: *«oggi l'app dice questo modello
è a questa versione; per il QA la domanda vera è cosa è cambiato dall'ultima
volta che ho testato»*. Ora c'è.

Nuovo modulo **`core/retest.py`** e tabella **`test_baseline`**. Si dichiara
«testato adesso», l'app fotografa lo stato software, e da lì in poi il
confronto è sempre fra quella fotografia e lo stato corrente:

| cambia | peso | azione suggerita |
|---|---|---|
| versione Android | MAJOR | retest completo |
| skin, cifra principale diversa (One UI 7 → 8) | MAJOR | retest completo |
| skin, stessa cifra (8.0 → 8.0.1) | FEATURE | smoke test |
| build | FEATURE | smoke test |
| livello di patch | SECURITY | nessuna azione salvo regressioni note |

Quando cambiano più campi insieme vince il più grave, non l'ultimo trovato.

In interfaccia: colonna «Da ritestare» e contatore nella scheda Dispositivi,
contatori + filtro «solo quelli cambiati dall'ultima prova» + comandi per
riga nel Parco di test, e un riquadro nella scheda del singolo dispositivo.

**Due regole che valeva la pena fissare nei test**, perché senza sono
esattamente il genere di cosa che rende inutile la funzione:

1. **Un campo che sparisce non è un aggiornamento.** Se la fotografia aveva
   una build e oggi il campo è vuoto, non è successo niente al telefono: è
   una fonte che non risponde più. Trattarlo come cambiamento avrebbe
   prodotto «da ritestare» su tutto il parco a ogni giornata storta di una
   fonte — e anche fra un `rebuild_if_logic_changed` e la prima scansione,
   quando i campi sono tutti vuoti per costruzione.
2. **Un telefono non torna indietro.** Se lo stato corrente dichiara una
   versione *inferiore* alla fotografia, il dato è sbagliato: viene
   etichettato `INCOERENTE` e **mostrato**, non risolto in silenzio. È il
   punto 4 delle cose rimaste («rifiuto di una versione che retrocede»,
   «disaccordo mostrato invece che nascosto»), applicato dove si vede.
   Sulla stringa di una build invece non si afferma nessuna regressione: il
   formato cambia fra generazioni e regioni, e un ordinamento alfabetico non
   descrive nessuna realtà.

`test_baseline` **non** viene toccata da `rebuild_if_logic_changed`: è un
dato inserito da una persona, non il risultato dell'interpretazione di una
fonte, e ricostruirlo è impossibile.

### 4. `app.py` aveva zero test — ora no

1400 righe di codice procedurale eseguito **all'importazione**: importare
`app` equivale a disegnare la pagina intera. Era anche l'unico file del
progetto senza una riga di copertura, e i suoi difetti si scoprivano su
Streamlit Cloud, cioè dopo il deploy. Un `KeyError` su una chiave rinominata
in `storage` fa pagina bianca, e la pagina bianca non dice quale chiave.

`tests/test_interfaccia.py` sostituisce `streamlit` con un finto che
registra le chiamate invece di disegnare, e verifica tre stati:

- **archivio vuoto** — il caso più delicato: mezza pagina non ha dati e ogni
  riquadro deve dirlo invece di rompersi;
- **archivio popolato con baseline** — i percorsi che l'archivio vuoto non
  attraversa mai (tabella dispositivi, parco, confronto);
- **dispositivo aggiornato dopo la baseline** — quello che si vedrà più
  spesso.

Non verifica l'aspetto: quello non si verifica così. Verifica che ogni
scheda si costruisca.

---

## Errori da non ripetere

I dieci precedenti restano validi. Se ne aggiungono due, entrambi emersi
da questa sessione:

11. **Un sentinel «scaduto» costruito su `time.monotonic()`.** `0.0` non è
    «tanto tempo fa»: è l'accensione della macchina. Per dire «mai» serve
    `None` e un confronto esplicito, o si scrive un test che passa o fallisce
    a seconda di da quanto è acceso il computer.

12. **Sostituire l'aggancio HTTP di un modulo credendo di averli coperti
    tutti.** `sources.http_get` non è l'unico: `aer_catalog` e
    `oppo_official` hanno client `urllib` propri, `_oxygen_get` ha uno User-
    Agent suo, `modelcodes`, `imeicheck`, `appledevices`, `images` e `backup`
    chiamano `requests` direttamente. Il modo di saperlo non è ricordarlo, è
    `tests/test_niente_rete.py`.

E la regola del documento precedente che continua a ripagare: **le fixture
sono risposte registrate dai servizi veri**, mai ricostruite a mano.

---

## Il repo — la trappola da conoscere

Invariata e ancora vera: **l'upload dal browser di GitHub salta i file e le
cartelle che iniziano con un punto** (`.github/workflows/scan.yml`,
`.gitignore`). Usare **GitHub Desktop**. Dopo il push, controllare la scheda
*Actions* e i secret `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID`.

---

## Cosa resta da fare

1. **Unificare i punti d'accesso alla rete.** Sono sparsi in otto moduli, tre
   con client propri. È la causa diretta dei due bug corretti in questa
   sessione, e li ho corretti due volte perché la causa è rimasta. Un solo
   `core/net.py` con `get` / `post_json`, e i test avrebbero **un** aggancio
   invece di sei. Non l'ho fatto di mia iniziativa perché tocca ogni fonte e
   le fonti sono tarate con precisione: va fatto con calma e una fonte alla
   volta, non in coda a un'altra modifica.

2. **Samsung FOTA su tutti i modelli** — chiuso in v21 (2332 codici dal
   dataset), ma vale la pena riverificarlo in produzione con un modello che
   non era nella vecchia tabella scritta a mano.

3. **Notifica sul retest.** Oggi la baseline si consulta aprendo l'app.
   Il passo naturale è che un dispositivo del parco che passa a «da
   ritestare» lo dica su Telegram, con il confronto già scritto nel
   messaggio — l'infrastruttura di notifica c'è già.

4. **Affidabilità, il resto del punto 4 di v20**: accordo fra fonti
   indipendenti *come segnale positivo* (oggi si sceglie la più fidata e
   basta), e rilevamento di degrado esteso ai campi vuoti, non solo al
   conteggio. La parte sulla versione che retrocede è fatta, ma solo nel
   confronto con la baseline: farla anche fra due fonti nello stesso momento
   è il pezzo che manca.

**Cosa NON fare**: aggiungere altre marche o fonti generiche. Invariato dal
documento precedente, e ancora più vero adesso che c'è una funzione in più
da mantenere.

---

## Nota sul 100%

Invariata rispetto a v20, e questa sessione ne aggiunge un corollario. Non è
ottenibile con fonti di terzi che cambiano formato senza preavviso. Quello
che si può fare: preferire il dato strutturato allo scrapato, etichettare il
tipo di dato (versione attuale / di fabbrica / indizio da notizia), e far sì
che un guasto sia **rumoroso** invece che silenzioso.

Il corollario: **anche i test devono essere rumorosi quando mentono**. Due
test verdi che passavano solo perché la rete rispondeva erano peggio di due
test rossi — perché un test creduto e sbagliato è un controllo che non c'è,
mentre uno rosso almeno si vede.
