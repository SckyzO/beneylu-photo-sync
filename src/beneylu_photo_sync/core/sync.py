# src/beneylu_photo_sync/core/sync.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from . import naming
log = logging.getLogger("beneylu_photo_sync.sync")

@dataclass
class SyncReport:
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    pruned: int = 0
    error_items: list[int] = field(default_factory=list)

class Synchronizer:
    def __init__(self, client, sources, storage, state):
        self.client = client
        self.sources = sources
        self.storage = storage
        self.state = state

    def run(self) -> SyncReport:
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
            for item in source.iter_items(self.client):
                try:
                    self._handle(item, report)
                except Exception:  # per-item isolation; run continues
                    log.exception("Failed to sync media %s", item.media_id)
                    report.errors += 1
                    report.error_items.append(item.media_id)
        return report

    def _handle(self, item, report: SyncReport) -> None:
        if self.state.has(item.media_id):
            stored = self.state.path_for(item.media_id)
            if stored and self.storage.exists(stored):
                report.skipped += 1
                return
            # Recorded but the file is gone from disk: self-heal by re-downloading.
            log.info("Re-downloading media %s: recorded but missing on disk", item.media_id)
        media = self.client.resolve_media(item.attachment)
        data = b"".join(self.client.download(media.url))
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
