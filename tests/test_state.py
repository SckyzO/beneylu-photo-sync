# tests/test_state.py
from ent_exporter.state import StateStore

def test_record_then_has(tmp_path):
    st = StateStore(tmp_path / "state.db")
    assert st.has(900000001) is False
    st.record(media_id=900000001, board_id="b1", card_id="c1", path="b1/a.jpg", card_updated_at="2026-06-12T18:24:16+02:00")
    assert st.has(900000001) is True
    st.close()

def test_persists_across_instances(tmp_path):
    db = tmp_path / "state.db"
    StateStore(db).record(900000001, "b1", "c1", "b1/a.jpg", "2026-06-12T18:24:16+02:00")
    assert StateStore(db).has(900000001) is True

def test_record_is_idempotent(tmp_path):
    st = StateStore(tmp_path / "state.db")
    st.record(900000001, "b1", "c1", "b1/a.jpg", "t")
    st.record(900000001, "b1", "c1", "b1/a.jpg", "t")  # no exception
    assert st.count() == 1

def test_forget_prefix_drops_matching_rows(tmp_path):
    st = StateStore(tmp_path / "state.db")
    st.record(1, "a", "c", "Board A/2026-06/a.jpg", "t")
    st.record(2, "a", "c", "Board A/2026-05/b.jpg", "t")
    st.record(3, "b", "c", "Board B/2026-06/c.jpg", "t")
    # forgetting a board prefix lets a later un-exclude re-download its photos
    removed = st.forget_prefix("Board A")
    assert removed == 2
    assert st.has(1) is False and st.has(2) is False
    assert st.has(3) is True
    # "Board A" must not match "Board AB"
    st.record(4, "ab", "c", "Board AB/x.jpg", "t")
    assert st.forget_prefix("Board A") == 0
    assert st.has(4) is True
