# Phase 10 - Vercel and Render deployment

Phase 10.5 adds durable PostgreSQL storage. Production now requires DATABASE_URL
and uses database-backed dataset/model bundles; the old disposable SQLite
production configuration is rejected. No live deployment has been performed.
See [DURABLE_STORAGE.md](DURABLE_STORAGE.md) for architecture and migration details.

## Preserve the existing application

Checkpoint `de173ee` contains Phases 1-9, including previously uncommitted work.
Development database, processed files and model artifacts are ignored by Git and
are not uploaded by a Git deployment. Keep them in place. Switching DATABASE_URL does not transfer them. Do not copy private
development accounts or pickle files into a public repository.

The new deployment starts empty. Load the existing bundled DEMO fixture explicitly
through Marketplace Data, build a dataset and train explicitly if a demonstration
needs a model. No startup seeding, automatic training or fake live collection runs.
Changing a machine or directory does not automatically repair absolute paths in
existing dataset metadata or model records; data transfer needs a separate plan.

## 1. Publish the code checkpoint and deployment changes

Review `git diff` and the Phase 10 report, commit the deployment files, and push to
the intended Git provider repository. No remote is configured in this workspace.
Configure one only after choosing the repository; do not publish ignored files.
Connect that repository to Render and Vercel using their account dashboards.

## 2. Render backend

Create a Blueprint from the repository-root `render.yaml`. Choose a new service
name if `marketpulse-api` is already used. The configuration declares:

| Setting | Value |
| --- | --- |
| Root directory | Repository root; leave Render Root Directory empty |
| Runtime | Python 3.14.7, matching the current development interpreter |
| Build command | `pip install -r backend/requirements.txt` |
| Start command | `cd backend && python -m app.start` |
| Health check | `/ready` |
| Workers | One; no reload or automatic scaling |
| Plan | Free disposable demo; memory capacity for ML is not verified |
| Automatic deployment | Off; deploy manually after review |

`app.start` calls Uvicorn with validated HOST/PORT and logging settings. Render
injects PORT. Startup applies existing Alembic migrations before serving requests.
Keeping the repository root includes `data/demo`, which is outside `backend`.

Provision a durable PostgreSQL database with backups and enter its private connection
URL for DATABASE_URL. The Blueprint does not provision or purchase that database.
Use provider-required TLS settings (for an external TLS endpoint, append
`?sslmode=require`, or use certificate validation as instructed by the provider).
Enter the exact planned Vercel production origin when prompted for CORS_ORIGINS.
Render generates JWT_SECRET_KEY; retain it across deploys. Never paste it into
frontend settings, screenshots, source files or this report.

After deployment, open `https://YOUR-BACKEND.onrender.com/ready` and `/health`.
Readiness must return HTTP 200 with `database: connected`. `/health` keeps the
original HTTP 200 degraded-status contract, so Render probes `/ready` instead.
A healthy response verifies process/database access, not model accuracy or storage durability.

## 3. Vercel frontend

Import the same Git repository into Vercel:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Framework | Vite |
| Node.js | `24.x` (also declared in package.json) |
| Install | `npm ci` |
| Build | `npm run build` |
| Output | `dist` |
| Public API URL | `VITE_API_BASE_URL=https://YOUR-BACKEND.onrender.com` |

Set VITE_API_BASE_URL in the Production environment before building. Vercel builds
reject missing, malformed, non-HTTPS or localhost API destinations. Ordinary local
builds retain the existing localhost fallback. Environment values are compiled
into the frontend bundle: changing the API URL requires a new deployment.

`frontend/vercel.json` rewrites SPA deep links to index.html. Verify direct visits
and refreshes at `/login`, `/dashboard/predictor`, `/dashboard/trends` and
`/dashboard/analytics`. Protected routes should show login when signed out.
Check that JS/CSS assets still load successfully. The frontend calls Render
directly; this rewrite does not proxy API requests.

After Vercel assigns the actual production domain, set Render CORS_ORIGINS to
that exact HTTPS origin and redeploy Render if it differs from the planned value.
Preview URLs need their own explicit allowlist entries; do not allow every Vercel
tenant. A custom domain must also be added explicitly.

