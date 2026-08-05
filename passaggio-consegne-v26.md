# Mobile Update Tracker — passaggio consegne (v26)

Aggiorna `passaggio-consegne-v25.md`.

- **448 test**, tutti verdi (erano 413). Nessuno tocca la rete.
- **`DATA_LOGIC_VERSION` resta 22.**
- Novità: `core/soc.py` + `data/`. E una **regressione corretta**.

---

## La regressione, prima di tutto

Introdotta da me due sessioni fa, quando i lookup hanno cominciato a
dichiarare il trust. I risultati delle fonti non ufficiali venivano
marcati `curated_lookup` invece di `official_lookup`, e due punti
riconoscevano solo la vecchia chiave:

1. `app.py` li classificava fra le **notizie** — cioè il tracker ARB e il
   canale di rollout, le uniche fonti che coprono OnePlus e OPPO recenti,
   comparivano come articoli di giornale.
2. `storage.purge_retired_sources` li trattava da **fonte ritirata** e li
   cancellava dall'archivio a ogni giro.

Il secondo era il peggiore: cancellava in silenzio proprio i dispositivi
per cui quelle fonti erano state aggiunte. Nessun test se n'era accorto
perché entrambi i punti confrontavano una stringa, e le stringhe
combaciavano ancora — per l'altra chiave. Ora c'è
`tests/test_regressione_curated.py`, che verifica anche che la vecchia
forma del confronto non torni.

**Lezione**: quando si aggiunge un valore a un enumerato di fatto (qui le
chiavi sorgente), vanno cercati *tutti* i confronti con i valori
esistenti. Un `grep` della stringa vecchia avrebbe trovato il problema in
dieci secondi.

---

## Il SoC accanto al firmware

**Perché serve al QA**: un difetto legato al chip si riproduce solo su una
delle varianti. Il Galaxy S24 `SM-S921B` (Europa) monta Exynos 2400, lo
`SM-S921U` (USA) monta Snapdragon 8 Gen 3. Stesso nome, stesso firmware,
chip diverso.

Da qui la scelta strutturale: **il SoC si risolve per codice modello, non
per nome.** Una fonte che dice "Galaxy S24 → Snapdragon" è sbagliata per
metà del mondo. È il criterio con cui sono state scartate quasi tutte le
fonti in circolazione (dettagli in `FONTI.md`).

### Tre fonti, in ordine

1. **Catalogo Google Play** (`data/play_device_catalog.csv`) — l'unica
   gratuita e strutturata col SoC per codice esatto. **Non inclusa**: si
   esporta dalla Play Console (serve un account) e si mette nel repo.
   L'app la legge da disco, senza rete né credenziali a runtime. Il SoC
   di un modello non cambia mai, quindi un export ogni pochi mesi basta.
2. **Regole deterministiche** Apple e Pixel — lecite perché lì non
   esistono varianti di mercato.
3. **Tabella curata** (`data/soc_modelli.csv`) — corta di proposito.

### Le decisioni da non disfare

- **Niente regola sul suffisso Samsung B/U.** Cambia a ogni generazione:
  S22 e S24 splittano, S23 e S25 no, e nella stessa generazione l'Ultra
  può seguire una regola diversa. Dedurlo sarebbe un errore sistematico,
  quindi un `SM-xxxxB` non in tabella resta "non disponibile".
- **iPad fuori.** La numerazione mescola generazioni e formati; una
  regola lì sarebbe indovinare. Stessa cosa per le generazioni iPhone
  oltre la 17, non verificate.
- **La tabella curata resta corta.** Chi legge un risultato non distingue
  una riga verificata da una ricordata male.
- **Ambiguità dichiarata, non silenzio.** Chi cerca "galaxy s24" senza
  codice riceve *entrambe* le varianti e l'invito a cercare la sigla.
  Sapere che ne esistono due è già operativo.

### Da verificare al primo export vero

L'importatore del catalogo Play è scritto sulle intestazioni
**documentate** da Google, non su un file catturato: il download richiede
il login. È l'unico pezzo non provato su dati reali. Le colonne sono
riconosciute per nome e non per posizione, e il campo arriva nella forma
`Qualcomm SDM855` — col produttore davanti alla sigla, cosa che un test
ha già colto e corretto.

---

## Errori da non ripetere

I quindici precedenti restano validi.

16. **Aggiungere un valore a un enumerato senza cercare i confronti con i
    vecchi valori.** Vedi la regressione sopra: due `==` su una stringa,
    nessun errore di tipo, nessun test rosso, dati cancellati in silenzio.

---

## Cosa resta da fare

1. **Esportare il catalogo Play** se si vuole copertura SoC vera oltre a
   Samsung S-series, Apple e Pixel. È il singolo intervento che cambia di
   più, e non richiede codice.
2. Verificare i tre involucri non provati su dati vivi: HTML `/s/` di
   Telegram, README del tracker ARB da `raw.githubusercontent.com`, CSV
   del catalogo Play. Tutti falliscono rumorosamente, ma vanno guardati.
3. Sorvegliare che il tracker ARB avanzi (`oplus_arb.copertura()`).
4. Invariati dal v23: unificare gli accessi di rete, notifica sul retest,
   accordo fra fonti indipendenti.

**Cosa NON fare**: aggiungere altre marche o fonti generiche.

---

## Il repo

**L'upload dal browser di GitHub salta i file e le cartelle che iniziano
con un punto**, e ora c'è anche `data/` da non dimenticare. Usare
**GitHub Desktop**. CRLF di `app.py` intatti.
