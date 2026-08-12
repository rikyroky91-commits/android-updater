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

DUE FILE DALL'11/08/2026, NON PIÙ UNO SOLO. `app.py` (il prototipo
Streamlit) è tornato nel repository, su richiesta esplicita, per girare
IN PARALLELO al sito — non al suo posto. Streamlit Cloud e Render leggono
build separate, quindi anche le dipendenze si sono separate:
`requirements.txt` (radice) è quello che Streamlit Cloud scopre da solo,
`requirements-web.txt` è quello che il `Dockerfile` installa per Render.
Ogni test qui sotto controlla il file giusto per la domanda che fa,
invece di uno solo per tutto — mescolarli rifarebbe esattamente
l'errore che la v46 aveva tolto (streamlit nell'immagine di Render).
"""
from __future__ import annotations

import os
import re
import unittest

_RADICE = os.path.dirname(os.path.dirname(__file__))
REQUIREMENTS_WEB = os.path.join(_RADICE, "requirements-web.txt")
REQUIREMENTS_STREAMLIT = os.path.join(_RADICE, "requirements.txt")


def _righe_utili(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        righe = []
        for riga in f:
            pulita = riga.split("#")[0].strip()
            if pulita:
                righe.append(pulita)
        return righe


def _nomi(path: str) -> set[str]:
    return {re.split(r"[<>=!\[]", r, 1)[0].strip().lower() for r in _righe_utili(path)}


class TestVincoloStarlette(unittest.TestCase):
    """IL TETTO SU STARLETTE È STATO TOLTO, e questo test ora difende il
    contrario di prima.

    `starlette<1.4.0` esisteva per un difetto del middleware di
    compressione di **Streamlit**, che istanziava `GZipResponder` con la
    firma vecchia e faceva morire ogni richiesta con
    «missing 1 required keyword-only argument: thread_minimum_size».
    Quel vincolo aveva senso solo finché streamlit e FastAPI condividevano
    un `requirements.txt` — un pin messo per l'uno finiva per legare anche
    l'altro. Dall'11/08/2026 non condividono più nemmeno il file: un
    conflitto del genere non può più ripresentarsi per costruzione, non
    solo perché streamlit «non c'è più» (è tornato, ma altrove).

    Un pin che sopravvive alla ragione per cui era stato messo è il
    genere di cosa che nessuno osa togliere perché nessuno ricorda
    perché c'era. Qui la ragione è scritta, ed è finita.
    """

    def test_starlette_non_ha_piu_un_tetto(self):
        righe = _righe_utili(REQUIREMENTS_WEB)
        starlette = [r for r in righe if r.lower().startswith("starlette")]
        self.assertEqual(starlette, [],
                         "il tetto su starlette serviva a Streamlit, che ora ha un file suo")

    def test_streamlit_e_pandas_non_sono_dipendenze_del_sito(self):
        """`requirements-web.txt` è quello che il Dockerfile installa per
        Render: erano la maggior parte del tempo di build e del peso
        dell'immagine, per una dashboard che qui non gira più (gira su
        Streamlit Cloud, da un file separato — vedi
        TestRequirementsStreamlit)."""
        nomi = _nomi(REQUIREMENTS_WEB)
        self.assertNotIn("streamlit", nomi)
        self.assertNotIn("pandas", nomi)


class TestDipendenzeDichiarate(unittest.TestCase):
    """Ogni pacchetto importato dal sito/worker deve essere dichiarato
    in `requirements-web.txt` — il file che Render installa davvero."""

    # Tolti `streamlit` e `pandas` il 2026-08-10 con la dashboard; restano
    # i pacchetti che il sito e il worker importano davvero. Dall'11/08
    # letti da `requirements-web.txt`, non più da `requirements.txt`
    # (quello ora serve a Streamlit Cloud, vedi il docstring del modulo).
    ATTESI = ("requests", "feedparser", "pyyaml", "openpyxl",
              "fastapi", "uvicorn", "jinja2", "python-multipart")

    def test_i_pacchetti_usati_sono_elencati(self):
        nomi = _nomi(REQUIREMENTS_WEB)
        for pacchetto in self.ATTESI:
            with self.subTest(pacchetto=pacchetto):
                self.assertIn(pacchetto, nomi)

    def test_il_file_e_leggibile_riga_per_riga(self):
        """Un commento a fine riga non deve far parte del nome del
        pacchetto: `uv` lo tollera, ma un errore di battitura qui non
        darebbe nessun avviso — solo un pacchetto mancante a runtime."""
        for riga in _righe_utili(REQUIREMENTS_WEB):
            with self.subTest(riga=riga):
                self.assertNotIn("#", riga)
                self.assertRegex(riga, r"^[A-Za-z0-9_.\-]+")


class TestRequirementsStreamlit(unittest.TestCase):
    """`requirements.txt` (radice) dall'11/08/2026 non è più il file del
    sito: è quello che Streamlit Cloud scopre da solo per `app.py`. Un
    test qui protegge la ragione per cui è stato separato — non deve
    tornare a pesare quanto quello del sito, né sparire lui stesso."""

    ATTESI = ("streamlit", "requests", "feedparser")

    def test_i_pacchetti_di_app_py_sono_elencati(self):
        nomi = _nomi(REQUIREMENTS_STREAMLIT)
        for pacchetto in self.ATTESI:
            with self.subTest(pacchetto=pacchetto):
                self.assertIn(pacchetto, nomi)

    def test_pandas_non_e_una_dipendenza(self):
        """`app.py` non importa pandas — solo streamlit, requests,
        feedparser e la libreria standard. Aggiungerlo qui senza che il
        codice lo usi rimetterebbe peso senza motivo."""
        self.assertNotIn("pandas", _nomi(REQUIREMENTS_STREAMLIT))

    def test_il_file_e_leggibile_riga_per_riga(self):
        for riga in _righe_utili(REQUIREMENTS_STREAMLIT):
            with self.subTest(riga=riga):
                self.assertNotIn("#", riga)
                self.assertRegex(riga, r"^[A-Za-z0-9_.\-]+")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
