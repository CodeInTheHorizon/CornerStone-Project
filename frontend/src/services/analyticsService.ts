import { apiRequest } from '@/services/apiClient'
import type { AnalyticsFilters, AnalyticsOptions, AnalyticsSummary, ComparisonResponse, TrendsResponse } from '@/types/analytics'

function query(filters: AnalyticsFilters, extra: Record<string, string> = {}) {
  const params = new URLSearchParams(extra)
  for (const [name, value] of Object.entries(filters)) if (value) params.set(name, value)
  return params.toString()
}
export const fetchTrends = (token: string, filters: AnalyticsFilters, offset = 0) => apiRequest<TrendsResponse>(`/analytics/trends?${query(filters, { offset: String(offset), limit: '20' })}`, { token })
export const fetchComparison = (token: string, filters: AnalyticsFilters) => apiRequest<ComparisonResponse>(`/analytics/platform-comparison?${query(filters)}`, { token })
export const fetchAnalyticsSummary = (token: string) => apiRequest<AnalyticsSummary>('/analytics/summary', { token })
export const fetchAnalyticsOptions = (token: string, filters: AnalyticsFilters, q = '', offset = 0) => apiRequest<AnalyticsOptions>(`/analytics/options?${query(filters, { q, offset: String(offset), limit: '50' })}`, { token })
