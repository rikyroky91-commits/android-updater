"""Test del modulo SoC.

Il gruppo che conta di più è `TestNonInventare`: il valore di questo
modulo non sta in quanti chip riconosce, ma nel fatto che quando non sa,
lo dice. Un Exynos scritto al posto di uno Snapdragon manda a cercare un
bug su un telefono che non ce l'ha.
"""
from __future__ import annotations

import unittest

from core import soc


class TestVariantiRegionali(unittest.TestCase):
    """Il motivo per cui il modulo esiste.

    Stesso nome, stesso firmware, chip diverso per mercato: è la
    distinzione che decide se un difetto è riproducibile.
    """

    def test_galaxy_s24_europa_e_usa_hanno_chip_diversi(self):
        europa = soc.per_modello("SM-S921B")
        usa = soc.per_modello("SM-S921U")
        self.assertIn("Exynos 2400", europa.etichetta)
        self.assertIn("Snapdragon 8 Gen 3", usa.etichetta)

    def test_la_nota_avverte_dell_altra_variante(self):
        europa = soc.per_modello("SM-S921B")
        self.assertIn("Snapdragon", europa.nota)

    def test_ultra_uguale_in_tutti_i_mercati(self):
        """Nella stessa generazione l'Ultra non segue la regola degli
        altri: è la prova che una regola sul suffisso B/U applicata alla
        cieca sarebbe sbagliata."""
        for codice in ("SM-S928B", "SM-S928U"):
            with self.subTest(codice=codice):
                self.assertIn("Snapdragon 8 Gen 3", soc.per_modello(codice).etichetta)

    def test_generazioni_diverse_ripartizioni_diverse(self):
        """S22 e S24 splittano Exynos/Snapdragon, S23 e S25 no. Nessuna
        regola generale: solo la tabella."""
        self.assertIn("Exynos 2200", soc.per_modello("SM-S901B").etichetta)
        self.assertIn("Snapdragon 8 Gen 1", soc.per_modello("SM-S901U").etichetta)
        self.assertIn("Snapdragon 8 Gen 2", soc.per_modello("SM-S911B").etichetta)
        self.assertIn("Snapdragon 8 Elite", soc.per_modello("SM-S931B").etichetta)


class TestMarcheFuoriDalPerimetroSpecs(unittest.TestCase):
    """HONOR, HUAWEI, realme e Nothing non sono in `specs.py` (vedi
    FONTI.md, "Undici marche"): il primo lotto di righe verificate a mano
    per queste marche, aggiunto l'11/08/2026, deve risolversi come le
    righe Samsung già presenti."""

    def test_honor_magic7_pro(self):
        self.assertIn("Snapdragon 8 Elite", soc.per_modello("PTP-AN10").etichetta)

    def test_honor_200_pro(self):
        self.assertIn("Snapdragon 8s Gen 3", soc.per_modello("ELP-AN00").etichetta)

    def test_huawei_pura_70_pro_stesso_chip_in_entrambe_le_varianti(self):
        internazionale = soc.per_modello("HBN-LX9")
        cina = soc.per_modello("HBN-AL00")
        self.assertIn("Kirin 9010", internazionale.etichetta)
        self.assertIn("Kirin 9010", cina.etichetta)
        # Qui a differenziare non è il chip (uguale) ma il sistema
        # operativo di base — la nota lo dice, non lo nasconde.
        self.assertIn("HarmonyOS", cina.nota)

    def test_realme_gt7_pro(self):
        self.assertIn("Snapdragon 8 Elite", soc.per_modello("RMX5010").etichetta)

    def test_nothing_phone_3(self):
        self.assertIn("Snapdragon 8s Gen 4", soc.per_modello("A024").etichetta)

    def test_nothing_phone_3a(self):
        self.assertIn("Snapdragon 7s Gen 3", soc.per_modello("A059").etichetta)

    def test_realme_note_60_e_il_telefono_del_caso_reale_discusso_in_sessione(self):
        """RMX3933: il codice del caso reale ("realme RMX3933" -> "Note
        60") già coperto dai nomi gemelli — qui si aggiunge il chip."""
        self.assertIn("Tiger T612", soc.per_modello("RMX3933").etichetta)

    def test_realme_c63_chiesto_dall_utente(self):
        """RMX3939: cercato dall'utente senza risultato, aggiunto su
        richiesta diretta. Verificato incrociando due fonti (GSMArena ha
        risposto 429 in sessione)."""
        self.assertIn("Tiger T612", soc.per_modello("RMX3939").etichetta)


