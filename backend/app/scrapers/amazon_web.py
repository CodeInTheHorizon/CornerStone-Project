"""Amazon search-results collector, parsing the public product listing pages.

Port of the cheerio-based scraper documented in the MarketPulse dashboard's
CLAUDE.md, adapted to this backend's `MarketplaceCollector` contract.

Two differences from that original are load-bearing:

* The dashboard scraper reads **one product page** given its URL. This
  interface is keyword-search based, so this collector parses the search
  results page (`/s?k=<keyword>`) and normalizes each result card instead.
* The original forced USD via `i18n-prefs`. This project targets amazon.in and
  stores INR, so the domain, currency and locale are configurable and default
  to the Indian marketplace.

Gating (see `status`): this collector stays inert unless the operator sets
AMAZON_WEB_ENABLED. Amazon's Conditions of Use restrict automated collection,
and the registry's other Amazon routes are deliberately disabled, so running
this is an explicit operator decision rather than a default.

Parsing is defensive throughout: Amazon ships several price layouts
simultaneously and changes them without notice, so price extraction tries
structured markup first and falls back through progressively weaker
strategies, capping every result at a sane maximum so a mis-parse surfaces as
a missing price rather than an invented one.
"""

from __future__ import annotations

import html as html_entities
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.models.enums import CollectorState, IngestionMode, Platform
from app.scrapers.base import (
    CollectionOutcome,
    CollectorProviderError,
    CollectorRateLimitedError,
    CollectorStatus,
    CollectorUnavailableError,
    MarketplaceCollector,
    NormalizedRecord,
)
from app.scrapers.parsing import (
    clean_text,
    compute_discount,
    extract_brand,
    normalize_url,
    parse_rating,
    parse_review_count,
)

PROVIDER = "amazon-public-search"

REQUIRED_CONFIGURATION = ("AMAZON_WEB_ENABLED",)

#: Attempts per collection for retryable failures (timeouts, network, 5xx).
MAX_ATTEMPTS = 3
#: Exponential backoff base between retryable attempts, in seconds.
BACKOFF_SECONDS = 1.0
#: Cooldown recorded when Amazon throttles or serves a bot challenge.
BLOCK_COOLDOWN_SECONDS = 300.0

#: Upper bound on any parsed price. Amazon embeds timestamps, widget ids and
#: other large integers in inline scripts; without a ceiling those leak through
#: the weaker extraction tiers as absurd prices. Sized for INR (a laptop is
#: routinely six figures), so it is deliberately far above USD expectations.
MAX_SANE_PRICE = 2_000_000.0

#: Mobile pages server-render more of the price block than desktop ones, so it
#: is tried first; desktop is the fallback when mobile yields nothing.
_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36"
)
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

_BOT_CHALLENGE_MARKERS = (
    "enter the characters you see below",
    "api-services-support@amazon.com",
    "to discuss automated access",
)

# Search result cards. Amazon ships several card markups concurrently.
_RESULT_CARD = re.compile(
    r'<div[^>]+data-component-type="s-search-result"[^>]*>', re.IGNORECASE
)
_ASIN_ATTR = re.compile(r'data-asin="([A-Z0-9]{10})"', re.IGNORECASE)

# Price: the composite whole+fraction spans are the only reliable source on
# current layouts -- `.a-offscreen` frequently omits the decimal separator,
# which is what produced "$4999" instead of "$49.99" in the original scraper.
_PRICE_WHOLE = re.compile(
    r'<span class="a-price-whole">([\d,.\s]+)', re.IGNORECASE
)
_PRICE_FRACTION = re.compile(
    r'<span class="a-price-fraction">(\d+)</span>', re.IGNORECASE
)
_PRICE_OFFSCREEN = re.compile(
    r'<span class="a-offscreen">\s*([^<]+?)\s*</span>', re.IGNORECASE
)
# The struck-through "M.R.P." price. The class list carries extra modifiers
# (`puis-light-weight-text`), so the match must not anchor on the closing quote.
_PRICE_STRIKE = re.compile(
    r'<span class="[^"]*a-text-price[^"]*"[^>]*>\s*<span class="a-offscreen">\s*([^<]+?)\s*</span>',
    re.IGNORECASE,
)

