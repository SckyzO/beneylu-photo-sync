from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WebConfig:
    login: str | None
    password: str | None = field(repr=False)
    data_dir: Path
    state_db: Path
    base_url: str
    sync_interval_hours: int
    has_password: bool
    excluded_boards: list[str] = field(default_factory=list)
    sync_workers: int = 4


class SettingsStore:
    """Persisted UI config in a chmod-600 JSON file. Env vars take priority."""

    def __init__(self, config_file: Path | str):
        self.config_file = Path(config_file)

    def _read_file(self) -> dict:
        if not self.config_file.is_file():
            return {}
        return json.loads(self.config_file.read_text())

    def save(self, *, login: str | None = None, password: str | None = None,
             sync_interval_hours: int | None = None,
             excluded_boards: list[str] | None = None) -> None:
        data = self._read_file()
        if login is not None:
            data["login"] = login
        if password:  # blank submission keeps the stored secret
            data["password"] = password
        if sync_interval_hours is not None:
            data["sync_interval_hours"] = int(sync_interval_hours)
        if excluded_boards is not None:
            data["excluded_boards"] = list(excluded_boards)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.config_file.with_suffix(".tmp")
        # Create the temp file already restricted to 0o600 so the plaintext
        # secret is never briefly world-readable (umask only removes bits).
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data))
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
        env_excl = os.getenv("ENT_EXCLUDED_BOARDS")
        if env_excl is not None:
            excluded = [s.strip() for s in env_excl.split(",") if s.strip()]
        else:
            excluded = list(data.get("excluded_boards", []))
        workers = int(os.getenv("ENT_SYNC_WORKERS", "4"))
        return WebConfig(login=login, password=password, data_dir=data_dir,
                         state_db=state_db, base_url=base_url,
                         sync_interval_hours=interval, has_password=bool(password),
                         excluded_boards=excluded, sync_workers=workers)
