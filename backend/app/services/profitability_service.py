"""Profitability Engine for Marketplace Channels.

Computes revenue, COGS, marketplace fee deductions, logistics/shipping costs,
net margins, ROI, break-even thresholds, and 3-scenario sensitivity analysis.
All fee structures are configurable and transparently exposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Default fee structures for electronics category in INR
DEFAULT_FEES: dict[str, dict[str, float]] = {
    "amazon": {
        "referral_fee_pct": 9.5,       # 9.5% referral fee for electronics
        "closing_fee": 25.0,           # Fixed closing fee
        "logistics_base": 55.0,        # Standard domestic shipping & handling
        "payment_processing_pct": 2.0, # Payment gateway / COD fee
    },
    "flipkart": {
        "referral_fee_pct": 8.5,       # 8.5% electronics referral fee
        "closing_fee": 20.0,           # Fixed closing fee
        "logistics_base": 48.0,        # Standard shipping fee
        "payment_processing_pct": 1.8, # Payment gateway
    },
    "croma": {
        "referral_fee_pct": 7.0,       # 7.0% marketplace commission
        "closing_fee": 15.0,           # Closing fee
        "logistics_base": 65.0,        # Logistics fulfillment
        "payment_processing_pct": 2.0, # Payment gateway
    },
    "alibaba": {
        "referral_fee_pct": 3.0,       # Wholesale trade assurance fee
        "closing_fee": 0.0,            # No retail closing fee
        "logistics_base": 180.0,       # International / bulk freight per unit equivalent
        "payment_processing_pct": 2.5, # Cross-border wire/escrow processing
    },
    "meesho": {
        "referral_fee_pct": 1.5,       # Zero/low commission reseller fee
        "closing_fee": 0.0,            # Zero closing fee
        "logistics_base": 42.0,        # Lightweight logistics
        "payment_processing_pct": 1.5, # Payment gateway
    },
}


@dataclass
class ChannelProfitability:
    platform: str
    selling_price: float
    cost_price: float
    expected_demand: float
    referral_fee: float
    closing_fee: float
    logistics_fee: float
    payment_fee: float
    total_fee_per_unit: float
    net_profit_per_unit: float
    margin_pct: float
    roi_pct: float
    total_revenue: float
    total_cogs: float
    total_profit: float
    break_even_units: int
    min_selling_price_for_target: float
    fee_assumptions: dict[str, float]


@dataclass
class ScenarioOutcome:
    name: str  # "conservative", "base", "optimistic"
    demand_multiplier: float
    price_delta_pct: float
    projected_units: int
    projected_revenue: float
    projected_profit: float
    projected_margin_pct: float


def compute_channel_profitability(
    *,
    platform: str,
    cost_price: float,
    selling_price: float,
    expected_demand: float = 50.0,
    target_margin_pct: float = 15.0,
    fixed_overhead: float = 0.0,
    fee_overrides: dict[str, float] | None = None,
) -> ChannelProfitability:
    """Compute detailed unit and batch profitability for a specific marketplace channel."""
    cost_price = max(0.01, float(cost_price))
    selling_price = max(cost_price, float(selling_price))
    expected_demand = max(0.0, float(expected_demand))

    fees = dict(DEFAULT_FEES.get(platform.lower(), DEFAULT_FEES["amazon"]))
    if fee_overrides:
        fees.update(fee_overrides)

    ref_pct = fees.get("referral_fee_pct", 9.0)
    closing = fees.get("closing_fee", 20.0)
    logistics = fees.get("logistics_base", 50.0)
    pay_pct = fees.get("payment_processing_pct", 2.0)

    referral_fee = round(selling_price * (ref_pct / 100.0), 2)
    payment_fee = round(selling_price * (pay_pct / 100.0), 2)
    total_fee_per_unit = round(referral_fee + closing + logistics + payment_fee, 2)

    total_cost_per_unit = round(cost_price + total_fee_per_unit, 2)
    net_profit_per_unit = round(selling_price - total_cost_per_unit, 2)

    margin_pct = round((net_profit_per_unit / selling_price) * 100.0, 2) if selling_price > 0 else 0.0
    roi_pct = round((net_profit_per_unit / cost_price) * 100.0, 2) if cost_price > 0 else 0.0

    total_revenue = round(selling_price * expected_demand, 2)
    total_cogs = round(cost_price * expected_demand, 2)
    total_profit = round(net_profit_per_unit * expected_demand - fixed_overhead, 2)

    # Break-even units to cover fixed overhead
    if net_profit_per_unit > 0:
        break_even_units = int((fixed_overhead + net_profit_per_unit - 0.001) // net_profit_per_unit) if fixed_overhead > 0 else 1
    else:
        break_even_units = 999999

    # Minimum selling price required to hit target margin
    # SP = (CP + closing + logistics) / (1 - (target_margin_pct + ref_pct + pay_pct)/100)
    deduction_pct = (target_margin_pct + ref_pct + pay_pct) / 100.0
    if deduction_pct < 0.95:
        min_sp = round((cost_price + closing + logistics) / (1.0 - deduction_pct), 2)
    else:
        min_sp = round(cost_price * 1.5, 2)

    return ChannelProfitability(
        platform=platform,
        selling_price=selling_price,
        cost_price=cost_price,
        expected_demand=expected_demand,
        referral_fee=referral_fee,
        closing_fee=closing,
        logistics_fee=logistics,
        payment_fee=payment_fee,
        total_fee_per_unit=total_fee_per_unit,
        net_profit_per_unit=net_profit_per_unit,
        margin_pct=margin_pct,
        roi_pct=roi_pct,
        total_revenue=total_revenue,
        total_cogs=total_cogs,
        total_profit=total_profit,
        break_even_units=break_even_units,
        min_selling_price_for_target=min_sp,
        fee_assumptions={
            "referral_fee_pct": ref_pct,
            "closing_fee": closing,
            "logistics_fee": logistics,
            "payment_processing_pct": pay_pct,
        },
    )


def generate_scenarios(
    *,
    cost_price: float,
    base_selling_price: float,
    base_demand: float,
    platform: str = "flipkart",
    fee_overrides: dict[str, float] | None = None,
) -> list[ScenarioOutcome]:
    """Generate Conservative (-30% demand, -5% price), Base, and Optimistic (+30% demand, +5% price) scenarios."""
    configs = [
        ("Conservative", 0.70, -0.05),
        ("Base", 1.00, 0.0),
        ("Optimistic", 1.30, 0.05),
    ]
    outcomes: list[ScenarioOutcome] = []
    for name, dem_mult, price_mult in configs:
        sp = round(base_selling_price * (1.0 + price_mult), 2)
        dem = max(1, int(round(base_demand * dem_mult)))
        calc = compute_channel_profitability(
            platform=platform,
            cost_price=cost_price,
            selling_price=sp,
            expected_demand=float(dem),
            fee_overrides=fee_overrides,
        )
        outcomes.append(
            ScenarioOutcome(
                name=name,
                demand_multiplier=dem_mult,
                price_delta_pct=round(price_mult * 100, 1),
                projected_units=dem,
                projected_revenue=calc.total_revenue,
                projected_profit=calc.total_profit,
                projected_margin_pct=calc.margin_pct,
            )
        )
    return outcomes
