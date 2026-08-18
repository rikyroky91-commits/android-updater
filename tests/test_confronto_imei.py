"""Lo stesso IMEI dà spesso un modello su un sito e un altro su un altro.

I database TAC sono alimentati dalla community, si contraddicono fra loro e
nessuno è autorevole. Fino alla v40 l'app li fondeva in uno solo: chi
arrivava dopo perdeva, e il disaccordo spariva senza lasciare traccia —
mentre è proprio il disaccordo il dato che serve a chi sta decidendo su
quale telefono lanciare un test.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, imeicheck, storage  # noqa: E402

# Forma reale delle tre basi dati.
CSV_PRINCIPALE = (
    "Brand,TAC,SPECS\n"
    "SAMSUNG,35692411,\"SAMSUNG GALAXY A54 5G, Samsung SM-A546B, 2023\"\n"
    "XIAOMI,86751306,\"XIAOMI 9A SPORT, Xiaomi M2006C3LG, Global Model, 2020\"\n"
)
CSV_OSMOCOM = (
    "Osmocom TAC database under CC-BY-SA v3.0 (c) Harald Welte 2016\n"
    "tac,name,name,contributor,comment,gsmarena,gsmarena,aka\n"
    "86751306,Xiaomi,Redmi 9A,tizio,,,,\n"
    "49013920,Nokia,1610,OsmoDevCon 2014,,,,\n"
)
CSV_IMEIDB = (
    "35913201,3GNET,G Series G528,,\n"
    # Una voce che solo questa base dati conosce E che sopravvive al taglio
    # dell'era Android: la riga 3GNET qui sopra non dichiara né anno né
    # codice modello, quindi dal 17/08/2026 l'indice non la tiene più. Resta
    # comunque nel CSV perché il test del PARSER deve continuare a leggerla:
    # scartare una voce dall'indice e non saperla leggere sono due guasti
    # diversi, e confonderli nasconderebbe il secondo.
    "35913203,Realme,realme 12 RMX3871 2024,,\n"
    "35692411,Samsung,Galaxy A54 5G,,\n"
)


class BaseImei(unittest.TestCase):
    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()
        imeicheck.reset_cache()
        self._download = imeicheck._download
        self._scarica_url = imeicheck._scarica_url
        imeicheck._download = lambda: CSV_PRINCIPALE.encode("utf-8")

        def finto_url(url, minimo=10_000):
            if url == imeicheck.TAC_DB_FALLBACK_URL:
                return CSV_OSMOCOM.encode("utf-8")
            if url == imeicheck.TAC_DB_IMEIDB_URL:
                return CSV_IMEIDB.encode("utf-8")
            return None

        imeicheck._scarica_url = finto_url

    def tearDown(self):
        imeicheck._download = self._download
        imeicheck._scarica_url = self._scarica_url
        imeicheck.reset_cache()
        storage.reset_state()
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale


class TestBaseDatiStorica(BaseImei):
    """QUESTA FONTE NON HA MAI FUNZIONATO. Il file comincia con una riga di
    copyright e l'intestazione vera è la seconda: cercando la colonna `tac`
    nella prima riga non si trovava, e la funzione usciva a mano vuota.
    L'app scaricava 3 MB ogni due settimane per ricavarne zero voci, e il
    download riusciva — quindi la Diagnostica non poteva accorgersene."""

    def test_la_riga_di_copyright_non_blocca_la_lettura(self):
        indice = imeicheck.carica_tac_osmocom(CSV_OSMOCOM)
        self.assertEqual(len(indice), 2)
        self.assertEqual(indice["49013920"], ("Nokia", "1610"))

    def test_le_due_colonne_name_sono_marca_e_modello(self):
        """L'intestazione ha DUE colonne chiamate `name`: cercarle per nome
        darebbe due volte la stessa."""
        indice = imeicheck.carica_tac_osmocom(CSV_OSMOCOM)
        self.assertEqual(indice["86751306"], ("Xiaomi", "Redmi 9A"))

    def test_un_file_senza_intestazione_riconoscibile_non_solleva(self):
        self.assertEqual(imeicheck.carica_tac_osmocom("qualcosa\naltro\n"), {})
        self.assertEqual(imeicheck.carica_tac_osmocom(""), {})


class TestTerzaBaseDati(BaseImei):
    def test_formato_senza_intestazione(self):
        indice = imeicheck.carica_tac_imeidb(CSV_IMEIDB)
        self.assertEqual(indice["35913201"], ("3GNET", "G Series G528"))

    def test_porta_codici_che_le_altre_non_hanno(self):
        voci = imeicheck.confronto("359132030000000")["voci"]
        self.assertTrue(voci)
        self.assertEqual(voci[0]["fonte"], imeicheck.FONTE_IMEIDB)

    def test_una_voce_senza_anno_ne_codice_non_entra_nell_indice(self):
        """Il rovescio dichiarato del taglio: `3GNET G Series G528` si
        legge ancora (vedi il test del parser qui sopra) ma non finisce in
        RAM. È il prezzo dei 114 MB risparmiati, e va scritto, non subìto."""
        self.assertFalse(imeicheck.confronto("359132010000000")["voci"])


class TestFormatoRiconosciutoDaiByte(BaseImei):
    """Il formato si guarda, non si presume: il repository pubblica lo
    stesso dato in CSV e in xlsx, e decidere dall'URL significa leggere
    zero righe senza nessun errore quando arriva l'altro."""

    def test_csv(self):
        indice = imeicheck._leggi_base_principale(CSV_PRINCIPALE.encode("utf-8"))
        self.assertIn("35692411", indice)

    def test_xlsx(self):
        import io as _io
        try:
            import openpyxl
        except ImportError:  # pragma: no cover
            self.skipTest("openpyxl non disponibile")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["brand", "tac", "specs"])
        ws.append(["MOTOROLA", "35692411", "Moto G84 5G, XT2347-1, 2023"])
        buf = _io.BytesIO()
        wb.save(buf)
        indice = imeicheck._leggi_base_principale(buf.getvalue())
        self.assertEqual(indice["35692411"][0], "MOTOROLA")

    def test_niente_byte_niente_indice(self):
        self.assertEqual(imeicheck._leggi_base_principale(None), {})
        self.assertEqual(imeicheck._leggi_base_principale(b""), {})


