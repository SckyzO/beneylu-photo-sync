# tests/test_models.py
from beneylu_photo_sync.core.models import Card, ResolvedMedia, Board

def test_card_parses_attachments(fixture):
    cards = [Card.model_validate(c) for c in fixture("cards.json")]
    img, txt = cards
    assert img.type == "image"
    assert img.attachments[0].media_id == 900000001
    assert img.attachments[0].entity_type == "Card"
    assert txt.attachments == []

def test_board_parses(fixture):
    boards = [Board.model_validate(b) for b in fixture("boards.json")]
    assert boards[0].name == "DANS LA CLASSE DES PS"

def test_resolved_media_parses(fixture):
    m = ResolvedMedia.model_validate(fixture("resolved_media.json"))
    assert m.label == "IMG_7363.jpg"
    assert m.downloadable is True
    assert m.url.startswith("https://")
