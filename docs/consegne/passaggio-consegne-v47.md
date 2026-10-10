# Mobile Update Tracker — passaggio consegne (v47)

- **824 test**, tutti verdi. Ne arrivavano **803 con 9 rossi**.
- `DATA_LOGIC_VERSION` invariata a **31**: non cambia il modo in cui una
  fonte viene interpretata, quindi l'archivio non si ricostruisce e il
  parco di test non si tocca.
- La segnalazione era «il sito è lento» e «manca il tasto AI». Sotto
  c'erano sei cose diverse, e nessuna era quella che sembrava.

---

## 0. Il tasto AI c'era già, ed era stato caricato nella cartella sbagliata

Prima di qualunque analisi, il fatto: `web/static/ai.js`,
`web/templates/base.html` con il tasto ✨, il `core/aiquery.py` con
l'elenco dei modelli di riserva e i due file di test **erano nel
repository**, dentro `tests/`. Un caricamento finito una cartella più in
basso: `tests/web/`, `tests/core/`, `tests/tests/`.

Il sito quindi girava con la versione precedente di tutto, e il tasto
compariva solo dopo una ricerca fallita. Spostati al loro posto, non
riscritti.

**Insieme a loro sono tornati al loro posto** `README.md` (era
`tests/README.md`) e il file di esempio della configurazione.

---

## 1. «Il sito è lento»: quattro cause, misurate una per una

Nessuna era il codice delle pagine. Con la rete spenta il sito risponde
in 89 ms.

### a) Una ricerca costava dodici secondi, e non se ne ricordava nessuna

Misurato sul sito vero:

| | |
|---|---|
| `GET /health` | 0,26 s |
| `GET /` | 1,25 s |
| **`GET /?q=SM-S928B`** | **12,84 s** |
| ricerca a vuoto (in locale) | 16,58 s, 30 richieste di rete |

E la stessa ricerca ripetuta ne costava altri dodici: fra due ricerche
identiche non c'era **nessuna** memoria. Chi non vede una risposta
ricarica la pagina, quindi «stessa domanda due volte» non è un caso
raro, è il più comune.

`web/cache.py`: memoria corta di quindici minuti, con scadenza sul tempo
monotono e un tetto al numero di voci. È onesta perché le fonti
pubblicano un firmware al massimo una volta al giorno e la scansione
gira una volta all'ora. Si spegne con `SEARCH_CACHE_SECONDS=0`, e si
svuota da sola quando l'archivio cambia sotto (scansione manuale, TAC
salvato a mano).

`SEARCH_BUDGET_SECONDS` da 25 a 12: era un tetto, non un bersaglio, e
le uniche ricerche che ci arrivavano vicino erano quelle a vuoto — cioè
proprio quelle in cui aspettare non serve.

### b) Il controllo di salute rispondeva 405, e l'host riavviava il servizio

Gli host controllano con `HEAD`. FastAPI — a differenza di Starlette
sotto di lui — **non** aggiunge `HEAD` a una rotta dichiarata `GET`:
rispondeva 405, il controllo lo leggeva come «servizio giù», e il
contenitore si riavviava. Ogni pochi minuti, all'infinito, e ogni
riavvio è un avvio a freddo da mezzo minuto.

Da fuori non si vede nessun errore: si vede un sito lento.

### c) L'archivio ripartiva vuoto a ogni risveglio

`avvio()` chiamava `backup.ripristina_se_serve()`. **Quella funzione non
esiste**: si chiama `ripristina()`. L'`AttributeError` finiva in un
`except Exception: pass` e spariva. Su un disco effimero significa che
il salvataggio su Gist — che esiste apposta per questo — non è mai stato
letto nemmeno una volta.

Corretto, e **non più silenzioso**: ogni passo dell'avvio lascia scritto
cosa ha fatto in `STATO_AVVIO`.

Aggiunta anche una copia di partenza dentro l'immagine (`tracker.db`, che
il workflow orario aggiorna): quando non c'è né archivio locale né
salvataggio esterno, il sito parte con 1536 dispositivi invece che con
zero. Non sovrascrive mai un archivio esistente e non installa una copia
illeggibile.

