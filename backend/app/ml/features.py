"""Deterministic feature engineering over cleaned snapshot rows.

Every function here is pure: same input frame, same output. No randomness, no
wall-clock reads, no model.

The governing rule is that a missing input produces a missing feature. Where a
value genuinely cannot be computed -- the first observation of a listing has no
prior price -- the result is NaN, not 0. Zero means "no change", which is a
claim about the world, and asserting it for the first row of every listing
would teach a later model that nothing ever moves.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.normalization import availability_state

#: Identity used for time-series grouping: the same listing on one platform.
GROUP_KEYS = ["platform", "product_key"]

#: Marketplace aggregates are computed within a category, per platform.
MARKET_KEYS = ["category_normalized"]

BASIC_FEATURES = [
    "effective_price",
    "discount_amount",
    "discount_percentage",
    "has_discount",
    "rating",
    "review_count",
    "price_to_original_ratio",
]

TIME_FEATURES = [
    "previous_price",
    "price_change_absolute",
    "price_change_percentage",
    "rating_change",
    "review_growth",
    "review_growth_percentage",
    "discount_change",
    "availability_change",
    "observation_index",
    "days_since_previous",
]

MARKET_FEATURES = [
    "listing_count_for_keyword",
    "average_market_price",
    "median_market_price",
    "price_vs_market_average",
    "price_vs_market_median",
    "average_rating",
    "average_review_count",
    "platform_listing_density",
    "competition_score",
]

TREND_FEATURES = [
    "short_term_price_trend",
    "review_momentum",
    "rating_momentum",
    "discount_momentum",
    "availability_trend",
]

FEATURE_NAMES = BASIC_FEATURES + TIME_FEATURES + MARKET_FEATURES + TREND_FEATURES

#: A listing needs at least this many observations before a slope is meaningful.
MIN_TREND_OBSERVATIONS = 3


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Element-wise division that yields NaN rather than inf on a zero divisor."""
    denom = denominator.replace(0, np.nan)
    return numerator / denom


def add_basic_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-row features derived from the row itself."""
    out = frame.copy()

    # The price a buyer actually pays. Falls back to the list price only when
    # no selling price was recorded; if neither exists it stays NaN.
    out["effective_price"] = out["price"].where(out["price"].notna(), out["original_price"])

    both_prices = out["price"].notna() & out["original_price"].notna()
    out["discount_amount"] = np.where(
        both_prices, out["original_price"] - out["price"], np.nan
    )

    # Recompute rather than trusting the stored percentage, so the column is
    # consistent across sources. Keep the stored value where we cannot derive one.
    derived_discount = _safe_ratio(
        out["original_price"] - out["price"], out["original_price"]
    ) * 100
    out["discount_percentage"] = derived_discount.where(
        both_prices, out["discount_percentage"]
    )

    # Nullable boolean: unknown when there is no discount information at all.
    out["has_discount"] = pd.Series(
        np.where(
            out["discount_amount"].notna(),
            out["discount_amount"] > 0,
            None,
        ),
        index=out.index,
        dtype="boolean",
    )

    out["price_to_original_ratio"] = _safe_ratio(out["price"], out["original_price"])

    return out


def add_time_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Change-since-previous-observation features.

    Requires the frame to be sorted chronologically within each group. The
    first observation of every listing gets NaN for each change feature.
    """
    out = frame.sort_values([*GROUP_KEYS, "collection_timestamp"]).copy()
    grouped = out.groupby(GROUP_KEYS, dropna=False, sort=False)

    out["observation_index"] = grouped.cumcount()

    previous_price = grouped["effective_price"].shift(1)
    out["previous_price"] = previous_price
    out["price_change_absolute"] = out["effective_price"] - previous_price
    out["price_change_percentage"] = (
        _safe_ratio(out["price_change_absolute"], previous_price) * 100
    )

    out["rating_change"] = out["rating"] - grouped["rating"].shift(1)

    previous_reviews = grouped["review_count"].shift(1)
    out["review_growth"] = out["review_count"] - previous_reviews
    out["review_growth_percentage"] = (
        _safe_ratio(out["review_growth"], previous_reviews) * 100
    )

    out["discount_change"] = out["discount_percentage"] - grouped[
        "discount_percentage"
    ].shift(1)

    out["availability_change"] = out["availability_state"] - grouped[
        "availability_state"
    ].shift(1)

    elapsed = out["collection_timestamp"] - grouped["collection_timestamp"].shift(1)
    out["days_since_previous"] = elapsed.dt.total_seconds() / 86400

    return out


