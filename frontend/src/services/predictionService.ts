import { apiRequest } from '@/services/apiClient'
import type { PredictionHistory, PredictionOptions, PredictionResult } from '@/types/prediction'

export function fetchPredictionOptions(token: string, query = '', offset = 0) {
  const params = new URLSearchParams({ q: query, offset: String(offset), limit: '50' })
  return apiRequest<PredictionOptions>(`/ml/prediction-options?${params}`, { token })
}

export function makePrediction(token: string, productKey: string, datasetId: string) {
  return apiRequest<PredictionResult>('/ml/predict', {
    token, method: 'POST',
    body: JSON.stringify({ product_key: productKey, dataset_id: datasetId }),
  })
}

export function fetchPredictionHistory(token: string, limit = 10) {
  return apiRequest<PredictionHistory>(`/ml/predictions?limit=${limit}`, { token })
}

export function fetchPrediction(token: string, id: number) {
  return apiRequest<PredictionResult>(`/ml/predictions/${id}`, { token })
}
