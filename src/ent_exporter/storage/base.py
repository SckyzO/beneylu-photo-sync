# src/ent_exporter/storage/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable

class Storage(ABC):
    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def write(self, key: str, stream: Iterable[bytes]) -> None:
        """Persist stream under key. Must be atomic: no partial artifact on failure."""

    @abstractmethod
    def remove(self, key: str) -> bool:
        """Delete the file or directory tree at key (relative to root). Returns
        True if something was removed. Must stay within the storage root and
        never delete the root itself."""
