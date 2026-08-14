"""Test della scheda tecnica per le marche fuori dal catalogo GSMArena.

I dati usati qui sono **registrati dalla fonte vera**, non ricostruiti a
mano: `tests/fixtures/versus_honor_magic7pro.html` è la pagina di versus
ritagliata alle sole parti che il parser legge (stessa scelta di
`vivo_aer.html`, e per lo stesso motivo: un parser collaudato su HTML
inventato collauda l'immaginazione di chi ha scritto il test), e
`versus_ricerca.json` sono risposte vere dell'endpoint di ricerca.

I test che contano di più in questo file non sono quelli che leggono un
valore: sono quelli che verificano che un telefono SBAGLIATO non venga
accettato. La ricerca di versus, interrogata con i nomi veri dei tracker
HONOR e realme, offre «Honor 400 Smart 5G» a chi ha chiesto «HONOR 400» e
«Realme 14 Pro» a chi ha chiesto «realme 14 Pro+ 5G». Sono i tranelli
registrati nella fixture, ed è la stessa famiglia di errore che il resto
del progetto documenta da mesi.
"""
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C  # noqa: E402

# L'ARCHIVIO DI QUESTO TEST È USA E GETTA, e la riga va prima di
# importare `versus`: il ricordo delle schede sta in un blob del database
# (`storage.set_blob`), quindi senza questo i test scriverebbero
# nell'archivio vero — e, peggio, si leggerebbero a vicenda, facendo
# passare per «scaricata» una scheda messa lì dal test precedente.
C.DB_PATH = os.path.join(tempfile.mkdtemp(prefix="versus-"), "test.db")
os.environ["TRACKER_DB"] = C.DB_PATH

from core import storage, versus  # noqa: E402

storage.reset_state()
storage.init_db()

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

with open(os.path.join(_FIXTURES, "versus_honor_magic7pro.html"), encoding="utf-8") as _f:
    PAGINA = _f.read()

with open(os.path.join(_FIXTURES, "versus_ricerca.json"), encoding="utf-8") as _f:
    RICERCHE = json.load(_f)


class _Risposta:
    """Il minimo che `versus._scarica` restituisce: testo e JSON."""

    def __init__(self, testo="", dati=None):
        self.text = testo
        self._dati = dati

    def json(self):
        if self._dati is None:
            raise ValueError("non è JSON")
        return self._dati


class TestMarcaScoperta(unittest.TestCase):
    """Questa fonte serve SOLO dove il catalogo GSMArena non arriva."""

    def test_le_quattro_marche_scoperte(self):
        for nome in ("realme C63", "HONOR Magic7 Pro", "Huawei P60",
                     "Nothing Phone 2", "NARZO 70 5G"):
            self.assertIsNotNone(versus.marca_scoperta(nome), nome)

    def test_le_marche_coperte_non_passano_di_qui(self):
        """Per Samsung, Xiaomi, Oppo e OnePlus il mirror GSMArena è una
        fonte migliore: è indicizzato per codice modello e distingue le
        varianti regionali. Interrogare versus per loro sarebbe scambiare
        una fonte buona con una peggiore."""
        for nome in ("Galaxy S24 Ultra", "Xiaomi 14", "OPPO Find X8",
                     "OnePlus 12", "Pixel 9 Pro"):
            self.assertIsNone(versus.marca_scoperta(nome), nome)

    def test_la_marca_si_legge_in_testa_non_in_mezzo(self):
        """«Galaxy S24 confrontato con HONOR 200» parla di un Samsung."""
        self.assertIsNone(versus.marca_scoperta("Galaxy S24 contro HONOR 200"))

    def test_testo_vuoto(self):
        self.assertIsNone(versus.marca_scoperta(None, "", "   "))