_TITLE = re.compile(
    r'<h2[^>]*>(?:\s*<a[^>]*>)?\s*(?:<span[^>]*>)?\s*([^<]{3,400}?)\s*</span>',
    re.IGNORECASE | re.DOTALL,
)
_TITLE_FALLBACK = re.compile(
    r'<span class="a-size-medium a-color-base a-text-normal"[^>]*>\s*([^<]{3,400}?)\s*</span>',
    re.IGNORECASE,
)
_LINK = re.compile(r'<a[^>]+class="[^"]*a-link-normal[^"]*"[^>]+href="([^"]+)"', re.IGNORECASE)
_RATING = re.compile(r'([\d.]+)\s+out of\s+5\s+stars', re.IGNORECASE)
# Read the count from aria-label, not the visible text: the latter is
# abbreviated ("(1.1K)") and would round 1,119 ratings down to 1,100.
_REVIEWS = re.compile(r'aria-label="([\d,]+)\s+ratings?"', re.IGNORECASE)
_IMAGE = re.compile(r'<img[^>]+(?:src|data-src)="(https://[^"]+(?:images-amazon|m\.media-amazon)[^"]+)"', re.IGNORECASE)
_SPONSORED = re.compile(r'>\s*Sponsored\s*<', re.IGNORECASE)
_TAG_STRIP = re.compile(r"<[^>]+>")

_AVAILABILITY_PATTERNS = (
    (re.compile(r"currently unavailable|not available", re.IGNORECASE), "Currently unavailable"),
    (re.compile(r"temporarily out of stock", re.IGNORECASE), "Temporarily out of stock"),
    (re.compile(r"only (\d+) left", re.IGNORECASE), None),  # message built from the match
    (re.compile(r"in stock", re.IGNORECASE), "In stock"),
)


