"""Runs a collection, validates the results and persists snapshots.

Sits between the API layer and the collectors so route handlers stay thin and
the same logic is reachable from a future scheduled job.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CollectionAttempt, MarketplaceSnapshot
from app.models.enums import AttemptOutcome, CollectorState, Platform, SourceType
from app.scrapers import (
    CollectorRateLimitedError,
    CollectorRequestError,
    CollectorStatus,
    CollectorUnavailableError,
    UnknownPlatformError,
    all_statuses,
    get_collector,
)
from app.services.ingest import ingest
from app.scrapers.registry import effective_status

logger = logging.getLogger(__name__)

MAX_ITEMS_LIMIT = 100

_FAILURE_OUTCOMES = (
    AttemptOutcome.RATE_LIMITED.value,
    AttemptOutcome.CREDENTIALS_REJECTED.value,
    AttemptOutcome.PROVIDER_ERROR.value,
)
_SUCCESS_OUTCOMES = (AttemptOutcome.SUCCESS.value, AttemptOutcome.EMPTY.value)


@dataclass
class CollectionResult:
    platform: str
    keyword: str
    collection_run_id: str
    collection_timestamp: datetime
    source_type: str = SourceType.LIVE.value
    provider: str | None = None
    items_received: int = 0
    items_collected: int = 0
    items_rejected: int = 0
    duplicates_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def active_cooldown(db: Session, platform: str, now: datetime | None = None) -> datetime | None:
    """When a provider's rate-limit window is still open, the time it ends."""
    now = now or datetime.now(timezone.utc)
    latest = latest_attempt(db, platform)
    if latest is None or latest.outcome != AttemptOutcome.RATE_LIMITED.value:
        return None
    retry_at = _utc(latest.retry_after_at)
    return retry_at if retry_at is not None and retry_at > now else None


def run_collection(
    db: Session,
    *,
    platform: str,
    keyword: str,
    category: str | None = None,
    max_items: int = 20,
) -> CollectionResult:
    """Fetch LIVE listings, validate, deduplicate, store and log the attempt.

    Propagates UnknownPlatformError, CollectorUnavailableError and
    CollectorRequestError (including its rate-limit and credential subclasses)
    so the API layer can map each to its own status code. Every call that
    reaches the provider is recorded in collection_attempts, failures included.
    Never returns fabricated rows on failure and never retrains a model.
    """
    collector = get_collector(platform)  # raises UnknownPlatformError
    state = effective_status(collector.status())
    if not state.available:
        raise CollectorUnavailableError(state.reason or "Collector unavailable.")

    platform_name = collector.platform.value
    retry_at = active_cooldown(db, platform_name)
    if retry_at is not None:
        # Respect the provider's window instead of sending another request.
        raise CollectorRateLimitedError(
            f"{platform_name.title()} rate-limited the last request. Try again after "
            f"{retry_at.isoformat(timespec='seconds')}.",
            retry_after_seconds=max(1.0, (retry_at - datetime.now(timezone.utc)).total_seconds()),
            code="cooldown",
            http_status=None,
        )

    max_items = max(1, min(MAX_ITEMS_LIMIT, max_items))
    run_id = str(uuid.uuid4())
    attempt = CollectionAttempt(
        platform=platform_name,
        provider=(state.provider or collector.access_method)[:64],
        source_type=SourceType.LIVE.value,
        collection_run_id=run_id,
        search_query=keyword[:255],
        category=category[:120] if category else None,
        max_items=max_items,
        started_at=datetime.now(timezone.utc),
        outcome=AttemptOutcome.SUCCESS.value,
    )

    try:
        outcome = collector.collect(keyword=keyword, category=category, max_items=max_items)
    except CollectorRequestError as exc:
        _record_failure(db, attempt, exc)
        raise
    except CollectorUnavailableError:
        raise
    except Exception as exc:
        # A collector bug still leaves an honest trace, never a silent success.
        _record_failure(db, attempt, CollectorRequestError(
            f"Unexpected collector failure ({type(exc).__name__}).", code="unexpected_error"
        ))
        raise

    # The attempt commits together with the snapshots it produced, so every
    # LIVE row has provenance. Same ingest path as import and demo loading.
    db.add(attempt)
    ingested = ingest(
        db,
        outcome.records,
        source_type=SourceType.LIVE,
        search_query=keyword,
        batch_id=run_id,
    )
    attempt.finished_at = datetime.now(timezone.utc)
    attempt.items_received = len(outcome.records)
    attempt.items_stored = ingested.stored
    attempt.items_rejected = ingested.rejected
    attempt.duplicates_skipped = ingested.duplicates
    attempt.outcome = (AttemptOutcome.SUCCESS if outcome.records else AttemptOutcome.EMPTY).value
    db.commit()

    logger.info(
        "LIVE collection %s on %s: received=%d stored=%d duplicates=%d rejected=%d",
        run_id, platform_name, attempt.items_received, ingested.stored, ingested.duplicates, ingested.rejected,
    )
    return CollectionResult(
        platform=platform_name,
        keyword=keyword,
        collection_run_id=run_id,
        collection_timestamp=ingested.timestamp,
        provider=attempt.provider,
        items_received=attempt.items_received,
        items_collected=ingested.stored,
        items_rejected=ingested.rejected,
        duplicates_skipped=ingested.duplicates,
        warnings=[*outcome.warnings, *ingested.warnings, *ingested.rejected_rows],
    )


