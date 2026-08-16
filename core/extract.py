"""Estrazione di dati strutturati dal testo di una notizia o di un record API.

È il modulo che rende possibile la vista "per dispositivo": da un titolo come
«Galaxy S24 Ultra starts receiving One UI 8.0 with build S928BXXU5BYG1»
ricava brand, modello, versione OS e build number.

Nessuna dipendenza esterna → completamente testabile offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import config as C

# ======================================================================
# 1. Riconoscimento brand
# ======================================================================
BRAND_KEYWORDS = {
    C.APPLE: ["iphone", "ipad", "ipod touch", "ios ", "ipados", "apple"],
    C.SAMSUNG: ["samsung", "galaxy", "one ui", "oneui"],
    C.XIAOMI: ["xiaomi", "redmi", "poco", "miui", "hyperos", "hyper os"],
    C.PIXEL: ["pixel", "google pixel"],
    C.HUAWEI: ["huawei", "honor", "harmonyos", "harmony os", "magicos", "magic os", "emui"],
    C.OPPO: ["oppo", "realme", "oneplus", "one plus", "coloros", "color os", "oxygenos", "oxygen os"],
    C.VIVO: ["vivo", "iqoo", "motorola", "moto g", "moto e", "moto x", "razr", "funtouch", "originos"],
    C.OTHER: [
        "nothing phone", "nothing os", "cmf phone", "umidigi", "doogee", "cubot",
        "blackview", "ulefone", "oukitel", "tecno", "infinix", "fairphone", "asus zenfone",
        "rog phone", "sony xperia", "xperia",
    ],
}

# Alcune keyword sono ambigue ("vivo" e "poco" sono parole italiane comuni):
# le accettiamo solo se poco dopo compare qualcosa che somiglia a un modello.
_AMBIGUOUS = {"vivo", "honor", "poco"}


# Nomi di gamma inequivocabilmente Samsung anche senza la parola «Galaxy».
#
# «S24 Ultra» finiva sotto «Altri brand» e creava un dispositivo separato
# accanto a «Samsung S24 Ultra»: lo stesso telefono in archivio due volte,
# ciascuna copia con metà della storia.
#
# Sono volutamente solo le gamme che NON hanno omonimi presso altre marche:
# la serie A è esclusa di proposito, perché «A15» è insieme un Galaxy A15 e
# un OPPO A15 e indovinare sarebbe peggio che tacere.
_SAMSUNG_SENZA_GALAXY = re.compile(
    r"\b(?:s\d{2}\s*(?:ultra|plus|\+|fe)"      # S24 Ultra, S23 FE
    # IL NOTE DI SAMSUNG SI È FERMATO AL 20. Con `note\s?\d{1,2}` finivano
    # sotto Samsung anche «Note 50», «Note 60», «Note 70»: sono realme e
    # Infinix, e la marca sbagliata è una chiave sbagliata, cioè una scheda
    # separata per un telefono che ne ha già una. Misurato sui dataset: era
    # la causa della maggior parte dei 108 codici attribuiti a due marche.
    r"|note\s?(?:[1-9]|1\d|20)(?![\d])"
    r"|z\s*(?:fold|flip)\s*\d?"                 # Z Fold6, Z Flip
    r"|tab\s+s\d)\b",                          # Tab S9
    re.I,
)


def detect_brand(text: str) -> str | None:
    """Assegna uno dei brand supportati a partire da un testo libero."""
    low = f" {str(text or '').lower()} "
    best = None
    best_pos = len(low) + 1
    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            pos = low.find(kw)
            if pos < 0:
                continue
            if kw in _AMBIGUOUS and not re.search(
                rf"\b{re.escape(kw)}\b[^.]{{0,24}}\d", low
            ):
                continue
            # vince la keyword che compare prima nel titolo
            if pos < best_pos:
                best, best_pos = brand, pos
    if best is None and _SAMSUNG_SENZA_GALAXY.search(low):
        return C.SAMSUNG
    return best


# ======================================================================
# 2. Riconoscimento modello
# ======================================================================
# Pattern ordinati dal più specifico al più generico: vince il primo che matcha.
DEVICE_PATTERNS: dict[str, list[str]] = {
    C.APPLE: [
        # Identificatore interno Apple (iPhone15,2): compare nelle fonti
        # ufficiali, va riconosciuto come modello a tutti gli effetti.
        r"(?:iphone|ipad|ipod)\d+,\d+",
        r"iphone\s*\d{1,2}\s*(?:pro\s*max|pro|plus|mini|e)?",
        r"iphone\s*(?:se|xr|xs\s*max|xs|x)(?:\s*\d*)?",
        r"ipad\s*pro(?:\s*\d{1,2}(?:\.\d)?)?(?:\s*(?:m\d|inch))?",
        r"ipad\s*(?:air|mini)\s*\d*(?:\s*m\d)?",
        r"ipad\s*\d{1,2}(?:th\s*gen)?",
        r"ipod\s*touch(?:\s*\d*)?",
    ],
    C.SAMSUNG: [
        r"galaxy\s+z\s+(?:fold|flip)\s*\d+(?:\s*(?:fe|5g))?",
        r"galaxy\s+tab\s+[sa]\d{1,2}(?:\s*(?:ultra|plus|\+|fe|lite))?",
        r"galaxy\s+s\d{1,2}\s*(?:ultra|plus|\+|fe|edge)?",
        r"galaxy\s+note\s*\d{1,2}(?:\s*(?:ultra|plus|\+))?",
        r"galaxy\s+[amf]\d{2,3}[a-z]?(?:\s*5g)?",
        r"galaxy\s+xcover\s*\d+(?:\s*pro)?",
        r"galaxy\s+watch\s*\d+(?:\s*(?:classic|ultra))?",
    ],
    C.XIAOMI: [
        r"redmi\s+note\s*\d{1,2}[a-z]?(?:\s*(?:pro\+?|turbo|s))?(?:\s*5g)?",
        r"redmi\s+(?:k|a)\d{1,2}[a-z]?(?:\s*(?:pro\+?|ultra))?",
        r"redmi\s+pad\s*(?:se|pro)?\s*\d*",
        r"redmi\s+\d{1,2}[a-z]?(?:\s*(?:pro\+?|c))?",
        r"poco\s+[fxmc]\d{1,2}(?:\s*(?:pro|ultra|gt))?",
        r"xiaomi\s+(?:mix\s*(?:fold|flip)\s*\d+|pad\s*\d+(?:\s*pro)?)",
        r"xiaomi\s+\d{1,2}[a-z]?(?:\s*(?:ultra|pro|lite|t\s*pro|t))?",
    ],
    C.PIXEL: [
        r"pixel\s+\d{1,2}\s*pro\s*(?:xl|fold)",
        r"pixel\s+\d{1,2}a?\s*(?:pro|xl|fold)?",
        r"pixel\s+(?:tablet|fold|watch\s*\d*)",
    ],
    C.HUAWEI: [
        r"huawei\s+mate\s*(?:x{1,2}s?\s*\d*|\d{1,2})(?:\s*(?:pro\+?|rs))?",
        r"huawei\s+p\s*\d{1,2}(?:\s*(?:pro\+?|lite|art))?",
        r"huawei\s+nova\s*\d{1,2}[a-z]?(?:\s*(?:pro|se|ultra))?",
        r"huawei\s+pura\s*\d{1,2}(?:\s*(?:pro\+?|ultra))?",
        r"honor\s+magic\s*(?:v\s*\d+|vs\s*\d+|\d+)(?:\s*(?:pro|ultimate|rsr))?",
        r"honor\s+\d{2,3}(?:\s*(?:pro\+?|lite))?",
        r"honor\s+x\d{1,2}[a-z]?(?:\s*(?:pro|b))?",
    ],
    C.OPPO: [
        r"oneplus\s+(?:nord\s*(?:ce\s*)?\d*[a-z]*(?:\s*lite)?|open|pad\s*\d*|watch\s*\d*)",
        r"oneplus\s+\d{1,2}[rt]?(?:\s*(?:pro|ace))?",
        r"oppo\s+find\s*[nx]\s*\d+(?:\s*(?:pro|ultra|s))?",
        r"oppo\s+reno\s*\d{1,2}[a-z]?(?:\s*(?:pro\+?|f))?",
        r"oppo\s+[af]\d{1,3}[a-z]?(?:\s*pro)?",
        r"realme\s+gt\s*\d+[a-z]?(?:\s*(?:pro|master|explorer)?)",
        r"realme\s+narzo\s*\d{1,2}[a-z]?(?:\s*(?:pro|x))?",
        r"realme\s+\d{1,2}[a-z]?(?:\s*(?:pro\+?|t|i))?",
    ],
    C.VIVO: [
        r"iqoo\s+(?:neo\s*\d+[a-z]?|z\d+[a-z]?|\d{1,2})(?:\s*(?:pro|turbo|ultra))?",
        r"vivo\s+[xyvts]\d{1,3}[a-z]?(?:\s*(?:pro\+?|ultra|fold\s*\d*|e))?",
        r"motorola\s+edge\s*\d{1,2}(?:\s*(?:pro|neo|ultra|fusion))?",
        r"moto\s+[gex]\s*\d{1,3}[a-z]*(?:\s*(?:power|plus|play|stylus|5g))?",
        r"(?:motorola\s+)?razr\s*(?:\d{2,4})?(?:\s*(?:plus|ultra|\+))?",
        r"moto\s+book\s*\d*",
    ],
    C.OTHER: [
        r"nothing\s+phone\s*\(?\s*\d[a-z]?\s*\)?(?:\s*pro)?",
        r"cmf\s+phone\s*\d+[a-z]?(?:\s*pro)?",
        r"(?:umidigi|doogee|cubot|blackview|ulefone|oukitel)\s+[a-z]*\s*\d{1,4}[a-z]*(?:\s*(?:pro|max|ultra))?",
        r"(?:tecno|infinix)\s+[a-z]+\s*\d{1,3}[a-z]*(?:\s*pro)?",
        r"asus\s+(?:zenfone|rog\s+phone)\s*\d{1,2}[a-z]*(?:\s*(?:pro|ultimate)?)",
        r"sony\s+xperia\s*[0-9iv]{1,4}(?:\s*[ivx]+)?",
        r"fairphone\s*\d+",
    ],
}

_COMPILED_DEVICE_PATTERNS = {
    brand: [re.compile(p, re.IGNORECASE) for p in patterns]
    for brand, patterns in DEVICE_PATTERNS.items()
}

# Come rendere leggibile un modello estratto in minuscolo.
_TOKEN_CASE = {
    "poco": "POCO", "iqoo": "iQOO", "oneplus": "OnePlus", "xcover": "XCover",
    "cmf": "CMF", "rog": "ROG", "ce": "CE", "fe": "FE", "xl": "XL", "rs": "RS",
    "rsr": "RSR", "gt": "GT", "se": "SE", "vs": "VS", "ui": "UI",
    # Apple scrive la "i" iniziale minuscola: "iPhone", non "Iphone".
    "iphone": "iPhone", "ipad": "iPad", "ipod": "iPod",
    "ios": "iOS", "ipados": "iPadOS", "max": "Max", "mini": "mini",
}
# Anche in forma composta con l'identificatore interno ("iphone15,2").
_APPLE_ID_TOKEN = re.compile(r"^(iphone|ipad|ipod)(\d+,\d+)$", re.IGNORECASE)
_ALNUM_TOKEN = re.compile(r"^[a-z]{0,2}\d+[a-z]{0,2}$")


def canonical_device(raw: str) -> str:
    """Normalizza la forma di un nome modello ('galaxy s24  ultra' → 'Galaxy S24 Ultra')."""
    raw = re.sub(r"\s+", " ", str(raw or "").strip())
    if not raw:
        return ""
    out = []
    for token in raw.split(" "):
        low = token.lower()
        apple_id = _APPLE_ID_TOKEN.match(low)
        if apple_id:
            # "iphone15,2" → "iPhone15,2" (identificatore interno Apple)
            out.append(_TOKEN_CASE[apple_id.group(1)] + apple_id.group(2))
        elif low in _TOKEN_CASE:
            out.append(_TOKEN_CASE[low])
        elif _ALNUM_TOKEN.match(low):
            out.append(low.upper())
        elif len(low) <= 2 and low.isalpha():
            out.append(low.upper())
        else:
            out.append(low[:1].upper() + low[1:])
    text = " ".join(out)
    # "Phone ( 2 A )" → "Phone (2a)"
    text = re.sub(r"\(\s*(\w+)\s*\)", lambda m: f"({m.group(1).lower()})", text)
    return text


def extract_device(text: str, brand: str | None = None) -> tuple[str | None, str | None]:
    """Restituisce (brand, modello). Entrambi possono essere None.

    Se `brand` è noto si cercano solo i pattern di quel brand; altrimenti si
    provano tutti e il brand viene dedotto dal pattern che matcha.
    """
    text = str(text or "")
    candidates = [brand] if brand in _COMPILED_DEVICE_PATTERNS else list(_COMPILED_DEVICE_PATTERNS)
    best: tuple[str, str, int] | None = None  # (brand, model, lunghezza match)
    for b in candidates:
        for pattern in _COMPILED_DEVICE_PATTERNS[b]:
            m = pattern.search(text)
            if not m:
                continue
            model = canonical_device(m.group(0))
            if best is None or len(m.group(0)) > best[2]:
                best = (b, model, len(m.group(0)))
    if best:
        return best[0], best[1]
    return (brand or detect_brand(text)), None


# ----------------------------------------------------------------------
# Parole che, dentro il nome di un modello, NON distinguono un telefono da
# un altro perché ripetono una marca che la chiave porta già.
#
# È la causa del doppione «Galaxy S24 Ultra» / «Samsung S24 Ultra»: lo
# stesso telefono in archivio due volte, ciascuna copia con metà della
# storia. Nasce dal fatto che le fonti ufficiali scrivono «Galaxy S24
# Ultra» mentre chi cerca digita «Samsung S24 Ultra» — e la ricerca live
# fissa come nome del dispositivo esattamente ciò che è stato scritto.
#
# L'elenco è volutamente CORTO. Vale solo dove la parola non può in nessun
# caso distinguere due modelli dentro lo stesso gruppo:
#
#   Samsung        «samsung» e «galaxy» sono la stessa marca detta in due modi
#   Apple          «apple» davanti a iPhone/iPad non aggiunge niente
#   Google Pixel   «google» davanti a Pixel non aggiunge niente
#
# Gli altri gruppi NON sono trattati, ed è deliberato: sotto
# «Oppo / Realme / OnePlus» le parole «oppo» e «realme» distinguono
# eccome (esistono sia un OPPO A5 sia un realme A5), e toglierle
# fonderebbe due telefoni diversi. Fondere per sbaglio è molto peggio che
# lasciare un doppione: un doppione si vede, una fusione sbagliata mostra
# la versione di un telefono sotto il nome di un altro.
_PAROLE_DI_MARCA_RIDONDANTI = {
    C.SAMSUNG: ("samsung", "galaxy"),
    C.APPLE: ("apple",),
    C.PIXEL: ("google",),
}

# Le marche che convivono dentro uno stesso gruppo. Servono alla regola
# qui sotto, che è il modo di togliere il nome del produttore SENZA
# fondere telefoni diversi.
_SOTTOMARCHE_DEL_GRUPPO = {
    C.XIAOMI: ("xiaomi", "redmi", "poco"),
    C.HUAWEI: ("huawei", "honor"),
    C.OPPO: ("oppo", "realme", "oneplus"),
    C.VIVO: ("vivo", "iqoo", "motorola", "moto"),
}


# Sotto questa lunghezza la radice non identifica un telefono, e togliere
# la sotto-marca fonderebbe cose diverse. È il numero che separa i due casi,
# e non è scelto a occhio: contando sul dataset intero, le radici contese
# fra due sotto-marche dello stesso gruppo sono il 2-3%, e sono quasi tutte
# lunghe uno o due caratteri — «2», «3», «x», «7».
_RADICE_MINIMA_SENZA_MARCA = 3


def _senza_marca_ridondante(parole: list[str], gruppo: str) -> list[str]:
    """Toglie il nome del produttore quando ciò che resta basta da solo.

    IL PROBLEMA. I dataset scrivono lo stesso telefono in tutti i modi:
    «Nord CE 3 Lite», «OnePlus Nord CE 3 Lite», «一加 Nord CE 3 Lite» —
    il nome cinese, quello inglese, o nessuno dei due. Ogni grafia una
    chiave, ogni chiave una scheda.

    PERCHÉ NON BASTAVA TOGLIERLO SEMPRE. Dentro un gruppo convivono più
    marche: «OPPO A5» e «realme A5» sono telefoni diversi, e fonderli
    sarebbe molto peggio di un doppione — mostrerebbe la versione di uno
    sotto il nome dell'altro.

    LA REGOLA, MISURATA. La sotto-marca serve solo quando ciò che resta è
    troppo corto per identificare qualcosa: contando sul dataset intero, le
    radici contese fra due sotto-marche sono il 2-3% e sono quasi tutte di
    uno o due caratteri. Sopra quella soglia il nome del produttore non
    aggiunge niente, e toglierlo fa convergere tutte le grafie.

        «OnePlus Nord CE 3 Lite» → nordce3lite   (= «Nord CE 3 Lite»)
        «Vivo X100 Pro»          → x100pro       (= «X100 Pro»)
        «OPPO A5»                → oppoa5        (resta «a5»: troppo corto)
        «Xiaomi Redmi 3»         → redmi3        (resta «3»: si tiene redmi)
    """
    sottomarche = _SOTTOMARCHE_DEL_GRUPPO.get(gruppo)
    if not sottomarche or len(parole) < 2:
        return parole
    presenti = [p for p in parole if p in sottomarche]
    if not presenti:
        return parole

    resto = [p for p in parole if p not in sottomarche]
    if len("".join(resto)) >= _RADICE_MINIMA_SENZA_MARCA:
        return resto
    # Radice troppo corta: si tiene la sotto-marca più specifica, cioè
    # l'ultima nominata («Xiaomi Redmi 3» → «redmi»).
    da_tenere = presenti[-1]
    return [p for p in parole if p not in sottomarche or p == da_tenere]


def radice_modello(brand: str, model: str) -> str:
    """La parte del nome che identifica davvero il modello, in minuscolo e
    senza separatori. «Galaxy S24 Ultra», «Samsung S24 Ultra» e «S24 Ultra»
    danno tutte e tre `s24ultra`."""
    testo = str(model or "").lower()
    # LA STESSA PAROLA DUE VOLTE DI FILA NON DISTINGUE NIENTE.
    # «POCO POCO M4 Pro», «Nokia Nokia C32», «Honor HONOR Magic6»: nomi
    # nati dall'unione di due colonne dove la marca compariva già. La
    # sorgente è corretta in `modelcodes`, ma la stessa forma può arrivare
    # da qualunque altra fonte, e qui è il punto in cui due grafie dello
    # stesso telefono devono convergere.
    testo = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", testo)
    ridondanti = _PAROLE_DI_MARCA_RIDONDANTI.get(brand)
    if ridondanti:
        ridotto = re.sub(
            r"(?<![a-z0-9])(?:" + "|".join(ridondanti) + r")(?![a-z0-9])", " ", testo)
        # Un nome fatto SOLO di parole di marca («Galaxy», «Samsung Galaxy»)
        # non è un modello: meglio tenerlo com'è che ridurlo a chiave vuota,
        # che accorperebbe fra loro tutti i nomi degeneri.
        if re.sub(r"[^a-z0-9]+", "", ridotto):
            testo = ridotto
    # E il nome del produttore quando ne resta un altro a distinguere:
    # «Xiaomi Redmi 3» = «Redmi 3», ma «Xiaomi 14» resta «Xiaomi 14».
    parole = re.sub(r"[^a-z0-9]+", " ", testo).split()
    testo = " ".join(_senza_marca_ridondante(parole, brand))
    return re.sub(r"[^a-z0-9]+", "", testo)


def device_key(brand: str, model: str) -> str:
    """Chiave stabile per identificare un device nel database.

    Cambiarne la forma invalida le chiavi già scritte in archivio, parco di
    test compreso: va sempre accompagnata dalla migrazione in
    `storage.migra_chiavi_dispositivo()`.
    """
    return f"{str(brand or '').strip().lower()}|{radice_modello(brand, model)}"


# ======================================================================
# 3. Versione OS, skin e patch level
# ======================================================================
_ANDROID_RE = re.compile(r"\bandroid\s*(\d{1,2})(?:\.\d+)?\b", re.IGNORECASE)

# LE VERSIONI DELLE SKIN SI CATTURANO PER INTERO, fino a quattro parti.
#
# Prima il gruppo si fermava a due (`\d{1,2}(?:\.\d{1,2})?`), e «MagicOS
# 9.0.0.157» diventava «MagicOS 9.0». Le due cifre buttate via erano
# proprio quelle che contano: una versione a tre o quattro parti esiste
# solo se un pacchetto e' stato davvero distribuito — e' una prova di
# distribuzione forte quanto un numero di build, mentre «MagicOS 9» da
# solo puo' essere un annuncio, un'attesa o un elenco di modelli idonei.
# Vedi `versione_precisa` piu' sotto e la regola in `scan.normalize`.
#
# Misurato il 16/08/2026: Honor dava firmware su 1 modello su 10 e vivo su
# 2 su 10, pur avendo notizie con la versione completa nel titolo.
SKIN_PATTERNS = [
    # iOS/iPadOS non sono "skin" sopra Android: sono il sistema operativo
    # stesso. Vivono comunque in questa lista perché il meccanismo che ne
    # deriva (nome + versione → etichetta leggibile) è identico, e per un
    # iPhone `android_version` resta correttamente vuoto.
    ("iPadOS", r"\bipados\s*(\d{1,2}(?:\.\d{1,2}){0,2})"),
    ("iOS", r"\bios\s*(\d{1,2}(?:\.\d{1,2}){0,2})"),
    ("One UI", r"\bone\s*ui\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("HyperOS", r"\bhyper\s*os\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("MIUI", r"\bmiui\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("ColorOS", r"\bcolor\s*os\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("OxygenOS", r"\boxygen\s*os\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("realme UI", r"\brealme\s*ui\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("MagicOS", r"\bmagic\s*os\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("HarmonyOS", r"\bharmony\s*os\s*(?:next\s*)?(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("EMUI", r"\bemui\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("Funtouch OS", r"\bfuntouch\s*os\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("OriginOS", r"\borigin\s*os\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
    ("Nothing OS", r"\bnothing\s*os\s*(\d{1,2}(?:\.\d{1,3}){0,3})"),
]
_COMPILED_SKINS = [(name, re.compile(p, re.IGNORECASE)) for name, p in SKIN_PATTERNS]

# Build/firmware: la presenza di uno di questi pattern è il segnale più
# affidabile che si stia parlando di un rilascio reale e non di un rumor.
BUILD_PATTERNS = [
    r"\b[A-Z]{2}\d[A-Z]\.\d{6}\.\d{3}(?:\.[A-Z]\d+)?\b",        # Pixel  AP4A.250105.002
    r"\b[A-Z]\d{3}[A-Z]{0,2}XX[A-Z0-9]{5,8}\b",                  # Samsung S928BXXU5BYG1
    r"\bOS\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.[A-Z]{4,8}\b",     # HyperOS OS2.0.1.0.VNCEUXM
    r"\bV\d{2}\.\d\.\d{1,2}\.\d\.[A-Z]{4,8}\b",                  # MIUI    V14.0.1.0.TKDEUXM
    r"\b\d{1,2}\.\d{1,2}\.\d{1,2}\.[A-Z]{2}\d{2}[A-Z]{2,4}\b",   # ColorOS/OxygenOS
    r"\b[A-Z]{3,}\d{2,}[A-Z0-9]{4,}\b",                          # fallback generico
]
_COMPILED_BUILDS = [re.compile(p) for p in BUILD_PATTERNS]

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_PATCH_ISO_RE = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
_PATCH_MONTH_RE = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+(20\d{2})\s+(?:security|android|patch)", re.IGNORECASE
)
_PATCH_MONTH_ALT_RE = re.compile(
    r"\b(?:security|patch)[^.]{0,20}?\b(" + "|".join(_MONTHS) + r")\s+(20\d{2})", re.IGNORECASE
)


# Il mese di un firmware Samsung sta DENTRO il numero di build.
#
# L'endpoint FOTA non pubblica nessuna data — verificato leggendo il suo
# XML: c'è la build, c'è il peso del pacchetto, la data no. Ma le ultime
# tre lettere della build la contengono: anno, mese, revisione.
#
#     S928BXXS6DZG1  →  Z=2026, G=luglio, revisione 1
#     A325FXXU1AUCC  →  U=2021, C=marzo,  revisione C
#
# LA MAPPATURA È STATA VERIFICATA SUI DATI, non presa da un forum: su dieci
# modelli europei interrogati oggi, otto cadono a luglio 2026 — il mese
# scorso, cioè dove deve stare il firmware corrente — e il Galaxy A32
# decodifica al marzo 2021, che è esattamente il modello che il progetto
# sa fermo da anni. Se la mappatura fosse sfasata, quei numeri non
# potrebbero tornare entrambi.
#
# Il GIORNO non c'è: si sa il mese, e si dice il mese.
_ANNI_BUILD_SAMSUNG = {chr(ord("R") + i): 2018 + i for i in range(12)}
_MESI_BUILD_SAMSUNG = {chr(ord("A") + i): i + 1 for i in range(12)}
_MESI_ITALIANO = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
                  "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
_RE_BUILD_SAMSUNG = re.compile(r"^[A-Z]\d{3}[A-Z]{0,2}XX[A-Z0-9]{5,8}$")


def mese_da_build_samsung(build: str) -> tuple[int, int] | None:
    """(anno, mese) letti dalla build Samsung, o None se non è una build
    Samsung o se le lettere non hanno senso."""
    testo = (build or "").strip().upper()
    if not _RE_BUILD_SAMSUNG.match(testo) or len(testo) < 4:
        return None
    anno, mese = _ANNI_BUILD_SAMSUNG.get(testo[-3]), _MESI_BUILD_SAMSUNG.get(testo[-2])
    if not anno or not mese:
        return None
    return anno, mese


def mese_leggibile(build: str) -> str | None:
    """«luglio 2026», o None se la build non dice quando è uscita."""
    quando = mese_da_build_samsung(build)
    if not quando:
        return None
    anno, mese = quando
    return f"{_MESI_ITALIANO[mese - 1]} {anno}"


def extract_android_version(text: str) -> int | None:
    m = _ANDROID_RE.search(str(text or ""))
    if not m:
        return None
    value = int(m.group(1))
    return value if 5 <= value <= 30 else None


def extract_skin(text: str) -> tuple[str, str] | None:
    """('One UI', '8.0') oppure None."""
    for name, pattern in _COMPILED_SKINS:
        m = pattern.search(str(text or ""))
        if m:
            return name, m.group(1)
    return None


def versione_precisa(versione: str | None) -> bool:
    """Una versione di skin a TRE O PIU' parti («9.0.0.157»).

    E' il discrimine fra «questo pacchetto e' uscito» e «si parla di
    questa versione». Un numero cosi' lungo non compare in un annuncio o
    in un elenco di modelli idonei: lo si scrive solo copiandolo da un
    aggiornamento reale, esattamente come un numero di build.
    """
    pezzi = [p for p in re.split(r"[^\d]+", str(versione or "")) if p]
    return len(pezzi) >= 3


def extract_build(text: str) -> str | None:
    text = str(text or "")
    for pattern in _COMPILED_BUILDS:
        m = pattern.search(text)
        if m:
            token = m.group(0)
            # Scarta falsi positivi tipo acronimi tutto maiuscolo senza cifre utili
            if len(token) >= 8:
                return token
    return None


def extract_patch_level(text: str) -> str | None:
    """Restituisce il livello patch di sicurezza normalizzato a 'YYYY-MM'."""
    text = str(text or "")
    m = _PATCH_ISO_RE.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    for regex in (_PATCH_MONTH_RE, _PATCH_MONTH_ALT_RE):
        m = regex.search(text)
        if m:
            month = _MONTHS[m.group(1).lower()]
            return f"{m.group(2)}-{month:02d}"
    return None


# ======================================================================
# 4. Risultato aggregato
# ======================================================================
@dataclass
class Extraction:
    brand: str | None = None
    device_model: str | None = None
    android_version: int | None = None
    skin_name: str | None = None
    skin_version: str | None = None
    build: str | None = None
    patch_level: str | None = None
    signals: list[str] = field(default_factory=list)

    @property
    def os_version(self) -> str:
        """Etichetta leggibile della versione ('Android 16 · One UI 8.0')."""
        parts = []
        if self.android_version:
            parts.append(f"Android {self.android_version}")
        if self.skin_name:
            parts.append(f"{self.skin_name} {self.skin_version}".strip())
        if not parts and self.patch_level:
            parts.append(f"Patch {self.patch_level}")
        return " · ".join(parts)

    @property
    def has_structural_signal(self) -> bool:
        return bool(self.build or self.android_version or self.skin_name or self.patch_level)


def extract_all(text: str, brand_hint: str | None = None) -> Extraction:
    """Esegue tutte le estrazioni su un testo (tipicamente il titolo + sommario)."""
    text = str(text or "")
    brand, model = extract_device(text, brand_hint)
    skin = extract_skin(text)
    result = Extraction(
        brand=brand or brand_hint,
        device_model=model,
        android_version=extract_android_version(text),
        skin_name=skin[0] if skin else None,
        skin_version=skin[1] if skin else None,
        build=extract_build(text),
        patch_level=extract_patch_level(text),
    )
    if result.build:
        result.signals.append("build number")
    if result.android_version:
        result.signals.append("versione Android")
    if result.skin_name:
        result.signals.append("versione interfaccia")
    if result.patch_level:
        result.signals.append("patch level")
    if result.device_model:
        result.signals.append("modello riconosciuto")
    return result
