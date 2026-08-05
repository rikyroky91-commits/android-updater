# Mobile Update Tracker — passaggio consegne (v25)

Aggiorna `passaggio-consegne-v24.md`. Le parti non ripetute qui restano
valide come scritte lì.

---

## Cos'è cambiato

- **413 test**, tutti verdi (erano 378). Nessuno tocca la rete.
- **`DATA_LOGIC_VERSION` resta 22.** È stata aggiunta una fonte, non è
  cambiata l'interpretazione di una fonte esistente.
- Nuova fonte `core/oplus_arb.py`, piste morte documentate in `FONTI.md`.

```bash
python -m unittest discover -s tests
```

---

## La fonte nuova: tracker ARB OnePlus/OPPO

`Bartixxx32/OnePlus-antirollchecker` — progetto community nato per
avvisare chi fa flashing del rischio di brick da anti-rollback. Il numero
di build, per lui, è un sottoprodotto. Per noi è il dato.

**È migliore del canale Telegram**, e per questo lo precede nell'ordine
dei lookup: entrambi sono community, ma questo è generato da uno script
che scarica i firmware veri e ne estrae i dati, l'altro è la prosa di una
persona. A parità di trust, vince la macchina.

**Cosa dà che nessun'altra fonte dà: la build per regione.** Lo stesso
OnePlus 13 è `CPH2653_16.0.5.703` in Europa e `CPH2649_16.0.7.201` in
India — build che non procedono di pari passo. Per un parco misto è metà
del lavoro.

**Copertura misurata:** OnePlus quasi per intero, più Reno10 Pro, Find
N3/N5, Find X3/X5, Find X8 Ultra. **Non** la serie A di OPPO, **non**
realme, **non** vivo.

### Le tre decisioni che vale la pena ricordare

1. **Si legge il README, non i JSON in `data/`.** GitHub blocca
   l'esplorazione automatica delle cartelle, quindi il contenuto di
   `data/` non è stato visto e costruirci sopra un parser sarebbe
   indovinare. Il README è generato da `generate_readme.py`: è un formato
   macchina scritto in Markdown. Se un domani si vedesse un JSON stabile,
   migrare è mezz'ora.

2. **Le tabelle di storico vengono ignorate, ed è il punto.** Il README
   ne contiene due tipi; quelle storiche elencano build superate.
   Prenderle per correnti direbbe a chi fa QA che un telefono è fermo a
   una versione che ha lasciato mesi fa. Il discriminante è la colonna
   `Region`, criterio strutturale che regge al riordino delle colonne.

3. **Non si deduce la versione di Android dalla build.** OxygenOS 16 gira
   su Android 16 quasi sempre. "Quasi" non basta per un campo che decide
   un retest completo: meglio vuoto che plausibile.

Nel giro periodico si tiene **una sola regione per dispositivo** (la build
più avanzata), perché l'archivio è indicizzato per telefono e cinque
regioni si sovrascriverebbero a vicenda. Tutte le regioni restano
visibili nella ricerca a comando, dove servono.

---

## Le piste chiuse, e perché

Documentate per esteso in `FONTI.md` per non riaprirle fra sei mesi.

- **User-Agent**: morta. Chrome congela modello e versione dalla 110
  (feb 2023), rollout completo entro la 113. Il `Build/` non c'è più.
- **Geekbench e benchmark**: mostrano solo `Android 16`, mai la build.
  Verificato su pagine di risultati reali.
- **Cataloghi Google**: l'intuizione era giusta — Google i fingerprint li
  ha — ma non li pubblica. Firebase Test Lab dà le versioni *supportate
  in laboratorio*, non quella installata.
- **AndroidDumps**: valutata e **non integrata**. Sulla carta la migliore
  (è l'unico posto col livello di patch), ma la misura ha detto: A6x
  assente, Find X9 assente, vivo assente; per la coda lunga un solo dump
  fatto al lancio, cioè la versione di fabbrica; e il sito blocca i
  lettori automatici. Quello che copre è già coperto meglio dall'ARB.
- **EPREL**: ufficiale e obbligatoria per legge, ma espone una *promessa*
  di durata in anni, non la versione installata. È la trappola di Honor
  scritta in un regolamento europeo.

---

## Errori da non ripetere

I quattordici precedenti restano validi. Se ne aggiunge uno.

15. **Non dedurre un campo che decide un'azione.** La tentazione di
    ricavare la versione di Android dal numero di OxygenOS era forte e
    sarebbe stata giusta nel 95% dei casi. Ma il 5% finisce in un retest
    completo ordinato a torto, o peggio non ordinato quando serviva.

---

## Cosa resta da fare

1. **Verificare i due involucri al primo giro in produzione.** Restano i
   soli pezzi non provati su dati vivi: l'HTML della vista `/s/` di
   Telegram e il fatto che `raw.githubusercontent.com` restituisca il
   README come atteso. Entrambe le fonti falliscono **rumorosamente** —
   diventano rosse in Diagnostica, non verdi e vuote — ma vanno guardate.

2. **Sorvegliare che il tracker ARB sia vivo.** Il README letto diceva
   `Last updated: 2026-05-17`. Se quella data smette di avanzare, la
   fonte va spenta. `oplus_arb.copertura()` restituisce `ultima_verifica`
   apposta.

3. **L'A6x resta scoperto**, e con lui la serie A di OPPO, realme e vivo.
   Non è un difetto da correggere: è che quel dato non esiste in forma
   pubblica. L'app ora lo dice invece di mostrare una scheda vuota.

4. Unificare i punti d'accesso alla rete, notifica sul retest, accordo
   fra fonti indipendenti: invariati dal v23.

**Cosa NON fare**: aggiungere altre marche o fonti generiche. Invariato.

---

## Il repo

Invariato: **l'upload dal browser di GitHub salta i file e le cartelle
che iniziano con un punto**. Usare **GitHub Desktop**. CRLF di `app.py`
intatti (1447, nessuna riga con solo LF).
