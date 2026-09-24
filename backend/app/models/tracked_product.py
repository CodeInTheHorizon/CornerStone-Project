"""A product a user has opted to track for scheduled re-scraping."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow


class TrackedProduct(Base):
    __tablename__ = "tracked_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    refresh_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=360, nullable=False
    )

    user: Mapped["User"] = relationship("User")
    product: Mapped["Product"] = relationship("Product", back_populates="tracked_by")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_tracked_user_product"),
    )

    def __repr__(self) -> str:
        return f"<TrackedProduct user={self.user_id} product={self.product_id}>"
