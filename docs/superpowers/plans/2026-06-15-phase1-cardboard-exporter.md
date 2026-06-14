# Phase 1 — Cardboard Photo Exporter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python tool that logs into Beneylu School (`ent-ecole.fr`), enumerates the class "cardboard" boards, and incrementally downloads new photos to a local folder, packaged as a CLI and a Docker container.

**Architecture:** A runtime-agnostic `core` package: an HTTP `BeneyluClient` (cookie auth + refresh), a pluggable `Source` interface (Cardboard in v1), a pluggable `Storage` interface (Filesystem in v1), a SQLite `StateStore` for idempotent incremental sync, a `naming` helper, and a `Synchronizer` orchestrator. A Typer CLI and a Dockerfile sit on top. No browser; pure HTTP.

**Tech Stack:** Python 3.11+, httpx, pydantic / pydantic-settings, Pillow (EXIF), Typer (CLI), SQLite (stdlib), pytest + respx (HTTP mocking). No live network in tests.

---

## File Structure

```
pyproject.toml
src/ent_exporter/
├─ __init__.py
├─ models.py            # pydantic models: Child, Board, Card, CardAttachment, ResolvedMedia, MediaItem
├─ config.py            # Settings (pydantic-settings)
├─ client.py            # BeneyluClient: login, refresh, me, boards, cards, resolve_media, download
├─ errors.py            # AuthError, CaptchaLockedError, MediaResolveError
├─ sources/
│  ├─ __init__.py
│  ├─ base.py           # Source ABC
│  └─ cardboard.py      # CardboardSource
├─ storage/
│  ├─ __init__.py
│  ├─ base.py           # Storage ABC
│  └─ filesystem.py     # FilesystemStorage
├─ state.py             # StateStore (SQLite)
├─ naming.py            # path_for()
├─ sync.py              # Synchronizer + SyncReport
└─ cli.py               # Typer app: login-test, list-boards, sync, run
tests/
├─ conftest.py          # fixtures loader
├─ fixtures/            # sanitized JSON captured from recon
│  ├─ login_check.json
│  ├─ users_me.json
│  ├─ boards.json
│  ├─ cards.json
│  └─ resolved_media.json
├─ test_models.py
├─ test_client_auth.py
├─ test_client_content.py
├─ test_cardboard_source.py
├─ test_filesystem_storage.py
├─ test_state.py
├─ test_naming.py
└─ test_sync.py
runtimes/docker/
├─ Dockerfile
└─ docker-compose.yml
```

Each `core` file has one responsibility and is tested in isolation with mocked dependencies.

---

### Task 1: Project scaffold + tooling

**Files:**
- Create: `pyproject.toml`
- Create: `src/ent_exporter/__init__.py`
- Create: `tests/__init__.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoke.py
def test_package_imports():
    import ent_exporter
    assert ent_exporter.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "ent-exporter"
version = "0.1.0"
description = "Export school photos from Beneylu School (ent-ecole.fr)"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "Pillow>=10.3",
    "typer>=0.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "respx>=0.21", "ruff>=0.5"]

[project.scripts]
ent-exporter = "ent_exporter.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ent_exporter"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
# src/ent_exporter/__init__.py
__version__ = "0.1.0"
```

```python
# tests/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]" && pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ent_exporter/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: project scaffold + tooling"
```

---

### Task 2: Sanitized recon fixtures + loader

**Files:**
- Create: `tests/fixtures/login_check.json`
- Create: `tests/fixtures/users_me.json`
- Create: `tests/fixtures/boards.json`
- Create: `tests/fixtures/cards.json`
- Create: `tests/fixtures/resolved_media.json`
- Create: `tests/conftest.py`
- Test: `tests/test_fixtures.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fixtures.py
def test_fixtures_load(fixture):
    cards = fixture("cards.json")
    assert cards[0]["type"] == "image"
    assert cards[0]["cardAttachments"][0]["mediaId"] == 900000001
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fixtures.py -v`
Expected: FAIL — `fixture 'fixture' not found`

