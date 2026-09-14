import { can } from '@/auth/permissions'
import { PermissionGate } from '@/components/PermissionGate'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/Button'
import { CollectorStateBadge } from '@/components/CollectorStateBadge'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { collect } from '@/services/dataService'
import { useAuth } from '@/hooks/useAuth'
import type { RefreshSource } from '@/types/analytics'
import { title } from '@/lib/predictionFormat'

/**
 * Refresh Market Data: LIVE fetch -> validated, appended snapshots -> caller
 * reloads analytics. Never retrains a model and never claims fresh data when
 * nothing new was stored.
 */
export function MarketDataRefresh({
  sources,
  onRefresh,
  selectedProduct,
}: {
  sources: RefreshSource[] | null
  onRefresh: () => void
  /** Name of the product currently selected by the page, used as the default keyword. */
  selectedProduct?: string
}) {
  const { token, user } = useAuth()
  const [platform, setPlatform] = useState('')
  const [typedKeyword, setTypedKeyword] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const available = sources?.filter((item) => item.available) ?? []
  const keyword = typedKeyword ?? selectedProduct ?? ''
  const chosen = platform || (available.length === 1 ? available[0].platform : '')

  async function refresh() {
    if (!can(user, "data:collect") || !token || keyword.trim().length < 2 || !available.some((item) => item.platform === chosen)) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await collect(token, { platform: chosen, keyword: keyword.trim(), max_items: 10 })
      setMessage(result.items_collected > 0
        ? `Stored ${result.items_collected} new LIVE observation${result.items_collected === 1 ? '' : 's'} (${result.items_received} received, ${result.duplicates_skipped} duplicate). Reloading analytics from the updated history.`
        : `No new observations were stored (${result.items_received} received, ${result.duplicates_skipped} duplicate). No fresh-data success is claimed.`)
      onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Collection failed.')
      onRefresh() // reload collector state (rate limited, provider error)
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-3">
      {can(user, "data:collect") && available.length > 0 && <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm text-muted">LIVE collector<select aria-label="LIVE collector" className="mt-2 block w-full rounded-card border border-border-hair bg-background p-2.5" value={chosen} onChange={(event) => setPlatform(event.target.value)}><option value="">Select platform</option>{available.map((item) => <option key={item.platform} value={item.platform}>{title(item.platform)}</option>)}</select></label>
        <Field label="Product keyword to fetch" name="refresh-keyword" value={keyword} onChange={setTypedKeyword} />
      </div>}
      <div className="flex flex-wrap gap-3">
        <PermissionGate permission="data:collect"><Button variant="secondary" disabled={busy || keyword.trim().length < 2 || !available.some((item) => item.platform === chosen)} onClick={() => void refresh()}>{busy ? 'Fetching…' : 'Refresh Market Data'}</Button></PermissionGate>
        <Button variant="ghost" disabled={busy} onClick={onRefresh}>Reload stored analytics</Button>
        <Link to="/dashboard/marketplace-data" className="self-center text-sm text-accent-text">Collector status / import data</Link>
      </div>
      {available.length === 0 && <p className="text-sm text-muted">LIVE refresh unavailable. {sources ? 'No LIVE collector is configured and approved.' : 'Collector status could not be loaded yet.'}</p>}
      {sources?.filter((item) => !item.available).map((item) => (
        <div key={item.platform} className="text-xs text-subtle">
          <p className="flex flex-wrap items-center gap-2"><strong>{title(item.platform)}</strong><CollectorStateBadge state={item.state} /></p>
          <p className="mt-1 leading-relaxed">{item.reason ?? 'Collector unavailable.'}</p>
          {item.required_configuration.length > 0 && ['credentials_missing', 'approval_required'].includes(item.state) && (
            <p className="mt-0.5 break-words font-mono">Backend environment: {item.required_configuration.join(', ')}</p>
          )}
        </div>
      ))}
      {message && <p role="status" className="text-sm text-muted">{message}</p>}
      {error && <FormAlert>{error}</FormAlert>}
    </div>
  )
}
