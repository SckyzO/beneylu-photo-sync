# Web UI Gallery (Phase 2.A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-hosted web UI (FastAPI, server-rendered) on top of the Phase 1 `core` — a navigable photo gallery, a "sync now" button with live status, a config page, and an internal interval scheduler — delivered in the Docker runtime, without modifying `core`.

**Architecture:** New `src/ent_exporter/web/` package consuming the public `core` interfaces (`BeneyluClient`, `CardboardSource`, `FilesystemStorage`, `StateStore`, `Synchronizer`). Server-rendered Jinja2 + vanilla JS (status polling). Background-thread sync runner (single concurrent run) + a tiny interval-thread scheduler (no APScheduler). Web deps isolated under a `web` extra so the CLI stays lean.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, python-multipart, uvicorn (runtime), Pillow (thumbnails), pytest + Starlette `TestClient` (no live network).

**Spec:** `docs/superpowers/specs/2026-06-15-web-ui-gallery-design.md`

---

## File Structure

- `src/ent_exporter/web/__init__.py` — package marker
- `src/ent_exporter/web/settings_store.py` — persisted config (`chmod 600`) + env-priority merge → `WebConfig`
- `src/ent_exporter/web/jobs.py` — `SyncRunner` (background thread, single run, status)
- `src/ent_exporter/web/scheduler.py` — `IntervalScheduler` (interval thread; 0 = disabled)
- `src/ent_exporter/web/gallery.py` — `scan()` filesystem → board/month groups; `safe_resolve()` (no traversal)
- `src/ent_exporter/web/thumbnails.py` — Pillow thumbnail + disk cache
- `src/ent_exporter/web/auth.py` — optional password session
- `src/ent_exporter/web/app.py` — `create_app()` factory: routes, templates, static
- `src/ent_exporter/web/__main__.py` — uvicorn entrypoint + bind warning
- `src/ent_exporter/web/templates/` — `base.html`, `gallery.html`, `config.html`, `login.html`
- `src/ent_exporter/web/static/` — `style.css`, `app.js`
- `tests/web/` — one test module per component
- `runtimes/docker/Dockerfile.web`, `runtimes/docker/docker-compose.yml` (add `web` service)
- `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml` — `web` extra wired into test install

---

### Task 1: `web` extra + package scaffold

**Files:**
- Modify: `pyproject.toml`
- Modify: `Makefile:8-15` (install command in `check`/`lint`/`test`)
- Modify: `.github/workflows/ci.yml:14-15`
- Create: `src/ent_exporter/web/__init__.py`
- Create: `tests/web/__init__.py`
- Test: `tests/web/test_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_scaffold.py
def test_web_package_and_deps_importable():
    import ent_exporter.web  # noqa: F401
    import fastapi  # noqa: F401
    import jinja2  # noqa: F401
    from fastapi.testclient import TestClient  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker run --rm -v "$PWD":/app -w /app python:3.12-slim sh -c "pip install -e '.[dev]' -q && pytest tests/web/test_scaffold.py -q"`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web` (and/or `fastapi`).

- [ ] **Step 3: Create the package and add the `web` extra**

Create `src/ent_exporter/web/__init__.py` (empty) and `tests/web/__init__.py` (empty).

In `pyproject.toml`, under `[project.optional-dependencies]`, add the `web` extra:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.2", "respx>=0.21", "ruff>=0.5"]
web = ["fastapi>=0.115", "jinja2>=3.1", "python-multipart>=0.0.9", "uvicorn[standard]>=0.30"]
```

In `[tool.hatch.build.targets.wheel]`, ensure templates/static ship with the wheel by adding:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/ent_exporter"]
artifacts = ["src/ent_exporter/web/templates/*", "src/ent_exporter/web/static/*"]
```

- [ ] **Step 4: Wire the `web` extra into the containerized test install**

In `Makefile`, change every `'.[dev]'` to `'.[dev,web]'` (the `check`, `lint`, `test` recipes).

In `.github/workflows/ci.yml`, change the install step:

```yaml
      - name: Install (with dev + web extras)
        run: pip install --no-cache-dir -e ".[dev,web]"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `docker run --rm -v "$PWD":/app -w /app python:3.12-slim sh -c "pip install -e '.[dev,web]' -q && pytest tests/web/test_scaffold.py -q"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml Makefile .github/workflows/ci.yml src/ent_exporter/web/__init__.py tests/web/
git commit -m "feat(web): scaffold web package + web optional-deps extra"
```

