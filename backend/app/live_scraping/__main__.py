"""Command-line entry point.

    python -m app.live_scraping add amazon https://www.amazon.in/dp/B0XXXXXXXX
    python -m app.live_scraping import targets.csv       # columns: marketplace,url[,refresh_minutes,label]
    python -m app.live_scraping observe amazon B0XXXXXXXX  # fetch + print, store nothing
    python -m app.live_scraping add-listing amazon search "wireless earbuds" --pages 3
    python -m app.live_scraping add-listing amazon bestsellers electronics --pages 2
    python -m app.live_scraping import-listings listings.csv  # marketplace,kind,query[,pages,refresh_minutes,auto_track,label]
    python -m app.live_scraping observe-listing amazon search "wireless earbuds"
    python -m app.live_scraping run --marketplace amazon --limit 50
    python -m app.live_scraping worker --poll-seconds 60
    python -m app.live_scraping status
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import signal
import sys
import threading
from pathlib import Path

from app.database.session import SessionLocal, init_db
from app.live_scraping.errors import ScrapeError
from app.live_scraping.registry import get_source, parse_marketplace
from app.live_scraping.schemas import Marketplace
from app.live_scraping.base import ListingKind
from app.live_scraping.service import (
    register_listing,
    register_target,
    run_due_listings,
    run_due_targets,
    status_report,
)


def _print(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def cmd_add(args) -> int:
    with SessionLocal() as db:
        try:
            target, created = register_target(db, args.marketplace, args.url, refresh_interval_minutes=args.refresh_minutes, label=args.label)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        db.commit()
        _print({"created": created, "id": target.id, "marketplace": target.marketplace,
                "platform_product_id": target.platform_product_id, "product_url": target.product_url})
    return 0


def cmd_import(args) -> int:
    created = existing = 0
    errors: list[str] = []
    with SessionLocal() as db, Path(args.csv).open(newline="", encoding="utf-8-sig") as handle:
        sources = {}
        try:
            for line, row in enumerate(csv.DictReader(handle), start=2):
                try:
                    market = parse_marketplace(row.get("marketplace") or "")
                    source = sources.get(market) or sources.setdefault(market, get_source(market))
                    minutes = int(row["refresh_minutes"]) if (row.get("refresh_minutes") or "").strip() else None
                    _, was_created = register_target(db, market, row.get("url") or "", refresh_interval_minutes=minutes,
                                                     label=row.get("label") or None, source=source)
                except (ValueError, KeyError) as exc:
                    errors.append(f"line {line}: {exc}")
                    continue
                created += was_created
                existing += not was_created
            db.commit()
        finally:
            for source in sources.values():
                source.close()
    _print({"created": created, "already_tracked": existing, "errors": errors[:50], "error_count": len(errors)})
    return 0 if not errors else 1


def cmd_observe(args) -> int:
    source = get_source(args.marketplace)
    try:
        ref = source.resolve(args.url)
        observation = source.observe(ref)
    except (ValueError, ScrapeError) as exc:
        outcome = getattr(getattr(exc, "outcome", None), "value", "invalid_target")
        _print({"stored": False, "outcome": outcome, "reason": str(exc)})
        return 1
    finally:
        source.close()
    _print({"stored": False, "observation": observation.model_dump(mode="json")})
    return 0


def _truthy(value: str | None, default: bool = True) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def cmd_add_listing(args) -> int:
    with SessionLocal() as db:
        try:
            listing, created = register_listing(
                db, args.marketplace, args.kind, args.query, max_pages=args.pages,
                refresh_interval_minutes=args.refresh_minutes, auto_track=not args.no_track, label=args.label,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        db.commit()
        _print({"created": created, "id": listing.id, "kind": listing.kind, "url": listing.url,
                "max_pages": listing.max_pages, "auto_track": listing.auto_track})
    return 0


def cmd_import_listings(args) -> int:
    created = existing = 0
    errors: list[str] = []
    sources = {}
    with SessionLocal() as db, Path(args.csv).open(newline="", encoding="utf-8-sig") as handle:
        try:
            for line, row in enumerate(csv.DictReader(handle), start=2):
                try:
                    market = parse_marketplace(row.get("marketplace") or "")
                    source = sources.get(market) or sources.setdefault(market, get_source(market))
                    pages = int(row["pages"]) if (row.get("pages") or "").strip() else 1
                    minutes = int(row["refresh_minutes"]) if (row.get("refresh_minutes") or "").strip() else None
                    _, was_created = register_listing(
                        db, market, row.get("kind") or "", row.get("query") or "", max_pages=pages,
                        refresh_interval_minutes=minutes, auto_track=_truthy(row.get("auto_track")),
                        label=row.get("label") or None, source=source,
                    )
                except (ValueError, KeyError) as exc:
                    errors.append(f"line {line}: {exc}")
                    continue
                created += was_created
                existing += not was_created
            db.commit()
        finally:
            for source in sources.values():
                source.close()
    _print({"created": created, "already_listed": existing, "errors": errors[:50], "error_count": len(errors)})
    return 0 if not errors else 1


def cmd_observe_listing(args) -> int:
    source = get_source(args.marketplace)
    try:
        ref = source.resolve_listing(ListingKind(args.kind), args.query)
        result = source.observe_listing(ref, args.page)
    except (ValueError, ScrapeError) as exc:
        outcome = getattr(getattr(exc, "outcome", None), "value", "invalid_listing")
        _print({"stored": False, "outcome": outcome, "reason": str(exc)})
        return 1
    finally:
        source.close()
    _print({"stored": False, "url": ref.url, "page": args.page, "count": len(result.items),
            "has_next_page": result.has_next_page, "skipped": list(result.skipped),
            "items": [{"rank": i.rank, "sponsored": i.sponsored, **i.observation.model_dump(mode="json")}
                      for i in result.items]})
    return 0


def _markets(value: str | None) -> list[Marketplace]:
    return [parse_marketplace(value)] if value else list(Marketplace)


def _run_once(markets: list[Marketplace], limit: int, listing_limit: int) -> list[dict]:
    """One pass per marketplace, in parallel threads -- each host has its own pacing.

    Listing pages go first (many products per request), then due product
    pages. Both share one source, so a single client paces every request.
    """
    results: list[dict] = []
    lock = threading.Lock()

    def work(market: Marketplace) -> None:
        source = get_source(market)
        try:
            with SessionLocal() as db:
                listed = run_due_listings(db, market, limit=listing_limit, source=source)
                detailed = run_due_targets(db, market, limit=limit, source=source)
        finally:
            source.close()
        with lock:
            results.append({
                "marketplace": market.value,
                "listing_pages": {"requests": listed.attempted, "stored": listed.stored,
                                  "new_products": listed.discovered, "outcomes": dict(listed.outcomes)},
                "product_pages": {"requests": detailed.attempted, "stored": detailed.stored,
                                  "outcomes": dict(detailed.outcomes)},
                "source_unavailable": listed.source_unavailable or detailed.source_unavailable,
            })

    threads = [threading.Thread(target=work, args=(m,), name=f"scrape-{m.value}") for m in markets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return sorted(results, key=lambda r: r["marketplace"])


def cmd_run(args) -> int:
    _print(_run_once(_markets(args.marketplace), args.limit, args.listing_limit))
    return 0


def cmd_worker(args) -> int:
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    log = logging.getLogger("app.live_scraping.worker")
    while not stop.is_set():
        for result in _run_once(_markets(args.marketplace), args.limit, args.listing_limit):
            requests_made = result["listing_pages"]["requests"] + result["product_pages"]["requests"]
            if requests_made or result["source_unavailable"]:
                log.info("%s", json.dumps(result, default=str))
        stop.wait(args.poll_seconds)
    return 0


def cmd_status(args) -> int:
    with SessionLocal() as db:
        _print(status_report(db))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.live_scraping", description="MarketPulse live product collection")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="track one product")
    add.add_argument("marketplace")
    add.add_argument("url", help="product URL or platform product id")
    add.add_argument("--refresh-minutes", type=int)
    add.add_argument("--label")
    add.set_defaults(func=cmd_add)

    imp = sub.add_parser("import", help="track products from a CSV (marketplace,url[,refresh_minutes,label])")
    imp.add_argument("csv")
    imp.set_defaults(func=cmd_import)

    obs = sub.add_parser("observe", help="fetch one product and print it without storing")
    obs.add_argument("marketplace")
    obs.add_argument("url")
    obs.set_defaults(func=cmd_observe)

    al = sub.add_parser("add-listing", help="sweep a search or best-seller listing (many products per request)")
    al.add_argument("marketplace")
    al.add_argument("kind", choices=[k.value for k in ListingKind])
    al.add_argument("query", help="search keyword, best-seller category path, or listing URL")
    al.add_argument("--pages", type=int, default=1, help="pages per sweep (1-10)")
    al.add_argument("--refresh-minutes", type=int)
    al.add_argument("--no-track", action="store_true", help="do not schedule product-page visits for products found")
    al.add_argument("--label")
    al.set_defaults(func=cmd_add_listing)

    il = sub.add_parser("import-listings",
                        help="listings from a CSV (marketplace,kind,query[,pages,refresh_minutes,auto_track,label])")
    il.add_argument("csv")
    il.set_defaults(func=cmd_import_listings)

    ol = sub.add_parser("observe-listing", help="fetch one listing page and print it without storing")
    ol.add_argument("marketplace")
    ol.add_argument("kind", choices=[k.value for k in ListingKind])
    ol.add_argument("query")
    ol.add_argument("--page", type=int, default=1)
    ol.set_defaults(func=cmd_observe_listing)

    for name, func, help_text in (("run", cmd_run, "one pass over due listings, then due products"),
                                  ("worker", cmd_worker, "keep running passes until interrupted")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--marketplace")
        p.add_argument("--limit", type=int, default=100, help="max product pages per marketplace per pass")
        p.add_argument("--listing-limit", type=int, default=20, help="max listings per marketplace per pass")
        if name == "worker":
            p.add_argument("--poll-seconds", type=float, default=60.0)
        p.set_defaults(func=func)

    st = sub.add_parser("status", help="per-marketplace targets, observations and availability")
    st.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.command not in {"observe", "observe-listing"}:
        init_db()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
