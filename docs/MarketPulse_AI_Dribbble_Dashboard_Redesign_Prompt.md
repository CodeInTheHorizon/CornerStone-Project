# MarketPulse AI — Dribbble-Inspired Dashboard Redesign Prompt

## How to use this file

Give the complete prompt below to Codex or Claude Code from the root of the existing MarketPulse AI repository. Attach or paste the Dribbble screenshot as well if the coding agent cannot open the reference URL.

---

## Complete implementation prompt

You are a senior product designer and frontend engineer working inside the existing **MarketPulse AI** repository. Redesign the authenticated application UI—especially the seller dashboard—using the following Dribbble shot as visual direction:

**Design reference:**  
https://dribbble.com/shots/27265849-E-Commerce-Admin-Dashboard

First inspect the repository, its current UI, routes, components, styling system, tests, and API integrations. Then inspect the design reference. If the URL cannot be opened, use the detailed visual direction in this prompt. Do not begin by replacing the project or generating an unrelated starter app.

### 1. Product context

MarketPulse AI is a full-stack decision-support platform for offline electronics sellers, shopkeepers, wholesalers, and manufacturers who want to evaluate which online marketplace may be most suitable for a product.

The application compares marketplace observations from platforms such as:

- Amazon
- Flipkart
- Croma
- Alibaba

Its main product areas include:

- seller overview dashboard;
- product and marketplace observations;
- AI/ML-assisted marketplace prediction;
- prediction history and details;
- market analytics and trends;
- dataset/data-management views;
- authentication, user profile, and role-aware access;
- administrative or operational screens already present in the repository.

The dashboard must help a seller answer these questions quickly:

1. What is happening across the observed marketplaces?
2. Which product or category should I investigate?
3. Which platform currently receives the strongest recommendation?
4. Why did the system produce that recommendation?
5. What data limitations, warnings, or risks should I understand before acting?

### 2. Non-negotiable product truth

This is primarily a **visual and UX redesign**, not a backend or ML rewrite.

- Preserve all current routes, authentication behavior, role checks, API contracts, database behavior, prediction calculations, provenance, warnings, and existing tests.
- Do not change the saved ML pipeline or prediction scoring formula unless an actual compatibility defect makes a small change unavoidable.
- Preserve the current scoring model and its contribution data. The existing formula uses model quality, price competitiveness, rating, review volume, discount, competition, and price trend inputs.
- Preserve existing loading, empty, error, unauthorized, and DEMO/baseline states.
- Existing stored marketplace observations are synthetic/demo unless the repository explicitly proves otherwise. Clearly label synthetic values as **DEMO data**. Never call them live, real-time, fresh, or scraped data.
- Treat any existing LIVE connector or on-demand refresh as gated unless credentials and approval are genuinely configured.
- Do not fabricate sales, revenue, profit, order, customer, or inventory values just because the reference design contains conventional e-commerce metrics.
- If the backend does not provide a value, show an honest empty state, unavailable state, or remove the metric.
- Do not copy proprietary logos, illustrations, or assets from the Dribbble shot. Recreate only the layout language and interaction style with original implementation and existing project branding.

### 3. Design goal

Transform the current MarketPulse AI application into a refined, premium analytics workspace inspired by the reference: spacious, structured, calm, modern, and data-dense without looking crowded.

The result should feel designed for a seller making a business decision—not like a generic admin template. Translate the reference design into MarketPulse AI’s information architecture rather than reproducing unrelated store-management content.

### 4. Visual direction

Use the reference as guidance for composition, visual hierarchy, spacing, card treatment, typography, sidebar behavior, chart styling, and density.

Implement the following fallback direction if the shot is inaccessible:

- A soft off-white or very light neutral application background.
- A slim, persistent left navigation rail/sidebar on desktop with the MarketPulse AI brand at the top.
- A wide main canvas with generous but efficient spacing.
- White or subtly tinted cards with soft borders, restrained shadows, and consistent rounded corners.
- A dark charcoal or near-black primary text color.
- Muted neutral secondary text.
- One controlled brand accent, preferably a confident indigo/blue-violet, with green, amber, and red reserved for semantic states.
- Contemporary sans-serif typography such as Inter or the repository’s existing equivalent.
- Compact icons from the project’s current icon library; do not mix icon families.
- Thin chart grids, readable axis labels, restrained fills, and strong selected states.
- Subtle 150–220 ms transitions for hover, focus, menu expansion, tabs, and filter controls.
- No glassmorphism overload, neon gradients, excessive animation, giant hero sections, decorative 3D objects, or chart clutter.

Create a coherent token system for:

- colors;
- typography scale;
- spacing;
- border radii;
- borders;
- shadows;
- chart colors;
- semantic status colors;
- focus rings;
- motion duration and easing.

Use existing CSS variables/theme infrastructure where possible. Avoid scattering raw colors and spacing values throughout components.

### 5. Application shell

#### Desktop sidebar

