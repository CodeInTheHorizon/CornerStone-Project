"""Deterministic analytics from MarketplaceSnapshot history, never model inference.

Series identity: canonical product + platform + source + currency + listing ID.
The Phase 5 product key is reused, but different listings/provenance/currencies
are never stitched into one price history. Duplicate observations at an identical
instant keep the highest database ID. Missing prices do NOT discard other signals.

Changes compare the first valid reading to the latest observation in the selected
window. If the latest reading is missing, historical statistics remain available,
but latest change/direction are null. Review momentum is net reviews per elapsed
calendar day (not sales, and not the Phase 5 per-observation slope).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, time, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.normalization import availability_state, normalize_category, normalize_product_name, product_key
from app.ml.opportunity import number
from app.models import MarketplaceSnapshot, ModelMetadata, Prediction
from app.models.enums import Platform
from app.schemas.analytics import AnalyticsFilters
from app.scrapers.registry import all_statuses, effective_status
from app.services import dataset_service

MAX_ROWS = 20_000
GROUP_FIELDS = ("product_key", "platform", "source_type", "currency", "listing_key")
POLICY = (
    "Separate exact product, listing, platform, source and currency histories. "
    "Repeated imports at the same instant keep the newest database row. "
    "No interpolation or imputation. Price direction uses a ±1% first-to-latest "
    "change over the selected window; other directions use the sign of the change. "
    "Review momentum is net review change per elapsed day, not sales demand."
)


class AnalyticsError(Exception):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.detail = {"status": status, "reason": reason}


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def iso(value: datetime | None) -> str | None:
    return utc(value).isoformat() if value else None


def mean(values) -> float | None:
    usable = [v for v in values if v is not None]
    return round(sum(usable) / len(usable), 6) if usable else None


def valid(value, lower=0, upper=float("inf")) -> float | None:
    value = number(value)
    return value if value is not None and lower <= value <= upper else None


def observations(db: Session, filters: AnalyticsFilters) -> tuple[list[dict], int]:
    if filters.start_date and filters.end_date and filters.start_date > filters.end_date:
        raise AnalyticsError("invalid_date_range", "start_date must be on or before end_date.")
    statement = select(MarketplaceSnapshot).order_by(MarketplaceSnapshot.collection_timestamp, MarketplaceSnapshot.id)
    if filters.platform:
        statement = statement.where(MarketplaceSnapshot.platform == filters.platform.value)
    if filters.source_type:
        statement = statement.where(MarketplaceSnapshot.source_type == filters.source_type.value)
    if filters.start_date:
        statement = statement.where(MarketplaceSnapshot.collection_timestamp >= datetime.combine(filters.start_date, time.min))
    if filters.end_date:
        # Inclusive calendar day, without overflowing date.max.
        statement = statement.where(MarketplaceSnapshot.collection_timestamp <= datetime.combine(filters.end_date, time.max))
    # Canonical identity/category are computed with Phase 5 normalization, not
    # guessed using SQL substring matches that would miss aliases.
    raw = db.scalars(statement.limit(MAX_ROWS + 1)).all()
    if len(raw) > MAX_ROWS:
        raise AnalyticsError("too_many_observations", "Narrow the platform, source or date range to at most 20,000 stored rows.")
    unique = {}
    matched = 0
    for row in raw:
        key = product_key(row.product_name, row.brand, row.category)
        category = normalize_category(row.category)
        if filters.product_key and key != filters.product_key:
            continue
        if filters.product and normalize_product_name(row.product_name) != normalize_product_name(filters.product):
            continue
        if filters.category and category != normalize_category(filters.category):
            continue
        matched += 1
        price = valid(row.price)
        discount = valid(row.discount_percentage, upper=100)
        derived = False
        original = valid(row.original_price)
        if discount is None and price is not None and original and price <= original:
            discount = (original - price) / original * 100
            derived = True
        item = {
            "snapshot_id": row.id, "product_key": key, "product_name": row.product_name,
            "category": category, "platform": row.platform, "source_type": row.source_type,
            "currency": row.currency or "unknown", "listing_key": row.external_id or row.listing_url or f"{key}|{row.seller_name or 'unknown-seller'}",
            "timestamp": utc(row.collection_timestamp), "price": price, "discount": discount,
            "discount_derived": derived, "rating": valid(row.rating, upper=5),
            "reviews": valid(row.review_count), "availability": availability_state(row.availability),
        }
        identity = tuple(item[field] for field in GROUP_FIELDS) + (item["timestamp"],)
        if identity not in unique or unique[identity]["snapshot_id"] < row.id:
            unique[identity] = item
    rows = sorted(unique.values(), key=lambda row: (row["timestamp"], row["snapshot_id"]))
    return rows, matched - len(rows)


def metric(rows: list[dict], field: str) -> dict:
    readings = [row for row in rows if row[field] is not None]
    values = [row[field] for row in readings]
    first = values[0] if values else None
    latest = rows[-1][field] if rows else None
    available = len(readings) >= 2 and latest is not None
    change = latest - first if available else None
    percentage = change / first * 100 if available and first != 0 else None
    direction = None
    if available:
        indicator = percentage if field == "price" and percentage is not None else change
        threshold = 1.0 if field == "price" and percentage is not None else 1e-9
        direction = "rising" if indicator > threshold else "falling" if indicator < -threshold else "stable"
    elapsed = (rows[-1]["timestamp"] - readings[0]["timestamp"]).total_seconds() / 86400 if available else None
    return {
        "status": "available" if available else "insufficient_data",
        "reason": None if available else f"At least two valid {field} observations and a valid latest reading are required.",
        "valid_observations": len(values), "first": first, "latest": latest,
        "first_observed_at": iso(readings[0]["timestamp"]) if readings else None,
        "latest_valid": values[-1] if values else None,
        "latest_valid_at": iso(readings[-1]["timestamp"]) if readings else None,
        "absolute_change": round(change, 6) if change is not None else None,
        "percentage_change": round(percentage, 6) if percentage is not None else None,
        "average": mean(values), "min": min(values) if values else None,
        "max": max(values) if values else None, "direction": direction,
        "momentum_per_day": round(change / elapsed, 6) if field == "reviews" and elapsed and elapsed > 0 else None,
    }


def availability(rows: list[dict]) -> dict:
    events = []
    pairs = 0
    for before, after in zip(rows, rows[1:]):
        if before["availability"] is None or after["availability"] is None:
            continue
        pairs += 1
        if before["availability"] != after["availability"]:
            events.append({"from": before["availability"], "to": after["availability"], "previous_observation": iso(before["timestamp"]), "observed_at": iso(after["timestamp"])})
    return {
        "status": "available" if pairs else "insufficient_data",
        "reason": None if pairs else "Two adjacent observations with known availability are required to identify movement.",
        "latest": rows[-1]["availability"] if rows else None,
        "changes": len(events) if pairs else None, "events": events,
        "notice": "Changes were observed between these timestamps. No stock quantity or exact change time is inferred; unknown gaps are not bridged.",
    }


def series_from(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in GROUP_FIELDS)].append(row)
    result = []
    for key in sorted(groups):
        history = groups[key]
        first = history[0]
        metrics = {field: metric(history, field) for field in ("price", "discount", "rating", "reviews")}
        stock = availability(history)
        available = any(value["status"] == "available" for value in [*metrics.values(), stock])
        result.append({
            **{field: first[field] for field in GROUP_FIELDS}, "product_name": first["product_name"], "category": first["category"],
            "status": "available" if available else "insufficient_data",
            "reason": None if available else "Insufficient repeated readings for a trend. Available single readings are shown without inferred direction.",
            "observation_count": len(history),
            "date_range": {"start": iso(first["timestamp"]), "end": iso(history[-1]["timestamp"])},
            **metrics, "availability": stock,
            "points": [{"timestamp": iso(row["timestamp"]), **{field: row[field] for field in ("price", "discount", "discount_derived", "rating", "reviews", "availability")}} for row in history],
        })
    return result


def provenance(rows: list[dict], duplicates: int) -> dict:
    sources = dict(sorted(Counter(row["source_type"] for row in rows).items()))
    return {
        "source_types": list(sources), "records_by_source_type": sources,
        "observation_count": len(rows), "duplicates_removed": duplicates,
        "date_range": {"start": iso(rows[0]["timestamp"]) if rows else None, "end": iso(rows[-1]["timestamp"]) if rows else None},
        "notice": "Stored observations only. DEMO is synthetic; IMPORTED was supplied by an operator. LIVE denotes original collection provenance, not current freshness.",
    }


def trends(db: Session, filters: AnalyticsFilters, limit: int = 20, offset: int = 0) -> dict:
    rows, duplicates = observations(db, filters)
    series = series_from(rows)
    available = any(s["status"] == "available" for s in series)
    return {
        "status": "available" if available else "insufficient_data",
        "reason": None if available else "No comparable repeated observations match the selected filters.",
        "provenance": provenance(rows, duplicates), "calculation_policy": POLICY,
        "total_series": len(series), "series": series[offset:offset + limit],
    }


def options(db: Session, filters: AnalyticsFilters, query: str = "", limit: int = 50, offset: int = 0) -> dict:
    rows, _ = observations(db, filters)
    products = {}
    for row in rows:
        if query.strip().lower() not in row["product_key"].lower():
            continue
        key = row["product_key"]
        products[key] = {"product_key": key, "product_name": row["product_name"], "category": row["category"]}
    keys = sorted(products)
    return {
        "products": [products[key] for key in keys[offset:offset + limit]], "total": len(keys),
        "categories": sorted({row["category"] for row in rows if row["category"]}),
    }


def saved_scores(db: Session, user_id: int, keys: set[str]) -> dict:
    """Only read the user's stored Phase 7 response; never predict or rescore."""
    found = {}
    # History is small in this MVP; newest matching observation wins. Bound the
    # lookup explicitly and leave scores unavailable if absent from recent history.
    records = db.scalars(select(Prediction).where(Prediction.user_id == user_id, Prediction.result_payload.is_not(None)).order_by(Prediction.created_at.desc(), Prediction.id.desc()).limit(500))
    for record in records:
        saved = record.result_payload or {}
        key = saved.get("product_key")
        if key not in keys:
            continue
        sources = saved.get("data_provenance", {}).get("source_types", [])
        for entry in saved.get("ranking", []):
            source = entry.get("source_type")
            if sources != [source] or not entry.get("data_freshness"):
                continue
            lookup = (key, entry["platform"], source, entry["data_freshness"])
            if lookup not in found:
                found[lookup] = {
                    "score": entry.get("opportunity_score"), "prediction_id": record.id,
                    "model_version": saved.get("model", {}).get("version"), "model": saved.get("model"),
                    "warning": saved.get("warning"), "created_at": iso(record.created_at),
                    "notice": "Saved Phase 7 result using its original dataset history; not recalculated for these filters.",
                }
    return found


