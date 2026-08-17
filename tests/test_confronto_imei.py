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
        voci = imeicheck.confronto("359132010000000")["voci"]
        self.assertTrue(voci)
        self.assertEqual(voci[0]["fonte"], imeicheck.FONTE_IMEIDB)


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
