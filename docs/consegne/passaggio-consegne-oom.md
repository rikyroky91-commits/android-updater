# OOM Render — 11 settembre 2026

Il riavvio delle 08:37 UTC è stato classificato «Out of memory» in Events,
secondo la verifica dell'utente. Il log HTTP da solo non identifica quale
allocazione abbia esaurito la memoria. La lettura pubblica di /health ha
mostrato il commit 716bffe, avvio 10:37:23 +02:00, RSS 170,2 MiB dopo il
riavvio e zero alleggerimenti. Main era già c87be49: mancava un deploy.

## Riduzione dei picchi e osservabilità

- Il preriscaldamento delle fonti durante le ricerche è ora opt-in:
  PRERISCALDA_FONTI_RICERCA=false per impostazione predefinita. Le fonti
  necessarie vengono comunque interrogate; non partono download speculativi
  che continuano dopo la risposta e si sovrappongono alla ricerca successiva.
- PRERISCALDA_CATALOGHI è false per impostazione predefinita e nel Blueprint.
- Il parser YAML Xiaomi compone un record alla volta, anziché un albero
  sintattico dell'intero storico. Restano in memoria il testo HTTP e i dati
  risultanti; non è uno streaming completo della rete. Record oltre 64 KiB
  e strutture incompatibili vengono rifiutati. Fixture reale confrontata
  con PyYAML: risultati identici.
- Un thread del lifespan controlla RSS ogni 5 secondi anche senza richieste,
  richiama l'alleggerimento esistente e si arresta allo shutdown. Scrive una
  riga memory ogni minuto e ad ogni intervento, senza query o IMEI.

Benchmark locale su 3.000 record sintetici, tracemalloc: picco Python
24,44 MiB prima, 4,21 MiB dopo. Non misura RSS totale né il picco su Render.

## Applicazione su Render

Il file render.yaml non modifica automaticamente ogni servizio esistente.
Verificare in Environment e applicare:

- PRERISCALDA_CATALOGHI=false
- PRERISCALDA_FONTI_RICERCA=false
- MEMORIA_SOGLIA_MB=380

Distribuire il commit corretto e controllare versione.commit e avvio_utc in
/health; i log devono contenere memory rss_mb=... . Il monitor rispetta
MEMORIA_SOGLIA_MB e la pausa esistente fra gli alleggerimenti. Se la variabile
rimane 450, interviene a 450: il nuovo valore nel Blueprint da solo non basta.

Questa è una mitigazione verificabile, non la dimostrazione dell'allocazione
responsabile né una garanzia anti-OOM: oggetti ancora in uso, più processi e
picchi fra due campioni possono superare il limite. Non si forza un riavvio
né si eliminano dati utente per ridurre RSS.
