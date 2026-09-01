# Passaggio di consegne — 31 agosto 2026 (v66)

Tre segnalazioni, tutte e tre riprodotte prima di essere toccate.

1. «il sito continua a crashare continuamente per saturamento della
   memoria»
2. «cercando 866068054131131 mi trova l'oppo f19 invece dell'a74 che è
   quello venduto in europa»
3. «ho bisogno di sapere nei risultati se è 4g o 5g»

---

## 1. La memoria: 165 MB tenuti per 3,6 MB di dati

### Che cosa ho misurato

Non ho ipotizzato niente: ho caricato i cataloghi veri e guardato
`/proc/self/statm` passo per passo. Sul database TAC vero (248.359 righe,
77.567 TAC tenuti dopo il filtro «era Android»):

| passo | RSS | picco |
|---|---|---|
| import dei moduli | 57,9 MB | 57,9 MB |
| costruzione dell'indice TAC | **165,6 MB** | **216,9 MB** |

Il dettaglio del secondo passo, misurato pezzo per pezzo:

* lettura dei byte dall'archivio  +19 MB
* `.decode()` del testo intero    +11 MB
* dizionario delle 248.359 righe  +50 MB, con un **picco di +106**
* indice finale (liste di tuple)  +47 MB

**E il dato utile sono 3,6 MB.** Tutto il resto era la forma in cui lo si
teneva: un `dict[str, list[tuple[str, str, str]]]` paga quattro oggetti
Python per ogni risposta di ogni fonte, e ogni oggetto costa più del testo
che contiene. In più i tre dizionari delle tre basi dati erano vivi tutti
insieme mentre si copiavano nell'indice — è quell'attimo che faceva
toccare i 217 MB.

Su un piano da 512 MB, con gli altri cataloghi e il thread di scansione
nello stesso processo, quel picco è il riavvio per OOM. E si ripete a ogni
avvio, perché l'indice si ricostruisce da capo: il piano gratuito di
Render si addormenta e si risveglia di continuo.

Una scoperta laterale, con il suo numero: **`import openpyxl` costa 26 MB**,
e serviva a un ripiego — leggere il foglio di calcolo se il CSV della base
dati sparisse — che non è mai stato usato.

### Che cosa ho cambiato

**`core/imeicheck.py`**, ed è tutto lì dentro.

* **I CSV si leggono una riga alla volta.** Nuovi `_flusso_di_testo`,
  `_righe_principali`, `_righe_imeidb`, `_righe_osmocom`: niente più testo
  intero decodificato in memoria, niente più dizionario per fonte. Le
  vecchie funzioni che restituivano dizionari (`carica_tac_osmocom`,
  `carica_tac_imeidb`, `_leggi_csv_tac`, `_indice_fallback`) esistono
  ancora e ora poggiano sugli stessi lettori — una sola interpretazione
  per file, non due.
* **`_indice_principale` e `_indice_imeidb` sono state tolte**: la loro
  catena di ripieghi (CSV → foglio di calcolo → copia nel repository) vive
  ora dentro `_voci_principali`, e tenerne due copie voleva dire due
  versioni che prima o poi smettono di somigliarsi.
* **L'indice tiene una stringa per TAC**, non una lista di tuple: le tre
  parti di una risposta separate da `\x1f`, le risposte fra loro da
  `\x1e`. Si srotolano in `_voci_dalla_cella`, cioè per il TAC che
  qualcuno ha cercato, non per i 77.000 che nessuno cercherà. La funzione
  accetta anche la vecchia forma a liste, così un `_build_index`
  sostituito da una prova continua a funzionare.
* **L'ordinamento per affidabilità è rimandato alla lettura.** Il
  punteggio di una risposta dipende solo dalle altre risposte dello stesso
  TAC, quindi calcolarlo per tutti all'avvio dava lo stesso risultato di
  calcolarlo per quello cercato — pagando 77.000 ordinamenti e altrettanti
  insiemi di parole che nessuno guardava.
* **`openpyxl` si importa al primo uso** (`_openpyxl()`), non all'avvio.

