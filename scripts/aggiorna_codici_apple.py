"""Rigenera `data/apple_codici_modello.csv` dalla pagina ufficiale Apple
«Identificare il modello di iPhone» (support.apple.com/en-us/108044).

Il «codice modello» che si legge su un iPhone (Impostazioni > Generali >
Info, o sul retro dei modelli vecchi) è il numero A: A2403, A1586... Né
ipsw.me né l'endpoint firmware di Apple lo elencano: parlano solo di
identificativi interni (iPhone13,2). La tabella cambia una volta l'anno,
quando esce un modello nuovo, quindi si tiene nel repository e si rilancia
questo script a mano:

    python3 scripts/aggiorna_codici_apple.py            # scarica la pagina
    python3 scripts/aggiorna_codici_apple.py pagina.html  # da un file salvato

Il sito non scarica mai la pagina da solo e i test non toccano la rete.
"""
from __future__ import annotations

import csv
import html
import os
import re
import sys

URL = "https://support.apple.com/en-us/108044"
DESTINAZIONE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "apple_codici_modello.csv")
_RE_CODICE = re.compile(r"\bA\d{4}\b")


def _testo(pagina: str) -> list[str]:
    testo = html.unescape(re.sub(r"<[^>]+>", "\n", pagina))
    return [r.strip() for r in testo.split("\n") if r.strip()]


def estrai(pagina: str) -> list[tuple[str, str, str]]:
    """(nome, codice, mercato) nell'ordine della pagina."""
    righe = _testo(pagina)
    voci: list[tuple[str, str, str]] = []
    visti: set[str] = set()
    i = 0
    while i < len(righe):
        riga = righe[i]
        if not re.match(r"(?i)(model numbers?\b|the model number on the back)", riga):
            i += 1
            continue
        # Il nome è l'ultima riga «iPhone …» prima dei codici.
        j = i - 1
        while j >= 0 and not re.match(r"^iPhone(\s|$)", righe[j]):
            j -= 1
        nome = righe[j] if j >= 0 else ""
        # I codici possono andare a capo: si raccoglie fino a «Details».
        blocco, k = [], i
        while k < len(righe) and not righe[k].startswith("Details"):
            blocco.append(righe[k])
            k += 1
        i = k
        testo = " ".join(blocco)
        trovati = list(_RE_CODICE.finditer(testo))
        if not nome or not trovati:
            continue
        for n, m in enumerate(trovati):
            fine = trovati[n + 1].start() if n + 1 < len(trovati) else len(testo)
            mercato = testo[m.end():fine]
            mercato = re.sub(r"[()]", " ", mercato).strip(" ,.;")
            mercato = re.sub(r"\s+", " ", mercato)
            mercato = re.sub(r"\s+\d+$", "", mercato)   # i rimandi alle note («Japan 2»)
            if m.group(0) in visti:
                continue
            visti.add(m.group(0))
            voci.append((nome, m.group(0), mercato))
    return voci


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        with open(argv[1], encoding="utf-8") as f:
            pagina = f.read()
    else:
        import requests
        pagina = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    voci = estrai(pagina)
    if len(voci) < 100:
        print(f"solo {len(voci)} codici: la pagina è cambiata, non sovrascrivo", file=sys.stderr)
        return 1
    with open(DESTINAZIONE, "w", encoding="utf-8", newline="") as f:
        scrittore = csv.writer(f)
        scrittore.writerow(["nome", "codice", "mercato"])
        scrittore.writerows(voci)
    print(f"scritti {len(voci)} codici di {len({v[0] for v in voci})} modelli in {DESTINAZIONE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
