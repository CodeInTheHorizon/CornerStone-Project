# MarketPulse AI — Final Project Report

**Date:** September 15, 2026 · **Phase:** 15, final production audit · **Branch:** `master` (last commit `8ca1d4b`; Phases 13–15 uncommitted at the time of writing)

This report states what exists, what works, what is gated, and what is blocked. Evidence is
from this audit unless labelled otherwise. Historical phase reports in `docs/` remain the
detailed record.

---

## 1. Executive summary

MarketPulse AI is a full-stack marketplace-intelligence application for electronics sellers:
a public website, authenticated role-based dashboard, a provenance-aware marketplace data
layer, a deterministic dataset builder, leakage-safe model training with a quality gate,
saved-pipeline predictions with an explained 0–100 Cross-Platform Opportunity Score,
stored-history analytics, and production deployment configuration.

**What is true today:**

- The complete pipeline works end to end — register → load or import data → build dataset →
  train → predict → compare opportunity scores → view trends and history — and is verified by
  497 backend tests (including PostgreSQL) and browser tests in Chromium, Firefox and
  WebKit.
- **All stored marketplace data is synthetic DEMO data: 480 DEMO, 0 IMPORTED, 0 LIVE.**
- The only LIVE route, the official Flipkart Affiliate API connector, is **implemented but
  gated**: no credentials and no written data-use approval exist, and **no provider request
  has ever been made** (0 collection attempts).
- The active model (v5, XGBoost) is **DEMO-trained, below its majority baseline, uncalibrated,
  and not reliable**. No model is real-data trained. The target is a **price-direction
  opportunity proxy, not sales demand**.
- The system is **deployment-ready and production-verified locally, but not deployed**: no
  Render service, Vercel project, managed database or hosted URL exists.

The software objectives are met. The remaining gaps are external (marketplace access,
hosting accounts) or depend on data that does not yet exist (a real-data model).

## 2. Original objectives

From `PROJECT_CONTEXT.md`: help electronics sellers without their own datasets answer which
products and marketplaces offer opportunity, what prices and competition look like, and how
the market changes — by building a dataset from marketplace observations and applying ML,
trend analytics and an interpretable Cross-Platform Opportunity Score, inside a focused MVP
(electronics only; Amazon, Flipkart, Croma, Alibaba; no ERP, inventory, orders or logistics),
with a public website, authentication and an interactive dashboard. Production scraping must
respect marketplace terms, robots rules, rate limits and official APIs.

## 3. Objective completion table

Classification: **COMPLETE** · **IMPLEMENTED BUT GATED** (works, disabled by configuration or
approval) · **PARTIAL** · **EXTERNAL BLOCKER** (cannot be completed from code) · **OUT OF SCOPE**.

### Public website

| Objective | Status | Evidence / note |
|---|---|---|
| MarketPulse AI branding | COMPLETE | Logo, title, theme tokens, light/dark |
| Home / About / Features / Contact navigation | COMPLETE | Anchors `#home`, `#about`, `#features`, `#contact` all resolve; mobile menu keyboard-verified |
| Login / Register entry points | COMPLETE | Navbar and routes `/login`, `/register` |
| Project hero description | COMPLETE | States stored/DEMO data honestly |
| "Why Choose MarketPulse AI?" cards | COMPLETE | Three flip cards |
| Meet the Developer | PARTIAL | Name, role, intro, skills and email shown; GitHub, LinkedIn and portfolio URLs are empty (hidden) until the owner supplies them |
| Features section | COMPLETE | Six feature cards including Cross-Platform Opportunity Score |
| Get in Touch / WhatsApp flow | IMPLEMENTED BUT GATED | Validation and WhatsApp hand-off work; submit stays disabled with an explanation until `VITE_WHATSAPP_NUMBER` is set (not set) |

### Authentication

| Objective | Status | Evidence / note |
|---|---|---|
| Registration | COMPLETE | Always creates an active **viewer**; rejects supplied role/version fields |
| Login | COMPLETE | bcrypt verification, JWT issued |
| Logout | COMPLETE | Revokes all account sessions server-side (token version) |
| Protected routes | COMPLETE | Deep links return to the requested page after login (fixed Phase 14) |
| Role-based access | COMPLETE | viewer / analyst / operator / administrator; UI fails closed; backend authoritative |
| Disabled users and session behaviour | COMPLETE | Disable, role change and admin revocation invalidate tokens; browser-verified |
| Admin user interface | OUT OF SCOPE | Administration is API-only by design (Phase 13) |

