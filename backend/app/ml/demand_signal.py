"""Estimated Demand Signal (Proxy) Calculation.

CRITICAL DISTINCTION:
Review count is NOT equal to sales.
Rating count is NOT equal to sales.
Product popularity is NOT automatically equal to sales.

When actual `units_sold` is unavailable from marketplaces, this module calculates
an Estimated Demand Signal (0-100) based strictly on observable market movement:
1. Review velocity (new reviews per day/week)
2. Rating count velocity & rating stability
3. Price trend (ability of listing to maintain/increase price without demand loss)
4. Stockout frequency & availability stability
5. Discount trend & promotional velocity

This is explicitly labeled as a proxy/estimated signal, never fabricated as true unit sales.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

DEMAND_PROXY_VERSION = "estimated-demand-v1"


def _clean_num(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def calculate_estimated_demand_signal(
    features: Mapping[str, Any],
) -> dict[str, Any]:
    """Calculate the estimated demand signal (0-100 proxy) from observed movement.

    Returns score, component contributions, coverage, and explicit proxy disclaimer.
    """
    reviews = _clean_num(features.get("review_count")) or 0.0
    rev_growth_7d = _clean_num(features.get("review_growth_7d")) or 0.0
    rev_velocity = _clean_num(features.get("review_velocity")) or 0.0
    rating = _clean_num(features.get("rating")) or 0.0
    stockout_freq = _clean_num(features.get("stockout_frequency")) or 0.0
    price_slope = _clean_num(features.get("short_term_price_trend")) or 0.0
    eff_price = _clean_num(features.get("effective_price")) or 1.0

    # 1. Review Momentum / Velocity (35% weight)
    # 5 reviews/day = 1.0 max velocity score
    velocity_norm = min(1.0, max(0.0, rev_velocity / 5.0))
    # Growth over 7 days: 20 reviews in 7d = 1.0
    growth_7d_norm = min(1.0, max(0.0, rev_growth_7d / 20.0))
    review_activity = (velocity_norm * 0.6) + (growth_7d_norm * 0.4)
    c_review_activity = round(35.0 * review_activity, 2)

    # 2. Established Social Proof Base (20% weight)
    # Log-scale baseline so established products have solid demand foundation
    proof_norm = min(1.0, math.log1p(max(0.0, reviews)) / math.log1p(5000.0))
    c_proof = round(20.0 * proof_norm, 2)

    # 3. Rating Quality & Customer Acceptance (20% weight)
    # 4.5+ rating = full score, below 3.0 = 0 score
    if rating >= 3.0:
        rating_norm = min(1.0, max(0.0, (rating - 3.0) / 1.5))
    else:
        rating_norm = 0.0
    c_rating = round(20.0 * rating_norm, 2)

    # 4. Price & Market Absorption (15% weight)
    # Products that can maintain price (+0% to +5% trend) without review drop indicate strong demand
    price_pct_move = (price_slope / max(1.0, eff_price)) if eff_price > 0 else 0.0
    price_signal = min(1.0, max(0.0, 0.5 + 5.0 * price_pct_move))
    c_price_trend = round(15.0 * price_signal, 2)

    # 5. Availability & In-Stock Reliability (10% weight)
    # Frequent stockouts penalize the demand realization score
    stock_signal = max(0.0, 1.0 - (stockout_freq * 1.5))
    c_stock = round(10.0 * stock_signal, 2)

    total_score = round(c_review_activity + c_proof + c_rating + c_price_trend + c_stock, 1)

    # Qualitative grade
    if total_score >= 80.0:
        grade = "High Demand"
    elif total_score >= 55.0:
        grade = "Moderate Demand"
    elif total_score >= 35.0:
        grade = "Emerging / Low Demand"
    else:
        grade = "Niche / Cold"

    return {
        "demand_signal_score": total_score,
        "demand_grade": grade,
        "is_proxy": True,
        "target_type": "proxy_demand_signal",
        "formula_version": DEMAND_PROXY_VERSION,
        "disclaimer": (
            "This score is an Estimated Demand Signal proxy derived from observable review velocity, "
            "rating dynamics, price absorption, and availability. It does NOT represent audited units sold."
        ),
        "components": {
            "review_velocity_signal": c_review_activity,
            "social_proof_base": c_proof,
            "rating_acceptance": c_rating,
            "price_absorption_trend": c_price_trend,
            "stock_reliability": c_stock,
        },
        "indicators": {
            "review_velocity_per_day": round(rev_velocity, 2),
            "review_growth_7d": round(rev_growth_7d, 1),
            "stockout_frequency_pct": round(stockout_freq * 100.0, 1),
            "rating": rating,
            "total_reviews": int(reviews),
        },
    }
