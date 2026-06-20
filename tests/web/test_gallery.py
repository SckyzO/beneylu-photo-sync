from beneylu_photo_sync.web.gallery import scan, safe_resolve


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_scan_groups_by_board_month_section(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "Sortie" / "a.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "Arts" / "b.png")
    _touch(tmp_path / "PS" / "2026-05" / "sans-titre" / "c.jpg")
    _touch(tmp_path / ".thumbnails" / "PS" / "2026-06" / "Sortie" / "a.jpg.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "Sortie" / "notes.txt")  # non-image ignored

    boards = scan(tmp_path)
    assert [b.board for b in boards] == ["PS"]
    months = boards[0].months
    assert [m.month for m in months] == ["2026-06", "2026-05"]  # newest first
    assert [s.section for s in months[0].sections] == ["Arts", "Sortie"]  # alpha
    assert months[0].sections[0].photos[0].key == "PS/2026-06/Arts/b.png"
    assert months[1].sections[0].section == "sans-titre"


def test_scan_legacy_two_level_becomes_sans_titre(tmp_path):
    # board/month/file (no section folder) -> single "sans-titre" section.
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")
    boards = scan(tmp_path)
    sections = boards[0].months[0].sections
    assert [s.section for s in sections] == ["sans-titre"]
    assert sections[0].photos[0].key == "PS/2026-06/a.jpg"


def test_scan_sans_titre_sorted_last(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "Zoo" / "a.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")  # -> sans-titre
    boards = scan(tmp_path)
    assert [s.section for s in boards[0].months[0].sections] == ["Zoo", "sans-titre"]


def test_scan_missing_root_is_empty(tmp_path):
    assert scan(tmp_path / "nope") == []


def test_safe_resolve_rejects_traversal(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")
    assert safe_resolve(tmp_path, "PS/2026-06/a.jpg") is not None
    assert safe_resolve(tmp_path, "../secret") is None
    assert safe_resolve(tmp_path, "PS/2026-06/missing.jpg") is None
