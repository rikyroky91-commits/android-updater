"""I file allegati alle righe del parco di test.

**IL VINCOLO CHE DECIDE TUTTO.** Il salvataggio esterno
(`core/backup.py`) ricarica ogni volta il file INTERO del database: oggi
5,7 MB compressi, che in base64 diventano circa 7,6 MB per invio. Un
allegato messo dentro il database verrebbe quindi rispedito per intero a
ogni salvataggio, per sempre — dieci foto da 2 MB e il salvataggio
passa da 7,6 MB a una trentina, ogni volta, avvicinandosi al tetto dei
Gist. Il database porta perciò solo i metadati (`allegati_parco` in
`core/storage.py`); qui c'è il contenuto, che si carica UNA VOLTA e poi
sta fermo.

**Dove sta il contenuto.** Nello stesso Gist del salvataggio, come file
separati. Non è una scorciatoia: un Gist tiene più file, la PATCH
dell'API ne tocca solo quelli che nomina, e `backup._leggi_da_gist`
sceglie il proprio per nome invece di prendere il primo. Database e
allegati convivono senza vedersi, e soprattutto **non serve configurare
niente di nuovo**: `BACKUP_GIST_ID` e `BACKUP_GITHUB_TOKEN` sono già
impostati. Un secondo Gist avrebbe voluto dire una variabile in più da
creare a mano su Render, cioè un altro passo in cui sbagliare, in cambio
di nessun vantaggio pratico.

**Il nome del file è l'impronta del contenuto**, non il nome scelto da
chi carica. Due file identici occupano un posto solo, e un nome con
caratteri strani (o uguale a quello del database) non può rompere
l'archivio.

**La copia locale.** Su Render il disco è effimero, quindi la copia in
`/tmp` non è la conservazione: è una cache. Chi scarica un allegato
appena caricato non deve aspettare un giro di rete verso GitHub; dopo un
riavvio la cache è vuota e il primo che lo apre lo riporta giù.

**Cosa NON fa.** Non ridimensiona le immagini e non converte niente:
servirebbe Pillow, una dipendenza nuova e pesante per un piano da
512 MB. Il limite di dimensione è invece un rifiuto dichiarato al
momento del caricamento, che costa zero e si capisce subito.
"""
from __future__ import annotations

import base64
import hashlib
import os
import threading

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from . import config as C
from . import storage

_PREFISSO = "allegato-"
_lock = threading.Lock()

# Tipi accettati: immagini (una foto dello schermo del telefono è il caso
# per cui questa funzione esiste), PDF e testo. Non è una lista di
# sicurezza — il file non viene mai eseguito — ma evita di riempire
# l'archivio di cose che il browser non saprebbe comunque mostrare.
TIPI_AMMESSI = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}


def configurato() -> bool:
    return bool(C.env("BACKUP_GIST_ID") and C.env("BACKUP_GITHUB_TOKEN")) and requests is not None


def _cartella_cache() -> str:
    cartella = os.path.join(
        os.path.dirname(os.path.abspath(C.DB_PATH)) or ".", "allegati")
    os.makedirs(cartella, exist_ok=True)
    return cartella


def _percorso_cache(impronta: str) -> str:
    return os.path.join(_cartella_cache(), impronta)


