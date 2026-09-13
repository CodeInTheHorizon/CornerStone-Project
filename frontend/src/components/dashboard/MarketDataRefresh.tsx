import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/Button'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { collect } from '@/services/dataService'
import { useAuth } from '@/hooks/useAuth'
import type { RefreshSource } from '@/types/analytics'
import { title } from '@/lib/predictionFormat'

/** Future live connector hook: collect -> stored snapshots -> caller refetches analytics. */
export function MarketDataRefresh({ sources, onRefresh }: { sources: RefreshSource[] | null; onRefresh: () => void }) {
  const { token } = useAuth()
  const [platform, setPlatform] = useState('')
  const [keyword, setKeyword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const available = sources?.filter((item) => item.available) ?? []
  async function refresh() {
    if (!token || !keyword.trim() || !available.some((item) => item.platform === platform)) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await collect(token, { platform, keyword: keyword.trim(), max_items: 20 })
      setMessage(result.items_collected > 0 ? `Stored ${result.items_collected} observations. Reloading analytics from the updated snapshot history.` : 'No new observations were stored. No fresh-data success is claimed.')
      onRefresh()
    } catch (err) { setError(err instanceof Error ? err.message : 'Collection failed.') }
    finally { setBusy(false) }
  }
  return (
    <div className="space-y-3">
      {available.length > 0 && <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm text-muted">Live collector<select aria-label="Live collector" className="mt-2 block w-full rounded-card border border-border-hair bg-background p-2.5" value={platform} onChange={(event) => setPlatform(event.target.value)}><option value="">Select platform</option>{available.map((item) => <option key={item.platform} value={item.platform}>{title(item.platform)}</option>)}</select></label>
        <Field label="Product keyword to collect" name="refresh-keyword" value={keyword} onChange={setKeyword} />
      </div>}
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" disabled={busy || !keyword.trim() || !available.some((item) => item.platform === platform)} onClick={() => void refresh()}>{busy ? 'Collecting…' : 'Refresh Market Data'}</Button>
        <Button variant="ghost" disabled={busy} onClick={onRefresh}>Reload stored analytics</Button>
        <Link to="/dashboard/marketplace-data" className="self-center text-sm text-accent-text">Import / manage stored data</Link>
      </div>
      {available.length === 0 && <p className="text-sm text-muted">Live refresh unavailable. {sources ? 'No usable LIVE collector is connected.' : 'Collector status could not be loaded yet.'}</p>}
      {sources?.filter((item) => !item.available).map((item) => <p key={item.platform} className="text-xs text-subtle"><strong>{title(item.platform)}:</strong> {item.reason ?? 'Collector unavailable.'}</p>)}
      {message && <p role="status" className="text-sm text-muted">{message}</p>}
      {error && <FormAlert>{error}</FormAlert>}
    </div>
  )
}
