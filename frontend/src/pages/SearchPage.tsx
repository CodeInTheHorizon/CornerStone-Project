import { useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import {
  Search,
  Loader2,
  ShoppingBag,
  Star,
  ExternalLink,
  ImageOff,
  Tag,
  AlertCircle,
} from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import {
  searchProducts,
  type SearchResponse,
  type PlatformResult,
  type SearchListing,
} from '@/services/searchService'

const PLATFORM_COLORS: Record<string, string> = {
  amazon: 'text-blue-600',
  flipkart: 'text-yellow-500',
  croma: 'text-green-600',
  alibaba: 'text-orange-500',
}

const STATUS_DOT: Record<string, string> = {
  ok: 'bg-green-500',
  error: 'bg-red-500',
  unavailable: 'bg-yellow-500',
}

function currencySymbol(currency: string) {
  return currency === 'INR' ? '₹' : '$'
}

function ProductCard({ listing }: { listing: SearchListing }) {
  const hasImage = !!listing.image_url
  const imgSrc = hasImage
    ? `/images/proxy?url=${encodeURIComponent(listing.image_url!)}`
    : undefined

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="flex flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
    >
      {hasImage ? (
        <img
          src={imgSrc}
          alt={listing.product_name}
          className="h-44 w-full object-contain bg-gray-50 dark:bg-gray-900 p-2"
          loading="lazy"
        />
      ) : (
        <div className="flex h-44 items-center justify-center bg-gray-100 dark:bg-gray-900">
          <ImageOff className="size-10 text-gray-400" />
        </div>
      )}

      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <h4 className="line-clamp-2 text-sm font-medium leading-snug text-gray-900 dark:text-gray-100">
          {listing.product_name}
        </h4>

        <div className="flex items-baseline gap-2">
          {listing.price != null && (
            <span className="text-base font-semibold text-gray-900 dark:text-white">
              {currencySymbol(listing.currency)}{listing.price.toLocaleString()}
            </span>
          )}
          {listing.original_price != null && listing.discount_percentage != null && (
            <span className="text-xs text-gray-400 line-through">
              {currencySymbol(listing.currency)}{listing.original_price.toLocaleString()}
            </span>
          )}
        </div>

        {listing.rating != null && (
          <div className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
            <Star className="size-3.5 fill-yellow-400 text-yellow-400" />
            <span>{listing.rating.toFixed(1)}</span>
            {listing.review_count != null && (
              <span className="text-gray-400">({listing.review_count.toLocaleString()})</span>
            )}
          </div>
        )}

        {listing.seller_name && (
          <p className="truncate text-xs text-gray-500 dark:text-gray-400">
            <Tag className="mr-1 inline size-3" />
            {listing.seller_name}
          </p>
        )}

        {listing.is_stale && (
          <span className="inline-flex w-fit items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
            Stale
          </span>
        )}

        {listing.listing_url && (
          <a
            href={listing.listing_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-auto inline-flex items-center gap-1 pt-2 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            View on {listing.platform}
            <ExternalLink className="size-3" />
          </a>
        )}
      </div>
    </motion.div>
  )
}

function PlatformSection({ result }: { result: PlatformResult }) {
  const colorClass = PLATFORM_COLORS[result.platform.toLowerCase()] ?? 'text-gray-600'
  const dotClass = STATUS_DOT[result.status] ?? 'bg-gray-400'

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <span className={`inline-block size-2.5 rounded-full ${dotClass}`} />
        <h3 className={`text-lg font-semibold capitalize ${colorClass}`}>
          {result.platform}
        </h3>
      </div>

      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span>{result.listings.length} results</span>
        <span>&middot;</span>
        <span>{result.latency_ms}ms</span>
        {result.from_cache && (
          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
            cached
          </span>
        )}
      </div>

      {result.status === 'error' && result.error && (
        <div className="mb-3 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span>{result.error}</span>
        </div>
      )}

      {result.status === 'unavailable' && (
        <p className="text-sm text-gray-400 italic">Platform unavailable</p>
      )}

      <div className="flex flex-col gap-4">
        {result.listings.map((listing, i) => (
          <ProductCard key={listing.external_id ?? `${listing.product_name}-${i}`} listing={listing} />
        ))}
      </div>
    </div>
  )
}

export function SearchPage() {
  const { token } = useAuth()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || !token) return

    setLoading(true)
    setError(null)
    try {
      const data = await searchProducts(token, trimmed)
      setResponse(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <DashboardLayout title="Product Search" subtitle="Search across Amazon, Flipkart, Croma and Alibaba">
      <form onSubmit={handleSearch} className="mx-auto mb-8 flex max-w-2xl items-center gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search products across platforms..."
            className="w-full rounded-xl border border-gray-300 bg-white py-3 pl-10 pr-4 text-sm shadow-sm outline-none transition-colors focus:border-blue-500 focus:ring-2 focus:ring-blue-200 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:focus:ring-blue-800"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
          Search
        </button>
      </form>

      {error && (
        <div className="mx-auto mb-6 flex max-w-2xl items-start gap-2 rounded-lg bg-red-50 p-4 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center gap-3 py-20 text-gray-400">
          <Loader2 className="size-8 animate-spin" />
          <p className="text-sm">Searching across platforms...</p>
        </div>
      )}

      {!loading && !response && !error && (
        <div className="flex flex-col items-center gap-3 py-20 text-gray-400">
          <ShoppingBag className="size-12" />
          <p className="text-sm">Enter a product name to search across all platforms</p>
        </div>
      )}

      {!loading && response && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {response.platforms.map((platform) => (
            <PlatformSection key={platform.platform} result={platform} />
          ))}
        </div>
      )}
    </DashboardLayout>
  )
}
