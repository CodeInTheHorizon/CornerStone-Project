# PRD Requirement Status — MarketPulse AI

Generated: 2026-09-24 | Codebase: `marketPulse_AI/`

---

## 8.1 Scraping — real time, all four platforms

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-SCR-01 | 🟡 Partial | `backend/app/scrapers/base.py` — `MarketplaceCollector` ABC with `collect(keyword, category, max_items)`. Amazon: 3 adapters (`amazon.py` PA-API, `amazon_web.py` HTML, `dataforseo_amazon.py` API). Flipkart: `flipkart.py` Affiliate API. | Interface is `collect()` not `search()/fetch_listing()` per PRD. Croma: stub only (`UnavailableCollector`). Alibaba: stub only. No per-listing `fetch_listing()` method on any collector. |
| REQ-SCR-02 | 🟡 Partial | `backend/app/services/collection_service.py` — fan-out collection across registered collectors. | No search-time TTL cache; results are stored in DB but not cached for repeat queries. No real-time on-demand search from the frontend — collection is manually triggered. |
| REQ-SCR-03 | 🟡 Partial | `MarketplaceSnapshot` model captures: title, price, original_price, discount_pct, rating, review_count, seller_name, listing_url, availability, badge, specs. | **No `image_url` field anywhere** — not on the model, not captured by any scraper. No seller/offer count field. No MOQ/price_range for Alibaba. |
| REQ-SCR-04 | ❌ Not started | — | No scheduled re-scraping job, no TrackedProduct model, no celery/apscheduler/cron. `collection_service.py` notes "reachable from a future scheduled job" but none exists. |
| REQ-SCR-05 | 🟡 Partial | `amazon_web.py` has UA rotation (`_AGENTS` list), retry with backoff, proxy support via config (`AMAZON_WEB_PROXY`). `flipkart.py` has retry. | No captcha/block detection. No proxy config for Flipkart. Croma/Alibaba are stubs. |
| REQ-SCR-06 | ❌ Not started | — | No `is_stale` flag on any model. No stale-data fallback mechanism. One platform failure does not block others (collection_service handles per-platform errors), but no cached-stale serving. |
| REQ-SCR-07 | ❌ Not started | — | No headless browser / Playwright integration for JS-rendered pages. |
| REQ-SCR-08 | 🟡 Partial | `GET /status` returns per-platform collector availability and access method. | No success rate, latency, or last-successful-scrape tracking. |
| REQ-SCR-09 | ❌ Not started | — | No `docs/scraping-policy.md`. |

## 8.2 Images — every item listed with its image

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-IMG-01 | ❌ Not started | — | No `image_url` field on `MarketplaceSnapshot`. No scraper captures images. |
| REQ-IMG-02 | ❌ Not started | — | No product images rendered anywhere in the frontend. |
| REQ-IMG-03 | ❌ Not started | — | No image proxy/cache service. |
| REQ-IMG-04 | ❌ Not started | — | No image placeholder component for missing images. |
| REQ-IMG-05 | ❌ Not started | — | No gallery image capture. |

## 8.3 Data storage and history

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-DATA-01 | 🟡 Partial | `MarketplaceSnapshot`, `User`, `Prediction`, `PriceAlert` models exist with Alembic migrations. | Missing: `Product` (canonical), `PlatformListing` (distinct from snapshot), `PriceHistory` (dedicated), `OpportunityScore`, `TrackedProduct`. |
| REQ-DATA-02 | 🟡 Partial | `MarketplaceSnapshot` rows are append-only (new row per observation). | No dedicated `PriceHistory` table; history is inferred from snapshots. Works but not the PRD's intended schema. |
| REQ-DATA-03 | ❌ Not started | — | No cross-platform product matching, no canonical Product model, no match confidence. |
| REQ-DATA-04 | ❌ Not started | — | No data retention policy or cleanup job. |

