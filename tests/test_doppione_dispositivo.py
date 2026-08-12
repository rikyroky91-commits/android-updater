"""«Galaxy S24 Ultra» e «Samsung S24 Ultra» sono lo stesso telefono.

Il doppione è sopravvissuto a tre versioni per un motivo preciso: dalla v34
il riconoscimento della marca è corretto, ma le righe già scritte in
archivio non convergono da sole. La logica giusta non basta se i dati che
quella logica aveva prodotto restano com'erano.

Il danno non è estetico: la storia del telefono si spezza in due, ciascuna
metà con i propri conteggi «ultimi 30 giorni», e il parco di test può
seguirne una sola.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, extract, storage  # noqa: E402


class BaseArchivio(unittest.TestCase):
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

    def _riga(self, **kwargs):
        base = {
            "id": kwargs.get("id", "prova"),
            "brand": C.SAMSUNG,
            "device_model": "Galaxy S24 Ultra",
            "title": "aggiornamento",
            "severity": C.SEV_SECURITY,
            "source_trust": C.TRUST_STRUCTURED,
            "is_relevant": True,
            "published": "2026-07-01T10:00:00+00:00",
        }
        base.update(kwargs)
        base.setdefault(
            "device_key", extract.device_key(base["brand"], base["device_model"]))
        return base


class TestChiave(unittest.TestCase):
    """La chiave deve ignorare le parole che ripetono la marca, e SOLO
    quelle: fondere per sbaglio è peggio di lasciare un doppione, perché un
    doppione si vede e una fusione sbagliata mostra la versione di un
    telefono sotto il nome di un altro."""

    def test_le_tre_grafie_di_un_samsung_coincidono(self):
        chiavi = {
            extract.device_key(C.SAMSUNG, nome)
            for nome in ("Galaxy S24 Ultra", "Samsung S24 Ultra",
                         "Samsung Galaxy S24 Ultra", "S24 Ultra", "galaxy s24  ultra")
        }
        self.assertEqual(len(chiavi), 1, f"grafie ancora separate: {chiavi}")

    def test_apple_e_google_si_comportano_uguale(self):
        self.assertEqual(extract.device_key(C.APPLE, "Apple iPhone 15"),
                         extract.device_key(C.APPLE, "iPhone 15"))
        self.assertEqual(extract.device_key(C.PIXEL, "Google Pixel 9"),
                         extract.device_key(C.PIXEL, "Pixel 9"))

    def test_i_modelli_restano_distinti(self):
        diverse = [
            extract.device_key(C.SAMSUNG, "Galaxy S24"),
            extract.device_key(C.SAMSUNG, "Galaxy S24 Ultra"),
            extract.device_key(C.SAMSUNG, "Galaxy S25 Ultra"),
            extract.device_key(C.SAMSUNG, "Galaxy Note 20"),
        ]
        self.assertEqual(len(set(diverse)), len(diverse))

    def test_le_sottomarche_non_si_fondono(self):
        """Sotto «Oppo / Realme / OnePlus» le parole «oppo» e «realme»
        distinguono eccome: esistono sia un OPPO A5 sia un realme A5."""
        self.assertNotEqual(extract.device_key(C.OPPO, "Oppo A5"),
                            extract.device_key(C.OPPO, "realme A5"))
        self.assertNotEqual(extract.device_key(C.XIAOMI, "Redmi 13"),
                            extract.device_key(C.XIAOMI, "POCO 13"))

    def test_un_nome_fatto_di_sola_marca_non_diventa_chiave_vuota(self):
        """«Galaxy» da solo non è un modello, ma ridurlo a niente
        accorperebbe fra loro tutti i nomi degeneri — che è il modo di
        trasformare un dato mancante in un dato sbagliato."""
        chiave = extract.device_key(C.SAMSUNG, "Galaxy")
        self.assertTrue(chiave.split("|")[1])
        self.assertNotEqual(chiave, extract.device_key(C.SAMSUNG, "Samsung"))


class TestDeduplicaDelRilascio(unittest.TestCase):
    """La deduplica esiste per evitare che lo stesso rollout raccontato da
    tre testate diventi tre record e tre messaggi Telegram. Con il nome del
    modello preso alla lettera falliva proprio nel caso per cui esiste:
    basta che una testata scriva «Samsung» dove l'altra scrive «Galaxy»."""

    def setUp(self):
        from core import sources
        self.fonte = sources.Source("prova", "Fonte di prova", C.TRUST_CURATED,
                                    lambda: ([], None))

    def test_stesso_rilascio_due_grafie_un_record(self):
        from core import scan, sources

        a = sources.RawItem(
            title="Galaxy S24 Ultra: One UI 8.0 in distribuzione (S928BXXU5BYG1)",
            brand=C.SAMSUNG, device="Galaxy S24 Ultra", build="S928BXXU5BYG1")
        b = sources.RawItem(
            title="Samsung S24 Ultra riceve One UI 8.0 con build S928BXXU5BYG1",
            brand=C.SAMSUNG, device="Samsung S24 Ultra", build="S928BXXU5BYG1")

        self.assertEqual(scan.normalize(a, self.fonte)["id"],
                         scan.normalize(b, self.fonte)["id"])

    def test_modelli_diversi_restano_record_diversi(self):
        from core import scan, sources

        a = sources.RawItem(title="Galaxy S24 — One UI 8.0", brand=C.SAMSUNG,
                            device="Galaxy S24", build="S921BXXU5BYG1")
        b = sources.RawItem(title="Galaxy S24 Ultra — One UI 8.0", brand=C.SAMSUNG,
                            device="Galaxy S24 Ultra", build="S921BXXU5BYG1")
        self.assertNotEqual(scan.normalize(a, self.fonte)["id"],
                            scan.normalize(b, self.fonte)["id"])


