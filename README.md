# MarketPulse AI

AI/ML-driven demand forecasting and marketplace intelligence for electronics
sellers.

MarketPulse AI imports or loads stored marketplace observations, turns them into
a structured dataset, trains models on it, and surfaces trend analytics and
experimental opportunity scores. A Flipkart Affiliate API connector exists for
LIVE collection but is disabled until credentials and Flipkart's data-use
approval are configured; no LIVE data is stored.

> **Status: Phase 12 complete - ML validation hardened; forward-label boundary leak fixed. Active model v5 is DEMO-trained and below baseline; 0 LIVE observations; no model is real-data trained.**
> Phase 11: LIVE connector implemented and gated; 0 LIVE records. Phase 10:
> deployment-ready and locally production-verified, not deployed.
> PostgreSQL storage, migrations, a Linux build and start of the Render
> configuration, and desktop/tablet/mobile browser flows were verified locally.
> No Render or Vercel service exists yet. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
> The landing page, accounts, the dashboard, the data layer, the dataset
> builder, model training, experimental predictions, opportunity scores, and
> user-scoped prediction history work. Stored trend charts, platform comparisons,
> and source-aware dashboard summaries are available. LIVE refresh works only once
> the Flipkart connector is configured and approved (see [docs/MARKETPLACE_SOURCES.md](docs/MARKETPLACE_SOURCES.md)).
> The active model is DEMO-trained and below the majority baseline. Results
> demonstrate the pipeline; they are not reliable marketplace recommendations.
> See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

---

## Requirements

- **Python 3.12+** (verified on 3.14)
- **Node.js 20+** (verified on 24)

## Setup

```bash
git clone <repo-url>
cd marketPulse_AI
cp .env.example .env        # adjust values as needed
```

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
```

### Frontend

```bash
cd frontend
npm install
```

## Running locally

Two processes, in two terminals. They run independently.

**Backend** — http://127.0.0.1:8000 (docs at `/docs`):

```bash
cd backend
.venv/Scripts/python -m uvicorn app.main:app --reload
```

**Frontend** — http://localhost:5173:

```bash
cd frontend
npm run dev
```

> The Vite dev server binds the `localhost` hostname. Use `http://localhost:5173`,
> not `http://127.0.0.1:5173`.

## Checks

```bash
cd backend  && .venv/Scripts/python -m pytest   # Full backend regression suite
cd frontend && npm run build                    # tsc -b && vite build
cd frontend && npm run lint                     # oxlint
cd frontend && npm test                         # Request/error regression tests
```

PostgreSQL integration tests (migrations, concurrent startup, storage, a
production-mode API journey) are skipped unless `TEST_POSTGRES_URL` points at a
disposable server; see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#local-development-unchanged).

## Environment variables

