# tests/test_sync.py
from ent_exporter.sync import Synchronizer
from ent_exporter.models import Board, Card, CardAttachment, MediaItem, ResolvedMedia


def _item(media_id=1, description=None):
    att = CardAttachment(mediaId=media_id, entityId="c1", entityType="Card", timestamp=1, signature="s")
    board = Board(id="b1", name="B")
    card = Card(id="c1", type="image", description=description,
                createdAt="2026-06-12T18:24:16+02:00",
                updatedAt="2026-06-12T18:24:16+02:00", cardAttachments=[att])
    return MediaItem(media_id=media_id, attachment=att, board=board, card=card)

class FakeSource:
    name = "fake"
    def __init__(self, items, obsolete=()):
        self._items = items
        self._obsolete = obsolete
    def iter_items(self, client): return iter(self._items)
    def obsolete_roots(self, client): return iter(self._obsolete)

class FakeClient:
    def __init__(self, payload: bytes = b"DATA"):
        self.downloaded = []
        self.payload = payload
    def resolve_media(self, att):
        return ResolvedMedia(id=att.media_id, label=f"IMG_{att.media_id}.jpg",
                             mime_type="image/jpeg", downloadable=True,
                             url=f"https://s3/{att.media_id}.jpg")
    def download(self, url):
        self.downloaded.append(url)
        yield self.payload

class FakeStorage:
    def __init__(self): self.written, self.removed = {}, []
    def exists(self, key): return key in self.written
    def write(self, key, stream): self.written[key] = b"".join(stream)
    def remove(self, key):
        hit = [k for k in self.written if k == key or k.startswith(key + "/")]
        for k in hit:
            del self.written[k]
        self.removed.append(key)
        return bool(hit)

class FakeState:
    def __init__(self, known=()):
        self._known = set(known)
        self.forgotten = []
    def has(self, mid): return mid in self._known
    def record(self, **kw): self._known.add(kw["media_id"])
    def forget_prefix(self, prefix):
        self.forgotten.append(prefix)
        return 0

def test_sync_downloads_new_item():
    client, storage, state = FakeClient(), FakeStorage(), FakeState()
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 1
    assert "B/2026-06/sans-titre/IMG_1.jpg" in storage.written

def test_sync_groups_photos_by_card_section():
    client, storage, state = FakeClient(), FakeStorage(), FakeState()
    item = _item(1, description="Sortie scolaire ferme pédagogique")
    report = Synchronizer(client, [FakeSource([item])], storage, state).run()
    assert report.downloaded == 1
    assert "B/2026-06/Sortie scolaire ferme pédagogique/IMG_1.jpg" in storage.written

def test_sync_skips_known_item():
    client, storage, state = FakeClient(), FakeStorage(), FakeState(known={1})
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 0
    assert report.skipped == 1
    assert client.downloaded == []

def test_per_item_error_does_not_abort_run():
    class ExplodingClient(FakeClient):
        def resolve_media(self, att):
            if att.media_id == 1:
                raise RuntimeError("boom")
            return super().resolve_media(att)
    client, storage, state = ExplodingClient(), FakeStorage(), FakeState()
    report = Synchronizer(client, [FakeSource([_item(1), _item(2)])], storage, state).run()
    assert report.downloaded == 1
    assert report.errors == 1
    assert "B/2026-06/sans-titre/IMG_2.jpg" in storage.written

def test_sync_prunes_now_excluded_roots_before_downloading():
    client, storage, state = FakeClient(), FakeStorage(), FakeState()
    storage.written["OldBoard/2026-06/x.jpg"] = b"old"   # previously synced board
    src = FakeSource([_item(1)], obsolete=["OldBoard"])   # now filtered out
    report = Synchronizer(client, [src], storage, state).run()
    assert report.pruned == 1
    assert "OldBoard/2026-06/x.jpg" not in storage.written   # filtered content removed
    assert "OldBoard" in storage.removed
    assert state.forgotten == ["OldBoard"]                   # state kept consistent
    assert "B/2026-06/sans-titre/IMG_1.jpg" in storage.written  # kept board still synced


def test_sync_groups_by_publication_month():
    client, storage, state = FakeClient(), FakeStorage(), FakeState()
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 1
    # 2026-06 comes from card.created_at, regardless of any image metadata.
    assert "B/2026-06/sans-titre/IMG_1.jpg" in storage.written
