"""Test del lettore del canale Telegram OxygenOS/ColorOS.

Girano sui **testi registrati dal canale vero**
(`tests/fixtures/telegram_oplus_messaggi.json`), non su messaggi
inventati: è la regola che il progetto si è dato dopo che parser tarati
su esempi immaginati si erano rotti al primo contatto con la realtà.

Il gruppo di test che conta davvero è `TestRifiutoPreliminari`. Il resto
verifica che i dati vengano letti; quello verifica che i dati SBAGLIATI
non entrino, ed è la ragione per cui questa fonte è accettabile.
"""
from __future__ import annotations

import json
import os
import unittest

from core import telegram_tracker as T

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "telegram_oplus_messaggi.json")


def _messaggi() -> list[dict]:
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)["messaggi"]


def _per_id(msg_id: str) -> str:
    for m in _messaggi():
        if m["id"] == msg_id:
            return m["testo"]
    raise AssertionError(f"messaggio {msg_id} assente dalla fixture")


def _tutti_i_rilasci() -> list[T.Rilascio]:
    rilasci = []
    for m in _messaggi():
        rilasci.extend(T.parse_messaggio(m["id"], m["testo"]))
    return rilasci


class TestRifiutoPreliminari(unittest.TestCase):
    """La versione promessa non è la versione spedita.

    Errore già pagato con la pagina AER di Honor. Qui il canale rende la
    trappola più insidiosa, perché il post preliminare contiene una build
    ben formata e una data di patch: sembra un dato buono in tutto e per
    tutto, e lo smentisce solo la prosa.
    """

    def test_post_upcoming_non_produce_nessun_rilascio(self):
        for msg_id in ("1644", "1645", "1657", "1673"):
            with self.subTest(msg=msg_id):
                self.assertEqual(T.parse_messaggio(msg_id, _per_id(msg_id)), [])

    def test_il_post_upcoming_conteneva_davvero_una_build_valida(self):
        """Il rifiuto non è banale: senza il filtro, questo passerebbe.

        Se un giorno qualcuno «semplificasse» il parser togliendo il
        controllo sui marcatori, questo test resterebbe verde mentre
        quello sopra diventerebbe rosso — e si capirebbe subito perché.
        """
        testo = _per_id("1673")
        self.assertRegex(testo, r"CPH2649_16\.0\.3\.502")
        self.assertTrue(T.e_preliminare(testo))

    def test_marcatori_riconosciuti(self):
        casi = [
            "Upcoming OnePlus Flagships Software Updates",
            "these values are subject to change",
            "Internal testing of ColorOS 17 based on Android 17 Started",
            "Version-15.0.0.830 [ Yet to Receive ]",
            "Status: Early Version Detected",
        ]
        for testo in casi:
            with self.subTest(testo=testo[:30]):
                self.assertTrue(T.e_preliminare(testo))

    def test_un_changelog_normale_non_e_preliminare(self):
        """Il filtro non deve essere così largo da mangiarsi i rilasci veri."""
        self.assertFalse(T.e_preliminare(_per_id("1637")))
        self.assertFalse(T.e_preliminare(_per_id("1638")))


