from __future__ import annotations
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

log = logging.getLogger("ent_exporter.web.jobs")


@dataclass
class RunStatus:
    state: str = "idle"            # idle | running | error
    last_run_at: Optional[str] = None
    last_error: Optional[str] = None
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0


class SyncRunner:
    """Runs one sync job at a time in a background thread."""

    def __init__(self, job: Callable[[], object]):
        # job() performs a full sync and returns an object with
        # .downloaded / .skipped / .errors (a core SyncReport).
        self._job = job
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.status = RunStatus()

    def trigger(self) -> bool:
        """Start a run if none is in progress. Returns True if started."""
        if not self._lock.acquire(blocking=False):
            return False
        self.status.state = "running"
        self.status.last_error = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        try:
            report = self._job()
            self.status.downloaded = report.downloaded
            self.status.skipped = report.skipped
            self.status.errors = report.errors
            self.status.state = "idle"
        except Exception as exc:  # surfaced in status, never swallowed
            log.exception("Sync run failed")
            self.status.state = "error"
            self.status.last_error = str(exc)
        finally:
            self.status.last_run_at = datetime.now(timezone.utc).isoformat()
            self._lock.release()
