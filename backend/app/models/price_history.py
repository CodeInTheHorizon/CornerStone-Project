"""Append-only price history — one row per observation of a listing."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("platform_listings.id"), nullable=False, index=True
    )
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seller_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    listing: Mapped["PlatformListing"] = relationship(
        "PlatformListing", back_populates="price_history"
    )

    __table_args__ = (
        Index("ix_price_history_listing_time", "listing_id", "observed_at"),
    )

    def __repr__(self) -> str:
        return f"<PriceHistory id={self.id} listing={self.listing_id} price={self.price}>"
