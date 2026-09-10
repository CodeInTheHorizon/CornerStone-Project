"""The single path every record takes into the database.

Live collection, CSV/JSON import and the demo dataset all converge here, so a
row can never enter storage having skipped validation, deduplication or the
provenance tag. The only thing that differs between them is `source_type`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

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
    if result.rejected > len(result.rejected_rows):
        result.warnings.append(
            f"{result.rejected - len(result.rejected_rows)} further rejection(s) "
            "not listed."
        )

    return result
