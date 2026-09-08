"""Regressioni delle risposte documentate e delle assenze memorizzate."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import imeicheck as I, storage


@pytest.fixture(autouse=True)
def isolato(monkeypatch):
    meta = {}
    monkeypatch.setattr(storage, "get_meta", lambda key, default=None: meta.get(key, default))
    monkeypatch.setattr(storage, "set_meta", lambda key, value: meta.__setitem__(key, value))
    for key in list(I.os.environ):
        if key.startswith("TAC_API_"):
            monkeypatch.delenv(key)
    I.reset_cache()
    yield meta
    I.reset_cache()


def servizio(monkeypatch, payload, status=200):
    risposta = SimpleNamespace(status_code=status, json=lambda: payload, text="", headers={})
    client = SimpleNamespace(get=Mock(return_value=risposta), post=Mock(return_value=risposta))
    monkeypatch.setattr(I, "requests", client)
    monkeypatch.setenv("TAC_API_KEY", "test-key")
    return client


@pytest.mark.parametrize("payload,status", [
    ({"success": False, "code": 401}, 200),
    ({"success": False, "code": 402}, 200),
    ({"success": False, "code": 429}, 200),
    ({}, 200), ({}, 404),
    ({"brand": "Samsung"}, 200),
    ({"brand": "Samsung", "model": "Samsung"}, 200),
    ({"brand": "Samsung", "model": "Galaxy A54", "tac": "11111111"}, 200),
])
def test_errori_non_diventano_assenze(monkeypatch, payload, status):
    servizio(monkeypatch, payload, status)
    assert I.cerca_tac_online_esito("35135531") == ("errore", None)
    assert I.ultimo_esito_servizio()["esito"] == "errore"


@pytest.mark.parametrize("status", [200, 404])
def test_assenza_documentata_imeicheckpro(monkeypatch, status):
    servizio(monkeypatch, {"success": False, "error": {"code": "TAC_NOT_FOUND"}}, status)
    assert I.cerca_tac_online_esito("35135531") == ("assente", None)


def test_profilo_gratuito_richiesta_e_risposta(monkeypatch):
    client = servizio(monkeypatch, {"success": True, "object": {
        "brand": "Samsung", "model": "Galaxy A54 5G", "name": "SM-A546B"}})
    monkeypatch.setenv("TAC_API_PROVIDER", "imeicheckpro")
    assert I.cerca_tac_online_esito("35135531") == ("trovato", ("Samsung", "Galaxy A54 5G"))
    assert client.get.call_args.args == ("https://imeicheckpro.com/api/tac/35135531",)
    assert client.get.call_args.kwargs["headers"]["X-API-Key"] == "test-key"
    client.post.assert_not_called()


def test_profilo_gratuito_non_supera_tre_chiamate_ora(monkeypatch):
    client = servizio(monkeypatch, {"found": False})
    monkeypatch.setenv("TAC_API_PROVIDER", "imeicheckpro")
    for _ in range(5):
        I.cerca_tac_online_esito("35135531")
        I.reset_cache()  # anche dopo il riavvio i contatori restano
    assert client.get.call_count == 3


@pytest.mark.parametrize("tipo", ["errore", "pausa", "quota"])
def test_ricerca_incompleta_non_si_memorizza(monkeypatch, tipo):
    monkeypatch.setattr(I, "fornitori_tac", lambda: [{"nome": "uno"}, {"nome": "due"}])
    monkeypatch.setattr(I, "_interroga_fornitore", lambda f, t:
                        ("errore" if f["nome"] == "due" and tipo == "errore" else "assente", None))
    monkeypatch.setattr(I, "servizio_in_pausa", lambda n: n == "due" and tipo == "pausa")
    monkeypatch.setattr(I, "_prenota_chiamata", lambda f: "quota" if f["nome"] == "due" and tipo == "quota" else "")
    monkeypatch.setattr(I, "_voci_per_tac", lambda t: [])
    assert I.identify("351355310000000") is None
    assert not I.tac_gia_chiesto_invano("35135531")


def test_nuovo_fornitore_invalida_assenza(monkeypatch):
    monkeypatch.setenv("TAC_API_KEY", "test-key")
    I._ricorda_tac_assente("35135531")
    assert I.tac_gia_chiesto_invano("35135531")
    monkeypatch.setenv("TAC_API_KEY_2", "other-test-key")
    monkeypatch.setenv("TAC_API_PROVIDER_2", "imeicheckpro")
    assert not I.tac_gia_chiesto_invano("35135531")


def test_vecchie_assenze_non_attendono_un_mese(isolato):
    isolato[I._META_TAC_ASSENTI] = json.dumps({"35135531": datetime.now(timezone.utc).isoformat()})
    assert not I.tac_gia_chiesto_invano("35135531")


def test_correzione_manuale_prevale_senza_api(monkeypatch):
    client = servizio(monkeypatch, {"model": "telefono diverso"})
    monkeypatch.setattr(I, "tac_inseriti", lambda: {"35135531": ("Samsung", "Galaxy A54 5G")})
    assert I.identify("351355310000000") == ("Samsung", "Galaxy A54 5G")
    client.post.assert_not_called()


def test_copia_completa_offline_cerca_anche_fuori_indice(monkeypatch, tmp_path):
    import gzip

    monkeypatch.setattr(I, "CARTELLA_DATI", str(tmp_path))
    with gzip.open(tmp_path / "tac_completo.csv.gz", "wt", encoding="utf-8") as f:
        f.write('Brand,TAC,SPECS\nSAMSUNG,35135531,"SAMSUNG, SAMSUNG E1195"\n')
    monkeypatch.setattr(I, "_cached_bytes", lambda: None)
    monkeypatch.setattr(I, "_cached_bytes_url", lambda *a, **kw: None)
    monkeypatch.setattr(I, "tac_inseriti", lambda: {})
    monkeypatch.setattr(I, "_indice_curato", lambda: {})
    assert not I._dell_era_android("SAMSUNG, SAMSUNG E1195")
    assert I.identify("351355310000000", solo_locale=True) == ("SAMSUNG", "SAMSUNG, SAMSUNG E1195")


def test_quota_atomica_tra_thread(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("TAC_API_MAX_GIORNO", "3")
    with ThreadPoolExecutor(max_workers=8) as pool:
        risultati = list(pool.map(lambda _: I._prenota_chiamata({"nome": "prova"}), range(20)))
    assert risultati.count("") == 3
