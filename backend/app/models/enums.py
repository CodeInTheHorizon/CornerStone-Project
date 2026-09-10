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


class TrainingStatus(str, Enum):
    """Lifecycle of a model-training run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
