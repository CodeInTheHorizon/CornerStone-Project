"""Flipkart collector, using the official Flipkart Affiliate API (v1.0).

Why the API and not the website: flipkart.com answers programmatic requests
(even robots.txt) with a reCAPTCHA interstitial, and solving or evading it is
out of scope. The Affiliate API is Flipkart's documented programmatic route:
https://affiliate.flipkart.com/api-docs/af_prod_ref.html

Gating, in order (see `status`):

1. FLIPKART_AFFILIATE_ID and FLIPKART_AFFILIATE_TOKEN must be configured.
2. FLIPKART_DATA_USE_APPROVED must be true. Flipkart's API terms restrict use
   to "in conjunction with Flipkart's platform", forbid use "in a similar or
   competitive platform", and say nothing about retaining price history,
   analytics or machine learning. MarketPulse stores observations over time
   and compares marketplaces, so this collector refuses to run until the
   operator records that Flipkart has approved that use. Credentials alone
   are not permission.

Provider facts used here (Flipkart affiliate documentation, checked
2026-09-14): search is `GET /affiliate/1.0/search.json?query=&resultCount=`
with `Fk-Affiliate-Id` / `Fk-Affiliate-Token` headers; calls are limited to 20
per second per affiliate; results carry `productBaseInfoV1` (id, title, brand,
category path, MRP, selling/special price, discount, stock, URL) and
`productShippingInfoV1` (seller). No product star rating or review count is
exposed -- only the *seller's* ratings -- so rating and review_count stay None.
The documentation publishes no error-code table and no search pagination; the
field mapping is defensive and should be checked against the first real
response.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import settings
from app.models.enums import CollectorState, IngestionMode, Platform
from app.scrapers.base import (
    CollectionOutcome,
    CollectorCredentialsRejectedError,
    CollectorProviderError,
    CollectorRateLimitedError,
    CollectorStatus,
    CollectorUnavailableError,
    MarketplaceCollector,
    NormalizedRecord,
)
from app.scrapers.parsing import clean_text, compute_discount, normalize_url, parse_price

PROVIDER = "flipkart-affiliate-api-1.0"
SEARCH_URL = "https://affiliate-api.flipkart.net/affiliate/1.0/search.json"

CREDENTIAL_CONFIGURATION = ("FLIPKART_AFFILIATE_ID", "FLIPKART_AFFILIATE_TOKEN")
APPROVAL_CONFIGURATION = ("FLIPKART_DATA_USE_APPROVED",)

#: One search request per refresh asks for at most this many results.
MAX_RESULTS_PER_REQUEST = 10
#: Attempts per refresh for retryable failures (timeouts, network, 5xx).
MAX_ATTEMPTS = 3
#: Exponential backoff base between retryable attempts, in seconds.
BACKOFF_SECONDS = 1.0
#: A 429 asking for a longer wait than this is not waited out in-request.
MAX_INLINE_RETRY_AFTER_SECONDS = 5.0
#: Cooldown recorded when a 429 carries no usable Retry-After header.
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 60.0


def _retry_after_seconds(value: str | None) -> float | None:
    """Parse Retry-After as seconds or an HTTP date; None when absent or invalid."""
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, min(seconds, 3600.0))


def _category_from_path(value: object) -> tuple[str | None, str | None]:
    """(category, subcategory) from categoryPath/categoryPaths.

    Accepts the documented string form ("Mobiles>Headphones>Earbuds") and the
    nested form ({"categoryPath": [[{"title": ...}, ...]]}); anything else
    yields (None, None) rather than a guess.
    """
    titles: list[str] = []
    if isinstance(value, str):
        titles = [part for part in (clean_text(p, 120) for p in value.replace("/", ">").split(">")) if part]
    elif isinstance(value, dict):
        return _category_from_path(value.get("categoryPath"))
    elif isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, list):
            titles = [t for t in (clean_text(node.get("title"), 120) for node in first if isinstance(node, dict)) if t]
        elif isinstance(first, dict):
            titles = [t for t in (clean_text(node.get("title"), 120) for node in value if isinstance(node, dict)) if t]
        elif isinstance(first, str):
            titles = [t for t in (clean_text(node, 120) for node in value) if t]
    if not titles:
        return None, None
    leaf = titles[-1]
    parent = titles[-2] if len(titles) >= 2 else None
    return (parent or leaf), (leaf if parent else None)


def _amount(value: object) -> tuple[float | None, str | None]:
    if isinstance(value, dict):
        currency = value.get("currency")
        return parse_price(value.get("amount")), currency if isinstance(currency, str) and currency.strip() else None
    return parse_price(value), None


class FlipkartCollector(MarketplaceCollector):
    """Collects Flipkart listings through the Affiliate API search endpoint."""

    platform = Platform.FLIPKART
    access_method = "Official API (Flipkart Affiliate API 1.0)"

    def __init__(
        self,
        *,
        affiliate_id: str | None = None,
        affiliate_token: str | None = None,
        data_use_approved: bool | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._affiliate_id = (affiliate_id if affiliate_id is not None else settings.FLIPKART_AFFILIATE_ID).strip()
        self._affiliate_token = (
            affiliate_token if affiliate_token is not None else settings.FLIPKART_AFFILIATE_TOKEN.get_secret_value()
        ).strip()
        self.data_use_approved = settings.FLIPKART_DATA_USE_APPROVED if data_use_approved is None else data_use_approved
        self.timeout = timeout if timeout is not None else settings.FLIPKART_TIMEOUT_SECONDS
        # Injectable so tests drive the real request/parse path through a mock
        # transport and never contact Flipkart.
        self._client = client
        self._sleep = sleep

    def __repr__(self) -> str:  # never expose credentials through a repr
        return f"FlipkartCollector(configured={self.is_configured}, approved={self.data_use_approved})"

    # -- status ------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return bool(self._affiliate_id and self._affiliate_token)

    def status(self) -> CollectorStatus:
        common = dict(
            platform=self.platform.value,
            access_method=self.access_method,
            ingestion_mode=IngestionMode.LIVE_API,
            requires_credentials=True,
            provider=PROVIDER,
        )
        if not self.is_configured:
            return CollectorStatus(
                **common,
                available=False,
                state=CollectorState.CREDENTIALS_MISSING,
                reason=(
                    "Flipkart Affiliate API credentials are not configured. Set "
                    "FLIPKART_AFFILIATE_ID and FLIPKART_AFFILIATE_TOKEN from an approved "
                    "Flipkart Affiliate account (API > API Token) in the backend environment, "
                    "and FLIPKART_DATA_USE_APPROVED=true only after Flipkart confirms that "
                    "storing and analysing its data in this application is permitted."
                ),
                required_configuration=CREDENTIAL_CONFIGURATION + APPROVAL_CONFIGURATION,
            )
        if not self.data_use_approved:
            return CollectorStatus(
                **common,
                available=False,
                state=CollectorState.APPROVAL_REQUIRED,
                reason=(
                    "Flipkart credentials are configured, but LIVE collection stays disabled "
                    "until FLIPKART_DATA_USE_APPROVED=true. Flipkart's API terms limit use to "
                    "its own platform and do not cover retaining price history, cross-marketplace "
                    "analytics or model training; obtain Flipkart's written approval first."
                ),
                required_configuration=APPROVAL_CONFIGURATION,
            )
        return CollectorStatus(
            **common,
            available=True,
            state=CollectorState.LIVE,
            required_configuration=CREDENTIAL_CONFIGURATION + APPROVAL_CONFIGURATION,
        )

    # -- collection --------------------------------------------------------

    def collect(
        self,
        keyword: str,
        category: str | None = None,
        max_items: int = 20,
    ) -> CollectionOutcome:
        state = self.status()
        if not state.available:
            raise CollectorUnavailableError(state.reason or "Flipkart collector is not enabled.")

        outcome = CollectionOutcome()
        requested = max(1, min(max_items, MAX_RESULTS_PER_REQUEST))
        if max_items > MAX_RESULTS_PER_REQUEST:
            outcome.warnings.append(
                f"Flipkart search is requested with at most {MAX_RESULTS_PER_REQUEST} results per refresh; "
                f"{max_items} were asked for."
            )

        payload, fetched_at = self._get(keyword, requested)
        products = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(products, list):
            raise CollectorProviderError(
                "Flipkart returned a response without a product list.", code="malformed_response"
            )
        if not products:
            outcome.warnings.append(f"Flipkart returned no results for '{keyword}'.")
            return outcome

        for item in products:
            record = self._to_record(item, category, fetched_at, outcome.warnings)
            if record is not None:
                outcome.records.append(record)
            if len(outcome.records) >= requested:
                break
        return outcome

    def _headers(self) -> dict[str, str]:
        return {
            "Fk-Affiliate-Id": self._affiliate_id,
            "Fk-Affiliate-Token": self._affiliate_token,
            "Accept": "application/json",
        }

    def _redact(self, text: str) -> str:
        for secret in (self._affiliate_token, self._affiliate_id):
            if secret:
                text = text.replace(secret, "[redacted]")
        return text[:300]

    def _get(self, keyword: str, result_count: int) -> tuple[dict[str, Any], datetime]:
        client = self._client or httpx.Client(timeout=self.timeout)
        close_after = self._client is None
        params = {"query": keyword, "resultCount": str(result_count)}
        last_error: CollectorProviderError | None = None
        try:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                if attempt > 1:
                    self._sleep(BACKOFF_SECONDS * (2 ** (attempt - 2)))
                try:
                    response = client.get(SEARCH_URL, params=params, headers=self._headers(), timeout=self.timeout)
                except httpx.TimeoutException:
                    last_error = CollectorProviderError(
                        f"Flipkart did not respond within {self.timeout:g} seconds.", code="timeout"
                    )
                    continue
                except httpx.HTTPError as exc:
                    last_error = CollectorProviderError(
                        self._redact(f"Could not reach Flipkart ({type(exc).__name__})."), code="network_error"
                    )
                    continue

                status_code = response.status_code
                if status_code == 429:
                    wait = _retry_after_seconds(response.headers.get("Retry-After"))
                    if attempt < MAX_ATTEMPTS and wait is not None and wait <= MAX_INLINE_RETRY_AFTER_SECONDS:
                        self._sleep(wait)
                        continue
                    raise CollectorRateLimitedError(
                        "Flipkart rate-limited this affiliate account (HTTP 429). Collection is paused until "
                        "the provider's retry window passes.",
                        retry_after_seconds=wait if wait is not None else DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
                    )
                if status_code in (401, 403):
                    raise CollectorCredentialsRejectedError(
                        f"Flipkart rejected the configured affiliate credentials (HTTP {status_code}). Check "
                        "FLIPKART_AFFILIATE_ID and FLIPKART_AFFILIATE_TOKEN; generating a new token disables the old one.",
                        code=f"http_{status_code}",
                        http_status=status_code,
                    )
                if status_code >= 500:
                    last_error = CollectorProviderError(
                        f"Flipkart returned a server error (HTTP {status_code}).",
                        code=f"http_{status_code}",
                        http_status=status_code,
                    )
                    continue
                if status_code >= 400:
                    raise CollectorProviderError(
                        f"Flipkart refused the search request (HTTP {status_code}).",
                        code=f"http_{status_code}",
                        http_status=status_code,
                    )
                try:
                    payload = response.json()
                except ValueError:
                    raise CollectorProviderError(
                        "Flipkart returned a response that is not valid JSON.", code="malformed_response",
                        http_status=status_code,
                    ) from None
                if not isinstance(payload, dict):
                    raise CollectorProviderError(
                        "Flipkart returned an unexpected JSON shape.", code="malformed_response",
                        http_status=status_code,
                    )
                return payload, datetime.now(timezone.utc)
        finally:
            if close_after:
                client.close()
        assert last_error is not None
        raise last_error

    # -- normalization -----------------------------------------------------

    def _to_record(
        self,
        item: object,
        category: str | None,
        fetched_at: datetime,
        warnings: list[str],
    ) -> NormalizedRecord | None:
        """Map one search result onto the shared schema; unknown values stay None."""
        if not isinstance(item, dict):
            warnings.append("Skipped a Flipkart result that was not an object.")
            return None
        base = item.get("productBaseInfoV1")
        if not isinstance(base, dict):
            warnings.append("Skipped a Flipkart result without productBaseInfoV1.")
            return None

        title = clean_text(base.get("title"))
        if not title:
            warnings.append("Skipped a Flipkart result with no title.")
            return None

        mrp, mrp_currency = _amount(base.get("maximumRetailPrice"))
        special, special_currency = _amount(base.get("flipkartSpecialPrice"))
        selling, selling_currency = _amount(base.get("flipkartSellingPrice"))
        # The special price includes extra offers; fall back to the selling price.
        price = special if special is not None else selling
        currency = (special_currency if special is not None else selling_currency) or mrp_currency or "INR"

        # Derive the discount from the stored price and MRP so the two agree:
        # Flipkart's own discountPercentage excludes offers, while `price` may be
        # the offer-inclusive special price. Use the reported value only when
        # the derivation is impossible.
        discount = compute_discount(price, mrp)
        if discount is None and special is None:
            reported = base.get("discountPercentage")
            if isinstance(reported, (int, float)) and not isinstance(reported, bool):
                discount = float(reported)

        in_stock = base.get("inStock")
        if in_stock is None:
            in_stock = base.get("isAvailable")
        availability = "In Stock" if in_stock is True else "Out of Stock" if in_stock is False else None

        shipping = item.get("productShippingInfoV1")
        seller = clean_text(shipping.get("sellerName"), 255) if isinstance(shipping, dict) else None
        seller = seller or clean_text(base.get("sellerName"), 255)

        platform_category, subcategory = _category_from_path(
            base.get("categoryPath") if base.get("categoryPath") is not None else base.get("categoryPaths")
        )

        specific = item.get("categorySpecificInfoV1")
        key_specs = specific.get("keySpecs") if isinstance(specific, dict) else None
        specifications = (
            {"key_specs": [spec for spec in key_specs if isinstance(spec, str)][:10]}
            if isinstance(key_specs, list) and any(isinstance(spec, str) for spec in key_specs)
            else None
        )

        return NormalizedRecord(
            platform=self.platform.value,
            product_name=title,
            # Only the brand Flipkart states; no guessing from the title.
            brand=clean_text(base.get("productBrand"), 120),
            category=platform_category or clean_text(category, 120),
            subcategory=subcategory,
            external_id=clean_text(base.get("productId"), 128),
            price=price,
            original_price=mrp,
            discount_percentage=discount,
            currency=currency,
            # Not exposed by the Affiliate API for products. Never substituted.
            rating=None,
            review_count=None,
            availability=availability,
            seller_name=seller,
            # normalize_url drops the query, which carries the affiliate tracking id.
            listing_url=normalize_url(base.get("productUrl")),
            specifications=specifications,
            stock_status=availability,
            collection_timestamp=fetched_at,
        )
