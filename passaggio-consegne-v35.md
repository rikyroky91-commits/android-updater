# Mobile Update Tracker — passaggio consegne (v35)

- **552 test**, tutti verdi (erano 547).
- `DATA_LOGIC_VERSION` invariata: cambia solo l'identificazione IMEI.

---

## Il TAC `35135531` e perché imei.info lo trova

Riccardo ha segnalato che `https://www.imei.info/it/?imei=351355315430630`
identifica il dispositivo mentre l'app no.

**Verificato: quel sito non è consultabile in automatico.** Risponde con
rilevamento bot, e i suoi termini d'uso vietano esplicitamente
l'estrazione automatica dei dati. Lo trova perché usa un **catalogo
commerciale**, non uno pubblico.

Quindi «lì funziona» non si traduce in «possiamo farlo gratis», e questa è
la parte da non fraintendere: non è un difetto dell'app, è una differenza
di catalogo. I database TAC scaricabili gratuitamente hanno buchi diversi
fra loro e nessuno è completo.

### Cosa è stato fatto invece

**1. Interrogazione puntuale del solo TAC, opzionale.** Un servizio con
piano gratuito (100 ricerche al mese) che — differenza che qui conta più
del prezzo — accetta le **sole 8 cifre del TAC**, non l'IMEI completo. Le
cifre restanti, che identificano il singolo telefono, non lasciano mai la
macchina. C'è un test che verifica proprio questo: che il corpo della
richiesta sia esattamente `{"query": "35135531"}` anche partendo
dall'IMEI intero.

**È spenta finché non c'è una chiave** in `TAC_API_KEY`. Senza, l'app si
comporta esattamente come prima: nessuna chiamata, nessun errore. E viene
interrogata **solo** dopo che entrambi i database locali hanno fallito,
perché cento ricerche al mese vanno spese sui codici che non abbiamo.

**2. Un vicolo cieco in meno.** Quando il TAC non si trova, il messaggio
ora dice *quale* TAC manca, spiega che è un buco di copertura e non un
guasto, e offre il collegamento diretto per verificarlo a mano. Se il
modello che compare lì è giusto, si aggiunge alla tabella verificata: una
riga, e quel telefono è coperto per sempre.

Consultare quei siti a mano è lecito; farlo dall'app no. Per questo si
offre il collegamento invece di copiare il dato.

---

## Errori da non ripetere

28. **«Su un altro sito funziona» non è una specifica.** Prima di
    inseguirlo va capito *perché* funziona: qui la risposta era «hanno
    comprato un catalogo migliore», e nessuna quantità di codice l'avrebbe
    colmata.

---

## Cosa resta da fare

1. **La CPU nella tabella dei dispositivi.** Nello screenshot del 06/08 la
   colonna non c'è: il chip compare solo nella scheda e nel riquadro di
   ricerca. Va aggiunto come colonna, perché è lì che l'utente guarda.
2. **Il doppione «Galaxy S24 Ultra» / «Samsung S24 Ultra».** Il
   riconoscimento della marca è corretto dalla v34, ma le due righe già in
   archivio restano finché non convergono su una chiave sola.
3. **Copertura SoC di tutti i brand.** La verifica ha stabilito che
   l'unico dataset scaricabile con una colonna `Chipset` è indicizzato per
   nome commerciale, è fermo al 2021 e non distingue le varianti regionali
   — cioè proprio l'informazione che serve al QA. Serve una strategia
   ibrida, non un semplice caricatore.
