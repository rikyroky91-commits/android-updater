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

from . import backup, classify, config as C, extract, modelcodes, notify, skinmap, soc, sources, storage
from .util import now_iso, short_hash, slug, utcnow

_scan_lock = threading.Lock()


# ----------------------------------------------------------------------
# Normalizzazione
# ----------------------------------------------------------------------
def _item_id(brand: str, model: str | None, fingerprint: str | None,
             source_key: str, title: str) -> str:
    """Identificativo di deduplica: lo stesso rollout visto da più fonti
    deve produrre UN record e UNA notifica.

    Il nome del modello entra nella sua forma canonica, la stessa usata da
    `extract.device_key()`. Prima ci entrava alla lettera, e bastava che
    una testata scrivesse «Samsung S24 Ultra» dove un'altra scriveva
    «Galaxy S24 Ultra» perché lo stesso identico rilascio diventasse due
    record e due messaggi Telegram — la deduplica c'era e non funzionava
    proprio nel caso per cui esiste.
    """
    if model:
        radice = extract.radice_modello(brand, model) or slug(model, 32)
        if fingerprint:
            return f"{slug(brand, 24)}|{radice[:32]}|{slug(fingerprint, 32)}"
        return f"{slug(brand, 24)}|{radice[:32]}|{short_hash(title)}"
    return f"{source_key}|{short_hash(title)}"


