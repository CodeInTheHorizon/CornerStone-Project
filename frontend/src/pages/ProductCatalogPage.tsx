import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Package, Search, Filter, Star, ArrowUpRight, ImageOff, Trophy } from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { listProducts, type ProductSummary } from '@/services/productService'

const PAGE_SIZE = 12

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-border-hair bg-surface p-4">
      <div className="aspect-[4/3] rounded-lg bg-background-alt" />
      <div className="mt-3 h-4 w-3/4 rounded bg-background-alt" />
      <div className="mt-2 h-3 w-1/2 rounded bg-background-alt" />
      <div className="mt-4 h-3 w-1/3 rounded bg-background-alt" />
    </div>
  )
}

export function ProductCatalogPage() {
  const { token } = useAuth()
  const navigate = useNavigate()

  const [products, setProducts] = useState<ProductSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [brand, setBrand] = useState('')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)

  const [categories, setCategories] = useState<string[]>([])
  const [brands, setBrands] = useState<string[]>([])

  const fetchProducts = useCallback(
    async (reset: boolean) => {
      if (!token) return
      setLoading(true)
      try {
        const newOffset = reset ? 0 : offset
        const data = await listProducts(token, {
          q: query || undefined,
          category: category || undefined,
          brand: brand || undefined,
          limit: PAGE_SIZE,
          offset: newOffset,
        })
        const merged = reset ? data : [...products, ...data]
        setProducts(merged)
        setOffset(newOffset + data.length)
        setHasMore(data.length === PAGE_SIZE)

        if (reset) {
          const cats = [...new Set(merged.map((p) => p.category).filter(Boolean))].sort()
          const brs = [...new Set(merged.map((p) => p.brand).filter((b): b is string => !!b))].sort()
          setCategories((prev) => (prev.length ? prev : cats))
          setBrands((prev) => (prev.length ? prev : brs))
        }
      } catch {
        if (reset) setProducts([])
      } finally {
        setLoading(false)
      }
    },
    [token, query, category, brand, offset, products],
  )

  useEffect(() => {
    void fetchProducts(true)
    // Only re-fetch when filters change, not on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, query, category, brand])

  const loadMore = () => void fetchProducts(false)

  const formatPrice = (min: number | null, max: number | null) => {
    if (min === null && max === null) return null
    if (min !== null && max !== null && min !== max)
      return `₹${min.toLocaleString()} – ₹${max.toLocaleString()}`
    return `₹${(min ?? max)!.toLocaleString()}`
  }

  return (
    <DashboardLayout title="Product Catalog">
      <div className="space-y-6">
        {/* Search and filters */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Search products..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded-lg border border-border-hair bg-surface py-2 pl-10 pr-4 text-sm outline-none transition-colors focus:border-accent"
            />
          </div>
          <div className="flex gap-2">
            <div className="relative">
              <Filter className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted" />
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="appearance-none rounded-lg border border-border-hair bg-surface py-2 pl-8 pr-8 text-sm outline-none transition-colors focus:border-accent"
              >
                <option value="">All Categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <select
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              className="appearance-none rounded-lg border border-border-hair bg-surface py-2 px-3 text-sm outline-none transition-colors focus:border-accent"
            >
              <option value="">All Brands</option>
              {brands.map((b) => (
                <option key={b} value={b}>{b}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Product grid */}
        {loading && products.length === 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-border-hair bg-surface px-6 py-16 text-center">
            <Package className="size-12 text-muted" />
            <h3 className="mt-4 text-lg font-semibold">No products found</h3>
            <p className="mt-2 max-w-md text-sm text-muted">
              Use the search page to discover products across marketplaces.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product, i) => (
              <motion.div
                key={product.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: (i % PAGE_SIZE) * 0.05 }}
                onClick={() => navigate(`/dashboard/product/${product.id}`)}
                className="group cursor-pointer rounded-xl border border-border-hair bg-surface transition-all hover:border-accent hover:shadow-md"
              >
                {/* Image */}
                {product.primary_image_url ? (
                  <img
                    src={`/images/proxy?url=${encodeURIComponent(product.primary_image_url)}`}
                    alt={product.canonical_title}
                    className="aspect-[4/3] w-full rounded-t-xl object-contain bg-background-alt"
                  />
                ) : (
                  <div className="flex aspect-[4/3] items-center justify-center rounded-t-xl bg-background-alt">
                    <ImageOff className="size-10 text-subtle" />
                  </div>
                )}

                <div className="p-4">
                  {/* Title */}
                  <h3 className="line-clamp-2 text-sm font-semibold leading-snug group-hover:text-accent-text">
                    {product.canonical_title}
                  </h3>

                  {/* Badges */}
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {product.brand && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-text">
                        <Star className="size-3" />{product.brand}
                      </span>
                    )}
                    <span className="rounded-full bg-background-alt px-2 py-0.5 text-[11px] font-medium text-muted">
                      {product.category}
                    </span>
                  </div>

                  {/* Platform count */}
                  <p className="mt-2 flex items-center gap-1 text-xs text-muted">
                    <ArrowUpRight className="size-3" />
                    Available on {product.platform_count} platform{product.platform_count !== 1 ? 's' : ''}
                  </p>

                  {/* Price + best value */}
                  <div className="mt-3 flex items-center justify-between border-t border-border-hair pt-3">
                    <span className="text-sm font-semibold">
                      {formatPrice(product.min_price, product.max_price) ?? 'Price N/A'}
                    </span>
                    {product.min_price !== null && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
                        <Trophy className="size-3" />Best value
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Load more */}
        {hasMore && (
          <div className="flex justify-center">
            <button
              onClick={loadMore}
              disabled={loading}
              className="rounded-lg border border-border-hair bg-surface px-6 py-2.5 text-sm font-medium transition-colors hover:border-accent hover:text-accent-text disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Load more products'}
            </button>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
