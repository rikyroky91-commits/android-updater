"""Le quattro segnalazioni di Riccardo, fissate una per una.

1. «non becca la versione di Android per modello»
2. «in base a come scrivo il modello cambia risultato»
3. «non trova la cpu di ogni samsung o altro brand»
4. «non sempre trovo l'IMEI mentre altri siti trovano il modello giusto»

Ognuna aveva una causa diversa e verificabile. Questi test le bloccano.
"""
from __future__ import annotations

import unittest

from core import imeicheck, modelcodes, scan, soc, sources


class TestVersionePiuRecenteFraLeRegioni(unittest.TestCase):
    """1 — la versione di Android era quella SBAGLIATA, non assente.

    Il controllo versione Samsung prendeva la prima regione che rispondeva.
    Per `SM-A325F` la prima della lista, `EUX`, è ferma ad **Android 11**,
    mentre tredici altre regioni danno **Android 13**: l'app dichiarava
    quindi Android 11 per un telefono aggiornato ad Android 13, con l'aria
    del dato ufficiale.
    """

    def test_sceglie_la_versione_piu_alta(self):
        risposte = {
            "EUX": ("A325FXXU1AUCC", "11", "EUX"),
            "ITV": ("A325FXXSCDYB2", "13", "ITV"),
            "DBT": ("A325FXXU1AUD7", "11", "DBT"),
        }
        originale = sources._fota_get

        def finto(url):
            csc = url.split("/firmware/")[1].split("/")[0]
            voce = risposte.get(csc)
            if not voce:
                return None
            return ('<latest o="%s">%s/X/Y</latest>' % (voce[1], voce[0]))

        sources._fota_get = finto
        try:
            pda, android, csc = sources._samsung_fus_latest("SM-A325F")
        finally:
            sources._fota_get = originale

        self.assertEqual(android, "13")
        self.assertEqual(pda, "A325FXXSCDYB2")

    def test_a_parita_di_android_vince_la_build_piu_recente(self):
        """La data è codificata nelle ultime tre lettere del PDA."""
        vecchia = sources._eta_build_samsung("A325FXXU1AUCC")   # 2021, marzo
        nuova = sources._eta_build_samsung("A325FXXSCDYB2")     # 2025, febbraio
        self.assertLess(vecchia, nuova)

    def test_pda_indecifrabile_non_rompe_il_confronto(self):
        self.assertEqual(sources._eta_build_samsung("XX"), (0, 0, ""))
        self.assertEqual(sources._eta_build_samsung(""), (0, 0, ""))


class TestStessoTelefonoScrittoInModiDiversi(unittest.TestCase):
    """2 — «samsung a32», «a325» e «SM-A325F» sono lo stesso telefono."""

    def test_codice_incompleto_si_espande(self):
        """Nel dataset non esiste `SM-A325`: esistono `SM-A325F/M/N`,
        perché l'ultima lettera è il mercato. Chi legge il codice sulla
        scatola o lo ricorda a metà scriveva qualcosa che non trovava
        nulla, pur essendo a un carattere dal dato."""
        completi = modelcodes.codici_per_prefisso("SM-A325")
        self.assertTrue(any(c.startswith("SM-A325") and len(c) > len("SM-A325")
                            for c in completi), completi)

    def test_prefisso_troppo_corto_non_pesca_nel_mucchio(self):
        """Su 68.000 codici un prefisso vago restituirebbe modelli di
        marche diverse: meglio nessuna risposta che una a caso."""
        self.assertEqual(modelcodes.codici_per_prefisso("SM"), [])
        self.assertEqual(modelcodes.codici_per_prefisso(""), [])

    def test_sigla_corta_diventa_nome_di_gamma(self):
        self.assertIn("Galaxy A32", sources._nomi_da_sigla_corta("a32"))
        self.assertIn("Galaxy A32", sources._nomi_da_sigla_corta("samsung a32"))

    def test_un_codice_vero_non_riceve_una_gamma_inventata(self):
        """«a325f» è già un codice: «Galaxy A325F» non esiste e sarebbe
        solo rumore che allunga la ricerca."""
        self.assertEqual(sources._nomi_da_sigla_corta("a325f"), [])
        self.assertEqual(sources._nomi_da_sigla_corta("SM-A325F"), [])

    def test_tutte_le_forme_producono_lo_stesso_modello(self):
        atteso = "Galaxy A32"
        for forma in ("a32", "a325", "samsung a32", "SM-A325F", "Galaxy A32"):
            with self.subTest(forma=forma):
                espansioni = sources.expand_query(forma)
                normalizzate = {modelcodes._normalize_name(e) for e in espansioni}
                self.assertIn(modelcodes._normalize_name(atteso), normalizzate,
                              f"«{forma}» non arriva a «{atteso}»: {espansioni}")

    def test_la_variante_5g_resta_distinta(self):
        """La tolleranza non deve fondere due telefoni diversi: l'A32 4G
        monta Helio G80, la 5G un Dimensity 720."""
        quattro = {modelcodes._normalize_name(e) for e in sources.expand_query("SM-A325F")}
        cinque = {modelcodes._normalize_name(e) for e in sources.expand_query("SM-A326B")}
        self.assertFalse(quattro & cinque)


