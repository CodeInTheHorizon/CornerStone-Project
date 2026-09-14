# Marketplace data sources (Phase 11)

**Status (September 14, 2026): no marketplace is collecting LIVE data.** One LIVE
connector (Flipkart Affiliate API) is implemented and tested against mocked
provider responses. It is disabled until an operator supplies Flipkart affiliate
credentials **and** records Flipkart's written approval for this application's
data use. No Flipkart credentials exist in this workspace, no request has
reached Flipkart, and the database holds **0 LIVE records**.

Nothing here bypasses CAPTCHAs, authentication, robots rules or anti-bot systems.
IMPORTED and DEMO rows are never relabelled LIVE.

## Summary

| Platform | Collector | Official route | Credentials | State in this deployment | LIVE-capable? |
| --- | --- | --- | --- | --- | --- |
| **Flipkart** | `FlipkartCollector` (Affiliate API 1.0) | Flipkart Affiliate API | Affiliate ID + API token | `credentials_missing` | Yes, after credentials **and** approval |
| Amazon | Legacy PA-API 5.0 client, disabled by policy | Creators API (PA-API retired) | Creators API OAuth credentials | `unavailable` | No: terms exclude this use |
| Croma | Inert stub | None public | n/a | `unavailable` | No |
| Alibaba | Inert stub | None for search | n/a | `unavailable` | No |

## Findings per platform (checked 2026-09-14)

### Amazon
- **PA-API 5.0 is retired.** Amazon deprecated it on 30 April 2026 and retired
  the endpoint on 15 May 2026. The retained collector code targets a dead API; a
  registry policy keeps it disabled and advertises no configuration.
- **Replacement: Creators API** (`https://creatorsapi.amazon/catalog/v1/`,
  OAuth 2.0 client credentials, 1-hour bearer tokens, `x-marketplace` header,
  lowerCamelCase `searchItems`/`getItems`).
- **Eligibility:** an accepted Amazon Associate. `403 AssociateNotEligible` means
  fewer than 10 qualified sales in the trailing 30 days, and access is lost after
  30 days without qualifying sales. Initial limits are 1 request/second and
  8,640/day.
- **Fields:** title, brand/byline, classifications, browse nodes and sales rank,
  `offersV2` price, availability, merchant and deal details. No customer-review
  resource, so no product ratings or review counts.
- **Why it is not integrated:** the Associates Program Policies say you will
  not, "without our express prior written approval, access or use Creators API,
  PA API or Data Feeds for the purpose of aggregating, analyzing, extracting, or
  repurposing any Product Advertising Content or in connection with any software
  or other application intended for use by persons or entities that offer
  products on an Amazon Site, or in the direct training or fine-tuning of a
  machine learning and/or foundational model". Non-image content may be cached
  for at most 24 hours. MarketPulse stores history, analyses it, serves sellers
  and trains models, so all of this applies.
- Safe to retain: yes, as a documented, disabled reference. Do not re-enable it.

### Flipkart
- The website answers programmatic requests with reCAPTCHA; it is not used.
- **Official route: Flipkart Affiliate API 1.0**, which is still documented.
  Search is `GET https://affiliate-api.flipkart.net/affiliate/1.0/search.json`
  with `Fk-Affiliate-Id` and `Fk-Affiliate-Token` headers. The earlier claim that
  registration is closed could not be confirmed: the documentation shows no such
  notice. Confirm access in your affiliate account.
- **Limit:** 20 calls per second per affiliate. One token per account; generating
  a new token disables the old one.
- **Terms that matter:** use must be "solely in conjunction with Flipkart's
  platform"; no use "in a similar or competitive platform"; content must not be
  used "in a manner intended to send sales to any site other than the Flipkart
  Site"; no redistribution. The terms say nothing about retaining price history,
  analytics or ML. A cross-marketplace "best platform" tool is in tension with
  these clauses, which is why the connector requires explicit approval.
- Safe to retain: yes. This is the implemented connector.

### Croma
- `croma.com` (including `robots.txt`) returns Akamai HTTP 403 to programmatic
  requests; bypassing it would be anti-bot evasion.
- No public product API. Product data is offered only to selected affiliates of
  third-party networks (for example INRDeals "Super Affiliates") for promoting
  Croma.
- Safe to retain: yes, as an explicit unavailable stub.

