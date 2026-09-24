"""DataForSEO Merchant Amazon Products Live adapter (no website scraping)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.models.enums import CollectorState, IngestionMode, Platform
from app.scrapers.base import (CollectionOutcome, CollectorCredentialsRejectedError,
    CollectorProviderError, CollectorRateLimitedError, CollectorStatus,
    CollectorUnavailableError, MarketplaceCollector, NormalizedRecord)
from app.scrapers.parsing import clean_text, compute_discount, normalize_url, parse_price

PROVIDER = "dataforseo"
URL = "https://api.dataforseo.com/v3/merchant/amazon/products/live/advanced"
INDIA_LOCATION_CODE = 2356

class DataForSEOAmazonCollector(MarketplaceCollector):
    platform = Platform.AMAZON
    access_method = "Third-party API (DataForSEO Merchant Amazon Products Live)"
    def __init__(self, *, login: str | None = None, password: str | None = None,
                 enabled: bool | None = None, timeout: float | None = None,
                 client: httpx.Client | None = None, sleep=time.sleep) -> None:
        self.login = (settings.DATAFORSEO_LOGIN if login is None else login).strip()
        self.password = (settings.DATAFORSEO_PASSWORD.get_secret_value() if password is None else password).strip()
        self.enabled = settings.AMAZON_LIVE_ENABLED if enabled is None else enabled
        self.timeout = settings.DATAFORSEO_TIMEOUT_SECONDS if timeout is None else timeout
        self.client, self.sleep = client, sleep
    def status(self) -> CollectorStatus:
        common = dict(platform="amazon", access_method=self.access_method, ingestion_mode=IngestionMode.LIVE_API,
                      requires_credentials=True, provider=PROVIDER,
                      required_configuration=("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD", "AMAZON_LIVE_ENABLED"))
        if not self.login or not self.password:
            return CollectorStatus(**common, available=False, state=CollectorState.CREDENTIALS_MISSING,
                reason="DataForSEO credentials are not configured.")
        if not self.enabled:
            return CollectorStatus(**common, available=False, state=CollectorState.APPROVAL_REQUIRED,
                reason="Amazon LIVE collection is disabled; set AMAZON_LIVE_ENABLED=true to allow paid DataForSEO requests.")
        return CollectorStatus(**common, available=True, state=CollectorState.LIVE)
    def collect(self, keyword: str, category: str | None = None, max_items: int = 20) -> CollectionOutcome:
        if not self.status().available: raise CollectorUnavailableError(self.status().reason or "Not configured")
        payload = [{"keyword": keyword, "location_code": INDIA_LOCATION_CODE, "language_code": "en_IN", "depth": min(max(1,max_items),100)}]
        client, own = self.client or httpx.Client(timeout=self.timeout), self.client is None
        try:
            for attempt in range(3):
                try: response = client.post(URL, json=payload, auth=(self.login,self.password), timeout=self.timeout)
                except httpx.TimeoutException:
                    if attempt < 2: self.sleep(2 ** attempt); continue
                    raise CollectorProviderError("DataForSEO timed out.", code="timeout")
                except httpx.HTTPError as exc: raise CollectorProviderError(f"Could not reach DataForSEO ({type(exc).__name__}).", code="network_error")
                if response.status_code in (401,403): raise CollectorCredentialsRejectedError(f"DataForSEO rejected credentials (HTTP {response.status_code}).", code=f"http_{response.status_code}", http_status=response.status_code)
                if response.status_code == 429: raise CollectorRateLimitedError("DataForSEO rate-limited the request (HTTP 429).", retry_after_seconds=60)
                if response.status_code >= 500:
                    if attempt < 2: self.sleep(2 ** attempt); continue
                    raise CollectorProviderError(f"DataForSEO server error (HTTP {response.status_code}).", code=f"http_{response.status_code}", http_status=response.status_code)
                if response.status_code >= 400: raise CollectorProviderError(f"DataForSEO refused request (HTTP {response.status_code}).", code=f"http_{response.status_code}", http_status=response.status_code)
                try: body=response.json()
                except ValueError: raise CollectorProviderError("DataForSEO returned invalid JSON.", code="malformed_response")
                return self._normalize(body, category, max_items)
        finally:
            if own: client.close()
        raise CollectorProviderError("DataForSEO request failed.")
    def _normalize(self, body: object, category: str | None, limit: int) -> CollectionOutcome:
        if not isinstance(body,dict) or not isinstance(body.get("tasks"),list) or not body["tasks"]: raise CollectorProviderError("DataForSEO response has no tasks.", code="malformed_response")
        task=body["tasks"][0]
        if not isinstance(task,dict) or task.get("status_code") != 20000: raise CollectorProviderError("DataForSEO task was unsuccessful.", code="provider_error")
        results=task.get("result")
        if not isinstance(results,list): raise CollectorProviderError("DataForSEO task has no result list.", code="malformed_response")
        rows=results[0].get("items",[]) if results and isinstance(results[0],dict) else []
        if not isinstance(rows,list): raise CollectorProviderError("DataForSEO result items are malformed.", code="malformed_response")
        out=CollectionOutcome()
        fetched=datetime.now(timezone.utc)
        for item in rows:
            if not isinstance(item,dict): continue
            title=clean_text(item.get("title"))
            if not title: out.warnings.append("Skipped DataForSEO item without title."); continue
            price=parse_price(item.get("price") or item.get("price_current")); original=parse_price(item.get("price_original"))
            rating=parse_price(item.get("rating")); rating = rating if rating is None or 0 <= rating <= 5 else None
            reviews=parse_price(item.get("reviews_count") or item.get("rating_count")); reviews = int(reviews) if reviews is not None and reviews >= 0 else None
            image = item.get("image_url") or item.get("main_image")
            image_url = image if isinstance(image, str) and image.startswith("http") else None
            out.records.append(NormalizedRecord(platform="amazon", product_name=title, external_id=clean_text(item.get("asin") or item.get("product_id"),128), brand=clean_text(item.get("brand"),120), category=clean_text(category,120), image_url=image_url, price=price, original_price=original, discount_percentage=compute_discount(price,original), currency=clean_text(item.get("currency"),8) or "INR", rating=rating, review_count=reviews, availability=clean_text(item.get("availability") or item.get("availability_status"),64), seller_name=clean_text(item.get("seller"),255), listing_url=normalize_url(item.get("url") or item.get("product_url")), specifications={"search_rank": item.get("rank_absolute") or item.get("position")}, collection_timestamp=fetched))
            if len(out.records)>=min(max(1,limit),100): break
        return out
