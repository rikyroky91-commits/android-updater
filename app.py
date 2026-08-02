"""Universal Mobile Update Tracker — dashboard Streamlit.

Copre Android (Samsung, Xiaomi, Pixel, Honor, Motorola, Oppo/OnePlus, vivo,
brand minori) e iOS/iPadOS (iPhone, iPad) con la stessa pipeline.

Avvio:  streamlit run app.py
"""
from __future__ import annotations

import os

import streamlit as st

st.set_page_config(page_title="Universal Mobile Update Tracker", page_icon="📱", layout="wide")

# I segreti di Streamlit diventano variabili d'ambiente PRIMA di importare il
# core, così lo stesso codice gira identico anche da worker standalone.
for _key in (
    "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TRACKER_DB", "SCAN_INTERVAL_MINUTES",
    "RELEVANCE_THRESHOLD", "NOTIFY_MIN_SEVERITY", "NOTIFY_ONLY_WATCHLIST",
    "EXTRA_FEEDS", "DISABLED_SOURCES", "RETENTION_DAYS",
):
    try:
        if _key in st.secrets and st.secrets[_key] not in (None, ""):
            os.environ.setdefault(_key, str(st.secrets[_key]))
    except Exception:
        pass

import pandas as pd  # noqa: E402

from core import config as C, extract, notify, scan, sources, storage  # noqa: E402
from core import images  # noqa: E402
from core import imeicheck  # noqa: E402
from core import modelcodes  # noqa: E402
from core import appledevices  # noqa: E402
from core import backup  # noqa: E402
from core import suggest  # noqa: E402
from core.classify import qa_impact  # noqa: E402
from core.util import days_since, fmt_date, fmt_dt, fmt_relative, truncate  # noqa: E402

