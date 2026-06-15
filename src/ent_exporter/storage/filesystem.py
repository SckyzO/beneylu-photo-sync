# src/ent_exporter/storage/filesystem.py
from __future__ import annotations
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
