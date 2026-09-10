/** Marketplace data collection endpoints. */

import { ApiRequestError, apiRequest } from '@/services/apiClient'
import { env } from '@/config/env'
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

/**
 * Uploads a CSV/JSON dataset.
 *
 * Uses fetch directly rather than apiRequest: the body is FormData, and the
 * browser must set its own multipart boundary, which apiRequest's JSON
 * Content-Type header would override.
 */
export async function importDataset(
  token: string,
  file: File,
): Promise<IngestSummary> {
  const body = new FormData()
  body.append('file', file)

  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}/data/import`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body,
    })
  } catch {
    throw new ApiRequestError(
      `Could not reach the API at ${env.apiBaseUrl}. Is the backend running?`,
    )
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : `Import failed with status ${response.status}.`
    throw new ApiRequestError(detail, response.status)
  }

  return payload as IngestSummary
}

export function loadDemoDataset(token: string): Promise<IngestSummary> {
  return apiRequest<IngestSummary>('/data/demo/load', { method: 'POST', token })
}
