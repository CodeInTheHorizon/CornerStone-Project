import { useCallback, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts'
import {
  ArrowLeft, Star, ExternalLink, ImageOff, TrendingUp,
  BarChart3, Bookmark, BookmarkCheck, RefreshCw, AlertTriangle,
  Calculator,
} from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import {
  getProduct, getProductHistory, getProductScores, trackProduct,
  type ProductOut, type PricePoint, type ScoreResponse,
} from '@/services/productService'
import {
  analyzeProfitability, allocateInventory,
  type ProfitabilityResponse, type OptimizationResponse,
} from '@/services/profitabilityService'

const PLATFORM_COLORS: Record<string, string> = {
  amazon: '#3b82f6', flipkart: '#eab308', croma: '#22c55e', alibaba: '#f97316', meesho: '#e11d48',
}

function platformColor(p: string) {
  return PLATFORM_COLORS[p.toLowerCase()] ?? '#8b5cf6'
}

function fmt(v: number | null, currency = 'INR') {
  if (v === null) return '—'
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }).format(v) }
  catch { return `${currency} ${v}` }
}

function imgSrc(url: string | null) {
  return url ? `/images/proxy?url=${encodeURIComponent(url)}` : null
}

function best(values: (number | null)[], mode: 'min' | 'max') {
  const nums = values.filter((v): v is number => v !== null)
  if (nums.length === 0) return null
  return mode === 'min' ? Math.min(...nums) : Math.max(...nums)
}

function CircularScore({ score, size = 72 }: { score: number; size?: number }) {
  const pct = Math.min(100, Math.max(0, score))
  const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#eab308' : '#ef4444'
  return (
    <div
      className="relative flex items-center justify-center rounded-full"
      style={{
        width: size, height: size,
        background: `conic-gradient(${color} ${pct * 3.6}deg, #e5e7eb ${pct * 3.6}deg)`,
      }}
    >
      <div className="absolute flex items-center justify-center rounded-full bg-white dark:bg-zinc-900"
        style={{ width: size - 12, height: size - 12 }}>
        <span className="text-sm font-bold">{Math.round(score)}</span>
      </div>
    </div>
  )
}

function rankLabel(rank: number) {
  if (rank === 1) return '1st'
  if (rank === 2) return '2nd'
  if (rank === 3) return '3rd'
  return `${rank}th`
}

