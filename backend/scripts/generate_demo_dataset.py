"""Generate the bundled demo dataset.

The output is a development and testing fixture. It is **synthetic**: the
brands are invented, and the prices, ratings and review counts are generated,
not observed. Nothing here is real market data, and every record is stored with
source_type = "demo" so it can never be presented as live.

Deterministic by design (fixed seed, fixed base date) so regenerating produces
an identical file and tests stay stable.

Run:  .venv/Scripts/python scripts/generate_demo_dataset.py
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = REPO_ROOT / "data" / "demo" / "electronics_snapshots.json"

SEED = 20260910
# Fixed so the file does not churn on every regeneration.
BASE_DATE = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
DAYS = 5

PLATFORMS = ["amazon", "flipkart", "croma", "alibaba"]

# Deliberately invented brand names. Using real brands would imply these are
# real listings for real products.
BRANDS = ["Acme", "Nova", "Orbit", "Kestrel", "Lumen", "Vantage", "Pico", "Zephyr"]

# category -> (subcategory, [model suffixes], (min_price, max_price))
CATALOGUE: dict[str, tuple[str, list[str], tuple[int, int]]] = {
    "wireless earbuds": ("audio", ["Buds Air", "Buds Pro", "SoundPods"], (999, 7999)),
    "headphones": ("audio", ["Studio 40", "Session X", "OverEar 900"], (1499, 19999)),
    "smartwatches": ("wearables", ["Watch Fit", "Watch GT", "Pulse 2"], (1999, 24999)),
    "chargers": ("power", ["65W GaN", "45W Dual", "30W PD"], (699, 3499)),
    "power banks": ("power", ["10000mAh", "20000mAh", "MagSlim"], (899, 4999)),
    "keyboards": ("peripherals", ["MK Compact", "TKL Pro", "Ergo Split"], (1299, 12999)),
    "mice": ("peripherals", ["Glide 200", "Precision 8K", "Vertical E1"], (499, 8999)),
    "speakers": ("audio", ["Boom 10", "Studio Mini", "Party 200"], (1299, 15999)),
}

AVAILABILITY = ["In Stock", "In Stock", "In Stock", "Only a few left", "Out of Stock"]
SELLERS = {
    "amazon": ["Northwind Retail", "Cloudline Traders", "Acme Direct"],
    "flipkart": ["RetailNet Demo", "SuperComNet Demo", "Orbit Retail"],
    "croma": ["Croma Demo Store", "Infiniti Demo Retail"],
    "alibaba": ["Shenzhen Demo Electronics", "Guangzhou Demo Trading"],
}


def build() -> list[dict]:
    rng = random.Random(SEED)
    records: list[dict] = []

    for category, (subcategory, suffixes, (low, high)) in CATALOGUE.items():
        for platform in PLATFORMS:
            for index, suffix in enumerate(suffixes):
                brand = BRANDS[rng.randrange(len(BRANDS))]
                product_name = f"{brand} {suffix}"
                external_id = f"DEMO-{platform[:2].upper()}-{abs(hash((platform, product_name))) % 100000:05d}"

                list_price = float(rng.randrange(low, high, 100))
                # A price path that drifts, so trend features have something to
                # read once Phase 5 arrives.
                price = round(list_price * rng.uniform(0.62, 0.95), 2)
                rating = round(rng.uniform(3.4, 4.8), 1)
                reviews = rng.randrange(25, 12000)
                seller = SELLERS[platform][index % len(SELLERS[platform])]

                for day in range(DAYS):
                    drift = rng.uniform(-0.035, 0.02)
                    price = max(round(price * (1 + drift), 2), round(list_price * 0.4, 2))
                    reviews += rng.randrange(0, 60)
                    if rng.random() < 0.15:
                        rating = round(
                            min(5.0, max(1.0, rating + rng.choice([-0.1, 0.1]))), 1
                        )

                    discount = round((list_price - price) / list_price * 100, 2)
                    stock = AVAILABILITY[rng.randrange(len(AVAILABILITY))]

                    records.append(
                        {
                            "platform": platform,
                            "product_name": product_name,
                            "brand": brand,
                            "category": category,
                            "subcategory": subcategory,
                            "external_id": external_id,
                            "price": price,
                            "original_price": list_price,
                            "discount_percentage": max(discount, 0.0),
                            "currency": "INR",
                            "rating": rating,
                            "review_count": reviews,
                            "availability": stock,
                            "seller_name": seller,
                            "listing_url": f"https://demo.invalid/{platform}/{external_id.lower()}",
                            "shipping_info": None,
                            "delivery_time": None,
                            "badge": "Demo" if rng.random() < 0.2 else None,
                            "sponsored": rng.random() < 0.15,
                            "stock_status": stock,
                            "collection_timestamp": (
                                BASE_DATE + timedelta(days=day)
                            ).isoformat(),
                        }
                    )

    return records


def main() -> None:
    records = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "_comment": (
                    "SYNTHETIC development fixture for MarketPulse AI. Brands, "
                    "prices, ratings and review counts are generated, not "
                    "observed. Not real market data. Loaded with "
                    'source_type="demo" and never presented as live.'
                ),
                "generated_by": "backend/scripts/generate_demo_dataset.py",
                "seed": SEED,
                "record_count": len(records),
                "records": records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(records)} demo records to {OUTPUT}")


if __name__ == "__main__":
    main()
