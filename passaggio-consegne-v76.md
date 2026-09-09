# Passaggio di consegne — 9 settembre 2026 (v76)

Base: v75, commit `ebacf8b5c26303f4fab55c77991b4ac125d24fee`.
Ambito richiesto: punti 1, 3, 4 e 5. Il punto 2 è escluso: nessuna
attivazione di fornitori, modifica delle chiavi o verifica API dal vivo.

## Indice TAC su disco

`core/tac_index.py` mantiene il catalogo nel file ricostruibile
`<DB_PATH>.tac.sqlite3`. Ogni ricerca apre una breve connessione e usa la
chiave primaria TAC; il processo non conserva il dizionario completo.
L'importazione legge progressivamente le fonti e viene confermata in una
transazione: un errore conserva il catalogo precedente. Le connessioni non
restano aperte. Il file è separato dal database di account e backup.

Sono indicizzati anche i TAC senza anno o codice: il filtro
`TAC_SOLO_ERA_ANDROID` non restringe più l'indice. La funzione di filtro
resta disponibile per gli script che producono le vecchie istantanee.
Le correzioni manuali mantengono la precedenza sulle fonti pubbliche.

La liberazione della RAM consente di riusare il file esistente. Modifiche
alle correzioni, alle istantanee e alla data dei download ne invalidano la
firma. Il refresh segue la scadenza reale delle fonti (14 giorni). Se una
fonte è scaduta o manca, il riuso del catalogo ritenta al più una volta per
ora, salvo reset esplicito. Su disco effimero il file può sparire e viene
ricostruito dalle fonti già disponibili.

Benchmark locale Windows con 200.000 righe sintetiche equivalenti:
dizionario circa 29,7 MiB di allocazioni Python trattenute; riferimento
SQLite circa 0,002 MiB. Costruzione 1,19 s contro 1,52 s; 1.000 letture
SQLite 0,48 s. Sono misure dell'indice, non della RAM totale del servizio;
`tracemalloc` non comprende memoria nativa di SQLite o cache del sistema.
La suite contiene anche una prova da 200.000 righe e verifica l'uso della
chiave primaria con `EXPLAIN QUERY PLAN`.

La diagnostica delle scansioni conserva dimensione dei cataloghi dopo la
raccolta e variazione rispetto all'inizio nelle ultime otto scansioni.
Un errore nella misurazione non interrompe la scansione.

## TAC da verificare

La pagina `/admin/tac`, collegata dalla testata degli amministratori e
dalla diagnostica, elenca conteggio, motivo e ultima ricerca. Il registro
contiene esclusivamente TAC di otto cifre; nessun IMEI completo, IP o
account del visitatore viene aggiunto a questa tabella.

Limite: 1.000 TAC, scadenza dopo 90 giorni senza ricerche. Il conteggio è
cumulativo finché la voce rimane presente, non una finestra mobile di
90 giorni. Il secondo caricamento aggiorna l'esito senza contare una
seconda visita. Un'identificazione risolta elimina la voce.

Le correzioni da questa pagina richiedono un amministratore, un token
CSRF valido, TAC, marca e modello. Il salvataggio invalida le cache e
richiede il backup attraverso il percorso già esistente. Le correzioni
pubbliche preesistenti dalla pagina di ricerca conservano il loro flusso.

## Stati della ricerca

Sono distinti modello identificato, nome/variante da verificare, TAC
sconosciuto, ricerca in corso e servizio indisponibile. La scheda tecnica
mancante è separata dall'identità. Il secondo caricamento non afferma più
che nessun database conosce il TAC quando la verifica esterna fallisce.
Una correzione manuale verificata prevale sul disaccordo fra cataloghi.
Il controllo Luhn non presenta più un numero errato come «IMEI valido».

## Rilascio

`/health` espone `versione.commit`, `build_utc` e `avvio_utc`.
La build Docker genera `release.json`; fuori da Docker la data della
build può essere assente. Il commit può provenire anche da
`RENDER_GIT_COMMIT` a runtime.

`render.yaml` imposta `autoDeployTrigger: checksPass` secondo la
[specifica Render](https://render.com/docs/blueprint-spec).
Il workflow testa `main`, i rami `codex/**` e le pull request su Linux.
Per un servizio Render creato manualmente, modificare il file YAML da solo
non dimostra che l'impostazione sia applicata: verificare in Settings che
Auto-Deploy sia **After CI Checks Pass**, oppure sincronizzare il Blueprint.
Non è stata modificata la configurazione del servizio dal dashboard.

Prima del rilascio verificare il workflow sul commit candidato. Dopo il
rilascio confrontare il commit di `/health`, aprire `/admin/tac` da un
account amministratore e verificare una ricerca TAC. Per il rollback,
ridistribuire il commit precedente: la tabella diagnostica aggiunta non
modifica lo schema delle tabelle esistenti e l'indice è una cache separata.