export function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>()
  const navigate = useNavigate()
  const { token } = useAuth()

  const [product, setProduct] = useState<ProductOut | null>(null)
  const [history, setHistory] = useState<Record<string, PricePoint[]>>({})
  const [scores, setScores] = useState<ScoreResponse | null>(null)
  const [tracked, setTracked] = useState(false)
  const [loading, setLoading] = useState(true)
  const [recomputing, setRecomputing] = useState(false)

  // Seller unit economics & inventory allocation state
  const [costPrice, setCostPrice] = useState<number>(1000)
  const [availableInventory, setAvailableInventory] = useState<number>(100)
  const [targetMargin, setTargetMargin] = useState<number>(15)
  const [profitData, setProfitData] = useState<ProfitabilityResponse | null>(null)
  const [optData, setOptData] = useState<OptimizationResponse | null>(null)
  const [calcBusy, setCalcBusy] = useState<boolean>(false)
  const [calcError, setCalcError] = useState<string>('')

  const id = Number(productId)

  const load = useCallback(async () => {
    if (!token || Number.isNaN(id)) return
    setLoading(true)
    try {
      const [prod, hist, sc] = await Promise.all([
        getProduct(token, id),
        getProductHistory(token, id),
        getProductScores(token, id),
      ])
      setProduct(prod)
      setHistory(hist)
      setScores(sc)

      // Initialize cost price to ~65% of minimum observed price
      if (prod && prod.listings && prod.listings.length > 0) {
        const prices = prod.listings
          .map((l) => l.price_current)
          .filter((p): p is number => p !== null && p > 0)
        if (prices.length > 0) {
          setCostPrice(Math.round(Math.min(...prices) * 0.65))
        }
      }
    } catch { /* handled by empty state */ }
    finally { setLoading(false) }
  }, [token, id])

  useEffect(() => { void load() }, [load])

  const handleTrack = async () => {
    if (!token || !product) return
    try {
      await trackProduct(token, product.id)
      setTracked(true)
    } catch { /* ignore */ }
  }

  const handleRecompute = async () => {
    if (!token) return
    setRecomputing(true)
    try {
      setScores(await getProductScores(token, id, true))
    } catch { /* ignore */ }
    finally { setRecomputing(false) }
  }

  const handleAnalyzeProfitability = async () => {
    if (!token || !product) return
    if (costPrice <= 0) {
      setCalcError('Cost price must be greater than zero.')
      return
    }
    setCalcBusy(true)
    setCalcError('')
    try {
      const [pRes, oRes] = await Promise.all([
        analyzeProfitability(token, {
          cost_price: Number(costPrice),
          available_inventory: Number(availableInventory),
          desired_margin_pct: Number(targetMargin),
          platforms: ['amazon', 'flipkart', 'croma', 'alibaba', 'meesho'],
          product_id: product.id,
        }),
        allocateInventory(token, {
          total_inventory: Number(availableInventory),
          min_margin_pct: Number(targetMargin),
          max_channel_share: 0.70,
          product_id: product.id,
          cost_price: Number(costPrice),
        }),
      ])
      setProfitData(pRes)
      setOptData(oRes)
    } catch (err: unknown) {
      setCalcError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setCalcBusy(false)
    }
  }

  // Build chart data: merge all platforms into [{date, amazon, flipkart, ...}]
  const chartData = (() => {
    const map = new Map<string, Record<string, number | null>>()
    for (const [platform, points] of Object.entries(history)) {
      for (const pt of points) {
        const day = pt.observed_at.slice(0, 10)
        const row = map.get(day) ?? {}
        row[platform] = pt.price
        map.set(day, row)
      }
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, rest]) => ({ date, ...rest }))
  })()

  const platforms = Object.keys(history)
  const listings = product?.listings ?? []

  if (loading) {
    return (
      <DashboardLayout title="Product Detail">
        <div className="flex items-center justify-center py-32">
          <RefreshCw className="size-6 animate-spin text-muted" />
          <span className="ml-3 text-sm text-muted">Loading product details...</span>
        </div>
      </DashboardLayout>
    )
  }

  if (!product) {
    return (
      <DashboardLayout title="Product Detail">
        <p className="py-20 text-center text-sm text-muted">Product not found.</p>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout title="Product Detail">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <button onClick={() => navigate(-1)} className="mt-1 rounded-lg p-1.5 transition-colors hover:bg-accent-soft">
              <ArrowLeft className="size-5" />
            </button>
            <div>
              <h1 className="text-xl font-semibold leading-tight">{product.canonical_title}</h1>
              <p className="mt-1 text-sm text-muted">
                {product.brand && <span className="font-medium">{product.brand}</span>}
                {product.brand && product.category && ' · '}
                {product.category}
              </p>
            </div>
          </div>
          <button onClick={() => void handleTrack()} className="inline-flex items-center gap-2 rounded-lg border border-border-hair px-4 py-2 text-sm font-medium transition-colors hover:bg-accent-soft">
            {tracked ? <BookmarkCheck className="size-4 text-green-500" /> : <Bookmark className="size-4" />}
            {tracked ? 'Tracked' : 'Track'}
          </button>
        </div>

        {/* Platform Comparison Table */}
        <section className="mt-8">
          <h2 className="mb-4 flex items-center gap-2 text-base font-semibold">
            <BarChart3 className="size-5" /> Platform Comparison
          </h2>
          <div className="overflow-x-auto rounded-xl border border-border-hair" role="region" aria-label="Platform comparison table" tabIndex={0}>
            <table className="w-full min-w-[600px] text-sm">
              <thead>
                <tr className="border-b border-border-hair bg-background-alt">
                  <th className="px-4 py-3 text-left text-xs font-medium text-subtle">Attribute</th>
                  {listings.map((l) => (
                    <th key={l.id} className="px-4 py-3 text-center text-xs font-medium">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="inline-block size-2.5 rounded-full" style={{ backgroundColor: platformColor(l.platform) }} />
                        <span className="capitalize">{l.platform}</span>
                        {l.is_stale && <AlertTriangle className="size-3.5 text-yellow-500" aria-label="Stale listing" />}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border-hair/60">
                  <td className="px-4 py-3 text-xs text-subtle">Image</td>
                  {listings.map((l) => {
                    const src = imgSrc(l.image_url)
                    return (
                      <td key={l.id} className="px-4 py-3 text-center">
                        {src ? <img src={src} alt="" className="mx-auto h-16 w-16 rounded object-contain" />
                          : <div className="mx-auto flex h-16 w-16 items-center justify-center rounded bg-zinc-100 dark:bg-zinc-800"><ImageOff className="size-5 text-muted" /></div>}
                      </td>
                    )
                  })}
                </tr>
                {([
                  ['Price', (l) => fmt(l.price_current, l.currency), (l) => l.price_current, 'min'],
                  ['Original Price', (l) => fmt(l.price_original, l.currency)],
                  ['Discount', (l) => l.discount_pct !== null ? `${l.discount_pct.toFixed(0)}%` : '—', (l) => l.discount_pct, 'max'],
                  ['Rating', (l) => l.rating !== null ? <span className="inline-flex items-center gap-1">{l.rating.toFixed(1)} <Star className="size-3.5 fill-yellow-400 text-yellow-400" /></span> : '—', (l) => l.rating, 'max'],
                  ['Reviews', (l) => l.review_count?.toLocaleString() ?? '—'],
                  ['Seller', (l) => l.seller_name ?? '—'],
                  ['Stock', (l) => l.in_stock === null ? '—' : l.in_stock ? 'In stock' : 'Out of stock'],
                  ['MOQ', (l) => l.min_order_qty ?? '—'],
                  ['Link', (l) => l.product_url ? <a href={l.product_url} target="_blank" rel="noreferrer" className="text-accent-text hover:underline"><ExternalLink className="mx-auto size-4" /></a> : '—'],
                ] as [string, (l: typeof listings[0]) => React.ReactNode, ((l: typeof listings[0]) => number | null)?, string?][]).map(([label, render, valFn, mode]) => {
                  const bestVal = valFn ? best(listings.map(valFn), (mode as 'min' | 'max') ?? 'min') : null
                  return (
                    <tr key={label} className="border-b border-border-hair/60 last:border-0">
                      <td className="px-4 py-2.5 text-xs text-subtle">{label}</td>
                      {listings.map((l) => {
                        const val = valFn?.(l)
                        const isBest = bestVal !== null && val !== null && val === bestVal
                        return (
                          <td key={l.id} className={`px-4 py-2.5 text-center text-sm ${isBest ? 'font-semibold text-green-600 dark:text-green-400' : ''}`}>
                            {render(l)}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Opportunity Scores */}
        {scores && scores.scores.length > 0 && (
          <section className="mt-8">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <TrendingUp className="size-5" /> Opportunity Scores
              </h2>
              <button onClick={() => void handleRecompute()} disabled={recomputing}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border-hair px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent-soft disabled:opacity-50">
                <RefreshCw className={`size-3.5 ${recomputing ? 'animate-spin' : ''}`} /> Recompute
              </button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {scores.scores.map((s) => (
                <div key={s.platform} className="surface-card flex flex-col items-center p-5">
                  <span className="mb-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold" style={{ backgroundColor: platformColor(s.platform) + '22', color: platformColor(s.platform) }}>
                    {rankLabel(s.rank)}
                  </span>
                  <CircularScore score={s.score} />
                  <p className="mt-2 text-sm font-semibold capitalize">{s.platform}</p>
                  <p className="mt-1 text-center text-xs leading-relaxed text-muted line-clamp-3">{s.explanation}</p>
                  <p className="mt-2 text-[11px] text-subtle">Inventory share: {s.suggested_inventory_share_pct}%</p>
                </div>
              ))}
            </div>
            {/* Inventory allocation bar */}
            <div className="mt-4 flex h-4 overflow-hidden rounded-full">
              {scores.scores.map((s) => (
                <div key={s.platform} title={`${s.platform}: ${s.suggested_inventory_share_pct}%`}
                  style={{ width: `${s.suggested_inventory_share_pct}%`, backgroundColor: platformColor(s.platform) }} />
              ))}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-4 text-[11px] text-muted">
              {scores.scores.map((s) => (
                <span key={s.platform} className="inline-flex items-center gap-1">
                  <span className="inline-block size-2 rounded-full" style={{ backgroundColor: platformColor(s.platform) }} />
                  <span className="capitalize">{s.platform}</span> {s.suggested_inventory_share_pct}%
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Price History Chart */}
        {chartData.length > 0 && (
          <section className="mt-8">
            <h2 className="mb-4 flex items-center gap-2 text-base font-semibold">
              <BarChart3 className="size-5" /> Price History
            </h2>
            <div className="surface-card p-4">
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  {platforms.map((p) => (
                    <Line key={p} type="monotone" dataKey={p} stroke={platformColor(p)}
                      strokeWidth={2} dot={false} name={p} connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {/* Profitability & Optimal Inventory Allocation Section */}
        <section className="mt-8">
          <div className="surface-card p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <Calculator className="size-5 text-accent-text" /> Seller Profitability & Allocation Calculator
                </h2>
                <p className="mt-1 text-xs text-muted">
                  Simulate seller fees, net margins, and optimal inventory distribution across sales channels for this product.
                </p>
              </div>
              <button
                onClick={() => void handleAnalyzeProfitability()}
                disabled={calcBusy}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-accent-contrast shadow-sm transition hover:opacity-95 disabled:opacity-50"
              >
                {calcBusy ? <Calculator className="size-3.5 animate-spin" /> : <TrendingUp className="size-3.5" />}
                {calcBusy ? 'Calculating Economics...' : 'Calculate Economics & Allocation'}
              </button>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <div>
                <label className="block text-xs font-medium text-subtle">Seller Unit Cost (₹ COGS)</label>
                <input
                  type="number"
                  min="1"
                  value={costPrice}
                  onChange={(e) => setCostPrice(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-subtle">Available Inventory (Units)</label>
                <input
                  type="number"
                  min="1"
                  value={availableInventory}
                  onChange={(e) => setAvailableInventory(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-subtle">Target Net Margin (%)</label>
                <input
                  type="number"
                  min="0"
                  max="80"
                  value={targetMargin}
                  onChange={(e) => setTargetMargin(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
                />
              </div>
            </div>

            {calcError && (
              <p className="mt-3 text-xs text-red-500">{calcError}</p>
            )}

            {profitData && (
              <div className="mt-6 space-y-6 border-t border-border-hair/60 pt-6">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg bg-background-alt p-3">
                    <span className="text-[11px] text-muted">Best Channel by Profit</span>
                    <p className="text-lg font-bold capitalize text-green-500">{profitData.best_channel_by_profit}</p>
                  </div>
                  <div className="rounded-lg bg-background-alt p-3">
                    <span className="text-[11px] text-muted">Best Channel by Margin</span>
                    <p className="text-lg font-bold capitalize text-blue-500">{profitData.best_channel_by_margin}</p>
                  </div>
                  {optData && (
                    <>
                      <div className="rounded-lg bg-background-alt p-3">
                        <span className="text-[11px] text-muted">Total Expected Net Profit</span>
                        <p className="text-lg font-bold text-foreground">{fmt(optData.total_expected_profit)}</p>
                      </div>
                      <div className="rounded-lg bg-background-alt p-3">
                        <span className="text-[11px] text-muted">Blended Margin</span>
                        <p className="text-lg font-bold text-accent-text">{optData.average_margin_pct.toFixed(1)}%</p>
                      </div>
                    </>
                  )}
                </div>

                {/* Economics Table */}
                <div className="overflow-x-auto rounded-lg border border-border-hair">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-border-hair bg-background-alt text-subtle">
                        <th className="px-3 py-2.5">Channel</th>
                        <th className="px-3 py-2.5 text-right">Selling Price</th>
                        <th className="px-3 py-2.5 text-right">Total Fees</th>
                        <th className="px-3 py-2.5 text-right">Net Profit / Unit</th>
                        <th className="px-3 py-2.5 text-right">Margin %</th>
                        <th className="px-3 py-2.5 text-right">Target Price ({targetMargin}%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {profitData.channels.map((ch) => (
                        <tr key={ch.platform} className="border-b border-border-hair/50 last:border-0">
                          <td className="px-3 py-2 font-medium capitalize">
                            <span className="inline-flex items-center gap-1.5">
                              <span className="size-2 rounded-full" style={{ backgroundColor: platformColor(ch.platform) }} />
                              {ch.platform}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right">{fmt(ch.selling_price)}</td>
                          <td className="px-3 py-2 text-right text-red-500">-{fmt(ch.total_fee_per_unit)}</td>
                          <td className={`px-3 py-2 text-right font-bold ${ch.net_profit_per_unit >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
                            {fmt(ch.net_profit_per_unit)}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <span className={`rounded px-1 py-0.5 font-semibold ${ch.margin_pct >= targetMargin ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-yellow-500/10 text-yellow-600'}`}>
                              {ch.margin_pct.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right font-medium text-accent-text">{fmt(ch.min_selling_price_for_target)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Optimal Allocation Breakdown */}
                {optData && optData.allocations.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-subtle">
                      Recommended Stock Allocation ({optData.total_allocated} / {availableInventory} units)
                    </h3>
                    <div className="flex h-3.5 overflow-hidden rounded-full">
                      {optData.allocations.map((a) => (
                        <div key={a.platform} title={`${a.platform}: ${a.allocated_units} units (${a.share_pct}%)`}
                          style={{ width: `${a.share_pct}%`, backgroundColor: platformColor(a.platform) }} />
                      ))}
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {optData.allocations.map((a) => (
                        <div key={a.platform} className="rounded-lg border border-border-hair bg-background p-3 text-xs">
                          <div className="flex justify-between font-semibold capitalize">
                            <span>{a.platform}</span>
                            <span className="text-accent-text">{a.allocated_units} units ({a.share_pct}%)</span>
                          </div>
                          <p className="mt-1 text-[11px] text-muted">{a.rationale}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </motion.div>
    </DashboardLayout>
  )
}
