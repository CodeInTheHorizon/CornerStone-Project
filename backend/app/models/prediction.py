"""A stored prediction produced for a user-selected product.

Populated by the prediction service in Phase 7.
"""

from sqlalchemy import Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Nullable so a prediction row survives cleanup of old model metadata.
    model_metadata_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_metadata.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # --- Request: the product the user asked about ---
    product_name: Mapped[str] = mapped_column(String(512), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    target_platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # --- Result ---
    recommended_platform: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # {"amazon": 82, "flipkart": 76, ...} -- 0-100 per marketplace.
    opportunity_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Contributing factors, so a result can be explained rather than asserted.
    key_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)

    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Number of snapshots the prediction was grounded in, for data-freshness display.
    snapshots_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Immutable response snapshot: probabilities, provenance, score components,
    # and measured model quality must survive subsequent training runs.
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="predictions")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Prediction id={self.id} product={self.product_name!r:.40} "
            f"recommended={self.recommended_platform!r}>"
        )
