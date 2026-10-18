"""Scheduling, append-only storage and failure handling, with a scripted source (no network)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DatabaseError

from app.live_scraping.base import ObservationSource, TargetRef
from app.live_scraping.errors import ParseFailedError, ProductNotFoundError, RateLimitedError, SourceBlockedError
from app.live_scraping.schemas import Availability, Marketplace, ProductObservation as Obs
from app.live_scraping.service import (
    NOT_FOUND_DEACTIVATE_AFTER,
    PARSE_FAILURE_CIRCUIT,
    register_target,
    run_due_targets,
    status_report,
)
from app.models.live_scraping import (
    ObservationImmutableError,
    ProductObservation,
    ScrapeAttempt,
    ScrapeSourceState,
    ScrapeTarget,
)


class ScriptedSource(ObservationSource):
    """Returns (price) floats as observations or raises queued errors, per product id."""

    marketplace = Marketplace.AMAZON
    source_name = "amazon-test/1"

    def __init__(self, script: dict[str, list] | None = None, *, enabled: bool = True) -> None:
        self.script = script or {}
        self.calls: list[str] = []
        self._enabled = enabled

    def enabled(self):
        return (True, None) if self._enabled else (False, "disabled for test")

    def resolve(self, url_or_id: str) -> TargetRef:
        pid = url_or_id.strip().upper()
        return TargetRef(Marketplace.AMAZON, pid, f"https://www.amazon.in/dp/{pid}")

    def observe(self, target: TargetRef) -> Obs:
        self.calls.append(target.platform_product_id)
        queue = self.script.get(target.platform_product_id, [1000.0])
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return Obs(
            marketplace=Marketplace.AMAZON, platform_product_id=target.platform_product_id,
            product_url=target.product_url, collected_at=datetime.now(timezone.utc), source=self.source_name,
            product_name=f"Product {target.platform_product_id}", current_price=Decimal(str(item)).quantize(Decimal("0.01")),
            mrp=Decimal("2000.00"), availability=Availability.IN_STOCK,
        )


@pytest.fixture(autouse=True)
def _clean(db_session):
    for model in (ProductObservation, ScrapeAttempt, ScrapeSourceState, ScrapeTarget):
        db_session.execute(delete(model))
    db_session.commit()
    yield


def _later(minutes: float):
    return lambda: datetime.now(timezone.utc) + timedelta(minutes=minutes)


def _add(db, *pids, refresh=60):
    source = ScriptedSource()
    targets = [register_target(db, "amazon", pid, refresh_interval_minutes=refresh, source=source)[0] for pid in pids]
    db.commit()
    return targets


def test_register_is_idempotent(db_session):
    source = ScriptedSource()
    first, created = register_target(db_session, "amazon", "b0testac01", source=source)
    again, created_again = register_target(db_session, "amazon", "B0TESTAC01", source=source)
    assert created and not created_again and first.id == again.id


def test_each_run_appends_a_new_observation_and_never_overwrites(db_session):
    (target,) = _add(db_session, "B0TESTAC01", refresh=60)
    source = ScriptedSource({"B0TESTAC01": [1299.0, 1199.0]})

    first = run_due_targets(db_session, "amazon", source=source)
    assert first.stored == 1
    second = run_due_targets(db_session, "amazon", source=source, now=_later(61))
    assert second.stored == 1

    rows = db_session.execute(
        select(ProductObservation).where(ProductObservation.target_id == target.id).order_by(ProductObservation.id)
    ).scalars().all()
    assert [r.current_price for r in rows] == [Decimal("1299.00"), Decimal("1199.00")]
    assert rows[0].run_id != rows[1].run_id
    assert db_session.execute(select(ScrapeAttempt)).scalars().all().__len__() == 2


def test_not_due_targets_are_not_fetched(db_session):
    _add(db_session, "B0TESTAC01", refresh=60)
    source = ScriptedSource()
    run_due_targets(db_session, "amazon", source=source)
    assert run_due_targets(db_session, "amazon", source=source, now=_later(30)).attempted == 0
    assert source.calls == ["B0TESTAC01"]


def test_orm_refuses_to_update_an_observation(db_session):
    _add(db_session, "B0TESTAC01")
    run_due_targets(db_session, "amazon", source=ScriptedSource())
    row = db_session.execute(select(ProductObservation)).scalar_one()
    row.current_price = Decimal("1.00")
    with pytest.raises(ObservationImmutableError):
        db_session.flush()
    db_session.rollback()


def test_database_trigger_refuses_update(db_session):
    _add(db_session, "B0TESTAC01")
    run_due_targets(db_session, "amazon", source=ScriptedSource())
    with pytest.raises(DatabaseError, match="append-only"):
        db_session.execute(text("UPDATE product_observations SET current_price = 1"))
    db_session.rollback()


def test_block_marks_source_unavailable_and_stops_the_pass(db_session):
    _add(db_session, "B0AAAAAAA1", "B0AAAAAAA2", "B0AAAAAAA3")
    source = ScriptedSource({
        "B0AAAAAAA1": [1000.0],
        "B0AAAAAAA2": [SourceBlockedError("Amazon served a CAPTCHA challenge.", http_status=200)],
    })
    summary = run_due_targets(db_session, "amazon", source=source)

    assert summary.stored == 1
    assert source.calls == ["B0AAAAAAA1", "B0AAAAAAA2"]  # third never requested
    assert "CAPTCHA" in summary.source_unavailable
    state = db_session.get(ScrapeSourceState, "amazon")
    assert state.state == "unavailable" and state.outcome == "blocked"
    attempts = db_session.execute(select(ScrapeAttempt.outcome).order_by(ScrapeAttempt.id)).scalars().all()
    assert attempts == ["success", "blocked"]
    assert db_session.execute(select(ProductObservation)).scalars().all().__len__() == 1

    # The next pass during the cooldown makes no requests at all.
    again = run_due_targets(db_session, "amazon", source=source)
    assert again.attempted == 0 and again.source_unavailable
    assert source.calls == ["B0AAAAAAA1", "B0AAAAAAA2"]


def test_rate_limit_cooldown_uses_retry_after(db_session):
    _add(db_session, "B0AAAAAAA1")
    source = ScriptedSource({"B0AAAAAAA1": [RateLimitedError("HTTP 429", retry_after_seconds=120)]})
    run_due_targets(db_session, "amazon", source=source)
    state = db_session.get(ScrapeSourceState, "amazon")
    until = state.unavailable_until if state.unavailable_until.tzinfo else state.unavailable_until.replace(tzinfo=timezone.utc)
    assert timedelta(seconds=60) < until - datetime.now(timezone.utc) <= timedelta(seconds=121)


def test_source_recovers_after_cooldown(db_session):
    _add(db_session, "B0AAAAAAA1")
    source = ScriptedSource({"B0AAAAAAA1": [SourceBlockedError("blocked"), 900.0]})
    run_due_targets(db_session, "amazon", source=source)
    summary = run_due_targets(db_session, "amazon", source=source, now=_later(24 * 60))
    assert summary.stored == 1
    assert db_session.get(ScrapeSourceState, "amazon").state == "available"


def test_missing_product_is_deactivated_after_repeated_404s(db_session):
    (target,) = _add(db_session, "B0GONE0001")
    source = ScriptedSource({"B0GONE0001": [ProductNotFoundError("HTTP 404")]})
    for step in range(NOT_FOUND_DEACTIVATE_AFTER):
        run_due_targets(db_session, "amazon", source=source, now=_later(step * 24 * 60))
    db_session.refresh(target)
    assert target.is_active is False and target.last_outcome == "not_found"
    assert db_session.get(ScrapeSourceState, "amazon") is None  # a 404 is not a source problem


def test_repeated_parse_failures_trip_the_circuit(db_session):
    pids = [f"B0PARSE{n:03d}" for n in range(PARSE_FAILURE_CIRCUIT + 2)]
    _add(db_session, *pids)
    source = ScriptedSource({pid: [ParseFailedError("no title")] for pid in pids})
    summary = run_due_targets(db_session, "amazon", source=source)
    assert summary.attempted == PARSE_FAILURE_CIRCUIT
    assert "layout" in summary.source_unavailable


def test_disabled_source_makes_no_requests(db_session):
    _add(db_session, "B0AAAAAAA1")
    source = ScriptedSource(enabled=False)
    summary = run_due_targets(db_session, "amazon", source=source)
    assert summary.attempted == 0 and summary.source_unavailable == "disabled for test"
    assert source.calls == []


def test_status_report(db_session):
    _add(db_session, "B0AAAAAAA1")
    report = status_report(db_session)
    assert set(report) == {"amazon", "flipkart", "meesho"}
    assert report["amazon"]["targets"] == 1 and report["amazon"]["due_now"] == 1
    assert report["meesho"]["enabled"] is False
