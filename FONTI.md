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
| `vivo.com/en/support/security-update` | **404** |
| `hihonor.com/global/security` | 200 ma sono bollettini CVE, non versioni per modello |
| API OTA Oppo/OnePlus/realme (Allawn/ColorOS) | richiedono l'impronta del dispositivo e la finzione dell'app ufficiale → **fuori dalle regole del progetto**, come già deciso per OxygenUpdater |

**Conclusione onesta su Oppo/OnePlus/realme moderni:** non esiste una fonte
pubblica e machine-readable della versione OTA corrente. Non è un limite
del progetto, è una scelta di quei produttori. Per quei modelli la strada
resta: versione di fabbrica dichiarata come tale + notizie, con l'etichetta
corretta.

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

Sostituisce i quattro parser HTML separati di Honor, realme, vivo e Oppo —
compreso quello vivo **mai verificato sul sito vero**. Da quattro punti di
rottura silenziosa a uno rumoroso.

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
