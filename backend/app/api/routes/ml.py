import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.permissions import Permission
from app.auth.rate_limits import operation
from app.database import get_db
from app.ml.training import XGBOOST_AVAILABLE, TrainingError
from app.models import ModelMetadata, User
from app.schemas.training import (
    AVAILABLE_MODELS,
    ModelMetricsResponse,
    ModelRunResult,
    ModelStatusResponse,
    QualityReport,
    TrainingRunSummary,
    TrainRequest,
    TrainResponse,
)
from app.services import training_service, training_state

router = APIRouter(prefix="/ml", tags=["ml"])

#: Statuses that mean "the request was fine, the data was not".
DATA_STATUSES = {"no_dataset", "insufficient_data", "missing_target", "missing_features", "no_models", "provenance_rejected"}


def _hyper(record: ModelMetadata) -> dict[str, Any]:
    return record.hyperparameters or {}


def _metrics(record: ModelMetadata) -> dict[str, Any]:
    return record.metrics or {}


def _quality(record: ModelMetadata) -> QualityReport:
    return QualityReport(**training_service.quality_report(record))


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
        quality_status=training_service.quality_report(record)["quality_status"],
    )


@router.post(
    "/train",
    response_model=TrainResponse,
    summary="Train, evaluate and persist a model",
)
def train(
    payload: TrainRequest,
    db: Session = Depends(get_db),
    user: User = Depends(operation(Permission.TRAIN, "train")),
) -> TrainResponse:
    try:
        record = training_service.train(
            db,
            dataset_id=payload.dataset_id,
            models=payload.models,
            source_types=payload.source_types,
            development_override=payload.development_override,
        )
    except TrainingError as exc:
        # 422 when the data was inadequate, 500 when training itself broke.
        code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if exc.status in DATA_STATUSES
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        if exc.status == "training_busy":
            code = status.HTTP_409_CONFLICT
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
        quality=_quality(record),
    )


@router.post("/train-async", summary="Start training in background")
async def train_async(
    payload: TrainRequest,
    db: Session = Depends(get_db),
    user: User = Depends(operation(Permission.TRAIN, "train")),
):
    training_id = uuid.uuid4().hex[:12]
    training_state.start(training_id)

    async def _run():
        try:
            record = await asyncio.to_thread(
                training_service.train,
                db,
                dataset_id=payload.dataset_id,
                models=payload.models,
                source_types=payload.source_types,
                development_override=payload.development_override,
            )
            training_state.finish(training_id, result={"model_version": record.model_version, "algorithm": record.algorithm})
        except TrainingError as exc:
            training_state.finish(training_id, error=exc.reason)
        except Exception as exc:
            training_state.finish(training_id, error=str(exc))

    asyncio.create_task(_run())
    return {"training_id": training_id, "status": "started"}


@router.get("/training-status", summary="Poll background training status")
def get_training_status(training_id: str, _: User = Depends(get_current_user)):
    state = training_state.get(training_id)
    if not state:
        raise HTTPException(404, "Training ID not found")
    return state


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
        quality=_quality(record),
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
        quality=_quality(record),
    )
