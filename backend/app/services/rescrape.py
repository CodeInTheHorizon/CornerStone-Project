"""Background re-scrape job for tracked products.

Finds tracked products whose listings are due for a refresh (based on each
tracked product's refresh_interval_minutes) and re-scrapes them across all
platforms they have listings on.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.platform_listing import PlatformListing
from app.models.price_history import PriceHistory
from app.models.tracked_product import TrackedProduct
from app.scrapers.registry import get_collector

logger = logging.getLogger(__name__)


def _due_tracked_products(db: Session) -> list[tuple[TrackedProduct, list[PlatformListing]]]:
    """Find tracked products whose listings need re-scraping."""
    tracked = db.execute(select(TrackedProduct)).scalars().all()
    due = []
    now = datetime.now(timezone.utc)

    for tp in tracked:
        listings = db.execute(
            select(PlatformListing).where(PlatformListing.product_id == tp.product_id)
        ).scalars().all()
        if not listings:
            continue

        stale_listings = []
        for listing in listings:
            age = now - listing.scraped_at
            if age > timedelta(minutes=tp.refresh_interval_minutes):
                stale_listings.append(listing)

        if stale_listings:
            due.append((tp, stale_listings))

    return due


def _rescrape_listing(db: Session, listing: PlatformListing) -> bool:
    """Re-scrape a single listing and update it. Returns True on success."""
    try:
        collector = get_collector(listing.platform)
        if not collector.status().available:
            listing.is_stale = True
            return False

        outcome = collector.collect(
            listing.title_on_platform,
            max_items=5,
        )
        if not outcome.records:
            listing.is_stale = True
            return False

        best = outcome.records[0]
        now = datetime.now(timezone.utc)

        listing.price_current = best.price
        listing.price_original = best.original_price
        listing.discount_pct = best.discount_percentage
        listing.rating = best.rating
        listing.review_count = best.review_count
        listing.seller_count = best.seller_count
        listing.offer_count = best.offer_count
        listing.image_url = best.image_url or listing.image_url
        listing.scraped_at = now
        listing.is_stale = False

        history = PriceHistory(
            listing_id=listing.id,
            price=best.price,
            discount_pct=best.discount_percentage,
            rating=best.rating,
            review_count=best.review_count,
            seller_count=best.seller_count,
            observed_at=now,
        )
        db.add(history)
        return True

    except Exception as exc:
        logger.warning("Re-scrape failed for listing %d: %s", listing.id, exc)
        listing.is_stale = True
        return False


def run_rescrape_cycle() -> dict[str, int]:
    """Run one full re-scrape cycle. Returns stats."""
    db = SessionLocal()
    stats = {"checked": 0, "updated": 0, "stale": 0}
    try:
        due = _due_tracked_products(db)
        for tp, listings in due:
            for listing in listings:
                stats["checked"] += 1
                if _rescrape_listing(db, listing):
                    stats["updated"] += 1
                else:
                    stats["stale"] += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    logger.info("Re-scrape cycle: %s", stats)
    return stats


async def rescrape_background_task() -> None:
    """Async wrapper for the re-scrape cycle, runs in a thread."""
    await asyncio.to_thread(run_rescrape_cycle)
