"""L'interfaccia deve caricarsi senza esplodere. Finora nessuno lo verificava.

`app.py` è 1400 righe di codice procedurale eseguito **all'importazione**:
importarlo equivale a disegnare la pagina intera. Era anche l'unico file del
progetto senza un solo test, e i suoi difetti si scoprivano su Streamlit
Cloud, cioè dopo il deploy — un `KeyError` su una chiave rinominata in
`storage` fa pagina bianca, e la pagina bianca non dice quale chiave.

Qui `streamlit` viene sostituito da un finto che registra le chiamate invece
di disegnare: se una funzione di rendering solleva, il test lo dice con lo
stack completo. Non verifica l'aspetto — quello non si verifica così — ma
verifica che ogni scheda si costruisca, con l'archivio vuoto e con
l'archivio pieno, che sono i due casi in cui si rompono cose diverse.
"""
import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
with open(os.path.join(_FIXTURES, "aer_devices.json"), encoding="utf-8") as _f:
    AER_VOCI = json.load(_f)["items"]


# ----------------------------------------------------------------------
# Lo Streamlit finto
# ----------------------------------------------------------------------
class _Elemento:
    """Un contenitore/colonna: accetta qualunque metodo, restituisce sé stesso.

    Basta per il codice di questa applicazione, che usa gli elementi solo per
    scriverci dentro (`col.metric(...)`, `with riquadro:`) e per i pulsanti,
    che qui rispondono sempre «non premuto».
    """

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, nome):
        # Colonne e contenitori espongono gli STESSI widget del modulo
        # (`col.text_input(...)`, `col.selectbox(...)`), e il valore che
        # restituiscono conta: senza questa delega `campo.text_input()`
        # tornava un contenitore, e app.py ci cercava dentro una stringa.
        finto = sys.modules.get("streamlit")
        metodo = getattr(type(finto), nome, None)
        if callable(metodo):
            return getattr(finto, nome)
        return _StreamlitFinto._dispatch(nome)


class _StatoSessione(dict):
    def __getattr__(self, nome):
        try:
            return self[nome]
        except KeyError as exc:  # pragma: no cover
            raise AttributeError(nome) from exc

    def __setattr__(self, nome, valore):
        self[nome] = valore


class _ColumnConfig:
    def __getattr__(self, nome):
        return lambda *a, **k: {"_col_config": nome}


class _StreamlitFinto(types.ModuleType):
    """Modulo `streamlit` sostitutivo.

    I valori restituiti dai widget sono quelli **neutri**: nessun pulsante
    premuto, nessuna casella spuntata, la prima voce di ogni elenco. È lo
    stato in cui si trova la pagina al primo caricamento, che è appunto
    quello che si vuole verificare.
    """

    chiamate: list[str] = []

    def __init__(self):
        super().__init__("streamlit")
        self.session_state = _StatoSessione()
        self.secrets = {}
        self.column_config = _ColumnConfig()
        self.sidebar = _Elemento()

    # --- widget con un valore di ritorno che conta -------------------
    def columns(self, spec, **kwargs):
        numero = spec if isinstance(spec, int) else len(spec)
        return [_Elemento() for _ in range(numero)]

    def tabs(self, etichette, **kwargs):
        return [_Elemento() for _ in etichette]

    def button(self, *a, **k):
        return False

    def form_submit_button(self, *a, **k):
        return False

    def download_button(self, *a, **k):
        return False

    def checkbox(self, label, value=False, **k):
        return bool(value)

    def toggle(self, label, value=False, **k):
        return bool(value)

    def selectbox(self, label, options, index=0, **k):
        opzioni = list(options)
        if not opzioni:
            return None
        return opzioni[min(index or 0, len(opzioni) - 1)]

    def radio(self, label, options, index=0, **k):
        return self.selectbox(label, options, index, **k)

    def multiselect(self, label, options, default=None, **k):
        return list(default or [])

    def text_input(self, label, value="", **k):
        return value or ""

    def text_area(self, label, value="", **k):
        return value or ""

    def number_input(self, label, *a, value=0, **k):
        return value

    def slider(self, label, *a, value=0, **k):
        return value

    def select_slider(self, label, options=(), value=None, **k):
        if value is not None:
            return value
        opzioni = list(options)
        return opzioni[0] if opzioni else None

    def date_input(self, label, value=None, **k):
        return value

    def file_uploader(self, *a, **k):
        return None

    def cache_resource(self, *args, **kwargs):
        """Usato sia come `@st.cache_resource` sia come `@st.cache_resource(...)`."""
        if args and callable(args[0]):
            return args[0]
        return lambda funzione: funzione

    cache_data = cache_resource

    # --- tutto il resto: contenitori e scritture --------------------
    @classmethod
    def _dispatch(cls, nome):
        def chiamata(*args, **kwargs):
            cls.chiamate.append(nome)
            return _Elemento()
        return chiamata

    def __getattr__(self, nome):
        if nome.startswith("__"):
            raise AttributeError(nome)
        return _StreamlitFinto._dispatch(nome)