Include only routes that actually exist. Map existing routes into a clear hierarchy such as:

- Overview
- Predictor
- Predictions
- Market Analytics
- Products or Observations
- Datasets/Data Sources
- Settings/Profile

Place administrative links in a separate group and render them only for authorized roles. Include clear active, hover, and keyboard-focus states. Support a collapsed icon-only state only if it fits the existing architecture without destabilizing navigation.

#### Top bar

Include:

- page title and short contextual subtitle or breadcrumb;
- global search only if it can search real application entities;
- time-range or category controls where meaningful;
- notifications only if the feature exists—otherwise omit it;
- user avatar/menu with profile and logout actions;
- a clear primary action such as **Run prediction**.

Do not add dead controls.

#### Responsive navigation

On tablet/mobile, convert the sidebar into a keyboard-accessible drawer or compact navigation pattern. Preserve all authorized destinations and make closing, backdrop behavior, focus management, and scroll locking reliable.

### 6. Overview dashboard information architecture

Build the overview from real fields already returned by the current APIs. Adapt labels to the exact domain model discovered in the repository.

#### A. Welcome and decision header

Show a concise greeting, explanation of the selected scope, and a primary **Run prediction** action. Display an obvious DEMO-data badge or banner whenever the visible data is synthetic.

#### B. Decision KPI cards

Use three or four compact cards. Prioritize decision-support metrics such as:

- products or observations analyzed;
- marketplaces compared;
- predictions generated in the selected period;
- latest recommended platform or average confidence, only when supported;
- warnings/data-quality issues requiring attention.

Each card should contain a clear label, prominent value, small contextual note, optional trend only when a valid comparison exists, and a consistent icon container. Never calculate a trend from insufficient data.

#### C. Main trend visualization

Create a large chart using the project’s current chart library. Depending on available API fields, visualize one defensible metric over time, such as observed price trend, prediction activity, platform score trend, or product observation volume.

Requirements:

- meaningful title and supporting subtitle;
- platform/category and date-range filters wired to real state;
- accessible tooltip;
- readable legend;
- responsive sizing;
- skeleton while loading;
- empty state when no time-series exists;
- no misleading interpolation or invented points.

#### D. Platform comparison panel

Show Amazon, Flipkart, Croma, and Alibaba only where present in the selected prediction/observation set. Use horizontal score bars, a compact bar chart, or ranked rows.

Each platform row may show:

- normalized/recommendation score;
- rank;
- price competitiveness;
- rating/review signal;
- competition or trend signal;
- warning/provenance indicator.

Clearly distinguish a model recommendation score from revenue, demand, or guaranteed profit. Do not imply certainty.

#### E. Latest recommendation card

Highlight the most recent prediction with:

- product/category;
- recommended marketplace;
- confidence or score label using correct terminology;
- short explanation based on actual contribution data;
- top positive factors;
- warnings and baseline/model-quality notice;
- timestamp;
- link to the existing prediction-detail route.

Do not hide important warnings behind hover-only UI.

#### F. Recent predictions table

Create a clean, responsive table containing only supported fields, for example:

- product/category;
- recommended marketplace;
- score/confidence;
- data mode or provenance;
- created date;
- status/warning;
- action to view details.

Provide search/filter/sort only when they work. On small screens, use horizontally scrollable tables with sticky key columns or accessible stacked rows/cards. Preserve pagination if already implemented.

#### G. Data quality or attention panel

Summarize missing fields, stale observations, baseline-model warnings, gated connectors, or other real validation issues. Use semantic colors carefully and link to the relevant existing workflow.

### 7. Predictor and detail pages

Apply the same visual system throughout the authenticated product, not only the first dashboard screen.

#### Predictor

- Create a clear step-based or sectioned input flow without turning it into a multi-page wizard unless already supported.
- Group product selection, marketplace observations, optional filters, and the final action logically.
- Make field help, validation, units, and required states obvious.
- Preserve current preview data, prediction request payload, warnings, and error handling.
- Keep the primary action visible without covering form content.

#### Prediction result/detail

- Lead with the recommended marketplace and correct score/confidence terminology.
- Show all marketplace comparisons beneath it.
- Present contribution breakdowns as readable bars or a chart tied to real values.
- Include formula/provenance/model-quality information in a structured explanation panel.
- Keep warnings prominent.
- Retain historical snapshot semantics so old results are not silently rendered using new/current observations.

#### Analytics, datasets, tables, profile, and admin views

- Reuse the same shell, tokens, cards, filters, table patterns, badges, skeletons, empty states, and form controls.
- Do not leave visually obsolete pages that clash with the redesigned dashboard.
- Do not expose admin actions to unauthorized users.

### 8. Component architecture

Before coding, identify reusable patterns and create/refactor focused components. Suggested examples—adapt names to repository conventions:

- `AppShell`
- `SidebarNav`
- `TopBar`
- `PageHeader`
- `DemoDataBanner`
- `MetricCard`
- `DashboardSection`
- `FilterBar`
- `PlatformBadge`
- `StatusBadge`
- `PlatformScoreRow`
- `RecommendationCard`
- `DataQualityPanel`
- `RecentPredictionsTable`
- chart wrappers and reusable loading/empty/error states

Avoid one enormous dashboard component. Also avoid unnecessary abstraction for components used once.

### 9. UX, accessibility, and quality requirements

- Meet WCAG 2.1 AA contrast wherever practical.
- All interactive controls must be keyboard reachable and display a visible focus state.
- Icon-only buttons require accessible names and tooltips where helpful.
- Use semantic landmarks, headings, labels, tables, and buttons.
- Do not communicate status by color alone.
- Respect `prefers-reduced-motion`.
- Avoid layout shifts during data loading.
- Use skeletons for known content shapes and clear empty/error/retry states.
- Make chart information available through labels, tooltips, summaries, or an accessible table where appropriate.
- Ensure usable layouts at approximately 360 px, 768 px, 1024 px, and 1440 px widths.
- Prevent horizontal page overflow; only intentionally scrollable data tables may overflow internally.
- Keep performance sensible: lazy-load heavy routes/charts when supported, avoid needless rerenders, and do not add a large dependency solely for a minor visual effect.

### 10. Repository-safe execution workflow

1. Read `CLAUDE.md`, `AGENTS.md`, `README`, package manifests, frontend source, route configuration, API client/types, and relevant tests.
2. Run `git status` and preserve all existing user changes. Do not reset, delete, or overwrite unrelated work.
3. Start the current frontend if practical and document the existing visual/functional baseline.
4. Inventory every authenticated route and map each one to the redesigned shell.
5. Identify which dashboard values are directly supported by current APIs. Create a small data-to-UI mapping before implementation.
6. Implement the design tokens and shared shell first.
7. Redesign the overview dashboard with real API wiring.
8. Apply the same system to Predictor, prediction history/detail, analytics, data, profile, and authorized admin pages.
9. Preserve or improve all loading, error, empty, authorization, DEMO, and responsive states.
10. Update/add tests for navigation, route rendering, key interactions, accessibility-sensitive behavior, and data-state rendering.
11. Run formatter, type-checker, linter, unit/integration tests, production build, and relevant backend tests if shared contracts were touched.
12. If browser tooling exists, visually verify major routes at desktop and mobile widths and correct clipping, overflow, spacing, focus, and console errors.
13. Update project documentation with a concise redesign summary and verification results.

### 11. Implementation boundaries

- Work inside the current frontend stack and styling architecture unless there is a compelling repository-backed reason to change it.
- Prefer the dependencies already installed.
- Do not migrate frameworks, replace authentication, rename API fields, or rewrite backend modules for visual convenience.
- Do not remove working features to make the layout match the reference.
- Do not use hard-coded dashboard numbers in production components.
- Test fixtures may use explicit sample values and must remain clearly isolated from production behavior.
- Do not add dark mode unless the project already supports it or it can be implemented without compromising the main redesign.
- Do not perform deployment, change secrets, or alter production infrastructure unless separately requested.
- Do not make a commit unless asked. Leave the worktree ready for review.

### 12. Acceptance criteria

The redesign is complete only when:

- the authenticated MarketPulse AI interface has a cohesive visual system inspired by the reference;
- the dashboard communicates marketplace decision support rather than generic store administration;
- existing routes, auth, role restrictions, APIs, prediction behavior, snapshots, and warnings still work;
- all synthetic information is clearly labeled DEMO and no unsupported live-data claim appears;
- no fabricated business KPI is displayed;
- desktop, tablet, and mobile layouts are usable;
- navigation and principal workflows work with keyboard input;
- every async panel has loading, empty, and error handling;
- charts and comparison widgets use real returned values and honest labels;
- changed code passes formatting, type-checking, linting, tests, and production build;
- there are no new browser console errors or obvious visual regressions;
- documentation states what changed, what was preserved, and what remains gated or unavailable.

### 13. Required final report

When finished, report:

1. a concise summary of the redesigned experience;
2. all major files/components changed;
3. the API fields mapped to every dashboard metric/chart;
4. routes visually updated;
5. responsive and accessibility work completed;
6. commands/tests/builds run and their exact results;
7. anything not completed and why;
8. any remaining DEMO, baseline-model, connector, or data-quality limitations;
9. screenshots or preview links if the environment supports them.

Do not claim completion based only on generated code. Inspect the result, run the available verification, and explicitly disclose any check that could not be performed.

---

## Optional reference attachment note

If the coding agent cannot access Dribbble, provide a screenshot of the shot with this file and add:

> Treat the attached screenshot as visual inspiration for hierarchy, proportions, spacing, card composition, navigation, typography, and chart styling. Preserve MarketPulse AI’s own branding, content, product truth, and workflows; do not copy logos or proprietary assets.
