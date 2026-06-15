from __future__ import annotations
import hashlib
import hmac
import os

COOKIE = "ent_session"


def password_required() -> str | None:
    return os.getenv("ENT_WEB_PASSWORD") or None


def _token(password: str) -> str:
    return hmac.new(password.encode(), b"ent-exporter-session",
                    hashlib.sha256).hexdigest()


def is_authenticated(request) -> bool:
    pw = password_required()
    if not pw:
        return True
    cookie = request.cookies.get(COOKIE, "")
    return hmac.compare_digest(cookie, _token(pw))


def check_password(candidate: str) -> bool:
    pw = password_required()
    return bool(pw) and hmac.compare_digest(candidate, pw)


def session_cookie_value() -> str:
    pw = password_required() or ""
    return _token(pw)
