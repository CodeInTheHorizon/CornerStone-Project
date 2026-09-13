"""Inference against saved Phase 5 observations using the active Phase 6 Pipeline.

No training, fitting, feature synthesis, fuzzy product matching, or fallback
models occur here. Missing optional observations remain NaN for the saved
imputer; absent required columns are a compatibility error.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml import opportunity
from app.ml.normalization import CATEGORY_ALIASES
from app.ml.target import CLASSES, TARGET_COLUMN
from app.models import ModelMetadata, Prediction
from app.models.enums import Platform, SourceType
from app.schemas.prediction import (
    ModelQuality, PlatformPrediction, PredictRequest, PredictionHistory,
    PredictionHistoryItem, PredictionResponse,
)
from app.services import dataset_service, training_service

logger = logging.getLogger(__name__)
STALE_AFTER_DAYS = 7
ELECTRONICS_CATEGORIES = set(CATEGORY_ALIASES.values())
CATEGORICAL = {"platform", "source_type", "category_normalized", "brand_normalized"}
REQUIRED_CONTEXT = {"product_key", "product_name", "platform", "source_type", "category_normalized", "collection_timestamp", "effective_price", "currency"}


class PredictionError(Exception):
    def __init__(self, status: str, reason: str, http_status: int = 422, **context):
        super().__init__(reason)
        self.detail = {"status": status, "reason": reason, **context}
        self.http_status = http_status


def quality(record: ModelMetadata) -> ModelQuality:
    baseline = opportunity.number((record.metrics or {}).get("majority_baseline"))
    accuracy = opportunity.number(record.accuracy)
    below = None if baseline is None or accuracy is None else accuracy <= baseline
    sources = training_service.source_types_for(record)
    warning = "Experimental result: "
    warning += "the current model is trained on DEMO data" if "demo" in sources else "this model predicts a price-direction proxy"
    if below:
        warning += " and does not outperform the validation baseline"
    elif below is None:
        warning += "; a complete accuracy/baseline comparison is unavailable"
    warning += ". Use this prediction only to demonstrate the pipeline. It does not predict actual sales demand."
    return ModelQuality(
        version=record.model_version, type=record.algorithm,
        target=(record.hyperparameters or {}).get("target", ""),
        primary_metric_value=record.f1_score, accuracy=accuracy,
        majority_baseline=baseline, below_baseline=below,
        source_types=sources, warning=warning,
    )


def load_active(db: Session) -> tuple[ModelMetadata, Pipeline]:
    record = training_service.active_model(db)
    if record is None or record.status != "completed":
        raise PredictionError("not_trained", "No completed active model. Train a model first.", 409)
    try:
        pipeline = training_service.load_pipeline(record)
    except Exception:
        logger.exception("Could not load active model %s", record.model_version)
        raise PredictionError("corrupt_artifact", "The active model artifact cannot be loaded. Restore a matching artifact or train explicitly.", 503) from None
    if pipeline is None:
        raise PredictionError("missing_artifact", "The active model artifact is missing. Restore it or train explicitly.", 503)
    expected = record.feature_names or []
    actual = list(getattr(pipeline, "feature_names_in_", []))
    algorithm = {"xgboost": "XGBClassifier", "random_forest": "RandomForestClassifier"}.get(record.algorithm)
    if (not isinstance(pipeline, Pipeline) or not expected or actual != expected
            or not algorithm or type(pipeline.named_steps.get("model")).__name__ != algorithm
            or (record.hyperparameters or {}).get("target") != TARGET_COLUMN):
        raise PredictionError("incompatible_features", "Active model metadata and saved pipeline are incompatible.", 409)
    return record, pipeline


def dataset(dataset_id: str | None = None) -> tuple[dict, pd.DataFrame]:
    metadata = next((m for m in dataset_service.list_datasets() if m.get("dataset_id") == dataset_id), None) if dataset_id else dataset_service.latest_dataset()
    if metadata is None:
        raise PredictionError("missing_dataset", "No matching processed dataset. Build one on Train Model first.")
    try:
        frame = dataset_service.load_dataset_frame(metadata["dataset_id"])
    except Exception:
        raise PredictionError("invalid_dataset", "The processed dataset cannot be read. Build a new dataset.") from None
    if frame is None or frame.empty:
        raise PredictionError("missing_dataset", "The processed dataset file is missing or empty. Build a new dataset.")
    missing = REQUIRED_CONTEXT - set(frame.columns)
    if missing:
        raise PredictionError("incompatible_features", "Dataset is missing context columns: " + ", ".join(sorted(missing)))
    frame = frame.copy()
    frame["collection_timestamp"] = pd.to_datetime(frame["collection_timestamp"], errors="coerce", utc=True)
    return metadata, frame


def latest_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values("collection_timestamp", na_position="first", kind="stable").drop_duplicates(["product_key", "platform"], keep="last")


def freshness(value) -> tuple[str | None, bool]:
    if pd.isna(value):
        return None, False
    age = (datetime.now(timezone.utc) - value.to_pydatetime()).total_seconds() / 86400
    return value.isoformat(), age > STALE_AFTER_DAYS


def options(query: str = "", limit: int = 50, offset: int = 0) -> dict:
    """Search exact dataset product identities; preview latest available observations."""
    metadata, frame = dataset()
    frame = frame[frame["category_normalized"].isin(ELECTRONICS_CATEGORIES)]
    if query:
        frame = frame[frame["product_key"].str.contains(query.strip(), case=False, regex=False, na=False)]
    rows = latest_rows(frame)
    keys = sorted(rows["product_key"].dropna().unique())
    products = []
    for key in keys[offset:offset + limit]:
        product = rows[rows["product_key"] == key]
        contexts = []
        for _, row in product.sort_values("platform").iterrows():
            timestamp, stale = freshness(row["collection_timestamp"])
            contexts.append({
                "platform": row["platform"], "source_type": row["source_type"],
                "data_freshness": timestamp, "stale": stale,
                "effective_price": opportunity.number(row["effective_price"]),
                "currency": row["currency"], "rating": opportunity.number(row.get("rating")),
                "review_count": opportunity.number(row.get("review_count")),
            })
        first = product.iloc[0]
        products.append({"product_key": key, "product_name": first["product_name"], "category": first["category_normalized"], "platforms": contexts})
    return {"dataset_id": metadata["dataset_id"], "generated_at": metadata.get("generated_at"), "source_types": metadata.get("source_types", []), "total": len(keys), "products": products}


def feature_frame(row: pd.Series, names: list[str]) -> pd.DataFrame:
    if set(names) - set(row.index):
        raise PredictionError("incompatible_features", "Dataset does not contain every saved model feature. Rebuild a compatible dataset.")
    values = {}
    for name in names:
        value = row[name]
        if pd.isna(value):
            values[name] = np.nan
        elif name in CATEGORICAL:
            values[name] = str(value)
        else:
            numeric = opportunity.number(value)
            if numeric is None:
                raise PredictionError("incompatible_features", f"Invalid numeric model feature: {name}.")
            values[name] = numeric
    return pd.DataFrame([values], columns=names)


def infer(pipeline: Pipeline, frame: pd.DataFrame, algorithm: str) -> tuple[str, dict | None, float | None]:
    """Decode each estimator's own class order, never assume probability order."""
    def decode(value) -> str:
        if algorithm == "xgboost":
            index = int(value)
            if float(value) != index or index < 0 or index >= len(CLASSES):
                raise ValueError("Unknown class ID")
            return CLASSES[index]
        if str(value) not in CLASSES:
            raise ValueError("Unknown class label")
        return str(value)

    predicted = decode(pipeline.predict(frame)[0])
    probabilities = None
    confidence = None
    if hasattr(pipeline, "predict_proba"):
        values = np.asarray(pipeline.predict_proba(frame)[0], dtype=float)
        labels = [decode(value) for value in pipeline.classes_]
        if (len(labels) != len(values) or len(set(labels)) != len(labels)
                or not np.isfinite(values).all() or (values < 0).any()
                or (values > 1).any() or not np.isclose(values.sum(), 1, atol=1e-5)):
            raise ValueError("Invalid class probabilities")
        probabilities = {label: float(value) for label, value in zip(labels, values, strict=True)}
        confidence = probabilities[predicted]
    return predicted, probabilities, confidence


