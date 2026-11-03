"""Catalog images must survive products whose primary_image_url was never set."""
from types import SimpleNamespace
from uuid import uuid4

from app.api.routes.products import _display_image
from app.models.platform_listing import PlatformListing
from app.models.product import Product
from app.services import rescrape


def _listing(image_url="", image_urls=None):
    return SimpleNamespace(image_url=image_url, image_urls=image_urls)


def test_display_image_prefers_product_image():
    product = SimpleNamespace(primary_image_url="https://cdn.test/product.jpg")
    assert _display_image(product, [_listing("https://cdn.test/listing.jpg")]) == "https://cdn.test/product.jpg"


def test_display_image_falls_back_to_listing_images():
    product = SimpleNamespace(primary_image_url=None)
    assert _display_image(product, [_listing("https://cdn.test/listing.jpg")]) == "https://cdn.test/listing.jpg"
    assert _display_image(product, [_listing("", ["https://cdn.test/gallery.jpg"])]) == "https://cdn.test/gallery.jpg"


def test_display_image_skips_blank_and_placeholder_urls():
    product = SimpleNamespace(primary_image_url="")
    listings = [_listing("https://cdn.test/grey-pixel.gif"), _listing("https://cdn.test/real.jpg")]
    assert _display_image(product, listings) == "https://cdn.test/real.jpg"
    assert _display_image(product, []) is None


def test_rescrape_backfills_missing_product_image(db_session, monkeypatch):
    product = Product(canonical_title=f"Phone {uuid4().hex}", category="electronics")
    db_session.add(product)
    db_session.flush()
    listing = PlatformListing(
        product_id=product.id, platform="amazon", title_on_platform=product.canonical_title, image_url=""
    )
    db_session.add(listing)
    db_session.flush()

    record = SimpleNamespace(
        price=100.0, original_price=None, discount_percentage=None, rating=None, review_count=None,
        seller_count=None, offer_count=None, image_url="https://cdn.test/new.jpg",
    )
    collector = SimpleNamespace(
        status=lambda: SimpleNamespace(available=True),
        collect=lambda *args, **kwargs: SimpleNamespace(records=[record]),
    )
    monkeypatch.setattr(rescrape, "get_collector", lambda platform: collector)

    assert rescrape._rescrape_listing(db_session, listing) is True
    assert product.primary_image_url == "https://cdn.test/new.jpg"
