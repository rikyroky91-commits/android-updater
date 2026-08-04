"""Orchestrazione: scarica → normalizza → deduplica → salva → notifica.

La normalizzazione è il punto in cui una notizia grezza diventa un record
strutturato per dispositivo. La chiave di deduplica è
`brand|modello|build-o-versione`: lo stesso rollout riportato da tre testate
diverse produce **un solo** item e **una sola** notifica.
"""
from __future__ import annotations

import threading
import time
import traceback

from . import backup, classify, config as C, extract, modelcodes, notify, sources, storage
from .util import now_iso, short_hash, slug, utcnow

_scan_lock = threading.Lock()


# ----------------------------------------------------------------------
# Normalizzazione
# ----------------------------------------------------------------------
def _item_id(brand: str, model: str | None, fingerprint: str | None,
             source_key: str, title: str) -> str:
    if model:
        if fingerprint:
            return f"{slug(brand, 24)}|{slug(model, 32)}|{slug(fingerprint, 32)}"
        return f"{slug(brand, 24)}|{slug(model, 32)}|{short_hash(title)}"
    return f"{source_key}|{short_hash(title)}"


def _implausibilita(brand: str | None, data, os_version: str) -> list[str]:
    """Elenco dei motivi per cui questo dato NON è credibile (vuoto = ok).

    Regole volutamente conservative: colpiscono solo ciò che è impossibile,
    non ciò che è insolito — un falso allarme qui nasconderebbe un dato
    buono, che è comunque un danno."""
    motivi = []

    # Una versione Android su un iPhone (o viceversa) è una confusione di
    # campi fra fonti diverse, non un dato reale.
    if brand == C.APPLE and data.android_version:
        motivi.append(f"incoerente: dispositivo Apple con versione Android {data.android_version}")
    if brand and brand != C.APPLE and data.skin_name in ("iOS", "iPadOS"):
        motivi.append(f"incoerente: dispositivo {brand} con versione {data.skin_name}")

    # Versione Android oltre l'orizzonte plausibile: Android avanza di una
    # major all'anno, quindi un numero molto oltre l'attuale indica che è
    # stato letto un altro numero (una promessa futura, un prezzo, un anno).
    if data.android_version and data.android_version > C.MAX_PLAUSIBLE_ANDROID:
        motivi.append(
            f"implausibile: Android {data.android_version} oltre il massimo "
            f"atteso ({C.MAX_PLAUSIBLE_ANDROID})"
        )

    # iOS: dal 2025 Apple usa la numerazione per anno (26 = ciclo 2025-26),
    # quindi il tetto è diverso da quello di Android.
    if data.skin_name in ("iOS", "iPadOS") and data.skin_version:
        try:
            major = int(str(data.skin_version).split(".")[0])
        except ValueError:
            major = 0
        if major > C.MAX_PLAUSIBLE_IOS:
            motivi.append(
                f"implausibile: {data.skin_name} {data.skin_version} oltre il "
                f"massimo atteso ({C.MAX_PLAUSIBLE_IOS})"
            )
    return motivi


