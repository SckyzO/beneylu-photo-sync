from PIL import Image
from ent_exporter.web.thumbnails import get_or_create, THUMB_DIR


def _make_image(path, size=(800, 600)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 30, 30)).save(path, "JPEG")


def test_creates_and_caches_thumbnail(tmp_path):
    src = tmp_path / "PS" / "2026-06" / "a.jpg"
    _make_image(src)
    out = get_or_create(tmp_path, src, "PS/2026-06/a.jpg")
    assert out.is_file()
    assert THUMB_DIR in out.parts
    with Image.open(out) as im:
        assert max(im.size) <= 320

    mtime = out.stat().st_mtime_ns
    out2 = get_or_create(tmp_path, src, "PS/2026-06/a.jpg")  # cached
    assert out2 == out
    assert out2.stat().st_mtime_ns == mtime  # not regenerated
