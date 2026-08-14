"""Test del core: estrazione, filtro di rilevanza, severità, persistenza.

Girano senza rete e senza Streamlit:

    python -m unittest discover -s tests -v
"""
import re
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import classify, config as C, extract, sources, storage  # noqa: E402
from core import appledevices, images, imeicheck, modelcodes, scan, suggest  # noqa: E402
from core import aer_catalog, oppo_official  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

with open(os.path.join(_FIXTURES, "aer_devices.json"), encoding="utf-8") as _f:
    AER_VOCI = json.load(_f)["items"]


class TestBrandDetection(unittest.TestCase):
    def test_riconosce_i_brand_principali(self):
        casi = {
            "Galaxy S24 Ultra One UI 8.0 rolling out": C.SAMSUNG,
            "Redmi Note 13 Pro gets HyperOS 2.0": C.XIAOMI,
            "Pixel 9 Pro XL January update is live": C.PIXEL,
            "Honor Magic 6 Pro MagicOS 9 rollout": C.HUAWEI,
            "OnePlus 12 OxygenOS 15 stable update": C.OPPO,
            "Motorola Edge 50 Pro Android 15 update": C.VIVO,
            "Nothing Phone (2a) Nothing OS 3.0 rollout": C.OTHER,
        }
        for titolo, atteso in casi.items():
            with self.subTest(titolo=titolo):
                self.assertEqual(extract.detect_brand(titolo), atteso)

    def test_parole_ambigue_non_creano_falsi_brand(self):
        # "vivo" e "poco" sono parole italiane comuni: senza un modello vicino
        # non devono attivare il brand.
        self.assertIsNone(extract.detect_brand("Il mercato è poco maturo"))
        self.assertIsNone(extract.detect_brand("Un ecosistema vivo e in crescita"))


class TestDeviceExtraction(unittest.TestCase):
    def test_modelli_riconosciuti(self):
        casi = [
            ("One UI 8 rolls out to the Galaxy S24 Ultra", "Galaxy S24 Ultra"),
            ("Galaxy Z Fold 6 receives September patch", "Galaxy Z Fold 6"),
            ("Pixel 9 Pro XL gets the June update", "Pixel 9 Pro XL"),
            ("OnePlus 12R starts receiving OxygenOS 15", "OnePlus 12R"),
            ("Redmi Note 13 Pro+ 5G HyperOS update", "Redmi Note 13 Pro+ 5G"),
            ("POCO F6 Pro stable rollout", "POCO F6 Pro"),
            ("Nothing Phone (2a) update", "Nothing Phone (2a)"),
        ]
        for titolo, atteso in casi:
            with self.subTest(titolo=titolo):
                _, modello = extract.extract_device(titolo)
                self.assertEqual(modello, atteso)

    def test_nessun_modello_quando_non_ce(self):
        _, modello = extract.extract_device("Samsung annuncia i risultati trimestrali")
        self.assertIsNone(modello)

    def test_device_key_stabile(self):
        a = extract.device_key(C.SAMSUNG, "Galaxy S24 Ultra")
        b = extract.device_key(C.SAMSUNG, "galaxy  s24   ultra")
        self.assertEqual(a, b)


class TestVersionExtraction(unittest.TestCase):
    def test_versione_android_numerica(self):
        self.assertEqual(extract.extract_android_version("Android 16 rollout"), 16)
        self.assertEqual(extract.extract_android_version("Android 18 arriva"), 18)
        self.assertIsNone(extract.extract_android_version("Android Auto si aggiorna"))

    def test_skin(self):
        self.assertEqual(extract.extract_skin("One UI 8.0 beta"), ("One UI", "8.0"))
        self.assertEqual(extract.extract_skin("HyperOS 2 in rollout"), ("HyperOS", "2"))

    def test_build_number(self):
        self.assertEqual(
            extract.extract_build("Pixel 9 riceve la build AP4A.250105.002 di gennaio"),
            "AP4A.250105.002",
        )
        self.assertEqual(
            extract.extract_build("Galaxy S24 Ultra firmware S928BXXU5BYG1 disponibile"),
            "S928BXXU5BYG1",
        )

    def test_patch_level(self):
        self.assertEqual(extract.extract_patch_level("July 2026 security patch"), "2026-07")
        self.assertEqual(extract.extract_patch_level("patch level 2026-03-01"), "2026-03")
        self.assertIsNone(extract.extract_patch_level("nessuna data qui"))

    def test_etichetta_versione_completa(self):
        risultato = extract.extract_all("Galaxy S24 gets Android 16 with One UI 8.0 build S921BXXU4CYG2")
        self.assertEqual(risultato.os_version, "Android 16 · One UI 8.0")
        self.assertEqual(risultato.device_model, "Galaxy S24")
        self.assertTrue(risultato.has_structural_signal)


class TestRelevance(unittest.TestCase):
    def _score(self, testo, trust=C.TRUST_NOISY):
        return classify.score_relevance(testo, extract.extract_all(testo), trust)

    def test_rollout_reale_passa(self):
        r = self._score("One UI 8.0 is now rolling out to the Galaxy S24 Ultra with build S928BXXU5BYG1")
        self.assertTrue(r.is_relevant)
        self.assertGreaterEqual(r.score, 5)

    def test_recensione_scartata(self):
        self.assertFalse(self._score("Galaxy S24 Ultra review: still the king").is_relevant)

    def test_rumor_scartato(self):
        self.assertFalse(self._score("Leak reveals Galaxy S26 design").is_relevant)

    def test_annuncio_al_futuro_scartato(self):
        # Il caso più insidioso: parla di update, ma non è ancora successo.
        r = self._score("These Samsung phones will get One UI 8 — here's when")
        self.assertFalse(r.is_relevant)
        self.assertIn("annuncio", r.explanation)

    def test_fonte_strutturata_bypassa_il_filtro(self):
        r = self._score("marble — Stable OS2.0.1.0.VNCEUXM", C.TRUST_STRUCTURED)
        self.assertTrue(r.is_relevant)

    def test_fonte_curata_ha_soglia_piu_bassa(self):
        testo = "Galaxy A55 firmware update released in Europe"
        self.assertTrue(self._score(testo, C.TRUST_CURATED).is_relevant)


class TestSeverity(unittest.TestCase):
    def _sev(self, testo, size=0.0):
        return classify.classify_severity(testo, extract.extract_all(testo), size)[0]

    def test_nuova_release_os(self):
        self.assertEqual(self._sev("Galaxy S24 gets Android 16 stable"), C.SEV_MAJOR)

    def test_versione_futura_non_cablata(self):
        # La versione precedente elencava "Android 15/16/17" a mano: qui la
        # logica regge anche per versioni non ancora esistenti.
        self.assertEqual(self._sev("Pixel 12 receives Android 20 stable update"), C.SEV_MAJOR)

    def test_beta_riconosciuta(self):
        self.assertEqual(self._sev("Android 16 QPR2 Beta 1 released for Pixel"), C.SEV_BETA)

    def test_patch_di_sicurezza(self):
        self.assertEqual(self._sev("Galaxy S23 receives the July 2026 security patch"), C.SEV_SECURITY)

    def test_pacchetto_pesante_major(self):
        self.assertEqual(self._sev("Full firmware package released", size=2.5), C.SEV_MAJOR)

    def test_semaforo_dimensione_rosso_sopra_soglia(self):
        # Sopra i 500 MB è sempre rosso, anche senza altri segnali testuali:
        # il peso del pacchetto è il proxy più oggettivo per il retest.
        self.assertEqual(self._sev("Galaxy S24 update released", size=0.6), C.SEV_MAJOR)

    def test_semaforo_dimensione_giallo_sotto_soglia_con_feature(self):
        testo = "Redmi Note 13 update brings camera features"
        r = classify.classify_severity(testo, extract.extract_all(testo), 0.2)
        self.assertEqual(r[0], C.SEV_FEATURE)

    def test_semaforo_dimensione_verde_sotto_soglia_solo_patch(self):
        r = classify.classify_severity(
            "Redmi Note 13 security update rolling out",
            extract.extract_all("Redmi Note 13 security update rolling out"),
            0.1,
        )
        self.assertEqual(r[0], C.SEV_SECURITY)

    def test_release_trimestrale_non_e_major(self):
        # Citare "Android 15" in un QPR non significa salto di major release.
        self.assertEqual(
            self._sev("Pixel 8 Pro — Android 15 QPR2 (AP4A.241205.013.B4) is now rolling out"),
            C.SEV_FEATURE,
        )

    def test_feature_drop_non_e_major(self):
        self.assertEqual(
            self._sev("Pixel Feature Drop rolling out with Android 16 improvements"),
            C.SEV_FEATURE,
        )

    def test_patch_che_cita_la_base_android(self):
        self.assertEqual(
            self._sev("Galaxy A54 gets the October 2025 security patch on Android 14"),
            C.SEV_SECURITY,
        )


class TestNormalizzazione(unittest.TestCase):
    def setUp(self):
        self.source = sources.Source("test", "Fonte di test", C.TRUST_CURATED, lambda: ([], None))

    def test_item_id_deduplica_fra_fonti(self):
        a = sources.RawItem(title="One UI 8.0 rolling out to Galaxy S24 Ultra (S928BXXU5BYG1)")
        b = sources.RawItem(title="Galaxy S24 Ultra: la build S928BXXU5BYG1 è in distribuzione")
        item_a = scan.normalize(a, self.source)
        item_b = scan.normalize(b, self.source)
        self.assertEqual(item_a["id"], item_b["id"])
        self.assertEqual(item_a["device_model"], "Galaxy S24 Ultra")

    def test_dati_della_fonte_hanno_precedenza(self):
        raw = sources.RawItem(
            title="marble — Stable OS2.0.1.0.VNCEUXM",
            brand=C.XIAOMI, device="Redmi Note 13 Pro", build="OS2.0.1.0.VNCEUXM",
            android_version=15,
        )
        item = scan.normalize(raw, self.source)
        self.assertEqual(item["device_model"], "Redmi Note 13 Pro")
        self.assertEqual(item["android_version"], 15)
        self.assertTrue(item["device_key"])

    def test_ricerca_generica_senza_modello_scartata(self):
        # Punteggio testuale alto (rollout + versione skin) ma nessun modello
        # preciso: da una ricerca Google News (fallback per i brand senza
        # fonte dedicata) non basta, perché non si saprebbe a quale device
        # applicarlo. Non vale per i feed editoriali (9to5Google, SamMobile,
        # ...), che restano governati solo dal punteggio di rilevanza.
        ricerca = sources.Source("news_test", "Ricerca di test", C.TRUST_NOISY,
                                  lambda: ([], None), is_web_search=True)
        raw = sources.RawItem(title="OnePlus starts rolling out the ColorOS 17 update")
        item = scan.normalize(raw, ricerca)
        self.assertFalse(item["is_relevant"])

    def test_ricerca_generica_con_modello_passa(self):
        ricerca = sources.Source("news_test", "Ricerca di test", C.TRUST_NOISY,
                                  lambda: ([], None), is_web_search=True)
        raw = sources.RawItem(title="OnePlus 12 starts receiving the ColorOS 15 stable update")
        item = scan.normalize(raw, ricerca)
        self.assertTrue(item["is_relevant"])


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        C.DB_PATH = self.tmp.name
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        os.unlink(self.tmp.name)

    def _item(self, **kwargs):
        base = {
            "id": "samsung|galaxy-s24|one-ui-8-0",
            "brand": C.SAMSUNG,
            "device_model": "Galaxy S24",
            "device_key": extract.device_key(C.SAMSUNG, "Galaxy S24"),
            "title": "One UI 8.0 rolling out",
            "os_version": "Android 16 · One UI 8.0",
            "severity": C.SEV_MAJOR,
            "is_relevant": True,
            "published": "2026-07-01T10:00:00+00:00",
        }
        base.update(kwargs)
        return base

    def test_upsert_segnala_solo_la_prima_volta(self):
        self.assertTrue(storage.upsert_update(self._item()))
        self.assertFalse(storage.upsert_update(self._item()))
        self.assertEqual(storage.count_updates(), 1)

    def test_upsert_arricchisce_i_campi_mancanti(self):
        storage.upsert_update(self._item(link="", build=None))
        storage.upsert_update(self._item(link="https://esempio.it", build="S921BXXU4CYG2"))
        riga = storage.get_updates()[0]
        self.assertEqual(riga["link"], "https://esempio.it")
        self.assertEqual(riga["build"], "S921BXXU4CYG2")

    def test_vista_per_dispositivo(self):
        storage.upsert_update(self._item(skin_name="One UI", skin_version="8.0",
                                         build="S921BXXU4CYG2"))
        storage.upsert_update(self._item(
            id="samsung|galaxy-s24|patch-2026-07", os_version="Patch 2026-07",
            patch_level="2026-07", severity=C.SEV_SECURITY,
            published="2026-07-20T10:00:00+00:00",
        ))
        dispositivi = storage.get_devices()
        self.assertEqual(len(dispositivi), 1)
        scheda = dispositivi[0]
        self.assertEqual(scheda["model"], "Galaxy S24")
        self.assertEqual(scheda["updates_total"], 2)
        # Lo stato del device è la somma delle rilevazioni, non solo l'ultima:
        # la patch più recente non deve cancellare la versione OS già nota.
        self.assertEqual(scheda["os_version"], "Android 16 · One UI 8.0")
        self.assertEqual(scheda["build"], "S921BXXU4CYG2")
        self.assertEqual(scheda["patch_level"], "2026-07")
        self.assertEqual(scheda["severity"], C.SEV_SECURITY)

    def test_watchlist(self):
        chiave = extract.device_key(C.SAMSUNG, "Galaxy S24")
        storage.add_to_watchlist(chiave, C.SAMSUNG, "Galaxy S24", "device primario di test")
        self.assertIn(chiave, storage.watched_keys())
        storage.upsert_update(self._item())
        self.assertEqual(storage.get_devices()[0]["watched"], 1)
        storage.remove_from_watchlist(chiave)
        self.assertNotIn(chiave, storage.watched_keys())

    def test_stato_notifica(self):
        storage.upsert_update(self._item())
        self.assertFalse(storage.is_notified("samsung|galaxy-s24|one-ui-8-0"))
        storage.mark_notified("samsung|galaxy-s24|one-ui-8-0")
        self.assertTrue(storage.is_notified("samsung|galaxy-s24|one-ui-8-0"))
        self.assertEqual(storage.clear_notified(), 1)

    def test_filtri_ricerca(self):
        storage.upsert_update(self._item())
        self.assertEqual(len(storage.get_updates(search="galaxy s24")), 1)
        self.assertEqual(len(storage.get_updates(search="pixel")), 0)
        self.assertEqual(len(storage.get_updates(brands=[C.PIXEL])), 0)

    def test_nome_modello_corretto_a_mano(self):
        """Il nome scelto a mano per un codice, vedi `web.main._cerca_davvero`
        e il bug reale che l'ha motivato: `RMX3933` ha più nomi commerciali
        veri (C61, Note 60, Note 60s, NARZO N61) e nessuno è oggettivamente
        «il» nome — la scelta si offre a chi il telefono ce l'ha."""
        self.assertIsNone(storage.get_nome_modello("RMX3933"))
        storage.set_nome_modello("RMX3933", "Note 60")
        self.assertEqual(storage.get_nome_modello("RMX3933"), "Note 60")

    def test_nome_modello_indifferente_a_maiuscole_e_spazi(self):
        storage.set_nome_modello("  rmx3933 ", "Note 60")
        self.assertEqual(storage.get_nome_modello("RMX3933"), "Note 60")
        self.assertEqual(storage.get_nome_modello("rmx3933"), "Note 60")

    def test_nome_modello_si_puo_correggere_di_nuovo(self):
        storage.set_nome_modello("RMX3933", "Note 60")
        storage.set_nome_modello("RMX3933", "Note 60s")
        self.assertEqual(storage.get_nome_modello("RMX3933"), "Note 60s")

    def test_nome_modello_vuoto_cancella_la_correzione(self):
        """Tornare alla scelta automatica: un nome vuoto CANCELLA, non
        salva una correzione vuota."""
        storage.set_nome_modello("RMX3933", "Note 60")
        storage.set_nome_modello("RMX3933", "")
        self.assertIsNone(storage.get_nome_modello("RMX3933"))
        self.assertNotIn("RMX3933", storage.get_nomi_modello())

    def test_nome_modello_senza_codice_non_fa_niente(self):
        storage.set_nome_modello("", "Note 60")
        storage.set_nome_modello("   ", "Note 60")
        self.assertEqual(storage.get_nomi_modello(), {})

    def test_get_nomi_modello_elenca_tutte_le_correzioni(self):
        storage.set_nome_modello("RMX3933", "Note 60")
        storage.set_nome_modello("CPH2781", "OPPO F31")
        elenco = storage.get_nomi_modello()
        self.assertEqual(set(elenco), {"RMX3933", "CPH2781"})
        self.assertEqual(elenco["RMX3933"]["nome"], "Note 60")
        self.assertIn("impostato_il", elenco["RMX3933"])


