/**
 * Typed access to Vite environment variables.
 *
 * Only VITE_-prefixed variables are exposed to the browser bundle, so no
 * secret may ever be read here. See .env.example at the repository root.
 */

/** Strips spaces, dashes and a leading + so wa.me gets bare digits. */
function normalizePhone(raw: string | undefined): string {
  return (raw ?? '').replace(/[^\d]/g, '')
}

const whatsappNumber = normalizePhone(import.meta.env.VITE_WHATSAPP_NUMBER)

export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  appName: import.meta.env.VITE_APP_NAME ?? 'MarketPulse AI',
  /** Digits only, no '+'. Empty when unconfigured. */
  whatsappNumber,
  /** The contact form cannot submit without a destination number. */
  isWhatsappConfigured: whatsappNumber.length >= 8,
} as const
