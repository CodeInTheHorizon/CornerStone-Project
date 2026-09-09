"""Common marketplace collector interface.

Every platform module implements `MarketplaceCollector` and returns
`NormalizedRecord`s, so the storage, validation and API layers never need to
know which marketplace produced a row.

Platform-specific request building and parsing stays inside the platform
module. Nothing here knows about HTML, selectors or vendor payload shapes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.models.enums import Platform


class CollectorError(Exception):
    """Base class for collection failures."""


class CollectorUnavailableError(CollectorError):
    """The platform cannot be collected from.

    Raised instead of returning empty or invented results, so an unsupported
    source is always visible as such rather than looking like a source that
    simply found nothing.
    """


class CollectorRequestError(CollectorError):
    """The upstream request failed (network, timeout, or an error response)."""


@dataclass(frozen=True)
class NormalizedRecord:
    """One marketplace observation, in the shared schema.

    Every optional field defaults to None. A collector must leave a field None
    when the source does not expose it -- never substitute a guess.
    """

    platform: str
    product_name: str

    # Identity
    brand: str | None = None
    category: str | None = None
    subcategory: str | None = None
    external_id: str | None = None

    # Pricing
    price: float | None = None
    original_price: float | None = None
    discount_percentage: float | None = None
    currency: str = "INR"

    # Social proof
    rating: float | None = None
    review_count: int | None = None

    # Availability / seller
    availability: str | None = None
    seller_name: str | None = None
    listing_url: str | None = None

    # Optional extras, stored as JSON metadata
    shipping_info: str | None = None
    delivery_time: str | None = None
    badge: str | None = None
    sponsored: bool | None = None
    specifications: dict[str, Any] | None = None
    stock_status: str | None = None

    collection_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def dedupe_key(self) -> str:
        """Identity used to drop duplicates inside one collection run.

        Falls back to the listing URL, then the product name, when the
        platform exposes no stable identifier.
        """
        identity = self.external_id or self.listing_url or self.product_name
        return f"{self.platform}:{identity.strip().lower()}"


@dataclass(frozen=True)
class CollectorStatus:
    """Whether a collector can run right now, and why not if it cannot."""

    platform: str
    available: bool
    access_method: str
    reason: str | None = None
    requires_credentials: bool = False


@dataclass
class CollectionOutcome:
    """What a single collection call produced."""

    records: list[NormalizedRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MarketplaceCollector(ABC):
    """Base class for every platform collector."""

    #: Which marketplace this collector serves.
    platform: Platform
    #: How data is obtained, e.g. "Official API (PA-API 5.0)". Shown in status.
    access_method: str

    @abstractmethod
    def status(self) -> CollectorStatus:
        """Report whether this collector can run, without performing I/O."""

    @abstractmethod
    def collect(
        self,
        keyword: str,
        category: str | None = None,
        max_items: int = 20,
    ) -> CollectionOutcome:
        """Collect up to `max_items` listings matching `keyword`.

        Raises CollectorUnavailableError when the platform is not supported or
        is not configured, and CollectorRequestError when the upstream call
        fails. Never returns fabricated records.
        """


class UnavailableCollector(MarketplaceCollector):
    """A platform that cannot currently be collected from.

    Used where public collection would require defeating an anti-bot control,
    or where the site's robots rules disallow the search paths. These are
    deliberately inert: they document the blocker rather than attempting to
    work around it.
    """

    def __init__(
        self,
        platform: Platform,
        reason: str,
        access_method: str = "Not available",
        requires_credentials: bool = False,
    ) -> None:
        self.platform = platform
        self.access_method = access_method
        self._reason = reason
        self._requires_credentials = requires_credentials

    def status(self) -> CollectorStatus:
        return CollectorStatus(
            platform=self.platform.value,
            available=False,
            access_method=self.access_method,
            reason=self._reason,
            requires_credentials=self._requires_credentials,
        )

    def collect(
        self,
        keyword: str,
        category: str | None = None,
        max_items: int = 20,
    ) -> CollectionOutcome:
        raise CollectorUnavailableError(self._reason)