class TestScansioneCompleta(unittest.TestCase):
    """End-to-end: fonte simulata → scansione → vista per dispositivo.

    Verifica il comportamento che conta davvero: due notizie diverse sullo
    stesso telefono devono fondersi in una sola riga con l'ultimo valore
    *noto* di ciascun campo (la build dell'ultima patch, l'OS della release
    che l'ha introdotto), e rumor/recensioni non devono comparire.
    """

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def _fonte(self):
        righe = [
            ("Samsung starts rolling out One UI 8.0 with Android 16 to Galaxy S24 Ultra "
             "(S928BXXU5CYA1)", "2026-07-20"),
            ("Galaxy S24 Ultra receives the July 2026 security patch (S928BXXU6CYG3)",
             "2026-07-25"),
            ("Galaxy S25 Ultra review: the best camera phone of the year", "2026-07-26"),
            ("OnePlus 13 could get OxygenOS 16 next month, tipster claims", "2026-07-22"),
        ]
        fetch = lambda: (  # noqa: E731
            [sources.RawItem(title=t, link="https://example.test", published=d)
             for t, d in righe],
            None,
        )
        return sources.Source("fake", "Fonte simulata", C.TRUST_CURATED, fetch)

    def test_scansione_popola_la_vista_per_dispositivo(self):
        risultato = scan.run_scan(auto_notify=False, only_sources=[self._fonte()])
        self.assertFalse(risultato["skipped"])
        self.assertEqual(risultato["total"], 4)

        devices = storage.get_devices()
        modelli = [d["model"] for d in devices]
        self.assertIn("Galaxy S24 Ultra", modelli)
        # La recensione e il rumor non devono creare schede dispositivo.
        self.assertNotIn("Galaxy S25 Ultra", modelli)
        self.assertNotIn("OnePlus 13", modelli)

        s24 = next(d for d in devices if d["model"] == "Galaxy S24 Ultra")
        self.assertEqual(s24["updates_total"], 2)
        self.assertEqual(s24["os_version"], "Android 16 · One UI 8.0")
        self.assertEqual(s24["build"], "S928BXXU6CYG3")   # build della patch più recente
        self.assertEqual(s24["patch_level"], "2026-07")

    def test_seconda_scansione_non_duplica(self):
        fonte = self._fonte()
        scan.run_scan(auto_notify=False, only_sources=[fonte])
        secondo = scan.run_scan(auto_notify=False, only_sources=[fonte])
        self.assertEqual(secondo["new"], 0)
        self.assertEqual(len(storage.get_devices()), 1)

    def test_fonte_ufficiale_vince_su_notizia_rumorosa_piu_recente(self):
        """Regressione: prima di questa correzione, i campi mostrati per un
        dispositivo venivano scelti solo per data più recente. Una notizia
        generica (rumorosa) con un dato sbagliato, se più recente, poteva
        sovrascrivere il dato corretto di una fonte ufficiale strutturata —
        è esattamente quello che è successo con la versione Android/skin
        di HONOR X8c. Ora deve vincere l'affidabilità della fonte, non la
        sola data."""
        def fetch_ufficiale():
            return [sources.RawItem(
                title="Modello X — versione ufficiale Android 16",
                link="https://ufficiale.test", brand=C.HUAWEI, device="Modello X",
                android_version=16, size_info="Fonte ufficiale",
            )], None
        fonte_ufficiale = sources.Source(
            "test_strutturata", "Fonte strutturata (test)", C.TRUST_STRUCTURED,
            fetch_ufficiale, C.HUAWEI, "",
        )

        def fetch_rumorosa():
            return [sources.RawItem(
                title="Modello X gets confused Android 99 update rumor",
                link="https://rumor.test", brand=C.HUAWEI, device="Modello X",
                published="2030-01-01",  # deliberatamente nel futuro: piu' recente di qualsiasi altra data
                android_version=99,
            )], None
        fonte_rumorosa = sources.Source(
            "test_rumorosa", "Fonte rumorosa (test)", C.TRUST_NOISY,
            fetch_rumorosa, C.HUAWEI, "",
        )

        # Scansiono prima quella rumorosa, poi quella ufficiale: l'ordine di
        # scansione non deve contare, solo l'affidabilità della fonte.
        scan.run_scan(auto_notify=False, only_sources=[fonte_rumorosa])
        scan.run_scan(auto_notify=False, only_sources=[fonte_ufficiale])

        device = storage.get_devices(search="modello x")[0]
        self.assertEqual(device["android_version"], 16)

    def test_item_senza_data_di_pubblicazione_e_marcato_come_stimato(self):
        """Regressione: la panoramica mostrava tutto come 'di oggi' perché
        gli item privi di data di pubblicazione reale (es. un controllo di
        stato ufficiale che non pubblica una data per ogni release) veniva
        silenziosamente datato al momento della scansione, mescolato senza
        distinzione con le date vere delle notizie. Ora ogni item porta un
        flag esplicito che dice se la sua data è reale o solo stimata."""
        def fetch_senza_data():
            return [sources.RawItem(
                title="Modello Y — controllo di stato ufficiale",
                link="https://ufficiale.test", brand=C.HUAWEI, device="Modello Y",
                android_version=16,
                # deliberatamente NESSUN published: e' il caso reale di
                # Samsung FUS / Honor AER, che non hanno una data per release.
            )], None
        fonte = sources.Source(
            "test_senza_data", "Fonte senza data (test)", C.TRUST_STRUCTURED,
            fetch_senza_data, C.HUAWEI, "",
        )
        scan.run_scan(auto_notify=False, only_sources=[fonte])

        items = storage.get_updates(search="modello y")
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["published_is_estimated"])
        self.assertIsNone(items[0]["published"])

        # Uno storico dispositivo deve avere lo stesso flag.
        device_key = items[0]["device_key"]
        history = storage.get_device_history(device_key)
        self.assertTrue(history[0]["published_is_estimated"])


class TestRisoluzioneCodiceModello(unittest.TestCase):
    """Un codice tecnico (RMX3939) deve risolvere ai nomi commerciali reali,
    e la ricerca live deve usare quei nomi quando il codice grezzo non
    trova nulla — perché e' cosi' che i giornalisti scrivono i titoli."""

    MOBILEMODELS_CSV = (
        "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
        "RMX3939,mob,realme,realme,,,realme C61 Global,\n"
        "RMX3939,mob,realme,realme,,,realme C63,\n"
        "RMX3939,mob,realme,realme,,,realme NARZO N63,\n"
        "XT2323-1,mob,motorola,Motorola,,,Motorola Razr 40,\n"
    )
    GOOGLE_PLAY_CSV = (
        "Retail Branding,Marketing Name,Device,Model\n"
        "realme,C63,RMX3939,RMX3939\n"
    )

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        modelcodes.reset_cache()
        self._original_download = modelcodes._download
        self._original_rss_items = sources.rss_items

        def fake_download(url, source_key):
            if url == modelcodes.MOBILEMODELS_URL:
                return self.MOBILEMODELS_CSV.encode("utf-8-sig")
            if url == modelcodes.GOOGLE_PLAY_URL:
                return self.GOOGLE_PLAY_CSV.encode("utf-16")
            return None

        modelcodes._download = fake_download

    def tearDown(self):
        modelcodes._download = self._original_download
        modelcodes.reset_cache()
        sources.rss_items = self._original_rss_items
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_risolve_piu_nomi_commerciali_da_entrambe_le_fonti(self):
        nomi = modelcodes.resolve("RMX3939")
        # Dalla fonte MobileModels (3 varianti) più "realme C63" dalla lista
        # Google Play — già presente da MobileModels, quindi senza duplicati.
        self.assertEqual(
            nomi, ["realme C61 Global", "realme C63", "realme NARZO N63"]
        )

    def test_risolve_case_insensitive(self):
        self.assertEqual(modelcodes.resolve("rmx3939"), modelcodes.resolve("RMX3939"))

    def test_codice_sconosciuto_lista_vuota(self):
        self.assertEqual(modelcodes.resolve("Galaxy S24 Ultra"), [])

    def test_ricerca_live_usa_il_nome_risolto_col_codice_con_spazio(self):
        def fake_rss_items(urls, brand, size_info, limit=None, timeout=None):
            if "C63" in urls[0]:
                return [sources.RawItem(
                    title="realme C63 gets Android 14 update", link="https://x.test",
                    published="2026-07-10", brand=brand, size_info=size_info,
                )], None
            return [], "nessun risultato"

        sources.rss_items = fake_rss_items
        items, error = sources.search_model_live("rmx 3939")

        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertIn("C63", items[0].device)
        # Il codice sta nella descrizione, non nel nome del modello.
        self.assertNotIn("RMX3939", items[0].device)
        self.assertIn("RMX3939", items[0].size_info)

    def test_codice_grezzo_senza_corrispondenza_prova_comunque(self):
        # Se il codice non risolve a nulla, la ricerca deve comunque provare
        # la query originale (comportamento precedente), non arrendersi subito.
        def fake_rss_items(urls, brand, size_info, limit=None, timeout=None):
            return [], "nessun risultato"

        sources.rss_items = fake_rss_items
        items, error = sources.search_model_live("Modello Del Tutto Sconosciuto 9999")
        self.assertEqual(items, [])
        self.assertIn("Modello Del Tutto Sconosciuto 9999", error)

    def test_bom_iniziale_del_csv_mobilemodels_non_azzera_l_indice(self):
        # Regressione: il CSV MobileModels pubblica un BOM UTF-8 a inizio
        # file. Senza rimuoverlo, il nome della prima colonna letto da
        # DictReader diventa "\ufeffmodel" invece di "model", e OGNI riga
        # viene scartata silenziosamente — il download riesce ma l'indice
        # risulta vuoto, mascherando il vero problema dietro un falso
        # "codice non trovato".
        csv_minimo = (
            "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
            "RMX3939,mob,realme,realme,,,realme C63,\n"
        )
        modelcodes._download = lambda url, source_key: (
            csv_minimo.encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None
        )
        modelcodes.reset_cache()
        self.assertEqual(modelcodes.resolve("RMX3939"), ["realme C63"])
        self.assertIn("indicizzati", modelcodes.status())
        self.assertNotIn("0 codici", modelcodes.status())

    def test_google_play_utf16_decodificato_correttamente(self):
        # Regressione: il file ufficiale Google Play è UTF-16, non UTF-8.
        # Decodificarlo come UTF-8 produce testo illeggibile invece di un
        # errore esplicito — un fallimento silenzioso dello stesso tipo del
        # bug del BOM sopra, ma per una causa diversa (codifica, non BOM).
        modelcodes._download = lambda url, source_key: (
            self.GOOGLE_PLAY_CSV.encode("utf-16")
            if url == modelcodes.GOOGLE_PLAY_URL else None
        )
        modelcodes.reset_cache()
        nomi = modelcodes.resolve("RMX3939")
        self.assertEqual(nomi, ["realme C63"])
        self.assertIn("indicizzati", modelcodes.status())

    def test_una_fonte_rotta_non_azzera_l_altra(self):
        # Se Google Play non risponde ma MobileModels sì (o viceversa), la
        # risoluzione deve comunque funzionare con quello che ha.
        modelcodes._download = lambda url, source_key: (
            self.MOBILEMODELS_CSV.encode("utf-8-sig")
            if url == modelcodes.MOBILEMODELS_URL else None
        )
        modelcodes.reset_cache()
        self.assertEqual(
            modelcodes.resolve("RMX3939"),
            ["realme C61 Global", "realme C63", "realme NARZO N63"],
        )


class TestIdentificazioneIMEI(unittest.TestCase):
    """Identificazione marca/modello dal TAC (prime 8 cifre dell'IMEI).
    Verifica anche esplicitamente che l'IMEI non venga MAI scritto nel
    database — solo usato in memoria per il calcolo del TAC."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        imeicheck.reset_cache()
        self._original_download = imeicheck._download
        # Le basi dati SUPPLEMENTARI vanno zittite, non solo la principale:
        # `_build_index` le interroga tutte, e senza questa riga un test
        # che stubba una sola fonte scarica davvero le altre — lento, e
        # dipendente dalla rete proprio dove il progetto promette di non
        # toccarla.
        self._original_scarica_url = imeicheck._scarica_url
        imeicheck._scarica_url = lambda url, minimo=10_000: None

    def tearDown(self):
        imeicheck._download = self._original_download
        imeicheck._scarica_url = self._original_scarica_url
        imeicheck.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    @staticmethod
    def _luhn_checkdigit(digits14: str) -> str:
        total = 0
        for i, ch in enumerate(digits14):
            n = int(ch)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return str((10 - (total % 10)) % 10)

    def _imei_valido(self, base14: str) -> str:
        return base14 + self._luhn_checkdigit(base14)

    def _xlsx_di_prova(self) -> bytes:
        import io as _io
        import openpyxl as _openpyxl

        wb = _openpyxl.Workbook()
        ws = wb.active
        ws.title = "Motorola"
        ws.append(["brand", "tac", "specs"])
        ws.append(["MOTOROLA", "35692411", "Moto G84 5G, XT2347-1, 2023"])
        buf = _io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_luhn_valido_e_non_valido(self):
        imei_ok = self._imei_valido("35692411234567")
        self.assertTrue(imeicheck.is_valid_imei(imei_ok))
        imei_rotto = imei_ok[:-1] + str((int(imei_ok[-1]) + 1) % 10)
        self.assertFalse(imeicheck.is_valid_imei(imei_rotto))
        self.assertFalse(imeicheck.is_valid_imei("123"))

    def test_identifica_marca_e_modello_dal_tac(self):
        imeicheck._download = lambda: self._xlsx_di_prova()
        imei = self._imei_valido("35692411234567")
        risultato = imeicheck.identify(imei)
        self.assertIsNotNone(risultato)
        brand, specs = risultato
        self.assertEqual(brand, "MOTOROLA")
        self.assertIn("Moto G84", specs)

    def test_tac_sconosciuto_ritorna_none(self):
        imeicheck._download = lambda: self._xlsx_di_prova()
        imei = self._imei_valido("99999999234567")
        self.assertIsNone(imeicheck.identify(imei))

    def test_imei_non_finisce_mai_nel_database(self):
        """Verifica esplicita del principio di privacy: dopo aver
        identificato un IMEI, nessuna tabella del database deve contenere
        quella stringa esatta da nessuna parte."""
        imeicheck._download = lambda: self._xlsx_di_prova()
        imei = self._imei_valido("35692411234567")
        imeicheck.identify(imei)

        conn = storage.connect()
        tabelle = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        for tabella in tabelle:
            colonne = [r["name"] for r in conn.execute(f"PRAGMA table_info({tabella})").fetchall()]
            for colonna in colonne:
                valori = conn.execute(f"SELECT {colonna} FROM {tabella}").fetchall()
                for (valore,) in valori:
                    if valore is not None:
                        self.assertNotIn(imei, str(valore),
                                          f"IMEI trovato in {tabella}.{colonna} — non deve mai essere salvato")


class TestImmagineDispositivo(unittest.TestCase):
    """La ricerca immagine deve passare dalla cache al secondo giro, e non
    ritentare all'infinito un modello per cui Wikipedia non ha nulla."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._original_get = images._get

    def tearDown(self):
        images._get = self._original_get
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_seconda_chiamata_usa_la_cache(self):
        chiamate = {"n": 0}

        class SearchResp:
            status_code = 200
            def json(self):
                return {"query": {"search": [{"title": "Samsung Galaxy S24 Ultra"}]}}

        class SummaryResp:
            status_code = 200
            def json(self):
                return {"originalimage": {"source": "https://example.test/s24.jpg"}}

        def fake_get(url, params, timeout=None, headers=None):
            chiamate["n"] += 1
            return SearchResp() if "action" in params else SummaryResp()

        images._get = fake_get
        prima = images.find_device_image("Galaxy S24 Ultra")
        seconda = images.find_device_image("Galaxy S24 Ultra")

        self.assertEqual(prima, "https://example.test/s24.jpg")
        self.assertEqual(prima, seconda)
        self.assertEqual(chiamate["n"], 2)  # solo dalla prima chiamata (ricerca + riepilogo)

    def test_nessun_risultato_non_viene_ricercato_di_nuovo(self):
        chiamate = {"n": 0}

        class VuotaResp:
            status_code = 200
            def json(self):
                return {"query": {"search": []}}

        def fake_get(url, params, timeout=None, headers=None):
            chiamate["n"] += 1
            return VuotaResp()

        images._get = fake_get
        self.assertIsNone(images.find_device_image("Modello Inesistente XYZ"))
        self.assertIsNone(images.find_device_image("Modello Inesistente XYZ"))
        self.assertEqual(chiamate["n"], 1)

    def test_un_titolo_senza_niente_in_comune_viene_scartato(self):
        """Misurato in produzione: cercando un realme C61 la ricerca su
        Wikipedia ha risposto con un telefono Xiaomi, e la scheda ha
        mostrato il logo sbagliato. Il titolo trovato deve condividere
        almeno una parola con la domanda, o va scartato — nessuna
        immagine è meglio di quella di un telefono diverso."""
        class SearchResp:
            status_code = 200
            def json(self):
                return {"query": {"search": [{"title": "Xiaomi Mi CC9"}]}}

        def fake_get(url, params, timeout=None, headers=None):
            return SearchResp()

        images._get = fake_get
        self.assertIsNone(images.find_device_image("Oppo / Realme / OnePlus C61"))

    def test_un_titolo_con_una_parola_in_comune_viene_accettato(self):
        class SearchResp:
            status_code = 200
            def json(self):
                return {"query": {"search": [{"title": "Realme C61"}]}}

        class SummaryResp:
            status_code = 200
            def json(self):
                return {"originalimage": {"source": "https://example.test/c61.jpg"}}

        def fake_get(url, params, timeout=None, headers=None):
            return SearchResp() if "action" in params else SummaryResp()

        images._get = fake_get
        self.assertEqual(images.find_device_image("Oppo / Realme / OnePlus C61"),
                         "https://example.test/c61.jpg")


