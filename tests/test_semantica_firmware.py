"""Regressioni per la semantica delle fonti firmware.

Una fonte che identifica un modello o dichiara la versione di fabbrica non
può far apparire un "ultimo firmware" né creare un dispositivo aggiornato.
Un rollout riportato e verificabile resta consultabile, ma è inferiore a una
build interrogata direttamente.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, scan, sources, storage  # noqa: E402


class TestSemanticaFonti(unittest.TestCase):
    def setUp(self):
        self._path = tempfile.mktemp(suffix=".db")
        self._old_path = C.DB_PATH
        C.DB_PATH = self._path
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self._path + suffix)
            except OSError:
                pass
        C.DB_PATH = self._old_path

    @staticmethod
    def _source(key, kind):
        return sources.Source(
            key=key, label=key, trust=C.TRUST_STRUCTURED, fetch=lambda: ([], None),
            brand=C.OPPO, firmware_kind=kind,
        )

    def _save(self, kind, title="realme Note 50 Android 14"):
        raw = sources.RawItem(
            title=title, brand=C.OPPO, device="realme Note 50",
            version="Android 14", firmware_kind=kind,
        )
        storage.upsert_update(scan.normalize(raw, self._source("test_" + kind, kind)))

    def test_factory_never_creates_current_device(self):
        self._save(C.FW_FACTORY)
        self.assertEqual(storage.get_devices(), [])
        self.assertEqual(storage.get_device_history("oppo / realme / oneplus|realme note 50"), [])

    def test_reported_rollout_is_kept_but_current_wins(self):
        self._save(C.FW_REPORTED, "realme Note 50 Android 14 rollout")
        self._save(C.FW_CURRENT, "realme Note 50 Android 15 official build")
        devices = storage.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["os_version"], "Android 15")
        self.assertEqual(len(storage.get_device_history(devices[0]["device_key"])), 2)

    def test_kind_mapping_never_promotes_aer_or_beta(self):
        self.assertEqual(
            sources.firmware_kind_for(self._source("realme_aer", C.FW_REPORTED)),
            C.FW_FACTORY,
        )
        self.assertEqual(
            sources.firmware_kind_for(self._source("pixel_ota", C.FW_REPORTED)),
            C.FW_BETA,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