### Marketplace data

| Objective | Status | Evidence / note |
|---|---|---|
| Amazon abstraction | COMPLETE (LIVE access: EXTERNAL BLOCKER) | Collector and status exist; PA-API 5 retired 15 May 2026; Creators API terms forbid this use without approval → `unavailable` |
| Flipkart abstraction | IMPLEMENTED BUT GATED | Official Affiliate API collector with retries, `Retry-After`, redaction; state `credentials_missing` |
| Croma abstraction | COMPLETE (LIVE access: EXTERNAL BLOCKER) | No public API → `unavailable` |
| Alibaba abstraction | COMPLETE (LIVE access: EXTERNAL BLOCKER) | Open API is seller-only → `unavailable` |
| LIVE / IMPORTED / DEMO provenance | COMPLETE | Every row carries `source_type`; badges everywhere; LIVE rows link to `collection_attempts` |
| CSV/JSON import | COMPLETE | 5 MiB / 5,000-row limits, aliases, row-level validation |
| Demo data | COMPLETE | Synthetic fixture, always badged DEMO |
| Collector status | COMPLETE | Seven explicit states with reasons and required configuration |
| LIVE connector readiness | IMPLEMENTED BUT GATED | Needs credentials **and** `FLIPKART_DATA_USE_APPROVED=true` backed by written approval |
| On-demand fresh-data refresh | IMPLEMENTED BUT GATED | Refresh Market Data works only with an available LIVE collector |
| Scheduled refresh jobs | OUT OF SCOPE | Not implemented; LIVE access is gated, and a scheduler would add nothing today |

### Dataset

| Objective | Status | Evidence / note |
|---|---|---|
| Cleaning | COMPLETE | Drops only unusable rows; repairs and drops counted by reason |
| Normalization | COMPLETE | Canonical product/category identity; strict matching avoids false merges |
| Feature engineering | COMPLETE | 31 features (basic, time-based, marketplace, trend) |
| Historical features | COMPLETE | Expanding windows over each listing's own past; missing stays NULL/NaN, never 0 |
| Processed dataset | COMPLETE | CSV locally; checksummed immutable bundle in PostgreSQL in production |
| Metadata | COMPLETE | Source types, platforms, counts, cleaning report, feature list |

### Machine learning

| Objective | Status | Evidence / note |
|---|---|---|
| Random Forest | COMPLETE | |
| XGBoost | COMPLETE | Active v5 is XGBoost |
| Time-aware, boundary-first validation | COMPLETE | Date boundary chosen first; each side labelled separately (Phase 12) |
| Leakage safeguards | COMPLETE | Fixed a confirmed leak (96/288 DEMO training labels crossed the boundary); near-perfect scores flagged |
| Provenance policy | COMPLETE | Explicit `source_types`; DEMO never mixed with IMPORTED/LIVE (development override only) |
| Quality gate | COMPLETE | `below_baseline` / `experimental` / `candidate` / `validated`; DEMO capped at experimental |
| Baseline comparison | COMPLETE | Majority, training-majority and previous-direction accuracies |
| Model persistence | COMPLETE | Saved preprocessing + model Pipelines; never overwritten |
| Versioning | COMPLETE | v1–v5 locally, each with metadata |
| Metrics | COMPLETE | Accuracy, weighted/macro F1, precision, recall, confusion matrix, log loss, Brier, ECE |
| Minimum-data requirements | COMPLETE | `ML_MIN_*` return `insufficient_data` before fitting |
| A reliable, real-data-trained model | EXTERNAL BLOCKER | Requires permitted LIVE or IMPORTED history; none exists |
| Price-band regression model | OUT OF SCOPE | Optional in the brief ("if needed"); not implemented |

### Prediction

