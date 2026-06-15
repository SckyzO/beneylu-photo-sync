# tests/test_config.py
from ent_exporter.config import Settings

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