class TestInserimentoMetodicoRealme(unittest.TestCase):
    """Round 1 dell'inserimento sistematico realme, su richiesta esplicita
    dell'utente (11/08/2026): una scheda alla volta su GSMArena, marca per
    marca. Copre i modelli correnti delle serie 14/15/16, GT, C, P."""

    def test_realme_14t(self):
        self.assertIn("Dimensity 6300", soc.per_modello("RMX5078").etichetta)

    def test_realme_c71(self):
        self.assertIn("T7250", soc.per_modello("RMX5303").etichetta)

    def test_realme_gt_7t(self):
        self.assertIn("Dimensity 8400 Max", soc.per_modello("RMX5085").etichetta)

    def test_realme_15_pro(self):
        self.assertIn("Snapdragon 7 Gen 4", soc.per_modello("RMX5101").etichetta)

    def test_realme_c75_5g(self):
        self.assertIn("Dimensity 6300", soc.per_modello("RMX3943").etichetta)

    def test_realme_15_5g(self):
        self.assertIn("Dimensity 7300+", soc.per_modello("RMX5106").etichetta)

    def test_realme_p4_power(self):
        self.assertIn("Dimensity 7400 Ultra", soc.per_modello("RMX5107").etichetta)

    def test_realme_c85_5g(self):
        self.assertIn("Dimensity 6300", soc.per_modello("RMX5253").etichetta)

    def test_realme_16_5g(self):
        self.assertIn("Dimensity 6400 Turbo", soc.per_modello("RMX5171").etichetta)

    def test_realme_p4_pro(self):
        self.assertIn("Snapdragon 7 Gen 4", soc.per_modello("RMX5116").etichetta)

    def test_i_chip_mediatek_senza_sigla_interna_non_ne_inventano_una(self):
        """Regressione diretta su un errore commesso e corretto in questa
        stessa sessione: per Dimensity 6300/7300+/7400 Ultra/8400 Max/6400
        Turbo GSMArena non pubblica una sigla MTxxxx distinta dal nome
        commerciale — il codice deve restare assente, non indovinato."""
        for codice in ("RMX5078", "RMX5085", "RMX3943", "RMX5106",
                       "RMX5107", "RMX5253", "RMX5171"):
            with self.subTest(codice=codice):
                self.assertIsNone(soc.per_modello(codice).codice)

    def test_honor_magic6_pro(self):
        self.assertIn("Snapdragon 8 Gen 3", soc.per_modello("BVL-AN16").etichetta)

    def test_realme_14_pro_plus(self):
        self.assertIn("Snapdragon 7s Gen 3", soc.per_modello("RMX5051").etichetta)

    def test_honor_400_pro(self):
        self.assertIn("Snapdragon 8 Gen 3", soc.per_modello("DNP-NX9").etichetta)

    def test_realme_gt8_pro(self):
        self.assertIn("Snapdragon 8 Elite Gen 5", soc.per_modello("RMX5210").etichetta)

    def test_honor_magic_v5_stesso_chip_in_tutte_le_varianti(self):
        for codice in ("MBH-AN10", "MHG-AN00", "MBH-N49"):
            with self.subTest(codice=codice):
                self.assertIn("Snapdragon 8 Elite", soc.per_modello(codice).etichetta)


class TestInserimentoMetodicoHonor(unittest.TestCase):
    """Round 1 dell'inserimento sistematico HONOR, su richiesta esplicita
    dell'utente (11/08/2026), subito dopo realme — stesso metodo."""

    def test_honor_400(self):
        self.assertIn("Snapdragon 7 Gen 3", soc.per_modello("DNY-NX9").etichetta)

    def test_honor_600(self):
        self.assertIn("Snapdragon 7 Gen 4", soc.per_modello("VKJ-NX9").etichetta)

    def test_honor_x9d(self):
        self.assertIn("Snapdragon 6 Gen 4", soc.per_modello("MTN-NX1").etichetta)

    def test_honor_magic7_base(self):
        self.assertIn("Snapdragon 8 Elite", soc.per_modello("PTP-AN00").etichetta)

    def test_honor_x8d_stesso_chip_in_entrambe_le_varianti(self):
        for codice in ("LNA-LX2", "LNA-LX3"):
            with self.subTest(codice=codice):
                self.assertIn("Snapdragon 6s 4G Gen 2", soc.per_modello(codice).etichetta)


