"""Registra dalle fonti vere i cataloghi grossi che servono ai test.

## Perché esiste

Tre cataloghi non sono «una fonte fra le tante» per la suite: sono
l'anagrafica su cui poggia tutto il resto. I codici modello
(`core/modelcodes.py`, due dataset pubblici da diversi megabyte) dicono
che `SM-A546B` è un Galaxy A54; il catalogo Xiaomi dice quali varianti
regionali esistono di uno stesso codice. Finché i test se li scaricavano
dal vivo, ogni esecuzione della suite raccontava una cosa diversa: verde
con la rete, rossa senza, e rossa in modo nuovo il giorno che una fonte
rispondeva `HTTP 429`. Sette test su milletrecento cambiavano esito senza
che nessuno avesse toccato una riga di codice, e altri due si
autoescludevano in silenzio.

Il rimedio non è inventare i dati a mano. **Un parser collaudato su dati
inventati collauda l'immaginazione di chi ha scritto il test**: le forme
che contano — il BOM del primo CSV, l'UTF-16 del secondo, le colonne
`Retail Branding`/`Marketing Name` che a volte ripetono la marca, i nomi
regionali del catalogo Xiaomi — sono esattamente quelle che una versione
inventata semplificherebbe. Qui si registrano le RIGHE VERE, nel loro
formato vero, limitate a ciò che la suite interroga.

## Che cosa produce

    tests/fixtures/codici_mobilemodels.csv   (UTF-8 con BOM, come l'originale)
    tests/fixtures/codici_google_play.csv    (UTF-16, come l'originale)
    tests/fixtures/xiaomi_latest.yml         (YAML, la famiglia Xiaomi 12)

I primi due restano file interi e leggibili, non compressi:
`modelcodes._download` riceve dai test gli stessi byte che riceverebbe
dalla rete, quindi il percorso collaudato è quello di produzione —
controllo di lunghezza minima compreso.

## Da dove viene l'elenco delle domande

`tests/fixtures/codici_richiesti.txt`, che NON è scritto a mano: è ciò che
la suite ha davvero chiesto a `modelcodes`, raccolto avvolgendo le sue
quattro funzioni pubbliche di interrogazione e facendo girare tutti i
test. Per rigenerarlo, dopo aver aggiunto test che interrogano codici
nuovi:

    1. avvolgi `modelcodes.resolve`, `codes_for_name`, `marca_dichiarata`
       e `nome_canonico` con una funzione che annota l'argomento;
    2. lancia la suite con `TEST_CON_RETE=1`;
    3. scrivi gli argomenti raccolti, uno per riga, nel file.

Un codice che nessuno chiede non serve; un codice chiesto e non registrato
si nota subito, perché il test che lo interroga smette di trovarlo.

## Quando rilanciarlo

    python scripts/registra_fixture_cataloghi.py

Dopo aver ampliato l'elenco delle domande, o quando serve una fotografia
più recente dei cataloghi. I file prodotti vanno committati: sono la
baseline che rende la suite indipendente dalla rete.
"""
from __future__ import annotations

import csv
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("AVVIA_WORKER", "0")

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from core import config as C  # noqa: E402
from core import modelcodes, sources, storage  # noqa: E402

CARTELLA_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures")
FILE_DOMANDE = os.path.join(CARTELLA_FIXTURE, "codici_richiesti.txt")
FILE_MOBILEMODELS = os.path.join(CARTELLA_FIXTURE, "codici_mobilemodels.csv")
FILE_GOOGLE_PLAY = os.path.join(CARTELLA_FIXTURE, "codici_google_play.csv")
FILE_XIAOMI = os.path.join(CARTELLA_FIXTURE, "xiaomi_latest.yml")

# LA FAMIGLIA INTERA, NON LE TRE RIGHE CHE SERVONO AL TEST. Il catalogo
# Xiaomi elenca lo stesso telefono una volta per mercato, e ciò che i test
# verificano è proprio la SCELTA fra quelle righe: che «Xiaomi 12» non
# risponda con un 12 Pro, un 12T o un 12X, e che fra le sue varianti esca
# per prima quella europea. Registrare solo le tre righe giuste
# significherebbe togliere dal banco di prova tutti i modi di sbagliare.
PREFISSO_XIAOMI = "Xiaomi 12"


def leggi_domande() -> list[str]:
    """Le interrogazioni che la suite rivolge a `modelcodes`, una per riga."""
    with open(FILE_DOMANDE, encoding="utf-8") as f:
        return [r.strip() for r in f
                if r.strip() and not r.lstrip().startswith("#")]


def codici_da_tenere(indice: dict[str, list[str]], domande: list[str]) -> set[str]:
    """I codici che rispondono alle domande della suite, gemelli compresi.

    Due passaggi, e il secondo non è un lusso. Una ricerca per nome
    (`codes_for_name`) e i «gemelli» di un codice — le varianti regionali
    dello stesso hardware, vedi `web.main._nomi_gemelli` — partono da un
    nome per tornare ad ALTRI codici: registrare solo i codici chiesti
    direttamente lascerebbe fuori proprio le righe che quelle funzioni
    esistono per trovare, e i test le vedrebbero rispondere a metà.
    """
    diretti: set[str] = set()
    for domanda in domande:
        for forma in [domanda] + modelcodes._varianti_senza_spazi(domanda):
            codice = forma.strip().upper()
            if codice in indice:
                diretti.add(codice)
        for codice in modelcodes.codes_for_name(domanda):
            diretti.add(codice.strip().upper())

    con_gemelli = set(diretti)
    for codice in diretti:
        for nome in indice.get(codice, []):
            for gemello in modelcodes.codes_for_name(nome):
                con_gemelli.add(gemello.strip().upper())
    return con_gemelli


