/** Backend system/status endpoints. */

import { apiRequest } from '@/services/apiClient'
import type { HealthResponse } from '@/types/api'

export function fetchHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health')
}
