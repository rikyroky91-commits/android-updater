# Ricerca Moto G(30), 11 settembre 2026

Segnalazione: cercando `MOTO G(30)` la pagina mostrava Motorola Edge 50 Neo.
Una successiva verifica pubblica ha restituito Moto G(30): la sostituzione
esatta vista nello screenshot non è stata riprodotta in modo deterministico.

Difetti verificati e corretti:

- Versus eliminava il numero tra parentesi: Moto G(30) diventava Moto G.
  Le parentesi numeriche ora conservano il modello, anche per Nothing Phone (2).
- Specifiche, catalogo Motorola e indice dei codici riconoscono G(30) e G30
  come la stessa grafia, anche con spazi dentro le parentesi.
- Il recupero AI non può sostituire un dispositivo già identificato con un
  altro modello solo perché per quello trova un firmware. Può ancora migliorare
  il risultato dello stesso telefono o interpretare una ricerca non identificata.

Test di regressione: selezione G30 con Moto G ed Edge 50 Neo tra i candidati,
rifiuto se manca G30, conservazione delle generazioni Nothing, indice specifiche,
rifiuto del recupero AI verso Edge e accettazione del recupero verso lo stesso G30.

Il deploy Render resta manuale. Dopo il deploy provare Moto G(30), Moto G30 e
Motorola Moto G30, attendendo anche il completamento del firmware. Non è stata
aggiunta una versione Android o una data di rilascio non verificata.
