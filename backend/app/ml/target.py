"""Target definition for the MarketPulse AI model.

## What is predicted

`marketplace_opportunity_class` -- the direction a listing's price is about to
move, in three classes:

* `improving`  -- price rises by more than the threshold by the next observation
* `stable`     -- price moves within +/- the threshold
* `declining`  -- price falls by more than the threshold

## Why forward-looking

The obvious approach -- score each row from its own Phase 5 features and use
that score as the label -- produces a tautology. The model would be handed the
same numbers the label was computed from and would simply re-derive the
formula, scoring near-perfectly while having learned nothing. Predicting the
*next* observation makes this a genuine forecasting problem: the features
describe now, the label describes what happens next, and no feature contains
the answer.

## Why price direction is the opportunity signal

MarketPulse AI is built for sellers. A listing whose price is holding or rising
indicates a market that can bear the price -- room for margin. A falling price
indicates pressure. So a rising price is `improving` opportunity for a seller,
which is the opposite of how a buyer would read it.

## What this is not

This is a **proxy**, not demand. Marketplace pages do not expose unit sales, so
nothing here measures how much anyone actually bought. It measures where the
asking price is heading, which is an observable stand-in for competitive
pressure -- and no more than that.

Rows with no following observation cannot be labelled and are excluded from
training rather than assigned a default class.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET_COLUMN = "marketplace_opportunity_class"

CLASS_DECLINING = "declining"
CLASS_STABLE = "stable"
CLASS_IMPROVING = "improving"
CLASSES = [CLASS_DECLINING, CLASS_STABLE, CLASS_IMPROVING]

#: Percentage move that separates a real change from noise. 1.0 was chosen by
#: inspecting the class balance on the available data: it produced the most
#: even three-way split, and therefore the least trivially-guessable target.
DEFAULT_THRESHOLD_PCT = 1.0

#: Columns created while building the target. They encode the future and must
#: never reach the model.
TARGET_HELPER_COLUMNS = [
    "forward_price",
    "forward_price_change_pct",
]

#: Grouping that defines "the same listing over time".
GROUP_KEYS = ["platform", "product_key"]


def add_target(
    frame: pd.DataFrame,
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
) -> pd.DataFrame:
    """Attach the target column, plus the helper columns used to derive it.

    Deterministic: the same frame and threshold always produce the same labels.
    The final observation of each listing has no successor, so its target is
    NaN -- the caller drops those rows rather than inventing a class.
    """
    if frame.empty:
        out = frame.copy()
        for column in [*TARGET_HELPER_COLUMNS, TARGET_COLUMN]:
            out[column] = pd.Series(dtype="object")
        return out

    out = frame.sort_values([*GROUP_KEYS, "collection_timestamp"]).copy()
    grouped = out.groupby(GROUP_KEYS, dropna=False, sort=False)

    out["forward_price"] = grouped["effective_price"].shift(-1)
    out["forward_price_change_pct"] = (
        (out["forward_price"] - out["effective_price"])
        / out["effective_price"].replace(0, np.nan)
        * 100
    )

    out[TARGET_COLUMN] = pd.cut(
        out["forward_price_change_pct"],
        bins=[-np.inf, -threshold_pct, threshold_pct, np.inf],
        labels=CLASSES,
    ).astype("object")

    return out


def labelled_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Only the rows that could actually be labelled."""
    if TARGET_COLUMN not in frame.columns:
        return frame.iloc[0:0]
    return frame[frame[TARGET_COLUMN].notna()].copy()


def class_distribution(frame: pd.DataFrame) -> dict[str, int]:
    if TARGET_COLUMN not in frame.columns:
        return {}
    counts = frame[TARGET_COLUMN].value_counts().to_dict()
    return {str(label): int(count) for label, count in counts.items()}


def majority_baseline(frame: pd.DataFrame) -> float | None:
    """Accuracy obtainable by always guessing the most common class.

    Reported alongside every result: a model that cannot beat this has learned
    nothing, however respectable its raw accuracy looks.
    """
    distribution = class_distribution(frame)
    total = sum(distribution.values())
    if not total:
        return None
    return round(max(distribution.values()) / total, 4)
