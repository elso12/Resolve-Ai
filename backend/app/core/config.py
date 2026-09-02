"""
ResolveAI — Application Configuration

Centralised settings via Pydantic Settings v2 with strict environment
validation.  All secrets are loaded from environment variables or a
`.env` file; nothing is hardcoded for production.
"""

from __future__ import annotations

import secrets
from enum import Enum
from typing import Any

from pydantic import (
    Field,
    PostgresDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Allowed deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Application-wide settings.

    Values are loaded in priority order:
      1. Environment variables
      2. `.env` file (project root)
      3. Defaults defined below

    In **production** mode the ``SECRET_KEY`` *must* be explicitly set —
    the auto-generated fallback is only accepted in development / staging.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Project ──────────────────────────────────────────────────────────
    PROJECT_NAME: str = "ResolveAI"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # ── Security ─────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: PostgresDsn | str = Field(
        default="postgresql+asyncpg://postgres:postgrespassword@localhost:5432/resolveai",  # type: ignore[assignment]
    )

    # ── External Services ────────────────────────────────────────────────
    OPENAI_API_KEY: str | None = None

    # ── CORS ─────────────────────────────────────────────────────────────
    # Stored as a comma-separated string because pydantic-settings v2.15+
    # attempts JSON parsing on list-typed fields before validators run.
    CORS_ORIGINS: str = ""

    # ── Logging ──────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False

    # ── Validators ───────────────────────────────────────────────────────

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalise_log_level(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.upper()
        return v

    @model_validator(mode="after")
    def enforce_production_secret(self) -> "Settings":
        """
        Prevent the application from starting in production with an
        auto-generated (i.e. ephemeral) secret key.
        """
        if self.ENVIRONMENT == Environment.PRODUCTION:
            # If the key looks auto-generated (base64 URL-safe, 86 chars for
            # a 64-byte token), reject it.  Real keys should be set explicitly.
            if len(self.SECRET_KEY) == 86 and self.SECRET_KEY.replace("-", "").replace("_", "").isalnum():
                raise ValueError(
                    "SECRET_KEY must be explicitly set in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
        return self

    @model_validator(mode="after")
    def set_debug_from_environment(self) -> "Settings":
        """Auto-enable DEBUG in development unless explicitly overridden."""
        if self.ENVIRONMENT == Environment.DEVELOPMENT:
            self.DEBUG = True
        return self

    @property
    def async_database_url(self) -> str:
        """Return the database URL as a plain string (required by SQLAlchemy)."""
        return str(self.DATABASE_URL)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS into a list of origin strings."""
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# ── Singleton ────────────────────────────────────────────────────────────────
settings = Settings()
