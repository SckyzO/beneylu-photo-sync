# src/ent_exporter/naming.py
from __future__ import annotations
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Callable

_UNSAFE = re.compile(r'[/\\:*?"<>|]')
_WHITESPACE = re.compile(r"\s+")

SECTION_MAXLEN = 60
SECTION_FALLBACK = "sans-titre"

def sanitize(name: str) -> str:
    return _UNSAFE.sub("_", name).strip()

def month_folder(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"

def section_folder(description: str | None) -> str:
    """A safe folder name for a card's section, derived from its description.

    Collapses whitespace/newlines, neutralizes path-unsafe characters (accents
    kept for readability), truncates to a sane length, and falls back to a
    constant when the description is empty or reduces to nothing.
    """
    if not description:
        return SECTION_FALLBACK
    text = _WHITESPACE.sub(" ", description).strip()
    text = _UNSAFE.sub("_", text)
    text = text[:SECTION_MAXLEN].rstrip(" .")
    return text or SECTION_FALLBACK

def path_for(board_name: str, section: str | None, label: str, taken_at: datetime,
             media_id: int, exists: Callable[[str], bool] | None = None) -> str:
    folder = f"{sanitize(board_name)}/{month_folder(taken_at)}/{section_folder(section)}"
    label = sanitize(label)
    key = f"{folder}/{label}"
    if exists and exists(key):
        stem = PurePosixPath(label).stem
        suffix = PurePosixPath(label).suffix
        key = f"{folder}/{stem}_{media_id}{suffix}"
    return key
