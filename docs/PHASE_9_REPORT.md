# Phase 9 — End-to-End Testing, Security and UI Polish

Implemented on the existing Phase 1–8 architecture. No deployment, new marketplace,
model family, scheduled job or visual redesign was introduced. Git remains on
`master` at `c7d4b86` with existing Phase 7–8 changes preserved; no commit was made.
PROJECT_CONTEXT.md and Phase 6–8 reports were read before implementation.

## Pre-implementation status

- Baseline: 257 backend tests passed; production frontend build and oxlint passed.
- Auth, ingestion, dataset, training, prediction, history and analytics were already
  implemented. The audit focused on their integration and failure paths.
- Reproduced DEBUG=release startup failure, comma-separated CORS parsing failure,
  whitespace-only collection keyword acceptance, empty production-secret acceptance,
  missing required JWT claims, and input-echo risk in validation responses.
- Found unbounded uploaded-file reads, malformed CSV/metadata error paths, timezone
  normalization gaps, training artifact collision risk, migration logging reset,
  and bundled-demo lookup tied unnecessarily to the writable output directory.
- Frontend had no request timeout or centralized expired-session handling; multipart
  imports duplicated error handling. Mobile navigation lacked focus containment.
  Public copy advertised unavailable real-time collection.
- The browser tool returned `apps: [], browsers: []`. No browser interaction or
  desktop/tablet/mobile visual verification can be claimed.

## Files created

- `backend/tests/test_stabilization.py` — configuration, JWT, validation, errors,
  import, timezone, logging, collector consistency and persistence safeguards.
- `backend/tests/test_end_to_end.py` — fresh-install API journey in a subprocess.
- `frontend/tests/apiClient.test.mjs` — eight real request-wrapper failure tests
  using Node's built-in runner and the existing Vite module loader.
- `docs/PHASE_9_REPORT.md` — this report.

## Files modified in Phase 9

| Area | Files |
| --- | --- |
| Settings and application | `.env.example`, `backend/.env.example`, `backend/app/config.py`, `backend/app/main.py` |
| Authentication | `backend/app/auth/security.py`, `backend/app/auth/dependencies.py`, `backend/app/services/user_service.py`, `backend/app/schemas/auth.py`, `backend/app/api/routes/auth.py` |
| API validation and diagnostics | `backend/app/schemas/data.py`, `backend/app/schemas/dataset.py`, `backend/app/schemas/training.py`, `backend/app/api/routes/data.py`, `backend/app/api/routes/ml.py`, `backend/app/api/routes/analytics.py`, `backend/app/api/routes/prediction.py` |
| Data and training services | `backend/app/scrapers/registry.py`, `backend/app/scrapers/validation.py`, `backend/app/services/collection_service.py`, `backend/app/services/analytics_service.py`, `backend/app/services/dataset_service.py`, `backend/app/services/demo_service.py`, `backend/app/services/import_service.py`, `backend/app/services/training_service.py` |
| Migration logging | `backend/migrations/env.py` |
| Existing test contracts | `backend/tests/test_analytics.py`, `backend/tests/test_import_demo.py`, `backend/tests/test_training.py` |
| Frontend request/session handling | `frontend/src/services/apiClient.ts`, `frontend/src/services/dataService.ts`, `frontend/src/services/trainingService.ts`, `frontend/src/config/env.ts`, `frontend/src/auth/AuthProvider.tsx`, `frontend/src/auth/authContext.ts`, `frontend/src/components/ProtectedRoute.tsx` |
| UI and forms | `frontend/src/components/Panel.tsx`, `frontend/src/components/dashboard/DashboardLayout.tsx`, `frontend/src/components/dashboard/Sidebar.tsx`, `frontend/src/components/dashboard/ObservedLineChart.tsx`, `frontend/src/components/dashboard/TrainingResults.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/RegisterPage.tsx`, `frontend/src/pages/MarketplaceDataPage.tsx`, `frontend/src/pages/TrainModelPage.tsx`, `frontend/src/config/site.ts` |
| Test command and documentation | `frontend/package.json`, `README.md`, `CLAUDE.md` |

Other uncommitted files shown by Git belong to the earlier phases. Historical
phase reports, development data, active model and ML scoring formulas are preserved.
No package dependency was added.

## Bugs and security fixes

1. **Boolean-safe settings:** DEBUG defaults false. `release` explicitly maps to
   false and `debug` to true; ordinary boolean strings still work and unknown
   values fail. Non-development runtime rejects DEBUG=true.
