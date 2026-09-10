"""Model training, evaluation and comparison.

Deliberately small: one preprocessing pipeline, two candidate models, one
documented selection rule. No hyperparameter search -- on a dataset this size
it would tune to noise, and the phase is about proving the pipeline works.

Everything that could inflate a score is treated as a defect:

* Preprocessing is fitted inside the pipeline, on training data only, so
  validation statistics never leak backwards through an imputer or encoder.
* The split is time-aware, because the same listing appears on consecutive
  dates and a random split would put near-duplicate rows on both sides.
* Every result is reported next to the majority-class baseline, so a score
  that merely matches "always guess the most common class" is visible as such.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.target import (
    CLASSES,
    TARGET_COLUMN,
    TARGET_HELPER_COLUMNS,
    class_distribution,
    majority_baseline,
)

logger = logging.getLogger(__name__)

RANDOM_SEED = 42

#: Validation accuracy at or above this is treated as suspicious rather than
#: good. Predicting next-period price direction is genuinely hard; a score
#: this high almost always means leakage or train/validation overlap.
SUSPICIOUS_ACCURACY = 0.95

#: Below this, a train/validation split is not meaningful.
MIN_TRAINING_ROWS = 40
MIN_VALIDATION_ROWS = 10

try:  # pragma: no cover - environment dependent
    from xgboost import XGBClassifier

    XGBOOST_AVAILABLE = True
    XGBOOST_ERROR: str | None = None
except Exception as exc:  # pragma: no cover
    XGBClassifier = None  # type: ignore[assignment]
    XGBOOST_AVAILABLE = False
    XGBOOST_ERROR = str(exc)


#: Columns excluded from the feature matrix, with the reason.
#:
#: Identity columns would let a tree memorise individual listings; the raw
#: timestamp would let it memorise dates; the helper columns encode the future
#: the target is built from and would hand the model the answer.
EXCLUDED_COLUMNS: dict[str, str] = {
    "snapshot_id": "row identifier - memorisable, no predictive meaning",
    "product_key": "listing identifier - would let the model memorise listings",
    "external_id": "platform listing id - identifier, not a signal",
    "product_name": "free text identifier - high-cardinality, memorisable",
    "currency": "constant in the current data - no signal",
    "collection_timestamp": "raw timestamp - would let the model memorise dates",
    "forward_price": "derived from the future - direct target leakage",
    "forward_price_change_pct": "the target's own source - direct target leakage",
    TARGET_COLUMN: "the target itself",
}

#: Low-cardinality categoricals that are legitimate signal.
CATEGORICAL_FEATURES = ["platform", "source_type", "category_normalized", "brand_normalized"]


class TrainingError(Exception):
    """Training could not proceed. Carries a machine-readable status."""

    def __init__(self, reason: str, status: str = "training_failed"):
        super().__init__(reason)
        self.reason = reason
        self.status = status


@dataclass
class ModelResult:
    name: str
    metrics: dict[str, float]
    confusion_matrix: list[list[int]]
    labels: list[str]
    pipeline: Any = None
    error: str | None = None

    @property
    def trained(self) -> bool:
        return self.pipeline is not None


@dataclass
class TrainingOutcome:
    target: str
    results: list[ModelResult]
    selected: ModelResult
    feature_names: list[str]
    numeric_features: list[str]
    categorical_features: list[str]
    excluded_columns: dict[str, str]
    training_rows: int
    validation_rows: int
    split_strategy: str
    split_rationale: str
    class_distribution: dict[str, int]
    majority_baseline: float | None
    selection_rule: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Feature selection and splitting
# ---------------------------------------------------------------------------


def select_features(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Split usable columns into numeric and categorical feature lists."""
    candidates = [c for c in frame.columns if c not in EXCLUDED_COLUMNS]

    categorical = [c for c in CATEGORICAL_FEATURES if c in candidates]
    numeric = [
        c
        for c in candidates
        if c not in categorical and pd.api.types.is_numeric_dtype(frame[c])
    ]

    # Anything left is unhandled free text; drop it rather than one-hot encoding
    # something high-cardinality by accident.
    return numeric, categorical


