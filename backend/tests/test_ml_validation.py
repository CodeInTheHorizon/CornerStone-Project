"""Phase 12: leakage-safe labels, provenance policy, quality gate, probabilities.

No provider, no LIVE data, no development artifacts: synthetic frames in memory
and isolated temporary storage only.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml import provenance, validation
from app.ml import target as target_module
from app.ml.target import CLASSES, TARGET_COLUMN
from app.ml.training import TrainingError, TrainingRequirements, train_models
from app.models import ModelMetadata
from app.schemas.prediction import PredictionResponse
from app.services import dataset_service, prediction_service, training_service

from tests.test_prediction import post, prepared, ready  # noqa: F401  (fixtures)
from tests.test_training import auth_headers, build_dataset_via_api, clean_models, clean_snapshots  # noqa: F401

BASE = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


def frame_of(listings=30, days=6, seed=3, source="live", step=None):
    """Processed-dataset-shaped rows with a random price walk per listing."""
    rng = np.random.default_rng(seed)
    rows = []
    for listing in range(listings):
        price = float(rng.integers(500, 5000))
        for day in range(days):
            if day:
                price = step(price, listing, day) if step else max(50.0, price * (1 + rng.uniform(-0.05, 0.05)))
            rows.append({
                "snapshot_id": len(rows) + 1,
                "platform": ["amazon", "flipkart", "croma", "alibaba"][listing % 4],
                "source_type": source,
                "product_key": f"product-{listing}|acme|earbuds",
                "product_name": f"Product {listing}",
                "brand_normalized": "acme",
                "category_normalized": "wireless earbuds",
                "external_id": f"X{listing}",
                "currency": "INR",
                "collection_timestamp": BASE + timedelta(days=day),
                "effective_price": round(price, 2),
                "price_change_percentage": np.nan,
                "rating": float(rng.uniform(3, 5)),
                "review_count": int(rng.integers(10, 900)),
            })
    frame = pd.DataFrame(rows).sort_values(["platform", "product_key", "collection_timestamp"])
    previous = frame.groupby(["platform", "product_key"])["effective_price"].shift(1)
    frame["price_change_percentage"] = (frame["effective_price"] - previous) / previous * 100
    return frame.reset_index(drop=True)


# --------------------------------------------------------------------------
# 1. Forward-label split-boundary leakage
# --------------------------------------------------------------------------


def test_global_labelling_would_cross_the_boundary():
    """Regression guard: the pre-Phase 12 approach really did leak."""
    frame = frame_of(listings=12, days=5)
    split = validation.temporal_split(frame)
    globally = target_module.labelled_rows(target_module.add_target(frame))
    crossing = globally[(globally["collection_timestamp"] < split.boundary) & (globally["target_observed_at"] >= split.boundary)]
    assert len(crossing) == 12  # one per listing: the last training-period row
    assert split.boundary_purged_rows == 12


def test_no_training_label_uses_validation_period_observations():
    split = validation.temporal_split(frame_of(listings=20, days=6))
    assert split.train["collection_timestamp"].max() < split.boundary
    assert split.train["target_observed_at"].notna().all()
    assert split.train["target_observed_at"].max() < split.boundary


def test_validation_labels_stay_inside_the_evaluation_window():
    frame = frame_of(listings=20, days=6)
    split = validation.temporal_split(frame)
    window_end = frame["collection_timestamp"].max()
    assert split.validation["collection_timestamp"].min() >= split.boundary
    assert (split.validation["target_observed_at"] >= split.boundary).all()
    assert (split.validation["target_observed_at"] <= window_end).all()
    assert (split.validation["target_observed_at"] > split.validation["collection_timestamp"]).all()


def test_training_labels_are_invariant_to_any_validation_period_change():
    """Rewriting every future price must not move a single training label."""
    frame = frame_of(listings=16, days=6)
    boundary = validation.temporal_split(frame).boundary
    poisoned = frame.copy()
    future = poisoned["collection_timestamp"] >= boundary
    poisoned.loc[future, "effective_price"] = poisoned.loc[future, "effective_price"] * 5
    before = validation.temporal_split(frame).train.set_index("snapshot_id")[TARGET_COLUMN]
    after = validation.temporal_split(poisoned).train.set_index("snapshot_id")[TARGET_COLUMN]
    pd.testing.assert_series_equal(before.sort_index(), after.sort_index())


def test_validation_labels_are_invariant_to_training_period_price_changes():
    frame = frame_of(listings=16, days=6)
    boundary = validation.temporal_split(frame).boundary
    rewritten = frame.copy()
    past = rewritten["collection_timestamp"] < boundary
    rewritten.loc[past, "effective_price"] = rewritten.loc[past, "effective_price"] * 0.2
    before = validation.temporal_split(frame).validation.set_index("snapshot_id")[TARGET_COLUMN]
    after = validation.temporal_split(rewritten).validation.set_index("snapshot_id")[TARGET_COLUMN]
    pd.testing.assert_series_equal(before.sort_index(), after.sort_index())


def test_precomputed_global_target_on_the_input_is_ignored():
    frame = frame_of(listings=40, days=6)
    labelled_globally = target_module.add_target(frame)
    outcome_clean = train_models(frame, ["random_forest"])
    outcome_prelabelled = train_models(labelled_globally, ["random_forest"])
    assert outcome_prelabelled.training_rows == outcome_clean.training_rows
    assert outcome_prelabelled.split["boundary"] == outcome_clean.split["boundary"]
    assert outcome_prelabelled.selected.metrics == outcome_clean.selected.metrics
    assert outcome_clean.split["boundary_purged_rows"] == 40
    assert "target_observed_at" not in outcome_clean.feature_names


def test_split_metadata_records_ranges_and_safeguards():
    outcome = train_models(frame_of(listings=40, days=6), ["random_forest"])
    split = outcome.split
    assert split["strategy"] == validation.SPLIT_STRATEGY
    assert split["training_range"]["end"] < split["boundary"] <= split["validation_range"]["start"]
    assert len(split["leakage_safeguards"]) >= 4
    assert outcome.data_summary["unique_products"] == 40
    assert outcome.data_summary["observation_dates"] == 6


# --------------------------------------------------------------------------
# 3. Product/group overlap audit
# --------------------------------------------------------------------------


def test_group_overlap_reports_shared_listings_and_unseen_products():
    frame = frame_of(listings=30, days=6)
    # Ten products exist only from the boundary onwards.
    split = validation.temporal_split(frame)
    late = frame[~frame["product_key"].isin([f"product-{i}|acme|earbuds" for i in range(20, 30)]) | (frame["collection_timestamp"] >= split.boundary)]
    late_split = validation.temporal_split(late)
    overlap = validation.group_overlap(late_split.train, late_split.validation)
    assert overlap["validation_listings"] == 30
    assert overlap["listings_also_in_training"] == 20
    assert overlap["unseen_product_validation_rows"] == len(late_split.validation[late_split.validation["product_key"].str.contains(r"product-2\d\|")])


# --------------------------------------------------------------------------
# 2 + 3. Provenance policy and DEMO contamination
# --------------------------------------------------------------------------


@pytest.mark.parametrize("selected,dataset,profile", [
    (["demo"], ["demo"], "development_demo"),
    (["imported"], ["imported"], "imported_history"),
    (["live"], ["live"], "live_history"),
    (["imported", "live"], ["imported", "live"], "imported_and_live"),
    (["live", "imported"], ["live"], "imported_and_live"),
])
def test_permitted_provenance_selections(selected, dataset, profile):
    policy = provenance.resolve(selected, dataset)
    assert policy.profile == profile
    assert policy.development_override is False


@pytest.mark.parametrize("selected,dataset,message", [
    ([], ["live"], "Select the source types"),
    (["synthetic"], ["live"], "Unknown source type"),
    (["live"], ["live", "demo"], "rebuild the dataset"),
    (["imported"], ["live"], "not selected"),
    (["live"], [], "does not record"),
])
def test_provenance_rejections(selected, dataset, message):
    with pytest.raises(provenance.ProvenanceError, match=message):
        provenance.resolve(selected, dataset)


@pytest.mark.parametrize("selected", [["demo", "live"], ["demo", "imported"], ["demo", "imported", "live"]])
def test_demo_cannot_be_mixed_with_real_data_by_default(selected):
    with pytest.raises(provenance.ProvenanceError, match="DEMO data cannot be combined"):
        provenance.resolve(selected, selected)


def test_demo_mixing_override_is_development_only():
    with pytest.raises(provenance.ProvenanceError, match="ENVIRONMENT=development"):
        provenance.resolve(["demo", "live"], ["demo", "live"], development_override=True, is_development=False)
    policy = provenance.resolve(["demo", "live"], ["demo", "live"], development_override=True, is_development=True)
    assert policy.profile == "development_mixed" and policy.uses_demo


def test_training_requires_explicit_source_types(client, auth_headers):
    response = client.post("/ml/train", headers=auth_headers, json={})
    assert response.status_code == 422
    assert any(error["loc"][-1] == "source_types" for error in response.json()["detail"])


def test_training_rejects_a_dataset_with_unselected_provenance(client, auth_headers, clean_models, clean_snapshots, db_session):
    build_dataset_via_api(client, auth_headers)  # DEMO dataset
    response = client.post("/ml/train", headers=auth_headers, json={"source_types": ["live"]})
    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "provenance_rejected"
    assert "DEMO" in response.json()["detail"]["reason"]
    assert db_session.query(ModelMetadata).count() == 0


def test_training_rejects_demo_plus_live_selection(client, auth_headers, clean_models, clean_snapshots):
    build_dataset_via_api(client, auth_headers)
    response = client.post("/ml/train", headers=auth_headers, json={"source_types": ["demo", "live"]})
    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "provenance_rejected"


# --------------------------------------------------------------------------
# 4. Quality gate
# --------------------------------------------------------------------------


def gate(accuracy, *, sources=("live",), rows=400, dates=3, assessment="better_than_class_prior", best=None, majority=0.4, **extra):
    return validation.quality_gate(
        accuracy=accuracy,
        baseline_report={"majority_baseline": majority, "best_baseline_accuracy": best if best is not None else majority},
        source_types=list(sources), validation_rows=rows, validation_dates=dates,
        probability_report={"assessment": assessment}, **extra,
    )


def test_accuracy_at_or_below_majority_is_below_baseline():
    assert gate(0.40)[0] == "below_baseline"
    assert gate(0.33)[0] == "below_baseline"
    assert gate(0.33, sources=("demo",))[0] == "below_baseline"


def test_demo_data_is_never_above_experimental():
    status, reasons = gate(0.99, sources=("demo",), rows=10_000, dates=30)
    assert status == "experimental"
    assert any("DEMO" in reason for reason in reasons)


def test_development_override_and_legacy_split_cap_quality():
    assert gate(0.9, development_override=True)[0] == "experimental"
    assert gate(0.9, leakage_safe_split=False)[0] == "experimental"


def test_beating_majority_but_not_persistence_is_experimental():
    status, reasons = gate(0.45, majority=0.40, best=0.50)
    assert status == "experimental"
    assert any("strongest naive baseline" in reason for reason in reasons)


def test_small_evaluation_cannot_be_validated():
    status, reasons = gate(0.9, rows=50, dates=1)
    assert status == "candidate"
    assert any("200 are required" in reason for reason in reasons)
    assert any("date(s)" in reason for reason in reasons)


def test_marginal_accuracy_is_not_validated_by_a_single_metric():
    # 0.43 vs 0.40 on 400 rows: the 95% lower bound does not clear the baseline.
    status, reasons = gate(0.43, rows=400)
    assert status == "candidate"
    assert any("lower bound" in reason for reason in reasons)


def test_poor_probabilities_block_validation():
    assert gate(0.8, rows=1000, assessment="worse_than_class_prior")[0] == "candidate"
    assert gate(0.8, rows=1000, assessment="insufficient_data")[0] == "candidate"


def test_strong_real_evidence_is_validated():
    status, reasons = gate(0.8, rows=1000, dates=5)
    assert status == "validated"
    assert "uncalibrated" in reasons[-1]


def test_wilson_lower_bound():
    assert validation.accuracy_lower_bound(0.5, 100) == pytest.approx(0.4038, abs=1e-4)
    assert validation.accuracy_lower_bound(0.8, 1000) > 0.77


# --------------------------------------------------------------------------
# 5. Minimum-data rejection
# --------------------------------------------------------------------------


def test_too_few_observation_dates_is_insufficient_data():
    with pytest.raises(TrainingError, match="observation date") as error:
        train_models(frame_of(listings=60, days=3))
    assert error.value.status == "insufficient_data"


def test_too_few_products_is_insufficient_data():
    with pytest.raises(TrainingError, match="unique product") as error:
        train_models(frame_of(listings=6, days=10))
    assert error.value.status == "insufficient_data"


def test_too_few_labelled_rows_is_insufficient_data():
    with pytest.raises(TrainingError, match="can be labelled") as error:
        train_models(frame_of(listings=12, days=6))
    assert error.value.status == "insufficient_data"


def test_thin_class_is_insufficient_data():
    # Prices only ever rise or hold: "declining" never appears.
    rising = frame_of(listings=60, days=6, step=lambda price, listing, day: price * (1.03 if listing % 2 else 1.0))
    with pytest.raises(TrainingError, match="too few examples of class") as error:
        train_models(rising)
    assert error.value.status == "insufficient_data"


def test_minimums_are_configurable():
    frame = frame_of(listings=12, days=6)
    relaxed = TrainingRequirements(min_labelled_rows=20, min_training_rows=10, min_validation_rows=5, min_unique_products=5, min_rows_per_class=1)
    assert train_models(frame, ["random_forest"], requirements=relaxed).requirements["min_labelled_rows"] == 20


# --------------------------------------------------------------------------
# 6. Baselines
# --------------------------------------------------------------------------


def test_baseline_calculations():
    train = pd.DataFrame({TARGET_COLUMN: ["declining"] * 5 + ["stable"] * 3 + ["improving"] * 2})
    validation_rows = pd.DataFrame({
        TARGET_COLUMN: ["stable", "stable", "stable", "declining", "improving"],
        # previous moves: stable, improving, missing, declining, improving
        "price_change_percentage": [0.2, 3.0, np.nan, -4.0, 2.0],
    })
    report = validation.baselines(train, validation_rows)
    assert report["majority_baseline"] == 0.6
    assert report["training_majority_class"] == "declining"
    assert report["training_majority_accuracy"] == 0.2
    # stable(ok) improving(x) fallback-declining(x) declining(ok) improving(ok)
    assert report["persistence_accuracy"] == 0.6
    assert report["persistence_coverage_rows"] == 4
    assert report["best_baseline_accuracy"] == 0.6
    assert report["metric"] == "accuracy"


# --------------------------------------------------------------------------
# 8. Probability quality labelling
# --------------------------------------------------------------------------


def test_probability_quality_is_measured_but_never_calibrated():
    truth = pd.Series(["declining", "stable", "improving"] * 100)
    perfect = np.eye(3)[truth.map({c: i for i, c in enumerate(CLASSES)})] * 0.9 + 0.1 / 3
    report = validation.probability_quality(truth, perfect, {"declining": 1, "stable": 1, "improving": 1})
    assert report["calibration_status"] == "uncalibrated"
    assert report["assessment"] == "better_than_class_prior"
    assert report["log_loss"] < report["class_prior_log_loss"]
    assert 0 <= report["expected_calibration_error"] <= 1


def test_small_samples_are_labelled_insufficient():
    truth = pd.Series(["declining", "stable"] * 20)
    report = validation.probability_quality(truth, np.full((40, 3), 1 / 3), {"declining": 5, "stable": 5, "improving": 5})
    assert report["assessment"] == "insufficient_data"
    assert report["calibration_status"] == "uncalibrated"


def test_overconfident_wrong_probabilities_are_worse_than_prior():
    truth = pd.Series(["declining"] * 300)
    wrong = np.tile([0.02, 0.96, 0.02], (300, 1))
    assert validation.probability_quality(truth, wrong, {"declining": 10, "stable": 10, "improving": 10})["assessment"] == "worse_than_class_prior"


def test_missing_probabilities_are_unavailable():
    assert validation.probability_quality(pd.Series(["stable"]), None, {})["calibration_status"] == "unavailable"


# --------------------------------------------------------------------------
# 7. Metadata persistence (isolated storage)
# --------------------------------------------------------------------------


def test_quality_evidence_is_persisted(client, auth_headers, clean_models, clean_snapshots, db_session):
    build_dataset_via_api(client, auth_headers)
    body = client.post("/ml/train", headers=auth_headers, json={"source_types": ["demo"], "models": ["random_forest"]}).json()
    quality = body["quality"]
    assert quality["quality_status"] in {"below_baseline", "experimental"}
    assert quality["calibration_status"] == "uncalibrated"
    assert quality["probability_quality"]["assessment"] == "insufficient_data"
    assert quality["source_policy"]["profile"] == "development_demo"
    assert quality["split"]["boundary_purged_rows"] > 0
    assert quality["data_summary"]["unique_products"] == 79
    assert quality["data_summary"]["observation_dates"] == 5
    assert quality["baselines"]["metric"] == "accuracy"
    assert quality["legacy"] is False

    db_session.expire_all()
    record = db_session.query(ModelMetadata).filter_by(model_version=body["model_version"]).one()
    assert record.quality_status == quality["quality_status"]
    assert record.calibration_status == "uncalibrated"
    assert record.hyperparameters["training_policy_version"] == training_service.TRAINING_POLICY_VERSION
    assert record.hyperparameters["split"]["boundary"]
    assert record.metrics["baselines"]["majority_baseline"] == body["majority_baseline"]

    sidecar = json.loads((Path(record.artifact_path).parent / f"model_{record.model_version}.metadata.json").read_text(encoding="utf-8"))
    assert sidecar["quality_status"] == record.quality_status
    assert sidecar["split"]["leakage_safeguards"]

    status = client.get("/ml/status", headers=auth_headers).json()
    assert status["quality"]["quality_status"] == record.quality_status
    assert status["history"][0]["quality_status"] == record.quality_status
    assert client.get("/ml/metrics", headers=auth_headers).json()["quality"]["split"]["strategy"] == validation.SPLIT_STRATEGY


# --------------------------------------------------------------------------
# 9. Backwards compatibility with existing model metadata
# --------------------------------------------------------------------------


def legacy_record(accuracy):
    return ModelMetadata(
        model_name="legacy", model_version="v5-like", algorithm="xgboost", status="completed",
        accuracy=accuracy, f1_score=0.3187, dataset_rows=384,
        metrics={"majority_baseline": 0.4062, "accuracy": accuracy},
        hyperparameters={"target": TARGET_COLUMN, "dataset_source_types": ["demo"], "training_rows": 288, "validation_rows": 96, "split_strategy": "time-aware: train < 2026-09-04, validate >= 2026-09-04"},
    )


def test_legacy_below_baseline_record_is_interpreted_not_rewritten():
    record = legacy_record(0.3333)
    report = training_service.quality_report(record)
    assert report["legacy"] is True and report["leakage_safe_split"] is False
    assert report["quality_status"] == "below_baseline"
    assert report["calibration_status"] == "uncalibrated"
    assert any("before Phase 12" in reason for reason in report["quality_reasons"])
    assert record.quality_status is None  # nothing is written back


def test_legacy_record_can_never_be_candidate_or_validated():
    record = legacy_record(0.99)
    record.hyperparameters["dataset_source_types"] = ["live"]
    record.hyperparameters["validation_rows"] = 100_000
    assert training_service.quality_report(record)["quality_status"] == "experimental"


def test_legacy_active_model_status_endpoint_still_works(ready, client):
    body = client.get("/ml/status", headers=ready.headers).json()
    assert body["trained"] is True
    assert body["quality"]["legacy"] is True
    assert body["quality"]["quality_status"] == "below_baseline"


def test_prediction_saved_before_phase_12_still_validates(ready, client):
    body = post(client, ready).json()
    for key in ("quality_status", "calibration_status", "probability_assessment", "baselines", "legacy_model"):
        body["model"].pop(key)
    body.pop("recommendation_label")
    restored = PredictionResponse.model_validate(body)
    assert restored.model.calibration_status == "uncalibrated"
    assert restored.recommendation_label == "Highest observed opportunity score"


# --------------------------------------------------------------------------
# 10. Prediction warning behaviour
# --------------------------------------------------------------------------


def test_below_baseline_prediction_is_labelled_experimental(ready, client):
    body = post(client, ready).json()
    assert body["recommendation_label"] == "Highest experimental opportunity score"
    assert body["model"]["quality_status"] == "below_baseline"
    assert body["model"]["calibration_status"] == "uncalibrated"
    assert body["model"]["legacy_model"] is True
    assert "does not outperform the validation baseline" in body["warning"]
    assert "uncalibrated" in body["warning"]
    assert "Phase 12" in body["warning"]


def test_candidate_quality_uses_the_plain_label(ready, client, monkeypatch):
    real = training_service.quality_report

    def candidate(record):
        report = real(record)
        return {**report, "quality_status": "candidate", "legacy": False}

    monkeypatch.setattr(training_service, "quality_report", candidate)
    ready.model.accuracy = 0.6
    monkeypatch.setattr(prediction_service.opportunity, "number", lambda value: None if value is None else float(value))
    record_quality = prediction_service.quality(ready.model)
    assert prediction_service.recommendation_label(record_quality) == "Highest observed opportunity score"
    assert "Experimental result" not in record_quality.warning


def test_experimental_status_never_gets_the_plain_label():
    base = dict(version="v", type="rf", target=TARGET_COLUMN, primary_metric_value=0.5, accuracy=0.5,
                majority_baseline=0.4, below_baseline=False, source_types=["live"], warning="w")
    from app.schemas.prediction import ModelQuality
    for status in ("experimental", "below_baseline", None):
        assert prediction_service.recommendation_label(ModelQuality(**base, quality_status=status)) == "Highest experimental opportunity score"
