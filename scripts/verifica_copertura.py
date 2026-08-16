"""Banco di prova: 10 modelli per marca, la catena intera.

**Perché è uno script e non un test.** Ogni riga qui dipende dalla rete e
da cataloghi che cambiano da soli: un `pytest` che interroga Google News
e GSMArena sarebbe rosso il giorno che una fonte è lenta, e verde il
giorno dopo senza che nessuno abbia toccato niente — cioè un test che
non dice nulla sul codice. I test veri stanno in `tests/`, con le fonti
sostituite da doppi. Questo invece MISURA la realtà: quanta copertura
c'è davvero, adesso, sui modelli che una persona cercherebbe.

**Cosa verifica**, per ogni modello, nell'ordine in cui una persona lo
farebbe:

1. il codice modello esiste nei cataloghi e si risolve nel nome giusto
   (`modelcodes.resolve`) — è la ricerca «per codice modello»;
2. cercando quel codice si ottiene un firmware (versione, build o patch);
3. la scheda tecnica ha almeno il processore o lo schermo;
4. c'è una foto del modello.

Uso:
    python scripts/verifica_copertura.py            # tutte le marche
    python scripts/verifica_copertura.py samsung    # una sola
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# I dieci modelli per marca sono scelti fra quelli che una persona cerca
# davvero — ammiraglie e fasce medie recenti — non pescati a caso dal
# catalogo: un codice di un modello venduto in un solo mercato nel 2019
# fallirebbe per motivi che non dicono niente sulla salute del progetto.
MODELLI: dict[str, list[str]] = {
    "samsung": [
        "Galaxy S24 Ultra", "Galaxy S24", "Galaxy S23 Ultra", "Galaxy S23",
        "Galaxy A55", "Galaxy A54", "Galaxy A35", "Galaxy A15",
        "Galaxy Z Fold5", "Galaxy Z Flip5",
    ],
    "motorola": [
        "Moto G85", "Edge 50 Pro", "Edge 50 Fusion", "Moto G54", "Moto G84",
        "Razr 50", "Edge 40 Neo", "Moto G24", "Moto G04", "Edge 40",
    ],
    "xiaomi": [
        "Xiaomi 14", "Xiaomi 14 Ultra", "Xiaomi 14T", "Xiaomi 13T Pro",
        "Xiaomi 13", "Xiaomi 13T", "Xiaomi 12T", "Xiaomi 12",
        "Xiaomi 11T", "Xiaomi 14T Pro",
    ],
    "realme": [
        "realme 12 Pro", "realme 12 Pro+", "realme 11 Pro", "realme GT 6",
        "realme C67", "realme 13 Pro", "realme 10", "realme 9",
        "realme GT Neo 5", "realme C55",
    ],
    "huawei": [
        "P60 Pro", "Mate 60 Pro", "P50 Pro", "Mate 50 Pro", "Nova 12",
        "Mate X5", "P40 Pro", "Nova 11", "Mate 40 Pro", "P30 Pro",
    ],
    "redmi": [
        "Redmi Note 13 Pro", "Redmi Note 13", "Redmi Note 12 Pro", "Redmi 13C",
        "Redmi Note 12", "Redmi K70", "Redmi 12", "Redmi Note 11",
        "Redmi A3", "Redmi Note 14",
    ],
    "honor": [
        "Honor Magic6 Pro", "Honor Magic5 Pro", "Honor 90", "Honor X9b",
        "Honor Magic V2", "Honor 200", "Honor X8b", "Honor 70",
        "Honor Magic4 Pro", "Honor X7b",
    ],
    "vivo": [
        "vivo X100", "vivo X100 Pro", "vivo V30", "vivo Y36", "vivo X90",
        "vivo V29", "vivo Y27", "vivo X80", "vivo V27", "vivo Y100",
    ],
}

# Come si riconosce il codice DELLA MARCA GIUSTA fra i candidati che il
# catalogo restituisce per un nome. Serve perché la ricerca per nome è
# sfocata: `codes_for_name("Xiaomi 14")` propone anche `RMX5075`, che è
# un codice realme.
import re

FORMA_CODICE = {
    "samsung": re.compile(r"^SM-[A-Z0-9]+$", re.I),
    "motorola": re.compile(r"^XT\d{3,4}-?\d*$", re.I),
    "xiaomi": re.compile(r"^2[0-9]{3}[A-Z0-9]{4,}$", re.I),
    "realme": re.compile(r"^RMX\d{4}", re.I),
    "huawei": re.compile(r"^[A-Z]{3}-[A-Z0-9]{2,5}$", re.I),
    "redmi": re.compile(r"^2[0-9]{3}[A-Z0-9]{4,}$", re.I),
    "honor": re.compile(r"^[A-Z]{3}-[A-Z0-9]{2,5}$", re.I),
    "vivo": re.compile(r"^(V\d{4}[A-Z]*|PD\d{4}[A-Z]*)$", re.I),
}


def codice_per(marca: str, nome: str) -> str | None:
    """Lo stesso percorso che segue l'applicazione, non uno inventato qui.

    Per Motorola in particolare: `sources.py` interroga PRIMA il catalogo
    dedicato (`motorola_catalog`, costruito dalla pagina ufficiale dei
    codici XT) e solo dopo l'indice generale. Misurare senza quello
    dichiarava «nessun codice» per sei modelli su sette che il progetto
    invece conosce benissimo — un dato falso sulla salute del progetto,
    prodotto dal banco di prova e non dal codice.
    """
    from core import modelcodes

    forma = FORMA_CODICE[marca]
    candidati: list[str] = []
    if marca == "motorola":
        from core import motorola_catalog

        candidati.extend(motorola_catalog.codes_for_name(nome))
    candidati.extend(modelcodes.codes_for_name(nome))
    for codice in candidati:
        if forma.match(codice):
            return codice
    return None


def _ha_firmware(risultato: dict) -> bool:
    for voce in risultato.get("items", []):
        if voce.get("os_version") or voce.get("build") or voce.get("patch_level"):
            return True
    return False


def _nome_coerente(atteso: str, nomi: list[str]) -> bool:
    """Il codice deve risolvere in QUEL modello, non in uno qualsiasi.
    Confronto sulle sole cifre e lettere, perché «Galaxy Z Fold5»,
    «Galaxy Z Fold 5» e «Z Fold5» sono lo stesso telefono scritto in tre
    modi da tre cataloghi diversi."""
    def piatto(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    a = piatto(atteso)
    return any(a in piatto(n) or piatto(n) in a for n in nomi if n)


def prova_modello(marca: str, nome: str) -> dict:
    from core import modelcodes, scan
    from web import presenters as P

    esito = {"marca": marca, "nome": nome, "codice": None,
             "codice_ok": False, "nome_ok": False, "firmware": False,
             "scheda": False, "foto": False, "errore": ""}
    try:
        codice = codice_per(marca, nome)
        esito["codice"] = codice
        if not codice:
            esito["errore"] = "nessun codice di questa marca nel catalogo"
            return esito
        esito["codice_ok"] = True

        nomi = modelcodes.resolve(codice)
        esito["nome_ok"] = _nome_coerente(nome, nomi)

        risultato = scan.search_model(codice)
        esito["firmware"] = _ha_firmware(risultato)

        scheda = P.scheda_tecnica(nome, codice=codice, brand=marca)
        # «trovata» da sola non basta: dice che una scheda esiste, non che
        # abbia dentro qualcosa di utile. Si guarda il contenuto vero —
        # processore o almeno una voce compilata.
        esito["scheda"] = bool(scheda.get("cpu") or scheda.get("voci"))
        esito["foto"] = bool(scheda.get("foto"))
    except Exception as exc:  # una marca che esplode non deve fermare le altre
        esito["errore"] = f"{type(exc).__name__}: {exc}"
    return esito


def main() -> int:
    os.environ.setdefault("AVVIA_WORKER", "0")
    from core import storage

    storage.init_db()

    marche = sys.argv[1:] or list(MODELLI)
    tutti: list[dict] = []
    for marca in marche:
        if marca not in MODELLI:
            print(f"marca sconosciuta: {marca}")
            return 2
        print(f"\n=== {marca.upper()} ===")
        print(f"{'modello':22} {'codice':16} nome fw sch foto")
        for nome in MODELLI[marca]:
            esito = prova_modello(marca, nome)
            tutti.append(esito)
            segno = lambda b: "ok" if b else "--"
            print(f"{nome:22} {str(esito['codice'] or '-'):16} "
                  f"{segno(esito['nome_ok']):4} {segno(esito['firmware']):3} "
                  f"{segno(esito['scheda']):3} {segno(esito['foto']):4}"
                  f"{'  ' + esito['errore'] if esito['errore'] else ''}")
            time.sleep(0.5)  # non martellare le fonti

    print("\n=== RIEPILOGO ===")
    print(f"{'marca':10} {'codice':>7} {'nome':>6} {'firmware':>9} "
          f"{'scheda':>7} {'foto':>5}")
    for marca in marche:
        righe = [e for e in tutti if e["marca"] == marca]
        n = len(righe)
        def q(campo):
            return f"{sum(1 for e in righe if e[campo])}/{n}"
        print(f"{marca:10} {q('codice_ok'):>7} {q('nome_ok'):>6} "
              f"{q('firmware'):>9} {q('scheda'):>7} {q('foto'):>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
