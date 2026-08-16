"""Login, registrazione e approvazione degli accessi al parco di test.

**Perché un file a parte.** Le rotte di ricerca/dispositivi/aggiornamenti
in `main.py` non hanno nulla a che fare con «chi può vedere il parco di
test»: tenerle insieme avrebbe allungato ulteriormente un file già grande
con una responsabilità del tutto diversa (identità, non aggiornamenti
Android).

**Come funziona l'approvazione.** Chi vuole un account compila il modulo
di registrazione: l'account nasce SUBITO nel database, ma con stato
`in_attesa` — non può accedere a nulla finché qualcuno non lo approva.
Un'unica persona può farlo: l'amministratore, creato al primo avvio da
`ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` (vedi
`core/config.py::admin_bootstrap`). Riceve una email con un link a
token — a uso singolo, con scadenza — che porta a una pagina di conferma
raggiungibile anche senza aver fatto login (per poter decidere dal
telefono, dal link ricevuto). Se l'email non arriva (SMTP non
configurato, o un problema di consegna), la richiesta resta comunque
visibile e decidibile su `/admin/richieste` dopo aver fatto login come
amministratore: l'email è una comodità, non l'unico canale — lo stesso
principio per cui le notifiche Telegram non sono mai state l'unico modo
di vedere un aggiornamento in questo progetto.

**Standard di sicurezza.** Password con scrypt (`core/auth.py`, nessuna
dipendenza esterna), sessione firmata HMAC in un cookie httponly+secure,
CSRF a doppio invio su ogni modulo di questo file, blocco temporaneo
dell'account dopo troppi tentativi di accesso falliti, tempo di risposta
uniforme sul login indipendentemente dal fatto che lo username esista.
"""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core import auth, config as C, mail, storage
from core.util import to_dt, utcnow

from . import auth_web
from .contesto import contesto, rendi

router = APIRouter()

MESSAGGI_ERRORE_LOGIN = {
    "credenziali": "Nome utente o password non corretti.",
    "in_attesa": "Il tuo account è in attesa di approvazione da parte dell'amministratore.",
    "rifiutato": "La richiesta di accesso non è stata approvata.",
    "bloccato": ("Troppi tentativi non riusciti: riprova tra qualche minuto "
                 f"(fino a {C.LOGIN_BLOCCO_MINUTI})."),
    "modulo_scaduto": "La pagina era aperta da troppo tempo: riprova.",
}

MESSAGGI_ERRORE_REGISTRAZIONE = {
    "username": "Scegli un nome utente di almeno 3 caratteri.",
    "username_esistente": "Questo nome utente è già in uso.",
    "email": "Inserisci un indirizzo email valido.",
    "conferma": "Le due password inserite non coincidono.",
    "modulo_scaduto": "La pagina era aperta da troppo tempo: riprova.",
}

MESSAGGI_ERRORE_PASSWORD = {
    "attuale": "La password attuale inserita non è corretta.",
    "conferma": "Le due password inserite non coincidono.",
    "modulo_scaduto": "La pagina era aperta da troppo tempo: riprova.",
}


def _next_sicuro(valore: str) -> str:
    """Solo un percorso locale: mai un redirect verso un altro dominio
    costruito da un parametro che chiunque può mettere nell'URL.

    LA BARRA ROVESCIA CONTA QUANTO QUELLA DRITTA. Il browser normalizza
    `\\` in `/` prima di risolvere l'indirizzo, quindi `/\\esempio.invalid`
    arriva qui come percorso locale (comincia per `/`, non per `//`) ma
    viene poi seguito come `//esempio.invalid`, cioè un dominio esterno.
    Basta rifiutare la barra rovesciata ovunque nel valore: un percorso
    legittimo di questo sito non ne contiene mai una."""
    if (valore and valore.startswith("/") and not valore.startswith("//")
            and "\\" not in valore):
        return valore
    return "/parco"


def _imposta_cookie_csrf(risposta, csrf: str):
    """Il cookie porta LO STESSO valore già scritto nel campo nascosto del
    modulo appena renderizzato — vedi core/auth.py per il perché del
    doppio invio invece di uno stato lato server."""
    risposta.set_cookie(auth_web.COOKIE_CSRF, csrf, httponly=True,
                        secure=C.COOKIE_SECURE, samesite="lax", max_age=3600)
    return risposta


def _imposta_cookie_sessione(risposta, utente: dict):
    """Il cookie di sessione porta anche l'impronta dell'hash della
    password IN VIGORE ADESSO (vedi `core/auth.py::impronta_password`):
    per questo va riscritto anche dopo un cambio password, non solo al
    login — altrimenti chi ha appena cambiato password si troverebbe
    disconnesso dal proprio stesso cambiamento."""
    token = auth.crea_sessione(utente["id"], auth.impronta_password(utente["password_hash"]))
    risposta.set_cookie(auth_web.COOKIE_SESSIONE, token, httponly=True,
                        secure=C.COOKIE_SECURE, samesite="lax",
                        max_age=C.SESSIONE_DURATA_ORE * 3600)
    return risposta


