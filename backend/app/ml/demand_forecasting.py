"""Demand Forecasting Regression Models and Pipeline.

Trains supervised learning models to forecast actual demand (`units_sold`) using:
- Chronological time-based train-validation-test split (NO data leakage).
- Models: Ridge Regression, Random Forest Regressor, XGBoost Regressor.
- Metrics: MAE, RMSE, R², WAPE, MAPE.
- Selection based on validation performance (WAPE / MAE).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBRegressor = None
    XGBOOST_AVAILABLE = False

logger = logging.getLogger(__name__)

NUMERIC_FEATURES = [
    "price",
    "discount_percentage",
    "rating",
    "review_count",
    "review_velocity",
    "inventory",
]

CATEGORICAL_FEATURES = [
    "platform",
    "category",
]

TARGET_COLUMN = "units_sold"


@dataclass
class DemandModelResult:
    name: str
    algorithm: str
    metrics: dict[str, float]
    pipeline: Any
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DemandForecastingOutcome:
    selected_model: DemandModelResult
    all_results: list[DemandModelResult]
    training_rows: int
    validation_rows: int
    split_date: str
    feature_names: list[str]
    target: str = TARGET_COLUMN


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Calculate regression metrics: MAE, RMSE, R², WAPE, and MAPE."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    # Predictions cannot be physically negative for unit sales
    y_pred_clipped = np.clip(y_pred, 0.0, None)

    mae = float(mean_absolute_error(y_true, y_pred_clipped))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred_clipped)))
    r2 = float(r2_score(y_true, y_pred_clipped))

    # WAPE = sum(|y - y_hat|) / sum(y)
    sum_y = float(np.sum(y_true))
    wape = float(np.sum(np.abs(y_true - y_pred_clipped)) / sum_y) if sum_y > 0 else 0.0

    # MAPE (safe for zeros)
    non_zero = y_true > 0
    if np.any(non_zero):
        mape = float(np.mean(np.abs((y_true[non_zero] - y_pred_clipped[non_zero]) / y_true[non_zero])))
    else:
        mape = 0.0

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2": round(r2, 4),
        "wape": round(wape, 4),
        "mape": round(mape, 4),
    }


def chronological_split(
    df: pd.DataFrame,
    date_col: str = "date",
    val_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Perform a strict chronological train/validation split without forward leakage."""
    sorted_df = df.sort_values(date_col).copy()
    dates = sorted_df[date_col].drop_duplicates().sort_values()

    n_val_dates = max(1, int(len(dates) * val_fraction))
    split_idx = len(dates) - n_val_dates
    split_date = dates.iloc[split_idx]

    train = sorted_df[sorted_df[date_col] < split_date].copy()
    val = sorted_df[sorted_df[date_col] >= split_date].copy()

    split_desc = f"Temporal boundary: Train before {split_date.strftime('%Y-%m-%d')}, Validation on/after."
    return train, val, split_desc


def build_preprocessor(numeric_cols: list[str], categorical_cols: list[str]) -> ColumnTransformer:
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    return ColumnTransformer([
        ("num", num_pipeline, numeric_cols),
        ("cat", cat_pipeline, categorical_cols),
    ])


def train_demand_models(
    df: pd.DataFrame,
    val_fraction: float = 0.2,
    artifact_dir: Path | None = None,
) -> DemandForecastingOutcome:
    """Train candidate regression models on chronological split and pick best performer."""
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Target column '{TARGET_COLUMN}' missing from dataframe.")

    train_df, val_df, split_desc = chronological_split(df, val_fraction=val_fraction)

    available_num = [c for c in NUMERIC_FEATURES if c in df.columns]
    available_cat = [c for c in CATEGORICAL_FEATURES if c in df.columns]

    X_train = train_df[available_num + available_cat]
    y_train = train_df[TARGET_COLUMN].to_numpy()

    X_val = val_df[available_num + available_cat]
    y_val = val_df[TARGET_COLUMN].to_numpy()

    candidates: dict[str, tuple[str, Any]] = {
        "ridge": ("Ridge Regression", Ridge(alpha=1.0)),
        "random_forest": ("Random Forest Regressor", RandomForestRegressor(
            n_estimators=150,
            max_depth=10,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )),
    }

    if XGBOOST_AVAILABLE:
        candidates["xgboost"] = ("XGBoost Regressor", XGBRegressor(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.08,
            random_state=42,
            tree_method="hist",
        ))

    results: list[DemandModelResult] = []

    for name, (algo_label, regressor) in candidates.items():
        preprocessor = build_preprocessor(available_num, available_cat)
        pipe = Pipeline([
            ("preprocessor", preprocessor),
            ("regressor", regressor),
        ])

        pipe.fit(X_train, y_train)
        val_preds = pipe.predict(X_val)
        metrics = calculate_metrics(y_val, val_preds)

        results.append(
            DemandModelResult(
                name=name,
                algorithm=algo_label,
                metrics=metrics,
                pipeline=pipe,
            )
        )

    # Selection rule: Lowest WAPE, breaking ties with lowest MAE
    selected = min(results, key=lambda r: (r.metrics["wape"], r.metrics["mae"]))

    if artifact_dir:
        artifact_dir = Path(artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(selected.pipeline, artifact_dir / "demand_forecast_model.pkl")

    return DemandForecastingOutcome(
        selected_model=selected,
        all_results=results,
        training_rows=len(train_df),
        validation_rows=len(val_df),
        split_date=split_desc,
        feature_names=available_num + available_cat,
    )
