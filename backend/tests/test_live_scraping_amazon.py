"""Amazon product-page parser against synthetic fixtures (no network)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.live_scraping.adapters.amazon import AmazonParser
from app.live_scraping.errors import JavaScriptRenderedError, ParseFailedError, ProductNotFoundError
from app.live_scraping.http_client import FetchedPage
from app.live_scraping.normalize import normalize
from app.live_scraping.schemas import Availability, Marketplace

FIXTURES = Path(__file__).parent / "fixtures" / "live_scraping"
URL = "https://www.amazon.in/dp/B0TESTAC01"
parser = AmazonParser()


def _page(name_or_html: str, *, status: int = 200, final_url: str = URL) -> FetchedPage:
    path = FIXTURES / name_or_html
    text = path.read_text(encoding="utf-8") if path.suffix == ".html" and path.exists() else name_or_html
    return FetchedPage(URL, final_url, status, text, "text/html", 10, 1)


def _observe(name: str):
    return normalize(
        parser.parse(_page(name)), marketplace=Marketplace.AMAZON, platform_product_id="B0TESTAC01",
        product_url=URL, collected_at=datetime(2026, 9, 30, tzinfo=timezone.utc), source="amazon-html/1",
    )


def test_full_product_page():
    obs = _observe("amazon_product.html")
    assert obs.product_name == "Acme Buds Pro Wireless Earbuds with 40H Playtime, ENC Mic"
    assert obs.brand == "Acme"
    assert obs.category == "In-Ear"
    assert obs.category_path == "Electronics > Headphones, Earbuds & Accessories > In-Ear"
    assert obs.model == "ACM-BP-40"
    assert obs.variant == "Colour: Midnight Black"
    assert obs.current_price == Decimal("1299.00")
    assert obs.mrp == Decimal("3999.00")
    assert obs.discount_percentage == Decimal("67.52")  # recomputed; page's "-68%" is within tolerance
    assert obs.rating == Decimal("4.20")
    assert obs.rating_count == 12845
    assert obs.review_count is None  # not on the product page; not guessed
    assert obs.availability is Availability.IN_STOCK
    assert obs.seller_name == "Acme Retail India"
    assert obs.warnings == ()


def test_carousel_prices_are_never_used():
    obs = _observe("amazon_unavailable.html")
    assert obs.current_price is None and obs.mrp is None  # the ₹899 carousel card is ignored


def test_unavailable_page_with_legacy_layout():
    obs = _observe("amazon_unavailable.html")
    assert obs.brand == "Zento"
    assert obs.model == "ZPB-20K"
    assert obs.variant == "Colour: Blue; Size: 20000 mAh"
    assert obs.rating == Decimal("3.90")
    assert obs.rating_count == 102311
    assert obs.availability is Availability.UNAVAILABLE
    assert obs.warnings == ()


def test_captcha_page_is_detected():
    assert "CAPTCHA" in parser.detect_block(_page("amazon_captcha.html"))


@pytest.mark.parametrize("final_url", [
    "https://www.amazon.in/errors/validateCaptcha?amzn=x",
    "https://www.amazon.in/ap/signin?openid.return_to=x",
])
def test_block_and_sign_in_redirects_are_detected(final_url):
    assert parser.detect_block(_page("<html></html>", final_url=final_url)) is not None


def test_normal_product_page_is_not_a_block():
    assert parser.detect_block(_page("amazon_product.html")) is None


def test_not_found_page():
    html = "<html><body><h1>Looking for something?</h1><p>We're sorry. The Web address you entered is not a functioning page on our site.</p></body></html>"
    with pytest.raises(ProductNotFoundError):
        parser.parse(_page(html))


def test_script_only_page_is_js_rendered():
    with pytest.raises(JavaScriptRenderedError):
        parser.parse(_page("<html><body><div id='app'></div><script src='/app.js'></script></body></html>"))


def test_unrecognised_layout_is_a_parse_failure():
    with pytest.raises(ParseFailedError):
        parser.parse(_page("<html><body>" + "<p>Some unrelated long content.</p>" * 20 + "</body></html>"))


def test_asin_mismatch_is_recorded_as_a_warning():
    html = _page("amazon_product.html").text.replace('value="B0TESTAC01"', 'value="B0OTHER001"')
    obs = normalize(parser.parse(_page(html)), marketplace=Marketplace.AMAZON, platform_product_id="B0TESTAC01",
                    product_url=URL, collected_at=datetime(2026, 9, 30, tzinfo=timezone.utc), source="s")
    assert "page reports product id B0OTHER001" in obs.warnings


@pytest.mark.parametrize(("value", "asin"), [
    ("B0TESTAC01", "B0TESTAC01"),
    ("b0testac01", "B0TESTAC01"),
    ("https://www.amazon.in/Acme-Buds-Pro/dp/B0TESTAC01/ref=sr_1_3?keywords=earbuds", "B0TESTAC01"),
    ("https://www.amazon.in/gp/product/B0TESTAC01?th=1", "B0TESTAC01"),
    ("amazon.in/dp/B0TESTAC01", "B0TESTAC01"),
    ("https://www.flipkart.com/dp/B0TESTAC01", None),
    ("https://www.amazon.in/s?k=earbuds", None),
])
def test_extract_product_id(value, asin):
    assert parser.extract_product_id(value) == asin


def test_model_from_current_product_details_table():
    # Layout seen on amazon.in in 2026-09: an id-less prodDetTable under #prodDetails.
    html = """<html><body><span id="productTitle">Charger</span>
      <div id="productDetails_feature_div"><div id="prodDetails"><table class="a-keyvalue prodDetTable">
        <tr><th class="prodDetSectionEntry"> Model Name </th><td class="prodDetAttrValue"> Travel Adapter </td></tr>
        <tr><th class="prodDetSectionEntry"> Model Number </th><td class="prodDetAttrValue"> EP-T2510N </td></tr>
      </table></div></div>
      <table class="prodDetTable"><tr><th>Model Number</th><td>OTHER-PRODUCT</td></tr></table>
    </body></html>"""
    assert parser.parse(_page(html)).model == "EP-T2510N"


def test_department_is_the_only_category_fallback():
    html = """<html><body><div id="nav-subnav" data-category="electronics">Mobiles Laptops Audio Cameras</div>
      <span id="productTitle">Thing</span></body></html>"""
    assert parser.parse(_page(html)).category_path == ("electronics",)


def test_canonical_url_drops_tracking():
    assert parser.product_url("B0TESTAC01") == "https://www.amazon.in/dp/B0TESTAC01"
