# Mobile Update Tracker — passaggio consegne (v38)

- **581 test**, tutti verdi (erano 569).
- `DATA_LOGIC_VERSION` invariata.

---

## IMEI non trovato: da vicolo cieco a due minuti di lavoro

### Più siti dove verificare, non uno solo

I database TAC gratuiti hanno buchi **diversi fra loro**: un codice
assente da uno si trova spesso nell'altro. Ora l'app propone quattro
strade — HiCellTek (gratuito, nessuna registrazione), imei.info,
nobbi.com per i modelli storici, IMEI DB.

Nessuno di questi viene interrogato dall'app: bloccano l'accesso
automatico o lo vietano nei termini d'uso. Consultarli di persona è
invece del tutto lecito, ed è esattamente ciò che i collegamenti
permettono. Solo il collegamento a imei.info porta l'IMEI nell'indirizzo,
perché è l'unico che accetta una ricerca diretta; gli altri sono pagine
di ricerca e non ricevono nessun identificativo.

### Il modello si inserisce dentro l'app

Trovato il modello, lo si scrive in due campi e si salva. Vale **subito**
e per **tutti gli IMEI di quel modello**, perché si salva il TAC: le altre
sette cifre identificano il singolo esemplare e col modello non c'entrano.

**Ha la precedenza su tutto**, database scaricati compresi: se lo hai
verificato tu, hai ragione tu. Si può correggere riscrivendolo e togliere.

Il salvataggio vive nell'archivio, quindi sopravvive ai riavvii ma non a
un archivio ricostruito da zero. Per questo l'app mostra **anche** la riga
già compilata da incollare in `data/tac_modelli.csv`, che è la forma
definitiva. Le due strade non si escludono: una è immediata, l'altra è
permanente.

---

## Il difetto trovato scrivendo la funzione

`_build_index()` usciva subito se il database scaricato non era
disponibile — e con lei sparivano **anche la tabella verificata a mano e i
TAC inseriti nell'app**, che col download non c'entrano niente.

Bastava un'ora senza rete perché l'app dimenticasse dati che aveva in
casa. E sarebbe stato invisibile: si sarebbe manifestato come «a volte non
riconosce il telefono», la peggior forma di segnalazione da inseguire.

Ora le fonti locali si aggiungono sempre, qualunque cosa faccia il
download, e lo stato in Diagnostica dice quante voci vengono da dove.

---

## Errori da non ripetere

33. **Un'uscita anticipata deve riguardare solo ciò che dipende dalla
    condizione che l'ha causata.** Qui un download fallito cancellava
    anche i dati locali, che erano già in memoria e non c'entravano.

---

## Cosa resta da fare

1. **Il doppione «Galaxy S24 Ultra» / «Samsung S24 Ultra»**: invariato.
2. **Il filtro anti-rumore troppo permissivo**: invariato.
3. **Verificare in produzione** il download del dataset dei chip (v37) e
   i quattro collegamenti di verifica.