class TestFusioneInArchivio(BaseArchivio):

    def test_due_grafie_diventano_un_dispositivo_solo(self):
        storage.upsert_update(self._riga(
            id="ufficiale", device_model="Galaxy S24 Ultra",
            build="S928BXXU5CYA1", os_version="Android 16"))
        storage.upsert_update(self._riga(
            id="ricerca", device_model="Samsung S24 Ultra",
            source_trust=C.TRUST_NOISY, patch_level="2026-07",
            published="2026-07-20T10:00:00+00:00"))

        dispositivi = storage.get_devices()
        self.assertEqual(len(dispositivi), 1)
        self.assertEqual(dispositivi[0]["updates_total"], 2)

    def test_il_nome_mostrato_e_quello_della_fonte_piu_affidabile(self):
        """Fuse le due righe, la scheda deve portare il nome ufficiale, non
        quello digitato in una ricerca — anche quando la ricerca è più
        recente. È lo stesso criterio già usato per versione, build e
        patch: decide l'affidabilità, non la data."""
        storage.upsert_update(self._riga(
            id="ufficiale", device_model="Galaxy S24 Ultra",
            published="2026-01-01T10:00:00+00:00"))
        storage.upsert_update(self._riga(
            id="ricerca", device_model="Samsung S24 Ultra",
            source_trust=C.TRUST_NOISY,
            published="2026-12-01T10:00:00+00:00"))

        self.assertEqual(storage.get_devices()[0]["model"], "Galaxy S24 Ultra")

    def test_si_trova_anche_col_nome_che_non_e_mostrato(self):
        """Chi ha cercato «Samsung S24 Ultra» deve ritrovarlo ora che la
        scheda si chiama «Galaxy S24 Ultra»: filtrare sul solo nome
        vincente farebbe sparire il dispositivo per metà delle ricerche."""
        storage.upsert_update(self._riga(
            id="ufficiale", device_model="Galaxy S24 Ultra"))
        storage.upsert_update(self._riga(
            id="ricerca", device_model="Samsung S24 Ultra",
            source_trust=C.TRUST_NOISY))

        for query in ("galaxy s24 ultra", "samsung s24 ultra", "s24 ultra"):
            with self.subTest(query=query):
                self.assertEqual(len(storage.get_devices(search=query)), 1)


