/**
 * Dashboard overview.
 *
 * Layout follows PROJECT_CONTEXT.md section 9. Collection figures come from
 * GET /data/status and are real. Everything not yet measurable is marked as
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
import { supportedPlatforms } from '@/config/dashboard'
import { useAuth } from '@/hooks/useAuth'
import * as dataService from '@/services/dataService'
import * as trainingService from '@/services/trainingService'
import type { CollectorStatus, ModelStatus } from '@/types/data'

function formatTimestamp(value: string | null): string {
  if (!value) return 'No data yet'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString()
}

export function DashboardPage() {
  const { user, token } = useAuth()
  const navigate = useNavigate()
  const firstName = user?.full_name?.split(' ')[0] ?? null

  const [status, setStatus] = useState<CollectorStatus | null>(null)
  const [model, setModel] = useState<ModelStatus | null>(null)

  // Real collection figures, so the summary cards stop being static once data
  // exists. Failures are non-fatal: the cards fall back to their empty state.
  const loadStatus = useCallback(async () => {
    if (!token) return
    try {
      setStatus(await dataService.fetchStatus(token))
    } catch {
      setStatus(null)
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

  const collected = status?.total_snapshots ?? 0
  const trained = model?.trained === true
  const bySource = status?.records_by_source_type ?? {}
  const liveRecords = bySource.live ?? 0
  const availablePlatforms = status
    ? Object.values(status.platforms).filter((p) => p.available).length
    : 0

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
              Using fresh cross-platform data and machine learning. Marketplace
              collection is live; the model pipeline is still being built.
            </p>
          </div>

          <div className="flex flex-col items-end gap-3">
            {/* Tone follows live data specifically: a database full of demo
                rows is not a healthy data pipeline, and should not look like one. */}
            <StatusPill tone={liveRecords > 0 ? 'ok' : 'idle'}>
              {collected > 0
                ? `${collected} record${collected === 1 ? '' : 's'} stored`
                : 'No data collected yet'}
            </StatusPill>
            <Link
              to="/dashboard/marketplace-data"
              className="inline-flex items-center gap-2 rounded-card border border-border-strong px-4 py-2 text-sm font-medium transition-colors hover:border-accent hover:text-accent-text"
            >
              <Icon name="refresh" className="size-4" />
              Refresh Marketplace Data
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
            value={0}
            hint="No predictions have been made yet."
          />
          <SummaryCard
            label="Model Accuracy"
            icon="target"
            unavailable={trained ? undefined : 'Not trained'}
            value={
              trained && model?.primary_metric_value !== null &&
              model?.primary_metric_value !== undefined
                ? `${(model.primary_metric_value * 100).toFixed(1)}% F1`
                : undefined
            }
            hint={
              trained
                ? `${model?.active_model} ${model?.version}. Baseline (always guess the most common class): ${
                    model?.majority_baseline !== null &&
                    model?.majority_baseline !== undefined
                      ? `${(model.majority_baseline * 100).toFixed(1)}%`
                      : 'unknown'
                  }.`
                : 'Populated from a real evaluation run once a model is trained.'
            }
          />
          <SummaryCard
            label="Data Freshness"
            icon="clock"
            unavailable={
              status?.last_collection
                ? undefined
                : 'No data yet'
            }
            value={
              status?.last_collection
                ? formatTimestamp(status.last_collection)
                : undefined
            }
            hint={
              collected > 0
                ? `${liveRecords} live, ${bySource.imported ?? 0} imported, ${bySource.demo ?? 0} demo.`
                : 'Shows the last marketplace collection timestamp.'
            }
          />
          <SummaryCard
            label="Platforms"
            icon="database"
            value={supportedPlatforms.length}
            hint={
              status
                ? `${availablePlatforms} of ${supportedPlatforms.length} collectable. ${supportedPlatforms.join(', ')}`
                : supportedPlatforms.join(', ')
            }
          />
        </div>
      </section>

      {/* Main actions */}
      <section aria-label="Actions" className="mt-6">
        <div className="grid gap-5 md:grid-cols-2">
          <ActionCard
            icon="layers"
            title="Train Model"
            description="Build the ML-ready dataset from stored snapshots, then train a model on it and record its measured accuracy. Dataset preparation is available now; training arrives next."
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
            blockedReason="Needs a trained model. No model has been trained yet."
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
          dataset builder and model training are live. Predictions and trend
          charts are the next phases — the sidebar items marked{' '}
          <span className="rounded-full border border-border-hair px-1.5 py-0.5 text-[10px] text-subtle">
            Soon
          </span>{' '}
          are not built yet.
        </p>
      </section>
    </DashboardLayout>
  )
}