- [ ] **Step 3: Write minimal implementation**

```json
// tests/fixtures/login_check.json
{"auth_url": "https://login.school.beneylu.com/oauth/v2/connect/", "refresh_token": "test-refresh-token-abc123"}
```

```json
// tests/fixtures/users_me.json
{"id": 100, "username": "parent.test", "firstName": "Test", "lastName": "Parent",
 "highRole": "PARENT", "displayName": "M. Test Parent",
 "children": [{"id": 200, "username": "child.test", "firstName": "Léo", "lastName": "Parent", "displayName": "Léo Parent"}]}
```

```json
// tests/fixtures/boards.json
[{"id": "board-uuid-1", "authorId": 300, "name": "DANS LA CLASSE DES PS", "archived": false, "isHidden": false},
 {"id": "board-uuid-2", "authorId": 300, "name": "APEIT", "archived": false, "isHidden": false}]
```

```json
// tests/fixtures/cards.json
[{"type": "image", "id": "card-uuid-1", "creatorId": 300, "content": null, "description": "Sortie",
  "createdAt": "2026-06-12T18:24:16+02:00", "updatedAt": "2026-06-12T18:24:16+02:00", "position": 1,
  "cardAttachments": [{"mediaId": 900000001, "resourceId": null, "entityId": "card-uuid-1",
                       "entityType": "Card", "timestamp": 1781479136, "signature": "sigA"}]},
 {"type": "text", "id": "card-uuid-2", "creatorId": 300, "content": "Bonjour", "description": null,
  "createdAt": "2026-06-11T10:00:00+02:00", "updatedAt": "2026-06-11T10:00:00+02:00", "position": 2,
  "cardAttachments": []}]
```

```json
// tests/fixtures/resolved_media.json
{"id": 900000001, "label": "IMG_7363.jpg", "type_unique_name": "IMAGE", "optimized": true,
 "mime_type": "image/jpeg", "downloadable": true, "readable": true,
 "url": "https://s3.example.test/2026_06_12/300/900000001/img-7363.jpg?X-Amz-Signature=deadbeef",
 "display_url": "https://s3.example.test/2026_06_12/300/900000001/display.jpg?X-Amz-Signature=cafe"}
```

```python
# tests/conftest.py
import json
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def fixture():
    def _load(name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return _load
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fixtures.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures tests/conftest.py tests/test_fixtures.py
git commit -m "test: sanitized recon fixtures + loader"
```

---

### Task 3: Domain models

**Files:**
- Create: `src/ent_exporter/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from ent_exporter.models import Card, ResolvedMedia, Board

def test_card_parses_attachments(fixture):
    cards = [Card.model_validate(c) for c in fixture("cards.json")]
    img, txt = cards
    assert img.type == "image"
    assert img.attachments[0].media_id == 900000001
    assert img.attachments[0].entity_type == "Card"
    assert txt.attachments == []

def test_board_parses(fixture):
    boards = [Board.model_validate(b) for b in fixture("boards.json")]
    assert boards[0].name == "DANS LA CLASSE DES PS"

def test_resolved_media_parses(fixture):
    m = ResolvedMedia.model_validate(fixture("resolved_media.json"))
    assert m.label == "IMG_7363.jpg"
    assert m.downloadable is True
    assert m.url.startswith("https://")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/models.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field

class Child(BaseModel):
    id: int
    username: str
    display_name: str = Field(alias="displayName")
    model_config = {"populate_by_name": True}

class Board(BaseModel):
    id: str
    name: str
    archived: bool = False
    is_hidden: bool = Field(default=False, alias="isHidden")
    model_config = {"populate_by_name": True}

class CardAttachment(BaseModel):
    media_id: int = Field(alias="mediaId")
    entity_id: str = Field(alias="entityId")
    entity_type: str = Field(alias="entityType")
    timestamp: int
    signature: str
    model_config = {"populate_by_name": True}

class Card(BaseModel):
    id: str
    type: str
    description: str | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    attachments: list[CardAttachment] = Field(default_factory=list, alias="cardAttachments")
    model_config = {"populate_by_name": True}

class ResolvedMedia(BaseModel):
    id: int
    label: str
    mime_type: str = Field(alias="mime_type")
    downloadable: bool
    url: str
    display_url: str | None = None
    model_config = {"populate_by_name": True}

class MediaItem(BaseModel):
    """One downloadable photo produced by a Source, before resolution."""
    media_id: int
    attachment: CardAttachment
    board: Board
    card: Card
    child: Child | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/models.py tests/test_models.py
git commit -m "feat: domain models for Beneylu entities"
```

