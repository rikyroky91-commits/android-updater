from pathlib import Path
from unittest.mock import Mock, patch
import threading

import pytest
import yaml

from core import sources
from web.memory_monitor import MemoryMonitor


def test_yaml_records_match_real_catalog_fixture():
    text = (Path(__file__).parent / "fixtures/xiaomi_latest.yml").read_text(encoding="utf-8")
    assert sources._yaml_catalogo_a_blocchi(text) == yaml.safe_load(text)


def test_yaml_parser_rejects_oversized_record():
    with pytest.raises(ValueError, match="64 KiB"):
        sources._yaml_catalogo_a_blocchi("- name: " + "x" * 65537)


def test_default_lookup_does_not_launch_background_downloads():
    fetch = Mock()
    voce = sources.StructuredLookup("test", lambda q: [], "basso", "test", fetch)
    with patch.dict("os.environ", {"PRERISCALDA_FONTI_RICERCA": "false"}), \
         patch.object(sources, "ThreadPoolExecutor") as pool:
        sources._scalda_fonti([voce])
    pool.assert_not_called()
    fetch.assert_not_called()


def test_monitor_runs_without_requests_and_stops():
    sampled = threading.Event()
    monitor = MemoryMonitor(interval=0.01)
    with patch("web.memory_monitor.alleggerisci_se_serve", side_effect=lambda: (sampled.set() or {"fatto": False})), \
         patch("web.memory_monitor.memoria_mb", return_value=381), \
         patch("web.memory_monitor.memoria_picco_mb", return_value=400):
        monitor.start()
        try:
            assert sampled.wait(2)
        finally:
            monitor.stop()
    assert not monitor.thread.is_alive()
