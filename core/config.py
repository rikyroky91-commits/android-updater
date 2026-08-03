"""Configurazione centrale dell'applicazione.

Tutti i parametri operativi si leggono da variabili d'ambiente, così il core
resta indipendente da Streamlit (app.py copia `st.secrets` in `os.environ`
all'avvio) e lo stesso codice può girare come worker standalone.
"""
from __future__ import annotations

import os

APP_TITLE = "Universal Mobile Update Tracker"
APP_CAPTION = "Monitoraggio multi-brand degli aggiornamenti Android, per device"


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default) or default


def env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "si", "sì"}


# --- Persistenza -------------------------------------------------------
DB_PATH = env("TRACKER_DB", "tracker.db")
RETENTION_DAYS = env_int("RETENTION_DAYS", 400)

# --- Scansione ---------------------------------------------------------
SCAN_INTERVAL_MINUTES = env_int("SCAN_INTERVAL_MINUTES", 60)
HTTP_TIMEOUT = env_int("HTTP_TIMEOUT", 15)
MAX_ITEMS_PER_SOURCE = env_int("MAX_ITEMS_PER_SOURCE", 100)
# Il tracker Xiaomi è un catalogo strutturato (~1300 device unici), non un
# feed di notizie recenti: qui il limite serve solo da tetto di sicurezza,
# non da finestra "ultime N novità" come per le altre fonti — altrimenti
# un device reale ma non aggiornato di recente (es. Redmi 12) non entra mai
# nel database e sembra "introvabile" anche se esiste davvero.
XIAOMI_MAX_DEVICES = env_int("XIAOMI_MAX_DEVICES", 3000)
# Finestra temporale (in giorni) usata dalle ricerche Google News (Vivo/iQOO,
# Motorola, brand minori). Piu' e' larga, piu' storico si recupera per singola
# scansione, a scapito di qualche risultato meno recente/pertinente.
NEWS_SEARCH_WINDOW_DAYS = env_int("NEWS_SEARCH_WINDOW_DAYS", 120)
USER_AGENT = env(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; AndroidUpdateTracker/2.0; +https://github.com/)",
)

# --- API OxygenUpdater (Oppo / OnePlus / realme) ------------------------
# Il loro endpoint filtra sullo User-Agent: risponde 403 a chiunque non si
# dichiari l'app OxygenUpdater. Di default ci identifichiamo onestamente
# per quello che siamo, quindi finché i manutentori non mettono in
# whitelist questo UA la fonte resta inattiva (403) — è il comportamento
# voluto: il codice è pronto, l'accesso no.
#
# Quando la whitelist sarà attiva basta valorizzare questa variabile con
# l'UA concordato, senza toccare una riga di codice. La configurazione di
# chi esegue il tracker è anche il posto giusto per questa scelta: è una
# decisione di chi ha l'accordo con i manutentori, non qualcosa da
# incorporare nel repository.
OXYGEN_USER_AGENT = env(
    "OXYGEN_USER_AGENT",
    "AndroidUpdateTracker/2.0 (+https://github.com/rikyroky91-commits/android-update-tracker)",
)

# --- Notifiche ---------------------------------------------------------
# Lette a runtime (non a import-time) perché app.py popola l'ambiente dopo.
def telegram_token() -> str:
    return env("TELEGRAM_TOKEN")


def telegram_chat_id() -> str:
    return env("TELEGRAM_CHAT_ID")


def notify_enabled() -> bool:
    return bool(telegram_token() and telegram_chat_id())


# Severità minima per far partire una notifica automatica su un device NON
# in watchlist. I device in watchlist notificano sempre. Di default include
# tutto il semaforo rosso/giallo/verde: solo i canali BETA restano silenziosi
# (sono anteprime, non rollout di produzione).
NOTIFY_MIN_SEVERITY = env("NOTIFY_MIN_SEVERITY", "SECURITY")
NOTIFY_ONLY_WATCHLIST = env_bool("NOTIFY_ONLY_WATCHLIST", False)
NOTIFY_MAX_PER_SCAN = env_int("NOTIFY_MAX_PER_SCAN", 25)

