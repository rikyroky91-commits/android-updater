# Mobile Update Tracker — passaggio consegne (v24)

Aggiorna e sostituisce `passaggio-consegne-v23.md`. Le parti non ripetute
qui (bug corretti, guard di rete, baseline di retest, test dell'interfaccia)
restano valide come scritte lì.

---

## Cos'è cambiato in questa sessione

Una cosa sola, ma è quella che mancava: **Oppo, OnePlus e realme moderni
adesso hanno un numero di build.**

- **378 test**, tutti verdi (erano 335). Nessuno tocca la rete.
- **`DATA_LOGIC_VERSION` resta 22.** Non è cambiato il modo in cui una
  fonte esistente viene interpretata: è stata aggiunta una fonte nuova.
  Incrementarla costerebbe la ricostruzione dell'archivio senza guadagno.

```bash
python -m unittest discover -s tests
```

---

## Il problema, detto per bene

«Cercando oppo a6x non trova firmware ma solo il modello» era una critica
giusta a un limite reale, ma la causa non era una regressione. Per Oppo,
OnePlus e realme **non esiste una fonte ufficiale interrogabile**, e in
`FONTI.md` ci sono le prove: 403, 404, un dominio che non esiste in DNS,
un portale di bug bounty senza versione per modello. L'archivio ufficiale
Oppo che funziona copre ~94 modelli fermi al 2021-22; l'A6x è del 2025.

Quello che restava era la versione **di fabbrica** — cioè, per un QA,
quasi niente.

---

## Cosa è stato fatto

### 1. Prima misurare, poi scrivere il parser

Il canale `t.me/s/oxygenos14update` era stato individuato nella sessione
precedente come possibile fonte, e la sessione si era chiusa **senza
integrarlo**, perché non se ne conosceva la copertura. Integrare una
fonte e scoprire dopo cosa non copre era già successo con l'archivio
Oppo.

Due pagine consecutive lette e contate (numeri in `FONTI.md`):

| | |
|---|---|
| rilasci confermati | **11**, su 11 codici modello distinti |
| di cui **senza nome del telefono** | **5** |
| post di versioni **previste** | 6 — da scartare |
| resto | rilanci da X, sondaggi, dirette |

**I due numeri che hanno deciso l'integrazione** sono il secondo e il
terzo, e vanno letti insieme.

Che metà dei rilasci arrivi **senza nome commerciale** (`Version :
CPH2613_16.0.3.500` e basta) altrove sarebbe un difetto fatale. Qui no:
`modelcodes` e il catalogo AER traducono già quel codice in un nome. Il
canale porta il firmware, il progetto ci mette l'identità. È il motivo
per cui questa fonte funziona *in questo progetto* e non funzionerebbe in
un altro.

Che sei post su quaranta siano previsioni è invece il rischio, ed è
**esattamente la trappola di Honor**: build ben formata, livello di patch,
tutto plausibile, e a smentirlo solo la prosa («subject to change as the
verification process is still ongoing»). Prenderla per versione attuale
sarebbe lo stesso errore, ripetuto a distanza di mesi.

### 2. `core/telegram_tracker.py` — parser, e basta

**Zero rete, di proposito.** Il modulo riceve HTML già scaricato e
restituisce dati: non importa `requests`, non apre socket. È l'errore
n. 12 del documento precedente (moduli con client HTTP propri che
sfuggono agli agganci dei test) applicato in partenza invece che corretto
dopo. Chi scarica è `sources.py`, che ha già il suo punto unico e
sostituibile.

Legge i **tre impaginati** che il canale usa contemporaneamente, incluso
quello Oppo col codice fra graffe e la versione su una riga separata.

Quattro difetti trovati alla prima passata sui messaggi veri, tutti con
un test che li fissa:

1. **`OnePlus 10T` diventava `OnePlus 10t`.** La normalizzazione del
   maiuscolo pieno (serve per `OPPO RENO 15` → `OPPO Reno 15`) non deve
   toccare i token con cifre: è lo stesso inciampo di `HONOR X8c`.
2. **`EX01` finiva nel campo regione.** È il canale di rilascio, non un
   luogo. Produceva dispositivi con «Regione: EX01».
3. **`14.0.0.2401` letto come versione della skin.** Distinzione che
   decide il peso di un retest: in `core/retest.py` un cambio di cifra
   principale della skin vale retest completo, un cambio di build vale
   smoke test. Sbagliarla faceva scattare il retest completo a **ogni
   patch mensile** — un allarme che suona sempre, cioè nessun allarme.
4. **Post multi-device.** Un messaggio elenca OnePlus 12 e OnePlus Open
   con build diverse: attribuirle entrambe al primo nome sarebbe peggio
   che non leggere il messaggio.

### 3. Il trust, che era il punto pericoloso

`scan._lookup_structured_for` etichettava **d'ufficio come STRUCTURED**
tutto ciò che usciva da `lookup_model_structured`. Era una scorciatoia
innocua finché lì dentro c'erano solo fonti ufficiali. Con un canale non
ufficiale nell'elenco sarebbe diventata la bugia peggiore: il trust è ciò
che decide chi vince quando due fonti dicono cose diverse sullo stesso
telefono, ed è già stato corretto una volta in `storage.get_devices()`.

Ora `RawItem` ha un campo `trust` opzionale e `StructuredLookup` ha il
suo, dichiarato. `None` significa «il predefinito», quindi nessuna fonte
esistente cambia comportamento — e c'è un test che lo verifica una per una.

**Nota di merito per chi legge il diff:** `trust` è stato messo **in coda**
ai campi di `StructuredLookup`, non in mezzo, perché `fetch` è passato
come quinto argomento *posizionale* in mezza dozzina di punti. Infilare un
campo prima di lui li avrebbe riassegnati tutti in silenzio, senza errori
di tipo. C'è un test anche per questo.

### 4. L'ordine delle fonti Oppo — è la tesi dell'aggiunta

1. se Oppo pubblica il firmware di quel modello, **vince Oppo**;
2. altrimenti una build reale da un canale dichiaratamente non ufficiale
   vale più della versione con cui il telefono è uscito di fabbrica;
3. e comunque il trust `CURATED` impedisce che sovrascriva un dato
   ufficiale già in archivio.

### 5. Dire *perché* manca, non solo *che* manca

Il fastidio non era il dato mancante: era che l'app non spiegasse la
differenza fra «non lo so» e «non è pubblicato da nessuna parte». Un
modello riconosciuto senza versione ora ha un riquadro che dice qual è il
limite di copertura di quella marca (`sources.nota_copertura`). Per chi fa
QA è un'informazione operativa: dice su quali marche non si può contare
per decidere un retest.

---

## Errori da non ripetere

I dodici precedenti restano validi. Se ne aggiungono due.

13. **Un campo nuovo in mezzo a una dataclass costruita per posizione.**
    I tipi combaciano, i test non se ne accorgono, e ogni chiamante ha
    silenziosamente un argomento in meno. In coda, o solo per nome.

14. **Adottare una fonte senza averne contato la copertura.** Vale sia in
    positivo (l'archivio Oppo: integrato, poi scoperto fermo al 2021) sia
    in negativo (questo canale: contato prima, e i numeri hanno cambiato
    il progetto del parser, non solo la decisione se usarlo).

E la regola che continua a ripagare: **le fixture sono risposte
registrate dai servizi veri**. Con un'eccezione dichiarata, sotto.

---

## Cosa resta da fare

1. **Confermare l'involucro HTML al primo giro in produzione.** I testi
   dei messaggi sono registrati dal canale vero; la struttura HTML della
   vista `/s/` è ricostruita, perché lo strumento con cui l'ho letta
   restituisce testo estratto e non HTML grezzo. **È l'unico pezzo del
   progetto non verificato su dati reali.** Il rischio è contenuto per
   costruzione — se l'involucro fosse sbagliato la fonte apparirebbe
   **rossa** in Diagnostica, non verde e vuota — ma va guardato.

2. **Unificare i punti d'accesso alla rete** (era il punto 1 del v23,
   invariato). Il nuovo modulo non peggiora la situazione: la sua rete sta
   già in `sources.py`.

3. **Sorvegliare la copertura del canale.** `telegram_tracker.copertura()`
   esiste per questo. Se scendesse a zero rilasci su più pagine, la fonte
   va **spenta**, non tollerata: una fonte che non porta niente e resta
   accesa è rumore in Diagnostica.

4. **Notifica sul retest** e **accordo fra fonti indipendenti**: invariati
   dal v23.

**Cosa NON fare**: aggiungere altre marche o fonti generiche. Invariato.

---

## Il repo — la trappola da conoscere

Invariata: **l'upload dal browser di GitHub salta i file e le cartelle che
iniziano con un punto**. Usare **GitHub Desktop**. I CRLF di `app.py` sono
intatti (1447, nessuna riga con solo LF).
