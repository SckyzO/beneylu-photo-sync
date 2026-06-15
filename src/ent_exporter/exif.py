# src/ent_exporter/exif.py
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from PIL import Image

_DATETIME_ORIGINAL = 36867  # EXIF tag DateTimeOriginal
_EXIF_IFD = 0x8769  # Exif sub-IFD where DateTimeOriginal normally lives
_EXIF_DATETIME_FMT = "%Y:%m:%d %H:%M:%S"


def capture_date(image_bytes: bytes) -> datetime | None:
    """Return the EXIF DateTimeOriginal of an image, or None if absent/unparseable.

    The returned datetime is naive: EXIF stores no timezone and we do not invent one.
    A corrupt or non-image input never raises -- it yields None -- so a single bad
    photo cannot abort a sync run.
    """
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            exif = img.getexif()
        raw = exif.get_ifd(_EXIF_IFD).get(_DATETIME_ORIGINAL)
        if raw is None:
            raw = exif.get(_DATETIME_ORIGINAL)
        if not raw:
            return None
        return datetime.strptime(str(raw), _EXIF_DATETIME_FMT)
    except Exception:
        return None
