"""Test del sito.

Le pagine si disegnano davvero, con un archivio vero (piccolo, costruito
qui) e senza toccare la rete: `scan.search_model` e il catalogo specifiche
sono sostituiti. Quello che si verifica non è «la pagina ha risposto 200»
— quello lo fa anche una pagina bianca — ma **cosa c'è scritto dentro**.

È la lezione più cara di questo progetto, pagata due volte
sull'interfaccia Streamlit: una regola morta e un foglio di stile mangiato
dal sanificatore non davano errore, davano una pagina che sembrava a posto
finché non la si guardava.
"""
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AVVIA_WORKER"] = "0"

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _prepara():
    """Un archivio vero, in un file temporaneo, con due dispositivi."""
    cartella = tempfile.mkdtemp(prefix="sito-")
    os.environ["DB_PATH"] = os.path.join(cartella, "test.db")

    from core import config as C

    C.DB_PATH = os.environ["DB_PATH"]

    from core import extract, specs, storage, versus

    storage.reset_state()
    storage.init_db()

    with open(os.path.join(_FIXTURES, "specs_devices.tar.gz"), "rb") as f:
        specs._scarica = lambda: None
        specs.carica_da(specs.leggi_archivio(f.read()), "fixture di test")

    # ANCHE IL RIPIEGO ESTERNO VA ZITTITO. Dalla v49 una scheda mancante
    # per un realme o un HONOR fa scattare `core/versus.py`, che è rete: se
    # resta acceso, questi test disegnano una pagina diversa a seconda di
    # cosa risponde un server di terzi — cioè non collaudano più niente.
    versus._scarica = lambda url, parametri=None: None
    versus.reset_cache()

    # LA CHIAVE SI COSTRUISCE COL CODICE VERO, non a mano. È lei che lega
    # gli aggiornamenti a un dispositivo: scriverla a occhio in un test
    # significa collaudare una forma che in produzione non esiste.
    storage.upsert_update({
        "id": "samsung|galaxy-a07|a075fxxs1",
        "device_key": extract.device_key("Samsung", "Galaxy A07"),
        "brand": "Samsung", "device_model": "Galaxy A07",
        "model_code": "SM-A075F", "title": "Galaxy A07 riceve One UI 8",
        "build": "A075FXXS1AYG1", "os_version": "Android 16",
        "android_version": "16", "patch_level": "2026-06-01",
        "severity": "🟢 Patch", "color": "#00CC66", "severity_reason": "patch",
        "source": "samsung_fota", "source_label": "Endpoint FOTA ufficiale",
        "source_trust": "structured", "link": "", "published": "2026-06-20",
        "first_seen": "2026-06-21", "is_relevant": 1,
    })
    storage.upsert_update({
        "id": "samsung|galaxy-s24|s921bxxu",
        "device_key": extract.device_key("Samsung", "Galaxy S24"),
        "brand": "Samsung", "device_model": "Galaxy S24",
        "model_code": "SM-S921B", "title": "Galaxy S24 aggiornato",
        "build": "S921BXXU5CYA1", "os_version": "Android 16",
        "android_version": "16", "patch_level": "2026-05-01",
        "severity": "🟡 Feature", "color": "#FFAA00", "severity_reason": "build",
        "source": "samsung_fota", "source_label": "Endpoint FOTA ufficiale",
        "source_trust": "structured", "link": "", "published": "2026-05-10",
        "first_seen": "2026-05-11", "is_relevant": 1,
    })
    return cartella


class _Sito(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _prepara()
        from fastapi.testclient import TestClient

        from core import scan
        from web.main import app

        # LA RICERCA NON ESCE IN RETE. Si sostituisce l'unico punto che la
        # toccherebbe: il resto della catena — riconoscimento del codice,
        # scheda tecnica, suggerimenti — resta quello vero, ed è quello
        # che si vuole collaudare.
        cls._search_vera = scan.search_model
        scan.search_model = lambda q: cls.RISPOSTA_RICERCA(q)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from core import scan, specs

        scan.search_model = cls._search_vera
        specs.reset_cache()

    def setUp(self):
        """LA MEMORIA CORTA VA AZZERATA FRA UN TEST E L'ALTRO.

        Il sito ricorda l'esito di una ricerca per un quarto d'ora — è la
        correzione dei dodici secondi. Qui però le classi cambiano la
        risposta finta della stessa query da un test all'altro: senza
        questa riga il secondo test riceve la risposta preparata per il
        primo, e fallisce per un motivo che non c'entra niente con quello
        che sta collaudando. È la cache a essere giusta; è il test che
        deve dichiarare da dove parte.
        """
        from web.main import RICERCHE

        RICERCHE.svuota()

    RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [], "error": None})


class TestLePagineSiDisegnano(_Sito):
    def test_ogni_pagina_risponde(self):
        for percorso in ("/", "/dispositivi", "/aggiornamenti", "/parco",
                         "/catalogo", "/diagnostica", "/health"):
            with self.subTest(percorso=percorso):
                self.assertEqual(self.client.get(percorso).status_code, 200)

    def test_il_nome_del_sito_e_in_ogni_pagina(self):
        """Il difetto più stupido e più visibile della versione Streamlit:
        una testata alta zero, col solo filo nero e senza il nome."""
        for percorso in ("/", "/aggiornamenti", "/diagnostica"):
            with self.subTest(percorso=percorso):
                self.assertIn("Mobile Update Tracker",
                              self.client.get(percorso).text)

    def test_la_navigazione_marca_la_pagina_corrente(self):
        pagina = self.client.get("/aggiornamenti").text
        self.assertIn('href="/aggiornamenti" class="attiva"', pagina)

    def test_il_contatore_delle_fonti_e_vero(self):
        """Nel prototipo è scritto a mano. Qui viene dall'archivio, e per
        questo è la prima riga di diagnostica invece di una decorazione."""
        from core import storage

        storage.record_source_status("tale", "Fonte Tale", True, 12, None)
        storage.record_source_status("quale", "Fonte Quale", False, 0, "rotta")
        self.assertIn("1/2 fonti attive", self.client.get("/").text)

    def test_i_dispositivi_compaiono_in_tabella(self):
        # LA TABELLA STA IN «/dispositivi», non più sulla home: la home
        # è la sola barra di ricerca, e l'elenco ha una pagina sua.
        pagina = self.client.get("/dispositivi").text
        self.assertIn("Galaxy A07", pagina)
        self.assertIn("Galaxy S24", pagina)

    def test_il_processore_compare_in_tabella(self):
        """È la segnalazione da cui è partito tutto: il chip mancava."""
        pagina = self.client.get("/dispositivi").text
        self.assertIn("Helio G99", pagina)

    def test_la_diagnostica_mostra_lo_stato_del_backup(self):
        """Segnalato dall'utente: non c'era nessun modo di vedere da fuori
        se il backup esterno fosse configurato e funzionante — la pagina
        elencava fonti e cataloghi ma taceva sul backup, l'unica risposta
        concreta a «la correzione che ho salvato sopravviverà a un
        riavvio?». Vedi `P.stato_backup` e `TestStatoBackup` in
        `test_presenters.py` per i dettagli dei quattro stati."""
        pagina = self.client.get("/diagnostica").text
        self.assertIn("Backup esterno", pagina)
        self.assertIn("Ultimo salvataggio riuscito", pagina)
        self.assertIn("Ultimo ripristino", pagina)


