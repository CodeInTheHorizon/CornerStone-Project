import { PermissionGate } from '@/components/PermissionGate'
import { can } from '@/auth/permissions'
/**
 * Train Model — dataset preparation (Phase 5) and training (Phase 6).
 *
 * Build the ML-ready dataset, then train and evaluate models on it. Every
 * metric shown is measured on a held-out validation split and reported
 * beside the majority-class baseline, so a model that has learned nothing
 * cannot look successful.
 */

import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/Button'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { Icon } from '@/components/Icon'
import { SourceBadge } from '@/components/SourceBadge'
import { supportedPlatforms } from '@/config/dashboard'
import { useAuth } from '@/hooks/useAuth'
import { ApiRequestError } from '@/services/apiClient'
import { TrainingResults } from '@/components/dashboard/TrainingResults'
import * as datasetService from '@/services/datasetService'
import * as trainingService from '@/services/trainingService'
import * as demandService from '@/services/demandService'
import type {
  DatasetBuildResponse,
  DatasetPreview,
  DatasetStatus,
  ModelMetrics,
  ModelStatus,
  SourceType,
} from '@/types/data'

const SOURCE_TYPES: SourceType[] = ['live', 'imported', 'demo']

/** Columns worth showing in a narrow preview; the dataset has many more. */
const PREVIEW_COLUMNS = [
  'platform',
  'source_type',
  'product_name',
  'category_normalized',
  'effective_price',
  'discount_percentage',
  'price_change_absolute',
  'review_growth',
  'competition_score',
  'short_term_price_trend',
]

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString()
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2)
  }
  return String(value)
}

