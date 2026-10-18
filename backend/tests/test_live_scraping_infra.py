"""robots.txt matching, HTTP policy (retries, blocks, pacing, proxy) and normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import requests
from requests.structures import CaseInsensitiveDict

from app.live_scraping.errors import (
    HttpStatusError,
    NetworkError,
    ParseFailedError,
    ProductNotFoundError,
    RateLimitedError,
    RobotsDisallowedError,
    SourceBlockedError,
)
from app.live_scraping.http_client import HttpClientConfig, PoliteHttpClient
from app.live_scraping.normalize import ParsedProduct, normalize, parse_count, parse_money
from app.live_scraping.rate_limit import HostRateLimiter
from app.live_scraping.robots import RobotsRules
from app.live_scraping.schemas import Availability, Marketplace

# ---------------------------------------------------------------- robots.txt


AMAZON_LIKE = """
User-agent: *
Disallow: /dp/product-availability/
Disallow: /gp/cart
Disallow: /*/reviews/*
Allow: /gp/cart/view.html$

User-agent: Scrapy
User-agent: GPTBot
Disallow: /
"""


@pytest.mark.parametrize(
    ("path", "agent", "allowed"),
    [
        ("/dp/B0TESTAC01", "MarketPulseBot", True),
        ("/dp/product-availability/B0TESTAC01", "MarketPulseBot", False),
        ("/gp/cart/add", "MarketPulseBot", False),
        ("/gp/cart/view.html", "MarketPulseBot", True),        # longer Allow wins
        ("/gp/cart/view.html?x=1", "MarketPulseBot", False),   # `$` anchors the end
        ("/some-product/reviews/B0TESTAC01", "MarketPulseBot", False),  # `*` wildcard
        ("/dp/B0TESTAC01", "scrapy", False),                   # named group, case-insensitive
        ("/robots.txt", "GPTBot", True),
    ],
)
def test_robots_rules(path, agent, allowed):
    assert RobotsRules.parse(AMAZON_LIKE).is_allowed(path, agent) is allowed


def test_robots_equal_length_tie_goes_to_allow_and_empty_disallow_is_no_rule():
    rules = RobotsRules.parse("User-agent: *\nDisallow: /page\nAllow: /page\nDisallow:\n")
    assert rules.is_allowed("/page", "x")
    assert RobotsRules.parse("User-agent: *\nDisallow:\n").is_allowed("/anything", "x")
    assert not RobotsRules.disallow_all().is_allowed("/", "x")


# ------------------------------------------------------------ fake transport


def _response(status=200, body="", headers=None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.headers = CaseInsensitiveDict({"Content-Type": "text/html; charset=utf-8", **(headers or {})})
    response._content = body.encode("utf-8")
    response._content_consumed = True
    return response


class ScriptedSession(requests.Session):
    """Returns queued responses per URL; an Exception in the queue is raised."""

    def __init__(self, script: dict[str, list]) -> None:
        super().__init__()
        self.script = {url: list(items) for url, items in script.items()}
        self.calls: list[str] = []

    def get(self, url, **kwargs):  # noqa: D401 - requests signature
        self.calls.append(url)
        queue = self.script.get(url)
        if not queue:
            raise AssertionError(f"unexpected request to {url}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


ROBOTS = "https://shop.example/robots.txt"
PAGE = "https://shop.example/dp/B0TESTAC01"
OK_ROBOTS = _response(200, "User-agent: *\nDisallow: /private/\n", {"Content-Type": "text/plain"})


def _client(script, **config) -> tuple[PoliteHttpClient, ScriptedSession, FakeClock]:
    clock = FakeClock()
    session = ScriptedSession(script)
    cfg = HttpClientConfig(user_agent="TestAgent/1.0", min_interval_seconds=5.0, backoff_base=2.0, **config)
    return PoliteHttpClient(cfg, session=session, sleep=clock.sleep, clock=clock), session, clock


def test_fetch_success_sets_headers_and_decodes():
    client, session, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(200, "<p>₹1,299</p>")]})
    page = client.get(PAGE)
    assert page.status_code == 200 and "₹1,299" in page.text and page.attempts == 1
    assert session.headers["User-Agent"] == "TestAgent/1.0"
    assert session.headers["Accept-Language"].startswith("en-IN")


def test_proxy_is_applied_from_config():
    client, session, _ = _client({}, http_proxy="http://proxy.internal:3128", https_proxy="http://proxy.internal:3128")
    assert session.proxies == {"http": "http://proxy.internal:3128", "https": "http://proxy.internal:3128"}


def test_robots_disallowed_path_is_never_requested():
    client, session, _ = _client({ROBOTS: [OK_ROBOTS]})
    with pytest.raises(RobotsDisallowedError) as caught:
        client.get("https://shop.example/private/x")
    assert caught.value.source_level is False
    assert session.calls == [ROBOTS]


@pytest.mark.parametrize(
    "robots_response",
    [_response(503, "down"), _response(403, "no"), _response(200, "<!doctype html><title>captcha</title>")],
)
def test_unreadable_robots_disallows_the_whole_source(robots_response):
    client, session, _ = _client({ROBOTS: [robots_response]})
    with pytest.raises(RobotsDisallowedError) as caught:
        client.get(PAGE)
    assert caught.value.source_level is True
    assert session.calls == [ROBOTS]


def test_missing_robots_allows_access():
    client, _, _ = _client({ROBOTS: [_response(404, "")], PAGE: [_response(200, "ok")]})
    assert client.get(PAGE).text == "ok"


def test_robots_is_cached_between_requests():
    client, session, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(200, "ok")]})
    client.get(PAGE)
    client.get(PAGE)
    assert session.calls.count(ROBOTS) == 1


def test_transient_5xx_is_retried_with_backoff_and_pacing():
    client, session, clock = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(502, "bad"), _response(200, "ok")]})
    page = client.get(PAGE)
    assert page.text == "ok" and page.attempts == 2
    assert session.calls.count(PAGE) == 2
    # Waited at least the per-host interval plus the first backoff step.
    assert sum(clock.slept) >= 5.0


def test_persistent_network_failure_gives_up_after_max_attempts():
    client, session, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [requests.Timeout("slow")]}, max_attempts=3)
    with pytest.raises(NetworkError):
        client.get(PAGE)
    assert session.calls.count(PAGE) == 3


def test_persistent_5xx_is_an_http_error():
    client, _, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(500, "err")]}, max_attempts=2)
    with pytest.raises(HttpStatusError):
        client.get(PAGE)


def test_429_is_not_retried_and_carries_retry_after():
    client, session, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(429, "", {"Retry-After": "120"})]})
    with pytest.raises(RateLimitedError) as caught:
        client.get(PAGE)
    assert caught.value.retry_after_seconds == 120 and caught.value.source_level
    assert session.calls.count(PAGE) == 1


def test_403_is_a_block_and_not_retried():
    client, session, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(403, "denied")]})
    with pytest.raises(SourceBlockedError):
        client.get(PAGE)
    assert session.calls.count(PAGE) == 1


def test_block_page_with_200_is_detected_and_not_retried():
    client, session, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(200, "please solve this captcha")]})
    with pytest.raises(SourceBlockedError, match="challenge"):
        client.get(PAGE, detect_block=lambda page: "challenge page" if "captcha" in page.text else None)
    assert session.calls.count(PAGE) == 1


def test_404_is_not_found():
    client, _, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(404, "gone")]})
    with pytest.raises(ProductNotFoundError):
        client.get(PAGE)


def test_redirects_are_checked_against_robots():
    redirect = _response(302, "", {"Location": "/private/login"})
    client, session, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [redirect]})
    with pytest.raises(RobotsDisallowedError):
        client.get(PAGE)
    assert "https://shop.example/private/login" not in session.calls


def test_oversized_response_is_refused():
    client, _, _ = _client({ROBOTS: [OK_ROBOTS], PAGE: [_response(200, "x" * 2048)]}, max_response_bytes=1024)
    with pytest.raises(HttpStatusError, match="exceeded"):
        client.get(PAGE)


def test_rate_limiter_spaces_requests_per_host():
    clock = FakeClock()
    limiter = HostRateLimiter(5.0, jitter_ratio=0.0, clock=clock, sleep=clock.sleep)
    assert limiter.wait("a") == 0
    assert limiter.wait("a") == pytest.approx(5.0)
    assert limiter.wait("b") == 0  # hosts are independent
    limiter.defer("a", 60)
    assert limiter.wait("a") == pytest.approx(60.0)


# -------------------------------------------------------------- normalization


@pytest.mark.parametrize(
    ("text", "amount"),
    [("₹1,29,999.00", Decimal("129999.00")), ("Rs. 499", Decimal("499.00")), ("₹ 1,299", Decimal("1299.00")),
     ("", None), ("Price not available", None), ("₹499 - ₹999", None), ("₹0", None)],
)
def test_parse_money(text, amount):
    assert parse_money(text)[0] == amount


@pytest.mark.parametrize(
    ("text", "count"),
    [("12,845 ratings", 12845), ("1,02,311 Ratings", 102311), ("1.2K", 1200), ("3.4 lakh reviews", 340000),
     ("12 left", 12), (None, None)],
)
def test_parse_count(text, count):
    assert parse_count(text) == count


def _obs(**parsed):
    return normalize(
        ParsedProduct(**{"product_name": "Thing", **parsed}),
        marketplace=Marketplace.AMAZON, platform_product_id="B0TESTAC01",
        product_url="https://www.amazon.in/dp/B0TESTAC01",
        collected_at=datetime(2026, 9, 30, 12, tzinfo=timezone.utc), source="amazon-html/1",
    )


def test_discount_is_recomputed_from_prices_and_mismatch_is_flagged():
    obs = _obs(current_price_text="₹750", mrp_text="₹1,000", discount_text="-40%")
    assert obs.discount_percentage == Decimal("25.00")
    assert any("stated 40" in w for w in obs.warnings)


def test_stated_discount_used_only_without_mrp():
    assert _obs(current_price_text="₹750", discount_text="25% off").discount_percentage == Decimal("25.00")
    assert _obs(discount_text="25% off").discount_percentage is None


def test_mrp_below_price_is_dropped_not_clamped():
    obs = _obs(current_price_text="₹1,500", mrp_text="₹1,000")
    assert obs.current_price == Decimal("1500.00") and obs.mrp is None and obs.discount_percentage is None
    assert any("mrp" in w for w in obs.warnings)


def test_out_of_range_rating_is_dropped():
    obs = _obs(rating_text="45 out of 5")
    assert obs.rating is None and any("rating" in w for w in obs.warnings)


def test_missing_values_stay_missing():
    obs = _obs()
    assert (obs.current_price, obs.mrp, obs.rating, obs.rating_count, obs.review_count, obs.seller_name) == (None,) * 6
    assert obs.availability is Availability.UNKNOWN


def test_no_product_name_is_a_parse_failure():
    with pytest.raises(ParseFailedError):
        _obs(product_name="   ")


def test_collected_at_is_stored_in_utc():
    from datetime import timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    obs = normalize(ParsedProduct(product_name="x"), marketplace=Marketplace.AMAZON, platform_product_id="B0TESTAC01",
                    product_url="https://www.amazon.in/dp/B0TESTAC01",
                    collected_at=datetime(2026, 9, 30, 17, 30, tzinfo=ist), source="s")
    assert obs.collected_at == datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    assert obs.collected_at.utcoffset() == timedelta(0)
