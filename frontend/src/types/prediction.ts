import type { SourceType } from '@/types/data'

export interface ModelQuality {
  version: string
  type: string | null
  primary_metric: string
  primary_metric_value: number | null
  accuracy: number | null
  majority_baseline: number | null
  below_baseline: boolean | null
  source_types: SourceType[]
  warning: string
}

export interface PlatformPrediction {
  platform: string
  status: string
  reason: string | null
  predicted_class: string | null
  confidence: number | null
  probabilities: Record<string, number> | null
  opportunity_score: number | null
  components: Record<string, number>
  normalized_signals: Record<string, number | null>
  coverage_weight: number
  missing_components: string[]
  key_factors: string[]
  model_version: string
  source_type: SourceType | null
  data_freshness: string | null
  stale: boolean
  warning: string
}

export interface PredictionResult {
  id: number
  product: string
  product_key: string
  created_at: string
  recommended_platform: string
  recommendation_label: string
  ranking: PlatformPrediction[]
  platform_results: PlatformPrediction[]
  score_difference: number | null
  key_factors: string[]
  model: ModelQuality
  data_provenance: { dataset_id: string; source_types: SourceType[]; model_source_types: SourceType[] }
  formula: { version: string; weights: Record<string, number>; explanations: Record<string, string>; missing_policy: string }
  warning: string
}

export interface PredictionHistory {
  total: number
  items: {
    id: number
    product: string
    recommended_platform: string | null
    top_score: number | null
    model_version: string | null
    source_types: SourceType[]
    created_at: string
    model: ModelQuality | null
    warning: string
  }[]
}

export interface PredictionOptions {
  dataset_id: string
  generated_at: string | null
  total: number
  source_types: SourceType[]
  products: {
    product_key: string
    product_name: string
    category: string
    platforms: {
      platform: string
      source_type: SourceType
      data_freshness: string | null
      stale: boolean
      effective_price: number | null
      currency: string
      rating: number | null
      review_count: number | null
    }[]
  }[]
}
