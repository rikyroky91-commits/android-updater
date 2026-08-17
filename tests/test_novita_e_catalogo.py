"""La pagina Novità, e la fusione di Catalogo e Diagnostica dietro login.

Richiesta dell'utente il 16/08/2026: «le sezioni catalogo e diagnostica
uniscile e lasciale sotto accesso tramite account. Riformula pure
dispositivi e aggiornamenti facendo qualcosa di più utile come una
pagina che raccoglie le ultime notizie riguardo gli update facendo un
riassunto della notizia e dando il link della fonte».
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AVVIA_WORKER"] = "0"


class _SitoNuovo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cartella = tempfile.mkdtemp(prefix="novita-")
        os.environ["DB_PATH"] = os.path.join(cartella, "test.db")
        os.environ["ADMIN_USERNAME"] = "capo"
        os.environ["ADMIN_EMAIL"] = "capo@example.com"
        os.environ["ADMIN_PASSWORD"] = "password-di-collaudo-lunga"

        from core import config as C, storage

        C.DB_PATH = os.environ["DB_PATH"]
        C.COOKIE_SECURE = False
        storage.reset_state()
        storage.init_db()
        storage.upsert_update({
            "id": "prova|galaxy|uno",
            "brand": "Samsung", "device_model": "Galaxy S24",
            "device_key": "samsung|galaxys24",
            "title": "Galaxy S24 riceve One UI 8",
            "summary": "Samsung ha avviato il rollout in Europa con la patch di agosto.",
            "link": "https://esempio.invalid/notizia",
            "build": "S921BXXU5C", "os_version": "Android 16",
            "source": "sammobile", "source_label": "SamMobile",
            "severity": "SECURITY", "color": "#cc0000",
            "published": "2026-08-15T10:00:00+00:00", "is_relevant": 1,
        })

        from fastapi.testclient import TestClient

        from web import account
        from web.main import app

        account.assicura_admin()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        for chiave in ("ADMIN_USERNAME", "ADMIN_EMAIL", "ADMIN_PASSWORD"):
            os.environ.pop(chiave, None)

    def _accedi(self):
        self.client.cookies.clear()
        self.client.get("/login")
        self.client.post("/login", data={
            "username": "capo", "password": "password-di-collaudo-lunga",
            "next": "/parco", "csrf": self.client.cookies.get("csrf_token"),
        }, follow_redirects=False)


class TestPaginaNovita(_SitoNuovo):
    def test_mostra_titolo_riassunto_e_link_alla_fonte(self):
        """E' la ragione per cui la pagina esiste: una tabella di sette
        colonne diceva DI COSA parla una notizia, non COSA dice."""
        self.client.cookies.clear()
        pagina = self.client.get("/novita?giorni=90").text
        self.assertIn("Galaxy S24 riceve One UI 8", pagina)
        self.assertIn("rollout in Europa", pagina)
        self.assertIn("https://esempio.invalid/notizia", pagina)
        self.assertIn("SamMobile", pagina)

    def test_resta_pubblica(self):
        """Sapere se e' uscito un aggiornamento non deve richiedere un
        account: e' lo scopo del progetto."""
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/novita", follow_redirects=False).status_code, 200)

    def test_il_vecchio_indirizzo_porta_ancora_qui(self):
        """«Aggiornamenti» e' stato in navigazione per mesi: i segnalibri
        di chi lo usava non devono rompersi."""
        self.client.cookies.clear()
        r = self.client.get("/aggiornamenti", follow_redirects=False)
        self.assertEqual(r.status_code, 301)
        self.assertIn("/novita", r.headers["location"])

    def test_si_filtra_per_marca(self):
        self.client.cookies.clear()
        pagina = self.client.get("/novita?giorni=90&marca=Samsung").text
        self.assertIn("Galaxy S24 riceve One UI 8", pagina)
        vuota = self.client.get("/novita?giorni=90&marca=Nokia").text
        self.assertNotIn("Galaxy S24 riceve One UI 8", vuota)


