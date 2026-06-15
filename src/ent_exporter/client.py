# src/ent_exporter/client.py
from __future__ import annotations
import httpx
from .errors import AuthError, CaptchaLockedError

class BeneyluClient:
    def __init__(self, base_url: str, login: str, password: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._login = login
        self._password = password
        self.refresh_token: str | None = None
        self._http = httpx.Client(
            base_url=self.base_url, timeout=timeout,
            headers={"Accept": "application/json", "Referer": f"{self.base_url}/"},
        )

    def login(self) -> None:
        body = {"login": self._login, "password": self._password,
                "first_name": "", "last_name": "", "otp": "", "remember_me": False, "captcha": ""}
        resp = self._http.post("/api/auth/login_check", json=body)
        if resp.headers.get("X-Bns-Captcha"):
            raise CaptchaLockedError("Account temporarily locked after failed logins (captcha required).")
        if resp.status_code != 200:
            raise AuthError(f"Login failed: HTTP {resp.status_code}")
        self.refresh_token = resp.json().get("refresh_token")

    def refresh(self) -> None:
        if not self.refresh_token:
            raise AuthError("No refresh token; call login() first.")
        resp = self._http.post("/api/auth/token/refresh", json={"refresh_token": self.refresh_token})
        if resp.status_code != 200:
            raise AuthError(f"Token refresh failed: HTTP {resp.status_code}")
        new = resp.json().get("refresh_token")
        if new:
            self.refresh_token = new

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BeneyluClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
