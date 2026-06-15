# src/ent_exporter/sources/cardboard.py
from __future__ import annotations
from typing import Iterable
from .base import Source
from ..client import BeneyluClient
from ..models import MediaItem

class CardboardSource(Source):
    name = "cardboard"

    def iter_items(self, client: BeneyluClient) -> Iterable[MediaItem]:
        for board in client.boards():
            for card in client.cards(board.id):
                if card.type != "image":
                    continue
                for att in card.attachments:
                    yield MediaItem(media_id=att.media_id, attachment=att, board=board, card=card)
