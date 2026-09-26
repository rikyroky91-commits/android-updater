"""Traduzione delle novità in italiano (`core/traduzioni.py`), con un Gemini finto."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, storage, traduzioni  # noqa: E402
from web import presenters as P  # noqa: E402


class FintaRisposta:
    def __init__(self, dati, status=200):
        self.status_code = status
        self._dati = dati

    def json(self):
        return self._dati

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class TestTraduzioni(unittest.TestCase):
    def setUp(self):
        self._db_prima = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        with storage.transaction() as conn:
            for i, titolo in enumerate(["Galaxy S24 gets One UI 8", "Pixel 9 receives the September patch"]):
                conn.execute(
                    "INSERT INTO updates (id, brand, device_model, title, summary, firmware_kind,"
                    " is_relevant, published, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (f"u{i}", "Samsung", "Galaxy S24", titolo, "Rollout started in Europe.",
                     "reported", 1, "2026-09-25", "2026-09-25T10:00:00", "2026-09-25T10:00:00"))
        self._env = {k: os.environ.get(k) for k in ("GEMINI_API_KEY", "BACKUP_SOLO_LETTURA")}
        os.environ["GEMINI_API_KEY"] = "finta"
        os.environ.pop("BACKUP_SOLO_LETTURA", None)
        self._post = traduzioni.requests.post
        self._pausa = traduzioni.PAUSA_FRA_LOTTI
        traduzioni.PAUSA_FRA_LOTTI = 0

    def tearDown(self):
        traduzioni.requests.post = self._post
        traduzioni.PAUSA_FRA_LOTTI = self._pausa
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        storage.reset_state()
        C.DB_PATH = self._db_prima
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass

    def _gemini(self, tradotte):
        inviate = []

        def post(url, headers=None, json=None, timeout=None):
            inviate.append(json)
            testo = globals()["json"].dumps(tradotte)
            return FintaRisposta({"candidates": [{"content": {"parts": [{"text": testo}]}}]})

        traduzioni.requests.post = post
        return inviate

    def test_traduce_e_salva(self):
        inviate = self._gemini([
            {"id": "u0", "titolo": "Galaxy S24 riceve One UI 8", "riassunto": "Il rollout è partito in Europa."},
            {"id": "u1", "titolo": "Pixel 9 riceve la patch di settembre", "riassunto": ""},
            {"id": "estraneo", "titolo": "non deve entrare", "riassunto": ""},
        ])
        self.assertEqual(traduzioni.traduci_nuove(max_lotti=1), 2)
        self.assertEqual(len(inviate), 1, "le voci devono andare in UNA chiamata")
        m = traduzioni.mappa(["u0", "u1", "estraneo"])
        self.assertEqual(m["u0"]["titolo"], "Galaxy S24 riceve One UI 8")
        self.assertNotIn("estraneo", m)
        # Una seconda volta non c'è più niente da tradurre.
        self.assertEqual(traduzioni.da_tradurre(10), [])

    def test_senza_chiave_non_fa_niente(self):
        os.environ.pop("GEMINI_API_KEY", None)
        self.assertFalse(traduzioni.attiva())
        self.assertEqual(traduzioni.traduci_nuove(), 0)

    def test_sola_lettura_non_traduce(self):
        os.environ["BACKUP_SOLO_LETTURA"] = "true"
        self.assertFalse(traduzioni.attiva())

    def test_la_voce_mostra_italiano_e_originale(self):
        voce = P.voce_feed({"title": "Galaxy S24 gets One UI 8", "summary": "Rollout started."})
        voce = P.con_traduzione(voce, {"titolo": "Galaxy S24 riceve One UI 8",
                                       "riassunto": "Il rollout è partito."})
        self.assertEqual(voce["titolo"], "Galaxy S24 riceve One UI 8")
        self.assertEqual(voce["titolo_originale"], "Galaxy S24 gets One UI 8")
        self.assertEqual(voce["riassunto_originale"], "Rollout started.")

    def test_fonte_gia_italiana_nessun_originale(self):
        voce = P.con_traduzione(P.voce_feed({"title": "Aggiornamento per Galaxy S24"}),
                                {"titolo": "Aggiornamento per Galaxy S24", "riassunto": ""})
        self.assertNotIn("titolo_originale", voce)


if __name__ == "__main__":
    unittest.main()
