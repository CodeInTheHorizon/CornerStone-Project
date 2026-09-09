/**
 * Typed access to Vite environment variables.
 *
 * Only VITE_-prefixed variables are exposed to the browser bundle, so no
 * secret may ever be read here. See .env.example at the repository root.
 */

export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  appName: import.meta.env.VITE_APP_NAME ?? 'MarketPulse AI',
} as const
