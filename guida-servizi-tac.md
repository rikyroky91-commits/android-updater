# Servizi TAC: configurazione e collaudo

Verifica documentazione: 8 settembre 2026. Il riconoscimento locale resta
gratuito e non richiede chiavi. Le correzioni manuali prevalgono; le API
si interrogano soltanto se il TAC non è disponibile localmente.

## HiCellTek

La [documentazione ufficiale](https://hicelltek.com/en/api/imei/) conferma
POST `https://imei.hicelltek.com/api/v1/tac/lookup`, intestazione `X-Api-Key`,
corpo `{"query":"35135531"}` e piano gratuito da 100 richieste mensili.
Configurare `TAC_API_KEY` nel pannello dell'host.

L'8 settembre la diagnostica pubblica del deploy mostrava sette chiamate
recenti, tutte fallite. Le risposte contenevano una pagina JavaScript
“Security check” di o2switch-PowerBoost-v3. È una risposta del filtro davanti
all'API: non permette di concludere se la chiave sia valida. Non basta
dichiarare il servizio “configurato”, né cambiare User-Agent, per collaudarlo.

## IMEI Check Pro

La [documentazione](https://imeicheckpro.com/tac-api) dichiara accesso gratuito
dopo approvazione e tre ricerche all'ora. Richiedere una chiave permanente
dal [modulo TAC](https://imeicheckpro.com/tac-access); le chiavi demo scadono.

Nel pannello Render impostare:

```text
TAC_API_PROVIDER_2=imeicheckpro
TAC_API_KEY_2=<chiave approvata>
```

Lasciare `TAC_API_URL_2`, `TAC_API_HEADER_2` e `TAC_API_NOME_2` non impostati,
oppure eliminare eventuali vecchi valori di prova. Il profilo configura GET
`https://imeicheckpro.com/api/tac/{tac}`, `X-API-Key`, lettura di `object.model`
e limite locale di tre richieste negli ultimi 60 minuti. Restano anche i
tetti locali di 10 al giorno e 100 al mese, deliberatamente conservativi.
Il profilo funziona anche negli slot senza suffisso e `_3`.

Non occorrono un IMEI completo, un IMEI sintetico o scraping di pagine web.
IMEIDB.xyz resta un endpoint personalizzabile, ma la sua documentazione
[descrive un saldo da ricaricare](https://imeidb.xyz/api): non è presentato
qui come alternativa gratuita verificata.

## Verifica dopo il rilascio

Eseguire nello stesso ambiente del sito, con le stesse variabili:

```bash
python scripts/verifica_servizi_tac.py
python scripts/verifica_servizi_tac.py --live --tac 35135531
```

Il primo comando elenca i fornitori senza interrogarli. Il secondo consuma
quota e passa dalla stessa logica della produzione, ma salta il catalogo
locale: un TAC già corretto manualmente non nasconde più un'API guasta
durante il collaudo. Non stampa chiavi né URL contenenti token.
Per provare specificamente il secondo fornitore, in un ambiente di verifica
configurare solo la sua chiave/profilo. Un servizio in pausa o senza quota
non viene forzato dal comando.

Accettazione: ottenere `esito: trovato` con marca e modello plausibili,
verificare la risposta nella diagnostica e il contatore del fornitore.
Una risposta `assente` indica solo che quel TAC non è in catalogo; non
certifica il riconoscimento di altri TAC. Il programma termina con codice
non zero se non ottiene un modello o se non ci sono fornitori configurati.

## Limiti da mantenere espliciti

- Nessuna chiave nuova è stata creata o configurata durante questa revisione.
  Il nuovo adattatore è collaudato su risposte documentate, non su un account reale.
- Un nuovo fornitore o una nuova chiave invalida la cache negativa. Le vecchie
  assenze, potenzialmente derivate da errori, non bloccano per un mese il retry.
- Le risposte positive hanno ancora la persistenza storica del progetto.
  Verificare il TTL del piano: i [termini HiCellTek](https://hicelltek.com/en/api-terms/)
  vincolano il caching al TTL assegnato. Il codice preesistente non gestisce
  ancora scadenze differenziate per fornitore.
- I contatori sono protetti tra thread nello stesso processo. Più processi
  o repliche richiedono una prenotazione transazionale condivisa; il Dockerfile
  attuale avvia un solo processo Uvicorn.
- La copia TAC completa aumenta la copertura offline, ma nessun database
  community garantisce di identificare ogni Samsung o ogni variante.
