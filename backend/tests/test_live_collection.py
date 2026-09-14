"""LIVE collection pipeline: API -> Flipkart collector (mocked HTTP) -> ingest -> DB.

Exercises provenance, append-only history, true-duplicate skipping, rate-limit
cooldowns, runtime collector states and secret handling end to end, without
contacting Flipkart.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import delete, select, update

from app.models import CollectionAttempt, MarketplaceSnapshot, ModelMetadata
from app.models.enums import Platform, SourceType
from app.scrapers import registry
from app.scrapers.flipkart import PROVIDER, FlipkartCollector

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "flipkart_search_response.json").read_text(encoding="utf-8"))
AFFILIATE_ID = "live-test-affiliate-5521"
TOKEN = "live-test-secret-token-3be71d"


class Provider:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def set(self, *responses):
        self.responses = list(responses)

    def __call__(self, request):
        self.calls += 1
        step = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(step, Exception):
            raise step
        return step


def payload(price=1999.0, stock=True):
    body = json.loads(json.dumps(FIXTURE))
    body["products"] = [body["products"][0]]
    base = body["products"][0]["productBaseInfoV1"]
    base["flipkartSpecialPrice"]["amount"] = price
    base["inStock"] = stock
    return body


@pytest.fixture
def auth_headers(client):
    email = f"live_{uuid.uuid4().hex[:10]}@example.com"
    response = client.post("/auth/register", json={"email": email, "password": "marketpulse1"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def clean_flipkart(db_session):
    def wipe():
        db_session.execute(delete(CollectionAttempt).where(CollectionAttempt.platform == "flipkart"))
        db_session.execute(delete(MarketplaceSnapshot).where(
            MarketplaceSnapshot.platform == "flipkart", MarketplaceSnapshot.source_type == SourceType.LIVE.value))
        db_session.commit()
    wipe()
    yield
    wipe()


@pytest.fixture
def flipkart(monkeypatch, clean_flipkart):
    """Configure the registry's Flipkart collector against a scripted provider."""
    provider = Provider(httpx.Response(200, json=payload()))
    state = {"approved": True, "configured": True}

    def build():
        return FlipkartCollector(
            affiliate_id=AFFILIATE_ID if state["configured"] else "",
            affiliate_token=TOKEN if state["configured"] else "",
            data_use_approved=state["approved"],
            timeout=2,
            client=httpx.Client(transport=httpx.MockTransport(provider)),
            sleep=lambda _: None,
        )

    monkeypatch.setitem(registry._BUILDERS, Platform.FLIPKART, build)
    provider.state = state
    return provider


def collect(client, headers, keyword="wireless earbuds", **extra):
    return client.post("/data/collect", headers=headers, json={"platform": "flipkart", "keyword": keyword, "max_items": 10, **extra})


def flipkart_status(client, headers):
    return client.get("/data/status", headers=headers).json()["platforms"]["flipkart"]


def attempts(db_session):
    db_session.expire_all()
    return list(db_session.execute(
        select(CollectionAttempt).where(CollectionAttempt.platform == "flipkart").order_by(CollectionAttempt.id)
    ).scalars())


def live_rows(db_session, external_id="ACCFIXTURE0001"):
    db_session.expire_all()
    return list(db_session.execute(
        select(MarketplaceSnapshot).where(
            MarketplaceSnapshot.platform == "flipkart", MarketplaceSnapshot.external_id == external_id,
            MarketplaceSnapshot.source_type == SourceType.LIVE.value,
        ).order_by(MarketplaceSnapshot.id)
    ).scalars())


# --------------------------------------------------------------------------
# Success, provenance, persistence
# --------------------------------------------------------------------------


def test_live_fetch_is_stored_with_provenance(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.Response(200, json=FIXTURE))
    response = collect(client, auth_headers, category="Audio")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_type"] == "live"
    assert body["provider"] == PROVIDER
    assert body["items_received"] == 3
    assert body["items_collected"] == 3

    [attempt] = attempts(db_session)
    assert attempt.outcome == "success"
    assert attempt.provider == PROVIDER
    assert attempt.source_type == "live"
    assert attempt.search_query == "wireless earbuds" and attempt.category == "Audio"
    assert attempt.collection_run_id == body["collection_run_id"]
    assert (attempt.items_received, attempt.items_stored) == (3, 3)
    assert attempt.finished_at is not None and attempt.error_message is None

    rows = db_session.execute(select(MarketplaceSnapshot).where(
        MarketplaceSnapshot.collection_run_id == body["collection_run_id"])).scalars().all()
    assert len(rows) == 3
    assert {row.source_type for row in rows} == {"live"}
    assert {row.search_query for row in rows} == {"wireless earbuds"}
    full = next(row for row in rows if row.external_id == "ACCFIXTURE0001")
    assert (full.price, full.original_price, full.rating, full.review_count) == (1999.0, 4999.0, None, None)
    assert full.collection_timestamp is not None