# --- Filtro di rilevanza ----------------------------------------------
RELEVANCE_THRESHOLD = env_int("RELEVANCE_THRESHOLD", 3)

# --- Semaforo QA in base al peso del pacchetto --------------------------
# Sopra questa soglia l'aggiornamento è sempre 🔴 (retest completo),
# sotto è 🟡 o 🟢 secondo il contenuto. Vale solo quando la fonte dichiara
# (o l'articolo cita) una dimensione: altrimenti si ricade sull'euristica
# testuale. In MB (non GB) per evitare l'arrotondamento di 0.5 GiB a 512 MB.
SIZE_MAJOR_MB = env_int("SIZE_MAJOR_MB", 500)

# --- Freschezza device (semaforo "vale la pena testare?") --------------
FRESH_DAYS = env_int("FRESH_DAYS", 30)
STALE_DAYS = env_int("STALE_DAYS", 90)


# --- Brand -------------------------------------------------------------
SAMSUNG = "Samsung"
XIAOMI = "Xiaomi / Redmi / POCO"
PIXEL = "Google Pixel"
HUAWEI = "Huawei / Honor"
OPPO = "Oppo / Realme / OnePlus"
VIVO = "Vivo / iQOO / Motorola"
APPLE = "Apple iPhone / iPad"
OTHER = "Altri brand (Nothing, Umidigi, Doogee…)"

BRANDS = [APPLE, XIAOMI, SAMSUNG, PIXEL, HUAWEI, OPPO, VIVO, OTHER]


# --- Severità ----------------------------------------------------------
SEV_MAJOR = "🔴 MAJOR (nuova release OS)"
SEV_FEATURE = "🟡 FEATURE DROP"
SEV_SECURITY = "🟢 PATCH / SECURITY"
SEV_BETA = "🔵 BETA / PREVIEW"

SEVERITY_ORDER = [SEV_MAJOR, SEV_FEATURE, SEV_SECURITY, SEV_BETA]
SEVERITY_RANK = {name: i for i, name in enumerate(SEVERITY_ORDER)}
SEVERITY_COLORS = {
    SEV_MAJOR: "#FF4B4B",
    SEV_FEATURE: "#FFAA00",
    SEV_SECURITY: "#00CC66",
    SEV_BETA: "#3B82F6",
}
# Mappatura sintetica usata da NOTIFY_MIN_SEVERITY
SEVERITY_KEYS = {
    "MAJOR": SEV_MAJOR,
    "FEATURE": SEV_FEATURE,
    "SECURITY": SEV_SECURITY,
    "BETA": SEV_BETA,
}


def min_severity_rank() -> int:
    """Rank massimo (incluso) ammesso per notificare un device non in watchlist."""
    label = SEVERITY_KEYS.get(NOTIFY_MIN_SEVERITY.upper(), SEV_FEATURE)
    return SEVERITY_RANK.get(label, 1)


# --- Livelli di fiducia delle fonti ------------------------------------
# structured : dato ufficiale/strutturato → è per definizione un rilascio reale
# curated    : feed dedicato agli aggiornamenti → filtro morbido
# noisy      : ricerca generica → filtro rigido
TRUST_STRUCTURED = "structured"
TRUST_CURATED = "curated"
TRUST_NOISY = "noisy"


# --- Controlli di plausibilità (rete di sicurezza sui dati) -------------
# Nessuna fonte esterna è affidabile per sempre: quando una si rompe, il
# rischio peggiore non è restare senza dati ma pubblicarne di falsi. Questi
# tetti servono a scartare valori impossibili invece di mostrarli.
# Vanno alzati quando esce una nuova major (una riga, una volta l'anno).
MAX_PLAUSIBLE_ANDROID = env_int("MAX_PLAUSIBLE_ANDROID", 20)
# Apple dal 2025 numera per anno (iOS 26 = ciclo 2025-2026).
MAX_PLAUSIBLE_IOS = env_int("MAX_PLAUSIBLE_IOS", 30)


