# Phase 14 — Cross-Browser, Accessibility and Production-Style E2E Verification

September 14–15, 2026. Verification complete in a **local production-style environment**.
No hosted Vercel or Render URL exists, so nothing here is hosted verification.

## Headline

| Check | Result |
|---|---|
| Smoke test, per engine | Chromium **passed**, Firefox **passed**, WebKit **passed** |
| `e2e/journeys.spec.ts` (13 tests × 3 engines) | **39/39 passed** (3.5 min) |
| `e2e/verification.spec.ts` (18 tests × 3 engines) | **54/54 passed** (17.5 min) |
| Backend pytest, with disposable PostgreSQL 17 | **497 tests: 496 passed, 1 skipped, 0 failed** (236.7 s) |
| Frontend `npm run build` / `npm run lint` | passed / passed (no warnings) |
| Frontend `npm test` | **38/38 passed** |
| E2E TypeScript type-check | passed |
| `git diff --check` | clean |
| Development artifacts v1–v5 and processed datasets | unchanged during Phase 14 (see Preservation) |

The only skipped backend test is the opt-in real Flipkart API test (needs credentials,
Flipkart's written approval and `RUN_FLIPKART_LIVE_TEST=1`). All PostgreSQL tests ran.

No ML logic, connector semantics, RBAC rules, backend code or visual identity changed.

## 1. Browser matrix

| Engine | Build | Usable | What it stands in for |
|---|---|---|---|
| Chromium | Playwright Chromium 1243 (Playwright 1.63) | yes | Chrome / Edge |
| Firefox | Playwright Firefox 1543 | yes | Firefox |
| WebKit | Playwright WebKit 2359, **Windows build** | yes | Safari-equivalent engine only, **not real Safari** |

Google Chrome and Microsoft Edge are installed but were not driven separately. There is
no macOS or iOS device, so real Safari (desktop or iOS) was **not tested**.

## 2. Smoke results

`e2e/smoke.spec.ts`, run per engine before any large spec, after confirming from Node
that backend `/health` and `/ready` and the SPA root returned 200:

| Engine | Result | Checks |
|---|---|---|
| Chromium | passed (3.1 s) | `/health` 200, `/ready` 200, SPA 200, login, dashboard loaded, logout 204, back on `/login`, no page errors, no failed requests |
| Firefox | passed (18.6 s) | same |
| WebKit | passed (6.4 s) | same |

## 3. Journey results — 39/39

`e2e/journeys.spec.ts`, 13 tests in each engine:

| Area | Test |
|---|---|
| RBAC | **Viewer**: sees own (empty) prediction history; Make Prediction, Import, Load demo and Refresh Market Data disabled with the denial message and role; direct API calls to import, demo, collect, dataset build, train, predict and `/admin/users` return **403**; reload keeps the session; no console errors or failed requests |
| RBAC | **Analyst**: Build Dataset enabled; Train Model, Import, Load demo and LIVE refresh disabled; Make Prediction disabled until a product is chosen, then enabled; import/collect/train/admin return 403; session survives |
| RBAC | **Administrator**: all operational controls enabled, sidebar shows "Train Model" and role; `/admin/users` 200 without password hashes or token versions; admin role change viewer → analyst takes effect in a second browser session; a further change revokes that session (redirect to login with a session message) and the new role applies after sign-in |
| Sessions | Protected deep link → login → **returns to the requested page**; reload on all six dashboard routes stays on the route; unknown route → `/`; `/login` while signed in → dashboard |
| Sessions | Disabled account is signed out with a session message and cannot sign back in |
| Sessions | A 401 during use returns to login with a session message; a 503 on the session check keeps the token and shows the server message, and the app recovers |
| Network | Backend offline: login and the analytics page show "Could not reach the API", never a blank screen |
| Keyboard | Landing, login and Train Model operated by keyboard, every Tab stop shows a ≥2 px focus outline; Space/Enter toggle source-type buttons (`aria-pressed`); sidebar link activated by Enter; select focus ring visible |
| Keyboard | Mobile drawer at 360×800 stays inside the viewport, Escape closes it and returns focus to the opener, no trap afterwards |
| Cleanliness | Production bundle contains no `127.0.0.1:8000`/`localhost:8000` API fallback and no signing key; only the SPA and API origins are contacted; no repeated API requests during a 3 s idle window on any of six pages; API JSON never contains `hashed_password`, `token_version`, the password or the signing key |
| CORS | Configured origin allowed on 401 responses and preflight; a foreign origin gets no `Access-Control-Allow-Origin` on requests or preflight |
| Charts | Trends empty state states what to select; charts expose an accessible name; the "Observation values (accessible table)" disclosure has column headers and rows |
| Validation | Duplicate registration error visible, specific, no internals, still visible after 4 s; Import disabled without a file; an invalid JSON file shows a persistent error; a training conflict (409) and a prediction validation error (422 field message) are shown and no result is rendered |

## 4. Verification results — 54/54

`e2e/verification.spec.ts`, 18 tests in each engine:

- **Matrix** (12 per engine): every viewport in light and dark over nine routes (`/`,
  `/register`, `/login`, `/dashboard`, Marketplace Data, Train Model, Predictor, Trends,
  Analytics): route content settles, **no horizontal overflow**, no console/page errors,
  no unexpected 4xx/5xx, axe audit (see section 6), and below 1024 px the navigation
  drawer opens by keyboard, keeps focus inside for 12 Tabs, closes on Escape and returns
  focus to its opener.
- **Viewer, analyst and operator journeys**: viewer denied everywhere (UI disabled, API
  403); analyst builds a DEMO dataset, runs a prediction, opens a saved result, is denied
  training; operator loads DEMO data, imports a JSON file, receives the gated collector's
  501 (no LIVE request is made), builds, **trains XGBoost in the isolated environment**,
  predicts; all visit Trends and Analytics; logout revokes the token (old token → 401) and
  a protected deep link then redirects to login.
- **Error handling**: 403 keeps the analyst signed in; deliberate 403, 404, 413, 422, 429,
  500, 502 and 503 responses with long messages are shown as alerts that wrap without
  overflow; connection refused, a slow response and a request timeout are reported.
- **Registration and keyboard**: required-field, invalid-email and mismatched-password
  errors; 2 px focus outline on inputs; mobile menu opens with Space and closes with Escape
  returning focus; theme toggle by keyboard.
- **Sessions**: active role change, account disable, administrator session revocation and an
  expired token each redirect to login with a session message.

## 5. Responsive coverage

| Viewport | Class | Light | Dark | axe audit |
|---|---|---|---|---|
| 1440 × 900 | Desktop | ✓ | ✓ | ✓ |
| 1280 × 800 | Laptop | ✓ | ✓ | — |
| 768 × 1024 | Tablet portrait | ✓ | ✓ | — |
| 1024 × 768 | Tablet landscape | ✓ | ✓ | — |
| 390 × 844 | Mobile | ✓ | ✓ | — |
| 360 × 800 | Small mobile | ✓ | ✓ | ✓ |

All six viewports × two themes × nine routes × three engines. Wide tables scroll inside
their own keyboard-focusable regions; charts scroll horizontally in a labelled region on
narrow screens; long error messages wrap. Viewports are emulated in desktop engines, not
real phones or tablets.

## 6. Accessibility coverage

- **Automated audit**: `@axe-core/playwright` 4.13 with `wcag2a`, `wcag2aa`, `wcag21a`,
  `wcag21aa` and `best-practice` rules on all nine routes at 1440 px and 360 px, in light
  and dark themes, in all three engines — **zero violations** in the final run. This
  includes axe's colour-contrast rule in both themes, labels, names, duplicate IDs, ARIA
  validity, landmarks, heading order and table headers.
- **Keyboard**: Tab order and visible focus on landing, login and Train Model; Space/Enter
  on toggle buttons; Enter on sidebar links; Escape closes the dashboard drawer and the
  landing menu and returns focus; drawer focus containment; skip link is the first Tab stop
  (Chromium, Firefox).
- **Focus behaviour**: every checked Tab stop has a ≥2 px outline; focus returns to openers.
- **Accessibility tree**: attached per matrix run; accessible names checked for selects
  (Product/Category/Platform/Data source are named correctly in all three engines).
- **Link Tab order in WebKit**: measured, not assumed — in this WebKit build neither Tab nor
  Alt+Tab moves focus to links (buttons and inputs only), matching Safari's default
  "Press Tab to highlight each item" off. WebKit therefore verifies buttons, inputs and focus
  visibility, but **keyboard focus on links and the skip link is verified only in Chromium
  and Firefox**.
- **WebKit on Windows is not real Safari**, and **no manual screen-reader testing** (NVDA,
  JAWS, VoiceOver, TalkBack) was performed. This is not a WCAG certification.

## 7. Real application bugs found and fixed

1. **Protected deep-link login redirect race** (`src/pages/LoginPage.tsx`). Signing in after
   being redirected from a protected page landed on `/dashboard` in all three engines: once
   login set the session, the page re-rendered as authenticated and its early
   `<Navigate to="/dashboard">` won over the later `navigate(from)`. Both paths now use one
   validated destination; only same-app paths (starting with `/`, not `//`) are honoured.
2. **Dashboard crash on role-less account data** (`src/auth/permissions.ts`,
   `src/auth/normalizeUser.ts`, `src/services/authService.ts`, `src/types/auth.ts`,
   `src/components/PermissionGate.tsx`, `src/components/dashboard/Sidebar.tsx`).
   `TypeError: Cannot read properties of undefined (reading 'includes')` at
   `can()` from `DashboardPage`. An active account payload without `permissions` (a
   pre-Phase 13 backend, or any malformed response) passed the `is_active` check and
   crashed rendering. Reproduced in Chromium against a pre-Phase 13 backend, then fixed at
   the permission boundary without try/catch: account payloads are normalized at the API
   boundary, `can()` fails closed for missing/unknown/malformed users, roles, permissions
   and mappings, and `PermissionGate` keeps actions disabled ("Checking your permissions…")
   while the session is restoring. The same browser journey then had 0 errors and denied
   actions. A control is enabled only when both the server's permissions and the frontend's
   mirrored role matrix allow it; a test compares that matrix with
   `backend/app/auth/permissions.py`. The backend remains authoritative. Sidebar had the
   same direct `permissions.includes` risk; all other call sites already used `can()`.
3. **Keyboard focus indicator removed** on six form controls (`Field.tsx`, and selects/inputs
   in Analytics, Marketplace Data and Predictor): `focus:outline-none` overrode the global
   `:focus-visible` ring. Removed; the existing ring now shows.
4. **Scrollable tables not keyboard-reachable** (axe `scrollable-region-focusable`, serious,
   at 360 px): six horizontally scrolling table wrappers (Marketplace Data, Train Model ×2,
   Training Results ×2, Trends observation table) are now named `role="region"` elements with
   `tabIndex={0}`, as the chart wrapper already was.
5. **Empty table header** (axe `empty-table-header`): the confusion-matrix corner cell has
   screen-reader text "Actual class".
6. **Heading order on Trends** (axe `heading-order`): chart titles jumped from h2 to h4; they
   are h3 now with identical styling.
7. **Garbled text**: "Active Model ? Weighted F1" and "Loading dataset and model status?"
   (a character-encoding loss dating from commit `de173ee`) now read "Active Model · Weighted
   F1" and "Loading dataset and model status…". The same loss in
   `docs/PHASE_13_REPORT.md` punctuation was repaired.

## 8. Harness fixes

- **Brittle "480" assertion removed.** The dashboard check now requires the Stored Records
  card to show a positive whole number (fails on "Unavailable" or an empty value), because
  journeys add records to the shared isolated database.
- **Analyst product selection**: the test selects a product before expecting Make Prediction
  to be enabled (it is disabled for every role until a product is chosen).
- **401 and revocation races fixed**: tests now wait for the page's own API responses
  (`/analytics/summary`, `/ml/status`, Train Model's loaded state) before changing session
  state; no `networkidle` waits remain.
- **Request diagnostics added** (`e2e/diagnostics.ts`): every test records failed requests
  (method, URL, browser failure reason) and HTTP responses ≥400 (method, URL, status) as a
  `network-diagnostics` attachment. Headers, bodies, JWTs and secrets are never logged.
- **Network-abort noise filtered precisely**:
  - Chromium reports `net::ERR_ABORTED` for a body-less 204 that already has its response;
    recorded as informational `after-response`, not a failure.
  - Requests cancelled because the test navigated (Firefox `NS_BINDING_ABORTED`, WebKit
    `Load request cancelled`) are ignored only when they started before a test-initiated
    `goto`/`reload`, using the browser's request start time.
  - Playwright's WebKit reports such cancellations as page errors ("Fetch API cannot load … due
    to access control checks."). Measured: 13 reports while in-page `unhandledrejection` and
    `error` listeners recorded 0, so no application exception exists. Ignored only after a
    test navigation; CORS itself is verified by a dedicated test.
- **Selectors**: Trends/Analytics Product select uses its accessible role/name (the select sits
  inside its label, so `getByLabel` also matched option text); the operator test asserts DEMO
  is preselected instead of clicking (which deselected it); a regex escape bug flagged by lint
  fixed.
- **Harness lifecycle**: Playwright's web-server command uses a platform-native absolute path
  (Windows `cmd` could not run the relative POSIX path); `serve.py` purges stale `mp_e2e_*`
  schemas left when Windows stops the server without running cleanup; `PHASE14_REUSE_SERVER=1`
  lets verified running servers be reused.

## 9. ENOTFOUND investigation

An `API Error: Can't reach the API server — check your internet or DNS (ENOTFOUND)` message
appeared during an earlier long cross-browser run.

- **No failing hostname was found in the harness.** The string does not occur in the Playwright
  output, test results, reports, backend or server logs, or task outputs.
- Every host the harness requests is the IP literal `127.0.0.1` (ports 5184, 8184, 55434), which
  needs no DNS lookup. `attacker.example` and `frontend.marketpulse.test` appear only as Origin
  header or CORS configuration strings and are never requested.
- Windows logged Modern Standby during that run (18:22–19:00 and 19:00–20:50, with
  "Connectivity state in standby: Disconnected", plus short standbys near 21:52), which
  explains its 2.9-hour duration and a 37.9-minute test.
- The likely cause is an **external network/standby event outside the harness**. This is not a
  proven cause and **not an application bug**. Later runs kept the system awake for their
  duration and completed normally.

## 10. Production-style verification (not hosted)

- **Tested locally**: a production-mode backend (`ENVIRONMENT=production`, database storage,
  PostgreSQL 17 `postgres:17-alpine` on `127.0.0.1:55434`, one worker, isolated schema per run)
  and the **production bundle** served with an SPA history fallback equivalent to the
  `vercel.json` rewrite, on a separate origin with exact CORS. Direct visits and refreshes on
  protected routes, API base URL, CORS and 401/403/404/413/422/429/5xx handling were verified.
- **Vercel build guard** rechecked: `VERCEL=1` without `VITE_API_BASE_URL` fails, an
  `http://` URL fails, an `https://` URL builds with that URL. The remaining `localhost` strings
  in bundles are React Router's URL-parsing base, not API addresses.
- **HTTPS and mixed content** could not be exercised: the local environment is HTTP.
- **No real Vercel or Render URL exists or was verified.** No deployment was performed.

## 11. Remaining browser and accessibility limitations

- WebKit link Tab behaviour (section 6): link and skip-link keyboard focus unverified in WebKit.
- No macOS Safari and no iOS Safari; WebKit here is the Windows build.
- No manual assistive-technology (screen reader) validation was performed.
- No real mobile/tablet devices; touch gestures were not tested; viewports are emulated.
- Native `<select>` dropdown keyboard operation is browser-provided and was not scripted
  beyond focus and visible focus.
- axe cannot judge every state (hover, transient toasts, disabled-control contrast is exempt);
  contrast was not checked manually.
- No hosted verification (TLS, CDN rewrite behaviour, real cross-site cookies/CORS at the edge).
- Performance was checked only for idle request loops; the main bundle is one chunk of about
  402 kB (117 kB gzip). No Lighthouse or throttled-network profiling.

## 12. Backend test result

Full suite with `TEST_POSTGRES_URL` pointing at the disposable `phase14` database in the
`marketpulse-phase14-tests` container (each PostgreSQL test uses its own schema):

**497 tests — 496 passed, 1 skipped (opt-in LIVE Flipkart), 0 failures, 0 errors, 236.7 s.**
No backend code changed in Phase 14; no regression fixes were needed. Warnings are the existing
dependency deprecations and scikit-learn notices about empty DEMO trend features.

## 13. Frontend test, build and lint result

- `npm run build` (`tsc -b && vite build`): passed.
- `npm run lint` (oxlint): passed, no warnings.
- `npm test`: **38/38 passed**, including 28 permission tests (undefined, null, unknown, empty and
  non-string roles; valid viewer/analyst/operator/administrator; restoring auth state; missing or
  malformed permission mappings and fields; pre-Phase 13 payload normalization; Dashboard and
  Sidebar rendering for a role-less account; backend role-matrix drift check). With the original
  `can()` restored temporarily, 14 of them failed, including the exact Dashboard crash.
- E2E TypeScript type-check of `e2e/*.ts` (strict): passed.

## 14. git diff --check

Clean (only Git's CRLF normalization notices, which are not whitespace errors).

## 15. Development data and artifact preservation

- **Model artifacts v1–v5** (`backend/app/ml/artifacts/`) and processed datasets were not
  modified: their modification times predate Phase 14 (v1–v4 September 10, v5 September 14
  00:18), and all 164 development data/model files were byte-identical before and after the
  backend test run.
- **No test used the development database.** Browser tests used an isolated production-mode
  backend on disposable PostgreSQL; backend tests use temporary storage and throwaway schemas.
- **The development database was migrated, at the owner's explicit request.** When asked to "run
  the project", the owner chose to back up and run against the development database. A consistent
  SQLite backup at `0004` was taken first (`data/backups/marketpulse-pre-0008-20260914-174616.db`),
  then normal startup applied `0005`–`0008`. Afterwards: revision `0008`, 24 users (all `viewer`
  until promoted), 480 DEMO snapshots, 0 LIVE, 2 predictions, 5 model records, active model v5
  (XGBoost, DEMO-trained, below baseline). The development backend (port 8001, because port 8000
  belongs to an unrelated container) and Vite dev server (5173) were still running at the time of
  writing, so ordinary use can change that database file.
- `data/backups/` (backup and dev-server logs) is now ignored by Git.

## 16. Files changed in Phase 14

Application (frontend):

- `frontend/src/auth/permissions.ts` — fail-closed permission boundary
- `frontend/src/auth/normalizeUser.ts` — **new**, account payload normalization
- `frontend/src/types/auth.ts`
- `frontend/src/services/authService.ts`
- `frontend/src/components/PermissionGate.tsx`
- `frontend/src/components/Field.tsx`
- `frontend/src/components/dashboard/Sidebar.tsx`
- `frontend/src/components/dashboard/ObservedLineChart.tsx`
- `frontend/src/components/dashboard/TrainingResults.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/TrainModelPage.tsx`
- `frontend/src/pages/MarketplaceDataPage.tsx`
- `frontend/src/pages/PredictorPage.tsx`
- `frontend/src/pages/AnalyticsPage.tsx`

Tests and harness:

- `frontend/tests/permissions.test.mjs`
- `frontend/e2e/smoke.spec.ts` — **new**
- `frontend/e2e/journeys.spec.ts` — **new**
- `frontend/e2e/diagnostics.ts` — **new**
- `frontend/e2e/verification.spec.ts` (pre-existing uncommitted spec, repaired and extended)
- `frontend/e2e/serve.py`
- `frontend/playwright.config.ts`

Documentation and configuration:

- `docs/PHASE_14_REPORT.md` — **new**
- `docs/PHASE_13_REPORT.md` (punctuation encoding repair only)
- `OVERALL_PROJECT_REPORT.md`
- `CLAUDE.md`
- `README.md`
- `.gitignore`

No backend application code, migrations, ML modules, connectors or model artifacts changed.

## How to run

```sh
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8184 npx vite build --outDir .e2e-dist --emptyOutDir
export PHASE14_POSTGRES_URL=postgresql://USER:PASSWORD@127.0.0.1:PORT/phase14   # disposable, loopback only
npx playwright test e2e/smoke.spec.ts --project=chromium    # then firefox, webkit
npx playwright test e2e/journeys.spec.ts
npx playwright test e2e/verification.spec.ts
```

`serve.py` refuses non-loopback hosts and databases whose name does not start with `phase14`.
Keep the machine awake during long runs; a suspended system stalls the browsers.
