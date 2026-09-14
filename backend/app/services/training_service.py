"""Orchestrates a training run: dataset -> target -> train -> persist.

Artifacts are versioned (`model_v1.pkl`, `model_v2.pkl`, ...) and never
overwritten. An older artifact may be the one a stored prediction was made
with, and silently replacing it would break that link.

Every run is recorded in ModelMetadata, including which source types the
dataset came from -- so a model trained only on the synthetic fixture stays
identifiable as such wherever it is reported.
"""

from __future__ import annotations

import logging
from threading import Lock
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.ml import provenance
from app.ml import validation as validation_module
from app.ml.training import TrainingError, TrainingOutcome, train_models
from app.models import ModelMetadata
from app.models.enums import SourceType, TrainingStatus
from app.services import dataset_service
from app.storage.artifact_store import ArtifactStore
from app.storage.base import StorageError

logger = logging.getLogger(__name__)

ARTIFACT_DIR = settings.MODEL_ARTIFACT_DIR
_TRAINING_LOCK = Lock()
MODEL_NAME = "marketpulse-opportunity-classifier"

DEMO_TRAINING_NOTICE = (
    "Model trained on DEMO data for development/testing."
)

#: Marks records trained with the Phase 12 boundary-first split and quality gate.
TRAINING_POLICY_VERSION = "phase12-v1"


def _next_version(db: Session) -> str:
    """v1, v2, ... based on how many runs have been recorded."""
    existing = db.execute(select(ModelMetadata.model_version)).scalars().all()
    numbers = [
        int(version[1:])
        for version in existing
        if isinstance(version, str) and version.startswith("v") and version[1:].isdigit()
    ]
    for key in ArtifactStore(ARTIFACT_DIR).keys():
        suffix = key.split(".")[0].removeprefix("model_v")
        if suffix.isdigit():
            numbers.append(int(suffix))
    return f"v{max(numbers, default=0) + 1}"


def _notice(source_types: list[str]) -> str | None:
    return DEMO_TRAINING_NOTICE if SourceType.DEMO.value in source_types else None


def train(
    db: Session,
    *,
    dataset_id: str | None = None,
    models: list[str] | None = None,
    source_types: list[str] | None = None,
    development_override: bool = False,
) -> ModelMetadata:
    if not _TRAINING_LOCK.acquire(blocking=False):
        raise TrainingError("A training run is already in progress. Wait for it to finish.", status="training_busy")
    try:
        return _train(
            db, dataset_id=dataset_id, models=models,
            source_types=source_types, development_override=development_override,
        )
    except StorageError:
        db.rollback()
        raise
    except TrainingError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Training failed: %s", type(exc).__name__)
        raise TrainingError("Training could not be completed. Check dataset and artifact storage, then retry.", status="training_failed") from None
    finally:
        _TRAINING_LOCK.release()


def _train(
    db: Session,
    *,
    dataset_id: str | None = None,
    models: list[str] | None = None,
    source_types: list[str] | None = None,
    development_override: bool = False,
) -> ModelMetadata:
    """Run training against a stored dataset and record the result.

    Raises TrainingError with a machine-readable `status` so the API can
    distinguish "no dataset" from "provenance rejected" from "one class" from
    "training crashed".
    """
    metadata = (
        next(
            (d for d in dataset_service.list_datasets() if d["dataset_id"] == dataset_id),
            None,
        )
        if dataset_id and dataset_id != "latest"
        else dataset_service.latest_dataset()
    )

    if metadata is None:
        raise TrainingError(
            "No processed dataset is available. Build one on the Train Model "
            "page first.",
            status="no_dataset",
        )

    # Provenance first: never read or fit a dataset the caller did not accept.
    try:
        policy = provenance.resolve(
            source_types,
            metadata.get("source_types", []),
            development_override=development_override,
            is_development=settings.is_development,
        )
    except provenance.ProvenanceError as exc:
        raise TrainingError(str(exc), status="provenance_rejected") from None

    frame = dataset_service.load_dataset_frame(metadata["dataset_id"])
    if frame is None or frame.empty:
        raise TrainingError(
            f"Dataset {metadata['dataset_id']} could not be read from storage.",
            status="no_dataset",
        )
    actual = sorted(frame["source_type"].dropna().astype(str).str.lower().unique()) if "source_type" in frame else []
    if set(actual) - set(policy.selected):
        raise TrainingError(
            "The dataset file contains source types its metadata does not declare. Rebuild the dataset.",
            status="provenance_rejected",
        )

    # Labels are generated inside train_models, per split partition, so no
    # training label can come from a validation-period observation.
    outcome = train_models(frame, models)

    quality_status, quality_reasons = validation_module.quality_gate(
        accuracy=outcome.selected.metrics.get("accuracy"),
        baseline_report=outcome.baselines,
        source_types=policy.dataset_source_types,
        validation_rows=outcome.validation_rows,
        validation_dates=outcome.data_summary.get("validation_label_dates", 0),
        probability_report=outcome.probability_quality,
        development_override=policy.development_override,
    )

    version = _next_version(db)
    artifact_path, storage_info = _persist_artifact(
        outcome, version, metadata, policy, quality_status, quality_reasons
    )

    record = _record_metadata(
        db, outcome, version, metadata, artifact_path, storage_info, policy, quality_status, quality_reasons
    )
    return record