| Objective | Status | Evidence / note |
|---|---|---|
| Product selection | COMPLETE | Search and selection from stored products |
| Saved-pipeline inference | COMPLETE | Loads the persisted Pipeline; rejects incompatible metadata |
| Cross-platform comparison | COMPLETE | Per-marketplace results with comparison bars |
| Opportunity Score (0–100) | COMPLETE | Fixed budgets: model 10, price 20, rating 15, reviews 15, discount 10, competition 15, trend 15 |
| Explanation | COMPLETE | Per-signal contributions; missing signals get 0 points and are listed |
| Model quality context | COMPLETE | Quality status, baselines, DEMO/uncalibrated warnings saved with each prediction; top score labelled "experimental" unless candidate/validated |
| Prediction history | COMPLETE | Owner-only history and immutable result snapshots |

### Analytics

| Objective | Status | Evidence / note |
|---|---|---|
| Price trend | COMPLETE | Charts plus accessible value tables |
| Discount trend | COMPLETE | Including derived discounts, labelled |
| Rating / review trend | COMPLETE | Review momentum per day with caveats |
| Availability | COMPLETE | Latest state and observed change events |
| Platform comparison | COMPLETE | Exact-product and category-aggregate groupings; currencies never mixed |
| Dashboard summaries | COMPLETE | Stored counts, provenance, latest observation, active model, collector availability |
| Listing-growth and brand-movement trends | PARTIAL | Listing density and category aggregates exist; no time series of listing growth or brand movement |

### Security

| Objective | Status | Evidence / note |
|---|---|---|
| JWT | COMPLETE | HS256, 12 h expiry, required claims, integer token version |
| Password hashing | COMPLETE | bcrypt; passwords never echoed |
| RBAC | COMPLETE | Central matrix `backend/app/auth/permissions.py` |
| Permission enforcement | COMPLETE | Route dependencies return 403; UI mirrors and fails closed; browser-verified for all four roles |
| Rate limiting | COMPLETE (single instance) | Per-category limits; in-memory store is one-process only |
| Request-size controls | COMPLETE | Pre-parser body limits: 1 MiB, 6 MiB import envelope, 5 MiB file → 413 |
| Account disable | COMPLETE | Rejected at login and on every request |
| Session invalidation / revocation | COMPLETE | Token version increments on logout, role/status change and admin revocation |

### Deployment

| Objective | Status | Evidence / note |
|---|---|---|
| Render configuration | COMPLETE | `render.yaml`, one instance, `/ready` health check; Linux build and start verified locally |
| Vercel configuration | COMPLETE | `frontend/vercel.json` with SPA rewrite |
| PostgreSQL | COMPLETE (locally) | Required outside development; verified on PostgreSQL 17 |
| Durable storage | COMPLETE | `stored_objects`: immutable, checksummed dataset and model bundles |
| Migrations | COMPLETE | Alembic `0001`–`0008`, run on startup; failure stops startup |
| Startup migration locking | COMPLETE | PostgreSQL advisory lock; four concurrent startups verified |
| CORS | COMPLETE | Exact origins; browser-verified including preflight and foreign origins |
| API URL guard | COMPLETE | Vercel build fails without an HTTPS `VITE_API_BASE_URL`; no localhost fallback in production bundles |
| Backups | PARTIAL | Plan documented and a PostgreSQL dump/restore rehearsed locally; no hosted automated backups |
| Production-style local verification | COMPLETE | Production-mode backend + production bundle + PostgreSQL |
| Actual hosted deployment | EXTERNAL BLOCKER | No Git remote, Render/Vercel accounts, domain or managed database in this workspace |

### Browser and accessibility

| Objective | Status | Evidence / note |
|---|---|---|
| Chromium | COMPLETE | Playwright Chromium |
| Firefox | COMPLETE | Playwright Firefox |
| WebKit | COMPLETE | Playwright WebKit, Windows build (not Safari) |
| Responsive layouts | COMPLETE | 1440×900, 1280×800, 768×1024, 1024×768, 390×844, 360×800; no horizontal overflow |
| Light and dark themes | COMPLETE | All viewports, both themes |
| Accessibility audits | COMPLETE | axe WCAG 2.0/2.1 A/AA + best practice, nine routes, 1440 and 360 px, both themes, three engines: 0 violations |
| Keyboard verification | COMPLETE (WebKit links excepted) | Tab order, visible focus, toggles, drawer focus containment and Escape |
| Real macOS / iOS Safari | EXTERNAL BLOCKER | No Apple hardware available |
| Manual screen-reader testing | OUT OF SCOPE | Not performed; automated audits only |

