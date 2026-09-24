"""Opportunity Score API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.opportunity_score import OpportunityScore
from app.models.product import Product
from app.models.user import User
from app.services.scoring import compute_and_store_scores, score_product

router = APIRouter(prefix="/scores", tags=["scores"])


class ScoreComponent(BaseModel):
    raw_value: float | None = None
    normalized: float
    weight: float
    contribution: float


class ScoreOut(BaseModel):
    platform: str
    score: float
    rank: int
    components: dict[str, ScoreComponent] = {}
    explanation: str = ""
    suggested_inventory_share_pct: float = 0.0
    computed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScoreResponse(BaseModel):
    product_id: int
    product_title: str
    scores: list[ScoreOut]


@router.get("/{product_id}", response_model=ScoreResponse)
def get_scores(
    product_id: int,
    recompute: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Any:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if recompute:
        stored = compute_and_store_scores(db, product_id)
        return ScoreResponse(
            product_id=product_id,
            product_title=product.canonical_title,
            scores=[
                ScoreOut(
                    platform=s.platform,
                    score=s.score,
                    rank=s.rank or 0,
                    components=s.components or {},
                    explanation=s.explanation or "",
                    suggested_inventory_share_pct=s.suggested_inventory_share_pct or 0,
                    computed_at=s.computed_at,
                )
                for s in stored
            ],
        )

    existing = db.execute(
        select(OpportunityScore)
        .where(OpportunityScore.product_id == product_id)
        .order_by(OpportunityScore.rank)
    ).scalars().all()

    if not existing:
        stored = compute_and_store_scores(db, product_id)
        return ScoreResponse(
            product_id=product_id,
            product_title=product.canonical_title,
            scores=[
                ScoreOut(
                    platform=s.platform,
                    score=s.score,
                    rank=s.rank or 0,
                    components=s.components or {},
                    explanation=s.explanation or "",
                    suggested_inventory_share_pct=s.suggested_inventory_share_pct or 0,
                    computed_at=s.computed_at,
                )
                for s in stored
            ],
        )

    return ScoreResponse(
        product_id=product_id,
        product_title=product.canonical_title,
        scores=[
            ScoreOut(
                platform=s.platform,
                score=s.score,
                rank=s.rank or 0,
                components=s.components or {},
                explanation=s.explanation or "",
                suggested_inventory_share_pct=s.suggested_inventory_share_pct or 0,
                computed_at=s.computed_at,
            )
            for s in existing
        ],
    )


@router.post("/{product_id}/recompute", response_model=ScoreResponse)
def recompute_scores(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Any:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    stored = compute_and_store_scores(db, product_id)
    return ScoreResponse(
        product_id=product_id,
        product_title=product.canonical_title,
        scores=[
            ScoreOut(
                platform=s.platform,
                score=s.score,
                rank=s.rank or 0,
                components=s.components or {},
                explanation=s.explanation or "",
                suggested_inventory_share_pct=s.suggested_inventory_share_pct or 0,
                computed_at=s.computed_at,
            )
            for s in stored
        ],
    )
