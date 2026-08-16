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
# DUE NOMI PER LA STESSA COSA, e il secondo non aveva mai funzionato.
#
# Il `Dockerfile` e `render.yaml` dichiarano `DB_PATH=/tmp/tracker.db`, con
# tanto di nota sul perché l'archivio deve stare in `/tmp`. Qui però si
# leggeva soltanto `TRACKER_DB`: quella variabile non ha mai avuto alcun
# effetto, e in produzione l'archivio è sempre finito nella cartella di
# lavoro. Non dava errore — dava un file in un posto diverso da quello
# documentato, che è il genere di cosa che si scopre il giorno che serve.
#
# `TRACKER_DB` resta la prima perché è quella che il workflow orario di
# GitHub Actions passa al worker.
DB_PATH = env("TRACKER_DB") or env("DB_PATH") or "tracker.db"
RETENTION_DAYS = env_int("RETENTION_DAYS", 400)

# --- Scansione ---------------------------------------------------------
SCAN_INTERVAL_MINUTES = env_int("SCAN_INTERVAL_MINUTES", 60)
HTTP_TIMEOUT = env_int("HTTP_TIMEOUT", 15)
# I cataloghi bulk si preparano in background solo dopo che il sito e' gia'
# pronto a rispondere. Su Render la memoria e' limitata: avviarli insieme al
# worker e' il picco che produceva gli OOM, avviarli uno alla volta evita che
# la prima ricerca li debba invece scaricare tutti da zero.
PRERISCALDA_CATALOGHI = env_bool("PRERISCALDA_CATALOGHI", False)
PRERISCALDA_ATTESA_SECONDI = env_int("PRERISCALDA_ATTESA_SECONDI", 8)
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

# --- Accesso al parco di test -------------------------------------------
# Il parco di test è l'unica parte del sito dietro login: contiene lo
# storico di cosa è stato provato su ciascun device, non è materiale da
# lasciare pubblico come la ricerca. Vedi core/auth.py e web/account.py.
ADMIN_APPROVAL_EMAIL = env("ADMIN_APPROVAL_EMAIL", "Riccardo.cucurullo91@gmail.com")
# Serve per comporre link assoluti nell'email di approvazione (un link
# relativo non si può cliccare da un client di posta). Da impostare
# sull'host reale in produzione; il default è quello del deploy attuale.
SITE_BASE_URL = env("SITE_BASE_URL", "https://android-updater.onrender.com").rstrip("/")
# Sopra HTTPS (Render lo termina sempre) il cookie di sessione deve avere
# l'attributo Secure. Si disattiva solo per collaudare in locale su http.
COOKIE_SECURE = env_bool("COOKIE_SECURE", True)
LOGIN_MAX_TENTATIVI = env_int("LOGIN_MAX_TENTATIVI", 5)
LOGIN_BLOCCO_MINUTI = env_int("LOGIN_BLOCCO_MINUTI", 15)
SESSIONE_DURATA_ORE = env_int("SESSIONE_DURATA_ORE", 12)
RICHIESTA_ACCESSO_SCADENZA_GIORNI = env_int("RICHIESTA_ACCESSO_SCADENZA_GIORNI", 7)


def session_secret() -> str:
    """Chiave per firmare i cookie di sessione. Vedi core/auth.py per cosa
    succede quando non è impostata: mai una stringa vuota o fissa nel
    codice, che chiunque legga la repository pubblica potrebbe leggere e
    usare per firmare una sessione falsa."""
    return env("SESSION_SECRET")


