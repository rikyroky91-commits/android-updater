"""Una memoria corta per le risposte che costano una connessione.

## Il numero che ha motivato questo file

Misurato sul sito vero il 2026-08-10, con il cronometro e non a occhio:

    GET /health                    0,26 s
    GET /                          1,25 s
    GET /?q=SM-S928B              12,84 s      ← la ricerca
    GET /?q=«modello inesistente»  16,58 s     (in locale; in rete peggio)

Dodici secondi non sono un dettaglio di rifinitura: sono il tempo in cui
una persona decide che il sito è rotto e ricarica la pagina. E ricaricare
la pagina rifaceva **tutto da capo**, perché fra due ricerche identiche
non c'era nessuna memoria: la seconda `SM-S928B` costava altre undici
richieste di rete e altri dodici secondi.

## Perché una cache qui è onesta e altrove non lo sarebbe

Questo progetto rifiuta per principio di mostrare un dato vecchio con
l'aria di uno nuovo. Una cache sembra la stessa cosa e non lo è, per una
ragione di scala: le fonti pubblicano un firmware **al massimo una volta
al giorno**, e la scansione periodica gira **una volta all'ora**. Tenere
una risposta per un quarto d'ora non nasconde niente che nel frattempo
possa essere cambiato — mentre rifare la stessa domanda alle stesse fonti
sessanta volte in un'ora infastidisce loro e rallenta noi.

La durata è configurabile e si può azzerare (`SEARCH_CACHE_SECONDS=0`)
per tornare esattamente al comportamento di prima.

## Due dettagli che sembrano pignoleria e non lo sono

**Si scade sul tempo MONOTONO**, non sull'orologio: l'ora di sistema può
saltare all'indietro (fuso, sincronizzazione), e una voce con scadenza
nel passato-che-torna-futuro resterebbe valida per ore.

**C'è un tetto al numero di voci.** Senza, ogni ricerca mai fatta resta
in memoria per sempre: su un host da 512 MB — dove questa applicazione è
già stata riavviata d'ufficio per memoria — una cache senza tetto è un
guasto che arriva fra due settimane, cioè quando nessuno la collega più
alla sua causa.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any


class CacheATempo:
    """Chiave → valore, con scadenza e capienza. Sicura fra thread.

    Il thread di scansione gira in sottofondo mentre le pagine si
    disegnano: senza il lucchetto, due letture simultanee possono
    incontrare il dizionario a metà di uno spostamento.
    """

    def __init__(self, durata_secondi: float, capienza: int = 200) -> None:
        self.durata = max(0.0, float(durata_secondi))
        self.capienza = max(1, int(capienza))
        self._voci: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lucchetto = threading.Lock()
        self.colpi = 0
        self.buchi = 0

    @property
    def attiva(self) -> bool:
        return self.durata > 0

    def leggi(self, chiave: str) -> Any | None:
        """Il valore se è ancora fresco, altrimenti `None`.

        `None` non è memorizzabile, ed è voluto: significa «non ce l'ho»,
        e distinguere «assente» da «presente e vale None» costerebbe un
        involucro per un caso che qui non serve.
        """
        if not self.attiva:
            return None
        with self._lucchetto:
            voce = self._voci.get(chiave)
            if voce is None:
                self.buchi += 1
                return None
            scadenza, valore = voce
            if time.monotonic() >= scadenza:
                # Scaduta: si toglie subito invece di lasciarla occupare
                # un posto fino al prossimo sfoltimento.
                del self._voci[chiave]
                self.buchi += 1
                return None
            # Rimessa in fondo: la capienza sfoltisce le MENO usate di
            # recente, non le più vecchie in assoluto.
            self._voci.move_to_end(chiave)
            self.colpi += 1
            return valore

    def scrivi(self, chiave: str, valore: Any) -> None:
        if not self.attiva or valore is None:
            return
        with self._lucchetto:
            self._voci[chiave] = (time.monotonic() + self.durata, valore)
            self._voci.move_to_end(chiave)
            while len(self._voci) > self.capienza:
                self._voci.popitem(last=False)

    def dimentica(self, chiave: str) -> None:
        """Toglie una voce sola: serve dopo un'azione che la smentisce."""
        with self._lucchetto:
            self._voci.pop(chiave, None)

    def svuota(self) -> None:
        with self._lucchetto:
            self._voci.clear()
            self.colpi = self.buchi = 0

    def stato(self) -> dict:
        """Per la Diagnostica: una cache che non si vede non si controlla."""
        with self._lucchetto:
            voci = len(self._voci)
        domande = self.colpi + self.buchi
        return {
            "attiva": self.attiva,
            "voci": voci,
            "capienza": self.capienza,
            "durata_minuti": round(self.durata / 60, 1),
            "colpi": self.colpi,
            "domande": domande,
            "resa": round(100 * self.colpi / domande) if domande else 0,
        }
