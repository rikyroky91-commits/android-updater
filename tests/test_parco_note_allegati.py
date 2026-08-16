"""Note e allegati delle righe del parco di test, e il salvataggio
raggruppato che li porta nell'archivio esterno.

L'archivio esterno è un Gist, quindi qui c'è un finto GitHub in memoria
(`_GistFinto`) al posto di `requests`: si collauda che il contenuto ci
arrivi davvero codificato, che si rilegga uguale, e che una PATCH tocchi
solo il file che nomina — cioè che gli allegati non possano sovrascrivere
il salvataggio del database, che vive nello stesso Gist.
"""
import base64
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AVVIA_WORKER"] = "0"


class _RispostaFinta:
    def __init__(self, status_code, dati=None, testo=""):
        self.status_code = status_code
        self._dati = dati if dati is not None else {}
        self.text = testo

    def json(self):
        return self._dati


class _GistFinto:
    """Un Gist in memoria con la stessa forma di quello vero: un
    dizionario di file, dove una PATCH aggiunge/sostituisce solo le
    chiavi che nomina e `None` come valore cancella."""

    def __init__(self):
        self.files = {"tracker-db.sqlite.gz": {"content": "il-database-finto"}}
        self.patch_ricevute = 0
        # Sopra questa soglia il vero GitHub tronca il contenuto e
        # rimanda al raw_url: serve a collaudare quel ramo.
        self.soglia_troncamento = None

    def patch(self, url, headers=None, json=None, timeout=None):
        self.patch_ricevute += 1
        for nome, valore in (json or {}).get("files", {}).items():
            if valore is None:
                self.files.pop(nome, None)
            else:
                self.files[nome] = {"content": valore["content"]}
        return _RispostaFinta(200)

    def get(self, url, headers=None, timeout=None):
        if "raw" in url:
            nome = url.rsplit("/", 1)[-1]
            return _RispostaFinta(200, testo=self.files[nome]["content"])
        files = {}
        for nome, dati in self.files.items():
            voce = dict(dati)
            if (self.soglia_troncamento is not None
                    and len(dati["content"]) > self.soglia_troncamento):
                voce = {"content": dati["content"][:10], "truncated": True,
                        "raw_url": f"https://gist.invalid/raw/{nome}"}
            files[nome] = voce
        return _RispostaFinta(200, dati={"files": files})


