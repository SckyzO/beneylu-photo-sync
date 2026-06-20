# tests/test_naming.py
from datetime import datetime
from ent_exporter.naming import path_for, sanitize, month_folder, section_folder

def test_sanitize_removes_unsafe_chars():
    assert sanitize("DANS LA CLASSE DES PS") == "DANS LA CLASSE DES PS"
    assert sanitize("a/b:c*?.jpg") == "a_b_c__.jpg"

def test_month_folder_from_datetime():
    assert month_folder(datetime(2026, 6, 12)) == "2026-06"

def test_section_folder_keeps_clean_label():
    assert section_folder("Arts visuels") == "Arts visuels"
    assert section_folder("Maths:quantités") == "Maths_quantités"

def test_section_folder_keeps_only_first_line():
    desc = "Écrit\n -Graphisme: échelles\n -Écrire son prénom"
    assert section_folder(desc) == "Écrit"

def test_section_folder_cuts_at_first_inline_bullet():
    assert section_folder("Explorer le monde -Entraînement au découpage") == "Explorer le monde"

def test_section_folder_first_line_with_colon():
    # First line only; the colon is path-sanitized to underscore.
    assert section_folder("ARTS:\nThématiques printemps") == "ARTS_"

def test_section_folder_blank_or_empty_falls_back():
    assert section_folder(None) == "sans-titre"
    assert section_folder("") == "sans-titre"
    assert section_folder("   \n  ") == "sans-titre"
    assert section_folder("...") == "sans-titre"

def test_section_folder_truncates_long_description():
    s = section_folder("Maths: " + "abcde " * 40)
    assert len(s) <= 60
    assert s.startswith("Maths_ abcde")

def test_path_for_uses_board_month_section_label():
    p = path_for(board_name="DANS LA CLASSE DES PS", section="Arts visuels",
                 label="IMG_7363.jpg", taken_at=datetime(2026, 6, 12), media_id=900000001)
    assert p == "DANS LA CLASSE DES PS/2026-06/Arts visuels/IMG_7363.jpg"

def test_path_for_blank_section_uses_fallback_folder():
    p = path_for(board_name="B", section=None, label="IMG.jpg",
                 taken_at=datetime(2026, 6, 1), media_id=7)
    assert p == "B/2026-06/sans-titre/IMG.jpg"

def test_path_for_disambiguates_on_collision():
    p = path_for(board_name="B", section="S", label="IMG.jpg", taken_at=datetime(2026, 6, 1),
                 media_id=42, exists=lambda key: key == "B/2026-06/S/IMG.jpg")
    assert p == "B/2026-06/S/IMG_42.jpg"
