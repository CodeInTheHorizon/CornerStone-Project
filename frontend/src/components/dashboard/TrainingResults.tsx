/**
 * Measured evaluation results for the active model.
 *
 * Two things this deliberately does: it shows the majority-class baseline
 * beside the accuracy, so a model that fails to beat guessing is visible as
 * such; and it surfaces the training warnings verbatim rather than tucking
 * them away.
 */

import { Icon } from '@/components/Icon'
import { SourceBadge } from '@/components/SourceBadge'
import { StatusPill } from '@/components/StatusPill'
import {
  BELOW_BASELINE_MESSAGE,
  DEMO_MODEL_MESSAGE,
  dateOnly,
  percentOrDash,
  qualityPresentation,
} from '@/lib/modelQuality'
import type { ModelMetrics, QualityReport } from '@/types/data'

function QualitySection({ quality, sources }: { quality: QualityReport; sources: string[] }) {
  const presentation = qualityPresentation[quality.quality_status]
  const usesDemo = quality.source_policy.uses_demo ?? sources.includes('demo')
  const probability = quality.probability_quality
  const data = quality.data_summary
  const baselines = quality.baselines
  const rows: [string, string][] = [
    ['Selected source types', (quality.source_policy.selected_source_types ?? []).map((s) => s.toUpperCase()).join(', ') || '—'],
    ['Labelled rows', `${data.labelled_rows ?? '—'} (${data.training_rows ?? '—'} train / ${data.validation_rows ?? '—'} validate)`],
    ['Observation dates', String(data.observation_dates ?? '—')],
    ['Unique products', String(data.unique_products ?? '—')],
    ['Split', quality.split.strategy ?? '—'],
    ['Split boundary', quality.split.boundary ? `${dateOnly(quality.split.boundary)} · ${quality.split.boundary_purged_rows ?? 0} boundary-crossing labels purged` : '—'],
    ['Majority baseline accuracy', percentOrDash(baselines.majority_baseline)],
    ['Training-majority accuracy', percentOrDash(baselines.training_majority_accuracy)],
    ['Previous-direction accuracy', percentOrDash(baselines.persistence_accuracy)],
    ['Calibration', `${quality.calibration_status} · ${probability.assessment?.replace(/_/g, ' ') ?? 'not measured'}`],
  ]

  return (
    <div className="mt-6 border-t border-border-hair pt-6">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-xs font-medium text-muted">Model quality</h3>
        <StatusPill tone={presentation.tone}>{presentation.label}</StatusPill>
      </div>

      {quality.quality_status === 'below_baseline' && (
        <p role="alert" className="mt-4 flex items-start gap-2.5 rounded-card border border-signal-down/30 bg-signal-down/10 px-4 py-3 text-sm font-semibold text-signal-down">
          <Icon name="alert" className="mt-0.5 size-4 shrink-0" />
          <span>{BELOW_BASELINE_MESSAGE}</span>
        </p>
      )}
      {usesDemo && (
        <p className="mt-3 flex items-start gap-2.5 rounded-card border border-signal-warn/30 bg-signal-warn/10 px-4 py-3 text-sm text-signal-warn">
          <Icon name="alert" className="mt-0.5 size-4 shrink-0" />
          <span>{DEMO_MODEL_MESSAGE}</span>
        </p>
      )}
      {quality.legacy && (
        <p className="mt-3 text-xs leading-relaxed text-signal-warn">
          Trained before the Phase 12 leakage fix: its labels were generated before the time split, so its
          validation score is overstated. Probabilities were never measured.
        </p>
      )}

      <dl className="mt-4 grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3 border-b border-border-hair/60 py-1.5">
            <dt className="text-subtle">{label}</dt>
            <dd className="text-right font-mono">{value}</dd>
          </div>
        ))}
      </dl>
      {probability.log_loss !== undefined && (
        <p className="mt-2 text-xs text-subtle">
          Log loss {probability.log_loss} vs class prior {probability.class_prior_log_loss} · Brier {probability.brier_score} · ECE {probability.expected_calibration_error} on {probability.rows} rows. Probabilities are not recalibrated.
        </p>
      )}
      {quality.quality_reasons.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-relaxed text-muted">
          {quality.quality_reasons.map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      )}
    </div>
  )
}

