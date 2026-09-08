# Passaggio di consegne — 8 settembre 2026 (v75)

Revisione basata su `main` al commit `9c7d1b4`, sui passaggi di consegna
e sulle integrazioni successive annotate in FONTI.md. Modifiche preparate
localmente: nessun push, deploy o modifica delle chiavi dell'host.

## Problema verificato sul sito

La diagnostica pubblica `/health?dettaglio=1` dell'8 settembre riporta le
ultime sette chiamate HiCellTek tutte in errore, ultima alle 07:28:38 UTC.
Il corpo contiene “Security check” e richiesta di JavaScript, con server
o2switch-PowerBoost-v3. Non è una risposta del catalogo TAC. La chiave
risulta configurata, ma la sua validità non è verificabile da questa risposta.
Il cambio di User-Agent delle precedenti modifiche non ha risolto il blocco.

## Correzioni

1. HTTP 200 con `success:false`, errori di credenziali/saldo/quota, JSON
   senza modello e 404 generici non vengono più memorizzati come TAC assenti.
   Si accettano solo assenze esplicite (`found:false`, `TAC_NOT_FOUND`).
   Un modello uguale alla sola marca o un TAC restituito diverso da quello
   richiesto non diventa un'identificazione riuscita.
2. L'assenza richiede una risposta negativa da tutti i fornitori configurati.
   Errori, pause e quota esaurita mantengono l'esito incompleto e riprovabile.
   Il test precedente aveva un titolo corretto ma pretendeva erroneamente
   `assente` dopo un 500 del secondo fornitore: l'aspettativa è stata corretta.
3. Le vecchie assenze potenzialmente errate non bloccano il retry per un mese.
   Un cambio di fornitori, URL o chiavi invalida le nuove assenze memorizzate.
4. Profilo `imeicheckpro`: GET documentata, autenticazione via intestazione,
   parser del campo `object`, tre richieste nell'ultima ora e contatori
   persistenti. Controllo e prenotazione quota sono atomici tra thread.
5. Copia TAC completa per il fallback offline: 254.703 TAC distinti contro
   gli 83.137 della copia filtrata; 171.566 aggiuntivi, di cui 12.784 Samsung.
   Questi numeri includono telefoni vecchi: non indicano altrettanti modelli
   recenti né una copertura completa. L'indice in RAM resta filtrato, la
   lettura del file completo è progressiva. Le correzioni manuali prevalgono.
6. Comando `scripts/verifica_servizi_tac.py`: controlla la configurazione;
   con `--live` verifica il percorso API senza farsi nascondere dai TAC
   corretti manualmente. Rispetta quote e pause, non stampa chiavi.

## Consegna e documentazione

- Nuova [guida servizi TAC](guida-servizi-tac.md), con configurazione,
  fonti ufficiali, criteri di accettazione e limiti ancora aperti.
- README corretto: non suggerisce più il workflow rimosso `scan.yml` che
  pubblicava il database; distingue Gist non elencato e cifratura.
- Commenti Docker aggiornati al precaricamento effettivo dei cataloghi:
  non viene copiato un database di produzione aggiornato ogni ora.
- Nuovo workflow `.github/workflows/tests.yml` per la suite su Linux.
  È incluso nel pacchetto ma non è stato eseguito su GitHub.

## Verifiche eseguite

- Suite completa durante la revisione: 1.569 passati, 14 falliti, 1 saltato,
  514 sottocasi passati, su Windows/Python 3.12. Non è una suite tutta verde.
- Dieci fallimenti riguardano misure Linux (`/proc`/rilascio memoria):
  riprodotti sulla copia originale, inclusi i due test del sito.
- Quattro fallimenti Samsung erano dovuti a quote persistite da altri test:
  corretto l'isolamento nel file che verifica il protocollo API.
- Verifica finale del gruppo IMEI: **241 passati, 1 saltato, 21 esclusi**
  (gruppi relativi alla memoria), 38 sottocasi passati. Include 20 nuovi casi
  di regressione sulle API, cache, quota concorrente e fallback offline.
- Revisione indipendente delle modifiche: nessun nuovo bug confermato.
- Nessuna chiamata autenticata al nuovo servizio: manca una chiave approvata
  in questo ambiente. Non dichiarare l'integrazione operativa finché il
  collaudo reale descritto nella guida non restituisce un modello.

## Passi dopo l'integrazione

1. Applicare la patch sul commit base o integrare i file aggiornati; includere
   `.github/workflows/tests.yml` e `data/tac_completo.csv.gz`.
2. Eseguire la suite su Linux e controllare la build Docker su Render.
   Non modificare o pubblicare `tracker.db` e conservare le chiavi esistenti.
3. Richiedere una chiave gratuita approvata IMEI Check Pro, poi configurare
   `TAC_API_PROVIDER_2=imeicheckpro` e `TAC_API_KEY_2` nel pannello dell'host.
4. Eseguire il comando di prova `--live` nello stesso ambiente, controllare
   risposta e quota, poi verificare una ricerca IMEI nell'interfaccia.

Restano da verificare il TTL consentito alle risposte positive HiCellTek
(la persistenza preesistente è senza scadenza), l'accesso reale delle API
dal deploy e l'andamento della memoria su Linux. Non vengono promesse
identificazioni universali né specifiche RAM/storage ricavate dal solo TAC.
