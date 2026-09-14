"""Leakage-safe evaluation: split, labels, baselines, probability quality, gate.

## The boundary rule (Phase 12)

The target is the direction of a listing's *next* observed price. Before
Phase 12, labels were generated over the whole dataset and the rows were then
split by date, so the last training day's labels came from validation-day
prices: on the DEMO dataset, 96 of 288 training rows crossed the boundary.

Now the boundary is chosen first, from observation dates alone, and labels are
generated inside each partition independently:

* training rows are dated before the boundary, and their label observation is
  also before it;
* validation rows are dated on or after the boundary, and their label
  observation is inside the validation window.

Features may still describe the past (a validation row's previous price can be
a training-period observation). That is information available at prediction
time, not future data.

## Split strategy: temporal, not grouped

The same listings appear in both partitions. That measures what the product
needs -- forecasting the next move of listings a seller is already watching --
but it does not measure generalization to never-seen products. The overlap is
reported with every run, and when enough unseen-product validation rows exist
their accuracy is reported separately. A grouped split is not used as the
primary strategy: on the current data every listing is observed on every date,
so it would leave no validation rows at all.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.ml import target as target_module
from app.ml.target import CLASSES, TARGET_COLUMN

#: Fixed list of guarantees recorded with every model trained by this module.
LEAKAGE_SAFEGUARDS = [
    "Split boundary chosen from observation dates before any label is generated.",
    "Labels generated separately inside the training and validation partitions; no label crosses the boundary.",
    "Listing and timestamp identifiers, the target and its helper columns are excluded from features.",
    "Preprocessing is fitted on the training partition only, inside the model pipeline.",
    "Engineered features use each listing's own past and same-date market peers only.",
    "Near-perfect validation accuracy is flagged as suspected leakage.",
]

SPLIT_STRATEGY = "temporal (boundary-first, per-partition labels)"
SPLIT_RATIONALE = (
    "Repeated observations of one listing make a random split leak, and labels "
    "generated before splitting let the last training day learn from validation "
    "prices. The boundary is fixed first and each side is labelled separately. "
    "Listings are shared across the boundary on purpose: the product forecasts "
    "listings a seller already watches. Unseen-product generalization is reported "
    "separately when enough unseen listings exist."
)

#: Below this many validation rows, probability metrics are reported but not interpreted.
PROBABILITY_MIN_ROWS = 200
#: Calibration bins for expected calibration error.
ECE_BINS = 5
#: Validation evidence a model needs before "validated" is even considered.
VALIDATED_MIN_VALIDATION_ROWS = 200
VALIDATED_MIN_VALIDATION_DATES = 2
#: Two-sided 95% normal quantile for the accuracy lower bound.
Z_95 = 1.96


class SplitError(ValueError):
    """The data cannot support a leakage-safe split. Carries a user-facing reason."""


@dataclass
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    boundary: pd.Timestamp
    description: str
    #: Rows that would have been labelled from the other side of the boundary.
    boundary_purged_rows: int
    training_range: dict[str, str | None]
    validation_range: dict[str, str | None]
    observation_dates: int
    safeguards: list[str] = field(default_factory=lambda: list(LEAKAGE_SAFEGUARDS))

    def summary(self) -> dict[str, Any]:
        return {
            "strategy": SPLIT_STRATEGY,
            "description": self.description,
            "boundary": self.boundary.isoformat(),
            "training_range": self.training_range,
            "validation_range": self.validation_range,
            "boundary_purged_rows": self.boundary_purged_rows,
            "observation_dates": self.observation_dates,
            "leakage_safeguards": self.safeguards,
            "rationale": SPLIT_RATIONALE,
        }


def _utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True)


def observation_dates(frame: pd.DataFrame) -> list[pd.Timestamp]:
    """Distinct UTC calendar dates, oldest first."""
    if frame.empty:
        return []
    return sorted(_utc(frame["collection_timestamp"]).dt.floor("D").unique())


def _range(frame: pd.DataFrame, column: str = "collection_timestamp") -> dict[str, str | None]:
    if frame.empty:
        return {"start": None, "end": None}
    stamps = _utc(frame[column])
    return {"start": stamps.min().isoformat(), "end": stamps.max().isoformat()}


def label_partition(partition: pd.DataFrame) -> pd.DataFrame:
    """Labelled rows of one partition, labelled from that partition only."""
    return target_module.labelled_rows(target_module.add_target(partition))


def temporal_split(frame: pd.DataFrame, validation_fraction: float = 0.2) -> TemporalSplit:
    """Choose a date boundary, then label each side independently.

    The latest boundary is chosen whose validation side holds at least
    `validation_fraction` of all safely labelled rows, with labelled rows on
    both sides. Raises SplitError when no such boundary exists.
    """
    required = {"platform", "product_key", "collection_timestamp", "effective_price"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SplitError(f"The dataset lacks columns needed to derive the target: {', '.join(missing)}.")

    base = frame.drop(columns=[c for c in [*target_module.TARGET_HELPER_COLUMNS, TARGET_COLUMN] if c in frame.columns]).copy()
    base["collection_timestamp"] = _utc(base["collection_timestamp"])
    dates = observation_dates(base)
    if len(dates) < 2:
        raise SplitError(
            "The dataset covers a single observation date, so no time-aware split is possible. "
            "Collect or import data over more than one date."
        )

    globally_labelled = int(target_module.labelled_rows(target_module.add_target(base)).shape[0])
    chosen: tuple[pd.Timestamp, pd.DataFrame, pd.DataFrame] | None = None
    for index in range(len(dates) - 1, 0, -1):
        boundary = pd.Timestamp(dates[index])
        train = label_partition(base[base["collection_timestamp"] < boundary])
        validation = label_partition(base[base["collection_timestamp"] >= boundary])
        if train.empty or validation.empty:
            continue
        if len(validation) / (len(train) + len(validation)) >= validation_fraction:
            chosen = (boundary, train, validation)
            break
    if chosen is None:
        raise SplitError(
            "No date boundary leaves labelled rows on both sides with a large enough validation share. "
            "Each side needs at least two observation dates per listing; collect over more dates."
        )

    boundary, train, validation = chosen
    purged = globally_labelled - len(train) - len(validation)
    return TemporalSplit(
        train=train,
        validation=validation,
        boundary=boundary,
        description=(
            f"temporal, boundary-first: train observations and labels < {boundary.date()}, "
            f"validate observations and labels >= {boundary.date()}; "
            f"{purged} boundary-crossing label(s) purged"
        ),
        boundary_purged_rows=purged,
        training_range=_range(train),
        validation_range=_range(validation),
        observation_dates=len(dates),
    )


# ---------------------------------------------------------------------------
# Product overlap
# ---------------------------------------------------------------------------


def group_overlap(train: pd.DataFrame, validation: pd.DataFrame) -> dict[str, Any]:
    """How much listing/product identity is shared across the split."""
    train_listings = set(map(tuple, train[["platform", "product_key"]].drop_duplicates().to_numpy()))
    validation_listings = set(map(tuple, validation[["platform", "product_key"]].drop_duplicates().to_numpy()))
    train_products = set(train["product_key"])
    unseen = validation[~validation["product_key"].isin(train_products)]
    shared = train_listings & validation_listings
    return {
        "validation_listings": len(validation_listings),
        "listings_also_in_training": len(shared),
        "listing_overlap_share": round(len(shared) / len(validation_listings), 4) if validation_listings else None,
        "validation_products": int(validation["product_key"].nunique()),
        "unseen_product_validation_rows": int(len(unseen)),
        "measures": "temporal generalization on listings already observed; unseen-product accuracy reported separately when enough unseen rows exist",
    }


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _direction(change_pct: pd.Series, threshold: float = target_module.DEFAULT_THRESHOLD_PCT) -> pd.Series:
    return pd.cut(change_pct, bins=[-np.inf, -threshold, threshold, np.inf], labels=CLASSES).astype("object")


def baselines(train: pd.DataFrame, validation: pd.DataFrame) -> dict[str, Any]:
    """Naive predictors scored on the validation rows, as accuracies.

    * majority_baseline: share of the validation set's most common class (the
      best any constant guess could do in hindsight; the historical comparison).
    * training_majority_accuracy: always predicting the training set's most
      common class (the constant guess available without hindsight).
    * persistence_accuracy: predicting that the last observed move repeats,
      falling back to the training majority where no previous move exists.

    All are accuracies. F1 must not be compared against them.
    """
    truth = validation[TARGET_COLUMN]
    majority = target_module.majority_baseline(validation)
    train_counts = train[TARGET_COLUMN].value_counts()
    train_majority = str(train_counts.idxmax()) if not train_counts.empty else None
    train_majority_accuracy = round(float((truth == train_majority).mean()), 4) if train_majority else None

    persistence = None
    coverage = 0
    if "price_change_percentage" in validation.columns and train_majority:
        previous = _direction(pd.to_numeric(validation["price_change_percentage"], errors="coerce"))
        coverage = int(previous.notna().sum())
        guess = previous.where(previous.notna(), train_majority)
        persistence = round(float((guess == truth).mean()), 4)

    candidates = [value for value in (majority, train_majority_accuracy, persistence) if value is not None]
    return {
        "majority_baseline": majority,
        "training_majority_class": train_majority,
        "training_majority_accuracy": train_majority_accuracy,
        "persistence_accuracy": persistence,
        "persistence_coverage_rows": coverage,
        "best_baseline_accuracy": max(candidates) if candidates else None,
        "metric": "accuracy",
    }


# ---------------------------------------------------------------------------
# Probability quality
# ---------------------------------------------------------------------------


def probability_quality(
    truth: pd.Series,
    probabilities: np.ndarray | None,
    training_distribution: dict[str, int],
) -> dict[str, Any]:
    """Log loss, multiclass Brier score and expected calibration error.

    Columns of `probabilities` follow CLASSES. Nothing is recalibrated: these
    numbers describe the raw model outputs, and the outputs stay labelled
    uncalibrated whatever they show.
    """
    if probabilities is None:
        return {"available": False, "calibration_status": "unavailable", "assessment": "no_probabilities"}

    index = {label: position for position, label in enumerate(CLASSES)}
    y = truth.map(index).to_numpy(dtype=int)
    n = len(y)
    probs = np.clip(np.asarray(probabilities, dtype=float), 1e-15, 1.0)
    probs = probs / probs.sum(axis=1, keepdims=True)
    onehot = np.eye(len(CLASSES))[y]

    log_loss = float(-np.log(probs[np.arange(n), y]).mean())
    brier = float(((probs - onehot) ** 2).sum(axis=1).mean())

    total = sum(training_distribution.values()) or 1
    prior = np.array([max(training_distribution.get(label, 0), 1) / total for label in CLASSES])
    prior = prior / prior.sum()
    prior_log_loss = float(-np.log(prior[y]).mean())

    confidence = probs.max(axis=1)
    correct = probs.argmax(axis=1) == y
    edges = np.linspace(0, 1, ECE_BINS + 1)
    ece = 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        chosen = (confidence > low) & (confidence <= high)
        if chosen.any():
            ece += chosen.mean() * abs(correct[chosen].mean() - confidence[chosen].mean())

    if n < PROBABILITY_MIN_ROWS:
        assessment = "insufficient_data"
    elif log_loss >= prior_log_loss:
        assessment = "worse_than_class_prior"
    else:
        assessment = "better_than_class_prior"

    return {
        "available": True,
        "calibration_status": "uncalibrated",
        "assessment": assessment,
        "rows": n,
        "log_loss": round(log_loss, 4),
        "uniform_log_loss": round(math.log(len(CLASSES)), 4),
        "class_prior_log_loss": round(prior_log_loss, 4),
        "brier_score": round(brier, 4),
        "uniform_brier_score": round(float(((np.full_like(probs, 1 / len(CLASSES)) - onehot) ** 2).sum(axis=1).mean()), 4),
        "expected_calibration_error": round(float(ece), 4),
        "mean_confidence": round(float(confidence.mean()), 4),
        "minimum_rows_for_interpretation": PROBABILITY_MIN_ROWS,
    }


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------


def accuracy_lower_bound(accuracy: float, rows: int) -> float:
    """Wilson 95% lower bound for an accuracy measured on `rows` examples."""
    if rows <= 0:
        return 0.0
    denominator = 1 + Z_95**2 / rows
    centre = accuracy + Z_95**2 / (2 * rows)
    margin = Z_95 * math.sqrt(accuracy * (1 - accuracy) / rows + Z_95**2 / (4 * rows**2))
    return round((centre - margin) / denominator, 4)


def quality_gate(
    *,
    accuracy: float | None,
    baseline_report: dict[str, Any],
    source_types: list[str],
    validation_rows: int,
    validation_dates: int,
    probability_report: dict[str, Any],
    development_override: bool = False,
    leakage_safe_split: bool = True,
) -> tuple[str, list[str]]:
    """Quality status and the reasons for it.

    * below_baseline -- accuracy does not beat the majority baseline.
    * experimental   -- beats it, but DEMO data, a development override, an
                        unverified split or missing evidence is involved.
    * candidate      -- real (IMPORTED/LIVE) data beating every naive baseline.
    * validated      -- a candidate whose accuracy lower bound beats every
                        baseline on enough rows and dates, with probabilities
                        better than the class prior. Never from one metric.
    """
    reasons: list[str] = []
    majority = baseline_report.get("majority_baseline")
    best = baseline_report.get("best_baseline_accuracy")

    if accuracy is None or majority is None:
        return "experimental", ["Accuracy or majority baseline is unavailable; quality cannot be established."]
    if accuracy <= majority:
        return "below_baseline", [f"Accuracy {accuracy} does not beat the majority baseline accuracy {majority}."]

    if not leakage_safe_split:
        reasons.append("Trained before the Phase 12 boundary-leakage fix; its validation score is not trustworthy.")
    if "demo" in source_types:
        reasons.append("Trained on synthetic DEMO data; it can never be more than experimental.")
    if development_override:
        reasons.append("Trained with a development override that mixed DEMO data with other provenance.")
    if best is not None and accuracy <= best:
        reasons.append(f"Accuracy {accuracy} does not beat the strongest naive baseline ({best}).")
    if reasons:
        return "experimental", reasons

    reasons.append(f"Real-data model beats every naive baseline (accuracy {accuracy} vs best baseline {best}).")
    blockers: list[str] = []
    if validation_rows < VALIDATED_MIN_VALIDATION_ROWS:
        blockers.append(f"Only {validation_rows} validation rows; {VALIDATED_MIN_VALIDATION_ROWS} are required to validate.")
    if validation_dates < VALIDATED_MIN_VALIDATION_DATES:
        blockers.append(f"Validation labels span {validation_dates} date(s); {VALIDATED_MIN_VALIDATION_DATES} are required.")
    lower = accuracy_lower_bound(accuracy, validation_rows)
    if best is not None and lower <= best:
        blockers.append(f"Accuracy 95% lower bound {lower} does not clear the best baseline {best}.")
    if probability_report.get("assessment") != "better_than_class_prior":
        blockers.append(f"Probability quality is '{probability_report.get('assessment')}', not better than the class prior.")
    if blockers:
        return "candidate", reasons + blockers
    return "validated", reasons + [
        f"Accuracy 95% lower bound {lower} clears every baseline on {validation_rows} rows over "
        f"{validation_dates} dates, and log loss beats the class prior. Probabilities remain uncalibrated."
    ]
