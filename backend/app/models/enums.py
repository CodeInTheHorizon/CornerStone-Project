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


class DataSource(str, Enum):
    """Provenance of a stored record.

    Every persisted observation must declare whether it came from a real
    collection run or from the bundled demo dataset, so that demo rows can
    never be presented as live marketplace data.
    """

    LIVE = "live"
    DEMO = "demo"


class TrainingStatus(str, Enum):
    """Lifecycle of a model-training run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
