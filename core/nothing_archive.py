"""Nothing / CMF: build per dispositivo dall'archivio `spike0en/nothing_archive`.

## Perché questa fonte (26/09/2026)

Fino a oggi, per Nothing e CMF il progetto aveva soltanto la ricerca su
notizie: nessuna fonte diceva quale fosse l'ultima build di un Phone (3a).
Nothing non pubblica un elenco ufficiale machine-readable, e il suo server
OTA risponde solo a chi si finge un telefono — la stessa porta già chiusa
per OxygenUpdater.

`nothing_archive` è un archivio community, curato, che conserva il
changelog di **ogni** build di ogni telefono Nothing/CMF, un file per
build. Misurato il 26/09/2026: 13 telefoni, aggiornato lo stesso giorno.
Il dato utile sta già tutto nel NOME del file:

    website/docs/changelogs/metroid/Metroid-V3.5-250923-1421.md
                            ^^^^^^^ ^^^^^^^ ^^^^ ^^^^^^ ^^^^
                            cartella codename ver  data   ora

La lettera davanti alla versione è la lettera del dolce Android, come nei
nomi in codice di Google: V = 15 (Vanilla Ice Cream), B = 16 (Baklava),
C = 17. È così che si ricava l'Android senza indovinarlo dalla versione
di Nothing OS.

## Cosa si legge dal testo, e cosa no

Dal changelog si prendono due cose sole:

* **se è una beta** — le Open Beta hanno lo stesso formato di nome delle
  stabili (la C5.0 di settembre 2026 è una beta di Android 17), e una
  beta non deve mai diventare «l'ultimo firmware stabile»;
* **la patch di sicurezza**, quando il changelog la dichiara
  («Updated to August 2026 security patch»).

Attenzione a un falso positivo misurato sul file vero: molte build
STABILI dicono «Updating to Open Beta for Nothing OS 4.0 won't be
possible after this update». La parola «Open Beta» da sola non basta;
serve l'annuncio della beta in testa al changelog.

## Licenza

La compilazione è CC BY-NC 4.0: uso non commerciale con attribuzione. Il
link a ogni changelog, sempre visibile nella pagina, è l'attribuzione.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

REPO = "spike0en/nothing_archive"
HOMEPAGE = f"https://github.com/{REPO}"
TREE_URL = f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/"
BLOB_URL = f"{HOMEPAGE}/blob/main/"

# Codename → (nome commerciale, codice modello). Dalla tabella
# `website/docs/devices.md` dello stesso archivio, verificata il 26/09/2026.
# Un codename nuovo che manca qui viene SALTATO, non indovinato: un nome
# sbagliato attaccherebbe la build al telefono sbagliato.
MODELLI: dict[str, tuple[str, str]] = {
    "spacewar": ("Nothing Phone (1)", "A063"),
    "pong": ("Nothing Phone (2)", "A065"),
    "pacman": ("Nothing Phone (2a)", "A142"),
    "pacmanpro": ("Nothing Phone (2a) Plus", "A142P"),
    "asteroids": ("Nothing Phone (3a)", "A059"),
    "asteroidspro": ("Nothing Phone (3a) Pro", "A059P"),
    "metroid": ("Nothing Phone (3)", "A024"),
    "galaxian": ("Nothing Phone (3a) Lite", "A001T"),
    "frogger": ("Nothing Phone (4a)", "A069"),
    "froggerpro": ("Nothing Phone (4a) Pro", "A069P"),
    "supercontra": ("Nothing Phone (4b)", "A009P"),
    "tetris": ("CMF Phone 1", "A015"),
    "galaga": ("CMF Phone 2 Pro", "A001"),
}

# Telefoni SENZA una cartella propria perché ricevono le stesse build di
# un altro: il (3a) Pro condivide il firmware del (3a) — l'archivio ha la
# sola cartella `asteroids` (verificato il 26/09/2026). Senza questa riga
# il (3a) Pro risultava sconosciuto pur avendo la stessa build del (3a).
CONDIVISI: dict[str, tuple[str, ...]] = {
    "asteroids": ("asteroidspro",),
}

ANDROID_PER_LETTERA = {"S": 12, "T": 13, "U": 14, "V": 15, "B": 16, "C": 17}

_FILE_RE = re.compile(
    r"^website/docs/changelogs/(?P<cartella>[a-z0-9]+)/"
    r"(?P<codename>[A-Za-z0-9]+)-(?P<lettera>[A-Z])(?P<versione>\d+(?:\.\d+)*)"
    r"-(?P<data>\d{6})-(?P<ora>\d{4})\.md$"
)

# L'annuncio della beta, cercato solo in testa al changelog (vedi docstring).
_BETA_RE = re.compile(
    r"\(Beta\)|joining the [^\n]{0,80}\bBeta\b|\bOpen Beta (?:build|update|version|release)\b",
    re.IGNORECASE,
)
_TESTA_CHANGELOG = 600

_MESI = ("january february march april may june july august september "
         "october november december").split()
_PATCH_RE = re.compile(
    r"\b(" + "|".join(_MESI) + r")\s+(20\d{2})\s+security\s+patch", re.IGNORECASE)


@dataclass(frozen=True)
class Build:
    percorso: str
    cartella: str
    codename: str
    lettera: str
    versione: str
    data: str        # AAAA-MM-GG
    ora: str         # HH:MM

    @property
    def nome_build(self) -> str:
        return f"{self.codename}-{self.lettera}{self.versione}-{self.data[2:].replace('-', '')}-{self.ora.replace(':', '')}"

    @property
    def android(self) -> int | None:
        return ANDROID_PER_LETTERA.get(self.lettera)

    @property
    def chiave_ordine(self) -> tuple:
        return (self.data, self.ora)


def build_dal_percorso(percorso: str) -> Build | None:
    m = _FILE_RE.match(percorso or "")
    if not m:
        return None
    d = m.group("data")
    o = m.group("ora")
    return Build(
        percorso=percorso,
        cartella=m.group("cartella"),
        codename=m.group("codename"),
        lettera=m.group("lettera"),
        versione=m.group("versione"),
        data=f"20{d[0:2]}-{d[2:4]}-{d[4:6]}",
        ora=f"{o[0:2]}:{o[2:4]}",
    )


def build_per_dispositivo(albero: dict) -> dict[str, list[Build]]:
    """Dalla risposta dell'API «git trees»: cartella → build, la più
    recente per prima. Le cartelle senza un modello noto restano fuori."""
    per_cartella: dict[str, list[Build]] = {}
    for voce in (albero or {}).get("tree", []) or []:
        build = build_dal_percorso(voce.get("path", ""))
        if build is None or build.cartella not in MODELLI:
            continue
        per_cartella.setdefault(build.cartella, []).append(build)
    for elenco in per_cartella.values():
        elenco.sort(key=lambda b: b.chiave_ordine, reverse=True)
    return per_cartella


def e_beta(testo: str) -> bool:
    return bool(_BETA_RE.search((testo or "")[:_TESTA_CHANGELOG]))


def patch_sicurezza(testo: str) -> str | None:
    """«August 2026 security patch» → «2026-08»."""
    m = _PATCH_RE.search(testo or "")
    if not m:
        return None
    return f"{m.group(2)}-{_MESI.index(m.group(1).lower()) + 1:02d}"


def estratto(testo: str, righe: int = 4) -> str:
    """Le prime voci del changelog, senza markdown né emoji: bastano a
    dire di che build si tratta, e la pagina completa resta a un click."""
    utili = []
    for riga in (testo or "").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or riga.lower().startswith(
                ("welcome", "thank you", "disclaimer", "please back up", "what's new")):
            continue
        riga = re.sub(r"[^\w\s.,:;()%'+/&-]", "", riga).strip()
        if len(riga) < 8:
            continue
        utili.append(riga)
        if len(utili) >= righe:
            break
    return " · ".join(utili)
