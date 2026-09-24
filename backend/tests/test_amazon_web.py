"""Amazon public-search collector against mocked HTTP responses.

No test reaches Amazon: every request goes through httpx.MockTransport, so the
real request building, retry, error mapping and parsing code runs against
markup captured from a live amazon.in search page.
"""

import httpx
import pytest

from app.models.enums import CollectorState, IngestionMode
from app.scrapers.amazon_web import (
    BLOCK_COOLDOWN_SECONDS,
    MAX_ATTEMPTS,
    MAX_SANE_PRICE,
    PROVIDER,
    AmazonWebCollector,
    _composite_price,
    _parse_price,
)
from app.scrapers.base import (
    CollectorProviderError,
    CollectorRateLimitedError,
    CollectorUnavailableError,
)

# Trimmed from a real amazon.in result card: current price in split
# whole/fraction spans, struck-through M.R.P., rating, and an aria-label
# review count that the visible text abbreviates to "(1.1K)".
CARD = """
<div data-asin="B0GV1L119H" data-component-type="s-search-result">
  <h2><a href="/Dell-Laptop/dp/B0GV1L119H/ref=sr_1_3?keywords=laptop">
    <span>Dell 15 Laptop, 14th Gen Intel Core i5</span></a></h2>
  <i class="a-icon a-icon-star-mini"><span class="a-icon-alt">4.0 out of 5 stars</span></i>
  <span aria-label="1,119 ratings" class="a-size-mini a-color-secondary">(1.1K)</span>
  <span class="a-price" data-a-size="l"><span class="a-offscreen">&#8377;60,490</span>
    <span aria-hidden="true"><span class="a-price-symbol">&#8377;</span>
    <span class="a-price-whole">60,490</span></span></span>
  <span class="a-size-mini a-color-secondary">M.R.P: </span>
  <span class="a-price a-text-price puis-light-weight-text" data-a-strike="true">
    <span class="a-offscreen">&#8377;72,781</span><span aria-hidden="true">&#8377;72,781</span></span>
  <div id="availability"><span>In stock</span></div>
</div>
"""

SPONSORED_CARD = """
<div data-asin="B0GWHGS8P5" data-component-type="s-search-result">
  <h2><a href="/dp/B0GWHGS8P5"><span>Dell 15 AI Powered Laptop</span></a></h2>
  <span class="puis-label-popover-default"><span>Sponsored</span></span>
  <span class="a-price"><span aria-hidden="true">
    <span class="a-price-whole">84,990</span><span class="a-price-fraction">50</span></span></span>
</div>
"""

PAGE = f"<html><body>{CARD}{SPONSORED_CARD}</body></html>"

BOT_CHALLENGE = (
    "<html><head><title>Robot Check</title></head><body>"
    "Enter the characters you see below Sorry, we just need to make sure "
    "you're not a robot. To discuss automated access to Amazon data please "
    "contact api-services-support@amazon.com</body></html>"
)


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


def collector(provider=None, *, enabled=True, sleeps=None):
    provider = provider or Provider(httpx.Response(200, text=PAGE))
    client = httpx.Client(transport=httpx.MockTransport(provider))
    return AmazonWebCollector(
        enabled=enabled,
        client=client,
        sleep=(sleeps.append if sleeps is not None else lambda _: None),
    ), provider


# -- price parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("₹60,490", 60490.0),
        ("INR 1,09,227", 109227.0),          # Indian lakh grouping
        ("M.R.P: ₹72,781", 72781.0),    # label prefix ahead of the number
        ("$49.99", 49.99),
        ("", None),
        ("Out of stock", None),
        ("0", None),                          # a zero price is not a price
        (str(MAX_SANE_PRICE + 1), None),      # implausible values are discarded
    ],
)
def test_parse_price_reads_or_rejects(raw, expected):
    assert _parse_price(raw) == expected


def test_composite_price_rebuilds_decimal_from_split_spans():
    """The whole/fraction split is what decides decimal placement."""
    fragment = (
        '<span class="a-price-whole">1,299</span>'
        '<span class="a-price-fraction">50</span>'
    )
    assert _composite_price(fragment) == 1299.50


def test_composite_price_defaults_missing_fraction_to_zero():
    assert _composite_price('<span class="a-price-whole">84,990</span>') == 84990.0


# -- status ----------------------------------------------------------------


def test_disabled_collector_reports_approval_required():
    status = AmazonWebCollector(enabled=False).status()
    assert status.available is False
    assert status.state is CollectorState.APPROVAL_REQUIRED
    assert "AMAZON_WEB_ENABLED" in status.required_configuration


def test_enabled_collector_reports_live_public_source():
    status = AmazonWebCollector(enabled=True).status()
    assert status.available is True
    assert status.state is CollectorState.LIVE
    assert status.ingestion_mode is IngestionMode.LIVE_PUBLIC_SOURCE
    assert status.provider == PROVIDER
    assert status.requires_credentials is False


def test_disabled_collector_refuses_to_collect():
    subject, _ = collector(enabled=False)
    with pytest.raises(CollectorUnavailableError):
        subject.collect("laptop")


# -- normalization ---------------------------------------------------------


