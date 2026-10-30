import { FormAlert } from '@/components/FormAlert'
import { Panel } from '@/components/Panel'
import { SourceBadge } from '@/components/SourceBadge'
import { StatusPill } from '@/components/StatusPill'
import { PlatformBadge } from '@/components/dashboard/PlatformBadge'
import { PlatformScoreRow } from '@/components/dashboard/PlatformScoreRow'
import { BELOW_BASELINE_MESSAGE, qualityPresentation } from '@/lib/modelQuality'
import type { QualityStatus } from '@/types/data'
import type { ModelQuality, PredictionResult } from '@/types/prediction'
import { percent, timestamp, title } from '@/lib/predictionFormat'

export function QualityContext({ model }: { model: ModelQuality }) {
  const status = model.quality_status && model.quality_status in qualityPresentation
    ? qualityPresentation[model.quality_status as QualityStatus]
    : null
  return (
    <div className="space-y-3">
      {model.below_baseline && (
        <p role="alert" className="rounded-card border border-signal-down/30 bg-signal-down/10 px-4 py-3 text-sm font-semibold text-signal-down">
          {BELOW_BASELINE_MESSAGE}
        </p>
      )}
      <FormAlert tone="info">{model.warning}</FormAlert>
      <p className="text-sm leading-relaxed text-muted">
        {title(model.type ?? 'Unknown model')} {model.version} · Validation accuracy <strong className="text-foreground">{percent(model.accuracy)}</strong>
        {' '}vs majority baseline accuracy <strong className="text-foreground">{percent(model.majority_baseline)}</strong>
        {model.baselines?.persistence_accuracy !== undefined && model.baselines?.persistence_accuracy !== null && (
          <> · previous-direction baseline accuracy {percent(model.baselines.persistence_accuracy)}</>
        )}
        {' '}· Weighted F1 {percent(model.primary_metric_value)}
      </p>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        {status ? <StatusPill tone={status.tone}>{status.label}</StatusPill> : <span>Quality status not recorded</span>}
        <span>Probabilities: {model.calibration_status ?? 'uncalibrated'}</span>
        {model.legacy_model && <span className="text-signal-warn">Trained before the Phase 12 leakage fix</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        Model training data: {model.source_types.map((source) => <SourceBadge key={source} kind={source} />)}
      </div>
    </div>
  )
}

export function PredictionResults({ result }: { result: PredictionResult }) {
  const top = result.ranking[0]
  const ranks = new Map(result.ranking.map((platform, index) => [platform.platform, index + 1]))
  return (
    <section aria-label="Prediction results" className="space-y-5">
      <div className="surface-card min-w-0 overflow-hidden break-words">
        <div className="grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <div className="p-5 sm:p-7">
            <p className="text-xs text-subtle">Saved result #{result.id} · {timestamp(result.created_at)}</p>
            <h2 className="mt-2 text-xl font-semibold">{result.product}</h2>
            <p className="mt-5 text-xs font-medium tracking-wide text-subtle uppercase">{result.recommendation_label}</p>
            <div className="mt-1.5 flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <PlatformBadge platform={result.recommended_platform} className="text-3xl font-semibold tracking-tight" />
              <p className="text-2xl font-semibold tabular-nums text-accent-text">{top?.opportunity_score?.toFixed(1)} <span className="text-base font-medium text-muted">/ 100</span></p>
            </div>
            <p className="mt-2 text-sm text-muted">
              {result.score_difference === null ? 'Only one platform could be evaluated.' : result.score_difference === 0 ? 'Tied top score. Display order uses platform name.' : `${result.score_difference.toFixed(1)} points above the next platform.`}
            </p>
            <p className="mt-2 text-xs text-subtle">These scores are heuristic comparisons of recorded signals, not success probabilities or profit estimates.</p>
            <p className="mt-3 text-sm text-muted">{result.warning}</p>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted">
              Input dataset: {result.data_provenance.source_types.map((source) => <SourceBadge key={source} kind={source} />)}
            </div>
            <p className="mt-1 text-xs text-subtle">Trend history uses current stored snapshots; it does not change this saved prediction.</p>
          </div>
          <div className="border-t border-border-hair bg-background-alt/60 p-5 sm:p-7 lg:border-t-0 lg:border-l">
            <h3 className="text-sm font-semibold">Model quality at prediction time</h3>
            <div className="mt-3"><QualityContext model={result.model} /></div>
          </div>
        </div>
      </div>

      <Panel>
        <h3 className="font-semibold">Marketplace comparison</h3>
        <p className="mt-1 text-sm text-muted">Fixed 0–100 scale. Missing signals earn no points; compare coverage and observation dates.</p>
        <div className="mt-5 space-y-5">
          {[...result.platform_results].sort((a, b) => (ranks.get(a.platform) ?? 99) - (ranks.get(b.platform) ?? 99)).map((platform) => (
            <PlatformScoreRow key={platform.platform} platform={platform} rank={ranks.get(platform.platform) ?? null} recommended={platform.platform === result.recommended_platform} />
          ))}
        </div>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        {result.ranking.map((platform, index) => (
          <Panel key={platform.platform}>
            <div className="flex items-center justify-between gap-3">
              <h3 className="flex items-center gap-2 font-semibold"><span className="text-subtle">{index + 1}.</span> <PlatformBadge platform={platform.platform} /></h3>
              {platform.source_type && <SourceBadge kind={platform.source_type} />}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 rounded-card bg-background-alt p-3 text-sm">
              <div><p className="text-xs text-subtle">Price-direction class</p><p className="mt-0.5 font-semibold">{title(platform.predicted_class ?? 'Unavailable')}</p></div>
              <div><p className="text-xs text-subtle">Class probability</p><p className="mt-0.5 font-semibold tabular-nums">{percent(platform.confidence)}</p></div>
            </div>
            <p className="mt-2 text-xs text-subtle">Uncalibrated model probability; not reliability or likelihood of marketplace success. {platform.model_version}</p>
            <p className="mt-3 text-xs text-muted">Observed: {timestamp(platform.data_freshness)}{platform.stale ? <span className="font-medium text-signal-warn"> · STALE</span> : ''}</p>
            <p className="mt-3 text-xs leading-relaxed text-signal-warn">{platform.warning}</p>
            <p className="mt-3 text-sm text-muted">Top contributions: {platform.key_factors.map(title).join(', ')}</p>

            <h4 className="mt-4 text-xs font-medium text-muted">Score contributions</h4>
            <dl className="mt-2 space-y-2.5">
              {Object.entries(platform.components).map(([key, points]) => {
                const weight = result.formula.weights[key] ?? 0
                const missing = platform.missing_components.includes(key)
                return (
                  <div key={key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 text-xs">
                    <dt className="text-muted">{title(key)}</dt>
                    <dd className={missing ? 'text-subtle' : 'tabular-nums'}>{missing ? 'Missing · 0 points' : `${points.toFixed(2)} / ${weight} points`}</dd>
                    <dd aria-hidden="true" className="col-span-2 mt-1 h-1.5 overflow-hidden rounded-full bg-chart-track">
                      {!missing && <div className="h-full rounded-full bg-accent" style={{ width: `${weight ? Math.min(100, (points / weight) * 100) : 0}%` }} />}
                    </dd>
                  </div>
                )
              })}
            </dl>
            {Object.keys(platform.probabilities ?? {}).length > 0 && (
              <details className="mt-4 text-sm">
                <summary className="cursor-pointer text-accent-text">Class probabilities</summary>
                <dl className="mt-3 space-y-2">
                  {Object.entries(platform.probabilities ?? {}).map(([key, value]) => (
                    <div key={key} className="flex justify-between gap-3 text-muted"><dt>P({key})</dt><dd className="tabular-nums">{percent(value)}</dd></div>
                  ))}
                </dl>
              </details>
            )}
          </Panel>
        ))}
      </div>
      <Panel>
        <details>
          <summary className="cursor-pointer text-sm font-medium">How the score is calculated</summary>
          <p className="mt-3 text-sm text-muted">{result.formula.missing_policy} The model contributes at most 10 points.</p>
          <ul className="mt-3 space-y-3 text-sm text-muted">
            {Object.entries(result.formula.explanations).map(([key, explanation]) => <li key={key}><strong className="text-foreground">{title(key)} ({result.formula.weights[key]} points):</strong> {explanation}</li>)}
          </ul>
          <p className="mt-3 text-xs text-subtle">Formula {result.formula.version} · Dataset {result.data_provenance.dataset_id}</p>
        </details>
      </Panel>
    </section>
  )
}
