# Mobile Update Tracker — passaggio consegne (v32)

Aggiorna `passaggio-consegne-v31.md`.

- **511 test**, tutti verdi (erano 505).
- `DATA_LOGIC_VERSION` resta 24: cambia la copertura del chip, non
  l'interpretazione dei dati in archivio.

---

## Il guasto: la CPU rispondeva a macchia di leopardo

Segnalazione: «cercando a145f non trova la cpu, con a135f la trova».

Riprodotto: **nessuno dei due** si risolveva. Ma il punto non era quale
dei due funzionasse — era che la copertura sembrava casuale a chi la
usava, perché la tabella conteneva solo i top di gamma.

**L'errore era mio e di impostazione**, dichiarato già nel v26: avevo
tenuto la tabella corta di proposito e appoggiato tutto il resto su un
export della Play Console che Riccardo non ha. Una funzione che sulla
carta esiste e in pratica non risponde quasi mai è peggio di una funzione
assente, perché fa perdere tempo a capire se è rotta.

### Tre correzioni

**1. Copertura reale.** Da 68 a 134 voci: serie A completa (A03→A05s,
A13, A14 con le tre varianti di mercato, A15, A16, A23, A24, A25, A26,
A33→A36, A51, A52/A52s, A53→A56, A71→A73), S20 e Note20, S23 FE e S24 FE,
i pieghevoli Z Flip5/6 e Z Fold5/6.

La chiave resta il **codice completo e mai il nome**, perché le varianti
montano chip diversi: A13 4G è Exynos 850 e la 5G è Dimensity 700; il
Galaxy A14 monta Helio G80 nelle versioni `/F` e `/P` ed **Exynos 850
nella `/R`**. Senza il codice esatto la domanda non ha una risposta sola.

**2. Il chip si risolve dal numero di build.** La build Samsung comincia
col codice modello — `A325F`XXSCDYB2 — ed è spesso l'unico posto dove il
codice compare in una scheda dispositivo, dove il solo nome commerciale
non basterebbe a distinguere le varianti.

Nel farlo è emerso un difetto silenzioso: per le espressioni regolari il
**trattino basso è un carattere di parola**, quindi con `\b` il codice
dentro `CPH2649_16.0.7.201` non veniva riconosciuto. Per quei dispositivi
il chip non si sarebbe risolto mai.

**3. Il chip nella scheda dispositivo.** Prima compariva solo nel riquadro
di ricerca: guardando un telefono del parco di test non si vedeva. E
quando non è noto ora **lo dice** («SoC non disponibile») invece di
lasciare la riga vuota: un campo assente sembra un guasto dell'app, una
frase esplicita dice che il dato manca e dove aggiungerlo.

---

## Il limite che resta, dichiarato

`data/soc_modelli.csv` è **curato a mano**. Non esiste un dataset gratuito
e senza registrazione che risolva codice modello → SoC su tutta la fascia
media: la ricerca lo ha stabilito e resta vero.

Quindi la tabella cresce per aggiunte verificate, non per riempimento. Se
un modello manca, la riga da aggiungere è una sola e il formato è
documentato in testa al file. **Se una riga risultasse sbagliata, va
corretta lì**: è l'unico posto dove quel dato vive.

---

## Errori da non ripetere

I ventitré precedenti restano validi.

24. **Una funzione che risponde di rado è peggio di una che non c'è.**
    La tabella SoC corta era una scelta difendibile in astratto — meglio
    pochi dati giusti — ma in uso produceva l'impressione di uno strumento
    rotto, perché due modelli della stessa famiglia si comportavano in
    modo diverso senza una ragione visibile.

25. **`\b` non delimita dove c'è un trattino basso.** Vale per ogni
    estrazione di codici da stringhe di build e di versione.

---

## Cosa resta da fare

1. **Il filtro anti-rumore troppo permissivo** (20 notizie su 25
   riconosciute come rilascio): invariato dal v31, ed è ciò che continua a
   creare dispositivi fantasma tipo «Modello: Samsung».
2. **Identità unica per dispositivo**: invariato dal v30.
3. **Verificare in produzione** lo User-Agent FOTA (v30, mai visto girare).
4. Invariati: pin `starlette<1.4.0`, tracker ARB da sorvegliare.

---

## Il repo

**GitHub Desktop.** Ci sono `.github/`, `.streamlit/` e `data/`. CRLF di
`app.py` intatti.