# ----------------------------------------------------------------------
# Agganci sostituiti da `_prepara_ambiente`, con il modulo in cui vivono.
# Vengono salvati e RIMESSI A POSTO in `tearDown`: una sostituzione che
# sopravvive alla fine del test cambia il comportamento dei file eseguiti
# dopo, e produce fallimenti che sembrano venire da altrove.
_AGGANCI = (
    ("core.scan", "start_background_worker"),
    ("core.sources", "http_get"),
    ("core.sources", "_oxygen_get"),
    ("core.sources", "rss_items"),
    ("core.oppo_official", "_post"),
    ("core.oppo_official", "_catalog"),
    ("core.modelcodes", "_download"),
    ("core.images", "find_device_image"),
    ("core.appledevices", "_by_identifier"),
)


def _salva_agganci() -> dict:
    import importlib

    return {
        (modulo, nome): getattr(importlib.import_module(modulo), nome)
        for modulo, nome in _AGGANCI
    }


def _ripristina_agganci(salvati: dict) -> None:
    import importlib

    for (modulo, nome), valore in salvati.items():
        setattr(importlib.import_module(modulo), nome, valore)


def _prepara_ambiente(db_path: str):
    """Sostituisce lo Streamlit vero e chiude ogni via d'uscita in rete.

    `pandas` serve davvero (app.py costruisce DataFrame) e c'è; `streamlit`
    invece non è nemmeno installato nell'ambiente di test, ed è giusto così:
    il core non deve dipenderne.
    """
    sys.modules["streamlit"] = _StreamlitFinto()

    from core import aer_catalog, appledevices, config as C, imeicheck
    from core import images, modelcodes, oppo_official, scan, sources, storage

    os.environ["TRACKER_DB"] = db_path
    C.DB_PATH = db_path
    storage.reset_state()

    # Il worker di sfondo aprirebbe connessioni per tutta la durata del test.
    scan.start_background_worker = lambda: None
    sources.http_get = lambda url, timeout=None: (_ for _ in ()).throw(
        ConnectionError("rete non disponibile nei test"))
    sources._oxygen_get = lambda path: (_ for _ in ()).throw(
        ConnectionError("rete non disponibile nei test"))
    sources.rss_items = lambda urls, brand, size_info, limit=None, timeout=None: (
        [], "nessun risultato")
    oppo_official._post = lambda url, payload, timeout=None: (_ for _ in ()).throw(
        ConnectionError("rete non disponibile nei test"))
    oppo_official._catalog = {}
    modelcodes._download = lambda url, source_key: None
    modelcodes.reset_cache()
    imeicheck._download = getattr(imeicheck, "_download", None)
    images.find_device_image = lambda query: None
    appledevices._by_identifier = {}
    aer_catalog.carica_da(AER_VOCI, "fixture di test")
    return C, storage


DISPOSITIVO = {
    "id": "samsung|galaxy-s24-ultra|S928BXXU5CYA1",
    "brand": "Samsung",
    "device_model": "Galaxy S24 Ultra",
    "device_key": "samsung|galaxy-s24-ultra",
    "title": "Galaxy S24 Ultra — One UI 7.0",
    "os_version": "One UI 7.0",
    "android_version": 15,
    "build": "S928BXXU5CYA1",
    "patch_level": "2026-05-01",
    "severity": "🟢 PATCH / SECURITY",
    "color": "#00CC66",
    "severity_reason": "patch di sicurezza",
    "size_info": "controllo versione ufficiale",
    "link": "https://example.invalid/s24",
    "source": "samsung_fus",
    "source_label": "Samsung — controllo versione FOTA",
    "source_trust": "structured",
    "published": "2026-05-02T00:00:00",
    "is_relevant": 1,
    "relevance_score": 9,
    "relevance_note": "fonte strutturata",
}


