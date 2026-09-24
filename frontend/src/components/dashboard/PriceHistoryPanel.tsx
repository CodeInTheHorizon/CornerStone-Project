/**
 * Overview trend panel: stored listing histories for one product, one metric
 * at a time, filtered by platform. Reads GET /analytics/options and
 * GET /analytics/trends; nothing is aggregated across currencies or listings.
 */

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { SourceBadge } from '@/components/SourceBadge'
import { MultiSeriesChart } from '@/components/dashboard/MultiSeriesChart'
import { SectionCard } from '@/components/dashboard/SectionCard'
import { EmptyState, ErrorState, SkeletonBlock } from '@/components/dashboard/StateViews'
import { useAuth } from '@/hooks/useAuth'
import { chartSeries, seriesCurrencies, type ChartMetric } from '@/lib/dashboardInsights'
import { PLATFORM_KEYS } from '@/lib/platforms'
import { timestamp, title } from '@/lib/predictionFormat'
import * as analytics from '@/services/analyticsService'
import type { AnalyticsOptions, TrendsResponse } from '@/types/analytics'

const metrics: { id: ChartMetric; label: string; unit: (currency: string | null) => string }[] = [
  { id: 'price', label: 'Observed price', unit: (currency) => currency ?? 'price' },
  { id: 'discount', label: 'Discount', unit: () => '%' },
  { id: 'rating', label: 'Rating', unit: () => '0–5' },
]

type TimeRange = '7d' | '30d' | '90d' | 'all'
const timeRanges: { id: TimeRange; label: string; days: number | null }[] = [
  { id: '7d', label: '7 days', days: 7 },
  { id: '30d', label: '30 days', days: 30 },
  { id: '90d', label: '90 days', days: 90 },
  { id: 'all', label: 'All', days: null },
]

const control = 'w-full min-w-0 rounded-card border border-border-hair bg-surface px-3 py-2 text-sm text-foreground transition-colors duration-200 focus:border-accent'

