"""Phase 5 tests: cleaning, normalization, feature engineering and the API.

Feature engineering is deterministic, so most of this is exact-value assertion
against hand-built frames. The 480-row demo fixture is used for the
integration-level checks.
"""

import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.ml import features as feature_module
from app.ml.dataset_builder import (
    DatasetFilters,
    InsufficientDataError,
    build_dataset,
    clean,
    deduplicate,
    normalize,
)
from app.ml.normalization import (
    availability_state,
    normalize_category,
    normalize_platform,
    product_key,
)
from app.models.enums import SourceType
from app.services import dataset_service

BASE = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def clean_snapshots(db_session):
    """Start from an empty snapshot table.

    The test database is session-scoped, so earlier modules leave live and
    imported rows behind. A dataset test asserting "only demo rows exist" needs
    to control what is there.
    """
    from app.models import MarketplaceSnapshot

    db_session.query(MarketplaceSnapshot).delete()
    db_session.commit()
    yield
    db_session.query(MarketplaceSnapshot).delete()
    db_session.commit()


@pytest.fixture
def auth_headers(client):
    email = f"dataset_{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": "marketpulse1"}
    )
    assert response.status_code == 201, response.text
    from tests.accounts import grant_role
    grant_role(response.json()["user"]["id"])
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def raw_row(**overrides):
    row = {
        "id": 1,
        "platform": "amazon",
        "source_type": "demo",
        "search_query": "earbuds",
        "product_name": "Acme Buds Pro",
        "brand": "Acme",
        "category": "wireless earbuds",
        "subcategory": "audio",
        "external_id": "A1",
        "price": 2000.0,
        "original_price": 4000.0,
        "discount_percentage": 50.0,
        "currency": "INR",
        "rating": 4.2,
        "review_count": 100,
        "availability": "In Stock",
        "seller_name": "Seller",
        "collection_timestamp": BASE,
    }
    row.update(overrides)
    return row


def raw_frame(rows):
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Amazon", "amazon"),
        ("AMAZON", "amazon"),
        ("  amazon.in ", "amazon"),
        ("Flipkart.com", "flipkart"),
        ("Tata Croma", "croma"),
        ("ALI BABA", "alibaba"),
        (None, None),
        ("", None),
    ],
)
def test_platform_normalization(value, expected):
    assert normalize_platform(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Wireless Earbuds", "wireless earbuds"),
        ("earbuds", "wireless earbuds"),
        ("TWS", "wireless earbuds"),
        ("In-Ear Headphones", "wireless earbuds"),
        ("Power Bank", "power banks"),
        ("Mouse", "mice"),
        # No rule: cleaned but not merged, rather than guessed at.
        ("Drone Accessories", "drone accessories"),
    ],
)
def test_category_normalization(value, expected):
    assert normalize_category(value) == expected


def test_product_key_is_conservative():
    a = product_key("Acme Buds Pro (Black)", "Acme", "wireless earbuds")
    b = product_key("Acme Buds Pro - Black", "acme", "Earbuds")
    assert a == b, "punctuation and casing must not split one product"

    # A different brand is a different product, even with the same name.
    assert a != product_key("Acme Buds Pro (Black)", "Nova", "wireless earbuds")
    assert product_key("", "Acme", "earbuds") is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("In Stock", 1),
        ("Only a few left", 1),
        ("Out of Stock", 0),
        ("Currently unavailable", 0),
        ("Ships in 3 weeks", None),  # unrecognised: no guess
        (None, None),
    ],
)
def test_availability_state(value, expected):
    assert availability_state(value) == expected


# --------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------


def test_rows_missing_essential_fields_are_dropped():
    frame = raw_frame(
        [
            raw_row(id=1),
            raw_row(id=2, product_name="   "),
            raw_row(id=3, platform="ebay"),
            raw_row(id=4, collection_timestamp="not-a-date"),
            raw_row(id=5, price=None, original_price=None),
        ]
    )

    cleaned, reasons = clean(frame)

    assert len(cleaned) == 1
    assert reasons["missing_product_name"] == 1
    assert reasons["unknown_platform"] == 1
    assert reasons["invalid_timestamp"] == 1
    assert reasons["no_usable_price"] == 1