def _nome_nel_gist(impronta: str) -> str:
    return f"{_PREFISSO}{impronta}"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {C.env('BACKUP_GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "User-Agent": C.USER_AGENT,
    }


def _patch_gist(files: dict) -> tuple[bool, str]:
    """Una PATCH tocca SOLO i file che nomina: il salvataggio del
    database, che sta nello stesso Gist con un altro nome, non si accorge
    di questa chiamata."""
    try:
        risposta = requests.patch(
            f"https://api.github.com/gists/{C.env('BACKUP_GIST_ID')}",
            headers=_headers(), json={"files": files},
            timeout=C.HTTP_TIMEOUT + 45,
        )
    except Exception as exc:
        return False, f"connessione a GitHub fallita: {exc}"
    if risposta.status_code != 200:
        return False, f"GitHub ha risposto {risposta.status_code}: {risposta.text[:120]}"
    return True, ""


def controlla(nome: str, tipo: str, contenuto: bytes) -> str | None:
    """None se il file si può accettare, altrimenti il motivo da mostrare
    a chi ha provato a caricarlo."""
    if not contenuto:
        return "Il file è vuoto."
    massimo = C.ALLEGATI_MAX_MB * 1024 * 1024
    if len(contenuto) > massimo:
        return (f"Il file pesa {len(contenuto) // 1024 // 1024} MB: il limite è "
                f"{C.ALLEGATI_MAX_MB} MB. L'archivio esterno è un Gist, non uno spazio disco.")
    if tipo not in TIPI_AMMESSI:
        ammessi = ", ".join(sorted(set(TIPI_AMMESSI.values())))
        return f"Tipo di file non ammesso ({tipo or 'sconosciuto'}). Ammessi: {ammessi}."
    if not nome.strip():
        return "Il file non ha un nome."
    return None


def salva(contenuto: bytes) -> tuple[bool, str, str]:
    """Carica il contenuto e torna `(riuscito, messaggio, impronta)`.

    Se un file identico c'è già (stessa impronta) non lo ricarica: è il
    caso di una foto allegata a due modelli diversi.
    """
    if not configurato():
        return False, ("archivio esterno non configurato (BACKUP_GIST_ID / "
                       "BACKUP_GITHUB_TOKEN): senza, un allegato sparirebbe al "
                       "primo riavvio"), ""
    impronta = hashlib.sha256(contenuto).hexdigest()
    with _lock:
        # La copia locale si scrive comunque: se GitHub non risponde, il
        # caricamento fallisce e non resta una riga che punta al nulla.
        try:
            with open(_percorso_cache(impronta), "wb") as f:
                f.write(contenuto)
        except OSError as errore:
            return False, f"copia locale non riuscita: {errore}", ""

        if storage.impronta_ancora_usata(impronta):
            return True, "", impronta

        ok, messaggio = _patch_gist({
            _nome_nel_gist(impronta): {
                "content": base64.b64encode(contenuto).decode("ascii")},
        })
    if not ok:
        return False, messaggio, ""
    return True, "", impronta


def leggi(impronta: str) -> bytes | None:
    """Il contenuto, dalla cache locale se c'è, altrimenti dall'archivio
    esterno (e la cache si riempie per la prossima volta)."""
    percorso = _percorso_cache(impronta)
    if os.path.exists(percorso):
        try:
            with open(percorso, "rb") as f:
                return f.read()
        except OSError:
            pass
    if not configurato():
        return None
    dati = _scarica(impronta)
    if dati is None:
        return None
    try:
        with open(percorso, "wb") as f:
            f.write(dati)
    except OSError:  # pragma: no cover - la cache è un di più, non un obbligo
        pass
    return dati


def _scarica(impronta: str) -> bytes | None:
    try:
        risposta = requests.get(
            f"https://api.github.com/gists/{C.env('BACKUP_GIST_ID')}",
            headers=_headers(), timeout=C.HTTP_TIMEOUT + 30,
        )
    except Exception:
        return None
    if risposta.status_code != 200:
        return None
    try:
        file_gist = risposta.json()["files"].get(_nome_nel_gist(impronta))
    except (ValueError, KeyError, AttributeError):
        return None
    if not file_gist:
        return None
    contenuto = file_gist.get("content")
    # Sopra il megabyte l'API tronca il contenuto e rimanda al raw_url:
    # senza questo ramo si servirebbe un file a metà, che è peggio di un
    # file mancante perché sembra funzionare.
    if file_gist.get("truncated") and file_gist.get("raw_url"):
        try:
            grezzo = requests.get(file_gist["raw_url"], headers=_headers(),
                                  timeout=C.HTTP_TIMEOUT + 45)
            if grezzo.status_code == 200:
                contenuto = grezzo.text
        except Exception:
            pass
    if not contenuto:
        return None
    try:
        return base64.b64decode(contenuto)
    except Exception:
        return None


def elimina(impronta: str) -> None:
    """Toglie il contenuto dall'archivio esterno e dalla cache. Da
    chiamare SOLO dopo aver controllato che nessuna riga lo nomini più
    (`storage.impronta_ancora_usata`)."""
    try:
        os.remove(_percorso_cache(impronta))
    except OSError:
        pass
    if not configurato():
        return
    with _lock:
        # `None` come valore di un file, per l'API dei Gist, vuol dire
        # «cancellalo».
        _patch_gist({_nome_nel_gist(impronta): None})


def stato() -> str:
    """Riga per la Diagnostica."""
    if not configurato():
        return "non configurato: il caricamento di allegati è disattivato"
    conteggio = len(storage.get_allegati_per_device())
    return (f"attivo nel Gist del salvataggio · {conteggio} modelli con allegati · "
            f"limite {C.ALLEGATI_MAX_MB} MB per file")
