# src/ent_exporter/state.py
from __future__ import annotations
import sqlite3
from pathlib import Path

class StateStore:
    def __init__(self, db_path: Path | str):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
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

    def record(self, media_id: int, board_id: str, card_id: str, path: str, card_updated_at: str) -> None:
        self._conn.execute(
            """INSERT INTO media (media_id, board_id, card_id, path, card_updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(media_id) DO UPDATE SET path=excluded.path,
                   card_updated_at=excluded.card_updated_at""",
            (media_id, board_id, card_id, path, card_updated_at))
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
