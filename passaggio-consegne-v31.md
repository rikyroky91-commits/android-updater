# Mobile Update Tracker — passaggio consegne (v31)

Aggiorna `passaggio-consegne-v30.md`.

- **505 test**, tutti verdi (erano 501).
- **`DATA_LOGIC_VERSION` 23 → 24.** L'archivio contiene migliaia di righe
  scritte con la regola vecchia e va ricostruito: è lì che vive
  «Samsung A32 · Android 14».

---

## Il guasto: una notizia dettava la versione di un telefono

Schermata: cercando «samsung a32» compariva un dispositivo con
**Sistema: Android 14**, patch 2025-01, e **Build: `—`**.

Quel trattino è la chiave di tutto. Vuol dire che il dato **non veniva
dall'endpoint ufficiale**: veniva da un articolo. E il campo «Modello»
diceva `Samsung`, che non è un modello — è il marchio finito al posto del
modello. Il dispositivo mostrato era un fantasma costruito da una notizia,
non un telefono riconosciuto.

Nella stessa schermata: `25 notizie trovate, 20 riconosciute come rilascio
reale`. Venti su venticinque passano il filtro anti-rumore.

### La regola nuova

**Una fonte inaffidabile senza numero di build non può portare una
versione di sistema.**

Il numero di build è ciò che distingue l'osservazione di un rilascio da
un'opinione su un telefono: esiste solo se un pacchetto è stato davvero
distribuito. Un titolo che nomina un modello e una versione può parlare di
un aggiornamento *atteso*, di un elenco di dispositivi **esclusi**, o
semplicemente sbagliare — e il filtro a parole chiave non può distinguerli,
perché la differenza non è nel linguaggio ma nei fatti.

L'item resta visibile fra le notizie; smette solo di poter rispondere alla
domanda «a che versione sta questo telefono».

### Due limiti deliberati della regola

**Vale solo per le fonti inaffidabili.** Alcune fonti ufficiali danno la
versione senza build, e non vanno toccate.

**Il livello di patch resta.** È una rivendicazione più debole e più
verificabile: «ha ricevuto la patch di luglio» descrive un fatto datato,
mentre «Android 14» in un titolo parla quasi sempre di attese o di
idoneità. Cancellarlo faceva anche fallire un test che difendeva
esplicitamente quel comportamento — un buon segno che la prima versione
della regola era troppo larga.

---

## Errori da non ripetere

I ventidue precedenti restano validi.

23. **Un campo vuoto accanto a un campo pieno è un indizio, non un
    dettaglio estetico.** «Build: —» accanto a «Android 14» diceva già
    tutto: quella versione non veniva da nessun rilascio osservato. Nessun
    controllo la guardava.

---

## Cosa resta da fare

1. **Il filtro anti-rumore è ancora troppo permissivo** (20 su 25). La
   regola nuova ne limita il danno — le notizie non dettano più le
   versioni — ma continuano a creare *dispositivi*. Il passo successivo è
   non creare un dispositivo da una fonte inaffidabile quando il modello
   non è riconosciuto con certezza (il caso «Modello: Samsung»).
2. **Identità unica per dispositivo**: invariato dal v30.
3. **Verificare in produzione** che l'endpoint FOTA risponda davvero con
   lo User-Agent corretto (correzione v30, mai vista girare).
4. Invariati: pin `starlette<1.4.0`, copertura SoC, tracker ARB.

---

## Il repo

**GitHub Desktop.** Ci sono `.github/`, `.streamlit/` e `data/`. CRLF di
`app.py` intatti.