class TestCronologiaRicerche(unittest.TestCase):
    """Ogni ricerca live riuscita deve lasciare una riga condensata
    (modello + firmware) nella cronologia ricerche."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._original_rss_items = sources.rss_items
        # Isola dalla rete anche la risoluzione codici modello: senza questo,
        # "moto g14" può corrispondere per davvero a una voce del CSV
        # Google Play reale (device.py ha accesso rete in questo ambiente),
        # cambiando il nome atteso in modo non deterministico a seconda di
        # cosa contiene il dataset in quel momento.
        self._original_modelcodes_cache = modelcodes._memory_cache
        modelcodes._memory_cache = {}

    def tearDown(self):
        sources.rss_items = self._original_rss_items
        modelcodes._memory_cache = self._original_modelcodes_cache
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def _rss_con_titolo(self, title, published):
        def fake(urls, brand, size_info, limit=None, timeout=None):
            return [sources.RawItem(title=title, link="https://x.test",
                                     published=published, brand=brand, size_info=size_info)], None
        return fake

    def test_ricerca_riuscita_finisce_in_cronologia(self):
        sources.rss_items = self._rss_con_titolo(
            "Moto G14 gets July 2026 security patch update", "2026-07-10")
        scan.search_model("moto g14")

        storia = storage.get_search_history()
        self.assertEqual(len(storia), 1)
        self.assertEqual(storia[0]["model"], "Moto G14")
        self.assertEqual(storia[0]["query"], "moto g14")
        self.assertIn("2026-07", storia[0]["firmware"])

    def test_fonte_ufficiale_senza_firmware_non_oscura_una_patch_datata(self):
        """Alcune fonti ufficiali confermano che un modello ESISTE senza
        pubblicarne la versione (il catalogo Android Enterprise
        Recommended, l'elenco Oppo). Preferirle comunque, solo perché
        strutturate, faceva finire in cronologia un «—» mentre una notizia
        riportava una patch datata: la fonte più autorevole vince, ma solo
        se ha davvero qualcosa da dire."""
        sources.rss_items = self._rss_con_titolo(
            "Moto G14 gets July 2026 security patch update", "2026-07-10")

        def solo_esistenza(model_name):
            return [sources.RawItem(
                title=f"{model_name} — dispositivo certificato",
                brand=C.VIVO, device="Moto G14",
                size_info="Android Enterprise Recommended",
            )]

        originale = sources._lookup_order
        sources._lookup_order = lambda brand: [
            sources.StructuredLookup(
                None, solo_esistenza, "basso", "catalogo di prova",
                firmware_kind=C.FW_SUPPORT,
            )
        ]
        try:
            scan.search_model("moto g14")
        finally:
            sources._lookup_order = originale

        storia = storage.get_search_history()
        self.assertEqual(len(storia), 1)
        self.assertIn("2026-07", storia[0]["firmware"],
                      "la cronologia ha preferito una voce senza firmware")

    def test_piu_ricerche_restano_in_ordine_cronologico_inverso(self):
        sources.rss_items = self._rss_con_titolo("Foo Phone update", "2026-01-01")
        scan.search_model("foo phone")
        sources.rss_items = self._rss_con_titolo("Bar Phone update", "2026-02-01")
        scan.search_model("bar phone")

        storia = storage.get_search_history()
        self.assertEqual([h["model"] for h in storia], ["Bar Phone", "Foo Phone"])

    def test_svuota_cronologia(self):
        sources.rss_items = self._rss_con_titolo("Foo Phone update", "2026-01-01")
        scan.search_model("foo phone")
        self.assertEqual(len(storage.get_search_history()), 1)
        storage.clear_search_history()
        self.assertEqual(len(storage.get_search_history()), 0)


class TestRicercaLiveModelloQualunque(unittest.TestCase):
    """La ricerca live deve riconoscere QUALSIASI modello scritto dall'utente
    come dispositivo — anche uno che nessun pattern regex del progetto
    conosce — perché è il meccanismo pensato per coprire modelli di nicchia
    o più vecchi che le fonti strutturate/curate non intercettano mai."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._original_rss_items = sources.rss_items
        self._original_lookup_order = sources._lookup_order

    def tearDown(self):
        sources.rss_items = self._original_rss_items
        sources._lookup_order = self._original_lookup_order
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_modello_sconosciuto_ai_pattern_diventa_dispositivo(self):
        def fake_rss_items(urls, brand, size_info, limit=None, timeout=None):
            return [
                sources.RawItem(
                    title="Wiko View5 receives Android 10 security update in Europe",
                    link="https://x.test/1", published="2021-08-10",
                    brand=brand, size_info=size_info,
                )
            ], None

        sources.rss_items = fake_rss_items
        risultato = scan.search_model("wiko view5")

        self.assertIsNone(risultato["error"])
        # Si asserisce che la notizia DIVENTI un dispositivo, non che sia
        # l'unica voce: da quando il nome commerciale arriva ai codici come
        # ci arriva il codice stesso, un modello noto al dataset riceve
        # anche la voce «riconosciuto». È informazione vera e coerente —
        # stesso `device_key`, quindi un dispositivo solo in archivio — e
        # legare il test al numero di voci lo farebbe fallire ogni volta
        # che il riconoscimento migliora.
        self.assertTrue(risultato["items"])
        item = next(i for i in risultato["items"] if i.get("is_relevant"))
        self.assertEqual(item["device_model"], "Wiko View5")
        self.assertTrue(item["device_key"])

        trovati = storage.get_devices(search="wiko")
        self.assertEqual(len(trovati), 1)
        self.assertEqual(trovati[0]["model"], "Wiko View5")

    def test_ricerca_vuota_non_chiama_la_rete(self):
        risultato = scan.search_model("   ")
        self.assertIsNotNone(risultato["error"])
        self.assertEqual(risultato["items"], [])

    def test_dato_strutturato_gia_in_archivio_vince_su_ricerca_live_vuota(self):
        # Un modello già presente in archivio con un dato da fonte
        # STRUCTURED (es. il catalogo Xiaomi dopo un giro periodico) deve
        # risultare comunque "trovato" anche se in questo preciso momento
        # la ricerca live su Google News non intercetta nessuna notizia:
        # il dato ufficiale è già la risposta, non serve la notizia.
        fonte_strutturata = sources.Source(
            "test_xiaomi", "Xiaomi (test)", C.TRUST_STRUCTURED,
            lambda: ([sources.RawItem(
                title="Redmi 12 India — Stable OS2.0.204.0.VMXINXM",
                link="https://x.test/redmi12", published="2026-06-05",
                brand=C.XIAOMI, device="Redmi 12 India", build="OS2.0.204.0.VMXINXM",
                android_version=15,
            )], None),
        )
        scan.run_scan(auto_notify=False, only_sources=[fonte_strutturata])

        def fake_rss_items_vuoto(urls, brand, size_info, limit=None, timeout=None):
            return [], "nessun risultato"
        sources.rss_items = fake_rss_items_vuoto
        # Anche le fonti strutturate vanno zittite, non solo le notizie:
        # senza questo il test interroga DAVVERO il catalogo Xiaomi, che
        # per «Redmi 12 India» risponde, e la premessa «ricerca live vuota»
        # non regge più. Il risultato dipendeva dalla rete, cioè dal caso.
        sources._lookup_order = lambda brand: []

        risultato = scan.search_model("Redmi 12 India")
        self.assertIsNone(risultato["error"])
        self.assertEqual(risultato["items"], [])
        self.assertIsNotNone(risultato["existing_device"])
        self.assertTrue(risultato["existing_is_structured"])
        self.assertEqual(risultato["existing_device"]["build"], "OS2.0.204.0.VMXINXM")


class TestHonorAER(unittest.TestCase):
    """La pagina ufficiale Honor 'Android Enterprise Recommended' e' una
    fonte diretta (non dipendente da notizie) per la versione Android di
    ogni modello elencato."""

    SAMPLE = (
        "HONOR 200\n\n06/2027 at least（Global）\n\n"
        "Shipped version: 14  \nFuture version: 15&16 at least（Global）\n\n"
        "[More details >](https://www.honor.com/global/support/bulletin/)\n\n"
        "HONOR X8c\n\n01/2027 at least（Global）\n\n"
        "Shipped version: 15  \nFuture version: 16 at least（Global）\n\n"
        "[More details >](https://www.honor.com/global/support/bulletin/)\n"
    )

    def setUp(self):
        # `fetch_honor_aer` tiene la pagina in cache per un'ora (vedi
        # `_CacheDiFonte` in sources.py): senza azzerarla, un test di
        # questa classe riceverebbe la risposta mockata da quello prima
        # invece di chiamare di nuovo l'`http_get` finto appena impostato.
        sources.reset_honor_aer_cache()

    def tearDown(self):
        sources.reset_honor_aer_cache()

    def test_estrae_dispositivi_e_versioni(self):
        class FakeResponse:
            status_code = 200
            text = TestHonorAER.SAMPLE

        original = sources.http_get
        sources.http_get = lambda url, timeout=None: FakeResponse()
        try:
            items, error = sources.fetch_honor_aer()
        finally:
            sources.http_get = original

        self.assertIsNone(error)
        self.assertEqual(len(items), 2)
        by_device = {i.device: i for i in items}
        # La versione dichiarata deve essere quella EFFETTIVA di fabbrica
        # ("Shipped version"), non la promessa di aggiornamento futuro.
        self.assertEqual(by_device["HONOR 200"].android_version, 14)
        self.assertEqual(by_device["HONOR X8c"].android_version, 15)

    def test_impegno_futuro_non_viene_spacciato_per_versione_attuale(self):
        """Regressione su un errore reale già commesso: la pagina Honor
        elenca sia "Shipped version: 15" (la versione che il telefono HA)
        sia "Future version: 16 at least" (una PROMESSA di aggiornamento).
        Usare la seconda come `android_version` faceva dichiarare all'app
        una versione che il dispositivo non ha ancora — l'HONOR X8c veniva
        riportato ad Android 16 quando è realmente su Android 15."""
        class FakeResponse:
            status_code = 200
            text = TestHonorAER.SAMPLE

        original = sources.http_get
        sources.http_get = lambda url, timeout=None: FakeResponse()
        try:
            items, _ = sources.fetch_honor_aer()
        finally:
            sources.http_get = original

        x8c = next(i for i in items if i.device == "HONOR X8c")
        self.assertEqual(x8c.android_version, 15, "deve essere la versione di fabbrica")
        self.assertNotEqual(x8c.android_version, 16, "16 è la promessa futura, non la versione attuale")
        # L'impegno futuro resta comunque visibile come contesto.
        self.assertIn("16", x8c.title)

    def test_pagina_vuota_segnala_errore_invece_di_lista_vuota_silenziosa(self):
        class FakeResponse:
            status_code = 200
            text = "<html>pagina cambiata, nessuna tabella qui</html>"

        original = sources.http_get
        sources.http_get = lambda url, timeout=None: FakeResponse()
        try:
            items, error = sources.fetch_honor_aer()
        finally:
            sources.http_get = original
        self.assertEqual(items, [])
        self.assertIsNotNone(error)


class TestOppoUfficiale(unittest.TestCase):
    """Fonte ufficiale Oppo/OnePlus/realme (API OxygenUpdater), usata su
    accordo con i manutentori. Vedi la nota in cima alla sezione in
    sources.py prima di modificarla."""

    RISPOSTA = {
        "version_number": "CPH2653_16.0.9.401(EX01)",
        "ota_version_number": "CPH2653_11.F.91_2910_202607050051",
        "changelog": "##System\nMigliorie varie.",
        "description": "#CPH2653_16.0.9.401(EX01)\n##2026-07-08\n\n##System\nMigliorie varie.",
        "download_url": "https://example.test/ota.zip",
        "download_size": 8261206016,
    }

    def _con_risposta(self, payload, status=200):
        class FakeResponse:
            status_code = status
            def json(self):
                return payload
        return lambda path: FakeResponse()

    def test_estrae_build_data_e_dimensione(self):
        original = sources._oxygen_get
        original_devices = sources.OPPO_OFFICIAL_DEVICES
        sources._oxygen_get = self._con_risposta(self.RISPOSTA)
        sources.OPPO_OFFICIAL_DEVICES = [(151, "OnePlus 13")]
        try:
            items, error = sources.fetch_oppo_official()
        finally:
            sources._oxygen_get = original
            sources.OPPO_OFFICIAL_DEVICES = original_devices

        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.device, "OnePlus 13")
        self.assertEqual(item.build, "CPH2653_16.0.9.401(EX01)")
        # La data non ha un campo proprio: va estratta dall'intestazione
        # markdown nella descrizione, non inventata dalla data di scansione.
        self.assertTrue(item.published.startswith("2026-07-08"))
        self.assertAlmostEqual(item.size_gb, 7.69, places=1)

    def test_usa_lo_user_agent_configurato(self):
        """L'UA deve arrivare da config (OXYGEN_USER_AGENT), non essere
        cablato: quando i manutentori metteranno in whitelist un UA
        dedicato al tracker dev'essere una modifica di sola configurazione."""
        visti = {}

        class FakeResponse:
            status_code = 403
            def json(self):
                return {}

        def fake_get(url, timeout=None, headers=None):
            visti.update(headers or {})
            return FakeResponse()

        original = sources.requests
        class FakeRequests:
            get = staticmethod(fake_get)
        sources.requests = FakeRequests
        try:
            sources._oxygen_get("mostRecentUpdateData/151/2")
        finally:
            sources.requests = original

        self.assertEqual(visti.get("User-Agent"), C.OXYGEN_USER_AGENT)

    def test_nessun_device_raggiungibile_segnala_errore(self):
        original = sources._oxygen_get
        original_devices = sources.OPPO_OFFICIAL_DEVICES
        sources._oxygen_get = self._con_risposta({}, status=403)
        sources.OPPO_OFFICIAL_DEVICES = [(151, "OnePlus 13")]
        try:
            items, error = sources.fetch_oppo_official()
        finally:
            sources._oxygen_get = original
            sources.OPPO_OFFICIAL_DEVICES = original_devices
        self.assertEqual(items, [])
        self.assertIsNotNone(error)


class TestMotorolaLolinet(unittest.TestCase):
    """Il parsing dell'indice h5ai del mirror lolinet.com per Motorola.

    Non facciamo una vera chiamata di rete (il sandbox non ce l'ha e non
    dovrebbe servire ai test): verifichiamo solo che il regex estragga
    correttamente file, data e build da una riga di tabella realistica,
    tenga il file più recente fra più righe e scarti risposte vuote/rotte
    senza sollevare eccezioni.
    """

    def _riga(self, filename: str, data: str) -> str:
        return (
            f'<tr><td class="fb-n"><a href="{filename}">{filename}</a></td>'
            f'<td class="fb-d">{data}</td></tr>'
        )

    def test_estrae_file_piu_recente_fra_piu_righe(self):
        html = (
            self._riga(
                "XT2323-1_LYNKCO_RETEU_14_U3TVS34.1-60-5-5_subsidy-DEFAULT_"
                "regulatory-DEFAULT_cid50_CFC.xml.zip",
                "2024-12-08 00:03",
            )
            + self._riga(
                "XT2323-1_LYNKCO_RETEU_15_V1TVS35H.41-24-6-7_subsidy-DEFAULT_"
                "regulatory-DEFAULT_cid50_CFC.xml.zip",
                "2025-10-16 23:10",
            )
        )
        matches = sources._LOLINET_FILE_RE.findall(html)
        self.assertEqual(len(matches), 2)
        filename, data = max(matches, key=lambda m: m[1])
        self.assertIn("V1TVS35H.41-24-6-7", filename)
        self.assertEqual(data, "2025-10-16 23:10")

    def test_estrae_android_e_build_dal_nome_file(self):
        filename = (
            "XT2323-1_LYNKCO_RETEU_15_V1TVS35H.41-24-6-7_subsidy-DEFAULT_"
            "regulatory-DEFAULT_cid50_CFC.xml.zip"
        )
        m = sources._LOLINET_NAME_RE.search(filename)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "15")
        self.assertEqual(m.group(3), "V1TVS35H.41-24-6-7")

    def test_pagina_vuota_non_solleva_eccezioni(self):
        self.assertEqual(sources._LOLINET_FILE_RE.findall("<html>vuota</html>"), [])

    def test_elenco_dispositivi_ha_anno_codename_nome(self):
        self.assertGreater(len(sources.MOTOROLA_LOLINET_DEVICES), 20)
        for year, codename, model in sources.MOTOROLA_LOLINET_DEVICES:
            self.assertIsInstance(year, int)
            self.assertTrue(codename.islower())
            self.assertTrue(model)


class TestPixelOtaPerPosizione(unittest.TestCase):
    """La pagina Pixel OTA e' cambiata piu' volte (Google ha ristrutturato il
    sito). Questi test proteggono il pattern chiave: dispositivo e build si
    associano per POSIZIONE nella tabella, non tramite una mappa di
    nomi-in-codice, cosi' un codename mai visto prima (es. Pixel 10) non
    rompe l'estrazione."""

    def test_dispositivi_e_build_nello_stesso_ordine(self):
        html = (
            "| Pixel 6 | oriole_beta-ota-bp41.250916.015-c409c359.zip |\n"
            "| Pixel 9 Pro Fold | comet_beta-ota-bp41.250916.015.a1-aeb0389b.zip |\n"
            "| Pixel 10 | frankel_beta-ota-bp41.250916.015.a1-44d384b0.zip |\n"
        )
        devices = re.findall(sources._PIXEL_DEVICE_RE.pattern, html)
        builds = [m.group(1) for m in sources._PIXEL_FILENAME_RE.finditer(html)]
        self.assertEqual(devices, ["Pixel 6", "Pixel 9 Pro Fold", "Pixel 10"])
        self.assertEqual(len(builds), 3)
        self.assertIn("bp41.250916.015", builds[0])

    def test_data_con_mese_per_esteso(self):
        from core.util import iso
        self.assertEqual(iso("November 10, 2025")[:10], "2025-11-10")


