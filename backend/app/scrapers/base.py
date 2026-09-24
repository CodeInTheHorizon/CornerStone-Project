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

from app.models.enums import AttemptOutcome, CollectorState, IngestionMode, Platform


class CollectorError(Exception):
    """Base class for collection failures."""


class CollectorUnavailableError(CollectorError):
    """The platform cannot be collected from.

    Raised instead of returning empty or invented results, so an unsupported
    source is always visible as such rather than looking like a source that
    simply found nothing.
    """


class CollectorRequestError(CollectorError):
    """The upstream request failed (network, timeout, or an error response).

    `code` is a short machine-readable reason ("timeout", "http_503",
    "malformed_response"). Messages must never contain credentials or raw
    provider bodies.
    """

    outcome: AttemptOutcome = AttemptOutcome.PROVIDER_ERROR

    def __init__(self, message: str, *, code: str = "provider_error", http_status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class CollectorProviderError(CollectorRequestError):
    """The provider failed: timeout, network error, 5xx, other 4xx or a bad payload."""


class CollectorCredentialsRejectedError(CollectorRequestError):
    """The provider refused the configured credentials (HTTP 401/403)."""

    outcome = AttemptOutcome.CREDENTIALS_REJECTED


class CollectorRateLimitedError(CollectorRequestError):
    """The provider throttled the request (HTTP 429).

    `retry_after_seconds` is how long the provider asked callers to wait, when
    it said; collection is refused until then rather than retried in a loop.
    """

    outcome = AttemptOutcome.RATE_LIMITED

    def __init__(self, message: str, *, retry_after_seconds: float | None = None, code: str = "http_429", http_status: int | None = 429) -> None:
        super().__init__(message, code=code, http_status=http_status)
        self.retry_after_seconds = retry_after_seconds


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

    # Images
    image_url: str | None = None
    image_urls: list[str] | None = None

    # Alibaba-specific wholesale fields
    min_order_qty: int | None = None
    price_min: float | None = None
    price_max: float | None = None
    supplier_years: int | None = None

    # Competition
    seller_count: int | None = None
    offer_count: int | None = None

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

    def dedupe_key(self, *, include_timestamp: bool = False) -> str:
        """Identity used to drop duplicates inside one batch.

        Falls back to the listing URL, then the product name, when the
        platform exposes no stable identifier.

        `include_timestamp` distinguishes the two kinds of batch:

        * A **live collection run** observes each listing once, so identity
          alone is the right key -- the same listing appearing twice in the
          results is a genuine duplicate.
        * An **imported or demo dataset** may legitimately contain the same
          listing on many dates. That is the whole point of a time series, so
          the timestamp has to be part of the key or the history collapses to
          a single row.
        """
        identity = self.external_id or self.listing_url or self.product_name
        key = f"{self.platform}:{identity.strip().lower()}"
        if include_timestamp:
            key = f"{key}@{self.collection_timestamp.isoformat()}"
        return key


@dataclass(frozen=True)
class CollectorStatus:
    """Whether a collector can run right now, and why not if it cannot."""

    platform: str
    available: bool
    access_method: str
    #: How this platform's data would reach the system if it were working.
    ingestion_mode: IngestionMode = IngestionMode.UNAVAILABLE
    reason: str | None = None
    requires_credentials: bool = False
    #: Environment variables an operator must set to make this collector work.
    #: Empty when no configuration would help (a hard block, not a missing key).
    required_configuration: tuple[str, ...] = ()
    #: Finer-grained reason than `available`. Defaults from `available` so
    #: existing collectors need not set it.
    state: CollectorState | None = None
    #: Stable provider identifier recorded with every LIVE fetch.
    provider: str | None = None

    def __post_init__(self) -> None:
        if self.state is None:
            object.__setattr__(
                self, "state", CollectorState.LIVE if self.available else CollectorState.UNAVAILABLE
            )


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
        required_configuration: tuple[str, ...] = (),
    ) -> None:
        self.platform = platform
        self.access_method = access_method
        self._reason = reason
        self._requires_credentials = requires_credentials
        self._required_configuration = required_configuration

    def status(self) -> CollectorStatus:
        return CollectorStatus(
            platform=self.platform.value,
            available=False,
            access_method=self.access_method,
            ingestion_mode=IngestionMode.UNAVAILABLE,
            reason=self._reason,
            requires_credentials=self._requires_credentials,
            required_configuration=self._required_configuration,
        )

    def collect(
        self,
        keyword: str,
        category: str | None = None,
        max_items: int = 20,
    ) -> CollectionOutcome:
        raise CollectorUnavailableError(self._reason)
