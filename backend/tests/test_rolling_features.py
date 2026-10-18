"""Tests for rolling window historical feature engineering and estimated demand signals."""

import pandas as pd
import numpy as np
import pytest

from app.ml.features import build_features, ROLLING_HISTORICAL_FEATURES, FEATURE_NAMES
from app.ml.demand_signal import calculate_estimated_demand_signal, DEMAND_PROXY_VERSION


def test_rolling_historical_features():
    dates = pd.to_datetime([
        "2026-10-01 10:00:00+00:00",
        "2026-10-03 10:00:00+00:00",
        "2026-10-05 10:00:00+00:00",
        "2026-10-07 10:00:00+00:00",
    ])
    raw = pd.DataFrame({
        "product_key": "prod-galaxy-a56",
        "platform": "flipkart",
        "collection_timestamp": dates,
        "price": [30999.0, 29999.0, 28999.0, 28499.0],
        "original_price": [34999.0, 34999.0, 34999.0, 34999.0],
        "discount_percentage": [11.4, 14.3, 17.1, 18.6],
        "rating": [4.3, 4.3, 4.4, 4.4],
        "review_count": [4000, 4100, 4250, 4410],
        "availability": ["In Stock", "In Stock", "In Stock", "In Stock"],
        "category_normalized": "smartphones",
        "brand_normalized": "samsung",
    })

    feats = build_features(raw)

    # Check all features are present
    for col in ROLLING_HISTORICAL_FEATURES:
        assert col in feats.columns, f"Missing feature: {col}"

    # Oct 1 to Oct 7 review growth
    last_row = feats.iloc[-1]
    assert last_row["review_growth_7d"] == 410.0
    assert last_row["review_velocity"] > 50.0  # 410 / 6 days = ~68.3 reviews/day
    assert last_row["price_change_7d"] == -2500.0
    assert last_row["price_volatility_30d"] > 0.0
    assert last_row["stockout_frequency"] == 0.0


def test_estimated_demand_signal_proxy():
    features = {
        "review_count": 4410,
        "review_growth_7d": 410.0,
        "review_velocity": 68.3,
        "rating": 4.4,
        "stockout_frequency": 0.0,
        "short_term_price_trend": 10.0,
        "effective_price": 28499.0,
    }

    result = calculate_estimated_demand_signal(features)

    assert result["is_proxy"] is True
    assert result["target_type"] == "proxy_demand_signal"
    assert result["formula_version"] == DEMAND_PROXY_VERSION
    assert 0.0 <= result["demand_signal_score"] <= 100.0
    assert "review_velocity_signal" in result["components"]
    assert "disclaimer" in result
    assert "NOT represent audited units sold" in result["disclaimer"]
