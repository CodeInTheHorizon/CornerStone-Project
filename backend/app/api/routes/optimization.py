"""Inventory & Channel Optimization API Endpoints (Checkpoint 10)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.product import Product
from app.models.user import User
from app.services.optimization_service import (
    ChannelCandidate,
    OptimizationResult,
    optimize_inventory_allocation,
)
from app.services.profitability_service import compute_channel_profitability

router = APIRouter(prefix="/optimization", tags=["optimization"])


class CandidateInput(BaseModel):
    platform: str
    selling_price: float = Field(..., gt=0)
    cost_price: float = Field(..., gt=0)
    expected_demand: int = Field(default=50, ge=1)
    min_order_qty: int = Field(default=1, ge=1)


class OptimizationRequest(BaseModel):
    total_inventory: int = Field(..., gt=0, description="Available stock to allocate")
    min_margin_pct: float = Field(default=10.0, ge=0.0, le=80.0)
    max_channel_share: float = Field(default=0.70, ge=0.20, le=1.0)
    product_id: int | None = None
    cost_price: float | None = None
    channels: list[CandidateInput] | None = None


class ChannelAllocationOut(BaseModel):
    platform: str
    allocated_units: int
    share_pct: float
    expected_revenue: float
    expected_profit: float
    unit_margin_pct: float
    rationale: str


class OptimizationResponse(BaseModel):
    total_inventory: int
    total_allocated: int
    unallocated_inventory: int
    total_expected_revenue: float
    total_expected_profit: float
    average_margin_pct: float
    status: str
    allocations: list[ChannelAllocationOut]
    explanation: list[str]
    risk_notes: list[str]


@router.post("/allocate", response_model=OptimizationResponse)
def allocate_inventory(
    payload: OptimizationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Any:
    candidates: list[ChannelCandidate] = []

    # Case A: Explicit channels provided
    if payload.channels:
        for ch in payload.channels:
            calc = compute_channel_profitability(
                platform=ch.platform,
                cost_price=ch.cost_price,
                selling_price=ch.selling_price,
                expected_demand=float(ch.expected_demand),
            )
            candidates.append(
                ChannelCandidate(
                    platform=ch.platform,
                    selling_price=ch.selling_price,
                    cost_price=ch.cost_price,
                    expected_demand=ch.expected_demand,
                    net_profit_per_unit=calc.net_profit_per_unit,
                    margin_pct=calc.margin_pct,
                    min_order_qty=ch.min_order_qty,
                )
            )
    # Case B: Derive from product_id
    elif payload.product_id:
        product = db.get(Product, payload.product_id)
        if not product or not product.listings:
            raise HTTPException(status_code=404, detail="Product not found or has no marketplace listings.")

        cp = payload.cost_price or 1000.0  # default fallback if not given
        for l in product.listings:
            sp = l.price_current if (l.price_current and l.price_current > 0) else cp * 1.3
            dem = 40 if l.in_stock else 15
            calc = compute_channel_profitability(
                platform=l.platform,
                cost_price=cp,
                selling_price=sp,
                expected_demand=float(dem),
            )
            candidates.append(
                ChannelCandidate(
                    platform=l.platform,
                    selling_price=sp,
                    cost_price=cp,
                    expected_demand=dem,
                    net_profit_per_unit=calc.net_profit_per_unit,
                    margin_pct=calc.margin_pct,
                    min_order_qty=l.min_order_qty or 1,
                )
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a candidate channels list or a product_id.",
        )

    result = optimize_inventory_allocation(
        total_inventory=payload.total_inventory,
        candidates=candidates,
        min_margin_pct=payload.min_margin_pct,
        max_channel_share=payload.max_channel_share,
    )

    return OptimizationResponse(
        total_inventory=result.total_inventory,
        total_allocated=result.total_allocated,
        unallocated_inventory=result.unallocated_inventory,
        total_expected_revenue=result.total_expected_revenue,
        total_expected_profit=result.total_expected_profit,
        average_margin_pct=result.average_margin_pct,
        status=result.status,
        allocations=[
            ChannelAllocationOut(
                platform=a.platform,
                allocated_units=a.allocated_units,
                share_pct=a.share_pct,
                expected_revenue=a.expected_revenue,
                expected_profit=a.expected_profit,
                unit_margin_pct=a.unit_margin_pct,
                rationale=a.rationale,
            )
            for a in result.allocations
        ],
        explanation=result.explanation,
        risk_notes=result.risk_notes,
    )
