"""Amazon collector, using the official Product Advertising API 5.0.

Why the official API and not the website: amazon.in returns 503 to
programmatic requests to /s, and the Conditions of Use prohibit data mining
regardless. Defeating that block is out of scope by policy, so PA-API is the
only permitted programmatic route.

PA-API requires an approved Associate account. Without credentials this
collector reports itself unavailable rather than falling back to scraping.

Known gap: PA-API 5.0 does not return star ratings or review counts. Those
fields stay None here, which matters for the review/rating trend features
planned in later phases.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
from typing import Any

import httpx

from app.config import settings
from app.models.enums import IngestionMode, Platform
from app.scrapers.base import (
    CollectionOutcome,
    CollectorRequestError,
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
)

REQUIRED_CONFIGURATION = (
    "AMAZON_PAAPI_ACCESS_KEY",
    "AMAZON_PAAPI_SECRET_KEY",
    "AMAZON_PAAPI_PARTNER_TAG",
)

SERVICE = "ProductAdvertisingAPI"
TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
PATH = "/paapi5/searchitems"

# The subset of the response we actually use. Requesting less keeps the call
# within PA-API's throughput limits.
RESOURCES = [
    "ItemInfo.Title",
    "ItemInfo.ByLineInfo",
    "ItemInfo.Classifications",
    "ItemInfo.Features",
    "ItemInfo.ProductInfo",
    "Offers.Listings.Price",
    "Offers.Listings.SavingBasis",
    "Offers.Listings.Availability.Message",
    "Offers.Listings.MerchantInfo",
    "Offers.Listings.DeliveryInfo.IsPrimeEligible",
    "BrowseNodeInfo.BrowseNodes",
]


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signature_key(secret: str, date_stamp: str, region: str) -> bytes:
    """Derive the AWS SigV4 signing key."""
    k_date = _sign(f"AWS4{secret}".encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, SERVICE)
    return _sign(k_service, "aws4_request")


class AmazonCollector(MarketplaceCollector):
    """Collects Amazon listings through PA-API 5.0."""

    platform = Platform.AMAZON
    access_method = "Official API (Product Advertising API 5.0)"

    def __init__(
        self,
        *,
        access_key: str | None = None,
        secret_key: str | None = None,
        partner_tag: str | None = None,
        host: str | None = None,
        region: str | None = None,
        marketplace: str | None = None,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.access_key = access_key if access_key is not None else settings.AMAZON_PAAPI_ACCESS_KEY
        self.secret_key = secret_key if secret_key is not None else settings.AMAZON_PAAPI_SECRET_KEY
        self.partner_tag = partner_tag if partner_tag is not None else settings.AMAZON_PAAPI_PARTNER_TAG
        self.host = host or settings.AMAZON_PAAPI_HOST
        self.region = region or settings.AMAZON_PAAPI_REGION
        self.marketplace = marketplace or settings.AMAZON_PAAPI_MARKETPLACE
        self.timeout = timeout
        # Injectable so tests exercise the real request/parse path against a
        # mock transport instead of the live API.
        self._client = client

    # -- status ------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return bool(self.access_key and self.secret_key and self.partner_tag)

    def status(self) -> CollectorStatus:
        if not self.is_configured:
            return CollectorStatus(
                platform=self.platform.value,
                available=False,
                access_method=self.access_method,
                ingestion_mode=IngestionMode.LIVE_API,
                reason=(
                    "PA-API credentials are not configured. An approved Amazon "
                    "Associate account is required."
                ),
                requires_credentials=True,
                required_configuration=REQUIRED_CONFIGURATION,
            )

        return CollectorStatus(
            platform=self.platform.value,
            available=True,
            access_method=self.access_method,
            ingestion_mode=IngestionMode.LIVE_API,
            requires_credentials=True,
            required_configuration=REQUIRED_CONFIGURATION,
        )

    # -- request signing ---------------------------------------------------

    def _signed_headers(self, payload: str, now: dt.datetime) -> dict[str, str]:
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"host:{self.host}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:{TARGET}\n"
        )
        signed_headers = "content-encoding;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        canonical_request = "\n".join(
            ["POST", PATH, "", canonical_headers, signed_headers, payload_hash]
        )

        credential_scope = f"{date_stamp}/{self.region}/{SERVICE}/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        signature = hmac.new(
            _signature_key(self.secret_key, date_stamp, self.region),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": self.host,
            "x-amz-date": amz_date,
            "x-amz-target": TARGET,
            "Authorization": authorization,
        }

    # -- collection --------------------------------------------------------

    def collect(
        self,
        keyword: str,
        category: str | None = None,
        max_items: int = 20,
    ) -> CollectionOutcome:
        if not self.is_configured:
            raise CollectorUnavailableError(self.status().reason or "Not configured.")

        outcome = CollectionOutcome()
        # PA-API returns at most 10 items per page.
        pages = max(1, min(10, (max_items + 9) // 10))

        for page in range(1, pages + 1):
            body: dict[str, Any] = {
                "Keywords": keyword,
                "PartnerTag": self.partner_tag,
                "PartnerType": "Associates",
                "Marketplace": self.marketplace,
                "ItemPage": page,
                "ItemCount": min(10, max_items - len(outcome.records)),
                "Resources": RESOURCES,
            }
            if category:
                body["SearchIndex"] = category

            payload = json.dumps(body)
            headers = self._signed_headers(payload, dt.datetime.now(dt.timezone.utc))

            data = self._post(payload, headers)

            errors = data.get("Errors")
            if errors:
                messages = "; ".join(
                    str(err.get("Message", err)) for err in errors if isinstance(err, dict)
                )
                # PA-API reports "no results" as an error code, which is not a
                # failure of the collector.
                if any(
                    isinstance(err, dict) and err.get("Code") == "NoResults"
                    for err in errors
                ):
                    outcome.warnings.append(f"No results for '{keyword}'.")
                    break
                raise CollectorRequestError(f"PA-API error: {messages}")

            items = (data.get("SearchResult") or {}).get("Items") or []
            if not items:
                break

            for item in items:
                record = self._to_record(item, keyword, category, outcome.warnings)
                if record is not None:
                    outcome.records.append(record)
                if len(outcome.records) >= max_items:
                    return outcome

        return outcome

    def _post(self, payload: str, headers: dict[str, str]) -> dict[str, Any]:
        url = f"https://{self.host}{PATH}"
        client = self._client or httpx.Client(timeout=self.timeout)
        close_after = self._client is None

        try:
            # One retry: PA-API throttles aggressively and a single 429 is
            # common. This is backoff, not evasion.
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    response = client.post(url, content=payload, headers=headers)
                except httpx.HTTPError as exc:
                    last_error = exc
                    continue

                if response.status_code == 429 and attempt == 0:
                    last_error = CollectorRequestError("PA-API rate limited (429).")
                    continue

                if response.status_code >= 400:
                    raise CollectorRequestError(
                        f"PA-API returned {response.status_code}: {response.text[:300]}"
                    )

                try:
                    return response.json()
                except ValueError as exc:
                    raise CollectorRequestError(
                        "PA-API returned a non-JSON response."
                    ) from exc

            raise CollectorRequestError(
                f"PA-API request failed: {last_error}"
            ) from last_error
        finally:
            if close_after:
                client.close()

    # -- normalization -----------------------------------------------------

    def _to_record(
        self,
        item: dict[str, Any],
        keyword: str,
        category: str | None,
        warnings: list[str],
    ) -> NormalizedRecord | None:
        """Map one PA-API item onto the shared schema.

        Returns None when the item has no usable title, and records a warning
        rather than raising: one malformed item should not abort the run.
        """
        try:
            info = item.get("ItemInfo") or {}
            title = clean_text(((info.get("Title") or {}).get("DisplayValue")))
            if not title:
                warnings.append("Skipped an item with no title.")
                return None

            asin = clean_text(item.get("ASIN"), limit=128)

            by_line = info.get("ByLineInfo") or {}
            brand = extract_brand(
                (by_line.get("Brand") or by_line.get("Manufacturer") or {}).get(
                    "DisplayValue"
                ),
                title,
            )

            listing = ((item.get("Offers") or {}).get("Listings") or [{}])[0]

            price = parse_price((listing.get("Price") or {}).get("Amount"))
            original_price = parse_price(
                (listing.get("SavingBasis") or {}).get("Amount")
            )
            currency = (listing.get("Price") or {}).get("Currency") or "INR"

            availability = clean_text(
                (listing.get("Availability") or {}).get("Message"), limit=64
            )
            seller = clean_text(
                (listing.get("MerchantInfo") or {}).get("Name"), limit=255
            )
            prime = ((listing.get("DeliveryInfo") or {}).get("IsPrimeEligible"))

            browse = (item.get("BrowseNodeInfo") or {}).get("BrowseNodes") or []
            browse_category = clean_text(browse[0].get("DisplayName"), 120) if browse else None
            subcategory = None
            if browse and isinstance(browse[0].get("Ancestor"), dict):
                subcategory = clean_text(
                    browse[0]["Ancestor"].get("DisplayName"), 120
                )

            features = (info.get("Features") or {}).get("DisplayValues")
            specifications = (
                {"features": [f for f in features if isinstance(f, str)][:10]}
                if isinstance(features, list) and features
                else None
            )

            return NormalizedRecord(
                platform=self.platform.value,
                product_name=title,
                brand=brand,
                # Prefer the platform's own classification over the user's input.
                category=browse_category or clean_text(category, 120),
                subcategory=subcategory,
                external_id=asin,
                price=price,
                original_price=original_price,
                discount_percentage=compute_discount(price, original_price),
                currency=currency,
                # PA-API 5.0 exposes neither of these. Left None deliberately.
                rating=None,
                review_count=None,
                availability=availability,
                seller_name=seller,
                listing_url=normalize_url(item.get("DetailPageURL")),
                badge="Prime" if prime is True else None,
                sponsored=None,
                specifications=specifications,
                stock_status=availability,
            )
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            # A shape change upstream should degrade to a skipped item.
            warnings.append(f"Skipped an item that could not be parsed: {exc}")
            return None
