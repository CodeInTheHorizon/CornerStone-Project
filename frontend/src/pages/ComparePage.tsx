import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Plus, X, Search, ChevronDown, Package } from 'lucide-react'

import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { EmptyState } from '@/components/dashboard/StateViews'
import { Panel } from '@/components/Panel'
import { useAuth } from '@/hooks/useAuth'
import { PLATFORM_KEYS, platformColour } from '@/lib/platforms'
import { title } from '@/lib/predictionFormat'
import * as service from '@/services/analyticsService'
import { listProducts } from '@/services/productService'
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
  const [catalogProducts, setCatalogProducts] = useState<{ product_key: string; product_name: string; category: string }[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [results, setResults] = useState<Map<string, ComparisonResponse>>(new Map())
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Fetch analytics options
  useEffect(() => {
    if (!token) return
    service.fetchAnalyticsOptions(token, {}, query).then(setOptions).catch(() => setOptions(null))
  }, [token, query])

  // Also fetch saved catalog products so searched products appear in suggestions
  useEffect(() => {
    if (!token) return
    listProducts(token, { limit: 100 })
      .then((prods) => {
        setCatalogProducts(
          prods.map((p) => ({
            product_key: p.canonical_title,
            product_name: p.canonical_title,
            category: p.category || 'electronics',
          }))
        )
      })
      .catch(() => {})
  }, [token])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Merge available products from both sources
  const availableProducts = useMemo(() => {
    const map = new Map<string, { product_key: string; product_name: string; category: string }>()
    for (const p of catalogProducts) {
      map.set(p.product_key, p)
    }
    if (options?.products) {
      for (const p of options.products) {
        map.set(p.product_key, p)
      }
    }
    return Array.from(map.values())
  }, [catalogProducts, options])

  // Filter products by search query and exclude selected
  const filteredProducts = useMemo(() => {
    return availableProducts.filter((p) => {
      if (selected.includes(p.product_key)) return false
      if (!query.trim()) return true
      const q = query.toLowerCase()
      return p.product_name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q)
    })
  }, [availableProducts, selected, query])

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
    if (selected.length < 4 && !selected.includes(key)) {
      setSelected([...selected, key])
    }
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
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Compare products across platforms</h2>
              <p className="mt-1 text-sm text-muted">Select 2-4 products to see side-by-side marketplace metrics.</p>
            </div>
            <span className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-text">
              {selected.length} / 4 selected
            </span>
          </div>

          {selected.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {selected.map((key) => (
                <span key={key} className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-text">
                  {key.split('|')[0]}
                  <button onClick={() => removeProduct(key)} className="rounded-full hover:bg-accent/20"><X className="size-3" /></button>
                </span>
              ))}
            </div>
          )}

          {selected.length < 4 && (
            <div ref={dropdownRef} className="relative mt-4">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
                <input
                  type="text"
                  placeholder={availableProducts.length > 0 ? "Click to view available products or type to search..." : "Search products..."}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value)
                    setIsOpen(true)
                  }}
                  onFocus={() => setIsOpen(true)}
                  className="w-full rounded-card border border-border-hair bg-background pl-9 pr-9 py-2.5 text-sm transition-colors focus:border-accent focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setIsOpen(!isOpen)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-muted transition-colors hover:text-foreground"
                  aria-label="Toggle product list"
                >
                  <ChevronDown className={`size-4 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
                </button>
              </div>

              {isOpen && (
                <div className="absolute left-0 right-0 top-full z-30 mt-1.5 max-h-64 overflow-y-auto rounded-card border border-border-hair bg-surface p-1.5 shadow-float">
                  <div className="flex items-center justify-between px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
                    <span>Available Products ({filteredProducts.length})</span>
                    <span>Click to add</span>
                  </div>

                  {filteredProducts.length === 0 ? (
                    <div className="py-6 text-center text-xs text-muted">
                      <Package className="mx-auto mb-1.5 size-5 opacity-40" />
                      {availableProducts.length === 0
                        ? "No products available yet. Use the Search page to discover products across platforms."
                        : "No matching products found."}
                    </div>
                  ) : (
                    <ul className="mt-1 space-y-0.5">
                      {filteredProducts.map((product) => (
                        <li key={product.product_key}>
                          <button
                            type="button"
                            onClick={() => {
                              addProduct(product.product_key)
                              setQuery('')
                              setIsOpen(false)
                            }}
                            className="group flex w-full items-center justify-between gap-3 rounded px-2.5 py-2 text-left text-sm transition-colors hover:bg-background-alt"
                          >
                            <div className="flex items-center gap-2.5 min-w-0">
                              <Plus className="size-4 shrink-0 text-accent-text transition-transform group-hover:scale-125" />
                              <span className="truncate font-medium text-foreground">{product.product_name}</span>
                            </div>
                            <span className="shrink-0 rounded-full bg-accent-soft/80 px-2 py-0.5 text-[11px] font-medium text-accent-text">
                              {product.category}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
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
