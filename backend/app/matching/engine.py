"""Specification extraction and multi-stage canonical product matching engine.

Combines:
1. Deterministic specification extraction (Brand, Model, RAM, Storage, 5G/4G, Variant).
2. Hard conflict rejection (e.g. 128GB vs 256GB storage or 6GB vs 8GB RAM will never match).
3. RapidFuzz token-based similarity scoring (token_sort_ratio, token_set_ratio).
4. Canonical Product resolution and linkage across Amazon, Flipkart, Meesho, etc.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product

MATCH_THRESHOLD = 0.72
HIGH_CONFIDENCE_THRESHOLD = 0.85

_NOISE_WORDS = re.compile(
    r"\b(with|for|and|the|new|latest|best|original|genuine|pack of|combo|set|offer|deal|hot|official|warranty|free|delivery)\b",
    re.IGNORECASE,
)
_PARENS = re.compile(r"[\(\)\[\]\{\}]")
_MULTI_SPACE = re.compile(r"\s+")

# RAM patterns: "8GB RAM", "8 GB RAM", "8GB", "8gb", or in "8/128", "8GB/128GB"
_RAM_PATTERN = re.compile(r"\b(\d{1,2})\s*(?:gb|g)\s*(?:ram)?\b", re.IGNORECASE)
# Storage / ROM patterns: "128GB ROM", "128 GB Storage", "128GB", "256GB", "512GB", "1TB", "64GB"
_STORAGE_PATTERN = re.compile(r"\b(\d{2,4})\s*(?:gb|g|tb)\s*(?:rom|storage|internal)?\b", re.IGNORECASE)
# Combined shorthand: "8/128", "8GB/128GB", "8+128", "8GB+128GB"
_RAM_STORAGE_COMBO = re.compile(r"\b(\d{1,2})\s*(?:gb)?\s*[\/\+]\s*(\d{2,4})\s*(?:gb)?\b", re.IGNORECASE)

KNOWN_BRANDS = [
    "Samsung", "Apple", "Xiaomi", "Redmi", "Realme", "OnePlus", "Oppo", "Vivo",
    "Motorola", "Moto", "Poco", "Google", "Sony", "Nokia", "Infinix", "Tecno",
    "Lava", "Asus", "Lenovo", "Dell", "HP", "Acer", "boAt", "Noise", "Boult",
    "Zebronics", "Fire-Boltt", "Fastrack", "JBL", "Sony", "Philips"
]


@dataclass
class ProductSpecs:
    brand: str | None = None
    model: str | None = None
    ram: str | None = None
    storage: str | None = None
    network: str | None = None # e.g. "5G", "4G"
    color: str | None = None
    variant: str | None = None
    raw_specs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def extract_specifications(title: str, existing_specs: dict[str, Any] | None = None) -> ProductSpecs:
    """Extract structured product specifications from listing title and raw specs."""
    specs = ProductSpecs()
    if existing_specs:
        specs.raw_specs = dict(existing_specs)

    # 1. Brand extraction
    for b in KNOWN_BRANDS:
        pattern = rf"\b{re.escape(b)}\b"
        if re.search(pattern, title, re.IGNORECASE):
            # Normalize Brand casing
            if b.lower() == "moto":
                specs.brand = "Motorola"
            else:
                specs.brand = b.capitalize() if b.islower() else b
            break

    # 2. Combined RAM/Storage shorthand (e.g., "8/128" or "8GB/128GB")
    combo_match = _RAM_STORAGE_COMBO.search(title)
    if combo_match:
        r, s = combo_match.group(1), combo_match.group(2)
        specs.ram = f"{r}GB"
        specs.storage = f"{s}GB"
    else:
        # Individual RAM
        ram_matches = _RAM_PATTERN.findall(title)
        if ram_matches:
            # Usually RAM is 2, 3, 4, 6, 8, 12, 16, 24, 32
            valid_ram = [r for r in ram_matches if int(r) in (2, 3, 4, 6, 8, 12, 16, 24, 32)]
            if valid_ram:
                specs.ram = f"{valid_ram[0]}GB"

        # Individual Storage
        storage_matches = _STORAGE_PATTERN.findall(title)
        if storage_matches:
            valid_storage = [s for s in storage_matches if int(s) in (16, 32, 64, 128, 256, 512, 1024)]
            # If same as RAM, discard to avoid collision
            if specs.ram:
                ram_num = specs.ram.replace("GB", "")
                valid_storage = [s for s in valid_storage if s != ram_num]
            if valid_storage:
                specs.storage = f"{valid_storage[0]}GB"

    # 3. 5G / 4G Network
    if re.search(r"\b5G\b", title, re.IGNORECASE):
        specs.network = "5G"
    elif re.search(r"\b4G\b", title, re.IGNORECASE):
        specs.network = "4G"

    # 4. Model extraction (e.g. Galaxy A56, iPhone 15, Redmi Note 13)
    # Extract model by looking after brand
    if specs.brand:
        brand_idx = re.search(rf"\b{re.escape(specs.brand)}\b", title, re.IGNORECASE)
        if brand_idx:
            after_brand = title[brand_idx.end():].strip()
            # Stop at commas, brackets, or memory specs
            parts = re.split(r"[,(\[\{]|\b\d+\s*GB\b|\b\d+\/\d+\b", after_brand, flags=re.IGNORECASE)
            model_candidate = parts[0].strip()
            if model_candidate:
                specs.model = model_candidate

    # 5. Composite Variant
    variant_parts = []
    if specs.ram:
        variant_parts.append(specs.ram)
    if specs.storage:
        variant_parts.append(specs.storage)
    if specs.network:
        variant_parts.append(specs.network)
    if variant_parts:
        specs.variant = " / ".join(variant_parts)

    return specs


def normalize_title(title: str) -> str:
    """Strip punctuation, noise words and extra spaces for fuzzy matching."""
    t = title.lower().strip()
    t = _PARENS.sub(" ", t)
    t = _NOISE_WORDS.sub(" ", t)
    t = _MULTI_SPACE.sub(" ", t).strip()
    return t


def compute_match_confidence(
    title_a: str,
    title_b: str,
    specs_a: ProductSpecs,
    specs_b: ProductSpecs,
) -> float:
    """Compute high-precision match score combining deterministic rules & RapidFuzz."""
    # Rule 1: Brand Conflict
    if specs_a.brand and specs_b.brand:
        if specs_a.brand.lower() != specs_b.brand.lower():
            return 0.0

    # Rule 2: Hardware Specification Conflict (RAM or Storage mismatch)
    if specs_a.ram and specs_b.ram and specs_a.ram.lower() != specs_b.ram.lower():
        return 0.0
    if specs_a.storage and specs_b.storage and specs_a.storage.lower() != specs_b.storage.lower():
        return 0.0
    if specs_a.network and specs_b.network and specs_a.network.lower() != specs_b.network.lower():
        return 0.0

    # Clean titles
    norm_a = normalize_title(title_a)
    norm_b = normalize_title(title_b)

    # RapidFuzz token sorting and set ratio
    sort_ratio = fuzz.token_sort_ratio(norm_a, norm_b) / 100.0
    set_ratio = fuzz.token_set_ratio(norm_a, norm_b) / 100.0
    fuzzy_score = (sort_ratio * 0.5) + (set_ratio * 0.5)

    # Specification Agreement Bonus
    bonus = 0.0
    if specs_a.model and specs_b.model:
        model_sim = fuzz.token_set_ratio(specs_a.model.lower(), specs_b.model.lower()) / 100.0
        if model_sim > 0.80:
            bonus += 0.15
        elif model_sim < 0.40:
            return 0.0 # Clear model contradiction

    if specs_a.ram and specs_b.ram and specs_a.ram.lower() == specs_b.ram.lower():
        bonus += 0.05
    if specs_a.storage and specs_b.storage and specs_a.storage.lower() == specs_b.storage.lower():
        bonus += 0.05

    final_score = min(1.0, fuzzy_score * 0.8 + bonus)
    return round(final_score, 4)


def match_or_create_product(
    db: Session,
    *,
    title: str,
    brand: str | None = None,
    category: str = "electronics",
    subcategory: str | None = None,
    image_url: str | None = None,
    raw_specs: dict[str, Any] | None = None,
) -> tuple[Product, float]:
    """Find best canonical Product using RapidFuzz + deterministic specs, or create new one."""
    extracted_specs = extract_specifications(title, raw_specs)
    effective_brand = brand or extracted_specs.brand

    stmt = select(Product).where(Product.category == category)
    if effective_brand:
        stmt = stmt.where(Product.brand == effective_brand)
    candidates = db.execute(stmt).scalars().all()

    best_match: Product | None = None
    best_score: float = 0.0

    for cand in candidates:
        cand_specs = extract_specifications(
            cand.canonical_title,
            getattr(cand, "specifications", None),
        )
        score = compute_match_confidence(
            title,
            cand.canonical_title,
            extracted_specs,
            cand_specs,
        )
        if score > best_score:
            best_score = score
            best_match = cand

    if best_match is not None and best_score >= MATCH_THRESHOLD:
        if image_url and not best_match.primary_image_url:
            best_match.primary_image_url = image_url
        return best_match, best_score

    # Construct clean canonical name
    canonical_parts = []
    if effective_brand:
        canonical_parts.append(effective_brand)
    if extracted_specs.model:
        canonical_parts.append(extracted_specs.model)
    elif title:
        canonical_parts.append(title[:60])
    if extracted_specs.variant:
        canonical_parts.append(f"({extracted_specs.variant})")

    canonical_title = " ".join(canonical_parts) if canonical_parts else title

    product = Product(
        canonical_title=canonical_title,
        brand=effective_brand,
        model_number=extracted_specs.model,
        category=category,
        subcategory=subcategory,
        primary_image_url=image_url,
    )
    # If the product model has specifications or variant columns, set them
    if hasattr(product, "variant") and extracted_specs.variant:
        setattr(product, "variant", extracted_specs.variant)
    if hasattr(product, "specifications") and extracted_specs.to_dict():
        setattr(product, "specifications", extracted_specs.to_dict())

    db.add(product)
    db.flush()
    return product, 1.0