def validate_row(row: pd.Series) -> None:
    if pd.isna(row["collection_timestamp"]):
        raise PredictionError("insufficient_data", "Observation timestamp is missing or invalid.")
    if row["collection_timestamp"] > pd.Timestamp.now(tz="UTC") + pd.Timedelta(minutes=5):
        raise PredictionError("insufficient_data", "Observation timestamp is in the future.")
    if row["source_type"] not in {s.value for s in SourceType}:
        raise PredictionError("insufficient_data", "Observation provenance is unknown.")
    if row["currency"] != "INR":
        raise PredictionError("insufficient_data", "Phase 7 supports INR observations; currencies are not converted.")
    price = opportunity.number(row["effective_price"])
    if price is None or price <= 0:
        raise PredictionError("insufficient_data", "A positive observed price is required.")
    for name, upper in [("rating", 5), ("discount_percentage", 100), ("competition_score", 100), ("review_count", float("inf"))]:
        value = opportunity.number(row.get(name))
        if value is not None and not 0 <= value <= upper:
            raise PredictionError("insufficient_data", f"Observed {name} is outside its valid range.")
    signals = opportunity.score(row, None)["normalized_signals"]
    count = sum(value is not None for key, value in signals.items() if key != "model_signal")
    coverage = sum(opportunity.WEIGHTS[key] for key, value in signals.items() if value is not None and key != "model_signal")
    if count < 3 or coverage < 40:
        raise PredictionError("insufficient_data", "Need at least three observed score components covering 40 deterministic points.")


