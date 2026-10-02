"""L'estensione del browser (`estensione/`) usa gli stessi file del sito.

Quello che si difende:
  - il pacchetto è aggiornato: chi cambia `ring.js`, la tendina o il suo stile
    e dimentica `python3 estensione/costruisci.py` lo scopre qui;
  - il manifest chiede il permesso minimo (la scheda su cui si clicca), non
    l'accesso a tutti i siti;
  - niente codice caricato da fuori: tutto sta nel pacchetto.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
PACCHETTO = RADICE / "estensione" / "pacchetto"


class TestEstensione(unittest.TestCase):

    def test_il_pacchetto_e_aggiornato_con_i_file_del_sito(self):
        esito = subprocess.run([sys.executable, str(RADICE / "estensione" / "costruisci.py"), "--verifica"],
                               capture_output=True, text=True)
        self.assertEqual(esito.returncode, 0, esito.stdout + esito.stderr)

    def test_manifest_v3_col_permesso_minimo(self):
        m = json.loads((PACCHETTO / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["manifest_version"], 3)
        self.assertEqual(sorted(m["permissions"]), ["activeTab", "scripting", "storage"])
        self.assertNotIn("host_permissions", m)
        self.assertNotIn("content_scripts", m)       # parte solo al clic sull'icona
        for lato in ("16", "48", "128"):
            self.assertTrue((PACCHETTO / m["icons"][lato]).exists())
        self.assertTrue((PACCHETTO / m["background"]["service_worker"]).exists())

    def test_il_ring_e_lo_stesso_file_del_sito(self):
        self.assertEqual((PACCHETTO / "ring.js").read_text(encoding="utf-8"),
                         (RADICE / "web" / "static" / "ring.js").read_text(encoding="utf-8"))

    def test_niente_codice_da_fuori_e_niente_rete(self):
        for nome in ("prepara.js", "sfondo.js", "ring.js"):
            testo = (PACCHETTO / nome).read_text(encoding="utf-8")
            for vietato in ("fetch(", "XMLHttpRequest", "eval(", "new Function", "importScripts(", "<script"):
                self.assertNotIn(vietato, testo, f"{nome}: {vietato}")

    def test_la_tendina_sta_in_uno_shadow_dom_con_lo_stile_costruito(self):
        testo = (PACCHETTO / "prepara.js").read_text(encoding="utf-8")
        self.assertIn("attachShadow", testo)
        self.assertIn("adoptedStyleSheets", testo)
        self.assertIn("data-pannello", testo)
        self.assertIn("__ringDeposito", testo)
        self.assertIn("chrome.storage.local", testo)


if __name__ == "__main__":
    unittest.main()
