"""Il sito e il worker devono fare le stesse manutenzioni all'avvio.

Sono due percorsi d'avvio per lo stesso archivio: `web/main.py` quando si
apre il sito e `worker.py` su GitHub Actions o su una macchina sempre
accesa. Finché fanno cose diverse, una correzione nella lettura delle
fonti vale in uno e non nell'altro — e il `tracker.db` committato ogni
ora dal workflow continua a riportare indietro i dati vecchi, annullando
la correzione in silenzio. È l'errore 41 del passaggio consegne.

**ED È GIÀ SUCCESSO DI NUOVO.** Questo file controllava `app.py` e
`worker.py`, cioè la dashboard Streamlit e il worker. Quando il sito è
diventato il percorso principale nessuno ha spostato il controllo, e
`web/main.py` è nato senza `migra_chiavi_dispositivo` e senza
`purge_retired_sources`: due manutenzioni che giravano ovunque tranne
che nel posto da cui passa la gente. Ora il controllo guarda i percorsi
che esistono davvero.

I file si leggono invece di eseguirli: importare `web.main` avvia il
thread di scansione e il worker entra in un ciclo infinito, quindi
«eseguirli» qui non vorrebbe dire niente. Quello che serve verificare è
che entrambi CHIAMINO le stesse manutenzioni, ed è visibile così.
"""
from __future__ import annotations

import os
import unittest

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Manutenzioni che decidono cosa c'è in archivio, quindi vanno fatte da
# qualunque percorso lo alimenti.
MANUTENZIONI = (
    "rebuild_if_logic_changed",
    "migra_chiavi_dispositivo",
)

# I percorsi d'avvio vivi. `app.py` è stato tolto con la dashboard.
PERCORSI = ("web/main.py", "worker.py")


def _sorgente(nome: str) -> str:
    with open(os.path.join(RADICE, nome), encoding="utf-8") as f:
        return f.read()


class TestManutenzioniAllAvvio(unittest.TestCase):

    def test_entrambi_i_percorsi_le_eseguono(self):
        for percorso in PERCORSI:
            testo = _sorgente(percorso)
            for funzione in MANUTENZIONI:
                with self.subTest(percorso=percorso, funzione=funzione):
                    self.assertIn(
                        f"{funzione}()", testo,
                        f"{percorso} non esegue {funzione}: l'archivio che "
                        "alimenta resterà indietro rispetto alla logica")

    def test_la_migrazione_segue_la_ricostruzione(self):
        """Migrare righe che stanno per essere cancellate è lavoro
        sprecato. L'ordine non cambia il risultato, ma è quello sensato e
        va fissato prima che qualcuno lo inverta per riordinare."""
        for percorso in PERCORSI:
            testo = _sorgente(percorso)
            with self.subTest(percorso=percorso):
                self.assertLess(testo.index("rebuild_if_logic_changed()"),
                                testo.index("migra_chiavi_dispositivo()"))

    def test_il_sito_ripristina_l_archivio_esterno(self):
        """IL DIFETTO CHE QUESTO TEST FERMA, e che è costato caro.

        `avvio()` chiamava `backup.ripristina_se_serve()`, che in
        `core/backup.py` non esiste — si chiama `ripristina()`.
        L'`AttributeError` finiva in un `except Exception: pass` e
        spariva: su un host con il disco effimero l'archivio ripartiva
        vuoto a ogni risveglio, e il salvataggio su Gist non veniva letto
        nemmeno una volta.

        Si verifica che la funzione chiamata ESISTA davvero, non che sia
        scritta in un certo modo: è il controllo che mancava.
        """
        from core import backup
        from web import main

        testo = _sorgente("web/main.py")
        self.assertIn("backup.ripristina(", testo)
        for nome in ("ripristina", "configurato", "salva"):
            with self.subTest(funzione=nome):
                self.assertTrue(callable(getattr(backup, nome, None)),
                                f"web/main chiama backup.{nome}, che non esiste")
        self.assertTrue(callable(main.avvio))


class TestLaVariabileDellArchivioHaEffetto(unittest.TestCase):
    """`DB_PATH` era dichiarata in due posti e non la leggeva nessuno.

    Il `Dockerfile` e `render.yaml` impostano `DB_PATH=/tmp/tracker.db`,
    con tanto di nota sul perché l'archivio deve stare in `/tmp` su un
    host col disco effimero. `core/config.py` leggeva però soltanto
    `TRACKER_DB`: la variabile non ha mai avuto alcun effetto, e in
    produzione l'archivio è sempre finito nella cartella di lavoro.

    Non dava errore. Dava un file in un posto diverso da quello
    documentato — e quel posto è anche quello da cui `_semina_archivio`
    legge la copia di partenza, che quindi l'applicazione si sarebbe
    riscritta sotto.
    """

    def _dichiarate(self, percorso: str) -> str:
        return _sorgente(percorso)

    def test_le_due_variabili_funzionano_entrambe(self):
        import importlib

        from core import config

        for variabile in ("TRACKER_DB", "DB_PATH"):
            with self.subTest(variabile=variabile):
                prima = {v: os.environ.pop(v, None) for v in ("TRACKER_DB", "DB_PATH")}
                os.environ[variabile] = "/percorso/di/prova.db"
                try:
                    importlib.reload(config)
                    self.assertEqual(config.DB_PATH, "/percorso/di/prova.db",
                                     f"{variabile} non ha effetto")
                finally:
                    os.environ.pop(variabile, None)
                    for nome, valore in prima.items():
                        if valore is not None:
                            os.environ[nome] = valore
                    importlib.reload(config)

    def test_quella_dichiarata_nell_immagine_e_una_di_quelle_lette(self):
        """Se il Dockerfile dichiarasse un terzo nome, il test lo direbbe
        qui invece che dopo il deploy."""
        import re

        testo = self._dichiarate("Dockerfile") + self._dichiarate("render.yaml")
        nominate = set(re.findall(r"\b(DB_PATH|TRACKER_DB)\b", testo))
        self.assertTrue(nominate, "l'immagine non dichiara dove sta l'archivio")
        self.assertTrue(nominate <= {"DB_PATH", "TRACKER_DB"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
