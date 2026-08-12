"""Confronto fra due momenti: «cosa è cambiato da quando ho testato».

PERCHÉ ESISTE. Finora l'app risponde a «a che versione è questo modello».
È utile, ma non è la domanda del QA: chi ha già provato la propria app su un
Galaxy S24 il mese scorso non vuole sapere qual è la versione — vuole sapere
**se è cambiata da allora**, e quanto profondamente. Senza questo confronto
la decisione «vale la pena rilanciare i test?» resta a memoria di chi ha
testato, che è il punto in cui si perde.

Il meccanismo è volutamente elementare: quando si dichiara «testato adesso»
si fotografa lo stato software del dispositivo (`storage.set_test_baseline`).
Da quel momento ogni confronto è fra quella fotografia e lo stato corrente.

## Cosa conta come cambiamento, e quanto pesa

| cambia | peso | perché |
|---|---|---|
| versione Android | MAJOR | cambia il comportamento dei permessi, delle API, del background |
| skin / versione completa | MAJOR se cambia la cifra principale, altrimenti FEATURE | One UI 7 → 8 non è One UI 8.0 → 8.0.1 |
| build | FEATURE | firmware diverso a parità di OS |
| livello di patch | SECURITY | correzioni di sicurezza, di rado visibili all'app |

## La versione che retrocede

Un dispositivo non torna indietro. Se lo stato corrente dichiara una versione
**inferiore** alla fotografia, il dato è sbagliato — non è un aggiornamento
al contrario. Qui viene classificato come `INCOERENTE` e **mostrato**, non
corretto in silenzio: nascondere un disaccordo fra fonti è il modo più
efficace di far sembrare affidabile un archivio che non lo è. È l'ultimo dei
punti aperti del documento di passaggio consegne («rifiuto di una versione
che retrocede», «disaccordo *mostrato* invece che nascosto»).

## Un campo che sparisce non è un cambiamento

Se la fotografia aveva una build e oggi il campo è vuoto, non è successo
niente al telefono: è una fonte che non risponde più, o che risponde con
meno dati. Trattarlo come cambiamento produrrebbe un «da ritestare» ogni
volta che una fonte ha una giornata storta. Viene quindi ignorato ai fini
del retest, e segnalato a parte come dato mancante.
"""
from __future__ import annotations

import re

from . import config as C

MAI_TESTATO = "mai_testato"
INVARIATO = "invariato"
DA_RITESTARE = "da_ritestare"
INCOERENTE = "incoerente"

ETICHETTE = {
    MAI_TESTATO: "⚪ Mai testato",
    INVARIATO: "🟢 Invariato",
    DA_RITESTARE: "🔴 Da ritestare",
    INCOERENTE: "🟠 Dato incoerente",
}

# I campi confrontati, nell'ordine in cui vanno mostrati.
CAMPI = (
    ("android_version", "Android"),
    ("os_version", "Versione completa"),
    ("build", "Build"),
    ("patch_level", "Patch"),
)

_PATCH_ISO = re.compile(r"^(\d{4})-(\d{2})")
_PRIMA_CIFRA = re.compile(r"(\d+)")


def _testo(valore) -> str:
    return " ".join(str(valore or "").split())


def _intero(valore) -> int | None:
    try:
        return int(valore)
    except (TypeError, ValueError):
        return None


def _cifra_principale(versione: str) -> int | None:
    """«One UI 8.0» → 8. Serve a distinguere un salto di skin da un
    ritocco: 8.0 → 8.0.1 non è 7.1 → 8.0."""
    trovato = _PRIMA_CIFRA.search(_testo(versione))
    return int(trovato.group(1)) if trovato else None


def _patch_confrontabile(valore: str) -> str | None:
    """Livello di patch ridotto a `AAAA-MM`, l'unica forma confrontabile.

    Le fonti scrivono `2026-07-01`, `2026-07` o `July 2026`: solo le prime
    due si ordinano senza interpretare, e sono la stragrande maggioranza.
    Su una forma che non si riconosce si preferisce non pronunciarsi
    piuttosto che inventare un ordine.
    """
    trovato = _PATCH_ISO.match(_testo(valore))
    return f"{trovato.group(1)}-{trovato.group(2)}" if trovato else None


def _snapshot(origine: dict | None) -> dict:
    """Estrae i soli campi che descrivono lo stato software."""
    origine = origine or {}
    return {
        "android_version": _intero(origine.get("android_version")),
        "os_version": _testo(origine.get("os_version")) or None,
        "build": _testo(origine.get("build")) or None,
        "patch_level": _testo(origine.get("patch_level")) or None,
    }


def snapshot(device: dict) -> dict:
    """Fotografia dello stato software, da salvare come baseline."""
    return _snapshot(device)


