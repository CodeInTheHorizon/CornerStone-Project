"""Profitability Analysis API Endpoints (Checkpoint 9)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.product import Product
from app.models.user import User
from app.services.profitability_service import (
    DEFAULT_FEES,
    ChannelProfitability,
    ScenarioOutcome,
    compute_channel_profitability,
    generate_scenarios,
)

router = APIRouter(prefix="/profitability", tags=["profitability"])


class ProfitabilityRequest(BaseModel):
    cost_price: float = Field(..., gt=0, description="Seller unit cost in INR")
    selling_price: float | None = Field(default=None, description="Optional target selling price")
    available_inventory: int = Field(default=100, ge=0)
    desired_margin_pct: float = Field(default=15.0, ge=0.0, le=90.0)
    fixed_overhead: float = Field(default=0.0, ge=0.0)
    platforms: list[str] = Field(default=["amazon", "flipkart", "croma", "alibaba"])
    fee_overrides: dict[str, dict[str, float]] | None = None
    product_id: int | None = None


class ChannelProfitOut(BaseModel):
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


class ScenarioOut(BaseModel):
    name: str
    demand_multiplier: float
    price_delta_pct: float
    projected_units: int
    projected_revenue: float
    projected_profit: float
    projected_margin_pct: float


class ProfitabilityResponse(BaseModel):
    cost_price: float
    desired_margin_pct: float
    channels: list[ChannelProfitOut]
    best_channel_by_profit: str
    best_channel_by_margin: str
    scenarios_for_recommended: list[ScenarioOut]
    fee_transparency_note: str


@router.post("/analyze", response_model=ProfitabilityResponse)
def analyze_profitability(
    payload: ProfitabilityRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Any:
    # If product_id provided, we can pull platform listings to set realistic observed prices
    observed_prices: dict[str, float] = {}
    if payload.product_id:
        product = db.get(Product, payload.product_id)
        if product and product.listings:
            for l in product.listings:
                if l.price_current and l.price_current > 0:
                    observed_prices[l.platform.lower()] = l.price_current

    channels_out: list[ChannelProfitOut] = []
    for plat in payload.platforms:
        p_lower = plat.lower()
        # Selling price: payload override -> observed price -> default markup
        sp = payload.selling_price
        if sp is None:
            sp = observed_prices.get(p_lower, round(payload.cost_price * 1.30, 2))

        overrides = (payload.fee_overrides or {}).get(p_lower)
        calc = compute_channel_profitability(
            platform=p_lower,
            cost_price=payload.cost_price,
            selling_price=sp,
            expected_demand=float(payload.available_inventory),
            target_margin_pct=payload.desired_margin_pct,
            fixed_overhead=payload.fixed_overhead,
            fee_overrides=overrides,
        )
        channels_out.append(
            ChannelProfitOut(
                platform=calc.platform,
                selling_price=calc.selling_price,
                cost_price=calc.cost_price,
                expected_demand=calc.expected_demand,
                referral_fee=calc.referral_fee,
                closing_fee=calc.closing_fee,
                logistics_fee=calc.logistics_fee,
                payment_fee=calc.payment_fee,
                total_fee_per_unit=calc.total_fee_per_unit,
                net_profit_per_unit=calc.net_profit_per_unit,
                margin_pct=calc.margin_pct,
                roi_pct=calc.roi_pct,
                total_revenue=calc.total_revenue,
                total_cogs=calc.total_cogs,
                total_profit=calc.total_profit,
                break_even_units=calc.break_even_units,
                min_selling_price_for_target=calc.min_selling_price_for_target,
                fee_assumptions=calc.fee_assumptions,
            )
        )

    if not channels_out:
        raise HTTPException(status_code=400, detail="No channels evaluated.")

    best_profit = max(channels_out, key=lambda c: c.total_profit).platform
    best_margin = max(channels_out, key=lambda c: c.margin_pct).platform

    # Generate 3 scenarios for the top channel
    recommended_ch = next(c for c in channels_out if c.platform == best_profit)
    scenarios_data = generate_scenarios(
        cost_price=payload.cost_price,
        base_selling_price=recommended_ch.selling_price,
        base_demand=recommended_ch.expected_demand,
        platform=recommended_ch.platform,
    )
    scenarios_out = [
        ScenarioOut(
            name=s.name,
            demand_multiplier=s.demand_multiplier,
            price_delta_pct=s.price_delta_pct,
            projected_units=s.projected_units,
            projected_revenue=s.projected_revenue,
            projected_profit=s.projected_profit,
            projected_margin_pct=s.projected_margin_pct,
        )
        for s in scenarios_data
    ]

    return ProfitabilityResponse(
        cost_price=payload.cost_price,
        desired_margin_pct=payload.desired_margin_pct,
        channels=channels_out,
        best_channel_by_profit=best_profit,
        best_channel_by_margin=best_margin,
        scenarios_for_recommended=scenarios_out,
        fee_transparency_note="Marketplace fees (referral %, closing fees, logistics) are estimated based on published category rate cards and can be customized per seller contract.",
    )
