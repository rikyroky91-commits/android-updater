"""Interprete della ricerca: capisce la domanda, non risponde alla domanda.

## La distinzione su cui poggia tutto

Un modello linguistico, se gli si chiede «che processore monta l'SM-A075F»,
risponde. Sempre. Anche quando non lo sa: produce un chipset plausibile,
scritto bene, indistinguibile da quello vero. Sarebbe la negazione esatta
di come è costruito il resto di questa applicazione — le fonti a livelli di
fiducia, la tabella curata davanti al catalogo, «non disponibile» invece di
dedurre — e renderebbe l'app più piacevole e meno affidabile, che per uno
strumento di QA è il peggiore degli scambi.

Qui quindi il modello fa una cosa sola, e non è produrre dati:

    "quel samsung a07 nero preso l'anno scorso"
              ↓  sceglie fra i candidati CHE GIÀ ABBIAMO
         SM-A075F, SM-A076B
              ↓  ognuno passa dalle fonti vere
    Galaxy A07 4G · Helio G99 · fonte: endpoint FOTA ufficiale

Il modello traduce una domanda mal posta in una chiave di ricerca. Le
risposte continuano a venire da dove venivano prima.

## I due vincoli, meccanici e non affidati al prompt

1. **Sceglie solo fra un elenco che gli passiamo noi**, costruito dai nostri
   cataloghi. Quello che propone viene ricontrollato contro quell'elenco e
   scartato se non c'è: non può inventare un telefono perché non può
   nominarne uno che non conosciamo già. Il prompt glielo chiede, ma è il
   filtro dopo la risposta che lo garantisce — un'istruzione si può
   disattendere, un `if` no.
2. **Non scrive niente in archivio e non è mai una fonte.** Restituisce
   chiavi di ricerca; l'interfaccia le presenta come «interpretazione della
   ricerca», e il dato che ne esce porta l'etichetta della fonte vera che
   lo ha prodotto.

## Perché Anthropic e perché il modello piccolo

Il compito è scegliere fra venti righe di testo: non serve capacità di
ragionamento, serve latenza bassa e costo trascurabile, perché sta dentro
un giro di ricerca. Il modello è configurabile (`AI_QUERY_MODEL`) e il
client sta tutto in `_chiama`, che è una funzione sola: cambiare fornitore
significa riscrivere quella e nient'altro.

Senza chiave la funzione è **spenta**, non rotta: `disponibile()` risponde
`False` e l'interfaccia non mostra nemmeno il pulsante.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import config as C

# ----------------------------------------------------------------------
# I fornitori, in ordine di preferenza
# ----------------------------------------------------------------------
# GEMINI PER PRIMO PERCHÉ È L'UNICO DAVVERO GRATUITO. Google AI Studio dà
# una quota gratuita permanente sui modelli «flash»; Anthropic e OpenAI
# vogliono un credito. Il compito qui è scegliere fra venti righe di
# testo, quindi il modello più piccolo di ciascuno basta e avanza — e la
# differenza fra loro, su questo, non si vede.
#
# Si prende il primo per cui esiste una chiave. Non c'è un interruttore da
# configurare: si incolla una chiave nell'ambiente e l'interprete si
# accende con quel fornitore.
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/"
              "models/{modello}:generateContent")

FORNITORI = (
    # (chiave d'ambiente, nome leggibile, variabile del modello, modello di norma)
    ("GEMINI_API_KEY", "Gemini", "AI_QUERY_MODEL", ""),
    ("ANTHROPIC_API_KEY", "Anthropic", "AI_QUERY_MODEL", "claude-haiku-4-5-20251001"),
    ("OPENAI_API_KEY", "OpenAI", "AI_QUERY_MODEL", "gpt-4o-mini"),
)

# UN ELENCO, NON UN MODELLO SOLO — e la ragione è costata un pomeriggio.
# La prima versione fissava `gemini-2.0-flash`. Google lo ha spento il 1°
# giugno 2026, e un modello spento non ha una corsia di quota: la risposta
# che arriva non è «questo modello non esiste», è **429, quota esaurita**.
# Che manda a cercare un problema di limiti dove c'è un nome vecchio.
#
# I nomi dei modelli cambiano più in fretta di quanto si aggiorni un
# progetto, quindi qui non se ne sceglie uno: si prova in ordine e ci si
# ferma al primo che risponde. Quando anche il primo della lista verrà
# dismesso, l'applicazione scenderà al successivo da sola invece di
# fermarsi. `AI_QUERY_MODEL` scavalca tutto, se serve puntarne uno preciso.
#
# I NOMI SONO STATI RILETTI DALLA DOCUMENTAZIONE, non ricordati: il
# 2026-08-10 la pagina dei modelli dà per attivi 3.6-flash, 3.5-flash,
# 3.5-flash-lite e 3.1-flash-lite, e per spenti tutti i 2.0 e i 2.5. Le
# versioni 2.5 stavano ancora in questo elenco e sono state tolte: un nome
# morto non fa danno — cade e si passa oltre — ma costa una richiesta e
# rimette in circolo il 429 che non si capisce.
#
# I «lite» vengono PRIMA, e non è un dettaglio di gusto: il vincolo qui è
# la quota gratuita, non la bravura. Il compito è scegliere fra venti
# righe di testo, dove un modello piccolo dà la stessa risposta di uno
# grande consumando una frazione della quota del giorno.
MODELLI_GEMINI = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
)

# Stati per cui vale la pena provare il modello successivo: il nome non
# esiste più, non è accessibile, o non ha quota gratuita. Su un errore
# diverso — chiave sbagliata, richiesta malformata — cambiare modello non
# aiuta e nasconderebbe la causa vera.
_STATI_DA_RIPROVARE = (400, 403, 404, 429)

# Il numero di candidati che finiscono nella richiesta. Alto abbastanza
# perché quello giusto ci sia, basso abbastanza da restare una richiesta
# breve: se il candidato corretto non è nell'elenco, il modello non può
# trovarlo — e questo è il vero limite del meccanismo, non la sua bravura.
MAX_CANDIDATI = 40
_TIMEOUT = 25


def fornitore() -> tuple[str, str, str] | None:
    """(nome, chiave, modello) del primo fornitore configurato, o None."""
    for variabile, nome, var_modello, predefinito in FORNITORI:
        chiave = C.env(variabile).strip()
        if chiave:
            return nome, chiave, C.env(var_modello, predefinito)
    return None


def modelli_da_provare() -> list[str]:
    """I modelli da tentare, in ordine, per il fornitore configurato."""
    scelto = fornitore()
    if scelto is None:
        return []
    nome, _chiave, richiesto = scelto
    if richiesto:
        return [richiesto]
    return list(MODELLI_GEMINI) if nome == "Gemini" else []


def modello() -> str:
    da_provare = modelli_da_provare()
    return da_provare[0] if da_provare else ""


def disponibile() -> bool:
    """Vera solo se c'è una chiave: senza, la funzione è spenta."""
    return fornitore() is not None and requests is not None


