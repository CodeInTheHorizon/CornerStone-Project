"""Opportunity Score engine — v1 transparent weighted model.

Computes a 0–100 score per platform for a given product, with per-signal
component breakdown, plain-English explanation, and inventory allocation.

Signals and default weights (from PRD Section 11):
  Competition (25%) - lower seller count = better opportunity
  Price trend (15%) - rising prices = better for new sellers
  Demand proxy (20%) - higher review count/velocity = more demand
  Rating environment (10%) - moderate-high ratings = healthy market
  Discount depth (10%) - shallow discounts = less margin pressure
  Price band fit (10%) - product price within platform's range
  Category momentum (10%) - category-level growth signal
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.opportunity_score import OpportunityScore
from app.models.platform_listing import PlatformListing
from app.models.price_history import PriceHistory

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "competition": 0.25,
    "price_trend": 0.15,
    "demand_proxy": 0.20,
    "rating_environment": 0.10,
    "discount_depth": 0.10,
    "price_band_fit": 0.10,
    "category_momentum": 0.10,
}

WHOLESALE_WEIGHTS = {
    "moq_accessibility": 0.25,
    "price_range_value": 0.25,
    "supplier_trust": 0.20,
    "demand_proxy": 0.15,
    "price_band_fit": 0.15,
}


@dataclass
class SignalResult:
    name: str
    raw_value: float | None
    normalized: float
    weight: float
    contribution: float
    explanation: str


@dataclass
class ScoringResult:
    platform: str
    score: float
    rank: int = 0
    components: dict = field(default_factory=dict)
    explanation: str = ""
    suggested_inventory_share_pct: float = 0.0
    is_wholesale: bool = False


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default


def _competition_score(listing: PlatformListing, all_listings: list[PlatformListing]) -> SignalResult:
    seller_count = listing.seller_count or 1
    counts = [l.seller_count or 1 for l in all_listings if l.seller_count]
    max_count = max(counts) if counts else seller_count
    normalized = _clamp(100 * (1 - _safe_div(seller_count, max_count + 1)), 0, 100)
    explanation = f"{seller_count} seller(s)"
    if max_count > seller_count:
        explanation += f" vs up to {max_count} on other platforms"
    return SignalResult(
        name="competition",
        raw_value=float(seller_count),
        normalized=normalized,
        weight=DEFAULT_WEIGHTS["competition"],
        contribution=normalized * DEFAULT_WEIGHTS["competition"],
        explanation=explanation,
    )


def _price_trend_score(listing: PlatformListing, db: Session) -> SignalResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    history = db.execute(
        select(PriceHistory)
        .where(PriceHistory.listing_id == listing.id, PriceHistory.observed_at >= cutoff)
        .order_by(PriceHistory.observed_at)
    ).scalars().all()

    if len(history) < 2 or not history[0].price or not history[-1].price:
        return SignalResult(
            name="price_trend", raw_value=None, normalized=50.0,
            weight=DEFAULT_WEIGHTS["price_trend"],
            contribution=50.0 * DEFAULT_WEIGHTS["price_trend"],
            explanation="Insufficient price history (neutral score)",
        )

    pct_change = ((history[-1].price - history[0].price) / history[0].price) * 100
    normalized = _clamp(50 + pct_change * 5, 0, 100)
    direction = "up" if pct_change > 0 else "down" if pct_change < 0 else "flat"
    return SignalResult(
        name="price_trend", raw_value=pct_change, normalized=normalized,
        weight=DEFAULT_WEIGHTS["price_trend"],
        contribution=normalized * DEFAULT_WEIGHTS["price_trend"],
        explanation=f"Prices trending {direction} {abs(pct_change):.1f}% over 30 days",
    )


def _demand_score(listing: PlatformListing, all_listings: list[PlatformListing]) -> SignalResult:
    reviews = listing.review_count or 0
    max_reviews = max((l.review_count or 0) for l in all_listings) if all_listings else reviews
    normalized = _clamp(100 * _safe_div(reviews, max_reviews + 1, 0.5), 0, 100) if max_reviews > 0 else 50.0
    return SignalResult(
        name="demand_proxy", raw_value=float(reviews), normalized=normalized,
        weight=DEFAULT_WEIGHTS["demand_proxy"],
        contribution=normalized * DEFAULT_WEIGHTS["demand_proxy"],
        explanation=f"{reviews:,} reviews" + (f" (highest: {max_reviews:,})" if max_reviews > reviews else ""),
    )


def _rating_score(listing: PlatformListing) -> SignalResult:
    rating = listing.rating
    if rating is None:
        return SignalResult(
            name="rating_environment", raw_value=None, normalized=50.0,
            weight=DEFAULT_WEIGHTS["rating_environment"],
            contribution=50.0 * DEFAULT_WEIGHTS["rating_environment"],
            explanation="No rating data available (neutral score)",
        )
    if rating >= 4.5:
        normalized = 60.0
        explanation = f"Rating {rating:.1f}/5 — very competitive, hard to stand out"
    elif rating >= 3.5:
        normalized = 85.0
        explanation = f"Rating {rating:.1f}/5 — healthy market, room to differentiate"
    elif rating >= 2.5:
        normalized = 70.0
        explanation = f"Rating {rating:.1f}/5 — moderate quality expectations"
    else:
        normalized = 90.0
        explanation = f"Rating {rating:.1f}/5 — low bar, easy to differentiate with quality"
    return SignalResult(
        name="rating_environment", raw_value=rating, normalized=normalized,
        weight=DEFAULT_WEIGHTS["rating_environment"],
        contribution=normalized * DEFAULT_WEIGHTS["rating_environment"],
        explanation=explanation,
    )


def _discount_score(listing: PlatformListing) -> SignalResult:
    discount = listing.discount_pct or 0.0
    normalized = _clamp(100 - discount * 2, 0, 100)
    return SignalResult(
        name="discount_depth", raw_value=discount, normalized=normalized,
        weight=DEFAULT_WEIGHTS["discount_depth"],
        contribution=normalized * DEFAULT_WEIGHTS["discount_depth"],
        explanation=f"{discount:.0f}% avg discount" + (" — deep discounting signals margin pressure" if discount > 30 else ""),
    )


def _price_band_score(listing: PlatformListing, all_listings: list[PlatformListing]) -> SignalResult:
    price = listing.price_current
    if price is None:
        return SignalResult(
            name="price_band_fit", raw_value=None, normalized=50.0,
            weight=DEFAULT_WEIGHTS["price_band_fit"],
            contribution=50.0 * DEFAULT_WEIGHTS["price_band_fit"],
            explanation="No price data (neutral score)",
        )
    prices = [l.price_current for l in all_listings if l.price_current and l.platform == listing.platform]
    if len(prices) < 2:
        return SignalResult(
            name="price_band_fit", raw_value=price, normalized=70.0,
            weight=DEFAULT_WEIGHTS["price_band_fit"],
            contribution=70.0 * DEFAULT_WEIGHTS["price_band_fit"],
            explanation=f"Price ₹{price:,.0f} (limited comparison data)",
        )
    lo, hi = min(prices), max(prices)
    if hi == lo:
        normalized = 80.0
    else:
        position = (price - lo) / (hi - lo)
        normalized = _clamp(100 * (1 - abs(position - 0.5) * 2), 30, 100)
    return SignalResult(
        name="price_band_fit", raw_value=price, normalized=normalized,
        weight=DEFAULT_WEIGHTS["price_band_fit"],
        contribution=normalized * DEFAULT_WEIGHTS["price_band_fit"],
        explanation=f"Price ₹{price:,.0f} in range ₹{lo:,.0f}–₹{hi:,.0f}",
    )


def _category_momentum_score() -> SignalResult:
    return SignalResult(
        name="category_momentum", raw_value=None, normalized=50.0,
        weight=DEFAULT_WEIGHTS["category_momentum"],
        contribution=50.0 * DEFAULT_WEIGHTS["category_momentum"],
        explanation="Category momentum signal not yet available (neutral score)",
    )


def _wholesale_score(listing: PlatformListing) -> list[SignalResult]:
    signals: list[SignalResult] = []

    moq = listing.min_order_qty or 1
    moq_norm = _clamp(100 * (1 - min(moq, 1000) / 1000), 0, 100)
    signals.append(SignalResult(
        name="moq_accessibility", raw_value=float(moq), normalized=moq_norm,
        weight=WHOLESALE_WEIGHTS["moq_accessibility"],
        contribution=moq_norm * WHOLESALE_WEIGHTS["moq_accessibility"],
        explanation=f"MOQ: {moq} units" + (" (low barrier)" if moq <= 10 else " (bulk order required)" if moq > 100 else ""),
    ))

    price_min = listing.price_min
    price_max = listing.price_max
    if price_min and price_max:
        spread = (price_max - price_min) / price_min * 100 if price_min > 0 else 0
        norm = _clamp(80 - spread, 20, 100)
        signals.append(SignalResult(
            name="price_range_value", raw_value=spread, normalized=norm,
            weight=WHOLESALE_WEIGHTS["price_range_value"],
            contribution=norm * WHOLESALE_WEIGHTS["price_range_value"],
            explanation=f"Price range ${price_min:.2f}–${price_max:.2f} ({spread:.0f}% spread)",
        ))
    else:
        signals.append(SignalResult(
            name="price_range_value", raw_value=None, normalized=50.0,
            weight=WHOLESALE_WEIGHTS["price_range_value"],
            contribution=50.0 * WHOLESALE_WEIGHTS["price_range_value"],
            explanation="No price range data (neutral)",
        ))

    rating = listing.rating or 0
    norm = _clamp(rating * 20, 0, 100)
    signals.append(SignalResult(
        name="supplier_trust", raw_value=rating, normalized=norm,
        weight=WHOLESALE_WEIGHTS["supplier_trust"],
        contribution=norm * WHOLESALE_WEIGHTS["supplier_trust"],
        explanation=f"Supplier rating: {rating:.1f}/5.0",
    ))

    reviews = listing.review_count or 0
    norm = _clamp(min(reviews, 500) / 5, 0, 100)
    signals.append(SignalResult(
        name="demand_proxy", raw_value=float(reviews), normalized=norm,
        weight=WHOLESALE_WEIGHTS["demand_proxy"],
        contribution=norm * WHOLESALE_WEIGHTS["demand_proxy"],
        explanation=f"{reviews} reviews",
    ))

    price = listing.price_current or 0
    norm = _clamp(70, 30, 100)
    signals.append(SignalResult(
        name="price_band_fit", raw_value=price, normalized=norm,
        weight=WHOLESALE_WEIGHTS["price_band_fit"],
        contribution=norm * WHOLESALE_WEIGHTS["price_band_fit"],
        explanation=f"Unit price ${price:.2f}",
    ))

    return signals


def score_product(
    db: Session,
    product_id: int,
    weights: dict[str, float] | None = None,
) -> list[ScoringResult]:
    """Score a product across all platforms it has listings on.

    Returns a list of ScoringResult, one per platform, sorted by score desc.
    """
    listings = db.execute(
        select(PlatformListing).where(PlatformListing.product_id == product_id)
    ).scalars().all()

    if not listings:
        return []

    w = weights or DEFAULT_WEIGHTS
    results: list[ScoringResult] = []

    for listing in listings:
        is_wholesale = listing.platform == "alibaba"

        if is_wholesale:
            signals = _wholesale_score(listing)
        else:
            signals = [
                _competition_score(listing, listings),
                _price_trend_score(listing, db),
                _demand_score(listing, listings),
                _rating_score(listing),
                _discount_score(listing),
                _price_band_score(listing, listings),
                _category_momentum_score(),
            ]

        total = sum(s.contribution for s in signals)
        score = _clamp(total, 0, 100)

        components = {
            s.name: {
                "raw_value": s.raw_value,
                "normalized": round(s.normalized, 1),
                "weight": s.weight,
                "contribution": round(s.contribution, 2),
            }
            for s in signals
        }

        explanation_parts = [s.explanation for s in signals if s.explanation]
        label = "Wholesale/Sourcing" if is_wholesale else "Retail"
        explanation = f"{listing.platform.title()} ({label}): " + "; ".join(explanation_parts)

        results.append(ScoringResult(
            platform=listing.platform,
            score=round(score, 1),
            components=components,
            explanation=explanation,
            is_wholesale=is_wholesale,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    for i, r in enumerate(results):
        r.rank = i + 1

    total_score = sum(r.score for r in results)
    for r in results:
        r.suggested_inventory_share_pct = round(
            100 * _safe_div(r.score, total_score, 1 / len(results)), 1
        )

    return results


def compute_and_store_scores(
    db: Session,
    product_id: int,
) -> list[OpportunityScore]:
    """Compute scores and persist them as OpportunityScore rows."""
    results = score_product(db, product_id)
    stored = []

    for r in results:
        existing = db.execute(
            select(OpportunityScore).where(
                OpportunityScore.product_id == product_id,
                OpportunityScore.platform == r.platform,
            )
        ).scalar_one_or_none()

        if existing:
            existing.score = r.score
            existing.rank = r.rank
            existing.components = r.components
            existing.explanation = r.explanation
            existing.suggested_inventory_share_pct = r.suggested_inventory_share_pct
            existing.computed_at = datetime.now(timezone.utc)
            stored.append(existing)
        else:
            opp = OpportunityScore(
                product_id=product_id,
                platform=r.platform,
                score=r.score,
                rank=r.rank,
                components=r.components,
                explanation=r.explanation,
                suggested_inventory_share_pct=r.suggested_inventory_share_pct,
            )
            db.add(opp)
            stored.append(opp)

    db.commit()
    return stored
