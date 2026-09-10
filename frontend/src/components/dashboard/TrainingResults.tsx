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
import type { ModelMetrics } from '@/types/data'

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
            ? ' — it is doing better than guessing.'
            : ' — it is not beating that baseline, so it has found no usable signal in this data.'}
        </span>
      </div>

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
