"""Canonical product entity — one row per real-world product across all platforms."""

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_title: Mapped[str] = mapped_column(String(512), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str] = mapped_column(String(120), default="electronics", nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(120), nullable=True)
    primary_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    listings: Mapped[list["PlatformListing"]] = relationship(
        "PlatformListing", back_populates="product", lazy="selectin"
    )
    tracked_by: Mapped[list["TrackedProduct"]] = relationship(
        "TrackedProduct", back_populates="product", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_product_brand_category", "brand", "category"),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} title={self.canonical_title!r:.40}>"