def test_bad_values_clear_the_field_but_keep_the_row():
    frame = raw_frame(
        [
            raw_row(id=1, rating=9.9),
            raw_row(id=2, review_count=-5),
            raw_row(id=3, price=-100.0),
        ]
    )

    cleaned, reasons = clean(frame)

    # All three rows survive: one bad field is not an unusable observation.
    assert len(cleaned) == 3
    assert cleaned["rating"].isna().sum() == 1
    assert cleaned["review_count"].isna().sum() == 1
    assert reasons["cleared_invalid_rating"] == 1
    assert reasons["cleared_negative_review_count"] == 1
    assert reasons["cleared_negative_price"] == 1


def test_malformed_numbers_become_null_not_zero():
    frame = raw_frame([raw_row(id=1, rating="not-a-number", review_count="many")])
    cleaned, _ = clean(frame)

    assert pd.isna(cleaned.iloc[0]["rating"])
    assert pd.isna(cleaned.iloc[0]["review_count"])


def test_empty_strings_become_null():
    frame = raw_frame([raw_row(id=1, brand="   ", seller_name="")])
    cleaned, _ = clean(frame)

    assert cleaned.iloc[0]["brand"] is None
    assert cleaned.iloc[0]["seller_name"] is None


def test_duplicate_observations_are_removed():
    frame = normalize(
        clean(
            raw_frame(
                [
                    raw_row(id=1),
                    raw_row(id=2),  # same listing, same instant
                    raw_row(id=3, collection_timestamp=BASE + timedelta(days=1)),
                ]
            )
        )[0]
    )

    deduped, removed = deduplicate(frame)

    assert removed == 1
    assert len(deduped) == 2, "a different date is a different observation"


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------


def series(days: int, **overrides) -> pd.DataFrame:
    """A single listing observed over consecutive days."""
    rows = []
    for day in range(days):
        row = raw_row(id=day + 1, collection_timestamp=BASE + timedelta(days=day))
        for key, values in overrides.items():
            row[key] = values[day]
        rows.append(row)
    cleaned, _ = clean(raw_frame(rows))
    return normalize(cleaned)


def test_basic_features():
    frame = feature_module.build_features(series(1))
    row = frame.iloc[0]

    assert row["effective_price"] == 2000.0
    assert row["discount_amount"] == 2000.0
    assert row["discount_percentage"] == 50.0
    assert bool(row["has_discount"]) is True
    assert row["price_to_original_ratio"] == 0.5


def test_price_change_features():
    frame = feature_module.build_features(
        series(3, price=[1000.0, 900.0, 990.0])
    ).sort_values("collection_timestamp")

    first, second, third = frame.iloc[0], frame.iloc[1], frame.iloc[2]

    # No prior observation exists, so these are unknown -- not zero.
    assert pd.isna(first["previous_price"])
    assert pd.isna(first["price_change_absolute"])
    assert pd.isna(first["price_change_percentage"])

    assert second["previous_price"] == 1000.0
    assert second["price_change_absolute"] == -100.0
    assert second["price_change_percentage"] == pytest.approx(-10.0)

    assert third["price_change_absolute"] == pytest.approx(90.0)
    assert third["price_change_percentage"] == pytest.approx(10.0)


def test_review_growth_features():
    frame = feature_module.build_features(
        series(3, review_count=[100, 150, 150])
    ).sort_values("collection_timestamp")

    assert pd.isna(frame.iloc[0]["review_growth"])
    assert frame.iloc[1]["review_growth"] == 50
    assert frame.iloc[1]["review_growth_percentage"] == pytest.approx(50.0)
    # A genuine zero: reviews really did not move between these observations.
    assert frame.iloc[2]["review_growth"] == 0


def test_rating_and_availability_change():
    frame = feature_module.build_features(
        series(
            2,
            rating=[4.0, 4.5],
            availability=["In Stock", "Out of Stock"],
        )
    ).sort_values("collection_timestamp")

    assert frame.iloc[1]["rating_change"] == pytest.approx(0.5)
    assert frame.iloc[1]["availability_change"] == -1


