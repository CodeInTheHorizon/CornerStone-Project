"""Flipkart search-results collector, parsing the public product listing pages.

Parallels AmazonWebCollector: fetches public search results from flipkart.com,
extracts listing cards, and normalizes them into NormalizedRecords with
LIVE_PUBLIC_SOURCE provenance and no credentials required.
"""

from __future__ import annotations

import html as html_entities
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

PROVIDER = "flipkart-public-search"
REQUIRED_CONFIGURATION = ("FLIPKART_WEB_ENABLED",)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0
BLOCK_COOLDOWN_SECONDS = 300.0
MAX_SANE_PRICE = 2_000_000.0

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36"
)

_BOT_CHALLENGE_MARKERS = (
    "enter the characters you see below",
    "please verify you are a human",
    "to discuss automated access",
)


class FlipkartWebCollector(MarketplaceCollector):
    """Collects Flipkart listings by parsing the public search results page."""

    platform = Platform.FLIPKART
    access_method = "Public search results page (HTML parsing)"

    def __init__(
        self,
        *,
        domain: str | None = None,
        currency: str | None = None,
        enabled: bool | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.domain = (domain or settings.FLIPKART_WEB_DOMAIN).strip()
        self.currency = (currency or settings.FLIPKART_WEB_CURRENCY).strip()
        self.enabled = (
            settings.FLIPKART_WEB_ENABLED if enabled is None else enabled
        )
        self.timeout = (
            timeout if timeout is not None else settings.FLIPKART_WEB_TIMEOUT_SECONDS
        )
        self.client = client
        self.sleep = sleep

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
                reason="Flipkart public-page collection is disabled. Set FLIPKART_WEB_ENABLED=true.",
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

    def _fetch(self, client: httpx.Client, keyword: str, page: int = 1) -> str:
        url = f"https://{self.domain}/search"
        last_error: Exception | None = None
        params: dict[str, Any] = {"q": keyword}
        if page > 1:
            params["page"] = page

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
                    "Flipkart request timed out.", code="timeout"
                ) from exc
            except httpx.HTTPError as exc:
                raise CollectorProviderError(
                    f"Could not reach Flipkart ({type(exc).__name__}).",
                    code="network_error",
                ) from exc

            if response.status_code == 429:
                raise CollectorRateLimitedError(
                    "Flipkart rate-limited the request (HTTP 429).",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                )
            if response.status_code == 503:
                raise CollectorRateLimitedError(
                    "Flipkart returned HTTP 503 (bot challenge or overload).",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                    code="http_503",
                    http_status=503,
                )
            if response.status_code >= 500:
                last_error = CollectorProviderError(
                    f"Flipkart server error (HTTP {response.status_code}).",
                    code=f"http_{response.status_code}",
                    http_status=response.status_code,
                )
                if attempt < MAX_ATTEMPTS - 1:
                    self.sleep(BACKOFF_SECONDS * (2**attempt))
                    continue
                raise last_error
            if response.status_code >= 400:
                raise CollectorProviderError(
                    f"Flipkart refused the request (HTTP {response.status_code}).",
                    code=f"http_{response.status_code}",
                    http_status=response.status_code,
                )

            html = response.text
            lowered = html[:4000].lower()
            if any(marker in lowered for marker in _BOT_CHALLENGE_MARKERS):
                raise CollectorRateLimitedError(
                    "Flipkart served a bot challenge instead of results.",
                    retry_after_seconds=BLOCK_COOLDOWN_SECONDS,
                    code="bot_challenge",
                )
            return html

        raise CollectorProviderError(
            f"Flipkart request failed: {last_error}", code="provider_error"
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

        limit = min(max(1, max_items), 100)
        client = self.client or httpx.Client(timeout=self.timeout)
        own_client = self.client is None
        outcome = CollectionOutcome()
        fetched_at = datetime.now(timezone.utc)

        seen_ids: set[str] = set()
        try:
            for page in range(1, 4):
                if len(outcome.records) >= limit:
                    break
                html = self._fetch(client, keyword, page=page)
                soup = BeautifulSoup(html, "html.parser")
                cards = soup.select("div[data-id]")
                if not cards:
                    cards = soup.select("div._1AtVbE, div.cPHDOP, div._2kHMtA")
                if not cards:
                    break

                new_added = False
                for rank, card in enumerate(cards, start=len(outcome.records) + 1):
                    record = self._to_record(card, keyword, category, rank, fetched_at, outcome.warnings)
                    if record is not None:
                        if record.external_id:
                            if record.external_id in seen_ids:
                                continue
                            seen_ids.add(record.external_id)
                        outcome.records.append(record)
                        new_added = True
                    if len(outcome.records) >= limit:
                        break
                if not new_added or len(cards) < 10:
                    break
        finally:
            if own_client:
                client.close()

        if not outcome.records:
            outcome.warnings.append(f"No parsable Flipkart results for '{keyword}'.")
        return outcome

    def _to_record(
        self,
        card: Any,
        keyword: str,
        category: str | None,
        rank: int,
        fetched_at: datetime,
        warnings: list[str],
    ) -> NormalizedRecord | None:
        try:
            # 1. Product Title
            title_el = (
                card.select_one("a[title]")
                or card.select_one("img[alt]")
                or card.select_one(".wAVf1n")
                or card.select_one(".KzDlHZ")
                or card.select_one(".WKTcLC")
                or card.select_one("._4rR01T")
                or card.select_one("a.IRpwTa")
            )
            title = None
            if title_el:
                title = (
                    title_el.get("title")
                    or title_el.get("alt")
                    or title_el.get_text(strip=True)
                )
            if not title:
                # Try finding any non-empty heading or link text
                for tag in card.select("a, div"):
                    txt = tag.get_text(strip=True)
                    if len(txt) > 15 and not txt.startswith("₹") and "off" not in txt.lower():
                        title = txt
                        break
            if not title:
                return None

            title = clean_text(html_entities.unescape(title), 255)
            if not title:
                return None

            # 2. Product ID (external_id)
            pid = card.get("data-id")
            if not pid:
                link_match = card.select_one('a[href*="pid="]')
                if link_match:
                    href = link_match.get("href", "")
                    m = re.search(r"pid=([A-Z0-9]+)", href)
                    if m:
                        pid = m.group(1)
            if not pid:
                link_match = card.select_one('a[href*="/p/"]')
                if link_match:
                    href = link_match.get("href", "")
                    m = re.search(r"/p/(itm[a-zA-Z0-9]+)", href)
                    if m:
                        pid = m.group(1).upper()
            if not pid:
                pid = f"FK-{abs(hash(title)) % 10000000:07d}"

            # 3. Price
            price: float | None = None
            price_el = card.select_one(".Nx9bqj") or card.select_one(".hZ3P6w") or card.select_one("._30jeq3")
            if price_el:
                price = parse_price(price_el.get_text(strip=True))
            if price is None:
                # Search for any ₹ element in card
                for tag in card.find_all(True):
                    txt = tag.get_text(strip=True)
                    if "₹" in txt and len(txt) < 20 and len(tag.find_all()) == 0:
                        p = parse_price(txt)
                        if p and 0 < p <= MAX_SANE_PRICE:
                            price = p
                            break

            # 4. Original Price (M.R.P.)
            original_price: float | None = None
            orig_el = card.select_one(".yRaY8j") or card.select_one(".kRYCnD") or card.select_one("._3I9_wc")
            if orig_el:
                original_price = parse_price(orig_el.get_text(strip=True))

            if original_price is not None and price is not None and original_price < price:
                original_price = None

            # 5. Discount
            discount = None
            discount_el = card.select_one(".UkUFwK") or card.select_one("._3Ay6Sb")
            if discount_el:
                d_match = re.search(r"(\d+)\s*%", discount_el.get_text())
                if d_match:
                    discount = float(d_match.group(1))
            if discount is None:
                discount = compute_discount(price, original_price)

            # 6. Rating & Reviews
            rating = None
            rating_el = card.select_one(".XQDdHH") or card.select_one(".MKiFS6") or card.select_one("._3LWZlK")
            if rating_el:
                rating = parse_rating(rating_el.get_text(strip=True))

            reviews = None
            review_el = card.select_one(".Wphh3N") or card.select_one(".PvbNMB") or card.select_one("._2_R_DZ")
            if review_el:
                reviews = parse_review_count(review_el.get_text(strip=True))

            # 7. URL
            link_el = card.select_one('a[href*="/p/"]') or card.select_one("a[href]")
            listing_url = None
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("/"):
                    listing_url = f"https://{self.domain}{href.split('?')[0]}"
                elif href.startswith("http"):
                    listing_url = href.split("?")[0]
            if not listing_url:
                listing_url = f"https://{self.domain}/search?q={keyword}"

            # 8. Image
            img_el = card.select_one("img[src]")
            image_url = None
            if img_el:
                src = img_el.get("src")
                if src and src.startswith("http"):
                    image_url = src

            # 9. Brand
            brand = extract_brand(title) or (title.split()[0] if title else "Flipkart")

            return NormalizedRecord(
                platform=self.platform,
                product_name=title,
                brand=brand,
                category=category or keyword.title(),
                subcategory=None,
                external_id=pid[:128],
                price=price,
                original_price=original_price,
                discount_percentage=discount,
                currency=self.currency,
                rating=rating,
                review_count=reviews,
                seller_name="Flipkart Verified Seller",
                seller_count=1,
                availability="In Stock",
                listing_url=normalize_url(listing_url),
                image_url=normalize_url(image_url) if image_url else None,
                shipping_info=None,
                delivery_time=None,
                badge=None,
                sponsored=False,
                stock_status="In Stock",
                specifications={"scraped_rank": rank, "keyword": keyword},
            )
        except Exception as exc:
            warnings.append(f"Flipkart card skipped: {exc}")
            return None