---

### Task 4: Settings / config

**Files:**
- Create: `src/ent_exporter/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from ent_exporter.config import Settings

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("ENT_LOGIN", "parent.test")
    monkeypatch.setenv("ENT_PASSWORD", "secret")
    monkeypatch.setenv("ENT_DATA_DIR", "/tmp/ent-data")
    s = Settings()
    assert s.login == "parent.test"
    assert s.password.get_secret_value() == "secret"
    assert str(s.data_dir) == "/tmp/ent-data"
    assert s.base_url == "https://www.ent-ecole.fr"

def test_password_not_in_repr(monkeypatch):
    monkeypatch.setenv("ENT_LOGIN", "x")
    monkeypatch.setenv("ENT_PASSWORD", "topsecret")
    s = Settings()
    assert "topsecret" not in repr(s)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/config.py
from pathlib import Path
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENT_", env_file=".env", extra="ignore")

    login: str
    password: SecretStr
    base_url: str = "https://www.ent-ecole.fr"
    data_dir: Path = Field(default=Path("./data"))
    state_db: Path = Field(default=Path("./state.db"))
    request_timeout: float = 30.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/config.py tests/test_config.py
git commit -m "feat: settings via pydantic-settings (secrets masked)"
```

---

### Task 5: Errors module

**Files:**
- Create: `src/ent_exporter/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_errors.py
from ent_exporter.errors import EntExporterError, AuthError, CaptchaLockedError, MediaResolveError

def test_error_hierarchy():
    assert issubclass(AuthError, EntExporterError)
    assert issubclass(CaptchaLockedError, AuthError)
    assert issubclass(MediaResolveError, EntExporterError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.errors'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/errors.py
class EntExporterError(Exception):
    """Base error."""

class AuthError(EntExporterError):
    """Login or token refresh failed."""

class CaptchaLockedError(AuthError):
    """Account temporarily locked (X-Bns-Captcha)."""

class MediaResolveError(EntExporterError):
    """Could not resolve a media's signed download URL."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/errors.py tests/test_errors.py
git commit -m "feat: typed error hierarchy"
```

---

### Task 6: BeneyluClient — authentication

**Files:**
- Create: `src/ent_exporter/client.py`
- Test: `tests/test_client_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client_auth.py
import httpx, respx, pytest
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_client_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.client'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_client_auth.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/client.py tests/test_client_auth.py
git commit -m "feat: BeneyluClient login + refresh + captcha detection"
```

---

### Task 7: BeneyluClient — content + media resolution + download