def admin_bootstrap() -> tuple[str, str, str] | None:
    """(username, email, password) per creare il primo amministratore —
    l'unico che può approvare le richieste di accesso al parco di test.

    Le tre variabili si leggono a runtime, non solo al primo avvio: se il
    database non ha ancora nessun amministratore (prima installazione, o
    dopo che il disco effimero di Render è stato ricreato) e queste sono
    impostate, `web/main.py` crea l'account admin. Se un amministratore
    esiste già, l'app non lo ricrea né ne cambia la password da sola —
    altrimenti riavvii periodici del piano gratuito la riporterebbero
    ogni volta alla password iniziale. Nessuna delle tre ha un default:
    meglio un sito senza parco di test accessibile finché non sono
    configurate, che un amministratore con credenziali indovinabili."""
    username = env("ADMIN_USERNAME")
    email = env("ADMIN_EMAIL")
    password = env("ADMIN_PASSWORD")
    if username and email and password:
        return username, email, password
    return None


def smtp_config() -> dict | None:
    """Configurazione SMTP per la sola email che il sito manda: la
    richiesta di approvazione di un nuovo account. None se non è
    impostata — l'invio va allora in errore dichiarato (vedi
    core/mail.py), mai in un tentativo silenzioso che non parte."""
    username = env("SMTP_USERNAME")
    password = env("SMTP_PASSWORD")
    if not (username and password):
        return None
    return {
        "host": env("SMTP_HOST", "smtp.gmail.com"),
        "port": env_int("SMTP_PORT", 587),
        "username": username,
        "password": password,
        "mittente": env("SMTP_MITTENTE") or username,
    }


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