def assicura_admin() -> str:
    """Crea l'account amministratore al primo avvio, se configurato e se
    non ne esiste già uno (vedi il docstring di `admin_bootstrap` in
    core/config.py per il perché non lo ricrea né lo aggiorna più dopo).
    Il testo tornato finisce in STATO_AVVIO, la stessa diagnostica di
    ogni altro passo dell'avvio in `web/main.py`.

    NON SOLLEVA MAI. Viene chiamata da `web/main.avvio()`, che gira dentro
    il ciclo di vita di FastAPI: un'eccezione qui non lascerebbe il parco
    di test senza amministratore, farebbe fallire l'avvio dell'intero
    sito — ricerca e dispositivi compresi, che con gli account non
    c'entrano nulla. Ogni guasto diventa una riga di diagnostica.
    """
    try:
        if storage.esiste_admin():
            return "già presente"
        bootstrap = C.admin_bootstrap()
        if not bootstrap:
            return ("non configurato (ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD "
                     "mancanti su Render): il parco di test resta inaccessibile finché non lo sono")
        username, email, password = bootstrap
        motivo = auth.password_valida(password)
        if motivo:
            return f"ADMIN_PASSWORD non valida: {motivo}"
        # LO USERNAME PUÒ ESSERE GIÀ OCCUPATO da un account NON
        # amministratore: `/registrati` è pubblico e non richiede che un
        # amministratore esista già, quindi chiunque può registrarsi con
        # lo stesso nome messo in ADMIN_USERNAME — e su un disco effimero
        # il bootstrap riparte a ogni riavvio, trovandoselo davanti.
        # Senza questo controllo l'INSERT violava il vincolo UNIQUE e
        # buttava giù l'avvio. Non si promuove l'account esistente ad
        # amministratore: sarebbe regalare i permessi a chi si è
        # registrato per primo con quel nome.
        if storage.get_utente_per_username(username):
            return (f"ADMIN_USERNAME «{username}» è già di un account non amministratore: "
                    "scegli un altro nome su Render, oppure elimina quell'account dal database")
        storage.crea_utente(username, email, auth.hash_password(password),
                            admin=True, stato=storage.STATO_APPROVATO)
        return f"creato ({username})"
    except Exception as errore:  # pragma: no cover - rete di sicurezza dell'avvio
        return f"non riuscito: {errore}"


# ======================================================================
# Login / logout
# ======================================================================
@router.get("/login", response_class=HTMLResponse)
def pagina_login(request: Request, next: str = "/parco", errore: str = ""):
    if auth_web.utente_da_richiesta(request):
        return RedirectResponse(_next_sicuro(next), status_code=303)
    csrf = auth.nuovo_token_csrf()
    risposta = rendi(request, "login.html", contesto(
        request, attiva="", next=_next_sicuro(next), csrf=csrf,
        errore_testo=MESSAGGI_ERRORE_LOGIN.get(errore, ""),
    ))
    return _imposta_cookie_csrf(risposta, csrf)


@router.post("/login")
def esegui_login(request: Request, username: str = Form(...), password: str = Form(...),
                  next: str = Form("/parco"), csrf: str = Form("")):
    prossimo = _next_sicuro(next)
    if not auth_web.csrf_valido_per(request, csrf):
        return RedirectResponse(f"/login?errore=modulo_scaduto&next={quote(prossimo)}", status_code=303)

    utente = storage.get_utente_per_username(username.strip())
    if not utente:
        # Stesso costo di un confronto vero: senza, il tempo di risposta
        # da solo direbbe se quello username esiste.
        auth.verifica_password(password, auth.hash_fittizio())
        return RedirectResponse(f"/login?errore=credenziali&next={quote(prossimo)}", status_code=303)

    bloccato_fino_a = to_dt(utente.get("bloccato_fino_a"))
    if bloccato_fino_a and bloccato_fino_a > utcnow():
        return RedirectResponse(f"/login?errore=bloccato&next={quote(prossimo)}", status_code=303)

    if utente["stato"] != storage.STATO_APPROVATO:
        codice = "in_attesa" if utente["stato"] == storage.STATO_IN_ATTESA else "rifiutato"
        return RedirectResponse(f"/login?errore={codice}&next={quote(prossimo)}", status_code=303)

    if not auth.verifica_password(password, utente["password_hash"]):
        tentativi = utente["tentativi_falliti"] + 1
        blocco = None
        if tentativi >= C.LOGIN_MAX_TENTATIVI:
            blocco = (utcnow() + timedelta(minutes=C.LOGIN_BLOCCO_MINUTI)).isoformat()
        storage.registra_tentativo_fallito(utente["id"], blocco)
        return RedirectResponse(f"/login?errore=credenziali&next={quote(prossimo)}", status_code=303)

    storage.reset_tentativi_falliti(utente["id"])
    return _imposta_cookie_sessione(RedirectResponse(prossimo, status_code=303), utente)


