# MarketPulse AI - Overall Project Report

**Report date:** September 13, 2026 (status addenda updated September 14, 2026)

**Current stage:** Phases 1-9 complete. Phase 10 partially implemented: deployment configuration and durable-storage code are committed in the "checkpoint marketpulse through phase 10 prep" commit. Local automated checks pass; nothing has been deployed, and real PostgreSQL behavior is unverified. See [Durable storage](docs/DURABLE_STORAGE.md) and [Phase 10 report](docs/PHASE_10_REPORT.md).

**Durable storage addendum:** Configuration requires PostgreSQL and database
storage in production, and dataset/model bundles persist through the storage
abstraction (migration `0005`). No Phase 10.5 report has been written; the work
was interrupted and then stabilized, not signed off. Development data is preserved.
The historical inspection below does not describe the new production storage.

**Development database addendum (read-only inspection, September 14):** the
active model is now **XGBoost v5**, trained September 13 during the interrupted
Phase 10 run on the same DEMO data; its accuracy 33.33%, weighted F1 31.87% and
majority baseline 40.62% match v4. The database holds 24 users, 2 saved
predictions, 5 model records and 480 DEMO snapshots. Alembic is still at `0004`;
the next normal backend startup applies `0005`, which only adds `stored_objects`.

**Phase 10 addendum:** The report below preserves the Phase 1-9 inspection.
Checkpoint `de173ee` now preserves that work in Git. Deployment configuration,
production startup, readiness and configuration checks have since been added.
Storage redesign remains deferred; development data and ML behavior are preserved.

## Report scope and evidence

This report summarizes work implemented through Phase 9. On September 13, the
working-tree status, latest commit, frontend routes, API route inventory, ML
modules, database model files and existing phase documentation were inspected.
The test results and development database figures below are from the completed
September 11 Phase 9 verification; they were not rerun or remeasured for this
documentation update. No application code, data, model or configuration was changed.

## Project purpose

MarketPulse AI is an electronics marketplace intelligence application for sellers.
It brings marketplace observations, dataset preparation, custom model training,
product-level predictions and descriptive trend comparisons into one dashboard.
Amazon, Flipkart, Croma and Alibaba are represented in its marketplace abstraction.
Its implemented predictions concern an observable opportunity proxy, not verified
unit sales, profitability or true consumer demand. Inventory, orders, accounting,
advertising and logistics management remain outside the initial scope.

## Overall status

MarketPulse AI now supports the complete stored-data demonstration pipeline:

**Register / Login -> Load or import data -> Build dataset -> Train model -> Predict -> Compare Opportunity Scores -> View trends and prediction history.**

The application is suitable for demonstrating the implemented pipeline. It is
**not yet a verified production deployment or a reliable real-market prediction system**.
Current stored observations are synthetic DEMO data, no LIVE collector is usable,
and the active model performs below the majority-class baseline.

## Progress by phase

| Phase | Status | Delivered |
| --- | --- | --- |
| 1 - Foundation | Complete | Repository structure, FastAPI, React, configuration, database models and health endpoint. |
| 2 - Landing page | Complete | Public sections, navigation, developer profile, theme support and configurable contact form. |
| 3 - Authentication | Complete | Registration, login, bcrypt password hashing, JWT authentication, logout and protected dashboard. |
| 4 - Collection layer | Implemented; live access blocked | Modular marketplace adapters, validation, normalization, deduplication, snapshot storage and status APIs. |
| 4.5 - Import and provenance | Complete | CSV/JSON imports, bundled synthetic demo data and explicit LIVE / IMPORTED / DEMO labeling. |
| 5 - Dataset pipeline | Complete | Cleaning, canonical product/category normalization, historical features, processed CSV files and metadata. |
| 6 - Model training | Complete with documented limitations | Random Forest and XGBoost, temporal validation, measured metrics, baseline comparison, versioned Pipelines and active-model metadata. |
| 7 - Predictions | Complete | Saved-Pipeline inference, explained Opportunity Scores, user-scoped prediction history and immutable result snapshots. |
| 8 - Trend analytics | Complete | Stored price, discount, rating, review and availability histories; platform comparisons; charts and actual dashboard summaries. |
| 9 - Stabilization | Implemented; automated checks pass | Security/configuration fixes, input validation, failure handling, persistence safeguards, API journey tests and UI/accessibility polish. Browser interaction remains unverified. |
| 10 - Deployment | Partially implemented; not deployed | Render/Vercel configuration, production settings validation, readiness check and database-backed storage exist and pass local checks. Hosting, real PostgreSQL and deployment verification remain. |

