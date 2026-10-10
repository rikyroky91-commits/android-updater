# Passaggio di consegne — 2 settembre 2026 (v73)

> «352643332782672 dice che trova il modello ma non me lo dà né la scheda
> tecnica.»

## La riga c'è, e il modello pure: lo buttavamo noi

```
MOTOROLA,35264333,"MOTOROLA, FOGO5G23"
```

Il primo campo di quella descrizione è **la marca**, non il nome
commerciale. `parse_specs` prendeva sempre il primo campo per nome, quindi
il modello diventava «Motorola»: la pagina dichiarava di aver riconosciuto
il telefono e poi mostrava il nome della marca, senza modello e senza
scheda tecnica — perché «Motorola» non è un telefono e nessun catalogo ha
una scheda per la parola «Motorola».

**Non è un caso isolato, ed è qui che la segnalazione diventa importante.**
Misurato sul file vero:

* **156.375 righe su 248.373** hanno il primo campo uguale alla marca;
* di queste, **156.373** hanno esattamente due campi;
* e **156.159** hanno la stessa identica struttura: `MARCA, MARCA MODELLO`.

Il modello, in tutte quelle righe, è scritto — nel secondo campo — e
veniva sostituito dal nome della marca:

```
INFINIX, INFINIX NOTE 50      il modello è «Note 50», un telefono del 2025
ZTE, ZTE BLADE V40 DESIGN     «Blade V40 Design»
SAMSUNG, SAMSUNG E1195        «E1195»
VIVO, Vivo Mobile vivo Y55    «Y55»
LG, SKT X SCREEN              «Skt X Screen» (qui la marca non si ripete)
```

Contava poco finché quelle righe stavano fuori dall'indice. Da quando si
cercano anche nei file (v67) sono **tutte** raggiungibili, e questo difetto
è diventato quello che si vede.

## La correzione

In `parse_specs`: quando il primo campo **è soltanto la marca**, il modello
si prende dalla coda, togliendo la marca ripetuta davanti.

Due dettagli che sembrano piccoli e non lo sono:

* **si taglia dall'ULTIMA occorrenza della marca**, non dalla prima:
  `Vivo Mobile vivo Y55` ha la ragione sociale in mezzo, e fermarsi alla
  prima lascerebbe «Mobile vivo Y55»;
* **«è la marca» non è «contiene la marca»**. Al primo tentativo avevo
  usato `_same_words`, che accetta un insieme di parole contenuto
  nell'altro: «OPPO A74» risultava uguale a «OPPO» e la regola si mangiava
  il nome di mezzo database — `OPPO A74, Oppo CPH2219` diventava
  «Cph2219». L'ho visto misurando subito dopo, prima di spedire, ed è il
  motivo per cui adesso c'è un test apposta.

E una sigla resta come l'hanno scritta: `prettify_model` trasformava
`FOGO5G23` in «Fogo5g23», che non è né il dato della fonte né un nome di
telefono — sembra un errore di battitura dell'app. Una parola sola con
dentro lettere e cifre è una sigla, e di una sigla si riporta la grafia
della fonte.

## Il tuo IMEI, adesso

Da «Motorola» a **«MOTOROLA FOGO5G23»**: il dato vero, quello che il
database dice davvero di quel TAC.

La scheda tecnica però resta vuota, e va detto perché: `FOGO5G23` è un
**nome in codice interno**, non un nome commerciale, e nessun catalogo lo
indicizza. Ho cercato: «fogo» è il codename Motorola del **moto g 5G** —
la pagina dispositivo di /e/ Foundation e il database DDDB lo legano a
XT2417 (moto g 5G 2024), un thread XDA parla di «Moto G 5G XT2417D FOGO».
Il «23» nella riga del database punta però al 2023, e le due cose non
tornano: **non lo scrivo come fatto**. Il progetto ha già in casa una
tabella di codename Motorola verificati (`MOTOROLA_LOLINET_DEVICES`, 40
voci, con `fogos` → G34 5G e `fogorow` → G24) e «fogo» semplice non c'è:
accostarlo a `fogos` sarebbe indovinare.

Se lo controlli su imei.info e mi dici che telefono è, diventa una riga in
`data/tac_modelli.csv` e da quel momento è riconosciuto subito, per
sempre.

## Test

**1428, tutti verdi** (erano 1423). Cinque nuovi: il modello che si prende
dalla coda, la ragione sociale in mezzo che non disturba, la coda tenuta
intera quando la marca non si ripete, la sigla che conserva la grafia
della fonte, e — il più importante — che un nome che *comincia* per marca
non venga toccato, con dentro i tre casi che la prima versione rompeva.