def _codice_dal_build(build: str | None) -> str | None:
    """Il codice della variante letto dentro il numero di build.

    Molti produttori ci scrivono dentro il codice modello e nessun altro
    posto lo dichiara: `CPH2653_16.0.9.402` è un OnePlus 13 europeo,
    `A325FXXSCDYB2` è un SM-A325F. Senza questa lettura la variante restava
    vuota per tutte le marche tranne Samsung interrogata per codice — e con
    lei restava vuoto il processore, che è la ragione per cui la variante
    interessa.

    Si accetta solo un codice riconosciuto dal modulo dei chip, che ha le
    forme note (SM-, CPH, RMX, XT…): dedurre un codice da una stringa
    qualsiasi produrrebbe varianti inventate.
    """
    if not build:
        return None
    codici = soc.codici_da_testo(build)
    return codici[0] if codici else None


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

    # Skin del produttore in contraddizione con la versione Android.
    #
    # È il difetto osservato sul Galaxy A32: una fonte diceva Android 12,
    # un'altra One UI 5.0 — e One UI 5 gira su Android 13. L'app aveva il
    # dato giusto sotto forma di versione dell'interfaccia e mostrava
    # quello sbagliato come versione Android.
    #
    # Il controllo tace dove la corrispondenza è nota come non univoca
    # (One UI 3.1.1, EMUI 11, MIUI, ColorOS antecedenti alla 11): lì una
    # discrepanza non è una prova di errore.
    conflitto = skinmap.contraddizione(
        data.skin_name, data.skin_version, data.android_version)
    if conflitto:
        motivi.append(conflitto)

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

    # QUANDO IL CODICE È NOTO, È IL CODICE A DECIDERE IL NOME.
    #
    # È la correzione alla radice di metà dei difetti di queste versioni.
    # L'identità del dispositivo si costruisce sul nome, ma le fonti
    # identificano i telefoni per codice — e il 17% dei codici ha più di un
    # nome: `CPH2423` è insieme «一加 10R», «OnePlus 10R» e «OnePlus 10R
    # 5G». Lo stesso telefono diventava tre dispositivi a seconda di quale
    # grafia era arrivata per prima.
    #
    # Normalizzare le grafie una per una — parole di marca, nomi cinesi,
    # parentesi, suffissi — è la partita che non si vince: le grafie sono
    # un dato della realtà. Passando dal codice, tutte le strade che
    # arrivano a quel telefono arrivano allo stesso nome.
    #
    # SOLO IL CODICE DICHIARATO DALLA FONTE, mai quello dedotto da una
    # build. Un codice letto dentro un numero di build è ottimo per
    # risolvere il chip, ma non basta a RINOMINARE un dispositivo: in una
    # notizia la build citata può appartenere a un altro modello nominato
    # nello stesso articolo, e il risultato sarebbe una scheda che cambia
    # nome da sola. Il codice dichiarato viene invece da una fonte che ha
    # interrogato proprio quel telefono.
    # Una fonte strutturata può già dichiarare un nome regionale preciso
    # (per esempio CPH2781 = OPPO A6 Pro in Europa). Il dataset dei codici
    # contiene anche rebrand di altri mercati (F31): usarlo per sovrascrivere
    # `raw.device` riporterebbe proprio il modello sbagliato. Il codice resta
    # il ripiego per le fonti che non pubblicano alcun nome.
    if raw.model_code and not raw.device:
        canonico = modelcodes.nome_canonico(raw.model_code)
        if canonico:
            model = canonico
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

    # La versione Android DEDOTTA dalla skin, quando la fonte non la dice.
    #
    # «One UI 5.1» da solo non risponde alla domanda che conta per un QA —
    # se il telefono ha cambiato major Android — ma la contiene: One UI 5
    # gira su Android 13. Dove la corrispondenza è univoca conviene
    # esplicitarla, invece di lasciare un campo vuoto accanto a un dato che
    # lo implica.
    #
    # Si deduce SOLO se la fonte non ha detto niente: un dato dichiarato
    # non viene mai sovrascritto da uno dedotto. E si deduce solo dove la
    # tabella è certa — MIUI, EMUI 11 e ColorOS vecchie restano vuote.
    dedotto_da_skin = False
    if data.android_version is None:
        implicata = skinmap.android_da_skin(data.skin_name, data.skin_version)
        if implicata is not None:
            data.android_version = implicata
            dedotto_da_skin = True

    # UNA NOTIZIA SENZA BUILD NON PUÒ DETTARE LA VERSIONE DI UN TELEFONO.
    #
    # È il difetto che ha prodotto «Samsung A32 · Android 14»: un articolo
    # che nomina un modello e una versione non è l'osservazione di un
    # rilascio, è un'opinione su un telefono. Poteva parlare di un
    # aggiornamento atteso, di un elenco di dispositivi ESCLUSI, o
    # semplicemente sbagliare.
    #
    # Il numero di build è ciò che distingue le due cose: esiste solo se
    # un pacchetto è stato davvero distribuito. Senza, l'item resta
    # visibile fra le notizie ma non porta più una versione, quindi non
    # può diventare la risposta alla domanda «a che versione sta questo
    # telefono».
    #
    # Vale SOLO per le fonti inaffidabili: le fonti ufficiali che danno la
    # versione senza build (rare ma esistono) non sono toccate.
    if source.trust == C.TRUST_NOISY and not data.build:
        # `os_version` è una proprietà calcolata da skin e Android:
        # si azzerano le fonti, non il risultato.
        data.android_version = None
        data.skin_name = None
        data.skin_version = None
        # Il livello di patch RESTA. È una rivendicazione più debole e
        # più verificabile: «ha ricevuto la patch di luglio» descrive un
        # fatto datato, mentre «Android 14» in un titolo parla quasi
        # sempre di attese, di idoneità o di elenchi di esclusi.

    os_version = data.os_version or (raw.version or "")
    if source.trust == C.TRUST_NOISY and not data.build:
        os_version = ""
    # `data.android_version` PUÒ essere stata appena azzerata dalla regola
    # qui sopra, e in quel caso non c'è nessuna versione da riscrivere.
    # Senza questa condizione l'etichetta diventava la stringa letterale
    # «Android None» — visibile in scheda dispositivo e in cronologia, dove
    # sembra un guasto dell'app e non lo è: è una notizia rumorosa che
    # nominava una skin e nessuna build, cioè proprio il caso in cui la
    # versione era stata tolta apposta.
    if dedotto_da_skin and not os_version and data.android_version is not None:
        os_version = f"Android {data.android_version}"
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
        # La chiave si costruisce sulla marca EFFETTIVAMENTE mostrata. Se il
        # produttore non si deduce, l'item veniva presentato sotto «Altri
        # brand» ma restava senza chiave: compariva nella ricerca e non
        # entrava mai nella lista dispositivi — riconosciuto e invisibile
        # insieme. Vale solo per le fonti strutturate, che il modello lo
        # hanno verificato: per una notizia un modello dedotto male
        # diventerebbe un dispositivo fantasma, ed è un problema aperto.
        "device_key": (
            extract.device_key(brand, model) if (brand and model)
            else (extract.device_key(C.OTHER, model)
                  if (model and source.trust == C.TRUST_STRUCTURED) else None)
        ),
        "title": raw.title,
        # IL CODICE DELLA VARIANTE, quando è noto.
        #
        # `app.py` lo leggeva già in due punti — per il chip nella tabella
        # dispositivi e nel riquadro di ricerca — ma NESSUNO lo scriveva:
        # due letture morte, e il chip ricadeva ogni volta sul nome
        # commerciale, che per un Galaxy S24 non può che rispondere «o
        # Exynos o Snapdragon». Il dato c'era (la fonte FOTA interroga
        # proprio un codice), si perdeva a metà strada.
        "model_code": raw.model_code or _codice_dal_build(data.build),
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
        # La fonte può essere autorevole senza rappresentare il firmware
        # corrente (per esempio AER o una scheda tecnica): conservarlo nel
        # record permette a storage e UI di non trasformarlo in un update.
        "firmware_kind": raw.firmware_kind or sources.firmware_kind_for(source),
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


