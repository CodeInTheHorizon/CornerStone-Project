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
from app.models.enums import DataSource, Platform
from app.scrapers import (
    CollectorRequestError,
    CollectorUnavailableError,
    UnknownPlatformError,
    get_collector,
)
from app.scrapers.base import NormalizedRecord
from app.scrapers.validation import validate_record

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


def _dedupe(
    records: list[NormalizedRecord],
) -> tuple[list[NormalizedRecord], int]:
    """Drop repeats within one run, keeping the first occurrence."""
    seen: set[str] = set()
    unique: list[NormalizedRecord] = []
    skipped = 0

    for record in records:
        key = record.dedupe_key()
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        unique.append(record)

    return unique, skipped


def _to_snapshot(
    record: NormalizedRecord,
    *,
    keyword: str,
    run_id: str,
    warnings: list[str],
) -> MarketplaceSnapshot:
    return MarketplaceSnapshot(
        platform=record.platform,
        source=DataSource.LIVE.value,
        search_query=keyword,
        collection_run_id=run_id,
        product_name=record.product_name,
        brand=record.brand,
        category=record.category,
        subcategory=record.subcategory,
        external_id=record.external_id,
        price=record.price,
        original_price=record.original_price,
        discount_percentage=record.discount_percentage,
        currency=record.currency,
        rating=record.rating,
        review_count=record.review_count,
        availability=record.availability,
        seller_name=record.seller_name,
        listing_url=record.listing_url,
        shipping_info=record.shipping_info,
        delivery_time=record.delivery_time,
        badge=record.badge,
        sponsored=record.sponsored,
        specifications=record.specifications,
        stock_status=record.stock_status,
        warnings=warnings or None,
        collection_timestamp=record.collection_timestamp,
    )


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
    max_items = max(1, min(MAX_ITEMS_LIMIT, max_items))

    outcome = collector.collect(
        keyword=keyword, category=category, max_items=max_items
    )

    unique, duplicates = _dedupe(outcome.records)

    run_id = str(uuid.uuid4())
    result = CollectionResult(
        platform=collector.platform.value,
        keyword=keyword,
        collection_run_id=run_id,
        collection_timestamp=datetime.now(timezone.utc),
        duplicates_skipped=duplicates,
        warnings=list(outcome.warnings),
    )

    snapshots: list[MarketplaceSnapshot] = []
    for record in unique:
        validation = validate_record(record)
        if not validation.is_valid:
            result.items_rejected += 1
            result.warnings.append(
                f"Rejected a record: {validation.rejected_reason}."
            )
            continue

        snapshots.append(
            _to_snapshot(
                validation.record,
                keyword=keyword,
                run_id=run_id,
                warnings=validation.warnings,
            )
        )

    if snapshots:
        db.add_all(snapshots)
        db.commit()

    result.items_collected = len(snapshots)

    if duplicates:
        result.warnings.append(
            f"Skipped {duplicates} duplicate listing(s) within this run."
        )

    return result


def latest_snapshots(
    db: Session,
    *,
    platform: str | None = None,
    keyword: str | None = None,
    category: str | None = None,
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

    return list(db.execute(stmt.limit(limit)).scalars())


def snapshot_history(
    db: Session,
    *,
    platform: str | None = None,
    product: str | None = None,
    category: str | None = None,
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
]
