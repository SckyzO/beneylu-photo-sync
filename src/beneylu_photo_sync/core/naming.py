# src/beneylu_photo_sync/core/naming.py
from __future__ import annotations
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Callable

_UNSAFE = re.compile(r'[/\\:*?"<>|]')
_WHITESPACE = re.compile(r"\s+")
_BULLET = re.compile(r"\s[-•]\s?")

SECTION_MAXLEN = 60
SECTION_FALLBACK = "sans-titre"

def sanitize(name: str) -> str:
    return _UNSAFE.sub("_", name).strip()

def month_folder(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"

def section_folder(description: str | None) -> str:
    """A safe folder name for a card's section, derived from its title.

    Beneylu cards store a short title followed by a bulleted activity list. We
    keep only the title: the text before the first newline, or before the first
    inline bullet ("- " / "• "). Whitespace is collapsed, path-unsafe characters
    neutralized (accents kept), the result truncated and trailing punctuation
    trimmed, with a constant fallback when nothing remains.
    """
    if not description:
        return SECTION_FALLBACK
    first = description.replace("\r", "\n").split("\n", 1)[0]
    first = _BULLET.split(first, maxsplit=1)[0]
    text = _WHITESPACE.sub(" ", first).strip()
    text = _UNSAFE.sub("_", text)
    # Strip trailing separator artifacts: a title ending in ":" becomes "_"
    # after sanitization, and trailing " . _ , -" all read as noise on a folder.
    text = text[:SECTION_MAXLEN].rstrip(" ._,-")
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
