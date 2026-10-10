# Software installato e test

Il risultato firmware offre un confronto locale con Android/build letti sul
telefono. Non invia questi valori a servizi esterni e non installa aggiornamenti.
Richiede conferma di modello, variante e regione; accetta soltanto fonti classificate
come firmware attuale. Non ordina alfabeticamente build diverse e segnala dati
discordanti o insufficienti. La conferma della variante è dell'utente, non automatica.

Il parco consente di registrare Android/build effettivamente installati ed esito
(Superato, Fallito, Da completare), mantenendo data, note e allegati esistenti.
I campi vuoti non ereditano il firmware delle fonti. Nessuna skin o patch viene
dedotta da Android. Il salvataggio aggiorna l'ultima baseline, non uno storico.

La provenienza manuale e l'esito sono JSON nel campo note della baseline:
`{"origine":"telefono","esito":"Superato"}`. Le note libere restano nella
watchlist. I backup esistenti includono già questi campi; nessuna migrazione SQL.
Le vecchie baseline delle fonti non vengono presentate come dati letti sul telefono.
Il pulsante Copia riepilogo usa soltanto i dati già salvati, senza IMEI; se gli
appunti non sono disponibili mostra un testo selezionabile da copiare.

Verifiche: test Python del parco, caricamento asincrono e retest; test Node dei
confronti, eseguiti anche dalla workflow GitHub. Deploy Render manuale.
