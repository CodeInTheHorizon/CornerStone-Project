/** Model training endpoints (Phase 6). */

import { apiRequest } from '@/services/apiClient'
import type {
  ModelMetrics,
  ModelStatus,
  TrainRequest,
  TrainResponse,
} from '@/types/data'

export function trainModel(
  token: string,
  payload: TrainRequest,
): Promise<TrainResponse> {
  return apiRequest<TrainResponse>('/ml/train', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  })
}

export function fetchModelStatus(token: string): Promise<ModelStatus> {
  return apiRequest<ModelStatus>('/ml/status', { token })
}

export function fetchModelMetrics(token: string): Promise<ModelMetrics> {
  return apiRequest<ModelMetrics>('/ml/metrics', { token })
}
