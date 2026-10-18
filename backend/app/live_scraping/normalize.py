"""Turn a parser's raw strings into a validated `ProductObservation`.

Rules, shared by every marketplace:

* A value that cannot be parsed stays None. Nothing is guessed or defaulted.
* A value that parses but is implausible is dropped (not clamped) and the
  reason is kept in `warnings`, so a gap in the history is explained.
* When MRP and price are both known, the discount is recomputed from them;
  the page's own "-23%" is only used when MRP is missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from pydantic import ValidationError

from app.live_scraping.errors import ParseFailedError
from app.live_scraping.schemas import MAX_PRICE, Availability, Marketplace, ProductObservation

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_RANGE = re.compile(r"\d[\d,.]*\s*(?:-|–|—|to)\s*[₹$]?\s*\d", re.IGNORECASE)
_COUNT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|l|lakh|lac|m|mn|cr|crore)?\b", re.IGNORECASE)
_MULTIPLIERS = {"k": 1_000, "l": 100_000, "lakh": 100_000, "lac": 100_000, "m": 1_000_000, "mn": 1_000_000,
                "cr": 10_000_000, "crore": 10_000_000}
#: Stated vs computed discount may differ by rounding; beyond this, trust the prices.
DISCOUNT_TOLERANCE = Decimal("1.5")
_CENT = Decimal("0.01")


@dataclass(frozen=True)
class ParsedProduct:
    """What a parser read off the page, still as text. Every field is optional."""

    product_name: str | None = None
    brand: str | None = None
    category_path: tuple[str, ...] = ()
    model: str | None = None
    variant: str | None = None
    current_price_text: str | None = None
    mrp_text: str | None = None
    discount_text: str | None = None
    rating_text: str | None = None
    rating_count_text: str | None = None
    review_count_text: str | None = None
    availability: Availability | None = None
    availability_text: str | None = None
    seller_name: str | None = None
    currency: str = "INR"
    #: The product id the page itself reports, when it reports one.
    page_product_id: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


#: Bidi and zero-width marks Amazon embeds in detail tables ("‎MTP03HN/A").
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍‎‏‪‫‬‭‮⁦⁧⁨⁩﻿"))


def clean_text(value: str | None, limit: int = 255) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.translate(_INVISIBLE).split())
    return cleaned[:limit] or None


def parse_money(text: str | None) -> tuple[Decimal | None, str | None]:
    """(amount, warning). Handles "₹1,29,999.00", "Rs. 499"; refuses ranges."""
    if not text or not text.strip():
        return None, None
    if _RANGE.search(text):
        return None, f"price '{clean_text(text, 40)}' is a range; not recorded"
    match = _NUMBER.search(text)
    if match is None:
        return None, f"price '{clean_text(text, 40)}' has no number"
    try:
        amount = Decimal(match.group(0).replace(",", "")).quantize(_CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None, f"price '{clean_text(text, 40)}' is not a number"
    if amount <= 0 or amount > MAX_PRICE:
        return None, f"price {amount} is outside 0-{MAX_PRICE}; not recorded"
    return amount, None


def parse_count(text: str | None) -> int | None:
    """ "12,345 ratings" -> 12345, "1.2K" -> 1200, "3.4 lakh" -> 340000."""
    if not text:
        return None
    match = _COUNT.search(text)
    if match is None:
        return None
    try:
        number = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    suffix = (match.group(2) or "").lower()
    return int(number * _MULTIPLIERS.get(suffix, 1))


def parse_rating(text: str | None) -> Decimal | None:
    if not text:
        return None
    match = _NUMBER.search(text)
    if match is None:
        return None
    try:
        rating = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None
    return rating.quantize(_CENT) if 0 <= rating <= 5 else None


def parse_percent(text: str | None) -> Decimal | None:
    if not text:
        return None
    match = _NUMBER.search(text)
    if match is None:
        return None
    value = Decimal(match.group(0).replace(",", ""))
    return value.quantize(_CENT) if 0 <= value <= 100 else None


def classify_availability(text: str | None) -> Availability:
    """Keyword classifier for availability wording common to Indian marketplaces."""
    if not text:
        return Availability.UNKNOWN
    t = text.lower()
    if "currently unavailable" in t or "no longer available" in t or "not available" in t:
        return Availability.UNAVAILABLE
    if "out of stock" in t or "sold out" in t:
        return Availability.OUT_OF_STOCK
    if "pre-order" in t or "preorder" in t:
        return Availability.PREORDER
    if re.search(r"only \d+ left", t) or "hurry" in t or "few left" in t:
        return Availability.LOW_STOCK
    if "in stock" in t or "available" in t:
        return Availability.IN_STOCK
    return Availability.UNKNOWN


def normalize(
    parsed: ParsedProduct,
    *,
    marketplace: Marketplace,
    platform_product_id: str,
    product_url: str,
    collected_at: datetime,
    source: str,
) -> ProductObservation:
    """Build the observation, or raise ParseFailedError when the page gave nothing usable."""
    warnings: list[str] = list(parsed.notes)

    name = clean_text(parsed.product_name, 1000)
    if name is None:
        raise ParseFailedError("No product name found on the page.")

    price, warning = parse_money(parsed.current_price_text)
    if warning:
        warnings.append(f"current_price: {warning}")
    mrp, warning = parse_money(parsed.mrp_text)
    if warning:
        warnings.append(f"mrp: {warning}")

    if price is not None and mrp is not None and price > mrp:
        warnings.append(f"mrp {mrp} was below current_price {price}; mrp not recorded")
        mrp = None

    stated_discount = parse_percent(parsed.discount_text)
    discount: Decimal | None = None
    if price is not None and mrp is not None:
        discount = ((mrp - price) / mrp * 100).quantize(_CENT, rounding=ROUND_HALF_UP)
        if stated_discount is not None and abs(stated_discount - discount) > DISCOUNT_TOLERANCE:
            warnings.append(f"page stated {stated_discount}% off but prices give {discount}%; using prices")
    elif stated_discount is not None and price is not None:
        discount = stated_discount

    rating = parse_rating(parsed.rating_text)
    if parsed.rating_text and rating is None:
        warnings.append(f"rating '{clean_text(parsed.rating_text, 40)}' is not a 0-5 value; not recorded")
    rating_count = parse_count(parsed.rating_count_text)
    review_count = parse_count(parsed.review_count_text)
    if review_count is not None and rating_count is not None and review_count > rating_count:
        warnings.append("review_count exceeded rating_count; review_count not recorded")
        review_count = None

    if parsed.page_product_id and parsed.page_product_id != platform_product_id:
        warnings.append(f"page reports product id {parsed.page_product_id}")

    availability_text = clean_text(parsed.availability_text)
    availability = parsed.availability or classify_availability(availability_text)
    path = tuple(p for p in (clean_text(c, 120) for c in parsed.category_path) if p)

    try:
        return ProductObservation(
            marketplace=marketplace,
            platform_product_id=platform_product_id,
            product_url=product_url,
            collected_at=collected_at,
            source=source,
            product_name=name,
            brand=clean_text(parsed.brand),
            category=path[-1] if path else None,
            category_path=" > ".join(path)[:1000] if path else None,
            model=clean_text(parsed.model),
            variant=clean_text(parsed.variant, 500),
            current_price=price,
            mrp=mrp,
            currency=parsed.currency,
            discount_percentage=discount,
            rating=rating,
            rating_count=rating_count,
            review_count=review_count,
            availability=availability,
            availability_text=availability_text,
            seller_name=clean_text(parsed.seller_name),
            warnings=tuple(warnings),
        )
    except ValidationError as exc:
        fields = ", ".join(sorted({".".join(str(p) for p in err["loc"]) or "model" for err in exc.errors()}))
        raise ParseFailedError(f"Observation failed validation ({fields}).") from None