class TestInserimentoMetodicoRound2(unittest.TestCase):
    """Round 2 dello stesso inserimento sistematico (11/08/2026): ripresa
    dei modelli saltati per 429 nel round 1, piu' nuovi modelli realme e
    HONOR trovati proseguendo il giro."""

    def test_honor_600_pro_fonte_singola(self):
        self.assertIn("Snapdragon 8 Elite", soc.per_modello("VKP-NX9").etichetta)

    def test_honor_magic7_rsr_porsche_design_stesso_chip_in_entrambe_le_varianti(self):
        for codice in ("PTP-AN20", "PTP-N59"):
            with self.subTest(codice=codice):
                self.assertIn("Snapdragon 8 Elite", soc.per_modello(codice).etichetta)

    def test_realme_16_pro_plus(self):
        self.assertIn("Snapdragon 7 Gen 4", soc.per_modello("RMX5131").etichetta)

    def test_honor_200_stesso_chip_in_entrambe_le_varianti(self):
        for codice in ("ELI-AN00", "ELI-NX9"):
            with self.subTest(codice=codice):
                self.assertIn("Snapdragon 7 Gen 3", soc.per_modello(codice).etichetta)

    def test_honor_magic7_lite(self):
        self.assertIn("Snapdragon 6 Gen 1", soc.per_modello("BRP-NX1").etichetta)

    def test_realme_gt_7_base(self):
        self.assertIn("Dimensity 9400e", soc.per_modello("RMX5061").etichetta)

    def test_realme_15t_entrambe_le_varianti(self):
        for codice in ("RMX5111", "RMX5112"):
            with self.subTest(codice=codice):
                self.assertIn("Dimensity 6400 Max", soc.per_modello(codice).etichetta)

    def test_honor_400_lite_entrambe_le_varianti(self):
        for codice in ("ABR-NX1", "ABR-N31C1"):
            with self.subTest(codice=codice):
                self.assertIn("Dimensity 7025 Ultra", soc.per_modello(codice).etichetta)

    def test_honor_x70i(self):
        self.assertIn("Dimensity 7025 Ultra", soc.per_modello("ABR-AN00").etichetta)

    def test_honor_x70_entrambi_i_codici(self):
        for codice in ("MTN-AN00", "MTN-AN80"):
            with self.subTest(codice=codice):
                self.assertIn("Snapdragon 6 Gen 4", soc.per_modello(codice).etichetta)

    def test_i_chip_senza_sigla_interna_pubblicata_non_ne_inventano_una(self):
        """Stessa regressione della sessione, estesa ai nuovi codici del
        round 2: nessuno di questi ha una sigla interna verificata su una
        fonte, quindi il campo deve restare assente."""
        for codice in ("RMX5061", "RMX5111", "RMX5112", "ABR-NX1",
                       "ABR-N31C1", "ABR-AN00", "MTN-AN00", "MTN-AN80"):
            with self.subTest(codice=codice):
                self.assertIsNone(soc.per_modello(codice).codice)


class TestAmbiguitaDichiarata(unittest.TestCase):
    """Chi cerca senza codice non può avere una risposta sola — ma
    nemmeno il silenzio."""

    def test_nome_con_due_varianti_le_elenca_entrambe(self):
        chip = soc.per_modello("galaxy s24")
        self.assertIn("Exynos 2400", chip.nome)
        self.assertIn("Snapdragon 8 Gen 3", chip.nome)

    def test_e_dice_come_disambiguare(self):
        chip = soc.per_modello("galaxy s24")
        self.assertIn("codice esatto", chip.nota)

    def test_nome_con_una_sola_variante_risponde_secco(self):
        chip = soc.per_modello("Galaxy S25")
        self.assertIn("Snapdragon 8 Elite", chip.nome)
        self.assertNotIn("oppure", chip.nome)

    def test_e_non_eredita_la_nota_di_una_variante(self):
        """Cercando «Galaxy S25» non si è indicato nessun mercato: una
        nota «Variante USA» qui sarebbe fuorviante."""
        self.assertIsNone(soc.per_modello("Galaxy S25").nota)


class TestCodiceDentroTestoLibero(unittest.TestCase):
    """Il codice quasi mai arriva in un campo suo."""

    def test_codice_annegato_nella_ricerca(self):
        chip = soc.per_modello("samsung sm-s921u aggiornamento")
        self.assertIn("Snapdragon", chip.etichetta)

    def test_estrazione_dei_formati_noti(self):
        casi = {
            "SM-S921B": ["SM-S921B"],
            "OnePlus 13 CPH2649": ["CPH2649"],
            "realme RMX3939 e NE2211": ["RMX3939", "NE2211"],
            "moto XT2451-3": ["XT2451-3"],
        }
        for testo, atteso in casi.items():
            with self.subTest(testo=testo):
                self.assertEqual(soc.codici_da_testo(testo), atteso)

    def test_il_codice_esplicito_batte_quello_estratto(self):
        chip = soc.per_modello("SM-S921U", "Galaxy S24 SM-S921B")
        self.assertIn("Snapdragon", chip.etichetta)


