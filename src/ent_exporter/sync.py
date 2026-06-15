# src/ent_exporter/sync.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from . import naming

log = logging.getLogger("ent_exporter.sync")

@dataclass
class SyncReport:
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
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
            report.skipped += 1
            return
        media = self.client.resolve_media(item.attachment)
        taken_at = item.card.created_at
        key = naming.path_for(item.board.name, media.label, taken_at, item.media_id,
                              exists=self.storage.exists)
        if not self.storage.exists(key):
            self.storage.write(key, self.client.download(media.url))
        self.state.record(media_id=item.media_id, board_id=item.board.id,
                          card_id=item.card.id, path=key,
                          card_updated_at=item.card.updated_at.isoformat())
        report.downloaded += 1
