"""The observation contract every source must produce.

`ProductObservation` is strict: it is the last gate before PostgreSQL, so a
value that reaches it in the wrong shape is a bug in the normalizer, not
something to coerce silently. Leniency (turning "₹1,299" into a Decimal,
dropping an MRP below the selling price) lives in `normalize.py`.

A future API-backed source replaces a scraper by producing this same model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

#: Ceiling for any price, in rupees. A mis-parse (a widget id, a timestamp)
#: must surface as a missing price rather than an absurd one.
MAX_PRICE = Decimal("10000000")


class Marketplace(str, Enum):
    AMAZON = "amazon"
    FLIPKART = "flipkart"
    MEESHO = "meesho"


class Availability(str, Enum):
    IN_STOCK = "in_stock"
    #: "Only 3 left in stock" and similar.
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    #: Listed but not purchasable at all ("Currently unavailable").
    UNAVAILABLE = "unavailable"
    PREORDER = "preorder"
    UNKNOWN = "unknown"


def _http_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("must be an absolute http(s) URL")
    return value


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


Money = Annotated[Decimal, Field(ge=0, le=MAX_PRICE, max_digits=10, decimal_places=2)]
ShortText = Annotated[str, Field(min_length=1, max_length=255)]


class ProductObservation(BaseModel):
    """One timestamped look at one product on one marketplace. Never updated after storage."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    marketplace: Marketplace
    platform_product_id: Annotated[str, Field(min_length=1, max_length=128)]
    product_url: Annotated[str, AfterValidator(_http_url), Field(max_length=2048)]
    collected_at: Annotated[AwareDatetime, AfterValidator(_utc)]
    #: Which implementation produced this row, e.g. "amazon-html/1".
    source: Annotated[str, Field(min_length=1, max_length=64)]

    product_name: Annotated[str, Field(min_length=1, max_length=1000)]
    brand: ShortText | None = None
    #: Leaf of the breadcrumb, e.g. "In-Ear".
    category: ShortText | None = None
    #: Full breadcrumb, e.g. "Electronics > Headphones > In-Ear".
    category_path: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    model: ShortText | None = None
    #: Selected variation, e.g. "Colour: Black; Size: 128 GB".
    variant: Annotated[str, Field(min_length=1, max_length=500)] | None = None

    current_price: Money | None = None
    mrp: Money | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "INR"
    discount_percentage: Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)] | None = None

    rating: Annotated[Decimal, Field(ge=0, le=5, max_digits=3, decimal_places=2)] | None = None
    #: Star ratings (with or without text).
    rating_count: Annotated[int, Field(ge=0)] | None = None
    #: Written reviews. Often not shown on the product page; None when absent.
    review_count: Annotated[int, Field(ge=0)] | None = None

    availability: Availability = Availability.UNKNOWN
    availability_text: ShortText | None = None
    seller_name: ShortText | None = None

    #: Values the normalizer cleared or corrected, so a gap is explained.
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> "ProductObservation":
        if self.current_price is not None and self.mrp is not None and self.current_price > self.mrp:
            raise ValueError("current_price must not exceed mrp")
        if self.review_count is not None and self.rating_count is not None and self.review_count > self.rating_count:
            raise ValueError("review_count must not exceed rating_count")
        return self
