"""Data-quality checks applied to every record before it is stored.

Two outcomes:

* **Rejected** -- the record is unusable (no product name, unknown platform,
  no timestamp). It is dropped and counted, never stored.
* **Accepted with warnings** -- the record is usable but one field was
  suspect. The bad field is cleared to None and the reason is stored on the
  row, so nothing silently becomes a plausible-looking number.

Clearing rather than clamping is deliberate: a clamped rating looks like a
real measurement.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timezone
from math import isfinite
from urllib.parse import urlparse

from app.models.enums import Platform
from app.scrapers.base import NormalizedRecord

MAX_RATING = 5.0


@dataclass
class ValidationResult:
    record: NormalizedRecord | None
    warnings: list[str]
    rejected_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.record is not None


def _known_platform(value: str) -> bool:
    return value in {platform.value for platform in Platform}


def validate_record(record: NormalizedRecord) -> ValidationResult:
    """Check one record, clearing suspect fields and collecting warnings."""
    warnings: list[str] = []

    # --- Rejections ---
    if not record.product_name or not record.product_name.strip():
        return ValidationResult(None, warnings, "product_name is empty")

    if not _known_platform(record.platform):
        return ValidationResult(
            None, warnings, f"unknown platform '{record.platform}'"
        )

    if record.collection_timestamp is None:
        return ValidationResult(None, warnings, "collection_timestamp is missing")

    stamp = record.collection_timestamp
    stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
    cleaned = replace(record, collection_timestamp=stamp)
    for field in ("price", "original_price", "rating", "review_count", "discount_percentage"):
        value = getattr(cleaned, field)
        if value is not None and not isfinite(value):
            warnings.append(f"{field} was not finite and has been dropped")
            cleaned = replace(cleaned, **{field: None})

    # --- Field-level corrections ---
    if cleaned.price is not None and cleaned.price < 0:
        warnings.append("price was negative and has been dropped")
        cleaned = replace(cleaned, price=None)

    if cleaned.original_price is not None and cleaned.original_price < 0:
        warnings.append("original_price was negative and has been dropped")
        cleaned = replace(cleaned, original_price=None)

    if cleaned.rating is not None and not (0 <= cleaned.rating <= MAX_RATING):
        warnings.append(
            f"rating {cleaned.rating} is outside 0-{MAX_RATING} and has been dropped"
        )
        cleaned = replace(cleaned, rating=None)

    if cleaned.review_count is not None and cleaned.review_count < 0:
        warnings.append("review_count was negative and has been dropped")
        cleaned = replace(cleaned, review_count=None)

    if cleaned.listing_url is not None:
        parsed = urlparse(cleaned.listing_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            warnings.append("listing_url was not a valid URL and has been dropped")
            cleaned = replace(cleaned, listing_url=None)

    if (
        cleaned.discount_percentage is not None
        and not (0 <= cleaned.discount_percentage <= 100)
    ):
        warnings.append(
            "discount_percentage was outside 0-100 and has been dropped"
        )
        cleaned = replace(cleaned, discount_percentage=None)

    # A sale price above the list price means one of the two was misread.
    if (
        cleaned.price is not None
        and cleaned.original_price is not None
        and cleaned.price > cleaned.original_price
    ):
        warnings.append(
            "price exceeded original_price; original_price has been dropped"
        )
        cleaned = replace(cleaned, original_price=None, discount_percentage=None)

    return ValidationResult(cleaned, warnings)
