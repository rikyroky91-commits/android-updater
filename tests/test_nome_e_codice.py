"""Cercare per nome e cercare per codice devono portare allo stesso posto.

«samsung s24» e «SM-S921B» sono lo stesso telefono, e devono dare la stessa
versione, la stessa build e la stessa CPU. Lo stesso vale per «oppo reno 14»
e «CPH2737», e per ogni altra marca: chi fa QA scrive l'una o l'altra forma
a seconda di dove ha letto il modello, e non deve ottenere due risposte.

Verificato anche sul campo (v41), ma qui la rete non si tocca: si prova il
MECCANISMO — quali forme vengono provate, quale risultato vince, dove
finisce il codice della variante.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, extract, modelcodes, scan, sources, storage  # noqa: E402

# Dataset ridotto, nella forma reale dei due CSV pubblici.
MOBILEMODELS = (
    "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
    "CPH2737,mob,oppo,OPPO,,,OPPO Reno14,\n"
    "SM-S921B,mob,samsung,Samsung,,,Galaxy S24,\n"
    "SM-S9210,mob,samsung,Samsung,,,Galaxy S24,\n"
    "SM-S921U,mob,samsung,Samsung,,,Galaxy S24,\n"
    "23129RAA4G,mob,xiaomi,Xiaomi,,,Redmi Note 13,\n"
    # Codici la cui FORMA non dice niente, e la cui marca è invece scritta
    # nel dataset: sono la ragione per cui `brand_from_code` non può
    # basarsi su un elenco di espressioni regolari.
    "PCET00,mob,oppo,OPPO,,,OPPO A9x,\n"
    "V2283A,mob,vivo,vivo,,,vivo S17,\n"
    "CLT-L04,mob,huawei,HUAWEI,,,HUAWEI P20 Pro,\n"
    "G020E,mob,google,Google,,,Pixel 3a,\n"
    "MKDA,mob,nokia,Nokia,,,Nokia C32,\n"
)


class BaseCodici(unittest.TestCase):
    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._download = modelcodes._download
        modelcodes._download = lambda url, chiave: (
            MOBILEMODELS.encode("utf-8-sig") if url == modelcodes.MOBILEMODELS_URL else None
        )
        modelcodes.reset_cache()
        modelcodes.resolve("")

    def tearDown(self):
        modelcodes._download = self._download
        modelcodes.reset_cache()
        storage.reset_state()
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale


class TestFormeEquivalenti(BaseCodici):
    """Il dataset sa fare il percorso in tutti e due i versi. Finché se ne
    usava uno solo, la ricerca per nome non arrivava alle fonti ufficiali."""

    def test_dal_nome_si_arriva_al_codice(self):
        forme = scan.forme_equivalenti("oppo reno 14")
        self.assertIn("CPH2737", forme)

    def test_dal_codice_si_arriva_al_nome(self):
        forme = scan.forme_equivalenti("CPH2737")
        self.assertIn("OPPO Reno14", forme)

    def test_un_codice_di_forma_insolita_arriva_lo_stesso_al_nome(self):
        """`23129RAA4G` non somiglia a nessuna delle forme note (SM-, CPH,
        RMX): il filtro per forma lo scartava, benché il dataset lo
        conoscesse alla lettera."""
        self.assertIn("Redmi Note 13", scan.forme_equivalenti("23129RAA4G"))

    def test_il_testo_digitato_resta_il_primo(self):
        """Le forme derivate sono un ripiego, non un sostituto: la prima
        cosa da provare è sempre ciò che è stato scritto."""
        self.assertEqual(scan.forme_equivalenti("oppo reno 14")[0], "oppo reno 14")

    def test_nessun_doppione(self):
        forme = scan.forme_equivalenti("CPH2737")
        self.assertEqual(len(forme), len({f.lower() for f in forme}))


class TestNomeAmbiguoNonReindirizzaAUnAltroTelefono(unittest.TestCase):
    """Cercando «realme c63» il sito mostrava la scheda di «C61»: niente
    foto, niente CPU, aggiornamenti di RMX3930 (il vero C61, secondo
    Android Enterprise Recommended) al posto di RMX3939 (verificato in
    questo stesso progetto come "realme C63", vedi `data/soc_modelli.csv`).

    Riprodotto qui SENZA rete: il dataset MobileModels (community, non
    verificato) assegna il nome "C61" a più di un codice — non solo al
    caso reale già noto (RMX3933, gestito correttamente dai "gemelli" in
    `web/main.py`), ma anche a RMX3939, dove collide con RMX3930. Prima
    della correzione, `forme_equivalenti` provava "C61" come forma
    equivalente di RMX3939 e una fonte ufficiale rispondeva per l'ALTRO
    telefono che porta lo stesso nome nel dataset.
    """

    MOBILEMODELS = (
        "model,dtype,brand,brand_title,code,code_alias,model_name,ver_name\n"
        "RMX3939,mob,realme,realme,,,realme C63,\n"
        "RMX3939,mob,realme,realme,,,realme C61,\n"
        "RMX3930,mob,realme,realme,,,realme C61,\n"
    )

    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        self._download = modelcodes._download
        modelcodes._download = lambda url, chiave: (
            self.MOBILEMODELS.encode("utf-8-sig")
            if url == modelcodes.MOBILEMODELS_URL else None)
        modelcodes.reset_cache()
        modelcodes.resolve("")
        self._ordine = sources._lookup_order

    def tearDown(self):
        sources._lookup_order = self._ordine
        modelcodes._download = self._download
        modelcodes.reset_cache()
        storage.reset_state()
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale

    def test_il_nome_condiviso_non_e_una_forma_equivalente(self):
        """`resolve()` grezzo lo darebbe ancora — è `resolve_senza_ambiguita`
        (usato da `forme_equivalenti`) a doverlo scartare.

        Query «c63» invece di «realme c63»: con quest'ultima, «realme C63»
        finito fra le forme derivate coinciderebbe (a maiuscole/minuscole)
        con la query originale già in testa alla lista, e la dedup la
        toglierebbe comunque — un falso negativo che non proverebbe niente
        sul filtro dell'ambiguità, che è ciò che questo test deve isolare.
        """
        self.assertIn("realme C61", modelcodes.resolve("RMX3939"))
        forme = scan.forme_equivalenti("c63")
        self.assertIn("RMX3939", forme)
        self.assertIn("realme C63", forme)
        self.assertNotIn("realme C61", forme)

    def test_la_ricerca_non_trova_il_firmware_dell_altro_telefono(self):
        """Fonte ufficiale di prova che risponde SOLO al nome ambiguo
        "realme C61" — cioè esattamente la fonte che nella realtà è
        Android Enterprise Recommended per RMX3930. Se la correzione
        funziona, questa fonte non deve più essere interrogata affatto per
        una ricerca su RMX3939/C63: l'eventuale risultato deve venire
        dal riconoscimento del codice (RMX3939), mai dal nome condiviso.
        """
        def solo_per_c61(nome):
            if nome != "realme C61":
                return []
            return [sources.RawItem(
                title="realme C61 (RMX3930) — piano ufficiale",
                brand=C.OPPO, device="realme C61",
                os_version="Android 14", size_info="AER di prova")]

        sources._lookup_order = lambda brand: [
            sources.StructuredLookup(C.OPPO, solo_per_c61, "basso", "AER di prova"),
        ]
        items, _nota = scan._lookup_structured_for("realme c63")
        self.assertFalse(
            any("RMX3930" in (i.get("title") or "") for i in items),
            "non deve restituire il firmware di un telefono diverso "
            "(RMX3930/C61) per una ricerca su RMX3939/C63")
        if items:
            self.assertIn("RMX3939", items[0]["title"])
            self.assertEqual(items[0]["device_model"], "realme C63")

    def test_nome_canonico_preferisce_il_nome_non_ambiguo(self):
        """Conseguenza diretta dello stesso principio, in `nome_canonico`:
        fra "C63" (solo di RMX3939) e "C61" (anche di RMX3930), a parità
        di ogni altro criterio va scelto quello che non si confonde con un
        altro telefono — non il primo in ordine alfabetico, che qui
        sarebbe stato proprio "C61"."""
        self.assertEqual(modelcodes.nome_canonico("RMX3939"), "realme C63")
        # RMX3930 ha SOLO "realme C61": nessuna alternativa non ambigua
        # disponibile, quindi resta quello — non c'è un dato migliore da
        # preferire, e il filtro non deve svuotare la risposta.
        self.assertEqual(modelcodes.nome_canonico("RMX3930"), "realme C61")


class TestSpazioFraGammaENumero(BaseCodici):
    """«OPPO Reno14» sul catalogo, «oppo reno 14» nella testa delle persone."""

    def test_lo_spazio_non_impedisce_la_risoluzione(self):
        self.assertIn("CPH2737", modelcodes.codes_for_name("oppo reno 14"))
        self.assertIn("CPH2737", modelcodes.codes_for_name("Oppo Reno14"))
        self.assertIn("CPH2737", modelcodes.codes_for_name("reno 14"))

    def test_non_inventa_corrispondenze(self):
        self.assertEqual(modelcodes.codes_for_name("telefono inesistente 99"), [])


class TestMarcaDalDataset(BaseCodici):
    """PRIMA IL DATO, POI L'INDOVINELLO.

    La marca era già scritta nei dataset dei codici, riga per riga, e
    veniva buttata via: si deduceva da una manciata di formati scritti a
    mano (`RMX`, `CPH`, `SM-`, `XT`), quindi ogni famiglia non prevista
    finiva sotto «Altri brand». Non è un dettaglio di presentazione — il
    brand entra nella chiave del dispositivo, quindi lo stesso telefono
    cercato per nome e per codice diventava due schede separate.

    Misurato su un campione casuale di 32 modelli: era la causa singola più
    frequente di divergenza fra le due ricerche.
    """

    def test_codici_che_nessun_formato_riconosce(self):
        atteso = {
            "PCET00": C.OPPO,       # Oppo, ma non comincia per CPH
            "V2283A": C.VIVO,       # vivo
            "CLT-L04": C.HUAWEI,    # Huawei
            "G020E": C.PIXEL,       # un Pixel dato per Samsung, prima
        }
        for codice, gruppo in atteso.items():
            with self.subTest(codice=codice):
                self.assertEqual(sources.brand_from_code(codice), gruppo)

    def test_una_marca_non_elencata_finisce_fra_gli_altri(self):
        """«Altri brand» è una risposta vera: Nokia sta davvero lì."""
        self.assertEqual(sources.brand_from_code("MKDA"), C.OTHER)

    def test_i_formati_noti_continuano_a_valere(self):
        """Servono ancora per i codici che nessun dataset conosce."""
        self.assertEqual(sources.brand_from_code("RMX9999"), C.OPPO)
        self.assertEqual(sources.brand_from_code("SM-Z999X"), C.SAMSUNG)

    def test_un_testo_qualunque_non_riceve_una_marca(self):
        self.assertIsNone(sources.brand_from_code("telefono qualsiasi"))
        self.assertIsNone(sources.brand_from_code(""))

    def test_lo_spazio_dentro_il_codice_non_lo_nasconde(self):
        """«TECNO W5006S» è scritto con lo spazio nel dataset: compattarlo
        e basta faceva perdere la marca di tutta quella famiglia."""
        self.assertEqual(sources.gruppo_di_marca("OPPO"), C.OPPO)
        self.assertEqual(sources.gruppo_di_marca("Redmi"), C.XIAOMI)
        self.assertIsNone(sources.gruppo_di_marca(""))


class TestMarcaRipetutaNelNome(unittest.TestCase):
    """UNDICIMILA NOMI SBAGLIATI, E LI SCRIVEVAMO NOI.

    Il CSV di Google tiene marca e nome in due colonne, ma il nome spesso
    la marca ce l'ha già dentro: unirli sempre produceva «POCO POCO M4
    Pro», «Nokia Nokia C32», «Honor HONOR Magic6» — 11 251 voci su questa
    forma, misurate sul file vero.

    E il nome finisce nella chiave del dispositivo: chi cercava «POCO M4
    Pro» e chi arrivava dal codice — che risolve al nome duplicato —
    ottenevano due schede per lo stesso telefono.
    """

    def test_la_marca_non_si_ripete(self):
        self.assertEqual(modelcodes._nome_visualizzato("POCO", "POCO M4 Pro"),
                         "POCO M4 Pro")
        self.assertEqual(modelcodes._nome_visualizzato("Honor", "HONOR Magic6"),
                         "HONOR Magic6")

    def test_quando_manca_davvero_si_aggiunge(self):
        self.assertEqual(modelcodes._nome_visualizzato("Samsung", "Galaxy S24"),
                         "Samsung Galaxy S24")

    def test_il_confronto_e_per_parole_intere(self):
        """«Tecno» e «TECNOPOP 5C» non sono una ripetizione: «TECNOPOP» è
        una gamma, e togliere la marca lascerebbe un nome che il catalogo
        non usa."""
        self.assertEqual(modelcodes._nome_visualizzato("Tecno", "TECNOPOP 5C"),
                         "Tecno TECNOPOP 5C")

    def test_campi_vuoti(self):
        self.assertEqual(modelcodes._nome_visualizzato("", "Galaxy S24"), "Galaxy S24")
        self.assertEqual(modelcodes._nome_visualizzato("Samsung", ""), "Samsung")

    def test_la_chiave_regge_comunque_un_nome_duplicato(self):
        """La sorgente è corretta, ma la stessa forma può arrivare da
        un'altra fonte: la chiave è il punto in cui due grafie dello stesso
        telefono devono convergere, e deve reggere da sola."""
        self.assertEqual(extract.device_key(C.XIAOMI, "POCO POCO M4 Pro"),
                         extract.device_key(C.XIAOMI, "POCO M4 Pro"))
        self.assertEqual(extract.device_key(C.OTHER, "Nokia Nokia C32"),
                         extract.device_key(C.OTHER, "Nokia C32"))

    def test_una_parola_ripetuta_non_di_fila_resta(self):
        """Si toglie solo la ripetizione IMMEDIATA: «Pro» due volte in un
        nome lungo può essere legittimo."""
        self.assertNotEqual(extract.device_key(C.OTHER, "Pad Pro 11 Pro"),
                            extract.device_key(C.OTHER, "Pad Pro 11"))


class TestParentesiNelNome(unittest.TestCase):
    """TUTTI I NOTHING PHONE ERANO LO STESSO TELEFONO.

    La regola nata per «Oppo A6x (CPH2819)» — buttare via ciò che sta fra
    parentesi — cancellava anche il numero di «Nothing Phone (2)», e con
    lui la differenza fra (1), (2), (3a) e (4b). Cercando «Phone (2)» si
    otteneva la scheda del Phone (1): un altro telefono, con un'altra
    versione, e nessun segno che fosse successo.
    """

    def test_il_numero_di_gamma_resta(self):
        self.assertNotEqual(modelcodes._normalize_name("Nothing Phone (2)"),
                            modelcodes._normalize_name("Nothing Phone (1)"))

    def test_il_codice_tecnico_se_ne_va_ancora(self):
        """Era la ragione della regola, e non va persa: «Oppo A6x
        (CPH2819)» e «OPPO A6x» sono lo stesso telefono."""
        self.assertEqual(modelcodes._normalize_name("Oppo A6x (CPH2819)"),
                         modelcodes._normalize_name("OPPO A6x"))
        self.assertEqual(modelcodes._normalize_name("Galaxy A54 (SM-A546B)"),
                         modelcodes._normalize_name("Galaxy A54"))

    def test_vale_per_chiunque_usi_le_parentesi_come_numero(self):
        self.assertNotEqual(modelcodes._normalize_name("CMF Phone (2) Pro"),
                            modelcodes._normalize_name("CMF Phone (1) Pro"))


class TestLaMarcaChiestaEUnVincolo(unittest.TestCase):
    """Una ricerca su OnePlus rispondeva con un Redmi.

    Le fonti si confrontano su un nome normalizzato, e la normalizzazione
    toglie il prefisso della marca perché «Samsung Galaxy S24» e «Galaxy
    S24» sono lo stesso telefono. L'effetto collaterale è che «OnePlus Pad
    Go» diventa «pad go», che è contenuto in «Redmi Pad Go Russia»: il
    catalogo Xiaomi rispondeva, e con una versione, quindi vinceva.

    Un modello di un'altra marca non è un risultato parziale — è la
    risposta sbagliata.
    """

    def test_scarta_chi_non_e_della_marca_chiesta(self):
        items = [
            sources.RawItem(title="Redmi Pad Go Russia", brand=C.XIAOMI,
                            device="Redmi Pad Go Russia", build="V10.2"),
            sources.RawItem(title="OnePlus Pad Go", brand=C.OPPO,
                            device="OnePlus Pad Go"),
        ]
        tenuti = sources._scarta_marca_sbagliata(items, C.OPPO)
        self.assertEqual([i.device for i in tenuti], ["OnePlus Pad Go"])

    def test_senza_marca_nella_domanda_non_si_scarta_niente(self):
        """«a15» è insieme un OPPO A15 e un Galaxy A15: lì mostrarle
        entrambe è la risposta giusta."""
        items = [
            sources.RawItem(title="OPPO A15", brand=C.OPPO, device="OPPO A15"),
            sources.RawItem(title="Galaxy A15", brand=C.SAMSUNG, device="Galaxy A15"),
        ]
        self.assertEqual(len(sources._scarta_marca_sbagliata(items, None)), 2)

    def test_un_risultato_senza_marca_resta(self):
        """Non tutte le fonti dichiarano il brand: toglierlo per assenza
        significherebbe scartare dati buoni."""
        items = [sources.RawItem(title="Qualcosa", device="Qualcosa")]
        self.assertEqual(len(sources._scarta_marca_sbagliata(items, C.OPPO)), 1)


class TestMarcaCinese(unittest.TestCase):
    """IL DATASET È CINESE PRIMA CHE INGLESE.

    MobileModels nasce in Cina e scrive le marche nella loro lingua:
    `SM-G9900` è di 三星, `DE2117` di 一加. Su 3577 nomi di marca distinti,
    sedici sono in caratteri cinesi e coprono da soli oltre quattromila
    codici.

    E soprattutto: una marca NON riconosciuta deve tacere, non rispondere
    «Altri brand». Questa funzione decide prima delle regole sul formato
    del codice, e un «Altri brand» qui cancellava il riconoscimento di
    `SM-…` come Samsung — misurato, Samsung era sceso al 75% di coerenza
    e Redmi al 13%.
    """

    def test_i_nomi_cinesi_sono_riconosciuti(self):
        self.assertEqual(sources.gruppo_di_marca("三星"), C.SAMSUNG)
        self.assertEqual(sources.gruppo_di_marca("一加"), C.OPPO)
        self.assertEqual(sources.gruppo_di_marca("小米"), C.XIAOMI)
        self.assertEqual(sources.gruppo_di_marca("华为"), C.HUAWEI)
        self.assertEqual(sources.gruppo_di_marca("荣耀"), C.HUAWEI)

    def test_una_marca_sconosciuta_tace(self):
        """È la differenza fra lasciar decidere a chi viene dopo e
        cancellarne il lavoro."""
        self.assertIsNone(sources.gruppo_di_marca("ZTE"))
        self.assertIsNone(sources.gruppo_di_marca("Hisense"))

    def test_le_marche_del_gruppo_altri_sono_elencate(self):
        """«Altri brand» resta una risposta, ma dichiarata."""
        self.assertEqual(sources.gruppo_di_marca("Nothing"), C.OTHER)
        self.assertEqual(sources.gruppo_di_marca("Nokia"), C.OTHER)

    def test_il_formato_del_codice_resta_l_ultima_parola(self):
        """Se il dataset tace, le regole sul formato devono ancora valere."""
        self.assertEqual(sources.brand_from_code("SM-Z999X"), C.SAMSUNG)


class TestSottomarcaNellaChiave(unittest.TestCase):
    """I dataset scrivono lo stesso telefono in tutti i modi: «Nord CE 3
    Lite», «OnePlus Nord CE 3 Lite», «一加 Nord CE 3 Lite». Ogni grafia una
    chiave, ogni chiave una scheda.

    Toglierla sempre però fonderebbe «OPPO A5» e «realme A5». La soglia
    non è scelta a occhio: contando sul dataset intero, le radici contese
    fra due sotto-marche sono il 2-3% e sono quasi tutte di uno o due
    caratteri.
    """

    def test_le_grafie_convergono(self):
        atteso = [
            (C.OPPO, "OnePlus Nord CE 3 Lite", "Nord CE 3 Lite"),
            (C.VIVO, "Vivo X100 Pro", "X100 Pro"),
            (C.OPPO, "realme narzo 50A Prime", "Narzo 50A Prime"),
            (C.HUAWEI, "Huawei P20 Pro", "P20 Pro"),
            (C.XIAOMI, "Xiaomi Redmi 3", "Redmi 3"),
        ]
        for gruppo, a, b in atteso:
            with self.subTest(nome=a):
                self.assertEqual(extract.device_key(gruppo, a),
                                 extract.device_key(gruppo, b))

    def test_le_sottomarche_non_si_fondono_sui_nomi_corti(self):
        """È il caso che la soglia protegge: «A5» da solo non identifica
        niente, e senza la marca «OPPO A5» diventerebbe «realme A5»."""
        self.assertNotEqual(extract.device_key(C.OPPO, "OPPO A5"),
                            extract.device_key(C.OPPO, "realme A5"))
        self.assertNotEqual(extract.device_key(C.XIAOMI, "Xiaomi 14"),
                            extract.device_key(C.XIAOMI, "Redmi 14"))

    def test_una_chiave_non_diventa_mai_vuota(self):
        for nome in ("OnePlus", "Xiaomi", "vivo", "Huawei"):
            with self.subTest(nome=nome):
                chiave = extract.device_key(C.OPPO, nome)
                self.assertTrue(chiave.split("|")[1])


class TestVarianteSamsung(unittest.TestCase):
    """Senza un mercato indicato si sceglie l'internazionale, e lo si dice.

    Prima vinceva l'ordine del dataset: cercando «samsung s24» rispondeva
    la build cinese e cercando `SM-S921B` quella europea. Due risposte per
    lo stesso telefono, e la differenza non spiegata da nessuna parte."""

    def test_l_internazionale_viene_prima(self):
        codici = ["SM-S9210", "SM-S921U", "SM-S921N", "SM-S921B"]
        ordinati = sorted(codici, key=sources._rango_mercato_samsung)
        self.assertEqual(ordinati[0], "SM-S921B")

    def test_anche_la_vecchia_sigla_internazionale(self):
        self.assertLess(sources._rango_mercato_samsung("SM-A325F"),
                        sources._rango_mercato_samsung("SM-A3250"))

    def test_un_suffisso_sconosciuto_non_solleva(self):
        self.assertIsInstance(sources._rango_mercato_samsung("SCG25"), int)


class TestCodiceDentroLaBuild(unittest.TestCase):
    """Molti produttori scrivono il codice modello dentro il numero di
    build, ed è l'unico posto dove compare."""

    def test_oneplus(self):
        self.assertEqual(scan._codice_dal_build("CPH2653_16.0.9.402(EX01)"), "CPH2653")

    def test_samsung(self):
        self.assertEqual(scan._codice_dal_build("A325FXXSCDYB2"), "SM-A325F")

    def test_una_build_senza_codice_non_ne_inventa_uno(self):
        self.assertIsNone(scan._codice_dal_build("OS2.0.211.0.VNGMIXM"))
        self.assertIsNone(scan._codice_dal_build("AP4A.250105.002"))
        self.assertIsNone(scan._codice_dal_build(None))


