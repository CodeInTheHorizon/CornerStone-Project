# Phase 8 — Trend Analytics + Dashboard Integration

Implemented against the existing Phases 1–7 implementation on `master`, starting
from commit `c7d4b86` with existing uncommitted Phase 7 work preserved. No commit
was created. PROJECT_CONTEXT.md and both previous phase reports were read before
implementation. No new dependencies, schema migration, scraping implementation,
scheduler, retraining feature or deployment storage changes were introduced.

## Files created in Phase 8

- `backend/app/schemas/analytics.py` — filter contract.
- `backend/app/services/analytics_service.py` — deterministic snapshot analytics and summary.
- `backend/app/api/routes/analytics.py` — authenticated read APIs.
- `backend/tests/test_analytics.py` — 13 repeatable analytics tests.
- `frontend/src/types/analytics.ts` — typed API contracts.
- `frontend/src/services/analyticsService.ts` — API wrappers.
- `frontend/src/components/dashboard/ObservedLineChart.tsx` — simple SVG history charts.
- `frontend/src/components/dashboard/MarketDataRefresh.tsx` — collector integration hook and unavailable states.
- `frontend/src/pages/AnalyticsPage.tsx` — trend and platform-comparison modes.
- `docs/PHASE_8_REPORT.md` — this report.

## Files modified in Phase 8

- `backend/app/api/router.py` — register analytics router.
- `frontend/src/App.tsx` — authenticated Trends and Analytics routes.
- `frontend/src/config/dashboard.ts` — enable existing sidebar entries.
- `frontend/src/pages/DashboardPage.tsx` — real summary cards, provenance and refresh hook; retain model-status quality notice.
- `frontend/src/components/dashboard/PredictionResults.tsx` — link the selected product to stored trends, without recomputing predictions (this file was already new in Phase 7).
- `README.md`, `CLAUDE.md` — current Phase 8 status and usage.

Other dirty/new files shown by Git belong to the pre-existing Phase 7 work.
Historical Phase 6/7 reports are preserved.

## Metrics and calculation policies

All trend inputs are MarketplaceSnapshot records. Canonical product keys and
category aliases reuse Phase 5 normalization. Analytics does not use processed
features because their missing-price cleaning would discard useful review or
availability history. No saved Pipeline is loaded or run.

A history is identified by canonical product, platform, source, currency and
listing identity (external ID, otherwise URL, otherwise product plus seller).
Same-instant duplicates retain the highest snapshot ID. Results disclose removed
duplicates. Different sources and currencies never form one history.

| Signal | Calculations |
| --- | --- |
| Price | First valid and latest observed price; absolute and percentage change; average, min, max; rising/stable/falling |
| Discount | First/latest/mean/min/max discount, change in percentage points, relative percentage change, direction |
| Rating | Latest rating, first-to-latest change, descriptive statistics and direction |
| Reviews | Count change, percentage growth, net reviews per elapsed calendar day |
| Availability | Latest known/unknown state and changes between adjacent known observations |

Changes require at least two valid observations and a valid latest reading.
A missing latest reading stays null, although historical averages and the latest
valid reading remain available. Zero baselines produce null percentage changes.
Negative review growth is retained (it can reflect review removal). Price uses a
±1% stable band across the selected window; a zero price baseline uses the sign
of absolute change. Other directions use the sign of change. There is no forecast,
imputation, extrapolation or inferred sales volume.

Discount is derived from selling/original prices only when absent and valid;
points identify this with `discount_derived`. Out-of-range signals become null.
Unknown availability gaps are not bridged. Event timestamps indicate observation
bounds, never an exact stock-event time or stock quantity.

Dates filter complete inclusive UTC calendar days. Series are ordered by actual
observation timestamps. The query caps candidate rows at 20,000 before canonical
product/category filtering and asks callers to narrow source/platform/date scope
rather than silently truncate analytics.

## APIs

All routes require JWT authentication and inherit API_PREFIX.

| GET route | Contract |
| --- | --- |
| `/analytics/trends` | Filtered/paginated histories, signal metrics, chart points, provenance, policy and insufficient states |
| `/analytics/platform-comparison` | Exact-product or explicit category groups, platform statistics and saved score context |
| `/analytics/summary` | User prediction count; raw stored count/source counts/platforms; latest observation and its sources; active model metadata; latest dataset source/time/file availability; live collector status |
| `/analytics/options` | Filtered snapshot-derived product/category choices, product search and pagination |

Filters: product (normalized exact name), product_key, platform, category,
source_type, start_date and end_date. Invalid dates/enums/pagination return 422.
No matching or inadequate history returns an explicit `insufficient_data` with a
reason. A single reading is shown without claiming a change. Trends default to
20 histories/page (maximum 100); options default to 50 products/page (maximum 100).

Comparisons keep exact products separate, even when their names match but brands
or categories differ. Category mode is explicitly an aggregate over possibly
different assortments. Means weight each listing equally, after calculating its
own history statistic. Latest prices can come from different dates; date coverage
and valid-latest-price/review-growth listing counts are exposed. Listing density
is the fraction of observed listings in that source/currency group, not market
competition. At least two priced platforms are needed for an available group.

