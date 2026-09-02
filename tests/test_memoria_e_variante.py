"""Le tre segnalazioni del 31/08/2026, con dentro il modo di accorgersene.

1. «il sito continua a crashare continuamente per saturamento della
   memoria» — misurato: l'indice TAC costava 165 MB stabili e 217 di picco
   su un servizio che ne ha 512, e li ricostruiva a ogni avvio. I test qui
   sotto non guardano il codice: guardano i MEGABYTE, perché è l'unica cosa
   che il difetto faceva vedere. Un test che controllasse «esiste il
   generatore» tornerebbe verde anche se qualcuno domani ci rimettesse
   dentro un dizionario intermedio.

2. «cercando 866068054131131 mi trova l'oppo f19 invece dell'a74 che è
   quello venduto in europa» — il database TAC dice «OPPO A74», il
   catalogo tecnico indicizza quel codice come «Oppo F19», e la pagina
   lasciava vincere il secondo.

3. «ho bisogno di sapere nei risultati se è 4g o 5g».

I primi due test girano in un processo SEPARATO. Non è una complicazione
gratuita: la memoria di picco (`VmHWM`) è un dato del processo e non si
azzera, quindi dentro la suite misurerebbe il test più affamato girato
prima; e `openpyxl` una volta importato da un altro file resta in
`sys.modules` per sempre. Sono le due cose che vanno misurate su un
processo appena nato, come quello di Render.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from core import imeicheck, modelcodes  # noqa: E402
from web import presenters as P  # noqa: E402


def _in_un_processo_nuovo(codice: str) -> str:
    """Esegue uno script con la radice del progetto in PYTHONPATH."""
    ambiente = dict(os.environ,
                    PYTHONPATH=RADICE,
                    AVVIA_WORKER="0",
                    PRERISCALDA_CATALOGHI="0",
                    TAC_SOLO_ERA_ANDROID="true")
    esito = subprocess.run([sys.executable, "-c", textwrap.dedent(codice)],
                           capture_output=True, text=True, timeout=300,
                           env=ambiente, cwd=RADICE)
    if esito.returncode != 0:  # pragma: no cover - diagnosi di un guasto
        raise AssertionError(f"il processo di prova è fallito:\n{esito.stderr}")
    return esito.stdout.strip()


class TestIndiceTacNonSaturaLaMemoria(unittest.TestCase):
    """«il sito continua a crashare continuamente per saturamento della
    memoria», 31/08/2026.

    Misure prese sul database vero (248.359 righe, 77.567 TAC tenuti):

        prima    165 MB stabili   217 MB di picco
        dopo      54 MB stabili    64 MB di picco

    Il dato utile, in tutto, sono 3,6 MB di testo: il resto era la forma in
    cui lo si teneva — un dizionario di liste di tuple paga quattro oggetti
    Python per ogni risposta di ogni fonte — più i dizionari intermedi di
    ciascuna fonte, vivi tutti insieme mentre si copiavano nell'indice.
    """

    def test_costruire_l_indice_non_costa_piu_di_ottanta_megabyte(self):
        """La soglia sta in mezzo alle due misure, non al pelo di una.

        60 MB è ampiamente sopra i 7 misurati dopo la correzione e
        ampiamente sotto i 147 di prima: un test così non diventa rosso
        perché una macchina è un po' diversa, ma diventa rosso il giorno
        che qualcuno rimette in mezzo una struttura intera.
        """
        uscita = _in_un_processo_nuovo("""
            import csv, io, os, sys

            def picco():
                for riga in open("/proc/self/status"):
                    if riga.startswith("VmHWM:"):
                        return int(riga.split()[1]) / 1024
                return 0.0

            from core import imeicheck

            # 200.000 righe come quelle vere, generate qui: il test non
            # deve dipendere da un download né da un file di 12 MB nel
            # repository.
            def csv_finto():
                righe = ["Brand,TAC,SPECS"]
                for i in range(200000):
                    tac = str(10000000 + i)
                    righe.append(f'MARCA{i % 50},{tac},"MODELLO {i}, Codice SM-A{i % 900:03d}B, 2023"')
                return ("\\n".join(righe) + "\\n").encode("utf-8")

            grezzo = csv_finto()
            imeicheck._cached_bytes = lambda: grezzo
            imeicheck._cached_bytes_url = lambda *a, **k: None
            imeicheck._indice_curato = dict
            imeicheck.tac_inseriti = dict
            imeicheck.tac_esterni = dict

            prima = picco()
            indice = imeicheck._build_index()
            print(f"{len(indice)} {picco() - prima:.1f}")
        """)
        quanti, cresciuto = uscita.split()
        self.assertEqual(int(quanti), 200000)
        self.assertLess(
            float(cresciuto), 60.0,
            f"costruire l'indice ha fatto crescere il picco di {cresciuto} MB: "
            "prima della correzione del 31/08/2026 erano 147, ed è il difetto "
            "che faceva riavviare il servizio")

    def test_openpyxl_non_si_importa_all_avvio(self):
        """26 MB, misurati, per una libreria che serve in un ripiego.

        Il foglio di calcolo si legge solo se il CSV della base dati
        sparisse: un caso mai capitato, che però si pagava a ogni avvio.
        """
        uscita = _in_un_processo_nuovo("""
            import sys
            from core import imeicheck  # noqa: F401
            print("openpyxl" in sys.modules)
        """)
        self.assertEqual(uscita, "False")

    def test_il_foglio_di_calcolo_si_legge_ancora(self):
        """Rimandare un import non è toglierlo: il ripiego deve funzionare."""
        try:
            import openpyxl
        except ImportError:  # pragma: no cover
            self.skipTest("openpyxl non disponibile")
        import io as _io

        libro = openpyxl.Workbook()
        foglio = libro.active
        foglio.append(["brand", "tac", "specs"])
        foglio.append(["MOTOROLA", "35692411", "Moto G84 5G, XT2347-1, 2023"])
        buffer = _io.BytesIO()
        libro.save(buffer)

        indice = imeicheck._leggi_base_principale(buffer.getvalue())
        self.assertEqual(indice["35692411"][0], "MOTOROLA")


class TestLeRisposteDiUnTacSiSrotolano(unittest.TestCase):
    """L'indice tiene una stringa per TAC; chi legge riceve le tuple di
    sempre. Questi test guardano il confine fra le due forme, che è il
    punto dove un errore non darebbe un guasto ma una risposta sbagliata.
    """

    def test_una_cella_compatta_torna_a_essere_voci(self):
        cella = (f"{imeicheck.FONTE_CURATA}\x1fSamsung\x1fGalaxy A54 5G"
                 f"\x1e{imeicheck.FONTE_PRINCIPALE}\x1fSAMSUNG\x1fGALAXY A54")
        self.assertEqual(
            imeicheck._voci_dalla_cella(cella),
            [(imeicheck.FONTE_CURATA, "Samsung", "Galaxy A54 5G"),
             (imeicheck.FONTE_PRINCIPALE, "SAMSUNG", "GALAXY A54")])

    def test_una_lista_di_tuple_resta_valida(self):
        """`tests/test_core.py` sostituisce `_build_index` con un
        dizionario di liste: chi legge non deve sapere com'è fatto
        l'indice dentro."""
        self.assertEqual(
            imeicheck._voci_dalla_cella([("prova", "Marca", "Modello")]),
            [("prova", "Marca", "Modello")])

    def test_una_fonte_parla_una_volta_sola(self):
        """Nella base principale 14 TAC su 248.359 compaiono due volte.

        Prima del flusso ogni fonte diventava un dizionario, e lì la riga
        ripetuta sovrascriveva la precedente. Ora le righe arrivano tutte e
        il duplicato si scarta in lettura: stesso esito, senza il
        dizionario intermedio.
        """
        cella = (f"{imeicheck.FONTE_PRINCIPALE}\x1fOPPO\x1fPRIMA VERSIONE"
                 f"\x1e{imeicheck.FONTE_PRINCIPALE}\x1fOPPO\x1fSECONDA VERSIONE")
        voci = imeicheck._voci_dalla_cella(cella)
        self.assertEqual(len(voci), 1)
        self.assertEqual(voci[0][2], "SECONDA VERSIONE")

    def test_la_precedenza_delle_fonti_non_cambia(self):
        """Una correzione umana resta davanti a un database scaricato."""
        cella = (f"{imeicheck.FONTE_PRINCIPALE}\x1fOPPO\x1fQUELLO DEL DATABASE"
                 f"\x1e{imeicheck.FONTE_UTENTE}\x1fOPPO\x1fQUELLO SCRITTO A MANO")
        self.assertEqual(imeicheck._voci_dalla_cella(cella)[0][0],
                         imeicheck.FONTE_UTENTE)

    def test_la_riga_di_copyright_di_osmocom_si_salta_ancora(self):
        """Quel file comincia con una riga di licenza e l'intestazione vera
        è la seconda: è il difetto che teneva quella fonte a zero voci per
        mesi, e il lettore in flusso deve continuare a evitarlo."""
        import io

        testo = ("Osmocom TAC database under CC-BY-SA v3.0\n"
                 "tac,name,name,gsmarena_url\n"
                 "35692411,MOTOROLA,Moto G84 5G,\n")
        self.assertEqual(list(imeicheck._righe_osmocom(io.StringIO(testo))),
                         [("35692411", "MOTOROLA", "Moto G84 5G")])