class TestVarianteNelRisultato(unittest.TestCase):
    """Il codice della variante deve arrivare fino al record salvato: è ciò
    che permette di risolvere il chip in modo esatto invece di rispondere
    «Exynos oppure Snapdragon»."""

    def setUp(self):
        self.fonte = sources.Source("prova", "Fonte di prova", C.TRUST_STRUCTURED,
                                    lambda: ([], None))

    def test_il_codice_dichiarato_dalla_fonte_arriva_nel_record(self):
        raw = sources.RawItem(title="Galaxy S24 — build S921BXXSGDZG1", brand=C.SAMSUNG,
                              device="Galaxy S24", model_code="SM-S921B",
                              build="S921BXXSGDZG1")
        self.assertEqual(scan.normalize(raw, self.fonte)["model_code"], "SM-S921B")

    def test_senza_dichiarazione_si_legge_dalla_build(self):
        raw = sources.RawItem(title="OnePlus 13", brand=C.OPPO, device="OnePlus 13",
                              build="CPH2653_16.0.9.402(EX01)")
        self.assertEqual(scan.normalize(raw, self.fonte)["model_code"], "CPH2653")

    def test_il_codice_non_entra_nel_testo_analizzato(self):
        """`RawItem.text` è ciò che rileggono gli estrattori, e un codice
        modello ha la forma di un numero di build: infilarcelo dentro
        avrebbe creato build inventate."""
        raw = sources.RawItem(title="Galaxy S24", model_code="SM-S921B")
        self.assertNotIn("SM-S921B", raw.text)


