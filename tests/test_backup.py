"""Test della persistenza dell'archivio fra i riavvii.

Attenzione particolare ai casi in cui si può PERDERE lavoro: sovrascrivere
un database popolato con una copia più vecchia, o scrivere un file
troncato. In un tracker che serve a rispondere «cosa è cambiato dall'ultima
volta», la perdita dello storico è il danno peggiore possibile — peggio di
un'app che non parte, perché non si nota subito.
"""
import base64
import gzip
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3  # noqa: E402

from core import backup, config as C, storage  # noqa: E402


class FintaRisposta:
    def __init__(self, status=200, payload=None, contenuto=b"", testo=""):
        self.status_code = status
        self._payload = payload
        self.content = contenuto
        self.text = testo or ""

    def json(self):
        if self._payload is None:
            raise ValueError("non JSON")
        return self._payload


class BaseBackup(unittest.TestCase):
    """Base con ripristino COMPLETO dello stato globale.

    `C.DB_PATH` è una variabile di modulo condivisa da tutta la suite, e
    questi test la puntano di proposito su file che NON sono database (per
    verificare il salvataggio di byte grezzi). Lasciandola lì, i file di
    test successivi ereditavano quel percorso e fallivano con «file is not
    a database» — un guasto che sembrava loro e non era loro.

    Allo stesso modo va chiusa la connessione: `backup.salva()` ne apre una
    su `C.DB_PATH` per produrre l'istantanea, e su Windows un file con un
    descrittore aperto non si può cancellare (`WinError 32`). Il tearDown
    falliva, e con lui saltava anche il ripristino del percorso.
    """

    def setUp(self):
        self._db_originale = C.DB_PATH
        self._env_originale = os.environ.get("TRACKER_DB")
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        os.environ["TRACKER_DB"] = self._db
        for chiave in ("BACKUP_GIST_ID", "BACKUP_GITHUB_TOKEN", "BACKUP_URL"):
            os.environ.pop(chiave, None)
        self._requests_originale = backup.requests

    def tearDown(self):
        backup.requests = self._requests_originale
        for chiave in ("BACKUP_GIST_ID", "BACKUP_GITHUB_TOKEN", "BACKUP_URL"):
            os.environ.pop(chiave, None)
        storage.reset_state()
        for coda in ("", "-wal", "-shm", "-journal", ".snapshot", ".tmp"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale
        if self._env_originale is None:
            os.environ.pop("TRACKER_DB", None)
        else:
            os.environ["TRACKER_DB"] = self._env_originale

    def _scrivi_db(self, contenuto=None):
        """Mette sul disco un database VERO, con dentro qualcosa.

        Prima qui si scriveva una stringa ripetuta, come segnaposto. Era una
        scorciatoia che ha finito per difendere il difetto peggiore del
        modulo: `salva()` caricava qualunque byte trovasse nel file, quindi
        anche una copia che non è un database — ed è così che un archivio
        esterno guasto si crea. Da quando il salvataggio controlla ciò che
        carica, il segnaposto non passa più, e giustamente.

        `contenuto` esplicito resta possibile per i test che vogliono
        proprio dei byte arbitrari.
        """
        if contenuto is not None:
            with open(self._db, "wb") as f:
                f.write(contenuto)
            return contenuto
        storage.reset_state()
        storage.init_db()
        storage.set_meta("prova", "contenuto del database")
        storage.add_to_watchlist("samsung|s24", "Samsung", "Galaxy S24")
        storage.reset_state()
        with open(self._db, "rb") as f:
            return f.read()


class TestConfigurazione(BaseBackup):
    def test_inerte_senza_configurazione(self):
        """Senza archivio configurato il modulo non deve fare nulla: chi non
        lo usa non deve subirne effetti."""
        self.assertFalse(backup.configurato())
        ok, messaggio = backup.salva()
        self.assertFalse(ok)
        self.assertIn("nessun archivio", messaggio)

    def test_riconosce_configurazione_gist(self):
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"
        self.assertTrue(backup.configurato())

    def test_riconosce_configurazione_url(self):
        os.environ["BACKUP_URL"] = "https://archivio.test/db"
        self.assertTrue(backup.configurato())

    def test_gist_incompleto_non_e_configurazione(self):
        """Un id senza token non basta: meglio comportarsi come non
        configurato che fallire a ogni scansione."""
        os.environ["BACKUP_GIST_ID"] = "abc123"
        self.assertFalse(backup.configurato())


class TestSalvataggio(BaseBackup):
    def test_salva_su_gist_comprimendo(self):
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"
        contenuto = self._scrivi_db()
        inviato = {}

        class FinteRichieste:
            @staticmethod
            def patch(url, headers=None, json=None, timeout=None):
                inviato["json"] = json
                return FintaRisposta(200)

        backup.requests = FinteRichieste
        ok, messaggio = backup.salva()

        self.assertTrue(ok, messaggio)
        caricato = inviato["json"]["files"]["tracker-db.sqlite.gz"]["content"]
        # SI VERIFICA IL CONTENUTO, NON I BYTE. L'istantanea è prodotta da
        # `VACUUM INTO`, che riorganizza le pagine: confrontarla byte a
        # byte con il file su disco fallirebbe pur essendo tutto corretto —
        # e il confronto giusto è comunque un altro, cioè che quello che si
        # carica sia un database leggibile con dentro gli stessi dati.
        ricostruito = gzip.decompress(base64.b64decode(caricato))
        prova = self._db + ".ricostruito"
        with open(prova, "wb") as f:
            f.write(ricostruito)
        try:
            self.assertIsNone(storage.integrita_file(prova),
                              "è stato caricato qualcosa che non è un database")
            conn = sqlite3.connect(prova)
            righe = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
            conn.close()
            self.assertEqual(righe, 1, "il salvataggio ha perso i dati")
        finally:
            os.remove(prova)
        self.assertLess(len(caricato), len(contenuto),
                        "la compressione non ha ridotto la dimensione")

    def test_database_inesistente_non_salva(self):
        os.environ["BACKUP_URL"] = "https://archivio.test/db"
        ok, messaggio = backup.salva()
        self.assertFalse(ok)
        self.assertIn("non ancora creato", messaggio)

    def test_errore_di_rete_riportato_non_sollevato(self):
        """Un archivio irraggiungibile non deve far fallire una scansione
        andata a buon fine: l'errore si riporta, non si propaga."""
        os.environ["BACKUP_URL"] = "https://archivio.test/db"
        self._scrivi_db()

        class FinteRichieste:
            @staticmethod
            def put(*args, **kwargs):
                raise ConnectionError("rete assente")

        backup.requests = FinteRichieste
        ok, messaggio = backup.salva()
        self.assertFalse(ok)
        self.assertIn("connessione fallita", messaggio)


class TestRipristino(BaseBackup):
    def _gist_con(self, contenuto: bytes):
        compresso = base64.b64encode(gzip.compress(contenuto)).decode()

        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                return FintaRisposta(200, payload={
                    "files": {"tracker-db.sqlite.gz": {"content": compresso}}
                })

        return FinteRichieste

    def test_ripristina_quando_il_database_manca(self):
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"
        # UN DATABASE VERO, non byte qualsiasi: il ripristino ora rifiuta
        # di installare una copia che non è leggibile, ed è la correzione
        # che impedisce a un archivio esterno guasto di rimettersi al suo
        # posto a ogni avvio.
        atteso = self._scrivi_db()
        os.remove(self._db)
        backup.requests = self._gist_con(atteso)

        ok, messaggio = backup.ripristina()
        self.assertTrue(ok, messaggio)
        with open(self._db, "rb") as f:
            self.assertEqual(f.read(), atteso)

    def test_non_sovrascrive_un_database_gia_popolato(self):
        """IL CASO PIÙ PERICOLOSO. Ripristinare sopra un database locale
        già pieno significherebbe sostituire dati recenti con una copia più
        vecchia: si perde lavoro senza accorgersene."""
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"
        locale = self._scrivi_db(b"dati locali recenti" * 500)
        backup.requests = self._gist_con(b"copia vecchia" * 300)

        ok, messaggio = backup.ripristina(solo_se_mancante=True)
        self.assertFalse(ok)
        self.assertIn("già presente", messaggio)
        with open(self._db, "rb") as f:
            self.assertEqual(f.read(), locale, "il database locale è stato sovrascritto")

    def test_forzare_il_ripristino_e_possibile(self):
        """Deve restare possibile farlo apposta, ma solo esplicitamente."""
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"
        atteso = self._scrivi_db()          # un database vero, dall'archivio
        self._scrivi_db(b"dati locali" * 500)   # e uno diverso in locale
        backup.requests = self._gist_con(atteso)

        ok, messaggio = backup.ripristina(solo_se_mancante=False)
        self.assertTrue(ok, messaggio)
        with open(self._db, "rb") as f:
            self.assertEqual(f.read(), atteso)

    def test_forzare_non_basta_a_installare_una_copia_guasta(self):
        """Il «forza» salta il controllo sul database LOCALE, non quello
        sulla copia che arriva: installare una copia illeggibile non è mai
        ciò che qualcuno intendeva chiedere."""
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"
        locale = self._scrivi_db()
        backup.requests = self._gist_con(b"non e' un database" * 300)

        ok, messaggio = backup.ripristina(solo_se_mancante=False)
        self.assertFalse(ok)
        self.assertIn("danneggiato", messaggio)
        with open(self._db, "rb") as f:
            self.assertEqual(f.read(), locale, "il database locale è stato perso")

    def test_archivio_vuoto_gestito(self):
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"

        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                return FintaRisposta(200, payload={"files": {}})

        backup.requests = FinteRichieste
        ok, messaggio = backup.ripristina()
        self.assertFalse(ok)
        self.assertIn("nessun salvataggio", messaggio)

    def test_contenuto_corrotto_non_scrive_il_database(self):
        """Meglio nessun database che uno corrotto: il secondo non si nota
        subito e rompe tutto a valle."""
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"

        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                return FintaRisposta(200, payload={
                    "files": {"tracker-db.sqlite.gz": {
                        "content": base64.b64encode(b"non e' un gzip").decode()}}
                })

        backup.requests = FinteRichieste
        ok, messaggio = backup.ripristina()
        self.assertFalse(ok)
        self.assertIn("non decomprimibile", messaggio)
        self.assertFalse(os.path.exists(self._db),
                         "un contenuto corrotto non deve creare il file")

    def test_nessun_file_temporaneo_lasciato(self):
        """La scrittura è atomica: non deve restare spazzatura sul disco."""
        os.environ["BACKUP_GIST_ID"] = "abc123"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token"
        backup.requests = self._gist_con(b"contenuto" * 300)
        backup.ripristina()
        self.assertFalse(os.path.exists(self._db + ".tmp"))


class TestSalvataggioPeriodico(BaseBackup):
    def test_primo_salvataggio_avviene_subito(self):
        """Con un contatore azzerato il primo salvataggio verrebbe scambiato
        per «appena fatto» e saltato: il primissimo dopo l'avvio non
        avverrebbe mai, e un riavvio poco dopo perderebbe tutto."""
        os.environ["BACKUP_URL"] = "https://archivio.test/db"
        self._scrivi_db()
        chiamate = {"n": 0}

        class FinteRichieste:
            @staticmethod
            def put(*args, **kwargs):
                chiamate["n"] += 1
                return FintaRisposta(200)

        backup.requests = FinteRichieste
        backup._ultimo_tentativo = None
        backup.salva_se_serve(intervallo_minuti=30)
        self.assertEqual(chiamate["n"], 1)

    def test_non_salva_a_ogni_scansione(self):
        """Senza un intervallo minimo si caricherebbe l'intero database a
        ogni giro, sprecando banda e consumando il limite dell'archivio."""
        os.environ["BACKUP_URL"] = "https://archivio.test/db"
        self._scrivi_db()
        chiamate = {"n": 0}

        class FinteRichieste:
            @staticmethod
            def put(*args, **kwargs):
                chiamate["n"] += 1
                return FintaRisposta(200)

        backup.requests = FinteRichieste
        backup._ultimo_tentativo = None
        backup.salva_se_serve(intervallo_minuti=30)
        backup.salva_se_serve(intervallo_minuti=30)
        backup.salva_se_serve(intervallo_minuti=30)
        self.assertEqual(chiamate["n"], 1, "ha salvato più volte di quanto dovuto")

    def test_inerte_se_non_configurato(self):
        backup._ultimo_tentativo = None
        backup.salva_se_serve()  # non deve sollevare nulla


class TestPreparazioneAssistita(BaseBackup):
    """Creazione dell'archivio e verifica, per ridurre i passaggi manuali.

    La configurazione a mano richiedeva di creare un Gist, copiarne
    l'identificativo dall'indirizzo e incollarlo altrove: tre occasioni di
    sbagliare per un'operazione che si fa una volta sola. Qui l'app crea
    l'archivio da sé, e verifica con una scrittura vera che funzioni."""

    def test_token_valido_riconosciuto(self):
        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                risposta = FintaRisposta(200, payload={"login": "tizio"})
                risposta.headers = {"x-oauth-scopes": "gist, repo"}
                return risposta

        backup.requests = FinteRichieste
        ok, messaggio = backup.verifica_token("ghp_valido")
        self.assertTrue(ok)
        self.assertIn("tizio", messaggio)

    def test_token_senza_permesso_gist_rifiutato(self):
        """Va detto subito: altrimenti l'errore emergerebbe molto più
        avanti, in una forma difficile da ricondurre alla causa."""
        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                risposta = FintaRisposta(200, payload={"login": "tizio"})
                risposta.headers = {"x-oauth-scopes": "repo"}
                return risposta

        backup.requests = FinteRichieste
        ok, messaggio = backup.verifica_token("ghp_senza_gist")
        self.assertFalse(ok)
        self.assertIn("gist", messaggio)

    def test_token_non_valido_riconosciuto(self):
        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                risposta = FintaRisposta(401)
                risposta.headers = {}
                return risposta

        backup.requests = FinteRichieste
        ok, messaggio = backup.verifica_token("ghp_scaduto")
        self.assertFalse(ok)
        self.assertIn("non valido", messaggio)

    def test_token_fine_grained_accettato(self):
        """I token «fine-grained» non dichiarano i permessi in
        un'intestazione: l'assenza non deve essere scambiata per mancanza
        di autorizzazione."""
        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                risposta = FintaRisposta(200, payload={"login": "tizio"})
                risposta.headers = {}
                return risposta

        backup.requests = FinteRichieste
        ok, _ = backup.verifica_token("github_pat_moderno")
        self.assertTrue(ok)

    def test_crea_archivio_privato(self):
        creato = {}

        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                risposta = FintaRisposta(200, payload={"login": "tizio"})
                risposta.headers = {"x-oauth-scopes": "gist"}
                return risposta

            @staticmethod
            def post(url, headers=None, json=None, timeout=None):
                creato.update(json)
                return FintaRisposta(201, payload={"id": "abc123def"})

        backup.requests = FinteRichieste
        ok, _, identificativo = backup.crea_archivio("ghp_valido")
        self.assertTrue(ok)
        self.assertEqual(identificativo, "abc123def")
        self.assertFalse(creato["public"], "l'archivio non deve essere pubblico")

    def test_non_crea_con_token_invalido(self):
        class FinteRichieste:
            @staticmethod
            def get(url, headers=None, timeout=None):
                risposta = FintaRisposta(401)
                risposta.headers = {}
                return risposta

        backup.requests = FinteRichieste
        ok, _, identificativo = backup.crea_archivio("ghp_scaduto")
        self.assertFalse(ok)
        self.assertIsNone(identificativo)

    def test_prova_completa_scrive_e_rilegge(self):
        """Verificare con una scrittura vera è l'unico modo per sapere che
        funzionerà quando servirà: un problema di permessi si scoprirebbe
        altrimenti solo al primo riavvio, cioè a dati già persi."""
        archivio = {}

        class FinteRichieste:
            @staticmethod
            def patch(url, headers=None, json=None, timeout=None):
                archivio.update(json["files"])
                return FintaRisposta(200)

            @staticmethod
            def get(url, headers=None, timeout=None):
                return FintaRisposta(200, payload={"files": archivio})

        backup.requests = FinteRichieste
        ok, messaggio = backup.prova_completa("abc123", "ghp_valido")
        self.assertTrue(ok, messaggio)

    def test_prova_rileva_permessi_insufficienti(self):
        class FinteRichieste:
            @staticmethod
            def patch(url, headers=None, json=None, timeout=None):
                return FintaRisposta(404)

        backup.requests = FinteRichieste
        ok, messaggio = backup.prova_completa("abc123", "ghp_senza_permessi")
        self.assertFalse(ok)
        self.assertIn("gist", messaggio)


if __name__ == "__main__":
    unittest.main(verbosity=2)
