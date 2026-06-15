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
