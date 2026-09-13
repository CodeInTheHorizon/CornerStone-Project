"""Runs a collection, validates the results and persists snapshots.

Sits between the API layer and the collectors so route handlers stay thin and
the same logic is reachable from a future scheduled job.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MarketplaceSnapshot
from app.models.enums import Platform, SourceType
from app.scrapers import (
    CollectorRequestError,
    CollectorUnavailableError,
    UnknownPlatformError,
    get_collector,
)
from app.services.ingest import ingest
from app.scrapers.registry import effective_status

logger = logging.getLogger(__name__)

MAX_ITEMS_LIMIT = 100


@dataclass
class CollectionResult:
    platform: str
    keyword: str
    collection_run_id: str
    collection_timestamp: datetime
    items_collected: int = 0
    items_rejected: int = 0
    duplicates_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def run_collection(
    db: Session,
    *,
    platform: str,
    keyword: str,
    category: str | None = None,
    max_items: int = 20,
) -> CollectionResult:
    """Collect, validate, deduplicate and store one batch of listings.

    Propagates UnknownPlatformError, CollectorUnavailableError and
    CollectorRequestError so the API layer can map each to its own status
    code. Never returns fabricated rows on failure.
    """
    collector = get_collector(platform)  # raises UnknownPlatformError
    state = effective_status(collector.status())
    if not state.available:
        raise CollectorUnavailableError(state.reason or "Collector unavailable.")
    max_items = max(1, min(MAX_ITEMS_LIMIT, max_items))

    outcome = collector.collect(
        keyword=keyword, category=category, max_items=max_items
    )

    # Same ingest path as import and demo loading, so live rows cannot skip
    # validation or deduplication.
    ingested = ingest(
        db,
        outcome.records,
        source_type=SourceType.LIVE,
        search_query=keyword,
    )

    return CollectionResult(
        platform=collector.platform.value,
        keyword=keyword,
        collection_run_id=ingested.batch_id,
        collection_timestamp=ingested.timestamp,
        items_collected=ingested.stored,
        items_rejected=ingested.rejected,
        duplicates_skipped=ingested.duplicates,
        warnings=[*outcome.warnings, *ingested.warnings, *ingested.rejected_rows],
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
    "CollectorRequestError",
    "CollectorUnavailableError",
    "UnknownPlatformError",
    "last_collection_at",
    "latest_snapshots",
    "run_collection",
    "snapshot_counts",
    "snapshot_history",
    "source_types_by_platform",
]
