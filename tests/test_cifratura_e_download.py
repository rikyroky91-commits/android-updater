"""Cifratura del salvataggio esterno, e le copie scaricabili.

PERCHE' LA CIFRATURA. L'unica copia duratura del progetto e' un Gist, e
un Gist «secret» NON e' privato: e' non elencato. Chiunque ne conosca
l'indirizzo lo apre senza autenticarsi. Da quando quel database contiene
email e hash delle password degli account del parco di test, la
segretezza di un URL non e' una difesa sufficiente.

PERCHE' IL DOWNLOAD. Fino a oggi quella copia duratura stava su un
servizio solo, con un token solo. Poterne tenere una sul proprio computer
e' la differenza fra un guasto e una perdita.
"""
import gzip
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AVVIA_WORKER"] = "0"

from core import cifratura  # noqa: E402


class TestCifratura(unittest.TestCase):
    def setUp(self):
        self._prima = os.environ.get("BACKUP_ENCRYPTION_KEY")
        os.environ["BACKUP_ENCRYPTION_KEY"] = "passphrase-di-collaudo"

    def tearDown(self):
        if self._prima is None:
            os.environ.pop("BACKUP_ENCRYPTION_KEY", None)
        else:
            os.environ["BACKUP_ENCRYPTION_KEY"] = self._prima

    def test_il_giro_completo_restituisce_lo_stesso_archivio(self):
        originale = b"SQLite format 3\x00" + b"contenuto" * 500
        cifrato, errore = cifratura.cifra(originale)
        self.assertEqual(errore, "")
        tornato, errore = cifratura.decifra(cifrato)
        self.assertEqual(errore, "")
        self.assertEqual(tornato, originale)

    def test_il_contenuto_in_chiaro_non_si_legge(self):
        """E' l'unica cosa che questo modulo deve garantire."""
        cifrato, _ = cifratura.cifra(b"scrypt$16384$8$1$sale$hash-di-password")
        self.assertNotIn(b"scrypt", cifrato)
        self.assertNotIn(b"hash-di-password", cifrato)

    def test_due_cifrature_dello_stesso_archivio_sono_diverse(self):
        """Sale e nonce casuali: due salvataggi identici non devono
        essere riconoscibili come tali da chi guarda il Gist."""
        uno, _ = cifratura.cifra(b"stesso contenuto")
        due, _ = cifratura.cifra(b"stesso contenuto")
        self.assertNotEqual(uno, due)

    def test_un_archivio_non_cifrato_passa_immutato(self):
        """I salvataggi fatti prima che la cifratura esistesse devono
        continuare a ripristinarsi: e' l'intestazione a distinguerli."""
        vecchio = b"\x1f\x8b\x08 un gzip qualunque"
        tornato, errore = cifratura.decifra(vecchio)
        self.assertEqual(errore, "")
        self.assertEqual(tornato, vecchio)

    def test_la_chiave_sbagliata_non_produce_spazzatura_plausibile(self):
        """AES-GCM autentica: meglio un errore dichiarato che un database
        di byte casuali scritto sopra quello buono."""
        cifrato, _ = cifratura.cifra(b"contenuto vero")
        os.environ["BACKUP_ENCRYPTION_KEY"] = "una passphrase diversa"
        tornato, errore = cifratura.decifra(cifrato)
        self.assertIsNone(tornato)
        self.assertIn("non decifrabile", errore)

    def test_senza_chiave_un_archivio_cifrato_lo_dice(self):
        cifrato, _ = cifratura.cifra(b"contenuto")
        os.environ.pop("BACKUP_ENCRYPTION_KEY", None)
        tornato, errore = cifratura.decifra(cifrato)
        self.assertIsNone(tornato)
        # Il messaggio deve NOMINARE la variabile che manca: chi lo legge
        # sta cercando di capire perche' il ripristino non parte.
        self.assertIn("BACKUP_ENCRYPTION_KEY", errore)

    def test_la_diagnostica_distingue_i_due_stati(self):
        self.assertIn("attiva", cifratura.stato())
        os.environ.pop("BACKUP_ENCRYPTION_KEY", None)
        self.assertIn("non attiva", cifratura.stato())


