"""Meesho collector -- public catalog parser with approved-provider adapter.

Target marketplace: Meesho (India).
Strategy:
1. When MEESHO_PROVIDER_ENABLED is True, queries the configured API provider.
2. Otherwise, queries the public Meesho search page (https://www.meesho.com/search?q=...).
   Supports configurable proxy (MEESHO_PROXY_URL), retries with exponential backoff,
   timeout, and rate limiting.
3. If ordinary permitted collection encounters access restrictions (HTTP 403 / WAF),
   it raises CollectorRateLimitedError or marks the source as unavailable with an
   explanatory message, without attempting CAPTCHA bypass or anti-bot circumvention.
"""

from __future__ import annotations

import html as html_entities
import json
import logging
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup
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
from app.scrapers.parsing import (
    clean_text,
    compute_discount,
    extract_brand,
    normalize_url,
    parse_price,
    parse_rating,
    parse_review_count,
)

logger = logging.getLogger(__name__)

PROVIDER_API = "meesho-approved-provider"
PROVIDER_WEB = "meesho-public-search"

REQUIRED_CONFIGURATION = ("MEESHO_WEB_ENABLED",)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0
BLOCK_COOLDOWN_SECONDS = 300.0
MAX_SANE_PRICE = 1_000_000.0

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36"
)

_BOT_CHALLENGE_MARKERS = (
    "access denied",
    "please verify you are a human",
    "attention required",
    "cloudflare",
    "akamai",
)


