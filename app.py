import streamlit as st
import requests
import feedparser
import urllib.parse
import json
import os
import time
import re
from datetime import datetime
from threading import Thread

# ==========================================
# CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(
    page_title="Universal Android Update & QA Tracker",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# COSTANTI E FILE LOCALI
# ==========================================
SENT_CACHE_FILE = "sent_updates.json"
LATEST_DATA_FILE = "latest_data.json"
DEVICE_DB_FILE = "device_database.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

API_LEVEL_MAP = {
    "ANDROID 13": "API 33",
    "ANDROID 14": "API 34",
    "ANDROID 15": "API 35 (Android V)",
    "ANDROID 16": "API 36 (Android Baklava)",
    "ANDROID 17": "API 37 (Android 17)"
}

# ==========================================
# UTILITY: EXTRAZIONE PESO E DATA
# ==========================================
def extract_file_size(text: str) -> str:
    """Estrae la dimensione in MB o GB dal testo tramite Regex."""
    match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB|GiB|MiB))', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "N/D (OTA Incrementale)"

def parse_release_date(entry) -> str:
    """Estrae e formatta la data esatta di rilascio dell'update."""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            return time.strftime("%d/%m/%Y", entry.published_parsed)
        except Exception:
            pass
    elif hasattr(entry, 'published') and entry.published:
        return entry.published[:16]
    return datetime.now().strftime("%d/%m/%Y")

def ensure_valid_link(link: str, search_context: str) -> str:
    """Garantisce che ogni risultato abbia sempre un URL valido e cliccabile."""
    if link and isinstance(link, str) and link.startswith("http") and link != "#":
        return link
    encoded_query = urllib.parse.quote(f"{search_context} firmware update source")
    return f"https://www.google.com/search?q={encoded_query}"

# ==========================================
# GESTIONE JSON E DATABASE PERSISTENTE
# ==========================================
def load_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_val
    return default_val

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

def get_device_db():
    return load_json(DEVICE_DB_FILE, {})

# ==========================================
# CREEDENZIALI TELEGRAM
# ==========================================
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "737033122")

# ==========================================
# LOGICA DI ANALISI E CLASSIFICAZIONE
# ==========================================
def detect_api_level(text: str) -> str:
    text_upper = text.upper()
    for android_ver, api_level in API_LEVEL_MAP.items():
        if android_ver in text_upper:
            return api_level
    return "API Standard / Patch"

def classify_update(title_or_version: str, size_str: str = ""):
    text = title_or_version.upper()

    # Check dimensione se espressa in GB
    is_large_file = False
    if "GB" in size_str.upper():
        try:
            val = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+)", size_str)[0])
            if val >= 1.2:
                is_large_file = True
        except Exception:
            pass

    major_keywords = [
        "ANDROID 14", "ANDROID 15", "ANDROID 16", "ANDROID 17",
        "ONE UI 7", "ONE UI 8", "HYPEROS 2", "HYPEROS 3",
        "COLOROS 15", "OXYGENOS 15", "MAGICOS 9", "RECOVERY", "FULL ROM"
    ]

    is_major = any(kw in text for kw in major_keywords) or is_large_file

    if is_major:
        return "🔴 MAJOR UPDATE (Test App Prioritario)", "#FF4B4B", "Alto (Rischio breaking changes / permessi)"
    elif any(kw in text for kw in ["UPDATE", "OTA", "BETA", "QPR", "FEATURE", "ROLLOUT"]):
        return "🟡 FEATURE UPDATE (Test Consigliato)", "#FFAA00", "Medio (Nuove funzionalità OS)"
    else:
        return "🟢 PATCH / SECURITY (Basso Rischio)", "#00CC66", "Basso (Fix di sicurezza)"

def send_telegram_alert(token, chat_id, brand, device, version, size_info, release_date, badge, api_lvl, link):
    if not token or not chat_id:
        return False

    valid_link = ensure_valid_link(link, f"{brand} {device} {version}")

    msg = f"""🚨 **ANDROID UPDATE DETECTED** 🚨

🏢 **Brand:** {brand}
📱 **Modello:** {device}
📦 **Build/Versione:** `{version}`
📅 **Data Rilascio:** `{release_date}`
💾 **Peso Package:** `{size_info}`
🎯 **Target API:** `{api_lvl}`
📊 **QA Impact:** {badge}

🔗 [Analizza Fonte / Release Notes]({valid_link})"""

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

