"""Test del tracker ARB OnePlus/OPPO.

Girano sull'estratto **registrato** dal README vero
(`tests/fixtures/oplus_arb_readme.md`).

Il gruppo che conta di più è `TestTabelleStoricheIgnorate`: le tabelle di
storico elencano build superate, e prenderle per correnti direbbe a chi fa
QA che un telefono è fermo a una versione che ha lasciato mesi fa.
"""
from __future__ import annotations

import os
import unittest

from core import oplus_arb as A

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "oplus_arb_readme.md")


def _readme() -> str:
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def _rilasci():
    rilasci, errore = A.rilasci_da_readme(_readme())
    assert errore is None, errore
    return rilasci


def _uno(nome: str, regione: str):
    for r in _rilasci():
        if r.device_name == nome and r.region == regione:
            return r
    raise AssertionError(f"{nome} / {regione} non trovato")


class TestTabelleStoricheIgnorate(unittest.TestCase):
    """Storico ≠ stato corrente."""

    def test_le_build_storiche_non_entrano(self):
        build = {r.build for r in _rilasci()}
        # Presenti nella fixture SOLO dentro le tabelle di storico.
        for superata in ("CPH2649_16.0.5.703(EX01)", "CPH2649_16.0.5.701(EX01)",
                         "CPH2649_15.0.0.860(EX01)", "CPH2613_16.0.3.500(EX01)"):
            with self.subTest(build=superata):
                self.assertNotIn(superata, build)

    def test_la_build_corrente_e_quella_giusta(self):
        self.assertEqual(_uno("OnePlus 13", "India").build, "CPH2649_16.0.7.201(EX01)")

    def test_il_discriminante_e_la_colonna_region(self):
        """Criterio strutturale, non posizionale: regge al riordino delle
        colonne, che in un README generato può cambiare senza preavviso."""
        intestazioni = [i for _, i, _ in A._tabelle(_readme())]
        con_regione = [i for i in intestazioni if "Region" in i]
        senza = [i for i in intestazioni if "Region" not in i]
        self.assertTrue(con_regione and senza)
        for i in senza:
            self.assertIn("Firmware Version", i)


class TestLetturaDeiCampi(unittest.TestCase):

    def test_stessa_build_codici_diversi_per_regione(self):
        """Il motivo principale per cui questa fonte vale: lo stesso
        telefono ha codici e build diversi per mercato."""
        europa = _uno("OnePlus 13", "Europe")
        india = _uno("OnePlus 13", "India")
        self.assertEqual(europa.model_code, "CPH2653")
        self.assertEqual(india.model_code, "CPH2649")
        self.assertNotEqual(europa.build, india.build)

    def test_md5_non_finisce_nella_build(self):
        for r in _rilasci():
            with self.subTest(build=r.build):
                self.assertNotIn("MD5", r.build)
                self.assertLess(len(r.build), 40)

    def test_versione_skin_dalle_prime_tre_cifre(self):
        self.assertEqual(_uno("OnePlus 13", "India").skin_version, "16.0.7")

    def test_build_di_vecchio_stile_senza_versione_inventata(self):
        """`CPH2611_11_A.65` non espone una versione di skin leggibile:
        meglio None che un numero dedotto."""
        vecchia = _uno("OnePlus 12R", "North America")
        self.assertEqual(vecchia.build, "CPH2611_11_A.65")
        self.assertIsNone(vecchia.skin_version)

    def test_canale_di_rilascio_separato(self):
        self.assertEqual(_uno("OnePlus 13", "China").canale_build, "CN01")
        self.assertEqual(_uno("OnePlus 13", "India").canale_build, "EX01")

    def test_data_di_verifica_del_tracker(self):
        self.assertEqual(_uno("OPPO Reno10 Pro", "Europe").last_checked, "2026-04-23")

    def test_arb_non_rilevabile(self):
        r = _uno("OnePlus 9RT", "India")
        self.assertEqual(r.arb, "?")
        self.assertIn("non rilevabile", r.arb_nota)

    def test_codice_col_suffisso_di_mercato(self):
        self.assertEqual(_uno("OPPO Reno10 Pro", "Europe").model_code, "CPH2525EEA")

    def test_codice_dalla_colonna_anche_se_diverso_dalla_build(self):
        """Find N5 Cina dichiara PKV110 in colonna ma PKH110 nella build.
        Vince la colonna, che è il codice del telefono."""
        r = _uno("OPPO Find N5", "China")
        self.assertEqual(r.model_code, "PKV110")
        self.assertTrue(r.build.startswith("PKH110"))


class TestNomiMarca(unittest.TestCase):

    def test_oppo_normalizzato_in_maiuscolo(self):
        """Il tracker scrive «Oppo», il catalogo AER e le fonti ufficiali
        «OPPO». Grafie diverse = due dispositivi in archivio per lo stesso
        telefono."""
        nomi = {r.device_name for r in _rilasci()}
        self.assertIn("OPPO Reno10 Pro", nomi)
        self.assertNotIn("Oppo Reno10 Pro", nomi)

    def test_i_nomi_oneplus_restano_intatti(self):
        nomi = {r.device_name for r in _rilasci()}
        self.assertIn("OnePlus 9RT", nomi)
        self.assertIn("OnePlus Nord CE 4", nomi)


