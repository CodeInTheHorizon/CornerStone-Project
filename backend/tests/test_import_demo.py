"""Phase 4.5 tests: CSV/JSON import, demo dataset, and source-type provenance.

Nothing here touches an external site.
"""

import io
import json
import uuid
from datetime import datetime, timezone

import pytest

from app.models import MarketplaceSnapshot
from app.models.enums import IngestionMode, Platform, SourceType
from app.services import demo_service, import_service
from app.services.import_service import ImportError_, parse_rows, row_to_record


@pytest.fixture
def auth_headers(client):
    email = f"importer_{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/auth/register", json={"email": email, "password": "marketpulse1"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


CSV_CONTENT = """platform,product_name,brand,category,price,mrp,rating,reviews,url,collected_at
amazon,Acme Buds Pro,Acme,wireless earbuds,2499,4999,4.3,1200,https://example.com/a?tag=x,2026-09-01T09:00:00Z
flipkart,Nova Watch Fit,Nova,smartwatches,3999,5999,4.1,340,https://example.com/b,2026-09-01T09:00:00Z
croma,Orbit 65W Charger,Orbit,chargers,1299,1999,4.6,88,https://example.com/c,2026-09-01T09:00:00Z
"""


def upload(client, headers, content: bytes, filename: str):
    return client.post(
        "/data/import",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
    )


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def test_csv_aliases_are_mapped():
    rows = parse_rows(CSV_CONTENT.encode("utf-8"), "data.csv")
    record = row_to_record(rows[0])

    assert record.platform == "amazon"
    assert record.product_name == "Acme Buds Pro"
    # 'mrp' -> original_price, 'reviews' -> review_count, 'url' -> listing_url
    assert record.original_price == 4999.0
    assert record.review_count == 1200
    assert record.listing_url == "https://example.com/a"  # tracking stripped
    assert record.rating == 4.3
    assert record.collection_timestamp.year == 2026


def test_missing_fields_stay_none_not_zero():
    rows = parse_rows(
        b"platform,product_name\namazon,Bare Minimum Product\n", "x.csv"
    )
    record = row_to_record(rows[0])

    assert record.price is None
    assert record.rating is None
    assert record.review_count is None
    assert record.brand is None
    assert record.seller_name is None


def test_discount_is_derived_only_when_absent():
    stated = row_to_record(
        {"platform": "amazon", "product_name": "X", "price": "50", "mrp": "100", "discount": "40"}
    )
    assert stated.discount_percentage == 40.0  # the file's value wins

    derived = row_to_record(
        {"platform": "amazon", "product_name": "X", "price": "50", "mrp": "100"}
    )
    assert derived.discount_percentage == 50.0


def test_row_without_platform_or_name_is_unusable():
    assert row_to_record({"product_name": "No platform"}) is None
    assert row_to_record({"platform": "amazon"}) is None


@pytest.mark.parametrize(
    "content,filename",
    [
        (b"", "x.csv"),
        (b"not json at all", "x.json"),
        (b"a,b,c\n1,2,3\n", "x.csv"),  # no recognised columns
        (b"platform,product_name\n", "x.csv"),  # header only
        (b'{"nope": 1}', "x.json"),
        (b"[]", "x.json"),
    ],
)
def test_unusable_files_are_rejected_with_a_reason(content, filename):
    with pytest.raises(ImportError_):
        parse_rows(content, filename)


def test_format_is_inferred_when_the_extension_is_missing():
    rows = parse_rows(b'[{"platform":"amazon","product_name":"X"}]', "upload")
    assert rows[0]["platform"] == "amazon"


# --------------------------------------------------------------------------
# Import endpoint
# --------------------------------------------------------------------------


def test_import_requires_authentication(client):
    response = client.post(
        "/data/import",
        files={"file": ("x.csv", io.BytesIO(CSV_CONTENT.encode()), "text/csv")},
    )
    assert response.status_code == 401


def test_csv_import_stores_records_as_imported(client, auth_headers, db_session):
    response = upload(client, auth_headers, CSV_CONTENT.encode("utf-8"), "feed.csv")

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "imported"
    assert body["stored"] == 3
    assert body["rejected"] == 0
    assert sorted(body["platforms"]) == ["amazon", "croma", "flipkart"]

    rows = (
        db_session.query(MarketplaceSnapshot)
        .filter(MarketplaceSnapshot.collection_run_id == body["batch_id"])
        .all()
    )
    assert len(rows) == 3
    # Imported data must never be labelled live.
    assert {row.source_type for row in rows} == {SourceType.IMPORTED.value}


def test_json_import_stores_records(client, auth_headers):
    payload = json.dumps(
        [
            {
                "platform": "alibaba",
                "product_name": "Kestrel Power Bank 20000mAh",
                "brand": "Kestrel",
                "category": "power banks",
                "price": 1899,
                "rating": 4.2,
            }
        ]
    ).encode("utf-8")

    body = upload(client, auth_headers, payload, "feed.json").json()

    assert body["stored"] == 1
    assert body["source_type"] == "imported"
    assert body["platforms"] == ["alibaba"]


def test_json_import_accepts_a_wrapped_array(client, auth_headers):
    payload = json.dumps(
        {"records": [{"platform": "amazon", "product_name": "Wrapped Item"}]}
    ).encode("utf-8")

    assert upload(client, auth_headers, payload, "feed.json").json()["stored"] == 1


def test_import_reports_invalid_rows_without_storing_them(client, auth_headers):
    csv_content = (
        "platform,product_name,price\n"
        "amazon,Good Product,999\n"
        "amazon,,499\n"  # no product name
        "notaplatform,Unknown Platform Item,199\n"
    ).encode("utf-8")

    body = upload(client, auth_headers, csv_content, "mixed.csv").json()

    assert body["stored"] == 1
    assert body["rejected"] == 2
    # Each rejection names the row it came from.
    assert any("row 3" in message for message in body["rejected_rows"])
    assert any("row 4" in message for message in body["rejected_rows"])


def test_import_deduplicates_identical_rows(client, auth_headers):
    row = "amazon,Repeated Item,999,DUP-1,2026-09-01T09:00:00Z\n"
    csv_content = (
        "platform,product_name,price,sku,collected_at\n" + row + row + row
    ).encode("utf-8")

    body = upload(client, auth_headers, csv_content, "dupes.csv").json()

    assert body["stored"] == 1
    assert body["duplicates"] == 2


def test_import_keeps_the_same_listing_on_different_dates(client, auth_headers):
    """A time series must survive import; only exact repeats are duplicates."""
    csv_content = (
        "platform,product_name,price,sku,collected_at\n"
        "amazon,Tracked Item,999,TS-1,2026-09-01T09:00:00Z\n"
        "amazon,Tracked Item,949,TS-1,2026-09-02T09:00:00Z\n"
        "amazon,Tracked Item,899,TS-1,2026-09-03T09:00:00Z\n"
    ).encode("utf-8")

    body = upload(client, auth_headers, csv_content, "series.csv").json()

    assert body["stored"] == 3, "same listing on three dates is three observations"
    assert body["duplicates"] == 0


def test_import_rejects_an_unreadable_file(client, auth_headers):
    response = upload(client, auth_headers, b"\xff\xfe\x00binary", "x.csv")
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Demo dataset
# --------------------------------------------------------------------------


def test_demo_dataset_is_present_and_covers_every_platform():
    described = demo_service.describe()

    assert described["record_count"] > 0
    assert set(described["platforms"]) == {p.value for p in Platform}
    assert len(described["categories"]) >= 8


def test_demo_load_tags_every_row_demo(client, auth_headers, db_session):
    body = client.post("/data/demo/load", headers=auth_headers).json()

    assert body["source_type"] == "demo"
    assert body["stored"] > 0

    source_types = {
        row.source_type
        for row in db_session.query(MarketplaceSnapshot)
        .filter(MarketplaceSnapshot.collection_run_id == body["batch_id"])
        .all()
    }
    assert source_types == {SourceType.DEMO.value}


def test_demo_load_preserves_the_time_series(client, auth_headers, db_session):
    client.post("/data/demo/load", headers=auth_headers)

    # One demo listing should appear on several dates, not collapse to one row.
    row = (
        db_session.query(MarketplaceSnapshot)
        .filter(MarketplaceSnapshot.source_type == SourceType.DEMO.value)
        .first()
    )
    same_listing = (
        db_session.query(MarketplaceSnapshot)
        .filter(
            MarketplaceSnapshot.source_type == SourceType.DEMO.value,
            MarketplaceSnapshot.external_id == row.external_id,
        )
        .all()
    )
    assert len(same_listing) > 1
    assert len({s.collection_timestamp for s in same_listing}) == len(same_listing)


def test_repeated_demo_load_replaces_rather_than_accumulates(
    client, auth_headers, db_session
):
    first = client.post("/data/demo/load", headers=auth_headers).json()
    second = client.post("/data/demo/load", headers=auth_headers).json()

    assert first["stored"] == second["stored"]
    total = (
        db_session.query(MarketplaceSnapshot)
        .filter(MarketplaceSnapshot.source_type == SourceType.DEMO.value)
        .count()
    )
    assert total == second["stored"]


def test_demo_load_does_not_touch_imported_rows(client, auth_headers, db_session):
    upload(client, auth_headers, CSV_CONTENT.encode("utf-8"), "keepme.csv")
    before = (
        db_session.query(MarketplaceSnapshot)
        .filter(MarketplaceSnapshot.source_type == SourceType.IMPORTED.value)
        .count()
    )

    client.post("/data/demo/load", headers=auth_headers)

    after = (
        db_session.query(MarketplaceSnapshot)
        .filter(MarketplaceSnapshot.source_type == SourceType.IMPORTED.value)
        .count()
    )
    assert after == before


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------


def test_status_reports_ingestion_mode_and_required_configuration(
    client, auth_headers
):
    body = client.get("/data/status", headers=auth_headers).json()

    amazon = body["platforms"]["amazon"]
    assert amazon["ingestion_mode"] == IngestionMode.LIVE_API.value
    assert amazon["available"] is False  # no credentials in tests
    assert "AMAZON_PAAPI_ACCESS_KEY" in amazon["required_configuration"]

    for name in ("flipkart", "croma"):
        entry = body["platforms"][name]
        assert entry["ingestion_mode"] == IngestionMode.UNAVAILABLE.value
        assert entry["reason"]
        # A hard block: no configuration would unblock it.
        assert entry["required_configuration"] == []


def test_status_lists_source_types_actually_stored(client, auth_headers):
    client.post("/data/demo/load", headers=auth_headers)
    upload(client, auth_headers, CSV_CONTENT.encode("utf-8"), "status.csv")

    body = client.get("/data/status", headers=auth_headers).json()

    assert "demo" in body["platforms"]["amazon"]["source_types_available"]
    assert "imported" in body["platforms"]["amazon"]["source_types_available"]
    assert body["records_by_source_type"]["demo"] > 0
    assert body["records_by_source_type"]["imported"] > 0


def test_status_describes_the_demo_dataset(client, auth_headers):
    body = client.get("/data/status", headers=auth_headers).json()
    demo = body["demo_dataset"]

    assert demo["available"] is True
    assert demo["record_count"] > 0
    assert set(demo["platforms"]) == {p.value for p in Platform}


def test_latest_can_filter_by_source_type(client, auth_headers):
    client.post("/data/demo/load", headers=auth_headers)

    body = client.get(
        "/data/latest?source_type=demo&limit=5", headers=auth_headers
    ).json()

    assert body["count"] > 0
    assert all(item["source_type"] == "demo" for item in body["items"])


def test_demo_records_carry_a_synthetic_marker(client, auth_headers):
    """Demo rows must be identifiable as synthetic from the record itself."""
    client.post("/data/demo/load", headers=auth_headers)

    body = client.get(
        "/data/latest?source_type=demo&limit=3", headers=auth_headers
    ).json()

    for item in body["items"]:
        assert item["source_type"] == "demo"
        assert item["external_id"].startswith("DEMO-")
        assert "demo.invalid" in item["listing_url"]
