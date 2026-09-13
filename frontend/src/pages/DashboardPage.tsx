/**
 * Dashboard overview.
 *
 * Layout follows PROJECT_CONTEXT.md section 9. Collection figures come from
 * GET /analytics/summary and are real. Everything not yet measurable is marked as
 * unavailable rather than given a placeholder number: model accuracy stays
 * "Not trained" until a real evaluation run fills it.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ActionCard } from '@/components/dashboard/ActionCard'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { SummaryCard } from '@/components/dashboard/SummaryCard'
import { Icon } from '@/components/Icon'
import { StatusPill } from '@/components/StatusPill'
import { MarketDataRefresh } from '@/components/dashboard/MarketDataRefresh'
import { SourceBadge } from '@/components/SourceBadge'
import { fetchAnalyticsSummary } from '@/services/analyticsService'
import type { AnalyticsSummary } from '@/types/analytics'
import { useAuth } from '@/hooks/useAuth'
import * as trainingService from '@/services/trainingService'
import type { ModelStatus } from '@/types/data'

function formatTimestamp(value: string | null): string {
  if (!value) return 'No data yet'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString()
}

export function DashboardPage() {
  const { user, token } = useAuth()
  const navigate = useNavigate()
  const firstName = user?.full_name?.split(' ')[0] ?? null

  const [status, setStatus] = useState<AnalyticsSummary | null>(null)
  const [model, setModel] = useState<ModelStatus | null>(null)
  const [error, setError] = useState('')
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
    }

    // Model status is independent: a collection failure should not blank
    // out a perfectly good trained model, or the reverse.
    try {
      setModel(await trainingService.fetchModelStatus(token))
    } catch {
      setModel(null)
    }

  }, [token])

  useEffect(() => {
    // loadStatus/load only set state after awaiting the request, so nothing
    // is set synchronously here; the rule cannot see across the async boundary.
    // oxlint-disable-next-line react/set-state-in-effect
    void loadStatus()
  }, [loadStatus])

  const collected = status?.stored_records ?? 0
  const trained = model?.trained === true
  const bySource = status?.records_by_source_type ?? {}
  const liveRecords = bySource.live ?? 0
  const availablePlatforms = status?.available_live_platforms.length


  return (
    <DashboardLayout title="MarketPulse AI — Platform Predictor Dashboard">
      {/* Hero card */}
      <section className="rounded-panel border border-border-hair bg-surface p-7 sm:p-9">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold tracking-[0.16em] text-accent-text uppercase">
              {firstName ? `Welcome back, ${firstName}` : 'Welcome back'}
            </p>
            <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
              Predict marketplace opportunities for electronics products
            </h2>
            <p className="mt-3 leading-relaxed text-muted">
              Compare recorded marketplace signals using an experimental model
              pipeline. Data provenance and measured model quality accompany results.
            </p>
          </div>

          <div className="flex flex-col items-end gap-3">
            {/* Tone follows live data specifically: a database full of demo
                rows is not a healthy data pipeline, and should not look like one. */}
            <StatusPill tone={liveRecords > 0 ? 'ok' : 'idle'}>
              {collected > 0
                ? `${collected} record${collected === 1 ? '' : 's'} stored`
                : status ? 'No data collected yet' : 'Summary unavailable'}
            </StatusPill>
            <Link
              to="/dashboard/marketplace-data"
              className="inline-flex items-center gap-2 rounded-card border border-border-strong px-4 py-2 text-sm font-medium transition-colors hover:border-accent hover:text-accent-text"
            >
              <Icon name="refresh" className="size-4" />
              Manage Marketplace Data
            </Link>
          </div>
        </div>
      </section>

      {/* Summary cards */}
      <section aria-label="Summary" className="mt-6">
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard
            label="Total Predictions"
            icon="compass"
            value={predictionCount ?? undefined}
            unavailable={predictionCount === null ? 'Unavailable' : undefined}
            hint="Your saved experimental predictions."
          />
          <SummaryCard
            label="Active Model ? Weighted F1"
            icon="target"
            unavailable={trained ? undefined : model ? 'Not trained' : 'Unavailable'}
            value={
              trained && model?.primary_metric_value !== null &&
              model?.primary_metric_value !== undefined
                ? `${(model.primary_metric_value * 100).toFixed(1)}% F1`
                : undefined
            }
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
            label="Latest Observation"
            icon="clock"
            unavailable={
              status?.latest_observation
                ? undefined
                : status ? 'No data yet' : 'Unavailable'
            }
            value={
              status?.latest_observation
                ? formatTimestamp(status.latest_observation)
                : undefined
            }
            hint={
              collected > 0
                ? `${liveRecords} live, ${bySource.imported ?? 0} imported, ${bySource.demo ?? 0} demo.`
                : 'Shows the last marketplace collection timestamp.'
            }
          />
          <SummaryCard label="Stored Records" icon="database" value={status?.stored_records} unavailable={status ? undefined : 'Unavailable'} hint={status ? `${status.stored_platforms.length} platforms represented in stored data.` : 'Stored platform coverage unavailable.'} />
          <SummaryCard label="Usable Live Collectors" icon="refresh" value={availablePlatforms} unavailable={status ? undefined : 'Unavailable'} hint="Collector availability, independent of how many platforms have stored rows." />
          <SummaryCard label="Latest Dataset Source" icon="layers" value={status?.latest_dataset?.source_types.map((source) => source.toUpperCase()).join(' / ') || undefined} unavailable={status?.latest_dataset?.source_types.length ? undefined : status ? 'No dataset' : 'Unavailable'} hint={status?.latest_dataset ? `${status.latest_dataset.dataset_id}. ${status.latest_dataset.file_available ? 'Dataset file present.' : 'Dataset file unavailable.'}` : 'Build a dataset from stored observations.'} />
        </div>
      </section>

      <section className="mt-6 space-y-3">
        {error && <p role="alert" className="text-sm text-signal-warn">{error}</p>}
        {status && <><div className="flex flex-wrap items-center gap-2 text-sm"><span>Latest observation:</span>{status.latest_observation_sources.map((source) => <SourceBadge key={source} kind={source} />)}</div><p className="text-sm text-muted">{status.notice}</p></>}
        <MarketDataRefresh sources={status?.refresh_sources ?? null} onRefresh={() => { void loadStatus() }} />
      </section>

      {/* Main actions */}
      <section aria-label="Actions" className="mt-6">
        <div className="grid gap-5 md:grid-cols-2">
          <ActionCard
            icon="layers"
            title="Train Model"
            description="Build the ML-ready dataset from stored snapshots, then train a model and inspect measured validation quality."
            actionLabel={collected === 0 ? 'Train Model' : 'Prepare dataset'}
            blockedReason={
              collected === 0
                ? 'Needs a dataset. Collect, import or load demo data first.'
                : undefined
            }
            onAction={() => navigate('/dashboard/train')}
          />
          <ActionCard
            icon="compass"
            title="Make Prediction"
            description="Choose an electronics product, compare marketplaces, and get a 0-100 opportunity score for each with the factors behind it."
            actionLabel="New Prediction"
            blockedReason={trained ? undefined : 'Needs an active trained model. Open Train Model first.'}
            onAction={() => navigate('/dashboard/predictor')}
          />
        </div>
      </section>

      {/* Demo-trained model warning */}
      {model?.notice && (
        <section className="mt-6">
          <p
            role="status"
            className="flex items-start gap-2.5 rounded-panel border border-signal-warn/30 bg-signal-warn/10 px-5 py-4 text-sm text-signal-warn"
          >
            <Icon name="alert" className="mt-0.5 size-4 shrink-0" />
            <span>{model.notice}</span>
          </p>
        </section>
      )}

      {/* Build status */}
      <section className="mt-6 rounded-panel border border-border-hair bg-background-alt p-6">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Icon name="check" className="size-4 text-signal-ok" />
          What works right now
        </h3>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
          Accounts, sign-in, this dashboard, marketplace data collection, the
          dataset builder, model training and experimental predictions are available.
          Stored price, discount, rating, review and availability histories are available
          in Trend Analysis; Analytics compares explicitly grouped products or categories.
        </p>
      </section>
    </DashboardLayout>
  )
}
