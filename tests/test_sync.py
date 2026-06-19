# tests/test_sync.py
from io import BytesIO

from PIL import Image

from ent_exporter.sync import Synchronizer
from ent_exporter.models import Board, Card, CardAttachment, MediaItem, ResolvedMedia


def _jpeg(exif_date: str | None = None) -> bytes:
    img = Image.new("RGB", (2, 2))
    buf = BytesIO()
    if exif_date is None:
        img.save(buf, format="JPEG")
    else:
        exif = Image.Exif()
        exif.get_ifd(0x8769)[36867] = exif_date  # DateTimeOriginal
        img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _item(media_id=1, description=None):
    att = CardAttachment(mediaId=media_id, entityId="c1", entityType="Card", timestamp=1, signature="s")
    board = Board(id="b1", name="B")
    card = Card(id="c1", type="image", description=description,
                createdAt="2026-06-12T18:24:16+02:00",
                updatedAt="2026-06-12T18:24:16+02:00", cardAttachments=[att])
    return MediaItem(media_id=media_id, attachment=att, board=board, card=card)

class FakeSource:
    name = "fake"
    def __init__(self, items): self._items = items
    def iter_items(self, client): return iter(self._items)

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
    def __init__(self): self.written = {}
    def exists(self, key): return key in self.written
    def write(self, key, stream): self.written[key] = b"".join(stream)

class FakeState:
    def __init__(self, known=()): self._known = set(known)
    def has(self, mid): return mid in self._known
    def record(self, **kw): self._known.add(kw["media_id"])

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


def test_sync_uses_exif_capture_date_for_path():
    # card.createdAt is June 2026; EXIF DateTimeOriginal is March 2026.
    client = FakeClient(payload=_jpeg("2026:03:04 11:22:33"))
    storage, state = FakeStorage(), FakeState()
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 1
    assert "B/2026-03/sans-titre/IMG_1.jpg" in storage.written
    assert "B/2026-06/sans-titre/IMG_1.jpg" not in storage.written


def test_sync_falls_back_to_created_at_without_exif():
    client = FakeClient(payload=_jpeg(None))
    storage, state = FakeStorage(), FakeState()
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 1
    assert "B/2026-06/sans-titre/IMG_1.jpg" in storage.written
