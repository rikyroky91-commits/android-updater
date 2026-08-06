# Mobile Update Tracker — passaggio consegne (v34)

Aggiorna `passaggio-consegne-v32.md`.

- **533 test**, tutti verdi (erano 511 con **2 rossi già prima** di questa sessione).
- `DATA_LOGIC_VERSION` **25**: la versione riportata per i Samsung cambia,
  quindi l'archivio va ricostruito.

---

## Quattro segnalazioni, quattro cause diverse

Erano tutte vere, e nessuna aveva la causa che sembrava.

### 1. «Non becca la versione di Android» — la beccava SBAGLIATA

Il controllo versione Samsung prendeva **la prima regione che rispondeva**.
Per `SM-A325F` la prima della lista, `EUX`, è ferma ad **Android 11**;
tredici altre regioni danno **Android 13**. L'app dichiarava quindi Android
11 per un telefono aggiornato ad Android 13, con l'aria del dato ufficiale.

Ora interroga otto regioni in parallelo e **confronta**: prima la versione
di Android, poi la data codificata nelle ultime tre lettere del PDA
(`A325FXXSCDYB2` → `YB2` = 2025, febbraio).

### 2. «Cambia risultato in base a come scrivo» — due lacune distinte

* **Codice incompleto.** `a325` diventava `SM-A325`, che nel dataset non
  esiste: ci sono `SM-A325F`, `SM-A325M`, `SM-A325N`, perché l'ultima
  lettera è il mercato. La ricerca falliva **a un carattere dal dato**.
* **Sigla senza gamma.** `a32` e `samsung a32` non erano né codice (due
  cifre sono troppo poche) né nome (il catalogo lo chiama «Galaxy A32»).

E un terzo difetto sopra i due: la marca si deduceva **solo dal testo
digitato**. `a32` non rivela il produttore, quindi la fonte Samsung — che è
costosa e parte solo a marca nota — non veniva mai interrogata, anche dopo
che l'espansione aveva riconosciuto il modello. Ora la marca si deduce anche
dalle forme espanse.

Sei scritture, una risposta:

```
a32 · a325 · samsung a32 · SM-A325F · Galaxy A32 · galaxy a32
   -> Galaxy A32 · Android 13 · SoC MediaTek Helio G80
galaxy a32 5g -> Galaxy A32 5G   (la variante resta distinta)
```

### 3. «Non trova la CPU» — la trovava e poi la buttava

Il chip veniva allegato **solo** nel ripiego «codice riconosciuto ma nessun
firmware». Bastava che una fonte rispondesse — cioè il caso migliore —
perché sparisse dalla scheda. Ora si allega a ogni risultato strutturato, e
si prova anche a ricavarlo dal numero di build.

Resta il limite dichiarato nel v32: `data/soc_modelli.csv` è curato a mano
(134 voci). **Novità sgradita: GSMArena non è più utilizzabile** — risponde
con una pagina di verifica anti-bot Cloudflare. Non si aggira. Quindi non è
una fonte candidata per il SoC, e la sua utilità come ripiego per la
versione di fabbrica va riverificata.

