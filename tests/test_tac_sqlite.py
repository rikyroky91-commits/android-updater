"""Copertura, riuso e consumo dell'indice TAC su disco."""
import tracemalloc
from contextlib import closing

import pytest

from core import config as C, imeicheck, storage
from core.tac_index import TacIndex


def test_catalogo_grande_indicizzato_senza_dizionario(tmp_path):
    indice = TacIndex(tmp_path / 'catalogo.sqlite3')
    tracemalloc.start()
    try:
        indice.rebuild(((f'{i:08}', f'fonte\x1fSamsung\x1fModello {i}')
                        for i in range(200_000)), lambda: 'v1')
        _, picco = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert picco < 8 * 1024 * 1024, 'Il catalogo è stato materializzato in RAM'
    assert len(indice) == 200_000
    assert indice['00199999'].endswith('Modello 199999')
    with closing(indice.connect()) as conn:
        piano = conn.execute('EXPLAIN QUERY PLAN SELECT cell FROM catalog WHERE tac=?',
                             ('00199999',)).fetchall()
    assert 'PRIMARY KEY' in str(piano)


def test_importazione_interrotta_conserva_vecchio_catalogo(tmp_path):
    indice = TacIndex(tmp_path / 'catalogo.sqlite3')
    indice.rebuild([('11111111', 'vecchio')], lambda: 'v1')
    def interrotte():
        yield '22222222', 'parziale'
        raise RuntimeError('download interrotto')
    with pytest.raises(RuntimeError):
        indice.rebuild(interrotte(), lambda: 'v2')
    assert indice.current('v1')
    assert indice['11111111'] == 'vecchio'
    assert '22222222' not in indice


def test_cache_corrotto_ricostruibile(tmp_path):
    path = tmp_path / 'catalogo.sqlite3'
    path.write_bytes(b'questo non e SQLite')
    indice = TacIndex(path)
    assert not indice.current('v1')
    indice.rebuild([('11111111', 'nuovo')], lambda: 'v1')
    assert indice.current('v1')
    assert indice['11111111'] == 'nuovo'


@pytest.fixture
def catalogo(tmp_path, monkeypatch):
    storage.reset_state()
    monkeypatch.setattr(C, 'DB_PATH', str(tmp_path / 'tracker.db'))
    storage.init_db()
    imeicheck.reset_cache()
    for nome in ('_indice_curato', 'tac_inseriti', 'tac_esterni'):
        if nome != 'tac_inseriti':
            monkeypatch.setattr(imeicheck, nome, lambda: {})
    monkeypatch.setattr(imeicheck, '_voci_principali',
                        lambda: iter([('11111111', 'Samsung', 'Galaxy senza anno')]))
    monkeypatch.setattr(imeicheck, '_voci_imeidb', lambda: iter(()))
    monkeypatch.setattr(imeicheck, '_voci_storiche', lambda: iter(()))
    yield
    imeicheck.reset_cache()
    storage.reset_state()


def test_riuso_disco_dopo_rilascio_ram(catalogo, monkeypatch):
    assert imeicheck._voci_per_tac('11111111')[0][2] == 'Galaxy senza anno'
    imeicheck.libera_indice()
    def vietato():
        pytest.fail('Riletto il catalogo completo dopo la sola liberazione RAM')
    monkeypatch.setattr(imeicheck, '_voci_principali', vietato)
    assert imeicheck._voci_per_tac('11111111')[0][2] == 'Galaxy senza anno'
    assert imeicheck._voci_per_tac('99999999') == []
    assert imeicheck._CACHE_SECONDE_LETTURE == {}


def test_correzione_invalida_indice_e_prevale(catalogo):
    imeicheck._voci_per_tac('11111111')
    assert imeicheck.aggiungi_tac('11111111', 'Samsung', 'Galaxy verificato')
    # Forza il catalogo completo, oltre al percorso rapido delle correzioni.
    imeicheck._voci_per_tac('99999999')
    assert imeicheck._voci_per_tac('11111111')[0] == (
        imeicheck.FONTE_UTENTE, 'Samsung', 'Galaxy verificato')


def test_duplicati_mantengono_ultima_riga_della_fonte(tmp_path):
    indice = TacIndex(tmp_path / 'catalogo.sqlite3')
    indice.rebuild([('11111111', 'fonte\x1fSamsung\x1fPrima'),
                    ('11111111', 'fonte\x1fSamsung\x1fUltima')], lambda: 'v1')
    assert imeicheck._voci_dalla_cella(indice['11111111']) == [('fonte', 'Samsung', 'Ultima')]


def test_refresh_segue_scadenza_reale_del_download(catalogo, monkeypatch):
    from datetime import datetime, timezone, timedelta
    class Orologio(datetime):
        adesso = datetime(2026, 9, 1, tzinfo=timezone.utc)
        @classmethod
        def now(cls, tz=None):
            return cls.adesso
    monkeypatch.setattr(imeicheck, 'datetime', Orologio)
    for chiave in (imeicheck._META_FETCHED_KEY, imeicheck._META_IMEIDB_FETCHED,
                   imeicheck._META_FALLBACK_FETCHED):
        storage.set_meta(chiave, (Orologio.adesso - timedelta(days=13)).isoformat())
    letture = []
    def righe():
        letture.append(1)
        yield '11111111', 'Samsung', 'Modello'
    monkeypatch.setattr(imeicheck, '_voci_principali', righe)
    imeicheck._voci_per_tac('11111111')
    Orologio.adesso += timedelta(hours=1)
    imeicheck.libera_indice()
    imeicheck._voci_per_tac('11111111')
    assert len(letture) == 1
    Orologio.adesso += timedelta(days=2)
    imeicheck.libera_indice()
    imeicheck._voci_per_tac('11111111')
    assert len(letture) == 2
