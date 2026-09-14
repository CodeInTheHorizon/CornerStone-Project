# MarketPulse AI - Working Notes for Claude Code

Read `PROJECT_CONTEXT.md` before making changes. It is the source of truth for
scope, architecture, the 10-day roadmap and the acceptance criteria.

## Current state

**Phases 1-11 implemented.** Phase 11 status, verbatim for reports:
- Flipkart Affiliate API LIVE connector implemented and tested with mocked responses.
- Connector is gated: credentials **and** Flipkart's written data-use approval are required.
- Flipkart credentials are missing (state `credentials_missing`).
- Written approval is required and not held (`FLIPKART_DATA_USE_APPROVED` stays false).
- **0 LIVE records**: no request has reached Flipkart and no real marketplace data was collected.
- ML is unchanged: no features, targets, training or scoring changed; the model is still DEMO-trained.

Never claim LIVE data or LIVE success. Phase 10 is deployment-ready and locally
production-verified (real PostgreSQL 17, a Linux Render build and start, a
Playwright browser pass), but **not deployed**: no Git remote, Render/Vercel
service, domain or managed database exists. Never claim a live deployment.

Phase 1: repository structure, FastAPI backend with config/CORS/`/health`,
SQLAlchemy models for `User`, `MarketplaceSnapshot`, `Prediction`,
`ModelMetadata`, React + Vite + TypeScript + Tailwind frontend, typed API client.

Phase 2: public landing page - navbar, hero, "Why Choose" flip cards, developer
profile, feature grid, WhatsApp contact form, footer; light/dark theming with a
pre-paint script; scroll reveals honouring `prefers-reduced-motion`.

Phase 3: bcrypt password hashing, JWT auth (`/auth/register`, `/auth/login`,
`/auth/me`), a protected dashboard shell with sidebar, summary cards and the
Train Model / Make Prediction actions. Sections beyond the overview render an
honest placeholder.

Phase 4: marketplace collection layer - collector interface, Amazon via the
official PA-API 5.0, honest unavailable stubs for Flipkart/Croma/Alibaba,
normalization, validation, dedup, /data/collect|latest|history|status, and the
Marketplace Data dashboard page. Alembic migrations replace create_all().

Phase 4.5: source-type provenance (live/imported/demo), a shared ingest
pipeline every path goes through, CSV/JSON import at /data/import, a synthetic
demo fixture at data/demo/, enriched /data/status (ingestion mode, required
configuration, stored provenance) and LIVE/IMPORTED/DEMO/UNAVAILABLE badges.

Phase 5: dataset builder and feature engineering - app/ml/{normalization,
features,dataset_builder}.py, dataset_service, /ml/dataset/{build,status,
preview}, CSV + metadata output to data/processed/, and the Dataset
Preparation panel on Train Model.

Phase 6: model training - app/ml/{target,training}.py, training_service,
/ml/{train,status,metrics}, versioned artifacts in app/ml/artifacts/,
ModelMetadata persistence, and training UI on Train Model plus the dashboard
model status card.

Phase 7: saved-Pipeline prediction, conservative opportunity scores, authenticated
/ml/predict and /ml/predictions history/detail, /ml/prediction-options product
selection, migration 0004 with immutable result JSON, and an active ML Predictor
page with comparison bars, provenance and model/baseline warnings.

Phase 8: snapshot-only analytics_service, authenticated /analytics/{trends,
platform-comparison,summary,options}, active Trends/Analytics pages, simple SVG
charts, actual dashboard summaries, and a disabled live-refresh hook with reasons.
Sources, currencies and listings remain separate; no model inference or training
runs in analytics. See docs/PHASE_8_REPORT.md for policies and limitations.

Phase 9: configuration/JWT/input hardening, shared request timeouts and session
expiry, migration logging preservation, bounded import/preview reads, consistent
unavailable collector status, training collision protection and mobile focus polish.
Fresh-install API journey and frontend request regressions are in tests. See
docs/PHASE_9_REPORT.md; browser interaction remains unverified (no available browser).