def _record_failure(db: Session, attempt: CollectionAttempt, exc: CollectorRequestError) -> None:
    now = datetime.now(timezone.utc)
    attempt.finished_at = now
    attempt.outcome = exc.outcome.value
    attempt.error_code = (getattr(exc, "code", None) or "provider_error")[:64]
    attempt.error_message = str(exc)[:500]
    attempt.http_status = getattr(exc, "http_status", None)
    retry_after = getattr(exc, "retry_after_seconds", None)
    if isinstance(exc, CollectorRateLimitedError) and retry_after is not None:
        attempt.retry_after_at = now + timedelta(seconds=retry_after)
    db.rollback()  # never persist partial work from a failed fetch
    db.add(attempt)
    db.commit()
    logger.warning(
        "LIVE collection %s on %s failed: outcome=%s code=%s",
        attempt.collection_run_id, attempt.platform, attempt.outcome, attempt.error_code,
    )


# --------------------------------------------------------------------------
# Status: the collector's static state overlaid with its latest attempt
# --------------------------------------------------------------------------


def latest_attempt(db: Session, platform: str) -> CollectionAttempt | None:
    return db.execute(
        select(CollectionAttempt)
        .where(CollectionAttempt.platform == platform)
        .order_by(CollectionAttempt.started_at.desc(), CollectionAttempt.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _latest_with_outcomes(db: Session, platform: str, outcomes: tuple[str, ...]) -> CollectionAttempt | None:
    return db.execute(
        select(CollectionAttempt)
        .where(CollectionAttempt.platform == platform, CollectionAttempt.outcome.in_(outcomes))
        .order_by(CollectionAttempt.started_at.desc(), CollectionAttempt.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def runtime_status(db: Session, status: CollectorStatus, now: datetime | None = None) -> CollectorStatus:
    """Apply the latest fetch outcome to a configured collector's status.

    Static blockers (credentials missing, approval required, unavailable) win.
    For a LIVE-capable collector: an open rate-limit window blocks collection;
    rejected credentials or a provider failure stay visible until a later
    fetch succeeds, without blocking a retry.
    """
    if status.state is not CollectorState.LIVE:
        return status
    now = now or datetime.now(timezone.utc)
    latest = latest_attempt(db, status.platform)
    if latest is None or latest.outcome in _SUCCESS_OUTCOMES:
        return status
    if latest.outcome == AttemptOutcome.RATE_LIMITED.value:
        retry_at = _utc(latest.retry_after_at)
        if retry_at is not None and retry_at > now:
            return replace(
                status, available=False, state=CollectorState.RATE_LIMITED,
                reason=f"The provider rate-limited the last request. Collection resumes after {retry_at.isoformat(timespec='seconds')}.",
            )
        return status
    if latest.outcome == AttemptOutcome.CREDENTIALS_REJECTED.value:
        return replace(status, state=CollectorState.CREDENTIALS_REJECTED, reason=latest.error_message)
    return replace(status, state=CollectorState.PROVIDER_ERROR, reason=latest.error_message)


def platform_statuses(db: Session, statuses: dict[str, CollectorStatus] | None = None) -> dict[str, CollectorStatus]:
    """Every platform's effective, runtime-aware collector status."""
    statuses = statuses if statuses is not None else all_statuses()
    return {name: runtime_status(db, effective_status(state)) for name, state in statuses.items()}


@dataclass
class FetchHistory:
    last_successful_fetch: datetime | None = None
    last_failed_fetch: datetime | None = None
    last_failure_outcome: str | None = None
    last_failure_reason: str | None = None
    retry_after: datetime | None = None
    live_records: int = 0
    last_live_observation: datetime | None = None


def fetch_history(db: Session, platform: str) -> FetchHistory:
    success = _latest_with_outcomes(db, platform, _SUCCESS_OUTCOMES)
    failure = _latest_with_outcomes(db, platform, _FAILURE_OUTCOMES)
    live_count, live_last = db.execute(
        select(func.count(MarketplaceSnapshot.id), func.max(MarketplaceSnapshot.collection_timestamp)).where(
            MarketplaceSnapshot.platform == platform,
            MarketplaceSnapshot.source_type == SourceType.LIVE.value,
        )
    ).one()
    return FetchHistory(
        last_successful_fetch=_utc(success.finished_at or success.started_at) if success else None,
        last_failed_fetch=_utc(failure.finished_at or failure.started_at) if failure else None,
        last_failure_outcome=failure.outcome if failure else None,
        last_failure_reason=failure.error_message if failure else None,
        retry_after=active_cooldown(db, platform),
        live_records=live_count or 0,
        last_live_observation=_utc(live_last),
    )


def latest_snapshots(
    db: Session,
    *,
    platform: str | None = None,
    keyword: str | None = None,
    category: str | None = None,
    source_type: str | None = None,
    limit: int = 50,
) -> list[MarketplaceSnapshot]:
    """Most recently collected snapshots, newest first."""
    stmt = select(MarketplaceSnapshot).order_by(
        MarketplaceSnapshot.collection_timestamp.desc(),
        MarketplaceSnapshot.id.desc(),
    )

    if platform:
        stmt = stmt.where(MarketplaceSnapshot.platform == platform.lower())
    if keyword:
        stmt = stmt.where(MarketplaceSnapshot.search_query.ilike(f"%{keyword}%"))
    if category:
        stmt = stmt.where(MarketplaceSnapshot.category.ilike(f"%{category}%"))
    if source_type:
        stmt = stmt.where(MarketplaceSnapshot.source_type == source_type)

    return list(db.execute(stmt.limit(limit)).scalars())


def snapshot_history(
    db: Session,
    *,
    platform: str | None = None,
    product: str | None = None,
    category: str | None = None,
    source_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 200,
) -> list[MarketplaceSnapshot]:
    """Stored snapshots over a window, oldest first for time-series reading."""
    stmt = select(MarketplaceSnapshot).order_by(
        MarketplaceSnapshot.collection_timestamp.asc(),
        MarketplaceSnapshot.id.asc(),
    )

    if platform:
        stmt = stmt.where(MarketplaceSnapshot.platform == platform.lower())
    if product:
        stmt = stmt.where(MarketplaceSnapshot.product_name.ilike(f"%{product}%"))
    if category:
        stmt = stmt.where(MarketplaceSnapshot.category.ilike(f"%{category}%"))
    if source_type:
        stmt = stmt.where(MarketplaceSnapshot.source_type == source_type)
    if start:
        stmt = stmt.where(MarketplaceSnapshot.collection_timestamp >= start)
    if end:
        stmt = stmt.where(MarketplaceSnapshot.collection_timestamp <= end)

    return list(db.execute(stmt.limit(limit)).scalars())


def last_collection_at(db: Session, platform: str) -> datetime | None:
    """Timestamp of the most recent snapshot for a platform, if any."""
    return db.execute(
        select(func.max(MarketplaceSnapshot.collection_timestamp)).where(
            MarketplaceSnapshot.platform == platform
        )
    ).scalar_one_or_none()


def snapshot_counts(db: Session) -> dict[str, int]:
    """Stored snapshot count per platform."""
    rows = db.execute(
        select(MarketplaceSnapshot.platform, func.count(MarketplaceSnapshot.id))
        .group_by(MarketplaceSnapshot.platform)
    ).all()
    counts = {platform.value: 0 for platform in Platform}
    counts.update({row[0]: row[1] for row in rows})
    return counts


def source_types_by_platform(db: Session) -> dict[str, list[str]]:
    """Which provenance types are actually stored for each platform.

    Drives the "Available data: IMPORTED / DEMO" line in the UI, so it reflects
    what is really in the database rather than what might be possible.
    """
    rows = db.execute(
        select(MarketplaceSnapshot.platform, MarketplaceSnapshot.source_type)
        .distinct()
    ).all()

    found: dict[str, set[str]] = {platform.value: set() for platform in Platform}
    for platform_name, source_type in rows:
        found.setdefault(platform_name, set()).add(source_type)

    # Ordered live -> imported -> demo, most authoritative first.
    order = [s.value for s in (SourceType.LIVE, SourceType.IMPORTED, SourceType.DEMO)]
    return {
        name: [value for value in order if value in types]
        for name, types in found.items()
    }


__all__ = [
    "CollectionResult",
    "CollectorRateLimitedError",
    "CollectorRequestError",
    "CollectorUnavailableError",
    "FetchHistory",
    "UnknownPlatformError",
    "active_cooldown",
    "fetch_history",
    "last_collection_at",
    "latest_attempt",
    "latest_snapshots",
    "platform_statuses",
    "run_collection",
    "runtime_status",
    "snapshot_counts",
    "snapshot_history",
    "source_types_by_platform",
]