def normalize(raw: sources.RawItem, source: sources.Source) -> dict:
    """Trasforma un `RawItem` in un record pronto per il database."""
    text = raw.text
    data = extract.extract_all(text, raw.brand or source.brand)

    # I campi forniti direttamente dalla fonte hanno la precedenza sull'estrazione
    model = raw.device or data.device_model
    if model:
        model = extract.canonical_device(model) if not raw.device else raw.device.strip()
    brand = raw.brand or data.brand or source.brand or extract.detect_brand(text)
    if raw.build:
        data.build = raw.build
    if raw.android_version:
        data.android_version = raw.android_version
    data.device_model = model
    data.brand = brand

    relevance = classify.score_relevance(text, data, source.trust)
    # Le ricerche generiche su Google News sono l'ultima risorsa per i brand
    # senza fonte dedicata: senza un modello riconosciuto non c'è modo di
    # sapere a quale device si riferiscano (es. notizie di mercato/strategia
    # che citano "update" di striscio), quindi non contano come
    # aggiornamento firmware anche se il punteggio testuale passerebbe. Non
    # si applica ai feed editoriali (9to5Google, GSMArena, SamMobile, ...)
    # né alla ricerca live (che fissa sempre un modello esplicito prima di
    # normalizzare): quelli restano governati solo dal punteggio di rilevanza.
    if relevance.is_relevant and source.is_web_search and not data.device_model:
        relevance = classify.Relevance(
            False, relevance.score,
            relevance.reasons + ["fonte generica (ricerca news) senza un modello riconosciuto"],
        )
    severity, color, severity_reason = classify.classify_severity(text, data, raw.size_gb)

    os_version = data.os_version or (raw.version or "")
    fingerprint = data.build or os_version or data.patch_level

    # ---- Controllo di plausibilità (rete di sicurezza) ------------------
    # Nessuna fonte è affidabile per sempre: siti e API cambiano struttura
    # senza preavviso, e un errore di parsing produce numeri plausibili ma
    # falsi (è già successo: un iPhone 8 mostrato con iOS 26, una versione
    # Android presa da una promessa di aggiornamento futuro). Qui i valori
    # palesemente impossibili vengono SCARTATI invece di pubblicati: è
    # meglio che l'app dica "non lo so" che affermi con sicurezza una cosa
    # sbagliata, perché un dato falso è peggio di un dato assente.
    incoerenze = _implausibilita(brand, data, os_version)
    if incoerenze:
        relevance = classify.Relevance(
            False, relevance.score, relevance.reasons + incoerenze,
        )

    return {
        "id": _item_id(brand or source.key, model, fingerprint, source.key, raw.title),
        "brand": brand or C.OTHER,
        "device_model": model,
        "device_key": extract.device_key(brand, model) if (brand and model) else None,
        "title": raw.title,
        "os_version": os_version,
        "android_version": data.android_version,
        "skin_name": data.skin_name,
        "skin_version": data.skin_version,
        "build": data.build,
        "patch_level": data.patch_level,
        "severity": severity,
        "color": color,
        "severity_reason": severity_reason,
        "size_info": raw.size_info,
        "link": raw.link,
        "source": source.key,
        "source_label": source.label,
        "source_trust": source.trust,
        "published": raw.published,
        "first_seen": now_iso(),
        "is_relevant": relevance.is_relevant,
        "relevance_score": relevance.score,
        "relevance_note": relevance.explanation,
    }


# ----------------------------------------------------------------------
# Collezione
# ----------------------------------------------------------------------
def collect(only_sources: list | None = None) -> tuple[list[dict], list[dict]]:
    """Interroga le fonti. Restituisce (items normalizzati, stato fonti).

    `only_sources` permette di iniettare fonti specifiche (test, debug di una
    singola fonte) senza toccare il registro globale.
    """
    items: list[dict] = []
    status: list[dict] = []

    for source in (only_sources if only_sources is not None else sources.all_sources()):
        started = time.time()
        try:
            raw_items, error = source.fetch()
        except Exception as exc:  # una fonte rotta non deve fermare la scansione
            raw_items, error = [], f"eccezione: {exc}"
        normalized = []
        for raw in raw_items:
            try:
                normalized.append(normalize(raw, source))
            except Exception as exc:  # pragma: no cover
                error = error or f"normalizzazione fallita: {exc}"
        items.extend(normalized)
        storage.record_source_status(source.key, source.label, error is None, len(normalized), error)
        # Annota il conteggio per il confronto con le scansioni precedenti:
        # è l'unico modo per accorgersi di una fonte che risponde ma rende
        # molto meno del solito (vedi storage._valuta_degrado).
        storage.record_source_history(source.key, len(normalized), error is None)
        status.append({
            "source": source.key,
            "label": source.label,
            "trust": source.trust,
            "ok": error is None,
            "items": len(normalized),
            "error": error,
            "seconds": round(time.time() - started, 1),
        })
    return items, status


