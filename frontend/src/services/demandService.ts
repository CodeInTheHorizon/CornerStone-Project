/**
 * Client service for Demand Forecasting model training, benchmarking, and unit sales forecasting.
 */

import { apiRequest } from '@/services/apiClient'

export interface DemandMetrics {
  mae: number
  rmse: number
  r2: number
  wape: number
  mape: number
}

export interface CandidateModel {
  name: string
  algorithm: string
  metrics: DemandMetrics
}

export interface DemandTrainResponse {
  status: string
  selected_model: string
  metrics: DemandMetrics
  training_rows: number
  validation_rows: number
  temporal_split: string
  features: string[]
  candidates: CandidateModel[]
  dataset_source: string
}

export interface DemandStatusResponse {
  has_model: boolean
  model_file: string | null
  algorithm: string
  benchmark_dataset_available: boolean
  primary_metric: string
}

export interface DemandBenchmarkSummary {
  dataset_name: string
  total_records: number
  source_type: string
  platforms: string[]
  date_range: {
    start: string
    end: string
  }
  total_units_sold: number
  average_price: number
  median_units_sold: number
  max_units_sold: number
  sample_columns: string[]
}

export interface SingleForecastParams {
  platform: string
  category: string
  price: number
  discount_percentage?: number
  rating?: number
  review_count?: number
  review_velocity?: number
  inventory?: number
}

export interface ForecastRequest {
  product_id?: number | null
  features?: SingleForecastParams | null
}

export interface ChannelDemandForecast {
  platform: string
  category: string
  price: number
  discount_percentage: number
  predicted_units_sold: number
  forecast_lower_bound: number
  forecast_upper_bound: number
  projected_revenue: number
  demand_grade: string
  is_estimated: boolean
}

export interface DemandForecastResponse {
  status: string
  model_used: string
  forecasts: ChannelDemandForecast[]
  total_projected_units: number
  total_projected_revenue: number
  methodology_note: string
}

export async function fetchDemandBenchmark(token: string): Promise<DemandBenchmarkSummary> {
  return apiRequest<DemandBenchmarkSummary>('/ml/demand/benchmark', { token })
}

export async function fetchDemandStatus(token: string): Promise<DemandStatusResponse> {
  return apiRequest<DemandStatusResponse>('/ml/demand/status', { token })
}

export async function trainDemandModels(
  token: string,
  valFraction = 0.2,
): Promise<DemandTrainResponse> {
  return apiRequest<DemandTrainResponse>(`/ml/demand/train?val_fraction=${valFraction}`, {
    method: 'POST',
    token,
  })
}

export async function forecastDemand(
  token: string,
  payload: ForecastRequest,
): Promise<DemandForecastResponse> {
  return apiRequest<DemandForecastResponse>('/ml/demand/forecast', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  })
}
