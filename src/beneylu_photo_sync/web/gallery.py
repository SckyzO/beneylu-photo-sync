from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .thumbnails import THUMB_DIR

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
SECTION_FALLBACK = "sans-titre"


@dataclass
class Photo:
    key: str  # posix path relative to the data root
    name: str


@dataclass
class SectionGroup:
    section: str
    photos: list[Photo] = field(default_factory=list)


@dataclass
class MonthGroup:
    month: str
    sections: list[SectionGroup] = field(default_factory=list)


@dataclass
class BoardGroup:
    board: str
    months: list[MonthGroup] = field(default_factory=list)


def _section_sort_key(section: str) -> tuple[bool, str]:
    # Real sections alpha-first; the "sans-titre" fallback always last.
    return (section == SECTION_FALLBACK, section.casefold())


def scan(root: Path | str) -> list[BoardGroup]:
    root = Path(root)
    if not root.is_dir():
        return []
    boards: list[BoardGroup] = []
    for board_dir in sorted(
        p for p in root.iterdir() if p.is_dir() and p.name != THUMB_DIR
    ):
        # month -> section -> [Photo]. Photos live as board/month/file (legacy)
        # or board/month/section/file (section grouping). The section is the
        # third path component when present, else the "sans-titre" fallback.
        by_month: dict[str, dict[str, list[Photo]]] = {}
        for f in board_dir.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            rel = f.relative_to(root)
            if THUMB_DIR in rel.parts or len(rel.parts) < 3:
                continue
            month = rel.parts[1]
            section = rel.parts[2] if len(rel.parts) >= 4 else SECTION_FALLBACK
            by_month.setdefault(month, {}).setdefault(section, []).append(
                Photo(key=rel.as_posix(), name=f.name)
            )
        months = []
        for m in sorted(by_month, reverse=True):
            sections = [
                SectionGroup(
                    section=s,
                    photos=sorted(by_month[m][s], key=lambda p: p.key),
                )
                for s in sorted(by_month[m], key=_section_sort_key)
            ]
            months.append(MonthGroup(month=m, sections=sections))
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
