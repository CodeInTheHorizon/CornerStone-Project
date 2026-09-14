"""Model training, evaluation and comparison.

Deliberately small: one preprocessing pipeline, two candidate models, one
documented selection rule. No hyperparameter search -- on a dataset this size
it would tune to noise, and the phase is about proving the pipeline works.

Everything that could inflate a score is treated as a defect:

* Preprocessing is fitted inside the pipeline, on training data only, so
  validation statistics never leak backwards through an imputer or encoder.
* The split is time-aware and boundary-first (Phase 12): labels are generated
  inside each partition, so no training label depends on a validation-period
  price. Any target already present on the input frame is discarded.
* Every result is reported next to naive baselines (majority class, training
  majority, persistence), so a score that merely matches a guess is visible.
* Minimum data requirements are enforced before fitting, not after.
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

from app.config import settings
from app.ml import validation as validation_module
from app.ml.target import (
    CLASSES,
    TARGET_COLUMN,
    TARGET_HELPER_COLUMNS,
    class_distribution,
)

logger = logging.getLogger(__name__)

RANDOM_SEED = 42

#: Validation accuracy at or above this is treated as suspicious rather than
#: good. Predicting next-period price direction is genuinely hard; a score
#: this high almost always means leakage or train/validation overlap.
SUSPICIOUS_ACCURACY = 0.95


@dataclass(frozen=True)
class TrainingRequirements:
    """Minimum evidence before any model is fitted. Configurable via ML_MIN_* settings.

    Defaults: 100 labelled rows so the validation share is not a handful of
    rows; 60 training / 20 validation rows so each side has a few examples per
    class; 10 products so a model is not a lookup of a few listings; 4 dates
    because each side of the boundary needs two dates to label anything; and 5
    training rows per class so no class is learned from one or two examples.
    """

    min_labelled_rows: int = 100
    min_training_rows: int = 60
    min_validation_rows: int = 20
    min_unique_products: int = 10
    min_observation_dates: int = 4
    min_rows_per_class: int = 5

    @classmethod
    def from_settings(cls) -> "TrainingRequirements":
        return cls(
            min_labelled_rows=settings.ML_MIN_LABELLED_ROWS,
            min_training_rows=settings.ML_MIN_TRAINING_ROWS,
            min_validation_rows=settings.ML_MIN_VALIDATION_ROWS,
            min_unique_products=settings.ML_MIN_UNIQUE_PRODUCTS,
            min_observation_dates=settings.ML_MIN_OBSERVATION_DATES,
            min_rows_per_class=settings.ML_MIN_ROWS_PER_CLASS,
        )

    def to_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


#: Backwards-compatible names for the default minimums.
MIN_TRAINING_ROWS = TrainingRequirements.min_training_rows
MIN_VALIDATION_ROWS = TrainingRequirements.min_validation_rows

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
    "target_observed_at": "timestamp of the future observation behind the label - direct target leakage",
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
    #: Phase 12 evaluation evidence.
    split: dict[str, Any] = field(default_factory=dict)
    baselines: dict[str, Any] = field(default_factory=dict)
    probability_quality: dict[str, Any] = field(default_factory=dict)
    group_overlap: dict[str, Any] = field(default_factory=dict)
    data_summary: dict[str, Any] = field(default_factory=dict)
    requirements: dict[str, int] = field(default_factory=dict)
    training_class_distribution: dict[str, int] = field(default_factory=dict)
    validation_class_distribution: dict[str, int] = field(default_factory=dict)
    unseen_product_accuracy: float | None = None


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
    """Leakage-safe temporal split returning labelled (train, validation, description).

    Any target already on `frame` is discarded: labels are regenerated inside
    each side of a date boundary (see app.ml.validation.temporal_split).
    """
    try:
        split = validation_module.temporal_split(frame, validation_fraction)
    except validation_module.SplitError as exc:
        raise TrainingError(str(exc), status="insufficient_data") from None
    return split.train, split.validation, split.description


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


def _probabilities(pipeline: Any, name: str, features: pd.DataFrame) -> np.ndarray | None:
    """Class probabilities with columns in CLASSES order, or None."""
    if not hasattr(pipeline, "predict_proba"):
        return None
    raw = np.asarray(pipeline.predict_proba(features), dtype=float)
    classes = list(getattr(pipeline, "classes_", []))
    if name == "xgboost":
        # Integer ids map through CLASSES, exactly as at fit time.
        classes = [CLASSES[int(value)] for value in classes] if classes else CLASSES[: raw.shape[1]]
    aligned = np.zeros((raw.shape[0], len(CLASSES)))
    for column, label in enumerate(classes):
        if label in CLASSES:
            aligned[:, CLASSES.index(label)] = raw[:, column]
    return aligned


def _predict(pipeline: Any, name: str, features: pd.DataFrame) -> np.ndarray:
    if name == "xgboost":
        return np.array([CLASSES[int(value)] for value in pipeline.predict(features)])
    return np.asarray(pipeline.predict(features))


def _insufficient(reason: str) -> TrainingError:
    return TrainingError(reason, status="insufficient_data")


def train_models(
    frame: pd.DataFrame,
    model_names: list[str] | None = None,
    validation_fraction: float = 0.2,
    requirements: TrainingRequirements | None = None,
) -> TrainingOutcome:
    """Train the candidate models on a leakage-safe split and return every result.

    `frame` is a processed dataset. Any target columns already on it are
    discarded and regenerated inside each split partition, so a frame labelled
    over the whole history cannot smuggle boundary-crossing labels in.
    """
    requirements = requirements or TrainingRequirements.from_settings()
    warnings: list[str] = []

    required = {"platform", "product_key", "collection_timestamp", "effective_price"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise TrainingError(
            f"The dataset cannot produce '{TARGET_COLUMN}': missing column(s) {', '.join(missing)}.",
            status="missing_target",
        )

    dates = validation_module.observation_dates(frame)
    products = int(frame["product_key"].nunique())
    if len(dates) < requirements.min_observation_dates:
        raise _insufficient(
            f"The dataset covers {len(dates)} observation date(s); at least "
            f"{requirements.min_observation_dates} are required so both sides of the time split can be "
            "labelled. Collect or import observations over more dates."
        )
    if products < requirements.min_unique_products:
        raise _insufficient(
            f"The dataset has {products} unique product(s); at least {requirements.min_unique_products} are required."
        )

    try:
        split = validation_module.temporal_split(frame, validation_fraction)
    except validation_module.SplitError as exc:
        raise _insufficient(str(exc)) from None
    train, validation = split.train, split.validation
    labelled = pd.concat([train, validation])

    distribution = class_distribution(labelled)
    if len(distribution) < 2:
        raise _insufficient(
            f"Target contains only one class ({list(distribution)}). A classifier needs at least two."
        )
    if len(labelled) < requirements.min_labelled_rows:
        raise _insufficient(
            f"Only {len(labelled)} rows can be labelled without crossing the split boundary; "
            f"at least {requirements.min_labelled_rows} are required."
        )
    if len(train) < requirements.min_training_rows:
        raise _insufficient(
            f"Only {len(train)} training rows after the leakage-safe split; at least "
            f"{requirements.min_training_rows} are needed."
        )
    if len(validation) < requirements.min_validation_rows:
        raise _insufficient(
            f"Only {len(validation)} validation rows after the leakage-safe split; at least "
            f"{requirements.min_validation_rows} are needed."
        )
    train_distribution = class_distribution(train)
    thin = [label for label in CLASSES if train_distribution.get(label, 0) < requirements.min_rows_per_class]
    if thin:
        raise _insufficient(
            "The training period has too few examples of class(es) "
            + ", ".join(f"{label} ({train_distribution.get(label, 0)})" for label in thin)
            + f"; at least {requirements.min_rows_per_class} per class are required."
        )

    numeric, categorical = select_features(labelled)
    if not numeric and not categorical:
        raise TrainingError("No usable feature columns.", status="missing_features")

    feature_columns = numeric + categorical
    x_train, y_train = train[feature_columns], train[TARGET_COLUMN]
    x_validation, y_validation = validation[feature_columns], validation[TARGET_COLUMN]

    empty_in_training = [column for column in numeric if x_train[column].isna().all()]
    if empty_in_training:
        warnings.append(
            "These features have no values in the training period and carry no signal (the imputer "
            f"drops them): {', '.join(empty_in_training)}. Trend features need at least three prior "
            "observations per listing before the split boundary."
        )

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
                pipeline.fit(x_train, y_train.map({label: index for index, label in enumerate(CLASSES)}))
            else:
                pipeline.fit(x_train, y_train)
            predictions = _predict(pipeline, name, x_validation)
            results.append(_evaluate(name, y_validation, predictions, pipeline))
        except Exception as exc:  # a failing candidate must not kill the run
            logger.exception("Training %s failed", name)
            results.append(
                ModelResult(name=name, metrics={}, confusion_matrix=[], labels=[], error=str(exc))
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

    baseline_report = validation_module.baselines(train, validation)
    accuracy = selected.metrics.get("accuracy", 0)
    majority = baseline_report["majority_baseline"]
    best = baseline_report["best_baseline_accuracy"]
    if majority is not None and accuracy <= majority:
        warnings.append(
            f"The selected model's accuracy ({accuracy}) does not beat always guessing the most "
            f"common class ({majority})."
        )
    elif best is not None and accuracy <= best:
        warnings.append(
            f"The selected model's accuracy ({accuracy}) does not beat the strongest naive baseline ({best})."
        )

    if accuracy >= SUSPICIOUS_ACCURACY:
        warnings.append(
            "Validation accuracy is near-perfect, which usually indicates "
            "target leakage or train/validation overlap rather than a good "
            "model. Inspect before trusting this result."
        )

    probability_report = validation_module.probability_quality(
        y_validation, _probabilities(selected.pipeline, selected.name, x_validation), train_distribution
    )
    overlap = validation_module.group_overlap(train, validation)
    unseen_accuracy = None
    unseen = validation[~validation["product_key"].isin(set(train["product_key"]))]
    if len(unseen) >= requirements.min_validation_rows:
        unseen_predictions = _predict(selected.pipeline, selected.name, unseen[feature_columns])
        unseen_accuracy = round(float((unseen_predictions == unseen[TARGET_COLUMN].to_numpy()).mean()), 4)

    data_summary = {
        "observation_rows": int(len(frame)),
        "labelled_rows": int(len(labelled)),
        "training_rows": int(len(train)),
        "validation_rows": int(len(validation)),
        "observation_dates": len(dates),
        "validation_label_dates": len(validation_module.observation_dates(validation)),
        "unique_products": products,
        "boundary_purged_rows": split.boundary_purged_rows,
    }

    return TrainingOutcome(
        target=TARGET_COLUMN,
        results=results,
        selected=selected,
        feature_names=feature_columns,
        numeric_features=numeric,
        categorical_features=categorical,
        excluded_columns={
            k: v for k, v in EXCLUDED_COLUMNS.items() if k in labelled.columns or k in frame.columns
        },
        training_rows=len(train),
        validation_rows=len(validation),
        split_strategy=split.description,
        split_rationale=validation_module.SPLIT_RATIONALE,
        class_distribution=distribution,
        majority_baseline=majority,
        selection_rule=SELECTION_RULE,
        warnings=warnings,
        split=split.summary(),
        baselines=baseline_report,
        probability_quality=probability_report,
        group_overlap=overlap,
        data_summary=data_summary,
        requirements=requirements.to_dict(),
        training_class_distribution=train_distribution,
        validation_class_distribution=class_distribution(validation),
        unseen_product_accuracy=unseen_accuracy,
    )