def test_no_credentials_are_persisted_logged_or_returned(client, auth_headers, flipkart, db_session, caplog):
    caplog.set_level(logging.DEBUG)
    flipkart.set(httpx.Response(200, json=FIXTURE))
    body = collect(client, auth_headers).json()
    status = client.get("/data/status", headers=auth_headers).text
    stored = [
        {column.name: getattr(row, column.name) for column in MarketplaceSnapshot.__table__.columns}
        for row in db_session.execute(select(MarketplaceSnapshot).where(
            MarketplaceSnapshot.collection_run_id == body["collection_run_id"])).scalars()
    ]
    logged = [{column.name: getattr(row, column.name) for column in CollectionAttempt.__table__.columns} for row in attempts(db_session)]
    everything = json.dumps([body, stored, logged], default=str) + status + caplog.text
    assert TOKEN not in everything
    assert AFFILIATE_ID not in everything
    assert "fixtureaffiliate" not in everything  # affiliate tracking id in productUrl


def test_status_reports_live_counts_and_fetch_times(client, auth_headers, flipkart):
    flipkart.set(httpx.Response(200, json=FIXTURE))
    collect(client, auth_headers)
    entry = flipkart_status(client, auth_headers)
    assert entry["available"] is True
    assert entry["state"] == "live"
    assert entry["provider"] == PROVIDER
    assert entry["live_records"] == 3
    assert entry["last_successful_fetch"] and entry["last_live_observation"]
    assert entry["last_failed_fetch"] is None
    assert "live" in entry["source_types_available"]


def test_collection_never_retrains_or_relabels_other_data(client, auth_headers, flipkart, db_session):
    client.post("/data/demo/load", headers=auth_headers)
    before_demo = db_session.query(MarketplaceSnapshot).filter_by(source_type="demo").count()
    models_before = db_session.query(ModelMetadata).count()
    flipkart.set(httpx.Response(200, json=FIXTURE))
    assert collect(client, auth_headers).status_code == 200
    db_session.expire_all()
    assert db_session.query(MarketplaceSnapshot).filter_by(source_type="demo").count() == before_demo
    assert db_session.query(ModelMetadata).count() == models_before


def test_analytics_refresh_sources_carry_runtime_state(client, auth_headers, flipkart):
    flipkart.state["approved"] = False
    sources = client.get("/analytics/summary", headers=auth_headers).json()["refresh_sources"]
    entry = next(item for item in sources if item["platform"] == "flipkart")
    assert entry["available"] is False
    assert entry["state"] == "approval_required"
    assert entry["required_configuration"] == ["FLIPKART_DATA_USE_APPROVED"]


# --------------------------------------------------------------------------
# Historical, append-only observations
# --------------------------------------------------------------------------


def test_changed_observations_are_appended_not_overwritten(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.Response(200, json=payload(price=1999.0)))
    assert collect(client, auth_headers).json()["items_collected"] == 1
    flipkart.set(httpx.Response(200, json=payload(price=1899.0)))
    assert collect(client, auth_headers).json()["items_collected"] == 1
    flipkart.set(httpx.Response(200, json=payload(price=1899.0, stock=False)))
    assert collect(client, auth_headers).json()["items_collected"] == 1
    rows = live_rows(db_session)
    assert [row.price for row in rows] == [1999.0, 1899.0, 1899.0]
    assert [row.availability for row in rows] == ["In Stock", "In Stock", "Out of Stock"]
    assert len({row.collection_run_id for row in rows}) == 3


def test_identical_repeat_fetch_is_skipped_as_a_true_duplicate(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.Response(200, json=payload()))
    first = collect(client, auth_headers).json()
    repeat = collect(client, auth_headers).json()
    assert first["items_collected"] == 1
    assert repeat["items_collected"] == 0
    assert repeat["duplicates_skipped"] == 1
    assert any("identical" in warning for warning in repeat["warnings"])
    rows = live_rows(db_session)
    assert len(rows) == 1 and rows[0].collection_run_id == first["collection_run_id"]
    assert [attempt.outcome for attempt in attempts(db_session)] == ["success", "success"]
    assert attempts(db_session)[1].duplicates_skipped == 1


