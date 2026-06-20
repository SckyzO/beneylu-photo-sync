# src/ent_exporter/sources/cardboard.py
from __future__ import annotations
from typing import Iterable
from .base import Source
from ..client import BeneyluClient
from ..models import MediaItem

class CardboardSource(Source):
    name = "cardboard"

    def __init__(self, excluded_boards: list[str] | None = None):
        # Lowercased, blank-stripped exclusion terms; matched as substrings.
        self._excluded = [b.casefold() for b in (excluded_boards or []) if b.strip()]

    def _is_excluded(self, board_name: str) -> bool:
        name = board_name.casefold()
        return any(term in name for term in self._excluded)

    def iter_items(self, client: BeneyluClient) -> Iterable[MediaItem]:
        for board in client.boards():
            if self._is_excluded(board.name):
                continue
            for card in client.cards(board.id):
                if card.type != "image":
                    continue
                for att in card.attachments:
                    yield MediaItem(media_id=att.media_id, attachment=att, board=board, card=card)
