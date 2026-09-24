import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Plus, X } from 'lucide-react'

import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { EmptyState } from '@/components/dashboard/StateViews'
import { Panel } from '@/components/Panel'
import { useAuth } from '@/hooks/useAuth'
import { PLATFORM_KEYS, platformColour } from '@/lib/platforms'
import { title } from '@/lib/predictionFormat'
import * as service from '@/services/analyticsService'
import type { AnalyticsOptions, ComparisonResponse } from '@/types/analytics'

const metrics = [
  { key: 'average_price', label: 'Avg Price', unit: '' },
  { key: 'average_rating', label: 'Avg Rating', unit: '/5' },
  { key: 'average_discount', label: 'Avg Discount', unit: '%' },
] as const

function ComparisonChart({ data, metric, unit }: { data: { platform: string; value: number | null }[]; metric: string; unit: string }) {
  const filtered = data.filter((d) => d.value != null)
  if (!filtered.length) return <p className="py-4 text-center text-xs text-muted">No data</p>

  const best = metric === 'average_price'
    ? Math.min(...filtered.map((d) => d.value!))
    : Math.max(...filtered.map((d) => d.value!))

  return (
    <div className="h-40">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={filtered} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="platform" tick={{ fontSize: 11, fill: 'var(--muted)' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} axisLine={false} tickLine={false} width={45} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0]
              return (
                <div className="glass-card px-3 py-2 text-xs shadow-pop">
                  <span className="font-medium">{d.payload.platform}</span>: {Number(d.value).toFixed(2)}{unit}
                </div>
              )
            }}
          />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
            {filtered.map((entry) => (
              <Cell key={entry.platform} fill={entry.value === best ? 'var(--signal-ok)' : platformColour(entry.platform.toLowerCase())} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function ComparePage() {
  const { token } = useAuth()
  const [options, setOptions] = useState<AnalyticsOptions | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [results, setResults] = useState<Map<string, ComparisonResponse>>(new Map())
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!token) return
    service.fetchAnalyticsOptions(token, {}, query).then(setOptions).catch(() => setOptions(null))
  }, [token, query])

  useEffect(() => {
    if (!token || selected.length === 0) return
    setLoading(true)
    Promise.all(
      selected.map(async (key) => {
        if (results.has(key)) return
        const res = await service.fetchComparison(token, { product_key: key })
        setResults((prev) => new Map(prev).set(key, res))
      }),
    ).finally(() => setLoading(false))
  }, [token, selected])

  function addProduct(key: string) {
    if (selected.length < 4 && !selected.includes(key)) setSelected([...selected, key])
  }

  function removeProduct(key: string) {
    setSelected(selected.filter((k) => k !== key))
    setResults((prev) => { const next = new Map(prev); next.delete(key); return next })
  }

  const allPlatforms = PLATFORM_KEYS.map((p) => title(p))

  return (
    <DashboardLayout title="Product Comparison">
      <div className="space-y-6">
        <Panel>
          <h2 className="text-lg font-semibold">Compare products across platforms</h2>
          <p className="mt-1 text-sm text-muted">Select 2-4 products to see side-by-side marketplace metrics.</p>

          <div className="mt-4 flex flex-wrap gap-2">
            {selected.map((key) => (
              <span key={key} className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-text">
                {key.split('|')[0]}
                <button onClick={() => removeProduct(key)} className="rounded-full hover:bg-accent/20"><X className="size-3" /></button>
              </span>
            ))}
          </div>

          {selected.length < 4 && (
            <div className="mt-3">
              <input
                type="text"
                placeholder="Search products..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full rounded-card border border-border-hair bg-background px-3 py-2 text-sm transition-colors focus:border-accent"
              />
              {options && (
                <ul className="mt-2 max-h-40 overflow-y-auto rounded-card border border-border-hair bg-surface text-sm">
                  {options.products
                    .filter((p) => !selected.includes(p.product_key))
                    .slice(0, 8)
                    .map((product) => (
                      <li key={product.product_key}>
                        <button
                          onClick={() => addProduct(product.product_key)}
                          className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-background-alt"
                        >
                          <Plus className="size-3.5 shrink-0 text-accent-text" />
                          <span className="truncate">{product.product_name}</span>
                          <span className="ml-auto shrink-0 text-xs text-subtle">{product.category}</span>
                        </button>
                      </li>
                    ))}
                </ul>
              )}
            </div>
          )}
        </Panel>

        {selected.length < 2 && !loading && (
          <EmptyState icon="chart" title="Select at least 2 products">
            Pick products above to compare their marketplace performance side by side.
          </EmptyState>
        )}

        {selected.length >= 2 && (
          <div className="space-y-6">
            {metrics.map(({ key, label, unit }) => (
              <Panel key={key}>
                <h3 className="text-sm font-semibold">{label}</h3>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {selected.map((productKey) => {
                    const result = results.get(productKey)
                    const group = result?.groups[0]
                    const data = allPlatforms.map((platform) => {
                      const p = group?.platforms.find((pl) => title(pl.platform) === platform)
                      return { platform, value: p ? (p[key as keyof typeof p] as number | null) : null }
                    })
                    return (
                      <motion.div
                        key={productKey}
                        className="rounded-card border border-border-hair bg-background-alt/30 p-3"
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                      >
                        <p className="truncate text-xs font-medium">{productKey.split('|')[0]}</p>
                        <ComparisonChart data={data} metric={key} unit={unit} />
                      </motion.div>
                    )
                  })}
                </div>
              </Panel>
            ))}
          </div>
        )}

        {loading && <p className="text-sm text-muted">Loading comparison data...</p>}
      </div>
    </DashboardLayout>
  )
}