class TestFormatiReali(unittest.TestCase):
    """I tre impaginati che il canale usa contemporaneamente."""

    def test_formato_senza_nome_modello(self):
        """Il caso più frequente: c'è la build, non c'è il telefono."""
        rilasci = T.parse_messaggio("1636", _per_id("1636"))
        self.assertEqual(len(rilasci), 1)
        r = rilasci[0]
        self.assertEqual(r.model_code, "CPH2613")
        self.assertEqual(r.build, "CPH2613_16.0.3.500")
        self.assertIsNone(r.device_name)
        self.assertEqual(r.android_version, 16)
        self.assertEqual(r.patch_level, "2026-02-01")
        self.assertEqual(r.skin, "OxygenOS")
        self.assertEqual(r.skin_version, "16.0.3")

    def test_formato_con_nome_e_canale(self):
        rilasci = T.parse_messaggio("1637", _per_id("1637"))
        self.assertEqual(len(rilasci), 1)
        r = rilasci[0]
        self.assertEqual(r.device_name, "OnePlus 10T")
        self.assertEqual(r.build, "CPH2413_15.0.0.1603(EX01)")
        self.assertEqual(r.canale_build, "EX01")
        self.assertEqual(r.patch_level, "2026-02-01")

    def test_formato_oppo_con_codice_fra_graffe(self):
        rilasci = T.parse_messaggio("1638", _per_id("1638"))
        self.assertEqual(len(rilasci), 1)
        r = rilasci[0]
        self.assertEqual(r.model_code, "CPH2813")
        self.assertEqual(r.device_name, "OPPO Reno 15 Pro Mini")
        self.assertEqual(r.build, "CPH2813_16.0.3.502(EX01)")
        self.assertEqual(r.skin, "ColorOS")
        self.assertEqual(r.skin_version, "16.0.3")

    def test_post_con_due_device_attribuisce_a_ciascuno_la_sua_build(self):
        """Il caso in cui sbagliare significa scrivere un dato falso.

        Il messaggio elenca OnePlus 12 e OnePlus Open con build diverse.
        Attribuire a entrambi la prima build sarebbe peggio che non
        leggere affatto il messaggio.
        """
        rilasci = T.parse_messaggio("0243", _per_id("0243"))
        self.assertEqual(len(rilasci), 2)
        coppie = {(r.device_name, r.build) for r in rilasci}
        self.assertEqual(coppie, {
            ("OnePlus 12", "CPH2573_15.0.0.23(EX01)"),
            ("OnePlus Open", "CPH2551_15.0.0.11(EX01)"),
        })


class TestNomiModello(unittest.TestCase):
    """Un nome storpiato è un dispositivo diverso, quindi mezza storia persa."""

    def test_le_sigle_con_cifre_restano_intatte(self):
        self.assertEqual(T._ripulisci_nome("OnePlus 10T"), "OnePlus 10T")
        self.assertEqual(T._ripulisci_nome("OnePlus 9RT"), "OnePlus 9RT")
        self.assertEqual(T._ripulisci_nome("OnePlus 13R"), "OnePlus 13R")

    def test_il_maiuscolo_pieno_viene_ammorbidito(self):
        self.assertEqual(T._ripulisci_nome("OPPO RENO 15 Pro Mini"),
                         "OPPO Reno 15 Pro Mini")

    def test_il_marchio_resta_maiuscolo(self):
        """Le fonti ufficiali Oppo scrivono «OPPO»: allinearsi a loro."""
        self.assertTrue(T._ripulisci_nome("OPPO PAD SE").startswith("OPPO "))

    def test_nome_letto_dal_messaggio_reale(self):
        rilasci = T.parse_messaggio("1122", _per_id("1122"))
        self.assertEqual(rilasci[0].device_name, "OnePlus 9RT")


class TestCampiDelicati(unittest.TestCase):

    def test_il_suffisso_della_build_non_e_la_regione(self):
        """EX01 è il canale di rilascio. Confonderlo con la regione
        produceva dispositivi con «Regione: EX01», che non vuol dire
        niente e sporca il filtro per mercato."""
        for r in _tutti_i_rilasci():
            with self.subTest(build=r.build):
                self.assertNotIn(r.region or "", ("EX01", "CN01", "IN01"))

    def test_la_versione_di_skin_non_e_il_numero_della_build(self):
        """Distinzione che decide il peso di un retest.

        In `core/retest.py` un cambio di cifra principale della skin vale
        «retest completo», un cambio di build vale «smoke test». Leggere
        `14.0.0.2401` come versione di skin farebbe scattare il retest
        completo a ogni patch mensile.
        """
        rilasci = T.parse_messaggio("1122", _per_id("1122"))
        self.assertEqual(rilasci[0].skin_version, "14.0")
        self.assertEqual(rilasci[0].build, "MT2111_14.0.0.2401(EX01)")

    def test_android_version_plausibile_o_assente(self):
        for r in _tutti_i_rilasci():
            if r.android_version is not None:
                with self.subTest(build=r.build):
                    self.assertTrue(8 <= r.android_version <= 30)

    def test_patch_level_in_forma_iso(self):
        for r in _tutti_i_rilasci():
            if r.patch_level:
                with self.subTest(build=r.build):
                    self.assertRegex(r.patch_level, r"^\d{4}-\d{2}-\d{2}$")

    def test_nessun_rilascio_senza_build(self):
        for r in _tutti_i_rilasci():
            self.assertTrue(r.build)

    def test_link_al_messaggio_di_origine(self):
        r = T.parse_messaggio("1636", _per_id("1636"))[0]
        self.assertEqual(r.link, "https://t.me/oxygenos14update/1636")


