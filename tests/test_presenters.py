"""Test di `web/presenters.py`.

Questo file nasce da un bug reale, segnalato dall'utente sul sito in
produzione: cercando «rmx 3933» (un codice realme) la scheda tecnica non
compariva; cercando «realme Note 60» — lo STESSO identico telefono, stesso
codice — compariva. La causa è descritta per esteso nel docstring di
`core.specs._ripiego_esterno`: il ripiego su versus.com (l'unica fonte di
scheda per realme/HONOR/Huawei/Nothing, vedi `core/versus.py`) decide la
marca guardando la PRIMA PAROLA del testo che riceve, e un codice o un nome
canonico corto («Note 60s», scelto da `modelcodes.nome_canonico` perché è
il più corto dei nomi veri di quel codice) non la scrivono mai.

`web/presenters.py::scheda_tecnica` è il punto giusto per collaudare il
fix: è lui a conoscere una marca affidabile — quella del catalogo AER
ufficiale (`aer_catalog.lookup(...).get("brand_aer")`), non indovinata dal
testo — ed è lui che prima di questo fix la calcolava ma non la passava
mai a `specs.cerca`/`soc.per_modello`.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import aer_catalog, backup, modelcodes, specs, soc  # noqa: E402
from web import presenters as P  # noqa: E402


def _voce_aer(nome: str, codici: str, marca: str) -> dict:
    """Una voce del catalogo AER, nella forma grezza che `parse_device` si
    aspetta (`displayName`/`brand`/`models`) — non un dizionario a caso:
    è la stessa forma con cui `aer_catalog._indicizza` la legge davvero."""
    return {"displayName": nome, "brand": marca, "models": codici,
            "hardwareFeatures": {}, "imageUrls": {}}


class TestMarcaAerPassataAlleFontiEsterne(unittest.TestCase):
    """Non verifica una scheda vera (niente rete nei test, vedi
    `versus._scarica` in `test_sito.py`): verifica solo che l'argomento
    `marca`, calcolato dal catalogo AER, arrivi fino a `specs.cerca` e
    `soc.per_modello` — il collegamento che prima mancava."""

    def setUp(self):
        aer_catalog.carica_da(
            [_voce_aer("Note Test 60s", "RMXTEST1", "realme")],
            "fixture di test")
        self._cerca_vera = specs.cerca
        self._per_modello_vero = soc.per_modello
        self.chiamate_cerca = []
        self.chiamate_soc = []

        def finto_cerca(*testi, marca=None):
            self.chiamate_cerca.append(marca)
            return None

        def finto_per_modello(model_code=None, device_name=None, marca=None):
            self.chiamate_soc.append(marca)
            return None

        specs.cerca = finto_cerca
        soc.per_modello = finto_per_modello

    def tearDown(self):
        specs.cerca = self._cerca_vera
        soc.per_modello = self._per_modello_vero
        aer_catalog.reset_cache()

    def test_la_marca_della_fonte_arriva_a_specs_cerca(self):
        P.scheda_tecnica("Note Test 60s", codice="RMXTEST1",
                         brand="Oppo / Realme / OnePlus")
        self.assertEqual(self.chiamate_cerca, ["Oppo / Realme / OnePlus"])

    def test_la_marca_della_fonte_arriva_a_soc_per_modello(self):
        P.scheda_tecnica("Note Test 60s", codice="RMXTEST1",
                         brand="Oppo / Realme / OnePlus")
        self.assertEqual(self.chiamate_soc, ["Oppo / Realme / OnePlus"])

    def test_senza_voce_aer_la_marca_e_none_non_indovinata(self):
        """Un codice che il catalogo AER non conosce non deve inventare
        una marca: quella dichiarata dalla fonte resta un vincolo di
        sicurezza e non puo' essere scartata."""
        P.scheda_tecnica("Telefono Che Non Esiste 9000", codice="ZZ0000",
                         brand="Samsung")
        self.assertEqual(self.chiamate_cerca, ["Samsung"])
        self.assertEqual(self.chiamate_soc, ["Samsung"])

    def test_il_vincolo_di_marca_blocca_omonimi_di_altri_produttori(self):
        """X200 Pro vivo non puo' risolvere il Samsung SM-X200."""
        aer_catalog.carica_da(
            [_voce_aer("Galaxy Tab A8", "SM-X200", "Samsung")],
            "omonimo di test")
        P.scheda_tecnica("X200 Pro", codice="", brand="Vivo / iQOO / Motorola")
        self.assertEqual(self.chiamate_cerca, ["Vivo / iQOO / Motorola"])

    def test_il_codice_e_il_nome_trovano_entrambi_la_stessa_voce_aer(self):
        """Cercare per codice o per nome è la stessa domanda: deve
        produrre la stessa marca, non una marca diversa a seconda della
        forma scritta — è esattamente l'incoerenza segnalata."""
        P.scheda_tecnica("Note Test 60s", codice="RMXTEST1", brand="")
        P.scheda_tecnica("Note Test 60s", codice="", brand="")
        self.assertEqual(self.chiamate_cerca, ["realme", "realme"])


