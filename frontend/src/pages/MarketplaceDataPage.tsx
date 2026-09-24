import { PermissionGate } from '@/components/PermissionGate'
import { can } from '@/auth/permissions'
/**
 * Marketplace Data (Phases 4, 4.5 and 11).
 *
 * Three ways data reaches the system, all converging on the same normalized
 * store: LIVE collection through official APIs, CSV/JSON import, and the
 * bundled demo fixture. Every row is labelled with its provenance, and every
 * platform card shows its collector state (LIVE ready, credentials missing,
 * approval required, rate limited, provider error, unavailable), so an
 * IMPORTED or DEMO record can never be mistaken for a live observation.
 *
 * Uses the existing visual system throughout. No charts: those are Phase 8.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/Button'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { Icon } from '@/components/Icon'
import { CollectorStateBadge } from '@/components/CollectorStateBadge'
import { collectorStateLabel } from '@/lib/collectorState'
import { SourceBadge } from '@/components/SourceBadge'
import { supportedPlatforms } from '@/config/dashboard'
import { useAuth } from '@/hooks/useAuth'
import { ApiRequestError } from '@/services/apiClient'
import * as dataService from '@/services/dataService'
import type {
  CollectResponse,
  CollectorStatus,
  IngestSummary,
  Snapshot,
  SourceType,
} from '@/types/data'

function formatTimestamp(value: string | null): string {
  if (!value) return 'Never'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString()
}

function formatMoney(value: number | null, currency: string): string {
  if (value === null) return '—'
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(value)
  } catch {
    return `${currency} ${value}`
  }
}

export function MarketplaceDataPage() {
  const { token, user } = useAuth()

  const [status, setStatus] = useState<CollectorStatus | null>(null)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const loadSequence = useRef(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [sourceFilter, setSourceFilter] = useState<SourceType | ''>('')

  // Collection
  // Flipkart is the only platform with a LIVE API integration.
  const [platform, setPlatform] = useState('flipkart')
  const [keyword, setKeyword] = useState('')
  const [category, setCategory] = useState('')
  const [maxItems, setMaxItems] = useState('10')
  const [collecting, setCollecting] = useState(false)
  const [result, setResult] = useState<CollectResponse | null>(null)
  const [collectError, setCollectError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)

  // Import / demo
  const fileInput = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<IngestSummary | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const [loadingDemo, setLoadingDemo] = useState(false)

  const load = useCallback(
    async (filter: SourceType | '' = sourceFilter) => {
      if (!token) return
      const sequence = ++loadSequence.current
      setLoading(true)
      setSnapshots([])
      setLoadError(null)
      try {
        const [nextStatus, latest] = await Promise.all([
          dataService.fetchStatus(token),
          dataService.fetchLatest(token, {
            limit: 50,
            sourceType: filter || undefined,
          }),
        ])
        if (sequence !== loadSequence.current) return
        setStatus(nextStatus)
        setSnapshots(latest.items)
      } catch (error) {
        if (sequence !== loadSequence.current) return
        setLoadError(
          error instanceof ApiRequestError
            ? error.message
            : 'Could not load marketplace data.',
        )
      } finally { if (sequence === loadSequence.current) setLoading(false) }
    },
    [token, sourceFilter],
  )

  useEffect(() => {
    // load only sets state after awaiting the request, so nothing is set
    // synchronously here; the rule cannot see across the async boundary.
    // oxlint-disable-next-line react/set-state-in-effect
    void load()
    return () => { loadSequence.current += 1 }
  }, [load])

  const handleCollect = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!can(user, "data:collect")) return
    setCollectError(null)
    setResult(null)

    const trimmed = keyword.trim()
    if (trimmed.length < 2) {
      setFieldError('Enter a product keyword of at least 2 characters.')
      return
    }
    setFieldError(null)

    setCollecting(true)
    try {
      setResult(
        await dataService.collect(token!, {
          platform,
          keyword: trimmed,
          category: category.trim() || undefined,
          max_items: Number(maxItems) || 10,
        }),
      )
      await load()
    } catch (error) {
      setCollectError(
        error instanceof ApiRequestError
          ? error.message
          : 'Collection failed. Please try again.',
      )
      // A failed fetch changes the collector's state (rate limited, provider
      // error, rejected credentials); show it without a manual reload.
      await load()
    } finally {
      setCollecting(false)
    }
  }

  const handleImport = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!can(user, "data:import")) return
    setImportError(null)
    setImportResult(null)

    if (!file) {
      setImportError('Choose a CSV or JSON file first.')
      return
    }

    if (file.size > 5 * 1024 * 1024) { setImportError('File must be at most 5 MB.'); return }
    setImporting(true)
    try {
      setImportResult(await dataService.importDataset(token!, file))
      setFile(null)
      if (fileInput.current) fileInput.current.value = ''
      await load()
    } catch (error) {
      setImportError(
        error instanceof ApiRequestError
          ? error.message
          : 'Import failed. Please try again.',
      )
    } finally {
      setImporting(false)
    }
  }

  const handleDemoLoad = async () => {
    if (!can(user, "data:demo")) return
    setImportError(null)
    setImportResult(null)
    setLoadingDemo(true)
    try {
      setImportResult(await dataService.loadDemoDataset(token!))
      await load()
    } catch (error) {
      setImportError(
        error instanceof ApiRequestError
          ? error.message
          : 'Could not load the demo dataset.',
      )
    } finally {
      setLoadingDemo(false)
    }
  }

  // Platform options come from the static supported list, not the status
  // response: if that request fails the form must still be usable.
  const platforms = supportedPlatforms.map((name) => {
    const key = name.toLowerCase()
    return [key, status?.platforms[key] ?? null] as const
  })
  const selected = status?.platforms[platform] ?? null
  const demo = status?.demo_dataset

  return (
    <DashboardLayout title="Marketplace Data">
      {loading && <p role="status" className="mb-4 text-sm text-muted">Loading stored marketplace data…</p>}
      {loadError && (
        <div className="mb-6">
          <FormAlert>{loadError}</FormAlert>
        </div>
      )}

      {/* Per-platform status */}
      <section aria-label="Platform status">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {platforms.map(([name, state]) => {
            // The header shows the collector's runtime STATE. What data is
            // stored is a separate line below, so a blocked platform holding
            // demo rows cannot read as live.
            const configurable = state && ['credentials_missing', 'approval_required', 'credentials_rejected'].includes(state.state)

            return (
              <div
                key={name}
                className="flex flex-col surface-card p-5"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold capitalize">{name}</p>
                  {state ? <CollectorStateBadge state={state.state} /> : <SourceBadge kind="unavailable" />}
                </div>

                <p className="mt-3 text-xs text-subtle">
                  {state
                    ? `${state.access_method} · ${state.ingestion_mode.replace(/_/g, ' ')}`
                    : 'Loading…'}
                </p>

                {state?.reason && (
                  <p className="mt-2 text-xs leading-relaxed text-muted">
                    {state.reason}
                  </p>
                )}

                {configurable && state.required_configuration.length > 0 && (
                  <div className="mt-2 text-[11px] leading-relaxed text-subtle">
                    <p>Backend environment variables (names only):</p>
                    <p className="mt-0.5 break-words font-mono">{state.required_configuration.join(', ')}</p>
                  </div>
                )}

                <div className="flex-1" />

                <dl className="mt-4 border-t border-border-hair pt-3 text-xs">
                  <div className="flex justify-between gap-3">
                    <dt className="text-subtle">Stored records</dt>
                    <dd className="font-mono tabular-nums">
                      {state?.stored_records ?? '—'}
                    </dd>
                  </div>
                  <div className="mt-1.5 flex justify-between gap-3">
                    <dt className="flex items-center gap-1.5 text-subtle">
                      <SourceBadge kind="live" /> records
                    </dt>
                    <dd className="font-mono tabular-nums">
                      {state?.live_records ?? '—'}
                    </dd>
                  </div>
                  <div className="mt-1.5 flex justify-between gap-3">
                    <dt className="text-subtle">Last successful LIVE fetch</dt>
                    <dd className="truncate font-mono">
                      {formatTimestamp(state?.last_successful_fetch ?? null)}
                    </dd>
                  </div>
                  {state?.last_failed_fetch && (
                    <div className="mt-1.5 flex justify-between gap-3">
                      <dt className="text-subtle">Last failed fetch</dt>
                      <dd className="truncate font-mono">
                        {formatTimestamp(state.last_failed_fetch)}
                      </dd>
                    </div>
                  )}
                  {state?.last_failed_fetch && state.last_failure_reason && (
                    <div className="mt-1">
                      <dt className="sr-only">Last failure reason</dt>
                      <dd className="leading-relaxed text-muted">
                        {state.last_failure_reason}
                      </dd>
                    </div>
                  )}
                  {state?.retry_after && (
                    <div className="mt-1.5 flex justify-between gap-3">
                      <dt className="text-subtle">Retry after</dt>
                      <dd className="truncate font-mono">
                        {formatTimestamp(state.retry_after)}
                      </dd>
                    </div>
                  )}
                  <div className="mt-1.5 flex justify-between gap-3">
                    <dt className="text-subtle">Newest stored observation</dt>
                    <dd className="truncate font-mono">
                      {formatTimestamp(state?.last_collection ?? null)}
                    </dd>
                  </div>
                  <div className="mt-2.5 flex items-center gap-2">
                    <dt className="text-subtle">Available data</dt>
                    <dd className="flex flex-wrap gap-1">
                      {state && state.source_types_available.length > 0 ? (
                        state.source_types_available.map((type) => (
                          <SourceBadge key={type} kind={type} />
                        ))
                      ) : (
                        <span className="text-xs text-subtle">No data yet</span>
                      )}
                    </dd>
                  </div>
                </dl>
              </div>
            )
          })}
        </div>
      </section>

      {/* Live collection */}
      <section aria-label="Collect data" className="mt-6">
        <PermissionGate permission="data:collect"><form
          noValidate
          onSubmit={handleCollect}
          className="surface-card p-5 sm:p-7"
        >
          <h2 className="text-lg font-semibold">Refresh LIVE market data</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Fetches new observations on demand through officially permitted APIs
            only, and appends them to the stored history. A platform that cannot be
            collected reports why, rather than returning invented rows. Refreshing
            never retrains a model.
          </p>

          <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label
                htmlFor="platform"
                className="block text-sm font-medium text-muted"
              >
                Platform
              </label>
              <select
                id="platform"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="mt-2 w-full rounded-card border border-border-hair bg-background px-3.5 py-2.5 text-sm text-foreground focus:border-accent"
              >
                {platforms.map(([name, state]) => (
                  <option key={name} value={name}>
                    {name}
                    {state ? ` (${collectorStateLabel(state.state).toLowerCase()})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <Field
              label="Product keyword"
              name="keyword"
              placeholder="wireless earbuds"
              value={keyword}
              onChange={(value) => {
                setKeyword(value)
                setFieldError(null)
              }}
              error={fieldError ?? undefined}
            />
            <Field
              label="Category (optional)"
              name="category"
              placeholder="Electronics"
              value={category}
              onChange={setCategory}
            />
            <Field
              label="Max items"
              name="max_items"
              type="number"
              value={maxItems}
              onChange={setMaxItems}
            />
          </div>

          {selected && !selected.available && selected.reason && (
            <div className="mt-6">
              <FormAlert tone="info">{selected.reason}</FormAlert>
            </div>
          )}

          {collectError && (
            <div className="mt-6">
              <FormAlert>{collectError}</FormAlert>
            </div>
          )}

          {result && (
            <div
              role="status"
              className={
                result.items_collected > 0
                  ? 'mt-6 rounded-card border border-signal-ok/30 bg-signal-ok/10 px-4 py-3 text-sm text-signal-ok'
                  : 'mt-6 rounded-card border border-border-hair bg-background-alt px-4 py-3 text-sm text-muted'
              }
            >
              <p className="flex flex-wrap items-center gap-2 font-medium">
                <SourceBadge kind={result.source_type} />
                <span>
                  {result.items_collected} new observation
                  {result.items_collected === 1 ? '' : 's'} stored from{' '}
                  {result.platform} at {formatTimestamp(result.collection_timestamp)}
                  {result.provider ? ` via ${result.provider}` : ''}.
                </span>
              </p>
              <p className="mt-1 text-xs">
                {result.items_received} received, {result.items_rejected} rejected,{' '}
                {result.duplicates_skipped} duplicate(s) skipped.
                {result.items_collected === 0 && ' No new data was stored.'}
              </p>
              {result.warnings.length > 0 && (
                <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs">
                  {result.warnings.slice(0, 5).map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="mt-7 flex flex-wrap items-center gap-4">
            <Button type="submit" size="lg" disabled={collecting || (selected !== null && !selected.available)}>
              <Icon name="refresh" className="size-4" />
              {collecting ? 'Fetching…' : 'Refresh Market Data'}
            </Button>
            {collecting && (
              <p className="text-sm text-muted" role="status">
                Contacting {platform}…
              </p>
            )}
          </div>
        </form></PermissionGate>
      </section>

      {/* Import + demo */}
      <section aria-label="Import data" className="mt-6">
        <div className="grid gap-5 lg:grid-cols-2">
          <PermissionGate permission="data:import"><form
            noValidate
            onSubmit={handleImport}
            className="surface-card p-5 sm:p-7"
          >
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">Import a dataset</h2>
              <SourceBadge kind="imported" />
            </div>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              Upload a CSV or JSON file of marketplace records. It goes through
              the same validation and deduplication as live collection, and is
              stored as IMPORTED — never as live data.
            </p>

            <div className="mt-6">
              <label
                htmlFor="dataset"
                className="block text-sm font-medium text-muted"
              >
                CSV or JSON file
              </label>
              <input
                id="dataset"
                ref={fileInput}
                type="file"
                accept=".csv,.json,text/csv,application/json"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null)
                  setImportError(null)
                }}
                className="mt-2 w-full rounded-card border border-border-hair bg-background px-3.5 py-2.5 text-sm text-foreground
                           file:mr-3 file:rounded-card file:border-0 file:bg-accent-soft file:px-3 file:py-1.5
                           file:text-xs file:font-medium file:text-accent-text focus:border-accent"
              />
              <p className="mt-2 text-xs leading-relaxed text-subtle">
                Needs at least <code className="font-mono">platform</code> and{' '}
                <code className="font-mono">product_name</code>. Common aliases
                (mrp, reviews, url, asin, timestamp) are recognised. Missing
                fields stay empty.
              </p>
            </div>

            <div className="mt-6">
              <Button type="submit" disabled={importing || !file}>
                <Icon name="database" className="size-4" />
                {importing ? 'Importing…' : 'Import file'}
              </Button>
            </div>
          </form></PermissionGate>

          <div className="surface-card p-5 sm:p-7">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">Demo dataset</h2>
              <SourceBadge kind="demo" />
            </div>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              A synthetic fixture for development and testing:{' '}
              {demo?.record_count ?? '—'} records across{' '}
              {demo?.platforms.length ?? '?'} platforms and{' '}
              {demo?.categories.length ?? '?'} categories, over several dates.
            </p>

            <p className="mt-4 rounded-card border border-border-strong bg-background-alt px-4 py-3 text-xs leading-relaxed text-muted">
              <strong className="font-semibold">Not real market data.</strong>{' '}
              Brands, prices, ratings and review counts are generated. Every row
              is stored as DEMO and is never shown as a live observation.
            </p>

            {demo && demo.loaded_records > 0 && (
              <p className="mt-4 text-xs text-subtle">
                Currently loaded: {demo.loaded_records} records. Loading again
                replaces them; live and imported data is untouched.
              </p>
            )}

            <div className="mt-6">
              <PermissionGate permission="data:demo"><Button
                type="button"
                variant="secondary"
                onClick={() => void handleDemoLoad()}
                disabled={loadingDemo || !demo?.available}
              >
                <Icon name="layers" className="size-4" />
                {loadingDemo ? 'Loading…' : 'Load demo dataset'}
              </Button></PermissionGate>
            </div>

            {demo && !demo.available && (
              <p className="mt-4 text-xs text-signal-warn">{demo.reason}</p>
            )}
          </div>
        </div>

        {importError && (
          <div className="mt-5">
            <FormAlert>{importError}</FormAlert>
          </div>
        )}

        {importResult && (
          <div
            role="status"
            className="mt-5 surface-card p-6"
          >
            <div className="flex flex-wrap items-center gap-3">
              <SourceBadge kind={importResult.source_type} />
              <p className="text-sm font-medium">
                {importResult.stored} record
                {importResult.stored === 1 ? '' : 's'} stored
              </p>
              <p className="text-xs text-subtle">
                {formatTimestamp(importResult.timestamp)}
              </p>
            </div>

            <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-xs">
              <div>
                <dt className="text-subtle">Rejected</dt>
                <dd className="mt-0.5 font-mono tabular-nums">
                  {importResult.rejected}
                </dd>
              </div>
              <div>
                <dt className="text-subtle">Duplicates</dt>
                <dd className="mt-0.5 font-mono tabular-nums">
                  {importResult.duplicates}
                </dd>
              </div>
              <div>
                <dt className="text-subtle">Platforms detected</dt>
                <dd className="mt-0.5 font-mono">
                  {importResult.platforms.join(', ') || '—'}
                </dd>
              </div>
            </dl>

            {importResult.rejected_rows.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-medium text-signal-down">
                  Rejected rows
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-muted">
                  {importResult.rejected_rows.slice(0, 10).map((row, index) => (
                    <li key={`${index}-${row}`}>{row}</li>
                  ))}
                </ul>
              </div>
            )}

            {importResult.warnings.length > 0 && (
              <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-subtle">
                {importResult.warnings.slice(0, 5).map((warning, index) => (
                  <li key={`${index}-${warning}`}>{warning}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {/* Stored records */}
      <section aria-label="Stored records" className="mt-6">
        <div className="surface-card">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-hair px-6 py-4">
            <h2 className="text-sm font-semibold">
              Latest stored records
              <span className="ml-2 font-normal text-subtle">
                ({snapshots.length})
              </span>
            </h2>

            <div className="flex items-center gap-2">
              <label htmlFor="source-filter" className="sr-only">
                Filter by source
              </label>
              <select
                id="source-filter"
                value={sourceFilter}
                onChange={(e) => {
                  const next = e.target.value as SourceType | ''
                  setSourceFilter(next)
                  void load(next)
                }}
                className="rounded-card border border-border-hair bg-background px-3 py-1.5 text-xs text-foreground focus:border-accent"
              >
                <option value="">All sources</option>
                <option value="live">Live only</option>
                <option value="imported">Imported only</option>
                <option value="demo">Demo only</option>
              </select>

              <button
                type="button"
                onClick={() => void load()}
                className="inline-flex items-center gap-2 rounded-card px-3 py-1.5 text-xs text-muted transition-colors hover:bg-accent-soft hover:text-accent-text"
              >
                <Icon name="refresh" className="size-3.5" />
                Reload
              </button>
            </div>
          </div>

          {!loading && snapshots.length === 0 ? (
            <p className="px-6 py-12 text-center text-sm text-muted">
              No marketplace data has been collected yet. Collect, import a file,
              or load the demo dataset above to populate this table.
            </p>
          ) : (
            <div className="overflow-x-auto" role="region" aria-label="Latest stored records table, scroll horizontally on small screens" tabIndex={0}>
              <table className="w-full min-w-[940px] text-left text-sm">
                <thead className="border-b border-border-hair text-xs tracking-wider text-subtle uppercase">
                  <tr>
                    <th scope="col" className="px-6 py-3 font-medium">Product</th>
                    <th scope="col" className="px-4 py-3 font-medium">Source</th>
                    <th scope="col" className="px-4 py-3 font-medium">Platform</th>
                    <th scope="col" className="px-4 py-3 font-medium">Brand</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Price</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Was</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Off</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Rating</th>
                    <th scope="col" className="px-4 py-3 font-medium">Observed</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-border-hair/60 last:border-0 hover:bg-background-alt"
                    >
                      <td className="max-w-sm px-6 py-3">
                        {row.listing_url && row.source_type === 'live' ? (
                          <a
                            href={row.listing_url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="line-clamp-2 hover:text-accent-text"
                          >
                            {row.product_name}
                          </a>
                        ) : (
                          // Imported and demo URLs are not necessarily
                          // reachable, so they are not offered as links.
                          <span className="line-clamp-2">{row.product_name}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <SourceBadge kind={row.source_type} />
                      </td>
                      <td className="px-4 py-3 capitalize text-muted">
                        {row.platform}
                      </td>
                      <td className="px-4 py-3 text-muted">{row.brand ?? '—'}</td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {formatMoney(row.price, row.currency)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums text-subtle">
                        {formatMoney(row.original_price, row.currency)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums text-muted">
                        {row.discount_percentage === null
                          ? '—'
                          : `${row.discount_percentage.toFixed(0)}%`}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums text-muted">
                        {row.rating === null ? '—' : row.rating}
                      </td>
                      <td className="px-4 py-3 text-xs whitespace-nowrap text-subtle">
                        {formatTimestamp(row.collection_timestamp)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="border-t border-border-hair px-6 py-3 text-xs leading-relaxed text-subtle">
            A dash means the source did not expose that field; missing values are
            never filled in with estimates. Amazon&rsquo;s Product Advertising
            API returns no ratings or review counts, so those stay empty for live
            Amazon rows. <strong className="font-semibold">DEMO</strong> rows are
            synthetic and <strong className="font-semibold">IMPORTED</strong>{' '}
            rows were supplied by you — neither was observed by this system.
          </p>
        </div>
      </section>
    </DashboardLayout>
  )
}