Phase 10: `render.yaml` (one instance) + `python -m app.start` (one worker),
`/ready` returning 503 when the DB is unreachable, `frontend/vercel.json` with SPA
rewrite, Vercel builds requiring an HTTPS `VITE_API_BASE_URL`, and production
settings validation.
- **Durable storage:** `app/storage/` (local and database adapters, checksummed
  immutable bundles), `STORAGE_BACKEND`/`STORAGE_MAX_BYTES`, migration 0005
  (`stored_objects`). Outside development, settings require a PostgreSQL
  `DATABASE_URL` (normalized to `postgresql+psycopg`) and database storage;
  development keeps SQLite and local files.
- **Startup migrations** take a PostgreSQL advisory lock
  (`app/database/migrate.py`) so concurrent startups cannot race, and any
  migration failure stops startup.
- **Frontend:** the `127.0.0.1:8000` API fallback is dev-server only; production
  bundles without `VITE_API_BASE_URL` report "API address is not configured".
- **Docs:** docs/DEPLOYMENT.md holds the env var lists, backup plan and live smoke
  checklist; docs/PHASE_10_REPORT.md has the evidence and remaining blockers.

Phase 11 (LIVE marketplace data; details in docs/MARKETPLACE_SOURCES.md):
- **Connector:** `app/scrapers/flipkart.py` is `FlipkartCollector`, the official
  Affiliate API 1.0 search endpoint with bounded retries, `Retry-After` handling,
  credential redaction and affiliate-id stripping from URLs. It runs only with
  `FLIPKART_AFFILIATE_ID`, `FLIPKART_AFFILIATE_TOKEN` (SecretStr) **and**
  `FLIPKART_DATA_USE_APPROVED=true`, which records Flipkart's written approval;
  its terms limit use to its own platform. Never default that flag to true or
  bypass the gate.
- **Other platforms:** Amazon PA-API 5 was retired on 15 May 2026, and the
  Creators API terms forbid aggregation, seller tools and ML training without
  approval, so the registry policy keeps Amazon `unavailable`. Croma has no API.
  Alibaba's Open API is seller-only.
- **Collector states** (`CollectorState`): live, credentials_missing,
  approval_required, credentials_rejected, rate_limited, provider_error,
  unavailable. `collection_service.platform_statuses` overlays the latest
  attempt on each collector's static status.
- **Provenance:** `collection_attempts` (migration 0006) logs every outbound fetch,
  failures included; LIVE snapshots link to it via `collection_run_id`. A 429
  sets `retry_after_at`, and `/data/collect` then returns 429 without calling the
  provider.
- **History** is append-only. `ingest.recent_live_duplicate` skips only a LIVE
  observation identical to one stored for the same listing within 10 minutes.
- **Flipkart gives no product rating or review count;** those stay NULL (never
  seller ratings). One refresh returns at most 10 results. No scheduler.
- **Tests** use `httpx.MockTransport` (`tests/test_flipkart.py`,
  `tests/test_live_collection.py`). `tests/test_flipkart_live.py` is opt-in via
  `RUN_FLIPKART_LIVE_TEST=1` plus credentials and approval.

No scheduled jobs have been implemented.
See docs/PHASE_7_REPORT.md for the exact score formula. Preserve historical
model quality with every saved prediction.

## Layout

```
backend/app/
  config.py       env-driven settings (pydantic-settings)
  main.py         app factory, CORS, router wiring
  api/            routes/ + aggregate router (feature routers land here)
  start.py        production entrypoint (python -m app.start)
  database/       engine, session, declarative Base
  models/         ORM models
  schemas/        pydantic request/response shapes
  auth/           security.py (hashing, JWT), dependencies.py (get_current_user)
  scrapers/       base (collector contract, states, errors), parsing, validation,
                  registry + one module per platform (flipkart = Affiliate API)
  ml/             normalization, features, dataset_builder, target, training, opportunity
  services/       ingest, collection, import, demo, dataset, training, prediction, analytics, user
  storage/        dataset/artifact stores over local files or DB bundles
frontend/src/
  components/     reusable UI primitives
  sections/       landing page sections
  pages/          routed pages
  theme/          themeContext.ts + ThemeProvider.tsx
  lib/            pure helpers (cn, contactForm)
  services/ hooks/ types/ config/
```

## Frontend conventions

- Landing copy lives in `src/config/site.ts`, not inside components.
- Colours come from semantic tokens (`bg-surface`, `text-muted`, `border-border-hair`)
  defined per theme in `src/index.css`. Never hardcode a hex in a component.