class TestRicercaMultiMarcaEndToEnd(unittest.TestCase):
    """Verifica esplicita, marca per marca, che l'intera pipeline (codice
    tecnico → nome commerciale → query di ricerca semplice → item trovato
    con la sua ultima informazione di aggiornamento) funzioni.

    Le query Google News reali non sono raggiungibili da questo sandbox di
    test (nessun accesso di rete), quindi qui si simula il livello HTTP più
    basso (`rss_items`) con risposte realistiche — l'obiettivo è verificare
    che la LOGICA di risoluzione, cascata e visualizzazione sia corretta
    per ciascuna marca, non che Google News risponda davvero in questo
    momento (quello lo si scopre solo con un test dal vivo sull'app)."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        modelcodes.reset_cache()
        self._original_rss_items = sources.rss_items
        self._original_download = modelcodes._download

    def tearDown(self):
        sources.rss_items = self._original_rss_items
        modelcodes._download = self._original_download
        modelcodes.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def _scenario(self, mobilemodels_rows: str, google_play_rows: str,
                  matching_text: str, news_title: str, published: str):
        """Prepara un caso: database codici con la mappatura data, e una
        finta risposta Google News che risponde solo quando la query
        contiene `matching_text` (il nome commerciale risolto), non quando
        contiene il codice tecnico grezzo — così il test fallisce se la
        risoluzione codice→nome smette di funzionare."""
        mm_csv = "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n" + mobilemodels_rows
        gp_csv = "Retail Branding,Marketing Name,Device,Model\n" + google_play_rows

        def fake_download(url, source_key):
            if url == modelcodes.MOBILEMODELS_URL:
                return mm_csv.encode("utf-8-sig")
            if url == modelcodes.GOOGLE_PLAY_URL:
                return gp_csv.encode("utf-16")
            return None

        modelcodes._download = fake_download
        modelcodes.reset_cache()

        def fake_rss_items(urls, brand, size_info, limit=None, timeout=None):
            from urllib.parse import unquote
            decoded_url = unquote(urls[0])
            if matching_text.lower() in decoded_url.lower():
                return [sources.RawItem(
                    title=news_title, link="https://x.test",
                    published=published, brand=brand, size_info=size_info,
                )], None
            return [], "nessun risultato"

        sources.rss_items = fake_rss_items

    def test_realme_rmx3939(self):
        self._scenario(
            mobilemodels_rows="RMX3939,mob,realme,realme,,,realme C63,\n",
            google_play_rows="realme,C63,RMX3939,RMX3939\n",
            matching_text="C63",
            news_title="realme C63 gets Android 14 update with July 2026 security patch",
            published="2026-07-15",
        )
        items, error = sources.search_model_live("RMX3939")
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertIn("C63", items[0].device)
        # Il codice NON deve stare nel nome (vedi
        # TestNomeModelloSenzaDecorazioni): sta nella descrizione.
        self.assertNotIn("RMX3939", items[0].device)
        self.assertIn("RMX3939", items[0].size_info)
        self.assertEqual(items[0].published, "2026-07-15")

    def test_honor_abr_lx1(self):
        self._scenario(
            mobilemodels_rows="ABR-LX1,mob,honor,Honor,,,HONOR X8c,\n",
            google_play_rows="HONOR,X8c,ABR-LX1,ABR-LX1\n",
            matching_text="X8c",
            news_title="HONOR X8c receives Android 15 update with MagicOS 9",
            published="2026-06-20",
        )
        items, error = sources.search_model_live("ABR-LX1")
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertIn("X8c", items[0].device)

    def test_samsung_sm_s928b(self):
        self._scenario(
            mobilemodels_rows="SM-S928B,mob,samsung,Samsung,,,Galaxy S24 Ultra,\n",
            google_play_rows="samsung,Galaxy S24 Ultra,b0q,SM-S928B\n",
            matching_text="Galaxy S24 Ultra",
            news_title="Galaxy S24 Ultra gets One UI 8 stable update",
            published="2026-05-10",
        )
        items, error = sources.search_model_live("SM-S928B")
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertIn("Galaxy S24 Ultra", items[0].device)

    def test_xiaomi_codename(self):
        self._scenario(
            mobilemodels_rows="22101316UG,mob,xiaomi,Xiaomi,,,Xiaomi 12T Pro,\n",
            google_play_rows="Xiaomi,12T Pro,diting,22101316UG\n",
            matching_text="12T Pro",
            news_title="Xiaomi 12T Pro receives HyperOS 2.0 update",
            published="2026-04-01",
        )
        items, error = sources.search_model_live("22101316UG")
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertIn("12T Pro", items[0].device)

    def test_oneplus_cph_code(self):
        self._scenario(
            mobilemodels_rows="CPH2581,mob,oneplus,OnePlus,,,OnePlus 12,\n",
            google_play_rows="OnePlus,12,CPH2581,CPH2581\n",
            matching_text="OnePlus 12",
            news_title="OnePlus 12 gets OxygenOS 15 stable update",
            published="2026-03-12",
        )
        items, error = sources.search_model_live("CPH2581")
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertIn("OnePlus 12", items[0].device)

    def test_motorola_xt_code(self):
        self._scenario(
            mobilemodels_rows="XT2323-1,mob,motorola,Motorola,,,Motorola Razr 40,\n",
            google_play_rows="Motorola,Razr 40,lynkco,XT2323-1\n",
            matching_text="Razr 40",
            news_title="Motorola Razr 40 receives Android 15 update",
            published="2026-02-18",
        )
        items, error = sources.search_model_live("XT2323-1")
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertIn("Razr 40", items[0].device)

    def test_codice_non_in_nessun_database_usa_comunque_la_query_grezza(self):
        # Nessuna mappatura per questo codice in nessuna delle due fonti:
        # la ricerca deve comunque provare il testo originale (non arrendersi
        # subito), e trovarlo se la notizia esiste con quel testo esatto.
        self._scenario(
            mobilemodels_rows="ALTROCODICE,mob,altro,Altro,,,Altro Modello,\n",
            google_play_rows="Altro,Modello,ALTROCODICE,ALTROCODICE\n",
            matching_text="XYZ9999",
            news_title="XYZ9999 gets a rare update",
            published="2026-01-01",
        )
        items, error = sources.search_model_live("XYZ9999")
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)

    def test_query_semplici_non_complesse(self):
        # Blocca esplicitamente una regressione verso le vecchie query
        # complesse (virgolette + OR + intitle: insieme), che il parser di
        # Google News RSS può rifiutare silenziosamente.
        for text in ("Galaxy S24 Ultra", "RMX3939", "Honor X8c"):
            for query in sources._news_attempts(text):
                self.assertNotIn(" OR ", query)
                self.assertNotIn("intitle:", query)
                self.assertNotIn('"', query)


class TestRicercaOnDemandFontiUfficiali(unittest.TestCase):
    """La ricerca di un modello deve interrogare la fonte UFFICIALE del brand
    a comando, non solo le notizie.

    È la lacuna che rendeva la ricerca inaffidabile: le fonti strutturate
    venivano interrogate solo dal giro periodico, e solo per i modelli di
    tabelle scritte a mano. Cercando un modello non ancora in archivio
    (situazione normale su Streamlit Cloud, dove il database si azzera a
    ogni riavvio del container) restavano solo le notizie — che per
    definizione non garantiscono un dato di firmware.

    Tutti i test qui girano con ZERO notizie disponibili: è il caso
    peggiore, quello in cui prima la ricerca non trovava nulla."""

    MOBILEMODELS = (
        "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
        "ABR-LX1,mob,honor,Honor,,,HONOR X8c,\n"
        "SM-S928B,mob,samsung,Samsung,,,Galaxy S24 Ultra,\n"
    )
    GOOGLE_PLAY = (
        "Retail Branding,Marketing Name,Device,Model\n"
        "HONOR,X8c,ABR-LX1,ABR-LX1\n"
    )
    HONOR_PAGE = (
        "HONOR X8c\n\n01/2027 at least（Global）\n\n"
        "Shipped version: 15  \nFuture version: 16 at least（Global）\n"
    )
    SAMSUNG_XML = '<latest o="14">S928BXXU5CYA1/S928BOXM5CYA1/S928BXXU5CYA1</latest>'

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        modelcodes.reset_cache()
        self._orig_download = modelcodes._download
        self._orig_http_get = sources.http_get
        self._orig_rss_items = sources.rss_items

        def fake_download(url, source_key):
            if url == modelcodes.MOBILEMODELS_URL:
                return self.MOBILEMODELS.encode("utf-8-sig")
            if url == modelcodes.GOOGLE_PLAY_URL:
                return self.GOOGLE_PLAY.encode("utf-16")
            return None

        class Resp:
            def __init__(self, text):
                self.status_code = 200
                self.text = text

        def fake_http_get(url, timeout=None, headers=None):
            if "honor.com" in url:
                return Resp(TestRicercaOnDemandFontiUfficiali.HONOR_PAGE)
            if "ospserver.net" in url:
                return Resp(TestRicercaOnDemandFontiUfficiali.SAMSUNG_XML)
            raise ConnectionError("URL non previsto in questo test")

        modelcodes._download = fake_download
        sources.http_get = fake_http_get
        # Nessuna notizia disponibile: il caso peggiore.
        sources.rss_items = lambda urls, brand, size_info, limit=None, timeout=None: ([], "nessun risultato")

        # Il catalogo AER NON passa da `sources.http_get`: ha un client HTTP
        # suo. Senza questa riga i test qui sotto uscivano davvero in rete —
        # l'errore n. 10 del documento di passaggio consegne — e il loro
        # esito dipendeva da cosa rispondeva Google in quel momento:
        # `test_brand_senza_fonte_dedicata_degrada_pulitamente` passava con
        # la rete e falliva senza. Ora parte da una risposta registrata.
        aer_catalog.carica_da(AER_VOCI, "fixture di test")
        # Stessa storia per l'archivio Oppo, che usa `urllib` per conto suo:
        # ogni ricerca qui apriva davvero una connessione verso
        # `sgp-sow-cms.oppo.com`. L'ha trovato `tests/test_niente_rete.py`,
        # che blocca il socket invece di fidarsi dell'elenco degli agganci.
        self._orig_oppo_post = oppo_official._post
        self._orig_oppo_catalog = oppo_official._catalog
        oppo_official._post = lambda url, payload, timeout=None: (
            (_ for _ in ()).throw(ConnectionError("URL non previsto in questo test")))
        oppo_official._catalog = {}

    def tearDown(self):
        modelcodes._download = self._orig_download
        sources.http_get = self._orig_http_get
        sources.rss_items = self._orig_rss_items
        oppo_official._post = self._orig_oppo_post
        oppo_official._catalog = self._orig_oppo_catalog
        aer_catalog.reset_cache()
        modelcodes.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_honor_per_nome_commerciale(self):
        res = scan.search_model("Honor X8c")
        self.assertEqual(res["structured_count"], 1)
        self.assertEqual(res["items"][0]["device_model"], "HONOR X8c")
        # Versione EFFETTIVA di fabbrica, non la promessa di aggiornamento.
        self.assertEqual(res["items"][0]["android_version"], 15)

    def test_honor_per_codice_tecnico(self):
        """Chi cerca 'ABR-LX1' deve ottenere il dato ufficiale di HONOR X8c:
        il codice viene risolto al nome commerciale e la fonte ufficiale
        viene interrogata con quello."""
        res = scan.search_model("ABR-LX1")
        self.assertEqual(res["structured_count"], 1)
        self.assertEqual(res["items"][0]["device_model"], "HONOR X8c")

    def test_samsung_build_reale_da_endpoint_ufficiale(self):
        res = scan.search_model("Galaxy S24 Ultra")
        self.assertEqual(res["structured_count"], 1)
        item = res["items"][0]
        self.assertEqual(item["build"], "S928BXXU5CYA1")
        self.assertEqual(item["android_version"], 14)

    def test_samsung_per_codice_modello(self):
        res = scan.search_model("SM-S928B")
        self.assertEqual(res["structured_count"], 1)
        self.assertEqual(res["items"][0]["build"], "S928BXXU5CYA1")

    def test_samsung_copertura_oltre_la_tabella_manuale(self):
        """La copertura Samsung non è più limitata ai modelli della tabella
        scritta a mano: il codice SM-xxxx arriva dall'indice inverso dei
        dataset pubblici, quindi vale per qualunque Samsung indicizzato.

        Qui si usa deliberatamente un modello ASSENTE dalla tabella manuale
        `SAMSUNG_FUS_DEVICES` per dimostrarlo."""
        modelli_in_tabella = {m for m, _ in sources.SAMSUNG_FUS_DEVICES}
        self.assertNotIn(
            "SM-S938B", modelli_in_tabella,
            "il test presuppone che questo modello NON sia nella tabella manuale",
        )

        modelcodes._download = lambda url, source_key: (
            "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
            "SM-S938B,mob,samsung,Samsung,,,Galaxy S25 Ultra,\n"
        ).encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None
        modelcodes.reset_cache()

        self.assertIn("SM-S938B", modelcodes.codes_for_name("Galaxy S25 Ultra"))
        res = scan.search_model("Galaxy S25 Ultra")
        self.assertEqual(res["structured_count"], 1)
        self.assertEqual(res["items"][0]["build"], "S928BXXU5CYA1")  # risposta simulata

    def test_modello_di_fabbrica_non_finisce_nel_catalogo_firmware(self):
        scan.search_model("Honor X8c")
        # Il piano Honor è una fonte ufficiale di identità/supporto e
        # versione iniziale, non un endpoint OTA: non deve creare la falsa
        # impressione di un firmware corrente nel catalogo dispositivi.
        self.assertEqual(storage.get_devices(search="honor x8c"), [])

    def test_brand_senza_fonte_dedicata_degrada_pulitamente(self):
        """La ricerca su una marca senza fonte DEDICATA non deve mai
        fallire: o trova qualcosa di strutturato, o spiega perché no.

        Questo test asseriva `structured_count == 0` per OnePlus. Non vale
        più, ed è una buona notizia: dal catalogo Android Enterprise
        Recommended OnePlus ha finalmente una fonte strutturata. Asserire
        ancora lo zero significherebbe difendere una lacuna appena chiusa —
        è l'errore già commesso quando tre test difendevano la «Future
        version» di Honor.
        """
        aer_catalog.carica_da(AER_VOCI, "fixture di test")

        res = scan.search_model("OnePlus 12")
        self.assertIsNone(res.get("error"))
        self.assertTrue(
            res["structured_count"] > 0 or res.get("structured_note"),
            "senza risultati strutturati va detto il motivo, non taciuto",
        )
        # SI ASSERISCE IL COMPORTAMENTO, NON QUALE FONTE VINCE.
        #
        # Questo test pretendeva prima `structured_count == 1`, poi che a
        # rispondere fosse il catalogo Android Enterprise Recommended. Sono
        # cadute entrambe, e per una buona ragione: OnePlus ha ora un
        # tracker ARB dedicato, che risponde per primo e meglio. Legare un
        # test alla fonte che vince significa doverlo riscrivere ogni volta
        # che la copertura MIGLIORA — e nel frattempo il rosso non segnala
        # un guasto, il che è il modo più rapido di smettere di leggerlo.
        #
        # Quello che deve restare vero è: il modello viene riconosciuto, e
        # nessuno si inventa una versione che la fonte non ha pubblicato.
        self.assertGreater(res["structured_count"], 0)
        nomi = {i.get("device_model") for i in res["items"]}
        self.assertIn("OnePlus 12", nomi)
        for voce in res["items"]:
            if voce.get("android_version"):
                self.assertTrue(
                    voce.get("build") or voce.get("os_version"),
                    f"«{voce.get('source_label')}» dichiara una versione senza "
                    "nessun firmware a sostegno",
                )


class TestSupportoApple(unittest.TestCase):
    """iPhone/iPad: la versione viene letta dalla lista firmware DEL SINGOLO
    dispositivo, non ricavata invertendo una lista globale di release.

    Questo è il punto centrale, non un dettaglio: la prima versione di
    questo supporto costruiva l'associazione dispositivo→versione a partire
    dall'elenco globale Apple, e in produzione ha attribuito iOS 26 a un
    iPhone 8 (che si ferma a iOS 16.7.x). Interrogando la lista del
    dispositivo quell'errore è IMPOSSIBILE per costruzione: una versione
    che il dispositivo non supporta non è nella sua lista."""

    # Risposte fedeli allo schema di /v4/device/{identificatore}
    FIRMWARE_PER_DEVICE = {
        "iPhone10,1": {  # iPhone 8: si ferma a iOS 16.x
            "name": "iPhone 8",
            "firmwares": [
                {"version": "16.7.10", "buildid": "20H350", "releasedate": "2025-11-01", "signed": True},
                {"version": "15.8.2", "buildid": "19H370", "releasedate": "2024-03-05", "signed": False},
            ],
        },
        "iPhone10,3": {  # iPhone X: idem
            "name": "iPhone X (Global)",
            "firmwares": [
                {"version": "16.7.11", "buildid": "20H360", "releasedate": "2026-01-15", "signed": True},
            ],
        },
        "iPhone16,1": {  # iPhone 15 Pro: versione moderna
            "name": "iPhone 15 Pro",
            "firmwares": [
                {"version": "26.2", "buildid": "23C100", "releasedate": "2026-07-20", "signed": True},
                {"version": "26.1.1", "buildid": "23B91", "releasedate": "2026-06-10", "signed": False},
            ],
        },
        "iPad14,3": {
            "name": "iPad Pro 11-inch (4th gen)",
            "firmwares": [
                {"version": "26.1", "buildid": "23B80", "releasedate": "2026-05-30", "signed": True},
            ],
        },
    }
    DEVICES = [
        {"identifier": "iPhone10,1", "name": "iPhone 8"},
        {"identifier": "iPhone10,3", "name": "iPhone X (Global)"},
        {"identifier": "iPhone16,1", "name": "iPhone 15 Pro"},
        {"identifier": "iPad14,3", "name": "iPad Pro 11-inch (4th gen)"},
        {"identifier": "Watch6,1", "name": "Apple Watch Series 6"},
    ]

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        appledevices.reset_cache()
        self._orig_http_get = sources.http_get
        self._orig_download = appledevices._download
        self._orig_rss = sources.rss_items
        self._orig_tracked = sources.APPLE_TRACKED_DEVICES

        class Resp:
            def __init__(self, payload, status=200):
                self.status_code = status
                self._payload = payload

            def json(self):
                return self._payload

            @property
            def text(self):
                return json.dumps(self._payload)

        def fake_http_get(url, timeout=None, headers=None):
            for identifier, payload in TestSupportoApple.FIRMWARE_PER_DEVICE.items():
                if url.endswith(f"/device/{identifier}"):
                    return Resp(payload)
            if "/device/" in url:
                return Resp({}, status=404)
            raise ConnectionError("URL non previsto in questo test")

        sources.http_get = fake_http_get
        appledevices._download = lambda: json.dumps(self.DEVICES)
        sources.rss_items = lambda urls, brand, size_info, limit=None, timeout=None: ([], "nessun risultato")
        sources.APPLE_TRACKED_DEVICES = list(self.FIRMWARE_PER_DEVICE)

    def tearDown(self):
        sources.http_get = self._orig_http_get
        appledevices._download = self._orig_download
        sources.rss_items = self._orig_rss
        sources.APPLE_TRACKED_DEVICES = self._orig_tracked
        appledevices.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    # --- il caso che ha fatto emergere il problema -----------------------
    def test_iphone_8_non_puo_avere_una_versione_moderna(self):
        """Regressione sul bug reale segnalato: l'iPhone 8 mostrava iOS 26.
        Interrogando la sua lista firmware, il massimo ottenibile è ciò che
        Apple ha davvero rilasciato per lui."""
        res = scan.search_model("iPhone 8")
        self.assertEqual(res["structured_count"], 1)
        item = res["items"][0]
        self.assertEqual(item["device_model"], "iPhone 8")
        self.assertEqual(item["os_version"], "iOS 16.7.10")
        self.assertNotIn("26", item["os_version"])

    def test_iphone_x_non_puo_avere_una_versione_moderna(self):
        res = scan.search_model("iPhone X")
        self.assertEqual(res["structured_count"], 1)
        self.assertEqual(res["items"][0]["os_version"], "iOS 16.7.11")

    def test_modello_moderno_ha_la_sua_versione_moderna(self):
        res = scan.search_model("iPhone 15 Pro")
        self.assertEqual(res["items"][0]["os_version"], "iOS 26.2")
        self.assertEqual(res["items"][0]["build"], "23C100")

    def test_ogni_dispositivo_ha_la_propria_versione(self):
        """Nessuna 'ultima versione iOS' globale: ogni modello ha la sua."""
        items, error = sources.fetch_apple()
        self.assertIsNone(error)
        per_device = {i.device: i.version for i in items}
        self.assertEqual(per_device["iPhone 8"], "iOS 16.7.10")
        self.assertEqual(per_device["iPhone X (Global)"], "iOS 16.7.11")
        self.assertEqual(per_device["iPhone 15 Pro"], "iOS 26.2")
        self.assertEqual(per_device["iPad Pro 11-inch (4th gen)"], "iPadOS 26.1")

    def test_ipad_riconosciuto_come_ipados(self):
        item, _ = sources._apple_item_for("iPad14,3")
        self.assertTrue(item.version.startswith("iPadOS"))

    def test_data_di_rilascio_reale(self):
        item, _ = sources._apple_item_for("iPhone16,1")
        self.assertTrue(item.published.startswith("2026-07-20"))

    def test_ordinamento_versioni_numerico_non_alfabetico(self):
        self.assertGreater(sources._apple_version_key("18.2"), sources._apple_version_key("9.0"))
        self.assertGreater(sources._apple_version_key("18.1.1"), sources._apple_version_key("18.1"))
        self.assertGreater(sources._apple_version_key("26.2"), sources._apple_version_key("16.7.10"))

    def test_dispositivo_sconosciuto_non_inventa_nulla(self):
        """Se il nome non è traducibile in un identificatore noto, la
        risposta deve essere vuota — non un numero plausibile inventato."""
        res = scan.search_model("iPhone Inesistente 99 Pro")
        self.assertEqual(res["structured_count"], 0)

    def test_severita_ios_dalla_struttura_della_versione(self):
        casi = [("iOS 26.0", C.SEV_MAJOR), ("iOS 26.2", C.SEV_FEATURE), ("iOS 26.1.1", C.SEV_SECURITY)]
        for versione, attesa in casi:
            testo = f"iPhone 15 Pro — {versione}"
            estratto = extract.extract_all(testo)
            severita, _, _ = classify.classify_severity(testo, estratto)
            self.assertEqual(severita, attesa, f"{versione} doveva essere {attesa}")

    def test_iphone_non_ha_versione_android(self):
        res = scan.search_model("iPhone 15 Pro")
        self.assertIsNone(res["items"][0]["android_version"])
        self.assertIn("iOS", res["items"][0]["os_version"])

    def test_ricerca_per_identificatore_interno(self):
        res = scan.search_model("iPhone16,1")
        self.assertEqual(res["items"][0]["device_model"], "iPhone 15 Pro")

    def test_esclude_dispositivi_non_mobili(self):
        appledevices.name_for("iPhone16,1")  # forza il caricamento
        self.assertIsNone(appledevices.name_for("Watch6,1"))

    def test_apple_nei_brand_supportati(self):
        self.assertIn(C.APPLE, C.BRANDS)

    def test_nomi_apple_con_maiuscole_corrette(self):
        self.assertEqual(extract.canonical_device("iphone 15 pro max"), "iPhone 15 Pro Max")
        self.assertEqual(extract.canonical_device("ipad air"), "iPad Air")
        self.assertEqual(extract.canonical_device("iphone16,1"), "iPhone16,1")


class TestControlloPlausibilita(unittest.TestCase):
    """Rete di sicurezza: quando una fonte si rompe, il rischio peggiore non
    è restare senza dati ma pubblicarne di FALSI (è già accaduto due volte:
    un iPhone 8 con iOS 26, e una versione Android letta da una promessa di
    aggiornamento futuro). Questi controlli scartano l'impossibile invece di
    mostrarlo: meglio "non lo so" di un'affermazione sbagliata."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._src = sources.Source("t", "Fonte di prova", C.TRUST_STRUCTURED, None, None, "")

    def tearDown(self):
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def _normalizza(self, titolo, device, brand, android=None):
        raw = sources.RawItem(title=titolo, device=device, brand=brand, android_version=android)
        return scan.normalize(raw, self._src)

    def test_apple_con_versione_android_scartato(self):
        item = self._normalizza("iPhone 8 — Android 15 update", "iPhone 8", C.APPLE, android=15)
        self.assertFalse(item["is_relevant"])
        self.assertIn("incoerente", item["relevance_note"])

    def test_android_con_versione_ios_scartato(self):
        item = self._normalizza("Galaxy S24 — iOS 18.2 update", "Galaxy S24", C.SAMSUNG)
        self.assertFalse(item["is_relevant"])
        self.assertIn("incoerente", item["relevance_note"])

    def test_versione_android_oltre_il_plausibile_scartata(self):
        item = self._normalizza("Galaxy S24 — Android 99 update", "Galaxy S24", C.SAMSUNG, android=99)
        self.assertFalse(item["is_relevant"])
        self.assertIn("implausibile", item["relevance_note"])

    def test_versione_ios_oltre_il_plausibile_scartata(self):
        item = self._normalizza("iPhone 15 Pro — iOS 99.1", "iPhone 15 Pro", C.APPLE)
        self.assertFalse(item["is_relevant"])
        self.assertIn("implausibile", item["relevance_note"])

    def test_dati_normali_non_vengono_scartati(self):
        """Il controllo deve colpire solo l'impossibile: un falso allarme
        nasconderebbe un dato buono, che è comunque un danno."""
        android = self._normalizza(
            "Galaxy S24 — Android 16 One UI 8.0 rolling out", "Galaxy S24", C.SAMSUNG, android=16)
        self.assertTrue(android["is_relevant"])
        apple = self._normalizza("iPhone 15 Pro — iOS 26.2", "iPhone 15 Pro", C.APPLE)
        self.assertTrue(apple["is_relevant"])

    def test_soglie_configurabili(self):
        self.assertGreaterEqual(C.MAX_PLAUSIBLE_ANDROID, 20)
        self.assertGreaterEqual(C.MAX_PLAUSIBLE_IOS, 26)