**`core/backup.py`** — `salva()` teneva il database in chiaro in memoria
per tutta la durata del caricamento, mentre accanto crescevano la copia
base64 e il corpo JSON della richiesta: tre copie dello stesso archivio
nello stesso momento, ogni mezz'ora. Ora `grezzo` si libera appena
compresso.

**`core/util.py` + `/health` + Diagnostica** — `memoria_mb()` e
`memoria_picco_mb()`. Esistono perché il difetto era invisibile: su Render
un riavvio per memoria esaurita non lascia altro segno che un avvio nel
registro. Ora `/health` risponde anche `memoria_mb` e `memoria_picco_mb`,
e la Diagnostica ha la riga «Memoria del processo». Il picco conta più del
valore corrente: a far riavviare il contenitore è l'istante peggiore.

### Il risultato, misurato sullo stesso identico giro

Due processi uvicorn, stesso archivio, stessa ricerca per IMEI:

| | RSS | picco |
|---|---|---|
| prima (HEAD `f9c9a21`) | 230,9 MB | 267,7 MB |
| dopo | **168,6 MB** | **168,6 MB** |

**62 MB in meno tenuti, 99 MB in meno di picco** — e il picco sparisce del
tutto: 168 stabili contro 168 di massimo, cioè non c'è più nessun momento
in cui l'applicazione costa più di quanto costi normalmente.

In produzione il margine guadagnato è maggiore di così, perché qui due
cataloghi (Google Play e le schede tecniche) non erano scaricabili e sul
sito vero occupano anche loro.

---

## 2. «Oppo F19» al posto di «OPPO A74»

### La causa, che non era dove sembrava

Il database TAC risponde **giusto**: per il TAC `86606805` dice
`OPPO A74, Oppo CPH2219`. Anche `nome_canonico("CPH2219")` risponde
giusto: «OPPO A74». L'app aveva la risposta esatta in mano e la buttava
all'ultimo passo.

In `web/main._ancora_esito_imei` c'è un commento che dice, per esteso, che
il titolo della scheda tecnica **non** deve vincere sul nome canonico del
codice. Il codice sotto assegnava `modello = titolo_scheda` senza guardare
niente. Il catalogo GSMArena indicizza `CPH2219` come «Oppo F19» — la
grafia indiana — e quello finiva sul titolo della pagina.

Il commento c'era, la regola no.

### Che cosa ho cambiato

* **`core/modelcodes.stesso_telefono(a, b)`** — la stessa regola di
  famiglia che `nome_canonico` usa già per scegliere fra i nomi di un
  codice, ora esposta perché serve anche fuori. Distingue le due cose che
  si somigliano:
  * «Galaxy A16» → «Galaxy A16 4G» — la scheda **completa la grafia**, e
    deve vincere (è il caso che aveva motivato la regola originale);
  * «OPPO A74» → «Oppo F19» — la scheda **cambia nome di mercato**, e non
    è affare suo.
* **`web/main._ancora_esito_imei`** applica quella distinzione, e allinea
  anche il titolo della scheda al nome mostrato: la pagina di un
  dispositivo in archivio mostra quel titolo, e sarebbe tornata a dire
  «Oppo F19» sotto un «OPPO A74».
* **La stessa regola nella condizione «cambia davvero telefono»** della
  riga curata, poco sotto. Era un confronto secco fra stringhe, e con la
  riga nuova accorciava «OPPO A74 4G» in «OPPO A74»: la regressione che
  quella condizione era nata per evitare, rientrata da un'altra porta. Se
  ne è accorto un test, non io.
* **`data/nomi_modello.csv`**: riga `CPH2219 → OPPO A74`. Verificato:
  PhoneDB e DeviceAtlas elencano quel codice come «F19 / A74»,
  `oppo.com/np` vende l'F19, Wikipedia e GSMArena documentano l'A74. La
  riga non inventa niente — `nome_canonico` la applica solo se quel nome è
  già fra quelli che il dataset conosce per quel codice.

---

## 3. 4G o 5G nei risultati

