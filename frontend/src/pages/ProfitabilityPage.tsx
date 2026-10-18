import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Calculator, TrendingUp, Layers, CheckCircle2,
  AlertCircle, ShieldAlert, BarChart3
} from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import {
  analyzeProfitability, allocateInventory,
  type ProfitabilityResponse, type OptimizationResponse
} from '@/services/profitabilityService'
import { listProducts, getProduct, type ProductSummary } from '@/services/productService'

const PLATFORM_COLORS: Record<string, string> = {
  amazon: '#3b82f6',
  flipkart: '#eab308',
  croma: '#22c55e',
  alibaba: '#f97316',
  meesho: '#e11d48',
}

function platformColor(p: string) {
  return PLATFORM_COLORS[p.toLowerCase()] ?? '#8b5cf6'
}

function fmtINR(val: number | null | undefined) {
  if (val === null || val === undefined || isNaN(val)) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val)
}

export function ProfitabilityPage() {
  const { token } = useAuth()
  const [products, setProducts] = useState<ProductSummary[]>([])
  const [selectedProductId, setSelectedProductId] = useState<string>('')
  
  // Inputs
  const [costPrice, setCostPrice] = useState<number>(1500)
  const [sellingPrice, setSellingPrice] = useState<string>('')
  const [availableInventory, setAvailableInventory] = useState<number>(200)
  const [desiredMarginPct, setDesiredMarginPct] = useState<number>(20)
  const [fixedOverhead, setFixedOverhead] = useState<number>(0)
  
  // State
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const [profitability, setProfitability] = useState<ProfitabilityResponse | null>(null)
  const [optimization, setOptimization] = useState<OptimizationResponse | null>(null)

  useEffect(() => {
    if (!token) return
    listProducts(token, { limit: 50 })
      .then((items) => {
        setProducts(items)
        if (items.length > 0) {
          const first = items[0]
          setSelectedProductId(String(first.id))
          if (first.min_price && first.min_price > 0) {
            setCostPrice(Math.round(first.min_price * 0.65))
          }
        }
      })
      .catch(() => {})
  }, [token])

  const handleProductChange = async (productIdStr: string) => {
    setSelectedProductId(productIdStr)
    if (!token || !productIdStr) return
    const id = Number(productIdStr)
    if (isNaN(id)) return
    try {
      const fullProd = await getProduct(token, id)
      const prices = fullProd.listings
        .map((l) => l.price_current)
        .filter((p): p is number => p !== null && p > 0)
      if (prices.length > 0) {
        setCostPrice(Math.round(Math.min(...prices) * 0.65))
      }
    } catch {
      const prod = products.find((p) => String(p.id) === productIdStr)
      if (prod?.min_price) {
        setCostPrice(Math.round(prod.min_price * 0.65))
      }
    }
  }

  const handleCalculate = async () => {
    if (!token) return
    if (costPrice <= 0) {
      setError('Cost price must be greater than zero.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const prodId = selectedProductId ? Number(selectedProductId) : null
      const sp = sellingPrice.trim() !== '' ? Number(sellingPrice) : null

      const [profitRes, optRes] = await Promise.all([
        analyzeProfitability(token, {
          cost_price: Number(costPrice),
          selling_price: sp,
          available_inventory: Number(availableInventory),
          desired_margin_pct: Number(desiredMarginPct),
          fixed_overhead: Number(fixedOverhead),
          platforms: ['amazon', 'flipkart', 'croma', 'alibaba', 'meesho'],
          product_id: prodId,
        }),
        allocateInventory(token, {
          total_inventory: Number(availableInventory),
          min_margin_pct: Number(desiredMarginPct),
          max_channel_share: 0.70,
          product_id: prodId,
          cost_price: Number(costPrice),
        }),
      ])

      setProfitability(profitRes)
      setOptimization(optRes)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Calculation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <DashboardLayout title="Profitability & Channel Optimization">
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Channel Profitability & Allocation Engine</h1>
          <p className="mt-1 text-sm text-muted">
            Evaluate unit economics, platform fee deductions (referral, logistics, closing), and optimal multi-channel inventory allocation.
          </p>
        </div>

        {/* Input Parameters Panel */}
        <div className="surface-card p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <Calculator className="size-5 text-accent-text" />
            Seller Unit Economics & Inventory Parameters
          </h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
            <div>
              <label htmlFor="target-product-select" className="block text-xs font-medium text-subtle">Target Product (Optional)</label>
              <select
                id="target-product-select"
                value={selectedProductId}
                onChange={(e) => void handleProductChange(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              >
                <option value="">Custom Simulation</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.canonical_title.slice(0, 30)}...
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="cost-price-input" className="block text-xs font-medium text-subtle">Seller Cost (₹ COGS)</label>
              <input
                id="cost-price-input"
                type="number"
                min="1"
                value={costPrice}
                onChange={(e) => setCostPrice(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </div>

            <div>
              <label htmlFor="selling-price-input" className="block text-xs font-medium text-subtle">Selling Price (₹ Opt.)</label>
              <input
                id="selling-price-input"
                type="number"
                placeholder="Market rate"
                value={sellingPrice}
                onChange={(e) => setSellingPrice(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </div>

            <div>
              <label htmlFor="total-inventory-input" className="block text-xs font-medium text-subtle">Inventory (Units)</label>
              <input
                id="total-inventory-input"
                type="number"
                min="1"
                value={availableInventory}
                onChange={(e) => setAvailableInventory(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </div>

            <div>
              <label htmlFor="target-margin-input" className="block text-xs font-medium text-subtle">Target Margin (%)</label>
              <input
                id="target-margin-input"
                type="number"
                min="0"
                max="80"
                value={desiredMarginPct}
                onChange={(e) => setDesiredMarginPct(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </div>

            <div>
              <label htmlFor="fixed-overhead-input" className="block text-xs font-medium text-subtle">Fixed Overhead (₹)</label>
              <input
                id="fixed-overhead-input"
                type="number"
                min="0"
                value={fixedOverhead}
                onChange={(e) => setFixedOverhead(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border-hair bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </div>
          </div>

          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-500/10 p-3 text-xs text-red-500">
              <AlertCircle className="size-4" /> {error}
            </div>
          )}

          <div className="mt-6 flex justify-end">
            <button
              onClick={() => void handleCalculate()}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-accent-contrast shadow-sm transition hover:opacity-95 disabled:opacity-50"
            >
              {loading ? <Calculator className="size-4 animate-spin" /> : <TrendingUp className="size-4" />}
              {loading ? 'Evaluating Economics...' : 'Compute Profitability & Optimal Allocation'}
            </button>
          </div>
        </div>

        {/* Results Section */}
        {profitability && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
            {/* Highlights */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="surface-card p-5">
                <span className="text-xs font-medium text-muted">Best Channel by Profit</span>
                <p className="mt-1 text-2xl font-bold capitalize text-green-500">
                  {profitability.best_channel_by_profit}
                </p>
                <p className="mt-1 text-xs text-subtle">Maximizes absolute bottom-line net return</p>
              </div>

              <div className="surface-card p-5">
                <span className="text-xs font-medium text-muted">Best Channel by Margin %</span>
                <p className="mt-1 text-2xl font-bold capitalize text-blue-500">
                  {profitability.best_channel_by_margin}
                </p>
                <p className="mt-1 text-xs text-subtle">Highest capital efficiency per unit sold</p>
              </div>

              {optimization && (
                <>
                  <div className="surface-card p-5">
                    <span className="text-xs font-medium text-muted">Total Projected Profit</span>
                    <p className="mt-1 text-2xl font-bold text-foreground">
                      {fmtINR(optimization.total_expected_profit)}
                    </p>
                    <p className="mt-1 text-xs text-subtle">From {optimization.total_allocated} allocated units</p>
                  </div>

                  <div className="surface-card p-5">
                    <span className="text-xs font-medium text-muted">Blended Margin</span>
                    <p className="mt-1 text-2xl font-bold text-accent-text">
                      {optimization.average_margin_pct.toFixed(1)}%
                    </p>
                    <p className="mt-1 text-xs text-subtle">Allocation status: {optimization.status}</p>
                  </div>
                </>
              )}
            </div>

            {/* Platform Economics Breakdown */}
            <div className="surface-card p-6">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <BarChart3 className="size-5 text-accent-text" />
                Cross-Platform Unit Economics & Marketplace Deductions
              </h2>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[700px] text-sm">
                  <thead>
                    <tr className="border-b border-border-hair bg-background-alt text-xs font-medium text-subtle">
                      <th className="px-4 py-3 text-left">Platform</th>
                      <th className="px-4 py-3 text-right">Selling Price</th>
                      <th className="px-4 py-3 text-right">COGS</th>
                      <th className="px-4 py-3 text-right">Referral Fee</th>
                      <th className="px-4 py-3 text-right">Logistics / FBA</th>
                      <th className="px-4 py-3 text-right">Total Fees</th>
                      <th className="px-4 py-3 text-right">Net Profit / Unit</th>
                      <th className="px-4 py-3 text-right">Margin %</th>
                      <th className="px-4 py-3 text-right">Target Price ({desiredMarginPct}%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profitability.channels.map((ch) => (
                      <tr key={ch.platform} className="border-b border-border-hair/60 last:border-0 hover:bg-background-alt/50">
                        <td className="px-4 py-3 font-semibold capitalize">
                          <span className="inline-flex items-center gap-2">
                            <span className="size-2.5 rounded-full" style={{ backgroundColor: platformColor(ch.platform) }} />
                            {ch.platform}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">{fmtINR(ch.selling_price)}</td>
                        <td className="px-4 py-3 text-right text-muted">{fmtINR(ch.cost_price)}</td>
                        <td className="px-4 py-3 text-right text-muted">{fmtINR(ch.referral_fee)}</td>
                        <td className="px-4 py-3 text-right text-muted">{fmtINR(ch.logistics_fee)}</td>
                        <td className="px-4 py-3 text-right font-medium text-red-500">-{fmtINR(ch.total_fee_per_unit)}</td>
                        <td className={`px-4 py-3 text-right font-bold ${ch.net_profit_per_unit > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
                          {fmtINR(ch.net_profit_per_unit)}
                        </td>
                        <td className="px-4 py-3 text-right font-semibold">
                          <span className={`rounded px-1.5 py-0.5 text-xs ${ch.margin_pct >= desiredMarginPct ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-yellow-500/10 text-yellow-600'}`}>
                            {ch.margin_pct.toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-medium text-accent-text">
                          {fmtINR(ch.min_selling_price_for_target)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-subtle">
                {profitability.fee_transparency_note}
              </p>
            </div>

            {/* Inventory Allocation Suggestions */}
            {optimization && optimization.allocations.length > 0 && (
              <div className="surface-card p-6">
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <Layers className="size-5 text-accent-text" />
                  Recommended Multi-Channel Inventory Allocation
                </h2>
                
                {/* Visual share bar */}
                <div className="mt-5 flex h-5 overflow-hidden rounded-full">
                  {optimization.allocations.map((a) => (
                    <div
                      key={a.platform}
                      title={`${a.platform}: ${a.allocated_units} units (${a.share_pct}%)`}
                      style={{ width: `${a.share_pct}%`, backgroundColor: platformColor(a.platform) }}
                    />
                  ))}
                </div>
                <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted">
                  {optimization.allocations.map((a) => (
                    <span key={a.platform} className="inline-flex items-center gap-1.5 font-medium">
                      <span className="size-2 rounded-full" style={{ backgroundColor: platformColor(a.platform) }} />
                      <span className="capitalize">{a.platform}</span>: {a.allocated_units} units ({a.share_pct}%)
                    </span>
                  ))}
                </div>

                <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {optimization.allocations.map((a) => (
                    <div key={a.platform} className="rounded-xl border border-border-hair bg-background p-4">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold capitalize text-foreground">{a.platform}</span>
                        <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-bold text-accent-text">
                          {a.allocated_units} units
                        </span>
                      </div>
                      <div className="mt-3 space-y-1 text-xs">
                        <div className="flex justify-between text-muted">
                          <span>Projected Revenue:</span>
                          <span className="font-medium text-foreground">{fmtINR(a.expected_revenue)}</span>
                        </div>
                        <div className="flex justify-between text-muted">
                          <span>Projected Net Profit:</span>
                          <span className="font-semibold text-green-600 dark:text-green-400">{fmtINR(a.expected_profit)}</span>
                        </div>
                        <div className="flex justify-between text-muted">
                          <span>Unit Margin:</span>
                          <span className="font-medium text-foreground">{a.unit_margin_pct.toFixed(1)}%</span>
                        </div>
                      </div>
                      <p className="mt-3 text-xs leading-relaxed text-subtle border-t border-border-hair/50 pt-2">
                        {a.rationale}
                      </p>
                    </div>
                  ))}
                </div>

                {/* Explanation & Risk */}
                {optimization.explanation.length > 0 && (
                  <div className="mt-6 rounded-lg bg-background-alt p-4">
                    <h3 className="text-xs font-semibold text-subtle uppercase tracking-wider">Optimization Rationale</h3>
                    <ul className="mt-2 space-y-1 text-xs text-muted">
                      {optimization.explanation.map((exp, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <CheckCircle2 className="size-3.5 mt-0.5 text-green-500 shrink-0" />
                          <span>{exp}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {optimization.risk_notes.length > 0 && (
                  <div className="mt-4 rounded-lg bg-yellow-500/10 p-4 text-xs text-yellow-600 dark:text-yellow-400">
                    <h3 className="font-semibold flex items-center gap-1.5">
                      <ShieldAlert className="size-4" /> Risk & Portfolio Concentration Notes
                    </h3>
                    <ul className="mt-2 space-y-1">
                      {optimization.risk_notes.map((rn, i) => (
                        <li key={i}>• {rn}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Demand & Pricing Sensitivity Scenarios */}
            {profitability.scenarios_for_recommended.length > 0 && (
              <div className="surface-card p-6">
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <TrendingUp className="size-5 text-accent-text" />
                  Demand Sensitivity Scenarios for Top Channel ({profitability.best_channel_by_profit.toUpperCase()})
                </h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-3">
                  {profitability.scenarios_for_recommended.map((s) => (
                    <div key={s.name} className="rounded-xl border border-border-hair bg-background p-4">
                      <h3 className="text-sm font-semibold capitalize text-foreground">{s.name} Scenario</h3>
                      <p className="mt-1 text-xs text-subtle">
                        Demand: {s.demand_multiplier}x | Price Shift: {s.price_delta_pct > 0 ? `+${s.price_delta_pct}%` : `${s.price_delta_pct}%`}
                      </p>
                      <div className="mt-4 space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-muted">Projected Units:</span>
                          <span className="font-medium text-foreground">{s.projected_units}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Expected Revenue:</span>
                          <span className="font-medium text-foreground">{fmtINR(s.projected_revenue)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Expected Net Profit:</span>
                          <span className={`font-bold ${s.projected_profit >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
                            {fmtINR(s.projected_profit)}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Projected Margin:</span>
                          <span className="font-medium text-foreground">{s.projected_margin_pct.toFixed(1)}%</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </DashboardLayout>
  )
}
