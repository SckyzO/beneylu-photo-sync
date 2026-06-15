# tests/test_fixtures.py
def test_fixtures_load(fixture):
    cards = fixture("cards.json")
    assert cards[0]["type"] == "image"
    assert cards[0]["cardAttachments"][0]["mediaId"] == 900000001
