"""Builds, persists and retrieves processed datasets through configured storage.

Development uses data/processed/; production uses PostgreSQL binary/JSON bundles.
Filenames carry a timestamp and the dataset id, so a build never overwrites a
previous one -- an earlier dataset may be the one a model was trained on, and
silently replacing it would break that link.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.dataset_builder import (
    DatasetFilters,
    DatasetResult,
    InsufficientDataError,
    build_dataset,
)
from app.storage.dataset_store import DatasetStore

logger = logging.getLogger(__name__)

PROCESSED_DIR = settings.DATA_DIR / "processed"

#: Hard cap on preview rows returned through the API, so a 50k-row dataset
#: cannot be pulled through the browser.
MAX_PREVIEW_ROWS = 100


def build_and_store(
    db: Session,
    filters: DatasetFilters | None = None,
    *,
    persist: bool = True,
) -> DatasetResult:
    """Build a dataset and, by default, write it to data/processed/.

    Raises InsufficientDataError when nothing survives filtering or cleaning.
    """
    result = build_dataset(db, filters)

    if not persist:
        return result

    DatasetStore(PROCESSED_DIR).save(result)

    logger.info(
        "Wrote dataset %s (%d rows) to %s",
        result.metadata.dataset_id,
        result.metadata.total_output_rows,
        result.metadata.csv_path,
    )
    return result


def list_datasets() -> list[dict[str, Any]]:
    """Every stored dataset's metadata, newest first."""
    return DatasetStore(PROCESSED_DIR).catalog()


def latest_dataset() -> dict[str, Any] | None:
    datasets = list_datasets()
    return datasets[0] if datasets else None


def dataset_available(metadata: dict[str, Any]) -> bool:
    """Whether a catalogued dataset still has its CSV payload."""
    csv_path = metadata.get("csv_path")
    if not csv_path:
        return False
    if settings.storage_backend == "local":
        return Path(csv_path).is_file()
    # Database bundles store payload and metadata in one row, so a catalogued
    # dataset always has its payload; csv_path is a dbstore:// reference.
    return True


def load_dataset_frame(dataset_id: str | None = None, *, nrows: int | None = None) -> pd.DataFrame | None:
    """Read a stored dataset back. Defaults to the most recent one."""
    metadata = (
        next(
            (d for d in list_datasets() if d.get("dataset_id") == dataset_id),
            None,
        )
        if dataset_id
        else latest_dataset()
    )
    if metadata is None:
        return None

    if not metadata.get("csv_path"):
        return None
    try:
        return DatasetStore(PROCESSED_DIR).load(metadata, nrows=nrows)
    except (OSError, ValueError, pd.errors.ParserError):
        logger.warning("Processed dataset could not be read")
        return None


def preview_rows(
    dataset_id: str | None = None, limit: int = 20
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """First N rows of a stored dataset, as JSON-safe dictionaries."""
    metadata = (
        next((d for d in list_datasets() if d.get("dataset_id") == dataset_id), None)
        if dataset_id
        else latest_dataset()
    )
    if metadata is None:
        return None

    frame = load_dataset_frame(metadata["dataset_id"], nrows=max(1, min(limit, MAX_PREVIEW_ROWS)))
    if frame is None:
        return None

    limited = frame.head(max(1, min(limit, MAX_PREVIEW_ROWS)))
    # NaN is not valid JSON; None is, and preserves "this value is missing".
    records = limited.astype(object).where(pd.notna(limited), None).to_dict("records")
    return records, metadata


__all__ = [
    "DatasetFilters",
    "InsufficientDataError",
    "build_and_store",
    "dataset_available",
    "latest_dataset",
    "list_datasets",
    "load_dataset_frame",
    "preview_rows",
]
