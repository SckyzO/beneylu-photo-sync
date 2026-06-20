# src/beneylu_photo_sync/core/state.py
from __future__ import annotations
import sqlite3
from pathlib import Path

def _like_escape(s: str) -> str:
    # Neutralize LIKE wildcards so a folder name keeps its literal meaning
    # (sanitized board folders routinely contain "_", which LIKE treats as "?").
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

class StateStore:
    def __init__(self, db_path: Path | str):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            # card_updated_at: seam reserved for the Phase-2 `updatedAt` cursor
            # (recorded now, not yet read) to enable incremental re-sync of
            # edited cards without a full-history rescan.
            """CREATE TABLE IF NOT EXISTS media (
                 media_id INTEGER PRIMARY KEY,
                 board_id TEXT, card_id TEXT, path TEXT,
                 card_updated_at TEXT,
                 downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP)"""
        )
        self._conn.commit()

    def has(self, media_id: int) -> bool:
        cur = self._conn.execute("SELECT 1 FROM media WHERE media_id = ?", (media_id,))
        return cur.fetchone() is not None

    def path_for(self, media_id: int) -> str | None:
        """The on-disk path recorded for media_id, or None if unknown. Lets the
        synchronizer self-heal a recorded photo whose file was deleted."""
        row = self._conn.execute(
            "SELECT path FROM media WHERE media_id = ?", (media_id,)).fetchone()
        return row[0] if row else None

    def record(self, media_id: int, board_id: str, card_id: str, path: str, card_updated_at: str) -> None:
        self._conn.execute(
            """INSERT INTO media (media_id, board_id, card_id, path, card_updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(media_id) DO UPDATE SET path=excluded.path,
                   card_updated_at=excluded.card_updated_at""",
            (media_id, board_id, card_id, path, card_updated_at))
        self._conn.commit()

    def forget_prefix(self, prefix: str) -> int:
        """Drop rows whose stored path is, or lives under, prefix. Lets a later
        un-exclude of a pruned board re-download its photos. Returns the count
        removed. The "prefix/" guard stops "Board A" matching "Board AB"."""
        cur = self._conn.execute(
            "DELETE FROM media WHERE path = ? OR path LIKE ? ESCAPE '\\'",
            (prefix, _like_escape(prefix) + "/%"))
        self._conn.commit()
        return cur.rowcount

    def clear(self) -> int:
        """Drop every row. Used by the admin 'wipe' / 'force full resync'
        actions so the next sync re-downloads from scratch. Returns the count
        removed."""
        cur = self._conn.execute("DELETE FROM media")
        self._conn.commit()
        return cur.rowcount

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "StateStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
