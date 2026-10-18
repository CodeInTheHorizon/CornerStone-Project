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

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

# Repository root: backend/app/config.py -> backend/app -> backend -> repo root
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

SUPPORTED_DATABASE_DRIVERS = {"sqlite", "sqlite+pysqlite", "postgresql+psycopg"}


class Settings(BaseSettings):
    """Environment-driven settings for the MarketPulse AI backend."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
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
    PORT: int = Field(default=8000, ge=1, le=65535)
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    ACCESS_LOG: bool = False

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

    # --- Abuse controls (single process; replace store before scaling) ---
    RATE_LIMIT_LOGIN: int = Field(default=5, ge=1)
    RATE_LIMIT_REGISTER: int = Field(default=3, ge=1)
    RATE_LIMIT_PREDICT: int = Field(default=30, ge=1)
    RATE_LIMIT_COLLECT: int = Field(default=5, ge=1)
    RATE_LIMIT_BUILD: int = Field(default=5, ge=1)
    RATE_LIMIT_IMPORT: int = Field(default=5, ge=1)
    RATE_LIMIT_DEMO: int = Field(default=5, ge=1)
    RATE_LIMIT_TRAIN: int = Field(default=2, ge=1)  # per hour
    REQUEST_MAX_BYTES: int = Field(default=1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    IMPORT_REQUEST_MAX_BYTES: int = Field(default=6 * 1024 * 1024, ge=6 * 1024 * 1024, le=10 * 1024 * 1024)

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

    # DataForSEO Merchant API is the supported Amazon search provider.  These
    # are deliberately backend-only and a disabled switch prevents accidental
    # paid requests in a newly deployed environment.
    DATAFORSEO_LOGIN: str = ""
    DATAFORSEO_PASSWORD: SecretStr = SecretStr("")
    AMAZON_LIVE_ENABLED: bool = False
    DATAFORSEO_TIMEOUT_SECONDS: float = Field(default=20.0, ge=1.0, le=60.0)

    # Amazon public search-page collector. Off by default: Amazon's Conditions
    # of Use restrict automated collection, so enabling this is an explicit
    # operator decision, not a fallback the system reaches for on its own.
    AMAZON_WEB_ENABLED: bool = False
    AMAZON_WEB_DOMAIN: str = "www.amazon.in"
    AMAZON_WEB_CURRENCY: str = "INR"
    AMAZON_WEB_LOCALE: str = "en-IN"
    AMAZON_WEB_TIMEOUT_SECONDS: float = Field(default=15.0, ge=1.0, le=60.0)

    # Flipkart public search-page collector.
    FLIPKART_WEB_ENABLED: bool = False
    FLIPKART_WEB_DOMAIN: str = "www.flipkart.com"
    FLIPKART_WEB_CURRENCY: str = "INR"
    FLIPKART_WEB_TIMEOUT_SECONDS: float = Field(default=15.0, ge=1.0, le=60.0)

    # Meesho public search-page & provider collector.
    MEESHO_WEB_ENABLED: bool = True
    MEESHO_WEB_DOMAIN: str = "www.meesho.com"
    MEESHO_WEB_CURRENCY: str = "INR"
    MEESHO_WEB_TIMEOUT_SECONDS: float = Field(default=15.0, ge=1.0, le=60.0)
    MEESHO_PROXY_URL: str = ""
    MEESHO_PROVIDER_ENABLED: bool = False
    MEESHO_PROVIDER_BASE_URL: str = ""
    MEESHO_PROVIDER_API_KEY: SecretStr = SecretStr("")

    # Reserved approved-provider adapter slots.  No scraper is used for these
    # marketplaces; an operator must explicitly enable a lawful provider.
    CROMA_PROVIDER_ENABLED: bool = False
    CROMA_PROVIDER_BASE_URL: str = ""
    CROMA_PROVIDER_API_KEY: SecretStr = SecretStr("")
    ALIBABA_PROVIDER_ENABLED: bool = False
    ALIBABA_PROVIDER_BASE_URL: str = ""
    ALIBABA_PROVIDER_API_KEY: SecretStr = SecretStr("")

    # --- Model training minimums (Phase 12) ---
    # Training returns insufficient_data below these, even when scikit-learn
    # could technically fit something. See docs/PHASE_12_REPORT.md.
    # Labelled rows remaining after leakage-safe, per-partition labelling.
    ML_MIN_LABELLED_ROWS: int = Field(default=100, ge=10)
    ML_MIN_TRAINING_ROWS: int = Field(default=60, ge=10)
    ML_MIN_VALIDATION_ROWS: int = Field(default=20, ge=5)
    ML_MIN_UNIQUE_PRODUCTS: int = Field(default=10, ge=2)
    # Each side of the split needs two dates to label anything; 4 is structural.
    ML_MIN_OBSERVATION_DATES: int = Field(default=4, ge=4)
    # Per class, in the training partition.
    ML_MIN_ROWS_PER_CLASS: int = Field(default=5, ge=1)

    # --- Flipkart Affiliate API (Phase 11) ---
    # Credentials from an approved Flipkart Affiliate account (API > API Token).
    # Backend environment only; never VITE_-prefixed, logged or stored.
    FLIPKART_AFFILIATE_ID: str = ""
    FLIPKART_AFFILIATE_TOKEN: SecretStr = SecretStr("")
    # Flipkart's API terms limit use to "in conjunction with Flipkart's
    # platform" and are silent on storing history, analytics and ML. The
    # collector stays disabled until the operator sets this to true, which
    # records that Flipkart has confirmed this application's use in writing.
    FLIPKART_DATA_USE_APPROVED: bool = False
    FLIPKART_TIMEOUT_SECONDS: float = Field(default=15.0, ge=1.0, le=60.0)

    # --- Live product-page scraping (app/live_scraping) ---
    # Each marketplace is off until the operator turns it on. A marketplace
    # that blocks ordinary requests is recorded as unavailable, never bypassed.
    SCRAPER_AMAZON_ENABLED: bool = False
    SCRAPER_FLIPKART_ENABLED: bool = False
    SCRAPER_MEESHO_ENABLED: bool = False
    SCRAPER_AMAZON_DOMAIN: str = "www.amazon.in"
    SCRAPER_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    )
    SCRAPER_ACCEPT_LANGUAGE: str = "en-IN,en;q=0.9"
    # Product token used to select this client's robots.txt group.
    SCRAPER_ROBOTS_AGENT: str = "MarketPulseBot"
    # One fixed egress proxy, e.g. http://user:pass@proxy.internal:3128.
    SCRAPER_HTTP_PROXY: SecretStr = SecretStr("")
    SCRAPER_HTTPS_PROXY: SecretStr = SecretStr("")
    SCRAPER_CONNECT_TIMEOUT_SECONDS: float = Field(default=5.0, ge=1.0, le=30.0)
    SCRAPER_READ_TIMEOUT_SECONDS: float = Field(default=20.0, ge=1.0, le=120.0)
    SCRAPER_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=6)
    SCRAPER_BACKOFF_BASE_SECONDS: float = Field(default=2.0, ge=0.1, le=60.0)
    SCRAPER_BACKOFF_MAX_SECONDS: float = Field(default=60.0, ge=1.0, le=600.0)
    # Minimum spacing between requests to one host. The floor is deliberate.
    SCRAPER_MIN_INTERVAL_SECONDS: float = Field(default=5.0, ge=1.0, le=600.0)
    # How long a blocked / throttled marketplace is left alone.
    SCRAPER_BLOCK_COOLDOWN_MINUTES: int = Field(default=360, ge=5, le=7 * 24 * 60)
    SCRAPER_DEFAULT_REFRESH_MINUTES: int = Field(default=1440, ge=15, le=30 * 24 * 60)
    # Search / best-seller pages: 20-30 products per request, so they carry
    # the frequent price/rating refresh...
    SCRAPER_LISTING_REFRESH_MINUTES: int = Field(default=1440, ge=15, le=30 * 24 * 60)
    # ...while products discovered on them get a product-page visit (seller,
    # model, availability) this often, spread across the interval.
    SCRAPER_DETAIL_REFRESH_MINUTES: int = Field(default=7 * 24 * 60, ge=60, le=90 * 24 * 60)

    # --- CORS ---
    # Comma-separated list of allowed frontend origins.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- Data / ML paths (directories are created on startup) ---
    DATA_DIR: Path = PROJECT_ROOT / "data"
    MODEL_ARTIFACT_DIR: Path = BACKEND_DIR / "app" / "ml" / "artifacts"

    # --- Dataset / model storage (app/storage/) ---
    # auto = local files in development, database bundles everywhere else.
    STORAGE_BACKEND: Literal["auto", "local", "database"] = "auto"
    # Per stored dataset or model; bundles are serialized and read in memory.
    STORAGE_MAX_BYTES: int = Field(default=128 * 1024 * 1024, ge=1024, le=512 * 1024 * 1024)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _database_driver(cls, value: object) -> object:
        """Accept SQLite or PostgreSQL, using only the drivers in requirements.txt.

        Hosted providers hand out postgres:// or postgresql:// URLs, which
        SQLAlchemy would map to psycopg2 (not installed); rewrite them to psycopg.
        """
        if not isinstance(value, str):
            return value
        value = value.strip()
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+psycopg://" + value[len(prefix):]
                break
        try:
            drivername = make_url(value).drivername
        except ArgumentError:
            drivername = None
        if drivername not in SUPPORTED_DATABASE_DRIVERS:
            # Never echo the URL: it normally carries the database password.
            raise ValueError("DATABASE_URL must be a sqlite:/// or postgresql+psycopg:// URL.")
        return value

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
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or "*" in origin or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError("CORS origins must be exact HTTP(S) origins without paths or credentials.")
            try:
                parsed.port
            except ValueError:
                raise ValueError("CORS origin contains an invalid port.") from None
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def _safe_runtime(self):
        if not self.JWT_SECRET_KEY.strip():
            raise ValueError("JWT_SECRET_KEY must not be empty.")
        if not self.is_development:
            if self.is_sqlite:
                raise ValueError("Production requires a PostgreSQL DATABASE_URL; SQLite is development-only.")
            if self.storage_backend != "database":
                raise ValueError("Production requires durable database storage.")
            if self.uses_default_jwt_secret or len(self.JWT_SECRET_KEY.encode()) < 32:
                raise ValueError("Use a random JWT_SECRET_KEY of at least 32 bytes outside development.")
            if self.DEBUG:
                raise ValueError("DEBUG must be false outside development.")
            if self.SQL_ECHO:
                raise ValueError("SQL_ECHO must be false outside development.")
            if not any(origin.startswith("https://") for origin in self.CORS_ORIGINS):
                raise ValueError("Configure an explicit HTTPS frontend origin outside development.")
            for origin in self.CORS_ORIGINS:
                parsed = urlsplit(origin)
                if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                    raise ValueError("Non-local production CORS origins must use HTTPS.")
        return self

    @property
    def storage_backend(self) -> Literal["local", "database"]:
        """STORAGE_BACKEND with 'auto' resolved for the current environment."""
        if self.STORAGE_BACKEND == "auto":
            return "local" if self.is_development else "database"
        return self.STORAGE_BACKEND

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
