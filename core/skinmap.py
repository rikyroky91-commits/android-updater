"""Corrispondenza fra l'interfaccia del produttore e la versione Android.

**Il problema che risolve.** Cercando un Galaxy A32 l'app rispondeva
«Android 12» da una parte e «One UI 5.0» dall'altra. Sono due affermazioni
sullo stesso telefono e una delle due è falsa: One UI 5 gira su Android 13.
L'app aveva il dato giusto sotto forma di versione della skin e ne mostrava
uno sbagliato come versione Android, senza accorgersi della contraddizione.

**Come va usata questa tabella, e come NON va usata.** Serve soprattutto
come **controllo di coerenza**: se una fonte dice Android 12 e un'altra
dice One UI 5.0, una delle due sbaglia e va scartata, non mediata. Serve
solo in seconda battuta a *dedurre* la versione Android, e unicamente dove
la corrispondenza è univoca.

**Perché la distinzione conta.** La corrispondenza sembra ovvia e invece ha
eccezioni documentate, tutte reali:

- **One UI 3.1.1** girava su Android 12 mentre i telefoni normali restavano
  etichettati «3.1» su Android 11.
- **EMUI 11 è basata su Android 10**, non 11: Huawei ha rotto di proposito
  l'allineamento che aveva tenuto fino ad allora.
- **MIUI** ha pubblicato la stessa major su due Android diversi più volte.
- **ColorOS** si è allineata ad Android solo dalla 11: prima saltava da 7 a 11.

Dedurre la versione Android in questi casi significherebbe inventare un
dato che poi decide un retest. Dove la corrispondenza non è certa, questo
modulo dice `None` e l'app tace, come da regola del progetto.
"""
from __future__ import annotations

import re

# Corrispondenza skin → major Android.
#
# `None` come valore significa: corrispondenza NOTA COME NON UNIVOCA, quindi
# da non usare per dedurre. È diverso da «versione assente dalla tabella»,
# che vuol dire semplicemente «non lo so»: nel primo caso sappiamo che una
# risposta sola non esiste, e non ci proviamo nemmeno.
_MAPPA: dict[str, dict[str, int | None]] = {
    "One UI": {
        "1": 9, "1.1": 9,
        "2": 10, "2.1": 10, "2.5": 10,
        "3": 11, "3.1": 11,
        "3.1.1": 12,      # solo pieghevoli e tablet: i bar-phone restavano 3.1
        "4": 12, "4.1": 12, "4.1.1": 12,
        "5": 13, "5.1": 13, "5.1.1": 13,
        "6": 14, "6.1": 14, "6.1.1": 14,
        "7": 15, "7.1": 15,
        "8": 16, "8.5": 16,
    },
    "HyperOS": {"1": 14, "2": 15, "3": 16},
    "MIUI": {
        # Xiaomi ha spedito la stessa major su Android diversi: nessuna
        # deduzione, solo il riconoscimento del nome.
        "12": None, "12.5": None, "13": 12, "14": 13,
    },
    "ColorOS": {
        # Allineata ad Android solo dalla 11 in poi.
        "7": None, "7.1": None, "7.2": None,
        "11": 11, "12": 12, "13": 13, "14": 14, "15": 15, "16": 16,
    },
    "OxygenOS": {"12": 12, "13": 13, "14": 14, "15": 15, "16": 16},
    "realme UI": {"1": 10, "2": 11, "3": 12, "4": 13, "5": 14, "6": 15},
    "MagicOS": {"7": 13, "8": 14, "9": 15},
    "Magic UI": {"4": 10, "5": 11},
    "EMUI": {
        # Il caso più insidioso: EMUI 11 gira su Android 10.
        "9": 9, "10": 10, "11": 10, "12": 12, "13": 12,
    },
    "Funtouch OS": {"16": 16},
    "OriginOS": {"6": 16},
}

# Nomi alternativi con cui le fonti scrivono la stessa interfaccia.
_ALIAS = {
    "ONEUI": "One UI", "ONE UI": "One UI", "SAMSUNG ONE UI": "One UI",
    "HYPEROS": "HyperOS", "XIAOMI HYPEROS": "HyperOS",
    "MIUI": "MIUI",
    "COLOROS": "ColorOS", "COLOR OS": "ColorOS",
    "OXYGENOS": "OxygenOS", "OXYGEN OS": "OxygenOS",
    "REALMEUI": "realme UI", "REALME UI": "realme UI",
    "MAGICOS": "MagicOS", "MAGIC OS": "MagicOS", "MAGIC UI": "Magic UI",
    "EMUI": "EMUI",
    "FUNTOUCH OS": "Funtouch OS", "FUNTOUCHOS": "Funtouch OS",
    "ORIGINOS": "OriginOS", "ORIGIN OS": "OriginOS",
}

# Interfacce che NON sono Android: per loro la domanda «quale major
# Android?» non ha risposta, e inventarne una sarebbe peggio che tacere.
NON_ANDROID = {"HARMONYOS", "HARMONY OS", "IOS", "IPADOS"}


def _normalizza_skin(nome: str | None) -> str | None:
    if not nome:
        return None
    compatto = re.sub(r"\s+", " ", nome).strip().upper()
    if compatto in NON_ANDROID:
        return None
    return _ALIAS.get(compatto)


def _chiavi_versione(versione: str | None) -> list[str]:
    """`5.1.1` → prova `5.1.1`, poi `5.1`, poi `5`.

    Dal più specifico al più generico, perché le eccezioni stanno sempre
    nel numero lungo: `3.1.1` è Android 12 mentre `3.1` è Android 11.
    """
    if versione is None:
        return []
    pezzi = [p for p in re.split(r"[^\d]+", str(versione)) if p]
    return [".".join(pezzi[:i]) for i in range(len(pezzi), 0, -1)]


def android_da_skin(skin: str | None, versione: str | None) -> int | None:
    """Major Android implicata dalla skin, o None se non è deducibile.

    None copre due casi diversi che per il chiamante si equivalgono: skin
    sconosciuta, e skin la cui corrispondenza è nota come non univoca.
    """
    nome = _normalizza_skin(skin)
    if not nome:
        return None
    tabella = _MAPPA.get(nome, {})
    for chiave in _chiavi_versione(versione):
        if chiave in tabella:
            return tabella[chiave]
    return None


def contraddizione(skin: str | None, versione_skin: str | None,
                   android: int | None) -> str | None:
    """Descrive il conflitto fra skin e versione Android, se c'è.

    None significa «nessun conflitto rilevabile», che comprende anche il
    caso in cui semplicemente non sappiamo abbastanza per giudicare.
    Un controllo che nel dubbio accusa farebbe sparire dati buoni.
    """
    if android is None:
        return None
    atteso = android_da_skin(skin, versione_skin)
    if atteso is None or atteso == android:
        return None
    nome = _normalizza_skin(skin)
    return (f"incoerente: {nome} {versione_skin} gira su Android {atteso}, "
            f"non su Android {android}")


def descrizione(skin: str | None, versione_skin: str | None) -> str | None:
    """Etichetta leggibile del tipo «One UI 5.1 (Android 13)»."""
    nome = _normalizza_skin(skin)
    if not nome:
        return None
    etichetta = f"{nome} {versione_skin}".strip()
    atteso = android_da_skin(skin, versione_skin)
    return f"{etichetta} (Android {atteso})" if atteso else etichetta