# Semantica del dato firmware. La fiducia dice quanto è attendibile una fonte;
# questa etichetta dice invece *che cosa* la fonte sta dichiarando. Sono due
# assi diversi: una scheda tecnica ufficiale può essere affidabile ma non
# rappresentare l'ultimo firmware rilasciato.
FW_CURRENT = "current"
FW_FACTORY = "factory"
FW_SUPPORT = "support"
FW_BETA = "beta"
FW_REPORTED = "reported"


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
#  25 → Samsung: si sceglie la regione con il firmware PIÙ RECENTE invece
#       della prima che risponde. Per `SM-A325F` la prima della lista
#       (`EUX`) è ferma ad Android 11 mentre tredici altre danno Android
#       13: l'app dichiarava Android 11 per un telefono aggiornato ad
#       Android 13. Cambia il dato in archivio, quindi va ricostruito.
#       Nello stesso giro: codice incompleto («a325») e sigla senza gamma
#       («a32», «samsung a32») ora risolvono allo stesso modello; il chip
#       viene allegato a ogni risultato strutturato e non solo al ripiego;
#       la ricerca da IMEI usa il codice esatto del database TAC invece
#       del nome commerciale.
#  27 → DUE CAMBIAMENTI, entrambi sul modo di interpretare i dati.
#       (a) IDENTITÀ DEL DISPOSITIVO. Le parole di marca che non
#           distinguono nulla escono dalla chiave: «Galaxy S24 Ultra»,
#           «Samsung S24 Ultra» e «S24 Ultra» sono lo stesso telefono, non
#           tre. Le righe già in archivio non convergono da sole — se ne
#           occupa `storage.migra_chiavi_dispositivo()`, che aggiorna anche
#           parco di test e baseline (che la ricostruzione non tocca).
#       (b) FILTRO ANTI-RUMORE. Da una ricerca generica di notizie, nominare
#           un modello e una versione Android non basta più: serve una prova
#           che qualcosa sia stato DISTRIBUITO (numero di build, livello di
#           patch, o una frase di rollout). Modello + versione facevano
#           esattamente 3, cioè la soglia, quindi qualunque titolo che
#           citasse un telefono e un numero di Android diventava un
#           «aggiornamento» e creava un dispositivo.
#  28 → NOME E CODICE PORTANO ALLO STESSO RISULTATO.
#       (a) La ricerca strutturata prova anche i CODICI risolti dal nome,
#           non solo i nomi risolti da un codice: «oppo reno 14» non
#           arrivava a nessuna fonte ufficiale mentre «CPH2737» sì.
#       (b) Lo spazio fra gamma e numero non distingue più niente nella
#           risoluzione nome → codice («reno 14» = «Reno14»).
#       (c) Il codice della variante che ha risposto viaggia con il dato
#           (`model_code`) e decide il chip: senza, il processore di un
#           Galaxy S24 restava «Exynos oppure Snapdragon» anche quando la
#           fonte aveva appena interrogato un codice preciso.
#       (d) Fra le varianti di mercato Samsung si sceglie l'internazionale
#           invece della prima che il dataset elenca — cioè una scelta
#           dichiarata invece del caso. Cambia la build mostrata a chi
#           cerca per nome, quindi va ricostruito.
#       (e) Xiaomi e Honor: il nome ESATTO batte quello che lo contiene.
#           «Redmi Note 13» rispondeva «Redmi Note 13 Pro+ 5G Taiwan».
#       (f) Corretta l'etichetta «Android None», che compariva quando una
#           notizia rumorosa citava una skin senza numero di build.
#  29 → LA MARCA VIENE DAL DATASET, NON DAL FORMATO DEL CODICE.
#       `brand_from_code()` la deduceva da cinque espressioni regolari
#       (`RMX`, `CPH`, `SM-`, `XT`, `XXX-YYnn`): tutto il resto finiva
#       sotto «Altri brand», e `G020E` — un Pixel — finiva addirittura
#       sotto Samsung. La marca entra nella chiave del dispositivo, quindi
#       lo stesso telefono cercato per nome e per codice diventava due
#       schede. I due dataset dei codici la dichiarano riga per riga
#       (`brand_title`, `Retail Branding`) e quel campo veniva scartato in
#       lettura. Misurato su un campione casuale di 32 modelli: era la
#       causa singola più frequente di divergenza fra le due ricerche.
#  30 → LA CHIAVE DEL DISPOSITIVO, RIFATTA SULLE CAUSE MISURATE.
#       Analizzando l'IDENTITÀ di 4300 modelli (marca per marca, senza
#       rete) sono emerse tre cause che spiegano quasi tutte le divergenze
#       fra ricerca per nome e per codice:
#       (a) i dataset scrivono le marche IN CINESE — `SM-G9900` è di 三星,
#           `DE2117` di 一加 — e `gruppo_di_marca()` mandava tutto ciò che
#           non riconosceva in «Altri brand», scavalcando le regole sul
#           formato del codice che funzionavano da sempre;
#       (b) il nome del produttore compare su una grafia e non sull'altra
#           («Nord CE 3 Lite» / «OnePlus Nord CE 3 Lite»): ora esce dalla
#           chiave, ma solo quando ciò che resta è lungo abbastanza da
#           identificare il telefono da solo — sotto quella soglia
#           vivono le radici contese fra sotto-marche («A5»);
#       (c) le parentesi venivano buttate via sempre, e con loro il numero
#           di «Nothing Phone (2)»: TUTTI i Nothing erano lo stesso
#           telefono.
#       Coerenza per marca: Samsung 75→100%, POCO 31→92%, Redmi 13→70%,
#       OnePlus 28→59%, vivo 38→62%, Huawei 58→78%.
#  31 → L'IDENTITA' VIENE DAL CODICE, NON DAL NOME.
#       La radice di meta' dei difetti delle ultime versioni. Il 17% dei
#       codici ha PIU' DI UN nome — `CPH2423` e' insieme «一加 10R»,
#       «OnePlus 10R» e «OnePlus 10R 5G» — e con una chiave costruita sul
#       nome lo stesso telefono diventava tre dispositivi. Normalizzare le
#       grafie una per una (parole di marca, nomi cinesi, parentesi,
#       suffissi) e' la partita che non si vince: le grafie sono un dato
#       della realta'. Quando la fonte dichiara il codice, ora e' il codice
#       a decidere il nome, sempre lo stesso. Il codice DEDOTTO da una
#       build non rinomina: serve al chip, non all'identita'.
#       Nello stesso giro: la marca scritta nella domanda vale anche sulle
#       forme derivate (cercando «xiaomi 14» si otteneva un realme) e il
#       confronto fra nomi e' per parole intere («14» non e' «14T»).
#  32 → la fiducia di una fonte e il tipo di dato diventano distinti. Le
#       versioni di fabbrica, cataloghi di supporto e beta non possono più
#       dichiarare l'ultimo firmware stabile; l'archivio va ricostruito.
#  33 → la ricerca conserva questa distinzione, ma visualizza sempre la
#       versione Android certa più recente disponibile: un dato di fabbrica
#       resta dichiarato come tale, invece di sparire lasciando la pagina
#       senza alcuna versione.
DATA_LOGIC_VERSION = env_int("DATA_LOGIC_VERSION", 33)


