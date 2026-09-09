"""Revisione dei TAC mancanti riservata agli amministratori."""
import re
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response
from core import auth, imeicheck, tac_missing
from . import auth_web
from .contesto import contesto, rendi

router = APIRouter()


def accesso(request):
    utente = auth_web.utente_da_richiesta(request)
    if not utente:
        return RedirectResponse("/login?next=/admin/tac", status_code=303)
    if not auth_web.richiede_admin(utente):
        return Response("Accesso riservato agli amministratori", status_code=403)


@router.get("/admin/tac")
def elenco(request: Request):
    negato = accesso(request)
    if negato is not None:
        return negato
    csrf = auth.nuovo_token_csrf()
    risposta = rendi(request, "admin_tac.html", contesto(request,
        voci=tac_missing.elenco(), motivi=tac_missing.MOTIVI,
        csrf=csrf))
    from .account import _imposta_cookie_csrf
    return _imposta_cookie_csrf(risposta, csrf)


@router.post("/admin/tac/correggi")
def correggi(request: Request, tac: str = Form(...), marca: str = Form(...),
             modello: str = Form(...), csrf: str = Form("")):
    negato = accesso(request)
    if negato is not None:
        return negato
    if not auth_web.csrf_valido_per(request, csrf):
        return Response("Modulo scaduto: ricarica la pagina", status_code=403)
    if (not re.fullmatch(r"[0-9]{8}", tac) or not marca.strip() or not modello.strip()
            or len(marca) > 80 or len(modello) > 160
            or not imeicheck.aggiungi_tac(tac, marca, modello)):
        return Response("TAC, marca e modello non validi", status_code=400)
    tac_missing.risolto(tac)
    imeicheck.dimentica_tac_assente(tac)
    from .main import RICERCHE, _backup_subito
    RICERCHE.svuota()
    _backup_subito()
    return RedirectResponse("/admin/tac", status_code=303)