# ==========================================
# MOTORE RICERCA DEDICATO "ON-DEMAND"
# ==========================================
def search_specific_model_online(model_name: str):
    """Esegue una ricerca mirata estrando data di rilascio e peso pacchetto."""
    results = []

    encoded_query = urllib.parse.quote(f"{model_name} update Android firmware OTA size MB GB release date")
    feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:6]:
                title = entry.title
                summary = getattr(entry, 'summary', '')
                full_text = f"{title} {summary}"

                size_str = extract_file_size(full_text)
                rel_date = parse_release_date(entry)

                badge, color, impact = classify_update(title, size_str)
                api_lvl = detect_api_level(full_text)
                raw_link = getattr(entry, 'link', '#')
                valid_link = ensure_valid_link(raw_link, f"{model_name} {title}")

                item = {
                    "brand": "Ricerca Mirata",
                    "device": model_name.title(),
                    "version": title,
                    "release_date": rel_date,
                    "file_size": size_str,
                    "api_level": api_lvl,
                    "badge": badge,
                    "color": color,
                    "qa_impact": impact,
                    "link": valid_link
                }
                results.append(item)

                clean_key = re.sub(r'[^a-zA-Z0-9_]', '', f"{model_name}_{title[:20]}".lower().replace(" ", "_"))
                device_db = get_device_db()
                device_db[clean_key] = item
                save_json(DEVICE_DB_FILE, device_db)
    except Exception:
        pass

    return results

# ==========================================
# SCRAPER GLOBALE GENERALIZZATO
# ==========================================
def fetch_all_updates():
    results = []

    # 1. Xiaomi / POCO / Redmi (Con Dati Peso e Data Nativi)
    try:
        url = "https://raw.githubusercontent.com/XiaomiFirmwareUpdater/miui-updates-tracker/master/data/latest.json"
        r = requests.get(url, headers=HEADERS, timeout=6)
        if r.status_code == 200:
            items = r.json()
            items = items if isinstance(items, list) else list(items.values())
            for item in items:
                dev = item.get('device', item.get('codename', 'Xiaomi'))
                ver = item.get('version', 'N/D')
                raw_link = item.get('download', '#')
                valid_link = ensure_valid_link(raw_link, f"Xiaomi {dev} {ver}")

                # Parsing dimensione da Xiaomi API
                raw_size = item.get('size', '')
                if raw_size and raw_size.isdigit():
                    size_str = f"{round(int(raw_size) / (1024**3), 2)} GB"
                else:
                    size_str = str(raw_size) if raw_size else "2.5 GB (Full Recovery)"

                rel_date = item.get('date', datetime.now().strftime("%d/%m/%Y"))
                badge, color, impact = classify_update(ver, size_str)
                api_lvl = detect_api_level(ver)

                results.append({
                    "brand": "Xiaomi / POCO",
                    "device": dev,
                    "version": ver,
                    "release_date": rel_date,
                    "file_size": size_str,
                    "api_level": api_lvl,
                    "badge": badge,
                    "color": color,
                    "qa_impact": impact,
                    "link": valid_link
                })
    except Exception:
        pass

    # 2. RSS Feeds Generali
    query_minor = urllib.parse.quote("Umidigi OR Doogee OR Cubot OR Blackview OR Ulefone OR Oukitel update Android MB GB")
    query_alt = urllib.parse.quote("Sony Xperia OR Asus ROG OR Zenfone OR Nothing Phone OR Nokia update MB GB")
    query_moto = urllib.parse.quote("Motorola OR Vivo OR iQOO OR Lenovo Android update OTA MB GB")

    rss_sources = [
        ("Samsung Galaxy", "https://www.sammobile.com/category/firmware-news/feed/"),
        ("Google Pixel", "https://9to5google.com/category/pixel/feed/"),
        ("Oppo / OnePlus", "https://oxygenupdater.com/api/v2.6/news"),
        ("Huawei / Honor", "https://www.huaweicentral.com/category/updates/feed/"),
        ("Motorola / Vivo", f"https://news.google.com/rss/search?q={query_moto}&hl=en-US&gl=US&ceid=US:en"),
        ("Brand Minori / Rugged", f"https://news.google.com/rss/search?q={query_minor}&hl=en-US&gl=US&ceid=US:en"),
        ("Sony / Asus / Nothing", f"https://news.google.com/rss/search?q={query_alt}&hl=en-US&gl=US&ceid=US:en")
    ]

    for brand, feed_url in rss_sources:
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=4)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:6]:
                    title = entry.title
                    summary = getattr(entry, 'summary', '')
                    full_text = f"{title} {summary}"

                    if any(k in title.lower() for k in ["update", "android", "ota", "firmware", "patch"]):
                        size_str = extract_file_size(full_text)
                        rel_date = parse_release_date(entry)

                        badge, color, impact = classify_update(title, size_str)
                        api_lvl = detect_api_level(full_text)
                        raw_link = getattr(entry, 'link', '#')
                        valid_link = ensure_valid_link(raw_link, f"{brand} {title}")

                        results.append({
                            "brand": brand,
                            "device": title.split(" ")[0] if " " in title else brand,
                            "version": title,
                            "release_date": rel_date,
                            "file_size": size_str,
                            "api_level": api_lvl,
                            "badge": badge,
                            "color": color,
                            "qa_impact": impact,
                            "link": valid_link
                        })
        except Exception:
            continue

    return results