class TestChiaviDiConfronto(unittest.TestCase):
    def test_le_due_grafie_dello_stesso_telefono(self):
        """La pagina AER scrive «HONOR Magic7 Pro», versus «Honor Magic 7
        Pro»: senza questo non si troverebbero mai."""
        self.assertEqual(versus.chiave("HONOR Magic7 Pro"),
                         versus.chiave("Honor Magic 7 Pro"))

    def test_il_piu_e_la_parola_plus(self):
        """realme pubblica «realme 13+», versus «Realme 13 Plus»."""
        self.assertEqual(versus.chiave("realme 13+"), versus.chiave("Realme 13 Plus"))

    def test_il_piu_non_sparisce(self):
        """Togliere il «+» invece di tradurlo farebbe combaciare il Pro+
        con il Pro, che è un altro telefono con un altro chip."""
        self.assertNotEqual(versus.chiave("realme 13 Pro+"),
                            versus.chiave("realme 13 Pro"))

    def test_il_taglio_di_memoria_non_e_un_telefono(self):
        for grezzo in ("Realme 14 Pro (256GB / 12GB RAM)", "Realme 13 5G 128GB",
                       "Honor Magic 7 Lite 256GB", "Realme Narzo 70 5G 6GB RAM"):
            self.assertNotIn("GB", versus.senza_variante(grezzo), grezzo)

    def test_la_marca_si_aggiunge_solo_se_manca(self):
        self.assertEqual(versus.con_marca("NARZO 70 5G", "Realme"),
                         "Realme NARZO 70 5G")
        self.assertEqual(versus.con_marca("realme C63", "Realme"), "realme C63")


class TestSceltaCandidato(unittest.TestCase):
    """Il cuore del modulo: quando NON accettare una risposta."""

    def _scegli(self, chiesto, marca):
        risultati = RICERCHE[chiesto]
        return versus.scegli_candidato(versus.con_marca(chiesto, marca),
                                       risultati, marca)

    def test_il_modello_liscio_non_diventa_la_variante_smart(self):
        """IL TRANELLO REGISTRATO. Chiedendo «HONOR 400» la ricerca di
        versus mette per primo «Honor 400 Smart 5G», che è un altro
        telefono con un altro chip. Il modello giusto è più in basso."""
        scelto = self._scegli("HONOR 400", "Honor")
        self.assertIsNotNone(scelto)
        self.assertEqual(scelto["name_url"], "honor-400-5g")

    def test_due_versioni_di_connettivita_non_si_scelgono_a_caso(self):
        """Di «HONOR X7d» versus ha sia la 4G sia la 5G. Sono due telefoni:
        prenderne uno sarebbe indovinare, e si preferisce non rispondere.
        È la stessa regola di `specs.per_nome`."""
        self.assertIsNone(self._scegli("HONOR X7d", "Honor"))

    def test_il_piu_trova_la_parola_plus(self):
        scelto = self._scegli("realme 13+", "Realme")
        self.assertIsNotNone(scelto)
        self.assertEqual(scelto["name_url"], "realme-13-plus-5g")

    def test_il_pro_plus_non_diventa_il_pro(self):
        """L'ALTRO TRANELLO REGISTRATO: per «realme 14 Pro+ 5G» la ricerca
        propone «Realme 14 Pro», che monta un Dimensity 7300 invece di uno
        Snapdragon 7s Gen 3."""
        scelto = self._scegli("realme 14 Pro+ 5G", "Realme")
        if scelto is not None:
            self.assertIn("plus", scelto["name_url"])

    def test_un_altra_marca_non_e_una_risposta(self):
        """La ricerca di «realme 14 Pro+ 5G» risponde anche con dei Redmi
        Note 14 Pro: nomi simili, produttore diverso."""
        for riga in RICERCHE["realme 14 Pro+ 5G"]:
            scelto = versus.scegli_candidato("Realme 14 Pro Plus 5G",
                                             [riga], "Realme")
            if scelto is not None:
                self.assertTrue(scelto["name"].lower().startswith("realme"),
                                scelto["name"])

    def test_nessun_candidato_non_e_un_errore(self):
        self.assertIsNone(versus.scegli_candidato("Honor 999", [], "Honor"))
        self.assertIsNone(versus.scegli_candidato("", RICERCHE["HONOR 400"], "Honor"))


