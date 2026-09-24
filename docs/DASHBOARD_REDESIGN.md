# Workspace UI redesign (2026-09-15)

A visual and UX redesign of the signed-in workspace, based on the layout ideas in
`docs/MarketPulse_AI_Dribbble_Dashboard_Redesign_Prompt.md`. No assets were copied. No backend
code, API contract, route, permission, ML pipeline or scoring formula changed.

## What changed

- **Design tokens** (`frontend/src/index.css`): a `.workspace` palette used only inside the app,
  so the public site keeps its amber brand. It has a cool neutral background, white cards and
  one indigo accent. Green, amber and red are used only for status. There are also chart colours
  (`--chart-1..4`, grid, track), a `--shadow-pop`, the `ease-standard` easing, a `surface-card`
  utility and `.skeleton` loading blocks. Every text pairing was checked against WCAG AA in both
  themes. Light `--signal-ok` was darkened to `#136b41` so it also passes on tinted backgrounds.
- **Shell** (`DashboardLayout`, `Sidebar`, new `AccountMenu`):
  - The sidebar is split into two groups, "Decision support" and "Data & models". The active
    page shows an accent bar.
  - The top bar shows the page title and a subtitle (the subtitle comes from
    `config/dashboard.ts`). It also has a Run prediction link (only for roles with
    `prediction:run`), the theme toggle, and an account menu with the user's name, email, role
    and a Sign out button.
  - The mobile drawer keeps its focus trap, Escape to close, scroll lock and return of focus.
  - The "Dashboard" navigation entry is now called "Overview".
- **Overview** (`DashboardPage`): welcome header with Run prediction, a DEMO data banner, 4 KPI
  cards, a stored observation history chart, the latest recommendation, a platform comparison,
  a data quality & attention panel, a recent predictions table, pipeline status, quick actions,
  market data refresh and "What works right now".
- **New components** in `components/dashboard/`: `SectionCard`, `StateViews` (skeleton, empty
  and error states with Retry), `PlatformBadge`, `DemoDataBanner`, `PlatformScoreRow`,
  `RecommendationCard`, `DataQualityPanel`, `RecentPredictionsTable`, `PriceHistoryPanel`,
  `MultiSeriesChart`. Pure logic lives in `lib/dashboardInsights.ts` and `lib/platforms.ts`.
- **Predictor**: the form is now three numbered steps plus a "How to read a result" side card.
  The prediction request, warnings and error handling are unchanged. `?prediction=<id>` opens a
  saved result exactly as it was saved; the overview links use it.
- **Prediction results**:
  - The page opens with the recommended platform and its score, next to the model quality
    measured at prediction time.
  - Platform score bars are ordered by rank.
  - Score contributions are now always-visible bars, where each bar is points out of the
    component weight. Class probabilities moved into their own expandable section.
- **Analytics, Trends, Marketplace Data, Train Model**: these pages use the same cards, filters
  and platform badges. Their content, labels and controls are unchanged.

## Where each overview figure comes from

| UI | API field(s) |
|---|---|
| Stored Records + source mix | `/analytics/summary` `stored_records`, `records_by_source_type`, `stored_platforms` |
| Total Predictions | `/analytics/summary` `total_predictions` |
| Active Model · Weighted F1 | `/ml/status` `primary_metric_value`, `majority_baseline`, `quality.quality_status`, `active_model`, `version` |
| Items Needing Attention | count of `attentionItems()` (below) |
| DEMO banner | `records_by_source_type.demo` / `.live` |
| Stored observation history | `/analytics/options` products; `/analytics/trends?product_key&platform` `series[].points[].price|discount|rating`, `provenance` |
| Latest recommendation | `/ml/predictions` newest item → `/ml/predictions/{id}` `recommended_platform`, `recommendation_label`, `ranking[0].opportunity_score`, `components`, `formula.weights`, `score_difference`, `model.*`, `data_provenance`, `warning` |
| Platform comparison | the same saved result: `platform_results[]` `opportunity_score`, `coverage_weight`, `key_factors`, `source_type`, `stale`, `reason` |
| Data quality & attention | summary (`live` count, `available_live_platforms`, `refresh_sources[].state`, `latest_dataset`), model (`trained`, `quality_status`, `notice`), latest result (`stale`, missing scores) |
| Recent predictions table | `/ml/predictions` `items[]` `product`, `recommended_platform`, `top_score`, `source_types`, `model.quality_status`, `created_at`, `id` |
| Pipeline status | summary `latest_observation`, `latest_observation_sources`, `available_live_platforms`, `latest_dataset`, `stored_platforms`, `notice` |

