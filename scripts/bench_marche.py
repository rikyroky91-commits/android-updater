"""Banco di prova: ricerca, IMEI e scheda tecnica su N modelli per marca.

    python scripts/bench_marche.py --per-marca 40 --thread 4 --uscita bench.json

I modelli vengono dal catalogo TAC (`data/tac_completo.csv.gz`): i più
recenti per marca, uno per nome, ciascuno con un suo TAC. Così lo stesso
telefono serve a tutte e tre le prove, e l'IMEI di prova è costruito da un
TAC vero (TAC + sei cifre + cifra di controllo Luhn), non inventato.

VA ESEGUITO SU UNA COPIA DEL DATABASE, mai su quello di produzione: la
ricerca scrive in archivio ciò che trova. Esempio sul server Oracle:

    docker compose -f deploy/oracle/docker-compose.yml run --rm \
      -e DB_PATH=/tmp/bench.db -e BACKUP_GIST_ID= -e BACKUP_GITHUB_TOKEN= \
      -e TELEGRAM_TOKEN= web sh -c \
      "cp /home/app/archivio/tracker.db /tmp/bench.db && python scripts/bench_marche.py"

L'IMEI si prova SOLO in locale (`solo_locale=True`): il servizio TAC
esterno ha un piano gratuito da 100 richieste al mese, e un banco di prova
non deve consumarlo.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADICE)

# Marca del catalogo TAC → come la si riconosce nella risposta del sito.
MARCHE = {
    "SAMSUNG": ("samsung",),
    "APPLE": ("apple", "iphone", "ipad"),
    "GOOGLE": ("google", "pixel"),
    "XIAOMI": ("xiaomi", "redmi", "poco"),
    "MOTOROLA": ("motorola", "moto", "vivo / iqoo / motorola"),
    "OPPO": ("oppo",),
    "REALME": ("realme", "oppo / realme"),
    "ONEPLUS": ("oneplus", "oppo / realme / oneplus"),
    "VIVO": ("vivo", "iqoo"),
    "HONOR": ("honor", "huawei / honor"),
    "HUAWEI": ("huawei",),
    "NOTHING": ("nothing", "cmf", "altri brand"),
}

# La prima parola del nome, come la scriverebbe chi cerca. Le righe del
# catalogo con davanti l'operatore («At&T Galaxy Note», «2Degrees Galaxy
# J2») sono nomi che nessuno digita: misurarle abbassava i numeri per un
# motivo che con la ricerca vera non c'entra.
PRIME_PAROLE = {
    "SAMSUNG": {"samsung", "galaxy"}, "APPLE": {"apple", "iphone"},
    "GOOGLE": {"google", "pixel"}, "XIAOMI": {"xiaomi", "redmi", "poco"},
    "MOTOROLA": {"motorola", "moto"}, "OPPO": {"oppo"}, "REALME": {"realme"},
    "ONEPLUS": {"oneplus", "1+"}, "VIVO": {"vivo", "iqoo"},
    "HONOR": {"honor"}, "HUAWEI": {"huawei"}, "NOTHING": {"nothing", "cmf"},
}

_ANNO_RE = re.compile(r"\b(20[12]\d)\b")
_NON_TELEFONI = re.compile(r"\b(watch|band|buds|tab|pad|tv|router|laptop|book|glass|ring)\b", re.I)


def luhn_imei(tac: str, seriale: str = "123456") -> str:
    corpo = (tac + seriale)[:14]
    somma = 0
    for i, c in enumerate(corpo):
        n = int(c)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        somma += n
    return corpo + str((10 - somma % 10) % 10)


def modelli_per_marca(per_marca: int, anno_minimo: int) -> dict[str, list[dict]]:
    percorso = os.path.join(RADICE, "data", "tac_completo.csv.gz")
    with gzip.open(percorso, "rb") as f:
        righe = list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")))
    scelti: dict[str, dict[str, dict]] = {m: {} for m in MARCHE}
    for riga in righe:
        marca = (riga.get("Brand") or "").strip().upper()
        if marca not in scelti:
            continue
        specs = riga.get("SPECS") or ""
        anno = _ANNO_RE.search(specs)
        anno = int(anno.group(1)) if anno else 0
        # Senza anno si tiene lo stesso, in coda: per HONOR, vivo e realme
        # le righe recenti spesso non lo scrivono, e scartarle lasciava
        # quelle marche sotto i 40 modelli.
        if anno and anno < anno_minimo:
            continue
        nome = specs.split(",")[0].strip()
        # Il catalogo scrive la marca in testa al nome: si tiene così, è
        # anche il modo in cui una persona lo cercherebbe.
        if not nome or len(nome) < 5 or _NON_TELEFONI.search(nome):
            continue
        if nome.split()[0].lower() not in PRIME_PAROLE[marca]:
            continue
        chiave = nome.upper()
        if chiave not in scelti[marca]:
            scelti[marca][chiave] = {"marca": marca, "nome": nome.title(),
                                     "tac": riga["TAC"], "anno": anno}
    uscita = {}
    for marca, per_nome in scelti.items():
        elenco = sorted(per_nome.values(), key=lambda r: (-r["anno"], r["nome"]))
        uscita[marca] = elenco[:per_marca]
    return uscita


def marca_coerente(marca_attesa: str, testo: str) -> bool:
    testo = (testo or "").lower()
    return any(p in testo for p in MARCHE[marca_attesa])


def prova(modello: dict) -> dict:
    from core import imeicheck
    from web import main

    esito = dict(modello)
    # --- ricerca ---
    t = time.monotonic()
    try:
        r = main._cerca_davvero(modello["nome"])
        esito["ricerca_trovato"] = bool(r.get("trovato"))
        esito["ricerca_nome"] = r.get("nome") or ""
        esito["ricerca_firmware"] = bool(r.get("trovato")) and not r.get("senza_firmware")
        esito["ricerca_tipo"] = r.get("tipo_versione") or ""
        esito["ricerca_riga"] = (r.get("riga") or "")[:120]
        esito["ricerca_fonte"] = r.get("fonte") or ""
        # `scheda` è SEMPRE un dizionario, anche quando non è stata trovata:
        # contarlo come vero dava il 100% ovunque nella prima prova.
        esito["scheda"] = bool((r.get("scheda") or {}).get("trovata"))
        esito["ricerca_errore"] = r.get("errore") or ""
    except Exception as errore:  # pragma: no cover - si registra, non si ferma
        esito.update(ricerca_trovato=False, ricerca_firmware=False, scheda=False,
                     ricerca_errore=f"eccezione: {errore}")
    esito["ricerca_secondi"] = round(time.monotonic() - t, 1)

    # --- scheda tecnica, anche per nome da solo ---
    if not esito.get("scheda"):
        try:
            from core import specs
            esito["scheda_diretta"] = bool(specs.cerca(modello["nome"]))
        except Exception:
            esito["scheda_diretta"] = False

    # --- IMEI ---
    imei = luhn_imei(modello["tac"])
    try:
        trovato = imeicheck.identify(imei, solo_locale=True)
        esito["imei_trovato"] = bool(trovato)
        esito["imei_marca_ok"] = bool(trovato) and marca_coerente(
            modello["marca"], " ".join(str(x) for x in trovato))
        esito["imei_risposta"] = " ".join(str(x) for x in trovato)[:100] if trovato else ""
    except Exception as errore:
        esito.update(imei_trovato=False, imei_marca_ok=False, imei_risposta=f"eccezione: {errore}")
    return esito


def riepilogo(esiti: list[dict]) -> str:
    righe = ["marca      n  trovato  firmware  scheda  imei_ok  sec_medi"]
    per_marca: dict[str, list[dict]] = {}
    for e in esiti:
        per_marca.setdefault(e["marca"], []).append(e)
    for marca in MARCHE:
        el = per_marca.get(marca) or []
        if not el:
            continue
        n = len(el)

        def pct(chiave):
            return f"{100 * sum(1 for e in el if e.get(chiave)) // n:>3}%"

        scheda = sum(1 for e in el if e.get("scheda") or e.get("scheda_diretta"))
        medi = sum(e.get("ricerca_secondi", 0) for e in el) / n
        righe.append(f"{marca:<9} {n:>2}    {pct('ricerca_trovato')}     {pct('ricerca_firmware')}"
                     f"    {100 * scheda // n:>3}%     {pct('imei_marca_ok')}    {medi:5.1f}")
    return "\n".join(righe)


def main_cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--per-marca", type=int, default=40)
    p.add_argument("--anno-minimo", type=int, default=2021)
    p.add_argument("--thread", type=int, default=1)
    p.add_argument("--uscita", default="bench.json")
    p.add_argument("--marche", default="", help="es. SAMSUNG,NOTHING")
    a = p.parse_args()

    # Niente scansione in sottofondo: nello stesso processo si contende
    # database e cataloghi con le ricerche, e la prima prova del 26/09/2026
    # si è fermata a 20 modelli su 442 con la CPU a zero.
    os.environ["AVVIA_WORKER"] = "false"
    # Se si blocca di nuovo, ogni 5 minuti lo stato di tutti i thread
    # finisce nel log invece di un silenzio indistinguibile dal lavoro.
    import faulthandler
    faulthandler.dump_traceback_later(300, repeat=True)
    from web import main
    main.avvio()

    modelli = modelli_per_marca(a.per_marca, a.anno_minimo)
    if a.marche:
        vuote = {m.strip().upper() for m in a.marche.split(",")}
        modelli = {m: v for m, v in modelli.items() if m in vuote}
    tutti = [m for elenco in modelli.values() for m in elenco]
    print(f"{len(tutti)} modelli: " + ", ".join(f"{k} {len(v)}" for k, v in modelli.items()),
          flush=True)

    esiti = []
    inizio = time.monotonic()
    with ThreadPoolExecutor(max_workers=a.thread) as pool:
        futuri = [pool.submit(prova, m) for m in tutti]
        for i, f in enumerate(as_completed(futuri), 1):
            esiti.append(f.result())
            if i % 20 == 0:
                print(f"  {i}/{len(tutti)} in {time.monotonic() - inizio:.0f}s", flush=True)
                try:
                    with open(a.uscita, "w", encoding="utf-8") as out:
                        json.dump(esiti, out, ensure_ascii=False, indent=1)
                except OSError as errore:
                    print(f"  salvataggio parziale non riuscito: {errore}", flush=True)
    with open(a.uscita, "w", encoding="utf-8") as out:
        json.dump(esiti, out, ensure_ascii=False, indent=1)
    print(riepilogo(esiti))


if __name__ == "__main__":
    main_cli()
