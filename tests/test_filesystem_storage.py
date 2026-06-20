# tests/test_filesystem_storage.py
from beneylu_photo_sync.core.storage.filesystem import FilesystemStorage

def test_write_then_exists(tmp_path):
    s = FilesystemStorage(tmp_path)
    assert s.exists("board/2026-06/a.jpg") is False
    s.write("board/2026-06/a.jpg", iter([b"\xff\xd8", b"DATA"]))
    assert s.exists("board/2026-06/a.jpg") is True
    assert (tmp_path / "board" / "2026-06" / "a.jpg").read_bytes() == b"\xff\xd8DATA"

def test_remove_deletes_file_and_subtree(tmp_path):
    s = FilesystemStorage(tmp_path)
    s.write("Board A/2026-06/a.jpg", iter([b"x"]))
    s.write("Board A/2026-05/b.jpg", iter([b"y"]))
    s.write("Board B/2026-06/c.jpg", iter([b"z"]))
    # removing a top-level folder wipes the whole board subtree, not siblings
    assert s.remove("Board A") is True
    assert (tmp_path / "Board A").exists() is False
    assert s.exists("Board B/2026-06/c.jpg") is True
    # removing a single file works too
    assert s.remove("Board B/2026-06/c.jpg") is True
    assert s.exists("Board B/2026-06/c.jpg") is False


def test_remove_is_safe(tmp_path):
    s = FilesystemStorage(tmp_path)
    s.write("Board/x.jpg", iter([b"x"]))
    assert s.remove("missing") is False              # nothing to remove
    assert s.remove("") is False                     # never delete the root itself
    assert s.remove("../outside") is False           # never escape the root
    assert tmp_path.exists() is True
    assert s.exists("Board/x.jpg") is True


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
