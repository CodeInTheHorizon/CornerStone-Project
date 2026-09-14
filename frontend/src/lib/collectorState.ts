import type { CollectorState } from '@/types/data'

export type CollectorTone = 'ok' | 'warn' | 'down' | 'idle'

/** Label and tone per collector state. "LIVE ready" is not a claim that LIVE data exists. */
export const collectorStatePresentation: Record<CollectorState, { tone: CollectorTone; label: string }> = {
  live: { tone: 'ok', label: 'LIVE ready' },
  credentials_missing: { tone: 'idle', label: 'Credentials missing' },
  approval_required: { tone: 'warn', label: 'Approval required' },
  credentials_rejected: { tone: 'down', label: 'Credentials rejected' },
  rate_limited: { tone: 'warn', label: 'Rate limited' },
  provider_error: { tone: 'down', label: 'Provider error' },
  unavailable: { tone: 'idle', label: 'Unavailable' },
}

export function collectorStateLabel(state: CollectorState | undefined): string {
  return state ? collectorStatePresentation[state].label : 'Unknown'
}
