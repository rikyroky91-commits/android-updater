# Fonti dati — indagine completa e verdetti

Verificato il 2026-08-02. Ogni riga qui sotto è stata **provata davvero**,
non dedotta dalla documentazione. Dove ho scritto «non funziona» ho la
risposta del server.

## Premessa, perché cambia le conclusioni

**Il 100% non è ottenibile.** Nessuna di queste fonti è sotto il tuo
controllo: sono siti e API di terzi che possono cambiare formato senza
preavviso, e nessuna offre un contratto di stabilità. Chiunque prometta
affidabilità totale su dati scrapati sta descrivendo un desiderio.

Quello che si può fare davvero, ed è quello a cui punto qui, è:

1. **preferire il dato strutturato a quello scrapato** — un JSON tipizzato
   si rompe in modo rumoroso, una regex su HTML si rompe in silenzio;
2. **ridurre il numero di fonti** invece di aumentarlo — ogni fonte è
   manutenzione che si accumula (è la raccomandazione del documento di
   passaggio consegne, e tutte le proposte qui sotto la rispettano:
   sostituiscono o approfondiscono, non aggiungono marche);
3. **dire la verità sul tipo di dato** — «versione attuale», «versione di
   lancio» e «finestra di supporto» sono tre cose diverse, e confonderle è
   il modo più efficace di rendere l'app inaffidabile pur avendo tutte le
   fonti verdi;
4. **accorgersi subito dei guasti** — il rilevamento delle fonti impoverite
   già presente in `storage.py` è la cosa più vicina all'affidabilità che
   esista, e va esteso.

---

## Verdetti, fonte per fonte

### ✅ Solide — versione ATTUALE, dato ufficiale

| Fonte | Endpoint | Copertura | Note |
|---|---|---|---|
| **Samsung FOTA** | `fota-cloud-dn.ospserver.net/firmware/{CSC}/{MODEL}/version.xml` | **ogni Samsung** | vedi sotto: oggi ne usa 23 su migliaia |
| **Apple** | `api.ipsw.me/v4/device/{id}` | ogni iPhone/iPad | già in uso, solida |
| **Google Pixel** | pagine OTA `developer.android.com` | ogni Pixel | già in uso |
| **Xiaomi** | tracker MIUI/HyperOS (YAML) | ~1300 device | già in uso, comunitaria ma curata |
| **Motorola** | mirror `lolinet.com` | ~35 modelli | già in uso |

### 🟡 Utili ma parziali

| Fonte | Cosa dà | Limite verificato |
|---|---|---|
| **Oppo — archivio firmware** `{host}/oppo-server/softwareUpgrade/info` | versione rilasciata reale, data, patch level | **solo 94 modelli fino al 2021-2022**. Vedi `INTEGRAZIONE-OPPO.md` |
| **AER — API JSON** | catalogo, codici modello, fine supporto sicurezza | **nessuna versione attuale** (vedi trappola sotto) |
| **GSMArena** | versione di fabbrica + codici modello | derivata, non ufficiale |

### ❌ Provate e scartate, con la prova

| Fonte | Esito |
|---|---|
| `realme.com/*/support/software-update` | 200, ma è lo **stesso archivio legacy** di Oppo: realme UI 1.0-3.0, modelli RMX18xx. Niente di attuale |
| `service.oneplus.com` | **403** a qualunque accesso automatico |
| `oneplus.com/global/support/software-upgrade` | **404** |
| `coloros.com/en/version` | **404** |
| `security.oppo.com` | 200, ma è il portale bug-bounty (OSRC): avvisi CVE, **nessun patch level per modello** |
| `security.oneplus.com` | 200 ma 2,8 KB: pagina vuota, contenuto caricato altrove |
| `security.realme.com` | **il dominio non esiste** (DNS) |
| `vivo.com/en/support/security-update` | **404** — ma `vivo.com/en/security` funziona: vedi sotto |
| `hihonor.com/global/security` | 200 ma sono bollettini CVE, non versioni per modello |
| API OTA Oppo/OnePlus/realme (Allawn/ColorOS) | richiedono l'impronta del dispositivo e la finzione dell'app ufficiale → **fuori dalle regole del progetto**, come già deciso per OxygenUpdater |

**Conclusione onesta su Oppo/OnePlus/realme moderni:** non esiste una fonte
**ufficiale** pubblica e machine-readable della versione OTA corrente. Non è
un limite del progetto, è una scelta di quei produttori.

Da qui è nata l'unica eccezione dichiaratamente non ufficiale del progetto,
descritta sotto.

---

## Il canale di rollout OxygenOS/ColorOS — misurato prima di essere adottato

`https://t.me/s/oxygenos14update` — vista web pubblica, nessun account,
nessun token, nessuna API di Telegram. **Trust `CURATED`, mai `STRUCTURED`:**
è il canale di una persona e non deve poter sovrascrivere un dato ufficiale.

### La misura, fatta prima di scrivere il parser

Due pagine consecutive (messaggi 1636-1677), lette il 2026-08-03:

| | |
|---|---|
| post totali | ~40 |
| **rilasci confermati** | **11**, su 11 codici modello distinti |
| di cui **senza il nome del telefono** | **5** — c'è solo `CPH2613`, `NE2211`… |
| post di versioni **previste** | 6 (scartati) |
| rumore (rilanci da X, sondaggi, dirette) | il resto |

Due conclusioni operative da questi numeri.

**La copertura è reale ma stretta.** Prevalgono OnePlus e Oppo di fascia
alta, regione India; realme quasi non compare nonostante il nome del canale.
Una pagina intera (1656-1677) non conteneva **nessun** rilascio confermato:
è normale, non un guasto, e il codice distingue i due casi.

**Metà dei rilasci arriva senza nome commerciale.** È il motivo per cui
questa fonte funziona *qui* e non funzionerebbe altrove: `modelcodes` e il
catalogo AER traducono già `CPH2613` in un nome. Il canale porta il
firmware, il progetto ci mette l'identità. Un rilascio il cui codice non si
risolve viene **scartato** nel giro periodico: un dispositivo chiamato
«CPH2613» non incontrerebbe mai «OPPO A6x» delle altre fonti, e
produrrebbe due schede con mezza storia ciascuna.

### La trappola: è di nuovo quella di Honor

Una fetta consistente dei post è una **previsione**, con build ben formata e
livello di patch — sembra un dato buono in tutto, e lo smentisce solo la
prosa: «Upcoming…», «these values are subject to change as the verification
process is still ongoing». Prenderla per versione attuale sarebbe
**identico** all'errore già pagato con la pagina AER di Honor, dove la
versione *promessa* era stata letta come *spedita*.

Il rifiuto è esplicito, elencato in `MARCATORI_PRELIMINARI`, e coperto da un
test che verifica anche il contrario — che quel post conteneva davvero una
build valida — così se qualcuno «semplificasse» il filtro si vedrebbe subito
perché il test è rosso.

### L'unico pezzo non verificato sul vivo

I **testi dei messaggi** sono registrati dal canale vero
(`tests/fixtures/telegram_oplus_messaggi.json`). L'**involucro HTML** della
vista `/s/` no: è ricostruito sulla struttura nota della pagina, perché lo
strumento con cui l'ho letta restituisce testo estratto, non HTML grezzo.

Il rischio è contenuto per costruzione: `rilasci_da_pagina()` restituisce un
**errore** quando non estrae nessun messaggio. Se l'involucro fosse
sbagliato, o se Telegram cambiasse le classi CSS, la fonte apparirebbe
**rossa in Diagnostica** invece che verde e vuota — che è la differenza fra
un guasto e una bugia silenziosa. **Da confermare comunque al primo giro in
produzione**, guardando Diagnostica.

---

## Le tre cose da fare, in ordine di guadagno

### 1. Samsung FOTA su tutti i modelli — il guadagno maggiore

Oggi la fonte Samsung copre **23 modelli** scelti a mano. L'endpoint è
generico: verificato che con `CSC=EUX` risponde per qualunque `SM-`
europeo.

```
SM-S928B EUX → Android 16  S928BXXS6DZG1/S928BOXM6DZG1/…
SM-S938B EUX → Android 16  S938BXXSBCZG3/…
SM-F966B EUX → Android 16  F966BXXSBBZG3/…
SM-X510  EUX → Android 16  X510XXSEEZG3/…
SM-A346B EUX → Android 16  A346BXXUFFZE6/…
```

Un modello inesistente per quel CSC dà **403**, non un dato sbagliato: è il
comportamento ideale, l'errore è distinguibile dal successo.

I codici `SM-` per interrogarlo ci sono già: li dà l'AER (96 Samsung) e il
CSV di Google (sotto). Samsung passerebbe da 23 modelli a **tutti**, con
dato ufficiale e attuale — la fonte più affidabile del progetto, oggi usata
al minimo.

Attenzione al costo: una richiesta per modello. Va fatto solo per i device
in archivio o in watchlist, non per un catalogo intero a ogni giro.

### 2. AER via JSON invece di quattro regex — già implementato

`core/aer_catalog.py`, **40 test verdi** in `tests/test_aer_catalog.py`.

Una richiesta, **706 dispositivi di 40+ marche**, con:

* **1404 codici modello** (`CPH2791` → `OPPO Find X9 Pro`, `RMX5057` →
  `realme 14 Pro 5G`, `SM-S938B` → `Galaxy S25 Ultra`);
* **fine del supporto di sicurezza** e cadenza (mensile/trimestrale). Per un
  QA è un dato operativo che oggi non è da nessuna parte: dice se un device
  di test è ancora vivo o è fuori supporto;
* versione Android **di lancio**;
* la **foto ufficiale** del modello (oggi si indovina da Wikipedia).

Sostituirebbe i parser HTML separati di Honor, realme e Oppo: da tre punti
di rottura silenziosa a uno rumoroso. (vivo non serve più: la sua pagina
ufficiale è stata letta e il parser riscritto sui dati veri — vedi sotto.)

> **La trappola, e vale la pena scriverla due volte.** Il campo
> `hardwareFeatures.os` sembra la versione attuale. Non lo è: il **Galaxy
> S21 FE vi risulta «Android 16»**, che non ha mai ricevuto, e **402
> dispositivi su 706 riportano lo stesso identico valore**. È dichiarativo,
> compilato dal produttore. Usarlo sarebbe la ripetizione esatta dell'errore
> della «Future version» di HONOR, con l'aggravante che qui sembra
> plausibile. Nel modulo c'è `verifica_versione_attuale()`, che esiste solo
> per sollevare un'eccezione con la spiegazione, e un test che blocca la
> regressione.

Un bug trovato e corretto durante la scrittura, che vale come esempio del
perché servono i test: togliere la marca dal nome faceva collidere
**«OnePlus 12» con «Redmi 12»** (entrambi si riducono a `12`), e la ricerca
restituiva il modello sbagliato. Ora le forme ambigue vengono **scartate**
invece che assegnate al primo arrivato: meglio un modello non trovato — che
si vede — di uno sbagliato che sembra giusto.

### 3. Codici modello dal CSV ufficiale di Google

```
https://storage.googleapis.com/play_public/supported_devices.csv
```

**53.242 righe**, UTF-16, colonne `Retail Branding, Marketing Name, Device,
Model`. È il catalogo con cui Google Play decide la compatibilità delle app:
ufficiale, stabile da anni, aggiornato di continuo.

```
"Oppo","Find X9 Pro","OP5E8EL1","CPH2791"
```

Oggi `modelcodes.py` usa due dataset e `diagnose_query()` deve avvisare
«il testo ha la forma di un codice ma nessun dataset lo conosce» — che il
documento indica come **il motivo più probabile** di una ricerca a vuoto.
Questo CSV chiude quel buco per tutte le marche in una volta.

---

## Come si rende affidabile un impianto di fonti che non lo è

Nessuno dei punti sopra basta da solo. Quello che rende il risultato
affidabile è il modo in cui le fonti vengono combinate.

1. **Etichettare il tipo di dato, non solo la fonte.** Tre categorie
   distinte in interfaccia: *versione attuale verificata* (Samsung FOTA,
   Apple, Pixel, Xiaomi, Motorola, archivio Oppo), *versione di lancio*
   (AER, GSMArena), *indizio da notizia*. Oggi la distinzione esiste a metà
   in `size_info`. Un dato di categoria bassa non deve mai apparire con la
   stessa faccia di uno alto.

2. **Accordo fra fonti come segnale.** Quando due fonti indipendenti danno
   la stessa versione per lo stesso modello, la fiducia è alta. Quando
   dissentono, è un'informazione: va mostrato il disaccordo, non nascosto
   scegliendo la fonte con più punti. È il caso in cui l'app oggi può
   sbagliare senza che nessuno se ne accorga.

3. **Estendere il rilevamento di degrado ai campi, non solo al conteggio.**
   `_valuta_degrado` in `storage.py` si accorge se una fonte rende meno
   voci. Non si accorge se rende lo stesso numero di voci con il campo
   versione vuoto — che è come si è rotta la fonte realme. Stessa mediana,
   applicata alla percentuale di voci con versione valorizzata.

4. **Un controllo di coerenza temporale.** Una versione che *retrocede* per
   un modello già noto è quasi sempre un errore di lettura, non un
   downgrade. Oggi verrebbe scritta in archivio. Va scartata come già si fa
   con gli impossibili in `_implausibilita`.

5. **`DATA_LOGIC_VERSION` a ogni correzione.** Già in uso, già a 18.

Con questi cinque, quando una fonte si rompe l'app **lo dice** invece di
mostrare un dato vecchio con l'aria di uno nuovo. È il massimo grado di
affidabilità ottenibile con dati di terzi, ed è molto più utile di una
promessa di perfezione.

---

## Stato del codice

Il progetto in questa cartella è la versione completa (quella che era a
`DATA_LOGIC_VERSION` 17), ripresa dallo zip `tracker-fonte-vivo.zip`, non
dal repository GitHub: **il repo è indietro, fermo alla 13**. Le versioni
14-17 (GSMArena universale, la ricerca che sceglie il risultato con la
versione, il rilevamento delle fonti impoverite, la fonte vivo) non sono
mai state caricate. Vale la pena allinearlo.

| Voce | Stato |
|---|---|
| `core/oppo_official.py` + `_lookup_oppo_support` in `sources.py` | **collegato e verificato dal vivo** |
| `core/aer_catalog.py` | pronto e verificato (706 dispositivi, 1404 codici); **non ancora collegato** |
| `core/suggest.py` | **bug corretto** (vedi sotto) |
| `DATA_LOGIC_VERSION` | 18 |
| Samsung FOTA generico | verificato, da implementare |
| CSV Google Play | verificato, da implementare |

**269 test, tutti verdi** (erano 267 all'apertura dello zip, ma **9 erano
rossi**).

### Il bug che i test hanno fatto emergere

In `core/suggest.py`, dentro `_collect_names()`:

```python
for nomi, _codice in sources.realme_name_variants().values():
    nomi_realme.update(nomi)
```

La variabile del ciclo si chiamava **come l'insieme che accumula tutti i
nomi**. Dopo il ciclo `nomi` non era più il catalogo ma l'ultima lista
realme; le `nomi.update(...)` successive sollevavano `AttributeError`, che i
`except Exception: pass` inghiottivano uno dopo l'altro.

Effetto: `suggest.catalog()` restituiva **un solo modello**
(`['realme C51s']`). Completamento mentre si scrive e «forse cercavi…»
erano **completamente morti**, senza un errore visibile da nessuna parte —
il guasto silenzioso perfetto, e la ragione per cui vale la pena eseguire
i test invece di fidarsi del fatto che l'app parte.

Corretto rinominando la variabile. Otto test tornano verdi.

