"""Application settings. Precedence: env vars > .env > defaults."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration for little-warren."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="LW_", extra="ignore")

    env: str = "dev"
    data_cache_dir: Path = Path("data/cache")
    default_interval: str = "1d"
    default_lookback_days: int = 730


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