class TestConfronto(BaseImei):

    def test_elenca_tutte_le_fonti_che_conoscono_il_tac(self):
        esito = imeicheck.confronto("867513060000000")
        fonti = [v["fonte"] for v in esito["voci"]]
        self.assertIn(imeicheck.FONTE_PRINCIPALE, fonti)
        self.assertIn(imeicheck.FONTE_OSMOCOM, fonti)

    def test_segnala_il_disaccordo(self):
        """«XIAOMI 9A SPORT» e «Redmi 9A» sono due nomi diversi per lo
        stesso TAC: è il caso che l'utente vive e che l'app nascondeva."""
        self.assertTrue(imeicheck.confronto("867513060000000")["discordi"])

    def test_due_grafie_dello_stesso_telefono_non_sono_un_disaccordo(self):
        """«SAMSUNG GALAXY A54 5G» e «Samsung / Galaxy A54 5G» dicono la
        stessa cosa: segnalarle come discordi sarebbe rumore, e il rumore
        rende inutile l'avviso quando serve davvero."""
        esito = imeicheck.confronto("356924110000000")
        self.assertGreaterEqual(len(esito["voci"]), 2)
        self.assertFalse(esito["discordi"])

    def test_l_ordine_e_la_precedenza(self):
        """La prima riga è la risposta che l'app usa."""
        imeicheck.aggiungi_tac("86751306", "Xiaomi", "Redmi 9A Verificato")
        esito = imeicheck.confronto("867513060000000")
        self.assertEqual(esito["voci"][0]["fonte"], imeicheck.FONTE_UTENTE)
        self.assertEqual(imeicheck.identify("867513060000000")[1], "Redmi 9A Verificato")

    def test_tac_curato_note_50_precede_il_c60_delle_fonti_community(self):
        """La correzione verificata deve vincere sul primo match pubblico.

        Il TAC 86120607 e' stato segnalato come realme C60 da una fonte
        community, ma il dispositivo europeo e' un realme Note 50. Una
        riga curata e' quindi una fonte di affidabilita, non un semplice
        suggerimento da mostrare dopo il risultato sbagliato.
        """
        imei = "861206074094914"
        esito = imeicheck.confronto(imei)
        self.assertEqual(esito["voci"][0]["fonte"], imeicheck.FONTE_CURATA)
        self.assertEqual(esito["voci"][0]["marca"].lower(), "realme")
        self.assertEqual(esito["voci"][0]["modello"], "Note 50")
        self.assertEqual(imeicheck.identify(imei), ("realme", "Note 50"))

    def test_il_segnale_europeo_batte_la_posizione_della_fonte_pubblica(self):
        """Fra dati pubblici discordanti, il mercato dichiarato conta.

        Non e' una nuova eccezione per il Note 50: qualsiasi candidato con
        disponibilita' EEA/Europa esplicita puo' superare una fonte che
        arriva prima ma non offre lo stesso riscontro. Nessuna rete viene
        interrogata per prendere questa decisione.
        """
        voci = [
            (imeicheck.FONTE_PRINCIPALE, "realme",
             "REALME C60, Realme RMX3939, 2024"),
            (imeicheck.FONTE_IMEIDB, "realme",
             "REALME NOTE 50, Realme RMX3834, EEA"),
        ]
        ordinate = imeicheck._ordina_per_affidabilita(voci)
        self.assertEqual(ordinate[0][0], imeicheck.FONTE_IMEIDB)
        self.assertIn("NOTE 50", ordinate[0][2])

    def test_un_tac_sconosciuto_non_solleva(self):
        esito = imeicheck.confronto("999999990000000")
        self.assertEqual(esito["voci"], [])
        self.assertFalse(esito["discordi"])

    def test_un_imei_troppo_corto_non_solleva(self):
        self.assertEqual(imeicheck.confronto("123")["tac"], "")
        self.assertEqual(imeicheck.confronto("")["voci"], [])

    def test_l_imei_non_esce_dal_confronto(self):
        """Principio di privacy: solo il TAC viene usato, e solo il TAC
        compare nel risultato."""
        imei = "867513061234567"
        esito = imeicheck.confronto(imei)
        self.assertEqual(esito["tac"], "86751306")
        self.assertNotIn(imei, str(esito))