def predict(db: Session, user_id: int, payload: PredictRequest) -> PredictionResponse:
    record, pipeline = load_active(db)
    model = quality(record)
    metadata, frame = dataset(payload.dataset_id)
    product = frame[frame["product_key"] == payload.product_key]
    if product.empty:
        raise PredictionError("insufficient_data", "This exact product is absent from the selected dataset.", model=model.model_dump())
    if not product["category_normalized"].isin(ELECTRONICS_CATEGORIES).all():
        raise PredictionError("unsupported_category", "Choose a supported electronics/accessory category from the product list.")
    rows = latest_rows(product)
    results = []
    for platform in sorted(set(p.value for p in payload.platforms)):
        matches = rows[rows["platform"] == platform]
        result = PlatformPrediction(platform=platform, status="insufficient_data", model_version=record.model_version, warning=model.warning)
        if matches.empty:
            result.reason = "No observation for this exact product on this platform in the selected dataset."
        else:
            row = matches.iloc[0]
            timestamp, stale = freshness(row["collection_timestamp"])
            result.source_type = str(row["source_type"]) if pd.notna(row["source_type"]) else None
            result.data_freshness = datetime.fromisoformat(timestamp) if timestamp else None
            result.stale = stale
            try:
                validate_row(row)
                features = feature_frame(row, record.feature_names)
                predicted, probabilities, confidence = infer(pipeline, features, record.algorithm)
                scored = opportunity.score(row, probabilities)
                factors = sorted(scored["components"], key=lambda k: (-scored["components"][k], k))
                factors = [key for key in factors if scored["normalized_signals"][key] is not None][:3]
                result = PlatformPrediction(
                    platform=platform, status="success", predicted_class=predicted,
                    probabilities=probabilities, confidence=confidence,
                    model_version=record.model_version, source_type=str(row["source_type"]),
                    data_freshness=timestamp, stale=stale, warning=model.warning,
                    key_factors=factors, **scored,
                )
                if stale:
                    result.warning += f" Observation is older than {STALE_AFTER_DAYS} days; refresh and rebuild the dataset."
                if scored["missing_components"]:
                    result.warning += " Some score components are missing and contribute no points; compare coverage before interpreting the ranking."
                if probabilities is None:
                    result.warning += " This pipeline does not expose class probabilities; confidence is unavailable."
            except PredictionError as exc:
                result.status = exc.detail["status"]
                result.reason = exc.detail["reason"]
            except Exception:
                logger.exception("Inference failed on %s using %s", platform, record.model_version)
                result.status = "prediction_failed"
                result.reason = "The saved pipeline could not evaluate this observation. No fallback result was generated."
        results.append(result)
    ranking = sorted([r for r in results if r.status == "success"], key=lambda r: (-r.opportunity_score, r.platform))
    if not ranking:
        raise PredictionError("no_predictions", "No platform could be evaluated.", platform_results=[r.model_dump(mode="json") for r in results], model=model.model_dump())
    top = ranking[0]
    warning = model.warning
    if any(r.stale for r in ranking):
        warning += f" Some observations are older than {STALE_AFTER_DAYS} days."
    if len(ranking) == 1:
        warning += " Only one platform has sufficient data; no cross-platform comparison is possible."
    if len({r.coverage_weight for r in ranking}) > 1:
        warning += " Platforms have unequal signal coverage; missing signals lower scores."
    difference = round(top.opportunity_score - ranking[1].opportunity_score, 1) if len(ranking) > 1 else None
    if difference == 0:
        warning += " Top scores are tied; platform name determines display order, not superiority."
    source_types = sorted(set(product["source_type"].dropna()) | set(metadata.get("source_types", [])))
    # Dataset-wide provenance matters: market-context features include peers.
    if "demo" in source_types and "demo" not in model.source_types:
        warning += " Input features contain DEMO-derived data."
    response = PredictionResponse(
        id=0, product=str(product.iloc[0]["product_name"]), product_key=payload.product_key,
        created_at=datetime.now(timezone.utc), recommended_platform=top.platform,
        ranking=ranking, platform_results=results, score_difference=difference,
        key_factors=top.key_factors, model=model, warning=warning,
        data_provenance={"dataset_id": metadata["dataset_id"], "dataset_generated_at": metadata.get("generated_at"), "source_types": source_types, "model_source_types": model.source_types, "observations_used": len(product), "stale_after_days": STALE_AFTER_DAYS},
        formula={"version": opportunity.FORMULA_VERSION, "weights": opportunity.WEIGHTS, "explanations": opportunity.EXPLANATIONS, "missing_policy": "No points for missing components; fixed weights, no reweighting. Compare coverage as well as score."},
    )
    stored = Prediction(
        user_id=user_id, model_metadata_id=record.id, product_name=response.product,
        brand=str(product.iloc[0].get("brand_normalized", "")), category=str(product.iloc[0]["category_normalized"]),
        input_payload=payload.model_dump(mode="json"), recommended_platform=top.platform,
        confidence=top.confidence, opportunity_scores={r.platform: r.opportunity_score for r in ranking},
        key_factors=top.key_factors, model_version=record.model_version,
        snapshots_used=len(product), created_at=response.created_at,
    )
    try:
        db.add(stored)
        db.flush()
        response.id = stored.id
        stored.result_payload = response.model_dump(mode="json")
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist prediction")
        raise PredictionError("persistence_failed", "Prediction could not be saved. Please retry.", 500) from None
    return response


