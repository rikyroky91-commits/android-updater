"""Gli account dei giocatori di Parry Brawl Survivor (18/10/2026).

Il gioco è un sito statico su GitHub Pages (origine `https://rikyroky91-commits.github.io`,
percorso `/parry-brawl-survivor/`) e parla con questo server, come già fa per la classifica
(`/api/corsa/*` in `web/main.py`). Qui si tiene un account per giocatore — nick, email,
password — e il suo salvataggio, così la partita si ritrova su un altro dispositivo.

Rotte (tutte JSON, sotto `/api/giocatore`):

- `POST /registra`      {nick, email, password}  → {token, nick, salvataggio: null}
- `POST /accedi`        {login, password}        → {token, nick, salvataggio, aggiornato}
- `GET  /salvataggio`   (Bearer)                 → {nick, salvataggio, aggiornato}
- `PUT  /salvataggio`   (Bearer) {salvataggio}   → {ok: true, aggiornato}
- `POST /esci`          (Bearer)                 → {ok: true}

COSA NON SONO. Non sono utenti del tracker: stanno nelle tabelle `giocatori` e
`gettoni_giocatori`, non in `utenti`, e nessuna rotta del tracker le guarda. Un giocatore non
ha e non avrà mai permessi sul tracker. La password usa lo stesso hash scrypt del tracker
(`core.auth.hash_password` / `verifica_password`).

IL GETTONE. Niente cookie (il sito sta su un'altra origine): il gioco tiene il gettone e lo
manda in `Authorization: Bearer …`. Il server ne tiene solo lo SHA-256, e scade dopo 180 giorni.

L'EMAIL serve solo all'unicità e all'accesso: non torna mai in nessuna risposta e non si
scrive nei log.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from core import auth, storage
from core.util import utcnow

router = APIRouter()

DURATA_GETTONE = timedelta(days=180)
MAX_SALVATAGGIO = 64 * 1024          # byte del salvataggio serializzato
_MAX_CORPO_ACCESSO = 4096            # registra / accedi: tre campi brevi
_MAX_PASSWORD = 200                  # scrypt su una password enorme costa: si taglia prima

_NICK = re.compile(r"^[A-Za-z0-9 _\-]{3,20}$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")

# Il sito del gioco, e due indirizzi per provarlo in locale. Le altre origini non ricevono
# l'intestazione: il browser blocca la risposta. Niente credenziali (niente cookie): il
# gettone viaggia in Authorization, che va dichiarato fra le intestazioni ammesse.
ORIGINI_AMMESSE = {
    "https://rikyroky91-commits.github.io",
    "http://localhost:8765",
    "http://127.0.0.1:8765",
}
_CORS_BASE = {"Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
              "Access-Control-Allow-Headers": "Authorization, Content-Type",
              "Access-Control-Max-Age": "86400"}

_ERRORE_ACCESSO = "Nome, email o password non corretti."
_ERRORE_GETTONE = "Accesso scaduto o non valido: entra di nuovo."

# Limite per indirizzo, in memoria, come `_troppi_invii` della classifica: tentativi
# per finestra di secondi. Per l'accesso conta ogni tentativo, riuscito o no.
_LIMITI = {"registra": (5, 3600), "accedi": (15, 600)}
_TENTATIVI: dict[tuple[str, str], list[float]] = {}


def _intestazioni(request: Request) -> dict:
    testa = {"Cache-Control": "no-store", "Vary": "Origin"}
    origine = request.headers.get("origin", "")
    if origine in ORIGINI_AMMESSE:
        testa["Access-Control-Allow-Origin"] = origine
        testa.update(_CORS_BASE)
    return testa


def _risposta(request: Request, corpo: dict, codice: int = 200) -> JSONResponse:
    return JSONResponse(corpo, status_code=codice, headers=_intestazioni(request))


def _errore(request: Request, testo: str, codice: int = 400) -> JSONResponse:
    return _risposta(request, {"errore": testo}, codice)


def _indirizzo(request: Request) -> str:
    # Stessa regola di `web/main.py`: davanti c'è Caddy, che scrive X-Forwarded-For.
    avanti = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return avanti or (request.client.host if request.client else "?")


def _troppi(tipo: str, chi: str) -> bool:
    massimo, finestra = _LIMITI[tipo]
    adesso = time.time()
    if len(_TENTATIVI) > 5000:      # non deve crescere senza fine
        for k in [k for k, v in _TENTATIVI.items() if not v or adesso - v[-1] > 3600]:
            _TENTATIVI.pop(k, None)
    recenti = [t for t in _TENTATIVI.get((tipo, chi), []) if adesso - t < finestra]
    if len(recenti) >= massimo:
        _TENTATIVI[(tipo, chi)] = recenti
        return True
    recenti.append(adesso)
    _TENTATIVI[(tipo, chi)] = recenti
    return False


async def _corpo_json(request: Request, massimo: int):
    """Il corpo come JSON, o None se manca, è troppo lungo o non si legge."""
    try:
        if int(request.headers.get("content-length") or 0) > massimo:
            return None
        grezzo = await request.body()
        if len(grezzo) > massimo:
            return None
        return json.loads(grezzo)
    except Exception:
        return None


def _hash_gettone(gettone: str) -> str:
    return hashlib.sha256(gettone.encode("utf-8")).hexdigest()


def _nuovo_gettone(giocatore_id: int) -> str:
    gettone = secrets.token_urlsafe(32)
    storage.crea_gettone_giocatore(giocatore_id, _hash_gettone(gettone),
                                   (utcnow() + DURATA_GETTONE).isoformat())
    return gettone


def _gettone_della_richiesta(request: Request) -> str | None:
    tipo, _, gettone = request.headers.get("authorization", "").partition(" ")
    gettone = gettone.strip()
    if tipo.lower() != "bearer" or not gettone or len(gettone) > 200:
        return None
    return gettone


def _giocatore(request: Request) -> dict | None:
    gettone = _gettone_della_richiesta(request)
    return storage.giocatore_per_gettone(_hash_gettone(gettone)) if gettone else None


def _salvataggio(giocatore: dict):
    testo = giocatore.get("salvataggio")
    if not testo:
        return None
    try:
        return json.loads(testo)
    except ValueError:      # pragma: no cover - lo scrive solo questa rotta, già controllato
        return None


# --- Preflight -----------------------------------------------------------------
@router.options("/api/giocatore/registra")
@router.options("/api/giocatore/accedi")
@router.options("/api/giocatore/salvataggio")
@router.options("/api/giocatore/esci")
def api_giocatore_preflight(request: Request):
    return Response(status_code=204, headers=_intestazioni(request))


# --- Rotte ---------------------------------------------------------------------
@router.post("/api/giocatore/registra")
async def api_giocatore_registra(request: Request):
    dati = await _corpo_json(request, _MAX_CORPO_ACCESSO)
    if not isinstance(dati, dict):
        return _errore(request, "Richiesta non valida.")
    nick = " ".join(str(dati.get("nick") or "").split())
    email = str(dati.get("email") or "").strip().lower()
    password = dati.get("password")
    if not _NICK.match(nick):
        return _errore(request, "Il nome deve avere da 3 a 20 caratteri: lettere, cifre, spazio, _ o -.")
    if len(email) > 254 or not _EMAIL.match(email):
        return _errore(request, "Email non valida.")
    if not isinstance(password, str) or len(password) < 8:
        return _errore(request, "La password deve avere almeno 8 caratteri.")
    if len(password) > _MAX_PASSWORD:
        return _errore(request, "Password troppo lunga.")
    if _troppi("registra", _indirizzo(request)):
        return _errore(request, "Troppe registrazioni di fila: riprova più tardi.", 429)
    occupato = storage.giocatore_occupato(nick, email)
    if occupato == "nick":
        return _errore(request, "Questo nome è già preso.", 409)
    if occupato == "email":
        return _errore(request, "Questa email ha già un account.", 409)
    nuovo = storage.crea_giocatore(nick, email, auth.hash_password(password))
    if nuovo is None:       # preso nel frattempo da un'altra richiesta
        return _errore(request, "Nome o email già usati.", 409)
    return _risposta(request, {"token": _nuovo_gettone(nuovo), "nick": nick, "salvataggio": None})


@router.post("/api/giocatore/accedi")
async def api_giocatore_accedi(request: Request):
    dati = await _corpo_json(request, _MAX_CORPO_ACCESSO)
    if not isinstance(dati, dict):
        return _errore(request, "Richiesta non valida.")
    login = " ".join(str(dati.get("login") or "").split())
    password = dati.get("password")
    if not login or not isinstance(password, str) or not password or len(password) > _MAX_PASSWORD or len(login) > 254:
        return _errore(request, _ERRORE_ACCESSO, 401)
    if _troppi("accedi", _indirizzo(request)):
        return _errore(request, "Troppi tentativi: riprova fra qualche minuto.", 429)
    giocatore = storage.giocatore_per_accesso(login)
    # Se l'account non c'è si calcola comunque uno scrypt: il tempo di risposta non dice
    # se un nick o un'email esistono (stessa idea di core/auth.py).
    hashed = giocatore["password_hash"] if giocatore else auth.hash_fittizio()
    if not auth.verifica_password(password, hashed) or not giocatore:
        return _errore(request, _ERRORE_ACCESSO, 401)
    return _risposta(request, {"token": _nuovo_gettone(giocatore["id"]), "nick": giocatore["nick"],
                               "salvataggio": _salvataggio(giocatore), "aggiornato": giocatore["aggiornato_il"]})


@router.get("/api/giocatore/salvataggio")
def api_giocatore_leggi(request: Request):
    giocatore = _giocatore(request)
    if not giocatore:
        return _errore(request, _ERRORE_GETTONE, 401)
    return _risposta(request, {"nick": giocatore["nick"], "salvataggio": _salvataggio(giocatore),
                               "aggiornato": giocatore["aggiornato_il"]})


@router.put("/api/giocatore/salvataggio")
async def api_giocatore_scrivi(request: Request):
    giocatore = _giocatore(request)
    if not giocatore:
        return _errore(request, _ERRORE_GETTONE, 401)
    # Margine sopra MAX_SALVATAGGIO per l'involucro {"salvataggio": …} e gli spazi.
    dati = await _corpo_json(request, MAX_SALVATAGGIO + 1024)
    if dati is None:
        return _errore(request, "Salvataggio troppo grande o non leggibile.", 413
                       if int(request.headers.get("content-length") or 0) > MAX_SALVATAGGIO else 400)
    salvataggio = dati.get("salvataggio") if isinstance(dati, dict) else None
    if not isinstance(salvataggio, dict):
        return _errore(request, "Il salvataggio deve essere un oggetto JSON.")
    testo = json.dumps(salvataggio, ensure_ascii=False, separators=(",", ":"))
    if len(testo.encode("utf-8")) > MAX_SALVATAGGIO:
        return _errore(request, "Salvataggio troppo grande.", 413)
    quando = storage.salva_salvataggio_giocatore(giocatore["id"], testo)
    return _risposta(request, {"ok": True, "aggiornato": quando})


@router.post("/api/giocatore/esci")
def api_giocatore_esci(request: Request):
    gettone = _gettone_della_richiesta(request)
    if not gettone or not storage.giocatore_per_gettone(_hash_gettone(gettone)):
        return _errore(request, _ERRORE_GETTONE, 401)
    storage.elimina_gettone_giocatore(_hash_gettone(gettone))
    return _risposta(request, {"ok": True})
