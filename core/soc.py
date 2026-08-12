"""Quale chip monta un telefono.

**A cosa serve nel QA.** Un difetto legato al SoC si riproduce solo su
una delle varianti. Il caso da manuale è il Galaxy S24: `SM-S921B`
(Europa) monta Exynos 2400, `SM-S921U` (USA) monta Snapdragon 8 Gen 3.
Stesso nome commerciale, stesso firmware, chip diverso — e un bug di
codifica video o di fotocamera può stare tutto da una parte sola.
Per questo il SoC va risolto **per codice modello**, non per nome: una
fonte che dice «Galaxy S24 → Snapdragon» sta dando un'informazione
sbagliata a metà del mondo.

## Da dove viene il dato, in ordine

1. **Catalogo dispositivi di Google Play** (`data/play_device_catalog.csv`),
   se presente. È l'unica fonte gratuita e strutturata che dà il SoC per
   codice esatto, quindi gestisce le varianti regionali per costruzione.
   Non è scaricabile in modo anonimo: si esporta dalla Play Console e si
   mette nel repo. Il file **non è incluso** — vedi `FONTI.md` per come
   ottenerlo. Finché manca, valgono i punti 2 e 3.
2. **Regole deterministiche** per Apple e Pixel, dove l'identificatore
   del modello *implica* il chip senza ambiguità né varianti di mercato.
3. **Tabella curata a mano** (`data/soc_modelli.csv`), piccola di
   proposito: contiene solo modelli per cui l'abbinamento è verificato e
   documentato. Non è un tentativo di coprire il mercato.

## Perché la tabella curata è così corta

Perché la regola del progetto è che un dato che guida una decisione non
si inventa. Sarebbe stato facile riempire un CSV con qualche centinaio
di righe «plausibili»: chi legge non distingue una riga verificata da una
ricordata male, e il primo Exynos scritto al posto di uno Snapdragon
farebbe cercare un bug su un telefono che non ce l'ha. Meglio poche righe
giuste e un onesto «non disponibile» sul resto.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
from dataclasses import dataclass

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None
from datetime import datetime, timezone

CARTELLA_DATI = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FILE_CURATO = os.path.join(CARTELLA_DATI, "soc_modelli.csv")
FILE_PLAY = os.path.join(CARTELLA_DATI, "play_device_catalog.csv")


@dataclass(frozen=True)
class Soc:
    """Il chip di un dispositivo, con la provenienza sempre allegata."""
    nome: str                      # «Snapdragon 8 Gen 3 for Galaxy»
    produttore: str                # «Qualcomm», «Samsung», «MediaTek»...
    codice: str | None = None      # «SM8650-AC», «S5E9945»
    fonte: str = ""                # da dove viene, mostrato all'utente
    nota: str | None = None        # es. avviso sulla variante regionale

    @property
    def etichetta(self) -> str:
        testo = f"{self.produttore} {self.nome}".strip()
        if self.codice and self.codice.lower() not in testo.lower():
            testo += f" ({self.codice})"
        return testo


# ======================================================================
# Codice interno del chip → nome commerciale
# ======================================================================
# Questa è la parte SICURA del modulo: la corrispondenza fra sigla e nome
# commerciale è pubblicata dai produttori e non cambia mai.
#
# Serve perché le fonti strutturate restituiscono la sigla: il catalogo
# Play scrive «SM8750», Geekbench scrive il codename «sun». Mostrare
# «SM8750» a chi fa QA non serve a niente; «Snapdragon 8 Elite» sì.
_CHIP: dict[str, tuple[str, str]] = {
    # --- Qualcomm, generazioni recenti -------------------------------
    "SM8750": ("Qualcomm", "Snapdragon 8 Elite"),
    "SM8735": ("Qualcomm", "Snapdragon 8s Gen 4"),
    "SM8650": ("Qualcomm", "Snapdragon 8 Gen 3"),
    "SM8635": ("Qualcomm", "Snapdragon 8s Gen 3"),
    "SM8550": ("Qualcomm", "Snapdragon 8 Gen 2"),
    "SM8475": ("Qualcomm", "Snapdragon 8+ Gen 1"),
    "SM8450": ("Qualcomm", "Snapdragon 8 Gen 1"),
    "SM8350": ("Qualcomm", "Snapdragon 888"),
    "SM8250": ("Qualcomm", "Snapdragon 865"),
    "SM8150": ("Qualcomm", "Snapdragon 855"),
    "SDM855": ("Qualcomm", "Snapdragon 855"),
    "SDM845": ("Qualcomm", "Snapdragon 845"),
    "MSM8998": ("Qualcomm", "Snapdragon 835"),
    "SM7675": ("Qualcomm", "Snapdragon 7 Gen 3"),
    "SM7550": ("Qualcomm", "Snapdragon 7 Gen 3"),
    "SM7435": ("Qualcomm", "Snapdragon 6s Gen 3"),
    "SM7325": ("Qualcomm", "Snapdragon 778G"),
    "SM6375": ("Qualcomm", "Snapdragon 695"),
    "SM6225": ("Qualcomm", "Snapdragon 680"),
    "SM4450": ("Qualcomm", "Snapdragon 4 Gen 2"),
    # --- Samsung Exynos ----------------------------------------------
    "S5E9955": ("Samsung", "Exynos 2500"),
    "S5E9945": ("Samsung", "Exynos 2400"),
    "S5E9925": ("Samsung", "Exynos 2200"),
    "S5E9840": ("Samsung", "Exynos 2100"),
    "S5E8845": ("Samsung", "Exynos 1480"),
    "S5E8835": ("Samsung", "Exynos 1380"),
    "S5E8825": ("Samsung", "Exynos 1280"),
    "EXYNOS9810": ("Samsung", "Exynos 9810"),
    "UNIVERSAL9810": ("Samsung", "Exynos 9810"),
    # --- MediaTek -----------------------------------------------------
    "MT6991": ("MediaTek", "Dimensity 9400"),
    "MT6989": ("MediaTek", "Dimensity 9300"),
    "MT6985": ("MediaTek", "Dimensity 9200"),
    "MT6983": ("MediaTek", "Dimensity 9000"),
    "MT6897": ("MediaTek", "Dimensity 8300"),
    "MT6896": ("MediaTek", "Dimensity 8200"),
    "MT6895": ("MediaTek", "Dimensity 8100"),
    "MT6893": ("MediaTek", "Dimensity 1200"),
    "MT6891": ("MediaTek", "Dimensity 1100"),
    "MT6886": ("MediaTek", "Dimensity 7200"),
    "MT6835": ("MediaTek", "Dimensity 6100+"),
    "MT6833": ("MediaTek", "Dimensity 700"),
    "MT6789": ("MediaTek", "Helio G99"),
    "MT6785": ("MediaTek", "Helio G95"),
    # --- Google Tensor ------------------------------------------------
    "GS101": ("Google", "Tensor"),
    "GS201": ("Google", "Tensor G2"),
    "ZUMA": ("Google", "Tensor G3"),
    "ZUMAPRO": ("Google", "Tensor G4"),
    # --- Unisoc / HiSilicon ------------------------------------------
    "T612": ("Unisoc", "Tiger T612"),
    "T606": ("Unisoc", "Tiger T606"),
    "KIRIN9000S": ("HiSilicon", "Kirin 9000S"),
    "KIRIN9000": ("HiSilicon", "Kirin 9000"),
}

# Codename di piattaforma → sigla. Compaiono in `ro.board.platform` e nei
# risultati dei benchmark.
_CODENAME: dict[str, str] = {
    "SUN": "SM8750", "PINEAPPLE": "SM8650", "KALAMA": "SM8550",
    "TARO": "SM8450", "LAHAINA": "SM8350", "KONA": "SM8250",
    "MSMNILE": "SM8150", "SDM845": "SDM845",
}

_RE_SIGLA = re.compile(r"^[A-Z]{2,3}\d{3,4}")


def _pulisci_sigla(grezza: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (grezza or "").upper())


def chip_da_sigla(grezza: str) -> Soc | None:
    """`SM8750-AC` → Snapdragon 8 Elite. None se la sigla non è nota.

    Il suffisso dopo il trattino (`-AB`, `-AC`) distingue varianti dello
    stesso chip: `-AC` è tipicamente la versione «for Galaxy», con clock
    più alto. Si conserva nel codice mostrato ma non cambia il nome.

    Accetta anche la forma con il produttore davanti — «Qualcomm SDM855»,
    «Samsung S5E9945» — che è **come il catalogo di Google Play scrive
    davvero il campo**: si prova ogni pezzo della stringa finché uno
    corrisponde, invece di pretendere una sigla isolata.
    """
    testo = (grezza or "").strip()
    if not testo:
        return None

    pezzi = [p for p in re.split(r"[\s/,]+", testo) if p]
    for pezzo in pezzi + ([testo] if len(pezzi) > 1 else []):
        trovato = _chip_da_pezzo(pezzo)
        if trovato:
            return trovato
    return None


def _chip_da_pezzo(grezza: str) -> Soc | None:
    sigla = _pulisci_sigla(grezza)
    if not sigla:
        return None

    codice = grezza.strip()
    if sigla in _CODENAME:
        sigla = _CODENAME[sigla]
        # Il codename («sun») è un dettaglio interno che non dice niente a
        # nessuno: si mostra la sigla vera, che è cercabile.
        codice = sigla

    voce = _CHIP.get(sigla)
    if voce is None:
        # Prova a togliere il suffisso di variante: SM8750AC → SM8750.
        radice = _RE_SIGLA.match(sigla)
        if radice:
            voce = _CHIP.get(radice.group(0))
    if voce is None:
        return None

    produttore, nome = voce
    if produttore == "Qualcomm" and sigla.endswith("AC") and "Galaxy" not in nome:
        # La variante -AC è quella spinta riservata a Samsung: dirlo,
        # perché a parità di nome le prestazioni non sono le stesse.
        nome = f"{nome} for Galaxy"
    return Soc(nome=nome, produttore=produttore, codice=codice)


# ======================================================================
# Regole deterministiche: Apple e Pixel
# ======================================================================
# Qui non serve nessuna tabella di dispositivi, perché l'identificatore
# implica il chip. E soprattutto non esistono varianti regionali: un
# iPhone17,3 monta lo stesso A18 ovunque nel mondo.
_APPLE_CHIP: dict[str, str] = {
    "iPhone10": "A11 Bionic",
    "iPhone11": "A12 Bionic",
    "iPhone12": "A13 Bionic",
    "iPhone13": "A14 Bionic",
    "iPhone14": "A15 Bionic",
}
# Dove una generazione mescola due chip, l'abbinamento è per
# identificatore esatto: è l'unico modo di non sbagliare fra Pro e non-Pro.
_APPLE_ESATTI: dict[str, str] = {
    "iPhone15,2": "A16 Bionic", "iPhone15,3": "A16 Bionic",
    "iPhone15,4": "A16 Bionic", "iPhone15,5": "A16 Bionic",
    "iPhone16,1": "A17 Pro", "iPhone16,2": "A17 Pro",
    "iPhone17,1": "A18 Pro", "iPhone17,2": "A18 Pro",
    "iPhone17,3": "A18", "iPhone17,4": "A18", "iPhone17,5": "A18",
}

_RE_APPLE = re.compile(r"^(?P<famiglia>iPhone|iPad)(?P<major>\d+),(?P<minor>\d+)$", re.I)


def _soc_apple(identificatore: str) -> Soc | None:
    """Chip di un iPhone dal suo identificatore interno.

    Gli iPad restano volutamente fuori: la loro numerazione mescola
    generazioni e formati in un modo che non si riduce a una regola, e
    tirare a indovinare qui varrebbe meno di un onesto «non disponibile».

    Anche le generazioni oltre iPhone17 restano fuori finché la
    corrispondenza esatta fra identificatore e chip non è verificata.
    """
    testo = (identificatore or "").strip()
    match = _RE_APPLE.match(testo)
    if not match or match.group("famiglia").lower() != "iphone":
        return None

    normalizzato = f"iPhone{match.group('major')},{match.group('minor')}"
    nome = _APPLE_ESATTI.get(normalizzato)
    if nome is None:
        nome = _APPLE_CHIP.get(f"iPhone{match.group('major')}")
    if nome is None:
        return None
    return Soc(nome=nome, produttore="Apple", fonte="identificatore Apple")


# Pixel: la generazione determina il Tensor, senza varianti di mercato.
_PIXEL: list[tuple[re.Pattern, tuple[str, str]]] = [
    (re.compile(r"\bpixel\s*10\b", re.I), ("Google", "Tensor G5")),
    (re.compile(r"\bpixel\s*9\b|\bpixel\s*9a\b", re.I), ("Google", "Tensor G4")),
    (re.compile(r"\bpixel\s*8\b|\bpixel\s*8a\b", re.I), ("Google", "Tensor G3")),
    (re.compile(r"\bpixel\s*7\b|\bpixel\s*7a\b|\bpixel\s*fold\b|\bpixel\s*tablet\b", re.I),
     ("Google", "Tensor G2")),
    (re.compile(r"\bpixel\s*6\b|\bpixel\s*6a\b", re.I), ("Google", "Tensor")),
    (re.compile(r"\bpixel\s*5\b|\bpixel\s*5a\b", re.I), ("Qualcomm", "Snapdragon 765G")),
]


def _soc_pixel(nome_dispositivo: str) -> Soc | None:
    testo = (nome_dispositivo or "")
    if "pixel" not in testo.lower():
        return None
    for schema, (produttore, nome) in _PIXEL:
        if schema.search(testo):
            return Soc(nome=nome, produttore=produttore, fonte="generazione Pixel")
    return None


# ======================================================================
# Dataset da file
# ======================================================================
_curato: dict[str, Soc] | None = None
_dataset: dict[str, Soc] | None = None
_play: dict[str, Soc] | None = None


def _leggi(percorso: str) -> str | None:
    try:
        with open(percorso, encoding="utf-8-sig") as f:
            return f.read()
    except OSError:
        return None


# Parole di gamma che i produttori mettono nel nome ma che la gente omette,
# e nomi di marca che invece la gente aggiunge. Nella pratica lo stesso
# telefono si scrive «Galaxy S24 Ultra», «Samsung S24 Ultra» o «S24 Ultra»,
# e tutte e tre devono portare allo stesso chip.
_GAMME = ("GALAXY", "REDMI", "POCO", "IQOO", "NARZO", "MOTO")
_MARCHE = ("SAMSUNG", "XIAOMI", "OPPO", "REALME", "ONEPLUS", "VIVO",
           "MOTOROLA", "HONOR", "HUAWEI", "GOOGLE", "APPLE", "NOTHING")


def varianti_nome(nome: str) -> list[str]:
    """Tutti i modi in cui la gente scrive lo stesso nome commerciale.

    «Galaxy S24 Ultra» genera anche «S24 Ultra» e «Samsung S24 Ultra»,
    perché è così che viene digitato e così che le fonti di notizie lo
    scrivono. Senza queste varianti il chip si trovava solo indovinando la
    grafia esatta del CSV — che è il motivo per cui cercando «samsung s24
    ultra» non compariva nessun processore.
    """
    pulito = re.sub(r"\s+", " ", (nome or "")).strip().upper()
    if not pulito:
        return []

    forme = {pulito}
    parole = pulito.split(" ")

    # Senza la parola di gamma: «Galaxy S24 Ultra» → «S24 Ultra»
    senza_gamma = [p for p in parole if p not in _GAMME]
    if senza_gamma and senza_gamma != parole:
        forme.add(" ".join(senza_gamma))

    # Senza la marca: «Samsung Galaxy A32» → «Galaxy A32»
    senza_marca = [p for p in parole if p not in _MARCHE]
    if senza_marca and senza_marca != parole:
        forme.add(" ".join(senza_marca))

    # Con la marca davanti, per ognuna delle forme trovate finora.
    marca = _MARCA_DI_GAMMA.get(parole[0])
    if marca:
        for forma in list(forme):
            forme.add(f"{marca} {forma}")
            senza = [p for p in forma.split(" ") if p not in _GAMME]
            if senza:
                forme.add(f"{marca} {' '.join(senza)}")

    return [f for f in forme if f]


_MARCA_DI_GAMMA = {"GALAXY": "SAMSUNG", "REDMI": "XIAOMI", "POCO": "XIAOMI",
                   "NARZO": "REALME", "MOTO": "MOTOROLA", "IQOO": "VIVO"}


def carica_curato(testo: str) -> dict[str, Soc]:
    """Legge `soc_modelli.csv`: codice modello → chip, curato a mano.

    Le righe che iniziano con `#` sono commenti e vengono tolte prima del
    parsing: il CSV standard non li prevede, ma qui servono a spiegare
    *perché* la tabella è corta, e quella spiegazione deve stare accanto
    ai dati e non in un file che nessuno apre.
    """
    righe = [r for r in (testo or "").splitlines() if not r.lstrip().startswith("#")]
    indice: dict[str, Soc] = {}
    per_nome: dict[str, list[Soc]] = {}
    for riga in csv.DictReader(io.StringIO("\n".join(righe))):
        codice = (riga.get("model_code") or "").strip().upper()
        nome = (riga.get("soc_nome") or "").strip()
        if not codice or not nome:
            continue
        voce = Soc(
            nome=nome,
            produttore=(riga.get("produttore") or "").strip(),
            codice=(riga.get("soc_codice") or "").strip() or None,
            fonte="tabella verificata a mano",
            nota=(riga.get("nota") or "").strip() or None,
        )
        indice[codice] = voce
        commerciale = (riga.get("nome_commerciale") or "").strip().upper()
        for scritto in varianti_nome(commerciale):
            per_nome.setdefault(scritto, []).append(voce)

    # Voci per nome commerciale, con l'AMBIGUITÀ resa esplicita. Chi cerca
    # «Galaxy S24» senza codice non può ricevere una risposta sola, perché
    # una risposta sola sarebbe sbagliata per metà dei telefoni con quel
    # nome. Ma tacere è peggio: sapere che ESISTONO due varianti è già
    # un'informazione operativa, dice di andare a guardare la sigla sulla
    # scatola prima di aprire un bug.
    for commerciale, voci in per_nome.items():
        distinti = {v.nome for v in voci}
        if len(distinti) == 1:
            # Tutte le varianti montano lo stesso chip: la nota della
            # singola riga («Variante USA») qui sarebbe fuorviante, perché
            # chi ha cercato per nome non ha indicato nessuna variante.
            modello = voci[0]
            indice.setdefault(commerciale, Soc(
                nome=modello.nome, produttore=modello.produttore,
                codice=modello.codice, fonte=modello.fonte,
            ))
        else:
            elenco = " oppure ".join(sorted(distinti))
            indice.setdefault(commerciale, Soc(
                nome=elenco,
                produttore="",
                fonte="tabella verificata a mano",
                nota=("Questo modello esiste in più varianti con chip diverso: "
                      "serve il codice esatto (es. SM-S921B) per sapere quale."),
            ))
    return indice


# Intestazioni del catalogo Play, come documentate da Google. Il file non
# è incluso nel repo: chi ce l'ha lo esporta dalla Play Console e lo
# lascia cadere in `data/`. Il confronto è per NOME di colonna e non per
# posizione, così l'importatore regge a un riordino.
_COL_CODICE = ("model code", "model_code", "device", "codename")
_COL_SOC = ("system on chip", "system_on_chip", "soc", "chipset")
_COL_NOME = ("model name", "marketing name", "model_name")


def carica_play_catalog(testo: str) -> dict[str, Soc]:
    """Legge l'export del catalogo dispositivi di Google Play.

    Il file elenca una riga per codice, quindi le varianti regionali con
    chip diverso sono già righe distinte: è esattamente il motivo per cui
    questa è la fonte primaria e non un ripiego.
    """
    lettore = csv.reader(io.StringIO(testo or ""))
    try:
        intestazione = [c.strip().lower() for c in next(lettore)]
    except StopIteration:
        return {}

    def indice_di(nomi):
        for nome in nomi:
            if nome in intestazione:
                return intestazione.index(nome)
        return None

    i_codice = indice_di(_COL_CODICE)
    i_soc = indice_di(_COL_SOC)
    i_nome = indice_di(_COL_NOME)
    if i_codice is None or i_soc is None:
        return {}

    indice: dict[str, Soc] = {}
    for riga in lettore:
        if max(i_codice, i_soc) >= len(riga):
            continue
        codice = riga[i_codice].strip().upper()
        grezzo = riga[i_soc].strip()
        if not codice or not grezzo:
            continue
        chip = chip_da_sigla(grezzo)
        if chip is None:
            # Sigla sconosciuta: si mostra comunque quella grezza invece
            # di buttare il dato. Meglio «SM7635» di niente — chi fa QA
            # può cercarla, mentre un campo vuoto non dice nulla.
            chip = Soc(nome=grezzo, produttore="", codice=grezzo)
        indice[codice] = Soc(nome=chip.nome, produttore=chip.produttore,
                             codice=chip.codice, fonte="catalogo dispositivi Google Play")
        nome_commerciale = (riga[i_nome].strip().upper()
                            if i_nome is not None and i_nome < len(riga) else "")
        if nome_commerciale:
            indice.setdefault(nome_commerciale, indice[codice])
    return indice


# ======================================================================
# Dataset esterno multi-marca
# ======================================================================
# Perché esiste. La tabella scritta a mano non può coprire decine di
# migliaia di modelli, e nessun dataset gratuito risolve *codice modello →
# chip* su tutta la fascia media. Questo però risolve *nome commerciale →
# chip* per quasi tutte le marche, e il progetto ha già la catena che
# porta dal codice al nome commerciale (~70.000 codici). Messi in fila,
# coprono la gran parte delle ricerche reali.
#
# Tre limiti, tutti noti e dichiarati:
#   1. È indicizzato per NOME COMMERCIALE, non per codice: le varianti
#      regionali dello stesso nome (Galaxy S24 Exynos in Europa e
#      Snapdragon negli USA) non si distinguono. Per questo la tabella
#      curata VINCE sempre: è lì che vivono le varianti.
#   2. È fermo intorno al 2021: sui modelli recenti non risponde.
#   3. I valori sono letterali Python (`b'Exynos 980'`) e vanno ripuliti.
#
# Si può spegnere con SOC_DATASET_URL="" se un domani la fonte sparisse o
# desse dati sbagliati.
SOC_DATASET_URL = os.environ.get(
    "SOC_DATASET_URL",
    "https://raw.githubusercontent.com/foykes/gsm-arena-dataset/main/"
    "gsm_arena_full_dataset.csv",
)
_META_DATASET_BYTES = "soc_dataset_bytes"
_META_DATASET_FETCHED = "soc_dataset_fetched_at"
_RINFRESCA_ORE = 24 * 30   # il chip di un modello non cambia mai

_RE_LETTERALE = re.compile(r"^b['\"](.*)['\"]$", re.S)


def _ripulisci_letterale(valore: str) -> str:
    """`b'Exynos 980 (8 nm)'` → `Exynos 980 (8 nm)`."""
    testo = (valore or "").strip()
    match = _RE_LETTERALE.match(testo)
    return (match.group(1) if match else testo).strip()


def carica_dataset_esterno(testo: str) -> dict[str, Soc]:
    """Indice nome commerciale → chip dal dataset multi-marca."""
    lettore = csv.reader(io.StringIO(testo or ""))
    try:
        intestazione = [_ripulisci_letterale(c).strip().lower()
                        for c in next(lettore)]
    except StopIteration:
        return {}

    def colonna(*nomi):
        for nome in nomi:
            if nome in intestazione:
                return intestazione.index(nome)
        return None

    i_nome = colonna("model name", "name", "model", "phone name")
    i_chip = colonna("chipset")
    i_marca = colonna("brand", "manufacturer")
    if i_nome is None or i_chip is None:
        return {}

    indice: dict[str, Soc] = {}
    # Da quale telefono e con quale chip è arrivata ogni chiave: serve a
    # riconoscere le collisioni fra modelli diversi (vedi più sotto).
    provenienza: dict[str, tuple[str, str]] = {}
    scartate: set[str] = set()
    for riga in lettore:
        if max(i_nome, i_chip) >= len(riga):
            continue
        nome = _ripulisci_letterale(riga[i_nome])
        grezzo = _ripulisci_letterale(riga[i_chip])
        if not nome or not grezzo:
            continue

        # Il campo elenca a volte due chip separati da «/»: sono le
        # varianti regionali dello stesso modello. Dichiararne una sola
        # sarebbe una risposta sbagliata per metà dei telefoni, quindi si
        # riportano entrambe e si dice che serve il codice esatto.
        pezzi = [p.strip() for p in re.split(r"\s+/\s+|\s+or\s+", grezzo) if p.strip()]
        ambiguo = len(pezzi) > 1

        chip = chip_da_sigla(pezzi[0]) if pezzi else None
        voce = Soc(
            nome=" oppure ".join(pezzi) if ambiguo else (chip.nome if chip else grezzo),
            produttore="" if ambiguo else (chip.produttore if chip else ""),
            codice=None if ambiguo else (chip.codice if chip else None),
            fonte="dataset specifiche multi-marca",
            nota=("Questo nome esiste in più varianti con chip diverso: "
                  "serve il codice esatto per sapere quale." if ambiguo else None),
        )

        marca = (_ripulisci_letterale(riga[i_marca])
                 if i_marca is not None and i_marca < len(riga) else "")
        telefono = f"{marca} {nome}".strip().lower()
        for scritto in varianti_nome(nome) + (varianti_nome(f"{marca} {nome}") if marca else []):
            if not _chiave_utilizzabile(scritto) or scritto in scartate:
                continue
            precedente = provenienza.get(scritto)
            if precedente is None:
                provenienza[scritto] = (telefono, grezzo)
                indice[scritto] = voce
            elif precedente[0] != telefono and precedente[1] != grezzo:
                # DUE TELEFONI DIVERSI, DUE CHIP DIVERSI, LO STESSO NOME
                # ABBREVIATO. Qui non si sceglie: si tace.
                #
                # `varianti_nome` genera anche la forma senza marca, ed è
                # quello che rende utile il dataset («Samsung S24 Ultra»
                # trova «Galaxy S24 Ultra»). Ma la stessa abbreviazione
                # accorpa telefoni che non c'entrano niente: «Huawei P30»
                # e «Motorola P30» diventano entrambi «P30», «vivo U3» e
                # «vivo iQOO U3» entrambi «vivo U3». Tenendo la prima riga
                # incontrata — che è quanto faceva `setdefault` — il chip
                # mostrato dipendeva dall'ordine delle righe nel CSV.
                #
                # Un dato falso è peggio di un dato assente: è la regola
                # che questo progetto applica ovunque, e vale anche qui.
                # Sul dataset reale sono 25 chiavi su 14182.
                scartate.add(scritto)
                indice.pop(scritto, None)
                provenienza.pop(scritto, None)
    return indice


# Sotto questa lunghezza un nome non identifica un telefono. La forma
# abbreviata di «OnePlus 2» è «2», quella di «OnePlus X» è «X»: chiavi che
# non possono che rispondere a caso.
_LUNGHEZZA_MINIMA_CHIAVE = 3


def _chiave_utilizzabile(chiave: str) -> bool:
    return (len(chiave) >= _LUNGHEZZA_MINIMA_CHIAVE
            and any(c.isalpha() for c in chiave))


def _scarica_dataset() -> str | None:
    if not SOC_DATASET_URL or requests is None:
        return None
    try:
        risposta = requests.get(SOC_DATASET_URL, timeout=60,
                                headers={"User-Agent": "Mozilla/5.0"})
    except Exception:
        return None
    if getattr(risposta, "status_code", 0) != 200 or len(risposta.content) < 10_000:
        return None
    return risposta.text


# ======================================================================
# L'indice derivato, al posto del CSV
# ======================================================================
# SI CONSERVA IL RISULTATO, NON LA MATERIA PRIMA.
#
# Il dataset scaricato è un CSV da 12,2 MB, e quello che se ne ricava è
# un indice di 14 000 nomi → chip: qualche centinaio di kilobyte. Finora
# in archivio finiva il CSV, con tre conseguenze che si sommano:
#
#   * `tracker.db` se lo porta dietro — e quel file viene caricato su un
#     Gist ogni mezz'ora e committato ogni ora;
#   * a ogni avvio il CSV viene riletto e ri-analizzato riga per riga;
#   * durante quella lettura convivono in memoria il testo, le righe e
#     l'indice, cioè tre copie della stessa informazione.
#
# Conservando l'indice si evitano tutte e tre. Il CSV resta la fonte —
# si riscarica quando l'indice manca o è vecchio — ma smette di essere
# ciò che si tiene.
_META_INDICE = "soc_indice_gz"


def _indice_a_json(indice: dict[str, Soc]) -> bytes:
    """Indice → byte compressi, pronti per l'archivio."""
    crudo = {
        chiave: [voce.nome, voce.produttore, voce.codice, voce.fonte, voce.nota]
        for chiave, voce in indice.items()
    }
    return gzip.compress(
        json.dumps(crudo, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 6)


def _indice_da_json(dati: bytes) -> dict[str, Soc]:
    """Il giro inverso. Una voce malformata si salta, non fa cadere tutto."""
    try:
        crudo = json.loads(gzip.decompress(dati).decode("utf-8"))
    except Exception:
        return {}
    indice: dict[str, Soc] = {}
    for chiave, voce in (crudo or {}).items():
        if not isinstance(voce, list) or len(voce) != 5:
            continue
        nome, produttore, codice, fonte, nota = voce
        indice[chiave] = Soc(nome=nome, produttore=produttore or "",
                             codice=codice, fonte=fonte or "", nota=nota)
    return indice


def _indice_dataset() -> dict[str, Soc]:
    global _dataset
    if _dataset is not None:
        return _dataset

    try:
        from . import storage
        salvato = storage.get_blob(_META_INDICE)
        quando = storage.get_meta(_META_DATASET_FETCHED)
        fresca = False
        if salvato and quando:
            try:
                eta = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(quando)).total_seconds() / 3600
                fresca = eta < _RINFRESCA_ORE
            except ValueError:
                fresca = False
        if fresca:
            _dataset = _indice_da_json(salvato)
            if _dataset:
                return _dataset

        nuovo = _scarica_dataset()
        if nuovo:
            _dataset = carica_dataset_esterno(nuovo)
            if _dataset:
                storage.set_blob(_META_INDICE, _indice_a_json(_dataset))
                storage.set_meta(_META_DATASET_FETCHED,
                                 datetime.now(timezone.utc).isoformat())
                # Il CSV grezzo delle versioni precedenti non serve più:
                # si toglie, o resterebbe in archivio per sempre a
                # occupare 1,8 MB che nessuno legge.
                storage.set_meta(_META_DATASET_BYTES, None)
            return _dataset
        # Rete muta: meglio un indice vecchio che nessun indice.
        if salvato:
            _dataset = _indice_da_json(salvato)
            if _dataset:
                return _dataset
    except Exception:
        pass

    _dataset = _dataset if _dataset is not None else {}
    return _dataset


