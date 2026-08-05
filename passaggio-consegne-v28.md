# Mobile Update Tracker — passaggio consegne (v28)

Aggiorna `passaggio-consegne-v27.md`.

- **467 test**, tutti verdi (erano 463).
- Una sola correzione, ma bloccante: **l'app non partiva affatto.**

---

## Il guasto: una riga in `requirements.txt`

Log di produzione del 2026-08-05, 18 errori identici e nient'altro:

```
TypeError: GZipResponder.__init__() missing 1 required
           keyword-only argument: 'thread_minimum_size'
  streamlit/web/server/starlette/starlette_gzip_middleware.py:125
```

Starlette 1.4.0 ha reso `thread_minimum_size` obbligatorio; il middleware
di compressione di Streamlit lo istanzia ancora con la vecchia firma.
Risultato: **ogni richiesta HTTP risponde 500**, i controlli di salute
falliscono, il container si riavvia in ciclo. `app.py` non viene mai
eseguito.

`requirements.txt` chiedeva `streamlit>=1.40` e non nominava `starlette`.
Streamlit non dichiara un tetto sulla sua dipendenza, quindi `uv` ha preso
l'ultima versione disponibile. Ambiente osservato: streamlit 1.61.0,
starlette 1.4.0, Python 3.14.6.

**Correzione**: `starlette<1.4.0`, con il motivo scritto accanto — un pin
senza spiegazione lo toglie il primo che fa pulizia.

### Perché merita un capitolo

Questo guasto ha una proprietà che nessun altro in tutto il progetto ha:
**si è verificato senza che nel repo cambiasse una riga.** Non dipende da
cosa fa il codice, ma da cosa installa il server il giorno del deploy.

I 463 test erano verdi mentre l'app era irraggiungibile, e sarebbero
rimasti verdi per sempre: girano su un ambiente dove le dipendenze sono
già installate. Da qui `tests/test_dipendenze.py`, che legge
`requirements.txt` come un artefatto e verifica che il vincolo ci sia e
che il motivo sia cercabile nel file.

---

## Errori da non ripetere

I diciassette precedenti restano validi.

19. **Un limite inferiore senza limite superiore non è un vincolo, è una
    scommessa.** `streamlit>=1.40` sembra prudente e invece delega a un
    installatore, mesi dopo, la scelta che decide se l'app parte. Dove una
    dipendenza transitiva puo' rompere l'avvio, serve un tetto.

---

## Cosa resta da fare

1. **Verificare che il deploy risalga**, e solo allora controllare se le
   correzioni della v27 (suffisso `/DS`, region Samsung, riconoscimento
   del codice) funzionano con la rete vera: finora sono state provate solo
   con l'endpoint simulato, e in produzione non hanno mai potuto girare.
2. **Riprovare a togliere il pin** quando una versione di Streamlit
   dichiarera' il supporto a Starlette 1.4+. Fino ad allora resta.
3. Invariati dal v26: esportare il catalogo Play per la copertura SoC,
   verificare i tre involucri non provati su dati vivi.

---

## Il repo

**GitHub Desktop.** Ci sono `.github/`, `.streamlit/` e `data/` che
l'upload da browser salterebbe. CRLF di `app.py` intatti.
