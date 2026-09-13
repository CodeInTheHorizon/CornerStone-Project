# MarketPulse AI - Project Progress

**Updated:** September 11, 2026  
**Current stage:** Phase 9 implemented and automated checks passing. Phase 10 has not started.

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
| 10 - Deployment | Not started | Hosting, durable storage, production configuration and deployment verification remain. |

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

## Current data and model

The development database was inspected without editing its contents.

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

## Verification completed

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

The development database remains at migration `0003`. Normal backend startup
applies the existing `0004` prediction-result migration. Its upgrade was verified
on a temporary database copy; development data was not modified for testing.

## Why real-time data is still unavailable

- The retained Amazon adapter uses deprecated PA-API 5 and is disabled by the
  shared collector policy. A supported replacement and approved access are needed.
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
- Latest commit: `c7d4b86` - `docs: Phase 6 report`.
- Phase 7-9 work is present as uncommitted working-tree changes.
- No deployment or Phase 10 implementation has been performed.

Reference reports:

- [Project context](PROJECT_CONTEXT.md)
- [Phase 6 report](docs/PHASE_6_REPORT.md)
- [Phase 7 report](docs/PHASE_7_REPORT.md)
- [Phase 8 report](docs/PHASE_8_REPORT.md)
- [Phase 9 report](docs/PHASE_9_REPORT.md)
- [Setup and usage](README.md)
