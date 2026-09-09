/**
 * Dashboard shell (Phase 3).
 *
 * Layout follows PROJECT_CONTEXT.md section 9. Every figure shown here is
 * either genuinely known (the user, the configured platform count) or clearly
 * marked as not yet available. Nothing invents a model accuracy, a prediction
 * count or a data-freshness timestamp — those become real in Phases 4-8.
 */

import { ActionCard } from '@/components/dashboard/ActionCard'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { SummaryCard } from '@/components/dashboard/SummaryCard'
import { Icon } from '@/components/Icon'
import { StatusPill } from '@/components/StatusPill'
import { supportedPlatforms } from '@/config/dashboard'
import { useAuth } from '@/hooks/useAuth'

export function DashboardPage() {
  const { user } = useAuth()
  const firstName = user?.full_name?.split(' ')[0] ?? null

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
              Using fresh cross-platform data and machine learning. The
              collection and model pipelines are still being built, so the
              actions below are inactive until there is real data behind them.
            </p>
          </div>

          <StatusPill tone="idle">No data collected yet</StatusPill>
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
            unavailable="Not trained"
            hint="Populated from a real evaluation run once a model is trained."
          />
          <SummaryCard
            label="Data Freshness"
            icon="clock"
            unavailable="No data yet"
            hint="Shows the last marketplace collection timestamp."
          />
          <SummaryCard
            label="Platforms"
            icon="database"
            value={supportedPlatforms.length}
            hint={supportedPlatforms.join(', ')}
          />
        </div>
      </section>

      {/* Main actions */}
      <section aria-label="Actions" className="mt-6">
        <div className="grid gap-5 md:grid-cols-2">
          <ActionCard
            icon="layers"
            title="Train Model"
            description="Train a model on the collected marketplace dataset and record its measured accuracy, dataset size and feature set."
            actionLabel="Train Model"
            blockedReason="Needs a collected dataset. Marketplace collection is not implemented yet."
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

      {/* Build status */}
      <section className="mt-6 rounded-panel border border-border-hair bg-background-alt p-6">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Icon name="check" className="size-4 text-signal-ok" />
          What works right now
        </h3>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
          Accounts, sign-in and this protected dashboard are live. Marketplace
          data collection, the dataset builder, model training, predictions and
          trend charts are the next phases — the sidebar items marked{' '}
          <span className="rounded-full border border-border-hair px-1.5 py-0.5 text-[10px] text-subtle">
            Soon
          </span>{' '}
          are not built yet.
        </p>
      </section>
    </DashboardLayout>
  )
}