- Any colour change must be re-checked against WCAG AA in **both** themes.
- Do not pass responsive display classes (`hidden md:inline-flex`) to `Button`;
  its base sets `inline-flex` and the winner depends on stylesheet order. Put
  them on a wrapper element.

## Rules

1. Work only on the requested phase; do not implement future phases early.
2. Inspect existing files before replacing them; preserve working code.
3. Keep frontend, backend, scraping, ML and analytics modular.
4. **Never fabricate marketplace data or ML metrics.** Metric columns stay NULL
   until a real evaluation run fills them. Demo rows must be tagged
   `source="demo"` (`DataSource.DEMO`) so they can never be shown as live data.
   In the UI this means `SummaryCard` takes `unavailable="Not trained"` rather
   than a placeholder digit, and blocked actions state what is missing.
   Every stored row carries `source_type`; the demo fixture is synthetic and
   must always be badged DEMO, never rendered as a live observation.
   In feature engineering this means a value that cannot be computed is NaN,
   never 0 -- zero is a claim that nothing changed. Trend features must not
   look ahead: use expanding windows over each listing's own past only.
   In training it means metrics are always reported beside the majority-class
   baseline, near-perfect accuracy is flagged as suspected leakage rather than
   success, and the split stays time-aware because repeated observations of one
   listing make a random split leak.
5. Marketplace collection must use officially permitted access paths. Never
   bypass CAPTCHAs, authentication, anti-bot protections or access controls. If
   a source cannot be collected reliably, return an explicit unsupported status.
6. No secrets in frontend code - only `VITE_`-prefixed public values.
7. Run the checks below after every phase and report results honestly.

## Commands

```bash
# Backend (from backend/)
.venv/Scripts/python -m pytest
.venv/Scripts/python -m uvicorn app.main:app --reload

# Frontend (from frontend/)
npm run build     # tsc -b && vite build
npm run lint
npm test
npm run dev
```

## Environment notes

- Python 3.14 on Windows. Dependency pins in `requirements.txt` are the versions
  verified installable on cp314 - several older pins have no 3.14 wheels, so
  bump rather than downgrade Python if a pin fails.
- The Vite dev server binds `localhost` (IPv6). `127.0.0.1:5173` will not
  connect; both origins are allowed in `CORS_ORIGINS` regardless.
- The schema is managed by Alembic (`backend/migrations/`) and upgraded on
  startup. When you change a model, add a migration - `tests/test_migrations.py`
  fails if the migrated schema and the models disagree.
- Tests isolate database, model artifacts and generated datasets in temporary
  storage. Do not point test writes at the development artifact directory.
- The existing inactive v1 database record and artifact disagree. Phase 7 leaves
  them untouched and rejects incompatible metadata/pipelines.
- Development database (inspected read-only 2026-09-14): active model is **v5**
  (XGBoost, trained 2026-09-13 during the interrupted Phase 10 run; v1-v4 are
  inactive), 24 users, 2 saved predictions, 480 DEMO snapshots, 0 LIVE. Alembic is
  still at **0004**; the next normal backend startup applies 0005 and 0006 (adds
  `stored_objects` and `collection_attempts` only). Do not delete or retrain over
  these files without being asked.
- Prediction is a DEMO pipeline demonstration: v5 (like v4) scores accuracy 33.3%
  vs majority baseline accuracy 40.6%, weighted F1 31.9%. Never equate class
  probability or the heuristic opportunity score with reliable marketplace advice
  or sales demand.
- In this sandbox pytest cannot write its default temp root; pass
  `--basetemp` pointing at a writable scratch directory if fixtures fail with
  `PermissionError`.
- PostgreSQL tests (`tests/test_postgresql.py`, the `postgresql` storage fixture)
  skip unless `TEST_POSTGRES_URL` is set. Docker Desktop is installed; a disposable
  `postgres:17-alpine` bound to `127.0.0.1` works (see docs/DEPLOYMENT.md). Each
  test uses its own schema. Never point it at a real database.
- Importing the app (pandas/scikit-learn/scipy) takes 10-30 s when the machine is
  busy. Subprocess startup tests allow 180-240 s; do not tighten them.

- DEBUG defaults false; legacy DEBUG=release is false. Exact CORS origins accept
  comma-separated text or JSON. Non-development secrets need at least 32 bytes.
- Training lock is process-local; run one worker pending cross-process coordination.
