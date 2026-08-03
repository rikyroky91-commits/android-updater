"""Nessun test deve toccare la rete — verificato, non promesso.

È l'errore n. 10 del documento di passaggio consegne, e si era ripresentato:
`test_brand_senza_fonte_dedicata_degrada_pulitamente` interrogava davvero il
catalogo Android Enterprise Recommended, perché `core/aer_catalog.py` ha un
client HTTP proprio e non passa da `sources.http_get`, che il test sostituiva
diligentemente. Risultato: il test passava sulla macchina di chi l'aveva
scritto e falliva in un ambiente senza rete, cioè diceva il contrario di
quello che affermava di verificare.

Il rimedio non è ricordarsene. Qui si **blocca il socket** e si guarda cosa
succede: se un percorso di ricerca prova a uscire, il test lo dice, con
l'indirizzo che stava per contattare. Un elenco a mano dei punti di accesso
alla rete invecchierebbe alla prima fonte aggiunta; questo no.
"""
import json
import os
import socket
import sys
import tempfile
import unittest
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import aer_catalog, config as C, modelcodes, oppo_official  # noqa: E402
from core import scan, sources, storage  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
with open(os.path.join(_FIXTURES, "aer_devices.json"), encoding="utf-8") as _f:
    AER_VOCI = json.load(_f)["items"]


@contextmanager
def rete_bloccata():
    """Ogni tentativo di aprire una connessione viene annotato e respinto.

    Si intercettano entrambe le porte d'ingresso: `socket.create_connection`
    (la via di `requests`/`urllib3`) e `socket.socket.connect` (quella di
    `urllib.request` e di chiunque scenda più in basso).
    """
    tentativi: list[str] = []
    vero_create = socket.create_connection
    vero_connect = socket.socket.connect

    def create_connection(address, *args, **kwargs):
        tentativi.append(f"{address[0]}:{address[1]}")
        raise OSError("rete bloccata dal test")

    def connect(self, address, *args, **kwargs):
        try:
            tentativi.append(f"{address[0]}:{address[1]}")
        except Exception:  # socket unix o indirizzo non standard
            tentativi.append(str(address))
        raise OSError("rete bloccata dal test")

    socket.create_connection = create_connection
    socket.socket.connect = connect
    try:
        yield tentativi
    finally:
        socket.create_connection = vero_create
        socket.socket.connect = vero_connect


class TestLaRicercaNonEsceInRete(unittest.TestCase):
    """Con tutti gli agganci sostituiti, `search_model` non deve aprire
    nemmeno una connessione. Se ne apre una, vuol dire che esiste un
    percorso che i test non controllano — ed è lì che si annidano i
    fallimenti a intermittenza."""

    MOBILEMODELS = (
        "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
        "SM-S928B,mob,samsung,Samsung,,,Galaxy S24 Ultra,\n"
    )

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

        self._orig_download = modelcodes._download
        self._orig_http_get = sources.http_get
        self._orig_rss_items = sources.rss_items
        self._orig_oxygen_get = sources._oxygen_get
        self._orig_oppo_post = oppo_official._post
        self._orig_oppo_catalog = oppo_official._catalog

        modelcodes.reset_cache()
        modelcodes._download = lambda url, source_key: (
            self.MOBILEMODELS.encode("utf-8-sig")
            if url == modelcodes.MOBILEMODELS_URL else None
        )

        def niente_http(url, timeout=None):
            raise ConnectionError("fonte non prevista in questo test")

        sources.http_get = niente_http
        sources._oxygen_get = lambda path: (_ for _ in ()).throw(
            ConnectionError("fonte non prevista in questo test"))
        sources.rss_items = lambda urls, brand, size_info, limit=None, timeout=None: (
            [], "nessun risultato")
        # L'archivio Oppo ha anche lui un client HTTP proprio (`urllib`), come
        # il catalogo AER: è il secondo percorso che sfuggiva agli agganci.
        oppo_official._post = lambda url, payload, timeout=None: (
            (_ for _ in ()).throw(ConnectionError("fonte non prevista in questo test")))
        oppo_official._catalog = {}
        aer_catalog.carica_da(AER_VOCI, "fixture di test")

    def tearDown(self):
        modelcodes._download = self._orig_download
        sources.http_get = self._orig_http_get
        sources.rss_items = self._orig_rss_items
        sources._oxygen_get = self._orig_oxygen_get
        oppo_official._post = self._orig_oppo_post
        oppo_official._catalog = self._orig_oppo_catalog
        modelcodes.reset_cache()
        aer_catalog.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_search_model_non_apre_nessuna_connessione(self):
        with rete_bloccata() as tentativi:
            for query in ("OnePlus 12", "Galaxy S24 Ultra", "Modello Inesistente XYZ"):
                scan.search_model(query)
        self.assertEqual(
            tentativi, [],
            "un percorso di ricerca è uscito in rete nonostante gli agganci "
            f"sostituiti: {tentativi}. Va aggiunto un aggancio per quella "
            "fonte, altrimenti i test che la attraversano dipendono da cosa "
            "risponde un server di terzi.",
        )