# --- Versione della logica di interpretazione dei dati -------------------
# Va incrementata OGNI VOLTA che si corregge il modo in cui una fonte viene
# interpretata (parsing, mappature, semantica dei campi). All'avvio, se il
# database è stato popolato con una versione precedente, gli aggiornamenti
# raccolti vengono azzerati e ricostruiti alla prima scansione.
#
# Perché serve: i dati in archivio sono il RISULTATO della logica di
# interpretazione. Correggere un errore di lettura senza buttare via ciò che
# quell'errore aveva prodotto lascia i valori sbagliati visibili in eterno —
# è esattamente quanto accaduto con iOS 26 attribuito a un iPhone 8 e con la
# versione Android letta da una promessa di aggiornamento futuro: la
# correzione era attiva, ma la scheda dispositivo continuava a mostrare il
# vecchio dato perché nessuno lo aveva rimosso.
#
# Storico:
#   1 → versione iniziale
#   2 → Honor: versione di fabbrica invece della promessa futura
#   3 → Apple: firmware per singolo dispositivo invece dell'elenco globale,
#       più controlli di plausibilità sui dati in ingresso
#   4 → pulizia dello stato delle fonti ritirate e disattivazione della
#       fonte OxygenUpdater ufficiale (inaccessibile senza impersonazione)
#   5 → realme: pagina ufficiale AER come fonte strutturata, con mappatura
#       ufficiale dei codici modello e riconoscimento del brand dal codice
#   6 → nomi regionali realme cercabili singolarmente e confronto tollerante
#       allo spazio fra sigla e cifre ("C 63" = "C63")
#   7 → ordinamento per data di uscita reale invece che per data di
#       rilevazione della scansione
#   8 → fonte realme: regex corretta per l'HTML reale (prima era costruita
#       sulla resa in markdown, che il codice non riceve mai)
#   9 → una sigla breve ("C61") non viene più scambiata per codice modello
#  10 → ricerca su più fonti invece di una scelta in base al brand, ed
#       espansione della query centralizzata (uguale per tutte le marche)
#  11 → fonte ufficiale Oppo (elenco AER) e notizie ColorOS dedicate
#  12 → estrazione Oppo tollerante all'HTML reale (spazi, nomi duplicati,
#       slug degli URL) e diagnosi passo-passo di una ricerca
#  13 → il nome del modello non contiene più il codice fra parentesi, che
#       lo rendeva un dispositivo diverso da quello delle fonti ufficiali
#  14 → GSMArena come fonte universale della versione di fabbrica, per le
#       marche senza fonte ufficiale (Oppo, vivo, OnePlus, brand minori)
#  15 → la ricerca sceglie il risultato CON la versione firmware invece
#       di fermarsi alla prima fonte che risponde qualcosa
#  16 → rilevamento delle fonti che rendono molto meno del solito pur
#       rispondendo senza errori (guasto silenzioso)
#  17 → fonte ufficiale vivo/iQOO (schema AER), non verificata sul sito reale
#  18 → Oppo: archivio firmware ufficiale di support.oppo.com
#       (`softwareUpgrade/info`). Per i ~94 modelli coperti la versione
#       passa da «di fabbrica, dedotta» a versione rilasciata reale, con
#       data e livello di patch. Vedi core/oppo_official.py.
#       Nello stesso giro: corretto il catalogo dei suggerimenti, che una
#       variabile di ciclo omonima riduceva a un solo modello (l'errore era
#       invisibile perché un `except Exception: pass` lo inghiottiva).
#  19 → vivo: parser riscritto sulla TABELLA REALE della pagina AER, dopo
#       averla finalmente letta. Il precedente era un'ipotesi (schema di
#       Honor/realme) e la fonte era in errore da giorni: la tabella non
#       scrive la marca nel nome, usa `&nbsp;` e dice «Shipped version:
#       Android 16» invece di «Shipped version: 15». Ora 20 modelli, con
#       fine del supporto e cadenza delle patch.
#  20 → catalogo Android Enterprise Recommended in JSON come fonte
#       AGGIUNTIVA (non sostitutiva: la misura dice che le pagine ufficiali
#       Honor e vivo hanno più versioni del JSON). Porta 706 dispositivi di
#       40+ marche, 1404 codici modello verificati, la finestra di supporto
#       di sicurezza, e la prima fonte strutturata per OnePlus.
#  21 → COPERTURA. Il nome commerciale ora combacia anche quando differisce
#       per una sigla di connettività: il catalogo scrive «Galaxy A55 5G»,
#       le persone cercano «Galaxy A55», e con il confronto esatto quel
#       modello non aveva nessun codice — quindi il controllo versione
#       Samsung, che è generico, non poteva partire. Dati presenti,
#       meccanismo funzionante, risultato zero. Samsung passa da 23 modelli
#       a tutti quelli del dataset (2332 codici). Inoltre la scansione
#       periodica interroga anche i Samsung del parco di test, che prima
#       non ricevevano notifiche se fuori dalla tabella scritta a mano.
#       Aggiunta la ricerca a comando per Pixel, che non c'era: la fonte
#       esisteva solo nella scansione periodica.
#  22 → Pixel: la fonte serve immagini del canale BETA, non stabili
#       (verificato: tutte le pagine per-release contengono solo file
#       `*_beta-ota-*`). Dichiarava «Pixel 9 Pro — Android 17», cioè
#       un'anteprima spacciata per la versione installata, su OGNI Pixel.
#       Ora gli item sono marcati beta e non impongono più una versione al
#       dispositivo. Serve una fonte stabile: la pagina delle immagini
#       ufficiali è resa in JavaScript e non è leggibile via HTTP.
DATA_LOGIC_VERSION = env_int("DATA_LOGIC_VERSION", 22)


