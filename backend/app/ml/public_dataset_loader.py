"""Loader and validator for public historical retail datasets (Kaggle, UCI, research).

Strict rules per architecture:
1. Every observation carries source_type = 'public_dataset'.
2. The dataset must provide ground-truth `units_sold` for true demand forecasting.
3. NEVER silently fabricate missing sales labels. If `units_sold` is missing or NaN,
   the row is dropped from training.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.models.enums import SourceType

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {
    "date",
    "product_id",
    "category",
    "platform",
    "price",
    "units_sold",
}

OPTIONAL_FIELDS = {
    "product_name",
    "brand",
    "mrp",
    "discount_percentage",
    "rating",
    "review_count",
    "review_velocity",
    "inventory",
    "revenue",
}


class DatasetValidationError(ValueError):
    """Raised when an uploaded public historical dataset fails integrity checks."""


def load_public_dataset(
    file_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load, validate, and type-normalize a public historical e-commerce dataset.

    Returns the cleaned DataFrame and an audit metadata summary.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Historical dataset file not found at: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in (".json", ".jsonl"):
        df = pd.read_json(path)
    elif path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise DatasetValidationError(
            f"Unsupported file format: {path.suffix}. Use CSV, JSON, or Parquet."
        )

    # 1. Check required columns
    missing = REQUIRED_FIELDS - set(df.columns)
    if missing:
        raise DatasetValidationError(
            f"Dataset is missing required columns for demand forecasting: {sorted(missing)}. "
            f"Required columns are: {sorted(REQUIRED_FIELDS)}."
        )

    initial_count = len(df)

    # 2. Enforce ground truth `units_sold` - NEVER silently fabricate
    unlabelled_mask = df["units_sold"].isna() | (df["units_sold"] < 0)
    unlabelled_count = int(unlabelled_mask.sum())
    if unlabelled_count > 0:
        logger.warning(
            "Dropping %d rows with missing or negative units_sold labels. Fabricating labels is forbidden.",
            unlabelled_count,
        )
        df = df[~unlabelled_mask].copy()

    if df.empty:
        raise DatasetValidationError("Dataset has no rows with valid `units_sold` target labels.")

    # 3. Clean and normalize types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce").astype(int)

    if "discount_percentage" in df.columns:
        df["discount_percentage"] = pd.to_numeric(df["discount_percentage"], errors="coerce").fillna(0.0)
    elif "mrp" in df.columns:
        mrp = pd.to_numeric(df["mrp"], errors="coerce")
        df["discount_percentage"] = (((mrp - df["price"]) / mrp) * 100).clip(lower=0.0).fillna(0.0)
    else:
        df["discount_percentage"] = 0.0

    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").clip(0.0, 5.0)
    else:
        df["rating"] = None

    if "review_count" in df.columns:
        df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(0).astype(int)
    else:
        df["review_count"] = 0

    # Ensure platform is lowercase string
    df["platform"] = df["platform"].astype(str).str.lower().str.strip()
    df["category"] = df["category"].astype(str).str.lower().str.strip()

    # Tag provenance explicitly
    df["source_type"] = SourceType.PUBLIC_DATASET.value

    metadata = {
        "source_type": SourceType.PUBLIC_DATASET.value,
        "file_name": path.name,
        "initial_rows": initial_count,
        "valid_rows": len(df),
        "dropped_unlabelled": unlabelled_count,
        "date_range": [df["date"].min().strftime("%Y-%m-%d"), df["date"].max().strftime("%Y-%m-%d")],
        "platforms": sorted(df["platform"].unique().tolist()),
        "categories": sorted(df["category"].unique().tolist()),
        "mean_units_sold": round(float(df["units_sold"].mean()), 2),
    }

    return df, metadata
