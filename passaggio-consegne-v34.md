# Mobile Update Tracker — passaggio consegne (v34)

- **547 test**, tutti verdi. **Ne arrivavano 4 rossi**: vedi sotto.
- **`DATA_LOGIC_VERSION` 25 → 26**: cambia il riconoscimento della marca,
  quindi le righe in archivio vanno rilette.

---

## Prima di tutto: la suite arrivava con 4 test rossi

`test_quattro_segnalazioni.py` faceva risolvere codici e nomi
**scaricando i dataset veri**. Passava solo su una macchina connessa e
falliva ovunque altro — in violazione della regola per cui nessun test
tocca la rete, che è una delle poche difese che questo progetto ha contro
i guasti silenziosi.

Il modulo `modelcodes` non aveva un punto d'innesto per seminare un
indice: senza, quella regola lì non era applicabile. Ora c'è
`modelcodes.carica_indice()` e i test usano un indice minimo di nove voci
reali. Girano in 0,7 secondi invece di dipendere dalla rete.

---

## Le tre segnalazioni

### 1. «samsung s24 ultra» non trova il SoC

La tabella conosceva solo la grafia **«Galaxy S24 Ultra»**. Ma nessuno
digita così, e nemmeno le fonti di notizie scrivono così: il nome arriva
ora con la marca davanti, ora senza la parola di gamma.

`soc.varianti_nome()` indicizza ogni nome sotto tutte le grafie in uso:
«Galaxy S24 Ultra» risponde anche a «S24 Ultra», «Samsung S24 Ultra» e
«Samsung Galaxy S24 Ultra». Vale per tutte le marche, con la gamma giusta
per ciascuna (Redmi→Xiaomi, Narzo→realme, Moto→Motorola).

### 2. Lo stesso telefono due volte, una sotto «Altri brand»

Nello screenshot: «S24 Ultra» sotto *Altri brand (Nothing, Umidigi,
Doogee…)* e «Samsung S24 Ultra» sotto Samsung. Due righe per lo stesso
telefono, ciascuna con metà della storia.

Causa: senza la parola «Galaxy», il riconoscimento della marca falliva e
il dispositivo finiva nella categoria residuale.

Ora le gamme **inequivocabilmente** Samsung sono riconosciute anche senza
«Galaxy»: `S24 Ultra`, `S23 FE`, `Note20`, `Z Fold`, `Z Flip`, `Tab S`.

**La serie A è esclusa di proposito**: «A15» è insieme un Galaxy A15 e un
OPPO A15, e indovinare lì sarebbe peggio che tacere.

### 3. L'IMEI `351355315430630` non trovato

La cifra di controllo **torna**: l'IMEI è formalmente valido, quindi il
problema non è il numero ma il database, che non conosce quel TAC
(`35135531`).

Nessun database TAC pubblico è completo: sono tutti alimentati dalla
community e ognuno ha buchi diversi. Ora se ne consultano **due**: la
seconda (Osmocom, storica) viene interrogata solo per i TAC che la prima
non ha. È vecchia e non aiuta sui modelli recenti, ma copre bene i TAC
storici — che è esattamente dove la prima è più debole.

Fallisce in silenzio di proposito: è un supplemento, e se non risponde
l'app deve continuare a identificare con la prima invece di smettere di
identificare del tutto.

**Non posso garantire che questo TAC specifico sia nella seconda base
dati**: il container di sviluppo non ha rete e non ho potuto verificarlo.
Se dopo il deploy resta non trovato, è un buco di copertura di entrambe le
fonti, e la strada successiva è una terza base dati.

---

## Errori da non ripetere

26. **Un test che dipende dalla rete non è un test: è un campione.** Passa
    dove c'è connessione e fallisce altrove, e nel frattempo non protegge
    niente.

27. **Indicizzare un nome con una sola grafia vuol dire non indicizzarlo.**
    Le persone e le fonti scrivono lo stesso telefono in quattro modi.

---

## Cosa resta da fare

1. **Copertura SoC di tutti i brand.** Resta il punto aperto: a mano non
   si fa, e nessun dataset gratuito e senza registrazione risolve codice
   modello → chip su tutta la fascia media. La strada è un caricatore che
   scarichi un dataset vero all'avvio, con gli URL **verificati prima** di
   scrivere il codice.
2. **Filtro anti-rumore troppo permissivo**: invariato.
3. **Verificare in produzione** lo User-Agent FOTA.
