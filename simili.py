"""Telefoni con hardware simile: stessa marca, stesso processore.

**A cosa serve nel QA.** Un difetto legato al SoC (codifica video,
fotocamera, GPU, modem) si riproduce su tutti i telefoni che montano
quel chip, e dentro la stessa marca anche il software di base è quasi
sempre lo stesso: stesso BSP, stessa skin, stessi driver. Quando il
modello segnalato non è nel parco di test — o è occupato — la domanda
pratica è «quale telefono che ho, o che posso procurarmi, gli somiglia
abbastanza da riprodurre il problema?».

## I criteri, in ordine

1. **Stessa marca** (obbligatoria). La marca è quella VERA, non il gruppo
   del tracker: il catalogo mette OnePlus e Oppo nello stesso gruppo,
   ma sono due software diversi. Redmi e POCO invece sono Xiaomi.
2. **Stesso processore** (obbligatorio). Il confronto è sul chip
   commerciale (Snapdragon 8 Gen 3, Helio G99), non sulla sigla né sul
   processo produttivo: «Qualcomm SM8650-AB Snapdragon 8 Gen 3 (4 nm)»
   e «Snapdragon 8 Gen 3 for Galaxy» sono lo stesso silicio.
3. **Stesso software** (preferito, non obbligatorio). Si confrontano
   solo dati dello stesso tipo: l'Android in archivio con l'Android in
   archivio, l'Android di lancio con l'Android di lancio. Mettere
   l'Android di lancio di un telefono accanto all'ultimo Android di un
   altro darebbe una somiglianza che non esiste.

## Cosa NON fa

Non inventa chip. Un modello senza processore noto non ha simili da
proporre, e la pagina lo dice invece di ripiegare sul nome. Una marca che
il catalogo specifiche non copre (realme, HONOR, Nothing: vedi FONTI.md)
ha solo i pochi modelli delle schede curate come candidati, e anche
questo si dice.
"""
from __future__ import annotations

import re
from functools import lru_cache

# ======================================================================
# Il chip, ridotto a una chiave confrontabile
# ======================================================================
# Produttori da togliere in testa: la chiave è il chip, non chi lo fa.
_PRODUTTORI = {"qualcomm", "qct", "mediatek", "samsung", "google", "unisoc",
               "spreadtrum", "hisilicon", "apple", "intel", "nvidia"}
# Parole che distinguono la confezione, non il silicio. «Tiger» è il nome
# di famiglia che Unisoc a volte scrive e a volte no («Unisoc T612» e
# «Unisoc Tiger T612» sono lo stesso chip); «Bionic» idem per Apple.
_PAROLE_VUOTE = {"tiger", "bionic"}
# Una sigla da sola (SM8650-AB, MT6769V/CU, SDM665): utile solo quando
# non c'è altro, perché la stessa sigla ha suffissi diversi per lo
# stesso chip e il nome commerciale è quello che le fonti scrivono.
_RE_SIGLA = re.compile(r"^(?:sm|sdm|msm|apq|mt|sc|ums|s5e|esm)\d{3,4}[a-z0-9\-/]*$")
# Una riga che nomina solo la famiglia non identifica niente:
# «Qualcomm Snapdragon», «Spreadtrum».
_SOLO_FAMIGLIA = {"snapdragon", "dimensity", "helio", "exynos", "kirin",
                  "unisoc", "spreadtrum", "mediatek", "qualcomm", ""}


def _pezzi(testo: str) -> list[str]:
    """Una stringa di chip → le singole alternative che elenca.

    Il catalogo scrive le varianti su righe diverse, ma a volte anche
    sulla stessa: «… Snapdragon 425 (28 nm) or Qualcomm MSM8920 …»,
    «Broadcom BCM21664 (3G) / Qualcomm MSM8930 …». La scheda del sito le
    unisce con « oppure ». Lo slash separa solo se circondato da spazi:
    «MT6769V/CU» è una sigla sola.
    """
    pezzi: list[str] = []
    for riga in (testo or "").splitlines():
        pezzi.extend(re.split(r"\s+(?:or|oppure)\s+|\s*/\s+|\s+/\s*", riga))
    return [p.strip() for p in pezzi if p and p.strip()]