# ----------------------------------------------------------------------
# Notifiche
# ----------------------------------------------------------------------
def _should_notify(item: dict, watched: set[str]) -> bool:
    if not item.get("is_relevant"):
        return False
    is_watched = bool(item.get("device_key") and item["device_key"] in watched)
    if C.NOTIFY_ONLY_WATCHLIST and not is_watched:
        return False
    if is_watched:
        return True
    rank = C.SEVERITY_RANK.get(item.get("severity", ""), 99)
    return rank <= C.min_severity_rank()


def notify_new(new_items: list[dict]) -> int:
    """Invia le notifiche per gli item appena comparsi. Restituisce quante ne partono."""
    if not C.notify_enabled():
        return 0
    watched = storage.watched_keys()
    candidates = [i for i in new_items if _should_notify(i, watched)][: C.NOTIFY_MAX_PER_SCAN]
    if not candidates:
        return 0

    # Molti item in un colpo solo (primo avvio, cache svuotata): un digest unico
    # invece di trenta messaggi.
    if len(candidates) > 8:
        ok, error = notify.send_digest(candidates, watched)
        for item in candidates:
            storage.mark_notified(item["id"])
            storage.log_notification(item, kind="digest", ok=ok)
        return len(candidates) if ok else 0

    sent = 0
    for item in candidates:
        is_watched = bool(item.get("device_key") and item["device_key"] in watched)
        ok, error = notify.send_update(item, is_watched)
        storage.log_notification(item, kind="auto", ok=ok)
        if ok:
            storage.mark_notified(item["id"])
            sent += 1
        time.sleep(0.4)  # rispetta il rate limit di Telegram
    return sent


# ----------------------------------------------------------------------
# Scansione completa
# ----------------------------------------------------------------------
def run_scan(auto_notify: bool = True, only_sources: list | None = None) -> dict:
    """Esegue una scansione completa. È idempotente e protetta da lock."""
    if not _scan_lock.acquire(blocking=False):
        return {"skipped": True, "reason": "scansione già in corso"}

    scan_id = storage.start_scan()
    started = time.time()
    error_text = None
    items, status, new_items = [], [], []
    notifications = 0
    try:
        items, status = collect(only_sources)
        for item in items:
            if storage.upsert_update(item):
                new_items.append(item)
        if auto_notify:
            notifications = notify_new(new_items)
        storage.purge_old()
    except Exception:  # pragma: no cover
        error_text = traceback.format_exc(limit=3)
    finally:
        duration = time.time() - started
        storage.finish_scan(
            scan_id, total=len(items), new_items=len(new_items),
            notifications=notifications, duration=duration, error=error_text,
        )
        storage.set_meta("last_scan_at", now_iso())
        # Il database vive su disco effimero: senza questo salvataggio,
        # tutto il lavoro appena fatto sparirebbe al prossimo riavvio.
        # Non più spesso di BACKUP_EVERY_MINUTES, e silenzioso se non
        # configurato: un archivio irraggiungibile non deve far fallire
        # una scansione andata a buon fine.
        try:
            backup.salva_se_serve()
        except Exception:  # pragma: no cover - il salvataggio non è critico
            pass
        _scan_lock.release()

    return {
        "skipped": False,
        "total": len(items),
        "new": len(new_items),
        "notifications": notifications,
        "sources": status,
        "duration": duration,
        "error": error_text,
    }


# ----------------------------------------------------------------------
# Ricerca live su un modello specifico (on-demand)
# ----------------------------------------------------------------------
_LIVE_SOURCE = sources.Source(
    key="live_search", label="Ricerca live", trust=C.TRUST_NOISY, fetch=None,
)


_STRUCTURED_TRUSTS = (C.TRUST_STRUCTURED, C.TRUST_CURATED)


