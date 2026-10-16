"""Le donazioni libere di Page Brawl via Ko-fi (16/10/2026, vedi web/donazioni.py)."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from core import config as C, storage
from web import auth_web, main

ADMIN = {'admin': True, 'username': 'admin'}
TOKEN = 'segreto-di-prova'


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    storage.reset_state()
    monkeypatch.setattr(C, 'DB_PATH', str(tmp_path / 'tracker.db'))
    monkeypatch.setattr(C, 'COOKIE_SECURE', False)
    monkeypatch.setattr(C, 'KOFI_VERIFICATION_TOKEN', TOKEN)
    monkeypatch.setattr(main, '_backup_subito', lambda: None)
    storage.init_db()
    client = TestClient(main.app)
    yield client
    client.close()
    storage.reset_state()


def _come(monkeypatch, utente):
    monkeypatch.setattr(auth_web, 'utente_da_richiesta', lambda request: utente)


def _donazione(**altro):
    dati = {'verification_token': TOKEN, 'message_id': 'm-1', 'timestamp': '2026-10-16T10:00:00Z',
            'type': 'Donation', 'is_public': True, 'from_name': 'Gianni', 'message': 'Un personaggio pirata!',
            'amount': '3.00', 'url': 'https://ko-fi.com/Home/CoffeeShop?txid=x', 'email': 'gianni@example.com',
            'currency': 'EUR', 'kofi_transaction_id': 'tx-1'}
    dati.update(altro)
    return {'data': json.dumps(dati)}


def test_il_webhook_salva_la_donazione_col_messaggio_e_non_l_email(archivio):
    risposta = archivio.post('/api/kofi', data=_donazione())
    assert risposta.status_code == 200 and risposta.json()['salvata'] is True
    [voce] = storage.donazioni()
    assert (voce['nome'], voce['messaggio'], voce['importo'], voce['valuta']) == ('Gianni', 'Un personaggio pirata!', '3.00', 'EUR')
    assert voce['letta'] == 0 and voce['pubblica'] == 1
    assert 'gianni@example.com' not in json.dumps(voce)


def test_ko_fi_che_ripete_il_webhook_non_conta_la_donazione_due_volte(archivio):
    archivio.post('/api/kofi', data=_donazione())
    seconda = archivio.post('/api/kofi', data=_donazione())
    assert seconda.status_code == 200 and seconda.json()['salvata'] is False
    assert len(storage.donazioni()) == 1


def test_token_sbagliato_o_assente_rifiutato(archivio, monkeypatch):
    assert archivio.post('/api/kofi', data=_donazione(verification_token='altro')).status_code == 403
    assert archivio.post('/api/kofi', data={'data': 'non json'}).status_code == 400
    assert archivio.post('/api/kofi', data={}).status_code == 400
    # Senza token configurato sul server non si accetta niente, nemmeno con un token qualsiasi.
    monkeypatch.setattr(C, 'KOFI_VERIFICATION_TOKEN', '')
    assert archivio.post('/api/kofi', data=_donazione(verification_token='')).status_code == 503
    assert storage.donazioni() == []


def test_eventi_sconosciuti_ok_ma_non_salvati_e_testi_ripuliti(archivio):
    assert archivio.post('/api/kofi', data=_donazione(type='Altro', kofi_transaction_id='tx-9')).json()['salvata'] is False
    lungo = 'a' * 5000 + '\x07'
    archivio.post('/api/kofi', data=_donazione(kofi_transaction_id='tx-2', message=lungo, from_name='  Ugo \n  Rossi '))
    [voce] = storage.donazioni()
    assert voce['nome'] == 'Ugo Rossi' and len(voce['messaggio']) == 1000 and '\x07' not in voce['messaggio']


def test_la_pagina_delle_donazioni_e_solo_per_gli_amministratori(archivio, monkeypatch):
    archivio.post('/api/kofi', data=_donazione(message='<script>alert(1)</script> un drago'))
    _come(monkeypatch, None)
    assert archivio.get('/admin/donazioni', follow_redirects=False).headers['location'].startswith('/login')
    _come(monkeypatch, {'admin': False})
    assert archivio.get('/admin/donazioni').status_code == 403
    _come(monkeypatch, ADMIN)
    pagina = archivio.get('/admin/donazioni')
    assert pagina.status_code == 200 and 'un drago' in pagina.text and 'Gianni' in pagina.text
    assert '<script>alert(1)</script>' not in pagina.text            # (il messaggio è di chiunque: va escapato)
    [voce] = storage.donazioni()
    csrf = {'csrf': archivio.cookies.get(auth_web.COOKIE_CSRF)}
    assert archivio.post(f"/admin/donazioni/{voce['id']}/letta").status_code == 403    # senza token del modulo
    archivio.post(f"/admin/donazioni/{voce['id']}/letta", data=csrf, follow_redirects=False)
    assert storage.donazioni()[0]['letta'] == 1


def test_l_estensione_ha_il_tasto_della_donazione_solo_con_l_indirizzo_ko_fi(monkeypatch):
    from estensione import costruisci
    senza = costruisci.file_attesi('store')['prepara.js']
    assert 'data-dona' not in senza
    monkeypatch.setattr(costruisci, 'premium', lambda: {'premium': False, 'urlAcquisto': '', 'sbloccoGratis': False,
                                                         'urlDonazione': 'https://ko-fi.com/pagebrawl'})
    con = costruisci.file_attesi('store')['prepara.js']
    assert 'data-dona' in con and 'https://ko-fi.com/pagebrawl' in con and 'Sostieni Page Brawl' in con
    assert re.search(r'noopener', con)