# ======================================================================
# Sistema visivo
# ======================================================================
# Direzione: interfaccia MONOCROMATICA, con il colore riservato
# esclusivamente al significato di stato (rosso/ambra/verde della
# severità). In uno strumento diagnostico il colore è un segnale: ogni
# tinta decorativa entra in concorrenza con quello che deve essere letto
# al volo, e la pagina diventa rumorosa.
#
# Elemento caratterizzante: la stringa di build (S928BXXU5CYA1,
# AP4A.241205.013.B4). È l'artefatto proprio di questo mondo, e viene
# trattata come oggetto tipografico di prima classe — monospaziata,
# spaziata, su fondo tenue — invece che come testo qualsiasi.
st.markdown(
    """
    <style>
      :root {
        --ink:        #16191D;
        --ink-soft:   #5A6270;
        --ink-faint:  #8B93A1;
        --hairline:   #E4E7EC;
        --surface:    #F7F8FA;
      }

      /* Ritmo verticale: meno respiro sprecato, gerarchia più leggibile */
      .block-container { padding-top: 2.2rem; max-width: 1180px; }

      /* Testata */
      .app-title {
        font-size: 1.55rem; font-weight: 650; letter-spacing: -.022em;
        color: var(--ink); margin: 0 0 .15rem 0;
      }
      .app-sub { color: var(--ink-soft); font-size: .92rem; margin: 0 0 1.4rem 0; }

      /* Riga di stato: una sola riga discreta al posto di cinque riquadri */
      .statusline {
        display: flex; flex-wrap: wrap; gap: 1.4rem;
        padding: .7rem 0 .9rem 0; margin-bottom: 1.1rem;
        border-top: 1px solid var(--hairline);
        border-bottom: 1px solid var(--hairline);
        font-size: .85rem; color: var(--ink-soft);
      }
      .statusline b { color: var(--ink); font-weight: 600; }

      /* Elemento caratterizzante: la stringa di build */
      .build {
        font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
        font-size: .82rem; letter-spacing: .01em;
        background: var(--surface); border: 1px solid var(--hairline);
        border-radius: 5px; padding: .12rem .42rem; color: var(--ink);
        white-space: nowrap;
      }

      /* Etichetta minuta sopra un blocco: struttura, non decorazione */
      .eyebrow {
        text-transform: uppercase; letter-spacing: .09em;
        font-size: .7rem; font-weight: 600; color: var(--ink-faint);
        margin: 1.6rem 0 .5rem 0;
      }

      .muted { color: var(--ink-soft); font-size: .86rem; }

      /* Campo di ricerca: unico elemento davvero prominente della pagina */
      div[data-testid="stForm"] { border: 0; padding: 0; }
      div[data-testid="stForm"] input {
        font-size: 1.02rem !important; padding: .62rem .8rem !important;
      }

      /* Contenitori e immagini: angoli coerenti, ombre assenti */
      [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px !important; }
      [data-testid="stImage"] img { border-radius: 10px; }

      /* Le metriche residue non devono gridare */
      div[data-testid="stMetric"] { background: transparent; padding: 0; }
      div[data-testid="stMetricValue"] { font-size: 1.35rem; font-weight: 600; }
      div[data-testid="stMetricLabel"] { color: var(--ink-faint); }

      /* Tab: separati da una linea sottile, senza riempimenti pesanti */
      button[data-baseweb="tab"] { font-size: .93rem; }

      /* Colonna di monitoraggio: deve restare leggibile ma non competere
         con il contenuto. Testo minuto, nessun riempimento colorato. */
      .rail-head { font-size: .95rem; color: var(--ink); margin-bottom: .2rem; }
      .rail-source {
        font-size: .82rem; color: var(--ink); display: flex;
        justify-content: space-between; gap: .5rem; padding: .12rem 0;
      }
      .rail-count { color: var(--ink-faint); font-variant-numeric: tabular-nums; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ======================================================================
# Avvio del worker (una sola volta per processo)
# ======================================================================
@st.cache_resource(show_spinner=False)
def _worker():
    # ORDINE IMPORTANTE: il ripristino deve precedere init_db().
    # `init_db` crea un database vuoto se il file non c'è, e a quel punto
    # il ripristino non avverrebbe più (vedrebbe un database «già
    # presente» e si asterrebbe, per non sovrascrivere dati locali con una
    # copia più vecchia). Il file va quindi recuperato prima che qualcuno
    # lo crei.
    ripristinato = False
    try:
        ripristinato, _nota_ripristino = backup.ripristina(solo_se_mancante=True)
    except Exception:  # pragma: no cover - il ripristino non è critico
        pass

    storage.init_db()
    # I dati in archivio sono il risultato dell'interpretazione delle fonti:
    # se quella logica è stata corretta dopo l'ultimo popolamento, gli
    # aggiornamenti vecchi vanno rimossi o resterebbero visibili con i
    # valori sbagliati anche dopo la correzione (vedi
    # storage.rebuild_if_logic_changed).
    rimossi = storage.rebuild_if_logic_changed()
    ritirati = storage.purge_retired_sources([s.key for s in sources.all_sources()])
    return scan.start_background_worker(), rimossi, ritirati, ripristinato


_thread, _rimossi_logica, _rimossi_ritirate, _archivio_ripristinato = _worker()
if _archivio_ripristinato:
    st.success(
        "💾 Archivio ripristinato dal salvataggio esterno: lo storico degli "
        "aggiornamenti è sopravvissuto al riavvio."
    )
if _rimossi_logica or _rimossi_ritirate:
    st.info(
        "🔄 Archivio ricostruito dopo una correzione nella lettura delle fonti: "
        f"{_rimossi_logica + _rimossi_ritirate} voci obsolete rimosse. "
        "I dati corretti si ripopolano alla prossima scansione (o premendo "
        "«Scansiona adesso»). Watchlist e cronologia sono rimaste intatte."
    )


# ======================================================================
# Helper di presentazione
# ======================================================================
def freshness(last_update_at) -> str:
    days = days_since(last_update_at)
    if days is None:
        return "⚪ Mai visto"
    if days <= 7:
        return "🟢 Questa settimana"
    if days <= C.FRESH_DAYS:
        return "🟢 Recente"
    if days <= C.STALE_DAYS:
        return "🟡 In ritardo"
    return "🔴 Fermo"


def toggle_watch(device_key: str, brand: str, model: str, watched: bool) -> None:
    if watched:
        storage.remove_from_watchlist(device_key)
    else:
        storage.add_to_watchlist(device_key, brand, model)


def date_label(item: dict, published_key: str = "published", seen_key: str = "first_seen") -> str:
    """Data leggibile che dice chiaramente se è la data di uscita reale
    dell'aggiornamento o solo la data in cui la scansione l'ha rilevato per
    la prima volta (le due cose non sono la stessa cosa: alcune fonti come
    il controllo versione ufficiale Samsung/Honor non pubblicano una data
    di rilascio propria)."""
    if item.get(published_key):
        return fmt_date(item[published_key])
    return f"rilevato {fmt_relative(item.get(seen_key))}"


def render_update_row(item: dict, watched_keys: set[str], row_index: int = 0) -> None:
    """Una riga del feed aggiornamenti.

    `row_index` (la posizione nella lista, non l'id) garantisce una chiave
    Streamlit sempre unica anche se due righe condividessero per qualche
    motivo lo stesso `id` (es. dati residui da una versione precedente del
    database) — altrimenti Streamlit va in crash con
    StreamlitDuplicateElementKey invece di mostrare l'errore vero.
    """
    is_watched = item.get("device_key") in watched_keys
    with st.container(border=True):
        left, right = st.columns([5, 2])
        title = item.get("device_model") or truncate(item.get("title", ""), 90)
        star = "⭐ " if is_watched else ""
        if item.get("link"):
            left.markdown(f"{star}**[{title}]({item['link']})**")
        else:
            left.markdown(f"{star}**{title}**")

        details = []
        if item.get("android_version"):
            details.append(f"Android {item['android_version']}")
        elif item.get("os_version"):
            details.append(item["os_version"])
        if item.get("os_version") and item["os_version"] not in details:
            details.append(item["os_version"])
        if item.get("build"):
            details.append(f"<span class='build'>{item['build']}</span>")
        if item.get("patch_level"):
            details.append(f"patch {item['patch_level']}")
        left.markdown(
            " · ".join(details) if details else f"_{truncate(item.get('title', ''), 120)}_",
            unsafe_allow_html=True,
        )
        left.caption(f"{item.get('brand', '')} · {item.get('source_label', '')} · {date_label(item)}")

        right.markdown(
            f"<span style='color:{item.get('color', '#888')};font-weight:600'>{item.get('severity', '')}</span>",
            unsafe_allow_html=True,
        )
        if item.get("severity_reason"):
            right.caption(item["severity_reason"])
        right.caption(qa_impact(item.get("severity", ""), is_watched))
        if item.get("link") and "GB" in (item.get("severity_reason") or ""):
            left.caption("⬇️ Il link è il file firmware diretto (diversi GB), non una pagina: verifica i dati sopra, scaricalo solo se ti serve installarlo.")
        if right.button("Invia su Telegram", key=f"send_{row_index}_{item['id']}", use_container_width=True):
            ok, error = notify.send_update(item, is_watched)
            storage.log_notification(item, kind="manuale", ok=ok)
            if ok:
                storage.mark_notified(item["id"])
                st.toast("Notifica inviata.")
            else:
                st.error(f"Invio non riuscito — {error}")


# ======================================================================
# Intestazione
# ======================================================================
stats = storage.stats()
last = stats.get("last_scan") or {}
watched_keys = storage.watched_keys()

st.markdown(
    '<div class="app-title">Mobile Update Tracker</div>'
    '<div class="app-sub">Quale aggiornamento è arrivato, su quale modello, quando.</div>',
    unsafe_allow_html=True,
)

# Una riga di stato al posto di cinque riquadri: le stesse informazioni,
# ma senza cinque elementi che si contendono l'attenzione con la ricerca,
# che è l'unica cosa da cui si parte davvero.
st.markdown(
    '<div class="statusline">'
    f'<span><b>{stats.get("devices", 0)}</b> dispositivi</span>'
    f'<span><b>{stats.get("updates_relevant", 0)}</b> aggiornamenti</span>'
    f'<span><b>{len(watched_keys)}</b> nel parco di test</span>'
    f'<span>ultima scansione <b>{fmt_relative(last.get("finished_at"))}</b></span>'
    f'<span>+{last.get("new_items", 0)} nell\'ultimo giro</span>'
    '</div>',
    unsafe_allow_html=True,
)


# ======================================================================
# Ricerca unificata — modello, codice modello o IMEI, tutto in un campo
# ======================================================================
def avvia_ricerca(termine: str) -> None:
    """Fa partire una ricerca da un pulsante (suggerimento, ricerca recente,
    voce di catalogo) come se fosse stata digitata."""
    st.session_state["_ricerca_in_arrivo"] = termine
    st.rerun()


# Una ricerca avviata da un pulsante arriva da qui, non dal campo di testo.
_ricerca_da_pulsante = st.session_state.pop("_ricerca_in_arrivo", None)

with st.form("unified_search_form", clear_on_submit=False):
    fu1, fu2 = st.columns([5, 1])
    unified_query = fu1.text_input(
        "Cerca", placeholder="Cerca un modello, un codice (RMX3939, SM-S928B) o un IMEI",
        label_visibility="collapsed", max_chars=64,
        value=_ricerca_da_pulsante or "",
    )
    unified_submitted = fu2.form_submit_button("Cerca", use_container_width=True, type="primary")

if _ricerca_da_pulsante:
    unified_query = _ricerca_da_pulsante
    unified_submitted = True

# --- Completamenti mentre si scrive ------------------------------------
# Streamlit non rilancia lo script a ogni tasto premuto: i suggerimenti
# compaiono quando il campo perde il fuoco o si preme Invio. Restano utili
# lo stesso, perché il caso frequente è scrivere un nome quasi giusto.
if unified_query and not unified_submitted and len(unified_query.strip()) >= 2:
    completamenti = suggest.suggest(unified_query.strip(), limit=6)
    if completamenti:
        st.caption("Forse stai cercando:")
        colonne = st.columns(min(len(completamenti), 3))
        for indice, nome in enumerate(completamenti):
            if colonne[indice % len(colonne)].button(
                nome, key=f"sugg_{indice}_{nome}", use_container_width=True
            ):
                avvia_ricerca(nome)

def render_search_outcome(display_name: str, live_result: dict) -> None:
    """Mostra prima il dato più preciso disponibile, poi l'esito della
    verifica su notizie — l'ordine conta: un dato da fonte ufficiale
    (Samsung FOTA, Honor, catalogo Xiaomi, mirror Motorola) è sempre più
    affidabile di una notizia, anche quando la ricerca online non trova
    nulla di nuovo in questo momento."""
    # 1) Dato appena ottenuto interrogando a comando la fonte ufficiale del
    #    brand: è la risposta migliore possibile e va mostrata per prima.
    structured = [i for i in live_result.get("items", []) if i.get("source") == "official_lookup"]
    if structured:
        best = structured[0]
        pezzi = []
        if best.get("android_version"):
            pezzi.append(f"**Android {best['android_version']}**")
        elif best.get("os_version"):
            pezzi.append(f"**{best['os_version']}**")
        if best.get("os_version") and best["os_version"] not in pezzi:
            pezzi.append(best["os_version"])
        if best.get("build"):
            pezzi.append(f"build `{best['build']}`")
        if best.get("patch_level"):
            pezzi.append(f"patch {best['patch_level']}")
        # ONESTÀ DEL RISULTATO. Alcune fonti confermano che un modello
        # esiste ma NON pubblicano la versione firmware (è il caso
        # dell'elenco Oppo). Dichiarare «dato trovato» in quel caso è
        # peggio che non trovare nulla: fa credere di avere una risposta
        # che non c'è. Qui i due casi vengono detti in modo diverso.
        nome_mostrato = best.get("device_model") or display_name
        fonte = best.get("source_label", "")
        if pezzi:
            st.success(
                f"✅ **{nome_mostrato}** — " + " · ".join(pezzi)
                + f"  \n*Fonte: {fonte}*"
            )
        else:
            st.warning(
                f"**{nome_mostrato}** riconosciuto, ma **questa fonte non "
                f"pubblica la versione firmware**: conferma solo che il "
                f"modello esiste e la finestra di supporto."
                f"  \n*Fonte: {fonte}*"
            )
        if best.get("size_info") and "FABBRICA" in (best["size_info"] or "").upper():
            st.caption(
                "⚠️ Questa è la versione **di fabbrica**, non necessariamente "
                "quella installata oggi dopo gli aggiornamenti."
            )

    device = live_result.get("existing_device")
    if device and not structured:
        firmware = (
            device.get("os_version")
            or (f"build `{device['build']}`" if device.get("build") else None)
            or (f"patch {device['patch_level']}" if device.get("patch_level") else None)
            or "—"
        )
        fonte = "dato ufficiale/strutturato" if live_result.get("existing_is_structured") else "da notizie già raccolte"
        st.success(
            f"**{device['brand']} {device['model']}** — fermo a **{firmware}**, "
            f"aggiornato **{fmt_relative(device['last_update_at'])}** ({fonte})."
        )

    news_items = [i for i in live_result.get("items", []) if i.get("source") != "official_lookup"]
    if news_items:
        rilevanti = sum(1 for i in news_items if i["is_relevant"])
        st.caption(
            f"Verifica online: {len(news_items)} notizie trovate, "
            f"{rilevanti} riconosciute come rilascio reale."
        )
    elif not structured and not device:
        dettaglio = f" ({live_result['error']})" if live_result.get("error") else ""
        nota = live_result.get("structured_note")
        st.warning(
            f"Nessun dato trovato per «{display_name}»{dettaglio}, e il modello "
            "non è ancora nel catalogo."
            + (f"  \n*Fonte ufficiale: {nota}*" if nota else "")
        )
        # Il motivo più comune di una ricerca a vuoto non è che il modello
        # manchi, ma che il nome sia scritto in modo leggermente diverso
        # («galaxi s24», «redmi note13»). Qui si propongono i nomi noti più
        # somiglianti, cliccabili per ripetere subito la ricerca.
        proposte = suggest.did_you_mean(display_name, limit=5)
        if not proposte:
            proposte = suggest.suggest(display_name, limit=5)
        if proposte:
            st.markdown("**Forse cercavi:**")
            colonne = st.columns(min(len(proposte), 3))
            for indice, nome in enumerate(proposte):
                if colonne[indice % len(colonne)].button(
                    nome, key=f"forse_{indice}_{nome}", use_container_width=True
                ):
                    avvia_ricerca(nome)
    elif not structured and live_result.get("structured_note"):
        st.caption(f"ℹ️ Fonte ufficiale del produttore: {live_result['structured_note']}")


active_search = ""
if unified_submitted and unified_query.strip():
    query = unified_query.strip()
    if imeicheck.is_valid_imei(query):
        found = imeicheck.identify(query)
        if not found:
            st.warning(
                f"IMEI valido ma codice non trovato nel database ({imeicheck.status()}). "
                "Può capitare per modelli molto recenti o rari."
            )
        else:
            brand_found, specs = found
            dettagli = imeicheck.parse_specs(brand_found, specs)
            model_from_imei = dettagli["model"]
            descrizione = imeicheck.describe(brand_found, specs)
            st.info(f"IMEI riconosciuto: **{descrizione}**")
            with st.spinner(f"Verifico «{model_from_imei}»…"):
                live_result = scan.search_model(model_from_imei)
            render_search_outcome(model_from_imei, live_result)
            active_search = model_from_imei
    else:
        with st.spinner(f"Verifico «{query}»…"):
            live_result = scan.search_model(query)
        render_search_outcome(query, live_result)
        active_search = query

search_history = storage.get_search_history(30)

# --- Ricerche recenti, ripetibili con un clic --------------------------
# Ripetere un controllo su un modello già cercato è l'operazione più
# frequente in un flusso di QA: non deve costare il riscrivere il nome.
if search_history and not unified_submitted:
    recenti = list(dict.fromkeys(h["model"] for h in search_history if h.get("model")))[:6]
    if recenti:
        st.caption("Ricerche recenti:")
        colonne = st.columns(min(len(recenti), 6))
        for indice, nome in enumerate(recenti):
            if colonne[indice % len(colonne)].button(
                nome, key=f"recente_{indice}_{nome}", use_container_width=True
            ):
                avvia_ricerca(nome)

# --- Sfoglia per marca -------------------------------------------------
# Non tutti ricordano il nome esatto del proprio telefono: i portali di
# settore offrono sempre anche una via d'ingresso per navigazione, non
# solo la ricerca testuale.
_catalogo_per_marca = suggest.brands_with_devices()
if _catalogo_per_marca:
    totale_modelli = sum(len(v) for v in _catalogo_per_marca.values())
    with st.expander(f"📚 Sfoglia il catalogo ({totale_modelli} modelli)", expanded=False):
        marca_scelta = st.selectbox(
            "Marca", list(_catalogo_per_marca), key="sfoglia_marca",
        )
        modelli = _catalogo_per_marca.get(marca_scelta, [])
        st.caption(f"{len(modelli)} modelli in archivio per {marca_scelta}")
        for riga_inizio in range(0, min(len(modelli), 24), 3):
            colonne = st.columns(3)
            for offset, nome in enumerate(modelli[riga_inizio:riga_inizio + 3]):
                if colonne[offset].button(
                    nome, key=f"sfoglia_{riga_inizio}_{offset}_{nome}",
                    use_container_width=True,
                ):
                    avvia_ricerca(nome)
        if len(modelli) > 24:
            st.caption(f"…e altri {len(modelli) - 24}. Usa la ricerca per arrivarci direttamente.")

if search_history:
    with st.expander(f"🕐 Cronologia ricerche ({len(search_history)})", expanded=False):
        hist_table = pd.DataFrame([
            {
                "Modello": h["model"],
                "Firmware": h["firmware"] or "—",
                "Cercato": fmt_relative(h["searched_at"]),
            }
            for h in search_history
        ])
        st.dataframe(hist_table, hide_index=True, use_container_width=True, height=240)
        if st.button("Svuota cronologia ricerche"):
            storage.clear_search_history()
            st.rerun()


# ======================================================================
# Filtri — sotto la ricerca, non più in una sidebar separata
# ======================================================================
with st.expander("Filtri", expanded=False):
    ff1, ff2, ff3 = st.columns(3)
    brand_filter = ff1.multiselect("Brand", C.BRANDS, default=[])
    severity_filter = ff2.multiselect(
        "Severità", C.SEVERITY_ORDER, default=[],
        format_func=lambda s: s,
    )
    window = ff3.select_slider(
        "Finestra temporale (Aggiornamenti/Diagnostica)",
        options=[7, 14, 30, 60, 90, 180, 365], value=90,
        format_func=lambda d: f"ultimi {d} giorni",
    )
    ff4, ff5 = st.columns(2)
    strict = ff4.toggle(
        "Modalità rigorosa", value=True,
        help="Mostra solo ciò che il filtro riconosce come rilascio reale. "
             "Disattivala per vedere anche gli scarti e capire perché lo sono.",
    )
    only_watched = ff5.toggle("Solo il parco di test", value=False)
    st.caption(
        f"Notifiche automatiche: da **{C.NOTIFY_MIN_SEVERITY}** in su, più tutti i device "
        f"nel parco di test. Intervallo scansione: {C.SCAN_INTERVAL_MINUTES} min."
    )

if not active_search:
    active_search = ""


# Le metriche e il pulsante di scansione vivono ora nella colonna di
# monitoraggio a destra: qui erano un terzo posto in cui leggere gli stessi
# numeri già presenti nella riga di stato.
if not C.notify_enabled():
    st.warning(
        "Telegram non è configurato: la dashboard funziona, ma non riceverai notifiche. "
        "Aggiungi `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` ai secrets."
    )


# ======================================================================
# Panoramica ultimi 30 giorni — sotto la ricerca, non più la prima cosa
# ======================================================================
def render_panoramica() -> None:
    """Sintesi degli ultimi 30 giorni, basata solo su date di uscita reali."""
    overview_items_raw = storage.get_updates(only_relevant=True, since_days=30, limit=500)
    # Solo gli item con una VERA data di pubblicazione entrano nella
    # panoramica: prima di questa correzione, gli item privi di data
    # (es. i controlli di stato ufficiali Samsung/Honor, che non
    # pubblicano una data di rilascio per ogni release) venivano
    # "datati" al momento della scansione, facendo sembrare tutto
    # concentrato su un solo giorno — la panoramica mostrava quando
    # l'app aveva guardato, non quando l'aggiornamento era davvero uscito.
    overview_items = [i for i in overview_items_raw if not i.get("published_is_estimated")]
    esclusi = len(overview_items_raw) - len(overview_items)

    if not overview_items:
        st.info(
            "Nessun aggiornamento con una data di rilascio nota negli ultimi 30 giorni. "
            + (f"({esclusi} item senza data reale esclusi qui, ma restano visibili nelle "
               "schede dispositivo.) " if esclusi else "")
            + "Lancia una scansione qui sopra per popolare la panoramica."
        )
    else:
        overview_df = pd.DataFrame(overview_items)
        sev_counts = overview_df["severity"].value_counts()

        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Aggiornamenti con data nota (30 gg)", len(overview_items))
        o2.metric("🔴 Major", int(sev_counts.get(C.SEV_MAJOR, 0)))
        o3.metric("🟡 Feature", int(sev_counts.get(C.SEV_FEATURE, 0)))
        o4.metric("🟢 Patch/Security", int(sev_counts.get(C.SEV_SECURITY, 0)))
        if esclusi:
            st.caption(
                f"ℹ️ {esclusi} aggiornamento/i senza una data di rilascio reale (es. controlli di "
                "stato ufficiali) non sono conteggiati qui per non falsare le date — restano "
                "comunque visibili nelle singole schede dispositivo."
            )

        overview_df["giorno"] = overview_df["published"].str.slice(0, 10)
        chart_col, list_col = st.columns([2, 3])

        with chart_col:
            st.caption("Aggiornamenti per giorno di uscita (30 gg)")
            by_day = overview_df.groupby("giorno").size().sort_index()
            st.bar_chart(by_day, height=280)

        with list_col:
            st.caption("In evidenza — i più recenti (data di uscita reale)")
            highlights = sorted(
                overview_items, key=lambda i: i.get("published") or "", reverse=True,
            )[:6]
            for h in highlights:
                with st.container(border=True):
                    hc1, hc2 = st.columns([4, 2])
                    label = h.get("device_model") or truncate(h.get("title", ""), 70)
                    if h.get("link"):
                        hc1.markdown(f"**[{label}]({h['link']})**")
                    else:
                        hc1.markdown(f"**{label}**")
                    dettagli = " · ".join(filter(None, [
                        h.get("brand"),
                        (f"Android {h['android_version']}" if h.get("android_version")
                         else (h.get("os_version") or None)),
                        (f"<span class='build'>{h['build']}</span>" if h.get("build") else None),
                    ]))
                    hc1.markdown(
                        f"<span class='muted'>{dettagli or '—'}</span>",
                        unsafe_allow_html=True,
                    )
                    hc2.markdown(
                        f"<span style='color:{h.get('color', '#888')};font-weight:600'>"
                        f"{h['severity']}</span>",
                        unsafe_allow_html=True,
                    )
                    hc2.caption(fmt_date(h.get("published")))


# ======================================================================
# Tab
# ======================================================================
def render_dispositivi() -> None:
    """Elenco dei modelli con lo stato software attuale, e scheda del singolo."""
    devices = storage.get_devices(brands=brand_filter or None, search=active_search or None)
    if only_watched:
        devices = [d for d in devices if d["watched"]]
    if severity_filter:
        devices = [d for d in devices if d["severity"] in severity_filter]

    if not devices:
        st.info(
            "Nessun dispositivo ancora riconosciuto con questi filtri. Cerca un modello "
            "qui sopra, oppure lancia una scansione completa dall'alto della pagina."
        )
    else:
        fresh = sum(1 for d in devices if (days_since(d["last_update_at"]) or 999) <= 7)
        stale = sum(1 for d in devices if (days_since(d["last_update_at"]) or 999) > C.STALE_DAYS)
        d1, d2, d3 = st.columns(3)
        d1.metric("Modelli in elenco", len(devices))
        d2.metric("Aggiornati negli ultimi 7 giorni", fresh)
        d3.metric(f"Fermi da oltre {C.STALE_DAYS} giorni", stale)

        table = pd.DataFrame([
            {
                "⭐": "⭐" if d["watched"] else "",
                "Brand": d["brand"],
                "Modello": d["model"],
                "Sistema": (f"Android {d['android_version']}" if d.get("android_version")
                            else (d["os_version"] or "—")),
                "Versione completa": d["os_version"] or "—",
                "Build": d["build"] or "—",
                "Patch": d["patch_level"] or "—",
                "Ultimo aggiornamento": fmt_date(d["last_update_at"]),
                "Quando": fmt_relative(d["last_update_at"]),
                "Stato": freshness(d["last_update_at"]),
                "Tipo": d["severity"],
                "30 gg": d["updates_30d"],
                "90 gg": d["updates_90d"],
                "Fonte": d["link"] or "",
            }
            for d in devices
        ])
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={"Fonte": st.column_config.LinkColumn("Fonte", display_text="🔗 apri")},
        )

        st.markdown('<div class="eyebrow">Scheda dispositivo</div>', unsafe_allow_html=True)
        options = {f"{d['brand']} · {d['model']}": d for d in devices}
        option_labels = list(options)
        default_index = 0
        if unified_submitted and active_search:
            match = next(
                (i for i, d in enumerate(devices) if active_search.lower() in d["model"].lower()),
                None,
            )
            if match is not None:
                default_index = match
        chosen = st.selectbox("Apri lo storico di", option_labels, index=default_index)
        device = options[chosen]

        with st.container(border=True):
            img_col, info_col = st.columns([1, 3])
            with img_col:
                photo_url = images.find_device_image(f"{device['brand']} {device['model']}")
                if photo_url:
                    st.image(photo_url, use_container_width=True)
                else:
                    st.markdown(
                        "<div style='display:flex;align-items:center;justify-content:center;"
                        "height:140px;border-radius:14px;background:rgba(127,127,127,.08);"
                        "font-size:2.6rem;'>📱</div>",
                        unsafe_allow_html=True,
                    )

            with info_col:
                info_col.markdown(f"### {device['model']}")
                info_col.caption(device["brand"])
                s1b, s2, s3, s4 = info_col.columns(4)
                s1b.metric(
                    "Sistema",
                    f"Android {device['android_version']}" if device.get("android_version")
                    else (device["os_version"] or "—"),
                )
                s2.metric("Versione completa", device["os_version"] or "—")
                s3.metric("Ultimo aggiornamento", fmt_relative(device["last_update_at"]))
                s4.metric("Update ultimi 90 gg", device["updates_90d"])

                identificativi = []
                if device["build"]:
                    identificativi.append(f"build <span class='build'>{device['build']}</span>")
                if device["patch_level"]:
                    identificativi.append(f"patch <span class='build'>{device['patch_level']}</span>")
                if identificativi:
                    info_col.markdown(" · ".join(identificativi), unsafe_allow_html=True)
                info_col.markdown(
                    f"**Stato:** {freshness(device['last_update_at'])} — "
                    f"{qa_impact(device['severity'], bool(device['watched']))}"
                )

                b1, b2 = info_col.columns(2)
                watch_label = "Rimuovi dal parco di test" if device["watched"] else "⭐ Aggiungi al parco di test"
                if b1.button(watch_label, key=f"watch_{device['device_key']}", use_container_width=True):
                    toggle_watch(device["device_key"], device["brand"], device["model"], bool(device["watched"]))
                    st.rerun()
                if b2.button("🔄 Verifica adesso", key=f"refresh_{device['device_key']}", use_container_width=True,
                             help="Ricontrolla online se c'è qualcosa di più recente per questo modello."):
                    with st.spinner(f"Verifico «{device['model']}»…"):
                        refresh_result = scan.search_model(device["model"])
                    if refresh_result["items"]:
                        st.success(f"Trovate {len(refresh_result['items'])} notizie aggiornate.")
                        st.rerun()
                    else:
                        st.info("Nessuna novità trovata rispetto a quanto già in archivio.")

        history = storage.get_device_history(device["device_key"])
        st.markdown(f"**Storico ({len(history)} rilevazioni)**")
        for entry in history:
            with st.container(border=True):
                head, tail = st.columns([5, 2])
                label = entry.get("os_version") or truncate(entry.get("title", ""), 80)
                if entry.get("link"):
                    head.markdown(f"[{label}]({entry['link']})")
                else:
                    head.markdown(label)
                extras = [x for x in (entry.get("build"), entry.get("patch_level")) if x]
                if extras:
                    head.caption(" · ".join(extras))
                head.caption(f"{entry.get('source_label', '')} — {truncate(entry.get('title', ''), 110)}")
                tail.markdown(
                    f"<span style='color:{entry.get('color', '#888')};font-weight:600'>{entry.get('severity', '')}</span>",
                    unsafe_allow_html=True,
                )
                tail.caption(date_label(entry))


    # ----------------------------------------------------------------------
    # TAB 2 — Feed aggiornamenti
    # ----------------------------------------------------------------------


def render_aggiornamenti() -> None:
    """Flusso cronologico degli aggiornamenti, ordinato per data di uscita."""
    items = storage.get_updates(
        brands=brand_filter or None,
        severities=severity_filter or None,
        only_relevant=strict,
        since_days=window,
        search=active_search or None,
        limit=300,
    )
    if only_watched:
        items = [i for i in items if i.get("device_key") in watched_keys]
    # Rete di sicurezza: se due fonti diverse producessero per errore lo
    # stesso id, qui si tiene solo la prima occorrenza invece di mostrare
    # (e provare a dare la stessa key a) la riga due volte.
    seen_ids: set[str] = set()
    deduped = []
    for i in items:
        if i["id"] not in seen_ids:
            seen_ids.add(i["id"])
            deduped.append(i)
    items = deduped

    if not items:
        st.info("Nessun aggiornamento corrisponde ai filtri. Allarga la finestra temporale o togli qualche filtro.")
    else:
        st.caption(f"{len(items)} aggiornamenti negli ultimi {window} giorni.")
        export = pd.DataFrame([
            {
                "Brand": i["brand"],
                "Modello": i["device_model"] or "",
                "Sistema": (f"Android {i['android_version']}" if i.get("android_version")
                            else (i["os_version"] or "")),
                "Versione": i["os_version"] or "",
                "Build": i["build"] or "",
                "Patch level": i["patch_level"] or "",
                "Severità": i["severity"],
                "Pubblicato": fmt_dt(i["published"]) if not i.get("published_is_estimated") else "",
                "Rilevato": fmt_dt(i["first_seen"]),
                "Fonte": i["source_label"],
                "Link": i["link"] or "",
                "Titolo": i["title"],
                "Rilevanza": i["relevance_score"],
            }
            for i in items
        ])
        st.download_button(
            "⬇️ Esporta in CSV",
            data=export.to_csv(index=False).encode("utf-8"),
            file_name="android_updates.csv",
            mime="text/csv",
        )
        for idx, item in enumerate(items[:120]):
            render_update_row(item, watched_keys, row_index=idx)
        if len(items) > 120:
            st.caption(f"Mostrati i 120 più recenti su {len(items)}. Usa i filtri per restringere.")


    # ----------------------------------------------------------------------
    # TAB 3 — Parco di test
    # ----------------------------------------------------------------------


def render_parco() -> None:
    """Parco dispositivi di test: modelli seguiti con notifica su ogni update."""
    st.markdown(
        "Segna qui i modelli su cui provi la tua app: ricevi una notifica per **ogni** "
        "aggiornamento che li riguarda, anche quando è solo una patch di sicurezza."
    )
    watchlist = storage.get_watchlist()

    add1, add2, add3 = st.columns([2, 3, 1])
    new_brand = add1.selectbox("Brand", C.BRANDS, key="wl_brand")
    new_model = add2.text_input("Modello", placeholder="es. Galaxy S24 Ultra", key="wl_model")
    add3.markdown("<br>", unsafe_allow_html=True)
    if add3.button("Aggiungi", use_container_width=True):
        if new_model.strip():
            model = extract.canonical_device(new_model)
            storage.add_to_watchlist(extract.device_key(new_brand, model), new_brand, model)
            st.success(f"{model} aggiunto al parco di test.")
            st.rerun()
        else:
            st.error("Scrivi il nome del modello.")

    if not watchlist:
        st.info("Il parco di test è vuoto. Aggiungi un modello qui sopra o dalla scheda dispositivo.")
    else:
        if st.button("🔄 Verifica ora tutto il parco di test", use_container_width=True,
                     help="Controlla online, uno per uno, tutti i modelli del parco di test."):
            progress = st.progress(0.0)
            status_ph = st.empty()
            trovati_totali = 0
            for i, entry in enumerate(watchlist):
                status_ph.caption(f"Verifico {entry['model']}…")
                esito = scan.search_model(entry["model"])
                trovati_totali += len(esito["items"])
                progress.progress((i + 1) / len(watchlist))
            progress.empty()
            status_ph.empty()
            st.success(
                f"Verifica completata su {len(watchlist)} modelli: "
                f"{trovati_totali} notizie trovate in totale."
            )
            st.rerun()

        summary = {d["device_key"]: d for d in storage.get_devices()}
        for entry in watchlist:
            device = summary.get(entry["device_key"])
            with st.container(border=True):
                col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
                col1.markdown(f"**{entry['model']}**")
                col1.caption(entry["brand"])
                if device:
                    col2.markdown(
                        f"Android {device['android_version']}" if device.get("android_version")
                        else (device["os_version"] or "—")
                    )
                    col2.caption(f"build {device['build'] or '—'} · patch {device['patch_level'] or '—'}")
                    col3.markdown(freshness(device["last_update_at"]))
                    col3.caption(fmt_relative(device["last_update_at"]))
                else:
                    col2.caption("Nessun aggiornamento rilevato finora per questo modello.")
                    col3.markdown("⚪ In attesa")
                if col4.button("🔄", key=f"verify_{entry['device_key']}", use_container_width=True,
                               help="Verifica ora questo modello"):
                    with st.spinner(f"Verifico «{entry['model']}»…"):
                        scan.search_model(entry["model"])
                    st.rerun()
                if col5.button("🗑️", key=f"rm_{entry['device_key']}", use_container_width=True,
                               help="Rimuovi dal parco di test"):
                    storage.remove_from_watchlist(entry["device_key"])
                    st.rerun()


    # ----------------------------------------------------------------------
    # TAB 4 — Diagnostica
    # ----------------------------------------------------------------------


def render_diagnostica_completa() -> None:
    """Diagnostica estesa: storico scansioni, scarti del filtro, manutenzione."""
    st.markdown('<div class="eyebrow">Stato delle fonti</div>', unsafe_allow_html=True)
    status = storage.get_source_status()
    if not status:
        st.info("Nessuna scansione eseguita finora.")
    else:
        st.dataframe(
            pd.DataFrame([
                {
                    "Stato": ("🔴 Errore" if not s["ok"]
                              else "🟠 Impoverita" if s.get("degrado") else "🟢 OK"),
                    "Fonte": s["label"],
                    "Item": s["items_found"],
                    "Di norma": (s["degrado"]["atteso"] if s.get("degrado") else "—"),
                    "Ultimo controllo": fmt_relative(s["checked_at"]),
                    "Ultimo successo": fmt_relative(s["last_ok_at"]),
                    "Dettaglio": truncate(
                        s["last_error"] or (s["degrado"]["messaggio"] if s.get("degrado") else ""),
                        140),
                }
                for s in status
            ]),
            hide_index=True,
            use_container_width=True,
        )

    if status:
        with st.expander("Andamento di una fonte nel tempo", expanded=False):
            st.caption(
                "Quante voci ha restituito una fonte nelle ultime scansioni. "
                "Serve a capire QUANDO è iniziato un calo: un guasto di formato "
                "si vede come un gradino netto, non come un'oscillazione."
            )
            etichette = {s["label"]: s["source"] for s in status}
            scelta = st.selectbox("Fonte", list(etichette), key="andamento_fonte")
            storico = storage.get_source_history(etichette[scelta], limit=20)
            if len(storico) < 2:
                st.caption("Storico troppo breve: servono almeno due scansioni.")
            else:
                serie = pd.DataFrame({
                    "voci": [r["items_found"] for r in reversed(storico)],
                }, index=[fmt_dt(r["recorded_at"]) for r in reversed(storico)])
                st.line_chart(serie, height=200)

    st.markdown('<div class="eyebrow">Ultime scansioni</div>', unsafe_allow_html=True)
    scans = storage.get_scans(10)
    if scans:
        st.dataframe(
            pd.DataFrame([
                {
                    "Quando": fmt_relative(s["started_at"]),
                    "Durata": f"{(s['duration_s'] or 0):.0f}s",
                    "Trovati": s["total_found"],
                    "Nuovi": s["new_items"],
                    "Notifiche": s["notifications"],
                    "Errore": truncate(s["error"] or "", 80),
                }
                for s in scans
            ]),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown('<div class="eyebrow">Cosa ha scartato il filtro</div>', unsafe_allow_html=True)
    st.caption("Serve a tarare le parole chiave: se qui trovi rilasci veri, il filtro è troppo severo.")
    discarded = [i for i in storage.get_updates(only_relevant=False, since_days=window, limit=400)
                 if not i["is_relevant"]]
    if not discarded:
        st.success("Nessuno scarto nella finestra selezionata.")
    else:
        st.dataframe(
            pd.DataFrame([
                {
                    "Titolo": truncate(i["title"], 90),
                    "Fonte": i["source_label"],
                    "Punteggio": i["relevance_score"],
                    "Motivo": truncate(i["relevance_note"], 90),
                }
                for i in discarded[:100]
            ]),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown('<div class="eyebrow">Notifiche inviate</div>', unsafe_allow_html=True)
    notifications = storage.get_notifications(40)
    if not notifications:
        st.caption("Nessuna notifica inviata finora.")
    else:
        for record in notifications:
            icon = "✅" if record["ok"] else "⚠️"
            label = f"[{record['device']}]({record['link']})" if record["link"] else record["device"]
            st.write(
                f"{icon} **{record['brand']}** — {label} · {record['version']} · "
                f"{record['severity']} · {record['kind']} · {fmt_dt(record['sent_at'])}"
            )

    st.markdown('<div class="eyebrow">Perché una ricerca non trova nulla</div>',
                unsafe_allow_html=True)
    st.caption(
        "Mostra passo per passo cosa succede cercando un modello: se il testo "
        "è stato riconosciuto come codice, in quali nomi è stato risolto, quali "
        "fonti sono state interrogate e cosa ha risposto ciascuna."
    )
    with st.form("diagnosi_query"):
        dq1, dq2 = st.columns([5, 1])
        query_da_diagnosticare = dq1.text_input(
            "Modello", placeholder="es. CPH2819", label_visibility="collapsed")
        diagnosi_richiesta = dq2.form_submit_button("Analizza", use_container_width=True)

    if diagnosi_richiesta and query_da_diagnosticare.strip():
        with st.spinner("Ripercorro la ricerca…"):
            passi = sources.diagnose_query(query_da_diagnosticare.strip())

        st.markdown(f"**Esito:** {passi['esito']}")
        dd1, dd2 = st.columns(2)
        dd1.markdown(
            f"Riconosciuto come codice: **{'sì' if passi['ha_forma_di_codice'] else 'no'}**  \n"
            f"Brand dedotto: **{passi['brand_dedotto'] or '—'}**"
        )
        dd2.markdown(
            "Forme provate:  \n" + ("  \n".join(f"· {f}" for f in passi["forme_provate"]) or "—")
        )
        if passi["nomi_risolti"]:
            for voce in passi["nomi_risolti"]:
                st.caption(f"«{voce['codice']}» risolto in: {', '.join(voce['nomi'])}")
        elif passi["ha_forma_di_codice"]:
            st.warning(
                "Il testo ha la forma di un codice, ma nessun dataset lo conosce: "
                "è il motivo più probabile per cui la ricerca non arriva al modello. "
                "Prova a cercare il nome commerciale."
            )

        st.dataframe(
            pd.DataFrame([
                {
                    "Fonte": f["fonte"],
                    "Trovati": f["trovati"],
                    "Dispositivo": f.get("dispositivo", "—"),
                    "Errore": truncate(f["errore"] or "", 90),
                }
                for f in passi["fonti"]
            ]),
            hide_index=True, use_container_width=True,
        )

    st.markdown('<div class="eyebrow">Persistenza dell\'archivio</div>',
                unsafe_allow_html=True)

    if backup.configurato():
        info = backup.stato()
        st.success("💾 L'archivio sopravvive ai riavvii.")
        st.markdown(
            f"<div class='muted'>Ultimo esito: {info['ultimo_esito']}<br>"
            f"Ultimo salvataggio: {fmt_relative(info['ultimo_salvataggio'])} · "
            f"ultimo ripristino: {fmt_relative(info['ultimo_ripristino'])}</div>",
            unsafe_allow_html=True,
        )
        b1, b2, b3 = st.columns(3)
        if b1.button("Salva ora", use_container_width=True):
            ok, messaggio = backup.salva()
            st.success(messaggio) if ok else st.error(messaggio)
        if b2.button("Ripristina", use_container_width=True,
                     help="Sovrascrive il database locale con l'ultimo salvataggio."):
            ok, messaggio = backup.ripristina(solo_se_mancante=False)
            st.success(messaggio + " — ricarica la pagina.") if ok else st.error(messaggio)
        if b3.button("Verifica che funzioni", use_container_width=True):
            with st.spinner("Scrivo e rileggo un dato di prova…"):
                ok, messaggio = backup.prova_completa(
                    C.env("BACKUP_GIST_ID"), C.env("BACKUP_GITHUB_TOKEN"))
            st.success(messaggio) if ok else st.error(messaggio)
    else:
        st.warning(
            "**L'archivio non sopravvive ai riavvii.** Su questo tipo di hosting il "
            "disco è temporaneo: a ogni riavvio o sospensione lo storico riparte da "
            "zero. Si configura una volta sola, qui sotto."
        )

        st.markdown("**Serve solo un token GitHub.** Al resto pensa l'app.")
        st.markdown(
            "1. Apri [github.com/settings/tokens/new](https://github.com/settings/tokens/new?scopes=gist&description=Mobile%20Update%20Tracker) "
            "— il permesso «gist» è già selezionato\n"
            "2. In fondo alla pagina premi **Generate token**\n"
            "3. Copia il token che compare (inizia con `ghp_`) e incollalo qui sotto"
        )

        with st.form("configura_archivio"):
            token_inserito = st.text_input(
                "Token GitHub", type="password", placeholder="ghp_…",
                help="Non viene salvato dall'app: serve solo per creare l'archivio.",
            )
            crea = st.form_submit_button("Crea l'archivio", type="primary")

        if crea and token_inserito.strip():
            with st.spinner("Verifico il token e creo l'archivio…"):
                ok, messaggio, gist_id = backup.crea_archivio(token_inserito.strip())
            if not ok:
                st.error(messaggio)
            else:
                st.success("Archivio creato. Manca un ultimo passaggio.")
                st.markdown(
                    "Copia queste due righe e incollale nei **secrets** dell'app "
                    "(su Streamlit Cloud: menu ⋮ → *Settings* → *Secrets*), poi riavvia:"
                )
                st.code(
                    f'BACKUP_GIST_ID = "{gist_id}"\n'
                    f'BACKUP_GITHUB_TOKEN = "{token_inserito.strip()}"',
                    language="toml",
                )
                st.caption(
                    "Questo passaggio non può farlo l'app: i secrets sono l'unico posto "
                    "dove un token può stare al sicuro, e solo tu puoi scriverci."
                )
                with st.spinner("Verifico che l'archivio funzioni…"):
                    ok_prova, messaggio_prova = backup.prova_completa(
                        gist_id, token_inserito.strip())
                st.success(messaggio_prova) if ok_prova else st.warning(messaggio_prova)

    st.markdown('<div class="eyebrow">Manutenzione</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    if t1.button("Prova il canale Telegram", use_container_width=True):
        ok, error = notify.send_test()
        st.success("Messaggio di prova inviato.") if ok else st.error(f"Invio non riuscito — {error}")
    if t2.button(f"Elimina i dati oltre {C.RETENTION_DAYS} giorni", use_container_width=True):
        removed = storage.purge_old()
        st.success(f"Eliminati {removed} record.")
    if t3.button("Azzera stato notifiche", use_container_width=True,
                 help="Rimanda al prossimo giro le notifiche già inviate."):
        count = storage.clear_notified()
        st.success(f"Azzerato lo stato di {count} item.")
    st.caption(f"Database: `{stats['db_path']}` · {stats['updates_total']} record totali")

    st.divider()
    d1, d2 = st.columns([3, 1])
    d1.caption(f"Database codici modello (RMX3939 → nome commerciale): {modelcodes.status()}")
    d1.caption(f"Database dispositivi Apple (iPhone16,1 → iPhone 15 Pro): {appledevices.status()}")
    if d2.button("Ricarica ora", use_container_width=True,
                 help="Forza un nuovo tentativo di scaricare il database dei codici modello."):
        modelcodes.reset_cache()
        modelcodes.resolve("")  # forza il caricamento subito, cosi' lo stato si aggiorna
        st.rerun()



def render_diagnostica_rail() -> None:
    """Diagnostica sempre in vista, nella colonna di destra.

    Non è una scelta solo estetica: finché lo stato delle fonti è stato
    sepolto in una scheda da aprire apposta, una fonte rotta è rimasta
    rossa per giorni senza che nessuno se ne accorgesse. Un pannello di
    monitoraggio serve proprio a essere visto mentre si fa altro.
    """
    stati = storage.get_source_status()
    attive = len(stati)
    ok = sum(1 for s in stati if s["ok"])
    in_errore = [s for s in stati if not s["ok"]]
    # Fonti che rispondono senza errori ma rendono molto meno del solito:
    # è il guasto che non si vede, e che va mostrato accanto agli errori
    # veri invece che sepolto in un elenco.
    impoverite = [s for s in stati if s.get("degrado")]

    st.markdown('<div class="eyebrow">Diagnostica</div>', unsafe_allow_html=True)

    if not stati:
        st.caption("Nessuna scansione ancora eseguita.")
    else:
        if in_errore:
            pallino = "🔴"
        elif impoverite:
            pallino = "🟠"
        else:
            pallino = "🟢"
        riga = f"{pallino} <b>{ok}/{attive}</b> fonti attive"
        if impoverite:
            riga += f" · <b>{len(impoverite)}</b> impoverite"
        st.markdown(f"<div class='rail-head'>{riga}</div>", unsafe_allow_html=True)

    ultima = stats.get("last_scan") or {}
    if ultima.get("finished_at"):
        st.markdown(
            f"<div class='muted'>Ultima scansione {fmt_relative(ultima['finished_at'])} · "
            f"{ultima.get('total_found', 0)} voci, {ultima.get('new_items', 0)} nuove</div>",
            unsafe_allow_html=True,
        )
    prossima = scan.seconds_until_next_scan()
    if prossima:
        st.markdown(
            f"<div class='muted'>Prossima fra ~{prossima // 60} min</div>",
            unsafe_allow_html=True,
        )

    if st.button("Scansiona adesso", use_container_width=True, key="rail_scan"):
        with st.spinner("Interrogo le fonti…"):
            esito = scan.run_scan(auto_notify=True)
        if esito.get("skipped"):
            st.info("Scansione già in corso.")
        else:
            st.success(
                f"{esito['total']} voci · {esito['new']} nuove · "
                f"{esito['notifications']} notifiche"
            )
        st.rerun()

    # Le fonti in errore vengono per prime: sono l'unica cosa che richiede
    # un'azione, e non devono farsi cercare in fondo a un elenco.
    if impoverite:
        st.markdown('<div class="eyebrow">Rendono meno del solito</div>',
                    unsafe_allow_html=True)
        for fonte in impoverite:
            with st.container(border=True):
                degrado = fonte["degrado"]
                st.markdown(
                    f"<div class='rail-source'>🟠 {fonte['label']}</div>"
                    f"<div class='muted'>{degrado['attuale']} voci invece di "
                    f"{degrado['atteso']} (−{degrado['calo_percentuale']}%)<br>"
                    "risponde senza errori: probabile cambio di formato</div>",
                    unsafe_allow_html=True,
                )

    if in_errore:
        st.markdown('<div class="eyebrow">Da controllare</div>', unsafe_allow_html=True)
        for fonte in in_errore:
            with st.container(border=True):
                st.markdown(
                    f"<div class='rail-source'>🔴 {fonte['label']}</div>"
                    f"<div class='muted'>{truncate(fonte['last_error'] or '', 110)}</div>",
                    unsafe_allow_html=True,
                )

    if stati:
        with st.expander(f"Tutte le fonti ({attive})", expanded=False):
            for fonte in sorted(stati, key=lambda s: (s["ok"], s["label"])):
                icona = "🟢" if fonte["ok"] else "🔴"
                st.markdown(
                    f"<div class='rail-source'>{icona} {fonte['label']}"
                    f"<span class='rail-count'>{fonte['items_found']}</span></div>",
                    unsafe_allow_html=True,
                )

    st.markdown('<div class="eyebrow">Archivio</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='muted'>{stats.get('updates_relevant', 0)} aggiornamenti · "
        f"{stats.get('devices', 0)} dispositivi<br>"
        f"{stats.get('notifications', 0)} notifiche inviate</div>",
        unsafe_allow_html=True,
    )


def render_catalogo() -> None:
    """Dispositivi e aggiornamenti in una vista sola.

    Erano due schede separate, ma raccontano la stessa cosa da due angoli:
    «a che punto è ogni modello» e «cosa è uscito di recente». Tenerle
    divise costringeva a saltare avanti e indietro per rispondere a una
    domanda sola. Qui restano due raggruppamenti dello stesso insieme, con
    un interruttore invece di due schede.
    """
    vista = st.segmented_control(
        "Vista", ["Per dispositivo", "Cronologia"],
        default="Per dispositivo", label_visibility="collapsed",
        key="vista_catalogo",
    ) or "Per dispositivo"

    if vista == "Per dispositivo":
        render_dispositivi()
    else:
        render_panoramica()
        st.markdown('<div class="eyebrow">Tutti gli aggiornamenti</div>',
                    unsafe_allow_html=True)
        render_aggiornamenti()


# ======================================================================
# Impianto della pagina: contenuto a sinistra, monitoraggio a destra
# ======================================================================
colonna_principale, colonna_stato = st.columns([3.2, 1], gap="large")

with colonna_principale:
    scheda_catalogo, scheda_parco = st.tabs(["Dispositivi e aggiornamenti", "Parco di test"])
    with scheda_catalogo:
        render_catalogo()
    with scheda_parco:
        render_parco()

with colonna_stato:
    render_diagnostica_rail()

with st.expander("Diagnostica estesa", expanded=False):
    render_diagnostica_completa()