2. **CORS:** Disable automatic JSON decoding for this setting so both documented
   CSV origins and JSON arrays reach validation. Accept exact HTTP(S) origins,
   reject wildcards/paths/embedded credentials, and remove duplicates.
3. **Secrets and JWTs:** Reject empty secrets; outside development reject the
   shipped default or secrets shorter than 32 bytes. Limit configured signing
   algorithms to supported HMAC variants and require a positive token lifetime.
   JWTs require sub/iat/exp; oversized or invalid numeric user IDs fail with 401.
4. **Passwords and registration:** Retain bcrypt, constant-cost nonexistent-user
   verification and case-normalized emails. Bound login inputs; remove raw input
   and context from validation responses so invalid passwords are not echoed.
   Roll back duplicate-registration races and return the existing 409 contract.
5. **Inputs:** Trim collection keywords before length validation. Validate known
   dataset platforms, bounded lists/categories, date ordering and normalized UTC
   bounds. Reject unknown/empty training selections and blank/oversized dataset IDs.
   Existing strict prediction selectors and analytics filters remain in place.
6. **Imports:** Read at most the 5 MB cap plus one byte into application memory.
   Handle CSV parser failures, excess CSV rows and excessive JSON nesting cleanly.
   Normalize offset timestamps to UTC before SQLite storage. Drop non-finite
   numeric signals instead of returning invalid JSON or plausible infinities.
7. **Dataset reliability:** Ignore schema-invalid metadata sidecars. Unreadable
   CSV files return unavailable through existing service contracts. Preview reads
   only its bounded row count, instead of reading the full file then slicing it.
8. **Training persistence:** A nonblocking process-local lock returns 409 for an
   overlapping run. Version selection also accounts for orphaned on-disk versions.
   Exclusive file creation refuses to overwrite historical artifacts. Training tests
   now isolate files as well as metadata, and assert that older artifact bytes are unchanged. Failures
   roll back the database and return a sanitized training error. ML feature,
   target, split, selection and Opportunity Score formulas are unchanged.
9. **Collector consistency:** A shared effective-status policy excludes the
   deprecated PA-API adapter from both Marketplace Data and analytics. Actual
   collection calls reject it before a network request. Existing adapter/parser
   code remains testable against mock transports; no unsupported scraping is added.
10. **Startup and diagnostics:** Embedded Alembic migrations no longer replace or
    disable application loggers. Auth/import/prediction/analytics rejection logs
    avoid passwords, tokens and submitted payloads. Unexpected failures return a
    generic 500 and log the exception class only; allowed browser origins can read
    the sanitized error response. The bundled demo remains accessible when DATA_DIR
    points at a separate writable output directory.

The source audit found no tracked private `.env` files and no high-confidence
private-key/AWS/GitHub-token signatures in tracked content. All 23 development
user password fields had bcrypt prefixes; hashes and account details were not
printed. Development placeholders and test-only credentials remain intentional.
This is a source/configuration audit, not a penetration test or a guarantee that
all historical secrets or dependency vulnerabilities have been ruled out.

## UX, responsiveness and accessibility fixes

- JSON and multipart requests now share readable offline/401/403/404/422/500 and
  unavailable-source errors. A malformed success body is rejected instead of
  becoming null page state. Timeout covers response headers and body reads.
- Timeouts: 30 seconds normally, 120 seconds for import, 300 seconds for training.
  No mutation is automatically retried. The message warns that server work may
  still complete and directs users to reload status before resubmitting.
- Rejected authenticated requests clear the matching session and return users to
  sign-in with an explanation. An old request cannot invalidate a newer token.
  Restoration failures remain visible; transient network errors preserve stored
  credentials. Logout propagates to other tabs. Return navigation preserves query
  parameters, including selected-product trend links.
- Registration validates maximum name/password sizes and UTF-8 password byte limits.
- Marketplace data requests ignore stale filter responses, show loading, clear old
  rows while fetching, and reject oversized uploads before sending. Missing fixture
  metadata displays unavailable values instead of hardcoded platform/category counts.
- Dataset/model status loads independently, so a missing dataset preview does not
  suppress model quality. Training is disabled while building/loading and explicit
  loading text appears. Existing errors, baseline metrics and DEMO notices remain.
- Training evaluation includes a visible experimental-use and no-sales-demand notice.
  Landing content now describes stored analytics and unavailable live refresh.