class TestDownloadSoloAdmin(unittest.TestCase):
    """Il primo file contiene l'archivio INTERO: email e hash delle
    password di tutti. Non e' un'esportazione «dei propri dati», e' quella
    dei dati di tutti — quindi solo l'amministratore."""

    @classmethod
    def setUpClass(cls):
        cartella = tempfile.mkdtemp(prefix="download-")
        os.environ["DB_PATH"] = os.path.join(cartella, "test.db")
        os.environ["ADMIN_USERNAME"] = "capo"
        os.environ["ADMIN_EMAIL"] = "capo@example.com"
        os.environ["ADMIN_PASSWORD"] = "password-di-collaudo-lunga"

        from core import auth, config as C, storage

        C.DB_PATH = os.environ["DB_PATH"]
        C.COOKIE_SECURE = False
        storage.reset_state()
        storage.init_db()
        storage.add_to_watchlist("samsung|galaxy-s24", "Samsung", "Galaxy S24")
        storage.imposta_nota_parco("samsung|galaxy-s24", "una nota\ncon un a capo")
        storage.crea_utente("normale", "normale@example.com",
                            auth.hash_password("password-normale-lunga"),
                            stato=storage.STATO_APPROVATO)

        from fastapi.testclient import TestClient

        from web import account
        from web.main import app

        account.assicura_admin()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        for chiave in ("ADMIN_USERNAME", "ADMIN_EMAIL", "ADMIN_PASSWORD"):
            os.environ.pop(chiave, None)

    def _accedi(self, username, password):
        self.client.cookies.clear()
        self.client.get("/login")
        self.client.post("/login", data={
            "username": username, "password": password, "next": "/parco",
            "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)

    def test_lanonimo_non_scarica_niente(self):
        self.client.cookies.clear()
        for percorso in ("/admin/backup", "/admin/parco.csv"):
            with self.subTest(percorso=percorso):
                r = self.client.get(percorso, follow_redirects=False)
                self.assertEqual(r.status_code, 303)
                self.assertIn("/login", r.headers["location"])

    def test_un_account_normale_non_scarica_niente(self):
        """Approvato e collegato, ma non amministratore: quei file non
        contengono i suoi dati, contengono quelli di tutti."""
        self._accedi("normale", "password-normale-lunga")
        for percorso in ("/admin/backup", "/admin/parco.csv"):
            with self.subTest(percorso=percorso):
                r = self.client.get(percorso, follow_redirects=False)
                self.assertEqual(r.status_code, 303)
                self.assertEqual(r.headers["location"], "/parco")

    def test_lamministratore_scarica_larchivio(self):
        self._accedi("capo", "password-di-collaudo-lunga")
        r = self.client.get("/admin/backup")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["content-disposition"])
        # Dev'essere un database vero, non una pagina di errore.
        self.assertTrue(gzip.decompress(r.content).startswith(b"SQLite format 3"))

    def test_lamministratore_scarica_il_parco_in_csv(self):
        self._accedi("capo", "password-di-collaudo-lunga")
        r = self.client.get("/admin/parco.csv")
        self.assertEqual(r.status_code, 200)
        testo = r.content.decode("utf-8")
        self.assertTrue(testo.startswith("﻿"), "manca il BOM per Excel")
        self.assertIn("Galaxy S24", testo)
        # Un a capo dentro una nota spezzerebbe la riga del CSV.
        righe = [riga for riga in testo.splitlines() if riga.strip()]
        self.assertEqual(len(righe), 2, f"il CSV ha righe di troppo: {righe}")


if __name__ == "__main__":
    unittest.main()


class TestUnBackupNonSovrascriveIlPienoColVuoto(unittest.TestCase):
    """«il parco test è vuoto, settimane fa era pieno di roba, come si è
    perso tutto?», 07/09/2026.

    La catena che porta lì, e il pezzo grave è l'ultimo:

    1. il contenitore riparte — su Render `/tmp` si azzera a ogni deploy,
       a ogni riavvio per memoria, a ogni risveglio dopo il sonno;
    2. l'avvio prova `ripristina()`, l'unica cosa che rimette i dati;
    3. se quel ripristino NON riesce l'app parte VUOTA;
    4. mezz'ora dopo il salvataggio periodico carica nel Gist il database
       vuoto, e la copia buona non è più l'ultima.

    Il passo 4 è il difetto, e non è un caso limite: è il funzionamento
    normale applicato a una situazione anormale. Nessuno se ne accorge,
    perché ogni singolo salvataggio «riesce».
    """

    def setUp(self):
        from core import backup

        self.backup = backup
        self._dimensione = backup._dimensione_remota
        self.addCleanup(lambda: setattr(backup, "_dimensione_remota",
                                        self._dimensione))

    def _remoto(self, byte, nota=""):
        self.backup._dimensione_remota = lambda: (byte, nota)

    def test_un_crollo_ferma_il_salvataggio(self):
        """Un archivio vuoto contro uno pieno: è il caso reale."""
        self._remoto(2_000_000)
        motivo = self.backup._crollo_sospetto(30_000)
        self.assertIn("ANNULLATO", motivo)
        self.assertIn("Diagnostica", motivo)

    def test_una_crescita_normale_passa(self):
        self._remoto(1_000_000)
        self.assertEqual(self.backup._crollo_sospetto(900_000), "")

    def test_una_riduzione_moderata_passa(self):
        """La potatura degli aggiornamenti vecchi fa rimpicciolire
        l'archivio per motivi legittimi: una guardia che scatta sul
        rumore verrebbe disattivata dopo il secondo falso allarme."""
        self._remoto(1_000_000)
        self.assertEqual(self.backup._crollo_sospetto(600_000), "")

    def test_il_primo_salvataggio_non_e_un_crollo(self):
        """Un archivio remoto minuscolo è un primo salvataggio, non una
        copia da proteggere."""
        self._remoto(0)
        self.assertEqual(self.backup._crollo_sospetto(10), "")
        self._remoto(1_000)
        self.assertEqual(self.backup._crollo_sospetto(10), "")

    def test_se_non_si_legge_il_precedente_non_si_blocca(self):
        """Bloccare un salvataggio perché non si è riusciti a leggere il
        precedente vorrebbe dire smettere di salvare proprio quando la
        rete è incerta."""
        self._remoto(0, "dimensione precedente non leggibile (HTTP 502)")
        self.assertEqual(self.backup._crollo_sospetto(10), "")

    def test_il_messaggio_dice_la_via_d_uscita(self):
        """Una guardia senza via d'uscita si finisce per toglierla."""
        self._remoto(2_000_000)
        self.assertIn("Salva adesso", self.backup._crollo_sospetto(30_000))

    def test_forza_passa_oltre(self):
        """La via d'uscita è un gesto esplicito di una persona, non il
        comportamento automatico di ogni mezz'ora."""
        import inspect

        firma = inspect.signature(self.backup.salva)
        self.assertIn("forza", firma.parameters)
        self.assertIs(firma.parameters["forza"].default, False)