# --- Tempo massimo di una ricerca interattiva ---------------------------
# Una ricerca può dover provare più nomi candidati e più formulazioni di
# query, ciascuna con la propria richiesta di rete. Senza un tetto
# complessivo il caso peggiore supera i cinque minuti: la pagina resta in
# caricamento e sembra bloccata, tanto da indurre a ricaricarla.
# Meglio rispondere entro un tempo prevedibile con quello che si è trovato,
# dicendo chiaramente che la ricerca è stata interrotta, che restare muti.
SEARCH_BUDGET_SECONDS = env_int("SEARCH_BUDGET_SECONDS", 25)
# Timeout per singola richiesta durante una ricerca interattiva: più corto
# di quello della scansione periodica, che può permettersi di attendere.
SEARCH_HTTP_TIMEOUT = env_int("SEARCH_HTTP_TIMEOUT", 8)
# Numero massimo di nomi candidati provati in una ricerca (un codice può
# risolverne parecchi: RMX3939 ne dà quattro, e provarli tutti moltiplica
# le richieste di rete).
SEARCH_MAX_CANDIDATES = env_int("SEARCH_MAX_CANDIDATES", 3)


# --- Persistenza del database fra i riavvii ------------------------------
# Su hosting con disco effimero (Streamlit Cloud) il file del database
# sparisce a ogni riavvio o sospensione, e l'archivio riparte da zero.
# Se configurato, il file viene sincronizzato su un archivio esterno.
# Vedi core/backup.py per il funzionamento e le alternative valutate.
#
# Opzione 1 — Gist GitHub privato (la più semplice):
#   BACKUP_GIST_ID       id del gist (dalla sua URL)
#   BACKUP_GITHUB_TOKEN  token con permesso "gist"
# Opzione 2 — qualsiasi archivio che accetti PUT/GET:
#   BACKUP_URL           indirizzo completo del file
BACKUP_EVERY_MINUTES = env_int("BACKUP_EVERY_MINUTES", 30)