def test_collect_normalizes_a_result_card():
    subject, _ = collector()
    outcome = subject.collect("laptop", category="Electronics", max_items=1)

    assert len(outcome.records) == 1
    record = outcome.records[0]
    assert record.platform == "amazon"
    assert record.external_id == "B0GV1L119H"
    assert record.product_name == "Dell 15 Laptop, 14th Gen Intel Core i5"
    assert record.price == 60490.0
    assert record.original_price == 72781.0
    assert record.discount_percentage == pytest.approx(16.89, abs=0.01)
    assert record.currency == "INR"
    assert record.rating == 4.0
    # Read from aria-label, not the abbreviated "(1.1K)" the page displays.
    assert record.review_count == 1119
    assert record.category == "Electronics"
    assert record.availability == "In stock"
    assert record.sponsored is False
    assert record.listing_url.startswith("https://www.amazon.in/")
    # The search page names no seller; it must stay unset rather than guessed.
    assert record.seller_name is None


def test_collect_flags_sponsored_results_and_keeps_rank():
    subject, _ = collector()
    outcome = subject.collect("laptop", max_items=5)

    assert [r.sponsored for r in outcome.records] == [False, True]
    assert [r.specifications["search_rank"] for r in outcome.records] == [1, 2]
    assert outcome.records[1].price == 84990.50


def test_collect_honours_max_items():
    subject, _ = collector()
    assert len(subject.collect("laptop", max_items=1).records) == 1


def test_collect_sends_currency_and_locale_cookies():
    subject, provider = collector()
    subject.collect("laptop")

    request = provider.requests[0]
    assert request.url.params["k"] == "laptop"
    assert "i18n-prefs=INR" in request.headers["cookie"]
    assert "en-IN" in request.headers["accept-language"]


def test_unparsable_page_warns_instead_of_inventing_records():
    subject, _ = collector(Provider(httpx.Response(200, text="<html></html>")))
    outcome = subject.collect("laptop")

    assert outcome.records == []
    assert outcome.warnings and "No parsable" in outcome.warnings[0]


def test_result_without_a_title_is_skipped_with_a_warning():
    page = '<div data-asin="B01" data-component-type="s-search-result"></div>'
    subject, _ = collector(Provider(httpx.Response(200, text=page)))
    outcome = subject.collect("laptop")

    assert outcome.records == []
    assert any("no readable title" in w for w in outcome.warnings)


def test_missing_price_is_left_none_rather_than_guessed():
    page = (
        '<div data-asin="B02" data-component-type="s-search-result">'
        "<h2><a><span>A product with no price shown</span></a></h2></div>"
    )
    subject, _ = collector(Provider(httpx.Response(200, text=page)))
    record = subject.collect("laptop").records[0]

    assert record.price is None
    assert record.discount_percentage is None


def test_strike_price_below_current_price_is_discarded():
    """A "was" price under the current price means the spans were mismatched."""
    page = (
        '<div data-asin="B03" data-component-type="s-search-result">'
        "<h2><a><span>Mismatched price spans</span></a></h2>"
        '<span class="a-price"><span class="a-price-whole">999</span></span>'
        '<span class="a-price a-text-price"><span class="a-offscreen">&#8377;500</span></span>'
        "</div>"
    )
    subject, _ = collector(Provider(httpx.Response(200, text=page)))
    record = subject.collect("laptop").records[0]

    assert record.price == 999.0
    assert record.original_price is None


# -- failure mapping -------------------------------------------------------


def test_bot_challenge_is_reported_as_rate_limited():
    """A challenge page is a block to back off from, not a parse failure."""
    subject, _ = collector(Provider(httpx.Response(200, text=BOT_CHALLENGE)))
    with pytest.raises(CollectorRateLimitedError) as exc:
        subject.collect("laptop")
    assert exc.value.retry_after_seconds == BLOCK_COOLDOWN_SECONDS


def test_http_503_is_treated_as_a_block_not_a_retryable_server_error():
    sleeps: list[float] = []
    subject, provider = collector(Provider(httpx.Response(503)), sleeps=sleeps)

    with pytest.raises(CollectorRateLimitedError):
        subject.collect("laptop")
    # Retrying a challenge harder is exactly the wrong response.
    assert len(provider.requests) == 1
    assert sleeps == []


def test_http_429_is_rate_limited():
    subject, _ = collector(Provider(httpx.Response(429)))
    with pytest.raises(CollectorRateLimitedError):
        subject.collect("laptop")


def test_server_error_retries_then_fails():
    sleeps: list[float] = []
    subject, provider = collector(Provider(httpx.Response(500)), sleeps=sleeps)

    with pytest.raises(CollectorProviderError):
        subject.collect("laptop")
    assert len(provider.requests) == MAX_ATTEMPTS
    assert len(sleeps) == MAX_ATTEMPTS - 1


def test_server_error_recovers_when_a_retry_succeeds():
    subject, provider = collector(
        Provider(httpx.Response(500), httpx.Response(200, text=PAGE)),
        sleeps=[],
    )
    assert len(subject.collect("laptop", max_items=1).records) == 1
    assert len(provider.requests) == 2


def test_timeout_retries_then_fails_as_timeout():
    sleeps: list[float] = []
    subject, provider = collector(
        Provider(httpx.TimeoutException("slow")), sleeps=sleeps
    )

    with pytest.raises(CollectorProviderError) as exc:
        subject.collect("laptop")
    assert exc.value.code == "timeout"
    assert len(provider.requests) == MAX_ATTEMPTS


def test_client_error_is_not_retried():
    subject, provider = collector(Provider(httpx.Response(404)))
    with pytest.raises(CollectorProviderError):
        subject.collect("laptop")
    assert len(provider.requests) == 1
