"""Il costo di una ricerca, e le due regole che lo tengono onesto.

Questo file collauda cose che non si vedono guardando il risultato: quante
volte una fonte viene scaricata, e quali risposte vengono scartate perché
riguardano un altro telefono. Sono le due facce dello stesso lavoro — a
cache fredde una ricerca sforava il budget di dodici secondi e rispondeva
«nessuna fonte conosce questo modello» per pura scadenza del tempo.

Nessun test qui tocca la rete: `http_get` è sostituito da un contatore.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C  # noqa: E402

C.DB_PATH = os.path.join(tempfile.mkdtemp(prefix="veloce-"), "t.db")
os.environ["TRACKER_DB"] = C.DB_PATH

from core import sources, storage  # noqa: E402

storage.reset_state()
storage.init_db()


class _Risposta:
    status_code = 200

    def __init__(self, testo=""):
        self.text = testo
        self.encoding = "utf-8"

    def json(self):
        return {}


# PAGINE CHE I PARSER ACCETTANO, non testo qualsiasi. È un dettaglio che
# ha fatto fallire la prima stesura di questo file: un guasto NON viene
# messo in cache (di proposito — vedi `_CacheDiFonte.ottieni`), quindi una
# pagina illeggibile fa riscaricare ogni volta e i test sul numero di
# richieste misurerebbero l'esatto contrario di quello che affermano.
# Le forme qui sotto sono le stesse usate in `test_core`.
_PAGINA_HONOR = ("<div><p>HONOR X8c</p><p>01/2027 at least（Global）</p>"
                 "<p>Shipped version: 15</p>"
                 "<p>Future version: 16 at least（Global）</p></div>")
_PAGINA_REALME = (
    "<html><body><table>"
    "<tr><td>realme 14 5G</td><td>Security update support end date: 5/2031</td>"
    "<td>Shipped version: Android 15<br/>Future version: Android 16</td></tr>"
    "</table></body></html>")
_PAGINA_VIVO = (
    '<table><tr class="table-content"><td>X300 Ultra</td>'
    "<td>End date: 07/2031</td><td>Shipped version: Android 16</td></tr></table>")
_PAGINA_PIXEL = ("<html><body><p>Pixel 9 Pro</p>"
                 "<p>caiman_beta-ota-bp11.250404.001-a1b2c3d4.zip</p>"
                 "<p>Release date | April 15, 2026</p></body></html>")


class _ConContatore(unittest.TestCase):
    """Sostituisce `http_get` con un contatore per URL."""

    def setUp(self):
        self.chiamate = []
        self._vero = sources.http_get
        sources.http_get = self._contato
        sources.azzera_cache_fonti()
        self.addCleanup(self._ripristina)

    def _ripristina(self):
        sources.http_get = self._vero
        sources.azzera_cache_fonti()

    def _pagina_per(self, url: str) -> str:
        if "honor.com" in url:
            return _PAGINA_HONOR
        if "realme.com" in url:
            return _PAGINA_REALME
        if "vivo.com" in url:
            return _PAGINA_VIVO
        if "android.com" in url or "google.com" in url:
            return _PAGINA_PIXEL
        return "<html><body><p>niente di riconoscibile</p></body></html>"

    def _contato(self, url, timeout=None, headers=None):
        self.chiamate.append(url)
        return _Risposta(self._pagina_per(url))

    def quante(self, pezzo: str) -> int:
        return sum(1 for u in self.chiamate if pezzo in u)


class TestUnaFonteSiScaricaUnaVoltaSola(_ConContatore):
    """Ogni catalogo va scaricato una volta per ricerca, non una per forma.

    `lookup_model_structured` interroga ogni fonte con TUTTE le forme
    equivalenti della domanda (per «c63» sono cinque). Senza cache ogni
    forma rifà il giro: è così che la fonte Pixel arrivava a consumare da
    sola 6,9 dei 12 secondi di budget, in una ricerca che con i Pixel non
    c'entrava niente.
    """

    def test_pixel_una_volta_sola(self):
        """La fonte che pesava di più: 6,9 secondi su 12, in cinque
        chiamate, cercando un realme."""
        for _ in range(4):
            items, errore = sources.fetch_pixel_ota()
        self.assertIsNone(errore, "la pagina di prova deve essere leggibile, "
                                  "o un guasto non messo in cache falserebbe il conto")
        self.assertLessEqual(self.quante("developer.android.com")
                             + self.quante("developers.google.com"), 1)

    def test_realme_una_volta_sola(self):
        for _ in range(4):
            sources.fetch_realme_aer()
        self.assertLessEqual(self.quante("realme.com"), 1)

    def test_honor_e_vivo_una_volta_sola(self):
        for _ in range(3):
            sources.fetch_honor_aer()
            sources.fetch_vivo_aer()
        self.assertLessEqual(self.quante("honor.com"), 1)
        self.assertLessEqual(self.quante("vivo.com"), 1)

    def test_un_guasto_non_si_mette_in_cache(self):
        """Tenere un errore vorrebbe dire rispondere «fonte irraggiungibile»
        per un'ora dopo un singolo errore di rete passeggero."""
        def rotta(url, timeout=None, headers=None):
            self.chiamate.append(url)
            raise ConnectionError("rete giù")

        sources.http_get = rotta
        sources.fetch_honor_aer()
        primo = self.quante("honor.com")
        sources.fetch_honor_aer()
        self.assertGreater(self.quante("honor.com"), primo,
                           "un errore è stato messo in cache")


