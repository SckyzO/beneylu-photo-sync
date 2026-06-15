# tests/test_filesystem_storage.py
from ent_exporter.storage.filesystem import FilesystemStorage

def test_write_then_exists(tmp_path):
    s = FilesystemStorage(tmp_path)
    assert s.exists("board/2026-06/a.jpg") is False
    s.write("board/2026-06/a.jpg", iter([b"\xff\xd8", b"DATA"]))
    assert s.exists("board/2026-06/a.jpg") is True
    assert (tmp_path / "board" / "2026-06" / "a.jpg").read_bytes() == b"\xff\xd8DATA"

def test_write_is_atomic_no_partial_on_error(tmp_path):
    s = FilesystemStorage(tmp_path)
    def boom():
        yield b"partial"
        raise RuntimeError("network died")
    import pytest
    with pytest.raises(RuntimeError):
        s.write("board/x.jpg", boom())
    assert s.exists("board/x.jpg") is False
    assert list(tmp_path.rglob("*.part")) == []
