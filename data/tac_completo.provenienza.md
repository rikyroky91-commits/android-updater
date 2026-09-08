# Copia completa TAC

- Fonte: https://raw.githubusercontent.com/MoazEb/tac-database/main/tac_full.csv
- Acquisizione: 8 settembre 2026.
- 254.997 righe ricevute; 254.717 con TAC normalizzabile conservate.
- Formato: Brand,TAC,SPECS, UTF-8, gzip; nessun IMEI completo.
- Riproduzione: `python scripts/aggiorna_istantanea_tac.py --completa`.

La copia completa serve quando il download e la cache non sono disponibili.
Non si applica il filtro dell'era Android al file: modelli recenti possono
non avere anno o codice modello nella descrizione. Il filtro resta attivo
nell'indice in memoria; la seconda lettura cerca nei file anche i TAC esclusi.

`tac_era_android.csv.gz` resta disponibile per compatibilità e come ulteriore
ripiego. La nuova copia è una fotografia di un database community: aumenta
la copertura offline, non certifica la correttezza dei singoli abbinamenti.