def time_aware_split(
    frame: pd.DataFrame, validation_fraction: float = 0.2
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Split on observation date: earlier dates train, the latest validate.

    Each listing appears on several consecutive dates, so a random split would
    place day 3 and day 4 of the same listing on opposite sides -- rows that
    are near-identical by construction. The model would score well by having
    effectively seen the validation rows already.
    """
    dates = sorted(frame["collection_timestamp"].unique())

    if len(dates) < 2:
        raise TrainingError(
            "The dataset covers a single observation date, so no time-aware "
            "split is possible. Collect or import data over more than one date.",
            status="insufficient_data",
        )

    # Take whole dates from the end until the validation share is reached.
    cutoff_index = len(dates)
    for index in range(len(dates) - 1, 0, -1):
        share = frame["collection_timestamp"].isin(dates[index:]).mean()
        cutoff_index = index
        if share >= validation_fraction:
            break

    cutoff = dates[cutoff_index]
    train = frame[frame["collection_timestamp"] < cutoff].copy()
    validation = frame[frame["collection_timestamp"] >= cutoff].copy()

    description = (
        f"time-aware: train < {pd.Timestamp(cutoff).date()}, "
        f"validate >= {pd.Timestamp(cutoff).date()}"
    )
    return train, validation, description


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def build_preprocessor(
    numeric: list[str], categorical: list[str]
) -> ColumnTransformer:
    """Imputation + scaling for numerics, imputation + one-hot for categoricals.

    Wrapped in a ColumnTransformer inside the model Pipeline so it is fitted on
    the training fold only.
    """
    numeric_pipeline = Pipeline(
        [
            # Median rather than mean: the price columns are skewed.
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    return ColumnTransformer(
        [
            ("numeric", numeric_pipeline, numeric),
            ("categorical", categorical_pipeline, categorical),
        ],
        remainder="drop",
    )


def _evaluate(
    name: str, y_true: pd.Series, y_pred: np.ndarray, pipeline: Any
) -> ModelResult:
    labels = [c for c in CLASSES if c in set(y_true) | set(y_pred)]

    metrics = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_weighted": round(
            float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
            4,
        ),
        "recall_weighted": round(
            float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4
        ),
        "f1_weighted": round(
            float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4
        ),
        "f1_macro": round(
            float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4
        ),
    }

    return ModelResult(
        name=name,
        metrics=metrics,
        confusion_matrix=confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        labels=labels,
        pipeline=pipeline,
    )


def _candidates(model_names: list[str] | None) -> dict[str, Any]:
    """Model constructors to try, keyed by name."""
    wanted = model_names or ["random_forest", "xgboost"]
    built: dict[str, Any] = {}

    if "random_forest" in wanted:
        built["random_forest"] = RandomForestClassifier(
            n_estimators=200,
            min_samples_leaf=2,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        )

    if "xgboost" in wanted and XGBOOST_AVAILABLE:
        built["xgboost"] = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=RANDOM_SEED,
            tree_method="hist",
            # Labels are strings; encoded by the caller before fitting.
            objective="multi:softprob",
        )

    return built


#: How the winner is picked, stated so it can be argued with.
SELECTION_RULE = (
    "Highest weighted F1 on the validation split. F1 rather than accuracy "
    "because the classes are imbalanced, and weighted rather than macro so "
    "each class counts in proportion to how often it actually occurs. Ties "
    "break toward the simpler model (RandomForest)."
)


def train_models(
    frame: pd.DataFrame,
    model_names: list[str] | None = None,
    validation_fraction: float = 0.2,
) -> TrainingOutcome:
    """Train the candidate models and return every result plus the winner."""
    warnings: list[str] = []

    if TARGET_COLUMN not in frame.columns:
        raise TrainingError(
            f"The dataset has no '{TARGET_COLUMN}' column.", status="missing_target"
        )

    labelled = frame[frame[TARGET_COLUMN].notna()].copy()
    if labelled.empty:
        raise TrainingError(
            "No rows could be labelled. Each listing needs at least two "
            "observations so a following price is available.",
            status="insufficient_data",
        )

    distribution = class_distribution(labelled)
    if len(distribution) < 2:
        raise TrainingError(
            f"Target contains only one class ({list(distribution)}). "
            "A classifier needs at least two.",
            status="insufficient_data",
        )

    train, validation, split_description = time_aware_split(
        labelled, validation_fraction
    )

    if len(train) < MIN_TRAINING_ROWS:
        raise TrainingError(
            f"Only {len(train)} training rows after splitting; at least "
            f"{MIN_TRAINING_ROWS} are needed.",
            status="insufficient_data",
        )
    if len(validation) < MIN_VALIDATION_ROWS:
        raise TrainingError(
            f"Only {len(validation)} validation rows after splitting; at least "
            f"{MIN_VALIDATION_ROWS} are needed.",
            status="insufficient_data",
        )

    if len(set(train[TARGET_COLUMN])) < 2:
        raise TrainingError(
            "The training split contains only one class after the time-aware "
            "split.",
            status="insufficient_data",
        )

    numeric, categorical = select_features(labelled)
    if not numeric and not categorical:
        raise TrainingError("No usable feature columns.", status="missing_features")

    feature_columns = numeric + categorical
    x_train, y_train = train[feature_columns], train[TARGET_COLUMN]
    x_validation, y_validation = validation[feature_columns], validation[TARGET_COLUMN]

    candidates = _candidates(model_names)
    if not candidates:
        raise TrainingError("No model types were selected.", status="no_models")

    if "xgboost" in (model_names or ["random_forest", "xgboost"]) and not XGBOOST_AVAILABLE:
        warnings.append(f"XGBoost is unavailable and was skipped: {XGBOOST_ERROR}")

    results: list[ModelResult] = []
    for name, estimator in candidates.items():
        try:
            pipeline = Pipeline(
                [
                    ("preprocess", build_preprocessor(numeric, categorical)),
                    ("model", estimator),
                ]
            )

            if name == "xgboost":
                # XGBoost needs integer labels; map and map back on predict.
                mapping = {label: index for index, label in enumerate(CLASSES)}
                inverse = {index: label for label, index in mapping.items()}
                pipeline.fit(x_train, y_train.map(mapping))
                predictions = np.array(
                    [inverse[int(p)] for p in pipeline.predict(x_validation)]
                )
            else:
                pipeline.fit(x_train, y_train)
                predictions = pipeline.predict(x_validation)

            results.append(_evaluate(name, y_validation, predictions, pipeline))
        except Exception as exc:  # a failing candidate must not kill the run
            logger.exception("Training %s failed", name)
            results.append(
                ModelResult(
                    name=name,
                    metrics={},
                    confusion_matrix=[],
                    labels=[],
                    error=str(exc),
                )
            )

    trained = [r for r in results if r.trained]
    if not trained:
        raise TrainingError(
            "Every candidate model failed to train. "
            + "; ".join(f"{r.name}: {r.error}" for r in results),
            status="training_failed",
        )

    # Highest weighted F1; ties break toward RandomForest as the simpler model.
    selected = max(
        trained,
        key=lambda r: (r.metrics.get("f1_weighted", 0), r.name == "random_forest"),
    )

    baseline = majority_baseline(validation)
    if baseline is not None and selected.metrics.get("accuracy", 0) <= baseline:
        warnings.append(
            f"The selected model's accuracy ({selected.metrics.get('accuracy')}) "
            f"does not beat always guessing the most common class ({baseline}). "
            "On this data that is expected rather than a bug -- see the "
            "limitations note."
        )

    if selected.metrics.get("accuracy", 0) >= SUSPICIOUS_ACCURACY:
        warnings.append(
            "Validation accuracy is near-perfect, which usually indicates "
            "target leakage or train/validation overlap rather than a good "
            "model. Inspect before trusting this result."
        )

    return TrainingOutcome(
        target=TARGET_COLUMN,
        results=results,
        selected=selected,
        feature_names=feature_columns,
        numeric_features=numeric,
        categorical_features=categorical,
        excluded_columns={
            k: v for k, v in EXCLUDED_COLUMNS.items() if k in frame.columns
        },
        training_rows=len(train),
        validation_rows=len(validation),
        split_strategy=split_description,
        split_rationale=(
            "Repeated observations of the same listing on consecutive dates "
            "make a random split leak: adjacent days are near-duplicates. "
            "Splitting on date keeps every listing's future strictly unseen."
        ),
        class_distribution=distribution,
        majority_baseline=baseline,
        selection_rule=SELECTION_RULE,
        warnings=warnings,
    )
