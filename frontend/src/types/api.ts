/** Shapes returned by the MarketPulse AI backend. */

export interface HealthResponse {
  status: string
  app: string
  version: string
  environment: string
  /** 'connected' when the backend reached its database, else 'unavailable'. */
  database: string
  timestamp: string
}

/** Normalized failure shape surfaced to the UI. */
export interface ApiError {
  message: string
  status?: number
}
