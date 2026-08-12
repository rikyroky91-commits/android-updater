"""Test della fonte ufficiale vivo (Android Enterprise Recommended).

L'HTML usato qui è quello VERO della pagina, registrato in
`tests/fixtures/vivo_aer.html` il 2026-08-02 — non una ricostruzione.

È il punto centrale di questo file. La versione precedente del parser era
dichiaratamente un'ipotesi: riusava lo schema AER di Honor e realme senza
che nessuno avesse mai letto la pagina vivo, ed è rimasta in errore per
giorni. Gli stessi test su un HTML inventato sarebbero passati benissimo,
confermando un parser che non funzionava — è già successo con realme.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as C, sources  # noqa: E402

_FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "vivo_aer.html")
with open(_FIXTURE, encoding="utf-8") as _f:
    PAGINA = _f.read()


class TestLetturaTabellaReale(unittest.TestCase):
    def setUp(self):
        self.items = sources.parse_vivo_aer(PAGINA)
        self.per_nome = {i.device: i for i in self.items}

    def test_riconosce_tutti_i_modelli(self):
        """20 righe nella tabella, 20 modelli. Se il numero cala senza che
        la pagina sia cambiata, il riconoscimento si è rotto."""
        self.assertEqual(len(self.items), 20)

    def test_versione_di_fabbrica_letta(self):
        voce = self.per_nome["vivo X300 Ultra"]
        self.assertEqual(voce.android_version, 16)
        self.assertEqual(voce.brand, C.VIVO)

    def test_promessa_futura_mai_usata_come_versione(self):
        """«Future version: Andorid 17&18&19&20&21» non deve MAI diventare
        la versione del dispositivo: è l'errore che dichiarava un HONOR X8c
        su Android 16 quando era su Android 15."""
        for voce in self.items:
            self.assertLessEqual(
                voce.android_version, 16,
                f"«{voce.device}» ha preso una versione futura: {voce.android_version}",
            )

    def test_android_scritto_per_esteso_riconosciuto(self):
        """Qui la pagina scrive «Shipped version: Android 16», non
        «Shipped version: 16» come Honor: è una delle tre ragioni per cui
        lo schema generico non trovava nulla."""
        self.assertIn("Shipped version: Android", PAGINA.replace("&nbsp;", " "),
                      "la fixture non rappresenta più il formato che questo test protegge")
        self.assertTrue(all(v.android_version for v in self.items))

    def test_entita_nbsp_decodificate(self):
        """Ogni cella comincia con `&nbsp;&nbsp;`: togliere i tag non le
        decodifica, e senza `html.unescape` il nome sarebbe
        «&nbsp;&nbsp;X300 Ultra»."""
        self.assertIn("&nbsp;", PAGINA, "la fixture non ha più le entità da decodificare")
        for voce in self.items:
            self.assertNotIn("&nbsp;", voce.device)
            self.assertNotIn("\xa0", voce.device)

    def test_marca_aggiunta_al_nome(self):
        """La tabella scrive «X300 Ultra» senza marca. Senza il prefisso il
        `device_key` non coinciderebbe con quello delle altre fonti e lo
        stesso telefono diventerebbe due dispositivi distinti."""
        for voce in self.items:
            self.assertRegex(voce.device, r"(?i)^(vivo|iqoo)\s")

    def test_codice_modello_non_incollato_al_nome(self):
        """La tabella ha «V40 Lite(V2341)». Il codice va tolto dal nome —
        attaccato lo renderebbe un device diverso — ma conservato altrove."""
        self.assertIn("vivo V40 Lite", self.per_nome)
        voce = self.per_nome["vivo V40 Lite"]
        self.assertNotIn("(", voce.device)
        self.assertIn("V2341", voce.size_info)

    def test_finestra_di_supporto_conservata(self):
        """Fino a quando arrivano le patch è un dato operativo da QA, ed è
        nella stessa riga: sarebbe uno spreco buttarlo."""
        voce = self.per_nome["vivo X300 Ultra"]
        self.assertIn("07/2031", voce.size_info)
        self.assertIn("30 day", voce.size_info)

    def test_nessun_duplicato(self):
        nomi = [i.device for i in self.items]
        self.assertEqual(len(nomi), len(set(nomi)))


class TestRobustezza(unittest.TestCase):
    def test_pagina_senza_tabella_non_produce_nulla(self):
        self.assertEqual(sources.parse_vivo_aer("<html><body>ciao</body></html>"), [])

    def test_riga_incompleta_saltata_non_sollevata(self):
        html = ('<tr class="table-content"><td>&nbsp;X99</td>'
                '<td>End date: 01/2030</td></tr>')
        self.assertEqual(sources.parse_vivo_aer(html), [])

    def test_versione_implausibile_scartata(self):
        """Meglio un buco visibile che un dato falso: se la pagina
        dichiarasse Android 99, la voce non deve entrare in archivio."""
        html = ('<tr class="table-content"><td>&nbsp;X99</td>'
                '<td>End date: 01/2030</td>'
                '<td>Shipped version: Android 99 Future version: Android 100</td></tr>')
        self.assertEqual(sources.parse_vivo_aer(html), [])

    def test_testo_vuoto_gestito(self):
        self.assertEqual(sources.parse_vivo_aer(""), [])
        self.assertEqual(sources.parse_vivo_aer(None), [])


class TestRicercaPerModello(unittest.TestCase):
    """La fonte deve essere raggiungibile dalla ricerca, non solo dalla
    scansione periodica."""

    def setUp(self):
        self._originale = sources.http_get

        class Risposta:
            status_code = 200
            text = PAGINA

        sources.http_get = lambda url, timeout=None: Risposta()

    def tearDown(self):
        sources.http_get = self._originale

    def test_ricerca_per_nome_completo(self):
        trovati = sources._lookup_vivo("vivo X300 Ultra")
        self.assertTrue(trovati)
        self.assertEqual(trovati[0].device, "vivo X300 Ultra")

    def test_ricerca_senza_marca(self):
        trovati = sources._lookup_vivo("X300 Ultra")
        self.assertTrue(trovati, "«X300 Ultra» senza marca deve trovare lo stesso")

    def test_modello_inesistente(self):
        self.assertEqual(sources._lookup_vivo("Galaxy S24 Ultra"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
