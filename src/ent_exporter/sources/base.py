# src/ent_exporter/sources/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable
from ..client import BeneyluClient
from ..models import MediaItem

class Source(ABC):
    name: str

    @abstractmethod
    def iter_items(self, client: BeneyluClient) -> Iterable[MediaItem]:
        """Yield every downloadable MediaItem this source exposes."""
