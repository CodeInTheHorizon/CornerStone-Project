import { apiRequest } from './apiClient'

export interface SearchListing {
  platform: string
  product_name: string
  brand: string | null
  category: string | null
  external_id: string | null
  image_url: string | null
  image_urls: string[] | null
  price: number | null
  original_price: number | null
  discount_percentage: number | null
  currency: string
  rating: number | null
  review_count: number | null
  availability: string | null
  seller_name: string | null
  seller_count: number | null
  offer_count: number | null
  listing_url: string | null
  min_order_qty: number | null
  price_min: number | null
  price_max: number | null
  supplier_years: number | null
  is_stale: boolean
}

export interface PlatformResult {
  platform: string
  status: 'ok' | 'error' | 'unavailable'
  listings: SearchListing[]
  error: string | null
  latency_ms: number
  from_cache: boolean
}

export interface SearchResponse {
  query: string
  total_results: number
  platforms: PlatformResult[]
}

export async function searchProducts(
  token: string,
  query: string,
  options?: {
    category?: string
    maxItems?: number
    platforms?: string[]
  },
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query })
  if (options?.category) params.set('category', options.category)
  if (options?.maxItems) params.set('max_items', String(options.maxItems))
  if (options?.platforms?.length) params.set('platforms', options.platforms.join(','))
  return apiRequest<SearchResponse>(`/search?${params}`, { token })
}
