import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Download } from 'lucide-react'
import { Button } from '@/components/Button'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { Panel } from '@/components/Panel'
import { SourceBadge } from '@/components/SourceBadge'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { MarketDataRefresh } from '@/components/dashboard/MarketDataRefresh'
import { ObservedLineChart } from '@/components/dashboard/ObservedLineChart'
import { PlatformBadge } from '@/components/dashboard/PlatformBadge'
import { QualityContext } from '@/components/dashboard/PredictionResults'
import { Icon } from '@/components/Icon'
import { exportCSV, exportJSON } from '@/lib/export'
import { PLATFORM_KEYS } from '@/lib/platforms'
import { useAuth } from '@/hooks/useAuth'
import { timestamp, title } from '@/lib/predictionFormat'
import * as service from '@/services/analyticsService'
import type { AnalyticsFilters, AnalyticsOptions, AnalyticsSummary, ComparisonResponse, TrendMetric, TrendsResponse } from '@/types/analytics'

const number = (value: number | null | undefined, unit = '') => value == null ? 'Unavailable' : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit}`
const stock = (value: number | null) => value === 1 ? 'In stock' : value === 0 ? 'Out of stock' : 'Unknown'
const control = 'mt-2 w-full rounded-card border border-border-hair bg-background px-3 py-2.5 text-sm text-foreground transition-colors duration-200 focus:border-accent'

function MetricSummary({ label, metric, unit = '', changeUnit = unit }: { label: string; metric: TrendMetric; unit?: string; changeUnit?: string }) {
  return <div className="rounded-card border border-border-hair bg-background-alt/50 p-3 text-xs leading-relaxed text-muted">
    <strong>{label}</strong>: latest {number(metric.latest, unit)} · first {number(metric.first, unit)} · change {number(metric.absolute_change, changeUnit)} ({number(metric.percentage_change, '%')}) · {metric.direction ?? 'Direction unavailable'}
    <p>Average {number(metric.average, unit)} · min {number(metric.min, unit)} · max {number(metric.max, unit)} · {metric.valid_observations} valid readings</p>
    {metric.reason && <p className="mt-1">{metric.reason}</p>}
  </div>
}

export function AnalyticsPage({ mode }: { mode: 'trends' | 'comparison' }) {
  const { token } = useAuth()
  const [params] = useSearchParams()
  const [filters, setFilters] = useState<AnalyticsFilters>({ product_key: params.get('product_key') ?? '' })
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState<AnalyticsOptions | null>(null)
  const [optionOffset, setOptionOffset] = useState(0)
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [trends, setTrends] = useState<TrendsResponse | null>(null)
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [optionError, setOptionError] = useState('')
  const [summaryError, setSummaryError] = useState('')

  function update(name: keyof AnalyticsFilters, value: string) {
    setFilters((previous) => ({ ...previous, [name]: value }))
    setOffset(0); setOptionOffset(0); setTrends(null); setComparison(null)
  }
  useEffect(() => {
    if (!token) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      setOptionError('')
      const { product_key: _product, ...scope } = filters
      service.fetchAnalyticsOptions(token, scope, query, optionOffset)
        .then((data) => { if (!cancelled) setOptions(data) })
        .catch((err: unknown) => { if (!cancelled) { setOptions(null); setOptionError(err instanceof Error ? err.message : 'Could not load stored products.') } })
    }, 200)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [token, filters, query, optionOffset, revision])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    service.fetchAnalyticsSummary(token).then((data) => { if (!cancelled) { setSummary(data); setSummaryError('') } }).catch((err: unknown) => { if (!cancelled) { setSummary(null); setSummaryError(err instanceof Error ? err.message : 'Summary unavailable.') } })
    return () => { cancelled = true }
  }, [token, revision])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    async function load() {
      setError(''); setTrends(null); setComparison(null)
      if (!filters.product_key && !filters.category) { setLoading(false); return }
      setLoading(true)
      try {
        if (mode === 'trends') {
          const response = await service.fetchTrends(token!, filters, offset)
          if (!cancelled) setTrends(response)
        } else {
          const response = await service.fetchComparison(token!, filters)
          if (!cancelled) setComparison(response)
        }
      } catch (err) { if (!cancelled) setError(err instanceof Error ? err.message : 'Analytics request failed.') }
      finally { if (!cancelled) setLoading(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [token, filters, mode, offset, revision])
  const response = mode === 'trends' ? trends : comparison
  const selectedInOptions = options?.products.some((item) => item.product_key === filters.product_key)
  // The selected product becomes the default LIVE refresh keyword.
  const selectedProductName = filters.product_key
    ? options?.products.find((item) => item.product_key === filters.product_key)?.product_name ?? filters.product_key.split('|')[0]
    : undefined

  return <DashboardLayout title={mode === 'trends' ? 'Trend Analysis' : 'Analytics'}>
    <div className="space-y-6">
      <Panel>
        <h2 className="text-xl font-semibold tracking-tight">{mode === 'trends' ? 'Trends in stored observations' : 'Compare observed marketplace signals'}</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">These calculations read snapshot history. DEMO is synthetic, IMPORTED is operator-supplied, and LIVE describes collection provenance. None of these labels guarantees current data or actual sales demand.</p>
        <div className="mt-5 grid gap-4 rounded-card border border-border-hair bg-background-alt/40 p-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Search product / brand" name="analytics-search" value={query} onChange={(value) => { setQuery(value); setOptionOffset(0) }} />
          <label className="text-sm text-muted">Product<select className={control} value={filters.product_key ?? ''} onChange={(event) => update('product_key', event.target.value)}><option value="">All products in selected category</option>{filters.product_key && !selectedInOptions && <option value={filters.product_key}>{filters.product_key.split('|')[0]} (selected)</option>}{options?.products.map((item) => <option key={item.product_key} value={item.product_key}>{item.product_name} · {item.category}</option>)}</select></label>
          <label className="text-sm text-muted">Category<select className={control} value={filters.category ?? ''} onChange={(event) => { update('category', event.target.value); update('product_key', '') }}><option value="">All categories</option>{filters.category && !options?.categories.includes(filters.category) && <option>{filters.category}</option>}{options?.categories.map((category) => <option key={category}>{category}</option>)}</select></label>
          <label className="text-sm text-muted">Platform<select className={control} value={filters.platform ?? ''} onChange={(event) => update('platform', event.target.value)}><option value="">All platforms</option>{PLATFORM_KEYS.map((platform) => <option key={platform} value={platform}>{title(platform)}</option>)}</select></label>
          <label className="text-sm text-muted">Data source<select className={control} value={filters.source_type ?? ''} onChange={(event) => update('source_type', event.target.value)}><option value="">All sources (kept separate)</option>{['demo', 'imported', 'live'].map((source) => <option key={source} value={source}>{source.toUpperCase()}</option>)}</select></label>
          <div className="grid grid-cols-2 gap-3"><Field label="From (UTC)" name="start-date" type="date" value={filters.start_date ?? ''} onChange={(value) => update('start_date', value)} /><Field label="Through (UTC)" name="end-date" type="date" value={filters.end_date ?? ''} onChange={(value) => update('end_date', value)} /></div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-subtle"><span>{options ? `${options.total} matching products` : 'Loading stored products…'}</span>{optionOffset > 0 && <Button variant="ghost" size="sm" onClick={() => setOptionOffset(Math.max(0, optionOffset - 50))}>Previous products</Button>}{options && optionOffset + 50 < options.total && <Button variant="ghost" size="sm" onClick={() => setOptionOffset(optionOffset + 50)}>More products</Button>}</div>
        {optionError && <div className="mt-3"><FormAlert>{optionError}</FormAlert></div>}
      </Panel>

      {error && <FormAlert>{error}</FormAlert>}
      {loading && <p role="status" className="text-sm text-muted">Calculating stored history…</p>}
      {!filters.product_key && !filters.category && <Panel className="flex items-center gap-3 border-dashed"><Icon name="chart" className="size-5 shrink-0 text-muted" /><p className="text-sm text-muted">Select a product for like-for-like histories, or a category for explicitly grouped summaries.</p></Panel>}
      {response && !loading && <Panel>
        <div className="flex flex-wrap items-center gap-2">{response.provenance.source_types.map((source) => <SourceBadge key={source} kind={source} />)}<span className="text-sm text-muted">{response.provenance.observation_count} observations · {response.provenance.duplicates_removed} duplicates removed</span></div>
        <p className="mt-3 text-sm text-muted">Observed {timestamp(response.provenance.date_range.start)} through {timestamp(response.provenance.date_range.end)}</p>
        <p className="mt-2 text-xs text-subtle">{response.provenance.notice}</p>
        {response.reason && <p className="mt-3 text-sm text-signal-warn">{response.reason}</p>}
        <div className="mt-3 flex gap-2">
          <button onClick={() => exportJSON(response, `analytics-${mode}`)} className="inline-flex items-center gap-1.5 rounded-full border border-border-hair px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-accent hover:text-accent-text">
            <Download className="size-3" />Export JSON
          </button>
          {trends && <button onClick={() => {
            const rows = trends.series.flatMap((s) => s.points.map((p) => ({ product: s.product_name, platform: s.platform, source: s.source_type, timestamp: p.timestamp, price: p.price, discount: p.discount, rating: p.rating, reviews: p.reviews })))
            exportCSV(rows, 'trend-data')
          }} className="inline-flex items-center gap-1.5 rounded-full border border-border-hair px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-accent hover:text-accent-text">
            <Download className="size-3" />Export CSV
          </button>}
        </div>
      </Panel>}

      {trends && !loading && <>
        <p className="text-xs leading-relaxed text-muted">{trends.calculation_policy}</p>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted"><span>Showing {trends.series.length} of {trends.total_series} separate listing histories</span>{offset > 0 && <Button size="sm" variant="ghost" onClick={() => setOffset(Math.max(0, offset - 20))}>Previous histories</Button>}{offset + 20 < trends.total_series && <Button size="sm" variant="ghost" onClick={() => setOffset(offset + 20)}>More histories</Button>}</div>
        {trends.series.map((item, index) => <Panel key={`${item.product_key}-${item.platform}-${item.source_type}-${item.currency}-${item.listing_key}`}>
          <details open={index === 0}>
            <summary className="cursor-pointer text-sm font-semibold">{item.product_name} · <PlatformBadge platform={item.platform} /> · {item.currency} · {item.observation_count} observations <SourceBadge kind={item.source_type} /></summary>
            <p className="mt-3 text-xs text-subtle">Listing: {item.listing_key} · latest observation {timestamp(item.date_range.end)}</p>
            {item.reason && <p className="mt-3 text-sm text-signal-warn">{item.reason}</p>}
            <div className="mt-4 grid gap-4 xl:grid-cols-2"><ObservedLineChart points={item.points} field="price" label="Price" unit={item.currency} /><ObservedLineChart points={item.points} field="discount" label="Discount" unit="%" /><ObservedLineChart points={item.points} field="rating" label="Rating" unit="0–5" /><ObservedLineChart points={item.points} field="reviews" label="Review count" unit="reviews" /></div>
            {item.points.some((point) => point.discount_derived) && <p className="mt-3 text-xs text-subtle">Some discounts were calculated from the recorded selling and original prices because the discount field was missing.</p>}
            <div className="mt-4 grid gap-3 lg:grid-cols-2"><MetricSummary label="Price" metric={item.price} /><MetricSummary label="Discount" metric={item.discount} unit="%" changeUnit=" pp" /><MetricSummary label="Rating" metric={item.rating} /><MetricSummary label="Reviews" metric={item.reviews} /></div>
            <p className="mt-3 text-sm text-muted">Review momentum: {number(item.reviews.momentum_per_day)} reviews/day. Negative changes can reflect review removal, not falling sales.</p>
            <p className="mt-3 text-sm text-muted">Latest availability: <strong>{stock(item.availability.latest)}</strong> · observed changes: {number(item.availability.changes)}</p>
            <p className="mt-2 text-xs text-subtle">{item.availability.reason ?? item.availability.notice}</p>
            {item.availability.events.map((event) => <p key={event.observed_at} className="mt-1 text-xs text-muted">{stock(event.from)} → {stock(event.to)}, observed between {timestamp(event.previous_observation)} and {timestamp(event.observed_at)}</p>)}
            <details className="mt-4"><summary className="cursor-pointer text-sm text-accent-text">Observation values (accessible table)</summary><div className="mt-3 overflow-x-auto" role="region" aria-label={`Observation values for ${item.product_name} on ${title(item.platform)}, scroll horizontally on small screens`} tabIndex={0}><table className="w-full text-left text-xs"><caption className="sr-only">Stored values for {item.product_name} on {item.platform}</caption><thead><tr>{['Observed (UTC)', 'Price', 'Discount %', 'Rating', 'Reviews', 'Availability'].map((label) => <th key={label} className="p-2">{label}</th>)}</tr></thead><tbody>{item.points.map((point) => <tr key={point.timestamp} className="border-t border-border-hair"><td className="whitespace-nowrap p-2">{point.timestamp}</td><td className="p-2">{number(point.price)}</td><td className="p-2">{number(point.discount)}</td><td className="p-2">{number(point.rating)}</td><td className="p-2">{number(point.reviews)}</td><td className="p-2">{stock(point.availability)}</td></tr>)}</tbody></table></div></details>
          </details>
        </Panel>)}
      </>}

      {comparison && !loading && comparison.groups.map((group) => <Panel key={`${group.identity}-${group.source_type}-${group.currency}`}>
        <h3 className="font-semibold">{group.grouping === 'category_aggregate' ? 'Category aggregate' : 'Exact product'}: {group.identity.split('|')[0]} · {group.currency}</h3>
        <div className="mt-2"><SourceBadge kind={group.source_type} /></div>
        <p className="mt-3 text-xs leading-relaxed text-muted">{group.notice}</p>
        {group.reason && <p className="mt-3 text-sm text-signal-warn">{group.reason}</p>}
        <div className="mt-4 grid gap-4 md:grid-cols-2">{group.platforms.map((platform) => <div key={platform.platform} className="rounded-card border border-border-hair bg-background-alt/40 p-4">
          <h4 className="font-medium"><PlatformBadge platform={platform.platform} /></h4>
          {platform.reason && <p className="mt-2 text-sm text-muted">{platform.reason}</p>}
          <dl className="mt-3 space-y-2 text-sm text-muted">{[
            ['Average price', number(platform.average_price)], ['Latest price / listing mean', number(platform.latest_price)], ['Average discount', number(platform.average_discount, '%')], ['Average rating', number(platform.average_rating)], ['Mean review change', number(platform.review_growth)], ['Mean review growth', number(platform.review_growth_percentage, '%')], ['Observed listings', String(platform.listing_count)], ['Share of sampled listings', number(platform.listing_density * 100, '%')],
          ].map(([label, value]) => <div key={label} className="flex justify-between gap-3"><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
          <p className="mt-3 text-xs text-subtle">Latest observation: {timestamp(platform.latest_observation)}. Latest prices available for {platform.latest_price_listing_count}/{platform.listing_count} listings; review growth for {platform.review_growth_listing_count}/{platform.listing_count}.</p>
          {platform.earliest_latest_observation !== platform.latest_observation && <p className="mt-2 text-xs text-subtle">Individual latest readings range from {timestamp(platform.earliest_latest_observation)} to {timestamp(platform.latest_observation)}.</p>}
          {platform.opportunity ? <div className="mt-4 space-y-3"><p className="text-sm font-medium">Saved Phase 7 score: {number(platform.opportunity.score)} / 100 · {platform.opportunity.model_version}</p><QualityContext model={platform.opportunity.model} /><p className="text-xs text-muted">{platform.opportunity.notice} Saved {timestamp(platform.opportunity.created_at)}.</p><p className="text-xs text-signal-warn">{platform.opportunity.warning}</p></div> : <p className="mt-4 text-xs text-subtle">Opportunity Score unavailable. {platform.opportunity_reason}</p>}
        </div>)}</div>
      </Panel>)}

      <Panel><h3 className="font-semibold">Data refresh</h3><p className="mt-1 mb-4 text-sm text-muted">LIVE refresh runs only when a collector is configured and approved.</p>{summaryError && <div className="mb-3"><FormAlert>{summaryError}</FormAlert></div>}<MarketDataRefresh key={filters.product_key ?? ''} sources={summary?.refresh_sources ?? null} selectedProduct={selectedProductName} onRefresh={() => setRevision((value) => value + 1)} /></Panel>
    </div>
  </DashboardLayout>
}