class TestDiagnosticaConfigurazioneBackup(_Sito):
    """Segnalato dall'utente: aveva seguito i passaggi manuali (creare il
    token, creare il Gist, incollare due valori su Render) e la pagina
    continuava a dire «Non configurato» — tre pagine diverse sono tre
    occasioni di sbagliare o di non aver ancora aspettato il riavvio.
    Queste rotte (`POST /diagnostica/backup/crea` e
    `POST /diagnostica/backup/salva`, in `web/main.py`) tolgono di
    mezzo la creazione manuale del Gist e danno un modo diretto di
    verificare la configurazione attuale."""

    def setUp(self):
        from core import backup

        self._configurato = backup.configurato
        self._stato = backup.stato
        self._verifica_token = backup.verifica_token
        self._crea_archivio = backup.crea_archivio
        self._prova_completa = backup.prova_completa
        self._salva = backup.salva

    def tearDown(self):
        from core import backup

        backup.configurato = self._configurato
        backup.stato = self._stato
        backup.verifica_token = self._verifica_token
        backup.crea_archivio = self._crea_archivio
        backup.prova_completa = self._prova_completa
        backup.salva = self._salva

    def _non_configurato(self):
        from core import backup

        backup.configurato = lambda: False
        backup.stato = lambda: {"ultimo_esito": "non configurato",
                                "ultimo_salvataggio": None, "ultimo_ripristino": None}

    def _configurato_e_attivo(self):
        from core import backup

        backup.configurato = lambda: True
        backup.stato = lambda: {"ultimo_esito": "salvato (12 KB compressi)",
                                "ultimo_salvataggio": "2026-08-12T10:00:00+00:00",
                                "ultimo_ripristino": None}

    def _configurato_con_errore(self):
        # Segnalato dall'utente sul sito vero: aveva incollato lo stesso
        # valore sia in BACKUP_GIST_ID sia in BACKUP_GITHUB_TOKEN — GitHub
        # rispondeva 401 Bad credentials. `configurato()` torna True (le
        # due variabili sono valorizzate, l'app non sa che sono sbagliate),
        # ma non è mai stato salvato niente: questo È lo stato «Errore».
        from core import backup

        backup.configurato = lambda: True
        backup.stato = lambda: {
            "ultimo_esito": 'GitHub ha risposto 401: { "message": "Bad credentials" }',
            "ultimo_salvataggio": None, "ultimo_ripristino": None}

    def test_il_modulo_di_configurazione_compare_solo_se_non_configurato(self):
        self._non_configurato()
        pagina = self.client.get("/diagnostica").text
        self.assertIn("Configura il backup", pagina)
        self.assertIn('name="token"', pagina)

    def test_a_configurazione_attiva_compare_salva_adesso_non_il_modulo(self):
        self._configurato_e_attivo()
        pagina = self.client.get("/diagnostica").text
        self.assertNotIn("Configura il backup", pagina)
        self.assertNotIn("Rifai la configurazione", pagina)
        self.assertIn("Salva adesso, per verificare", pagina)

    def test_in_errore_compaiono_sia_salva_adesso_sia_rifai_la_configurazione(self):
        # Il caso reale: valori sbagliati su Render (per esempio lo stesso
        # valore incollato in entrambe le variabili) producono «Errore»,
        # non «Non configurato» — chi lo vede deve poter sia riprovare sia
        # rifare la configurazione da capo, senza restare bloccato.
        self._configurato_con_errore()
        pagina = self.client.get("/diagnostica").text
        self.assertIn("Rifai la configurazione", pagina)
        self.assertIn('name="token"', pagina)
        self.assertIn("Salva adesso, per verificare", pagina)

    def test_token_valido_crea_larchivio_e_mostra_i_due_valori_da_copiare(self):
        from core import backup

        self._non_configurato()
        backup.verifica_token = lambda t: (True, "token valido (utente prova)")
        backup.crea_archivio = lambda t: (True, "archivio creato", "abc123def456")
        backup.prova_completa = lambda gid, t: (True, "scrittura e rilettura riuscite")

        pagina = self.client.post(
            "/diagnostica/backup/crea", data={"token": "ghp_finto"}).text
        self.assertIn("Archivio creato e verificato", pagina)
        self.assertIn("abc123def456", pagina)
        self.assertIn("BACKUP_GIST_ID", pagina)
        self.assertIn("BACKUP_GITHUB_TOKEN", pagina)
        # IL TOKEN NON SI RISCRIVE IN CHIARO NELLA RISPOSTA: chi lo ha
        # appena incollato lo riusa da dove lo ha preso, non da qui.
        self.assertNotIn("ghp_finto", pagina)

    def test_token_non_valido_mostra_lerrore_e_non_crea_niente(self):
        from core import backup

        self._non_configurato()
        chiamato = {"crea": False}
        backup.verifica_token = lambda t: (False, "token non valido o scaduto")

        def crea_vietata(t):
            chiamato["crea"] = True
            return True, "non dovrebbe mai partire", "xxx"

        backup.crea_archivio = crea_vietata

        pagina = self.client.post(
            "/diagnostica/backup/crea", data={"token": "ghp_scaduto"}).text
        self.assertIn("Il token non va bene", pagina)
        self.assertIn("token non valido o scaduto", pagina)
        self.assertFalse(chiamato["crea"],
                         "un token non valido non deve arrivare a creare l'archivio")

    def test_salva_adesso_mostra_lesito_vero(self):
        from core import backup

        self._configurato_e_attivo()
        backup.salva = lambda: (True, "salvato (9 KB compressi)")

        pagina = self.client.post("/diagnostica/backup/salva").text
        self.assertIn("Salvataggio riuscito", pagina)
        self.assertIn("salvato (9 KB compressi)", pagina)

    def test_salva_adesso_con_esito_negativo_lo_dice(self):
        from core import backup

        self._configurato_e_attivo()
        backup.salva = lambda: (False, "GitHub ha risposto 401: token non valido")

        pagina = self.client.post("/diagnostica/backup/salva").text
        self.assertIn("Salvataggio non riuscito", pagina)
        self.assertIn("401", pagina)


class TestNotaCoperturaConChipTrovato(unittest.TestCase):
    """Il round di inserimento metodico ha esteso `data/soc_modelli.csv` a
    HONOR e realme: per quei codici `chip` si trova (tabella curata) ma
    `scheda` (RAM, storage, fotocamera — dal catalogo automatico di
    `specs.py`, che quelle marche non copre) resta vuota. Prima la pagina
    mostrava comunque «Specifiche hardware non disponibili... realme non
    ci sono» SUBITO SOTTO il processore appena mostrato — sembrava una
    contraddizione, non un buco di copertura parziale. Misurato cercando
    «realme c63» in produzione, insieme al bug di identità distinto
    corretto in `TestNomeAmbiguoNonReindirizzaAUnAltroTelefono`."""

    @classmethod
    def setUpClass(cls):
        _prepara()
        from core import extract, storage

        storage.upsert_update({
            "id": "oppo|realme-c63|rmx3939-rilevato",
            "device_key": extract.device_key("Oppo / Realme / OnePlus", "realme C63"),
            "brand": "Oppo / Realme / OnePlus", "device_model": "realme C63",
            "model_code": "RMX3939", "title": "realme C63 (RMX3939) riconosciuto",
            "build": "", "os_version": "", "android_version": None,
            "patch_level": "", "severity": "", "color": "", "severity_reason": "",
            "source": "official_lookup",
            "source_label": "Riconoscimento del codice modello (ricerca diretta)",
            "source_trust": "structured", "link": "", "published": None,
            "first_seen": "2026-08-11", "is_relevant": 1,
        })

        from fastapi.testclient import TestClient

        from core import scan
        from web.main import app

        cls._search_vera = scan.search_model
        scan.search_model = lambda q: {"items": [], "error": None}
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from core import scan, specs

        scan.search_model = cls._search_vera
        specs.reset_cache()

    def setUp(self):
        from web.main import RICERCHE

        RICERCHE.svuota()

    def _chiave(self) -> str:
        from core import storage

        return next(d["device_key"] for d in storage.get_devices()
                    if "C63" in d["model"])

    def test_mostra_il_processore_curato(self):
        pagina = self.client.get("/dispositivo", params={"k": self._chiave()}).text
        self.assertIn("Tiger T612", pagina)

    def test_la_nota_non_contraddice_il_processore_appena_mostrato(self):
        pagina = self.client.get("/dispositivo", params={"k": self._chiave()}).text
        self.assertIn("tabella verificata a mano", pagina)
        self.assertNotIn("Specifiche hardware non disponibili per questo modello.",
                         pagina)