@router.post("/logout")
def esegui_logout():
    risposta = RedirectResponse("/", status_code=303)
    risposta.delete_cookie(auth_web.COOKIE_SESSIONE)
    return risposta


# ======================================================================
# Registrazione
# ======================================================================
@router.get("/registrati", response_class=HTMLResponse)
def pagina_registrati(request: Request, errore: str = "", inviata: int = 0):
    if auth_web.utente_da_richiesta(request):
        return RedirectResponse("/parco", status_code=303)
    # Un codice noto (username, email, ...) diventa il testo del dizionario
    # sopra; un codice sconosciuto è il motivo preciso restituito da
    # `auth.password_valida` — passato direttamente nell'URL perché è già
    # il messaggio da mostrare, non un'altra chiave da tradurre.
    messaggio_errore = MESSAGGI_ERRORE_REGISTRAZIONE.get(errore, errore)
    csrf = auth.nuovo_token_csrf()
    risposta = rendi(request, "registrati.html", contesto(
        request, attiva="", errore_testo=messaggio_errore, inviata=bool(inviata), csrf=csrf,
    ))
    return _imposta_cookie_csrf(risposta, csrf)


@router.post("/registrati")
def esegui_registrazione(request: Request, username: str = Form(...), email: str = Form(...),
                         password: str = Form(...), conferma: str = Form(...),
                         csrf: str = Form("")):
    if not auth_web.csrf_valido_per(request, csrf):
        return RedirectResponse("/registrati?errore=modulo_scaduto", status_code=303)

    username = username.strip()
    email = email.strip()
    if len(username) < 3:
        return RedirectResponse("/registrati?errore=username", status_code=303)
    if storage.get_utente_per_username(username):
        return RedirectResponse("/registrati?errore=username_esistente", status_code=303)
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return RedirectResponse("/registrati?errore=email", status_code=303)
    if password != conferma:
        return RedirectResponse("/registrati?errore=conferma", status_code=303)
    motivo = auth.password_valida(password)
    if motivo:
        return RedirectResponse(f"/registrati?errore={quote(motivo)}", status_code=303)

    utente_id = storage.crea_utente(username, email, auth.hash_password(password))
    utente = storage.get_utente(utente_id)

    token, token_hash = auth.nuovo_token_richiesta()
    scade_il = (utcnow() + timedelta(days=C.RICHIESTA_ACCESSO_SCADENZA_GIORNI)).isoformat()
    richiesta_id = storage.crea_richiesta_accesso(utente_id, token_hash, scade_il)

    link = f"{C.SITE_BASE_URL}/admin/richieste/token/{richiesta_id}?token={token}"
    oggetto, corpo = mail.costruisci_richiesta(utente, link)
    mail.invia(C.ADMIN_APPROVAL_EMAIL, oggetto, corpo)
    # L'esito dell'invio non cambia la risposta a chi si registra — vedi
    # il docstring del modulo sul perché l'email non è l'unico canale.

    return RedirectResponse("/registrati?inviata=1", status_code=303)


# ======================================================================
# Approvazione — pannello amministratore (richiede login)
# ======================================================================
@router.get("/admin/richieste", response_class=HTMLResponse)
def pagina_richieste(request: Request):
    utente = auth_web.utente_da_richiesta(request)
    if not utente:
        return RedirectResponse("/login?next=/admin/richieste", status_code=303)
    if not auth_web.richiede_admin(utente):
        return RedirectResponse("/parco", status_code=303)
    csrf = auth.nuovo_token_csrf()
    risposta = rendi(request, "admin_richieste.html", contesto(
        request, attiva="", richieste=storage.get_utenti_in_attesa(), csrf=csrf,
    ))
    return _imposta_cookie_csrf(risposta, csrf)


@router.post("/admin/richieste/{utente_id}/approva")
def approva_richiesta(request: Request, utente_id: int, csrf: str = Form("")):
    utente = auth_web.utente_da_richiesta(request)
    if not utente or not auth_web.richiede_admin(utente):
        return RedirectResponse("/login?next=/admin/richieste", status_code=303)
    if auth_web.csrf_valido_per(request, csrf):
        storage.imposta_stato_utente(utente_id, storage.STATO_APPROVATO)
    return RedirectResponse("/admin/richieste", status_code=303)


