import { PermissionGate } from '@/components/PermissionGate'
import { can } from '@/auth/permissions'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/Button'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { Panel } from '@/components/Panel'
import { SourceBadge } from '@/components/SourceBadge'
import { StatusPill } from '@/components/StatusPill'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { PlatformBadge } from '@/components/dashboard/PlatformBadge'
import { PredictionResults } from '@/components/dashboard/PredictionResults'
import { SkeletonBlock } from '@/components/dashboard/StateViews'
import { qualityPresentation } from '@/lib/modelQuality'
import { PLATFORM_KEYS } from '@/lib/platforms'
import { percent, timestamp, title } from '@/lib/predictionFormat'
import { useAuth } from '@/hooks/useAuth'
import { ApiRequestError } from '@/services/apiClient'
import * as service from '@/services/predictionService'
import * as demandService from '@/services/demandService'
import type { QualityStatus } from '@/types/data'
import type { PlatformPrediction, PredictionHistory, PredictionOptions, PredictionResult } from '@/types/prediction'

const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'The request could not be completed.'

function Step({ number, title: heading, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <div className="relative pl-10">
      <span aria-hidden="true" className="absolute top-0 left-0 grid size-7 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-text">{number}</span>
      <h3 className="pt-0.5 text-sm font-semibold"><span className="sr-only">Step {number}: </span>{heading}</h3>
      <div className="mt-3">{children}</div>
    </div>
  )
}