class TestSiPreferisceLaFormaCheHaIlFirmware(BaseCodici):
    """Fra le forme equivalenti vince quella che risponde con una versione,
    non la prima che risponde qualcosa. Cercando `23129RAA4G` il catalogo
    dei dispositivi certificati riconosceva il codice e ci si fermava lì,
    con un modello senza versione, mentre la forma successiva avrebbe
    trovato la build reale."""

    def setUp(self):
        super().setUp()
        self._ordine = sources._lookup_order

        def solo_esistenza(nome):
            if nome.upper() != "23129RAA4G":
                return []
            return [sources.RawItem(title=f"{nome} — dispositivo certificato",
                                    brand=C.XIAOMI, device="Redmi Note 13",
                                    size_info="catalogo di prova")]

        def con_firmware(nome):
            if nome != "Redmi Note 13":
                return []
            return [sources.RawItem(title="Redmi Note 13 — OS2.0.211.0.VNGMIXM",
                                    brand=C.XIAOMI, device="Redmi Note 13",
                                    build="OS2.0.211.0.VNGMIXM",
                                    size_info="catalogo firmware di prova")]

        sources._lookup_order = lambda brand: [
            sources.StructuredLookup(C.XIAOMI, solo_esistenza, "basso", "certificati"),
            sources.StructuredLookup(C.XIAOMI, con_firmware, "basso", "firmware"),
        ]

    def tearDown(self):
        sources._lookup_order = self._ordine
        super().tearDown()

    def test_vince_la_forma_con_la_versione(self):
        items, _nota = scan._lookup_structured_for("23129RAA4G")
        self.assertTrue(items)
        self.assertEqual(items[0]["build"], "OS2.0.211.0.VNGMIXM")

    def test_senza_nessuna_versione_resta_la_conferma_del_modello(self):
        """Un risultato senza firmware non va buttato: dice comunque che il
        telefono esiste, ed è un'informazione."""
        sources._lookup_order = lambda brand: [
            sources.StructuredLookup(
                C.XIAOMI,
                lambda nome: ([sources.RawItem(title=f"{nome} — certificato",
                                               brand=C.XIAOMI, device="Redmi Note 13")]
                              if nome.upper() == "23129RAA4G" else []),
                "basso", "certificati"),
        ]
        items, _nota = scan._lookup_structured_for("23129RAA4G")
        self.assertTrue(items)
        self.assertEqual(items[0]["device_model"], "Redmi Note 13")


