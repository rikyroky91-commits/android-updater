"""Lettura del canale Telegram che pubblica le build OxygenOS / ColorOS.

**Perché esiste.** Per Oppo, OnePlus e realme moderni non c'è una fonte
ufficiale interrogabile: `FONTI.md` elenca le prove (403, 404, domini
inesistenti, portali di bug bounty senza versione per modello), e
l'archivio ufficiale Oppo (`core/oppo_official.py`) si ferma ai ~94
modelli fino al 2021-22. Questo canale è, alla data della misura,
**l'unico posto pubblico dove compaiono numeri di build reali** per i
modelli recenti di quelle tre marche.

**Cosa NON è.** Non è una fonte ufficiale ed è gestito da una persona:
il trust è `CURATED`, mai `STRUCTURED`. Non deve poter sovrascrivere un
dato ufficiale, e nell'interfaccia va etichettato per quello che è.

**Zero rete, di proposito.** Questo modulo riceve HTML già scaricato e
restituisce dati: non importa `requests`, non apre socket. È la lezione
n. 12 del passaggio di consegne applicata in partenza invece che corretta
dopo — chi scarica è `sources.py`, che ha già il suo aggancio unico e
sostituibile nei test.

## I tre formati veri, e il perché di un parser tollerante

Il canale non ha un formato solo. Dai messaggi registrati (vedi
`tests/fixtures/telegram_oplus_messaggi.json`) se ne contano tre vivi
contemporaneamente:

    A) Version : CPH2613_16.0.3.500        ← nessun nome di modello!
       OxygenOS Version: 16.0.3
       Android Version: 16
       Security Build : 1 February 2026

    B) 📲 OnePlus 10T
       Version :CPH2413_15.0.0.1603(EX01)
       📥 Android Version: 15
       🔐 1 February 2026

    C) 📱Device : OPPO RENO 15 Pro Mini
       {CPH2813}
       🗃️ ColorOS 16.0.3 • A16
       📤 ColorOS Version
       v16.0.3.502(EX01)
       🔑 1 February 2026

Il formato A è il più frequente e **non contiene il nome del telefono**:
c'è solo il codice modello dentro la build. Non è un problema, è anzi il
punto in cui questo progetto è già attrezzato — `modelcodes` e il
catalogo AER traducono `CPH2613` in un nome commerciale. Il canale porta
la build, l'app ci mette l'identità.

## La trappola, che è la stessa di Honor

Una parte consistente dei post è una **previsione**, non un rilascio:
«Upcoming ... Software Updates», con tanto di build plausibile, seguita da
«these values are subject to change as the verification process is still
ongoing». Prendere quella per versione attuale sarebbe l'identico errore
già pagato con la pagina AER di Honor, dove la versione *promessa* era
stata letta come *spedita*.

Qui il rifiuto è esplicito e testato: un messaggio che contiene un
marcatore di preliminarità viene scartato **anche se contiene una build
perfettamente formata**. Meglio nessun dato che un dato che si smentisce
da solo il mese dopo.
"""
from __future__ import annotations

import html as html_mod
import re
from dataclasses import dataclass

# Canale misurato il 2026-08-03. `/s/` è la vista web pubblica: non
# richiede account, non richiede l'API di Telegram, non richiede token.
CANALE = "oxygenos14update"
URL_CANALE = f"https://t.me/s/{CANALE}"


def url_messaggio(msg_id: str) -> str:
    return f"https://t.me/{CANALE}/{msg_id}"


# ----------------------------------------------------------------------
# Marcatori di preliminarità — il filtro che evita l'errore Honor
# ----------------------------------------------------------------------
# Ogni voce è stata vista in un post reale. Sono volutamente specifici:
# una parola generica come "test" comparirebbe anche in un changelog
# legittimo e farebbe sparire rilasci veri.
MARCATORI_PRELIMINARI = (
    "upcoming",
    "important notice",
    "subject to change",
    "verification process is still ongoing",
    "preliminary",
    "yet to receive",
    "early version detected",
    "internal testing",
    "started testing",
    "testing is going",
    "not the final version",
    "can't confirm",
    "cant confirm",
    "might be possible",
    "version just found",
)


def e_preliminare(testo: str) -> bool:
    """True se il messaggio annuncia una versione **prevista**, non uscita.

    Volutamente prudente: nel dubbio si scarta. Un rilascio perso ricompare
    al giro dopo (il canale ripubblica il post confermato); un rilascio
    inventato invece resta in archivio e sporca il confronto con la
    baseline di test, che è il danno peggiore.
    """
    minuscolo = (testo or "").lower()
    return any(marcatore in minuscolo for marcatore in MARCATORI_PRELIMINARI)


