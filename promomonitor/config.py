from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_ID: int
    API_HASH: str
    SESSION_NAME: str = "promomonitor"
    STORAGE_PATH: Path = Path("keywords.json")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna uma instância única (singleton em cache) das configurações validadas."""
    return Settings()  # pyright: ignore[reportCallIssue]