## Required and optional environment variables

| Variable | Location | Required value / default |
| --- | --- | --- |
| ENVIRONMENT | Render | `production` |
| JWT_SECRET_KEY | Render secret | Random private value of at least 32 bytes; Blueprint generates it |
| CORS_ORIGINS | Render | Exact HTTPS production frontend origin; CSV or JSON list |
| DEBUG | Render | `false`; legacy `release` also resolves false |
| SQL_ECHO | Render | `false`; true rejected outside development |
| HOST | Render | `0.0.0.0` |
| PORT | Render | Injected by Render, integer 1-65535 |
| PYTHON_VERSION | Render build | `3.14.7` |
| PYTHONUNBUFFERED | Render | `1` |
| LOG_LEVEL | Render | `INFO`; DEBUG/INFO/WARNING/ERROR/CRITICAL accepted |
| ACCESS_LOG | Render | `false`; avoids logging request URLs/query strings by default |
| VITE_API_BASE_URL | Vercel build | Actual HTTPS backend URL; append API_PREFIX if configured |
| API_PREFIX | Render, optional | Empty default; `/health` and `/ready` always unprefixed |
| DATABASE_URL | Render, required | Durable PostgreSQL URL; local development still defaults to SQLite |
| STORAGE_BACKEND | Render | `database`; `auto` selects database outside development |
| STORAGE_MAX_BYTES | Backend, optional | `134217728` (128 MiB per binary object) |
| DATA_DIR | Local development, optional | Existing repository `data` directory |
| MODEL_ARTIFACT_DIR | Local development, optional | Existing `backend/app/ml/artifacts` directory |
| JWT_ALGORITHM | Backend, optional | `HS256` |
| ACCESS_TOKEN_EXPIRE_MINUTES | Backend, optional | `720` |
| APP_NAME / APP_VERSION | Backend, optional | `MarketPulse AI API` / `0.1.0` |
| VITE_APP_NAME | Vercel, optional | `MarketPulse AI` |
| VITE_WHATSAPP_NUMBER | Vercel, optional | Public international digits; blank disables contact submission |

Existing marketplace credentials are not required for this deployment: the current
live integrations remain unavailable. No new connector is enabled.

Backend settings read repository `.env`, then `backend/.env`; process environment
overrides both. Frontend Vite reads `frontend/.env*` with the configured project
root. Root `.env` frontend values alone do not configure Vite. Examples are not
loaded automatically. Never deploy `.env` files or use VITE_ for private values.

For local development keep ENVIRONMENT=development, the SQLite defaults and
`CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`. Development commands
remain `python -m uvicorn app.main:app --reload` from backend and `npm run dev`
from frontend. In PowerShell use `npm.cmd` if npm.ps1 is blocked.

## Hosted verification still required

1. Confirm Linux dependency installation succeeds with the existing pinned packages.
2. Verify readiness, health and startup migration logs without exposing secrets.
3. Verify allowed-origin preflight and rejection of an unrelated origin.
4. Verify SPA links, auth/session handling and the complete DEMO pipeline in browser.
5. Verify process memory/time limits during training; one worker is required by the
   current training lock. No instance size has been benchmarked on Render.
6. Verify the actual PostgreSQL service, backups and restore before retaining production data.
7. Resolve public operator authorization/abuse controls before public multi-user use.

The active local model is DEMO-trained and below baseline. Deployment does not
make its predictions reliable or supply real-time marketplace data. No ML
features, target definitions or scoring formulas were changed. Phase 10.5 adds migration 0005.

## Platform references

- [Render FastAPI deployment](https://render.com/docs/deploy-fastapi)
- [Render Blueprint configuration](https://render.com/docs/blueprint-spec)
- [Render Python version selection](https://render.com/docs/python-version)
- [Render health checks](https://render.com/docs/health-checks)
- [Vite on Vercel and SPA rewrites](https://vercel.com/docs/frameworks/frontend/vite)
- [Vite environment loading](https://vite.dev/guide/env-and-mode)
