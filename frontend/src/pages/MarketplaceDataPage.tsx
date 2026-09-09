/**
 * Marketplace Data (Phase 4).
 *
 * Collection form, per-platform collector status, and a table of the most
 * recent stored snapshots. Uses the existing visual system throughout — same
 * tokens, panels, Field and Button primitives. No charts: those are Phase 8.
 */

import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/Button'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { Icon } from '@/components/Icon'
import { StatusPill } from '@/components/StatusPill'
import { supportedPlatforms } from '@/config/dashboard'
import { useAuth } from '@/hooks/useAuth'
import { ApiRequestError } from '@/services/apiClient'
import * as dataService from '@/services/dataService'
import type {
  CollectResponse,
  CollectorStatus,
  Snapshot,
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
  const { token } = useAuth()

  const [status, setStatus] = useState<CollectorStatus | null>(null)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const [platform, setPlatform] = useState('amazon')
  const [keyword, setKeyword] = useState('')
  const [category, setCategory] = useState('')
  const [maxItems, setMaxItems] = useState('20')

  const [collecting, setCollecting] = useState(false)
  const [result, setResult] = useState<CollectResponse | null>(null)
  const [collectError, setCollectError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setLoadError(null)
    try {
      const [nextStatus, latest] = await Promise.all([
        dataService.fetchStatus(token),
        dataService.fetchLatest(token, { limit: 50 }),
      ])
      setStatus(nextStatus)
      setSnapshots(latest.items)
    } catch (error) {
      setLoadError(
        error instanceof ApiRequestError
          ? error.message
          : 'Could not load marketplace data.',
      )
    }
  }, [token])

  useEffect(() => {
    // loadStatus/load only set state after awaiting the request, so nothing
    // is set synchronously here; the rule cannot see across the async boundary.
    // oxlint-disable-next-line react/set-state-in-effect
    void load()
  }, [load])

  const handleCollect = async (event: React.FormEvent) => {
    event.preventDefault()
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
      const response = await dataService.collect(token!, {
        platform,
        keyword: trimmed,
        category: category.trim() || undefined,
        max_items: Number(maxItems) || 20,
      })
      setResult(response)
      await load()
    } catch (error) {
      setCollectError(
        error instanceof ApiRequestError
          ? error.message
          : 'Collection failed. Please try again.',
      )
    } finally {
      setCollecting(false)
    }
  }

  // Platform options come from the static supported list, not from the
  // status response: if that request fails the form must still be usable.
  // Status only enriches each option once it has loaded.
  const platforms = supportedPlatforms.map((name) => {
    const key = name.toLowerCase()
    return [key, status?.platforms[key] ?? null] as const
  })
  const selected = status?.platforms[platform] ?? null

  return (
    <DashboardLayout title="MarketPulse AI — Marketplace Data">
      {loadError && (
        <div className="mb-6">
          <FormAlert>{loadError}</FormAlert>
        </div>
      )}

      {/* Collector status */}
      <section aria-label="Collector status">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {platforms.map(([name, state]) => (
            <div
              key={name}
              className="rounded-panel border border-border-hair bg-surface p-5"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold capitalize">{name}</p>
                <StatusPill tone={state?.available ? 'ok' : 'idle'}>
                  {state === null
                    ? 'Loading…'
                    : state.available
                      ? 'Available'
                      : 'Unavailable'}
                </StatusPill>
              </div>

              <p className="mt-3 text-xs text-subtle">
                {state?.access_method ?? '—'}
              </p>

              {state?.reason && (
                <p className="mt-2 text-xs leading-relaxed text-muted">
                  {state.reason}
                </p>
              )}

              <dl className="mt-4 flex gap-5 text-xs">
                <div>
                  <dt className="text-subtle">Stored</dt>
                  <dd className="mt-0.5 font-mono tabular-nums">
                    {state?.stored_snapshots ?? '—'}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-subtle">Last collection</dt>
                  <dd className="mt-0.5 truncate font-mono">
                    {formatTimestamp(state?.last_collection ?? null)}
                  </dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      </section>

      {/* Collection form */}
      <section aria-label="Collect data" className="mt-6">
        <form
          noValidate
          onSubmit={handleCollect}
          className="rounded-panel border border-border-hair bg-surface p-7"
        >
          <h2 className="text-lg font-semibold">Refresh marketplace data</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Collection runs on demand against officially permitted sources only.
            A platform that cannot be collected reports why, rather than
            returning invented rows.
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
                className="mt-2 w-full rounded-card border border-border-hair bg-background px-3.5 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none"
              >
                {platforms.map(([name, state]) => (
                  <option key={name} value={name}>
                    {name}
                    {state && !state.available ? ' (unavailable)' : ''}
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
              className="mt-6 rounded-card border border-signal-ok/30 bg-signal-ok/10 px-4 py-3 text-sm text-signal-ok"
            >
              <p className="font-medium">
                {result.items_collected} item
                {result.items_collected === 1 ? '' : 's'} collected from{' '}
                {result.platform} at {formatTimestamp(result.collection_timestamp)}.
              </p>
              {(result.items_rejected > 0 || result.duplicates_skipped > 0) && (
                <p className="mt-1 text-xs">
                  {result.items_rejected} rejected, {result.duplicates_skipped}{' '}
                  duplicate(s) skipped.
                </p>
              )}
              {result.warnings.length > 0 && (
                <ul className="mt-2 list-disc space-y-1 pl-4 text-xs">
                  {/* Warnings repeat by design ("Skipped an item with no
                      title." once per item), so the index is the key. */}
                  {result.warnings.slice(0, 5).map((warning, index) => (
                    <li key={`${index}-${warning}`}>{warning}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="mt-7 flex flex-wrap items-center gap-4">
            <Button type="submit" size="lg" disabled={collecting}>
              <Icon name="refresh" className="size-4" />
              {collecting ? 'Collecting…' : 'Collect data'}
            </Button>
            {collecting && (
              <p className="text-sm text-muted" role="status">
                Contacting {platform}…
              </p>
            )}
          </div>
        </form>
      </section>

      {/* Latest records */}
      <section aria-label="Latest records" className="mt-6">
        <div className="rounded-panel border border-border-hair bg-surface">
          <div className="flex items-center justify-between gap-4 border-b border-border-hair px-6 py-4">
            <h2 className="text-sm font-semibold">
              Latest collected records
              <span className="ml-2 font-normal text-subtle">
                ({snapshots.length})
              </span>
            </h2>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex items-center gap-2 rounded-card px-3 py-1.5 text-xs text-muted transition-colors hover:bg-accent-soft hover:text-accent-text"
            >
              <Icon name="refresh" className="size-3.5" />
              Reload
            </button>
          </div>

          {snapshots.length === 0 ? (
            <p className="px-6 py-12 text-center text-sm text-muted">
              No marketplace data has been collected yet. Run a collection above
              to populate this table.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="border-b border-border-hair text-xs tracking-wider text-subtle uppercase">
                  <tr>
                    <th scope="col" className="px-6 py-3 font-medium">Product</th>
                    <th scope="col" className="px-4 py-3 font-medium">Platform</th>
                    <th scope="col" className="px-4 py-3 font-medium">Brand</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Price</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Was</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Off</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Rating</th>
                    <th scope="col" className="px-4 py-3 font-medium">Collected</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-border-hair/60 last:border-0 hover:bg-background-alt"
                    >
                      <td className="max-w-sm px-6 py-3">
                        {row.listing_url ? (
                          <a
                            href={row.listing_url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="line-clamp-2 hover:text-accent-text"
                          >
                            {row.product_name}
                          </a>
                        ) : (
                          <span className="line-clamp-2">{row.product_name}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 capitalize text-muted">{row.platform}</td>
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
            A dash means the source did not expose that field. Missing values are
            never filled in with estimates. Amazon&rsquo;s Product Advertising API
            does not return ratings or review counts, so those columns stay empty
            for Amazon rows.
          </p>
        </div>
      </section>
    </DashboardLayout>
  )
}