All configuration is environment-driven; see [`.env.example`](.env.example).

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL. SQLite locally; **PostgreSQL required in production** (`postgres://` / `postgresql://` normalize to psycopg). Leave unset locally — a relative `sqlite:///` URL resolves against the working directory. | absolute `<repo-root>/data/marketpulse.db` |
| `STORAGE_BACKEND` | Where datasets and models live: `local` files or `database` bundles. `auto` = local in development, database otherwise; production rejects local. | `auto` |
| `STORAGE_MAX_BYTES` | Size limit per stored dataset or model. | `134217728` (128 MiB) |
| `CORS_ORIGINS` | Exact HTTP(S) origins, comma-separated or JSON array; no wildcard. Production needs at least one HTTPS origin. | `http://localhost:5173,http://127.0.0.1:5173` |
| `DEBUG` / `SQL_ECHO` | Booleans; legacy `DEBUG=release` maps to false. Both must be false outside development. | `false` |
| `ENVIRONMENT` | `development` / `production`. | `development` |
| `HOST` / `PORT` / `LOG_LEVEL` / `ACCESS_LOG` | Used by `python -m app.start`. | `127.0.0.1` / `8000` / `INFO` / `false` |
| `API_PREFIX` | Prefix for feature endpoints. Empty matches the API outline in PROJECT_CONTEXT.md §15. `/health` and `/ready` are always unprefixed. | *(empty)* |
| `JWT_SECRET_KEY` | Signs access tokens. **Must** be at least 32 bytes and not the default outside development. | dev placeholder |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime. | `720` (12h) |
| `FLIPKART_AFFILIATE_ID` / `FLIPKART_AFFILIATE_TOKEN` | Flipkart Affiliate API credentials, backend only. The token is a secret. | *(empty)* |
| `FLIPKART_DATA_USE_APPROVED` | Set `true` only after Flipkart confirms in writing that storing history, analytics and ML use are permitted. Credentials alone never enable collection. | `false` |
| `FLIPKART_TIMEOUT_SECONDS` | Flipkart request timeout (1-60). | `15` |
| `ML_MIN_LABELLED_ROWS` / `ML_MIN_TRAINING_ROWS` / `ML_MIN_VALIDATION_ROWS` | Training minimums after leakage-safe labelling; below them training returns `insufficient_data`. | `100` / `60` / `20` |
| `ML_MIN_UNIQUE_PRODUCTS` / `ML_MIN_OBSERVATION_DATES` / `ML_MIN_ROWS_PER_CLASS` | Further training minimums (dates: at least 4, structurally). | `10` / `4` / `5` |
| `AMAZON_PAAPI_ACCESS_KEY` / `_SECRET_KEY` / `_PARTNER_TAG` | Legacy PA-API configuration. PA-API was retired on 15 May 2026; nothing is enabled by these. | *(empty)* |
| `VITE_API_BASE_URL` | Backend base URL used by the browser, set at build time. The localhost default applies only to `npm run dev`; production builds must set it (Vercel builds require HTTPS). | dev server: `http://127.0.0.1:8000` |
| `VITE_WHATSAPP_NUMBER` | Destination for the contact form, digits only (e.g. `919876543210`). Empty disables the form, which then says so. | *(empty)* |

Only `VITE_`-prefixed variables reach the browser bundle. Never put a secret in one.
The exact Render and Vercel variable lists are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Architecture

