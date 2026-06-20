# src/beneylu_photo_sync/core/client.py
from __future__ import annotations
import httpx
import logging
import threading
from typing import Iterator
from .errors import AuthError, CaptchaLockedError, MediaResolveError
from .models import Board, Card, CardAttachment, ResolvedMedia

log = logging.getLogger("beneylu_photo_sync.client")

# The /cards endpoint caps its response to ~10 most recent cards by default and
# ignores page/offset/cursor params; only `limit` is honored. Request a high
# limit to retrieve a board's full history in one call.
CARDS_PAGE_LIMIT = 2000


class BeneyluClient:
    def __init__(self, base_url: str, login: str, password: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._login = login
        self._password = password
        self.refresh_token: str | None = None
        # Single-flight the JWT refresh: under a parallel sync many requests can
        # 401 at once; a lock + generation counter collapses them to one refresh.
        self._refresh_lock = threading.Lock()
        self._refresh_gen = 0
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

    def _refresh_once(self, seen_gen: int) -> None:
        """Refresh the JWT unless another thread already did so since the caller
        observed its 401. The generation counter makes concurrent 401s collapse
        into a single refresh instead of a stampede of redundant token calls."""
        with self._refresh_lock:
            if self._refresh_gen != seen_gen:
                return  # someone else refreshed while we waited for the lock
            self.refresh()
            self._refresh_gen += 1

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Send an authenticated request, refreshing the JWT once on 401.

        The BEARER JWT expires after ~15 min, shorter than a full-history sync.
        On a 401 with a refresh token available, we refresh and retry once.
        """
        gen = self._refresh_gen
        resp = self._http.request(method, url, **kwargs)
        if resp.status_code == 401 and self.refresh_token:
            self._refresh_once(gen)
            resp = self._http.request(method, url, **kwargs)
        return resp

    def boards(self) -> list[Board]:
        resp = self._request("GET", "/api/cardboard/boards")
        resp.raise_for_status()
        boards = [Board.model_validate(b) for b in resp.json()]
        return [b for b in boards if not b.archived and not b.is_hidden]

    def cards(self, board_id: str) -> list[Card]:
        resp = self._request("GET", f"/api/cardboard/boards/{board_id}/cards",
                             params={"limit": CARDS_PAGE_LIMIT})
        resp.raise_for_status()
        data = resp.json()
        if len(data) >= CARDS_PAGE_LIMIT:
            # We hit our own ceiling — there may be even older cards we did not
            # fetch. Surface it loudly rather than silently dropping history.
            log.warning("cards(%s): received %d cards (>= limit %d); some older "
                        "cards may be missing", board_id, len(data), CARDS_PAGE_LIMIT)
        return [Card.model_validate(c) for c in data]

    def resolve_media(self, att: CardAttachment) -> ResolvedMedia:
        params = {"mediaId": att.media_id, "entityId": att.entity_id,
                  "entityType": att.entity_type, "timestamp": att.timestamp,
                  "signature": att.signature}
        resp = self._request("GET", f"/api/media-library/media/{att.media_id}", params=params)
        if resp.status_code != 200:
            raise MediaResolveError(f"Resolve media {att.media_id} failed: HTTP {resp.status_code}")
        return ResolvedMedia.model_validate(resp.json())

    def download(self, url: str) -> Iterator[bytes]:
        gen = self._refresh_gen
        with self._http.stream("GET", url) as resp:
            if resp.status_code == 401 and self.refresh_token:
                resp.close()
                self._refresh_once(gen)
                with self._http.stream("GET", url) as retry:
                    retry.raise_for_status()
                    yield from retry.iter_bytes()
                return
            resp.raise_for_status()
            yield from resp.iter_bytes()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BeneyluClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
