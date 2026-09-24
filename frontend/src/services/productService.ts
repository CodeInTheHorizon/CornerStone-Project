import { apiRequest } from './apiClient'

export interface ProductSummary {
  id: number
  canonical_title: string
  brand: string | null
  category: string
  primary_image_url: string | null
  platform_count: number
  min_price: number | null
  max_price: number | null
}

export interface ListingOut {
  id: number
  platform: string
  platform_product_id: string | null
  product_url: string | null
  title_on_platform: string
  image_url: string
  image_urls: string[] | null
  price_current: number | null
  price_original: number | null
  currency: string
  discount_pct: number | null
  rating: number | null
  review_count: number | null
  seller_name: string | null
  seller_count: number | null
  offer_count: number | null
  in_stock: boolean | null
  min_order_qty: number | null
  price_min: number | null
  price_max: number | null
  match_confidence: number | null
  scraped_at: string
  is_stale: boolean
}

export interface ProductOut {
  id: number
  canonical_title: string
  brand: string | null
  model_number: string | null
  category: string
  subcategory: string | null
  primary_image_url: string | null
  listings: ListingOut[]
}

export interface PricePoint {
  price: number | null
  discount_pct: number | null
  rating: number | null
  review_count: number | null
  seller_count: number | null
  observed_at: string
}

export interface ScoreComponent {
  raw_value: number | null
  normalized: number
  weight: number
  contribution: number
}

export interface ScoreOut {
  platform: string
  score: number
  rank: number
  components: Record<string, ScoreComponent>
  explanation: string
  suggested_inventory_share_pct: number
  computed_at: string | null
}

export interface ScoreResponse {
  product_id: number
  product_title: string
  scores: ScoreOut[]
}

export interface TrackedOut {
  id: number
  product_id: number
  product_title: string
  added_at: string
  refresh_interval_minutes: number
  platform_count: number
}

export async function listProducts(
  token: string,
  options?: { q?: string; category?: string; brand?: string; limit?: number; offset?: number },
): Promise<ProductSummary[]> {
  const params = new URLSearchParams()
  if (options?.q) params.set('q', options.q)
  if (options?.category) params.set('category', options.category)
  if (options?.brand) params.set('brand', options.brand)
  if (options?.limit) params.set('limit', String(options.limit))
  if (options?.offset) params.set('offset', String(options.offset))
  const qs = params.toString()
  return apiRequest<ProductSummary[]>(`/products${qs ? `?${qs}` : ''}`, { token })
}

export async function getProduct(token: string, id: number): Promise<ProductOut> {
  return apiRequest<ProductOut>(`/products/${id}`, { token })
}

export async function getProductListings(token: string, id: number): Promise<ListingOut[]> {
  return apiRequest<ListingOut[]>(`/products/${id}/listings`, { token })
}

export async function getProductHistory(
  token: string,
  id: number,
  platform?: string,
): Promise<Record<string, PricePoint[]>> {
  const params = platform ? `?platform=${platform}` : ''
  return apiRequest<Record<string, PricePoint[]>>(`/products/${id}/history${params}`, { token })
}

export async function getProductScores(
  token: string,
  id: number,
  recompute = false,
): Promise<ScoreResponse> {
  return apiRequest<ScoreResponse>(`/scores/${id}${recompute ? '?recompute=true' : ''}`, { token })
}

export async function trackProduct(
  token: string,
  productId: number,
  refreshIntervalMinutes = 360,
): Promise<TrackedOut> {
  return apiRequest<TrackedOut>('/products/track', {
    token,
    method: 'POST',
    body: JSON.stringify({ product_id: productId, refresh_interval_minutes: refreshIntervalMinutes }),
  })
}

export async function listTracked(token: string): Promise<TrackedOut[]> {
  return apiRequest<TrackedOut[]>('/products/tracked/list', { token })
}

export async function untrackProduct(token: string, trackedId: number): Promise<void> {
  return apiRequest<void>(`/products/track/${trackedId}`, { token, method: 'DELETE' })
}
