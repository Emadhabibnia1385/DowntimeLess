from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DL_", env_file=".env", extra="ignore")

    data_dir: Path = ROOT / "data"
    public_url: str = "http://127.0.0.1:7390"
    bot_token: str = ""
    frontend_dir: Path = ROOT / "web" / "dist"
    agent_dir: Path = ROOT / "agent"
    interval_s: int = 30
    offline_after: int = 3  # missed intervals before a server counts as offline
    cookie_secure: bool = False
    dev_telegram: str = "emadhabibnia"
    dev_github: str = "emadhabibnia1385"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "downtimeless.db"

    @property
    def claim_file(self) -> Path:
        return self.data_dir / "claim_link.txt"


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