class TestRumore(unittest.TestCase):
    """Il canale parla anche d'altro: rilanci, sondaggi, dirette, consigli."""

    def test_messaggi_senza_build_non_producono_niente(self):
        for msg_id in ("1639", "1640", "1641", "1646", "1647", "1650",
                       "1652", "1653", "1655", "1656"):
            with self.subTest(msg=msg_id):
                self.assertEqual(T.parse_messaggio(msg_id, _per_id(msg_id)), [])

    def test_messaggio_vuoto(self):
        self.assertEqual(T.parse_messaggio("1", ""), [])
        self.assertEqual(T.parse_messaggio("1", "   \n  "), [])


class TestEstrazioneDaHtml(unittest.TestCase):
    """L'involucro HTML della vista `/s/` di Telegram.

    NOTA ONESTA: a differenza dei testi dei messaggi, questo frammento è
    ricostruito sulla struttura nota della pagina, non catturato. È
    l'unico pezzo di questa fonte non verificato su dati reali, ed è
    documentato in FONTI.md come tale. Il rischio è contenuto dal fatto
    che `rilasci_da_pagina` restituisce un ERRORE quando non estrae
    nessun messaggio: se questo involucro fosse sbagliato, la fonte
    apparirebbe rossa in Diagnostica invece di apparire verde e vuota.
    """

    HTML = (
        '<div class="tgme_widget_message_wrap">'
        '<div class="tgme_widget_message" data-post="oxygenos14update/1636">'
        '<div class="tgme_widget_message_text js-message_text" dir="auto">'
        'Version : CPH2613_16.0.3.500<br/>OxygenOS Version: 16.0.3<br/>'
        'Android Version: 16<br/>Security Build : 1 February 2026<br/>'
        'Region : INDIA</div>'
        '<div class="tgme_widget_message_footer">3.81K views</div>'
        '</div></div>'
        '<div class="tgme_widget_message_wrap">'
        '<div class="tgme_widget_message" data-post="oxygenos14update/1640">'
        '<div class="tgme_widget_message_text js-message_text" dir="auto">'
        'OnePlus Started Testing 16.1.0 &amp; March patch</div>'
        '<div class="tgme_widget_message_footer">5.5K views</div>'
        '</div></div>'
    )

    def test_estrae_id_e_testo(self):
        messaggi = T.estrai_messaggi(self.HTML)
        self.assertEqual([m[0] for m in messaggi], ["1636", "1640"])
        self.assertIn("CPH2613_16.0.3.500", messaggi[0][1])
        self.assertIn("&", messaggi[1][1])          # entità HTML risolta

    def test_i_br_diventano_righe(self):
        _, testo = T.estrai_messaggi(self.HTML)[0]
        self.assertIn("\n", testo)
        self.assertIn("Region : INDIA", testo.splitlines()[-1])

    def test_pagina_intera_verso_rilasci(self):
        rilasci, errore = T.rilasci_da_pagina(self.HTML)
        self.assertIsNone(errore)
        self.assertEqual(len(rilasci), 1)           # il secondo è preliminare
        self.assertEqual(rilasci[0].model_code, "CPH2613")

    def test_pagina_senza_messaggi_e_un_errore_non_un_silenzio(self):
        """Il guasto deve essere rumoroso.

        Se Telegram cambiasse le classi CSS, senza questo la fonte
        resterebbe verde in Diagnostica pur non portando più niente:
        esattamente la bugia silenziosa che il progetto rifiuta.
        """
        rilasci, errore = T.rilasci_da_pagina("<html><body>ciao</body></html>")
        self.assertEqual(rilasci, [])
        self.assertIsNotNone(errore)
        self.assertIn("nessun messaggio", errore)

    def test_giornata_senza_rilasci_non_e_un_errore(self):
        """Distinzione opposta alla precedente, e altrettanto importante:
        il canale che parla d'altro è normale, non un guasto."""
        html = self.HTML.replace("Version : CPH2613_16.0.3.500", "Buongiorno")
        rilasci, errore = T.rilasci_da_pagina(html)
        self.assertEqual(rilasci, [])
        self.assertIsNone(errore)


