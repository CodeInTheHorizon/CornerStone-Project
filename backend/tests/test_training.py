"""Phase 6 tests: target, split, preprocessing, training, persistence, API.

The strongest assertions here are the negative ones. A model that scores
near-perfectly on this data would mean leakage, not skill, so several tests
exist specifically to catch that.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml import target as target_module
from app.ml.training import (
    EXCLUDED_COLUMNS,
    XGBOOST_AVAILABLE,
    TrainingError,
    select_features,
    time_aware_split,
    train_models,
)
from app.models import ModelMetadata
from app.services import dataset_service, training_service

BASE = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def auth_headers(client):
    email = f"trainer_{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": "marketpulse1"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def clean_snapshots(db_session):
    """Start from an empty snapshot table.

    The test database is session-scoped, so earlier modules leave live and
    imported rows behind. A test asserting the dataset is demo-only has to
    control what is there.
    """
    from app.models import MarketplaceSnapshot

    db_session.query(MarketplaceSnapshot).delete()
    db_session.commit()
    yield
    db_session.query(MarketplaceSnapshot).delete()
    db_session.commit()


@pytest.fixture
def clean_models(db_session, tmp_path, monkeypatch):
    """Each test owns metadata AND files, so numbering can safely start at v1."""
    monkeypatch.setattr(training_service, "ARTIFACT_DIR", tmp_path / "models")
    db_session.query(ModelMetadata).delete()
    db_session.commit()
    yield
    db_session.query(ModelMetadata).delete()
    db_session.commit()


def synthetic_frame(
    listings: int = 40, days: int = 5, seed: int = 7, price_walk=None
) -> pd.DataFrame:
    """A dataset-shaped frame with enough rows to train on."""
    rng = np.random.default_rng(seed)
    rows = []
    for listing in range(listings):
        price = float(rng.integers(500, 5000))
        reviews = int(rng.integers(50, 5000))
        for day in range(days):
            if price_walk is not None:
                price = price_walk(price, day)
            else:
                price = max(50.0, price * (1 + rng.uniform(-0.05, 0.05)))
            reviews += int(rng.integers(0, 40))
            rows.append(
                {
                    "snapshot_id": len(rows) + 1,
                    "platform": ["amazon", "flipkart", "croma", "alibaba"][listing % 4],
                    "source_type": "demo",
                    "product_key": f"product-{listing}|acme|earbuds",
                    "product_name": f"Product {listing}",
                    "brand_normalized": "acme",
                    "category_normalized": "wireless earbuds",
                    "external_id": f"X{listing}",
                    "currency": "INR",
                    "collection_timestamp": BASE + timedelta(days=day),
                    "effective_price": round(price, 2),
                    "discount_percentage": float(rng.uniform(0, 40)),
                    "rating": float(rng.uniform(3, 5)),
                    "review_count": reviews,
                    "competition_score": float(rng.uniform(20, 60)),
                    "price_vs_market_median": float(rng.uniform(0.5, 1.5)),
                    "observation_index": day,
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Target
# --------------------------------------------------------------------------


def test_target_classes_come_from_the_next_observation():
    frame = pd.DataFrame(
        [
            {
                "platform": "amazon",
                "product_key": "p|b|c",
                "collection_timestamp": BASE + timedelta(days=day),
                "effective_price": price,
            }
            for day, price in enumerate([100.0, 110.0, 110.2, 100.0])
        ]
    )

    labelled = target_module.add_target(frame).sort_values("collection_timestamp")
    classes = labelled[target_module.TARGET_COLUMN].tolist()

    assert classes[0] == "improving"  # 100 -> 110
    assert classes[1] == "stable"  # 110 -> 110.2, inside +/-1%
    assert classes[2] == "declining"  # 110.2 -> 100
    # The last observation has no successor and cannot be labelled.
    assert pd.isna(classes[3])


def test_target_is_deterministic():
    frame = synthetic_frame(listings=8)
    first = target_module.add_target(frame)[target_module.TARGET_COLUMN]
    second = target_module.add_target(frame)[target_module.TARGET_COLUMN]
    pd.testing.assert_series_equal(first, second)


def test_unlabelled_rows_are_excluded_not_defaulted():
    frame = target_module.add_target(synthetic_frame(listings=10, days=3))
    labelled = target_module.labelled_rows(frame)

    # One row per listing (the last) has no future.
    assert len(labelled) == len(frame) - 10
    assert labelled[target_module.TARGET_COLUMN].notna().all()


def test_majority_baseline_is_reported():
    frame = target_module.labelled_rows(target_module.add_target(synthetic_frame()))
    baseline = target_module.majority_baseline(frame)

    assert baseline is not None
    assert 0 < baseline <= 1


# --------------------------------------------------------------------------
# Leakage guards
# --------------------------------------------------------------------------


def test_target_helper_columns_are_excluded_from_features():
    for column in target_module.TARGET_HELPER_COLUMNS:
        assert column in EXCLUDED_COLUMNS, f"{column} encodes the future"


def test_identifier_columns_are_excluded_from_features():
    frame = target_module.add_target(synthetic_frame())
    numeric, categorical = select_features(frame)
    chosen = set(numeric) | set(categorical)

    for column in (
        "snapshot_id",
        "product_key",
        "external_id",
        "product_name",
        "collection_timestamp",
        "forward_price",
        "forward_price_change_pct",
        target_module.TARGET_COLUMN,
    ):
        assert column not in chosen, f"{column} must never be a feature"


def test_split_is_time_aware_with_no_overlap():
    frame = target_module.labelled_rows(target_module.add_target(synthetic_frame()))
    train, validation, description = time_aware_split(frame)

    assert "temporal" in description and "boundary-first" in description
    assert train["collection_timestamp"].max() < validation["collection_timestamp"].min()
    # No training label may come from the validation period.
    assert train["target_observed_at"].max() < validation["collection_timestamp"].min()
    assert len(train) > 0 and len(validation) > 0
    # No row can appear on both sides.
    assert set(train["snapshot_id"]) & set(validation["snapshot_id"]) == set()


def test_split_rejects_a_single_date():
    frame = target_module.labelled_rows(
        target_module.add_target(synthetic_frame(days=2))
    )
    single_date = frame[frame["collection_timestamp"] == frame["collection_timestamp"].min()]

    with pytest.raises(TrainingError) as exc:
        time_aware_split(single_date)
    assert exc.value.status == "insufficient_data"


def test_a_leaked_feature_would_be_detected():
    """Sanity check on the guard, not on the model.

    Training with the target's own source column left in must produce a
    near-perfect score -- which is exactly what the near-perfect warning is
    there to flag.
    """
    frame = target_module.add_target(synthetic_frame(listings=200))
    leaked = frame.copy()
    leaked["leaky_copy"] = leaked["forward_price_change_pct"]

    outcome = train_models(leaked, ["random_forest"])

    assert outcome.selected.metrics["accuracy"] > 0.95
    assert any("near-perfect" in w for w in outcome.warnings), (
        "a leaked feature must trigger the leakage warning"
    )


# --------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------


def test_random_forest_trains_and_reports_real_metrics():
    frame = target_module.add_target(synthetic_frame(listings=60))
    outcome = train_models(frame, ["random_forest"])

    assert outcome.selected.name == "random_forest"
    assert outcome.selected.trained
    for metric in ("accuracy", "precision_weighted", "recall_weighted", "f1_weighted"):
        assert 0 <= outcome.selected.metrics[metric] <= 1
    assert outcome.training_rows > 0
    assert outcome.validation_rows > 0
    assert outcome.confusion_ok if hasattr(outcome, "confusion_ok") else True
    assert outcome.selected.confusion_matrix


@pytest.mark.skipif(not XGBOOST_AVAILABLE, reason="XGBoost not installed")
def test_xgboost_trains():
    frame = target_module.add_target(synthetic_frame(listings=60))
    outcome = train_models(frame, ["xgboost"])

    assert outcome.selected.name == "xgboost"
    assert 0 <= outcome.selected.metrics["accuracy"] <= 1


def test_model_comparison_picks_highest_f1():
    frame = target_module.add_target(synthetic_frame(listings=60))
    outcome = train_models(frame)

    trained = [r for r in outcome.results if r.trained]
    assert len(trained) >= 1
    best = max(r.metrics["f1_weighted"] for r in trained)
    assert outcome.selected.metrics["f1_weighted"] == best
    assert "F1" in outcome.selection_rule


def test_training_is_reproducible():
    frame = target_module.add_target(synthetic_frame(listings=60))
    first = train_models(frame, ["random_forest"])
    second = train_models(frame, ["random_forest"])

    assert first.selected.metrics == second.selected.metrics


def test_one_class_target_is_rejected():
    # A price that only ever rises produces a single class.
    frame = target_module.add_target(
        synthetic_frame(listings=40, price_walk=lambda price, day: price * 1.10)
    )

    with pytest.raises(TrainingError) as exc:
        train_models(frame)
    assert exc.value.status == "insufficient_data"
    assert "one class" in exc.value.reason.lower()


def test_missing_target_column_is_rejected():
    with pytest.raises(TrainingError) as exc:
        train_models(synthetic_frame(listings=60).drop(columns=["effective_price"]))
    assert exc.value.status == "missing_target"


def test_too_few_rows_is_rejected():
    frame = target_module.add_target(synthetic_frame(listings=3, days=3))
    with pytest.raises(TrainingError) as exc:
        train_models(frame)
    assert exc.value.status == "insufficient_data"


def test_a_failing_candidate_does_not_kill_the_run(monkeypatch):
    """One broken model must not lose the results of the other."""
    import app.ml.training as training_module

    original = training_module._candidates

    class Exploding:
        def fit(self, *args, **kwargs):
            raise RuntimeError("boom")

    def patched(names):
        built = original(["random_forest"])
        built["exploding"] = Exploding()
        return built

    monkeypatch.setattr(training_module, "_candidates", patched)

    frame = target_module.add_target(synthetic_frame(listings=60))
    outcome = training_module.train_models(frame)

    assert outcome.selected.name == "random_forest"
    assert any(r.error for r in outcome.results)


# --------------------------------------------------------------------------
# Persistence + API
# --------------------------------------------------------------------------


def build_dataset_via_api(client, headers):
    client.post("/data/demo/load", headers=headers)
    response = client.post(
        "/ml/dataset/build", headers=headers, json={"persist": True}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "method,path",
    [("post", "/ml/train"), ("get", "/ml/status"), ("get", "/ml/metrics")],
)
def test_ml_endpoints_require_authentication(client, method, path):
    response = client.post(path, json={}) if method == "post" else client.get(path)
    assert response.status_code == 401


def test_status_before_any_training(client, auth_headers, clean_models):
    body = client.get("/ml/status", headers=auth_headers).json()

    assert body["trained"] is False
    assert body["active_model"] is None
    assert "random_forest" in body["available_models"]


def test_metrics_before_training_is_a_clean_404(client, auth_headers, clean_models):
    response = client.get("/ml/metrics", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["status"] == "not_trained"


def test_train_without_a_dataset_reports_no_dataset(
    client, auth_headers, clean_models, monkeypatch
):
    monkeypatch.setattr(dataset_service, "list_datasets", lambda: [])
    monkeypatch.setattr(dataset_service, "latest_dataset", lambda: None)

    response = client.post("/ml/train", headers=auth_headers, json={"source_types": ["demo"]})

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "no_dataset"


def test_full_training_run_via_api(client, auth_headers, clean_models, clean_snapshots, db_session):
    build_dataset_via_api(client, auth_headers)

    response = client.post(
        "/ml/train", headers=auth_headers, json={"dataset_id": "latest", "source_types": ["demo"]}
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "success"
    assert body["model_version"] == "v1"
    assert body["selected_model"] in {"random_forest", "xgboost"}
    assert body["target"] == target_module.TARGET_COLUMN
    assert body["training_rows"] > 0 and body["validation_rows"] > 0
    assert 0 <= body["metrics"]["accuracy"] <= 1
    assert body["majority_baseline"] is not None
    assert body["dataset_source_types"] == ["demo"]
    # A demo-trained model must say so.
    assert body["notice"] == "Model trained on DEMO data for development/testing."
    assert body["selection_rule"]
    assert "boundary-first" in body["split_strategy"]

    # Metrics must be measured, not perfect: this data is close to noise.
    assert body["metrics"]["accuracy"] < 0.95, (
        "near-perfect accuracy on synthetic drift would mean leakage"
    )


def test_artifact_and_metadata_are_persisted(
    client, auth_headers, clean_models, clean_snapshots, db_session
):
    build_dataset_via_api(client, auth_headers)
    body = client.post("/ml/train", headers=auth_headers, json={"source_types": ["demo"]}).json()

    record = (
        db_session.query(ModelMetadata)
        .filter(ModelMetadata.model_version == body["model_version"])
        .one()
    )
    assert record.is_active is True
    assert record.status == "completed"
    assert record.accuracy is not None
    assert record.feature_names

    artifact = Path(record.artifact_path)
    assert artifact.exists()

    sidecar = artifact.with_suffix("").with_suffix(".metadata.json")
    sidecar = artifact.parent / f"model_{record.model_version}.metadata.json"
    assert sidecar.exists()
    saved = json.loads(sidecar.read_text(encoding="utf-8"))
    assert saved["target"] == target_module.TARGET_COLUMN
    assert saved["dataset_source_types"] == ["demo"]
    assert saved["notice"]

    # The saved pipeline loads and can predict.
    pipeline = training_service.load_pipeline(record)
    assert pipeline is not None


def test_retraining_versions_and_does_not_overwrite(
    client, auth_headers, clean_models, clean_snapshots, db_session
):
    build_dataset_via_api(client, auth_headers)

    first = client.post("/ml/train", headers=auth_headers, json={"source_types": ["demo"]}).json()
    first_record = db_session.query(ModelMetadata).filter_by(model_version=first["model_version"]).one()
    original_bytes = Path(first_record.artifact_path).read_bytes()
    second = client.post("/ml/train", headers=auth_headers, json={"source_types": ["demo"]}).json()

    assert first["model_version"] == "v1"
    assert second["model_version"] == "v2"
    assert Path(first["model_version"]).name != Path(second["model_version"]).name

    # The API commits through a separate session; refresh this test session.
    db_session.expire_all()
    records = {r.model_version: r for r in db_session.query(ModelMetadata).all()}
    assert records["v1"].is_active is False, "only one model may be active"
    assert records["v2"].is_active is True
    # The older artifact survives.
    assert Path(records["v1"].artifact_path).read_bytes() == original_bytes


def test_status_and_metrics_after_training(client, auth_headers, clean_models, clean_snapshots):
    build_dataset_via_api(client, auth_headers)
    trained = client.post("/ml/train", headers=auth_headers, json={"source_types": ["demo"]}).json()

    status_body = client.get("/ml/status", headers=auth_headers).json()
    assert status_body["trained"] is True
    assert status_body["version"] == trained["model_version"]
    assert status_body["active_model"] == trained["selected_model"]
    assert status_body["dataset_source_types"] == ["demo"]
    assert status_body["notice"]
    assert status_body["history"]

    metrics_body = client.get("/ml/metrics", headers=auth_headers).json()
    assert metrics_body["target"] == target_module.TARGET_COLUMN
    assert metrics_body["confusion_matrix"]
    assert metrics_body["confusion_labels"]
    assert metrics_body["class_distribution"]
    assert metrics_body["feature_count"] > 0
    assert metrics_body["excluded_columns"], "leakage exclusions must be reported"
    assert metrics_body["majority_baseline"] is not None
    assert metrics_body["all_models"]


def test_selecting_only_random_forest(client, auth_headers, clean_models, clean_snapshots):
    build_dataset_via_api(client, auth_headers)

    body = client.post(
        "/ml/train", headers=auth_headers, json={"models": ["random_forest"], "source_types": ["demo"]}
    ).json()

    assert body["selected_model"] == "random_forest"
    assert [run["model"] for run in body["all_models"]] == ["random_forest"]
