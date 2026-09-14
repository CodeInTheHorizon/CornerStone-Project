# Phase 10 - Production Deployment and Verification

**Updated:** September 14, 2026

## Outcome

Phase 10 is **deployment-ready and locally production-verified, but not deployed.**
No Git remote, Render or Vercel account, platform CLI, deployment URL or production
database credential exists in this workspace. **No Render service, Vercel project or
hosted database was created, and no live URL was tested.**

Verification that the Render and Vercel targets would otherwise have provided
was done locally with real components:

| Stand-in | What it replaced |
| --- | --- |
| PostgreSQL 17.11 (Docker, loopback only, disposable) | managed PostgreSQL |
| `python:3.14.7-slim` Linux container running Render's exact build and start commands, from the files git would push | Render web service |
| Production frontend bundle served by a static server implementing the `vercel.json` rewrite | Vercel hosting |
| Playwright Chromium at desktop, tablet and mobile sizes | manual browser QA |

Run instructions, environment variables and the backup plan are in
[DEPLOYMENT.md](DEPLOYMENT.md). Storage design is in [DURABLE_STORAGE.md](DURABLE_STORAGE.md).

## Timeline

| Commit / state | Content |
| --- | --- |
| `de173ee` | Phases 1-9 checkpoint |
| `ae86a21` | Deployment foundation (`render.yaml`, `app.start`, `/ready`, `vercel.json`, production settings validation), durable storage (`app/storage/`, migration `0005`) and the post-interruption stabilization |
| This update | PostgreSQL, Linux, browser, migration and backup verification, plus the two defects below |

## Defects found and fixed during verification

1. **Concurrent startup migrations crashed** (`backend/app/database/migrate.py`).
   Four processes migrating an empty PostgreSQL schema at once: three of four exited
   with `UniqueViolation` on `pg_type`. No data was harmed (transactional DDL), but an
   overlapping deploy or restart could fail to start. `upgrade_to_head` now takes a
   transaction-scoped `pg_advisory_xact_lock` and reads the current revision inside
   the lock. Afterwards four of four succeeded in two runs, and a regression test was
   added. SQLite is unaffected.
2. **Production bundles embedded a localhost API fallback** (`frontend/src/config/env.ts`).
   Any production build without `VITE_API_BASE_URL` outside Vercel shipped
   `http://127.0.0.1:8000` (two occurrences in the committed build). The fallback now
   applies only in the Vite dev server. An unconfigured production bundle contains no
   localhost URL, and `apiRequest` reports "The API address is not configured"
   instead of calling the visitor's machine. The Vercel build guard is unchanged.

Also changed:
- `render.yaml` now declares `numInstances: 1` and has an accurate header comment.
- **Test-only change: widened subprocess startup deadlines.**
  `test_startup_and_exact_cors_with_local_database` failed twice in isolation
  (after passing in a full run) because its 40 s deadline covered a cold child
  import of pandas/scikit-learn/scipy. That import measured 10-31 s while the
  shared desktop CPU was at 100%, and the child logged nothing. The subprocess
  startup tests now allow 180-240 s and still fail immediately if the process exits.

No ML features, targets, scoring formulas, connectors or API contracts changed.

## 1. PostgreSQL validation - passed (local server)

- `DATABASE_URL`: `postgres://` and `postgresql://` normalize to `postgresql+psycopg`.
  Unsupported drivers (`psycopg2`, `asyncpg`, MySQL, malformed) are rejected without
  echoing credentials. A percent-encoded `options=-csearch_path%3D...` query passes
  through settings, SQLAlchemy and Alembic interpolation.
- psycopg 3.3.5 (binary) connects to PostgreSQL 17.11 on Windows and on Linux.
- Migrations `0001`-`0005` applied to empty schemas, both from the Windows test run
  and from inside the Linux container. `stored_objects` has a BYTEA payload,
  a composite primary key and the checksum columns. The migrated schema matches the
  models (`compare_metadata` is empty). A user inserted at `0004` survives upgrading
  to `0005`, and a repeated upgrade is a no-op.
- PostgreSQL test run: `tests/test_postgresql.py` (4 tests) and the PostgreSQL
  parameter of the `tests/test_storage.py` adapter contract (6 tests) all passed.

