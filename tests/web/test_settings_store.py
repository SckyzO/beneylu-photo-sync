import json
import stat
from pathlib import Path
from ent_exporter.web.settings_store import SettingsStore


def test_save_writes_0600_and_roundtrips(tmp_path, monkeypatch):
    monkeypatch.delenv("ENT_LOGIN", raising=False)
    monkeypatch.delenv("ENT_PASSWORD", raising=False)
    cfg_file = tmp_path / "config.json"
    store = SettingsStore(cfg_file)
    store.save(login="alice", password="s3cret", sync_interval_hours=6)

    mode = stat.S_IMODE(cfg_file.stat().st_mode)
    assert mode == 0o600
    eff = store.effective()
    assert eff.login == "alice"
    assert eff.password == "s3cret"
    assert eff.sync_interval_hours == 6
    assert eff.has_password is True


def test_empty_password_does_not_wipe_existing(tmp_path, monkeypatch):
    monkeypatch.delenv("ENT_PASSWORD", raising=False)
    store = SettingsStore(tmp_path / "config.json")
    store.save(login="alice", password="keepme")
    store.save(login="alice2", password="")  # user left password blank
    data = json.loads(Path(tmp_path / "config.json").read_text())
    assert data["password"] == "keepme"
    assert data["login"] == "alice2"


def test_env_overrides_file(tmp_path, monkeypatch):
    store = SettingsStore(tmp_path / "config.json")
    store.save(login="file-user", password="file-pw")
    monkeypatch.setenv("ENT_LOGIN", "env-user")
    monkeypatch.setenv("ENT_PASSWORD", "env-pw")
    eff = store.effective()
    assert eff.login == "env-user"
    assert eff.password == "env-pw"


def test_excluded_boards_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("ENT_EXCLUDED_BOARDS", raising=False)
    store = SettingsStore(tmp_path / "config.json")
    store.save(login="a", password="p", excluded_boards=["APEIT", "Foo"])
    assert store.effective().excluded_boards == ["APEIT", "Foo"]

def test_excluded_boards_env_overrides_file(tmp_path, monkeypatch):
    store = SettingsStore(tmp_path / "config.json")
    store.save(login="a", password="p", excluded_boards=["FromFile"])
    monkeypatch.setenv("ENT_EXCLUDED_BOARDS", "EnvA, EnvB")
    assert store.effective().excluded_boards == ["EnvA", "EnvB"]

def test_excluded_boards_default_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("ENT_EXCLUDED_BOARDS", raising=False)
    store = SettingsStore(tmp_path / "config.json")
    store.save(login="a", password="p")
    assert store.effective().excluded_boards == []
