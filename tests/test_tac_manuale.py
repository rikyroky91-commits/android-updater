"""Inserimento del modello dentro l'app e verifica su più siti."""
from __future__ import annotations

import unittest

from core import imeicheck, storage


class TestLinkDiVerifica(unittest.TestCase):
    """Più di un sito, di proposito: hanno cataloghi diversi e un TAC
    assente da uno si trova spesso nell'altro."""

    def test_ce_ne_sono_diversi(self):
        self.assertGreaterEqual(len(imeicheck.link_verifica("351355315430630")), 3)

    def test_l_imei_finisce_solo_dove_serve(self):
        link = dict((n, u) for n, u, _ in imeicheck.link_verifica("351355315430630"))
        self.assertIn("351355315430630", link["imei.info"])
        # Gli altri sono pagine di ricerca: nessun identificativo nell'URL.
        self.assertNotIn("351355315430630", link["HiCellTek"])

    def test_url_ben_formati(self):
        for nome, url, nota in imeicheck.link_verifica("351355315430630"):
            with self.subTest(sito=nome):
                self.assertTrue(url.startswith("http"))
                self.assertTrue(nota)


class TestInserimentoManuale(unittest.TestCase):

    def setUp(self):
        storage.reset_state()
        storage.init_db()
        imeicheck.reset_cache()
        # Nessun download: qui si prova ciò che l'utente inserisce a mano.
        self._download = imeicheck._download
        self._scarica_url = imeicheck._scarica_url
        imeicheck._download = lambda: None
        imeicheck._scarica_url = lambda url, minimo=10_000: None

    def tearDown(self):
        imeicheck._download = self._download
        imeicheck._scarica_url = self._scarica_url
        storage.reset_state()
        imeicheck.reset_cache()

    def test_salva_e_ritrova(self):
        self.assertTrue(imeicheck.aggiungi_tac("35135531", "Samsung", "Galaxy A54 5G"))
        self.assertEqual(imeicheck.identify("351355315430630"),
                         ("Samsung", "Galaxy A54 5G"))

    def test_vale_per_tutti_gli_imei_dello_stesso_modello(self):
        """Si salva il TAC, non l'IMEI: le altre sette cifre identificano
        il singolo esemplare e non c'entrano col modello."""
        imeicheck.aggiungi_tac("35135531", "Samsung", "Galaxy A54 5G")
        self.assertIsNotNone(imeicheck.identify("351355319999995"))

    def test_serve_almeno_marca_o_modello(self):
        self.assertFalse(imeicheck.aggiungi_tac("35135531", "", ""))

    def test_un_tac_malformato_viene_rifiutato(self):
        self.assertFalse(imeicheck.aggiungi_tac("123", "Samsung", "X"))
        self.assertFalse(imeicheck.aggiungi_tac("", "Samsung", "X"))

    def test_accetta_l_imei_intero_e_ne_tiene_le_prime_otto(self):
        self.assertTrue(imeicheck.aggiungi_tac("351355315430630", "Samsung", "X"))
        self.assertIn("35135531", imeicheck.tac_inseriti())

    def test_si_puo_correggere_e_togliere(self):
        imeicheck.aggiungi_tac("35135531", "Samsung", "Sbagliato")
        imeicheck.aggiungi_tac("35135531", "Samsung", "Giusto")
        self.assertEqual(imeicheck.identify("351355315430630")[1], "Giusto")
        self.assertTrue(imeicheck.rimuovi_tac("35135531"))
        self.assertEqual(imeicheck.tac_inseriti(), {})

    def test_la_riga_per_il_file_e_pronta_da_incollare(self):
        riga = imeicheck.riga_csv("35135531", "Samsung", "Galaxy A54 5G")
        self.assertEqual(riga.split(",")[:3], ["35135531", "Samsung", "Galaxy A54 5G"])


