"""A single observation of one marketplace listing at one point in time.

Repeated snapshots of the same listing are what give MarketPulse AI its
time-series signal (price change, review growth, and so on). Nothing here
is populated in Phase 1; the collection layer arrives in Phase 4.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, utcnow
from app.models.enums import DataSource


class MarketplaceSnapshot(Base, TimestampMixin):
    __tablename__ = "marketplace_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Provenance ---
    platform: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source: Mapped[str] = mapped_column(
        String(16), default=DataSource.LIVE.value, index=True, nullable=False
    )
    # Search keyword / query that produced this record, for traceability.
    search_query: Mapped[str | None] = mapped_column(String(255), nullable=True)

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

    # --- Availability / seller ---
    availability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    listing_url: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<MarketplaceSnapshot id={self.id} platform={self.platform!r} "
            f"product={self.product_name!r:.40} price={self.price}>"
        )