@dataclass(frozen=True)
class Interpretazione:
    """Cosa ha proposto il modello, e cosa è stato scartato."""
    proposte: tuple[str, ...] = ()
    motivo: str = ""
    errore: str | None = None
    candidati: tuple[str, ...] = field(default=(), repr=False)
    scartate: tuple[str, ...] = ()

    @property
    def riuscita(self) -> bool:
        return bool(self.proposte)


@dataclass(frozen=True)
class Verifica:
    """Esito della verifica assistita, mai un dato firmware dell'archivio.

    Il testo rimane separato dalle fonti di aggiornamento: Gemini puo' aiutare
    a trovare una pagina ufficiale, non diventare lui stesso una fonte che
    dichiara una build o una versione Android.
    """
    sintesi: str = ""
    fonti: tuple[tuple[str, str], ...] = ()
    errore: str | None = None

    @property
    def riuscita(self) -> bool:
        return bool(self.sintesi or self.fonti)


# ======================================================================
# I candidati: l'elenco fra cui il modello può scegliere
# ======================================================================
def _parole(testo: str) -> list[str]:
    return [p for p in re.split(r"[^a-z0-9+]+", (testo or "").lower()) if len(p) > 1]


def candidati_per(query: str, limite: int = MAX_CANDIDATI) -> list[str]:
    """Nomi e codici plausibili, presi dai nostri cataloghi.

    Si mescolano tre strade perché sbagliano in modi diversi: il
    completamento prende chi ha scritto l'inizio giusto, la somiglianza
    prende chi ha sbagliato una lettera, la ricerca per parole prende chi
    ha scritto una frase intera con dentro il nome. Una sola delle tre
    lascerebbe fuori proprio i casi per cui esiste questo modulo.
    """
    from . import suggest

    trovati: list[str] = []
    # QUELLO CHE È STATO SCRITTO NON È UNA TRADUZIONE DI SÉ STESSO.
    #
    # `expand_query` restituisce sempre la domanda come prima forma, e
    # con quella in elenco il modello rispondeva «samsung s23» a chi
    # aveva scritto «samsung s23»: una proposta che non propone niente,
    # e una riga che dice «hai scritto X, ho cercato X». Se la forma
    # scritta bastava, bastava anche premere Invio.
    # IL CONFRONTO È SUL TESTO, NON SULLA CHIAVE NORMALIZZATA. Con la
    # chiave — che toglie trattini e maiuscole — «SMA075F» e «SM-A075F»
    # risultano la stessa cosa, e il candidato giusto spariva: per un
    # codice copiato male l'elenco restava VUOTO, cioè proprio il caso
    # per cui questo tasto esiste. La differenza fra i due è tutto il
    # lavoro da fare.
    scritto = " ".join(str(query or "").split()).lower()

    def aggiungi(voci) -> None:
        for voce in voci or ():
            testo = " ".join(str(voce or "").split())
            if testo and testo.lower() != scritto and testo not in trovati:
                trovati.append(testo)

    # LE FORME DELLA RICERCA NORMALE, PER PRIME.
    #
    # Senza di loro l'elenco era spazzatura, e si vedeva nel risultato:
    # per «samsung s23» il modello riceveva `SAMSUNG-SM-T537A`,
    # `Samsung 心系天下 三星 W23`, `Samsung Gem`… e «Galaxy S23» NON
    # C'ERA. Il modello sceglie solo fra quello che gli diamo, quindi
    # rispondeva «Samsung Galaxy S23+» — il meno peggio dell'elenco.
    #
    # È il limite dichiarato di questo meccanismo: «se il candidato
    # corretto non è nell'elenco, il modello non può trovarlo». Era
    # scritto qui sotto da sempre, e nessuno aveva provato a mettercelo.
    #
    # `expand_query` è la funzione che la ricerca normale usa per
    # arrivare al telefono: è per costruzione l'insieme dei candidati
    # migliori che il progetto sappia produrre.
    try:
        from . import sources

        aggiungi(sources.expand_query(query))
    except Exception:
        pass
    try:
        aggiungi(suggest.codici_simili(query, limit=6, cutoff=0.6))
    except Exception:
        pass
    try:
        aggiungi(suggest.suggest(query, limit=12))
        aggiungi(suggest.did_you_mean(query, limit=6))
    except Exception:
        pass

    # LA FRASE INTERA. «quel samsung a07 nero preso l'anno scorso» non è
    # l'inizio di nessun nome e non somiglia a nessuno: le due strade
    # sopra tornano vuote. Qui si guarda quali nomi contengono le parole
    # della domanda, che è l'unico modo di arrivarci.
    parole = [p for p in _parole(query) if len(p) > 2]
    if parole:
        try:
            catalogo = suggest.catalog()
        except Exception:
            catalogo = []
        punteggi: list[tuple[int, int, str]] = []
        for nome in catalogo:
            normalizzato = nome.lower()
            colpi = sum(1 for p in parole if p in normalizzato)
            if colpi:
                punteggi.append((-colpi, len(nome), nome))
        punteggi.sort()
        aggiungi(n for _, _, n in punteggi[: limite])

    return trovati[:limite]


