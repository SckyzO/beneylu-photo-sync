# tests/test_client_auth.py
import httpx
import respx
import pytest
from ent_exporter.client import BeneyluClient
from ent_exporter.errors import AuthError, CaptchaLockedError

BASE = "https://www.ent-ecole.fr"

@respx.mock
def test_login_sets_cookie_and_refresh_token(fixture):
    respx.post(f"{BASE}/api/auth/login_check").mock(
        return_value=httpx.Response(200, json=fixture("login_check.json"),
                                    headers={"set-cookie": "BEARER=jwt-token; path=/; httponly"}))
    c = BeneyluClient(base_url=BASE, login="parent.test", password="secret")
    c.login()
    assert c.refresh_token == "test-refresh-token-abc123"
    assert c._http.cookies.get("BEARER") == "jwt-token"

@respx.mock
def test_login_sends_login_field_not_username(fixture):
    route = respx.post(f"{BASE}/api/auth/login_check").mock(
        return_value=httpx.Response(200, json=fixture("login_check.json")))
    c = BeneyluClient(base_url=BASE, login="parent.test", password="secret")
    c.login()
    sent = route.calls.last.request
    import json as _json
    body = _json.loads(sent.content)
    assert body["login"] == "parent.test"
    assert "username" not in body
    assert body["remember_me"] is False

@respx.mock
def test_authenticated_call_sends_bearer_cookie(fixture):
    respx.post(f"{BASE}/api/auth/login_check").mock(
        return_value=httpx.Response(200, json=fixture("login_check.json"),
                                    headers={"set-cookie": "BEARER=jwt-token; path=/; httponly"}))
    route = respx.get(f"{BASE}/api/cardboard/boards").mock(
        return_value=httpx.Response(200, json=fixture("boards.json")))
    c = BeneyluClient(base_url=BASE, login="parent.test", password="secret")
    c.login()
    c.boards()
    assert "BEARER=jwt-token" in route.calls.last.request.headers["cookie"]

@respx.mock
def test_captcha_lock_raises():
    respx.post(f"{BASE}/api/auth/login_check").mock(
        return_value=httpx.Response(401, headers={"X-Bns-Captcha": "1"}, json={}))
    c = BeneyluClient(base_url=BASE, login="x", password="y")
    with pytest.raises(CaptchaLockedError):
        c.login()

@respx.mock
def test_bad_credentials_raise_autherror():
    respx.post(f"{BASE}/api/auth/login_check").mock(return_value=httpx.Response(400, json={}))
    c = BeneyluClient(base_url=BASE, login="x", password="y")
    with pytest.raises(AuthError):
        c.login()
