import io
import json
import threading
import zipfile
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


def test_config_page_is_cosmos_styled(env):
    client, _, _ = _client(env)
    r = client.get("/config")
    assert r.status_code == 200
    assert "focus:ring-brand-500/10" in r.text  # cosmos input styling present
    assert 'name="login"' in r.text


def test_login_page_is_cosmos_styled(env, monkeypatch):
    monkeypatch.setenv("ENT_WEB_PASSWORD", "secret")
    client, _, _ = _client(env)  # rebuilds app with login route mounted
    r = client.get("/login")
    assert r.status_code == 200
    assert "rounded-2xl" in r.text  # cosmos card present
    assert 'name="password"' in r.text


def test_gallery_renders_section_heading(env):
    _touch(env / "PS" / "2026-06" / "Sortie ferme" / "a.jpg")
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert "Sortie ferme" in r.text
    assert "/thumb/PS/2026-06/Sortie ferme/a.jpg" in r.text


def test_base_uses_cosmos_css_and_dark_default(env):
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert "/static/cosmos.css" in r.text
    assert 'class="dark"' in r.text
    assert "/static/style.css" not in r.text
    assert 'id="theme-toggle"' in r.text


def test_branding_uses_name_and_svg_icons(env):
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert "Beneylu Photo Sync" in r.text       # new display name
    assert "ent_exporter" not in r.text          # old name gone from the page
    assert "📸" not in r.text and "☀️" not in r.text and "🌙" not in r.text  # no emoji
    assert r.text.count("<svg") >= 3             # camera + sun + moon marks


def test_config_page_centered_with_exclude_field(env):
    client, _, _ = _client(env)
    r = client.get("/config")
    assert r.status_code == 200
    assert "mx-auto" in r.text and "max-w-md" in r.text   # centered cosmos card
    assert 'name="excluded_boards"' in r.text             # new field present


def test_config_post_persists_excluded_boards(env):
    client, _, store = _client(env)
    r = client.post("/config",
                    data={"login": "alice", "password": "", "sync_interval_hours": "0",
                          "excluded_boards": "APEIT, Vie de l'école"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert store.effective().excluded_boards == ["APEIT", "Vie de l'école"]
    # Pre-filled back into the form on the next GET.
    page = client.get("/config")
    assert "APEIT, Vie de l'école" in page.text


def test_gallery_has_section_count_badge_and_download_all(env):
    _touch(env / "PS" / "2026-06" / "Sortie ferme" / "a.jpg")
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert "Tout télécharger" in r.text          # global download button
    assert 'aspect-square' in r.text             # square tiles redesign


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


def test_gallery_thumbnails_carry_lightbox_markers(env):
    _touch(env / "PS" / "2026-06" / "Sortie ferme" / "a.jpg")
    client, _, _ = _client(env)
    r = client.get("/")
    assert 'class="js-photo"' in r.text
    assert "data-lightbox-group" in r.text
    assert 'data-full="/photo/PS/2026-06/Sortie ferme/a.jpg"' in r.text


def test_download_all_returns_zip(env):
    _touch(env / "PS" / "2026-06" / "Sortie" / "a.jpg")
    client, _, _ = _client(env)
    r = client.get("/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert "PS/2026-06/Sortie/a.jpg" in zf.namelist()


def test_download_section_subtree(env):
    _touch(env / "PS" / "2026-06" / "Sortie" / "a.jpg")
    _touch(env / "PS" / "2026-06" / "Autre" / "b.jpg")
    client, _, _ = _client(env)
    r = client.get("/download/PS/2026-06/Sortie")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert zf.namelist() == ["PS/2026-06/Sortie/a.jpg"]


def test_download_rejects_traversal_and_unknown(env):
    client, _, _ = _client(env)
    assert client.get("/download/../config.json").status_code == 404
    assert client.get("/download/Nope/2099-01").status_code == 404


def test_download_thumbnail_dir_is_404(env):
    from ent_exporter.web.thumbnails import THUMB_DIR
    _touch(env / THUMB_DIR / "x.jpg")
    client, _, _ = _client(env)
    assert client.get(f"/download/{THUMB_DIR}").status_code == 404