## 2. Render backend - configuration verified, not deployed

- `render.yaml` parses as YAML: one `web` service, `runtime: python`, `numInstances: 1`,
  build `pip install -r backend/requirements.txt`, start `cd backend && python -m app.start`,
  `healthCheckPath: /ready`, 13 environment entries (`JWT_SECRET_KEY` generated,
  `DATABASE_URL` and `CORS_ORIGINS` prompted). Every application key maps to a
  setting, and production settings built from these values validate.
- Linux container, from the 310 KB set of git-pushable files (no `.venv`,
  `node_modules`, `*.db`, `*.pkl` or `.env`):
  - Python 3.14.7 x86_64
  - every pinned package installed from a prebuilt wheel, none compiled from source
  - `pip check`: no broken requirements
  - `python -m app.start` migrated `0001`-`0005` and served on `0.0.0.0:$PORT`
- Linux smoke test:
  - `/health` returned `ok` with `environment: production`; `/ready` returned 200 `connected`
  - register, login and `/auth/me` succeeded
  - dataset status and model status returned 200, and 401 without a token
  - CORS allowed the configured Vercel origin and gave no allow-origin to `other.vercel.app`
  - no secret or password appeared in the logs
- Capacity (local Linux, 480-row DEMO): peak RSS about 300 MiB (307,148 kB) through
  demo load, dataset build, Random Forest and XGBoost training (6.9 s) and prediction
  (0.48 s). Render's CPU and memory limits are not measured.

## 3. Vercel frontend - configuration verified, not deployed

- `vercel.json`: framework `vite`, `npm ci`, `npm run build`, output `dist`, rewrite
  `/(.*)` to `/index.html`.
- Build guard with `VERCEL=1`: a missing URL fails, `http://localhost:8000` fails, and
  `https://…onrender.com` builds with that URL in the bundle and no `127.0.0.1:8000`.
- A plain production build without `VITE_API_BASE_URL` contains no localhost URL.
- The SPA rewrite was simulated locally, not observed on Vercel. `/`, `/login`,
  `/dashboard/train` and `/dashboard/analytics` returned the app shell, assets loaded,
  and refreshes stayed on the route (see browser results).
- Cross-origin calls from the frontend origin to the separate backend origin worked in Chromium.

## 4. Migration startup - passed

| Check | Result |
| --- | --- |
| Unknown recorded revision (`9999_unknown`) | `app.start` exits non-zero, never logs startup complete, and the database and its rows are untouched (`test_failed_migration_stops_startup_without_touching_data`) |
| Unreachable PostgreSQL in production | exits non-zero, password not logged (`test_production_startup_stops_when_database_unreachable`) |
| Four concurrent startups on an empty PostgreSQL schema | all succeed, one revision row `0005` (`test_concurrent_startup_migrations_serialize`) |
| Existing rows across `0004` to `0005` | preserved (`test_postgresql_upgrade_persistence_and_schema`) |
| Linux production startup on an empty schema | `0001` to `0005`, then serving |

No multi-worker configuration was introduced.

## 5. Storage against PostgreSQL - passed

`test_production_journey_on_postgresql` runs real `python -m app.start` processes in
production mode with `STORAGE_BACKEND=database` and a restart in the middle:

| Behaviour | Evidence |
| --- | --- |
| Dataset save | `POST /ml/dataset/build` creates a `datasets` row; `csv_path` is `dbstore://datasets/…` |
| Dataset load | after restart, status lists 1 dataset and preview returns rows |
| Artifact save | `POST /ml/train` creates `artifacts/model_v1.pkl` |
| Artifact load | after restart, `/ml/status` reports v1 and prediction reloads the pipeline from PostgreSQL |
| Checksum validation | stored `sha256` equals PostgreSQL's `sha256(payload)` and sizes match; a tampered payload returns 503 `corrupt_artifact` |
| No overwrite | a second `put('model_v1.pkl')` raises `StorageConflict` |
| Missing object | deleting the dataset row leaves `has_dataset: false` and preview 404, with nothing fabricated |
| No local writes | no `DATA_DIR/processed` or `MODEL_ARTIFACT_DIR` was created |