class TestCopertura(unittest.TestCase):
    """La misura che ha motivato l'adozione della fonte, e che dirà
    quando spegnerla."""

    def test_riepilogo_sui_dati_registrati(self):
        dati = T.copertura(_tutti_i_rilasci())
        self.assertEqual(dati["rilasci"], 11)
        self.assertEqual(dati["codici_distinti"], 11)
        # Cinque rilasci su undici arrivano SENZA nome commerciale: è il
        # motivo per cui la risoluzione del codice modello non è un
        # abbellimento ma la condizione perché la fonte serva a qualcosa.
        self.assertLess(dati["con_nome_esplicito"], dati["rilasci"])


class _Risposta:
    """Minima risposta HTTP finta, con la sola superficie che serve."""

    def __init__(self, testo: str, status_code: int = 200):
        self.text = testo
        self.status_code = status_code


class TestFonteInSources(unittest.TestCase):
    """L'aggancio in `core/sources.py`: scarico, risoluzione del codice,
    trust dichiarato."""

    PAGINA = TestEstrazioneDaHtml.HTML

    def setUp(self):
        from core import aer_catalog, config as C, modelcodes, sources
        self.sources, self.C = sources, C
        self._orig_http = sources.http_get
        self._orig_name = aer_catalog.name_for_code
        self._orig_resolve = modelcodes.resolve
        self._orig_codes = modelcodes.codes_for_name
        self._aer, self._mc = aer_catalog, modelcodes

        sources.http_get = lambda url, timeout=None: _Risposta(self.PAGINA)
        aer_catalog.name_for_code = lambda codice: (
            "OPPO A6x" if codice.upper() == "CPH2613" else None)
        modelcodes.resolve = lambda codice: []
        modelcodes.codes_for_name = lambda nome: (
            ["CPH2613"] if "a6x" in (nome or "").lower() else [])
        sources.reset_telegram_cache()

    def tearDown(self):
        self.sources.http_get = self._orig_http
        self._aer.name_for_code = self._orig_name
        self._mc.resolve = self._orig_resolve
        self._mc.codes_for_name = self._orig_codes
        self.sources.reset_telegram_cache()

    def test_il_codice_diventa_un_nome_commerciale(self):
        """Il punto per cui la fonte serve.

        Il post non nominava il telefono: c'era solo `CPH2613`. Se il
        codice non venisse risolto, l'item sarebbe inservibile.
        """
        items, errore = self.sources.fetch_oplus_telegram()
        self.assertIsNone(errore)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].device, "OPPO A6x")
        self.assertEqual(items[0].build, "CPH2613_16.0.3.500")
        self.assertEqual(items[0].brand, self.C.OPPO)

    def test_il_trust_dichiarato_e_curated(self):
        """Non è un dettaglio: è ciò che impedisce a questa fonte di
        sovrascrivere un dato ufficiale."""
        items, _ = self.sources.fetch_oplus_telegram()
        self.assertEqual(items[0].trust, self.C.TRUST_CURATED)

    def test_l_etichetta_dice_che_non_e_ufficiale(self):
        items, _ = self.sources.fetch_oplus_telegram()
        self.assertIn("non ufficiale", items[0].size_info.lower())

    def test_nessuna_data_di_pubblicazione_inventata(self):
        """Il canale dà il livello di patch, non il giorno del rilascio.

        Spacciare il primo per il secondo produrrebbe date di uscita
        sbagliate su ogni dispositivo di questa fonte.
        """
        items, _ = self.sources.fetch_oplus_telegram()
        self.assertIsNone(items[0].published)
        self.assertIn("2026-02-01", items[0].summary)

    def test_ricerca_per_codice_modello(self):
        items = self.sources._lookup_oplus_telegram("CPH2613")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].build, "CPH2613_16.0.3.500")

    def test_ricerca_per_nome_commerciale(self):
        items = self.sources._lookup_oplus_telegram("OPPO A6x")
        self.assertEqual(len(items), 1)

    def test_modello_estraneo_non_trova_niente(self):
        self.assertEqual(self.sources._lookup_oplus_telegram("Galaxy S24 Ultra"), [])
        self.assertEqual(self.sources._lookup_oplus_telegram(""), [])

    def test_rilascio_senza_nome_risolvibile_viene_scartato(self):
        """Un dispositivo chiamato «CPH2613» in archivio non incontrerebbe
        mai «OPPO A6x» delle altre fonti: due schede, mezza storia
        ciascuna."""
        self._aer.name_for_code = lambda codice: None
        self.sources.reset_telegram_cache()
        items, errore = self.sources.fetch_oplus_telegram()
        self.assertIsNone(errore)
        self.assertEqual(items, [])

    def test_html_cambiato_produce_un_errore_visibile(self):
        self.sources.http_get = lambda url, timeout=None: _Risposta("<html></html>")
        self.sources.reset_telegram_cache()
        items, errore = self.sources.fetch_oplus_telegram()
        self.assertEqual(items, [])
        self.assertIsNotNone(errore)

    def test_http_non_200_e_un_errore(self):
        self.sources.http_get = lambda url, timeout=None: _Risposta("", 503)
        self.sources.reset_telegram_cache()
        _, errore = self.sources.fetch_oplus_telegram()
        self.assertIn("503", errore or "")

    def test_rete_assente_non_solleva(self):
        def esplode(url, timeout=None, headers=None):
            raise ConnectionError("rete assente")

        self.sources.http_get = esplode
        self.sources.reset_telegram_cache()
        items, errore = self.sources.fetch_oplus_telegram()
        self.assertEqual(items, [])
        self.assertIsNotNone(errore)

    def test_la_cache_evita_di_riscaricare(self):
        chiamate = []

        def conta(url, timeout=None, headers=None):
            chiamate.append(url)
            return _Risposta(self.PAGINA)

        self.sources.http_get = conta
        self.sources.reset_telegram_cache()
        self.sources.fetch_oplus_telegram()
        self.sources.fetch_oplus_telegram()
        self.sources._lookup_oplus_telegram("CPH2613")
        self.assertEqual(len(chiamate), 1)


