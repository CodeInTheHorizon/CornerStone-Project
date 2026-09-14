"""Phase 7 contract, real Pipeline inference, scoring, persistence and failures."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import joblib
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from app.ml import opportunity
from app.ml.dataset_builder import clean, normalize, IDENTITY_COLUMNS
from app.ml.features import build_features, FEATURE_NAMES
from app.ml.target import add_target, CLASSES
from app.ml.training import train_models, XGBOOST_AVAILABLE
from app.models import ModelMetadata, Prediction
from app.schemas.prediction import PredictRequest
from app.services import dataset_service, prediction_service as service, training_service


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    """Train a fixture model on the same 35-feature schema, in isolated storage."""
    directory = tmp_path_factory.mktemp("prediction_fixture")
    payload = json.loads((Path(__file__).resolve().parents[2] / "data/demo/electronics_snapshots.json").read_text())
    raw = pd.DataFrame(payload["records"])
    raw["id"] = range(1, len(raw) + 1)
    raw["source_type"] = "demo"
    cleaned, _ = clean(raw)
    frame = build_features(normalize(cleaned)).rename(columns={"id": "snapshot_id"})
    frame = frame[[*IDENTITY_COLUMNS, *FEATURE_NAMES]]
    frame.to_csv(directory / "input.csv", index=False)
    outcome = train_models(add_target(frame), ["random_forest"])
    joblib.dump(outcome.selected.pipeline, directory / "model.pkl")
    # Pick a genuinely shared identity to test comparison without fuzzy merging.
    counts = frame.groupby("product_key")["platform"].nunique()
    key = counts.sort_values(ascending=False).index[0]
    return directory, frame, outcome, key


@pytest.fixture
def ready(prepared, monkeypatch, db_session, client):
    directory, frame, outcome, key = prepared
    monkeypatch.setattr(training_service, "ARTIFACT_DIR", directory)
    monkeypatch.setattr(dataset_service, "PROCESSED_DIR", directory)
    db_session.query(Prediction).delete()
    db_session.query(ModelMetadata).delete()
    db_session.commit()
    model = ModelMetadata(
        model_name="fixture", model_version="fixture-v1", algorithm="random_forest",
        status="completed", is_active=True, feature_names=outcome.feature_names,
        artifact_path=str(directory / "model.pkl"), accuracy=0.3333, f1_score=0.3187,
        metrics={"majority_baseline": 0.4062},
        hyperparameters={"target": "marketplace_opportunity_class", "dataset_source_types": ["demo"]},
    )
    db_session.add(model)
    db_session.commit()
    metadata = {"dataset_id": "fixture-data", "source_types": ["demo"], "generated_at": "2026-09-10T00:00:00+00:00", "csv_path": str(directory / "input.csv")}
    monkeypatch.setattr(dataset_service, "list_datasets", lambda: [metadata])
    token = client.post("/auth/register", json={"email": f"predict-{uuid.uuid4().hex}@example.com", "password": "marketpulse1"}).json()
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    user_id = token["user"]["id"]
    yield SimpleNamespace(model=model, key=key, headers=headers, user_id=user_id, frame=frame, metadata=metadata)
    db_session.query(Prediction).delete()
    db_session.query(ModelMetadata).delete()
    db_session.commit()


def post(client, ready, **extra):
    return client.post("/ml/predict", headers=ready.headers, json={"product_key": ready.key, **extra})


def test_active_saved_pipeline_is_used_without_fitting(ready, db_session, monkeypatch, client):
    original = training_service.load_pipeline
    loader = Mock(side_effect=original)
    monkeypatch.setattr(training_service, "load_pipeline", loader)
    monkeypatch.setattr(training_service, "train", Mock(side_effect=AssertionError("must not retrain")))
    response = post(client, ready)
    assert response.status_code == 200, response.text
    loader.assert_called_once()
    assert response.json()["ranking"]


def test_exact_preprocessing_contract_and_null_history(ready, db_session):
    record, pipeline = service.load_active(db_session)
    row = ready.frame.iloc[0]
    features = service.feature_frame(row, record.feature_names)
    assert list(features.columns) == list(pipeline.feature_names_in_)
    assert features["previous_price"].isna().all()
    label, probabilities, confidence = service.infer(pipeline, features, record.algorithm)
    assert label in CLASSES
    assert sum(probabilities.values()) == pytest.approx(1)
    assert confidence == probabilities[label]
    # RF classes are alphabetical: declining, improving, stable, not CLASSES.
    raw = pipeline.predict_proba(features)[0]
    assert probabilities["improving"] == pytest.approx(raw[list(pipeline.classes_).index("improving")])


@pytest.mark.skipif(not XGBOOST_AVAILABLE, reason="XGBoost unavailable")
def test_real_xgboost_probability_ids_are_decoded(prepared):
    _, frame, _, _ = prepared
    outcome = train_models(add_target(frame), ["xgboost"])
    label, probabilities, confidence = service.infer(outcome.selected.pipeline, frame[outcome.feature_names].tail(1), "xgboost")
    assert label in CLASSES
    assert list(probabilities) == CLASSES
    assert confidence == probabilities[label]


def test_estimator_without_probabilities_is_honest():
    model = SimpleNamespace(predict=lambda frame: np.array(["stable"]))
    label, probabilities, confidence = service.infer(model, pd.DataFrame(), "random_forest")
    assert (label, probabilities, confidence) == ("stable", None, None)


@pytest.mark.parametrize("probabilities", [[0.5, 0.5, float("nan")], [1.2, -0.1, -0.1], [0.1, 0.1, 0.1]])
def test_bad_probabilities_are_rejected(probabilities):
    model = SimpleNamespace(predict=lambda frame: ["stable"], predict_proba=lambda frame: [probabilities], classes_=CLASSES)
    with pytest.raises(ValueError):
        service.infer(model, pd.DataFrame(), "random_forest")


def test_score_bounds_determinism_contributions_and_ml_cap(prepared):
    for row in prepared[1].to_dict("records"):
        first = opportunity.score(row, {"declining": 0.1, "stable": 0.2, "improving": 0.7})
        assert first == opportunity.score(row, {"declining": 0.1, "stable": 0.2, "improving": 0.7})
        assert 0 <= first["opportunity_score"] <= 100
        assert first["opportunity_score"] == round(sum(first["components"].values()), 1)
        assert first["components"]["model_signal"] <= 10
    assert sum(opportunity.WEIGHTS.values()) == 100


def test_missing_signals_do_not_inflate_model_weight():
    result = opportunity.score({}, {"improving": 1.0})
    assert result["opportunity_score"] == 10
    assert result["coverage_weight"] == 10
    assert len(result["missing_components"]) == 6
    assert result["normalized_signals"]["rating_signal"] is None
    assert opportunity.score({}, None)["opportunity_score"] == 0


def test_api_persists_complete_result_and_quality(ready, client, db_session):
    response = post(client, ready)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"]["accuracy"] == 0.3333
    assert body["model"]["majority_baseline"] == 0.4062
    assert body["model"]["below_baseline"] is True
    assert "DEMO" in body["warning"] and "baseline" in body["warning"]
    assert body["data_provenance"]["source_types"] == ["demo"]
    assert len(body["platform_results"]) == 4
    scores = [r["opportunity_score"] for r in body["ranking"]]
    assert scores == sorted(scores, reverse=True)
    record = db_session.get(Prediction, body["id"])
    assert record.user_id == ready.user_id
    assert record.result_payload == body
    assert record.model_metadata_id == ready.model.id
    assert record.created_at is not None
    assert record.input_payload["product_key"] == ready.key
    assert record.result_payload["ranking"][0]["probabilities"]


def test_history_and_detail_are_user_scoped_and_keep_old_quality(ready, client, db_session):
    body = post(client, ready).json()
    ready.model.accuracy = 0.99
    db_session.commit()
    history = client.get("/ml/predictions", headers=ready.headers).json()
    assert history["total"] == 1
    assert history["items"][0]["model"]["accuracy"] == 0.3333
    assert client.get(f"/ml/predictions/{body['id']}", headers=ready.headers).json() == body
    other = client.post("/auth/register", json={"email": f"other-{uuid.uuid4().hex}@example.com", "password": "marketpulse1"}).json()
    headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get("/ml/predictions", headers=headers).json()["total"] == 0
    assert client.get(f"/ml/predictions/{body['id']}", headers=headers).status_code == 404


def test_insufficient_platforms_are_not_fabricated(ready, client, monkeypatch):
    frame = ready.frame[ready.frame["platform"] == "amazon"].copy()
    key = frame["product_key"].iloc[0]
    monkeypatch.setattr(dataset_service, "load_dataset_frame", lambda *_: frame)
    body = client.post("/ml/predict", headers=ready.headers, json={"product_key": key}).json()
    assert len(body["ranking"]) == 1
    assert body["score_difference"] is None
    assert "Only one platform" in body["warning"]
    for result in body["platform_results"]:
        if result["platform"] != "amazon":
            assert result["status"] == "insufficient_data"
            assert result["opportunity_score"] is None and result["predicted_class"] is None


def test_unknown_product_creates_no_prediction(ready, client, db_session):
    response = client.post("/ml/predict", headers=ready.headers, json={"product_key": "absent"})
    assert response.status_code == 422
    assert not list(db_session.scalars(select(Prediction)))


@pytest.mark.parametrize("field,value", [("rating", 99), ("effective_price", -1), ("currency", "USD"), ("source_type", "unknown"), ("collection_timestamp", "bad")])
def test_invalid_observations_return_platform_errors(ready, client, monkeypatch, field, value):
    frame = ready.frame.copy()
    frame[field] = value
    monkeypatch.setattr(dataset_service, "load_dataset_frame", lambda *_: frame)
    response = post(client, ready)
    assert response.status_code == 422, response.text
    assert all(r["opportunity_score"] is None for r in response.json()["detail"]["platform_results"])


def test_missing_feature_column_is_not_imputed_into_existence(ready, client, monkeypatch):
    monkeypatch.setattr(dataset_service, "load_dataset_frame", lambda *_: ready.frame.drop(columns=["review_growth"]))
    response = post(client, ready)
    assert response.status_code == 422
    assert any(r["status"] == "incompatible_features" for r in response.json()["detail"]["platform_results"])


def test_stale_observations_are_explicit(ready, client, monkeypatch):
    frame = ready.frame.copy()
    frame["collection_timestamp"] = pd.to_datetime(frame["collection_timestamp"], utc=True) - pd.Timedelta(days=365)
    monkeypatch.setattr(dataset_service, "load_dataset_frame", lambda *_: frame)
    response = post(client, ready)
    assert response.status_code == 200, response.text
    assert all(r["stale"] for r in response.json()["ranking"])
    assert "older than" in response.json()["warning"]


@pytest.mark.parametrize("kind,expected", [("none", "not_trained"), ("missing", "missing_artifact"), ("corrupt", "corrupt_artifact"), ("mismatch", "incompatible_features")])
def test_model_failures_are_explicit(ready, client, db_session, tmp_path, kind, expected):
    if kind == "none":
        ready.model.is_active = False
    elif kind == "missing":
        ready.model.artifact_path = str(tmp_path / "missing.pkl")
    elif kind == "corrupt":
        path = tmp_path / "corrupt.pkl"
        path.write_bytes(b"not a pickle")
        ready.model.artifact_path = str(path)
    else:
        ready.model.feature_names = ["wrong"]
    db_session.commit()
    response = post(client, ready)
    assert response.status_code in (409, 503)
    assert response.json()["detail"]["status"] == expected
    assert not list(db_session.scalars(select(Prediction)))


@pytest.mark.parametrize("mode", ["no_metadata", "missing_file", "unreadable"])
def test_missing_or_invalid_dataset(ready, client, monkeypatch, mode):
    if mode == "no_metadata":
        monkeypatch.setattr(dataset_service, "list_datasets", lambda: [])
    elif mode == "missing_file":
        monkeypatch.setattr(dataset_service, "load_dataset_frame", lambda *_: None)
    else:
        monkeypatch.setattr(dataset_service, "load_dataset_frame", Mock(side_effect=ValueError("bad csv")))
    assert post(client, ready).status_code == 422


def test_pipeline_prediction_failure_never_returns_fallback(ready, client, monkeypatch):
    monkeypatch.setattr(service, "infer", Mock(side_effect=ValueError("broken estimator")))
    response = post(client, ready)
    assert response.status_code == 422
    assert any(r["status"] == "prediction_failed" for r in response.json()["detail"]["platform_results"])


def test_options_search_returns_latest_observed_context(ready, client):
    body = client.get("/ml/prediction-options?q=nova&limit=2", headers=ready.headers).json()
    assert body["dataset_id"] == "fixture-data"
    assert 0 < len(body["products"]) <= 2
    assert body["source_types"] == ["demo"]
    for product in body["products"]:
        assert "nova" in product["product_key"]
        assert all("2026-09-05" in row["data_freshness"] for row in product["platforms"])


@pytest.mark.parametrize("method,path", [("post", "/ml/predict"), ("get", "/ml/predictions"), ("get", "/ml/predictions/1"), ("get", "/ml/prediction-options")])
def test_authentication_required(client, method, path):
    assert getattr(client, method)(path, **({"json": {"product_key": "p"}} if method == "post" else {})).status_code == 401


@pytest.mark.parametrize("extra", [{"platforms": ["ebay"]}, {"platforms": []}, {"rating": 5}, {"dataset_id": ""}])
def test_invalid_request_fields_rejected(ready, client, extra):
    assert post(client, ready, **extra).status_code == 422


def test_unavailable_signal_threshold():
    row = pd.Series({"collection_timestamp": pd.Timestamp.now(tz="UTC"), "source_type": "demo", "currency": "INR", "effective_price": 100})
    with pytest.raises(service.PredictionError, match="three observed"):
        service.validate_row(row)
