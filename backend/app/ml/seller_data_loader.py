"""Extensible loader and schema validator for seller historical sales data.

Allows a seller to upload their own ground-truth order/sales data:
X = product + price + marketplace + market features
y = actual units sold

All ingested seller data is tagged with source_type = 'seller_data' and
isolated from live scraped marketplace snapshots.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.models.enums import SourceType

logger = logging.getLogger(__name__)

SELLER_REQUIRED_COLUMNS = {
    "date",
    "product",
    "category",
    "platform",
    "selling_price",
    "units_sold",
}

SELLER_OPTIONAL_COLUMNS = {
    "discount",
    "revenue",
    "inventory",
}


class SellerDataValidationError(ValueError):
    """Raised when seller sales data format is invalid."""


def parse_and_validate_seller_data(
    source: str | Path | pd.DataFrame,
    seller_id: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Parse, validate, and standardize seller-provided sales data.

    Returns the cleaned DataFrame ready for demand modeling and metadata summary.
    """
    if isinstance(source, (str, Path)):
        path = Path(source).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Seller file not found: {path}")
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        elif path.suffix.lower() in (".json", ".jsonl"):
            df = pd.read_json(path)
        else:
            raise SellerDataValidationError(f"Unsupported format: {path.suffix}")
    elif isinstance(source, pd.DataFrame):
        df = source.copy()
    else:
        raise TypeError("Source must be a file path or pandas DataFrame.")

    # Standardize column names (lowercase, stripped)
    df.columns = [str(c).lower().strip() for c in df.columns]

    missing = SELLER_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise SellerDataValidationError(
            f"Seller data is missing mandatory fields: {sorted(missing)}. "
            f"Required fields: {sorted(SELLER_REQUIRED_COLUMNS)}."
        )

    # Validate non-empty sales labels
    initial_len = len(df)
    valid_mask = df["units_sold"].notna() & (df["units_sold"] >= 0)
    df = df[valid_mask].copy()

    if df.empty:
        raise SellerDataValidationError("No rows found with valid non-negative units_sold.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    df["price"] = pd.to_numeric(df["selling_price"], errors="coerce")
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce").astype(int)

    if "discount" in df.columns:
        df["discount_percentage"] = pd.to_numeric(df["discount"], errors="coerce").fillna(0.0)
    else:
        df["discount_percentage"] = 0.0

    df["platform"] = df["platform"].astype(str).str.lower().str.strip()
    df["category"] = df["category"].astype(str).str.lower().str.strip()
    df["product_name"] = df["product"].astype(str).str.strip()
    df["product_id"] = df["product_name"].str.lower().str.replace(r"\s+", "_", regex=True)

    # Provenance tagging
    df["source_type"] = SourceType.SELLER_DATA.value
    if seller_id:
        df["seller_id"] = seller_id

    metadata = {
        "source_type": SourceType.SELLER_DATA.value,
        "seller_id": seller_id,
        "total_records": len(df),
        "dropped_unlabelled": initial_len - len(df),
        "date_range": [df["date"].min().strftime("%Y-%m-%d"), df["date"].max().strftime("%Y-%m-%d")],
        "platforms": sorted(df["platform"].unique().tolist()),
        "categories": sorted(df["category"].unique().tolist()),
        "total_units_sold": int(df["units_sold"].sum()),
    }

    return df, metadata
