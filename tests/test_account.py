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


class _ConRecupero(_SitoConAccount):
    """Base con un secondo account approvato, che è quello che dimentica
    la password: l'amministratore serve a generare i link, non a farsi
    resettare (per lui c'è una via a parte, vedi in fondo)."""

    def setUp(self):
        super().setUp()
        from core import auth, storage

        esistente = storage.get_utente_per_username("smemorato")
        if not esistente:
            storage.crea_utente("smemorato", "smemorato@example.com",
                                auth.hash_password("la-password-di-prima"),
                                stato=storage.STATO_APPROVATO)
        else:
            storage.imposta_password(esistente["id"],
                                     auth.hash_password("la-password-di-prima"))
            storage.imposta_stato_utente(esistente["id"], storage.STATO_APPROVATO)
            storage.reset_tentativi_falliti(esistente["id"])

    def _chiedi_recupero(self, email):
        self.client.get("/password-dimenticata")
        csrf = self.client.cookies.get("csrf_token")
        with patch("web.account.mail.invia", return_value=(True, "")) as invio:
            risposta = self.client.post("/password-dimenticata", data={
                "email": email, "csrf": csrf,
            }, follow_redirects=False)
        return risposta, invio

    def _percorso_dal_link(self, link):
        """Dal link assoluto dell'email al percorso da chiamare nei test."""
        return link.replace(C_SITE_BASE_URL(), "")

    def _imposta_dal_link(self, percorso, password):
        self.client.get(percorso)
        csrf = self.client.cookies.get("csrf_token")
        token = percorso.split("token=", 1)[1]
        base = percorso.split("?", 1)[0]
        return self.client.post(base, data={
            "token": token, "nuova": password, "conferma": password, "csrf": csrf,
        }, follow_redirects=False)


def C_SITE_BASE_URL():
    from core import config as C

    return C.SITE_BASE_URL