class TestRicostruzioneArchivio(unittest.TestCase):
    """Quando la logica di lettura delle fonti viene corretta, i dati che
    quella logica sbagliata aveva già prodotto devono essere rimossi.

    Senza questo, una correzione resta invisibile dove conta: è accaduto con
    iOS 26 attribuito a un iPhone 8 — la ricerca dava il valore giusto, ma la
    scheda dispositivo continuava a mostrare il vecchio dato rimasto in
    archivio, perché nessuno lo aveva cancellato."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def _riga_obsoleta(self, source="apple_gdmf"):
        storage.upsert_update({
            "id": f"vecchio_{source}", "brand": C.APPLE, "device_model": "iPhone 8",
            "device_key": "apple|iphone8", "title": "iPhone 8 — iOS 26.5",
            "os_version": "iOS 26.5", "android_version": None, "skin_name": "iOS",
            "skin_version": "26.5", "build": None, "patch_level": None,
            "severity": C.SEV_FEATURE, "color": "#FFAA00", "severity_reason": "",
            "size_info": "", "link": "", "source": source,
            "source_label": "fonte precedente", "source_trust": C.TRUST_STRUCTURED,
            "published": "2026-07-20", "is_relevant": 1, "relevance_score": 9,
            "relevance_note": "",
        })

    def test_archivio_azzerato_quando_la_logica_cambia(self):
        self._riga_obsoleta()
        storage.set_meta("data_logic_version", C.DATA_LOGIC_VERSION - 1)
        self.assertEqual(len(storage.get_devices()), 1)

        rimossi = storage.rebuild_if_logic_changed()
        self.assertGreaterEqual(rimossi, 1)
        self.assertEqual(storage.get_devices(), [])

    def test_nessuna_ricostruzione_se_la_logica_non_e_cambiata(self):
        storage.set_meta("data_logic_version", C.DATA_LOGIC_VERSION)
        self._riga_obsoleta()
        self.assertEqual(storage.rebuild_if_logic_changed(), 0)
        self.assertEqual(len(storage.get_devices()), 1)

    def test_watchlist_e_cronologia_sopravvivono(self):
        """La ricostruzione tocca solo i dati ricavabili di nuovo dalle
        fonti: quello che l'utente ha inserito a mano non si perde."""
        storage.add_to_watchlist("chiave", "Samsung", "Galaxy S24")
        self._riga_obsoleta()
        storage.set_meta("data_logic_version", C.DATA_LOGIC_VERSION - 1)
        storage.rebuild_if_logic_changed()
        self.assertEqual([w["model"] for w in storage.get_watchlist()], ["Galaxy S24"])

    def test_dati_da_fonti_ritirate_rimossi(self):
        """Una fonte sostituita non aggiorna più i suoi dati: lasciarli in
        archivio significa mostrare per sempre l'ultimo valore che aveva
        scritto."""
        self._riga_obsoleta(source="fonte_che_non_esiste_piu")
        chiavi_attive = [s.key for s in sources.all_sources()]
        rimossi = storage.purge_retired_sources(chiavi_attive)
        self.assertGreaterEqual(rimossi, 1)
        self.assertEqual(storage.get_devices(), [])

    def test_stato_delle_fonti_ritirate_rimosso(self):
        """Regressione su un caso reale: la vecchia fonte Apple sostituita
        continuava a comparire in Diagnostica con un errore TLS di 35 minuti
        prima, mentre tutte le altre riportavano «pochi istanti fa». Non era
        un guasto in corso: era una riga di stato che nessuno cancellava più.
        Un errore rosso permanente per una fonte che non viene nemmeno
        interrogata rende meno credibili gli errori veri."""
        storage.record_source_status(
            "fonte_ritirata", "Fonte ritirata", ok=False, items_found=0,
            error="errore rimasto da prima della sostituzione",
        )
        storage.record_source_status(
            "gsmarena", "Multi-brand — GSMArena", ok=True, items_found=20, error=None,
        )
        self.assertEqual(len(storage.get_source_status()), 2)

        storage.purge_retired_sources([s.key for s in sources.all_sources()])

        rimaste = {s["source"] for s in storage.get_source_status()}
        self.assertNotIn("fonte_ritirata", rimaste)
        self.assertIn("gsmarena", rimaste)

    def test_pseudo_fonti_della_ricerca_non_vengono_rimosse(self):
        """`live_search` e `official_lookup` non sono nel registro delle
        fonti periodiche ma sono legittime: i loro dati devono restare."""
        self._riga_obsoleta(source="official_lookup")
        storage.purge_retired_sources([s.key for s in sources.all_sources()])
        self.assertEqual(len(storage.get_devices()), 1)


class TestFontiRitirateDalRegistro(unittest.TestCase):
    """Una fonte che non può riuscire nell'ambiente normale non deve restare
    attiva: mostrerebbe un errore rosso permanente in Diagnostica, rendendo
    meno leggibili i guasti veri.

    Caso concreto: l'endpoint ufficiale OxygenUpdater risponde solo a chi si
    dichiara la loro applicazione. Senza un accordo con i manutentori,
    l'unico modo di farlo funzionare sarebbe impersonare la loro app —
    cosa che questo progetto non fa. Il codice resta disponibile e
    riattivabile, ma non è attivo per impostazione predefinita."""

    def tearDown(self):
        os.environ.pop("ENABLED_SOURCES", None)

    def test_fonte_inaccessibile_non_attiva_di_default(self):
        attive = {s.key for s in sources.all_sources()}
        self.assertNotIn("oppo_official", attive)

    def test_oppo_resta_comunque_coperto_da_unaltra_fonte(self):
        """Ritirare la fonte non deve lasciare il brand scoperto."""
        marchi_coperti = {s.brand for s in sources.all_sources()}
        self.assertIn(C.OPPO, marchi_coperti)

    def test_il_codice_della_fonte_ritirata_resta_disponibile(self):
        chiavi_ritirate = {s.key for s in sources.RETIRED_SOURCES}
        self.assertIn("oppo_official", chiavi_ritirate)
        self.assertTrue(callable(sources.fetch_oppo_official))

    def test_riattivabile_esplicitamente_senza_toccare_il_codice(self):
        os.environ["ENABLED_SOURCES"] = "oppo_official"
        try:
            attive = {s.key for s in sources.all_sources()}
            self.assertIn("oppo_official", attive)
        finally:
            os.environ.pop("ENABLED_SOURCES", None)


class TestRealmeUfficiale(unittest.TestCase):
    """realme dalla pagina ufficiale Android Enterprise Recommended.

    Due cose in una: la versione Android di fabbrica per modello, e la
    mappatura UFFICIALE codice→nome (RMX3939 → realme C63/Narzo 63/C61),
    di prima mano e quindi più autorevole dei dataset community."""

    # HTML GREZZO, non la resa in markdown della pagina.
    # È la forma che il codice riceve davvero da `http_get`, ed è
    # esattamente la distinzione che aveva fatto fallire questa fonte in
    # produzione: la regex era stata costruita sulla resa in markdown (con
    # le pipe fra le colonne), che il codice non vede mai. Un test scritto
    # sul formato sbagliato conferma il bug invece di scoprirlo.
    PAGINA = (
        "<html><body><table>"
        "<tr><th>Device marketing name</th><th>Security update support</th>"
        "<th>OS version update support</th></tr>"
        "<tr><td>realme 12x 5G</td><td>Security update support end date: 5/2027</td>"
        "<td>Shipped version: Android 14<br/>Future version: Android 15</td></tr>"
        "<tr><td>realme C61</td><td>Security update support end date: 5/2027</td>"
        "<td>Shipped version: Android 14<br/>Future version: Android 15</td></tr>"
        "<tr><td>realme 14 5G</td><td>Security update support end date: 5/2031</td>"
        "<td>Shipped version: Android 15<br/>Future version: Android 16</td></tr>"
        "</table>"
        "<p>For the following models, we will update the security patch version "
        "once a month:</p><p>realme C75（RMX3941）</p>"
        "<p>For the following models (including but not limited to), we will update "
        "the security patch version no later than every quarter:</p>"
        "<p>realme C63/Nazro 63/C61（RMX3939）</p>"
        "<p>realme 9i（RMX3491、RMX3492、RMX3493）</p>"
        "</body></html>"
    )

    def setUp(self):
        # La pagina realme ha una cache dalla v49 (prima era l'unica
        # delle tre pagine AER senza, e si riscaricava a ogni forma di
        # ogni ricerca). Un test che sostituisce `http_get` deve
        # azzerarla, altrimenti legge la pagina lasciata lì dal test
        # precedente invece della propria — vedi la nota in
        # `test_honor_legge_una_pagina_html`.
        # Le fonti vengono scaldate in thread di servizio. Se un test
        # precedente lascia una cache (o un worker) attivo, qui non stiamo
        # più testando questa pagina Realme ma il risultato casuale di prima.
        sources.azzera_cache_fonti()
        self.addCleanup(sources.azzera_cache_fonti)
        # Questa classe verifica il parser e la risoluzione, non il
        # riscaldamento. Un worker mantiene la propria connessione SQLite e
        # su Windows può trattenere il database temporaneo del test.
        self._orig_scalda_fonti = sources._scalda_fonti
        sources._scalda_fonti = lambda voci: None
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._orig_http_get = sources.http_get
        self._orig_rss = sources.rss_items

        class Resp:
            status_code = 200
            text = TestRealmeUfficiale.PAGINA

        sources.http_get = lambda url, timeout=None: Resp()
        sources.rss_items = lambda urls, brand, size_info, limit=None, timeout=None: ([], "nessun risultato")

    def tearDown(self):
        sources.http_get = self._orig_http_get
        sources.rss_items = self._orig_rss
        sources._scalda_fonti = self._orig_scalda_fonti
        sources.attendi_riscaldamenti()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_versione_di_fabbrica_non_promessa_futura(self):
        """Stesso tranello della pagina Honor: 'Shipped version' è ciò che
        il telefono HA, 'Future version' è una promessa. Usare la seconda ha
        già prodotto un errore reale in produzione."""
        items, error = sources.fetch_realme_aer()
        self.assertIsNone(error)
        per_device = {i.device: i.android_version for i in items}
        self.assertEqual(per_device["realme 14 5G"], 15)      # shipped, non 16
        self.assertEqual(per_device["realme C61"], 14)        # shipped, non 15

    def test_mappatura_ufficiale_codici(self):
        mappa = sources.realme_official_codes()
        self.assertIn("RMX3939", mappa)
        self.assertIn("C63", mappa["RMX3939"][0])
        # Un codice può valere per più modelli regionali insieme.
        self.assertIn("RMX3491", mappa)
        self.assertIn("RMX3493", mappa)

    def test_cadenza_patch_distinta(self):
        """La pagina distingue i modelli con patch mensile da quelli
        trimestrali: è un'informazione utile per pianificare i test."""
        mappa = sources.realme_official_codes()
        self.assertEqual(mappa["RMX3941"][1], "mensile")
        self.assertEqual(mappa["RMX3939"][1], "trimestrale")

    def test_ricerca_per_nome_commerciale(self):
        res = scan.search_model("realme 14 5G")
        self.assertEqual(res["structured_count"], 1)
        self.assertEqual(res["items"][0]["android_version"], 15)

    def test_ricerca_per_codice_ufficiale(self):
        """RMX3939 corrisponde al nome composto «realme C63/Narzo 63/C61»:
        vanno provati tutti i nomi che lo compongono, perché la tabella
        elenca i modelli singolarmente."""
        res = scan.search_model("RMX3939")
        self.assertEqual(res["structured_count"], 1)
        self.assertEqual(res["items"][0]["android_version"], 14)

    def test_codice_scritto_con_spazio(self):
        res = scan.search_model("rmx 3939")
        self.assertEqual(res["structured_count"], 1)

    def test_brand_dedotto_dal_formato_del_codice(self):
        """Un codice tecnico puro non contiene il nome della marca: senza
        dedurlo dal formato, la ricerca non saprebbe quale fonte ufficiale
        interrogare."""
        self.assertEqual(sources.brand_from_code("RMX3939"), C.OPPO)
        self.assertEqual(sources.brand_from_code("SM-S928B"), C.SAMSUNG)
        self.assertEqual(sources.brand_from_code("iPhone16,1"), C.APPLE)
        self.assertEqual(sources.brand_from_code("ABR-LX1"), C.HUAWEI)
        self.assertIsNone(sources.brand_from_code("Galaxy S24 Ultra"))


class TestFormattazioneRisultatiIMEI(unittest.TestCase):
    """Il campo descrittivo del database TAC è pensato per essere letto da
    una macchina, non da una persona: nome ripetuto, tutto in maiuscolo, e
    codice modello attaccato all'anno senza separatore. Mostrato così com'è
    produce righe illeggibili come «REALME NOTE 70 (REALME NOTE 70, Realme
    Chongqing RMX53132025)»."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        modelcodes.reset_cache()
        self._orig_download = modelcodes._download
        modelcodes._download = lambda url, key: (
            "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
            "ABR-LX1,mob,honor,Honor,,,HONOR X8c,\n"
        ).encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None

    def tearDown(self):
        modelcodes._download = self._orig_download
        modelcodes.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_codice_e_anno_concatenati_vengono_separati(self):
        """«RMX53132025» sono due campi appiccicati: RMX5313 del 2025."""
        p = imeicheck.parse_specs("REALME", "REALME NOTE 70, Realme Chongqing RMX53132025")
        self.assertEqual(p["code"], "RMX5313")
        self.assertEqual(p["year"], "2025")

    def test_nome_non_viene_ripetuto(self):
        descrizione = imeicheck.describe("REALME", "REALME NOTE 70, Realme Chongqing RMX53132025")
        self.assertEqual(descrizione.lower().count("note 70"), 1)

    def test_nome_non_resta_tutto_maiuscolo(self):
        p = imeicheck.parse_specs("REALME", "REALME NOTE 70, Realme Chongqing RMX53132025")
        self.assertNotEqual(p["model"], p["model"].upper())

    def test_formati_di_codice_dei_vari_produttori(self):
        """Una regex generica non basta: i formati sono molto diversi fra
        loro, e un pattern unico o non riconosce Samsung o spezza in due il
        suffisso di Motorola."""
        casi = [
            ("Galaxy S24 Ultra, SM-S928B, 2024", "SM-S928B"),
            ("Moto G84 5G, XT2347-1, 2023", "XT2347-1"),
            ("REDMI NOTE 13 PRO, Xiaomi Communications 2312DRA50C 2023", "2312DRA50C"),
            ("OPPO Reno12, Guangdong Oppo CPH2625 2024", "CPH2625"),
            ("HONOR X8C, ABR-LX1 2024", "ABR-LX1"),
        ]
        for specs, codice_atteso in casi:
            with self.subTest(specs=specs):
                self.assertEqual(imeicheck.parse_specs("", specs)["code"], codice_atteso)

    def test_maiuscole_corrette_dal_dataset_ufficiale(self):
        """Da una stringa tutta maiuscola la forma originale è persa:
        indovinarla sbaglia (Honor scrive «X8c», non «X8C»). Se il codice
        è noto, il nome giusto si prende dal dataset ufficiale."""
        p = imeicheck.parse_specs("HONOR", "HONOR X8C, ABR-LX1 2024")
        self.assertEqual(p["model"], "HONOR X8c")

    def test_produttore_ridondante_non_mostrato(self):
        """«Realme Chongqing» dentro una scheda già marcata realme non
        aggiunge nulla: va tolto invece di allungare la riga."""
        p = imeicheck.parse_specs("REALME", "REALME NOTE 70, Realme Chongqing RMX53132025")
        self.assertIsNone(p["maker"])

    def test_nome_senza_extra_resta_pulito(self):
        self.assertEqual(imeicheck.describe("APPLE", "iPhone 15 Pro"), "iPhone 15 Pro")


class TestTettoDiTempoRicerca(unittest.TestCase):
    """Una ricerca deve rispondere entro un tempo prevedibile.

    Ogni tentativo è una richiesta di rete, e i nomi risolti da un codice
    possono essere parecchi: senza un tetto, il caso peggiore è
    nomi × formulazioni × timeout, cioè diversi minuti. Dal punto di vista
    di chi guarda, la pagina resta in caricamento e sembra bloccata — tanto
    da indurre a ricaricarla, che è esattamente il sintomo segnalato."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._orig_rss = sources.rss_items
        self._orig_budget = C.SEARCH_BUDGET_SECONDS

    def tearDown(self):
        sources.rss_items = self._orig_rss
        C.SEARCH_BUDGET_SECONDS = self._orig_budget
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_ricerca_lenta_viene_interrotta_entro_il_tetto(self):
        C.SEARCH_BUDGET_SECONDS = 1
        chiamate = {"n": 0}

        def rss_lento(urls, brand, size_info, limit=None, timeout=None):
            chiamate["n"] += 1
            time.sleep(0.4)
            return [], "nessun risultato"

        sources.rss_items = rss_lento
        inizio = time.monotonic()
        items, error = sources.search_model_live("Modello Lento Di Prova")
        durata = time.monotonic() - inizio

        self.assertEqual(items, [])
        self.assertIn("interrotta", error)
        # Deve fermarsi vicino al tetto, non proseguire per tutte le
        # combinazioni possibili.
        self.assertLess(durata, 3.0, "la ricerca non ha rispettato il tetto di tempo")

    def test_ricerca_veloce_non_viene_interrotta(self):
        """Il tetto non deve penalizzare il caso normale."""
        C.SEARCH_BUDGET_SECONDS = 10

        def rss_veloce(urls, brand, size_info, limit=None, timeout=None):
            return [sources.RawItem(title="Modello Di Prova update", link="https://x.test",
                                     brand=brand, size_info=size_info)], None

        sources.rss_items = rss_veloce
        items, error = sources.search_model_live("Modello Di Prova")
        self.assertEqual(len(items), 1)
        self.assertIsNone(error)

    def test_numero_di_candidati_limitato(self):
        """Un codice può risolvere a molti nomi: provarli tutti moltiplica
        le richieste di rete senza aggiungere molto."""
        self.assertLessEqual(C.SEARCH_MAX_CANDIDATES, 4)

    def test_timeout_interattivo_piu_corto_di_quello_periodico(self):
        """Chi aspetta davanti allo schermo non può attendere quanto una
        scansione di sottofondo."""
        self.assertLess(C.SEARCH_HTTP_TIMEOUT, C.HTTP_TIMEOUT)


