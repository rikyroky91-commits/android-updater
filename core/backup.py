"""Persistenza del database fra un riavvio e l'altro.

IL PROBLEMA. Su Streamlit Cloud il disco è effimero: a ogni riavvio, o
dopo una sospensione per inattività, il file del database sparisce e
l'archivio riparte da zero. Per un tracker che serve a rispondere «cosa è
cambiato dall'ultima volta», perdere lo storico è la cosa peggiore che
possa succedere — ed è successo davvero, con il catalogo tornato a zero
dispositivi da un'apertura all'altra.

LA SCELTA. L'alternativa più ovvia sarebbe passare a un database gestito
(Postgres). È però una riscrittura di tutte le query — 41 segnaposto,
espressioni di data specifiche di SQLite, `INSERT OR REPLACE`,
`AUTOINCREMENT` — su codice che oggi funziona e che 193 test verificano.
Molto lavoro, molte occasioni di rompere qualcosa.

Qui si fa invece una cosa più semplice e reversibile: il database resta
SQLite, esattamente com'è, e il FILE viene sincronizzato su un archivio
esterno. All'avvio si scarica l'ultimo salvataggio, a fine scansione si
ricarica. Nessuna query cambia, nessun test cambia, e se un giorno si
volesse davvero Postgres questa strada non lo impedisce.

BACKEND SUPPORTATI, in ordine di preferenza:
  1. Gist GitHub privato (basta un token, nessun servizio da attivare)
  2. Qualsiasi URL HTTP con PUT/GET (S3, Backblaze, WebDAV…)
  3. Nessuno: l'app funziona lo stesso, ma senza memoria fra i riavvii

Nulla di tutto questo è obbligatorio: senza configurazione il modulo resta
inerte e l'applicazione si comporta come prima.
"""
from __future__ import annotations

import base64
import gzip
import os
import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import config as C

_GIST_FILENAME = "tracker-db.sqlite.gz"
_lock = threading.Lock()
_stato = {"ultimo_esito": "non configurato", "ultimo_salvataggio": None,
          "ultimo_ripristino": None, "byte": 0}


def stato() -> dict:
    """Diagnostica leggibile, per la scheda Diagnostica."""
    return dict(_stato)


def configurato() -> bool:
    return bool(C.env("BACKUP_GIST_ID") and C.env("BACKUP_GITHUB_TOKEN")) or bool(
        C.env("BACKUP_URL")
    )


def _headers_github() -> dict:
    return {
        "Authorization": f"Bearer {C.env('BACKUP_GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "User-Agent": C.USER_AGENT,
    }