class TestMarcaDaiNomiVeriQuandoLAerNonBasta(unittest.TestCase):
    """Secondo giro sullo stesso bug, segnalato di nuovo dall'utente:
    RMX3933 non è nel catalogo AER (non tutti i modelli realme lo sono —
    è un programma a cui il produttore aderisce modello per modello), e
    senza una voce AER `marca_aer` restava vuota per QUALSIASI forma del
    nome, non solo per quelle senza marca in testa. Il ripiego: guardare
    tutti i nomi VERI del codice (`modelcodes.resolve`, la stessa fonte
    già usata per i "gemelli") e prendere la marca dal primo che la
    dichiara — non indovinata, letta da un nome commerciale verificato.
    """

    def setUp(self):
        aer_catalog.reset_cache()  # nessuna voce AER per questo codice
        modelcodes._memory_cache = modelcodes._memory_cache or {}
        self._cerca_vera = specs.cerca
        self.chiamate_cerca = []

        def finto_cerca(*testi, marca=None):
            self.chiamate_cerca.append(marca)
            return None

        specs.cerca = finto_cerca

    def tearDown(self):
        specs.cerca = self._cerca_vera
        modelcodes._memory_cache.pop("ZZ4321", None)
        aer_catalog.reset_cache()

    def test_la_marca_si_trova_in_un_nome_vero_col_prefisso(self):
        """Nessuna voce AER, ma uno dei nomi veri del codice porta la
        marca in testa: si usa quella, non ci si arrende."""
        modelcodes._memory_cache["ZZ4321"] = ["Note Test", "realme Note Test"]
        P.scheda_tecnica("Note Test", codice="ZZ4321", brand="")
        self.assertEqual(self.chiamate_cerca, ["Realme"])

    def test_la_marca_si_trova_anche_senza_il_prefisso_esplicito(self):
        """NARZO è un caso reale (RMX3933 risolve anche a «NARZO N61»):
        `versus.marca_scoperta` riconosce «narzo» come sinonimo di
        realme anche senza la parola «realme» scritta da nessuna parte."""
        modelcodes._memory_cache["ZZ4321"] = ["Note Test", "NARZO Test"]
        P.scheda_tecnica("Note Test", codice="ZZ4321", brand="")
        self.assertEqual(self.chiamate_cerca, ["Realme"])

    def test_nessun_nome_vero_con_marca_riconosciuta_resta_none(self):
        """Nessuna voce AER e nessuno dei nomi veri porta una marca che
        versus.com copre: `marca` resta `None`, non un valore inventato."""
        modelcodes._memory_cache["ZZ4321"] = ["Galaxy Test", "Samsung Galaxy Test"]
        P.scheda_tecnica("Galaxy Test", codice="ZZ4321", brand="")
        self.assertEqual(self.chiamate_cerca, [None])


class TestStatoBackup(unittest.TestCase):
    """Nato da una domanda dell'utente: dopo il fix che avvia un backup
    subito a ogni correzione, la pagina Diagnostica non diceva NIENTE sul
    backup — nessun modo di vedere da fuori se fosse configurato e se
    l'ultimo salvataggio fosse davvero riuscito. Vedi `P.stato_backup`.
    """

    def setUp(self):
        self._configurato = backup.configurato
        self._stato = backup.stato

    def tearDown(self):
        backup.configurato = self._configurato
        backup.stato = self._stato

    def test_non_configurato(self):
        backup.configurato = lambda: False
        backup.stato = lambda: {"ultimo_esito": "non configurato",
                                "ultimo_salvataggio": None, "ultimo_ripristino": None}
        stato = P.stato_backup()
        self.assertEqual(stato["etichetta"], "Non configurato")
        self.assertEqual(stato["classe"], "tag-outline")

    def test_configurato_e_funzionante(self):
        backup.configurato = lambda: True
        backup.stato = lambda: {"ultimo_esito": "salvato (12 KB compressi)",
                                "ultimo_salvataggio": "2026-08-12T10:00:00+00:00",
                                "ultimo_ripristino": "2026-08-12T09:00:00+00:00"}
        stato = P.stato_backup()
        self.assertEqual(stato["etichetta"], "Attivo")
        self.assertEqual(stato["classe"], "tag-accent")
        self.assertIn("salvato", stato["dettaglio"])

    def test_configurato_ma_mai_ancora_tentato_in_questa_sessione(self):
        """Il caso che ha generato questo presenter: `_stato['ultimo_esito']`
        di `core/backup.py` parte da "non configurato" a ogni avvio del
        processo, anche quando la configurazione C'È — mostrarlo alla
        lettera farebbe credere che manchi la configurazione, quando è
        solo che non è ancora successo niente da riportare."""
        backup.configurato = lambda: True
        backup.stato = lambda: {"ultimo_esito": "non configurato",
                                "ultimo_salvataggio": None, "ultimo_ripristino": None}
        stato = P.stato_backup()
        self.assertNotEqual(stato["etichetta"], "Non configurato")
        self.assertIn("attesa", stato["etichetta"])
        self.assertNotIn("non configurato", stato["dettaglio"])

    def test_configurato_ma_in_errore(self):
        backup.configurato = lambda: True
        backup.stato = lambda: {
            "ultimo_esito": "GitHub ha risposto 401: token non valido",
            "ultimo_salvataggio": None, "ultimo_ripristino": None,
            "ultima_operazione": "salvataggio", "ultima_operazione_ok": False,
        }
        stato = P.stato_backup()
        self.assertEqual(stato["etichetta"], "Errore")
        self.assertEqual(stato["classe"], "tag-outline")
        self.assertIn("401", stato["dettaglio"])

    def test_ripristino_fallito_non_scambia_la_configurazione_per_un_errore(self):
        backup.configurato = lambda: True
        backup.stato = lambda: {
            "ultimo_esito": "connessione fallita durante il ripristino",
            "ultimo_salvataggio": None, "ultimo_ripristino": None,
            "ultima_operazione": "ripristino", "ultima_operazione_ok": False,
        }
        stato = P.stato_backup()
        self.assertEqual(stato["etichetta"], "Configurato, verifica consigliata")
        self.assertEqual(stato["classe"], "tag-neutral")
        self.assertIn("ripristino", stato["dettaglio"])


if __name__ == "__main__":
    unittest.main()