def search_model(model_query: str) -> dict:
    """Risponde a «qual è l'ultimo aggiornamento di questo modello, e di
    quando è» combinando due fonti di verità, in ordine di precisione:

    1. **Archivio locale** — se il giro periodico ha già una riga per questo
       device da una fonte STRUCTURED/CURATED (catalogo Xiaomi, controllo
       ufficiale Samsung FUS/Motorola lolinet/Honor AER, feed editoriali),
       quel dato è più preciso di qualunque notizia e non richiede nessuna
       chiamata di rete: build/versione/patch vengono da un controllo
       diretto, non da un titolo da interpretare.
    2. **Ricerca live su Google News** — sempre eseguita comunque, per
       intercettare un rollout più recente di quanto l'archivio sappia, o
       per i brand (Oppo/OnePlus/realme, Vivo generico, brand di nicchia)
       che non hanno nessuna fonte strutturata dedicata.

    I risultati della ricerca live vengono comunque normalizzati e salvati
    con `upsert_update`, così entrano anche nello storico del dispositivo e
    nel Feed, non solo in questa risposta. Ogni ricerca riuscita viene anche
    condensata in una riga della cronologia ricerche (modello + firmware).
    """
    existing = storage.get_devices(search=model_query)
    existing_device = existing[0] if existing else None
    existing_is_structured = bool(existing_device and existing_device.get("best_source_trust") in _STRUCTURED_TRUSTS)

    items = []

    # 1) Fonte UFFICIALE del brand, interrogata a comando per questo modello.
    #    È il passaggio che rende la ricerca capace di dare un firmware reale
    #    anche per un modello mai visto prima dal giro periodico (situazione
    #    normale su Streamlit Cloud, dove il database si azzera a ogni
    #    riavvio del container).
    structured_items, structured_note = _lookup_structured_for(model_query)
    for item in structured_items:
        storage.upsert_update(item)
    items.extend(structured_items)

    # 2) Ricerca live su notizie: sempre eseguita comunque, per intercettare
    #    un rollout più recente di quanto sappia la fonte ufficiale, e per i
    #    brand che non hanno una fonte ufficiale interrogabile a comando.
    raw_items, error = sources.search_model_live(model_query)
    if not (error and not raw_items):
        news_items = [normalize(raw, _LIVE_SOURCE) for raw in raw_items]
        for item in news_items:
            storage.upsert_update(item)
        items.extend(news_items)

    items.sort(key=lambda i: i.get("published") or i.get("first_seen") or "", reverse=True)

    # Per la cronologia si privilegia un dato da fonte ufficiale, se c'è:
    # una build verificata vale più del titolo di una notizia.
    #
    # MA SOLO SE PORTA DAVVERO UN FIRMWARE. Alcune fonti ufficiali
    # confermano che un modello esiste senza pubblicarne la versione (il
    # catalogo Android Enterprise Recommended, l'elenco Oppo): sceglierle
    # comunque faceva finire in cronologia un «—» mentre una notizia
    # riportava una patch datata. È la stessa regola già adottata per la
    # scelta del risultato — si preferisce ciò CHE HA la versione — qui
    # applicata anche a quello che si annota.
    def _ha_firmware(voce: dict) -> bool:
        return bool(voce.get("os_version") or voce.get("build") or voce.get("patch_level"))

    structured_relevant = [i for i in structured_items if i.get("is_relevant")]
    rilevanti = [i for i in items if i.get("is_relevant")]
    best = next(
        (i for i in structured_relevant if _ha_firmware(i)),
        next(
            (i for i in rilevanti if _ha_firmware(i)),
            (structured_relevant[0] if structured_relevant
             else (rilevanti[0] if rilevanti else (items[0] if items else None))),
        ),
    )
    if best:
        storage.log_search(model_query, best)
    elif existing_device:
        # Nessuna notizia trovata online in questo momento, ma il modello è
        # già noto in archivio da una fonte strutturata: la ricerca comunque
        # "riesce", con quel dato come risposta.
        storage.log_search(model_query, {
            "device_key": existing_device["device_key"], "brand": existing_device["brand"],
            "device_model": existing_device["model"], "os_version": existing_device.get("os_version"),
            "build": existing_device.get("build"), "patch_level": existing_device.get("patch_level"),
            "link": existing_device.get("link"),
        })

    return {
        "error": None if (items or existing_device) else error,
        "items": items,
        "existing_device": existing_device,
        "existing_is_structured": existing_is_structured,
        "structured_count": len(structured_items),
        "structured_note": structured_note,
    }


