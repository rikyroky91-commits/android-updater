"""Correzioni proposte da chi non ha un account, in attesa di verifica.

Un modello salvato per un TAC o un nome scelto per un codice hanno la
precedenza su ogni fonte scaricata: è il loro scopo. Fino al 10/10/2026
chiunque poteva scriverne uno con una POST, e la pagina di ricerca di
tutti cambiava all'istante. Ora chi ha un account approvato continua a
salvare direttamente; chi non ce l'ha lascia una proposta qui, e un
amministratore la approva o la scarta da `/admin/tac`.

Stesse regole di riservatezza di `tac_missing`: si conserva cosa viene
proposto e quante volte, mai chi lo propone (niente IMEI, IP o account).
"""
import re
from datetime import datetime, timedelta, timezone

from . import storage

TIPI = {"tac": "Modello per un TAC", "nome": "Nome commerciale per un codice"}
MASSIMO = 500
GIORNI = 90
_LUNGHEZZE = {"chiave": 40, "marca": 80, "valore": 160}


def _pulisci(tipo, chiave, marca, valore):
    chiave = (chiave or "").strip()
    marca = (marca or "").strip()
    valore = (valore or "").strip()
    if tipo == "tac":
        if not re.fullmatch(r"[0-9]{8}", chiave) or not (marca or valore):
            return None
    elif tipo == "nome":
        chiave = chiave.upper()
        if not chiave:
            return None
        marca = ""
    else:
        return None
    if (len(chiave) > _LUNGHEZZE["chiave"] or len(marca) > _LUNGHEZZE["marca"]
            or len(valore) > _LUNGHEZZE["valore"]):
        return None
    return chiave, marca, valore


def registra(tipo, chiave, marca="", valore="") -> bool:
    """Aggiunge la proposta, o ne conta una in più se è identica a una già
    in coda. Per un nome, `valore` vuoto propone di tornare alla scelta
    automatica. Falso se i dati non sono validi."""
    pulita = _pulisci(tipo, chiave, marca, valore)
    if pulita is None:
        return False
    adesso = datetime.now(timezone.utc)
    quando = adesso.isoformat(timespec="microseconds")
    with storage.transaction() as conn:
        conn.execute("DELETE FROM proposte_correzione WHERE ultima < ?",
                     ((adesso - timedelta(days=GIORNI)).isoformat(),))
        conn.execute(
            "INSERT INTO proposte_correzione (tipo, chiave, marca, valore, prima, ultima) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(tipo, chiave, marca, valore) "
            "DO UPDATE SET conteggio=conteggio+1, ultima=excluded.ultima",
            (tipo, *pulita, quando, quando))
        conn.execute("DELETE FROM proposte_correzione WHERE id IN (SELECT id FROM "
                     "proposte_correzione ORDER BY ultima DESC LIMIT -1 OFFSET ?)", (MASSIMO,))
    return True


def elenco() -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=GIORNI)).isoformat()
    return [dict(r) for r in storage.connect().execute(
        "SELECT * FROM proposte_correzione WHERE ultima >= ? "
        "ORDER BY conteggio DESC, ultima DESC LIMIT ?", (cutoff, MASSIMO))]


def prendi(id_proposta) -> dict | None:
    riga = storage.connect().execute(
        "SELECT * FROM proposte_correzione WHERE id = ?", (id_proposta,)).fetchone()
    return dict(riga) if riga else None


def scarta(id_proposta) -> None:
    with storage.transaction() as conn:
        conn.execute("DELETE FROM proposte_correzione WHERE id = ?", (id_proposta,))


def risolte(tipo, chiave) -> None:
    """Toglie tutte le proposte per quel TAC o codice: una correzione è
    appena stata applicata, e le altre proposte rispondevano alla domanda
    che non è più aperta."""
    if tipo == "nome":
        chiave = (chiave or "").strip().upper()
    with storage.transaction() as conn:
        conn.execute("DELETE FROM proposte_correzione WHERE tipo = ? AND chiave = ?",
                     (tipo, (chiave or "").strip()))