class TestRecuperoPasswordViaEmail(_ConRecupero):
    def test_il_giro_completo_dal_link_al_nuovo_accesso(self):
        risposta, invio = self._chiedi_recupero("smemorato@example.com")
        self.assertEqual(risposta.headers["location"], "/password-dimenticata?inviata=1")

        destinatario, _oggetto, corpo = invio.call_args[0]
        self.assertEqual(destinatario, "smemorato@example.com")
        link = [p for p in corpo.split() if "/password-nuova/" in p][0]

        esito = self._imposta_dal_link(self._percorso_dal_link(link),
                                       "una-password-nuova-lunga")
        self.assertEqual(esito.headers["location"], "/login?reimpostata=1")

        # La password nuova entra...
        self.client.cookies.clear()
        self.client.get("/login")
        accesso = self.client.post("/login", data={
            "username": "smemorato", "password": "una-password-nuova-lunga",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)
        self.assertEqual(accesso.headers["location"], "/parco")

    def test_un_indirizzo_sconosciuto_risponde_uguale_e_non_manda_niente(self):
        """Distinguere i due casi trasformerebbe il modulo in un modo per
        scoprire quali indirizzi hanno un account qui dentro."""
        noto, invio_noto = self._chiedi_recupero("smemorato@example.com")
        ignoto, invio_ignoto = self._chiedi_recupero("nessuno@example.com")

        self.assertEqual(noto.headers["location"], ignoto.headers["location"])
        invio_noto.assert_called_once()
        invio_ignoto.assert_not_called()

    def test_un_account_non_approvato_non_si_recupera(self):
        from core import auth, storage

        storage.crea_utente("mai_approvato", "attesa2@example.com",
                            auth.hash_password("una-password-qualunque"))
        _risposta, invio = self._chiedi_recupero("attesa2@example.com")
        invio.assert_not_called()

    def test_il_link_vale_una_volta_sola(self):
        _risposta, invio = self._chiedi_recupero("smemorato@example.com")
        corpo = invio.call_args[0][2]
        percorso = self._percorso_dal_link(
            [p for p in corpo.split() if "/password-nuova/" in p][0])

        self._imposta_dal_link(percorso, "prima-password-nuova-lunga")
        # Secondo giro con lo stesso link: la pagina deve dirlo, e la
        # password non deve cambiare di nuovo.
        pagina = self.client.get(percorso).text
        self.assertIn("Link scaduto o già usato", pagina)

    def test_un_token_sbagliato_non_reimposta_niente(self):
        _risposta, invio = self._chiedi_recupero("smemorato@example.com")
        corpo = invio.call_args[0][2]
        percorso = self._percorso_dal_link(
            [p for p in corpo.split() if "/password-nuova/" in p][0])
        falso = percorso.split("?", 1)[0] + "?token=inventato-di-sana-pianta"

        self.assertIn("Link non valido", self.client.get(falso).text)
        self._imposta_dal_link(falso, "password-mai-impostata-lunga")

        # La password di prima è ancora quella buona.
        self.client.cookies.clear()
        self.client.get("/login")
        accesso = self.client.post("/login", data={
            "username": "smemorato", "password": "la-password-di-prima",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)
        self.assertEqual(accesso.headers["location"], "/parco")

    def test_chiedere_un_secondo_link_annulla_il_primo(self):
        _r1, invio1 = self._chiedi_recupero("smemorato@example.com")
        primo = self._percorso_dal_link(
            [p for p in invio1.call_args[0][2].split() if "/password-nuova/" in p][0])
        _r2, _invio2 = self._chiedi_recupero("smemorato@example.com")

        self.assertIn("Link scaduto o già usato", self.client.get(primo).text)

    def test_il_recupero_sblocca_chi_era_chiuso_fuori_dai_tentativi(self):
        """Chi recupera la password è spesso chi si è bloccato provandola:
        senza questo, reimposterebbe e si ritroverebbe comunque «troppi
        tentativi»."""
        from datetime import timedelta

        from core import storage
        from core.util import utcnow

        smemorato = storage.get_utente_per_username("smemorato")
        storage.registra_tentativo_fallito(
            smemorato["id"], (utcnow() + timedelta(minutes=30)).isoformat())

        _risposta, invio = self._chiedi_recupero("smemorato@example.com")
        percorso = self._percorso_dal_link(
            [p for p in invio.call_args[0][2].split() if "/password-nuova/" in p][0])
        self._imposta_dal_link(percorso, "password-dopo-lo-sblocco")

        self.client.cookies.clear()
        self.client.get("/login")
        accesso = self.client.post("/login", data={
            "username": "smemorato", "password": "password-dopo-lo-sblocco",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)
        self.assertEqual(accesso.headers["location"], "/parco",
                         "il blocco doveva essere tolto insieme alla password")


class TestResetGeneratoDallAmministratore(_ConRecupero):
    """La via che funziona SENZA SMTP — cioè quella che serve davvero
    finché su Render non sono impostate SMTP_USERNAME/SMTP_PASSWORD."""

    def _accedi_admin(self):
        self.client.get("/login")
        return self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)

    def test_lamministratore_genera_un_link_e_quello_funziona(self):
        from core import storage

        self._accedi_admin()
        self.client.get("/admin/utenti")
        smemorato = storage.get_utente_per_username("smemorato")
        risposta = self.client.post(
            f"/admin/utenti/{smemorato['id']}/reset",
            data={"csrf": self.client.cookies.get("csrf_token")},
            follow_redirects=False)

        # Il link si MOSTRA all'amministratore, non parte per email.
        pagina = self.client.get(risposta.headers["location"]).text
        self.assertIn("/password-nuova/", pagina)
        self.assertIn("smemorato", pagina)

    def test_chi_non_e_amministratore_non_puo_generare_reset(self):
        from core import storage

        self.client.get("/login")
        self.client.post("/login", data={
            "username": "smemorato", "password": "la-password-di-prima",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)

        admin = storage.get_utente_per_username("riccardo")
        risposta = self.client.post(
            f"/admin/utenti/{admin['id']}/reset",
            data={"csrf": self.client.cookies.get("csrf_token")},
            follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)
        self.assertIn("/login", risposta.headers["location"])

        pagina = self.client.get("/admin/utenti", follow_redirects=False)
        self.assertEqual(pagina.headers["location"], "/parco")


class TestViaDUscitaAmministratore(unittest.TestCase):
    """Se a perdere la password è l'unico amministratore, nessuno può
    generargli un link: è lui che li genera. L'unica prova d'identità
    rimasta è il controllo delle variabili d'ambiente di Render."""

    def setUp(self):
        _archivio_vuoto()
        os.environ["ADMIN_USERNAME"] = "capo"
        os.environ["ADMIN_EMAIL"] = "capo@example.com"
        os.environ["ADMIN_PASSWORD"] = "la-password-iniziale"
        os.environ.pop("ADMIN_PASSWORD_RESET", None)

        from web import account

        account.assicura_admin()

    def tearDown(self):
        for chiave in ("ADMIN_USERNAME", "ADMIN_EMAIL", "ADMIN_PASSWORD",
                       "ADMIN_PASSWORD_RESET"):
            os.environ.pop(chiave, None)

    def test_senza_la_variabile_un_riavvio_non_tocca_la_password(self):
        """È il comportamento di sempre, e va difeso: reimpostare a ogni
        avvio cancellerebbe in silenzio ogni cambio fatto a mano."""
        from core import auth, storage
        from web import account

        storage.imposta_password(
            storage.get_utente_per_username("capo")["id"],
            auth.hash_password("cambiata-a-mano-dopo"))

        self.assertEqual(account.assicura_admin(), "già presente")

        capo = storage.get_utente_per_username("capo")
        self.assertTrue(auth.verifica_password("cambiata-a-mano-dopo", capo["password_hash"]))

    def test_con_la_variabile_la_password_torna_quella_di_render(self):
        from core import auth, storage
        from web import account

        storage.imposta_password(
            storage.get_utente_per_username("capo")["id"],
            auth.hash_password("quella-che-ho-dimenticato"))
        os.environ["ADMIN_PASSWORD_RESET"] = "true"
        os.environ["ADMIN_PASSWORD"] = "la-password-di-rientro"

        esito = account.assicura_admin()
        self.assertIn("reimpostata", esito)
        # Il messaggio deve ricordare di togliere la variabile: lasciata
        # accesa, ogni riavvio riporterebbe la password a quella.
        self.assertIn("togli quella variabile", esito)

        capo = storage.get_utente_per_username("capo")
        self.assertTrue(auth.verifica_password("la-password-di-rientro", capo["password_hash"]))

    def test_la_variabile_non_reimposta_niente_se_la_password_e_troppo_corta(self):
        from core import auth, storage
        from web import account

        os.environ["ADMIN_PASSWORD_RESET"] = "true"
        os.environ["ADMIN_PASSWORD"] = "corta"

        esito = account.assicura_admin()
        self.assertIn("non valida", esito)
        capo = storage.get_utente_per_username("capo")
        self.assertTrue(auth.verifica_password("la-password-iniziale", capo["password_hash"]))


class TestDiagnosticaInvioEmail(_SitoConAccount):
    """Segnalato dall'utente: «non mi arriva la mail di richiesta account».
    Non arrivava perché SMTP non era configurato — un modo di funzionare
    previsto, non un guasto — ma nessuna pagina lo diceva, quindi da fuori
    era indistinguibile da un'email persa o da un difetto del codice."""

    def _accedi_diagnostica(self):
        """Catalogo e Diagnostica sono una pagina sola e stanno dietro
        login dal 16/08/2026: dicono quali fonti falliscono e com'e'
        configurato il salvataggio, cioe' come e' fatto il servizio."""
        self.client.cookies.clear()
        self.client.get("/login")
        self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)



    def test_senza_smtp_la_diagnostica_lo_dice(self):
        from core import mail

        for chiave in ("SMTP_USERNAME", "SMTP_PASSWORD"):
            os.environ.pop(chiave, None)
        self.assertIn("non configurato", mail.stato())
        self.assertIn("/admin/richieste", mail.stato())

        # La pagina e' passata dietro login insieme al Catalogo.
        self._accedi_diagnostica()
        pagina = self.client.get("/catalogo").text
        self.assertIn("Invio email", pagina)

    def test_con_smtp_la_diagnostica_dice_da_dove_parte(self):
        from core import mail

        os.environ["SMTP_USERNAME"] = "mittente@example.com"
        os.environ["SMTP_PASSWORD"] = "una-password-per-le-app"
        try:
            testo = mail.stato()
            self.assertIn("attivo", testo)
            self.assertIn("mittente@example.com", testo)
        finally:
            for chiave in ("SMTP_USERNAME", "SMTP_PASSWORD"):
                os.environ.pop(chiave, None)

    def test_il_pannello_richieste_avverte_che_le_email_non_partono(self):
        for chiave in ("SMTP_USERNAME", "SMTP_PASSWORD"):
            os.environ.pop(chiave, None)
        self.client.get("/login")
        self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)

        pagina = self.client.get("/admin/richieste").text
        self.assertIn("non è configurato", pagina)
        # E soprattutto NON deve promettere un'email che non parte.
        self.assertNotIn("arrivano anche via email", pagina)


class TestVersioneInProduzione(_SitoConAccount):
    """«Ho fatto il push, il sito e' aggiornato?» era deducibile solo per
    indizi, e una volta la deduzione e' stata sbagliata. Render mette
    RENDER_GIT_COMMIT da solo nell'ambiente: qui si verifica che finisca
    dove si va a guardare."""

    def _accedi_diagnostica(self):
        """Catalogo e Diagnostica sono una pagina sola e stanno dietro
        login dal 16/08/2026: dicono quali fonti falliscono e com'e'
        configurato il salvataggio, cioe' come e' fatto il servizio."""
        self.client.cookies.clear()
        self.client.get("/login")
        self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)



    def test_fuori_da_render_lo_dice_invece_di_inventare(self):
        from core import config as C

        for chiave in ("RENDER_GIT_COMMIT", "RENDER_GIT_BRANCH"):
            os.environ.pop(chiave, None)
        self.assertIn("sconosciuta", C.versione_distribuita())

    def test_su_render_mostra_commit_e_ramo(self):
        from core import config as C

        os.environ["RENDER_GIT_COMMIT"] = "abcdef1234567890"
        os.environ["RENDER_GIT_BRANCH"] = "main"
        try:
            testo = C.versione_distribuita()
            self.assertIn("abcdef1", testo)
            self.assertIn("main", testo)
            # Accorciato: un commit intero in una tabella non si legge.
            self.assertNotIn("abcdef1234567890", testo)

            self._accedi_diagnostica()
            pagina = self.client.get("/catalogo").text
            self.assertIn("Versione in produzione", pagina)
            self.assertIn("abcdef1", pagina)
        finally:
            for chiave in ("RENDER_GIT_COMMIT", "RENDER_GIT_BRANCH"):
                os.environ.pop(chiave, None)