def _indice_curato() -> dict[str, Soc]:
    global _curato
    if _curato is None:
        _curato = carica_curato(_leggi(FILE_CURATO) or "")
    return _curato


def _indice_play() -> dict[str, Soc]:
    global _play
    if _play is None:
        _play = carica_play_catalog(_leggi(FILE_PLAY) or "")
    return _play


def reset_cache() -> None:
    global _curato, _play, _dataset
    _curato = None
    _play = None
    _dataset = None


def catalogo_play_presente() -> bool:
    return bool(_indice_play())


def status() -> str:
    """Riga di diagnostica: quanto copre oggi il modulo.

    Il dataset esterno viene riportato SENZA forzarne il caricamento: dire
    «non ancora caricato» è un'informazione, scaricare 12 MB solo per
    scrivere una riga di diagnostica non lo è. Era comunque l'unica cosa
    che mancava a mantenere la promessa della v37 — «se il download
    fallisce, la Diagnostica lo dice» — perché finora questa riga il
    dataset non lo nominava affatto.
    """
    play = len(_indice_play())
    curato = len(_indice_curato())
    if _dataset is None:
        dataset = "dataset multi-marca: non ancora caricato"
    elif _dataset:
        dataset = f"dataset multi-marca: {len(_dataset)} nomi"
    else:
        dataset = "dataset multi-marca: NON disponibile (download fallito o spento)"
    if play:
        return f"catalogo Play: {play} voci · tabella curata: {curato} voci · {dataset}"
    return (f"catalogo Play assente · tabella curata: {curato} voci · {dataset} · "
            "regole Apple e Pixel attive")


