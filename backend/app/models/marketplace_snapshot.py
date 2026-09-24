"""A single observation of one marketplace listing at one point in time.

Repeated snapshots of the same listing are what give MarketPulse AI its
time-series signal (price change, review growth, and so on). Nothing here
is populated in Phase 1; the collection layer arrives in Phase 4.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, utcnow
from app.models.enums import SourceType


class MarketplaceSnapshot(Base, TimestampMixin):
    __tablename__ = "marketplace_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Provenance ---
    platform: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # live | imported | demo. Never NULL: a row whose provenance is unknown
    # could be mistaken for a live observation.
    source_type: Mapped[str] = mapped_column(
        String(16), default=SourceType.LIVE.value, index=True, nullable=False
    )
    # Search keyword / query that produced this record, for traceability.
    search_query: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Groups every row written by one collection call, so a run can be
    # inspected or rolled back as a unit and deduplicated within itself.
    collection_run_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )

    # --- Product identity ---
    product_name: Mapped[str] = mapped_column(String(512), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Platform-native identifier (ASIN, FSN, SKU ...) when exposed publicly.
    external_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    # --- Pricing ---
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)

    # --- Social proof ---
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Images ---
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # --- Availability / seller ---
    availability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Alibaba wholesale ---
    min_order_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    supplier_years: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Optional extras, only where the platform exposes them ---
    shipping_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_time: Mapped[str | None] = mapped_column(String(120), nullable=True)
    badge: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sponsored: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    specifications: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stock_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Validation notes attached at ingest, e.g. an out-of-range rating that
    # was dropped. Empty/NULL means the record passed cleanly.
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # --- Observation time ---
    # When the marketplace was actually observed. Distinct from created_at,
    # which is when the row was written to this database.
    collection_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    __table_args__ = (
        # Supports "latest snapshots for a platform" and time-window queries.
        Index("ix_snapshot_platform_collected", "platform", "collection_timestamp"),
        # Supports building a per-listing time series for trend features.
        Index("ix_snapshot_platform_external_id", "platform", "external_id"),
        # One row per listing per observation time per batch. The timestamp
        # is part of the key because an imported or demo dataset carries the
        # same listing across many dates in a single batch -- that time
        # series is the point, and keying on identity alone would reject it.
        UniqueConstraint(
            "collection_run_id",
            "platform",
            "external_id",
            "collection_timestamp",
            name="uq_snapshot_run_platform_item_time",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<MarketplaceSnapshot id={self.id} platform={self.platform!r} "
            f"product={self.product_name!r:.40} price={self.price}>"
        )