# ----------------------------------------------------------------------
# Riconoscimento dei pezzi
# ----------------------------------------------------------------------
# Build completa, con il codice modello incorporato:
#   CPH2413_15.0.0.1603(EX01) · OPD2481_16.0.3.500 · NE2211_16.0.3.510
#   MT2111_14.0.0.2401(EX01)  · PJZ110PRE_15.0.0.831(CN01)
# Il codice è 2-4 lettere + 3-4 cifre, con un eventuale suffisso di
# variante (PRE, EU, IN...) attaccato prima del trattino basso.
_RE_BUILD_COMPLETA = re.compile(
    r"\b(?P<codice>[A-Z]{2,4}\d{3,4})(?P<variante>[A-Z]{0,4})"
    r"_(?P<versione>\d+(?:\.\d+){2,3})"
    r"(?:\((?P<regione>[A-Z0-9]{2,6})\))?",
)

# Formato C: il codice sta fra graffe su una riga sua, e la versione è
# separata (`v16.0.3.502(EX01)`).
_RE_CODICE_GRAFFE = re.compile(r"\{\s*([A-Z]{2,4}\d{3,4}[A-Z]{0,4})\s*\}")
_RE_VERSIONE_NUDA = re.compile(
    r"^\s*v?(?P<versione>\d+(?:\.\d+){2,3})(?:\((?P<regione>[A-Z0-9]{2,6})\))?\s*$",
    re.M,
)

# Livello di patch: «1 February 2026», «01 February 2026».
_RE_PATCH = re.compile(
    r"\b(?P<giorno>\d{1,2})\s+(?P<mese>January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+(?P<anno>20\d{2})\b",
    re.I,
)

_MESI = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# Versione di Android: «Android Version: 16», «Android 16», «• A16».
_RE_ANDROID = re.compile(
    r"(?:android(?:\s+version)?\s*[:\s]\s*(?P<a>\d{1,2})\b)|(?:•\s*A(?P<b>\d{1,2})\b)",
    re.I,
)

# Nome del modello, nei due modi in cui il canale lo scrive.
_RE_NOME_DEVICE = re.compile(
    r"^\s*(?:📱|📲)?\s*Device\s*:\s*(?P<nome>[^\n{]+)", re.I | re.M)
_RE_NOME_RIGA = re.compile(
    r"^\s*(?:📱|📲)\s*(?P<nome>(?:OnePlus|OPPO|realme|Oppo|Realme)[^\n]*)$", re.I | re.M)

# Skin: quale interfaccia, e a che versione.
_RE_SKIN = re.compile(
    r"\b(?P<skin>Oxygen\s?OS|ColorOS|Color\s?OS|realme\s?UI)\b"
    r"(?:\s*Version)?\s*[:\s]?\s*(?P<versione>\d+(?:\.\d+){0,3})?",
    re.I,
)

# «OS Version : 15.0», «OS Version 14.0» — la versione della skin quando il
# canale non ripete il nome dell'interfaccia. Il `(?!\S*_)` impedisce di
# agganciare i numeri di una build («Oxygen OS Version MT2111_14.0.0.2401»),
# che sono un'altra cosa e vanno lette dal pattern della build.
_RE_OS_VERSION = re.compile(
    r"\bOS\s+Version\s*[:\s]\s*(?P<versione>\d+(?:\.\d+){0,2})\b(?!\S*_)", re.I)

_RE_REGIONE = re.compile(r"Region\s*:\s*(?P<regione>[A-Za-z ]{2,20})", re.I)

# Parole tutte maiuscole che NON vanno rese in forma «Capitalizzata»:
# sono marchi o sigle e vengono scritte così anche dalle fonti ufficiali.
_SIGLE_DA_LASCIARE = frozenset({"OPPO", "SE", "UI", "XL", "GT", "CE", "NE"})

# Righe decorative del formato C, da non scambiare per contenuto.
_RE_SEPARATORE = re.compile(r"^[\s—\-•·]+$")


