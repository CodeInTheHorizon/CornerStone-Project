"""Phase 4 tests: /data endpoints, persistence and deduplication.

Collection is driven through a patched collector, so no test reaches a live
marketplace.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import MarketplaceSnapshot
from app.models.enums import Platform, SourceType
from app.scrapers.base import (
    CollectionOutcome,
    CollectorRequestError,
    CollectorUnavailableError,
    MarketplaceCollector,
    NormalizedRecord,
)


@pytest.fixture
def auth_headers(client):
    # Unique per test: the schema is created once per session, so a fixed
    # address would collide on the second test that uses this fixture.
    email = f"collector_{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": "marketpulse1"}
    )
    assert response.status_code == 201, response.text
    from tests.accounts import grant_role
    grant_role(response.json()["user"]["id"])
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def record(**overrides) -> NormalizedRecord:
    # A unique listing per call: the database is shared across tests, and an
    # identical LIVE observation of the same listing minutes apart is (rightly)
    # skipped as a repeated fetch.
    listing = f"B0{uuid.uuid4().hex[:8].upper()}"
    defaults = dict(
        platform=Platform.AMAZON.value,
        product_name="Acme Earbuds",
        brand="Acme",
        external_id=listing,
        price=1999.0,
        original_price=2999.0,
        discount_percentage=33.34,
        availability="In Stock",
        listing_url=f"https://www.amazon.in/dp/{listing}",
        collection_timestamp=datetime.now(timezone.utc),
    )
    return NormalizedRecord(**{**defaults, **overrides})


class StubCollector(MarketplaceCollector):
    """Stands in for a real collector so tests never hit the network."""

    platform = Platform.AMAZON
    access_method = "Stub"

    def __init__(self, outcome=None, error=None):
        self._outcome = outcome or CollectionOutcome()
        self._error = error

    def status(self):
        from app.scrapers.base import CollectorStatus

        return CollectorStatus(
            platform=self.platform.value, available=True, access_method="Stub"
        )

    def collect(self, keyword, category=None, max_items=20):
        if self._error:
            raise self._error
        return self._outcome


@pytest.fixture
def patch_collector(monkeypatch):
    def _patch(outcome=None, error=None):
        stub = StubCollector(outcome, error)
        monkeypatch.setattr(
            "app.services.collection_service.get_collector", lambda platform: stub
        )
        return stub

    return _patch


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/data/collect"),
        ("get", "/data/latest"),
        ("get", "/data/history"),
        ("get", "/data/status"),
    ],
)
def test_data_endpoints_require_authentication(client, method, path):
    # httpx's .get() takes no json kwarg, so build the call per method.
    if method == "post":
        response = client.post(path, json={"platform": "amazon", "keyword": "earbuds"})
    else:
        response = client.get(path)

    assert response.status_code == 401


# --------------------------------------------------------------------------
# Request validation
# --------------------------------------------------------------------------


def test_collect_rejects_unknown_platform(client, auth_headers):
    response = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "ebay", "keyword": "earbuds"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"platform": "amazon", "keyword": "a"},
        {"platform": "amazon", "keyword": "earbuds", "max_items": 0},
        {"platform": "amazon", "keyword": "earbuds", "max_items": 5000},
        {"platform": "amazon"},
    ],
)
def test_collect_rejects_bad_input(client, auth_headers, payload):
    response = client.post("/data/collect", headers=auth_headers, json=payload)
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Unsupported platforms
# --------------------------------------------------------------------------


@pytest.mark.parametrize("platform", ["flipkart"])
def test_collect_on_blocked_platform_returns_501_with_reason(
    client, auth_headers, platform
):
    response = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": platform, "keyword": "wireless earbuds"},
    )

    assert response.status_code == 501
    assert len(response.json()["detail"]) > 30


def test_collect_amazon_web_enabled_does_not_return_501(client, auth_headers):
    response = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "wireless earbuds"},
    )
    assert response.status_code != 501


# --------------------------------------------------------------------------
# Successful collection and persistence
# --------------------------------------------------------------------------


def test_collect_persists_snapshots(client, auth_headers, patch_collector, db_session):
    patch_collector(
        CollectionOutcome(
            records=[record(), record(external_id="B0BBB", product_name="Nova Buds")]
        )
    )

    response = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "wireless earbuds", "max_items": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["items_collected"] == 2
    assert body["platform"] == "amazon"
    assert body["collection_run_id"]

    rows = (
        db_session.query(MarketplaceSnapshot)
        .filter(MarketplaceSnapshot.collection_run_id == body["collection_run_id"])
        .all()
    )
    assert len(rows) == 2
    stored = rows[0]
    assert stored.search_query == "wireless earbuds"
    # Every collected row is tagged live, never demo.
    assert stored.source_type == SourceType.LIVE.value
    assert stored.price == 1999.0


def test_collect_deduplicates_within_a_run(
    client, auth_headers, patch_collector, db_session
):
    duplicate = record()
    patch_collector(CollectionOutcome(records=[duplicate, duplicate, record(external_id="B0CCC")]))

    body = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "dedupe test"},
    ).json()

    assert body["items_collected"] == 2
    assert body["duplicates_skipped"] == 1
    assert any("duplicate" in w for w in body["warnings"])


def test_collect_rejects_bad_records_and_reports_them(
    client, auth_headers, patch_collector
):
    patch_collector(
        CollectionOutcome(
            records=[
                record(),
                record(external_id="B0BAD", product_name="   "),  # rejected
            ]
        )
    )

    body = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "bad records"},
    ).json()

    assert body["items_collected"] == 1
    assert body["items_rejected"] == 1
    # The warning names the offending record and why it was dropped.
    assert any("product_name is empty" in w for w in body["warnings"])


def test_collect_stores_warnings_on_a_salvaged_record(
    client, auth_headers, patch_collector, db_session
):
    patch_collector(
        CollectionOutcome(records=[record(external_id="B0WARN", rating=9.9)])
    )

    body = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "warning test"},
    ).json()

    stored = (
        db_session.query(MarketplaceSnapshot)
        .filter(MarketplaceSnapshot.collection_run_id == body["collection_run_id"])
        .one()
    )
    # The bad value is cleared, not clamped, and the reason is kept.
    assert stored.rating is None
    assert stored.warnings and any("rating" in w for w in stored.warnings)


def test_collect_reports_empty_when_nothing_found(
    client, auth_headers, patch_collector
):
    patch_collector(CollectionOutcome(records=[], warnings=["No results for 'zzz'."]))

    body = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "zzz nonexistent"},
    ).json()

    assert body["status"] == "empty"
    assert body["items_collected"] == 0


def test_collect_maps_upstream_failure_to_502(client, auth_headers, patch_collector):
    patch_collector(error=CollectorRequestError("PA-API returned 500"))

    response = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "earbuds"},
    )
    assert response.status_code == 502


def test_collect_maps_unavailable_to_501(client, auth_headers, patch_collector):
    patch_collector(error=CollectorUnavailableError("Not configured"))

    response = client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "earbuds"},
    )
    assert response.status_code == 501


# --------------------------------------------------------------------------
# Reading collected data
# --------------------------------------------------------------------------


def test_latest_returns_newest_first_and_filters(
    client, auth_headers, patch_collector
):
    patch_collector(CollectionOutcome(records=[record(external_id="B0LATEST")]))
    client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "latest probe"},
    )

    body = client.get(
        "/data/latest?keyword=latest probe&limit=10", headers=auth_headers
    ).json()

    assert body["count"] >= 1
    assert body["items"][0]["search_query"] == "latest probe"
    assert body["items"][0]["platform"] == "amazon"

    # A platform with no rows returns an empty list, not an error.
    empty = client.get("/data/latest?platform=croma", headers=auth_headers).json()
    assert empty["count"] == 0


def test_history_supports_a_date_range(client, auth_headers, patch_collector):
    patch_collector(CollectionOutcome(records=[record(external_id="B0HIST")]))
    client.post(
        "/data/collect",
        headers=auth_headers,
        json={"platform": "amazon", "keyword": "history probe"},
    )

    now = datetime.now(timezone.utc)
    inside = client.get(
        "/data/history",
        headers=auth_headers,
        params={
            "product": "Acme",
            "start": (now - timedelta(days=1)).isoformat(),
            "end": (now + timedelta(days=1)).isoformat(),
        },
    ).json()
    assert inside["count"] >= 1

    outside = client.get(
        "/data/history",
        headers=auth_headers,
        params={"start": (now + timedelta(days=2)).isoformat()},
    ).json()
    assert outside["count"] == 0


def test_history_rejects_a_reversed_date_range(client, auth_headers):
    now = datetime.now(timezone.utc)
    response = client.get(
        "/data/history",
        headers=auth_headers,
        params={
            "start": (now + timedelta(days=1)).isoformat(),
            "end": now.isoformat(),
        },
    )
    assert response.status_code == 400


def test_status_reports_every_platform_honestly(client, auth_headers):
    body = client.get("/data/status", headers=auth_headers).json()

    assert set(body["platforms"]) == {p.value for p in Platform}

    flipkart = body["platforms"]["flipkart"]
    assert flipkart["available"] is False
    assert flipkart["reason"]

    for name in ("croma", "alibaba"):
        entry = body["platforms"][name]
        assert entry["reason"]

    amazon = body["platforms"]["amazon"]
    assert "access_method" in amazon
