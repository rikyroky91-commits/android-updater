"""Test della fonte ufficiale Oppo.

Le risposte usate qui sono REGISTRATE DAL SERVIZIO VERO
(`tests/fixtures/oppo_api.json`, catturate il 2026-08-02), non inventate.
È la lezione della fonte realme, rimasta rotta per giorni perché i suoi
test giravano su una resa che il codice non riceve mai. Se un giorno Oppo
cambia formato, il modo giusto di aggiornare questi test è ricatturare il
file, non riscrivere l'atteso a mano.

Nessun test qui tocca la rete: le funzioni di parsing sono separate da
quelle di trasporto proprio per rendere possibile questa scelta.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import oppo_official as oppo  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "fixtures", "oppo_api.json")
with open(_FIXTURES, encoding="utf-8") as _f:
    RISPOSTE = json.load(_f)


class TestConfrontoNomi(unittest.TestCase):
    """Il nome scritto dall'utente non coincide quasi mai con quello
    dell'API: il confronto deve assorbire marca, maiuscole e spazi."""

    def test_forme_equivalenti_collassano(self):
        for scritto in ("Find X2", "find x2", "OPPO Find X2", "  FindX2  "):
            self.assertEqual(oppo.normalize(scritto), oppo.normalize("Find X2"),
                             f"«{scritto}» non riconosciuto")

    def test_spazio_fra_sigla_e_cifre_ignorato(self):
        self.assertEqual(oppo.normalize("Reno 4 Pro"), oppo.normalize("Reno4 Pro"))

    def test_codice_fra_parentesi_ignorato(self):
        """L'API scrive «A73(CPH2095)»; chi cerca scrive «A73»."""
        self.assertEqual(oppo.normalize("A73(CPH2095)"), oppo.normalize("A73"))

    def test_modelli_diversi_restano_diversi(self):
        """La tolleranza non deve arrivare a fondere due device: un falso
        abbinamento è peggio di un modello non trovato, perché produce un
        dato sbagliato invece di un buco visibile."""
        self.assertNotEqual(oppo.normalize("Find X2"), oppo.normalize("Find X3"))
        self.assertNotEqual(oppo.normalize("A54"), oppo.normalize("A5"))


class TestLetturaRispostaReale(unittest.TestCase):
    def test_versione_corrente_estratta(self):
        dato = oppo.parse_info(RISPOSTE["info_find_x2"], "Find X2")
        self.assertIsNotNone(dato)
        self.assertEqual(dato["device_model"], "OPPO Find X2")
        self.assertTrue(dato["build"].startswith("CPH2023_"))
        self.assertEqual(dato["source_trust"], "structured")

    def test_si_prende_la_versione_piu_recente(self):
        """L'API elenca anche le versioni precedenti. Pubblicare la più
        vecchia significherebbe dichiarare fermo un telefono aggiornato."""
        payload = RISPOSTE["info_find_x2"]
        self.assertGreater(len(payload["data"]), 1, "fixture senza storico: test inutile")
        date = [v["releaseDate"] for v in payload["data"]]
        dato = oppo.parse_info(payload, "Find X2")
        self.assertEqual(dato["published"], max(date),
                         "non è stata scelta la release più recente")

    def test_conta_le_versioni_archiviate(self):
        dato = oppo.parse_info(RISPOSTE["info_find_x2"], "Find X2")
        self.assertEqual(dato["versioni_archiviate"], len(RISPOSTE["info_find_x2"]["data"]))

    def test_nessuna_versione_android_inventata(self):
        """`CPH2023_11_A.42` contiene «11», ma è un codice di canale, non
        Android 11. Dedurlo sarebbe un'ipotesi non verificata — la stessa
        famiglia di errore che è costata giorni a questo progetto."""
        dato = oppo.parse_info(RISPOSTE["info_find_x2"], "Find X2")
        self.assertNotIn("android_version", dato)
        self.assertNotIn("os_version", dato)

    def test_il_nome_non_porta_il_codice_appiccicato(self):
        """`A73(CPH2095)` come nome modello diventerebbe un dispositivo
        diverso da «OPPO A73» delle altre fonti, e come termine di ricerca
        nel catalogo non troverebbe nulla. Il codice resta disponibile a
        parte, non incollato al nome."""
        self.assertEqual(oppo.nome_pulito("A73(CPH2095)"), "A73")
        self.assertEqual(oppo.nome_pulito("A3s(CPH1803)"), "A3s")

    def test_il_nome_porta_la_marca_come_le_altre_fonti(self):
        """L'elenco AER e GSMArena scrivono «OPPO A6x». Un nome senza marca
        darebbe un `device_key` diverso per lo stesso telefono: due
        dispositivi in archivio, ciascuno con metà della storia."""
        self.assertEqual(oppo.nome_pulito("A73(CPH2095)", "OPPO"), "OPPO A73")
        self.assertEqual(oppo.nome_pulito("Find X2", "OPPO"), "OPPO Find X2")

    def test_la_marca_non_viene_raddoppiata(self):
        self.assertEqual(oppo.nome_pulito("OPPO Find X2", "OPPO"), "OPPO Find X2")

    def test_le_varianti_di_memoria_restano_distinte(self):
        """La ripulitura non deve arrivare a fondere due prodotti veri:
        «A83 (2G + 16G)» e «A83(3G+16G)…» sono device diversi."""
        self.assertEqual(oppo.nome_pulito("A83 (2G + 16G)"), "A83 (2G + 16G)")

    def test_dimensione_letta_come_numero(self):
        dato = oppo.parse_info(RISPOSTE["info_reno4_pro"], "Reno4 Pro")
        self.assertIsInstance(dato["size_mb"], int)
        self.assertGreater(dato["size_mb"], 100)