def _evaluation_evidence(
    outcome: TrainingOutcome,
    policy: provenance.ProvenancePolicy,
    quality_status: str,
    quality_reasons: list[str],
) -> dict[str, Any]:
    """Phase 12 evidence stored with every new model (sidecar and metadata)."""
    return {
        "training_policy_version": TRAINING_POLICY_VERSION,
        "source_policy": policy.to_dict(),
        "quality_status": quality_status,
        "quality_reasons": quality_reasons,
        "calibration_status": outcome.probability_quality.get("calibration_status", "unavailable"),
        "probability_quality": outcome.probability_quality,
        "baselines": outcome.baselines,
        "split": outcome.split,
        "data_summary": outcome.data_summary,
        "group_overlap": outcome.group_overlap,
        "unseen_product_accuracy": outcome.unseen_product_accuracy,
        "training_requirements": outcome.requirements,
        "training_class_distribution": outcome.training_class_distribution,
        "validation_class_distribution": outcome.validation_class_distribution,
    }


def _persist_artifact(
    outcome: TrainingOutcome,
    version: str,
    dataset_meta: dict[str, Any],
    policy: provenance.ProvenancePolicy,
    quality_status: str,
    quality_reasons: list[str],
) -> tuple[str, dict]:
    """Publish the fitted pipeline and its metadata through configured storage."""
    sidecar = {
        **_evaluation_evidence(outcome, policy, quality_status, quality_reasons),
        "model_version": version,
        "model_name": MODEL_NAME,
        "model_type": outcome.selected.name,
        "target": outcome.target,
        "target_definition": (
            "Direction of the next observed price for the same listing: "
            "improving / stable / declining, at a +/-1% threshold. A proxy for "
            "near-term margin direction, NOT a measure of sales demand."
        ),
        "dataset_id": dataset_meta["dataset_id"],
        "dataset_source_types": dataset_meta.get("source_types", []),
        "dataset_platforms": dataset_meta.get("platforms", []),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": outcome.training_rows,
        "validation_rows": outcome.validation_rows,
        "split_strategy": outcome.split_strategy,
        "split_rationale": outcome.split_rationale,
        "selection_rule": outcome.selection_rule,
        "feature_names": outcome.feature_names,
        "numeric_features": outcome.numeric_features,
        "categorical_features": outcome.categorical_features,
        "excluded_columns": outcome.excluded_columns,
        "class_distribution": outcome.class_distribution,
        "majority_baseline": outcome.majority_baseline,
        "metrics": outcome.selected.metrics,
        "confusion_matrix": outcome.selected.confusion_matrix,
        "confusion_labels": outcome.selected.labels,
        "all_model_results": [
            {"model": r.name, "metrics": r.metrics, "error": r.error}
            for r in outcome.results
        ],
        "warnings": outcome.warnings,
        "notice": _notice(dataset_meta.get("source_types", [])),
    }
    location, info = ArtifactStore(ARTIFACT_DIR).save(outcome.selected.pipeline, version, sidecar)
    logger.info("Saved model %s (%s)", version, outcome.selected.name)
    return location, info


