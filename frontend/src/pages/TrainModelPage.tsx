/**
 * Train Model — Dataset Preparation (Phase 5).
 *
 * Builds the ML-ready dataset and shows what came out. Training itself is
 * Phase 6: the action below is present but explicitly inactive, so the
 * workflow is visible without implying it works.
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
import * as datasetService from '@/services/datasetService'
import type {
  DatasetBuildResponse,
  DatasetPreview,
  DatasetStatus,
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
  const { token } = useAuth()

  const [status, setStatus] = useState<DatasetStatus | null>(null)
  const [preview, setPreview] = useState<DatasetPreview | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [platforms, setPlatforms] = useState<string[]>([])
  const [sourceTypes, setSourceTypes] = useState<SourceType[]>(['demo'])
  const [category, setCategory] = useState('')

  const [building, setBuilding] = useState(false)
  const [result, setResult] = useState<DatasetBuildResponse | null>(null)
  const [buildError, setBuildError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setLoadError(null)
    try {
      const nextStatus = await datasetService.fetchDatasetStatus(token)
      setStatus(nextStatus)
      if (nextStatus.has_dataset) {
        setPreview(await datasetService.fetchDatasetPreview(token, 10))
      }
    } catch (error) {
      setLoadError(
        error instanceof ApiRequestError
          ? error.message
          : 'Could not load dataset status.',
      )
    }
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

  const latest = result?.metadata ?? status?.latest ?? null
  const notice = result?.notice ?? status?.notice ?? null
  const previewColumns = preview
    ? PREVIEW_COLUMNS.filter((column) => preview.columns.includes(column))
    : []

  return (
    <DashboardLayout title="MarketPulse AI — Train Model">
      {loadError && (
        <div className="mb-6">
          <FormAlert>{loadError}</FormAlert>
        </div>
      )}

      {/* Build form */}
      <section aria-label="Dataset preparation">
        <form
          noValidate
          onSubmit={handleBuild}
          className="rounded-panel border border-border-hair bg-surface p-7"
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
        </form>
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
          <div className="rounded-panel border border-border-hair bg-surface p-7">
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
          <div className="rounded-panel border border-border-hair bg-surface">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-hair px-6 py-4">
              <h2 className="text-sm font-semibold">
                Preview
                <span className="ml-2 font-normal text-subtle">
                  (first {preview.rows.length} of {preview.total_rows} rows)
                </span>
              </h2>
            </div>

            <div className="overflow-x-auto">
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

      {/* Training is Phase 6 */}
      <section className="mt-6">
        <div className="rounded-panel border border-border-hair bg-background-alt p-7">
          <h2 className="text-sm font-semibold">Model training</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
            Training runs on the dataset above and records its measured
            accuracy. It is not built yet — this phase produces the dataset
            only.
          </p>
          <div className="mt-5">
            <Button variant="secondary" disabled>
              Train Model
            </Button>
          </div>
        </div>
      </section>
    </DashboardLayout>
  )
}
