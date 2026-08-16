"""Lettura della sessione dalla richiesta HTTP e guardie di accesso.

`core/auth.py` sa firmare e verificare un token; questo modulo lo collega
a una `Request` di FastAPI — nome del cookie, lookup dell'utente,
controllo dello stato account. Resta un file a parte (non dentro
`web/account.py`) perché `web/contesto.py` lo usa per decidere cosa
mostrare in testata su OGNI pagina, non solo su quelle di login: è il
punto più in basso della catena di importazioni fra i moduli web.
"""
from __future__ import annotations

import hmac

from fastapi import Request

from core import auth, storage

COOKIE_SESSIONE = "sessione"
COOKIE_CSRF = "csrf_token"


def utente_da_richiesta(request: Request) -> dict | None:
    """L'utente collegato, solo se la sessione è valida E l'account è
    tuttora approvato E la password non è cambiata da quando la sessione
    è nata — tutte e tre le condizioni si rileggono dal database a ogni
    richiesta, non solo al login: una revoca (`imposta_stato_utente`) o un
    cambio password devono avere effetto sulle sessioni GIÀ aperte, non
    solo su quelle future. Vedi `core/auth.py::impronta_password`."""
    token = request.cookies.get(COOKIE_SESSIONE)
    sessione = auth.leggi_sessione_completa(token)
    if sessione is None:
        return None
    utente = storage.get_utente(sessione["u"])
    if not utente or utente["stato"] != storage.STATO_APPROVATO:
        return None
    if not hmac.compare_digest(sessione["p"],
                               auth.impronta_password(utente["password_hash"])):
        return None
    return utente


def richiede_admin(utente: dict | None) -> bool:
    return bool(utente and utente.get("admin"))


def csrf_valido_per(request: Request, valore_modulo: str | None) -> bool:
    return auth.csrf_valido(request.cookies.get(COOKIE_CSRF), valore_modulo)