# --- Tempo massimo di una ricerca interattiva ---------------------------
# Una ricerca può dover provare più nomi candidati e più formulazioni di
# query, ciascuna con la propria richiesta di rete. Senza un tetto
# complessivo il caso peggiore supera i cinque minuti: la pagina resta in
# caricamento e sembra bloccata, tanto da indurre a ricaricarla.
# Meglio rispondere entro un tempo prevedibile con quello che si è trovato,
# dicendo chiaramente che la ricerca è stata interrotta, che restare muti.
#
# ABBASSATO DA 25 A 12 il 2026-08-10, dopo averlo misurato: una ricerca
# che non trova niente girava per 16,6 secondi in locale e quasi 13 sul
# sito vero. Venticinque secondi non erano un bersaglio ma un tetto, e
# nessuna ricerca utile ci arrivava nemmeno vicino — quelle che ci
# arrivavano erano le ricerche a vuoto, cioè proprio i casi in cui
# aspettare non serve a niente. Chi ha digitato male vuole saperlo
# subito, non fra un quarto di minuto.
SEARCH_BUDGET_SECONDS = env_int("SEARCH_BUDGET_SECONDS", 12)
# Timeout per singola richiesta durante una ricerca interattiva: più corto
# di quello della scansione periodica, che può permettersi di attendere.
#
# ABBASSATO DA 8 A 5 l'11/08/2026. Il controllo del budget sopra
# (`scadenza`) avviene FRA un tentativo e il successivo, non DURANTE: una
# `requests.get(timeout=8)` già partita non si interrompe a metà. Con
# `_news_attempts` che prova fino a quattro formulazioni per candidato, due
# tentativi consecutivi che vanno entrambi in timeout bastavano da soli a
# spiegare i 16,6s misurati il 10/08 — il budget di 12s non li fermava
# perché il secondo tentativo era già partito quando il primo tornava.
# Con 5s il caso peggiore (rete lenta, non fonte irraggiungibile: quello
# fallisce subito) resta comunque abbastanza per una risposta reale — le
# ricerche misurate che TROVANO qualcosa rispondono in frazioni di
# secondo, è solo l'attesa di un timeout a valere la pena accorciare.
SEARCH_HTTP_TIMEOUT = env_int("SEARCH_HTTP_TIMEOUT", 5)
# Numero massimo di nomi candidati provati in una ricerca (un codice può
# risolverne parecchi: RMX3939 ne dà quattro, e provarli tutti moltiplica
# le richieste di rete).
SEARCH_MAX_CANDIDATES = env_int("SEARCH_MAX_CANDIDATES", 3)

# --- Per quanto si ricorda l'esito di una ricerca ------------------------
# Fra due ricerche identiche non c'era NESSUNA memoria: ricaricare la
# pagina rifaceva undici richieste di rete e ripagava dodici secondi. Le
# fonti pubblicano un firmware al massimo una volta al giorno e la
# scansione periodica gira una volta all'ora, quindi tenere una risposta
# per un quarto d'ora non può nascondere niente che sia cambiato davvero.
# A zero la cache è spenta e il comportamento torna quello di prima.
SEARCH_CACHE_SECONDS = env_int("SEARCH_CACHE_SECONDS", 900)
SEARCH_CACHE_MAX = env_int("SEARCH_CACHE_MAX", 200)


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
