# MarketPulse AI — Working Notes for Claude Code

Read `PROJECT_CONTEXT.md` before making changes. It is the source of truth for
scope, architecture, the 10-day roadmap and the acceptance criteria.

## Current state

**Phase 1 (Project Foundation) complete.** Phases 2–10 not started.

Implemented: repository structure, FastAPI backend with config/CORS/`/health`,
SQLAlchemy models for `User`, `MarketplaceSnapshot`, `Prediction`,
`ModelMetadata`, and a React + Vite + TypeScript + Tailwind frontend with a
typed API client. No authentication, scraping, ML or analytics logic exists yet.

## Layout

```
backend/app/
  config.py       env-driven settings (pydantic-settings)
  main.py         app factory, CORS, router wiring
  api/            routes/ + aggregate router (feature routers land here)
  database/       engine, session, declarative Base
  models/         ORM models
  schemas/        pydantic request/response shapes
  auth/           Phase 3
  scrapers/       Phase 4
  ml/             Phases 5-7
  services/       business logic between API and DB
frontend/src/
  components/ pages/ services/ hooks/ types/ config/
```

## Rules

1. Work only on the requested phase; do not implement future phases early.
2. Inspect existing files before replacing them; preserve working code.
3. Keep frontend, backend, scraping, ML and analytics modular.
4. **Never fabricate marketplace data or ML metrics.** Metric columns stay NULL
   until a real evaluation run fills them. Demo rows must be tagged
   `source="demo"` (`DataSource.DEMO`) so they can never be shown as live data.
5. Marketplace collection must use officially permitted access paths. Never
   bypass CAPTCHAs, authentication, anti-bot protections or access controls. If
   a source cannot be collected reliably, return an explicit unsupported status.
6. No secrets in frontend code — only `VITE_`-prefixed public values.
7. Run the checks below after every phase and report results honestly.

## Commands

```bash
# Backend (from backend/)
.venv/Scripts/python -m pytest
.venv/Scripts/python -m uvicorn app.main:app --reload

# Frontend (from frontend/)
npm run build     # tsc -b && vite build
npm run lint
npm run dev
```

## Environment notes

- Python 3.14 on Windows. Dependency pins in `requirements.txt` are the versions
  verified installable on cp314 — several older pins have no 3.14 wheels, so
  bump rather than downgrade Python if a pin fails.
- The Vite dev server binds `localhost` (IPv6). `127.0.0.1:5173` will not
  connect; both origins are allowed in `CORS_ORIGINS` regardless.
- `Base.metadata.create_all()` runs on startup. Introduce Alembic before the
  schema changes in an environment holding real data.