class TestNomeEsattoBatteLaSottostringa(unittest.TestCase):
    """«Redmi Note 13» rispondeva «Redmi Note 13 Pro+ 5G Taiwan»: un altro
    telefono, con un altro chip e un altro firmware, scelto dall'ordine del
    catalogo."""

    def setUp(self):
        self._fetch = sources.fetch_xiaomi
        sources.fetch_xiaomi = lambda: ([
            sources.RawItem(title="a", device="Redmi Note 13 Pro+ 5G Taiwan"),
            sources.RawItem(title="b", device="Redmi Note 13 Global"),
            sources.RawItem(title="c", device="Redmi Note 13"),
        ], None)

    def tearDown(self):
        sources.fetch_xiaomi = self._fetch

    def test_l_esatto_vince(self):
        trovati = sources._lookup_xiaomi("Redmi Note 13")
        self.assertEqual(trovati[0].device, "Redmi Note 13")

    def test_senza_esatto_vince_il_piu_vicino(self):
        sources.fetch_xiaomi = lambda: ([
            sources.RawItem(title="a", device="Redmi Note 13 Pro+ 5G Taiwan"),
            sources.RawItem(title="b", device="Redmi Note 13 Global"),
        ], None)
        trovati = sources._lookup_xiaomi("Redmi Note 13")
        self.assertEqual(trovati[0].device, "Redmi Note 13 Global")


