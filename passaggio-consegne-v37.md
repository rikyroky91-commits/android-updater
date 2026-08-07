# Mobile Update Tracker — passaggio consegne (v37)

- **569 test**, tutti verdi (erano 560).
- `DATA_LOGIC_VERSION` invariata: cambia la copertura del chip, non
  l'interpretazione dei dati in archivio.

---

## La CPU, finalmente dove si guarda

### 1. È una colonna della tabella dispositivi

Era il difetto più stupido e il più fastidioso: il chip veniva risolto
correttamente ma compariva **solo** nella scheda dispositivo e nel
riquadro di ricerca. Nella tabella — cioè dove si guarda — non c'era.

Ora è una colonna, accanto al modello: il processore è una proprietà del
telefono, non dell'aggiornamento, quindi sta con le colonne d'identità.

### 2. Un solo punto di risoluzione per tutta l'interfaccia

`chip_di()` prova le tracce dalla più precisa alla meno: codice modello,
poi numero di build (che per Samsung **comincia** col codice modello:
`A325F`XXSCDYB2), infine nome commerciale.

Tabella, scheda e ricerca ora passano tutte da lì, quindi **non possono
più dare risposte diverse sullo stesso telefono** — che era una delle cose
che facevano sembrare l'app inaffidabile.

### 3. Copertura oltre Samsung: il dataset esterno

La tabella scritta a mano non può coprire decine di migliaia di modelli.
Nessun dataset gratuito risolve *codice modello → chip* su tutta la fascia
media, ma ne esiste uno che risolve *nome commerciale → chip* per quasi
tutte le marche — e il progetto ha già la catena che porta dal codice al
nome (~70.000 codici). Messi in fila, coprono la gran parte delle ricerche
reali.

Scaricato una volta al mese e tenuto in cache: il chip di un modello non
cambia mai.

**Tre limiti, tutti noti e gestiti nel codice:**

1. **Indicizzato per nome commerciale**, quindi le varianti regionali
   dello stesso nome non si distinguono. Quando la cella contiene due chip
   (`Exynos 990 / Qualcomm SM8250`) **si dichiarano entrambi** e si dice
   che serve il codice esatto — sceglierne uno sarebbe una risposta
   sbagliata per metà dei telefoni.
2. **Fermo intorno al 2021**: sui modelli recenti non risponde. Per quelli
   vale la tabella curata.
3. **I valori sono letterali Python** (`b'Exynos 980'`): senza ripulirli,
   l'app si sarebbe riempita di chip chiamati «b'Exynos'». C'è un test
   sulla forma reale del file.

**Ordine delle fonti, che è la garanzia di correttezza:**
catalogo Play → **tabella curata** → dataset esterno.
La curata vince sul dataset perché è indicizzata per codice e quindi
distingue le varianti; il dataset copre dove la curata tace.

Si spegne con `SOC_DATASET_URL=""` se un domani la fonte sparisse o desse
dati sbagliati.

---

## Un difetto trovato scrivendo i test

`per_modello()` cercava per nome **solo** nel secondo argomento. Ma chi usa
l'app digita una cosa sola, e quella arriva come primo argomento anche
quando è un nome commerciale: «Redmi Note 10» digitato nella barra non
trovava niente pur essendo nel dataset. Ora si provano entrambi.

È la terza volta che questo progetto inciampa sulla stessa forma di
errore: una funzione che accetta due strade e ne guarda una sola.

---

## Errori da non ripetere

31. **Risolvere un dato e non mostrarlo dove l'utente guarda equivale a
    non averlo risolto.** Il chip era corretto da tre versioni e per
    Riccardo semplicemente non esisteva.

32. **Quando una funzione accetta più forme dello stesso input, deve
    provarle tutte.** Vale per i codici modello, per i nomi commerciali e
    per le grafie: è la causa ricorrente di metà delle segnalazioni.

---

## Cosa resta da fare

1. **Il doppione «Galaxy S24 Ultra» / «Samsung S24 Ultra».** Il
   riconoscimento della marca è corretto dalla v34, ma le due righe già in
   archivio non convergono da sole.
2. **Il filtro anti-rumore troppo permissivo**, che continua a creare
   dispositivi da notizie generiche.
3. **Verificare in produzione** che il dataset si scarichi davvero: URL e
   nome della colonna sono verificati, il download no — il container di
   sviluppo non ha rete. Se fallisce, l'app resta com'era e la Diagnostica
   lo dice.
