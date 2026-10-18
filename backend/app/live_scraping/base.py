"""The seam between MarketPulse and any one way of reading a marketplace.

`ObservationSource` is the only thing the scheduler and storage know about.
Today each marketplace's source is an `HtmlScraperSource` wrapping that
marketplace's `MarketplaceParser`. An official API or data provider replaces
it by implementing `ObservationSource.observe` and returning the same
`ProductObservation` -- nothing else in MarketPulse changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.live_scraping.errors import ParseFailedError, SourceDisabledError
from app.live_scraping.http_client import FetchedPage, PoliteHttpClient
from app.live_scraping.normalize import ParsedProduct, normalize
from app.live_scraping.schemas import Marketplace, ProductObservation


@dataclass(frozen=True)
class TargetRef:
    """Which product to observe. `product_url` is the canonical URL, not a tracking link."""

    marketplace: Marketplace
    platform_product_id: str
    product_url: str


# ------------------------------------------------------------ listing pages
#
# A listing page (search results, best-sellers) shows many products at once,
# so one request yields many observations -- with fewer fields than a product
# page (typically no seller or model). Fields a page does not show stay None.


class ListingKind(str, Enum):
    SEARCH = "search"
    BESTSELLERS = "bestsellers"


@dataclass(frozen=True)
class ListingRef:
    marketplace: Marketplace
    kind: ListingKind
    #: Canonical page-1 URL, without session or tracking parameters.
    url: str


@dataclass(frozen=True)
class ListingItem:
    platform_product_id: str
    parsed: ParsedProduct
    #: Position on the list (best-seller rank, or search position), when known.
    rank: int | None = None
    sponsored: bool | None = None


@dataclass(frozen=True)
class ParsedListing:
    items: tuple[ListingItem, ...]
    has_next_page: bool = False


@dataclass(frozen=True)
class ObservedListingItem:
    observation: ProductObservation
    rank: int | None
    sponsored: bool | None


@dataclass(frozen=True)
class ListingResult:
    items: tuple[ObservedListingItem, ...]
    has_next_page: bool
    #: Cards dropped because they could not be normalized, with the reason.
    skipped: tuple[str, ...] = ()


class ObservationSource(ABC):
    marketplace: Marketplace
    #: Stored on every observation and attempt, e.g. "amazon-html/1".
    source_name: str

    @abstractmethod
    def enabled(self) -> tuple[bool, str | None]:
        """(enabled, reason-if-not). Must not perform I/O."""

    @abstractmethod
    def resolve(self, url_or_id: str) -> TargetRef:
        """Turn a pasted URL or bare product id into a canonical target. Raises ValueError."""

    @abstractmethod
    def observe(self, target: TargetRef) -> ProductObservation:
        """Collect one fresh observation. Raises a ScrapeError subclass; never returns invented data."""

    # Listing pages are optional: a source that cannot read them keeps these defaults.

    def supports_listings(self) -> bool:
        return False

    def resolve_listing(self, kind: ListingKind, query_or_url: str) -> ListingRef:
        raise ValueError(f"{self.marketplace.value} does not support listing pages.")

    def observe_listing(self, ref: ListingRef, page_number: int = 1) -> ListingResult:
        raise SourceDisabledError(f"{self.marketplace.value} does not support listing pages.")

    def close(self) -> None:  # noqa: B027 - optional hook
        pass


class MarketplaceParser(ABC):
    """Everything marketplace-specific about reading one product page. Pure: no I/O."""

    marketplace: Marketplace
    #: Bump when parsing changes in a way that could shift values, so history
    #: before and after the change can be told apart.
    parser_version: str

    @abstractmethod
    def extract_product_id(self, url_or_id: str) -> str | None: ...

    @abstractmethod
    def product_url(self, platform_product_id: str) -> str: ...

    @abstractmethod
    def detect_block(self, page: FetchedPage) -> str | None:
        """A reason string when the page is a CAPTCHA, bot wall or sign-in wall."""

    @abstractmethod
    def parse(self, page: FetchedPage) -> ParsedProduct:
        """Raise ProductNotFoundError, JavaScriptRenderedError or ParseFailedError when appropriate."""


class ListingParser(ABC):
    """Marketplace-specific reading of listing pages. Pure: no I/O."""

    marketplace: Marketplace
    parser_version: str

    @abstractmethod
    def listing_ref(self, kind: ListingKind, query_or_url: str) -> ListingRef:
        """Canonical listing for a keyword or a pasted listing URL. Raises ValueError."""

    @abstractmethod
    def page_url(self, ref: ListingRef, page_number: int) -> str: ...

    @abstractmethod
    def detect_block(self, page: FetchedPage) -> str | None: ...

    @abstractmethod
    def parse_listing(self, page: FetchedPage, kind: ListingKind) -> ParsedListing:
        """Raise ParseFailedError when the page has no recognisable listing at all."""


class HtmlScraperSource(ObservationSource):
    def __init__(
        self,
        parser: MarketplaceParser,
        client: PoliteHttpClient,
        *,
        is_enabled: bool,
        disabled_reason: str | None = None,
        listing_parser: ListingParser | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.parser = parser
        self.listing_parser = listing_parser
        self.listing_source_name = (
            f"{parser.marketplace.value}-listing/{listing_parser.parser_version}" if listing_parser else None
        )
        self.marketplace = parser.marketplace
        self.source_name = f"{parser.marketplace.value}-html/{parser.parser_version}"
        self._client = client
        self._enabled = is_enabled
        self._disabled_reason = disabled_reason
        self._now = now

    def enabled(self) -> tuple[bool, str | None]:
        return (True, None) if self._enabled else (False, self._disabled_reason)

    def resolve(self, url_or_id: str) -> TargetRef:
        product_id = self.parser.extract_product_id(url_or_id.strip())
        if not product_id:
            raise ValueError(f"Not a recognisable {self.marketplace.value} product URL or id: {url_or_id!r}")
        return TargetRef(self.marketplace, product_id, self.parser.product_url(product_id))

    def observe(self, target: TargetRef) -> ProductObservation:
        ok, reason = self.enabled()
        if not ok:
            raise SourceDisabledError(reason or f"{self.marketplace.value} collection is disabled.")
        page = self._client.get(target.product_url, detect_block=self.parser.detect_block)
        collected_at = self._now()
        parsed = self.parser.parse(page)
        return normalize(
            parsed,
            marketplace=self.marketplace,
            platform_product_id=target.platform_product_id,
            product_url=target.product_url,
            collected_at=collected_at,
            source=self.source_name,
        )

    def supports_listings(self) -> bool:
        return self.listing_parser is not None

    def resolve_listing(self, kind: ListingKind, query_or_url: str) -> ListingRef:
        if self.listing_parser is None:
            return super().resolve_listing(kind, query_or_url)
        return self.listing_parser.listing_ref(kind, query_or_url)

    def observe_listing(self, ref: ListingRef, page_number: int = 1) -> ListingResult:
        ok, reason = self.enabled()
        if not ok:
            raise SourceDisabledError(reason or f"{self.marketplace.value} collection is disabled.")
        if self.listing_parser is None:
            return super().observe_listing(ref, page_number)

        url = self.listing_parser.page_url(ref, page_number)
        page = self._client.get(url, detect_block=self.listing_parser.detect_block)
        collected_at = self._now()
        parsed = self.listing_parser.parse_listing(page, ref.kind)

        observed: list[ObservedListingItem] = []
        skipped: list[str] = []
        seen: set[str] = set()
        for item in parsed.items:
            if item.platform_product_id in seen:
                continue  # the same product as an ad and an organic result
            seen.add(item.platform_product_id)
            try:
                observation = normalize(
                    item.parsed,
                    marketplace=self.marketplace,
                    platform_product_id=item.platform_product_id,
                    product_url=self.parser.product_url(item.platform_product_id),
                    collected_at=collected_at,
                    source=self.listing_source_name,
                )
            except ParseFailedError as exc:
                skipped.append(f"{item.platform_product_id}: {exc}")
                continue
            observed.append(ObservedListingItem(observation, item.rank, item.sponsored))
        return ListingResult(tuple(observed), parsed.has_next_page, tuple(skipped))

    def close(self) -> None:
        self._client.close()


class UnavailableSource(ObservationSource):
    """A marketplace with no working adapter yet. Makes no requests."""

    def __init__(self, marketplace: Marketplace, reason: str) -> None:
        self.marketplace = marketplace
        self.source_name = f"{marketplace.value}-unavailable"
        self._reason = reason

    def enabled(self) -> tuple[bool, str | None]:
        return False, self._reason

    def resolve(self, url_or_id: str) -> TargetRef:
        raise ValueError(self._reason)

    def observe(self, target: TargetRef) -> ProductObservation:
        raise SourceDisabledError(self._reason)