# Codici modello riconoscibili dentro un testo libero. Servono perché il
# codice quasi mai arriva in un campo suo: o l'utente lo ha digitato nella
# ricerca, o è annegato nel nome mostrato. E senza il codice si perde
# esattamente la distinzione per cui questo modulo esiste — «Galaxy S24»
# da solo non dice se è l'Exynos europeo o lo Snapdragon americano.
# I confini sono espressi come «non alfanumerico» invece che con `\b`
# perché il trattino basso, per le espressioni regolari, è un carattere di
# parola: con `\b` il codice dentro una build come `CPH2649_16.0.7.201`
# non veniva riconosciuto, e per quei dispositivi il chip non si risolveva
# mai partendo dal numero di build.
_RE_CODICI = re.compile(
    r"(?<![A-Za-z0-9])(?:SM-[A-Z]\d{3,4}[A-Z0-9/]*"   # Samsung
    r"|CPH\d{4}[A-Z]{0,4}"                           # OPPO/OnePlus
    r"|RMX\d{4}"                                     # realme
    r"|XT\d{4}-\d{1,2}"                              # Motorola
    r"|[A-Z]{2}\d{4})(?![A-Za-z0-9])",                # NE2211, MT2111, OPD2420
    re.I,
)


def codici_da_testo(testo: str) -> list[str]:
    """Codici modello plausibili dentro una stringa qualsiasi.

    Include l'espansione dei codici Samsung scritti senza prefisso:
    `a325f` è la forma che compare nei numeri di build e nei log, ed è
    quella che chi fa QA copia più spesso. Senza questa riga il chip non
    veniva risolto proprio per le ricerche più frequenti.
    """
    trovati = [m.group(0).upper() for m in _RE_CODICI.finditer(testo or "")]

    # Il codice nudo non ha una forma che `_RE_CODICI` intercetti (una
    # lettera e tre cifre sono troppo poco per distinguerlo da una parola
    # qualsiasi), quindi va cercato a parte: sia come intera stringa
    # digitata, sia come singola parola dentro una frase.
    # I confini di parola sono obbligatori: senza, dentro «CPH2649» si
    # legge «H264» e si finisce per cercare un inesistente «SM-H264».
    parole = re.findall(r"\b[A-Za-z]\d{3}[A-Za-z]{0,3}\b", testo or "")

    # Il numero di build Samsung COMINCIA col codice modello:
    # `A325FXXSCDYB2` = A325F + regione + revisione + data. È spesso
    # l'unico posto dove il codice compare in una scheda dispositivo, dove
    # il nome commerciale da solo non basterebbe a distinguere le varianti.
    for build in re.findall(r"\b([A-Za-z]\d{3}[A-Za-z])[A-Z]{2,3}\w{4,}\b", testo or ""):
        parole.append(build)

    candidati = [(testo or "").strip().upper()] + [p.upper() for p in parole]

    espansi = []
    for codice in candidati + trovati:
        if codice.startswith("SM-") or not _RE_SAMSUNG_NUDO.match(codice):
            continue
        completo = f"SM-{codice}"
        if completo not in espansi:
            espansi.append(completo)
    ordinati = espansi + trovati
    return list(dict.fromkeys(ordinati))