class TestUnTacConosciutoNonSiPerdePiu(unittest.TestCase):
    """«trovare gli imei sta diventando difficile: su due imei non ne ha
    trovato neanche uno», 31/08/2026.

    Uno dei due era `865587084948173`, e la base dati lo conosce
    benissimo: `HONOR,86558708,"HONOR 400 PRO, N/A2025"`. La pagina
    rispondeva «modello sconosciuto». Due difetti sovrapposti, tutti e due
    corretti qui sotto.
    """

    def setUp(self):
        imeicheck.reset_cache()
        self.addCleanup(imeicheck.reset_cache)

    # ---- difetto 1: l'anno attaccato a una parola corta ----------------
    def test_l_anno_attaccato_a_n_a_viene_visto(self):
        """`N/A` sono tre caratteri, e `_unglue_year` ne chiede almeno
        cinque: l'anno spariva, e con lui i modelli più nuovi — quelli per
        cui il dataset non ha ancora un codice."""
        self.assertTrue(imeicheck._dell_era_android("HONOR 400 PRO, N/A2025"))
        self.assertTrue(imeicheck._dell_era_android("REDMI 15 5G, N/A2025"))

    def test_anche_quando_e_attaccato_a_un_nome(self):
        self.assertEqual(imeicheck._anno_appiccicato("Google Pixel 7a2023"), "2023")
        self.assertEqual(imeicheck._anno_appiccicato("Tecno HK KG5p2022, MT H G37"),
                         "2022")

    def test_un_anno_deve_chiudere_la_parola(self):
        """`BD202403` è un codice, non un telefono del 2024: le quattro
        cifre non finiscono la parola, e senza questo freno la regola
        larga diventerebbe una regola che indovina."""
        self.assertIsNone(imeicheck._anno_appiccicato("BIRD BD202403"))

    def test_un_codice_che_finisce_con_un_anno_non_si_spezza(self):
        """`CPH2019` è un codice OPPO, non «CPH» del 2019. La regola larga
        vive solo dentro `_dell_era_android`, dopo che nessun codice è
        stato riconosciuto: `_unglue_year`, che serve a estrarre i codici,
        resta stretta come prima."""
        self.assertEqual(imeicheck._unglue_year("OPPO A5, Oppo CPH2019"),
                         "OPPO A5, Oppo CPH2019")
        codice, _anno = imeicheck._split_code_and_year("OPPO A5, Oppo CPH2019")
        self.assertEqual(codice, "CPH2019")

    def test_n_a_non_e_un_codice_ne_un_produttore(self):
        """«N/A» vuol dire «non ce l'ho», e la pagina scriveva «Honor 400
        Pro (N/A2025)» — una sigla che sembra un codice modello. L'anno
        invece è un dato vero e si tiene."""
        letto = imeicheck.parse_specs("HONOR", "HONOR 400 PRO, N/A2025")
        self.assertEqual(letto["model"], "Honor 400 Pro")
        self.assertEqual(letto["year"], "2025")
        self.assertIsNone(letto["code"])
        self.assertIsNone(letto["maker"])
        self.assertEqual(imeicheck.describe("HONOR", "HONOR 400 PRO, N/A2025"),
                         "Honor 400 Pro (2025)")

    # ---- il codice vivo, che nessun pattern riconosceva ----------------
    def test_i_codici_vivo_hanno_una_lettera_sola(self):
        """`V2124` — segnalato dall'utente il 01/09/2026 con l'IMEI
        862245059650208. Il pattern generico pretende almeno due lettere,
        quindi NESSUN codice vivo veniva riconosciuto: due terzi dei vivo
        del database restavano fuori dall'indice e venivano cercati per
        nome invece che per codice."""
        letto = imeicheck.parse_specs("VIVO", "VIVO Y76 5G, Vivo Mobile V2124")
        self.assertEqual(letto["code"], "V2124")
        self.assertTrue(imeicheck._dell_era_android("VIVO Y76 5G, Vivo Mobile V2124"))
        self.assertEqual(
            imeicheck._split_code_and_year("VIVO V60 LITE 5G, Vivo Mobile V2529")[0],
            "V2529")

    def test_una_sigla_corta_non_diventa_un_codice_vivo(self):
        """Il pattern chiede quattro cifre: «Motorola V66» e «SGH-V100»
        restano quello che sono, cioè telefoni vecchi senza codice."""
        for testo in ("Motorola V66", "SAMSUNG, SAMSUNG SGH-V100", "Nokia 6108"):
            with self.subTest(testo=testo):
                self.assertIsNone(imeicheck._split_code_and_year(testo)[0])

    # ---- difetto 2: fuori dall'indice non vuol dire perduto ------------
    def _con_una_base_dati_finta(self, csv_finto: str):
        """Sostituisce la base dati principale e azzera le cache."""
        veri = (imeicheck._cached_bytes, imeicheck._cached_bytes_url)
        imeicheck._cached_bytes = lambda: csv_finto.encode("utf-8")
        imeicheck._cached_bytes_url = lambda *a, **k: None
        imeicheck.reset_cache()

        def rimetti():
            imeicheck._cached_bytes, imeicheck._cached_bytes_url = veri
            imeicheck.reset_cache()

        self.addCleanup(rimetti)

    # Una riga che il filtro dell'era Android scarta di sicuro: niente
    # anno, niente codice riconoscibile.
    BASE = ("Brand,TAC,SPECS\n"
            "NOKIA,11111111,\"Nokia 6108\"\n"
            "HONOR,22222222,\"HONOR 400 PRO, N/A2025\"\n")

    def test_una_riga_scartata_resta_cercabile_nei_file(self):
        """216.617 righe su 248.373 stavano fuori dall'indice, e finora
        erano semplicemente perse: un dato che sta in un file dentro
        l'applicazione, e a cui l'applicazione risponde «non lo so», non è
        un buco di copertura — è un dato buttato."""
        self._con_una_base_dati_finta(self.BASE)
        indice = imeicheck._build_index()
        self.assertNotIn("11111111", indice)      # il filtro l'ha esclusa
        voci = imeicheck._voci_per_tac("11111111")
        self.assertEqual([v[2] for v in voci], ["Nokia 6108"])

    def test_la_riga_recente_sta_invece_nell_indice(self):
        """Il caso dell'utente: dopo la correzione dell'anno appiccicato
        l'HONOR 400 Pro non ha nemmeno bisogno della seconda lettura."""
        self._con_una_base_dati_finta(self.BASE)
        self.assertIn("22222222", imeicheck._build_index())

    def test_un_tac_che_non_c_e_resta_un_no(self):
        """La seconda lettura allarga la copertura, non inventa risposte."""
        self._con_una_base_dati_finta(self.BASE)
        imeicheck._build_index()
        self.assertEqual(imeicheck._voci_per_tac("99999999"), [])

    def test_i_file_non_si_rileggono_a_ogni_domanda(self):
        """Una pagina sola interroga questa strada più volte — identità,
        confronto fra le fonti, secondo tempo della ricerca — e rileggere
        i file a ogni giro sarebbe il modo di trasformare una correzione
        in un rallentamento."""
        self._con_una_base_dati_finta(self.BASE)
        imeicheck._build_index()
        imeicheck._voci_per_tac("11111111")
        letture = []
        vero = imeicheck._voci_principali
        imeicheck._voci_principali = lambda: letture.append(1) or iter(())
        try:
            imeicheck._voci_per_tac("11111111")
        finally:
            imeicheck._voci_principali = vero
        self.assertEqual(letture, [])

    def test_salvare_un_modello_cancella_il_ricordo_del_no(self):
        """`reset_cache` viene chiamata da `/tac/salva`: un «non c'è»
        ricordato da prima risponderebbe al posto del dato appena
        scritto."""
        self._con_una_base_dati_finta(self.BASE)
        imeicheck._build_index()
        imeicheck._voci_per_tac("99999999")
        self.assertIn("99999999", imeicheck._CACHE_SECONDE_LETTURE)
        imeicheck.reset_cache()
        self.assertEqual(imeicheck._CACHE_SECONDE_LETTURE, {})