class TestSchedaDispositivo(_Sito):
    def _chiave(self) -> str:
        from core import storage

        return next(d["device_key"] for d in storage.get_devices()
                    if "A07" in d["model"])

    def test_la_scheda_mostra_hardware_e_ram(self):
        pagina = self.client.get("/dispositivo", params={"k": self._chiave()}).text
        for atteso in ("Helio G99", "4 / 6 / 8 GB", "5000 mAh", "Batteria"):
            with self.subTest(atteso=atteso):
                self.assertIn(atteso, pagina)

    def test_la_chiave_con_le_barre_non_fa_404(self):
        """Le chiavi hanno dentro barre e barre verticali
        (`vivo / iqoo / motorola|v29`). In un segmento di percorso la
        barra è un separatore e l'indirizzo non corrisponderebbe mai."""
        from core import storage

        from core import extract

        chiave = extract.device_key("Vivo / iQOO / Motorola", "vivo V29")
        self.assertIn("|", chiave)
        risposta = self.client.get("/dispositivo", params={"k": chiave},
                                   follow_redirects=False)
        # Non è in archivio, quindi rimanda all'elenco: quello che conta è
        # che l'indirizzo venga instradato invece di dare 404.
        self.assertEqual(risposta.status_code, 303)

    def test_chiave_inesistente_riporta_all_elenco(self):
        risposta = self.client.get("/dispositivo", params={"k": "non|esiste"},
                                   follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)


class TestRicercaRicordata(_Sito):
    """DODICI SECONDI, E NESSUNA MEMORIA FRA DUE RICERCHE UGUALI.

    Misurato sul sito vero il 2026-08-10: `GET /?q=SM-S928B` impiegava
    12,84 s, e ripeterlo ne impiegava altri dodici — undici richieste di
    rete rifatte identiche. Chi non vede una risposta ricarica la pagina,
    quindi il caso «stessa domanda due volte» non è raro: è il più comune.

    Una cache qui è onesta perché le fonti pubblicano un firmware al
    massimo una volta al giorno e la scansione gira una volta all'ora:
    quindici minuti non nascondono niente che possa essere cambiato.
    """

    def test_la_seconda_ricerca_non_interroga_di_nuovo_le_fonti(self):
        chiamate = []

        def conta(q):
            chiamate.append(q)
            return {"items": [], "error": None}

        type(self).RISPOSTA_RICERCA = staticmethod(conta)
        try:
            self.client.get("/", params={"q": "SM-A075F"})
            self.client.get("/", params={"q": "SM-A075F"})
            self.assertEqual(len(chiamate), 1,
                             "la seconda ricerca ha ripagato la rete")
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})

    def test_spazi_e_maiuscole_sono_la_stessa_domanda(self):
        chiamate = []

        def conta(q):
            chiamate.append(q)
            return {"items": [], "error": None}

        type(self).RISPOSTA_RICERCA = staticmethod(conta)
        try:
            self.client.get("/", params={"q": "SM-A075F"})
            self.client.get("/", params={"q": "  sm-a075f "})
            self.assertEqual(len(chiamate), 1)
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})

    def test_ricerche_diverse_restano_diverse(self):
        """Una cache che risponde alla domanda sbagliata è molto peggio
        di una cache che non c'è."""
        viste = []
        type(self).RISPOSTA_RICERCA = staticmethod(
            lambda q: (viste.append(q), {"items": [], "error": None})[1])
        try:
            self.client.get("/", params={"q": "SM-A075F"})
            self.client.get("/", params={"q": "SM-S928B"})
            self.assertEqual(viste, ["SM-A075F", "SM-S928B"])
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})

    def test_salvare_un_tac_a_mano_cancella_la_memoria(self):
        """Hai appena corretto il modello di quel TAC: se la ricerca
        rispondesse dalla cache ti restituirebbe la risposta sbagliata
        che eri venuto a correggere, e sembrerebbe che il salvataggio non
        abbia funzionato."""
        from web.main import RICERCHE

        RICERCHE.scrivi("qualcosa", {"query": "qualcosa"})
        self.client.post("/tac/salva",
                         data={"tac": "35135531", "marca": "Samsung",
                               "modello": "Galaxy A54 5G", "imei": ""},
                         follow_redirects=False)
        self.assertIsNone(RICERCHE.leggi("qualcosa"))


class TestRigheCostruiteSoloSeSiVedono(_Sito):
    """Si costruivano 1536 righe per mostrarne 200.

    Il taglio stava nel template (`righe[:200]`), cioè DOPO che ogni riga
    aveva già risolto il proprio processore — la parte cara. Misurato su
    questo archivio: 50 ms per tutte contro 5 ms per quelle che si
    vedono, su una macchina molto più veloce di quella che serve il sito.
    """

    def test_si_presentano_solo_le_righe_in_pagina(self):
        from web import main as M
        from web import presenters as P

        quante = []
        vera = P.riga_dispositivo

        def conta(device, in_parco=False):
            quante.append(device)
            return vera(device, in_parco)

        P.riga_dispositivo = conta
        try:
            self.client.get("/dispositivi")
        finally:
            P.riga_dispositivo = vera
        self.assertLessEqual(len(quante), M.IN_PAGINA)

    def test_il_totale_resta_quello_vero(self):
        """Impaginare non deve far sparire il conteggio: chi guarda deve
        sapere che sotto le duecento righe ce ne sono altre."""
        from core import storage

        quanti = len(storage.get_devices())
        pagina = self.client.get("/dispositivi").text
        if quanti > 200:
            self.assertIn(str(quanti), pagina)


class TestRicerca(_Sito):
    def test_un_modello_trovato_mostra_la_scheda(self):
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "source_label": "Endpoint FOTA ufficiale",
            "brand": "Samsung", "device_model": "Galaxy A07",
            "model_code": "SM-A075F", "build": "A075FXXS1AYG1",
            "os_version": "Android 16", "android_version": "16",
            "patch_level": "2026-06-01", "published": "2026-06-20",
            "title": "", "severity": "", "color": "#00CC66",
        }], "error": None})
        try:
            pagina = self.client.get("/", params={"q": "SM-A075F"}).text
            self.assertIn("Galaxy A07", pagina)
            self.assertIn("A075FXXS1AYG1", pagina)
            self.assertIn("Helio G99", pagina)
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})

    def test_un_modello_non_trovato_lo_dice_e_propone(self):
        """E NON mostra una scheda di soli trattini: sotto un «nessun
        firmware trovato» non aggiunge niente e fa sembrare guasto quello
        che è un modello inesistente."""
        pagina = self.client.get("/", params={"q": "SMA075F"}).text
        self.assertIn("Nessun firmware", pagina)
        # Il livello gratuito deve aver corretto il codice senza trattino.
        self.assertIn("SM-A075F", pagina)

    def test_i_nomi_gemelli_del_codice_si_vedono_in_pagina(self):
        """Un codice con più di un nome commerciale vero (misurato:
        `RMX3933` = C61/Note 60/Note 60s/NARZO N61) deve mostrarli in
        pagina, non solo quello scelto — vedi `_nomi_gemelli` in
        `web/main.py`."""
        from core import modelcodes

        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "source_label": "Riconoscimento del codice modello",
            "brand": "Oppo / Realme / OnePlus", "device_model": "Test Alpha",
            "model_code": None, "title": "Test Alpha (ZZ5555)", "severity": "",
            "color": "#00CC66", "size_info": "Codice modello riconosciuto (ZZ5555)",
            "os_version": "", "android_version": None,
        }], "error": None})
        if modelcodes._memory_cache is None:
            modelcodes._memory_cache = {}
        modelcodes._memory_cache["ZZ5555"] = ["Test Alpha", "Test Beta"]
        try:
            pagina = self.client.get("/", params={"q": "realme ZZ5555"}).text
            self.assertIn("noto anche come", pagina)
            self.assertIn("Test Beta", pagina)
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})
            modelcodes._memory_cache.pop("ZZ5555", None)

    def test_riconosciuto_ma_senza_firmware_non_dice_trovato(self):
        """Alcune fonti confermano che il modello esiste ma non pubblicano
        la versione. Dire «trovato» lì fa credere di avere una risposta
        che non c'è."""
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "curated_lookup", "source_label": "Tabella curata",
            "brand": "Samsung", "device_model": "Galaxy A07",
            "model_code": "SM-A075F", "title": "", "severity": "",
            "color": "#00CC66",
        }], "error": None})
        try:
            pagina = self.client.get("/", params={"q": "SM-A075F"}).text
            self.assertIn("nessuna fonte ne pubblica la versione", pagina)
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})

    def test_il_risultato_propone_il_confronto(self):
        """L'ingresso alla pagina di confronto (vedi `TestConfronto` sotto):
        un clic dal risultato di una ricerca, col primo modello già
        scritto."""
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "source_label": "Endpoint FOTA ufficiale",
            "brand": "Samsung", "device_model": "Galaxy A07",
            "model_code": "SM-A075F", "build": "A075FXXS1AYG1",
            "os_version": "Android 16", "android_version": "16",
            "patch_level": "2026-06-01", "published": "2026-06-20",
            "title": "", "severity": "", "color": "#00CC66",
        }], "error": None})
        try:
            pagina = self.client.get("/", params={"q": "SM-A075F"}).text
            self.assertIn("/confronto?a=SM-A075F", pagina)
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})


