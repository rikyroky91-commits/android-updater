# Mobile Update Tracker — passaggio consegne (v27)

Aggiorna `passaggio-consegne-v26.md`.

- **463 test**, tutti verdi (erano 448). Nessuno tocca la rete.
- **`DATA_LOGIC_VERSION` resta 22.**
- Sessione di sole correzioni: la ricerca per codice modello era rotta.

---

## Il guasto segnalato

«Cercando SM-A075F/DS e SM-S928B non trova alcun modello o aggiornamenti.»

Tre difetti distinti, tutti pre-esistenti, ciascuno capace da solo di far
sembrare l'app rotta. **Nessuno era coperto dai test**, ed è la cosa che
va notata: 448 test verdi mentre la funzione più usata non rispondeva.

### 1. Il suffisso di variante — `/DS`

`SM-A075F/DS` è la forma stampata sulla scatola e mostrata in «Info
software»: è quella che chiunque copia naturalmente. La barra non era
prevista da nessuna delle espressioni che riconoscono un codice modello,
quindi `looks_like_model_code` diceva no e **la ricerca non partiva
proprio**. Nessun errore, nessun messaggio: silenzio.

Ora c'è `sources.normalizza_codice_modello`, che toglie `/DS`, `/DSN`,
`DUOS` e simili. **L'ordine conta**: il suffisso va tolto *prima* di
comprimere gli spazi, altrimenti «SM-A075F DS» diventa «SM-A075FDS», che
ha ancora la forma di un codice valido — quindi non verrebbe segnalato
come errore, verrebbe solo cercato invano. C'è un test apposta.

### 2. Quattro region, tutte europee

`SAMSUNG_CSC_CANDIDATES` era `["ITV", "DBT", "EUX", "XEO"]`. Per un
`SM-A075F`, venduto soprattutto in India e Asia, nessuna di quelle
quattro distribuisce il firmware: l'endpoint rispondeva 404 quattro volte
e la ricerca concludeva «niente». Il firmware esiste, si stava guardando
nel posto sbagliato.

Ora la lista copre Europa, India, Nord America, Asia-Pacifico, Medio
Oriente, Africa e America Latina, con le region multi-paese in testa
perché coprono di più con una richiesta sola. La ricerca si ferma alla
prima che risponde, quindi la lista più lunga **non costa tempo** quando
il modello è europeo: costa solo quando altrimenti non si troverebbe
nulla.

### 3. Il silenzio quando le fonti firmware tacciono — il peggiore

Il progetto ha in casa ~70.000 codici modello (MobileModels + lista
Google Play) e un modulo che sa quale chip monta un dispositivo. Se però
nessuna fonte firmware rispondeva, tutto questo restava inutilizzato e la
ricerca restituiva «niente» — dando l'impressione che l'app fosse rotta,
mentre sapeva benissimo di che telefono si trattava.

Il difetto è concettuale: **confondeva due domande diverse.**

    «che telefono è?»      → quasi sempre rispondibile
    «a che firmware sta?»  → dipende dal produttore

Ora `scan._identifica_senza_firmware` è l'ultimo ripiego: riconosce il
modello dai dataset già scaricati e ci aggiunge il SoC, restituendo un
item **senza** versione, build o patch. L'interfaccia lo distingue già e
mostra «riconosciuto, ma questa fonte non pubblica la versione
firmware». Riempirlo di campi inventati per farlo sembrare un risultato
pieno sarebbe stato il contrario di quello che serve.

Se il codice non è nei dataset, la risposta resta vuota: non si tira a
indovinare un modello.

---

## Errori da non ripetere

I sedici precedenti restano validi.

17. **Testare la logica e non il percorso completo.** Le funzioni di
    riconoscimento del codice erano coperte; la domanda «cosa succede se
    un utente digita il codice come lo legge sul telefono?» no. I test di
    regressione nuovi partono dall'input dell'utente e arrivano al
    risultato, non dal pezzo intermedio.

18. **Una lista di costanti è una scelta di copertura, non configurazione.**
    Quelle quattro region europee non erano un dettaglio tecnico:
    decidevano quali mercati l'app poteva servire, e nessuno lo aveva
    scritto da nessuna parte.

---

## Cosa resta da fare

1. **Verificare in produzione con la rete vera.** Le correzioni sono
   provate con l'endpoint simulato: il container di sviluppo non ha rete.
   Se `SM-S928B` continuasse a non dare la build con la rete attiva, il
   sospetto successivo è il formato della risposta FOTA, non il codice.
2. Invariati dal v26: esportare il catalogo Play per la copertura SoC,
   verificare i tre involucri non provati su dati vivi (HTML Telegram,
   README ARB, CSV Play), sorvegliare che il tracker ARB avanzi.

---

## Il repo

**GitHub Desktop.** Ci sono `.github/`, `.streamlit/` e `data/` che
l'upload da browser salterebbe. CRLF di `app.py` intatti.
