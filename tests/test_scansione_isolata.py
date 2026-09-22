"""La scansione oraria gira in un processo a sé (22/09/2026).

In produzione il processo web partiva da 94 MB e dopo qualche scansione
oraria stava fra 310 e 345, con solo 62 MB di cataloghi: il resto era il
mucchio lasciato dalla scansione, che dentro lo stesso processo non torna
al sistema. Un processo figlio che finisce lo restituisce tutto.
"""
import os
import subprocess
import unittest
from unittest import mock

from core import scan, util


class TestScansioneIsolata(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.get("SCANSIONE_ISOLATA")
        os.environ.pop("SCANSIONE_ISOLATA", None)

    def tearDown(self):
        if self._env is None:
            os.environ.pop("SCANSIONE_ISOLATA", None)
        else:
            os.environ["SCANSIONE_ISOLATA"] = self._env

    def test_di_default_parte_un_processo_figlio(self):
        with mock.patch.object(scan.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0)) as run, \
             mock.patch.object(scan, "run_scan") as nel_processo:
            esito = scan.run_scan_isolata(auto_notify=False)
        comando = run.call_args.args[0]
        self.assertEqual(comando[1:3], ["-m", "core.scan_isolata"])
        self.assertIn("--no-notify", comando)
        nel_processo.assert_not_called()
        self.assertTrue(esito["isolata"])
        self.assertIsNone(esito["error"])

    def test_un_figlio_fallito_non_si_ripete_nel_processo_web(self):
        """Rifarla qui dentro sarebbe proprio il picco da evitare."""
        with mock.patch.object(scan.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1)), \
             mock.patch.object(scan, "run_scan") as nel_processo:
            esito = scan.run_scan_isolata()
        nel_processo.assert_not_called()
        self.assertIn("codice 1", esito["error"])

    def test_se_il_figlio_non_parte_si_ripiega_nel_processo(self):
        with mock.patch.object(scan.subprocess, "run", side_effect=OSError("fork negato")), \
             mock.patch.object(scan, "run_scan", return_value={"skipped": False}) as nel_processo:
            scan.run_scan_isolata()
        nel_processo.assert_called_once()

    def test_si_puo_spegnere_dall_ambiente(self):
        os.environ["SCANSIONE_ISOLATA"] = "false"
        with mock.patch.object(scan.subprocess, "run") as run, \
             mock.patch.object(scan, "run_scan", return_value={}) as nel_processo:
            scan.run_scan_isolata()
        run.assert_not_called()
        nel_processo.assert_called_once()

    def test_un_figlio_bloccato_non_blocca_il_ciclo(self):
        with mock.patch.object(scan.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("x", 1)):
            esito = scan.run_scan_isolata()
        self.assertIn("oltre", esito["error"])

    def test_il_ciclo_usa_il_figlio_e_poi_avvisa(self):
        """Dopo la scansione le risposte ricordate vanno buttate: il
        processo web non vede più la scansione accadere."""
        chiamate = []
        fermo = mock.Mock()
        fermo.wait.return_value = True   # un solo giro
        with mock.patch.object(scan, "seconds_until_next_scan", return_value=0), \
             mock.patch.object(scan, "run_scan_isolata",
                               side_effect=lambda **k: chiamate.append("scan")):
            scan._loop(fermo, dopo_scansione=lambda: chiamate.append("svuota"))
        self.assertEqual(chiamate, ["scan", "svuota"])


class TestMemoriaContenitore(unittest.TestCase):
    def test_fuori_da_un_contenitore_risponde_none_o_un_numero(self):
        valore = util.memoria_contenitore_mb()
        self.assertTrue(valore is None or valore > 0)


if __name__ == "__main__":
    unittest.main()
