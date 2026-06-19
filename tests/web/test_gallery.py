from ent_exporter.web.gallery import scan, safe_resolve


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_scan_groups_by_board_then_month(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")
    _touch(tmp_path / "PS" / "2026-05" / "b.png")
    _touch(tmp_path / ".thumbnails" / "PS" / "2026-06" / "a.jpg.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "notes.txt")  # non-image ignored

    boards = scan(tmp_path)
    assert [b.board for b in boards] == ["PS"]
    months = boards[0].months
    assert [m.month for m in months] == ["2026-06", "2026-05"]  # newest first
    assert [p.name for p in months[0].photos] == ["a.jpg"]
    assert months[0].photos[0].key == "PS/2026-06/a.jpg"


def test_scan_finds_photos_nested_in_sections(tmp_path):
    # Section grouping nests photos under board/month/<section>/file.
    _touch(tmp_path / "PS" / "2026-06" / "Sortie ferme" / "x.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "Arts" / "y.jpg")
    _touch(tmp_path / "PS" / "2026-05" / "sans-titre" / "z.png")

    boards = scan(tmp_path)
    assert [b.board for b in boards] == ["PS"]
    assert [m.month for m in boards[0].months] == ["2026-06", "2026-05"]
    june_keys = [p.key for p in boards[0].months[0].photos]
    assert "PS/2026-06/Arts/y.jpg" in june_keys
    assert "PS/2026-06/Sortie ferme/x.jpg" in june_keys
    assert boards[0].months[1].photos[0].key == "PS/2026-05/sans-titre/z.png"


def test_scan_missing_root_is_empty(tmp_path):
    assert scan(tmp_path / "nope") == []


def test_safe_resolve_rejects_traversal(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")
    assert safe_resolve(tmp_path, "PS/2026-06/a.jpg") is not None
    assert safe_resolve(tmp_path, "../secret") is None
    assert safe_resolve(tmp_path, "PS/2026-06/missing.jpg") is None