---

### Task 2: `settings_store` — persisted config + env priority

**Files:**
- Create: `src/ent_exporter/web/settings_store.py`
- Test: `tests/web/test_settings_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_settings_store.py
import json
import stat
from pathlib import Path
from ent_exporter.web.settings_store import SettingsStore


def test_save_writes_0600_and_roundtrips(tmp_path, monkeypatch):
    monkeypatch.delenv("ENT_LOGIN", raising=False)
    monkeypatch.delenv("ENT_PASSWORD", raising=False)
    cfg_file = tmp_path / "config.json"
    store = SettingsStore(cfg_file)
    store.save(login="alice", password="s3cret", sync_interval_hours=6)

    mode = stat.S_IMODE(cfg_file.stat().st_mode)
    assert mode == 0o600
    eff = store.effective()
    assert eff.login == "alice"
    assert eff.password == "s3cret"
    assert eff.sync_interval_hours == 6
    assert eff.has_password is True


def test_empty_password_does_not_wipe_existing(tmp_path, monkeypatch):
    monkeypatch.delenv("ENT_PASSWORD", raising=False)
    store = SettingsStore(tmp_path / "config.json")
    store.save(login="alice", password="keepme")
    store.save(login="alice2", password="")  # user left password blank
    data = json.loads(Path(tmp_path / "config.json").read_text())
    assert data["password"] == "keepme"
    assert data["login"] == "alice2"


def test_env_overrides_file(tmp_path, monkeypatch):
    store = SettingsStore(tmp_path / "config.json")
    store.save(login="file-user", password="file-pw")
    monkeypatch.setenv("ENT_LOGIN", "env-user")
    monkeypatch.setenv("ENT_PASSWORD", "env-pw")
    eff = store.effective()
    assert eff.login == "env-user"
    assert eff.password == "env-pw"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_settings_store.py -q`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web.settings_store`.

- [ ] **Step 3: Write the implementation**

```python
# src/ent_exporter/web/settings_store.py
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WebConfig:
    login: str | None
    password: str | None
    data_dir: Path
    state_db: Path
    base_url: str
    sync_interval_hours: int
    has_password: bool


class SettingsStore:
    """Persisted UI config in a chmod-600 JSON file. Env vars take priority."""

    def __init__(self, config_file: Path | str):
        self.config_file = Path(config_file)

    def _read_file(self) -> dict:
        if not self.config_file.is_file():
            return {}
        return json.loads(self.config_file.read_text())

    def save(self, *, login: str | None = None, password: str | None = None,
             sync_interval_hours: int | None = None) -> None:
        data = self._read_file()
        if login is not None:
            data["login"] = login
        if password:  # blank submission keeps the stored secret
            data["password"] = password
        if sync_interval_hours is not None:
            data["sync_interval_hours"] = int(sync_interval_hours)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.config_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        os.chmod(tmp, 0o600)
        tmp.replace(self.config_file)

    def effective(self) -> WebConfig:
        data = self._read_file()
        login = os.getenv("ENT_LOGIN") or data.get("login")
        password = os.getenv("ENT_PASSWORD") or data.get("password")
        data_dir = Path(os.getenv("ENT_DATA_DIR", "./data"))
        state_db = Path(os.getenv("ENT_STATE_DB", "./state.db"))
        base_url = os.getenv("ENT_BASE_URL", "https://www.ent-ecole.fr")
        interval = int(os.getenv("ENT_SYNC_INTERVAL_HOURS",
                                 str(data.get("sync_interval_hours", 0))))
        return WebConfig(login=login, password=password, data_dir=data_dir,
                         state_db=state_db, base_url=base_url,
                         sync_interval_hours=interval, has_password=bool(password))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_settings_store.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/settings_store.py tests/web/test_settings_store.py
git commit -m "feat(web): persisted settings store (chmod 600, env priority)"
```

---

### Task 3: `jobs` — background sync runner

**Files:**
- Create: `src/ent_exporter/web/jobs.py`
- Test: `tests/web/test_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_jobs.py
import threading
from dataclasses import dataclass
from ent_exporter.web.jobs import SyncRunner


@dataclass
class FakeReport:
    downloaded: int = 3
    skipped: int = 1
    errors: int = 0