```
backend/app/
├── config.py            environment-driven settings and production validation
├── main.py              application entrypoint, CORS, routers
├── start.py             production entrypoint: python -m app.start (one worker)
├── api/                 HTTP layer (routes/ + aggregate router)
├── database/            engine, session factory, Alembic startup migrations
├── models/              User, MarketplaceSnapshot, Prediction, ModelMetadata
├── schemas/             pydantic request/response shapes
├── auth/                password hashing, JWT
├── scrapers/            base, parsing, validation, registry + one module per platform
├── ml/                  features, dataset builder, target, training, opportunity score
├── services/            business logic between API and database
└── storage/             datasets and models as local files (dev) or PostgreSQL bundles (prod)

frontend/src/
├── components/  reusable UI primitives (Button, Section, FlipCard, Navbar, Icon...)
├── sections/    landing page sections (Hero, WhyChoose, Developer, Features, Contact)
├── pages/       routed pages
├── theme/       light/dark theme context and provider
├── services/    typed API client
├── lib/         pure helpers (validation, WhatsApp link building)
└── hooks/  types/  config/

data/demo                   bundled synthetic DEMO fixture
data/processed              local development datasets (production uses the database)
docs/                       phase reports, deployment and storage guides
render.yaml                 Render backend Blueprint
frontend/vercel.json        Vercel build settings and SPA rewrite
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | — | Service descriptor |
| `GET` | `/health` | — | Liveness + database reachability (always HTTP 200) |
| `GET` | `/ready` | — | Deployment readiness: HTTP 503 when the database is unreachable |
| `GET` | `/docs` | — | OpenAPI UI |
| `POST` | `/auth/register` | — | Create an account, returns a token |
| `POST` | `/auth/login` | — | Exchange credentials for a token |
| `GET` | `/auth/me` | Bearer | The authenticated user |
| `POST` | `/data/collect` | Bearer | Fetch LIVE listings through an official API and append them (501 blocked, 429 rate limited, 502 provider failure) |
| `POST` | `/data/import` | Bearer | Import a CSV/JSON dataset (stored as IMPORTED) |
| `POST` | `/data/demo/load` | Bearer | Load the synthetic demo fixture (stored as DEMO) |
| `GET` | `/data/latest` | Bearer | Recent snapshots (filter by platform/keyword/category) |
| `GET` | `/data/history` | Bearer | Snapshots over a time window, oldest first |
| `GET` | `/data/status` | Bearer | Collector state, required configuration names, LIVE record count, last successful/failed fetch and stored provenance per platform |
| `POST` | `/ml/dataset/build` | Bearer | Build an ML-ready dataset from stored snapshots |
| `GET` | `/ml/dataset/status` | Bearer | Metadata for the most recent dataset |
| `GET` | `/ml/dataset/preview` | Bearer | First N rows of a stored dataset |
| `POST` | `/ml/train` | Bearer | Train on explicitly selected `source_types`, evaluate against baselines, apply the quality gate and persist |
| `GET` | `/ml/status` | Bearer | Active model, version and training history |
| `GET` | `/ml/metrics` | Bearer | Measured evaluation results for the active model |
| `GET` | `/ml/prediction-options` | Bearer | Stored products available for prediction |
| `POST` | `/ml/predict` | Bearer | Experimental prediction and opportunity scores |
| `GET` | `/ml/predictions`, `/ml/predictions/{id}` | Bearer | The user's saved prediction history |
| `GET` | `/analytics/trends`, `/platform-comparison`, `/summary`, `/options` | Bearer | Stored-snapshot trends and comparisons |

There is no `/auth/logout`: tokens are stateless JWTs, so signing out is a
client-side discard. A no-op endpoint would imply a revocation that does not
happen. Server-side revocation is a real feature worth adding, not a stub.

## Frontend routes

| Path | Auth | Page |
|---|---|---|
| `/` | — | Public landing page |
| `/login`, `/register` | — | Authentication |
| `/status` | — | Backend connectivity diagnostic |
| `/dashboard` | Required | Dashboard overview |
| `/dashboard/marketplace-data`, `/predictor`, `/train`, `/trends`, `/analytics` | Required | Marketplace data, ML Predictor, Train Model, Trend Analysis, Analytics |

Protected routes survive a page refresh: the stored token is re-checked before any
redirect. Hosting needs an SPA fallback (`frontend/vercel.json` rewrites to `index.html`).

## Theming

Light and dark are both first-class. The toggle in the navbar switches themes;
the default follows the operating system and keeps following it while the page
is open. The choice persists in `localStorage`, and an inline script applies it
before first paint so there is no flash of the wrong theme. Every text/ground
pairing in both themes was measured against WCAG AA (4.5:1). See
[docs/design-direction.md](docs/design-direction.md).

## Data model

| Table | Holds |
|---|---|
| `users` | Accounts. Password **hashes** only. |
| `marketplace_snapshots` | One observation of one listing at one time. Repeated snapshots form the time series behind every trend feature. |
| `predictions` | Stored prediction requests and results, including per-marketplace opportunity scores and contributing factors. |
| `model_metadata` | One row per training run: dataset size, feature names, measured metrics, artifact reference. |
| `collection_attempts` | One row per outbound LIVE fetch, including failures: provider, query, outcome, error code, retry-after, counts. Provenance for LIVE snapshots via `collection_run_id`. Never holds credentials. |
| `stored_objects` | Production dataset CSVs and model binaries with their metadata and SHA-256 checksums (immutable). |

## Limitations

These are current and deliberate — please read before evaluating the project.

- **Not deployed.** Render and Vercel configuration is verified locally (PostgreSQL,
  a Linux build and start, browser flows), but no hosted service, domain or managed
  database exists yet. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
- **No live marketplace data.** Stored observations are synthetic DEMO or operator
  IMPORTED rows. The Flipkart connector is implemented but disabled until an
  operator supplies affiliate credentials and records Flipkart's data-use approval.
- **The contact form does not reach a server.** It validates locally and hands the
  message to WhatsApp. There is no contact endpoint, and nothing is stored.
- **Dashboard figures are not invented.** Model accuracy reads "Not trained" and
  data freshness reads "No data yet" until a real training run and stored
  observations fill them.
- **The access token is kept in `localStorage`**, which any script on the origin
  can read. It trades some XSS exposure for a session that survives a refresh; a
  httpOnly refresh-token cookie is the stronger design and is worth revisiting.
- **Marketplace pages do not expose true unit sales.** MarketPulse AI therefore
  predicts a marketplace *opportunity / demand proxy* built from observable
  signals, and does not claim to forecast real-world sales volume.
- **Data collection respects platform restrictions.** Collectors use officially
  permitted access paths only. CAPTCHAs, authentication and anti-bot protections
  are never bypassed. A source that cannot be collected reliably reports an
  explicit unsupported status instead of returning fabricated rows.
- **Metrics are measured, never asserted.** Model metric fields stay NULL until a
  real evaluation run fills them, and demo records are tagged `source="demo"` so
  they can never be displayed as live data.
- **Only Flipkart has a LIVE path, and it is gated.** Amazon's PA-API was retired
  and its Creators API terms forbid aggregation, seller tools and ML training
  without written approval. Croma has no public API. Alibaba's Open API is
  seller-only. See [docs/MARKETPLACE_SOURCES.md](docs/MARKETPLACE_SOURCES.md).
- **Flipkart's API returns no product ratings or review counts.** Those columns
  stay NULL for LIVE Flipkart rows (seller ratings are not substituted), which
  limits review/rating trend features. Imported and demo rows can carry them.
- **One fetch is not a trend.** A refresh returns at most 10 listings; useful LIVE
  history needs repeated refreshes over days. There is no scheduler.
- **The demo dataset is synthetic.** It exists to make the pipeline testable, not
  to describe any real market. No model trained only on demo data says anything
  about reality, and metrics from such a run must be read that way.
- **Trend features are thin on the current data.** Five observations per listing
  supports a short-term slope and nothing seasonal. Longer histories need
  repeated collection over real calendar time.
- **The trained model has no predictive power on the current data, and that is
  the expected result.** The demo fixture drifts prices by an independent random
  draw each step, so next-period direction is close to unpredictable by
  construction. Active model v5 scores 33.3% accuracy against a 40.6% majority
  baseline -- worse than guessing -- and its quality status is `below_baseline`.
  It was trained before the Phase 12 leakage fix, so even that score is
  overstated. It demonstrates nothing about real marketplace behaviour.
- **No model is real-data trained.** There are 0 LIVE observations and the LIVE
  connector is gated. See [docs/PHASE_12_REPORT.md](docs/PHASE_12_REPORT.md) for
  the conditions a future model must meet before being called real-data trained.
- **Probabilities are uncalibrated.** Log loss, Brier score and calibration error
  are measured and shown; nothing is recalibrated on this little data.
- **SQLite and local files are development-only.** Render's filesystem is
  ephemeral, so production requires a PostgreSQL `DATABASE_URL` and stores datasets
  and models in the database. Durability depends on that database's backups.
- **One instance, synchronous training.** Training runs inside the request under a
  process-local lock; do not scale the backend horizontally yet.
- **No role-based authorization or rate limiting.** Any signed-in account can run
  shared data and model operations; add controls before opening registration publicly.

## Marketplace collection

Collection is on demand: choose a platform and product keyword on **Marketplace
Data** (or a product on Trends/Analytics) and press **Refresh Market Data**.
LIVE records are fetched through an official API, validated, normalized,
deduplicated and **appended** as snapshots. Earlier observations are never
overwritten, and refreshing never retrains a model. Every fetch, including
failures, is logged in `collection_attempts` for provenance.

Provider access was rechecked on 2026-09-14 (details and sources:
[docs/MARKETPLACE_SOURCES.md](docs/MARKETPLACE_SOURCES.md)):

| Platform | Collector state here | Route and blocker |
|---|---|---|
| **Flipkart** | `credentials_missing` | **Official Affiliate API 1.0** connector, implemented. Needs `FLIPKART_AFFILIATE_ID`, `FLIPKART_AFFILIATE_TOKEN` and `FLIPKART_DATA_USE_APPROVED=true`, the last only with Flipkart's written approval, because its API terms limit use to its own platform. 20 calls/s per affiliate. The website's reCAPTCHA is never touched. |
| Amazon | `unavailable` | PA-API 5.0 **retired 15 May 2026**. The Creators API needs 10 qualified sales per 30 days, and Amazon's policies forbid aggregation/analysis, seller tools and ML training without written approval. |
| Croma | `unavailable` | **HTTP 403** (Akamai) to programmatic requests; no public API. |
| Alibaba | `unavailable` | `robots.txt` disallows `/trade/` search; the Open API only manages a seller's own catalogue. |

Collector states are `live`, `credentials_missing`, `approval_required`,
`credentials_rejected`, `rate_limited`, `provider_error` and `unavailable`. A
blocked platform returns HTTP 501 with its reason. A provider rate limit
returns 429 with `Retry-After` and pauses further requests until the window
passes. A provider failure or rejected credentials return 502. No CAPTCHA,
authentication, anti-bot protection or robots rule is bypassed anywhere.

### Source types

The project does not depend on all four marketplaces being collectable. Data
reaches the same normalized store three ways, and every stored row records
which:

| `source_type` | Meaning |
|---|---|
| `live` | Observed from the marketplace through a permitted route. |
| `imported` | A CSV/JSON dataset you uploaded. Real data you vouch for, but this system did not observe it and cannot attest to how it was gathered. |
| `demo` | The bundled **synthetic** fixture. Invented brands, generated prices. Not real market data. |

All three pass through identical validation, normalization and deduplication.
The UI badges every row and every platform card, so an IMPORTED or DEMO record
can never be mistaken for a live observation.

### Importing a dataset

Upload CSV or JSON on **Marketplace Data**. The minimum is `platform` and
`product_name`; common aliases (`mrp`, `reviews`, `url`, `asin`, `timestamp`)
are recognised. Missing fields stay empty -- nothing is inferred. Rejected rows
are reported by row number with the reason.

### Demo dataset

`data/demo/electronics_snapshots.json` holds 480 synthetic records across the
four platforms and eight electronics categories, over five dates, so the
dataset builder and ML phases are testable while most marketplaces cannot be
collected from. It is deterministic (fixed seed) so tests stay stable.

```bash
cd backend
.venv/Scripts/python scripts/generate_demo_dataset.py   # regenerate
```

Load it from the dashboard, or `POST /data/demo/load`. Loading again replaces
the demo rows; live and imported data is never touched.

### Data quality

Records are rejected outright when `product_name` is empty, the platform is
unknown, or the timestamp is missing. A record with one bad field is kept, the
bad field is **cleared to NULL** (never clamped, since a clamped rating reads as
a real measurement) and the reason is stored in the row's `warnings` column.

## Database migrations

The schema is versioned with Alembic from Phase 4 onward. `create_all()` can add
a missing table but never a missing column, so a database created by an earlier
phase silently lacked fields added later.

Migrations run automatically on startup. A pre-Alembic database is stamped at the
baseline revision and upgraded in place, preserving existing rows.

- A failed migration stops startup: the process exits and `/ready` never passes.
- On PostgreSQL the upgrade is one transaction, so a failure rolls back.
- Concurrent startups against PostgreSQL are serialized by an advisory lock, so an
  overlapping deploy and restart cannot race.
- Migrations `0001`-`0007` add or rename without dropping data. `0005` adds
  `stored_objects`; `0006` adds `collection_attempts`; `0007` adds model
  `quality_status` and `calibration_status`. Back up before any manual downgrade.

```bash
cd backend
.venv/Scripts/python -m alembic current       # where the database is
.venv/Scripts/python -m alembic upgrade head  # apply outstanding migrations
```

## Dataset builder

**Train Model** turns stored snapshots into an ML-ready table. The pipeline is
filter -> clean -> normalize -> deduplicate -> sort -> engineer features, and it
is fully deterministic: the same rows in produce the same table out.

In development, datasets are written to `data/processed/` as a CSV plus a JSON
metadata sidecar; models go to `backend/app/ml/artifacts/`. In production both are
immutable, checksummed rows in the PostgreSQL `stored_objects` table (see
[docs/DURABLE_STORAGE.md](docs/DURABLE_STORAGE.md)). Names carry a timestamp and id
or version, so a build never overwrites an earlier one -- that earlier dataset may
be what a model was trained on.

### Cleaning rules

Rows are **dropped** only when an essential field is unusable: missing product
name, unknown platform, unparseable timestamp, or no price at all. Everything
else is repaired in place -- a bad rating is cleared to NULL and the row is
kept, because one bad field is not an unusable observation. Every drop and
every repair is counted by reason in the metadata.

### Features

31 features across four groups:

| Group | Features |
|---|---|
| Basic | `effective_price`, `discount_amount`, `discount_percentage`, `has_discount`, `rating`, `review_count`, `price_to_original_ratio` |
| Time-based | `previous_price`, `price_change_absolute`, `price_change_percentage`, `rating_change`, `review_growth`, `review_growth_percentage`, `discount_change`, `availability_change`, `observation_index`, `days_since_previous` |
| Marketplace | `listing_count_for_keyword`, `average_market_price`, `median_market_price`, `price_vs_market_average`, `price_vs_market_median`, `average_rating`, `average_review_count`, `platform_listing_density`, `competition_score` |
| Trend | `short_term_price_trend`, `review_momentum`, `rating_momentum`, `discount_momentum`, `availability_trend` |

Two rules govern every one of them:

- **A missing input produces a missing feature.** The first observation of a
  listing has no prior price, so `price_change_absolute` is NULL, not `0`. Zero
  means "no change" -- a claim about the world that the data does not support.
- **No look-ahead.** Trend features use an expanding window over each listing's
  own past only, and stay NULL until three observations exist. A two-point
  "trend" is a line through noise.

`competition_score` is a documented weighted average, **not** a model: listing
density (50%), price pressure below the market median (30%), and log-scaled
review depth (20%), re-weighted by whichever components are actually present.

### Product matching

Listings are grouped by `normalized_product_name + brand + category`.
Deliberately strict -- punctuation and casing are ignored, but nothing else.
A false merge fabricates a price history that never happened, so ambiguous
records stay separate.

## Model training

**Train Model** fits and evaluates models on the Phase 5 dataset, then saves
the winner. Artifacts are versioned (`model_v1.pkl`, `model_v2.pkl`, ...) under
`backend/app/ml/artifacts/` and never overwritten -- an older artifact may be
what a stored prediction was made with.

### The target

`marketplace_opportunity_class`, three classes derived from the **next**
observation of the same listing:

| Class | Meaning |
|---|---|
| `improving` | price rises more than 1% by the next observation |
| `stable` | price moves within +/-1% |
| `declining` | price falls more than 1% |

**Why forward-looking.** Scoring each row from its own features and using that
as the label would be a tautology: the model would be handed the numbers the
label was computed from and would simply re-derive the formula, scoring
near-perfectly having learned nothing. Predicting the next observation makes
this a real forecasting problem.

**Why price direction.** MarketPulse AI is for sellers, so a price that holds
or rises signals room for margin and a falling price signals pressure. This is
the opposite of how a buyer would read it.

**What it is not.** A proxy for near-term margin direction, **not** a measure of
sales demand. Marketplace pages do not expose unit sales.

### Guards against inflated scores

Predicting price direction is genuinely hard. Everything that could make a
result look better than it is has been treated as a defect:

- **Boundary-first temporal split (Phase 12).** A date boundary is chosen first
  and each side is labelled separately, so no training label comes from a
  validation-period price. Before Phase 12, labels were generated first: 96 of 288
  DEMO training labels crossed the boundary. Listings are shared across the split
  on purpose (the product forecasts listings a seller already watches); overlap
  and unseen-product accuracy are reported.
- **Explicit provenance.** Training requires `source_types`, and the dataset
  may contain only those. DEMO cannot be combined with IMPORTED or LIVE except
  through a development-only override.
- **Preprocessing inside the pipeline**, fitted on the training fold only, so
  imputer and encoder statistics never leak backwards.
- **Nine columns excluded** as identifiers or target-derived, each with a
  recorded reason, surfaced in `/ml/metrics`.
- **Baselines reported beside every score, all as accuracies:** majority class,
  training-majority class and previous direction. Weighted F1 is never compared
  with them.
- **Quality gate.** Every model is `below_baseline`, `experimental`, `candidate`
  or `validated`. DEMO data caps a model at experimental; "validated" needs real
  data, 200+ validation rows over 2+ dates, a 95% accuracy lower bound above
  every baseline, and log loss better than the class prior.
- **Minimum data.** Configurable `ML_MIN_*` limits return `insufficient_data`
  before fitting.
- **Near-perfect accuracy is flagged as suspicious**, not celebrated: at or
  above 95% the run carries a warning to inspect for leakage.

### Selection rule

Highest weighted F1 on the validation split. F1 rather than accuracy because
the classes are imbalanced; weighted rather than macro so each class counts in
proportion to how often it occurs. Ties break toward the simpler model.

## Documentation

- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) — full specification and 10-day roadmap
- [CLAUDE.md](CLAUDE.md) — working rules and current state
- [docs/design-direction.md](docs/design-direction.md) — visual language
- [docs/PHASE_7_REPORT.md](docs/PHASE_7_REPORT.md) — prediction contract, formula, verification and limitations
- [docs/PHASE_12_REPORT.md](docs/PHASE_12_REPORT.md) — ML validation audit, leakage fix, provenance policy, quality gate and real-data conditions
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — Render/Vercel runbook, environment variables, backups, smoke test
- [docs/DURABLE_STORAGE.md](docs/DURABLE_STORAGE.md) — production dataset/model storage and migration 0005
- [docs/MARKETPLACE_SOURCES.md](docs/MARKETPLACE_SOURCES.md) — provider findings, the Flipkart LIVE connector, fields and constraints
- [docs/PHASE_10_REPORT.md](docs/PHASE_10_REPORT.md) — deployment verification evidence and remaining blockers
- [OVERALL_PROJECT_REPORT.md](OVERALL_PROJECT_REPORT.md) — project-wide status

## Experimental prediction workflow

1. Collect, import, or load DEMO snapshots on **Marketplace Data**.
2. Build a processed dataset and explicitly train a model on **Train Model**.
3. Open **ML Predictor**, search/select a stored electronics product, and inspect
   its latest observations. Click **Make Prediction** to compare available platforms.
4. Inspect validation accuracy versus majority baseline accuracy, weighted F1,
   provenance, observation dates, class probabilities, and score contributions.
5. Reopen a saved result from **Your recent predictions**. Historical results keep
   their original quality metrics, even after another model is trained.

Prediction uses the exact saved Pipeline and never trains or rebuilds its
preprocessing. Optional missing values remain missing for the saved imputer;
missing required columns cause a compatibility error. Product matching preserves
Phase 5's strict normalized name + brand + category identity.

Authenticated Phase 7 endpoints (subject to `API_PREFIX`):

| Method | Route | Purpose |
|---|---|---|
| GET | `/ml/prediction-options?q=&limit=50&offset=0` | Search the latest dataset and preview observations |
| POST | `/ml/predict` | Predict and persist a successful comparison |
| GET | `/ml/predictions?limit=20&offset=0` | Current user's history and total count |
| GET | `/ml/predictions/{id}` | Current user's original saved result |

Example request, using a product key returned by the options endpoint:

```json
{
  "product_key": "acme 20000mah|acme|power banks",
  "platforms": ["amazon", "flipkart", "croma", "alibaba"]
}
```

`dataset_id` optionally pins the previewed dataset; otherwise the newest prepared
dataset is used. The frontend pins its preview. No arbitrary manual feature
vectors are accepted. Phase 7 supports INR observations in the eight canonical
electronics categories already defined by Phase 5.

The fixed 100-point score uses model probability (10), price competitiveness
(20), rating (15), review signals (15), discount (10), competition (15), and price
trend (15). Missing components receive no points, are explicitly identified, and
never increase ML's weight. At least three observed deterministic components,
covering 40 points, plus a positive observed price are required. The score is a
heuristic, not a probability of success or an estimate of profit or sales demand.
The full formula is in `backend/app/ml/opportunity.py` and is returned by the API.

Observations older than seven days remain usable for demonstration but are
labelled **STALE**, with instructions to refresh and rebuild. All observation
timestamps remain visible; a recent dataset build does not imply recent observations.
Unavailable platforms return `insufficient_data`, never invented scores.

Migration `0004` adds a nullable JSON result snapshot to the existing Prediction
table and runs automatically on backend startup. Existing rows are preserved.
No model or dataset persistence infrastructure was changed.

Tests now use isolated database, artifact and processed-dataset storage, preserving
the bundled demo fixture. On PowerShell, use `npm.cmd run build` / `npm.cmd run lint`
if execution policy blocks `npm.ps1`. If the surrounding shell exports
`DEBUG=release`, it is explicitly interpreted as false. Prefer `DEBUG=false`;
unknown non-boolean values are rejected. Tests isolate their settings.


## Stored analytics (Phase 8)

Open **Trend Analysis** for per-listing price, discount, rating, review and
availability history. Open **Analytics** for exact-product or explicitly grouped
category comparisons. Both use authenticated snapshot-only APIs:

| GET endpoint | Purpose |
| --- | --- |
| `/analytics/trends` | Separate listing histories and deterministic metrics |
| `/analytics/platform-comparison` | Comparable platform statistics; matching saved Phase 7 scores where available |
| `/analytics/summary` | Stored counts, latest observation, model/dataset context and usable collector status |
| `/analytics/options` | Searchable, paginated product choices from snapshots |

Filters: `product`, `product_key`, `platform`, `category`, `source_type`,
`start_date`, `end_date`. Dates include both complete UTC calendar days.
Trends accept `limit` (1?100, default 20) and `offset`; options additionally
accept `q`, with default limit 50. `API_PREFIX` applies to all routes.

Histories never combine sources, currencies or distinct listing IDs. Fewer than
two valid readings cannot establish change or direction. Missing latest signals
stay null; historical means remain available. Price direction uses a ?1% band
across the selected window. Review momentum is net reviews per day, not sales.

**Refresh Market Data** remains disabled with collector-specific reasons until a
supported collector is available. **Reload stored analytics** only rereads stored
data. No scheduled jobs or model retraining were added. See
[Phase 8 report](docs/PHASE_8_REPORT.md) for calculations, validation and a DEMO example.


## Stabilization (Phase 9)

The backend integration test exercises a fresh database through register/login,
demo loading and JSON import, dataset build, Random Forest training, prediction,
score display APIs, trends/comparison, history, user isolation and a second startup.
It uses temporary database, dataset and model directories. No development data is
removed and no development model is retrained by the checks.

Security fixes require JWT expiry/issued-at/subject claims, avoid echoing password
inputs in validation errors, handle registration races, bound uploaded-file reads,
validate model/date/platform selections, and return generic unexpected failures.
Startup migrations preserve application logging. Model training is guarded against
overlapping calls in one process and refuses to overwrite an existing artifact.
Run one backend worker until cross-process coordination is implemented.

The frontend uses shared error handling for JSON and multipart calls: 30-second
request timeouts, 120 seconds for imports, and 300 seconds for training. A timeout
**does not cancel server work**; check status before retrying a mutation. Rejected
sessions return to sign-in with a message; logout clears client storage, including
other open tabs. JWTs remain stateless: a copied token stays valid until expiry
or account deactivation. localStorage token storage and the shared operator data/
model workspace are existing MVP limitations, not production multi-tenant isolation.

The mobile drawer contains focus, supports Escape, locks background scrolling and
restores focus on close. Charts can scroll at narrow widths. Live/source warnings
remain visible. No browser was available for interactive desktop/tablet/mobile QA;
these layout changes are code-reviewed, not visually certified. Backend tests,
frontend request tests, build and lint provide the automated evidence.

See [Phase 9 report](docs/PHASE_9_REPORT.md) for the file inventory, checks and
remaining Phase 10 blockers. No deployment was attempted.

## Deployment (Phase 10)

**Status: deployment-ready, not deployed.** No Render service, Vercel project,
domain or managed database has been created, so no live URL has been tested.

| Piece | Configuration |
| --- | --- |
| Backend | Render Blueprint `render.yaml`: build `pip install -r backend/requirements.txt`, start `cd backend && python -m app.start`, health check `/ready`, one instance and worker |
| Frontend | Vercel, Root Directory `frontend`, `frontend/vercel.json` (`npm ci`, `npm run build`, `dist`, SPA rewrite); `VITE_API_BASE_URL` must be the HTTPS backend URL |
| Database and storage | PostgreSQL `DATABASE_URL` (required in production); datasets and models in `stored_objects` |
| Backups | Provider backups or PITR plus `pg_dump -Fc` before each deploy; one database backup covers data, datasets and models |

Verified locally, not on the platforms:

- migrations, storage and a production-mode API journey with restart against PostgreSQL 17
- Render's build and start commands in a Linux Python 3.14.7 container (all wheels,
  `pip check` clean, about 300 MiB peak RSS on the DEMO pipeline)
- 60/60 Playwright checks in Chromium (not Firefox or Safari) at desktop, tablet
  and mobile: login, every dashboard page, refresh on each protected route, a
  prediction, logout
- a PostgreSQL dump and restore with checksum verification

Environment variables, the live smoke checklist, backup commands and limitations:
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Evidence and remaining blockers:
[docs/PHASE_10_REPORT.md](docs/PHASE_10_REPORT.md). Storage design:
[docs/DURABLE_STORAGE.md](docs/DURABLE_STORAGE.md).