### Alibaba
- `robots.txt` disallows `/trade/`, where keyword search lives.
- The Alibaba.com Open API is an ERP/seller API for a paid seller's own products
  and orders. It has no marketplace keyword search, so the previously listed
  `ALIBABA_APP_KEY`/`ALIBABA_APP_SECRET` would not help and are no longer listed.
- Safe to retain: yes, as an explicit unavailable stub.

### Alternatives considered (not integrated)
- **Best Buy Products API:** cache limit of 72 hours; no analysing Best Buy
  pricing for third parties such as other retailers. US-only data.
- **eBay Browse API:** the June 2025 API License Agreement prohibits using eBay
  content to train algorithms or for machine learning.

Neither permits the retained history and ML use MarketPulse needs.

## The Flipkart connector

### Enabling it
Set these in the **backend** environment (Render dashboard or `backend/.env`),
never in frontend `VITE_` variables:

| Variable | Value |
| --- | --- |
| `FLIPKART_AFFILIATE_ID` | Affiliate tracking ID |
| `FLIPKART_AFFILIATE_TOKEN` | Affiliate API token (secret) |
| `FLIPKART_DATA_USE_APPROVED` | `true` **only** after Flipkart confirms in writing that storing observations as history, cross-marketplace analytics and model training are permitted |
| `FLIPKART_TIMEOUT_SECONDS` | Optional, default `15` (1-60) |

Restart the backend afterwards. Marketplace Data should then show **LIVE ready**
for Flipkart.

### Behaviour
- **Gating:** without credentials the state is `credentials_missing`; with
  credentials but no approval it is `approval_required`; otherwise `live`.
  A blocked collector never contacts Flipkart.
- **Request:** one search per refresh (keyword, up to 10 results). The documented
  search API has no pagination; larger requests are capped with a warning. A
  user-supplied category is used only when Flipkart provides none.
- **Retries:** timeouts, network errors and 5xx are retried up to 3 attempts with
  1 s and 2 s backoff. Other 4xx responses are not retried.
- **Rate limits:** a 429 whose `Retry-After` is 5 s or less is waited out once.
  Otherwise the fetch fails with `rate_limited`, the window (or 60 s when the
  header is missing) is recorded, and further refreshes return HTTP 429 without
  contacting Flipkart until it passes.
- **Errors:** 401/403 become `credentials_rejected`; timeouts, network failures,
  5xx, other 4xx and malformed JSON become `provider_error` with a code such as
  `timeout`, `http_503` or `malformed_response`. Provider bodies are never echoed,
  and credentials are redacted from every message.

### Field mapping

| MarketPulse field | Flipkart source | Notes |
| --- | --- | --- |
| `platform` | constant `flipkart` | |
| `product_name` | `productBaseInfoV1.title` | Items without a title are skipped with a warning |
| `external_id` | `productId` | Flipkart SKU id |
| `brand` | `productBrand` | Never guessed from the title |
| `category`, `subcategory` | `categoryPath` / `categoryPaths` | Parent and leaf of the path; string or nested form |
| `price` | `flipkartSpecialPrice.amount`, else `flipkartSellingPrice.amount` | Special price includes extra offers |
| `original_price` | `maximumRetailPrice.amount` | MRP |
| `discount_percentage` | derived from `price` and MRP | Flipkart's `discountPercentage` excludes offers, so it is used only when derivation is impossible and no special price exists |
| `currency` | price `currency` | Default `INR` |
| `availability`, `stock_status` | `inStock` / `isAvailable` | `In Stock` / `Out of Stock` |
| `seller_name` | `productShippingInfoV1.sellerName` | |
| `listing_url` | `productUrl` | Query string removed, which drops the affiliate tracking id |
| `specifications` | `categorySpecificInfoV1.keySpecs` | Up to 10 strings |
| `collection_timestamp` | time the response was received (UTC) | |
| `source_type` | `live` | |

**Always null:** `rating` and `review_count`. The API exposes only the seller's
rating and rating count, which are not product signals and are not substituted.
Images, offers and COD flags are not stored.

The mapping follows Flipkart's published documentation, which has no error-code
table and a sparse search reference. Run the optional real-API test after
enabling it to confirm the mapping against a real response.

