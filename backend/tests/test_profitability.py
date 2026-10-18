import uuid
import pytest
from tests.accounts import grant_role
from app.services.profitability_service import (
    compute_channel_profitability,
    generate_scenarios,
    DEFAULT_FEES,
)


@pytest.fixture
def auth_headers(client):
    email = f"seller_{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": "marketpulse1"}
    )
    assert response.status_code == 201
    grant_role(response.json()["user"]["id"], role="operator")
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_channel_profitability_calculation():
    # Cost price 2000, Selling price 2999, Demand 50
    result = compute_channel_profitability(
        platform="flipkart",
        cost_price=2000.0,
        selling_price=2999.0,
        expected_demand=50,
        target_margin_pct=15.0,
    )
    assert result.platform == "flipkart"
    assert result.selling_price == 2999.0
    assert result.cost_price == 2000.0
    assert result.expected_demand == 50
    assert result.referral_fee > 0
    assert result.closing_fee == 20.0
    assert result.logistics_fee == 48.0
    assert result.net_profit_per_unit > 0
    assert result.margin_pct > 0
    assert result.total_revenue == round(2999.0 * 50, 2)
    assert result.total_profit > 0
    assert result.min_selling_price_for_target > 2000.0


def test_profitability_with_custom_fee_overrides():
    custom_fees = {
        "referral_fee_pct": 5.0,
        "closing_fee": 10.0,
        "logistics_base": 30.0,
    }
    result = compute_channel_profitability(
        platform="amazon",
        cost_price=1000.0,
        selling_price=1500.0,
        expected_demand=10,
        fee_overrides=custom_fees,
    )
    assert result.fee_assumptions["referral_fee_pct"] == 5.0
    assert result.referral_fee == 75.0
    assert result.closing_fee == 10.0
    assert result.logistics_fee == 30.0


def test_scenario_generation():
    scenarios = generate_scenarios(
        cost_price=1000.0,
        base_selling_price=1500.0,
        base_demand=100.0,
        platform="amazon",
    )
    assert len(scenarios) == 3
    names = [s.name for s in scenarios]
    assert names == ["Conservative", "Base", "Optimistic"]

    cons = scenarios[0]
    base = scenarios[1]
    opt = scenarios[2]

    assert cons.projected_units < base.projected_units < opt.projected_units
    assert cons.projected_revenue < base.projected_revenue < opt.projected_revenue
    assert cons.projected_profit < base.projected_profit < opt.projected_profit


def test_profitability_api_endpoint(client, auth_headers):
    payload = {
        "cost_price": 1200.0,
        "selling_price": 1899.0,
        "available_inventory": 80,
        "desired_margin_pct": 18.0,
        "platforms": ["amazon", "flipkart", "croma", "alibaba"],
    }
    res = client.post("/profitability/analyze", headers=auth_headers, json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["cost_price"] == 1200.0
    assert len(data["channels"]) == 4
    assert data["best_channel_by_profit"] in ["amazon", "flipkart", "croma", "alibaba"]
    assert len(data["scenarios_for_recommended"]) == 3
