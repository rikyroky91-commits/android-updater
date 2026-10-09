"""La classifica della corsa infinita del ring (09/10/2026).

A fine corsa il browser manda nome e punteggio a `/api/corsa/punteggio` e
rilegge i primi dieci da `/api/corsa/classifica`. Il punteggio lo calcola il
browser, quindi la rotta deve scartare quello che è fuori misura, i nomi che
non vanno, e chi manda troppe corse di fila.
"""
from __future__ import annotations

import os
import tempfile
import unittest


def _archivio_vuoto():
    cartella = tempfile.mkdtemp(prefix="classifica-")
    os.environ["DB_PATH"] = os.path.join(cartella, "test.db")
    from core import config as C
    C.DB_PATH = os.environ["DB_PATH"]
    from core import storage
    storage.reset_state()


def _corsa(**altro):
    dati = {"nome": "Riccardo", "punti": 4200, "round": 9, "personaggio": "robot", "stile": "guerrieri", "uccisi": 60, "durata": 400}
    dati.update(altro)
    return dati


class TestClassificaCorsa(unittest.TestCase):
    def setUp(self):
        _archivio_vuoto()
        from fastapi.testclient import TestClient

        from web import main
        main._CORSA_INVII.clear()
        self.main = main
        self.client = TestClient(main.app)

    def manda(self, ip="1.2.3.4", **altro):
        return self.client.post("/api/corsa/punteggio", json=_corsa(**altro), headers={"X-Forwarded-For": ip})

    def test_vuota_e_poi_ordinata_per_punti(self):
        r = self.client.get("/api/corsa/classifica")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"voci": []})
        self.assertEqual(r.headers["cache-control"], "no-store")
        self.assertEqual(self.manda(nome="Primo", punti=900, round=3, durata=60).json()["posizione"], 1)
        r2 = self.manda(nome="Secondo", punti=5000, round=10, durata=500).json()
        self.assertEqual(r2["posizione"], 1, "più punti: davanti a tutti")
        self.assertEqual([v["nome"] for v in r2["voci"]], ["Secondo", "Primo"])
        # A parità di punti è davanti chi c'era prima.
        self.assertEqual(self.manda(nome="Terzo", punti=900, round=3, durata=60).json()["posizione"], 3)
        voci = self.client.get("/api/corsa/classifica").json()["voci"]
        self.assertEqual([v["nome"] for v in voci], ["Secondo", "Primo", "Terzo"])
        self.assertEqual(set(voci[0]), {"id", "nome", "punti", "round", "personaggio", "stile", "quando"})

    def test_nomi_puliti(self):
        self.assertEqual(self.manda(nome="  Ricky   91 ").json()["voci"][0]["nome"], "Ricky 91")
        self.assertEqual(self.manda(nome="Élodie-Ñ").status_code, 200, "le lettere accentate vanno bene")
        for cattivo in ["", "   ", "x" * 17, "<script>", "a\x07b", "Cazzone", "F.U.C.K", "sh1t"]:
            self.assertEqual(self.manda(nome=cattivo, ip="9.9.9." + str(len(cattivo))).status_code, 422, repr(cattivo))

    def test_punteggi_fuori_misura(self):
        for male in [dict(punti=10**7), dict(round=0), dict(round=1000), dict(punti=-1), dict(durata=5, round=9),
                     dict(personaggio="drago"), dict(stile="ninja"), dict(punti="tanti")]:
            r = self.manda(ip="5.5.5." + str(len(str(male))), **male)
            self.assertIn(r.status_code, (400, 422), male)
        self.assertEqual(self.client.get("/api/corsa/classifica").json()["voci"], [])
        r = self.client.post("/api/corsa/punteggio", content="non è json", headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 400)

    def test_troppe_corse_dallo_stesso_indirizzo(self):
        for i in range(6):
            self.assertEqual(self.manda(ip="7.7.7.7", nome="Uno" + str(i)).status_code, 200)
        self.assertEqual(self.manda(ip="7.7.7.7", nome="Sette").status_code, 429)
        self.assertEqual(self.manda(ip="8.8.8.8", nome="Altro").status_code, 200, "un altro indirizzo passa")

    def test_la_tabella_non_cresce_senza_fine(self):
        from core import storage
        vecchio = storage.CLASSIFICA_TENUTI
        storage.CLASSIFICA_TENUTI = 5
        try:
            for i in range(9):
                storage.salva_punteggio_corsa("N" + str(i), 100 * i, 1, "mela")
            voci = storage.classifica_corsa(50)
            self.assertEqual(len(voci), 5)
            self.assertEqual(voci[0]["punti"], 800)
        finally:
            storage.CLASSIFICA_TENUTI = vecchio


if __name__ == "__main__":
    unittest.main()
