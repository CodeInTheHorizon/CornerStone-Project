"""Real-time cross-platform product search.

A single search fans out to all four platforms in parallel, returning results
as they arrive. Results are cached with a short TTL for repeat queries.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models import User
from app.models.enums import Platform
from app.scrapers.base import CollectorError, NormalizedRecord
from app.scrapers.registry import get_collector
from app.services.product_persistence import persist_search_results

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# In-memory TTL cache: {cache_key: (timestamp, results)}
_cache: dict[str, tuple[float, list[dict]]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes


class SearchListing(BaseModel):
    platform: str
    product_name: str
    brand: str | None = None
    category: str | None = None
    external_id: str | None = None
    image_url: str | None = None
    image_urls: list[str] | None = None
    price: float | None = None
    original_price: float | None = None
    discount_percentage: float | None = None
    currency: str = "INR"
    rating: float | None = None
    review_count: int | None = None
    availability: str | None = None
    seller_name: str | None = None
    seller_count: int | None = None
    offer_count: int | None = None
    listing_url: str | None = None
    min_order_qty: int | None = None
    price_min: float | None = None
    price_max: float | None = None
    supplier_years: int | None = None
    is_stale: bool = False


class PlatformResult(BaseModel):
    platform: str
    status: str  # "ok" | "error" | "unavailable"
    listings: list[SearchListing] = Field(default_factory=list)
    error: str | None = None
    latency_ms: int = 0
    from_cache: bool = False


class SearchResponse(BaseModel):
    query: str
    total_results: int
    platforms: list[PlatformResult]


def _record_to_listing(record: NormalizedRecord) -> SearchListing:
    return SearchListing(
        platform=record.platform,
        product_name=record.product_name,
        brand=record.brand,
        category=record.category,
        external_id=record.external_id,
        image_url=record.image_url,
        image_urls=record.image_urls,
        price=record.price,
        original_price=record.original_price,
        discount_percentage=record.discount_percentage,
        currency=record.currency,
        rating=record.rating,
        review_count=record.review_count,
        availability=record.availability,
        seller_name=record.seller_name,
        seller_count=record.seller_count,
        offer_count=record.offer_count,
        listing_url=record.listing_url,
        min_order_qty=record.min_order_qty,
        price_min=record.price_min,
        price_max=record.price_max,
        supplier_years=record.supplier_years,
    )


def _cache_key(query: str, platform: str) -> str:
    return hashlib.md5(f"{platform}:{query.strip().lower()}".encode()).hexdigest()


def _get_cached(query: str, platform: str) -> list[dict] | None:
    key = _cache_key(query, platform)
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts > CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return data


def _set_cache(query: str, platform: str, listings: list[SearchListing]) -> None:
    key = _cache_key(query, platform)
    _cache[key] = (time.time(), [l.model_dump() for l in listings])
    if len(_cache) > 500:
        cutoff = time.time() - CACHE_TTL_SECONDS
        expired = [k for k, (ts, _) in _cache.items() if ts < cutoff]
        for k in expired:
            _cache.pop(k, None)


async def _search_platform(
    platform_name: str, query: str, max_items: int, category: str | None
) -> tuple[PlatformResult, list[NormalizedRecord]]:
    cached = _get_cached(query, platform_name)
    if cached is not None:
        return PlatformResult(
            platform=platform_name,
            status="ok",
            listings=[SearchListing(**item) for item in cached],
            from_cache=True,
        ), []

    start = time.time()
    try:
        collector = get_collector(platform_name)
        status = collector.status()
        if not status.available:
            return PlatformResult(
                platform=platform_name,
                status="unavailable",
                error=status.reason,
            ), []

        outcome = await asyncio.to_thread(
            collector.collect, query, category, max_items
        )
        listings = [_record_to_listing(r) for r in outcome.records]
        latency = int((time.time() - start) * 1000)

        _set_cache(query, platform_name, listings)

        return PlatformResult(
            platform=platform_name,
            status="ok",
            listings=listings,
            latency_ms=latency,
        ), list(outcome.records)
    except CollectorError as exc:
        latency = int((time.time() - start) * 1000)
        logger.warning("Search failed for %s: %s", platform_name, exc)
        return PlatformResult(
            platform=platform_name,
            status="error",
            error=str(exc),
            latency_ms=latency,
        ), []
    except Exception as exc:
        latency = int((time.time() - start) * 1000)
        logger.exception("Unexpected error searching %s", platform_name)
        return PlatformResult(
            platform=platform_name,
            status="error",
            error=f"Internal error: {type(exc).__name__}",
            latency_ms=latency,
        ), []


@router.get("", response_model=SearchResponse)
async def search_products(
    q: str = Query(min_length=2, max_length=120, description="Product search query"),
    category: str | None = Query(default=None, max_length=120),
    max_items: int = Query(default=10, ge=1, le=50),
    platforms: str | None = Query(
        default=None,
        description="Comma-separated platform filter (e.g. 'amazon,flipkart'). Omit for all.",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    platform_list = (
        [p.strip().lower() for p in platforms.split(",") if p.strip()]
        if platforms
        else [p.value for p in Platform]
    )

    tasks = [
        _search_platform(p, q, max_items, category) for p in platform_list
    ]
    gather_results = await asyncio.gather(*tasks)

    platform_results = []
    all_records: list[NormalizedRecord] = []
    for result, records in gather_results:
        platform_results.append(result)
        all_records.extend(records)

    if all_records:
        try:
            await asyncio.to_thread(persist_search_results, db, all_records)
        except Exception:
            logger.warning("Failed to persist search results", exc_info=True)

    total = sum(len(r.listings) for r in platform_results)
    return SearchResponse(query=q, total_results=total, platforms=platform_results)
