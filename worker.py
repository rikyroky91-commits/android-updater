"""Worker standalone: esegue le scansioni senza avviare la UI.

Utile quando la dashboard gira su un hosting che va in sleep (Streamlit
Community Cloud) e si vuole comunque ricevere le notifiche 24/7: si lancia
questo processo su una macchina sempre attiva, puntando allo stesso database.

    python worker.py            # ciclo continuo
    python worker.py --once     # una sola scansione (ideale per cron/GitHub Actions)
"""
import argparse
import time

from core import config as C, scan, storage


def main() -> None:
    parser = argparse.ArgumentParser(description="Scansione aggiornamenti Android")
    parser.add_argument("--once", action="store_true", help="esegue una sola scansione ed esce")
    parser.add_argument("--no-notify", action="store_true", help="non invia notifiche Telegram")
    args = parser.parse_args()

    storage.init_db()
    while True:
        result = scan.run_scan(auto_notify=not args.no_notify)
        print(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"trovati={result.get('total', 0)} nuovi={result.get('new', 0)} "
            f"notifiche={result.get('notifications', 0)}"
        )
        for source in result.get("sources", []):
            if not source["ok"]:
                print(f"  ! {source['label']}: {source['error']}")
        if args.once:
            return
        time.sleep(max(60, C.SCAN_INTERVAL_MINUTES * 60))


if __name__ == "__main__":
    main()
