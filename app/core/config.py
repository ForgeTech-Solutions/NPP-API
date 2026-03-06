"""Application configuration settings."""
import os
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database - Support both PostgreSQL (production) and SQLite (development)
    DATABASE_URL: str = "sqlite+aiosqlite:///./nomenclature.db"
    POSTGRES_USER: str = "npp"
    POSTGRES_PASSWORD: str = "npp_secret"
    POSTGRES_DB: str = "nomenclature"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    # JWT
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # App
    APP_NAME: str = "Nomenclature API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Admin (initial user)
    ADMIN_EMAIL: str = "admin@nomenclature.dz"
    ADMIN_PASSWORD: str = "Admin2025!"

    # Docs protection (HTTP Basic Auth on /docs, /redoc, /openapi.json)
    DOCS_USERNAME: str = "admin"
    DOCS_PASSWORD: str = "docs2025!"

    # Reverse proxy prefix (e.g. /v1 when behind nginx)
    ROOT_PATH: str = ""

    # ── Microsoft 365 Email (Graph API) ────────────────────────────────
    MICROSOFT_TENANT_ID: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MAIL_FROM: str = ""          # e.g. noreply@nhaddag.net
    MAIL_FROM_NAME: str = "NPP — Nomenclature Pharmaceutique"
    MAIL_ENABLED: bool = False   # Set True once M365 creds are configured
    ADMIN_NOTIFICATION_EMAIL: str = ""  # Admin receives signup notifications

    @model_validator(mode="after")
    def normalize_database_url(self):
        """Build a reliable DB URL for Docker and sanitize malformed values."""
        db_url = (self.DATABASE_URL or "").strip().strip('"').strip("'")
        running_in_docker = os.path.exists("/.dockerenv") or os.getenv("RUNNING_IN_DOCKER") == "1"

        if running_in_docker:
            user = quote_plus(self.POSTGRES_USER)
            password = quote_plus(self.POSTGRES_PASSWORD)
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{user}:{password}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
            return self

        if not db_url:
            self.DATABASE_URL = "sqlite+aiosqlite:///./nomenclature.db"
            return self

        placeholder_markers = ["@host:", "://user:password@", "://user:pass@"]
        if any(marker in db_url for marker in placeholder_markers):
            self.DATABASE_URL = "sqlite+aiosqlite:///./nomenclature.db"
            return self

        self.DATABASE_URL = db_url
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