class TestConfronto(_Sito):
    """La pagina che mette due modelli fianco a fianco.

    Nasce dal bug «RMX3939 rispondeva coi dati di RMX3930» (vedi
    FONTI.md): la domanda che quel bug ha reso concreta — due nomi vicini
    sono lo stesso telefono, o due telefoni diversi? — qui la si dà in
    mano a chi guarda invece di lasciarla indovinare al sistema.
    """

    def test_senza_i_due_modelli_mostra_linvito_non_la_tabella(self):
        pagina = self.client.get("/confronto").text
        self.assertIn("Scrivi un nome o un codice", pagina)
        self.assertNotIn('class="tabella minuta tabella-confronto"', pagina)

    def test_un_solo_modello_scritto_mostra_ancora_linvito(self):
        """Metà del confronto non è un confronto: manca l'altro termine di
        paragone, non solo il suo dato."""
        pagina = self.client.get("/confronto", params={"a": "SM-A075F"}).text
        self.assertIn("Scrivi un nome o un codice", pagina)

    def test_due_modelli_diversi_mostrano_nomi_e_differenze_vere(self):
        """Galaxy A07 (Helio G99, dalla fixture specs) contro Galaxy S24
        (Exynos 2400, dalla tabella curata) — una differenza di CPU vera,
        non simulata, esattamente come la vedrebbe chi fa QA."""
        risposte = {
            "SM-A075F": {"items": [{
                "source": "official_lookup", "source_label": "Endpoint FOTA ufficiale",
                "brand": "Samsung", "device_model": "Galaxy A07",
                "model_code": "SM-A075F", "build": "A075FXXS1AYG1",
                "os_version": "Android 16", "android_version": "16",
                "patch_level": "2026-06-01", "published": "2026-06-20",
                "title": "", "severity": "", "color": "#00CC66",
            }], "error": None},
            "SM-S921B": {"items": [{
                "source": "official_lookup", "source_label": "Endpoint FOTA ufficiale",
                "brand": "Samsung", "device_model": "Galaxy S24",
                "model_code": "SM-S921B", "build": "S921BXXU5CYA1",
                "os_version": "Android 16", "android_version": "16",
                "patch_level": "2026-05-01", "published": "2026-05-10",
                "title": "", "severity": "", "color": "#00CC66",
            }], "error": None},
        }
        type(self).RISPOSTA_RICERCA = staticmethod(
            lambda q: risposte.get(q, {"items": [], "error": None}))
        try:
            pagina = self.client.get(
                "/confronto", params={"a": "SM-A075F", "b": "SM-S921B"}).text
            self.assertIn("Galaxy A07", pagina)
            self.assertIn("Galaxy S24", pagina)
            self.assertIn("Helio G99", pagina)
            self.assertIn("Exynos 2400", pagina)
            # La riga del processore deve essere segnata come diversa.
            self.assertIn('<tr class="diversi">', pagina)
            self.assertNotIn("risolvono allo stesso identico modello", pagina)
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})

    def test_lo_stesso_modello_scritto_due_volte_lo_dichiara(self):
        """Non un confronto fra due telefoni: lo stesso, chiesto due volte
        — deve dirlo, non lasciarlo capire da una tabella tutta uguale."""
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "source_label": "Endpoint FOTA ufficiale",
            "brand": "Samsung", "device_model": "Galaxy A07",
            "model_code": "SM-A075F", "build": "A075FXXS1AYG1",
            "os_version": "Android 16", "android_version": "16",
            "patch_level": "2026-06-01", "published": "2026-06-20",
            "title": "", "severity": "", "color": "#00CC66",
        }], "error": None})
        try:
            pagina = self.client.get(
                "/confronto", params={"a": "SM-A075F", "b": "sm-a075f"}).text
            self.assertIn("risolvono allo stesso identico modello", pagina)
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})


class TestCorrezioneNomeModello(_Sito):
    """Il nome commerciale scelto a mano per un codice — vedi il
    commento in `web.main._cerca_davvero` per il bug reale che l'ha
    motivato: un codice con più nomi veri (misurato su `RMX3933`: C61,
    Note 60, Note 60s, NARZO N61) mostra un nome scelto in automatico
    (il più corto) che può non essere quello di chi ha il telefono in
    mano. Qui si verifica che la correzione si salvi e valga per ogni
    ricerca futura di quel codice, con qualsiasi dei suoi nomi.

    `ZZ5555` è un codice di prova, non uno vero (stessa convenzione di
    `test_i_nomi_gemelli_del_codice_si_vedono_in_pagina`): iniettato in
    `modelcodes._memory_cache` invece di dipendere dal dataset scaricato,
    così il test resta deterministico.
    """

    def setUp(self):
        from core import modelcodes

        from web.main import RICERCHE

        RICERCHE.svuota()
        if modelcodes._memory_cache is None:
            modelcodes._memory_cache = {}
        modelcodes._memory_cache["ZZ5555"] = ["Test Alpha", "Test Beta"]
        # `codes_for_name` (usata da `_codici_del_risultato`, che decide su
        # quale codice si appoggia la correzione) tiene un indice inverso
        # costruito UNA VOLTA SOLA da `_memory_cache` e mai più aggiornato
        # (vedi il suo docstring): senza invalidarlo qui, il test userebbe
        # un indice costruito da un giro precedente, senza «ZZ5555» dentro.
        modelcodes._reverse_cache = None
        modelcodes._reverse_senza_suffisso = None
        modelcodes._reverse_compatto = None
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "source_label": "Riconoscimento del codice modello",
            "brand": "Oppo / Realme / OnePlus", "device_model": "Test Alpha",
            "model_code": "ZZ5555", "title": "Test Alpha (ZZ5555)", "severity": "",
            "color": "#00CC66", "os_version": "", "android_version": None,
        }], "error": None})

    def tearDown(self):
        from core import modelcodes, storage

        from web.main import RICERCHE

        type(self).RISPOSTA_RICERCA = staticmethod(
            lambda q: {"items": [], "error": None})
        modelcodes._memory_cache.pop("ZZ5555", None)
        modelcodes._reverse_cache = None
        modelcodes._reverse_senza_suffisso = None
        modelcodes._reverse_compatto = None
        storage.set_nome_modello("ZZ5555", "")
        RICERCHE.svuota()

    def test_senza_correzione_mostra_il_nome_della_fonte(self):
        pagina = self.client.get("/", params={"q": "realme ZZ5555"}).text
        self.assertIn("Test Alpha", pagina)
        self.assertIn("Non è il nome giusto?", pagina)

    def test_la_correzione_salvata_diventa_il_nome_mostrato(self):
        risposta = self.client.post(
            "/modello/correggi",
            data={"codice": "ZZ5555", "nome": "Test Beta", "query": "realme ZZ5555"},
            follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)

        pagina = self.client.get("/", params={"q": "realme ZZ5555"}).text
        self.assertIn("Test Beta", pagina)
        self.assertIn("Nome corretto a mano", pagina)
        # Il nome scartato ora è un gemello, non più il titolo.
        self.assertIn("noto anche come", pagina)

    def test_la_correzione_vale_anche_cercando_con_un_altro_nome_vero(self):
        """Il punto della funzionalità: non solo con la stessa forma
        scritta la prima volta. Stesso codice, nome diverso digitato —
        deve trovare comunque la scelta salvata."""
        storage_set = self.client.post(
            "/modello/correggi",
            data={"codice": "ZZ5555", "nome": "Test Beta", "query": "realme ZZ5555"},
            follow_redirects=False)
        self.assertEqual(storage_set.status_code, 303)

        # La fonte simulata risponde sempre "Test Alpha" come device_model
        # (la risposta è fissa, vedi RISPOSTA_RICERCA in setUp): quello che
        # cambia è solo il testo digitato, esattamente come cercare lo
        # stesso telefono scrivendolo in un altro modo.
        pagina = self.client.get("/", params={"q": "Test Alpha"}).text
        self.assertIn("Test Beta", pagina)

    def test_si_puo_tornare_alla_scelta_automatica(self):
        self.client.post("/modello/correggi",
                         data={"codice": "ZZ5555", "nome": "Test Beta",
                               "query": "realme ZZ5555"})
        self.client.post("/modello/correggi",
                         data={"codice": "ZZ5555", "nome": "",
                               "query": "realme ZZ5555"})
        pagina = self.client.get("/", params={"q": "realme ZZ5555"}).text
        self.assertIn("Test Alpha", pagina)
        self.assertNotIn("Nome corretto a mano", pagina)

    def test_la_memoria_corta_si_dimentica_dopo_il_salvataggio(self):
        """Come `test_salvare_un_tac_a_mano_cancella_la_memoria`: senza
        svuotare la cache la ricerca ripeterebbe la risposta di prima e
        la correzione sembrerebbe non aver funzionato.

        Il client di test segue il redirect del POST, che rifà quindi una
        `GET /` e ripopola la cache: quello che conta è che la ripopoli
        con la risposta CORRETTA, non con quella vecchia rimasta lì."""
        from web.main import RICERCHE

        self.client.get("/", params={"q": "realme ZZ5555"})
        self.assertEqual(RICERCHE.leggi("realme zz5555")["nome"], "Test Alpha")
        self.client.post("/modello/correggi",
                         data={"codice": "ZZ5555", "nome": "Test Beta",
                               "query": "realme ZZ5555"})
        self.assertEqual(RICERCHE.leggi("realme zz5555")["nome"], "Test Beta")