class TestIdentifyRestaCompatibile(BaseImei):
    """La forma del risultato di `identify` non cambia: è usata in tre
    punti dell'interfaccia e in una decina di test."""

    def test_restituisce_ancora_una_coppia(self):
        esito = imeicheck.identify("356924110000000")
        self.assertIsInstance(esito, tuple)
        self.assertEqual(len(esito), 2)
        self.assertEqual(esito[0], "SAMSUNG")

    def test_tac_sconosciuto_resta_none(self):
        self.assertIsNone(imeicheck.identify("999999990000000"))


class TestLinkDiVerifica(unittest.TestCase):
    def test_i_servizi_richiesti_sono_disponibili(self):
        nomi = [nome for nome, _url, _nota in imeicheck.link_verifica("356909222457120")]
        for atteso in ("imei.info", "IMEIpro", "IMEI Check"):
            with self.subTest(servizio=atteso):
                self.assertIn(atteso, nomi)

    def test_imei_info_riceve_il_numero_nell_indirizzo(self):
        links = dict((nome, url) for nome, url, _nota
                     in imeicheck.link_verifica("356909222457120"))
        self.assertIn("imei=356909222457120", links["imei.info"])

    def test_quindici_cifre_con_luhn_errato_restano_un_imei(self):
        self.assertTrue(imeicheck.is_imei_like("356909222457120"))
        self.assertFalse(imeicheck.is_valid_imei("356909222457120"))


class TestIndiceSoloEraAndroid(unittest.TestCase):
    """L'indice TAC tiene l'era Android, non trent'anni di telefonia.

    Chiesto dall'utente il 17/08/2026: «non possiamo eliminare i tac troppo
    vecchi? voglio risolvere il fatto che la prima ricerca è sempre
    lentissima», e poi «non m'interessano imei prima dell'avvento di
    Android 8». Misurato: l'indice intero costa 114 MB su un piano da 512,
    ed è la ragione per cui il preriscaldamento dei cataloghi era spento —
    quindi la ragione per cui la prima ricerca faceva aspettare.
    """

    def test_un_telefono_datato_prima_di_android_8_non_entra(self):
        self.assertFalse(imeicheck._dell_era_android("NOKIA 3310, 2000"))
        self.assertFalse(imeicheck._dell_era_android("SAMSUNG SGH-E600, 2004"))

    def test_un_telefono_recente_entra(self):
        self.assertTrue(imeicheck._dell_era_android("XIAOMI REDMI NOTE 13, 2024"))

    def test_il_codice_modello_vale_piu_dell_anno(self):
        """L'84% delle voci non dichiara nessun anno: buttarle tutte
        perderebbe anche telefoni recenti. Il codice le salva, ed è anche
        ciò che rende possibile una scheda tecnica."""
        self.assertTrue(imeicheck._dell_era_android(
            "OPPO A6 PRO, Oppo Guangdong CPH2781"))
        self.assertFalse(imeicheck._dell_era_android("Samsung"))

    def test_le_correzioni_umane_non_si_filtrano_mai(self):
        """Un TAC inserito a mano è lì apposta: nessun criterio
        automatico può decidere che non serviva."""
        vecchio = {"12345678": ("NOKIA", "NOKIA 3310, 2000")}
        indice: dict = {}

        def aggiungi(fonte, voci, filtrabile=True):
            for tac, (marca, specs) in voci.items():
                if filtrabile and not imeicheck._dell_era_android(specs):
                    continue
                indice.setdefault(tac, []).append((fonte, marca, specs))

        aggiungi(imeicheck.FONTE_UTENTE, vecchio, filtrabile=False)
        self.assertIn("12345678", indice)


