"""Request/response schemas for the dataset builder."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import SourceType
from app.ml.normalization import normalize_platform, is_known_platform

MAX_PREVIEW = 100


class DatasetBuildRequest(BaseModel):
    """Which stored snapshots to build a dataset from.

    Omitting a filter means "no restriction on that dimension". Source types
    are never mixed silently -- whatever is selected is echoed back in the
    metadata.
    """

    platforms: list[str] | None = Field(default=None, max_length=4)
    categories: list[str] | None = Field(default=None, max_length=50)
    keyword: str | None = Field(default=None, max_length=120)
    source_types: list[SourceType] | None = None
    start: datetime | None = None
    end: datetime | None = None
    #: False builds in memory without writing to data/processed/.
    persist: bool = True

    @field_validator("platforms", "categories")
    @classmethod
    def _clean_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if item and item.strip()]
        return cleaned or None

    @field_validator("platforms")
    @classmethod
    def _platforms(cls, value):
        if value is None:
            return value
        normalized = [normalize_platform(item) for item in value]
        if not all(is_known_platform(item) for item in normalized):
            raise ValueError("Unsupported platform in dataset filters.")
        return list(dict.fromkeys(normalized))

    @field_validator("start", "end")
    @classmethod
    def _utc_dates(cls, value):
        if value is None:
            return value
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _date_range(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be on or before end.")
        if self.categories and any(len(item) > 120 for item in self.categories):
            raise ValueError("Category filters must be at most 120 characters.")
        return self

    @field_validator("source_types", mode="before")
    @classmethod
    def _accept_any_case(cls, value: object) -> object:
        # The UI and the spec both use uppercase (DEMO); storage is lowercase.
        if isinstance(value, list):
            return [
                item.lower() if isinstance(item, str) else item for item in value
            ]
        return value


class DatasetMetadataRead(BaseModel):
    dataset_id: str
    generated_at: datetime
    total_input_rows: int
    total_output_rows: int
    removed_rows: int
    removal_reasons: dict[str, int] = Field(default_factory=dict)
    platforms: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    date_range: dict[str, str | None] = Field(default_factory=dict)
    feature_count: int = 0
    feature_names: list[str] = Field(default_factory=list)
    products: int = 0
    dataset_version: str = "1.0"
    contains_demo_data: bool = False
    demo_only: bool = False
    csv_path: str | None = None
    metadata_path: str | None = None


class DatasetBuildResponse(BaseModel):
    status: str = "success"
    dataset_id: str
    rows: int
    features: int
    source_types: list[str]
    removed_rows: int
    generated_at: datetime
    metadata: DatasetMetadataRead
    #: Present whenever any row is synthetic. Shown verbatim in the UI.
    notice: str | None = None


class DatasetStatusResponse(BaseModel):
    """State of the dataset builder."""

    has_dataset: bool
    latest: DatasetMetadataRead | None = None
    stored_datasets: int = 0
    available_features: list[str] = Field(default_factory=list)
    notice: str | None = None


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    rows: list[dict[str, Any]]
    columns: list[str]
    total_rows: int
    notice: str | None = None