class TestCodiceSconosciutoNonDiventaUnDispositivo(unittest.TestCase):
    """Fissare il modello al testo digitato rende tracciabile un telefono di
    nicchia chiamato per nome. Applicato a un codice che nessun dataset
    conosce, crea invece un dispositivo che si chiama «Xt2341-3», separato
    dal «Moto G14» che è lo stesso telefono."""

    def setUp(self):
        self._rss = sources.rss_items
        self._resolve = modelcodes.resolve
        modelcodes.resolve = lambda codice: []
        sources.rss_items = lambda urls, brand, size_info, limit=None, timeout=None: (
            [sources.RawItem(title="Moto G14 gets the July 2026 security patch",
                             link="https://x.test/1", published="2026-07-10")], None)

    def tearDown(self):
        sources.rss_items = self._rss
        modelcodes.resolve = self._resolve

    def test_il_codice_non_diventa_il_nome_del_modello(self):
        items, _errore = sources.search_model_live("XT2341-3")
        self.assertTrue(items)
        self.assertNotEqual((items[0].device or "").lower(), "xt2341-3")

    def test_un_nome_qualunque_resta_invece_il_modello(self):
        items, _errore = sources.search_model_live("Telefono Ignoto 7")
        self.assertTrue(items)
        self.assertEqual(items[0].device, "Telefono Ignoto 7")


