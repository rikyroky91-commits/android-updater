"""Lettura del tracker ARB OnePlus/Oppo (`Bartixxx32/OnePlus-antirollchecker`).

**Perché esiste.** È l'unica fonte trovata che pubblica, in modo
automatizzato e per regione, il numero di build corrente di OnePlus e di
una parte degli OPPO. Rispetto al canale Telegram (`telegram_tracker`)
il salto di qualità è netto: lì si legge la prosa di una persona, qui si
legge una tabella generata da uno script che scarica i firmware veri e ne
estrae i dati. Copre anche il caso «stessa build, codice diverso per
regione» (OnePlus 13 = CPH2653 in Europa, CPH2649 in India), che è
esattamente la distinzione che serve a un QA con un parco misto.

**Cosa NON è.** Non è una fonte ufficiale: è un progetto community nato
per un altro scopo — avvisare chi fa flashing del rischio di brick da
anti-rollback. Il numero di build è per lui un sottoprodotto. Trust
`CURATED`, mai `STRUCTURED`.

**Zero rete, come `telegram_tracker`.** Questo modulo riceve testo già
scaricato e restituisce dati. Chi scarica è `sources.py`.

## Perché si legge il README e non i JSON

Il repository ha una cartella `data/`, che sarebbe la scelta ovvia. Ma
GitHub blocca l'esplorazione automatica delle cartelle, quindi il
contenuto esatto non è stato verificato e costruire un parser su una
struttura non vista sarebbe indovinare. Il README invece è **generato da
`generate_readme.py`** a ogni aggiornamento: è a tutti gli effetti un
formato macchina, solo scritto in Markdown, ed è raggiungibile come file
grezzo. Se un domani si scoprisse un JSON stabile in `data/`, migrare è
un lavoro da mezz'ora — il resto del modulo non cambia.

## La distinzione che tiene in piedi il parser

Il README contiene DUE tipi di tabella, e confonderli sarebbe grave:

    Stato corrente:  | Region | Model | Firmware Version | ARB Index | ...
    Storico:         | Firmware Version | ARB | OEM Version | Last Seen | ...

Le tabelle storiche elencano build **vecchie**. Prenderle per correnti
significherebbe dire a chi fa QA che un telefono è fermo a una versione
che ha superato mesi fa: l'errore opposto a quello di Honor, ma con lo
stesso esito — un dato falso su un dispositivo reale.

Il discriminante usato è la presenza della colonna `Region`, che c'è solo
nelle tabelle di stato corrente. È un criterio strutturale, non una
posizione, quindi regge se le colonne vengono riordinate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

REPO = "Bartixxx32/OnePlus-antirollchecker"
URL_README = f"https://raw.githubusercontent.com/{REPO}/main/README.md"
URL_PAGINA = f"https://github.com/{REPO}"

# Intestazione di sezione: «### OnePlus 13», «### Oppo Reno10 Pro».
_RE_TITOLO = re.compile(r"^#{2,4}\s+(?P<nome>[^\n#]+?)\s*$", re.M)

# Una build completa: CPH2649_16.0.7.201(EX01), MT2111_14.0.0.2702(EX01),
# PJZ110_16.0.7.201(CN01), e le vecchie CPH2611_11_A.65 / GM1905_11_H.41.
_RE_BUILD = re.compile(
    r"\b(?P<codice>[A-Z]{2,4}\d{3,4})"
    r"_(?P<versione>\d+(?:\.\d+){1,3}|\d+_[A-Z]\.\d+)"
    r"(?:\((?P<canale>[A-Z0-9]{2,6})\))?"
)

# Codice modello di colonna: CPH2653, CPH2525EEA, PJZ110.
_RE_CODICE = re.compile(r"^(?P<codice>[A-Z]{2,4}\d{3,4})(?P<suffisso>[A-Z]{2,4})?$")

_RE_DATA = re.compile(r"\b(?P<data>\d{4}-\d{2}-\d{2})\b")
_RE_TAG_HTML = re.compile(r"<[^>]+>")

_INTESTAZIONI_IGNORATE = {
    "current status", "on-demand arb checker", "oos downloader api",
    "credits", "android app", "community & support", "how to use",
    "oneplus arb checker bot", "support the project",
}


@dataclass
class Rilascio:
    """Una build corrente per una regione, letta dal tracker."""
    device_name: str
    region: str
    model_code: str
    build: str
    skin_version: str | None = None
    canale_build: str | None = None
    last_checked: str | None = None     # ISO, quando il tracker l'ha vista
    arb: str | None = None
    arb_nota: str | None = None

    @property
    def link(self) -> str:
        return URL_PAGINA


def _pulisci(cella: str) -> str:
    """Toglie markup e decorazioni da una cella di tabella."""
    testo = _RE_TAG_HTML.sub(" ", cella or "")
    testo = testo.replace("**", "").replace("`", "")
    testo = re.sub(r"\s+", " ", testo)
    return testo.strip()


def _celle(riga: str) -> list[str]:
    grezza = riga.strip()
    if not grezza.startswith("|"):
        return []
    parti = grezza.strip("|").split("|")
    return [_pulisci(p) for p in parti]


def _e_separatore(riga: str) -> bool:
    return bool(re.match(r"^\s*\|[\s:\-|]+\|\s*$", riga))


def _versione_skin(versione: str) -> str | None:
    """`16.0.7.201` → `16.0.7`. Le build vecchie non hanno una versione di
    skin leggibile e restituiscono None invece di un numero inventato."""
    pezzi = versione.split(".")
    if len(pezzi) >= 3 and all(p.isdigit() for p in pezzi[:3]):
        return ".".join(pezzi[:3])
    return None


def _nota_arb(cella_safe: str, arb: str | None) -> str | None:
    testo = (cella_safe or "").lower()
    if "undetectable" in testo:
        return "indice ARB non rilevabile"
    if "protected" in testo or (arb or "") not in ("0", "", None):
        return "ARB attivo: downgrade bloccato dal bootloader"
    return None


def _tabelle(testo: str):
    """Blocchi `(titolo_sezione, intestazione, righe)` del documento."""
    titoli = list(_RE_TITOLO.finditer(testo or ""))
    confini = [(m.start(), m.group("nome").strip()) for m in titoli]

    def titolo_per(posizione: int) -> str:
        corrente = ""
        for inizio, nome in confini:
            if inizio <= posizione:
                corrente = nome
            else:
                break
        return corrente

    righe = (testo or "").splitlines()
    indice = 0
    offset = 0
    posizioni = []
    for riga in righe:
        posizioni.append(offset)
        offset += len(riga) + 1

    while indice < len(righe):
        intestazione = _celle(righe[indice])
        if (intestazione and indice + 1 < len(righe)
                and _e_separatore(righe[indice + 1])):
            corpo = []
            cursore = indice + 2
            while cursore < len(righe) and righe[cursore].strip().startswith("|"):
                celle = _celle(righe[cursore])
                if celle:
                    corpo.append(celle)
                cursore += 1
            yield titolo_per(posizioni[indice]), intestazione, corpo
            indice = cursore
        else:
            indice += 1


def _indice_colonna(intestazione: list[str], *nomi: str) -> int | None:
    minuscole = [c.lower() for c in intestazione]
    for nome in nomi:
        if nome in minuscole:
            return minuscole.index(nome)
    return None


def _nome_pulito(titolo: str) -> str:
    """«Oppo Reno10 Pro» → «OPPO Reno10 Pro».

    Il tracker scrive «Oppo»; le fonti ufficiali e il catalogo AER usati
    dal resto del progetto scrivono «OPPO». Allinearsi evita di creare in
    archivio due dispositivi diversi per lo stesso telefono.
    """
    nome = re.sub(r"\s+", " ", titolo or "").strip()
    return re.sub(r"^Oppo\b", "OPPO", nome)


def rilasci_da_readme(testo: str) -> tuple[list[Rilascio], str | None]:
    """Build correnti per regione, dal README del tracker.

    Ritorna `(rilasci, errore)`. Come per il canale Telegram, l'assenza
    totale di tabelle di stato è un ERRORE e non un silenzio: se il
    formato del README cambiasse, la fonte deve diventare rossa in
    Diagnostica invece di restare verde e vuota.
    """
    rilasci: list[Rilascio] = []
    tabelle_di_stato = 0

    for titolo, intestazione, corpo in _tabelle(testo):
        i_regione = _indice_colonna(intestazione, "region")
        if i_regione is None:
            # Tabella storica: elenca build SUPERATE. Ignorarla non è
            # una semplificazione, è il punto — vedi il docstring.
            continue
        if not titolo or titolo.strip().lower() in _INTESTAZIONI_IGNORATE:
            continue

        i_modello = _indice_colonna(intestazione, "model")
        i_build = _indice_colonna(intestazione, "firmware version", "firmware")
        i_arb = _indice_colonna(intestazione, "arb index", "arb")
        i_data = _indice_colonna(intestazione, "last checked", "last seen")
        i_safe = _indice_colonna(intestazione, "safe")
        if i_modello is None or i_build is None:
            continue

        tabelle_di_stato += 1
        nome = _nome_pulito(titolo)

        for celle in corpo:
            if max(i_regione, i_modello, i_build) >= len(celle):
                continue
            match = _RE_BUILD.search(celle[i_build])
            if not match:
                continue

            codice_colonna = _RE_CODICE.match(celle[i_modello].strip())
            # Il codice della COLONNA è quello commerciale del mercato
            # (CPH2525EEA); quello dentro la build è il codice base
            # (CPH2525). Si tiene il primo per la ricerca e si ricade sul
            # secondo quando la colonna non è un codice riconoscibile —
            # succede su Find N5, dove la riga Cina dichiara PKV110 ma la
            # build è PKH110.
            codice = (codice_colonna.group(0) if codice_colonna
                      else match.group("codice"))

            arb = celle[i_arb].strip() if i_arb is not None and i_arb < len(celle) else None
            safe = celle[i_safe] if i_safe is not None and i_safe < len(celle) else ""
            data = None
            if i_data is not None and i_data < len(celle):
                trovata = _RE_DATA.search(celle[i_data])
                data = trovata.group("data") if trovata else None

            rilasci.append(Rilascio(
                device_name=nome,
                region=celle[i_regione].strip(),
                model_code=codice,
                build=match.group(0),
                skin_version=_versione_skin(match.group("versione")),
                canale_build=match.group("canale"),
                last_checked=data,
                arb=arb if arb not in ("", None) else None,
                arb_nota=_nota_arb(safe, arb),
            ))

    if tabelle_di_stato == 0:
        return [], ("nessuna tabella di stato trovata nel README del tracker ARB: "
                    "il formato potrebbe essere cambiato")
    return rilasci, None


def copertura(rilasci: list[Rilascio]) -> dict:
    """Cosa copre davvero la fonte — il numero che dirà quando spegnerla."""
    return {
        "rilasci": len(rilasci),
        "dispositivi": len({r.device_name for r in rilasci}),
        "codici_distinti": len({r.model_code for r in rilasci}),
        "regioni": sorted({r.region for r in rilasci if r.region}),
        "ultima_verifica": max((r.last_checked for r in rilasci if r.last_checked),
                               default=None),
    }
