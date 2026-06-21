import io
import json
import threading
import zipfile
import pytest
from fastapi.testclient import TestClient
from beneylu_photo_sync.web.app import create_app
from beneylu_photo_sync.web.settings_store import SettingsStore
from beneylu_photo_sync.web.jobs import SyncRunner


class FakeReport:
    downloaded, skipped, errors, pruned = 0, 0, 0, 0


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


@pytest.fixture
def env(tmp_path, monkeypatch):
    for k in ("ENT_LOGIN", "ENT_PASSWORD", "ENT_WEB_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENT_CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setenv("ENT_STATE_DB", str(tmp_path / "state.db"))
    return tmp_path


def _client(env, boards_provider=None):
    store = SettingsStore(env / "config.json")
    triggered = threading.Event()
    runner = SyncRunner(lambda on_progress=None: FakeReport())
    runner.trigger = lambda: (triggered.set(), True)[1]  # don't really sync
    app = create_app(store=store, runner=runner, boards_provider=boards_provider)
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


def test_thumb_corrupt_image_is_404_not_500(env):
    # A file with an image suffix but unreadable bytes must degrade to 404,
    # never crash the route with a 500.
    p = env / "PS" / "2026-06" / "broken.jpg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"not a real jpeg")
    client, _, _ = _client(env)
    assert client.get("/thumb/PS/2026-06/broken.jpg").status_code == 404


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
    assert "rounded-xl" in r.text  # cosmos card present
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
    assert "beneylu_photo_sync" not in r.text          # old name gone from the page
    assert "📸" not in r.text and "☀️" not in r.text and "🌙" not in r.text  # no emoji
    assert r.text.count("<svg") >= 3             # camera + sun + moon marks


def test_config_page_centered_with_exclude_field(env):
    client, _, _ = _client(env)
    r = client.get("/config")
    assert r.status_code == 200
    assert "mx-auto" in r.text and "max-w-md" in r.text   # centered cosmos card
    assert 'name="excluded_boards"' in r.text             # new field present


def test_config_page_has_back_to_gallery_link(env):
    client, _, _ = _client(env)
    r = client.get("/config")
    assert r.status_code == 200
    assert "Retour à la galerie" in r.text
    assert 'href="/"' in r.text


def test_corner_radius_is_homogeneous(env):
    # All rounded utilities collapse to a single token across the rendered UI.
    import re
    _touch(env / "PS" / "2026-06" / "S" / "a.jpg")
    client, _, _ = _client(env)
    radii = set(re.findall(r"rounded-\w+", client.get("/").text + client.get("/config").text))
    assert radii == {"rounded-xl"}, radii


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


def test_gallery_has_search_input_and_per_section_index(env):
    _touch(env / "PS" / "2026-06" / "Sortie ferme" / "a.jpg")
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="gallery-search"' in r.text                 # toolbar search box
    assert "data-search=" in r.text                        # per-section filter index
    # the index is lowercased board/month/section text
    assert "ps 2026-06 sortie ferme" in r.text


def test_section_download_is_icon_button_with_tooltip(env):
    _touch(env / "PS" / "2026-06" / "Sortie ferme" / "a.jpg")
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    # icon-only download affordance with an accessible label/tooltip
    assert 'aria-label="Télécharger la sélection"' in r.text
    assert 'title="Télécharger la sélection"' in r.text


def test_gallery_has_progressive_scroll_sentinel(env):
    _touch(env / "PS" / "2026-06" / "S1" / "a.jpg")
    _touch(env / "PS" / "2026-06" / "S2" / "b.jpg")
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="scroll-sentinel"' in r.text          # infinite-scroll trigger + loader
    assert "animate-spin" in r.text                  # spinner present


def test_header_nav_marks_active_route(env):
    client, _, _ = _client(env)
    gallery = client.get("/")
    assert 'href="/" aria-current="page"' in gallery.text          # gallery active
    config = client.get("/config")
    assert 'href="/config" aria-current="page"' in config.text     # config active


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


def test_download_section_subtree_with_accents_and_spaces(env):
    # Real board/section names carry spaces and accents; the URL-encoded path
    # must round-trip through the route back to the on-disk directory.
    board = "DANS LA CLASSE DES PS"
    section = "Vie de l'école"
    _touch(env / board / "2026-06" / section / "a.jpg")
    client, _, _ = _client(env)
    r = client.get(f"/download/{board}/2026-06/{section}")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert zf.namelist() == [f"{board}/2026-06/{section}/a.jpg"]


def test_download_rejects_traversal_and_unknown(env):
    client, _, _ = _client(env)
    assert client.get("/download/../config.json").status_code == 404
    assert client.get("/download/Nope/2099-01").status_code == 404


def test_download_thumbnail_dir_is_404(env):
    from beneylu_photo_sync.web.thumbnails import THUMB_DIR
    _touch(env / THUMB_DIR / "x.jpg")
    client, _, _ = _client(env)
    assert client.get(f"/download/{THUMB_DIR}").status_code == 404


def test_gallery_has_destructive_actions(env):
    # The destructive actions live in the gallery's sync dropdown (single source),
    # each behind a confirm modal carrying the typed token the server requires.
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="sync-menu"' in r.text
    assert 'action="/admin/wipe"' in r.text and 'action="/admin/resync"' in r.text
    assert 'value="SUPPRIMER"' in r.text and 'value="RESYNC"' in r.text


def test_config_page_has_no_danger_zone(env):
    # Danger zone was moved out of /config to avoid two places doing the same thing.
    client, _, _ = _client(env)
    r = client.get("/config")
    assert r.status_code == 200
    assert "Zone de danger" not in r.text


def test_admin_wipe_requires_typed_confirmation(env):
    _touch(env / "PS" / "2026-06" / "Sortie" / "a.jpg")
    client, _, _ = _client(env)
    r = client.post("/admin/wipe", data={"confirm": "nope"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/config?danger=wipe"
    assert (env / "PS" / "2026-06" / "Sortie" / "a.jpg").exists()  # nothing erased


def test_admin_wipe_clears_photos_and_state(env):
    from beneylu_photo_sync.core.state import StateStore
    _touch(env / "PS" / "2026-06" / "Sortie" / "a.jpg")
    _touch(env / ".thumbnails" / "PS" / "2026-06" / "Sortie" / "a.jpg.jpg")
    st = StateStore(env / "state.db")
    st.record(1, "b", "c", "PS/2026-06/Sortie/a.jpg", "t")
    st.close()
    client, _, _ = _client(env)
    r = client.post("/admin/wipe", data={"confirm": "SUPPRIMER"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert not (env / "PS").exists()             # board content removed
    assert not (env / ".thumbnails").exists()    # thumbnail cache removed
    after = StateStore(env / "state.db")
    assert after.count() == 0                    # state cleared
    after.close()


def test_admin_resync_requires_confirmation(env):
    _touch(env / "PS" / "2026-06" / "Sortie" / "a.jpg")
    client, triggered, _ = _client(env)
    r = client.post("/admin/resync", data={"confirm": "x"}, follow_redirects=False)
    assert r.status_code == 303
    assert not triggered.is_set()                # no sync kicked off
    assert (env / "PS" / "2026-06" / "Sortie" / "a.jpg").exists()


def test_admin_resync_wipes_then_triggers(env):
    from beneylu_photo_sync.core.state import StateStore
    _touch(env / "PS" / "2026-06" / "Sortie" / "a.jpg")
    st = StateStore(env / "state.db")
    st.record(1, "b", "c", "PS/2026-06/Sortie/a.jpg", "t")
    st.close()
    client, triggered, _ = _client(env)
    r = client.post("/admin/resync", data={"confirm": "RESYNC"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert not (env / "PS").exists()
    after = StateStore(env / "state.db")
    assert after.count() == 0
    after.close()
    assert triggered.is_set()                    # fresh full sync started


def test_api_boards_flags_excluded(env):
    client, _, store = _client(env, boards_provider=lambda: ["Classe PS", "APEIT", "Vie de l'école"])
    store.save(login="alice", password="pw", excluded_boards=["APEIT"])
    r = client.get("/api/boards")
    assert r.status_code == 200
    boards = {b["name"]: b["included"] for b in r.json()["boards"]}
    assert boards == {"Classe PS": True, "APEIT": False, "Vie de l'école": True}


def test_api_boards_requires_credentials(env):
    client, _, _ = _client(env, boards_provider=lambda: ["X"])
    r = client.get("/api/boards")
    assert r.status_code == 400
    assert "error" in r.json()


def test_api_boards_handles_listing_failure(env):
    def boom():
        raise RuntimeError("ENT down")
    client, _, store = _client(env, boards_provider=boom)
    store.save(login="alice", password="pw")
    r = client.get("/api/boards")
    assert r.status_code == 502
    assert "error" in r.json()


def test_admin_boards_persists_exclusions_and_triggers(env):
    client, triggered, store = _client(env, boards_provider=lambda: ["A", "B"])
    store.save(login="alice", password="pw")
    r = client.post("/admin/boards", data={"excluded": ["APEIT", "Vie de l'école"]},
                    follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert store.effective().excluded_boards == ["APEIT", "Vie de l'école"]
    assert triggered.is_set()
