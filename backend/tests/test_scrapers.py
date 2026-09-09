"""Phase 4 tests: parsing, normalization, validation and collector behaviour.

Nothing here touches a live marketplace. The Amazon collector is exercised
against a recorded PA-API response through a mock transport, so the real
request-signing and parsing path runs without any network call.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.models.enums import Platform
from app.scrapers import (
    CollectorUnavailableError,
    UnknownPlatformError,
    all_statuses,
    get_collector,
)
from app.scrapers.amazon import AmazonCollector
from app.scrapers.base import NormalizedRecord
from app.scrapers.parsing import (
    compute_discount,
    extract_brand,
    normalize_url,
    parse_price,
    parse_rating,
    parse_review_count,
)
from app.scrapers.validation import validate_record

FIXTURE = Path(__file__).parent / "fixtures" / "paapi_search_response.json"

CREDENTIALS = {
    "access_key": "AKIATESTONLY",
    "secret_key": "test-secret-not-real",
    "partner_tag": "example-21",
}


def make_collector(handler) -> AmazonCollector:
    """Amazon collector wired to a mock transport instead of the network."""
    return AmazonCollector(
        **CREDENTIALS,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("₹1,299.00", 1299.0),
        ("Rs. 999", 999.0),
        (2499, 2499.0),
        (2499.5, 2499.5),
        ("", None),
        ("out of stock", None),
        (None, None),
        (True, None),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("4.3 out of 5 stars", 4.3), ("5", 5.0), ("0", 0.0), ("7.2", None), ("", None)],
)
def test_parse_rating_discards_out_of_range(raw, expected):
    # 7.2 is discarded rather than clamped to 5: a clamped value would look
    # like a real measurement.
    assert parse_rating(raw) == expected


@pytest.mark.parametrize(
    "raw,expected", [("1,234 ratings", 1234), ("0", 0), ("-5", None), ("", None)]
)
def test_parse_review_count(raw, expected):
    assert parse_review_count(raw) == expected


def test_compute_discount():
    assert compute_discount(2499.0, 4999.0) == 50.01
    # Nonsensical combinations produce None, not a negative discount.
    assert compute_discount(5000.0, 4000.0) is None
    assert compute_discount(None, 4000.0) is None
    assert compute_discount(100.0, 0) is None


def test_normalize_url_strips_tracking_and_forces_https():
    assert (
        normalize_url("http://www.amazon.in/dp/B0X?tag=aff-21&ref=sr_1")
        == "https://www.amazon.in/dp/B0X"
    )
    assert normalize_url("/dp/B0X", base="https://www.amazon.in") == "https://www.amazon.in/dp/B0X"
    assert normalize_url("javascript:alert(1)") is None
    assert normalize_url(None) is None


def test_extract_brand_prefers_explicit_value():
    assert extract_brand("Acme", "Sony WH-1000XM5") == "Acme"
    assert extract_brand(None, "Sony WH-1000XM5") == "Sony"
    # Not a plausible brand token.
    assert extract_brand(None, "65W Fast Charger") is None
    assert extract_brand(None, None) is None


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def base_record(**overrides) -> NormalizedRecord:
    defaults = dict(
        platform=Platform.AMAZON.value,
        product_name="Test Earbuds",
        price=999.0,
        collection_timestamp=datetime.now(timezone.utc),
    )
    return NormalizedRecord(**{**defaults, **overrides})


def test_validation_rejects_empty_product_name():
    result = validate_record(base_record(product_name="   "))
    assert not result.is_valid
    assert "product_name" in result.rejected_reason


def test_validation_rejects_unknown_platform():
    result = validate_record(base_record(platform="ebay"))
    assert not result.is_valid
    assert "unknown platform" in result.rejected_reason


def test_validation_drops_out_of_range_rating_with_a_warning():
    result = validate_record(base_record(rating=9.9))
    assert result.is_valid
    assert result.record.rating is None
    assert any("rating" in w for w in result.warnings)


def test_validation_drops_negative_review_count():
    result = validate_record(base_record(review_count=-4))
    assert result.is_valid
    assert result.record.review_count is None


def test_validation_drops_invalid_url():
    result = validate_record(base_record(listing_url="not-a-url"))
    assert result.is_valid
    assert result.record.listing_url is None


def test_validation_flags_price_above_original_price():
    result = validate_record(
        base_record(price=5000.0, original_price=4000.0, discount_percentage=-25.0)
    )
    assert result.is_valid
    assert result.record.original_price is None
    assert result.record.discount_percentage is None


def test_validation_passes_a_clean_record_without_warnings():
    result = validate_record(
        base_record(rating=4.5, review_count=120, listing_url="https://a.in/dp/X")
    )
    assert result.is_valid
    assert result.warnings == []


# --------------------------------------------------------------------------
# Registry and unsupported platforms
# --------------------------------------------------------------------------


def test_every_platform_has_a_collector():
    statuses = all_statuses()
    assert set(statuses) == {p.value for p in Platform}


def test_unknown_platform_raises():
    with pytest.raises(UnknownPlatformError):
        get_collector("ebay")


@pytest.mark.parametrize("platform", ["flipkart", "croma", "alibaba"])
def test_blocked_platforms_report_unavailable_with_a_reason(platform):
    collector = get_collector(platform)
    status = collector.status()

    assert status.available is False
    # The reason must actually explain the blocker, not just say "no".
    assert status.reason and len(status.reason) > 30


@pytest.mark.parametrize("platform", ["flipkart", "croma", "alibaba"])
def test_blocked_platforms_raise_rather_than_returning_empty(platform):
    # An unsupported source must never look like a source that found nothing.
    with pytest.raises(CollectorUnavailableError):
        get_collector(platform).collect("wireless earbuds", max_items=5)


def test_amazon_reports_unavailable_without_credentials():
    collector = AmazonCollector(access_key="", secret_key="", partner_tag="")
    status = collector.status()

    assert status.available is False
    assert status.requires_credentials is True
    assert "credentials" in status.reason.lower()

    with pytest.raises(CollectorUnavailableError):
        collector.collect("wireless earbuds")


# --------------------------------------------------------------------------
# Amazon collector against a recorded PA-API response
# --------------------------------------------------------------------------


def test_amazon_normalizes_a_recorded_response():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["target"] = request.headers.get("x-amz-target")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=payload)

    outcome = make_collector(handler).collect(
        "wireless earbuds", category="Electronics", max_items=10
    )

    # The request was properly signed and addressed.
    assert seen["url"].endswith("/paapi5/searchitems")
    assert seen["auth"].startswith("AWS4-HMAC-SHA256 Credential=AKIATESTONLY/")
    assert "SearchItems" in seen["target"]
    assert seen["body"]["Keywords"] == "wireless earbuds"
    assert seen["body"]["SearchIndex"] == "Electronics"

    # The third fixture item has no title and must be skipped, not invented.
    assert len(outcome.records) == 2
    assert any("no title" in w for w in outcome.warnings)

    first = outcome.records[0]
    assert first.platform == "amazon"
    assert first.product_name == "Acme SoundPods Pro Wireless Earbuds, 40h Playtime"
    assert first.brand == "Acme"
    assert first.external_id == "B0TESTAAA1"
    assert first.price == 2499.0
    assert first.original_price == 4999.0
    assert first.discount_percentage == 50.01
    assert first.currency == "INR"
    assert first.availability == "In Stock"
    assert first.seller_name == "Appario Retail Private Ltd"
    assert first.badge == "Prime"
    # Platform classification wins over the caller's category input.
    assert first.category == "In-Ear Headphones"
    assert first.subcategory == "Headphones"
    assert first.specifications["features"][0] == "Active noise cancellation"
    # Affiliate/tracking parameters are stripped.
    assert first.listing_url == "https://www.amazon.in/dp/B0TESTAAA1"

    # PA-API 5.0 exposes neither of these; they must stay None, not become 0.
    assert first.rating is None
    assert first.review_count is None

    # Sparse item: only what the response actually contained.
    second = outcome.records[1]
    assert second.product_name == "Nova Buds Lite"
    assert second.original_price is None
    assert second.discount_percentage is None
    assert second.seller_name is None
    assert second.badge is None


def test_amazon_reports_no_results_as_a_warning_not_an_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"Errors": [{"Code": "NoResults", "Message": "No results found"}]},
        )

    outcome = make_collector(handler).collect("zzzz-nonexistent", max_items=5)

    assert outcome.records == []
    assert any("No results" in w for w in outcome.warnings)


def test_amazon_raises_on_an_api_error():
    from app.scrapers.base import CollectorRequestError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "Errors": [
                    {"Code": "InvalidPartnerTag", "Message": "The partner tag is invalid"}
                ]
            },
        )

    with pytest.raises(CollectorRequestError, match="partner tag"):
        make_collector(handler).collect("earbuds", max_items=5)


def test_amazon_raises_on_http_error():
    from app.scrapers.base import CollectorRequestError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="TooManyRequests")

    with pytest.raises(CollectorRequestError, match="403"):
        make_collector(handler).collect("earbuds", max_items=5)


def test_amazon_survives_an_unexpected_payload_shape():
    # A shape change upstream should degrade to skipped items with warnings,
    # not raise and not fabricate.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "SearchResult": {
                    "Items": [
                        {"ASIN": "B0X", "ItemInfo": {"Title": "not-an-object"}}
                    ]
                }
            },
        )

    outcome = make_collector(handler).collect("earbuds", max_items=5)
    assert outcome.records == []
    assert outcome.warnings