class TestChangelog(unittest.TestCase):
    def test_tag_sostituiti_da_spazio_non_rimossi(self):
        """`<p>[Security]</p><p>Added…` senza spazio diventerebbe
        `[Security]Added…`, attaccando parole che i pattern cercano
        separate."""
        testo = oppo.changelog_text("<p>[Security]</p><p>Added the patch</p>")
        self.assertEqual(testo, "[Security] Added the patch")

    def test_entita_doppiamente_codificate_risolte(self):
        self.assertEqual(oppo.changelog_text("a &amp;middot; b"), "a · b")

    def test_livello_patch_leggibile_nel_changelog_reale(self):
        """Il motivo per cui si interroga in inglese: la resa inglese dice
        «September 2020 Android security patch», che gli estrattori del
        progetto riconoscono; quella italiana no."""
        dato = oppo.parse_info(RISPOSTE["info_reno4_pro"], "Reno4 Pro")
        self.assertRegex(
            dato["changelog"],
            r"(?i)\b(january|february|march|april|may|june|july|august|"
            r"september|october|november|december)\s+20\d{2}\s+Android\s+security",
        )


class TestModelloFuoriDallArchivio(unittest.TestCase):
    """Il caso più frequente, e quello da non sbagliare: per ogni Oppo dal
    2022 in poi l'API risponde regolarmente ma senza dati. Va trattato come
    ASSENZA di dato, non come guasto: una fonte rossa in Diagnostica per un
    comportamento normale fa ignorare anche gli allarmi veri."""

    def test_risposta_vuota_non_produce_dato(self):
        self.assertEqual(RISPOSTE["info_modello_moderno"]["code"], "1",
                         "la fixture non rappresenta più il caso «vuoto ma OK»")
        self.assertIsNone(oppo.parse_info(RISPOSTE["info_modello_moderno"], "Find X8 Pro"))

    def test_codice_di_errore_non_produce_dato(self):
        self.assertIsNone(oppo.parse_info({"code": "500", "msg": "Server Is Busy"}, "Find X2"))

    def test_modello_sconosciuto_non_e_un_errore(self):
        """`fetch_oppo_official` distingue «non ce l'ho» da «non ho
        risposto»: solo il secondo va segnalato."""
        oppo.reset_cache()
        oppo._catalog = {oppo.normalize("Find X2"): (oppo.HOST_APAC, "in", "Find X2")}
        dato, errore = oppo.fetch_oppo_official("Find X9 Pro")
        self.assertIsNone(dato)
        self.assertIsNone(errore, "un modello assente non deve sembrare un guasto")
        oppo.reset_cache()

    def test_testo_vuoto_gestito(self):
        oppo.reset_cache()
        self.assertEqual(oppo.fetch_oppo_official(""), (None, None))
        oppo.reset_cache()


class TestCatalogo(unittest.TestCase):
    def test_elenco_modelli_letto_dalla_risposta_reale(self):
        payload = RISPOSTE["model_in"]
        attesi = {m["machineModel"] for s in payload["data"] for m in s["models"]}
        self.assertIn("Find X2", attesi)
        self.assertGreater(len(attesi), 30)

    def test_la_ricerca_usa_il_nome_esatto_dellapi(self):
        """Il catalogo serve proprio a questo: l'API accetta solo il nome
        `machineModel` esatto, e restituisce vuoto per qualsiasi variante."""
        oppo.reset_cache()
        oppo._catalog = {oppo.normalize("Reno4 Pro"): (oppo.HOST_APAC, "in", "Reno4 Pro")}
        inviato = {}

        def finto_post(url, payload, timeout=None):
            inviato["url"] = url
            inviato["payload"] = payload
            return RISPOSTE["info_reno4_pro"]

        originale = oppo._post
        oppo._post = finto_post
        try:
            dato, errore = oppo.fetch_oppo_official("oppo reno 4 pro")
        finally:
            oppo._post = originale
            oppo.reset_cache()

        self.assertIsNone(errore)
        self.assertIsNotNone(dato)
        self.assertEqual(inviato["payload"]["model"], "Reno4 Pro")
        self.assertEqual(inviato["payload"]["langId"], "1033")
        self.assertTrue(inviato["url"].endswith("/softwareUpgrade/info"))


