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
