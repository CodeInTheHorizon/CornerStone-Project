"""Flipkart Affiliate API collector against mocked HTTP responses.

No test reaches Flipkart: every request goes through httpx.MockTransport, so
the real request building, retry, error mapping and normalization code runs.
"""

import json
from datetime import timezone
from pathlib import Path

import httpx
import pytest

from app.models.enums import CollectorState, IngestionMode
from app.scrapers import get_collector
from app.scrapers.base import (
    CollectorCredentialsRejectedError,
    CollectorProviderError,
    CollectorRateLimitedError,
    CollectorUnavailableError,
)
from app.scrapers.flipkart import (
    DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
    MAX_ATTEMPTS,
    MAX_RESULTS_PER_REQUEST,
    PROVIDER,
    SEARCH_URL,
    FlipkartCollector,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "flipkart_search_response.json").read_text(encoding="utf-8"))
AFFILIATE_ID = "fixture-affiliate-id-7731"
TOKEN = "fixture-secret-token-9f2c41"


class Provider:
    """Scripted provider: each call pops the next response (or exception)."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(step, Exception):
            raise step
        return step


def ok(payload=FIXTURE):
    return httpx.Response(200, json=payload)


def collector(provider=None, *, approved=True, affiliate_id=AFFILIATE_ID, token=TOKEN, sleeps=None):
    client = httpx.Client(transport=httpx.MockTransport(provider or Provider(ok())))
    return FlipkartCollector(
        affiliate_id=affiliate_id, affiliate_token=token, data_use_approved=approved,
        timeout=2, client=client, sleep=(sleeps.append if sleeps is not None else (lambda _: None)),
    )


# --------------------------------------------------------------------------
# Status and gating
# --------------------------------------------------------------------------


def test_registry_uses_the_flipkart_api_collector():
    assert isinstance(get_collector("flipkart"), FlipkartCollector)


def test_credentials_missing_status_names_variables_only():
    status = FlipkartCollector(affiliate_id="", affiliate_token="", data_use_approved=False).status()
    assert status.available is False
    assert status.state is CollectorState.CREDENTIALS_MISSING
    assert status.ingestion_mode is IngestionMode.LIVE_API
    assert status.requires_credentials is True
    assert status.required_configuration == ("FLIPKART_AFFILIATE_ID", "FLIPKART_AFFILIATE_TOKEN", "FLIPKART_DATA_USE_APPROVED")
    assert status.provider == PROVIDER


def test_credentials_without_approval_stay_disabled_and_make_no_request():
    provider = Provider(ok())
    blocked = collector(provider, approved=False)
    status = blocked.status()
    assert status.available is False
    assert status.state is CollectorState.APPROVAL_REQUIRED
    assert "FLIPKART_DATA_USE_APPROVED" in status.reason
    assert TOKEN not in status.reason and AFFILIATE_ID not in status.reason
    with pytest.raises(CollectorUnavailableError):
        blocked.collect("earbuds")
    assert provider.requests == []


def test_configured_and_approved_is_live():
    status = collector().status()
    assert status.available is True
    assert status.state is CollectorState.LIVE


def test_unconfigured_collect_raises_instead_of_returning_empty():
    with pytest.raises(CollectorUnavailableError):
        FlipkartCollector(affiliate_id="", affiliate_token="", data_use_approved=True).collect("earbuds")


def test_repr_never_contains_credentials():
    assert TOKEN not in repr(collector()) and AFFILIATE_ID not in repr(collector())


# --------------------------------------------------------------------------
# Successful fetch and normalization
# --------------------------------------------------------------------------


def test_request_uses_official_endpoint_headers_and_limits():
    provider = Provider(ok())
    collector(provider).collect("wireless earbuds", max_items=5)
    request = provider.requests[0]
    assert str(request.url).startswith(SEARCH_URL)
    assert request.url.params["query"] == "wireless earbuds"
    assert request.url.params["resultCount"] == "5"
    assert request.headers["Fk-Affiliate-Id"] == AFFILIATE_ID
    assert request.headers["Fk-Affiliate-Token"] == TOKEN
    assert request.method == "GET"


def test_successful_fetch_normalizes_into_the_shared_schema():
    outcome = collector().collect("wireless earbuds", category="Audio", max_items=10)
    assert [r.product_name for r in outcome.records] == [
        "Fixture Buds Pro Bluetooth Headset", "Fixture Minimal Charger", "Fixture 65W GaN Charger",
    ]
    full = outcome.records[0]
    assert full.platform == "flipkart"
    assert full.external_id == "ACCFIXTURE0001"
    assert full.brand == "Fixture"
    assert (full.category, full.subcategory) == ("Headphones", "True Wireless")
    # The offer-inclusive special price wins; MRP is the original price.
    assert full.price == 1999.0 and full.original_price == 4999.0
    # Derived from the stored prices, not Flipkart's offer-exclusive 56%.
    assert full.discount_percentage == 60.01
    assert full.currency == "INR"
    assert full.availability == "In Stock" and full.stock_status == "In Stock"
    assert full.seller_name == "Fixture Retail"
    assert full.specifications == {"key_specs": ["Bluetooth 5.3", "40 hour battery"]}
    assert full.collection_timestamp.tzinfo is not None
    assert full.collection_timestamp.utcoffset() == timezone.utc.utcoffset(None)


def test_stored_url_drops_affiliate_tracking_parameters():
    url = collector().collect("earbuds").records[0].listing_url
    assert url == "https://dl.flipkart.com/dl/fixture-buds-pro/p/itm0001"
    assert "affid" not in url and "fixtureaffiliate" not in url


def test_ratings_and_reviews_are_never_filled_from_seller_ratings():
    for record in collector().collect("earbuds").records:
        assert record.rating is None
        assert record.review_count is None


def test_missing_fields_stay_none():
    minimal = collector().collect("charger").records[1]
    assert minimal.product_name == "Fixture Minimal Charger"
    for name in ("brand", "category", "subcategory", "external_id", "price", "original_price",
                 "discount_percentage", "availability", "seller_name", "listing_url", "specifications"):
        assert getattr(minimal, name) is None, name


def test_user_category_is_used_only_when_flipkart_gives_none():
    records = collector().collect("charger", category="Chargers").records
    assert records[1].category == "Chargers"
    assert records[0].category == "Headphones"


def test_nested_category_paths_and_selling_price_fallback():
    nested = collector().collect("charger").records[2]
    assert (nested.category, nested.subcategory) == ("Chargers", "Wall Chargers")
    assert nested.price == 1499.0 and nested.original_price == 2999.0
    assert nested.discount_percentage == 50.02
    assert nested.availability == "Out of Stock"
    assert nested.brand is None  # no guessing "Fixture" from the title


def test_unusable_items_are_skipped_with_warnings():
    outcome = collector().collect("earbuds")
    assert len(outcome.records) == 3
    assert any("no title" in warning for warning in outcome.warnings)
    assert any("not an object" in warning for warning in outcome.warnings)


def test_item_limit_is_capped_per_request_with_a_warning():
    provider = Provider(ok())
    outcome = collector(provider).collect("earbuds", max_items=50)
    assert provider.requests[0].url.params["resultCount"] == str(MAX_RESULTS_PER_REQUEST)
    assert any("at most 10" in warning for warning in outcome.warnings)


def test_limit_applies_to_returned_records():
    assert len(collector().collect("earbuds", max_items=2).records) == 2


def test_empty_result_is_a_warning_not_an_error():
    outcome = collector(Provider(ok({"products": []}))).collect("nothing", max_items=10)
    assert outcome.records == []
    assert outcome.warnings == ["Flipkart returned no results for 'nothing'."]


# --------------------------------------------------------------------------
# Provider failures
# --------------------------------------------------------------------------


def test_timeout_is_retried_with_backoff_then_reported():
    sleeps: list[float] = []
    provider = Provider(httpx.ReadTimeout("slow"))
    with pytest.raises(CollectorProviderError) as error:
        collector(provider, sleeps=sleeps).collect("earbuds")
    assert error.value.code == "timeout"
    assert len(provider.requests) == MAX_ATTEMPTS
    assert sleeps == [1.0, 2.0]


def test_transient_timeout_recovers():
    provider = Provider(httpx.ConnectTimeout("slow"), ok())
    assert len(collector(provider).collect("earbuds").records) == 3
    assert len(provider.requests) == 2


def test_network_error_message_never_contains_credentials():
    provider = Provider(httpx.ConnectError(f"refused token={TOKEN} id={AFFILIATE_ID}"))
    with pytest.raises(CollectorProviderError) as error:
        collector(provider).collect("earbuds")
    assert error.value.code == "network_error"
    assert TOKEN not in str(error.value) and AFFILIATE_ID not in str(error.value)


@pytest.mark.parametrize("status_code", [400, 404, 410])
def test_other_4xx_is_a_provider_error_without_retry(status_code):
    provider = Provider(httpx.Response(status_code, text=f"bad request echo {TOKEN}"))
    with pytest.raises(CollectorProviderError) as error:
        collector(provider).collect("earbuds")
    assert error.value.code == f"http_{status_code}"
    assert error.value.http_status == status_code
    assert len(provider.requests) == 1
    assert TOKEN not in str(error.value)  # provider bodies are never echoed


@pytest.mark.parametrize("status_code", [401, 403])
def test_rejected_credentials_are_distinct_and_not_retried(status_code):
    provider = Provider(httpx.Response(status_code, json={"error": "invalid token"}))
    with pytest.raises(CollectorCredentialsRejectedError) as error:
        collector(provider).collect("earbuds")
    assert error.value.outcome.value == "credentials_rejected"
    assert len(provider.requests) == 1
    assert TOKEN not in str(error.value) and AFFILIATE_ID not in str(error.value)


def test_5xx_is_retried_then_reported():
    provider = Provider(httpx.Response(503))
    with pytest.raises(CollectorProviderError) as error:
        collector(provider).collect("earbuds")
    assert error.value.code == "http_503"
    assert len(provider.requests) == MAX_ATTEMPTS


def test_transient_5xx_recovers():
    provider = Provider(httpx.Response(500), ok())
    assert len(collector(provider).collect("earbuds").records) == 3


def test_short_rate_limit_is_waited_out_once():
    sleeps: list[float] = []
    provider = Provider(httpx.Response(429, headers={"Retry-After": "2"}), ok())
    assert len(collector(provider, sleeps=sleeps).collect("earbuds").records) == 3
    assert sleeps == [2.0, 1.0]  # the provider's wait, then normal backoff


def test_long_rate_limit_is_reported_with_the_providers_window():
    provider = Provider(httpx.Response(429, headers={"Retry-After": "120"}))
    with pytest.raises(CollectorRateLimitedError) as error:
        collector(provider).collect("earbuds")
    assert error.value.retry_after_seconds == 120
    assert error.value.outcome.value == "rate_limited"
    assert len(provider.requests) == 1


def test_rate_limit_without_retry_after_uses_a_default_cooldown():
    with pytest.raises(CollectorRateLimitedError) as error:
        collector(Provider(httpx.Response(429))).collect("earbuds")
    assert error.value.retry_after_seconds == DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["products"]),
        httpx.Response(200, json={"items": []}),
        httpx.Response(200, json={"products": "none"}),
    ],
)
def test_malformed_responses_are_provider_errors(response):
    with pytest.raises(CollectorProviderError) as error:
        collector(Provider(response)).collect("earbuds")
    assert error.value.code == "malformed_response"
