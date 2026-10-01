"""Controllo notturno: una trentina di ricerche note contro il sito vero.

    python scripts/controllo_notturno.py https://mobileupdatetracker.duckdns.org

Esce con codice 1 se una ricerca che deve funzionare non funziona più: il
workflow `controllo-notturno.yml` fallisce e GitHub manda l'email.

## Perché queste ricerche

Ognuna protegge qualcosa che si è già rotto o che conta di più:

* le forme che il banco di prova del 26/09/2026 ha trovato rotte — la
  marca davanti al nome («Apple iPhone 16») o al codice («Samsung
  SM-S921B», «Oppo CPH2789»), le forme Nothing senza «Phone»;
* un modello di punta per ogni fonte firmware strutturata, così se una
  fonte cambia formato lo si sa la mattina dopo e non quando qualcuno
  cerca proprio quel telefono.

Il controllo è volutamente di MANICA LARGA sul nome («contiene», senza
distinguere maiuscole): una fonte che scrive «OnePlus 15» o «ONEPLUS 15»
va bene uguale. Sul firmware invece no: dove lo si aspetta, deve esserci.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

# (ricerca, il nome deve contenere, serve anche il firmware)
CASI: list[tuple[str, str, bool]] = [
    # --- regressioni del 26/09/2026 ---
    ("Apple iPhone 16", "iphone 16", True),
    ("Samsung SM-S921B", "galaxy s24", True),
    ("Oppo CPH2789", "a6s", True),
    ("OnePlus CPH2707", "nord 5", True),
    ("Nothing (3a)", "phone (3a)", True),
    ("CMF Phone 1", "cmf phone 1", True),
    # --- una per fonte firmware ---
    ("iPhone 15 Pro", "iphone 15 pro", True),          # Apple (ipsw.me)
    ("Galaxy S24 Ultra", "s24 ultra", True),           # Samsung FOTA
    ("SM-A556B", "a55", True),                         # Samsung per codice
    ("Redmi Note 14S", "note 14s", True),              # Xiaomi tracker
    ("2502FRA65G", "note 14s", True),                  # Xiaomi per codice
    ("Pixel 9", "pixel 9", False),                     # Pixel: solo beta
    ("OnePlus 15", "oneplus 15", True),                # tracker OnePlus/OPPO
    ("CPH2745", "oneplus 15", True),
    ("realme Note 50", "note 50", True),               # archivi realme
    ("RMX3834", "note 50", True),
    ("Nothing Phone (3)", "phone (3)", True),          # archivio Nothing
    ("A059P", "phone (3a) pro", True),
    ("HONOR 400 Lite", "400 lite", False),             # HONOR: supporto
    # g85 e S50 Neo condividono il codice XT2427-4: l'archivio Motorola
    # lo chiama S50 Neo. Stesso hardware, si accettano entrambi.
    ("moto g85", "g85|s50 neo", False),               # Motorola
    ("vivo X200", "x200", False),                      # vivo: fabbrica
    # --- nomi e codici ---
    ("Galaxy A07", "a07", True),
    ("SM-A075F", "a07", True),
    ("iPhone 17 Pro Max", "17 pro max", True),
    ("Xiaomi 15T", "15t", True),
]

TIMEOUT = 60


def cerca(base: str, query: str) -> dict:
    url = f"{base.rstrip('/')}/api/cerca?q={urllib.parse.quote(query)}"
    richiesta = urllib.request.Request(url, headers={"User-Agent": "controllo-notturno"})
    with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:
        return json.loads(risposta.read().decode("utf-8"))


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "https://mobileupdatetracker.duckdns.org"
    guasti = []
    for query, atteso, serve_firmware in CASI:
        inizio = time.monotonic()
        try:
            esito = cerca(base, query)
        except Exception as errore:
            guasti.append(f"{query}: richiesta fallita ({errore})")
            print(f"ERRORE  {query}: {errore}", flush=True)
            continue
        secondi = time.monotonic() - inizio
        nome = esito.get("nome", "")
        problemi = []
        # «a|b»: va bene uno qualsiasi dei nomi (telefoni con più nomi veri).
        if not any(forma in nome.lower() for forma in atteso.lower().split("|")):
            problemi.append(f"nome «{nome}», atteso che contenga «{atteso}»")
        if serve_firmware and not esito.get("firmware"):
            problemi.append("nessun firmware")
        # IL CODICE MODELLO ACCANTO AL NOME (richiesta del 30/09/2026): un
        # risultato col solo nome commerciale non dice quale variante è.
        if "codici_modello" in esito and not esito.get("codici_modello"):
            problemi.append("nessun codice modello")
        stato = "OK    " if not problemi else "GUASTO"
        codice = (esito.get("codici_modello") or [""])[0]
        print(f"{stato}  {query:22} {secondi:5.1f}s  {nome[:34]:34}  {codice[:14]:14}  "
              f"{esito.get('riga', '')[:60]}",
              flush=True)
        if problemi:
            guasti.append(f"{query}: " + "; ".join(problemi))
    print()
    if guasti:
        print(f"{len(guasti)} ricerche su {len(CASI)} non funzionano come dovrebbero:")
        for g in guasti:
            print(f"  - {g}")
        return 1
    print(f"Tutte le {len(CASI)} ricerche funzionano.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
