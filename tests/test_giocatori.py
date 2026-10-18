"""Gli account dei giocatori di Parry Brawl Survivor (18/10/2026).

Il sito del gioco (GitHub Pages) registra e fa entrare i giocatori su `/api/giocatore/*` e ci
tiene il salvataggio. Qui si controlla: registrazione e doppioni, accesso col nick e con
l'email, password sbagliata, salvataggio avanti e indietro, salvataggio troppo grande,
uscita che invalida il gettone, CORS dal sito del gioco, e che i giocatori non finiscano
fra gli utenti del tracker.
"""
from __future__ import annotations

import os
import tempfile
import unittest

PAGES = "https://rikyroky91-commits.github.io"


def _archivio_vuoto():
    cartella = tempfile.mkdtemp(prefix="giocatori-")
    os.environ["DB_PATH"] = os.path.join(cartella, "test.db")
    from core import config as C
    C.DB_PATH = os.environ["DB_PATH"]
    from core import storage
    storage.reset_state()


class TestGiocatori(unittest.TestCase):
    def setUp(self):
        _archivio_vuoto()
        from fastapi.testclient import TestClient

        from web import giocatori, main
        giocatori._TENTATIVI.clear()
        self.giocatori = giocatori
        self.client = TestClient(main.app)

    def registra(self, nick="Ricky 91", email="ricky@example.com", password="segretissima", ip="1.2.3.4"):
        return self.client.post("/api/giocatore/registra", json={"nick": nick, "email": email, "password": password},
                                headers={"X-Forwarded-For": ip})

    def accedi(self, login, password="segretissima", ip="1.2.3.4"):
        return self.client.post("/api/giocatore/accedi", json={"login": login, "password": password},
                                headers={"X-Forwarded-For": ip})

    @staticmethod
    def bearer(token):
        return {"Authorization": f"Bearer {token}"}

    def test_registrazione(self):
        r = self.registra()
        self.assertEqual(r.status_code, 200, r.text)
        corpo = r.json()
        self.assertEqual(set(corpo), {"token", "nick", "salvataggio"})
        self.assertEqual(corpo["nick"], "Ricky 91")
        self.assertIsNone(corpo["salvataggio"])
        self.assertGreater(len(corpo["token"]), 30)
        self.assertNotIn("ricky@example.com", r.text, "l'email non torna mai indietro")
        # Il gettone in chiaro non sta nell'archivio: solo il suo SHA-256.
        from core import storage
        righe = storage.connect().execute("SELECT gettone_hash FROM gettoni_giocatori").fetchall()
        self.assertEqual(len(righe), 1)
        self.assertNotEqual(righe[0][0], corpo["token"])
        self.assertEqual(righe[0][0], self.giocatori._hash_gettone(corpo["token"]))
        # La password è l'hash scrypt del tracker, non il testo.
        riga = storage.connect().execute("SELECT password_hash FROM giocatori").fetchone()
        self.assertTrue(riga[0].startswith("scrypt$"))

    def test_non_sono_utenti_del_tracker(self):
        self.assertEqual(self.registra().status_code, 200)
        from core import storage
        self.assertIsNone(storage.get_utente_per_username("Ricky 91"))
        self.assertIsNone(storage.get_utente_per_email("ricky@example.com"))
        self.assertFalse(storage.esiste_admin())

    def test_validazione(self):
        for male in [dict(nick="ab"), dict(nick="x" * 21), dict(nick="<script>"), dict(nick="Élodie"),
                     dict(email="senza-chiocciola"), dict(email="a@b"), dict(email=""),
                     dict(password="corta"), dict(password=12345678), dict(password="x" * 201)]:
            r = self.registra(**male)
            self.assertEqual(r.status_code, 400, repr(male))
            self.assertIn("errore", r.json())
        r = self.client.post("/api/giocatore/registra", content=b"non json", headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 400)

    def test_doppioni(self):
        self.assertEqual(self.registra().status_code, 200)
        r = self.registra(nick="RICKY 91", email="altra@example.com")
        self.assertEqual(r.status_code, 409, "il nick non distingue maiuscole")
        self.assertIn("errore", r.json())
        r = self.registra(nick="Altro", email="Ricky@Example.com")
        self.assertEqual(r.status_code, 409, "l'email non distingue maiuscole")
        self.assertEqual(self.registra(nick="Altro", email="altra@example.com").status_code, 200)

    def test_accesso_col_nick_e_con_l_email(self):
        self.registra()
        for login in ["Ricky 91", "ricky 91", "ricky@example.com", "RICKY@example.com"]:
            r = self.accedi(login)
            self.assertEqual(r.status_code, 200, login)
            corpo = r.json()
            self.assertEqual(set(corpo), {"token", "nick", "salvataggio", "aggiornato"})
            self.assertEqual(corpo["nick"], "Ricky 91")
            self.assertNotIn("example.com", r.text)
        # Ogni accesso ha il suo gettone, e funzionano tutti.
        t1, t2 = self.accedi("Ricky 91").json()["token"], self.accedi("Ricky 91").json()["token"]
        self.assertNotEqual(t1, t2)
        for t in (t1, t2):
            self.assertEqual(self.client.get("/api/giocatore/salvataggio", headers=self.bearer(t)).status_code, 200)

    def test_password_sbagliata_e_account_inesistente(self):
        self.registra()
        sbagliata = self.accedi("Ricky 91", password="non-e-questa")
        inesistente = self.accedi("Nessuno", password="segretissima")
        self.assertEqual(sbagliata.status_code, 401)
        self.assertEqual(inesistente.status_code, 401)
        self.assertEqual(sbagliata.json(), inesistente.json(), "stesso messaggio: non dice se l'account esiste")
        self.assertEqual(self.accedi("", password="").status_code, 401)

    def test_salvataggio_avanti_e_indietro(self):
        token = self.registra().json()["token"]
        vuoto = self.client.get("/api/giocatore/salvataggio", headers=self.bearer(token))
        self.assertEqual(vuoto.json(), {"nick": "Ricky 91", "salvataggio": None, "aggiornato": None})
        dati = {"crediti": 1200, "sbloccati": ["robot", "mela"], "impostazioni": {"volume": 0.7, "lingua": "it"},
                "nome": "Ünïcödé ✓"}
        r = self.client.put("/api/giocatore/salvataggio", json={"salvataggio": dati}, headers=self.bearer(token))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertTrue(r.json()["aggiornato"])
        letto = self.client.get("/api/giocatore/salvataggio", headers=self.bearer(token)).json()
        self.assertEqual(letto["salvataggio"], dati)
        self.assertEqual(letto["aggiornato"], r.json()["aggiornato"])
        # E torna anche all'accesso, da un altro dispositivo.
        accesso = self.accedi("ricky@example.com").json()
        self.assertEqual(accesso["salvataggio"], dati)
        self.assertEqual(accesso["aggiornato"], r.json()["aggiornato"])

    def test_salvataggio_non_valido_o_troppo_grande(self):
        token = self.registra().json()["token"]
        for male in [[1, 2, 3], "testo", 5, None]:
            r = self.client.put("/api/giocatore/salvataggio", json={"salvataggio": male}, headers=self.bearer(token))
            self.assertEqual(r.status_code, 400, repr(male))
        grande = {"pieno": "x" * (70 * 1024)}
        r = self.client.put("/api/giocatore/salvataggio", json={"salvataggio": grande}, headers=self.bearer(token))
        self.assertEqual(r.status_code, 413)
        self.assertIn("errore", r.json())
        # Appena sotto il tetto entra.
        quasi = {"pieno": "x" * (60 * 1024)}
        r = self.client.put("/api/giocatore/salvataggio", json={"salvataggio": quasi}, headers=self.bearer(token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/giocatore/salvataggio", headers=self.bearer(token)).json()["salvataggio"], quasi)

    def test_senza_gettone(self):
        for testa in [{}, {"Authorization": "Bearer "}, {"Authorization": "Bearer inventato"},
                      {"Authorization": "Basic abc"}]:
            self.assertEqual(self.client.get("/api/giocatore/salvataggio", headers=testa).status_code, 401)
            self.assertEqual(self.client.put("/api/giocatore/salvataggio", json={"salvataggio": {}},
                                             headers=testa).status_code, 401)

    def test_uscita_invalida_il_gettone(self):
        token = self.registra().json()["token"]
        altro = self.accedi("Ricky 91").json()["token"]
        r = self.client.post("/api/giocatore/esci", headers=self.bearer(token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(self.client.get("/api/giocatore/salvataggio", headers=self.bearer(token)).status_code, 401)
        self.assertEqual(self.client.post("/api/giocatore/esci", headers=self.bearer(token)).status_code, 401)
        # Gli altri dispositivi restano dentro.
        self.assertEqual(self.client.get("/api/giocatore/salvataggio", headers=self.bearer(altro)).status_code, 200)

    def test_gettone_scaduto(self):
        token = self.registra().json()["token"]
        from core import storage
        with storage.transaction() as conn:
            conn.execute("UPDATE gettoni_giocatori SET scade_il = '2000-01-01T00:00:00+00:00'")
        self.assertEqual(self.client.get("/api/giocatore/salvataggio", headers=self.bearer(token)).status_code, 401)

    def test_cors_dal_sito_del_gioco(self):
        for rotta, metodo in [("/api/giocatore/salvataggio", "PUT"), ("/api/giocatore/registra", "POST"),
                              ("/api/giocatore/accedi", "POST"), ("/api/giocatore/esci", "POST")]:
            pre = self.client.options(rotta, headers={"Origin": PAGES, "Access-Control-Request-Method": metodo,
                                                      "Access-Control-Request-Headers": "authorization, content-type"})
            self.assertEqual(pre.status_code, 204, rotta)
            self.assertEqual(pre.headers["access-control-allow-origin"], PAGES)
            self.assertIn(metodo, pre.headers["access-control-allow-methods"])
            ammesse = pre.headers["access-control-allow-headers"].lower()
            self.assertIn("authorization", ammesse)
            self.assertIn("content-type", ammesse)
        # Le risposte vere, anche gli errori, portano l'intestazione.
        r = self.client.post("/api/giocatore/registra", headers={"Origin": PAGES},
                             json={"nick": "Pagine", "email": "p@example.com", "password": "segretissima"})
        self.assertEqual(r.headers["access-control-allow-origin"], PAGES)
        self.assertEqual(self.client.get("/api/giocatore/salvataggio", headers={"Origin": PAGES})
                         .headers["access-control-allow-origin"], PAGES)
        # In locale per le prove.
        for locale in ["http://localhost:8765", "http://127.0.0.1:8765"]:
            pre = self.client.options("/api/giocatore/accedi", headers={"Origin": locale, "Access-Control-Request-Method": "POST"})
            self.assertEqual(pre.headers["access-control-allow-origin"], locale)
        # Un'altra origine no.
        pre = self.client.options("/api/giocatore/accedi", headers={"Origin": "https://malintenzionato.example",
                                                                    "Access-Control-Request-Method": "POST"})
        self.assertNotIn("access-control-allow-origin", pre.headers)

    def test_limite_per_indirizzo(self):
        self.registra()
        for _ in range(15):
            self.assertEqual(self.accedi("Ricky 91", password="sbagliata!", ip="7.7.7.7").status_code, 401)
        self.assertEqual(self.accedi("Ricky 91", ip="7.7.7.7").status_code, 429)
        self.assertEqual(self.accedi("Ricky 91", ip="8.8.8.8").status_code, 200, "un altro indirizzo entra")
        for i in range(4):
            self.assertEqual(self.registra(nick=f"Nuovo{i}", email=f"n{i}@example.com", ip="9.9.9.9").status_code, 200)
        self.assertEqual(self.registra(nick="Nuovo9", email="n9@example.com", ip="9.9.9.9").status_code, 200)
        self.assertEqual(self.registra(nick="Nuovo10", email="n10@example.com", ip="9.9.9.9").status_code, 429)


if __name__ == "__main__":
    unittest.main()
