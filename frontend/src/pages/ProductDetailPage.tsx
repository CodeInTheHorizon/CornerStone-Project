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
} from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import {
  getProduct, getProductHistory, getProductScores, trackProduct,
  type ProductOut, type PricePoint, type ScoreResponse,
} from '@/services/productService'

const PLATFORM_COLORS: Record<string, string> = {
  amazon: '#3b82f6', flipkart: '#eab308', croma: '#22c55e', alibaba: '#f97316',
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
      </motion.div>
    </DashboardLayout>
  )
}