### d) Il servizio dorme dopo quindici minuti

`.github/workflows/sveglia.yml` chiama `/health` ogni dieci minuti. Chi
apre il sito una volta al giorno lo trovava **sempre** addormentato: per
lui non era lento ogni tanto, era lento sempre.

### E la memoria, che diventa lentezza

144 MB dopo il caricamento dei cataloghi, su un host che ne ha 512 e che
per averli superati aveva già riavviato il servizio d'ufficio.

| | prima | dopo |
|---|---|---|
| schede tecniche in memoria | 47,5 MB | 33,9 MB |
| indice dei processori in archivio | 1,85 MB | 0,10 MB |
| **`tracker.db`** | **10,6 MB** | **6,3 MB** |

Le sezioni delle schede stanno **ripiegate in una stringa**, non
compresse: il primo tentativo le comprimeva in base64 e faceva crescere
`tracker.db` a 12,2 MB, perché il base64 di dati compressi non si
ricomprime e quel file la compressione se l'aspettava. Il peso non era
nel testo ma negli oggetti — settecentomila stringhe e dizionari Python.

---

## 2. L'interprete AI rispondeva «quota esaurita» perché il modello era spento

In produzione, il 2026-08-10:

```
POST /api/interpreta → HTTP 429 — You exceeded your current quota
```

Non era la quota. `gemini-2.0-flash` è **dismesso**, e un modello spento
non ha una corsia di quota: Google risponde 429, non «modello
inesistente». L'errore manda a cercare un problema di limiti dove c'è un
nome vecchio.

Ora c'è un **elenco** di modelli provati in ordine, riletto dalla
documentazione e non ricordato: `gemini-3.5-flash-lite`,
`gemini-3.1-flash-lite`, `gemini-3.6-flash`, `gemini-3.5-flash`. I
«lite» per primi, perché il vincolo qui è la quota gratuita e non la
bravura: il compito è scegliere fra venti righe di testo.

**La regola che conta non è cambiata**: il modello sceglie fra candidati
che gli passiamo noi, e quello che propone viene ricontrollato contro i
cataloghi e scartato se non c'è. Il prompt glielo chiede, ma è il filtro
dopo la risposta che lo garantisce.

---

## 3. Le pagine, rifatte dove servivano

- **`/` è la sola barra di ricerca**, più in basso e più grande. Prima
  c'era anche l'elenco di 1536 dispositivi: la ricerca stava schiacciata
  sopra una tabella che nessuno aveva chiesto.
- **`/dispositivi`** è l'archivio. Il suo filtro si chiama `filtro` e non
  `q`, perché non esce in rete e le due cose non vanno confuse.
- **Una ricerca mostra la scheda tecnica e gli aggiornamenti di quel
  modello**, non solo la riga del firmware.
- **Il «forse cercavi» compare anche quando la ricerca riesce** — ed è lì
  che serve di più: chi cerca «galaxy s24» e voleva l'Ultra riceve una
  risposta corretta e inutile.
- Il piede sta in fondo alla pagina, la trama di sfondo è a `.62`.

### Le righe si costruiscono solo se si vedono

La tabella ne mostra duecento, ma il taglio stava nel template: se ne
costruivano 1536 e se ne buttavano 1336 **dopo** aver risolto il
processore di ognuna. 50 ms contro 5.

---

## 4. «s 24», «samsung s24» e «SM-S921B» danno la stessa risposta

Provato interrogando il sito, nove gruppi sulle marche che contano.
**Cinque erano incoerenti**, per due cause distinte:

1. **Lo spazio fra lettere e cifre.** «redmi note13» e «pixel9» non
   arrivavano a nessuna fonte, «Redmi Note 13» e «Pixel 9» sì.
   `expand_query` ora prova entrambe le forme, nei due versi.
2. **Il nome lo sceglieva chi rispondeva**: `realme C61` o `C61`,
   `Moto G14` o `Motorola G14`, `Pixel 9` o `Google Pixel 9`. Ora lo
   decide l'archivio, che un nome canonico ce l'ha già.

