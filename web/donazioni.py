"""Le donazioni libere di Page Brawl, via Ko-fi (16/10/2026).

Riccardo: «un sistema di donazione libero a cui può essere legata la possibilità di
mandare un messaggio e chiedere una feature o un personaggio aggiuntivo»; solo
nell'estensione del browser. L'estensione apre la pagina Ko-fi (`url_donazione` in
`estensione/premium.json`): lì si sceglie l'importo e si scrive il messaggio. Ko-fi
manda poi la donazione qui (`POST /api/kofi`), e i messaggi si leggono in
`/admin/donazioni`, riservata agli amministratori.

Il webhook di Ko-fi è un POST `application/x-www-form-urlencoded` con un solo campo,
`data`, che contiene il JSON della donazione (`verification_token`, `type`,
`from_name`, `message`, `amount`, `currency`, `is_public`, `kofi_transaction_id`,
`email` e altro). Formato preso il 16/10 da esempi pubblicati da terzi, non dalla
documentazione di Ko-fi: il tasto «Send Test» del pannello Ko-fi lo conferma.
Ko-fi ripete il webhook se non riceve un 200: la stessa transazione si salva una volta.
"""
import hmac
import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from core import auth, storage
from core import config as C
from . import auth_web
from .contesto import contesto, rendi

router = APIRouter()

# Quello che si tiene di ogni donazione, tagliato a misura: un messaggio Ko-fi è
# breve, ma qui non deve entrare un romanzo.
_MAX_NOME, _MAX_MESSAGGIO, _MAX_CORPO = 80, 1000, 20_000
_TIPI = {"Donation", "Subscription", "Commission", "Shop Order"}


def _testo(valore, lunghezza: int) -> str:
    testo = " ".join(str(valore or "").split())
    return "".join(c for c in testo if ord(c) >= 32)[:lunghezza]


@router.post("/api/kofi")
async def webhook_kofi(request: Request):
    atteso = C.KOFI_VERIFICATION_TOKEN
    if not atteso:
        return JSONResponse({"errore": "donazioni non configurate"}, status_code=503)
    try:
        if int(request.headers.get("content-length") or 0) > _MAX_CORPO:
            return JSONResponse({"errore": "troppo lungo"}, status_code=413)
        modulo = await request.form()
        dati = json.loads(str(modulo.get("data") or ""))
    except Exception:
        return JSONResponse({"errore": "formato"}, status_code=400)
    if not isinstance(dati, dict):
        return JSONResponse({"errore": "formato"}, status_code=400)
    if not hmac.compare_digest(str(dati.get("verification_token") or ""), atteso):
        return JSONResponse({"errore": "token"}, status_code=403)
    kofi_id = _testo(dati.get("kofi_transaction_id") or dati.get("message_id"), 120)
    tipo = str(dati.get("type") or "")
    if not kofi_id or tipo not in _TIPI:
        # (un evento che non conosciamo: risposto 200, sennò Ko-fi riprova all'infinito)
        return JSONResponse({"ok": True, "salvata": False})
    nuova = storage.salva_donazione(
        kofi_id, tipo,
        _testo(dati.get("from_name"), _MAX_NOME),
        _testo(dati.get("message"), _MAX_MESSAGGIO),
        _testo(dati.get("amount"), 20),
        _testo(dati.get("currency"), 8),
        bool(dati.get("is_public")),
    )
    return JSONResponse({"ok": True, "salvata": nuova})


def _accesso(request):
    utente = auth_web.utente_da_richiesta(request)
    if not utente:
        return RedirectResponse("/login?next=/admin/donazioni", status_code=303)
    if not auth_web.richiede_admin(utente):
        return Response("Accesso riservato agli amministratori", status_code=403)


@router.get("/admin/donazioni")
def elenco_donazioni(request: Request):
    negato = _accesso(request)
    if negato is not None:
        return negato
    csrf = auth.nuovo_token_csrf()
    voci = storage.donazioni()
    risposta = rendi(request, "admin_donazioni.html", contesto(request,
        voci=voci, da_leggere=sum(1 for v in voci if not v["letta"]),
        configurate=bool(C.KOFI_VERIFICATION_TOKEN), csrf=csrf))
    from .account import _imposta_cookie_csrf
    return _imposta_cookie_csrf(risposta, csrf)


@router.post("/admin/donazioni/{id_donazione}/{azione}")
def segna_donazione(request: Request, id_donazione: int, azione: str, csrf: str = Form("")):
    negato = _accesso(request)
    if negato is not None:
        return negato
    if not auth_web.csrf_valido_per(request, csrf):
        return Response("Modulo scaduto: ricarica la pagina", status_code=403)
    if azione in ("letta", "da-leggere"):
        storage.segna_donazione(id_donazione, azione == "letta")
    return RedirectResponse("/admin/donazioni", status_code=303)
