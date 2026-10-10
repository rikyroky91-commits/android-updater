# Passaggio di consegne — 1 settembre 2026 (v69)

Richiesta: «controlla se il deploy è stato fatto e assicurati che ora va
bene».

## Il deploy c'è

GitHub è allineato: `45879f7` (oggi 13:52) più i due commit precedenti
contengono **esattamente** l'albero che avevo consegnato — ho confrontato
file per file con `git hash-object`, comprese le consegne v66/v67/v68 e il
file di test nuovo. Render ha distribuito: il sito risponde con il codice
nuovo, e si vede da `/health`, che ora riporta la memoria (riga aggiunta
dalla v66).

## I quattro IMEI, chiesti al sito vero

| IMEI | ora risponde |
|---|---|
| `862245059650208` | **vivo Y76 5G** · codice `V2124` · Dimensity 700 |
| `865587084948173` | **Honor 400 Pro (2025)** |
| `866068054131131` | **OPPO A74** · «Rete mobile: 4G · dalla scheda tecnica» |
| `356427134239214` | **Samsung Galaxy A06 4G** |

**CORREZIONE, scritta dopo dall'utente**: il Galaxy A06 **non** l'ha
risolto il servizio esterno — l'ha scritto lui a mano nel riquadro della
pagina, e il servizio esterno non funziona. Avevo dedotto la fonte
dall'esito invece di leggerla, ed è esattamente l'errore che questo
progetto evita ovunque: una risposta senza fonte dichiarata. Vedi la v70,
che parte da qui.

Ho verificato anche la strada nuova della v67 su un TAC volutamente fuori
dall'indice: `358850000000006` (TAC `35885000`) risponde **Nokia 6108**,
cercato riga per riga nei file. Prima era «modello sconosciuto».

## Una cosa da correggere l'ho trovata guardando

Il titolo diceva **«vivo Y76 5G 5G»**: il nome commerciale finisce già per
«5G» e la pastiglia lo ripeteva attaccato. Chi legge quel titolo la
risposta ce l'ha davanti, e ripeterla sembra un errore dell'app.

`rete_mobile` adesso dichiara `nel_nome`, e la pastiglia (con la sua riga
«Rete mobile: …») compare solo quando aggiunge qualcosa. Nella scheda
tecnica la voce «Rete» resta sempre: lì sta in una tabella di
caratteristiche, dove un valore si scrive anche quando è ovvio.

## E una che NON è a posto: la memoria

Qui la risposta onesta è «meglio, ma non tranquillo».

Misurato sul servizio vero, tre volte a qualche minuto di distanza:

```
memoria_mb 431.8 · memoria_picco_mb 431.8
```

Il numero è **fermo**, e picco uguale a corrente significa che da quando è
partito non ha mai avuto un momento peggiore: il picco da 268 MB
dell'indice TAC, quello che faceva riavviare il contenitore, non c'è più.
Ma 432 su 512 lascia 80 MB di margine, e non basta a dire «a posto».

**La causa non è più quella corretta.** L'indice TAC ora pesa 15,5 MB
misurati, i codici modello 2,2 più 3,5 di indici inversi: tutti i
cataloghi insieme, in locale, stanno in 23 MB. I 400 e passa MB di
produzione stanno da un'altra parte — i cataloghi che qui non si riescono
a scaricare (la lista Google Play, le 4.766 schede tecniche), l'archivio
con i suoi 914 dispositivi, il thread di scansione.

Invece di tirare a indovinare ho aggiunto il modo di saperlo:

    /health?dettaglio=1

risponde con la stessa riga di prima più `cataloghi_mb`, cioè quanto pesa
OGNI catalogo tenuto in memoria, contato voce per voce (non
`sys.getsizeof`, che su un dizionario di liste risponde il 5% del vero).
Il dettaglio si chiede con il parametro e non si calcola a ogni battito,
perché quella rotta la interroga l'host ogni minuto.

**Da fare dopo aver distribuito questo pacchetto**: apri
`android-updater.onrender.com/health?dettaglio=1` e mandami cosa risponde.
Da lì si vede quale catalogo occupa cosa, e la prossima correzione è
mirata invece che a tentativi. Il sospetto principale resta
`core/modelcodes.py`, che ha la stessa forma di memoria che nell'indice
TAC è costata 112 MB — un dizionario di liste più **tre** indici inversi —
e in produzione indicizza anche la lista Google Play, che qui non è
scaricabile.

## Test

**1408, tutti verdi.** Tre nuovi su `nel_nome`; uno esistente aggiornato:
la pagina del Galaxy A16 4G ora verifica che la pastiglia NON ci sia,
perché il nome lo dice già.