def test_trend_features_need_a_minimum_history():
    two = feature_module.build_features(series(2, price=[1000.0, 900.0]))
    assert two["short_term_price_trend"].isna().all(), (
        "two points is not a trend"
    )

    three = feature_module.build_features(
        series(3, price=[1000.0, 900.0, 800.0])
    ).sort_values("collection_timestamp")
    # Falling 100 per step.
    assert three.iloc[2]["short_term_price_trend"] == pytest.approx(-100.0)


def test_trend_features_do_not_look_ahead():
    frame = feature_module.build_features(
        series(4, price=[1000.0, 1000.0, 1000.0, 1.0])
    ).sort_values("collection_timestamp")

    # The third row must not know about the crash that follows it.
    assert frame.iloc[2]["short_term_price_trend"] == pytest.approx(0.0)
    assert frame.iloc[3]["short_term_price_trend"] < 0


def test_market_features_compare_within_a_category_and_date():
    rows = [
        raw_row(id=1, platform="amazon", product_name="A", price=1000.0),
        raw_row(id=2, platform="flipkart", product_name="B", price=2000.0),
        raw_row(id=3, platform="croma", product_name="C", price=3000.0),
    ]
    cleaned, _ = clean(raw_frame(rows))
    frame = feature_module.build_features(normalize(cleaned))

    assert (frame["listing_count_for_keyword"] == 3).all()
    assert frame["average_market_price"].iloc[0] == pytest.approx(2000.0)
    assert frame["median_market_price"].iloc[0] == pytest.approx(2000.0)

    cheapest = frame[frame["product_name"] == "A"].iloc[0]
    assert cheapest["price_vs_market_average"] == pytest.approx(0.5)
    # Three platforms, one listing each.
    assert cheapest["platform_listing_density"] == pytest.approx(1 / 3)


def test_competition_score_is_deterministic_and_bounded():
    rows = [
        raw_row(id=i, platform="amazon", product_name=f"P{i}", price=1000.0 + i)
        for i in range(1, 11)
    ]
    cleaned, _ = clean(raw_frame(rows))
    frame = feature_module.build_features(normalize(cleaned))

    scores = frame["competition_score"].dropna()
    assert len(scores) == 10
    assert scores.between(0, 100).all()

    # Same input, same output.
    again = feature_module.build_features(normalize(clean(raw_frame(rows))[0]))
    pd.testing.assert_series_equal(
        frame["competition_score"], again["competition_score"]
    )


def test_features_are_null_not_zero_when_inputs_are_missing():
    frame = feature_module.build_features(
        normalize(clean(raw_frame([raw_row(id=1, original_price=None, rating=None)]))[0])
    )
    row = frame.iloc[0]

    assert pd.isna(row["discount_amount"])
    assert pd.isna(row["price_to_original_ratio"])
    assert pd.isna(row["rating"])
    # effective_price still resolves from the selling price.
    assert row["effective_price"] == 2000.0


# --------------------------------------------------------------------------
# Build + metadata
# --------------------------------------------------------------------------


def test_build_on_the_demo_dataset(client, auth_headers, db_session, clean_snapshots):
    client.post("/data/demo/load", headers=auth_headers)

    result = build_dataset(db_session, DatasetFilters())
    meta = result.metadata

    assert meta.total_output_rows > 0
    assert meta.total_input_rows == meta.total_output_rows + meta.removed_rows
    assert meta.source_types == ["demo"]
    assert meta.demo_only is True
    assert meta.contains_demo_data is True
    assert meta.feature_count == len(meta.feature_names)
    assert set(meta.platforms) <= {"amazon", "flipkart", "croma", "alibaba"}
    assert meta.date_range["start"] and meta.date_range["end"]


def test_source_type_filtering_does_not_mix(client, auth_headers, db_session, clean_snapshots):
    client.post("/data/demo/load", headers=auth_headers)

    result = build_dataset(
        db_session, DatasetFilters(source_types=[SourceType.DEMO])
    )
    assert set(result.frame["source_type"].unique()) == {"demo"}

    # No live rows exist, so a live-only build must report that, not fall back.
    with pytest.raises(InsufficientDataError):
        build_dataset(db_session, DatasetFilters(source_types=[SourceType.LIVE]))


def test_platform_filtering(client, auth_headers, db_session, clean_snapshots):
    client.post("/data/demo/load", headers=auth_headers)

    result = build_dataset(db_session, DatasetFilters(platforms=["amazon"]))
    assert set(result.frame["platform"].unique()) == {"amazon"}


