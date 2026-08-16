"""Password, sessioni e token — solo stdlib, come il resto di `core/`.

**Perché esiste.** Il parco di test è l'unica pagina del sito dietro
login (vedi `web/account.py`): questo modulo ha la parte che non deve mai
dipendere da una libreria esterna che smette di essere mantenuta o
introduce una falla — hashing password, firma dei cookie di sessione,
token di approvazione monouso. Nessuna delle tre cose ha bisogno di più
della libreria standard.

## Password

`hashlib.scrypt` (stdlib dalla 3.6), non un hash veloce come SHA-256: uno
che costa deliberatamente tempo e memoria a chi prova a indovinare una
password offline. I parametri (N=2**14, r=8, p=1) restano dentro il
limite di RAM del piano gratuito di Render citato altrove in questo
progetto (`scripts/preload_cataloghi.py`, `render.yaml`) — un costo più
alto sarebbe più sicuro in astratto ma rischia l'OOM proprio nel momento
in cui più conta, un tentativo di forzare l'accesso.

## Sessioni

Un cookie che porta l'identità firmata con HMAC-SHA256, non un
riferimento a una sessione salvata da qualche parte: niente tabella da
pulire, niente stato server da perdere a ogni riavvio del piano gratuito
(che riavvia da solo dopo un periodo di inattività). La firma impedisce
di alterare il contenuto senza conoscere la chiave; la scadenza è dentro
il payload firmato, quindi non falsificabile spostando l'orologio del
client.

**La chiave di firma.** Se `SESSION_SECRET` non è impostata, se ne genera
una casuale all'avvio del processo invece di usarne una fissa nel codice
(che chiunque leggesse questa repository pubblica potrebbe copiare). Il
costo è che ogni riavvio invalida le sessioni esistenti — su un piano che
si addormenta dopo inattività, capita spesso. È un compromesso dichiarato:
disconnettere tutti ogni tanto è innocuo, una chiave di firma prevedibile
non lo è. Chi vuole sessioni stabili imposta `SESSION_SECRET` su Render.

## Token di approvazione

Lo stesso principio delle password: mai il valore in chiaro nel database.
Il link mandato via email porta il token vero; il database conserva solo
`sha256(token)`. Chi legge una copia del database (un backup, per
esempio) non può fabbricare un'approvazione.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from . import config as C

# Parametri scrypt: vedi il docstring del modulo per il perché di questi
# valori specifici (limite di memoria del piano gratuito).
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

# Hash fittizio ma con la stessa forma di uno vero, usato per confrontare
# una password anche quando lo username non esiste — altrimenti chi prova
# ad accedere misurerebbe dal tempo di risposta se uno username esiste,
# perché la verifica su un utente inesistente salterebbe interamente il
# costo (deliberato) dello scrypt.
_HASH_FITTIZIO = None  # calcolato al primo uso, vedi hash_fittizio()

# Generata una sola volta per processo: vedi "La chiave di firma" sopra.
_CHIAVE_DI_RISERVA = secrets.token_urlsafe(48)


def _chiave_sessione() -> bytes:
    valore = C.session_secret() or _CHIAVE_DI_RISERVA
    return valore.encode("utf-8")


def _b64(dati: bytes) -> str:
    return base64.urlsafe_b64encode(dati).rstrip(b"=").decode("ascii")


def _unb64(testo: str) -> bytes:
    imbottitura = "=" * (-len(testo) % 4)
    return base64.urlsafe_b64decode(testo + imbottitura)


# ----------------------------------------------------------------------
# Password
# ----------------------------------------------------------------------
def password_valida(password: str) -> str | None:
    """None se la password rispetta lo standard minimo, altrimenti il
    motivo da mostrare. Non richiede simboli o maiuscole obbligatorie —
    la letteratura NIST sconsiglia quelle regole, che spingono verso
    password prevedibili («Password1!») più che verso password robuste:
    la lunghezza è la difesa che conta davvero contro un attacco offline."""
    if not password or len(password) < 10:
        return "La password deve avere almeno 10 caratteri."
    if len(password) > 200:
        return "Password troppo lunga."
    if password != password.strip():
        return "La password non può iniziare o finire con uno spazio."
    return None


def hash_password(password: str) -> str:
    sale = secrets.token_bytes(16)
    derivato = hashlib.scrypt(
        password.encode("utf-8"), salt=sale,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(sale)}${_b64(derivato)}"


def hash_fittizio() -> str:
    """Un hash valido di una password che nessuno userà mai, calcolato
    una sola volta: serve solo a occupare lo stesso tempo di un confronto
    vero quando lo username non esiste (vedi il docstring del modulo)."""
    global _HASH_FITTIZIO
    if _HASH_FITTIZIO is None:
        _HASH_FITTIZIO = hash_password(secrets.token_urlsafe(32))
    return _HASH_FITTIZIO


def verifica_password(password: str, hashed: str) -> bool:
    try:
        algoritmo, n, r, p, sale_b64, derivato_b64 = hashed.split("$")
        if algoritmo != "scrypt":
            return False
        sale = _unb64(sale_b64)
        atteso = _unb64(derivato_b64)
        calcolato = hashlib.scrypt(
            password.encode("utf-8"), salt=sale,
            n=int(n), r=int(r), p=int(p), dklen=len(atteso),
        )
        return hmac.compare_digest(calcolato, atteso)
    except Exception:
        return False


# ----------------------------------------------------------------------
# Sessioni
# ----------------------------------------------------------------------
def impronta_password(password_hash: str) -> str:
    """Poche cifre derivate dall'hash della password, da mettere nella
    sessione. NON è un secondo hash della password: parte dall'hash già
    salato, quindi non aggiunge niente da cui risalire alla password.

    **A cosa serve.** Una sessione firmata non ha uno stato lato server
    da cancellare: cambiare la password non basterebbe a invalidare le
    sessioni già aperte altrove, che resterebbero valide fino alla loro
    scadenza naturale. È il caso che conta davvero — chi cambia password
    di solito lo fa perché sospetta che qualcuno sia entrato. Legando la
    sessione a questa impronta, il cookie smette di funzionare
    esattamente quando l'hash cambia: al cambio password (`web/account.py`)
    e a un reset fatto a mano sul database."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def crea_sessione(utente_id: int, impronta: str = "",
                  durata_secondi: int | None = None) -> str:
    """`impronta` è quella di `impronta_password` sull'hash in vigore al
    momento del login: `web/auth_web.py` la riconfronta a ogni richiesta.

    `durata_secondi` esiste soprattutto per i test (una sessione già
    scaduta si crea passando un valore negativo): il codice di produzione
    usa sempre il default, `SESSIONE_DURATA_ORE`."""
    durata = durata_secondi if durata_secondi is not None else C.SESSIONE_DURATA_ORE * 3600
    scadenza = int(time.time()) + durata
    payload = json.dumps({"u": int(utente_id), "s": scadenza, "p": impronta},
                         separators=(",", ":")).encode("utf-8")
    firma = hmac.new(_chiave_sessione(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(firma)}"


def leggi_sessione(token: str | None) -> int | None:
    """L'id utente contenuto nel token, o None se manca, è scaduto o è
    stato alterato. Non solleva mai eccezioni: un cookie malformato deve
    trattarsi come «non autenticato», non come un errore del server."""
    dati = leggi_sessione_completa(token)
    return dati["u"] if dati else None


def leggi_sessione_completa(token: str | None) -> dict | None:
    """Come `leggi_sessione`, ma torna anche l'impronta della password
    (`{"u": id, "p": impronta}`), che il chiamante deve confrontare con
    quella dell'hash attuale — vedi `impronta_password`."""
    if not token or "." not in token:
        return None
    grezzo_payload, grezza_firma = token.rsplit(".", 1)
    try:
        payload = _unb64(grezzo_payload)
        firma = _unb64(grezza_firma)
    except Exception:
        return None
    firma_attesa = hmac.new(_chiave_sessione(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(firma, firma_attesa):
        return None
    try:
        dati = json.loads(payload)
    except Exception:
        return None
    if not isinstance(dati, dict):
        return None
    try:
        scadenza = int(dati.get("s", 0))
        utente_id = int(dati.get("u"))
    except (TypeError, ValueError):
        return None
    if scadenza < int(time.time()):
        return None
    impronta = dati.get("p")
    return {"u": utente_id, "p": impronta if isinstance(impronta, str) else ""}


# ----------------------------------------------------------------------
# CSRF — doppio invio (cookie + campo nascosto), nessuno stato server
# ----------------------------------------------------------------------
def nuovo_token_csrf() -> str:
    return secrets.token_urlsafe(32)


def csrf_valido(dal_cookie: str | None, dal_modulo: str | None) -> bool:
    if not dal_cookie or not dal_modulo:
        return False
    return hmac.compare_digest(dal_cookie, dal_modulo)


# ----------------------------------------------------------------------
# Token di approvazione (email di richiesta accesso)
# ----------------------------------------------------------------------
def nuovo_token_richiesta() -> tuple[str, str]:
    """(token in chiaro da mettere nel link, hash da salvare nel database)."""
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_richiesta_valido(token: str | None, token_hash: str) -> bool:
    if not token:
        return False
    calcolato = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(calcolato, token_hash)
