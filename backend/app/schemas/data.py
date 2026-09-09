"""Request/response schemas for marketplace data collection."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Platform

MAX_ITEMS = 100


class CollectRequest(BaseModel):
    platform: str = Field(description="One of: amazon, flipkart, croma, alibaba.")
    keyword: str = Field(min_length=2, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    max_items: int = Field(default=20, ge=1, le=MAX_ITEMS)

    @field_validator("platform")
    @classmethod
    def _known_platform(cls, value: str) -> str:
        normalized = value.strip().lower()
        valid = {platform.value for platform in Platform}
        if normalized not in valid:
            raise ValueError(
                f"Unknown platform '{value}'. Supported: {', '.join(sorted(valid))}."
            )
        return normalized

    @field_validator("keyword", "category")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class CollectResponse(BaseModel):
    status: str = "success"
    platform: str
    keyword: str
    items_collected: int
    items_rejected: int
    duplicates_skipped: int
    collection_run_id: str
    collection_timestamp: datetime
    warnings: list[str] = Field(default_factory=list)


class SnapshotRead(BaseModel):
    """One stored marketplace observation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    source: str
    search_query: str | None
    collection_run_id: str | None

    product_name: str
    brand: str | None
    category: str | None
    subcategory: str | None
    external_id: str | None

    price: float | None
    original_price: float | None
    discount_percentage: float | None
    currency: str

    rating: float | None
    review_count: int | None

    availability: str | None
    seller_name: str | None
    listing_url: str | None

    shipping_info: str | None
    delivery_time: str | None
    badge: str | None
    sponsored: bool | None
    specifications: dict | None
    stock_status: str | None

    warnings: list | None
    collection_timestamp: datetime


class SnapshotListResponse(BaseModel):
    count: int
    items: list[SnapshotRead]


class PlatformStatus(BaseModel):
    available: bool
    access_method: str
    reason: str | None = None
    requires_credentials: bool = False
    last_collection: datetime | None = None
    stored_snapshots: int = 0


class StatusResponse(BaseModel):
    platforms: dict[str, PlatformStatus]
    total_snapshots: int
    last_collection: datetime | None = None
