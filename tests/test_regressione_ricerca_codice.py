"""Regressione: la ricerca per codice modello Samsung non trovava nulla.

Tre difetti distinti, tutti e tre capaci da soli di far sembrare l'app
rotta, e nessuno coperto dai test precedenti.

1. **Suffisso di variante.** `SM-A075F/DS` è la forma stampata sulla
   scatola e mostrata in «Info software», cioè quella che un utente copia
   naturalmente. Non era riconosciuta come codice: la ricerca non partiva
   nemmeno.
2. **Solo quattro region europee.** Un modello venduto in India o in Asia
   non poteva essere trovato: il firmware esiste, ma nessuna delle
   quattro region interrogate lo distribuisce.
3. **Silenzio quando le fonti firmware tacciono.** Il progetto ha ~70.000
   codici modello in casa, ma se nessuna fonte firmware rispondeva la
   ricerca restituiva «niente» — pur sapendo benissimo di che telefono si
   trattava.

Il terzo è il più insidioso, perché confonde due domande diverse:
«che telefono è?» e «a che firmware sta?». La prima ha quasi sempre una
risposta, la seconda dipende dal produttore.
"""
from __future__ import annotations

import unittest

from core import modelcodes, scan, sources, storage


class TestSuffissoDiVariante(unittest.TestCase):

    def test_le_forme_stampate_sul_telefono_sono_codici_validi(self):
        for testo in ("SM-A075F/DS", "SM-A546B/DSN", "SM-S928B/DS",
                      "SM-A075F DS", "sm-a075f/ds"):
            with self.subTest(testo=testo):
                self.assertTrue(sources.looks_like_model_code(testo))

    def test_normalizzazione(self):
        casi = {
            "SM-A075F/DS": "SM-A075F",
            "SM-A546B/DSN": "SM-A546B",
            "SM-A075F DS": "SM-A075F",
            "SM-S928B": "SM-S928B",
            " sm-s928b ": "SM-S928B",
        }
        for grezzo, atteso in casi.items():
            with self.subTest(grezzo=grezzo):
                self.assertEqual(sources.normalizza_codice_modello(grezzo), atteso)

    def test_il_suffisso_si_toglie_prima_di_comprimere_gli_spazi(self):
        """Al contrario «SM-A075F DS» diventerebbe «SM-A075FDS», che ha
        ancora la forma di un codice valido: non verrebbe segnalato come
        errore, verrebbe solo cercato invano."""
        self.assertEqual(sources.normalizza_codice_modello("SM-A075F DS"), "SM-A075F")
        self.assertNotEqual(sources.normalizza_codice_modello("SM-A075F DS"), "SM-A075FDS")

    def test_la_forma_senza_suffisso_viene_provata_per_prima(self):
        """È quella che l'endpoint FOTA conosce."""
        candidati = sources._code_candidates("SM-A075F/DS")
        self.assertEqual(candidati[0], "SM-A075F")

    def test_un_codice_vero_non_viene_mutilato(self):
        """La lista di suffissi non deve mangiarsi lettere legittime."""
        for codice in ("SM-S928B", "SM-A536B", "CPH2649", "RMX3939"):
            with self.subTest(codice=codice):
                self.assertEqual(sources.normalizza_codice_modello(codice), codice)


class TestCodiceXiaomiStileClassico(unittest.TestCase):
    """Regressione: `M1910F4G` (Xiaomi Mi Note 10) non aveva la forma di
    un codice per `looks_like_model_code` — nessuna delle forme in
    `_MODEL_CODE_SHAPES` comincia con UNA lettera sola seguita da cifre.

    Segnalato dall'utente cercando quel codice esatto: la pagina diceva
    «Nessun firmware per «m1910f4g»» senza mai nominare il telefono, pur
    avendo `core/specs.py` trovato la scheda tecnica giusta (foto,
    processore) — perché `specs.cerca` prova il testo SENZA validarne la
    forma, mentre tutto il resto (instradamento verso il catalogo
    Xiaomi, gemelli, correzione del nome) passa da qui e saltava.
    """

    def test_i_codici_xiaomi_a_lettera_singola_sono_validi(self):
        for codice in ("M1910F4G", "M2007J20CG", "M2101K6G", "M2012K11AG",
                       "M2003J15SC", "m1910f4g"):
            with self.subTest(codice=codice):
                self.assertTrue(sources.looks_like_model_code(codice))

    def test_non_cattura_parole_qualunque_che_iniziano_per_m(self):
        # «M123» non è in questa lista: ha GIÀ la forma di un Samsung
        # senza prefisso («M»+tre cifre, vedi `_RE_SAMSUNG_SENZA_PREFISSO`)
        # e risultava già `True` prima di questo fix, per una ragione
        # del tutto indipendente — non è una regressione di questo
        # pattern, è un altro pattern preesistente che se ne occupa.
        for testo in ("MOTOROLA", "MODELLO", "M"):
            with self.subTest(testo=testo):
                self.assertFalse(sources.looks_like_model_code(testo))

    def test_compare_fra_i_candidati_di_ricerca(self):
        self.assertIn("M1910F4G", sources._code_candidates("m1910f4g"))