class TestMigrazione(BaseArchivio):
    """Le righe già in archivio non convergono da sole: senza migrazione la
    correzione vale solo per i dati futuri, che è precisamente il motivo per
    cui questo difetto è sopravvissuto a tre versioni."""

    VECCHIA_UFFICIALE = "samsung|galaxys24ultra"
    VECCHIA_RICERCA = "samsung|samsungs24ultra"

    def _scrivi_con_chiavi_vecchie(self):
        storage.upsert_update(self._riga(
            id="ufficiale", device_model="Galaxy S24 Ultra",
            device_key=self.VECCHIA_UFFICIALE))
        storage.upsert_update(self._riga(
            id="ricerca", device_model="Samsung S24 Ultra",
            device_key=self.VECCHIA_RICERCA, source_trust=C.TRUST_NOISY))

    def test_gli_aggiornamenti_convergono(self):
        self._scrivi_con_chiavi_vecchie()
        self.assertEqual(len(storage.get_devices()), 2)

        esito = storage.migra_chiavi_dispositivo()
        self.assertEqual(esito["aggiornamenti"], 2)
        self.assertEqual(len(storage.get_devices()), 1)

    def test_il_parco_di_test_segue_le_chiavi(self):
        """È la parte che non si può sbagliare: la ricostruzione
        dell'archivio NON tocca il parco di test, quindi senza migrazione un
        dispositivo seguito resterebbe agganciato a una chiave che non
        esiste più — sparito dal parco pur essendo ancora in archivio."""
        self._scrivi_con_chiavi_vecchie()
        storage.add_to_watchlist(
            self.VECCHIA_UFFICIALE, C.SAMSUNG, "Galaxy S24 Ultra", "device primario")

        storage.migra_chiavi_dispositivo()

        dispositivo = storage.get_devices()[0]
        self.assertEqual(dispositivo["watched"], 1,
                         "il dispositivo seguito ha perso l'aggancio al parco di test")
        self.assertEqual(dispositivo["watch_note"], "device primario")

    def test_due_iscrizioni_allo_stesso_telefono_si_fondono(self):
        """Chi seguiva entrambe le grafie non deve ritrovarsi con una
        chiave primaria duplicata, né perdere la nota che aveva scritto."""
        storage.add_to_watchlist(self.VECCHIA_UFFICIALE, C.SAMSUNG,
                                 "Galaxy S24 Ultra", "")
        storage.add_to_watchlist(self.VECCHIA_RICERCA, C.SAMSUNG,
                                 "Samsung S24 Ultra", "quello con la SIM aziendale")

        esito = storage.migra_chiavi_dispositivo()

        parco = storage.get_watchlist()
        self.assertEqual(len(parco), 1)
        self.assertEqual(esito["parco_di_test"], 1)
        self.assertEqual(parco[0]["note"], "quello con la SIM aziendale",
                         "la nota scritta a mano è andata persa nella fusione")

    def test_delle_baseline_sopravvive_la_piu_recente(self):
        """La domanda è «cosa è cambiato dall'ULTIMA volta che l'ho
        provato»: fondendo due fotografie, tenere la vecchia direbbe da
        ritestare cose già ritestate."""
        with storage.transaction() as conn:
            for chiave, quando, build in (
                (self.VECCHIA_UFFICIALE, "2026-01-01T00:00:00+00:00", "vecchia"),
                (self.VECCHIA_RICERCA, "2026-06-01T00:00:00+00:00", "recente"),
            ):
                conn.execute(
                    """INSERT INTO test_baseline
                           (device_key, brand, model, os_version, android_version,
                            build, patch_level, tested_at, note)
                       VALUES (?, ?, ?, '', NULL, ?, NULL, ?, '')""",
                    (chiave, C.SAMSUNG, "Galaxy S24 Ultra", build, quando),
                )

        esito = storage.migra_chiavi_dispositivo()

        rimaste = storage.get_test_baselines()
        self.assertEqual(len(rimaste), 1)
        self.assertEqual(esito["baseline"], 1)
        self.assertEqual(list(rimaste.values())[0]["build"], "recente")

    def test_gira_una_volta_sola(self):
        """Una migrazione che rigira a ogni avvio è una migrazione che
        prima o poi riscrive dati già corretti."""
        self._scrivi_con_chiavi_vecchie()
        primo = storage.migra_chiavi_dispositivo()
        secondo = storage.migra_chiavi_dispositivo()
        self.assertTrue(any(primo.values()))
        self.assertEqual(secondo, {"aggiornamenti": 0, "parco_di_test": 0,
                                   "baseline": 0, "ricerche": 0})

    def test_su_archivio_vuoto_non_solleva(self):
        self.assertEqual(storage.migra_chiavi_dispositivo()["aggiornamenti"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