# Stessa forma riconosciuta da `sources.espandi_codice_samsung`. È ripetuta
# qui invece di importata perché questo modulo non dipende da nessun altro:
# è una tabella di consultazione, e tenerla isolata la rende collaudabile
# senza tirarsi dietro mezza applicazione.
_RE_SAMSUNG_NUDO = re.compile(r"^[A-Z]\d{3}[A-Z]{0,3}$")


# Produttori riconosciuti in testa alla stringa di GSMArena, e come si
# scrivono davvero. «Mediatek» con la t minuscola è come lo scrive la
# fonte; il nome corretto è MediaTek.
_PRODUTTORI_TESTA = {
    "QUALCOMM": "Qualcomm", "MEDIATEK": "MediaTek", "SAMSUNG": "Samsung",
    "GOOGLE": "Google", "UNISOC": "Unisoc", "SPREADTRUM": "Unisoc",
    "HISILICON": "HiSilicon", "APPLE": "Apple", "INTEL": "Intel",
    "NVIDIA": "Nvidia",
}
# Famiglie che implicano il produttore anche quando la fonte non lo scrive:
# «Exynos 1580 (4 nm)» non nomina Samsung da nessuna parte.
_FAMIGLIE = {
    "EXYNOS": "Samsung", "SNAPDRAGON": "Qualcomm", "TENSOR": "Google",
    "DIMENSITY": "MediaTek", "HELIO": "MediaTek", "KIRIN": "HiSilicon",
    "TIGER": "Unisoc",
}
# GSMArena mette il mercato in coda con un trattino:
# «Exynos 2400 (4 nm) - International».
_RE_MERCATO = re.compile(r"\s+-\s+(?P<mercato>[^-]+)$")


