"""Collector lookup.

The single place that maps a platform name to its collector, so adding or
replacing a marketplace touches nothing else.
"""

from __future__ import annotations

from dataclasses import replace

from app.models.enums import Platform, IngestionMode
from app.scrapers.alibaba import AlibabaCollector
from app.scrapers.amazon import AmazonCollector
from app.scrapers.base import CollectorStatus, MarketplaceCollector
from app.scrapers.croma import CromaCollector
from app.scrapers.flipkart import FlipkartCollector

_BUILDERS = {
    Platform.AMAZON: AmazonCollector,
    Platform.FLIPKART: FlipkartCollector,
    Platform.CROMA: CromaCollector,
    Platform.ALIBABA: AlibabaCollector,
}


class UnknownPlatformError(ValueError):
    """Raised for a platform name this system does not support."""


def supported_platforms() -> list[str]:
    return [platform.value for platform in Platform]


def get_collector(platform: str | Platform) -> MarketplaceCollector:
    """Return the collector for a platform name (case-insensitive)."""
    if isinstance(platform, Platform):
        resolved = platform
    else:
        try:
            resolved = Platform(str(platform).strip().lower())
        except ValueError:
            raise UnknownPlatformError(
                f"Unknown platform '{platform}'. "
                f"Supported: {', '.join(supported_platforms())}."
            ) from None

    return _BUILDERS[resolved]()


def effective_status(state: CollectorStatus) -> CollectorStatus:
    """One availability policy for the API and analytics refresh controls."""
    if "Product Advertising API 5.0" in state.access_method:
        return replace(state, available=False, ingestion_mode=IngestionMode.UNAVAILABLE,
                       reason="The existing Amazon collector uses deprecated PA-API 5. A supported replacement and approved API access with credentials are required.")
    return state


def all_statuses() -> dict[str, CollectorStatus]:
    """Status for every platform, for GET /data/status."""
    return {
        platform.value: effective_status(_BUILDERS[platform]().status()) for platform in Platform
    }