def test_run_records_report_and_returns_to_idle():
    done = threading.Event()
    runner = SyncRunner(lambda: (done.wait(1), FakeReport())[1])
    assert runner.trigger() is True
    assert runner.status.state == "running"
    done.set()
    runner._thread.join(2)
    assert runner.status.state == "idle"
    assert runner.status.downloaded == 3
    assert runner.status.skipped == 1
    assert runner.status.last_run_at is not None


def test_single_concurrent_run():
    gate = threading.Event()
    runner = SyncRunner(lambda: (gate.wait(1), FakeReport())[1])
    assert runner.trigger() is True
    assert runner.trigger() is False  # already running
    gate.set()
    runner._thread.join(2)


def test_exception_surfaces_in_status():
    def boom():
        raise RuntimeError("identifiants ENT manquants")
    runner = SyncRunner(boom)
    runner.trigger()
    runner._thread.join(2)
    assert runner.status.state == "error"
    assert "identifiants" in runner.status.last_error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_jobs.py -q`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web.jobs`.

- [ ] **Step 3: Write the implementation**

```python
# src/ent_exporter/web/jobs.py
from __future__ import annotations
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

log = logging.getLogger("ent_exporter.web.jobs")


@dataclass
class RunStatus:
    state: str = "idle"            # idle | running | error
    last_run_at: Optional[str] = None
    last_error: Optional[str] = None
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0


class SyncRunner:
    """Runs one sync job at a time in a background thread."""

    def __init__(self, job: Callable[[], object]):
        # job() performs a full sync and returns an object with
        # .downloaded / .skipped / .errors (a core SyncReport).
        self._job = job
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.status = RunStatus()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def trigger(self) -> bool:
        """Start a run if none is in progress. Returns True if started."""
        if not self._lock.acquire(blocking=False):
            return False
        self.status.state = "running"
        self.status.last_error = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        try:
            report = self._job()
            self.status.downloaded = report.downloaded
            self.status.skipped = report.skipped
            self.status.errors = report.errors
            self.status.state = "idle"
        except Exception as exc:  # surfaced in status, never swallowed
            log.exception("Sync run failed")
            self.status.state = "error"
            self.status.last_error = str(exc)
        finally:
            self.status.last_run_at = datetime.now(timezone.utc).isoformat()
            self._lock.release()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_jobs.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(web): background SyncRunner with single-run lock and status"
```

---

### Task 4: `scheduler` — interval thread

**Files:**
- Create: `src/ent_exporter/web/scheduler.py`
- Test: `tests/web/test_scheduler.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_scheduler.py
import threading
import time
from ent_exporter.web.scheduler import IntervalScheduler


def test_disabled_when_interval_zero():
    calls = []
    sched = IntervalScheduler(0, lambda: calls.append(1))
    sched.start()
    time.sleep(0.2)
    assert sched._thread is None
    assert calls == []


def test_fires_callback_on_interval():
    fired = threading.Event()
    sched = IntervalScheduler(1, fired.set)   # 1 hour nominally
    sched.interval_seconds = 0.05             # shrink for the test
    sched.start()
    assert fired.wait(1.0) is True
    sched.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_scheduler.py -q`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web.scheduler`.

- [ ] **Step 3: Write the implementation**

```python
# src/ent_exporter/web/scheduler.py
from __future__ import annotations
import logging
import threading
from typing import Callable

log = logging.getLogger("ent_exporter.web.scheduler")


class IntervalScheduler:
    """Calls `callback` every `interval_hours` hours in a daemon thread.

    interval_hours <= 0 disables scheduling (start() is a no-op).
    """

    def __init__(self, interval_hours: float, callback: Callable[[], object]):
        self.interval_seconds = interval_hours * 3600
        self._callback = callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.interval_seconds <= 0:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        # _stop.wait returns True when stopped, False on timeout (fire).
        while not self._stop.wait(self.interval_seconds):
            try:
                self._callback()
            except Exception:  # a scheduled failure must not kill the loop
                log.exception("Scheduled sync trigger failed")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_scheduler.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/scheduler.py tests/web/test_scheduler.py
