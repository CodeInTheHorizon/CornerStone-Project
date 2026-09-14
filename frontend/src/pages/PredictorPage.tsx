import { PermissionGate } from '@/components/PermissionGate'
import { can } from '@/auth/permissions'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/Button'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { Panel } from '@/components/Panel'
import { SourceBadge } from '@/components/SourceBadge'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { PredictionResults } from '@/components/dashboard/PredictionResults'
import { percent, timestamp, title } from '@/lib/predictionFormat'
import { useAuth } from '@/hooks/useAuth'
import { ApiRequestError } from '@/services/apiClient'
import * as service from '@/services/predictionService'
import type { PlatformPrediction, PredictionHistory, PredictionOptions, PredictionResult } from '@/types/prediction'

const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'The request could not be completed.'

export function PredictorPage() {
  const { token, user } = useAuth()
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
  const [busy, setBusy] = useState(false)
  const resultRef = useRef<HTMLDivElement>(null)
  const product = options?.products.find((item) => item.product_key === selected)

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

  async function predict() {
    if (!can(user, "prediction:run") || !token || !options || !selected || busy) return
    setBusy(true); setError(''); setFailedPlatforms([]); setResult(null)
    try {
      const prediction = await service.makePrediction(token, selected, options.dataset_id)
      setResult(prediction)
      setHistoryError('')
      try { setHistory(await service.fetchPredictionHistory(token)) }
      catch (err) { setHistoryError(errorMessage(err)) }
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
    <DashboardLayout title="MarketPulse AI — ML Predictor">
      <div className="space-y-6">
        <Panel>
          <h2 className="text-2xl font-semibold">Compare observed marketplace opportunities</h2>
          <p className="mt-3 text-sm leading-relaxed text-muted">Choose an electronics accessory from a prepared dataset. We use its latest recorded features for each available platform, including historical context.</p>
          <div className="mt-4"><FormAlert tone="info">Experimental pipeline demonstration. DEMO-derived results are synthetic; a below-baseline model cannot provide reliable marketplace recommendations. Every result includes measured model quality and the baseline. This does not predict actual sales demand.</FormAlert></div>
          <div className="mt-5"><Field label="Find a stored product, brand, or category" name="product-search" value={query} onChange={(value) => { setQuery(value); setOffset(0); setSelected(''); setLoadingOptions(true) }} placeholder="e.g. earbuds or Nova" /></div>
          {loadingOptions && <p role="status" className="mt-4 text-sm text-muted">Loading stored products…</p>}
          {optionsError && <div className="mt-4"><FormAlert>{optionsError}</FormAlert>{can(user, "dataset:build") && <Link to="/dashboard/train" className="mt-3 inline-block text-sm text-accent-text">Prepare a dataset</Link>}</div>}
          {!loadingOptions && options && (
            <>
              <label htmlFor="prediction-product" className="mt-5 block text-sm font-medium text-muted">Product / accessory</label>
              <select id="prediction-product" value={selected} onChange={(event) => setSelected(event.target.value)} disabled={busy} className="mt-2 w-full rounded-card border border-border-hair bg-background px-3.5 py-2.5 text-sm text-foreground focus:border-accent">
                <option value="">Select a product</option>
                {options.products.map((item) => <option key={item.product_key} value={item.product_key}>{item.product_name} — {item.category} ({item.platforms.length} platforms)</option>)}
              </select>
              {options.products.length === 0 && <p className="mt-3 text-sm text-muted">No matching electronics products. Change the search, or collect/import data and build a dataset.</p>}
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
                <span>{options.total} matching products · Dataset prepared {timestamp(options.generated_at)}</span>
                {offset > 0 && <Button size="sm" variant="ghost" onClick={() => { setOffset(Math.max(0, offset - 50)); setSelected(''); setLoadingOptions(true) }}>Previous</Button>}
                {offset + 50 < options.total && <Button size="sm" variant="ghost" onClick={() => { setOffset(offset + 50); setSelected(''); setLoadingOptions(true) }}>More products</Button>}
              </div>
            </>
          )}
          {product && !loadingOptions && (
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {['amazon', 'flipkart', 'croma', 'alibaba'].map((platform) => {
                const row = product.platforms.find((entry) => entry.platform === platform)
                return <div key={platform} className="rounded-card border border-border-hair p-4 text-sm">
                  <div className="flex justify-between gap-2"><strong>{title(platform)}</strong><SourceBadge kind={row?.source_type ?? 'unavailable'} /></div>
                  {row ? <><p className="mt-2 text-muted">{row.currency} {row.effective_price?.toLocaleString() ?? 'Unknown price'} · Rating {row.rating ?? 'unknown'} · {row.review_count?.toLocaleString() ?? 'Unknown'} reviews</p><p className="mt-2 text-xs text-subtle">Observed {timestamp(row.data_freshness)}{row.stale ? ' · STALE' : ''}</p></> : <p className="mt-2 text-muted">Insufficient data for this exact product.</p>}
                </div>
              })}
            </div>
          )}
          <PermissionGate permission="prediction:run"><Button className="mt-5" disabled={!product || loadingOptions || busy} onClick={() => void predict()}>{busy ? 'Working…' : 'Make Prediction'}</Button></PermissionGate>
        </Panel>
        <div ref={resultRef} aria-live="polite" aria-busy={busy} className="scroll-mt-6 space-y-4">
          {error && <FormAlert>{error}</FormAlert>}
          {failedPlatforms.map((platform) => <Panel key={platform.platform}><p className="text-sm">{title(platform.platform)}: {platform.reason}</p><p className="mt-2 text-xs text-signal-warn">{platform.warning}</p></Panel>)}
          {result && <PredictionResults result={result} />}
        </div>
        <Panel>
          <h2 className="text-lg font-semibold">Your recent predictions</h2>
          {historyError && <div className="mt-3"><FormAlert>{historyError}</FormAlert></div>}
          {!history && !historyError && <p className="mt-3 text-sm text-muted">Loading history…</p>}
          {history?.total === 0 && <p className="mt-3 text-sm text-muted">No saved predictions yet.</p>}
          {history && history.total > 0 && <p className="mt-2 text-xs text-subtle">Showing the latest {history.items.length} of {history.total}. Each entry retains the model quality measured when it was made.</p>}
          <ul className="mt-4 space-y-4">
            {history?.items.map((item) => <li key={item.id} className="rounded-card border border-border-hair p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="font-medium">{item.product}</p><p className="mt-1 text-sm text-muted">{title(item.recommended_platform ?? 'Unavailable')} · {item.top_score?.toFixed(1) ?? '—'} / 100 · {item.model_version}</p></div>
                <Button variant="secondary" size="sm" disabled={busy} onClick={() => void openHistory(item.id)}>View result #{item.id}</Button>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">{timestamp(item.created_at)} {item.source_types.map((source) => <SourceBadge key={source} kind={source} />)}</div>
              <p className="mt-3 text-xs leading-relaxed text-signal-warn">{item.warning}</p>
              <p className="mt-2 text-xs text-muted">Validation accuracy {percent(item.model?.accuracy)} vs majority baseline accuracy {percent(item.model?.majority_baseline)} · Weighted F1 {percent(item.model?.primary_metric_value)}</p>
            </li>)}
          </ul>
        </Panel>
      </div>
    </DashboardLayout>
  )
}