def _parse_price(raw: object) -> float | None:
    """Extract a price, rejecting anything implausible rather than guessing.

    Strips currency codes/symbols and thousands separators before parsing, and
    discards values at or below zero or above `MAX_SANE_PRICE`. Returns None on
    anything it cannot read -- a missing price must stay missing.
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if 0 < value <= MAX_SANE_PRICE else None
    if not isinstance(raw, str):
        return None

    # Entities first: Amazon serves the rupee sign as both a literal "₹" and as
    # "&#8377;", and an undecoded entity parses as the number 8377.
    text = html_entities.unescape(raw).strip()
    if not text:
        return None

    # Order matters: the alphabetic code ("INR", "USD") is stripped before the
    # symbol, then separators, so "INR 1,29,900.00" reduces cleanly.
    text = re.sub(r"^[A-Z]{2,3}\s*", "", text)
    text = re.sub(r"^[\s$₹€£¥]+", "", text)
    text = text.replace(",", "").replace("\xa0", "").strip()

    match = re.search(r"\d+(?:\.\d{1,2})?", text)
    if match is None:
        return None
    try:
        value = float(match.group(0))
    except ValueError:
        return None
    return value if 0 < value <= MAX_SANE_PRICE else None


def _composite_price(fragment: str) -> float | None:
    """Rebuild a price from Amazon's split whole/fraction spans.

    Amazon renders "1,299.00" as a `a-price-whole` span holding "1,299" and an
    `a-price-fraction` span holding "00". Reading either alone loses the
    decimal placement, which is the single most common source of wrong prices.
    """
    whole_match = _PRICE_WHOLE.search(fragment)
    if whole_match is None:
        return None
    whole = re.sub(r"[^\d]", "", whole_match.group(1))
    if not whole:
        return None
    fraction_match = _PRICE_FRACTION.search(fragment)
    fraction = fraction_match.group(1)[:2] if fraction_match else "00"
    return _parse_price(f"{whole}.{fraction}")


def _availability(fragment: str) -> str | None:
    """Read a stock message out of a result card, when it states one."""
    text = _TAG_STRIP.sub(" ", fragment)
    for pattern, message in _AVAILABILITY_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        if message is not None:
            return message
        return f"Only {match.group(1)} left in stock"
    return None


def _split_cards(html: str) -> list[str]:
    """Split the search page into one fragment per result card."""
    starts = [m.start() for m in _RESULT_CARD.finditer(html)]
    if not starts:
        return []
    bounds = starts + [len(html)]
    return [html[bounds[i] : bounds[i + 1]] for i in range(len(starts))]


class AmazonWebCollector(MarketplaceCollector):
    """Collects Amazon listings by parsing the public search results page."""

    platform = Platform.AMAZON
    access_method = "Public search results page (HTML parsing)"

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        domain: str | None = None,
        currency: str | None = None,
        locale: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.enabled = settings.AMAZON_WEB_ENABLED if enabled is None else enabled
        self.domain = (settings.AMAZON_WEB_DOMAIN if domain is None else domain).strip().rstrip("/")
        self.currency = (settings.AMAZON_WEB_CURRENCY if currency is None else currency).strip().upper()
        self.locale = (settings.AMAZON_WEB_LOCALE if locale is None else locale).strip()
        self.timeout = settings.AMAZON_WEB_TIMEOUT_SECONDS if timeout is None else timeout
        # Injectable so tests exercise the real request/parse path against a
        # mock transport instead of hitting Amazon.
        self.client = client
        self.sleep = sleep

    # -- status ------------------------------------------------------------

    def status(self) -> CollectorStatus:
        common = dict(
            platform=self.platform.value,
            access_method=self.access_method,
            ingestion_mode=IngestionMode.LIVE_PUBLIC_SOURCE,
            requires_credentials=False,
            provider=PROVIDER,
            required_configuration=REQUIRED_CONFIGURATION,
        )
        if not self.enabled:
            return CollectorStatus(
                **common,
                available=False,
                state=CollectorState.APPROVAL_REQUIRED,
                reason=(
                    "Amazon public-page collection is disabled. Amazon's Conditions "
                    "of Use restrict automated collection, so set AMAZON_WEB_ENABLED=true "
                    "only if you have confirmed this use is permitted for your account "
                    "and region."
                ),
            )
        return CollectorStatus(**common, available=True, state=CollectorState.LIVE)

    # -- collection --------------------------------------------------------

    def _headers(self, mobile: bool) -> dict[str, str]:
        return {
            "User-Agent": _MOBILE_UA if mobile else _DESKTOP_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": f"{self.locale},en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            # Pins currency and locale so a geo-routed response does not silently
            # return a different currency than the one recorded on the record.
            "Cookie": f"i18n-prefs={self.currency}; lc-main={self.locale.replace('-', '_')}",
        }

    def _fetch(self, client: httpx.Client, keyword: str, mobile: bool) -> str:
        url = f"https://{self.domain}/s"
        last_error: Exception | None = None

        for attempt in range(MAX_ATTEMPTS):
            try:
                response = client.get(
                    url,
                    params={"k": keyword},
                    headers=self._headers(mobile),
                    timeout=self.timeout,
                    follow_redirects=True,
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < MAX_ATTEMPTS - 1:
                    self.sleep(BACKOFF_SECONDS * (2**attempt))
                    continue
                raise CollectorProviderError("Amazon request timed out.", code="timeout") from exc
            except httpx.HTTPError as exc:
                raise CollectorProviderError(
                    f"Could not reach Amazon ({type(exc).__name__}).", code="network_error"
                ) from exc

            if response.status_code == 429:
                raise CollectorRateLimitedError(
                    "Amazon rate-limited the request (HTTP 429).",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                )
            if response.status_code == 503:
                # Amazon serves 503 for its bot challenge, not as a transient
                # server fault; retrying harder is exactly the wrong response.
                raise CollectorRateLimitedError(
                    "Amazon returned HTTP 503 (automated-access challenge).",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                    code="http_503",
                    http_status=503,
                )
            if response.status_code >= 500:
                last_error = CollectorProviderError(
                    f"Amazon server error (HTTP {response.status_code}).",
                    code=f"http_{response.status_code}",
                    http_status=response.status_code,
                )
                if attempt < MAX_ATTEMPTS - 1:
                    self.sleep(BACKOFF_SECONDS * (2**attempt))
                    continue
                raise last_error
            if response.status_code >= 400:
                raise CollectorProviderError(
                    f"Amazon refused the request (HTTP {response.status_code}).",
                    code=f"http_{response.status_code}",
                    http_status=response.status_code,
                )

            html = response.text
            lowered = html[:4000].lower()
            if any(marker in lowered for marker in _BOT_CHALLENGE_MARKERS):
                raise CollectorRateLimitedError(
                    "Amazon served a bot challenge instead of results.",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                    code="bot_challenge",
                )
            return html

        raise CollectorProviderError(
            f"Amazon request failed: {last_error}", code="provider_error"
        )

    def collect(
        self,
        keyword: str,
        category: str | None = None,
        max_items: int = 20,
    ) -> CollectionOutcome:
        state = self.status()
        if not state.available:
            raise CollectorUnavailableError(state.reason or "Not configured.")

        limit = min(max(1, max_items), 60)
        client = self.client or httpx.Client(timeout=self.timeout)
        own_client = self.client is None
        try:
            html = self._fetch(client, keyword, mobile=True)
            cards = _split_cards(html)
            # Mobile markup occasionally renders no parsable cards; the desktop
            # layout is the documented fallback rather than a second guess.
            if not cards:
                html = self._fetch(client, keyword, mobile=False)
                cards = _split_cards(html)
        finally:
            if own_client:
                client.close()

        outcome = CollectionOutcome()
        if not cards:
            outcome.warnings.append(f"No parsable Amazon results for '{keyword}'.")
            return outcome

        fetched_at = datetime.now(timezone.utc)
        for rank, card in enumerate(cards, start=1):
            record = self._to_record(card, category, rank, fetched_at, outcome.warnings)
            if record is not None:
                outcome.records.append(record)
            if len(outcome.records) >= limit:
                break

        if not outcome.records:
            outcome.warnings.append(
                f"Amazon returned {len(cards)} results for '{keyword}', none parsable."
            )
        return outcome

    # -- normalization -----------------------------------------------------

    def _to_record(
        self,
        card: str,
        category: str | None,
        rank: int,
        fetched_at: datetime,
        warnings: list[str],
    ) -> NormalizedRecord | None:
        """Map one search result card onto the shared schema.

        Returns None (with a warning) rather than raising when a card cannot be
        read: one changed card must not abort an otherwise good run.
        """
        try:
            title_match = _TITLE.search(card) or _TITLE_FALLBACK.search(card)
            title = (
                clean_text(html_entities.unescape(title_match.group(1)))
                if title_match
                else None
            )
            if not title:
                warnings.append("Skipped an Amazon result with no readable title.")
                return None

            asin_match = _ASIN_ATTR.search(card)
            asin = asin_match.group(1) if asin_match else None

            # Composite spans first; `.a-offscreen` only as a fallback, since it
            # is the layout that loses decimal placement.
            price = _composite_price(card)
            if price is None:
                offscreen = _PRICE_OFFSCREEN.search(card)
                if offscreen is not None:
                    price = _parse_price(offscreen.group(1))

            strike = _PRICE_STRIKE.search(card)
            original_price = _parse_price(strike.group(1)) if strike else None
            # A "was" price below the current price means the two spans were
            # mismatched, so the comparison is dropped rather than recorded.
            if original_price is not None and price is not None and original_price < price:
                original_price = None

            rating_match = _RATING.search(card)
            rating = parse_rating(rating_match.group(1)) if rating_match else None

            reviews_match = _REVIEWS.search(card)
            review_count = parse_review_count(reviews_match.group(1)) if reviews_match else None

            link_match = _LINK.search(card)
            listing_url = None
            if link_match:
                listing_url = normalize_url(link_match.group(1), base=f"https://{self.domain}")
            if listing_url is None and asin:
                listing_url = f"https://{self.domain}/dp/{asin}"

            availability = _availability(card)

            image_match = _IMAGE.search(card)
            image_url = image_match.group(1) if image_match else None

            return NormalizedRecord(
                platform=self.platform.value,
                product_name=title,
                brand=extract_brand(None, title),
                category=clean_text(category, 120),
                external_id=asin,
                image_url=image_url,
                price=price,
                original_price=original_price,
                discount_percentage=compute_discount(price, original_price),
                currency=self.currency,
                rating=rating,
                review_count=review_count,
                availability=availability,
                seller_name=None,
                listing_url=listing_url,
                sponsored=bool(_SPONSORED.search(card)),
                specifications={"search_rank": rank},
                stock_status=availability,
                collection_timestamp=fetched_at,
            )
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            warnings.append(f"Skipped an Amazon result that could not be parsed: {exc}")
            return None
