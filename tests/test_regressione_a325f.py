"""Regressione: «a325f» dava Android 11 invece di Android 13.

Due difetti che si sommavano, e il secondo è quello che rendeva il primo
pericoloso invece che solo scomodo.

1. **Il codice senza prefisso non era riconosciuto.** `A325F` è la forma
   che compare nel numero di build (`A325FXXU2CVK1`), nei log e nei nomi
   dei firmware: è quella che chi fa QA copia più spesso, molto più di
   `SM-A325F`. Non essendo riconosciuta, il controllo firmware ufficiale
   Samsung non partiva nemmeno.
2. **Rispondeva allora un'altra fonte, con la versione DI FABBRICA.** Su
   un Galaxy A32 significa Android 11 (il lancio, 2021) su un telefono
   arrivato ad Android 13.

Il risultato non era un dato mancante ma un dato **sbagliato**, che per
un tracker di aggiornamenti è molto peggio: un QA che ci si fida non
ritesta un dispositivo che invece è cambiato di due major.
"""
from __future__ import annotations

import unittest

from core import config as C, modelcodes, scan, sources, storage


class TestCodiceSenzaPrefisso(unittest.TestCase):

    def test_le_forme_usate_davvero_sono_riconosciute(self):
        for testo in ("a325f", "A325F", "S928B", "a075f", "G991B"):
            with self.subTest(testo=testo):
                self.assertTrue(sources.looks_like_model_code(testo))

    def test_espansione_al_codice_completo(self):
        casi = {"a325f": "SM-A325F", "S928B": "SM-S928B", "g991b": "SM-G991B"}
        for grezzo, atteso in casi.items():
            with self.subTest(grezzo=grezzo):
                self.assertEqual(sources.espandi_codice_samsung(grezzo), atteso)

    def test_la_forma_espansa_viene_provata_per_prima(self):
        """È l'unico nome che l'endpoint firmware Samsung conosce."""
        self.assertEqual(sources._code_candidates("a325f")[0], "SM-A325F")

    def test_il_brand_viene_dedotto(self):
        self.assertEqual(sources.brand_from_code("a325f"), C.SAMSUNG)

    def test_un_codice_gia_completo_non_viene_espanso_due_volte(self):
        self.assertIsNone(sources.espandi_codice_samsung("SM-A325F"))
        self.assertEqual(sources._code_candidates("SM-A325F"), ["SM-A325F"])

    def test_non_cattura_cio_che_non_e_un_codice_samsung(self):
        """La regola è stretta apposta: allargarla farebbe passare per
        codice Samsung qualunque parola con dei numeri."""
        for testo in ("galaxy a32", "pixel 9", "iPhone17,3", "A32", "Android 13"):
            with self.subTest(testo=testo):
                self.assertIsNone(sources.espandi_codice_samsung(testo))

    def test_le_altre_marche_non_sono_toccate(self):
        self.assertEqual(sources.brand_from_code("RMX3939"), C.OPPO)
        self.assertTrue(sources.looks_like_model_code("2312DRA50G"))


class _Risposta:
    def __init__(self, testo, status_code=200):
        self.text, self.status_code = testo, status_code


# Risposta reale dell'endpoint FOTA per un A32 aggiornato ad Android 13.
XML_A32 = (
    '<?xml version="1.0" encoding="UTF-8"?><versioninfo><firmware><version>'
    '<latest o="13">A325FXXU2CVK1/A325FODM2CVK1/A325FXXU2CVK1</latest>'
    '</version></firmware></versioninfo>'
)


class TestRicercaA325F(unittest.TestCase):
    """Il caso segnalato, dall'input dell'utente al risultato."""

    def setUp(self):
        self._http = sources.http_get
        self._resolve = modelcodes.resolve
        self._codes = modelcodes.codes_for_name
        storage.reset_state()
        storage.init_db()

        def get(url, timeout=None, headers=None):
            if "fota-cloud-dn" in url:
                return _Risposta(XML_A32)
            raise ConnectionError("altre fonti non disponibili")

        sources.http_get = get
        modelcodes.resolve = lambda c: {"SM-A325F": ["Galaxy A32"]}.get(c.upper(), [])
        modelcodes.codes_for_name = lambda n: []

    def tearDown(self):
        sources.http_get = self._http
        modelcodes.resolve = self._resolve
        modelcodes.codes_for_name = self._codes
        storage.reset_state()

    def test_il_codice_minuscolo_senza_prefisso_da_la_versione_vera(self):
        for query in ("a325f", "A325F", "SM-A325F"):
            with self.subTest(query=query):
                risultato = scan.search_model(query)
                versioni = [i.get("os_version") or "" for i in risultato.get("items", [])]
                self.assertTrue(any("13" in v for v in versioni), versioni)
                self.assertFalse(any("11" in v for v in versioni), versioni)

    def test_risponde_la_fonte_ufficiale_non_un_ripiego(self):
        risultato = scan.search_model("a325f")
        etichette = [i.get("source_label") or "" for i in risultato["items"]]
        self.assertTrue(any("FOTA" in e for e in etichette), etichette)

    def test_l_endpoint_riceve_il_codice_completo(self):
        richieste = []

        def get(url, timeout=None, headers=None):
            richieste.append(url)
            if "fota-cloud-dn" in url:
                return _Risposta(XML_A32)
            raise ConnectionError("no")

        sources.http_get = get
        sources._lookup_samsung("a325f")
        self.assertTrue(any("/SM-A325F/" in u for u in richieste), richieste)


class TestNienteRetrocessione(unittest.TestCase):
    """Un telefono Android non torna indietro di major.

    A parità di affidabilità deve vincere la versione più alta, non
    quella incontrata più di recente: altrimenti un articolo del 2021 che
    parla del lancio può scalzare il dato attuale.
    """

    def setUp(self):
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()

    def _scrivi(self, android, trust, quando, titolo):
        storage.upsert_update({
            "id": f"{titolo}-{android}-{trust}",
            "device_key": "samsung|galaxy-a32",
            "brand": C.SAMSUNG,
            "device_model": "Galaxy A32",
            "title": titolo,
            "os_version": f"Android {android}",
            "android_version": android,
            "source": "test",
            "source_label": titolo,
            "source_trust": trust,
            "published": quando,
            "first_seen": quando,
            "is_relevant": 1,
        })

    def test_a_parita_di_fiducia_vince_la_piu_alta(self):
        self._scrivi(13, C.TRUST_NOISY, "2023-05-01T00:00:00", "articolo 2023")
        self._scrivi(11, C.TRUST_NOISY, "2026-08-01T00:00:00", "articolo vecchio ripescato")
        righe = storage.get_devices()
        riga = next(r for r in righe if r["device_key"] == "samsung|galaxy-a32")
        self.assertEqual(riga["android_version"], 13)
        self.assertIn("13", riga["os_version"] or "")

    def test_ma_l_affidabilita_viene_ancora_prima(self):
        """Una fonte ufficiale che dice 13 batte una notizia che dice 14:
        la regola nuova non deve scavalcare quella vecchia."""
        self._scrivi(13, C.TRUST_STRUCTURED, "2026-01-01T00:00:00", "endpoint ufficiale")
        self._scrivi(14, C.TRUST_NOISY, "2026-08-01T00:00:00", "notizia entusiasta")
        righe = storage.get_devices()
        riga = next(r for r in righe if r["device_key"] == "samsung|galaxy-a32")
        self.assertEqual(riga["android_version"], 13)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
