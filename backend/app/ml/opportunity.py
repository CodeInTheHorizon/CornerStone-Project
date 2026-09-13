"""Experimental observed-opportunity score, formula version 1.

Fixed point budgets sum to 100. Model probabilities can contribute at most
10 points, regardless of missing data. Missing signals earn no points and
are explicitly reported as unavailable; they are never treated as measured
zero or reweighted. Coverage therefore matters when comparing platforms.

This is a transparent heuristic, not expected profit, sales demand, or a
calibrated probability of marketplace success. Constants are judgement calls.
"""

from __future__ import annotations

import math
from typing import Mapping

WEIGHTS = {
    "model_signal": 10,
    "price_competitiveness": 20,
    "rating_signal": 15,
    "review_signal": 15,
    "discount_signal": 10,
    "competition_signal": 15,
    "price_trend": 15,
}
FORMULA_VERSION = "observed-opportunity-v1"
EXPLANATIONS = {
    "model_signal": "P(improving) + 0.5 × P(stable); at most 10 points. Probabilities are uncalibrated.",
    "price_competitiveness": "clip(1.5 − price / category market median, 0, 1). Median-priced = half points; lower prices score higher, not higher margins.",
    "rating_signal": "Rating / 5, clipped to 0–1.",
    "review_signal": "Mean of available signals: log(1 + reviews) / log(10001), and review momentum / 20. Each clipped to 0–1; momentum is reviews per observation.",
    "discount_signal": "Discount percentage / 50, clipped to 0–1. Discounts are activity signals, not profit.",
    "competition_signal": "1 − Phase 5 competition score / 100, clipped to 0–1.",
    "price_trend": "clip(0.5 + 10 × price slope / current price, 0, 1). Flat = half points; +5% per observation = full points.",
}


def number(value: object) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def score(row: Mapping, probabilities: dict[str, float] | None) -> dict:
    """Return score, normalized signals, contributions, and available coverage."""
    def scaled(name: str, scale: float) -> float | None:
        value = number(row.get(name))
        return None if value is None else clip(value / scale)

    ratio = number(row.get("price_vs_market_median"))
    reviews = number(row.get("review_count"))
    competition = number(row.get("competition_score"))
    price = number(row.get("effective_price"))
    slope = number(row.get("short_term_price_trend"))
    review_signals = [
        None if reviews is None else clip(math.log1p(max(0, reviews)) / math.log1p(10_000)),
        scaled("review_momentum", 20),
    ]
    available_reviews = [v for v in review_signals if v is not None]
    signals = {
        "model_signal": None if probabilities is None else clip(
            probabilities.get("improving", 0) + 0.5 * probabilities.get("stable", 0)
        ),
        "price_competitiveness": None if ratio is None else clip(1.5 - ratio),
        "rating_signal": scaled("rating", 5),
        "review_signal": sum(available_reviews) / len(available_reviews) if available_reviews else None,
        "discount_signal": scaled("discount_percentage", 50),
        "competition_signal": None if competition is None else clip(1 - competition / 100),
        "price_trend": None if slope is None or price is None or price <= 0 else clip(0.5 + 10 * slope / price),
    }
    contributions = {
        key: round(WEIGHTS[key] * value, 3) if value is not None else 0.0
        for key, value in signals.items()
    }
    return {
        "opportunity_score": round(sum(contributions.values()), 1),
        "components": contributions,
        "normalized_signals": signals,
        "coverage_weight": sum(WEIGHTS[key] for key, value in signals.items() if value is not None),
        "missing_components": [key for key, value in signals.items() if value is None],
    }
