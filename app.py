"""Universal Mobile Update Tracker — dashboard Streamlit.

Copre Android (Samsung, Xiaomi, Pixel, Honor, Motorola, Oppo/OnePlus, vivo,
brand minori) e iOS/iPadOS (iPhone, iPad) con la stessa pipeline.

Avvio:  streamlit run app.py
"""
from __future__ import annotations

import os

import streamlit as st

st.set_page_config(
    page_title="Universal Mobile Update Tracker",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# I segreti di Streamlit diventano variabili d'ambiente PRIMA di importare il
# core, così lo stesso codice gira identico anche da worker standalone.
for _key in (
    "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TRACKER_DB", "SCAN_INTERVAL_MINUTES",
    "RELEVANCE_THRESHOLD", "NOTIFY_MIN_SEVERITY", "NOTIFY_ONLY_WATCHLIST",
    "EXTRA_FEEDS", "DISABLED_SOURCES", "RETENTION_DAYS",
    "BACKUP_GIST_ID", "BACKUP_GITHUB_TOKEN", "BACKUP_URL",
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
from core import retest  # noqa: E402
from core import soc  # noqa: E402
from core.classify import qa_impact  # noqa: E402
from core.util import days_since, fmt_date, fmt_dt, fmt_relative, truncate  # noqa: E402

# ======================================================================
# Sistema visivo
# ======================================================================
# DUE REGOLE, e la prima è la correzione di un difetto vero.
#
# 1. NESSUN COLORE DI TESTO O DI SFONDO CABLATO. La versione precedente
#    fissava una tavolozza chiara (`--ink: #16191D`, `--surface: #F7F8FA`).
#    Con Streamlit in tema scuro il risultato era testo quasi nero su fondo
#    quasi nero — contrasto misurato 1.05:1, cioè illeggibile — e riquadri
#    bianchi accecanti. Qui i toni si ricavano da `currentColor` e da grigi
#    semitrasparenti: si adattano da soli a QUALUNQUE tema, senza doverlo
#    rilevare e senza poter sbagliare.
#
# 2. IL COLORE È RISERVATO AL SIGNIFICATO. L'unico colore pieno è quello
#    della severità (rosso/ambra/verde/blu). In uno strumento diagnostico
#    ogni tinta decorativa compete con il segnale che va letto al volo.
#
# Elemento caratterizzante: la stringa di build (S928BXXU5CYA1,
# AP4A.241205.013.B4), trattata come oggetto tipografico di prima classe —
# monospaziata, su fondo tenue — invece che come testo qualsiasi.
st.markdown(
    """
    <style>
      :root {
        /* Grigi neutri semitrasparenti: funzionano identici in chiaro e in
           scuro, perché prendono il colore da ciò che hanno sotto. */
        --hairline: rgba(128, 128, 128, 0.30);
        --surface:  rgba(128, 128, 128, 0.10);
      }

      .block-container { padding-top: 2rem; max-width: 1240px; }

      /* --- Testata ---------------------------------------------------- */
      .app-title {
        font-size: 1.5rem; font-weight: 650; letter-spacing: -.022em;
        margin: 0 0 .1rem 0;            /* nessun `color`: eredita dal tema */
      }
      .app-sub {
        font-size: .92rem; margin: 0 0 1.2rem 0;
        color: color-mix(in srgb, currentColor 72%, transparent);
      }

      /* --- Testo attenuato --------------------------------------------
         `color-mix` verso `transparent` schiarisce sul fondo scuro e
         scurisce sul chiaro: è il modo più semplice di avere un grigio
         corretto in entrambi i temi senza sapere quale sia attivo. */
      .muted {
        font-size: .86rem;
        color: color-mix(in srgb, currentColor 72%, transparent);
      }
      .faint { color: color-mix(in srgb, currentColor 62%, transparent); }

      /* --- Riga di stato ------------------------------------------------ */
      /* Il tono attenuato va sulle ETICHETTE, non sul contenitore: messo
         sul contenitore, i numeri lo ereditavano via `currentColor` e non
         c'era modo di recuperare il colore pieno — la gerarchia spariva e
         il dato pesava quanto la sua didascalia. */
      .statusline {
        display: flex; flex-wrap: wrap; gap: 1.5rem;
        padding: .7rem 0 .8rem 0; margin-bottom: 1.1rem;
        border-top: 1px solid var(--hairline);
        border-bottom: 1px solid var(--hairline);
        font-size: .85rem;
      }
      .statusline .lbl { color: color-mix(in srgb, currentColor 72%, transparent); }
      .statusline b { font-weight: 650; font-variant-numeric: tabular-nums; }
      .statusline .n { font-size: 1.05rem; }

      /* --- Stringa di build --------------------------------------------- */
      .build {
        font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
        font-size: .82rem; letter-spacing: .01em;
        background: var(--surface); border: 1px solid var(--hairline);
        border-radius: 5px; padding: .1rem .4rem; white-space: nowrap;
      }

      /* --- Etichetta di sezione ----------------------------------------- */
      .eyebrow {
        text-transform: uppercase; letter-spacing: .09em;
        font-size: .7rem; font-weight: 650;
        color: color-mix(in srgb, currentColor 72%, transparent);
        margin: 1.5rem 0 .5rem 0;
      }

      /* --- Ricerca: unico elemento davvero prominente -------------------- */
      div[data-testid="stForm"] { border: 0; padding: 0; }
      div[data-testid="stForm"] input {
        font-size: 1.02rem !important; padding: .6rem .8rem !important;
      }

      /* --- Contenitori --------------------------------------------------- */
      [data-testid="stImage"] img { border-radius: 10px; }
      [data-testid="stMetric"] { background: transparent; padding: 0; }
      [data-testid="stMetricValue"] { font-size: 1.3rem; font-weight: 650; }

      /* --- Schede ---------------------------------------------------------
         I NOMI DEI SELETTORI VANNO VERIFICATI SUL DOM, NON RICORDATI.
         Qui c'era `button[data-baseweb="tab"]`, che in Streamlit 1.60 non
         corrisponde a niente: le schede sono `div[data-testid="stTab"]`.
         La regola era morta, e le schede restavano scritte nude senza
         nessun segno di essere cliccabili — è la ragione per cui
         sembravano testo. */
      [data-testid="stTabs"] [role="tablist"] {
        border-bottom: 1px solid var(--hairline);
        gap: .15rem;
      }
      [data-testid="stTab"] {
        font-size: .95rem;
        padding: .1rem .7rem !important;
        border-radius: 8px 8px 0 0;
        transition: background-color .12s ease;
      }
      /* Lo stato al passaggio del mouse è ciò che dice «questo si preme». */
      [data-testid="stTab"]:hover { background: var(--surface); }

      /* --- Pannello laterale --------------------------------------------- */
      .rail-row {
        font-size: .84rem; display: flex; justify-content: space-between;
        gap: .5rem; padding: .14rem 0;
      }
      .rail-count {
        font-variant-numeric: tabular-nums;
        color: color-mix(in srgb, currentColor 72%, transparent);
      }
      .rail-head { font-size: .95rem; margin-bottom: .15rem; }

      /* --- Primo avvio ---------------------------------------------------- */
      .onboard {
        border: 1px solid var(--hairline); border-radius: 12px;
        background: var(--surface); padding: 1.1rem 1.2rem;
        margin: .3rem 0 1rem 0;
      }
      .onboard h3 { margin: 0 0 .35rem 0; font-size: 1.05rem; font-weight: 650; }
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
    # il ripristino non avverrebbe più (vedrebbe un database «già presente»
    # e si asterrebbe, per non sovrascrivere dati locali con una copia più
    # vecchia). Il file va recuperato prima che qualcuno lo crei.
    ripristinato = False
    try:
        ripristinato, _nota = backup.ripristina(solo_se_mancante=True)
    except Exception:  # pragma: no cover - il ripristino non è critico
        pass

    storage.init_db()
    # I dati in archivio sono il RISULTATO dell'interpretazione delle fonti:
    # se quella logica è stata corretta dopo l'ultimo popolamento, gli
    # aggiornamenti vecchi vanno rimossi o resterebbero visibili con i
    # valori sbagliati anche dopo la correzione.
    rimossi = storage.rebuild_if_logic_changed()
    ritirati = storage.purge_retired_sources([s.key for s in sources.all_sources()])
    return scan.start_background_worker(), rimossi, ritirati, ripristinato


_thread, _rimossi_logica, _rimossi_ritirate, _archivio_ripristinato = _worker()


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


def blocco_retest(device: dict, chiave: str) -> dict:
    """Confronto con l'ultima baseline di test, più i comandi per aggiornarla.

    È la risposta alla domanda che il QA si pone davvero — non «a che
    versione è», ma «è cambiato qualcosa da quando l'ho provato». Restituisce
    l'esito del confronto perché chi chiama possa usarlo anche altrove
    (contatori, ordinamento) senza ricalcolarlo.
    """
    esito = retest.confronta(device, storage.get_test_baseline(device["device_key"]))
    riga = esito["etichetta"]
    if esito["tested_at"]:
        riga += f" · provato {fmt_relative(esito['tested_at'])}"
    st.markdown(riga)

    if esito["riassunto"]:
        st.caption(esito["riassunto"])
    st.caption(esito["azione"])
    if esito["stato"] == retest.INCOERENTE:
        st.warning(
            "Una versione che retrocede non è un aggiornamento: è un dato "
            "sbagliato. Controlla la fonte nello storico qui sotto prima di "
            "decidere se ritestare."
        )
    if esito["mancanti"]:
        st.caption(
            "Non più pubblicato da nessuna fonte: " + ", ".join(esito["mancanti"])
            + " — è un buco di copertura, non un cambiamento del telefono."
        )

    c1, c2 = st.columns(2)
    etichetta = ("✅ Ho ritestato adesso" if esito["tested_at"]
                 else "✅ Segna come testato adesso")
    if c1.button(etichetta, key=f"baseline_{chiave}_{device['device_key']}",
                 use_container_width=True,
                 help="Fotografa la versione attuale: da qui in poi il "
                      "confronto parte da questo momento."):
        storage.set_test_baseline(device)
        st.rerun()
    if esito["tested_at"] and c2.button(
            "Dimentica la baseline", key=f"nobase_{chiave}_{device['device_key']}",
            use_container_width=True):
        storage.clear_test_baseline(device["device_key"])
        st.rerun()
    return esito


def date_label(item: dict, published_key: str = "published",
               seen_key: str = "first_seen") -> str:
    """Data leggibile che distingue la data di uscita reale da quella in cui
    la scansione l'ha rilevata: alcune fonti (il controllo versione ufficiale
    Samsung o Honor) non pubblicano una data di rilascio propria."""
    if item.get(published_key):
        return fmt_date(item[published_key])
    return f"rilevato {fmt_relative(item.get(seen_key))}"


def severity_html(item: dict) -> str:
    return (f"<span style='color:{item.get('color', '#888')};font-weight:650'>"
            f"{item.get('severity', '')}</span>")


def avvia_ricerca(termine: str) -> None:
    """Fa partire una ricerca da un pulsante (suggerimento, ricerca recente,
    voce di catalogo) come se fosse stata digitata."""
    st.session_state["_ricerca_in_arrivo"] = termine
    st.rerun()


def bottoniera(nomi: list[str], prefisso: str, per_riga: int = 3) -> None:
    """Elenco di nomi cliccabili che rilanciano la ricerca."""
    if not nomi:
        return
    colonne = st.columns(min(len(nomi), per_riga))
    for indice, nome in enumerate(nomi):
        if colonne[indice % len(colonne)].button(
            nome, key=f"{prefisso}_{indice}_{nome}", use_container_width=True
        ):
            avvia_ricerca(nome)


def render_update_row(item: dict, watched_keys: set[str], row_index: int = 0) -> None:
    """Una riga del feed aggiornamenti.

    `row_index` (la posizione nella lista, non l'id) garantisce una chiave
    Streamlit sempre unica anche se due righe condividessero per qualche
    motivo lo stesso `id` — altrimenti Streamlit va in crash con
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
        left.caption(f"{item.get('brand', '')} · {item.get('source_label', '')} · "
                     f"{date_label(item)}")

        right.markdown(severity_html(item), unsafe_allow_html=True)
        if item.get("severity_reason"):
            right.caption(item["severity_reason"])
        right.caption(qa_impact(item.get("severity", ""), is_watched))
        if item.get("link") and "GB" in (item.get("severity_reason") or ""):
            left.caption(
                "⬇️ Il link è il file firmware diretto (diversi GB), non una pagina: "
                "verifica i dati sopra, scaricalo solo se ti serve installarlo."
            )
        if right.button("Invia su Telegram", key=f"send_{row_index}_{item['id']}",
                        use_container_width=True):
            ok, error = notify.send_update(item, is_watched)
            storage.log_notification(item, kind="manuale", ok=ok)
            if ok:
                storage.mark_notified(item["id"])
                st.toast("Notifica inviata.")
            else:
                st.error(f"Invio non riuscito — {error}")


# ======================================================================
# Dati comuni a tutta la pagina
# ======================================================================
stats = storage.stats()
last_scan = stats.get("last_scan") or {}
watched_keys = storage.watched_keys()
stati_fonti = storage.get_source_status()
# «Vuoto» vuol dire NESSUN DISPOSITIVO, non «nessuna scansione». La
# condizione precedente guardava anche `finished_at`: una scansione che
# finiva senza trovare niente contava come archivio pieno, e la pagina
# mostrava cinque zeri affiancati invece della spiegazione. Il caso è tutt'
# altro che raro — è esattamente quello che si vede al primo giro.
archivio_vuoto = not stats.get("devices")
mai_scansionato = not last_scan.get("finished_at")


# ======================================================================
# Pannello laterale — stato, azioni, avvisi
# ======================================================================
# Perché nella sidebar e non in una colonna stretta a destra, com'era: a
# larghezze normali quella colonna riceveva meno di 300 px e i suoi
# contenuti si accavallavano. La sidebar ha una larghezza propria, si
# richiude, e su schermo stretto scorre sopra il contenuto invece di
# comprimerlo.
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="eyebrow" style="margin-top:0">Stato</div>',
                    unsafe_allow_html=True)

        in_errore = [s for s in stati_fonti if not s["ok"]]
        # Fonti che rispondono senza errori ma rendono molto meno del
        # solito: è il guasto che non si vede, e va mostrato accanto agli
        # errori veri invece che sepolto in un elenco.
        impoverite = [s for s in stati_fonti if s.get("degrado")]

        if not stati_fonti:
            st.markdown("<div class='muted'>Nessuna scansione ancora eseguita.</div>",
                        unsafe_allow_html=True)
        else:
            ok = sum(1 for s in stati_fonti if s["ok"])
            pallino = "🔴" if in_errore else ("🟠" if impoverite else "🟢")
            riga = f"{pallino} <b>{ok}/{len(stati_fonti)}</b> fonti attive"
            if impoverite:
                riga += f" · {len(impoverite)} impoverite"
            st.markdown(f"<div class='rail-head'>{riga}</div>", unsafe_allow_html=True)

        if last_scan.get("finished_at"):
            st.markdown(
                f"<div class='muted'>Ultima scansione {fmt_relative(last_scan['finished_at'])} · "
                f"{last_scan.get('total_found', 0)} voci, "
                f"{last_scan.get('new_items', 0)} nuove</div>",
                unsafe_allow_html=True,
            )
        prossima = scan.seconds_until_next_scan()
        if prossima:
            st.markdown(f"<div class='muted'>Prossima fra ~{prossima // 60} min</div>",
                        unsafe_allow_html=True)

        if st.button("Scansiona adesso", use_container_width=True, key="rail_scan"):
            with st.spinner("Interrogo le fonti…"):
                esito = scan.run_scan(auto_notify=True)
            if esito.get("skipped"):
                st.info("Scansione già in corso.")
            else:
                st.success(f"{esito['total']} voci · {esito['new']} nuove · "
                           f"{esito['notifications']} notifiche")
            st.rerun()

        # Le fonti che richiedono un'azione vengono per prime: non devono
        # farsi cercare in fondo a un elenco.
        if impoverite:
            st.markdown('<div class="eyebrow">Rendono meno del solito</div>',
                        unsafe_allow_html=True)
            for fonte in impoverite:
                degrado = fonte["degrado"]
                st.markdown(
                    f"<div class='rail-row'>🟠 {fonte['label']}</div>"
                    f"<div class='muted'>{degrado['attuale']} voci invece di "
                    f"{degrado['atteso']} (−{degrado['calo_percentuale']}%) — risponde "
                    "senza errori: probabile cambio di formato</div>",
                    unsafe_allow_html=True,
                )

        if in_errore:
            st.markdown('<div class="eyebrow">Da controllare</div>', unsafe_allow_html=True)
            for fonte in in_errore:
                st.markdown(
                    f"<div class='rail-row'>🔴 {fonte['label']}</div>"
                    f"<div class='muted'>{truncate(fonte['last_error'] or '', 110)}</div>",
                    unsafe_allow_html=True,
                )

        if stati_fonti:
            with st.expander(f"Tutte le fonti ({len(stati_fonti)})", expanded=False):
                for fonte in sorted(stati_fonti, key=lambda s: (s["ok"], s["label"])):
                    icona = "🟢" if fonte["ok"] else "🔴"
                    st.markdown(
                        f"<div class='rail-row'>{icona} {fonte['label']}"
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

        # Avvisi di configurazione: qui e non a tutta pagina. Sono
        # condizioni permanenti, non novità: una fascia gialla larga quanto
        # lo schermo ruba attenzione alla ricerca a ogni singolo caricamento.
        avvisi = []
        if not C.notify_enabled():
            avvisi.append("Telegram non configurato: nessuna notifica.")
        if not backup.configurato():
            avvisi.append("Archivio non persistente: si azzera al riavvio.")
        if avvisi:
            st.markdown('<div class="eyebrow">Configurazione</div>', unsafe_allow_html=True)
            for avviso in avvisi:
                st.markdown(f"<div class='muted'>⚠️ {avviso}</div>", unsafe_allow_html=True)
            st.markdown("<div class='muted faint'>Si sistemano dalla scheda "
                        "<b>Diagnostica</b>.</div>", unsafe_allow_html=True)


render_sidebar()


# ======================================================================
# Testata
# ======================================================================
st.markdown(
    '<div class="app-title">Mobile Update Tracker</div>'
    '<div class="app-sub">Quale aggiornamento è arrivato, su quale modello, quando.</div>',
    unsafe_allow_html=True,
)

if _archivio_ripristinato:
    st.success("💾 Archivio ripristinato dal salvataggio esterno: lo storico degli "
               "aggiornamenti è sopravvissuto al riavvio.")
if _rimossi_logica or _rimossi_ritirate:
    st.info(
        "🔄 Archivio ricostruito dopo una correzione nella lettura delle fonti: "
        f"{_rimossi_logica + _rimossi_ritirate} voci obsolete rimosse. I dati corretti "
        "si ripopolano alla prossima scansione. Parco di test e cronologia sono "
        "rimasti intatti."
    )

# La riga di stato compare solo quando ha qualcosa da dire. Cinque zeri
# affiancati non informano: comunicano soltanto che l'app sembra rotta.
if not archivio_vuoto:
    st.markdown(
        '<div class="statusline">'
        f'<span><b class="n">{stats.get("devices", 0)}</b>'
        f'<span class="lbl"> dispositivi</span></span>'
        f'<span><b class="n">{stats.get("updates_relevant", 0)}</b>'
        f'<span class="lbl"> aggiornamenti</span></span>'
        f'<span><b class="n">{len(watched_keys)}</b>'
        f'<span class="lbl"> nel parco di test</span></span>'
        f'<span><span class="lbl">ultima scansione </span>'
        f'<b>{fmt_relative(last_scan.get("finished_at"))}</b></span>'
        f'<span><b>+{last_scan.get("new_items", 0)}</b>'
        f'<span class="lbl"> nell\'ultimo giro</span></span>'
        '</div>',
        unsafe_allow_html=True,
    )


# ======================================================================
# Ricerca unificata — modello, codice modello o IMEI, tutto in un campo
# ======================================================================
_ricerca_da_pulsante = st.session_state.pop("_ricerca_in_arrivo", None)

with st.form("unified_search_form", clear_on_submit=False):
    campo, pulsante = st.columns([6, 1], vertical_alignment="center")
    unified_query = campo.text_input(
        "Cerca",
        placeholder="Cerca un modello, un codice (RMX3939, SM-S928B) o un IMEI",
        label_visibility="collapsed", max_chars=64,
        value=_ricerca_da_pulsante or "",
    )
    unified_submitted = pulsante.form_submit_button("Cerca", use_container_width=True,
                                                    type="primary")

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
        bottoniera(completamenti, "sugg")


def render_search_outcome(display_name: str, live_result: dict,
                          query_grezza: str = "") -> None:
    """Mostra prima il dato più preciso disponibile, poi l'esito della
    verifica su notizie — l'ordine conta: un dato da fonte ufficiale è
    sempre più affidabile di una notizia, anche quando la ricerca online non
    trova nulla di nuovo in questo momento."""
    # `official_lookup` e `curated_lookup` sono ENTRAMBI risultati di una
    # ricerca diretta su una fonte, non notizie. La distinzione fra i due
    # e' il livello di fiducia, che viene mostrato accanto al dato; se qui
    # si guardasse solo il primo, i risultati del tracker ARB e del canale
    # di rollout finirebbero fra gli articoli di giornale — cioe' proprio
    # le uniche fonti che coprono OnePlus e OPPO recenti.
    CHIAVI_LOOKUP = ("official_lookup", "curated_lookup")
    structured = [i for i in live_result.get("items", [])
                  if i.get("source") in CHIAVI_LOOKUP]
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
        # esiste ma NON pubblicano la versione firmware. Dichiarare «dato
        # trovato» in quel caso è peggio che non trovare nulla: fa credere
        # di avere una risposta che non c'è.
        nome_mostrato = best.get("device_model") or display_name
        fonte = best.get("source_label", "")

        # IL CHIP, accanto al firmware. Per il QA e' meta' della
        # domanda: un difetto legato al SoC si riproduce solo su una
        # delle varianti, e su Samsung due telefoni con lo STESSO nome
        # e lo STESSO firmware possono montare Exynos o Snapdragon a
        # seconda del mercato.
        chip = soc.per_modello(query_grezza or best.get("model_code"),
                               f"{nome_mostrato} {best.get('size_info') or ''}")
        if chip:
            pezzi.append(f"SoC **{chip.etichetta}**")

        if pezzi:
            st.success(f"✅ **{nome_mostrato}** — " + " · ".join(pezzi)
                       + f"  \n*Fonte: {fonte}*")
            if chip and chip.nota:
                st.caption(f"🔧 {chip.nota}")
        else:
            st.warning(
                f"**{nome_mostrato}** riconosciuto, ma **questa fonte non pubblica la "
                f"versione firmware**: conferma solo che il modello esiste e la "
                f"finestra di supporto.  \n*Fonte: {fonte}*"
            )
            if chip:
                nota_chip = f" — {chip.nota}" if chip.nota else ""
                st.caption(f"🔧 SoC: **{chip.etichetta}**{nota_chip}")
            # PERCHE' manca, non solo CHE manca. Un modello mostrato senza
            # firmware sembra un guasto dell'app; detto cosi' e' il limite
            # del produttore, ed e' un'informazione utile a chi fa QA
            # (dice su quali marche non si puo' contare per il retest).
            nota_brand = sources.nota_copertura(best.get("brand"))
            if nota_brand:
                with st.expander("Perche' questo modello non ha una versione"):
                    st.write(nota_brand)
        if best.get("size_info") and "FABBRICA" in (best["size_info"] or "").upper():
            st.caption("⚠️ Questa è la versione **di fabbrica**, non necessariamente "
                       "quella installata oggi dopo gli aggiornamenti.")

    device = live_result.get("existing_device")
    if device and not structured:
        firmware = (
            device.get("os_version")
            or (f"build `{device['build']}`" if device.get("build") else None)
            or (f"patch {device['patch_level']}" if device.get("patch_level") else None)
            or "—"
        )
        fonte = ("dato ufficiale/strutturato" if live_result.get("existing_is_structured")
                 else "da notizie già raccolte")
        st.success(f"**{device['brand']} {device['model']}** — fermo a **{firmware}**, "
                   f"aggiornato **{fmt_relative(device['last_update_at'])}** ({fonte}).")

    news_items = [i for i in live_result.get("items", [])
                  if i.get("source") not in CHIAVI_LOOKUP]
    if news_items:
        rilevanti = sum(1 for i in news_items if i["is_relevant"])
        st.caption(f"Verifica online: {len(news_items)} notizie trovate, "
                   f"{rilevanti} riconosciute come rilascio reale.")
    elif not structured and not device:
        dettaglio = f" ({live_result['error']})" if live_result.get("error") else ""
        nota = live_result.get("structured_note")
        st.warning(
            f"Nessun dato trovato per «{display_name}»{dettaglio}, e il modello non è "
            "ancora nel catalogo."
            + (f"  \n*Fonte ufficiale: {nota}*" if nota else "")
        )
        # Il motivo più comune di una ricerca a vuoto non è che il modello
        # manchi, ma che il nome sia scritto in modo leggermente diverso.
        proposte = (suggest.did_you_mean(display_name, limit=5)
                    or suggest.suggest(display_name, limit=5))
        if proposte:
            st.markdown("**Forse cercavi:**")
            bottoniera(proposte, "forse")
    elif not structured and live_result.get("structured_note"):
        st.caption(f"ℹ️ Fonte ufficiale del produttore: {live_result['structured_note']}")


active_search = ""
if unified_submitted and unified_query.strip():
    query = unified_query.strip()
    if imeicheck.is_valid_imei(query):
        found = imeicheck.identify(query)
        if not found:
            tac_cercato = "".join(c for c in query if c.isdigit())[:8]
            st.warning(
                f"IMEI valido, ma il TAC **{tac_cercato}** non è in nessuno dei "
                f"database consultati ({imeicheck.status()})."
            )
            # NON È UN GUASTO, È UN BUCO DI COPERTURA. Sono due cose che
            # si vivono allo stesso modo ma si risolvono in modi opposti,
            # e dirlo evita di cercare un difetto che non c'è.
            #
            # I siti sotto NON vengono interrogati dall'app: bloccano
            # l'accesso automatico o lo vietano nei termini d'uso.
            # Consultarli di persona è invece del tutto lecito.
            st.caption(
                "I database gratuiti hanno buchi diversi fra loro e nessuno è "
                "completo. Controlla su uno di questi e poi salva il modello qui "
                "sotto: resterà valido anche per le prossime ricerche."
            )
            colonne_link = st.columns(len(imeicheck.SITI_VERIFICA_TAC))
            for colonna, (nome_sito, url_sito, nota_sito) in zip(
                    colonne_link, imeicheck.link_verifica(query)):
                colonna.link_button(nome_sito, url_sito, use_container_width=True,
                                    help=nota_sito)

            with st.expander("✍️ Salva tu il modello per questo TAC"):
                st.caption(
                    f"Vale subito per il TAC **{tac_cercato}**, cioè per tutti gli "
                    "IMEI di quel modello. Ha la precedenza sui database "
                    "scaricati: se lo hai verificato tu, hai ragione tu."
                )
                mc1, mc2 = st.columns(2)
                marca_manuale = mc1.text_input("Marca", key="tac_marca",
                                               placeholder="es. Samsung")
                modello_manuale = mc2.text_input("Modello", key="tac_modello",
                                                 placeholder="es. Galaxy A54 5G")
                if st.button("Salva questo modello", key="tac_salva"):
                    if imeicheck.aggiungi_tac(tac_cercato, marca_manuale,
                                              modello_manuale):
                        st.success("Salvato. Ricerca di nuovo l'IMEI.")
                        st.rerun()
                    else:
                        st.error("Serve almeno la marca o il modello.")

                # Il salvataggio vive nell'archivio, quindi sopravvive ai
                # riavvii ma non a un archivio ricostruito da zero. La riga
                # nel file del progetto è la forma definitiva: le due strade
                # non si escludono, si completano.
                st.caption("Per renderlo permanente, aggiungi questa riga a "
                           "`data/tac_modelli.csv`:")
                st.code(imeicheck.riga_csv(tac_cercato,
                                           marca_manuale or "Marca",
                                           modello_manuale or "Nome del modello"),
                        language="text")

            if not imeicheck._chiave_api():
                st.caption(
                    "💡 Con una chiave gratuita in `TAC_API_KEY` l'app può "
                    "interrogare un catalogo più ampio inviando **solo le prime "
                    "8 cifre**, mai l'IMEI intero."
                )
        else:
            brand_found, specs = found
            dettagli_imei = imeicheck.parse_specs(brand_found, specs)
            # SI CERCA PER CODICE, NON PER NOME, quando il database TAC lo
            # contiene — e lo contiene quasi sempre: la voce è del tipo
            # «SAMSUNG GALAXY S26 ULTRA, Samsung SM-S948B». Il nome è
            # ambiguo fra le varianti di mercato (che montano firmware e
            # perfino chip diversi) e arriva in forme incoerenti, ora
            # «Galaxy S26 Ultra» ora «Samsung Galaxy S26 Ultra». Il codice
            # invece è esatto ed è la chiave che le fonti ufficiali
            # accettano: è la differenza fra «trova qualcosa» e «trova
            # quel telefono».
            model_from_imei = dettagli_imei.get("code") or dettagli_imei["model"]
            st.info(f"IMEI riconosciuto: **{imeicheck.describe(brand_found, specs)}**")
            with st.spinner(f"Verifico «{model_from_imei}»…"):
                live_result = scan.search_model(model_from_imei)
            render_search_outcome(model_from_imei, live_result)
            active_search = model_from_imei
    else:
        with st.spinner(f"Verifico «{query}»…"):
            live_result = scan.search_model(query)
        render_search_outcome(query, live_result, query_grezza=query)
        active_search = query

search_history = storage.get_search_history(30)

# --- Ricerche recenti, ripetibili con un clic --------------------------
# Ripetere un controllo su un modello già cercato è l'operazione più
# frequente in un flusso di QA: non deve costare il riscrivere il nome.
if search_history and not unified_submitted:
    recenti = list(dict.fromkeys(h["model"] for h in search_history if h.get("model")))[:6]
    if recenti:
        st.caption("Ricerche recenti:")
        bottoniera(recenti, "recente", per_riga=6)


# ======================================================================
# Primo avvio — una sola cosa da fare, detta chiaramente
# ======================================================================
# Prima qui comparivano cinque «0» nella riga di stato, un riquadro «nessun
# dispositivo», un altro «nessun aggiornamento» e un avviso Telegram:
# quattro messaggi per dire la stessa cosa, e nessuno che dicesse cosa fare.
if archivio_vuoto:
    if mai_scansionato:
        titolo = "L'archivio è vuoto"
        spiegazione = (
            "Due modi per riempirlo: cerca un modello qui sopra — la ricerca interroga "
            "le fonti ufficiali sul momento — oppure lancia una scansione completa, che "
            "raccoglie tutto quello che le fonti pubblicano e da lì in poi prosegue da "
            f"sola ogni {C.SCAN_INTERVAL_MINUTES} minuti."
        )
        etichetta = "Esegui la prima scansione"
    elif not stats.get("updates_total") and last_scan.get("total_found"):
        # Caso frequentissimo dopo un aggiornamento del codice, e da NON
        # confondere con un guasto: l'archivio è stato svuotato apposta
        # perché la logica di lettura delle fonti è cambiata, mentre la riga
        # della vecchia scansione è rimasta. Senza questo ramo la pagina
        # direbbe «la scansione non ha prodotto dispositivi» — un allarme
        # per qualcosa che ha funzionato esattamente come doveva.
        #
        # La firma è nei DATI, non nella memoria del processo: una scansione
        # che dichiara voci trovate a fronte di un archivio vuoto può
        # significare solo che quelle voci sono state rimosse dopo. Usare
        # `_rimossi_logica` non basterebbe: quel valore vive in
        # `@st.cache_resource` e torna a zero al primo rerun successivo.
        titolo = "Archivio da ripopolare"
        spiegazione = (
            f"L'ultima scansione aveva raccolto {last_scan['total_found']} voci, ma sono "
            "state rimosse perché interpretate da una versione più vecchia della logica "
            "di lettura delle fonti: tenerle avrebbe significato mostrare per sempre i "
            "vecchi valori sbagliati. Una scansione le ricostruisce, corrette. Parco di "
            "test e cronologia non sono stati toccati."
        )
        etichetta = "Ricostruisci l'archivio"
    else:
        # Caso diverso e da dire diversamente: la scansione è avvenuta ma
        # non ha prodotto dispositivi. Non è «devi ancora iniziare», è
        # «qualcosa non ha funzionato» — e la risposta sta in Diagnostica.
        titolo = "Nessuna voce riconducibile a un modello"
        spiegazione = (
            f"L'ultimo giro è terminato {fmt_relative(last_scan.get('finished_at'))} e in "
            f"archivio ci sono {stats.get('updates_total', 0)} voci, ma nessuna è legata a "
            "un modello preciso. Di solito significa che una fonte è in errore o ha "
            "cambiato formato: la scheda <b>Diagnostica</b> dice quale. Nel frattempo la "
            "ricerca qui sopra funziona lo stesso, perché interroga le fonti sul momento."
        )
        etichetta = "Riprova la scansione"

    st.markdown(
        f'<div class="onboard"><h3>{titolo}</h3>'
        f'<div class="muted">{spiegazione}</div></div>',
        unsafe_allow_html=True,
    )
    avvio1, _avvio2 = st.columns([1, 3])
    if avvio1.button(etichetta, type="primary", use_container_width=True,
                     key="onboard_scan"):
        with st.spinner("Interrogo le fonti… il primo giro richiede qualche minuto."):
            esito = scan.run_scan(auto_notify=False)
        if esito.get("skipped"):
            st.info("Scansione già in corso.")
        else:
            st.success(f"{esito['total']} voci raccolte, {esito['new']} nuove.")
        st.rerun()


# ======================================================================
# Filtri
# ======================================================================
with st.expander("Filtri", expanded=False):
    ff1, ff2, ff3 = st.columns(3)
    brand_filter = ff1.multiselect("Brand", C.BRANDS, default=[])
    severity_filter = ff2.multiselect("Severità", C.SEVERITY_ORDER, default=[])
    window = ff3.select_slider(
        "Finestra temporale", options=[7, 14, 30, 60, 90, 180, 365], value=90,
        format_func=lambda d: f"ultimi {d} giorni",
    )
    ff4, ff5 = st.columns(2)
    strict = ff4.toggle(
        "Modalità rigorosa", value=True,
        help="Mostra solo ciò che il filtro riconosce come rilascio reale. "
             "Disattivala per vedere anche gli scarti e capire perché lo sono.",
    )
    only_watched = ff5.toggle("Solo il parco di test", value=False)
    st.caption(f"Notifiche automatiche da **{C.NOTIFY_MIN_SEVERITY}** in su, più tutti i "
               f"device nel parco di test. Scansione ogni {C.SCAN_INTERVAL_MINUTES} min.")


# ======================================================================
# Scheda — Dispositivi
# ======================================================================
def render_dispositivi() -> None:
    """Elenco dei modelli con lo stato software attuale, e scheda del singolo."""
    devices = storage.get_devices(brands=brand_filter or None,
                                  search=active_search or None)
    if only_watched:
        devices = [d for d in devices if d["watched"]]
    if severity_filter:
        devices = [d for d in devices if d["severity"] in severity_filter]

    if not devices:
        st.info("Nessun dispositivo con questi filtri. Cerca un modello qui sopra, "
                "oppure lancia una scansione dal pannello a sinistra.")
        return

    fresh = sum(1 for d in devices if (days_since(d["last_update_at"]) or 999) <= 7)
    stale = sum(1 for d in devices if (days_since(d["last_update_at"]) or 999) > C.STALE_DAYS)
    baselines = storage.get_test_baselines()
    conteggio = retest.riepilogo(devices, baselines)
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Modelli in elenco", len(devices))
    d2.metric("Aggiornati negli ultimi 7 giorni", fresh)
    d3.metric(f"Fermi da oltre {C.STALE_DAYS} giorni", stale)
    d4.metric("Cambiati da quando li hai provati",
              conteggio[retest.DA_RITESTARE] + conteggio[retest.INCOERENTE],
              help="Conta solo i modelli con una baseline di test: gli altri "
                   "non hanno un termine di paragone.")

    def chip_di(riga) -> "soc.Soc | None":
        """Il processore di una riga dispositivo.

        Prova tutte le tracce disponibili, dalla più precisa alla meno:
        il codice modello se c'è, poi il numero di build (che per Samsung
        COMINCIA col codice modello: `A325F`XXSCDYB2), infine il nome
        commerciale. Un solo punto per tutta l'interfaccia, così tabella,
        scheda e ricerca non possono più dare risposte diverse sullo
        stesso telefono.
        """
        return soc.per_modello(
            riga.get("model_code") or riga.get("build"),
            riga.get("model") or riga.get("device_model"),
        )

    # Risolto una volta sola per dispositivo: dentro la comprensione
    # sarebbe stato chiamato due volte per riga, per nessun motivo.
    chip_per_riga = {}
    for _d in devices:
        _chip = chip_di(_d)
        chip_per_riga[_d["device_key"]] = _chip.etichetta if _chip else "—"

    st.dataframe(
        pd.DataFrame([
            {
                "⭐": "⭐" if d["watched"] else "",
                "Brand": d["brand"],
                "Modello": d["model"],
                "CPU": chip_per_riga.get(d["device_key"], "—"),
                "Sistema": (f"Android {d['android_version']}" if d.get("android_version")
                            else (d["os_version"] or "—")),
                "Versione completa": d["os_version"] or "—",
                "Build": d["build"] or "—",
                "Patch": d["patch_level"] or "—",
                "Ultimo aggiornamento": fmt_date(d["last_update_at"]),
                "Quando": fmt_relative(d["last_update_at"]),
                "Stato": freshness(d["last_update_at"]),
                "Da ritestare": retest.confronta(
                    d, baselines.get(d["device_key"]))["etichetta"],
                "Tipo": d["severity"],
                "30 gg": d["updates_30d"],
                "90 gg": d["updates_90d"],
                "Fonte": d["link"] or "",
            }
            for d in devices
        ]),
        hide_index=True, use_container_width=True,
        column_config={"Fonte": st.column_config.LinkColumn("Fonte", display_text="🔗 apri")},
    )

    st.markdown('<div class="eyebrow">Scheda dispositivo</div>', unsafe_allow_html=True)
    options = {f"{d['brand']} · {d['model']}": d for d in devices}
    default_index = 0
    if unified_submitted and active_search:
        match = next((i for i, d in enumerate(devices)
                      if active_search.lower() in d["model"].lower()), None)
        if match is not None:
            default_index = match
    device = options[st.selectbox("Apri lo storico di", list(options), index=default_index)]

    with st.container(border=True):
        img_col, info_col = st.columns([1, 3])
        with img_col:
            photo_url = images.find_device_image(f"{device['brand']} {device['model']}")
            if photo_url:
                st.image(photo_url, use_container_width=True)
            else:
                st.markdown(
                    "<div style='display:flex;align-items:center;justify-content:center;"
                    "height:140px;border-radius:12px;background:var(--surface);"
                    "border:1px solid var(--hairline);font-size:2.4rem;'>📱</div>",
                    unsafe_allow_html=True,
                )

        with info_col:
            info_col.markdown(f"### {device['model']}")
            info_col.caption(device["brand"])
            s1, s2, s3, s4 = info_col.columns(4)
            s1.metric("Sistema",
                      f"Android {device['android_version']}" if device.get("android_version")
                      else (device["os_version"] or "—"))
            s2.metric("Versione completa", device["os_version"] or "—")
            s3.metric("Ultimo aggiornamento", fmt_relative(device["last_update_at"]))
            s4.metric("Update ultimi 90 gg", device["updates_90d"])

            identificativi = []
            if device["build"]:
                identificativi.append(f"build <span class='build'>{device['build']}</span>")
            if device["patch_level"]:
                identificativi.append(f"patch <span class='build'>{device['patch_level']}</span>")

            # IL CHIP NELLA SCHEDA, non solo nel riquadro di ricerca.
            # Chi guarda un dispositivo del parco di test vuole sapere
            # quale processore monta senza doverlo ricercare: un difetto
            # legato al SoC si riproduce solo su una delle varianti.
            #
            # Quando non lo sappiamo lo diciamo, invece di lasciare la
            # riga vuota: un campo assente sembra un guasto dell'app,
            # una frase esplicita dice che il dato manca e si puo'
            # aggiungere (data/soc_modelli.csv).
            chip_device = chip_di(device)
            if chip_device:
                identificativi.append(
                    f"SoC <span class='build'>{chip_device.etichetta}</span>")
            else:
                identificativi.append("SoC non disponibile")
            if identificativi:
                info_col.markdown(" · ".join(identificativi), unsafe_allow_html=True)
            if chip_device and chip_device.nota:
                info_col.caption(f"🔧 {chip_device.nota}")
            info_col.markdown(f"**Stato:** {freshness(device['last_update_at'])} — "
                              f"{qa_impact(device['severity'], bool(device['watched']))}")

            b1, b2 = info_col.columns(2)
            watch_label = ("Rimuovi dal parco di test" if device["watched"]
                           else "⭐ Aggiungi al parco di test")
            if b1.button(watch_label, key=f"watch_{device['device_key']}",
                         use_container_width=True):
                toggle_watch(device["device_key"], device["brand"], device["model"],
                             bool(device["watched"]))
                st.rerun()
            if b2.button("🔄 Verifica adesso", key=f"refresh_{device['device_key']}",
                         use_container_width=True,
                         help="Ricontrolla online se c'è qualcosa di più recente."):
                with st.spinner(f"Verifico «{device['model']}»…"):
                    refresh_result = scan.search_model(device["model"])
                if refresh_result["items"]:
                    st.success(f"Trovate {len(refresh_result['items'])} notizie aggiornate.")
                    st.rerun()
                else:
                    st.info("Nessuna novità rispetto a quanto già in archivio.")

    with st.container(border=True):
        st.markdown('<div class="eyebrow">Rispetto all\'ultima volta che l\'hai testato</div>',
                    unsafe_allow_html=True)
        blocco_retest(device, "scheda")

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
            head.caption(f"{entry.get('source_label', '')} — "
                         f"{truncate(entry.get('title', ''), 110)}")
            tail.markdown(severity_html(entry), unsafe_allow_html=True)
            tail.caption(date_label(entry))


# ======================================================================
# Scheda — Aggiornamenti
# ======================================================================
def render_panoramica() -> None:
    """Sintesi degli ultimi 30 giorni, basata solo su date di uscita reali."""
    grezzi = storage.get_updates(only_relevant=True, since_days=30, limit=500)
    # Solo gli item con una VERA data di pubblicazione entrano qui: prima di
    # questa correzione, quelli privi di data (i controlli di stato
    # ufficiali, che non pubblicano una data per release) venivano "datati"
    # al momento della scansione, e la panoramica mostrava quando l'app
    # aveva guardato, non quando l'aggiornamento era uscito.
    overview_items = [i for i in grezzi if not i.get("published_is_estimated")]
    esclusi = len(grezzi) - len(overview_items)

    if not overview_items:
        st.info(
            "Nessun aggiornamento con una data di rilascio nota negli ultimi 30 giorni. "
            + (f"({esclusi} voci senza data reale escluse qui, ma visibili nelle schede "
               "dispositivo.)" if esclusi else "")
        )
        return

    overview_df = pd.DataFrame(overview_items)
    sev_counts = overview_df["severity"].value_counts()

    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Con data nota (30 gg)", len(overview_items))
    o2.metric("🔴 Major", int(sev_counts.get(C.SEV_MAJOR, 0)))
    o3.metric("🟡 Feature", int(sev_counts.get(C.SEV_FEATURE, 0)))
    o4.metric("🟢 Patch/Security", int(sev_counts.get(C.SEV_SECURITY, 0)))
    if esclusi:
        st.caption(f"ℹ️ {esclusi} aggiornamento/i senza data di rilascio reale (es. "
                   "controlli di stato ufficiali) non sono conteggiati qui per non "
                   "falsare le date — restano visibili nelle schede dispositivo.")

    overview_df["giorno"] = overview_df["published"].str.slice(0, 10)
    chart_col, list_col = st.columns([2, 3])

    with chart_col:
        st.caption("Aggiornamenti per giorno di uscita (30 gg)")
        st.bar_chart(overview_df.groupby("giorno").size().sort_index(), height=280)

    with list_col:
        st.caption("In evidenza — i più recenti (data di uscita reale)")
        highlights = sorted(overview_items, key=lambda i: i.get("published") or "",
                            reverse=True)[:6]
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
                hc1.markdown(f"<span class='muted'>{dettagli or '—'}</span>",
                             unsafe_allow_html=True)
                hc2.markdown(severity_html(h), unsafe_allow_html=True)
                hc2.caption(fmt_date(h.get("published")))


def render_aggiornamenti() -> None:
    """Flusso cronologico degli aggiornamenti, ordinato per data di uscita."""
    render_panoramica()
    st.markdown('<div class="eyebrow">Tutti gli aggiornamenti</div>', unsafe_allow_html=True)

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
    # stesso id, qui si tiene solo la prima occorrenza invece di dare la
    # stessa key a due righe (che manderebbe Streamlit in crash).
    seen_ids: set[str] = set()
    deduped = []
    for i in items:
        if i["id"] not in seen_ids:
            seen_ids.add(i["id"])
            deduped.append(i)
    items = deduped

    if not items:
        st.info("Nessun aggiornamento con questi filtri. Allarga la finestra temporale.")
        return

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
    st.download_button("⬇️ Esporta in CSV",
                       data=export.to_csv(index=False).encode("utf-8"),
                       file_name="mobile_updates.csv", mime="text/csv")
    for idx, item in enumerate(items[:120]):
        render_update_row(item, watched_keys, row_index=idx)
    if len(items) > 120:
        st.caption(f"Mostrati i 120 più recenti su {len(items)}. Usa i filtri per restringere.")


# ======================================================================
# Scheda — Parco di test
# ======================================================================
def render_parco() -> None:
    """Modelli seguiti, con notifica su ogni aggiornamento che li riguarda."""
    st.markdown("Segna qui i modelli su cui provi la tua app: ricevi una notifica per "
                "**ogni** aggiornamento che li riguarda, anche una sola patch di sicurezza.")
    watchlist = storage.get_watchlist()

    # `vertical_alignment="bottom"` invece dello spaziatore da 1.75rem che
    # c'era prima: quell'altezza era indovinata, e bastava un'etichetta su
    # due righe per far scivolare il pulsante fuori posto.
    add1, add2, add3 = st.columns([2, 3, 1], vertical_alignment="bottom")
    new_brand = add1.selectbox("Brand", C.BRANDS, key="wl_brand")
    new_model = add2.text_input("Modello", placeholder="es. Galaxy S24 Ultra", key="wl_model")
    if add3.button("Aggiungi", use_container_width=True):
        if new_model.strip():
            model = extract.canonical_device(new_model)
            storage.add_to_watchlist(extract.device_key(new_brand, model), new_brand, model)
            st.success(f"{model} aggiunto al parco di test.")
            st.rerun()
        else:
            st.error("Scrivi il nome del modello.")

    if not watchlist:
        st.info("Il parco di test è vuoto. Aggiungi un modello qui sopra o dalla "
                "scheda dispositivo.")
        return

    if st.button("🔄 Verifica ora tutto il parco di test", use_container_width=True,
                 help="Controlla online, uno per uno, tutti i modelli del parco."):
        progress = st.progress(0.0)
        status_ph = st.empty()
        trovati_totali = 0
        for i, entry in enumerate(watchlist):
            status_ph.caption(f"Verifico {entry['model']}…")
            trovati_totali += len(scan.search_model(entry["model"])["items"])
            progress.progress((i + 1) / len(watchlist))
        progress.empty()
        status_ph.empty()
        st.success(f"Verifica completata su {len(watchlist)} modelli: "
                   f"{trovati_totali} notizie trovate in totale.")
        st.rerun()

    summary = {d["device_key"]: d for d in storage.get_devices()}
    baselines = storage.get_test_baselines()

    # La domanda del parco di test non è «a che versione sono», ma «quali
    # sono cambiati da quando li ho provati»: quel conteggio va davanti.
    presenti = [summary[e["device_key"]] for e in watchlist
                if e["device_key"] in summary]
    conteggio = retest.riepilogo(presenti, baselines)
    p1, p2, p3 = st.columns(3)
    p1.metric("Da ritestare",
              conteggio[retest.DA_RITESTARE] + conteggio[retest.INCOERENTE])
    p2.metric("Invariati dall'ultima prova", conteggio[retest.INVARIATO])
    p3.metric("Senza baseline",
              conteggio[retest.MAI_TESTATO] + len(watchlist) - len(presenti),
              help="Modelli per cui non hai ancora dichiarato «testato»: "
                   "senza un termine di paragone non si può dire cosa è cambiato.")

    solo_da_ritestare = st.checkbox(
        "Mostra solo quelli cambiati dall'ultima prova", value=False,
        key="parco_solo_retest")

    for entry in watchlist:
        device = summary.get(entry["device_key"])
        esito = retest.confronta(device or {}, baselines.get(entry["device_key"]))
        if solo_da_ritestare and esito["stato"] not in (retest.DA_RITESTARE,
                                                        retest.INCOERENTE):
            continue
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
            col1.markdown(f"**{entry['model']}**")
            col1.caption(entry["brand"])
            if device:
                col2.markdown(f"Android {device['android_version']}"
                              if device.get("android_version")
                              else (device["os_version"] or "—"))
                col2.caption(f"build {device['build'] or '—'} · "
                             f"patch {device['patch_level'] or '—'}")
                col3.markdown(freshness(device["last_update_at"]))
                col3.caption(fmt_relative(device["last_update_at"]))
            else:
                col2.caption("Nessun aggiornamento rilevato finora.")
                col3.markdown("⚪ In attesa")
            if col4.button("🔄", key=f"verify_{entry['device_key']}",
                           use_container_width=True, help="Verifica ora questo modello"):
                with st.spinner(f"Verifico «{entry['model']}»…"):
                    scan.search_model(entry["model"])
                st.rerun()
            if col5.button("🗑️", key=f"rm_{entry['device_key']}",
                           use_container_width=True, help="Rimuovi dal parco di test"):
                storage.remove_from_watchlist(entry["device_key"])
                st.rerun()

            if device:
                blocco_retest(device, "parco")
            else:
                st.caption("La baseline si potrà fotografare appena una fonte "
                           "pubblicherà una versione per questo modello.")


# ======================================================================
# Scheda — Catalogo
# ======================================================================
def render_catalogo() -> None:
    """Via d'ingresso per navigazione, per chi non ricorda il nome esatto,
    più la cronologia delle ricerche."""
    per_marca = suggest.brands_with_devices()
    if not per_marca:
        st.info("Il catalogo si popola con la prima scansione.")
    else:
        totale = sum(len(v) for v in per_marca.values())
        st.caption(f"{totale} modelli noti all'app.")
        marca = st.selectbox("Marca", list(per_marca), key="sfoglia_marca")
        modelli = per_marca.get(marca, [])
        st.caption(f"{len(modelli)} modelli per {marca}")
        for inizio in range(0, min(len(modelli), 24), 3):
            colonne = st.columns(3)
            for offset, nome in enumerate(modelli[inizio:inizio + 3]):
                if colonne[offset].button(nome, key=f"sfoglia_{inizio}_{offset}_{nome}",
                                          use_container_width=True):
                    avvia_ricerca(nome)
        if len(modelli) > 24:
            st.caption(f"…e altri {len(modelli) - 24}. Usa la ricerca per arrivarci "
                       "direttamente.")

    if search_history:
        st.markdown('<div class="eyebrow">Cronologia ricerche</div>', unsafe_allow_html=True)
        st.dataframe(
            pd.DataFrame([
                {"Modello": h["model"], "Firmware": h["firmware"] or "—",
                 "Cercato": fmt_relative(h["searched_at"])}
                for h in search_history
            ]),
            hide_index=True, use_container_width=True, height=240,
        )
        if st.button("Svuota cronologia ricerche"):
            storage.clear_search_history()
            st.rerun()


# ======================================================================
# Scheda — Diagnostica
# ======================================================================
def render_persistenza() -> None:
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
                ok, messaggio = backup.prova_completa(C.env("BACKUP_GIST_ID"),
                                                      C.env("BACKUP_GITHUB_TOKEN"))
            st.success(messaggio) if ok else st.error(messaggio)
        return

    st.warning(
        "**L'archivio non sopravvive ai riavvii.** Su questo tipo di hosting il disco è "
        "temporaneo: a ogni riavvio o sospensione lo storico riparte da zero. Si "
        "configura una volta sola, qui sotto."
    )
    st.markdown("**Serve solo un token GitHub.** Al resto pensa l'app.")
    st.markdown(
        "1. Apri [github.com/settings/tokens/new]"
        "(https://github.com/settings/tokens/new?scopes=gist&description=Mobile%20Update%20Tracker) "
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
            return
        st.success("Archivio creato. Manca un ultimo passaggio.")
        st.markdown("Copia queste due righe e incollale nei **secrets** dell'app "
                    "(su Streamlit Cloud: menu ⋮ → *Settings* → *Secrets*), poi riavvia:")
        st.code(f'BACKUP_GIST_ID = "{gist_id}"\n'
                f'BACKUP_GITHUB_TOKEN = "{token_inserito.strip()}"', language="toml")
        st.caption("Questo passaggio non può farlo l'app: i secrets sono l'unico posto "
                   "dove un token può stare al sicuro, e solo tu puoi scriverci.")
        with st.spinner("Verifico che l'archivio funzioni…"):
            ok_prova, messaggio_prova = backup.prova_completa(gist_id, token_inserito.strip())
        st.success(messaggio_prova) if ok_prova else st.warning(messaggio_prova)


def render_diagnostica() -> None:
    """Tutto ciò che serve a capire perché un dato manca o è sbagliato.

    Era sparsa in tre posti (colonna laterale, scheda, expander in fondo
    alla pagina). Qui è una scheda sola: la sintesi resta nel pannello a
    sinistra, sempre in vista, e il dettaglio sta qui."""
    st.markdown('<div class="eyebrow">Stato delle fonti</div>', unsafe_allow_html=True)
    if not stati_fonti:
        st.info("Nessuna scansione eseguita finora.")
    else:
        st.dataframe(
            pd.DataFrame([
                {
                    "Stato": ("🔴 Errore" if not s["ok"]
                              else "🟠 Impoverita" if s.get("degrado") else "🟢 OK"),
                    "Fonte": s["label"],
                    "Voci": s["items_found"],
                    "Di norma": (s["degrado"]["atteso"] if s.get("degrado") else "—"),
                    "Ultimo controllo": fmt_relative(s["checked_at"]),
                    "Ultimo successo": fmt_relative(s["last_ok_at"]),
                    "Dettaglio": truncate(
                        s["last_error"] or (s["degrado"]["messaggio"] if s.get("degrado") else ""),
                        140),
                }
                for s in stati_fonti
            ]),
            hide_index=True, use_container_width=True,
        )

        with st.expander("Andamento di una fonte nel tempo", expanded=False):
            st.caption("Quante voci ha restituito una fonte nelle ultime scansioni. Serve "
                       "a capire QUANDO è iniziato un calo: un guasto di formato si vede "
                       "come un gradino netto, non come un'oscillazione.")
            etichette = {s["label"]: s["source"] for s in stati_fonti}
            scelta = st.selectbox("Fonte", list(etichette), key="andamento_fonte")
            storico = storage.get_source_history(etichette[scelta], limit=20)
            if len(storico) < 2:
                st.caption("Storico troppo breve: servono almeno due scansioni.")
            else:
                st.line_chart(
                    pd.DataFrame({"voci": [r["items_found"] for r in reversed(storico)]},
                                 index=[fmt_dt(r["recorded_at"]) for r in reversed(storico)]),
                    height=200,
                )

    st.markdown('<div class="eyebrow">Perché una ricerca non trova nulla</div>',
                unsafe_allow_html=True)
    st.caption("Passo per passo: se il testo è stato riconosciuto come codice, in quali "
               "nomi è stato risolto, quali fonti sono state interrogate e cosa ha "
               "risposto ciascuna.")
    with st.form("diagnosi_query"):
        dq1, dq2 = st.columns([5, 1], vertical_alignment="center")
        query_diag = dq1.text_input("Modello", placeholder="es. CPH2819",
                                    label_visibility="collapsed")
        diagnosi_richiesta = dq2.form_submit_button("Analizza", use_container_width=True)

    if diagnosi_richiesta and query_diag.strip():
        with st.spinner("Ripercorro la ricerca…"):
            passi = sources.diagnose_query(query_diag.strip())
        st.markdown(f"**Esito:** {passi['esito']}")
        dd1, dd2 = st.columns(2)
        dd1.markdown(
            f"Riconosciuto come codice: **{'sì' if passi['ha_forma_di_codice'] else 'no'}**  \n"
            f"Brand dedotto: **{passi['brand_dedotto'] or '—'}**"
        )
        dd2.markdown("Forme provate:  \n"
                     + ("  \n".join(f"· {f}" for f in passi["forme_provate"]) or "—"))
        if passi["nomi_risolti"]:
            for voce in passi["nomi_risolti"]:
                st.caption(f"«{voce['codice']}» risolto in: {', '.join(voce['nomi'])}")
        elif passi["ha_forma_di_codice"]:
            st.warning("Il testo ha la forma di un codice, ma nessun dataset lo conosce: è "
                       "il motivo più probabile per cui la ricerca non arriva al modello. "
                       "Prova con il nome commerciale.")
        st.dataframe(
            pd.DataFrame([
                {"Fonte": f["fonte"], "Trovati": f["trovati"],
                 "Dispositivo": f.get("dispositivo", "—"),
                 "Errore": truncate(f["errore"] or "", 90)}
                for f in passi["fonti"]
            ]),
            hide_index=True, use_container_width=True,
        )

    st.markdown('<div class="eyebrow">Cosa ha scartato il filtro</div>', unsafe_allow_html=True)
    st.caption("Se qui trovi rilasci veri, il filtro è troppo severo.")
    discarded = [i for i in storage.get_updates(only_relevant=False, since_days=window,
                                                limit=400) if not i["is_relevant"]]
    if not discarded:
        st.success("Nessuno scarto nella finestra selezionata.")
    else:
        st.dataframe(
            pd.DataFrame([
                {"Titolo": truncate(i["title"], 90), "Fonte": i["source_label"],
                 "Punteggio": i["relevance_score"],
                 "Motivo": truncate(i["relevance_note"], 90)}
                for i in discarded[:100]
            ]),
            hide_index=True, use_container_width=True,
        )

    with st.expander("Ultime scansioni e notifiche inviate", expanded=False):
        scans = storage.get_scans(10)
        if scans:
            st.dataframe(
                pd.DataFrame([
                    {"Quando": fmt_relative(s["started_at"]),
                     "Durata": f"{(s['duration_s'] or 0):.0f}s",
                     "Trovati": s["total_found"], "Nuovi": s["new_items"],
                     "Notifiche": s["notifications"],
                     "Errore": truncate(s["error"] or "", 80)}
                    for s in scans
                ]),
                hide_index=True, use_container_width=True,
            )
        notifications = storage.get_notifications(40)
        if not notifications:
            st.caption("Nessuna notifica inviata finora.")
        else:
            for record in notifications:
                icon = "✅" if record["ok"] else "⚠️"
                label = (f"[{record['device']}]({record['link']})" if record["link"]
                         else record["device"])
                st.write(f"{icon} **{record['brand']}** — {label} · {record['version']} · "
                         f"{record['severity']} · {record['kind']} · {fmt_dt(record['sent_at'])}")

    render_persistenza()

    st.markdown('<div class="eyebrow">Manutenzione</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    if t1.button("Prova il canale Telegram", use_container_width=True):
        ok, error = notify.send_test()
        st.success("Messaggio di prova inviato.") if ok else st.error(
            f"Invio non riuscito — {error}")
    if t2.button(f"Elimina i dati oltre {C.RETENTION_DAYS} giorni", use_container_width=True):
        st.success(f"Eliminati {storage.purge_old()} record.")
    if t3.button("Azzera stato notifiche", use_container_width=True,
                 help="Rimanda al prossimo giro le notifiche già inviate."):
        st.success(f"Azzerato lo stato di {storage.clear_notified()} voci.")

    st.markdown(
        f"<div class='muted'>Database <code>{stats['db_path']}</code> · "
        f"{stats['updates_total']} record totali · logica dati v{C.DATA_LOGIC_VERSION}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='muted'>Codici modello: {modelcodes.status()}<br>"
        f"Dispositivi Apple: {appledevices.status()}</div>",
        unsafe_allow_html=True,
    )
    if st.button("Ricarica i database dei codici", key="reload_codes",
                 help="Forza un nuovo tentativo di scaricamento."):
        modelcodes.reset_cache()
        modelcodes.resolve("")   # forza il caricamento, così lo stato si aggiorna
        st.rerun()


# ======================================================================
# Impianto della pagina — cinque schede allo stesso livello
# ======================================================================
# Prima erano due schede, dentro la prima un interruttore a due posizioni, e
# in fondo alla pagina un expander con altra diagnostica: tre livelli di
# navigazione per quattro destinazioni, e la diagnostica in tre posti
# diversi. Ora sono cinque voci pari, ciascuna con un solo posto dove sta.
(scheda_dispositivi, scheda_aggiornamenti, scheda_parco,
 scheda_catalogo, scheda_diagnostica) = st.tabs(
    ["Dispositivi", "Aggiornamenti", "Parco di test", "Catalogo", "Diagnostica"]
)

with scheda_dispositivi:
    render_dispositivi()
with scheda_aggiornamenti:
    render_aggiornamenti()
with scheda_parco:
    render_parco()
with scheda_catalogo:
    render_catalogo()
with scheda_diagnostica:
    render_diagnostica()
