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
        months: list[MonthGroup] = []
        for month_dir in sorted(
            (p for p in board_dir.iterdir() if p.is_dir()), reverse=True
        ):
            photos = [
                Photo(
                    key=f"{board_dir.name}/{month_dir.name}/{f.name}",
                    name=f.name,
                )
                for f in sorted(month_dir.iterdir())
                if f.is_file() and f.suffix.lower() in IMAGE_EXTS
            ]
            if photos:
                months.append(MonthGroup(month=month_dir.name, photos=photos))
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