@dataclass
class Rilascio:
    """Un aggiornamento **confermato** letto da un messaggio del canale."""
    msg_id: str
    build: str
    model_code: str | None = None
    device_name: str | None = None
    skin: str | None = None
    skin_version: str | None = None
    android_version: int | None = None
    patch_level: str | None = None       # ISO: 2026-02-01
    region: str | None = None
    # Suffisso fra parentesi della build: EX01, CN01, IN01...
    # È il CANALE DI RILASCIO, non la regione geografica, e confonderli
    # produceva dispositivi con «Region: EX01» — un dato che non vuol
    # dire niente. La regione vera si legge solo dalla riga «Region :».
    canale_build: str | None = None
    changelog: str = ""

    @property
    def link(self) -> str:
        return url_messaggio(self.msg_id)


def _normalizza_skin(grezzo: str) -> str:
    testo = re.sub(r"\s+", "", (grezzo or "")).lower()
    if testo.startswith("oxygen"):
        return "OxygenOS"
    if testo.startswith("color"):
        return "ColorOS"
    if testo.startswith("realme"):
        return "realme UI"
    return grezzo.strip()


def _patch_iso(testo: str) -> str | None:
    """Primo livello di patch trovato, in forma ISO.

    Si prende il PRIMO: nei messaggi reali la data della patch sta in
    testa, mentre più in basso il changelog ripete il mese («Integrates
    the February 2026 Android security patch...») senza il giorno.
    """
    match = _RE_PATCH.search(testo or "")
    if not match:
        return None
    mese = _MESI.get(match.group("mese").lower())
    if not mese:
        return None
    giorno = int(match.group("giorno"))
    if not 1 <= giorno <= 31:
        return None
    return f"{match.group('anno')}-{mese:02d}-{giorno:02d}"


def _android_version(testo: str) -> int | None:
    for match in _RE_ANDROID.finditer(testo or ""):
        grezzo = match.group("a") or match.group("b")
        if not grezzo:
            continue
        valore = int(grezzo)
        # Sotto Android 8 non esiste nessun ColorOS/OxygenOS ancora
        # aggiornato, e sopra 30 siamo in un numero di versione della
        # skin letto per sbaglio: fuori da questa finestra si tace
        # invece di affermare una cosa falsa.
        if 8 <= valore <= 30:
            return valore
    return None


def _nome_device(testo: str) -> str | None:
    match = _RE_NOME_DEVICE.search(testo or "")
    if match:
        nome = match.group("nome").strip(" :•—-")
        if nome:
            return _ripulisci_nome(nome)
    match = _RE_NOME_RIGA.search(testo or "")
    if match:
        nome = match.group("nome").strip(" :•—-")
        # La riga del formato B contiene solo il nome; se ci finisce
        # dentro una build vuol dire che è una riga d'elenco di un post
        # multi-device, gestito altrove.
        if nome and not _RE_BUILD_COMPLETA.search(nome):
            return _ripulisci_nome(nome)
    return None


def _ripulisci_nome(nome: str) -> str:
    """«OPPO RENO 15 Pro Mini» → «OPPO Reno 15 Pro Mini».

    Il canale scrive spesso in maiuscolo pieno. Lasciarlo così produce un
    `device_key` diverso da quello delle altre fonti per lo STESSO
    telefono, cioè due dispositivi in archivio ciascuno con metà della
    storia — l'errore già descritto in `INTEGRAZIONE-OPPO.md`.

    **La regola vale solo per le parole di sole lettere.** Un token che
    contiene una cifra è un nome di modello, e lì la maiuscola è
    significativa: «OnePlus 10T» normalizzato ingenuamente diventa
    «OnePlus 10t», che è semplicemente un telefono che non esiste. È lo
    stesso inciampo già visto con «HONOR X8c» in `search_model_live`,
    dove la normalizzazione rovinava un nome già scritto giusto.
    """
    nome = re.sub(r"\s+", " ", nome).strip()
    parole = []
    for parola in nome.split(" "):
        ha_cifre = any(c.isdigit() for c in parola)
        if (parola.isupper() and not ha_cifre and len(parola) >= 3
                and parola not in _SIGLE_DA_LASCIARE):
            parole.append(parola.capitalize())
        else:
            parole.append(parola)
    return " ".join(parole)


