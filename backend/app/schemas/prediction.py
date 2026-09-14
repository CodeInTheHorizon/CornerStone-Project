"""Prediction requests select observed products, never arbitrary feature vectors."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Platform


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    product_key: str = Field(min_length=1, max_length=900)
    dataset_id: str | None = Field(default=None, min_length=1, max_length=64)
    platforms: list[Platform] = Field(default_factory=lambda: list(Platform), min_length=1, max_length=4)


class ModelQuality(BaseModel):
    version: str
    type: str | None
    target: str
    primary_metric: str = "f1_weighted"
    primary_metric_value: float | None
    accuracy: float | None
    majority_baseline: float | None
    below_baseline: bool | None
    source_types: list[str]
    warning: str
    # Phase 12. Defaults keep predictions saved before Phase 12 readable.
    quality_status: str | None = None
    calibration_status: str = "uncalibrated"
    probability_assessment: str | None = None
    #: Accuracy of every naive baseline the model was compared with.
    baselines: dict[str, Any] = Field(default_factory=dict)
    #: True when the model was trained before the boundary-leakage fix.
    legacy_model: bool | None = None


class PlatformPrediction(BaseModel):
    platform: str
    status: Literal["success", "insufficient_data", "prediction_failed", "incompatible_features"]
    reason: str | None = None
    predicted_class: str | None = None
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    opportunity_score: float | None = None
    components: dict[str, float] = Field(default_factory=dict)
    normalized_signals: dict[str, float | None] = Field(default_factory=dict)
    coverage_weight: int = 0
    missing_components: list[str] = Field(default_factory=list)
    key_factors: list[str] = Field(default_factory=list)
    model_version: str
    source_type: str | None = None
    data_freshness: datetime | None = None
    stale: bool = False
    warning: str


class PredictionResponse(BaseModel):
    id: int
    status: str = "success"
    product: str
    product_key: str
    created_at: datetime
    recommended_platform: str
    recommendation_label: str = "Highest observed opportunity score"
    ranking: list[PlatformPrediction]
    platform_results: list[PlatformPrediction]
    score_difference: float | None
    key_factors: list[str]
    model: ModelQuality
    data_provenance: dict[str, Any]
    formula: dict[str, Any]
    warning: str


class PredictionHistoryItem(BaseModel):
    id: int
    product: str
    recommended_platform: str | None
    top_score: float | None
    model_version: str | None
    source_types: list[str]
    created_at: datetime
    model: ModelQuality | None = None
    warning: str


class PredictionHistory(BaseModel):
    total: int
    items: list[PredictionHistoryItem]