**Il secondo punto ha prodotto un difetto peggiore del difetto**, ed è la
cosa da ricordare: la prima versione adottava il nome di qualunque
dispositivo l'archivio restituisse per quel testo, e «Pixel 9» ha
cominciato a rispondere «**Google Pixel 9a**» — un telefono diverso, con
un altro chip. Coerente e sbagliato. Il confronto ora è sulla chiave di
dispositivo, cioè la regola con cui l'archivio stesso decide che due
nomi sono un telefono solo.

Esito finale: **nove gruppi su nove coerenti**.

Resta una imperfezione dichiarata: realme mostra «C61» invece di
«realme C61». È il nome con cui quel telefono sta in archivio, quindi è
coerente ovunque; a correggerlo è la fonte, non la vista.

---

## 5. Via la dashboard Streamlit

`app.py` (110 KB) e i suoi nove test **erano rossi da tempo**:
`.streamlit/config.toml` non è mai arrivato nel repository, perché
l'upload dal browser di GitHub salta le cartelle che iniziano con un
punto. Il sito è in produzione, quindi si tolgono — come previsto dal
passaggio consegne v46.

Con loro se ne vanno `streamlit` e `pandas` (la maggior parte del tempo
di build e del peso dell'immagine) e il tetto `starlette<1.4.0`, che
esisteva per un difetto del middleware di **Streamlit** e teneva FastAPI
su una versione vecchia di mesi.

Il file di esempio della configurazione è ora `configurazione.esempio.toml`,
alla radice: fuori da una cartella col punto, così l'upload dal browser
non lo salta più.

---

## Errori da non ripetere

64. **Un file caricato nella cartella sbagliata non dà nessun errore.**
    Il tasto AI esisteva, era collaudato, ed era invisibile perché stava
    un livello più in basso. Dopo un caricamento vale la pena guardare
    `git ls-files` prima di cercare il difetto nel codice.

65. **Una funzione chiamata e inesistente dentro un `except Exception`
    è un pezzo di applicazione che non c'è.** `ripristina_se_serve` non
    è mai esistita e nessuno se n'è accorto per una versione intera.
    Dove si ingoia un'eccezione, si scriva almeno cosa si è ingoiato.

66. **`HEAD` non è `GET`.** FastAPI non lo aggiunge da solo, e un
    controllo di salute che riceve 405 fa riavviare il servizio senza
    lasciare un solo errore nei registri.

67. **Comprimere due volte fa crescere il file.** Il base64 di un gzip
    non si ricomprime, e `tracker.db` è passato da 10,6 a 12,2 MB per una
    correzione che doveva alleggerirlo. Il peso di una struttura in
    memoria di solito sta negli oggetti, non nel testo.

68. **Una correzione che uniforma può uniformare sulla cosa sbagliata.**
    Far decidere il nome all'archivio ha reso coerenti nove gruppi su
    nove e ha fatto rispondere «Pixel 9a» a chi cercava il Pixel 9.
    Quando si fa convergere qualcosa, il criterio di identità va
    verificato, non dato per buono.

69. **Un test che guarda un file cancellato non protegge più niente.**
    `test_avvio_coerente` controllava `app.py` e `worker.py`. Il sito è
    nato come terzo percorso d'avvio, nessuno ha spostato il controllo, e
    `web/main.py` è nato senza due manutenzioni su tre.

---

## Cosa resta da fare

1. **Guardare `/diagnostica` dopo il primo deploy.** Adesso riporta cosa
   ha fatto l'avvio: se l'archivio esterno è configurato, se il
   ripristino è riuscito, se è partito dalla copia dell'immagine.
2. **Provare il tasto ✨ in produzione.** La chiave Gemini sul pannello
   di Render c'è già; il modello di riserva non è mai stato provato con
   una chiave vera, perché in locale non ce n'è una.
3. **realme mostra «C61» invece di «realme C61»** (vedi §4).
4. **OPPO fermo al 69%** — invariato dalla v44.
