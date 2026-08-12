"""Da dove vengono TUTTI gli errori: analisi per marca, non per caso.

La domanda «nome e codice portano allo stesso telefono?» si decide
sull'IDENTITÀ (marca + nome canonico → device_key), che si calcola in
locale dai dataset. Niente rete, quindi invece di 32 coppie se ne possono
guardare migliaia — che è l'unico modo di vedere una CAUSA invece di un
caso.
"""
import io, os, random, sys, tempfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath("v36"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

os.environ["TRACKER_DB"] = tempfile.mktemp(suffix=".db")
from core import config as C, extract, modelcodes, sources, storage
C.DB_PATH = os.environ["TRACKER_DB"]
storage.init_db()
modelcodes.resolve("")

random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 4242)
PER_MARCA = int(sys.argv[2]) if len(sys.argv) > 2 else 300

# Ordine di importanza chiesto.
ORDINE = ["Galaxy", "Redmi", "Xiaomi", "realme", "motorola", "moto",
          "OPPO", "OnePlus", "HONOR", "HUAWEI", "vivo", "iQOO",
          "POCO", "Pixel", "Nothing", "TECNO", "Infinix", "Nokia"]

per_marca = defaultdict(list)
for codice, nomi in modelcodes._memory_cache.items():
    for nome in nomi:
        # UN CODICE NON È UN NOME. L'8% delle voci del dataset mette il
        # codice anche nella colonna del nome: usarle come «nome cercato»
        # misurerebbe un caso che non esiste — nessuno digita «Oppo
        # CPH2385» pensando di scrivere un nome commerciale, e se lo
        # facesse l'app lo riconoscerebbe come codice.
        if modelcodes._e_il_codice(nome, codice):
            continue
        basso = nome.lower()
        for marca in ORDINE:
            if basso.startswith(marca.lower() + " ") or basso == marca.lower():
                per_marca[marca].append((nome, codice))
                break


def identita(testo, e_codice):
    """(marca, chiave) come li calcolerebbe l'applicazione."""
    if e_codice:
        nomi = modelcodes.resolve(testo)
        nome = nomi[0] if nomi else testo
        marca = (sources.brand_from_code(testo)
                 or extract.detect_brand(nome)
                 or sources.brand_from_known_device(nome)
                 or C.OTHER)
    else:
        nome = testo
        marca = (extract.detect_brand(testo)
                 or sources.brand_from_code(testo)
                 or sources.brand_from_known_device(testo)
                 or C.OTHER)
    return marca, nome, extract.device_key(marca, nome)


def causa(nome, codice, ia, ib):
    marca_a, nome_a, chiave_a = ia
    marca_b, nome_b, chiave_b = ib
    if chiave_a == chiave_b:
        return None
    if marca_a != marca_b:
        return "marca diversa"
    if not modelcodes.resolve(codice):
        return "codice non risolto (resta il codice come nome)"
    radice_a = chiave_a.split("|", 1)[1]
    radice_b = chiave_b.split("|", 1)[1]
    if radice_a in radice_b or radice_b in radice_a:
        return "nome piu' lungo da una parte (variante regionale/gamma)"
    return "nomi diversi"


print(f"analisi identita': {PER_MARCA} modelli per marca, seme fisso\n")
print(f"{'marca':12s} {'campione':>9s} {'coerenti':>9s} {'%':>6s}   cause principali")
print("-" * 100)

totale_cause = Counter()
esempi = defaultdict(list)
for marca in ORDINE:
    elenco = per_marca.get(marca) or []
    if not elenco:
        continue
    campione = random.sample(elenco, min(PER_MARCA, len(elenco)))
    cause = Counter()
    ok = 0
    for nome, codice in campione:
        ia, ib = identita(nome, False), identita(codice, True)
        c = causa(nome, codice, ia, ib)
        if c is None:
            ok += 1
        else:
            cause[c] += 1
            totale_cause[c] += 1
            if len(esempi[c]) < 4:
                esempi[c].append((nome, codice, ia[2], ib[2]))
    prime = ", ".join(f"{k} ({v})" for k, v in cause.most_common(3))
    print(f"{marca:12s} {len(campione):9d} {ok:9d} {100*ok/len(campione):5.0f}%   {prime}")

print("\n" + "=" * 100)
print("CAUSE, IN ORDINE DI FREQUENZA")
for c, n in totale_cause.most_common():
    print(f"\n  {n:5d}  {c}")
    for nome, codice, ka, kb in esempi[c]:
        print(f"           «{nome}» -> {ka}")
        print(f"           «{codice}» -> {kb}")
