"""Explicit, reusable normalization rules for categorical fields.

Kept as plain lookup tables rather than fuzzy matching: a wrong merge silently
corrupts every downstream feature, and a rule you can read is a rule you can
audit. Anything not covered by a rule is lower-cased and whitespace-collapsed
but otherwise left alone -- never guessed at.
"""

from __future__ import annotations

import re
import unicodedata

from app.models.enums import Platform

_WHITESPACE = re.compile(r"\s+")
# Hyphens are separators too: "WH-1000XM5" and "WH 1000XM5" are one product,
# and "Pro - Black" must key the same as "Pro (Black)".
_PUNCTUATION = re.compile(r"[^\w\s]")

#: Spellings seen in real feeds, mapped to the canonical platform value.
PLATFORM_ALIASES: dict[str, str] = {
    "amazon": Platform.AMAZON.value,
    "amazon.in": Platform.AMAZON.value,
    "amazon india": Platform.AMAZON.value,
    "www.amazon.in": Platform.AMAZON.value,
    "flipkart": Platform.FLIPKART.value,
    "flipkart.com": Platform.FLIPKART.value,
    "www.flipkart.com": Platform.FLIPKART.value,
    "croma": Platform.CROMA.value,
    "croma.com": Platform.CROMA.value,
    "tata croma": Platform.CROMA.value,
    "alibaba": Platform.ALIBABA.value,
    "alibaba.com": Platform.ALIBABA.value,
    "ali baba": Platform.ALIBABA.value,
}

#: Category spellings mapped to a canonical category. Only merges that are
#: unambiguous for electronics accessories; anything doubtful is left as-is.
CATEGORY_ALIASES: dict[str, str] = {
    "wireless earbuds": "wireless earbuds",
    "earbuds": "wireless earbuds",
    "true wireless earbuds": "wireless earbuds",
    "tws": "wireless earbuds",
    "in-ear headphones": "wireless earbuds",
    "in ear headphones": "wireless earbuds",
    "headphones": "headphones",
    "headphone": "headphones",
    "over-ear headphones": "headphones",
    "over ear headphones": "headphones",
    "on-ear headphones": "headphones",
    "on ear headphones": "headphones",
    "smartwatches": "smartwatches",
    "smartwatch": "smartwatches",
    "smart watch": "smartwatches",
    "watches": "smartwatches",
    "chargers": "chargers",
    "charger": "chargers",
    "wall charger": "chargers",
    "adapters": "chargers",
    "power banks": "power banks",
    "power bank": "power banks",
    "powerbank": "power banks",
    "portable charger": "power banks",
    "keyboards": "keyboards",
    "keyboard": "keyboards",
    "mechanical keyboard": "keyboards",
    "mice": "mice",
    "mouse": "mice",
    "computer mouse": "mice",
    "speakers": "speakers",
    "speaker": "speakers",
    "bluetooth speaker": "speakers",
}

#: Availability text mapped to a coarse state. Used for availability_change and
#: availability_trend, which need an ordered signal rather than free text.
IN_STOCK_MARKERS = ("in stock", "available", "usually dispatched", "only a few left")
OUT_OF_STOCK_MARKERS = ("out of stock", "unavailable", "sold out", "currently unavailable")


def _basic_clean(value: object) -> str | None:
    """Lower-case, strip accents, collapse whitespace. None stays None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return _WHITESPACE.sub(" ", text).strip().lower() or None


def normalize_platform(value: object) -> str | None:
    """Canonical platform name, or None when it cannot be determined.

    An unrecognised platform is returned cleaned rather than dropped here --
    the dataset builder decides whether to keep it.
    """
    cleaned = _basic_clean(value)
    if cleaned is None:
        return None
    return PLATFORM_ALIASES.get(cleaned, cleaned)


def is_known_platform(value: object) -> bool:
    normalized = normalize_platform(value)
    return normalized in {platform.value for platform in Platform}


def normalize_category(value: object) -> str | None:
    """Canonical category, falling back to the cleaned text.

    Falling back rather than dropping keeps a category we have no rule for
    usable; it simply will not merge with its synonyms.
    """
    cleaned = _basic_clean(value)
    if cleaned is None:
        return None
    if cleaned in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[cleaned]

    # Try again without punctuation, so "in-ear headphones" and
    # "in ear headphones" reach the same rule.
    depunctuated = _WHITESPACE.sub(" ", _PUNCTUATION.sub(" ", cleaned)).strip()
    return CATEGORY_ALIASES.get(depunctuated, cleaned)


def normalize_brand(value: object) -> str | None:
    """Canonical brand token. No alias table: brand naming is too varied to
    merge safely, so this only cleans."""
    return _basic_clean(value)


def normalize_product_name(value: object) -> str | None:
    """Product name reduced to a comparison key.

    Strips punctuation and collapses whitespace so "Acme Buds Pro (Black)" and
    "Acme Buds Pro - Black" compare equal. Deliberately conservative: no token
    reordering, no fuzzy distance.
    """
    cleaned = _basic_clean(value)
    if cleaned is None:
        return None
    without_punctuation = _PUNCTUATION.sub(" ", cleaned)
    return _WHITESPACE.sub(" ", without_punctuation).strip() or None


def availability_state(value: object) -> int | None:
    """Map availability text to 1 (in stock), 0 (out of stock) or None.

    Ordered so a change can be measured. Unrecognised text returns None rather
    than a guess, because guessing "in stock" would invent supply.
    """
    cleaned = _basic_clean(value)
    if cleaned is None:
        return None
    if any(marker in cleaned for marker in OUT_OF_STOCK_MARKERS):
        return 0
    if any(marker in cleaned for marker in IN_STOCK_MARKERS):
        return 1
    return None


def product_key(
    product_name: object,
    brand: object,
    category: object,
) -> str | None:
    """Conservative identity for "the same product".

    Deliberately strict: normalized name + brand + category. Two listings match
    only if all three agree. Ambiguous records stay separate, because a false
    merge fabricates a price history that never happened.
    """
    name = normalize_product_name(product_name)
    if not name:
        return None
    return "|".join(
        [
            name,
            normalize_brand(brand) or "unknown-brand",
            normalize_category(category) or "unknown-category",
        ]
    )
