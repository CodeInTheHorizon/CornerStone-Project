"""Scheduling, storage and failure handling for live product observations.

`run_due_targets` is one pass over one marketplace:

1. Skip entirely if the marketplace is disabled or inside a block cooldown.
2. Claim up to `limit` due targets (row-locked with SKIP LOCKED on
   PostgreSQL, so several workers never fetch the same product).
3. Observe each one. Success INSERTs a new `product_observations` row --
   history is never updated in place. Every attempt, failed or not, is
   logged in `scrape_attempts`.
4. A source-level failure (CAPTCHA/bot page, 403, 429, JavaScript-only
   pages, unreadable robots.txt, or repeated parse failures that suggest a
   layout change) marks the marketplace unavailable for the cooldown and
   ends the pass. Targets not yet attempted are released untouched.

Each target is committed on its own, so one failure never discards the
observations already collected in the same pass.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.live_scraping.base import ListingKind, ListingRef, ObservationSource, ObservedListingItem, TargetRef
from app.live_scraping.errors import (
    ProductNotFoundError,
    RateLimitedError,
    RobotsDisallowedError,
    ScrapeError,
    ScrapeOutcome,
)
from app.live_scraping.registry import get_source, parse_marketplace
from app.live_scraping.schemas import Marketplace, ProductObservation as ObservationModel
from app.models.live_scraping import (
    ProductObservation,
    ScrapeAttempt,
    ScrapeListingPage,
    ScrapeSourceState,
    ScrapeTarget,
)

logger = logging.getLogger(__name__)

#: How long a claimed target stays reserved if a worker dies mid-pass.
CLAIM_LEASE = timedelta(minutes=30)
#: This many parse failures in a row across different products means the
#: layout changed; stop instead of spending requests on pages we cannot read.
PARSE_FAILURE_CIRCUIT = 5
#: A product that is missing this many times in a row is deactivated.
NOT_FOUND_DEACTIVATE_AFTER = 3
#: Retry delay for a product-level failure, doubled per consecutive failure.
FAILURE_RETRY_BASE = timedelta(minutes=30)
#: Pages per listing sweep. Amazon search rarely has useful results past 10.
MAX_LISTING_PAGES = 10

UNAVAILABLE = "unavailable"
AVAILABLE = "available"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass
class RunSummary:
    marketplace: str
    run_id: str
    attempted: int = 0
    stored: int = 0
    outcomes: Counter = field(default_factory=Counter)
    #: Set when the pass did not run or stopped early because of the source.
    source_unavailable: str | None = None
    #: Listing sweeps only: products seen for the first time (new scrape targets).
    discovered: int = 0


# --------------------------------------------------------------------- targets


def register_target(
    db: Session,
    marketplace: str | Marketplace,
    url_or_id: str,
    *,
    refresh_interval_minutes: int | None = None,
    label: str | None = None,
    product_id: int | None = None,
    source: ObservationSource | None = None,
) -> tuple[ScrapeTarget, bool]:
    """Add a product to track, or return the existing target. (target, created)."""
    market = parse_marketplace(marketplace)
    owned = source is None
    source = source or get_source(market)
    try:
        ref = source.resolve(url_or_id)
    finally:
        if owned:
            source.close()

    existing = db.execute(
        select(ScrapeTarget).where(
            ScrapeTarget.marketplace == market.value,
            ScrapeTarget.platform_product_id == ref.platform_product_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    target = ScrapeTarget(
        marketplace=market.value,
        platform_product_id=ref.platform_product_id,
        product_url=ref.product_url,
        label=label[:255] if label else None,
        product_id=product_id,
        refresh_interval_minutes=refresh_interval_minutes or settings.SCRAPER_DEFAULT_REFRESH_MINUTES,
        next_due_at=_now(),
        is_active=True,
        consecutive_failures=0,
    )
    db.add(target)
    db.flush()
    return target, True


# --------------------------------------------------------------- source state


def source_state(db: Session, marketplace: str) -> ScrapeSourceState | None:
    return db.get(ScrapeSourceState, marketplace)


def _cooldown_until(db: Session, marketplace: str, now: datetime) -> ScrapeSourceState | None:
    state = source_state(db, marketplace)
    if state is None or state.state != UNAVAILABLE:
        return None
    until = _aware(state.unavailable_until)
    return state if until is None or until > now else None


def _mark_source(db: Session, marketplace: str, *, available: bool, outcome: str | None = None,
                 reason: str | None = None, until: datetime | None = None) -> None:
    state = source_state(db, marketplace)
    if state is None:
        state = ScrapeSourceState(marketplace=marketplace)
        db.add(state)
    state.state = AVAILABLE if available else UNAVAILABLE
    state.outcome = None if available else outcome
    state.reason = None if available else (reason or "")[:500]
    state.unavailable_until = None if available else until
    state.updated_at = _now()


def _pause_source(db: Session, marketplace: str, outcome: str, message: str,
                  retry_after: float | None, *, now) -> datetime:
    """Mark the marketplace unavailable for the provider's Retry-After, else the configured cooldown."""
    until = now() + (
        timedelta(seconds=retry_after) if retry_after
        else timedelta(minutes=settings.SCRAPER_BLOCK_COOLDOWN_MINUTES)
    )
    _mark_source(db, marketplace, available=False, outcome=outcome, reason=message, until=until)
    logger.warning("%s marked unavailable until %s: %s", marketplace, until.isoformat(), message)
    return until


