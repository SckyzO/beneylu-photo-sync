from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from .gallery import IMAGE_EXTS
from .thumbnails import THUMB_DIR


def build_zip(root: Path | str, subdir: Path | str) -> str:
    """Zip every image file under ``subdir`` into a temp .zip; return its path.

    Arcnames are stored relative to ``root`` so the archive mirrors the gallery
    layout. The thumbnail cache and non-image files are skipped. The caller owns
    the returned temp file and must delete it after sending.
    """
    root = Path(root)
    subdir = Path(subdir)
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(subdir.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            rel = f.relative_to(root)
            if THUMB_DIR in rel.parts:
                continue
            zf.write(f, arcname=rel.as_posix())
    return tmp.name