## What was deliberately kept out

- No sales, revenue, order, customer or inventory figures, because the backend has none.
- No trend arrows on KPI cards, because stored history gives no valid earlier period to
  compare against.
- No global search, notifications or profile page, because those features don't exist.
- No date-range control on the overview chart. DEMO timestamps are in the past, so a "last N
  days" filter would show nothing. The full date filters remain in Trend Analysis.
- Chart values are never interpolated: a missing reading breaks the line. Price lines are shown
  for one currency at a time. Every listing history gets its own line, with a legend and a
  table of the values.

## Verification (2026-09-15)

- `npm run build`: passed. `npm run lint` (oxlint): exit 0. `npm test`: **49/49** (38 existing
  plus 11 new in `tests/dashboard.test.mjs`).
- Backend: no files changed, so backend tests were not rerun.
- Browser (Playwright Chromium only):
  - Setup: a throwaway backend in development mode with SQLite in temporary storage, the demo
    fixture, a random-forest model trained on DEMO data and 2 analyst predictions. The
    development database was not used.
  - Coverage: 6 workspace routes × 1440/1024/768/360 px × light/dark, signed in as analyst and
    as viewer. Result: no horizontal overflow, no console errors, no HTTP ≥ 400 responses, and
    0 axe WCAG 2.0/2.1 A/AA + best-practice violations at 1440 and 360.
  - A script repeated the key selectors from `journeys.spec.ts` and `verification.spec.ts`
    (viewer and analyst permissions, predict and View result, Trends/Analytics product combobox
    and chart table, Logout, mobile drawer focus trap and Escape). All passed.
- **Not rerun:** the Phase 14 Playwright suite. It needs the disposable PostgreSQL container,
  and Docker was not running. Firefox and WebKit were not run.

## Limitations that still apply

- Stored data is DEMO; there are 0 LIVE observations.
- The active model is DEMO-trained and below baseline.
- LIVE collection stays gated: Flipkart needs credentials plus written approval, and
  Amazon, Croma and Alibaba are unavailable.
- Scores are a price-direction opportunity proxy, not demand forecasts.

## Lavender theme pass (2026-09-15, later)

The whole frontend (landing, login, register and the workspace) now follows one lavender reference design.
The copy, routes and behaviour are unchanged.

- **Tokens** (`index.css`, both themes):
  - Light theme: ground `#F5F3FF`, alt `#EDE9FE`, white cards, text `#1E1B4B`, accent `#7C3AED`
    (hover `#6D28D9`), secondary `#A78BFA`.
  - Dark theme: a violet-tinted version of the same.
  - Status colours are deepened in light mode (`#04683F`, `#8F3F0B`, `#A91B1B`) so they stay
    AA on tinted backgrounds.
  - Panel radius is now 20 px, with purple-tinted card, pop and accent shadows. A soft radial
    `--page-wash` sits behind pages.
  - `--color-brand` and `--color-brand-deep` are fixed deep-violet fills for the logo tile,
    avatars and the auth badge, because they carry white text in both themes.
  - The indigo palette scoped to `.workspace` was removed.
- **Components:**
  - Primary buttons have an accent shadow, and large buttons are pills.
  - Inputs are white with a soft focus halo; the 2 px focus outline is kept.
  - Landing sections are transparent or translucent bands with pill eyebrows.
  - Feature and flip cards, Developer, Contact and Footer use the card style.
  - The navbar Register link is a primary pill.
  - The login and register card now contains the title, with a decorative check badge.
- **Hero:** at `lg` and wider, the text is left-aligned beside a decorative illustration built
  from abstract cards and bars. The illustration is `aria-hidden` and has no numbers or labels.
  Narrower layouts are unchanged.
- **Not added from the reference:** search, notifications, and Products/Reports/Settings pages.
  None of these exist in the app, so they would be dead controls or invented content. No web
  font was added: an external font host would break the E2E "no stray hosts" check, and the
  font stack already lists Inter first.
- **Verified:**
  - `tsc` and oxlint are clean, and `npm test` passes 49/49.
  - Chromium, public pages: `/`, `/login` and `/register` at 1440/1024/768/360 px in
    light/dark, with no overflow, no console errors and 0 axe violations (axe run at 1440 and
    360).
  - Chromium, workspace: the 6-route analyst matrix is clean, and the key E2E selector script
    passes.
  - The Phase 14 Playwright suite was still not rerun.