def run_update_cycle(manual_token="", manual_chat=""):
    scraped_updates = fetch_all_updates()
    device_db = get_device_db()

    for item in scraped_updates:
        clean_key = re.sub(r'[^a-zA-Z0-9_]', '', f"{item['brand']}_{item['device']}_{item['version'][:15]}".lower().replace(" ", "_"))
        device_db[clean_key] = item

    save_json(DEVICE_DB_FILE, device_db)
    save_json(LATEST_DATA_FILE, {
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total_found": len(scraped_updates),
        "updates": scraped_updates
    })

    token_to_use = manual_token if manual_token else TELEGRAM_TOKEN
    chat_to_use = manual_chat if manual_chat else TELEGRAM_CHAT_ID

    if token_to_use and chat_to_use:
        sent_cache = set(load_json(SENT_CACHE_FILE, []))
        new_sents = []

        for item in scraped_updates:
            unique_id = f"{item['brand']}_{item['device']}_{item['version']}"
            if unique_id not in sent_cache:
                success = send_telegram_alert(
                    token_to_use, chat_to_use,
                    item['brand'], item['device'], item['version'],
                    item['file_size'], item['release_date'], item['badge'], item['api_level'], item['link']
                )
                if success:
                    sent_cache.add(unique_id)
                    new_sents.append(unique_id)

        if new_sents:
            save_json(SENT_CACHE_FILE, list(sent_cache))

# ==========================================
# THREAD IN BACKGROUND
# ==========================================
@st.cache_resource
def init_background_worker():
    def worker():
        run_update_cycle()
        while True:
            time.sleep(3600)
            try:
                run_update_cycle()
            except Exception:
                pass

    t = Thread(target=worker, daemon=True)
    t.start()
    return True

init_background_worker()

# ==========================================
# INTERFACCIA UTENTE (STREAMLIT DASHBOARD)
# ==========================================
st.sidebar.title("⚙️ Configurazione & Controllo")

st.sidebar.markdown("### 🔔 Notifiche Telegram")
token_input = st.sidebar.text_input("Bot Token:", value=TELEGRAM_TOKEN, type="password")
chat_id_input = st.sidebar.text_input("Chat ID:", value=TELEGRAM_CHAT_ID)

if token_input and chat_id_input:
    st.sidebar.success("✅ Bot Operativo 24/7")
else:
    st.sidebar.warning("⚠️ Inserisci credenziali Telegram")

st.sidebar.divider()
st.sidebar.markdown("### 🛠️ Azioni Rapide")

if st.sidebar.button("🔄 Scansione Globale Server", use_container_width=True):
    with st.spinner("Scansione in corso..."):
        run_update_cycle(token_input.strip(), chat_id_input.strip())
    st.sidebar.success("Database aggiornato!")
    st.rerun()

if st.sidebar.button("🗑️ Reset Cache Notifiche", use_container_width=True):
    save_json(SENT_CACHE_FILE, [])
    st.sidebar.success("Cache notificate resettata.")

# Caricamento Dati
db_data = load_json(LATEST_DATA_FILE, {"timestamp": "Avvio...", "total_found": 0, "updates": []})
device_db = get_device_db()
sent_history = load_json(SENT_CACHE_FILE, [])

st.title("📱 Universal Android Update & QA Tracker")
st.caption("Tracker avanzato con Peso Pacchetto (MB/GB), Data di Rilascio esatta e fonti verificate.")

m1, m2, m3 = st.columns(3)
m1.metric("Dispositivi Salvati nel DB", len(device_db))
m2.metric("News Ultima Scansione", db_data.get("total_found", 0))
m3.metric("Alert Telegram Inviati", len(sent_history))

st.divider()

tab_search, tab_tracker, tab_history = st.tabs([
    "🔍 Cerca Firmware per Modello (On-Demand)",
    "📋 News Ultimi Aggiornamenti Intercettati",
    "🗄️ Storico Alert Telegram"
])

