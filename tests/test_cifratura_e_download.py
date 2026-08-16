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