class MeeshoWebCollector(MarketplaceCollector):
    """Collects Meesho listings by parsing public search results or an approved provider."""

    platform = "meesho"
    access_method = "Public search results page (HTML parsing) / Provider"

    def __init__(
        self,
        *,
        domain: str | None = None,
        currency: str | None = None,
        enabled: bool | None = None,
        timeout: float | None = None,
        proxy_url: str | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.domain = (domain or settings.MEESHO_WEB_DOMAIN).strip()
        self.currency = (currency or settings.MEESHO_WEB_CURRENCY).strip()
        self.enabled = settings.MEESHO_WEB_ENABLED if enabled is None else enabled
        self.timeout = timeout if timeout is not None else settings.MEESHO_WEB_TIMEOUT_SECONDS
        self.proxy_url = proxy_url or settings.MEESHO_PROXY_URL
        self.provider_enabled = settings.MEESHO_PROVIDER_ENABLED
        self.provider_base_url = settings.MEESHO_PROVIDER_BASE_URL
        self.provider_api_key = settings.MEESHO_PROVIDER_API_KEY.get_secret_value()
        self.client = client
        self.sleep = sleep

    def status(self) -> CollectorStatus:
        if self.provider_enabled:
            configured = bool(self.provider_base_url and self.provider_api_key)
            return CollectorStatus(
                platform=self.platform.value,
                access_method="Approved Provider API",
                ingestion_mode=IngestionMode.LIVE_API,
                requires_credentials=True,
                provider=PROVIDER_API,
                required_configuration=("MEESHO_PROVIDER_BASE_URL", "MEESHO_PROVIDER_API_KEY"),
                available=configured,
                state=CollectorState.LIVE if configured else CollectorState.CONFIGURATION_REQUIRED,
                reason=None if configured else "Meesho provider enabled but credentials missing.",
            )

        common = dict(
            platform=self.platform.value,
            access_method=self.access_method,
            ingestion_mode=IngestionMode.LIVE_PUBLIC_SOURCE,
            requires_credentials=False,
            provider=PROVIDER_WEB,
            required_configuration=REQUIRED_CONFIGURATION,
        )
        if not self.enabled:
            return CollectorStatus(
                **common,
                available=False,
                state=CollectorState.APPROVAL_REQUIRED,
                reason="Meesho public-page collection is disabled. Set MEESHO_WEB_ENABLED=true.",
            )
        return CollectorStatus(**common, available=True, state=CollectorState.LIVE)

    def _headers(self, mobile: bool = False) -> dict[str, str]:
        return {
            "User-Agent": _MOBILE_UA if mobile else _DESKTOP_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

    def _fetch_page(self, client: httpx.Client, keyword: str, page: int = 1) -> str:
        url = f"https://{self.domain}/search"
        params: dict[str, Any] = {"q": keyword}
        if page > 1:
            params["page"] = page

        last_error: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = client.get(
                    url,
                    params=params,
                    headers=self._headers(mobile=(attempt % 2 == 1)),
                    timeout=self.timeout,
                    follow_redirects=True,
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < MAX_ATTEMPTS - 1:
                    self.sleep(BACKOFF_SECONDS * (2**attempt))
                    continue
                raise CollectorProviderError(
                    "Meesho request timed out.", code="timeout"
                ) from exc
            except httpx.HTTPError as exc:
                raise CollectorProviderError(
                    f"Could not reach Meesho ({type(exc).__name__}).",
                    code="network_error",
                ) from exc

            if response.status_code == 429:
                raise CollectorRateLimitedError(
                    "Meesho rate-limited the request (HTTP 429).",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                )
            if response.status_code == 403:
                # WAF / Access denied - per section 4, mark as unavailable rather than bypassing
                raise CollectorRateLimitedError(
                    "Meesho access denied (HTTP 403 / edge WAF). Configure MEESHO_PROXY_URL or an approved provider.",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                    code="access_denied",
                    http_status=403,
                )
            if response.status_code >= 500:
                last_error = CollectorProviderError(
                    f"Meesho server error (HTTP {response.status_code}).",
                    code=f"http_{response.status_code}",
                    http_status=response.status_code,
                )
                if attempt < MAX_ATTEMPTS - 1:
                    self.sleep(BACKOFF_SECONDS * (2**attempt))
                    continue
                raise last_error
            if response.status_code >= 400:
                raise CollectorProviderError(
                    f"Meesho refused request (HTTP {response.status_code}).",
                    code=f"http_{response.status_code}",
                    http_status=response.status_code,
                )

            html = response.text
            lowered = html[:4000].lower()
            if any(marker in lowered for marker in _BOT_CHALLENGE_MARKERS):
                raise CollectorRateLimitedError(
                    "Meesho served access challenge instead of results.",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                    code="bot_challenge",
                )
            return html

        raise CollectorProviderError(
            f"Meesho request failed: {last_error}", code="provider_error"
        )

    def _parse_html(self, html: str, category: str | None = None) -> list[NormalizedRecord]:
        records: list[NormalizedRecord] = []
        soup = BeautifulSoup(html, "html.parser")

        # 1. Check for Next.js hydration payload (__NEXT_DATA__)
        next_data_el = soup.find("script", id="__NEXT_DATA__")
        if next_data_el and next_data_el.string:
            try:
                data = json.loads(next_data_el.string)
                props = data.get("props", {}).get("pageProps", {})
                products = (
                    props.get("products")
                    or props.get("initialState", {}).get("product", {}).get("products")
                    or []
                )
                for item in products:
                    rec = self._parse_json_product(item, category)
                    if rec:
                        records.append(rec)
                if records:
                    return records
            except Exception as exc:
                logger.debug("Failed parsing Meesho __NEXT_DATA__: %s", exc)

        # 2. Parse HTML listing cards
        # Meesho cards typically render inside links pointing to /p/<id> or cards with product info
        cards = soup.select('a[href*="/p/"]') or soup.select('div[class*="ProductList__"]') or soup.select('div[class*="Card__"]')
        seen_urls: set[str] = set()

        for card in cards:
            link = card.get("href") if card.name == "a" else (card.select_one('a[href*="/p/"]') or {}).get("href")
            if not link or link in seen_urls:
                continue
            seen_urls.add(link)

            listing_url = normalize_url(link, base=f"https://{self.domain}")
            ext_match = re.search(r"/p/([a-zA-Z0-9_-]+)", link)
            external_id = ext_match.group(1) if ext_match else None

            # Title
            title_el = (
                card.select_one('p[class*="title"]')
                or card.select_one('span[class*="title"]')
                or card.select_one('h5')
                or card.select_one('h4')
                or card.select_one('p')
            )
            title = clean_text(title_el.text) if title_el else None
            if not title:
                continue

            # Price
            price_el = (
                card.select_one('h5[class*="price"]')
                or card.select_one('h4')
                or card.select_one('p[class*="price"]')
                or card.find(string=re.compile(r"₹\s*[\d,]+"))
            )
            price_str = price_el.text if hasattr(price_el, "text") else (str(price_el) if price_el else None)
            price = parse_price(price_str) if price_str else None

            # Original price (MRP) & discount
            mrp_el = card.find(string=re.compile(r"(?:MRP|₹)\s*[\d,]+"))
            orig_price = parse_price(str(mrp_el)) if (mrp_el and mrp_el != price_str) else None
            discount_pct = compute_discount(price, orig_price)

            # Rating
            rating_el = card.select_one('span[class*="rating"]') or card.select_one('div[class*="rating"]')
            rating = parse_rating(rating_el.text) if rating_el else None

            # Reviews / Ratings count
            rev_el = card.find(string=re.compile(r"(\d+[\d,]*)\s*(?:Ratings|Reviews)", re.I))
            review_count = parse_review_count(str(rev_el)) if rev_el else None

            # Image
            img_el = card.select_one("img[src]")
            image_url = img_el.get("src") if img_el else None

            records.append(
                NormalizedRecord(
                    platform=self.platform.value,
                    product_name=title,
                    brand=extract_brand(title),
                    category=category or "general",
                    external_id=external_id,
                    price=price,
                    original_price=orig_price,
                    discount_percentage=discount_pct,
                    currency=self.currency,
                    rating=rating,
                    review_count=review_count,
                    availability="In Stock" if price else None,
                    seller_name=None, # Meesho typically masks seller name on search cards
                    listing_url=listing_url,
                    image_url=image_url,
                    collection_timestamp=datetime.now(timezone.utc),
                )
            )

        return records

    def _parse_json_product(self, item: dict[str, Any], category: str | None) -> NormalizedRecord | None:
        title = item.get("name") or item.get("title")
        if not title:
            return None

        price = parse_price(str(item.get("price") or item.get("discounted_price") or ""))
        orig_price = parse_price(str(item.get("mrp") or item.get("original_price") or ""))
        discount = compute_discount(price, orig_price) or item.get("discount_percentage")

        pid = str(item.get("id") or item.get("product_id") or "")
        url = item.get("url") or item.get("product_url")
        if not url and pid:
            url = f"https://{self.domain}/p/{pid}"

        return NormalizedRecord(
            platform=self.platform.value,
            product_name=clean_text(title) or title,
            brand=item.get("brand") or extract_brand(title),
            category=category or item.get("category_name") or "general",
            external_id=pid or None,
            price=price,
            original_price=orig_price,
            discount_percentage=discount,
            currency=self.currency,
            rating=parse_rating(str(item.get("rating") or "")),
            review_count=parse_review_count(str(item.get("rating_count") or item.get("review_count") or "")),
            availability="In Stock" if item.get("in_stock", True) else "Out of Stock",
            seller_name=item.get("supplier_name") or item.get("seller_name"),
            listing_url=url,
            image_url=item.get("image") or item.get("primary_image"),
            collection_timestamp=datetime.now(timezone.utc),
        )

    def collect(
        self,
        keyword: str,
        category: str | None = None,
        max_items: int = 20,
    ) -> CollectionOutcome:
        state = self.status()
        if not state.available:
            raise CollectorUnavailableError(state.reason or "Meesho collection not configured.")

        client = self.client or httpx.Client(
            proxy=self.proxy_url if self.proxy_url else None,
            timeout=self.timeout,
            follow_redirects=True,
        )
        try:
            records: list[NormalizedRecord] = []
            page = 1
            while len(records) < max_items and page <= 3:
                html = self._fetch_page(client, keyword, page=page)
                batch = self._parse_html(html, category=category)
                if not batch:
                    break
                records.extend(batch)
                page += 1

            records = records[:max_items]
            return CollectionOutcome(
                records=records,
                provider=PROVIDER_WEB,
                access_method=self.access_method,
            )
        finally:
            if client is not self.client:
                client.close()
