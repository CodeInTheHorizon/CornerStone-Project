import uuid
import pytest


@pytest.fixture
def auth_headers(client):
    email = f"demand_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "TestPassword123!"
    res = client.post("/auth/register", json={"email": email, "password": pwd, "full_name": "Demand Tester"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_demand_benchmark_endpoint(client, auth_headers):
    response = client.get("/ml/demand/benchmark", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] > 0
    assert "platforms" in data
    assert "total_units_sold" in data


def test_demand_status_endpoint(client, auth_headers):
    response = client.get("/ml/demand/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "benchmark_dataset_available" in data
    assert data["benchmark_dataset_available"] is True


def test_demand_train_endpoint(client, auth_headers):
    response = client.post("/ml/demand/train?val_fraction=0.2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "selected_model" in data
    assert "metrics" in data
    assert data["metrics"]["wape"] <= 1.0


def test_demand_forecast_single_scenario(client, auth_headers):
    payload = {
        "features": {
            "platform": "amazon",
            "category": "wireless earbuds",
            "price": 1999.0,
            "discount_percentage": 25.0,
            "rating": 4.2,
            "review_count": 350.0,
            "review_velocity": 4.5,
            "inventory": 150.0,
        }
    }
    response = client.post("/ml/demand/forecast", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["forecasts"]) == 1
    assert data["forecasts"][0]["predicted_units_sold"] > 0
    assert data["total_projected_units"] > 0
    assert data["total_projected_revenue"] > 0
