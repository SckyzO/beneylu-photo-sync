# tests/test_cli.py
import httpx, respx
from typer.testing import CliRunner
from ent_exporter.cli import app

BASE = "https://www.ent-ecole.fr"
runner = CliRunner()
ENV = {"ENT_LOGIN": "parent.test", "ENT_PASSWORD": "secret", "ENT_BASE_URL": BASE}

@respx.mock
def test_login_test_ok(fixture):
    respx.post(f"{BASE}/api/auth/login_check").mock(return_value=httpx.Response(200, json=fixture("login_check.json")))
    result = runner.invoke(app, ["login-test"], env=ENV)
    assert result.exit_code == 0
    assert "OK" in result.stdout

@respx.mock
def test_list_boards(fixture):
    respx.post(f"{BASE}/api/auth/login_check").mock(return_value=httpx.Response(200, json=fixture("login_check.json")))
    respx.get(f"{BASE}/api/cardboard/boards").mock(return_value=httpx.Response(200, json=fixture("boards.json")))
    result = runner.invoke(app, ["list-boards"], env=ENV)
    assert result.exit_code == 0
    assert "DANS LA CLASSE DES PS" in result.stdout

@respx.mock
def test_sync_reports_counts(fixture, tmp_path):
    respx.post(f"{BASE}/api/auth/login_check").mock(return_value=httpx.Response(200, json=fixture("login_check.json")))
    respx.get(f"{BASE}/api/cardboard/boards").mock(return_value=httpx.Response(200, json=fixture("boards.json")[:1]))
    respx.get(f"{BASE}/api/cardboard/boards/board-uuid-1/cards").mock(return_value=httpx.Response(200, json=fixture("cards.json")))
    respx.get(f"{BASE}/api/media-library/media/900000001").mock(return_value=httpx.Response(200, json=fixture("resolved_media.json")))
    respx.get("https://s3.example.test/2026_06_12/300/900000001/img-7363.jpg").mock(return_value=httpx.Response(200, content=b"\xff\xd8\xffJPEG"))
    env = {**ENV, "ENT_DATA_DIR": str(tmp_path / "data"), "ENT_STATE_DB": str(tmp_path / "state.db")}
    result = runner.invoke(app, ["sync"], env=env)
    assert result.exit_code == 0
    assert "downloaded=1" in result.stdout
    assert (tmp_path / "data" / "DANS LA CLASSE DES PS" / "2026-06" / "IMG_7363.jpg").read_bytes() == b"\xff\xd8\xffJPEG"
