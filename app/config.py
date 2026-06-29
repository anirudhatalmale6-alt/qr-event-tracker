"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """QR Event Tracker application settings.

    Values are loaded from environment variables (case-insensitive) and
    fall back to the defaults defined here.  A `.env` file in the project
    root is also read automatically.
    """

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Core ---
    APP_NAME: str = "QR Event Tracker"

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./qr_tracker.db"

    # --- Auth ---
    API_KEY: str = "changeme-api-key-12345"

    # --- Geolocation ---
    GEOLOCATION_CACHE_TTL: int = 86400  # 24 hours

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["*"]

    # --- Rate limiting ---
    RATE_LIMIT_SCAN: str = "60/minute"

    # --- Base URL (for QR code generation) ---
    BASE_URL: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
