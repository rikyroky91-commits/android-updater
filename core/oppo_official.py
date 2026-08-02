"""Fonte ufficiale Oppo: archivio firmware di support.oppo.com.

COSA RISOLVE. Fino a oggi Oppo era l'unico brand per cui il tracker sapeva
dire solo la **versione di fabbrica** (dedotta da GSMArena). La pagina
ufficiale

    https://support.oppo.com/it/software-update/software-download/?m=Find%20X2

mostra invece la versione firmware davvero rilasciata, ma il server
restituisce un guscio vuoto: nell'HTML grezzo il titolo è letteralmente
`OPPO XX Download Firmware` — `XX` è un segnaposto che il browser
sostituisce dopo il caricamento.

L'INDIRIZZO INTERNO. Il codice della pagina
(`software-detail.min.js`) chiama, dopo il caricamento:

    POST {SOWAPIPATH}/softwareUpgrade/info
    Content-Type: application/json
    {"region": "it", "langId": "1040", "seriesLangId": "1040",
     "model": "Find X2"}

dove `SOWAPIPATH` è dichiarato nell'HTML della pagina stessa e vale
`https://par-sow-cms.oppo.com/oppo-server` per l'Europa,
`https://sgp-sow-cms.oppo.com/oppo-server` per l'Asia-Pacifico.
L'elenco dei modelli disponibili viene dalla stessa API:

    POST {SOWAPIPATH}/softwareUpgrade/model
    {"region": "in", "langId": "1033", "seriesLangId": "1033"}

Verificato il 2026-08-02: **nessuna firma calcolata dal JavaScript** e
**nessun User-Agent particolare** — le due condizioni che il documento di
passaggio consegne indicava come motivo per fermarsi. Le richieste qui
sotto si identificano onestamente con `C.USER_AGENT`, esattamente come
tutte le altre fonti del progetto.

IL LIMITE, DA DIRE SUBITO. Questo non è un elenco di «tutti gli Oppo»: è
l'archivio dei **firmware completi scaricabili**, che Oppo pubblica solo
per i modelli fino al 2021-2022 circa. L'unione di tutte le regioni dà
**~94 modelli**, il più recente dei quali è un Reno4 / A54. Per un Find X9
o un A6x l'API risponde `code=1` con `data` vuoto: nessun errore, nessun
dato. Per quei modelli il ripiego resta GSMArena (versione di fabbrica),
esattamente come prima.

Cosa si guadagna, quindi: per ~94 modelli Oppo si passa da «versione di
fabbrica dedotta» a **versione firmware ufficiale, con data di rilascio e
livello di patch di sicurezza reali**. Per gli altri non cambia nulla, e —
punto importante — non si peggiora nulla: una risposta vuota non è un
errore e non deve interrompere la ricerca sulle altre fonti.

SCELTA DELLA LINGUA. Si interroga in **inglese** (`langId=1033`) anche
dalla versione italiana del sito: il changelog inglese scrive
«Added the September 2020 Android security patch», che
`extract.extract_patch_level()` riconosce, mentre la resa italiana
(«Aggiunte le patch di sicurezza Android di settembre 2020») non rientra
nei pattern esistenti. Meglio una fonte in inglese che un dato perso.
"""
from __future__ import annotations

import html
import json
import re
import threading
import urllib.error
import urllib.request

from . import config as C

# I due soli host esistenti: l'API è regionalizzata, e una regione servita
# da un host non risponde sull'altro.
HOST_EU = "https://par-sow-cms.oppo.com/oppo-server"
HOST_APAC = "https://sgp-sow-cms.oppo.com/oppo-server"

# Regioni da cui costruire il catalogo, in ordine di resa. Non sono tutte
# quelle esistenti: sono il sottoinsieme MINIMO che copre 92 dei 94 modelli
# noti (India da sola ne dà 64). Interrogarle tutte costerebbe una ventina
# di richieste per guadagnare due modelli.
CATALOG_REGIONS: list[tuple[str, str]] = [
    (HOST_APAC, "in"),
    (HOST_APAC, "tw"),
    (HOST_APAC, "ae"),
    (HOST_EU, "pl"),
    (HOST_APAC, "au"),
]

# Inglese: vedi la nota sulla scelta della lingua nel docstring del modulo.
LANG_ID = "1033"

SOURCE_KEY = "oppo_support"
SOURCE_LABEL = "Oppo — archivio firmware ufficiale"

