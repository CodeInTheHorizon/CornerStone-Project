"""Builds, persists and retrieves processed datasets.

Datasets are written to data/processed/ as a CSV plus a JSON metadata sidecar.
Filenames carry a timestamp and the dataset id, so a build never overwrites a
previous one -- an earlier dataset may be the one a model was trained on, and
silently replacing it would break that link.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
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

logger = logging.getLogger(__name__)

PROCESSED_DIR = settings.DATA_DIR / "processed"
FILENAME_PREFIX = "marketpulse_dataset"

#: Hard cap on preview rows returned through the API, so a 50k-row dataset
#: cannot be pulled through the browser.
MAX_PREVIEW_ROWS = 100


def _paths(generated_at: datetime, dataset_id: str) -> tuple[Path, Path]:
    stamp = generated_at.strftime("%Y%m%dT%H%M%S")
    base = f"{FILENAME_PREFIX}_{stamp}_{dataset_id}"
    return PROCESSED_DIR / f"{base}.csv", PROCESSED_DIR / f"{base}.metadata.json"


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

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    csv_path, metadata_path = _paths(
        result.metadata.generated_at, result.metadata.dataset_id
    )

    result.frame.to_csv(csv_path, index=False)
    result.metadata.csv_path = str(csv_path)
    result.metadata.metadata_path = str(metadata_path)
    metadata_path.write_text(
        json.dumps(result.metadata.to_dict(), indent=2) + "\n", encoding="utf-8"
    )

    logger.info(
        "Wrote dataset %s (%d rows) to %s",
        result.metadata.dataset_id,
        result.metadata.total_output_rows,
        csv_path,
    )
    return result


def list_datasets() -> list[dict[str, Any]]:
    """Every stored dataset's metadata, newest first."""
    if not PROCESSED_DIR.exists():
        return []

    found: list[dict[str, Any]] = []
    for path in PROCESSED_DIR.glob(f"{FILENAME_PREFIX}_*.metadata.json"):
        try:
            from app.schemas.dataset import DatasetMetadataRead
            metadata = json.loads(path.read_text(encoding="utf-8"))
            DatasetMetadataRead.model_validate(metadata)
            found.append(metadata)
        except (OSError, ValueError, TypeError):
            # A corrupt sidecar should not hide every other dataset.
            logger.warning("Could not read dataset metadata at %s", path)

    return sorted(found, key=lambda item: item.get("generated_at", ""), reverse=True)


def latest_dataset() -> dict[str, Any] | None:
    datasets = list_datasets()
    return datasets[0] if datasets else None


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

    csv_path = metadata.get("csv_path")
    if not csv_path or not Path(csv_path).exists():
        return None

    try:
        return pd.read_csv(csv_path, nrows=nrows)
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
    "latest_dataset",
    "list_datasets",
    "load_dataset_frame",
    "preview_rows",
]
