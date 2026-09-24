import { PermissionGate } from '@/components/PermissionGate'
import { can } from '@/auth/permissions'

import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'

import { ActionCard } from '@/components/dashboard/ActionCard'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { DataQualityPanel } from '@/components/dashboard/DataQualityPanel'
import { DemoDataBanner } from '@/components/dashboard/DemoDataBanner'
import { OnboardingGuide } from '@/components/dashboard/OnboardingGuide'
import { PlatformScoreRow } from '@/components/dashboard/PlatformScoreRow'
import { PriceHistoryPanel } from '@/components/dashboard/PriceHistoryPanel'
import { RecentPredictionsTable } from '@/components/dashboard/RecentPredictionsTable'
import { RecommendationCard } from '@/components/dashboard/RecommendationCard'
import { SectionCard } from '@/components/dashboard/SectionCard'
import { EmptyState, SkeletonBlock } from '@/components/dashboard/StateViews'
import { SummaryCard } from '@/components/dashboard/SummaryCard'
import { Icon } from '@/components/Icon'
import { MarketDataRefresh } from '@/components/dashboard/MarketDataRefresh'
import { SourceBadge } from '@/components/SourceBadge'
import { fetchAnalyticsSummary } from '@/services/analyticsService'
import type { AnalyticsSummary } from '@/types/analytics'
import { useAuth } from '@/hooks/useAuth'
import { useInterval } from '@/hooks/useInterval'
import { attentionItems } from '@/lib/dashboardInsights'
import { qualityPresentation } from '@/lib/modelQuality'
import { PLATFORM_KEYS } from '@/lib/platforms'
import { title } from '@/lib/predictionFormat'
import * as predictionService from '@/services/predictionService'
import * as trainingService from '@/services/trainingService'
import type { ModelStatus } from '@/types/data'
import type { PredictionHistory, PredictionResult } from '@/types/prediction'

function formatTimestamp(value: string | null): string {
  if (!value) return 'No data yet'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString()
}

const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback

export function DashboardPage() {
  const { user, token } = useAuth()
  const navigate = useNavigate()
  const firstName = user?.full_name?.split(' ')[0] ?? null

  const [status, setStatus] = useState<AnalyticsSummary | null>(null)
  const [model, setModel] = useState<ModelStatus | null>(null)
  const [error, setError] = useState('')
  const [summaryLoaded, setSummaryLoaded] = useState(false)
  const [modelLoaded, setModelLoaded] = useState(false)
  const [history, setHistory] = useState<PredictionHistory | null>(null)
  const [historyError, setHistoryError] = useState('')
  const [latest, setLatest] = useState<PredictionResult | null>(null)
  const [latestError, setLatestError] = useState('')
  const [latestLoading, setLatestLoading] = useState(true)
  const predictionCount = status?.total_predictions ?? null

  // Real collection figures, so the summary cards stop being static once data
  // exists. Failures are non-fatal: the cards fall back to their empty state.
  const loadStatus = useCallback(async () => {
    if (!token) return
    try {
      setStatus(await fetchAnalyticsSummary(token))
      setError('')
    } catch {
      setStatus(null)
      setError('Dashboard summary unavailable. Reload stored analytics to retry.')
    } finally {
      setSummaryLoaded(true)
    }

    // Model status is independent: a collection failure should not blank
    // out a perfectly good trained model, or the reverse.
    try {
      setModel(await trainingService.fetchModelStatus(token))
    } catch {
      setModel(null)
    } finally {
      setModelLoaded(true)
    }

  }, [token])

  // Saved predictions and the most recent saved result, rendered as saved.
  const loadPredictions = useCallback(async () => {
    if (!token) return
    setHistoryError(''); setLatestError(''); setLatestLoading(true)
    try {
      const saved = await predictionService.fetchPredictionHistory(token)
      setHistory(saved)
      const newest = saved.items[0]
      if (newest) {
        try { setLatest(await predictionService.fetchPrediction(token, newest.id)) }
        catch (err) { setLatest(null); setLatestError(errorMessage(err, 'Latest prediction unavailable.')) }
      } else setLatest(null)
    } catch (err) {
      setHistory(null)
      setHistoryError(errorMessage(err, 'Prediction history unavailable.'))
      setLatestError(errorMessage(err, 'Prediction history unavailable.'))
    } finally {
      setLatestLoading(false)
    }
  }, [token])

  useEffect(() => {
    // loadStatus/load only set state after awaiting the request, so nothing
    // is set synchronously here; the rule cannot see across the async boundary.
    // oxlint-disable-next-line react/set-state-in-effect
    void loadStatus()
  }, [loadStatus])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    void loadPredictions()
  }, [loadPredictions])

  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date())
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const refreshAll = useCallback(() => {
    setRefreshing(true)
    Promise.all([loadStatus(), loadPredictions()]).finally(() => {
      setLastRefreshed(new Date())
      setRefreshing(false)
    })
  }, [loadStatus, loadPredictions])

  useInterval(() => { if (autoRefresh) refreshAll() }, autoRefresh ? 60_000 : null)

  const collected = status?.stored_records ?? 0
  const trained = model?.trained === true
  const bySource = status?.records_by_source_type ?? {}
  const liveRecords = bySource.live ?? 0
  const demoRecords = bySource.demo ?? 0
  const availablePlatforms = status?.available_live_platforms.length
  const quality = model?.quality?.quality_status ? qualityPresentation[model.quality.quality_status] : null
  const attention = attentionItems(status, model, latest)
  const ranks = new Map(latest?.ranking.map((platform, index) => [platform.platform, index + 1]) ?? [])
  const comparison = latest
    ? [...latest.platform_results].sort((a, b) => (ranks.get(a.platform) ?? 99) - (ranks.get(b.platform) ?? 99))
    : []

  const completedSteps = [collected > 0, !!status?.latest_dataset, trained, (history?.total ?? 0) > 0].filter(Boolean).length

  return (
    <DashboardLayout title="Overview">
      <div className="space-y-6">
        {collected === 0 && <OnboardingGuide completedSteps={completedSteps} />}

        <div className="flex items-center justify-end gap-3">
          <span className="text-xs text-subtle">
            Last refreshed: {lastRefreshed.toLocaleTimeString()}
          </span>
          <button
            onClick={refreshAll}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 rounded-full border border-border-hair bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-accent hover:text-accent-text disabled:opacity-50"
          >
            <RefreshCw className={`size-3 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${autoRefresh ? 'bg-accent-soft text-accent-text' : 'bg-background-alt text-subtle'}`}
          >
            Auto {autoRefresh ? 'ON' : 'OFF'}
          </button>
        </div>

        <section aria-labelledby="overview-heading" className="surface-card overflow-hidden">
          <div className="h-1.5 gradient-accent" />
          <div className="flex flex-wrap items-start justify-between gap-5 p-5 sm:p-7">
            <div className="max-w-2xl min-w-0">
              <p className="text-sm font-medium text-accent-text">
                {(() => {
                  const h = new Date().getHours()
                  const greeting = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
                  return firstName ? `${greeting}, ${firstName}` : greeting
                })()}
              </p>
              <h2 id="overview-heading" className="mt-1.5 text-2xl font-semibold tracking-tight sm:text-[28px]">
                Marketplace Intelligence Dashboard
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                Compare marketplace signals, track price trends, and get ML-powered opportunity scores across platforms.
              </p>
            </div>
          </div>

          <div className="border-t border-border-hair px-5 py-3 sm:px-7">
            <div className="flex flex-wrap items-center gap-2.5">
              <Link to="/dashboard/search" className="inline-flex items-center gap-2 rounded-full bg-accent px-3.5 py-2 text-xs font-medium text-accent-ink shadow-accent transition-colors hover:bg-accent-hover">
                <Icon name="search" className="size-3.5" />Search Products
              </Link>
              <Link to="/dashboard/products" className="inline-flex items-center gap-2 rounded-full border border-border-hair bg-surface px-3.5 py-2 text-xs font-medium transition-colors hover:border-accent hover:text-accent-text">
                <Icon name="package" className="size-3.5" />Product Catalog
              </Link>
              <Link to="/dashboard/marketplace-data" className="inline-flex items-center gap-2 rounded-full border border-border-hair bg-surface px-3.5 py-2 text-xs font-medium transition-colors hover:border-accent hover:text-accent-text">
                <Icon name="database" className="size-3.5" />Collect Data
              </Link>
              {can(user, 'prediction:run') && (
                <Link to="/dashboard/predictor" className="inline-flex items-center gap-2 rounded-full bg-accent px-3.5 py-2 text-xs font-medium text-accent-ink shadow-accent transition-colors hover:bg-accent-hover">
                  <Icon name="compass" className="size-3.5" />Predict
                </Link>
              )}
              <Link to="/dashboard/trends" className="inline-flex items-center gap-2 rounded-full border border-border-hair bg-surface px-3.5 py-2 text-xs font-medium transition-colors hover:border-accent hover:text-accent-text">
                <Icon name="trend" className="size-3.5" />View Trends
              </Link>
              <Link to="/dashboard/alerts" className="inline-flex items-center gap-2 rounded-full border border-border-hair bg-surface px-3.5 py-2 text-xs font-medium transition-colors hover:border-accent hover:text-accent-text">
                <Icon name="pulse" className="size-3.5" />Alerts
              </Link>
            </div>
          </div>

          {(demoRecords > 0 || error) && (
            <div className="border-t border-border-hair bg-background px-5 py-4 sm:px-7">
              {error && <p role="alert" className="text-sm text-signal-warn">{error}</p>}
              {demoRecords > 0 && <DemoDataBanner demoRecords={demoRecords} liveRecords={liveRecords} />}
            </div>
          )}
        </section>

        {/* Decision KPI cards */}
        <section aria-label="Summary">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryCard
              label="Stored Records"
              icon="database"
              loading={!summaryLoaded}
              value={status?.stored_records}
              unavailable={summaryLoaded && !status ? 'Unavailable' : undefined}
              footer={status && collected > 0 ? (['live', 'imported', 'demo'] as const).filter((source) => (bySource[source] ?? 0) > 0).map((source) => <span key={source} className="inline-flex items-center gap-1 text-xs text-muted"><SourceBadge kind={source} />{(bySource[source] ?? 0).toLocaleString()}</span>) : undefined}
              hint={status ? `${status.stored_platforms.length} of ${PLATFORM_KEYS.length} marketplaces represented in stored data.` : 'Stored platform coverage unavailable.'}
            />
            <SummaryCard
              label="Total Predictions"
              icon="compass"
              loading={!summaryLoaded}
              value={predictionCount ?? undefined}
              unavailable={summaryLoaded && predictionCount === null ? 'Unavailable' : undefined}
              hint="Your saved experimental predictions."
            />
            <SummaryCard
              label="Active Model · Weighted F1"
              icon="target"
              tone={quality?.tone === 'down' ? 'down' : quality?.tone === 'ok' ? 'ok' : quality ? 'warn' : 'idle'}
              loading={!modelLoaded}
              unavailable={trained ? undefined : model ? 'Not trained' : 'Unavailable'}
              value={
                trained && model?.primary_metric_value !== null &&
                model?.primary_metric_value !== undefined
                  ? `${(model.primary_metric_value * 100).toFixed(1)}% F1`
                  : undefined
              }
              footer={trained && quality ? <span className="text-xs font-medium text-muted">Quality: <span className={quality.tone === 'down' ? 'text-signal-down' : quality.tone === 'ok' ? 'text-signal-ok' : 'text-signal-warn'}>{quality.label}</span></span> : undefined}
              hint={
                trained
                  ? `${model?.active_model} ${model?.version}. Majority baseline accuracy (a different metric): ${
                      model?.majority_baseline !== null &&
                      model?.majority_baseline !== undefined
                        ? `${(model.majority_baseline * 100).toFixed(1)}%`
                        : 'unknown'
                    }.`
                  : 'Populated from a real evaluation run once a model is trained.'
              }
            />
            <SummaryCard
              label="Items Needing Attention"
              icon="alert"
              tone={attention.some((item) => item.tone === 'down') ? 'down' : attention.length ? 'warn' : 'ok'}
              loading={!summaryLoaded || !modelLoaded}
              value={attention.length}
              hint="Data-quality, collector and model limitations listed below."
            />
          </div>
        </section>

        {/* Trend + latest recommendation */}
        <div className="grid gap-6 xl:grid-cols-12">
          <div className="min-w-0 xl:col-span-8">
            <PriceHistoryPanel preferredProductKey={latest?.product_key ?? null} />
          </div>
          <div className="min-w-0 xl:col-span-4">
            <RecommendationCard result={latest} loading={latestLoading} error={latestError} empty={history?.total === 0} onRetry={() => { void loadPredictions() }} />
          </div>
        </div>

        {/* Platform comparison + data quality */}
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="min-w-0 lg:col-span-7">
            <SectionCard
              title="Platform comparison"
              description={latest ? <>Heuristic opportunity scores (fixed 0–100 scale) from the latest saved prediction for <strong className="font-medium text-foreground">{latest.product}</strong>. Not revenue, demand or guaranteed profit.</> : 'Scores from your latest saved prediction appear here.'}
              className="h-full"
            >
              {latestLoading ? <SkeletonBlock label="Loading platform comparison" lines={4} /> : comparison.length === 0 ? (
                <EmptyState icon="chart" title="No platform comparison yet">Only platforms present in a saved prediction are compared; nothing is shown for platforms without stored observations.</EmptyState>
              ) : (
                <div className="space-y-5">
                  {comparison.map((platform) => (
                    <PlatformScoreRow key={platform.platform} platform={platform} rank={ranks.get(platform.platform) ?? null} recommended={platform.platform === latest?.recommended_platform} />
                  ))}
                  <p className="border-t border-border-hair pt-3 text-xs text-subtle">Missing signals earn no points; compare coverage and observation dates. Formula {latest?.formula.version}.</p>
                </div>
              )}
            </SectionCard>
          </div>
          <div className="min-w-0 lg:col-span-5">
            <DataQualityPanel items={attention} loading={!summaryLoaded || !modelLoaded} />
          </div>
        </div>

        {/* Recent predictions + pipeline status */}
        <div className="grid gap-6 xl:grid-cols-12">
          <div className="min-w-0 xl:col-span-8">
            <RecentPredictionsTable history={history} error={historyError} onRetry={() => { void loadPredictions() }} />
          </div>
          <div className="min-w-0 xl:col-span-4">
            <SectionCard title="Pipeline status" description="Collection, dataset and collector state." className="h-full">
              {!summaryLoaded ? <SkeletonBlock label="Loading pipeline status" lines={4} /> : (
                <div className="space-y-3 text-sm">
                  <dl className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <dt className="flex items-center gap-2 text-muted"><Icon name="clock" className="size-4" />Latest Observation</dt>
                      <dd className="text-right font-medium">{status?.latest_observation ? formatTimestamp(status.latest_observation) : status ? 'No data yet' : 'Unavailable'}</dd>
                    </div>
                    {status && status.latest_observation_sources.length > 0 && (
                      <div className="flex flex-wrap items-center justify-end gap-1.5 text-xs text-muted">
                        <dt>Latest observation source:</dt>
                        <dd className="flex gap-1.5">{status.latest_observation_sources.map((source) => <SourceBadge key={source} kind={source} />)}</dd>
                      </div>
                    )}
                    <div className="flex items-start justify-between gap-3 border-t border-border-hair pt-3">
                      <dt className="flex items-center gap-2 text-muted"><Icon name="refresh" className="size-4" />Usable Live Collectors</dt>
                      <dd className="font-medium tabular-nums">{availablePlatforms ?? 'Unavailable'}</dd>
                    </div>
                    <div className="flex items-start justify-between gap-3 border-t border-border-hair pt-3">
                      <dt className="flex items-center gap-2 text-muted"><Icon name="layers" className="size-4" />Latest Dataset Source</dt>
                      <dd className="text-right font-medium">{status?.latest_dataset?.source_types.map((source) => source.toUpperCase()).join(' / ') || (status ? 'No dataset' : 'Unavailable')}</dd>
                    </div>
                  </dl>
                  <p className="text-xs break-words text-subtle">{status?.latest_dataset ? `${status.latest_dataset.dataset_id}. ${status.latest_dataset.file_available ? 'Dataset file present.' : 'Dataset file unavailable.'}` : 'Build a dataset from stored observations.'}</p>
                  <div className="border-t border-border-hair pt-3">
                    <p className="text-muted">Marketplaces with stored data</p>
                    <p className="mt-2 flex flex-wrap gap-2">
                      {status && status.stored_platforms.length > 0
                        ? status.stored_platforms.map((platform) => <span key={platform} className="rounded-full border border-border-hair bg-background-alt px-2.5 py-0.5 text-xs font-medium">{title(platform)}</span>)
                        : <span className="text-xs text-subtle">None stored</span>}
                    </p>
                  </div>
                  {status?.notice && <p className="border-t border-border-hair pt-3 text-xs leading-relaxed text-muted">{status.notice}</p>}
                </div>
              )}
            </SectionCard>
          </div>
        </div>

        {/* Main actions */}
        <section aria-label="Actions">
          <div className="grid gap-4 md:grid-cols-2">
            <PermissionGate permission="dataset:build"><ActionCard
              icon="layers"
              title={can(user, "model:train") ? "Train Model" : "Prepare Dataset"}
              description="Build the ML-ready dataset from stored snapshots, then train a model and inspect measured validation quality."
              actionLabel="Prepare dataset"
              blockedReason={
                collected === 0
                  ? 'Needs a dataset. Collect, import or load demo data first.'
                  : undefined
              }
              onAction={() => navigate('/dashboard/train')}
            /></PermissionGate>
            <PermissionGate permission="prediction:run"><ActionCard
              icon="compass"
              title="Make Prediction"
              description="Choose an electronics product, compare marketplaces, and get a 0-100 opportunity score for each with the factors behind it."
              actionLabel="New Prediction"
              blockedReason={trained ? undefined : 'Needs an active trained model. Open Train Model first.'}
              onAction={() => navigate('/dashboard/predictor')}
            /></PermissionGate>
          </div>
        </section>

        {/* Data refresh (LIVE collection stays gated) */}
        <SectionCard title="Market data refresh" description="LIVE refresh runs only when a collector is configured and approved. Otherwise, reload stored analytics.">
          <MarketDataRefresh sources={status?.refresh_sources ?? null} onRefresh={() => { void loadStatus(); void loadPredictions() }} />
        </SectionCard>

      </div>
    </DashboardLayout>
  )
}
