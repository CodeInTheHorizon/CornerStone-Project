"""Cross-platform product matching.

Given a normalized product title from one platform, find or create the
canonical Product row it belongs to. v1 approach: normalize the title
(lowercase, strip noise words, extract brand + model tokens) then fuzzy-match
against existing canonical titles. When confidence is above the threshold,
link; otherwise create a new Product.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product

MATCH_THRESHOLD = 0.70
HIGH_CONFIDENCE_THRESHOLD = 0.85

_NOISE = re.compile(
    r"\b(with|for|and|the|new|latest|best|original|genuine|pack of|combo|set)\b",
    re.IGNORECASE,
)
_PARENS = re.compile(r"\([^)]*\)")
_MULTI_SPACE = re.compile(r"\s+")


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = _PARENS.sub(" ", t)
    t = _NOISE.sub(" ", t)
    t = _MULTI_SPACE.sub(" ", t).strip()
    return t


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


from app.matching.engine import match_or_create_product


def find_or_create_product(
    db: Session,
    *,
    title: str,
    brand: str | None = None,
    category: str = "electronics",
    subcategory: str | None = None,
    image_url: str | None = None,
    raw_specs: dict | None = None,
) -> tuple[Product, float]:
    """Find the best-matching canonical Product or create a new one using RapidFuzz & specs."""
    return match_or_create_product(
        db,
        title=title,
        brand=brand,
        category=category,
        subcategory=subcategory,
        image_url=image_url,
        raw_specs=raw_specs,
    )
