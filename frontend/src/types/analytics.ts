import type { SourceType } from '@/types/data'
import type { ModelQuality } from '@/types/prediction'

export interface AnalyticsFilters {
  product_key?: string
  platform?: string
  category?: string
  source_type?: string
  start_date?: string
  end_date?: string
}
export interface ObservationProvenance {
  source_types: SourceType[]
  records_by_source_type: Partial<Record<SourceType, number>>
  observation_count: number
  duplicates_removed: number
  date_range: { start: string | null; end: string | null }
  notice: string
}
export interface TrendMetric {
  status: string
  reason: string | null
  valid_observations: number
  first: number | null
  latest: number | null
  absolute_change: number | null
  percentage_change: number | null
  average: number | null
  min: number | null
  max: number | null
  direction: string | null
  momentum_per_day: number | null
}
export interface TrendPoint {
  timestamp: string
  price: number | null
  discount: number | null
  discount_derived: boolean
  rating: number | null
  reviews: number | null
  availability: number | null
}
export interface TrendSeries {
  product_key: string
  product_name: string
  platform: string
  source_type: SourceType
  currency: string
  listing_key: string
  observation_count: number
  status: string
  reason: string | null
  date_range: { start: string; end: string }
  price: TrendMetric
  discount: TrendMetric
  rating: TrendMetric
  reviews: TrendMetric
  availability: {
    latest: number | null
    changes: number | null
    status: string
    reason: string | null
    notice: string
    events: { from: number; to: number; previous_observation: string; observed_at: string }[]
  }
  points: TrendPoint[]
}
export interface TrendsResponse {
  status: string
  reason: string | null
  provenance: ObservationProvenance
  calculation_policy: string
  total_series: number
  series: TrendSeries[]
}
export interface ComparisonPlatform {
  platform: string
  status: string
  reason: string | null
  listing_count: number
  listing_density: number
  average_price: number | null
  latest_price: number | null
  average_discount: number | null
  average_rating: number | null
  review_growth: number | null
  review_growth_percentage: number | null
  review_growth_listing_count: number
  latest_price_listing_count: number
  latest_observation: string | null
  earliest_latest_observation: string | null
  opportunity: { score: number; prediction_id: number; model_version: string; model: ModelQuality; warning: string; created_at: string; notice: string } | null
  opportunity_reason: string | null
}
export interface ComparisonResponse {
  status: string
  reason: string | null
  provenance: ObservationProvenance
  groups: { identity: string; grouping: string; source_type: SourceType; currency: string; platforms: ComparisonPlatform[]; status: string; reason: string | null; notice: string }[]
}
export interface AnalyticsOptions {
  products: { product_key: string; product_name: string; category: string }[]
  categories: string[]
  total: number
}
export interface RefreshSource { platform: string; available: boolean; reason: string | null; access_method: string }
export interface AnalyticsSummary {
  total_predictions: number
  stored_records: number
  records_by_source_type: Partial<Record<SourceType, number>>
  latest_observation: string | null
  latest_observation_sources: SourceType[]
  stored_platforms: string[]
  available_live_platforms: string[]
  refresh_sources: RefreshSource[]
  active_model: { version: string; type: string; accuracy: number | null; f1_weighted: number | null; majority_baseline: number | null; source_types: SourceType[] } | null
  latest_dataset: { dataset_id: string; source_types: SourceType[]; generated_at: string | null; file_available: boolean } | null
  notice: string
}
