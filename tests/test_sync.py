# tests/test_sync.py
from beneylu_photo_sync.core.sync import Synchronizer
from beneylu_photo_sync.core.models import Board, Card, CardAttachment, MediaItem, ResolvedMedia


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
    def __init__(self, known=None):
        # known: dict {media_id: recorded_path}, or an iterable of media_ids
        # (path unknown). Path lets the synchronizer self-heal: a recorded id
        # whose file is gone from disk must be re-downloaded, not skipped.
        if isinstance(known, dict):
            self._paths = dict(known)
        else:
            self._paths = {mid: None for mid in (known or ())}
        self.forgotten = []
    def has(self, mid): return mid in self._paths
    def path_for(self, mid): return self._paths.get(mid)
    def record(self, **kw): self._paths[kw["media_id"]] = kw["path"]
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
    # Recorded AND present on disk → genuine skip, no network call.
    path = "B/2026-06/sans-titre/IMG_1.jpg"
    client, storage, state = FakeClient(), FakeStorage(), FakeState(known={1: path})
    storage.written[path] = b"already-here"
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 0
    assert report.skipped == 1
    assert client.downloaded == []


def test_sync_redownloads_recorded_but_missing_on_disk():
    # State remembers media 1 but its file was deleted from disk: self-heal by
    # re-downloading instead of skipping a now-missing photo forever.
    path = "B/2026-06/sans-titre/IMG_1.jpg"
    client, storage, state = FakeClient(), FakeStorage(), FakeState(known={1: path})
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 1
    assert report.skipped == 0
    assert client.downloaded == ["https://s3/1.jpg"]
    assert path in storage.written

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


def test_sync_downloads_run_concurrently():
    # A barrier of size `workers` only releases when that many threads reach it
    # together: this passes under a bounded pool and would time out if serial.
    import threading
    workers = 3
    barrier = threading.Barrier(workers, timeout=5)

    class BarrierClient(FakeClient):
        def download(self, url):
            barrier.wait()
            yield self.payload

    items = [_item(i) for i in range(1, workers + 1)]
    report = Synchronizer(BarrierClient(), [FakeSource(items)], FakeStorage(),
                          FakeState(), workers=workers).run()
    assert report.downloaded == workers


def test_sync_parallel_preserves_all_results_and_isolates_errors():
    class ExplodingClient(FakeClient):
        def resolve_media(self, att):
            if att.media_id == 2:
                raise RuntimeError("boom")
            return super().resolve_media(att)
    items = [_item(i) for i in range(1, 5)]
    storage, state = FakeStorage(), FakeState()
    report = Synchronizer(ExplodingClient(), [FakeSource(items)], storage, state,
                          workers=4).run()
    assert report.downloaded == 3
    assert report.errors == 1
    assert report.error_items == [2]
    for i in (1, 3, 4):
        assert f"B/2026-06/sans-titre/IMG_{i}.jpg" in storage.written
    assert "B/2026-06/sans-titre/IMG_2.jpg" not in storage.written


def test_sync_groups_by_publication_month():
    client, storage, state = FakeClient(), FakeStorage(), FakeState()
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 1
    # 2026-06 comes from card.created_at, regardless of any image metadata.
    assert "B/2026-06/sans-titre/IMG_1.jpg" in storage.written