class TestCatalogoUnitoDietroLogin(_SitoNuovo):
    def test_lanonimo_non_entra(self):
        self.client.cookies.clear()
        for percorso in ("/catalogo", "/dispositivi", "/dispositivi-elenco"):
            with self.subTest(percorso=percorso):
                r = self.client.get(percorso, follow_redirects=False)
                self.assertEqual(r.status_code, 303)
                self.assertIn("/login", r.headers["location"])

    def test_il_vecchio_indirizzo_della_diagnostica_porta_al_catalogo(self):
        self.client.cookies.clear()
        r = self.client.get("/diagnostica", follow_redirects=False)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.headers["location"], "/catalogo")

    def test_collegato_vede_le_due_cose_insieme(self):
        """Erano due voci di menu che rispondevano alla stessa domanda:
        «com'e' messo il servizio»."""
        self._accedi()
        pagina = self.client.get("/catalogo").text
        self.assertIn("Versione in produzione", pagina)   # era la Diagnostica
        self.assertIn("Elenco dei dispositivi", pagina)   # era il Catalogo

    def test_le_azioni_di_backup_non_sono_piu_pubbliche(self):
        """ERANO RAGGIUNGIBILI DA CHIUNQUE. Una POST non ha bisogno della
        pagina che la contiene per essere chiamata, e queste due creano
        un archivio da un token GitHub incollato nel modulo, oppure
        forzano un salvataggio."""
        self.client.cookies.clear()
        for percorso in ("/catalogo/backup/crea", "/catalogo/backup/salva"):
            with self.subTest(percorso=percorso):
                r = self.client.post(percorso, data={"token": "ghp_finto"},
                                     follow_redirects=False)
                self.assertEqual(r.status_code, 303)
                self.assertIn("/login", r.headers["location"])

    def test_la_navigazione_mostra_il_catalogo_solo_a_chi_e_collegato(self):
        self.client.cookies.clear()
        self.assertNotIn('href="/catalogo"', self.client.get("/novita").text)
        self._accedi()
        self.assertIn('href="/catalogo"', self.client.get("/novita").text)


class TestLetturaSuSchermoStretto(_SitoNuovo):
    """Rifiniture nate guardando la pagina su un telefono, non sul
    portatile: «sembra tutto confuso», 17/08/2026."""

    def test_i_filtri_di_marca_stanno_chiusi(self):
        """Sette voci lunghe («Oppo / Realme / OnePlus») occupavano mezza
        schermata PRIMA della prima notizia. Chi apre questa pagina vuole
        leggere le novita', non scegliere un filtro."""
        self.client.cookies.clear()
        pagina = self.client.get("/novita?giorni=90").text
        self.assertIn("<details", pagina)
        self.assertIn("filtro-marca", pagina)
        # Chiuso non deve nascondere QUALE filtro e' attivo.
        self.assertIn("Marca:", pagina)

    def test_il_filtro_attivo_apre_il_pannello(self):
        """Se un filtro c'e', chiuderlo lo renderebbe invisibile: si
        vedrebbe un elenco corto senza capire perche'."""
        self.client.cookies.clear()
        pagina = self.client.get("/novita?giorni=90&marca=Samsung").text
        self.assertIn("<details class=\"filtro-marca\" open>", pagina)

    def test_la_fonte_non_compare_due_volte(self):
        """Visto sullo screenshot: «GSMArena · patch di sicurezza» sopra e
        «Multi-brand — GSMArena» sotto, in quattro righe."""
        from web.presenters import voce_feed

        v = voce_feed({"title": "prova", "size_info": "GSMArena",
                       "severity_reason": "patch di sicurezza",
                       "source_label": "Multi-brand — GSMArena"})
        self.assertNotIn("GSMArena", v["riassunto"])
        self.assertEqual(v["riassunto"], "patch di sicurezza")
        self.assertTrue(v["riassunto_di_servizio"])

    def test_la_versione_non_si_ripete(self):
        """Per una patch, `os_version` vale gia' «Patch 2026-08» e
        `patch_level` «2026-08»: usciva «Patch 2026-08 · patch 2026-08»."""
        from web.presenters import voce_feed

        v = voce_feed({"title": "x", "os_version": "Patch 2026-08",
                       "patch_level": "2026-08"})
        self.assertEqual(v["versione"], "Patch 2026-08")

    def test_la_coda_del_feed_non_finisce_nel_riassunto(self):
        """«The post <titolo> appeared first on <sito>» e' la firma che i
        plugin WordPress attaccano a ogni descrizione. Arrivava tagliata
        a meta' dal limite di caratteri e sembrava un guasto dell'app."""
        from web.presenters import voce_feed

        v = voce_feed({
            "title": "x",
            "summary": "La versione stabile e' vicina […] The post New One UI "
                       "9 beta appeared first on SamMobile.",
        })
        self.assertNotIn("The post", v["riassunto"])
        self.assertNotIn("[…]", v["riassunto"])
        self.assertTrue(v["riassunto"].endswith("vicina"))


if __name__ == "__main__":
    unittest.main()
