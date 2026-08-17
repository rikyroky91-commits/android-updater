"""Scheda tecnica di un dispositivo: chip, RAM, schermo, batteria, foto.

## Perché esiste

Fino alla v44 il progetto sapeva rispondere a «a che versione sta questo
telefono» ma non a «che telefono è». Mancavano due cose che per il QA non
sono un contorno:

* **il processore**, perché un difetto legato al SoC si riproduce solo su
  una delle varianti — ed era assente proprio sui modelli recenti, che sono
  quelli che si testano;
* **la RAM**, perché è la prima cosa che si guarda quando un'app va in OOM
  o è lenta solo su un dispositivo del parco.

La tabella curata a mano (`data/soc_modelli.csv`) copre venti modelli di
punta, e il dataset multi-marca già in uso è fermo al 2021: `SM-A075F`, un
Galaxy A07 uscito nel 2025, non era in nessuno dei due. Da qui questa fonte.

## Che cos'è la fonte

`bytecharts/device_specs_gsmarena` è una copia in JSON del catalogo
GSMArena, un file per modello, aggiornata di continuo. Si scarica in un
colpo solo come archivio (**circa 1,6 MB compressi**, 4700 schede) e
contiene, per ogni dispositivo:

    Misc.Models       SM-A075B, SM-A075F, SM-A075M, ...   ← i CODICI
    Platform.Chipset  Mediatek Helio G99 (6 nm)
    Memory.Internal   64GB 4GB RAM, 128GB 6GB RAM, ...
    imageUrl          la foto del modello
    release_date, Display, Battery, Main Camera, ...

Il campo `Misc.Models` è quello che la rende utilizzabile qui: permette di
indicizzare **per codice modello**, che è la chiave con cui questo progetto
ragiona ovunque, invece che per nome commerciale. Il dataset del 2021
espone la stessa colonna ma non veniva letta: era indicizzato per nome, e
per questo non sapeva distinguere le varianti regionali.

## Due limiti, dichiarati

1. **Le marche coperte sono undici** (Samsung, Xiaomi, OPPO, OnePlus, vivo,
   Motorola, Google, Apple, Sony, Nokia). HONOR, realme, Huawei e Nothing
   non sono nel mirror: per loro si prova il ripiego per modello; per HONOR
   anche la pagina prodotto italiana ufficiale, senza scaricare un catalogo.
2. **Un chip per scheda, non per codice.** Dove GSMArena elenca due chip
   («Snapdragon negli USA, Exynos altrove») la scheda è una sola e i codici
   stanno tutti insieme: da qui non si può sapere quale codice monta quale.
   In quel caso si riporta l'ambiguità invece di scegliere — e la tabella
   curata, che le varianti le distingue davvero, **viene prima di questa**.

Nessun dato di questo modulo entra in archivio: si legge al momento di
mostrare una scheda. Per questo `DATA_LOGIC_VERSION` non cambia.
"""
from __future__ import annotations

import gzip
import html
import io
import json
import os
import re
import tarfile
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import config as C

CARTELLA_DATI = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FILE_SCHEDE_CURATE = os.path.join(CARTELLA_DATI, "schede_curate.json")

# L'archivio del branch principale. `codeload` è l'host che GitHub usa per
# gli archivi: risponde senza autenticazione e non consuma il rate limit
# dell'API, che è la ragione per cui non si passa da `api.github.com`.
ARCHIVIO_URL = (
    "https://codeload.github.com/bytecharts/device_specs_gsmarena/"
    "tar.gz/refs/heads/main"
)
FONTE_LABEL = "catalogo specifiche GSMArena (mirror JSON)"
FONTE_HONOR_LABEL = "specifiche ufficiali HONOR Italia"

# Le schede cambiano quando esce un modello nuovo: qualche volta al mese.
_RINFRESCA_ORE = 24 * 14
_BLOB_SCHEDE = "specs_schede_gz"
_META_SCARICATO = "specs_scaricato_at"

# Un archivio più piccolo di così non è l'archivio: è una pagina di errore.
_DIMENSIONE_MINIMA = 200_000

_lock = threading.Lock()
_schede: list[dict] | None = None
_per_codice: dict[str, dict] = {}
_per_nome: dict[str, dict] = {}
_status = "non ancora caricato"
_curate_per_codice: dict[str, dict] | None = None
_curate_per_nome: dict[str, dict] | None = None

# Le pagine prodotto HONOR sono individuali: una piccola cache LRU evita che
# una ricerca, la sua scheda e un eventuale refresh ricarichino tre volte lo
# stesso HTML. Non è un catalogo in memoria e non cambia il profilo OOM.
_HONOR_SPECS_TTL = 24 * 60 * 60
_HONOR_SPECS_CACHE_LIMIT = 32
_honor_specs_cache: dict[str, tuple[float, Scheda | None]] = {}
_honor_specs_lock = threading.Lock()


# ======================================================================
# Pulizia del testo
# ======================================================================
# I valori arrivano come frammenti di HTML: entità (`&amp;`, `&nbsp;`),
# tag di formattazione (`<sup>2</sup>`) e link interni al sito. Mostrarli
# tali e quali significa scrivere «Octa-core (2x2.4 GHz Cortex-A76 &amp;»
# in interfaccia.
_RE_TAG = re.compile(r"<[^>]+>")
_RE_SPAZI = re.compile(r"[ \t\u00a0]+")


def pulisci(valore) -> str:
    testo = _RE_TAG.sub(" ", str(valore or ""))
    testo = html.unescape(testo).replace("\u00a0", " ")
    righe = [_RE_SPAZI.sub(" ", r).strip() for r in testo.splitlines()]
    return "\n".join(r for r in righe if r).strip()


