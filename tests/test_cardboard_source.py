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

def test_source_has_name():
    assert CardboardSource().name == "cardboard"