Wikipedia è stata valutata come fonte SoC: copertura ampia, ma la ricerca
sbaglia pagina (cercando `Galaxy M15` restituisce l'**A15**) e il campo
mescola le varianti regionali (`S24` elenca Snapdragon *e* Exynos). Usabile
solo con guardie strette — titolo che combacia e valore privo di markup di
variante. Non implementata: è il primo candidato per il prossimo giro.

### 4. «Non sempre trova l'IMEI» — trovava il TAC e perdeva il codice

Il database TAC contiene il **codice esatto**:
`SAMSUNG GALAXY S26 ULTRA, Samsung SM-S948B`. `parse_specs` lo estrae già,
ma l'interfaccia usava il **nome commerciale** — ambiguo fra le varianti di
mercato e restituito in forme incoerenti (ora `Galaxy S26 Ultra`, ora
`Samsung Galaxy S26 Ultra`).

Ora si cerca per codice quando c'è. È la differenza fra «trova qualcosa» e
«trova quel telefono»: da un IMEI si arriva a `SM-A566B` e quindi a
firmware **e** chip.

---

## I due test rossi che c'erano già

1. **`test_arriva_anche_il_chip`** falliva davvero: è il difetto 3.
2. **`test_brand_senza_fonte_dedicata_degrada_pulitamente`** passava da solo
   e falliva nella suite. Motivo: pretendeva che a rispondere fosse il
   catalogo AER, ma **OnePlus ha ora un tracker ARB dedicato** che risponde
   per primo. Il test difendeva il mondo vecchio. Ora asserisce il
   comportamento (il modello è riconosciuto, nessuno inventa una versione)
   e non quale fonte vince.

---

## Errori da non ripetere

I venticinque precedenti restano validi.

26. **Prendere la prima risposta invece della migliore.** Vale ovunque ci
    siano più fonti equivalenti: la prima che risponde non è la più
    aggiornata, e sceglierla produce un dato *sbagliato* — molto peggio di
    un dato assente, perché non si nota.

27. **Un test legato a QUALE fonte vince si rompe quando la copertura
    migliora.** Asserire il comportamento, non il vincitore.

28. **Dedurre la marca solo dal testo digitato.** Se l'espansione riconosce
    il modello, la marca va ridedotta da lì: altrimenti le fonti costose
    restano fuori proprio nei casi in cui servirebbero.

---

## Cosa resta da fare

1. **SoC oltre le 134 voci curate.** Wikipedia con guardie strette (sopra).
   GSMArena è fuori gioco.
2. **Il tracker ARB restituisce 5 voci identiche** per OnePlus 12: da
   deduplicare.
3. **Filtro anti-rumore troppo permissivo** — invariato dal v31.
4. **Identità unica per dispositivo** — invariato dal v30.

## Il repo

**GitHub Desktop.** Ci sono `.github/`, `.streamlit/` e `data/`.


---

## Secondo giro: le forme viste negli screenshot

Segnalazione: «samsung a235» e «oppo a96» non davano risultati pur essendo
nomi e codici veri.

### «samsung a235» — la marca nascondeva il codice

`a235` funzionava, `samsung a235` no: con la parola davanti il testo non ha
più la forma di un codice e non veniva riconosciuto. Il codice ora si cerca
anche sul testo **senza marca**.

E si smette di inventare nomi: tre cifre sono già la radice di un codice
(`a235` → `SM-A235F`), non un nome commerciale. Veniva prodotto un
«Galaxy A235» inesistente che per giunta **prendeva il posto**
dell'espansione del codice, che invece funziona.

### «oppo a96» — la gamma era cablata a Galaxy

L'errore peggiore di questa sessione, e mio: `_nomi_da_sigla_corta`
attribuiva la gamma «Galaxy» a **qualunque** marca. «oppo a96» diventava
«Galaxy A96», un telefono che non esiste, e la ricerca non poteva che
fallire. Ora la gamma segue la marca scritta (`OPPO`, `realme`, `vivo`,
`HONOR`, `Redmi`, `POCO`, `OnePlus`, `iQOO`); senza marca si provano più
gamme, perché una sigla da sola non dice di chi sia e indovinarne una sola
fa fallire ricerche che avrebbero successo.

### Il nome commerciale valeva meno del codice

`CPH2333` rispondeva «OPPO A96 riconosciuto», `oppo a96` non rispondeva
niente: stessa domanda, stesso telefono, e la forma muta era quella più
naturale. Il riconoscimento ora parte anche dai **nomi**, risolti a codici
con il dataset che già faceva il percorso inverso.

### Riconosciuto e invisibile insieme

Un item con modello ma senza marca deducibile veniva mostrato sotto «Altri
brand» e **restava senza `device_key`**: compariva nella ricerca e non
entrava mai nella lista dispositivi. Ora la chiave si costruisce sulla marca
effettivamente mostrata — ma **solo per le fonti strutturate**, che il
modello lo hanno verificato: farlo anche per le notizie moltiplicherebbe i
dispositivi fantasma, che restano un problema aperto.

## Errori da non ripetere (seguito)

29. **Cablare una gamma per tutte le marche.** «Galaxy» per Oppo produce un
    modello inesistente: non una ricerca a vuoto, un dato inventato.
30. **Trattare una radice di codice come un nome.** Tre cifre dopo la
    lettera sono un codice; inventarci sopra un nome commerciale toglie
    anche il posto all'espansione che avrebbe funzionato.
31. **Far valere il codice più del nome.** Se il dataset sa andare da nome a
    codice, le due forme devono avere la stessa risposta.

---

## Terzo giro: strutturale, non per-modello

Domanda: «hai risolto solo i modelli degli screenshot o a livello
strutturale?». Verificato su modelli **mai toccati**, quattro forme
ciascuno: **22 forme su 22** risolte (Samsung A15/M34/S23, OPPO A58,
realme C53, vivo Y27, HONOR X7b).

La misura ha però fatto emergere un difetto che nessuno aveva segnalato.

### Una sigla senza marca è ambigua, e veniva risolta in silenzio

`a15` è insieme un **OPPO A15** e un **Galaxy A15**: esistono entrambi.
L'app rispondeva «OPPO A15, patch 2022-04» — il più vecchio dei due — senza
mai interrogare Samsung e senza dire che stava scegliendo.

Due cause sovrapposte:

1. la ricerca si ferma alla prima fonte che ha una versione, e l'ordine
   delle fonti è per **costo**, non per pertinenza;
2. la marca dedotta era una sola (Oppo), e questo **escludeva** il controllo
   versione Samsung, che è costoso e parte solo a marca corrispondente.

Ora, quando la marca non è scritta e il testo non è un codice, si uniscono
gli ordini di tutte le marche implicate dalle forme espanse e si
restituiscono **tutti i dispositivi distinti** trovati. Con la marca scritta
o con un codice il comportamento è invariato: una domanda precisa merita una
risposta sola.

```
a15         -> Galaxy A15 (Android 16) ; OPPO A15 (Patch 2022-04)
samsung a15 -> Galaxy A15 (Android 16)
oppo a15    -> OPPO A15 (Patch 2022-04)
```

32. **Una risposta sola a una domanda con due risposte è sbagliata anche
    quando è verificata.** Vale ovunque l'input sia ambiguo: la scelta
    silenziosa è peggio dell'ambiguità dichiarata.
33. **Deduplicare con la chiave sbagliata cancella informazione.**
    `_normalize_name` toglie la marca per far combaciare le forme dello
    stesso telefono: usarla per distinguere telefoni diversi li fonde.