# ======================================================================
# La scheda
# ======================================================================
@dataclass(frozen=True)
class Scheda:
    """Quello che si sa dell'hardware di un modello."""
    nome: str
    marca: str = ""
    foto: str | None = None
    codici: tuple[str, ...] = ()
    rilascio: str | None = None
    chipset: str | None = None
    cpu: str | None = None
    gpu: str | None = None
    ram_gb: tuple[int, ...] = ()
    storage_gb: tuple[int, ...] = ()
    memoria: str | None = None          # la riga grezza, con tutti i tagli
    display: str | None = None
    display_tipo: str | None = None
    batteria: str | None = None
    ricarica: str | None = None
    camera_post: str | None = None
    camera_front: str | None = None
    os_lancio: str | None = None
    peso: str | None = None
    dimensioni: str | None = None
    # LA SCHEDA COMPLETA STA RIPIEGATA IN UNA STRINGA, non sparsa in
    # mille dizionari. Vedi la nota su `_ripiega_sezioni`: sono 47 MB
    # tenuti sempre per un pannello che si apre di rado, e `sezioni` qui
    # sotto li rende senza che chi legge debba saperlo.
    sezioni_json: str = ""
    fonte: str = FONTE_LABEL

    @property
    def sezioni(self) -> dict:
        """Le specifiche complete, ricostruite al momento di mostrarle."""
        return _espandi_sezioni(self.sezioni_json)

    # ---- comodità per l'interfaccia -----------------------------------
    @property
    def ram_etichetta(self) -> str | None:
        """«4 / 6 / 8 GB» — tutti i tagli, perché il parco di test ne ha
        più di uno e sapere quale si ha in mano è metà della diagnosi."""
        if not self.ram_gb:
            return None
        return " / ".join(f"{v:g}" for v in self.ram_gb) + " GB"

    @property
    def storage_etichetta(self) -> str | None:
        if not self.storage_gb:
            return None
        return " / ".join(f"{v} GB" if v < 1024 else f"{v // 1024} TB"
                          for v in self.storage_gb)

    @property
    def chip_varianti(self) -> list[str]:
        """I chip elencati, uno per riga nel dato originale.

        Più di uno significa che il modello esiste in versioni con chip
        diverso: è un'informazione, non un problema da nascondere.
        """
        if not self.chipset:
            return []
        return [r.strip() for r in self.chipset.splitlines() if r.strip()]

    @property
    def chip_ambiguo(self) -> bool:
        return len(self.chip_varianti) > 1


# ======================================================================
# Lettura di una singola scheda
# ======================================================================
_RE_TAGLI = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|MB|TB)(?:\s+(\d+(?:\.\d+)?)\s*(GB|MB)\s*RAM)?",
                       re.IGNORECASE)
_MOLTIPLICATORE = {"MB": 1 / 1024, "GB": 1.0, "TB": 1024.0}