def test_empty_filters_raise_insufficient_data(db_session):
    with pytest.raises(InsufficientDataError) as exc:
        build_dataset(db_session, DatasetFilters(keyword="zzz-nothing-matches"))
    assert "no marketplace records" in str(exc.value).lower()


def test_single_observation_yields_null_history(db_session, client, auth_headers, clean_snapshots):
    client.post("/data/demo/load", headers=auth_headers)

    result = build_dataset(db_session, DatasetFilters())
    first = result.frame[result.frame["observation_index"] == 0]

    assert len(first) > 0
    assert first["price_change_absolute"].isna().all()
    assert first["short_term_price_trend"].isna().all()


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/ml/dataset/build"),
        ("get", "/ml/dataset/status"),
        ("get", "/ml/dataset/preview"),
    ],
)
def test_dataset_endpoints_require_authentication(client, method, path):
    response = (
        client.post(path, json={}) if method == "post" else client.get(path)
    )
    assert response.status_code == 401


def test_build_endpoint(client, auth_headers, clean_snapshots):
    client.post("/data/demo/load", headers=auth_headers)

    response = client.post(
        "/ml/dataset/build",
        headers=auth_headers,
        json={"source_types": ["DEMO"], "persist": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["rows"] > 0
    assert body["features"] > 0
    assert body["source_types"] == ["demo"]
    # The demo warning must always be present, never suppressed.
    assert body["notice"] == (
        "Dataset contains DEMO records and is intended for development/testing."
    )
    assert body["metadata"]["demo_only"] is True


def test_build_endpoint_accepts_lowercase_source_types(client, auth_headers):
    client.post("/data/demo/load", headers=auth_headers)
    response = client.post(
        "/ml/dataset/build", headers=auth_headers, json={"source_types": ["demo"]}
    )
    assert response.status_code == 200


def test_build_endpoint_reports_insufficient_data(client, auth_headers):
    response = client.post(
        "/ml/dataset/build",
        headers=auth_headers,
        json={"keyword": "nothing-matches-this-at-all"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "insufficient_data"
    assert detail["reason"]


def test_status_and_preview(client, auth_headers):
    client.post("/data/demo/load", headers=auth_headers)
    built = client.post(
        "/ml/dataset/build", headers=auth_headers, json={"persist": True}
    ).json()

    status_body = client.get("/ml/dataset/status", headers=auth_headers).json()
    assert status_body["has_dataset"] is True
    assert status_body["latest"]["dataset_id"] == built["dataset_id"]
    assert status_body["available_features"]
    assert status_body["notice"]

    preview = client.get(
        "/ml/dataset/preview?limit=5", headers=auth_headers
    ).json()
    assert len(preview["rows"]) == 5
    assert "effective_price" in preview["columns"]
    assert preview["notice"]
    # NaN is not valid JSON; missing values must come back as null.
    assert all(
        row["price_change_absolute"] is None
        for row in preview["rows"]
        if row["observation_index"] == 0
    )


def test_preview_without_a_dataset_is_a_clean_404(client, auth_headers, monkeypatch):
    monkeypatch.setattr(dataset_service, "list_datasets", lambda: [])
    response = client.get("/ml/dataset/preview", headers=auth_headers)
    assert response.status_code == 404


def test_build_does_not_overwrite_previous_datasets(client, auth_headers):
    client.post("/data/demo/load", headers=auth_headers)

    first = client.post(
        "/ml/dataset/build", headers=auth_headers, json={"persist": True}
    ).json()
    second = client.post(
        "/ml/dataset/build", headers=auth_headers, json={"persist": True}
    ).json()

    assert first["dataset_id"] != second["dataset_id"]
    ids = {d["dataset_id"] for d in dataset_service.list_datasets()}
    assert {first["dataset_id"], second["dataset_id"]} <= ids


def test_persist_false_builds_without_writing(client, auth_headers):
    client.post("/data/demo/load", headers=auth_headers)
    before = len(dataset_service.list_datasets())

    body = client.post(
        "/ml/dataset/build", headers=auth_headers, json={"persist": False}
    ).json()

    assert body["rows"] > 0
    assert body["metadata"]["csv_path"] is None
    assert len(dataset_service.list_datasets()) == before