- Mobile navigation traps Tab focus, supports Escape, marks the background inert,
  locks background scrolling, restores focus and closes when returning to desktop.
  Navigation controls expose expanded/modal semantics. Home navigation closes the drawer.
- Panels can shrink and wrap long text. Charts preserve readable labels with a
  horizontal scroll region on narrow screens. Existing table scroll wrappers,
  labels, table headers, focus styling, theme tokens and reduced-motion support remain.

Desktop/tablet/mobile behavior was reviewed in code; no screenshot or keyboard
interaction testing was possible without an available browser. The eight frontend
checks exercise request behavior, not layout or React interaction.

## Full-flow validation and migration preservation

The new subprocess test starts against an empty database and empty output/model
directories with DEBUG=release. Normal startup applies migrations; the test does not
manually insert SQL rows. It then exercises:

1. Health, register, login and authenticated user lookup.
2. Empty dashboard summary and marketplace status.
3. Load 480 bundled DEMO snapshots and import one JSON row (attempted LIVE input
   provenance is correctly stored as IMPORTED).
4. Build a DEMO-only 480-row dataset and preview five rows.
5. Train a Random Forest in temporary artifact storage and read actual metrics.
6. Select Acme 20000mAh, predict with the saved Pipeline and read two scored platforms.
7. Read trend history, platform comparison and matching saved score/model context.
8. Read prediction history and dashboard count; verify another user's detail lookup
   returns 404 and requests without a token return 401.
9. Start the application again and verify the saved result JSON is identical and
   all 481 snapshots remain. This checks restart persistence and idempotent migration.

This validates the backend APIs behind the requested flow. Landing-page interaction,
form navigation, browser logout and responsive layouts were not end-to-end browser tested.

A separate read-only backup of the actual development database was migrated twice
from revision 0003 to head. All existing rows were preserved: 23 users, 480 snapshots,
4 model metadata records and 0 predictions. The original database was not migrated
for this check; normal backend startup will apply 0004. Model files and development
database hashes were checked against the inspection baseline.

## Test results

- Baseline backend: 257 passed.
- Focused new security/full-flow tests plus affected collector contracts: 40 passed.
- Frontend request tests: 8 passed (`npm.cmd test`).
- Frontend production TypeScript/Vite build: passed.
- Frontend oxlint: passed.
- Full final backend regression: **295 passed**, with 6 dependency deprecation warnings; no failures.
- `git diff --check`: passed.

## Remaining limitations and Phase 10 blockers

- No usable LIVE marketplace connector. Approved supported access and a replacement
  adapter are required; no credentials or browser plugin magically supply it.
- The active v4 XGBoost remains DEMO-trained, with accuracy 0.3333, weighted F1 0.3187
  and majority accuracy baseline 0.4062. Scores are experimental proxies, not reliable
  sales/margin recommendations. No development retraining occurred.
- Existing ML evaluation limitations remain, including small synthetic history and
  boundary-crossing forward labels in the original split. Historical metrics were
  not reinterpreted or silently changed; ML behavior was outside this stabilization fix.
- Database, processed datasets and trusted pickle artifacts remain local files.
  Deployment persistence, backups, filesystem permissions, correct public API URL,
  HTTPS, SPA rewrites and platform configuration still require Phase 10 work.
- The shared operator workspace permits authenticated users to ingest/build/train
  global data and models; only prediction history is user-scoped. Public self-service
  multi-tenant deployment needs an explicit authorization/rate-limit policy first.
- JWTs remain in localStorage and stateless logout does not revoke copied tokens.
  HttpOnly session design, server revocation and public-endpoint abuse controls were
  not introduced as new infrastructure in this phase.
- The training lock coordinates one process. Exclusive files prevent overwrites,
  but multiple worker processes still need a shared training/activation coordinator.
  Failed persistence can leave unreferenced artifacts; their versions are preserved.
- The 5 MB application read cap is not a reverse-proxy total-request limit. Configure
  upload/body limits at the deployment boundary as well.
- Imported timestamps are operator-supplied; legacy undated imports use ingestion
  time and cannot be treated as independently verified historical observations.
- Application data/model directory contents are trusted. No arbitrary artifact
  upload route exists; pickle files must never be accepted from untrusted parties.
- Browser visual/interaction QA and public deployment verification remain undone.

Phase 9 stops here. No Phase 10 deployment or infrastructure work was performed.