def _skin(testo: str) -> tuple[str | None, str | None]:
    """Interfaccia e sua versione — mai il numero di una build.

    La distinzione conta per il confronto con la baseline di test: in
    `core/retest.py` un cambio della cifra principale della skin vale
    «retest completo», mentre un cambio di build vale «smoke test».
    Scambiare `14.0.0.2401` (build) per la versione della skin farebbe
    scattare un retest completo a ogni patch mensile — un allarme che
    suona sempre e che quindi nessuno guarda più.
    """
    testo = testo or ""
    nome_skin = None
    versione = None

    for match in _RE_SKIN.finditer(testo):
        if nome_skin is None:
            nome_skin = _normalizza_skin(match.group("skin"))
        candidata = match.group("versione")
        if candidata and versione is None:
            # Scarta se il numero fa parte di una build: nel testo reale
            # «Oxygen OS Version MT2111_14.0.0.2401(EX01)» il numero è
            # incollato al codice modello da un trattino basso.
            coda = testo[match.end("versione"):match.end("versione") + 1]
            if coda != "_" and "_" not in match.group(0):
                versione = candidata

    if versione is None:
        match_os = _RE_OS_VERSION.search(testo)
        if match_os:
            versione = match_os.group("versione")

    return nome_skin, versione


def _regione(testo: str) -> str | None:
    match = _RE_REGIONE.search(testo or "")
    if not match:
        return None
    regione = match.group("regione").strip()
    if not regione:
        return None
    return regione.title()


def _changelog(testo: str) -> str:
    """Le righe di changelog, senza le decorazioni e senza l'intestazione."""
    righe = []
    dentro = False
    for riga in (testo or "").splitlines():
        pulita = riga.strip()
        if not pulita or _RE_SEPARATORE.match(pulita):
            continue
        if re.search(r"changelog", pulita, re.I):
            dentro = True
            continue
        if dentro:
            righe.append(re.sub(r"^[^\w(]+", "", pulita).strip())
    return " · ".join(r for r in righe if r)[:500]


def parse_messaggio(msg_id: str, testo: str) -> list[Rilascio]:
    """Da un messaggio a zero, uno o più rilasci confermati.

    Zero è l'esito normale e non è un errore: la maggior parte dei post
    del canale sono rilanci da X, sondaggi, dirette e commenti. Restituire
    una lista vuota per quelli è il comportamento giusto.
    """
    testo = testo or ""
    if not testo.strip():
        return []
    if e_preliminare(testo):
        return []

    trovate = list(_RE_BUILD_COMPLETA.finditer(testo))
    patch = _patch_iso(testo)
    android = _android_version(testo)
    skin, skin_versione = _skin(testo)
    regione = _regione(testo)
    changelog = _changelog(testo)

    # --- formati A, B e i post multi-device: la build porta il codice ---
    if trovate:
        rilasci = []
        for match in trovate:
            codice = match.group("codice") + (match.group("variante") or "")
            build = match.group(0)
            nome = _nome_riga_vicina(testo, match.start()) or _nome_device(testo)
            rilasci.append(Rilascio(
                msg_id=msg_id,
                build=build,
                model_code=codice,
                device_name=nome,
                skin=skin,
                skin_version=skin_versione,
                android_version=android,
                patch_level=patch,
                region=regione,
                canale_build=match.group("regione"),
                changelog=changelog,
            ))
        return rilasci

    # --- formato C: codice fra graffe, versione su una riga separata ---
    codice_match = _RE_CODICE_GRAFFE.search(testo)
    versione_match = _RE_VERSIONE_NUDA.search(testo)
    if codice_match and versione_match:
        codice = codice_match.group(1)
        versione = versione_match.group("versione")
        canale = versione_match.group("regione")
        # La build che il telefono mostra davvero è codice + versione +
        # canale: ricomporla per intero evita che lo stesso aggiornamento
        # risulti «diverso» da come lo scrive un'altra fonte.
        build = f"{codice}_{versione}" + (f"({canale})" if canale else "")
        return [Rilascio(
            msg_id=msg_id,
            build=build,
            model_code=codice,
            device_name=_nome_device(testo),
            skin=skin,
            skin_version=skin_versione or versione,
            android_version=android,
            patch_level=patch,
            region=regione,
            canale_build=canale,
            changelog=changelog,
        )]

    return []