Phase completion describes the implemented software, not the fulfillment of live
marketplace access or production-readiness requirements.

## Current architecture

| Layer | Implementation |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS and React Router. |
| Backend | FastAPI, Pydantic settings/validation and SQLAlchemy. |
| Database | SQLite locally, managed through Alembic migrations. |
| Database models | User, MarketplaceSnapshot, ModelMetadata and Prediction. |
| ML | pandas, scikit-learn, Random Forest, XGBoost and saved preprocessing/model Pipelines. |
| Storage | Local database, processed datasets and versioned model artifacts. |
| Authentication | bcrypt passwords and expiring JWT access tokens. |

The existing architecture and scoring formulas have been preserved through Phase 9.

## Working screens and APIs

Available screens: Landing, Register, Login, Dashboard, Marketplace Data,
Train Model, ML Predictor with prediction history, Trend Analysis and Analytics.

| Area | Main endpoints |
| --- | --- |
| Authentication | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Marketplace data | `POST /data/collect`, `POST /data/import`, `POST /data/demo/load`, `GET /data/latest`, `GET /data/history`, `GET /data/status` |
| Datasets | `POST /ml/dataset/build`, `GET /ml/dataset/status`, `GET /ml/dataset/preview` |
| Training | `POST /ml/train`, `GET /ml/status`, `GET /ml/metrics` |
| Predictions | `GET /ml/prediction-options`, `POST /ml/predict`, `GET /ml/predictions`, `GET /ml/predictions/{id}` |
| Analytics | `GET /analytics/trends`, `GET /analytics/platform-comparison`, `GET /analytics/summary`, `GET /analytics/options` |

Feature endpoints require authentication. `API_PREFIX` can namespace them.
The collection endpoint reports unavailable sources explicitly; its existence
does not mean live fetching currently works.

## Implementation details by subsystem

### Public website and authentication

The public frontend provides the landing page, feature and developer sections,
theme support, configurable WhatsApp contact flow, registration and login.
Protected dashboard routes use the shared authentication provider. Passwords are
hashed with bcrypt; authenticated API calls use expiring JWTs. Phase 9 added
centralized rejected-session handling, cross-tab logout and clearer network errors.

### Collection, imports and datasets

The collection layer separates marketplace adapters from normalization, validation,
deduplication and database persistence. Source status makes unavailable connectors
explicit. CSV/JSON imports and the bundled demo fixture let the rest of the pipeline
operate without live access. Provenance distinguishes LIVE, IMPORTED and DEMO.

Dataset generation cleans stored observations, normalizes product/category identity,
creates historical features and saves processed CSV data with metadata. Dataset
status and bounded preview endpoints are connected to the training screen.

### Model training and inference

Existing ML modules are:

| Module | Responsibility |
| --- | --- |
| `backend/app/ml/normalization.py` | Normalize product and category identities. |
| `backend/app/ml/features.py` | Build model features from observations. |
| `backend/app/ml/dataset_builder.py` | Assemble processed datasets. |
| `backend/app/ml/target.py` | Generate forward price-direction labels and baseline statistics. |
| `backend/app/ml/training.py` | Fit and evaluate the supported models and preprocessing pipeline. |
| `backend/app/ml/opportunity.py` | Calculate explained experimental Opportunity Scores. |

The target uses the following observation's price movement to assign declining,
stable or improving classes around a 1% threshold. Rows without a following
observation cannot be labeled. Future target-helper columns are excluded from
features. Temporal validation and preprocessing protections are implemented, but
the documented boundary-crossing forward-label limitation still needs attention.

