"""Test del catalogo specifiche hardware.

Le schede usate qui sono **registrate dalla fonte vera**
(`tests/fixtures/specs_devices.tar.gz`, nove schede reali su 4766) e non
ricostruite a mano: un parser collaudato su dati inventati collauda
l'immaginazione di chi ha scritto il test, non la fonte.

Dentro la fixture c'è anche un `details.json` volutamente corrotto: serve a
fissare che un file illeggibile su 4766 non deve far perdere gli altri.

Il test più importante di questo file è
`test_la_tabella_curata_vince_sulle_varianti`: il catalogo ha una scheda
sola per i modelli venduti con due chip diversi, e anteporlo alla tabella
curata significherebbe rispondere «o l'uno o l'altro» proprio dove la
risposta esatta si conosce.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C  # noqa: E402
from core import soc  # noqa: E402
from core import specs  # noqa: E402

_FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "specs_devices.tar.gz")

with open(_FIXTURE, "rb") as _f:
    ARCHIVIO = _f.read()

SCHEDE = specs.leggi_archivio(ARCHIVIO)


def carica_fixture():
    specs.carica_da(SCHEDE, "fixture")


class TestLetturaArchivio(unittest.TestCase):
    def setUp(self):
        carica_fixture()

    def tearDown(self):
        specs.reset_cache()

    def test_le_schede_si_leggono_dall_archivio_compresso(self):
        """Nove schede vere più un file corrotto: si leggono le nove."""
        self.assertEqual(len(SCHEDE), 9)

    def test_un_file_corrotto_non_fa_perdere_gli_altri(self):
        """La fixture contiene un `details.json` non parsabile."""
        nomi = {s["nome"] for s in SCHEDE}
        self.assertIn("Samsung Galaxy A07 4G", nomi)
        self.assertNotIn("Rotto", nomi)

    def test_marca_dedotta_dalla_cartella(self):
        """La fonte lascia `data.brand` vuoto: la marca sta nel percorso."""
        marche = {s["nome"]: s["marca"] for s in SCHEDE}
        self.assertEqual(marche["Samsung Galaxy A07 4G"], C.SAMSUNG)
        self.assertEqual(marche["Google Pixel 10"], C.PIXEL)

    def test_html_ripulito(self):
        """I valori arrivano come frammenti di HTML: `&amp;`, `<sup>2</sup>`.
        Non ripulirli significa scriverli tali e quali in interfaccia."""
        scheda = specs.per_codice("SM-A075F")
        self.assertIsNotNone(scheda.cpu)
        for veleno in ("&amp;", "<sup>", "&nbsp;", "</a>"):
            for valore in scheda.sezioni.get("Platform", {}).values():
                self.assertNotIn(veleno, valore)
            self.assertNotIn(veleno, scheda.cpu)


class TestLetturaMemoria(unittest.TestCase):
    """La riga `Memory.Internal` mescola archiviazione e RAM."""

    def test_tagli_separati(self):
        storage, ram = specs.leggi_memoria(
            "64GB 4GB RAM, 128GB 4GB RAM, 128GB 6GB RAM, 256GB 8GB RAM")
        self.assertEqual(storage, (64, 128, 256))
        self.assertEqual(ram, (4, 6, 8))

    def test_riga_senza_ram_resta_valida(self):
        """I telefoni vecchi dichiarano solo l'archiviazione: si legge
        quella invece di scartare tutta la riga."""
        storage, ram = specs.leggi_memoria("64GB")
        self.assertEqual(storage, (64,))
        self.assertEqual(ram, ())

    def test_terabyte_e_megabyte(self):
        storage, ram = specs.leggi_memoria("1TB 16GB RAM, 512MB")
        self.assertIn(1024, storage)
        self.assertEqual(ram, (16,))

    def test_riga_vuota_non_esplode(self):
        self.assertEqual(specs.leggi_memoria(""), ((), ()))
        self.assertEqual(specs.leggi_memoria(None), ((), ()))


class TestLetturaCodici(unittest.TestCase):
    def test_suffisso_dual_sim_tolto(self):
        """`/DS` identifica una confezione, non un telefono diverso."""
        self.assertEqual(
            specs.leggi_codici("SM-A075F, SM-A075F/DS, SM-A075M"),
            ["SM-A075F", "SM-A075M"],
        )

    def test_parole_senza_cifre_scartate(self):
        self.assertEqual(specs.leggi_codici("Global, International"), [])


class TestRicercaScheda(unittest.TestCase):
    def setUp(self):
        carica_fixture()

    def tearDown(self):
        specs.reset_cache()

    def test_il_caso_che_ha_originato_il_modulo(self):
        """`SM-A075F` non era in nessuna delle fonti precedenti."""
        scheda = specs.cerca("SM-A075F")
        self.assertEqual(scheda.nome, "Samsung Galaxy A07 4G")
        self.assertIn("Helio G99", scheda.chipset)
        self.assertEqual(scheda.ram_gb, (4, 6, 8))
        self.assertTrue(scheda.foto.startswith("https://"))

    def test_codice_indifferente_a_maiuscole_e_dual_sim(self):
        atteso = specs.cerca("SM-A075F").nome
        for forma in ("sm-a075f", "SM-A075F/DS", " SM-A075F "):
            self.assertEqual(specs.cerca(forma).nome, atteso, forma)

    def test_codice_dentro_una_frase(self):
        """Il codice arriva spesso annegato nel testo digitato."""
        self.assertEqual(specs.cerca("samsung SM-A075F europa").nome,
                         "Samsung Galaxy A07 4G")

    def test_nome_commerciale_in_tutte_le_grafie(self):
        for forma in ("Samsung Galaxy A56", "Galaxy A56", "samsung a56"):
            trovata = specs.cerca(forma)
            self.assertIsNotNone(trovata, forma)
            self.assertEqual(trovata.nome, "Samsung Galaxy A56", forma)

    def test_suffisso_di_connettivita_solo_se_non_ambiguo(self):
        """Chi cerca «Galaxy A07» intende il Galaxy A07, e il catalogo lo
        chiama «Galaxy A07 4G». Il ripiego vale solo con un candidato."""
        self.assertEqual(specs.cerca("Galaxy A07").nome, "Samsung Galaxy A07 4G")

    def test_ricerca_a_vuoto_non_inventa(self):
        self.assertIsNone(specs.cerca("Telefono Che Non Esiste 9000"))
        self.assertIsNone(specs.cerca(""))
        self.assertIsNone(specs.cerca(None))


class TestRipiegoEsternoConMarca(unittest.TestCase):
    """Il bug reale: «RMX3933» (un codice) e «Note 60s» (il nome canonico
    di quel codice) restavano senza scheda tecnica, mentre «realme Note
    60» — lo STESSO identico telefono — ce l'aveva. Vedi il docstring di
    `specs._ripiego_esterno`.

    `versus.marca_scoperta` guarda solo la prima parola del testo: nessuno
    dei due (un codice, un nome corto senza «realme» in testa) la supera.
    Qui non si tocca la rete: si finge `versus` per vedere CHI viene
    chiamato e CON QUALE testo, che è la parte che questo fix cambia.
    """

    def setUp(self):
        from core import sources, versus
        self._marca_scoperta = versus.marca_scoperta
        self._scheda_grezza = versus.scheda_grezza
        self.chiamate_scheda_grezza = []

        def finta_scheda_grezza(nome, marca_tracker=""):
            self.chiamate_scheda_grezza.append(nome)
            # Risponde solo a un nome commerciale vero con la marca già
            # scritta in testa — mai a un codice, che versus.com non
            # indicizza (vedi il docstring di `specs._ripiego_esterno`):
            # senza questo controllo il test passerebbe anche se il fix
            # si fermasse al primo indizio provato (il codice) invece di
            # arrivare al nome.
            marca = versus.marca_scoperta(nome)
            if not marca:
                return None
            resto = nome[len(marca):].strip() if nome.lower().startswith(marca.lower()) else nome
            if sources.looks_like_model_code(resto):
                return None
            return {"nome": nome, "chipset": "Unisoc Tiger T612",
                   "marca": marca_tracker}

        versus.scheda_grezza = finta_scheda_grezza

    def tearDown(self):
        from core import versus
        versus.marca_scoperta = self._marca_scoperta
        versus.scheda_grezza = self._scheda_grezza
        specs.reset_cache()

    def test_senza_indizio_di_marca_il_codice_resta_senza_scheda(self):
        """Comportamento di prima del fix: senza `marca`, un codice o un
        nome corto non trovano niente da versus.com."""
        self.assertIsNone(specs._ripiego_esterno("RMX3933", "Note 60s"))
        self.assertIsNone(specs._ripiego_esterno("RMX3933", "Note 60s", marca=None))

    def test_con_indizio_di_marca_il_codice_trova_la_scheda(self):
        """Con la marca nota (dal catalogo AER, non indovinata) il nome
        corto viene completato PRIMA di chiedere a versus.com."""
        scheda = specs._ripiego_esterno("RMX3933", "Note 60s", marca="realme")
        self.assertIsNotNone(scheda)
        # Il secondo giro (quello con la marca esplicita) ha provato
        # «realme RMX3933» e poi «realme Note 60s» — non il testo grezzo.
        self.assertIn("Realme Note 60s", self.chiamate_scheda_grezza)

    def test_il_testo_che_gia_porta_la_marca_non_ha_bisogno_dell_indizio(self):
        """Se uno degli indizi supera già `marca_scoperta` da solo (es.
        «realme Note 60»), si usa quello: il giro con l'indizio esplicito
        è un ripiego, non la prima scelta."""
        scheda = specs._ripiego_esterno("RMX3933", "realme Note 60", marca="realme")
        self.assertIsNotNone(scheda)
        self.assertEqual(self.chiamate_scheda_grezza, ["realme Note 60"])

    def test_indizio_di_marca_sconosciuta_viene_ignorato(self):
        """Una marca che versus.com non copre (es. «Samsung») non deve
        fabbricare un nome finto: quella marca ha già GSMArena."""
        self.assertIsNone(
            specs._ripiego_esterno("SM-S921B", "Galaxy S24", marca="Samsung"))
        self.assertEqual(self.chiamate_scheda_grezza, [])

    def test_cerca_passa_la_marca_al_ripiego(self):
        """`specs.cerca` (il punto d'ingresso vero, usato da
        `presenters.scheda_tecnica`) inoltra `marca` fino in fondo."""
        specs.reset_cache()  # nessuna scheda locale per RMX3933/Note 60s
        scheda = specs.cerca("RMX3933", "Note 60s", marca="realme")
        self.assertIsNotNone(scheda)
        self.assertIn("Realme Note 60s", self.chiamate_scheda_grezza)

    def test_il_codice_aggiunge_un_alias_reale_al_ripiego(self):
        """RMX2202 è «realme GT 5G»: cercare solo «GT» non basta alla fonte.

        L'alias viene dal codice tecnico già riconosciuto, non da una
        somiglianza fra modelli, quindi non può trasformare GT in GT Neo.
        """
        from core import modelcodes, versus
        originale_risolvi = modelcodes.resolve
        originale_scheda = versus.scheda_grezza
        chiamate = []

        modelcodes.resolve = lambda codice: (
            ["realme GT 5G"] if codice.upper() == "RMX2202" else []
        )

        def solo_alias(nome, marca_tracker=""):
            chiamate.append(nome)
            if nome.lower() == "realme gt 5g":
                return {"nome": nome, "chipset": "Snapdragon 888",
                        "marca": marca_tracker}
            return None

        versus.scheda_grezza = solo_alias
        try:
            scheda = specs._ripiego_esterno("RMX2202", "realme GT", marca="realme")
        finally:
            modelcodes.resolve = originale_risolvi
            versus.scheda_grezza = originale_scheda

        self.assertIsNotNone(scheda)
        self.assertIn("realme GT 5G", chiamate)


class TestChipsetLeggibile(unittest.TestCase):
    """La traduzione da stringa GSMArena a chip mostrabile."""

    def test_sigla_riconosciuta_ha_la_precedenza(self):
        chip, mercato = soc._chipset_leggibile(
            "Qualcomm SM8750-AC Snapdragon 8 Elite (3 nm)")
        self.assertEqual(chip.produttore, "Qualcomm")
        self.assertIn("Snapdragon 8 Elite", chip.nome)
        self.assertIsNone(mercato)

    def test_mercato_staccato_dalla_coda(self):
        chip, mercato = soc._chipset_leggibile("Exynos 2400 (4 nm) - International")
        self.assertEqual(mercato, "International")
        self.assertEqual(chip.produttore, "Samsung")
        self.assertNotIn("International", chip.nome)

    def test_produttore_dedotto_dalla_famiglia(self):
        """«Exynos 1580 (4 nm)» non nomina Samsung da nessuna parte."""
        chip, _ = soc._chipset_leggibile("Exynos 1580 (4 nm)")
        self.assertEqual(chip.produttore, "Samsung")

    def test_sigla_sconosciuta_si_riporta_come_scritta(self):
        """Riscrivere quello che la fonte dice sarebbe inventare: se la
        sigla non è nota si tiene il testo, senza il produttore doppio."""
        chip, _ = soc._chipset_leggibile("Mediatek MT6769V/CU Helio G80 (12 nm)")
        self.assertEqual(chip.produttore, "MediaTek")
        self.assertNotIn("Mediatek", chip.nome)
        self.assertIn("Helio G80", chip.nome)

    def test_riga_vuota(self):
        self.assertEqual(soc._chipset_leggibile(""), (None, None))


class TestSocDalCatalogo(unittest.TestCase):
    def setUp(self):
        carica_fixture()
        soc.reset_cache()

    def tearDown(self):
        specs.reset_cache()
        soc.reset_cache()

    def test_il_processore_si_trova_per_i_samsung_recenti(self):
        """Il motivo per cui esiste tutto questo: prima era None."""
        chip = soc.per_modello("SM-A075F", None)
        self.assertIsNotNone(chip)
        self.assertIn("Helio G99", chip.etichetta)

    def test_la_tabella_curata_vince_sulle_varianti(self):
        """Il catalogo ha UNA scheda per l'S24 con dentro tutti i codici,
        europei e americani. La tabella curata ha una riga per codice, e
        per questo deve restare davanti: `SM-S921B` è l'Exynos, punto."""
        chip = soc.per_modello("SM-S921B", None)
        self.assertEqual(chip.nome, "Exynos 2400")
        self.assertEqual(chip.produttore, "Samsung")

    def test_ambiguita_dichiarata_quando_il_catalogo_e_l_unica_fonte(self):
        """Per un codice che la tabella curata non ha, e la cui scheda
        elenca due chip, si riporta l'ambiguità invece di sceglierne uno:
        rispondere «Exynos» a chi ha il modello americano manda a cercare
        un difetto sul telefono sbagliato."""
        chip = soc._soc_da_specifiche(codice="SM-S921E")
        self.assertIsNotNone(chip)
        self.assertIn("oppure", chip.nome)
        self.assertIn("codice esatto", chip.nota)

    def test_il_chip_si_trova_anche_dal_nome_commerciale(self):
        chip = soc.per_modello("samsung galaxy a56", None)
        self.assertIsNotNone(chip)
        self.assertIn("Exynos 1580", chip.etichetta)

    def test_nessun_dato_inventato_per_un_modello_sconosciuto(self):
        self.assertIsNone(soc.per_modello("SM-Z999Q", "Telefono Inesistente 9000"))

    def test_marca_arriva_fino_al_ripiego_esterno(self):
        """Stesso bug di `TestRipiegoEsternoConMarca`, ma per il chip: senza
        marca esplicita un codice/nome corto di realme o HONOR non arriva
        mai a `_ripiego_esterno` con un indizio che `versus.marca_scoperta`
        possa accettare. Qui si verifica solo che `per_modello` INOLTRA
        l'argomento fino in fondo, non il risultato di versus.com."""
        catturato = {}

        def finto_ripiego(*testi, marca=None):
            catturato["testi"] = testi
            catturato["marca"] = marca
            return None

        originale = specs._ripiego_esterno
        specs._ripiego_esterno = finto_ripiego
        try:
            # Un codice/nome che nessun indice locale conosce: deve
            # arrivare fino all'ultima spiaggia per essere collaudabile.
            soc.per_modello("RMX9999", "Telefono Inesistente 9000", marca="realme")
        finally:
            specs._ripiego_esterno = originale
        self.assertEqual(catturato["marca"], "realme")


class TestNienteRete(unittest.TestCase):
    """`carica_da` esiste per collaudare senza dipendere da un server."""

    def tearDown(self):
        specs.reset_cache()

    def test_carica_da_non_scarica_niente(self):
        def esplodi():
            raise AssertionError("il catalogo ha provato a scaricare")

        originale = specs._scarica
        specs._scarica = esplodi
        try:
            specs.carica_da(SCHEDE, "fixture")
            self.assertIsNotNone(specs.per_codice("SM-A075F"))
        finally:
            specs._scarica = originale

    def test_status_dice_che_non_e_caricato(self):
        specs.reset_cache()
        self.assertIn("non ancora caricato", specs.status())


if __name__ == "__main__":
    unittest.main()