class TestEtichettaVersione(unittest.TestCase):
    """`Android None` era una stringa letterale, visibile in scheda
    dispositivo: la versione dedotta dalla skin veniva riscritta DOPO che
    la regola sulle fonti rumorose l'aveva appena tolta."""

    def test_niente_android_none(self):
        fonte = sources.Source("news", "Ricerca di prova", C.TRUST_NOISY,
                               lambda: ([], None))
        raw = sources.RawItem(
            title="Oppo Reno 14 riceve ColorOS 15 in rollout",
            brand=C.OPPO, device="Oppo Reno 14")
        item = scan.normalize(raw, fonte)
        self.assertNotIn("None", item["os_version"] or "")


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)


class TestQuandoEUscita(unittest.TestCase):
    """L'endpoint FOTA di Samsung non pubblica NESSUNA data — verificato
    leggendo il suo XML: c'è la build, c'è il peso del pacchetto, la data
    no. Ma le ultime tre lettere della build la contengono.

    La mappatura è stata verificata sui dati e non presa da un forum: su
    dieci modelli europei interrogati, otto cadono al mese scorso — dove
    deve stare il firmware corrente — e il Galaxy A32 decodifica al marzo
    2021, che è esattamente il modello che il progetto sa fermo da anni.
    """

    def test_legge_anno_e_mese(self):
        self.assertEqual(extract.mese_da_build_samsung("S928BXXS6DZG1"), (2026, 7))
        self.assertEqual(extract.mese_da_build_samsung("A325FXXU1AUCC"), (2021, 3))

    def test_forma_leggibile(self):
        self.assertEqual(extract.mese_leggibile("S928BXXS6DZG1"), "luglio 2026")

    def test_non_inventa_date_da_build_di_altre_marche(self):
        for build in ("OS2.0.211.0.VNGMIXM", "AP4A.250105.002",
                      "CPH2653_16.0.9.402", "", None):
            with self.subTest(build=build):
                self.assertIsNone(extract.mese_leggibile(build or ""))

    def test_lettere_fuori_scala_non_producono_una_data(self):
        """Meglio nessuna data che una sbagliata: è la regola del progetto."""
        self.assertIsNone(extract.mese_da_build_samsung("S928BXXS6D01"))


