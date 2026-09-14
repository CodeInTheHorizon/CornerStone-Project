"""Dataset builder endpoints.

Phase 5 only: these produce and inspect the ML-ready table. No training, no
prediction, no scoring.
"""

from app.auth.permissions import Permission
from app.auth.rate_limits import operation


from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.ml import features as feature_module
from app.ml.dataset_builder import DatasetFilters, DatasetMetadata
from app.models import User
from app.schemas.dataset import (
    DatasetBuildRequest,
    DatasetBuildResponse,
    DatasetMetadataRead,
    DatasetPreviewResponse,
    DatasetStatusResponse,
)
from app.services import dataset_service

router = APIRouter(prefix="/ml/dataset", tags=["dataset"])

DEMO_NOTICE = (
    "Dataset contains DEMO records and is intended for development/testing."
)


def _notice(source_types: list[str]) -> str | None:
    """Warn whenever synthetic rows are present, mixed or not."""
    return DEMO_NOTICE if "demo" in source_types else None


@router.post(
    "/build",
    response_model=DatasetBuildResponse,
    summary="Build an ML-ready dataset from stored snapshots",
)
def build(
    payload: DatasetBuildRequest,
    db: Session = Depends(get_db),
    _: User = Depends(operation(Permission.BUILD, "build")),
) -> DatasetBuildResponse:
    filters = DatasetFilters(
        platforms=payload.platforms,
        categories=payload.categories,
        keyword=payload.keyword,
        source_types=payload.source_types,
        start=payload.start,
        end=payload.end,
    )

    try:
        result = dataset_service.build_and_store(
            db, filters, persist=payload.persist
        )
    except dataset_service.InsufficientDataError as exc:
        # 422 rather than 404: the request was well formed, the data was not
        # sufficient. The body says which, so the UI can explain it.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "insufficient_data", "reason": exc.reason},
        ) from None

    meta: DatasetMetadata = result.metadata
    return DatasetBuildResponse(
        dataset_id=meta.dataset_id,
        rows=meta.total_output_rows,
        features=meta.feature_count,
        source_types=meta.source_types,
        removed_rows=meta.removed_rows,
        generated_at=meta.generated_at,
        metadata=DatasetMetadataRead(**meta.to_dict()),
        notice=_notice(meta.source_types),
    )


@router.get(
    "/status",
    response_model=DatasetStatusResponse,
    summary="State of the most recently built dataset",
)
def dataset_status(_: User = Depends(get_current_user)) -> DatasetStatusResponse:
    datasets = dataset_service.list_datasets()
    latest = datasets[0] if datasets else None

    return DatasetStatusResponse(
        has_dataset=latest is not None,
        latest=DatasetMetadataRead(**latest) if latest else None,
        stored_datasets=len(datasets),
        available_features=feature_module.FEATURE_NAMES,
        notice=_notice(latest.get("source_types", [])) if latest else None,
    )


@router.get(
    "/preview",
    response_model=DatasetPreviewResponse,
    summary="First rows of a stored dataset",
)
def preview(
    dataset_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=dataset_service.MAX_PREVIEW_ROWS),
    _: User = Depends(get_current_user),
) -> DatasetPreviewResponse:
    found = dataset_service.preview_rows(dataset_id, limit)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No dataset has been built yet.",
        )

    rows, metadata = found
    return DatasetPreviewResponse(
        dataset_id=metadata["dataset_id"],
        rows=rows,
        columns=list(rows[0].keys()) if rows else [],
        total_rows=metadata.get("total_output_rows", len(rows)),
        notice=_notice(metadata.get("source_types", [])),
    )
