"""Registro aggregato, accesso amministratore e stati IMEI distinti."""
import pytest
from fastapi.testclient import TestClient
from core import config as C, imeicheck, storage, tac_missing
from web import auth_web, imei_status, main
from web.contesto import templates


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    storage.reset_state()
    monkeypatch.setattr(C, 'DB_PATH', str(tmp_path / 'tracker.db'))
    storage.init_db()
    imeicheck.reset_cache()
    yield
    imeicheck.reset_cache()
    storage.reset_state()


def test_registro_non_salva_imei_ne_raddoppia_secondo_tempo(archivio):
    tac_missing.registra('351355315430630', 'tac_non_trovato')
    tac_missing.registra('35135531', 'in_corso')
    tac_missing.registra('35135531', 'servizio_indisponibile', conteggia=False)
    tac_missing.registra('99999999', 'in_corso', conteggia=False)
    righe = tac_missing.elenco()
    assert len(righe) == 1
    assert righe[0]['conteggio'] == 1
    assert righe[0]['motivo'] == 'servizio_indisponibile'
    tac_missing.registra('35135531', 'tac_non_trovato')
    assert tac_missing.elenco()[0]['conteggio'] == 2
    tac_missing.risolto('35135531')
    assert tac_missing.elenco() == []


def test_registro_limita_dimensione_e_scarta_vecchie_voci(archivio):
    with storage.transaction() as conn:
        conn.executemany('INSERT INTO tac_da_verificare VALUES (?,1,?,?,?)',
                         ((f'{i:08}', '2020-01-01', '2020-01-01', 'tac_non_trovato')
                          for i in range(1001)))
    tac_missing.registra('99999999', 'tac_non_trovato')
    assert [r['tac'] for r in tac_missing.elenco()] == ['99999999']
    for i in range(1001):
        tac_missing.registra(f'{i:08}', 'tac_non_trovato')
    assert len(tac_missing.elenco()) == 1000


@pytest.mark.parametrize('dati,esito', [
    ({}, 'tac_non_trovato'),
    ({'cerco_fuori': True}, 'in_corso'),
    ({'servizio_esterno_guasto': 'quota'}, 'servizio_indisponibile'),
    ({'chiesto_invano': True, 'servizio_esterno_guasto': 'errore precedente'}, 'tac_non_trovato'),
    ({'riconosciuto': True, 'modello': 'Galaxy A54'}, 'identificato'),
    ({'riconosciuto': True, 'modello': 'SM-A546B', 'codice': 'SM-A546B'}, 'nome_da_verificare'),
    ({'riconosciuto': True, 'modello': 'Galaxy A54', 'discordi': True}, 'nome_da_verificare'),
    ({'riconosciuto': True, 'modello': 'Galaxy A54', 'discordi': True,
      'voci': [{'fonte': imeicheck.FONTE_UTENTE}]}, 'identificato'),
])
def test_stati_distinti(dati, esito):
    assert imei_status.stato(dati) == esito


def test_scheda_mancante_non_nasconde_identificazione():
    testo = templates.env.get_template('_imei_identita.html').render(
        imei={'riconosciuto': True, 'tac': '35135531', 'descrizione': 'Samsung Galaxy A54'},
        risultato={'scheda': {'trovata': False}})
    assert 'IMEI riconosciuto' in testo
    assert 'Scheda tecnica non disponibile' in testo


def test_guasto_non_viene_presentato_come_assenza():
    testo = templates.env.get_template('_imei_non_risolto.html').render(
        imei={'tac': '35135531', 'stato_identita': 'servizio_indisponibile'})
    assert 'Servizio esterno indisponibile' in testo
    assert 'nessun database' not in testo.lower()
    assert 'data-identita="ignota"' in testo


def test_admin_accesso_csrf_e_correzione(archivio, monkeypatch):
    monkeypatch.setattr(C, 'COOKIE_SECURE', False)
    monkeypatch.setattr(main, '_backup_subito', lambda: None)
    client = TestClient(main.app)
    try:
        monkeypatch.setattr(auth_web, 'utente_da_richiesta', lambda request: None)
        assert client.get('/admin/tac', follow_redirects=False).status_code == 303
        monkeypatch.setattr(auth_web, 'utente_da_richiesta', lambda request: {'admin': False})
        assert client.get('/admin/tac').status_code == 403
        dati = {'tac': '35135531', 'marca': 'Samsung', 'modello': 'Galaxy A54'}
        assert client.post('/admin/tac/correggi', data=dati).status_code == 403
        monkeypatch.setattr(auth_web, 'utente_da_richiesta',
                            lambda request: {'admin': True, 'username': 'admin'})
        tac_missing.registra('35135531', 'tac_non_trovato')
        pagina = client.get('/admin/tac')
        assert pagina.status_code == 200
        assert '35135531' in pagina.text
        assert client.post('/admin/tac/correggi', data=dati).status_code == 403
        dati['csrf'] = client.cookies.get(auth_web.COOKIE_CSRF)
        risposta = client.post('/admin/tac/correggi', data=dati, follow_redirects=False)
        assert risposta.status_code == 303
        assert tac_missing.elenco() == []
        assert imeicheck.tac_inseriti()['35135531'] == ('Samsung', 'Galaxy A54')
    finally:
        client.close()


def test_versione_non_legge_db(monkeypatch):
    monkeypatch.setenv('RENDER_GIT_COMMIT', 'abc123')
    monkeypatch.setattr(storage, 'connect', lambda: pytest.fail('accesso DB nella versione'))
    assert C.dettagli_versione()['commit'] == 'abc123'
    assert C.dettagli_versione()['avvio_utc']


def test_secondo_tempo_risolve_il_nome_anche_nel_registro(archivio, monkeypatch):
    from starlette.requests import Request
    imei = {'tac': '35135531', 'riconosciuto': True, 'modello': 'SM-A546B',
            'codice': 'SM-A546B', 'modello_cercato': 'SM-A546B'}
    imei_status.annota(imei)
    assert tac_missing.elenco()[0]['motivo'] == 'nome_da_verificare'
    monkeypatch.setattr(main, '_esito_imei', lambda domanda: dict(imei))
    monkeypatch.setattr(main, '_esito_ricerca', lambda domanda: {'nome': 'Samsung Galaxy A54'})
    monkeypatch.setattr(main, '_ancora_esito_imei', lambda risultato, imei: risultato)
    monkeypatch.setattr(main, '_rendi', lambda *args, **kwargs: None)
    main.frammento_firmware(Request({'type': 'http', 'headers': []}), q='351355315430630')
    assert tac_missing.elenco() == []