@router.post("/admin/richieste/{utente_id}/rifiuta")
def rifiuta_richiesta(request: Request, utente_id: int, csrf: str = Form("")):
    utente = auth_web.utente_da_richiesta(request)
    if not utente or not auth_web.richiede_admin(utente):
        return RedirectResponse("/login?next=/admin/richieste", status_code=303)
    if auth_web.csrf_valido_per(request, csrf):
        storage.imposta_stato_utente(utente_id, storage.STATO_RIFIUTATO)
    return RedirectResponse("/admin/richieste", status_code=303)


# ======================================================================
# Approvazione — link a token, dall'email (non richiede login)
# ======================================================================
def _stato_richiesta_token(richiesta_id: int, token: str) -> dict:
    richiesta = storage.get_richiesta_accesso(richiesta_id)
    utente = storage.get_utente(richiesta["utente_id"]) if richiesta else None
    if not richiesta or not utente:
        return {"esito": "non_trovata", "utente": None}
    if utente["stato"] != storage.STATO_IN_ATTESA:
        return {"esito": "gia_decisa", "utente": utente}
    scadenza = to_dt(richiesta["scade_il"])
    if richiesta["usata"] or not scadenza or scadenza <= utcnow():
        return {"esito": "scaduta", "utente": utente}
    if not auth.token_richiesta_valido(token, richiesta["token_hash"]):
        return {"esito": "token_non_valido", "utente": utente}
    return {"esito": "da_decidere", "utente": utente}


@router.get("/admin/richieste/token/{richiesta_id}", response_class=HTMLResponse)
def pagina_richiesta_token(request: Request, richiesta_id: int, token: str = ""):
    stato = _stato_richiesta_token(richiesta_id, token)
    return rendi(request, "admin_richiesta_token.html", contesto(
        request, attiva="", richiesta_id=richiesta_id, token=token, **stato,
    ))


def _decidi_richiesta_token(richiesta_id: int, token: str, stato: str):
    esito = _stato_richiesta_token(richiesta_id, token)
    if esito["esito"] == "da_decidere":
        richiesta = storage.get_richiesta_accesso(richiesta_id)
        storage.imposta_stato_utente(richiesta["utente_id"], stato)
        storage.segna_richiesta_usata(richiesta_id)
    return RedirectResponse(
        f"/admin/richieste/token/{richiesta_id}?token={quote(token)}", status_code=303)


@router.post("/admin/richieste/token/{richiesta_id}/approva")
def approva_richiesta_token(richiesta_id: int, token: str = Form("")):
    return _decidi_richiesta_token(richiesta_id, token, storage.STATO_APPROVATO)


@router.post("/admin/richieste/token/{richiesta_id}/rifiuta")
def rifiuta_richiesta_token(richiesta_id: int, token: str = Form("")):
    return _decidi_richiesta_token(richiesta_id, token, storage.STATO_RIFIUTATO)


# ======================================================================
# Cambio password (richiede login)
# ======================================================================
@router.get("/account/password", response_class=HTMLResponse)
def pagina_cambio_password(request: Request, errore: str = "", ok: int = 0):
    utente = auth_web.utente_da_richiesta(request)
    if not utente:
        return RedirectResponse("/login?next=/account/password", status_code=303)
    csrf = auth.nuovo_token_csrf()
    risposta = rendi(request, "account_password.html", contesto(
        request, attiva="", errore_testo=MESSAGGI_ERRORE_PASSWORD.get(errore, errore),
        ok=bool(ok), csrf=csrf,
    ))
    return _imposta_cookie_csrf(risposta, csrf)


@router.post("/account/password")
def esegui_cambio_password(request: Request, attuale: str = Form(...), nuova: str = Form(...),
                           conferma: str = Form(...), csrf: str = Form("")):
    utente = auth_web.utente_da_richiesta(request)
    if not utente:
        return RedirectResponse("/login", status_code=303)
    if not auth_web.csrf_valido_per(request, csrf):
        return RedirectResponse("/account/password?errore=modulo_scaduto", status_code=303)
    if not auth.verifica_password(attuale, utente["password_hash"]):
        return RedirectResponse("/account/password?errore=attuale", status_code=303)
    if nuova != conferma:
        return RedirectResponse("/account/password?errore=conferma", status_code=303)
    motivo = auth.password_valida(nuova)
    if motivo:
        return RedirectResponse(f"/account/password?errore={quote(motivo)}", status_code=303)
    nuovo_hash = auth.hash_password(nuova)
    storage.imposta_password(utente["id"], nuovo_hash)
    # Tutte le sessioni aperte con la password VECCHIA smettono di valere
    # da qui (è il motivo per cui l'impronta sta nel cookie): a questa,
    # che è quella di chi ha appena cambiato password di sua volontà, si
    # dà subito un cookie nuovo, così non si ritrova buttato fuori.
    utente = dict(utente, password_hash=nuovo_hash)
    return _imposta_cookie_sessione(
        RedirectResponse("/account/password?ok=1", status_code=303), utente)
