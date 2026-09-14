# Phase 13 — Authorization and Abuse Controls

September 14, 2026. Implementation complete; automated verification recorded below.
Interactive browser verification is unavailable in this session. No deployment performed.

## Preserved state

No ML features, targets, training policy, scoring, connector semantics, provenance,
quality warnings, or integrations changed. Active development model remains v5,
DEMO-trained and `below_baseline`, flagged as predating the Phase 12 leakage fix.
Probabilities remain uncalibrated. 480 DEMO observations, 0 LIVE observations.
Flipkart still requires credentials and written data-use approval.
The development SQLite database remains at 0004; no startup, migration, administrator
bootstrap or persistent training was performed against it. Test models use disposable storage.

## Role matrix and endpoints

Permissions are centralized in `backend/app/auth/permissions.py`; mutation routes
use reusable permission/rate-limit dependencies. Public registration always creates
an active **viewer** and rejects extra fields such as role, permissions or token_version.
`/auth/me` and login/register responses expose role and permissions, never hashes or versions.

| Permission | Viewer | Analyst | Operator | Administrator | Endpoints |
|---|---|---|---|---|---|
| Shared reads, own history | yes | yes | yes | yes | Existing authenticated GET data, dataset, model, prediction-options/history and analytics routes |
| `dataset:build` | no | yes | yes | yes | POST /ml/dataset/build |
| `prediction:run` | no | yes | yes | yes | POST /ml/predict |
| `data:collect` | no | no | yes | yes | POST /data/collect |
| `data:import` | no | no | yes | yes | POST /data/import |
| `data:demo` | no | no | yes | yes | POST /data/demo/load |
| `model:train` | no | no | yes | yes | POST /ml/train |
| `users:manage` | no | no | no | yes | GET /admin/users; PATCH /admin/users/{id}/role; PATCH /admin/users/{id}/status; POST /admin/users/{id}/revoke-sessions |

All active accounts may POST `/auth/logout` or `/auth/revoke-sessions` for themselves.
API_PREFIX applies to all these routes. Admin lists are paginated (maximum 100).
Prediction history, details, counts and saved-score overlays remain owner-only,
including for administrators. Access to another user's prediction ID returns 404.
Shared observations, datasets and models remain a shared operator workspace.

Admin bodies are `{ "role": "analyst" }` and `{ "is_active": false }`, respectively.
Role/status changes revoke the target's existing tokens. The last active administrator
cannot be disabled or demoted (409). PostgreSQL advisory locking and SQLite writer
serialization protect this invariant; the actor's admin authority is rechecked after
locking. Admin account management is API-only; there is no new admin UI.

## Migration and first administrator

`0008_authorization.py`, after `0007`, adds only:
- `users.role`: non-null string, database and ORM default `viewer`.
- `users.token_version`: non-null integer, database and ORM default `0`.

Existing users, passwords, timestamps and active/disabled state are preserved.
Existing accounts receive viewer access; no automatic administrator or operator exists.
Normal startup applies pending migrations. This phase intentionally leaves the existing
development database unchanged, so it still needs 0005–0008 on a future authorized startup.

On the intended deployment database, after normal startup migration and registration
of the chosen account, the operator may explicitly run from `backend/`:

```sh
python -m app.bootstrap_admin --email existing@example.com
```

This promotes an existing active account only when there is no active administrator.
It does not run migrations, create users, or run automatically. It revokes prior tokens;
sign in again, then use admin APIs to grant operational roles. It is also the explicit
operator recovery path if out-of-band database changes leave no active administrator.
The command was tested only on disposable accounts; no real account was promoted.

## JWT/session behavior

JWTs still use the configured HMAC algorithm and expiry (HS256, 12 hours by default).
They now require an integer `token_version` matching the current user row, in addition
to sub/iat/exp and type=access. Pre-Phase 13 tokens without a version are rejected.
Every authenticated request checks the database account state and token version.

Atomic version increments invalidate **all** account tokens on logout/revoke-all,
explicit admin revocation, role changes, and account disable/reactivation. Password
change/reset is not implemented; future password-changing paths must increment the version.
Reactivation permits a fresh login and cannot resurrect old tokens.

Invalid/missing/expired/stale tokens return 401 with a Bearer challenge. Valid tokens
without an operation permission return 403 with "You do not have permission to perform
this action." Disabled login returns 403. Directly disabled accounts are rejected
backend-side even if an out-of-band writer did not increment the version.

