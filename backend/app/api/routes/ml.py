"""Model training endpoints.

Phase 6 only: train, evaluate, compare, persist, report. Prediction and the
opportunity score are Phase 7.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.ml.training import XGBOOST_AVAILABLE, TrainingError
from app.models import ModelMetadata, User
from app.schemas.training import (
    AVAILABLE_MODELS,
    ModelMetricsResponse,
    ModelRunResult,
    ModelStatusResponse,
    TrainingRunSummary,
    TrainRequest,
    TrainResponse,
)
from app.services import training_service

router = APIRouter(prefix="/ml", tags=["ml"])

#: Statuses that mean "the request was fine, the data was not".
DATA_STATUSES = {"no_dataset", "insufficient_data", "missing_target", "missing_features"}


def _hyper(record: ModelMetadata) -> dict[str, Any]:
    return record.hyperparameters or {}


def _metrics(record: ModelMetadata) -> dict[str, Any]:
    return record.metrics or {}


def _summary(record: ModelMetadata) -> TrainingRunSummary:
    hyper = _hyper(record)
    return TrainingRunSummary(
        model_version=record.model_version,
        model_type=record.algorithm,
        trained_at=record.trained_at,
        dataset_id=hyper.get("dataset_id"),
        accuracy=record.accuracy,
        f1_weighted=record.f1_score,
        source_types=hyper.get("dataset_source_types", []),
        is_active=record.is_active,
    )


@router.post(
    "/train",
    response_model=TrainResponse,
    summary="Train, evaluate and persist a model",
)
def train(
    payload: TrainRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrainResponse:
    try:
        record = training_service.train(
            db, dataset_id=payload.dataset_id, models=payload.models
        )
    except TrainingError as exc:
        # 422 when the data was inadequate, 500 when training itself broke.
        code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if exc.status in DATA_STATUSES
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(
            status_code=code, detail={"status": exc.status, "reason": exc.reason}
        ) from None

    hyper = _hyper(record)
    metrics = _metrics(record)

    return TrainResponse(
        model_version=record.model_version,
        selected_model=record.algorithm or "unknown",
        target=hyper.get("target", ""),
        training_rows=hyper.get("training_rows", 0),
        validation_rows=hyper.get("validation_rows", 0),
        metrics={
            key: value
            for key, value in metrics.items()
            if isinstance(value, (int, float)) and key != "majority_baseline"
        },
        majority_baseline=metrics.get("majority_baseline"),
        dataset_id=hyper.get("dataset_id", ""),
        dataset_source_types=hyper.get("dataset_source_types", []),
        all_models=[ModelRunResult(**run) for run in metrics.get("all_models", [])],
        selection_rule=hyper.get("selection_rule", ""),
        split_strategy=hyper.get("split_strategy", ""),
        warnings=metrics.get("warnings", []),
        notice=training_service.notice_for(record),
    )


@router.get(
    "/status",
    response_model=ModelStatusResponse,
    summary="Whether a trained model exists, and which one is active",
)
def model_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ModelStatusResponse:
    record = training_service.active_model(db)
    history = [_summary(run) for run in training_service.training_history(db)]

    if record is None:
        return ModelStatusResponse(
            trained=False,
            xgboost_available=XGBOOST_AVAILABLE,
            available_models=AVAILABLE_MODELS,
            history=history,
        )

    hyper = _hyper(record)
    metrics = _metrics(record)

    return ModelStatusResponse(
        trained=True,
        active_model=record.algorithm,
        version=record.model_version,
        model_name=record.model_name,
        target=hyper.get("target"),
        trained_at=record.trained_at,
        dataset_id=hyper.get("dataset_id"),
        dataset_source_types=hyper.get("dataset_source_types", []),
        primary_metric="f1_weighted",
        primary_metric_value=record.f1_score,
        majority_baseline=metrics.get("majority_baseline"),
        status=record.status,
        feature_count=len(record.feature_names or []),
        xgboost_available=XGBOOST_AVAILABLE,
        available_models=AVAILABLE_MODELS,
        history=history,
        notice=training_service.notice_for(record),
    )


@router.get(
    "/metrics",
    response_model=ModelMetricsResponse,
    summary="Measured evaluation results for the active model",
)
def model_metrics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ModelMetricsResponse:
    record = training_service.active_model(db)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "not_trained",
                "reason": "No model has been trained yet.",
            },
        )

    hyper = _hyper(record)
    metrics = _metrics(record)

    return ModelMetricsResponse(
        model_version=record.model_version,
        selected_model=record.algorithm,
        target=hyper.get("target", ""),
        trained_at=record.trained_at,
        metrics={
            key: value
            for key, value in metrics.items()
            if isinstance(value, (int, float))
        },
        majority_baseline=metrics.get("majority_baseline"),
        confusion_matrix=metrics.get("confusion_matrix", []),
        confusion_labels=metrics.get("confusion_labels", []),
        class_distribution=metrics.get("class_distribution", {}),
        feature_count=len(record.feature_names or []),
        feature_names=record.feature_names or [],
        excluded_columns=metrics.get("excluded_columns", {}),
        training_rows=hyper.get("training_rows", 0),
        validation_rows=hyper.get("validation_rows", 0),
        split_strategy=hyper.get("split_strategy"),
        selection_rule=hyper.get("selection_rule"),
        dataset_id=hyper.get("dataset_id"),
        dataset_source_types=hyper.get("dataset_source_types", []),
        all_models=[ModelRunResult(**run) for run in metrics.get("all_models", [])],
        warnings=metrics.get("warnings", []),
        notice=training_service.notice_for(record),
    )