class TestSenzaSmtpLoDiceSubito(_SitoConAccount):
    """Segnalato dall'utente il 17/08/2026: «non arriva la mail di
    recupero». Non arrivava perche' SMTP non e' configurato — previsto —
    ma la pagina rispondeva «Controlla la posta» lo stesso, mandando ad
    aspettare un messaggio mai partito.

    Che questo sito sappia o no mandare email e' una proprieta' DEL SITO,
    uguale per tutti: dichiararla non rivela quali indirizzi abbiano un
    account, che e' la cosa da non rivelare.
    """

    def setUp(self):
        super().setUp()
        for chiave in ("SMTP_USERNAME", "SMTP_PASSWORD"):
            os.environ.pop(chiave, None)

    def _chiedi(self, email="qualcuno@example.com"):
        self.client.get("/password-dimenticata")
        csrf = self.client.cookies.get("csrf_token")
        self.client.post("/password-dimenticata", data={"email": email, "csrf": csrf},
                         follow_redirects=False)
        return self.client.get("/password-dimenticata?inviata=1").text

    def test_senza_smtp_non_dice_di_controllare_la_posta(self):
        pagina = self._chiedi()
        self.assertNotIn("Controlla la posta", pagina)
        self.assertIn("le email non partono", pagina)
        self.assertIn("link di recupero", pagina)

    def test_con_smtp_torna_il_messaggio_normale(self):
        os.environ["SMTP_USERNAME"] = "mittente@example.com"
        os.environ["SMTP_PASSWORD"] = "una-password-per-le-app"
        try:
            with patch("web.account.mail.invia", return_value=(True, "")):
                pagina = self._chiedi()
            self.assertIn("Controlla la posta", pagina)
        finally:
            for chiave in ("SMTP_USERNAME", "SMTP_PASSWORD"):
                os.environ.pop(chiave, None)

    def test_non_rivela_comunque_se_lindirizzo_esiste(self):
        """La regola che conta resta: la risposta e' la stessa per un
        indirizzo noto e per uno inventato."""
        noto = self._chiedi("riccardo@example.com")
        ignoto = self._chiedi("nessuno-di-sicuro@example.com")
        self.assertEqual(noto, ignoto)


