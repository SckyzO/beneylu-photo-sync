import json
import threading
import pytest
from fastapi.testclient import TestClient
from ent_exporter.web.app import create_app
from ent_exporter.web.settings_store import SettingsStore
from ent_exporter.web.jobs import SyncRunner


class FakeReport:
    downloaded, skipped, errors = 0, 0, 0


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


@pytest.fixture
def env(tmp_path, monkeypatch):
    for k in ("ENT_LOGIN", "ENT_PASSWORD", "ENT_WEB_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENT_CONFIG_FILE", str(tmp_path / "config.json"))
    return tmp_path


def _client(env):
    store = SettingsStore(env / "config.json")
    triggered = threading.Event()
    runner = SyncRunner(lambda: FakeReport())
    runner.trigger = lambda: (triggered.set(), True)[1]  # don't really sync
    app = create_app(store=store, runner=runner)
    return TestClient(app), triggered, store


def test_gallery_renders(env):
    _touch(env / "PS" / "2026-06" / "a.jpg")
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert "PS" in r.text


def test_sync_triggers_runner(env):
    client, triggered, _ = _client(env)
    r = client.post("/sync", follow_redirects=False)
    assert r.status_code == 303
    assert triggered.is_set()


def test_status_endpoint_is_json(env):
    client, _, _ = _client(env)
    r = client.get("/api/status")
    assert r.status_code == 200
    body = json.loads(r.text)
    assert body["state"] == "idle"


def test_config_post_writes_file_and_hides_secret(env):
    client, _, store = _client(env)
    r = client.post("/config",
                    data={"login": "alice", "password": "topsecret",
                          "sync_interval_hours": "6"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert store.effective().login == "alice"
    page = client.get("/config")
    assert "topsecret" not in page.text  # write-only secret never echoed


def test_photo_route_rejects_traversal(env):
    client, _, _ = _client(env)
    r = client.get("/photo/../config.json")
    assert r.status_code == 404


def test_thumb_rejects_non_image(env):
    # A real file under the data root but not an image must 404, not 500.
    _touch(env / "PS" / "2026-06" / "notes.txt")
    client, _, _ = _client(env)
    assert client.get("/thumb/PS/2026-06/notes.txt").status_code == 404
    assert client.get("/photo/PS/2026-06/notes.txt").status_code == 404


def test_password_gate_redirects_to_login(env, monkeypatch):
    monkeypatch.setenv("ENT_WEB_PASSWORD", "letmein")
    store = SettingsStore(env / "config.json")
    app = create_app(store=store, runner=SyncRunner(lambda: FakeReport()))
    client = TestClient(app)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    ok = client.post("/login", data={"password": "letmein"},
                     follow_redirects=False)
    assert ok.status_code == 303
    assert client.get("/", follow_redirects=False).status_code == 200