export function PredictorPage() {
  const { token, user } = useAuth()
  const [params] = useSearchParams()
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [options, setOptions] = useState<PredictionOptions | null>(null)
  const [selected, setSelected] = useState('')
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [optionsError, setOptionsError] = useState('')
  const [result, setResult] = useState<PredictionResult | null>(null)
  const [history, setHistory] = useState<PredictionHistory | null>(null)
  const [historyError, setHistoryError] = useState('')
  const [error, setError] = useState('')
  const [failedPlatforms, setFailedPlatforms] = useState<PlatformPrediction[]>([])
  const [demandForecasts, setDemandForecasts] = useState<demandService.ChannelDemandForecast[]>([])
  const [busy, setBusy] = useState(false)
  const resultRef = useRef<HTMLDivElement>(null)
  const product = options?.products.find((item) => item.product_key === selected)
  const linkedPrediction = Number(params.get('prediction'))

  useEffect(() => {
    if (!token) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      setLoadingOptions(true)
      setOptionsError('')
      service.fetchPredictionOptions(token, query, offset)
        .then((data) => {
          if (cancelled) return
          setOptions(data)
          setSelected('')
        })
        .catch((err: unknown) => { if (!cancelled) { setOptions(null); setOptionsError(errorMessage(err)) } })
        .finally(() => { if (!cancelled) setLoadingOptions(false) })
    }, 250)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [token, query, offset])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    service.fetchPredictionHistory(token)
      .then((data) => { if (!cancelled) setHistory(data) })
      .catch((err: unknown) => { if (!cancelled) setHistoryError(errorMessage(err)) })
    return () => { cancelled = true }
  }, [token])

  // Deep link from the overview (?prediction=<id>): open that saved result as saved.
  useEffect(() => {
    if (!token || !Number.isInteger(linkedPrediction) || linkedPrediction <= 0) return
    let cancelled = false
    service.fetchPrediction(token, linkedPrediction)
      .then((data) => {
        if (cancelled) return
        setResult(data)
        window.requestAnimationFrame(() => resultRef.current?.scrollIntoView({ block: 'start' }))
      })
      .catch((err: unknown) => { if (!cancelled) setError(errorMessage(err)) })
    return () => { cancelled = true }
  }, [token, linkedPrediction])

  async function predict() {
    if (!can(user, "prediction:run") || !token || !options || !selected || busy) return
    setBusy(true); setError(''); setFailedPlatforms([]); setResult(null); setDemandForecasts([])
    try {
      const prediction = await service.makePrediction(token, selected, options.dataset_id)
      setResult(prediction)
      setHistoryError('')
      try { setHistory(await service.fetchPredictionHistory(token)) }
      catch (err) { setHistoryError(errorMessage(err)) }

      // Generate Sales Demand Forecasts across platforms for this product
      if (product && product.platforms.length > 0) {
        try {
          const forecasts = await Promise.all(
            product.platforms.map(async (p) => {
              try {
                const res = await demandService.forecastDemand(token, {
                  features: {
                    platform: p.platform,
                    category: product.category,
                    price: p.effective_price ?? 1000,
                    rating: p.rating ?? 4.0,
                    review_count: p.review_count ?? 50,
                    discount_percentage: 15,
                    inventory: 100,
                  },
                })
                return res.forecasts[0]
              } catch {
                return null
              }
            })
          )
          setDemandForecasts(forecasts.filter((f): f is demandService.ChannelDemandForecast => f !== null))
        } catch { /* optional */ }
      }
    } catch (err) {
      setError(errorMessage(err))
      if (err instanceof ApiRequestError && err.detail && typeof err.detail === 'object') {
        const details = err.detail as { platform_results?: PlatformPrediction[] }
        if (Array.isArray(details.platform_results)) setFailedPlatforms(details.platform_results)
      }
    } finally { setBusy(false) }
  }

  async function openHistory(id: number) {
    if (!token || busy) return
    setBusy(true); setError(''); setFailedPlatforms([])
    try {
      setResult(await service.fetchPrediction(token, id))
      resultRef.current?.scrollIntoView({ block: 'start' })
    } catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }

  return (
    <DashboardLayout title="ML Predictor">
      <div className="space-y-6">
        <div className="grid gap-6 xl:grid-cols-12">
          <Panel className="xl:col-span-8">
            <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Compare observed marketplace opportunities</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">Choose an electronics accessory from a prepared dataset. We use its latest recorded features for each available platform, including historical context.</p>
            <div className="mt-4"><FormAlert tone="info">Experimental pipeline demonstration. DEMO-derived results are synthetic; a below-baseline model cannot provide reliable marketplace recommendations. Every result includes measured model quality and the baseline. This does not predict actual sales demand.</FormAlert></div>

            <div className="mt-6 space-y-7">
              <Step number={1} title="Choose a stored product">
                <Field label="Find a stored product, brand, or category" name="product-search" value={query} onChange={(value) => { setQuery(value); setOffset(0); setSelected(''); setLoadingOptions(true) }} placeholder="e.g. earbuds or Nova" />
                {loadingOptions && <p role="status" className="mt-4 text-sm text-muted">Loading stored products…</p>}
                {optionsError && <div className="mt-4"><FormAlert>{optionsError}</FormAlert>{can(user, "dataset:build") && <Link to="/dashboard/train" className="mt-3 inline-block text-sm text-accent-text">Prepare a dataset</Link>}</div>}
                {!loadingOptions && options && (
                  <>
                    <label htmlFor="prediction-product" className="mt-4 block text-sm font-medium text-muted">Product / accessory</label>
                    <select id="prediction-product" aria-required="true" aria-describedby="prediction-product-help" value={selected} onChange={(event) => setSelected(event.target.value)} disabled={busy} className="mt-2 w-full rounded-card border border-border-hair bg-surface px-3.5 py-2.5 text-sm text-foreground transition-colors duration-200 focus:border-accent">
                      <option value="">Select a product</option>
                      {options.products.map((item) => <option key={item.product_key} value={item.product_key}>{item.product_name} — {item.category} ({item.platforms.length} platforms)</option>)}
                    </select>
                    <p id="prediction-product-help" className="mt-1.5 text-xs text-subtle">Required. Lists products in the prepared dataset with their platform coverage.</p>
                    {options.products.length === 0 && <p className="mt-3 text-sm text-muted">No matching electronics products. Change the search, or collect/import data and build a dataset.</p>}
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
                      <span>{options.total} matching products · Dataset prepared {timestamp(options.generated_at)}</span>
                      {options.source_types.map((source) => <SourceBadge key={source} kind={source} />)}
                      {offset > 0 && <Button size="sm" variant="ghost" onClick={() => { setOffset(Math.max(0, offset - 50)); setSelected(''); setLoadingOptions(true) }}>Previous</Button>}
                      {offset + 50 < options.total && <Button size="sm" variant="ghost" onClick={() => { setOffset(offset + 50); setSelected(''); setLoadingOptions(true) }}>More products</Button>}
                    </div>
                  </>
                )}
              </Step>

              <Step number={2} title="Review the stored observations">
                {product && !loadingOptions ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {PLATFORM_KEYS.map((platform) => {
                      const row = product.platforms.find((entry) => entry.platform === platform)
                      return <div key={platform} className="rounded-card border border-border-hair bg-background-alt/50 p-4 text-sm">
                        <div className="flex justify-between gap-2"><strong><PlatformBadge platform={platform} /></strong><SourceBadge kind={row?.source_type ?? 'unavailable'} /></div>
                        {row ? <><p className="mt-2 text-muted"><span className="font-semibold text-foreground">{row.currency} {row.effective_price?.toLocaleString() ?? 'Unknown price'}</span> · Rating {row.rating ?? 'unknown'} · {row.review_count?.toLocaleString() ?? 'Unknown'} reviews</p><p className="mt-2 text-xs text-subtle">Observed {timestamp(row.data_freshness)}{row.stale ? <span className="font-medium text-signal-warn"> · STALE</span> : ''}</p></> : <p className="mt-2 text-muted">Insufficient data for this exact product.</p>}
                      </div>
                    })}
                  </div>
                ) : <p className="text-sm text-subtle">Select a product to see its latest stored observation on each platform.</p>}
              </Step>

              <Step number={3} title="Run the comparison">
                <PermissionGate permission="prediction:run"><Button disabled={!product || loadingOptions || busy} onClick={() => void predict()}>{busy ? 'Working…' : 'Make Prediction'}</Button></PermissionGate>
                <p className="mt-2 text-xs text-subtle">The result is saved with the model quality and data provenance measured at this moment.</p>
              </Step>
            </div>
          </Panel>

          <aside aria-label="How to read results" className="xl:col-span-4">
            <div className="surface-card p-5 sm:p-6 xl:sticky xl:top-24">
              <h2 className="text-base font-semibold">How to read a result</h2>
              <ul className="mt-3 space-y-3 text-sm leading-relaxed text-muted">
                <li><strong className="text-foreground">Opportunity score</strong> is a heuristic 0–100 comparison of recorded price, rating, review, discount, competition and trend signals, plus at most 10 model points.</li>
                <li><strong className="text-foreground">Class probability</strong> is an uncalibrated price-direction model output, not a success likelihood.</li>
                <li><strong className="text-foreground">Model quality</strong> is measured against naive baselines; below-baseline models are flagged on every result.</li>
                <li><strong className="text-foreground">Provenance badges</strong> show whether inputs were LIVE, IMPORTED or synthetic DEMO data.</li>
              </ul>
            </div>
          </aside>
        </div>

        <div ref={resultRef} aria-live="polite" aria-busy={busy} className="scroll-mt-24 space-y-4">
          {error && <FormAlert>{error}</FormAlert>}
          {failedPlatforms.map((platform) => <Panel key={platform.platform}><p className="text-sm">{title(platform.platform)}: {platform.reason}</p><p className="mt-2 text-xs text-signal-warn">{platform.warning}</p></Panel>)}
          {result && <PredictionResults result={result} />}

          {demandForecasts.length > 0 && (
            <div className="surface-card p-6">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-hair pb-4">
                <div>
                  <h3 className="text-base font-semibold">Forecasted Sales Demand (Supervised ML Regression)</h3>
                  <p className="mt-1 text-xs text-muted">Estimated units ordered and monthly gross revenue projections per marketplace channel.</p>
                </div>
                <span className="rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent-text">
                  Regression Model Active
                </span>
              </div>
              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {demandForecasts.map((df) => (
                  <div key={df.platform} className="rounded-card border border-border-hair bg-background-alt/50 p-4">
                    <div className="flex items-center justify-between">
                      <PlatformBadge platform={df.platform} />
                      <span className="text-xs font-medium text-subtle">{df.demand_grade}</span>
                    </div>
                    <div className="mt-3">
                      <p className="text-xs text-muted">Forecasted Sales</p>
                      <p className="text-2xl font-bold text-foreground">{df.predicted_units_sold} <span className="text-xs font-normal text-muted">units</span></p>
                    </div>
                    <div className="mt-2 space-y-1 text-xs text-muted">
                      <div className="flex justify-between">
                        <span>Expected Range:</span>
                        <span className="font-medium text-foreground">{df.forecast_lower_bound} – {df.forecast_upper_bound}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Projected Rev.:</span>
                        <span className="font-semibold text-green-600 dark:text-green-400">₹{df.projected_revenue.toLocaleString()}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="surface-card min-w-0 break-words">
          <div className="flex flex-wrap items-end justify-between gap-2 px-5 pt-5 sm:px-6">
            <div>
              <h2 className="text-lg font-semibold">Your recent predictions</h2>
              {history && history.total > 0 && <p className="mt-1 text-xs text-subtle">Showing the latest {history.items.length} of {history.total}. Each entry retains the model quality measured when it was made.</p>}
            </div>
          </div>
          <div className="px-5 pb-5 sm:px-6 sm:pb-6">
            {historyError && <div className="mt-3"><FormAlert>{historyError}</FormAlert></div>}
            {!history && !historyError && <div className="mt-4"><p className="sr-only">Loading history…</p><SkeletonBlock label="Loading history…" lines={3} /></div>}
            {history?.total === 0 && <p className="mt-3 text-sm text-muted">No saved predictions yet.</p>}
            <ul className="mt-4 divide-y divide-border-hair">
              {history?.items.map((item) => {
                const status = item.model?.quality_status && item.model.quality_status in qualityPresentation ? qualityPresentation[item.model.quality_status as QualityStatus] : null
                return <li key={item.id} className="py-4 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium">{item.product}</p>
                      <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">{item.recommended_platform ? <PlatformBadge platform={item.recommended_platform} /> : 'Unavailable'} <span>· {item.top_score?.toFixed(1) ?? '—'} / 100 · {item.model_version}</span></p>
                    </div>
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => void openHistory(item.id)}>View result #{item.id}</Button>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">{timestamp(item.created_at)} {item.source_types.map((source) => <SourceBadge key={source} kind={source} />)}{status && <StatusPill tone={status.tone}>{status.label}</StatusPill>}</div>
                  <p className="mt-3 text-xs leading-relaxed text-signal-warn">{item.warning}</p>
                  <p className="mt-2 text-xs text-muted">Validation accuracy {percent(item.model?.accuracy)} vs majority baseline accuracy {percent(item.model?.majority_baseline)} · Weighted F1 {percent(item.model?.primary_metric_value)}</p>
                </li>
              })}
            </ul>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
