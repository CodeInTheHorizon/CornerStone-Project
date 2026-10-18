"""Listing pages: Amazon search / best-seller parsing and the listing sweep (no network)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.config import settings
from app.live_scraping.adapters.amazon import AmazonParser
from app.live_scraping.adapters.amazon_listing import AmazonListingParser
from app.live_scraping.base import (
    HtmlScraperSource,
    ListingKind,
    ListingRef,
    ListingResult,
    ObservationSource,
    ObservedListingItem,
    TargetRef,
)
from app.live_scraping.errors import ParseFailedError, SourceBlockedError
from app.live_scraping.http_client import FetchedPage
from app.live_scraping.schemas import Availability, Marketplace, ProductObservation as Obs
from app.live_scraping.service import register_listing, register_target, run_due_listings, run_due_targets
from app.models.live_scraping import (
    ProductObservation,
    ScrapeAttempt,
    ScrapeListingPage,
    ScrapeSourceState,
    ScrapeTarget,
)

FIXTURES = Path(__file__).parent / "fixtures" / "live_scraping"
listing_parser = AmazonListingParser()


class FixtureClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.urls: list[str] = []

    def get(self, url, detect_block=None):
        self.urls.append(url)
        page = FetchedPage(url, url, 200, self.text, "text/html", 5, 1)
        if detect_block and (reason := detect_block(page)):
            raise SourceBlockedError(reason)
        return page

    def close(self):
        pass


def _observe(fixture: str, kind: ListingKind, query: str, page: int = 1):
    client = FixtureClient((FIXTURES / fixture).read_text(encoding="utf-8"))
    source = HtmlScraperSource(AmazonParser(), client, is_enabled=True, listing_parser=listing_parser)
    ref = source.resolve_listing(kind, query)
    return source.observe_listing(ref, page), client


# ------------------------------------------------------------------ parsing


def test_search_page_yields_one_observation_per_product():
    result, client = _observe("amazon_search.html", ListingKind.SEARCH, "wireless earbuds")
    assert client.urls == ["https://www.amazon.in/s?k=wireless+earbuds"]
    by_id = {i.observation.platform_product_id: i for i in result.items}
    assert list(by_id) == ["B0SPONS001", "B0ORGANIC1", "B0NOBUYBOX"]  # duplicate and ASIN-less cards dropped
    assert "B0CAROUSE1" not in by_id
    assert result.has_next_page

    ad = by_id["B0SPONS001"]
    obs = ad.observation
    assert ad.rank == 1 and ad.sponsored is True
    assert obs.product_name == "Sonix Buds 5 Wireless Earbuds"
    assert (obs.current_price, obs.mrp, obs.discount_percentage) == (Decimal("4990.00"), Decimal("8990.00"), Decimal("44.49"))
    assert obs.rating == Decimal("4.00") and obs.rating_count == 5175  # exact, not the rounded "(5.1K)"
    assert obs.availability is Availability.IN_STOCK
    assert obs.source == "amazon-listing/1"
    assert obs.product_url == "https://www.amazon.in/dp/B0SPONS001"
    assert obs.seller_name is None and obs.model is None  # listing pages do not show these


def test_unit_price_is_not_read_as_mrp_and_low_stock_is_detected():
    result, _ = _observe("amazon_search.html", ListingKind.SEARCH, "wireless earbuds")
    obs = next(i.observation for i in result.items if i.observation.platform_product_id == "B0ORGANIC1")
    assert (obs.current_price, obs.mrp) == (Decimal("299.00"), Decimal("999.00"))
    assert obs.availability is Availability.LOW_STOCK


def test_card_without_buy_box_has_no_price():
    result, _ = _observe("amazon_search.html", ListingKind.SEARCH, "wireless earbuds")
    obs = next(i.observation for i in result.items if i.observation.platform_product_id == "B0NOBUYBOX")
    assert obs.current_price is None  # "₹1,999 (1 new offer)" is a third-party offer
    assert obs.availability is Availability.UNKNOWN
    assert obs.availability_text == "No featured offers available"
    assert obs.rating_count == 50596


def test_bestsellers_page():
    result, client = _observe("amazon_bestsellers.html", ListingKind.BESTSELLERS, "electronics")
    assert client.urls == ["https://www.amazon.in/gp/bestsellers/electronics"]
    first, second = result.items
    assert first.rank == 1 and second.rank == 2
    assert first.observation.product_name == "Portix Conch Theta C in Ear Type C Wired Earphones with in Line HD Mic"
    assert first.observation.current_price == Decimal("311.00")
    assert first.observation.rating_count == 13275 and first.observation.rating == Decimal("4.10")
    assert first.observation.category == "Electronics"
    assert second.observation.rating is None and second.observation.rating_count is None
    assert result.has_next_page


def test_search_page_without_cards_is_a_parse_failure_but_no_results_is_empty():
    source = HtmlScraperSource(AmazonParser(), FixtureClient("<html><body>" + "<p>x</p>" * 50 + "</body></html>"),
                               is_enabled=True, listing_parser=listing_parser)
    ref = source.resolve_listing(ListingKind.SEARCH, "zzz")
    with pytest.raises(ParseFailedError):
        source.observe_listing(ref)
    empty = HtmlScraperSource(AmazonParser(), FixtureClient("<html><body>No results for zzz.</body></html>"),
                              is_enabled=True, listing_parser=listing_parser)
    assert empty.observe_listing(ref).items == ()


def test_captcha_on_a_listing_page_is_a_block():
    source = HtmlScraperSource(AmazonParser(), FixtureClient((FIXTURES / "amazon_captcha.html").read_text(encoding="utf-8")),
                               is_enabled=True, listing_parser=listing_parser)
    with pytest.raises(SourceBlockedError):
        source.observe_listing(source.resolve_listing(ListingKind.SEARCH, "earbuds"))


@pytest.mark.parametrize(("kind", "value", "url"), [
    (ListingKind.SEARCH, "  wireless   earbuds ", "https://www.amazon.in/s?k=wireless+earbuds"),
    (ListingKind.SEARCH, "https://www.amazon.in/s?k=power+bank&xpid=abc&qid=1&ref=sr_pg_1",
     "https://www.amazon.in/s?k=power+bank"),
    (ListingKind.BESTSELLERS, "electronics", "https://www.amazon.in/gp/bestsellers/electronics"),
    (ListingKind.BESTSELLERS, "https://www.amazon.in/gp/bestsellers/electronics/1388921031/ref=zg_bs_nav_0",
     "https://www.amazon.in/gp/bestsellers/electronics/1388921031"),
])
def test_listing_refs_are_canonical(kind, value, url):
    assert listing_parser.listing_ref(kind, value).url == url


@pytest.mark.parametrize(("kind", "value"), [
    (ListingKind.SEARCH, "https://www.flipkart.com/s?k=x"),
    (ListingKind.SEARCH, "https://www.amazon.in/dp/B0TESTAC01"),
    (ListingKind.BESTSELLERS, "https://www.amazon.in/gp/cart"),
    (ListingKind.SEARCH, "   "),
])
def test_bad_listing_refs_are_rejected(kind, value):
    with pytest.raises(ValueError):
        listing_parser.listing_ref(kind, value)


def test_page_urls():
    search = listing_parser.listing_ref(ListingKind.SEARCH, "earbuds")
    best = listing_parser.listing_ref(ListingKind.BESTSELLERS, "electronics")
    assert listing_parser.page_url(search, 1) == "https://www.amazon.in/s?k=earbuds"
    assert listing_parser.page_url(search, 3) == "https://www.amazon.in/s?k=earbuds&page=3"
    assert listing_parser.page_url(best, 2) == "https://www.amazon.in/gp/bestsellers/electronics?pg=2"


# -------------------------------------------------------------------- sweep


def _obs(pid: str, price: str = "100.00") -> Obs:
    return Obs(marketplace=Marketplace.AMAZON, platform_product_id=pid, product_url=f"https://www.amazon.in/dp/{pid}",
               collected_at=datetime.now(timezone.utc), source="amazon-listing/1", product_name=f"Product {pid}",
               current_price=Decimal(price), availability=Availability.UNKNOWN)


class ScriptedListingSource(ObservationSource):
    """Listing pages come from `pages[(url, page_number)]`: a list of pids, or an exception."""

    marketplace = Marketplace.AMAZON
    source_name = "amazon-test/1"
    listing_source_name = "amazon-listing-test/1"

    def __init__(self, pages: dict, *, next_pages: set | None = None) -> None:
        self.pages = pages
        self.next_pages = next_pages or set()
        self.listing_calls: list[tuple[str, int]] = []
        self.product_calls: list[str] = []

    def enabled(self):
        return True, None

    def supports_listings(self):
        return True

    def resolve(self, url_or_id):
        pid = url_or_id.strip().upper()
        return TargetRef(Marketplace.AMAZON, pid, f"https://www.amazon.in/dp/{pid}")

    def resolve_listing(self, kind, query_or_url):
        return listing_parser.listing_ref(ListingKind(kind), query_or_url)

    def observe(self, target):
        self.product_calls.append(target.platform_product_id)
        return _obs(target.platform_product_id)

    def observe_listing(self, ref: ListingRef, page_number: int = 1) -> ListingResult:
        self.listing_calls.append((ref.url, page_number))
        entry = self.pages.get((ref.url, page_number), [])
        if isinstance(entry, Exception):
            raise entry
        items = tuple(ObservedListingItem(_obs(pid), rank, False) for rank, pid in enumerate(entry, start=1))
        return ListingResult(items, (ref.url, page_number) in self.next_pages)


SEARCH = "https://www.amazon.in/s?k=earbuds"
BEST = "https://www.amazon.in/gp/bestsellers/electronics"


@pytest.fixture(autouse=True)
def _clean(db_session):
    for model in (ProductObservation, ScrapeAttempt, ScrapeListingPage, ScrapeSourceState, ScrapeTarget):
        db_session.execute(delete(model))
    db_session.commit()
    yield


def _register(db, source, kind, query, pages=1, **kw):
    listing, _ = register_listing(db, "amazon", kind, query, max_pages=pages, source=source, **kw)
    db.commit()
    return listing


def test_sweep_stores_every_product_and_follows_pages(db_session):
    source = ScriptedListingSource(
        {(SEARCH, 1): ["B0AAAAAAA1", "B0AAAAAAA2"], (SEARCH, 2): ["B0AAAAAAA3"]}, next_pages={(SEARCH, 1)}
    )
    _register(db_session, source, "search", "earbuds", pages=3)
    summary = run_due_listings(db_session, "amazon", source=source)

    assert source.listing_calls == [(SEARCH, 1), (SEARCH, 2)]  # stops when there is no next page
    assert (summary.attempted, summary.stored, summary.discovered) == (2, 3, 3)
    rows = db_session.execute(select(ProductObservation).order_by(ProductObservation.id)).scalars().all()
    assert [r.list_rank for r in rows] == [1, 2, 3]  # search ranks continue across pages
    assert all(r.listing_page_id is not None for r in rows)
    attempts = db_session.execute(select(ScrapeAttempt).order_by(ScrapeAttempt.id)).scalars().all()
    assert [(a.page_number, a.items_found) for a in attempts] == [(1, 2), (2, 1)]
    assert len({r.attempt_id for r in rows}) == 2  # many observations share one attempt


def test_discovered_products_get_spread_detail_visits_not_an_immediate_burst(db_session):
    source = ScriptedListingSource({(BEST, 1): [f"B0DISCOV{n:02d}" for n in range(20)]})
    _register(db_session, source, "bestsellers", "electronics")
    run_due_listings(db_session, "amazon", source=source)

    targets = db_session.execute(select(ScrapeTarget)).scalars().all()
    assert len(targets) == 20 and all(t.is_active for t in targets)
    assert all(t.refresh_interval_minutes == settings.SCRAPER_DETAIL_REFRESH_MINUTES for t in targets)
    # Only products whose spread offset has already passed are due; not all 20 at once.
    assert run_due_targets(db_session, "amazon", source=source).attempted < 20


def test_repeat_sweeps_append_history(db_session):
    source = ScriptedListingSource({(BEST, 1): ["B0AAAAAAA1"]})
    _register(db_session, source, "bestsellers", "electronics", refresh_interval_minutes=60)
    run_due_listings(db_session, "amazon", source=source)
    later = lambda: datetime.now(timezone.utc) + timedelta(minutes=61)  # noqa: E731
    run_due_listings(db_session, "amazon", source=source, now=later)
    assert db_session.execute(select(func.count(ProductObservation.id))).scalar_one() == 2
    assert db_session.execute(select(func.count(ScrapeTarget.id))).scalar_one() == 1


def test_product_on_two_listings_is_stored_once_per_run(db_session):
    source = ScriptedListingSource({(SEARCH, 1): ["B0AAAAAAA1", "B0AAAAAAA2"], (BEST, 1): ["B0AAAAAAA2"]})
    _register(db_session, source, "search", "earbuds")
    _register(db_session, source, "bestsellers", "electronics")
    summary = run_due_listings(db_session, "amazon", source=source)
    assert summary.stored == 2


def test_no_track_listing_creates_inactive_targets(db_session):
    source = ScriptedListingSource({(BEST, 1): ["B0AAAAAAA1"]})
    _register(db_session, source, "bestsellers", "electronics", auto_track=False)
    run_due_listings(db_session, "amazon", source=source)
    assert db_session.execute(select(ScrapeTarget.is_active)).scalar_one() is False


def test_existing_target_keeps_its_own_schedule(db_session):
    source = ScriptedListingSource({(BEST, 1): ["B0AAAAAAA1"]})
    target, _ = register_target(db_session, "amazon", "B0AAAAAAA1", refresh_interval_minutes=90, source=source)
    db_session.commit()
    _register(db_session, source, "bestsellers", "electronics")
    summary = run_due_listings(db_session, "amazon", source=source)
    db_session.refresh(target)
    assert summary.discovered == 0 and target.refresh_interval_minutes == 90


def test_block_on_a_listing_pauses_the_marketplace_for_product_pages_too(db_session):
    source = ScriptedListingSource({(SEARCH, 1): SourceBlockedError("Amazon served a CAPTCHA challenge.")})
    _register(db_session, source, "search", "earbuds")
    register_target(db_session, "amazon", "B0AAAAAAA1", source=source)
    db_session.commit()

    summary = run_due_listings(db_session, "amazon", source=source)
    assert "CAPTCHA" in summary.source_unavailable
    assert db_session.get(ScrapeSourceState, "amazon").state == "unavailable"
    assert run_due_targets(db_session, "amazon", source=source).attempted == 0
    assert source.product_calls == []
    assert db_session.execute(select(func.count(ProductObservation.id))).scalar_one() == 0


def test_block_on_page_two_keeps_page_one(db_session):
    source = ScriptedListingSource(
        {(SEARCH, 1): ["B0AAAAAAA1"], (SEARCH, 2): SourceBlockedError("CAPTCHA")}, next_pages={(SEARCH, 1)}
    )
    _register(db_session, source, "search", "earbuds", pages=2)
    summary = run_due_listings(db_session, "amazon", source=source)
    assert summary.stored == 1 and summary.source_unavailable
    assert db_session.execute(select(func.count(ProductObservation.id))).scalar_one() == 1


def test_register_listing_validation(db_session):
    source = ScriptedListingSource({})
    with pytest.raises(ValueError, match="kind"):
        register_listing(db_session, "amazon", "deals", "x", source=source)
    with pytest.raises(ValueError, match="max_pages"):
        register_listing(db_session, "amazon", "search", "x", max_pages=11, source=source)
    first, created = register_listing(db_session, "amazon", "search", "Earbuds ", source=source)
    again, created_again = register_listing(db_session, "amazon", "search", "earbuds", source=source)
    assert created and not created_again and first.id == again.id
