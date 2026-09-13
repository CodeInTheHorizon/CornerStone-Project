/** Marketplace data collection endpoints. */

import { apiRequest } from '@/services/apiClient'
import type {
  CollectRequest,
  CollectResponse,
  CollectorStatus,
  IngestSummary,
  SnapshotList,
  SourceType,
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
  params: {
    platform?: string
    keyword?: string
    sourceType?: SourceType
    limit?: number
  } = {},
): Promise<SnapshotList> {
  const query = new URLSearchParams()
  if (params.platform) query.set('platform', params.platform)
  if (params.keyword) query.set('keyword', params.keyword)
  if (params.sourceType) query.set('source_type', params.sourceType)
  query.set('limit', String(params.limit ?? 50))

  return apiRequest<SnapshotList>(`/data/latest?${query}`, { token })
}

export function fetchStatus(token: string): Promise<CollectorStatus> {
  return apiRequest<CollectorStatus>('/data/status', { token })
}

/** Multipart upload shares error, timeout and authentication handling. */
export async function importDataset(token: string, file: File): Promise<IngestSummary> {
  const body = new FormData()
  body.append('file', file)
  return apiRequest<IngestSummary>('/data/import', { method: 'POST', token, body, timeoutMs: 120_000 })
}

export function loadDemoDataset(token: string): Promise<IngestSummary> {
  return apiRequest<IngestSummary>('/data/demo/load', { method: 'POST', token })
}
