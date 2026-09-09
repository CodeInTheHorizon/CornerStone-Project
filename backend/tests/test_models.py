"""Phase 1 schema tests: the four models are registered and persistable."""

from datetime import datetime, timezone

import pytest

from app.database import Base, SessionLocal
from app.models import (
    DataSource,
    MarketplaceSnapshot,
    ModelMetadata,
    Platform,
    Prediction,
    User,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_all_expected_tables_are_registered():
    assert {
        "users",
        "marketplace_snapshots",
        "predictions",
        "model_metadata",
    } <= set(Base.metadata.tables)


def test_user_and_prediction_round_trip(db):
    user = User(
        email="phase1@example.com",
        full_name="Phase One",
        hashed_password="not-a-real-hash",
    )
    db.add(user)
    db.flush()

    prediction = Prediction(
        user_id=user.id,
        product_name="65W GaN Charger",
        category="chargers",
        opportunity_scores={"amazon": 82, "flipkart": 76},
        key_factors=["price_attractiveness", "review_momentum"],
    )
    db.add(prediction)
    db.flush()

    assert prediction.id is not None
    assert user.predictions == [prediction]
    # JSON columns survive the round trip.
    assert prediction.opportunity_scores["amazon"] == 82


def test_snapshot_defaults_mark_provenance(db):
    snapshot = MarketplaceSnapshot(
        platform=Platform.AMAZON.value,
        product_name="USB-C Cable 1m",
        price=499.0,
    )
    db.add(snapshot)
    db.flush()

    # Provenance and observation time must always be populated.
    assert snapshot.source == DataSource.LIVE.value
    assert snapshot.currency == "INR"
    assert isinstance(snapshot.collection_timestamp, datetime)


def test_model_metadata_metrics_default_to_null(db):
    meta = ModelMetadata(model_name="baseline", model_version="v0")
    db.add(meta)
    db.flush()

    # Metrics stay NULL until a real evaluation has run -- never seeded.
    assert meta.accuracy is None
    assert meta.f1_score is None
    assert meta.is_active is False
    assert meta.status == "pending"
    assert meta.trained_at is None or isinstance(meta.trained_at, datetime)