**Files:**
- Modify: `src/ent_exporter/client.py`
- Test: `tests/test_client_content.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client_content.py
import httpx, respx
from ent_exporter.client import BeneyluClient
from ent_exporter.models import CardAttachment

BASE = "https://www.ent-ecole.fr"

def _client():
    return BeneyluClient(base_url=BASE, login="x", password="y")

@respx.mock
def test_get_me_and_children(fixture):
    respx.get(f"{BASE}/api/auth/users/me").mock(return_value=httpx.Response(200, json=fixture("users_me.json")))
    me = _client().get_me()
    assert me.children[0].display_name == "Léo Parent"

@respx.mock
def test_boards_filters_archived_hidden(fixture):
    data = fixture("boards.json") + [{"id": "b3", "name": "old", "archived": True, "isHidden": False}]
    respx.get(f"{BASE}/api/cardboard/boards").mock(return_value=httpx.Response(200, json=data))
    boards = _client().boards()
    assert [b.name for b in boards] == ["DANS LA CLASSE DES PS", "APEIT"]

@respx.mock
def test_cards(fixture):
    respx.get(f"{BASE}/api/cardboard/boards/board-uuid-1/cards").mock(
        return_value=httpx.Response(200, json=fixture("cards.json")))
    cards = _client().cards("board-uuid-1")
    assert cards[0].attachments[0].media_id == 900000001

@respx.mock
def test_resolve_media_builds_signed_query(fixture):
    att = CardAttachment(mediaId=900000001, entityId="card-uuid-1", entityType="Card",
                         timestamp=1781479136, signature="sigA")
    route = respx.get(f"{BASE}/api/media-library/media/900000001").mock(
        return_value=httpx.Response(200, json=fixture("resolved_media.json")))
    media = _client().resolve_media(att)
    assert media.label == "IMG_7363.jpg"
    q = dict(route.calls.last.request.url.params)
    assert q == {"mediaId": "900000001", "entityId": "card-uuid-1",
                 "entityType": "Card", "timestamp": "1781479136", "signature": "sigA"}

@respx.mock
def test_download_streams_bytes():
    respx.get("https://s3.example.test/x.jpg").mock(
        return_value=httpx.Response(200, content=b"\xff\xd8\xffDATA"))
    chunks = b"".join(_client().download("https://s3.example.test/x.jpg"))
    assert chunks == b"\xff\xd8\xffDATA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_client_content.py -v`
Expected: FAIL — `AttributeError: 'BeneyluClient' object has no attribute 'get_me'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/ent_exporter/client.py` (add imports at top, methods on the class):

```python
# add to imports at top of client.py:
from typing import Iterator
from .models import Board, Card, CardAttachment, Child, ResolvedMedia
from .errors import MediaResolveError
from pydantic import BaseModel

# add this model near the bottom of client.py (module level):
class Me(BaseModel):
    children: list[Child] = []

# add these methods inside class BeneyluClient:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_client_content.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/client.py tests/test_client_content.py
git commit -m "feat: client content methods + signed media resolution + streaming download"
```

---

### Task 8: Source interface + CardboardSource

**Files:**
- Create: `src/ent_exporter/sources/__init__.py`
- Create: `src/ent_exporter/sources/base.py`
- Create: `src/ent_exporter/sources/cardboard.py`
- Test: `tests/test_cardboard_source.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cardboard_source.py
import httpx, respx
from ent_exporter.client import BeneyluClient
from ent_exporter.sources.cardboard import CardboardSource

BASE = "https://www.ent-ecole.fr"

@respx.mock
def test_cardboard_yields_only_image_attachments(fixture):
    respx.get(f"{BASE}/api/cardboard/boards").mock(return_value=httpx.Response(200, json=fixture("boards.json")[:1]))
    respx.get(f"{BASE}/api/cardboard/boards/board-uuid-1/cards").mock(
        return_value=httpx.Response(200, json=fixture("cards.json")))
    client = BeneyluClient(base_url=BASE, login="x", password="y")
    items = list(CardboardSource().iter_items(client))
    assert len(items) == 1  # text card has no attachments
    assert items[0].media_id == 900000001
    assert items[0].board.name == "DANS LA CLASSE DES PS"
    assert items[0].card.id == "card-uuid-1"

def test_source_has_name():
    assert CardboardSource().name == "cardboard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cardboard_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.sources'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/sources/__init__.py
```

```python
# src/ent_exporter/sources/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable
from ..client import BeneyluClient
from ..models import MediaItem

class Source(ABC):
    name: str

    @abstractmethod
    def iter_items(self, client: BeneyluClient) -> Iterable[MediaItem]:
        """Yield every downloadable MediaItem this source exposes."""
```