# ----------------------------------------------------
# TAB 1: RICERCA ED ESECUZIONE RICERCA MIRATA ON-DEMAND
# ----------------------------------------------------
with tab_search:
    st.subheader("🔎 Ricerca e Verifica Firmware per Modello Specifico")
    st.caption("Estrae peso del file, data di uscita e livello API per qualsiasi smartphone.")

    col_s1, col_s2 = st.columns([3, 1])
    search_query = col_s1.text_input("Modello Smartphone:", placeholder="Es. Umidigi Bison, Doogee V30, Edge 40, Zenfone 10...").strip()
    force_online_search = col_s2.button("🌐 Cerca Online Ora", use_container_width=True)

    if search_query:
        matched_devices = [
            data for key, data in device_db.items()
            if search_query.lower() in data["device"].lower() or search_query.lower() in data["brand"].lower() or search_query.lower() in data["version"].lower()
        ]

        if force_online_search or not matched_devices:
            with st.spinner(f"Ricerca firmware e metadati in corso per '{search_query}'..."):
                online_results = search_specific_model_online(search_query)
                if online_results:
                    st.success(f"Trovati {len(online_results)} risultati recenti con metadati per '{search_query}'!")
                    device_db = get_device_db()
                    matched_devices = [
                        data for key, data in device_db.items()
                        if search_query.lower() in data["device"].lower() or search_query.lower() in data["brand"].lower() or search_query.lower() in data["version"].lower()
                    ]

        if matched_devices:
            st.markdown(f"### Risultati Trovati ({len(matched_devices)})")
            for item in matched_devices:
                valid_url = ensure_valid_link(item.get('link'), f"{item['brand']} {item['device']}")
                with st.container():
                    c1, c2, c3, c4 = st.columns([2.5, 4, 2, 1.5])

                    c1.markdown(f"**Modello:** `{item['device']}`\n\n**Marca:** {item['brand']}")
                    c2.markdown(
                        f"**Build/Versione:** `{item['version']}`\n\n"
                        f"📅 **Data Rilascio:** `{item.get('release_date', 'N/D')}` | 💾 **Peso File:** `{item.get('file_size', 'N/D')}`\n\n"
                        f"🎯 **Target:** `{item['api_level']}` | ⚠️ **QA Impact:** {item.get('qa_impact', 'Standard')}"
                    )

                    badge_color = item.get('color', '#00CC66')
                    c3.markdown(f"<span style='color:{badge_color}; font-weight:bold;'>{item['badge']}</span>", unsafe_allow_html=True)

                    c4.link_button("🔗 Analizza Fonte", valid_url, use_container_width=True)

                    st.divider()
        else:
            st.warning(f"Nessun firmware trovato sul web per '{search_query}'. Assicurati che il nome del modello sia corretto.")

# ----------------------------------------------------
# TAB 2: ULTIME NEWS / ULTIMI AGGIORNAMENTI INTERCETTATI
# ----------------------------------------------------
with tab_tracker:
    st.subheader("📋 Notizie & Firmware Intercettati nell'Ultima Scansione")
    if not db_data["updates"]:
        st.info("ℹ️ Scansione iniziale in corso.")
    else:
        col_f1, col_f2 = st.columns([2, 2])
        brands_list = ["Tutti i Brand"] + sorted(list(set([u["brand"] for u in db_data["updates"]])))
        selected_brand = col_f1.selectbox("Filtra Marca:", brands_list)
        severity_filter = col_f2.selectbox("Filtra Severity QA:", ["Tutti i Livelli", "🔴 MAJOR UPDATE", "🟡 FEATURE UPDATE", "🟢 PATCH / SECURITY"])

        st.markdown("---")

        for item in db_data["updates"]:
            if selected_brand != "Tutti i Brand" and item["brand"] != selected_brand:
                continue
            if severity_filter != "Tutti i Livelli" and not item["badge"].startswith(severity_filter.split()[0]):
                continue

            valid_url = ensure_valid_link(item.get('link'), f"{item['brand']} {item['device']}")

            with st.container():
                c1, c2, c3, c4 = st.columns([2.5, 4, 2, 1.5])

                c1.markdown(f"**{item['brand']}**\n\n📱 `{item['device']}`")
                c2.markdown(
                    f"**Build/Versione:** `{item['version']}`\n\n"
                    f"📅 **Data Uscita:** `{item.get('release_date', 'N/D')}` | 💾 **Peso:** `{item.get('file_size', 'N/D')}`\n\n"
                    f"🎯 **Target:** `{item['api_level']}`"
                )
                c3.markdown(f"<span style='color:{item['color']}; font-weight:bold;'>{item['badge']}</span>", unsafe_allow_html=True)

                c4.link_button("🔗 Analizza Fonte", valid_url, use_container_width=True)

                st.divider()

# ----------------------------------------------------
# TAB 3: CRONOLOGIA TELEGRAM
# ----------------------------------------------------
with tab_history:
    st.subheader("🗄️ Registro Alert Inviati")
    if not sent_history:
        st.info("Ancora nessuna notifica inviata automaticamente.")
    else:
        for history_id in reversed(sent_history):
            st.markdown(f"- `{history_id}`")