class TestRegoleDeterministiche(unittest.TestCase):
    """Apple e Pixel non hanno varianti di mercato: qui una regola è
    lecita perché non c'è niente da indovinare."""

    def test_iphone_per_identificatore(self):
        casi = {
            "iPhone17,3": "A18", "iPhone17,1": "A18 Pro",
            "iPhone16,2": "A17 Pro", "iPhone15,4": "A16 Bionic",
            "iPhone14,5": "A15 Bionic", "iPhone13,2": "A14 Bionic",
            "iPhone10,3": "A11 Bionic",
        }
        for identificatore, chip in casi.items():
            with self.subTest(id=identificatore):
                self.assertEqual(soc.per_modello(None, identificatore).nome, chip)

    def test_pro_e_non_pro_della_stessa_generazione(self):
        self.assertEqual(soc.per_modello(None, "iPhone17,1").nome, "A18 Pro")
        self.assertEqual(soc.per_modello(None, "iPhone17,3").nome, "A18")

    def test_ipad_resta_fuori(self):
        """La numerazione iPad mescola generazioni e formati: una regola
        qui sarebbe indovinare."""
        self.assertIsNone(soc.per_modello(None, "iPad14,3"))

    def test_generazioni_apple_non_verificate_restano_fuori(self):
        self.assertIsNone(soc.per_modello(None, "iPhone20,1"))

    def test_pixel_per_generazione(self):
        casi = {"Pixel 9 Pro": "Tensor G4", "Pixel 8a": "Tensor G3",
                "Pixel 7": "Tensor G2", "Pixel 6a": "Tensor",
                "Pixel 10 Pro XL": "Tensor G5"}
        for nome, chip in casi.items():
            with self.subTest(nome=nome):
                self.assertEqual(soc.per_modello(None, nome).nome, chip)


class TestSigleChip(unittest.TestCase):
    """La parte sicura: sigla → nome commerciale."""

    def test_sigle_note(self):
        casi = {"SM8750": "Snapdragon 8 Elite", "SM8650": "Snapdragon 8 Gen 3",
                "MT6989": "Dimensity 9300", "S5E9945": "Exynos 2400",
                "GS201": "Tensor G2", "MSM8998": "Snapdragon 835"}
        for sigla, nome in casi.items():
            with self.subTest(sigla=sigla):
                self.assertEqual(soc.chip_da_sigla(sigla).nome, nome)

    def test_suffisso_di_variante(self):
        """`-AC` è la versione spinta riservata a Samsung: a parità di
        nome le prestazioni non sono le stesse, quindi si dice."""
        self.assertIn("for Galaxy", soc.chip_da_sigla("SM8750-AC").nome)
        self.assertNotIn("for Galaxy", soc.chip_da_sigla("SM8750-AB").nome)

    def test_codename_di_piattaforma(self):
        chip = soc.chip_da_sigla("sun")
        self.assertEqual(chip.nome, "Snapdragon 8 Elite")
        # Si mostra la sigla vera, non il codename interno.
        self.assertEqual(chip.codice, "SM8750")

    def test_sigla_sconosciuta(self):
        self.assertIsNone(soc.chip_da_sigla("XYZ999"))
        self.assertIsNone(soc.chip_da_sigla(""))


class TestNonInventare(unittest.TestCase):
    """La regola del progetto, applicata al chip."""

    def test_modello_ignoto_non_disponibile(self):
        """Un modello che nessuna fonte copre resta senza chip.

        `CPH2649` (OnePlus 13) stava in questo elenco e ne è uscito: dalla
        v45 il catalogo specifiche lo copre davvero, quindi pretendere qui
        un `None` significherebbe **collaudare un buco invece di un
        comportamento** — cioè impedire di chiuderlo. La regola che questo
        test difende non è «non si sa niente di CPH2649», è «non si
        inventa niente su ciò che non si sa».
        """
        for testo in ("Umidigi Bison", "Telefono Inesistente 9000", ""):
            with self.subTest(testo=testo):
                self.assertIsNone(soc.per_modello(testo or None))

    def test_nessuna_regola_sul_suffisso_samsung(self):
        """Un SM-xxxxB non presente in tabella NON diventa Exynos per
        analogia con gli altri: la ripartizione cambia a ogni
        generazione, quindi dedurla sarebbe un errore sistematico."""
        self.assertIsNone(soc.per_modello("SM-A999Z"))

    def test_la_provenienza_viaggia_sempre_col_dato(self):
        for chip in (soc.per_modello("SM-S921B"),
                     soc.per_modello(None, "iPhone17,3"),
                     soc.per_modello(None, "Pixel 9")):
            with self.subTest(chip=chip.nome):
                self.assertTrue(chip.fonte)


