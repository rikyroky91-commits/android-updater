"""Una scansione, in un processo a sé, e poi fuori.

    python -m core.scan_isolata            # con notifiche
    python -m core.scan_isolata --no-notify

PERCHÉ ESISTE (22/09/2026). Il sito veniva ucciso per memoria anche dopo
tutte le correzioni di settembre. `/health?dettaglio=1` lo diceva in due
numeri: 94 MB appena avviato, 310-345 MB dopo qualche scansione oraria —
e solo 62 di quei MB erano cataloghi. Il resto è il mucchio che una
scansione lascia dietro di sé dentro il processo web: migliaia di voci,
testi di feed, risposte HTTP, il salvataggio compresso. Python libera gli
oggetti, ma le arene frammentate restano al processo (`restituiti` era
0,0 a ogni giro), e il pavimento non torna più giù. Su quel pavimento
bastava una ricerca pesante per superare i 512 MB.

Dentro lo stesso processo questo non si risolve: si può solo rimandare.
Un processo che finisce, invece, restituisce al sistema TUTTO, sempre,
senza eccezioni. La scansione gira qui; il processo web la lancia, la
aspetta e resta leggero. I risultati passano dall'archivio SQLite, che è
già il punto di incontro di tutto il resto (WAL, busy_timeout).
"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Una scansione isolata")
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args(argv)

    from . import scan, storage

    storage.init_db()
    risultato = scan.run_scan(auto_notify=not args.no_notify)
    if risultato.get("skipped"):
        print(f"scansione isolata saltata: {risultato.get('reason')}", flush=True)
        return 0
    memoria = risultato.get("memoria") or {}
    print(f"scansione isolata: trovati={risultato.get('total', 0)} "
          f"nuovi={risultato.get('new', 0)} "
          f"memoria_figlio_mb={memoria.get('dopo il salvataggio')}", flush=True)
    return 1 if risultato.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