class TestCorrezioneNomeModelloConMarcaSintetica(_Sito):
    """Il caso reale che ha motivato `_opzioni_correzione`: RMX3933.

    Nel dataset vero nessuno dei nomi di quel codice scrive «realme» per
    esteso — solo «NARZO N61», riconosciuto come sinonimo — quindi
    «realme Note 60» non è mai stato un nome che i «gemelli» potessero
    mostrare (sono solo forme verificate dal dataset). Qui si verifica che
    il menu di correzione proponga comunque quella forma, aggiunta perché
    la marca si conosce e la forma resta collegata alla stessa scheda.

    `ZZ6001` è un codice di prova, stessa convenzione delle altre classi
    di questo file.
    """

    def setUp(self):
        from core import aer_catalog, modelcodes

        from web.main import RICERCHE

        RICERCHE.svuota()
        aer_catalog.reset_cache()
        if modelcodes._memory_cache is None:
            modelcodes._memory_cache = {}
        modelcodes._memory_cache["ZZ6001"] = ["Nota Prova", "NARZO Nota Prova"]
        modelcodes._reverse_cache = None
        modelcodes._reverse_senza_suffisso = None
        modelcodes._reverse_compatto = None
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "source_label": "Riconoscimento del codice modello",
            "brand": "Oppo / Realme / OnePlus", "device_model": "Nota Prova",
            "model_code": "ZZ6001", "title": "Nota Prova (ZZ6001)", "severity": "",
            "color": "#00CC66", "os_version": "", "android_version": None,
        }], "error": None})

    def tearDown(self):
        from core import aer_catalog, modelcodes, storage

        from web.main import RICERCHE

        type(self).RISPOSTA_RICERCA = staticmethod(
            lambda q: {"items": [], "error": None})
        modelcodes._memory_cache.pop("ZZ6001", None)
        modelcodes._reverse_cache = None
        modelcodes._reverse_senza_suffisso = None
        modelcodes._reverse_compatto = None
        storage.set_nome_modello("ZZ6001", "")
        aer_catalog.reset_cache()
        RICERCHE.svuota()

    def test_la_forma_con_la_marca_compare_fra_le_opzioni_anche_se_non_e_un_gemello(self):
        pagina = self.client.get("/", params={"q": "ZZ6001"}).text
        self.assertIn("Nota Prova", pagina)
        # NON è un nome verificato dal dataset: non deve comparire come
        # pastiglia fra i «gemelli» dichiarati (quel link punta a una
        # ricerca, e userebbe questa forma esattamente come le altre).
        self.assertNotIn('href="/?q=Realme%20Nota%20Prova"', pagina)
        # Ma resta un'opzione valida nel menu di correzione.
        self.assertIn('<option value="Realme Nota Prova">', pagina)

    def test_si_puo_scegliere_la_forma_con_la_marca_come_nome_principale(self):
        risposta = self.client.post(
            "/modello/correggi",
            data={"codice": "ZZ6001", "nome": "Realme Nota Prova", "query": "ZZ6001"},
            follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)

        pagina = self.client.get("/", params={"q": "ZZ6001"}).text
        self.assertIn("Realme Nota Prova", pagina)
        self.assertIn("Nome corretto a mano", pagina)


class TestCorrezioneNomeScrittaAMano(_Sito):
    """Il testo libero, ultima via d'uscita per chi non riconosce il
    proprio telefono in NESSUNA delle forme proposte — segnalato
    dall'utente, che chiedeva la stessa cosa già disponibile per un TAC
    sconosciuto (vedi `_imei.html` e `imeicheck.aggiungi_tac`). Stesso
    campo `nome` del menu a tendina, solo un widget diverso: il backend
    (`POST /modello/correggi`) non ha bisogno di sapere da quale dei due
    è arrivato.
    """

    def setUp(self):
        from core import modelcodes

        from web.main import RICERCHE

        RICERCHE.svuota()
        if modelcodes._memory_cache is None:
            modelcodes._memory_cache = {}
        modelcodes._memory_cache["ZZ7001"] = ["Test Alpha", "Test Beta"]
        modelcodes._reverse_cache = None
        modelcodes._reverse_senza_suffisso = None
        modelcodes._reverse_compatto = None
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "source_label": "Riconoscimento del codice modello",
            "brand": "", "device_model": "Test Alpha",
            "model_code": "ZZ7001", "title": "Test Alpha (ZZ7001)", "severity": "",
            "color": "#00CC66", "os_version": "", "android_version": None,
        }], "error": None})

    def tearDown(self):
        from core import modelcodes, storage

        from web.main import RICERCHE

        type(self).RISPOSTA_RICERCA = staticmethod(
            lambda q: {"items": [], "error": None})
        modelcodes._memory_cache.pop("ZZ7001", None)
        modelcodes._reverse_cache = None
        modelcodes._reverse_senza_suffisso = None
        modelcodes._reverse_compatto = None
        storage.set_nome_modello("ZZ7001", "")
        RICERCHE.svuota()

    def test_il_campo_di_testo_libero_compare_nella_pagina(self):
        pagina = self.client.get("/", params={"q": "ZZ7001"}).text
        self.assertIn("Non trovi il nome giusto? Scrivilo tu", pagina)
        self.assertIn('id="correzione-nome-libero"', pagina)

    def test_si_puo_salvare_un_nome_scritto_a_mano(self):
        risposta = self.client.post(
            "/modello/correggi",
            data={"codice": "ZZ7001", "nome": "Nome Scritto A Mano", "query": "ZZ7001"},
            follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)

        pagina = self.client.get("/", params={"q": "ZZ7001"}).text
        self.assertIn("Nome Scritto A Mano", pagina)
        self.assertIn("Nome corretto a mano", pagina)


