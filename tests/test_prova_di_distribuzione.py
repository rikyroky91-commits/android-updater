"""Il filtro anti-rumore chiede una prova che qualcosa sia stato distribuito.

IL DIFETTO. Nel punteggio, un modello riconosciuto vale 1 e una versione
Android vale 2: insieme fanno 3, cioè esattamente la soglia. Bastava quindi
che un titolo nominasse un telefono e un numero di Android — «Vivo X200 Pro
debuts with Android 15» — perché una ricerca generica di notizie lo
classificasse come rilascio e ne facesse un dispositivo in elenco.

Quei due segnali dicono di COSA parla l'articolo, non che sia successo
qualcosa. Ciò che distingue un rilascio da un articolo su un telefono è una
prova di distribuzione: un numero di build (esiste solo se il pacchetto
esiste), un livello di patch (è una data), o una frase che descrive un
rollout in corso.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import classify, config as C, extract, scan, sources, storage  # noqa: E402


def _rilevanza(testo, trust=C.TRUST_NOISY):
    return classify.score_relevance(testo, extract.extract_all(testo), trust)


class TestFonteRumorosa(unittest.TestCase):

    def test_modello_piu_versione_non_bastano_piu(self):
        """Il caso esatto che stava sulla soglia: 1 + 2 = 3."""
        r = _rilevanza("Vivo X200 Pro debuts with Android 15")
        self.assertEqual(r.score, 3, "il punteggio è cambiato: il test non prova più il caso limite")
        self.assertFalse(r.is_relevant)
        self.assertIn("prova di distribuzione", r.explanation)

    def test_la_parola_update_da_sola_non_basta(self):
        self.assertFalse(_rilevanza("Nothing Phone 3 Android 16 update").is_relevant)

    def test_un_numero_di_build_basta(self):
        """Un build number esiste solo se il pacchetto esiste: è la prova
        più forte disponibile, e vale anche senza nessuna frase di rollout."""
        self.assertTrue(_rilevanza("Galaxy S24 Ultra S928BXXU5CYA1").is_relevant)

    def test_un_livello_di_patch_basta(self):
        self.assertTrue(
            _rilevanza("Moto G14 July 2026 security patch").is_relevant)

    def test_una_frase_di_rollout_basta(self):
        self.assertTrue(
            _rilevanza("Galaxy S24 Ultra gets Android 16 update").is_relevant)
        self.assertTrue(
            _rilevanza("OnePlus 12 starts receiving the ColorOS 15 stable update").is_relevant)

    def test_i_feed_curati_non_sono_toccati(self):
        """Un feed dedicato agli aggiornamenti parla di rilasci per
        mestiere: la soglia più bassa è voluta, e stringerla qui avrebbe
        tolto dati veri per correggere un problema che non è suo."""
        self.assertTrue(
            _rilevanza("Galaxy A55 gets a new firmware in Europe", C.TRUST_CURATED).is_relevant)

    def test_le_fonti_strutturate_non_passano_dal_filtro(self):
        self.assertTrue(
            _rilevanza("marble — Stable OS2.0.1.0.VNCEUXM", C.TRUST_STRUCTURED).is_relevant)

    def test_lo_scarto_dice_perche(self):
        """Uno scarto silenzioso è indistinguibile da un guasto: la
        Diagnostica mostra questi motivi, e devono essere leggibili."""
        r = _rilevanza("Vivo X200 Pro debuts with Android 15")
        self.assertIn("build", r.explanation)
        self.assertIn("patch", r.explanation)


class TestNienteDispositivoFantasma(unittest.TestCase):
    """La conseguenza vera del filtro permissivo: un elenco di dispositivi
    popolato da telefoni di cui non si sa niente, nati da un titolo."""

    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale

    def _fonte_di_notizie(self, titoli):
        def fetch():
            return [sources.RawItem(title=t, link=f"https://x.test/{i}",
                                    published="2026-07-01", brand=C.VIVO)
                    for i, t in enumerate(titoli)], None
        return sources.Source("news_prova", "Ricerca di prova", C.TRUST_NOISY,
                              fetch, C.VIVO, "", is_web_search=True)

    def test_una_notizia_di_lancio_non_crea_un_dispositivo(self):
        scan.run_scan(auto_notify=False, only_sources=[self._fonte_di_notizie([
            "Vivo X200 Pro debuts with Android 15",
        ])])
        self.assertEqual(storage.get_devices(), [])

    def test_un_rollout_vero_lo_crea_ancora(self):
        scan.run_scan(auto_notify=False, only_sources=[self._fonte_di_notizie([
            "Vivo X200 Pro starts receiving the Android 15 update",
        ])])
        modelli = [d["model"] for d in storage.get_devices()]
        self.assertEqual(modelli, ["Vivo X200 Pro"])

    def test_lo_scarto_resta_visibile(self):
        """Nascondere ciò che il filtro scarta è il modo più efficace di
        rendere impossibile capire perché un modello non si trova: l'item
        resta in archivio, marcato, con la sua motivazione."""
        scan.run_scan(auto_notify=False, only_sources=[self._fonte_di_notizie([
            "Vivo X200 Pro debuts with Android 15",
        ])])
        scartati = storage.get_updates(only_relevant=False)
        self.assertEqual(len(scartati), 1)
        self.assertFalse(scartati[0]["is_relevant"])
        self.assertIn("prova di distribuzione", scartati[0]["relevance_note"])



class TestVersionePrecisaComeProva(unittest.TestCase):
    """Una versione di skin a TRE O PIU' parti vale quanto un numero di
    build: entrambi esistono solo se un pacchetto e' stato distribuito.

    La regola in `scan.normalize` chiede una PROVA di distribuzione, non
    letteralmente una build. Honor e vivo pubblicano le versioni in forma
    puntata («MagicOS 9.0.0.157», «Funtouch OS 14.0.1.2») e quasi mai un
    build number in stile Samsung: senza questa equivalenza il dato
    veniva estratto correttamente e poi buttato via.

    Misurato il 16/08/2026 su dieci modelli per marca: Honor dava un
    firmware su 1 modello su 10, vivo su 2 su 10.
    """

    def test_una_versione_a_tre_parti_e_una_prova(self):
        self.assertTrue(extract.versione_precisa("9.0.0.157"))
        self.assertTrue(extract.versione_precisa("14.0.1.2"))

    def test_una_versione_corta_non_lo_e(self):
        """«MagicOS 10» o «One UI 6.1» possono essere un annuncio, un
        elenco di modelli idonei o un'attesa: sono esattamente il caso che
        la regola anti-rumore esiste per fermare."""
        self.assertFalse(extract.versione_precisa("10"))
        self.assertFalse(extract.versione_precisa("6.1"))
        self.assertFalse(extract.versione_precisa(None))

    def test_la_versione_completa_si_estrae_per_intero(self):
        """Il gruppo si fermava a due parti e «9.0.0.157» diventava
        «9.0» — cioe' le due cifre che dimostrano il rilascio venivano
        tolte prima ancora di poter essere valutate."""
        e = extract.extract_all(
            "MagicOS 9.0.0.157 feature update rolling out for Honor Magic 7/6 series")
        self.assertEqual(e.skin_name, "MagicOS")
        self.assertEqual(e.skin_version, "9.0.0.157")

    def test_una_notizia_rumorosa_con_versione_precisa_tiene_la_versione(self):
        fonte = sources.Source(key="prova", label="Prova", trust=C.TRUST_NOISY, fetch=None)
        voce = scan.normalize(
            sources.RawItem(
                title="MagicOS 9.0.0.157 rolling out for Honor Magic6 Pro",
                link="https://esempio.invalid/1"),
            fonte)
        self.assertEqual(voce["skin_name"], "MagicOS")
        self.assertEqual(voce["skin_version"], "9.0.0.157")

    def test_una_notizia_rumorosa_con_versione_vaga_la_perde_ancora(self):
        """La difesa che ha prodotto «Samsung A32 - Android 14» resta in
        piedi: e' il caso per cui la regola e' nata."""
        fonte = sources.Source(key="prova", label="Prova", trust=C.TRUST_NOISY, fetch=None)
        voce = scan.normalize(
            sources.RawItem(
                title="Galaxy A32 will get Android 14 One UI 6",
                link="https://esempio.invalid/2"),
            fonte)
        self.assertFalse(voce["skin_version"])
        self.assertFalse(voce["os_version"])
        self.assertIsNone(voce["android_version"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
