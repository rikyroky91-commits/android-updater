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

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

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
    if C.env("BREVO_API_KEY"):
        mittente = C.env("BREVO_MITTENTE") or C.env("SMTP_USERNAME") or "mittente non impostato"
        testo = (f"attivo via HTTPS (Brevo) · da {mittente} "
                 f"· le richieste vanno a {C.ADMIN_APPROVAL_EMAIL}")
    else:
        cfg = C.smtp_config()
        if not cfg:
            return ("non configurato: le richieste di accesso NON arrivano per "
                    "email, restano su /admin/richieste. Su Render gratuito le "
                    "porte SMTP sono bloccate — imposta BREVO_API_KEY e "
                    "BREVO_MITTENTE, che passano da HTTPS")
        testo = (f"attivo via SMTP · da {cfg['mittente']} via {cfg['host']}:{cfg['port']} "
                 f"· le richieste vanno a {C.ADMIN_APPROVAL_EMAIL}"
                 # Su Render gratuito questa via non funziona, e la riga
                 # diceva «attivo» anche mentre ogni invio falliva.
                 " · ATTENZIONE: su Render gratuito le porte SMTP sono"
                 " bloccate, l'invio fallirà con «Network is unreachable»")
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
    # PRIMA LA VIA HTTPS, POI SMTP. Vedi il docstring del modulo: su
    # Render gratuito le porte SMTP sono chiuse, e l'unica strada che
    # esce e' la 443.
    if C.env("BREVO_API_KEY"):
        return _invia_via_brevo(destinatario, oggetto, corpo)
    return _invia_via_smtp(destinatario, oggetto, corpo)


def _invia_via_brevo(destinatario: str, oggetto: str, corpo: str) -> tuple[bool, str]:
    """Invio attraverso l'API HTTP di Brevo, sulla porta 443.

    PERCHE' NON BASTA SMTP. Dal 26/09/2025 Render blocca il traffico in
    uscita verso le porte SMTP (25, 465, 587) sui servizi gratuiti: la
    connessione non parte proprio, e l'errore che arriva e'
    «[Errno 101] Network is unreachable» — che sembra un guasto di rete
    generico e manda a cercare il problema nelle credenziali, dove non
    e'. Verificato dal vivo il 17/08/2026 con SMTP configurato
    correttamente.
    Le due vie d'uscita sono passare a un piano a pagamento oppure usare
    un servizio che accetti le email su HTTPS. Questa e' la seconda.

    PERCHE' BREVO fra i tanti: si puo' spedire validando un singolo
    indirizzo mittente (un clic su un link ricevuto per email), senza
    possedere un dominio ne' inserire una carta — che sono i due
    ostacoli degli altri servizi transazionali per chi ha un progetto
    personale.

    SMTP resta la prima scelta ovunque non sia bloccato: `_invia_davvero`
    usa questa via solo se la chiave c'e'.
    """
    if requests is None:  # pragma: no cover - dipendenze non installate
        return False, "libreria 'requests' non disponibile"
    mittente = C.env("BREVO_MITTENTE") or C.env("SMTP_USERNAME")
    if not mittente:
        return False, ("BREVO_API_KEY impostata ma manca l'indirizzo mittente: "
                       "imposta BREVO_MITTENTE con l'indirizzo che hai validato "
                       "su Brevo")
    try:
        risposta = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": C.env("BREVO_API_KEY"),
                     "content-type": "application/json",
                     "accept": "application/json"},
            json={
                "sender": {"email": mittente, "name": "Mobile Update Tracker"},
                "to": [{"email": destinatario}],
                "subject": oggetto,
                "textContent": corpo,
            },
            timeout=C.HTTP_TIMEOUT + 15,
        )
    except Exception as errore:
        return False, f"connessione a Brevo fallita: {errore}"
    if risposta.status_code in (200, 201, 202):
        return True, ""
    # Il corpo della risposta contiene il motivo vero (mittente non
    # validato, chiave revocata, quota finita): senza, resterebbe solo un
    # numero.
    return False, f"Brevo ha risposto {risposta.status_code}: {risposta.text[:200]}"


def _invia_via_smtp(destinatario: str, oggetto: str, corpo: str) -> tuple[bool, str]:
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