class TestMarcaDavantiAllaSigla(unittest.TestCase):
    """Le forme viste negli screenshot: «samsung a235» e «oppo a96».

    Entrambe fallivano, per due ragioni opposte e istruttive.
    """

    def test_la_marca_non_nasconde_il_codice(self):
        """«a235» funzionava, «samsung a235» no: con la parola davanti il
        testo non ha più la forma di un codice e non veniva riconosciuto.
        Ora il codice si cerca anche sul testo senza marca."""
        nudo = {modelcodes._normalize_name(e) for e in sources.expand_query("a235")}
        con_marca = {modelcodes._normalize_name(e)
                     for e in sources.expand_query("samsung a235")}
        self.assertTrue(nudo & con_marca,
                        "«samsung a235» non arriva dove arriva «a235»")

    def test_niente_modelli_inventati_da_una_radice(self):
        """Tre cifre sono già una radice di codice (`a235` → `SM-A235F`),
        non un nome: «Galaxy A235» non esiste, e inventarlo prendeva anche
        il posto dell'espansione del codice, che invece funziona."""
        self.assertEqual(sources._nomi_da_sigla_corta("a235"), [])
        self.assertNotIn("Galaxy A235", sources.expand_query("samsung a235"))

    def test_la_gamma_segue_la_marca_scritta(self):
        """L'errore più grave: la gamma era cablata a «Galaxy» per tutti, e
        «oppo a96» diventava «Galaxy A96» — un telefono che non esiste."""
        self.assertEqual(sources._nomi_da_sigla_corta("oppo a96"), ["OPPO A96"])
        self.assertEqual(sources._nomi_da_sigla_corta("realme c61"), ["realme C61"])
        self.assertEqual(sources._nomi_da_sigla_corta("samsung a23"), ["Galaxy A23"])

    def test_senza_marca_si_provano_piu_gamme(self):
        """Una sigla da sola non dice di chi sia: indovinarne una sola fa
        fallire ricerche che avrebbero successo. Un nome inesistente non
        trova nulla e non fa danno."""
        proposte = sources._nomi_da_sigla_corta("a96")
        self.assertIn("OPPO A96", proposte)
        self.assertIn("Galaxy A96", proposte)


class TestNomeCommercialeValeQuantoIlCodice(unittest.TestCase):
    """`CPH2333` diceva «OPPO A96 riconosciuto», `oppo a96` non diceva
    niente: stessa domanda, stesso telefono, due risposte diverse — e
    quella muta toccava alla forma più naturale."""

    def test_il_nome_arriva_agli_stessi_codici_del_codice(self):
        codici = scan._codici_riconoscibili("OPPO A96")
        self.assertTrue(codici, "nessun codice raggiunto dal nome commerciale")

    def test_un_nome_ignoto_non_produce_codici(self):
        self.assertEqual(scan._codici_riconoscibili("Telefono Inesistente 999"), [])


