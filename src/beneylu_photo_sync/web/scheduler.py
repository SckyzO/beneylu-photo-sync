from __future__ import annotations
import logging
import threading
from typing import Callable

log = logging.getLogger("beneylu_photo_sync.web.scheduler")


class IntervalScheduler:
    """Calls `callback` every `interval_hours` hours in a daemon thread.

    interval_hours <= 0 disables scheduling (start() is a no-op).
    """

    def __init__(self, interval_hours: float, callback: Callable[[], object]):
        self.interval_seconds = interval_hours * 3600
        self._callback = callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.interval_seconds <= 0:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        # _stop.wait returns True when stopped, False on timeout (fire).
        while not self._stop.wait(self.interval_seconds):
            try:
                self._callback()
            except Exception:  # a scheduled failure must not kill the loop
                log.exception("Scheduled sync trigger failed")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