## 4. Architecture

| Layer | Implementation |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, React Router; semantic theme tokens; `AuthProvider` + `PermissionGate` |
| Backend | FastAPI, Pydantic settings, SQLAlchemy; routers for auth, admin, data, dataset, ml, prediction, analytics, health |
| Data collection | `app/scrapers/`: collector contract, states, registry, one module per platform |
| Services | ingest, collection, import, demo, dataset, training, prediction, analytics, user, account |
| ML | `app/ml/`: normalization, features, dataset_builder, target, validation, provenance, training, opportunity |
| Storage | `app/storage/`: local files in development; immutable checksummed PostgreSQL bundles in production |
| Database | SQLite (development), PostgreSQL via psycopg (production); Alembic migrations `0001`–`0008` |
| Security | bcrypt, versioned JWT, central permissions, rate and request limits |
| Deployment | Render web service (one instance, `python -m app.start`); Vercel static SPA |

Main tables: `users`, `marketplace_snapshots`, `collection_attempts`, `model_metadata`,
`predictions`, `stored_objects`.

## 5. Data pipeline

**Sources → ingest → snapshots.** Every path (LIVE fetch, CSV/JSON import, DEMO fixture) runs
through one shared ingest: normalization, validation, deduplication and provenance tagging.
LIVE history is append-only; only a LIVE observation identical to one stored for the same
listing within 10 minutes is skipped. Every outbound LIVE fetch — including failures and
rate-limit cooldowns — is logged in `collection_attempts`.

**Current data (development database, read-only audit):**

| Item | Value |
|---|---|
| LIVE records | **0** |
| IMPORTED records | **0** |
| DEMO records | **480** (120 each for Amazon, Flipkart, Croma, Alibaba; synthetic) |
| Collection attempts (provider requests) | **0** |
| Flipkart connector state | `credentials_missing` |
| Flipkart credentials | not configured (`FLIPKART_AFFILIATE_ID` and token unset) |
| Flipkart written data-use approval | not held (`FLIPKART_DATA_USE_APPROVED=false`) |
| Successful provider request ever made | **No** |
| Amazon / Croma / Alibaba | `unavailable` (policy / no public API / seller-only API) |

The gated Flipkart connector is **not "LIVE in production"**. It has only been exercised against
mocked provider responses.

**Dataset builder.** Filter → clean → normalize → deduplicate → sort → engineer 31 features,
deterministically. Missing inputs yield missing features; trend features look only backwards.
Outputs are a CSV plus metadata locally, or immutable bundles in PostgreSQL.

## 6. ML pipeline

- **Target:** `marketplace_opportunity_class` — the direction of a listing's **next observed
  price** (improving > +1%, stable within ±1%, declining < −1%). It is a **price-direction
  opportunity proxy, not sales demand**.
- **Split:** a date boundary is fixed first; each side is labelled separately, so no training
  label uses a validation-period price.
- **Provenance:** training names its `source_types`; the dataset may contain only those; DEMO
  is never mixed with IMPORTED/LIVE outside a development-only override.
- **Minimums:** 100 labelled, 60 training, 20 validation rows, 10 products, 4 dates, 5 per class.
- **Models:** Random Forest and XGBoost in saved preprocessing Pipelines; versioned artifacts.
- **Evaluation:** metrics always beside majority, training-majority and previous-direction
  accuracies; probability quality measured (log loss, Brier, ECE) and never recalibrated.
- **Quality gate:** `validated` requires real data, ≥200 validation rows on ≥2 dates, a Wilson
  lower bound above every baseline and log loss better than the class prior. DEMO,
  development-override and pre-Phase 12 models are capped at `experimental`.

### Model status (development database, read-only audit)

| Item | Value |
|---|---|
| Active model | **v5** |
| Model type | XGBoost |
| Provenance | **DEMO** (dataset `4675ea7921af`, 480 synthetic rows) |
| Validation accuracy | **33.33%** |
| Weighted F1 | **31.87%** |
| Majority baseline accuracy | **40.62%** |
| Quality status | **`below_baseline`** (legacy record interpreted on read; trained before the Phase 12 leakage fix, so even this score is overstated) |
| Calibration status | **`uncalibrated`** |
| Reliable? | **No** — it does not beat always guessing the most common class |
| Real-data trained? | **No** — no model is real-data trained; 0 LIVE and 0 IMPORTED observations |