class TestSuggerimentiRicerca(unittest.TestCase):
    """Completamento, correzione degli errori di battitura e navigazione.

    Il motivo più comune di una ricerca a vuoto non è che il modello manchi,
    ma che il nome sia scritto in modo leggermente diverso: «galaxi s24»,
    «redmi note13», «hunor x8c». Senza questi aiuti l'utente conclude che
    l'app non conosce il dispositivo, quando in realtà ce l'ha."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        modelcodes.reset_cache()
        appledevices.reset_cache()
        suggest.reset_cache()
        self._orig_mc_download = modelcodes._download
        self._orig_apple_download = appledevices._download

        modelcodes._download = lambda url, key: (
            "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
            "SM-S928B,mob,samsung,Samsung,,,Galaxy S24 Ultra,\n"
            "SM-S921B,mob,samsung,Samsung,,,Galaxy S24,\n"
            "SM-S926B,mob,samsung,Samsung,,,Galaxy S24 Plus,\n"
            "2312DRA50C,mob,xiaomi,Xiaomi,,,Redmi Note 13 Pro,\n"
            "ABR-LX1,mob,honor,Honor,,,HONOR X8c,\n"
        ).encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None
        appledevices._download = lambda: json.dumps([
            {"identifier": "iPhone16,1", "name": "iPhone 15 Pro"},
            {"identifier": "iPhone16,2", "name": "iPhone 15 Pro Max"},
        ])

    def tearDown(self):
        modelcodes._download = self._orig_mc_download
        appledevices._download = self._orig_apple_download
        modelcodes.reset_cache()
        appledevices.reset_cache()
        suggest.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_completamento_ordinato_per_pertinenza(self):
        """Chi scrive «galaxy s24» deve vedere prima «Galaxy S24», non un
        modello che contiene quelle parole in mezzo ad altre."""
        proposte = suggest.suggest("galaxy s24")
        self.assertEqual(proposte[0], "Galaxy S24")
        self.assertIn("Galaxy S24 Ultra", proposte)

    def test_completamento_da_prefisso_breve(self):
        self.assertTrue(all("Galaxy" in n for n in suggest.suggest("gal")))

    def test_completamento_su_parola_interna(self):
        """«note 13» deve trovare «Redmi Note 13 Pro» anche se il nome non
        inizia con quelle parole."""
        self.assertIn("Redmi Note 13 Pro", suggest.suggest("note 13"))

    def test_correzione_errori_di_battitura(self):
        casi = [
            ("galaxi s24", "Galaxy S24"),
            ("redmi note13", "Redmi Note 13 Pro"),
            ("hunor x8c", "HONOR X8c"),
            ("iphone 15pro", "iPhone 15 Pro"),
        ]
        for sbagliato, atteso in casi:
            with self.subTest(query=sbagliato):
                self.assertIn(atteso, suggest.did_you_mean(sbagliato))

    def test_nessun_suggerimento_per_testo_senza_senso(self):
        """Una proposta sbagliata manda fuori strada più di quanto una
        proposta mancante faccia danno: meglio tacere che indovinare."""
        self.assertEqual(suggest.did_you_mean("zzzzqqqq"), [])

    def test_query_troppo_corta_non_suggerisce(self):
        self.assertEqual(suggest.suggest("g"), [])

    def test_codici_tecnici_esclusi_dai_suggerimenti(self):
        """Suggerire «SM-S928B» non aiuta a scrivere il nome: come
        completamento servono i nomi commerciali."""
        self.assertNotIn("SM-S928B", suggest.catalog())

    def test_identificatori_interni_esclusi(self):
        self.assertFalse(any("," in n for n in suggest.catalog()))

    def test_catalogo_da_fonti_multiple(self):
        catalogo = suggest.catalog()
        self.assertIn("Galaxy S24 Ultra", catalogo)   # dataset codici
        self.assertIn("iPhone 15 Pro", catalogo)      # elenco Apple

    def test_fonte_rotta_non_impedisce_i_suggerimenti(self):
        """Una fonte non caricata deve ridurre la qualità dei suggerimenti,
        non azzerarli."""
        def esplode(*args, **kwargs):
            raise RuntimeError("fonte non disponibile")

        appledevices._download = esplode
        appledevices.reset_cache()
        suggest.reset_cache()
        self.assertIn("Galaxy S24 Ultra", suggest.catalog())


class TestRealmeNomiRegionali(unittest.TestCase):
    """Un modello realme può essere venduto con nomi diversi a seconda del
    mercato, tutti sotto lo stesso codice: «realme C63/Narzo 63/C61
    （RMX3939）». La tabella con le versioni ne riporta però uno solo.

    Chi cerca «C63» — o «c 63», o senza indicare la marca — deve arrivare
    comunque al dato, che è pubblicato sotto «C61»: è lo stesso telefono.
    Prima di questa correzione nessuna di quelle forme trovava nulla."""

    # HTML grezzo: vedi la nota in TestRealmeUfficiale.
    PAGINA = (
        "<html><body><table>"
        "<tr><td>realme C61</td><td>Security update support end date: 5/2027</td>"
        "<td>Shipped version: Android 14<br/>Future version: Android 15</td></tr>"
        "<tr><td>realme 14 5G</td><td>Security update support end date: 5/2031</td>"
        "<td>Shipped version: Android 15<br/>Future version: Android 16</td></tr>"
        "</table>"
        "<p>For the following models (including but not limited to), we will update "
        "the security patch version no later than every quarter:</p>"
        "<p>realme C63/Nazro 63/C61（RMX3939）</p>"
        "</body></html>"
    )

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._orig_http_get = sources.http_get

        class Resp:
            status_code = 200
            text = TestRealmeNomiRegionali.PAGINA

        sources.http_get = lambda url, timeout=None: Resp()

    def tearDown(self):
        sources.http_get = self._orig_http_get
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_tutte_le_forme_di_scrittura_trovano_il_modello(self):
        """Le quattro forme segnalate come non funzionanti."""
        for query in ["c63", "C63", "c 63", "realme c 63", "realme C63", "RMX3939"]:
            with self.subTest(query=query):
                trovati, nota = sources.lookup_model_structured(query)
                self.assertTrue(trovati, f"«{query}» non ha trovato nulla: {nota}")
                self.assertEqual(trovati[0].android_version, 14)

    def test_spazio_fra_sigla_e_cifre_ignorato(self):
        """«C 63» e «C63» sono lo stesso modello."""
        self.assertEqual(
            modelcodes._normalize_name("realme C 63"),
            modelcodes._normalize_name("realme C63"),
        )

    def test_parola_intera_non_viene_unita_alle_cifre(self):
        """L'unione vale solo per sigle brevi: «Note 13» non deve diventare
        «Note13», che non corrisponderebbe più a nulla."""
        self.assertIn("note 13", modelcodes._normalize_name("Redmi Note 13"))
        self.assertNotIn("note13", modelcodes._normalize_name("Redmi Note 13"))

    def test_nome_composto_scomposto_in_varianti(self):
        varianti = sources.realme_name_variants()
        self.assertIn("c63", varianti)
        self.assertIn("c61", varianti)
        fratelli, codice = varianti["c63"]
        self.assertEqual(codice, "RMX3939")
        self.assertIn("realme C61", fratelli)

    def test_brand_dedotto_da_nome_noto_senza_marca(self):
        """«c63» non contiene la marca e non ha il formato di un codice:
        va riconosciuto perché compare in un catalogo ufficiale."""
        self.assertEqual(sources.brand_from_known_device("c63"), C.OPPO)
        self.assertIsNone(sources.brand_from_known_device("xyz999"))

    def test_differenza_di_nome_dichiarata_non_nascosta(self):
        """Se il dato è pubblicato sotto un altro nome regionale va detto:
        nasconderlo farebbe sembrare che la fonte parli esattamente del
        modello cercato."""
        trovati, _ = sources.lookup_model_structured("c63")
        self.assertIn("realme C61", trovati[0].title)
        self.assertIn("stesso dispositivo", trovati[0].title)

    def test_nome_esatto_non_riceve_etichetta_superflua(self):
        trovati, _ = sources.lookup_model_structured("realme C61")
        self.assertNotIn("stesso dispositivo", trovati[0].title)


class TestRealmeNomeCondivisoDaDueCodici(unittest.TestCase):
    """Bug reale, segnalato dall'utente con uno screenshot dal sito vero:
    cercando `RMX3939` (gruppo ufficiale «realme C63/Narzo 63/C61») la
    pagina mostrava i dati di un ALTRO telefono realme, pubblicato sotto
    lo stesso nome «realme C61» ma con un codice a sé.

    Verificato leggendo la pagina ufficiale realme vera (non solo
    simulato): la sigla «C61» compare due volte, in due punti distinti —
    una riga a sé nella tabella Android Enterprise Recommended e, separata,
    dentro il gruppo composto di RMX3939 nell'elenco trimestrale. Questa
    classe riproduce ESATTAMENTE quella struttura a due voci, che
    `TestRealmeNomiRegionali` sopra (una sola voce «C61», nessun conflitto)
    non copriva."""

    PAGINA = (
        "<html><body><table>"
        "<tr><th>Device marketing name</th><th>Security update support</th>"
        "<th>OS version update support</th></tr>"
        "<tr><td>realme C61</td><td>Security update support end date: 5/2027</td>"
        "<td>Shipped version: Android 14<br/>Future version: Android 15</td></tr>"
        "</table>"
        "<p>For the following models (including but not limited to), we will update "
        "the security patch version no later than every quarter:</p>"
        # La voce A SÉ STANTE (un ALTRO codice, RMX3930) che dà alla riga
        # tabellare qui sopra il suo codice vero, tramite `codici_per_nome`.
        "<p>realme C61（RMX3930）</p>"
        # Il gruppo composto di RMX3939, che condivide il pezzo «C61» con
        # la voce a sé stante qui sopra — il conflitto vero.
        "<p>realme C63/Narzo 63/C61（RMX3939）</p>"
        "</body></html>"
    )

    def setUp(self):
        # La pagina realme ha una cache dalla v49 (prima era l'unica
        # delle tre pagine AER senza, e si riscaricava a ogni forma di
        # ogni ricerca). Un test che sostituisce `http_get` deve
        # azzerarla, altrimenti legge la pagina lasciata lì dal test
        # precedente invece della propria — vedi la nota in
        # `test_honor_legge_una_pagina_html`.
        sources.reset_realme_aer_cache()
        self.addCleanup(sources.reset_realme_aer_cache)
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._orig_http_get = sources.http_get

        class Resp:
            status_code = 200
            text = TestRealmeNomeCondivisoDaDueCodici.PAGINA

        sources.http_get = lambda url, timeout=None: Resp()

    def tearDown(self):
        sources.http_get = self._orig_http_get
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_il_gruppo_composto_non_prende_i_dati_dell_altro_codice(self):
        """Il caso esatto dello screenshot: cercare RMX3939 non deve più
        restituire la riga di RMX3930, solo perché condividono un pezzo
        di nome («C61»). Onesto «niente trovato» batte un dato vero ma
        del telefono sbagliato."""
        trovati, nota = sources.lookup_model_structured("RMX3939")
        self.assertFalse(
            any("RMX3930" in (i.title or "") for i in trovati),
            "non deve restituire il firmware di RMX3930 per una ricerca su RMX3939")

    def test_la_voce_a_se_stante_trova_ancora_i_propri_dati(self):
        """RMX3930 possiede DAVVERO quella riga (`codici_per_nome` la
        etichetta col suo codice tramite un confronto esatto sul gruppo):
        il filtro sull'ambiguità del nome non deve privare anche lui del
        proprio dato, solo perché un altro codice ne condivide un pezzo."""
        trovati, nota = sources.lookup_model_structured("RMX3930")
        self.assertTrue(trovati, f"RMX3930 non ha trovato nulla: {nota}")
        self.assertEqual(trovati[0].android_version, 14)

    def test_il_nome_condiviso_e_fuori_dai_candidati(self):
        self.assertIn("c61", sources._realme_nomi_ambigui())

    def test_i_nomi_non_condivisi_restano_candidati_validi(self):
        """Solo «C61» è conteso: «C63» e «Narzo 63», scomposti dallo
        stesso gruppo di RMX3939, non lo sono e restano utilizzabili."""
        ambigui = sources._realme_nomi_ambigui()
        self.assertNotIn("c63", ambigui)
        self.assertNotIn("narzo 63", ambigui)


class TestOrdinamentoPerDataDiUscita(unittest.TestCase):
    """Il feed deve essere ordinato per data di USCITA reale, non per
    quando la scansione ha visto la notizia.

    Prima si ordinava per COALESCE(published, first_seen): un aggiornamento
    uscito mesi fa ma rilevato oggi finiva in cima, davanti a uno uscito
    ieri — l'esatto opposto di quello che serve per capire cosa è cambiato
    di recente."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def _aggiungi(self, id_, modello, published, first_seen):
        storage.upsert_update({
            "id": id_, "brand": C.SAMSUNG, "device_model": modello,
            "device_key": f"k|{id_}", "title": f"{modello} update",
            "os_version": "Android 15", "android_version": 15, "skin_name": None,
            "skin_version": None, "build": None, "patch_level": None,
            "severity": C.SEV_FEATURE, "color": "#FFAA00", "severity_reason": "",
            "size_info": "", "link": "", "source": "t", "source_label": "prova",
            "source_trust": C.TRUST_CURATED, "published": published,
            "is_relevant": 1, "relevance_score": 9, "relevance_note": "",
        })
        conn = storage.connect()
        conn.execute("UPDATE updates SET first_seen=? WHERE id=?", (first_seen, id_))
        conn.commit()

    def test_uscita_recente_prima_di_rilevazione_recente(self):
        # Uscito a gennaio ma rilevato oggi: NON deve stare in cima.
        self._aggiungi("vecchio", "Uscito a gennaio", "2026-01-10", "2026-07-31")
        # Uscito ieri: deve stare in cima.
        self._aggiungi("recente", "Uscito ieri", "2026-07-30", "2026-07-30")

        ordinati = [u["device_model"] for u in storage.get_updates(limit=10)]
        self.assertEqual(ordinati[0], "Uscito ieri")
        self.assertEqual(ordinati[1], "Uscito a gennaio")

    def test_voci_senza_data_di_uscita_vanno_in_coda(self):
        """I controlli di stato ufficiali non pubblicano una data per
        release: senza data vera non possono precedere un rilascio datato,
        o sembrerebbero i più recenti solo perché scansionati per ultimi."""
        self._aggiungi("con_data", "Con data", "2026-01-10", "2026-07-31")
        self._aggiungi("senza_data", "Senza data", None, "2026-07-31")

        ordinati = [u["device_model"] for u in storage.get_updates(limit=10)]
        self.assertEqual(ordinati[0], "Con data")
        self.assertEqual(ordinati[-1], "Senza data")

    def test_storico_dispositivo_stesso_criterio(self):
        self._aggiungi("a", "Modello", "2026-01-10", "2026-07-31")
        conn = storage.connect()
        conn.execute("UPDATE updates SET device_key='stesso' WHERE id='a'")
        conn.commit()
        self._aggiungi("b", "Modello", "2026-07-30", "2026-07-30")
        conn = storage.connect()
        conn.execute("UPDATE updates SET device_key='stesso' WHERE id='b'")
        conn.commit()

        storico = storage.get_device_history("stesso")
        self.assertEqual(storico[0]["published"][:10], "2026-07-30")


