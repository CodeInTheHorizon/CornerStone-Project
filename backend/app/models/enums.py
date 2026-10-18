"""Shared enumerations used across the MarketPulse AI data model."""

from enum import Enum


class Platform(str, Enum):
    """Marketplaces targeted by the MVP.

    Kept as a plain string enum so new marketplaces can be added without a
    schema migration on SQLite; values are stored as text.
    """

    AMAZON = "amazon"
    FLIPKART = "flipkart"
    CROMA = "croma"
    ALIBABA = "alibaba"


class SourceType(str, Enum):
    """Where a stored record actually came from.

    Every persisted observation carries one of these. Nothing in the UI or the
    ML pipeline may treat IMPORTED or DEMO rows as live marketplace data.

    Stored lowercase for consistency with Platform; the UI uppercases them.
    """

    #: Collected from the marketplace itself, through a permitted route.
    LIVE = "live"
    #: Supplied by the operator as a CSV/JSON upload. Real data, but this
    #: system did not observe it and cannot vouch for when or how it was taken.
    IMPORTED = "imported"
    #: Open public benchmark or research dataset (e.g., Kaggle, UCI) with real sales labels.
    PUBLIC_DATASET = "public_dataset"
    #: Seller-uploaded historical sales records (X -> actual units sold).
    SELLER_DATA = "seller_data"
    #: Synthetic fixture bundled for development and testing. Not real market
    #: data, and must never be presented as such.
    DEMO = "demo"


#: Backwards-compatible alias. `DataSource` was the Phase 1 name.
DataSource = SourceType


class IngestionMode(str, Enum):
    """How a platform's data reaches the system."""

    #: An official, credentialed API (e.g. Amazon PA-API 5.0).
    LIVE_API = "LIVE_API"
    #: A public source whose robots rules permit programmatic access.
    LIVE_PUBLIC_SOURCE = "LIVE_PUBLIC_SOURCE"
    #: Operator-supplied dataset upload.
    IMPORTED = "IMPORTED"
    #: Bundled synthetic fixture.
    DEMO = "DEMO"
    #: No permitted route exists at all.
    UNAVAILABLE = "UNAVAILABLE"


class CollectorState(str, Enum):
    """Why a collector can or cannot run right now.

    Deliberately finer than available/unavailable, so a missing key, a missing
    data-use approval, a throttled provider and a failing provider each stay
    distinguishable instead of all reading "unavailable".
    """

    #: Configured and approved; a LIVE fetch may be attempted.
    LIVE = "live"
    #: An official API exists but its credentials are not configured.
    CREDENTIALS_MISSING = "credentials_missing"
    #: Credentials are present, but the operator has not confirmed that the
    #: provider permits this application's storage/analytics use of its data.
    APPROVAL_REQUIRED = "approval_required"
    #: The provider rejected the configured credentials (HTTP 401/403).
    CREDENTIALS_REJECTED = "credentials_rejected"
    #: The provider throttled the last request; wait before retrying.
    RATE_LIMITED = "rate_limited"
    #: The last request failed on the provider side (timeout, 5xx, bad payload).
    PROVIDER_ERROR = "provider_error"
    #: No permitted route exists (anti-bot block, robots rules, retired API).
    UNAVAILABLE = "unavailable"


class AttemptOutcome(str, Enum):
    """Result of one outbound LIVE fetch, recorded in collection_attempts."""

    SUCCESS = "success"
    #: The provider answered correctly but returned nothing usable.
    EMPTY = "empty"
    RATE_LIMITED = "rate_limited"
    CREDENTIALS_REJECTED = "credentials_rejected"
    PROVIDER_ERROR = "provider_error"


class TrainingStatus(str, Enum):
    """Lifecycle of a model-training run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