def history(db: Session, user_id: int, limit: int = 20, offset: int = 0) -> PredictionHistory:
    scope = Prediction.user_id == user_id
    total = db.scalar(select(func.count()).select_from(Prediction).where(scope)) or 0
    records = db.scalars(select(Prediction).where(scope).order_by(Prediction.created_at.desc(), Prediction.id.desc()).limit(limit).offset(offset)).all()
    items = []
    for record in records:
        saved = record.result_payload or {}
        items.append(PredictionHistoryItem(
            id=record.id, product=record.product_name, recommended_platform=record.recommended_platform,
            top_score=(record.opportunity_scores or {}).get(record.recommended_platform),
            model_version=record.model_version, source_types=saved.get("data_provenance", {}).get("source_types", []),
            created_at=record.created_at, model=saved.get("model"),
            warning=saved.get("warning", "Historical result has no preserved model-quality metadata. Do not use it for marketplace decisions."),
        ))
    return PredictionHistory(total=total, items=items)


def detail(db: Session, user_id: int, prediction_id: int) -> PredictionResponse:
    record = db.scalar(select(Prediction).where(Prediction.id == prediction_id, Prediction.user_id == user_id))
    if record is None:
        raise PredictionError("not_found", "Prediction not found.", 404)
    if not record.result_payload:
        raise PredictionError("legacy_result", "This historical prediction has no preserved result details.", 409)
    return PredictionResponse.model_validate(record.result_payload)
