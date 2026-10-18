"""Persist search results into the canonical Product → PlatformListing → PriceHistory chain."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.platform_listing import PlatformListing
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.scrapers.base import NormalizedRecord
from app.services.product_matcher import find_or_create_product


def _in_stock(record: NormalizedRecord) -> bool | None:
    avail = (record.availability or "").lower()
    if not avail:
        return None
    if "out" in avail:
        return False
    if "in stock" in avail or "available" in avail:
        return True
    return None


def persist_listing(
    db: Session,
    record: NormalizedRecord,
) -> tuple[Product, PlatformListing, PriceHistory]:
    """Upsert a NormalizedRecord into the Product/Listing/History chain.

    - Finds or creates a canonical Product via fuzzy matching.
    - Upserts the PlatformListing (one per product per platform).
    - Appends a PriceHistory row (never overwrites old ones).
    """
    product, confidence = find_or_create_product(
        db,
        title=record.product_name,
        brand=record.brand,
        category=record.category or "electronics",
        subcategory=getattr(record, "subcategory", None),
        image_url=record.image_url,
    )

    listing = db.execute(
        select(PlatformListing).where(
            PlatformListing.product_id == product.id,
            PlatformListing.platform == record.platform,
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if listing is None:
        listing = PlatformListing(
            product_id=product.id,
            platform=record.platform,
            platform_product_id=record.external_id,
            product_url=record.listing_url,
            title_on_platform=record.product_name,
            image_url=record.image_url or "",
            image_urls=record.image_urls,
            price_current=record.price,
            price_original=record.original_price,
            currency=record.currency or "INR",
            discount_pct=record.discount_percentage,
            rating=record.rating,
            review_count=record.review_count,
            seller_name=record.seller_name,
            seller_count=record.seller_count,
            offer_count=record.offer_count,
            in_stock=_in_stock(record),
            min_order_qty=record.min_order_qty,
            price_min=record.price_min,
            price_max=record.price_max,
            match_confidence=confidence,
            scraped_at=now,
            is_stale=False,
        )
        db.add(listing)
        db.flush()
    else:
        listing.title_on_platform = record.product_name
        listing.platform_product_id = record.external_id or listing.platform_product_id
        listing.product_url = record.listing_url or listing.product_url
        listing.image_url = record.image_url or listing.image_url
        listing.image_urls = record.image_urls or listing.image_urls
        listing.price_current = record.price
        listing.price_original = record.original_price
        listing.discount_pct = record.discount_percentage
        listing.rating = record.rating
        listing.review_count = record.review_count
        listing.seller_name = record.seller_name or listing.seller_name
        listing.seller_count = record.seller_count
        listing.offer_count = record.offer_count
        listing.in_stock = _in_stock(record) if record.availability else listing.in_stock
        listing.min_order_qty = record.min_order_qty or listing.min_order_qty
        listing.price_min = record.price_min or listing.price_min
        listing.price_max = record.price_max or listing.price_max
        listing.match_confidence = confidence
        listing.scraped_at = now
        listing.is_stale = False
        db.flush()

    history = PriceHistory(
        listing_id=listing.id,
        price=record.price,
        mrp=record.original_price,
        discount_pct=record.discount_percentage,
        rating=record.rating,
        rating_count=record.review_count,
        review_count=record.review_count,
        availability=record.availability,
        seller_count=record.seller_count,
        observed_at=now,
    )
    db.add(history)

    return product, listing, history


def persist_search_results(
    db: Session,
    records: list[NormalizedRecord],
) -> list[tuple[Product, PlatformListing, PriceHistory]]:
    """Persist a batch of search results and commit."""
    results = []
    for record in records:
        try:
            result = persist_listing(db, record)
            results.append(result)
        except Exception:
            continue
    db.commit()
    return results