class TestIlNomeEuropeoVinceSulNomeDiUnAltroMercato(unittest.TestCase):
    """«cercando 866068054131131 mi trova l'oppo f19 invece dell'a74 che è
    quello venduto in europa», 31/08/2026.

    Il database TAC risponde «OPPO A74, Oppo CPH2219» — il nome giusto — e
    la pagina lo perdeva all'ultimo passo, perché il catalogo tecnico
    indicizza `CPH2219` come «Oppo F19», la grafia indiana, e il suo titolo
    vinceva senza nessun controllo. Il commento sopra quella riga diceva
    già che non doveva succedere: era il codice a non dirlo.
    """

    def test_due_grafie_dello_stesso_nome_sono_lo_stesso_telefono(self):
        self.assertTrue(modelcodes.stesso_telefono("Galaxy A16", "Galaxy A16 4G"))
        self.assertTrue(modelcodes.stesso_telefono("OPPO Reno12 F", "Reno12 F 5G"))

    def test_due_nomi_di_mercato_diversi_non_lo_sono(self):
        self.assertFalse(modelcodes.stesso_telefono("Oppo F19", "OPPO A74"))
        self.assertFalse(modelcodes.stesso_telefono("OPPO F27", "OPPO Reno12 F"))

    def _pagina_per_l_imei(self, titolo_della_scheda: str) -> dict:
        """La pagina dell'IMEI con un catalogo tecnico che dichiara
        `titolo_della_scheda`, senza toccare rete né archivio."""
        from web import main as M

        vera = P.scheda_tecnica

        def finta(nome, codice="", brand="", device=None):
            return {"trovata": True, "titolo": titolo_della_scheda,
                    "marca": "OPPO", "codice": codice, "foto": None,
                    "rilascio": None, "cpu": None, "cpu_nota": None,
                    "cpu_fonte": None, "ram": None, "storage": None,
                    "batteria": None, "voci": [], "sezioni": {},
                    "fonte": "catalogo di prova", "patch_fino_a": None,
                    "patch_cadenza": None, "nota_copertura": None,
                    "rete": None}

        imei = {"modello_cercato": "CPH2219", "codice": "CPH2219",
                "modello": "OPPO A74", "marca": "OPPO",
                "descrizione": "OPPO A74 (CPH2219)", "riconosciuto": True}
        vuoto = {"query": "CPH2219", "trovato": False, "nome": "CPH2219",
                 "codice": "CPH2219", "riga": "", "fonte": "",
                 "senza_firmware": False, "scheda": {"trovata": False},
                 "notizie": [], "quante_notizie": 0, "forse": [],
                 "gemelli": [], "storico": [], "chiave": "",
                 "nota_fonte": None, "errore": None}
        M.P.scheda_tecnica = finta
        try:
            return M._ancora_esito_imei(dict(vuoto), imei)
        finally:
            M.P.scheda_tecnica = vera

    def test_la_scheda_non_puo_cambiare_il_nome_di_mercato(self):
        if not modelcodes.resolve("CPH2219"):
            self.skipTest("catalogo dei codici non disponibile in questo ambiente")
        pagina = self._pagina_per_l_imei("Oppo F19")
        self.assertEqual(pagina["nome"], "OPPO A74")
        # E nemmeno di nascosto, nell'intestazione della scheda: la pagina
        # del dispositivo in archivio mostra quel titolo.
        self.assertEqual(pagina["scheda"]["titolo"], "OPPO A74")

    def test_la_scheda_puo_ancora_completare_la_grafia(self):
        """Il caso che aveva motivato la regola originale, e che resta:
        «Galaxy A16 4G» è la grafia completa che il catalogo tecnico
        conserva, e un nome più preciso non è un nome diverso."""
        if not modelcodes.resolve("CPH2219"):
            self.skipTest("catalogo dei codici non disponibile in questo ambiente")
        pagina = self._pagina_per_l_imei("OPPO A74 4G")
        self.assertEqual(pagina["nome"], "OPPO A74 4G")

    def test_la_riga_curata_dichiara_il_nome_europeo(self):
        """`data/nomi_modello.csv` non inventa: sceglie fra nomi che il
        dataset conosce già. Se il catalogo a monte smettesse di conoscere
        «OPPO A74», la riga smetterebbe di avere effetto — e questo test
        se ne accorgerebbe."""
        if not modelcodes.resolve("CPH2219"):
            self.skipTest("catalogo dei codici non disponibile in questo ambiente")
        self.assertEqual(modelcodes.nome_scelto_a_mano("CPH2219"), "OPPO A74")
        self.assertEqual(modelcodes.nome_canonico("CPH2219"), "OPPO A74")


