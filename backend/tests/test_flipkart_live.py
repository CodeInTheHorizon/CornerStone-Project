"""Optional real Flipkart Affiliate API check. Skipped by default.

Runs only when all of these are set in the environment:

    FLIPKART_AFFILIATE_ID, FLIPKART_AFFILIATE_TOKEN
    FLIPKART_DATA_USE_APPROVED=true   (Flipkart has approved this use)
    RUN_FLIPKART_LIVE_TEST=1          (explicit opt-in to an outbound call)

It performs one small search and checks the response still matches the
connector's field mapping. It writes nothing to any database and prints no
credential.
"""

import os

import pytest

from app.scrapers.flipkart import FlipkartCollector

_ENABLED = (
    os.environ.get("RUN_FLIPKART_LIVE_TEST") == "1"
    and os.environ.get("FLIPKART_AFFILIATE_ID")
    and os.environ.get("FLIPKART_AFFILIATE_TOKEN")
    and os.environ.get("FLIPKART_DATA_USE_APPROVED", "").lower() == "true"
)


@pytest.mark.skipif(not _ENABLED, reason="Real Flipkart API test not enabled (needs credentials, approval and RUN_FLIPKART_LIVE_TEST=1)")
def test_real_flipkart_search_matches_the_field_mapping():
    collector = FlipkartCollector(
        affiliate_id=os.environ["FLIPKART_AFFILIATE_ID"],
        affiliate_token=os.environ["FLIPKART_AFFILIATE_TOKEN"],
        data_use_approved=True,
    )
    outcome = collector.collect("wireless earbuds", max_items=3)

    assert outcome.records, f"No records; warnings: {outcome.warnings}"
    for record in outcome.records:
        assert record.platform == "flipkart"
        assert record.product_name
        assert record.external_id, "productId missing: check productBaseInfoV1 mapping"
        assert record.price is None or record.price > 0
        assert record.listing_url is None or "affid" not in record.listing_url
        # The Affiliate API exposes no product rating/review count.
        assert record.rating is None and record.review_count is None