export function PriceHistoryPanel({ preferredProductKey }: { preferredProductKey: string | null }) {
  const { token } = useAuth()
  const [options, setOptions] = useState<AnalyticsOptions | null>(null)
  const [optionsError, setOptionsError] = useState('')
  const [chosenProduct, setChosenProduct] = useState<string | null>(null)
  const [platform, setPlatform] = useState('')
  const [metric, setMetric] = useState<ChartMetric>('price')
  const [chosenCurrency, setChosenCurrency] = useState<string | null>(null)
  const [trends, setTrends] = useState<TrendsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [timeRange, setTimeRange] = useState<TimeRange>('all')

  useEffect(() => {
    if (!token) return
    let cancelled = false
    analytics.fetchAnalyticsOptions(token, {})
      .then((data) => { if (!cancelled) { setOptions(data); setOptionsError('') } })
      .catch((err: unknown) => { if (!cancelled) { setOptions(null); setOptionsError(err instanceof Error ? err.message : 'Could not load stored products.') } })
    return () => { cancelled = true }
  }, [token, revision])

  // The latest prediction's product is the default, when it is still stored.
  const productKey = chosenProduct
    ?? (preferredProductKey && options?.products.some((item) => item.product_key === preferredProductKey) ? preferredProductKey : null)
    ?? options?.products[0]?.product_key
    ?? ''

  useEffect(() => {
    if (!token || !productKey) return
    let cancelled = false
    async function load() {
      setLoading(true); setError('')
      try {
        const response = await analytics.fetchTrends(token!, { product_key: productKey, platform: platform || undefined })
        if (!cancelled) setTrends(response)
      } catch (err) {
        if (!cancelled) { setTrends(null); setError(err instanceof Error ? err.message : 'Analytics request failed.') }
      } finally { if (!cancelled) setLoading(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [token, productKey, platform, revision])

  const currencies = useMemo(() => seriesCurrencies(trends?.series ?? []), [trends])
  const currency = chosenCurrency && currencies.includes(chosenCurrency) ? chosenCurrency : currencies[0] ?? null
  const allLines = useMemo(() => chartSeries(trends?.series ?? [], metric, currency), [trends, metric, currency])
  const lines = useMemo(() => {
    const range = timeRanges.find((r) => r.id === timeRange)
    if (!range?.days) return allLines
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - range.days)
    const cutoffISO = cutoff.toISOString()
    return allLines.map((line) => ({
      ...line,
      points: line.points.filter((p) => p.timestamp >= cutoffISO),
    })).filter((line) => line.points.length > 0)
  }, [allLines, timeRange])
  const selectedMetric = metrics.find((item) => item.id === metric)!
  const productName = options?.products.find((item) => item.product_key === productKey)?.product_name ?? productKey.split('|')[0]
  const format = (value: number) => metric === 'discount' ? `${value.toFixed(0)}%` : metric === 'rating' ? value.toFixed(1) : value.toLocaleString(undefined, { maximumFractionDigits: 0 })

  return (
    <SectionCard
      title="Stored observation history"
      description={productKey ? <>Listing histories for <strong className="font-medium text-foreground">{productName}</strong>. Each line is one stored listing; sources and currencies stay separate.</> : 'Listing histories from stored snapshots.'}
      actions={productKey ? <Link to={`/dashboard/trends?product_key=${encodeURIComponent(productKey)}`} className="text-sm font-medium text-accent-text hover:underline">Full trend analysis</Link> : undefined}
      className="h-full"
    >
      {optionsError ? <ErrorState message={optionsError} onRetry={() => setRevision((value) => value + 1)} /> : !options ? (
        <SkeletonBlock label="Loading stored products" lines={2} />
      ) : options.products.length === 0 ? (
        <EmptyState icon="database" title="No stored products yet">Collect, import or load demo data to see observation histories.</EmptyState>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <label className="min-w-0 text-xs font-medium text-muted">
              Chart product
              <select className={`${control} mt-1.5`} value={productKey} onChange={(event) => { setChosenProduct(event.target.value); setChosenCurrency(null) }}>
                {options.products.map((item) => <option key={item.product_key} value={item.product_key}>{item.product_name} · {item.category}</option>)}
              </select>
            </label>
            <label className="min-w-0 text-xs font-medium text-muted">
              Chart platform
              <select className={`${control} mt-1.5`} value={platform} onChange={(event) => setPlatform(event.target.value)}>
                <option value="">All platforms</option>
                {PLATFORM_KEYS.map((key) => <option key={key} value={key}>{title(key)}</option>)}
              </select>
            </label>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div role="group" aria-label="Chart metric" className="inline-flex rounded-card border border-border-hair bg-background-alt p-0.5">
              {metrics.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={metric === item.id}
                  onClick={() => setMetric(item.id)}
                  className={`rounded-[9px] px-3 py-1.5 text-xs font-medium transition-colors duration-200 ease-standard ${metric === item.id ? 'bg-surface text-foreground shadow-card' : 'text-muted hover:text-foreground'}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div role="group" aria-label="Time range" className="inline-flex rounded-card border border-border-hair bg-background-alt p-0.5">
                {timeRanges.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={timeRange === item.id}
                    onClick={() => setTimeRange(item.id)}
                    className={`rounded-[9px] px-2.5 py-1.5 text-xs font-medium transition-colors duration-200 ease-standard ${timeRange === item.id ? 'bg-surface text-foreground shadow-card' : 'text-muted hover:text-foreground'}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              {metric === 'price' && currencies.length > 1 && (
                <label className="flex items-center gap-2 text-xs font-medium text-muted">
                  Currency
                  <select className="rounded-card border border-border-hair bg-surface px-2 py-1.5 text-sm text-foreground" value={currency ?? ''} onChange={(event) => setChosenCurrency(event.target.value)}>
                    {currencies.map((item) => <option key={item}>{item}</option>)}
                  </select>
                </label>
              )}
            </div>
          </div>

          <div className="mt-4 min-h-[21rem]" aria-busy={loading}>
            {error ? <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} /> : loading || !trends ? (
              <div role="status" aria-label="Loading observation history" className="space-y-3">
                <div className="skeleton h-12" />
                <div className="skeleton h-60" />
              </div>
            ) : lines.length === 0 ? (
              <EmptyState icon="chart" title="No recorded values for this selection">{trends.reason ?? `No ${selectedMetric.label.toLowerCase()} readings are stored for this product${platform ? ` on ${title(platform)}` : ''}.`}</EmptyState>
            ) : (
              <>
                <MultiSeriesChart series={lines} metricLabel={`${selectedMetric.label} for ${productName}`} unit={selectedMetric.unit(currency)} format={format} />
                <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border-hair pt-3 text-xs text-subtle">
                  {trends.provenance.source_types.map((source) => <SourceBadge key={source} kind={source} />)}
                  <span>{trends.provenance.observation_count} observations · {timestamp(trends.provenance.date_range.start)} – {timestamp(trends.provenance.date_range.end)}</span>
                  {trends.total_series > trends.series.length && <span>· showing {trends.series.length} of {trends.total_series} listing histories</span>}
                </div>
              </>
            )}
          </div>
        </>
      )}
    </SectionCard>
  )
}