```python
# src/ent_exporter/sources/cardboard.py
from __future__ import annotations
from typing import Iterable
from .base import Source
from ..client import BeneyluClient
from ..models import MediaItem

class CardboardSource(Source):
    name = "cardboard"

    def iter_items(self, client: BeneyluClient) -> Iterable[MediaItem]:
        for board in client.boards():
            for card in client.cards(board.id):
                for att in card.attachments:
                    yield MediaItem(media_id=att.media_id, attachment=att, board=board, card=card)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cardboard_source.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/sources tests/test_cardboard_source.py
git commit -m "feat: Source interface + CardboardSource enumeration"
```

---

### Task 9: Storage interface + FilesystemStorage

**Files:**
- Create: `src/ent_exporter/storage/__init__.py`
- Create: `src/ent_exporter/storage/base.py`
- Create: `src/ent_exporter/storage/filesystem.py`
- Test: `tests/test_filesystem_storage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_filesystem_storage.py
from ent_exporter.storage.filesystem import FilesystemStorage

def test_write_then_exists(tmp_path):
    s = FilesystemStorage(tmp_path)
    assert s.exists("board/2026-06/a.jpg") is False
    s.write("board/2026-06/a.jpg", iter([b"\xff\xd8", b"DATA"]))
    assert s.exists("board/2026-06/a.jpg") is True
    assert (tmp_path / "board" / "2026-06" / "a.jpg").read_bytes() == b"\xff\xd8DATA"

def test_write_is_atomic_no_partial_on_error(tmp_path):
    s = FilesystemStorage(tmp_path)
    def boom():
        yield b"partial"
        raise RuntimeError("network died")
    import pytest
    with pytest.raises(RuntimeError):
        s.write("board/x.jpg", boom())
    assert s.exists("board/x.jpg") is False
    assert list(tmp_path.rglob("*.part")) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_filesystem_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.storage'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/storage/__init__.py
```

```python
# src/ent_exporter/storage/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable

class Storage(ABC):
    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def write(self, key: str, stream: Iterable[bytes]) -> None:
        """Persist stream under key. Must be atomic: no partial artifact on failure."""
```

```python
# src/ent_exporter/storage/filesystem.py
from __future__ import annotations
from pathlib import Path
from typing import Iterable
from .base import Storage

class FilesystemStorage(Storage):
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def write(self, key: str, stream: Iterable[bytes]) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with tmp.open("wb") as f:
                for chunk in stream:
                    f.write(chunk)
            tmp.replace(dest)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_filesystem_storage.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/storage tests/test_filesystem_storage.py
git commit -m "feat: Storage interface + atomic FilesystemStorage"
```

---

### Task 10: StateStore (SQLite, incremental)

**Files:**
- Create: `src/ent_exporter/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
from ent_exporter.state import StateStore

def test_record_then_has(tmp_path):
    st = StateStore(tmp_path / "state.db")
    assert st.has(900000001) is False
    st.record(media_id=900000001, board_id="b1", card_id="c1", path="b1/a.jpg", card_updated_at="2026-06-12T18:24:16+02:00")
    assert st.has(900000001) is True
    st.close()

def test_persists_across_instances(tmp_path):
    db = tmp_path / "state.db"
    StateStore(db).record(900000001, "b1", "c1", "b1/a.jpg", "2026-06-12T18:24:16+02:00")
    assert StateStore(db).has(900000001) is True

def test_record_is_idempotent(tmp_path):
    st = StateStore(tmp_path / "state.db")
    st.record(900000001, "b1", "c1", "b1/a.jpg", "t")
    st.record(900000001, "b1", "c1", "b1/a.jpg", "t")  # no exception
    assert st.count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.state'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/state.py
from __future__ import annotations
import sqlite3
from pathlib import Path

class StateStore:
    def __init__(self, db_path: Path | str):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS media (
                 media_id INTEGER PRIMARY KEY,
                 board_id TEXT, card_id TEXT, path TEXT,
                 card_updated_at TEXT,
                 downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP)"""
        )
        self._conn.commit()

    def has(self, media_id: int) -> bool:
        cur = self._conn.execute("SELECT 1 FROM media WHERE media_id = ?", (media_id,))
        return cur.fetchone() is not None

    def record(self, media_id: int, board_id: str, card_id: str, path: str, card_updated_at: str) -> None:
        self._conn.execute(
            """INSERT INTO media (media_id, board_id, card_id, path, card_updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(media_id) DO UPDATE SET path=excluded.path,
                   card_updated_at=excluded.card_updated_at""",
            (media_id, board_id, card_id, path, card_updated_at))
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/state.py tests/test_state.py
git commit -m "feat: SQLite StateStore for incremental sync"
```

