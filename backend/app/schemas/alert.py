from datetime import datetime
from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=512)
    platform: str = Field(min_length=1, max_length=64)
    condition: str = Field(pattern=r"^(below|above|change_pct)$")
    threshold: float
    currency: str = Field(default="INR", max_length=8)


class AlertUpdate(BaseModel):
    condition: str | None = Field(default=None, pattern=r"^(below|above|change_pct)$")
    threshold: float | None = None
    active: bool | None = None


class AlertRead(BaseModel):
    id: int
    user_id: int
    product_name: str
    platform: str
    condition: str
    threshold: float
    currency: str
    active: bool
    triggered_at: datetime | None
    triggered_value: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    alerts: list[AlertRead]
    total: int
