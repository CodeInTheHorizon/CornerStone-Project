"""CSV / JSON dataset import.

Parses an operator-supplied file into NormalizedRecords and hands them to the
shared ingest pipeline, so imported rows go through exactly the same
validation, deduplication and storage as live collection.

Imported rows are tagged SourceType.IMPORTED. They are real data the operator
vouches for, but this system did not observe them and cannot attest to when or
how they were gathered -- so they are never labelled LIVE.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import SourceType
from app.scrapers.base import NormalizedRecord
from app.scrapers.parsing import (
    clean_text,
    compute_discount,
    normalize_url,
    parse_price,
    parse_rating,
    parse_review_count,
)
from app.services.ingest import IngestResult, ingest

MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMPORT_ROWS = 5000


class ImportError_(Exception):
    """The uploaded file could not be read at all."""


#: Accepted column names, mapped to the normalized field they populate.
#: Aliases exist because exported datasets rarely use our exact headers.
FIELD_ALIASES: dict[str, str] = {
    "platform": "platform",
    "marketplace": "platform",
    "product_name": "product_name",
    "title": "product_name",
    "name": "product_name",
    "brand": "brand",
    "category": "category",
    "subcategory": "subcategory",
    "sub_category": "subcategory",
    "external_id": "external_id",
    "asin": "external_id",
    "sku": "external_id",
    "product_id": "external_id",
    "price": "price",
    "selling_price": "price",
    "original_price": "original_price",
    "mrp": "original_price",
    "list_price": "original_price",
    "discount_percentage": "discount_percentage",
    "discount": "discount_percentage",
    "currency": "currency",
    "rating": "rating",
    "review_count": "review_count",
    "reviews": "review_count",
    "num_reviews": "review_count",
    "availability": "availability",
    "seller_name": "seller_name",
    "seller": "seller_name",
    "listing_url": "listing_url",
    "url": "listing_url",
    "link": "listing_url",
    "shipping_info": "shipping_info",
    "delivery_time": "delivery_time",
    "badge": "badge",
    "sponsored": "sponsored",
    "stock_status": "stock_status",
    "collection_timestamp": "collection_timestamp",
    "timestamp": "collection_timestamp",
    "collected_at": "collection_timestamp",
}

_TRUE = {"true", "yes", "1", "y"}
_FALSE = {"false", "no", "0", "n"}


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp; None when absent or unreadable."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    # Naive timestamps are assumed UTC rather than rejected.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_keys(row: dict[str, Any]) -> dict[str, Any]:
    """Map incoming column names onto normalized field names."""
    mapped: dict[str, Any] = {}
    for key, value in row.items():
        if key is None:
            continue
        field = FIELD_ALIASES.get(str(key).strip().lower())
        if field and field not in mapped:
            mapped[field] = value
    return mapped


def row_to_record(row: dict[str, Any]) -> NormalizedRecord | None:
    """Build a NormalizedRecord from one incoming row.

    Returns None when the row has no product name or platform -- validation
    would reject it anyway, and this keeps the reason precise. Absent fields
    stay None; nothing is inferred.
    """
    mapped = _normalize_keys(row)

    platform = clean_text(mapped.get("platform"), 32)
    product_name = clean_text(mapped.get("product_name"), 512)
    if not platform or not product_name:
        return None

    price = parse_price(mapped.get("price"))
    original_price = parse_price(mapped.get("original_price"))

    stated_discount = parse_price(mapped.get("discount_percentage"))
    # Trust a stated discount; only derive one when the file omits it.
    discount = (
        stated_discount
        if stated_discount is not None
        else compute_discount(price, original_price)
    )

    timestamp = _parse_timestamp(mapped.get("collection_timestamp"))

    return NormalizedRecord(
        platform=platform.lower(),
        product_name=product_name,
        brand=clean_text(mapped.get("brand"), 120),
        category=clean_text(mapped.get("category"), 120),
        subcategory=clean_text(mapped.get("subcategory"), 120),
        external_id=clean_text(mapped.get("external_id"), 128),
        price=price,
        original_price=original_price,
        discount_percentage=discount,
        currency=clean_text(mapped.get("currency"), 8) or "INR",
        rating=parse_rating(mapped.get("rating")),
        review_count=parse_review_count(mapped.get("review_count")),
        availability=clean_text(mapped.get("availability"), 64),
        seller_name=clean_text(mapped.get("seller_name"), 255),
        listing_url=normalize_url(mapped.get("listing_url")),
        shipping_info=clean_text(mapped.get("shipping_info"), 255),
        delivery_time=clean_text(mapped.get("delivery_time"), 120),
        badge=clean_text(mapped.get("badge"), 64),
        sponsored=_parse_bool(mapped.get("sponsored")),
        stock_status=clean_text(mapped.get("stock_status"), 64),
        # Falls back to now, and the row is flagged, so an undated import is
        # never silently treated as a historical observation.
        collection_timestamp=timestamp or datetime.now(timezone.utc),
    )


def parse_rows(content: bytes, filename: str) -> list[dict[str, Any]]:
    """Decode an uploaded CSV or JSON file into raw row dictionaries."""
    if len(content) > MAX_IMPORT_BYTES:
        raise ImportError_(
            f"File is larger than {MAX_IMPORT_BYTES // (1024 * 1024)} MB."
        )

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportError_("File must be UTF-8 encoded text.") from exc

    if not text.strip():
        raise ImportError_("File is empty.")

    lowered = (filename or "").lower()

    if lowered.endswith(".json"):
        return _parse_json(text)
    if lowered.endswith(".csv"):
        return _parse_csv(text)

    # No usable extension: infer from the content instead of refusing.
    if text.lstrip().startswith(("[", "{")):
        return _parse_json(text)
    return _parse_csv(text)


def _parse_json(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportError_(f"Invalid JSON: {exc.msg} (line {exc.lineno}).") from None

    # Accept a bare array, or an object wrapping one under a common key.
    if isinstance(payload, dict):
        for key in ("records", "items", "data", "snapshots"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            raise ImportError_(
                "JSON object must contain a 'records', 'items', 'data' or "
                "'snapshots' array."
            )

    if not isinstance(payload, list):
        raise ImportError_("JSON must be an array of record objects.")

    rows = [row for row in payload if isinstance(row, dict)]
    if not rows:
        raise ImportError_("JSON contained no record objects.")
    return rows


def _parse_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ImportError_("CSV has no header row.")

    known = {
        name
        for name in reader.fieldnames
        if name and name.strip().lower() in FIELD_ALIASES
    }
    if not known:
        raise ImportError_(
            "CSV header has no recognised columns. At minimum it needs "
            "'platform' and 'product_name'."
        )

    rows = [dict(row) for row in reader]
    if not rows:
        raise ImportError_("CSV has a header but no data rows.")
    return rows


def import_dataset(
    db: Session,
    *,
    content: bytes,
    filename: str,
) -> IngestResult:
    """Parse an uploaded dataset and store it as IMPORTED records."""
    rows = parse_rows(content, filename)

    if len(rows) > MAX_IMPORT_ROWS:
        raise ImportError_(
            f"File has {len(rows)} rows; the limit is {MAX_IMPORT_ROWS}."
        )

    records: list[NormalizedRecord] = []
    labels: list[str] = []
    unreadable: list[str] = []

    for index, row in enumerate(rows):
        # +2 for CSV: row 1 is the header, and humans count from 1.
        label = f"row {index + 2}"
        record = row_to_record(row)
        if record is None:
            unreadable.append(f"{label}: missing platform or product_name")
            continue
        records.append(record)
        labels.append(label)

    result = ingest(
        db,
        records,
        source_type=SourceType.IMPORTED,
        search_query=f"import:{filename}" if filename else "import",
        row_labels=labels,
    )

    # Rows that never became records still count as rejections.
    result.rejected += len(unreadable)
    for message in unreadable:
        if len(result.rejected_rows) < 25:
            result.rejected_rows.append(message)

    return result
