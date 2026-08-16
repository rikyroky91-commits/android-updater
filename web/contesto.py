"""Template Jinja2 e contesto comune a ogni pagina — condiviso da
`web/main.py` e `web/account.py`.

Vive in un file a parte per un motivo solo: `web/account.py` (login,
registrazione, approvazioni) deve poter renderizzare pagine con la stessa
testata di tutte le altre senza importare `web/main.py`, che a sua volta
include le rotte di `account.py` — un'importazione circolare altrimenti
inevitabile.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from core import aiquery, storage
from core.util import fmt_date, fmt_relative, truncate
from . import auth_web

RADICE = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(RADICE / "templates"))
templates.env.globals["fmt_relative"] = fmt_relative
templates.env.globals["truncate"] = truncate
templates.env.globals["fmt_date"] = fmt_date


def rendi(request: Request, pagina: str, contesto: dict):
    """UNA SOLA FIRMA PER TUTTE LE PAGINE — vedi la nota originale in
    main.py sul perché FastAPI vuole `(request, pagina, contesto)`."""
    return templates.TemplateResponse(request, pagina, contesto)


def contesto(request: Request, **extra) -> dict:
    """Quello che serve a OGNI pagina: testata, stato fonti, ricerca, chi
    è collegato adesso (per la voce Accedi/Esci della navigazione)."""
    stati = storage.get_source_status()
    base = {
        "titolo_sito": "Mobile Update Tracker",
        "sottotitolo": "Quale aggiornamento è arrivato, su quale modello, quando.",
        "fonti_ok": sum(1 for s in stati if s.get("ok")),
        "fonti_totali": len(stati),
        "ai_attiva": aiquery.disponibile(),
        "ai_verifica_attiva": bool(
            aiquery.fornitore() and aiquery.fornitore()[0] == "Gemini"),
        "query": "",
        "attiva": "",
        "verifica_ai": None,
        "utente": auth_web.utente_da_richiesta(request),
    }
    base.update(extra)
    return base
