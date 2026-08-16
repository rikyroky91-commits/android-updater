"""Cifratura del salvataggio esterno.

**PERCHÉ ESISTE.** L'unica copia duratura di questo progetto è un Gist, e
un Gist «secret» NON è privato: è *non elencato*. Chiunque conosca
l'indirizzo lo apre senza autenticarsi. Finché lì dentro c'era un
catalogo di firmware pubblici era un rischio accettabile — il peggio era
che qualcuno leggesse dati che stanno già sui siti dei produttori.

Dal 16/08/2026 quel database contiene **email e hash di password** degli
account del parco di test. La segretezza di un URL non è una difesa
sufficiente per quella roba, e questo modulo la toglie dall'equazione:
nel Gist finiscono byte illeggibili senza la chiave, che vive solo nelle
variabili d'ambiente di Render.

## La dipendenza, dichiarata

Questo è l'unico punto del progetto che usa `cryptography` invece della
sola libreria standard, e non è una scelta di comodo: **Python non ha AES
nella stdlib**. Le alternative erano scrivere una cifratura a mano — che
non si fa mai, per nessun motivo — o non cifrare. `cryptography` è la
libreria di riferimento dell'ecosistema, mantenuta e verificata.

## Il formato

    MUTCIFRA1 | sale (16 byte) | nonce (12 byte) | testo cifrato + tag

L'intestazione serve a **riconoscere un salvataggio cifrato da uno in
chiaro**: i backup già nel Gist sono gzip semplice, e devono continuare a
ripristinarsi. Senza un marcatore esplicito bisognerebbe indovinare, e
indovinare male qui significa scrivere un database di byte casuali.

## Le scelte

* **AES-256-GCM**, che autentica oltre a cifrare: un file corrotto o
  manomesso fallisce la verifica invece di produrre spazzatura
  plausibile. Su un archivio è la proprietà che conta di più.
* **La chiave si deriva con `hashlib.scrypt`**, non si usa la
  passphrase così com'è: stessi parametri di `core/auth.py`
  (`N=2**14, r=8, p=1`), scelti per restare dentro il limite di RAM del
  piano gratuito e già misurati lì.
* **Sale casuale per ogni salvataggio**, scritto nel file. Un sale fisso
  renderebbe la stessa passphrase sempre la stessa chiave, e due
  salvataggi identici sarebbero riconoscibili come tali.
* **Se la chiave è impostata ma la libreria manca, si RIFIUTA di
  salvare** invece di caricare in chiaro. Un salvataggio che si
  degrada in silenzio è peggio di uno che fallisce: nessuno se ne
  accorge finché non serve.
"""
from __future__ import annotations

import hashlib
import os

from . import config as C

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover - assente solo se le dipendenze non sono installate
    AESGCM = None

INTESTAZIONE = b"MUTCIFRA1"
_SALE = 16
_NONCE = 12


def chiave_configurata() -> str:
    return C.env("BACKUP_ENCRYPTION_KEY")


def attiva() -> bool:
    return bool(chiave_configurata())


def disponibile() -> bool:
    """La libreria c'è. Separata da `attiva()` di proposito: «non
    configurato» e «configurato ma non installabile» sono due guasti
    diversi e portano a due rimedi diversi."""
    return AESGCM is not None


def e_cifrato(dati: bytes) -> bool:
    return bool(dati) and dati[:len(INTESTAZIONE)] == INTESTAZIONE


def _chiave_da(passphrase: str, sale: bytes) -> bytes:
    return hashlib.scrypt(passphrase.encode("utf-8"), salt=sale,
                          n=2 ** 14, r=8, p=1, dklen=32)


def cifra(dati: bytes) -> tuple[bytes | None, str]:
    """`(cifrato, errore)`. Da chiamare solo se `attiva()`."""
    passphrase = chiave_configurata()
    if not passphrase:
        return None, "nessuna chiave di cifratura configurata"
    if AESGCM is None:
        return None, ("BACKUP_ENCRYPTION_KEY è impostata ma la libreria "
                      "'cryptography' non è installata: salvataggio annullato "
                      "invece di caricare l'archivio in chiaro")
    sale = os.urandom(_SALE)
    nonce = os.urandom(_NONCE)
    try:
        cifrato = AESGCM(_chiave_da(passphrase, sale)).encrypt(nonce, dati, None)
    except Exception as errore:  # pragma: no cover - percorso difensivo
        return None, f"cifratura non riuscita: {errore}"
    return INTESTAZIONE + sale + nonce + cifrato, ""


def decifra(dati: bytes) -> tuple[bytes | None, str]:
    """`(in chiaro, errore)`.

    Un archivio NON cifrato torna com'è: i salvataggi fatti prima che
    questa funzione esistesse devono continuare a ripristinarsi, e
    l'intestazione è lì proprio per distinguerli.
    """
    if not e_cifrato(dati):
        return dati, ""
    passphrase = chiave_configurata()
    if not passphrase:
        return None, ("l'archivio è cifrato ma BACKUP_ENCRYPTION_KEY non è "
                      "impostata: senza la chiave non è recuperabile")
    if AESGCM is None:
        return None, ("l'archivio è cifrato ma la libreria 'cryptography' "
                      "non è installata")
    inizio = len(INTESTAZIONE)
    sale = dati[inizio:inizio + _SALE]
    nonce = dati[inizio + _SALE:inizio + _SALE + _NONCE]
    corpo = dati[inizio + _SALE + _NONCE:]
    try:
        return AESGCM(_chiave_da(passphrase, sale)).decrypt(nonce, corpo, None), ""
    except Exception:
        # AES-GCM autentica: qui non si distingue «chiave sbagliata» da
        # «file manomesso», ed è giusto così — in entrambi i casi quel
        # contenuto non va scritto sul database.
        return None, ("archivio cifrato non decifrabile: la chiave non "
                      "corrisponde, oppure il file è danneggiato")


def stato() -> str:
    """Riga per la Diagnostica."""
    if not attiva():
        return ("non attiva: il salvataggio va nel Gist in chiaro. Il Gist è "
                "«secret», cioè non elencato, non privato — chi ne conosce "
                "l'indirizzo lo legge, e lì dentro ci sono email e hash delle password")
    if not disponibile():
        return ("CONFIGURATA MA NON UTILIZZABILE: manca la libreria "
                "'cryptography'. I salvataggi sono fermi, di proposito")
    return "attiva (AES-256-GCM, chiave derivata con scrypt)"
