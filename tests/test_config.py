# tests/test_config.py
from beneylu_photo_sync.core.config import Settings

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("ENT_LOGIN", "parent.test")
    monkeypatch.setenv("ENT_PASSWORD", "secret")
    monkeypatch.setenv("ENT_DATA_DIR", "/tmp/ent-data")
    s = Settings()
    assert s.login == "parent.test"
    assert s.password.get_secret_value() == "secret"
    assert str(s.data_dir) == "/tmp/ent-data"
    assert s.base_url == "https://www.ent-ecole.fr"

def test_password_not_in_repr(monkeypatch):
    monkeypatch.setenv("ENT_LOGIN", "x")
    monkeypatch.setenv("ENT_PASSWORD", "topsecret")
    s = Settings()
    assert "topsecret" not in repr(s)

def test_excluded_boards_parsed_from_comma_list(monkeypatch):
    monkeypatch.setenv("ENT_LOGIN", "x")
    monkeypatch.setenv("ENT_PASSWORD", "y")
    monkeypatch.setenv("ENT_EXCLUDED_BOARDS", "APEIT, Vie de l'école ")
    s = Settings()
    assert s.excluded_boards == ["APEIT", "Vie de l'école"]

def test_excluded_boards_defaults_empty(monkeypatch):
    monkeypatch.setenv("ENT_LOGIN", "x")
    monkeypatch.setenv("ENT_PASSWORD", "y")
    monkeypatch.delenv("ENT_EXCLUDED_BOARDS", raising=False)
    assert Settings().excluded_boards == []
