"""Amazon.in product-page parser (`/dp/<ASIN>`).

Why product pages: robots.txt for amazon.in (checked 2026-09-30) allows
`/dp/<ASIN>` for the generic `*` agent, and tracking a fixed catalogue is
more precise by ASIN than by re-running searches.

Selectors are scoped to the product's own price/buy-box/detail containers.
Page-wide selectors such as `.a-price` would also match "customers also
bought" carousels and record another product's price as this one's.

Known gaps, left as None rather than guessed:
* `review_count` -- the product page shows the number of *ratings*; the
  written-review count is only on the reviews pages, which are not fetched.
* `mrp` -- absent when Amazon shows no struck-through list price.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from app.live_scraping.base import MarketplaceParser
from app.live_scraping.errors import JavaScriptRenderedError, ParseFailedError, ProductNotFoundError
from app.live_scraping.http_client import FetchedPage
from app.live_scraping.normalize import ParsedProduct, classify_availability, clean_text
from app.live_scraping.schemas import Availability, Marketplace

_ASIN = re.compile(r"^[A-Z0-9]{10}$")
_ASIN_IN_PATH = re.compile(r"/(?:dp|gp/product|gp/aw/d|exec/obidos/asin|o/ASIN)/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE)

_BLOCK_MARKERS = (
    "enter the characters you see below",
    "type the characters you see in this image",
    "to discuss automated access to amazon data please contact",
    "api-services-support@amazon.com",
)
_NOT_FOUND_MARKERS = (
    "we're sorry. the web address you entered is not a functioning page",
    "looking for something?",
    "page not found",
)

# Price containers, most specific first. Each is (container, price-within-it).
_PRICE_SELECTORS = (
    "#corePriceDisplay_desktop_feature_div .priceToPay",
    "#corePriceDisplay_mobile_feature_div .priceToPay",
    "#apex_desktop .priceToPay",
    "#corePrice_desktop .a-price[data-a-color='price']",
    "#corePrice_feature_div .a-price",
    "#priceblock_dealprice",
    "#priceblock_ourprice",
    "#priceblock_saleprice",
)
_MRP_SELECTORS = (
    "#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price.a-text-price[data-a-strike='true'] .a-offscreen",
    "#corePriceDisplay_mobile_feature_div .basisPrice .a-offscreen",
    "#apex_desktop .basisPrice .a-offscreen",
    "#corePrice_desktop .a-price.a-text-price .a-offscreen",
    "#priceblock_listprice",
    "#listPrice",
)
_DISCOUNT_SELECTORS = (
    "#corePriceDisplay_desktop_feature_div .savingsPercentage",
    "#corePriceDisplay_mobile_feature_div .savingsPercentage",
    "#apex_desktop .savingsPercentage",
    "#corePrice_desktop .savingsPercentage",
    "#regularprice_savings",
    "#dealprice_savings",
)
_SELLER_SELECTORS = (
    "#sellerProfileTriggerId",
    "#merchantInfoFeature_feature_div .offer-display-feature-text-message",
    "div[tabular-attribute-name='Sold by'] .tabular-buybox-text",
    "#merchant-info a",
)
_DIMENSION_LABELS = {
    "color_name": "Colour", "size_name": "Size", "style_name": "Style",
    "pattern_name": "Pattern", "configuration": "Configuration",
}


def _text(node: Tag | None) -> str | None:
    return clean_text(node.get_text(" ", strip=True)) if node is not None else None


def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        value = _text(soup.select_one(selector))
        if value:
            return value
    return None


def _price_from(container: Tag) -> str | None:
    """`.a-offscreen` carries the full price; fall back to whole+fraction spans."""
    offscreen = container.select_one(".a-offscreen")
    if offscreen is not None and (value := _text(offscreen)) and any(ch.isdigit() for ch in value):
        return value
    whole = container.select_one(".a-price-whole")
    if whole is not None:
        digits = re.sub(r"[^\d,]", "", whole.get_text())
        fraction = container.select_one(".a-price-fraction")
        cents = re.sub(r"\D", "", fraction.get_text()) if fraction is not None else ""
        if digits:
            return f"{digits}.{cents or '00'}"
    value = _text(container)
    return value if value and any(ch.isdigit() for ch in value) else None


class AmazonParser(MarketplaceParser):
    marketplace = Marketplace.AMAZON
    parser_version = "1"

    def __init__(self, domain: str = "www.amazon.in") -> None:
        self.domain = domain

    # ----------------------------------------------------------- identity

    def extract_product_id(self, url_or_id: str) -> str | None:
        candidate = url_or_id.strip()
        if _ASIN.match(candidate.upper()) and "/" not in candidate:
            return candidate.upper()
        parts = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
        host = (parts.hostname or "").lower()
        if not (host == "amazon.in" or host.endswith(".amazon.in") or host.startswith("amazon.") or ".amazon." in host):
            return None
        match = _ASIN_IN_PATH.search(parts.path)
        return match.group(1).upper() if match else None

    def product_url(self, platform_product_id: str) -> str:
        return f"https://{self.domain}/dp/{platform_product_id}"

    # ------------------------------------------------------------- blocks

    def detect_block(self, page: FetchedPage) -> str | None:
        path = urlsplit(page.final_url).path.lower()
        if "/errors/validatecaptcha" in path:
            return "Amazon redirected to its CAPTCHA page."
        if path.startswith("/ap/signin"):
            return "Amazon required sign-in to view the page."
        head = page.text[:200_000].lower()
        if "validatecaptcha" in head and "<form" in head:
            return "Amazon served a CAPTCHA challenge."
        if any(marker in head for marker in _BLOCK_MARKERS):
            return "Amazon served its automated-access (bot detection) page."
        if page.status_code == 503 and "sorry! something went wrong" in head:
            return "Amazon served its 503 throttling page."
        return None

    # -------------------------------------------------------------- parse

    def parse(self, page: FetchedPage) -> ParsedProduct:
        soup = BeautifulSoup(page.text, "lxml")
        title = _text(soup.select_one("#productTitle")) or _text(soup.select_one("#title"))
        if not title:
            lowered = page.text[:200_000].lower()
            if any(marker in lowered for marker in _NOT_FOUND_MARKERS):
                raise ProductNotFoundError("Amazon reports the product page does not exist.", http_status=page.status_code)
            body_text = soup.body.get_text(" ", strip=True) if soup.body else ""
            if len(body_text) < 200 and soup.find("script") is not None:
                raise JavaScriptRenderedError("Amazon returned a script-only page with no product data in the HTML.")
            raise ParseFailedError("No #productTitle on the page; the layout may have changed.")

        details = self._details(soup)
        availability_text = _first_text(soup, ("#availability", "#availabilityInsideBuyBox_feature_div", "#outOfStock"))
        availability = classify_availability(availability_text)
        if availability is Availability.UNKNOWN and soup.select_one("#add-to-cart-button, #buy-now-button"):
            availability = Availability.IN_STOCK

        asin_input = soup.select_one("input#ASIN[value]")
        return ParsedProduct(
            product_name=title,
            brand=self._brand(soup, details),
            category_path=self._category_path(soup),
            # A model number when Amazon gives one; the "Model Name" only as a fallback.
            model=details.get("item model number") or details.get("model number") or details.get("model name"),
            variant=self._variant(soup),
            current_price_text=self._current_price(soup),
            mrp_text=_first_text(soup, _MRP_SELECTORS),
            discount_text=_first_text(soup, _DISCOUNT_SELECTORS),
            rating_text=(
                (soup.select_one("#acrPopover") or {}).get("title")
                or _text(soup.select_one("#acrPopover .a-icon-alt"))
                or _text(soup.select_one("#averageCustomerReviews .a-icon-alt"))
            ),
            rating_count_text=_text(soup.select_one("#acrCustomerReviewText")),
            review_count_text=None,
            availability=availability,
            availability_text=availability_text,
            seller_name=_first_text(soup, _SELLER_SELECTORS),
            page_product_id=asin_input["value"].strip().upper() if asin_input else None,
        )

    @staticmethod
    def _category_path(soup: BeautifulSoup) -> tuple[str, ...]:
        """The breadcrumb; failing that, only the store department (e.g. "electronics").

        The department menu next to it lists the whole store, not this
        product, so it is never read as the category.
        """
        crumbs = tuple(t for t in (_text(a) for a in soup.select("#wayfinding-breadcrumbs_feature_div ul li a")) if t)
        if crumbs:
            return crumbs
        subnav = soup.select_one("#nav-subnav[data-category]")
        department = clean_text(subnav["data-category"]) if subnav is not None else None
        return (department,) if department else ()

    @staticmethod
    def _current_price(soup: BeautifulSoup) -> str | None:
        for selector in _PRICE_SELECTORS:
            container = soup.select_one(selector)
            if container is not None and (price := _price_from(container)):
                return price
        hidden = soup.select_one("input#attach-base-product-price[value]")
        return hidden["value"] if hidden is not None and hidden["value"].strip() else None

    @staticmethod
    def _details(soup: BeautifulSoup) -> dict[str, str]:
        """Merge the three product-detail layouts into one lowercase-keyed dict."""
        details: dict[str, str] = {}
        for row in soup.select("#productOverview_feature_div tr, #poExpander tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and (key := _text(cells[0])) and (value := _text(cells[-1])):
                details.setdefault(key.lower(), value)
        for row in soup.select(
            "#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr, "
            "#technicalSpecifications_section_1 tr, #prodDetails table.prodDetTable tr, "
            "#productDetails_feature_div table.prodDetTable tr"
        ):
            header, cell = row.find("th"), row.find("td")
            if (key := _text(header)) and (value := _text(cell)):
                details.setdefault(key.lower(), value)
        for item in soup.select("#detailBullets_feature_div li"):
            bold = item.select_one(".a-text-bold")
            if bold is None:
                continue
            key = (_text(bold) or "").replace("‏", "").replace("‎", "").rstrip(" :").strip()
            bold.extract()
            value = _text(item)
            if key and value:
                details.setdefault(key.lower(), value.lstrip(": ").strip())
        return details

    @staticmethod
    def _brand(soup: BeautifulSoup, details: dict[str, str]) -> str | None:
        if details.get("brand"):
            return details["brand"]
        byline = _text(soup.select_one("#bylineInfo"))
        if not byline:
            return None
        for pattern in (r"^Visit the (.+?) Store$", r"^Brand:\s*(.+)$"):
            if match := re.match(pattern, byline, re.IGNORECASE):
                return match.group(1).strip()
        return None

    @staticmethod
    def _variant(soup: BeautifulSoup) -> str | None:
        parts: list[str] = []
        for block in soup.select("#twister [id^='variation_']"):
            label = _text(block.select_one(".a-form-label"))
            value = _text(block.select_one(".selection"))
            if label and value:
                parts.append(f"{label.rstrip(': ')}: {value}")
        if not parts:
            for span in soup.select("span[id^='inline-twister-expanded-dimension-text-']"):
                key = span["id"].removeprefix("inline-twister-expanded-dimension-text-")
                if value := _text(span):
                    parts.append(f"{_DIMENSION_LABELS.get(key, key.replace('_', ' ').title())}: {value}")
        return "; ".join(parts) or None
