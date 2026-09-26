"""Traduzione in italiano di titoli e riassunti delle novità, con Gemini.

## Perché e come (26/09/2026, richiesta dell'utente: «tutte le notizie
## devono avere una traduzione in italiano»)

Le fonti scrivono quasi tutte in inglese — GSMArena, PiunikaWeb,
SamMobile, i changelog di Nothing — e la pagina Novità è in italiano.

* **Una volta sola per voce.** La traduzione si salva nella tabella
  `traduzioni`, separata da `updates`: non cambia lo schema dell'archivio
  e viaggia col backup come tutto il resto.
* **A lotti di 20**, in una chiamata sola che risponde in JSON: 700 voci
  sono una trentina di chiamate, dentro la quota gratuita di Gemini.
* **Dopo ogni scansione**, in sottofondo, dalla più recente: la pagina si
  traduce subito dove la si guarda, poi il resto.
* **Nomi di modello, build, versioni e marche restano come sono**: sono
  dati da copiare e confrontare, non testo da rendere in italiano.

Senza chiave Gemini non succede niente: la pagina mostra l'originale,
come prima. Un'istanza in sola lettura (`BACKUP_SOLO_LETTURA`, Render)
non traduce: perderebbe il lavoro al primo riavvio.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import aiquery, backup, storage
from . import config as C

PER_LOTTO = 20
MAX_LOTTI_PER_GIRO = 12
PAUSA_FRA_LOTTI = 5          # secondi: la quota gratuita conta le chiamate al minuto
GIORNI = 90
_TIMEOUT = 60

_ISTRUZIONI = (
    "Traduci in italiano titoli e riassunti di notizie su aggiornamenti "
    "software di smartphone. Regole: italiano naturale e conciso, come una "
    "testata tecnologica italiana; NON tradurre né modificare nomi di "
    "marche e modelli (Galaxy S24, Pixel 9, Redmi Note 14S), nomi di "
    "sistemi (One UI, HyperOS, ColorOS, Nothing OS, Android 16), numeri di "
    "build e versione, codici, sigle; se un testo è già in italiano "
    "restituiscilo com'è. Rispondi SOLO con un array JSON di oggetti "
    '{"id": ..., "titolo": ..., "riassunto": ...}, uno per voce ricevuta, '
    "nello stesso ordine."
)

_lucchetto = threading.Lock()
_stato = {"ultimo_giro": None, "tradotte": 0, "errore": None}


def _assicura_tabella() -> None:
    with storage.transaction() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS traduzioni ("
            " update_id TEXT PRIMARY KEY,"
            " titolo TEXT NOT NULL,"
            " riassunto TEXT,"
            " creata TEXT NOT NULL)"
        )


def attiva() -> bool:
    scelto = aiquery.fornitore()
    return bool(scelto and scelto[0] == "Gemini" and requests is not None
                and not backup.sola_lettura()
                and C.env_bool("TRADUCI_NOTIZIE", True))


def da_tradurre(quante: int) -> list[dict]:
    _assicura_tabella()
    conn = storage.connect()
    righe = conn.execute(
        "SELECT u.id, u.title, u.summary FROM updates u"
        " LEFT JOIN traduzioni t ON t.update_id = u.id"
        " WHERE t.update_id IS NULL AND u.is_relevant = 1"
        " AND u.firmware_kind IN ('current', 'reported')"
        " AND COALESCE(u.published, u.first_seen) >= datetime('now', ?)"
        " ORDER BY COALESCE(u.published, u.first_seen) DESC LIMIT ?",
        (f"-{GIORNI} days", int(quante)),
    ).fetchall()
    return [{"id": r["id"], "titolo": r["title"] or "",
             "riassunto": (r["summary"] or "")[:600]} for r in righe]


def mappa(ids: list[str]) -> dict[str, dict]:
    """update_id → {"titolo", "riassunto"} per le voci già tradotte."""
    ids = [i for i in ids if i]
    if not ids:
        return {}
    try:
        _assicura_tabella()
        conn = storage.connect()
        risultato: dict[str, dict] = {}
        for inizio in range(0, len(ids), 500):
            pezzo = ids[inizio:inizio + 500]
            for r in conn.execute(
                    f"SELECT update_id, titolo, riassunto FROM traduzioni"
                    f" WHERE update_id IN ({','.join('?' * len(pezzo))})", pezzo):
                risultato[r["update_id"]] = {"titolo": r["titolo"], "riassunto": r["riassunto"] or ""}
        return risultato
    except Exception:  # pragma: no cover - senza tabella si mostra l'originale
        return {}


def _json_dalla_risposta(testo: str):
    testo = (testo or "").strip()
    testo = re.sub(r"^```(?:json)?\s*|\s*```$", "", testo)
    return json.loads(testo)


def _chiama(lotto: list[dict]) -> list[dict]:
    _nome, chiave, _ = aiquery.fornitore()
    ultimo = None
    for modello in aiquery.modelli_da_provare():
        risposta = requests.post(
            aiquery.GEMINI_URL.format(modello=modello),
            headers={"content-type": "application/json", "x-goog-api-key": chiave},
            json={
                "systemInstruction": {"parts": [{"text": _ISTRUZIONI}]},
                "contents": [{"role": "user", "parts": [
                    {"text": json.dumps(lotto, ensure_ascii=False)}]}],
                "generationConfig": {"temperature": 0.2,
                                     "responseMimeType": "application/json"},
            },
            timeout=_TIMEOUT,
        )
        if risposta.status_code in (400, 403, 404, 429, 500, 503):
            ultimo = f"{modello}: HTTP {risposta.status_code}"
            continue
        risposta.raise_for_status()
        pezzi = ((risposta.json().get("candidates") or [{}])[0]
                 .get("content", {}).get("parts") or [])
        dati = _json_dalla_risposta("".join(p.get("text", "") for p in pezzi))
        return dati if isinstance(dati, list) else []
    raise RuntimeError(ultimo or "nessun modello Gemini disponibile")


def _salva(lotto: list[dict], tradotte: list[dict]) -> int:
    validi = {v["id"] for v in lotto}
    ora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    righe = []
    for t in tradotte:
        if not isinstance(t, dict) or t.get("id") not in validi:
            continue
        titolo = " ".join(str(t.get("titolo") or "").split())
        if not titolo:
            continue
        righe.append((t["id"], titolo[:400], " ".join(str(t.get("riassunto") or "").split())[:900], ora))
    if righe:
        with storage.transaction() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO traduzioni (update_id, titolo, riassunto, creata)"
                " VALUES (?, ?, ?, ?)", righe)
    return len(righe)


def traduci_nuove(max_lotti: int = MAX_LOTTI_PER_GIRO) -> int:
    """Traduce fino a `max_lotti` lotti di voci non ancora tradotte."""
    if not attiva() or not _lucchetto.acquire(blocking=False):
        return 0
    fatte = 0
    try:
        for numero in range(max_lotti):
            lotto = da_tradurre(PER_LOTTO)
            if not lotto:
                break
            try:
                salvate = _salva(lotto, _chiama(lotto))
            except Exception as errore:
                _stato["errore"] = str(errore)[:200]
                break
            fatte += salvate
            if salvate == 0:
                break
            if numero + 1 < max_lotti:
                time.sleep(PAUSA_FRA_LOTTI)
        if fatte:
            _stato["errore"] = None
            backup.segna_modificato()
    finally:
        _stato["ultimo_giro"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _stato["tradotte"] += fatte
        _lucchetto.release()
    return fatte


def traduci_in_sottofondo(max_lotti: int = MAX_LOTTI_PER_GIRO) -> None:
    """Dopo una scansione (o all'avvio): non la fa aspettare."""
    if attiva():
        threading.Thread(target=traduci_nuove, kwargs={"max_lotti": max_lotti},
                         name="traduzioni", daemon=True).start()


def stato() -> dict:
    return dict(_stato)
