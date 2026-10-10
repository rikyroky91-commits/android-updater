"""Correzioni proposte da chi non ha un account (10/10/2026).

Prima `/tac/salva` e `/modello/correggi` applicavano la correzione da
chiunque, con la precedenza su ogni fonte. Ora chi non ha fatto l'accesso
lascia una proposta, e un amministratore la approva o la scarta.
"""
import pytest
from fastapi.testclient import TestClient

from core import config as C, imeicheck, proposte, storage
from web import auth_web, main

ADMIN = {'admin': True, 'username': 'admin'}


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    storage.reset_state()
    monkeypatch.setattr(C, 'DB_PATH', str(tmp_path / 'tracker.db'))
    monkeypatch.setattr(C, 'COOKIE_SECURE', False)
    monkeypatch.setattr(main, '_backup_subito', lambda: None)
    storage.init_db()
    imeicheck.reset_cache()
    client = TestClient(main.app)
    yield client
    client.close()
    imeicheck.reset_cache()
    storage.reset_state()


def _come(monkeypatch, utente):
    monkeypatch.setattr(auth_web, 'utente_da_richiesta', lambda request: utente)


def test_senza_account_il_tac_non_cambia_e_resta_una_proposta(archivio, monkeypatch):
    _come(monkeypatch, None)
    risposta = archivio.post('/tac/salva', data={'tac': '35135531', 'imei': '351355315430630',
                                                  'incollato': 'Samsung Galaxy A54'},
                             follow_redirects=False)
    assert risposta.headers['location'] == '/?q=351355315430630&proposta=1'
    assert '35135531' not in imeicheck.tac_inseriti()
    [voce] = proposte.elenco()
    assert (voce['tipo'], voce['chiave'], voce['marca'], voce['valore']) == \
        ('tac', '35135531', 'Samsung', 'Galaxy A54')
    # La stessa proposta di nuovo non fa una riga in più, la conta.
    archivio.post('/tac/salva', data={'tac': '35135531', 'marca': 'Samsung',
                                      'modello': 'Galaxy A54'}, follow_redirects=False)
    assert [v['conteggio'] for v in proposte.elenco()] == [2]


def test_senza_account_il_nome_non_cambia(archivio, monkeypatch):
    _come(monkeypatch, None)
    risposta = archivio.post('/modello/correggi', data={'codice': 'sm-a546b', 'nome': 'Finto',
                                                         'query': 'SM-A546B'},
                             follow_redirects=False)
    assert risposta.headers['location'] == '/?q=SM-A546B&proposta=1'
    assert storage.get_nome_modello('SM-A546B') is None
    assert [(v['tipo'], v['chiave'], v['valore']) for v in proposte.elenco()] == \
        [('nome', 'SM-A546B', 'Finto')]


def test_una_proposta_non_valida_lo_dice(archivio, monkeypatch):
    _come(monkeypatch, None)
    risposta = archivio.post('/tac/salva', data={'tac': '351', 'marca': 'X', 'modello': 'Y'},
                             follow_redirects=False)
    assert risposta.headers['location'].endswith('proposta=0')
    assert proposte.elenco() == []


def test_con_account_si_salva_subito_e_le_proposte_spariscono(archivio, monkeypatch):
    proposte.registra('tac', '35135531', 'Samsung', 'Galaxy A55')
    _come(monkeypatch, {'username': 'collaudo'})
    risposta = archivio.post('/tac/salva', data={'tac': '35135531', 'marca': 'Samsung',
                                                  'modello': 'Galaxy A54'},
                             follow_redirects=False)
    assert risposta.headers['location'].endswith('saved=1')
    assert imeicheck.tac_inseriti()['35135531'] == ('Samsung', 'Galaxy A54')
    assert proposte.elenco() == []


def test_l_amministratore_approva_o_scarta(archivio, monkeypatch):
    proposte.registra('tac', '35135531', 'Samsung', 'Galaxy A54')
    proposte.registra('tac', '35135531', 'Samsung', 'Galaxy A55')
    proposte.registra('nome', 'SM-A546B', '', 'Galaxy A54 5G')
    per_id = {(v['chiave'], v['valore']): v['id'] for v in proposte.elenco()}

    _come(monkeypatch, None)
    assert archivio.post(f"/admin/proposte/{per_id[('35135531', 'Galaxy A54')]}/approva",
                         follow_redirects=False).headers['location'].startswith('/login')
    _come(monkeypatch, {'admin': False})
    assert archivio.post(f"/admin/proposte/{per_id[('35135531', 'Galaxy A54')]}/approva"
                         ).status_code == 403

    _come(monkeypatch, ADMIN)
    pagina = archivio.get('/admin/tac')
    assert 'Galaxy A55' in pagina.text and 'Galaxy A54 5G' in pagina.text
    csrf = {'csrf': archivio.cookies.get(auth_web.COOKIE_CSRF)}
    # Senza token il modulo non passa.
    assert archivio.post(f"/admin/proposte/{per_id[('35135531', 'Galaxy A54')]}/approva"
                         ).status_code == 403

    archivio.post(f"/admin/proposte/{per_id[('35135531', 'Galaxy A54')]}/approva",
                  data=csrf, follow_redirects=False)
    assert imeicheck.tac_inseriti()['35135531'] == ('Samsung', 'Galaxy A54')
    # L'altra proposta per lo stesso TAC rispondeva alla stessa domanda.
    assert [v['chiave'] for v in proposte.elenco()] == ['SM-A546B']

    archivio.post(f"/admin/proposte/{per_id[('SM-A546B', 'Galaxy A54 5G')]}/scarta",
                  data=csrf, follow_redirects=False)
    assert proposte.elenco() == []
    assert storage.get_nome_modello('SM-A546B') is None


def test_la_coda_ha_un_tetto(archivio, monkeypatch):
    monkeypatch.setattr(proposte, 'MASSIMO', 3)
    for n in range(5):
        proposte.registra('nome', f'CODICE{n}', '', 'Nome')
    assert len(proposte.elenco()) == 3