def _ha_firmware(voce: dict) -> bool:
    """Questa voce dice davvero a che versione sta il telefono?

    Alcune fonti confermano che un modello ESISTE senza pubblicarne la
    versione (il catalogo Android Enterprise Recommended, l'elenco Oppo).
    Trattarle come una risposta piena è il modo più efficace di far credere
    di avere un dato che non c'è.
    """
    return bool(
        voce.get("firmware_kind") in (C.FW_CURRENT, C.FW_REPORTED)
        and (voce.get("os_version") or voce.get("build") or voce.get("patch_level"))
    )


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

    # Il SoC NON dipende dalla fonte che ha risposto sul firmware: si sa
    # comunque, e va allegato a qualunque risultato strutturato. Prima
    # veniva aggiunto solo nel ripiego «codice riconosciuto ma nessun
    # firmware»: bastava che una fonte rispondesse — cioè il caso
    # migliore — perché il chip sparisse dalla scheda.
    def _aggiungi_chip(item: dict, testo_cercato: str) -> None:
        if "soc" in (item.get("size_info") or "").lower():
            return
        chip = soc.per_modello(
            model_code=testo_cercato,
            device_name=item.get("device_model") or "",
        )
        if not chip:
            # Il codice può essere annegato nella build (`A325FXXSCDYB2`),
            # che spesso è l'unico posto dove compare.
            chip = soc.per_modello(model_code=item.get("build") or "")
        if not chip:
            return
        pezzi = [p for p in [(item.get("size_info") or "").strip(),
                             f"SoC {chip.etichetta}"] if p]
        item["size_info"] = " · ".join(pezzi)

    # 1) Fonte UFFICIALE del brand, interrogata a comando per questo modello.
    #    È il passaggio che rende la ricerca capace di dare un firmware reale
    #    anche per un modello mai visto prima dal giro periodico (situazione
    #    normale su Streamlit Cloud, dove il database si azzera a ogni
    #    riavvio del container).
    structured_items, structured_note = _lookup_structured_for(model_query)
    for item in structured_items:
        _aggiungi_chip(item, model_query)
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
    structured_relevant = [
        i for i in structured_items
        if i.get("is_relevant") and i.get("firmware_kind") == C.FW_CURRENT
    ]
    structured_reported = [
        i for i in structured_items
        if i.get("is_relevant") and i.get("firmware_kind") == C.FW_REPORTED
    ]
    rilevanti = [
        i for i in items
        if i.get("is_relevant") and i.get("firmware_kind") == C.FW_CURRENT
    ]
    riportati = [
        i for i in items
        if i.get("is_relevant") and i.get("firmware_kind") == C.FW_REPORTED
    ]
    identita = [i for i in items if i.get("is_relevant")]
    best = next(
        (i for i in structured_relevant if _ha_firmware(i)),
        next(
            (i for i in rilevanti if _ha_firmware(i)),
            (structured_relevant[0] if structured_relevant
             else (rilevanti[0] if rilevanti
                   else (structured_reported[0] if structured_reported
                         else (riportati[0] if riportati
                               else (identita[0] if identita else (items[0] if items else None)))))),
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


def forme_equivalenti(model_query: str) -> list[str]:
    """Tutte le forme sotto cui questo telefono può essere interrogato,
    dalla più vicina a ciò che è stato scritto alla più derivata.

    **LA STRADA MANCANTE ERA UNA SOLA, E ANDAVA IN UN VERSO SOLO.**
    Da un codice si arrivava al nome commerciale, ma da un nome NON si
    arrivava al codice: `_code_candidates` estrae solo i codici già scritti
    nel testo. Chi cercava «CPH2737» otteneva l'elenco ufficiale OPPO; chi
    cercava «oppo reno 14» — cioè lo stesso telefono chiamato come lo
    chiamano le persone — non otteneva nessuna fonte strutturata.

    È la terza volta che il progetto inciampa qui (v37, errore 32): una
    funzione che accetta due forme dello stesso input e ne guarda una sola.
    Il dataset sa già fare il percorso inverso — `codes_for_name` — e ora
    lo si usa.
    """
    forme: list[str] = [model_query]

    # 1) Il testo digitato COM'È, chiesto al dataset dei codici.
    #    `_code_candidates` filtra per FORMA (SM-…, CPH…, RMX…), e un codice
    #    che non somiglia a nessuna di quelle forme veniva scartato anche
    #    quando il dataset lo conosce alla lettera: `23129RAA4G` risolve in
    #    «Redmi Note 13», ma nessuno glielo chiedeva.
    #
    #    `resolve_senza_ambiguita`, NON `resolve`, per lo stesso motivo del
    #    punto 4 qui sotto: un nome che il dataset condivide fra più codici
    #    non deve diventare una forma di ricerca, perché una fonte ufficiale
    #    che risponde a quel nome potrebbe descrivere UN ALTRO telefono.
    forme.extend(modelcodes.resolve_senza_ambiguita(model_query))

    # 2) Codici scritti dentro un testo più lungo → nomi commerciali.
    for candidate_code in sources._code_candidates(model_query):
        forme.extend(modelcodes.resolve_senza_ambiguita(candidate_code))

    # 3) Nome → codici. È il verso che mancava.
    codici = _codici_riconoscibili(model_query)
    forme.extend(codici)

    # 4) Grafia ufficiale di quei codici: le fonti indicizzate per nome
    #    scrivono «OPPO Reno14», non «oppo reno 14».
    #
    #    SOLO I NOMI CHE NON SI CONFONDONO CON UN ALTRO TELEFONO. Cercando
    #    «realme c63» (RMX3939, verificato in `data/soc_modelli.csv`) questa
    #    riga aggiungeva anche «C61» fra le forme da provare: `resolve()`
    #    riporta quel nome anche per RMX3939, ma il dataset community lo
    #    riporta ALLO STESSO MODO anche per RMX3930 e RMX3933 — tre
    #    telefoni diversi con lo stesso nome scritto. La forma «C61»
    #    trovava poi il piano ufficiale Android Enterprise del vero C61
    #    (RMX3930, fonte Google) e lo sostituiva silenziosamente alla
    #    domanda su RMX3939: stesso bug del punto 1, sintomo misurato sul
    #    sito reale. `resolve_senza_ambiguita` tiene solo i nomi che
    #    risolvono a un solo codice — proprio questo — e scarta gli altri:
    #    si perde una via in più per trovare il firmware (raro), non si
    #    rischia più di mostrare il telefono sbagliato (frequente quanto
    #    basta per essere stato notato).
    for codice in codici[:C.SEARCH_MAX_CANDIDATES]:
        forme.extend(modelcodes.resolve_senza_ambiguita(codice))

    # LA MARCA SCRITTA NELLA DOMANDA VALE ANCHE PER LE FORME DERIVATE.
    #
    # `codes_for_name` è tollerante di proposito (suffissi, spazi), e su un
    # nome corto può restituire il codice di un'altra marca: «xiaomi 14»
    # arrivava anche a `RMX5075`, che è realme. Quella forma poi vinceva —
    # perché aveva il firmware e la forma giusta no — e la ricerca di uno
    # Xiaomi rispondeva con un realme.
    #
    # Lo scarto per marca sbagliata esisteva già, ma un livello più in là:
    # applicato ai risultati e non alle forme, arrivava troppo tardi.
    marca_chiesta = extract.detect_brand(model_query)

    viste, ordinate = set(), []
    for forma in forme:
        chiave = (forma or "").strip().lower()
        if not chiave or chiave in viste:
            continue
        if marca_chiesta and forma is not model_query:
            marca_forma = _marca_della_forma(forma)
            if marca_forma and marca_forma != marca_chiesta:
                continue
        viste.add(chiave)
        ordinate.append(forma)
    return ordinate


def _marca_della_forma(forma: str) -> str | None:
    """Di che marca è questa forma derivata, compresi i nomi cinesi.

    IL FILTRO SI FIDAVA DI DUE STRADE SOLE — il formato del codice e il
    riconoscimento del nome — e nessuna delle due sa leggere «真我 14».
    Una forma senza marca RICONOSCIBILE passava il filtro, e da lì si
    tornava a un realme: cercando «Xiaomi 14» il sito rispondeva
    «真我 14». Misurato interrogando il sito, non dedotto.

    È lo stesso difetto della v41, per una porta diversa: là la forma
    cinese arrivava dalla risoluzione di un codice, qui dal nome. La
    correzione di allora guardava i risultati; questa guarda le forme,
    che è un passo prima.

    `sources.gruppo_di_marca` i nomi cinesi li conosce già — 三星, 一加,
    小米, 真我 — e tace su quelli che non riconosce, che è esattamente il
    comportamento che serve: una marca ignota non deve far scartare
    niente.
    """
    marca = sources.brand_from_code(forma) or extract.detect_brand(forma)
    if marca:
        return marca
    prima = (forma or "").strip().split(" ")[0]
    return sources.gruppo_di_marca(prima) if prima else None


def _lookup_structured_for(model_query: str) -> tuple[list[dict], str | None]:
    """Interroga la fonte ufficiale del brand per il modello cercato,
    provando TUTTE le forme equivalenti: i nomi commerciali risolti da un
    codice (chi cerca 'ABR-LX1' deve ottenere il dato di 'HONOR X8c') e i
    codici risolti da un nome (chi cerca 'oppo reno 14' deve ottenere il
    dato di 'CPH2737')."""
    note = None
    ripiego: list[dict] | None = None   # forma che conferma il modello, senza versione
    # TETTO DI TEMPO COMPLESSIVO. Ogni forma provata è un giro completo di
    # fonti, ciascuno con il proprio budget: senza un tetto qui, allargare
    # l'elenco delle forme moltiplicava il caso peggiore, e una pagina che
    # resta in caricamento sembra bloccata (stessa ragione della nota in
    # `sources.search_model_live`).
    scadenza = time.monotonic() + C.SEARCH_BUDGET_SECONDS
    for name in forme_equivalenti(model_query):
        if time.monotonic() >= scadenza:
            break
        raw_items, lookup_note = sources.lookup_model_structured(name)
        note = note or lookup_note
        # LA MARCA DELLA DOMANDA VALE FINO IN FONDO.
        #
        # Le forme derivate perdono la marca per strada: «xiaomi 14»
        # risolve anche al nome cinese «真我 14», che non contiene niente
        # di riconoscibile — e da lì si torna a realme. La forma vince
        # perché ha il firmware, e la ricerca di uno Xiaomi risponde con un
        # realme. Il filtro esisteva già dentro `lookup_model_structured`,
        # ma lì la domanda è la FORMA, non quella originale: è qui che si
        # sa ancora cosa aveva scritto la persona.
        raw_items = sources._scarta_marca_sbagliata(
            raw_items, extract.detect_brand(model_query))
        if raw_items:
            # La forma che ha risposto, se è un codice, È il codice della
            # variante: va allegata al risultato, o il chip ricadrebbe sul
            # nome commerciale anche quando sappiamo esattamente di quale
            # esemplare stiamo parlando.
            if sources.looks_like_model_code(name):
                codice = sources.normalizza_codice_modello(name)
                for raw in raw_items:
                    if not raw.model_code:
                        raw.model_code = codice
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
                # I lookup registrati hanno già marcato ogni RawItem.
                # Il default CURRENT preserva invece le integrazioni esterne
                # e i test che restituiscono un RawItem di firmware senza
                # conoscere ancora questo campo; i ripieghi di sola identità
                # lo dichiarano esplicitamente più sotto come SUPPORT.
                firmware_kind=raw_items[0].firmware_kind or C.FW_CURRENT,
            )
            normalizzati = [normalize(raw, source) for raw in raw_items]
            # SI SCEGLIE LA FORMA CHE HA IL FIRMWARE, NON LA PRIMA CHE
            # RISPONDE. È la regola che `lookup_model_structured` applica
            # già fra le sue fonti, e che qui — fra le forme equivalenti —
            # mancava: cercando `23129RAA4G` il catalogo Android Enterprise
            # riconosceva il codice e ci si fermava lì, con un «Redmi Note
            # 13» senza versione, mentre la forma successiva («Redmi Note
            # 13») avrebbe trovato la build reale nel catalogo Xiaomi.
            # Stesso telefono, due schede diverse a seconda di come lo si
            # cercava.
            if any(_ha_firmware(voce) for voce in normalizzati):
                return normalizzati, None
            if ripiego is None:
                ripiego = normalizzati

    if ripiego:
        return ripiego, note

    # ULTIMA SPIAGGIA: nessuna fonte firmware conosce questo modello, ma il
    # codice potrebbe essere comunque riconoscibile.
    #
    # Il progetto ha già in casa ~70.000 codici modello (MobileModels e la
    # lista Google Play) e un modulo che sa quale chip monta un dispositivo.
    # Prima, se le fonti firmware tacevano, tutto questo restava inutilizzato
    # e la ricerca rispondeva «niente» — dando l'impressione che l'app fosse
    # rotta, quando in realtà sapeva benissimo di che telefono si trattava e
    # semplicemente non ne conosceva l'aggiornamento.
    #
    # Sono due domande diverse e vanno risposte separatamente:
    #   «che telefono è?»          → quasi sempre rispondibile
    #   «a che firmware sta?»      → dipende dal produttore
    identificato = _identifica_senza_firmware(model_query)
    if identificato:
        return identificato, note
    return [], note


def _codici_riconoscibili(model_query: str) -> list[str]:
    """Codici modello a cui questa ricerca può arrivare.

    NON SOLO QUELLI SCRITTI. Prima si guardava solo se il testo digitato
    *era* un codice: chi scriveva `CPH2333` otteneva «OPPO A96
    riconosciuto», chi scriveva `oppo a96` — cioè il nome commerciale, il
    modo normale di chiamarlo — non otteneva niente. Stessa domanda, stesso
    telefono, due risposte diverse, e quella sbagliata era per la forma più
    naturale.

    Il dataset sa già fare il percorso inverso: dal nome ai codici. Qui lo
    si usa, così una ricerca per nome vale quanto una per codice.
    """
    codici = list(sources._code_candidates(model_query))
    for forma in sources.expand_query(model_query):
        for codice in modelcodes.codes_for_name(forma):
            if codice not in codici:
                codici.append(codice)
    return codici


def _identifica_senza_firmware(model_query: str) -> list[dict]:
    """Riconosce il dispositivo senza saperne il firmware.

    Restituisce un item SENZA versione, build o patch: l'interfaccia lo
    distingue già da un risultato completo e mostra il ramo «riconosciuto,
    ma questa fonte non pubblica la versione firmware». Riempirlo di campi
    inventati per farlo sembrare un risultato pieno sarebbe il contrario
    di quello che serve.

    ## La marca chiesta vale anche qui

    `codes_for_name` è tollerante di proposito, e su un nome corto
    restituisce codici di marche diverse: per «Xiaomi 14» il PRIMO è
    `RMX5075`, che è un realme. La ragione è che la chiave normalizzata
    di «Xiaomi 14» e quella di «真我 14» sono entrambe `14` — la marca
    esce dalla chiave e i caratteri cinesi pure.

    Il filtro per marca esisteva già in `forme_equivalenti`, ma questa
    funzione non passa di là: prende i codici e si ferma al primo che
    risolve. Risultato misurato: cercando «Xiaomi 14» il sito rispondeva
    «真我 14». È l'errore 51b del passaggio consegne — una correzione
    applicata in un posto e non cercata negli altri.
    """
    marca_chiesta = extract.detect_brand(model_query)
    for codice in _codici_riconoscibili(model_query):
        nomi = modelcodes.resolve(codice)
        if not nomi:
            continue
        if marca_chiesta:
            marca_codice = (sources.brand_from_code(codice)
                            or _marca_della_forma(nomi[0]))
            if marca_codice and marca_codice != marca_chiesta:
                continue
        # IL NOME LO SCEGLIE `nome_canonico`, NON L'ORDINE DELLA LISTA.
        #
        # `resolve` restituisce tutte le grafie che i dataset conoscono
        # per quel codice, e la prima può essere quella cinese: cercando
        # «Xiaomi 14» il sito rispondeva «真我 14». `nome_canonico` esiste
        # apposta — mette l'alfabeto latino davanti ai caratteri cinesi e
        # sceglie sempre allo stesso modo — ed è la funzione che il resto
        # del progetto usa già per la stessa domanda. Qui era rimasto un
        # `nomi[0]`, cioè «il primo che capita».
        nome = modelcodes.nome_canonico(codice) or nomi[0]
        pulito = sources.normalizza_codice_modello(codice)
        descrizione = [f"Codice modello riconosciuto ({pulito})"]
        chip = soc.per_modello(pulito, nome)
        if chip:
            descrizione.append(f"SoC {chip.etichetta}")

        raw = sources.RawItem(
            title=f"{nome} ({pulito})",
            link="",
            brand=sources.brand_from_code(pulito) or sources.brand_from_known_device(nome),
            device=nome,
            size_info=" · ".join(descrizione),
            trust=C.TRUST_STRUCTURED,
        )
        source = sources.Source(
            key="official_lookup",
            label="Riconoscimento del codice modello (ricerca diretta)",
            trust=C.TRUST_STRUCTURED,
            fetch=None,
            brand=raw.brand,
            homepage="",
            firmware_kind=C.FW_SUPPORT,
        )
        return [normalize(raw, source)]
    return []


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