const METRIC_LABELS: Record<string, string> = {
  accuracy: 'Accuracy',
  f1_weighted: 'F1 (weighted)',
  f1_macro: 'F1 (macro)',
  precision_weighted: 'Precision',
  recall_weighted: 'Recall',
}

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`
}

export function TrainingResults({ metrics }: { metrics: ModelMetrics }) {
  const beatsBaseline =
    metrics.majority_baseline !== null &&
    typeof metrics.metrics.accuracy === 'number' &&
    metrics.metrics.accuracy > metrics.majority_baseline

  return (
    <div className="rounded-panel border border-border-hair bg-surface p-7">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-sm font-semibold">
          Evaluation
          <span className="ml-2 font-mono text-xs font-normal text-subtle">
            {metrics.selected_model} · {metrics.model_version}
          </span>
        </h2>
        <div className="flex flex-wrap gap-1.5">
          {metrics.dataset_source_types.map((type) => (
            <SourceBadge key={type} kind={type} />
          ))}
        </div>
      </div>

      <p className="mt-4 text-sm text-signal-warn">Experimental opportunity proxy, not actual sales demand. Validation performance does not establish reliability for marketplace decisions.</p>

      {/* Headline metrics */}
      <dl className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(METRIC_LABELS).map(([key, label]) =>
          typeof metrics.metrics[key] === 'number' ? (
            <div key={key}>
              <dt className="text-xs tracking-[0.14em] text-subtle uppercase">
                {label}
              </dt>
              <dd className="mt-2 text-2xl font-semibold tabular-nums">
                {percent(metrics.metrics[key])}
              </dd>
            </div>
          ) : null,
        )}
      </dl>

      {/* Baseline comparison — the honest read on whether this model learned */}
      <div
        className={`mt-6 flex items-start gap-2.5 rounded-card border px-4 py-3 text-sm ${
          beatsBaseline
            ? 'border-signal-ok/30 bg-signal-ok/10 text-signal-ok'
            : 'border-signal-warn/30 bg-signal-warn/10 text-signal-warn'
        }`}
      >
        <Icon
          name={beatsBaseline ? 'check' : 'alert'}
          className="mt-0.5 size-4 shrink-0"
        />
        <span>
          Always guessing the most common class scores{' '}
          <strong className="font-semibold">
            {percent(metrics.majority_baseline)}
          </strong>
          . This model scores{' '}
          <strong className="font-semibold">
            {percent(metrics.metrics.accuracy)}
          </strong>
          {beatsBaseline
            ? ' — it beats that constant guess. Check the quality status below before trusting it.'
            : ' — it is not beating that baseline, so it has found no usable signal in this data.'}
        </span>
      </div>

      {metrics.quality && <QualitySection quality={metrics.quality} sources={metrics.dataset_source_types} />}

      {metrics.warnings.length > 0 && (
        <ul className="mt-4 space-y-2">
          {metrics.warnings.map((warning, index) => (
            <li
              key={`${index}-${warning}`}
              className="flex items-start gap-2 text-xs leading-relaxed text-muted"
            >
              <Icon name="alert" className="mt-0.5 size-3.5 shrink-0" />
              <span>{warning}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Model comparison */}
      {metrics.all_models.length > 0 && (
        <div className="mt-7 border-t border-border-hair pt-6">
          <h3 className="text-xs font-medium text-muted">Models compared</h3>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[420px] text-left text-sm">
              <thead className="text-xs tracking-wider text-subtle uppercase">
                <tr>
                  <th scope="col" className="py-2 pr-4 font-medium">Model</th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">Accuracy</th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">F1 (weighted)</th>
                  <th scope="col" className="py-2 font-medium">Selected</th>
                </tr>
              </thead>
              <tbody>
                {metrics.all_models.map((run) => (
                  <tr key={run.model} className="border-t border-border-hair/60">
                    <td className="py-2.5 pr-4 font-mono text-xs">{run.model}</td>
                    <td className="py-2.5 pr-4 text-right font-mono tabular-nums">
                      {run.error ? '—' : percent(run.metrics.accuracy)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono tabular-nums">
                      {run.error ? '—' : percent(run.metrics.f1_weighted)}
                    </td>
                    <td className="py-2.5 text-xs">
                      {run.error ? (
                        <span className="text-signal-down">{run.error}</span>
                      ) : run.model === metrics.selected_model ? (
                        <span className="text-accent-text">✓</span>
                      ) : (
                        <span className="text-subtle">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {metrics.selection_rule && (
            <p className="mt-3 text-xs leading-relaxed text-subtle">
              {metrics.selection_rule}
            </p>
          )}
        </div>
      )}

      {/* Confusion matrix */}
      {metrics.confusion_matrix.length > 0 && (
        <div className="mt-7 border-t border-border-hair pt-6">
          <h3 className="text-xs font-medium text-muted">
            Confusion matrix
            <span className="ml-2 font-normal text-subtle">
              (rows = actual, columns = predicted)
            </span>
          </h3>
          <div className="mt-3 overflow-x-auto">
            <table className="text-left text-sm">
              <thead className="text-xs tracking-wider text-subtle uppercase">
                <tr>
                  <th scope="col" className="py-2 pr-4 font-medium" />
                  {metrics.confusion_labels.map((label) => (
                    <th key={label} scope="col" className="px-3 py-2 text-right font-medium">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metrics.confusion_matrix.map((row, index) => (
                  <tr
                    key={metrics.confusion_labels[index] ?? index}
                    className="border-t border-border-hair/60"
                  >
                    <th scope="row" className="py-2.5 pr-4 text-xs font-medium text-muted">
                      {metrics.confusion_labels[index]}
                    </th>
                    {row.map((count, columnIndex) => (
                      <td
                        key={columnIndex}
                        className={`px-3 py-2.5 text-right font-mono tabular-nums ${
                          index === columnIndex ? 'text-accent-text' : 'text-muted'
                        }`}
                      >
                        {count}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Provenance */}
      <dl className="mt-7 grid gap-4 border-t border-border-hair pt-6 text-xs sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-subtle">Target</dt>
          <dd className="mt-1 font-mono break-all">{metrics.target}</dd>
        </div>
        <div>
          <dt className="text-subtle">Split</dt>
          <dd className="mt-1">{metrics.split_strategy ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-subtle">Rows</dt>
          <dd className="mt-1 font-mono">
            {metrics.training_rows} train / {metrics.validation_rows} validate
          </dd>
        </div>
        <div>
          <dt className="text-subtle">Features</dt>
          <dd className="mt-1 font-mono">{metrics.feature_count}</dd>
        </div>
      </dl>

      {Object.keys(metrics.excluded_columns).length > 0 && (
        <details className="mt-5 text-xs">
          <summary className="cursor-pointer text-subtle hover:text-foreground">
            Columns excluded to prevent leakage (
            {Object.keys(metrics.excluded_columns).length})
          </summary>
          <ul className="mt-3 space-y-1.5 text-muted">
            {Object.entries(metrics.excluded_columns).map(([column, reason]) => (
              <li key={column}>
                <span className="font-mono">{column}</span> — {reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
