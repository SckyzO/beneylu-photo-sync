from __future__ import annotations

from pathlib import Path

from PIL import Image

THUMB_DIR = ".thumbnails"
MAX_SIZE = (320, 320)
# Hard ceiling on source pixels before decoding. School photos sit well under
# this; anything larger is treated as a decompression bomb and refused so a
# hostile image can't exhaust memory. Checked against the header-declared size,
# which Image.open() exposes without decoding the pixel data.
MAX_PIXELS = 50_000_000


class DecompressionGuardError(ValueError):
    """Source image declares more pixels than MAX_PIXELS allows."""


def thumb_path(data_root: Path | str, key: str) -> Path:
    return Path(data_root) / THUMB_DIR / f"{key}.jpg"


def get_or_create(data_root: Path | str, source: Path, key: str) -> Path:
    out = thumb_path(data_root, key)
    if out.is_file() and out.stat().st_mtime >= source.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        w, h = im.size  # header dimensions, no pixel decode yet
        if w * h > MAX_PIXELS:
            raise DecompressionGuardError(
                f"{source}: {w}x{h} exceeds {MAX_PIXELS} px cap")
        im = im.convert("RGB")
        im.thumbnail(MAX_SIZE)
        im.save(out, "JPEG", quality=85)
    return out