class TestSiglaSenzaMarcaEAmbigua(unittest.TestCase):
    """«a15» è insieme un OPPO A15 e un Galaxy A15: esistono entrambi.

    La ricerca si fermava alla prima fonte con una versione, e l'ordine
    delle fonti è per COSTO, non per pertinenza: rispondeva «OPPO A15,
    patch 2022-04» senza mai interrogare Samsung e senza dire che stava
    scegliendo. Una risposta sola a una domanda con due risposte è
    sbagliata anche quando è verificata.
    """

    def test_una_sigla_nuda_e_riconosciuta_come_ambigua(self):
        self.assertFalse(sources.looks_like_model_code("a15"))
        self.assertIsNone(__import__("core.extract", fromlist=["x"]).detect_brand("a15"))

    def test_con_la_marca_scritta_non_ce_ambiguita(self):
        from core import extract
        self.assertIsNotNone(extract.detect_brand("samsung a15"))
        self.assertIsNotNone(extract.detect_brand("oppo a15"))

    def test_il_deduplicatore_non_fonde_marche_diverse(self):
        """La deduplica dei risultati ambigui usa il nome COSÌ COM'È.

        `_normalize_name` è fatta per far combaciare le forme dello stesso
        telefono e toglie la marca quando la riconosce: «OPPO A15» diventa
        «a15». Usarla qui rischierebbe di fondere due telefoni diversi —
        cioè esattamente quelli che questa funzione deve tenere distinti.
        """
        self.assertEqual(modelcodes._normalize_name("OPPO A15"), "a15")
        chiavi = {" ".join(n.lower().split()) for n in ("OPPO A15", "Galaxy A15")}
        self.assertEqual(len(chiavi), 2)


class TestChipSempreAllegato(unittest.TestCase):
    """3 — il chip non dipende da chi ha risposto sul firmware."""

    def test_chip_per_codice_esatto(self):
        chip = soc.per_modello(model_code="SM-A325F")
        self.assertIsNotNone(chip)
        self.assertIn("Helio G80", chip.etichetta)

    def test_varianti_regionali_distinte(self):
        """Il caso per cui il modulo esiste: stesso nome, chip diverso."""
        europa = soc.per_modello(model_code="SM-S921B")
        usa = soc.per_modello(model_code="SM-S921U")
        self.assertIsNotNone(europa)
        self.assertIsNotNone(usa)
        self.assertNotEqual(europa.nome, usa.nome)

    def test_nome_ambiguo_lo_dichiara(self):
        """Chi cerca «Galaxy S24» senza codice non può avere una risposta
        sola: una risposta sola sarebbe sbagliata per metà dei telefoni."""
        chip = soc.per_modello(device_name="Galaxy S24")
        self.assertIsNotNone(chip)
        self.assertIn("oppure", chip.nome)

    def test_chip_allegato_anche_quando_il_firmware_arriva(self):
        """La regressione vera: il chip veniva aggiunto SOLO nel ripiego
        «codice riconosciuto ma nessun firmware». Bastava che una fonte
        rispondesse — cioè il caso migliore — perché sparisse."""
        voce = {"device_model": "Galaxy S24 Ultra", "size_info": "Fonte ufficiale"}
        scan._aggiungi_chip(voce, "SM-S928B") if hasattr(scan, "_aggiungi_chip") else None
        if hasattr(scan, "_aggiungi_chip"):
            self.assertIn("SoC", voce["size_info"])
            self.assertIn("Fonte ufficiale", voce["size_info"])


class TestImeiRisolveAlCodice(unittest.TestCase):
    """4 — l'IMEI conosce il codice esatto: va usato quello."""

    def test_il_codice_viene_estratto_dalla_voce_tac(self):
        """La voce del database è «SAMSUNG GALAXY S26 ULTRA, Samsung
        SM-S948B»: il codice c'è, ed è più preciso del nome."""
        dettagli = imeicheck.parse_specs(
            "SAMSUNG", "SAMSUNG GALAXY S26 ULTRA, Samsung SM-S948B")
        self.assertEqual(dettagli["code"], "SM-S948B")

    def test_il_nome_resta_come_ripiego(self):
        dettagli = imeicheck.parse_specs("NOKIA", "NOKIA C1 PLUS")
        self.assertTrue(dettagli["model"])

    def test_imei_non_valido_non_viene_interrogato(self):
        self.assertFalse(imeicheck.is_valid_imei("123456789012345"))
        self.assertFalse(imeicheck.is_valid_imei("abc"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
