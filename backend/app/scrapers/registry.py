"""Collector lookup.

The single place that maps a platform name to its collector, so adding or
replacing a marketplace touches nothing else.
"""

from __future__ import annotations

from dataclasses import replace

from app.models.enums import CollectorState, IngestionMode, Platform
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


#: Verified 2026-09-14 against Amazon's Creators API documentation and
#: Associates Program Policies. See docs/MARKETPLACE_SOURCES.md.
AMAZON_POLICY_REASON = (
    "The existing Amazon collector uses PA-API 5, which Amazon deprecated and retired on "
    "15 May 2026. Its replacement, the Creators API, needs new OAuth credentials and 10 "
    "qualified referral sales in the trailing 30 days, and Amazon's policies forbid using it to aggregate or analyse "
    "product data, in tools for Amazon sellers, or to train machine-learning models without "
    "Amazon's express written approval. No LIVE Amazon collection is enabled."
)


def effective_status(state: CollectorStatus) -> CollectorStatus:
    """One availability policy for the API and analytics refresh controls."""
    if "Product Advertising API 5.0" in state.access_method:
        # No configuration can enable it: the endpoint is retired and the
        # replacement's terms exclude this application's use.
        return replace(state, available=False, ingestion_mode=IngestionMode.UNAVAILABLE,
                       state=CollectorState.UNAVAILABLE, reason=AMAZON_POLICY_REASON,
                       required_configuration=())
    return state


def all_statuses() -> dict[str, CollectorStatus]:
    """Status for every platform, for GET /data/status."""
    return {
        platform.value: effective_status(_BUILDERS[platform]().status()) for platform in Platform
    }