v1–v4 are inactive XGBoost records with the same DEMO metrics. The DEMO fixture drifts prices
randomly, so next-price direction is close to unpredictable by construction; the below-baseline
result is expected and demonstrates the pipeline, not market behaviour.

## 7. Prediction pipeline

Select a stored product → load the active saved Pipeline → score each marketplace's latest
observations → compute the explained 0–100 Opportunity Score (model signal is capped at 10
points; missing signals receive nothing and are listed, weights are not redistributed) → save
an immutable snapshot of the result, the model version, its quality status, baselines and
warnings → show per-marketplace comparison bars and the owner's history. The top result is
labelled "Highest experimental opportunity score" unless the model is `candidate` or
`validated`. Neither class probabilities nor the score are marketplace advice.

## 8. Analytics

Snapshot-only analytics (no model inference, no training): price, discount, rating, review and
availability histories per listing, with first/latest/change/min/max/average and valid-reading
counts; platform comparisons by exact product or explicit category aggregate, never mixing
currencies or sources; saved opportunity scores overlaid with their original quality context;
dashboard summaries from stored records. Charts are SVG with text alternatives and value
tables, and show a clear empty state. Reloading analytics never contacts a marketplace.

## 9. Security

### Roles and permissions

| Permission | Viewer | Analyst | Operator | Administrator | Endpoint |
|---|---|---|---|---|---|
| Shared reads, own prediction history | ✓ | ✓ | ✓ | ✓ | authenticated GET routes |
| `dataset:build` | — | ✓ | ✓ | ✓ | POST `/ml/dataset/build` |
| `prediction:run` | — | ✓ | ✓ | ✓ | POST `/ml/predict` |
| `data:collect` | — | — | ✓ | ✓ | POST `/data/collect` |
| `data:import` | — | — | ✓ | ✓ | POST `/data/import` |
| `data:demo` | — | — | ✓ | ✓ | POST `/data/demo/load` |
| `model:train` | — | — | ✓ | ✓ | POST `/ml/train` |
| `users:manage` | — | — | — | ✓ | `/admin/users` list, role, status, revoke-sessions |

Prediction history is owner-only for every role. The last active administrator cannot be
demoted or disabled. The first administrator is promoted by an explicit command
(`python -m app.bootstrap_admin --email …`), never automatically.

### Limits

| Rate limit (default) | Value |
|---|---|
| Login / registration (per IP) | 5 / 3 per minute |
| Prediction / collection / dataset build / import / DEMO load (per user) | 30 / 5 / 5 / 5 / 5 per minute |
| Training (per user) | 2 per hour |

Request limits: 1 MiB ordinary bodies; 6 MiB import envelope; 5 MiB and 5,000 rows per file;
enforced before parsing, including chunked bodies → 413. Throttling → 429 with `Retry-After`.

### Token and session strategy

Stateless HS256 JWTs (12-hour expiry) carrying an integer token version checked against the
database on every request, together with account active state. Logout, role or status change and
administrator revocation increment the version, invalidating all of that account's tokens.
Pre-Phase 13 tokens are rejected. 401 (invalid session) is kept distinct from 403 (permission):
ordinary 403 responses never sign the user out.

### Remaining security limitations

- Tokens live in `localStorage` (XSS-readable); no httpOnly refresh cookie.
- Rate limits are in-memory: one worker and one instance only; restart resets them.
- Forwarded IP headers are not trusted, so behind a proxy login limits may be shared.
- No MFA, email verification, password reset/change, per-device sessions or durable audit store.
- Public registration exposes the shared read workspace to viewers (not tenant isolation).
- Revocation blocks later requests; work already admitted is not cancelled.

## 10. Deployment readiness

### A. Deployment-ready (verified locally)

- `render.yaml` (one instance, `/ready`), `python -m app.start` (one worker, migrations with an
  advisory lock, failure stops startup); Render's build and start commands verified in a Linux
  Python 3.14.7 container.
- `frontend/vercel.json` (SPA rewrite); Vercel builds fail without an HTTPS
  `VITE_API_BASE_URL`; production bundles contain no localhost API fallback.