## Provenance and history
- Every outbound fetch, successful or failed, is a row in `collection_attempts`
  (migration `0006`). A row records provider id, platform, `source_type=live`,
  query, category, requested limit, start and finish time, outcome, error code,
  sanitized message, HTTP status, retry-after time and received/stored/rejected/
  duplicate counts. LIVE snapshots link to it through `collection_run_id`.
- No credential, header or raw provider body is stored, logged or returned.
- Collection is append-only: every fetch adds new snapshots, and earlier LIVE
  observations are never updated or deleted.
- **True duplicates only:** a LIVE observation is skipped when the same listing
  already has a LIVE snapshot within the previous 10 minutes with identical
  name, prices, discount, currency, rating, review count, availability and
  seller. Any change, or any repeat after 10 minutes, is stored as new history.
  A result with neither a product id nor a URL has no stable identity, so it is
  always appended rather than risk dropping a real observation.
- Refreshing never retrains or reactivates a model.

## API
- `POST /data/collect` returns `source_type`, `provider` and `items_received`,
  plus the existing counts. Errors:
  - `501`: blocked; the detail names the missing variables or the approval
    requirement.
  - `429`: rate limited, with a `Retry-After` header.
  - `502`: credentials rejected or provider failure.
- `GET /data/status` adds, per platform, `state`, `provider`, `live_records`,
  `last_live_observation`, `last_successful_fetch`, `last_failed_fetch`,
  `last_failure_state`, `last_failure_reason` and `retry_after`.
  `required_configuration` lists variable names only.
- `GET /analytics/summary` `refresh_sources` entries add `state` and
  `required_configuration`.

## Tests
- `backend/tests/test_flipkart.py` runs the collector against `httpx.MockTransport`.
  It covers gating, request headers and limits, normalization, missing fields,
  timeouts, network errors, 4xx, 401/403, 5xx, rate limits and malformed
  responses.
- `backend/tests/test_live_collection.py` runs the API, service and database end
  to end with mocked HTTP. It covers provenance, secret handling, append-only
  history, true-duplicate skipping, cooldown enforcement and expiry, every
  runtime state, and confirms no retraining or relabelling.
- `backend/tests/test_flipkart_live.py` is the optional real-API check. It is
  skipped unless `FLIPKART_AFFILIATE_ID`, `FLIPKART_AFFILIATE_TOKEN`,
  `FLIPKART_DATA_USE_APPROVED=true` and `RUN_FLIPKART_LIVE_TEST=1` are set, and
  it writes nothing to a database.

## Known limitations
- No LIVE data exists yet; enabling needs a Flipkart affiliate account and
  Flipkart's approval, neither of which this project holds.
- Product ratings and review counts are unavailable from Flipkart's API, so the
  rating/review trend features stay empty for LIVE Flipkart rows.
- One search returns at most 10 listings; building useful history needs
  repeated refreshes over days. A single fetch cannot support trend prediction.
- Collection is on demand only; there is no scheduler.
- Rate-limit cooldowns and the training lock assume one backend instance.
- Search relevance and result order are Flipkart's; the same keyword may return
  different listings between fetches.
- The model is still trained on DEMO data and remains below its majority-class
  baseline. ML logic was not changed in Phase 11.

## Sources
- [Amazon PA-API 5 deprecation notice](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/paapiv5-deprecation)
- [Creators API migration guide](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/migrating-to-creatorsapi-from-paapi)
- [Creators API SearchItems](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/operations/search-items)
- [Creators API rates](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/concepts/api-rates)
- [Creators API error codes](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/troubleshooting/error-codes-and-messages)
- [Amazon Associates Program Policies](https://affiliate-program.amazon.com/help/operating/policies)
- [Flipkart Affiliate product API reference](https://affiliate.flipkart.com/api-docs/af_prod_ref.html)
- [Flipkart Affiliate API FAQ](https://affiliate.flipkart.com/api-docs/af_faq.html)
- [Flipkart Affiliate API terms of use](https://affiliate.flipkart.com/api-docs/af_tou.html)
- [Flipkart Affiliate registration](https://affiliate.flipkart.com/api-docs/af_register.html)
- [Alibaba.com Open API](https://developer.alibaba.com/docs/doc.htm?treeId=684&articleId=118416&docType=1)
- [Best Buy Developer API terms](https://developer.bestbuy.com/legal)
- [eBay API License Agreement update (EcommerceBytes)](https://www.ecommercebytes.com/2025/07/18/ebay-restricts-developers-from-using-its-data-to-train-ai/)