# ----------------------------------------------------------------------
# Salvataggio
# ----------------------------------------------------------------------
def salva() -> tuple[bool, str]:
    """Carica il database sull'archivio esterno.

    Il file viene compresso: un database di qualche megabyte scende a
    poche centinaia di kilobyte, il che conta perché i Gist hanno un
    limite di dimensione e la banda non è gratuita.
    """
    if not configurato():
        return False, "nessun archivio configurato"
    if requests is None:  # pragma: no cover
        return False, "libreria 'requests' non disponibile"

    percorso = C.DB_PATH
    if not os.path.exists(percorso):
        return False, "database non ancora creato"

    with _lock:
        try:
            with open(percorso, "rb") as f:
                grezzo = f.read()
        except OSError as exc:
            return False, f"lettura del database non riuscita: {exc}"

        compresso = gzip.compress(grezzo, compresslevel=6)
        _stato["byte"] = len(compresso)

        if C.env("BACKUP_GIST_ID"):
            ok, messaggio = _salva_su_gist(compresso)
        else:
            ok, messaggio = _salva_su_url(compresso)

        _stato["ultimo_esito"] = messaggio
        if ok:
            _stato["ultimo_salvataggio"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return ok, messaggio


def _salva_su_gist(dati: bytes) -> tuple[bool, str]:
    # I Gist accettano solo testo: il binario compresso viaggia in base64.
    contenuto = base64.b64encode(dati).decode("ascii")
    if len(contenuto) > 50 * 1024 * 1024:
        return False, f"database troppo grande per un Gist ({len(contenuto) // 1024 // 1024} MB)"
    try:
        risposta = requests.patch(
            f"https://api.github.com/gists/{C.env('BACKUP_GIST_ID')}",
            headers=_headers_github(),
            json={"files": {_GIST_FILENAME: {"content": contenuto}}},
            timeout=C.HTTP_TIMEOUT + 45,
        )
    except Exception as exc:
        return False, f"connessione fallita: {exc}"
    if risposta.status_code != 200:
        return False, f"GitHub ha risposto {risposta.status_code}: {risposta.text[:120]}"
    return True, f"salvato ({len(dati) // 1024} KB compressi)"


def _salva_su_url(dati: bytes) -> tuple[bool, str]:
    try:
        risposta = requests.put(
            C.env("BACKUP_URL"), data=dati,
            headers={"Content-Type": "application/octet-stream",
                     "User-Agent": C.USER_AGENT},
            timeout=C.HTTP_TIMEOUT + 45,
        )
    except Exception as exc:
        return False, f"connessione fallita: {exc}"
    if risposta.status_code not in (200, 201, 204):
        return False, f"l'archivio ha risposto {risposta.status_code}"
    return True, f"salvato ({len(dati) // 1024} KB compressi)"


# ----------------------------------------------------------------------
# Ripristino
# ----------------------------------------------------------------------
def ripristina(solo_se_mancante: bool = True) -> tuple[bool, str]:
    """Scarica il database dall'archivio esterno.

    `solo_se_mancante` protegge dal caso peggiore: sovrascrivere un
    database locale già popolato con una copia più vecchia. All'avvio il
    file non esiste (disco effimero) e il ripristino è quello che serve;
    in ogni altra situazione si preferisce non toccare nulla.
    """
    if not configurato():
        return False, "nessun archivio configurato"
    if requests is None:  # pragma: no cover
        return False, "libreria 'requests' non disponibile"

    percorso = C.DB_PATH
    if solo_se_mancante and os.path.exists(percorso) and os.path.getsize(percorso) > 4096:
        return False, "database locale già presente: ripristino non necessario"

    with _lock:
        if C.env("BACKUP_GIST_ID"):
            dati, messaggio = _leggi_da_gist()
        else:
            dati, messaggio = _leggi_da_url()

        if dati is None:
            _stato["ultimo_esito"] = messaggio
            return False, messaggio

        try:
            grezzo = gzip.decompress(dati)
        except Exception as exc:
            messaggio = f"archivio scaricato ma non decomprimibile: {exc}"
            _stato["ultimo_esito"] = messaggio
            return False, messaggio

        # Scrittura atomica: un'interruzione a metà lascerebbe un database
        # corrotto, che è peggio di un database assente.
        temporaneo = percorso + ".tmp"
        try:
            with open(temporaneo, "wb") as f:
                f.write(grezzo)
            os.replace(temporaneo, percorso)
        except OSError as exc:
            return False, f"scrittura del database non riuscita: {exc}"
        finally:
            if os.path.exists(temporaneo):
                os.remove(temporaneo)

        messaggio = f"ripristinato ({len(grezzo) // 1024} KB)"
        _stato["ultimo_esito"] = messaggio
        _stato["ultimo_ripristino"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return True, messaggio


def _leggi_da_gist() -> tuple[bytes | None, str]:
    try:
        risposta = requests.get(
            f"https://api.github.com/gists/{C.env('BACKUP_GIST_ID')}",
            headers=_headers_github(), timeout=C.HTTP_TIMEOUT + 30,
        )
    except Exception as exc:
        return None, f"connessione fallita: {exc}"
    if risposta.status_code != 200:
        return None, f"GitHub ha risposto {risposta.status_code}"
    try:
        file_gist = risposta.json()["files"].get(_GIST_FILENAME)
    except (ValueError, KeyError, AttributeError):
        return None, "risposta di GitHub in forma inattesa"
    if not file_gist:
        return None, "nessun salvataggio presente nel Gist"

    contenuto = file_gist.get("content")
    # I Gist grandi arrivano troncati: in quel caso il contenuto va preso
    # dal raw_url, altrimenti si scriverebbe un database incompleto.
    if file_gist.get("truncated") and file_gist.get("raw_url"):
        try:
            grezzo = requests.get(file_gist["raw_url"], timeout=C.HTTP_TIMEOUT + 45)
            contenuto = grezzo.text if grezzo.status_code == 200 else contenuto
        except Exception:
            pass
    if not contenuto:
        return None, "salvataggio vuoto"
    try:
        return base64.b64decode(contenuto), "ok"
    except Exception as exc:
        return None, f"contenuto non decodificabile: {exc}"


def _leggi_da_url() -> tuple[bytes | None, str]:
    try:
        risposta = requests.get(C.env("BACKUP_URL"), timeout=C.HTTP_TIMEOUT + 45)
    except Exception as exc:
        return None, f"connessione fallita: {exc}"
    if risposta.status_code == 404:
        return None, "nessun salvataggio presente"
    if risposta.status_code != 200:
        return None, f"l'archivio ha risposto {risposta.status_code}"
    return risposta.content, "ok"


# ----------------------------------------------------------------------
# Salvataggio periodico
# ----------------------------------------------------------------------
# None = non si è ancora salvato in questa esecuzione. Va distinto da 0.0:
# con un contatore azzerato il primo salvataggio verrebbe scambiato per
# «appena fatto» e saltato, e il primissimo dopo l'avvio non avverrebbe mai.
_ultimo_tentativo: float | None = None


def salva_se_serve(intervallo_minuti: int | None = None) -> None:
    """Salva, ma non più spesso del necessario.

    Chiamata a fine di ogni scansione: senza un intervallo minimo si
    caricherebbe l'intero database a ogni giro, sprecando banda e
    consumando il limite di chiamate dell'archivio.
    """
    global _ultimo_tentativo
    if not configurato():
        return
    minuti = intervallo_minuti if intervallo_minuti is not None else C.BACKUP_EVERY_MINUTES
    if _ultimo_tentativo is not None and (time.monotonic() - _ultimo_tentativo) < minuti * 60:
        return
    _ultimo_tentativo = time.monotonic()
    salva()


# ----------------------------------------------------------------------
# Preparazione assistita
# ----------------------------------------------------------------------
def verifica_token(token: str) -> tuple[bool, str]:
    """Controlla che il token esista e abbia il permesso giusto.

    Vale la pena farlo prima di tentare qualsiasi altra cosa: un token
    senza il permesso «gist» produrrebbe un errore molto più avanti, e
    molto più difficile da ricondurre alla causa.
    """
    if requests is None:  # pragma: no cover
        return False, "libreria 'requests' non disponibile"
    token = (token or "").strip()
    if not token:
        return False, "nessun token indicato"
    try:
        risposta = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": C.USER_AGENT},
            timeout=C.HTTP_TIMEOUT,
        )
    except Exception as exc:
        return False, f"connessione a GitHub fallita: {exc}"
    if risposta.status_code == 401:
        return False, "token non valido o scaduto"
    if risposta.status_code != 200:
        return False, f"GitHub ha risposto {risposta.status_code}"

    # I token classici dichiarano i permessi in un'intestazione; quelli
    # «fine-grained» no, quindi l'assenza non è di per sé un errore.
    ambiti = risposta.headers.get("x-oauth-scopes", "")
    if ambiti and "gist" not in ambiti:
        return False, (
            f"il token non ha il permesso «gist» (permessi attuali: {ambiti or 'nessuno'})"
        )
    try:
        utente = risposta.json().get("login", "")
    except ValueError:
        utente = ""
    return True, f"token valido{f' (utente {utente})' if utente else ''}"


def crea_archivio(token: str) -> tuple[bool, str, str | None]:
    """Crea da zero il Gist privato dove conservare l'archivio.

    Ritorna `(riuscito, messaggio, id_del_gist)`. Serve a togliere di mezzo
    i passaggi manuali: senza questo bisognerebbe creare il Gist a mano,
    copiarne l'identificativo dall'indirizzo e incollarlo altrove — tre
    occasioni di sbagliare per un'operazione che si fa una volta sola.
    """
    if requests is None:  # pragma: no cover
        return False, "libreria 'requests' non disponibile", None
    ok, messaggio = verifica_token(token)
    if not ok:
        return False, messaggio, None

    try:
        risposta = requests.post(
            "https://api.github.com/gists",
            headers={"Authorization": f"Bearer {token.strip()}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": C.USER_AGENT},
            json={
                "description": "Mobile Update Tracker — archivio (non modificare a mano)",
                "public": False,
                "files": {_GIST_FILENAME: {"content": "in attesa del primo salvataggio"}},
            },
            timeout=C.HTTP_TIMEOUT + 15,
        )
    except Exception as exc:
        return False, f"connessione a GitHub fallita: {exc}", None
    if risposta.status_code != 201:
        return False, f"GitHub ha risposto {risposta.status_code}: {risposta.text[:120]}", None
    try:
        identificativo = risposta.json()["id"]
    except (ValueError, KeyError):
        return False, "risposta di GitHub in forma inattesa", None
    return True, "archivio creato", identificativo


def prova_completa(gist_id: str, token: str) -> tuple[bool, str]:
    """Salva e rilegge un dato di prova, per confermare che tutto funzioni.

    Verificare la configurazione con una scrittura vera è l'unico modo per
    sapere che funzionerà davvero quando servirà: un errore di permessi si
    scoprirebbe altrimenti solo al primo riavvio, cioè quando i dati sono
    già andati persi.
    """
    if requests is None:  # pragma: no cover
        return False, "libreria 'requests' non disponibile"
    prova = f"prova-{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    intestazioni = {
        "Authorization": f"Bearer {(token or '').strip()}",
        "Accept": "application/vnd.github+json",
        "User-Agent": C.USER_AGENT,
    }
    try:
        scrittura = requests.patch(
            f"https://api.github.com/gists/{(gist_id or '').strip()}",
            headers=intestazioni,
            json={"files": {"prova-scrittura.txt": {"content": prova}}},
            timeout=C.HTTP_TIMEOUT + 15,
        )
    except Exception as exc:
        return False, f"scrittura non riuscita: {exc}"
    if scrittura.status_code != 200:
        return False, (
            f"scrittura non riuscita ({scrittura.status_code}): "
            "controlla che l'identificativo dell'archivio sia corretto e che il "
            "token abbia il permesso «gist»"
        )

    try:
        lettura = requests.get(
            f"https://api.github.com/gists/{(gist_id or '').strip()}",
            headers=intestazioni, timeout=C.HTTP_TIMEOUT,
        )
        riletto = lettura.json()["files"]["prova-scrittura.txt"]["content"]
    except Exception as exc:
        return False, f"rilettura non riuscita: {exc}"
    if riletto.strip() != prova:
        return False, "il dato riletto non corrisponde a quello scritto"
    return True, "scrittura e rilettura riuscite: l'archivio è pronto"
