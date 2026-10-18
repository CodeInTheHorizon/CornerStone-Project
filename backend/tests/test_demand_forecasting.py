"""Tests for demand forecasting models, public dataset loader, and seller data loader."""

from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from app.ml.public_dataset_loader import load_public_dataset, DatasetValidationError
from app.ml.seller_data_loader import parse_and_validate_seller_data, SellerDataValidationError
from app.ml.demand_forecasting import (
    train_demand_models,
    calculate_metrics,
    chronological_split,
)


def test_public_dataset_loader():
    dataset_path = Path(__file__).resolve().parents[2] / "data/historical/ecommerce_demand_dataset.csv"
    assert dataset_path.exists(), "Benchmark dataset must exist."

    df, meta = load_public_dataset(dataset_path)
    assert not df.empty
    assert meta["source_type"] == "public_dataset"
    assert "units_sold" in df.columns
    assert df["units_sold"].min() >= 0
    assert "platform" in df.columns
    assert set(meta["platforms"]) == {"amazon", "flipkart", "meesho"}


def test_public_dataset_rejects_missing_sales():
    bad_df = pd.DataFrame({
        "date": ["2026-09-01"],
        "product_id": ["p1"],
        "category": ["electronics"],
        "platform": ["amazon"],
        "price": [100.0],
        # units_sold is missing!
    })
    tmp_file = Path("test_bad.csv")
    bad_df.to_csv(tmp_file, index=False)
    try:
        with pytest.raises(DatasetValidationError) as exc:
            load_public_dataset(tmp_file)
        assert "missing required columns" in str(exc.value).lower()
    finally:
        if tmp_file.exists():
            tmp_file.unlink()


def test_seller_data_loader():
    seller_df = pd.DataFrame({
        "date": ["2026-09-01", "2026-09-02"],
        "product": ["Galaxy A56", "Galaxy A56"],
        "category": ["smartphones", "smartphones"],
        "platform": ["flipkart", "flipkart"],
        "selling_price": [28999.0, 28499.0],
        "units_sold": [15, 22],
        "discount": [10.0, 12.0],
    })
    df, meta = parse_and_validate_seller_data(seller_df, seller_id="seller_123")
    assert len(df) == 2
    assert meta["source_type"] == "seller_data"
    assert meta["total_units_sold"] == 37


def test_chronological_split_no_leakage():
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "units_sold": range(10),
    })
    train, val, desc = chronological_split(df, val_fraction=0.3)
    assert train["date"].max() < val["date"].min()
    assert len(val) >= 2


def test_train_demand_models():
    dataset_path = Path(__file__).resolve().parents[2] / "data/historical/ecommerce_demand_dataset.csv"
    df, _ = load_public_dataset(dataset_path)

    test_art_dir = Path(__file__).resolve().parent / "test_artifacts"
    test_art_dir.mkdir(parents=True, exist_ok=True)
    try:
        outcome = train_demand_models(df, val_fraction=0.2, artifact_dir=test_art_dir)

        assert outcome.training_rows > 0
        assert outcome.validation_rows > 0
        assert len(outcome.all_results) >= 2

        # Check metrics
        selected = outcome.selected_model
        assert "mae" in selected.metrics
        assert "rmse" in selected.metrics
        assert "wape" in selected.metrics
        assert selected.metrics["wape"] <= 1.0
        assert (test_art_dir / "demand_forecast_model.pkl").exists()
    finally:
        import shutil
        if test_art_dir.exists():
            shutil.rmtree(test_art_dir, ignore_errors=True)
