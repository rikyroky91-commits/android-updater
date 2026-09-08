"""Verifica configurazione TAC; --live esegue una ricerca consumando quota.

Eseguire nello stesso ambiente del sito, con le chiavi nelle variabili
d'ambiente. Non stampa chiavi, URL con token o IMEI completi.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import imeicheck, storage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="interroga i fornitori configurati")
    parser.add_argument("--tac", default="35135531", help="esattamente 8 cifre TAC")
    args = parser.parse_args()
    if len(args.tac) != 8 or not args.tac.isascii() or not args.tac.isdigit():
        parser.error("fornire solo le prime 8 cifre (TAC)")
    storage.init_db()
    configurati = imeicheck.fornitori_tac()
    risultato = {"fornitori": [f["nome"] for f in configurati], "live": args.live}
    if args.live:
        esito, modello = imeicheck.cerca_tac_online_esito(args.tac)
        risultato.update(esito=esito, modello=modello,
                         diagnosi=imeicheck.ultimo_esito_servizio())
    print(json.dumps(risultato, ensure_ascii=False, indent=2))
    return 0 if configurati and (not args.live or risultato["esito"] == "trovato") else 1


if __name__ == "__main__":
    raise SystemExit(main())
