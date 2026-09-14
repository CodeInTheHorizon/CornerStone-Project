"""Marketplace data collectors.

Collectors must use officially permitted access paths only. They must never
bypass CAPTCHAs, authentication, anti-bot protections or robots rules. A
platform that cannot be collected from reports an explicit unavailable status
instead of returning fabricated or empty-looking results.
"""

from app.scrapers.base import (
    CollectionOutcome,
    CollectorCredentialsRejectedError,
    CollectorError,
    CollectorProviderError,
    CollectorRateLimitedError,
    CollectorRequestError,
    CollectorStatus,
    CollectorUnavailableError,
    MarketplaceCollector,
    NormalizedRecord,
    UnavailableCollector,
)
from app.scrapers.registry import (
    UnknownPlatformError,
    all_statuses,
    get_collector,
    supported_platforms,
)

__all__ = [
    "CollectionOutcome",
    "CollectorCredentialsRejectedError",
    "CollectorError",
    "CollectorProviderError",
    "CollectorRateLimitedError",
    "CollectorRequestError",
    "CollectorStatus",
    "CollectorUnavailableError",
    "MarketplaceCollector",
    "NormalizedRecord",
    "UnavailableCollector",
    "UnknownPlatformError",
    "all_statuses",
    "get_collector",
    "supported_platforms",
]