def _chipset_leggibile(riga: str) -> tuple[Soc | None, str | None]:
    """Una riga di `Platform.Chipset` → (chip, mercato).

    Prima si prova la sigla, perché è l'unica parte verificabile: dentro
    «Qualcomm SM8650-AC Snapdragon 8 Gen 3 (4 nm)» c'è `SM8650-AC`, che la
    tabella delle sigle traduce da sola e che porta con sé anche la
    distinzione «for Galaxy». Se la sigla non c'è — ed è il caso normale
    per MediaTek ed Exynos — si tiene **il testo della fonte così com'è**,
    limitandosi a staccare il produttore. Riscriverlo sarebbe inventare:
    «MT6769V/CU Helio G80» è brutto ma è quello che monta il telefono.
    """
    testo = (riga or "").strip()
    if not testo:
        return None, None

    mercato = None
    trovato_mercato = _RE_MERCATO.search(testo)
    if trovato_mercato:
        mercato = trovato_mercato.group("mercato").strip()
        testo = testo[: trovato_mercato.start()].strip()
    if not testo:
        return None, mercato

    parole = testo.split()
    produttore = ""
    if parole and parole[0].upper() in _PRODUTTORI_TESTA:
        produttore = _PRODUTTORI_TESTA[parole[0].upper()]
        parole = parole[1:]
    resto = " ".join(parole).strip()
    if not resto:
        return None, mercato

    dalla_sigla = chip_da_sigla(resto)
    if dalla_sigla is not None:
        return dalla_sigla, mercato

    if not produttore:
        for parola in parole:
            famiglia = _FAMIGLIE.get(re.sub(r"[^A-Z]", "", parola.upper()))
            if famiglia:
                produttore = famiglia
                break
    return Soc(nome=resto, produttore=produttore,
               fonte="catalogo specifiche"), mercato


