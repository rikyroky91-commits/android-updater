"""Registro aggregato dei TAC da verificare, senza IMEI o dati personali."""
import re
from datetime import datetime, timedelta, timezone

from . import storage

MOTIVI = {
    "tac_non_trovato": "TAC non trovato nei cataloghi disponibili",
    "servizio_indisponibile": "Servizio esterno indisponibile",
    "nome_da_verificare": "Nome o variante da verificare",
    "in_corso": "Ricerca esterna in corso",
}


def registra(tac, motivo, conteggia=True):
    if not re.fullmatch(r"[0-9]{8}", str(tac or "")) or motivo not in MOTIVI:
        return
    adesso = datetime.now(timezone.utc)
    quando = adesso.isoformat(timespec="microseconds")
    with storage.transaction() as conn:
        conn.execute("DELETE FROM tac_da_verificare WHERE ultima < ?",
                     ((adesso - timedelta(days=90)).isoformat(),))
        if conteggia:
            conn.execute("INSERT INTO tac_da_verificare VALUES (?, 1, ?, ?, ?) "
                         "ON CONFLICT(tac) DO UPDATE SET conteggio=conteggio+1, "
                         "ultima=excluded.ultima, motivo=excluded.motivo", (tac, quando, quando, motivo))
        else:
            # Il secondo tempo aggiorna il motivo, non conta una seconda visita.
            conn.execute("UPDATE tac_da_verificare SET ultima=?, motivo=? WHERE tac=?",
                         (quando, motivo, tac))
        conn.execute("DELETE FROM tac_da_verificare WHERE tac IN "
                     "(SELECT tac FROM tac_da_verificare ORDER BY ultima DESC LIMIT -1 OFFSET 1000)")


def risolto(tac):
    if re.fullmatch(r"[0-9]{8}", str(tac or "")):
        with storage.transaction() as conn:
            conn.execute("DELETE FROM tac_da_verificare WHERE tac=?", (tac,))


def elenco():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    return [dict(r) for r in storage.connect().execute(
        "SELECT * FROM tac_da_verificare WHERE ultima>=? ORDER BY conteggio DESC, ultima DESC LIMIT 1000", (cutoff,))]