## 8.4 Opportunity Score engine

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-SCORE-01 | 🟡 Partial | `backend/app/ml/opportunity.py` — 7-signal weighted model computing 0–100 score. | Scores computed per-snapshot, not per-canonical-product-per-platform. No cross-platform comparison in a single scoring call. |
| REQ-SCORE-02 | 🟡 Partial | `opportunity.py` has `EXPLANATIONS` dict per signal. `prediction_service.py` assembles ranking. | Explanations are static formula descriptions, not dynamic plain-English (e.g., "Flipkart: 12 sellers vs. 48 on Amazon"). |
| REQ-SCORE-03 | ✅ Done | `opportunity.py` — transparent weighted model with configurable `WEIGHTS` dict, `FORMULA_VERSION`. | — |
| REQ-SCORE-04 | ❌ Not started | — | No inventory allocation suggestion computed anywhere. |
| REQ-SCORE-05 | 🟡 Partial | `backend/app/ml/training.py` — sklearn pipeline training. `prediction_service.py` — model inference. | Model exists but doesn't blend with the weighted opportunity score behind one interface. |
| REQ-SCORE-06 | ❌ Not started | — | Alibaba is a stub; no wholesale-specific scoring profile (MOQ, supplier rating, price range). |
| REQ-SCORE-07 | ❌ Not started | — | No seller-specific cost/margin inputs. |

## 8.5 Business dashboard (post-login home)

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-DASH-01 | ✅ Done | `frontend/src/App.tsx` — `/dashboard` is the post-login route. `DashboardPage.tsx` is the landing page. | — |
| REQ-DASH-02 | ❌ Not started | — | No time-of-day greeting. Dashboard shows "Welcome back" but not personalized with name or time. |
| REQ-DASH-03 | 🟡 Partial | `DashboardPage.tsx` — has summary cards (Collected, Platforms, Latest Prediction, Model Quality). | Cards show ML metrics, not business metrics (Products Tracked, Market Opportunities, Price Drops, High Competition Alerts, Trending). Not clickable to filter. |
| REQ-DASH-04 | ❌ Not started | — | No Trending Products, Top Opportunities, or Price Movement sections with product image cards. |
| REQ-DASH-05 | ❌ Not started | — | No "today in the market" / since-last-visit framing. |
| REQ-DASH-06 | ❌ Not started | — | No sparkline per product from price history. |
| REQ-DASH-07 | 🟡 Partial | `OnboardingGuide.tsx` — stepper for new users (load demo → build dataset → train → predict). | Guides toward ML workflow, not toward searching/tracking a first product. |

## 8.6 Product search, list and comparison

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-LIST-01 | ❌ Not started | — | No search bar that triggers live 4-platform scraping and shows results side-by-side with images. Existing search is within stored data only. |
| REQ-LIST-02 | ❌ Not started | — | No tracked product list page. `MarketplaceDataPage.tsx` shows stored snapshots but without images, score badges, or best-platform indicators. |
| REQ-LIST-03 | 🟡 Partial | `ComparePage.tsx` — side-by-side comparison of products. `AnalyticsPage.tsx` — price history charts. | No per-platform comparison table with scores + explanations + allocation suggestion on a single product detail page. No gallery image. |
| REQ-LIST-04 | ❌ Not started | — | No stale data indicators. |
| REQ-LIST-05 | 🟡 Partial | `frontend/src/lib/export.ts` — CSV and JSON export. `backend/app/api/routes/export.py` — server-side CSV export. | No PDF export. |

## 8.7 Alerts and trends

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-ALERT-01 | ❌ Not started | — | `PriceAlert` exists but is a manual threshold alert. No automatic price-drop detection (≥X% drop vs. previous observation). |
| REQ-ALERT-02 | ❌ Not started | — | No high-competition alert (seller count threshold or % increase). |
| REQ-ALERT-03 | ❌ Not started | — | No trending detection (review velocity, rank movement). |
| REQ-ALERT-04 | 🟡 Partial | `AlertsPage.tsx` — alert list with create/delete. `NotificationBell.tsx` — triggered count badge. | Alerts are manual price thresholds only, not the 4 types from PRD. No read/unread state. Metric cards not driven by alert counts. |
| REQ-ALERT-05 | ❌ Not started | — | No email/WhatsApp notifications. |

## 8.8 Auth and accounts

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-AUTH-01 | 🟡 Partial | `backend/app/auth/` — JWT auth with email/password login + registration. `LoginPage.tsx`, `RegisterPage.tsx`. | No password reset flow. |
| REQ-AUTH-02 | 🟡 Partial | `User` model has `full_name` and `email`. | No `business_type` field (retailer/wholesaler/manufacturer/other). |
| REQ-AUTH-03 | ❌ Not started | — | No Google sign-in. |

