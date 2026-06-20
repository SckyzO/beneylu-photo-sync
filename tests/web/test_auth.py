from beneylu_photo_sync.web import auth


class FakeRequest:
    def __init__(self, cookies):
        self.cookies = cookies


def test_no_password_means_always_authenticated(monkeypatch):
    monkeypatch.delenv("ENT_WEB_PASSWORD", raising=False)
    assert auth.password_required() is None
    assert auth.is_authenticated(FakeRequest({})) is True


def test_password_gate_and_cookie(monkeypatch):
    monkeypatch.setenv("ENT_WEB_PASSWORD", "letmein")
    assert auth.password_required() == "letmein"
    assert auth.is_authenticated(FakeRequest({})) is False
    assert auth.check_password("letmein") is True
    assert auth.check_password("nope") is False
    good = auth.session_cookie_value()
    assert auth.is_authenticated(FakeRequest({auth.COOKIE: good})) is True
    assert auth.is_authenticated(FakeRequest({auth.COOKIE: "forged"})) is False