class _ParcoConLogin(unittest.TestCase):
    """Un sito vero, un archivio vuoto, un amministratore collegato e un
    modello nel parco: il minimo per esercitare le rotte del parco, che
    sono tutte dietro login."""

    @classmethod
    def setUpClass(cls):
        cls.cartella = tempfile.mkdtemp(prefix="parco-")
        os.environ["DB_PATH"] = os.path.join(cls.cartella, "test.db")
        os.environ["ADMIN_USERNAME"] = "capo"
        os.environ["ADMIN_EMAIL"] = "capo@example.com"
        os.environ["ADMIN_PASSWORD"] = "password-di-collaudo-lunga"
        os.environ["BACKUP_GIST_ID"] = "gist-finto"
        os.environ["BACKUP_GITHUB_TOKEN"] = "token-finto"

        from core import config as C

        C.DB_PATH = os.environ["DB_PATH"]
        C.COOKIE_SECURE = False

        from core import storage

        storage.reset_state()
        storage.init_db()
        storage.add_to_watchlist("samsung|galaxy-s24", "Samsung", "Galaxy S24")
        storage.add_to_watchlist("google|pixel-9", "Google", "Pixel 9")

        from fastapi.testclient import TestClient

        from web import account
        from web.main import app

        account.assicura_admin()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        for chiave in ("ADMIN_USERNAME", "ADMIN_EMAIL", "ADMIN_PASSWORD",
                       "BACKUP_GIST_ID", "BACKUP_GITHUB_TOKEN"):
            os.environ.pop(chiave, None)

    def setUp(self):
        import shutil

        from core import allegati, storage

        # OGNI TEST PARTE DA ZERO ALLEGATI E ZERO NOTE. L'archivio è
        # condiviso dalla classe (crearne uno per test costerebbe un
        # `init_db` a testa), quindi senza questa pulizia un test
        # eredita gli allegati di quello prima e le sue asserzioni sui
        # conteggi diventano dipendenti dall'ordine alfabetico dei nomi
        # dei metodi — cioè verdi o rosse per motivi che non c'entrano
        # con quello che vogliono verificare.
        with storage.transaction() as conn:
            conn.execute("DELETE FROM allegati_parco")
            conn.execute("UPDATE watchlist SET note = ''")
        shutil.rmtree(allegati._cartella_cache(), ignore_errors=True)

        self.client.cookies.clear()
        self.client.get("/login")
        self.client.post("/login", data={
            "username": "capo", "password": "password-di-collaudo-lunga",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)

        self.gist = _GistFinto()
        self._requests_vere = allegati.requests
        allegati.requests = self.gist

    def tearDown(self):
        from core import allegati

        allegati.requests = self._requests_vere


class TestLaNota(_ParcoConLogin):
    def test_la_nota_si_salva_e_si_rilegge(self):
        risposta = self.client.post("/parco/nota", data={
            "chiave": "samsung|galaxy-s24",
            "nota": "Fotocamera lenta ad aprirsi dopo l'update",
        }, follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)
        self.assertIn("nota_salvata=1", risposta.headers["location"])

        pagina = self.client.get("/parco").text
        self.assertIn("Fotocamera lenta ad aprirsi dopo l&#39;update", pagina)

    def test_la_nota_torna_alla_ricerca_da_cui_si_era_partiti(self):
        # Chi stava guardando un parco filtrato non deve ritrovarsi
        # l'elenco intero dopo aver salvato una nota.
        risposta = self.client.post(
            "/parco/nota?q=galaxy&ordina=meno_recente",
            data={"chiave": "samsung|galaxy-s24", "nota": "una nota"},
            follow_redirects=False)
        destinazione = risposta.headers["location"]
        self.assertIn("q=galaxy", destinazione)
        self.assertIn("ordina=meno_recente", destinazione)

    def test_un_indirizzo_diventa_un_tasto_senza_mostrarsi_per_intero(self):
        self.client.post("/parco/nota", data={
            "chiave": "google|pixel-9",
            "nota": "Procedura completa su https://esempio.invalid/una-pagina-dal-nome-lunghissimo",
        }, follow_redirects=False)
        pagina = self.client.get("/parco").text

        self.assertIn('class="tasto-link"', pagina)
        self.assertIn(">Link</a>", pagina)
        # L'indirizzo c'è solo dentro href e title, mai come testo che
        # allarga la tabella.
        self.assertNotIn(
            ">https://esempio.invalid/una-pagina-dal-nome-lunghissimo<", pagina)
        self.assertIn('href="https://esempio.invalid/una-pagina-dal-nome-lunghissimo"', pagina)

    def test_una_nota_non_puo_iniettare_html(self):
        self.client.post("/parco/nota", data={
            "chiave": "google|pixel-9",
            "nota": "<script>alert(1)</script>",
        }, follow_redirects=False)
        pagina = self.client.get("/parco").text
        self.assertNotIn("<script>alert(1)</script>", pagina)
        self.assertIn("&lt;script&gt;", pagina)

    def test_riaggiungere_al_parco_non_cancella_la_nota(self):
        """`/parco/aggiungi` chiama `add_to_watchlist` con nota vuota:
        finché la nota non si vedeva, sovrascriverla non si notava."""
        from core import storage

        storage.imposta_nota_parco("samsung|galaxy-s24", "nota da non perdere")
        storage.add_to_watchlist("samsung|galaxy-s24", "Samsung", "Galaxy S24")

        voce = next(v for v in storage.get_watchlist()
                    if v["device_key"] == "samsung|galaxy-s24")
        self.assertEqual(voce["note"], "nota da non perdere")

    def test_una_nota_su_un_modello_fuori_dal_parco_non_crea_righe_fantasma(self):
        from core import storage

        prima = len(storage.get_watchlist())
        self.client.post("/parco/nota", data={
            "chiave": "marca|inesistente", "nota": "ciao",
        }, follow_redirects=False)
        self.assertEqual(len(storage.get_watchlist()), prima)


class TestGliAllegati(_ParcoConLogin):
    def _carica(self, nome="prova.png", tipo="image/png", contenuto=b"\x89PNG-finto",
                chiave="samsung|galaxy-s24"):
        return self.client.post(
            "/parco/allegato", data={"chiave": chiave},
            files={"file": (nome, contenuto, tipo)}, follow_redirects=False)

    def test_si_carica_si_riscarica_e_si_toglie(self):
        from core import storage

        risposta = self._carica(contenuto=b"contenuto-di-prova")
        self.assertIn("allegato_salvato=1", risposta.headers["location"])

        allegati_riga = storage.get_allegati_per_device()["samsung|galaxy-s24"]
        self.assertEqual(len(allegati_riga), 1)
        identificativo = allegati_riga[0]["id"]

        # Il contenuto è arrivato al Gist, codificato, in un file suo — e
        # il salvataggio del database che vive lì accanto è intatto.
        nomi = [n for n in self.gist.files if n.startswith("allegato-")]
        self.assertEqual(len(nomi), 1)
        self.assertEqual(base64.b64decode(self.gist.files[nomi[0]]["content"]),
                         b"contenuto-di-prova")
        self.assertEqual(self.gist.files["tracker-db.sqlite.gz"]["content"],
                         "il-database-finto")

        scaricato = self.client.get(f"/parco/allegato/{identificativo}")
        self.assertEqual(scaricato.status_code, 200)
        self.assertEqual(scaricato.content, b"contenuto-di-prova")

        self.client.post(f"/parco/allegato/{identificativo}/elimina",
                         follow_redirects=False)
        self.assertEqual(storage.get_allegati_per_device().get("samsung|galaxy-s24", []), [])
        self.assertFalse([n for n in self.gist.files if n.startswith("allegato-")])

    def test_si_riscarica_anche_quando_la_cache_locale_e_sparita(self):
        """Dopo un riavvio di Render `/tmp` è vuoto: il contenuto deve
        tornare dall'archivio esterno, non risultare perso."""
        from core import allegati, storage

        self._carica(contenuto=b"sopravvive-al-riavvio")
        identificativo = storage.get_allegati_per_device()["samsung|galaxy-s24"][0]["id"]

        impronta = storage.get_allegato(identificativo)["impronta"]
        os.remove(allegati._percorso_cache(impronta))

        scaricato = self.client.get(f"/parco/allegato/{identificativo}")
        self.assertEqual(scaricato.content, b"sopravvive-al-riavvio")

    def test_un_contenuto_troncato_dallapi_si_riprende_dal_raw_url(self):
        from core import allegati, storage

        self._carica(contenuto=b"un contenuto abbastanza lungo da essere troncato")
        identificativo = storage.get_allegati_per_device()["samsung|galaxy-s24"][0]["id"]
        impronta = storage.get_allegato(identificativo)["impronta"]
        os.remove(allegati._percorso_cache(impronta))
        self.gist.soglia_troncamento = 8

        scaricato = self.client.get(f"/parco/allegato/{identificativo}")
        self.assertEqual(scaricato.content,
                         b"un contenuto abbastanza lungo da essere troncato")

    def test_un_file_troppo_grande_e_rifiutato_con_il_motivo(self):
        from core import config as C

        troppo = b"x" * (C.ALLEGATI_MAX_MB * 1024 * 1024 + 1)
        risposta = self._carica(contenuto=troppo)
        self.assertIn("errore_allegato", risposta.headers["location"])
        self.assertNotIn("allegato_salvato", risposta.headers["location"])
        # Niente è finito nell'archivio esterno.
        self.assertFalse([n for n in self.gist.files if n.startswith("allegato-")])

    def test_un_tipo_non_ammesso_e_rifiutato(self):
        risposta = self._carica(nome="brutto.exe", tipo="application/x-msdownload",
                                contenuto=b"MZ")
        self.assertIn("errore_allegato", risposta.headers["location"])

    def test_lo_stesso_file_su_due_modelli_occupa_un_posto_solo(self):
        from core import storage

        self._carica(contenuto=b"identico", chiave="samsung|galaxy-s24")
        self._carica(contenuto=b"identico", chiave="google|pixel-9")

        nomi = [n for n in self.gist.files if n.startswith("allegato-")]
        self.assertEqual(len(nomi), 1, "due file identici devono condividere il contenuto")

        # Togliendolo da un modello, l'altro deve restare leggibile: il
        # contenuto si cancella solo quando nessuno lo nomina più.
        primo = storage.get_allegati_per_device()["samsung|galaxy-s24"][0]["id"]
        self.client.post(f"/parco/allegato/{primo}/elimina", follow_redirects=False)

        secondo = storage.get_allegati_per_device()["google|pixel-9"][0]["id"]
        scaricato = self.client.get(f"/parco/allegato/{secondo}")
        self.assertEqual(scaricato.content, b"identico")

    def test_gli_allegati_sono_dietro_login_come_il_resto_del_parco(self):
        from core import storage

        self._carica(contenuto=b"riservato")
        identificativo = storage.get_allegati_per_device()["samsung|galaxy-s24"][0]["id"]

        self.client.cookies.clear()
        risposta = self.client.get(f"/parco/allegato/{identificativo}",
                                   follow_redirects=False)
        self.assertEqual(risposta.status_code, 303)
        self.assertEqual(risposta.headers["location"], "/login?next=/parco")

    def test_oltre_il_limite_per_modello_non_si_aggiunge(self):
        from core import config as C

        vecchio = C.ALLEGATI_MAX_PER_MODELLO
        C.ALLEGATI_MAX_PER_MODELLO = 2
        try:
            self._carica(contenuto=b"uno")
            self._carica(contenuto=b"due")
            risposta = self._carica(contenuto=b"tre")
            self.assertIn("errore_test=troppi_allegati", risposta.headers["location"])
        finally:
            C.ALLEGATI_MAX_PER_MODELLO = vecchio


class TestGliAllegatiSeguonoLaChiave(unittest.TestCase):
    """`migra_chiavi_dispositivo` riscrive le chiavi del parco quando la
    regola che le genera cambia. `allegati_parco` è indicizzata per
    chiave come il parco: se la migrazione non la tocca, gli allegati
    restano agganciati a una chiave che non esiste più e spariscono dalla
    riga pur essendo ancora nell'archivio esterno — lo stesso guasto che
    il docstring di quella funzione descrive per il parco di test.
    """

    def setUp(self):
        cartella = tempfile.mkdtemp(prefix="migrazione-")
        os.environ["DB_PATH"] = os.path.join(cartella, "test.db")

        from core import config as C

        C.DB_PATH = os.environ["DB_PATH"]

        from core import storage

        storage.reset_state()
        storage.init_db()

    def test_una_migrazione_di_chiave_si_porta_dietro_gli_allegati(self):
        from core import storage

        # Una chiave in una forma che la regola corrente NON produce:
        # è la situazione di un archivio scritto da una versione
        # precedente del progetto.
        vecchia = "SAMSUNG|Galaxy S24 Ultra"
        storage.add_to_watchlist(vecchia, "Samsung", "Galaxy S24 Ultra")
        storage.aggiungi_allegato(vecchia, "foto.png", "image/png", 10, "cc" * 32)
        storage.set_meta(storage._CHIAVI_KEY, "forza-la-migrazione")

        storage.migra_chiavi_dispositivo()

        chiavi_parco = {v["device_key"] for v in storage.get_watchlist()}
        # Senza questo, il test passerebbe a vuoto il giorno in cui la
        # regola smettesse di cambiare quella chiave: non starebbe più
        # collaudando una migrazione, ma il fatto che non ne serva una.
        self.assertNotIn(vecchia, chiavi_parco,
                         "la chiave doveva cambiare: il test non prova nulla se resta uguale")

        chiavi_allegati = set(storage.get_allegati_per_device())
        self.assertEqual(
            chiavi_allegati, chiavi_parco,
            "gli allegati devono restare sulla stessa chiave della riga del parco")


class TestSalvataggioRaggruppato(unittest.TestCase):
    """La richiesta era «salva a ogni click». Il costo vero è che ogni
    salvataggio ricarica l'INTERO database (~7,6 MB in base64), quindi
    dieci click sarebbero dieci invii: qui si verifica che una raffica di
    modifiche diventi un invio solo, e che nessuna resti fuori."""

    def setUp(self):
        from core import backup

        self._salva_vera = backup.salva
        self._configurato_vero = backup.configurato
        self._ritardo_vero = backup.RITARDO_SALVATAGGIO
        self.salvataggi = []
        self.avvenuto = threading.Event()

        def salva_finta():
            self.salvataggi.append(time.monotonic())
            self.avvenuto.set()
            return True, "ok (finto)"

        backup.salva = salva_finta
        backup.configurato = lambda: True

    def tearDown(self):
        from core import backup

        backup.ferma_salvataggio_continuo(attesa=5)
        backup.salva = self._salva_vera
        backup.configurato = self._configurato_vero
        backup.RITARDO_SALVATAGGIO = self._ritardo_vero

    def test_dieci_modifiche_ravvicinate_diventano_un_salvataggio_solo(self):
        from core import backup

        backup.RITARDO_SALVATAGGIO = 1
        backup.avvia_salvataggio_continuo()
        for _ in range(10):
            backup.segna_modificato()

        self.assertTrue(self.avvenuto.wait(timeout=10))
        time.sleep(1.5)  # lascia passare un'eventuale seconda finestra
        self.assertEqual(len(self.salvataggi), 1,
                         f"attesa una sola chiamata a salva(), fatte {len(self.salvataggi)}")

    def test_senza_modifiche_non_salva_niente(self):
        from core import backup

        backup.RITARDO_SALVATAGGIO = 0
        backup.avvia_salvataggio_continuo()
        time.sleep(1)
        self.assertEqual(self.salvataggi, [])

    def test_larresto_non_si_porta_via_una_modifica_in_sospeso(self):
        from core import backup

        # Ritardo lungo: senza il salvataggio all'arresto, la modifica
        # appena segnata non farebbe in tempo a partire.
        backup.RITARDO_SALVATAGGIO = 300
        backup.avvia_salvataggio_continuo()
        backup.segna_modificato()
        backup.ferma_salvataggio_continuo(attesa=10)
        self.assertEqual(len(self.salvataggi), 1)


if __name__ == "__main__":
    unittest.main()
