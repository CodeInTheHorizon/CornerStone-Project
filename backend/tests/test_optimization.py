import uuid
import pytest
from tests.accounts import grant_role
from app.services.optimization_service import (
    ChannelCandidate,
    optimize_inventory_allocation,
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


def test_optimization_solver_basic():
    candidates = [
        ChannelCandidate(
            platform="flipkart",
            selling_price=3000.0,
            cost_price=2000.0,
            expected_demand=60,
            net_profit_per_unit=600.0,
            margin_pct=20.0,
        ),
        ChannelCandidate(
            platform="amazon",
            selling_price=2800.0,
            cost_price=2000.0,
            expected_demand=80,
            net_profit_per_unit=450.0,
            margin_pct=16.0,
        ),
        ChannelCandidate(
            platform="croma",
            selling_price=2700.0,
            cost_price=2000.0,
            expected_demand=40,
            net_profit_per_unit=350.0,
            margin_pct=13.0,
        ),
    ]

    result = optimize_inventory_allocation(
        total_inventory=100,
        candidates=candidates,
        min_margin_pct=15.0,  # Excludes croma (13%)
        max_channel_share=0.70,
    )

    assert result.status in ["optimal", "feasible"]
    assert result.total_allocated <= 100
    assert result.total_allocated > 0
    assert result.total_expected_profit > 0

    # Ensure Croma got 0 units due to margin constraint
    croma_alloc = next((a for a in result.allocations if a.platform == "croma"), None)
    assert croma_alloc is None  # filtered out by min_margin_pct

    # Ensure max channel share constraint respected
    for alloc in result.allocations:
        assert alloc.allocated_units <= 70


def test_optimization_moq_handling():
    candidates = [
        ChannelCandidate(
            platform="alibaba",
            selling_price=1500.0,
            cost_price=1000.0,
            expected_demand=100,
            net_profit_per_unit=350.0,
            margin_pct=23.3,
            min_order_qty=50,  # MOQ is 50
        ),
        ChannelCandidate(
            platform="amazon",
            selling_price=1600.0,
            cost_price=1000.0,
            expected_demand=50,
            net_profit_per_unit=300.0,
            margin_pct=18.7,
            min_order_qty=1,
        ),
    ]

    # Inventory of only 30 units: Alibaba requires MOQ 50, so Alibaba should receive 0
    result = optimize_inventory_allocation(
        total_inventory=30,
        candidates=candidates,
        min_margin_pct=10.0,
        max_channel_share=1.0,
    )

    alibaba_alloc = next(a for a in result.allocations if a.platform == "alibaba")
    assert alibaba_alloc.allocated_units == 0


def test_optimization_infeasible_when_all_submargin():
    candidates = [
        ChannelCandidate(
            platform="amazon",
            selling_price=1100.0,
            cost_price=1050.0,
            expected_demand=50,
            net_profit_per_unit=-20.0,
            margin_pct=-1.8,
        )
    ]
    result = optimize_inventory_allocation(
        total_inventory=50,
        candidates=candidates,
        min_margin_pct=10.0,
    )
    assert result.status == "infeasible"
    assert result.total_allocated == 0
    assert len(result.explanation) > 0


def test_optimization_api_endpoint(client, auth_headers):
    payload = {
        "total_inventory": 120,
        "min_margin_pct": 12.0,
        "max_channel_share": 0.65,
        "channels": [
            {
                "platform": "flipkart",
                "selling_price": 2499.0,
                "cost_price": 1600.0,
                "expected_demand": 70,
                "min_order_qty": 1,
            },
            {
                "platform": "amazon",
                "selling_price": 2599.0,
                "cost_price": 1600.0,
                "expected_demand": 80,
                "min_order_qty": 1,
            },
        ],
    }

    res = client.post("/optimization/allocate", headers=auth_headers, json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["total_inventory"] == 120
    assert data["total_allocated"] <= 120
    assert len(data["allocations"]) == 2
    assert len(data["explanation"]) > 0
    assert len(data["risk_notes"]) > 0
