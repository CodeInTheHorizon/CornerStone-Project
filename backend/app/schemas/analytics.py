"""Stored-observation analytics filters. Calendar dates are interpreted in UTC."""

from dataclasses import dataclass
from datetime import date

from app.models.enums import Platform, SourceType


@dataclass(frozen=True)
class AnalyticsFilters:
    product: str | None = None
    product_key: str | None = None
    platform: Platform | None = None
    category: str | None = None
    source_type: SourceType | None = None
    start_date: date | None = None
    end_date: date | None = None
