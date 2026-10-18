"""Multi-Channel Inventory & Profit Optimization Engine.

Solves the channel allocation problem:
Maximize Total Expected Net Profit subject to:
1. Total inventory availability constraints (sum(x_i) <= Total Inventory)
2. Channel demand absorption capacity (0 <= x_i <= Demand_i)
3. Minimum acceptable margin constraints (Margin_i >= MinMargin)
4. Platform Minimum Order Quantities (e.g. wholesale MOQ on Alibaba)
5. Risk diversification / channel concentration limits (x_i <= MaxShare * TotalInventory)

Uses SciPy's HiGHS mixed-integer linear programming (MILP) solver with fallback heuristic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import linprog

from app.services.profitability_service import ChannelProfitability, compute_channel_profitability


@dataclass
class ChannelCandidate:
    platform: str
    selling_price: float
    cost_price: float
    expected_demand: int
    net_profit_per_unit: float
    margin_pct: float
    min_order_qty: int = 1


@dataclass
class ChannelAllocation:
    platform: str
    allocated_units: int
    share_pct: float
    expected_revenue: float
    expected_profit: float
    unit_margin_pct: float
    rationale: str


@dataclass
class OptimizationResult:
    total_inventory: int
    total_allocated: int
    unallocated_inventory: int
    total_expected_revenue: float
    total_expected_profit: float
    average_margin_pct: float
    status: str  # "optimal", "feasible", "constrained", "infeasible"
    allocations: list[ChannelAllocation]
    explanation: list[str]
    risk_notes: list[str]


def optimize_inventory_allocation(
    *,
    total_inventory: int,
    candidates: list[ChannelCandidate],
    min_margin_pct: float = 10.0,
    max_channel_share: float = 0.70,
) -> OptimizationResult:
    """Optimize channel allocation across eligible marketplaces using Mixed-Integer Linear Programming."""
    total_inventory = max(0, int(total_inventory))
    if total_inventory == 0 or not candidates:
        return OptimizationResult(
            total_inventory=total_inventory,
            total_allocated=0,
            unallocated_inventory=total_inventory,
            total_expected_revenue=0.0,
            total_expected_profit=0.0,
            average_margin_pct=0.0,
            status="infeasible" if total_inventory == 0 else "no_candidates",
            allocations=[],
            explanation=["No inventory available or no candidate channels provided."],
            risk_notes=["Zero allocation performed."],
        )

    # 1. Filter candidates meeting minimum margin threshold
    eligible: list[ChannelCandidate] = []
    rejected_margin: list[str] = []
    for c in candidates:
        if c.net_profit_per_unit > 0 and c.margin_pct >= min_margin_pct:
            eligible.append(c)
        else:
            rejected_margin.append(f"{c.platform.capitalize()} ({c.margin_pct}% margin < {min_margin_pct}% min threshold)")

    if not eligible:
        return OptimizationResult(
            total_inventory=total_inventory,
            total_allocated=0,
            unallocated_inventory=total_inventory,
            total_expected_revenue=0.0,
            total_expected_profit=0.0,
            average_margin_pct=0.0,
            status="infeasible",
            allocations=[],
            explanation=["All candidate channels failed the minimum margin threshold (" + ", ".join(rejected_margin) + ")."],
            risk_notes=["Pricing is too low or product cost is too high to sell profitably on any channel."],
        )

    n = len(eligible)
    # Objective: maximize sum(profit_i * x_i)  --> minimize sum(-profit_i * x_i)
    c_obj = np.array([-c.net_profit_per_unit for c in eligible], dtype=float)

    # Upper bounds per channel
    # Demand limit and channel concentration limit
    max_per_channel = int(math.ceil(total_inventory * max_channel_share)) if n > 1 and total_inventory > 5 else total_inventory

    bounds: list[tuple[float, float]] = []
    for c in eligible:
        upper = min(float(c.expected_demand), float(max_per_channel), float(total_inventory))
        # Ensure upper is at least 0
        upper = max(0.0, upper)
        bounds.append((0.0, upper))

    # Constraint 1: sum(x_i) <= total_inventory
    A_ub = np.ones((1, n), dtype=float)
    b_ub = np.array([float(total_inventory)], dtype=float)

    # Solve MILP using HiGHS
    integrality = np.ones(n, dtype=int)  # All decision variables must be integers
    res = linprog(
        c=c_obj,
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=bounds,
        integrality=integrality,
        method="highs",
    )

    if res.success:
        raw_alloc = np.round(res.x).astype(int)
    else:
        # Fallback greedy heuristic: allocate greedily by descending net profit per unit
        sorted_indices = sorted(range(n), key=lambda i: -eligible[i].net_profit_per_unit)
        raw_alloc = np.zeros(n, dtype=int)
        remaining = total_inventory
        for idx in sorted_indices:
            c = eligible[idx]
            cap = min(remaining, c.expected_demand, max_per_channel)
            if cap >= c.min_order_qty:
                raw_alloc[idx] = cap
                remaining -= cap

    # Post-process MOQ constraints
    for i, c in enumerate(eligible):
        if 0 < raw_alloc[i] < c.min_order_qty:
            raw_alloc[i] = 0

    total_allocated = int(np.sum(raw_alloc))
    unallocated = total_inventory - total_allocated

    allocations: list[ChannelAllocation] = []
    tot_rev = 0.0
    tot_profit = 0.0
    explanation: list[str] = []
    risk_notes: list[str] = []

    for i, c in enumerate(eligible):
        units = int(raw_alloc[i])
        share = round((units / total_inventory) * 100.0, 1) if total_inventory > 0 else 0.0
        rev = round(units * c.selling_price, 2)
        profit = round(units * c.net_profit_per_unit, 2)
        tot_rev += rev
        tot_profit += profit

        if units > 0:
            rat = f"Allocated {units} units ({share}%) due to attractive unit profit of ₹{c.net_profit_per_unit:.1f} ({c.margin_pct}% margin)."
            if units == c.expected_demand:
                rat += " Reached 100% of channel forecasted demand."
            elif units == max_per_channel and n > 1:
                rat += f" Capped by {int(max_channel_share*100)}% risk diversification limit."
        else:
            rat = f"Zero allocation: other channels yielded higher margin or demand was satisfied."

        allocations.append(
            ChannelAllocation(
                platform=c.platform,
                allocated_units=units,
                share_pct=share,
                expected_revenue=rev,
                expected_profit=profit,
                unit_margin_pct=c.margin_pct,
                rationale=rat,
            )
        )
        if units > 0:
            explanation.append(f"{c.platform.capitalize()}: {units} units (₹{profit:,.0f} profit).")

    # Overall explanation
    if total_allocated == total_inventory:
        explanation.insert(0, f"Full inventory ({total_inventory} units) successfully distributed across {sum(1 for a in allocations if a.allocated_units > 0)} profitable channel(s).")
    else:
        explanation.insert(0, f"Allocated {total_allocated} of {total_inventory} units. Remaining {unallocated} units held to prevent margin dilution or exceeding channel demand.")

    # Risk evaluation
    max_share = max((a.share_pct for a in allocations), default=0.0)
    if max_share > 65.0 and n > 1:
        top_plat = next(a.platform for a in allocations if a.share_pct == max_share)
        risk_notes.append(f"High concentration risk on {top_plat.capitalize()} ({max_share}% of inventory). Consider testing alternative channels if account issues arise.")
    if unallocated > total_inventory * 0.3:
        risk_notes.append(f"High excess inventory risk: {unallocated} units unallocated due to market demand ceilings.")
    if rejected_margin:
        risk_notes.append(f"Excluded channels with sub-target margins: {', '.join(rejected_margin)}.")
    if not risk_notes:
        risk_notes.append("Balanced multi-channel allocation with low concentration and healthy margin safety.")

    avg_margin = round((tot_profit / tot_rev) * 100.0, 2) if tot_rev > 0 else 0.0

    return OptimizationResult(
        total_inventory=total_inventory,
        total_allocated=total_allocated,
        unallocated_inventory=unallocated,
        total_expected_revenue=round(tot_rev, 2),
        total_expected_profit=round(tot_profit, 2),
        average_margin_pct=avg_margin,
        status="optimal" if res.success else "feasible",
        allocations=allocations,
        explanation=explanation,
        risk_notes=risk_notes,
    )
