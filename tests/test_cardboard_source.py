# tests/test_cardboard_source.py
import httpx
import respx
from ent_exporter.client import BeneyluClient
from ent_exporter.sources.cardboard import CardboardSource

BASE = "https://www.ent-ecole.fr"

@respx.mock
def test_cardboard_yields_only_image_attachments(fixture):
    respx.get(f"{BASE}/api/cardboard/boards").mock(return_value=httpx.Response(200, json=fixture("boards.json")[:1]))
    respx.get(f"{BASE}/api/cardboard/boards/board-uuid-1/cards").mock(
        return_value=httpx.Response(200, json=fixture("cards.json")))
    client = BeneyluClient(base_url=BASE, login="x", password="y")
    items = list(CardboardSource().iter_items(client))
    assert len(items) == 1  # text card has no attachments
    assert items[0].media_id == 900000001
    assert items[0].board.name == "DANS LA CLASSE DES PS"
    assert items[0].card.id == "card-uuid-1"

@respx.mock
def test_cardboard_skips_non_image_card_with_attachment(fixture):
    cards = [
        {"type": "file", "id": "card-file", "creatorId": 300, "content": None,
         "description": "Doc", "createdAt": "2026-06-12T18:24:16+02:00",
         "updatedAt": "2026-06-12T18:24:16+02:00", "position": 1,
         "cardAttachments": [{"mediaId": 999, "resourceId": None, "entityId": "card-file",
                              "entityType": "Card", "timestamp": 1781479136, "signature": "sigX"}]},
    ]
    respx.get(f"{BASE}/api/cardboard/boards").mock(return_value=httpx.Response(200, json=fixture("boards.json")[:1]))
    respx.get(f"{BASE}/api/cardboard/boards/board-uuid-1/cards").mock(
        return_value=httpx.Response(200, json=cards))
    client = BeneyluClient(base_url=BASE, login="x", password="y")
    items = list(CardboardSource().iter_items(client))
    assert items == []  # non-image card excluded even though it carries an attachment


def test_source_has_name():
    assert CardboardSource().name == "cardboard"


@respx.mock
def test_cardboard_excludes_board_by_substring_case_insensitive(fixture):
    respx.get(f"{BASE}/api/cardboard/boards").mock(
        return_value=httpx.Response(200, json=fixture("boards.json")[:1]))
    client = BeneyluClient(base_url=BASE, login="x", password="y")
    # boards.json[0].name == "DANS LA CLASSE DES PS"; exclude via lowercase substring.
    src = CardboardSource(excluded_boards=["dans la classe"])
    assert list(src.iter_items(client)) == []  # the only board is filtered out

def test_cardboard_default_excludes_nothing():
    assert CardboardSource().name == "cardboard"
    assert CardboardSource(excluded_boards=[]) is not None
    assert CardboardSource(excluded_boards=["  "])._is_excluded("Anything") is False
