/** Marketplace data shapes returned by the backend. */

export type SourceType = 'live' | 'imported' | 'demo'

export type IngestionMode =
  | 'LIVE_API'
  | 'LIVE_PUBLIC_SOURCE'
  | 'IMPORTED'
  | 'DEMO'
  | 'UNAVAILABLE'

export interface Snapshot {
  id: number
  platform: string
  source_type: SourceType
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
  ingestion_mode: IngestionMode
  access_method: string
  reason: string | null
  requires_credentials: boolean
  required_configuration: string[]
  last_collection: string | null
  stored_records: number
  /** Provenance types actually stored for this platform. */
  source_types_available: SourceType[]
}

export interface DemoDatasetInfo {
  available: boolean
  record_count: number
  platforms: string[]
  categories: string[]
  loaded_records: number
  reason: string | null
}

export interface CollectorStatus {
  platforms: Record<string, PlatformStatus>
  total_snapshots: number
  last_collection: string | null
  records_by_source_type: Partial<Record<SourceType, number>>
  demo_dataset: DemoDatasetInfo
}

/** Outcome of an import or a demo load. */
export interface IngestSummary {
  status: string
  source_type: SourceType
  batch_id: string
  timestamp: string
  stored: number
  rejected: number
  duplicates: number
  platforms: string[]
  warnings: string[]
  rejected_rows: string[]
}