class TestIdentitaDalCodice(BaseCodici):
    """LA RADICE DI META' DEI DIFETTI DI QUESTE VERSIONI.

    L'identità del dispositivo si costruisce sul NOME, ma le fonti
    identificano i telefoni per CODICE — e il 17% dei codici ha più di un
    nome: `CPH2423` è insieme «一加 10R», «OnePlus 10R» e «OnePlus 10R 5G».
    Lo stesso telefono diventava tre dispositivi.

    Normalizzare le grafie una per una è la partita che non si vince: le
    grafie sono un dato della realtà. Quando il codice c'è, decide lui.
    """

    def test_un_codice_da_sempre_lo_stesso_nome(self):
        self.assertEqual(modelcodes.nome_canonico("SM-S921B"), "Galaxy S24")
        self.assertEqual(modelcodes.nome_canonico("PCET00"), "OPPO A9x")

    def test_il_nome_cinese_non_vince_su_quello_latino(self):
        modelcodes._memory_cache["ZZTEST1"] = ["一加 10R", "OnePlus 10R 5G", "OnePlus 10R"]
        try:
            self.assertEqual(modelcodes.nome_canonico("ZZTEST1"), "OnePlus 10R")
        finally:
            modelcodes._memory_cache.pop("ZZTEST1", None)

    def test_un_codice_ripetuto_come_nome_perde_sempre(self):
        modelcodes._memory_cache["ZZTEST2"] = ["Oppo ZZTEST2", "OPPO A57s"]
        try:
            self.assertEqual(modelcodes.nome_canonico("ZZTEST2"), "OPPO A57s")
        finally:
            modelcodes._memory_cache.pop("ZZTEST2", None)

    def test_codice_sconosciuto(self):
        self.assertIsNone(modelcodes.nome_canonico("ZZ-INESISTENTE"))

    def test_la_scelta_e_deterministica(self):
        """Due esecuzioni non devono dare due nomi diversi: sarebbero due
        dispositivi."""
        self.assertEqual(modelcodes.nome_canonico("SM-S921B"),
                         modelcodes.nome_canonico("SM-S921B"))

    def test_i_nomi_gemelli_si_dichiarano(self):
        """Quando un codice ha PIÙ di un nome commerciale vero, la scelta
        di `nome_canonico` è necessaria (una chiave sola per dispositivo)
        ma resta una scelta: il modello mostrato non è l'unico nome vero
        per quel codice.

        Misurato in produzione: `RMX3933` è insieme «C61», «Note 60»,
        «Note 60s» e «NARZO N61» — la stessa piattaforma venduta con nomi
        diversi in mercati diversi — e la ricerca rispondeva solo «C61»,
        senza nessun segnale che non fosse l'unico nome possibile. Chi ha
        in mano un «Note 60» leggeva un nome diverso dal proprio e
        concludeva che l'app avesse sbagliato telefono.

        `_nomi_gemelli` (in `web/main.py`) è la funzione che dichiara gli
        altri nomi veri, non indovinati per somiglianza di stringa come fa
        `_forse_cercavi`, ma letti dalla stessa riga del dataset."""
        from web import main as M

        modelcodes._memory_cache["ZZ9999"] = ["Test Alpha", "Test Beta", "Test Gamma"]
        try:
            gemelli = M._nomi_gemelli("ZZ9999", "Test Alpha")
            self.assertIn("Test Beta", gemelli)
            self.assertIn("Test Gamma", gemelli)
            self.assertNotIn("Test Alpha", gemelli,
                             "il nome già scelto non è un «gemello» di se stesso")
        finally:
            modelcodes._memory_cache.pop("ZZ9999", None)

    def test_marca_piu_lo_stesso_nome_non_e_un_gemello_in_piu(self):
        """Segnalato dall'utente: `RMX3933` risolve anche a «realme Note
        60», che è «Note 60» col produttore scritto davanti — non un
        telefono in più, la stessa identica forma commerciale. Le due
        forme si uniscono in una sola voce (la più corta); «Note 60s»,
        un telefono regionale VERO e diverso, resta invece una voce a
        sé."""
        from web import main as M

        modelcodes._memory_cache["ZZ5432"] = [
            "Note 60", "realme Note 60", "Note 60s", "NARZO N61"]
        try:
            gemelli = M._nomi_gemelli("ZZ5432", "Note 60s")
            self.assertIn("Note 60", gemelli)
            self.assertNotIn("realme Note 60", gemelli)
            self.assertIn("NARZO N61", gemelli)
            self.assertEqual(len(gemelli), 2)
        finally:
            modelcodes._memory_cache.pop("ZZ5432", None)

    def test_la_marca_scritta_davanti_al_nome_mostrato_non_e_un_gemello(self):
        """Se il nome mostrato È «Note 60», anche «realme Note 60» va
        escluso dai gemelli — non solo l'esatto «Note 60»."""
        from web import main as M

        modelcodes._memory_cache["ZZ5431"] = [
            "Note 60", "realme Note 60", "Note 60s"]
        try:
            gemelli = M._nomi_gemelli("ZZ5431", "Note 60")
            self.assertNotIn("realme Note 60", gemelli)
            self.assertEqual(gemelli, ["Note 60s"])
        finally:
            modelcodes._memory_cache.pop("ZZ5431", None)

    def test_un_codice_ripetuto_non_conta_come_nome_gemello(self):
        """Il codice scritto una seconda volta (`_e_il_codice`) non è un
        nome commerciale: proporlo come alternativa sarebbe proporre il
        codice stesso travestito da nome."""
        from web import main as M

        modelcodes._memory_cache["ZZ8888"] = ["ZZ8888", "Test Solo"]
        try:
            gemelli = M._nomi_gemelli("ZZ8888", "Test Solo")
            self.assertEqual(gemelli, [])
        finally:
            modelcodes._memory_cache.pop("ZZ8888", None)

    def test_i_gemelli_si_trovano_anche_con_la_marca_davanti(self):
        """«realme RMX3933» non ha la forma di un codice (la marca
        davanti lo nasconde): va tolta prima di riprovare, o si finisce
        per guardare i gemelli del codice del NOME trovato (C61 →
        RMX3930) invece di quelli del codice scritto (RMX3933) — due
        codici imparentati ma diversi. Misurato: prima di questo
        controllo `_codici_del_risultato` restituiva RMX3930."""
        from web import main as M

        modelcodes._memory_cache["ZZ6666"] = ["Test Marca", "Test Gemello"]
        try:
            gemelli = M._nomi_gemelli("realme ZZ6666", "Test Marca")
            self.assertIn("Test Gemello", gemelli)
        finally:
            modelcodes._memory_cache.pop("ZZ6666", None)

    def test_un_solo_nome_vero_non_ha_gemelli(self):
        from web import main as M

        modelcodes._memory_cache["ZZ7777"] = ["Test Unico"]
        try:
            self.assertEqual(M._nomi_gemelli("ZZ7777", "Test Unico"), [])
        finally:
            modelcodes._memory_cache.pop("ZZ7777", None)

    def test_solo_il_codice_dichiarato_rinomina(self):
        """Un codice letto dentro una build serve al chip, non a rinominare
        il dispositivo: in una notizia quella build può appartenere a un
        altro modello citato nello stesso articolo."""
        fonte = sources.Source("prova", "Prova", C.TRUST_CURATED, lambda: ([], None))
        raw = sources.RawItem(title="Galaxy S24 Ultra riceve One UI",
                              brand=C.SAMSUNG, device="Galaxy S24 Ultra",
                              build="S921BXXU5BYG1")
        self.assertEqual(scan.normalize(raw, fonte)["device_model"], "Galaxy S24 Ultra")

    def test_la_marca_chiesta_vale_sulle_forme_derivate(self):
        """«xiaomi 14» risolveva anche al nome cinese di un realme, e quella
        forma vinceva perché aveva il firmware."""
        forme = scan.forme_equivalenti("oppo reno 14")
        for f in forme:
            marca = sources.brand_from_code(f) or extract.detect_brand(f)
            if marca:
                self.assertEqual(marca, C.OPPO, f"forma di un'altra marca: {f}")