class TestRedmiNoteDieciNonEUnMiNoteDieci(unittest.TestCase):
    """Il freno che doveva accorgersi di un nome estraneo diceva di sì.

    `_nome_appartiene_al_codice` confrontava le stringhe APPIATTITE, senza
    spazi: `minote10` sta dentro `redminote10` per tre lettere di
    distanza, quindi «Redmi Note 10 EEA» risultava un nome legittimo di
    `M1910F4G`, che è un Mi Note 10. Sono due telefoni diversi.

    Era il difetto dietro l'unico test rosso che questo repository si
    portava dietro da prima di questa sessione.
    """

    def test_una_parola_piu_lunga_non_contiene_l_altra(self):
        from web import main as M
        self.assertFalse(M._uno_dentro_l_altro("Mi Note 10", "Redmi Note 10 EEA"))

    def test_una_parola_intera_in_piu_non_cambia_telefono(self):
        from web import main as M
        self.assertTrue(M._uno_dentro_l_altro("Galaxy A54 5G",
                                              "Samsung Galaxy A54 5G"))
        self.assertTrue(M._uno_dentro_l_altro("Reno12 F", "OPPO Reno12 F 5G"))

    def test_gli_ideogrammi_sono_lettere(self):
        """Buttarli via riduceva «小米 Note 10» a «note10», che risulta
        contenuto in mezzo mondo: era la seconda strada per cui «Redmi
        Note 10» passava per un «Mi Note 10»."""
        from web import main as M
        self.assertFalse(M._uno_dentro_l_altro("小米 Note 10", "Redmi Note 10 EEA"))
        self.assertTrue(M._uno_dentro_l_altro("一加 10R", "一加 10R 5G"))