def comparison(db: Session, user_id: int, filters: AnalyticsFilters) -> dict:
    if not (filters.product_key or filters.product or filters.category):
        return {"status": "insufficient_data", "reason": "Select an exact product or category to compare platforms.", "groups": [], "provenance": provenance([], 0)}
    rows, duplicates = observations(db, filters)
    histories = series_from(rows)
    by_product = bool(filters.product_key or filters.product)
    groups = defaultdict(list)
    for item in histories:
        key = (item["product_key"] if by_product else item["category"], item["source_type"], item["currency"])
        groups[key].append(item)
    scores = saved_scores(db, user_id, {row["product_key"] for row in rows}) if by_product and rows else {}
    result = []
    for (identity, source, currency), items in sorted(groups.items()):
        platforms = []
        for platform in ([filters.platform.value] if filters.platform else [p.value for p in Platform]):
            matching = [item for item in items if item["platform"] == platform]
            latest_dates = sorted(item["date_range"]["end"] for item in matching)
            score = None
            # Phase 7 uses INR; multiple distinct listings cannot be assigned one
            # old score unambiguously. Match exact source and observation instant.
            if by_product and len(matching) == 1 and currency == "INR":
                for (key, candidate, kind, stamp), saved in scores.items():
                    if (key, candidate, kind) == (identity, platform, source) and utc(datetime.fromisoformat(stamp)) == utc(datetime.fromisoformat(latest_dates[-1])):
                        score = saved
                        break
            average_price = mean(item["price"]["average"] for item in matching)
            platforms.append({
                "platform": platform, "status": "available" if average_price is not None else "insufficient_data",
                "reason": None if average_price is not None else "No valid stored prices for this comparison group.",
                "listing_count": len(matching), "listing_density": round(len(matching) / len(items), 6),
                "average_price": average_price, "latest_price": mean(item["price"]["latest"] for item in matching),
                "average_discount": mean(item["discount"]["average"] for item in matching),
                "average_rating": mean(item["rating"]["average"] for item in matching),
                "review_growth": mean(item["reviews"]["absolute_change"] for item in matching),
                "review_growth_percentage": mean(item["reviews"]["percentage_change"] for item in matching),
                "review_growth_listing_count": sum(item["reviews"]["absolute_change"] is not None for item in matching),
                "latest_price_listing_count": sum(item["price"]["latest"] is not None for item in matching),
                "latest_observation": latest_dates[-1] if latest_dates else None,
                "earliest_latest_observation": latest_dates[0] if latest_dates else None,
                "opportunity": score,
                "opportunity_reason": None if score else "No unambiguous saved Phase 7 score matches this product, source and latest observation (last 500 user predictions checked).",
            })
        comparable = sum(item["status"] == "available" for item in platforms) >= 2
        result.append({
            "identity": identity, "grouping": "exact_product" if by_product else "category_aggregate",
            "source_type": source, "currency": currency, "platforms": platforms,
            "status": "available" if comparable else "insufficient_data",
            "reason": None if comparable else "At least two platforms with observed prices are needed for comparison.",
            "notice": "Equal-weight means of individual listing statistics. Category groups may contain different product assortments and are not like-for-like product comparisons. Listing density is share of listings observed in this filtered sample, not market-wide competition. Latest readings may be from different dates.",
        })
    available = any(group["status"] == "available" for group in result)
    return {"status": "available" if available else "insufficient_data", "reason": None if available else "Insufficient comparable platform data.", "groups": result, "provenance": provenance(rows, duplicates)}


