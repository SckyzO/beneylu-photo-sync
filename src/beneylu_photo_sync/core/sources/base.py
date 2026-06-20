# src/beneylu_photo_sync/core/sources/base.py
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

    def obsolete_roots(self, client: BeneyluClient) -> Iterable[str]:
        """Top-level storage path prefixes this source no longer owns (e.g.
        now-excluded boards), to be pruned from storage and state on the next
        sync. Default: nothing to prune."""
        return ()