def _record_metadata(
    db: Session,
    outcome: TrainingOutcome,
    version: str,
    dataset_meta: dict[str, Any],
    artifact_path: str,
    storage_info: dict,
    policy: provenance.ProvenancePolicy,
    quality_status: str,
    quality_reasons: list[str],
) -> ModelMetadata:
    """Persist the run and make it the active model."""
    evidence = _evaluation_evidence(outcome, policy, quality_status, quality_reasons)
    # Exactly one active model at a time.
    for previous in db.execute(
        select(ModelMetadata).where(ModelMetadata.is_active.is_(True))
    ).scalars():
        previous.is_active = False

    metrics = dict(outcome.selected.metrics)
    record = ModelMetadata(
        model_name=MODEL_NAME,
        model_version=version,
        algorithm=outcome.selected.name,
        status=TrainingStatus.COMPLETED.value,
        dataset_rows=outcome.training_rows + outcome.validation_rows,
        feature_names=outcome.feature_names,
        hyperparameters={
            "artifact_storage": storage_info,
            "split_strategy": outcome.split_strategy,
            "training_rows": outcome.training_rows,
            "validation_rows": outcome.validation_rows,
            "target": outcome.target,
            "dataset_id": dataset_meta["dataset_id"],
            "dataset_source_types": dataset_meta.get("source_types", []),
            "dataset_platforms": dataset_meta.get("platforms", []),
            "selection_rule": outcome.selection_rule,
            "training_policy_version": TRAINING_POLICY_VERSION,
            "source_policy": evidence["source_policy"],
            "split": evidence["split"],
            "data_summary": evidence["data_summary"],
            "training_requirements": evidence["training_requirements"],
        },
        accuracy=metrics.get("accuracy"),
        f1_score=metrics.get("f1_weighted"),
        metrics={
            **metrics,
            "majority_baseline": outcome.majority_baseline,
            "confusion_matrix": outcome.selected.confusion_matrix,
            "confusion_labels": outcome.selected.labels,
            "class_distribution": outcome.class_distribution,
            "all_models": [
                {"model": r.name, "metrics": r.metrics, "error": r.error}
                for r in outcome.results
            ],
            "warnings": outcome.warnings,
            "excluded_columns": outcome.excluded_columns,
            "baselines": evidence["baselines"],
            "probability_quality": evidence["probability_quality"],
            "quality_reasons": quality_reasons,
            "group_overlap": evidence["group_overlap"],
            "unseen_product_accuracy": evidence["unseen_product_accuracy"],
            "training_class_distribution": evidence["training_class_distribution"],
            "validation_class_distribution": evidence["validation_class_distribution"],
        },
        quality_status=quality_status,
        calibration_status=evidence["calibration_status"],
        artifact_path=str(artifact_path),
        is_active=True,
        trained_at=datetime.now(timezone.utc),
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def active_model(db: Session) -> ModelMetadata | None:
    return db.execute(
        select(ModelMetadata).where(ModelMetadata.is_active.is_(True))
    ).scalars().first()


def training_history(db: Session, limit: int = 20) -> list[ModelMetadata]:
    return list(
        db.execute(
            select(ModelMetadata)
            .order_by(ModelMetadata.trained_at.desc(), ModelMetadata.id.desc())
            .limit(limit)
        ).scalars()
    )


def load_pipeline(record: ModelMetadata) -> Any | None:
    """Load a stored pipeline, or None when the artifact is gone."""
    return ArtifactStore(ARTIFACT_DIR).load(record)


def source_types_for(record: ModelMetadata) -> list[str]:
    return list((record.hyperparameters or {}).get("dataset_source_types", []))


def notice_for(record: ModelMetadata) -> str | None:
    return _notice(source_types_for(record))


def quality_report(record: ModelMetadata) -> dict[str, Any]:
    """Quality evidence for any model record, including pre-Phase 12 ones.

    Records trained before Phase 12 have no stored gate. They are interpreted
    conservatively and never rewritten: their labels were generated before the
    split (boundary leakage was not purged), so they can be at best
    experimental, and their probabilities were never measured.
    """
    hyper = record.hyperparameters or {}
    metrics = record.metrics or {}
    sources = source_types_for(record)
    legacy = hyper.get("training_policy_version") is None

    if legacy:
        baseline = metrics.get("majority_baseline")
        status, reasons = validation_module.quality_gate(
            accuracy=record.accuracy,
            baseline_report={"majority_baseline": baseline, "best_baseline_accuracy": baseline},
            source_types=sources,
            validation_rows=int(hyper.get("validation_rows") or 0),
            validation_dates=0,
            probability_report={"assessment": "not_measured"},
            leakage_safe_split=False,
        )
        if status != "below_baseline":
            status = "experimental"
        reasons = [*reasons, "Trained before Phase 12: labels were generated before the time split, so boundary-crossing labels were not purged."]
        return {
            "quality_status": status,
            "quality_reasons": list(dict.fromkeys(reasons)),
            "calibration_status": "uncalibrated",
            "probability_quality": {"available": False, "calibration_status": "uncalibrated", "assessment": "not_measured"},
            "baselines": {"majority_baseline": baseline, "metric": "accuracy"},
            "split": {"strategy": "legacy time-aware (labels generated before splitting)", "description": hyper.get("split_strategy"), "leakage_safeguards": []},
            "data_summary": {"training_rows": hyper.get("training_rows"), "validation_rows": hyper.get("validation_rows"), "labelled_rows": record.dataset_rows},
            "source_policy": {"selected_source_types": sources, "dataset_source_types": sources, "profile": "legacy_unrecorded", "development_override": False, "uses_demo": "demo" in sources},
            "group_overlap": {},
            "unseen_product_accuracy": None,
            "legacy": True,
            "leakage_safe_split": False,
        }

    return {
        "quality_status": record.quality_status or "experimental",
        "quality_reasons": metrics.get("quality_reasons", []),
        "calibration_status": record.calibration_status or "uncalibrated",
        "probability_quality": metrics.get("probability_quality", {}),
        "baselines": metrics.get("baselines", {"majority_baseline": metrics.get("majority_baseline"), "metric": "accuracy"}),
        "split": hyper.get("split", {}),
        "data_summary": hyper.get("data_summary", {}),
        "source_policy": hyper.get("source_policy", {}),
        "group_overlap": metrics.get("group_overlap", {}),
        "unseen_product_accuracy": metrics.get("unseen_product_accuracy"),
        "legacy": False,
        "leakage_safe_split": True,
    }


__all__ = [
    "DEMO_TRAINING_NOTICE",
    "TrainingError",
    "active_model",
    "load_pipeline",
    "notice_for",
    "quality_report",
    "source_types_for",
    "train",
    "training_history",
]
