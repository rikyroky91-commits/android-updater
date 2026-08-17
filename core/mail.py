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
from datetime import datetime, timezone
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


def costruisci_reset(utente: dict, link_reset: str) -> tuple[str, str]:
    """(oggetto, corpo) dell'email di recupero password.

    Dice esplicitamente cosa fare se NON è stato l'utente a chiederlo:
    un messaggio di reset che non lo spiega lascia chi lo riceve col
    dubbio di essere sotto attacco, quando nella quasi totalità dei casi
    è solo qualcuno che ha sbagliato a digitare la propria email."""
    oggetto = "Reimposta la password del parco di test"
    corpo = (
        f"Ciao {utente['username']},\n\n"
        f"qualcuno ha chiesto di reimpostare la password di questo account. "
        f"Apri questo link per sceglierne una nuova:\n"
        f"{link_reset}\n\n"
        f"Il link vale una sola volta e scade tra "
        f"{C.RESET_PASSWORD_SCADENZA_ORE} ore.\n\n"
        f"Se non sei stato tu, puoi ignorare questo messaggio: senza aprire "
        f"il link non cambia nulla, e la password attuale resta valida."
    )
    return oggetto, corpo


def stato() -> str:
    """Riga per la Diagnostica.

    ESISTE PER UN MOTIVO PRECISO, segnalato dall'utente: «non mi arriva
    la mail di richiesta account». Non arrivava perché SMTP non era
    configurato — il che è un modo di funzionare previsto, non un guasto
    (la richiesta resta su `/admin/richieste`) — ma da fuori era
    indistinguibile da un'email persa, da Gmail che rifiuta la password,
    o da un difetto del codice. Senza una riga che lo dica, l'unica via
    per scoprirlo era leggere il codice.
    """
    cfg = C.smtp_config()
    if not cfg:
        return ("non configurato (SMTP_USERNAME / SMTP_PASSWORD assenti su Render): "
                "le richieste di accesso NON arrivano per email, restano su /admin/richieste")
    testo = (f"attivo · da {cfg['mittente']} via {cfg['host']}:{cfg['port']} "
             f"· le richieste vanno a {C.ADMIN_APPROVAL_EMAIL}")
    if _ultimo["ok"] is True:
        testo += f" · ultimo invio riuscito ({_ultimo['quando']}) a {_ultimo['destinatario']}"
    elif _ultimo["ok"] is False:
        testo += (f" · ULTIMO INVIO FALLITO ({_ultimo['quando']}) "
                  f"verso {_ultimo['destinatario']}: {_ultimo['messaggio']}")
    else:
        testo += " · nessun invio tentato da quando il servizio è partito"
    return testo


# L'ESITO DELL'ULTIMO INVIO, che altrimenti non lo sapeva nessuno.
#
# `web/account.py` ignora di proposito il risultato di `invia`: se la
# pagina del recupero password dicesse «invio fallito» per un indirizzo e
# «fatto» per un altro, direbbe anche quali indirizzi hanno un account
# qui dentro. La conseguenza pero' era che un errore VERO — password per
# le app sbagliata, Gmail che rifiuta la connessione — spariva senza
# lasciare traccia da nessuna parte, e da fuori restava solo «non arriva
# la mail». Segnalato due volte, il 16 e il 17/08/2026.
#
# Qui l'esito si conserva e la Diagnostica lo mostra: quella pagina e'
# dietro login, quindi lo legge solo chi amministra il servizio.
_ultimo = {"quando": None, "ok": None, "messaggio": "", "destinatario": ""}


def ultimo_invio() -> dict:
    return dict(_ultimo)


def invia(destinatario: str, oggetto: str, corpo: str) -> tuple[bool, str]:
    """Invia l'email via SMTP. Ritorna sempre (ok, messaggio): mai
    un'eccezione che risale fino alla richiesta HTTP di chi si registra."""
    esito = _invia_davvero(destinatario, oggetto, corpo)
    _ultimo.update({
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": esito[0], "messaggio": esito[1],
        # Il destinatario si conserva per capire QUALE invio e' fallito
        # quando ce ne sono di due tipi (richiesta account, recupero
        # password). Lo legge solo l'amministratore.
        "destinatario": destinatario,
    })
    return esito


def _invia_davvero(destinatario: str, oggetto: str, corpo: str) -> tuple[bool, str]:
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
