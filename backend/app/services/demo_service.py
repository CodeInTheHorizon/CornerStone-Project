"""Loads the bundled synthetic demo dataset.

The dataset is a development and testing fixture: generated values, invented
brands, not real market data. It exists so the dataset builder and ML pipeline
in later phases are testable while three of four marketplaces cannot be
collected from.

Every row is stored with source_type = "demo" and must never be presented as a
live marketplace observation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarketplaceSnapshot
from app.models.enums import SourceType
from app.scrapers.base import NormalizedRecord
from app.services.ingest import IngestResult, ingest

DEMO_FILE = settings.DATA_DIR / "demo" / "electronics_snapshots.json"


class DemoDatasetMissingError(FileNotFoundError):
    """The bundled demo dataset file is not present."""


@lru_cache(maxsize=1)
def _load_payload() -> dict[str, Any]:
    if not DEMO_FILE.exists():
        raise DemoDatasetMissingError(
            f"Demo dataset not found at {DEMO_FILE}. Regenerate it with "
            "`python scripts/generate_demo_dataset.py`."
        )
    return json.loads(DEMO_FILE.read_text(encoding="utf-8"))


def _to_record(row: dict[str, Any]) -> NormalizedRecord:
    raw = row.get("collection_timestamp")
    timestamp = (
        datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if raw
        else datetime.now(timezone.utc)
    )
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return NormalizedRecord(
        platform=row["platform"],
        product_name=row["product_name"],
        brand=row.get("brand"),
        category=row.get("category"),
        subcategory=row.get("subcategory"),
        external_id=row.get("external_id"),
        price=row.get("price"),
        original_price=row.get("original_price"),
        discount_percentage=row.get("discount_percentage"),
        currency=row.get("currency") or "INR",
        rating=row.get("rating"),
        review_count=row.get("review_count"),
        availability=row.get("availability"),
        seller_name=row.get("seller_name"),
        listing_url=row.get("listing_url"),
        shipping_info=row.get("shipping_info"),
        delivery_time=row.get("delivery_time"),
        badge=row.get("badge"),
        sponsored=row.get("sponsored"),
        stock_status=row.get("stock_status"),
        collection_timestamp=timestamp,
    )


def describe() -> dict[str, Any]:
    """Summary of the bundled dataset, without loading it into the database."""
    payload = _load_payload()
    records = payload.get("records", [])
    return {
        "available": True,
        "record_count": len(records),
        "platforms": sorted({row["platform"] for row in records}),
        "categories": sorted({row["category"] for row in records if row.get("category")}),
        "path": str(DEMO_FILE),
    }


def load_demo_dataset(db: Session, *, replace: bool = True) -> IngestResult:
    """Insert the demo dataset as DEMO-tagged snapshots.

    `replace` clears previously loaded demo rows first, so repeated loads do
    not accumulate copies. Only demo rows are removed -- live and imported data
    is never touched.
    """
    payload = _load_payload()
    rows = payload.get("records", [])

    if replace:
        db.execute(
            delete(MarketplaceSnapshot).where(
                MarketplaceSnapshot.source_type == SourceType.DEMO.value
            )
        )
        db.commit()

    records = [_to_record(row) for row in rows]

    return ingest(
        db,
        records,
        source_type=SourceType.DEMO,
        search_query="demo dataset",
    )


def demo_row_count(db: Session) -> int:
    return (
        db.execute(
            select(func.count(MarketplaceSnapshot.id)).where(
                MarketplaceSnapshot.source_type == SourceType.DEMO.value
            )
        ).scalar_one()
        or 0
    )
