"""Metadata describing one trained model artifact.

Populated by the training pipeline in Phase 6. Metrics stored here are
always measured values from an actual evaluation run.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin
from app.models.enums import TrainingStatus


class ModelMetadata(Base, TimestampMixin):
    __tablename__ = "model_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)

    model_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    algorithm: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), default=TrainingStatus.PENDING.value, index=True, nullable=False
    )
    # Populated when status is FAILED.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Training inputs ---
    dataset_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feature_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    hyperparameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # --- Measured evaluation results ---
    # Left NULL until a real evaluation has run. Never seed with a placeholder.
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # --- Quality gate (Phase 12) ---
    # below_baseline | experimental | candidate | validated. NULL on records
    # trained before Phase 12; those are interpreted on read, never backfilled.
    quality_status: Mapped[str | None] = mapped_column(String(24), index=True, nullable=True)
    # Probabilities are never recalibrated: "uncalibrated" or "unavailable".
    calibration_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # --- Artifact ---
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Exactly one row is expected to be active; enforced in the service layer.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<ModelMetadata id={self.id} name={self.model_name!r} "
            f"version={self.model_version!r} status={self.status!r}>"
        )
