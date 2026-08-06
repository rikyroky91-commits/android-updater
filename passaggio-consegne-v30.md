# Mobile Update Tracker — passaggio consegne (v30)

Aggiorna `passaggio-consegne-v29.md`.

- **501 test**, tutti verdi (erano 479).
- **`DATA_LOGIC_VERSION` 22 → 23.** Questa volta è cambiato *come si
  interpreta* un dato, non solo quale record vince: l'archivio contiene
  righe scritte con la logica vecchia (fra cui l'Android 12 sbagliato del
  Galaxy A32) e va ricostruito.

---

## Il guasto: «a32 4g» dava Android 12, «a325f» quasi niente, e mai la CPU

Tre sintomi, tre cause distinte. Nessuna delle correzioni precedenti le
toccava, perché stavano tutte a monte.

### 1. La radice del problema Samsung: lo User-Agent

`fota-cloud-dn.ospserver.net` serve il client ufficiale Samsung e con uno
User-Agent da browser risponde 403. Il controllo versione lo chiamava con
quello generico del progetto, dentro un `except: continue`.

**Ogni region falliva in silenzio.** La ricerca finiva per rispondere con
una fonte di ripiego — la versione di fabbrica o una notizia vecchia — e
da fuori sembrava che il modello non fosse coperto. In realtà non gli
veniva mai chiesto niente.

Ora la richiesta porta `User-Agent: Kies2.0_FUS`. E gestisce la
**compressione**: il server può restituire gzip senza dichiararlo, e in
quel caso `response.text` è un blocco binario in cui il numero di build
non si trova — un secondo modo silenzioso di non funzionare, che sarebbe
rimasto anche dopo aver corretto il primo.

Questo spiega da solo perché tutte le correzioni delle sessioni v27 e v29
non avevano prodotto l'effetto atteso: erano giuste, ma a valle di una
richiesta che non arrivava mai a destinazione.

### 2. «One UI 5.0» e «Android 12» sono la stessa affermazione, e una era falsa

One UI 5 gira su Android 13. L'app aveva il dato giusto sotto forma di
versione dell'interfaccia e ne mostrava uno sbagliato come versione
Android, senza accorgersi della contraddizione.

`core/skinmap.py` porta la corrispondenza fra skin del produttore e major
Android, e serve **soprattutto come controllo di coerenza**: quando due
fonti si contraddicono, una va scartata, non mediata. Solo in seconda
battuta deduce la versione Android, e unicamente dove la corrispondenza è
univoca.

**La distinzione non è pedanteria.** La tabella ha eccezioni reali:

- **One UI 3.1.1** girava su Android 12 mentre i telefoni normali
  restavano etichettati «3.1» su Android 11;
- **EMUI 11 è basata su Android 10**, non 11 — Huawei ha rotto
  l'allineamento di proposito;
- **MIUI** ha pubblicato la stessa major su due Android diversi;
- **ColorOS** si è allineata solo dalla 11: prima saltava da 7 a 11.

Dove la corrispondenza è nota come non univoca il modulo restituisce
`None` e il controllo tace: una discrepanza lì non è una prova di errore,
e un controllo che nel dubbio accusa farebbe sparire dati buoni.

### 3. La CPU: un errore mio di impostazione

Avevo costruito la tabella SoC volutamente corta — solo Galaxy serie S —
appoggiando tutto il resto su un export della Play Console che Riccardo
non ha. Il risultato era una funzione che sulla carta esisteva e in
pratica non rispondeva quasi mai.

Ora la tabella copre anche la serie A (A15, A25, A32 4G e 5G, A34, A35,
A36, A52/A52s, A53, A54, A55, A56) e la serie S21, e il modulo riconosce
i codici scritti senza prefisso. Due difetti trovati scrivendo i test:

- **`SM-H264` inventato dal nulla.** Senza confini di parola, dentro
  «CPH2649» si legge «H264» e si finiva per cercare un codice Samsung che
  non esiste.
- **Candidati duplicati**, che moltiplicavano le interrogazioni.

Resta vero che la copertura larga richiede una fonte esterna: la ricerca
ha stabilito che **nessun dataset gratuito e senza registrazione** risolve
codice modello → SoC su tutta la fascia media. La tabella curata resta
corta per scelta, non per pigrizia: righe «plausibili» scritte a memoria
sarebbero indistinguibili da quelle verificate.

---

## Errori da non ripetere

I venti precedenti restano validi.

21. **Un `except: continue` che ingoia una richiesta mal formata è
    peggio di un errore.** Il guasto FOTA è durato tre sessioni perché
    ogni fallimento era silenzioso e indistinguibile da «questa region non
    ha firmware per questo modello». Dove si itera su candidati, va
    distinto *nessuno ha risposto* da *nessuno è stato interrogato bene*.

22. **Un dato che ne implica un altro va confrontato, non affiancato.**
    One UI 5.0 e Android 12 stavano nella stessa scheda senza che nessuno
    notasse che si smentivano.

---

## Cosa resta da fare

1. **Verificare in produzione.** Il container di sviluppo non ha rete:
   tutto è provato con l'endpoint simulato. Da controllare per primo che
   `a325f` dia Android 13 e One UI 5.1.
2. **Identità unica per dispositivo.** Resta il difetto di fondo per cui
   «a32 4g» e «a325f» possono atterrare su due record diversi dello stesso
   telefono, ciascuno con metà della storia. La correzione del FOTA lo
   attenua molto (ora entrambe le strade arrivano alla fonte ufficiale,
   che usa il nome canonico), ma la convergenza non è ancora garantita per
   costruzione.
3. **Copertura SoC**: valutare un dataset esterno da mettere in `data/`,
   sapendo che nessuno gratuito copre bene la fascia media per codice.
4. Invariati: pin `starlette<1.4.0` da rivedere, tracker ARB da
   sorvegliare.

---

## Il repo

**GitHub Desktop.** Ci sono `.github/`, `.streamlit/` e `data/` che
l'upload da browser salterebbe. CRLF di `app.py` intatti.