class TestImportatorePlayCatalog(unittest.TestCase):
    """L'importatore dell'export della Play Console.

    NOTA ONESTA: il CSV non è catturato ma costruito sulle intestazioni
    **documentate da Google**, perché il download richiede un login alla
    Play Console e non è ottenibile in modo anonimo. È l'unico pezzo di
    questo modulo non provato su un file reale, ed è segnalato in
    FONTI.md. Va verificato al primo export vero.
    """

    CSV = (
        "Manufacturer,Model Name,Model Code,RAM (TotalMem),Form Factor,"
        "System on Chip,Screen Sizes,Screen Densities,ABIs,Android SDK Versions\n"
        "Google,Pixel 4,flame,5466MB,Phone,Qualcomm SDM855,1080x2280,440,arm64-v8a,29\n"
        "samsung,Galaxy S24,SM-S921B,7811MB,Phone,Samsung S5E9945,1080x2340,420,arm64-v8a,34\n"
        "samsung,Galaxy S24,SM-S921U,7811MB,Phone,Qualcomm SM8650,1080x2340,420,arm64-v8a,34\n"
        "OnePlus,OnePlus 13,CPH2649,11823MB,Phone,Qualcomm SM8750,1440x3168,560,arm64-v8a,35\n"
        "Acme,Telefono Ignoto,ACME1,2048MB,Phone,Acme XX9999,720x1280,320,arm64-v8a,30\n"
    )

    def test_legge_il_soc_per_codice(self):
        indice = soc.carica_play_catalog(self.CSV)
        self.assertEqual(indice["CPH2649"].nome, "Snapdragon 8 Elite")
        self.assertEqual(indice["FLAME"].nome, "Snapdragon 855")

    def test_le_varianti_regionali_sono_righe_distinte(self):
        """È il motivo per cui questa è la fonte primaria: il problema
        delle varianti è risolto per costruzione, non da noi."""
        indice = soc.carica_play_catalog(self.CSV)
        self.assertEqual(indice["SM-S921B"].nome, "Exynos 2400")
        self.assertEqual(indice["SM-S921U"].nome, "Snapdragon 8 Gen 3")

    def test_sigla_sconosciuta_mostrata_grezza(self):
        """Meglio «Acme XX9999» di un campo vuoto: chi fa QA può
        cercarla, il vuoto non dice niente."""
        indice = soc.carica_play_catalog(self.CSV)
        self.assertIn("XX9999", indice["ACME1"].nome)

    def test_colonne_riconosciute_per_nome_non_per_posizione(self):
        righe = self.CSV.splitlines()
        invertito = "\n".join(
            [",".join(reversed(r.split(","))) for r in righe]) + "\n"
        indice = soc.carica_play_catalog(invertito)
        self.assertTrue(indice)

    def test_csv_vuoto_o_senza_colonne_utili(self):
        self.assertEqual(soc.carica_play_catalog(""), {})
        self.assertEqual(soc.carica_play_catalog("a,b\n1,2\n"), {})

    def test_la_fonte_e_dichiarata(self):
        indice = soc.carica_play_catalog(self.CSV)
        self.assertIn("Google Play", indice["CPH2649"].fonte)


class TestDatasetCurato(unittest.TestCase):

    def test_i_commenti_non_diventano_dati(self):
        testo = ("# commento con, virgole, dentro\n"
                 "model_code,nome_commerciale,soc_nome,produttore,soc_codice,nota\n"
                 "# altro commento\n"
                 "SM-X,Test,Chip X,Marca,CODX,\n")
        indice = soc.carica_curato(testo)
        self.assertEqual(set(indice), {"SM-X", "TEST"})

    def test_righe_incomplete_ignorate(self):
        testo = ("model_code,nome_commerciale,soc_nome,produttore,soc_codice,nota\n"
                 "SM-Y,Test,,Marca,,\n"
                 ",Test,Chip,Marca,,\n")
        self.assertEqual(soc.carica_curato(testo), {})

    def test_il_file_del_repo_si_carica(self):
        self.assertIn("tabella curata", soc.status())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
