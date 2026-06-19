from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .thumbnails import THUMB_DIR

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


@dataclass
class Photo:
    key: str  # posix path relative to the data root
    name: str


@dataclass
class MonthGroup:
    month: str
    photos: list[Photo] = field(default_factory=list)


@dataclass
class BoardGroup:
    board: str
    months: list[MonthGroup] = field(default_factory=list)


def scan(root: Path | str) -> list[BoardGroup]:
    root = Path(root)
    if not root.is_dir():
        return []
    boards: list[BoardGroup] = []
    for board_dir in sorted(
        p for p in root.iterdir() if p.is_dir() and p.name != THUMB_DIR
    ):
        # Photos may live as board/month/file or, since section grouping,
        # board/month/section/file. Group by the month component (first level
        # under the board) regardless of any deeper section folders.
        by_month: dict[str, list[Photo]] = {}
        for f in board_dir.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            rel = f.relative_to(root)
            if THUMB_DIR in rel.parts or len(rel.parts) < 3:
                continue
            month = rel.parts[1]
            by_month.setdefault(month, []).append(
                Photo(key=rel.as_posix(), name=f.name)
            )
        months = [
            MonthGroup(month=m, photos=sorted(by_month[m], key=lambda p: p.key))
            for m in sorted(by_month, reverse=True)
        ]
        if months:
            boards.append(BoardGroup(board=board_dir.name, months=months))
    return boards


def safe_resolve(root: Path | str, key: str) -> Path | None:
    """Resolve a gallery key under root, refusing traversal. None if invalid."""
    root = Path(root).resolve()
    candidate = (root / key).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        return None
    if not candidate.is_file():
        return None
    return candidate
