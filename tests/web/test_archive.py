import zipfile
from pathlib import Path
from beneylu_photo_sync.web.archive import build_zip
from beneylu_photo_sync.web.thumbnails import THUMB_DIR


def _touch(p: Path, data: bytes = b"x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_build_zip_includes_only_images_relative_to_root(tmp_path):
    root = tmp_path
    _touch(root / "PS" / "2026-06" / "Sortie" / "a.jpg")
    _touch(root / "PS" / "2026-06" / "Sortie" / "b.png")
    _touch(root / "PS" / "2026-06" / "Sortie" / "notes.txt")        # excluded: not an image
    _touch(root / THUMB_DIR / "PS" / "2026-06" / "Sortie" / "a.jpg")  # excluded: thumbnail
    zip_path = build_zip(root, root / "PS")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = sorted(zf.namelist())
        assert names == ["PS/2026-06/Sortie/a.jpg", "PS/2026-06/Sortie/b.png"]
    finally:
        Path(zip_path).unlink()


def test_build_zip_empty_directory_yields_empty_archive(tmp_path):
    (tmp_path / "PS").mkdir()
    zip_path = build_zip(tmp_path, tmp_path / "PS")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            assert zf.namelist() == []
    finally:
        Path(zip_path).unlink()


def test_build_zip_cleans_up_temp_on_failure(tmp_path, monkeypatch):
    import os
    import beneylu_photo_sync.web.archive as archive_mod
    (tmp_path / "PS" / "2026-06").mkdir(parents=True)
    (tmp_path / "PS" / "2026-06" / "a.jpg").write_bytes(b"x")

    created = []
    real_zipfile = archive_mod.zipfile.ZipFile

    class BoomZip(real_zipfile):
        def write(self, *a, **k):
            raise OSError("disk full")

    # Capture the temp path the helper creates, then force the write to blow up.
    real_named = archive_mod.tempfile.NamedTemporaryFile
    def tracking_named(*a, **k):
        f = real_named(*a, **k)
        created.append(f.name)
        return f
    monkeypatch.setattr(archive_mod.tempfile, "NamedTemporaryFile", tracking_named)
    monkeypatch.setattr(archive_mod.zipfile, "ZipFile", BoomZip)

    import pytest
    with pytest.raises(OSError):
        archive_mod.build_zip(tmp_path, tmp_path / "PS")

    # The orphaned temp file must not be left behind.
    assert created, "expected the helper to create a temp file"
    assert not os.path.exists(created[0])