@lru_cache(maxsize=2048)
def chiave_chip(pezzo: str) -> str | None:
    """«Qualcomm SM8650-AB Snapdragon 8 Gen 3 (4 nm) - USA» → «snapdragon 8 gen 3».

    None quando il testo non basta a identificare un chip.
    """
    testo = re.sub(r"\([^)]*\)", " ", pezzo or "")      # «(4 nm)», «(D5103,D5106)»
    testo = re.sub(r"\s+-\s+.*$", "", testo)            # « - International»
    testo = re.sub(r"\bfor galaxy\b", " ", testo, flags=re.IGNORECASE)
    parole = [p for p in re.split(r"\s+", testo.lower()) if p]
    while parole and parole[0] in _PRODUTTORI:
        parole = parole[1:]
    parole = [p for p in parole if p not in _PAROLE_VUOTE and p not in _PRODUTTORI]
    commerciali = [p for p in parole if not _RE_SIGLA.match(p)]
    # «Snapdragon 865 5G» è lo Snapdragon 865: il 5G in coda è marketing.
    while commerciali and commerciali[-1] == "5g" and len(commerciali) > 2:
        commerciali.pop()
    if commerciali and " ".join(commerciali) not in _SOLO_FAMIGLIA:
        return " ".join(commerciali)
    sigle = [p for p in parole if _RE_SIGLA.match(p)]
    if sigle:
        # Solo la sigla: se la tabella delle sigle la conosce si passa al
        # nome commerciale, così «MT6789» e «Helio G99» si incontrano.
        from . import soc
        chip = soc.chip_da_sigla(sigle[0].upper())
        if chip is not None:
            return chiave_chip(chip.nome)
        return re.split(r"[-/]", sigle[0])[0]
    return None


def chiavi_chip(testo: str | None) -> tuple[str, ...]:
    """Tutte le chiavi di chip di un campo, nell'ordine in cui compaiono."""
    viste: list[str] = []
    for pezzo in _pezzi(testo or ""):
        chiave = chiave_chip(pezzo)
        if chiave and chiave not in viste:
            viste.append(chiave)
    return tuple(viste)


def etichetta_chip(chiave: str) -> str:
    """«snapdragon 8 gen 3» → «Snapdragon 8 Gen 3», per mostrarlo."""
    return " ".join(p.upper() if re.search(r"\d", p) and len(p) <= 5 and p[0].isalpha()
                    else p.capitalize() for p in chiave.split())


# ======================================================================
# La marca vera, non il gruppo del tracker
# ======================================================================
# Sottomarchi che condividono produttore E software con la marca madre.
# OnePlus/Oppo/realme restano separati: stesso gruppo societario, ma
# OxygenOS, ColorOS e realme UI si comportano in modo diverso nei test.
_MARCA_MADRE = {"redmi": "xiaomi", "poco": "xiaomi", "iqoo": "vivo",
                "galaxy": "samsung", "moto": "motorola", "pixel": "google",
                "iphone": "apple", "ipad": "apple"}


_MARCA_MOSTRATA = {
    "samsung": "Samsung", "xiaomi": "Xiaomi", "vivo": "vivo", "motorola": "Motorola",
    "google": "Google", "apple": "Apple", "oppo": "OPPO", "oneplus": "OnePlus",
    "realme": "realme", "honor": "HONOR", "huawei": "Huawei", "nokia": "Nokia",
    "sony": "Sony", "nothing": "Nothing",
}


def marca_mostrata(marca: str) -> str:
    return _MARCA_MOSTRATA.get(marca, marca.capitalize())


def marca_di(nome: str | None) -> str:
    """La marca vera dal nome commerciale: il catalogo la scrive in testa."""
    parole = re.split(r"\s+", (nome or "").strip().lower())
    if not parole or not parole[0]:
        return ""
    prima = parole[0]
    return _MARCA_MADRE.get(prima, prima)