class TestGuasti(unittest.TestCase):

    def test_readme_senza_tabelle_e_un_errore(self):
        rilasci, errore = A.rilasci_da_readme("# Titolo\n\nSolo testo.\n")
        self.assertEqual(rilasci, [])
        self.assertIsNotNone(errore)
        self.assertIn("nessuna tabella", errore)

    def test_testo_vuoto(self):
        rilasci, errore = A.rilasci_da_readme("")
        self.assertEqual(rilasci, [])
        self.assertIsNotNone(errore)

    def test_solo_tabelle_storiche_e_un_errore(self):
        """Se restassero solo gli storici, la fonte non ha più niente di
        utile: deve dirlo, non restare in silenzio."""
        solo_storico = (
            "### OnePlus 13\n\n"
            "| Firmware Version | ARB | Last Seen | Safe |\n"
            "| --- | --- | --- | --- |\n"
            "| CPH2649_16.0.5.703(EX01) | 1 | 2026-05-14 | Protected |\n"
        )
        rilasci, errore = A.rilasci_da_readme(solo_storico)
        self.assertEqual(rilasci, [])
        self.assertIsNotNone(errore)


class TestCopertura(unittest.TestCase):

    def test_riepilogo(self):
        dati = A.copertura(_rilasci())
        self.assertEqual(dati["rilasci"], 15)
        self.assertEqual(dati["dispositivi"], 6)
        self.assertIn("India", dati["regioni"])
        self.assertEqual(dati["ultima_verifica"], "2026-05-17")


class _Risposta:
    def __init__(self, testo: str, status_code: int = 200):
        self.text = testo
        self.status_code = status_code