class TestFontiHtmlLavoranoSuHtml(unittest.TestCase):
    """Le fonti che leggono una pagina web vanno provate sull'HTML GREZZO.

    Errore reale già commesso: la regex della fonte realme era stata
    costruita e provata sulla resa in *markdown* della pagina — quella che
    si ottiene con uno strumento di lettura web, con le pipe «|» a separare
    le colonne. Il codice però riceve HTML, e `_realme_page` sostituisce i
    tag con degli a capo: le pipe non esistono mai. Risultato in
    produzione: pagina scaricata correttamente, zero righe riconosciute,
    fonte in errore permanente.

    Un test scritto sul formato sbagliato non avrebbe scoperto nulla:
    avrebbe confermato il bug. Questi controlli fissano il formato giusto."""

    def _con_html(self, html: str):
        class Resp:
            status_code = 200
            text = html
        originale = sources.http_get
        sources.http_get = lambda url, timeout=None: Resp()
        return originale

    def test_realme_legge_una_tabella_html(self):
        # Dalla v49 anche la pagina realme ha una cache (prima era l'unica
        # delle tre pagine AER senza, e si riscaricava a ogni forma di ogni
        # ricerca). Va azzerata qui per lo stesso motivo di Honor: una
        # cache calda farebbe passare o fallire questo test a seconda di
        # quali test hanno girato prima.
        sources.reset_realme_aer_cache()
        self.addCleanup(sources.reset_realme_aer_cache)
        originale = self._con_html(
            "<table><tr><td>realme 14 5G</td>"
            "<td>Security update support end date: 5/2031</td>"
            "<td>Shipped version: Android 15<br/>Future version: Android 16</td></tr></table>"
        )
        try:
            items, error = sources.fetch_realme_aer()
        finally:
            sources.http_get = originale
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].android_version, 15)

    def test_honor_legge_una_pagina_html(self):
        """LA CACHE VA AZZERATA, ALTRIMENTI QUESTO TEST NON PROVA NIENTE.

        `fetch_honor_aer` tiene la pagina in `_honor_aer_cache` per un'ora.
        Se un test precedente dello stesso modulo l'ha già riempita con la
        pagina VERA, la chiamata qui sotto non guarda nemmeno l'HTML
        preparato: torna la cache, e l'asserzione finisce per descrivere il
        primo modello della pagina di oggi invece del modello del test.
        Falliva così — `14 != 15`, cioè HONOR 200 al posto dell'X8c — solo
        quando girava insieme agli altri, il che lo faceva sembrare un
        difetto a intermittenza invece di un test che non collauda.
        """
        sources.reset_honor_aer_cache()
        originale = self._con_html(
            "<div><p>HONOR X8c</p><p>01/2027 at least（Global）</p>"
            "<p>Shipped version: 15</p><p>Future version: 16 at least（Global）</p></div>"
        )
        try:
            items, error = sources.fetch_honor_aer()
        finally:
            sources.http_get = originale
            sources.reset_honor_aer_cache()
        self.assertIsNone(error)
        self.assertEqual(items[0].device, "HONOR X8c")
        self.assertEqual(items[0].android_version, 15)

    def test_pagina_senza_dati_segnala_errore_esplicito(self):
        """Se il formato cambia davvero, la fonte deve dirlo con chiarezza
        invece di restituire in silenzio una lista vuota."""
        sources.reset_realme_aer_cache()
        self.addCleanup(sources.reset_realme_aer_cache)
        originale = self._con_html("<html><body><p>pagina riorganizzata</p></body></html>")
        try:
            items, error = sources.fetch_realme_aer()
        finally:
            sources.http_get = originale
        self.assertEqual(items, [])
        self.assertIn("formato cambiato", error)


class TestNomeBreveNonScambiatoPerCodice(unittest.TestCase):
    """Una sigla corta come «C61» è un nome commerciale, non un codice.

    Errore reale: cercando «c 61» il testo veniva risolto contro il
    database dei codici, dove «C61» corrisponde per caso a dispositivi di
    marche del tutto diverse (Chainway C61, Oukitel C61_A15_EEA). La
    ricerca partiva quindi su telefoni che non c'entravano nulla,
    consumando il tempo disponibile e restituendo un errore incomprensibile.

    Con 70.000 codici indicizzati, risolvere una sigla generica trova
    sempre qualcosa — quasi mai la cosa giusta."""

    def test_sigle_brevi_non_sono_codici(self):
        for testo in ["c 61", "C61", "c63", "A54", "S24", "X8"]:
            with self.subTest(testo=testo):
                self.assertFalse(
                    sources.looks_like_model_code(testo),
                    f"«{testo}» non deve essere trattato come codice modello",
                )

    def test_codici_veri_riconosciuti(self):
        """Include i formati che il primo controllo aveva mancato: lo stile
        Xiaomi a sole cifre e il suffisso di variante Motorola. Restringere
        troppo è pericoloso quanto allargare troppo — un codice vero non
        riconosciuto perde la risoluzione al nome commerciale."""
        for testo in ["RMX3939", "rmx 3939", "SM-S928B", "ABR-LX1",
                      "iPhone16,1", "2312DRA50C", "CPH2625", "XT2347",
                      "22101316UG", "XT2323-1"]:
            with self.subTest(testo=testo):
                self.assertTrue(
                    sources.looks_like_model_code(testo),
                    f"«{testo}» è un codice modello e deve essere riconosciuto",
                )

    def test_nomi_commerciali_non_sono_codici(self):
        for testo in ["Galaxy S24 Ultra", "iPhone 15 Pro", "realme C63",
                      "Redmi Note 13 Pro"]:
            with self.subTest(testo=testo):
                self.assertFalse(sources.looks_like_model_code(testo))

    def test_sigla_breve_non_genera_candidati_codice(self):
        """Se non ha la forma di un codice, non deve nemmeno essere provata
        contro il database: è lì che nascevano le corrispondenze sbagliate."""
        self.assertEqual(sources._code_candidates("c 61"), [])
        self.assertIn("RMX3939", sources._code_candidates("rmx 3939"))


class TestDiagnosticaFonteDistinta(unittest.TestCase):
    """«La fonte non risponde» e «il modello non è in quella fonte» sono
    due situazioni diverse: la prima si risolve guardando la Diagnostica,
    la seconda no. Dirle allo stesso modo manda a cercare il problema nel
    posto sbagliato."""

    def setUp(self):
        # La pagina realme ha una cache dalla v49 (prima era l'unica
        # delle tre pagine AER senza, e si riscaricava a ogni forma di
        # ogni ricerca). Un test che sostituisce `http_get` deve
        # azzerarla, altrimenti legge la pagina lasciata lì dal test
        # precedente invece della propria — vedi la nota in
        # `test_honor_legge_una_pagina_html`.
        sources.reset_realme_aer_cache()
        self.addCleanup(sources.reset_realme_aer_cache)
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._orig_http = sources.http_get

    def tearDown(self):
        sources.http_get = self._orig_http
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_fonte_in_errore_lo_dichiara(self):
        storage.record_source_status(
            "realme_aer", "realme — piano ufficiale", ok=False, items_found=0,
            error="pagina raggiungibile ma nessuna riga riconosciuta",
        )

        class Resp:
            def __init__(self, status=200, text=""):
                self.status_code = status
                self.text = text

            def json(self):
                raise ValueError("non JSON")

        def finto(url, timeout=None, headers=None):
            # La ricerca ora prova anche le altre fonti economiche: quelle
            # non pertinenti devono rispondere in modo pulito, non rompersi.
            if "realme.com" in url:
                return Resp(200, "<html><body>pagina cambiata</body></html>")
            return Resp(404, "")

        sources.http_get = finto
        _, nota = sources.lookup_model_structured("realme C61")
        self.assertIn("non sta rispondendo", nota)

    def test_fonte_sana_ma_modello_assente(self):
        storage.record_source_status(
            "realme_aer", "realme — piano ufficiale", ok=True, items_found=3, error=None,
        )

        class Resp:
            def __init__(self, status=200, text=""):
                self.status_code = status
                self.text = text

            def json(self):
                raise ValueError("non JSON")

        def finto(url, timeout=None, headers=None):
            if "realme.com" in url:
                return Resp(200, (
                    "<table><tr><td>realme 14 5G</td>"
                    "<td>Security update support end date: 5/2031</td>"
                    "<td>Shipped version: Android 15<br/>Future version: Android 16</td>"
                    "</tr></table>"))
            return Resp(404, "")

        sources.http_get = finto
        _, nota = sources.lookup_model_structured("realme Inesistente 99")
        self.assertIn("nessuna fonte ufficiale conosce", nota)
        self.assertNotIn("non sta rispondendo", nota)


class TestMatriceRicerca(unittest.TestCase):
    """Ogni marca contro ogni forma di scrittura, in un colpo solo.

    PERCHÉ ESISTE QUESTA CLASSE. Per settimane le correzioni sono andate a
    caso singolo: si sistemava «C63», poi si rompeva «CPH2819»; si sistemava
    quello, e tornava a non funzionare qualcos'altro. La causa non era una
    fonte sbagliata ma l'assenza di un controllo d'insieme: nessun test
    provava le stesse marche con tutte le forme in cui una persona scrive
    davvero un modello.

    Questa matrice lo fa. Aggiungere una riga qui è il modo giusto di
    rispondere a una segnalazione: la correzione resta protetta, e una
    regressione su un'altra combinazione emerge subito."""

    # Forme di scrittura che una persona usa davvero, per ciascun modello:
    # nome commerciale, minuscolo, con e senza marca, e codice tecnico.
    MATRICE = [
        # (forme equivalenti, dispositivo atteso)
        (["Galaxy S24 Ultra", "galaxy s24 ultra", "SM-S928B"], "Galaxy S24 Ultra"),
        (["realme C61", "realme c 61", "c61", "C61"], "realme C61"),
        (["realme C63", "c63", "RMX3939", "rmx 3939"], "realme C61"),  # nome regionale gemello
        (["HONOR X8c", "honor x8c", "ABR-LX1"], "HONOR X8c"),
        (["iPhone 15 Pro", "iphone 15 pro", "iPhone16,1"], "iPhone 15 Pro"),
        # Oppo: il caso che aveva rivelato il difetto d'impianto — il
        # contenitore «Oppo / Realme / OnePlus» mandava ogni ricerca alla
        # sola pagina realme, condannando tutti gli Oppo.
        (["OPPO A6x", "oppo a6x", "CPH2819", "cph 2819"], "OPPO A6x"),
        # Oppo coperto dall'archivio firmware ufficiale: qui la risposta è
        # la versione DAVVERO rilasciata, non quella di fabbrica.
        (["OPPO Find X2", "find x2", "Find X2"], "OPPO Find X2"),
        # vivo: la tabella ufficiale scrive «X300 Ultra» senza marca, quindi
        # entrambe le forme devono arrivare allo stesso dispositivo.
        (["vivo X300 Ultra", "X300 Ultra", "x300 ultra"], "vivo X300 Ultra"),
    ]

    HONOR_HTML = (
        "<p>HONOR X8c</p><p>01/2027 at least（Global）</p>"
        "<p>Shipped version: 15</p><p>Future version: 16 at least（Global）</p>"
    )
    REALME_HTML = (
        "<table><tr><td>realme C61</td>"
        "<td>Security update support end date: 5/2027</td>"
        "<td>Shipped version: Android 14<br/>Future version: Android 15</td></tr></table>"
        "<p>quarter:</p><p>realme C63/Nazro 63/C61（RMX3939）</p>"
    )
    SAMSUNG_XML = '<latest o="15">S928BXXU5CYA1/S928BOXM5CYA1/S928BXXU5CYA1</latest>'
    OPPO_HTML = "<div><p>OPPO A6x</p><a href='/a6x/'>Learn more</a></div>"
    # Struttura reale della tabella vivo, `&nbsp;` compresi: è la forma su
    # cui il parser deve funzionare, non una ripulita.
    VIVO_HTML = (
        '<table><tr class="table-content">'
        '<td>&nbsp;&nbsp;X300 Ultra</td>'
        '<td>&nbsp;&nbsp;End date: 07/2031 at least(Global)</br>'
        '&nbsp;&nbsp;Frequency: Every 30 days</td>'
        '<td>&nbsp;&nbsp;Shipped version: Android 16</br>'
        '&nbsp;&nbsp;Future version: Andorid 17&18&19 at least(Globa)</td>'
        '</tr></table>'
    )
    APPLE_FW = {
        "name": "iPhone 15 Pro",
        "firmwares": [{"version": "26.2", "buildid": "23C100",
                       "releasedate": "2026-07-20", "signed": True}],
    }

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        modelcodes.reset_cache()
        appledevices.reset_cache()
        sources.azzera_cache_fonti()
        self._orig = (sources.http_get, sources.rss_items,
                      modelcodes._download, appledevices._download)
        # Stessa ragione della classe Realme sopra: qui servono risultati
        # riproducibili delle fonti finte, non download concorrenti che
        # possano trattenere il database di fixture su Windows.
        self._orig_scalda_fonti = sources._scalda_fonti
        sources._scalda_fonti = lambda voci: None
        # L'archivio firmware Oppo parla con urllib, non con
        # `sources.http_get`: senza questo stub la matrice andrebbe in rete
        # davvero, e un test che dipende dalla rete fallisce a caso.
        self._orig_oppo_post = oppo_official._post
        oppo_official.reset_cache()
        oppo_official._catalog = {
            oppo_official.normalize("Find X2"): (oppo_official.HOST_APAC, "in", "Find X2"),
        }
        oppo_official._post = lambda url, payload, timeout=None: {
            "code": "1", "msg": "SUCCESS!", "data": [{
                "prefix": "OPPO", "machineModel": "Find X2",
                "softwareVersion": "CPH2023_11_A.42", "fileSize": "3644",
                "releaseDate": "2020-12-19 02:28:23",
                "versionPath": "https://assorted.downloads.oppo.com/firmware/x.ozip",
                "content": "<p>[Security]</p><p>Added the September 2020 "
                           "Android security patch to enhance system security.</p>",
            }],
        }

        modelcodes._download = lambda url, key: (
            "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
            "SM-S928B,mob,samsung,Samsung,,,Galaxy S24 Ultra,\n"
            "ABR-LX1,mob,honor,Honor,,,HONOR X8c,\n"
            "CPH2819,mob,oppo,OPPO,,,OPPO A6x,\n"
        ).encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None
        appledevices._download = lambda: json.dumps(
            [{"identifier": "iPhone16,1", "name": "iPhone 15 Pro"}])

        class Resp:
            def __init__(self, status=200, text="", payload=None):
                self.status_code = status
                self.text = text
                self._payload = payload

            def json(self):
                if self._payload is None:
                    raise ValueError("non JSON")
                return self._payload

        def finto_http(url, timeout=None, headers=None):
            if "honor.com" in url:
                return Resp(200, TestMatriceRicerca.HONOR_HTML)
            if "realme.com" in url:
                return Resp(200, TestMatriceRicerca.REALME_HTML)
            if "oppo.com" in url:
                return Resp(200, TestMatriceRicerca.OPPO_HTML)
            if "vivo.com" in url:
                return Resp(200, TestMatriceRicerca.VIVO_HTML)
            if "ospserver.net" in url:
                return Resp(200, TestMatriceRicerca.SAMSUNG_XML)
            if "/device/iPhone16,1" in url:
                return Resp(200, payload=TestMatriceRicerca.APPLE_FW)
            return Resp(404, "")

        sources.http_get = finto_http
        # Nessuna notizia disponibile: si verifica che le fonti UFFICIALI
        # bastino da sole, che è la condizione più severa.
        sources.rss_items = lambda urls, brand, size_info, limit=None, timeout=None: (
            [], "nessun risultato")

    def tearDown(self):
        (sources.http_get, sources.rss_items,
         modelcodes._download, appledevices._download) = self._orig
        sources._scalda_fonti = self._orig_scalda_fonti
        oppo_official._post = self._orig_oppo_post
        oppo_official.reset_cache()
        modelcodes.reset_cache()
        appledevices.reset_cache()
        sources.azzera_cache_fonti()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_ogni_forma_trova_lo_stesso_dispositivo(self):
        for forme, atteso in self.MATRICE:
            for forma in forme:
                with self.subTest(forma=forma, atteso=atteso):
                    trovati, nota = sources.lookup_model_structured(forma)
                    self.assertTrue(
                        trovati,
                        f"«{forma}» doveva trovare «{atteso}» ma non ha trovato nulla: {nota}",
                    )
                    self.assertEqual(trovati[0].device, atteso)

    def test_modello_del_tutto_sconosciuto_lo_dichiara(self):
        """Un modello che nessuna fonte conosce deve produrre un messaggio
        comprensibile, non un silenzio."""
        trovati, nota = sources.lookup_model_structured("Marca Inesistente 999")
        self.assertEqual(trovati, [])
        self.assertIn("nessuna fonte ufficiale conosce", nota)

    def test_una_fonte_rotta_non_impedisce_le_altre(self):
        """Il difetto d'impianto corretto qui: prima si sceglieva UNA fonte
        in base a una supposizione sul brand e il suo esito era definitivo.
        Ora, se quella tace, le altre vengono comunque provate."""
        originale = sources.http_get

        def honor_rotto(url, timeout=None, headers=None):
            if "honor.com" in url:
                raise ConnectionError("fonte Honor irraggiungibile")
            return originale(url, timeout)

        sources.http_get = honor_rotto
        # realme resta raggiungibile e deve essere trovato lo stesso
        trovati, _ = sources.lookup_model_structured("realme C61")
        self.assertTrue(trovati)

    def test_fonti_costose_non_interrogate_per_altri_brand(self):
        """Le fonti che costano una richiesta per dispositivo (Samsung,
        Apple, Motorola) non devono essere interrogate quando il brand non
        corrisponde: pagherebbero decine di richieste a ogni ricerca."""
        etichette = [v.etichetta for v in sources._lookup_order(C.OPPO)]
        self.assertNotIn("controllo versione Samsung", etichette)
        self.assertNotIn("firmware Apple per dispositivo", etichette)
        self.assertIn("piano ufficiale realme", etichette)

    def test_fonte_del_brand_provata_per_prima(self):
        ordine = [v.brand for v in sources._lookup_order(C.HUAWEI)]
        self.assertEqual(ordine[0], C.HUAWEI)


class TestEstrazioneOppoRobusta(unittest.TestCase):
    """L'estrazione dei nomi dalla pagina Oppo deve reggere l'HTML vero.

    Errore già commesso (due volte, con fonti diverse): costruire il
    riconoscimento su un HTML scritto a mano e non su quello reale. La
    prima versione pretendeva che il nome iniziasse esattamente a inizio
    riga — bastava uno spazio di indentazione perché non riconoscesse più
    niente, e l'app dichiarava «formato cambiato» su una pagina intatta."""

    def _con_html(self, html):
        # `fetch_oppo_aer` ora tiene la pagina in cache per un'ora (vedi
        # `_CacheDiFonte` in sources.py): senza azzerarla qui, il secondo
        # test di questa classe in poi riceverebbe la risposta mockata dal
        # test precedente invece di quella appena preparata.
        sources.reset_oppo_aer_cache()
        class Resp:
            status_code = 200
            text = html
        originale = sources.http_get
        sources.http_get = lambda url, timeout=None: Resp()
        return originale

    def tearDown(self):
        sources.reset_oppo_aer_cache()

    def test_nome_indentato_riconosciuto(self):
        originale = self._con_html(
            "<div>\n      <p>\n        OPPO A6x\n      </p>\n</div>")
        try:
            items, error = sources.fetch_oppo_aer()
        finally:
            sources.http_get = originale
        self.assertIsNone(error)
        self.assertIn("OPPO A6x", [i.device for i in items])

    def test_nome_duplicato_del_menu_normalizzato(self):
        """Le voci di menu ripetono il nome due volte (testo + alternativa
        dell'immagine): va tenuta una copia sola."""
        originale = self._con_html("<li><a href='/x'>OPPO A6x OPPO A6x</a></li>")
        try:
            items, _ = sources.fetch_oppo_aer()
        finally:
            sources.http_get = originale
        self.assertIn("OPPO A6x", [i.device for i in items])

    def test_slug_url_come_seconda_via(self):
        """Se l'impaginazione cambia, gli indirizzi delle schede prodotto
        restano: sono una via di riconoscimento indipendente."""
        originale = self._con_html(
            "<a href='/en/smartphones/series-a/a6x-5g/'>&nbsp;</a>")
        try:
            items, _ = sources.fetch_oppo_aer()
        finally:
            sources.http_get = originale
        self.assertIn("OPPO A6x 5G", [i.device for i in items])

    def test_orologi_e_auricolari_esclusi(self):
        originale = self._con_html(
            "<p>OPPO Watch X3</p><p>OPPO Enco Air5 Pro</p><p>OPPO A6x</p>")
        try:
            items, _ = sources.fetch_oppo_aer()
        finally:
            sources.http_get = originale
        nomi = [i.device for i in items]
        self.assertIn("OPPO A6x", nomi)
        self.assertFalse(any("Watch" in n or "Enco" in n for n in nomi))

    def test_nessuna_versione_inventata(self):
        """La pagina non pubblica la versione per dispositivo: il campo deve
        restare vuoto, non essere dedotto (errore già fatto con Honor)."""
        originale = self._con_html("<p>OPPO A6x</p>")
        try:
            items, _ = sources.fetch_oppo_aer()
        finally:
            sources.http_get = originale
        self.assertIsNone(items[0].android_version)


