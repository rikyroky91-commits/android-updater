# Passaggio di consegne — 2 settembre 2026 (v74)

> «è un moto g34. come mai gli altri lo trovano e noi no?»

## La risposta breve

Perché quel telefono il nostro database **lo scrive in un'altra lingua**, e
noi avevamo il vocabolario chiuso in un cassetto.

## La risposta lunga

La riga è `MOTOROLA,35264333,"MOTOROLA, FOGO5G23"`. `FOGO5G23` non è un
nome mancante: è il **nome in codice interno** di quel telefono — codename
`fogo`, rete 5G, anno 23 — e i database TAC gratuiti scrivono così tutta la
produzione Motorola recente:

```
MOTOROLA BRONCO23      bronco  → ThinkPhone
MOTOROLA IBIZA21       ibiza   → G50
MOTOROLA PENANG5G23    penang  → G53 5G
MOTOROLA PENANG5GNA23  penang  → G53 5G (variante Nord America)
MOTOROLA TAIPEI24      taipei  → G55
MOTOROLA PAROS24       paros   → G75
```

I siti commerciali quel nome ce l'hanno perché comprano un catalogo:
imei.info mantiene un database proprietario, e l'elenco ufficiale della
GSMA è a pagamento. Le nostre tre fonti sono dump gratuiti alimentati dalla
community, e per i Motorola la community ha scritto il codename.

**Ma la parte che riguarda noi è un'altra, ed è quella che ho corretto.**
Il dizionario per tradurre quei codename è **dentro questo progetto da
mesi**: `sources.MOTOROLA_LOLINET_DEVICES`, quaranta codename verificati
sull'indice XDA e sul database community, che serve a cercare i firmware
sul mirror lolinet. Nessuno aveva mai unito le due cose. Il database
parlava in codice, e il vocabolario stava due file più in là.

## Cosa ho cambiato

`imeicheck._nome_da_codename()`: quando il nome che resta è un nome in
codice — lettere, poi un eventuale `5G`/`NA`/`EU`, poi due cifre d'anno —
si cerca nella tabella dei codename e si usa il nome commerciale.

**La corrispondenza deve essere esatta** dopo aver tolto anno e marcatori.
`SABAHLITE23` non diventa `sabahl` per somiglianza, e `FOGO5G23` non
diventa `fogos`: somigliarsi non è essere lo stesso telefono. Quei due
restano come sono scritti — e infatti c'è un test che lo pretende.

E il nome che esce dalla tabella **non passa dal correttore di
maiuscole**: quello serve ai nomi TUTTI MAIUSCOLI del database TAC, e su
un nome verificato non corregge, rovina — «ThinkPhone» diventava
«Thinkphone».

## Il tuo moto g34

Per lui la traduzione automatica non basta, ed è giusto così: la tabella ha
`fogos` → G34 5G, ma `fogo` senza la esse le fonti pubbliche lo legano al
moto g 5G del 2024. Due telefoni diversi, e un TAC solo non decide.

Quello che decide sei tu, che il telefono ce l'hai in mano. Riga aggiunta a
`data/tac_modelli.csv`:

```
35264333, Motorola, moto g34 5G
```

con in nota da dove viene la verifica. Da adesso quel TAC risponde
**«Moto G34 5G»** — con la pastiglia 5G — subito, senza nessuna chiamata
esterna, e sopravvive a ogni riavvio perché quel file viaggia nel
repository.

## Cosa resta aperto

La scheda tecnica di quel modello: il catalogo GSMArena lo conosce come
«Motorola Moto G34», e adesso che il nome è giusto la scheda dovrebbe
arrivare da sola al prossimo giro. Se non arriva, dimmelo e guardo lì.

## Test

**1433, tutti verdi** (erano 1428). Cinque nuovi: un codename noto che
diventa nome commerciale, i marcatori di rete e regione che non
disturbano, il nome verificato che non passa dal correttore di maiuscole,
il fatto che somigliarsi non basta (`SABAHLITE23` e `FOGO5G23` restano
tali), e il moto g34 nella tabella curata.