class TestFonteInSources(unittest.TestCase):

    def setUp(self):
        from core import config as C, modelcodes, sources
        self.sources, self.C, self._mc = sources, C, modelcodes
        self._orig_http = sources.http_get
        self._orig_codes = modelcodes.codes_for_name
        sources.http_get = lambda url, timeout=None: _Risposta(_readme())
        modelcodes.codes_for_name = lambda nome: []
        sources.reset_arb_cache()

    def tearDown(self):
        self.sources.http_get = self._orig_http
        self._mc.codes_for_name = self._orig_codes
        self.sources.reset_arb_cache()

    def test_una_sola_voce_per_dispositivo_nel_giro_periodico(self):
        """Cinque regioni dello stesso telefono si sovrascriverebbero in
        archivio: se ne tiene una, la più avanzata."""
        items, errore = self.sources.fetch_oplus_arb()
        self.assertIsNone(errore)
        self.assertEqual(len(items), 6)
        self.assertEqual(len({i.device for i in items}), 6)

    def test_vince_la_build_piu_avanzata_non_la_prima(self):
        items, _ = self.sources.fetch_oplus_arb()
        op13 = next(i for i in items if i.device == "OnePlus 13")
        self.assertIn("16.0.7.201", op13.build)

    def test_trust_curated(self):
        items, _ = self.sources.fetch_oplus_arb()
        for item in items:
            self.assertEqual(item.trust, self.C.TRUST_CURATED)

    def test_etichetta_dichiara_che_non_e_ufficiale(self):
        items, _ = self.sources.fetch_oplus_arb()
        self.assertIn("non ufficiale", items[0].size_info.lower())

    def test_android_recente_da_coloros_documentato(self):
        """ColorOS 14/15/16 corrispondono esplicitamente ad Android 14/15/16;
        i formati vecchi restano volutamente vuoti."""
        items, _ = self.sources.fetch_oplus_arb()
        op13 = next(i for i in items if i.device == "OnePlus 13")
        self.assertEqual(op13.android_version, 16)
        self.assertIsNone(self.sources._android_da_coloros("11"))

    def test_il_codice_di_variante_arriva_al_risultato(self):
        items, _ = self.sources.fetch_oplus_arb()
        reno = next(i for i in items if i.device == "OPPO Reno10 Pro")
        self.assertEqual(reno.model_code, "CPH2525SG")

    def test_nessuna_data_di_rilascio_inventata(self):
        """Il tracker dà la data in cui HA VISTO la build, non quella in
        cui il produttore l'ha distribuita."""
        items, _ = self.sources.fetch_oplus_arb()
        op13 = next(i for i in items if i.device == "OnePlus 13")
        self.assertIsNone(op13.published)
        self.assertIn("2026-05-17", op13.summary)

    def test_ricerca_restituisce_tutte_le_regioni(self):
        items = self.sources._lookup_oplus_arb("OnePlus 13")
        self.assertEqual(len(items), 5)
        self.assertTrue(any("[India]" in i.title for i in items))
        self.assertTrue(any("[Europe]" in i.title for i in items))

    def test_leuropa_viene_prima_delle_altre_regioni(self):
        # Segnalato dall'utente: cercando un modello non deve comparire
        # una variante a caso, ma quella europea in priorità. Nella
        # fixture l'India ha la build più recente (16.0.7.201 contro
        # 16.0.5.703 dell'Europa) — prima di questo fix vinceva l'India,
        # perché l'ordine era solo per build. `_cerca_davvero` (web/
        # main.py) mostra come risultato principale il primo elemento di
        # questa lista, quindi l'ordine qui è quello che l'utente vede.
        items = self.sources._lookup_oplus_arb("OnePlus 13")
        self.assertIn("[Europe]", items[0].title)

    def test_global_viene_dopo_leuropa_ma_prima_delle_altre(self):
        # «Global» è la build più vicina a un telefono europeo quando non
        # esiste una riga «Europe» dedicata — vedi `_rango_regione_arb`.
        items = self.sources._lookup_oplus_arb("OnePlus 13")
        regioni = [i.title.rsplit("[", 1)[1].rstrip("]") for i in items]
        self.assertEqual(regioni[0], "Europe")
        self.assertEqual(regioni[1], "Global")
        self.assertEqual(set(regioni[2:]), {"India", "China", "North America"})

    def test_senza_europa_ne_global_lordine_resta_per_build(self):
        # CPH2525 (Oppo Reno10 Pro) nella fixture ha Singapore/Europe/India:
        # con l'Europa presente deve comunque vincere lei, non la build più
        # recente delle altre due.
        items = self.sources._lookup_oplus_arb("CPH2525")
        self.assertIn("Europe", items[0].size_info)

    def test_ricerca_per_codice_esatto(self):
        items = self.sources._lookup_oplus_arb("CPH2649")
        self.assertTrue(items)
        self.assertEqual(items[0].build, "CPH2649_16.0.7.201(EX01)")

    def test_ricerca_per_codice_base_trova_la_variante_di_mercato(self):
        """Chi digita «CPH2525» deve trovare anche la riga «CPH2525EEA»."""
        items = self.sources._lookup_oplus_arb("CPH2525")
        self.assertTrue(items)
        self.assertTrue(all(i.device == "OPPO Reno10 Pro" for i in items))

    def test_modello_estraneo(self):
        self.assertEqual(self.sources._lookup_oplus_arb("Galaxy S24"), [])
        self.assertEqual(self.sources._lookup_oplus_arb(""), [])

    def test_rete_assente_non_solleva(self):
        def esplode(url, timeout=None, headers=None):
            raise ConnectionError("niente rete")

        self.sources.http_get = esplode
        self.sources.reset_arb_cache()
        items, errore = self.sources.fetch_oplus_arb()
        self.assertEqual(items, [])
        self.assertIsNotNone(errore)

    def test_http_non_200(self):
        self.sources.http_get = lambda url, timeout=None: _Risposta("", 404)
        self.sources.reset_arb_cache()
        _, errore = self.sources.fetch_oplus_arb()
        self.assertIn("404", errore or "")

    def test_la_cache_evita_di_riscaricare(self):
        chiamate = []

        def conta(url, timeout=None, headers=None):
            chiamate.append(url)
            return _Risposta(_readme())

        self.sources.http_get = conta
        self.sources.reset_arb_cache()
        self.sources.fetch_oplus_arb()
        self.sources._lookup_oplus_arb("CPH2649")
        self.assertEqual(len(chiamate), 1)


class TestOrdineFonti(unittest.TestCase):

    def test_registrata_come_curated(self):
        from core import config as C, sources
        fonte = next(s for s in sources.SOURCES if s.key == "oplus_arb")
        self.assertEqual(fonte.trust, C.TRUST_CURATED)
        self.assertEqual(fonte.brand, C.OPPO)

    def test_dopo_l_archivio_ufficiale_oppo(self):
        from core import sources
        etichette = [v.etichetta for v in sources._STRUCTURED_LOOKUPS_LIST]
        self.assertLess(etichette.index("archivio firmware ufficiale Oppo"),
                        etichette.index("tracker ARB OnePlus/OPPO (non ufficiale)"))

    def test_il_canale_telegram_e_ritirato(self):
        """Il canale Telegram (`oplus_telegram`) è stato ritirato l'11/08/2026
        — non dava risultati (0 voci in scansione) e costava comunque un
        giro di rete a ogni scansione e a ogni ricerca live Oppo/OnePlus.
        Il codice resta (`_lookup_oplus_telegram`, `fetch_oplus_telegram`),
        solo non gira più: vedi `RETIRED_SOURCES` in `core/sources.py`."""
        from core import sources
        etichette = [v.etichetta for v in sources._STRUCTURED_LOOKUPS_LIST]
        self.assertNotIn("canale rollout OxygenOS/ColorOS (non ufficiale)", etichette)

    def test_prima_delle_fonti_con_versione_di_fabbrica(self):
        from core import sources
        etichette = [v.etichetta for v in sources._STRUCTURED_LOOKUPS_LIST]
        posizione = etichette.index("tracker ARB OnePlus/OPPO (non ufficiale)")
        self.assertLess(posizione, etichette.index("piano ufficiale realme"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
