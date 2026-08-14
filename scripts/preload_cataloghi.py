"""Prepara il database iniziale incluso nell'immagine Docker.

Non e' un worker e non raccoglie aggiornamenti firmware: scarica solo gli
indici pubblici che il sito usa per rispondere alle ricerche. Il processo
gira durante la build, quando la memoria non e' quella limitata del servizio
Render, cosi' la prima visita non deve costruire cataloghi da zero.
"""
from __future__ import annotations

from core import (aer_catalog, imeicheck, modelcodes, motorola_catalog, soc,
                  sources, specs, storage)


def main() -> None:
    storage.init_db()
    passi = (
        ("TAC", imeicheck._build_index),
        ("codici modello", lambda: modelcodes.resolve("SM-A057F")),
        ("schede tecniche", specs.carica),
        # L'indice SoC viene usato da ogni risultato per completare la
        # scheda. Senza questo passo la prima ricerca dopo un deploy poteva
        # scaricare il dataset multi-marca durante la richiesta, con attese
        # lunghe e un picco di RAM sul piano Render da 512 MB.
        ("processori", soc._indice_dataset),
        ("catalogo Android Enterprise", aer_catalog.carica),
        ("codici Motorola", motorola_catalog.carica),
        ("bollettino sicurezza Honor", sources.fetch_honor_security_bulletin),
    )
    pronti = []
    for nome, carica in passi:
        try:
            carica()
            pronti.append(nome)
        except Exception as errore:
            # Una fonte temporaneamente indisponibile non deve bloccare un
            # deploy: l'app sa aggiornarla o riprovarla a runtime.
            print(f"catalogo {nome} non precaricato: {errore}")
    print("cataloghi precaricati: " + (", ".join(pronti) or "nessuno"))


if __name__ == "__main__":
    main()
