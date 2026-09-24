"""The single path every record takes into the database.

Live collection, CSV/JSON import and the demo dataset all converge here, so a
row can never enter storage having skipped validation, deduplication or the
provenance tag. The only thing that differs between them is `source_type`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MarketplaceSnapshot
from app.models.enums import SourceType
from app.scrapers.base import NormalizedRecord
from app.scrapers.validation import validate_record


@dataclass
class IngestResult:
    """Outcome of persisting one batch."""

    source_type: str
    batch_id: str
    timestamp: datetime
    stored: int = 0
    rejected: int = 0
    duplicates: int = 0
    platforms: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: Per-row rejection detail, for the import UI. Capped so a badly formed
    #: 10k-row file cannot produce a 10k-item response.
    rejected_rows: list[str] = field(default_factory=list)


MAX_REPORTED_REJECTIONS = 25

#: A LIVE observation identical to one stored for the same listing within this
#: window is a repeated fetch (e.g. a double-clicked refresh), not a new data
#: point. Anything that changed, or anything older, is appended as history.
LIVE_DUPLICATE_WINDOW = timedelta(minutes=10)

#: Observed values compared to decide whether a LIVE fetch repeated itself.
_OBSERVED_FIELDS = (
    "product_name", "price", "original_price", "discount_percentage", "currency",
    "rating", "review_count", "availability", "seller_name",
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def recent_live_duplicate(db: Session, record: NormalizedRecord) -> bool:
    """True when this LIVE record repeats a very recent stored observation.

    Historical LIVE rows are never updated or removed: this only decides
    whether to skip appending a copy that carries no new information.
    """
    if not record.external_id and not record.listing_url:
        return False  # no stable identity; never risk dropping a real observation
    observed_at = _utc(record.collection_timestamp)
    stmt = select(MarketplaceSnapshot).where(
        MarketplaceSnapshot.source_type == SourceType.LIVE.value,
        MarketplaceSnapshot.platform == record.platform,
        MarketplaceSnapshot.collection_timestamp >= observed_at - LIVE_DUPLICATE_WINDOW,
        MarketplaceSnapshot.collection_timestamp <= observed_at,
    )
    stmt = stmt.where(
        MarketplaceSnapshot.external_id == record.external_id
        if record.external_id
        else MarketplaceSnapshot.listing_url == record.listing_url
    )
    for stored in db.execute(stmt.order_by(MarketplaceSnapshot.collection_timestamp.desc()).limit(5)).scalars():
        if all(getattr(stored, name) == getattr(record, name) for name in _OBSERVED_FIELDS):
            return True
    return False


def deduplicate(
    records: list[NormalizedRecord],
    *,
    include_timestamp: bool = False,
) -> tuple[list[NormalizedRecord], int]:
    """Drop repeats within one batch, keeping the first occurrence.

    See NormalizedRecord.dedupe_key for why imported/demo batches key on the
    timestamp as well.
    """
    seen: set[str] = set()
    unique: list[NormalizedRecord] = []
    skipped = 0

    for record in records:
        key = record.dedupe_key(include_timestamp=include_timestamp)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        unique.append(record)

    return unique, skipped


def to_snapshot(
    record: NormalizedRecord,
    *,
    source_type: str,
    search_query: str | None,
    batch_id: str,
    warnings: list[str],
) -> MarketplaceSnapshot:
    return MarketplaceSnapshot(
        platform=record.platform,
        source_type=source_type,
        search_query=search_query,
        collection_run_id=batch_id,
        product_name=record.product_name,
        brand=record.brand,
        category=record.category,
        subcategory=record.subcategory,
        external_id=record.external_id,
        image_url=record.image_url,
        image_urls=record.image_urls,
        price=record.price,
        original_price=record.original_price,
        discount_percentage=record.discount_percentage,
        currency=record.currency,
        rating=record.rating,
        review_count=record.review_count,
        availability=record.availability,
        seller_name=record.seller_name,
        seller_count=record.seller_count,
        offer_count=record.offer_count,
        listing_url=record.listing_url,
        min_order_qty=record.min_order_qty,
        price_min=record.price_min,
        price_max=record.price_max,
        supplier_years=record.supplier_years,
        shipping_info=record.shipping_info,
        delivery_time=record.delivery_time,
        badge=record.badge,
        sponsored=record.sponsored,
        specifications=record.specifications,
        stock_status=record.stock_status,
        warnings=warnings or None,
        collection_timestamp=record.collection_timestamp,
    )


def ingest(
    db: Session,
    records: list[NormalizedRecord],
    *,
    source_type: SourceType,
    search_query: str | None = None,
    batch_id: str | None = None,
    row_labels: list[str] | None = None,
) -> IngestResult:
    """Validate, deduplicate and persist a batch of normalized records.

    `row_labels` lets a caller name each incoming record (e.g. "row 12") so
    rejections can be reported against the source file.
    """
    batch_id = batch_id or str(uuid.uuid4())
    result = IngestResult(
        source_type=source_type.value,
        batch_id=batch_id,
        timestamp=datetime.now(timezone.utc),
    )

    labels = row_labels or [f"record {i + 1}" for i in range(len(records))]
    labelled = list(zip(records, labels, strict=False))

    # A live run sees each listing once; an imported or demo dataset carries
    # the same listing across many dates and must keep every one.
    keyed_by_time = source_type is not SourceType.LIVE

    # Deduplicate before validating: identical rows should be reported once.
    unique_records, duplicates = deduplicate(
        [r for r, _ in labelled], include_timestamp=keyed_by_time
    )
    result.duplicates = duplicates
    label_by_key = {
        r.dedupe_key(include_timestamp=keyed_by_time): label
        for r, label in labelled
    }

    snapshots: list[MarketplaceSnapshot] = []
    platforms: set[str] = set()

    for record in unique_records:
        validation = validate_record(record)
        label = label_by_key.get(
            record.dedupe_key(include_timestamp=keyed_by_time), "record"
        )

        if not validation.is_valid:
            result.rejected += 1
            if len(result.rejected_rows) < MAX_REPORTED_REJECTIONS:
                result.rejected_rows.append(
                    f"{label}: {validation.rejected_reason}"
                )
            continue

        if source_type is SourceType.LIVE and recent_live_duplicate(db, validation.record):
            result.duplicates += 1
            continue

        platforms.add(validation.record.platform)
        snapshots.append(
            to_snapshot(
                validation.record,
                source_type=source_type.value,
                search_query=search_query,
                batch_id=batch_id,
                warnings=validation.warnings,
            )
        )

    if snapshots:
        db.add_all(snapshots)
        db.commit()

    result.stored = len(snapshots)
    result.platforms = sorted(platforms)

    if duplicates:
        result.warnings.append(
            f"Skipped {duplicates} duplicate record(s) within this batch."
        )
    repeated = result.duplicates - duplicates
    if repeated:
        result.warnings.append(
            f"Skipped {repeated} LIVE observation(s) identical to one stored for the same "
            f"listing in the last {int(LIVE_DUPLICATE_WINDOW.total_seconds() // 60)} minutes."
        )
    if result.rejected > len(result.rejected_rows):
        result.warnings.append(
            f"{result.rejected - len(result.rejected_rows)} further rejection(s) "
            "not listed."
        )

    return result
