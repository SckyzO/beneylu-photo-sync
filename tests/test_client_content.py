# tests/test_client_content.py
import httpx
import respx
from ent_exporter.client import BeneyluClient
from ent_exporter.models import CardAttachment

BASE = "https://www.ent-ecole.fr"

def _client():
    return BeneyluClient(base_url=BASE, login="x", password="y")

@respx.mock
def test_boards_filters_archived_hidden(fixture):
    data = fixture("boards.json") + [{"id": "b3", "name": "old", "archived": True, "isHidden": False}]
    respx.get(f"{BASE}/api/cardboard/boards").mock(return_value=httpx.Response(200, json=data))
    boards = _client().boards()
    assert [b.name for b in boards] == ["DANS LA CLASSE DES PS", "APEIT"]

@respx.mock
def test_cards(fixture):
    respx.get(f"{BASE}/api/cardboard/boards/board-uuid-1/cards").mock(
        return_value=httpx.Response(200, json=fixture("cards.json")))
    cards = _client().cards("board-uuid-1")
    assert cards[0].attachments[0].media_id == 900000001

@respx.mock
def test_resolve_media_builds_signed_query(fixture):
    att = CardAttachment(mediaId=900000001, entityId="card-uuid-1", entityType="Card",
                         timestamp=1781479136, signature="sigA")
    route = respx.get(f"{BASE}/api/media-library/media/900000001").mock(
        return_value=httpx.Response(200, json=fixture("resolved_media.json")))
    media = _client().resolve_media(att)
    assert media.label == "IMG_7363.jpg"
    q = dict(route.calls.last.request.url.params)
    assert q == {"mediaId": "900000001", "entityId": "card-uuid-1",
                 "entityType": "Card", "timestamp": "1781479136", "signature": "sigA"}

@respx.mock
def test_download_streams_bytes():
    respx.get("https://s3.example.test/x.jpg").mock(
        return_value=httpx.Response(200, content=b"\xff\xd8\xffDATA"))
    chunks = b"".join(_client().download("https://s3.example.test/x.jpg"))
    assert chunks == b"\xff\xd8\xffDATA"