def _sottoinsieme(testo: str, tenuti: set[str], colonne: tuple[str, ...],
                  fine_riga: str) -> tuple[str, int, int]:
    """Le righe del CSV il cui codice è fra quelli da tenere.

    Si riscrive col modulo `csv` invece di ritagliare le righe del testo
    originale perché un campo può contenere una virgola o un a capo fra
    virgolette: tagliare a mano produrrebbe un file che si legge storto
    solo su quelle righe, cioè il tipo di guasto che non si nota.
    """
    righe = list(csv.DictReader(io.StringIO(testo)))
    if not righe:
        return "", 0, 0
    fuori = io.StringIO()
    scrittore = csv.DictWriter(fuori, fieldnames=list(righe[0].keys()),
                               lineterminator=fine_riga)
    scrittore.writeheader()
    tenute = 0
    for riga in righe:
        if any((riga.get(colonna) or "").strip().upper() in tenuti
               for colonna in colonne):
            scrittore.writerow(riga)
            tenute += 1
    return fuori.getvalue(), tenute, len(righe)


def registra_xiaomi() -> int:
    """Le righe vere del catalogo Xiaomi per la famiglia `PREFISSO_XIAOMI`.

    Il file si riscrive dal dato già interpretato invece di ritagliare il
    testo originale: in YAML una voce non è una riga — ha campi su più
    righe e rientri che contano — e ritagliarla a occhio produrrebbe un
    file che si carica a metà. I valori restano quelli scaricati, cambia
    solo l'impaginazione.
    """
    if yaml is None:
        print("pyyaml non è installata: fixture Xiaomi non aggiornata")
        return 1
    try:
        risposta = sources.http_get(sources.XIAOMI_YAML_URLS[0], timeout=C.HTTP_TIMEOUT + 60)
    except Exception as errore:
        print(f"catalogo Xiaomi non raggiungibile ({errore}): fixture non aggiornata")
        return 1
    if risposta.status_code != 200:
        print(f"catalogo Xiaomi: HTTP {risposta.status_code}, fixture non aggiornata")
        return 1

    voci = yaml.safe_load(risposta.text)
    if not isinstance(voci, list):
        print("catalogo Xiaomi: formato inatteso, fixture non aggiornata")
        return 1
    tenute = [v for v in voci
              if isinstance(v, dict)
              and str(v.get("name") or "").startswith(PREFISSO_XIAOMI)]
    if not tenute:
        print(f"catalogo Xiaomi: nessuna voce «{PREFISSO_XIAOMI}», "
              "fixture non aggiornata")
        return 1

    testo = yaml.safe_dump(tenute, allow_unicode=True, sort_keys=True,
                           default_flow_style=False)
    with open(FILE_XIAOMI, "w", encoding="utf-8", newline="\n") as f:
        f.write(testo)
    nomi = len({v.get("name") for v in tenute})
    print(f"Xiaomi: {len(tenute)} voci su {len(voci)}, {nomi} varianti → {FILE_XIAOMI}")
    return 0


def main() -> int:
    os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "registra.db"))
    C.DB_PATH = os.environ["DB_PATH"]
    storage.init_db()

    domande = leggi_domande()
    if not domande:
        print(f"{FILE_DOMANDE} è vuoto: non c'è niente da registrare")
        return 1

    grezzo = {
        "mobilemodels": modelcodes._download(modelcodes.MOBILEMODELS_URL, "mobilemodels"),
        "google_play": modelcodes._download(modelcodes.GOOGLE_PLAY_URL, "google_play"),
    }
    mancanti = [nome for nome, dati in grezzo.items() if not dati]
    if mancanti:
        # Meglio nessun aggiornamento che una fixture dimezzata: una
        # baseline incompleta committata per sbaglio farebbe fallire i
        # test con un messaggio che parla di codici, non di download.
        print(f"fonte non disponibile ({', '.join(mancanti)}): "
              f"fixture non aggiornate. {modelcodes.status()}")
        return 1

    indice = modelcodes._build_index()
    modelcodes.carica_indice(indice)
    tenuti = codici_da_tenere(indice, domande)
    print(f"{len(domande)} domande → {len(tenuti)} codici da registrare "
          f"(su {len(indice)} noti alle due fonti)")

    # UTF-8 con BOM e UTF-16: le due codifiche degli originali, e non sono
    # un dettaglio di comodo. `modelcodes` ha un commento per ciascuna
    # perché su entrambe ha già sbagliato una volta, in silenzio; una
    # fixture riscritta in UTF-8 semplice collauderebbe un percorso che in
    # produzione non esiste.
    testo, tenute, totale = _sottoinsieme(
        grezzo["mobilemodels"].decode("utf-8-sig"), tenuti, ("model",), "\n")
    with open(FILE_MOBILEMODELS, "wb") as f:
        f.write(testo.encode("utf-8-sig"))
    print(f"MobileModels: {tenute} righe su {totale} → {FILE_MOBILEMODELS}")

    testo, tenute, totale = _sottoinsieme(
        grezzo["google_play"].decode("utf-16"), tenuti, ("Device", "Model"), "\r\n")
    with open(FILE_GOOGLE_PLAY, "wb") as f:
        f.write(testo.encode("utf-16"))
    print(f"Google Play: {tenute} righe su {totale} → {FILE_GOOGLE_PLAY}")

    return registra_xiaomi()


if __name__ == "__main__":
    raise SystemExit(main())
