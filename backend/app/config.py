"""Application configuration.

All runtime configuration is read from environment variables (or a local
.env file) so that no environment-specific value is hardcoded in source.
See .env.example for the full list of supported variables.
"""

import json
from typing import Annotated, Literal
from urllib.parse import urlsplit
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repository root: backend/app/config.py -> backend/app -> backend -> repo root
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Environment-driven settings for the MarketPulse AI backend."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "MarketPulse AI API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    # Empty by default so routes match the API outline in PROJECT_CONTEXT.md
    # section 15. Set to e.g. "/api" to namespace every feature endpoint.
    API_PREFIX: str = ""

    # --- Server ---
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # --- Database ---
    # SQLite by default for local development. Swap in a PostgreSQL URL
    # (postgresql+psycopg://user:pass@host:5432/dbname) for production
    # without any code change.
    DATABASE_URL: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'marketpulse.db').as_posix()}"
    SQL_ECHO: bool = False

    # --- Authentication ---
    # MUST be overridden in any deployed environment. The default exists so
    # local development works out of the box; startup refuses to use it when
    # ENVIRONMENT is not 'development'.
    JWT_SECRET_KEY: str = "dev-only-insecure-secret-change-me"
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 12, ge=1, le=10080)

    # --- Marketplace collection (Phase 4) ---
    # Amazon Product Advertising API 5.0. Requires an approved Amazon
    # Associate account; the collector reports itself unavailable when
    # these are unset rather than falling back to scraping.
    AMAZON_PAAPI_ACCESS_KEY: str = ""
    AMAZON_PAAPI_SECRET_KEY: str = ""
    AMAZON_PAAPI_PARTNER_TAG: str = ""
    AMAZON_PAAPI_HOST: str = "webservices.amazon.in"
    AMAZON_PAAPI_REGION: str = "eu-west-1"
    AMAZON_PAAPI_MARKETPLACE: str = "www.amazon.in"

    # --- CORS ---
    # Comma-separated list of allowed frontend origins.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- Data / ML paths (directories are created on startup) ---
    DATA_DIR: Path = PROJECT_ROOT / "data"
    MODEL_ARTIFACT_DIR: Path = BACKEND_DIR / "app" / "ml" / "artifacts"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow CORS_ORIGINS to be given as a comma-separated string."""
        if isinstance(value, str):
            return json.loads(value) if value.strip().startswith("[") else [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _boolean_debug(cls, value: object) -> object:
        # Some Windows shells export DEBUG=release. Map only these known labels;
        # all other values still undergo strict Pydantic boolean parsing.
        if isinstance(value, str):
            value = value.strip().lower()
            if value == "release":
                return False
            if value == "debug":
                return True
        return value

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _exact_origins(cls, values: list[str]) -> list[str]:
        for origin in values:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
                raise ValueError("CORS origins must be exact HTTP(S) origins without paths or credentials.")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def _safe_runtime(self):
        if not self.JWT_SECRET_KEY.strip():
            raise ValueError("JWT_SECRET_KEY must not be empty.")
        if not self.is_development:
            if self.uses_default_jwt_secret or len(self.JWT_SECRET_KEY.encode()) < 32:
                raise ValueError("Use a random JWT_SECRET_KEY of at least 32 bytes outside development.")
            if self.DEBUG:
                raise ValueError("DEBUG must be false outside development.")
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def uses_default_jwt_secret(self) -> bool:
        return self.JWT_SECRET_KEY == "dev-only-insecure-secret-change-me"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
