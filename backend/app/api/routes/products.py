"""Product catalog, listings, price history, and tracking endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.platform_listing import PlatformListing
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.models.tracked_product import TrackedProduct
from app.models.user import User

router = APIRouter(prefix="/products", tags=["products"])


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class ListingOut(BaseModel):
    id: int
    platform: str
    platform_product_id: str | None = None
    product_url: str | None = None
    title_on_platform: str
    image_url: str
    image_urls: list[str] | None = None
    price_current: float | None = None
    price_original: float | None = None
    currency: str = "INR"
    discount_pct: float | None = None
    rating: float | None = None
    review_count: int | None = None
    seller_name: str | None = None
    seller_count: int | None = None
    offer_count: int | None = None
    in_stock: bool | None = None
    min_order_qty: int | None = None
    price_min: float | None = None
    price_max: float | None = None
    match_confidence: float | None = None
    scraped_at: datetime
    is_stale: bool = False

    model_config = {"from_attributes": True}


class PricePoint(BaseModel):
    price: float | None = None
    discount_pct: float | None = None
    rating: float | None = None
    review_count: int | None = None
    seller_count: int | None = None
    observed_at: datetime

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    id: int
    canonical_title: str
    brand: str | None = None
    model_number: str | None = None
    category: str
    subcategory: str | None = None
    primary_image_url: str | None = None
    listings: list[ListingOut] = []

    model_config = {"from_attributes": True}


class ProductSummary(BaseModel):
    id: int
    canonical_title: str
    brand: str | None = None
    category: str
    primary_image_url: str | None = None
    platform_count: int = 0
    min_price: float | None = None
    max_price: float | None = None

    model_config = {"from_attributes": True}


class TrackRequest(BaseModel):
    product_id: int
    refresh_interval_minutes: int = 360


class TrackedOut(BaseModel):
    id: int
    product_id: int
    product_title: str
    added_at: datetime
    refresh_interval_minutes: int
    platform_count: int = 0

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------
# Product catalog
# --------------------------------------------------------------------------


@router.get("", response_model=list[ProductSummary])
def list_products(
    category: str | None = None,
    brand: str | None = None,
    q: str | None = Query(None, description="Search in title"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Any:
    stmt = select(Product)
    if category:
        stmt = stmt.where(Product.category == category)
    if brand:
        stmt = stmt.where(Product.brand == brand)
    if q:
        stmt = stmt.where(Product.canonical_title.ilike(f"%{q}%"))
    stmt = stmt.order_by(Product.updated_at.desc()).offset(offset).limit(limit)
    products = db.execute(stmt).scalars().all()

    result = []
    for p in products:
        listings = db.execute(
            select(PlatformListing).where(PlatformListing.product_id == p.id)
        ).scalars().all()
        prices = [l.price_current for l in listings if l.price_current is not None]
        result.append(ProductSummary(
            id=p.id,
            canonical_title=p.canonical_title,
            brand=p.brand,
            category=p.category,
            primary_image_url=p.primary_image_url,
            platform_count=len(listings),
            min_price=min(prices) if prices else None,
            max_price=max(prices) if prices else None,
        ))
    return result


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Any:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/listings", response_model=list[ListingOut])
def get_listings(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Any:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    listings = db.execute(
        select(PlatformListing).where(PlatformListing.product_id == product_id)
    ).scalars().all()
    return listings


@router.get("/{product_id}/history", response_model=dict[str, list[PricePoint]])
def get_price_history(
    product_id: int,
    platform: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Any:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    stmt = (
        select(PlatformListing)
        .where(PlatformListing.product_id == product_id)
    )
    if platform:
        stmt = stmt.where(PlatformListing.platform == platform)
    listings = db.execute(stmt).scalars().all()

    result: dict[str, list[PricePoint]] = {}
    for listing in listings:
        history = db.execute(
            select(PriceHistory)
            .where(PriceHistory.listing_id == listing.id)
            .order_by(PriceHistory.observed_at)
        ).scalars().all()
        result[listing.platform] = [PricePoint.model_validate(h) for h in history]

    return result


# --------------------------------------------------------------------------
# Tracked products
# --------------------------------------------------------------------------


@router.post("/track", response_model=TrackedOut)
def track_product(
    payload: TrackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    product = db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = db.execute(
        select(TrackedProduct).where(
            TrackedProduct.user_id == user.id,
            TrackedProduct.product_id == payload.product_id,
        )
    ).scalar_one_or_none()

    if existing:
        existing.refresh_interval_minutes = payload.refresh_interval_minutes
        db.commit()
        tp = existing
    else:
        tp = TrackedProduct(
            user_id=user.id,
            product_id=payload.product_id,
            refresh_interval_minutes=payload.refresh_interval_minutes,
        )
        db.add(tp)
        db.commit()
        db.refresh(tp)

    listing_count = db.execute(
        select(func.count()).select_from(PlatformListing).where(
            PlatformListing.product_id == tp.product_id
        )
    ).scalar_one()

    return TrackedOut(
        id=tp.id,
        product_id=tp.product_id,
        product_title=product.canonical_title,
        added_at=tp.added_at,
        refresh_interval_minutes=tp.refresh_interval_minutes,
        platform_count=listing_count,
    )


@router.get("/tracked/list", response_model=list[TrackedOut])
def list_tracked(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    tracked = db.execute(
        select(TrackedProduct).where(TrackedProduct.user_id == user.id)
    ).scalars().all()

    result = []
    for tp in tracked:
        product = db.get(Product, tp.product_id)
        listing_count = db.execute(
            select(func.count()).select_from(PlatformListing).where(
                PlatformListing.product_id == tp.product_id
            )
        ).scalar_one()
        result.append(TrackedOut(
            id=tp.id,
            product_id=tp.product_id,
            product_title=product.canonical_title if product else "Unknown",
            added_at=tp.added_at,
            refresh_interval_minutes=tp.refresh_interval_minutes,
            platform_count=listing_count,
        ))
    return result


@router.delete("/track/{tracked_id}", status_code=204)
def untrack_product(
    tracked_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    tp = db.execute(
        select(TrackedProduct).where(
            TrackedProduct.id == tracked_id,
            TrackedProduct.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not tp:
        raise HTTPException(status_code=404, detail="Tracked product not found")
    db.delete(tp)
    db.commit()
