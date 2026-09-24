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


def find_or_create_product(
    db: Session,
    *,
    title: str,
    brand: str | None = None,
    category: str = "electronics",
    subcategory: str | None = None,
    image_url: str | None = None,
) -> tuple[Product, float]:
    """Find the best-matching canonical Product or create a new one.

    Returns (product, confidence) where confidence is 1.0 for exact matches
    and the fuzzy ratio for partial matches.
    """
    norm = _normalize_title(title)
    if not norm:
        product = Product(
            canonical_title=title,
            brand=brand,
            category=category,
            subcategory=subcategory,
            primary_image_url=image_url,
        )
        db.add(product)
        db.flush()
        return product, 1.0

    stmt = select(Product)
    if brand:
        stmt = stmt.where(Product.brand == brand)
    stmt = stmt.where(Product.category == category)
    candidates = db.execute(stmt).scalars().all()

    best_match: Product | None = None
    best_score: float = 0.0

    for candidate in candidates:
        cand_norm = _normalize_title(candidate.canonical_title)
        score = _similarity(norm, cand_norm)
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_match is not None and best_score >= MATCH_THRESHOLD:
        if image_url and not best_match.primary_image_url:
            best_match.primary_image_url = image_url
        return best_match, round(best_score, 4)

    product = Product(
        canonical_title=title,
        brand=brand,
        category=category,
        subcategory=subcategory,
        primary_image_url=image_url,
    )
    db.add(product)
    db.flush()
    return product, 1.0