class TestScansioneSenzaRete(unittest.TestCase):
    """La scansione periodica gira su Streamlit Cloud e in GitHub Actions,
    dove una fonte irraggiungibile è la normalità, non l'eccezione.

    Il requisito è duplice e nessuno dei due lati è ovvio: la scansione deve
    **arrivare in fondo** anche con la rete completamente assente, e ogni
    fonte caduta deve lasciare un **errore leggibile** in Diagnostica. Una
    scansione che si interrompe a metà lascia l'archivio a uno stato
    indefinito; una che finisce in silenzio fa credere che non ci sia nulla
    da aggiornare.
    """

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        aer_catalog.reset_cache()
        oppo_official.reset_cache()
        modelcodes.reset_cache()

    def tearDown(self):
        storage.reset_state()
        aer_catalog.reset_cache()
        oppo_official.reset_cache()
        modelcodes.reset_cache()
        for suffisso in ("", "-wal", "-shm"):
            percorso = self._db + suffisso
            if os.path.exists(percorso):
                os.remove(percorso)

    def test_la_scansione_arriva_in_fondo_e_registra_i_guasti(self):
        with rete_bloccata():
            esito = scan.run_scan(auto_notify=False)

        self.assertFalse(esito.get("skipped"))
        self.assertIsNone(esito.get("error"),
                          "una fonte caduta non deve far esplodere la scansione")

        stato = storage.get_source_status()
        self.assertTrue(stato, "nessuna fonte registrata: la scansione non è partita")
        self.assertTrue(
            all(not riga["ok"] for riga in stato),
            "senza rete nessuna fonte può essere OK: se lo è, sta leggendo "
            "una cache invece della fonte, e lo sta dichiarando come dato fresco",
        )
        self.assertTrue(
            all(riga["last_error"] for riga in stato),
            "un guasto deve essere rumoroso: senza messaggio, in Diagnostica "
            "compare una fonte rossa senza motivo",
        )


class TestGuastoDiReteNonPropagaEccezioni(unittest.TestCase):
    """Con la rete davvero assente — nessun aggancio sostituito — le fonti
    devono degradare a un errore leggibile, non a un'eccezione."""

    def test_catalogo_aer_senza_rete(self):
        aer_catalog.reset_cache()
        try:
            with rete_bloccata():
                self.assertEqual(aer_catalog.carica(), [])
            self.assertIn("non raggiungibile", aer_catalog.status())
        finally:
            aer_catalog.reset_cache()

    def test_fonti_senza_rete_restituiscono_un_errore_non_lo_sollevano(self):
        with rete_bloccata():
            for fonte in (sources.fetch_aer_catalog, sources.fetch_honor_aer,
                          sources.fetch_realme_aer, sources.fetch_vivo_aer):
                with self.subTest(fonte=fonte.__name__):
                    items, errore = fonte()
                    self.assertEqual(items, [])
                    self.assertTrue(errore, "un guasto deve essere rumoroso, non vuoto")
        aer_catalog.reset_cache()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