Random Forest and XGBoost training save versioned preprocessing/model Pipelines.
The service persists measured metrics, baseline context and the active model in
ModelMetadata. Predictions load the saved Pipeline and retain their original
result, model version, quality context and provenance for later history reads.

The 0-100 Opportunity Score is an explained heuristic. Its point budgets are:
model signal 10, price competitiveness 20, rating 15, reviews 15, discount 10,
competition 15 and price trend 15. Missing signals are reported and receive no
points; their weights are not redistributed. This score is not a calibrated
probability of marketplace success.

### Analytics and dashboard

Stored histories support price, discount, rating, review and availability analysis,
with platform comparisons and visible data coverage. Dashboard summaries use
stored records rather than hardcoded success figures. Prediction history is
user-scoped, and saved scores retain the context from when they were generated.
Reloading these screens reads stored data; it does not itself contact marketplaces.

### Frontend routes

| Route | Screen |
| --- | --- |
| `/` | Public landing page |
| `/status` | Service status |
| `/register`, `/login` | Account access |
| `/dashboard` | Dashboard overview |
| `/dashboard/marketplace-data` | Observations, import/demo and collector status |
| `/dashboard/train` | Dataset building and model training/status |
| `/dashboard/predictor` | Predictions and saved history |
| `/dashboard/trends` | Stored trend analysis |
| `/dashboard/analytics` | Marketplace comparison |

### Database responsibilities

| Model | Stored information |
| --- | --- |
| `User` | Accounts, hashed passwords and account state. |
| `MarketplaceSnapshot` | Marketplace listing observations and provenance. |
| `ModelMetadata` | Training status, inputs, measured metrics, artifact path and active version. |
| `Prediction` | User request, marketplace scores, model reference and immutable result payload. |

Alembic migration `0004_prediction_result.py` adds persistence needed for the
Phase 7 full prediction result. Dataset files and trained model artifacts remain
on the local filesystem rather than being stored as database blobs.

## Data and model at the last verified inspection

The development database was inspected read-only during the September 11 verification.
This table is historical; see the September 14 addendum at the top for the current
active model (v5), user and prediction counts, and migration state.

| Item | Current value |
| --- | --- |
| Stored marketplace snapshots | 480 |
| Provenance | 480 DEMO; 0 IMPORTED; 0 LIVE |
| Platforms represented | Amazon, Flipkart, Croma and Alibaba |
| Observation window | September 1-5, 2026 |
| Latest observation | September 5, 2026, 09:00 UTC |
| User records | 23 |
| Model metadata records | 4 |
| Saved predictions in development DB | 0; persistence is verified in isolated tests |
| Active model | XGBoost v4 |
| Validation accuracy | 33.33% |
| Weighted F1 | 31.87% |
| Majority-class accuracy baseline | 40.62% |

**The model is experimental and below baseline.** It predicts a price-direction
opportunity proxy, not actual sales demand. Class probabilities and the heuristic
Opportunity Score must not be presented as reliable marketplace recommendations.
Weighted F1 and baseline accuracy are different metrics; the like-for-like
comparison is model accuracy against baseline accuracy.

Example from stored DEMO history: Acme 20000mAh on Croma fell from INR 2,207.71
to INR 2,085.20 across five observations, a 5.55% decrease. Reviews increased by
72, averaging 18 net reviews per day. These are synthetic observations, not live prices.

## Phase 9 improvements

- Fixed `DEBUG=release` handling and documented comma-separated/JSON CORS configuration.
- Required JWT expiry/issued-at/subject claims and tightened runtime secret validation.
- Prevented password inputs from being echoed in validation errors.
- Handled duplicate-registration races and invalid platform/date/model inputs.
- Bounded import reads, handled malformed files and normalized timestamps to UTC.
- Added training collision protection and safeguards against overwriting existing artifacts.
- Preserved application logging during startup migrations and sanitized unexpected API errors.
- Kept the bundled demo accessible with a separate data-output directory.
- Unified JSON/multipart request errors, added timeouts and handled rejected sessions centrally.
- Improved loading states, stale-response handling, mobile focus/scroll behavior and narrow charts.
- Corrected public live-data claims while preserving source badges and model-quality warnings.

## Last completed verification - September 11, 2026

