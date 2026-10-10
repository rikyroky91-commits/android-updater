# Passaggio di consegne — 31 agosto 2026 (v67)

> Segue la v66, che è già in produzione: l'ho verificato leggendo la riga
> di stato del sito vero, che riporta i conteggi nella forma nuova.

Segnalazione: «trovare gli imei sta diventando difficile. su due imei non
ne ha trovato neanche uno neanche con il secondo database —
`865587084948173`, `356427134239214`».

## Il primo IMEI: la base dati lo conosce benissimo

Riga nel database principale, presente adesso:

```
HONOR,86558708,"HONOR 400 PRO, N/A2025"
```

E il sito, interrogato sullo stesso numero, rispondeva «IMEI a 15 cifre,
modello sconosciuto · Nessuna delle basi dati locali conosce il TAC
86558708».

**Due difetti sovrapposti, e il secondo è quello grosso.**

### Difetto 1 — l'anno attaccato a una parola corta

Quando il dataset non ha un codice modello scrive `N/A`, e ci attacca
l'anno: `N/A2025`. `_unglue_year` separa un anno incollato solo se davanti
ha almeno cinque caratteri — regola giusta, serve a non spezzare `CPH2019`
(un codice OPPO) in «CPH» del 2019 — e `N/A` ne ha tre. Nessun codice,
nessun anno visto, riga fuori dall'indice.

Colpiva **esattamente i modelli appena usciti**, perché sono quelli per cui
il dataset non ha ancora il codice: HONOR 400 Pro, REDMI 15, REDMI A5,
REDMI Note 15, Pixel 7a, i Tecno. È il motivo per cui il problema
«peggiorava»: più il telefono è nuovo, più era probabile che sparisse.

Corretto con una regola larga che vive **solo** dentro `_dell_era_android`,
cioè solo dopo che nessun codice è stato riconosciuto, e che pretende che
l'anno chiuda la parola (così `BD202403` non diventa il 2024).
`_unglue_year`, che serve a estrarre i codici, resta stretta com'era.

**1.810 righe recuperate**, misurate sul file vero: l'indice passa da
77.567 a 79.380 TAC.

### Difetto 2 — «fuori dall'indice» voleva dire «perduto»

Questo è il difetto vero, e la v66 non l'aveva toccato.

L'indice tiene la sola era Android: **216.617 righe scartate su 248.373**,
misurate in produzione. Finora quelle righe erano semplicemente perse. Un
dato che sta in un file dentro l'applicazione, e a cui l'applicazione
risponde «non lo so», non è un buco di copertura: è un dato buttato.

Il filtro però serve davvero — è il motivo per cui l'indice sta in 22 MB
invece che in 70. La via d'uscita è smettere di trattare «in memoria» e
«disponibile» come la stessa cosa:

* l'**indice** è la via veloce, per l'era che interessa quasi sempre;
* il **file** è la via lenta, per tutto il resto — e non costa memoria.

Misurato: scorrere le 248.373 righe cercando UN TAC costa **0,2-0,6
secondi**, e in memoria **niente di permanente** — i byte del file
arrivano dall'archivio, si leggono in flusso e si lasciano andare. Il
primo giro fa salire l'RSS di ~8 MB (è lo spazio che Python prende per il
file da 12 MB); i giri successivi lo riusano e non aggiungono niente.
Misurato su un processo appena nato: 31,3 → 39,6 MB al primo, 34,5 al
secondo.

Si paga solo quando l'indice non sa rispondere — cioè proprio nel caso in
cui prima si rispondeva «non lo so» — e **prima** di spendere una delle
cento interrogazioni mensili del servizio esterno.

`_seconda_lettura(tac)` fa questo, su tutte e tre le basi dati, con una
memoria dei risultati (anche dei «non c'è») da 512 voci: una pagina sola
interroga quella strada più volte — identità, confronto fra le fonti,
secondo tempo della ricerca — e rileggere i file a ogni giro trasformerebbe
una correzione in un rallentamento. `reset_cache()` la azzera, perché
`/tac/salva` deve poter smentire un «non c'è» ricordato prima.

**Verifica**: 12 TAC presi a caso fra i 169.025 fuori dall'indice — un
Nokia 6108, un HTC Desire, un iPhone 5s, un LG, un Samsung SGH — trovati
12 su 12. La copertura passa da ~79.000 TAC a **~248.000** senza niente di
permanente in memoria.

E il primo IMEI della segnalazione, chiesto al sito avviato in locale,
risponde: **Honor 400 Pro**.

La riga di stato lo dice adesso: «… fuori dall'indice perché anteriori ad
Android 8 e senza codice modello — restano cercabili nei file, una riga
alla volta». Prima diceva «scartati», che faceva sembrare normale non
rispondere.

## Il secondo IMEI: quello non lo sa nessuno

`356427134239214` → TAC `35642713`. Cercato riga per riga in tutte e tre
le basi dati: **non c'è**. Nemmeno il vicinato aiuta, ed è la stessa
conclusione del 26 agosto sul TAC Samsung: `35642714` è un Galaxy A21s,
`35642710` un iPhone XR, `35642711` un TEX T400 — marche diverse nello
stesso prefisso, quindi non si deduce niente senza indovinare.

Qui la risposta giusta resta quella che l'app dà già: dirlo, offrire i link
di verifica esterni (imei.info conosce TAC che le basi gratuite non hanno)
e il riquadro per scrivere il modello a mano, che dalla v65 sta in chiaro e
non più dentro un pannello chiuso. Se lo cerchi su imei.info e mi dici che
telefono è, lo aggiungo a `data/tac_modelli.csv` e da quel momento è
riconosciuto subito, per sempre, senza nessuna chiamata esterna.

## Test

`tests/test_memoria_e_variante.py`, 28 test (erano 19): 9 nuovi su questa
segnalazione — l'anno attaccato a `N/A`, a un nome (`Pixel 7a2023`), il
freno su `BD202403`, `CPH2019` che non si spezza, la riga scartata che
risponde lo stesso, il TAC inesistente che resta un no, i file che non si
rileggono a ogni domanda, `reset_cache` che cancella il ricordo del no.

Un test esistente **diceva il contrario** e andava cambiato:
`test_una_voce_senza_anno_ne_codice_non_entra_nell_indice` verificava che
una riga fuori dall'indice non rispondesse — ed era giusto così finché
«fuori dall'indice» e «non risponde» erano la stessa cosa. Ora verifica
quello che resta vero: quella riga non sta in memoria, ma risponde.

Suite completa: nessun fallimento nuovo. Resta il solo rosso preesistente
(`M1910F4G` → «Redmi Note 10 EEA» invece di «Mi Note 10»), che era rosso
anche prima della v66.

## Cosa resta

1. **Applicare e distribuire** (la v66 lo è già).
2. **Il secondo IMEI**: serve un nome da una fonte esterna, poi diventa una
   riga in `data/tac_modelli.csv`.
3. Resta in piedi la nota della v66 su `core/modelcodes.py`, che ha la
   stessa forma di memoria che nell'indice TAC è costata 112 MB.
