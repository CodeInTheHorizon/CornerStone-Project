/** Dataset builder endpoints (Phase 5). */

import { apiRequest } from '@/services/apiClient'
import type {
  DatasetBuildRequest,
  DatasetBuildResponse,
  DatasetPreview,
  DatasetStatus,
} from '@/types/data'

export function buildDataset(
  token: string,
  payload: DatasetBuildRequest,
): Promise<DatasetBuildResponse> {
  return apiRequest<DatasetBuildResponse>('/ml/dataset/build', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  })
}

export function fetchDatasetStatus(token: string): Promise<DatasetStatus> {
  return apiRequest<DatasetStatus>('/ml/dataset/status', { token })
}

export function fetchDatasetPreview(
  token: string,
  limit = 10,
): Promise<DatasetPreview> {
  return apiRequest<DatasetPreview>(`/ml/dataset/preview?limit=${limit}`, {
    token,
  })
}