def _source_blocker(db: Session, source: ObservationSource, marketplace: str, now: datetime) -> str | None:
    """Why this marketplace must not be contacted right now, or None."""
    ok, reason = source.enabled()
    if not ok:
        return reason or f"{marketplace} collection is disabled."
    cooling = _cooldown_until(db, marketplace, now)
    if cooling is not None:
        until = _aware(cooling.unavailable_until)
        return f"{cooling.reason} Paused until {until.isoformat(timespec='minutes') if until else 'further notice'}."
    return None


# ------------------------------------------------------------------- the pass


def _claim_due(db: Session, marketplace: str, limit: int, now: datetime) -> list[ScrapeTarget]:
    stmt = (
        select(ScrapeTarget)
        .where(
            ScrapeTarget.marketplace == marketplace,
            ScrapeTarget.is_active.is_(True),
            ScrapeTarget.next_due_at <= now,
        )
        .order_by(ScrapeTarget.next_due_at, ScrapeTarget.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    targets = list(db.execute(stmt).scalars())
    for target in targets:
        target.next_due_at = now + CLAIM_LEASE
    db.commit()
    return targets


def _store_observation(db: Session, target: ScrapeTarget, attempt: ScrapeAttempt, obs: ObservationModel) -> ProductObservation:
    row = ProductObservation(
        target_id=target.id,
        attempt_id=attempt.id,
        run_id=attempt.run_id,
        marketplace=obs.marketplace.value,
        platform_product_id=obs.platform_product_id,
        product_url=obs.product_url,
        collected_at=obs.collected_at,
        source=obs.source,
        product_name=obs.product_name,
        brand=obs.brand,
        category=obs.category,
        category_path=obs.category_path,
        model=obs.model,
        variant=obs.variant,
        current_price=obs.current_price,
        mrp=obs.mrp,
        currency=obs.currency,
        discount_percentage=obs.discount_percentage,
        rating=obs.rating,
        rating_count=obs.rating_count,
        review_count=obs.review_count,
        availability=obs.availability.value,
        availability_text=obs.availability_text,
        seller_name=obs.seller_name,
        warnings=list(obs.warnings) or None,
    )
    db.add(row)
    return row


def run_due_targets(
    db: Session,
    marketplace: str | Marketplace,
    *,
    limit: int = 100,
    source: ObservationSource | None = None,
    now=_now,
) -> RunSummary:
    market = parse_marketplace(marketplace)
    summary = RunSummary(marketplace=market.value, run_id=str(uuid.uuid4()))
    owned = source is None
    source = source or get_source(market)
    try:
        blocker = _source_blocker(db, source, market.value, now())
        if blocker is not None:
            summary.source_unavailable = blocker
            return summary

        targets = _claim_due(db, market.value, max(1, limit), now())
        parse_failures_in_a_row = 0
        for index, target in enumerate(targets):
            stop = _observe_one(db, source, target, summary, now)
            if stop is None:
                if target.last_outcome == ScrapeOutcome.PARSE_FAILED.value:
                    parse_failures_in_a_row += 1
                else:
                    parse_failures_in_a_row = 0
                if parse_failures_in_a_row >= PARSE_FAILURE_CIRCUIT:
                    stop = (
                        ScrapeOutcome.PARSE_FAILED.value,
                        f"{PARSE_FAILURE_CIRCUIT} product pages in a row could not be parsed; "
                        "the page layout has probably changed.",
                        None,
                    )
            if stop is not None:
                until = _pause_source(db, market.value, *stop, now=now)
                for untouched in targets[index + 1:]:
                    untouched.next_due_at = until
                db.commit()
                summary.source_unavailable = stop[1]
                break
        else:
            if summary.stored:
                _mark_source(db, market.value, available=True)
                db.commit()
        return summary
    finally:
        if owned:
            source.close()


def _observe_one(db, source: ObservationSource, target: ScrapeTarget, summary: RunSummary, now) -> tuple | None:
    """Observe one target. Returns (outcome, message, retry_after) when the whole source must stop."""
    started = now()
    attempt = ScrapeAttempt(
        run_id=summary.run_id,
        target_id=target.id,
        marketplace=target.marketplace,
        source=source.source_name,
        url=target.product_url,
        started_at=started,
        outcome=ScrapeOutcome.SUCCESS.value,
    )
    ref = TargetRef(Marketplace(target.marketplace), target.platform_product_id, target.product_url)
    summary.attempted += 1
    target.last_attempt_at = started

    try:
        observation = source.observe(ref)
    except ScrapeError as exc:
        finished = now()
        attempt.finished_at = finished
        attempt.outcome = exc.outcome.value
        attempt.http_status = exc.http_status
        attempt.error_message = str(exc)[:500]
        attempt.elapsed_ms = int((finished - started).total_seconds() * 1000)
        db.add(attempt)
        target.last_outcome = exc.outcome.value
        summary.outcomes[exc.outcome.value] += 1

        if exc.source_level:
            # Not this product's fault: put it back where it was in the queue.
            target.next_due_at = started
            db.commit()
            retry_after = exc.retry_after_seconds if isinstance(exc, RateLimitedError) else None
            return exc.outcome.value, str(exc), retry_after

        target.consecutive_failures += 1
        if isinstance(exc, RobotsDisallowedError):
            target.is_active = False
        elif isinstance(exc, ProductNotFoundError) and target.consecutive_failures >= NOT_FOUND_DEACTIVATE_AFTER:
            target.is_active = False
        interval = timedelta(minutes=target.refresh_interval_minutes)
        retry = FAILURE_RETRY_BASE * (2 ** (target.consecutive_failures - 1))
        target.next_due_at = finished + min(interval, retry)
        db.commit()
        return None

    finished = now()
    attempt.finished_at = finished
    attempt.elapsed_ms = int((finished - started).total_seconds() * 1000)
    db.add(attempt)
    db.flush()  # attempt.id is needed by the observation
    _store_observation(db, target, attempt, observation)
    target.last_outcome = ScrapeOutcome.SUCCESS.value
    target.last_success_at = observation.collected_at
    target.consecutive_failures = 0
    target.next_due_at = finished + timedelta(minutes=target.refresh_interval_minutes)
    db.commit()
    summary.stored += 1
    summary.outcomes[ScrapeOutcome.SUCCESS.value] += 1
    return None


# -------------------------------------------------------------- listing pages
#
# One listing request stores an observation for every product on the page.
# Products seen for the first time become scrape targets whose product-page
# visits are spread over SCRAPER_DETAIL_REFRESH_MINUTES, so discovery never
# turns into a burst of product-page requests.


def register_listing(
    db: Session,
    marketplace: str | Marketplace,
    kind: str | ListingKind,
    query_or_url: str,
    *,
    max_pages: int = 1,
    refresh_interval_minutes: int | None = None,
    auto_track: bool = True,
    label: str | None = None,
    source: ObservationSource | None = None,
) -> tuple[ScrapeListingPage, bool]:
    """Add a search or best-seller listing to sweep, or return the existing one. (listing, created)."""
    market = parse_marketplace(marketplace)
    try:
        kind = kind if isinstance(kind, ListingKind) else ListingKind(kind.strip().lower())
    except ValueError:
        raise ValueError(f"Unknown listing kind {kind!r}; expected search or bestsellers.") from None
    if not 1 <= max_pages <= MAX_LISTING_PAGES:
        raise ValueError(f"max_pages must be between 1 and {MAX_LISTING_PAGES}.")
    owned = source is None
    source = source or get_source(market)
    try:
        if not source.supports_listings():
            raise ValueError(f"{market.value} does not support listing pages yet.")
        ref = source.resolve_listing(kind, query_or_url)
    finally:
        if owned:
            source.close()

    existing = db.execute(
        select(ScrapeListingPage).where(ScrapeListingPage.marketplace == market.value, ScrapeListingPage.url == ref.url)
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    listing = ScrapeListingPage(
        marketplace=market.value, kind=ref.kind.value, url=ref.url, label=label[:255] if label else None,
        max_pages=max_pages, auto_track=auto_track, is_active=True, consecutive_failures=0,
        refresh_interval_minutes=refresh_interval_minutes or settings.SCRAPER_LISTING_REFRESH_MINUTES,
        next_due_at=_now(),
    )
    db.add(listing)
    db.flush()
    return listing, True


def _detail_offset(platform_product_id: str, minutes: int) -> timedelta:
    """A stable per-product offset inside the detail interval, so first visits are spread evenly."""
    digest = int(hashlib.sha1(platform_product_id.encode()).hexdigest()[:8], 16)
    return timedelta(minutes=digest % max(1, minutes))


def _target_for(db: Session, listing: ScrapeListingPage, item: ObservedListingItem, now: datetime,
                summary: RunSummary) -> ScrapeTarget:
    obs = item.observation
    target = db.execute(
        select(ScrapeTarget).where(
            ScrapeTarget.marketplace == obs.marketplace.value,
            ScrapeTarget.platform_product_id == obs.platform_product_id,
        )
    ).scalar_one_or_none()
    if target is not None:
        return target
    minutes = settings.SCRAPER_DETAIL_REFRESH_MINUTES
    target = ScrapeTarget(
        marketplace=obs.marketplace.value,
        platform_product_id=obs.platform_product_id,
        product_url=obs.product_url,
        label=obs.product_name[:255],
        # Without auto_track the row exists for identity only: no product-page visits.
        is_active=listing.auto_track,
        refresh_interval_minutes=minutes,
        next_due_at=now + _detail_offset(obs.platform_product_id, minutes),
        consecutive_failures=0,
    )
    db.add(target)
    db.flush()
    summary.discovered += 1
    return target


def _claim_due_listings(db: Session, marketplace: str, limit: int, now: datetime) -> list[ScrapeListingPage]:
    stmt = (
        select(ScrapeListingPage)
        .where(
            ScrapeListingPage.marketplace == marketplace,
            ScrapeListingPage.is_active.is_(True),
            ScrapeListingPage.next_due_at <= now,
        )
        .order_by(ScrapeListingPage.next_due_at, ScrapeListingPage.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    listings = list(db.execute(stmt).scalars())
    for listing in listings:
        listing.next_due_at = now + CLAIM_LEASE
    db.commit()
    return listings


def run_due_listings(
    db: Session,
    marketplace: str | Marketplace,
    *,
    limit: int = 20,
    source: ObservationSource | None = None,
    now=_now,
) -> RunSummary:
    """Sweep due listing pages. `attempted` counts page requests; `stored` counts observations."""
    market = parse_marketplace(marketplace)
    summary = RunSummary(marketplace=market.value, run_id=str(uuid.uuid4()))
    owned = source is None
    source = source or get_source(market)
    try:
        blocker = _source_blocker(db, source, market.value, now())
        if blocker is None and not source.supports_listings():
            blocker = f"{market.value} does not support listing pages yet."
        if blocker is not None:
            summary.source_unavailable = blocker
            return summary

        listings = _claim_due_listings(db, market.value, max(1, limit), now())
        stored_this_run: set[str] = set()
        parse_failures_in_a_row = 0
        for index, listing in enumerate(listings):
            stop = _sweep_listing(db, source, listing, summary, stored_this_run, now)
            if stop is None:
                if listing.last_outcome == ScrapeOutcome.PARSE_FAILED.value:
                    parse_failures_in_a_row += 1
                else:
                    parse_failures_in_a_row = 0
                if parse_failures_in_a_row >= PARSE_FAILURE_CIRCUIT:
                    stop = (ScrapeOutcome.PARSE_FAILED.value,
                            f"{PARSE_FAILURE_CIRCUIT} listing pages in a row could not be parsed; "
                            "the page layout has probably changed.", None)
            if stop is not None:
                until = _pause_source(db, market.value, *stop, now=now)
                for untouched in listings[index + 1:]:
                    untouched.next_due_at = until
                db.commit()
                summary.source_unavailable = stop[1]
                break
        else:
            if summary.stored:
                _mark_source(db, market.value, available=True)
                db.commit()
        return summary
    finally:
        if owned:
            source.close()


def _sweep_listing(db, source: ObservationSource, listing: ScrapeListingPage, summary: RunSummary,
                   stored_this_run: set[str], now) -> tuple | None:
    """Fetch up to max_pages of one listing. Returns (outcome, message, retry_after) to stop the source."""
    ref = ListingRef(Marketplace(listing.marketplace), ListingKind(listing.kind), listing.url)
    listing.last_attempt_at = now()
    source_name = getattr(source, "listing_source_name", None) or source.source_name
    stored_here = 0
    rank_offset = 0

    for page_number in range(1, listing.max_pages + 1):
        started = now()
        attempt = ScrapeAttempt(
            run_id=summary.run_id, listing_page_id=listing.id, page_number=page_number,
            marketplace=listing.marketplace, source=source_name,
            url=listing.url, started_at=started, outcome=ScrapeOutcome.SUCCESS.value,
        )
        summary.attempted += 1
        try:
            result = source.observe_listing(ref, page_number)
        except ScrapeError as exc:
            finished = now()
            attempt.finished_at = finished
            attempt.outcome = exc.outcome.value
            attempt.http_status = exc.http_status
            attempt.error_message = str(exc)[:500]
            attempt.elapsed_ms = int((finished - started).total_seconds() * 1000)
            db.add(attempt)
            summary.outcomes[exc.outcome.value] += 1
            if exc.source_level:
                listing.last_outcome = exc.outcome.value
                listing.next_due_at = started
                summary.stored += stored_here
                db.commit()
                retry_after = exc.retry_after_seconds if isinstance(exc, RateLimitedError) else None
                return exc.outcome.value, str(exc), retry_after
            if page_number > 1:
                break  # keep what earlier pages stored; the sweep still counts
            listing.last_outcome = exc.outcome.value
            listing.consecutive_failures += 1
            if isinstance(exc, RobotsDisallowedError):
                listing.is_active = False
            retry = FAILURE_RETRY_BASE * (2 ** (listing.consecutive_failures - 1))
            listing.next_due_at = finished + min(timedelta(minutes=listing.refresh_interval_minutes), retry)
            db.commit()
            return None

        finished = now()
        attempt.finished_at = finished
        attempt.elapsed_ms = int((finished - started).total_seconds() * 1000)
        attempt.items_found = len(result.items)
        if result.skipped:
            attempt.error_message = f"{len(result.skipped)} cards skipped: {'; '.join(result.skipped)}"[:500]
        db.add(attempt)
        db.flush()

        page_max_rank = 0
        for item in result.items:
            rank = item.rank
            if rank is not None:
                page_max_rank = max(page_max_rank, rank)
                if ref.kind is ListingKind.SEARCH:
                    rank += rank_offset  # search positions restart on every page
            pid = item.observation.platform_product_id
            if pid in stored_this_run:
                continue  # already observed in this run through another listing
            target = _target_for(db, listing, item, finished, summary)
            row = _store_observation(db, target, attempt, item.observation)
            row.listing_page_id = listing.id
            row.list_rank = rank
            row.sponsored = item.sponsored
            stored_this_run.add(pid)
            stored_here += 1
        rank_offset += page_max_rank
        summary.outcomes[ScrapeOutcome.SUCCESS.value] += 1
        db.commit()
        if not result.has_next_page:
            break

    summary.stored += stored_here
    listing.last_outcome = ScrapeOutcome.SUCCESS.value
    listing.last_success_at = now()
    listing.last_items = stored_here
    listing.consecutive_failures = 0
    listing.next_due_at = now() + timedelta(minutes=listing.refresh_interval_minutes)
    db.commit()
    return None


# ---------------------------------------------------------------------- status


def status_report(db: Session, now: datetime | None = None) -> dict[str, dict]:
    now = now or _now()
    report: dict[str, dict] = {}
    for market in Marketplace:
        total, active, due = db.execute(
            select(
                func.count(ScrapeTarget.id),
                func.count(ScrapeTarget.id).filter(ScrapeTarget.is_active.is_(True)),
                func.count(ScrapeTarget.id).filter(ScrapeTarget.is_active.is_(True), ScrapeTarget.next_due_at <= now),
            ).where(ScrapeTarget.marketplace == market.value)
        ).one()
        observations, last_observed = db.execute(
            select(func.count(ProductObservation.id), func.max(ProductObservation.collected_at))
            .where(ProductObservation.marketplace == market.value)
        ).one()
        listings, listings_due = db.execute(
            select(
                func.count(ScrapeListingPage.id).filter(ScrapeListingPage.is_active.is_(True)),
                func.count(ScrapeListingPage.id).filter(
                    ScrapeListingPage.is_active.is_(True), ScrapeListingPage.next_due_at <= now
                ),
            ).where(ScrapeListingPage.marketplace == market.value)
        ).one()
        source = get_source(market)
        try:
            enabled, disabled_reason = source.enabled()
        finally:
            source.close()
        state = source_state(db, market.value)
        report[market.value] = {
            "enabled": enabled,
            "disabled_reason": disabled_reason,
            "state": state.state if state else AVAILABLE,
            "unavailable_reason": state.reason if state and state.state == UNAVAILABLE else None,
            "unavailable_until": _aware(state.unavailable_until) if state else None,
            "targets": total,
            "active_targets": active,
            "due_now": due,
            "listing_pages": listings,
            "listing_pages_due": listings_due,
            "observations": observations,
            "last_observed_at": _aware(last_observed),
        }
    return report
