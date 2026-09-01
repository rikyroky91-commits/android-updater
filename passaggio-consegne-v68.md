# Passaggio di consegne — 1 settembre 2026 (v68)

Segnalazione: «continua a non trovarmi i modelli — `862245059650208` questo
non lo trova».

La riga c'è, ed è questa:

```
VIVO,86224505,"VIVO Y76 5G, Vivo Mobile V2124"
```

Sono andato a fondo invece di correggere il caso singolo, e sotto ci sono
**quattro** difetti diversi, tutti della stessa famiglia: l'app aveva il
dato e non lo riconosceva. Uno di questi è la causa dell'unico test che
questo repository si portava dietro rosso da prima della v66.

**La suite ora passa per intero: 1405 test, zero fallimenti.**

---

## 1. I codici vivo hanno UNA lettera sola

`V2124`, `V2307`, `V2529`. Il pattern generico dei codici pretende almeno
due lettere iniziali (`[A-Z]{2,4}\d{3,5}`), quindi **nessun codice vivo è
mai stato riconosciuto**. Conseguenze, entrambe reali:

* la riga non ha nemmeno un anno, quindi senza codice restava fuori
  dall'indice — due terzi dei vivo del database (3.202 righe fuori contro
  1.610 dentro), fra cui il V60 Lite 5G del 2025 (`V2529`);
* anche quando veniva trovata, il telefono si cercava **per nome** invece
  che per codice, che è la chiave esatta con cui rispondono le fonti —
  mentre `modelcodes` sa benissimo che `V2124` è lo Y76 5G.

## 2. Metà dei codici Xiaomi recenti non erano codici

Il pattern Xiaomi pretende 2-3 CIFRE dopo il gruppo di lettere, e la
produzione recente non ce le ha: `2406ERN9CC`, `24074RPD2I`, `25078PC3EE`,
`2510ERA8BT`, `22111317PI`. Sono i Redmi e i POCO degli ultimi due anni.
Mancava anche la famiglia più vecchia, quella che comincia per M —
`M1910F4G` (Mi Note 10), `M2012C3P1C` (Redmi 9A).

**1.093 righe guadagnano un codice**, misurate sul file vero. Fra le righe
già indicizzate ne cambia una sola (`CELLON M8047UC IQ180`, che di sigle
ne ha due scritte in fila). Aggiunto anche `TA-1234` di Nokia, 250 righe.

L'indice passa da 79.380 a **83.044 TAC**, e la memoria non si muove: 54,5
MB contro 54,0, con lo stesso picco di 65.

## 3. «N/A» non è né un codice né un produttore

La pagina scriveva «Honor 400 Pro (N/A2025)». `N/A` è come il dataset dice
«non ce l'ho», e finiva intero nel campo produttore: una sigla che sembra
un codice modello e non lo è. Ora si scarta e si tiene l'anno, che è un
dato vero: «Honor 400 Pro (2025)».

## 4. «Redmi Note 10» non è un «Mi Note 10» — ed era da qui che veniva il test rosso

Questo è il difetto più interessante dei quattro.

`_nome_appartiene_al_codice` è il freno che deve distinguere una variante
regionale («OnePlus 10R» e «一加 10R») da un nome che parla di un altro
telefono. Confrontava le stringhe **appiattite**, senza spazi — e
`minote10` sta dentro `redminote10` per tre lettere di distanza. Quindi
«Redmi Note 10 EEA» risultava un nome legittimo di `M1910F4G`, che è un Mi
Note 10.

Seconda strada per lo stesso errore: l'appiattimento buttava via gli
ideogrammi, riducendo «小米 Note 10» a `note10`, che a quel punto è
contenuto in mezzo mondo.

Adesso il confronto è sulle parole: uno dei due nomi deve stare
nell'altro **cominciando e finendo dove finisce una parola**, e gli
ideogrammi sono lettere come le altre. «Galaxy A54 5G» dentro «Samsung
Galaxy A54 5G» continua a valere, perché lì il pezzo in più è una parola
intera.

Con il freno che funziona ho potuto usarlo in due punti nuovi di
`_cerca_davvero`:

* **una risposta che parla di un altro telefono non è una risposta.**
  Cercando `M1910F4G` il catalogo Xiaomi rispondeva con TRE ROM — «Redmi
  Note 10 EEA», «Mi Note 10 / Note 10 Pro EEA», «Redmi Note 10 Global» —
  tutte marcate con il codice cercato, perché è la ricerca stessa a
  incollarglielo. Vinceva la prima, e la pagina mostrava **nome e build di
  un telefono diverso**. Ora si tengono solo le risposte il cui nome è uno
  dei nomi di quel codice; se non ne passa nessuna non si butta via nulla,
  perché quando il catalogo non conosce il codice il freno risponde
  comunque «sì»;
* **un nome estraneo al codice non blocca più il nome canonico.** La
  regola che protegge il nome di una fonte strutturata (che conosce i
  mercati meglio del dataset community) resta, ma vale solo finché quel
  nome è uno dei nomi di quel codice.

Esito misurato: `M1910F4G` passa da «Redmi Note 10 EEA · Android 12 ·
build V14.0.6.0.SKGEUXM» a «Xiaomi Mi Note 10 / Note 10 Pro EEA · Android
11 · build V13.0.2.0.RFDEUXM» — il telefono giusto **e** la sua build.

---

## Verifica

Sito avviato in locale, i quattro IMEI di queste due segnalazioni:

| IMEI | prima | ora |
|---|---|---|
| `862245059650208` | non trovato | **vivo Y76 5G** (V2124), pastiglia 5G |
| `865587084948173` | non trovato | **Honor 400 Pro** (2025) |
| `866068054131131` | Oppo F19 | **OPPO A74** |
| `356427134239214` | non trovato | non trovato — non c'è in nessuna base dati gratuita |

Memoria: 167 MB, picco 194 (il picco include la lettura del file per
l'IMEI sconosciuto). Il confronto resta quello della v66: prima di tutto
questo erano 231 stabili e 268 di picco.

Suite: **1405 test, tutti verdi**. Erano 1371 con un rosso prima della
v66.

`tests/test_memoria_e_variante.py` sale a 34 test; i nuovi coprono i
codici vivo, la sigla corta che NON deve diventare un codice vivo
(«Motorola V66», «SGH-V100»), `N/A` che non è un produttore, e le tre
regole del confronto fra nomi (parola più lunga, parola intera in più,
ideogrammi).

## Cosa resta

1. **Applicare e distribuire.** Questo pacchetto contiene anche la v67, che
   non era ancora stata caricata: senza di quella il vivo Y76 5G verrebbe
   trovato lo stesso (è nell'indice grazie al codice `V2124`), ma tutte le
   righe fuori dall'indice resterebbero mute.
2. `356427134239214` aspetta un nome da una fonte esterna: cercalo su
   imei.info, dimmi che telefono è e diventa una riga in
   `data/tac_modelli.csv`.
3. Il catalogo Xiaomi risponde con più ROM per una stessa ricerca, e ora
   scartiamo quelle che nominano un altro telefono. Sarebbe meglio non
   farsele dare: è una nota per un giro futuro su `core/sources.py`.
4. Resta in piedi la nota della v66 su `core/modelcodes.py` e la sua forma
   di memoria.
