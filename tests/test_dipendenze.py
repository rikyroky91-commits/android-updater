"""Il file delle dipendenze è un artefatto critico quanto il codice.

Il 2026-08-05 l'app è rimasta irraggiungibile senza che nel repo fosse
cambiata una riga: `requirements.txt` non fissava `starlette`, è uscita la
1.4.0, e il middleware di compressione di Streamlit ha smesso di
funzionare. Ogni richiesta HTTP rispondeva 500 e il container si
riavviava in ciclo.

È una classe di guasto diversa da tutte le altre coperte qui: **non
dipende da cosa fa il codice, ma da cosa installa il server il giorno del
deploy.** Un test che legge il file è l'unico modo di accorgersene senza
un ambiente di produzione.
"""
from __future__ import annotations

import os
import re
import unittest

REQUIREMENTS = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "requirements.txt")


def _righe_utili() -> list[str]:
    with open(REQUIREMENTS, encoding="utf-8") as f:
        righe = []
        for riga in f:
            pulita = riga.split("#")[0].strip()
            if pulita:
                righe.append(pulita)
        return righe


class TestVincoloStarlette(unittest.TestCase):

    def test_starlette_ha_un_tetto(self):
        """Senza tetto l'installatore prende l'ultima versione e il deploy
        si rompe da solo, senza che nel repo cambi niente."""
        righe = _righe_utili()
        starlette = [r for r in righe if r.lower().startswith("starlette")]
        self.assertTrue(starlette, "manca il vincolo su starlette: il deploy si rompera'")
        self.assertRegex(starlette[0], r"<\s*1\.4")

    def test_il_motivo_e_scritto_accanto_al_vincolo(self):
        """Un pin senza spiegazione viene tolto dal primo che fa pulizia.
        Il nome dell'errore deve essere cercabile nel file."""
        with open(REQUIREMENTS, encoding="utf-8") as f:
            testo = f.read()
        self.assertIn("thread_minimum_size", testo)
        self.assertIn("GZipResponder", testo)


class TestDipendenzeDichiarate(unittest.TestCase):
    """Ogni pacchetto importato dal progetto deve essere dichiarato."""

    ATTESI = ("streamlit", "requests", "feedparser", "pandas", "pyyaml", "openpyxl")

    def test_i_pacchetti_usati_sono_elencati(self):
        nomi = {re.split(r"[<>=!\[]", r, 1)[0].strip().lower() for r in _righe_utili()}
        for pacchetto in self.ATTESI:
            with self.subTest(pacchetto=pacchetto):
                self.assertIn(pacchetto, nomi)

    def test_il_file_e_leggibile_riga_per_riga(self):
        """Un commento a fine riga non deve far parte del nome del
        pacchetto: `uv` lo tollera, ma un errore di battitura qui non
        darebbe nessun avviso — solo un pacchetto mancante a runtime."""
        for riga in _righe_utili():
            with self.subTest(riga=riga):
                self.assertNotIn("#", riga)
                self.assertRegex(riga, r"^[A-Za-z0-9_.\-]+")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