def _soc_da_specifiche(codice: str | None = None,
                       nome: str | None = None) -> Soc | None:
    """Il chip dal catalogo specifiche, o None.

    Quando la scheda elenca più chip si riporta **l'ambiguità**, con i
    mercati che la fonte indica: dire «Exynos 2400» a chi ha in mano il
    modello americano manderebbe a cercare un difetto sul telefono
    sbagliato, e tacere del tutto toglierebbe un'informazione che serve —
    sapere che le varianti esistono dice già di controllare la sigla prima
    di aprire una segnalazione.
    """
    try:
        from . import specs
        scheda = (specs.per_codice(codice) if codice else specs.per_nome(nome))
    except Exception:
        return None
    return _soc_da_scheda(scheda)


def _soc_da_scheda(scheda) -> Soc | None:
    """Il chip di una scheda già in mano.

    Staccata da `_soc_da_specifiche` perché la stessa lettura serve anche
    alle schede che non vengono dal catalogo interno — quelle delle marche
    che il mirror GSMArena non ha (vedi `core/versus.py`). La regola
    sull'ambiguità è la stessa e non va scritta due volte.
    """
    if scheda is None:
        return None

    letti = [_chipset_leggibile(r) for r in scheda.chip_varianti]
    letti = [(chip, mercato) for chip, mercato in letti if chip is not None]
    if not letti:
        return None

    # La fonte del chip è la fonte della scheda, letta dalla scheda stessa:
    # scriverla a mano significherebbe attribuire a GSMArena anche i chip
    # che vengono da altrove.
    fonte = getattr(scheda, "fonte", "") or "catalogo specifiche"

    if len(letti) == 1:
        chip = letti[0][0]
        return Soc(nome=chip.nome, produttore=chip.produttore,
                   codice=chip.codice, fonte=fonte)

    pezzi = []
    for chip, mercato in letti:
        etichetta = chip.etichetta
        pezzi.append(f"{etichetta} ({mercato})" if mercato else etichetta)
    return Soc(
        nome=" oppure ".join(chip.nome for chip, _ in letti),
        produttore="",
        fonte=fonte,
        nota=("Questo modello esiste in più varianti con chip diverso — "
              + " · ".join(pezzi)
              + ". Serve il codice esatto (es. SM-S921B) per sapere quale."),
    )