def _lookup_structured_for(model_query: str) -> tuple[list[dict], str | None]:
    """Interroga la fonte ufficiale del brand per il modello cercato,
    provando anche i nomi commerciali risolti da un eventuale codice
    tecnico (chi cerca 'ABR-LX1' deve ottenere il dato di 'HONOR X8c')."""
    candidates = [model_query]
    for candidate_code in sources._code_candidates(model_query):
        candidates.extend(modelcodes.resolve(candidate_code))

    note = None
    seen = set()
    for name in candidates:
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        raw_items, lookup_note = sources.lookup_model_structured(name)
        note = note or lookup_note
        if raw_items:
            # IL TRUST LO DICHIARA LA FONTE, NON QUESTA FUNZIONE.
            # Finché in `_STRUCTURED_LOOKUPS_LIST` c'erano solo fonti
            # ufficiali, scrivere STRUCTURED qui era una scorciatoia
            # innocua. Da quando c'è anche un canale non ufficiale
            # sarebbe una bugia, e per giunta quella che conta di più: il
            # trust è ciò che decide chi vince quando due fonti dicono
            # cose diverse sullo stesso telefono. Una fonte curated
            # promossa a strutturata potrebbe sovrascrivere un dato
            # ufficiale — il difetto già corretto una volta in
            # `storage.get_devices()`.
            trust = raw_items[0].trust or C.TRUST_STRUCTURED
            etichetta = raw_items[0].size_info or (
                "Fonte ufficiale" if trust == C.TRUST_STRUCTURED else "Fonte dedicata")
            source = sources.Source(
                key="official_lookup" if trust == C.TRUST_STRUCTURED else "curated_lookup",
                label=f"{etichetta} (ricerca diretta)",
                trust=trust,
                fetch=None,
                brand=raw_items[0].brand,
                homepage="",
            )
            return [normalize(raw, source) for raw in raw_items], None
    return [], note


def seconds_until_next_scan() -> int:
    last = storage.last_scan()
    if not last or not last.get("finished_at"):
        return 0
    from .util import to_dt

    finished = to_dt(last["finished_at"])
    if not finished:
        return 0
    elapsed = (utcnow() - finished).total_seconds()
    return max(0, int(C.SCAN_INTERVAL_MINUTES * 60 - elapsed))


# ----------------------------------------------------------------------
# Worker di background
# ----------------------------------------------------------------------
def _loop(stop_event: threading.Event | None = None) -> None:
    while True:
        try:
            if seconds_until_next_scan() == 0:
                run_scan(auto_notify=True)
        except Exception:  # pragma: no cover
            pass
        if stop_event is not None and stop_event.wait(60):
            return
        elif stop_event is None:
            time.sleep(60)


def start_background_worker() -> threading.Thread:
    """Avvia il ciclo periodico in un thread daemon.

    Il ciclo si sveglia ogni minuto e scansiona solo se è passato
    `SCAN_INTERVAL_MINUTES` dall'ultima scansione **completata**: così un
    riavvio del processo non provoca una scansione immediata e duplicata,
    perché lo stato vive nel database e non in memoria.
    """
    thread = threading.Thread(target=_loop, name="tracker-worker", daemon=True)
    thread.start()
    return thread
