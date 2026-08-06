# Mobile Update Tracker — passaggio consegne (v33)

Aggiorna `passaggio-consegne-v32.md`.

- **527 test**, tutti verdi (erano 511 con **2 rossi già prima** di questa sessione).
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