def _regressione(campo: str, prima, dopo) -> bool:
    """Vero solo quando si può dimostrare che il valore è ANDATO INDIETRO.

    Sulla stringa di una build non si può dire nulla: cambia formato fra
    generazioni e fra regioni, e un ordinamento alfabetico non descrive
    nessuna realtà. Meglio tacere che affermare una regressione inventata.
    """
    if campo == "android_version":
        return prima is not None and dopo is not None and dopo < prima
    if campo == "patch_level":
        a, b = _patch_confrontabile(prima), _patch_confrontabile(dopo)
        return bool(a and b and b < a)
    return False


def _peso(campo: str, prima, dopo) -> str:
    if campo == "android_version":
        return C.SEV_MAJOR
    if campo == "os_version":
        pa, pb = _cifra_principale(prima), _cifra_principale(dopo)
        if pa is not None and pb is not None and pa != pb:
            return C.SEV_MAJOR
        return C.SEV_FEATURE
    if campo == "build":
        return C.SEV_FEATURE
    return C.SEV_SECURITY


AZIONI = {
    C.SEV_MAJOR: "Retest completo: cambia il sistema operativo",
    C.SEV_FEATURE: "Smoke test: firmware diverso a parità di sistema",
    C.SEV_SECURITY: "Nessuna azione, salvo regressioni note di sicurezza",
}


def confronta(device: dict, baseline: dict | None) -> dict:
    """Confronta lo stato attuale di un dispositivo con l'ultima fotografia.

    `device` è una riga di `storage.get_devices()`; `baseline` una riga di
    `storage.get_test_baseline()` (o `None` se non è mai stato testato).
    """
    if not baseline:
        return {
            "stato": MAI_TESTATO,
            "etichetta": ETICHETTE[MAI_TESTATO],
            "severita": None,
            "azione": "Segna una baseline per iniziare a seguire i cambiamenti",
            "cambiamenti": [],
            "mancanti": [],
            "riassunto": "",
            "tested_at": None,
            "note": "",
        }

    prima = _snapshot(baseline)
    dopo = _snapshot(device)

    cambiamenti: list[dict] = []
    mancanti: list[str] = []
    incoerenze: list[dict] = []

    for campo, etichetta in CAMPI:
        vecchio, nuovo = prima[campo], dopo[campo]
        if vecchio == nuovo:
            continue
        if nuovo in (None, ""):
            # Il campo è sparito dalle fonti: è un buco di copertura, non un
            # aggiornamento del telefono. Non fa scattare il retest.
            if vecchio not in (None, ""):
                mancanti.append(etichetta)
            continue
        voce = {
            "campo": campo,
            "etichetta": etichetta,
            "prima": vecchio,
            "dopo": nuovo,
            "severita": _peso(campo, vecchio, nuovo),
        }
        if _regressione(campo, vecchio, nuovo):
            voce["severita"] = None
            incoerenze.append(voce)
        else:
            cambiamenti.append(voce)

    tested_at = baseline.get("tested_at")
    note = baseline.get("note") or ""

    if incoerenze:
        dettaglio = "; ".join(
            f"{v['etichetta']} {v['prima']} → {v['dopo']}" for v in incoerenze)
        return {
            "stato": INCOERENTE,
            "etichetta": ETICHETTE[INCOERENTE],
            "severita": None,
            "azione": ("Verificare la fonte prima di decidere: un dispositivo "
                       "non torna a una versione precedente"),
            "cambiamenti": cambiamenti,
            "incoerenze": incoerenze,
            "mancanti": mancanti,
            "riassunto": dettaglio,
            "tested_at": tested_at,
            "note": note,
        }

    if not cambiamenti:
        return {
            "stato": INVARIATO,
            "etichetta": ETICHETTE[INVARIATO],
            "severita": None,
            "azione": "Nessun retest necessario",
            "cambiamenti": [],
            "incoerenze": [],
            "mancanti": mancanti,
            "riassunto": "",
            "tested_at": tested_at,
            "note": note,
        }

    severita = min(
        (v["severita"] for v in cambiamenti),
        key=lambda s: C.SEVERITY_RANK.get(s, len(C.SEVERITY_ORDER)),
    )
    riassunto = "; ".join(
        f"{v['etichetta']} {v['prima']} → {v['dopo']}" for v in cambiamenti)
    return {
        "stato": DA_RITESTARE,
        "etichetta": ETICHETTE[DA_RITESTARE],
        "severita": severita,
        "azione": AZIONI.get(severita, "Retest da valutare"),
        "cambiamenti": cambiamenti,
        "incoerenze": [],
        "mancanti": mancanti,
        "riassunto": riassunto,
        "tested_at": tested_at,
        "note": note,
    }


def riepilogo(devices: list[dict], baselines: dict[str, dict]) -> dict:
    """Conteggio per stato su un elenco di dispositivi.

    Alimenta i contatori del parco di test: quanti device hanno una novità
    dall'ultima prova, quanti sono fermi, quanti non hanno mai una baseline.
    """
    conteggio = {MAI_TESTATO: 0, INVARIATO: 0, DA_RITESTARE: 0, INCOERENTE: 0}
    for device in devices:
        esito = confronta(device, baselines.get(device.get("device_key")))
        conteggio[esito["stato"]] += 1
    return conteggio
