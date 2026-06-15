# src/ent_exporter/client.py
from __future__ import annotations
import httpx
from typing import Iterator
from pydantic import BaseModel
from .errors import AuthError, CaptchaLockedError, MediaResolveError
from .models import Board, Card, CardAttachment, Child, ResolvedMedia


class Me(BaseModel):
    children: list[Child] = []

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

    def get_me(self) -> Me:
        resp = self._http.get("/api/auth/users/me")
        resp.raise_for_status()
        return Me.model_validate(resp.json())

    def boards(self) -> list[Board]:
        resp = self._http.get("/api/cardboard/boards")
        resp.raise_for_status()
        boards = [Board.model_validate(b) for b in resp.json()]
        return [b for b in boards if not b.archived and not b.is_hidden]

    def cards(self, board_id: str) -> list[Card]:
        resp = self._http.get(f"/api/cardboard/boards/{board_id}/cards")
        resp.raise_for_status()
        return [Card.model_validate(c) for c in resp.json()]

    def resolve_media(self, att: CardAttachment) -> ResolvedMedia:
        params = {"mediaId": att.media_id, "entityId": att.entity_id,
                  "entityType": att.entity_type, "timestamp": att.timestamp,
                  "signature": att.signature}
        resp = self._http.get(f"/api/media-library/media/{att.media_id}", params=params)
        if resp.status_code != 200:
            raise MediaResolveError(f"Resolve media {att.media_id} failed: HTTP {resp.status_code}")
        return ResolvedMedia.model_validate(resp.json())

    def download(self, url: str) -> Iterator[bytes]:
        with self._http.stream("GET", url) as resp:
            resp.raise_for_status()
            yield from resp.iter_bytes()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BeneyluClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
