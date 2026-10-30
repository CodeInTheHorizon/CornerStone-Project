import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true, hmr: false } })
const load = (path) => server.ssrLoadModule(path)
const { attentionItems, chartSeries, seriesCurrencies } = await load('/src/lib/dashboardInsights.ts')
const { ROLE_PERMISSIONS } = await load('/src/auth/permissions.ts')
const { AuthContext } = await load('/src/auth/authContext.ts')
const { ThemeContext } = await load('/src/theme/themeContext.ts')
const { Sidebar } = await load('/src/components/dashboard/Sidebar.tsx')
const { DashboardLayout } = await load('/src/components/dashboard/DashboardLayout.tsx')
const { SummaryCard } = await load('/src/components/dashboard/SummaryCard.tsx')
const { PlatformScoreRow } = await load('/src/components/dashboard/PlatformScoreRow.tsx')
const { RecentPredictionsTable } = await load('/src/components/dashboard/RecentPredictionsTable.tsx')
const { RecommendationCard } = await load('/src/components/dashboard/RecommendationCard.tsx')
const { MultiSeriesChart } = await load('/src/components/dashboard/MultiSeriesChart.tsx')
const { dashboardNav } = await load('/src/config/dashboard.ts')
const React = await import('react')
const { renderToStaticMarkup } = await import('react-dom/server')
const { MemoryRouter } = await import('react-router-dom')
after(async () => { await server.close() })

// Explicit test fixtures; never used by production components.
const account = (role) => ({ id: 1, email: `${role}@example.com`, full_name: 'Test User', role, permissions: ROLE_PERMISSIONS[role], is_active: true, created_at: 'x' })
function render(element, { user = account('viewer'), path = '/dashboard' } = {}) {
  const auth = { user, token: 'token', status: 'authenticated', sessionError: null, login: async () => {}, register: async () => {}, logout: async () => {} }
  const theme = { preference: 'light', theme: 'light', setPreference() {}, toggle() {} }
  return renderToStaticMarkup(React.createElement(MemoryRouter, { initialEntries: [path] },
    React.createElement(ThemeContext.Provider, { value: theme },
      React.createElement(AuthContext.Provider, { value: auth }, element))))
}

const summary = (overrides = {}) => ({
  total_predictions: 2, stored_records: 480, records_by_source_type: { demo: 480 }, latest_observation: '2026-09-01T00:00:00',
  latest_observation_sources: ['demo'], stored_platforms: ['amazon', 'flipkart'], available_live_platforms: [],
  refresh_sources: [{ platform: 'flipkart', available: false, state: 'credentials_missing', reason: null, access_method: 'api', required_configuration: [] }],
  active_model: null, latest_dataset: { dataset_id: 'ds-1', source_types: ['demo'], generated_at: null, file_available: true }, notice: '', ...overrides,
})
const platform = (name, score, overrides = {}) => ({
  platform: name, status: 'ok', reason: score == null ? 'Insufficient data for this exact product.' : null, predicted_class: 'up', confidence: 0.4,
  probabilities: { up: 0.4 }, opportunity_score: score, components: { price_competitiveness: 20, rating: 5 }, normalized_signals: {},
  coverage_weight: 80, missing_components: [], key_factors: ['price_competitiveness'], model_version: 'v5', source_type: 'demo',
  data_freshness: '2026-09-01T00:00:00', stale: false, warning: 'DEMO warning', ...overrides,
})

// --- Insights: derived only from returned fields ------------------------------

test('DEMO-only data and gated collectors are flagged for attention', () => {
  const items = attentionItems(summary(), null, null)
  const ids = items.map((item) => item.id)
  assert.ok(ids.includes('no-live'))
  assert.ok(ids.includes('collectors-gated'))
  assert.match(items.find((item) => item.id === 'no-live').detail, /480 DEMO/)
  assert.match(items.find((item) => item.id === 'collectors-gated').detail, /Flipkart: Credentials missing/)
})