The adapter contract (round trip, conflict, invalid keys, payload and manifest
corruption, size limit) also passes on PostgreSQL.

## 6. Deployment smoke test - no live target

No live deployment exists, so no live smoke test was possible. The listed backend
checks passed against the Linux Render-equivalent container, and the frontend checks
passed in the browser run below. The live checklist is in DEPLOYMENT.md.

## 7. Browser verification - passed locally (60/60)

Playwright Chromium against a production-mode backend on PostgreSQL (database
storage, seeded through the API with DEMO data, a dataset and a Random Forest model)
and the production bundle behind the rewrite server. Desktop 1440×900,
tablet 834×1112 and mobile 390×844 each covered:

- landing page
- anonymous `/dashboard/train` redirecting to login
- login
- sidebar or mobile-menu navigation to Marketplace Data, Train Model, ML Predictor,
  Trend Analysis, Analytics and Dashboard, each checked for expected content with
  no API error text and no horizontal overflow
- a page reload on every one of those routes, staying on the route and signed in
- a full prediction on ML Predictor
- logout, then a direct visit to `/dashboard/analytics` redirecting to login
- no unexpected API 4xx/5xx and no console or page errors

The first run reported 4 failures on Trend Analysis at tablet and mobile widths. The
cause was the test selector matching the hidden sidebar link; the page rendered
correctly. After scoping checks to `<main>`, all 60 passed. Screenshots were reviewed
for the mobile prediction, desktop Train Model and tablet Analytics; the Analytics
page settled in about 0.4 s with only 200 responses. This is not a hosted, assistive
technology or cross-browser (Firefox or Safari) audit.

## 8. Backups - plan documented and rehearsed locally

One consistent PostgreSQL backup covers accounts, observations, predictions, model
metadata and the stored dataset and model binaries. The plan: provider automated
backups or PITR as primary, `pg_dump -Fc` before every deploy and weekly as
secondary, and a monthly restore drill with checksum SQL. Rehearsed on PostgreSQL 17:
dump (638 KB) and restore into a separate database gave identical revision, row
counts and stored-object checksums, and the restored model loaded and predicted on
the restored dataset. No hosted backup is configured and no schedule is automated.

## Validation

| Check | Result |
| --- | --- |
| Full backend suite with `TEST_POSTGRES_URL` (PostgreSQL 17.11) | **341 passed, 0 skipped**, exit 0 (4 min 32 s) |
| PostgreSQL tests without `TEST_POSTGRES_URL` | skip cleanly (9 skipped) |
| Frontend `npm run build` | passed; bundle contains no `127.0.0.1:8000` |
| Frontend `npm run lint` | passed |
| Frontend `npm test` | **8 passed** |
| Vercel build guard (`VERCEL=1`) | missing and localhost URLs rejected; HTTPS URL accepted |
| Linux Render build and start (Python 3.14.7) | all wheels, `pip check` clean, migrated and serving, smoke test passed |
| Browser (Playwright Chromium, three viewports) | **60/60** |
| PostgreSQL dump and restore | counts and checksums identical; restored model inferred |
| `git diff --check` | clean |
| Development data and model preservation | development SQLite database (still `0004`, active v5, 24 users, 2 predictions) and all 159 local data/model files byte-identical; tests used temporary storage and throwaway PostgreSQL schemas |

## Remaining blockers

1. **Hosting access.** Push to a Git remote, create the Render Blueprint and the
   Vercel project, then run the live smoke checklist. Not possible from this workspace.
2. **Managed PostgreSQL with backups.** Choose a provider and plan with automated
   backups, set `DATABASE_URL`, and complete a hosted restore drill.
3. **Real domains.** Set Vercel `VITE_API_BASE_URL` and Render `CORS_ORIGINS` to the
   assigned HTTPS origins.
4. **Hosted capacity.** Measure training time and memory on the chosen Render plan.
   Training is synchronous and in-process on one worker.
5. **Public-use controls.** Role-based authorization for shared data and model
   operations, abuse and rate limits, and server-side token revocation.
6. **Product limits (outside Phase 10).** No approved live marketplace source; data is
   DEMO and the model is below its majority-class baseline.
