"""Fonti prioritarie: isolamento dei modelli, dei mercati e delle beta."""
from unittest.mock import patch

import pytest

from core import config as C, sources


def test_build_alone_does_not_stop_android_and_release_date_search():
    incomplete = sources.RawItem(title="test", device="OPPO A74", brand=C.OPPO, build="C.42")
    complete = sources.RawItem(title="test", device="OPPO A74", brand=C.OPPO, build="F.67",
                               android_version=13, published="2023-04-01")
    lookups = [sources.StructuredLookup(C.OPPO, lambda q: [incomplete], "basso", "prima"),
               sources.StructuredLookup(C.OPPO, lambda q: [complete], "basso", "seconda")]
    with patch.object(sources, "_lookup_order", return_value=lookups), \
         patch.object(sources, "expand_query", return_value=["OPPO A74"]), \
         patch.object(sources, "_scalda_fonti"):
        found, error = sources.lookup_model_structured("OPPO A74", C.OPPO)
    assert error is None
    assert found == [complete]
    assert incomplete.android_version is None  # niente metadati trasferiti fra build


def test_partial_firmware_survives_failed_later_source():
    incomplete = sources.RawItem(title="test", device="OPPO A74", brand=C.OPPO, build="C.42")
    def failure(q):
        raise RuntimeError("timeout")
    lookups = [sources.StructuredLookup(C.OPPO, lambda q: [incomplete], "basso", "prima"),
               sources.StructuredLookup(C.OPPO, failure, "basso", "seconda")]
    with patch.object(sources, "_lookup_order", return_value=lookups), \
         patch.object(sources, "expand_query", return_value=["OPPO A74"]), \
         patch.object(sources, "_scalda_fonti"):
        found, error = sources.lookup_model_structured("OPPO A74", C.OPPO)
    assert found == [incomplete]
    assert error is None


def test_redmi_stable_and_markets_survive_newer_beta():
    def record(version, date, branch="Stable"):
        return dict(name="Redmi Note 13", version=version, date=date,
                    branch=branch, android="14", codename="sapphire")
    data = [record("OS1.0.4.0.UNHEUXM", "2026-01-01"),
            record("OS1.0.5.0.UNHMIXM", "2026-02-01"),
            record("OS2.0.1.0.VNHEUXM", "2026-03-01", "Stable Beta"),
            record("OS3.0.26.3.1.DEV", "2026-04-01", "Public Beta")]
    with patch.object(sources, "fetch_yaml", return_value=(data, None)):
        items, error = sources._fetch_xiaomi_scarica()
    assert error is None
    assert {i.build for i in items} == {"OS1.0.4.0.UNHEUXM", "OS1.0.5.0.UNHMIXM"}


def test_oppo_legacy_service_number_is_not_android():
    packages = sources._pacchetti_realme_da_testo(
        "CPH2333export_11_F.73_2024110419020000.zip")
    assert len(packages) == 1
    assert packages[0].codice == "CPH2333"
    assert packages[0].build == "F.73"
    assert packages[0].android is None


def test_legacy_dated_branch_does_not_lose_to_larger_revision():
    packages = sources._pacchetti_realme_da_testo(
        "RMX3834GDPR_14_C.78_20250526230754.zip "
        "RMX3834GDPR_14_D.01_20260626230754.zip")
    assert max(packages, key=sources._chiave_pacchetto_realme).build == "D.01"


def test_gbfirmware_realme_exact_code_and_region():
    sources.reset_realme_firmware_cache()
    body = "RMX3834GDPR_14_C.73_20250217091923.zip RMX3834export_15_H.01_20260312121724.zip RMX3939GDPR_15_C.99_20260616191923.zip"
    with patch.object(sources, "_realme_codice_verificato", return_value=("RMX3834", "realme Note 50")), \
         patch.object(sources, "_archive_metadata", return_value=body) as get:
        items = sources._lookup_gbfirmware("realme Note 50")
        assert len(items) == 2
        assert items[0].build == "C.73"
        assert items[1].android_version == 15
        assert all(i.firmware_kind == C.FW_REPORTED for i in items)
        assert all(i.link == "https://gbfirmware.com/folder/rmx3834" for i in items)
        sources._lookup_gbfirmware("RMX3834")
        assert get.call_count == 1
    sources.reset_realme_firmware_cache()


def test_honor_keeps_variant_without_inventing_android():
    sources.reset_realme_firmware_cache()
    body = """ELI-N39 9.0.0.191(C185E7R3P1)_Firmware_Magic OS 9.0_0501AEEP.zip
    ELI-N39 9.0.0.180(C185E7R3P1)_Firmware_Magic OS 9.0_0501AEEP.zip
    ELI-N39 9.0.0.170(C185E4R3P1)_Firmware_Magic OS 9.0_0501AEEP.zip
    ELI-N39 9.0.0.190(C432E7R3P1)_Firmware_MagicOS 9.0_0501AEEP.zip
    ELI-NX9 10.0.0.199(C185E7R3P1)_Firmware_MagicOS 10.0_0501AEEP.zip
    ELI-N39 Repair Dead Boot [Unbrick].zip"""
    with patch.object(sources.modelcodes, "resolve", return_value=["HONOR 200"]), \
         patch.object(sources, "_archive_metadata", return_value=body):
        items = sources._lookup_honor_firmware_archive("ELI-N39")
    assert len(items) == 2
    assert {i.build for i in items} == {"9.0.0.191(C185E7R3P1)", "9.0.0.190(C432E7R3P1)"}
    assert all(i.android_version is None and i.firmware_kind == C.FW_REPORTED for i in items)
    sources.reset_realme_firmware_cache()


def test_gbfirmware_oppo_dispatch_and_unknown_code():
    sources.reset_realme_firmware_cache()
    with patch.object(sources, "_realme_codice_verificato", return_value=None), \
         patch.object(sources, "_oppo_codice_archivio_verificato", return_value=("CPH2333", "OPPO A96")) as verify, \
         patch.object(sources, "_archive_metadata", return_value="CPH2333export_11_F.73_2024110419020000.zip") as get:
        items = sources._lookup_gbfirmware("CPH2333")
        assert len(items) == 1
        assert items[0].device == "OPPO A96"
        assert items[0].build == "F.73"
        assert items[0].android_version is None
        verify.return_value = None
        assert sources._lookup_gbfirmware("CPH9999") == []
        assert get.call_count == 1
    sources.reset_realme_firmware_cache()


def test_honor_ambiguous_name_does_not_query_archive():
    with patch.object(sources.modelcodes, "codes_for_name", return_value=["ELI-N39", "ELI-NX9"]), \
         patch.object(sources.modelcodes, "resolve", return_value=["HONOR 200"]), \
         patch.object(sources, "_archive_metadata") as get:
        assert sources._lookup_honor_firmware_archive("HONOR 200") == []
        get.assert_not_called()


def test_archive_stream_stops_before_over_limit():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size):
            for _ in range(65):
                yield b"x" * 16384
    with patch.object(sources.requests, "get", return_value=Response()):
        with pytest.raises(ValueError, match="1 MiB"):
            sources._archive_metadata("https://gbfirmware.com/folder/rmx3834")