---

### Task 11: Naming (path from label + EXIF date)

**Files:**
- Create: `src/ent_exporter/naming.py`
- Test: `tests/test_naming.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_naming.py
from datetime import datetime
from ent_exporter.naming import path_for, sanitize, month_folder

def test_sanitize_removes_unsafe_chars():
    assert sanitize("DANS LA CLASSE DES PS") == "DANS LA CLASSE DES PS"
    assert sanitize("a/b:c*?.jpg") == "a_b_c__.jpg"

def test_month_folder_from_datetime():
    assert month_folder(datetime(2026, 6, 12)) == "2026-06"

def test_path_for_uses_board_month_label():
    p = path_for(board_name="DANS LA CLASSE DES PS", label="IMG_7363.jpg",
                 taken_at=datetime(2026, 6, 12), media_id=900000001)
    assert p == "DANS LA CLASSE DES PS/2026-06/IMG_7363.jpg"

def test_path_for_disambiguates_on_collision():
    p = path_for(board_name="B", label="IMG.jpg", taken_at=datetime(2026, 6, 1),
                 media_id=42, exists=lambda key: key == "B/2026-06/IMG.jpg")
    assert p == "B/2026-06/IMG_42.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_naming.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.naming'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/naming.py
from __future__ import annotations
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Callable

_UNSAFE = re.compile(r'[/\\:*?"<>|]')

def sanitize(name: str) -> str:
    return _UNSAFE.sub("_", name).strip()

def month_folder(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"

def path_for(board_name: str, label: str, taken_at: datetime, media_id: int,
             exists: Callable[[str], bool] | None = None) -> str:
    folder = f"{sanitize(board_name)}/{month_folder(taken_at)}"
    label = sanitize(label)
    key = f"{folder}/{label}"
    if exists and exists(key):
        stem = PurePosixPath(label).stem
        suffix = PurePosixPath(label).suffix
        key = f"{folder}/{stem}_{media_id}{suffix}"
    return key
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_naming.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/naming.py tests/test_naming.py
git commit -m "feat: filename/path strategy with collision handling"
```

---

### Task 12: Synchronizer orchestration