class TestRegionSamsung(unittest.TestCase):

    def test_non_solo_europa(self):
        """Quattro region europee escludevano interi mercati: è il motivo
        per cui un A-series indiano non restituiva nulla."""
        csc = sources.SAMSUNG_CSC_CANDIDATES
        self.assertGreater(len(csc), 10)
        for regione in ("INS", "XAA", "DBT"):
            with self.subTest(regione=regione):
                self.assertIn(regione, csc)

    def test_le_multi_paese_vengono_per_prime(self):
        """Coprono di più con una richiesta sola, e la ricerca si ferma
        alla prima che risponde."""
        csc = sources.SAMSUNG_CSC_CANDIDATES
        self.assertLess(csc.index("EUX"), csc.index("INS"))

    def test_nessun_doppione(self):
        self.assertEqual(len(sources.SAMSUNG_CSC_CANDIDATES),
                         len(set(sources.SAMSUNG_CSC_CANDIDATES)))


class _Risposta:
    def __init__(self, testo, status_code=200):
        self.text, self.status_code = testo, status_code


XML_FOTA = (
    '<?xml version="1.0" encoding="UTF-8"?><versioninfo><firmware><version>'
    '<latest o="14">S928BXXU1AXBC/S928BOXM1AXBC/S928BXXU1AXBC</latest>'
    '</version></firmware></versioninfo>'
)


class TestRicercaSamsungFunziona(unittest.TestCase):
    """Il percorso completo, con la rete simulata."""

    def setUp(self):
        self._http = sources.http_get
        self._resolve = modelcodes.resolve
        self._codes = modelcodes.codes_for_name
        storage.reset_state()
        storage.init_db()
        modelcodes.resolve = lambda c: {
            "SM-A075F": ["Galaxy A07"], "SM-S928B": ["Galaxy S24 Ultra"]}.get(c.upper(), [])
        modelcodes.codes_for_name = lambda n: []

    def tearDown(self):
        sources.http_get = self._http
        modelcodes.resolve = self._resolve
        modelcodes.codes_for_name = self._codes
        storage.reset_state()

    def _rete_fota(self):
        richieste = []

        def get(url, timeout=None, headers=None):
            richieste.append(url)
            if "fota-cloud-dn" in url:
                return _Risposta(XML_FOTA)
            raise ConnectionError("altre fonti non disponibili")

        sources.http_get = get
        return richieste

    def test_il_codice_col_suffisso_interroga_l_endpoint(self):
        richieste = self._rete_fota()
        items = sources._lookup_samsung("SM-A075F/DS")
        self.assertTrue(items)
        # L'URL deve contenere il codice PULITO: l'endpoint non conosce /DS.
        self.assertTrue(any("/SM-A075F/" in u for u in richieste))
        self.assertFalse(any("/DS/" in u for u in richieste))

    def test_ricerca_completa_restituisce_la_build(self):
        self._rete_fota()
        risultato = scan.search_model("SM-S928B")
        build = [i.get("build") for i in risultato.get("items", [])]
        self.assertIn("S928BXXU1AXBC", build)


class TestIdentificazioneSenzaFirmware(unittest.TestCase):
    """Il difetto peggiore: sapere che telefono è, e tacere lo stesso."""

    def setUp(self):
        self._http = sources.http_get
        self._resolve = modelcodes.resolve
        self._codes = modelcodes.codes_for_name
        storage.reset_state()
        storage.init_db()

        def giu(url, timeout=None, headers=None):
            raise ConnectionError("nessuna fonte firmware raggiungibile")

        sources.http_get = giu
        modelcodes.resolve = lambda c: {
            "SM-A075F": ["Galaxy A07"], "SM-S928B": ["Galaxy S24 Ultra"]}.get(c.upper(), [])
        modelcodes.codes_for_name = lambda n: []

    def tearDown(self):
        sources.http_get = self._http
        modelcodes.resolve = self._resolve
        modelcodes.codes_for_name = self._codes
        storage.reset_state()

    def test_il_modello_viene_riconosciuto_lo_stesso(self):
        risultato = scan.search_model("SM-A075F/DS")
        nomi = [i.get("device_model") for i in risultato.get("items", [])]
        self.assertIn("Galaxy A07", nomi)

    def test_ma_senza_inventare_un_firmware(self):
        """Un item senza versione è ciò che permette all'interfaccia di
        dire «riconosciuto, ma la versione non è pubblicata» invece di
        fingere un risultato pieno."""
        risultato = scan.search_model("SM-A075F/DS")
        voce = risultato["items"][0]
        for campo in ("build", "os_version", "patch_level"):
            with self.subTest(campo=campo):
                self.assertFalse(voce.get(campo))

    def test_arriva_anche_il_chip(self):
        """Il SoC non dipende dalle fonti firmware: si sa comunque."""
        risultato = scan.search_model("SM-S928B")
        voce = risultato["items"][0]
        self.assertIn("Snapdragon 8 Gen 3", voce.get("size_info") or "")

    def test_un_codice_sconosciuto_resta_senza_risposta(self):
        """La regola del progetto: non inventare. Se il codice non è nei
        dataset, non si tira a indovinare un modello."""
        risultato = scan.search_model("SM-ZZ999X")
        self.assertEqual(risultato.get("items"), [])

    def test_il_risultato_e_trattato_come_lookup_non_come_notizia(self):
        risultato = scan.search_model("SM-S928B")
        self.assertEqual(risultato["items"][0].get("source"), "official_lookup")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
