# Passaggio di consegne — 2 settembre 2026 (v71)

> «risolviamo il fatto della memoria di picco troppo alta. il sito crasha
> di notte anche quando nessuno lo usa.»

Quel «anche quando nessuno lo usa» è l'indizio che ha risolto il caso: di
notte non ci sono visite, ma ci sono i lavori periodici — la scansione
ogni ora e il salvataggio dell'archivio ogni mezz'ora.

## La causa: la memoria si libera, ma non torna indietro

Provato con la sequenza esatta del salvataggio (database → gzip → base64
→ corpo della richiesta), su un archivio da 20 MB:

```
picco durante l'invio         43,6 MB
dopo `del` e `gc.collect()`   43,6 MB   ← non torna NIENTE
dopo `malloc_trim(0)`         10,4 MB
```

`gc.collect()` libera gli **oggetti** Python; non restituisce al sistema
operativo le **arene** che li contenevano. Per il kernel — e quindi per il
limite dei 512 MB di Render — il processo continua a occuparle.

È anche la spiegazione di una cosa che avevamo sotto gli occhi da giorni e
che avevo letto come una buona notizia: `memoria_mb` e `memoria_picco_mb`
erano **sempre identici**. Non era stabilità: era che il pavimento, una
volta alzato, non scendeva più. Ogni giro notturno che allocava un po' più
del precedente lo alzava ancora, e la mattina il servizio era ripartito.

## La correzione

`core/util.libera_memoria()`: `gc.collect()` seguito da `malloc_trim(0)`,
la chiamata di glibc che quel pavimento lo riabbassa davvero. Ritorna i MB
effettivamente restituiti, così chi la chiama può scriverlo invece di
sperare. Dove non c'è glibc (musl, macOS, Windows) fa il solo
`gc.collect()` e torna zero, senza rompere niente.

Chiamata nei tre punti che allocano tanto e poi non servono più:

* **fine di ogni scansione** (`core/scan.run_scan`),
* **fine di ogni salvataggio** (`core/backup.salva`),
* **fine del preriscaldamento dei cataloghi** (`web/main`), dove si
  scaricano e attraversano megabyte per tenerne poche centinaia di
  kilobyte.

In più, dentro `run_scan`, **le voci raccolte si lasciano andare PRIMA del
salvataggio**, non dopo: sono migliaia di dizionari con dentro i titoli
interi, e il salvataggio è il momento più caro della nottata. Tenerle vive
mentre l'archivio viene compresso e codificato sommava i due picchi invece
di alternarli.

## La misura, su tre giri di notte simulati

Archivio da 19,3 MB, una fonte che rende 4.000 voci, salvataggio a ogni
giro:

```
                  partenza   giro 1   giro 2   giro 3
con il rilascio     43,4      48,2     48,8     48,8
senza               43,2      85,0     50,8     51,4
```

Con il rilascio il processo si assesta e resta lì. Senza, il primo giro
lascia **37 MB in più** attaccati al processo — e in produzione, dove ogni
ora le fonti rendono quantità diverse, quel massimo viene rialzato di
continuo e non viene mai restituito.

## Una prova andata male, che resta scritta nel codice

Sembrava ovvio che costruire a mano il corpo JSON del salvataggio —
liberando la stringa base64 prima di spedire — costasse meno che lasciarlo
fare a `requests`. Misurato, campionando la memoria ogni 5 ms:

```
con `json=` (come era)          +35,6 MB di picco
con `data=` costruito a mano    +74,0 MB
```

Peggio del doppio. `requests` serializza in modo più parsimonioso, e il
`del` anticipato non recupera quello che il doppio passaggio
`dumps` → `encode` costa. Ho rimesso la riga com'era e lasciato il numero
nel commento, così nessuno rifà la stessa prova credendola nuova.

## E il modo di guardare, la prossima notte

`/health?dettaglio=1` ora risponde anche:

* `archivio_mb` — quanto pesa `tracker.db`, che è il moltiplicatore del
  salvataggio: ogni invio ne tiene in memoria la copia intera, quella
  compressa, quella in base64 e il corpo della richiesta;
* `ultima_scansione` — la memoria **fase per fase** dell'ultimo giro:
  all'avvio, dopo la raccolta, dopo la scrittura, quanti MB sono stati
  restituiti e dove si è assestata.

Se il servizio riparte ancora, quei numeri dicono in quale fase è successo
invece di lasciare un avvio nel registro e nessuna causa.

## Cosa NON è dimostrato

Che questo da solo basti. È dimostrato che la memoria torna al sistema e
che il pavimento smette di salire; il picco vero di produzione dipende
anche dai cataloghi (i 340 MB di base) e da quanto rendono le fonti vere,
che qui non sono raggiungibili. Il prossimo numero utile è
`/health?dettaglio=1` dopo una notte intera.

Resta in piedi la nota della v66: `core/modelcodes.py` ha la stessa forma
di memoria che nell'indice TAC è costata 112 MB — un dizionario di liste
più tre indici inversi — e in produzione indicizza anche la lista Google
Play. Se dopo questa notte i 340 MB di base non scendono, è lì che si
guarda.

## Test

**1419, tutti verdi** (erano 1417). Due nuovi, e misurano i megabyte, non
le chiamate: che la memoria restituita sia più della metà del picco (un
test che controllasse «è stato invocato `malloc_trim`» resterebbe verde
anche il giorno che non serve più), e che una scansione dichiari da sé
quanto è costata in ogni fase, anche in archivio.