class TestRisolviConQueryAlternativa(unittest.TestCase):
    """La query completa può non contenere un vecchio modello nella top 20.

    Si registra il caso reale RMX3471 / realme 9 Pro 5G: la query senza 5G
    trova il modello liscio, che il selettore accetta solo perché è l'unico
    candidato con la medesima identità senza connettività.
    """

    def setUp(self):
        self._scarica = versus._scarica
        self.chiamate = []

        def finta(url, parametri=None):
            self.chiamate.append((url, (parametri or {}).get("q")))
            if (parametri or {}).get("q") == "Realme 9 Pro 5G":
                return _Risposta(dati=[{
                    "name": "Realme 9 Pro Plus 5G",
                    "name_url": "realme-9-pro-plus-5g",
                    "categories": ["phone"],
                }])
            return _Risposta(dati=[{
                "name": "Realme 9 Pro",
                "name_url": "realme-9-pro",
                "categories": ["phone"],
            }])

        versus._scarica = finta

    def tearDown(self):
        versus._scarica = self._scarica

    def test_riprova_senza_5g_senza_accettare_un_plus(self):
        scelto = versus.risolvi("Realme 9 Pro 5G", "Realme")
        self.assertEqual(scelto["name_url"], "realme-9-pro")
        self.assertEqual([q for _url, q in self.chiamate],
                         ["Realme 9 Pro 5G", "Realme 9 Pro"])


class TestLetturaPagina(unittest.TestCase):
    def setUp(self):
        self.proprieta, self.sezioni = versus.leggi_pagina(PAGINA)

    def test_i_capitoli_ci_sono_tutti(self):
        self.assertEqual(len(self.sezioni), 9)
        self.assertIn("Design", self.sezioni)
        self.assertIn("Performance", self.sezioni)

    def test_il_numero_di_capitolo_non_e_il_nome(self):
        for titolo in self.sezioni:
            self.assertFalse(titolo[0].isdigit(), titolo)

    def test_i_valori_che_servono(self):
        self.assertEqual(self.proprieta["chipset_name"], "Qualcomm Snapdragon 8 Elite")
        self.assertEqual(self.proprieta["ram"], "16GB")
        self.assertEqual(self.proprieta["battery_power"], "5,850 mAh")
        self.assertEqual(self.proprieta["android_version"], "Android 15")

    def test_un_booleano_non_e_una_stringa_vuota(self):
        """`<span class="bool y">` non ha testo: letto con un `strip_tags`
        diventa vuoto, e «ha l'NFC» e «non si sa» diventano la stessa cosa."""
        self.assertEqual(self.proprieta["nfc"], "sì")
        self.assertEqual(self.proprieta["headset_jack_35"], "no")

    def test_pagina_vuota_non_esplode(self):
        self.assertEqual(versus.leggi_pagina(""), ({}, {}))
        self.assertEqual(versus.leggi_pagina(None), ({}, {}))


class TestNumeriConSeparatore(unittest.TestCase):
    """Il motivo per cui si scarica la pagina INGLESE.

    Gli stessi valori escono come `1.024GB` in italiano e `1,024GB` in
    inglese. In italiano il punto separa le migliaia, e leggerlo come
    decimale trasformerebbe un terabyte in un giga.
    """

    def test_migliaia_non_confuse_con_decimali(self):
        self.assertEqual(versus._gigabyte("1,024GB"), (1024,))
        self.assertEqual(versus._numero("5,850 mAh"), 5850)

    def test_terabyte_convertiti(self):
        self.assertEqual(versus._gigabyte("1TB"), (1024,))

    def test_valori_assenti(self):
        self.assertEqual(versus._gigabyte(None), ())
        self.assertEqual(versus._gigabyte(""), ())
        self.assertIsNone(versus._numero(None))


