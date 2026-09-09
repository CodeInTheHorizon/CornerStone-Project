"""Shared parsing helpers for turning raw marketplace values into clean types.

All of these return None rather than a default when the input cannot be
parsed. A missing value must stay missing.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

_DIGITS = re.compile(r"[-+]?\d[\d,\s]*\.?\d*")
# Tracking/affiliate parameters worth stripping so the same listing collected
# twice produces the same URL.
_STRIP_QUERY = True


def parse_price(value: object) -> float | None:
    """Extract a price from a number or a string like "₹1,299.00" or "Rs. 999"."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        price = float(value)
        return price if price >= 0 else None

    if not isinstance(value, str):
        return None

    match = _DIGITS.search(value)
    if match is None:
        return None

    cleaned = match.group(0).replace(",", "").replace(" ", "")
    try:
        price = float(cleaned)
    except ValueError:
        return None
    return price if price >= 0 else None


def parse_rating(value: object, maximum: float = 5.0) -> float | None:
    """Extract a star rating, e.g. "4.3 out of 5 stars" -> 4.3.

    Values outside 0..maximum are discarded rather than clamped: a rating that
    far off means the source was misread, and a clamped number would look
    legitimate.
    """
    rating = parse_price(value)
    if rating is None:
        return None
    if rating < 0 or rating > maximum:
        return None
    return round(rating, 2)


def parse_review_count(value: object) -> int | None:
    """Extract a review count, e.g. "1,234 ratings" -> 1234."""
    count = parse_price(value)
    if count is None:
        return None
    if count < 0:
        return None
    return int(count)


def compute_discount(
    price: float | None,
    original_price: float | None,
) -> float | None:
    """Percentage off, when both prices are known and the maths makes sense."""
    if price is None or original_price is None:
        return None
    if original_price <= 0 or price < 0 or price > original_price:
        return None
    return round((original_price - price) / original_price * 100, 2)


def normalize_url(value: object, base: str | None = None) -> str | None:
    """Return an absolute https URL with tracking query/fragment removed."""
    if not isinstance(value, str):
        return None

    url = value.strip()
    if not url:
        return None

    if url.startswith("//"):
        url = f"https:{url}"
    elif url.startswith("/") and base:
        url = f"{base.rstrip('/')}{url}"

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    return urlunparse(
        (
            "https",
            parsed.netloc,
            parsed.path,
            "",
            "" if _STRIP_QUERY else parsed.query,
            "",
        )
    )


def extract_brand(
    explicit: object = None,
    product_name: str | None = None,
) -> str | None:
    """Prefer a brand the platform states; fall back to the leading token.

    The fallback is a heuristic, so it is only used when the source gives no
    brand at all, and only for a plausible-looking leading word.
    """
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()[:120]

    if not product_name:
        return None

    first = product_name.strip().split()
    if not first:
        return None

    candidate = first[0].strip("(),-|")
    # Reject tokens that are clearly not a brand. A leading digit means a spec
    # rather than a name -- "65W", "40h", "128GB" -- so the whole token is
    # discarded rather than guessed at.
    if len(candidate) < 2 or not candidate[0].isalpha():
        return None
    return candidate[:120]


def clean_text(value: object, limit: int = 512) -> str | None:
    """Collapse whitespace and trim; None when empty."""
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] if cleaned else None
