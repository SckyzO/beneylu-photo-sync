# src/beneylu_photo_sync/core/sync.py
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from . import naming
log = logging.getLogger("beneylu_photo_sync.sync")

DEFAULT_WORKERS = 4

@dataclass
class SyncReport:
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    pruned: int = 0
    error_items: list[int] = field(default_factory=list)

class Synchronizer:
    def __init__(self, client, sources, storage, state, workers: int = DEFAULT_WORKERS):
        self.client = client
        self.sources = sources
        self.storage = storage
        self.state = state
        self.workers = max(1, workers)

    def run(self, on_progress=None) -> SyncReport:
        """Run the sync. on_progress(report), if given, is called with the live
        SyncReport after each prune, skip and download so a UI can poll live
        counters instead of waiting for the final tally."""
        report = SyncReport()
        for source in self.sources:
            # Prune first: drop on-disk content (and its state rows) for boards
            # the filter now excludes, before downloading what's kept.
            for prefix in source.obsolete_roots(self.client):
                removed = self.storage.remove(prefix)
                forgotten = self.state.forget_prefix(prefix)
                if removed or forgotten:
                    log.info("Pruned now-excluded content under %s", prefix)
                    report.pruned += 1
                    if on_progress:
                        on_progress(report)
            # Decide what needs fetching on the main thread (single-threaded
            # state/storage reads), then download the rest concurrently.
            pending = []
            for item in source.iter_items(self.client):
                if self._already_present(item):
                    report.skipped += 1
                    if on_progress:
                        on_progress(report)
                else:
                    pending.append(item)
            self._download_all(pending, report, on_progress)
        return report

    def _already_present(self, item) -> bool:
        if not self.state.has(item.media_id):
            return False
        stored = self.state.path_for(item.media_id)
        if stored and self.storage.exists(stored):
            return True
        # Recorded but the file is gone from disk: self-heal by re-downloading.
        log.info("Re-downloading media %s: recorded but missing on disk", item.media_id)
        return False

    def _download_all(self, items, report: SyncReport, on_progress=None) -> None:
        """Fetch (network) concurrently in a bounded pool; commit (disk + state)
        serially in submission order. Keeping commits serial keeps SQLite on one
        thread and makes the dedup-suffix assignment deterministic. Per-item
        failures are isolated so one bad media never aborts the run."""
        if not items:
            return
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = [(item, pool.submit(self._fetch, item)) for item in items]
            for item, future in futures:
                try:
                    self._commit(item, future.result(), report)
                except Exception:  # per-item isolation; run continues
                    log.exception("Failed to sync media %s", item.media_id)
                    report.errors += 1
                    report.error_items.append(item.media_id)
                if on_progress:
                    on_progress(report)

    def _fetch(self, item):
        media = self.client.resolve_media(item.attachment)
        data = b"".join(self.client.download(media.url))
        return media, data

    def _commit(self, item, fetched, report: SyncReport) -> None:
        media, data = fetched
        # Group by the card's publication date so a posted section lands in one
        # month, instead of scattering by per-photo EXIF capture dates.
        key = naming.path_for(item.board.name, item.card.description, media.label,
                              item.card.created_at, item.media_id, exists=self.storage.exists)
        if not self.storage.exists(key):
            self.storage.write(key, iter([data]))
        self.state.record(media_id=item.media_id, board_id=item.board.id,
                          card_id=item.card.id, path=key,
                          card_updated_at=item.card.updated_at.isoformat())
        report.downloaded += 1