test('below-baseline model is critical; stale and unscored platforms are reported', () => {
  const model = { trained: true, quality: { quality_status: 'below_baseline' }, primary_metric_value: 0.319, majority_baseline: 0.406, notice: null }
  const latest = { platform_results: [platform('amazon', 60, { stale: true }), platform('croma', null)] }
  const items = attentionItems(summary({ records_by_source_type: { live: 3 }, available_live_platforms: ['flipkart'] }), model, latest)
  assert.equal(items.find((item) => item.id === 'below-baseline').tone, 'down')
  assert.match(items.find((item) => item.id === 'stale').detail, /Amazon/)
  assert.match(items.find((item) => item.id === 'unscored').detail, /Croma/)
  assert.equal(items.some((item) => item.id === 'no-live' || item.id === 'collectors-gated'), false)
})

test('an untrained model and a missing summary never invent items', () => {
  assert.deepEqual(attentionItems(null, null, null), [])
  assert.deepEqual(attentionItems(null, { trained: false }, null).map((item) => item.id), ['no-model'])
})

test('chart series keep currencies apart, keep gaps and label duplicate listings', () => {
  const series = (platformName, currency, listing, prices) => ({ platform: platformName, source_type: 'demo', currency, listing_key: listing, points: prices.map((price, index) => ({ timestamp: `2026-09-0${index + 1}T00:00:00`, price, discount: null, rating: 4, reviews: 1, availability: 1, discount_derived: false })) })
  const input = [series('amazon', 'INR', 'a', [100, null, 90]), series('amazon', 'INR', 'b', [110, 105]), series('alibaba', 'USD', 'c', [3, 4])]
  assert.deepEqual(seriesCurrencies(input), ['INR', 'USD'])
  const inr = chartSeries(input, 'price', 'INR')
  assert.equal(inr.length, 2)
  assert.deepEqual(inr[0].points.map((point) => point.value), [100, null, 90])
  assert.deepEqual(inr.map((item) => item.label), ['Amazon · DEMO · INR · listing 1', 'Amazon · DEMO · INR · listing 2'])
  assert.equal(chartSeries(input, 'discount', 'INR').length, 0, 'series without any value are dropped, not drawn as zero')
  assert.equal(chartSeries(input, 'rating', 'INR').length, 3, 'unitless metrics are not filtered by currency')
})

// --- Shell ----------------------------------------------------------------------

test('sidebar groups every route and keeps the role-aware Train Model label', () => {
  const html = render(React.createElement(Sidebar), { user: account('analyst') })
  assert.match(html, /Decision support/)
  assert.match(html, /Data &amp; models/)
  for (const item of dashboardNav.filter((entry) => entry.to !== '/dashboard/train')) assert.ok(html.includes(`href="${item.to}"`), item.to)
  assert.match(html, /Datasets \/ Model Status/)
  assert.match(html, /analyst@example\.com · analyst/)
  assert.match(render(React.createElement(Sidebar), { user: account('operator') }), />Train Model</)
})

test('top bar renders cleanly with accessible navigation and account controls', () => {
  const page = (user, path) => render(React.createElement(DashboardLayout, { title: 'Products' }, 'content'), { user, path })
  const html = page(account('viewer'), '/dashboard/products')
  assert.match(html, /<h1[^>]*>Products<\/h1>/)
  assert.match(html, /aria-label="Account menu"/)
  assert.match(html, /aria-label="Open navigation"/)
  assert.match(html, /<main/)
})

// --- Components --------------------------------------------------------------

test('summary card shows unavailable text or a skeleton instead of a placeholder number', () => {
  const unavailable = render(React.createElement(SummaryCard, { label: 'Active Model', icon: 'target', unavailable: 'Not trained' }))
  assert.match(unavailable, /Not trained/)
  const loading = render(React.createElement(SummaryCard, { label: 'Stored Records', icon: 'database', value: 480, loading: true }))
  assert.doesNotMatch(loading, /480/)
  assert.match(loading, /Loading Stored Records/)
  assert.match(render(React.createElement(SummaryCard, { label: 'Stored Records', icon: 'database', value: 480 })), /Stored Records<\/p>.*480/)
})