**Files:**
- Create: `src/ent_exporter/sync.py`
- Test: `tests/test_sync.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync.py
from datetime import datetime
from ent_exporter.sync import Synchronizer, SyncReport
from ent_exporter.models import Board, Card, CardAttachment, MediaItem, ResolvedMedia

def _item(media_id=1):
    att = CardAttachment(mediaId=media_id, entityId="c1", entityType="Card", timestamp=1, signature="s")
    board = Board(id="b1", name="B")
    card = Card(id="c1", type="image", createdAt="2026-06-12T18:24:16+02:00",
                updatedAt="2026-06-12T18:24:16+02:00", cardAttachments=[att])
    return MediaItem(media_id=media_id, attachment=att, board=board, card=card)

class FakeSource:
    name = "fake"
    def __init__(self, items): self._items = items
    def iter_items(self, client): return iter(self._items)

class FakeClient:
    def __init__(self): self.downloaded = []
    def resolve_media(self, att):
        return ResolvedMedia(id=att.media_id, label=f"IMG_{att.media_id}.jpg",
                             mime_type="image/jpeg", downloadable=True,
                             url=f"https://s3/{att.media_id}.jpg")
    def download(self, url):
        self.downloaded.append(url); yield b"DATA"

class FakeStorage:
    def __init__(self): self.written = {}
    def exists(self, key): return key in self.written
    def write(self, key, stream): self.written[key] = b"".join(stream)

class FakeState:
    def __init__(self, known=()): self._known = set(known)
    def has(self, mid): return mid in self._known
    def record(self, **kw): self._known.add(kw["media_id"])

def test_sync_downloads_new_item():
    client, storage, state = FakeClient(), FakeStorage(), FakeState()
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 1
    assert "B/2026-06/IMG_1.jpg" in storage.written

def test_sync_skips_known_item():
    client, storage, state = FakeClient(), FakeStorage(), FakeState(known={1})
    report = Synchronizer(client, [FakeSource([_item(1)])], storage, state).run()
    assert report.downloaded == 0
    assert report.skipped == 1
    assert client.downloaded == []

def test_per_item_error_does_not_abort_run():
    class ExplodingClient(FakeClient):
        def resolve_media(self, att):
            if att.media_id == 1:
                raise RuntimeError("boom")
            return super().resolve_media(att)
    client, storage, state = ExplodingClient(), FakeStorage(), FakeState()
    report = Synchronizer(client, [FakeSource([_item(1), _item(2)])], storage, state).run()
    assert report.downloaded == 1
    assert report.errors == 1
    assert "B/2026-06/IMG_2.jpg" in storage.written
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.sync'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/sync.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from . import naming

log = logging.getLogger("ent_exporter.sync")

@dataclass
class SyncReport:
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    error_items: list[int] = field(default_factory=list)

class Synchronizer:
    def __init__(self, client, sources, storage, state):
        self.client = client
        self.sources = sources
        self.storage = storage
        self.state = state

    def run(self) -> SyncReport:
        report = SyncReport()
        for source in self.sources:
            for item in source.iter_items(self.client):
                try:
                    self._handle(item, report)
                except Exception:  # per-item isolation; run continues
                    log.exception("Failed to sync media %s", item.media_id)
                    report.errors += 1
                    report.error_items.append(item.media_id)
        return report

    def _handle(self, item, report: SyncReport) -> None:
        if self.state.has(item.media_id):
            report.skipped += 1
            return
        media = self.client.resolve_media(item.attachment)
        taken_at = item.card.created_at
        key = naming.path_for(item.board.name, media.label, taken_at, item.media_id,
                              exists=self.storage.exists)
        if not self.storage.exists(key):
            self.storage.write(key, self.client.download(media.url))
        self.state.record(media_id=item.media_id, board_id=item.board.id,
                          card_id=item.card.id, path=key,
                          card_updated_at=item.card.updated_at.isoformat())
        report.downloaded += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sync.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/sync.py tests/test_sync.py
git commit -m "feat: Synchronizer with incremental skip + per-item error isolation"
```

---

### Task 13: CLI (Typer)

**Files:**
- Create: `src/ent_exporter/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ent_exporter.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ent_exporter/cli.py
from __future__ import annotations
import logging
import typer
from .config import Settings
from .client import BeneyluClient
from .sources.cardboard import CardboardSource
from .storage.filesystem import FilesystemStorage
from .state import StateStore
from .sync import Synchronizer

app = typer.Typer(add_completion=False, help="Export school photos from Beneylu School.")

def _client(settings: Settings) -> BeneyluClient:
    c = BeneyluClient(base_url=settings.base_url, login=settings.login,
                      password=settings.password.get_secret_value(),
                      timeout=settings.request_timeout)
    c.login()
    return c

@app.command("login-test")
def login_test():
    """Verify the ENT credentials work."""
    settings = Settings()
    with _client(settings):
        typer.echo("Login OK")

@app.command("list-boards")
def list_boards():
    """List the class boards on the account."""
    settings = Settings()
    with _client(settings) as c:
        for b in c.boards():
            typer.echo(f"{b.id}  {b.name}")

@app.command("sync")
def sync():
    """Download new photos incrementally."""
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    storage = FilesystemStorage(settings.data_dir)
    state = StateStore(settings.state_db)
    with _client(settings) as c:
        report = Synchronizer(c, [CardboardSource()], storage, state).run()
    typer.echo(f"Sync done: downloaded={report.downloaded} skipped={report.skipped} errors={report.errors}")
    state.close()

if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/cli.py tests/test_cli.py
git commit -m "feat: Typer CLI (login-test, list-boards, sync)"
```

