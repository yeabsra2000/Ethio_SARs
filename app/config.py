"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OVERLAYS_DIR = DATA_DIR / "overlays"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
FRONTEND_DIR = BASE_DIR / "frontend"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Dancing with the SARs - GERD"
    app_version: str = "1.0.0"
    gemini_api_key: str | None = None
    earthdata_token: str | None = None
    gemini_model: str = "gemini-3.1-flash-lite"
    embedding_model: str = "gemini-embedding-001"
    rag_top_k: int = 3
    cors_allow_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