_lock = threading.Lock()
# nome normalizzato -> (host, region, machineModel esatto)
_catalog: dict[str, tuple[str, str, str]] | None = None
_status = "non ancora caricato"


def status() -> str:
    return _status


def reset_cache() -> None:
    """Usato dai test e dal pulsante «Ricarica ora» della Diagnostica."""
    global _catalog, _status
    with _lock:
        _catalog = None
        _status = "non ancora caricato"


# ----------------------------------------------------------------------
# Rete
# ----------------------------------------------------------------------
def _post(url: str, payload: dict, timeout: int | None = None) -> dict:
    """POST JSON. Solleva su errore: chi chiama decide cosa farne."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": C.USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout or C.HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


# ----------------------------------------------------------------------
# Confronto tollerante dei nomi
# ----------------------------------------------------------------------
# Il nome che l'utente scrive non coincide quasi mai con `machineModel`:
# «OPPO Reno 4 Pro» contro «Reno4 Pro», «a54» contro «A54». Si confronta
# quindi su una forma ridotta a soli caratteri alfanumerici, che collassa
# anche lo spazio fra sigla e cifre — lo stesso criterio già adottato per
# realme (vedi la voce 6 dello storico di DATA_LOGIC_VERSION).
_PARENTESI = re.compile(r"\([^)]*\)")


def normalize(name: str) -> str:
    text = _PARENTESI.sub(" ", str(name or ""))
    text = re.sub(r"^\s*oppo\s+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


# ----------------------------------------------------------------------
# Catalogo
# ----------------------------------------------------------------------
def _load_catalog() -> dict[str, tuple[str, str, str]]:
    global _catalog, _status
    with _lock:
        if _catalog is not None:
            return _catalog
        catalogo: dict[str, tuple[str, str, str]] = {}
        errori: list[str] = []
        for host, region in CATALOG_REGIONS:
            try:
                risposta = _post(
                    f"{host}/softwareUpgrade/model",
                    {"region": region, "langId": LANG_ID, "seriesLangId": LANG_ID},
                )
            except Exception as exc:
                errori.append(f"{region}: {exc}")
                continue
            if str(risposta.get("code")) != "1":
                errori.append(f"{region}: code={risposta.get('code')}")
                continue
            for serie in risposta.get("data") or []:
                for modello in serie.get("models") or []:
                    nome = str(modello.get("machineModel") or "").strip()
                    if not nome:
                        continue
                    # La prima regione che dichiara un modello vince: le
                    # regioni sono ordinate per resa, quindi la prima è
                    # anche quella con più probabilità di avere il dato.
                    catalogo.setdefault(normalize(nome), (host, region, nome))
                    alias = str(modello.get("modelMultilingual") or "").strip()
                    if alias:
                        catalogo.setdefault(normalize(alias), (host, region, nome))
        _catalog = catalogo
        if catalogo:
            _status = f"{len(catalogo)} nomi indicizzati"
            if errori:
                _status += f" ({len(errori)} regioni non raggiunte)"
        else:
            _status = "catalogo non caricato: " + "; ".join(errori[:2])
        return _catalog


def known_models() -> list[str]:
    """Nomi commerciali coperti dall'archivio, per il catalogo sfogliabile."""
    return sorted({voce[2] for voce in _load_catalog().values()})


# ----------------------------------------------------------------------
# Interrogazione di un modello
# ----------------------------------------------------------------------
_TAG = re.compile(r"<[^>]+>")


def changelog_text(html_content: str) -> str:
    """Changelog HTML → testo piano, su cui far girare gli estrattori.

    L'HTML arriva con entità doppiamente codificate (`&amp;middot;`), e i
    tag vanno sostituiti da uno SPAZIO, non rimossi: `<p>[Security]</p><p>·
    Added…` diventerebbe altrimenti `[Security]· Added…`, attaccando
    parole che i pattern cercano separate.
    """
    testo = _TAG.sub(" ", str(html_content or ""))
    testo = html.unescape(html.unescape(testo))
    return re.sub(r"\s+", " ", testo).strip()


