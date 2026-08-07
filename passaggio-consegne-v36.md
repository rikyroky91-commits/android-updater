# Mobile Update Tracker — passaggio consegne (v36)

- **560 test**, tutti verdi (erano 552).
- `DATA_LOGIC_VERSION` invariata.

---

## Il TAC mancante, risolto senza dipendenze

La strada del servizio esterno si è rivelata più stretta di come sembrava:
il piano gratuito richiede un'**email aziendale** (Gmail e simili rifiutate)
e comunque **non include il chipset**, che è nel piano da €19/mese. In
cambio di una registrazione e di una dipendenza esterna si otteneva un
beneficio incerto — non sappiamo nemmeno se il loro catalogo contenga il
TAC che manca a noi.

### `data/tac_modelli.csv`

Stessa idea della tabella dei chip: **una riga per telefono, verificata a
mano, che ha la precedenza su tutto il resto.**

Il ragionamento è che consultare a mano un servizio commerciale è del
tutto lecito — è farlo dall'app che non lo è, perché bloccano l'accesso
automatico e nei termini d'uso lo vietano. Quindi l'app mostra il
collegamento, e il risultato verificato si scrive in una tabella locale.

**Sovrascrive i database scaricati, non ne colma solo i buchi**: se una
riga è stata controllata di persona e contraddice il dato scaricato,
quella controllata ha ragione. C'è un test che verifica l'ordine delle
operazioni, perché è il tipo di dettaglio che una rifattorizzazione
distratta inverte senza accorgersene.

Quando un IMEI non viene riconosciuto, l'interfaccia ora mostra **la riga
già pronta da copiare**, con il TAC dentro: resta da compilare marca e
modello e incollarla nel file.

### Cosa resta della via esterna

Il codice per l'interrogazione online resta, spento e senza chiave. Se un
domani ci fosse un'email aziendale, basta valorizzare `TAC_API_KEY`.
Nel frattempo non parte nessuna chiamata.

Corretto anche un difetto trovato verificando la documentazione reale del
servizio: `brand` arriva come **oggetto annidato** (`{"name": "Samsung"}`),
non come stringa. Con `str()` sarebbe finita la rappresentazione di un
dizionario dentro il nome del telefono.

---

## Errori da non ripetere

29. **Verificare la forma vera di una risposta prima di scrivere il
    parser.** Il campo `brand` annidato non si sarebbe visto finché
    qualcuno non avesse messo la chiave — cioè a settimane di distanza,
    quando nessuno avrebbe più collegato la causa all'effetto.

30. **Un piano gratuito con requisiti d'accesso non è gratuito.** Il costo
    era l'email aziendale, e andava pesato prima di proporlo.

---

## Cosa resta da fare

Invariato dalla v35, in ordine di fastidio per chi usa l'app:

1. **La CPU come colonna nella tabella dispositivi** — oggi è solo nella
   scheda e nel riquadro di ricerca, cioè non dove si guarda.
2. **Il doppione «Galaxy S24 Ultra» / «Samsung S24 Ultra»** — il
   riconoscimento della marca è corretto dalla v34, ma le righe già in
   archivio non convergono da sole.
3. **Copertura SoC di tutti i brand** — l'unico dataset scaricabile con
   una colonna `Chipset` è indicizzato per nome commerciale, fermo al 2021
   e non distingue le varianti regionali: serve una strategia ibrida.