def leggi_memoria(riga: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """`"64GB 4GB RAM, 128GB 6GB RAM"` → storage (64, 128), RAM (4, 6).

    La riga di GSMArena mescola due grandezze nello stesso campo e in un
    ordine fisso: prima l'archiviazione, poi la RAM. Le forme senza RAM
    («64GB», i telefoni vecchi) restano valide per l'archiviazione: si
    legge quello che c'è invece di scartare tutta la riga.
    """
    storage: list[int] = []
    ram: list[float] = []
    for quanto, unita, quanta_ram, unita_ram in _RE_TAGLI.findall(riga or ""):
        valore = float(quanto) * _MOLTIPLICATORE.get(unita.upper(), 1.0)
        if valore >= 1:
            storage.append(int(round(valore)))
        if quanta_ram:
            ram.append(float(quanta_ram) * _MOLTIPLICATORE.get(unita_ram.upper(), 1.0))
    ordina = lambda valori: tuple(sorted({round(v, 1) if v < 1 else int(v)
                                          for v in valori}))
    return ordina(storage), ordina(ram)


_RE_CODICE = re.compile(r"[A-Z0-9]{2,}[A-Z0-9\-]*", re.IGNORECASE)


def leggi_codici(riga: str) -> list[str]:
    """`"SM-A075F, SM-A075F/DS"` → `["SM-A075F"]`.

    Il suffisso `/DS` (dual SIM) e simili si tolgono: identificano una
    confezione, non un telefono diverso, e chi digita il codice lo scrive
    quasi sempre senza. Tenerli come chiavi separate raddoppierebbe
    l'indice senza aggiungere un solo dispositivo.
    """
    codici: list[str] = []
    for pezzo in re.split(r"[,\n;]+", riga or ""):
        radice = pezzo.strip().upper().split("/")[0].strip()
        if len(radice) < 4 or not _RE_CODICE.fullmatch(radice):
            continue
        if not any(c.isdigit() for c in radice):
            continue
        if radice not in codici:
            codici.append(radice)
    return codici


_MARCHE = {
    "samsung": C.SAMSUNG,
    "xiaomi": C.XIAOMI, "redmi": C.XIAOMI, "poco": C.XIAOMI,
    "google": C.PIXEL,
    "oppo": C.OPPO, "oneplus": C.OPPO, "realme": C.OPPO,
    "vivo": C.VIVO, "iqoo": C.VIVO, "motorola": C.VIVO,
    "honor": C.HUAWEI, "huawei": C.HUAWEI,
    "apple": C.APPLE,
}


def marca_da_cartella(percorso: str) -> tuple[str, str]:
    """`samsung-phones-9` → («samsung», brand del tracker)."""
    grezza = percorso.split("-phones-")[0].split("/")[-1].strip().lower()
    return grezza, _MARCHE.get(grezza, C.OTHER)


_SEZIONI_VUOTE: dict = {}


def _ripiega_sezioni(sezioni: dict) -> str:
    """Le specifiche complete, in UNA stringa invece che in mille oggetti.

    QUARANTASETTE MEGABYTE, ed è il numero che ha motivato questa
    funzione. Misurato il 2026-08-10 caricando il catalogo vero: le 4766
    schede tenute in chiaro costano 47 MB di memoria perenne, su un host
    che ne ha 512 in tutto e che ha già riavviato il servizio d'ufficio
    per averli superati. Ogni riavvio è un avvio a freddo: il costo non
    si paga in memoria, si paga in lentezza.

    ## Perché una stringa e non un gzip

    Il primo tentativo comprimeva ogni scheda e la teneva in base64.
    Funzionava in memoria e **peggiorava l'archivio**: `tracker.db`
    passava da 10,6 a 12,2 MB, perché il base64 di dati già compressi
    non si ricomprime, e quel file la compressione esterna se
    l'aspettava. Misurato, non previsto.

    La stringa semplice va meglio su tutti e due i fronti, e il motivo
    è che il peso non era nel testo ma negli OGGETTI: quindici sezioni
    per scheda, dieci voci per sezione, fanno circa settecentomila
    stringhe e dizionari Python: 47 MB di intestazioni per una manciata
    di megabyte di contenuto. Una stringa sola per scheda toglie quelle
    intestazioni senza costare un solo ciclo di compressione — e
    l'archivio la comprime come ha sempre fatto, perché è testo.
    """
    if not sezioni:
        return ""
    return json.dumps(sezioni, ensure_ascii=False, separators=(",", ":"))


def _espandi_sezioni(ripiegate: str) -> dict:
    """Il giro inverso. Una scheda illeggibile rende un dizionario vuoto:
    la pagina mostra una sezione in meno invece di non aprirsi."""
    if not ripiegate:
        return _SEZIONI_VUOTE
    try:
        return json.loads(ripiegate)
    except Exception:
        return _SEZIONI_VUOTE


def leggi_scheda(dati: dict, marca_grezza: str = "", marca: str = "") -> dict | None:
    """Da una `details.json` alla forma compatta che teniamo in memoria.

    Si conserva **tutto** il blocco delle specifiche, non solo i campi che
    l'interfaccia usa oggi: è quello che permette di mostrare una scheda
    tecnica completa senza dover riscaricare o ri-parsare niente. Il
    blocco però si tiene COMPRESSO — vedi `_comprimi_sezioni`.
    """
    corpo = (dati or {}).get("data") or {}
    nome = pulisci(corpo.get("model"))
    if not nome:
        return None

    grezze = corpo.get("specifications") or {}
    sezioni: dict[str, dict[str, str]] = {}
    for titolo, campi in grezze.items():
        if not isinstance(campi, dict):
            continue
        puliti = {pulisci(k): pulisci(v) for k, v in campi.items() if pulisci(v)}
        if puliti:
            sezioni[pulisci(titolo)] = puliti

    def campo(sezione: str, chiave: str) -> str | None:
        return (sezioni.get(sezione) or {}).get(chiave) or None

    memoria = campo("Memory", "Internal") or ""
    storage_gb, ram_gb = leggi_memoria(memoria)
    codici = leggi_codici(campo("Misc", "Models") or "")

    foto = pulisci(corpo.get("imageUrl")) or None
    if not foto:
        immagini = corpo.get("device_images") or []
        if immagini and isinstance(immagini, list):
            foto = pulisci((immagini[0] or {}).get("url")) or None

    return {
        "nome": nome,
        "marca": marca or _MARCHE.get(marca_grezza, C.OTHER),
        "foto": foto,
        "codici": codici,
        "rilascio": (campo("Launch", "Announced")
                     or pulisci(corpo.get("release_date")) or None),
        "chipset": campo("Platform", "Chipset"),
        "cpu": campo("Platform", "CPU"),
        "gpu": campo("Platform", "GPU"),
        "ram_gb": list(ram_gb),
        "storage_gb": list(storage_gb),
        "memoria": memoria or None,
        "display": campo("Display", "Size"),
        "display_tipo": campo("Display", "Type"),
        "batteria": campo("Battery", "Type"),
        "ricarica": campo("Battery", "Charging"),
        "camera_post": (campo("Main Camera", "Triple") or campo("Main Camera", "Quad")
                        or campo("Main Camera", "Dual") or campo("Main Camera", "Single")),
        "camera_front": (campo("Selfie camera", "Single")
                         or campo("Selfie camera", "Dual")),
        "os_lancio": campo("Platform", "OS"),
        "peso": campo("Body", "Weight"),
        "dimensioni": campo("Body", "Dimensions"),
        "sezioni_json": _ripiega_sezioni(sezioni),
    }


def _a_scheda(riga: dict) -> Scheda:
    return Scheda(
        nome=riga["nome"], marca=riga.get("marca", ""), foto=riga.get("foto"),
        codici=tuple(riga.get("codici") or ()),
        rilascio=riga.get("rilascio"), chipset=riga.get("chipset"),
        cpu=riga.get("cpu"), gpu=riga.get("gpu"),
        ram_gb=tuple(riga.get("ram_gb") or ()),
        storage_gb=tuple(riga.get("storage_gb") or ()),
        memoria=riga.get("memoria"), display=riga.get("display"),
        display_tipo=riga.get("display_tipo"), batteria=riga.get("batteria"),
        ricarica=riga.get("ricarica"), camera_post=riga.get("camera_post"),
        camera_front=riga.get("camera_front"), os_lancio=riga.get("os_lancio"),
        peso=riga.get("peso"), dimensioni=riga.get("dimensioni"),
        sezioni_json=riga.get("sezioni_json") or "",
        # La fonte si legge dalla riga e non si dà per scontata: dalla v49
        # le schede non arrivano più tutte da qui (vedi `_ripiego_esterno`),
        # e una scheda presa altrove non deve dichiarare GSMArena in fondo
        # alla pagina — è l'unica riga che dice a chi legge da dove viene
        # quello che sta guardando.
        fonte=riga.get("fonte") or FONTE_LABEL,
    )


def gruppo_marca(testo: str) -> str:
    """Il gruppo del tracker a cui appartiene una marca, comunque sia scritta.

    Una ricerca esatta in `_MARCHE` copre solo le grafie previste. I nomi
    delle marche però arrivano dai database TAC, che sono alimentati dalla
    community e scrivono la stessa azienda in molti modi: accanto a
    ``SAMSUNG`` c'è ``Samsung Electronics Co Ltd``. Con il confronto esatto
    quella forma non corrispondeva a niente e il filtro scartava ogni
    scheda — quaranta modelli su quaranta senza specifiche né foto nel
    banco di prova, col nome giusto sopra.

    Si cerca quindi un marchio noto DENTRO la stringa. Se ne compaiono di
    gruppi diversi non si indovina: si restituisce il testo com'è, e il
    confronto fallirà come prima. Meglio un filtro che non riconosce una
    marca ambigua di uno che assegna il telefono alla famiglia sbagliata,
    che è il motivo per cui questo filtro esiste.
    """
    testo = (testo or "").strip()
    if not testo:
        return testo
    diretto = _MARCHE.get(testo.lower())
    if diretto:
        return diretto
    parole = re.split(r"[^0-9a-zA-Z]+", testo.lower())
    gruppi = {_MARCHE[p] for p in parole if p in _MARCHE}
    return gruppi.pop() if len(gruppi) == 1 else testo


def _marca_compatibile(scheda: Scheda, richiesta: str | None) -> bool:
    """Evita che una coincidenza di nome attraversi una famiglia di marchi.

    Il catalogo contiene sia ``Redmi Pad Pro`` sia ``OnePlus Pad Pro``. La
    ricerca per nome può usare gli alias *dentro* Xiaomi/Redmi/POCO, ma non
    può trasformare il primo nel secondo. Le schede curate talvolta salvano
    il nome breve della marca (``Xiaomi``), mentre il catalogo usa il gruppo
    del tracker: `_MARCHE` normalizza entrambi prima del confronto.

    ENTRAMBI, appunto: fino al 17/08/2026 qui si normalizzava solo la marca
    TROVATA, e la richiesta si confrontava alla lettera. Chi chiedeva con il
    nome corto — il database TAC risponde ``OPPO``, ``MOTOROLA`` — non
    trovava mai niente, perché il catalogo indicizza il gruppo
    ``Oppo / Realme / OnePlus``. Da un IMEI sparivano insieme nome
    commerciale, scheda tecnica e foto, mentre cercando lo stesso telefono
    a mano (senza marca, quindi senza filtro) compariva tutto: è il guasto
    segnalato dall'utente su CPH2781 e XT2553-1.

    La normalizzazione vera e propria sta in `gruppo_marca`: il nome corto
    non era l'unica grafia che mancava all'appello.
    """
    if not richiesta:
        return True
    return gruppo_marca(scheda.marca or "") == gruppo_marca(richiesta)


# ======================================================================
# Archivio → elenco di schede
# ======================================================================
def leggi_archivio(dati: bytes) -> list[dict]:
    """Estrae le schede dal `tar.gz` scaricato, senza scriverlo su disco.

    Le voci illeggibili si saltano una per una: un file corrotto su 4700
    non deve far perdere le altre 4699.
    """
    schede: list[dict] = []
    try:
        archivio = tarfile.open(fileobj=io.BytesIO(dati), mode="r:gz")
    except (tarfile.TarError, OSError, EOFError):
        return schede
    with archivio:
        for membro in archivio:
            if not membro.isfile() or not membro.name.endswith("details.json"):
                continue
            pezzi = membro.name.split("/")
            cartella = pezzi[1] if len(pezzi) > 2 else ""
            if "-phones-" not in cartella:
                continue
            marca_grezza, marca = marca_da_cartella(cartella)
            try:
                estratto = archivio.extractfile(membro)
                if estratto is None:
                    continue
                dati_json = json.loads(estratto.read().decode("utf-8", "replace"))
            except (tarfile.TarError, OSError, ValueError):
                continue
            letta = leggi_scheda(dati_json, marca_grezza, marca)
            if letta:
                schede.append(letta)
    return schede


# ======================================================================
# Indici
# ======================================================================
def _forme_nome(nome: str) -> list[str]:
    """Tutti i modi in cui la gente scrive lo stesso nome.

    Si riusa la funzione di `soc`, che è già collaudata su questo: l'import
    è qui dentro e non in cima al file perché `soc` a sua volta consulta
    questo modulo, e a livello di modulo i due si aspetterebbero a vicenda.
    """
    from . import soc
    return soc.varianti_nome(nome)


# Sotto questa lunghezza un nome non identifica un telefono: la forma
# abbreviata di «OnePlus 2» è «2».
_LUNGHEZZA_MINIMA = 3


def indicizza(schede: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    """(per codice, per nome). I nomi contesi si buttano, i codici no.

    Un codice modello identifica un telefono e uno solo: se due schede se
    lo contendono vince la prima, che nella pratica non capita.

    Un nome abbreviato invece no. `varianti_nome` genera anche la forma
    senza marca, ed è quello che rende utile l'indice — «Samsung S24
    Ultra» trova «Galaxy S24 Ultra» — ma la stessa abbreviazione accorpa
    telefoni che non c'entrano niente. Quando due schede DIVERSE reclamano
    la stessa forma breve, la chiave si toglie: meglio non rispondere che
    rispondere a caso. È la stessa regola già applicata al dataset del 2021.
    """
    per_codice: dict[str, dict] = {}
    per_nome: dict[str, dict] = {}
    contese: set[str] = set()

    for riga in schede:
        for codice in riga.get("codici") or ():
            per_codice.setdefault(codice.upper(), riga)

        for forma in _forme_nome(riga["nome"]):
            if len(forma) < _LUNGHEZZA_MINIMA or forma in contese:
                continue
            precedente = per_nome.get(forma)
            if precedente is None:
                per_nome[forma] = riga
            elif precedente["nome"] != riga["nome"]:
                contese.add(forma)
                per_nome.pop(forma, None)
    return per_codice, per_nome


# ======================================================================
# Rete e cache
# ======================================================================
def _scarica() -> bytes | None:
    if requests is None:  # pragma: no cover
        return None
    try:
        risposta = requests.get(ARCHIVIO_URL, timeout=90,
                                headers={"User-Agent": C.USER_AGENT})
    except Exception:
        return None
    if getattr(risposta, "status_code", 0) != 200:
        return None
    contenuto = risposta.content
    if not contenuto or len(contenuto) < _DIMENSIONE_MINIMA:
        return None
    return contenuto


def _carica_schede_curate() -> tuple[dict[str, dict], dict[str, dict]]:
    """Le poche schede verificate in repository, senza rete né cataloghi bulk.

    Sono il percorso critico per modelli che un catalogo generale non copre.
    Vengono lette prima dell'archivio GSMArena: la pagina può rispondere con
    dati completi senza decomprimere migliaia di schede e senza rischiare un
    picco di memoria sul piano Render da 512 MB.
    """
    global _curate_per_codice, _curate_per_nome
    if _curate_per_codice is not None:
        return _curate_per_codice, _curate_per_nome or {}
    try:
        with open(FILE_SCHEDE_CURATE, encoding="utf-8") as f:
            righe = json.load(f)
    except (OSError, ValueError):
        righe = []
    if not isinstance(righe, list):
        righe = []
    _curate_per_codice, _curate_per_nome = indicizza(
        [r for r in righe if isinstance(r, dict) and r.get("nome")]
    )
    return _curate_per_codice, _curate_per_nome


def _curata_per_codice(codice: str) -> Scheda | None:
    per_codice, _per_nome_curato = _carica_schede_curate()
    riga = per_codice.get((codice or "").strip().upper().split("/")[0])
    return _a_scheda(riga) if riga else None


def _curata_per_nome(nome: str) -> Scheda | None:
    _per_codice_curato, per_nome = _carica_schede_curate()
    for forma in _forme_nome(nome):
        riga = per_nome.get(forma)
        if riga:
            return _a_scheda(riga)
    return None


def carica_da(schede: list[dict], etichetta: str = "elenco fornito") -> list[dict]:
    """Indicizza schede già in mano, **senza toccare la rete**.

    Esiste per i test e per un'eventuale copia locale: la stessa porta
    aperta da `aer_catalog.carica_da`, e per lo stesso motivo — collaudare
    un parser non deve dipendere da cosa risponde un server oggi.
    """
    global _schede, _per_codice, _per_nome, _status
    with _lock:
        _schede = list(schede)
        _per_codice, _per_nome = indicizza(_schede)
        _status = (f"{len(_schede)} schede, {len(_per_codice)} codici modello "
                   f"({etichetta})")
        return _schede


def carica() -> list[dict]:
    """Le schede, dalla cache se è fresca, altrimenti dalla rete.

    Se il download fallisce ma una copia in archivio c'è, si usa quella:
    un catalogo vecchio è enormemente meglio di nessun catalogo, e la
    differenza fra i due la vede solo chi cerca un modello uscito la
    settimana scorsa.
    """
    global _schede, _per_codice, _per_nome, _status
    if _schede is not None:
        return _schede

    with _lock:
        if _schede is not None:
            return _schede

        grezzo = None
        etichetta = ""
        try:
            from . import storage
            cache = storage.get_blob(_BLOB_SCHEDE)
            quando = storage.get_meta(_META_SCARICATO)
            fresca = False
            if cache and quando:
                try:
                    eta = (datetime.now(timezone.utc)
                           - datetime.fromisoformat(quando)).total_seconds() / 3600
                    fresca = eta < _RINFRESCA_ORE
                except ValueError:
                    fresca = False
            if fresca and cache:
                grezzo = json.loads(gzip.decompress(cache).decode("utf-8"))
                etichetta = "da archivio"
            else:
                scaricato = _scarica()
                if scaricato:
                    grezzo = leggi_archivio(scaricato)
                    etichetta = "scaricato"
                    if grezzo:
                        storage.set_blob(
                            _BLOB_SCHEDE,
                            gzip.compress(json.dumps(
                                grezzo, ensure_ascii=False).encode("utf-8"), 6),
                        )
                        storage.set_meta(_META_SCARICATO,
                                         datetime.now(timezone.utc).isoformat())
                elif cache:
                    grezzo = json.loads(gzip.decompress(cache).decode("utf-8"))
                    etichetta = "da archivio (download fallito)"
        except Exception as errore:
            _status = f"non disponibile: {errore}"
            grezzo = None

        _schede = list(grezzo or [])
        _per_codice, _per_nome = indicizza(_schede)
        if _schede:
            _status = (f"{len(_schede)} schede, {len(_per_codice)} codici modello "
                       f"({etichetta})")
        elif _status == "non ancora caricato":
            _status = "non disponibile (download fallito)"
        return _schede


def reset_cache() -> None:
    global _schede, _per_codice, _per_nome, _status
    with _lock:
        _schede = None
        _per_codice = {}
        _per_nome = {}
        _status = "non ancora caricato"
    with _honor_specs_lock:
        _honor_specs_cache.clear()


def status() -> str:
    return _status


# ======================================================================
# Ricerca
# ======================================================================
def per_codice(codice: str) -> Scheda | None:
    chiave = (codice or "").strip().upper().split("/")[0]
    if not chiave:
        return None
    curata = _curata_per_codice(chiave)
    if curata:
        return curata
    carica()
    riga = _per_codice.get(chiave)
    return _a_scheda(riga) if riga else None


# Suffissi che distinguono due confezioni dello stesso telefono, non due
# telefoni. Chi cerca «Galaxy A07» intende il Galaxy A07, e il catalogo lo
# chiama «Galaxy A07 4G» perché ne esiste anche una versione 5G.
_SUFFISSI_CONNETTIVITA = ("4G", "5G", "LTE", "5G UW")


def per_nome(nome: str, marca: str | None = None) -> Scheda | None:
    testo = (nome or "").strip()
    if not testo:
        return None
    curata = _curata_per_nome(testo)
    if curata and _marca_compatibile(curata, marca):
        return curata
    carica()
    forme = _forme_nome(testo)
    for forma in forme:
        riga = _per_nome.get(forma)
        if riga:
            trovata = _a_scheda(riga)
            if _marca_compatibile(trovata, marca):
                return trovata

    # RIPIEGO, e solo se non è ambiguo. Si accetta una scheda il cui nome
    # è quello cercato più un suffisso di connettività — ma **una sola**:
    # se il catalogo ne ha due (la 4G e la 5G) scegliere sarebbe indovinare,
    # e le due montano spesso chip diversi.
    for forma in forme:
        candidate = []
        for suffisso in _SUFFISSI_CONNETTIVITA:
            riga = _per_nome.get(f"{forma} {suffisso}")
            if (riga is not None and riga not in candidate
                    and _marca_compatibile(_a_scheda(riga), marca)):
                candidate.append(riga)
        if len(candidate) == 1:
            return _a_scheda(candidate[0])
    return None


# Il ripiego per le marche fuori perimetro. È una variabile e non una
# costante perché i test la spengono: una scheda che dipende da cosa
# risponde un server di terzi non è collaudabile.
RIPIEGO_ESTERNO = True


_HONOR_PRODUCT_URL = "https://www.honor.com/it/phones/{slug}/"
_HONOR_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HONOR_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)',
    re.IGNORECASE,
)
_HONOR_BATTERIA_RE = re.compile(r"\b(\d{4,5})\s*mAh\b", re.IGNORECASE)
_HONOR_RICARICA_RE = re.compile(r"\b(\d{2,3})\s*W\b[^.]{0,48}(?:SuperCharge|ricaric)", re.IGNORECASE)
_HONOR_PESO_RE = re.compile(r"\bpeso\s*(\d{2,3}(?:[,.]\d+)?)\s*g\b", re.IGNORECASE)
_HONOR_SPESSORE_RE = re.compile(r"\bspessore\s*(\d(?:[,.]\d+)?)\s*mm\b", re.IGNORECASE)
_HONOR_CAMERA_RE = re.compile(r"\b(\d{2,3})\s*MP\b", re.IGNORECASE)
_HONOR_RISOLUZIONE_RE = re.compile(r"\b(\d{3,4})\s*[×x*]\s*(\d{3,4})\b")
_HONOR_HZ_RE = re.compile(r"\b(\d{2,3})\s*Hz\b", re.IGNORECASE)