def per_modello(model_code: str | None = None,
                device_name: str | None = None,
                marca: str | None = None) -> Soc | None:
    """Il chip di un dispositivo, o None se non è noto con certezza.

    L'ordine delle fonti è deliberato: prima il codice esatto (che
    distingue le varianti regionali), poi le regole deterministiche, e
    solo alla fine il nome commerciale — che è l'unico livello a cui la
    domanda «quale chip?» può non avere una risposta sola.

    `marca`, quando c'è, arriva fino a `specs._ripiego_esterno`: stesso
    motivo per cui `specs.cerca` la accetta (vedi il suo docstring) — un
    nome commerciale corto come «Note 60s» non porta la marca in testa,
    e senza un indizio esplicito il ripiego su versus.com non saprebbe
    quale marca cercare.
    """
    codice = (model_code or "").strip().upper()

    candidati = [codice] if codice else []
    # Un codice può arrivare annegato nel testo digitato («samsung
    # SM-S921B») o nel nome mostrato: si prova anche così, ma sempre
    # DOPO il codice esplicito, che resta il più attendibile.
    for testo in (model_code, device_name):
        candidati.extend(c for c in codici_da_testo(testo or "") if c not in candidati)

    for candidato in candidati:
        for indice in (_indice_play(), _indice_curato()):
            trovato = indice.get(candidato)
            if trovato:
                return trovato

    # IL CATALOGO SPECIFICHE, per codice modello. Viene DOPO la tabella
    # curata e non prima, e la ragione è precisa: per i modelli con
    # varianti regionali (S24 Exynos in Europa, Snapdragon negli USA) il
    # catalogo ha una scheda sola con tutti i codici insieme, mentre la
    # tabella curata ha una riga per codice. Anteporlo significherebbe
    # rispondere «o l'uno o l'altro» proprio dove si conosce la risposta
    # esatta. Sotto la tabella curata, invece, è ciò che copre tutto il
    # resto del listino — cioè quasi tutti i Samsung usciti dopo il 2021.
    for candidato in candidati:
        trovato = _soc_da_specifiche(codice=candidato)
        if trovato:
            return trovato

    if device_name:
        apple = _soc_apple(device_name)
        if apple:
            return apple
    if model_code:
        apple = _soc_apple(model_code)
        if apple:
            return apple

    pixel = _soc_pixel(f"{device_name or ''} {model_code or ''}")
    if pixel:
        return pixel

    # La ricerca per nome prova ENTRAMBI gli argomenti: chi cerca digita
    # una cosa sola, e quella arriva qui come `model_code` anche quando è
    # un nome commerciale. Guardare solo `device_name` faceva fallire
    # «Redmi Note 10» digitato nella barra di ricerca.
    for testo in (device_name, model_code):
        if not testo:
            continue
        chiave = testo.strip().upper()
        for indice in (_indice_play(), _indice_curato()):
            trovato = indice.get(chiave)
            if trovato:
                return trovato
        trovato = _soc_da_specifiche(nome=testo)
        if trovato:
            return trovato
        trovato = _indice_dataset().get(chiave)
        if trovato:
            return trovato

    # ULTIMA SPIAGGIA, e per una marca sola alla volta: la scheda esterna
    # delle marche che il mirror GSMArena non ha. Sta in fondo a tutto
    # perché è l'unico passaggio che esce in rete e perché ogni indice
    # locale sopra è più preciso; ci arriva solo chi non ha trovato niente,
    # che prima della v49 per un realme o un HONOR fuori dalla tabella
    # scritta a mano voleva dire mostrare un trattino al posto del chip.
    try:
        from . import specs
        scheda = specs._ripiego_esterno(device_name, model_code, marca=marca)
    except Exception:
        return None
    return _soc_da_scheda(scheda)
