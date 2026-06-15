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
