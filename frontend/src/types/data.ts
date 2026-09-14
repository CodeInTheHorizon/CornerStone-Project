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
  source_type: SourceType
  provider: string | null
  items_received: number
  items_collected: number
  items_rejected: number
  duplicates_skipped: number
  collection_run_id: string
  collection_timestamp: string
  warnings: string[]
}

/** Why a collector can or cannot fetch LIVE data right now. */
export type CollectorState =
  | 'live'
  | 'credentials_missing'
  | 'approval_required'
  | 'credentials_rejected'
  | 'rate_limited'
  | 'provider_error'
  | 'unavailable'

export interface PlatformStatus {
  available: boolean
  state: CollectorState
  ingestion_mode: IngestionMode
  access_method: string
  provider: string | null
  reason: string | null
  requires_credentials: boolean
  /** Environment variable names only; never values. */
  required_configuration: string[]
  /** Newest stored observation of any provenance, LIVE or not. */
  last_collection: string | null
  stored_records: number
  /** Provenance types actually stored for this platform. */
  source_types_available: SourceType[]
  live_records: number
  last_live_observation: string | null
  last_successful_fetch: string | null
  last_failed_fetch: string | null
  last_failure_state: string | null
  last_failure_reason: string | null
  retry_after: string | null
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

// --- Model training (Phase 6) ---

export interface ModelRunResult {
  model: string
  metrics: Record<string, number>
  error: string | null
}

export interface TrainRequest {
  dataset_id?: string
  models?: string[]
  /** Required: the provenance classes this model may learn from. */
  source_types: SourceType[]
}

export type QualityStatus = 'below_baseline' | 'experimental' | 'candidate' | 'validated'

/** Phase 12 evaluation evidence for one model. Baselines are accuracies. */
export interface QualityReport {
  quality_status: QualityStatus
  quality_reasons: string[]
  calibration_status: string
  probability_quality: {
    available?: boolean
    assessment?: string
    log_loss?: number
    class_prior_log_loss?: number
    brier_score?: number
    expected_calibration_error?: number
    rows?: number
    minimum_rows_for_interpretation?: number
  }
  baselines: {
    majority_baseline?: number | null
    training_majority_class?: string | null
    training_majority_accuracy?: number | null
    persistence_accuracy?: number | null
    persistence_coverage_rows?: number
    best_baseline_accuracy?: number | null
  }
  split: {
    strategy?: string
    description?: string | null
    boundary?: string
    training_range?: { start: string | null; end: string | null }
    validation_range?: { start: string | null; end: string | null }
    boundary_purged_rows?: number
    leakage_safeguards?: string[]
  }
  data_summary: {
    observation_rows?: number
    labelled_rows?: number | null
    training_rows?: number | null
    validation_rows?: number | null
    observation_dates?: number
    validation_label_dates?: number
    unique_products?: number
    boundary_purged_rows?: number
  }
  source_policy: { selected_source_types?: SourceType[]; dataset_source_types?: SourceType[]; profile?: string; uses_demo?: boolean }
  group_overlap: { validation_listings?: number; listings_also_in_training?: number; unseen_product_validation_rows?: number }
  unseen_product_accuracy: number | null
  legacy: boolean
  leakage_safe_split: boolean
}

export interface TrainResponse {
  status: string
  model_version: string
  selected_model: string
  target: string
  training_rows: number
  validation_rows: number
  metrics: Record<string, number>
  /** Accuracy of always guessing the most common class. */
  majority_baseline: number | null
  dataset_id: string
  dataset_source_types: SourceType[]
  all_models: ModelRunResult[]
  selection_rule: string
  split_strategy: string
  warnings: string[]
  notice: string | null
  quality: QualityReport | null
}

export interface TrainingRunSummary {
  model_version: string
  model_type: string | null
  trained_at: string | null
  dataset_id: string | null
  accuracy: number | null
  f1_weighted: number | null
  source_types: SourceType[]
  is_active: boolean
  quality_status: QualityStatus | null
}

export interface ModelStatus {
  trained: boolean
  active_model: string | null
  version: string | null
  model_name: string | null
  target: string | null
  trained_at: string | null
  dataset_id: string | null
  dataset_source_types: SourceType[]
  primary_metric: string | null
  primary_metric_value: number | null
  majority_baseline: number | null
  status: string | null
  feature_count: number
  xgboost_available: boolean
  available_models: string[]
  history: TrainingRunSummary[]
  notice: string | null
  quality: QualityReport | null
}

export interface ModelMetrics {
  model_version: string
  selected_model: string | null
  target: string
  trained_at: string | null
  metrics: Record<string, number>
  majority_baseline: number | null
  confusion_matrix: number[][]
  confusion_labels: string[]
  class_distribution: Record<string, number>
  feature_count: number
  feature_names: string[]
  excluded_columns: Record<string, string>
  training_rows: number
  validation_rows: number
  split_strategy: string | null
  selection_rule: string | null
  dataset_id: string | null
  dataset_source_types: SourceType[]
  all_models: ModelRunResult[]
  warnings: string[]
  notice: string | null
  quality: QualityReport | null
}
