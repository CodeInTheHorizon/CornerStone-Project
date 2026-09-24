/** Marketplace identifiers as stored by the backend, with a stable series colour each. */

export const PLATFORM_KEYS = ['amazon', 'flipkart', 'croma', 'alibaba'] as const

const colours: Record<string, string> = {
  amazon: 'var(--chart-1)',
  flipkart: 'var(--chart-2)',
  croma: 'var(--chart-3)',
  alibaba: 'var(--chart-4)',
}

/** CSS colour for a platform's series; unknown platforms fall back to muted text. */
export function platformColour(platform: string): string {
  return colours[platform] ?? 'var(--muted)'
}