def test_identical_observation_outside_the_window_is_new_history(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.Response(200, json=payload()))
    collect(client, auth_headers)
    earlier = datetime.now(timezone.utc) - timedelta(minutes=30)
    db_session.execute(update(MarketplaceSnapshot).where(
        MarketplaceSnapshot.platform == "flipkart", MarketplaceSnapshot.source_type == "live").values(collection_timestamp=earlier))
    db_session.commit()
    assert collect(client, auth_headers).json()["items_collected"] == 1
    assert len(live_rows(db_session)) == 2


# --------------------------------------------------------------------------
# Failures and runtime states
# --------------------------------------------------------------------------


def test_missing_credentials_returns_501_with_configuration_names(client, auth_headers, flipkart, db_session):
    flipkart.state["configured"] = False
    response = collect(client, auth_headers)
    assert response.status_code == 501
    assert "FLIPKART_AFFILIATE_TOKEN" in response.json()["detail"]
    assert flipkart.calls == 0 and attempts(db_session) == []
    entry = flipkart_status(client, auth_headers)
    assert entry["state"] == "credentials_missing"
    assert entry["required_configuration"] == ["FLIPKART_AFFILIATE_ID", "FLIPKART_AFFILIATE_TOKEN", "FLIPKART_DATA_USE_APPROVED"]


def test_unapproved_collection_is_refused_before_any_request(client, auth_headers, flipkart, db_session):
    flipkart.state["approved"] = False
    response = collect(client, auth_headers)
    assert response.status_code == 501
    assert "FLIPKART_DATA_USE_APPROVED" in response.json()["detail"]
    assert flipkart.calls == 0 and attempts(db_session) == []
    assert flipkart_status(client, auth_headers)["state"] == "approval_required"


def test_rate_limit_is_recorded_enforced_and_expires(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.Response(429, headers={"Retry-After": "120"}))
    response = collect(client, auth_headers)
    assert response.status_code == 429
    assert 100 <= int(response.headers["Retry-After"]) <= 120
    [attempt] = attempts(db_session)
    assert attempt.outcome == "rate_limited" and attempt.http_status == 429
    assert attempt.retry_after_at is not None

    entry = flipkart_status(client, auth_headers)
    assert entry["state"] == "rate_limited" and entry["available"] is False
    assert entry["retry_after"] and entry["last_failure_state"] == "rate_limited"

    calls = flipkart.calls
    blocked = collect(client, auth_headers)
    assert blocked.status_code == 429
    assert flipkart.calls == calls  # the provider was not contacted again
    assert len(attempts(db_session)) == 1

    db_session.execute(update(CollectionAttempt).where(CollectionAttempt.id == attempt.id).values(
        retry_after_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    db_session.commit()
    assert flipkart_status(client, auth_headers)["state"] == "live"
    flipkart.set(httpx.Response(200, json=payload()))
    assert collect(client, auth_headers).status_code == 200


def test_provider_error_is_visible_until_a_later_success(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.Response(503))
    response = collect(client, auth_headers)
    assert response.status_code == 502
    assert "HTTP 503" in response.json()["detail"]
    [attempt] = attempts(db_session)
    assert (attempt.outcome, attempt.error_code) == ("provider_error", "http_503")

    entry = flipkart_status(client, auth_headers)
    assert entry["state"] == "provider_error"
    assert entry["available"] is True  # a retry is allowed
    assert "503" in entry["reason"] and entry["last_failed_fetch"]
    assert live_rows(db_session) == []

    flipkart.set(httpx.Response(200, json=payload()))
    assert collect(client, auth_headers).status_code == 200
    recovered = flipkart_status(client, auth_headers)
    assert recovered["state"] == "live"
    assert recovered["last_failed_fetch"] and recovered["last_successful_fetch"] > recovered["last_failed_fetch"]


def test_rejected_credentials_are_reported_distinctly(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.Response(401, text=f"invalid {TOKEN}"))
    response = collect(client, auth_headers)
    assert response.status_code == 502
    assert "rejected" in response.json()["detail"]
    assert TOKEN not in response.text
    assert attempts(db_session)[0].outcome == "credentials_rejected"
    assert flipkart_status(client, auth_headers)["state"] == "credentials_rejected"


def test_timeout_is_logged_as_a_provider_error(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.ReadTimeout("slow"))
    response = collect(client, auth_headers)
    assert response.status_code == 502
    assert attempts(db_session)[0].error_code == "timeout"
    assert flipkart.calls == 3


def test_malformed_response_stores_nothing(client, auth_headers, flipkart, db_session):
    flipkart.set(httpx.Response(200, text="<html>maintenance</html>"))
    response = collect(client, auth_headers)
    assert response.status_code == 502
    [attempt] = attempts(db_session)
    assert attempt.error_code == "malformed_response" and attempt.items_stored == 0
    assert db_session.query(MarketplaceSnapshot).filter_by(collection_run_id=attempt.collection_run_id).count() == 0
