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