The frontend calls `/auth/logout` before clearing the local token. Network failure
still signs out locally and explicitly says server revocation could not be confirmed.
401 handling and cross-tab logout use local clearing without another revocation call.
Ordinary 403 responses do not log users out. Tokens remain in localStorage; there are
no cookies, refresh tokens, OAuth, per-device session lists or idle-session expiry.

## Rate limits

| Category / setting suffix | Default | Key |
|---|---|---|
| LOGIN | 5/minute | Connection IP |
| REGISTER | 3/minute | Connection IP |
| PREDICT | 30/minute | User ID |
| COLLECT | 5/minute | User ID |
| BUILD | 5/minute | User ID |
| IMPORT | 5/minute | User ID |
| DEMO | 5/minute | User ID |
| TRAIN | 2/hour | User ID |

Settings are `RATE_LIMIT_<suffix>` in backend environment files. Defaults apply in
both development and production; developers can raise positive limits explicitly.
Tests reset the store and raise limits except dedicated rate-limit tests.
Rejected attempts count once admitted to a category; permission-denied operations
never enter a privileged service. Login/registration limits run before body parsing.
Responses are 429 with Retry-After, exposed through CORS.

The centralized `Store` protocol has a thread-safe, fixed-window `MemoryStore` implementation.
It caps state at 10,000 category/identity keys, purges expired entries and fails closed
for new keys at capacity instead of evicting active quotas. Restart resets quotas.
It supports **one process and one instance only**; use a shared atomic store such as
Redis before scaling. Fixed windows can allow a burst across a window boundary.

`app.start` disables Uvicorn proxy-header trust. Forwarded/X-Forwarded-For values cannot
spoof limiter identities. Behind a reverse proxy, login/registration quotas consequently
apply to the proxy connection IP and may be shared across visitors. Before public rollout,
configure trusted client-IP handling and/or per-client limits at the hosting edge with
known proxy boundaries; never trust arbitrary forwarded headers. Custom server commands
must preserve this trust policy. Application rate limits do not replace edge DDoS controls.
Existing Flipkart provider cooldowns and the training collision lock remain in force.

## Inbound request limits

The ASGI middleware buffers at most the configured total body before JSON/multipart
parsing, checks Content-Length early, and also counts actual streamed bytes (including
chunked or underreported requests). CORS applies to rejection responses.

- Ordinary requests: `REQUEST_MAX_BYTES=1048576` (1 MiB).
- Import request envelope: `IMPORT_REQUEST_MAX_BYTES=6291456` (6 MiB, including multipart overhead).
- CSV/JSON uploaded file: fixed 5 MiB; existing 5,000-row import validation remains.
- Oversized bodies/files return **413** with clear limit messaging. Invalid import content
  and row counts still return 422.
- `STORAGE_MAX_BYTES` remains an independent stored-object bound, not an HTTP upload limit.

No new server-wide connection/time limits or streaming ingest system were introduced.
Use ingress request timeouts/concurrency limits in deployment; many simultaneous bodies
can still consume memory even though each body is bounded.

## Frontend and logging

The UI uses server-provided permissions, not a duplicate role matrix. Unauthorized
mutation controls are disabled through native fieldsets with an adjacent explanation;
event handlers also check permissions. Dataset/model status and saved history remain
readable. Sidebar shows role and labels the training route "Datasets / Model Status"
for accounts without training permission. Existing provenance and model-quality UI remain.

Logs record failed login, permission denial, rate-limit triggers, role changes, account
state changes, bootstrap and session revocation. Audit messages use numeric user/actor
IDs and operation names, not passwords, JWTs, Flipkart tokens or request bodies.
Audit events are application logs, not a durable tamper-evident audit table; retain logs
appropriately on the deployment platform.

## Verification

| Check | Result |
|---|---|
| Full backend suite with disposable PostgreSQL 17 | **496 passed, 1 skipped**, 127 seconds; only opt-in LIVE Flipkart skipped |
| Dedicated PostgreSQL/storage run | **37 passed**, 0 skipped; later full run also includes the new account/concurrency test |
| New authorization/abuse tests | **53 passed** (included in full suite) |
| Final focused auth/authorization regression | **74 passed** after final middleware edge-case cleanup |
| Frontend TypeScript/Vite build | passed |
| Frontend lint | passed |
| Frontend tests | **15 passed**, including SSR role rendering, ordinary 403 handling and logout request |
| git diff --check | passed |
| Preservation | **161 files SHA-256 identical**: existing DB, datasets and v1–v5 artifacts; no new persistent dataset/model files |