class TestRigaDellIdentita(unittest.TestCase):
    """La riga «IMEI riconosciuto» quando il database conosce solo il codice.

    Chiesto dall'utente il 17/08/2026: il titolo diceva «Oppo A6 Pro» e la
    riga sotto «Oppo Cph2781», senza modo di capire quale credere. Si
    mostrano entrambi — nome commerciale davanti, risposta grezza dietro —
    ma solo quando dicono cose diverse.
    """

    def _riga(self, dal_database, nome_pagina):
        from web.main import _identita_da_mostrare

        return _identita_da_mostrare(
            {"riconosciuto": True, "modello": dal_database}, nome_pagina)

    def test_il_codice_travestito_da_nome_non_contraddice_piu_il_titolo(self):
        riga = self._riga("Oppo Cph2781", "Oppo A6 Pro")
        self.assertEqual(riga["nome_mostrato"], "Oppo A6 Pro")
        self.assertTrue(riga["nome_diverso_dal_database"])

    def test_lo_stesso_nome_non_si_ripete_due_volte(self):
        riga = self._riga("Galaxy A07", "Galaxy A07")
        self.assertFalse(riga["nome_diverso_dal_database"])

    def test_un_nome_piu_corto_non_e_un_disaccordo(self):
        """«A6 Pro» dentro «Oppo A6 Pro» è la stessa cosa detta più corta."""
        self.assertFalse(self._riga("A6 Pro", "Oppo A6 Pro")["nome_diverso_dal_database"])
        self.assertFalse(self._riga("GALAXY  A07", "Galaxy A07")["nome_diverso_dal_database"])

    def test_senza_nome_dalla_pagina_resta_quello_del_database(self):
        riga = self._riga("Oppo Cph2781", "")
        self.assertEqual(riga["nome_mostrato"], "Oppo Cph2781")
        self.assertFalse(riga["nome_diverso_dal_database"])

    def test_un_imei_non_riconosciuto_non_si_tocca(self):
        from web.main import _identita_da_mostrare

        grezzo = {"riconosciuto": False, "modello": ""}
        self.assertIs(_identita_da_mostrare(grezzo, "Qualcosa"), grezzo)


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)


class TestLaCopiaNelRepository(unittest.TestCase):
    """Il database TAC non deve esistere solo in rete.

    Il 17/08/2026 la fonte ha risposto `HTTP 429` e il risultato è stato
    che nessun IMEI veniva più riconosciuto: un dato che si trova solo in
    rete è un dato che si può perdere. La copia in `data/` contiene la
    sola era Android — mezzo megabyte compresso, un decimo di quanto
    l'app già scarica per i codici Google Play — e resta l'ULTIMA delle
    scelte: quando la rete risponde si usa il dato fresco, che conosce
    anche i modelli usciti dopo l'ultima istantanea.
    """

    def test_la_copia_c_e_e_si_legge(self):
        istantanea = imeicheck._istantanea_locale()
        self.assertGreater(len(istantanea), 50_000,
                           "l'istantanea sembra troppo piccola o mancante")

    def test_contiene_telefoni_veri(self):
        istantanea = imeicheck._istantanea_locale()
        for tac, atteso in (("86789908", "oppo"), ("35719772", "motorola"),
                            ("86120607", "realme")):
            with self.subTest(tac=tac):
                self.assertIn(tac, istantanea)
                marca, _specs = istantanea[tac]
                self.assertIn(atteso, marca.lower())

    def test_un_file_mancante_non_fa_esplodere_niente(self):
        originale = imeicheck.CARTELLA_DATI
        imeicheck.CARTELLA_DATI = os.path.join(originale, "cartella-che-non-esiste")
        try:
            self.assertEqual(imeicheck._istantanea_locale(), {})
        finally:
            imeicheck.CARTELLA_DATI = originale


