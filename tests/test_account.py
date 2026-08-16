"""Login, registrazione e approvazione del parco di test.

Stessa filosofia di `test_sito.py`: le pagine si disegnano davvero e le
rotte si chiamano davvero, con un archivio vero in un file temporaneo.
`core/auth.py` e `core/mail.py` si collaudano anche da soli, senza rete
e senza passare dal sito, perché sono pensati per questo (vedi i loro
docstring).
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AVVIA_WORKER"] = "0"


def _archivio_vuoto():
    cartella = tempfile.mkdtemp(prefix="account-")
    os.environ["DB_PATH"] = os.path.join(cartella, "test.db")

    from core import config as C

    C.DB_PATH = os.environ["DB_PATH"]
    # TestClient parla http://testserver, non https: un cookie Secure
    # verrebbe scartato dal suo cookie jar esattamente come da un vero
    # browser su un sito senza TLS. È lo stesso scenario descritto in
    # core/config.py per il collaudo in locale.
    C.COOKIE_SECURE = False

    from core import storage

    storage.reset_state()
    storage.init_db()
    return cartella


# ======================================================================
# core/auth.py — password, sessioni, CSRF, token — senza rete
# ======================================================================
class TestPassword(unittest.TestCase):
    def test_hash_e_verifica(self):
        from core import auth

        hashed = auth.hash_password("una-password-robusta")
        self.assertTrue(auth.verifica_password("una-password-robusta", hashed))
        self.assertFalse(auth.verifica_password("un-altra-password", hashed))

    def test_due_hash_della_stessa_password_sono_diversi(self):
        """Il sale è casuale a ogni chiamata: due hash della stessa
        password non devono mai coincidere, altrimenti una tabella
        precompilata (rainbow table) diventerebbe riusabile fra utenti."""
        from core import auth

        self.assertNotEqual(auth.hash_password("stessa-password"),
                            auth.hash_password("stessa-password"))

    def test_hash_manomesso_non_verifica(self):
        from core import auth

        hashed = auth.hash_password("una-password-robusta")
        manomesso = hashed[:-4] + "xxxx"
        self.assertFalse(auth.verifica_password("una-password-robusta", manomesso))

    def test_password_valida_richiede_dieci_caratteri(self):
        from core import auth

        self.assertIsNotNone(auth.password_valida("corta"))
        self.assertIsNone(auth.password_valida("password-lunga-abbastanza"))

    def test_password_con_spazi_ai_bordi_e_rifiutata(self):
        from core import auth

        self.assertIsNotNone(auth.password_valida(" password-lunga-abbastanza"))


class TestSessioni(unittest.TestCase):
    def test_sessione_valida_torna_lid_utente(self):
        from core import auth

        token = auth.crea_sessione(42)
        self.assertEqual(auth.leggi_sessione(token), 42)

    def test_sessione_scaduta_non_e_valida(self):
        from core import auth

        token = auth.crea_sessione(42, durata_secondi=-1)
        self.assertIsNone(auth.leggi_sessione(token))

    def test_token_manomesso_non_e_valido(self):
        """Cambiare anche un solo carattere del payload deve invalidare
        la firma — altrimenti si potrebbe cambiare l'id utente a mano e
        impersonare un altro account."""
        from core import auth

        token = auth.crea_sessione(42)
        payload, firma = token.split(".", 1)
        manomesso = payload[:-1] + ("A" if payload[-1] != "A" else "B") + "." + firma
        self.assertIsNone(auth.leggi_sessione(manomesso))

    def test_token_vuoto_o_malformato_non_solleva_eccezioni(self):
        from core import auth

        self.assertIsNone(auth.leggi_sessione(None))
        self.assertIsNone(auth.leggi_sessione(""))
        self.assertIsNone(auth.leggi_sessione("non-e-un-token"))


class TestCsrfETokenRichiesta(unittest.TestCase):
    def test_csrf_valido_solo_se_i_due_valori_coincidono(self):
        from core import auth

        token = auth.nuovo_token_csrf()
        self.assertTrue(auth.csrf_valido(token, token))
        self.assertFalse(auth.csrf_valido(token, "altro-valore"))
        self.assertFalse(auth.csrf_valido(None, token))

    def test_token_richiesta_verifica_solo_col_hash_giusto(self):
        from core import auth

        token, token_hash = auth.nuovo_token_richiesta()
        self.assertTrue(auth.token_richiesta_valido(token, token_hash))
        self.assertFalse(auth.token_richiesta_valido("token-sbagliato", token_hash))


class TestMail(unittest.TestCase):
    def test_il_testo_contiene_il_link_e_lo_username(self):
        from core import mail

        oggetto, corpo = mail.costruisci_richiesta(
            {"username": "mario", "email": "mario@example.com"},
            "https://esempio.test/admin/richieste/token/9?token=abc",
        )
        self.assertIn("mario", oggetto)
        self.assertIn("https://esempio.test/admin/richieste/token/9?token=abc", corpo)

    def test_invio_senza_smtp_configurato_torna_un_errore_chiaro(self):
        """Nessuna eccezione che risale fino alla richiesta HTTP di chi si
        registra: un fallimento di invio è un dato, non un crash."""
        from core import mail

        for chiave in ("SMTP_USERNAME", "SMTP_PASSWORD"):
            os.environ.pop(chiave, None)
        ok, messaggio = mail.invia("a@example.com", "oggetto", "corpo")
        self.assertFalse(ok)
        self.assertIn("SMTP", messaggio)


# ======================================================================
# Le rotte del sito
# ======================================================================
class _SitoConAccount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _archivio_vuoto()
        os.environ["ADMIN_USERNAME"] = "riccardo"
        os.environ["ADMIN_EMAIL"] = "riccardo@example.com"
        os.environ["ADMIN_PASSWORD"] = "password-admin-di-collaudo"

        from fastapi.testclient import TestClient

        from web import account
        from web.main import app

        # `avvio()` (e con lui il bootstrap dell'admin) gira solo dietro il
        # ciclo di vita ASGI, che TestClient qui non attraversa — stessa
        # ragione per cui `test_sito.py` popola l'archivio a mano invece
        # di aspettarselo dall'avvio vero. Si chiama esplicitamente, come
        # farebbe `web/main.py::avvio()` al primo deploy.
        cls._bootstrap_admin = account.assicura_admin()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        for chiave in ("ADMIN_USERNAME", "ADMIN_EMAIL", "ADMIN_PASSWORD"):
            os.environ.pop(chiave, None)

    def setUp(self):
        self.client.cookies.clear()


class TestBootstrapAdmin(_SitoConAccount):
    def test_lamministratore_nasce_una_sola_volta(self):
        from web import account

        self.assertIn("creato", self._bootstrap_admin)
        # Una seconda chiamata (es. un riavvio del piano gratuito con le
        # stesse variabili ancora impostate) non deve ricreare né toccare
        # l'account: altrimenti la password tornerebbe sempre quella
        # iniziale, azzerando ogni cambio fatto da /account/password.
        self.assertEqual(account.assicura_admin(), "già presente")


class TestAccessoParco(_SitoConAccount):
    def test_anonimo_viene_rimandato_al_login(self):
        risposta = self.client.get("/parco", follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)
        self.assertEqual(risposta.headers["location"], "/login?next=/parco")

    def test_le_azioni_del_parco_sono_protette_anche_loro(self):
        for metodo, percorso, dati in (
            ("post", "/parco/aggiungi", {"chiave": "x"}),
            ("post", "/parco/togli", {"chiave": "x"}),
            ("post", "/parco/segna-test", {"chiave": "x", "data_test": "2026-01-01"}),
        ):
            with self.subTest(percorso=percorso):
                risposta = getattr(self.client, metodo)(percorso, data=dati, follow_redirects=False)
                self.assertEqual(risposta.status_code, 303)
                self.assertEqual(risposta.headers["location"], "/login?next=/parco")

    def test_login_valido_apre_il_parco(self):
        risposta = self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": self._csrf_login(),
        }, follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)
        self.assertEqual(risposta.headers["location"], "/parco")
        self.assertEqual(self.client.get("/parco").status_code, 200)

    def test_nome_utente_compare_in_testata_dopo_il_login(self):
        self._accedi("riccardo", "password-admin-di-collaudo")
        self.assertIn("riccardo", self.client.get("/").text)

    def test_logout_toglie_laccesso(self):
        self._accedi("riccardo", "password-admin-di-collaudo")
        self.client.post("/logout", follow_redirects=False)
        self.assertEqual(self.client.get("/parco", follow_redirects=False).status_code, 303)

    def _csrf_login(self):
        self.client.get("/login")
        return self.client.cookies.get("csrf_token")

    def _accedi(self, username, password):
        csrf = self._csrf_login()
        return self.client.post("/login", data={
            "username": username, "password": password, "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)


class TestLoginCredenzialiSbagliate(_SitoConAccount):
    def test_password_sbagliata_non_entra(self):
        csrf = self._csrf()
        risposta = self.client.post("/login", data={
            "username": "riccardo", "password": "password-sbagliata",
            "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)
        self.assertEqual(risposta.headers["location"], "/login?errore=credenziali&next=/parco")
        self.assertEqual(self.client.get("/parco", follow_redirects=False).status_code, 303)

    def test_username_inesistente_non_entra_e_non_solleva_eccezioni(self):
        csrf = self._csrf()
        risposta = self.client.post("/login", data={
            "username": "nessuno-cosi", "password": "qualunque-cosa-lunga",
            "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)
        self.assertEqual(risposta.headers["location"], "/login?errore=credenziali&next=/parco")

    def test_csrf_mancante_blocca_il_login(self):
        risposta = self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": "token-a-caso",
        }, follow_redirects=False)
        self.assertIn("modulo_scaduto", risposta.headers["location"])
        self.assertEqual(self.client.get("/parco", follow_redirects=False).status_code, 303)

    def test_troppi_tentativi_bloccano_temporaneamente_laccount(self):
        from core import config as C

        csrf = self._csrf()
        for _ in range(C.LOGIN_MAX_TENTATIVI):
            self.client.post("/login", data={
                "username": "riccardo", "password": "password-sbagliata",
                "next": "/parco", "csrf": csrf,
            }, follow_redirects=False)
        risposta = self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)
        # Anche con la password GIUSTA, l'account resta bloccato: è il
        # punto di un blocco temporaneo — non basta indovinarla al
        # tentativo giusto durante la finestra di blocco.
        self.assertIn("bloccato", risposta.headers["location"])

    def _csrf(self):
        self.client.get("/login")
        return self.client.cookies.get("csrf_token")


class TestRegistrazioneEApprovazione(_SitoConAccount):
    def test_la_registrazione_crea_un_account_in_attesa_e_manda_lemail(self):
        from core import storage

        with patch("web.account.mail.invia", return_value=(True, "")) as invio:
            risposta = self._registra("nuovo_utente", "nuovo@example.com", "password-nuova-lunga")
        self.assertEqual(risposta.status_code, 303)
        self.assertEqual(risposta.headers["location"], "/registrati?inviata=1")

        utente = storage.get_utente_per_username("nuovo_utente")
        self.assertIsNotNone(utente)
        self.assertEqual(utente["stato"], storage.STATO_IN_ATTESA)

        invio.assert_called_once()
        destinatario, oggetto, corpo = invio.call_args[0]
        from core import config as C

        self.assertEqual(destinatario, C.ADMIN_APPROVAL_EMAIL)
        self.assertIn("nuovo_utente", oggetto)
        self.assertIn("/admin/richieste/token/", corpo)

    def test_lutente_in_attesa_non_puo_accedere(self):
        with patch("web.account.mail.invia", return_value=(True, "")):
            self._registra("in_attesa_x", "attesa@example.com", "password-nuova-lunga")
        csrf = self._csrf_login()
        risposta = self.client.post("/login", data={
            "username": "in_attesa_x", "password": "password-nuova-lunga",
            "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)
        self.assertIn("errore=in_attesa", risposta.headers["location"])

    def test_lamministratore_approva_dal_pannello_e_lutente_accede(self):
        from core import storage

        with patch("web.account.mail.invia", return_value=(True, "")):
            self._registra("da_approvare", "approva@example.com", "password-nuova-lunga")
        utente = storage.get_utente_per_username("da_approvare")

        self._accedi_admin()
        self.client.get("/admin/richieste")
        csrf_admin = self.client.cookies.get("csrf_token")
        risposta = self.client.post(f"/admin/richieste/{utente['id']}/approva",
                                    data={"csrf": csrf_admin}, follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)
        self.assertEqual(storage.get_utente(utente["id"])["stato"], storage.STATO_APPROVATO)

        self.client.cookies.clear()
        csrf = self._csrf_login()
        risposta = self.client.post("/login", data={
            "username": "da_approvare", "password": "password-nuova-lunga",
            "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)
        self.assertEqual(risposta.headers["location"], "/parco")

    def test_chi_non_e_amministratore_non_vede_il_pannello_richieste(self):
        from core import storage

        with patch("web.account.mail.invia", return_value=(True, "")):
            self._registra("utente_normale", "normale@example.com", "password-nuova-lunga")
        utente = storage.get_utente_per_username("utente_normale")
        storage.imposta_stato_utente(utente["id"], storage.STATO_APPROVATO)

        csrf = self._csrf_login()
        self.client.post("/login", data={
            "username": "utente_normale", "password": "password-nuova-lunga",
            "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)
        self.assertEqual(self.client.get("/admin/richieste", follow_redirects=False).status_code, 303)

    def test_lapprovazione_via_link_a_token_funziona_senza_login(self):
        from core import storage

        catturato = {}

        def _cattura(destinatario, oggetto, corpo):
            catturato["corpo"] = corpo
            return True, ""

        with patch("web.account.mail.invia", side_effect=_cattura):
            self._registra("via_link", "vialink@example.com", "password-nuova-lunga")
        utente = storage.get_utente_per_username("via_link")

        import re

        link = re.search(r"/admin/richieste/token/(\d+)\?token=(\S+)", catturato["corpo"])
        richiesta_id, token = link.group(1), link.group(2)

        client_anonimo = self.client.__class__(self.client.app)
        pagina = client_anonimo.get(f"/admin/richieste/token/{richiesta_id}", params={"token": token})
        self.assertIn("via_link", pagina.text)

        risposta = client_anonimo.post(
            f"/admin/richieste/token/{richiesta_id}/approva", data={"token": token},
            follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)
        self.assertEqual(storage.get_utente(utente["id"])["stato"], storage.STATO_APPROVATO)

        # Il link è a uso singolo: un secondo tentativo non deve poter
        # rifiutare un account già approvato.
        client_anonimo.post(f"/admin/richieste/token/{richiesta_id}/rifiuta",
                            data={"token": token}, follow_redirects=False)
        self.assertEqual(storage.get_utente(utente["id"])["stato"], storage.STATO_APPROVATO)

    def test_un_token_sbagliato_non_approva_nulla(self):
        from core import storage

        catturato = {}

        def _cattura(destinatario, oggetto, corpo):
            catturato["corpo"] = corpo
            return True, ""

        with patch("web.account.mail.invia", side_effect=_cattura):
            self._registra("token_sbagliato", "sbagliato@example.com", "password-nuova-lunga")
        utente = storage.get_utente_per_username("token_sbagliato")

        import re

        richiesta_id = re.search(r"/admin/richieste/token/(\d+)\?token=", catturato["corpo"]).group(1)

        client_anonimo = self.client.__class__(self.client.app)
        client_anonimo.post(f"/admin/richieste/token/{richiesta_id}/approva",
                            data={"token": "token-inventato"}, follow_redirects=False)
        self.assertEqual(storage.get_utente(utente["id"])["stato"], storage.STATO_IN_ATTESA)

    def test_username_gia_in_uso_e_rifiutato(self):
        with patch("web.account.mail.invia", return_value=(True, "")):
            self._registra("doppio", "uno@example.com", "password-nuova-lunga")
            risposta = self._registra("doppio", "due@example.com", "password-nuova-lunga")
        self.assertIn("errore=username_esistente", risposta.headers["location"])

    def test_password_troppo_corta_e_rifiutata(self):
        risposta = self._registra("password_corta", "corta@example.com", "corta")
        self.assertEqual(risposta.status_code, 303)
        self.assertIn("/registrati?errore=", risposta.headers["location"])
        from core import storage

        self.assertIsNone(storage.get_utente_per_username("password_corta"))

    def _registra(self, username, email, password):
        self.client.get("/registrati")
        csrf = self.client.cookies.get("csrf_token")
        return self.client.post("/registrati", data={
            "username": username, "email": email,
            "password": password, "conferma": password, "csrf": csrf,
        }, follow_redirects=False)

    def _csrf_login(self):
        self.client.get("/login")
        return self.client.cookies.get("csrf_token")

    def _accedi_admin(self):
        csrf = self._csrf_login()
        self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)


class TestCambioPassword(_SitoConAccount):
    def test_si_puo_cambiare_la_password(self):
        self._accedi("riccardo", "password-admin-di-collaudo")
        self.client.get("/account/password")
        csrf = self.client.cookies.get("csrf_token")
        risposta = self.client.post("/account/password", data={
            "attuale": "password-admin-di-collaudo", "nuova": "password-nuova-ancora-piu-lunga",
            "conferma": "password-nuova-ancora-piu-lunga", "csrf": csrf,
        }, follow_redirects=False)
        self.assertEqual(risposta.headers["location"], "/account/password?ok=1")

        self.client.cookies.clear()
        csrf = self._csrf_login()
        risposta = self.client.post("/login", data={
            "username": "riccardo", "password": "password-nuova-ancora-piu-lunga",
            "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)
        self.assertEqual(risposta.headers["location"], "/parco")

    def test_password_attuale_sbagliata_non_cambia_nulla(self):
        self._accedi("riccardo", "password-admin-di-collaudo")
        self.client.get("/account/password")
        csrf = self.client.cookies.get("csrf_token")
        risposta = self.client.post("/account/password", data={
            "attuale": "non-e-quella-giusta", "nuova": "password-nuova-ancora-piu-lunga",
            "conferma": "password-nuova-ancora-piu-lunga", "csrf": csrf,
        }, follow_redirects=False)
        self.assertIn("errore=attuale", risposta.headers["location"])

    def _csrf_login(self):
        self.client.get("/login")
        return self.client.cookies.get("csrf_token")

    def _accedi(self, username, password):
        csrf = self._csrf_login()
        return self.client.post("/login", data={
            "username": username, "password": password, "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)


class TestBootstrapAdminConflitto(_SitoConAccount):
    """ADMIN_USERNAME già occupato da un account NON amministratore.

    Non è uno scenario di laboratorio: `/registrati` è pubblico e non
    richiede che un amministratore esista già, quindi chiunque può
    prendersi quel nome; e su un disco effimero il bootstrap riparte a
    ogni riavvio, trovandoselo davanti. Prima, l'INSERT violava il
    vincolo UNIQUE e l'eccezione risaliva fino al ciclo di vita di
    FastAPI: non restava senza amministratore il parco di test, non
    partiva l'INTERO sito — ricerca e dispositivi compresi.
    """
    def test_username_occupato_non_butta_giu_lavvio(self):
        from core import auth, storage
        from web import account

        # Si riparte da zero: qui l'amministratore NON deve esistere
        # ancora, altrimenti `assicura_admin` uscirebbe subito con «già
        # presente» senza arrivare al punto in esame.
        _archivio_vuoto()
        storage.crea_utente("riccardo", "qualcunaltro@example.com",
                            auth.hash_password("una-password-qualunque"))

        esito = account.assicura_admin()

        self.assertIn("già di un account non amministratore", esito)
        # E soprattutto: nessun amministratore creato per sbaglio. Chi si
        # è registrato per primo con quel nome non deve ritrovarsi i
        # permessi di amministratore in mano.
        self.assertFalse(storage.esiste_admin())
        utente = storage.get_utente_per_username("riccardo")
        self.assertFalse(utente["admin"])


class TestRitornoDopoLogin(_SitoConAccount):
    def test_il_parametro_next_non_porta_fuori_dal_sito(self):
        from web.account import _next_sicuro

        for fuori in ("https://esempio.invalid/",
                      "//esempio.invalid/",
                      # La barra ROVESCIA: il browser la normalizza in
                      # barra dritta, quindi questo diventerebbe
                      # `//esempio.invalid`, cioè un altro dominio.
                      "/\\esempio.invalid",
                      "\\\\esempio.invalid"):
            with self.subTest(fuori=fuori):
                self.assertEqual(_next_sicuro(fuori), "/parco")

    def test_un_percorso_locale_viene_rispettato(self):
        from web.account import _next_sicuro

        self.assertEqual(_next_sicuro("/admin/richieste"), "/admin/richieste")


class TestLaSessioneSeguelaPassword(_SitoConAccount):
    """Cambiare password chiude le sessioni aperte ALTROVE.

    Una sessione firmata non ha uno stato lato server da cancellare: senza
    l'impronta dentro il cookie (`core/auth.py::impronta_password`) il
    cookie vecchio resterebbe buono fino alla scadenza naturale — proprio
    nel caso in cui si cambia password perché si sospetta che qualcuno
    sia entrato.
    """
    def test_il_cookie_vecchio_non_vale_piu_e_il_nuovo_si(self):
        self._accedi("riccardo", "password-admin-di-collaudo")
        # Il cookie che si porterebbe dietro un ALTRO browser, già
        # collegato, mentre qui si cambia la password.
        altro_browser = self.client.cookies.get("sessione")

        self.client.get("/account/password")
        risposta = self.client.post("/account/password", data={
            "attuale": "password-admin-di-collaudo",
            "nuova": "una-password-tutta-nuova",
            "conferma": "una-password-tutta-nuova",
            "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)
        self.assertEqual(risposta.headers["location"], "/account/password?ok=1")

        # Chi ha cambiato la password resta dentro: la risposta gli ha
        # dato un cookie nuovo, altrimenti si sarebbe buttato fuori da solo.
        self.assertEqual(self.client.get("/parco", follow_redirects=False).status_code, 200)

        # L'altro browser, no.
        self.client.cookies.clear()
        self.client.cookies.set("sessione", altro_browser)
        rimandato = self.client.get("/parco", follow_redirects=False)
        self.assertEqual(rimandato.status_code, 303)
        self.assertEqual(rimandato.headers["location"], "/login?next=/parco")

    def _csrf_login(self):
        self.client.get("/login")
        return self.client.cookies.get("csrf_token")

    def _accedi(self, username, password):
        csrf = self._csrf_login()
        return self.client.post("/login", data={
            "username": username, "password": password, "next": "/parco", "csrf": csrf,
        }, follow_redirects=False)


if __name__ == "__main__":
    unittest.main()
