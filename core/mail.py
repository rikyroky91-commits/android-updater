"""Invio della richiesta di approvazione account — l'unica email del sito.

Il progetto non aveva mai mandato una email prima d'ora: le notifiche
sono sempre state su Telegram (`core/notify.py`). Il parco di test
introduce un caso diverso — una decisione che una persona sola deve
prendere («questo account entra o no») — e va raggiunta anche se quella
persona non ha Telegram aperto in quel momento.

Stessa struttura di `notify.py`: costruzione del testo separata
dall'invio, così il contenuto si collauda senza toccare la rete, e
l'esito dell'invio torna a chi chiama invece di sparire in un log — un
errore SMTP inghiottito in silenzio è esattamente il tipo di guasto
descritto per Telegram («la notifica non partiva e nessuno se ne
accorgeva»).
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from . import config as C


def costruisci_richiesta(utente: dict, link_approvazione: str) -> tuple[str, str]:
    """(oggetto, corpo) dell'email mandata all'amministratore quando
    qualcuno chiede un account per il parco di test."""
    oggetto = f"Richiesta di accesso al parco di test — {utente['username']}"
    corpo = (
        f"{utente['username']} ({utente['email']}) ha chiesto un account "
        f"per il parco di test.\n\n"
        f"Apri questo link per approvare o rifiutare la richiesta:\n"
        f"{link_approvazione}\n\n"
        f"Il link si può usare una sola volta e scade tra "
        f"{C.RICHIESTA_ACCESSO_SCADENZA_GIORNI} giorni. Se scade o è già "
        f"stato usato, la richiesta resta comunque visibile accedendo con "
        f"l'account amministratore e aprendo /admin/richieste."
    )
    return oggetto, corpo


def invia(destinatario: str, oggetto: str, corpo: str) -> tuple[bool, str]:
    """Invia l'email via SMTP. Ritorna sempre (ok, messaggio): mai
    un'eccezione che risale fino alla richiesta HTTP di chi si registra."""
    cfg = C.smtp_config()
    if not cfg:
        return False, "SMTP non configurato (SMTP_USERNAME / SMTP_PASSWORD mancanti su Render)"
    messaggio = EmailMessage()
    messaggio["Subject"] = oggetto
    messaggio["From"] = cfg["mittente"]
    messaggio["To"] = destinatario
    messaggio.set_content(corpo)
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=C.HTTP_TIMEOUT) as server:
            server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.send_message(messaggio)
        return True, ""
    except Exception as errore:
        return False, str(errore)
