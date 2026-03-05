"""Application configuration settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database - Support both PostgreSQL (production) and SQLite (development)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite+aiosqlite:///./nomenclature.db"
    )
    
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
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


settings = Settings()
