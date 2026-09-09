# MarketPulse AI — Working Notes for Claude Code

Read `PROJECT_CONTEXT.md` before making changes. It is the source of truth for
scope, architecture, the 10-day roadmap and the acceptance criteria.

## Current state

**Phases 1-4 complete.** Phases 5-10 not started.

Phase 1: repository structure, FastAPI backend with config/CORS/`/health`,
SQLAlchemy models for `User`, `MarketplaceSnapshot`, `Prediction`,
`ModelMetadata`, React + Vite + TypeScript + Tailwind frontend, typed API client.

Phase 2: public landing page — navbar, hero, "Why Choose" flip cards, developer
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

No ML or analytics logic exists yet.

## Layout

```
backend/app/
  config.py       env-driven settings (pydantic-settings)
  main.py         app factory, CORS, router wiring
  api/            routes/ + aggregate router (feature routers land here)
  database/       engine, session, declarative Base
  models/         ORM models
  schemas/        pydantic request/response shapes
  auth/           security.py (hashing, JWT), dependencies.py (get_current_user)
  scrapers/       base, parsing, validation, registry + one module per platform
  ml/             Phases 5-7
  services/       business logic between API and DB
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
- The schema is managed by Alembic (`backend/migrations/`) and upgraded on
  startup. When you change a model, add a migration - `tests/test_migrations.py`
  fails if the migrated schema and the models disagree.