class TestQuattroGoCinqueG(unittest.TestCase):
    """«ho bisogno di sapere nei risultati se è 4g o 5g», 31/08/2026.

    Non è un dettaglio da scheda tecnica: A54 4G e A54 5G montano chip
    diversi, ricevono build diverse e si aggiornano in date diverse.
    Provare l'uno non dice niente sull'altro.
    """

    def test_il_nome_del_modello_e_la_fonte_migliore(self):
        rete = P.rete_mobile(None, "Samsung Galaxy A54 5G")
        self.assertEqual(rete["sigla"], "5G")
        self.assertEqual(rete["fonte"], "dal nome del modello")

    def test_la_riga_del_database_tac_quando_il_nome_tace(self):
        rete = P.rete_mobile(None, "Galaxy A54", "SAMSUNG GALAXY A54 5G, SM-A546B")
        self.assertEqual(rete["sigla"], "5G")
        self.assertEqual(rete["fonte"], "dal database TAC")

    def test_la_scheda_tecnica_quando_nessun_nome_lo_dice(self):
        scheda = {"sezioni": {"Network": {"Technology": "GSM / HSPA / LTE"}}}
        rete = P.rete_mobile(scheda, "OPPO A74")
        self.assertEqual(rete["sigla"], "4G")
        self.assertEqual(rete["fonte"], "dalla scheda tecnica")
        # Il dettaglio resta a portata di mano: è la riga vera, non un
        # riassunto, ed è quello che permette di controllare la risposta.
        self.assertIn("LTE", rete["dettaglio"])

    def test_il_cinque_g_batte_il_quattro_g_nella_stessa_riga(self):
        scheda = {"sezioni": {"Network": {"Technology": "GSM / HSPA / LTE / 5G"}}}
        self.assertEqual(P.rete_mobile(scheda, "")["sigla"], "5G")

    def test_niente_da_dire_e_una_risposta(self):
        """Dedurlo dal processore sarebbe indovinarlo: quasi tutti i SoC
        recenti hanno un modem 5G che il produttore può lasciare spento, ed
        è proprio il caso in cui esiste una variante 4G."""
        self.assertIsNone(P.rete_mobile({"sezioni": {}}, "OPPO A74"))
        self.assertIsNone(P.rete_mobile(None, "Galaxy S24 Ultra"))

    def test_un_codice_modello_non_e_una_dichiarazione_di_rete(self):
        """`M1910F4G` è il codice dello Xiaomi Mi Note 10: quel «4G»
        attaccato a una lettera non dice niente sulla rete."""
        self.assertIsNone(P.rete_mobile(None, "M1910F4G"))
        self.assertIsNone(P.rete_mobile(None, "SM-A546B"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)


class TestUnServizioRottoLoDeveDire(unittest.TestCase):
    """«il servizio esterno non funziona», 01/09/2026.

    Aveva ragione, e la cosa peggiore è che NON SI POTEVA SAPERE: chiave
    rifiutata, quota finita, servizio giù, rete che non passa — ogni
    guasto finiva nello stesso `return ("errore", None)` muto, e la pagina
    diceva «modello sconosciuto» esattamente come quando il servizio
    risponde «non lo conosco». Due situazioni opposte con la stessa
    frase: una si risolve in un minuto rifacendo una chiave, l'altra no.
    """

    def setUp(self):
        self._chiave = imeicheck._chiave_api
        self._requests = imeicheck.requests
        imeicheck._chiave_api = lambda: "chiave-di-prova"
        imeicheck.reset_cache()

        def rimetti():
            imeicheck._chiave_api = self._chiave
            imeicheck.requests = self._requests
            imeicheck.reset_cache()

        self.addCleanup(rimetti)

    def _servizio_che_risponde(self, stato, corpo=None):
        class Finto:
            def post(self_interno, *a, **k):
                class R:
                    status_code = stato

                    @staticmethod
                    def json():
                        return corpo if corpo is not None else {}
                return R()
        imeicheck.requests = Finto()

    def test_una_chiave_rifiutata_si_riconosce_dal_numero(self):
        self._servizio_che_risponde(401)
        self.assertEqual(imeicheck.cerca_tac_online_esito("35692411"),
                         ("errore", None))
        ultimo = imeicheck.ultimo_esito_servizio()
        self.assertEqual(ultimo["esito"], "errore")
        self.assertIn("401", ultimo["dettaglio"])
        self.assertIn("chiave rifiutata", ultimo["dettaglio"])

    def test_la_quota_finita_ha_parole_sue(self):
        self._servizio_che_risponde(429)
        imeicheck.cerca_tac_online_esito("35692411")
        self.assertIn("quota", imeicheck.ultimo_esito_servizio()["dettaglio"])

    def test_una_rete_che_non_passa_non_e_un_no(self):
        class Rotto:
            def post(self, *a, **k):
                raise OSError("niente rete")
        imeicheck.requests = Rotto()
        self.assertEqual(imeicheck.cerca_tac_online_esito("35692411"),
                         ("errore", None))
        ultimo = imeicheck.ultimo_esito_servizio()
        self.assertEqual(ultimo["esito"], "errore")
        self.assertIn("non raggiungibile", ultimo["dettaglio"])

    def test_dopo_un_guasto_non_si_martella(self):
        """Ogni tentativo costa il tempo del timeout, e chi cerca lo
        aspetta per ricevere comunque «non lo so»."""
        chiamate = []

        class Rotto:
            def post(self, *a, **k):
                chiamate.append(1)
                raise OSError("niente rete")

        imeicheck.requests = Rotto()
        imeicheck.cerca_tac_online_esito("35692411")
        imeicheck.cerca_tac_online_esito("35692412")
        self.assertEqual(len(chiamate), 1)
        self.assertIn("non raggiungibile", imeicheck.servizio_in_pausa() or "")

    def test_una_risposta_buona_toglie_la_pausa(self):
        class Rotto:
            def post(self, *a, **k):
                raise OSError("niente rete")

        imeicheck.requests = Rotto()
        imeicheck.cerca_tac_online_esito("35692411")
        self.assertIsNotNone(imeicheck.servizio_in_pausa())
        imeicheck.reset_cache()          # come fa `/tac/salva`
        self._servizio_che_risponde(200, {"manufacturer": "Samsung",
                                          "model": "Galaxy Test"})
        self.assertEqual(imeicheck.cerca_tac_online_esito("35692411"),
                         ("trovato", ("Samsung", "Galaxy Test")))
        self.assertIsNone(imeicheck.servizio_in_pausa())

    def test_un_no_del_servizio_resta_un_no(self):
        """La distinzione che regge tutto: «non lo conosco» è una
        risposta e si conserva, un guasto no."""
        self._servizio_che_risponde(404)
        self.assertEqual(imeicheck.cerca_tac_online_esito("35692411"),
                         ("assente", None))
        self.assertEqual(imeicheck.ultimo_esito_servizio()["esito"], "assente")
        self.assertIsNone(imeicheck.servizio_in_pausa())

    def test_lo_stato_per_diagnostica_dice_com_e_andata(self):
        self._servizio_che_risponde(401)
        imeicheck.cerca_tac_online_esito("35692411")
        stato = imeicheck.stato_servizio_esterno()
        self.assertIn("chiave presente", stato)
        self.assertIn("401", stato)


class TestLaRetaNonSiRipeteNelTitolo(unittest.TestCase):
    """Visto in produzione il 01/09/2026, appena distribuita la pastiglia:
    «vivo Y76 5G 5G». Il nome commerciale finiva già per «5G» e la
    pastiglia lo ripeteva attaccato.

    Chi legge quel titolo la risposta ce l'ha davanti; ripeterla non
    aggiunge niente e sembra un errore dell'app. Nella scheda tecnica la
    voce «Rete» resta invece sempre, perché lì sta in una tabella di
    caratteristiche, dove un valore va scritto anche quando è ovvio.
    """

    def test_il_nome_che_lo_dice_gia_alza_la_bandierina(self):
        rete = P.rete_mobile(None, "vivo Y76 5G")
        self.assertEqual(rete["sigla"], "5G")
        self.assertTrue(rete["nel_nome"])

    def test_la_scheda_tecnica_non_e_nel_nome(self):
        scheda = {"sezioni": {"Network": {"Technology": "GSM / HSPA / LTE"}}}
        rete = P.rete_mobile(scheda, "OPPO A74")
        self.assertEqual(rete["sigla"], "4G")
        self.assertFalse(rete["nel_nome"])

    def test_nemmeno_la_riga_del_database_tac(self):
        """Lì il dato non è sotto gli occhi di chi legge: il titolo mostra
        il nome canonico, non la riga grezza del TAC."""
        rete = P.rete_mobile(None, "Galaxy A54", "SAMSUNG GALAXY A54 5G, SM-A546B")
        self.assertEqual(rete["sigla"], "5G")
        self.assertFalse(rete["nel_nome"])
