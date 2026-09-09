# Fonti firmware prioritarie — 9 settembre 2026

Base: v76, b96e27d0fcfb1b476f35b89011180a4848de4790.
Priorità richiesta: OPPO, realme, Honor, Redmi. Nessuna chiave API richiesta.

## Cambiamenti

- OPPO/realme: GBFirmware aggiunto alle ricerche strutturate per codice
  verificato, affiancando HalabTech. Una pagina per codice, cache dei soli
  risultati per un'ora, condivisa con gli altri archivi e limitata a 32 chiavi.
- OPPO: riconosciuti anche pacchetti legacy CPH, per esempio A96 F.73.
  Il campo service `_11_` non viene presentato come Android 11.
- realme: nei formati legacy la data interna ordina le build nello stesso
  ramo, evitando che C.78 superi un successivo D.01 solo per il numero 78.
- Honor: ricerca HalabTech per un solo codice verificato nel catalogo
  modelli; nomi con più codici restano ambigui. Il parser accetta nomi di
  firmware MagicOS completi, esclude i titoli di dump/repair, sceglie la
  build più alta per ramo Cxxx e conserva il suffisso completo E/R/P.
  Non deduce Android dalla versione MagicOS.
- Redmi/Xiaomi: solo `Stable`, mai `Stable Beta`, `Public Beta` o `.DEV`.
  Mercati identificati dal suffisso della build restano distinti anche con
  lo stesso nome commerciale. `DATA_LOGIC_VERSION=34` richiede la consueta
  ricostruzione dei dati derivati, per eliminare classificazioni precedenti.
- Risposte vuote HTTP 200 degli archivi non vengono memorizzate come
  assenza: possono essere challenge o cambiamenti del layout.

## Verifica pubblica dei metadati

HTTP 200, senza account e senza scaricare pacchetti firmware:

- https://gbfirmware.com/folder/rmx3834: C.73 GDPR / Android 14,
  H.01 Export / Android 15, realme Note 50.
- https://gbfirmware.com/folder/cph2333: F.73 Export, OPPO A96;
  Android lasciato sconosciuto dal parser.
- https://support.halabtech.com/index.php?a=downloads&b=search&keyword=ELI-N39&p_start=1:
  tra i pacchetti letti 10.0.0.156(C185E6R3P1).

Questo collaudo HTTP isola i parser usando identità modello fissate;
non prova la copertura del catalogo codici né quella dell'intero parco utenti.
I test offline verificano rifiuto delle identità ambigue e isolamento dei codici.

## Limiti operativi

Tutte le nuove build d'archivio sono `CURATED` + `REPORTED`. Non certificano
la disponibilità OTA, l'autenticità dei file o l'assenza di release successive.
Le date di caricamento non sono usate come date di rilascio. L'accesso ai
metadati è gratuito; ciò non garantisce download gratuiti dei firmware.
La ricerca Honor legge la prima pagina: la copertura è parziale.

Le nuove letture HTTP usano streaming con limite di 1 MiB decompresso per
pagina e timeout esistente. Questo limita i nuovi download, non l'intero RSS
del processo e non garantisce l'assenza di picchi sul piano Render da 512 MB.

Nuovi test: `tests/test_firmware_priority.py`; regressioni aggiornate in
`tests/test_realme_firmware.py`. Prima della pubblicazione verificare il job
Linux sull'esatto commit. Il deploy Render va confermato separatamente su
`/health`; il solo push non ne costituisce prova.
