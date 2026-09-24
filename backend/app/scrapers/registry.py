"""Collector lookup.

The single place that maps a platform name to its collector, so adding or
replacing a marketplace touches nothing else.
"""

from __future__ import annotations

from dataclasses import replace

from app.config import settings
from app.models.enums import CollectorState, IngestionMode, Platform
from app.scrapers.alibaba import AlibabaCollector
from app.scrapers.amazon_web import AmazonWebCollector
from app.scrapers.dataforseo_amazon import DataForSEOAmazonCollector
from app.scrapers.base import CollectorStatus, MarketplaceCollector
from app.scrapers.croma import CromaCollector
from app.scrapers.flipkart import FlipkartCollector


def _amazon_collector() -> MarketplaceCollector:
    """Pick the Amazon route the operator has switched on.

    The public-page collector wins when explicitly enabled, because choosing it
    is a deliberate act; otherwise Amazon collection stays on the paid
    DataForSEO provider, which is the default supported route.
    """
    if settings.AMAZON_WEB_ENABLED:
        return AmazonWebCollector()
    return DataForSEOAmazonCollector()


_BUILDERS = {
    Platform.AMAZON: _amazon_collector,
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
        # No configuration can enable it: the endpoint is retired and the
        # replacement's terms exclude this application's use.
        return replace(state, available=False, ingestion_mode=IngestionMode.UNAVAILABLE,
                       state=CollectorState.UNAVAILABLE, reason="Amazon PA-API 5.0 is deprecated and disabled.",
                       required_configuration=())
    return state


def all_statuses() -> dict[str, CollectorStatus]:
    """Status for every platform, for GET /data/status."""
    return {
        platform.value: effective_status(_BUILDERS[platform]().status()) for platform in Platform
    }
