# MarketPulse AI - Working Notes for Claude Code

Read `PROJECT_CONTEXT.md` before making changes. It is the source of truth for
scope, architecture, the 10-day roadmap and the acceptance criteria.

## Current state

**Phases 1-9 complete.** Phase 10 partially implemented: deployment-ready
configuration and durable storage exist, but **nothing has been deployed or
live-verified** (no Render/Vercel service, no real PostgreSQL server tested).

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

Phase 10 (in progress): `render.yaml` + `python -m app.start` (one worker),
`/ready` returning 503 when the DB is unreachable, `frontend/vercel.json` with SPA
rewrite, Vercel builds requiring an HTTPS `VITE_API_BASE_URL`, and production
settings validation. Durable storage: `app/storage/` (local and database
adapters, checksummed immutable bundles), `STORAGE_BACKEND`/`STORAGE_MAX_BYTES`,
and migration 0005 (`stored_objects`). Outside development, settings require a
PostgreSQL `DATABASE_URL` (normalized to `postgresql+psycopg`) and database
storage; development keeps SQLite and local files. The interrupted durable-storage
run was stabilized, not signed off; no Phase 10.5 report exists. See
docs/PHASE_10_REPORT.md, docs/DEPLOYMENT.md and docs/DURABLE_STORAGE.md.

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
  scrapers/       base, parsing, validation, registry + one module per platform
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
  inactive), 24 users, 2 saved predictions, 480 DEMO snapshots. Alembic is still
  at **0004**; the next normal backend startup applies 0005 (adds `stored_objects`
  only). Do not delete or retrain over these files without being asked.
- Prediction is a DEMO pipeline demonstration: v5 (like v4) scores accuracy 33.3%
  vs majority baseline accuracy 40.6%, weighted F1 31.9%. Never equate class
  probability or the heuristic opportunity score with reliable marketplace advice
  or sales demand.
- In this sandbox pytest cannot write its default temp root; pass
  `--basetemp` pointing at a writable scratch directory if fixtures fail with
  `PermissionError`.

- DEBUG defaults false; legacy DEBUG=release is false. Exact CORS origins accept
  comma-separated text or JSON. Non-development secrets need at least 32 bytes.
- Training lock is process-local; run one worker pending cross-process coordination.