class TestProvaInvioEmail(_SitoConAccount):
    """«Configurato ma non arriva la mail», 17/08/2026.

    Il recupero password ignora di proposito l'esito dell'invio: dire
    «fallito» per un indirizzo e «fatto» per un altro rivelerebbe quali
    indirizzi hanno un account qui dentro. La conseguenza era pero' che
    un errore VERO — password per le app sbagliata, Gmail che rifiuta la
    connessione — non lo vedeva nessuno, e da fuori restava solo «non
    arriva la mail», che non si puo' diagnosticare.
    """

    def _accedi_admin(self):
        self.client.cookies.clear()
        self.client.get("/login")
        self.client.post("/login", data={
            "username": "riccardo", "password": "password-admin-di-collaudo",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)

    def test_lanonimo_non_puo_far_partire_email(self):
        self.client.cookies.clear()
        r = self.client.post("/catalogo/email/prova", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("/login", r.headers["location"])

    def test_lerrore_vero_si_vede(self):
        """E' il punto: qui non c'e' niente da proteggere — chi preme e'
        gia' collegato e il destinatario e' l'amministratore."""
        self._accedi_admin()
        with patch("core.mail._invia_davvero",
                   return_value=(False, "535 Username and Password not accepted")):
            pagina = self.client.post("/catalogo/email/prova").text
        self.assertIn("Invio non riuscito", pagina)
        self.assertIn("535", pagina)

    def test_linvio_riuscito_lo_dice(self):
        self._accedi_admin()
        with patch("core.mail._invia_davvero", return_value=(True, "")):
            pagina = self.client.post("/catalogo/email/prova").text
        self.assertIn("Email di prova inviata", pagina)

    def test_lesito_resta_scritto_nella_diagnostica(self):
        """Cosi' si vede anche l'esito di un invio VERO — quello del
        recupero password — che nessuno aveva potuto guardare."""
        from core import mail

        with patch("core.mail._invia_davvero",
                   return_value=(False, "connessione rifiutata")):
            mail.invia("qualcuno@example.com", "o", "c")
        ultimo = mail.ultimo_invio()
        self.assertFalse(ultimo["ok"])
        self.assertEqual(ultimo["destinatario"], "qualcuno@example.com")
        self.assertIn("connessione rifiutata", ultimo["messaggio"])


if __name__ == "__main__":
    unittest.main()