---

### Task 14: Full test run + lint gate

**Files:**
- Modify: none (verification task)

- [ ] **Step 1: Run the whole suite**

Run: `pytest -v`
Expected: ALL PASS (no live network)

- [ ] **Step 2: Lint**

Run: `ruff check src tests`
Expected: no errors (fix any inline)

- [ ] **Step 3: Commit any lint fixes**

```bash
git add -A && git commit -m "chore: lint pass" || echo "nothing to commit"
```

---

### Task 15: Docker packaging

**Files:**
- Create: `runtimes/docker/Dockerfile`
- Create: `runtimes/docker/docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Write the Dockerfile**

```dockerfile
# runtimes/docker/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV ENT_DATA_DIR=/data ENT_STATE_DB=/data/state.db
VOLUME ["/data"]
ENTRYPOINT ["ent-exporter"]
CMD ["sync"]
```

```yaml
# runtimes/docker/docker-compose.yml
services:
  ent-exporter:
    build:
      context: ../..
      dockerfile: runtimes/docker/Dockerfile
    environment:
      ENT_LOGIN: ${ENT_LOGIN}
      ENT_PASSWORD: ${ENT_PASSWORD}
    volumes:
      - ./data:/data
    restart: "no"
```

```
# .dockerignore
.venv
data
state.db*
tests
.git
__pycache__
```

- [ ] **Step 2: Build the image**

Run: `docker build -f runtimes/docker/Dockerfile -t ent-exporter:dev .`
Expected: image builds successfully

- [ ] **Step 3: Smoke-test the entrypoint (no creds → clear error)**

Run: `docker run --rm ent-exporter:dev login-test`
Expected: exits non-zero with a validation error about missing `ENT_LOGIN` (proves wiring; no creds in CI)

- [ ] **Step 4: Commit**

```bash
git add runtimes/docker .dockerignore
git commit -m "build: Docker packaging for the sync CLI"
```

---

### Task 16: Wire real run into README + finalize

**Files:**
- Modify: `README.md` (fill Installation / Configuration / Utilisation with the now-real commands)

- [ ] **Step 1: Replace the "à compléter" placeholders** in `README.md` with the verified commands:

```markdown
## Installation (Docker)

\`\`\`bash
git clone <repo> && cd ent_exporter
cp .env.example .env   # puis renseigne ENT_LOGIN / ENT_PASSWORD
docker compose -f runtimes/docker/docker-compose.yml run --rm ent-exporter sync
\`\`\`

## Configuration

| Variable | Rôle | Défaut |
|---|---|---|
| `ENT_LOGIN` | identifiant ENT | — |
| `ENT_PASSWORD` | mot de passe ENT | — |
| `ENT_DATA_DIR` | dossier des photos | `./data` |

## Utilisation

\`\`\`bash
ent-exporter login-test   # vérifie la connexion
ent-exporter list-boards  # liste les tableaux
ent-exporter sync         # télécharge les nouvelles photos
\`\`\`
```

- [ ] **Step 2: Create `.env.example`**

```bash
# .env.example
ENT_LOGIN=
ENT_PASSWORD=
ENT_DATA_DIR=./data
```

- [ ] **Step 3: Commit**

```bash
git add README.md .env.example
git commit -m "docs: real install/config/usage commands + .env.example"
```

---

## Notes for Phase 2 (separate plan, do NOT build here)

Web UI (FastAPI gallery + config + trigger), scheduler loop, GitHub Actions runtime,
Google Drive `Storage` backend, additional `Source`s (family-information, chat, newspaper),
`card.updatedAt` cursor optimisation, UI screenshots in `docs/screenshots/`.