# ======================================================================
# La chiamata
# ======================================================================
_ISTRUZIONI = (
    "Sei un interprete di ricerca per uno strumento di QA che tiene traccia "
    "degli aggiornamenti software degli smartphone.\n\n"
    "Ricevi quello che l'utente ha digitato e un ELENCO di modelli e codici "
    "che lo strumento conosce già. Il tuo unico compito è dire QUALI VOCI "
    "DELL'ELENCO corrispondono a quello che l'utente sta cercando.\n\n"
    "Regole tassative:\n"
    "- Rispondi SOLO con voci copiate alla lettera dall'elenco. Non "
    "riscriverle, non correggerle, non aggiungerne di tue.\n"
    "- Se nessuna voce corrisponde, restituisci un elenco vuoto. Un elenco "
    "vuoto è una risposta corretta e utile.\n"
    "- Non dire nulla sulle caratteristiche tecniche dei dispositivi "
    "(processore, RAM, versione software): non è quello che ti viene "
    "chiesto e lo strumento ha già le sue fonti per quello.\n"
    "- Se una voce corrisponde ESATTAMENTE al modello scritto, mettila "
    "per prima. Non sostituirla con una variante più ricca: chi scrive "
    "«S23» vuole l'S23, non l'S23+ né l'S23 Ultra. Le varianti si "
    "possono elencare dopo.\n"
    "- Al massimo 4 voci, dalla più probabile.\n\n"
    "Rispondi esclusivamente con questo JSON, senza testo attorno:\n"
    '{"scelte": ["voce esatta", ...], "motivo": "una frase breve in italiano"}'
)

