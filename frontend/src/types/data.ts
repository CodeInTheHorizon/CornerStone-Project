/** Marketplace data shapes returned by the backend. */

export interface Snapshot {
  id: number
  platform: string
  source: string
  search_query: string | null
  collection_run_id: string | null

  product_name: string
  brand: string | null
  category: string | null
  subcategory: string | null
  external_id: string | null

  price: number | null
  original_price: number | null
  discount_percentage: number | null
  currency: string

  rating: number | null
  review_count: number | null

  availability: string | null
  seller_name: string | null
  listing_url: string | null

  shipping_info: string | null
  delivery_time: string | null
  badge: string | null
  sponsored: boolean | null
  specifications: Record<string, unknown> | null
  stock_status: string | null

  warnings: string[] | null
  collection_timestamp: string
}

export interface SnapshotList {
  count: number
  items: Snapshot[]
}

export interface CollectRequest {
  platform: string
  keyword: string
  category?: string
  max_items?: number
}

export interface CollectResponse {
  status: string
  platform: string
  keyword: string
  items_collected: number
  items_rejected: number
  duplicates_skipped: number
  collection_run_id: string
  collection_timestamp: string
  warnings: string[]
}

export interface PlatformStatus {
  available: boolean
  access_method: string
  reason: string | null
  requires_credentials: boolean
  last_collection: string | null
  stored_snapshots: number
}

export interface CollectorStatus {
  platforms: Record<string, PlatformStatus>
  total_snapshots: number
  last_collection: string | null
}
