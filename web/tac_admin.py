"""Revisione dei TAC mancanti riservata agli amministratori."""
import re
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response
from core import auth, proposte, tac_missing
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
        proposte=proposte.elenco(), tipi_proposta=proposte.TIPI,
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
            or len(marca) > 80 or len(modello) > 160):
        return Response("TAC, marca e modello non validi", status_code=400)
    from .main import applica_correzione_tac
    if not applica_correzione_tac(tac, marca, modello):
        return Response("TAC, marca e modello non validi", status_code=400)
    tac_missing.risolto(tac)
    return RedirectResponse("/admin/tac", status_code=303)


@router.post("/admin/proposte/{id_proposta}/{azione}")
def decidi_proposta(request: Request, id_proposta: int, azione: str, csrf: str = Form("")):
    """Approva o scarta una correzione proposta da chi non ha un account
    (vedi `core/proposte.py`). Approvare fa esattamente quello che avrebbe
    fatto il salvataggio diretto: stessa funzione, non una copia."""
    negato = accesso(request)
    if negato is not None:
        return negato
    if not auth_web.csrf_valido_per(request, csrf):
        return Response("Modulo scaduto: ricarica la pagina", status_code=403)
    proposta = proposte.prendi(id_proposta)
    if proposta is None or azione not in ("approva", "scarta"):
        return RedirectResponse("/admin/tac", status_code=303)
    if azione == "scarta":
        proposte.scarta(id_proposta)
        return RedirectResponse("/admin/tac", status_code=303)
    from .main import applica_correzione_nome, applica_correzione_tac
    if proposta["tipo"] == "tac":
        if not applica_correzione_tac(proposta["chiave"], proposta["marca"], proposta["valore"]):
            return Response("Proposta non applicabile", status_code=400)
        tac_missing.risolto(proposta["chiave"])
    else:
        applica_correzione_nome(proposta["chiave"], proposta["valore"])
    return RedirectResponse("/admin/tac", status_code=303)