git commit -m "feat(web): internal interval scheduler (no APScheduler)"
```

---

### Task 5: `gallery` — filesystem scan + safe resolve

**Files:**
- Create: `src/ent_exporter/web/gallery.py`
- Test: `tests/web/test_gallery.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_gallery.py
from ent_exporter.web.gallery import scan, safe_resolve


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_scan_groups_by_board_then_month(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")
    _touch(tmp_path / "PS" / "2026-05" / "b.png")
    _touch(tmp_path / ".thumbnails" / "PS" / "2026-06" / "a.jpg.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "notes.txt")  # non-image ignored

    boards = scan(tmp_path)
    assert [b.board for b in boards] == ["PS"]
    months = boards[0].months
    assert [m.month for m in months] == ["2026-06", "2026-05"]  # newest first
    assert [p.name for p in months[0].photos] == ["a.jpg"]
    assert months[0].photos[0].key == "PS/2026-06/a.jpg"


def test_scan_missing_root_is_empty(tmp_path):
    assert scan(tmp_path / "nope") == []


def test_safe_resolve_rejects_traversal(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")
    assert safe_resolve(tmp_path, "PS/2026-06/a.jpg") is not None
    assert safe_resolve(tmp_path, "../secret") is None
    assert safe_resolve(tmp_path, "PS/2026-06/missing.jpg") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_gallery.py -q`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web.gallery`.

- [ ] **Step 3: Write the implementation**

```python
# src/ent_exporter/web/gallery.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
THUMB_DIR = ".thumbnails"


@dataclass
class Photo:
    key: str   # posix path relative to the data root
    name: str


@dataclass
class MonthGroup:
    month: str
    photos: list[Photo] = field(default_factory=list)


@dataclass
class BoardGroup:
    board: str
    months: list[MonthGroup] = field(default_factory=list)


def scan(root: Path | str) -> list[BoardGroup]:
    root = Path(root)
    if not root.is_dir():
        return []
    boards: list[BoardGroup] = []
    for board_dir in sorted(p for p in root.iterdir()
                            if p.is_dir() and p.name != THUMB_DIR):
        months: list[MonthGroup] = []
        for month_dir in sorted((p for p in board_dir.iterdir() if p.is_dir()),
                                reverse=True):
            photos = [
                Photo(key=f"{board_dir.name}/{month_dir.name}/{f.name}", name=f.name)
                for f in sorted(month_dir.iterdir())
                if f.is_file() and f.suffix.lower() in IMAGE_EXTS
            ]
            if photos:
                months.append(MonthGroup(month=month_dir.name, photos=photos))
        if months:
            boards.append(BoardGroup(board=board_dir.name, months=months))
    return boards


def safe_resolve(root: Path | str, key: str) -> Path | None:
    """Resolve a gallery key under root, refusing traversal. None if invalid."""
    root = Path(root).resolve()
    candidate = (root / key).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        return None
    if not candidate.is_file():
        return None
    return candidate
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_gallery.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/gallery.py tests/web/test_gallery.py
git commit -m "feat(web): gallery scan + traversal-safe key resolution"
```

---

### Task 6: `thumbnails` — Pillow thumbnail with disk cache

**Files:**
- Create: `src/ent_exporter/web/thumbnails.py`
- Test: `tests/web/test_thumbnails.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_thumbnails.py
from PIL import Image
from ent_exporter.web.thumbnails import get_or_create, THUMB_DIR


def _make_image(path, size=(800, 600)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 30, 30)).save(path, "JPEG")


def test_creates_and_caches_thumbnail(tmp_path):
    src = tmp_path / "PS" / "2026-06" / "a.jpg"
    _make_image(src)
    out = get_or_create(tmp_path, src, "PS/2026-06/a.jpg")
    assert out.is_file()
    assert THUMB_DIR in out.parts
    with Image.open(out) as im:
        assert max(im.size) <= 320

    mtime = out.stat().st_mtime_ns
    out2 = get_or_create(tmp_path, src, "PS/2026-06/a.jpg")  # cached
    assert out2 == out
    assert out2.stat().st_mtime_ns == mtime  # not regenerated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_thumbnails.py -q`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web.thumbnails`.

- [ ] **Step 3: Write the implementation**

```python
# src/ent_exporter/web/thumbnails.py
from __future__ import annotations
from pathlib import Path
from PIL import Image

THUMB_DIR = ".thumbnails"
MAX_SIZE = (320, 320)


def thumb_path(data_root: Path | str, key: str) -> Path:
    return Path(data_root) / THUMB_DIR / f"{key}.jpg"


def get_or_create(data_root: Path | str, source: Path, key: str) -> Path:
    out = thumb_path(data_root, key)
    if out.is_file() and out.stat().st_mtime >= source.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        im = im.convert("RGB")
        im.thumbnail(MAX_SIZE)
        im.save(out, "JPEG", quality=85)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_thumbnails.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/thumbnails.py tests/web/test_thumbnails.py
git commit -m "feat(web): cached Pillow thumbnails"
```

---

### Task 7: `auth` — optional password session

**Files:**
- Create: `src/ent_exporter/web/auth.py`
- Test: `tests/web/test_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_auth.py
from ent_exporter.web import auth


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_auth.py -q`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web.auth`.

- [ ] **Step 3: Write the implementation**

```python
# src/ent_exporter/web/auth.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_auth.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/auth.py tests/web/test_auth.py
git commit -m "feat(web): optional password session gate"
```

---

### Task 8: `app` factory + templates + static + routes

**Files:**
- Create: `src/ent_exporter/web/app.py`
- Create: `src/ent_exporter/web/templates/base.html`, `gallery.html`, `config.html`, `login.html`
- Create: `src/ent_exporter/web/static/style.css`, `app.js`
- Test: `tests/web/test_app.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_app.py
import json
import threading
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_app.py -q`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web.app`.

- [ ] **Step 3: Write the templates**

`src/ent_exporter/web/templates/base.html`:

```html
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}ent_exporter{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <a href="/" class="brand">📸 ent_exporter</a>
    <nav><a href="/">Galerie</a> <a href="/config">Configuration</a></nav>
  </header>
  <main>{% block content %}{% endblock %}</main>
  <script src="/static/app.js"></script>
</body>
</html>
```

`src/ent_exporter/web/templates/gallery.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="toolbar">
  <form method="post" action="/sync">
    <button type="submit" {% if not configured %}disabled{% endif %}>Synchroniser maintenant</button>
  </form>
  <span id="status" data-state="{{ status.state }}">{{ status.state }}</span>
</section>
{% if not configured %}
<p class="warn">Identifiants ENT manquants — renseigne-les dans <a href="/config">Configuration</a>.</p>
{% endif %}
{% for board in boards %}
<h2>{{ board.board }}</h2>
{% for month in board.months %}
<h3>{{ month.month }}</h3>
<div class="grid">
  {% for photo in month.photos %}
  <a href="/photo/{{ photo.key }}"><img loading="lazy" src="/thumb/{{ photo.key }}" alt="{{ photo.name }}"></a>
  {% endfor %}
</div>
{% endfor %}
{% else %}
<p>Aucune photo pour l'instant. Lance une synchronisation.</p>
{% endfor %}
{% endblock %}
```

`src/ent_exporter/web/templates/config.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>Configuration</h2>
<form method="post" action="/config" class="form">
  <label>Identifiant ENT
    <input type="text" name="login" value="{{ login }}" autocomplete="username">
  </label>
  <label>Mot de passe ENT {% if has_password %}<em>(déjà enregistré — laisser vide pour ne pas changer)</em>{% endif %}
    <input type="password" name="password" autocomplete="new-password" placeholder="••••••••">
  </label>
  <label>Fréquence de synchronisation (heures, 0 = manuel)
    <input type="number" name="sync_interval_hours" min="0" value="{{ sync_interval_hours }}">
  </label>
  <button type="submit">Enregistrer</button>
</form>
{% endblock %}
```

`src/ent_exporter/web/templates/login.html`:

```html
{% extends "base.html" %}
{% block content %}
<h2>Connexion</h2>
{% if error %}<p class="warn">Mot de passe incorrect.</p>{% endif %}
<form method="post" action="/login" class="form">
  <label>Mot de passe <input type="password" name="password" autofocus></label>
  <button type="submit">Entrer</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Write the static assets**

`src/ent_exporter/web/static/style.css`:

```css
* { box-sizing: border-box; }
body { font-family: system-ui, sans-serif; margin: 0; color: #1c1c1c; }
header { display: flex; gap: 1rem; align-items: center; padding: .8rem 1.2rem;
         background: #14532d; color: #fff; }
header a { color: #fff; text-decoration: none; margin-right: 1rem; }
.brand { font-weight: 700; }
main { padding: 1.2rem; max-width: 1100px; margin: 0 auto; }
.toolbar { display: flex; gap: 1rem; align-items: center; margin-bottom: 1rem; }
.toolbar button { background: #16a34a; color: #fff; border: 0; padding: .5rem 1rem;
                  border-radius: 6px; cursor: pointer; }
.toolbar button[disabled] { background: #9ca3af; cursor: not-allowed; }
.warn { background: #fef3c7; padding: .6rem 1rem; border-radius: 6px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: .5rem; margin-bottom: 1.5rem; }
.grid img { width: 100%; height: 150px; object-fit: cover; border-radius: 6px; }
.form { display: flex; flex-direction: column; gap: .9rem; max-width: 420px; }
.form input { width: 100%; padding: .5rem; }
#status[data-state="running"] { color: #b45309; }
#status[data-state="error"] { color: #b91c1c; }
```

`src/ent_exporter/web/static/app.js`:

```javascript
(function () {
  const el = document.getElementById("status");
  if (!el) return;
  async function poll() {
    try {
      const r = await fetch("/api/status");
      const s = await r.json();
      el.textContent = s.state + (s.last_error ? " — " + s.last_error : "");
      el.dataset.state = s.state;
      if (s.state === "running") return setTimeout(poll, 1000);
    } catch (e) { /* keep last shown state */ }
  }
  if (el.dataset.state === "running") poll();
  const form = document.querySelector('form[action="/sync"]');
  if (form) form.addEventListener("submit", () => setTimeout(poll, 500));
})();
```

- [ ] **Step 5: Write the app factory**

```python
# src/ent_exporter/web/app.py
from __future__ import annotations
import dataclasses
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..client import BeneyluClient
from ..sources.cardboard import CardboardSource
from ..state import StateStore
from ..storage.filesystem import FilesystemStorage
from ..sync import Synchronizer
from . import auth, gallery, thumbnails
from .jobs import SyncRunner
from .settings_store import SettingsStore

WEB_DIR = Path(__file__).parent


def _default_job(store: SettingsStore):
    def job():
        cfg = store.effective()
        if not cfg.login or not cfg.password:
            raise RuntimeError("identifiants ENT manquants — voir Configuration")
        storage = FilesystemStorage(cfg.data_dir)
        client = BeneyluClient(base_url=cfg.base_url, login=cfg.login,
                               password=cfg.password, timeout=30.0)
        client.login()
        with StateStore(cfg.state_db) as state, client as c:
            return Synchronizer(c, [CardboardSource()], storage, state).run()
    return job


def create_app(store: SettingsStore | None = None,
               runner: SyncRunner | None = None) -> FastAPI:
    if store is None:
        default_cfg = os.getenv("ENT_CONFIG_FILE") or str(
            Path(os.getenv("ENT_DATA_DIR", "./data")) / "config.json")
        store = SettingsStore(default_cfg)
    if runner is None:
        runner = SyncRunner(_default_job(store))

    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    def guard(request: Request):
        if not auth.is_authenticated(request):
            raise HTTPException(status_code=status.HTTP_303_SEE_OTHER,
                                headers={"Location": "/login"})

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, _=Depends(guard)):
        cfg = store.effective()
        return templates.TemplateResponse(
            request=request, name="gallery.html",
            context={"boards": gallery.scan(cfg.data_dir), "status": runner.status,
                     "configured": bool(cfg.login and cfg.password)})

    @app.get("/thumb/{key:path}")
    def thumb(key: str, _=Depends(guard)):
        cfg = store.effective()
        src = gallery.safe_resolve(cfg.data_dir, key)
        if not src:
            raise HTTPException(status_code=404)
        return FileResponse(thumbnails.get_or_create(cfg.data_dir, src, key))

    @app.get("/photo/{key:path}")
    def photo(key: str, _=Depends(guard)):
        cfg = store.effective()
        src = gallery.safe_resolve(cfg.data_dir, key)
        if not src:
            raise HTTPException(status_code=404)
        return FileResponse(src)

    @app.post("/sync")
    def sync(_=Depends(guard)):
        runner.trigger()
        return RedirectResponse("/", status_code=303)

    @app.get("/api/status")
    def status_api(_=Depends(guard)):
        return JSONResponse(dataclasses.asdict(runner.status))

    @app.get("/config", response_class=HTMLResponse)
    def config_get(request: Request, _=Depends(guard)):
        cfg = store.effective()
        return templates.TemplateResponse(
            request=request, name="config.html",
            context={"login": cfg.login or "", "has_password": cfg.has_password,
                     "sync_interval_hours": cfg.sync_interval_hours})

    @app.post("/config")
    def config_post(login: str = Form(""), password: str = Form(""),
                    sync_interval_hours: int = Form(0), _=Depends(guard)):
        store.save(login=login or None, password=password or None,
                   sync_interval_hours=sync_interval_hours)
        return RedirectResponse("/config", status_code=303)

    if auth.password_required():
        @app.get("/login", response_class=HTMLResponse)
        def login_get(request: Request):
            return templates.TemplateResponse(
                request=request, name="login.html", context={"error": False})

        @app.post("/login")
        def login_post(request: Request, password: str = Form("")):
            if auth.check_password(password):
                resp = RedirectResponse("/", status_code=303)
                resp.set_cookie(auth.COOKIE, auth.session_cookie_value(),
                                httponly=True, samesite="lax")
                return resp
            return templates.TemplateResponse(
                request=request, name="login.html",
                context={"error": True}, status_code=401)

        @app.get("/logout")
        def logout():
            resp = RedirectResponse("/login", status_code=303)
            resp.delete_cookie(auth.COOKIE)
            return resp

    return app
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/web/test_app.py -q`
Expected: PASS (6 passed).

- [ ] **Step 7: Commit**

```bash
git add src/ent_exporter/web/app.py src/ent_exporter/web/templates src/ent_exporter/web/static tests/web/test_app.py
git commit -m "feat(web): FastAPI app — gallery, sync trigger, status, config, optional login"
```

---

### Task 9: uvicorn entrypoint + Docker runtime

**Files:**
- Create: `src/ent_exporter/web/__main__.py`
- Create: `runtimes/docker/Dockerfile.web`
- Modify: `runtimes/docker/docker-compose.yml`
- Modify: `.env.example`
- Test: `tests/web/test_entrypoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_entrypoint.py
import logging
from ent_exporter.web import __main__ as entry


def test_warns_when_bound_to_all_interfaces(monkeypatch, caplog):
    monkeypatch.setenv("ENT_WEB_HOST", "0.0.0.0")
    monkeypatch.delenv("ENT_WEB_PASSWORD", raising=False)
    started = {}
    monkeypatch.setattr(entry.uvicorn, "run",
                        lambda app, host, port: started.update(host=host, port=port))
    monkeypatch.setattr(entry, "create_app", lambda: object())
    with caplog.at_level(logging.WARNING):
        entry.main()
    assert started["host"] == "0.0.0.0"
    assert any("0.0.0.0" in r.message for r in caplog.records)


def test_no_warning_on_localhost(monkeypatch, caplog):
    monkeypatch.setenv("ENT_WEB_HOST", "127.0.0.1")
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, host, port: None)
    monkeypatch.setattr(entry, "create_app", lambda: object())
    with caplog.at_level(logging.WARNING):
        entry.main()
    assert not any("0.0.0.0" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_entrypoint.py -q`
Expected: FAIL — `ModuleNotFoundError: ent_exporter.web.__main__`.

- [ ] **Step 3: Write the entrypoint**

```python
# src/ent_exporter/web/__main__.py
from __future__ import annotations
import logging
import os

import uvicorn

from .app import create_app

log = logging.getLogger("ent_exporter.web")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    host = os.getenv("ENT_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("ENT_WEB_PORT", "8000"))
    if host == "0.0.0.0" and not os.getenv("ENT_WEB_PASSWORD"):  # noqa: S104
        log.warning("L'UI ecoute sur 0.0.0.0 (exposee sur le reseau) sans mot de "
                    "passe. Definis ENT_WEB_PASSWORD pour proteger l'acces.")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
```

Note: the scheduler is started inside `create_app` via a startup hook in production; for the test the warning path is what matters. Add to `create_app` (Task 8 file) a FastAPI startup that launches `IntervalScheduler(cfg.sync_interval_hours, runner.trigger)` — append the snippet below to `create_app` just before `return app`:

```python
    from .scheduler import IntervalScheduler

    @app.on_event("startup")
    def _start_scheduler():
        cfg = store.effective()
        scheduler = IntervalScheduler(cfg.sync_interval_hours, runner.trigger)
        scheduler.start()
        app.state.scheduler = scheduler

    @app.on_event("shutdown")
    def _stop_scheduler():
        sched = getattr(app.state, "scheduler", None)
        if sched:
            sched.stop()
```

(If `on_event` raises a deprecation that `ruff` flags, switch to the `lifespan=` form; the interval-0 default means tests using a bare `TestClient` never start a thread.)

- [ ] **Step 4: Write the Docker runtime**

`runtimes/docker/Dockerfile.web`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[web]"
ENV ENT_DATA_DIR=/data ENT_STATE_DB=/data/state.db \
    ENT_CONFIG_FILE=/data/config.json ENT_WEB_HOST=0.0.0.0 ENT_WEB_PORT=8000
VOLUME ["/data"]
EXPOSE 8000
ENTRYPOINT ["python", "-m", "ent_exporter.web"]
```

In `runtimes/docker/docker-compose.yml`, add a `web` service alongside the existing `ent-exporter`:

```yaml
  web:
    build:
      context: ../..
      dockerfile: runtimes/docker/Dockerfile.web
    environment:
      ENT_WEB_PASSWORD: ${ENT_WEB_PASSWORD:-}
      ENT_SYNC_INTERVAL_HOURS: ${ENT_SYNC_INTERVAL_HOURS:-0}
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./data:/data
    restart: unless-stopped
```

Append to `.env.example`:

```
# --- Web UI (optional) ---
# ENT_WEB_PASSWORD=change-me        # protège l'accès à l'UI (sinon accès libre)
# ENT_SYNC_INTERVAL_HOURS=12        # sync auto toutes les N heures (0 = manuel)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/web/test_entrypoint.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add src/ent_exporter/web/__main__.py src/ent_exporter/web/app.py runtimes/docker/Dockerfile.web runtimes/docker/docker-compose.yml .env.example tests/web/test_entrypoint.py
git commit -m "feat(web): uvicorn entrypoint, bind warning, Docker web runtime"
```

---

### Task 10: Full-suite gate + README update

**Files:**
- Modify: `README.md`
- Test: whole suite

- [ ] **Step 1: Run the full containerized check**

Run: `make check`
Expected: ruff clean + all tests pass (Phase 1 suite + new `tests/web/`). If ruff flags unused imports or the `on_event` deprecation, fix inline (switch to `lifespan=`), re-run.

- [ ] **Step 2: Update the README usage + screenshots sections**

In `README.md`, replace the "Captures d'écran" placeholder block and extend "Utilisation" with the web UI:

````markdown
## Utilisation

### Interface web (recommandé)

```bash
docker compose -f runtimes/docker/docker-compose.yml up web
```

Ouvre <http://127.0.0.1:8000> : renseigne tes identifiants ENT dans **Configuration**,
clique **Synchroniser maintenant**, et parcours la galerie. Pour une sync automatique,
règle la fréquence (en heures) ; pour exposer l'UI sur le réseau, définis `ENT_WEB_PASSWORD`.

### En ligne de commande

```bash
ent-exporter login-test   # vérifie la connexion
ent-exporter list-boards  # liste les tableaux
ent-exporter sync         # télécharge les nouvelles photos
```

## Captures d'écran

![Galerie des photos](docs/screenshots/gallery.png)
![Configuration](docs/screenshots/config.png)
````

(Generate the two PNGs by running the UI locally once it works, save them under
`docs/screenshots/`. If not captured yet, leave the image lines commented to avoid
broken links.)

- [ ] **Step 3: Commit**

```bash
git add README.md docs/screenshots 2>/dev/null; git add README.md
git commit -m "docs: web UI usage + gallery screenshots"
```

- [ ] **Step 4: Final review**

Dispatch a final code reviewer over the whole `web/` package (or run `make check` one last time), then use **superpowers:finishing-a-development-branch**.

---

## Notes for later lots (NOT in this plan)

- **Lot B** — GitHub Actions runtime + Google Drive `Storage` backend.
- **Lot C** — additional `Source`s (family-information / chat / newspaper) — needs API recon first.
- **Lot D** — `card.updatedAt` cursor optimization in `core` (`StateStore` already records `card_updated_at`).
- The `web` service runs the same `core` as the CLI; keep all business logic in `core`, never in `web/`.