- Production settings validation: PostgreSQL `DATABASE_URL`, database storage, strong secrets.
- PostgreSQL 17: migrations, storage adapter contract, restart persistence, checksum rejection.
- Backup plan with a local dump/restore rehearsal (counts and checksums identical).
- Phase 14 browser verification against a production-mode backend and production bundle.

### B. Actually deployed

| Item | Exists? |
|---|---|
| Render service / URL | **No** |
| Vercel project / URL | **No** |
| Managed PostgreSQL | **No** |
| Hosted automated backups | **No** |
| Live hosted smoke test | **No** |
| Git remote | **No** |

**MarketPulse AI is deployment-ready, not deployed.** All production evidence is from local
production-style environments.

### Database and migration status

| Item | Value |
|---|---|
| Migration head | `0008_authorization` |
| Development database revision | `0008` (upgraded September 14, 2026 at the owner's request; `0004` backup in `data/backups/`) |
| Migrations pending locally | none |
| PostgreSQL verification | backend PostgreSQL tests pass on PostgreSQL 17 (this audit) |
| Durable storage (production) | datasets and models as immutable, checksummed `stored_objects` rows |
| Development storage | local files: `data/processed/` datasets, `backend/app/ml/artifacts/model_v1`–`v5` |
| Stored artifact behaviour | never overwritten (`StorageConflict`); checksum mismatch → 503 `corrupt_artifact`; a missing object is reported, never fabricated |
| Development `stored_objects` rows | 0 (development uses local files) |

## 11. Browser and accessibility verification

Playwright 1.63 against an isolated production-mode backend (disposable PostgreSQL 17 schema)
and the production bundle:

| Suite | Chromium | Firefox | WebKit | Total |
|---|---|---|---|---|
| Smoke (health, ready, SPA, login, dashboard, logout) | passed | passed | passed | **3/3** |
| Journeys (RBAC ×4 roles, sessions, deep links, offline API, keyboard, CORS, bundle/traffic, charts, validation) | 13/13 | 13/13 | 13/13 | **39/39** |
| Verification (6 viewports × light/dark × 9 routes with axe; role journeys incl. isolated training; error handling; sessions) | 18/18 | 18/18 | 18/18 | **54/54** |

Accessibility work found and fixed in Phase 14: suppressed focus rings, keyboard-unreachable
scrollable tables, an empty table header, a skipped heading level, garbled UI text, plus a
protected deep-link login redirect race and a crash on role-less account data. Not verified:
real Safari (macOS/iOS), WebKit keyboard focus on links (the engine skips links on Tab),
manual screen readers, real devices. Details: `docs/PHASE_14_REPORT.md`.

### Phase 15 audit corrections

The audit found public copy that contradicted the real state (all stored data synthetic DEMO,
LIVE gated) and corrected the wording only, with no layout or feature change:

| Location | Before | After |
|---|---|---|
| `frontend/index.html` meta description | "turns fresh e-commerce marketplace data into … predictions" | "turns stored, provenance-labelled marketplace observations into trend insights and experimental … opportunity scores" |
| `frontend/src/components/Footer.tsx` | "Built on fresh marketplace observations, not borrowed datasets." | "Every stored observation is labelled LIVE, IMPORTED or DEMO." |
| `frontend/src/sections/WhyChoose.tsx` | "collect real marketplace observations" | "gather marketplace observations with their provenance" |
| `frontend/src/config/site.ts` developer intro | "collecting real marketplace data … MarketPulse AI is that full loop" | "collecting marketplace data through permitted sources … demonstrates that full loop …, currently on synthetic DEMO data" |
| `README.md` tagline and limitation | "demand forecasting"; "opportunity / demand proxy" | "price-direction opportunity proxy, not sales demand" |

No ML behaviour, connector semantics, security control or data changed in Phase 15.

## 12. Test results

All results below were produced during this Phase 15 audit on September 15, 2026, after the
final code change (public copy corrections), unless labelled otherwise.

| Area | Check | Result |
|---|---|---|
| Backend | Full pytest suite (`TEST_POSTGRES_URL` → disposable PostgreSQL 17) | **497 tests: 496 passed, 1 skipped, 0 failed, 0 errors** (160.9 s) |
| Backend | Skipped test | opt-in real Flipkart API test (needs credentials, approval and `RUN_FLIPKART_LIVE_TEST=1`) |
| Backend | PostgreSQL tests | **16 passed**: 11 against the live PostgreSQL 17 server (migration chain, upgrade persistence and schema parity, concurrent startup, production journey with restart, account concurrency, 6 storage-adapter contract tests) + 5 URL-validation tests |
| Frontend | `npm test` (Node test runner) | **38/38 passed** |
| Frontend | `npm run build` (`tsc -b && vite build`) | passed |
| Frontend | `npm run lint` (oxlint) | passed, no warnings |
| Browser | Smoke — Chromium / Firefox / WebKit | **passed / passed / passed** (3/3) |
| Browser | `journeys.spec.ts` | **39/39** (13 per engine) |
| Browser | `verification.spec.ts` | **54/54** (18 per engine) |
| Repository | `git diff --check` | clean (run after the documentation was written) |
| Preservation | v1–v5 artifacts and processed datasets | 163 files byte-identical before and after all test runs |

Previously verified (not rerun in Phase 15, no related code changed since): Linux Render build
and start in a Python 3.14.7 container, PostgreSQL dump/restore rehearsal (Phase 10); Vercel
HTTPS URL build guard (rechecked in Phase 14).

## 13. Known limitations

- 0 LIVE and 0 IMPORTED observations; all analytics and models run on synthetic DEMO data.
- Active model v5 is below baseline and uncalibrated; predictions and scores are experimental.
- The target is a price-direction proxy, not sales demand; Flipkart provides no ratings/reviews.
- A LIVE refresh returns at most 10 listings; there is no scheduler; trends need repeated
  collection over real calendar time.
- Training is synchronous and in-process; one worker/instance only (training lock, rate limits).
- No admin UI; administration is API-only.
- Not deployed; hosted TLS, CDN rewrite and edge behaviour unverified.
- Browser coverage excludes real Safari, real devices and manual screen readers.
- Developer social links and the WhatsApp number are unset.

## 14. External blockers

Ranked:

1. **Critical external — marketplace access.** Flipkart affiliate credentials **and** written
   approval for storing history, analytics and ML use; or a licensed data provider whose terms
   permit this use. Amazon, Croma and Alibaba have no permitted route for this application.
2. **Critical before public production — hosting.** A Git remote, Render and Vercel accounts,
   real HTTPS domains (`VITE_API_BASE_URL`, `CORS_ORIGINS`).
3. **Critical before public production — managed PostgreSQL with automated backups/PITR**, and a
   hosted restore drill.
4. **Critical before public production — hosted smoke verification** using the checklist in
   `docs/DEPLOYMENT.md`, including Phase 13 controls and trusted edge/proxy rate limiting.
5. **Model — genuine historical data** meeting every minimum, then a model reaching at least
   `candidate` (ideally `validated`) before any reliability claim.
6. **Browser — real Safari/iOS and assistive-technology testing**, if required for the audience.

## 15. Future work

- After approval: repeated LIVE collection over weeks, a respectful scheduler, and retraining
  on LIVE/IMPORTED data through the existing provenance policy and quality gate.
- Probability calibration once real validation data supports it.
- Shared rate-limit store (e.g. Redis) and cross-process training coordination before scaling.
- httpOnly refresh-token cookies, password reset/change, MFA and a durable audit log.
- Optional admin UI over the existing admin APIs.
- Listing-growth and brand-movement trend series; code-splitting the single frontend bundle.
- Hosted monitoring, backups and restore drills after deployment.

## 16. Final conclusion

MarketPulse AI delivers its software objectives: a complete, tested, role-secured
marketplace-intelligence pipeline from provenance-labelled data to explained opportunity scores
and analytics, with deployment configuration verified in production-style local environments and
cross-browser, responsive and accessibility verification.

It is **not** a live-data product and **not** a reliable predictor today. Its data is synthetic
DEMO data, its only LIVE connector is gated behind external credentials and approval, its active
model is below baseline, and it has not been deployed. Those limits are stated in the UI, the
API and the documentation rather than hidden, and the system is built so that real data, once
permitted, flows through the same provenance, validation and quality gates before any claim of
reliability can be made.

For evaluation and portfolio use it demonstrates end-to-end engineering, ML methodology that
detects its own leakage and weakness, security design, and honest reporting. For a future
developer the next steps are external: marketplace approval, hosting and real data.