def parse_info(payload: dict, model_name: str) -> dict | None:
    """Risposta di `/softwareUpgrade/info` → dizionario per il tracker.

    Separata dalla rete apposta, così i test possono lavorare sulla
    risposta REALE registrata invece che su una finzione (è la lezione
    imparata con la fonte realme: una regex costruita su una resa
    inventata non funziona sui dati veri).
    """
    if str(payload.get("code")) != "1":
        return None
    voci = payload.get("data") or []
    if not voci:
        # Modello moderno, fuori dall'archivio dei firmware scaricabili.
        # NON è un errore: è l'assenza di dato, e va detta come tale.
        return None

    # L'API restituisce le versioni dalla più recente alla più vecchia.
    corrente = voci[0]
    versione = str(corrente.get("softwareVersion") or "").strip()
    if not versione:
        return None

    testo = changelog_text(corrente.get("content"))
    data = str(corrente.get("releaseDate") or "").strip()

    grezzo = str(corrente.get("machineModel") or model_name).strip()
    return {
        "device_model": nome_pulito(grezzo, str(corrente.get("prefix") or "")),
        "machine_model": grezzo,      # com'è scritto nell'API, per ripetere la chiamata
        "build": versione,
        # Volutamente NIENTE versione Android o ColorOS: l'API non le
        # dichiara. Il pezzo `_11_` di `CPH2023_11_A.42` è un codice di
        # canale, non «Android 11» — dedurlo sarebbe esattamente il tipo
        # di ipotesi non verificata che è costata giorni a questo progetto.
        "published": data or None,
        "changelog": testo,
        "size_mb": _intero(corrente.get("fileSize")),
        "link": str(corrente.get("versionPath") or "").strip() or None,
        "versioni_archiviate": len(voci),
        "source": SOURCE_KEY,
        "source_label": SOURCE_LABEL,
        "source_trust": C.TRUST_STRUCTURED,
        "brand": C.OPPO,
    }


# L'API scrive a volte il codice tecnico dentro il nome: «A73(CPH2095)».
# Quel codice va tolto — un nome decorato diventa un DISPOSITIVO DIVERSO da
# «OPPO A73» delle altre fonti, e come termine di ricerca nel catalogo non
# trova nulla (è l'errore già commesso con «Oppo A6X (cph2819)»).
# Si tolgono solo le parentesi che contengono un codice: «A83 (2G + 16G)»
# distingue davvero due prodotti e va lasciata dov'è.
_CODICE_IN_PARENTESI = re.compile(r"\s*\((?:CPH|RMX|PC[A-Z]?)\d{3,5}\)\s*", re.IGNORECASE)


def nome_pulito(machine_model: str, prefix: str = "") -> str:
    """`("A73(CPH2095)", "OPPO")` → `"OPPO A73"`.

    Il prefisso conta per la COERENZA fra fonti: l'elenco AER e GSMArena
    scrivono «OPPO A6x», e un nome senza marca produrrebbe un `device_key`
    diverso per lo stesso telefono — cioè due dispositivi distinti in
    archivio, ciascuno con metà della storia.
    """
    nome = _CODICE_IN_PARENTESI.sub(" ", str(machine_model or "")).strip()
    marca = str(prefix or "").strip()
    if not nome or not marca:
        return nome
    if nome.lower().startswith(marca.lower()):
        return nome
    return f"{marca} {nome}"


def _intero(valore) -> int | None:
    try:
        return int(str(valore).strip())
    except (TypeError, ValueError):
        return None


def fetch_oppo_official(model: str, timeout: int | None = None) -> tuple[dict | None, str | None]:
    """Versione firmware ufficiale di un modello Oppo.

    Restituisce `(dato, errore)`:
      * `(dict, None)`  — trovato;
      * `(None, None)`  — modello non presente nell'archivio (caso normale
                          per tutti i modelli dal 2022 in poi);
      * `(None, "…")`   — la fonte non ha risposto.

    La distinzione fra le ultime due è la parte importante: un modello
    assente non deve far comparire una fonte rossa in Diagnostica, e non
    deve interrompere la ricerca sulle altre fonti.
    """
    nome = str(model or "").strip()
    if not nome:
        return None, None

    try:
        catalogo = _load_catalog()
    except Exception as exc:  # pragma: no cover - percorso difensivo
        return None, f"catalogo non raggiungibile: {exc}"
    if not catalogo:
        return None, _status

    voce = catalogo.get(normalize(nome))
    if voce is None:
        return None, None

    host, region, machine_model = voce
    try:
        risposta = _post(
            f"{host}/softwareUpgrade/info",
            {
                "region": region,
                "langId": LANG_ID,
                "seriesLangId": LANG_ID,
                "model": machine_model,
            },
            timeout=timeout,
        )
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return None, f"richiesta non riuscita: {exc}"

    return parse_info(risposta, machine_model), None
