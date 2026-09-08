"""Rigenera la copia del database TAC che viaggia dentro il repository.

## Perché una copia nel repository

Il database TAC si scarica da un URL solo. Finché risponde va tutto bene;
quando risponde `HTTP 429` — capitato il 17/08/2026 — l'app che parte da
un archivio vuoto non riconosce più nessun IMEI, e i test che dipendono da
quel download raccontano cose diverse a seconda della connessione. Un
dato che si trova solo in rete è un dato che si può perdere.

La copia qui dentro ribalta il rapporto: la baseline sta nel repository,
la rete serve solo ad AGGIORNARLA. Se non risponde, il sito funziona
comunque — con dati vecchi di qualche settimana, il che per un database
di codici TAC è irrilevante: i modelli usciti nel frattempo mancano, gli
altri no.

## Perché solo l'era Android

Il file intero è 11,8 MB (1,9 compresso). L'era Android — anno dal 2017
in poi, oppure un codice modello, lo stesso criterio dell'indice in
memoria — sono 4,5 MB, cioè **0,5 compresso**: un decimo di quello che
l'app già scarica per i soli codici Google Play. Il resto sono Motorola
StarTAC e Nokia a tasti, che questa applicazione non sa comunque
descrivere.

    python scripts/aggiorna_istantanea_tac.py

Va rilanciato ogni tanto — diciamo ad ogni stagione di uscite — e il file
prodotto va committato.
"""
from __future__ import annotations

import csv
import argparse
import gzip
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("AVVIA_WORKER", "0")

from core import imeicheck, storage  # noqa: E402

DESTINAZIONE = os.path.join(imeicheck.CARTELLA_DATI, "tac_era_android.csv.gz")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completa", action="store_true",
                        help="conserva tutti i TAC per le ricerche offline fuori indice")
    args = parser.parse_args()
    storage.init_db()
    grezzo = imeicheck._cached_bytes()
    if not grezzo:
        print("la fonte non risponde e non c'è copia in cache: "
              f"istantanea non aggiornata ({imeicheck.status()})")
        return 1

    righe = list(csv.DictReader(io.StringIO(grezzo.decode("utf-8", "replace"))))
    if not righe:
        print("il file scaricato non contiene righe leggibili: formato cambiato?")
        return 1

    tenute = [r for r in righe
              if (args.completa or imeicheck._dell_era_android(r.get("SPECS") or r.get("specs") or ""))
              and imeicheck._tac_normalizzato(r.get("TAC") or r.get("tac"))]
    if args.completa and len(tenute) < 200_000:
        print("copia completa sospettosamente piccola: file non sostituito")
        return 1
    if len(tenute) < len(righe) // 10:
        # Una caduta simile significa che il formato è cambiato e il
        # criterio non riconosce più niente. Meglio non sovrascrivere una
        # copia buona con una vuota.
        print(f"solo {len(tenute)} righe su {len(righe)} superano il criterio: "
              "sospetto cambio di formato, istantanea non aggiornata")
        return 1

    buffer = io.StringIO()
    scrittore = csv.DictWriter(buffer, fieldnames=["Brand", "TAC", "SPECS"],
                               lineterminator="\n")
    scrittore.writeheader()
    for r in tenute:
        scrittore.writerow({
            "Brand": r.get("Brand") or r.get("brand") or "",
            # LO ZERO INIZIALE SI RIMETTE PRIMA DI SCRIVERE. La fonte lo
            # perde per 6 344 righe (vedi `_tac_normalizzato`): il lettore
            # ora lo ricostruisce comunque, ma un file che gira dentro il
            # repository e che si apre a mano deve contenere il TAC vero,
            # non quello che un foglio di calcolo ha accorciato.
            "TAC": imeicheck._tac_normalizzato(r.get("TAC") or r.get("tac")),
            "SPECS": r.get("SPECS") or r.get("specs") or "",
        })

    dati = gzip.compress(buffer.getvalue().encode("utf-8"), 9, mtime=0)
    destinazione = (os.path.join(imeicheck.CARTELLA_DATI, "tac_completo.csv.gz")
                    if args.completa else DESTINAZIONE)
    with open(destinazione + ".tmp", "wb") as f:
        f.write(dati)
    os.replace(destinazione + ".tmp", destinazione)
    print(f"istantanea aggiornata: {len(tenute)} TAC su {len(righe)}, "
          f"{len(dati) / 1e6:.1f} MB compressi in {destinazione}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