export function TrainModelPage() {
  const { token, user } = useAuth()

  const [status, setStatus] = useState<DatasetStatus | null>(null)
  const [preview, setPreview] = useState<DatasetPreview | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [platforms, setPlatforms] = useState<string[]>([])
  const [sourceTypes, setSourceTypes] = useState<SourceType[]>(['demo'])
  const [category, setCategory] = useState('')

  const [building, setBuilding] = useState(false)
  const [result, setResult] = useState<DatasetBuildResponse | null>(null)
  const [buildError, setBuildError] = useState<string | null>(null)

  // Training
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null)
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null)
  const [selectedModels, setSelectedModels] = useState<string[]>([
    'random_forest',
    'xgboost',
  ])
  const [trainSourceChoice, setTrainSourceChoice] = useState<SourceType[] | null>(null)
  const [training, setTraining] = useState(false)
  const [trainError, setTrainError] = useState<string | null>(null)

  // Demand Forecasting state
  const [demandBenchmark, setDemandBenchmark] = useState<demandService.DemandBenchmarkSummary | null>(null)
  const [demandOutcome, setDemandOutcome] = useState<demandService.DemandTrainResponse | null>(null)
  const [trainingDemand, setTrainingDemand] = useState(false)
  const [demandTrainError, setDemandTrainError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setLoadingStatus(true)
    setLoadError(null)
    const outcomes = await Promise.allSettled([
      (async () => {
        const nextStatus = await datasetService.fetchDatasetStatus(token)
        setStatus(nextStatus)
        setPreview(nextStatus.has_dataset ? await datasetService.fetchDatasetPreview(token, 10) : null)
      })(),
      (async () => {
        const nextModel = await trainingService.fetchModelStatus(token)
        setModelStatus(nextModel)
        setMetrics(nextModel.trained ? await trainingService.fetchModelMetrics(token) : null)
      })(),
      (async () => {
        try {
          const bm = await demandService.fetchDemandBenchmark(token)
          setDemandBenchmark(bm)
        } catch { /* optional */ }
      })(),
    ])
    setLoadingStatus(false)
    const failures = outcomes.filter((outcome) => outcome.status === 'rejected')
    if (failures.length) setLoadError(failures.map((failure) => failure.reason instanceof Error ? failure.reason.message : 'Could not load status.').join(' '))

  }, [token])

  useEffect(() => {
    // load only sets state after awaiting the request, so nothing is set
    // synchronously here; the rule cannot see across the async boundary.
    // oxlint-disable-next-line react/set-state-in-effect
    void load()
  }, [load])

  const toggle = <T extends string>(
    list: T[],
    value: T,
    setter: (next: T[]) => void,
  ) => {
    setter(list.includes(value) ? list.filter((v) => v !== value) : [...list, value])
  }

  const handleBuild = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!can(user, "dataset:build")) return
    setBuildError(null)
    setResult(null)
    setBuilding(true)

    try {
      const response = await datasetService.buildDataset(token!, {
        platforms: platforms.length ? platforms : undefined,
        source_types: sourceTypes.length ? sourceTypes : undefined,
        categories: category.trim() ? [category.trim()] : undefined,
        persist: true,
      })
      setResult(response)
      // A new dataset resets the training provenance to what it contains.
      setTrainSourceChoice(null)
      await load()
    } catch (error) {
      setBuildError(
        error instanceof ApiRequestError
          ? error.message
          : 'Could not build the dataset.',
      )
    } finally {
      setBuilding(false)
    }
  }

  const handleTrain = async () => {
    if (!can(user, "model:train")) return
    setTrainError(null)
    if (!trainingSources.length) {
      setTrainError('Select the source types this model may be trained on.')
      return
    }
    setTraining(true)
    try {
      await trainingService.trainModel(token!, {
        dataset_id: 'latest',
        models: selectedModels.length ? selectedModels : undefined,
        source_types: trainingSources,
      })
      await load()
    } catch (error) {
      setTrainError(
        error instanceof ApiRequestError
          ? error.message
          : 'Training failed. Please try again.',
      )
    } finally {
      setTraining(false)
    }
  }

  const handleTrainDemand = async () => {
    if (!token) return
    setTrainingDemand(true)
    setDemandTrainError(null)
    try {
      const outcome = await demandService.trainDemandModels(token, 0.2)
      setDemandOutcome(outcome)
    } catch (err: unknown) {
      setDemandTrainError(err instanceof Error ? err.message : 'Demand training failed.')
    } finally {
      setTrainingDemand(false)
    }
  }

  const latest = result?.metadata ?? status?.latest ?? null
  const notice = result?.notice ?? status?.notice ?? null
  // Training provenance is chosen deliberately; it starts from what the
  // dataset actually contains and the backend rejects any mismatch.
  const trainingSources: SourceType[] = trainSourceChoice ?? latest?.source_types ?? []
  const datasetHasDemo = latest?.source_types.includes('demo') ?? false
  const previewColumns = preview
    ? PREVIEW_COLUMNS.filter((column) => preview.columns.includes(column))
    : []

  return (
    <DashboardLayout title={can(user, 'model:train') ? 'Train Model' : 'Datasets / Model Status'}>
      {loadingStatus && <p role="status" className="mb-4 text-sm text-muted">Loading dataset and model status…</p>}
      {loadError && (
        <div className="mb-6">
          <FormAlert>{loadError}</FormAlert>
        </div>
      )}

      {/* Build form */}
      <section aria-label="Dataset preparation">
        <PermissionGate permission="dataset:build"><form
          noValidate
          onSubmit={handleBuild}
          className="surface-card p-5 sm:p-7"
        >
          <h2 className="text-lg font-semibold">Dataset preparation</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
            Turns stored marketplace snapshots into an ML-ready table: cleaned,
            normalized, deduplicated and enriched with price, review and
            competition features. Source types are never mixed silently — what
            you select here is recorded in the dataset metadata.
          </p>

          <fieldset className="mt-6">
            <legend className="text-sm font-medium text-muted">
              Source types
            </legend>
            <div className="mt-3 flex flex-wrap gap-2">
              {SOURCE_TYPES.map((type) => {
                const active = sourceTypes.includes(type)
                return (
                  <button
                    key={type}
                    type="button"
                    aria-pressed={active}
                    onClick={() => toggle(sourceTypes, type, setSourceTypes)}
                    className={`inline-flex items-center gap-2 rounded-card border px-3.5 py-2 text-sm transition-colors ${
                      active
                        ? 'border-accent bg-accent-soft text-accent-text'
                        : 'border-border-hair text-muted hover:border-border-strong'
                    }`}
                  >
                    <SourceBadge kind={type} />
                  </button>
                )
              })}
            </div>
            <p className="mt-2 text-xs text-subtle">
              Leave all unselected to include every source type.
            </p>
          </fieldset>

          <fieldset className="mt-6">
            <legend className="text-sm font-medium text-muted">Platforms</legend>
            <div className="mt-3 flex flex-wrap gap-2">
              {supportedPlatforms.map((name) => {
                const key = name.toLowerCase()
                const active = platforms.includes(key)
                return (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => toggle(platforms, key, setPlatforms)}
                    className={`rounded-card border px-3.5 py-2 text-sm transition-colors ${
                      active
                        ? 'border-accent bg-accent-soft text-accent-text'
                        : 'border-border-hair text-muted hover:border-border-strong'
                    }`}
                  >
                    {name}
                  </button>
                )
              })}
            </div>
            <p className="mt-2 text-xs text-subtle">
              Leave all unselected to include every platform.
            </p>
          </fieldset>

          <div className="mt-6 max-w-sm">
            <Field
              label="Category (optional)"
              name="category"
              placeholder="wireless earbuds"
              value={category}
              onChange={setCategory}
            />
          </div>

          {buildError && (
            <div className="mt-6">
              <FormAlert>{buildError}</FormAlert>
            </div>
          )}

          <div className="mt-7 flex flex-wrap items-center gap-4">
            <Button type="submit" size="lg" disabled={building}>
              <Icon name="layers" className="size-4" />
              {building ? 'Building…' : 'Build Dataset'}
            </Button>
            {building && (
              <p role="status" className="text-sm text-muted">
                Cleaning and engineering features…
              </p>
            )}
          </div>
        </form></PermissionGate>
      </section>

      {/* Demo warning — required whenever synthetic rows are present */}
      {notice && (
        <section className="mt-6">
          <p
            role="status"
            className="flex items-start gap-2.5 rounded-panel border border-signal-warn/30 bg-signal-warn/10 px-5 py-4 text-sm text-signal-warn"
          >
            <Icon name="alert" className="mt-0.5 size-4 shrink-0" />
            <span>{notice}</span>
          </p>
        </section>
      )}

      {/* Dataset summary */}
      {latest && (
        <section aria-label="Dataset summary" className="mt-6">
          <div className="surface-card p-5 sm:p-7">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="text-sm font-semibold">
                Latest dataset
                <span className="ml-2 font-mono text-xs font-normal text-subtle">
                  {latest.dataset_id}
                </span>
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {latest.source_types.map((type) => (
                  <SourceBadge key={type} kind={type} />
                ))}
              </div>
            </div>

            <dl className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ['Rows processed', latest.total_output_rows],
                ['Rows removed', latest.removed_rows],
                ['Features', latest.feature_count],
                ['Products', latest.products],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-xs tracking-[0.14em] text-subtle uppercase">
                    {label}
                  </dt>
                  <dd className="mt-2 text-2xl font-semibold tabular-nums">
                    {String(value)}
                  </dd>
                </div>
              ))}
            </dl>

            <dl className="mt-6 grid gap-4 border-t border-border-hair pt-5 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-xs text-subtle">Generated</dt>
                <dd className="mt-1 font-mono text-xs">
                  {formatTimestamp(latest.generated_at)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-subtle">Input rows</dt>
                <dd className="mt-1 font-mono text-xs">
                  {latest.total_input_rows}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-subtle">Platforms</dt>
                <dd className="mt-1 text-xs">
                  {latest.platforms.join(', ') || '—'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-subtle">Date range</dt>
                <dd className="mt-1 font-mono text-xs">
                  {latest.date_range.start
                    ? `${latest.date_range.start.slice(0, 10)} → ${latest.date_range.end?.slice(0, 10)}`
                    : '—'}
                </dd>
              </div>
            </dl>

            {Object.keys(latest.removal_reasons).length > 0 && (
              <div className="mt-6 border-t border-border-hair pt-5">
                <p className="text-xs font-medium text-muted">
                  Why rows were removed or repaired
                </p>
                <ul className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-subtle">
                  {Object.entries(latest.removal_reasons).map(([reason, count]) => (
                    <li key={reason}>
                      <span className="font-mono">{reason}</span>: {count}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {latest.csv_path && (
              <p className="mt-5 text-xs break-all text-subtle">
                Saved to <span className="font-mono">{latest.csv_path}</span>
              </p>
            )}
          </div>
        </section>
      )}

      {/* Preview */}
      {preview && preview.rows.length > 0 && (
        <section aria-label="Dataset preview" className="mt-6">
          <div className="surface-card">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-hair px-6 py-4">
              <h2 className="text-sm font-semibold">
                Preview
                <span className="ml-2 font-normal text-subtle">
                  (first {preview.rows.length} of {preview.total_rows} rows)
                </span>
              </h2>
            </div>

            <div className="overflow-x-auto" role="region" aria-label="Dataset preview table, scroll horizontally on small screens" tabIndex={0}>
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="border-b border-border-hair text-xs tracking-wider text-subtle uppercase">
                  <tr>
                    {previewColumns.map((column) => (
                      <th key={column} scope="col" className="px-4 py-3 font-medium">
                        {column.replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, index) => (
                    <tr
                      key={String(row.snapshot_id ?? index)}
                      className="border-b border-border-hair/60 last:border-0 hover:bg-background-alt"
                    >
                      {previewColumns.map((column) => (
                        <td
                          key={column}
                          className={`px-4 py-3 ${
                            typeof row[column] === 'number'
                              ? 'text-right font-mono tabular-nums'
                              : 'text-muted'
                          }`}
                        >
                          {column === 'source_type' ? (
                            <SourceBadge kind={row[column] as SourceType} />
                          ) : (
                            formatCell(row[column])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="border-t border-border-hair px-6 py-3 text-xs leading-relaxed text-subtle">
              A dash is a genuinely unknown value, not a zero. Change and trend
              features are empty for a listing&rsquo;s first observations,
              because no earlier reading exists to compare against.
            </p>
          </div>
        </section>
      )}

      {/* Training */}
      <section aria-label="Model training" className="mt-6">
        <PermissionGate permission="model:train"><div className="surface-card p-5 sm:p-7">
          <h2 className="text-lg font-semibold">Model training</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
            Trains on the dataset above and reports measured validation
            metrics against naive baselines. The split is temporal and
            boundary-first: a date boundary is fixed, then each side is labelled
            separately, so no training label comes from a validation-period price.
            The target is the direction of a listing&rsquo;s next price, an
            opportunity proxy, not sales demand.
          </p>

          <fieldset className="mt-6">
            <legend className="text-sm font-medium text-muted">Training source types</legend>
            <p className="mt-1 text-xs text-subtle">
              Must match the dataset&rsquo;s provenance. DEMO cannot be combined with IMPORTED or LIVE.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(['demo', 'imported', 'live'] as SourceType[]).map((type) => {
                const active = trainingSources.includes(type)
                return (
                  <button
                    key={type}
                    type="button"
                    aria-pressed={active}
                    onClick={() => toggle(trainingSources, type, (next) => setTrainSourceChoice(next))}
                    className={`rounded-card border px-3.5 py-2 transition-colors ${
                      active ? 'border-accent bg-accent-soft' : 'border-border-hair hover:border-border-strong'
                    }`}
                  >
                    <SourceBadge kind={type} />
                  </button>
                )
              })}
            </div>
            {latest && (
              <p className="mt-2 text-xs text-subtle">
                Dataset {latest.dataset_id} contains: {latest.source_types.map((type) => type.toUpperCase()).join(', ') || 'unknown'}.
              </p>
            )}
            {datasetHasDemo && trainingSources.includes('demo') && (
              <p className="mt-2 text-xs text-signal-warn">
                Development model — trained on synthetic DEMO data.
              </p>
            )}
          </fieldset>

          <fieldset className="mt-6">
            <legend className="text-sm font-medium text-muted">Models</legend>
            <div className="mt-3 flex flex-wrap gap-2">
              {(modelStatus?.available_models ?? ['random_forest']).map((name) => {
                const unavailable =
                  name === 'xgboost' && modelStatus?.xgboost_available === false
                const active = selectedModels.includes(name)
                return (
                  <button
                    key={name}
                    type="button"
                    disabled={unavailable}
                    aria-pressed={active}
                    onClick={() => toggle(selectedModels, name, setSelectedModels)}
                    className={`rounded-card border px-3.5 py-2 text-sm transition-colors disabled:opacity-50 ${
                      active && !unavailable
                        ? 'border-accent bg-accent-soft text-accent-text'
                        : 'border-border-hair text-muted hover:border-border-strong'
                    }`}
                  >
                    {name.replace(/_/g, ' ')}
                    {unavailable && ' (unavailable)'}
                  </button>
                )
              })}
            </div>
          </fieldset>

          {trainError && (
            <div className="mt-6">
              <FormAlert>{trainError}</FormAlert>
            </div>
          )}

          <div className="mt-7 flex flex-wrap items-center gap-4">
            <Button
              type="button"
              size="lg"
              onClick={() => void handleTrain()}
              disabled={training || building || loadingStatus || !status?.has_dataset || !selectedModels.length}
            >
              <Icon name="target" className="size-4" />
              {training ? 'Training…' : 'Train Model'}
            </Button>
            {training && (
              <p role="status" className="text-sm text-muted">
                Fitting and evaluating models…
              </p>
            )}
            {!loadingStatus && !status?.has_dataset && (
              <p className="text-sm text-subtle">Build a dataset first.</p>
            )}
          </div>

          {modelStatus?.notice && (
            <p
              role="status"
              className="mt-6 flex items-start gap-2.5 rounded-card border border-signal-warn/30 bg-signal-warn/10 px-4 py-3 text-sm text-signal-warn"
            >
              <Icon name="alert" className="mt-0.5 size-4 shrink-0" />
              <span>{modelStatus.notice}</span>
            </p>
          )}
        </div>
      </PermissionGate></section>

      {metrics && (
        <section aria-label="Evaluation" className="mt-6">
          <TrainingResults metrics={metrics} />
        </section>
      )}

      {modelStatus && modelStatus.history.length > 0 && (
        <section aria-label="Training history" className="mt-6">
          <div className="surface-card">
            <div className="border-b border-border-hair px-6 py-4">
              <h2 className="text-sm font-semibold">Training history</h2>
            </div>
            <div className="overflow-x-auto" role="region" aria-label="Training history table, scroll horizontally on small screens" tabIndex={0}>
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="border-b border-border-hair text-xs tracking-wider text-subtle uppercase">
                  <tr>
                    <th scope="col" className="px-6 py-3 font-medium">Version</th>
                    <th scope="col" className="px-4 py-3 font-medium">Model</th>
                    <th scope="col" className="px-4 py-3 font-medium">Trained</th>
                    <th scope="col" className="px-4 py-3 font-medium">Dataset</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">F1</th>
                    <th scope="col" className="px-4 py-3 font-medium">Quality</th>
                    <th scope="col" className="px-4 py-3 font-medium">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {modelStatus.history.map((run) => (
                    <tr
                      key={run.model_version}
                      className="border-b border-border-hair/60 last:border-0"
                    >
                      <td className="px-6 py-3 font-mono text-xs">
                        {run.model_version}
                      </td>
                      <td className="px-4 py-3 text-muted">{run.model_type ?? '—'}</td>
                      <td className="px-4 py-3 text-xs text-subtle">
                        {formatTimestamp(run.trained_at)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-subtle">
                        {run.dataset_id?.slice(0, 8) ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {run.f1_weighted === null
                          ? '—'
                          : `${(run.f1_weighted * 100).toFixed(1)}%`}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted">
                        {run.quality_status?.replace(/_/g, ' ') ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {run.is_active ? (
                          <span className="text-accent-text">active</span>
                        ) : (
                          <span className="text-subtle">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* Demand Forecasting Engine Section */}
      <section aria-label="Demand Forecasting Engine" className="mt-8">
        <div className="surface-card p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">Sales Demand Forecasting Engine (Supervised Regression)</h2>
              <p className="mt-1 text-xs text-muted">
                Benchmark, train, and evaluate regression models on chronological holdout data to forecast true units sold without temporal leakage.
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleTrainDemand()}
              disabled={trainingDemand}
            >
              <Icon name="target" className="size-4" />
              {trainingDemand ? 'Fitting Regression Models…' : 'Train & Benchmark Demand Models'}
            </Button>
          </div>

          {demandTrainError && (
            <div className="mt-4">
              <FormAlert>{demandTrainError}</FormAlert>
            </div>
          )}

          {/* Benchmark dataset summary */}
          {demandBenchmark && (
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-card border border-border-hair bg-background-alt/50 p-3 text-xs">
                <span className="text-subtle">Historical Sales Dataset</span>
                <p className="mt-1 font-semibold text-foreground">{demandBenchmark.total_records.toLocaleString()} records</p>
                <p className="text-[11px] text-muted">Multi-platform benchmark</p>
              </div>
              <div className="rounded-card border border-border-hair bg-background-alt/50 p-3 text-xs">
                <span className="text-subtle">Total Units Sold</span>
                <p className="mt-1 font-semibold text-foreground">{demandBenchmark.total_units_sold.toLocaleString()} units</p>
                <p className="text-[11px] text-muted">Target: units_sold</p>
              </div>
              <div className="rounded-card border border-border-hair bg-background-alt/50 p-3 text-xs">
                <span className="text-subtle">Average Market Price</span>
                <p className="mt-1 font-semibold text-foreground">₹{demandBenchmark.average_price.toLocaleString()}</p>
                <p className="text-[11px] text-muted">Median: {demandBenchmark.median_units_sold} units/day</p>
              </div>
              <div className="rounded-card border border-border-hair bg-background-alt/50 p-3 text-xs">
                <span className="text-subtle">Platforms Evaluated</span>
                <p className="mt-1 font-semibold capitalize text-foreground">{demandBenchmark.platforms.join(', ')}</p>
                <p className="text-[11px] text-muted">Verified sales history</p>
              </div>
            </div>
          )}

          {/* Results Comparison Table */}
          {demandOutcome && (
            <div className="mt-6 space-y-4 border-t border-border-hair/60 pt-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-semibold text-subtle uppercase tracking-wider">
                  Winning Model: <span className="text-accent-text">{demandOutcome.selected_model}</span>
                </span>
                <span className="text-xs text-muted">
                  {demandOutcome.temporal_split}
                </span>
              </div>

              <div className="overflow-x-auto rounded-card border border-border-hair">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-border-hair bg-background-alt text-subtle">
                      <th className="px-4 py-3 font-medium">Candidate Algorithm</th>
                      <th className="px-4 py-3 text-right font-medium">MAE (Units)</th>
                      <th className="px-4 py-3 text-right font-medium">RMSE</th>
                      <th className="px-4 py-3 text-right font-medium">WAPE (%)</th>
                      <th className="px-4 py-3 text-right font-medium">R²</th>
                      <th className="px-4 py-3 text-center font-medium">Selection</th>
                    </tr>
                  </thead>
                  <tbody>
                    {demandOutcome.candidates.map((cand) => {
                      const isSelected = cand.algorithm === demandOutcome.selected_model
                      return (
                        <tr key={cand.name} className="border-b border-border-hair/50 last:border-0">
                          <td className="px-4 py-3 font-medium text-foreground">{cand.algorithm}</td>
                          <td className="px-4 py-3 text-right text-muted">{cand.metrics.mae.toFixed(2)}</td>
                          <td className="px-4 py-3 text-right text-muted">{cand.metrics.rmse.toFixed(2)}</td>
                          <td className="px-4 py-3 text-right font-semibold text-foreground">
                            {(cand.metrics.wape * 100).toFixed(1)}%
                          </td>
                          <td className="px-4 py-3 text-right text-muted">{cand.metrics.r2.toFixed(3)}</td>
                          <td className="px-4 py-3 text-center">
                            {isSelected ? (
                              <span className="rounded-full bg-green-500/10 px-2 py-0.5 text-[11px] font-bold text-green-600 dark:text-green-400">
                                Winner
                              </span>
                            ) : (
                              <span className="text-subtle">Evaluated</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] text-subtle">
                Trained on {demandOutcome.training_rows} records and validated on {demandOutcome.validation_rows} future periods. Selection rule: Lowest WAPE, breaking ties with MAE.
              </p>
            </div>
          )}
        </div>
      </section>
    </DashboardLayout>
  )
}
