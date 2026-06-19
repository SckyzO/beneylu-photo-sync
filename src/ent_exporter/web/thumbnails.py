from __future__ import annotations

from pathlib import Path

from PIL import Image

THUMB_DIR = ".thumbnails"
MAX_SIZE = (320, 320)


def thumb_path(data_root: Path | str, key: str) -> Path:
    return Path(data_root) / THUMB_DIR / f"{key}.jpg"


def get_or_create(data_root: Path | str, source: Path, key: str) -> Path:
    out = thumb_path(data_root, key)
    if out.is_file() and out.stat().st_mtime >= source.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        im = im.convert("RGB")
        im.thumbnail(MAX_SIZE)
        im.save(out, "JPEG", quality=85)
    return out
