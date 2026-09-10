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

// --- Dataset builder (Phase 5) ---

export interface DatasetMetadata {
  dataset_id: string
  generated_at: string
  total_input_rows: number
  total_output_rows: number
  removed_rows: number
  removal_reasons: Record<string, number>
  platforms: string[]
  categories: string[]
  source_types: SourceType[]
  date_range: { start: string | null; end: string | null }
  feature_count: number
  feature_names: string[]
  products: number
  dataset_version: string
  contains_demo_data: boolean
  demo_only: boolean
  csv_path: string | null
  metadata_path: string | null
}

export interface DatasetBuildRequest {
  platforms?: string[]
  categories?: string[]
  keyword?: string
  source_types?: SourceType[]
  persist?: boolean
}

export interface DatasetBuildResponse {
  status: string
  dataset_id: string
  rows: number
  features: number
  source_types: SourceType[]
  removed_rows: number
  generated_at: string
  metadata: DatasetMetadata
  /** Present whenever the dataset contains synthetic rows. Never suppress it. */
  notice: string | null
}

export interface DatasetStatus {
  has_dataset: boolean
  latest: DatasetMetadata | null
  stored_datasets: number
  available_features: string[]
  notice: string | null
}

export interface DatasetPreview {
  dataset_id: string
  rows: Record<string, unknown>[]
  columns: string[]
  total_rows: number
  notice: string | null
}
