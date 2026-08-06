# Mobile Update Tracker — passaggio consegne (v29)

Aggiorna `passaggio-consegne-v28.md`.

- **479 test**, tutti verdi (erano 467).
- **`DATA_LOGIC_VERSION` resta 22**: non è cambiato il modo in cui una
  fonte viene interpretata, ma quale record vince a parità di fiducia.
  Le righe già in archivio restano valide, quindi ricostruirlo non
  servirebbe a niente.

---

## Il guasto: «a325f» dava Android 11 invece di Android 13

Due difetti che si sommavano, e il secondo è quello che rendeva il primo
pericoloso invece che solo scomodo.

### 1. Il codice senza prefisso non era riconosciuto

`A325F` è la forma che compare nel numero di build (`A325FXXU2CVK1`), nei
log, nei nomi dei firmware e nelle discussioni tecniche: è quella che chi
fa QA copia più spesso, molto più di `SM-A325F`.

Non essendo riconosciuta come codice modello, la ricerca non deduceva il
brand e **il controllo firmware ufficiale Samsung non partiva nemmeno**.

Ora `sources.espandi_codice_samsung` la riporta alla forma completa, che
è l'unica che l'endpoint FOTA conosce. La regola è **stretta apposta**
(lettera + esattamente tre cifre + fino a tre lettere): allargarla farebbe
passare per codice Samsung qualunque parola con dei numeri dentro.

### 2. Rispondeva un'altra fonte, con la versione DI FABBRICA

Su un Galaxy A32 significa Android 11 — il lancio, 2021 — su un telefono
arrivato ad Android 13.

**Il risultato non era un dato mancante ma un dato sbagliato**, che per un
tracker di aggiornamenti è molto peggio: un QA che ci si fida non ritesta
un dispositivo che invece è cambiato di due major.

---

## La rete di sicurezza generale: niente retrocessioni

Correggere il riconoscimento del codice risolve *questo* caso. Ma la
classe di difetto resta: una fonte qualsiasi può riportare una versione
vecchia e, se incontrata di recente, scalzare quella attuale.

`get_devices()` ordinava per affidabilità e **poi per data più recente**.
Ora, a parità di affidabilità, **vince la versione più alta**: un telefono
Android non torna indietro di major, quindi fra 11 e 13 la risposta giusta
è 13 anche se l'articolo che diceva 11 è stato incontrato ieri.

**L'ordine per affidabilità resta prima**, e questo va difeso: una fonte
ufficiale che dice 13 deve continuare a battere una notizia entusiasta che
dice 14. C'è un test che lo verifica, perché è la regola che una
«semplificazione» futura toglierebbe per prima.

---

## Errori da non ripetere

I diciannove precedenti restano validi.

20. **Un dato sbagliato è peggio di un dato assente.** Quando la fonte
    buona non risponde, il ripiego deve dire cosa non sa, non riempire il
    campo con quello che ha. Qui la versione di fabbrica era corretta come
    fatto storico e falsa come risposta alla domanda posta.

---

## Cosa resta da fare

1. **Verificare in produzione.** Come per la v27 e la v28, le correzioni
   sono provate con l'endpoint simulato: il container di sviluppo non ha
   rete. Da controllare che `a325f`, `SM-A075F/DS` e `SM-S928B` diano
   davvero la build corrente.
2. **Rivedere il pin `starlette<1.4.0`** quando Streamlit dichiarerà il
   supporto: è un tappo, non una soluzione.
3. Invariati: esportare il catalogo Play per la copertura SoC, verificare
   i tre involucri non provati su dati vivi, sorvegliare il tracker ARB.

---

## Il repo

**GitHub Desktop.** Ci sono `.github/`, `.streamlit/` e `data/` che
l'upload da browser salterebbe. CRLF di `app.py` intatti.