class TestCostruisciScheda(unittest.TestCase):
    def setUp(self):
        self.riga = versus.costruisci_scheda("Honor Magic 7 Pro", PAGINA, C.HUAWEI)

    def test_i_campi_che_l_interfaccia_mostra(self):
        self.assertEqual(self.riga["nome"], "Honor Magic 7 Pro")
        self.assertEqual(self.riga["marca"], C.HUAWEI)
        self.assertIn("Snapdragon 8 Elite", self.riga["chipset"])
        self.assertEqual(self.riga["ram_gb"], [16])
        self.assertEqual(self.riga["storage_gb"], [1024])
        self.assertTrue(self.riga["display"])
        self.assertTrue(self.riga["batteria"])
        self.assertEqual(self.riga["fonte"], versus.FONTE_LABEL)

    def test_il_taglio_di_memoria_non_entra_nel_nome(self):
        """Di alcuni modelli versus pubblica solo le pagine per confezione:
        il titolo «Realme 14 Pro (256GB / 8GB RAM)» renderebbe la pagina del
        dispositivo un telefono diverso da quello del tracker."""
        senza_titolo = re.sub(r"<h1.*?</h1>", "", PAGINA, flags=re.S)
        riga = versus.costruisci_scheda("Realme 14 Pro (256GB / 12GB RAM)",
                                        senza_titolo, C.OPPO)
        self.assertEqual(riga["nome"], "Realme 14 Pro")

    def test_nessun_dato_di_firmware(self):
        """versus è un catalogo di hardware. La versione che pubblica è
        quella di lancio, e attribuirla come versione attuale è l'errore
        già commesso con HONOR X8c (vedi `core/sources.py`): qui la scheda
        non espone nemmeno il campo."""
        self.assertNotIn("android_version", self.riga)
        self.assertEqual(self.riga["os_lancio"], "Android 15")

    def test_lo_zoom_assente_non_diventa_un_dato(self):
        """versus scrive `0x` quando lo zoom ottico non c'è: riportarlo
        mette «zoom ottico 0x» nella scheda di ogni telefono economico."""
        self.assertIsNone(versus._zoom("0x"))
        self.assertEqual(versus._zoom("3x"), "zoom ottico 3x")

    def test_niente_codici_inventati(self):
        """versus non pubblica i codici modello: l'indice per codice resta
        quello di GSMArena. Dichiararlo vuoto è corretto, riempirlo con
        qualcosa che somiglia a un codice no."""
        self.assertEqual(self.riga["codici"], [])

    def test_pagina_illeggibile_non_produce_una_scheda_vuota(self):
        self.assertIsNone(versus.costruisci_scheda("X", "<html></html>", C.HUAWEI))


class TestSenzaRete(unittest.TestCase):
    """Una fonte esterna che non risponde deve togliere una sezione dalla
    pagina, non farla fallire."""

    def setUp(self):
        self._vero = versus._scarica
        versus.reset_cache(anche_archivio=True)

    def tearDown(self):
        versus._scarica = self._vero
        versus.reset_cache(anche_archivio=True)

    def test_rete_muta(self):
        versus._scarica = lambda url, parametri=None: None
        self.assertIsNone(versus.scheda_grezza("HONOR Magic7 Pro", C.HUAWEI))

    def test_risposta_illeggibile(self):
        versus._scarica = lambda url, parametri=None: _Risposta("non json")
        self.assertIsNone(versus.scheda_grezza("realme C63", C.OPPO))

    def test_una_marca_coperta_non_esce_nemmeno_in_rete(self):
        def esplodi(url, parametri=None):
            raise AssertionError("versus interrogato per una marca coperta")

        versus._scarica = esplodi
        self.assertIsNone(versus.scheda_grezza("Galaxy S24 Ultra", C.SAMSUNG))


class TestGiroCompleto(unittest.TestCase):
    """Dalla domanda alla scheda, con la rete finta ma i dati veri."""

    def setUp(self):
        self._vero = versus._scarica
        versus.reset_cache(anche_archivio=True)
        self.chiamate = []

        def finta(url, parametri=None):
            self.chiamate.append(url)
            if url == versus.RICERCA_URL:
                return _Risposta(dati=RICERCHE["HONOR 400"])
            return _Risposta(testo=PAGINA)

        versus._scarica = finta

    def tearDown(self):
        versus._scarica = self._vero
        versus.reset_cache(anche_archivio=True)

    def test_la_scheda_arriva(self):
        riga = versus.scheda_grezza("HONOR 400", C.HUAWEI)
        self.assertIsNotNone(riga)
        self.assertIn("Snapdragon", riga["chipset"])
        self.assertEqual(riga["marca"], C.HUAWEI)

    def test_una_pagina_troppo_corta_e_una_pagina_di_errore(self):
        """Una risposta di poche decine di kB non è la scheda di un
        telefono: leggerla produrrebbe una scheda vuota indistinguibile da
        un modello senza dati."""
        versus._scarica = lambda url, parametri=None: (
            _Risposta(dati=RICERCHE["HONOR 400"]) if url == versus.RICERCA_URL
            else _Risposta(testo="<html>errore</html>"))
        self.assertIsNone(versus.scheda_grezza("HONOR 400", C.HUAWEI))


if __name__ == "__main__":
    unittest.main()