## 8.9 Non-functional

| Requirement | Status | Evidence | Gaps |
|---|---|---|---|
| REQ-NFR-01 | ❌ Not started | — | No real-time 4-platform search exists, so latency budget is N/A. No streaming/progressive per-platform rendering. |
| REQ-NFR-02 | ✅ Done | Dashboard loads from pre-computed/stored data. No live scraping on dashboard load. | — |
| REQ-NFR-03 | ✅ Done | Responsive Tailwind CSS layout throughout. Mobile-friendly sidebar drawer. | — |
| REQ-NFR-04 | 🟡 Partial | 25 test files exist: scraper parsers (`test_scrapers.py`, `test_amazon_web.py`, `test_flipkart.py`), auth, models, analytics, training, prediction, end-to-end. | Missing: Croma/Alibaba parser tests (stubs). No integration test for search → list → score flow (flow doesn't exist yet). |
| REQ-NFR-05 | 🟡 Partial | Python `logging` used throughout backend with structured log messages. | No dedicated error tracking service (Sentry, etc.). |

---

## Summary

| Status | Count |
|---|---|
| ✅ Done | 4 |
| 🟡 Partial | 19 |
| ❌ Not started | 22 |

## Conflicts with existing code

1. **Collector interface**: PRD wants `search(query, limit)` + `fetch_listing(url_or_id)`. Existing code uses `collect(keyword, category, max_items) -> CollectionOutcome`. **Resolution**: Extend `MarketplaceCollector` with `search()` and `fetch_listing()` methods; keep `collect()` as the batch-ingest path.
2. **Data model**: PRD wants normalized `Product` + `PlatformListing` + `PriceHistory`. Existing code uses a flat `MarketplaceSnapshot`. **Resolution**: Add the new tables alongside snapshots; the snapshot table continues to serve the existing ML pipeline.
3. **Dashboard focus**: PRD wants a business dashboard (tracked products, opportunities, price drops). Existing dashboard is ML-focused (model accuracy, training, prediction). **Resolution**: Rebuild dashboard sections to show business metrics; keep ML pages accessible via sidebar but not as the landing page.
4. **Alert model**: PRD wants 4 alert types (price_drop, high_competition, trending, new_opportunity) with read/unread. Existing `PriceAlert` is manual threshold-based. **Resolution**: Create new `Alert` model for auto-detected alerts alongside existing `PriceAlert`.

## Phase-by-phase gap list

### Phase 1 — Scraping (largest gap)
- Build Croma scraper (currently stub)
- Build Alibaba scraper (currently stub)
- Add `image_url` field to `MarketplaceSnapshot` + all scrapers
- Add `search()` and `fetch_listing()` to collector interface
- Implement real-time on-demand search API endpoint
- Result cache with TTL
- Image proxy/cache service
- Headless browser support for JS-rendered pages
- `docs/scraping-policy.md`

### Phase 2 — Storage
- `Product` (canonical) model + migration
- `PlatformListing` model + migration
- `TrackedProduct` model + migration
- `PriceHistory` dedicated model (or reuse snapshots with clear interface)
- Cross-platform product matcher with confidence
- Scheduled re-scrape background job
- `is_stale` flag and stale-data serving

### Phase 3 — Scoring
- Per-product-per-platform scoring (not per-snapshot)
- Dynamic plain-English explanations
- Inventory allocation suggestion
- Alibaba wholesale scoring profile
- OpportunityScore persistence model

### Phase 4 — Dashboard & UI
- Time-of-day greeting with user name
- Business metric cards (Products Tracked, Opportunities, Price Drops, Alerts, Trending)
- Trending Products / Top Opportunities / Price Movement sections with image cards
- Live 4-platform search results page with images
- Product list page with tracked products
- Product detail page with scores + allocation
- Stale indicators
- Image placeholder component
- Streaming/progressive search results

### Phase 5 — Alerts & Trends
- Auto-detect price drops, competition spikes, trending products
- New `Alert` model with 4 types + read/unread
- Alert-driven dashboard metric cards
- Price movement sparklines
- Scraper health view