Non è un dettaglio da scheda tecnica: A54 4G e A54 5G montano chip
diversi, ricevono build diverse e si aggiornano in date diverse. Provare
l'uno non dice niente sull'altro — che è esattamente la domanda a cui
questo progetto serve a rispondere.

**`web/presenters.rete_mobile()`**, con due sole fonti e in quest'ordine:

1. il **nome del modello** o la riga grezza del database TAC, quando la
   variante è scritta lì dentro («Galaxy A16 4G», «SAMSUNG GALAXY A54 5G,
   SM-A546B»). È il segnale più forte: viene dal codice esatto, che è
   quello che il TAC identifica;
2. la riga **«Network → Technology»** della scheda tecnica: «GSM / HSPA /
   LTE / 5G».

Se nessuna delle due parla, la risposta è «non dichiarato», scritto così.
Dedurlo dal processore sarebbe la scorciatoia sbagliata: quasi tutti i SoC
recenti hanno un modem 5G che il produttore può lasciare spento, ed è
proprio il caso in cui esiste una variante 4G.

Dove si vede: una pastiglia accanto al nome del modello nei risultati
(anche durante l'attesa del firmware, perché il modello lì è già
definitivo), la riga «Rete mobile: 4G · dal nome del modello» sotto, e una
voce «Rete» nella griglia della scheda tecnica — che è il punto in cui la
vede anche chi arriva dalla pagina di un dispositivo in archivio. Il
valore si calcola **una volta sola** (`web/main._con_rete`) e i due punti
leggono lo stesso: due punti che calcolano lo stesso dato per conto loro,
in questo progetto, sono due punti che prima o poi dicono cose diverse.

---

## Verifica

Suite completa, stesso ambiente, prima e dopo:

* base (HEAD `f9c9a21`): **1371 test, 1 fallimento**
* dopo: **1390 test, 1 fallimento** — lo stesso, non uno nuovo

Il fallimento preesistente è
`test_nome_e_codice.py::test_il_ripiego_per_i_codici_sconosciuti_resta`:
`M1910F4G` (Xiaomi Mi Note 10) risolve a «Redmi Note 10 EEA». È rosso
anche sul repository intatto, non l'ho toccato — ma è la stessa famiglia
di difetti degli altri due, e merita un giro suo.

I 19 test nuovi stanno in `tests/test_memoria_e_variante.py`. Due girano
in un **processo separato**, e non è una complicazione gratuita: il picco
di memoria (`VmHWM`) è un dato del processo e non si azzera, quindi dentro
la suite misurerebbe il test più affamato girato prima; e `openpyxl`, una
volta importato da un altro file, resta in `sys.modules` per sempre.

Il test della memoria misura i **megabyte**, non il codice. Un test che
controllasse «esiste il generatore» tornerebbe verde anche se qualcuno
domani ci rimettesse dentro un dizionario intermedio.

---

## Cosa resta

1. **Applicare il pacchetto e fare il deploy.** Vale l'avvertenza di
   sempre: da qui non ho accesso né a `git push` né a Render, e più volte
   una correzione è sembrata non funzionare solo perché lo zip non era
   ancora stato applicato.
2. **Il prossimo grosso consumatore di memoria è `core/modelcodes.py`.**
   Ha la stessa forma che qui è costata 112 MB — `dict[str, list[str]]`
   più **tre** indici inversi costruiti su richiesta — e in produzione
   indicizza anche la lista Google Play, che qui non era scaricabile.
   Merita la stessa misura e, se i numeri lo confermano, lo stesso
   trattamento. Non l'ho toccato in questo giro: quella è la logica dei
   nomi, cioè il cuore dell'app, e non si riscrive nella stessa sessione
   in cui si riscrive l'indice TAC.
3. **Guardare `/health` dopo il deploy.** Ora dice `memoria_mb` e
   `memoria_picco_mb`: se il picco resta lontano dai 512 per qualche
   giorno, la questione è chiusa; se ci torna vicino, il numero dice quando
   e da lì si parte, invece di ripartire da «ogni tanto va giù».
