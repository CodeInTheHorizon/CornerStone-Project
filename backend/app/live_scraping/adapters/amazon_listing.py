"""Amazon.in listing pages: search results (`/s?k=`) and best-sellers (`/gp/bestsellers/...`).

One listing request yields 20-30 product observations, against one per
product-page request -- the main way to cover thousands of products at a
polite request rate. robots.txt for amazon.in (checked 2026-09-30) allows
both paths for the generic `*` agent; the HTTP client re-checks on every fetch.

Markup notes, from real pages fetched 2026-09-30:

* Search cards are `div[data-component-type="s-search-result"]`. The selling
  price is the first `.a-price` without `.a-text-price`; the MRP is the
  struck `.a-text-price[data-a-strike=true]`. A non-struck `.a-text-price` is
  a unit price ("₹299/count") and is ignored. Cards with no buy box show
  "No featured offers available" and a third-party "(1 new offer)" price --
  that is not the product's price, so current_price stays None.
* The exact rating count is in an `aria-label` ("5,175 ratings"); the visible
  "(5.1K)" is rounded.
* Best-seller pages server-render 30 of their 50 items; the rest are loaded
  by JavaScript and are not collected. They show no MRP.

Fields listing pages never show (seller, model, most availability) stay None;
the product page fills them in on its own, slower schedule.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, quote_plus, urlencode, urlsplit

from bs4 import BeautifulSoup, Tag

from app.live_scraping.adapters.amazon import AmazonParser, _text
from app.live_scraping.base import ListingItem, ListingKind, ListingParser, ListingRef, ParsedListing
from app.live_scraping.errors import ParseFailedError
from app.live_scraping.http_client import FetchedPage
from app.live_scraping.normalize import ParsedProduct, clean_text
from app.live_scraping.schemas import Availability, Marketplace

_RATINGS_LABEL = re.compile(r"^\s*([\d,]+)\s+ratings?\s*$", re.IGNORECASE)
_DISCOUNT = re.compile(r"\((\d{1,2})% off\)")
_LOW_STOCK = re.compile(r"only \d+ left in stock", re.IGNORECASE)
_BESTSELLER_PATH = re.compile(r"^/(?:gp/bestsellers|gp/new-releases|gp/movers-and-shakers)(?:/[\w-]+)*/?$")
_RANK = re.compile(r"#\s*(\d+)")
_NO_RESULTS = ("no results for", "did not match any products")


def _card_availability(card: Tag) -> tuple[Availability, str | None]:
    """Only explicit wording counts; "colours available" must not read as in stock."""
    text = card.get_text(" ", strip=True)
    lowered = text.lower()
    if "currently unavailable" in lowered:
        return Availability.UNAVAILABLE, "Currently unavailable"
    if "out of stock" in lowered:
        return Availability.OUT_OF_STOCK, "Out of stock"
    if match := _LOW_STOCK.search(text):
        return Availability.LOW_STOCK, match.group(0)
    if "no featured offers available" in lowered:
        return Availability.UNKNOWN, "No featured offers available"
    if card.select_one("button[name='submit.addToCart'], [id^='a-autoid'] input[name='submit.addToCart']") or \
            "add to cart" in lowered:
        return Availability.IN_STOCK, None
    return Availability.UNKNOWN, None


class AmazonListingParser(ListingParser):
    marketplace = Marketplace.AMAZON
    parser_version = "1"

    def __init__(self, domain: str = "www.amazon.in") -> None:
        self.domain = domain
        self._product = AmazonParser(domain)

    # -------------------------------------------------------------- refs

    def listing_ref(self, kind: ListingKind, query_or_url: str) -> ListingRef:
        value = query_or_url.strip()
        if not value:
            raise ValueError("A search keyword or listing URL is required.")
        looks_like_url = "://" in value or value.startswith(("www.", "amazon.")) or value.startswith("/")

        if kind is ListingKind.SEARCH:
            if looks_like_url:
                parts = urlsplit(value if "://" in value else f"https://{value.lstrip('/')}")
                self._check_host(parts.hostname)
                keyword = (parse_qs(parts.query).get("k") or [""])[0]
                if parts.path.rstrip("/") != "/s" or not keyword.strip():
                    raise ValueError("An Amazon search URL must look like https://www.amazon.in/s?k=<keyword>.")
            else:
                keyword = value
            # Amazon search ignores case, so "Earbuds" and "earbuds" are one listing.
            keyword = " ".join(keyword.split()).lower()
            return ListingRef(self.marketplace, kind, f"https://{self.domain}/s?k={quote_plus(keyword)}")

        # Best-sellers: a URL, or a category path such as "electronics" or "electronics/1388921031".
        if looks_like_url:
            parts = urlsplit(value if "://" in value else f"https://{value.lstrip('/')}")
            self._check_host(parts.hostname)
            path = re.sub(r"/ref=[^/]*$", "", parts.path).rstrip("/")
        else:
            path = "/gp/bestsellers/" + value.strip("/")
        if not _BESTSELLER_PATH.match(path):
            raise ValueError("A best-sellers listing must be /gp/bestsellers/<category>[/<node>] on amazon.in.")
        return ListingRef(self.marketplace, kind, f"https://{self.domain}{path}")

    def _check_host(self, host: str | None) -> None:
        host = (host or "").lower()
        if host != self.domain and host != self.domain.removeprefix("www."):
            raise ValueError(f"Listing URLs must be on {self.domain}.")

    def page_url(self, ref: ListingRef, page_number: int) -> str:
        if page_number <= 1:
            return ref.url
        key = "page" if ref.kind is ListingKind.SEARCH else "pg"
        joiner = "&" if "?" in ref.url else "?"
        return f"{ref.url}{joiner}{urlencode({key: page_number})}"

    def detect_block(self, page: FetchedPage) -> str | None:
        return self._product.detect_block(page)

    # ------------------------------------------------------------- parse

    def parse_listing(self, page: FetchedPage, kind: ListingKind) -> ParsedListing:
        soup = BeautifulSoup(page.text, "lxml")
        if kind is ListingKind.SEARCH:
            return self._parse_search(soup, page)
        return self._parse_bestsellers(soup)

    def _parse_search(self, soup: BeautifulSoup, page: FetchedPage) -> ParsedListing:
        cards = soup.select('div[data-component-type="s-search-result"]')
        if not cards:
            text = soup.get_text(" ", strip=True).lower()
            if any(marker in text for marker in _NO_RESULTS):
                return ParsedListing(())
            raise ParseFailedError("No search-result cards on the page; the layout may have changed.")

        items: list[ListingItem] = []
        for position, card in enumerate(cards, start=1):
            asin = (card.get("data-asin") or "").strip().upper()
            if not asin or self._product.extract_product_id(asin) != asin:
                continue
            headings = card.select("h2")
            title = _text(headings[-1]) if headings else None
            brand = _text(headings[0]) if len(headings) > 1 else None

            price = next(
                (p for p in card.select(".a-price") if "a-text-price" not in (p.get("class") or [])), None
            )
            price_text = _text(price.select_one(".a-offscreen")) if price is not None else None
            mrp_text = _text(card.select_one(".a-price.a-text-price[data-a-strike='true'] .a-offscreen"))
            discount = _DISCOUNT.search(card.get_text(" ", strip=True))

            rating_text = next(
                (t for t in (_text(n) for n in card.select(".a-icon-alt")) if t and "out of 5" in t), None
            )
            count_text = next(
                (m.group(1) for m in (_RATINGS_LABEL.match(n.get("aria-label") or "") for n in card.select("[aria-label]")) if m),
                None,
            )
            sponsored = card.select_one(".puis-sponsored-label-text") is not None or any(
                (h.get("aria-label") or "").startswith("Sponsored") for h in headings
            )
            availability, availability_text = _card_availability(card)

            items.append(ListingItem(
                platform_product_id=asin,
                rank=position,
                sponsored=sponsored,
                parsed=ParsedProduct(
                    product_name=title,
                    brand=brand,
                    current_price_text=price_text,
                    mrp_text=mrp_text,
                    discount_text=f"{discount.group(1)}%" if discount else None,
                    rating_text=rating_text,
                    rating_count_text=count_text,
                    availability=availability,
                    availability_text=availability_text,
                ),
            ))
        has_next = soup.select_one("a.s-pagination-next[href]") is not None
        return ParsedListing(tuple(items), has_next)

    def _parse_bestsellers(self, soup: BeautifulSoup) -> ParsedListing:
        cells = soup.select("#gridItemRoot")
        if not cells:
            raise ParseFailedError("No best-seller grid on the page; the layout may have changed.")

        heading = next(
            (t for t in (_text(h) for h in soup.select("h1")) if t and t.lower().startswith(("bestsellers in", "best sellers in"))),
            None,
        )
        category = clean_text(re.sub(r"^best\s?sellers in\s+", "", heading, flags=re.IGNORECASE)) if heading else None

        items: list[ListingItem] = []
        for cell in cells:
            holder = cell.select_one("[data-asin]")
            asin = (holder.get("data-asin") if holder else "").strip().upper()
            if not asin or self._product.extract_product_id(asin) != asin:
                continue
            titles = [t for t in (_text(a) for a in cell.select("a[href*='/dp/']")) if t and "₹" not in t]
            title = max(titles, key=len) if titles else clean_text((cell.select_one("img[alt]") or {}).get("alt"))
            rank_match = _RANK.search(_text(cell.select_one(".zg-bdg-text")) or "")
            reviews = cell.select_one("a[href*='/product-reviews/']")
            count_text = _text(reviews.select_one(".a-size-small")) if reviews is not None else None
            price_text = _text(cell.select_one("[class*='p13n-sc-price']")) or _text(cell.select_one(".a-color-price"))

            items.append(ListingItem(
                platform_product_id=asin,
                rank=int(rank_match.group(1)) if rank_match else None,
                sponsored=False,
                parsed=ParsedProduct(
                    product_name=title,
                    category_path=(category,) if category else (),
                    current_price_text=price_text,
                    rating_text=_text(cell.select_one(".a-icon-alt")),
                    rating_count_text=count_text,
                ),
            ))
        has_next = soup.select_one("ul.a-pagination li.a-last a[href]") is not None
        return ParsedListing(tuple(items), has_next)
