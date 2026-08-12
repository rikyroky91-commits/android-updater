"""Lo stesso telefono scritto in modi diversi deve dare la stessa risposta.

## La misura da cui nasce questo file

Interrogando il sito vero, il 2026-08-10, con le forme che una persona
digita davvero. Nove gruppi, una marca per riga, **cinque incoerenti**:

    Redmi Note 13  → «Redmi Note 13 NFC EEA»   redmi note13 → nessun firmware
    Redmi 13       → «Redmi 13 / POCO M6 EEA»  redmi13      → «Redmi 13»
    realme C63     → «realme C61»              RMX3939      → «C61»
    Moto G14       → «Moto G14»                motorola g14 → «Motorola G14»
    Pixel 9        → «Pixel 9»                 pixel9       → «Google Pixel 9»

Due cause distinte, e vale la pena tenerle separate perché si correggono
in posti diversi:

1. **Lo spazio fra lettere e cifre.** «redmi note13» e «pixel9» non
   arrivavano a nessuna fonte: la forma con lo spazio sì. Corretto in
   `sources.expand_query`, che ora prova entrambe.
2. **Il nome lo sceglieva chi rispondeva.** Strade diverse arrivavano a
   fonti diverse, e ognuna scriveva il telefono a modo suo. Corretto in
   `web.main`, dove il nome mostrato lo decide l'archivio — ma **solo
   quando è lo stesso telefono**, verificato sulla chiave di dispositivo.

Il secondo punto è quello delicato: la prima versione adottava il nome
di qualunque dispositivo l'archivio restituisse per quel testo, e
«Pixel 9» ha cominciato a rispondere «Google Pixel 9a» — un telefono
diverso, con un altro chip. Coerente e sbagliato, che è il modo peggiore
di essere coerenti. C'è un test apposta più sotto.

Qui non si tocca la rete: si collauda il MECCANISMO, cioè quali forme
vengono provate e quale nome vince. La prova sul campo, con la rete
vera, sta nella misura qui sopra.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["AVVIA_WORKER"] = "0"

from core import config as C, extract, sources, storage  # noqa: E402


class TestSpazioFraLettereECifre(unittest.TestCase):
    """«redmi note13» e «Redmi Note 13» sono la stessa domanda."""

    def _forme(self, query: str) -> set[str]:
        return {f.lower() for f in sources.expand_query(query)}

    def test_la_forma_attaccata_arriva_a_quella_staccata(self):
        for attaccata, staccata in (("redmi note13", "redmi note 13"),
                                    ("pixel9", "pixel 9"),
                                    ("redmi13", "redmi 13")):
            with self.subTest(query=attaccata):
                self.assertIn(staccata, self._forme(attaccata))

    def test_e_viceversa(self):
        """L'incoerenza andava nei due versi: «moto g 14» deve arrivare a
        «Moto G14» tanto quanto il contrario."""
        self.assertIn("redmi note13", self._forme("redmi note 13"))
        self.assertIn("pixel9", self._forme("pixel 9"))

    def test_il_testo_digitato_resta_il_primo(self):
        """Le forme derivate sono un ripiego, non un sostituto: se quella
        scritta risponde, risponde per prima."""
        self.assertEqual(sources.expand_query("redmi note13")[0], "redmi note13")

    def test_una_sigla_di_una_lettera_non_viene_spezzata(self):
        """Separare `A32` in `A 32` produrrebbe una sigla che non esiste,
        e quella strada è già coperta da `_nomi_da_sigla_corta`."""
        self.assertNotIn("a 32", self._forme("A32"))
        self.assertNotIn("s 24", self._forme("S24"))

    def test_nessun_doppione(self):
        forme = sources.expand_query("redmi note 13")
        self.assertEqual(len(forme), len({f.lower() for f in forme}))


class BaseArchivio(unittest.TestCase):
    def setUp(self):
        self._db_originale = C.DB_PATH
        self._db = tempfile.mktemp(suffix=".db")
        C.DB_PATH = self._db
        storage.reset_state()
        storage.init_db()

    def tearDown(self):
        storage.reset_state()
        for coda in ("", "-wal", "-shm"):
            try:
                os.remove(self._db + coda)
            except OSError:
                pass
        C.DB_PATH = self._db_originale

    def _dispositivo(self, brand: str, modello: str, build: str = "B1"):
        storage.upsert_update({
            "id": f"{modello}|{build}",
            "device_key": extract.device_key(brand, modello),
            "brand": brand, "device_model": modello, "title": modello,
            "build": build, "os_version": "Android 16", "android_version": 16,
            "severity": C.SEV_SECURITY, "color": "#00CC66",
            "source": "official_lookup", "source_label": "Fonte ufficiale",
            "source_trust": C.TRUST_STRUCTURED, "is_relevant": 1,
            "published": "2026-07-01T10:00:00+00:00",
        })


class TestIlNomeLoDecideLArchivio(BaseArchivio):
    """Ma solo quando è lo stesso telefono."""

    def test_le_grafie_convergono_sul_nome_dell_archivio(self):
        from web import main as M

        self._dispositivo(C.PIXEL, "Pixel 9")
        _storico, _chiave, nome = M._storico_del_modello("Google Pixel 9", C.PIXEL)
        self.assertEqual(nome, "Pixel 9")

    def test_un_telefono_diverso_non_presta_il_suo_nome(self):
        """IL TEST PIÙ IMPORTANTE DEL FILE.

        La ricerca per nome è tollerante di proposito, quindi «Pixel 9»
        riporta anche il **Pixel 9a**. Adottarne il nome significava
        rispondere «Pixel 9a» a chi aveva chiesto il 9: un telefono
        diverso, con un altro chip. Il confronto è sulla chiave di
        dispositivo, cioè la stessa regola con cui l'archivio decide che
        due nomi sono un telefono solo.
        """
        from web import main as M

        self._dispositivo(C.PIXEL, "Pixel 9a")
        _storico, _chiave, nome = M._storico_del_modello("Pixel 9", C.PIXEL)
        self.assertNotEqual(nome, "Pixel 9a")

    def test_senza_archivio_resta_il_nome_della_fonte(self):
        """Inventare un nome sarebbe peggio che mostrarne uno imperfetto."""
        from web import main as M

        _storico, _chiave, nome = M._storico_del_modello("Telefono Ignoto 9", C.OTHER)
        self.assertEqual(nome, "")

    def test_lo_storico_scarta_le_righe_senza_niente_dentro(self):
        """Dodici righe con versione, build e patch tutte a trattino
        facevano sembrare rotta la pagina: erano notizie senza numero di
        build, che infatti compaiono già fra le notizie."""
        from web import main as M

        storage.upsert_update({
            "id": "solo-notizia", "device_key": extract.device_key(C.SAMSUNG, "Galaxy S24"),
            "brand": C.SAMSUNG, "device_model": "Galaxy S24",
            "title": "Un articolo che parla del Galaxy S24",
            "severity": C.SEV_SECURITY, "color": "#00CC66",
            "source": "live_search", "source_label": "Ricerca live",
            "source_trust": C.TRUST_NOISY, "is_relevant": 1,
            "published": "2026-07-01T10:00:00+00:00",
        })
        storico, _chiave, _nome = M._storico_del_modello("Galaxy S24", C.SAMSUNG)
        self.assertEqual(storico, [])


class TestForseCercavi(BaseArchivio):
    """Due domande diverse, due attrezzi diversi."""

    def test_quando_trova_propone_le_varianti_dello_stesso_modello(self):
        from web import main as M

        proposte = M._forse_cercavi("galaxy s24", "Galaxy S24", C.SAMSUNG, True)
        self.assertTrue(proposte, "nessuna variante proposta")
        self.assertTrue(any("S24" in p for p in proposte), proposte)

    def test_non_propone_il_telefono_che_si_sta_guardando(self):
        """Un suggerimento che rimanda a sé stesso non è un suggerimento.
        Vale sia per il nome trovato sia per quello che si è scritto."""
        from web import main as M

        proposte = M._forse_cercavi("Galaxy S24", "Galaxy S24", C.SAMSUNG, True)
        for voce in proposte:
            with self.subTest(voce=voce):
                self.assertNotEqual(extract.device_key(C.SAMSUNG, voce),
                                    extract.device_key(C.SAMSUNG, "Galaxy S24"))

    def test_quando_non_trova_corregge_il_refuso(self):
        from web import main as M

        proposte = M._forse_cercavi("galaxi s24", "galaxi s24", "", False)
        self.assertTrue(any("S24" in p for p in proposte), proposte)

    def test_non_propone_mai_quello_che_si_e_scritto(self):
        from web import main as M

        for trovato in (True, False):
            with self.subTest(trovato=trovato):
                proposte = M._forse_cercavi("SM-S921B", "SM-S921B", C.SAMSUNG, trovato)
                self.assertNotIn("SM-S921B", proposte)


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)


class TestLaMarcaChiestaValeOvunque(BaseArchivio):
    """«Xiaomi 14» rispondeva «真我 14», che è un realme.

    `codes_for_name` è tollerante di proposito, e su un nome corto
    restituisce codici di marche diverse: per «Xiaomi 14» il PRIMO è
    `RMX5075`. La ragione è che la chiave normalizzata di «Xiaomi 14» e
    quella di «真我 14» sono entrambe `14` — la marca esce dalla chiave e
    i caratteri cinesi pure.

    Il filtro esisteva in `forme_equivalenti` e mancava nei due punti che
    non passano di là. È l'errore 51b: una correzione applicata in un
    posto e non cercata negli altri.
    """

    def test_una_forma_di_un_altra_marca_viene_scartata(self):
        from core import scan

        forme = scan.forme_equivalenti("Xiaomi 14")
        for forma in forme[1:]:
            with self.subTest(forma=forma):
                marca = scan._marca_della_forma(forma)
                self.assertIn(marca, (None, C.XIAOMI),
                              f"«{forma}» è di un'altra marca")

    def test_il_nome_cinese_e_riconosciuto_come_marca(self):
        """`detect_brand` non sa leggere «真我», e una forma senza marca
        riconoscibile passava il filtro. `gruppo_di_marca` i nomi cinesi
        li conosce."""
        from core import scan

        self.assertEqual(scan._marca_della_forma("真我 14"), C.OPPO)
        self.assertEqual(scan._marca_della_forma("三星 Galaxy S24"), C.SAMSUNG)
        self.assertIsNone(scan._marca_della_forma("Telefono Ignoto 9"))

    def test_il_ripiego_per_codice_rispetta_la_marca(self):
        """`_identifica_senza_firmware` prendeva il primo codice che
        risolveva, senza guardare di chi fosse."""
        from core import scan

        voci = scan._identifica_senza_firmware("Xiaomi 14")
        if voci:
            self.assertNotIn("真我", voci[0]["device_model"])

    def test_la_marca_al_posto_della_gamma(self):
        """«samsung s23 ultra» non arrivava a nessun codice, mentre
        «galaxy s23 ultra» sì: il catalogo scrive «Galaxy», chi cerca
        scrive «samsung»."""
        from core import sources

        forme = {f.lower() for f in sources.expand_query("samsung s23 ultra")}
        self.assertIn("galaxy s23 ultra", forme)