def _nome_riga_vicina(testo: str, posizione: int) -> str | None:
    """Nome del modello scritto sulla stessa riga della build, o su quella
    subito sopra.

    Serve ai post che elencano più device insieme:

        🌐 OnePlus 12 CPH2573_15.0.0.23(EX01)
        🌐 OnePlus Open CPH2551_15.0.0.11(EX01)

    Senza questo, le due build finirebbero attribuite entrambe al nome
    trovato in cima al messaggio — cioè un dato sbagliato su un
    dispositivo reale, che è il caso peggiore.
    """
    inizio_riga = testo.rfind("\n", 0, posizione) + 1
    riga = testo[inizio_riga:posizione]
    pulita = re.sub(r"^[^\w]+", "", riga).strip(" :")
    pulita = re.sub(r"\b(?:Version|Oxygen\s?OS|ColorOS|realme\s?UI)\b", "", pulita,
                    flags=re.I).strip(" :")
    if re.match(r"^(?:OnePlus|OPPO|Oppo|realme|Realme)\b", pulita) and len(pulita) <= 40:
        return _ripulisci_nome(pulita)

    righe_precedenti = testo[:inizio_riga].rstrip().splitlines()
    if righe_precedenti:
        candidata = re.sub(r"^[^\w]+", "", righe_precedenti[-1]).strip(" :")
        if (re.match(r"^(?:OnePlus|OPPO|Oppo|realme|Realme)\b", candidata)
                and len(candidata) <= 40
                and not _RE_BUILD_COMPLETA.search(candidata)):
            return _ripulisci_nome(candidata)
    return None


# ----------------------------------------------------------------------
# Estrazione dei messaggi dall'HTML della vista /s/
# ----------------------------------------------------------------------
_RE_BLOCCO = re.compile(
    r'data-post="[^"/]+/(?P<id>\d+)"(?P<resto>.*?)'
    r'(?=data-post="[^"/]+/\d+"|\Z)',
    re.S,
)
_RE_TESTO = re.compile(
    r'class="tgme_widget_message_text[^"]*"[^>]*>(?P<testo>.*?)'
    r'(?=<div class="tgme_widget_message_footer|<div class="tgme_widget_message_info|\Z)',
    re.S,
)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_BR = re.compile(r"<br\s*/?>", re.I)


def _testo_pulito(frammento: str) -> str:
    testo = _RE_BR.sub("\n", frammento or "")
    testo = re.sub(r"</(?:div|p|blockquote)>", "\n", testo, flags=re.I)
    testo = _RE_TAG.sub("", testo)
    testo = html_mod.unescape(testo)
    testo = testo.replace("\u200b", "").replace("\ufeff", "")
    righe = [r.strip() for r in testo.splitlines()]
    return "\n".join(r for r in righe if r)


def estrai_messaggi(pagina_html: str) -> list[tuple[str, str]]:
    """Coppie `(id_messaggio, testo)` dalla pagina `t.me/s/<canale>`."""
    messaggi = []
    for blocco in _RE_BLOCCO.finditer(pagina_html or ""):
        pezzi = [_testo_pulito(m.group("testo"))
                 for m in _RE_TESTO.finditer(blocco.group("resto"))]
        testo = "\n".join(p for p in pezzi if p)
        if testo:
            messaggi.append((blocco.group("id"), testo))
    return messaggi


def rilasci_da_pagina(pagina_html: str) -> tuple[list[Rilascio], str | None]:
    """Rilasci confermati in una pagina del canale.

    **L'errore quando non si estrae nulla è voluto.** Se un domani
    Telegram cambia le classi CSS della vista `/s/`, questo modulo
    smetterebbe di trovare messaggi senza accorgersene, e la fonte
    resterebbe verde in Diagnostica mentre non porta più niente: un
    guasto silenzioso, esattamente quello che il progetto rifiuta. Meglio
    dirlo forte e rosso.

    Attenzione alla distinzione: *nessun messaggio* è un guasto, *nessun
    rilascio fra i messaggi* no — è una giornata in cui il canale ha
    parlato d'altro, e capita spesso.
    """
    messaggi = estrai_messaggi(pagina_html)
    if not messaggi:
        return [], ("nessun messaggio estratto dalla pagina del canale: "
                    "il formato HTML di t.me potrebbe essere cambiato")
    rilasci = []
    for msg_id, testo in messaggi:
        rilasci.extend(parse_messaggio(msg_id, testo))
    return rilasci, None


def copertura(rilasci: list[Rilascio]) -> dict:
    """Riepilogo di cosa copre davvero il canale, per la diagnostica.

    Non è una statistica per fare bella figura: è il numero che dice se
    vale la pena tenere la fonte accesa, ed è lo stesso che ha motivato
    la sua adozione. Se un giorno scende a zero rilasci su molte pagine,
    la fonte va spenta, non tollerata.
    """
    codici = {r.model_code for r in rilasci if r.model_code}
    con_nome = {r.device_name for r in rilasci if r.device_name}
    return {
        "rilasci": len(rilasci),
        "codici_distinti": len(codici),
        "con_nome_esplicito": len(con_nome),
        "regioni": sorted({r.region for r in rilasci if r.region}),
    }
