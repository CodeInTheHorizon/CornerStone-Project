"""Application configuration.

All runtime configuration is read from environment variables (or a local
.env file) so that no environment-specific value is hardcoded in source.
See .env.example for the full list of supported variables.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    DEBUG: bool = True
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
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

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
    CORS_ORIGINS: list[str] = Field(
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
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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
