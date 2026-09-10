"""Turns stored MarketplaceSnapshot rows into an ML-ready table.

Pipeline: filter -> clean -> normalize -> deduplicate -> sort -> engineer
features -> metadata.

Two rules run through the whole thing:

* **Provenance survives.** `source_type` is carried on every row and recorded
  in the metadata. A dataset built from demo records is marked as such at every
  layer, so no later phase can quietly report synthetic results as real.
* **Nothing is invented.** Rows are dropped only when an essential field is
  unusable, and every drop is counted with a reason. Missing optional values
  stay missing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import features as feature_module
from app.ml.normalization import (
    is_known_platform,
    normalize_brand,
    normalize_category,
    normalize_platform,
    normalize_product_name,
    product_key,
)
from app.models import MarketplaceSnapshot
from app.models.enums import SourceType

#: Columns read out of the database before any processing.
SOURCE_COLUMNS = [
    "id",
    "platform",
    "source_type",
    "search_query",
    "product_name",
    "brand",
    "category",
    "subcategory",
    "external_id",
    "price",
    "original_price",
    "discount_percentage",
    "currency",
    "rating",
    "review_count",
    "availability",
    "seller_name",
    "collection_timestamp",
]

#: Identity columns kept alongside the engineered features in the output.
IDENTITY_COLUMNS = [
    "snapshot_id",
    "platform",
    "source_type",
    "product_key",
    "product_name",
    "brand_normalized",
    "category_normalized",
    "external_id",
    "currency",
    "collection_timestamp",
]

MAX_RATING = 5.0


@dataclass
class DatasetFilters:
    """What subset of stored snapshots to build from."""

    platforms: list[str] | None = None
    categories: list[str] | None = None
    keyword: str | None = None
    source_types: list[SourceType] | None = None
    start: datetime | None = None
    end: datetime | None = None


@dataclass
class DatasetMetadata:
    dataset_id: str
    generated_at: datetime
    total_input_rows: int
    total_output_rows: int
    removed_rows: int
    removal_reasons: dict[str, int] = field(default_factory=dict)
    platforms: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)
    date_range: dict[str, str | None] = field(default_factory=dict)
    feature_count: int = 0
    feature_names: list[str] = field(default_factory=list)
    products: int = 0
    dataset_version: str = "1.0"
    #: True when any row came from the synthetic fixture.
    contains_demo_data: bool = False
    #: True when every row is synthetic.
    demo_only: bool = False
    csv_path: str | None = None
    metadata_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "generated_at": self.generated_at.isoformat(),
            "total_input_rows": self.total_input_rows,
            "total_output_rows": self.total_output_rows,
            "removed_rows": self.removed_rows,
            "removal_reasons": self.removal_reasons,
            "platforms": self.platforms,
            "categories": self.categories,
            "source_types": self.source_types,
            "date_range": self.date_range,
            "feature_count": self.feature_count,
            "feature_names": self.feature_names,
            "products": self.products,
            "dataset_version": self.dataset_version,
            "contains_demo_data": self.contains_demo_data,
            "demo_only": self.demo_only,
            "csv_path": self.csv_path,
            "metadata_path": self.metadata_path,
        }


@dataclass
class DatasetResult:
    frame: pd.DataFrame
    metadata: DatasetMetadata

    @property
    def is_empty(self) -> bool:
        return self.frame.empty


class InsufficientDataError(Exception):
    """No rows survived filtering or cleaning.

    Carries the reason so the API can say which stage emptied the dataset
    rather than returning a bare zero-row result.
    """

    def __init__(self, reason: str, metadata: DatasetMetadata | None = None):
        super().__init__(reason)
        self.reason = reason
        self.metadata = metadata


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_snapshots(db: Session, filters: DatasetFilters) -> pd.DataFrame:
    """Read matching snapshots into a frame. No cleaning yet."""
    stmt = select(*[getattr(MarketplaceSnapshot, name) for name in SOURCE_COLUMNS])

    if filters.platforms:
        wanted = [normalize_platform(p) for p in filters.platforms]
        stmt = stmt.where(MarketplaceSnapshot.platform.in_(wanted))

    if filters.source_types:
        stmt = stmt.where(
            MarketplaceSnapshot.source_type.in_(
                [s.value for s in filters.source_types]
            )
        )

    if filters.categories:
        # Matched loosely here, then normalized properly after loading.
        clauses = [
            MarketplaceSnapshot.category.ilike(f"%{c}%") for c in filters.categories
        ]
        from sqlalchemy import or_

        stmt = stmt.where(or_(*clauses))

    if filters.keyword:
        from sqlalchemy import or_

        stmt = stmt.where(
            or_(
                MarketplaceSnapshot.product_name.ilike(f"%{filters.keyword}%"),
                MarketplaceSnapshot.search_query.ilike(f"%{filters.keyword}%"),
            )
        )

    if filters.start:
        stmt = stmt.where(MarketplaceSnapshot.collection_timestamp >= filters.start)
    if filters.end:
        stmt = stmt.where(MarketplaceSnapshot.collection_timestamp <= filters.end)

    rows = db.execute(stmt).all()
    return pd.DataFrame(rows, columns=SOURCE_COLUMNS)


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------


def clean(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Drop unusable rows, repair repairable values, count every removal.

    Essential fields are product name, platform and timestamp: without them a
    row cannot be grouped, compared or ordered. Everything else is allowed to
    be missing.
    """
    reasons: dict[str, int] = {}
    if frame.empty:
        return frame, reasons

    out = frame.copy()
    before = len(out)

    def record(reason: str, mask: pd.Series) -> pd.DataFrame:
        nonlocal out
        removed = int(mask.sum())
        if removed:
            reasons[reason] = reasons.get(reason, 0) + removed
            out = out.loc[~mask].copy()
        return out

    # -- Essential fields -------------------------------------------------
    out["product_name"] = out["product_name"].astype("object").where(
        out["product_name"].notna(), None
    )
    blank_name = out["product_name"].isna() | (
        out["product_name"].astype(str).str.strip() == ""
    )
    out = record("missing_product_name", blank_name)

    out = record("missing_platform", out["platform"].isna())
    out = record("unknown_platform", ~out["platform"].map(is_known_platform))

    out["collection_timestamp"] = pd.to_datetime(
        out["collection_timestamp"], errors="coerce", utc=True
    )
    out = record("invalid_timestamp", out["collection_timestamp"].isna())

    # -- Numeric coercion: unparseable becomes NaN, not a guess -----------
    for column in ("price", "original_price", "discount_percentage", "rating"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out["review_count"] = pd.to_numeric(out["review_count"], errors="coerce")

    # -- Repairable values: clear the field, keep the row -----------------
    # Each of these is a bad reading of one field, not an unusable observation.
    negative_price = out["price"].notna() & (out["price"] < 0)
    if negative_price.any():
        reasons["cleared_negative_price"] = int(negative_price.sum())
        out.loc[negative_price, "price"] = pd.NA

    negative_original = out["original_price"].notna() & (out["original_price"] < 0)
    if negative_original.any():
        reasons["cleared_negative_original_price"] = int(negative_original.sum())
        out.loc[negative_original, "original_price"] = pd.NA

    bad_rating = out["rating"].notna() & (
        (out["rating"] < 0) | (out["rating"] > MAX_RATING)
    )
    if bad_rating.any():
        reasons["cleared_invalid_rating"] = int(bad_rating.sum())
        out.loc[bad_rating, "rating"] = pd.NA

    negative_reviews = out["review_count"].notna() & (out["review_count"] < 0)
    if negative_reviews.any():
        reasons["cleared_negative_review_count"] = int(negative_reviews.sum())
        out.loc[negative_reviews, "review_count"] = pd.NA

    # -- A row with no price at all cannot support any price feature ------
    no_price = out["price"].isna() & out["original_price"].isna()
    out = record("no_usable_price", no_price)

    # -- Empty strings become null ----------------------------------------
    for column in ("brand", "category", "subcategory", "seller_name", "availability"):
        stripped = out[column].astype("object").map(
            lambda v: None if v is None or str(v).strip() == "" else v
        )
        out[column] = stripped

    assert before - len(out) == sum(
        count for reason, count in reasons.items() if not reason.startswith("cleared_")
    )
    return out, reasons


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Add canonical platform/category/brand columns and the product key."""
    if frame.empty:
        return frame

    out = frame.copy()
    out["platform"] = out["platform"].map(normalize_platform)
    out["category_normalized"] = out["category"].map(normalize_category)
    out["brand_normalized"] = out["brand"].map(normalize_brand)
    out["product_name_normalized"] = out["product_name"].map(normalize_product_name)
    out["product_key"] = [
        product_key(name, brand, category)
        for name, brand, category in zip(
            out["product_name"], out["brand"], out["category"], strict=True
        )
    ]
    return out


def deduplicate(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Collapse repeat observations of one listing at one instant.

    Keyed on platform + product identity + timestamp, so a genuine time series
    is preserved and only true repeats are dropped. Keeps the last, which is
    the most recently ingested reading of that moment.
    """
    if frame.empty:
        return frame, 0

    before = len(frame)
    out = frame.sort_values("id").drop_duplicates(
        subset=["platform", "product_key", "collection_timestamp"], keep="last"
    )
    return out, before - len(out)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_dataset(db: Session, filters: DatasetFilters | None = None) -> DatasetResult:
    """Run the full pipeline and return the frame plus its metadata."""
    filters = filters or DatasetFilters()
    generated_at = datetime.now(timezone.utc)
    dataset_id = uuid.uuid4().hex[:12]

    raw = load_snapshots(db, filters)
    total_input = len(raw)

    if raw.empty:
        raise InsufficientDataError(
            "No marketplace records match the selected filters.",
            DatasetMetadata(
                dataset_id=dataset_id,
                generated_at=generated_at,
                total_input_rows=0,
                total_output_rows=0,
                removed_rows=0,
            ),
        )

    cleaned, reasons = clean(raw)
    cleaned = normalize(cleaned)
    cleaned, duplicates = deduplicate(cleaned)
    if duplicates:
        reasons["duplicate_observation"] = duplicates

    if cleaned.empty:
        raise InsufficientDataError(
            "Every matching record was removed during cleaning. "
            f"Reasons: {reasons}.",
            DatasetMetadata(
                dataset_id=dataset_id,
                generated_at=generated_at,
                total_input_rows=total_input,
                total_output_rows=0,
                removed_rows=total_input,
                removal_reasons=reasons,
            ),
        )

    engineered = feature_module.build_features(cleaned)

    engineered = engineered.rename(columns={"id": "snapshot_id"})
    columns = [
        column
        for column in [*IDENTITY_COLUMNS, *feature_module.FEATURE_NAMES]
        if column in engineered.columns
    ]
    output = engineered[columns].copy()

    source_types = sorted(output["source_type"].dropna().unique().tolist())
    timestamps = output["collection_timestamp"]

    metadata = DatasetMetadata(
        dataset_id=dataset_id,
        generated_at=generated_at,
        total_input_rows=total_input,
        total_output_rows=len(output),
        removed_rows=total_input - len(output),
        removal_reasons=reasons,
        platforms=sorted(output["platform"].dropna().unique().tolist()),
        categories=sorted(output["category_normalized"].dropna().unique().tolist()),
        source_types=source_types,
        date_range={
            "start": timestamps.min().isoformat() if not timestamps.empty else None,
            "end": timestamps.max().isoformat() if not timestamps.empty else None,
        },
        feature_count=len(
            [c for c in feature_module.FEATURE_NAMES if c in output.columns]
        ),
        feature_names=[
            c for c in feature_module.FEATURE_NAMES if c in output.columns
        ],
        products=int(output["product_key"].nunique()),
        contains_demo_data=SourceType.DEMO.value in source_types,
        demo_only=source_types == [SourceType.DEMO.value],
    )

    return DatasetResult(frame=output, metadata=metadata)
