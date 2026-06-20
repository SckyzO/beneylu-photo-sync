# src/ent_exporter/config.py
from pathlib import Path
from typing import Annotated
from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENT_", env_file=".env", extra="ignore")

    login: str
    password: SecretStr
    base_url: str = "https://www.ent-ecole.fr"
    data_dir: Path = Field(default=Path("./data"))
    state_db: Path = Field(default=Path("./state.db"))
    request_timeout: float = 30.0
    # Boards to skip at sync, e.g. ENT_EXCLUDED_BOARDS="APEIT, Vie de l'école".
    excluded_boards: Annotated[list[str], NoDecode] = []

    @field_validator("excluded_boards", mode="before")
    @classmethod
    def _split_excluded(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v  # already a list (default or programmatic)
