# MarketPulse AI

AI/ML-driven demand forecasting and marketplace intelligence for electronics
sellers.

MarketPulse AI collects fresh marketplace observations, turns them into a
structured dataset, trains models on it, and surfaces trend analytics and
cross-platform opportunity scores through an interactive dashboard.

> **Status: Phase 3 of 10 (Authentication + Dashboard Shell).**
> The landing page, accounts and the protected dashboard shell work. Marketplace
> data collection, the ML pipeline and analytics are **not** implemented yet.
> See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for the roadmap.

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
cd backend  && .venv/Scripts/python -m pytest   # 7 tests
cd frontend && npm run build                    # tsc -b && vite build
cd frontend && npm run lint                     # oxlint
```

## Environment variables

All configuration is environment-driven; see [`.env.example`](.env.example).

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL. SQLite locally, PostgreSQL in production. Leave unset locally — a relative `sqlite:///` URL resolves against the working directory. | absolute `<repo-root>/data/marketpulse.db` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. | `http://localhost:5173,http://127.0.0.1:5173` |
| `ENVIRONMENT` | `development` / `production`. | `development` |
| `API_PREFIX` | Prefix for feature endpoints. Empty matches the API outline in PROJECT_CONTEXT.md §15. `/health` is always unprefixed. | *(empty)* |
| `JWT_SECRET_KEY` | Signs access tokens. **Must** be overridden outside development — startup refuses the default. | dev placeholder |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime. | `720` (12h) |
| `VITE_API_BASE_URL` | Backend base URL used by the browser. | `http://127.0.0.1:8000` |
| `VITE_WHATSAPP_NUMBER` | Destination for the contact form, digits only (e.g. `919876543210`). Empty disables the form, which then says so. | *(empty)* |

Only `VITE_`-prefixed variables reach the browser bundle. Never put a secret in one.

## Architecture

```
backend/app/
├── config.py            environment-driven settings
├── main.py              application entrypoint, CORS, routers
├── api/                 HTTP layer (routes/ + aggregate router)
├── database/            engine, session factory, declarative Base
├── models/              User, MarketplaceSnapshot, Prediction, ModelMetadata
├── schemas/             pydantic request/response shapes
├── auth/                Phase 3
├── scrapers/            Phase 4 — marketplace collectors
├── ml/                  Phases 5–7 — features, training, prediction
└── services/            business logic between API and database

frontend/src/
├── components/  reusable UI primitives (Button, Section, FlipCard, Navbar, Icon...)
├── sections/    landing page sections (Hero, WhyChoose, Developer, Features, Contact)
├── pages/       routed pages
├── theme/       light/dark theme context and provider
├── services/    typed API client
├── lib/         pure helpers (validation, WhatsApp link building)
└── hooks/  types/  config/

data/{raw,processed,demo}   dataset storage
docs/                       design direction and notes
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | — | Service descriptor |
| `GET` | `/health` | — | Liveness + database reachability |
| `GET` | `/docs` | — | OpenAPI UI |
| `POST` | `/auth/register` | — | Create an account, returns a token |
| `POST` | `/auth/login` | — | Exchange credentials for a token |
| `GET` | `/auth/me` | Bearer | The authenticated user |

Data-collection, ML and analytics endpoints arrive in Phases 4 and 6–8.

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
| `/dashboard/marketplace-data`, `/predictor`, `/train`, `/trends`, `/analytics` | Required | Section placeholders — routes exist, features arrive in Phases 4–8 |

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
| `model_metadata` | One row per training run: dataset size, feature names, measured metrics, artifact path. |

## Limitations

These are current and deliberate — please read before evaluating the project.

- **Nothing is collected or predicted yet.** The landing page describes what the
  system will do; the data and ML layers behind it are still to be built.
- **The contact form does not reach a server.** It validates locally and hands the
  message to WhatsApp. There is no contact endpoint, and nothing is stored.
- **Dashboard figures are not invented.** Model accuracy reads "Not trained" and
  data freshness reads "No data yet" because no model and no collection exist.
  They stay that way until a real training run and a real collection fill them.
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
- **Schema is created with `create_all()`**, not migrations. Alembic should be
  added before the schema changes in an environment holding real data.
- **SQLite by default.** Render's filesystem is ephemeral, so production needs a
  PostgreSQL `DATABASE_URL`.

## Documentation

- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) — full specification and 10-day roadmap
- [CLAUDE.md](CLAUDE.md) — working rules and current state
- [docs/design-direction.md](docs/design-direction.md) — visual language