class TestGuastiDiRete(unittest.TestCase):
    def test_errore_riportato_non_sollevato(self):
        """Una fonte irraggiungibile non deve far fallire la ricerca sulle
        altre: l'errore si riporta, non si propaga."""
        oppo.reset_cache()
        oppo._catalog = {oppo.normalize("Find X2"): (oppo.HOST_APAC, "in", "Find X2")}

        def finto_post(url, payload, timeout=None):
            raise OSError("rete assente")

        originale = oppo._post
        oppo._post = finto_post
        try:
            dato, errore = oppo.fetch_oppo_official("Find X2")
        finally:
            oppo._post = originale
            oppo.reset_cache()

        self.assertIsNone(dato)
        self.assertIn("rete assente", errore)



class TestAccensioneConLUaConcordato(unittest.TestCase):
    """La fonte OxygenUpdater si accende impostando una variabile sola.

    Il 16/08/2026 i manutentori hanno dato il via libera all'accesso ma
    hanno detto di non poter cambiare niente lato loro: l'API continua
    quindi a rispondere 403 a chi non si dichiara come la loro app, e
    l'unica cosa che serve e' mandare il valore concordato in
    OXYGEN_USER_AGENT.

    Chiedere ANCHE ENABLED_SOURCES sarebbe una seconda variabile che dice
    la stessa cosa, con l'unico effetto possibile di dimenticarla: si
    imposta l'UA, non succede niente, e niente spiega perche'.
    """

    def setUp(self):
        self._prima = os.environ.get("OXYGEN_USER_AGENT")
        os.environ.pop("OXYGEN_USER_AGENT", None)

    def tearDown(self):
        if self._prima is None:
            os.environ.pop("OXYGEN_USER_AGENT", None)
        else:
            os.environ["OXYGEN_USER_AGENT"] = self._prima

    def _chiavi(self):
        from core import sources

        return [s.key for s in sources.all_sources()]

    def test_senza_ua_la_fonte_resta_spenta(self):
        """Accesa senza UA sarebbe una riga rossa fissa in Diagnostica per
        una fonte che non puo' rispondere."""
        self.assertNotIn("oppo_official", self._chiavi())

    def test_con_lua_impostato_la_fonte_si_accende_da_sola(self):
        os.environ["OXYGEN_USER_AGENT"] = "valore-concordato-coi-manutentori"
        self.assertIn("oppo_official", self._chiavi())

    def test_resta_disattivabile_a_mano(self):
        """DISABLED_SOURCES deve continuare ad avere l'ultima parola."""
        os.environ["OXYGEN_USER_AGENT"] = "valore-concordato"
        prima = os.environ.get("DISABLED_SOURCES")
        os.environ["DISABLED_SOURCES"] = "oppo_official"
        try:
            self.assertNotIn("oppo_official", self._chiavi())
        finally:
            if prima is None:
                os.environ.pop("DISABLED_SOURCES", None)
            else:
                os.environ["DISABLED_SOURCES"] = prima


class TestEuropaInTesta(unittest.TestCase):
    """`_load_catalog` usa `setdefault`: la PRIMA regione che dichiara un
    modello ne fissa il nome. Con l'India in testa vinceva la grafia
    indiana — «cph 2219 e' oppo a74 invece mi trova oppo f19», segnalato
    il 16/08/2026: A74 e' il nome europeo, F19 quello indiano, stesso
    telefono.
    """

    def test_la_prima_regione_interrogata_e_europea(self):
        from core import oppo_official as oo

        primo_host, prima_regione = oo.CATALOG_REGIONS[0]
        self.assertEqual(primo_host, oo.HOST_EU)
        self.assertEqual(prima_regione, "pl")

    def test_le_altre_regioni_restano_tutte(self):
        """Riordinare non deve ridurre la copertura: le regioni
        successive riempiono i modelli che l'Europa non vende — l'India da
        sola ne dichiara 64 su 94."""
        from core import oppo_official as oo

        regioni = {r for _, r in oo.CATALOG_REGIONS}
        self.assertEqual(regioni, {"pl", "in", "tw", "ae", "au"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