test('platform score row draws a meter only when a score exists', () => {
  const scored = render(React.createElement(PlatformScoreRow, { platform: platform('flipkart', 62.5), rank: 1, recommended: true }))
  assert.match(scored, /role="meter"/)
  assert.match(scored, /aria-valuenow="62.5"/)
  assert.match(scored, /Top score/)
  const missing = render(React.createElement(PlatformScoreRow, { platform: platform('croma', null), rank: null }))
  assert.doesNotMatch(missing, /role="meter"/)
  assert.match(missing, /Insufficient data for this exact product/)
})

test('recent predictions: empty state, then rows linking to the saved result', () => {
  assert.match(render(React.createElement(RecentPredictionsTable, { history: { total: 0, items: [] }, error: '', onRetry() {} })), /No saved predictions yet/)
  const history = { total: 1, items: [{ id: 7, product: 'Nova Buds Air', recommended_platform: 'amazon', top_score: 55.1, model_version: 'v5', source_types: ['demo'], created_at: '2026-09-01T00:00:00Z', model: { quality_status: 'below_baseline' }, warning: 'w' }] }
  const html = render(React.createElement(RecentPredictionsTable, { history, error: '', onRetry() {} }))
  assert.match(html, /<table/)
  assert.match(html, /#7/)
  assert.match(html, /Below baseline/)
  assert.match(html, />DEMO</)
  assert.match(render(React.createElement(RecentPredictionsTable, { history: null, error: 'Could not reach the API', onRetry() {} })), /Could not reach the API/)
})

test('latest recommendation keeps warnings visible and uses score terminology', () => {
  const result = {
    id: 9, product: 'Nova Buds Air', product_key: 'nova', created_at: '2026-09-01T00:00:00Z', recommended_platform: 'amazon',
    recommendation_label: 'Highest experimental opportunity score', ranking: [platform('amazon', 70)], platform_results: [platform('amazon', 70)],
    score_difference: null, key_factors: [], model: { below_baseline: true, quality_status: 'below_baseline', accuracy: 0.333, majority_baseline: 0.406, source_types: ['demo'], warning: 'w' },
    data_provenance: { dataset_id: 'ds', source_types: ['demo'], model_source_types: ['demo'] }, formula: { version: 'f1', weights: { price_competitiveness: 25, rating: 10 }, explanations: {}, missing_policy: '' }, warning: 'DEMO-derived result',
  }
  const html = render(React.createElement(RecommendationCard, { result, loading: false, error: '', empty: false, onRetry() {} }))
  assert.match(html, /Highest experimental opportunity score/)
  assert.match(html, /does not outperform the validation baseline/)
  assert.match(html, /DEMO-derived result/)
  assert.match(html, /not a demand, revenue or success probability/)
  assert.match(html, /20.0 \/ 25 pts/)
  assert.match(html, /Prediction #9/)
})

test('chart exposes a text alternative and legend without interpolating gaps', () => {
  const series = [{ key: 'a', platform: 'amazon', label: 'Amazon · DEMO · INR', sourceType: 'demo', currency: 'INR', points: [{ timestamp: '2026-09-01T00:00:00', value: 10 }, { timestamp: '2026-09-02T00:00:00', value: null }, { timestamp: '2026-09-03T00:00:00', value: 12 }] }]
  const html = render(React.createElement(MultiSeriesChart, { series, metricLabel: 'Observed price', unit: 'INR', format: String }))
  assert.match(html, /role="img"/)
  assert.match(html, /2 recorded values/)
  assert.equal((html.match(/<path /g) ?? []).length, 2, 'a missing reading splits the line into two segments')
  assert.match(html, /Amazon · DEMO · INR/)
})