class TestNomeDallaSchedaSenzaFirmware(_Sito):
    """Segnalato dall'utente cercando «m1910f4g» (Xiaomi Mi Note 10):
    nessuna fonte firmware conosceva quel codice, ma la scheda tecnica
    (foto, processore) lo trovava lo stesso — `specs.cerca` prova il
    testo anche senza che abbia la forma di un codice riconosciuto. Il
    risultato era «Nessun firmware per «m1910f4g»» sopra una scheda con
    la foto del telefono giusto: nessun nome, solo il codice grezzo
    ripetuto.

    Qui si riproduce lo stesso scarto con un codice sintetico che NON è
    nella forma di nessun codice riconosciuto (vedi
    `TestCodiceXiaomiStileClassico` per il caso Xiaomi vero, dove la
    causa era la forma del codice; qui la causa è più a monte — anche un
    codice che non ha affatto la forma di uno vero, ma che la scheda
    tecnica sa comunque risolvere) — per collaudare il ramo di
    `_cerca_davvero` senza dipendere dal dataset Xiaomi vero.
    """

    _RIGA_SINTETICA = {
        "nome": "Test Phone X9", "marca": "TestBrand",
        "foto": "https://example.com/foto-test.jpg",
        "codici": ("ZZFAKE001",), "rilascio": "2024, gennaio",
        "chipset": "Test Chip 9000", "cpu": "Octa-core", "gpu": "Test GPU",
        "ram_gb": (8,), "storage_gb": (128,),
        "display": "6.5 pollici", "display_tipo": "AMOLED",
        "batteria": "5000 mAh", "ricarica": "33W",
        "camera_post": "50 MP", "camera_front": "16 MP",
        "os_lancio": "Android 14", "peso": "190 g", "dimensioni": "160 x 75 x 8 mm",
    }

    def setUp(self):
        from core import specs

        from web.main import RICERCHE

        RICERCHE.svuota()
        # SI AGGIUNGE ALLA FIXTURE REALE, non la si sostituisce: `specs` è
        # un catalogo globale condiviso da tutti i test di questo processo,
        # e rimpiazzarla lascerebbe gli altri test senza le schede vere
        # che si aspettano.
        self._schede_originali = list(specs._schede)
        specs.carica_da(self._schede_originali + [self._RIGA_SINTETICA],
                        "fixture di test + scheda sintetica")

    def tearDown(self):
        from core import specs

        from web.main import RICERCHE

        specs.carica_da(self._schede_originali, "fixture di test")
        RICERCHE.svuota()

    def test_il_nome_risolto_dalla_scheda_compare_in_testata(self):
        pagina = self.client.get("/", params={"q": "ZZFAKE001"}).text
        self.assertIn("Test Phone X9", pagina)
        self.assertNotIn("Nessun firmware per «ZZFAKE001»", pagina)

    def test_dice_onestamente_che_manca_solo_il_firmware(self):
        pagina = self.client.get("/", params={"q": "ZZFAKE001"}).text
        self.assertIn("riconosciuto dalla scheda tecnica", pagina)

    def test_un_codice_davvero_sconosciuto_resta_senza_nome(self):
        """Il ramo nuovo non deve far comparire un nome dal nulla: senza
        una scheda risolta, resta il messaggio onesto di sempre."""
        pagina = self.client.get("/", params={"q": "ZZNONESISTE999"}).text
        self.assertIn("Nessun firmware per «ZZNONESISTE999»", pagina)


class TestCorrezioneAvviaSubitoIlBackup(_Sito):
    """Segnalato dall'utente: «assicurati che quando correggo il nome il
    risultato si salvi perché sembra che non lo faccia».

    Il salvataggio in sé funzionava già (finisce nella tabella
    `nomi_modello` di `tracker.db`), ma quel database vive in `/tmp`
    (disco effimero per scelta, vedi `Dockerfile`) e l'unica copia
    duratura è il backup su Gist — caricato prima SOLO a fine di ogni
    scansione periodica, non più spesso di `BACKUP_EVERY_MINUTES` (30 di
    default). Sul piano gratuito il servizio si addormenta dopo ~15
    minuti, portando via con sé anche il thread di scansione: una
    correzione fatta in quella finestra poteva restare solo nel database
    locale e sparire al riavvio successivo. Qui si collauda che
    `_backup_subito` (in `web/main.py`) faccia partire un salvataggio
    subito dopo ogni correzione, senza aspettare quel giro.
    """

    def setUp(self):
        from core import backup, modelcodes

        from web.main import RICERCHE

        RICERCHE.svuota()
        if modelcodes._memory_cache is None:
            modelcodes._memory_cache = {}
        modelcodes._memory_cache["ZZ8001"] = ["Test Gamma"]
        modelcodes._reverse_cache = None
        modelcodes._reverse_senza_suffisso = None
        modelcodes._reverse_compatto = None
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {"items": [{
            "source": "official_lookup", "source_label": "Riconoscimento del codice modello",
            "brand": "", "device_model": "Test Gamma",
            "model_code": "ZZ8001", "title": "Test Gamma (ZZ8001)", "severity": "",
            "color": "#00CC66", "os_version": "", "android_version": None,
        }], "error": None})

        self._salva_vera = backup.salva
        self.chiamato = threading.Event()

        def salva_finta():
            self.chiamato.set()
            return True, "ok (finto)"

        backup.salva = salva_finta

    def tearDown(self):
        from core import backup, modelcodes, storage

        from web.main import RICERCHE

        backup.salva = self._salva_vera
        type(self).RISPOSTA_RICERCA = staticmethod(
            lambda q: {"items": [], "error": None})
        modelcodes._memory_cache.pop("ZZ8001", None)
        modelcodes._reverse_cache = None
        modelcodes._reverse_senza_suffisso = None
        modelcodes._reverse_compatto = None
        storage.set_nome_modello("ZZ8001", "")
        RICERCHE.svuota()

    def test_la_correzione_del_nome_avvia_subito_un_backup(self):
        self.client.post(
            "/modello/correggi",
            data={"codice": "ZZ8001", "nome": "Nome Corretto", "query": "ZZ8001"},
            follow_redirects=False)
        self.assertTrue(
            self.chiamato.wait(timeout=2),
            "backup.salva() non è stato chiamato entro 2 secondi dalla correzione")

    def test_il_salvataggio_tac_avvia_subito_un_backup(self):
        self.client.post(
            "/tac/salva",
            data={"tac": "12345678", "marca": "Test", "modello": "Test Gamma"},
            follow_redirects=False)
        self.assertTrue(
            self.chiamato.wait(timeout=2),
            "backup.salva() non è stato chiamato entro 2 secondi dal salvataggio TAC")