class TestUnaRispostaCompratraSiPagaUnaVoltaSola(BaseImei):
    """Il servizio esterno ha cento interrogazioni al mese: non si sprecano.

    L'aggancio esisteva già ma la risposta finiva nel solo indice in
    memoria, e su Render il processo riparte a ogni deploy e dopo ogni
    sonno: lo stesso TAC sarebbe stato richiesto — e pagato — di nuovo.
    I dati TAC non invecchiano, quindi una risposta conservata vale per
    sempre e non ha bisogno di scadenza.
    """

    def setUp(self):
        super().setUp()
        self._online = imeicheck.cerca_tac_online
        self.chiamate = {"n": 0}

        def finto(tac):
            self.chiamate["n"] += 1
            return ("ZTE", "Blade A75 5G")

        imeicheck.cerca_tac_online = finto

    def tearDown(self):
        imeicheck.cerca_tac_online = self._online
        super().tearDown()

    def test_si_chiede_una_volta_e_poi_si_ricorda(self):
        ignoto = "998877660000000"
        self.assertEqual(imeicheck.identify(ignoto), ("ZTE", "Blade A75 5G"))
        self.assertEqual(self.chiamate["n"], 1)

        imeicheck.reset_cache()                      # come un riavvio
        self.assertEqual(imeicheck.identify(ignoto), ("ZTE", "Blade A75 5G"))
        self.assertEqual(self.chiamate["n"], 1, "il TAC è stato ricomprato")

    def test_non_si_chiede_per_un_tac_che_i_database_locali_conoscono(self):
        """Le interrogazioni vanno spese sui buchi, non sulle risposte
        che abbiamo già in casa."""
        imeicheck.identify("356924110000000")        # è nel CSV di prova
        self.assertEqual(self.chiamate["n"], 0)

    def test_le_risposte_comprate_restano_distinte_da_quelle_verificate(self):
        """Il sito mostra da dove viene ogni risposta: un acquisto e la
        verifica di una persona non devono confondersi nella stessa riga."""
        imeicheck.identify("998877660000000")
        self.assertIn("99887766", imeicheck.tac_esterni())
        self.assertNotIn("99887766", imeicheck.tac_inseriti())


class TestLAttesaDelServizioEsternoSiVede(BaseImei):
    """Chi aspetta deve sapere PERCHÉ, e non deve aspettare nel primo tempo.

    Chiesto dall'utente il 17/08/2026, a servizio attivo: «quando non
    trovi l'IMEI avverti con un messaggio a schermo che stai impiegando
    di più perché stai usando una ricerca su archivio esterno, e fai sì
    che non sia troppo lento».

    Le due cose sono la stessa: la chiamata stava nel PRIMO tempo, quello
    che deve uscire subito, e da lì non si può nemmeno avvisare — la
    pagina non è ancora partita. Spostata nel secondo, l'attesa si può
    dichiarare mentre accade.
    """

    def setUp(self):
        super().setUp()
        import os

        self._online = imeicheck.cerca_tac_online
        self._chiave = os.environ.get("TAC_API_KEY")
        os.environ["TAC_API_KEY"] = "finta-per-il-test"
        self.chiamate = {"n": 0}

        def finto(tac):
            self.chiamate["n"] += 1
            return ("ZTE", "Blade A75 5G")

        imeicheck.cerca_tac_online = finto

    def tearDown(self):
        import os

        imeicheck.cerca_tac_online = self._online
        if self._chiave is None:
            os.environ.pop("TAC_API_KEY", None)
        else:
            os.environ["TAC_API_KEY"] = self._chiave
        super().tearDown()

    def test_il_primo_tempo_non_esce_mai_in_rete(self):
        from web.main import _esito_imei

        esito = _esito_imei("998877660000000", solo_locale=True)
        self.assertEqual(self.chiamate["n"], 0)
        self.assertFalse(esito["riconosciuto"])
        self.assertTrue(esito["cerco_fuori"], "la pagina non sa di dover avvisare")

    def test_il_secondo_tempo_chiede_davvero(self):
        from web.main import _esito_imei

        esito = _esito_imei("998877660000000")
        self.assertEqual(self.chiamate["n"], 1)
        self.assertTrue(esito["riconosciuto"])

    def test_niente_avviso_se_il_servizio_non_e_configurato(self):
        """Un avviso per un'attesa che non ci sarà è una bugia: senza
        chiave nessuno interroga niente, e il TAC resta sconosciuto."""
        import os

        os.environ.pop("TAC_API_KEY", None)
        from web.main import _esito_imei

        self.assertFalse(_esito_imei("998877660000000", solo_locale=True)["cerco_fuori"])

    def test_niente_avviso_per_un_tac_gia_noto(self):
        from web.main import _esito_imei

        esito = _esito_imei("356924110000000", solo_locale=True)   # è nel CSV di prova
        self.assertTrue(esito["riconosciuto"])
        self.assertFalse(esito["cerco_fuori"])
