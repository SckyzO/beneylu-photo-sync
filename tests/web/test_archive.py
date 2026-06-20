import zipfile
from pathlib import Path
from ent_exporter.web.archive import build_zip
from ent_exporter.web.thumbnails import THUMB_DIR


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
