"""One listing of a product on a specific platform."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, utcnow


class PlatformListing(Base, TimestampMixin):
    __tablename__ = "platform_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    platform_product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_on_platform: Mapped[str] = mapped_column(String(512), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    price_current: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_original: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    min_order_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="listings")
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="listing", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("product_id", "platform", name="uq_listing_product_platform"),
        Index("ix_listing_platform_pid", "platform", "platform_product_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PlatformListing id={self.id} platform={self.platform!r} "
            f"title={self.title_on_platform!r:.40}>"
        )