class TestDiagnosiRicerca(unittest.TestCase):
    """Lo strumento che spiega perché una ricerca non trova nulla.

    Nasce da un problema di metodo: ogni volta che una ricerca falliva si
    procedeva per ipotesi, e ogni ipotesi sbagliata costava un giro di
    correzioni a vuoto. Questo sostituisce l'ipotesi con un fatto."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        modelcodes.reset_cache()
        self._orig = (sources.http_get, modelcodes._download)
        modelcodes._download = lambda url, key: (
            "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
            "CPH2819,mob,oppo,OPPO,,,OPPO A6x,\n"
        ).encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None

        class Resp:
            def __init__(self, status=200, text=""):
                self.status_code = status
                self.text = text

            def json(self):
                raise ValueError("non JSON")

        sources.http_get = lambda url, timeout=None: (
            Resp(200, "<p>OPPO A6x</p>") if "oppo.com" in url else Resp(404, ""))

    def tearDown(self):
        sources.http_get, modelcodes._download = self._orig
        modelcodes.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_racconta_i_passaggi_di_una_ricerca_riuscita(self):
        passi = sources.diagnose_query("CPH2819")
        self.assertTrue(passi["ha_forma_di_codice"])
        self.assertEqual(passi["brand_dedotto"], C.OPPO)
        self.assertIn("OPPO A6x", passi["forme_provate"])
        self.assertIn("trovato", passi["esito"])

    def test_indica_quale_fonte_ha_risposto(self):
        passi = sources.diagnose_query("CPH2819")
        vincente = [f for f in passi["fonti"] if f["trovati"]]
        self.assertTrue(vincente)
        self.assertEqual(vincente[0]["dispositivo"], "OPPO A6x")

    def test_segnala_codice_non_presente_nei_dataset(self):
        """Il caso più probabile quando un codice non porta a nulla: va
        detto esplicitamente, invece di lasciarlo dedurre."""
        passi = sources.diagnose_query("XYZ9999")
        self.assertEqual(passi["nomi_risolti"], [])
        self.assertIn("nessuna fonte", passi["esito"])

    def test_riporta_gli_errori_delle_fonti(self):
        # Le cache vanno azzerate, o le fonti che ne hanno una rispondono
        # con quello che ha scaricato un test precedente e la diagnosi non
        # vede nessun errore da riportare: vedi `azzera_cache_fonti`.
        sources.azzera_cache_fonti()
        self.addCleanup(sources.azzera_cache_fonti)

        def esplode(url, timeout=None, headers=None):
            raise ConnectionError("rete non disponibile")

        sources.http_get = esplode
        passi = sources.diagnose_query("OPPO A6x")
        self.assertTrue(any(f["errore"] for f in passi["fonti"]))


class TestNomeModelloSenzaDecorazioni(unittest.TestCase):
    """Il nome del modello non deve mai contenere il codice fra parentesi.

    CASO REALE. La ricerca per «CPH2819» risolveva correttamente il codice
    e riempiva la barra con «Oppo A6X (cph2819)». Sembrava aver funzionato,
    ma quel nome decorato diventava un dispositivo DIVERSO da «OPPO A6x»
    delle fonti ufficiali — e soprattutto veniva poi usato come termine di
    ricerca nel catalogo, dove la parola «cph2819» non compare in nessun
    campo. Risultato: 917 dispositivi in archivio, la fonte verde, il
    codice risolto correttamente, e la lista dispositivi vuota."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        storage.upsert_update({
            "id": "x", "brand": C.OPPO, "device_model": "OPPO A6x",
            "device_key": "oppo|a6x", "title": "OPPO A6x — AER",
            "os_version": None, "android_version": None, "skin_name": None,
            "skin_version": None, "build": None, "patch_level": None,
            "severity": C.SEV_SECURITY, "color": "#00CC66", "severity_reason": "",
            "size_info": "", "link": "", "source": "oppo_aer",
            "source_label": "Oppo AER", "source_trust": C.TRUST_STRUCTURED,
            "published": None, "is_relevant": 1, "relevance_score": 9,
            "relevance_note": "",
        })

    def tearDown(self):
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_nome_decorato_trova_comunque_il_dispositivo(self):
        """Difesa verso i dati già in archivio: un nome contaminato non
        deve azzerare i risultati."""
        trovati = storage.get_devices(search="Oppo A6X (cph2819)")
        self.assertEqual([d["model"] for d in trovati], ["OPPO A6x"])

    def test_confronto_ignora_le_parentesi(self):
        self.assertEqual(
            modelcodes._normalize_name("Oppo A6X (cph2819)"),
            modelcodes._normalize_name("OPPO A6x"),
        )

    def test_ricerca_live_non_decora_il_nome(self):
        """Alla radice: il codice va nella descrizione, non nel nome."""
        orig_rss = sources.rss_items
        orig_download = modelcodes._download
        modelcodes.reset_cache()
        modelcodes._download = lambda url, key: (
            "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
            "CPH2819,mob,oppo,OPPO,,,OPPO A6x,\n"
        ).encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None
        sources.rss_items = lambda urls, brand, size_info, limit=None, timeout=None: (
            [sources.RawItem(title="OPPO A6x update", link="https://x.test",
                             brand=brand, size_info=size_info)], None)
        try:
            items, _ = sources.search_model_live("CPH2819")
            self.assertTrue(items)
            self.assertEqual(items[0].device, "OPPO A6x")
            self.assertNotIn("(", items[0].device)
            # Il codice resta comunque visibile, ma nella descrizione.
            self.assertIn("CPH2819", items[0].size_info)
        finally:
            sources.rss_items = orig_rss
            modelcodes._download = orig_download
            modelcodes.reset_cache()


class TestFonteUniversaleGSMArena(unittest.TestCase):
    """La versione di fabbrica per QUALSIASI modello.

    Risponde al problema di copertura alla radice, invece di aggiungere
    l'ennesima fonte per un brand: GSMArena ha una scheda per ogni telefono
    mai prodotto, ciascuna con la riga «OS: Android 15, ColorOS 15». Vale
    per le marche senza fonte ufficiale (Oppo, vivo, OnePlus, brand minori)
    e anche per quelle future, senza aggiungere codice.

    Il punto che la rende affidabile: la scheda contiene anche la riga
    «Models: CPH2819». La corrispondenza viene VERIFICATA sul codice, non
    dedotta dalla somiglianza dei nomi — è ciò che impedisce di attribuire
    a un telefono la versione di un altro."""

    RISULTATI = '<div><a href="oppo_a6x-14322.php"><img/>Oppo A6x 4G</a></div>'
    SCHEDA = (
        "<h1>Oppo A6x 4G - Full phone specifications</h1>"
        "<span>Released 2025, December 02</span>"
        "<table>"
        "<tr><td class='ttl'>OS</td><td class='nfo'>Android 15, ColorOS 15</td></tr>"
        "<tr><td class='ttl'>Models</td><td class='nfo'>CPH2819</td></tr>"
        "</table>"
    )

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._orig = sources.http_get

        class Resp:
            def __init__(self, testo):
                self.status_code = 200
                self.text = testo

        sources.http_get = lambda url, timeout=None: Resp(
            TestFonteUniversaleGSMArena.SCHEDA if "oppo_a6x-14322" in url
            else TestFonteUniversaleGSMArena.RISULTATI
        )

    def tearDown(self):
        sources.http_get = self._orig
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def test_versione_trovata_per_codice(self):
        trovati = sources._lookup_gsmarena("CPH2819")
        self.assertTrue(trovati)
        self.assertIn("Android 15", trovati[0].version)
        self.assertIn("ColorOS 15", trovati[0].version)

    def test_versione_trovata_per_nome(self):
        trovati = sources._lookup_gsmarena("Oppo A6x 4G")
        self.assertTrue(trovati)
        self.assertIn("Android 15", trovati[0].version)

    def test_codice_con_spazio(self):
        self.assertTrue(sources._lookup_gsmarena("cph 2819"))

    def test_codice_sbagliato_scartato(self):
        """La verifica sul codice è la garanzia contro l'attribuzione
        sbagliata: se il codice cercato non compare nella scheda, il
        risultato va scartato anche se il nome somiglia."""
        self.assertEqual(sources._lookup_gsmarena("CPH9999"), [])

    def test_dichiara_che_e_la_versione_di_fabbrica(self):
        """Il limite va detto, non lasciato intendere: questa è la versione
        con cui il telefono è uscito, non quella installata oggi."""
        trovati = sources._lookup_gsmarena("CPH2819")
        self.assertIn("FABBRICA", trovati[0].size_info.upper())

    def test_provata_per_ultima(self):
        """Le fonti ufficiali danno la versione attuale e vanno preferite:
        GSMArena chiude la fila."""
        for brand in (C.OPPO, C.SAMSUNG, None):
            with self.subTest(brand=brand):
                ordine = [v.etichetta for v in sources._lookup_order(brand)]
                self.assertEqual(ordine[-1], "scheda tecnica GSMArena")

    def test_copre_qualunque_marca(self):
        """Non è legata a un brand: entra nella fila anche quando la marca
        non è stata riconosciuta."""
        ordine = [v.etichetta for v in sources._lookup_order(None)]
        self.assertIn("scheda tecnica GSMArena", ordine)


class TestSceltaRisultatoMigliore(unittest.TestCase):
    """La ricerca deve preferire un risultato CON la versione firmware.

    CASO REALE. La fonte Oppo conferma che un modello esiste ma non ne
    pubblica la versione. Fermandosi al primo risultato utile, la ricerca
    si accontentava di quella conferma e non interrogava mai GSMArena, che
    la versione ce l'ha. Dal punto di vista di chi guarda: ricerca
    riuscita, riquadro verde, e nessun firmware — cioè inutile.

    «Esiste» e «è a questa versione» sono due risposte diverse, e solo la
    seconda è quella che l'app deve cercare."""

    OPPO_AER = "<p>OPPO A6x</p>"        # conferma il modello, nessuna versione
    GSM_RESULTS = '<a href="oppo_a6x-14322.php">Oppo A6x 4G</a>'
    GSM_SCHEDA = (
        "<h1>Oppo A6x 4G - Full phone specifications</h1>"
        "<span>Released 2025, December 02</span>"
        "<tr><td>OS</td><td>Android 15, ColorOS 15</td></tr>"
        "<tr><td>Models</td><td>CPH2819</td></tr>"
    )

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        modelcodes.reset_cache()
        self._orig = (sources.http_get, modelcodes._download)
        modelcodes._download = lambda url, key: (
            "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
            "CPH2819,mob,oppo,OPPO,,,OPPO A6x,\n"
        ).encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None

    def tearDown(self):
        sources.http_get, modelcodes._download = self._orig
        sources.attendi_riscaldamenti()
        modelcodes.reset_cache()
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def _rete(self, con_gsmarena=True):
        class Resp:
            def __init__(self, testo):
                self.status_code = 200
                self.text = testo

            def json(self):
                raise ValueError("non JSON")

        def finto(url, timeout=None, headers=None):
            if "oppo.com" in url:
                return Resp(TestSceltaRisultatoMigliore.OPPO_AER)
            if con_gsmarena and "oppo_a6x-14322" in url:
                return Resp(TestSceltaRisultatoMigliore.GSM_SCHEDA)
            if con_gsmarena and "gsmarena" in url:
                return Resp(TestSceltaRisultatoMigliore.GSM_RESULTS)
            return Resp("")

        sources.http_get = finto

    def test_scavalca_la_fonte_senza_versione(self):
        self._rete()
        trovati, _ = sources.lookup_model_structured("CPH2819")
        self.assertTrue(trovati)
        self.assertIn("Android 15", trovati[0].version or "")

    def test_vale_anche_per_nome_e_codice_con_spazio(self):
        self._rete()
        for query in ["cph 2819", "oppo a6x", "OPPO A6x"]:
            with self.subTest(query=query):
                trovati, _ = sources.lookup_model_structured(query)
                self.assertTrue(trovati)
                self.assertTrue(sources._ha_versione(trovati[0]),
                                f"«{query}» ha restituito un risultato senza firmware")

    def test_ripiego_quando_nessuna_fonte_ha_la_versione(self):
        """Se davvero nessuno pubblica la versione, si restituisce comunque
        la conferma del modello: è meno di niente ma non è niente, e
        l'interfaccia lo dichiara invece di spacciarlo per successo."""
        self._rete(con_gsmarena=False)
        trovati, _ = sources.lookup_model_structured("OPPO A6x")
        self.assertTrue(trovati)
        self.assertFalse(sources._ha_versione(trovati[0]))

    def test_riconoscimento_della_presenza_di_firmware(self):
        con_versione = sources.RawItem(title="x", device="X", version="Android 15")
        con_build = sources.RawItem(title="x", device="X", build="S928BXXU5CYA1")
        con_android = sources.RawItem(title="x", device="X", android_version=15)
        senza = sources.RawItem(title="x", device="X")
        self.assertTrue(sources._ha_versione(con_versione))
        self.assertTrue(sources._ha_versione(con_build))
        self.assertTrue(sources._ha_versione(con_android))
        self.assertFalse(sources._ha_versione(senza))


class TestDegradoSilenziosoFonti(unittest.TestCase):
    """Intercettare le fonti che rendono molto meno del solito.

    È il guasto che sfugge a ogni controllo: la fonte risponde, non dà
    errori, risulta verde — ma restituisce una frazione dei dati perché il
    sito ha cambiato struttura e il riconoscimento coglie solo una parte
    delle righe. In questa sessione è successo più volte, e ogni volta se
    n'è accorto l'utente prima dell'applicazione.

    Il rischio opposto è altrettanto serio: un falso allarme fa perdere
    fiducia in tutte le segnalazioni, comprese quelle vere. Metà di questi
    test verifica proprio che NON si allarmi senza motivo."""

    def setUp(self):
        self._db = tempfile.mktemp(suffix=".db")
        os.environ["TRACKER_DB"] = self._db
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        if os.path.exists(self._db):
            os.remove(self._db)

    def _scansione(self, fonte, voci, ok=True):
        storage.record_source_status(
            fonte, f"Fonte {fonte}", ok, voci, None if ok else "errore")
        storage.record_source_history(fonte, voci, ok)

    def _degrado(self, fonte):
        for stato in storage.get_source_status():
            if stato["source"] == fonte:
                return stato.get("degrado")
        return None

    def test_crollo_improvviso_rilevato(self):
        """Il caso reale: Xiaomi da ~1276 voci a 40, senza alcun errore."""
        for voci in [1276, 1280, 1274, 1279, 1276, 1281]:
            self._scansione("xiaomi", voci)
        self._scansione("xiaomi", 40)

        degrado = self._degrado("xiaomi")
        self.assertIsNotNone(degrado, "il crollo non è stato rilevato")
        self.assertEqual(degrado["attuale"], 40)
        self.assertGreater(degrado["calo_percentuale"], 90)

    def test_oscillazione_normale_non_allarma(self):
        """Una variazione fisiologica non deve produrre segnalazioni."""
        for voci in [20, 22, 19, 21, 20, 23]:
            self._scansione("stabile", voci)
        self._scansione("stabile", 18)
        self.assertIsNone(self._degrado("stabile"))

    def test_fonti_piccole_non_allarmano(self):
        """Su numeri piccoli le percentuali non dicono nulla: una fonte che
        passa da 4 voci a 1 non è un guasto, è normale oscillazione."""
        for voci in [4, 3, 5, 4, 3, 4]:
            self._scansione("piccola", voci)
        self._scansione("piccola", 1)
        self.assertIsNone(self._degrado("piccola"))

    def test_storico_troppo_breve_non_allarma(self):
        """Senza abbastanza rilevazioni non si può sapere cosa sia
        «normale» per quella fonte."""
        self._scansione("nuova", 500)
        self._scansione("nuova", 20)
        self.assertIsNone(self._degrado("nuova"))

    def test_un_singolo_giro_storto_non_falsa_il_riferimento(self):
        """Il confronto usa la MEDIANA, non la media: una scansione andata
        male (rete lenta, richiesta scaduta) non deve alterare il valore di
        riferimento e provocare allarmi nei giri successivi."""
        for voci in [100, 102, 98, 101, 99, 103]:
            self._scansione("normale", voci)
        self._scansione("normale", 5)     # giro anomalo isolato
        self._scansione("normale", 100)   # tutto torna a posto
        self.assertIsNone(
            self._degrado("normale"),
            "un singolo giro storto ha falsato il riferimento",
        )

    def test_fonte_in_errore_non_produce_doppia_segnalazione(self):
        """Se è già rossa, non serve dire anche che rende meno: sarebbe
        rumore su un problema già visibile."""
        for voci in [200, 210, 205, 208, 202, 207]:
            self._scansione("rotta", voci)
        self._scansione("rotta", 0, ok=False)
        self.assertIsNone(self._degrado("rotta"))

    def test_calo_moderato_tollerato(self):
        """La soglia è al 50%: un calo del 30% può dipendere da quanti
        aggiornamenti sono usciti quel giorno, non da un guasto."""
        for voci in [100, 105, 98, 102, 100, 103]:
            self._scansione("moderata", voci)
        self._scansione("moderata", 70)
        self.assertIsNone(self._degrado("moderata"))

    def test_storico_consultabile(self):
        for voci in [10, 20, 30]:
            self._scansione("fonte", voci)
        storico = storage.get_source_history("fonte")
        self.assertEqual([r["items_found"] for r in storico], [30, 20, 10])

    def test_storico_non_cresce_indefinitamente(self):
        """Lo storico serve al confronto, non all'archiviazione."""
        for numero in range(60):
            self._scansione("prolifica", 100 + numero)
        self.assertLessEqual(len(storage.get_source_history("prolifica", limit=200)), 30)

    def test_messaggio_spiega_il_problema(self):
        for voci in [1000, 1010, 990, 1005, 995, 1002]:
            self._scansione("verbosa", voci)
        self._scansione("verbosa", 100)
        messaggio = self._degrado("verbosa")["messaggio"]
        self.assertIn("100", messaggio)
        self.assertIn("formato", messaggio)


if __name__ == "__main__":
    unittest.main(verbosity=2)