_ISTRUZIONI_VERIFICA = (
    "Sei un assistente di verifica per un'app italiana che traccia firmware "
    "degli smartphone. Devi cercare sul web solo quando serve, usando Google "
    "Search, e aiutare un tecnico a capire quale pagina ufficiale consultare.\n\n"
    "Regole tassative:\n"
    "- Non inventare e non presentare come certo nessun firmware, build, patch "
    "o versione Android che non sia supportata da una pagina del produttore.\n"
    "- Privilegia siti ufficiali del produttore o pagine di supporto; se non "
    "trovi una fonte ufficiale, dichiaralo chiaramente.\n"
    "- Spiega in massimo tre frasi cosa e' verificabile e cosa va controllato "
    "sul dispositivo.\n"
    "- Rispondi esclusivamente con JSON: "
    '{"sintesi":"...","fonti":[{"titolo":"...","url":"https://..."}]}'
)


def _dominio_ufficiale(url: str) -> bool:
    """Accetta solo collegamenti HTTPS a domini plausibilmente ufficiali.

    Gemini puo' restituire link utili ma una card di verifica non deve
    promuovere un blog o un servizio IMEI come fosse il produttore. Questa
    e' una barriera meccanica, non una preferenza affidata al prompt.
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    if not host or not str(url).startswith("https://"):
        return False
    domini = (
        "samsung.com", "apple.com", "google.com", "mi.com", "xiaomi.com",
        "oppo.com", "realme.com", "oneplus.com", "motorola.com", "lenovo.com",
        "vivo.com", "iqoo.com", "honor.com", "huawei.com", "nothing.tech",
        "sony.com", "nokia.com",
    )
    return any(host == dominio or host.endswith("." + dominio)
               for dominio in domini)


class ErroreRiprovabile(RuntimeError):
    """Errore per cui ha senso provare il modello successivo."""


def _chiama(domanda: str) -> str | None:
    """L'unico punto che tocca la rete. Restituisce il TESTO della risposta.

    Ogni fornitore ha la sua forma di richiesta e la sua forma di
    risposta, e sono l'unica cosa che cambia fra loro: sopra e sotto
    questa funzione il modulo non sa nemmeno con chi sta parlando.
    """
    if requests is None:
        return None
    scelto = fornitore()
    if scelto is None:
        return None
    nome, chiave, _richiesto = scelto

    if nome == "Gemini":
        ultimo = None
        for modello_scelto in modelli_da_provare():
            try:
                return _chiama_gemini(domanda, chiave, modello_scelto)
            except ErroreRiprovabile as errore:
                ultimo = f"{modello_scelto}: {errore}"
                continue
        raise RuntimeError(ultimo or "nessun modello disponibile")

    modello_scelto = (modelli_da_provare() or [""])[0]
    if nome == "Anthropic":
        risposta = requests.post(
            ANTHROPIC_URL,
            headers={"x-api-key": chiave,
                     "anthropic-version": ANTHROPIC_VERSION,
                     "content-type": "application/json"},
            json={"model": modello_scelto, "max_tokens": 400,
                  "system": _ISTRUZIONI,
                  "messages": [{"role": "user", "content": domanda}]},
            timeout=_TIMEOUT,
        )
        dati = _controlla(risposta)
        return "\n".join(
            str(b.get("text") or "") for b in (dati.get("content") or ())
            if isinstance(b, dict) and b.get("type") == "text"
        ).strip()

    # OpenAI
    risposta = requests.post(
        OPENAI_URL,
        headers={"authorization": f"Bearer {chiave}",
                 "content-type": "application/json"},
        json={"model": modello_scelto, "temperature": 0, "max_tokens": 400,
              "messages": [{"role": "system", "content": _ISTRUZIONI},
                           {"role": "user", "content": domanda}]},
        timeout=_TIMEOUT,
    )
    dati = _controlla(risposta)
    scelte = dati.get("choices") or [{}]
    return str((scelte[0].get("message") or {}).get("content") or "").strip()


def _chiama_gemini(domanda: str, chiave: str, modello_scelto: str) -> str:
    risposta = requests.post(
        GEMINI_URL.format(modello=modello_scelto),
        headers={"content-type": "application/json", "x-goog-api-key": chiave},
        json={
            "systemInstruction": {"parts": [{"text": _ISTRUZIONI}]},
            "contents": [{"role": "user", "parts": [{"text": domanda}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 400},
        },
        timeout=_TIMEOUT,
    )
    dati = _controlla(risposta)
    pezzi = ((dati.get("candidates") or [{}])[0]
             .get("content", {}).get("parts") or [])
    return "\n".join(str(p.get("text") or "") for p in pezzi).strip()


def _chiama_verifica_gemini(domanda: str, chiave: str, modello_scelto: str) -> str:
    """Gemini con grounding: cerca, ma restituisce solo una pista verificabile.

    Questa chiamata e' volutamente distinta da `_chiama_gemini`: l'interprete
    sceglie tra candidati locali e non ha ragione di consumare una ricerca
    web. La verifica, invece, si attiva solo dal risultato incompleto.
    """
    risposta = requests.post(
        GEMINI_URL.format(modello=modello_scelto),
        headers={"content-type": "application/json", "x-goog-api-key": chiave},
        json={
            "systemInstruction": {"parts": [{"text": _ISTRUZIONI_VERIFICA}]},
            "contents": [{"role": "user", "parts": [{"text": domanda}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 700},
        },
        timeout=_TIMEOUT,
    )
    dati = _controlla(risposta)
    pezzi = ((dati.get("candidates") or [{}])[0]
             .get("content", {}).get("parts") or [])
    return "\n".join(str(p.get("text") or "") for p in pezzi).strip()


def verifica(query: str, contesto: str = "") -> Verifica:
    """Cerca una fonte ufficiale quando la ricerca normale non basta.

    Il fallback e' esplicito: se Gemini non e' configurato, o il fornitore
    non e' Gemini, non si simula una ricerca. Il bottone spiega che continua
    a essere necessario verificare le informazioni sulla pagina collegata.
    """
    testo = " ".join(str(query or "").split())
    scelto = fornitore()
    if not testo:
        return Verifica(errore="nessun modello da verificare")
    if not disponibile() or scelto is None:
        return Verifica(errore="nessuna chiave Gemini configurata")
    nome, chiave, _richiesto = scelto
    if nome != "Gemini":
        return Verifica(errore="la verifica con fonti web richiede GEMINI_API_KEY")

    domanda = (
        f"Modello o codice: {testo}\n"
        f"Contesto gia' noto dall'app: {contesto[:900] or 'nessuna versione certa'}\n\n"
        "Trova una pagina ufficiale del produttore che aiuti a verificare "
        "supporto software, firmware o identita' del modello."
    )
    ultimo = None
    for modello_scelto in modelli_da_provare():
        try:
            risposta = _chiama_verifica_gemini(domanda, chiave, modello_scelto)
            dati = _json_dal_testo(risposta)
            if not isinstance(dati, dict):
                return Verifica(errore="risposta di verifica non interpretabile")
            fonti = []
            for voce in (dati.get("fonti") or [])[:4]:
                if not isinstance(voce, dict):
                    continue
                url = str(voce.get("url") or "").strip()
                titolo = " ".join(str(voce.get("titolo") or "Fonte ufficiale").split())[:160]
                if _dominio_ufficiale(url) and (titolo, url) not in fonti:
                    fonti.append((titolo, url))
            sintesi = " ".join(str(dati.get("sintesi") or "").split())[:700]
            if not fonti:
                return Verifica(
                    sintesi=(sintesi or "Nessuna fonte ufficiale trovata: verifica "
                             "direttamente sul sito del produttore."),
                    errore="nessun collegamento ufficiale verificabile restituito",
                )
            return Verifica(sintesi=sintesi, fonti=tuple(fonti))
        except ErroreRiprovabile as errore:
            ultimo = errore
            continue
        except Exception as errore:
            return Verifica(errore=_spiega(errore))
    return Verifica(errore=_spiega(ultimo or RuntimeError("nessun modello Gemini disponibile")))


def _controlla(risposta) -> dict:
    """Solleva con un messaggio LEGGIBILE, non con lo stato nudo.

    «HTTP 429» non dice se è finita la quota gratuita, se la chiave è
    sbagliata o se il modello non esiste — e sono tre cose da fare diverse.
    Il corpo dell'errore quasi sempre lo dice, e finisce in interfaccia.
    """
    stato = getattr(risposta, "status_code", 0)
    if stato == 200:
        return risposta.json()

    dettaglio = ""
    try:
        corpo = risposta.json()
        dettaglio = str((corpo.get("error") or {}).get("message") or "")[:200]
    except Exception:
        dettaglio = str(getattr(risposta, "text", ""))[:200]
    messaggio = f"HTTP {stato}" + (f" — {dettaglio}" if dettaglio else "")
    if stato in _STATI_DA_RIPROVARE:
        raise ErroreRiprovabile(messaggio)
    raise RuntimeError(messaggio)


def _json_dal_testo(testo: str) -> dict | None:
    """Il JSON, anche se il modello lo ha incorniciato di testo.

    Le istruzioni chiedono JSON e basta, e di solito è quello che arriva.
    «Di solito» non è un contratto: se attorno c'è una frase o dei
    backtick, si prende comunque la graffa più esterna invece di
    dichiarare fallita una risposta che c'era.
    """
    grezzo = (testo or "").strip()
    if grezzo.startswith("```"):
        grezzo = re.sub(r"^```[a-z]*\s*|\s*```$", "", grezzo, flags=re.I)
    try:
        return json.loads(grezzo)
    except ValueError:
        pass
    inizio, fine = grezzo.find("{"), grezzo.rfind("}")
    if inizio == -1 or fine <= inizio:
        return None
    try:
        return json.loads(grezzo[inizio:fine + 1])
    except ValueError:
        return None


def _chiave(testo: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (testo or "").lower())


# Parole che nel confronto non distinguono niente: sono la marca, e chi
# scrive «samsung s23» la scrive proprio perché il catalogo non la usa.
_PAROLE_DI_MARCA = frozenset((
    "samsung", "galaxy", "xiaomi", "redmi", "poco", "oppo", "realme",
    "oneplus", "vivo", "iqoo", "motorola", "moto", "honor", "huawei",
    "google", "pixel", "apple", "nothing", "sony", "nokia",
))


def _prima_il_piu_fedele(query: str, proposte: list[str]) -> list[str]:
    """Chi scrive «S23» vuole l'S23, non l'S23+.

    IL PROMPT NON BASTA, E QUI SI VEDE. La regola gli è scritta, ma il
    modello per «samsung s23» continuava a mettere davanti «Galaxy S23+»
    — e la prima proposta è quella che la pagina cerca davvero, quindi si
    finiva sul telefono sbagliato. È la stessa distinzione di tutto il
    progetto: un'istruzione si può disattendere, un riordino no.

    Il criterio è quello che il progetto usa già per i nomi: **parole
    intere**. «Galaxy S23» contiene la parola `s23`; «Galaxy S23+»
    contiene `s23+`, che è un'altra parola. Le parole di marca non
    contano, perché è proprio quello che cambia fra come si scrive e
    come scrive il catalogo.

    È volutamente conservativo: se nessuna proposta contiene tutte le
    parole della domanda — «quel samsung nero», un codice storpiato —
    nessuna vince e l'ordine del modello resta quello che era.
    """
    parole = {p for p in re.split(r"[^\w+]+", (query or "").lower())
              if p and p not in _PAROLE_DI_MARCA}
    if not parole or len(proposte) < 2:
        return proposte

    def fedele(proposta: str) -> tuple[int, int]:
        tokens = {p for p in re.split(r"[^\w+]+", proposta.lower()) if p}
        contiene = 0 if parole <= tokens else 1
        # QUANTE PAROLE IN PIÙ PORTA, e non è un dettaglio: contenere le
        # parole della domanda non basta, perché «Galaxy S24 Ultra»
        # contiene `s24` esattamente quanto «Galaxy S24». È l'aggiunta —
        # `ultra`, `pro`, `fe` — a fare la differenza fra il telefono
        # chiesto e un suo parente.
        in_piu = len(tokens - parole - _PAROLE_DI_MARCA)
        return (contiene, in_piu)

    # SE NESSUNA PROPOSTA CONTIENE LA DOMANDA, NON SI TOCCA NIENTE.
    #
    # È il caso di «quel samsung nero» o di un codice copiato male: lì il
    # confronto per parole non dice nulla, e il conteggio delle parole in
    # più diventa un criterio a caso — riordinava `Galaxy A56 5G` sotto
    # `Galaxy A55` solo perché il secondo è più corto, cioè scavalcava il
    # giudizio del modello proprio dove il modello sta facendo il lavoro
    # per cui esiste.
    if not any(fedele(p)[0] == 0 for p in proposte):
        return proposte

    # `sorted` è stabile: le proposte che non vincono restano nell'ordine
    # in cui il modello le ha messe.
    return sorted(proposte, key=fedele)


def interpreta(query: str, candidati: list[str] | None = None) -> Interpretazione:
    """Traduce una ricerca mal posta in chiavi che le fonti sanno cercare."""
    testo = " ".join(str(query or "").split())
    if not testo:
        return Interpretazione(errore="nessuna ricerca da interpretare")
    if not disponibile():
        return Interpretazione(errore="nessuna chiave AI configurata")

    elenco = list(candidati if candidati is not None else candidati_per(testo))
    if not elenco:
        # Detto com'è: il modello non ha fallito, non gli è stato dato
        # niente su cui lavorare. Sono due difetti diversi e vanno
        # distinti, altrimenti si va a cercare il problema dove non è.
        return Interpretazione(
            errore="nessun candidato nei cataloghi da sottoporre al modello")

    domanda = (f"L'utente ha cercato: {testo}\n\n"
               "Elenco delle voci conosciute:\n"
               + "\n".join(f"- {voce}" for voce in elenco))

    try:
        risposta = _chiama(domanda)
    except Exception as errore:
        return Interpretazione(errore=_spiega(errore), candidati=tuple(elenco))
    if not risposta:
        return Interpretazione(errore="nessuna risposta dal modello",
                               candidati=tuple(elenco))

    dati = _json_dal_testo(risposta)
    if dati is None:
        return Interpretazione(errore="risposta del modello non interpretabile",
                               candidati=tuple(elenco))

    # ------------------------------------------------------------------
    # IL FILTRO. È questo, non il prompt, che impedisce le invenzioni.
    # ------------------------------------------------------------------
    # Il confronto ignora maiuscole, spazi e trattini, perché un modello
    # che riscrive «SM-A075F» come «SM A075F» sta indicando la voce giusta
    # e sarebbe assurdo scartarla. Tutto il resto — un codice che non
    # esiste, un nome corretto di sua iniziativa, un modello aggiunto
    # perché sembrava pertinente — cade qui, e viene contato: le proposte
    # scartate sono un segnale sulla salute del meccanismo, non rumore da
    # buttare in silenzio.
    ammesse = {_chiave(v): v for v in elenco}
    proposte: list[str] = []
    scartate: list[str] = []
    for scelta in (dati.get("scelte") or ())[:8]:
        etichetta = " ".join(str(scelta or "").split())
        if not etichetta:
            continue
        vera = ammesse.get(_chiave(etichetta))
        if vera is None:
            scartate.append(etichetta)
        elif vera not in proposte:
            proposte.append(vera)

    motivo = " ".join(str(dati.get("motivo") or "").split())[:300]
    return Interpretazione(
        proposte=tuple(_prima_il_piu_fedele(testo, proposte)[:4]),
        motivo=motivo,
        errore=None if proposte else "nessuna corrispondenza fra i candidati",
        candidati=tuple(elenco),
        scartate=tuple(scartate),
    )


def _spiega(errore: Exception) -> str:
    """L'errore del fornitore, tradotto in cosa fare.

    «HTTP 429 — You exceeded your current quota» è vero e inservibile:
    non dice se la quota giornaliera è finita, se il modello è stato
    dismesso o se il progetto non ha mai avuto una corsia gratuita. Sono
    tre cose con tre rimedi diversi, e chi legge il messaggio deve poter
    capire quale delle tre lo riguarda.
    """
    testo = str(errore)
    if "429" in testo:
        return "Servizio AI temporaneamente non disponibile. Riprova più tardi."
    if "401" in testo or "403" in testo:
        return "Servizio AI temporaneamente non disponibile."
    return "Verifica AI non riuscita. Riprova più tardi."


def status() -> str:
    scelto = fornitore()
    if scelto is None:
        return ("spenta (nessuna chiave: serve GEMINI_API_KEY, "
                "ANTHROPIC_API_KEY o OPENAI_API_KEY)")
    da_provare = modelli_da_provare()
    quali = " → ".join(da_provare) if da_provare else "predefinito del fornitore"
    return f"attiva · {scelto[0]} · modelli {quali}"
