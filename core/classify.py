"""Rilevanza e severità.

Due miglioramenti rispetto alla versione precedente:

1. La rilevanza non è più un booleano "una keyword positiva e nessuna negativa",
   ma un **punteggio** che pesa insieme segnali linguistici e segnali
   strutturali (build number, patch level, versione OS). Un titolo che contiene
   `S928BXXU5BYG1` è quasi certamente un rilascio reale, qualunque sia la sua
   formulazione; un titolo al futuro ("will get", "expected to") quasi
   certamente no.

2. Le frasi speculative sono penalizzate separatamente dai temi fuori scope
   (recensioni, offerte), così si può capire *perché* un item è stato scartato.

Nessuna dipendenza esterna → testabile offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import config as C
from .extract import Extraction

# ----------------------------------------------------------------------
# Vocabolari
# ----------------------------------------------------------------------
# Frasi che descrivono una distribuzione già in corso (peso alto)
STRONG_POSITIVE = [
    "rolling out", "rolls out", "roll out to", "now available for", "starts receiving",
    "begins receiving", "is receiving", "are receiving", "has started receiving",
    "ota update", "ota rollout", "software update", "firmware update",
    "security update", "security patch", "update is live", "update is now live",
    "changelog", "build number", "update available", "released for",
    "now rolling", "gets android", "gets one ui", "gets hyperos", "gets coloros",
    "gets oxygenos", "update brings", "patch notes", "pushed to", "seeding",
    "stable update", "stable rollout", "arriva l'aggiornamento", "in rollout",
    "feature drop", "pixel drop", "rollout begins", "rollout expands",
    "starts rolling", "begins rolling", "arrives for", "seeded to", "goes live",
    "update released", "released in", "hits devices", "widely available",
]

# Termini generici legati agli update (peso basso: da soli non bastano)
WEAK_POSITIVE = [
    "update", "aggiornamento", "firmware", "patch", "build", "rollout",
    "beta", "release", "version",
]

# Temi fuori scope: se presenti l'item viene scartato a prescindere
HARD_NEGATIVE = [
    "rumor", "rumour", "leak", "leaked", "leaks", "review", "hands-on", "hands on",
    "unboxing", "benchmark", " vs ", " vs.", "comparison", "deal", "discount",
    "price cut", "price in", "sale", "offer", "giveaway", "coupon",
    "camera samples", "camera test", "wallpaper", "how to", "tips and tricks",
    "renders", "teaser", "first look", "concept", "clone", "best phones",
    "buying guide", "specs sheet", "specifications leak", "recensione", "offerta",
    "pre-order", "preorder", "goes on sale", "now official", "unveiled",
    "launched in", "wallpapers", "case leak",
]

# Segnali che l'articolo parla di qualcosa che *non è ancora successo*
SPECULATIVE = [
    "will get", "will receive", "to get", "to receive", "expected to", "tipped",
    "reportedly", "could get", "may get", "might get", "coming soon", "here's when",
    "when will", "eligible devices", "release date", "launch date", "roadmap",
    "rumored", "in arrivo", "potrebbe ricevere", "quando arriva",
]

_WORD_BOUNDARY_CACHE: dict[str, re.Pattern] = {}


def _contains(text: str, phrase: str) -> bool:
    if phrase not in _WORD_BOUNDARY_CACHE:
        _WORD_BOUNDARY_CACHE[phrase] = re.compile(
            r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])"
        )
    return bool(_WORD_BOUNDARY_CACHE[phrase].search(text))


def _matches(text: str, vocabulary: list[str]) -> list[str]:
    return [phrase for phrase in vocabulary if _contains(text, phrase)]


# ----------------------------------------------------------------------
# Rilevanza
# ----------------------------------------------------------------------
@dataclass
class Relevance:
    is_relevant: bool
    score: int
    reasons: list[str] = field(default_factory=list)

    @property
    def explanation(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "nessun segnale"


def _threshold_for(trust: str) -> int:
    if trust == C.TRUST_CURATED:
        return max(1, C.RELEVANCE_THRESHOLD - 2)
    return C.RELEVANCE_THRESHOLD


def score_relevance(text: str, extraction: Extraction, trust: str = C.TRUST_NOISY) -> Relevance:
    """Decide se un item descrive un rilascio software reale.

    `trust` proviene dalla fonte: le fonti strutturate (API ufficiali, tracker
    firmware) non passano dal filtro linguistico perché il dato è già certo.
    """
    if trust == C.TRUST_STRUCTURED:
        return Relevance(True, 10, ["fonte strutturata (dato di rilascio ufficiale)"])

    low = f" {str(text or '').lower()} "
    reasons: list[str] = []

    hard = _matches(low, HARD_NEGATIVE)
    if hard:
        return Relevance(False, -10, [f"tema fuori scope: {', '.join(hard[:3])}"])

    score = 0

    if extraction.build:
        score += 4
        reasons.append(f"build number rilevato ({extraction.build})")
    if extraction.patch_level:
        score += 3
        reasons.append(f"patch level {extraction.patch_level}")
    if extraction.skin_name:
        score += 2
        reasons.append(f"versione {extraction.skin_name} {extraction.skin_version}")
    if extraction.android_version:
        score += 2
        reasons.append(f"Android {extraction.android_version}")
    if extraction.device_model:
        score += 1
        reasons.append(f"modello riconosciuto: {extraction.device_model}")

    strong = _matches(low, STRONG_POSITIVE)
    if strong:
        score += 3
        reasons.append(f"rollout in corso: {strong[0]}")

    weak = _matches(low, WEAK_POSITIVE)
    if weak and not strong:
        score += 1
        reasons.append(f"termine generico: {weak[0]}")

    speculative = _matches(low, SPECULATIVE)
    if speculative:
        score -= 4
        reasons.append(f"annuncio/previsione, non rollout: {speculative[0]}")

    # ------------------------------------------------------------------
    # PROVA DI DISTRIBUZIONE, obbligatoria per le fonti rumorose.
    #
    # Il filtro a punteggio era troppo permissivo esattamente qui: un
    # modello riconosciuto vale 1 e una versione Android vale 2, cioè
    # insieme fanno 3, cioè la soglia. Bastava quindi che un titolo
    # nominasse un telefono e un numero di Android — «Vivo X200 Pro debuts
    # with Android 15» — perché diventasse un «aggiornamento» e creasse un
    # dispositivo in elenco. È l'origine dei dispositivi fantasma nati da
    # notizie generiche.
    #
    # Il punto è che quei due segnali dicono di COSA parla l'articolo, non
    # che sia successo qualcosa. Ciò che distingue un rilascio da un
    # articolo su un telefono è una prova che un pacchetto sia stato
    # distribuito davvero:
    #
    #   - un numero di build      esiste solo se il pacchetto esiste
    #   - un livello di patch     è una data, verificabile
    #   - una frase di rollout    «is rolling out», «security update»…
    #
    # Vale SOLO per le fonti rumorose (le ricerche generiche di notizie).
    # I feed editoriali sono curati — parlano di aggiornamenti per mestiere
    # — e le fonti strutturate non arrivano nemmeno fin qui.
    #
    # È la stessa regola già applicata a valle in `scan.normalize`, dove
    # una notizia senza build non può dettare la versione di un telefono.
    # Applicarla anche qui evita il passo prima: che diventi un dispositivo.
    if trust == C.TRUST_NOISY and not (extraction.build or extraction.patch_level or strong):
        return Relevance(
            False, score,
            reasons + ["nessuna prova di distribuzione: né build, né livello di "
                       "patch, né una frase che descriva un rollout in corso"],
        )

    threshold = _threshold_for(trust)
    return Relevance(score >= threshold, score, reasons)


# ----------------------------------------------------------------------
# Severità
# ----------------------------------------------------------------------
_BETA_RE = re.compile(r"\b(beta|developer preview|dev preview|qpr\d?\s*beta|canary)\b", re.I)
_STABLE_RE = re.compile(r"\b(stable|stabile|public release)\b", re.I)
# Release trimestrali/feature drop: citano una versione Android ma non sono
# un salto di major (es. "Android 15 QPR2", "December Feature Drop").
_QUARTERLY_RE = re.compile(r"\b(qpr\s?\d|feature drop|quarterly)\b", re.I)
# Frasi che indicano un vero passaggio di major release.
_UPGRADE_RE = re.compile(
    r"\b(upgrade to|update to|updated to|based on android \d+ (?:from|upgrade)|"
    r"major (?:update|release)|os upgrade|aggiornamento ad)\b", re.I)
_FEATURE_RE = re.compile(
    r"\b(feature drop|pixel drop|quarterly|qpr\d?|new features|nuove funzioni|"
    r"brings\s+\w+\s+features|functionality)\b",
    re.I,
)
_MAJOR_RE = re.compile(
    r"\b(major update|full firmware|recovery rom|fastboot rom|upgrade to|os upgrade|"
    r"aggiornamento maggiore)\b",
    re.I,
)


def classify_severity(text: str, extraction: Extraction, size_gb: float = 0.0) -> tuple[str, str, str]:
    """Restituisce (etichetta, colore, motivazione) — il semaforo QA.

    Il peso del pacchetto è il segnale più oggettivo per decidere quanto
    retest serve, quindi quando è noto (Xiaomi lo dichiara sempre; per le
    altre fonti viene comunque cercato nel testo dell'articolo) prevale su
    qualunque altro indizio linguistico: sopra la soglia è sempre 🔴, sotto è
    🟡 o 🟢 a seconda che si tratti di un aggiornamento funzionale o di sola
    manutenzione. Se la dimensione non è nota si ricade sull'euristica
    testuale precedente (versione Android, feature drop, major dell'skin…).
    """
    text = str(text or "")

    if _BETA_RE.search(text) and not _STABLE_RE.search(text):
        return C.SEV_BETA, C.SEVERITY_COLORS[C.SEV_BETA], "canale beta / preview"

    # iOS/iPadOS: la struttura del numero di versione dice già di che
    # rilascio si tratta, in modo molto più affidabile di qualunque
    # euristica testuale. Apple è coerente: 19.0 = nuova major (retest
    # completo), 18.2 = release funzionale, 18.1.1 = correttiva/sicurezza.
    if extraction.skin_name in ("iOS", "iPadOS") and extraction.skin_version:
        parti = extraction.skin_version.split(".")
        etichetta_os = f"{extraction.skin_name} {extraction.skin_version}"
        if len(parti) == 1 or (len(parti) > 1 and parti[1] == "0" and len(parti) == 2):
            return (
                C.SEV_MAJOR, C.SEVERITY_COLORS[C.SEV_MAJOR],
                f"{etichetta_os} — nuova release maggiore, retest completo",
            )
        if len(parti) == 2:
            return (
                C.SEV_FEATURE, C.SEVERITY_COLORS[C.SEV_FEATURE],
                f"{etichetta_os} — release funzionale",
            )
        return (
            C.SEV_SECURITY, C.SEVERITY_COLORS[C.SEV_SECURITY],
            f"{etichetta_os} — correttiva / sicurezza",
        )

    if size_gb > 0:
        size_mb = size_gb * 1024
        if size_mb > C.SIZE_MAJOR_MB:
            return (
                C.SEV_MAJOR, C.SEVERITY_COLORS[C.SEV_MAJOR],
                f"pacchetto da {size_gb:.1f} GB — oltre la soglia di {C.SIZE_MAJOR_MB} MB, retest completo",
            )
        size_label = f"{size_mb:.0f} MB"
        if _FEATURE_RE.search(text) or extraction.skin_version or extraction.android_version:
            return (
                C.SEV_FEATURE, C.SEVERITY_COLORS[C.SEV_FEATURE],
                f"pacchetto da {size_label}, sotto soglia — aggiornamento funzionale",
            )
        return (
            C.SEV_SECURITY, C.SEVERITY_COLORS[C.SEV_SECURITY],
            f"pacchetto da {size_label}, sotto soglia — patch di manutenzione",
        )

    # Dimensione non nota: euristica linguistica (invariata rispetto a prima).
    skin_major = False
    if extraction.skin_version:
        parts = extraction.skin_version.split(".")
        # 8.0 → major; 8.5 → feature
        skin_major = len(parts) == 1 or (len(parts) > 1 and parts[1] == "0")

    # Una versione Android citata non significa sempre "salto di major": in
    # "Android 15 QPR2" o "October patch based on Android 14" la versione è il
    # contesto, non il cambiamento. Si degrada quindi a FEATURE/SECURITY.
    quarterly = _QUARTERLY_RE.search(text)
    patch_only = extraction.patch_level and not _UPGRADE_RE.search(text)
    if extraction.android_version and not (quarterly or patch_only):
        return (
            C.SEV_MAJOR,
            C.SEVERITY_COLORS[C.SEV_MAJOR],
            f"nuova release OS: Android {extraction.android_version}",
        )
    if quarterly:
        return (
            C.SEV_FEATURE,
            C.SEVERITY_COLORS[C.SEV_FEATURE],
            "release trimestrale / feature drop",
        )
    if skin_major:
        return (
            C.SEV_MAJOR,
            C.SEVERITY_COLORS[C.SEV_MAJOR],
            f"nuova major dell'interfaccia: {extraction.skin_name} {extraction.skin_version}",
        )
    if _MAJOR_RE.search(text):
        return C.SEV_MAJOR, C.SEVERITY_COLORS[C.SEV_MAJOR], "pacchetto completo / firmware integrale"

    if _FEATURE_RE.search(text) or extraction.skin_version:
        return C.SEV_FEATURE, C.SEVERITY_COLORS[C.SEV_FEATURE], "aggiornamento funzionale"

    return C.SEV_SECURITY, C.SEVERITY_COLORS[C.SEV_SECURITY], "patch di sicurezza / manutenzione"


def qa_impact(severity: str, watched: bool) -> str:
    """Suggerimento operativo per il QA: vale la pena rilanciare i test?"""
    if severity == C.SEV_MAJOR:
        return "Retest completo consigliato" if watched else "Retest completo se il device è in scope"
    if severity == C.SEV_FEATURE:
        return "Smoke test sulle aree toccate"
    if severity == C.SEV_BETA:
        return "Solo se testi sui canali beta"
    return "Nessuna azione, salvo regressioni note"
