import { apiRequest } from '@/services/apiClient'

export interface Alert {
  id: number
  user_id: number
  product_name: string
  platform: string
  condition: 'below' | 'above' | 'change_pct'
  threshold: number
  currency: string
  active: boolean
  triggered_at: string | null
  triggered_value: number | null
  created_at: string
  updated_at: string
}

interface AlertListResponse {
  alerts: Alert[]
  total: number
}

interface AlertCreatePayload {
  product_name: string
  platform: string
  condition: 'below' | 'above' | 'change_pct'
  threshold: number
  currency?: string
}

export const fetchAlerts = (token: string) =>
  apiRequest<AlertListResponse>('/alerts', { token })

export const fetchTriggered = (token: string) =>
  apiRequest<Alert[]>('/alerts/triggered', { token })

export const createAlert = (token: string, data: AlertCreatePayload) =>
  apiRequest<Alert>('/alerts', { token, method: 'POST', body: JSON.stringify(data) })

export const deleteAlert = (token: string, id: number) =>
  apiRequest<void>(`/alerts/${id}`, { token, method: 'DELETE' })

export const updateAlert = (token: string, id: number, data: { active?: boolean; threshold?: number; condition?: string }) =>
  apiRequest<Alert>(`/alerts/${id}`, { token, method: 'PATCH', body: JSON.stringify(data) })
