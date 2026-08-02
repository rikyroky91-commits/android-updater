"""Notifiche Telegram.

Correzioni rispetto alla versione precedente:

* si usa `parse_mode=HTML` con escaping, invece di Markdown: i build number
  contengono spesso `_`, `*` o `[`, che con Markdown facevano fallire l'invio
  con un 400 silenzioso (la notifica non partiva e nessuno se ne accorgeva);
* gli errori dell'API vengono restituiti al chiamante e registrati, non
  inghiottiti;
* rispetto del rate limit (429 → attesa `retry_after`);
* messaggio orientato al QA: dice cosa è cambiato e se il device è nel parco di test.
"""
from __future__ import annotations

import html
import time

from . import config as C
from .classify import qa_impact
from .util import fmt_date

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


def _esc(value) -> str:
    return html.escape(str(value if value is not None else "—"), quote=False)


def build_message(item: dict, watched: bool = False) -> str:
    """Compone il testo HTML della notifica."""
    header = "⭐ <b>DEVICE IN TEST — NUOVO AGGIORNAMENTO</b>" if watched else "📲 <b>NUOVO AGGIORNAMENTO</b>"
    device = item.get("device_model") or item.get("title") or "Dispositivo non identificato"

    lines = [
        header,
        "",
        f"🏷️ <b>Brand:</b> {_esc(item.get('brand'))}",
        f"📱 <b>Dispositivo:</b> {_esc(device)}",
    ]
    if item.get("os_version"):
        lines.append(f"🤖 <b>Versione:</b> {_esc(item['os_version'])}")
    if item.get("build"):
        lines.append(f"🔢 <b>Build:</b> <code>{_esc(item['build'])}</code>")
    if item.get("patch_level"):
        lines.append(f"🛡️ <b>Patch level:</b> {_esc(item['patch_level'])}")
    lines.append(f"🚦 <b>Tipo:</b> {_esc(item.get('severity'))}")
    lines.append(f"🗓️ <b>Data:</b> {_esc(fmt_date(item.get('published') or item.get('first_seen')))}")
    lines.append(f"🧪 <b>QA:</b> {_esc(qa_impact(item.get('severity', ''), watched))}")
    if item.get("source_label"):
        lines.append(f"📡 <b>Fonte:</b> {_esc(item['source_label'])}")
    if item.get("link"):
        lines.append(f"\n🔗 <a href=\"{html.escape(str(item['link']), quote=True)}\">Apri la fonte</a>")
    if not item.get("device_model"):
        lines.append("\n<i>Modello non riconosciuto automaticamente: vedi il titolo sulla fonte.</i>")
    return "\n".join(lines)


def send_message(text: str, disable_preview: bool = True) -> tuple[bool, str | None]:
    """Invia un messaggio. Restituisce (ok, errore)."""
    if requests is None:  # pragma: no cover
        return False, "la libreria 'requests' non è installata"
    token, chat_id = C.telegram_token(), C.telegram_chat_id()
    if not token or not chat_id:
        return False, "TELEGRAM_TOKEN o TELEGRAM_CHAT_ID non configurati"

    payload = {
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    for attempt in range(3):
        try:
            response = requests.post(API_BASE.format(token=token), json=payload, timeout=15)
        except Exception as exc:
            if attempt == 2:
                return False, f"connessione fallita: {exc}"
            time.sleep(2)
            continue
        if response.status_code == 200:
            return True, None
        if response.status_code == 429:
            retry_after = 3
            try:
                retry_after = int(response.json().get("parameters", {}).get("retry_after", 3))
            except Exception:
                pass
            time.sleep(min(retry_after, 30))
            continue
        try:
            description = response.json().get("description", response.text[:120])
        except Exception:
            description = response.text[:120]
        return False, f"HTTP {response.status_code}: {description}"
    return False, "rate limit Telegram: invio non riuscito dopo 3 tentativi"


def send_update(item: dict, watched: bool = False) -> tuple[bool, str | None]:
    return send_message(build_message(item, watched))


def send_digest(items: list[dict], watched_keys: set[str] | None = None) -> tuple[bool, str | None]:
    """Riassunto unico quando una scansione produce molti item.

    Evita di intasare la chat con decine di messaggi dopo il primo avvio
    o dopo uno svuotamento della cache.
    """
    watched_keys = watched_keys or set()
    lines = [f"📦 <b>{len(items)} nuovi aggiornamenti rilevati</b>", ""]
    for item in items[:30]:
        star = "⭐ " if item.get("device_key") in watched_keys else ""
        device = item.get("device_model") or item.get("title")
        version = item.get("os_version") or item.get("build") or ""
        link = item.get("link")
        label = f"{star}{_esc(device)}"
        if link:
            label = f"<a href=\"{html.escape(str(link), quote=True)}\">{label}</a>"
        lines.append(f"• {label} — {_esc(version)} {_esc(item.get('severity', ''))}")
    if len(items) > 30:
        lines.append(f"\n…e altri {len(items) - 30}. Apri la dashboard per l'elenco completo.")
    return send_message("\n".join(lines))


def send_test() -> tuple[bool, str | None]:
    return send_message(
        "✅ <b>Universal Mobile Update Tracker</b>\nCanale Telegram configurato correttamente."
    )