class TestOpzioniCorrezione(unittest.TestCase):
    """`_opzioni_correzione` (web/main.py) — le forme proposte nel menu
    «Non è il nome giusto?», non sempre identiche a `_nomi_gemelli`.

    Nasce dalla segnalazione dell'utente su RMX3933: nel dataset reale
    nessuno dei nomi VERI di quel codice scrive «realme» per esteso (solo
    «NARZO N61», riconosciuto come sinonimo — vedi `core/versus.py`), e
    senza questa funzione «realme Note 60» non poteva mai comparire come
    opzione, nemmeno dopo aver risolto il bug della scheda assente."""

    def setUp(self):
        from core import aer_catalog
        aer_catalog.reset_cache()
        modelcodes._memory_cache = modelcodes._memory_cache or {}

    def tearDown(self):
        from core import aer_catalog
        aer_catalog.reset_cache()
        for codice in ("ZZ4001", "ZZ4002", "ZZ4003", "ZZ4004"):
            modelcodes._memory_cache.pop(codice, None)

    def test_aggiunge_una_forma_con_la_marca_per_ogni_nome_vero(self):
        """Nessuno dei nomi veri porta «realme» per esteso (solo il
        sinonimo NARZO): una forma sintetica va aggiunta per ciascuno —
        il nome mostrato e ogni gemello — non solo per uno a caso."""
        from web import main as M

        modelcodes._memory_cache["ZZ4001"] = [
            "Nota Test 60", "Nota Test 60s", "NARZO Nota Test"]
        gemelli = M._nomi_gemelli("ZZ4001", "Nota Test 60s")
        opzioni = M._opzioni_correzione("Nota Test 60s", gemelli, "ZZ4001")
        self.assertIn("Realme Nota Test 60s", opzioni)  # dal nome mostrato
        self.assertIn("Realme Nota Test 60", opzioni)   # da un gemello
        self.assertIn("Realme NARZO Nota Test", opzioni)  # dall'altro gemello

    def test_non_sceglie_a_caso_la_forma_piu_corta_come_unica_base(self):
        """Il bug reale segnalato dall'utente su RMX3933: prima di questo
        fix si generava UNA sola forma sintetica, scelta come la più
        corta fra tutti i nomi veri — «C61» (3 lettere) invece di «Note
        60» (7), che però è il nome con cui chi ha il telefono lo
        riconosce. Non c'è un modo di indovinare quale nome vero sia
        «quello giusto»: si generano tutte le forme, non se ne sceglie
        una sola per lunghezza."""
        from web import main as M

        modelcodes._memory_cache["ZZ4004"] = [
            "C61", "Note Test 60", "Note Test 60s", "NARZO Test N61"]
        gemelli = M._nomi_gemelli("ZZ4004", "Note Test 60s")
        opzioni = M._opzioni_correzione("Note Test 60s", gemelli, "ZZ4004")
        self.assertIn("Realme Note Test 60", opzioni,
                     "la forma riconoscibile deve esserci, non solo quella più corta")

    def test_non_duplica_una_forma_che_gia_scrive_la_marca(self):
        """Se la forma stessa porta già la marca in testa, `con_marca` la
        restituisce invariata: non deve comparire come doppione di se
        stessa."""
        from web import main as M

        modelcodes._memory_cache["ZZ4002"] = ["NARZO Nota Prova"]
        opzioni = M._opzioni_correzione("Realme Nota Prova", [], "ZZ4002")
        self.assertEqual(opzioni, [])

    def test_senza_marca_riconosciuta_le_opzioni_restano_i_soli_gemelli(self):
        """Nessuna voce AER e nessun nome vero con una marca che
        `versus.marca_scoperta` copre: niente forma sintetica inventata."""
        from web import main as M

        modelcodes._memory_cache["ZZ4003"] = ["Galaxy Prova", "Galaxy Prova Plus"]
        gemelli = M._nomi_gemelli("ZZ4003", "Galaxy Prova")
        opzioni = M._opzioni_correzione("Galaxy Prova", gemelli, "ZZ4003")
        self.assertEqual(opzioni, gemelli)

    def test_senza_codice_le_opzioni_restano_i_soli_gemelli(self):
        """Senza un codice a cui agganciare la marca, non si cerca
        nemmeno: comportamento invariato rispetto a prima di questo fix."""
        from web import main as M

        self.assertEqual(M._opzioni_correzione("Nota Test", ["Gemello"], ""), ["Gemello"])