# Tablet, orologi e simili montano spesso lo stesso chip di un telefono,
# ma non sono un banco di prova per un'app mobile pensata per telefoni.
_RE_NON_TELEFONO = re.compile(
    r"\b(tab|pad|watch|gear|band|fit|buds|tv|book|vision)\b", re.IGNORECASE)


def e_telefono(nome: str) -> bool:
    return not _RE_NON_TELEFONO.search(nome or "")


# ======================================================================
# Il software
# ======================================================================
_RE_ANDROID = re.compile(r"\bandroid\s*(\d{1,2})", re.IGNORECASE)
_RE_ANNO = re.compile(r"\b(20\d\d|19\d\d)\b")


def android_di_lancio(os_lancio: str | None) -> int | None:
    """«Android 13, upgradable to Android 15, One UI 7» → 13.

    La PRIMA versione citata: il resto della riga è la promessa di
    aggiornamento, non quello con cui il telefono è uscito.
    """
    trovato = _RE_ANDROID.search(os_lancio or "")
    return int(trovato.group(1)) if trovato else None


def anno_di(rilascio: str | None) -> int | None:
    trovato = _RE_ANNO.search(rilascio or "")
    return int(trovato.group(1)) if trovato else None


# ======================================================================
# La ricerca
# ======================================================================
def _candidati() -> list[dict]:
    """Catalogo specifiche + schede curate, senza doppioni per nome."""
    from . import specs
    righe: list[dict] = []
    visti: set[str] = set()
    per_codice, per_nome = specs._carica_schede_curate()
    for riga in list(per_codice.values()) + list(per_nome.values()):
        if riga["nome"].lower() not in visti:
            visti.add(riga["nome"].lower())
            righe.append(riga)
    for riga in specs.carica() or []:
        if riga["nome"].lower() not in visti:
            visti.add(riga["nome"].lower())
            righe.append(riga)
    return righe


def marche_coperte(candidati: list[dict]) -> set[str]:
    return {marca_di(r["nome"]) for r in candidati}


_RE_RETE_IN_CODA = re.compile(r"\s+(5G|4G|LTE)$", re.IGNORECASE)


def forme_stesso_telefono(nome: str | None) -> set[str]:
    """Il nome, e il nome senza «5G»/«4G» in coda, in minuscolo.

    Da SM-A556B la ricerca e la scheda dicono «Samsung Galaxy A55 5G», il
    catalogo «Samsung Galaxy A55»: lo stesso telefono, che in produzione
    compariva ancora fra i propri simili (verificato il 25/09/2026 dopo il
    primo correttivo, che confrontava solo i nomi interi). Si toglie il
    suffisso solo dal nome di PARTENZA: un candidato «A55 4G» resta un
    telefono diverso da un «A55 5G».
    """
    testo = (nome or "").strip()
    if not testo:
        return set()
    forme = {testo.lower()}
    senza = _RE_RETE_IN_CODA.sub("", testo).strip()
    if senza:
        forme.add(senza.lower())
    return forme


