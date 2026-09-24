/**
 * The most recent saved prediction: which marketplace had the highest heuristic
 * opportunity score, the contributions behind it, and the warnings that came
 * with it. Rendered from the saved result, never recomputed from current data.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

import { Icon } from '@/components/Icon'
import { SourceBadge } from '@/components/SourceBadge'
import { StatusPill } from '@/components/StatusPill'
import { PlatformBadge } from '@/components/dashboard/PlatformBadge'
import { SectionCard } from '@/components/dashboard/SectionCard'
import { EmptyState, ErrorState, SkeletonBlock } from '@/components/dashboard/StateViews'
import { BELOW_BASELINE_MESSAGE, qualityPresentation } from '@/lib/modelQuality'
import { percent, timestamp, title } from '@/lib/predictionFormat'
import type { QualityStatus } from '@/types/data'
import type { PredictionResult } from '@/types/prediction'

function AnimatedScore({ value }: { value: number }) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    let raf: number
    const start = performance.now()
    const duration = 800
    function tick(now: number) {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(eased * value)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])
  return <span className="text-2xl font-semibold tabular-nums text-foreground">{display.toFixed(1)}</span>
}

function ConfidenceMeter({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score))
  const hue = pct < 40 ? 0 : pct < 70 ? 40 : 142
  return (
    <div className="mt-3">
      <div className="flex items-center justify-between text-[11px] text-muted">
        <span>Opportunity strength</span>
        <span className="tabular-nums font-medium">{score.toFixed(1)} / 100</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-chart-track">
        <motion.div
          className="h-full rounded-full"
          style={{ background: `linear-gradient(90deg, hsl(${hue} 70% 45%), hsl(${hue} 70% 55%))` }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.2, 0, 0, 1] }}
        />
      </div>
    </div>
  )
}

interface RecommendationCardProps {
  result: PredictionResult | null
  loading: boolean
  error: string
  onRetry: () => void
  empty: boolean
}

export function RecommendationCard({ result, loading, error, onRetry, empty }: RecommendationCardProps) {
  const top = result?.ranking[0]
  const status = result?.model.quality_status && result.model.quality_status in qualityPresentation
    ? qualityPresentation[result.model.quality_status as QualityStatus]
    : null
  const contributions = top
    ? Object.entries(top.components)
        .filter(([key]) => !top.missing_components.includes(key))
        .sort(([, a], [, b]) => b - a)
        .slice(0, 3)
    : []

  return (
    <SectionCard
      title="Latest recommendation"
      description={result ? `Saved ${timestamp(result.created_at)}` : 'Your most recent saved prediction.'}
      className="h-full"
    >
      {error ? <ErrorState message={error} onRetry={onRetry} /> : loading ? <SkeletonBlock label="Loading latest prediction" lines={5} /> : empty || !result ? (
        <EmptyState icon="compass" title="No saved predictions yet">
          Run a prediction for a stored product to compare marketplaces.{' '}
          <Link to="/dashboard/predictor" className="font-medium text-accent-text hover:underline">Open ML Predictor</Link>
        </EmptyState>
      ) : (
        <div className="flex h-full flex-col">
          <p className="truncate text-sm text-muted" title={result.product}>{result.product}</p>
          <p className="mt-3 text-xs font-medium tracking-wide text-subtle uppercase">{result.recommendation_label}</p>
          <div className="mt-1 flex flex-wrap items-end justify-between gap-2">
            <PlatformBadge platform={result.recommended_platform} className="text-2xl font-semibold tracking-tight" />
            <p className="text-sm text-muted">
              {top?.opportunity_score != null ? <AnimatedScore value={top.opportunity_score} /> : <span className="text-2xl font-semibold tabular-nums text-foreground">—</span>} / 100
            </p>
          </div>
          {top?.opportunity_score != null && <ConfidenceMeter score={top.opportunity_score} />}
          <p className="mt-1 text-xs text-subtle">
            {result.score_difference === null ? 'Only one platform could be evaluated.' : result.score_difference === 0 ? 'Tied top score.' : `${result.score_difference.toFixed(1)} points above the next platform.`}
            {' '}Heuristic score, not a demand, revenue or success probability.
          </p>

          {contributions.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-medium text-muted">Largest score contributions ({title(result.recommended_platform)})</p>
              <dl className="mt-2 space-y-2">
                {contributions.map(([key, points]) => {
                  const weight = result.formula.weights[key] ?? 0
                  return (
                    <div key={key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 text-xs">
                      <dt className="truncate text-muted">{title(key)}</dt>
                      <dd className="tabular-nums">{points.toFixed(1)} / {weight} pts</dd>
                      <dd aria-hidden="true" className="col-span-2 mt-1 h-1.5 overflow-hidden rounded-full bg-chart-track">
                        <div className="h-full rounded-full bg-accent" style={{ width: `${weight ? Math.min(100, (points / weight) * 100) : 0}%` }} />
                      </dd>
                    </div>
                  )
                })}
              </dl>
            </div>
          )}

          <div className="mt-4 space-y-2 border-t border-border-hair pt-3">
            {result.model.below_baseline && (
              <p className="flex items-start gap-2 rounded-card border border-signal-down/30 bg-signal-down/10 px-3 py-2 text-xs font-medium text-signal-down">
                <Icon name="alert" className="mt-px size-3.5 shrink-0" />{BELOW_BASELINE_MESSAGE}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              {status ? <StatusPill tone={status.tone}>{status.label}</StatusPill> : <span>Quality status not recorded</span>}
              <span>Accuracy {percent(result.model.accuracy)} vs majority baseline {percent(result.model.majority_baseline)}</span>
            </div>
            <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted">Input data: {result.data_provenance.source_types.map((source) => <SourceBadge key={source} kind={source} />)}</p>
            <p className="text-xs leading-relaxed text-signal-warn">{result.warning}</p>
          </div>

          <Link
            to={`/dashboard/predictor?prediction=${result.id}`}
            className="mt-4 inline-flex items-center gap-1.5 self-start text-sm font-medium text-accent-text hover:underline"
          >
            View saved result #{result.id}
            <Icon name="arrow-right" className="size-4" />
          </Link>
        </div>
      )}
    </SectionCard>
  )
}