class TestGsmarenaNonSiScaricaDueVolte(_ConContatore):
    """La stessa pagina di ricerca veniva chiesta due volte di fila: una
    per verificare che rispondesse (togliendo i tag, e quindi buttando via
    proprio i link che servivano) e una per leggerne l'HTML."""

    def test_una_richiesta_per_la_pagina_dei_risultati(self):
        sources._lookup_gsmarena("Galaxy S24 Ultra")
        self.assertLessEqual(self.quante("gsmarena.com"), 1)


class TestSottomarcaDentroLoStessoGruppo(unittest.TestCase):
    """«OnePlus 12» non è un realme, anche se il progetto li tiene nello
    stesso cassetto `C.OPPO`.

    CASO REALE, comparso solo dopo aver reso veloce la fonte realme:
    cercando «OnePlus 12» la risposta diventava «realme 12x 5G». Il filtro
    sul gruppo non poteva vederlo — sono lo stesso gruppo — e a far
    combaciare i nomi è `_normalize_name`, che toglie il produttore:
    «OnePlus 12» diventa «12», che somiglia a «12x 5G».
    """

    def _item(self, device, brand=C.OPPO):
        return sources.RawItem(title=device, link="", brand=brand, device=device)

    def test_un_realme_non_risponde_a_una_domanda_su_oneplus(self):
        tenuti = sources._scarta_sottomarca_sbagliata(
            [self._item("realme 12x 5G")], "OnePlus 12")
        self.assertEqual(tenuti, [])

    def test_un_oneplus_risponde_a_una_domanda_su_oneplus(self):
        voce = self._item("OnePlus 12")
        self.assertEqual(
            sources._scarta_sottomarca_sbagliata([voce], "OnePlus 12"), [voce])

    def test_un_nome_senza_produttore_non_viene_scartato(self):
        """I cataloghi elencano parecchi modelli col solo nome commerciale:
        pretendere la marca butterebbe via risposte giuste."""
        voce = self._item("Nord CE 3 Lite")
        self.assertEqual(
            sources._scarta_sottomarca_sbagliata([voce], "OnePlus Nord CE 3 Lite"),
            [voce])

    def test_una_domanda_senza_produttore_non_scarta_niente(self):
        """«c63» non nomina nessuno: lì l'ambiguità è vera e si mostrano
        tutte le risposte."""
        voci = [self._item("realme C61"), self._item("OnePlus 12")]
        self.assertEqual(sources._scarta_sottomarca_sbagliata(voci, "c63"), voci)

    def test_le_sottomarche_riconosciute(self):
        self.assertEqual(sources._sottomarca_nominata("OnePlus 12"), "oneplus")
        self.assertEqual(sources._sottomarca_nominata("realme 12x 5G"), "realme")
        self.assertEqual(sources._sottomarca_nominata("POCO F8"), "poco")
        self.assertIsNone(sources._sottomarca_nominata("Nord CE 3 Lite"))
        self.assertIsNone(sources._sottomarca_nominata(""))


class TestRiscaldamentoInParallelo(_ConContatore):
    """Scaldare non deve cambiare cosa si trova, solo quando lo si aspetta."""

    def test_scalda_solo_le_fonti_fredde(self):
        sources.fetch_honor_aer()   # questa è già calda
        prima = self.quante("honor.com")
        voci = [v for v in sources._STRUCTURED_LOOKUPS_LIST
                if v.fetch is sources.fetch_honor_aer]
        sources._scalda_fonti(voci)
        sources.attendi_riscaldamenti()
        self.assertEqual(self.quante("honor.com"), prima,
                         "una fonte già in cache non va riscaricata")

    def test_i_riscaldamenti_si_possono_attendere(self):
        """Senza questa attesa un thread potrebbe scrivere in cache dopo
        che qualcuno l'ha azzerata: è la definizione di test a
        intermittenza."""
        voci = [v for v in sources._STRUCTURED_LOOKUPS_LIST if v.fetch is not None]
        sources._scalda_fonti(voci)
        sources.attendi_riscaldamenti()
        self.assertEqual(sources._scalda_in_volo, set())

    def test_un_guasto_nel_riscaldamento_resta_silenzioso(self):
        def rotta(url, timeout=None, headers=None):
            raise ConnectionError("rete giù")

        sources.http_get = rotta
        voci = [v for v in sources._STRUCTURED_LOOKUPS_LIST if v.fetch is not None]
        sources._scalda_fonti(voci)   # non deve sollevare
        sources.attendi_riscaldamenti()


class TestAzzeraCacheFonti(unittest.TestCase):
    """La funzione che i test usano per non misurarsi a vicenda."""

    def test_copre_anche_le_cache_che_non_sono_CacheDiFonte(self):
        """ARB e Telegram tengono lo stato in variabili di modulo. Non
        azzerarle faceva dichiarare «OK» una fonte che a rete spenta
        rispondeva con 53 voci lasciate da un test precedente."""
        sources._arb_cache = ["finto"]
        sources._telegram_cache = ["finto"]
        sources.azzera_cache_fonti()
        self.assertIsNone(sources._arb_cache)
        self.assertIsNone(sources._telegram_cache)

    def test_azzera_ogni_cache_registrata(self):
        for cache in sources._CacheDiFonte._tutte:
            cache.scrivi(([], None))
        sources.azzera_cache_fonti()
        self.assertFalse(any(c.fresca() for c in sources._CacheDiFonte._tutte))


if __name__ == "__main__":
    unittest.main()