def add_market_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Marketplace-level context, computed per category per observation date.

    Comparing a listing to the whole history would mix October prices into a
    September comparison, so the peer group is the same category on the same
    date. Cross-platform by design: the point is to place a listing against the
    wider market, not only against its own storefront.
    """
    out = frame.copy()
    out["observation_date"] = out["collection_timestamp"].dt.floor("D")

    market_keys = [*MARKET_KEYS, "observation_date"]
    market = out.groupby(market_keys, dropna=False, sort=False)

    out["listing_count_for_keyword"] = market["product_key"].transform("nunique")
    out["average_market_price"] = market["effective_price"].transform("mean")
    out["median_market_price"] = market["effective_price"].transform("median")
    out["average_rating"] = market["rating"].transform("mean")
    out["average_review_count"] = market["review_count"].transform("mean")

    # Below 1.0 means cheaper than the market.
    out["price_vs_market_average"] = _safe_ratio(
        out["effective_price"], out["average_market_price"]
    )
    out["price_vs_market_median"] = _safe_ratio(
        out["effective_price"], out["median_market_price"]
    )

    # What share of this category's listings sit on this platform, on this date.
    platform_keys = [*market_keys, "platform"]
    per_platform = out.groupby(platform_keys, dropna=False, sort=False)[
        "product_key"
    ].transform("nunique")
    out["platform_listing_density"] = _safe_ratio(
        per_platform, out["listing_count_for_keyword"]
    )

    out["competition_score"] = _competition_score(out)

    return out.drop(columns=["observation_date"])


def _competition_score(frame: pd.DataFrame) -> pd.Series:
    """A deterministic 0-100 estimate of how contested a listing's slot is.

    Not a model and not a prediction -- a documented weighted average of three
    observable signals, each normalized to 0-1 where higher means *more*
    competition:

    * **Listing density (50%)** -- how crowded the category is on that date,
      scaled against a 50-listing reference point and capped at 1.
    * **Price pressure (30%)** -- how far below the market median this listing
      is priced. Undercutting the median indicates a contested slot; at or
      above the median contributes 0.
    * **Review depth (20%)** -- how established the competing listings are,
      log-scaled because review counts span orders of magnitude.

    Weights are a judgement call, stated here so they can be argued with and
    changed. The score is NaN when none of the three components is available:
    an all-zero default would look like "no competition", which is a claim the
    data does not support.
    """
    # Crowding, relative to a 50-listing reference.
    density = (frame["listing_count_for_keyword"] / 50).clip(upper=1.0)

    # How far below the median this listing sits, capped at 50% under.
    below_median = (1 - frame["price_vs_market_median"]).clip(lower=0, upper=0.5) * 2

    # Log-scaled review depth of the surrounding market.
    reviews = frame["average_review_count"]
    review_depth = (np.log1p(reviews) / np.log1p(10_000)).clip(upper=1.0)

    components = pd.DataFrame(
        {
            "density": density * 0.5,
            "price_pressure": below_median * 0.3,
            "review_depth": review_depth * 0.2,
        }
    )
    weights = pd.DataFrame(
        {
            "density": density.notna() * 0.5,
            "price_pressure": below_median.notna() * 0.3,
            "review_depth": review_depth.notna() * 0.2,
        }
    )

    total_weight = weights.sum(axis=1).replace(0, np.nan)
    # Re-weight by what is actually present, so a listing missing one signal is
    # not silently scored as if that signal were zero.
    score = components.sum(axis=1, skipna=True) / total_weight * 100

    return score.round(2)


def _slope(values: pd.Series) -> float:
    """Least-squares slope per observation step. NaN when too few points."""
    usable = values.dropna()
    if len(usable) < MIN_TREND_OBSERVATIONS:
        return np.nan
    x = np.arange(len(usable), dtype=float)
    return float(np.polyfit(x, usable.to_numpy(dtype=float), 1)[0])


def add_trend_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Direction-of-travel features over each listing's own history.

    Every one is a least-squares slope over the observations seen so far, and
    every one is NaN until a listing has MIN_TREND_OBSERVATIONS points. A
    two-point "trend" is a line through noise.
    """
    out = frame.sort_values([*GROUP_KEYS, "collection_timestamp"]).copy()
    grouped = out.groupby(GROUP_KEYS, dropna=False, sort=False)

    definitions = {
        "short_term_price_trend": "effective_price",
        "review_momentum": "review_count",
        "rating_momentum": "rating",
        "discount_momentum": "discount_percentage",
        "availability_trend": "availability_state",
    }

    for feature, column in definitions.items():
        # Expanding, so each row sees only its own past -- never future data,
        # which would leak into any model trained on this.
        out[feature] = (
            grouped[column]
            .expanding()
            .apply(_slope, raw=False)
            .reset_index(level=list(range(len(GROUP_KEYS))), drop=True)
            .round(4)
        )

    return out


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply every feature stage in order."""
    if frame.empty:
        return frame

    out = frame.copy()
    out["availability_state"] = out["availability"].map(availability_state)

    out = add_basic_features(out)
    out = add_time_features(out)
    out = add_market_features(out)
    out = add_trend_features(out)

    return out.sort_values(
        ["collection_timestamp", "platform", "product_key"]
    ).reset_index(drop=True)
