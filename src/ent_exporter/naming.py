# src/ent_exporter/naming.py
from __future__ import annotations
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Callable

_UNSAFE = re.compile(r'[/\\:*?"<>|]')

def sanitize(name: str) -> str:
    return _UNSAFE.sub("_", name).strip()

def month_folder(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"

def path_for(board_name: str, label: str, taken_at: datetime, media_id: int,
             exists: Callable[[str], bool] | None = None) -> str:
    folder = f"{sanitize(board_name)}/{month_folder(taken_at)}"
    label = sanitize(label)
    key = f"{folder}/{label}"
    if exists and exists(key):
        stem = PurePosixPath(label).stem
        suffix = PurePosixPath(label).suffix
        key = f"{folder}/{stem}_{media_id}{suffix}"
    return key
