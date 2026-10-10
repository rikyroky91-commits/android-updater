# Passaggio di consegne — 1 settembre 2026 (v70)

> «il servizio esterno non funziona. il risultato galaxy a06 l'ho
> memorizzato io.»

## Prima di tutto: avevo scritto una cosa non vera

Nella v69 ho scritto che il Galaxy A06 lo aveva risolto il servizio
esterno. **L'ha scritto l'utente a mano**, nel riquadro «se sai che
telefono è, scrivilo qui». Ho dedotto la fonte dall'esito invece di
leggerla — la pagina la dichiara, la riga dice «inserito da te» — ed è
precisamente l'errore che questo progetto evita dappertutto: una risposta
senza fonte. La v69 è corretta nel testo.

E la deduzione sbagliata ha nascosto un difetto vero, che è il resto di
questa consegna.

## Il difetto: un servizio rotto e nessun modo di accorgersene

`cerca_tac_online_esito` distingue con cura «non lo conosco» da «non ha
risposto» — c'è un commento lungo che spiega perché è tutto il punto — ma
poi **ogni** guasto finiva nello stesso `return ("errore", None)` muto:

* chiave rifiutata (HTTP 401/403),
* quota del mese finita (HTTP 429),
* servizio giù (5xx),
* rete che non passa,
* risposta illeggibile.

Nessuna traccia da nessuna parte. E le due pagine che dovrebbero dirlo
raccontavano altro:

* **Diagnostica** diceva «chiave presente · N TAC risolti», cioè che la
  chiave *esiste*, non che *funziona*;
* **`/health`** diceva `tac_esterno: "configurato"`, stessa cosa;
* **la pagina dell'IMEI** diceva «modello sconosciuto», identica a quella
  di un TAC che nessun catalogo al mondo conosce.

Quest'ultima è la peggiore: porta alla conclusione sbagliata — «questo
telefono non è in nessun catalogo» — mentre il guasto sta a monte e spesso
si ripara in un minuto. È il quarto silenzio della serie che questa pagina
ha già imparato a distinguere (mai chiesto / servizio spento / chiesto e
non lo sanno), ed era l'unico rimasto senza parole sue.

## Cosa ho cambiato

**`core/imeicheck.py`**

* `ultimo_esito_servizio()` — l'esito dell'ultima chiamata vera
  (`quando`, `esito`, `dettaglio`), conservato in archivio, quindi
  sopravvive ai riavvii, che qui sono all'ordine del giorno.
* `_ricorda_esito_servizio()` chiamata su **ogni** strada: risposta
  ricevuta, «non lo conosco», e ciascun guasto con parole sue.
* `_spiega_stato()` traduce il numero HTTP nella mossa che serve: «chiave
  rifiutata — da rifare o da ricontrollare in `TAC_API_KEY`», «troppe
  richieste o quota del mese finita (il piano gratuito ne dà cento)»,
  «guasto del servizio, non nostro». Un numero da solo dice tutto a chi sa
  leggerlo e niente a chi deve decidere.
* **Pausa di cinque minuti dopo un guasto.** Ogni tentativo costa il tempo
  del timeout, e chi cerca lo aspetta per ricevere comunque «non lo so».
  Cinque minuti sono abbastanza da non martellare un servizio che sta
  male, e abbastanza pochi da accorgersi subito quando torna. La pausa sta
  in memoria, non in archivio: un riavvio la azzera da solo, e
  `reset_cache()` pure.

**`web/main.py` e i template**

* `/health` risponde anche `tac_esterno_ultima_chiamata` (e quando). Si
  legge **senza login**, che è il punto: Diagnostica sta dietro l'accesso,
  e una configurazione che si controlla solo da dentro è una
  configurazione che nessuno controlla.
* `stato_servizio_esterno()`, cioè la riga di Diagnostica, riporta lo
  stesso esito.
* La pagina dell'IMEI, quando il TAC resta sconosciuto e l'ultima chiamata
  è fallita, lo dice: «Il servizio esterno è configurato ma in questo
  momento non risponde: HTTP 401 … Questo "non lo so" quindi non dice che
  il telefono è introvabile: dice che l'ultima fonte rimasta non ha
  parlato.»

## Cosa NON ho potuto fare

**Non so ancora perché non funziona**, e non posso scoprirlo da qui:
`imei.hicelltek.com` non è raggiungibile da questo ambiente (la rete in
uscita è filtrata). Le tre ipotesi, in ordine di probabilità:

1. **La quota è finita.** Il piano gratuito dà cento interrogazioni al
   mese, e fino al 26 agosto c'era il ciclo infinito corretto nella v65:
   una pagina lasciata aperta le bruciava in minuti. Se è questa, si
   risolve da sé al mese nuovo — e il messaggio ora lo dirà, «HTTP 429».
2. **La chiave non è più valida** o non è mai stata letta bene: «HTTP
   401».
3. Il servizio ha cambiato indirizzo o formato: «HTTP 404/5xx» sulla
   rotta, o «risposta di forma inattesa».

**Il modo di saperlo adesso c'è.** Dopo aver distribuito questo pacchetto,
cerca un IMEI con un TAC che nessuno conosce — va bene
`356427134239214`, se prima togli il modello che hai salvato, oppure
`999999990000004` — e poi guarda:

    android-updater.onrender.com/health

La riga `tac_esterno_ultima_chiamata` dirà quale dei tre casi è. Mandamela
e la sistemiamo.

## Test

**1417, tutti verdi** (erano 1408).

Sette nuovi in `tests/test_memoria_e_variante.py`: chiave rifiutata
riconosciuta dal numero, quota finita con parole sue, rete che non passa
che non diventa un no, il servizio che non si martella dopo un guasto, la
risposta buona che toglie la pausa, il «non lo conosco» che resta una
risposta conservabile, e la riga di Diagnostica che riporta l'esito.

Due in `tests/test_sito.py`, sulla pagina vera: con un guasto registrato
la pagina di un TAC sconosciuto scrive «HTTP 401: chiave rifiutata» e la
frase «non dice che il telefono è introvabile»; con un guasto di cinque
anni fa non scrive niente, perché la finestra è di sei ore.

Provato anche a mano, con un guasto finto in archivio:

```
/health → "tac_esterno_ultima_chiamata": "HTTP 429: troppe richieste o
           quota del mese finita (il piano gratuito ne dà cento)",
          "tac_esterno_quando": "2026-09-01T13:48:00+00:00"

Diagnostica → chiave presente · nessun TAC ancora risolto dal servizio ·
              ultima chiamata: HTTP 429: … (2026-09-01 13:48 UTC)
```

## Cosa resta

1. Distribuire, provare un TAC sconosciuto, leggere `/health`.
2. La memoria: 432 MB su 512, ferma ma stretta. `/health?dettaglio=1`
   (v69) dice quale catalogo pesa cosa — è il dato che serve per la
   prossima mossa, e il sospetto principale resta `core/modelcodes.py`.
