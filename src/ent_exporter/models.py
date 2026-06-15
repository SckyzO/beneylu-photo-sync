# src/ent_exporter/models.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field

class Board(BaseModel):
    id: str
    name: str
    archived: bool = False
    is_hidden: bool = Field(default=False, alias="isHidden")
    model_config = {"populate_by_name": True}

class CardAttachment(BaseModel):
    media_id: int = Field(alias="mediaId")
    entity_id: str = Field(alias="entityId")
    entity_type: str = Field(alias="entityType")
    timestamp: int
    signature: str
    model_config = {"populate_by_name": True}

class Card(BaseModel):
    id: str
    type: str
    description: str | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    attachments: list[CardAttachment] = Field(default_factory=list, alias="cardAttachments")
    model_config = {"populate_by_name": True}

class ResolvedMedia(BaseModel):
    id: int
    label: str
    mime_type: str = Field(alias="mime_type")
    downloadable: bool
    url: str
    display_url: str | None = None
    model_config = {"populate_by_name": True}

class MediaItem(BaseModel):
    """One downloadable photo produced by a Source, before resolution."""
    media_id: int
    attachment: CardAttachment
    board: Board
    card: Card