class TestOrdineDelleFonti(unittest.TestCase):
    """Dove si colloca il canale rispetto alle altre fonti Oppo — e, dall'
    11/08/2026, il fatto che non ci si colloca più: la fonte è RITIRATA
    (0 voci in scansione, misurato), il codice resta ma non gira né nella
    scansione periodica né nella ricerca live. Vedi il commento sopra
    `RETIRED_SOURCES` in `core/sources.py`."""

    def test_ritirata_non_e_piu_fra_le_fonti_attive(self):
        from core import sources
        chiavi_attive = {s.key for s in sources.SOURCES}
        self.assertNotIn("oplus_telegram", chiavi_attive)

    def test_ritirata_ma_il_codice_resta_riattivabile(self):
        from core import config as C, sources
        fonte = next(s for s in sources.RETIRED_SOURCES if s.key == "oplus_telegram")
        self.assertEqual(fonte.trust, C.TRUST_CURATED)
        self.assertEqual(fonte.brand, C.OPPO)
        # `ENABLED_SOURCES` la rimette fra le fonti della scansione — ma
        # non nella ricerca live: quella StructuredLookup va rimessa a
        # mano in `_STRUCTURED_LOOKUPS_LIST` (vedi il commento lì).
        vecchie = sources.C.env("ENABLED_SOURCES")
        os.environ["ENABLED_SOURCES"] = "oplus_telegram"
        try:
            self.assertIn("oplus_telegram", {s.key for s in sources.all_sources()})
        finally:
            if vecchie:
                os.environ["ENABLED_SOURCES"] = vecchie
            else:
                os.environ.pop("ENABLED_SOURCES", None)

    def test_ritirata_non_e_piu_nella_ricerca_live(self):
        from core import sources
        etichette = [v.etichetta for v in sources._STRUCTURED_LOOKUPS_LIST]
        self.assertNotIn("canale rollout OxygenOS/ColorOS (non ufficiale)", etichette)

    def test_le_altre_fonti_restano_strutturate(self):
        """La comodità di un valore predefinito non deve aver cambiato
        silenziosamente il trust di nessun'altra fonte."""
        from core import config as C, sources
        for voce in sources._STRUCTURED_LOOKUPS_LIST:
            atteso = (C.TRUST_CURATED
                      if "non ufficiale" in voce.etichetta else C.TRUST_STRUCTURED)
            with self.subTest(fonte=voce.etichetta):
                self.assertEqual(voce.trust, atteso)

    def test_il_campo_fetch_non_e_slittato(self):
        """L'aggiunta di `trust` alla dataclass non deve aver riassegnato
        gli argomenti posizionali già in uso: `fetch` resta il quinto."""
        from core import sources
        pixel = next(v for v in sources._STRUCTURED_LOOKUPS_LIST
                     if v.etichetta == "immagini OTA ufficiali Pixel")
        self.assertIs(pixel.fetch, sources.fetch_pixel_ota)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
