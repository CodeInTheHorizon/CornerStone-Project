/** Marketplace identifiers as stored by the backend, with a stable series colour each. */

export const PLATFORM_KEYS = ['amazon', 'flipkart', 'meesho', 'croma', 'alibaba'] as const

const colours: Record<string, string> = {
  amazon: 'var(--chart-1)',
  flipkart: 'var(--chart-2)',
  meesho: 'var(--chart-5, #e11d48)',
  croma: 'var(--chart-3)',
  alibaba: 'var(--chart-4)',
}

/** CSS colour for a platform's series; unknown platforms fall back to muted text. */
export function platformColour(platform: string): string {
  return colours[platform] ?? 'var(--muted)'
}
