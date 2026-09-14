import { FormAlert } from '@/components/FormAlert'
import { Link } from 'react-router-dom'
import { Panel } from '@/components/Panel'
import { SourceBadge } from '@/components/SourceBadge'
import { StatusPill } from '@/components/StatusPill'
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
        {title(model.type ?? 'Unknown model')} {model.version} · Validation accuracy <strong>{percent(model.accuracy)}</strong>
        {' '}vs majority baseline accuracy <strong>{percent(model.majority_baseline)}</strong>
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
  return (
    <section aria-label="Prediction results" className="space-y-5">
      <Panel>
        <p className="text-xs text-subtle">Saved result #{result.id} · {timestamp(result.created_at)}</p>
        <h2 className="mt-2 text-xl font-semibold">{result.product}</h2>
        <div className="mt-4"><QualityContext model={result.model} /></div>
        <p className="mt-3 text-sm text-muted">{result.warning}</p>
        <p className="mt-5 text-sm text-muted">{result.recommendation_label}</p>
        <p className="mt-1 text-2xl font-semibold">{title(result.recommended_platform)} <span className="text-accent-text">{top?.opportunity_score?.toFixed(1)} / 100</span></p>
        <p className="mt-2 text-sm text-muted">
          {result.score_difference === null ? 'Only one platform could be evaluated.' : result.score_difference === 0 ? 'Tied top score. Display order uses platform name.' : `${result.score_difference.toFixed(1)} points above the next platform.`}
        </p>
        <p className="mt-2 text-xs text-subtle">These scores are heuristic comparisons of recorded signals, not success probabilities or profit estimates.</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
          Input dataset: {result.data_provenance.source_types.map((source) => <SourceBadge key={source} kind={source} />)}
        </div>
        <Link to={`/dashboard/trends?product_key=${encodeURIComponent(result.product_key)}`} className="mt-4 inline-block text-sm text-accent-text">View this product’s stored trend history</Link>
        <p className="mt-1 text-xs text-subtle">Trend history uses current stored snapshots; it does not change this saved prediction.</p>
      </Panel>

      <Panel>
        <h3 className="font-semibold">Marketplace comparison</h3>
        <p className="mt-2 text-sm text-muted">Fixed 0–100 scale. Missing signals earn no points; compare coverage and observation dates.</p>
        <div className="mt-5 space-y-5">
          {result.platform_results.map((platform) => (
            <div key={platform.platform}>
              <div className="mb-2 flex flex-wrap justify-between gap-2 text-sm">
                <span className="font-medium">{title(platform.platform)}</span>
                <span>{platform.opportunity_score == null ? 'Insufficient data / unavailable' : `${platform.opportunity_score.toFixed(1)} / 100 · ${platform.coverage_weight}% signal coverage`}</span>
              </div>
              {platform.opportunity_score != null ? (
                <div role="meter" aria-label={`${title(platform.platform)} opportunity score`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={platform.opportunity_score} className="h-3 overflow-hidden rounded-full bg-background-alt">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${platform.opportunity_score}%` }} />
                </div>
              ) : <p className="text-xs text-subtle">{platform.reason}</p>}
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        {result.ranking.map((platform, index) => (
          <Panel key={platform.platform}>
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold">{index + 1}. {title(platform.platform)}</h3>
              {platform.source_type && <SourceBadge kind={platform.source_type} />}
            </div>
            <p className="mt-3 text-sm">Price-direction class: <strong>{title(platform.predicted_class ?? 'Unavailable')}</strong></p>
            <p className="mt-1 text-sm text-muted">Class probability: {percent(platform.confidence)} · {platform.model_version}</p>
            <p className="mt-1 text-xs text-subtle">Uncalibrated model probability; not reliability or likelihood of marketplace success.</p>
            <p className="mt-3 text-xs text-muted">Observed: {timestamp(platform.data_freshness)}{platform.stale ? ' · STALE' : ''}</p>
            <p className="mt-3 text-xs leading-relaxed text-signal-warn">{platform.warning}</p>
            <p className="mt-3 text-sm text-muted">Top contributions: {platform.key_factors.map(title).join(', ')}</p>
            <details className="mt-4 text-sm">
              <summary className="cursor-pointer text-accent-text">Score contributions and class probabilities</summary>
              <dl className="mt-3 space-y-2">
                {Object.entries(platform.components).map(([key, points]) => (
                  <div key={key} className="flex justify-between gap-3 text-muted">
                    <dt>{title(key)}</dt><dd>{platform.missing_components.includes(key) ? 'Missing · 0 points' : `${points.toFixed(2)} / ${result.formula.weights[key]} points`}</dd>
                  </div>
                ))}
                {Object.entries(platform.probabilities ?? {}).map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-3 text-muted"><dt>P({key})</dt><dd>{percent(value)}</dd></div>
                ))}
              </dl>
            </details>
          </Panel>
        ))}
      </div>
      <Panel>
        <details>
          <summary className="cursor-pointer text-sm font-medium">How the score is calculated</summary>
          <p className="mt-3 text-sm text-muted">{result.formula.missing_policy} The model contributes at most 10 points.</p>
          <ul className="mt-3 space-y-3 text-sm text-muted">
            {Object.entries(result.formula.explanations).map(([key, explanation]) => <li key={key}><strong>{title(key)} ({result.formula.weights[key]} points):</strong> {explanation}</li>)}
          </ul>
          <p className="mt-3 text-xs text-subtle">Formula {result.formula.version} · Dataset {result.data_provenance.dataset_id}</p>
        </details>
      </Panel>
    </section>
  )
}