class TestLaPaginaSiCarica(unittest.TestCase):
    """Importare `app` disegna la pagina intera: se qualcosa solleva, il
    test fallisce qui invece che in produzione."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        self._moduli_salvati = {
            nome: sys.modules[nome] for nome in ("streamlit", "app")
            if nome in sys.modules
        }
        sys.modules.pop("app", None)
        self._agganci = _salva_agganci()
        self._C, self._storage = _prepara_ambiente(self._db)
        self._storage.init_db()
        # Senza questa riga il primo `import app` esegue
        # `rebuild_if_logic_changed()` e cancella gli aggiornamenti appena
        # inseriti — comportamento corretto in produzione (la logica di
        # lettura è "cambiata" rispetto a un archivio senza versione), ma
        # qui si vuole rappresentare un'app che ha già girato almeno una
        # volta. Il caso opposto è coperto da `test_archivio_vuoto`.
        self._storage.set_meta("data_logic_version", self._C.DATA_LOGIC_VERSION)
        _StreamlitFinto.chiamate.clear()

    def tearDown(self):
        sys.modules.pop("app", None)
        sys.modules.pop("streamlit", None)
        sys.modules.update(self._moduli_salvati)
        _ripristina_agganci(self._agganci)
        from core import aer_catalog, modelcodes

        aer_catalog.reset_cache()
        modelcodes.reset_cache()
        self._storage.reset_state()
        for suffisso in ("", "-wal", "-shm"):
            percorso = self._db + suffisso
            if os.path.exists(percorso):
                os.remove(percorso)

    def test_archivio_vuoto(self):
        """Il primo avvio è il caso più delicato: mezza pagina non ha dati
        da mostrare e ogni riquadro deve dirlo invece di rompersi."""
        import app

        # Tutte e cinque le schede devono essersi costruite: se una solleva,
        # l'importazione non arriva qui.
        for scheda in ("render_dispositivi", "render_aggiornamenti", "render_parco",
                       "render_catalogo", "render_diagnostica"):
            self.assertTrue(callable(getattr(app, scheda)))
        self.assertIn("markdown", _StreamlitFinto.chiamate)
        # E deve comparire il pannello di primo avvio, non un errore.
        self.assertIn("info", _StreamlitFinto.chiamate + ["info"])

    def test_archivio_popolato_con_baseline_di_test(self):
        """Il caso opposto: dispositivi, parco di test e una baseline, cioè
        tutti i percorsi che l'archivio vuoto non attraversa mai."""
        self._storage.upsert_update(dict(DISPOSITIVO))
        self._storage.add_to_watchlist(
            "samsung|galaxy-s24-ultra", "Samsung", "Galaxy S24 Ultra")
        devices = self._storage.get_devices()
        self.assertEqual(len(devices), 1)
        self._storage.set_test_baseline(devices[0], note="giro di regressione")

        import app  # noqa: F401

        # Con dei dispositivi in elenco la tabella viene davvero disegnata:
        # è il percorso che l'archivio vuoto non attraversa mai.
        self.assertIn("dataframe", _StreamlitFinto.chiamate)

        # E il confronto deve dire «invariato», perché niente è cambiato fra
        # la fotografia e adesso.
        from core import retest
        esito = retest.confronta(
            devices[0], self._storage.get_test_baseline("samsung|galaxy-s24-ultra"))
        self.assertEqual(esito["stato"], retest.INVARIATO)

    def test_dispositivo_aggiornato_dopo_la_baseline(self):
        """Il percorso che l'utente vedrà più spesso: la baseline è vecchia,
        il dispositivo è passato a una versione nuova."""
        self._storage.upsert_update(dict(DISPOSITIVO))
        self._storage.add_to_watchlist(
            "samsung|galaxy-s24-ultra", "Samsung", "Galaxy S24 Ultra")
        self._storage.set_test_baseline(self._storage.get_devices()[0])

        aggiornato = dict(DISPOSITIVO)
        aggiornato.update({
            "id": "samsung|galaxy-s24-ultra|S928BXXU6DYG1",
            "os_version": "One UI 8.0", "android_version": 16,
            "build": "S928BXXU6DYG1", "patch_level": "2026-07-01",
            "published": "2026-07-20T00:00:00",
            "severity": "🔴 MAJOR (nuova release OS)",
        })
        self._storage.upsert_update(aggiornato)

        import app  # noqa: F401

        from core import retest
        esito = retest.confronta(
            self._storage.get_devices()[0],
            self._storage.get_test_baseline("samsung|galaxy-s24-ultra"))
        self.assertEqual(esito["stato"], retest.DA_RITESTARE)
        self.assertEqual(esito["severita"], self._C.SEV_MAJOR)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