class TestRicercaPerImei(_Sito):
    """IL RAMO CHE ERA RIMASTO INDIETRO NEL PASSAGGIO AL SITO.

    Quindici cifre non sono né un nome né un codice modello: passarle
    dritte a `search_model` significa cercare un telefono che si chiama
    «867051060315467», e trovarne zero. Va prima riconosciuto l'IMEI,
    ridotto al TAC e tradotto in un modello.

    In produzione si è visto come «nessun firmware» su un IMEI valido —
    cioè come un buco delle fonti invece che come una funzione mancante.
    """

    def test_un_imei_valido_viene_riconosciuto(self):
        # IMEI con cifra di controllo valida, TAC di un modello noto ai
        # database locali.
        from core import imeicheck

        imei = "867051060315467"
        self.assertTrue(imeicheck.is_valid_imei(imei))
        pagina = self.client.get("/", params={"q": imei}).text
        self.assertIn("IMEI riconosciuto", pagina)
        self.assertIn("86705106", pagina)          # il TAC
        self.assertNotIn("Nessun firmware per «867051060315467»", pagina)

    def test_il_confronto_fra_le_fonti_si_mostra_sempre(self):
        """Anche quando l'IMEI è stato riconosciuto: i database TAC si
        contraddicono, e mostrare una risposta sola come se fosse LA
        risposta fa preparare il test sul telefono sbagliato."""
        pagina = self.client.get("/", params={"q": "867051060315467"}).text
        self.assertIn("Confronto fra le fonti", pagina)
        self.assertIn("Controlla lo stesso IMEI su un'altra fonte", pagina)

    def test_imei_riconosciuto_mostra_il_modello_anche_senza_firmware(self):
        """L'identita' dal TAC non deve sparire se la ricerca firmware e' vuota.

        Il caso segnalato e' il TAC 86120607: la pagina deve dire subito
        realme Note 50, anche quando nessuna fonte firmware ha ancora dati
        da rendere nel resto del risultato.
        """
        pagina = self.client.get("/", params={"q": "861206074094914"}).text
        self.assertIn("IMEI riconosciuto: <strong>Note 50</strong>", pagina)
        self.assertIn("<h2>realme Note 50</h2>", pagina)
        self.assertIn("Versione Android verificata: Android 13", pagina)

    def test_l_imei_non_puo_essere_rinominato_dalla_ricerca_firmware(self):
        """Il TAC Note 50 non deve finire con un titolo C60 nella pagina."""
        type(self).RISPOSTA_RICERCA = staticmethod(lambda q: {
            "items": [{
                "source": "official_lookup", "device_model": "C60",
                "model_code": "RMX3834", "brand": "Oppo / Realme / OnePlus",
                "source_label": "fonte finta",
            }], "error": None})
        pagina = self.client.get("/", params={"q": "861206074094914"}).text
        self.assertIn("<h2>realme Note 50</h2>", pagina)
        self.assertNotIn("<h2>C60</h2>", pagina)

    def test_il_tac_del_galaxy_a16_ha_modello_e_codice(self):
        pagina = self.client.get("/", params={"q": "351355315430630"}).text
        self.assertIn("Galaxy A16 4G", pagina)
        self.assertIn("SM-A165F", pagina)

    def test_il_note_50_usa_la_scheda_curata_senza_catalogo_bulk(self):
        from core import specs

        specs.reset_cache()
        pagina = self.client.get("/", params={"q": "861206074094914"}).text
        self.assertIn("Unisoc Tiger T612", pagina)
        self.assertIn("5000 mAh", pagina)
        self.assertIn("6,74 pollici", pagina)
        self.assertIsNone(specs._schede)

    def test_imei_mantiene_marca_modello_e_android_della_scheda(self):
        """Il codice è una chiave tecnica, non il titolo della pagina."""
        tipo(self).RISPOSTA_RICERCA = staticmethod(lambda q: {
            "items": [{
                "source": "official_lookup", "source_label": "fonte finta",
                "brand": "Samsung", "device_model": "A-16 4G",
                "model_code": "SM-A165F",
            }], "error": None})
        try:
            pagina = self.client.get("/", params={"q": "351355315430630"}).text
            self.assertIn("<h2>Samsung Galaxy A16 4G</h2>", pagina)
            self.assertIn("Versione Android verificata: Android 14", pagina)
            self.assertNotIn("<h2>SM-A165F</h2>", pagina)
        finally:
            type(self).RISPOSTA_RICERCA = staticmethod(
                lambda q: {"items": [], "error": None})

    def test_tac_redmi_mostra_nome_e_scheda_europea(self):
        pagina = self.client.get("/", params={"q": "867207081400866"}).text
        self.assertIn("<h2>Redmi A7 Pro</h2>", pagina)
        self.assertIn("Unisoc T7250", pagina)
        self.assertIn("6000 mAh", pagina)
        self.assertIn("Android 16", pagina)

    def test_un_imei_non_valido_resta_una_ricerca_normale(self):
        """Quindici cifre a caso non superano il controllo di Luhn: non
        vanno trattate come IMEI, o si direbbe «TAC sconosciuto» a chi ha
        semplicemente digitato male."""
        from core import imeicheck

        self.assertFalse(imeicheck.is_valid_imei("111111111111111"))
        pagina = self.client.get("/", params={"q": "111111111111111"}).text
        self.assertNotIn("IMEI riconosciuto", pagina)

    def test_il_tac_sconosciuto_lo_dice_e_offre_la_correzione(self):
        """NON È UN GUASTO, È UN BUCO DI COPERTURA. Sono due cose che si
        vivono allo stesso modo e si risolvono in modi opposti."""
        from core import imeicheck

        # Un IMEI valido con un TAC che nessun database può conoscere: si
        # cerca la cifra di controllo provando le dieci possibili, invece
        # di scriverne uno a memoria che potrebbe non superare Luhn.
        candidato = None
        for cifra in range(10):
            prova = f"99999999000000{cifra}"
            if imeicheck.is_valid_imei(prova):
                candidato = prova
                break
        self.assertIsNotNone(candidato, "nessun IMEI di prova costruibile")
        pagina = self.client.get("/", params={"q": candidato}).text
        self.assertIn("modello sconosciuto", pagina)
        self.assertIn("Correggi o salva tu il modello", pagina)


class TestInterpreteAI(_Sito):
    def setUp(self):
        super().setUp()
        from core import aiquery

        self._chiavi = {v: os.environ.pop(v, None) for v, *_ in aiquery.FORNITORI}
        self._chiama = aiquery._chiama

    def tearDown(self):
        from core import aiquery

        aiquery._chiama = self._chiama
        for variabile, valore in self._chiavi.items():
            if valore is not None:
                os.environ[variabile] = valore

    def test_il_tasto_non_compare_senza_chiave(self):
        """Un pulsante che risponde «non configurato» è un pulsante rotto.

        E con lui non deve partire nemmeno lo script: mandarlo a tutti
        significa far scaricare del codice che non può mai servire.
        """
        pagina = self.client.get("/", params={"q": "xyz9000"}).text
        self.assertNotIn('id="btn-ai"', pagina)
        self.assertNotIn("/static/ai.js", pagina)

    def test_il_tasto_sta_accanto_a_cerca_su_ogni_pagina(self):
        """Non più solo dopo un fallimento: sta nella barra di ricerca, che
        è in ogni pagina. La correzione gratuita dei refusi gira comunque
        per prima e in automatico, quindi il tasto non la scavalca."""
        os.environ["GEMINI_API_KEY"] = "finta"
        for percorso in ("/", "/aggiornamenti", "/diagnostica"):
            with self.subTest(percorso=percorso):
                pagina = self.client.get(percorso).text
                self.assertIn('id="btn-ai"', pagina)
                self.assertIn("/static/ai.js", pagina)

    def test_lo_script_dell_ai_si_scarica(self):
        os.environ["GEMINI_API_KEY"] = "finta"
        risposta = self.client.get("/static/ai.js")
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("/api/interpreta", risposta.text)

    def test_la_rotta_restituisce_solo_voci_dei_cataloghi(self):
        """IL VINCOLO CHE CONTA. Quello che il modello propone viene
        ricontrollato contro i nostri cataloghi: un modello inventato non
        deve poter uscire da questa rotta."""
        import json

        from core import aiquery

        os.environ["GEMINI_API_KEY"] = "finta"
        aiquery._chiama = lambda domanda: json.dumps(
            {"scelte": ["SM-A075F", "SM-Z999X Inventato"], "motivo": "ok"})
        # «sma075f» — il codice copiato male — è la forma che fa entrare
        # SM-A075F fra i candidati. Con una ricerca per nome i candidati
        # sarebbero nomi commerciali, e un codice non ci sarebbe: il
        # filtro lo scarterebbe, giustamente.
        risposta = self.client.post("/api/interpreta", data={"q": "sma075f"})
        dati = risposta.json()
        self.assertIn("SM-A075F", dati["proposte"])
        self.assertNotIn("SM-Z999X Inventato", dati["proposte"])
        self.assertEqual(dati["scartate"], ["SM-Z999X Inventato"])

    def test_senza_chiave_la_rotta_risponde_senza_esplodere(self):
        """Senza chiave l'AI non può interpretare niente — ma la rotta non
        deve rispondere PEGGIO di «Cerca» sullo stesso testo: si ripiega
        sul testo digitato invece di un vicolo cieco, e il motivo per cui
        l'AI non ha aiutato resta scritto, onestamente, nella spiegazione."""
        dati = self.client.post("/api/interpreta", data={"q": "a07"}).json()
        self.assertEqual(dati["proposte"], ["a07"])
        self.assertIsNone(dati["errore"])
        self.assertIn("chiave", dati["motivo"])

    def test_un_imei_non_passa_dal_modello(self):
        """Quindici cifre non somigliano a nessun nome di catalogo: prima
        finivano nell'elenco dei candidati (vuoto) e la rotta rispondeva
        «nessun candidato da sottoporre al modello» — peggio di «Cerca»,
        che un IMEI lo riconosce da sempre. Qui si passa il numero così
        com'è, senza nemmeno interrogare il modello."""
        imei = "356938035643809"
        dati = self.client.post("/api/interpreta", data={"q": imei}).json()
        self.assertEqual(dati["proposte"], [imei])
        self.assertIsNone(dati["errore"])

    def test_nessuna_corrispondenza_ripiega_sul_testo_digitato(self):
        """Anche con la chiave attiva, se l'AI non trova corrispondenze
        utili la ricerca deve comunque partire — sullo stesso testo che
        «Cerca» avrebbe usato — invece di fermarsi su un messaggio
        d'errore nel pannello AI."""
        import json

        from core import aiquery

        os.environ["GEMINI_API_KEY"] = "finta"
        aiquery._chiama = lambda domanda: json.dumps(
            {"scelte": [], "motivo": "non riconosco nessun modello"})
        dati = self.client.post("/api/interpreta", data={"q": "xyzxyz"}).json()
        self.assertEqual(dati["proposte"], ["xyzxyz"])
        self.assertIsNone(dati["errore"])