Phase 7 opportunity scores are optional reads from the current user's latest 500
saved responses. Only exact product/platform/source/latest-observation matches,
a single identifiable listing, INR, and single-source original datasets qualify.
The original score, model quality, warning and creation time accompany the result.
Scores are not recalculated for the selected date window. No matching score is
shown as unavailable; it is never fabricated. Category scores are not invented.

## Frontend and dashboard

The existing theme and dashboard shell are retained. `/dashboard/trends` supports
searchable product selection, category, platform/source and inclusive date filters,
paginated separate listing histories, price/discount/rating/review charts, signal
summaries, observed availability movement and a raw-value table. Missing values
break chart lines. `/dashboard/analytics` presents grouped platform comparison
cards with coverage, observation timestamps and saved model-quality context.

Dashboard cards show user prediction count, active model/weighted F1, latest
observation, stored record count, usable live collector count and latest dataset
source. The existing model notice remains visible. Observation time is explicitly
distinct from dataset generation time and dashboard load time.

DEMO / IMPORTED / LIVE badges appear beside observation provenance and per-series
or comparison groups. DEMO is synthetic; IMPORTED is operator-supplied; LIVE denotes
original collection provenance and does not guarantee freshness. A newly built
DEMO dataset does not become a live update.

Refresh Market Data follows the existing collect API → stored snapshots → analytics
reload contract for a future supported collector. It is currently disabled, with
individual reasons. The retained Amazon adapter declares deprecated PA-API 5 and
is excluded from usable collectors; the other three adapters report unavailable.
The existing collection implementations are preserved. Reload stored analytics
only rereads stored data. Errors and zero-new-record responses are shown plainly.

## Example calculated from the current development database

The actual database contains 480 DEMO rows across Amazon, Flipkart, Croma and
Alibaba, observed September 1–5, 2026 at 09:00 UTC, with no LIVE/IMPORTED rows.
Shipping/delivery fields are missing; they are not required by these analytics.
Each platform contains 120 rows representing 24 native listing IDs.

For `acme 20000mah|acme|power banks`, five Croma DEMO observations produce:

| Metric | Calculated result |
| --- | --- |
| First → latest price | INR 2,207.71 → 2,085.20 |
| Absolute / percentage price change | −122.51 / −5.549189% (falling) |
| Average / min / max price | 2,154.88 / 2,085.20 / 2,207.71 |
| First → latest discount | 23.85% → 28.07%; +4.22 percentage points |
| Average discount | 25.67% |
| Rating | 3.9 → 3.9 (stable) |
| Reviews | 8,606 → 8,678; +72 / +0.836626% |
| Review momentum | 18 net reviews/day |
| Availability | Two observed changes; latest in stock |

The same exact product on Alibaba has mean INR 3,136.914 and latest INR 3,035.68,
versus Croma's mean INR 2,154.88 and latest INR 2,085.20. Amazon and Flipkart lack
this exact product identity and are unavailable in that comparison. These are
stored synthetic examples, not current marketplace prices or recommendations.
The development database has no saved predictions, so score context is unavailable.

The current active model record is **v4 XGBoost**, with accuracy 0.3333,
weighted F1 0.3187 and majority accuracy baseline 0.4062, trained on DEMO.
Earlier phase reports recorded v2; current repository/database state takes
precedence. Phase 8 did not initiate development model training. Local v2/v3/v4
Pipeline files have identical SHA-256 hashes. This model remains experimental and
below baseline. Latest dataset metadata is DEMO, ID `1404fb9fc19b`, generated
September 10, 2026 at 12:41:40 UTC; latest observation remains September 5.

## Validation

- Focused analytics tests: 13 passed.
- Frontend TypeScript + production Vite build: passed.
- Frontend oxlint: passed.
- Full backend regression: **257 passed**, including all 13 new analytics tests.
  Command: `.venv/Scripts/python -B -m pytest -q -p no:cacheprovider`.
  Five dependency deprecation warnings; no failures. Focused execution also
  reported an existing pytest-cache directory warning; the full run disabled caching.

New tests cover price, discount, rating/review calculations; zero baseline;
negative reviews; no/single/missing observations; unknown availability gaps;
duplicate/source/currency/listing separation; inclusive dates and validation;
all four endpoint authentication requirements; exact/category comparison; product
options; saved-score ownership/freshness; summary counts and future collector hook.
No new test calls live marketplace sites or trains a model. Existing training and
prediction regression tests retain their isolated temporary fixture training;
production model artifacts and processed datasets are not their output targets.
SHA-256 verification before and after the regression suite matched for the
development database and all four local Pipeline files.
Browser visual interaction was not verified; compilation and lint are not a
substitute for that check.

## Known limitations

- Five observations per listing support only short descriptive histories; no real
  sales ground truth, representative competition estimate or real-time feed exists.
- Canonical name/brand/category identity cannot prove vendor SKU equivalence;
  source identity quality and fallback listing ambiguity remain ingestion limits.
- Analytics is bounded in-memory MVP aggregation, without caching/background jobs.
- Category assortment/date coverage differs across platforms; means are explicit
  descriptions rather than normalized market-price indexes.
- Saved scores retain their original history, may refer to older model versions,
  and cannot be assigned to ambiguous/multiple listings.
- Model and dataset artifacts remain local-filesystem resources.
- Phase 7 migration 0004 remains required by normal startup for saved-result reads;
  Phase 8 adds no migration.
- No Phase 9 work was begun.
