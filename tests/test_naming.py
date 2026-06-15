# tests/test_naming.py
from datetime import datetime
from ent_exporter.naming import path_for, sanitize, month_folder

def test_sanitize_removes_unsafe_chars():
    assert sanitize("DANS LA CLASSE DES PS") == "DANS LA CLASSE DES PS"
    assert sanitize("a/b:c*?.jpg") == "a_b_c__.jpg"

def test_month_folder_from_datetime():
    assert month_folder(datetime(2026, 6, 12)) == "2026-06"

def test_path_for_uses_board_month_label():
    p = path_for(board_name="DANS LA CLASSE DES PS", label="IMG_7363.jpg",
                 taken_at=datetime(2026, 6, 12), media_id=900000001)
    assert p == "DANS LA CLASSE DES PS/2026-06/IMG_7363.jpg"

def test_path_for_disambiguates_on_collision():
    p = path_for(board_name="B", label="IMG.jpg", taken_at=datetime(2026, 6, 1),
                 media_id=42, exists=lambda key: key == "B/2026-06/IMG.jpg")
    assert p == "B/2026-06/IMG_42.jpg"
