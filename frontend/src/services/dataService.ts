/** Marketplace data collection endpoints. */

import { apiRequest } from '@/services/apiClient'
import type {
  CollectRequest,
  CollectResponse,
  CollectorStatus,
  SnapshotList,
} from '@/types/data'

export function collect(
  token: string,
  payload: CollectRequest,
): Promise<CollectResponse> {
  return apiRequest<CollectResponse>('/data/collect', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  })
}

export function fetchLatest(
  token: string,
  params: { platform?: string; keyword?: string; limit?: number } = {},
): Promise<SnapshotList> {
  const query = new URLSearchParams()
  if (params.platform) query.set('platform', params.platform)
  if (params.keyword) query.set('keyword', params.keyword)
  query.set('limit', String(params.limit ?? 50))

  return apiRequest<SnapshotList>(`/data/latest?${query}`, { token })
}

export function fetchStatus(token: string): Promise<CollectorStatus> {
  return apiRequest<CollectorStatus>('/data/status', { token })
}
