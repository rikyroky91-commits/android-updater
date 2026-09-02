# Passaggio di consegne — 2 settembre 2026 (v72)

> Lettura di controllo dopo la v71: `memoria_mb 396,0 · picco 423,1`.
> Un'ora prima era 350,4 con picco 374,8.

## Cosa dice quella lettura

Due cose opposte, e vanno tenute separate.

**La buona.** `memoria` e `picco` sono numeri DIVERSI. Non era mai
successo: per giorni sono stati identici, ed era il sintomo del pavimento
che sale e non scende più. Adesso il processo tocca 423, torna a 396, e la
memoria viene davvero restituita al sistema. Il rilascio della v71
funziona.

**La cattiva.** Il pavimento sale lo stesso, più lentamente: +46 MB in
un'ora. A quel ritmo i 512 arrivano prima di sera, e il riavvio pure.

E i numeri per fase della v71 dicono dove sta il peso, che non è dove
avevo puntato io:

```
avvio               221,4
dopo la raccolta    328,4    ← +107 MB
dopo la scrittura   328,4
restituiti            0,0
dopo il salvataggio 349,5    ← +21 MB
```

**La raccolta costa 107 MB, il salvataggio 21.** Avevo lavorato sul
salvataggio: è il fratello piccolo. E `restituiti: 0,0` non è un guasto —
il salvataggio aveva già restituito la sua parte poche righe prima — ma
dice che di quei 107 MB, in quel momento, non c'era niente da buttare.

Parte di quei 107 sono cataloghi che restano per servire le ricerche, e si
vedono uno per uno:

```
codici modello 14,4 + indici inversi 25,7 = 40,1 MB
schede tecniche 20,8 · indice TAC 14,3 · archivio 14,8
```

I tre indici inversi di `modelcodes` costano quasi il doppio dell'indice
vero. È la previsione della v66 — «stessa forma di memoria che nell'indice
TAC è costata 112 MB» — adesso con un numero sopra.

## Cosa ho fatto, e cosa NON ho fatto

Non ho indovinato la causa della crescita. Ho fatto due cose: una che
**evita la conseguenza** subito, una che **rende la causa leggibile** al
prossimo giro.

### La valvola

`scan._libera_cataloghi_se_serve()`: a fine scansione, se la memoria supera
`MEMORIA_MASSIMA_MB` (420 di default su 512), i cataloghi si buttano —
indice TAC, codici modello, schede tecniche, processori, catalogo
aziendale — e si ricostruiscono alla prima richiesta che li cerca.

Non si perde nessun dato: sono cache, ognuna sa rifarsi da sola. Si perde
qualche secondo, una volta, per chi cerca subito dopo. L'alternativa è che
il contenitore venga ucciso, e allora si perde tutto quello che non è
ancora finito nel salvataggio esterno. **Una lentezza dichiarata è meglio
di un riavvio silenzioso.**

La soglia è una variabile d'ambiente: se 420 si rivelasse troppo alta o
troppo bassa si cambia da Render senza toccare il codice.

### Lo storico

`/health?dettaglio=1` risponde anche `storico_scansioni`: le ultime otto
scansioni con avvio, fine, MB restituiti e se la valvola è scattata.

Serve a distinguere due storie che oggi hanno lo stesso numero: «i
cataloghi si stanno ancora scaldando» — e allora il pavimento sale per
qualche giro e poi si ferma — e «ogni giro lascia qualcosa», che è un
problema diverso e si vede solo mettendo in fila più giri.

## Come si legge, la prossima volta

Apri `/health?dettaglio=1` e guarda `storico_scansioni`:

* se `avvio` **si assesta** dopo due o tre righe, era il riscaldamento:
  problema chiuso;
* se `avvio` **cresce a ogni riga**, ogni scansione lascia qualcosa, e i
  cataloghi da soli non lo spiegano: allora la prossima mossa è
  `core/modelcodes.py`, che vale 40 MB e ha la forma già corretta una
  volta nell'indice TAC;
* se compare `cataloghi buttati: true`, la valvola ha lavorato: il
  servizio è rimasto in piedi al posto di riavviarsi.

## Test

**1423, tutti verdi** (erano 1419). Quattro nuovi: sotto soglia non si
butta niente, sopra soglia i cataloghi se ne vanno davvero (e vengono
buttati, non svuotati a metà), lo storico tiene le ultime otto e non le
prime, e uno storico illeggibile in archivio non ferma la scansione — una
diagnosi non deve poter rompere il lavoro che diagnostica.
