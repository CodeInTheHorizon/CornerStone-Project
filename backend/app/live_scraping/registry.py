"""The single place that decides which source serves each marketplace.

Swapping a scraper for an official API or data provider means changing the
factory here to return a different `ObservationSource`; the scheduler,
storage and ML layers are untouched.
"""

from __future__ import annotations

from collections.abc import Callable

from app.config import settings
from app.live_scraping.adapters.amazon import AmazonParser
from app.live_scraping.adapters.amazon_listing import AmazonListingParser
from app.live_scraping.base import HtmlScraperSource, ObservationSource, UnavailableSource
from app.live_scraping.http_client import HttpClientConfig, PoliteHttpClient
from app.live_scraping.schemas import Marketplace


def _disabled_reason(flag: str) -> str:
    return f"Set {flag}=true to enable collection for this marketplace."


def _amazon() -> ObservationSource:
    return HtmlScraperSource(
        AmazonParser(settings.SCRAPER_AMAZON_DOMAIN),
        PoliteHttpClient(HttpClientConfig.from_settings(settings)),
        is_enabled=settings.SCRAPER_AMAZON_ENABLED,
        disabled_reason=_disabled_reason("SCRAPER_AMAZON_ENABLED"),
        listing_parser=AmazonListingParser(settings.SCRAPER_AMAZON_DOMAIN),
    )


def _flipkart() -> ObservationSource:
    return UnavailableSource(Marketplace.FLIPKART, "The Flipkart adapter is not implemented yet.")


def _meesho() -> ObservationSource:
    return UnavailableSource(Marketplace.MEESHO, "The Meesho adapter is not implemented yet.")


_FACTORIES: dict[Marketplace, Callable[[], ObservationSource]] = {
    Marketplace.AMAZON: _amazon,
    Marketplace.FLIPKART: _flipkart,
    Marketplace.MEESHO: _meesho,
}


def parse_marketplace(value: str | Marketplace) -> Marketplace:
    if isinstance(value, Marketplace):
        return value
    try:
        return Marketplace(value.strip().lower())
    except ValueError:
        raise ValueError(
            f"Unknown marketplace {value!r}; expected one of {', '.join(m.value for m in Marketplace)}."
        ) from None


def get_source(marketplace: str | Marketplace) -> ObservationSource:
    """A new source instance. The caller owns it and should `close()` it."""
    return _FACTORIES[parse_marketplace(marketplace)]()