| Check | Result |
| --- | --- |
| Full backend regression suite | **295 passed**, 6 dependency deprecation warnings |
| Frontend request-handling tests | **8 passed** |
| Frontend TypeScript/Vite production build | **Passed** |
| Frontend lint | **Passed**, no warnings in the final run |
| Git whitespace check | **Passed** |
| Fresh-install API journey | **Passed**, using temporary database/dataset/model storage |
| Development database migration-copy check | **Passed**, all existing rows preserved |
| Development database/model preservation | SHA-256 hashes matched the inspection baseline |
| Browser end-to-end and responsive visual testing | **Not performed: no browser available through the browser tool** |

The API journey covers registration/login, demo loading, import, dataset build,
isolated Random Forest training, inference, saved Opportunity Scores, analytics,
history, user isolation and restart persistence. It uses normal startup migrations
and APIs without manual database inserts. Browser navigation and browser logout
were not exercised by this API test.

At that inspection, the development database was at migration `0003`. Normal backend startup
applies the existing `0004` prediction-result migration. Its upgrade was verified
on a temporary database copy; development data was not modified for testing.

## Why the current implementation does not fetch real-time data

- The repository marks its retained Amazon PA-API 5 adapter deprecated and disables it
  through the shared collector policy. A supported replacement and approved access
  are needed. This report does not independently recheck provider policies.
- Flipkart, Croma and Alibaba adapters report their existing access restrictions
  or unavailable integration status.
- Importing a file produces IMPORTED records; loading the fixture produces DEMO records.
- Reloading analytics rereads stored observations and does not fetch fresh market data.

No scraping bypasses or simulated live-success responses were added.

## Remaining work and deployment blockers

1. Verify desktop, tablet and mobile layouts, keyboard behavior and the full browser journey.
2. Prepare and verify Phase 10 hosting, HTTPS, API URL/CORS configuration and SPA routing.
3. Provide durable database, dataset and artifact storage with backups.
4. Obtain a supported, approved source of genuine marketplace observations.
5. Evaluate on suitable real historical data before making reliability claims; address
   documented ML limitations, including boundary-crossing forward labels in the original split.
6. Define authorization and abuse controls before public multi-user deployment:
   data/model operations currently share an authenticated operator workspace.
7. Coordinate training across processes before enabling multiple backend workers.
8. Revisit browser token storage, revocation and deployment request-size limits.

The current JWT logout discards client tokens; it does not revoke a copied token
on the server. Imported observation timestamps depend on the operator's data.
Local model artifacts are trusted files and must not come from untrusted uploads.

## Repository and documentation

- Branch: `master`.
- `de173ee` checkpoints Phases 1-9; the following "checkpoint marketpulse through
  phase 10 prep" commit adds the Phase 10 deployment and durable-storage work.
- No deployment has been performed and no Git remote push is recorded here.

## How to interpret older documentation

PROJECT_CONTEXT.md records the intended scope and roadmap; its proposed features
are not proof of implementation. Phase reports capture the state at their own
completion. For example, the Phase 6 description of Prediction as unused is
superseded by Phase 7, and older active-model references are superseded by the
later database inspections (v4 on September 11, v5 on September 14). Historical
statements that a later phase had not started apply to the date of those reports.

Development databases, processed datasets and model artifacts are ignored by Git,
so a clean checkout contains the code and demo fixture but not the local v5 model.

## Existing test coverage

Backend test files cover health, models, migrations, authentication, scrapers,
data APIs, imports/demo ingestion, dataset building, training, predictions,
analytics, stabilization and a fresh-install API journey. The frontend test file
`frontend/tests/apiClient.test.mjs` exercises request handling with Node's test
runner. These are automated API/request checks, not full browser UI coverage.

## Reference documentation

Reference reports:

- [Project context](PROJECT_CONTEXT.md)
- [Phase 6 report](docs/PHASE_6_REPORT.md)
- [Phase 7 report](docs/PHASE_7_REPORT.md)
- [Phase 8 report](docs/PHASE_8_REPORT.md)
- [Phase 9 report](docs/PHASE_9_REPORT.md)
- [Setup and usage](README.md)