def refresh_sources() -> list[dict]:
    result = []
    for platform, status in all_statuses().items():
        status = effective_status(status)
        result.append({"platform": platform, "available": status.available, "reason": status.reason, "access_method": status.access_method})
    return result


def summary(db: Session, user_id: int) -> dict:
    by_source = {source: count for source, count in db.execute(select(MarketplaceSnapshot.source_type, func.count()).group_by(MarketplaceSnapshot.source_type))}
    latest = db.scalar(select(func.max(MarketplaceSnapshot.collection_timestamp)))
    latest_sources = list(db.scalars(select(MarketplaceSnapshot.source_type).where(MarketplaceSnapshot.collection_timestamp == latest).distinct())) if latest else []
    platforms = list(db.scalars(select(MarketplaceSnapshot.platform).distinct().order_by(MarketplaceSnapshot.platform)))
    model = db.scalar(select(ModelMetadata).where(ModelMetadata.is_active.is_(True)))
    dataset = dataset_service.latest_dataset()
    sources = refresh_sources()
    return {
        "total_predictions": db.scalar(select(func.count()).select_from(Prediction).where(Prediction.user_id == user_id)) or 0,
        "stored_records": sum(by_source.values()), "records_by_source_type": dict(sorted(by_source.items())),
        "latest_observation": iso(latest), "latest_observation_sources": sorted(latest_sources),
        "stored_platforms": platforms, "available_live_platforms": [s["platform"] for s in sources if s["available"]],
        "refresh_sources": sources,
        "active_model": None if model is None else {
            "version": model.model_version, "type": model.algorithm, "accuracy": model.accuracy,
            "f1_weighted": model.f1_score, "majority_baseline": (model.metrics or {}).get("majority_baseline"),
            "source_types": (model.hyperparameters or {}).get("dataset_source_types", []),
        },
        "latest_dataset": None if dataset is None else {
            "dataset_id": dataset["dataset_id"], "source_types": dataset.get("source_types", []),
            "generated_at": dataset.get("generated_at"),
            "file_available": bool(dataset.get("csv_path") and Path(dataset["csv_path"]).is_file()),
        },
        "notice": "Observation time records when the source was observed, not when the dashboard loaded or a dataset was built. DEMO and IMPORTED records are not live updates.",
    }