class TestLeFontiLocaliSopravvivonoAlDownload(unittest.TestCase):
    """Il difetto trovato scrivendo questa funzione.

    Se il database scaricato non era disponibile, `_build_index` usciva
    subito — e con lei sparivano anche la tabella verificata a mano e i
    TAC inseriti nell'app, che col download non c'entrano niente. Bastava
    un'ora senza rete perché l'app dimenticasse dati che aveva in casa.
    """

    def setUp(self):
        storage.reset_state()
        storage.init_db()
        imeicheck.reset_cache()
        self._cache = imeicheck._cached_bytes
        imeicheck._cached_bytes = lambda: None

    def tearDown(self):
        imeicheck._cached_bytes = self._cache
        storage.reset_state()
        imeicheck.reset_cache()

    def test_senza_download_i_dati_locali_valgono_lo_stesso(self):
        imeicheck.aggiungi_tac("35135531", "Samsung", "Galaxy A54 5G")
        self.assertEqual(imeicheck.identify("351355315430630"),
                         ("Samsung", "Galaxy A54 5G"))

    def test_lo_stato_dice_quanti_ne_hai_inseriti(self):
        imeicheck.aggiungi_tac("35135531", "Samsung", "X")
        imeicheck.identify("351355315430630")
        self.assertIn("inserito da te", imeicheck.status())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestQuelloCheInsegniNonDeveMorireColContenitore(unittest.TestCase):
    """«non puoi fare inserimenti manuali tu stesso?», 07/09/2026.

    No, non i TAC: le otto cifre le assegna la GSMA e non si deducono dal
    codice modello. Inventarle vorrebbe dire far rispondere l'app con
    sicurezza a un IMEI vero dando il telefono sbagliato — peggio di «non
    lo so», e il contrario della riga in fondo a ogni pagina.

    Chi PUÒ inserirli è chi ha il telefono in mano, e lo fa già dalla
    pagina dell'IMEI. Il difetto era cosa succede dopo: quei TAC finiscono
    in `tracker.db`, che su Render vive in `/tmp`. `riga_csv` esisteva
    apposta per riportarli nel repository ma non la chiamava nessuno, e la
    promessa nel commento di `_META_TAC_UTENTE` — «l'app mostra comunque
    la riga da incollare nel CSV» — non era mantenuta.
    """

    def setUp(self):
        import tempfile

        from core import config as C, storage

        self._db = C.DB_PATH
        C.DB_PATH = tempfile.mktemp(suffix=".db")
        storage.reset_state()
        storage.init_db()
        imeicheck.reset_cache()

        def rimetti():
            C.DB_PATH = self._db
            storage.reset_state()
            imeicheck.reset_cache()

        self.addCleanup(rimetti)

    def test_senza_inserimenti_non_si_esporta_un_file_vuoto(self):
        """Un file con la sola intestazione sembrerebbe un'esportazione
        riuscita e vuota, che è un'altra cosa da «non c'era niente»."""
        self.assertEqual(imeicheck.esporta_tac_inseriti(), "")

    def test_l_esportazione_e_un_pezzo_del_file_curato(self):
        imeicheck.aggiungi_tac("35139740", "Samsung", "Galaxy A56 5G")
        testo = imeicheck.esporta_tac_inseriti()
        self.assertIn("tac,marca,modello,nota", testo)
        self.assertIn("35139740,Samsung,Galaxy A56 5G,verificato a mano", testo)

    def test_e_si_rilegge_con_lo_stesso_lettore_del_repository(self):
        """È il collaudo che conta: quello che esce da qui deve poter
        essere incollato in `data/tac_modelli.csv` e ritrovato uguale.
        Un'esportazione che il lettore non riprende è carta straccia."""
        imeicheck.aggiungi_tac("35139740", "Samsung", "Galaxy A56 5G")
        imeicheck.aggiungi_tac("86558708", "HONOR", "HONOR 400 Pro")
        riletti = imeicheck.carica_tac_curati(imeicheck.esporta_tac_inseriti())
        self.assertEqual(riletti, {"35139740": ("Samsung", "Galaxy A56 5G"),
                                   "86558708": ("HONOR", "HONOR 400 Pro")})

    def test_una_virgola_nel_nome_non_spezza_la_riga(self):
        """«Galaxy A56 5G, SM-A566B» è esattamente la forma che il
        database TAC usa, ed è quella che si incolla nel campo."""
        imeicheck.aggiungi_tac("35139740", "Samsung", "Galaxy A56 5G, SM-A566B")
        riletti = imeicheck.carica_tac_curati(imeicheck.esporta_tac_inseriti())
        self.assertEqual(riletti["35139740"],
                         ("Samsung", "Galaxy A56 5G, SM-A566B"))

    def test_si_sa_quali_sono_gia_al_sicuro(self):
        """Senza, l'elenco da incollare crescerebbe per sempre e chi lo
        guarda non saprebbe quali righe ha già messo dentro."""
        imeicheck.aggiungi_tac("35139740", "Samsung", "Galaxy A56 5G")
        self.assertEqual(imeicheck.tac_inseriti_gia_curati(), [])
        # Un TAC che sta anche nel file del repository: il lavoro è salvo.
        curato = imeicheck._indice_curato()
        if curato:
            gia = sorted(curato)[0]
            imeicheck.aggiungi_tac(gia, "Marca", "Modello")
            self.assertIn(gia, imeicheck.tac_inseriti_gia_curati())

    def test_l_ordine_e_stabile(self):
        """Un'esportazione che cambia ordine a ogni giro produce un diff
        illeggibile in ogni commit."""
        for tac in ("86558708", "35139740", "01620200"):
            imeicheck.aggiungi_tac(tac, "M", "X")
        righe = [r for r in imeicheck.esporta_tac_inseriti().splitlines()
                 if r and not r.startswith(("#", "tac,"))]
        self.assertEqual([r.split(",")[0] for r in righe],
                         ["01620200", "35139740", "86558708"])
