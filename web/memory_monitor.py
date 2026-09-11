"""Controllo RSS indipendente dalle richieste, senza leggere dati utente."""
import logging
import threading
import time

from core.util import alleggerisci_se_serve, memoria_mb, memoria_picco_mb

log = logging.getLogger("uvicorn.error")


class MemoryMonitor:
    def __init__(self, interval=5.0):
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None
        self.last_log = 0.0

    def sample(self):
        result = alleggerisci_se_serve()
        now = time.monotonic()
        if result.get("fatto") or now - self.last_log >= 60:
            log.info("memory rss_mb=%s peak_mb=%s cleanup=%s",
                     memoria_mb(), memoria_picco_mb(), result)
            self.last_log = now

    def run(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.sample()
            except Exception:
                log.exception("memory monitor: controllo non riuscito")

    def start(self):
        self.thread = threading.Thread(target=self.run, name="memory-monitor", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
