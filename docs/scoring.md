# Opportunity Score — v1 Weighted Model

## Overview

Every product tracked in MarketPulse AI gets a 0–100 Opportunity Score per platform. The score answers: "How good an opportunity is this product on this platform for a new seller?"

## Signals and Weights

### Retail platforms (Amazon, Flipkart, Croma)

| Signal | Direction | Default Weight | Notes |
|---|---|---|---|
| Competition (seller/listing count) | Lower is better | 25% | Normalized within category on that platform |
| Price trend (30-day) | Rising is better | 15% | From PriceHistory; neutral when <2 data points |
| Demand proxy (review count) | Higher is better | 20% | Review count normalized against cross-platform max |
| Rating environment | Moderate-to-high is better | 10% | Very high avg ratings = hard to differentiate |
| Discount depth | Shallower is better | 10% | Deep discounting signals margin pressure |
| Price band fit | Within platform's range | 10% | How well the product fits the platform's price band |
| Category momentum | Higher is better | 10% | Category-level trend (placeholder in v1) |

### Wholesale platform (Alibaba)

Alibaba uses a separate wholesale scoring profile:

| Signal | Direction | Default Weight | Notes |
|---|---|---|---|
| MOQ accessibility | Lower MOQ is better | 25% | Minimum order quantity barrier |
| Price range value | Narrow range is better | 25% | Price consistency indicates reliable supplier |
| Supplier trust | Higher rating is better | 20% | Supplier rating on 0–5 scale |
| Demand proxy | Higher is better | 15% | Review/transaction count |
| Price band fit | Competitive pricing | 15% | Unit price competitiveness |

## Inventory Allocation

The suggested inventory allocation (%) is derived proportionally from the scores. If a product scores 60 on Amazon, 80 on Flipkart, and 40 on Croma, the allocation is:

- Amazon: 60/(60+80+40) = 33.3%
- Flipkart: 80/(60+80+40) = 44.4%
- Croma: 40/(60+80+40) = 22.2%

## Missing Signals

When a signal is unavailable (e.g., no price history yet, no reviews), the signal scores at 50 (neutral) and the explanation notes the missing data. The score never returns NaN or null.

## Future: ML Model (P1)

The weighted model is a starting point. An ML model trained on accumulated PriceHistory + outcomes will replace or blend with it behind the same `score(product_id)` interface. The model version will be stored on each OpportunityScore row.
