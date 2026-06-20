# src/beneylu_photo_sync/core/storage/filesystem.py
from __future__ import annotations
import shutil
from pathlib import Path
from typing import Iterable
from .base import Storage

class FilesystemStorage(Storage):
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def remove(self, key: str) -> bool:
        root = self.root.resolve()
        target = (self.root / key).resolve()
        # Never delete the root itself, never escape it (traversal/empty key).
        if target == root or root not in target.parents:
            return False
        if target.is_dir():
            shutil.rmtree(target)
            return True
        if target.is_file():
            target.unlink()
            return True
        return False

    def write(self, key: str, stream: Iterable[bytes]) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with tmp.open("wb") as f:
                for chunk in stream:
                    f.write(chunk)
            tmp.replace(dest)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