class TestParcoDiTest(_Sito):
    def test_aggiungere_e_togliere(self):
        from core import storage

        chiave = next(d["device_key"] for d in storage.get_devices()
                      if "S24" in d["model"])
        self.client.post("/parco/aggiungi",
                         data={"chiave": chiave, "brand": "Samsung",
                               "modello": "Galaxy S24"},
                         follow_redirects=False)
        self.assertIn(chiave, storage.watched_keys())
        self.assertIn("Galaxy S24", self.client.get("/parco").text)

        self.client.post("/parco/togli", data={"chiave": chiave},
                         follow_redirects=False)
        self.assertNotIn(chiave, storage.watched_keys())


class TestControlliDiSalute(_Sito):
    """IL DIFETTO CHE HA FATTO RIAVVIARE IL SERVIZIO IN CICLO.

    Gli host controllano che il servizio sia vivo con una richiesta
    `HEAD`. FastAPI, a differenza di Starlette sotto di lui, **non**
    aggiunge `HEAD` da solo a una rotta dichiarata `GET`: risponde 405,
    l'host lo legge come «non risponde» e riavvia il container. Ogni
    pochi minuti, all'infinito.

    La parte insidiosa è che non c'è nessun errore da cercare: le pagine
    rispondono 200, i registri sono puliti, e da fuori si vede solo un
    sito che ogni tanto è lento. Nei registri di produzione era una riga
    sola in mezzo alle altre.
    """

    def test_head_sulla_radice(self):
        self.assertEqual(self.client.head("/").status_code, 200)

    def test_head_su_health(self):
        self.assertEqual(self.client.head("/health").status_code, 200)

    def test_head_non_disegna_la_pagina(self):
        """`HEAD` chiede solo se il servizio è vivo: costruire l'elenco
        dei dispositivi per poi buttarlo via sarebbe una scansione del
        database ogni pochi minuti, per sempre."""
        risposta = self.client.head("/")
        self.assertEqual(risposta.text, "")


class TestSaluteLeggera(_Sito):
    def test_il_controllo_di_salute_non_tocca_l_archivio(self):
        """Un controllo che interroga il database ogni cinque minuti è un
        carico costante, e fallirebbe proprio mentre l'archivio è in
        riparazione — cioè quando l'host NON deve riavviare il servizio."""
        from core import storage

        vera = storage.connect

        def vietata(*args, **kwargs):
            raise AssertionError("/health ha aperto il database")

        storage.connect = vietata
        try:
            self.assertEqual(self.client.get("/health").status_code, 200)
        finally:
            storage.connect = vera


if __name__ == "__main__":
    unittest.main()


class TestMemoria(unittest.TestCase):
    """I due cataloghi grandi non devono tornare a tenersi tutto in chiaro.

    IL GUASTO CHE QUESTO TEST FERMA: su un host da 512 MB il servizio è
    stato riavviato d'ufficio per superamento della memoria. Le due voci
    più grosse erano le sezioni complete di 4766 schede tenute in chiaro
    (45 MB perenni per un pannello che si apre di rado) e un CSV da 12 MB
    che veniva tenuto in archivio e ricaricato in tre copie vive insieme.

    Nessuna delle due dava un errore: davano un numero che cresceva.
    """

    def test_le_sezioni_stanno_compresse(self):
        from core import specs

        with open(os.path.join(_FIXTURES, "specs_devices.tar.gz"), "rb") as f:
            schede = specs.leggi_archivio(f.read())
        for riga in schede:
            with self.subTest(scheda=riga["nome"]):
                self.assertNotIn("sezioni", riga,
                                 "le sezioni in chiaro sono tornate in memoria")
        specs.carica_da(schede, "fixture")
        try:
            scheda = specs.per_codice("SM-A075F")
            # Compresse sì, ma leggibili: il pannello deve continuare a
            # funzionare, altrimenti si è risparmiata memoria togliendo una
            # funzione invece che una spesa.
            self.assertIn("Platform", scheda.sezioni)
            self.assertIn("Chipset", scheda.sezioni["Platform"])
        finally:
            specs.reset_cache()

    def test_l_indice_dei_processori_si_serializza_in_poco(self):
        """L'indice compresso deve pesare kilobyte, non megabyte: è ciò
        che sostituisce il CSV sia in archivio sia nel salvataggio."""
        from core import soc

        indice = {f"MODELLO {i}": soc.Soc(nome="Snapdragon 8 Gen 3",
                                          produttore="Qualcomm",
                                          fonte="prova")
                  for i in range(2000)}
        compresso = soc._indice_a_json(indice)
        self.assertLess(len(compresso), 200_000)
        # E si deve poter rileggere identico, o la cache sarebbe una
        # perdita di dati silenziosa.
        riletto = soc._indice_da_json(compresso)
        self.assertEqual(len(riletto), 2000)
        self.assertEqual(riletto["MODELLO 7"].nome, "Snapdragon 8 Gen 3")
        self.assertEqual(riletto["MODELLO 7"].produttore, "Qualcomm")


class TestDockerfile(unittest.TestCase):
    """Il Dockerfile si collauda solo al deploy, quindi qui.

    Un `#` dentro una continuazione con la barra rovesciata NON è un
    commento: è parte del valore. Una `ENV` scritta così crea variabili
    d'ambiente che si chiamano «# DUE» e il container parte sbagliato — o
    non parte. Il ciclo per accorgersene è: commit, push, attesa della
    build, log.
    """

    RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_nessun_commento_dentro_una_continuazione(self):
        percorso = os.path.join(self.RADICE, "Dockerfile")
        if not os.path.exists(percorso):
            self.skipTest("Dockerfile assente")
        with open(percorso, encoding="utf-8") as f:
            righe = f.read().splitlines()
        continua = False
        for numero, riga in enumerate(righe, start=1):
            if continua and riga.strip().startswith("#"):
                self.fail(f"riga {numero}: commento dentro una continuazione "
                          f"— finirebbe nel valore dell'istruzione")
            continua = riga.rstrip().endswith("\\")


class TestIlTastoAiCerca(_Sito):
    """Il tasto AI deve DARE IL RISULTATO, non un elenco di link.

    Segnalazione: «ho cercato samsung s23 ma mi ha detto forse cercavi
    s23 plus o ultra. deve funzionare come la ricerca normale
    potenziata». Aveva ragione: il tasto restituiva delle proposte da
    cliccare, cioè faceva scegliere all'utente il lavoro per cui aveva
    premuto il tasto.

    Ora la pagina del risultato accetta l'interpretazione e la dichiara:
    che cosa era stato scritto, che cosa è stato cercato al posto suo, e
    le alternative a un clic.
    """

    def test_la_pagina_dice_cosa_ha_interpretato(self):
        pagina = self.client.get("/", params={
            "q": "Galaxy A07", "ai": "quel samsung nero",
            "alt": ["Galaxy A05"], "perche": "un Samsung della serie A"}).text
        self.assertIn("quel samsung nero", pagina)
        self.assertIn("un Samsung della serie A", pagina)
        self.assertIn("Galaxy A05", pagina)

    def test_senza_interpretazione_non_compare_nulla(self):
        """Una ricerca normale non deve portarsi dietro il riquadro
        dell'AI: chi ha digitato il nome sa già cosa ha cercato."""
        pagina = self.client.get("/", params={"q": "Galaxy A07"}).text
        self.assertNotIn("ho cercato", pagina)

    def test_lo_script_manda_alla_ricerca_invece_di_disegnare_link(self):
        """La prova sul comportamento sta nel file servito: se tornasse
        a costruire un elenco di `<a class="proposta">` il tasto
        ricomincerebbe a far scegliere invece di cercare."""
        script = self.client.get("/static/ai.js").text
        self.assertIn("window.location", script)
        self.assertNotIn('class="proposta"', script)

    def test_l_attesa_e_una_rotellina_non_una_frase(self):
        script = self.client.get("/static/ai.js").text
        self.assertIn("rotella", script)
        foglio = self.client.get("/static/style.css").text
        self.assertIn("@keyframes gira", foglio)