def _chiave_honor(valore: str) -> str:
    """Chiave URL/testo per un nome HONOR, senza accenti o punteggiatura."""
    decomposed = unicodedata.normalize("NFKD", valore or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(re.findall(r"[a-z0-9]+", ascii_text.lower()))


def _slug_honor(nome: str) -> str | None:
    """``HONOR Magic7 Lite`` → ``honor-magic7-lite`` in modo sicuro."""
    decomposed = unicodedata.normalize("NFKD", nome or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9]+", ascii_text.lower())
    if words and words[0] == "honor":
        words = words[1:]
    if not words or not any(any(ch.isdigit() for ch in word) for word in words):
        return None
    return "honor-" + "-".join(words)


def _testo_honor_pagina(html_text: str) -> str:
    """Testo breve della pagina prodotto, per i campi non strutturati."""
    return pulisci(re.sub(r"<[^>]+>", " ", html_text or ""))


def _scheda_honor_da_html(nome: str, pagina: str, url: str) -> Scheda | None:
    """Legge i dati dichiarati nella pagina prodotto HONOR italiana.

    La pagina non espone JSON-LD stabile: si estraggono soltanto misure e
    valori accompagnati dalla loro unità. Un campo assente resta assente;
    non si completa da brochure di altri paesi né da rebrand affini.
    """
    title_match = _HONOR_TITLE_RE.search(pagina or "")
    titolo = pulisci(title_match.group(1)) if title_match else ""
    chiave_nome = _chiave_honor(nome)
    if not titolo or not chiave_nome or chiave_nome not in _chiave_honor(titolo):
        return None

    # La stessa risposta HTML contiene il catalogo completo del menu: senza
    # questo ritaglio ``100 W`` di un alimentatore HONOR diventava la ricarica
    # del telefono. Le immagini della pagina prodotto sono invece in una
    # cartella che contiene ESATTAMENTE il suo slug; è il confine stabile fra
    # contenuto del modello e navigazione generale.
    slug = _slug_honor(nome)
    marker = f"/products/smartphone/{slug}/" if slug else ""
    start = pagina.lower().find(marker.lower()) if marker else -1
    if start < 0:
        return None
    pagina_prodotto = pagina[start:]
    testo = _testo_honor_pagina(pagina_prodotto)
    batteria = _HONOR_BATTERIA_RE.search(testo)
    ricarica = _HONOR_RICARICA_RE.search(testo)
    peso = _HONOR_PESO_RE.search(testo)
    spessore = _HONOR_SPESSORE_RE.search(testo)
    camera = _HONOR_CAMERA_RE.search(testo)
    risoluzione = _HONOR_RISOLUZIONE_RE.search(testo)
    hz = _HONOR_HZ_RE.search(testo)
    image = _HONOR_OG_IMAGE_RE.search(pagina or "")

    display_parts = []
    if risoluzione:
        display_parts.append(f"{risoluzione.group(1)} × {risoluzione.group(2)} px")
    if hz:
        display_parts.append(f"{hz.group(1)} Hz")
    sezioni = {"Specifiche ufficiali HONOR": {
        key: value for key, value in {
            "Batteria": f"{batteria.group(1)} mAh" if batteria else None,
            "Ricarica": f"{ricarica.group(1)} W" if ricarica else None,
            "Fotocamera principale": f"{camera.group(1)} MP" if camera else None,
            "Peso": f"{peso.group(1)} g" if peso else None,
            "Spessore": f"{spessore.group(1)} mm" if spessore else None,
            "Display": " · ".join(display_parts) or None,
            "Pagina prodotto": url,
        }.items() if value
    }}
    if len(sezioni["Specifiche ufficiali HONOR"]) <= 1:
        return None
    return Scheda(
        nome=nome,
        marca=C.HUAWEI,
        foto=html.unescape(image.group(1)) if image else None,
        display=" · ".join(display_parts) or None,
        batteria=f"{batteria.group(1)} mAh" if batteria else None,
        ricarica=f"{ricarica.group(1)} W cablata" if ricarica else None,
        camera_post=f"{camera.group(1)} MP" if camera else None,
        peso=f"{peso.group(1)} g" if peso else None,
        dimensioni=f"spessore {spessore.group(1)} mm" if spessore else None,
        sezioni_json=_ripiega_sezioni(sezioni),
        fonte=FONTE_HONOR_LABEL,
    )


def _ripiego_honor_ufficiale(*indizi: str | None, marca: str | None = None) -> Scheda | None:
    """Scheda leggera dalla pagina prodotto italiana per qualsiasi HONOR.

    È un fallback per modello, non un catalogo: entra dopo le fonti locali e
    versus e conserva al massimo 32 piccole schede. Così i nuovi HONOR non
    producono una card vuota solo perché il mirror GSMArena non li include.
    """
    marca_bassa = (marca or "").lower()
    candidati = [str(indizio).strip() for indizio in indizi
                 if indizio and "honor" in str(indizio).lower()]
    if not candidati and "honor" not in marca_bassa:
        return None
    if not candidati:
        return None
    nome = next((c for c in candidati if _slug_honor(c)), None)
    slug = _slug_honor(nome or "")
    if not slug or requests is None:
        return None

    ora = time.monotonic()
    with _honor_specs_lock:
        cached = _honor_specs_cache.get(slug)
        if cached and ora - cached[0] < _HONOR_SPECS_TTL:
            return cached[1]

    url = _HONOR_PRODUCT_URL.format(slug=slug)
    try:
        response = requests.get(url, headers={"User-Agent": C.USER_AGENT},
                                timeout=C.SEARCH_HTTP_TIMEOUT)
    except Exception:
        return None
    scheda = None
    if getattr(response, "status_code", 0) == 200:
        scheda = _scheda_honor_da_html(nome, getattr(response, "text", "") or "", url)
    with _honor_specs_lock:
        if len(_honor_specs_cache) >= _HONOR_SPECS_CACHE_LIMIT:
            _honor_specs_cache.pop(next(iter(_honor_specs_cache)))
        _honor_specs_cache[slug] = (ora, scheda)
    return scheda


def _ripiego_esterno(*indizi: str | None, marca: str | None = None) -> Scheda | None:
    """La scheda di un modello fuori dal mirror, da versus o HONOR ufficiale.

    Il limite n. 1 dichiarato in testa a questo file — «le marche coperte
    sono dieci» — era vero e resta vero per QUESTA fonte, ma non doveva
    restare vero per il progetto: sono le due marche che il tracker segue
    con una fonte ufficiale dedicata (le pagine AER di HONOR e realme) a
    non avere una scheda tecnica, cioè si sapeva a che Android sta un
    telefono senza sapere che telefono è. Vedi `core/versus.py`.

    Sta DOPO il catalogo e non prima: il mirror GSMArena è indicizzato per
    codice modello e distingue le varianti regionali, versus.com no. Se
    versus non conosce un HONOR, si prova infine la sua pagina italiana
    ufficiale — sempre per un solo modello, mai come catalogo bulk.

    ## Il bug reale trovato dall'utente: «RMX3933» senza scheda, «realme
    Note 60» con la scheda — stesso telefono

    `versus.marca_scoperta` guarda **solo la prima parola** del testo: le
    accetta «realme Note 60» e rifiuta sia «RMX3933» (un codice, nessuna
    parola di marca) sia «Note 60s» — che è il nome CANONICO scelto da
    `modelcodes.nome_canonico` per quello stesso codice, perché fra i nomi
    commerciali veri di RMX3933 (C61, Note 60, Note 60s, NARZO N61) sceglie
    il più corto, e nessuno di questi porta «realme» in testa. Risultato:
    cercando per codice, o per uno qualsiasi dei nomi brevi, la scheda
    spariva; cercando col nome completo con la marca, appariva. Due forme
    dello stesso identico telefono con due risposte diverse — la stessa
    famiglia di incoerenza che questo progetto ha già dovuto correggere
    altrove (vedi FONTI.md).

    **Non si può indovinare la marca da un nome corto**: «C61» da solo non
    dice se è realme o un prodotto di un'altra marca con lo stesso nome. Ma
    chi chiama questa funzione la marca spesso la sa già — dal catalogo AER
    (`aer_catalog.lookup(codice).get("brand_aer")`), che è una fonte
    ufficiale, non un'induzione dal testo. Il parametro `marca`, quando
    c'è, si usa SOLO al secondo giro, dopo che il testo da solo non ha
    prodotto niente: prima si tenta quello che il testo dice da sé (più
    affidabile, perché non dipende da chi chiama), poi si prova a
    costruire il nome con la marca esplicita (`versus.con_marca`) prima di
    arrendersi.
    """
    if not RIPIEGO_ESTERNO:
        return None
    try:
        from . import versus
    except ImportError:  # pragma: no cover
        return None
    testi = [str(t).strip() for t in indizi if t and str(t).strip()]
    if not testi:
        return None

    marca_nota = versus.marca_scoperta(marca) if marca else None

    for testo in testi:
        trovata = versus.marca_scoperta(testo)
        if not trovata:
            continue
        riga = versus.scheda_grezza(testo, _MARCHE.get(trovata.lower(), C.OTHER))
        if riga:
            return _a_scheda(riga)

    if not marca_nota:
        return None
    for testo in testi:
        completo = versus.con_marca(testo, marca_nota)
        riga = versus.scheda_grezza(completo, _MARCHE.get(marca_nota.lower(), C.OTHER))
        if riga:
            return _a_scheda(riga)

    # Un codice modello è più preciso del nome, ma versus indicizza solo
    # nomi. Solo DOPO avere provato gli indizi ricevuti, si aggiungono i nomi
    # associati a QUEL codice nel dataset: RMX2202 -> «realme GT 5G» è la
    # stessa identità, non una ricerca per somiglianza. Metterli in fondo
    # preserva la precedenza del nome scelto dalla fonte chiamante quando
    # questo è già risolvibile.
    try:
        from . import modelcodes
        alias_completi = []
        for codice in testi:
            for alias in modelcodes.resolve(codice):
                if versus.marca_scoperta(alias) != marca_nota:
                    continue
                completo = versus.con_marca(alias, marca_nota)
                if completo not in testi and completo not in alias_completi:
                    alias_completi.append(completo)
        for completo in alias_completi:
            riga = versus.scheda_grezza(completo, _MARCHE.get(marca_nota.lower(), C.OTHER))
            if riga:
                return _a_scheda(riga)
    except Exception:  # il ripiego non deve mai fermare una ricerca
        pass
    return _ripiego_honor_ufficiale(*testi, marca=marca)


def cerca(*indizi: str | None, marca: str | None = None) -> Scheda | None:
    """La scheda del dispositivo, provando ogni traccia disponibile.

    L'ordine non è casuale: prima i **codici modello** trovati in una
    qualsiasi delle stringhe (il codice identifica un telefono preciso),
    poi i nomi commerciali (che identificano una famiglia). Chi cerca
    digita una cosa sola, e quella arriva qui indifferentemente come nome
    o come codice: si prova in tutti e due i modi invece di pretendere che
    l'utente sappia quale campo sta riempiendo.

    `marca`, quando c'è, non serve al catalogo GSMArena o a `per_nome`
    (indicizzati per codice/nome, non per marca): serve solo al ripiego
    versus.com, come marca esplicita quando il nome canonico non la porta
    in testa (vedi il docstring di `_ripiego_esterno`).
    """
    from . import soc

    testi = [t for t in indizi if t and str(t).strip()]
    if not testi:
        return None

    visti: list[str] = []
    for testo in testi:
        for codice in soc.codici_da_testo(str(testo)):
            if codice not in visti:
                visti.append(codice)
        diretto = str(testo).strip().upper()
        if diretto not in visti:
            visti.append(diretto)

    for codice in visti:
        curata = _curata_per_codice(codice)
        if curata and _marca_compatibile(curata, marca):
            return curata
    for testo in testi:
        curata = _curata_per_nome(str(testo))
        if curata:
            return curata

    carica()
    for codice in visti:
        riga = _per_codice.get(codice.split("/")[0])
        if riga:
            trovata = _a_scheda(riga)
            if _marca_compatibile(trovata, marca):
                return trovata

    for testo in testi:
        trovata = per_nome(str(testo), marca=marca)
        if trovata:
            return trovata

    # Solo qui, quando il catalogo ha già detto di no su tutte le tracce.
    return _ripiego_esterno(*testi, marca=marca)