PostgreSQL verification used a newly created `postgres:17-alpine` container bound to
127.0.0.1:55433, with unique test schemas. Existing application containers were not used.
Checks cover migration preservation/defaults/schema parity through 0008, concurrent
startup, database storage/restart, token-version updates, disabled login and stale-session
rejection, reactivation, logout and concurrent cross-demotions preserving one administrator.
Existing scientific-stack warnings concern empty DEMO trend features; framework warnings
are deprecations. No test contacts a real marketplace.

Commands (backend uses its existing virtualenv):

```sh
python -B -m pytest -p no:cacheprovider --basetemp=.pytest-phase13-final --junitxml=.pytest-phase13-final-results.xml
python -B -m pytest tests/test_postgresql.py tests/test_storage.py -q -p no:cacheprovider --basetemp=.pytest-phase13-pg
npm.cmd run build
npm.cmd run lint
npm.cmd test
git diff --check
```

The backend full run had TEST_POSTGRES_URL set only to the disposable database.
No existing environment file was modified; only .env.example files changed.

Browser tool inventory returned no available browsers. Creating Chrome and in-app
browser tabs both returned "Browser is not available". Viewer, analyst and operator
interactive journeys, forbidden-action browser behavior and browser logout could not
be run. Admin UI journey is not applicable (API-only). Server-rendered React permission
controls and API/request tests are automated substitutes, not browser verification.

## Remaining limitations

- No live deployment or hosted security verification; Phase 10 evidence remains local.
- Browser journeys remain unverified for this phase.
- In-memory limits require one worker/instance; trusted reverse-proxy IP handling and
  edge time/concurrency controls remain deployment work.
- localStorage is readable by origin scripts; XSS can steal a token until expiry or revocation.
- Revocation prevents subsequent authentication; already-admitted work is not cancelled.
- Public viewer registration still exposes the shared read workspace. Use controlled
  access/network policy if the stored observations are confidential; this is not tenant isolation.
- No MFA, email verification, password reset/change, per-device sessions, or durable audit store.
- Administrator recovery requires operator database/CLI access; no automatic privileged account.
- No new scheduled jobs or integrations. No Phase 14 work.

## Files changed

Created:

- `backend/app/api/routes/admin.py`
- `backend/app/auth/permissions.py`
- `backend/app/auth/rate_limits.py`
- `backend/app/auth/request_limits.py`
- `backend/app/bootstrap_admin.py`
- `backend/app/services/account_service.py`
- `backend/migrations/versions/0008_authorization.py`
- `backend/tests/accounts.py`
- `backend/tests/test_authorization.py`
- `docs/PHASE_13_REPORT.md`
- `frontend/src/auth/permissions.ts`
- `frontend/src/components/PermissionGate.tsx`
- `frontend/tests/permissions.test.mjs`

Modified:

- `.env.example`
- `.gitignore`
- `CLAUDE.md`
- `OVERALL_PROJECT_REPORT.md`
- `README.md`
- `backend/.env.example`
- `backend/app/api/router.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/data.py`
- `backend/app/api/routes/dataset.py`
- `backend/app/api/routes/ml.py`
- `backend/app/api/routes/prediction.py`
- `backend/app/auth/dependencies.py`
- `backend/app/auth/security.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/models/user.py`
- `backend/app/schemas/auth.py`
- `backend/app/start.py`
- `backend/tests/conftest.py`
- `backend/tests/test_data_api.py`
- `backend/tests/test_dataset_builder.py`
- `backend/tests/test_end_to_end.py`
- `backend/tests/test_import_demo.py`
- `backend/tests/test_live_collection.py`
- `backend/tests/test_postgresql.py`
- `backend/tests/test_prediction.py`
- `backend/tests/test_stabilization.py`
- `backend/tests/test_training.py`
- `frontend/package.json`
- `frontend/src/auth/AuthProvider.tsx`
- `frontend/src/auth/authContext.ts`
- `frontend/src/components/dashboard/MarketDataRefresh.tsx`
- `frontend/src/components/dashboard/Sidebar.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/MarketplaceDataPage.tsx`
- `frontend/src/pages/PredictorPage.tsx`
- `frontend/src/pages/TrainModelPage.tsx`
- `frontend/src/services/authService.ts`
- `frontend/src/types/auth.ts`
- `frontend/tests/apiClient.test.mjs`
