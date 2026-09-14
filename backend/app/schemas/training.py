"""Request/response schemas for model training."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AVAILABLE_MODELS = ["random_forest", "xgboost"]


class TrainRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    #: "latest" (default) or a specific dataset id from /ml/dataset/status.
    dataset_id: str | None = Field(default="latest", min_length=1, max_length=64)
    models: list[Literal["random_forest", "xgboost"]] | None = Field(
        default=None, min_length=1, max_length=2,
        description="Subset of random_forest, xgboost. Omit to try both.",
    )
    #: Required and deliberate: the provenance classes this model may learn from.
    source_types: list[Literal["demo", "imported", "live"]] = Field(
        min_length=1, max_length=3,
        description="Allowed: [demo], [imported], [live], [imported, live]. DEMO with anything else is rejected.",
    )
    #: Development-only escape hatch to mix DEMO with real data. Never above experimental.
    development_override: bool = False


class QualityReport(BaseModel):
    """Phase 12 evaluation evidence for one model."""

    quality_status: Literal["below_baseline", "experimental", "candidate", "validated"]
    quality_reasons: list[str] = Field(default_factory=list)
    calibration_status: str = "uncalibrated"
    probability_quality: dict[str, Any] = Field(default_factory=dict)
    #: All accuracies; never compare weighted F1 with these.
    baselines: dict[str, Any] = Field(default_factory=dict)
    split: dict[str, Any] = Field(default_factory=dict)
    data_summary: dict[str, Any] = Field(default_factory=dict)
    source_policy: dict[str, Any] = Field(default_factory=dict)
    group_overlap: dict[str, Any] = Field(default_factory=dict)
    unseen_product_accuracy: float | None = None
    #: True for models trained before the Phase 12 leakage fix.
    legacy: bool = False
    leakage_safe_split: bool = True


class ModelRunResult(BaseModel):
    """One candidate model's outcome, including failures."""

    model: str
    metrics: dict[str, float] = Field(default_factory=dict)
    error: str | None = None


class TrainResponse(BaseModel):
    status: str = "success"
    model_version: str
    selected_model: str
    target: str
    training_rows: int
    validation_rows: int
    metrics: dict[str, float]
    #: Accuracy of always guessing the most common class. Reported so a result
    #: that fails to beat it is visible as such.
    majority_baseline: float | None = None
    dataset_id: str
    dataset_source_types: list[str] = Field(default_factory=list)
    all_models: list[ModelRunResult] = Field(default_factory=list)
    selection_rule: str
    split_strategy: str
    warnings: list[str] = Field(default_factory=list)
    #: Present whenever the training data was synthetic. Never suppressed.
    notice: str | None = None
    quality: QualityReport | None = None


class TrainingRunSummary(BaseModel):
    """A row of training history."""

    model_version: str
    model_type: str | None
    trained_at: datetime | None
    dataset_id: str | None
    accuracy: float | None
    f1_weighted: float | None
    source_types: list[str] = Field(default_factory=list)
    is_active: bool
    quality_status: str | None = None


class ModelStatusResponse(BaseModel):
    trained: bool
    active_model: str | None = None
    version: str | None = None
    model_name: str | None = None
    target: str | None = None
    trained_at: datetime | None = None
    dataset_id: str | None = None
    dataset_source_types: list[str] = Field(default_factory=list)
    primary_metric: str | None = None
    primary_metric_value: float | None = None
    majority_baseline: float | None = None
    status: str | None = None
    feature_count: int = 0
    xgboost_available: bool = True
    available_models: list[str] = Field(default_factory=lambda: list(AVAILABLE_MODELS))
    history: list[TrainingRunSummary] = Field(default_factory=list)
    notice: str | None = None
    quality: QualityReport | None = None


class ModelMetricsResponse(BaseModel):
    model_version: str
    selected_model: str | None
    target: str
    trained_at: datetime | None
    metrics: dict[str, Any]
    majority_baseline: float | None = None
    confusion_matrix: list[list[int]] = Field(default_factory=list)
    confusion_labels: list[str] = Field(default_factory=list)
    class_distribution: dict[str, int] = Field(default_factory=dict)
    feature_count: int = 0
    feature_names: list[str] = Field(default_factory=list)
    excluded_columns: dict[str, str] = Field(default_factory=dict)
    training_rows: int = 0
    validation_rows: int = 0
    split_strategy: str | None = None
    selection_rule: str | None = None
    dataset_id: str | None = None
    dataset_source_types: list[str] = Field(default_factory=list)
    all_models: list[ModelRunResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notice: str | None = None
    quality: QualityReport | None = None