def trova(*, nome: str, chip: str | None, marca: str = "",
          android_archivio: int | None = None,
          android_lancio: int | None = None,
          rilascio: str | None = None,
          archivio: dict[str, dict] | None = None,
          chiave_di=None,
          in_parco: set[str] | None = None,
          candidati: list[dict] | None = None,
          massimo: int = 30,
          altri_nomi: tuple[str, ...] = ()) -> dict:
    """I telefoni simili a `nome`.

    `chip` è il testo del processore come la scheda lo mostra (anche con
    « oppure » fra due varianti). `archivio` mappa chiave dispositivo →
    riga di `storage.get_devices()`; `chiave_di(marca_gruppo, nome)`
    calcola quella chiave (è `extract.device_key`, passato da fuori per
    tenere questo modulo collaudabile senza database).
    """
    archivio = archivio or {}
    in_parco = in_parco or set()
    candidati = _candidati() if candidati is None else candidati

    chiavi_rif = chiavi_chip(chip)
    marca_rif = marca_di(nome) or (marca or "").strip().lower()
    esito = {
        "chip_chiavi": list(chiavi_rif),
        "chip_etichetta": " oppure ".join(etichetta_chip(c) for c in chiavi_rif),
        "chip_certo": len(chiavi_rif) == 1,
        "marca": marca_rif,
        "marca_mostrata": marca_mostrata(marca_rif),
        "simili": [],
        "altre_marche": [],
        "motivo_vuoto": None,
        "marca_non_coperta": False,
    }
    if not chiavi_rif:
        esito["motivo_vuoto"] = (
            "Il processore di questo modello non è noto, quindi non c'è un "
            "criterio affidabile per cercarne di simili. Meglio nessuna "
            "proposta che una proposta basata sul solo nome.")
        return esito
    if marca_rif and marca_rif not in marche_coperte(candidati):
        esito["marca_non_coperta"] = True

    # LO STESSO TELEFONO NON È UN SIMILE. Il nome mostrato dalla ricerca
    # («Samsung Galaxy A55 5G», da SM-A556B) e il titolo della scheda nel
    # catalogo («Samsung Galaxy A55») sono due grafie dello stesso modello:
    # confrontando solo il primo, il telefono cercato compariva in cima
    # alla lista dei propri simili (visto in produzione il 25/09/2026).
    stessi = {forma for n in (nome, *altri_nomi) for forma in forme_stesso_telefono(n)}
    anno_rif = anno_di(rilascio)
    simili, altre = [], []
    for riga in candidati:
        nome_c = riga["nome"]
        if nome_c.lower() in stessi or not e_telefono(nome_c):
            continue
        chiavi_c = chiavi_chip(riga.get("chipset"))
        comuni = [c for c in chiavi_c if c in chiavi_rif]
        if not comuni:
            continue
        chiave = chiave_di(riga.get("marca", ""), nome_c) if chiave_di else ""
        in_archivio = archivio.get(chiave) if chiave else None
        lancio_c = android_di_lancio(riga.get("os_lancio"))
        archivio_c = (in_archivio or {}).get("android_version")
        # STESSO SOFTWARE, confrontando dati dello stesso tipo e solo
        # quelli: vedi il docstring del modulo.
        if android_archivio and archivio_c:
            software = "archivio" if int(archivio_c) == int(android_archivio) else None
        elif android_lancio and lancio_c:
            software = "lancio" if lancio_c == android_lancio else None
        else:
            software = None
        anno_c = anno_di(riga.get("rilascio"))
        voce = {
            "nome": nome_c,
            "marca": marca_di(nome_c),
            "marca_gruppo": riga.get("marca", ""),
            "chip": riga.get("chipset") or "",
            "chip_comune": etichetta_chip(comuni[0]),
            # Il candidato esiste anche con un altro chip: il match vale
            # solo per una delle sue varianti, e chi lo prende deve
            # controllare la sigla del telefono che ha in mano.
            "solo_una_variante": len(chiavi_c) > 1,
            "android_lancio": lancio_c,
            "android_archivio": int(archivio_c) if archivio_c else None,
            "stesso_software": software,
            "rilascio": riga.get("rilascio") or "",
            "anno": anno_c,
            "os_lancio": riga.get("os_lancio") or "",
            "chiave": chiave,
            "in_archivio": bool(in_archivio),
            "in_parco": bool(chiave and chiave in in_parco),
        }
        distanza = abs(anno_c - anno_rif) if (anno_c and anno_rif) else 99
        ordine = (
            software is None, software != "archivio", not voce["in_parco"],
            not voce["in_archivio"], voce["solo_una_variante"], distanza, nome_c.lower(),
        )
        if voce["marca"] == marca_rif:
            simili.append((ordine, voce))
        else:
            altre.append((ordine, voce))
    esito["simili"] = [v for _, v in sorted(simili, key=lambda x: x[0])[:massimo]]
    esito["altre_marche"] = [v for _, v in sorted(altre, key=lambda x: x[0])[:massimo]]
    esito["quanti_simili"] = len(simili)
    esito["quante_altre"] = len(altre)
    return esito