### L'altro test rosso

`test_dato_strutturato_gia_in_archivio_vince_su_ricerca_live_vuota` zittiva
le notizie ma **non** le fonti strutturate: interrogava davvero il catalogo
Xiaomi, che per «Redmi 12 India» risponde, e la premessa «ricerca live
vuota» cadeva. Passava o falliva a seconda della rete. Reso ermetico
azzerando anche `_lookup_order`.


---

## vivo — risolto sui dati veri (2026-08-02)

Era l'unica fonte in errore, e il documento di passaggio consegne la dava
per illeggibile («il sito rifiuta l'accesso automatico»). **Non è vero**:
`https://www.vivo.com/en/security` risponde 200 con 37 KB di HTML e una
tabella regolare di 20 modelli. A non funzionare era il riconoscimento, per
tre motivi che si vedono solo guardando l'HTML vero:

1. lo schema AER generico pretende che il nome cominci con «vivo» o
   «iQOO» — la tabella scrive soltanto `X300 Ultra`, senza marca, e
   l'ancora non ha mai combaciato;
2. ogni cella comincia con `&nbsp;&nbsp;`, che **resta nel testo** perché
   togliere i tag non decodifica le entità;
3. la pagina scrive `Shipped version: Android 16`, con la parola davanti al
   numero, mentre Honor scrive `Shipped version: 15`.

Il parser ora legge la tabella per quello che è — righe e celle — invece di
inseguire il testo con una regex sola. **20 modelli**, con versione di
fabbrica, **fine del supporto** e **cadenza delle patch** (`patch fino a
07/2031 · Every 30 days`), che prima si buttavano via pur essendo nella
stessa riga.

Due dettagli tenuti dalle lezioni passate: la marca viene aggiunta al nome
(`vivo X300 Ultra`), altrimenti lo stesso telefono avrebbe un `device_key`
diverso dalle altre fonti e diventerebbe due dispositivi; e il codice in
`V40 Lite(V2341)` viene tolto dal nome ma conservato a parte.

La promessa futura non viene nemmeno letta — nella pagina vivo è per giunta
scritta `Andorid`, con un refuso del produttore.

`tests/test_vivo_aer.py`: **16 test sull'HTML vero** registrato in
`tests/fixtures/vivo_aer.html`, più una riga nella matrice di ricerca.
Scansione completa dopo la correzione: **nessuna fonte in errore**.

---

## Tracker ARB OnePlus/OPPO — la fonte migliore per questi marchi

`https://raw.githubusercontent.com/Bartixxx32/OnePlus-antirollchecker/main/README.md`
Trust **CURATED**. Progetto community (154 star) nato per un altro scopo:
avvisare chi fa flashing del rischio di brick da anti-rollback. Il numero di
build, per lui, e' un sottoprodotto — ma e' esattamente il dato che serve qui.

**Perche' viene prima del canale Telegram.** Entrambe sono fonti community, ma
questa e' generata da uno script che scarica i firmware veri e ne estrae i dati,
l'altra e' la prosa di una persona. A parita' di trust, vince la macchina.

**Cosa da' in piu' di tutte le altre fonti:** la build **per regione**, con i
codici modello distinti. Lo stesso OnePlus 13 e' `CPH2653_16.0.5.703` in Europa
e `CPH2649_16.0.7.201` in India — build diverse che non procedono di pari passo.
Per un parco di test misto, sapere quale delle due si ha in mano e' meta' del
lavoro.

**Copertura misurata:** OnePlus quasi per intero (dal 7 al 15, Nord, Ace, Pad) e
una parte di OPPO (Reno10 Pro, Find N3/N5, Find X3/X5, Find X8 Ultra).
**NON copre**: la serie A di OPPO (quindi *non* l'A6x), realme, vivo/iQOO.

**Due trappole gestite nel codice:**
1. Il README contiene due tipi di tabella. Quelle di **storico** elencano build
   superate: prenderle per correnti direbbe che un telefono e' fermo a una
   versione che ha lasciato mesi fa. Il discriminante e' la colonna `Region`,
   presente solo nello stato corrente.
2. La data in tabella e' quando il **tracker ha visto** la build, non quando il
   produttore l'ha distribuita. Va detta com'e', non spacciata per data di uscita.

**Non si deduce la versione di Android dal numero di build.** OxygenOS 16 gira su
Android 16 quasi sempre; "quasi" non basta per un campo che decide un retest
completo.

**Da sorvegliare:** il README letto riportava `Last updated: 2026-05-17`. Se
quella data smette di avanzare, il progetto e' fermo e la fonte va spenta.
`oplus_arb.copertura()` restituisce `ultima_verifica` apposta.

---

## Piste valutate e CHIUSE — non riaprirle senza un motivo nuovo

Elencate qui con la ragione tecnica, perche' sono tutte idee che sembrano buone
e tornano a galla ogni pochi mesi.

### User-Agent (`Build/XXXXXX`) — CHIUSA
Lo User-Agent Android conteneva il build ID reale del telefono di un utente vero.
Non piu': Chrome congela modello e versione a partire dalla **110** (febbraio
2023), con rollout completato entro la **113** (maggio 2023). Il modello diventa
la lettera `K` e la piattaforma `Android 10` fissi. I Client Hints
(`Sec-CH-UA-Model`) danno al massimo il nome del modello, **mai** build o patch.
I database di UA (WhatIsMyBrowser e simili) restano utili solo come archeologia
di build vecchie. Da Android 17 la riduzione vale anche per la WebView.

### Database di benchmark (Geekbench, AnTuTu, GFXBench) — CHIUSA
Verificato aprendo pagine di risultati reali per CPH2649 e CPH2865: il campo
sistema operativo riporta **solo** `Android 15` / `Android 16`. Nessun
`ro.build.version.incremental`, nessun fingerprint, nessun livello di patch.
Resta un segnale debole utile a una cosa sola: accorgersi che un modello ha
cambiato versione **maggiore** di Android.

### Cataloghi Google (Play Console, Firebase Test Lab) — CHIUSA
L'intuizione e' giusta: Google riceve i fingerprint in fase di certificazione e
via attestazione. Ma non li pubblica. Firebase Test Lab espone `MODEL_ID`, brand
e **versioni Android supportate in laboratorio**, non la build corrente sul
telefono di nessuno. Il Device Catalog da' RAM, SoC e API level. L'Android
Management API ha il campo giusto (`androidBuildNumber`, `securityPatchLevel`)
ma solo per dispositivi arruolati in una policy EMM che si controlla.

### AndroidDumps / dumps.tadiphone.dev — VALUTATA, NON INTEGRATA
Sulla carta la migliore: i `build.prop` contengono `ro.build.fingerprint` **e**
`ro.build.version.security_patch`, cioe' l'unico posto dove il livello di patch
sarebbe leggibile. Misurata prima di scrivere codice, e scartata per tre motivi
che vanno insieme:
1. **Copertura sbagliata**: pochi flagship Snapdragon. OPPO A6x assente (4G e
   5G), Find X9 assente, vivo X200 assente, iQOO 13 assente. Cio' che c'e' —
   OnePlus 13, realme GT 7 — e' gia' coperto meglio dal tracker ARB.
2. **Per la coda lunga c'e' un solo dump, fatto al lancio**: cioe' la versione
   di fabbrica, che e' il dato inutile gia' disponibile dall'AER.
3. **Il sito blocca i lettori automatici**, quindi l'indice andrebbe ricavato
   scrapando il canale Telegram di annuncio: due punti di fragilita' in fila per
   un guadagno che si sovrappone a una fonte che abbiamo gia'.

**Cosa la riaprirebbe:** se servisse davvero il livello di patch di sicurezza per
i modelli coperti (oggi nessuna delle due fonti OnePlus/OPPO lo da'), oppure se
la copertura si allargasse alla serie A di OPPO e a vivo.

### EPREL (database UE) — DA VALUTARE, con una cautela grossa
Dal 20 giugno 2025 il Regolamento (UE) 2023/1670 obbliga a registrare ogni
smartphone venduto nell'UE in `eprel.ec.europa.eu`, con API pubblica e chiave
gratuita. E' **ufficiale e obbligatoria per legge**, quindi tentante.

Ma il campo che espone e' la *durata minima garantita degli aggiornamenti*
(almeno 5 anni dalla fine dell'immissione sul mercato): **una promessa in anni,
non la versione installata oggi**. E' la trappola di Honor riscritta in un
regolamento europeo. Se venisse integrata, va etichettata come "finestra di
supporto" e non deve mai finire nel campo versione. Copre solo i modelli
immessi sul mercato dopo il 20/06/2025.

---

## Il SoC: quale chip monta un modello

Per il QA e' meta' della domanda. Un difetto legato al chip si riproduce solo
su una delle varianti, e il caso da manuale e' il Galaxy S24: `SM-S921B`
(Europa) monta Exynos 2400, `SM-S921U` (USA) monta Snapdragon 8 Gen 3. Stesso
nome, stesso firmware, chip diverso.

**Quindi il SoC va risolto per CODICE MODELLO, non per nome.** Una fonte che
dice "Galaxy S24 -> Snapdragon" da' un'informazione sbagliata a meta' del mondo.
E' il criterio con cui sono state scartate quasi tutte le fonti disponibili.

### Ordine delle fonti, in `core/soc.py`

1. **Catalogo dispositivi di Google Play** — `data/play_device_catalog.csv`.
   L'unica fonte gratuita e strutturata con il SoC per codice esatto: le
   varianti regionali sono righe distinte, quindi il problema e' risolto per
   costruzione. **Non e' inclusa nel repo** perche' non e' scaricabile in modo
   anonimo (vedi sotto).
2. **Regole deterministiche** per Apple (identificatore -> chip) e Pixel
   (generazione -> Tensor). Qui una regola e' lecita perche' non esistono
   varianti di mercato: un iPhone17,3 monta lo stesso A18 ovunque.
3. **Tabella curata a mano** — `data/soc_modelli.csv`. Corta di proposito.
4. **Catalogo specifiche** — `core/specs.py`, indicizzato per CODICE MODELLO.
   Dalla v45. Vedi la sezione dedicata qui sotto.
5. **Dataset esterno multi-marca** — un dump GSMArena su GitHub del 2021,
   indicizzato per NOME COMMERCIALE. Copre dove le prime quattro tacciono,
   mai il contrario.

### Il dataset esterno, misurato sul file vero (2026-08-09)

Fino alla v39 questo pezzo era scritto ma **mai provato**: il contenitore di
sviluppo non aveva rete, e il passaggio di consegne lo elencava fra le cose da
verificare. Ora e' stato scaricato davvero. Numeri:

| | |
|---|---|
| URL | `raw.githubusercontent.com/foykes/gsm-arena-dataset/.../gsm_arena_full_dataset.csv` |
| Risposta | `200`, **12,2 MB** |
| Righe con nome **e** chipset | 5538 |
| Nomi indicizzati | **14 079** |
| Copertura su un campione di 18 modelli 2019-2021, 10 marche | **14 su 18** |

Le intestazioni (`Brand`, `Model Name`, `Chipset`) sono testo semplice, ma **i
valori sono letterali Python** (`b'Exynos 980'`): il modulo li ripulisce, ed e'
il dettaglio che avrebbe riempito l'app di chip chiamati «b'Exynos». I quattro
buchi del campione sono tutti modelli **dopo il 2021**, che e' il limite gia'
dichiarato del dump.

**Due difetti trovati solo guardando il file vero:**

- **25 chiavi su 14 182 rispondevano con il chip di un altro telefono.** La
  forma abbreviata e' cio' che rende utile il dataset («Samsung S24 Ultra»
  trova «Galaxy S24 Ultra»), ma accorpa anche «Huawei P30» con «Motorola P30»
  sotto `P30`, e «vivo U3» con «vivo iQOO U3» sotto `vivo U3`. Vinceva la prima
  riga incontrata: il chip mostrato dipendeva dall'ordine del CSV. Ora una
  chiave contesa da due telefoni diversi con chip diversi **non risponde**.
  Nello stesso giro spariscono le chiavi impossibili come `2` o `X`, che sono
  la forma abbreviata di «OnePlus 2» e «OnePlus X». In tutto 103 chiavi in meno
  su 14 182, nessuna delle quali poteva identificare un telefono.
- **La cache pesava 24 MB.** Il CSV veniva messo in `meta` in esadecimale, cioe'
  al doppio della sua dimensione, dentro `tracker.db` — il file che viene
  caricato su un Gist ogni mezz'ora e committato ogni ora da GitHub Actions.
  Compresso sono 1,8 MB: tredici volte meno.

**Limite residuo, dichiarato e non risolto:** un nome senza marca risponde con
l'unico telefono che il dataset conosce con quel nome. Chi cerca «Note 10»
pensando al Galaxy Note10 riceve il chip dell'Honor Note 10, perche' e' l'unico
«Note 10» nel dump. Le forme complete («Galaxy Note10», «Redmi Note 10») non ne
sono toccate.

### Come ottenere il catalogo Play (opzionale, ma raddoppia la copertura)

Play Console -> *Monitor and improve* -> *Reach and devices* -> *Device catalog*
-> **Export device list**. Il CSV ha una colonna `System on Chip` per codice
modello. Va salvato come `data/play_device_catalog.csv` e caricato nel repo:
l'app lo legge da disco, senza rete e senza credenziali a runtime. Il SoC di un
modello non cambia mai, quindi un export ogni pochi mesi basta.

Serve un account Play Console (25 USD una tantum) con un'app pubblicata. Senza,
l'app funziona lo stesso con le fonti 2 e 3.

**Da verificare al primo export vero:** l'importatore e' scritto sulle
intestazioni **documentate** da Google, non su un file catturato, perche' il
download richiede il login. E' l'unico pezzo del modulo non provato su dati
reali. Le colonne sono riconosciute per nome e non per posizione, e il campo
SoC arriva nella forma "Qualcomm SDM855" (produttore davanti alla sigla).

### Perche' la tabella curata e' cosi' corta

Perche' un dato che guida una decisione non si inventa. Riempire un CSV di
qualche centinaio di righe plausibili sarebbe stato facile, ma chi legge non
distingue una riga verificata da una ricordata male, e un Exynos scritto al
posto di uno Snapdragon manda a cercare un bug su un telefono che non ce l'ha.

In particolare **non esiste una regola sul suffisso** Samsung B/U che si possa
applicare alla cieca: la ripartizione cambia a ogni generazione. S22 e S24
splittano Exynos/Snapdragon, S23 e S25 no, e nella stessa generazione l'Ultra
puo' seguire una regola diversa dagli altri modelli. Solo tabella.

### Quando la risposta non puo' essere una sola

Chi cerca "galaxy s24" senza codice non puo' ricevere una risposta secca,
perche' sarebbe sbagliata per meta' dei telefoni con quel nome. Ma tacere e'
peggio: l'app elenca **entrambe** le varianti e dice di cercare la sigla
esatta. Sapere che esistono due varianti e' gia' un'informazione operativa.

### Catalogo specifiche per codice modello — adottato (2026-08-10)

**Il problema che risolve.** Fino alla v44 il chip si trovava per i modelli di
punta e per quelli fino al 2021, e basta. `SM-A075F` — un Galaxy A07 del 2025,
cioe' esattamente il genere di telefono che sta in un parco di test — non era
in nessuna fonte: non nella tabella curata (venti modelli), non nel catalogo
Play (assente), non nel dataset del 2021. Non era un difetto del codice, era
un buco di copertura, e riguardava **quasi tutti i Samsung usciti dopo il 2021**.

**La fonte.** `github.com/bytecharts/device_specs_gsmarena` — una copia in JSON
del catalogo GSMArena, un file per modello. Si scarica come archivio:

```
https://codeload.github.com/bytecharts/device_specs_gsmarena/tar.gz/refs/heads/main
```

1,6 MB compressi, 4766 schede, nessuna autenticazione. Si passa da `codeload`
e non dall'API di GitHub perche' gli archivi non consumano il rate limit.

**Perche' e' utilizzabile per codice, a differenza del dataset del 2021.** Ogni
scheda porta il campo `Misc.Models`, che elenca i codici tecnici:

```
Misc.Models       SM-A075B, SM-A075B/DS, SM-A075F, SM-A075F/DS, SM-A075M
Platform.Chipset  Mediatek Helio G99 (6 nm)
Memory.Internal   64GB 4GB RAM, 128GB 6GB RAM, 256GB 8GB RAM
imageUrl          https://fdn2.gsmarena.com/...
```

Il dataset del 2021 espone la stessa colonna e non la leggeva: era indicizzato
per nome, ed e' il motivo per cui restava l'ultima fonte.

**Copertura misurata sul catalogo intero (2026-08-10):**

| | |
|---|---|
| codici Samsung `SM-` nel catalogo | 1969 |
| con processore risolto | **1891 (96%)** |
| i 78 che restano | telefoni a tasti (`SM-B110`) e modelli 2014 per cui il chipset non e' pubblicato nemmeno alla fonte |

**Perche' sta SOTTO la tabella curata e non sopra.** Per i modelli venduti con
due chip il catalogo ha **una scheda sola** con dentro tutti i codici, europei
e americani insieme:

```
Galaxy S24 -> Qualcomm SM8650-AC Snapdragon 8 Gen 3 - USA/Canada/China
              Exynos 2400 - International
   Models    -> SM-S921B, SM-S921U, SM-S921W, SM-S921N, ...
```

Da qui non si puo' sapere quale codice monta quale chip. Anteporlo alla tabella
curata — che ha una riga per codice — significherebbe rispondere «o l'uno o
l'altro» proprio dove la risposta esatta si conosce. Sotto, invece, copre tutto
il resto del listino senza poter contraddire un dato preciso. E' la stessa
regola del punto 5, applicata un gradino piu' in alto.

Quando il catalogo e' l'unica fonte e la scheda elenca due chip, si riporta
**l'ambiguita' con i mercati** invece di sceglierne uno: dire «Exynos 2400» a
chi ha in mano il modello americano manda a cercare un difetto sul telefono
sbagliato, e tacere del tutto toglierebbe l'informazione che le varianti
esistono — che e' gia' operativa, dice di guardare la sigla prima di aprire
una segnalazione.

**I due limiti, dichiarati anche in interfaccia.**

1. **Undici marche**: Samsung, Xiaomi, OPPO, OnePlus, vivo, Motorola, Google,
   Apple, Sony, Nokia. **HONOR, realme, Huawei e Nothing non ci sono.** Non e'
   un difetto da correggere: e' il perimetro della fonte, e `specs.status()` lo
   dice in Diagnostica. Per quelle marche restano le fonti precedenti.
2. **Un chip per scheda, non per codice** — vedi sopra.

**Cosa alimenta oltre al chip.** La stessa scheda porta RAM, archiviazione,
schermo, batteria, ricarica, fotocamere, peso, dimensioni, data di rilascio e
la foto del modello: e' la fonte della scheda tecnica in interfaccia. Nessuno
di questi dati entra in archivio — si legge al momento di mostrare la scheda —
quindi `DATA_LOGIC_VERSION` non cambia per questa fonte.

**Fragilita' nota.** E' un repository di un singolo manutentore: puo' sparire.
Le contromisure sono quelle gia' in uso per il dataset del 2021 — copia in
cache nell'archivio (compressa, si riscarica ogni 14 giorni), ripiego sulla
copia vecchia se il download fallisce, e una riga in Diagnostica che distingue
«non ancora caricato» da «download fallito». Se sparisse, si perderebbe la
copertura dei modelli nuovi, non l'applicazione.

---

### Piste scartate per il SoC

- **Catalogo Android Enterprise Recommended** (gia' integrato per altro):
  verificato che **non contiene il SoC**. L'unico campo vicino e'
  `processorSpeed`, una stringa di clock tipo "2.2 GHz". Era la speranza di una
  soluzione a costo zero, ed e' smentita.
- **Firebase Test Lab**: da' `MODEL_ID`, brand e versioni Android. Nessun chip.
- **PhoneDB**: la piu' accurata per sigla esatta, ma il database e' sotto
  licenza a pagamento e lo scraping non e' consentito. Usabile solo come
  verifica manuale a campione.
- **GSMArena, DeviceSpecifications, Kimovil**: nessuna API, scraping non
  autorizzato.
- **Wikidata (proprieta' P880)**: gratuita e interrogabile via SPARQL, ma modella
  il nome commerciale e non la sigla: appiattisce proprio la distinzione che
  serve. Eventuale fallback NOISY, mai per le varianti.
- **Dataset generici di specifiche su Kaggle/GitHub**: quasi tutti a livello di
  nome commerciale. Comodi e fuorvianti — **come fonte principale**. Due sono
  poi stati adottati, ma entrambi SOTTO le fonti che lavorano per codice: li'
  non possono contraddire un dato preciso, possono solo riempire un silenzio.
  La distinzione e' tutta nell'ordine. Il secondo (v45, sezione sopra) porta
  con se' i codici modello e per questo lavora anche lui per codice — la
  differenza fra i due non e' la provenienza ma quale colonna si legge.

---

## I database TAC: misurati uno per uno (2026-08-09)

Da un IMEI si ricava il modello con le prime 8 cifre, il TAC. I database
pubblici sono alimentati dalla community, **si contraddicono fra loro** e
nessuno e' completo. Ecco quanto vale ciascuno, contato sui file veri.

| fonte | formato | TAC | di cui NUOVI | in archivio |
|---|---|---|---|---|
| MoazEb/tac-database | CSV 11,8 MB | 248 359 | — | 2,6 MB |
| VTSTech/IMEIDB | CSV 1,1 MB | 27 827 | **626** | 0,2 MB |
| Osmocom tacdb | CSV 3,2 MB | 22 524 | **97** | 0,3 MB |
| **insieme** | | **249 028** | **+0,27 %** | |

**Aggiungere basi dati gratuite non chiude il buco.** Due fonti in piu' —
una nuova, una riparata — portano 669 telefoni. E' un guadagno reale, ma
misurarlo ha risposto anche a una domanda piu' importante: non esiste la
combinazione di sorgenti gratuite che rende superfluo un secondo parere.
Per questo il confronto con i siti esterni e' sempre disponibile, non solo
quando la ricerca fallisce.

**29 060 TAC su 249 028 sono noti a piu' di una fonte**, e la' il
disaccordo e' frequente:

```
TAC 86751306   MoazEb   XIAOMI  ->  Xiaomi 9A Sport
               Osmocom  Xiaomi  ->  Redmi 9A
```

### Osmocom: scaricata per mesi, mai letta

Il file comincia con una riga di copyright, e l'intestazione vera e' la
**seconda**. Cercando la colonna `tac` nella prima riga non la si trovava e
la lettura usciva a mano vuota. Il download pero' **riusciva**, quindi
nessuna diagnostica poteva accorgersene. Altra particolarita': l'intestazione
ha due colonne chiamate `name` — la prima e' la marca, la seconda il
modello.

### Perche' il CSV e non l'xlsx

Stessa base dati, stesso commit, dati identici. Un `.xlsx` e' gia' un
archivio compresso, quindi dentro `tracker.db` occupava 13,5 MB anche dopo
la compressione; il CSV scende a 2,6. Il formato si riconosce **dai byte**
(`PK` all'inizio = zip = xlsx), non dall'URL: cosi' il file servito
nell'altro formato viene letto lo stesso invece di dare zero righe senza
errori.

### Piste NON percorribili per il TAC

- **imei.info, imeidb.xyz, hicelltek, nobbi.com**: bloccano l'accesso
  automatico o lo vietano nei termini d'uso. Consultarli **di persona** e'
  del tutto lecito, ed e' esattamente cio' che i collegamenti nell'app
  permettono. Solo imei.info accetta una ricerca diretta nell'indirizzo;
  gli altri sono pagine di ricerca e non ricevono nessun identificativo.
- **HiCellTek API**: piano gratuito da 100 interrogazioni al mese, accetta
  il **solo TAC** e non l'IMEI intero. Il codice c'e' ed e' spento: si
  attiva valorizzando `TAC_API_KEY`. La registrazione richiede un'email
  aziendale (vedi v36).
- **GSMA (l'autorita' che assegna i TAC)**: database ufficiale, a
  pagamento e sotto contratto.

---

## Investire su HONOR, HUAWEI, realme, Nothing (2026-08-11)

Richiesta dell'utente: scheda tecnica completa (almeno chip e firmware) per
ogni modello delle marche principali, "cosi per ogni marca grande". Le
quattro marche sotto sono quelle **fuori dal perimetro di `specs.py`**
(vedi "Undici marche" sopra). Di seguito cosa e' stato verificato, marca
per marca, e dove restano buchi reali.

### La caccia a un dataset sostitutivo: nessuno trovato

Prima di arrendersi alla compilazione manuale, si e' ripetuta la ricerca di
un dataset pronto (JSON/CSV, multi-marca, aggiornato dopo il 2021) che
copra HONOR/HUAWEI/realme/Nothing. Risultato: **stessa risposta della
ricerca precedente**, gia' in "Piste scartate per il SoC" sopra. Quello che
si trova sono script di scraping da eseguire in proprio (es.
`zehan-alam/Web-Scraping--GSMarena`, `cigarplug/scrape-gsma`) o dataset
Kaggle/GitHub a livello di **nome commerciale**, non di codice — la stessa
distinzione gia' spiegata per il Galaxy S24: inutile dove serve sapere
*quale* variante. Non c'e' una scorciatoia: la tabella curata resta l'unica
via per un dato verificato per codice esatto.

### Il primo lotto verificato a mano

Aggiunte 11 righe a `data/soc_modelli.csv` (7 modelli, 11 codici — alcuni
modelli hanno piu' codici per mercato), ciascuna controllata singolarmente
su GSMArena, stesso metodo gia' in uso per la serie Galaxy S: consultazione
manuale di una scheda, non uno scarico automatico. Coprono i modelli piu'
recenti/diffusi di ciascuna marca, non il catalogo storico:

| marca | modelli aggiunti | chip |
|---|---|---|
| HONOR | Magic7 Pro, 200 Pro | Snapdragon 8 Elite, Snapdragon 8s Gen 3 |
| HUAWEI | Pura 70 Pro | Kirin 9010 |
| realme | GT 7 Pro, 13 Pro+ | Snapdragon 8 Elite, Snapdragon 7s Gen 2 |
| Nothing | Phone (3), Phone (3a) | Snapdragon 8s Gen 4, Snapdragon 7s Gen 3 |

E' un inizio, non un catalogo: **7 modelli non sono "ogni modello delle
marche principali"**. Estendere la tabella resta un lavoro ripetibile ma
manuale — una riga verificata alla volta, mai una lista "plausibile"
generata in blocco, per lo stesso motivo per cui la tabella e' corta di
proposito (vedi `core/soc.py`).

### HUAWEI: un limite di scopo, non solo di dati

Scoperta rilevante per un tracker di *aggiornamenti Android*: da Mate 70
in poi (dicembre 2024), Huawei ha lasciato Android del tutto. HarmonyOS
NEXT non ha piu' base AOSP — non e' "Android in ritardo", e' un sistema
operativo diverso, senza compatibilita' con le app Android. I modelli
precedenti (Pura 70 e prima) restano invece Android/AOSP sotto la carrozzeria
EMUI o HarmonyOS ≤4.2: e' per questo che la riga HBN-AL00 sopra dice
esplicitamente "HarmonyOS 4.2 — ancora su base AOSP", per non confondere le
due situazioni.

Conseguenza pratica: per i modelli Mate 70/nuovi, un "non troviamo il
firmware Android" sarebbe un dato **falso**, non solo incompleto — il
telefono non ha un firmware Android da trovare. Il progetto non ha ancora
un modo per distinguere questo caso da un vero buco di copertura; e' il
prossimo passo consigliato su Huawei, prima di qualunque altro lavoro sui
suoi dati (altrimenti si rischia di "risolvere" un buco che non e' un
buco).

Sul fronte firmware per i modelli che restano Android: nessuna fonte
ufficiale gratuita e verificabile trovata (stessa conclusione gia' data per
Oppo/OnePlus/realme) — solo strumenti non ufficiali di terzi che rispecchiano
gli aggiornamenti (es. `satyamisme/Huawei-firmware-downloader`), nessuno
dei quali e' un'API interrogabile con garanzie.

### Nothing: l'unica delle quattro con una pista reale

A differenza di Oppo/OnePlus/realme (buco confermato, vedi sopra), per
Nothing esiste un archivio community **attivo e aggiornato** (ultime voci
2026), alimentato da OTA scaricate dai server ufficiali:
`spike0en/nothing_archive` (pagina pubblica `nothingarchive.tech`).
Copre tutta la gamma Phone (1-3, incluse le varianti a/Pro/Lite) e i
CMF by Nothing. Non e' un'API: sono tabelle HTML per modello, con link ai
file OTA, organizzate su un repository GitHub con una convenzione di nomi
prevedibile (`<codename>_<versione>-<data>-<ora>`).

**Non ancora integrata.** Servirebbe un parser per quelle tabelle (o per i
nomi file del repository) e va verificato se e' abbastanza stabile da
non rompersi a ogni redesign della pagina — lavoro concreto, ma alla
portata, ed e' il candidato migliore per il prossimo miglioramento di
copertura firmware fra le quattro marche.

### Samsung: verificato che la ricerca live non e' limitata alla lista curata

Domanda aperta da questa stessa indagine: la ricerca dal vivo di un
codice Samsung qualunque (non solo i ~23 della lista periodica
`SAMSUNG_FUS_DEVICES`) passa comunque dal confronto multi-regione?
Risposta: si'. `_lookup_samsung()` (in `core/sources.py`) risolve QUALUNQUE
`SM-xxxx` trovato nei dataset con `modelcodes.codes_for_name`, poi chiama
`_samsung_fus_latest()` — la stessa funzione con confronto fra le CSC
primarie — per ognuno. La lista curata serve solo alla scansione periodica
in background, non limita la ricerca interattiva. Nessuna modifica
necessaria.

### Il motore IA del tasto: dove puo' aiutare e dove no

Il principio del modulo (`core/aiquery.py`) e' che il modello non inventa
mai un dato, sceglie solo fra candidati gia' costruiti da fonti vere. I
buchi descritti qui sopra (HONOR/HUAWEI/realme/Nothing fuori da
`specs.py`, nessuna fonte firmware per Oppo/OnePlus/realme/Huawei) sono
**buchi di disponibilita' del dato**, non di interpretazione — il motore
IA non puo' produrre un chipset che non e' in nessun catalogo. Dove puo'
aiutare davvero e' a instradare query scritte male verso il dato *che
esiste gia'* (es. il codice giusto nella tabella appena estesa), non a
colmare l'assenza di fonte. Nessuna modifica al modulo per questa parte
del lavoro: il suo compito resta a valle della disponibilita' dei dati, non
a monte.

---

## Richiesta ristretta a Oppo/Xiaomi/HONOR/realme/Motorola (2026-08-11, stesso giorno)

Richiesta successiva, piu' mirata: "tutti i modelli" di queste cinque
marche con scheda tecnica e ultimo aggiornamento. Prima di aggiungere
altro, e' stato utile misurare **quanto e' gia' coperto davvero**, marca
per marca — la risposta cambia molto da marca a marca.

### Scheda tecnica: tre marche su cinque sono gia' a posto

`specs.py` (l'archivio GSMArena, ~4700 schede, aggiornato di continuo)
copre **Oppo, Xiaomi e Motorola per intero** — sono 3 delle 11 marche del
suo perimetro. Per queste tre, "la scheda tecnica di ogni modello" e' gia'
la situazione attuale, senza bisogno di altro lavoro: chip, RAM, schermo,
batteria, fotocamere per qualunque codice nel catalogo, aggiornato da solo.

**HONOR e realme restano fuori** (vedi sezione sopra) — qui la tabella
curata e' l'unica via, e resta un lavoro manuale senza scorciatoie: oggi
sono stati verificati altri 4 modelli (realme Note 60 — il telefono
dell'utente, RMX3933 — Honor Magic6 Pro, realme 14 Pro+), che si sommano ai
7 del lotto precedente. **11 modelli in tutto, non "tutti".**

### Firmware — "ultimo aggiornamento": la situazione reale, marca per marca

| marca | stato | dettaglio |
|---|---|---|
| **Xiaomi** | ✅ gia' a posto | tracker MIUI/HyperOS strutturato, gia' in uso |
| **Motorola** | ✅ gia' a posto per la gamma attuale | mirror `lolinet.com`, 35 modelli Razr/Edge/G 2022-2025, gia' in uso |
| **Oppo** | 🟡 parziale, e non migliorabile facilmente | vedi sotto |
| **realme** | ❌ il buco piu' profondo delle cinque | vedi sotto |

**Oppo, in dettaglio.** Tre fonti attive insieme: l'archivio ufficiale
`par-sow-cms.oppo.com` (94 modelli, ma fermi al 2021-22 — vedi
`INTEGRAZIONE-OPPO.md`), il tracker community `oplus_arb`
(`Bartixxx32/OnePlus-antirollchecker`, build reali per regione, ma **lui
stesso dichiara di non coprire la serie A, realme e vivo**), e infine AER +
notizie come ripiego. Il risultato e' buono per i modelli OnePlus e Oppo di
fascia alta recenti, debole sulla serie A economica.

**realme, in dettaglio — perche' e' il caso peggiore.** realme condivide
l'infrastruttura con Oppo (stesso gruppo BBK) ma **nessuna delle fonti
buone la copre**: `oplus_arb` la esclude esplicitamente; la pagina
`realme.com/*/support/software-update` risponde 200 ma e' **lo stesso
archivio legacy di Oppo** — realme UI 1.0-3.0, modelli RMX18xx, niente di
attuale (gia' verificato la volta scorsa). Restano solo AER (versione di
fabbrica) e le notizie.

### La ricerca di un'alternativa, oggi: confermato che non c'e'

Prima di scrivere "non c'e' soluzione" si e' cercata sul serio una via
nuova, in tre direzioni:

1. **API OTA ufficiali Oppo/realme (tipo quella usata da OxygenUpdater)**:
   richiedono di fingersi l'app ufficiale del telefono (`ro.product.name`,
   `ro.build.version.ota` come impronta) — **e' esattamente la regola gia'
   scritta in questo stesso file** ("fuori dalle regole del progetto, come
   gia' deciso per OxygenUpdater"). Non e' una scoperta nuova, e' la
   conferma che la porta e' chiusa per un motivo preciso, non per pigrizia.
2. **Tracker community equivalenti a `oplus_arb` ma per realme o HONOR**:
   cercati, non trovati. Quello che esiste (`realmeupdater.com`, canali
   Telegram, siti di terze parti tipo androidmtk.com/oppostockrom.com) o
   ripubblica lo stesso archivio legacy gia' noto, o e' un mirror di
   download senza una versione "corrente" dichiarata per modello.
3. **Un equivalente HONOR del mirror lolinet di Motorola**: cercato, non
   trovato. HONOR non ha un mirror comunitario strutturato paragonabile.

**Conclusione onesta**: per Oppo la situazione e' gia' quella migliore
ottenibile senza infrangere le regole del progetto; per realme e HONOR il
buco firmware e' reale e confermato una seconda volta, non solo dedotto
dalla sessione precedente. L'unica leva che resta e' la stessa gia' in uso
per Oppo/OnePlus: se in futuro emerge un tracker community nuovo, va
misurato con lo stesso metodo (numero di release confermate su un campione
di pagine, non fiducia sulla parola) prima di collegarlo — esattamente come
gia' fatto per `oplus_arb` e per il canale Telegram (poi ritirato perche'
misurato a zero risultati).

---

## Siti di confronto (versus.com, hdblog.it) come fonte specifiche: indagine, non ancora un'integrazione (2026-08-11)

L'utente ha chiesto conto, giustamente, del perche' non si possano prendere
le specifiche HONOR/realme da altri siti oltre GSMArena — versus.com e
hdblog.it come esempi concreti. Verificato sul serio, pagina per pagina,
non per teoria. Il verdetto e' diverso da entrambi gli estremi ("si puo'
sempre" e "non si puo' mai").

### Cosa e' stato controllato

| sito | `robots.txt` | dato nella pagina | codice modello |
|---|---|---|---|
| GSMArena | blocca **per nome** i bot AI, incluso "ClaudeBot" | statico | **si'** |
| honor.com | permissivo, sitemap pubblica | **caricato via JavaScript**, assente nell'HTML statico | si' (ma irraggiungibile senza browser headless) |
| realme.com | permissivo, sitemap pubblica | statico | **no** |
| versus.com | la pagina categoria ha risposto 403; le pagine singolo modello no | statico, dati reali (chip, RAM, OS) | **no**, cercato apposta e non c'e' |
| hdblog.it | permissivo (`Allow: /`) | non verificato a fondo: **429** (troppe richieste) gia' su 2 fetch di prova consecutivi | non verificato |

### Il problema non e' "i dati non esistono altrove" — e' un dato specifico che manca quasi ovunque

Chipset, RAM, versione Android per HONOR Magic7 Pro si trovano facilmente
anche su versus.com e su hdblog.it (quando risponde). Quello che **non**
c'e', su nessuno dei siti orientati al consumatore, e' il **codice
modello** (`PTP-AN10`, non "Honor Magic7 Pro"). GSMArena lo pubblica perche'
lo prende dalle certificazioni regolatorie (FCC, TENAA...), un lavoro che i
siti di confronto per consumatori non fanno: al lettore medio "che chip
monta" interessa, "che sigla ha sulla certificazione" no.

E' il motivo per cui questo progetto insiste sul codice: senza, un nome
commerciale con piu' varianti regionali a chip diverso (il caso Galaxy
S24 gia' spiegato piu' volte in questo file) darebbe una risposta sbagliata
a meta' di chi cerca. **Ma non tutti i telefoni hanno questo problema**: la
maggior parte dei modelli HONOR/realme di fascia media ha un chip solo,
uguale in ogni variante di codice. Per quei modelli un dato per NOME e'
gia' preciso, non approssimato — la stessa distinzione che il codice fa
gia' da solo in `carica_curato` (dichiara l'ambiguita' solo quando i chip
sono davvero diversi, altrimenti da' una risposta sola).

### Dove si incastrerebbe, se si costruisce

Non sostituirebbe la tabella curata per codice: si aggiungerebbe **sotto**,
nello stesso slot gia' occupato dal "dataset esterno multi-marca"
(`soc.carica_dataset_esterno`, oggi fermo al 2021) — indicizzato per nome,
`trust=CURATED`, mai in grado di sovrascrivere un dato per codice gia'
verificato. Un versus.com aggiornato al posto (o accanto) del dataset 2021
chiuderebbe silenzi reali su HONOR/realme senza toccare la precisione dei
modelli gia' in tabella.

### Perche' non l'ho gia' scritto

Stesso limite gia' incontrato con l'archivio `bytecharts` all'inizio della
sessione: **da questo ambiente non arrivano richieste dirette a versus.com
o hdblog.it** (stesso 403/timeout generico gia' visto con
`codeload.github.com`), quindi non posso vedere l'HTML vero — solo la
lettura mediata di `WebFetch`, che riassume ma non mostra tag, classi o
struttura. Scrivere un parser (regex o HTML) su una struttura non vista
sarebbe indovinare, esattamente quello che questo progetto si vieta (vedi
`core/oplus_arb.py`: "costruire un parser su una struttura non vista
sarebbe indovinare"). E hdblog.it, in piu', ha gia' risposto 429 a due
richieste isolate — un vero scraper dovrebbe fare i conti con un
rate-limit stretto, non solo con il parsing.

**Prossimo passo consigliato**: implementare e verificare questo modulo
dalla sessione con accesso di rete normale (quella con push/deploy), dove
si puo' vedere l'HTML vero, scegliere fra versus.com/hdblog.it/altri in
base a chi risponde in modo piu' stabile, e misurare — come gia' fatto per
`oplus_arb` — quante schede HONOR/realme escono davvero da un campione di
pagine prima di collegarlo.

### Checklist per chi lo implementa (sessione con rete vera)

Nell'ordine, ognuno e' un controllo che qui non ho potuto fare:

1. **Leggere i Termini d'Uso veri, non solo `robots.txt`** — di versus.com
   e di hdblog.it. Il progetto ha gia' scartato PhoneDB proprio per una
   clausola di licenza nei Termini, non nel `robots.txt`: lo stesso
   controllo va rifatto qui prima di scrivere una riga di parser. Se un
   sito lo vieta esplicitamente, si scarta, punto — stessa regola gia'
   applicata a GSMArena/Kimovil/DeviceSpecifications/PhoneDB.
2. **Vedere l'HTML vero** di 3-4 pagine modello (es.
   `versus.com/en/honor-magic-7-pro`, un realme, un modello piu' vecchio
   per controllare che il formato non sia cambiato nel tempo) e confermare
   che i campi chip/RAM/OS stanno in una struttura ripetibile (tabella,
   `<dl>`, o blocchi con classe fissa) — non dedotta da un riassunto.
3. **Cercare sul serio il codice modello** in quelle pagine — l'ho cercato
   e non l'ho trovato su versus.com per Magic7 Pro, ma vale la pena
   controllare 2-3 pagine diverse (magari un modello Samsung/Xiaomi dove
   si puo' confrontare con GSMArena) prima di dare per certo che manchi
   sempre.
4. **Trovare un modo per enumerare TUTTI i modelli HONOR/realme** sul sito
   scelto (sitemap, categoria, ricerca) — senza questo si torna a
   compilare a mano uno per uno, che e' quello che si sta gia' facendo.
5. **Misurare il rate limit** con una decina di richieste reali distanziate
   (hdblog.it ha gia' risposto 429 a due richieste isolate da qui): serve
   sapere il ritmo giusto prima di uno scan periodico, non scoprirlo in
   produzione.
6. **Scrivere i test con l'HTML vero salvato come fixture** (stesso
   pattern di `tests/test_soc_dataset.py`, che incolla un CSV letterale),
   non con dati inventati — cosi' il parser e' verificato contro la
   pagina reale, non contro un'ipotesi.
7. **Posizione nella catena delle fonti**: sotto la tabella curata per
   codice E sotto `specs.py`, mai sopra — stesso slot del dataset esterno
   2021 in `core/soc.py::carica_dataset_esterno`, `trust=CURATED` al
   massimo, indicizzato per NOME (non per codice, perche' quel dato manca).
   Dichiarare esplicitamente nell'interfaccia che e' un dato "per nome",
   non per codice esatto — stessa onesta' gia' usata per l'ambiguita' del
   Galaxy S24.
8. **honor.com resta un problema a parte**: i dati sono JS-rendered, quindi
   fuori standard per un parser leggero come tutti gli altri di questo
   progetto. Prima di inseguirlo, vale la pena decidere consapevolmente se
   introdurre un browser headless (Playwright) vale il costo — memoria e
   fragilita' aggiuntive, sullo stesso Render che ha gia' avuto OOM in
   questa sessione — o se conviene lasciarlo fuori e coprire HONOR solo
   con la tabella curata + l'eventuale fallback per nome su un sito che
   non richiede JavaScript.

---

## Proposta (non implementata): Gemini "Grounding with Google Search" per il buco specifiche (2026-08-11)

Nata mentre si discuteva se il motore IA del tasto (`core/aiquery.py`)
potesse aiutare con il buco HONOR/realme. Il tasto **usa gia' Gemini come
prima scelta** (vedi il modulo: "GEMINI PER PRIMO PERCHE' E' L'UNICO
DAVVERO GRATUITO") ma solo per un compito — scegliere fra candidati gia'
noti, mai inventare un dato tecnico. Questa e' un'idea per un compito
DIVERSO: usare Gemini per recuperare davvero la scheda di un modello che
qui manca.

**Come funzionerebbe.** L'API Gemini ha uno strumento ufficiale,
"Grounding with Google Search" (documentazione:
https://ai.google.dev/gemini-api/docs/generate-content/google-search): il
modello cerca sul web **dal lato server di Google**, non dal nostro, e
restituisce la risposta insieme a `groundingMetadata` — le query usate, i
frammenti di fonte con URL, e il collegamento fra ogni pezzo di testo e la
sua fonte. E' l'unica strada vista finora che aggira il muro di rete di
questo ambiente, perche' a cercare non sono io.

**Il limite che cambia la decisione: non e' gratis.** A differenza del
resto del tasto AI (pensato apposta per girare sulla quota gratuita di
Google AI Studio), questo strumento **richiede la fatturazione attiva** sul
progetto Google Cloud collegato alla chiave — si paga per ogni ricerca che
il modello decide di fare. E' un cambio di principio, non un dettaglio
tecnico: oggi "senza chiave la funzione e' spenta, non rotta" vale per una
funzione a costo zero; con grounding diventerebbe "spenta finche' non paghi
qualcosa".

**Se si decide di provarlo**, la forma piu' sicura e' comunque quella gia'
in uso in tutto il progetto: non scrivere mai il risultato in tabella senza
controllo, trattarlo come `trust=CURATED` con l'URL della fonte sempre
visibile (il campo `groundingChunks` lo da' gratis), e tenerlo separato dal
compito attuale del tasto — un endpoint o una funzione a parte, non una
modifica di `interpreta()`, perche' quella funzione oggi vieta esplicitamente
di parlare di "caratteristiche tecniche dei dispositivi" e va tenuta cosi'.

Non implementato: serve una chiave Gemini vera E la fatturazione attiva per
testarlo, nessuna delle due disponibili da questa sessione. Decisione da
prendere con l'utente, non da questa sessione in autonomia.

---

## Inserimento metodico per marca: realme poi HONOR (2026-08-11, stesso giorno)

Su richiesta esplicita dell'utente ("lavora ad un inserimento metodico,
autonomo per marca"), invece di aspettare richieste singole si è proceduto
in modo sistematico, una marca alla volta, stesso metodo di tutta la
sessione (una scheda verificata su GSMArena alla volta, mai uno scarico
bulk). Oppo verificato per primo e **già completo** (copertura automatica
via `specs.py`, nessun lavoro necessario — vedi sopra), poi realme, poi
HONOR.

**Un errore commesso e corretto in questo round, degno di nota.** Per
alcuni chip MediaTek (Dimensity 6300, 7300+, 7400 Ultra, 8400 Max, 6400
Turbo) GSMArena non pubblica una sigla interna distinta dal nome
commerciale, a differenza di altri MediaTek già in tabella (es. "Dimensity
6100+" = `MT6835`). Le prime righe scritte per questi modelli avevano una
sigla `MTxxxx` **indovinata per pattern** (es. "Dimensity 6300" →
`MT6300"), non letta da nessuna fonte — esattamente l'errore che questa
tabella esiste per evitare. Individuato e corretto prima del commit finale:
quelle righe ora hanno `soc_codice` vuoto invece di un dato inventato, con
un test di regressione dedicato
(`test_i_chip_mediatek_senza_sigla_interna_non_ne_inventano_una`) che
verifica esplicitamente l'assenza del codice per quei modelli.

**Risultato**: 24 righe nuove in questo round (13 realme, 11 HONOR — 111
righe totali in `data/soc_modelli.csv`, da un file che ne aveva 89
all'inizio della sessione). GSMArena ha risposto 429 (troppe richieste)
due volte durante il round HONOR: i modelli su cui è successo (Honor 600
Pro, realme P4 Lite) sono stati saltati invece di indovinati, restano da
riprendere in un round successivo.

Resta vero quanto già scritto sopra: non è "tutti i modelli", è una
copertura più ampia costruita nello stesso modo verificato di sempre.

---

## Inserimento metodico, round 2: ripresa dei saltati + nuovi modelli (2026-08-11, stesso giorno)

Su "riprendi un altro giro" si è proseguito il lavoro brand-by-brand del
round 1, con lo stesso metodo.

**Honor 600 Pro** (saltato nel round 1 per 429): GSMArena ha continuato a
rispondere 429 anche in questo round. Verificato invece su GSMchoice.com
(unica fonte, non incrociata) — `VKP-NX9`, Snapdragon 8 Elite
(`SM8750-AB`), coerente con lo schema già visto per altre coppie base/Pro
HONOR (es. `VKJ-NX9` Honor 600 → `VKP-NX9` Honor 600 Pro). Etichettato
esplicitamente come "fonte singola" nel campo `nota`, a differenza delle
altre righe cross-verificate.

**realme P4 Lite** (stesso motivo, stesso saltato): GSMchoice ha restituito
un chipset incoerente ("Unisoc Tiger T615 UMS9230E T7250" — due famiglie di
chip mescolate nella stessa stringa). Giudicato inaffidabile e **non
aggiunto**, coerente con il principio "meglio saltare che indovinare".

**Proseguito con nuovi modelli** una volta che GSMArena è tornato
disponibile: Honor Magic7 RSR Porsche Design (`PTP-AN20`/`PTP-N59`),
realme 16 Pro+ (`RMX5131`), Honor 200 (`ELI-AN00`/`ELI-NX9`), Honor Magic7
Lite (`BRP-NX1`), realme GT 7 base/global (`RMX5061`, distinto sia dal GT 7
Pro sia dalla variante Cina non codificata), realme 15T, Honor 400 Lite,
Honor X70i, Honor X70.

**Due casi particolari degni di nota:**

- *realme 15T*: GSMArena non pubblica affatto una riga "Models" per questo
  telefono (né sulla pagina globale né in altre varianti controllate). I
  codici (`RMX5111`, `RMX5112`) vengono da GSMchoice; il nome del chip è
  stato incrociato su 3 fonti indipendenti (GSMArena stesso, Gizbot,
  TechNave), tutte concordi su "Dimensity 6400 Max" — solo GSMchoice lo
  scrive senza "Max", giudicato un refuso minore e non un conflitto reale
  (diverso dal caso realme P4 Lite sopra, dove le fonti davano famiglie di
  chip diverse, non solo un suffisso).
- *Honor X70 / X70 Pro Max*: GSMArena e GSMchoice concordano che
  condividono lo **stesso** model code (`MTN-AN00`), stesso chipset
  (Snapdragon 6 Gen 4). Nessun problema per questa tabella — è indicizzata
  per codice, non per nome commerciale — ma vale la pena documentarlo: si
  è scelto "Honor X70" come nome canonico della riga, con nota esplicita
  che il codice è condiviso con la Pro Max.

**Risultato**: 15 righe nuove in questo round (126 righe totali in
`data/soc_modelli.csv`). Suite completa: 896 test passati (era 885 a fine
round 1).

---

## Bug reale trovato dall'utente: «realme c63» rispondeva «C61» (2026-08-11, stesso giorno)

Segnalato con uno screenshot dal sito vero: cercando «realme c63» la
pagina mostrava la scheda di «C61» — niente foto, niente CPU, e la tabella
aggiornamenti diceva «realme C61 (RMX3930) — Android 14 di fabbrica...
piano ufficiale Android Enterprise Recommended». RMX3939 (il vero C63,
verificato in questo stesso progetto — vedi sopra) non compariva da
nessuna parte. Domanda dell'utente, testuale: **"aggiornamento firmware su
quali basi?"**

### La causa, trovata risalendo la catena di chiamate senza toccare la rete

`core/scan.py::forme_equivalenti()` genera "forme equivalenti" per una
ricerca — un nome digitato prova anche il suo codice, un codice prova
anche i suoi nomi commerciali — così una ricerca per nome vale quanto una
per codice. Il passo che prova i nomi commerciali di un codice usa
`modelcodes.resolve(codice)`, che pesca dal dataset community
KHwang9883/MobileModels-csv (~89.000 codici, mai verificato a mano — lo
stesso genere di fonte di cui questo progetto diffida da sempre, vedi i
database TAC).

Verificato con una chiamata diretta (dati REALI, non simulati):

```python
>>> modelcodes.resolve("RMX3939")
['C61', 'C63', 'C65s', 'NARZO N63']
>>> modelcodes.codes_for_name("C61")
['RMX3930', 'RMX3933', 'RMX3939']   # tre codici diversi!
```

Il dataset registra "C61" come nome DI TUTTI E TRE questi codici — non
solo del caso già noto e gestito correttamente (RMX3933, che l'app mostra
già come «noto anche come» C61/Note 60/Note 60s/NARZO N61, la funzione
"gemelli"), ma anche di RMX3939, dove "C61" collide con RMX3930, il vero
C61 secondo Android Enterprise Recommended (fonte Google, non community).

`forme_equivalenti("realme c63")` risolveva correttamente al codice
RMX3939, poi provava OGNI suo nome commerciale come forma di ricerca
equivalente — compreso "C61", che essendo ambiguo portava a RMX3930. La
fonte ufficiale (AER) rispondeva per "C61" con dati VERI, ma di un
telefono diverso da quello cercato: non un dato inventato, un dato giusto
attaccato al telefono sbagliato. `_lookup_structured_for` prende la prima
forma che risponde con firmware e si ferma lì, senza verificare che il
codice restituito dalla fonte corrisponda a quello di partenza — questo
è il punto preciso dove la correzione serviva.

### La correzione

`core/modelcodes.py::resolve_senza_ambiguita(codice)` — come `resolve()`
ma tiene solo i nomi che risolvono **a un solo codice, ed è proprio
questo** (verificato col percorso inverso, `codes_for_name`). Per
RMX3939 restituisce `['C63', 'C65s', 'NARZO N63']` — "C61" escluso perché
condiviso con altri due codici. Usata al posto di `resolve()` nei tre
punti di `forme_equivalenti()` che espandono un codice o un nome ai suoi
alias, così un nome ambiguo non diventa mai una chiave di ricerca.

Stesso principio applicato a `modelcodes.nome_canonico()` — la funzione
che sceglie IL nome da mostrare per un codice quando ce ne sono più di
uno: ora un nome non condiviso con un altro codice vince su uno condiviso,
prima del criterio alfabetico che prima faceva vincere "C61" su "C63" (le
due stringhe hanno la stessa lunghezza). Effetto collaterale positivo,
verificato: `nome_canonico("RMX3933")` — il caso "gemelli" già noto —
ora sceglie "Note 60" invece di "C61" come nome principale, sempre per lo
stesso motivo: tutti gli altri nomi restano visibili come «noto anche
come», solo quello mostrato per primo cambia, a favore di uno che non è
anche il nome di un telefono diverso.

**Effetto pratico per l'utente**: cercando "realme c63" ora si trova
RMX3939, non più RMX3930. La CPU torna a comparire (Tiger T612, dalla
riga curata verificata questa sessione) perché il codice risolto è
finalmente quello giusto. Verificato con dati reali del dataset (non
solo con la simulazione dei test):

```python
>>> modelcodes.nome_canonico("RMX3939")
'C63'
>>> scan.forme_equivalenti("realme c63")
['realme c63', 'RMX3939', 'C63', 'C65s', 'NARZO N63']   # niente più "C61"
```

### Una nota a margine, non corretta qui: il messaggio di copertura

`web/presenters.py::scheda_tecnica` mostrava "Specifiche hardware non
disponibili per questo modello... realme non ci sono" ogni volta che
`specs.py` (RAM/storage/fotocamera, 11 marche) non copriva il modello —
**anche quando il processore era stato trovato** dalla tabella curata.
Per un modello HONOR/realme coperto a mano (come RMX3939, oggetto di
questo bug) la pagina mostrava la CPU giusta subito sopra una frase che
sembrava contraddirla. Corretto nello stesso giro, perché la stessa
indagine lo aveva reso visibile: ora la nota distingue "processore trovato
a mano, resto della scheda no" da "niente di niente", con parole diverse
per i due casi.

### Verificato, non solo scritto

Due file di test nuovi/estesi, tutti SENZA rete (dataset MobileModels
finto, fonte ufficiale finta che risponde solo al nome ambiguo):
`tests/test_nome_e_codice.py::TestNomeAmbiguoNonReindirizzaAUnAltroTelefono`
(3 test: la forma ambigua sparisce da `forme_equivalenti`, la ricerca non
prende più il firmware del telefono sbagliato, `nome_canonico` preferisce
il nome non ambiguo) e
`tests/test_sito.py::TestNotaCoperturaConChipTrovato` (2 test: la pagina
vera mostra il processore curato e la nota non lo contraddice più).
Suite completa dopo la correzione: **901 test passati, 0 falliti**
(era 896 prima di questo bug).

## Bug reale trovato dall'utente: cercare «RMX3939» rispondeva con i dati di «RMX3930» (2026-08-11, stesso giorno, secondo giro)

Consegnata la correzione qui sopra, l'utente ha cercato direttamente il
codice `RMX3939` sul sito vero (non più il nome «realme c63») e ha
ricevuto una risposta ancora sbagliata, ma diversa e più confusa: titolo
«C65s», chip corretto (Unisoc Tiger T612), ma la riga «aggiornamenti»
diceva testualmente *"RMX3939 — stesso dispositivo di «realme C61»,
codice RMX3939: realme C61 (RMX3930) — Android 14 di fabbrica..."* — un
codice che dichiara di essere se stesso ma cita, fra parentesi, il codice
di un ALTRO telefono.

### La causa: stesso principio, percorso di codice diverso

Il primo bug era nel dataset community (`modelcodes.py`, usato da
`scan.py::forme_equivalenti`). Questo è un bug GEMELLO ma indipendente,
nello scraper della pagina ufficiale realme (`core/sources.py`), che ha
la sua PROPRIA logica di espansione nomi↔codici, separata da
`modelcodes.py`.

Verificato leggendo la pagina ufficiale vera
(`https://www.realme.com/global/legal/AndroidSecurityAdvisories`): la
sigla «C61» compare **due volte**, in punti distinti — una riga a sé
nella tabella Android Enterprise Recommended (legata a un proprio codice
nell'elenco trimestrale) e, separatamente, dentro il gruppo composto di
RMX3939 nello stesso elenco trimestrale. La pagina ufficiale realme
riproduce quindi lo stesso tipo di collisione di nome del dataset
community — non è un'invenzione di terzi, è la fonte più autorevole del
progetto che lo fa davvero.

Ma la causa immediata di QUESTO bug non era `core/sources.py::_lookup_realme`
(quella funzione aveva già un suo filtro anti-ambiguità, funzionante) —
era `core/sources.py::expand_query()`, la funzione che genera le "forme
equivalenti" passate a OGNI fonte strutturata (non solo realme). Al suo
interno c'era una chiamata diretta e non filtrata:

```python
nomi = modelcodes.resolve(codice)      # NON resolve_senza_ambiguita
candidati.extend(nomi)
```

`expand_query("RMX3939")` produceva `['RMX3939', 'C61', 'C63', 'C65s',
'NARZO N63']` — con "C61" incluso come FORMA A SÉ STANTE, non solo come
candidato interno di `_lookup_realme`. Il motore di ricerca
(`lookup_model_structured`) prova ogni fonte per OGNI forma della lista:
arrivato a "C61" come forma indipendente, il filtro anti-ambiguità di
`_lookup_realme` non aiuta più, perché "C61" ORA È la query — e "C61" da
solo risolve legittimamente al VERO C61 (RMX3930), che è la risposta
giusta se la domanda fosse stata "C61", ma sbagliata perché la domanda
era "RMX3939".

Due funzioni diverse costruiscono le "forme equivalenti" nel progetto:
`scan.py::forme_equivalenti` (corretta nel giro precedente) e
`sources.py::expand_query` (non toccata, perché non esaminata insieme
all'altra) — la stessa lezione già scritta nel codice altrove nel
progetto ("una correzione applicata in un posto e non cercata negli
altri", `core/scan.py::_identifica_senza_firmware`).

### La correzione, in due parti

**1.** `core/sources.py::expand_query()` ora usa
`modelcodes.resolve_senza_ambiguita(codice)` invece di `resolve(codice)`
nei due punti che espandono un codice ai suoi nomi commerciali (`resolve`
resta, ma solo per capire se il codice è comunque noto — non per
scegliere le forme da aggiungere).

**2.** `core/sources.py::_realme_nomi_ambigui()` — nuova funzione,
l'equivalente di `resolve_senza_ambiguita` ma per la fonte ufficiale
realme (una mappatura codice→gruppo separata dal dataset community).
Usata per filtrare i candidati generati internamente da
`_lookup_realme()` prima di cercarli nella tabella AER, con una verifica
extra a priorità (il codice scritto per esteso in una riga batte sempre
un nome scomposto, ambiguo o no).

### Una correzione al criterio stesso, scoperta testando il fix

La prima versione di `resolve_senza_ambiguita` (e, per lo stesso motivo,
la prima versione di `_realme_nomi_ambigui`) scartava un nome se
**qualunque** altro codice lo rivendicava — "più di un codice = ambiguo".
Misurato sulla suite completa, questo criterio era troppo severo: rompeva
`SM-A325F/M/N → "Galaxy A32"` (tre codici REGIONALI per lo stesso
identico Samsung Galaxy A32 — non un'ambiguità, la normale variante di
mercato) e, sul lato realme, avrebbe rotto `RMX3491/3492/3493 → "realme
9i"` per lo stesso motivo (non ancora coperto da un test, trovato per
analogia mentre si correggeva il primo).

Criterio corretto, verificato: un nome resta valido per un codice solo se
OGNI codice fratello che lo rivendica ha, complessivamente, lo **stesso**
insieme di nomi (community) o lo stesso gruppo ufficiale scomposto
(realme) — non basta contare quanti codici condividono il nome, conta se
quei codici sono davvero lo stesso telefono. Verificato con dati reali:

```python
>>> modelcodes.resolve_senza_ambiguita("RMX3939")
['C63', 'C65s', 'NARZO N63']          # "C61" ancora escluso, giusto
>>> modelcodes.resolve_senza_ambiguita("SM-A325F")
['Galaxy A32']                         # non più svuotato, corretto
>>> sources._realme_nomi_ambigui()
{'c61'}                                # non include "realme 9i"
```

### Verificato, non solo scritto

Nuova classe di test, senza rete, che riproduce ESATTAMENTE la struttura
a due voci della pagina ufficiale vera (una riga AER a sé stante più due
voci trimestrali che condividono «C61»):
`tests/test_core.py::TestRealmeNomeCondivisoDaDueCodici` (4 test: RMX3939
non prende più i dati di RMX3930; RMX3930 continua a trovare i propri;
«c61» è nell'insieme dei nomi ambigui; «C63» e «Narzo 63», scomposti dallo
stesso gruppo, non lo sono). Suite completa dopo la correzione: **905
test passati, 407 subtest passati, 0 falliti** (era 901 prima di questo
bug).

## RMX3933: scheda tecnica assente per un codice, presente per il nome — e la scelta del nome a chi ha il telefono (2026-08-12)

### Il punto di partenza: due sessioni divergenti

Fra il giro precedente (v13-v15 di questa sessione, "Code61/C63/gemelli
di RMX3939") e questo, un'altra sessione — con accesso di rete pieno, che
questo ambiente non ha verso `versus.com`/`realme.com`/
`storage.googleapis.com` — aveva lavorato **indipendentemente sullo
stesso repository**: `core/versus.py` (nuovo, il ripiego su versus.com
per HONOR/realme/Huawei/Nothing), `core/aer_catalog.py` (nuovo, il
catalogo Android Enterprise Recommended di Google), ottimizzazioni serie
alla velocità di ricerca (v49-v50). Quel lavoro non includeva ancora la
pagina di confronto (v15 di questa sessione): le due basi sono state
riconciliate prendendo il caricamento più recente come base e
riapplicando sopra la pagina di confronto, invece di scegliere l'una o
l'altra.

### Il bug segnalato dall'utente, sul sito vero

Cercando **«rmx 3933»** compariva «Note 60s» come titolo, con «Note 60»
elencato come nome gemello — corretto, RMX3933 ha davvero più nomi
commerciali veri (vedi il giro precedente su RMX3939/C61/C63). Ma
cliccando sul gemello «Note 60» **la scheda tecnica appariva**, mentre
cercando direttamente il codice **non c'era**: stesso telefono, stesso
codice, due risposte diverse a seconda di come veniva scritta la
domanda.

### La causa: `versus.marca_scoperta` guarda solo la prima parola del testo

`core/specs.py::_ripiego_esterno()` (il punto che interroga versus.com
quando il catalogo GSMArena non copre la marca) decide se procedere
guardando se il testo che riceve **comincia** con «realme», «narzo»,
«honor», «huawei» o «nothing» (`versus.marca_scoperta`). Un codice
(«RMX3933») non lo scrive mai. E il nome canonico scelto da
`modelcodes.nome_canonico` per quel codice — «Note 60s», il più corto fra
i nomi veri — nemmeno: nessuno dei nomi brevi di RMX3933 porta la marca
in testa. Solo «realme Note 60» (una delle forme risolte, con la marca
scritta per esteso) la superava.

Misurato leggendo il codice, non indovinato: `web/presenters.py::
scheda_tecnica()` calcolava già una marca affidabile — quella del
catalogo AER ufficiale di Google (`aer_catalog.lookup(codice).
get("brand_aer")`, non indovinata dal testo — è la fonte che ha dato
origine a `core/aer_catalog.py`) — ma non la passava mai a `specs.cerca`
né a `soc.per_modello`. Il dato giusto c'era già in mano e restava
inutilizzato.

### La correzione, in tre punti

1. `core/specs.py::_ripiego_esterno()` e `cerca()` accettano ora un
   parametro `marca` opzionale: se il testo grezzo non basta da solo
   (primo giro, comportamento invariato), un secondo giro costruisce il
   nome con `versus.con_marca(nome, marca)` usando la marca esplicita,
   prima di arrendersi.
2. `core/soc.py::per_modello()` accetta lo stesso parametro, per lo
   stesso motivo: anche il chip passa dall'ultima spiaggia su versus.com.
3. `web/presenters.py::scheda_tecnica()` calcola `marca_aer` PRIMA di
   chiamare `specs.cerca`/`soc.per_modello` (non dopo, come faceva) e la
   passa a entrambi.

Verificato con `versus.scheda_grezza` sostituito da un doppio finto (vedi
`tests/test_specs.py::TestRipiegoEsternoConMarca` e
`tests/test_presenters.py`): senza `marca`, un codice o «Note 60s» non
trovano niente (comportamento di prima, invariato); con la marca
dell'AER, il secondo giro prova «Realme Note 60s» prima di arrendersi, e
lo trova.

### La scelta del nome: non un'euristica migliore, la scelta a chi ha il telefono

RMX3933 resta insieme «C61», «Note 60», «Note 60s», «NARZO N61» —
verificato cercando il modello su più fonti indipendenti (rivenditori,
DeviceAtlas, manuali): «Note 60» è il nome più diffuso a livello globale,
ma almeno un rivenditore lo vende come «Note 60s», e nessuna fonte dice
con certezza quale sia «il» nome per il mercato di chi lo sta cercando.
Non è un caso da risolvere con un algoritmo migliore — significherebbe
indovinare — è il caso per cui esiste la correzione a mano descritta
sotto.

## Correzione a mano del nome commerciale (2026-08-12)

Richiesta esplicita dell'utente: poter dire quale, fra i nomi veri di un
codice, è quello giusto per il telefono che ha in mano — e farlo
ricordare per ogni ricerca futura di quel codice.

**Design**: non un campo di testo libero. Le opzioni proposte sono SOLO i
nomi già verificati dal dataset per quel codice (`risultato.gemelli`, la
stessa lista già mostrata come "noto anche come" — vedi il giro
precedente su RMX3939): un campo libero rischierebbe di far salvare un
refuso o un nome inventato come se fosse un dato ufficiale, l'esatto
contrario della regola "meglio saltare che indovinare" che guida questo
progetto.

**Persistenza**: nuova tabella `nomi_modello` (`core/storage.py`),
`codice → nome`, con le funzioni `set_nome_modello`/`get_nome_modello`/
`get_nomi_modello`. Stessa idea di `imeicheck.aggiungi_tac` (una
correzione verificata da una persona vince su ogni fonte scaricata),
applicata al nome invece che al modello di un TAC. Un nome vuoto
CANCELLA la correzione (torna alla scelta automatica) invece di salvarne
una vuota.

**Dove si applica**: `web/main.py::_cerca_davvero()`, come ULTIMO
passaggio — dopo la convergenza col nome d'archivio, così la correzione
vince anche su quello. Il codice a cui agganciarsi si cerca con
`_codici_del_risultato(query, nome)` — la stessa funzione già usata da
`_nomi_gemelli` — non con `codice` (il `model_code` della fonte) da
solo: così la correzione vale cercando «RMX3933» O «Note 60» O
qualunque altro nome vero dello stesso codice, non solo con la forma
scritta la prima volta. Usare una terza via per trovare il codice,
invece di riusare quella già esistente, sarebbe stata esattamente la
famiglia di bug ("due funzioni che fanno la stessa cosa in due modi
diversi") che questo progetto ha già dovuto correggere due volte in
questa sessione.

**Interfaccia**: un `<details>` chiuso di default sotto i "gemelli" nella
pagina di ricerca (`web/templates/ricerca.html`), con un menu a tendina
dei nomi veri e un tasto salva; se una correzione è già attiva, anche un
tasto per tornare alla scelta automatica. Nuova rotta `POST /modello/
correggi`, che salva e svuota la memoria corta della ricerca (stessa
ragione di `/tac/salva`: senza, la ricerca successiva risponderebbe
ancora dalla cache con il nome di prima).

Verificato end-to-end con un codice di prova (`tests/test_sito.py::
TestCorrezioneNomeModello`, 5 test): senza correzione mostra il nome
della fonte; la correzione salvata diventa il nome mostrato; vale anche
cercando con un ALTRO nome vero dello stesso codice (il punto della
funzionalità); si può tornare alla scelta automatica; la memoria corta
si dimentica dopo il salvataggio.

### Verificato, non solo scritto

Suite completa dopo tutte le correzioni di questo giro: **980 test
passati, 407 subtest passati, 0 falliti** (era 954 all'inizio del giro,
sulla base ricevuta da Code).

## RMX3933, secondo giro: scheda ancora legata alla forma scritta, e due nomi mostrati come se fossero due telefoni (2026-08-12)

Il fix precedente (marca dal catalogo AER) non bastava per RMX3933:
quel codice specifico **non è nel catalogo AER** — non tutti i modelli
realme aderiscono al programma Android Enterprise Recommended — quindi
`marca_aer` restava vuota per QUALSIASI forma del nome, non solo per
quelle senza la marca in testa. La scheda continuava a dipendere da
cosa, per puro caso, l'utente aveva scritto o cliccato.

**Correzione**: `web/presenters.py::scheda_tecnica()` ora ha un secondo
ripiego, dopo l'AER: se `marca_aer` resta vuota, guarda TUTTI i nomi
veri del codice (`modelcodes.resolve(codice)` — la stessa fonte già
usata per i "gemelli", non una nuova euristica) e chiede a
`versus.marca_scoperta` se uno di questi la dichiara. Per RMX3933 basta
«NARZO N61»: `versus.marca_scoperta` riconosce «narzo» come sinonimo di
realme anche senza la parola «realme» scritta da nessuna parte. Con
questo, la marca — e quindi la scheda — non dipende più da QUALE dei
nomi veri sia mostrato in un dato momento: tutti convergono alla stessa
risposta.

**Il secondo problema, distinto**: `resolve("RMX3933")` include anche
«realme Note 60», che è «Note 60» con la marca scritta davanti — non un
telefono diverso, la stessa identica forma commerciale. Prima di questo
fix, `_nomi_gemelli` (`web/main.py`) la mostrava come una voce "gemella"
a sé stante, insieme a «Note 60» semplice: due voci per la stessa cosa,
che fanno sembrare che ci siano due telefoni da scegliere quando ce n'è
uno solo. «Note 60»/«Note 60s» restano invece due voci VERE e distinte
(due telefoni regionali diversi, non la stessa forma scritta in due
modi).

**Correzione**: `_nomi_gemelli` ora raggruppa i nomi veri per chiave
normalizzata (`modelcodes._normalize_name`, che toglie il prefisso di
marca — esiste già per questo motivo, vedi il suo docstring) e tiene una
sola forma per gruppo, la più corta — stessa preferenza già usata da
`nome_canonico`. La stessa lista alimenta anche il menu della
correzione a mano del nome (vedi sotto): questo fix la rende
automaticamente più pulita, senza toccare quel codice.

Verificato:
```python
>>> modelcodes.resolve("RMX3933")
['C61', 'Note 60', 'Note 60s', 'NARZO N61']   # oggi; il dataset community
                                                # è vivo e può includere o
                                                # meno «realme Note 60»
                                                # a seconda del giro
>>> versus.marca_scoperta(*modelcodes.resolve("RMX3933"))
'Realme'                                       # trovata via «NARZO N61»
```

Test nuovi: `tests/test_nome_e_codice.py` (+2, il raggruppamento dei
gemelli), `tests/test_presenters.py::TestMarcaDaiNomiVeriQuandoLAerNonBasta`
(3, il ripiego sui nomi veri quando l'AER non basta).

### Verificato, non solo scritto

Suite completa dopo questo secondo giro: **985 test passati, 407
subtest passati, 0 falliti** (era 980 dopo il primo giro dello stesso
bug).

## RMX3933, terzo giro: «realme Note 60» non può comparire come opzione perché non esiste nel dataset (2026-08-12)

Segnalato di nuovo dall'utente, guardando il sito vero: il menu «Non è
il nome giusto?» per RMX3933 mostra «Note 60s», «C61», «Note 60»,
«NARZO N61» — ma non «realme Note 60», che è il nome con cui l'utente
riconosce il telefono che ha in mano.

**Causa, verificata sul dataset reale (non supposta)**:

```python
>>> modelcodes.resolve("RMX3933")
['C61', 'Note 60', 'Note 60s', 'NARZO N61']
```

Nel dataset live, oggi, NESSUNA delle forme vere di RMX3933 scrive
«realme» per esteso — solo «NARZO N61», che `versus.marca_scoperta`
riconosce come sinonimo. Il fix del giro precedente (leggere la marca
dai nomi veri via `modelcodes.resolve`) risolve correttamente il
problema della SCHEDA TECNICA assente (la scheda si trova comunque,
qualunque nome si scelga — vedi la sezione «1bis» sopra), ma non può
far comparire nel menu una stringa che il dataset non ha mai scritto:
i «gemelli» sono, per design, solo forme VERIFICATE (vedi il docstring
di `_nomi_gemelli`) — inventarne una lì significherebbe spacciare un
nome non verificato per uno che lo è.

**Fix**: nuova funzione `web/main.py::_opzioni_correzione(nome, gemelli,
codice)`, usata SOLO per popolare il `<select>` della correzione a
mano — non le pastiglie «noto anche come», che restano `gemelli` puro.
Prende i gemelli veri e, se si conosce la marca del codice
(`web/presenters.py::marca_probabile` — la stessa funzione ora estratta
e condivisa fra `scheda_tecnica` e questo nuovo uso, non due euristiche
indipendenti) e nessuna forma già la scrive, aggiunge in coda una forma
sintetica «Marca + nome più corto» (`versus.con_marca`). Per RMX3933:
«Realme Note 60».

**Perché è comunque sicuro scegliere quella forma sintetica**: la
scheda tecnica si calcola dal CODICE (`P.scheda_tecnica` chiama
`marca_probabile(codice, nome)`), non dal nome mostrato — quindi
qualunque forma si scelga nel menu, sintetica o no, resta collegata
alla stessa identica scheda. È esattamente la garanzia richiesta
dall'utente: «dai la possibilità di scegliere come nome principale uno
messo a mano ma che sia comunque collegabile ad una scheda tecnica».

Verificato:
```python
>>> P.marca_probabile("RMX3933")
'Realme'
>>> versus.con_marca("Note 60", "Realme")
'Realme Note 60'
```

Test nuovi: `tests/test_nome_e_codice.py::TestOpzioniCorrezione` (4),
`tests/test_sito.py::TestCorrezioneNomeModelloConMarcaSintetica` (2,
end-to-end: la forma sintetica compare nel menu ma non fra i gemelli
dichiarati, e si può scegliere come nome principale).

## Pagina di confronto: una tabella sola, non due blocchi slegati (2026-08-12)

Segnalato dall'utente: la pagina `/confronto` sembrava confusa — non
si capiva bene dove finisse un modello e cominciasse l'altro, scorrendo
dalla foto giù fino alle caratteristiche.

**Causa**: foto e nome vivevano in un `<div class="confronto-intestazioni">`
(una griglia CSS a due colonne), separato dalla `<table>` dei dati
sottostante. Le due colonne dell'intestazione e le due colonne della
tabella erano allineate per coincidenza (stesse proporzioni), non per
struttura: nessuna riga visiva le teneva insieme.

**Fix**: foto e nome sono entrate DENTRO la stessa `<table>`, come righe
di `<thead>` (`web/templates/confronto.html`), con un `<colgroup>` a
fissare le larghezze delle tre colonne (etichetta, modello A, modello
B) via `table-layout: fixed`. Un bordo sinistro di 3px su ogni cella
della terza colonna — foto, nome, e ogni riga di caratteristica, essendo
la stessa tabella dall'inizio alla fine — diventa così un'unica linea
verticale continua che parte dalla foto e arriva fino all'ultima riga,
il «divisorio netto» richiesto. Su schermi stretti la tabella non si
spezza più nel formato a blocco generico (`.tabella` su mobile): scorre
orizzontalmente dentro un contenitore dedicato, restando una tabella
vera a qualunque larghezza.

Nessun dato o funzionalità è cambiato: stessa `_confronta`, stessi
`confronto.righe`, stessa evidenziazione delle differenze — solo la
struttura HTML/CSS che le mette in pagina.

## Nota per chi riprende da qui: perché il sito in produzione sembrava non avere nessuno dei fix precedenti

L'utente ha segnalato, con screenshot del sito vero, che «non c'è nulla
di quello che abbiamo lavorato nell'ultimo commit» — né il fix della
scheda assente, né la correzione a mano del nome. Verificato: gli
screenshot corrispondono esattamente al comportamento PRIMA di tutti i
fix di questa sessione (nessun nome «realme» proposto, nessuna scheda
per Note 60s, ecc.).

Non è un regresso: questa sessione (Cowork, sandbox) non ha accesso a
git/push/deploy. Ogni consegna è uno zip scaricato dall'utente
(`android-updater-fix-12ago-vNN.zip`), che deve essere applicato al
repository vero e ridistribuito (dall'altra sessione con accesso di
rete e git, o manualmente) prima che Render lo serva. Finché quel passo
non avviene, il sito in produzione resta fermo alla versione precedente
— per quanti giri di fix si facciano qui. Vale la pena ripeterlo
esplicitamente nel messaggio di consegna, non solo nei documenti.

### Verificato, non solo scritto

Suite completa dopo questo terzo giro: **991 test passati, 407 subtest
passati, 0 falliti** (era 985 dopo il secondo giro).

## Il build su Render falliva quando il repository viene ricreato da zero (2026-08-12)

Segnalato dall'utente con lo screenshot del log di Render: dopo aver
cancellato l'intero repository GitHub e ricaricato tutti i file da capo
(«Add files via upload»), il build Docker falliva con:

```
failed to calculate checksum of ref ...: "/tracker.db": not found
error: exit status 1
```

**Causa**: `Dockerfile` aveva `COPY --chown=app tracker.db ./tracker.db`
— un nome di file ESATTO, non un pattern. `COPY` su un nome esatto
pretende che il file esista nel contesto della build, altrimenti la
build intera fallisce. `tracker.db` normalmente esiste nel repository
perché un workflow di GitHub Actions lo committa ogni ora (vedi il
commento sopra quella riga) — ma un repository appena ricreato da zero
non ce l'ha ancora, e il caricamento manuale di file (né gli zip di
consegna di questa sessione, che lo escludono di proposito perché
contiene dati veri di produzione, non codice) non lo ripristina da
solo.

**La parte importante**: questo file NON serve al funzionamento
dell'app. `web/main._semina_archivio()` (il codice che lo legge
all'avvio) gestisce già perfettamione la sua assenza — vedi il suo
docstring: "nessuna copia nell'immagine" è un ramo previsto, non un
errore, e l'app riparte comunque (da un archivio vuoto che si ripopola
con le scansioni, o dal salvataggio su Gist se configurato). Il file è
solo un'ottimizzazione per evitare un avvio a freddo con l'archivio
vuoto — utile, ma la sua assenza non doveva MAI far fallire l'intera
build e portare giù il sito.

**Fix**: `COPY --chown=app tracker.db* ./` — l'asterisco rende il file
opzionale. Verificato con un test isolato usando lo stesso motore
Docker/BuildKit (non solo letto sulla documentazione): la build
completa con successo sia quando il file manca sia quando è presente
(e in quel caso viene copiato correttamente). Questo chiude anche il
caso più ampio: da ora in poi un repository ricreato da zero, o un
primissimo deploy prima che il workflow orario abbia mai girato, non fa
più fallire il build per questo motivo.

Nessun test Python è interessato da questo fix (è un cambiamento solo
al Dockerfile); verificato direttamente con una build Docker isolata
(`FROM scratch`, per non dipendere dall'accesso di rete a un registro
che questa sandbox non ha).

## RMX3933, quarto giro: la forma sintetica sceglieva la marca sul nome sbagliato (2026-08-12)

Segnalato dall'utente con screenshot del sito vero: nel menu «Non è il
nome giusto?» compariva «Realme C61», non «Realme Note 60» come
richiesto in precedenza.

**Causa**: il fix del terzo giro (vedi sopra) generava UNA SOLA forma
sintetica, scegliendo come base il nome vero più corto fra tutti
(`min(..., key=len)`) — pensato per imitare la stessa preferenza di
`modelcodes.nome_canonico`. Ma «C61» (3 lettere) è più corto di «Note
60» (7), e per RMX3933 nel dataset live risultavano entrambi nomi veri:
la funzione sceglieva «C61» come base e produceva «Realme C61», che non
è il nome con cui chi ha il telefono lo riconosce. Non c'è un modo di
indovinare algoritmicamente QUALE dei nomi veri sia «quello giusto» per
chi cerca — è esattamente il problema che la correzione a mano esiste
per risolvere, quindi scegliere una singola base è già la scelta
sbagliata in partenza.

**Fix**: `_opzioni_correzione` ora genera una forma sintetica per
CIASCUN nome vero (il nome mostrato e ogni gemello), non una sola.
Risultato per RMX3933: sia «Realme C61» sia «Realme Note 60» sia «Realme
Note 60s» sia «Realme NARZO N61» compaiono come opzioni — chi cerca
trova quella che riconosce, qualunque fosse la forma di partenza che
aveva in mente.

Test aggiornati: `tests/test_nome_e_codice.py::TestOpzioniCorrezione`
(riscritti per riflettere la generazione per-candidato, +1 test che
riproduce esattamente il bug segnalato: «Realme Note 60» deve comparire
anche quando «C61» è il nome vero più corto).

## Nome commerciale scritto a mano, quando nessuna forma proposta va bene (2026-08-12)

Richiesta esplicita dell'utente: la stessa via d'uscita già disponibile
per un TAC sconosciuto (`_imei.html`, campo di testo libero — vedi
`imeicheck.aggiungi_tac`) mancava per il nome di un modello. Il menu di
correzione offriva SOLO una scelta fra forme verificate o costruite
dalla marca nota: se nessuna di quelle corrispondeva a quello che
l'utente aveva in mano, non c'era modo di correggere.

**Design**: stesso pattern del TAC — un `<details>` annidato, chiuso di
default («Non trovi il nome giusto? Scrivilo tu»), con un `<input
type="text">` che posta allo STESSO `POST /modello/correggi` e allo
STESSO campo `nome` del menu a tendina: zero cambi lato server, perché
`storage.set_nome_modello` accetta già testo libero (esattamente come
`imeicheck.aggiungi_tac`). A differenza delle forme proposte nel menu —
sempre garantite collegabili a una scheda tecnica (vedi sopra) — un nome
scritto a mano non ha questa garanzia, e il testo nella pagina lo dice
esplicitamente: è un compromesso consapevole, non un effetto collaterale
non dichiarato.

Compare sempre quando c'è un codice a cui agganciare una correzione,
anche se il menu a tendina non ha nessuna alternativa da proporre (un
codice con un solo nome vero e nessuna marca riconosciuta): prima quel
caso non mostrava NESSUNA via di correzione.

Test nuovi: `tests/test_sito.py::TestCorrezioneNomeScrittaAMano` (2,
end-to-end: il campo compare in pagina, un nome scritto a mano si
salva e diventa il nome mostrato).

### Verificato, non solo scritto

Suite completa dopo questo quarto giro: **994 test passati, 407
subtest passati, 0 falliti** (era 991 dopo il terzo giro).

## Un realme 7 senza lettere, e i nomi che il firmware non conosce (2026-08-12)

Segnalato dall'utente facendo dei test veri: un IMEI risolto a un realme 7
mostrava solo «7» come nome, e cercare `m1910f4g` (Xiaomi Mi Note 10)
mostrava «Nessun firmware per «m1910f4g»» sopra una scheda tecnica con la
foto del telefono giusto — nessun nome da nessuna parte, solo il codice
grezzo ripetuto.

### Il realme «7» (`RMX2151`)

**Causa**: non un difetto dell'algoritmo di scelta — «7» è l'UNICO nome
vero che `resolve()` conosce per quel codice (il dataset community
MobileModels registra a volte solo il numero di gamma, senza marca).

**Fix**: `nome_canonico()` ora ripara SOLO il caso in cui il nome scelto
non ha UNA SOLA lettera (quindi non identifica niente da solo), aggiungendo
la marca che il dataset dichiara per quel codice (`marca_dichiarata()`,
mai indovinata). Non tocca `resolve()` né `_build_mobilemodels_index()`:
prefissare la marca a OGNI nome di quel dataset è già stato provato e
misurato peggiorare la coerenza nome/codice (Xiaomi 83% → 49%, vedi il
commento in `_build_mobilemodels_index()`) — qui si ripara solo il
risultato finale, nel solo caso in cui non c'è nulla da confondere perché
non c'è già un nome vero. Verificato sul dataset live: `RMX2151` e
`RMX2155` → «realme 7» (erano «7»); `RMX3933` → «Note 60» e `SM-S921B` →
«Galaxy S24» (nomi con lettere) restano invariati.

### Il codice Xiaomi che non aveva la forma di un codice (`M1910F4G`)

**Causa, più a monte**: `_MODEL_CODE_SHAPES` (`core/sources.py`) non
copriva lo stile classico dei codici Xiaomi — `M` + 4 cifre + lettera +
cifre (`M1910F4G`, `M2007J20CG`, `M2101K6G`...). Nessuna forma comincia
con UNA lettera sola: `looks_like_model_code("M1910F4G")` rispondeva
`False`. Questo non è un dettaglio cosmetico: `looks_like_model_code` e
`_code_candidates` decidono l'instradamento in tutta l'app — la ricerca
sul catalogo firmware Xiaomi, i «gemelli», la correzione del nome — quindi
un codice Xiaomi vero, scritto esattamente come sta sotto la batteria del
telefono, non attivava NESSUNO di questi percorsi. Solo `core/specs.py`
prova il testo senza validarne la forma, ed è per questo che la scheda
tecnica (foto, processore) trovava il telefono giusto mentre il resto
della pagina si comportava come se il codice non fosse mai stato scritto.

**Fix**: aggiunta la forma mancante a `_MODEL_CODE_SHAPES` —
`^M\d{4}[A-Z]\d{1,2}[A-Z]{0,3}$`. Riapre tre percorsi in un colpo solo:
la ricerca firmware Xiaomi per questi codici (prima invisibile), il
riconoscimento «senza firmware» via `modelcodes.resolve()` (già esistente,
ma mai raggiunto), e la correzione del nome.

**Fix complementare, in `_cerca_davvero` (`web/main.py`)**: anche con la
forma del codice riconosciuta, resta possibile che nessuna fonte firmware
E nessun `modelcodes.resolve()` sappia niente di un codice, mentre la
scheda tecnica (un catalogo diverso, con la sua indicizzazione) lo
risolve lo stesso — è il caso letterale di `m1910f4g` prima del fix sopra,
e resta un caso limite possibile anche dopo. Ora, quando non c'è nessun
risultato con firmware ma la scheda tecnica HA risolto un nome diverso
dalla query scritta, quel nome diventa l'intestazione della pagina, con un
messaggio onesto («riconosciuto dalla scheda tecnica, ma nessuna fonte
firmware conosce il codice») invece del solo codice grezzo ripetuto.
Attiva anche i «gemelli» e la correzione del nome per questo caso, prima
disponibili solo quando una fonte firmware rispondeva.

Test nuovi: `tests/test_regressione_ricerca_codice.py::TestCodiceXiaomiStileClassico`
(3, sulla forma del codice) e `tests/test_sito.py::TestNomeDallaSchedaSenzaFirmware`
(3, end-to-end sulla pagina, con una scheda sintetica per non dipendere dal
dataset Xiaomi vero).

## La correzione del nome non sopravviveva a un riavvio (2026-08-12)

Segnalato dall'utente: «assicurati che quando correggo il nome il
risultato si salvi perché sembra che non lo faccia».

**Causa**: il salvataggio in sé funzionava — la correzione finiva subito
nella tabella `nomi_modello` di `tracker.db` — ma quel database vive in
`/tmp` (`Dockerfile`, `DB_PATH=/tmp/tracker.db`, disco effimero per
scelta dichiarata) e la SOLA copia duratura è il backup su Gist
(`core/backup.py`), caricato prima SOLO a fine di ogni scansione
periodica tramite `salva_se_serve()`, non più spesso di
`BACKUP_EVERY_MINUTES` (30 di default). Sul piano gratuito di Render il
servizio si addormenta dopo circa 15 minuti senza visite, e il thread di
scansione dorme con lui (`render.yaml` lo dichiara esplicitamente): una
correzione fatta poco dopo l'ultimo backup periodico poteva restare SOLO
nel database locale ed essere persa al primo riavvio successivo — che su
questo piano è la norma, non l'eccezione. Da fuori sembrava un
salvataggio «che non funziona», ma il salvataggio non era mai stato il
problema: lo era il tempismo del backup, sganciato dalla correzione.

**Fix**: `POST /modello/correggi` e `POST /tac/salva` ora fanno partire
subito un `backup.salva()` in un thread separato (`_backup_subito()` in
`web/main.py`), invece di aspettare il prossimo giro di scansione — stessa
idea di `/scansione`, che non blocca la richiesta HTTP in attesa. Una
correzione verificata da una persona è rara e piccola: vale la pena
caricarla subito, ignorando l'intervallo minimo pensato per i backup
automatici. Se il backup non è configurato (`BACKUP_GIST_ID`/
`BACKUP_GITHUB_TOKEN` assenti nel pannello Render), `backup.salva()` torna
`False` senza fare niente — non cambia niente per chi non ha attivato
questa funzione, ma **è la condizione da cui dipende tutto questo fix**:
senza quei due segreti configurati su Render, nessuna correzione
sopravvive a un riavvio, con o senza questo fix, perché non esiste nessuna
copia duratura da nessuna parte.

Test nuovi: `tests/test_sito.py::TestCorrezioneAvviaSubitoIlBackup` (2,
verificano che `backup.salva` venga chiamato entro 2 secondi da entrambe
le rotte, con `backup.salva` sostituito da una finta per non parlare con
GitHub durante i test).

## `CPH2781` mostrava «F31» invece di «A6 Pro»: una tabella curata per le ambiguità vere (2026-08-12)

Segnalato dall'utente, con un'istruzione esplicita: «sistema dalla
radice». Terza volta che la stessa CLASSE di problema si presenta (dopo
RMX3933/C61 e la sua correzione a mano) — e la richiesta, ragionevole, è
di non dover ricorrere alla correzione manuale ogni volta che capita un
codice con più nomi commerciali veri.

**Verifica, non supposizione**: `resolve("CPH2781")` restituisce
`['OPPO F31', 'OPPO A6 Pro']` — non un errore del dataset. Confermato con
più fonti indipendenti (GSMArena Cina/India, oppo.com/en, DeviceAtlas,
Gizmochina, GSMchoice): stesso hardware (Dimensity 6300, display 6.57"
50MP+2MP, batteria 7000mAh) venduto come «OPPO F31 5G» in Cina e come
«OPPO A6 Pro 5G» nei mercati Global/India/Medio Oriente. Nessuno dei due
nomi è sbagliato — `nome_canonico()` sceglieva «F31» solo perché è più
corto (regola 4), un criterio che funziona quando un nome è un suffisso
di mercato dell'altro ma non quando sono due nomi commerciali del tutto
distinti, e che non ha modo di sapere che per un'app usata in Italia il
nome Global è quello riconoscibile.

**La scelta, e perché non è "la correzione manuale, di nuovo"**: chiedere
a ogni persona di correggere a mano lo stesso codice, verificato una
volta, per sempre, non è una radice — è la stessa toppa ripetuta
all'infinito. **Nuovo file `data/nomi_modello.csv`**, stessa filosofia di
`data/soc_modelli.csv` («curata a mano, corta di proposito, solo righe
verificate»): una tabella che SCEGLIE fra nomi che il dataset conferma
già, senza mai inventarne uno nuovo — `nome_canonico()` applica una riga
SOLO se il nome scritto è ancora fra quelli che `resolve()` restituisce
per quel codice, quindi un aggiornamento del dataset a monte disattiva da
solo una riga ormai sbagliata invece di imporla ciecamente. A differenza
della correzione manuale di un utente (tabella `nomi_modello` di
`tracker.db`, sul disco effimero — vedi la sezione sopra), questo file
viaggia nel repository come il codice: sopravvive a un reset completo
della repo, per sempre, in ogni build.

Prima riga: `CPH2781 → OPPO A6 Pro`. Il nome cinese («OPPO F31») resta
comunque visibile come «gemello» nel menu di correzione, per chi lo
riconosce con quel nome.

**Sulla richiesta più ampia** — «fatti aiutare in parallelo da Google
search... per migliorare mano a mano» — questo file è la risposta
scelta, non un rifiuto della richiesta: la ricerca (fatta con più fonti
indipendenti, non una sola pagina) è esattamente il lavoro da fare in
parallelo, ma il risultato entra nell'app come RIGA VERIFICATA E
FIRMATA in un file che chiunque può rileggere e contestare — non come
un suggerimento AI applicato silenziosamente in tempo reale. È lo stesso
principio già scritto in `core/aiquery.py` per il tasto «+AI»: un
sistema esterno (una persona con Google, o un modello linguistico) non
diventa mai una fonte da sola — può solo scegliere fra candidati che i
cataloghi del progetto hanno già, e quella scelta viene ricontrollata,
mai presa alla lettera. Aggiungere righe a questo file resta un lavoro
da fare consapevolmente, una alla volta, non un processo automatico — ma
è un lavoro che si fa UNA volta per codice, non a ogni ricerca.

Test nuovi: `tests/test_nome_e_codice.py::TestIdentitaDalCodice`
(+3: la tabella vince su due nomi ugualmente veri, non inventa un nome
che il dataset non conferma più, il file vero su disco contiene
davvero la riga CPH2781) e `tests/test_nome_e_codice.py::TestCaricaOverrideNomi`
(5, il parser del CSV: lettura, righe di commento, righe incomplete,
maiuscole, testo vuoto).

### Verificato, non solo scritto

Suite completa dopo questo giro: **1013 test passati, 416 subtest
passati, 0 falliti** (era 997 all'inizio di questo giro).

## La pagina Diagnostica non diceva niente sul backup esterno (2026-08-12)

Segnalato dall'utente con screenshot della pagina Diagnostica vera, dopo
il fix del backup immediato (sezione sopra): non c'era NESSUN modo di
vedere da fuori se il backup fosse configurato e se l'ultimo salvataggio
fosse davvero riuscito. Va detto con chiarezza: la risposta precedente di
questa sessione affermava che una sezione così esistesse già in
Diagnostica — non era vero, era un'assunzione sbagliata (l'esistenza di
`core/backup.py::stato()` non implica che qualcosa la mostri), e questo
screenshot l'ha corretta.

**Fix**: nuovo presenter `web/presenters.py::stato_backup()`, nuova
sezione «Backup esterno» in `diagnostica.html` (stessa forma a righe
`<th>/<td>` delle altre due tabelle della pagina — nessun elemento
nuovo da imparare). Mostra stato (Non configurato / Attivo / Errore /
Configurato ma in attesa del primo salvataggio), ultimo salvataggio
riuscito, ultimo ripristino, ultimo esito testuale.

**Un dettaglio non ovvio, gestito esplicitamente**: `core/backup.py`
inizializza `_stato["ultimo_esito"]` a `"non configurato"` a ogni avvio
del processo, e resta così finché `salva()`/`ripristina()` non girano
almeno una volta in quella sessione — quindi un backup CONFIGURATO ma
non ancora tentato da quando il servizio si è riavviato mostrerebbe
alla lettera "non configurato", che è fuorviante: sembra un problema di
configurazione quando è solo che non è ancora successo niente da
riportare. Il presenter distingue esplicitamente questo terzo stato
("Configurato, in attesa del primo salvataggio") da "Non configurato"
vero e da "Errore" (un tentativo c'è stato, ma non è riuscito).

Test nuovi: `tests/test_presenters.py::TestStatoBackup` (4, i quattro
stati), `tests/test_sito.py::
TestLePagineSiDisegnano::test_la_diagnostica_mostra_lo_stato_del_backup`
(1, end-to-end).

### Verificato, non solo scritto

Suite completa dopo questo giro: **1018 test passati, 416 subtest
passati, 0 falliti** (era 1013 all'inizio di questo giro).

## Configurare il backup da tre pagine a una (2026-08-12, stesso giorno)

Segnalato dall'utente subito dopo il fix precedente: **"dice che non è
configurato nonostante abbia ascoltato le tue istruzioni. metti il tool
in diagnostica e semplifica tutto"**. La configurazione manuale
richiedeva tre passaggi su tre siti diversi (creare un token su GitHub,
creare a mano un Gist privato, incollare due valori su Render) — tre
occasioni distinte di sbagliare qualcosa o di non aver ancora aspettato
il riavvio del servizio, e nessun modo diretto di distinguere "ho
sbagliato un passaggio" da "ho fatto tutto giusto ma Render non si è
ancora riavviato".

**Fix**: `core/backup.py` aveva già da tempo tre funzioni scritte ma mai
collegate a nessuna route (`verifica_token`, `crea_archivio`,
`prova_completa` — confermato con `grep -rln` che non comparivano fuori
da `backup.py` e dai suoi test). Questo giro le collega:

- `POST /diagnostica/backup/crea` — incolli un token, la rotta lo
  verifica, crea l'archivio privato su Gist e ci scrive/rilegge un
  valore di prova per confermare che funziona davvero, tutto in una
  chiamata. Il modulo compare in Diagnostica solo quando lo stato è
  "Non configurato" — a configurazione già attiva non ha senso
  riproporlo.
- `POST /diagnostica/backup/salva` — un pulsante "Salva adesso, per
  verificare" che esegue `backup.salva()` in modo sincrono (a differenza
  di `_backup_subito()` nel percorso di ricerca, che è volutamente
  fire-and-forget: qui invece è un'azione diagnostica esplicita, ha
  senso aspettare l'esito vero).

**Quello che resta manuale, e perché**: l'ultimo passaggio — incollare
`BACKUP_GIST_ID` e `BACKUP_GITHUB_TOKEN` nel pannello Environment di
Render — non si può automatizzare da qui: non c'è accesso alle API di
Render, ed è fuori scopo (richiederebbe un secondo insieme di
credenziali, quelle di Render, con più privilegi di quanto serva).
Restano quindi due passaggi invece di sei, con l'esito di ognuno
mostrato subito invece di scoprirlo solo al prossimo riavvio.

**Sicurezza**: il token non viene mai scritto su disco né loggato —
vive solo nella singola richiesta HTTP che lo verifica; il campo del
modulo è `type="password"`; il token non viene mai ririnviato nella
pagina di risposta (si dice solo "riusa lo stesso token appena
incollato qui sopra" invece di ripeterlo).

**Perché probabilmente il tentativo manuale dell'utente mostrava
ancora "Non configurato"**: due spiegazioni più probabili, non
verificabili da qui — (a) questa sessione non ha accesso a Render o al
repository reale, quindi il fix precedente (la sezione "Backup
esterno" stessa) potrebbe non essere ancora stato applicato lì, oppure
(b) le variabili sono state salvate ma Render non aveva ancora finito
il riavvio automatico. Il nuovo pulsante "Salva adesso" serve proprio a
questo: dà un modo diretto di controllare la configurazione attuale
invece di aspettare il prossimo ciclo di scansione.

Test nuovi: `tests/test_sito.py::TestDiagnosticaConfigurazioneBackup`
(6 — il modulo compare solo se non configurato, il pulsante "Salva
adesso" compare solo se configurato, token valido crea l'archivio e
mostra i due valori da copiare senza mai rimostrare il token, token
non valido mostra l'errore e non crea niente, "Salva adesso" mostra
l'esito vero sia in successo che in fallimento).

### Verificato, non solo scritto

Suite completa dopo questo giro: **1024 test passati, 416 subtest
passati, 0 falliti** (era 1018 all'inizio di questo giro).

## Stato «Errore» senza via d'uscita: chi sbaglia un valore restava bloccato (2026-08-12, stesso giorno, dopo il primo deploy del v58)

Appena il v58 è arrivato in produzione, l'utente ha provato «Salva
adesso» e ha ricevuto `Errore` — `GitHub ha risposto 401: {"message":
"Bad credentials"}`. Screenshot del pannello Environment di Render:
`BACKUP_GIST_ID` e `BACKUP_GITHUB_TOKEN` avevano **lo stesso identico
valore**, un ID di Gist (32 caratteri esadecimali) incollato in
entrambe le variabili invece che un vero token GitHub (che comincia
per `ghp_` o `github_pat_`) nella seconda.

Non era un bug nel codice: il token era davvero sbagliato, e GitHub ha
correttamente rifiutato la richiesta. Il problema stava nell'interfaccia
appena costruita: lo stato «Errore» mostrava SOLO il pulsante «Salva
adesso» (la stessa condizione `else` che copriva anche «Attivo» e
«Configurato, in attesa...»), che riprova con la STESSA configurazione
sbagliata e fallisce sempre allo stesso modo — nessun modo, da quella
pagina, di rifare la configurazione senza uscire e modificare Render a
mano, senza nemmeno sapere quale dei due valori fosse quello sbagliato.
Esattamente il tipo di vicolo cieco che «semplifica tutto» (la
richiesta che ha originato il punto precedente) doveva evitare.

**Fix**: `diagnostica.html`, la condizione sul modulo di configurazione
passa da un `if/else` a due `if` indipendenti — il modulo "Configura il
backup"/"Rifai la configurazione" ora compare per DUE stati
(`Non configurato` **e** `Errore`), il pulsante "Salva adesso" per
tutti tranne `Non configurato`. In stato `Errore` compaiono entrambi:
"Salva adesso" per riprovare (utile se l'errore era temporaneo, per
esempio un problema di rete lato GitHub) e "Rifai la configurazione"
(stesso modulo di prima, titolo diverso, più una nota che spiega
esplicitamente il sospetto più probabile — valori scambiati o
duplicati) per ripartire da un token nuovo senza dover indovinare quale
dei due valori salvati fosse sbagliato.

Test nuovo: `tests/test_sito.py::TestDiagnosticaConfigurazioneBackup::
test_in_errore_compaiono_sia_salva_adesso_sia_rifai_la_configurazione`.
Aggiornato anche `test_a_configurazione_attiva_compare_salva_adesso_non_il_modulo`
per verificare che "Rifai la configurazione" NON compaia quando il
backup è già attivo (nessuna ragione di riproporre il modulo a chi
funziona).

### Verificato, non solo scritto

Suite completa dopo questo giro: **1025 test passati, 416 subtest
passati, 0 falliti** (era 1024 all'inizio di questo giro).

## La ricerca priorizza la variante europea, non quella con la build più recente (2026-08-12, stesso giorno)

Richiesta esplicita dell'utente: «per migliorare la ricerca potresti
mettere in priorità i modelli europei? così se cerco un modello non mi
spunta un modello a caso ma in priorità quello europeo».

**Cosa succedeva prima, verificato non dedotto**: per Samsung la
priorità europea esisteva GIÀ, da tempo (`_ORDINE_MERCATI_SAMSUNG`,
codici che finiscono per `B`/`F`/`E`) — un fix precedente, documentato
più sopra in questo file. Per OnePlus/OPPO no: il tracker ARB
(`core/oplus_arb.py`) restituisce, per lo stesso telefono, una riga per
regione — «OnePlus 13» è `CPH2653` in Europa/Global e `CPH2649` in
India, con build che non procedono di pari passo, ESATTAMENTE il caso
che l'utente descrive. `_lookup_oplus_arb` (`core/sources.py`)
ordinava quelle righe per build più recente, non per regione: con la
fixture registrata (`tests/fixtures/oplus_arb_readme.md`), l'India ha
`16.0.7.201` contro `16.0.5.703` dell'Europa, quindi vinceva l'India —
verificato con uno script che riproduce l'intera catena fino a
`web/main.py::_cerca_davvero` (`migliore = strutturati[0]`), non solo
letto sul codice.

**Fix**: `_rango_regione_arb()`, stessa idea di
`_rango_mercato_samsung()` ma sulla colonna `Region` del tracker (che
scrive per esteso «Europe», «Global», «India»...). Ordine dichiarato:
Europa, poi Global (la build senza mercato specifico, la più vicina a
un telefono europeo quando l'Europa non ha una riga propria), poi le
altre nell'ordine di prima (build più recente). TUTTE le regioni
restano nel risultato — nessuna sparisce, l'informazione multi-regione
resta il valore di questa fonte per un parco di test misto — cambia
solo QUALE diventa il risultato principale mostrato dalla ricerca.

**Un dettaglio verificato prima di fidarsi, non assunto**: l'app somma
i risultati di più fonti e li riordina per data
(`core/scan.py::search_model`, `items.sort(...)`); c'era il rischio
concreto che quel riordino successivo cancellasse l'ordine appena
scelto qui. Verificato con lo stesso script end-to-end che
`core/util.py::now_iso()` tronca ai secondi (`replace(microsecond=0)`),
quindi tutte le righe normalizzate nella stessa richiesta ottengono lo
STESSO `first_seen`, e l'ordinamento a parità di data in Python è
stabile: l'ordine per regione sopravvive intatto fino alla pagina.
Senza questa verifica il fix sarebbe sembrato scritto ma silenziosamente
inefficace.

**Controllato ma non toccato, con la ragione**:
* **Catalogo Android Enterprise Recommended** (realme, HONOR, Motorola,
  alcuni Samsung/Xiaomi/OPPO) — ha già un campo `regions` per
  dispositivo, ma verificato sul fixture vero
  (`tests/fixtures/aer_devices.json`): ogni riga del catalogo elenca
  GIÀ tutte le regioni di un modello insieme (`["APAC", "Europe",
  "MEA", ...]`), non una riga separata per regione. Non c'è
  un'ambiguità da risolvere: nessun fix necessario qui.
* **Xiaomi** (`_lookup_xiaomi`/`_piu_vicini`) — il tracker usa nomi con
  parole di zona («Global», «India», «Indonesia»...) che il codice
  tratta già come equivalenti fra loro (non «un altro telefono»,
  `_PAROLE_VARIANTE`), quindi in teoria la stessa ambiguità potrebbe
  esistere. Non c'è però un fixture o un accesso di rete per
  verificarlo su dati veri in questa sessione: applicare qui la stessa
  regola senza aver visto un caso reale sarebbe indovinare, non
  correggere. Da riprendere se emerge un caso concreto.
* **HONOR, Motorola, realme (fonti non-AER)** — nessuna convenzione di
  codice o campo di dati nota per il mercato, verificata o no: stesso
  motivo di sopra.

Test nuovi: `tests/test_oplus_arb.py::TestFonteInSources::
test_leuropa_viene_prima_delle_altre_regioni`,
`test_global_viene_dopo_leuropa_ma_prima_delle_altre`,
`test_senza_europa_ne_global_lordine_resta_per_build` (3).

### Verificato, non solo scritto

Suite completa dopo questo giro: **1028 test passati, 416 subtest
passati, 0 falliti** (era 1025 all'inizio di questo giro).
